"""
教学Session API端点
处理Session的创建、查询、消息发送等
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DBSession
from typing import Optional, List
import json
import logging

from app.db.database import get_db
from app.services.session_service import SessionService
from app.schemas.teaching_session import (
    TeachingSessionCreate,
    TeachingSessionUpdate,
    TeachingSessionResponse,
    TeachingSessionDetailResponse,
    SessionListResponse,
    ChatRequest,
    ExplainRequest,
    ExerciseRequest,
    SwitchComponentRequest,
    ChatMessageResponse,
    MessageType
)
from app.api.v1.middleware.response import format_response

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== Session管理端点 ====================

@router.post("", response_model=dict)
def create_or_get_session(
    data: TeachingSessionCreate,
    db: DBSession = Depends(get_db)
):
    """
    获取或创建Session
    如果该用户在该主题下已有active状态的Session，则返回已有Session
    """
    service = SessionService(db)
    session = service.get_or_create_session(
        user_id=data.user_id,
        topic_id=data.topic_id,
        topic_name=data.topic_name
    )
    
    return format_response(data={
        "session_id": session.id,
        "user_id": session.user_id,
        "topic_id": session.topic_id,
        "topic_name": session.topic_name,
        "status": session.status,
        "current_component_id": session.current_component_id,
        "current_component_name": session.current_component_name,
        "learned_components": session.learned_components,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "last_message_at": session.last_message_at.isoformat() if session.last_message_at else None,
    })


@router.get("/check", response_model=dict)
def check_topic_exists(
    user_id: str = Query(..., description="用户ID"),
    topic_name: str = Query(..., description="主题名称"),
    db: DBSession = Depends(get_db)
):
    """
    检查用户是否已有相同主题名称的历史会话

    返回:
    - exists: true/false 是否存在
    - session_id: 存在的session_id（如果exists为true）
    - topic_id: 存在的topic_id（如果exists为true）
    """
    service = SessionService(db)
    session = service.get_session_by_topic_name(user_id, topic_name)

    if session:
        return format_response(data={
            "exists": True,
            "session_id": session.id,
            "topic_id": session.topic_id,
            "topic_name": session.topic_name,
            "last_message_at": session.last_message_at.isoformat() if session.last_message_at else None,
        })
    else:
        return format_response(data={
            "exists": False
        })


@router.get("", response_model=dict)
def list_sessions(
    user_id: str = Query(..., description="用户ID"),
    status: Optional[str] = Query(None, description="Session状态过滤"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: DBSession = Depends(get_db)
):
    """获取用户的Session列表"""
    service = SessionService(db)
    sessions = service.get_user_sessions(user_id, status, skip, limit)

    return format_response(data={
        "total": len(sessions),
        "sessions": [{
            "id": s.id,
            "user_id": s.user_id,
            "topic_id": s.topic_id,
            "topic_name": s.topic_name,
            "status": s.status,
            "current_component_id": s.current_component_id,
            "current_component_name": s.current_component_name,
            "learned_components": s.learned_components,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            "last_message_at": s.last_message_at.isoformat() if s.last_message_at else None,
        } for s in sessions]
    })


@router.get("/{session_id}", response_model=dict)
def get_session(
    session_id: str,
    include_messages: bool = Query(True, description="是否包含消息列表"),
    db: DBSession = Depends(get_db)
):
    """获取Session详情"""
    service = SessionService(db)
    session = service.get_session_by_id(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session不存在")
    
    result = {
        "id": session.id,
        "user_id": session.user_id,
        "topic_id": session.topic_id,
        "topic_name": session.topic_name,
        "status": session.status,
        "total_tokens_used": session.total_tokens_used,
        "context_summary": session.context_summary,
        "current_component_id": session.current_component_id,
        "current_component_name": session.current_component_name,
        "learned_components": session.learned_components,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        "last_message_at": session.last_message_at.isoformat() if session.last_message_at else None,
    }
    
    if include_messages:
        messages = service.get_session_messages(session_id)
        result["messages"] = [msg.to_dict() for msg in messages]
    
    return format_response(data=result)


@router.put("/{session_id}", response_model=dict)
def update_session(
    session_id: str,
    data: TeachingSessionUpdate,
    db: DBSession = Depends(get_db)
):
    """更新Session信息"""
    service = SessionService(db)
    session = service.update_session(session_id, data)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session不存在")
    
    return format_response(data={
        "id": session.id,
        "status": session.status,
        "current_component_id": session.current_component_id,
        "current_component_name": session.current_component_name,
        "learned_components": session.learned_components,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
    })


@router.put("/{session_id}/component", response_model=dict)
def switch_component(
    session_id: str,
    data: SwitchComponentRequest,
    db: DBSession = Depends(get_db)
):
    """切换当前知识组件"""
    service = SessionService(db)
    session = service.switch_component(
        session_id=session_id,
        component_id=data.component_id,
        component_name=data.component_name
    )
    
    if not session:
        raise HTTPException(status_code=404, detail="Session不存在")
    
    return format_response(data={
        "session_id": session.id,
        "current_component_id": session.current_component_id,
        "current_component_name": session.current_component_name,
        "learned_components": session.learned_components,
    })


# ==================== 消息管理端点 ====================

@router.get("/{session_id}/messages", response_model=dict)
def get_messages(
    session_id: str,
    limit: int = Query(50, ge=1, le=200),
    before_id: Optional[str] = Query(None, description="分页游标"),
    db: DBSession = Depends(get_db)
):
    """获取Session的消息列表"""
    service = SessionService(db)
    session = service.get_session_by_id(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session不存在")
    
    messages = service.get_session_messages(session_id, limit, before_id)
    
    return format_response(data={
        "total": len(messages),
        "messages": [msg.to_dict() for msg in messages]
    })


# ==================== 聊天端点 ====================

@router.post("/{session_id}/chat")
async def chat(
    session_id: str,
    request: ChatRequest,
    db: DBSession = Depends(get_db)
):
    """
    发送聊天消息
    支持普通对话、练习题回答等
    """
    from app.agents.llm_providers.agent_adapter import AgentLLMClient
    from app.agents.llm_providers.config import ProviderType
    
    service = SessionService(db)
    session = service.get_session_by_id(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session不存在")
    
    # 保存用户消息
    user_message = service.add_structured_message(
        session_id=session_id,
        role="user",
        message_type=request.message_type.value if request.message_type else MessageType.CHAT.value,
        content=request.content,
        component_id=request.component_id,
        component_name=request.component_name
    )
    
    # 构建上下文
    context_messages = service.get_messages_for_context(session_id)
    
    # 调用LLM生成回复
    llm_client = AgentLLMClient(provider=ProviderType.DOUBAO)
    
    async def generate_response():
        full_content = ""
        try:
            async for chunk in llm_client.generate_stream(
                prompt=request.content,
                system_prompt=context_messages[0]["content"] if context_messages else None,
                max_tokens=4000
            ):
                full_content += chunk
                yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
            
            # 保存AI回复
            service.add_structured_message(
                session_id=session_id,
                role="assistant",
                message_type=MessageType.CHAT.value,
                content=full_content,
                component_id=request.component_id,
                component_name=request.component_name
            )
            
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            logger.error(f"生成回复失败: {e}")
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# ==================== 全景介绍端点 ====================

@router.post("/{session_id}/overview")
async def generate_overview(
    session_id: str,
    db: DBSession = Depends(get_db)
):
    """
    生成主题全景介绍
    模拟用户发送"请介绍{主题}的全景知识"消息
    """
    from app.agents.learning.unified_teaching_agent import UnifiedTeachingAgent
    from app.agents.llm_providers.config import ProviderType
    
    service = SessionService(db)
    session = service.get_session_by_id(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session不存在")
    
    topic_name = session.topic_name
    
    # 添加用户消息（模拟）
    service.add_structured_message(
        session_id=session_id,
        role="user",
        message_type=MessageType.CHAT.value,
        content=f"请介绍 {topic_name} 的全景知识"
    )
    
    agent = UnifiedTeachingAgent(provider=ProviderType.DOUBAO)
    
    async def generate():
        try:
            result = await agent.generate_overview(topic_name)
            
            # 添加AI回复
            service.add_structured_message(
                session_id=session_id,
                role="assistant",
                message_type=MessageType.CHAT.value,
                content=f"## 📚 {topic_name} - 全景介绍\n\n{result}"
            )
            
            yield f"data: {json.dumps({'content': result, 'done': True}, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            logger.error(f"生成全景介绍失败: {e}")
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# ==================== 知识讲解端点 ====================

@router.post("/{session_id}/explain")
async def explain_component(
    session_id: str,
    request: ExplainRequest,
    db: DBSession = Depends(get_db)
):
    """
    获取知识组件讲解
    每次都调用LLM生成，不依赖缓存
    """
    from app.agents.learning.unified_teaching_agent import UnifiedTeachingAgent
    from app.agents.llm_providers.config import ProviderType
    
    service = SessionService(db)
    session = service.get_session_by_id(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session不存在")
    
    # 更新当前组件
    service.switch_component(session_id, request.component_id, request.component_name)
    
    # 添加用户消息（模拟）
    service.add_structured_message(
        session_id=session_id,
        role="user",
        message_type=MessageType.CHAT.value,
        content=f"请讲解 {request.component_name}",
        component_id=request.component_id,
        component_name=request.component_name
    )
    
    # 每次都调用LLM生成
    logger.info(f"生成知识讲解: component_id={request.component_id}, component_name={request.component_name}")
    
    agent = UnifiedTeachingAgent(provider=ProviderType.DOUBAO)
    
    async def generate_explanation():
        try:
            result_data = await agent.explain_knowledge_json(
                knowledge_name=request.component_name,
                topic_name=session.topic_name
            )
            sections = result_data.get("sections", [])
            
            if sections:
                # 保存到缓存
                from app.api.v1.endpoints.knowledge_cache import save_explanation_to_file
                save_explanation_to_file(
                    request.component_id,
                    request.component_name,
                    "",
                    sections=sections
                )
                
                # 保存为AI消息
                content_text = "\n\n".join([
                    f"{s.get('icon', '•')} {s.get('title', '')}\n{s.get('content', '')}"
                    for s in sections
                ])
                
                service.add_structured_message(
                    session_id=session_id,
                    role="assistant",
                    message_type=MessageType.EXPLANATION.value,
                    content=content_text,
                    structured_content=sections,
                    component_id=request.component_id,
                    component_name=request.component_name,
                    metadata={"is_cached": False}
                )
                
                yield f"data: {json.dumps({'sections': sections, 'done': True}, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps({'error': '生成讲解内容为空'}, ensure_ascii=False)}\n\n"
                
        except Exception as e:
            logger.error(f"生成讲解失败: {e}")
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate_explanation(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# ==================== 练习题端点 ====================

@router.post("/{session_id}/exercise")
async def generate_exercise(
    session_id: str,
    request: ExerciseRequest,
    db: DBSession = Depends(get_db)
):
    """
    生成练习题
    在对话中发送练习题题目
    """
    from app.agents.learning.unified_teaching_agent import UnifiedTeachingAgent
    from app.agents.llm_providers.config import ProviderType
    
    service = SessionService(db)
    session = service.get_session_by_id(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session不存在")
    
    # 确定知识组件
    component_id = request.component_id or session.current_component_id
    component_name = session.current_component_name
    
    if not component_id or not component_name:
        raise HTTPException(status_code=400, detail="未指定知识组件")
    
    # 添加用户消息（模拟）
    service.add_structured_message(
        session_id=session_id,
        role="user",
        message_type=MessageType.CHAT.value,
        content=f"请出一道关于 {component_name} 的练习题",
        component_id=component_id,
        component_name=component_name
    )
    
    agent = UnifiedTeachingAgent(provider=ProviderType.DOUBAO)
    
    async def generate():
        try:
            parsed = await agent.generate_exercises(component_name, session.topic_name)
            questions = parsed.get("questions", [])
            
            if questions and len(questions) > 0:
                question = questions[0]
                content = question.get("content", "")
                
                # 保存题目消息
                service.add_structured_message(
                    session_id=session_id,
                    role="assistant",
                    message_type=MessageType.EXERCISE_QUESTION.value,
                    content=f"📚 练习题\n\n{content}",
                    component_id=component_id,
                    component_name=component_name,
                    metadata={"question": question}
                )
                
                yield f"data: {json.dumps({'question': question, 'done': True}, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps({'error': '生成题目失败'}, ensure_ascii=False)}\n\n"
                
        except Exception as e:
            logger.error(f"生成练习题失败: {e}")
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/{session_id}/exercise/submit")
async def submit_exercise_answer(
    session_id: str,
    question_content: str = Body(..., description="题目内容"),
    user_answer: str = Body(..., description="用户答案"),
    component_id: Optional[str] = Body(None, description="知识组件ID"),
    db: DBSession = Depends(get_db)
):
    """
    提交练习题答案并批改
    """
    from app.agents.learning.unified_teaching_agent import UnifiedTeachingAgent
    from app.agents.llm_providers.config import ProviderType
    from app.api.v1.endpoints.knowledge_cache import mark_point_completed, find_topic_id_by_point
    from app.repositories.exercise_repo import get_exercise_repo, ExerciseRecord
    
    service = SessionService(db)
    session = service.get_session_by_id(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session不存在")
    
    # 确定知识组件
    comp_id = component_id or session.current_component_id
    comp_name = session.current_component_name
    
    if not comp_id or not comp_name:
        raise HTTPException(status_code=400, detail="未指定知识组件")
    
    # 保存用户答案消息
    service.add_structured_message(
        session_id=session_id,
        role="user",
        message_type=MessageType.EXERCISE_ANSWER.value,
        content=f"我的答案：\n{user_answer}",
        component_id=comp_id,
        component_name=comp_name
    )
    
    # 调用批改
    agent = UnifiedTeachingAgent(provider=ProviderType.DOUBAO)
    
    try:
        parsed = await agent.grade_answers(
            topic_name=session.topic_name,
            point_name=comp_name,
            question_content=question_content,
            user_answer=user_answer
        )
        
        is_correct = parsed.get("is_correct", False)
        score = 100 if is_correct else 0
        
        # 构建批改反馈
        feedback_content = f"""✅ 批改结果

