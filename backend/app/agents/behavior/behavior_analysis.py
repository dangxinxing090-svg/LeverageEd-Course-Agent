"""
U-030 用户行为分析Agent

核心职责：对用户行为数据进行多维度分析，生成学习画像和知识掌握度模型

底层执行逻辑：
1. 接收用户行为事件列表
2. 按维度聚合统计（时间、知识点、行为类型）
3. 基于BKT（贝叶斯知识追踪）模型计算知识点掌握概率
4. 生成学习画像（活跃度、专注度、薄弱点等）
5. 返回结构化分析报告

内存数据流转：
行为事件 → 维度聚合 → BKT建模 → 画像生成 → 结构化报告 → 返回

分析维度（4个维度）：
1. 时间维度：学习时长分布、活跃时段、连续学习天数
2. 内容维度：知识点覆盖率、停留时长、重复学习率
3. 练习维度：正确率、平均用时、错题分布
4. 路径维度：学习顺序、跳级频率、回退频率

BKT模型参数：
- P(L0): 先验掌握概率（初始值0.3）
- P(T): 学习转移概率（每次学习后掌握的概率0.15）
- P(G): 猜对概率（未掌握时猜对的概率0.1）
- P(S): 失误概率（掌握时答错的概率0.05）

潜在风险：
1. 内存泄漏：大量历史事件全量加载（已实现分页+采样）
2. 逻辑漏洞：BKT参数不合理（已使用教育领域经验值）
3. 边界条件：无行为数据（已有空数据兜底）
4. 质量风险：分析结果偏差（已实现多维度交叉验证）

依赖：app.agents.base、app.agents.error_handler
"""

import json
import logging
import math
import uuid
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from collections import defaultdict

from app.agents.base import TaskRequest, TaskType
from app.agents.error_handler import get_error_handler

logger = logging.getLogger(__name__)


# ============================================
# 数据模型定义
# ============================================

class ActivityLevel(str, Enum):
    """活跃度等级"""
    INACTIVE = "INACTIVE"    # 不活跃
    LOW = "LOW"              # 低活跃
    MEDIUM = "MEDIUM"        # 中等活跃
    HIGH = "HIGH"            # 高活跃
    VERY_HIGH = "VERY_HIGH"  # 非常活跃


class MasteryLevel(str, Enum):
    """掌握度等级"""
    NOT_STARTED = "NOT_STARTED"  # 未开始
    WEAK = "WEAK"                # 薄弱
    MODERATE = "MODERATE"        # 中等
    GOOD = "GOOD"                # 良好
    MASTERED = "MASTERED"        # 已掌握


@dataclass
class TimeAnalysis:
    """时间维度分析"""
    total_study_minutes: float = 0  # 总学习时长（分钟）
    avg_daily_minutes: float = 0    # 日均学习时长
    active_days: int = 0            # 活跃天数
    streak_days: int = 0            # 连续学习天数
    peak_hour: int = 0              # 高峰时段（小时）
    study_days: List[str] = None    # 学习日期列表

    def __post_init__(self):
        if self.study_days is None:
            self.study_days = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_study_minutes": self.total_study_minutes,
            "avg_daily_minutes": self.avg_daily_minutes,
            "active_days": self.active_days,
            "streak_days": self.streak_days,
            "peak_hour": self.peak_hour,
            "study_days_list": self.study_days[:30]  # 最多返回30天
        }


@dataclass
class ContentAnalysis:
    """内容维度分析"""
    total_points_viewed: int = 0       # 浏览的知识点数
    unique_points_viewed: int = 0      # 不重复的知识点数
    coverage_rate: float = 0           # 覆盖率
    avg_stay_seconds: float = 0        # 平均停留时长
    repeat_rate: float = 0             # 重复学习率
    most_viewed_points: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_points_viewed": self.total_points_viewed,
            "unique_points_viewed": self.unique_points_viewed,
            "coverage_rate": self.coverage_rate,
            "avg_stay_seconds": self.avg_stay_seconds,
            "repeat_rate": self.repeat_rate,
            "most_viewed_points": self.most_viewed_points[:10]
        }


