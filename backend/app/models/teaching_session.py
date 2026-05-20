"""
教学Session模型
支持对话式教学，每个主题一个Session
"""
from sqlalchemy import Column, String, DateTime, JSON, Integer, Text, ForeignKey, Index, func
from sqlalchemy.orm import relationship
from app.db.database import Base
from datetime import datetime
import uuid


class TeachingSession(Base):
    """
    教学Session表
    每个知识主题对应一个Session，包含对话历史和学习状态
    """
    __tablename__ = "teaching_sessions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(64), nullable=False, index=True, comment="用户ID")
    topic_id = Column(String(36), nullable=False, index=True, comment="主题ID")
    topic_name = Column(String(256), nullable=False, comment="主题名称")
    
    # Session状态: active(活跃), archived(已归档), closed(已关闭)
    status = Column(String(20), default="active", comment="Session状态")
    
    # Token管理
    total_tokens_used = Column(Integer, default=0, comment="已使用Token总数")
    context_summary = Column(Text, default="", comment="对话上下文摘要")
    summary_updated_at = Column(DateTime, nullable=True, comment="摘要更新时间")
    
    # 当前学习位置
    current_component_id = Column(String(36), nullable=True, comment="当前知识组件ID")
    current_component_name = Column(String(256), nullable=True, comment="当前知识组件名称")
    
    # 学习进度快照
    learned_components = Column(JSON, default=list, comment="已学习组件ID列表")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    last_message_at = Column(DateTime, default=datetime.utcnow, comment="最后消息时间")
    
    # 关联消息
    messages = relationship("ChatMessage", back_populates="session", 
                           order_by="ChatMessage.created_at", cascade="all, delete-orphan")
    
    # 复合索引
    __table_args__ = (
        Index('idx_session_user_topic', 'user_id', 'topic_id', 'status'),
        Index('idx_session_user_active', 'user_id', 'status'),
    )
    
    def __repr__(self):
        return f"<TeachingSession(id={self.id}, topic={self.topic_name}, status={self.status})>"


class ChatMessage(Base):
    """
    聊天消息表
    存储Session中的所有对话消息
    """
    __tablename__ = "chat_messages"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("teaching_sessions.id", ondelete="CASCADE"), 
                       nullable=False, index=True, comment="所属SessionID")
    
    # 消息角色: system(系统), user(用户), assistant(AI助手)
    role = Column(String(20), nullable=False, comment="消息角色")
    
    # 消息类型
    # chat: 普通对话
    # explanation: 知识讲解
    # exercise_question: 练习题题目
    # exercise_answer: 练习题答案
    # exercise_grading: 练习题批改结果
    # summary: 上下文摘要
    message_type = Column(String(32), default="chat", comment="消息类型")
    
    # 消息内容
    content = Column(Text, nullable=False, comment="消息文本内容")
    structured_content = Column(JSON, nullable=True, comment="结构化内容(如讲解的8维度)")
    
    # Token统计
    tokens_count = Column(Integer, default=0, comment="消息Token数")
    
    # 关联信息
    component_id = Column(String(36), nullable=True, comment="关联的知识组件ID")
    component_name = Column(String(256), nullable=True, comment="关联的知识组件名称")
    
    # 扩展元数据（使用meta_data避免与SQLAlchemy保留字冲突）
    meta_data = Column("metadata", JSON, default=dict, comment="扩展信息")
    # meta_data可能包含:
    # - is_cached: 是否来自缓存
    # - exercise_result: 练习题批改结果
    # - is_summarized: 是否已被摘要
    # - original_messages: 被摘要的原始消息ID列表
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    
    # 关联Session
    session = relationship("TeachingSession", back_populates="messages")
    
    # 索引
    __table_args__ = (
        Index('idx_message_session_type', 'session_id', 'message_type'),
        Index('idx_message_session_created', 'session_id', 'created_at'),
        Index('idx_message_component', 'component_id'),
    )
    
    def __repr__(self):
        return f"<ChatMessage(id={self.id}, role={self.role}, type={self.message_type})>"
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "message_type": self.message_type,
            "content": self.content,
            "structured_content": self.structured_content,
            "tokens_count": self.tokens_count,
            "component_id": self.component_id,
            "component_name": self.component_name,
            "metadata": self.meta_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
