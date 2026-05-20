"""
Agent调度中心模块

包含：
- U-015 Agent注册表 (registry.py)
- U-016 任务分发器 (dispatcher.py)
- U-017 依赖解析器 (dependency.py)
- U-018 结果聚合器 (aggregator.py)
- U-019 异常处理器 (error_handler.py)

当前在运行时使用的Agent：
- UnifiedTeachingAgent：统一教学Agent（知识讲解、出题、批改、问答）
- CustomExerciseAgent：定制综合练习Agent
- BehaviorAnalysisAgent：用户行为分析Agent
- MemoryCompressionAgent：记忆压缩Agent
"""

# 基础模型
from .base import (
    TaskType,
    TaskStatus,
    AgentCapability,
    TaskRequest,
    TaskResult,
    AgentRegistration,
    AgentStatus,
    AgentInfo,
)

# U-015 Agent注册表
from .registry import (
    AgentRegistry,
    AgentRegistryError,
    AgentNotFoundError,
    AgentAlreadyExistsError,
    CapabilityNotSupportedError,
    get_agent_registry,
)

# U-016 任务分发器
from .dispatcher import (
    TaskDispatcher,
    DispatcherError,
    NoAgentAvailableError,
    TaskDispatchError,
    TaskTimeoutError,
    get_task_dispatcher,
)

# U-017 依赖解析器
from .dependency import (
    DependencyResolver,
    DependencyError,
    CircularDependencyError,
    MissingDependencyError,
    resolve_dependencies,
)

# U-018 结果聚合器
from .aggregator import (
    AggregationStrategy,
    AggregationResult,
    ResultAggregator,
    SequentialAggregator,
    TreeAggregator,
    aggregate_results,
    aggregate_sequential_results,
)

# U-019 异常处理器
from .error_handler import (
    ErrorType,
    RetryStrategy,
    FallbackStrategy,
    RetryConfig,
    FallbackConfig,
    ErrorRecord,
    ErrorMetrics,
    ErrorClassifier,
    RetryPolicy,
    TaskErrorHandler,
    with_error_handling,
    get_error_handler,
)

# M08 数据基础模块（保留：行为分析 + 记忆压缩）
from .behavior import (
    ActivityLevel,
    MasteryLevel,
    TimeAnalysis,
    ContentAnalysis,
    ExerciseAnalysis,
    PathAnalysis,
    PointMastery,
    UserProfile,
    AnalysisReport,
    BehaviorAnalysisAgent,
    analyze_behavior,
    BKTParams,
    bkt_update,
    bkt_from_events,
    DataTemperature,
    CompressionConfig,
    DailySummary,
    CompressionResult,
    MemoryCompressionAgent,
    compress_logs,
)

# LLM Provider 多模型支持
from .llm_providers import (
    # 基础接口
    LLMProvider,
    LLMResponse,
    LLMMessage,
    ProviderConfig,
    ProviderType,
    ModelCapability,
    # 配置管理
    LLMConfigManager,
    get_llm_config,
    load_provider_config,
    # 工厂
    ProviderFactory,
    get_provider,
    create_provider,
    list_available_providers,
    # Provider实现
    OpenAIProvider,
    ZhipuProvider,
    KimiProvider,
    QwenProvider,
    DoubaoProvider,
    # Agent适配器
    AgentLLMClient,
    create_llm_client,
    get_default_llm_client,
)

__all__ = [
    # Base
    "TaskType",
    "TaskStatus",
    "AgentCapability",
    "TaskRequest",
    "TaskResult",
    "AgentRegistration",
    "AgentStatus",
    "AgentInfo",
    # Registry
    "AgentRegistry",
    "AgentRegistryError",
    "AgentNotFoundError",
    "AgentAlreadyExistsError",
    "CapabilityNotSupportedError",
    "get_agent_registry",
    # Dispatcher
    "TaskDispatcher",
    "DispatcherError",
    "NoAgentAvailableError",
    "TaskDispatchError",
    "TaskTimeoutError",
    "get_task_dispatcher",
    # Dependency
    "DependencyResolver",
    "DependencyError",
    "CircularDependencyError",
    "MissingDependencyError",
    "resolve_dependencies",
    # Aggregator
    "AggregationStrategy",
    "AggregationResult",
    "ResultAggregator",
    "SequentialAggregator",
    "TreeAggregator",
    "aggregate_results",
    "aggregate_sequential_results",
    # Error Handler
    "ErrorType",
    "RetryStrategy",
    "FallbackStrategy",
    "RetryConfig",
    "FallbackConfig",
    "ErrorRecord",
    "ErrorMetrics",
    "ErrorClassifier",
    "RetryPolicy",
    "TaskErrorHandler",
    "with_error_handling",
    "get_error_handler",
    # M08 Behavior
    "ActivityLevel",
    "MasteryLevel",
    "TimeAnalysis",
    "ContentAnalysis",
    "ExerciseAnalysis",
    "PathAnalysis",
    "PointMastery",
    "UserProfile",
    "AnalysisReport",
    "BehaviorAnalysisAgent",
    "analyze_behavior",
    "BKTParams",
    "bkt_update",
    "bkt_from_events",
    "DataTemperature",
    "CompressionConfig",
    "DailySummary",
    "CompressionResult",
    "MemoryCompressionAgent",
    "compress_logs",
    # LLM Provider
    "LLMProvider",
    "LLMResponse",
    "LLMMessage",
    "ProviderConfig",
    "ProviderType",
    "ModelCapability",
    "LLMConfigManager",
    "get_llm_config",
    "load_provider_config",
    "ProviderFactory",
    "get_provider",
    "create_provider",
    "list_available_providers",
    "OpenAIProvider",
    "ZhipuProvider",
    "KimiProvider",
    "QwenProvider",
    "DoubaoProvider",
    "AgentLLMClient",
    "create_llm_client",
    "get_default_llm_client",
]