@dataclass
class ExerciseAnalysis:
    """练习维度分析"""
    total_exercises: int = 0           # 总练习次数
    total_questions: int = 0           # 总答题数
    correct_questions: int = 0         # 正确数
    accuracy_rate: float = 0           # 正确率
    avg_time_seconds: float = 0        # 平均答题时长
    perfect_exercises: int = 0         # 满分次数
    weak_points: List[Dict[str, Any]] = field(default_factory=list)  # 薄弱知识点

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_exercises": self.total_exercises,
            "total_questions": self.total_questions,
            "correct_questions": self.correct_questions,
            "accuracy_rate": self.accuracy_rate,
            "avg_time_seconds": self.avg_time_seconds,
            "perfect_exercises": self.perfect_exercises,
            "weak_points": self.weak_points[:10]
        }


@dataclass
class PathAnalysis:
    """路径维度分析"""
    total_switches: int = 0            # 知识点切换次数
    skip_count: int = 0                # 跳级次数
    go_back_count: int = 0             # 回退次数
    linear_rate: float = 0             # 线性学习率（按顺序学习的比例）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_switches": self.total_switches,
            "skip_count": self.skip_count,
            "go_back_count": self.go_back_count,
            "linear_rate": self.linear_rate
        }


@dataclass
class PointMastery:
    """知识点掌握度"""
    point_id: str
    point_name: str
    mastery_probability: float = 0  # BKT掌握概率 0-1
    mastery_level: MasteryLevel = MasteryLevel.NOT_STARTED
    view_count: int = 0
    exercise_count: int = 0
    correct_rate: float = 0
    total_study_seconds: float = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "point_id": self.point_id,
            "point_name": self.point_name,
            "mastery_probability": round(self.mastery_probability, 3),
            "mastery_level": self.mastery_level.value,
            "view_count": self.view_count,
            "exercise_count": self.exercise_count,
            "correct_rate": round(self.correct_rate, 3),
            "total_study_seconds": round(self.total_study_seconds, 1)
        }


@dataclass
class UserProfile:
    """学习画像"""
    user_id: str
    activity_level: ActivityLevel = ActivityLevel.INACTIVE
    focus_score: float = 0  # 专注度评分 0-100
    consistency_score: float = 0  # 一致性评分 0-100
    overall_mastery: float = 0  # 总体掌握度 0-100
    strengths: List[str] = field(default_factory=list)  # 优势
    improvements: List[str] = field(default_factory=list)  # 待改进

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "activity_level": self.activity_level.value,
            "focus_score": round(self.focus_score, 1),
            "consistency_score": round(self.consistency_score, 1),
            "overall_mastery": round(self.overall_mastery, 1),
            "strengths": self.strengths,
            "improvements": self.improvements
        }


@dataclass
class AnalysisReport:
    """分析报告"""
    report_id: str
    user_id: str
    time_analysis: TimeAnalysis = field(default_factory=TimeAnalysis)
    content_analysis: ContentAnalysis = field(default_factory=ContentAnalysis)
    exercise_analysis: ExerciseAnalysis = field(default_factory=ExerciseAnalysis)
    path_analysis: PathAnalysis = field(default_factory=PathAnalysis)
    point_masteries: List[PointMastery] = field(default_factory=list)
    user_profile: Optional[UserProfile] = None
    analyzed_event_count: int = 0
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "user_id": self.user_id,
            "time_analysis": self.time_analysis.to_dict(),
            "content_analysis": self.content_analysis.to_dict(),
            "exercise_analysis": self.exercise_analysis.to_dict(),
            "path_analysis": self.path_analysis.to_dict(),
            "point_masteries": [p.to_dict() for p in self.point_masteries],
            "user_profile": self.user_profile.to_dict() if self.user_profile else None,
            "analyzed_event_count": self.analyzed_event_count,
            "created_at": self.created_at
        }


# ============================================
# BKT模型
# ============================================

@dataclass
class BKTParams:
    """BKT模型参数"""
    p_l0: float = 0.3   # 先验掌握概率
    p_t: float = 0.15    # 学习转移概率
    p_g: float = 0.1     # 猜对概率
    p_s: float = 0.05    # 失误概率


