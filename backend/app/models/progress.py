"""
学习进度模型
存储知识组件级别的掌握度（BKT计算结果）
"""
from sqlalchemy import Column, String, DateTime, Float, Integer, func, Index
from app.db.database import Base


class LearningProgress(Base):
    """
    学习进度表
    长期记忆：每个知识组件的掌握状态
    """
    __tablename__ = "learning_progress"

    progress_id = Column(String(64), primary_key=True, index=True, comment="进度ID")
    user_id = Column(String(64), index=True, nullable=False, comment="用户ID")
    component_id = Column(String(64), index=True, nullable=False, comment="知识组件ID")
    point_id = Column(String(64), index=True, comment="知识点ID")
    topic_id = Column(String(64), index=True, comment="主题ID")
    
    # 学习状态
    status = Column(String(32), default="not_started", comment="状态: not_started/in_progress/learn_completed/practicing/exercise_passed/mastered")
    
    # BKT掌握概率
    bkt_p_known = Column(Float, default=0.0, comment="掌握概率 P(known)")
    
    # 练习统计
    attempt_count = Column(Integer, default=0, comment="尝试次数")
    correct_count = Column(Integer, default=0, comment="正确次数")
    consecutive_correct = Column(Integer, default=0, comment="连续正确次数")
    
    # 时间记录
    first_attempt_at = Column(DateTime(timezone=True), comment="首次尝试时间")
    last_attempt_at = Column(DateTime(timezone=True), comment="最后尝试时间")
    next_review_at = Column(DateTime(timezone=True), comment="下次复习时间（间隔重复）")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 复合索引
    __table_args__ = (
        Index('idx_progress_user_component', 'user_id', 'component_id', unique=True),
        Index('idx_progress_user_status', 'user_id', 'status'),
    )

    def __repr__(self):
        return f"<LearningProgress(user_id={self.user_id}, component={self.component_id}, p={self.bkt_p_known})>"
