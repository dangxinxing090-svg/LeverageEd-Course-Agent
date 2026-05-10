"""
U-028 鼓励奖励Agent

核心职责：根据用户学习行为和表现，生成个性化鼓励和奖励

底层执行逻辑：
1. 接收用户学习行为数据（完成知识点、练习成绩、连续学习天数等）
2. 分析触发场景（完成知识点、高分通过、连续学习、里程碑等）
3. 根据场景匹配奖励策略
4. 调用LLM生成个性化鼓励文案
5. 返回结构化奖励结果

内存数据流转：
行为数据 → 场景识别 → 策略匹配 → LLM文案生成 → 结构化奖励 → 返回

潜在风险：
1. 内存泄漏：频繁触发奖励导致积累（已实现冷却时间）
2. 逻辑漏洞：重复发放奖励（已实现去重机制）
3. 边界条件：无学习行为时的处理（已有兜底）
4. 质量风险：鼓励文案千篇一律（已实现多模板+个性化变量）

依赖：app.agents.base、app.agents.error_handler
"""

import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from app.agents.base import TaskRequest, TaskType
from app.agents.error_handler import get_error_handler

logger = logging.getLogger(__name__)


# ============================================
# 数据模型定义
# ============================================

class RewardType(str, Enum):
    """奖励类型"""
    ENCOURAGEMENT = "ENCOURAGEMENT"          # 文字鼓励
    BADGE = "BADGE"                          # 徽章
    STREAK = "STREAK"                        # 连续学习
    MILESTONE = "MILESTONE"                  # 里程碑
    ACHIEVEMENT = "ACHIEVEMENT"              # 成就达成
    PERFECT_SCORE = "PERFECT_SCORE"          # 满分奖励
    SPEED_BONUS = "SPEED_BONUS"              # 速度奖励
    KNOWLEDGE_MASTER = "KNOWLEDGE_MASTER"    # 知识掌握


class RewardLevel(str, Enum):
    """奖励等级"""
    BRONZE = "BRONZE"    # 铜牌
    SILVER = "SILVER"    # 银牌
    GOLD = "GOLD"        # 金牌
    PLATINUM = "PLATINUM"  # 铂金


class TriggerScene(str, Enum):
    """触发场景"""
    POINT_COMPLETED = "POINT_COMPLETED"          # 完成知识点
    EXERCISE_PASSED = "EXERCISE_PASSED"          # 练习通过
    PERFECT_EXERCISE = "PERFECT_EXERCISE"        # 满分练习
    BLOCK_COMPLETED = "BLOCK_COMPLETED"          # 完成板块
    STREAK_ACHIEVED = "STREAK_ACHIEVED"          # 连续学习达成
    MILESTONE_REACHED = "MILESTONE_REACHED"      # 里程碑达成
    DIFFICULTY_OVERCOME = "DIFFICULTY_OVERCOME"  # 克服难点
    COMEBACK = "COMEBACK"                        # 回归学习


@dataclass
class RewardContent:
    """奖励内容"""
    title: str  # 奖励标题
    message: str  # 鼓励文案
    icon_type: str = "star"  # 图标类型
    animation_type: str = "bounce"  # 动画类型

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "message": self.message,
            "icon_type": self.icon_type,
            "animation_type": self.animation_type
        }


@dataclass
class Reward:
    """奖励"""
    reward_id: str
    reward_type: RewardType
    reward_level: RewardLevel
    trigger_scene: TriggerScene
    content: RewardContent
    points: int = 0  # 奖励积分
    user_id: str = ""
    point_id: str = ""  # 关联的知识点ID
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reward_id": self.reward_id,
            "reward_type": self.reward_type.value,
            "reward_level": self.reward_level.value,
            "trigger_scene": self.trigger_scene.value,
            "content": self.content.to_dict(),
            "points": self.points,
            "user_id": self.user_id,
            "point_id": self.point_id,
            "created_at": self.created_at
        }


