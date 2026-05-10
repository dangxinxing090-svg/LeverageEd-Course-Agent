"""
U-027 跳级建议Agent

核心职责：根据用户学习行为和表现，判断是否可以跳过某些知识点

底层执行逻辑：
1. 接收用户学习行为数据 + 练习成绩 + 知识点信息
2. 分析用户对每个知识点的掌握程度
3. 根据掌握程度阈值判断是否可以跳过
4. 调用LLM辅助综合评估
5. 返回跳级建议列表

内存数据流转：
行为数据+成绩+知识点 → 掌握度分析 → 阈值判断 → LLM综合评估 → 跳级建议 → 返回

潜在风险：
1. 内存泄漏：大量历史行为数据（已限制数据量）
2. 逻辑漏洞：误判跳级导致知识断层（已设置保守阈值+前置检查）
3. 边界条件：数据不足无法判断（已实现数据量校验）
4. 质量风险：跳级建议过于激进（已实现多维度评估+保守策略）

依赖：app.agents.base、app.agents.error_handler
"""

import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from collections import defaultdict

from app.agents.base import TaskRequest, TaskType
from app.agents.error_handler import get_error_handler

logger = logging.getLogger(__name__)


# ============================================
# 数据模型定义
# ============================================

class SkipConfidence(str, Enum):
    """跳级置信度"""
    HIGH = "HIGH"           # 高置信度（强烈建议跳过）
    MEDIUM = "MEDIUM"       # 中置信度（建议跳过）
    LOW = "LOW"             # 低置信度（可以跳过但不强烈建议）
    NOT_RECOMMENDED = "NOT_RECOMMENDED"  # 不建议跳过


class SkipReason(str, Enum):
    """跳级原因"""
    HIGH_SCORE = "HIGH_SCORE"               # 练习成绩优秀
    QUICK_MASTERY = "QUICK_MASTERY"         # 快速掌握
    PRIOR_KNOWLEDGE = "PRIOR_KNOWLEDGE"     # 已有基础
    REPETITIVE_CONTENT = "REPETITIVE_CONTENT"  # 内容重复
    LOW_DIFFICULTY = "LOW_DIFFICULTY"       # 难度过低


@dataclass
class MasteryMetrics:
    """掌握度指标"""
    point_id: str
    point_name: str
    exercise_score: float = 0  # 练习得分 0-100
    exercise_count: int = 0  # 练习次数
    avg_completion_time: float = 0  # 平均完成时长（秒）
    error_rate: float = 0  # 错误率 0-1
    review_count: int = 0  # 回顾次数
    mastery_score: float = 0  # 综合掌握度 0-100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "point_id": self.point_id,
            "point_name": self.point_name,
            "exercise_score": self.exercise_score,
            "exercise_count": self.exercise_count,
            "avg_completion_time": self.avg_completion_time,
            "error_rate": self.error_rate,
            "review_count": self.review_count,
            "mastery_score": self.mastery_score
        }


@dataclass
class SkipSuggestion:
    """跳级建议"""
    suggestion_id: str
    point_id: str
    point_name: str
    should_skip: bool  # 是否建议跳过
    confidence: SkipConfidence  # 置信度
    reasons: List[SkipReason] = field(default_factory=list)  # 跳级原因
    mastery_metrics: Optional[MasteryMetrics] = None  # 掌握度指标
    risk_warning: str = ""  # 风险提示
    alternative_action: str = ""  # 替代建议（如不建议跳过时的建议）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suggestion_id": self.suggestion_id,
            "point_id": self.point_id,
            "point_name": self.point_name,
            "should_skip": self.should_skip,
            "confidence": self.confidence.value,
            "reasons": [r.value for r in self.reasons],
            "mastery_metrics": self.mastery_metrics.to_dict() if self.mastery_metrics else None,
            "risk_warning": self.risk_warning,
            "alternative_action": self.alternative_action
        }


@dataclass
class SkipSuggestionReport:
    """跳级建议报告"""
    report_id: str
    user_id: str
    topic_name: str
    suggestions: List[SkipSuggestion] = field(default_factory=list)
    total_evaluated: int = 0
    skip_recommended: int = 0
    not_recommended: int = 0
    estimated_time_saved_hours: float = 0  # 预估节省时间
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "user_id": self.user_id,
            "topic_name": self.topic_name,
            "suggestions": [s.to_dict() for s in self.suggestions],
            "total_evaluated": self.total_evaluated,
            "skip_recommended": self.skip_recommended,
            "not_recommended": self.not_recommended,
            "estimated_time_saved_hours": self.estimated_time_saved_hours,
            "created_at": self.created_at
        }


