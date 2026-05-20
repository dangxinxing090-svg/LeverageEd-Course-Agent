"""
行为记录模型
存储用户所有学习行为的原始数据
"""
from sqlalchemy import Column, String, DateTime, JSON, Integer, func, Index
from app.db.database import Base


class BehaviorLog(Base):
    """
    行为记录表
    中期记忆：详细记录用户学习过程中的所有行为
    """
    __tablename__ = "behavior_logs"

    log_id = Column(String(64), primary_key=True, index=True, comment="日志ID")
    user_id = Column(String(64), index=True, nullable=False, comment="用户ID")
    session_id = Column(String(64), index=True, comment="会话ID")
    
    # 行为类型：learn/question/practice/skip/interact
    behavior_type = Column(String(32), index=True, nullable=False, comment="行为类型")
    
    # 上下文信息
    topic_id = Column(String(64), index=True, comment="主题ID")
    point_id = Column(String(64), index=True, comment="知识点ID")
    component_id = Column(String(64), index=True, comment="知识组件ID")
    
    # 详细数据（JSON格式，根据行为类型存储不同字段）
    details = Column(JSON, default=dict, comment="详细数据JSON")
    
    # 时间戳
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), comment="行为发生时间")
    
    # 复合索引优化查询
    __table_args__ = (
        Index('idx_behavior_user_time', 'user_id', 'timestamp'),
        Index('idx_behavior_type_time', 'behavior_type', 'timestamp'),
    )

    def __repr__(self):
        return f"<BehaviorLog(user_id={self.user_id}, type={self.behavior_type})>"
