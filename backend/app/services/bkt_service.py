"""
BKT服务层
封装BKT算法与数据库的交互逻辑
"""
from typing import Optional, List
from sqlalchemy.orm import Session

from app.core.bkt import BKTModel, BKTParams
from app.models.progress import LearningProgress
from app.models.exercise import ExerciseHistory
from app.models.user import UserProfile


class BKTService:
    """
    BKT服务
    
    提供知识掌握度计算、更新、查询等功能
    """
    
    def __init__(self, db: Session):
        """
        初始化BKT服务
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    def get_or_create_progress(
        self,
        user_id: str,
        component_id: str,
        point_id: str = "",
        topic_id: str = ""
    ) -> LearningProgress:
        """
        获取或创建学习进度记录
        
        Args:
            user_id: 用户ID
            component_id: 知识组件ID
            point_id: 知识点ID（可选）
            topic_id: 主题ID（可选）
            
        Returns:
            LearningProgress对象
        """
        progress = self.db.query(LearningProgress).filter(
            LearningProgress.user_id == user_id,
            LearningProgress.component_id == component_id
        ).first()
        
        if not progress:
            import uuid
            progress = LearningProgress(
                progress_id=f"prog-{uuid.uuid4().hex[:16]}",
                user_id=user_id,
                component_id=component_id,
                point_id=point_id,
                topic_id=topic_id,
                status="not_started",
                bkt_p_known=0.0,
                attempt_count=0,
                correct_count=0,
                consecutive_correct=0
            )
            self.db.add(progress)
            self.db.commit()
        
        return progress
    
    def update_progress_after_attempt(
        self,
        user_id: str,
        component_id: str,
        is_correct: bool,
        point_id: str = "",
        topic_id: str = ""
    ) -> dict:
        """
        答题后更新学习进度
        
        Args:
            user_id: 用户ID
            component_id: 知识组件ID
            is_correct: 是否答对
            point_id: 知识点ID（可选）
            topic_id: 主题ID（可选）
            
        Returns:
            更新后的进度信息
        """
        # 获取或创建进度记录
        progress = self.get_or_create_progress(
            user_id, component_id, point_id, topic_id
        )
        
        # 获取用户BKT参数
        user_profile = self.db.query(UserProfile).filter(
            UserProfile.user_id == user_id
        ).first()
        
        # 构建BKT参数
        if user_profile and component_id in (user_profile.bkt_parameters or {}):
            params_dict = user_profile.bkt_parameters[component_id]
            params = BKTParams(
                p_init=params_dict.get('p_init', 0.3),
                p_transit=params_dict.get('p_transit', 0.1),
                p_slip=params_dict.get('p_slip', 0.1),
                p_guess=params_dict.get('p_guess', 0.2)
            )
        else:
            params = BKTModel.DEFAULT_PARAMS
        
        # 创建BKT模型并设置当前状态
        model = BKTModel(params)
        model.state.p_known = progress.bkt_p_known or params.p_init
        
        # 更新BKT状态
        new_p_known = model.update(is_correct)
        
        # 更新进度记录
        progress.bkt_p_known = new_p_known
        progress.attempt_count = (progress.attempt_count or 0) + 1
        if is_correct:
            progress.correct_count = (progress.correct_count or 0) + 1
            progress.consecutive_correct = (progress.consecutive_correct or 0) + 1
        else:
            progress.consecutive_correct = 0
        
        # 更新状态
        if new_p_known >= BKTModel.MASTERY_THRESHOLD:
            progress.status = "mastered"
        elif progress.attempt_count > 0:
            progress.status = "learning"
        
        # 更新首次/最后尝试时间
        from datetime import datetime
        if not progress.first_attempt_at:
            progress.first_attempt_at = datetime.utcnow()
        progress.last_attempt_at = datetime.utcnow()
        
        self.db.commit()
        
        return {
            "progress_id": progress.progress_id,
            "component_id": component_id,
            "bkt_p_known": new_p_known,
            "is_mastered": model.is_mastered(),
            "mastery_level": model.get_mastery_level(),
            "status": progress.status,
            "attempt_count": progress.attempt_count,
            "correct_count": progress.correct_count
        }
    
    def get_component_mastery(self, user_id: str, component_id: str) -> Optional[dict]:
        """
        获取知识组件掌握度
        
        Args:
            user_id: 用户ID
            component_id: 知识组件ID
            
        Returns:
            掌握度信息，如果不存在返回None
        """
        progress = self.db.query(LearningProgress).filter(
            LearningProgress.user_id == user_id,
            LearningProgress.component_id == component_id
        ).first()
        
        if not progress:
            return None
        
        model = BKTModel()
        model.state.p_known = progress.bkt_p_known or 0.0
        
        return {
            "component_id": component_id,
            "bkt_p_known": progress.bkt_p_known or 0.0,
            "is_mastered": model.is_mastered(),
            "mastery_level": model.get_mastery_level(),
            "status": progress.status,
            "attempt_count": progress.attempt_count or 0,
            "correct_count": progress.correct_count or 0
        }
    
    def get_user_mastery_summary(self, user_id: str) -> dict:
        """
        获取用户掌握度汇总
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户掌握度汇总信息
        """
        progresses = self.db.query(LearningProgress).filter(
            LearningProgress.user_id == user_id
        ).all()
        
        total = len(progresses)
        mastered = sum(1 for p in progresses if p.status == "mastered")
        learning = sum(1 for p in progresses if p.status == "learning")
        not_started = sum(1 for p in progresses if p.status == "not_started")
        
        avg_p_known = sum(p.bkt_p_known or 0 for p in progresses) / total if total > 0 else 0
        
        return {
            "user_id": user_id,
            "total_components": total,
            "mastered_count": mastered,
            "learning_count": learning,
            "not_started_count": not_started,
            "average_mastery": avg_p_known,
            "mastered_percentage": (mastered / total * 100) if total > 0 else 0
        }
    
    def get_recommended_components(
        self,
        user_id: str,
        topic_id: str,
        limit: int = 5
    ) -> List[dict]:
        """
        获取推荐学习的知识组件
        
        推荐策略：
        1. 优先推荐正在学习但未掌握的组件
        2. 其次推荐未开始的组件
        3. 最后推荐已掌握但需要复习的组件
        
        Args:
            user_id: 用户ID
            topic_id: 主题ID
            limit: 返回数量限制
            
        Returns:
            推荐组件列表
        """
        from sqlalchemy import or_
        
        # 获取该主题下的所有进度
        progresses = self.db.query(LearningProgress).filter(
            LearningProgress.user_id == user_id,
            LearningProgress.topic_id == topic_id
        ).all()
        
        # 分类
        learning_components = []
        not_started_components = []
        mastered_components = []
        
        for p in progresses:
            component_info = {
                "component_id": p.component_id,
                "point_id": p.point_id,
                "bkt_p_known": p.bkt_p_known or 0.0,
                "status": p.status
            }
            
            if p.status == "learning":
                learning_components.append(component_info)
            elif p.status == "not_started":
                not_started_components.append(component_info)
            elif p.status == "mastered":
                mastered_components.append(component_info)
        
        # 排序：学习中的按掌握度升序（优先掌握度低的）
        learning_components.sort(key=lambda x: x["bkt_p_known"])
        
        # 合并结果
        recommended = learning_components + not_started_components + mastered_components
        
        return recommended[:limit]
