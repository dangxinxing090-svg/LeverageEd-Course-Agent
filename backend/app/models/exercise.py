"""
练习题历史模型
存储用户每次答题的详细记录
"""
from sqlalchemy import Column, String, DateTime, JSON, Integer, Boolean, Float, func, Index
from app.db.database import Base


class ExerciseHistory(Base):
    """
    练习题历史表
    长期记忆：每次答题的详细记录，用于BKT/DKT计算
    """
    __tablename__ = "exercise_history"

    history_id = Column(String(64), primary_key=True, index=True, comment="记录ID")
    user_id = Column(String(64), index=True, nullable=False, comment="用户ID")
    question_id = Column(String(64), index=True, comment="题目ID")
    component_id = Column(String(64), index=True, comment="知识组件ID")
    point_id = Column(String(64), index=True, comment="知识点ID")
    
    # 答题内容
    user_answer = Column(String(2000), comment="用户答案")
    is_correct = Column(Boolean, comment="是否正确")
    error_type = Column(String(64), comment="错误类型: syntax_error/logic_error/concept_error")
    
    # 答题过程
    time_spent = Column(Integer, comment="耗时（秒）")
    hint_used = Column(Boolean, default=False, comment="是否使用提示")
    attempt_number = Column(Integer, default=1, comment="第几次尝试")
    
    # 修改记录
    answer_versions = Column(JSON, default=list, comment="答案修改历史")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="答题时间")
    
    # 复合索引
    __table_args__ = (
        Index('idx_exercise_user_component', 'user_id', 'component_id'),
        Index('idx_exercise_user_time', 'user_id', 'created_at'),
    )

    def __repr__(self):
        return f"<ExerciseHistory(user_id={self.user_id}, correct={self.is_correct})>"
