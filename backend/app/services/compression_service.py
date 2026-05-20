"""
记忆压缩服务层
封装记忆压缩Agent与数据库的交互逻辑
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta

from app.agents.behavior.memory_compression import (
    MemoryCompressionAgent,
    CompressionConfig,
    CompressionResult,
    DailySummary,
    DataTemperature,
)


class CompressionService:
    """
    记忆压缩服务
    
    提供行为日志的扫描、分类、聚合、归档功能
    """
    
    def __init__(self, db: Session, config: Optional[CompressionConfig] = None):
        self.db = db
        self.config = config or CompressionConfig()
        self.agent = MemoryCompressionAgent(self.config)
    
    def scan_compressible_logs(
        self,
        user_id: Optional[str] = None,
        days_threshold: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        扫描可压缩的行为日志
        
        Args:
            user_id: 用户ID（可选，不传则扫描所有用户）
            days_threshold: 天数阈值（超过此天数的日志可被压缩）
            
        Returns:
            可压缩的日志列表
        """
        from app.models.behavior import BehaviorLog
        
        threshold = days_threshold or self.config.hot_days
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=threshold)
        
        query = self.db.query(BehaviorLog).filter(
            BehaviorLog.timestamp < cutoff_time
        )
        
        if user_id:
            query = query.filter(BehaviorLog.user_id == user_id)
        
        logs = query.order_by(BehaviorLog.timestamp.asc()).limit(10000).all()
        
        return [
            {
                "log_id": log.log_id,
                "user_id": log.user_id,
                "session_id": log.session_id or "",
                "behavior_type": log.behavior_type,
                "topic_id": log.topic_id or "",
                "point_id": log.point_id or "",
                "component_id": log.component_id or "",
                "details": log.details or {},
                "timestamp": log.timestamp,
            }
            for log in logs
        ]
    
    def execute_compression(
        self,
        user_id: Optional[str] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        执行记忆压缩
        
        扫描超过热数据期限的日志，聚合为摘要，归档原始数据
        
        Args:
            user_id: 用户ID（可选）
            dry_run: 试运行模式（不实际删除数据）
            
        Returns:
            压缩结果
        """
        from app.models.behavior import BehaviorLog
        
        # 1. 扫描可压缩日志
        logs = self.scan_compressible_logs(user_id)
        
        if not logs:
            return {
                "message": "没有需要压缩的数据",
                "total_logs_scanned": 0,
            }
        
        # 2. 执行压缩分析
        self.config.dry_run = dry_run
        result = self.agent.execute(logs)
        
        # 3. 生成摘要并保存
        if not dry_run:
            summaries = self.agent.aggregate_daily(logs)
            
            # 将摘要保存到用户画像的preference_settings中
            from app.models.user import UserProfile as UserProfileModel
            
            # 按用户分组摘要
            user_summaries: Dict[str, List[Dict]] = {}
            for summary in summaries:
                uid = summary.user_id
                if uid not in user_summaries:
                    user_summaries[uid] = []
                user_summaries[uid].append(summary.to_dict())
            
            for uid, summaries_list in user_summaries.items():
                profile = self.db.query(UserProfileModel).filter(
                    UserProfileModel.user_id == uid
                ).first()
                
                if profile:
                    prefs = profile.preference_settings or {}
                    # 追加摘要到历史记录
                    if "compression_history" not in prefs:
                        prefs["compression_history"] = []
                    prefs["compression_history"].append({
                        "compressed_at": datetime.now(timezone.utc).isoformat(),
                        "summaries_count": len(summaries_list),
                        "task_id": result.task_id,
                    })
                    # 保留最近10次压缩记录
                    prefs["compression_history"] = prefs["compression_history"][-10:]
                    profile.preference_settings = prefs
            
            # 4. 删除已归档的原始日志（温数据和冷数据）
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=self.config.hot_days)
            delete_query = self.db.query(BehaviorLog).filter(
                BehaviorLog.timestamp < cutoff_time
            )
            if user_id:
                delete_query = delete_query.filter(BehaviorLog.user_id == user_id)
            
            deleted_count = delete_query.delete()
            self.db.commit()
            
            result_dict = result.to_dict()
            result_dict["deleted_logs"] = deleted_count
            result_dict["dry_run"] = False
        else:
            result_dict = result.to_dict()
            result_dict["dry_run"] = True
            result_dict["deleted_logs"] = 0
        
        return result_dict
    
    def get_compression_stats(self) -> Dict[str, Any]:
        """
        获取压缩统计信息
        
        Returns:
            各温度数据量统计
        """
        from app.models.behavior import BehaviorLog
        from sqlalchemy import func
        
        now = datetime.now(timezone.utc)
        hot_cutoff = now - timedelta(days=self.config.hot_days)
        warm_cutoff = now - timedelta(days=self.config.warm_days)
        
        total = self.db.query(func.count(BehaviorLog.log_id)).scalar() or 0
        hot_count = self.db.query(func.count(BehaviorLog.log_id)).filter(
            BehaviorLog.timestamp >= hot_cutoff
        ).scalar() or 0
        warm_count = self.db.query(func.count(BehaviorLog.log_id)).filter(
            BehaviorLog.timestamp >= warm_cutoff,
            BehaviorLog.timestamp < hot_cutoff
        ).scalar() or 0
        cold_count = self.db.query(func.count(BehaviorLog.log_id)).filter(
            BehaviorLog.timestamp < warm_cutoff
        ).scalar() or 0
        
        return {
            "total_logs": total,
            "hot_logs": hot_count,
            "warm_logs": warm_count,
            "cold_logs": cold_count,
            "hot_days": self.config.hot_days,
            "warm_days": self.config.warm_days,
            "compression_candidates": warm_count + cold_count,
            "estimated_compression_rate": round(
                (warm_count + cold_count) / total * 100, 1
            ) if total > 0 else 0,
        }
    
    def get_user_daily_summaries(
        self,
        user_id: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        获取用户每日学习摘要
        
        Args:
            user_id: 用户ID
            days: 查询天数
            
        Returns:
            每日摘要列表
        """
        from app.models.behavior import BehaviorLog
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        logs = self.db.query(BehaviorLog).filter(
            BehaviorLog.user_id == user_id,
            BehaviorLog.timestamp >= cutoff
        ).order_by(BehaviorLog.timestamp.asc()).all()
        
        log_dicts = [
            {
                "user_id": log.user_id,
                "behavior_type": log.behavior_type,
                "topic_id": log.topic_id or "",
                "point_id": log.point_id or "",
                "component_id": log.component_id or "",
                "details": log.details or {},
                "timestamp": log.timestamp,
            }
            for log in logs
        ]
        
        summaries = self.agent.aggregate_daily(log_dicts)
        return [s.to_dict() for s in summaries]
