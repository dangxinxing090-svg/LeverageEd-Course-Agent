"""
用户画像模型
存储用户长期记忆：学习能力、学习风格、偏好设置、BKT参数
"""
from sqlalchemy import Column, String, DateTime, JSON, Integer, Float, func
from app.db.database import Base


class UserProfile(Base):
    """
    用户画像表
    长期记忆的核心存储
    """
    __tablename__ = "user_profiles"

    user_id = Column(String(64), primary_key=True, index=True, comment="用户ID")
    
    # 学习能力评估
    learning_ability_level = Column(Integer, default=3, comment="学习能力等级 1-5")
    
    # 学习风格标签（数组存储）
    learning_style_tags = Column(JSON, default=list, comment="学习风格标签列表")
    
    # 偏好设置
    preference_settings = Column(JSON, default=dict, comment="偏好设置JSON")
    
    # BKT参数（按知识组件存储）
    bkt_parameters = Column(JSON, default=dict, comment="BKT参数 {component_id: {p_init, p_transit, p_slip, p_guess}}")
    
    # 统计信息
    total_learn_time = Column(Integer, default=0, comment="总学习时长（秒）")
    completed_components = Column(Integer, default=0, comment="已完成知识组件数")
    total_exercises = Column(Integer, default=0, comment="总练习题数")
    correct_exercises = Column(Integer, default=0, comment="正确练习题数")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间")

    def __repr__(self):
        return f"<UserProfile(user_id={self.user_id}, level={self.learning_ability_level})>"