{parsed.get('feedback', '批改完成')}

{"✅ 回答正确！" if is_correct else "❌ 回答有误"}

{parsed.get('error_analysis', '') if not is_correct else ''}

{"参考答案：" + parsed.get('correct_answer', '') if not is_correct and parsed.get('correct_answer') else ''}
"""
        
        # 保存批改结果消息
        service.add_structured_message(
            session_id=session_id,
            role="assistant",
            message_type=MessageType.EXERCISE_GRADING.value,
            content=feedback_content,
            component_id=comp_id,
            component_name=comp_name,
            metadata={
                "is_correct": is_correct,
                "score": score,
                "exercise_result": parsed
            }
        )
        
        # 记录知识点完成状态
        # 这里简化处理，实际应该通过component_id查找point_id
        # mark_point_completed(topic_id, point_id, score)
        
        # 保存练习记录
        try:
            repo = get_exercise_repo()
            record = ExerciseRecord(
                record_id="",
                user_id=session.user_id,
                component_id=comp_id,
                component_name=comp_name,
                topic_name=session.topic_name,
                point_name=comp_name,
                question_content=question_content,
                user_answer=user_answer,
                correct_answer=parsed.get("correct_answer", ""),
                is_correct=is_correct,
                error_analysis=parsed.get("error_analysis", ""),
                feedback=parsed.get("feedback", "")
            )
            repo.save_record(record)
        except Exception as save_err:
            logger.warning(f"保存练习记录失败: {save_err}")
        
        return format_response(data={
            "is_correct": is_correct,
            "score": score,
            "feedback": parsed.get("feedback", ""),
            "error_analysis": parsed.get("error_analysis", ""),
            "correct_answer": parsed.get("correct_answer", ""),
        })
        
    except Exception as e:
        logger.error(f"批改失败: {e}")
        raise HTTPException(status_code=500, detail=f"批改失败: {str(e)}")
