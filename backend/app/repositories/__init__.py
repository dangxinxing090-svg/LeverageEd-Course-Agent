"""
M09 数据存储层

核心职责：
- U-031 用户Repository：用户数据CRUD
- U-032 知识点Repository：知识点数据CRUD
- U-033 学习进度Repository：学习进度数据CRUD

底层执行逻辑：
1. 提供统一的数据访问接口
2. 内存存储实现（生产环境替换为数据库）
3. 支持索引和查询优化
4. 线程安全

内存数据流转：
模型对象 → 序列化 → 存储 → 反序列化 → 模型对象 → 返回

潜在风险：
1. 内存泄漏：大量数据（已实现分页+定期清理）
2. 并发问题：多线程写入（使用Lock保护）
3. 数据一致性：级联删除（已实现检查）
4. 边界条件：数据不存在（返回None或抛出异常）

依赖：无外部依赖
"""

# U-031 用户Repository
from app.repositories.user_repo import (
    User,
    UserRepository,
    get_user_repository,
)

# U-032 知识点Repository
from app.repositories.knowledge_repo import (
    KnowledgeComponent,
    KnowledgePoint,
    KnowledgeBlock,
    KnowledgeTopic,
    KnowledgeRepository,
    get_knowledge_repository,
)

# U-033 学习进度Repository
from app.repositories.progress_repo import (
    ProgressStatus,
    LearningProgress,
    DailyStudyRecord,
    UserLearningSummary,
    ProgressRepository,
    get_progress_repository,
)

__all__ = [
    # U-031
    "User",
    "UserRepository",
    "get_user_repository",
    # U-032
    "KnowledgeComponent",
    "KnowledgePoint",
    "KnowledgeBlock",
    "KnowledgeTopic",
    "KnowledgeRepository",
    "get_knowledge_repository",
    # U-033
    "ProgressStatus",
    "LearningProgress",
    "DailyStudyRecord",
    "UserLearningSummary",
    "ProgressRepository",
    "get_progress_repository",
]
