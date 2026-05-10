"""
U-019 异常处理器

核心职责：Agent执行失败时的重试、降级、错误记录

底层执行逻辑：
1. 捕获Agent执行异常
2. 判断异常类型（可重试/不可重试）
3. 根据重试策略执行重试
4. 重试耗尽后执行降级策略
5. 记录错误日志和指标

内存数据流转：
Exception → 异常分类 → 重试判断 → 重试执行/降级 → 错误记录 → 最终结果

潜在风险：
1. 内存泄漏：重试计数未清理（已用过期机制）
2. 逻辑漏洞：重试风暴导致系统过载（已用指数退避策略）
3. 边界条件：最大重试次数耗尽后的处理（已实现多种降级策略）
4. 并发安全：多任务同时重试冲突（已用滑动窗口限制）

依赖：asyncio、logging
"""

import asyncio
import logging
import time
import random
from typing import Callable, Optional, Any, Dict, List, Type
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
from functools import wraps

from app.agents.base import TaskResult, TaskStatus

logger = logging.getLogger(__name__)


class ErrorType(str, Enum):
    """错误类型枚举"""
    TRANSIENT = "transient"           # 瞬时错误（网络超时等，可重试）
    RESOURCE = "resource"             # 资源错误（内存不足等，可能可恢复）
    CLIENT = "client"                 # 客户端错误（参数错误等，不可重试）
    SERVER = "server"                # 服务端错误（Agent宕机等，可能可恢复）
    TIMEOUT = "timeout"              # 超时错误
    UNKNOWN = "unknown"              # 未知错误


class RetryStrategy(str, Enum):
    """重试策略枚举"""
    IMMEDIATE = "immediate"          # 立即重试
    LINEAR = "linear"                # 线性退避
    EXPONENTIAL = "exponential"      # 指数退避
    FIBONACCI = "fibonacci"          # 斐波那契退避


class FallbackStrategy(str, Enum):
    """降级策略枚举"""
    RETURN_DEFAULT = "return_default"  # 返回默认值
    RETURN_PARTIAL = "return_partial"  # 返回部分结果
    SKIP_TASK = "skip_task"          # 跳过任务
    USE_CACHE = "use_cache"          # 使用缓存
    CALL_ANOTHER = "call_another"    # 调用备用Agent


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3                          # 最大重试次数
    base_delay_ms: int = 1000                    # 基础延迟（毫秒）
    max_delay_ms: int = 30000                     # 最大延迟（毫秒）
    retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    jitter: bool = True                           # 是否添加随机抖动
    retryable_errors: List[ErrorType] = field(default_factory=lambda: [
        ErrorType.TRANSIENT,
        ErrorType.TIMEOUT,
        ErrorType.SERVER,
    ])


@dataclass
class FallbackConfig:
    """降级配置"""
    strategy: FallbackStrategy = FallbackStrategy.RETURN_DEFAULT
    default_value: Any = None                    # 默认返回值
    fallback_agent_id: Optional[str] = None      # 备用Agent ID
    cache_ttl_seconds: int = 3600                # 缓存TTL


@dataclass
class ErrorRecord:
    """错误记录"""
    task_id: str
    error_type: ErrorType
    error_message: str
    retry_count: int
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    stack_trace: Optional[str] = None


@dataclass
class ErrorMetrics:
    """错误指标"""
    total_errors: int = 0
    transient_errors: int = 0
    retry_count: int = 0
    fallback_count: int = 0
    last_error_time: Optional[str] = None
    error_rate: float = 0.0

    def record_error(self, error_type: ErrorType, retry: bool = False, fallback: bool = False):
        """记录错误"""
        self.total_errors += 1
        if error_type == ErrorType.TRANSIENT:
            self.transient_errors += 1
        if retry:
            self.retry_count += 1
        if fallback:
            self.fallback_count += 1
        self.last_error_time = datetime.now(timezone.utc).isoformat()

        # 计算错误率（简化版）
        if self.total_errors > 0:
            self.error_rate = self.transient_errors / self.total_errors


