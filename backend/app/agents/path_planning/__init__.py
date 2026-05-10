"""
M06 路径规划模块

核心职责：
- U-026 学习路径规划Agent：基于知识体系和用户进度生成个性化学习路径
- U-027 跳级建议Agent：根据用户学习表现判断是否可以跳过知识点

底层执行逻辑：
1. 路径规划：知识体系 → 依赖分析 → 拓扑排序 → 状态判定 → 有序路径
2. 跳级建议：学习数据 → 掌握度计算 → 阈值判断 → 风险检查 → 跳级建议

内存数据流转：
用户请求 → 数据分析 → 算法处理 → 结构化结果 → 返回

潜在风险：
1. 内存泄漏：大量知识点处理（已限制单次处理量）
2. 逻辑漏洞：循环依赖导致死锁（已实现环检测+破环）
3. 边界条件：数据不足/全部完成（已有兜底策略）
4. 质量风险：误判跳级导致知识断层（已设置保守阈值+核心知识点保护）

依赖：
- app.agents.base: TaskRequest, TaskType等基础类型
- app.agents.error_handler: 错误处理器
"""

# ============================================
# 数据模型导出
# ============================================

# U-026 路径规划相关模型
from app.agents.path_planning.path_planning import (
    NodeStatus,              # 路径节点状态枚举
    PathNodeType,            # 路径节点类型枚举
    PathNode,                # 学习路径节点
    LearningPath,            # 学习路径
    PathPlanningAgent,       # 路径规划Agent
    plan_learning_path,      # 便捷函数
)

# U-027 跳级建议相关模型
from app.agents.path_planning.skip_suggest import (
    SkipConfidence,          # 跳级置信度枚举
    SkipReason,              # 跳级原因枚举
    MasteryMetrics,          # 掌握度指标
    SkipSuggestion,          # 跳级建议
    SkipSuggestionReport,    # 跳级建议报告
    SkipSuggestAgent,        # 跳级建议Agent
    suggest_skip,            # 便捷函数
)

# ============================================
# 模块元数据
# ============================================

__all__ = [
    # U-026 路径规划
    "NodeStatus",
    "PathNodeType",
    "PathNode",
    "LearningPath",
    "PathPlanningAgent",
    "plan_learning_path",

    # U-027 跳级建议
    "SkipConfidence",
    "SkipReason",
    "MasteryMetrics",
    "SkipSuggestion",
    "SkipSuggestionReport",
    "SkipSuggestAgent",
    "suggest_skip",
]
