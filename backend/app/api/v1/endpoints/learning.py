"""
Learning 端点

提供学习相关的API接口
"""

import logging
import time
import json
import re
from typing import Optional, List

from fastapi import APIRouter, Query, Body
from fastapi.responses import StreamingResponse

from app.api.v1.middleware.response import format_response, ResponseFormatter
from app.agents.learning.unified_teaching_agent import UnifiedTeachingAgent
from app.agents.llm_providers.config import ProviderType
from app.api.v1.endpoints.knowledge_cache import find_component_info

logger = logging.getLogger(__name__)

router = APIRouter()


# 统一教学Agent实例（单例模式）
_teaching_agent = None

def get_teaching_agent() -> UnifiedTeachingAgent:
    """获取统一教学Agent实例"""
    global _teaching_agent
    if _teaching_agent is None:
        _teaching_agent = UnifiedTeachingAgent(provider=ProviderType.DOUBAO)
    return _teaching_agent


@router.post("/qa/ask")
async def ask_question(
    question: str = Body(..., description="问题内容"),
    point_id: str = Body(..., description="当前知识点ID"),
    user_id: str = Body(..., description="用户ID")
):
    """
    提问

    - **question**: 问题内容
    - **point_id**: 当前知识点ID
    - **user_id**: 用户ID
    """
    try:
        agent = get_teaching_agent()
        answer = await agent.answer_question(question)

        logger.info(f"问答成功: question={question[:50]}")

        return format_response(data={
            "answer": answer,
            "related_points": [point_id],
            "confidence": 0.8,
            "suggested_questions": []
        })
    except Exception as e:
        logger.error(f"问答失败: {e}", exc_info=True)
        return format_response(message=f"问答失败: {str(e)}", data=None)


@router.get("/knowledge/components/{component_id}/explanation")
async def get_explanation(
    component_id: str,
    user_level: Optional[str] = Query("BEGINNER", description="用户级别")
):
    """
    获取知识点讲解

    - **component_id**: 组件ID
    - **user_level**: 用户级别 (BEGINNER/INTERMEDIATE/ADVANCED)
    """
    try:
        # 查找组件的真实名称
        comp_info = find_component_info(component_id)
        knowledge_name = comp_info["component_name"] if comp_info else component_id

        agent = get_teaching_agent()
        result_text = await agent.explain_knowledge(knowledge_name)

        # 将LLM响应转换为HTML：按段落分割，用<p>包裹，换行用<br>
        paragraphs = result_text.strip().split("\n\n")
        html_parts = []
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            # 将单行换行转为<br>
            para_html = para.replace("\n", "<br>")
            html_parts.append(f"<p>{para_html}</p>")
        html_content = "\n".join(html_parts)

        logger.info(f"知识点讲解成功: component_id={component_id}, knowledge_name={knowledge_name}")

        return format_response(data={
            "component_id": component_id,
            "content": html_content,
            "teaching_method": "向导式教学"
        })
    except Exception as e:
        logger.error(f"知识点讲解失败: {e}", exc_info=True)
        return format_response(message=f"知识点讲解失败: {str(e)}", data=None)


@router.get("/knowledge/components/{component_id}/explanation/stream")
async def get_explanation_stream(
    component_id: str,
    user_level: Optional[str] = Query("BEGINNER", description="用户级别")
):
    """
    流式获取知识点讲解 (SSE)
    """
    # 查找组件的真实名称
    comp_info = find_component_info(component_id)
    knowledge_name = comp_info["component_name"] if comp_info else component_id

    async def event_generator():
        try:
            agent = get_teaching_agent()
            async for chunk in agent.explain_knowledge_stream(knowledge_name):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"流式讲解失败: {e}")
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/qa/ask/stream")
async def ask_question_stream(
    question: str = Body(..., description="问题内容"),
    point_id: str = Body(..., description="当前知识点ID"),
    user_id: str = Body(..., description="用户ID")
):
    """
    流式提问 (SSE)
    """
    async def event_generator():
        try:
            agent = get_teaching_agent()
            async for chunk in agent.answer_question_stream(question):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"流式问答失败: {e}")
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/exercises/generate")
async def generate_exercises(
    point_id: str = Query(..., description="知识点ID"),
    total_questions: int = Query(1, ge=1, le=1, description="题目数量（每次固定出1道）")
):
    """生成练习题（每次出一道高难度实操性问答题）"""
    comp_info = find_component_info(point_id)
    knowledge_name = comp_info["point_name"] if comp_info else point_id
    block_name = comp_info["block_name"] if comp_info else ""

    try:
        agent = get_teaching_agent()
        parsed = await agent.generate_exercises(knowledge_name, block_name)
        questions = parsed.get("questions", [])
        # Ensure IDs and fields
        for i, q in enumerate(questions):
            q.setdefault("id", f"q-{i+1}")
            q.setdefault("type", "practical_qa")
            q.setdefault("difficulty", "hard")
            q.setdefault("category", "方案设计")
            q.setdefault("hints", [])
            q.setdefault("key_points", [])
            q.setdefault("reference_answer", "")
        return format_response(data={"questions": questions})
    except Exception as e:
        logger.error(f"练习题生成失败: {e}", exc_info=True)
        return format_response(message=f"练习题生成失败: {str(e)}", data=None)


