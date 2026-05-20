"""
DKT服务层
封装DKT模型与数据库的交互逻辑
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.core.dkt import DKTModel, DKTState, AnswerRecord
from app.models.behavior import BehaviorLog
from app.models.progress import LearningProgress


class DKTService:
    """
    DKT服务
    
    提供知识状态转移预测、薄弱组件识别、学习路径推荐等功能
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def build_dkt_model(
        self,
        user_id: str,
        topic_id: str = ""
    ) -> DKTModel:
        """
        为用户构建DKT模型
        
        从behavior_logs读取答题历史，注册知识组件，
        重建用户的DKT隐状态
        
        Args:
            user_id: 用户ID
            topic_id: 主题ID（可选，用于限定范围）
            
        Returns:
            构建好的DKTModel
        """
        model = DKTModel()
        
        # 1. 读取答题行为记录
        query = self.db.query(BehaviorLog).filter(
            BehaviorLog.user_id == user_id,
            BehaviorLog.behavior_type == "practice"
        )
        if topic_id:
            query = query.filter(BehaviorLog.topic_id == topic_id)
        
        logs = query.order_by(BehaviorLog.timestamp.asc()).all()
        
        if not logs:
            return model
        
        # 2. 收集所有涉及的知识组件，构建依赖关系
        component_ids = set()
        component_point_map: Dict[str, str] = {}
        
        # 同时读取学习行为来建立组件顺序
        learn_logs = self.db.query(BehaviorLog).filter(
            BehaviorLog.user_id == user_id,
            BehaviorLog.behavior_type == "learn"
        )
        if topic_id:
            learn_logs = learn_logs.filter(BehaviorLog.topic_id == topic_id)
        learn_logs = learn_logs.order_by(BehaviorLog.timestamp.asc()).all()
        
        # 按point_id分组，确定组件顺序
        point_components: Dict[str, List[str]] = {}
        for log in learn_logs:
            cid = log.component_id
            pid = log.point_id
            if cid and pid:
                if pid not in point_components:
                    point_components[pid] = []
                if cid not in point_components[pid]:
                    point_components[pid].append(cid)
                component_ids.add(cid)
                component_point_map[cid] = pid
        
        for log in logs:
            if log.component_id:
                component_ids.add(log.component_id)
                if log.point_id:
                    component_point_map[log.component_id] = log.point_id
        
        # 3. 注册知识组件（带前置依赖）
        # 按point_id排序，构建前置关系
        sorted_points = sorted(point_components.keys())
        point_order = {pid: i for i, pid in enumerate(sorted_points)}
        
        for cid in component_ids:
            pid = component_point_map.get(cid, "")
            prerequisites = []
            related = []
            
            # 前置：同一知识点中排在前面的组件
            if pid and pid in point_components:
                comps = point_components[pid]
                idx = comps.index(cid) if cid in comps else 0
                if idx > 0:
                    prerequisites.append(comps[idx - 1])
                related = [c for c in comps if c != cid]
            
            model.register_component(
                component_id=cid,
                point_id=pid,
                prerequisites=prerequisites,
                related_components=related
            )
        
        # 4. 回放答题序列，重建隐状态
        for log in logs:
            is_correct = (log.details or {}).get("is_correct", False)
            record = AnswerRecord(
                component_id=log.component_id,
                is_correct=is_correct,
                timestamp=int(log.timestamp.timestamp() * 1000) if log.timestamp else 0
            )
            model.update(record)
        
        return model
    
    def get_dkt_predictions(
        self,
        user_id: str,
        topic_id: str = ""
    ) -> Dict[str, Any]:
        """
        获取DKT预测结果
        
        Args:
            user_id: 用户ID
            topic_id: 主题ID
            
        Returns:
            DKT预测结果
        """
        model = self.build_dkt_model(user_id, topic_id)
        
        return {
            "user_id": user_id,
            "topic_id": topic_id,
            "sequence_length": model.state.sequence_length,
            "component_masteries": model.state.component_mastery,
            "predictions": model.predict_all(),
            "weak_components": model.get_weak_components(),
            "recommended_path": model.get_learning_path_recommendation()
        }
    
    def get_weak_components(
        self,
        user_id: str,
        topic_id: str = "",
        threshold: float = 0.5,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        获取薄弱知识组件
        
        Args:
            user_id: 用户ID
            topic_id: 主题ID
            threshold: 掌握度阈值
            limit: 返回数量
            
        Returns:
            薄弱组件列表
        """
        model = self.build_dkt_model(user_id, topic_id)
        return model.get_weak_components(threshold, limit)
    
    def get_learning_path_recommendation(
        self,
        user_id: str,
        topic_id: str = "",
        limit: int = 10
    ) -> List[str]:
        """
        获取学习路径推荐
        
        Args:
            user_id: 用户ID
            topic_id: 主题ID
            limit: 返回数量
            
        Returns:
            推荐的组件ID列表
        """
        model = self.build_dkt_model(user_id, topic_id)
        return model.get_learning_path_recommendation()[:limit]
    
    def get_bkt_dkt_comparison(
        self,
        user_id: str,
        topic_id: str = ""
    ) -> Dict[str, Any]:
        """
        获取BKT与DKT的对比分析
        
        Args:
            user_id: 用户ID
            topic_id: 主题ID
            
        Returns:
            BKT vs DKT对比结果
        """
        from app.services.bkt_service import BKTService
        
        # DKT预测
        dkt_model = self.build_dkt_model(user_id, topic_id)
        dkt_predictions = dkt_model.predict_all()
        
        # BKT数据
        bkt_service = BKTService(self.db)
        progresses = self.db.query(LearningProgress).filter(
            LearningProgress.user_id == user_id
        )
        if topic_id:
            progresses = progresses.filter(LearningProgress.topic_id == topic_id)
        progresses = progresses.all()
        
        comparison = []
        for prog in progresses:
            cid = prog.component_id
            bkt_mastery = prog.bkt_p_known or 0.0
            dkt_mastery = dkt_predictions.get(cid, 0.0)
            
            comparison.append({
                "component_id": cid,
                "point_id": prog.point_id,
                "bkt_mastery": round(bkt_mastery, 3),
                "dkt_mastery": round(dkt_mastery, 3),
                "difference": round(dkt_mastery - bkt_mastery, 3),
                "status": prog.status
            })
        
        return {
            "user_id": user_id,
            "topic_id": topic_id,
            "comparison": comparison,
            "dkt_sequence_length": dkt_model.state.sequence_length,
            "weak_components_dkt": dkt_model.get_weak_components(),
            "recommended_path": dkt_model.get_learning_path_recommendation()
        }
