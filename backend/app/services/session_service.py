"""
教学Session服务层
处理Session的创建、查询、更新等逻辑
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import desc
import logging

from app.models.teaching_session import TeachingSession, ChatMessage
from app.schemas.teaching_session import (
    TeachingSessionCreate,
    TeachingSessionUpdate,
    ChatMessageCreate,
    SessionStatus,
    MessageType
)

logger = logging.getLogger(__name__)


class SessionService:
    """Session服务类"""
    
    def __init__(self, db: DBSession):
        self.db = db
    
    # ==================== Session管理 ====================
    
    def get_or_create_session(
        self, 
        user_id: str, 
        topic_id: str, 
        topic_name: str
    ) -> TeachingSession:
        """
        获取或创建Session
        如果该用户在该主题下已有active状态的Session，则返回已有Session
        否则创建新的Session
        """
        # 查找现有的active Session
        existing_session = self.db.query(TeachingSession).filter(
            TeachingSession.user_id == user_id,
            TeachingSession.topic_id == topic_id,
            TeachingSession.status == SessionStatus.ACTIVE.value
        ).first()
        
        if existing_session:
            logger.info(f"找到现有Session: {existing_session.id}, topic={topic_name}")
            return existing_session
        
        # 创建新Session
        new_session = TeachingSession(
            user_id=user_id,
            topic_id=topic_id,
            topic_name=topic_name,
            status=SessionStatus.ACTIVE.value,
            learned_components=[]
        )
        self.db.add(new_session)
        self.db.commit()
        self.db.refresh(new_session)
        
        logger.info(f"创建新Session: {new_session.id}, topic={topic_name}")
        return new_session
    
    def get_session_by_id(self, session_id: str) -> Optional[TeachingSession]:
        """根据ID获取Session"""
        return self.db.query(TeachingSession).filter(
            TeachingSession.id == session_id
        ).first()
    
    def get_user_sessions(
        self, 
        user_id: str, 
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[TeachingSession]:
        """获取用户的Session列表"""
        query = self.db.query(TeachingSession).filter(
            TeachingSession.user_id == user_id
        )
        
        if status:
            query = query.filter(TeachingSession.status == status)
        
        return query.order_by(desc(TeachingSession.last_message_at)).offset(skip).limit(limit).all()
    
    def update_session(
        self, 
        session_id: str, 
        update_data: TeachingSessionUpdate
    ) -> Optional[TeachingSession]:
        """更新Session信息"""
        session = self.get_session_by_id(session_id)
        if not session:
            return None
        
        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(session, key, value)
        
        session.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(session)
        
        return session
    
    def switch_component(
        self,
        session_id: str,
        component_id: str,
        component_name: str
    ) -> Optional[TeachingSession]:
        """切换当前知识组件"""
        session = self.get_session_by_id(session_id)
        if not session:
            return None
        
        session.current_component_id = component_id
        session.current_component_name = component_name
        
        # 如果是新学习的组件，添加到已学习列表
        if component_id not in session.learned_components:
            session.learned_components.append(component_id)
        
        session.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(session)
        
        return session
    
    def add_tokens_used(self, session_id: str, tokens: int):
        """增加Session的Token使用量"""
        session = self.get_session_by_id(session_id)
        if session:
            session.total_tokens_used += tokens
            self.db.commit()
    
    def update_context_summary(self, session_id: str, summary: str):
        """更新上下文摘要"""
        session = self.get_session_by_id(session_id)
        if session:
            session.context_summary = summary
            session.summary_updated_at = datetime.utcnow()
            self.db.commit()
    
    # ==================== 消息管理 ====================
    
    def add_message(
        self,
        session_id: str,
        message_data: ChatMessageCreate
    ) -> ChatMessage:
        """添加消息到Session"""
        message = ChatMessage(
            session_id=session_id,
            role=message_data.role,
            message_type=message_data.message_type.value if isinstance(message_data.message_type, MessageType) else message_data.message_type,
            content=message_data.content,
            component_id=message_data.component_id,
            component_name=message_data.component_name,
            meta_data=message_data.metadata or {}
        )
        
        self.db.add(message)
        
        # 更新Session的最后消息时间
        session = self.get_session_by_id(session_id)
        if session:
            session.last_message_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(message)
        
        return message
    
    def add_structured_message(
        self,
        session_id: str,
        role: str,
        message_type: str,
        content: str,
        structured_content: Optional[List[Dict[str, Any]]] = None,
        component_id: Optional[str] = None,
        component_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ChatMessage:
        """添加结构化消息（便捷方法）"""
        message = ChatMessage(
            session_id=session_id,
            role=role,
            message_type=message_type,
            content=content,
            structured_content=structured_content,
            component_id=component_id,
            component_name=component_name,
            meta_data=metadata or {}
        )
        
        self.db.add(message)
        
        session = self.get_session_by_id(session_id)
        if session:
            session.last_message_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(message)
        
        return message
    
    def get_session_messages(
        self,
        session_id: str,
        limit: int = 100,
        before_id: Optional[str] = None
    ) -> List[ChatMessage]:
        """获取Session的消息列表"""
        query = self.db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        )
        
        if before_id:
            before_message = self.db.query(ChatMessage).filter(
                ChatMessage.id == before_id
            ).first()
            if before_message:
                query = query.filter(ChatMessage.created_at < before_message.created_at)
        
        return query.order_by(ChatMessage.created_at.desc()).limit(limit).all()[::-1]
    
    def get_recent_messages(
        self,
        session_id: str,
        limit: int = 20
    ) -> List[ChatMessage]:
        """获取最近的消息（用于构建上下文）"""
        messages = self.db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(desc(ChatMessage.created_at)).limit(limit).all()
        
        return messages[::-1]  # 按时间正序返回
    
    def get_messages_for_context(
        self,
        session_id: str,
        max_tokens: int = 6000
    ) -> List[Dict[str, str]]:
        """
        获取用于LLM上下文的消息列表
        包含：系统提示 + 上下文摘要 + 近期消息
        """
        session = self.get_session_by_id(session_id)
        if not session:
            return []
        
        context_messages = []
        
        # 1. 添加系统提示
        system_content = self._build_system_prompt(session)
        context_messages.append({"role": "system", "content": system_content})
        
        # 2. 添加上下文摘要（如果有）
        if session.context_summary:
            summary_content = f"【前文摘要】{session.context_summary}"
            context_messages.append({"role": "system", "content": summary_content})
        
        # 3. 添加近期消息（排除system消息）
        recent_messages = self.get_recent_messages(session_id, limit=20)
        for msg in recent_messages:
            if msg.role != "system":
                context_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
        
        return context_messages
    
    def _build_system_prompt(self, session: TeachingSession) -> str:
        """构建系统提示"""
        prompt = f"""你是一位专业的教学助手，正在帮助用户学习【{session.topic_name}】。

当前学习主题：{session.topic_name}
"""
        if session.current_component_name:
            prompt += f"当前知识组件：{session.current_component_name}\n"
        
        if session.learned_components:
            prompt += f"已学习组件数：{len(session.learned_components)}\n"
        
        prompt += """
请根据上下文提供有帮助的回答，可以：
1. 回答用户的问题
2. 解释知识点
3. 出练习题并批改
4. 引导学习路径

保持友好、专业的教学态度。"""
        
        return prompt
    
    def mark_messages_summarized(
        self,
        session_id: str,
        message_ids: List[str],
        summary_message_id: str
    ):
        """标记消息已被摘要"""
        for msg_id in message_ids:
            message = self.db.query(ChatMessage).filter(
                ChatMessage.id == msg_id
            ).first()
            if message:
                if "is_summarized" not in message.meta_data:
                    message.meta_data["is_summarized"] = True
                if "summarized_by" not in message.meta_data:
                    message.meta_data["summarized_by"] = summary_message_id
                
        self.db.commit()