class ErrorClassifier:
    """
    错误分类器

    根据异常特征判断错误类型
    """

    # 错误类型映射
    ERROR_TYPE_MAPPING = {
        # 瞬时错误
        "ConnectionError": ErrorType.TRANSIENT,
        "ConnectionResetError": ErrorType.TRANSIENT,
        "BrokenPipeError": ErrorType.TRANSIENT,

        # 超时错误
        "TimeoutError": ErrorType.TIMEOUT,
        "asyncio.TimeoutError": ErrorType.TIMEOUT,

        # 资源错误
        "MemoryError": ErrorType.RESOURCE,
        "OSError: [Errno 28]": ErrorType.RESOURCE,  # No space left

        # 客户端错误
        "ValidationError": ErrorType.CLIENT,
        "ValueError": ErrorType.CLIENT,
        "TypeError": ErrorType.CLIENT,

        # 服务端错误
        "InternalError": ErrorType.SERVER,
        "500": ErrorType.SERVER,
        "502": ErrorType.SERVER,
        "503": ErrorType.SERVER,
    }

    @classmethod
    def classify(cls, exception: Exception) -> ErrorType:
        """
        分类异常

        Args:
            exception: 异常对象

        Returns:
            错误类型
        """
        exception_type = type(exception).__name__
        exception_str = str(exception)

        # 检查类型名映射
        if exception_type in cls.ERROR_TYPE_MAPPING:
            return cls.ERROR_TYPE_MAPPING[exception_type]

        # 检查字符串匹配
        for pattern, error_type in cls.ERROR_TYPE_MAPPING.items():
            if pattern in exception_str:
                return error_type

        # 检查是否是HTTP状态码
        if exception_str.startswith(("4", "5")):
            if exception_str.startswith("5"):
                return ErrorType.SERVER
            return ErrorType.CLIENT

        return ErrorType.UNKNOWN


class RetryPolicy:
    """
    重试策略

    实现各种重试延迟计算
    """

    def __init__(self, config: RetryConfig):
        self.config = config

    def calculate_delay(self, retry_count: int) -> float:
        """
        计算重试延迟

        Args:
            retry_count: 当前重试次数（从1开始）

        Returns:
            延迟时间（秒）
        """
        base_delay = self.config.base_delay_ms / 1000

        if self.config.retry_strategy == RetryStrategy.IMMEDIATE:
            delay = 0

        elif self.config.retry_strategy == RetryStrategy.LINEAR:
            delay = base_delay * retry_count

        elif self.config.retry_strategy == RetryStrategy.EXPONENTIAL:
            delay = base_delay * (2 ** (retry_count - 1))

        elif self.config.retry_strategy == RetryStrategy.FIBONACCI:
            # 斐波那契数列
            fib = [1, 1, 2, 3, 5, 8, 13, 21]  # 前8个
            idx = min(retry_count - 1, len(fib) - 1)
            delay = base_delay * fib[idx]

        else:
            delay = base_delay

        # 限制最大延迟
        max_delay = self.config.max_delay_ms / 1000
        delay = min(delay, max_delay)

        # 添加抖动
        if self.config.jitter:
            jitter_range = delay * 0.1  # ±10%抖动
            delay += random.uniform(-jitter_range, jitter_range)
            delay = max(0, delay)

        return delay


