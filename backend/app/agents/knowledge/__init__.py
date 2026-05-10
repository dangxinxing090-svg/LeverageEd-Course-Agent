"""
M04 知识处理模块

核心职责：
- U-020 知识拆分Agent：将学习主题拆解为三层知识体系
- U-021 重点难点标注Agent：为知识点标注难度和重要性

底层执行逻辑：
1. 知识拆分：接收主题 → LLM调用 → 三层知识体系 → 返回结构化结果
2. 难度标注：接收知识点 → LLM评估 → 难度/重要性标注 → 返回标注结果

内存数据流转：
用户输入 → Prompt构建 → LLM API → JSON解析 → 结构化数据 → 返回

潜在风险：
1. 内存泄漏：LLM响应上下文未及时释放（已使用上下文管理器）
2. 逻辑漏洞：输出格式不稳定（已有多次解析尝试+兜底机制）
3. 边界条件：空输入/超大批次处理（已做空列表校验+分批处理）
4. 质量风险：知识拆分/标注结果不符合预期（已实现完整性验证）

依赖：
- app.agents.base: TaskRequest, TaskType等基础类型
- app.agents.error_handler: 错误处理器
"""

# ============================================
# 数据模型导出
# ============================================

# 知识拆分相关模型
from app.agents.knowledge.knowledge_split import (
    KnowledgeComponent,      # 知识组件
    KnowledgePoint,          # 知识点
    KnowledgeBlock,          # 知识板块
    KnowledgeStructure,      # 完整知识体系
)

# 难度标注相关模型
from app.agents.knowledge.difficulty_tag import (
    DifficultyLevel,             # 难度级别枚举
    ImportanceLevel,             # 重要性级别枚举
    KnowledgePointAnnotation,    # 知识点标注
    DifficultyTagResult,         # 标注结果
)

# ============================================
# Agent导出
# ============================================

from app.agents.knowledge.knowledge_split import (
    KnowledgeSplitAgent,     # 知识拆分Agent
    split_knowledge,         # 快捷函数
)

from app.agents.knowledge.difficulty_tag import (
    DifficultyTagAgent,      # 难度标注Agent
    tag_difficulty,          # 快捷函数
)

# ============================================
# 模块元数据
# ============================================

__all__ = [
    # 数据模型 - 知识拆分
    "KnowledgeComponent",
    "KnowledgePoint",
    "KnowledgeBlock",
    "KnowledgeStructure",

    # 数据模型 - 难度标注
    "DifficultyLevel",
    "ImportanceLevel",
    "KnowledgePointAnnotation",
    "DifficultyTagResult",

    # Agent类
    "KnowledgeSplitAgent",
    "DifficultyTagAgent",

    # 快捷函数
    "split_knowledge",
    "tag_difficulty",
]
