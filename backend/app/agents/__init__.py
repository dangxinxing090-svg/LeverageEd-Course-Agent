"""
Agent调度中心模块

包含：
- U-015 Agent注册表 (registry.py)
- U-016 任务分发器 (dispatcher.py)
- U-017 依赖解析器 (dependency.py)
- U-018 结果聚合器 (aggregator.py)
- U-019 异常处理器 (error_handler.py)
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

# M04 知识处理模块
from .knowledge import (
    # 知识拆分
    KnowledgeSplitAgent,
    split_knowledge,
    KnowledgeComponent,
    KnowledgePoint,
    KnowledgeBlock,
    KnowledgeStructure,
    # 难度标注
    DifficultyTagAgent,
    tag_difficulty,
    DifficultyLevel,
    ImportanceLevel,
    KnowledgePointAnnotation,
    DifficultyTagResult,
)

# M05 学习支持模块
from .learning import (
    # U-022 知识讲解
    ExplanationSection,
    ExplanationContent,
    ContentExplainAgent,
    explain_content,
    # U-023 练习题生成
    QuestionType,
    DifficultyLevel as ExerciseDifficultyLevel,
    QuestionOption,
    Question,
    ExerciseSet,
    ExerciseGenerateAgent,
    generate_exercise,
    # U-024 题目批改
    GradeQuestionType,
    GradeResult,
    QuestionGrade,
    GradeReport,
    AnswerGradeAgent,
    grade_answers,
    # U-025 答疑问答
    QAQuestionType,
    AnswerQuality,
    RelatedKnowledge,
    AnswerSection,
    QAAnswer,
    QAAnswerAgent,
    answer_question,
)

# M06 路径规划模块
from .path_planning import (
    # U-026 路径规划
    NodeStatus,
    PathNodeType,
    PathNode,
    LearningPath,
    PathPlanningAgent,
    plan_learning_path,
    # U-027 跳级建议
    SkipConfidence,
    SkipReason,
    MasteryMetrics,
    SkipSuggestion,
    SkipSuggestionReport,
    SkipSuggestAgent,
    suggest_skip,
)

# M07 激励系统模块
from .incentive import (
    RewardType,
    RewardLevel,
    TriggerScene,
    RewardContent,
    Reward,
    RewardResult,
    RewardGenerateAgent,
    generate_reward,
)

# M08 数据基础模块
from .behavior import (
    # U-029 行为记录
    BehaviorCategory,
    BehaviorAction,
    BehaviorEvent,
    RecordResult,
    BehaviorRecordAgent,
    record_behavior,
    # U-030 行为分析
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
    # M04 Knowledge
    "KnowledgeSplitAgent",
    "split_knowledge",
    "KnowledgeComponent",
    "KnowledgePoint",
    "KnowledgeBlock",
    "KnowledgeStructure",
    "DifficultyTagAgent",
    "tag_difficulty",
    "DifficultyLevel",
    "ImportanceLevel",
    "KnowledgePointAnnotation",
    "DifficultyTagResult",
    # M05 Learning
    "ExplanationSection",
    "ExplanationContent",
    "ContentExplainAgent",
    "explain_content",
    "QuestionType",
    "ExerciseDifficultyLevel",
    "QuestionOption",
    "Question",
    "ExerciseSet",
    "ExerciseGenerateAgent",
    "generate_exercise",
    "GradeQuestionType",
    "GradeResult",
    "QuestionGrade",
    "GradeReport",
    "AnswerGradeAgent",
    "grade_answers",
    "QAQuestionType",
    "AnswerQuality",
    "RelatedKnowledge",
    "AnswerSection",
    "QAAnswer",
    "QAAnswerAgent",
    "answer_question",
    # M06 Path Planning
    "NodeStatus",
    "PathNodeType",
    "PathNode",
    "LearningPath",
    "PathPlanningAgent",
    "plan_learning_path",
    "SkipConfidence",
    "SkipReason",
    "MasteryMetrics",
    "SkipSuggestion",
    "SkipSuggestionReport",
    "SkipSuggestAgent",
    "suggest_skip",
    # M07 Incentive
    "RewardType",
    "RewardLevel",
    "TriggerScene",
    "RewardContent",
    "Reward",
    "RewardResult",
    "RewardGenerateAgent",
    "generate_reward",
    # M08 Behavior
    "BehaviorCategory",
    "BehaviorAction",
    "BehaviorEvent",
    "RecordResult",
    "BehaviorRecordAgent",
    "record_behavior",
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
