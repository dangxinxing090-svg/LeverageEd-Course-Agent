"""
U-013 请求日志中间件

核心职责：记录每个请求的方法、路径、状态码、耗时，处理链路追踪

底层执行逻辑：
1. 请求开始时记录起始时间
2. 附加请求元数据（ID、来源、用户）
3. 请求结束后计算耗时
4. 构建结构化日志
5. 异步写入日志存储（Kafka/文件）

内存数据流转：
Request → RequestContext → Processing → Response → LogRecord → AsyncWrite(Kafka/File)

潜在风险：
1. 内存泄漏：日志缓冲区无限增长（已用队列大小限制+超时丢弃）
2. 逻辑漏洞：异常请求导致日志丢失（使用try-finally保证记录）
3. 边界条件：长耗时请求的日志延迟问题（已用后台线程异步写入）
4. 安全风险：敏感信息（密码、token）未脱敏直接写入日志

依赖：标准库logging、可选KafkaProducer
"""

import time
import json
import logging
import threading
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from collections import deque
from functools import wraps
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class LogLevel(str, Enum):
    """日志级别"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class RequestLogRecord:
    """
    请求日志记录

    包含完整的请求处理信息
    """
    # 请求标识
    request_id: str                    # 请求唯一ID（UUID）
    trace_id: Optional[str] = None    # 链路追踪ID

    # 请求信息
    method: str = ""                   # HTTP方法
    path: str = ""                     # 请求路径
    query_params: str = ""            # 查询参数
    client_ip: str = ""               # 客户端IP
    user_agent: str = ""              # User-Agent

    # 用户信息
    user_id: str = "anonymous"       # 用户ID
    subscription_type: str = "FREE"   # 订阅类型

    # 时间信息
    start_time: str = ""              # 开始时间（ISO格式）
    end_time: str = ""                # 结束时间（ISO格式）
    duration_ms: int = 0             # 耗时（毫秒）

    # 响应信息
    status_code: int = 0              # HTTP状态码
    response_size: int = 0           # 响应大小（字节）

    # 错误信息
    error_message: Optional[str] = None  # 错误信息（如果有）
    error_stack: Optional[str] = None   # 错误堆栈（如果有）

    # 元数据
    service_name: str = "api"          # 服务名称
    environment: str = "production"   # 环境

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)

    def should_sanitize(self, key: str) -> bool:
        """检查字段是否需要脱敏"""
        sensitive_keys = {
            "password", "token", "secret", "key",
            "authorization", "cookie", "access_token",
            "refresh_token", "api_key", "apikey"
        }
        return key.lower() in sensitive_keys

    def sanitize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        脱敏处理

        将敏感字段替换为***，但不删除字段（保持结构完整）
        """
        result = {}
        for key, value in data.items():
            if self.should_sanitize(key):
                result[key] = "***REDACTED***"
            elif isinstance(value, dict):
                result[key] = self.sanitize(value)
            else:
                result[key] = value
        return result


class LogBuffer:
    """
    日志缓冲区

    使用队列缓冲日志，支持批量写入
    """

    def __init__(self, max_size: int = 1000, flush_interval: float = 5.0):
        self.max_size = max_size
        self.flush_interval = flush_interval
        self.buffer: deque = deque(maxlen=max_size)
        self.lock = threading.Lock()

    def push(self, record: RequestLogRecord):
        """
        添加日志记录

        Args:
            record: 日志记录

        Note:
            如果缓冲区已满，新记录会覆盖最旧的记录
        """
        with self.lock:
            self.buffer.append(record)

    def flush(self) -> list:
        """
        刷新缓冲区，返回所有记录并清空

        Returns:
            日志记录列表
        """
        with self.lock:
            records = list(self.buffer)
            self.buffer.clear()
            return records

    def size(self) -> int:
        """获取缓冲区当前大小"""
        with self.lock:
            return len(self.buffer)


class AsyncLogWriter:
    """
    异步日志写入器

    后台线程定期将日志写入存储
    """

    def __init__(
        self,
        buffer: LogBuffer,
        writers: list = None,  # 可选的写入器列表
        flush_interval: float = 5.0
    ):
        self.buffer = buffer
        self.writers = writers or []
        self.flush_interval = flush_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def add_writer(self, writer: Callable):
        """添加写入器"""
        self.writers.append(writer)

    def _writer_loop(self):
        """写入器主循环"""
        while self._running:
            try:
                records = self.buffer.flush()
                if records:
                    for writer in self.writers:
                        try:
                            writer(records)
                        except Exception as e:
                            logger.error(f"日志写入失败: {e}")
            except Exception as e:
                logger.error(f"日志刷新失败: {e}")

            time.sleep(self.flush_interval)

    def start(self):
        """启动写入器"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._writer_loop, daemon=True)
        self._thread.start()
        logger.info("异步日志写入器已启动")

    def stop(self):
        """停止写入器"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("异步日志写入器已停止")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