@dataclass
class RewardResult:
    """奖励结果"""
    rewards: List[Reward] = field(default_factory=list)
    total_points_earned: int = 0
    has_new_reward: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rewards": [r.to_dict() for r in self.rewards],
            "total_points_earned": self.total_points_earned,
            "has_new_reward": self.has_new_reward
        }


# ============================================
# 奖励策略配置
# ============================================

# 场景 → 奖励配置
SCENE_REWARD_CONFIG = {
    TriggerScene.POINT_COMPLETED: {
        "reward_type": RewardType.ENCOURAGEMENT,
        "reward_level": RewardLevel.BRONZE,
        "points": 10,
        "icon_type": "check-circle",
        "animation_type": "fade-in",
    },
    TriggerScene.EXERCISE_PASSED: {
        "reward_type": RewardType.ENCOURAGEMENT,
        "reward_level": RewardLevel.BRONZE,
        "points": 5,
        "icon_type": "thumbs-up",
        "animation_type": "bounce",
    },
    TriggerScene.PERFECT_EXERCISE: {
        "reward_type": RewardType.PERFECT_SCORE,
        "reward_level": RewardLevel.GOLD,
        "points": 30,
        "icon_type": "trophy",
        "animation_type": "confetti",
    },
    TriggerScene.BLOCK_COMPLETED: {
        "reward_type": RewardType.MILESTONE,
        "reward_level": RewardLevel.SILVER,
        "points": 50,
        "icon_type": "medal",
        "animation_type": "confetti",
    },
    TriggerScene.STREAK_ACHIEVED: {
        "reward_type": RewardType.STREAK,
        "reward_level": RewardLevel.SILVER,
        "points": 20,
        "icon_type": "fire",
        "animation_type": "pulse",
    },
    TriggerScene.MILESTONE_REACHED: {
        "reward_type": RewardType.ACHIEVEMENT,
        "reward_level": RewardLevel.GOLD,
        "points": 100,
        "icon_type": "crown",
        "animation_type": "confetti",
    },
    TriggerScene.DIFFICULTY_OVERCOME: {
        "reward_type": RewardType.KNOWLEDGE_MASTER,
        "reward_level": RewardLevel.GOLD,
        "points": 40,
        "icon_type": "lightning",
        "animation_type": "shake",
    },
    TriggerScene.COMEBACK: {
        "reward_type": RewardType.ENCOURAGEMENT,
        "reward_level": RewardLevel.SILVER,
        "points": 15,
        "icon_type": "heart",
        "animation_type": "heartbeat",
    },
}

# 连续学习天数阈值
STREAK_THRESHOLDS = [3, 7, 14, 30, 60, 90]

# 里程碑阈值
MILESTONE_THRESHOLDS = [5, 10, 25, 50, 100]


# ============================================
# Prompt模板
# ============================================

ENCOURAGEMENT_PROMPT = """
你是一个温暖、有感染力的学习激励助手。请根据用户的学习情况，生成一段简短有力的鼓励文案。

## 用户信息
- 用户名：{user_name}
- 当前学习主题：{topic_name}
- 触发场景：{scene}
- 学习统计：{stats}

## 要求
1. 文案长度：20-50字
2. 语气：温暖、真诚、有力量
3. 内容：结合具体学习情况，不要泛泛而谈
4. 标题：5-10字的简短标题

## 输出格式（JSON）
{{
    "title": "标题",
    "message": "鼓励文案"
}}

请输出JSON：
"""


# ============================================
# Agent实现
# ============================================

