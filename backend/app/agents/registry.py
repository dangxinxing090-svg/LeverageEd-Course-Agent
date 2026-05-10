"""
U-015 Agent注册表

核心职责：管理所有Agent的注册信息、能力声明、健康状态

底层执行逻辑：
1. 接收Agent注册请求
2. 验证注册信息完整性
3. 存储到内存注册表（生产环境应持久化到Redis）
4. 按能力建立索引
5. 提供Agent查询和匹配接口

内存数据流转：
AgentRegistration → 验证 → 内存存储 → 索引更新 → 可查询状态

潜在风险：
1. 内存泄漏：注册表无限增长（已设置容量限制和过期机制）
2. 逻辑漏洞：重复注册未去重（已用agent_id唯一性约束）
3. 边界条件：Agent宕机后状态不一致（已用心跳检测机制）
4. 并发安全：多线程同时注册冲突（已用读写锁保护）

依赖：标准库threading、dataclasses
"""

import threading
import time
import logging
from typing import Dict, List, Optional, Set, Callable
from dataclasses import dataclass, field

from app.agents.base import (
    AgentRegistration,
    AgentInfo,
    AgentStatus,
    AgentCapability,
)

logger = logging.getLogger(__name__)


class AgentRegistryError(Exception):
    """Agent注册异常"""
    pass


class AgentNotFoundError(AgentRegistryError):
    """Agent未找到"""
    pass


class AgentAlreadyExistsError(AgentRegistryError):
    """Agent已存在"""
    pass


class CapabilityNotSupportedError(AgentRegistryError):
    """能力不支持"""
    pass


@dataclass
class RegistryConfig:
    """注册表配置"""
    max_agents: int = 100  # 最大Agent数量
    heartbeat_timeout_seconds: int = 60  # 心跳超时时间
    cleanup_interval_seconds: int = 300  # 清理间隔
    default_max_concurrent: int = 10  # 默认最大并发任务数