@router.post("/exercises/submit")
async def submit_exercises(
    point_id: str = Body(..., description="知识点ID"),
    answers: List[dict] = Body(..., description="答案列表")
):
    """提交练习答案"""
    comp_info = find_component_info(point_id)
    knowledge_name = comp_info["point_name"] if comp_info else point_id

    answers_text = "\n".join([f"第{i+1}题：用户选择 {a.get('answer', '未作答')}" for i, a in enumerate(answers)])

    try:
        agent = get_teaching_agent()
        parsed = await agent.grade_answers(knowledge_name, answers_text)
        return format_response(data={
            "score": parsed.get("total_score", 0),
            "totalCount": parsed.get("total_count", len(answers)),
            "correctCount": parsed.get("correct_count", 0),
            "feedback": parsed.get("feedback", "批改完成")
        })
    except Exception as e:
        logger.error(f"答案批改失败: {e}", exc_info=True)
        return format_response(message=f"答案批改失败: {str(e)}", data=None)


# ============================================
# 跳级测试相关端点
# ============================================

@router.post("/skip/test")
async def create_skip_test(
    user_id: str = Body(..., description="用户ID"),
    topic_id: str = Body(..., description="主题ID"),
    target_point_id: Optional[str] = Body(None, description="目标知识点ID")
):
    """创建跳级测试"""
    target_info = find_component_info(target_point_id) if target_point_id else None
    target_name = target_info["point_name"] if target_info else "下一阶段知识"

    test_prompt = f"""请为跳级测试生成5道综合性选择题，用于判断学生是否可以跳过当前阶段直接学习：{target_name}

要求：
1. 题目覆盖该阶段的核心知识点
2. 难度中等偏上，能区分是否已掌握
3. 每题4个选项，只有一个正确答案
4. 附带正确答案

请严格按以下JSON格式输出（只输出JSON）：
{{
  "questions": [
    {{
      "question_id": "sq-1",
      "question_type": "single_choice",
      "content": "题目内容",
      "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
      "correct_answer": "A"
    }}
  ]
}}"""

    try:
        llm_client = AgentLLMClient(provider=ProviderType.DOUBAO)
        result_text = await llm_client.generate(
            test_prompt,
            system_prompt="你是一位专业的教育评估专家，擅长设计跳级测试题。",
            max_tokens=3000
        )
        parsed = _parse_json_from_llm_response(result_text)
        questions = parsed.get("questions", [])
        for i, q in enumerate(questions):
            q.setdefault("question_id", f"sq-{i+1}")
            q.setdefault("question_type", "single_choice")
        return format_response(data={
            "test_id": f"skip-test-{int(time.time())}",
            "questions": questions,
            "time_limit": 300
        })
    except Exception as e:
        logger.error(f"跳级测试生成失败: {e}", exc_info=True)
        return format_response(message=f"跳级测试生成失败: {str(e)}", data=None)


@router.post("/skip/test/submit")
async def submit_skip_test(
    test_id: str = Body(..., description="测试ID"),
    user_id: str = Body(..., description="用户ID"),
    answers: List[dict] = Body(..., description="答案列表")
):
    """提交跳级测试"""
    answers_text = "\n".join([f"第{i+1}题：用户选择 {a.get('answer', '未作答')}" for i, a in enumerate(answers)])

    eval_prompt = f"""你是一位专业的教育评估专家，请评估学生的跳级测试结果。

学生答案：
{answers_text}

请按以下JSON格式输出评估结果（只输出JSON）：
{{
  "passed": true,
  "score": 80,
  "total_questions": 5,
  "correct_count": 4,
  "feedback": "评估反馈"
}}"""

    try:
        llm_client = AgentLLMClient(provider=ProviderType.DOUBAO)
        result_text = await llm_client.generate(
            eval_prompt,
            system_prompt="你是一位专业的教育评估专家。",
            max_tokens=1000
        )
        parsed = _parse_json_from_llm_response(result_text)
        return format_response(data={
            "passed": parsed.get("passed", False),
            "score": parsed.get("score", 0),
            "total_questions": parsed.get("total_questions", len(answers)),
            "correct_count": parsed.get("correct_count", 0),
            "skip_to_point_id": "next-point" if parsed.get("passed") else None,
            "feedback": parsed.get("feedback", "评估完成")
        })
    except Exception as e:
        logger.error(f"跳级测试评估失败: {e}", exc_info=True)
        return format_response(message=f"跳级测试评估失败: {str(e)}", data=None)
