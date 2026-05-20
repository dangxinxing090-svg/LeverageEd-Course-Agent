"""
教学Session相关的Pydantic模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class MessageType(str, Enum):
    """消息类型枚举"""
    CHAT = "chat"
    EXPLANATION = "explanation"
    EXERCISE_QUESTION = "exercise_question"
    EXERCISE_ANSWER = "exercise_answer"
    EXERCISE_GRADING = "exercise_grading"
    SUMMARY = "summary"


class SessionStatus(str, Enum):
    """Session状态枚举"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    CLOSED = "closed"


class ChatMessageCreate(BaseModel):
    """创建消息请求"""
    role: str = Field(..., description="消息角色: user/assistant/system")
    content: str = Field(..., description="消息内容")
    message_type: MessageType = Field(default=MessageType.CHAT, description="消息类型")
    component_id: Optional[str] = Field(None, description="关联的知识组件ID")
    component_name: Optional[str] = Field(None, description="关联的知识组件名称")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="扩展元数据")


class ChatMessageResponse(BaseModel):
    """消息响应"""
    id: str
    session_id: str
    role: str
    message_type: str
    content: str
    structured_content: Optional[List[Dict[str, Any]]] = None
    tokens_count: int
    component_id: Optional[str] = None
    component_name: Optional[str] = None
    metadata: Dict[str, Any]
    created_at: str
    
    class Config:
        from_attributes = True


class TeachingSessionCreate(BaseModel):
    """创建Session请求"""
    user_id: str = Field(..., description="用户ID")
    topic_id: str = Field(..., description="主题ID")
    topic_name: str = Field(..., description="主题名称")


class TeachingSessionUpdate(BaseModel):
    """更新Session请求"""
    status: Optional[SessionStatus] = None
    current_component_id: Optional[str] = None
    current_component_name: Optional[str] = None
    learned_components: Optional[List[str]] = None
    context_summary: Optional[str] = None


class TeachingSessionResponse(BaseModel):
    """Session响应"""
    id: str
    user_id: str
    topic_id: str
    topic_name: str
    status: str
    total_tokens_used: int
    context_summary: Optional[str] = None
    current_component_id: Optional[str] = None
    current_component_name: Optional[str] = None
    learned_components: List[str]
    created_at: str
    updated_at: str
    last_message_at: str
    
    class Config:
        from_attributes = True


class TeachingSessionDetailResponse(TeachingSessionResponse):
    """Session详情响应（包含消息列表）"""
    messages: List[ChatMessageResponse] = []


class SessionListResponse(BaseModel):
    """Session列表响应"""
    total: int
    sessions: List[TeachingSessionResponse]


class ChatRequest(BaseModel):
    """聊天请求"""
    content: str = Field(..., description="用户输入内容")
    message_type: Optional[MessageType] = Field(default=MessageType.CHAT, description="消息类型")
    component_id: Optional[str] = Field(None, description="当前知识组件ID")
    component_name: Optional[str] = Field(None, description="当前知识组件名称")


class ExplainRequest(BaseModel):
    """知识讲解请求"""
    component_id: str = Field(..., description="知识组件ID")
    component_name: str = Field(..., description="知识组件名称")


class ExerciseRequest(BaseModel):
    """练习题请求"""
    component_id: Optional[str] = Field(None, description="知识组件ID（可选，默认当前组件）")


class SwitchComponentRequest(BaseModel):
    """切换知识组件请求"""
    component_id: str = Field(..., description="知识组件ID")
    component_name: str = Field(..., description="知识组件名称")