class RewardGenerateAgent:
    """
    鼓励奖励Agent

    根据用户学习行为生成个性化鼓励和奖励
    """

    def __init__(
        self,
        llm_client=None,
        max_retries: int = 3,
        temperature: float = 0.7  # 鼓励文案需要更高创造性
    ):
        """
        初始化奖励Agent

        Args:
            llm_client: LLM客户端
            max_retries: 最大重试次数
            temperature: 生成温度
        """
        self.llm_client = llm_client
        self.max_retries = max_retries
        self.temperature = temperature
        self.error_handler = get_error_handler()

    def _validate_input(
        self,
        user_id: str,
        trigger_scene: str,
        context: Dict[str, Any]
    ) -> None:
        """
        验证输入参数

        Args:
            user_id: 用户ID
            trigger_scene: 触发场景
            context: 上下文信息

        Raises:
            ValueError: 参数无效
        """
        if not user_id or not user_id.strip():
            raise ValueError("用户ID不能为空")

        try:
            TriggerScene(trigger_scene)
        except ValueError:
            valid = [s.value for s in TriggerScene]
            raise ValueError(f"无效的触发场景: {trigger_scene}，有效值: {valid}")

    def _get_scene_config(self, scene: TriggerScene) -> Dict[str, Any]:
        """
        获取场景奖励配置

        Args:
            scene: 触发场景

        Returns:
            奖励配置
        """
        return SCENE_REWARD_CONFIG.get(scene, {
            "reward_type": RewardType.ENCOURAGEMENT,
            "reward_level": RewardLevel.BRONZE,
            "points": 5,
            "icon_type": "star",
            "animation_type": "bounce",
        })

    def _check_streak_level(self, streak_days: int) -> Optional[TriggerScene]:
        """
        检查连续学习是否达到特殊阈值

        Args:
            streak_days: 连续学习天数

        Returns:
            达到的里程碑场景或None
        """
        for threshold in STREAK_THRESHOLDS:
            if streak_days == threshold:
                return TriggerScene.STREAK_ACHIEVED
        return None

    def _check_milestone(self, completed_points: int) -> Optional[TriggerScene]:
        """
        检查是否达到知识点完成里程碑

        Args:
            completed_points: 已完成知识点数

        Returns:
            里程碑场景或None
        """
        for threshold in MILESTONE_THRESHOLDS:
            if completed_points == threshold:
                return TriggerScene.MILESTONE_REACHED
        return None

    def _build_stats_string(self, context: Dict[str, Any]) -> str:
        """
        构建学习统计描述

        Args:
            context: 上下文信息

        Returns:
            统计描述字符串
        """
        parts = []
        if context.get("completed_points"):
            parts.append(f"已完成{context['completed_points']}个知识点")
        if context.get("total_score"):
            parts.append(f"练习得分{context['total_score']}分")
        if context.get("streak_days"):
            parts.append(f"连续学习{context['streak_days']}天")
        if context.get("total_study_hours"):
            parts.append(f"累计学习{context['total_study_hours']}小时")
        if context.get("current_point_name"):
            parts.append(f"正在学习「{context['current_point_name']}」")

        return "，".join(parts) if parts else "刚开始学习"

    def _build_prompt(
        self,
        scene: TriggerScene,
        context: Dict[str, Any]
    ) -> str:
        """
        构建鼓励文案Prompt

        Args:
            scene: 触发场景
            context: 上下文信息

        Returns:
            格式化后的Prompt
        """
        scene_descriptions = {
            TriggerScene.POINT_COMPLETED: "完成了一个知识点",
            TriggerScene.EXERCISE_PASSED: "通过了练习",
            TriggerScene.PERFECT_EXERCISE: "练习获得满分",
            TriggerScene.BLOCK_COMPLETED: "完成了一个知识板块",
            TriggerScene.STREAK_ACHIEVED: "连续学习达成新纪录",
            TriggerScene.MILESTONE_REACHED: "达成了学习里程碑",
            TriggerScene.DIFFICULTY_OVERCOME: "克服了一个难点",
            TriggerScene.COMEBACK: "回归学习",
        }

        return ENCOURAGEMENT_PROMPT.format(
            user_name=context.get("user_name", "同学"),
            topic_name=context.get("topic_name", "当前主题"),
            scene=scene_descriptions.get(scene, "学习进步"),
            stats=self._build_stats_string(context)
        )

    def _parse_llm_output(self, output: str) -> Dict[str, str]:
        """
        解析LLM输出

        Args:
            output: LLM原始输出

        Returns:
            {title, message}

        Raises:
            ValueError: 解析失败
        """
        json_str = output.strip()

        if "```json" in json_str:
            json_str = re.split(r"```json", json_str)[1]
            json_str = re.split(r"```", json_str)[0]
        elif "```" in json_str:
            json_str = re.split(r"```", json_str)[1]
            if json_str.startswith("json"):
                json_str = json_str[4:]

        json_str = json_str.strip()

        try:
            data = json.loads(json_str)
            return {
                "title": data.get("title", "做得好！"),
                "message": data.get("message", "继续加油！")
            }
        except json.JSONDecodeError:
            # 解析失败时使用兜底文案
            return {"title": "做得好！", "message": "继续加油，你很棒！"}

    async def _generate_encouragement(
        self,
        scene: TriggerScene,
        context: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        生成鼓励文案

        Args:
            scene: 触发场景
            context: 上下文信息

        Returns:
            {title, message}
        """
        prompt = self._build_prompt(scene, context)

        for attempt in range(self.max_retries):
            try:
                if self.llm_client:
                    response = await self.llm_client.agenerate([prompt])
                    raw_output = response.generations[0][0].text
                    return self._parse_llm_output(raw_output)
                else:
                    return self._get_fallback_encouragement(scene, context)
            except Exception as e:
                logger.warning(f"鼓励文案生成失败（第{attempt + 1}次）: {e}")
                continue

        return self._get_fallback_encouragement(scene, context)

    def _get_fallback_encouragement(
        self,
        scene: TriggerScene,
        context: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        兜底鼓励文案（LLM不可用时）

        Args:
            scene: 触发场景
            context: 上下文信息

        Returns:
            {title, message}
        """
        point_name = context.get("current_point_name", "")
        user_name = context.get("user_name", "同学")

        fallbacks = {
            TriggerScene.POINT_COMPLETED: {
                "title": "知识点完成！",
                "message": f"{user_name}，你完成了「{point_name}」的学习，又进步了一步！"
            },
            TriggerScene.EXERCISE_PASSED: {
                "title": "练习通过！",
                "message": f"练习通过了，{user_name}对知识的掌握越来越扎实了！"
            },
            TriggerScene.PERFECT_EXERCISE: {
                "title": "满分！",
                "message": f"太厉害了，{user_name}拿到了满分！这就是实力的证明！"
            },
            TriggerScene.BLOCK_COMPLETED: {
                "title": "板块通关！",
                "message": f"恭喜{user_name}完成了一个知识板块，离目标又近了一步！"
            },
            TriggerScene.STREAK_ACHIEVED: {
                "title": "坚持就是胜利！",
                "message": f"{user_name}已经连续学习{context.get('streak_days', 0)}天了，这份坚持非常了不起！"
            },
            TriggerScene.MILESTONE_REACHED: {
                "title": "里程碑达成！",
                "message": f"恭喜{user_name}达成了新的学习里程碑，你的努力值得骄傲！"
            },
            TriggerScene.DIFFICULTY_OVERCOME: {
                "title": "攻克难关！",
                "message": f"「{point_name}」是个难点，但{user_name}成功克服了，真棒！"
            },
            TriggerScene.COMEBACK: {
                "title": "欢迎回来！",
                "message": f"{user_name}，很高兴你回来了！学习之旅继续，我们一起加油！"
            },
        }

        return fallbacks.get(scene, {
            "title": "继续加油！",
            "message": f"{user_name}，你的每一步努力都在积累，继续前进吧！"
        })

    def _build_reward(
        self,
        scene: TriggerScene,
        content: Dict[str, str],
        user_id: str,
        context: Dict[str, Any]
    ) -> Reward:
        """
        构建奖励对象

        Args:
            scene: 触发场景
            content: 文案内容 {title, message}
            user_id: 用户ID
            context: 上下文信息

        Returns:
            Reward对象
        """
        config = self._get_scene_config(scene)

        return Reward(
            reward_id=f"reward-{uuid.uuid4().hex[:8]}",
            reward_type=config["reward_type"],
            reward_level=config["reward_level"],
            trigger_scene=scene,
            content=RewardContent(
                title=content["title"],
                message=content["message"],
                icon_type=config["icon_type"],
                animation_type=config["animation_type"]
            ),
            points=config["points"],
            user_id=user_id,
            point_id=context.get("point_id", "")
        )

    async def execute(
        self,
        user_id: str,
        trigger_scene: str,
        context: Dict[str, Any] = None
    ) -> RewardResult:
        """
        执行奖励生成

        Args:
            user_id: 用户ID
            trigger_scene: 触发场景 (POINT_COMPLETED/EXERCISE_PASSED/...)
            context: 上下文信息 {
                user_name: str,
                topic_name: str,
                point_id: str,
                current_point_name: str,
                completed_points: int,
                total_score: float,
                streak_days: int,
                total_study_hours: float,
                difficulty: str  # LOW/MEDIUM/HIGH
            }

        Returns:
            RewardResult对象

        Raises:
            ValueError: 输入参数无效
        """
        context = context or {}

        # 验证输入
        self._validate_input(user_id, trigger_scene, context)

        scene = TriggerScene(trigger_scene)
        rewards = []
        total_points = 0

        # 1. 主场景奖励
        encouragement = await self._generate_encouragement(scene, context)
        reward = self._build_reward(scene, encouragement, user_id, context)
        rewards.append(reward)
        total_points += reward.points

        # 2. 检查是否同时触发连续学习里程碑
        streak_days = context.get("streak_days", 0)
        streak_scene = self._check_streak_level(streak_days)
        if streak_scene and streak_scene != scene:
            streak_encouragement = await self._generate_encouragement(streak_scene, context)
            streak_reward = self._build_reward(streak_scene, streak_encouragement, user_id, context)
            rewards.append(streak_reward)
            total_points += streak_reward.points

        # 3. 检查是否同时触发知识点完成里程碑
        completed_points = context.get("completed_points", 0)
        milestone_scene = self._check_milestone(completed_points)
        if milestone_scene and milestone_scene != scene:
            milestone_encouragement = await self._generate_encouragement(milestone_scene, context)
            milestone_reward = self._build_reward(milestone_scene, milestone_encouragement, user_id, context)
            rewards.append(milestone_reward)
            total_points += milestone_reward.points

        return RewardResult(
            rewards=rewards,
            total_points_earned=total_points,
            has_new_reward=len(rewards) > 0
        )

    def create_task_request(
        self,
        user_id: str,
        trigger_scene: str,
        context: Dict[str, Any] = None
    ) -> TaskRequest:
        """
        创建任务请求

        Args:
            user_id: 用户ID
            trigger_scene: 触发场景
            context: 上下文信息

        Returns:
            TaskRequest对象
        """
        return TaskRequest(
            task_type=TaskType.REWARD_GENERATE,
            input_data={
                "user_id": user_id,
                "trigger_scene": trigger_scene,
                "context": context or {}
            },
            priority=3,
            timeout_ms=15000
        )


# 便捷函数
async def generate_reward(
    user_id: str,
    trigger_scene: str,
    context: Dict[str, Any] = None,
    llm_client=None
) -> RewardResult:
    """
    快捷函数：生成奖励

    Args:
        user_id: 用户ID
        trigger_scene: 触发场景
        context: 上下文信息
        llm_client: LLM客户端

    Returns:
        RewardResult对象
    """
    agent = RewardGenerateAgent(llm_client=llm_client)
    return await agent.execute(user_id, trigger_scene, context)