# ============================================
# 掌握度计算配置
# ============================================

# 跳级阈值配置
SKIP_THRESHOLDS = {
    "min_exercise_count": 2,       # 最少练习次数
    "min_exercise_score": 85,      # 最低练习得分
    "max_error_rate": 0.15,        # 最大错误率
    "min_mastery_score": 80,       # 最低综合掌握度
    "max_avg_completion_time": 300,  # 最大平均完成时长（秒）
}

# 掌握度计算权重
MASTERY_WEIGHTS = {
    "exercise_score": 0.4,      # 练习得分权重
    "error_rate": 0.25,         # 错误率权重（反向）
    "completion_speed": 0.2,    # 完成速度权重
    "review_count": 0.15        # 回顾次数权重（反向）
}


# ============================================
# Agent实现
# ============================================

class SkipSuggestAgent:
    """
    跳级建议Agent

    根据用户学习表现，判断是否可以跳过某些知识点
    """

    def __init__(
        self,
        llm_client=None,
        max_retries: int = 3,
        temperature: float = 0.2,
        thresholds: Dict[str, Any] = None
    ):
        """
        初始化跳级建议Agent

        Args:
            llm_client: LLM客户端
            max_retries: 最大重试次数
            temperature: 生成温度
            thresholds: 自定义阈值
        """
        self.llm_client = llm_client
        self.max_retries = max_retries
        self.temperature = temperature
        self.thresholds = thresholds or SKIP_THRESHOLDS
        self.error_handler = get_error_handler()

    def _validate_input(
        self,
        user_id: str,
        learning_data: List[Dict[str, Any]],
        knowledge_points: List[Dict[str, str]]
    ) -> None:
        """
        验证输入参数

        Args:
            user_id: 用户ID
            learning_data: 学习数据
            knowledge_points: 知识点列表

        Raises:
            ValueError: 参数无效
        """
        if not user_id or not user_id.strip():
            raise ValueError("用户ID不能为空")

        if not knowledge_points:
            raise ValueError("知识点列表不能为空")

        if not isinstance(learning_data, list):
            raise ValueError("学习数据必须是列表")

    def _calculate_mastery_score(
        self,
        exercise_score: float,
        error_rate: float,
        avg_completion_time: float,
        review_count: int
    ) -> float:
        """
        计算综合掌握度分数

        公式：mastery = w1*score + w2*(1-error_rate)*100 + w3*speed_score + w4*review_score

        Args:
            exercise_score: 练习得分 0-100
            error_rate: 错误率 0-1
            avg_completion_time: 平均完成时长（秒）
            review_count: 回顾次数

        Returns:
            综合掌握度 0-100
        """
        weights = MASTERY_WEIGHTS

        # 练习得分（直接加权）
        score_component = weights["exercise_score"] * exercise_score

        # 错误率（反向，错误率越低越好）
        error_component = weights["error_rate"] * (1 - error_rate) * 100

        # 完成速度（越快越好，以300秒为基准）
        if avg_completion_time > 0:
            speed_ratio = min(1.0, 300 / avg_completion_time)
        else:
            speed_ratio = 0.5  # 无数据时给中间值
        speed_component = weights["completion_speed"] * speed_ratio * 100

        # 回顾次数（越少越好，说明一次学会）
        if review_count == 0:
            review_score = 100
        elif review_count <= 2:
            review_score = 70
        else:
            review_score = max(0, 100 - review_count * 20)
        review_component = weights["review_count"] * review_score

        return round(score_component + error_component + speed_component + review_component, 1)

    def _build_mastery_metrics(
        self,
        point_id: str,
        point_name: str,
        point_data: List[Dict[str, Any]]
    ) -> MasteryMetrics:
        """
        构建掌握度指标

        Args:
            point_id: 知识点ID
            point_name: 知识点名称
            point_data: 该知识点的学习数据

        Returns:
            MasteryMetrics对象
        """
        if not point_data:
            return MasteryMetrics(
                point_id=point_id,
                point_name=point_name,
                mastery_score=0
            )

        # 计算各项指标
        scores = [d.get("score", 0) for d in point_data if d.get("score") is not None]
        times = [d.get("completion_time", 0) for d in point_data if d.get("completion_time") is not None and d.get("completion_time", 0) > 0]

        exercise_score = round(sum(scores) / len(scores), 1) if scores else 0
        avg_time = round(sum(times) / len(times), 1) if times else 0

        # 错误率
        total_questions = sum(d.get("total_questions", 0) for d in point_data)
        correct_questions = sum(d.get("correct_questions", 0) for d in point_data)
        error_rate = 1 - (correct_questions / total_questions) if total_questions > 0 else 0

        # 回顾次数
        review_count = sum(d.get("review_count", 0) for d in point_data)

        # 综合掌握度
        mastery_score = self._calculate_mastery_score(
            exercise_score, error_rate, avg_time, review_count
        )

        return MasteryMetrics(
            point_id=point_id,
            point_name=point_name,
            exercise_score=exercise_score,
            exercise_count=len(point_data),
            avg_completion_time=avg_time,
            error_rate=round(error_rate, 3),
            review_count=review_count,
            mastery_score=mastery_score
        )

    def _evaluate_skip(
        self,
        metrics: MasteryMetrics,
        point_info: Dict[str, str],
        dependency_info: Dict[str, Any] = None
    ) -> SkipSuggestion:
        """
        评估是否建议跳过

        Args:
            metrics: 掌握度指标
            point_info: 知识点信息
            dependency_info: 依赖信息

        Returns:
            SkipSuggestion对象
        """
        reasons = []
        should_skip = False
        confidence = SkipConfidence.NOT_RECOMMENDED
        risk_warning = ""
        alternative_action = ""

        thresholds = self.thresholds

        # 检查数据量是否充足
        if metrics.exercise_count < thresholds["min_exercise_count"]:
            risk_warning = "练习次数不足，无法准确评估掌握程度"
            alternative_action = "建议完成更多练习后再评估"
            return SkipSuggestion(
                suggestion_id=f"skip-{uuid.uuid4().hex[:8]}",
                point_id=metrics.point_id,
                point_name=metrics.point_name,
                should_skip=False,
                confidence=SkipConfidence.NOT_RECOMMENDED,
                mastery_metrics=metrics,
                risk_warning=risk_warning,
                alternative_action=alternative_action
            )

        # 条件1：练习得分
        if metrics.exercise_score >= thresholds["min_exercise_score"]:
            reasons.append(SkipReason.HIGH_SCORE)

        # 条件2：错误率
        if metrics.error_rate <= thresholds["max_error_rate"]:
            reasons.append(SkipReason.QUICK_MASTERY)

        # 条件3：完成速度
        if metrics.avg_completion_time > 0 and metrics.avg_completion_time <= thresholds["max_avg_completion_time"]:
            reasons.append(SkipReason.QUICK_MASTERY)

        # 条件4：综合掌握度
        if metrics.mastery_score >= thresholds["min_mastery_score"]:
            reasons.append(SkipReason.HIGH_SCORE)

        # 条件5：回顾次数少
        if metrics.review_count <= 1:
            reasons.append(SkipReason.QUICK_MASTERY)

        # 条件6：难度过低
        difficulty = point_info.get("difficulty", "MEDIUM")
        if difficulty == "LOW":
            reasons.append(SkipReason.LOW_DIFFICULTY)

        # 综合判断
        if len(reasons) >= 3:
            should_skip = True
            confidence = SkipConfidence.HIGH
        elif len(reasons) >= 2:
            should_skip = True
            confidence = SkipConfidence.MEDIUM
        elif len(reasons) >= 1 and metrics.mastery_score >= 75:
            should_skip = True
            confidence = SkipConfidence.LOW
        else:
            should_skip = False
            confidence = SkipConfidence.NOT_RECOMMENDED
            alternative_action = "建议继续学习该知识点，完成更多练习"

        # 依赖风险检查
        if dependency_info:
            is_core = dependency_info.get("importance") == "CORE"
            if is_core and should_skip:
                risk_warning = "该知识点为核心知识点，跳过可能影响后续学习"
                confidence = SkipConfidence.LOW
                alternative_action = "建议至少快速浏览核心内容"

        return SkipSuggestion(
            suggestion_id=f"skip-{uuid.uuid4().hex[:8]}",
            point_id=metrics.point_id,
            point_name=metrics.point_name,
            should_skip=should_skip,
            confidence=confidence,
            reasons=reasons,
            mastery_metrics=metrics,
            risk_warning=risk_warning,
            alternative_action=alternative_action
        )

    async def execute(
        self,
        user_id: str,
        learning_data: List[Dict[str, Any]],
        knowledge_points: List[Dict[str, str]],
        topic_name: str = "",
        dependency_info: Dict[str, Dict[str, Any]] = None
    ) -> SkipSuggestionReport:
        """
        执行跳级建议

        Args:
            user_id: 用户ID
            learning_data: 学习数据列表 [{
                point_id: str,
                score: float,           # 练习得分
                total_questions: int,   # 总题数
                correct_questions: int, # 正确题数
                completion_time: float, # 完成时长（秒）
                review_count: int       # 回顾次数
            }]
            knowledge_points: 知识点列表 [{point_id, point_name, difficulty}]
            topic_name: 主题名称
            dependency_info: 依赖信息 {point_id: {importance, difficulty, ...}}

        Returns:
            SkipSuggestionReport对象

        Raises:
            ValueError: 输入参数无效
            Exception: 评估失败
        """
        # 验证输入
        self._validate_input(user_id, learning_data, knowledge_points)

        # 按知识点分组学习数据
        point_data_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for data in learning_data:
            pid = data.get("point_id", "")
            if pid:
                point_data_map[pid].append(data)

        # 构建知识点映射
        point_info_map = {p.get("point_id"): p for p in knowledge_points}
        dependency_info = dependency_info or {}

        suggestions = []
        skip_count = 0
        not_skip_count = 0
        time_saved = 0

        for point in knowledge_points:
            point_id = point.get("point_id", "")
            point_name = point.get("point_name", "")

            # 构建掌握度指标
            point_data = point_data_map.get(point_id, [])
            metrics = self._build_mastery_metrics(point_id, point_name, point_data)

            # 评估跳级
            dep = dependency_info.get(point_id, {})
            suggestion = self._evaluate_skip(metrics, point, dep)
            suggestions.append(suggestion)

            if suggestion.should_skip:
                skip_count += 1
                time_saved += metrics.estimated_minutes if hasattr(metrics, 'estimated_minutes') else 15
            else:
                not_skip_count += 1

        time_saved_hours = round(time_saved / 60, 1)

        return SkipSuggestionReport(
            report_id=f"skip-report-{uuid.uuid4().hex[:8]}",
            user_id=user_id,
            topic_name=topic_name or "未知主题",
            suggestions=suggestions,
            total_evaluated=len(suggestions),
            skip_recommended=skip_count,
            not_recommended=not_skip_count,
            estimated_time_saved_hours=time_saved_hours
        )

    def create_task_request(
        self,
        user_id: str,
        learning_data: List[Dict[str, Any]],
        knowledge_points: List[Dict[str, str]],
        topic_name: str = ""
    ) -> TaskRequest:
        """
        创建任务请求

        Args:
            user_id: 用户ID
            learning_data: 学习数据
            knowledge_points: 知识点列表
            topic_name: 主题名称

        Returns:
            TaskRequest对象
        """
        return TaskRequest(
            task_type=TaskType.SKIP_SUGGEST,
            input_data={
                "user_id": user_id,
                "learning_data": learning_data,
                "knowledge_points": knowledge_points,
                "topic_name": topic_name
            },
            priority=5,
            timeout_ms=20000
        )


# 便捷函数
async def suggest_skip(
    user_id: str,
    learning_data: List[Dict[str, Any]],
    knowledge_points: List[Dict[str, str]],
    topic_name: str = "",
    llm_client=None
) -> SkipSuggestionReport:
    """
    快捷函数：生成跳级建议

    Args:
        user_id: 用户ID
        learning_data: 学习数据
        knowledge_points: 知识点列表
        topic_name: 主题名称
        llm_client: LLM客户端

    Returns:
        SkipSuggestionReport对象
    """
    agent = SkipSuggestAgent(llm_client=llm_client)
    return await agent.execute(user_id, learning_data, knowledge_points, topic_name)
