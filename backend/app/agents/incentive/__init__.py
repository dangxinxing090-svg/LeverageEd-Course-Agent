"""
M07 激励系统模块

核心职责：
- U-028 鼓励奖励Agent：根据用户学习行为生成个性化鼓励和奖励

底层执行逻辑：
1. 接收触发场景和用户上下文
2. 匹配奖励策略（场景→类型→等级→积分）
3. LLM生成个性化鼓励文案（含兜底模板）
4. 检查是否同时触发连续学习/里程碑
5. 返回结构化奖励结果

内存数据流转：
触发场景+上下文 → 策略匹配 → LLM文案 → 奖励构建 → 返回

潜在风险：
1. 内存泄漏：频繁触发积累（已由调用方控制冷却时间）
2. 逻辑漏洞：重复发放（已由调用方去重，本Agent专注生成）
3. 边界条件：LLM不可用（已有完整兜底模板）
4. 质量风险：文案千篇一律（多场景模板+个性化变量）

依赖：
- app.agents.base: TaskRequest, TaskType等基础类型
- app.agents.error_handler: 错误处理器
"""

# ============================================
# 数据模型导出
# ============================================

from app.agents.incentive.reward_generate import (
    RewardType,              # 奖励类型枚举
    RewardLevel,             # 奖励等级枚举
    TriggerScene,            # 触发场景枚举
    RewardContent,           # 奖励内容
    Reward,                  # 奖励
    RewardResult,            # 奖励结果
    RewardGenerateAgent,     # 奖励生成Agent
    generate_reward,         # 便捷函数
)

# ============================================
# 模块元数据
# ============================================

__all__ = [
    "RewardType",
    "RewardLevel",
    "TriggerScene",
    "RewardContent",
    "Reward",
    "RewardResult",
    "RewardGenerateAgent",
    "generate_reward",
]