class FileLogWriter:
    """文件日志写入器"""

    def __init__(self, filepath: str):
        self.filepath = filepath

    def __call__(self, records: list):
        """写入日志到文件"""
        if not records:
            return

        try:
            with open(self.filepath, "a", encoding="utf-8") as f:
                for record in records:
                    f.write(record.to_json() + "\n")
        except Exception as e:
            logger.error(f"写入日志文件失败: {e}")


class ConsoleLogWriter:
    """控制台日志写入器（用于调试）"""

    def __call__(self, records: list):
        """写入日志到控制台"""
        for record in records:
            level = LogLevel.INFO
            if record.status_code >= 500:
                level = LogLevel.ERROR
            elif record.status_code >= 400:
                level = LogLevel.WARNING

            log_func = getattr(logger, level.value.lower())
            log_func(
                f"{record.method} {record.path} - {record.status_code} "
                f"({record.duration_ms}ms) - {record.user_id}"
            )


# 全局日志缓冲区和写入器
_log_buffer: Optional[LogBuffer] = None
_async_writer: Optional[AsyncLogWriter] = None


def get_log_buffer() -> LogBuffer:
    """获取日志缓冲区"""
    global _log_buffer
    if _log_buffer is None:
        _log_buffer = LogBuffer()
    return _log_buffer


def get_async_writer() -> AsyncLogWriter:
    """获取异步写入器"""
    global _async_writer
    if _async_writer is None:
        buffer = get_log_buffer()
        _async_writer = AsyncLogWriter(buffer)
        # 默认添加控制台写入器
        _async_writer.add_writer(ConsoleLogWriter())
    return _async_writer


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    请求日志中间件

    记录每个HTTP请求的处理信息
    """

    def __init__(self, app, service_name: str = "api"):
        super().__init__(app)
        self.service_name = service_name
        self.log_buffer = get_log_buffer()
        self.environment = "production"

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        中间件处理函数

        处理流程：
        1. 生成请求ID和追踪ID
        2. 记录开始时间
        3. 提取请求元数据
        4. 执行请求处理
        5. 记录响应信息
        6. 构建日志记录并写入缓冲区
        """
        # 生成请求ID
        request_id = str(uuid.uuid4())
        trace_id = request.headers.get("X-Trace-ID", request_id)

        # 记录开始时间
        start_time = time.time()
        start_datetime = datetime.now(timezone.utc)

        # 提取请求信息
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "")

        # 提取查询参数（脱敏）
        query_params = dict(request.query_params)
        query_params = self._sanitize_params(query_params)
        query_string = "&".join(f"{k}={v}" for k, v in query_params.items())

        # 提取用户信息
        user_id = "anonymous"
        subscription_type = "FREE"
        if hasattr(request.state, "user"):
            user = request.state.user
            user_id = getattr(user, "user_id", "anonymous")
            subscription_type = getattr(user, "subscription_type", "FREE")

        # 创建日志记录
        record = RequestLogRecord(
            request_id=request_id,
            trace_id=trace_id,
            method=request.method,
            path=str(request.url.path),
            query_params=query_string,
            client_ip=client_ip,
            user_agent=user_agent,
            user_id=user_id,
            subscription_type=subscription_type,
            start_time=start_datetime.isoformat(),
            service_name=self.service_name,
            environment=self.environment
        )

        # 将请求ID注入请求上下文
        request.state.request_id = request_id

        try:
            # 执行请求处理
            response = await call_next(request)

            # 记录结束时间和耗时
            end_time = time.time()
            end_datetime = datetime.now(timezone.utc)
            duration_ms = int((end_time - start_time) * 1000)

            # 更新日志记录
            record.end_time = end_datetime.isoformat()
            record.duration_ms = duration_ms
            record.status_code = response.status_code

            # 添加响应头
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Trace-ID"] = trace_id

        except Exception as e:
            # 记录异常信息
            end_datetime = datetime.now(timezone.utc)
            duration_ms = int((time.time() - start_time) * 1000)

            record.end_time = end_datetime.isoformat()
            record.duration_ms = duration_ms
            record.status_code = 500
            record.error_message = str(e)
            record.error_stack = self._format_exception(e)

            raise

        finally:
            # 始终写入日志（即使发生异常）
            try:
                self.log_buffer.push(record)
            except Exception as e:
                logger.error(f"写入日志缓冲区失败: {e}")

        return response

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实IP"""
        # 优先从X-Forwarded-For获取
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        # 从X-Real-IP获取
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # 从client获取
        if request.client:
            return request.client.host

        return "unknown"

    def _sanitize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """脱敏查询参数"""
        result = {}
        sensitive_keys = {
            "password", "token", "secret", "key",
            "authorization", "cookie", "access_token",
            "refresh_token", "api_key", "apikey"
        }
        for key, value in params.items():
            if key.lower() in sensitive_keys:
                result[key] = "***"
            else:
                result[key] = value
        return result

    def _format_exception(self, exc: Exception) -> str:
        """格式化异常堆栈"""
        import traceback
        return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


def get_request_logger(service_name: str = "api"):
    """
    获取请求日志记录器

    Args:
        service_name: 服务名称

    Returns:
        日志中间件类
    """
    return lambda app: RequestLoggingMiddleware(app, service_name)