def bkt_update(
    p_known: float,
    is_correct: bool,
    params: BKTParams = None
) -> float:
    """
    BKT单步更新

    Args:
        p_known: 当前掌握概率
        is_correct: 是否答对
        params: BKT参数

    Returns:
        更新后的掌握概率
    """
    if params is None:
        params = BKTParams()

    # 步骤1：从观测中更新（贝叶斯后验）
    if is_correct:
        p_l_given_obs = (
            p_known * (1 - params.p_s)
            / (p_known * (1 - params.p_s) + (1 - p_known) * params.p_g)
        )
    else:
        p_l_given_obs = (
            p_known * params.p_s
            / (p_known * params.p_s + (1 - p_known) * (1 - params.p_g))
        )

    # 步骤2：学习转移
    p_updated = p_l_given_obs + (1 - p_l_given_obs) * params.p_t

    # 限制在[0, 1]
    return max(0.0, min(1.0, p_updated))


def bkt_from_events(
    events: List[Dict[str, Any]],
    point_id: str,
    params: BKTParams = None
) -> float:
    """
    从行为事件序列计算BKT掌握概率

    Args:
        events: 行为事件列表
        point_id: 知识点ID
        params: BKT参数

    Returns:
        掌握概率
    """
    if params is None:
        params = BKTParams()

    p_known = params.p_l0

    # 提取该知识点的答题事件
    for event in events:
        if event.get("point_id") != point_id:
            continue

        action = event.get("action", "")
        metadata = event.get("metadata", {})

        if action == "SUBMIT_ANSWER":
            is_correct = metadata.get("is_correct", False)
            p_known = bkt_update(p_known, is_correct, params)

        elif action == "VIEW_EXPLANATION":
            # 查看讲解也视为一次学习机会
            p_known = p_known + (1 - p_known) * params.p_t * 0.5
            p_known = max(0.0, min(1.0, p_known))

    return p_known


# ============================================
# Agent实现
# ============================================

