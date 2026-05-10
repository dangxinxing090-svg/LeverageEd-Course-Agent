"""
Agent基类和任务模型定义

定义所有Agent共享的数据结构和枚举
"""

from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
import uuid


class TaskType(str, Enum):
    """任务类型枚举"""
    # 知识处理
    KNOWLEDGE_SPLIT = "KNOWLEDGE_SPLIT"        # 知识拆分
    DIFFICULTY_TAG = "DIFFICULTY_TAG"          # 重点难点标注

    # 学习支持
    CONTENT_GENERATE = "CONTENT_GENERATE"      # 知识讲解
    EXERCISE_GENERATE = "EXERCISE_GENERATE"    # 练习题生成
    ANSWER_GRADE = "ANSWER_GRADE"              # 题目批改
    QA_ANSWER = "QA_ANSWER"                    # 答疑问答

    # 路径规划
    PATH_PLAN = "PATH_PLAN"                    # 路径规划
    SKIP_SUGGEST = "SKIP_SUGGEST"              # 跳级建议

    # 激励系统
    REWARD_GENERATE = "REWARD_GENERATE"        # 鼓励奖励

    # 数据基础
    BEHAVIOR_RECORD = "BEHAVIOR_RECORD"        # 行为记录
    BEHAVIOR_ANALYZE = "BEHAVIOR_ANALYZE"      # 行为分析


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "PENDING"        # 待执行
    RUNNING = "RUNNING"        # 执行中
    SUCCESS = "SUCCESS"        # 成功
    FAILED = "FAILED"          # 失败
    TIMEOUT = "TIMEOUT"        # 超时
    CANCELLED = "CANCELLED"    # 已取消


class AgentCapability(str, Enum):
    """Agent能力枚举"""
    KNOWLEDGE_SPLIT = "KNOWLEDGE_SPLIT"
    DIFFICULTY_TAG = "DIFFICULTY_TAG"
    CONTENT_GENERATE = "CONTENT_GENERATE"
    EXERCISE_GENERATE = "EXERCISE_GENERATE"
    ANSWER_GRADE = "ANSWER_GRADE"
    QA_ANSWER = "QA_ANSWER"
    PATH_PLAN = "PATH_PLAN"
    SKIP_SUGGEST = "SKIP_SUGGEST"
    REWARD_GENERATE = "REWARD_GENERATE"
    BEHAVIOR_RECORD = "BEHAVIOR_RECORD"
    BEHAVIOR_ANALYZE = "BEHAVIOR_ANALYZE"


@dataclass
class TaskRequest:
    """
    任务请求

    用户提交给Agent调度中心的任务
    """
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_type: TaskType = TaskType.CONTENT_GENERATE
    input_data: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5  # 1-10，数字越大优先级越高
    dependencies: List[str] = field(default_factory=list)  # 依赖的任务ID列表
    timeout_ms: int = 30000  # 默认30秒超时
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "input_data": self.input_data,
            "priority": self.priority,
            "dependencies": self.dependencies,
            "timeout_ms": self.timeout_ms,
            "created_at": self.created_at
        }


@dataclass
class TaskResult:
    """
    任务结果

    Agent执行完成后的返回结果
    """
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    execution_time_ms: int = 0
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "output_data": self.output_data,
            "error_message": self.error_message,
            "execution_time_ms": self.execution_time_ms,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at
        }

    @property
    def is_success(self) -> bool:
        return self.status == TaskStatus.SUCCESS

    @property
    def is_failed(self) -> bool:
        return self.status in (TaskStatus.FAILED, TaskStatus.TIMEOUT)


@dataclass
class AgentRegistration:
    """
    Agent注册信息

    Agent向调度中心注册时提供的信息
    """
    agent_id: str
    agent_name: str
    agent_type: str  # 如 "KnowledgeSplitAgent"
    capabilities: List[AgentCapability]
    endpoint: str  # Agent服务的URL
    health_check_url: Optional[str] = None
    max_concurrent_tasks: int = 10
    description: str = ""
    version: str = "1.0.0"
    registered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "agent_type": self.agent_type,
            "capabilities": [c.value for c in self.capabilities],
            "endpoint": self.endpoint,
            "health_check_url": self.health_check_url,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "description": self.description,
            "version": self.version,
            "registered_at": self.registered_at
        }


class AgentStatus(str, Enum):
    """Agent状态"""
    HEALTHY = "HEALTHY"      # 健康
    BUSY = "BUSY"            # 忙碌
    UNHEALTHY = "UNHEALTHY" # 不健康
    OFFLINE = "OFFLINE"      # 离线


@dataclass
class AgentInfo:
    """
    Agent运行时信息

    包含注册信息和运行时状态
    """
    registration: AgentRegistration
    status: AgentStatus = AgentStatus.HEALTHY
    current_tasks: int = 0
    total_tasks_processed: int = 0
    avg_execution_time_ms: float = 0
    last_health_check: Optional[str] = None
    error_count: int = 0

    @property
    def is_available(self) -> bool:
        """Agent是否可用"""
        return (
            self.status in (AgentStatus.HEALTHY, AgentStatus.BUSY)
            and self.current_tasks < self.registration.max_concurrent_tasks
        )

    @property
    def load_factor(self) -> float:
        """负载因子"""
        if self.registration.max_concurrent_tasks == 0:
            return 1.0
        return self.current_tasks / self.registration.max_concurrent_tasks
