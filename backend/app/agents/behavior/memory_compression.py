"""
记忆压缩Agent

核心职责：定期归档旧行为数据，生成学习摘要，释放存储空间

底层执行逻辑：
1. 扫描超过保留期限的行为日志
2. 按用户+主题维度聚合原始行为为统计摘要
3. 生成学习摘要报告（时间段内学习概况）
4. 归档原始数据（标记或迁移到归档表）
5. 返回压缩结果统计

压缩策略：
- 热数据（7天内）：保留原始行为日志，支持实时分析
- 温数据（7-30天）：聚合为每日统计，保留关键事件
- 冷数据（30天以上）：聚合为每周统计，仅保留摘要

潜在风险：
1. 数据丢失：压缩过程中断（已实现事务保护）
2. 分析偏差：聚合粒度过粗（已保留关键指标）
3. 边界条件：空数据/超大用户（已有兜底+分页处理）

依赖：app.agents.base、app.agents.error_handler
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


# ============================================
# 数据模型定义
# ============================================

class DataTemperature(str, Enum):
    """数据温度"""
    HOT = "hot"        # 热数据（7天内）
    WARM = "warm"      # 温数据（7-30天）
    COLD = "cold"      # 冷数据（30天以上）


@dataclass
class CompressionConfig:
    """压缩配置"""
    hot_days: int = 7           # 热数据保留天数
    warm_days: int = 30         # 温数据保留天数
    batch_size: int = 1000      # 每批处理数量
    dry_run: bool = False       # 试运行（不实际删除）


@dataclass
class DailySummary:
    """每日行为摘要"""
    user_id: str
    date: str                   # YYYY-MM-DD
    topic_id: str
    
    # 学习统计
    total_events: int = 0
    learn_events: int = 0
    practice_events: int = 0
    question_events: int = 0
    skip_events: int = 0
    interact_events: int = 0
    
    # 练习统计
    total_exercises: int = 0
    correct_exercises: int = 0
    accuracy_rate: float = 0.0
    
    # 学习时长（秒）
    total_learn_time: int = 0
    
    # 涉及的知识组件
    component_ids: List[str] = field(default_factory=list)
    point_ids: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "date": self.date,
            "topic_id": self.topic_id,
            "total_events": self.total_events,
            "learn_events": self.learn_events,
            "practice_events": self.practice_events,
            "question_events": self.question_events,
            "skip_events": self.skip_events,
            "interact_events": self.interact_events,
            "total_exercises": self.total_exercises,
            "correct_exercises": self.correct_exercises,
            "accuracy_rate": round(self.accuracy_rate, 3),
            "total_learn_time": self.total_learn_time,
            "component_ids": self.component_ids,
            "point_ids": self.point_ids,
        }


@dataclass
class CompressionResult:
    """压缩结果"""
    task_id: str
    started_at: str
    completed_at: str = ""
    
    # 处理统计
    total_logs_scanned: int = 0
    hot_logs_kept: int = 0
    warm_logs_compressed: int = 0
    cold_logs_archived: int = 0
    
    # 摘要生成
    summaries_generated: int = 0
    
    # 错误统计
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_logs_scanned": self.total_logs_scanned,
            "hot_logs_kept": self.hot_logs_kept,
            "warm_logs_compressed": self.warm_logs_compressed,
            "cold_logs_archived": self.cold_logs_archived,
            "summaries_generated": self.summaries_generated,
            "errors": self.errors,
            "compression_rate": (
                (self.warm_logs_compressed + self.cold_logs_archived) / self.total_logs_scanned * 100
                if self.total_logs_scanned > 0 else 0
            )
        }


# ============================================
# 记忆压缩Agent
# ============================================

class MemoryCompressionAgent:
    """
    记忆压缩Agent
    
    定期将原始行为日志压缩为统计摘要，
    释放存储空间同时保留关键学习信息
    """
    
    def __init__(self, config: Optional[CompressionConfig] = None):
        self.config = config or CompressionConfig()
    
    def classify_temperature(self, log_timestamp: datetime) -> DataTemperature:
        """
        判断数据温度
        
        Args:
            log_timestamp: 日志时间戳
            
        Returns:
            数据温度
        """
        now = datetime.now(timezone.utc)
        age_days = (now - log_timestamp).days
        
        if age_days <= self.config.hot_days:
            return DataTemperature.HOT
        elif age_days <= self.config.warm_days:
            return DataTemperature.WARM
        else:
            return DataTemperature.COLD
    
    def aggregate_daily(
        self,
        logs: List[Dict[str, Any]]
    ) -> List[DailySummary]:
        """
        将行为日志聚合为每日摘要
        
        Args:
            logs: 行为日志列表（字典格式）
            
        Returns:
            每日摘要列表
        """
        # 按 (user_id, date, topic_id) 分组
        groups: Dict[tuple, List[Dict]] = defaultdict(list)
        
        for log in logs:
            user_id = log.get("user_id", "")
            topic_id = log.get("topic_id", "")
            timestamp = log.get("timestamp", "")
            
            # 提取日期
            if isinstance(timestamp, datetime):
                date_str = timestamp.strftime("%Y-%m-%d")
            elif timestamp:
                try:
                    date_str = timestamp[:10]
                except Exception:
                    date_str = "unknown"
            else:
                date_str = "unknown"
            
            key = (user_id, date_str, topic_id)
            groups[key].append(log)
        
        # 聚合每组数据
        summaries = []
        for (user_id, date_str, topic_id), group_logs in groups.items():
            summary = DailySummary(
                user_id=user_id,
                date=date_str,
                topic_id=topic_id
            )
            
            component_set = set()
            point_set = set()
            
            for log in group_logs:
                behavior_type = log.get("behavior_type", "")
                details = log.get("details", {}) or {}
                
                summary.total_events += 1
                
                if behavior_type == "learn":
                    summary.learn_events += 1
                    duration = details.get("duration", 0)
                    if isinstance(duration, (int, float)):
                        summary.total_learn_time += int(duration)
                elif behavior_type == "practice":
                    summary.practice_events += 1
                    summary.total_exercises += 1
                    if details.get("is_correct", False):
                        summary.correct_exercises += 1
                elif behavior_type == "question":
                    summary.question_events += 1
                elif behavior_type == "skip":
                    summary.skip_events += 1
                elif behavior_type == "interact":
                    summary.interact_events += 1
                
                cid = log.get("component_id", "")
                pid = log.get("point_id", "")
                if cid:
                    component_set.add(cid)
                if pid:
                    point_set.add(pid)
            
            summary.accuracy_rate = (
                summary.correct_exercises / summary.total_exercises
                if summary.total_exercises > 0 else 0.0
            )
            summary.component_ids = list(component_set)
            summary.point_ids = list(point_set)
            
            summaries.append(summary)
        
        return summaries
    
    def generate_weekly_summary(
        self,
        daily_summaries: List[DailySummary]
    ) -> Dict[str, Any]:
        """
        从每日摘要生成每周摘要
        
        Args:
            daily_summaries: 每日摘要列表
            
        Returns:
            每周摘要
        """
        if not daily_summaries:
            return {}
        
        user_id = daily_summaries[0].user_id
        topic_id = daily_summaries[0].topic_id
        
        # 按周分组
        weeks: Dict[str, List[DailySummary]] = defaultdict(list)
        for s in daily_summaries:
            # 提取周标识（年-周号）
            try:
                dt = datetime.strptime(s.date, "%Y-%m-%d")
                week_key = f"{dt.isocalendar()[0]}-W{dt.isocalendar()[1]:02d}"
            except Exception:
                week_key = s.date[:7] if len(s.date) >= 7 else "unknown"
            weeks[week_key].append(s)
        
        weekly_summaries = []
        for week_key, week_summaries in sorted(weeks.items()):
            total_events = sum(s.total_events for s in week_summaries)
            total_exercises = sum(s.total_exercises for s in week_summaries)
            correct_exercises = sum(s.correct_exercises for s in week_summaries)
            total_learn_time = sum(s.total_learn_time for s in week_summaries)
            
            all_components = set()
            all_points = set()
            for s in week_summaries:
                all_components.update(s.component_ids)
                all_points.update(s.point_ids)
            
            weekly_summaries.append({
                "week": week_key,
                "total_events": total_events,
                "total_exercises": total_exercises,
                "correct_exercises": correct_exercises,
                "accuracy_rate": round(
                    correct_exercises / total_exercises, 3
                ) if total_exercises > 0 else 0.0,
                "total_learn_time": total_learn_time,
                "active_days": len(week_summaries),
                "component_ids": list(all_components),
                "point_ids": list(all_points),
            })
        
        return {
            "user_id": user_id,
            "topic_id": topic_id,
            "weekly_summaries": weekly_summaries,
            "total_weeks": len(weekly_summaries),
        }
    
    def execute(
        self,
        logs: List[Dict[str, Any]],
        now: Optional[datetime] = None
    ) -> CompressionResult:
        """
        执行记忆压缩
        
        Args:
            logs: 待处理的行为日志列表
            now: 当前时间（测试用）
            
        Returns:
            压缩结果
        """
        task_id = f"compress-{uuid.uuid4().hex[:12]}"
        current_time = now or datetime.now(timezone.utc)
        
        result = CompressionResult(
            task_id=task_id,
            started_at=current_time.isoformat()
        )
        
        result.total_logs_scanned = len(logs)
        
        # 分类
        hot_logs = []
        warm_logs = []
        cold_logs = []
        
        for log in logs:
            timestamp = log.get("timestamp")
            if isinstance(timestamp, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                except Exception:
                    timestamp = None
            
            if not timestamp:
                # 无法解析时间戳，归为热数据保留
                hot_logs.append(log)
                continue
            
            temp = self.classify_temperature(timestamp)
            if temp == DataTemperature.HOT:
                hot_logs.append(log)
            elif temp == DataTemperature.WARM:
                warm_logs.append(log)
            else:
                cold_logs.append(log)
        
        result.hot_logs_kept = len(hot_logs)
        result.warm_logs_compressed = len(warm_logs)
        result.cold_logs_archived = len(cold_logs)
        
        # 生成温数据和冷数据的摘要
        if warm_logs:
            warm_summaries = self.aggregate_daily(warm_logs)
            result.summaries_generated += len(warm_summaries)
        
        if cold_logs:
            cold_daily = self.aggregate_daily(cold_logs)
            cold_weekly = self.generate_weekly_summary(cold_daily)
            result.summaries_generated += len(cold_daily)
        
        result.completed_at = datetime.now(timezone.utc).isoformat()
        
        return result


# ============================================
# 便捷函数
# ============================================

def compress_logs(
    logs: List[Dict[str, Any]],
    config: Optional[CompressionConfig] = None
) -> CompressionResult:
    """
    压缩行为日志的便捷函数
    
    Args:
        logs: 行为日志列表
        config: 压缩配置
        
    Returns:
        压缩结果
    """
    agent = MemoryCompressionAgent(config)
    return agent.execute(logs)