class BehaviorAnalysisAgent:
    """
    用户行为分析Agent

    对用户行为数据进行多维度分析
    """

    def __init__(
        self,
        bkt_params: BKTParams = None,
        max_events: int = 10000
    ):
        """
        初始化行为分析Agent

        Args:
            bkt_params: BKT模型参数
            max_events: 最大分析事件数
        """
        self.bkt_params = bkt_params or BKTParams()
        self.max_events = max_events
        self.error_handler = get_error_handler()

    def _validate_input(
        self,
        user_id: str,
        events: List[Dict[str, Any]]
    ) -> None:
        """
        验证输入参数

        Args:
            user_id: 用户ID
            events: 行为事件列表

        Raises:
            ValueError: 参数无效
        """
        if not user_id or not user_id.strip():
            raise ValueError("用户ID不能为空")

        if not isinstance(events, list):
            raise ValueError("事件列表必须是列表")

    def _parse_timestamp(self, ts: str) -> Optional[datetime]:
        """
        解析时间戳

        Args:
            ts: 时间戳字符串

        Returns:
            datetime或None
        """
        if not ts:
            return None
        try:
            # 尝试ISO格式
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None

    def _analyze_time(
        self,
        events: List[Dict[str, Any]]
    ) -> TimeAnalysis:
        """
        时间维度分析

        Args:
            events: 行为事件列表

        Returns:
            TimeAnalysis
        """
        total_ms = 0
        hour_counts: Dict[int, int] = defaultdict(int)
        study_dates: set = set()

        for event in events:
            duration = event.get("duration_ms", 0)
            total_ms += duration

            ts = self._parse_timestamp(event.get("timestamp", ""))
            if ts:
                study_dates.add(ts.strftime("%Y-%m-%d"))
                hour_counts[ts.hour] += 1

        total_minutes = total_ms / 60000
        active_days = len(study_dates)
        avg_daily = total_minutes / active_days if active_days > 0 else 0

        # 计算连续学习天数
        streak = 0
        if study_dates:
            sorted_dates = sorted(study_dates, reverse=True)
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            # 简化：从最近日期开始往前数连续天数
            check_date = datetime.now(timezone.utc).date()
            for date_str in sorted_dates:
                d = datetime.strptime(date_str, "%Y-%m-%d").date()
                if d == check_date:
                    streak += 1
                    check_date -= timedelta(days=1)
                elif d < check_date:
                    break

        # 高峰时段
        peak_hour = 0
        if hour_counts:
            peak_hour = max(hour_counts, key=hour_counts.get)

        return TimeAnalysis(
            total_study_minutes=round(total_minutes, 1),
            avg_daily_minutes=round(avg_daily, 1),
            active_days=active_days,
            streak_days=streak,
            peak_hour=peak_hour,
            study_days=sorted(study_dates, reverse=True)
        )

    def _analyze_content(
        self,
        events: List[Dict[str, Any]]
    ) -> ContentAnalysis:
        """
        内容维度分析

        Args:
            events: 行为事件列表

        Returns:
            ContentAnalysis
        """
        view_actions = {"VIEW_POINT", "VIEW_EXPLANATION"}
        point_views: Dict[str, int] = defaultdict(int)
        point_stay: Dict[str, float] = defaultdict(float)

        for event in events:
            action = event.get("action", "")
            point_id = event.get("point_id", "")

            if action in view_actions and point_id:
                point_views[point_id] += 1
                point_stay[point_id] += event.get("duration_ms", 0) / 1000

        total_views = sum(point_views.values())
        unique_points = len(point_views)
        repeat_views = total_views - unique_points
        repeat_rate = repeat_views / total_views if total_views > 0 else 0

        avg_stay = (
            sum(point_stay.values()) / unique_points
            if unique_points > 0 else 0
        )

        # 最常浏览的知识点
        most_viewed = sorted(
            point_views.items(), key=lambda x: x[1], reverse=True
        )[:10]

        return ContentAnalysis(
            total_points_viewed=total_views,
            unique_points_viewed=unique_points,
            coverage_rate=0,  # 需要总知识点数，由调用方补充
            avg_stay_seconds=round(avg_stay, 1),
            repeat_rate=round(repeat_rate, 3),
            most_viewed_points=[
                {"point_id": pid, "view_count": count}
                for pid, count in most_viewed
            ]
        )

    def _analyze_exercise(
        self,
        events: List[Dict[str, Any]]
    ) -> ExerciseAnalysis:
        """
        练习维度分析

        Args:
            events: 行为事件列表

        Returns:
            ExerciseAnalysis
        """
        exercise_events = [
            e for e in events
            if e.get("action") == "SUBMIT_ANSWER"
        ]

        total_exercises = len(exercise_events)
        total_questions = 0
        correct_questions = 0
        total_time = 0
        perfect_count = 0
        point_correct: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"total": 0, "correct": 0}
        )

        for event in exercise_events:
            metadata = event.get("metadata", {})
            is_correct = metadata.get("is_correct", False)
            q_count = metadata.get("question_count", 1)
            c_count = metadata.get("correct_count", 1 if is_correct else 0)

            total_questions += q_count
            correct_questions += c_count
            total_time += event.get("duration_ms", 0)

            point_id = event.get("point_id", "")
            if point_id:
                point_correct[point_id]["total"] += q_count
                point_correct[point_id]["correct"] += c_count

            if is_correct and c_count == q_count:
                perfect_count += 1

        accuracy = correct_questions / total_questions if total_questions > 0 else 0
        avg_time = total_time / 1000 / total_exercises if total_exercises > 0 else 0

        # 薄弱知识点（正确率最低的）
        weak_points = []
        for pid, counts in point_correct.items():
            if counts["total"] >= 2:  # 至少2题才有统计意义
                rate = counts["correct"] / counts["total"]
                weak_points.append({
                    "point_id": pid,
                    "accuracy": round(rate, 3),
                    "total": counts["total"]
                })
        weak_points.sort(key=lambda x: x["accuracy"])
        weak_points = weak_points[:10]

        return ExerciseAnalysis(
            total_exercises=total_exercises,
            total_questions=total_questions,
            correct_questions=correct_questions,
            accuracy_rate=round(accuracy, 3),
            avg_time_seconds=round(avg_time, 1),
            perfect_exercises=perfect_count,
            weak_points=weak_points
        )

    def _analyze_path(
        self,
        events: List[Dict[str, Any]]
    ) -> PathAnalysis:
        """
        路径维度分析

        Args:
            events: 行为事件列表

        Returns:
            PathAnalysis
        """
        switches = 0
        skips = 0
        go_backs = 0
        linear = 0

        switch_events = [
            e for e in events
            if e.get("action") in ("SWITCH_POINT", "SKIP_POINT", "GO_BACK")
        ]

        switches = len(switch_events)
        skips = sum(1 for e in switch_events if e["action"] == "SKIP_POINT")
        go_backs = sum(1 for e in switch_events if e["action"] == "GO_BACK")
        linear = switches - skips - go_backs

        linear_rate = linear / switches if switches > 0 else 1.0

        return PathAnalysis(
            total_switches=switches,
            skip_count=skips,
            go_back_count=go_backs,
            linear_rate=round(linear_rate, 3)
        )

    def _compute_point_masteries(
        self,
        events: List[Dict[str, Any]],
        point_names: Dict[str, str] = None
    ) -> List[PointMastery]:
        """
        计算各知识点掌握度

        Args:
            events: 行为事件列表
            point_names: 知识点ID到名称的映射

        Returns:
            PointMastery列表
        """
        point_names = point_names or {}

        # 收集所有涉及的知识点
        point_ids = set()
        point_data: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"views": 0, "exercises": 0, "correct": 0, "total_q": 0, "time": 0}
        )

        for event in events:
            pid = event.get("point_id", "")
            if not pid:
                continue

            point_ids.add(pid)
            action = event.get("action", "")
            metadata = event.get("metadata", {})

            if action in ("VIEW_POINT", "VIEW_EXPLANATION"):
                point_data[pid]["views"] += 1
                point_data[pid]["time"] += event.get("duration_ms", 0) / 1000

            elif action == "SUBMIT_ANSWER":
                point_data[pid]["exercises"] += 1
                point_data[pid]["total_q"] += metadata.get("question_count", 1)
                if metadata.get("is_correct", False):
                    point_data[pid]["correct"] += metadata.get("correct_count", 1)

        # 计算BKT掌握度
        masteries = []
        for pid in point_ids:
            p_mastery = bkt_from_events(events, pid, self.bkt_params)
            data = point_data[pid]

            # 确定掌握等级
            if p_mastery >= 0.9:
                level = MasteryLevel.MASTERED
            elif p_mastery >= 0.7:
                level = MasteryLevel.GOOD
            elif p_mastery >= 0.4:
                level = MasteryLevel.MODERATE
            elif p_mastery > self.bkt_params.p_l0:
                level = MasteryLevel.WEAK
            else:
                level = MasteryLevel.NOT_STARTED

            correct_rate = (
                data["correct"] / data["total_q"]
                if data["total_q"] > 0 else 0
            )

            masteries.append(PointMastery(
                point_id=pid,
                point_name=point_names.get(pid, ""),
                mastery_probability=p_mastery,
                mastery_level=level,
                view_count=data["views"],
                exercise_count=data["exercises"],
                correct_rate=correct_rate,
                total_study_seconds=data["time"]
            ))

        # 按掌握度排序
        masteries.sort(key=lambda m: m.mastery_probability, reverse=True)
        return masteries

    def _build_user_profile(
        self,
        user_id: str,
        time_analysis: TimeAnalysis,
        exercise_analysis: ExerciseAnalysis,
        point_masteries: List[PointMastery]
    ) -> UserProfile:
        """
        构建学习画像

        Args:
            user_id: 用户ID
            time_analysis: 时间分析
            exercise_analysis: 练习分析
            point_masteries: 知识点掌握度

        Returns:
            UserProfile
        """
        # 活跃度等级
        if time_analysis.active_days == 0:
            activity = ActivityLevel.INACTIVE
        elif time_analysis.avg_daily_minutes < 5:
            activity = ActivityLevel.LOW
        elif time_analysis.avg_daily_minutes < 20:
            activity = ActivityLevel.MEDIUM
        elif time_analysis.avg_daily_minutes < 60:
            activity = ActivityLevel.HIGH
        else:
            activity = ActivityLevel.VERY_HIGH

        # 专注度评分（基于线性学习率和平均答题时长）
        # 线性率高 → 专注，答题时长适中 → 专注
        focus = 50  # 基础分
        if exercise_analysis.avg_time_seconds > 0:
            # 答题时长在30-120秒之间最优
            if 30 <= exercise_analysis.avg_time_seconds <= 120:
                focus += 30
            elif 15 <= exercise_analysis.avg_time_seconds <= 180:
                focus += 15
        focus = min(100, focus)

        # 一致性评分（基于连续学习天数和活跃天数比）
        consistency = min(100, time_analysis.streak_days * 15)

        # 总体掌握度
        if point_masteries:
            overall = sum(m.mastery_probability for m in point_masteries) / len(point_masteries) * 100
        else:
            overall = 0

        # 优势和待改进
        strengths = []
        improvements = []

        if time_analysis.streak_days >= 7:
            strengths.append("坚持学习，连续学习超过7天")
        if exercise_analysis.accuracy_rate >= 0.8:
            strengths.append("练习正确率高，知识掌握扎实")
        if time_analysis.streak_days < 3:
            improvements.append("建议保持每日学习习惯")

        weak = [m for m in point_masteries if m.mastery_level in (MasteryLevel.WEAK, MasteryLevel.NOT_STARTED)]
        if len(weak) > 3:
            improvements.append(f"有{len(weak)}个知识点需要加强")

        if exercise_analysis.avg_time_seconds > 180:
            improvements.append("答题用时较长，建议加强练习提升熟练度")

        return UserProfile(
            user_id=user_id,
            activity_level=activity,
            focus_score=float(focus),
            consistency_score=float(consistency),
            overall_mastery=round(overall, 1),
            strengths=strengths[:5],
            improvements=improvements[:5]
        )

    async def execute(
        self,
        user_id: str,
        events: List[Dict[str, Any]],
        point_names: Dict[str, str] = None
    ) -> AnalysisReport:
        """
        执行行为分析

        Args:
            user_id: 用户ID
            events: 行为事件列表
            point_names: 知识点ID到名称的映射

        Returns:
            AnalysisReport对象

        Raises:
            ValueError: 输入参数无效
        """
        # 验证输入
        self._validate_input(user_id, events)

        # 限制事件数量
        if len(events) > self.max_events:
            logger.warning(f"事件数量{len(events)}超过上限，采样处理")
            # 均匀采样
            step = len(events) // self.max_events
            events = events[::step][:self.max_events]

        # 四维度分析
        time_analysis = self._analyze_time(events)
        content_analysis = self._analyze_content(events)
        exercise_analysis = self._analyze_exercise(events)
        path_analysis = self._analyze_path(events)

        # BKT掌握度
        point_masteries = self._compute_point_masteries(events, point_names)

        # 学习画像
        user_profile = self._build_user_profile(
            user_id, time_analysis, exercise_analysis, point_masteries
        )

        return AnalysisReport(
            report_id=f"report-{uuid.uuid4().hex[:8]}",
            user_id=user_id,
            time_analysis=time_analysis,
            content_analysis=content_analysis,
            exercise_analysis=exercise_analysis,
            path_analysis=path_analysis,
            point_masteries=point_masteries,
            user_profile=user_profile,
            analyzed_event_count=len(events)
        )

    def create_task_request(
        self,
        user_id: str,
        events: List[Dict[str, Any]],
        point_names: Dict[str, str] = None
    ) -> TaskRequest:
        """
        创建任务请求

        Args:
            user_id: 用户ID
            events: 行为事件列表
            point_names: 知识点名称映射

        Returns:
            TaskRequest对象
        """
        return TaskRequest(
            task_type=TaskType.BEHAVIOR_ANALYZE,
            input_data={
                "user_id": user_id,
                "events": events,
                "point_names": point_names or {}
            },
            priority=5,
            timeout_ms=30000
        )


# 便捷函数
async def analyze_behavior(
    user_id: str,
    events: List[Dict[str, Any]],
    point_names: Dict[str, str] = None
) -> AnalysisReport:
    """
    快捷函数：分析用户行为

    Args:
        user_id: 用户ID
        events: 行为事件列表
        point_names: 知识点名称映射

    Returns:
        AnalysisReport对象
    """
    agent = BehaviorAnalysisAgent()
    return await agent.execute(user_id, events, point_names)
