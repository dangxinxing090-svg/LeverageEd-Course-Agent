"""
M08 数据基础模块

核心职责：
- U-029 用户行为记录Agent：采集、清洗、存储用户行为事件
- U-030 用户行为分析Agent：多维度分析学习行为，BKT建模

底层执行逻辑：
1. 行为记录：原始事件 → 格式校验 → 数据清洗 → 去重 → 存储确认
2. 行为分析：行为事件 → 四维度聚合 → BKT建模 → 学习画像 → 报告

内存数据流转：
行为事件 → 校验清洗 → 存储确认 / 聚合分析 → BKT计算 → 结构化报告 → 返回

潜在风险：
1. 内存泄漏：高频事件堆积（已实现批量限制+缓存上限）
2. 逻辑漏洞：BKT参数不合理（已使用教育领域经验值）
3. 边界条件：空数据/超大数据（已有兜底+采样）
4. 质量风险：重复事件/分析偏差（已实现去重+多维度交叉验证）

依赖：
- app.agents.base: TaskRequest, TaskType等基础类型
- app.agents.error_handler: 错误处理器
"""

# ============================================
# U-029 行为记录相关模型
# ============================================

from app.agents.behavior.behavior_record import (
    BehaviorCategory,         # 行为大类枚举
    BehaviorAction,           # 行为动作枚举
    BehaviorEvent,            # 行为事件
    RecordResult,             # 记录结果
    BehaviorRecordAgent,      # 行为记录Agent
    record_behavior,          # 便捷函数
)

# ============================================
# U-030 行为分析相关模型
# ============================================

from app.agents.behavior.behavior_analysis import (
    ActivityLevel,            # 活跃度等级
    MasteryLevel,             # 掌握度等级
    TimeAnalysis,             # 时间维度分析
    ContentAnalysis,          # 内容维度分析
    ExerciseAnalysis,         # 练习维度分析
    PathAnalysis,             # 路径维度分析
    PointMastery,             # 知识点掌握度
    UserProfile,              # 学习画像
    AnalysisReport,           # 分析报告
    BehaviorAnalysisAgent,    # 行为分析Agent
    analyze_behavior,         # 便捷函数
    BKTParams,                # BKT模型参数
    bkt_update,               # BKT单步更新
    bkt_from_events,          # BKT从事件计算
)

# ============================================
# 模块元数据
# ============================================

__all__ = [
    # U-029 行为记录
    "BehaviorCategory",
    "BehaviorAction",
    "BehaviorEvent",
    "RecordResult",
    "BehaviorRecordAgent",
    "record_behavior",
    # U-030 行为分析
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
]
