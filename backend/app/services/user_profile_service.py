"""
用户画像服务层
将行为分析Agent的结果持久化到数据库，并提供查询功能
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.models.user import UserProfile as UserProfileModel
from app.models.behavior import BehaviorLog
from app.agents.behavior.behavior_analysis import (
    BehaviorAnalysisAgent,
    AnalysisReport,
    UserProfile as AgentUserProfile,
    ActivityLevel,
)
from app.services.bkt_service import BKTService


class UserProfileService:
    """
    用户画像服务
    
    将行为分析Agent的分析结果持久化到数据库
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.analysis_agent = BehaviorAnalysisAgent()
    
    def get_or_create_profile(self, user_id: str) -> UserProfileModel:
        """获取或创建用户画像"""
        profile = self.db.query(UserProfileModel).filter(
            UserProfileModel.user_id == user_id
        ).first()
        
        if not profile:
            profile = UserProfileModel(
                user_id=user_id,
                learning_ability_level=3,
                learning_style_tags=[],
                preference_settings={},
                bkt_parameters={}
            )
            self.db.add(profile)
            self.db.commit()
        
        return profile
    
    def analyze_and_update_profile(self, user_id: str) -> Dict[str, Any]:
        """
        分析用户行为数据并更新画像
        
        从behavior_logs读取原始行为数据，
        调用BehaviorAnalysisAgent进行分析，
        将结果持久化到user_profiles表
        
        Args:
            user_id: 用户ID
            
        Returns:
            分析报告摘要
        """
        # 1. 从数据库读取行为日志
        logs = self.db.query(BehaviorLog).filter(
            BehaviorLog.user_id == user_id
        ).order_by(BehaviorLog.timestamp.asc()).limit(10000).all()
        
        if not logs:
            return {
                "user_id": user_id,
                "message": "暂无行为数据",
                "profile": None
            }
        
        # 2. 转换为Agent所需的事件格式
        events = []
        for log in logs:
            event = {
                "user_id": log.user_id,
                "action": self._behavior_type_to_action(log.behavior_type),
                "point_id": log.point_id,
                "component_id": log.component_id,
                "topic_id": log.topic_id,
                "timestamp": log.timestamp.isoformat() if log.timestamp else "",
                "duration_ms": (log.details or {}).get("duration", 0) * 1000 if (log.details or {}).get("duration") else 0,
                "metadata": log.details or {}
            }
            events.append(event)
        
        # 3. 调用行为分析Agent
        report = self.analysis_agent.execute(user_id, events)
        
        # 4. 持久化到数据库
        profile = self.get_or_create_profile(user_id)
        
        # 更新学习能力等级（基于活跃度和掌握度）
        if report.user_profile:
            agent_profile = report.user_profile
            
            # 学习能力等级映射
            ability_map = {
                ActivityLevel.INACTIVE: 1,
                ActivityLevel.LOW: 2,
                ActivityLevel.MEDIUM: 3,
                ActivityLevel.HIGH: 4,
                ActivityLevel.VERY_HIGH: 5,
            }
            profile.learning_ability_level = ability_map.get(
                agent_profile.activity_level, 3
            )
            
            # 学习风格标签
            style_tags = []
            if agent_profile.focus_score >= 70:
                style_tags.append("高专注度")
            elif agent_profile.focus_score < 40:
                style_tags.append("需提升专注")
            
            if agent_profile.consistency_score >= 70:
                style_tags.append("学习稳定")
            elif agent_profile.consistency_score < 40:
                style_tags.append("学习不规律")
            
            if report.exercise_analysis.accuracy_rate >= 0.8:
                style_tags.append("准确率高")
            elif report.exercise_analysis.accuracy_rate < 0.5:
                style_tags.append("需加强练习")
            
            if report.path_analysis.linear_rate >= 0.8:
                style_tags.append("线性学习")
            elif report.path_analysis.skip_count > 3:
                style_tags.append("跳级偏好")
            
            profile.learning_style_tags = style_tags
            
            # 偏好设置
            profile.preference_settings = {
                "peak_hour": report.time_analysis.peak_hour,
                "avg_daily_minutes": report.time_analysis.avg_daily_minutes,
                "focus_score": agent_profile.focus_score,
                "consistency_score": agent_profile.consistency_score,
            }
            
            # 统计信息
            profile.total_learn_time = int(report.time_analysis.total_study_minutes * 60)
            profile.total_exercises = report.exercise_analysis.total_exercises
            profile.correct_exercises = report.exercise_analysis.correct_questions
        
        # 更新已完成组件数
        bkt_service = BKTService(self.db)
        summary = bkt_service.get_user_mastery_summary(user_id)
        profile.completed_components = summary.get("mastered_count", 0)
        
        self.db.commit()
        
        return {
            "user_id": user_id,
            "message": "画像更新成功",
            "report_id": report.report_id,
            "analyzed_event_count": report.analyzed_event_count,
            "profile": {
                "learning_ability_level": profile.learning_ability_level,
                "learning_style_tags": profile.learning_style_tags,
                "total_learn_time": profile.total_learn_time,
                "completed_components": profile.completed_components,
                "total_exercises": profile.total_exercises,
                "correct_exercises": profile.correct_exercises,
            },
            "analysis_summary": {
                "activity_level": report.user_profile.activity_level.value if report.user_profile else None,
                "focus_score": report.user_profile.focus_score if report.user_profile else None,
                "overall_mastery": report.user_profile.overall_mastery if report.user_profile else None,
                "strengths": report.user_profile.strengths if report.user_profile else [],
                "improvements": report.user_profile.improvements if report.user_profile else [],
            }
        }
    
    def get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取用户画像"""
        profile = self.db.query(UserProfileModel).filter(
            UserProfileModel.user_id == user_id
        ).first()
        
        if not profile:
            return None
        
        return {
            "user_id": profile.user_id,
            "learning_ability_level": profile.learning_ability_level,
            "learning_style_tags": profile.learning_style_tags or [],
            "preference_settings": profile.preference_settings or {},
            "bkt_parameters": profile.bkt_parameters or {},
            "total_learn_time": profile.total_learn_time or 0,
            "completed_components": profile.completed_components or 0,
            "total_exercises": profile.total_exercises or 0,
            "correct_exercises": profile.correct_exercises or 0,
            "created_at": profile.created_at.isoformat() if profile.created_at else None,
            "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
        }
    
    def _behavior_type_to_action(self, behavior_type: str) -> str:
        """将behavior_type映射为Agent的action格式"""
        mapping = {
            "learn": "VIEW_EXPLANATION",
            "question": "VIEW_POINT",
            "practice": "SUBMIT_ANSWER",
            "skip": "SKIP_POINT",
            "interact": "VIEW_POINT",
        }
        return mapping.get(behavior_type, "VIEW_POINT")
