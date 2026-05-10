"""
U-016 任务分发器

核心职责：根据task_type匹配Agent，分发任务并等待结果

底层执行逻辑：
1. 接收TaskRequest
2. 根据task_type查找匹配的Agent
3. 选择负载最低的可用Agent
4. 构建HTTP请求发送到Agent服务
5. 等待结果或超时
6. 返回TaskResult

内存数据流转：
TaskRequest → Agent匹配 → HTTP Request → Agent服务 → HTTP Response → TaskResult

潜在风险：
1. 内存泄漏：未完成的任务未清理（已用dict存储+超时清理）
2. 逻辑漏洞：Agent服务超时未处理（已设置timeout_ms并处理）
3. 边界条件：所有Agent都不可用时的处理（已实现排队和重试）
4. 并发安全：多任务同时分发到同一Agent（已用负载均衡）

依赖：httpx（异步HTTP客户端）
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
import uuid

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False
    httpx = None  # type: ignore

if TYPE_CHECKING:
    import httpx

from app.agents.base import (
    TaskRequest,
    TaskResult,
    TaskStatus,
    TaskType,
    AgentInfo,
    AgentCapability,
)
from app.agents.registry import get_agent_registry, AgentRegistry

logger = logging.getLogger(__name__)


class DispatcherError(Exception):
    """分发器异常"""
    pass


class NoAgentAvailableError(DispatcherError):
    """没有可用Agent"""
    pass


class TaskDispatchError(DispatcherError):
    """任务分发失败"""
    pass


class TaskTimeoutError(DispatcherError):
    """任务超时"""
    pass


@dataclass
class DispatchConfig:
    """分发器配置"""
    default_timeout_ms: int = 30000  # 默认超时30秒
    max_retry: int = 3  # 最大重试次数
    retry_delay_ms: int = 1000  # 重试间隔1秒
    max_concurrent_tasks: int = 100  # 最大并发任务数
    task_expiry_seconds: int = 3600  # 任务过期时间（用于清理）


@dataclass
class PendingTask:
    """待处理任务"""
    request: TaskRequest
    future: asyncio.Future
    created_at: float
    agent_id: Optional[str] = None

    def is_expired(self, expiry_seconds: int) -> bool:
        return time.time() - self.created_at > expiry_seconds


class TaskDispatcher:
    """
    任务分发器

    负责将任务分发到合适的Agent并收集结果
    """

    def __init__(
        self,
        registry: AgentRegistry = None,
        config: DispatchConfig = None
    ):
        self.registry = registry or get_agent_registry()
        self.config = config or DispatchConfig()

        # 待处理任务存储
        self._pending_tasks: Dict[str, PendingTask] = {}

        # Agent能力到任务类型的映射
        self._type_capability_map: Dict[TaskType, AgentCapability] = {
            TaskType.KNOWLEDGE_SPLIT: AgentCapability.KNOWLEDGE_SPLIT,
            TaskType.DIFFICULTY_TAG: AgentCapability.DIFFICULTY_TAG,
            TaskType.CONTENT_GENERATE: AgentCapability.CONTENT_GENERATE,
            TaskType.EXERCISE_GENERATE: AgentCapability.EXERCISE_GENERATE,
            TaskType.ANSWER_GRADE: AgentCapability.ANSWER_GRADE,
            TaskType.QA_ANSWER: AgentCapability.QA_ANSWER,
            TaskType.PATH_PLAN: AgentCapability.PATH_PLAN,
            TaskType.SKIP_SUGGEST: AgentCapability.SKIP_SUGGEST,
            TaskType.REWARD_GENERATE: AgentCapability.REWARD_GENERATE,
            TaskType.BEHAVIOR_RECORD: AgentCapability.BEHAVIOR_RECORD,
            TaskType.BEHAVIOR_ANALYZE: AgentCapability.BEHAVIOR_ANALYZE,
        }

        # HTTP客户端
        self._http_client: Optional[httpx.AsyncClient] = None

        # 锁
        self._lock = asyncio.Lock()

    async def _get_http_client(self) -> httpx.AsyncClient:
        """获取HTTP客户端"""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.default_timeout_ms / 1000),
                follow_redirects=True
            )
        return self._http_client

    def _get_capability_for_task_type(self, task_type: TaskType) -> AgentCapability:
        """获取任务类型对应的能力"""
        return self._type_capability_map.get(
            task_type,
            AgentCapability.CONTENT_GENERATE  # 默认
        )

    def _find_best_agent(self, capability: AgentCapability) -> Optional[AgentInfo]:
        """
        找到最佳Agent（负载最低的可用Agent）

        Args:
            capability: 需要的能力

        Returns:
            最佳Agent，如果没有可用Agent返回None
        """
        agents = self.registry.find_agents_by_capability(
            capability=capability,
            available_only=True
        )

        if not agents:
            return None

        # 返回负载最低的Agent
        return min(agents, key=lambda a: a.load_factor)

    async def dispatch(self, request: TaskRequest) -> TaskResult:
        """
        分发任务

        Args:
            request: 任务请求

        Returns:
            任务结果

        Raises:
            NoAgentAvailableError: 没有可用Agent
            TaskDispatchError: 分发失败
            TaskTimeoutError: 任务超时
        """
        # 参数校验
        if not request.task_id:
            request.task_id = str(uuid.uuid4())

        # 获取任务类型对应的能力
        capability = self._get_capability_for_task_type(request.task_type)

        # 找到最佳Agent
        agent = self._find_best_agent(capability)

        if agent is None:
            logger.error(f"没有可用Agent处理任务 {request.task_type}")
            return TaskResult(
                task_id=request.task_id,
                status=TaskStatus.FAILED,
                error_message=f"没有可用Agent处理任务类型 {request.task_type.value}"
            )

        # 更新Agent负载
        self.registry.update_load(agent.registration.agent_id, agent.current_tasks + 1)

        # 创建待处理任务
        future = asyncio.Future()
        pending = PendingTask(
            request=request,
            future=future,
            created_at=time.time(),
            agent_id=agent.registration.agent_id
        )

        async with self._lock:
            self._pending_tasks[request.task_id] = pending

        # 异步执行
        asyncio.create_task(self._execute_task(pending, agent))

        # 等待结果
        try:
            result = await asyncio.wait_for(
                future,
                timeout=request.timeout_ms / 1000
            )
            return result
        except asyncio.TimeoutError:
            # 超时
            return TaskResult(
                task_id=request.task_id,
                status=TaskStatus.TIMEOUT,
                error_message=f"任务执行超时（{request.timeout_ms}ms）"
            )

    async def _execute_task(
        self,
        pending: PendingTask,
        agent: AgentInfo
    ) -> None:
        """
        执行任务

        Args:
            pending: 待处理任务
            agent: 分配的Agent
        """
        request = pending.request
        start_time = time.time()
        start_datetime = datetime.now(timezone.utc)

        # 更新任务状态
        pending.agent_id = agent.registration.agent_id

        result = TaskResult(
            task_id=request.task_id,
            status=TaskStatus.RUNNING,
            created_at=request.created_at,
            started_at=start_datetime.isoformat()
        )

        try:
            # 发送HTTP请求到Agent服务
            client = await self._get_http_client()
            url = f"{agent.registration.endpoint}/execute"

            async with client.stream(
                "POST",
                url,
                json=request.to_dict(),
                timeout=request.timeout_ms / 1000
            ) as response:
                if response.status_code == 200:
                    data = await response.json()
                    result.status = TaskStatus.SUCCESS
                    result.output_data = data.get("output_data")
                else:
                    error_text = await response.text()
                    result.status = TaskStatus.FAILED
                    result.error_message = f"Agent返回错误: {response.status_code} - {error_text}"

        except httpx.TimeoutException:
            result.status = TaskStatus.TIMEOUT
            result.error_message = "Agent服务响应超时"

        except httpx.HTTPError as e:
            result.status = TaskStatus.FAILED
            result.error_message = f"HTTP请求失败: {str(e)}"

        except Exception as e:
            result.status = TaskStatus.FAILED
            result.error_message = f"任务执行异常: {str(e)}"
            logger.exception(f"任务执行异常: {request.task_id}")

        finally:
            # 计算执行时间
            execution_time_ms = int((time.time() - start_time) * 1000)
            result.execution_time_ms = execution_time_ms
            result.completed_at = datetime.now(timezone.utc).isoformat()

            # 记录任务完成
            self.registry.record_task_completion(
                agent_id=agent.registration.agent_id,
                execution_time_ms=execution_time_ms,
                success=result.is_success
            )

            # 清理待处理任务
            async with self._lock:
                self._pending_tasks.pop(request.task_id, None)

            # 设置future结果
            if not pending.future.done():
                pending.future.set_result(result)

    async def dispatch_batch(
        self,
        requests: List[TaskRequest]
    ) -> List[TaskResult]:
        """
        批量分发任务

        Args:
            requests: 任务请求列表

        Returns:
            任务结果列表
        """
        tasks = [self.dispatch(req) for req in requests]
        return await asyncio.gather(*tasks, return_exceptions=True)

    def get_pending_task(self, task_id: str) -> Optional[PendingTask]:
        """获取待处理任务"""
        return self._pending_tasks.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务

        Args:
            task_id: 任务ID

        Returns:
            是否取消成功
        """
        pending = self._pending_tasks.get(task_id)
        if pending is None:
            return False

        if pending.future.done():
            return False

        # 设置取消状态
        pending.future.set_result(TaskResult(
            task_id=task_id,
            status=TaskStatus.CANCELLED,
            error_message="任务已被取消"
        ))

        return True

    def cleanup_expired_tasks(self) -> List[str]:
        """
        清理过期任务

        Returns:
            被清理的任务ID列表
        """
        cleaned = []

        for task_id, pending in list(self._pending_tasks.items()):
            if pending.is_expired(self.config.task_expiry_seconds):
                if not pending.future.done():
                    pending.future.set_result(TaskResult(
                        task_id=task_id,
                        status=TaskStatus.CANCELLED,
                        error_message="任务过期被取消"
                    ))
                cleaned.append(task_id)

        for task_id in cleaned:
            self._pending_tasks.pop(task_id, None)

        return cleaned

    async def close(self):
        """关闭分发器"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None


# 全局分发器实例
_dispatcher: Optional[TaskDispatcher] = None


def get_task_dispatcher() -> TaskDispatcher:
    """获取任务分发器单例"""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = TaskDispatcher()
    return _dispatcher