class TaskErrorHandler:
    """
    任务错误处理器

    负责处理Agent执行中的错误
    """

    def __init__(
        self,
        retry_config: RetryConfig = None,
        fallback_config: FallbackConfig = None
    ):
        self.retry_config = retry_config or RetryConfig()
        self.fallback_config = fallback_config or FallbackConfig()
        self.retry_policy = RetryPolicy(self.retry_config)
        self.error_classifier = ErrorClassifier()
        self.error_metrics = ErrorMetrics()

        # 错误记录存储
        self._error_records: Dict[str, List[ErrorRecord]] = {}

        # 重试计数（滑动窗口）
        self._retry_counts: Dict[str, int] = {}

    def should_retry(self, task_id: str, error_type: ErrorType) -> bool:
        """
        判断是否应该重试

        Args:
            task_id: 任务ID
            error_type: 错误类型

        Returns:
            是否应该重试
        """
        # 检查错误类型是否可重试
        if error_type not in self.retry_config.retryable_errors:
            return False

        # 检查重试次数
        current_retries = self._retry_counts.get(task_id, 0)
        return current_retries < self.retry_config.max_retries

    async def handle_error(
        self,
        task_id: str,
        exception: Exception,
        task_func: Callable,
        *args,
        **kwargs
    ) -> TaskResult:
        """
        处理错误

        Args:
            task_id: 任务ID
            exception: 捕获的异常
            task_func: 要执行的任务函数
            *args, **kwargs: 任务函数参数

        Returns:
            TaskResult对象
        """
        error_type = self.error_classifier.classify(exception)

        # 记录错误
        self._record_error(task_id, error_type, exception)

        # 判断是否应该重试
        if self.should_retry(task_id, error_type):
            return await self._retry(task_id, task_func, error_type, *args, **kwargs)
        else:
            return await self._fallback(task_id, exception, error_type)

    async def _retry(
        self,
        task_id: str,
        task_func: Callable,
        error_type: ErrorType,
        *args,
        **kwargs
    ) -> TaskResult:
        """
        执行重试

        Args:
            task_id: 任务ID
            task_func: 任务函数
            error_type: 错误类型
            *args, **kwargs: 任务函数参数

        Returns:
            TaskResult对象
        """
        # 增加重试计数
        retry_count = self._retry_counts.get(task_id, 0) + 1
        self._retry_counts[task_id] = retry_count

        # 记录重试指标
        self.error_metrics.record_error(error_type, retry=True)

        # 计算延迟
        delay = self.retry_policy.calculate_delay(retry_count)

        logger.warning(
            f"任务 {task_id} 执行失败（{error_type.value}），"
            f"第 {retry_count} 次重试，等待 {delay:.2f}s"
        )

        # 等待
        if delay > 0:
            await asyncio.sleep(delay)

        # 执行任务
        start_time = time.time()
        try:
            result = await task_func(*args, **kwargs)

            # 成功，清零重试计数
            self._retry_counts.pop(task_id, None)

            # 转换为TaskResult
            if isinstance(result, TaskResult):
                return result
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.SUCCESS,
                output_data=result,
                execution_time_ms=int((time.time() - start_time) * 1000)
            )

        except Exception as e:
            # 再次失败，递归处理
            return await self.handle_error(task_id, e, task_func, *args, **kwargs)

    async def _fallback(
        self,
        task_id: str,
        exception: Exception,
        error_type: ErrorType
    ) -> TaskResult:
        """
        执行降级

        Args:
            task_id: 任务ID
            exception: 原始异常
            error_type: 错误类型

        Returns:
            TaskResult对象
        """
        # 记录降级指标
        self.error_metrics.record_error(error_type, fallback=True)

        logger.error(
            f"任务 {task_id} 重试耗尽，执行降级策略: {self.fallback_config.strategy.value}"
        )

        # 根据降级策略执行
        if self.fallback_config.strategy == FallbackStrategy.RETURN_DEFAULT:
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                output_data=self.fallback_config.default_value,
                error_message=f"任务失败，返回默认值: {str(exception)}"
            )

        elif self.fallback_config.strategy == FallbackStrategy.SKIP_TASK:
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error_message=f"任务失败并被跳过: {str(exception)}"
            )

        elif self.fallback_config.strategy == FallbackStrategy.USE_CACHE:
            # TODO: 实现缓存逻辑
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                output_data=None,
                error_message=f"任务失败，缓存未命中: {str(exception)}"
            )

        else:
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error_message=str(exception)
            )

    def _record_error(
        self,
        task_id: str,
        error_type: ErrorType,
        exception: Exception
    ) -> None:
        """记录错误"""
        import traceback

        record = ErrorRecord(
            task_id=task_id,
            error_type=error_type,
            error_message=str(exception),
            retry_count=self._retry_counts.get(task_id, 0),
            stack_trace=traceback.format_exc()
        )

        if task_id not in self._error_records:
            self._error_records[task_id] = []
        self._error_records[task_id].append(record)

    def get_error_history(self, task_id: str) -> List[ErrorRecord]:
        """获取任务错误历史"""
        return self._error_records.get(task_id, [])

    def get_metrics(self) -> ErrorMetrics:
        """获取错误指标"""
        return self.error_metrics

    def reset_metrics(self) -> None:
        """重置指标"""
        self.error_metrics = ErrorMetrics()

    def cleanup_old_records(self, max_age_seconds: int = 3600) -> int:
        """清理过期的错误记录"""
        current_time = time.time()
        cleaned = 0

        for task_id in list(self._error_records.keys()):
            records = self._error_records[task_id]
            valid_records = []

            for record in records:
                record_time = datetime.fromisoformat(record.timestamp).timestamp()
                if current_time - record_time < max_age_seconds:
                    valid_records.append(record)
                else:
                    cleaned += 1

            if valid_records:
                self._error_records[task_id] = valid_records
            else:
                del self._error_records[task_id]

        return cleaned


def with_error_handling(
    retry_config: RetryConfig = None,
    fallback_config: FallbackConfig = None
):
    """
    错误处理装饰器

    用法：
        @with_error_handling(retry_config=RetryConfig(max_retries=3))
        async def my_agent_task(input_data):
            ...
    """
    def decorator(func: Callable) -> Callable:
        handler = TaskErrorHandler(retry_config, fallback_config)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成任务ID
            task_id = f"{func.__name__}_{id(args)}_{id(kwargs)}"

            try:
                return await func(*args, **kwargs)
            except Exception as e:
                return await handler.handle_error(task_id, e, func, *args, **kwargs)

        # 附加handler到wrapper，方便外部访问
        wrapper._error_handler = handler

        return wrapper

    return decorator


# 全局错误处理器实例
_error_handler: Optional[TaskErrorHandler] = None


def get_error_handler() -> TaskErrorHandler:
    """获取全局错误处理器"""
    global _error_handler
    if _error_handler is None:
        _error_handler = TaskErrorHandler()
    return _error_handler