class AgentRegistry:
    """
    Agent注册表

    管理Agent的注册、查询、心跳和清理
    """

    def __init__(self, config: RegistryConfig = None):
        self.config = config or RegistryConfig()

        # 注册信息存储
        self._agents: Dict[str, AgentInfo] = {}
        self._lock = threading.RLock()  # 读写锁

        # 能力索引：capability -> set of agent_ids
        self._capability_index: Dict[AgentCapability, Set[str]] = {}

        # Agent类型索引：agent_type -> set of agent_ids
        self._type_index: Dict[str, Set[str]] = {}

        # 心跳记录：agent_id -> last_heartbeat_time
        self._heartbeats: Dict[str, float] = {}

        # 观察者回调
        self._observers: List[Callable] = []

    def register(self, registration: AgentRegistration) -> AgentInfo:
        """
        注册Agent

        Args:
            registration: Agent注册信息

        Returns:
            AgentInfo对象

        Raises:
            AgentAlreadyExistsError: Agent已存在
            AgentRegistryError: 注册失败
        """
        # 参数校验
        if not registration.agent_id:
            raise AgentRegistryError("agent_id不能为空")
        if not registration.agent_name:
            raise AgentRegistryError("agent_name不能为空")
        if not registration.capabilities:
            raise AgentRegistryError("capabilities不能为空")
        if not registration.endpoint:
            raise AgentRegistryError("endpoint不能为空")

        with self._lock:
            # 检查是否已存在
            if registration.agent_id in self._agents:
                raise AgentAlreadyExistsError(
                    f"Agent {registration.agent_id} 已存在，请先注销"
                )

            # 检查容量限制
            if len(self._agents) >= self.config.max_agents:
                raise AgentRegistryError(
                    f"注册表已满（{self.config.max_agents}），无法注册新Agent"
                )

            # 创建AgentInfo
            agent_info = AgentInfo(
                registration=registration,
                status=AgentStatus.HEALTHY,
                current_tasks=0,
                total_tasks_processed=0,
                avg_execution_time_ms=0,
                last_health_check=registration.registered_at
            )

            # 存储注册信息
            self._agents[registration.agent_id] = agent_info

            # 更新能力索引
            for capability in registration.capabilities:
                if capability not in self._capability_index:
                    self._capability_index[capability] = set()
                self._capability_index[capability].add(registration.agent_id)

            # 更新类型索引
            agent_type = registration.agent_type
            if agent_type not in self._type_index:
                self._type_index[agent_type] = set()
            self._type_index[agent_type].add(registration.agent_id)

            # 记录心跳
            self._heartbeats[registration.agent_id] = time.time()

            # 通知观察者
            self._notify_observers("register", registration.agent_id, agent_info)

            logger.info(f"Agent注册成功: {registration.agent_id} ({registration.agent_name})")

            return agent_info

    def unregister(self, agent_id: str) -> bool:
        """
        注销Agent

        Args:
            agent_id: Agent ID

        Returns:
            是否成功注销
        """
        with self._lock:
            if agent_id not in self._agents:
                return False

            agent_info = self._agents[agent_id]

            # 从存储中删除
            del self._agents[agent_id]

            # 更新能力索引
            for capability in agent_info.registration.capabilities:
                if capability in self._capability_index:
                    self._capability_index[capability].discard(agent_id)
                    if not self._capability_index[capability]:
                        del self._capability_index[capability]

            # 更新类型索引
            agent_type = agent_info.registration.agent_type
            if agent_type in self._type_index:
                self._type_index[agent_type].discard(agent_id)
                if not self._type_index[agent_type]:
                    del self._type_index[agent_type]

            # 删除心跳记录
            self._heartbeats.pop(agent_id, None)

            # 通知观察者
            self._notify_observers("unregister", agent_id, None)

            logger.info(f"Agent注销: {agent_id}")
            return True

    def get_agent(self, agent_id: str) -> AgentInfo:
        """
        获取Agent信息

        Args:
            agent_id: Agent ID

        Returns:
            AgentInfo对象

        Raises:
            AgentNotFoundError: Agent不存在
        """
        with self._lock:
            if agent_id not in self._agents:
                raise AgentNotFoundError(f"Agent {agent_id} 不存在")
            return self._agents[agent_id]

    def find_agents_by_capability(
        self,
        capability: AgentCapability,
        available_only: bool = True
    ) -> List[AgentInfo]:
        """
        根据能力查找Agent

        Args:
            capability: 能力类型
            available_only: 是否只返回可用Agent

        Returns:
            匹配的AgentInfo列表
        """
        with self._lock:
            agent_ids = self._capability_index.get(capability, set())

            agents = []
            for agent_id in agent_ids:
                agent_info = self._agents.get(agent_id)
                if agent_info:
                    if not available_only or agent_info.is_available:
                        agents.append(agent_info)

            # 按负载因子排序（负载低的优先）
            agents.sort(key=lambda a: a.load_factor)

            return agents

    def find_agent_by_type(
        self,
        agent_type: str,
        available_only: bool = True
    ) -> List[AgentInfo]:
        """
        根据类型查找Agent

        Args:
            agent_type: Agent类型
            available_only: 是否只返回可用Agent

        Returns:
            匹配的AgentInfo列表
        """
        with self._lock:
            agent_ids = self._type_index.get(agent_type, set())

            agents = []
            for agent_id in agent_ids:
                agent_info = self._agents.get(agent_id)
                if agent_info:
                    if not available_only or agent_info.is_available:
                        agents.append(agent_info)

            return agents

    def update_status(self, agent_id: str, status: AgentStatus) -> bool:
        """
        更新Agent状态

        Args:
            agent_id: Agent ID
            status: 新状态

        Returns:
            是否更新成功
        """
        with self._lock:
            if agent_id not in self._agents:
                return False

            self._agents[agent_id].status = status
            self._notify_observers("status_change", agent_id, status)
            return True

    def update_load(self, agent_id: str, current_tasks: int) -> bool:
        """
        更新Agent负载

        Args:
            agent_id: Agent ID
            current_tasks: 当前任务数

        Returns:
            是否更新成功
        """
        with self._lock:
            if agent_id not in self._agents:
                return False

            self._agents[agent_id].current_tasks = max(0, current_tasks)
            return True

    def record_task_completion(
        self,
        agent_id: str,
        execution_time_ms: int,
        success: bool
    ) -> bool:
        """
        记录任务完成

        Args:
            agent_id: Agent ID
            execution_time_ms: 执行耗时
            success: 是否成功

        Returns:
            是否记录成功
        """
        with self._lock:
            if agent_id not in self._agents:
                return False

            agent = self._agents[agent_id]

            # 更新任务计数
            agent.current_tasks = max(0, agent.current_tasks - 1)
            agent.total_tasks_processed += 1

            # 更新平均执行时间（滑动平均）
            n = agent.total_tasks_processed
            old_avg = agent.avg_execution_time_ms
            agent.avg_execution_time_ms = (old_avg * (n - 1) + execution_time_ms) / n

            # 如果失败，增加错误计数
            if not success:
                agent.error_count += 1

            # 更新状态
            if agent.error_count >= 5:
                agent.status = AgentStatus.UNHEALTHY

            return True

    def heartbeat(self, agent_id: str) -> bool:
        """
        Agent心跳

        Args:
            agent_id: Agent ID

        Returns:
            是否成功
        """
        with self._lock:
            if agent_id not in self._agents:
                return False

            self._heartbeats[agent_id] = time.time()

            # 如果之前是不健康状态，尝试恢复
            if self._agents[agent_id].status == AgentStatus.UNHEALTHY:
                if self._agents[agent_id].error_count < 3:
                    self._agents[agent_id].status = AgentStatus.HEALTHY

            return True

    def cleanup_stale_agents(self) -> List[str]:
        """
        清理超时的Agent

        Returns:
            被清理的Agent ID列表
        """
        current_time = time.time()
        cleaned = []

        with self._lock:
            stale_agent_ids = [
                agent_id
                for agent_id, last_heartbeat in self._heartbeats.items()
                if current_time - last_heartbeat > self.config.heartbeat_timeout_seconds
            ]

            for agent_id in stale_agent_ids:
                if agent_id in self._agents:
                    self._agents[agent_id].status = AgentStatus.OFFLINE
                    cleaned.append(agent_id)
                    logger.warning(f"Agent心跳超时: {agent_id}")

        return cleaned

    def list_all_agents(self) -> List[AgentInfo]:
        """列出所有Agent"""
        with self._lock:
            return list(self._agents.values())

    def list_capabilities(self) -> List[AgentCapability]:
        """列出所有已注册的能力"""
        with self._lock:
            return list(self._capability_index.keys())

    def add_observer(self, callback: Callable) -> None:
        """添加观察者"""
        self._observers.append(callback)

    def remove_observer(self, callback: Callable) -> None:
        """移除观察者"""
        self._observers.remove(callback)

    def _notify_observers(
        self,
        event: str,
        agent_id: str,
        data: any
    ) -> None:
        """通知观察者"""
        for observer in self._observers:
            try:
                observer(event, agent_id, data)
            except Exception as e:
                logger.error(f"观察者回调失败: {e}")

    @property
    def agent_count(self) -> int:
        """Agent总数"""
        with self._lock:
            return len(self._agents)

    @property
    def available_agent_count(self) -> int:
        """可用Agent数量"""
        with self._lock:
            return sum(1 for a in self._agents.values() if a.is_available)


# 全局注册表实例
_registry: Optional[AgentRegistry] = None


def get_agent_registry() -> AgentRegistry:
    """获取Agent注册表单例"""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry
