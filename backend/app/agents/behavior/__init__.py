"""
M08 数据基础模块

核心职责：
- U-030 用户行为分析：多维度分析学习行为，BKT建模
- U-031 记忆压缩：归档旧行为数据，生成学习摘要

注意：原 BehaviorRecordAgent（U-029）已废弃删除，
行为记录功能由 behavior.py API endpoint 直接操作数据库实现。
"""

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
# U-031 记忆压缩相关模型
# ============================================

from app.agents.behavior.memory_compression import (
    DataTemperature,            # 数据温度枚举
    CompressionConfig,          # 压缩配置
    DailySummary,               # 每日行为摘要
    CompressionResult,          # 压缩结果
    MemoryCompressionAgent,     # 记忆压缩Agent
    compress_logs,              # 便捷函数
)

# ============================================
# 模块元数据
# ============================================

__all__ = [
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
    # U-031 记忆压缩
    "DataTemperature",
    "CompressionConfig",
    "DailySummary",
    "CompressionResult",
    "MemoryCompressionAgent",
    "compress_logs",
]
