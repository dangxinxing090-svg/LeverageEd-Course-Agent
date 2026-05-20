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
from app.agents.llm_providers.agent_adapter import AgentLLMClient
from app.api.v1.endpoints.knowledge_cache import find_component_info, mark_point_completed, find_topic_id_by_point, load_explanation_from_file, save_explanation_to_file
from app.repositories.exercise_repo import get_exercise_repo, ExerciseRecord

logger = logging.getLogger(__name__)

router = APIRouter()


def _parse_json_from_llm_response(text: str) -> dict:
    """从LLM响应中解析JSON"""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 尝试从代码块中提取
    code_block = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
    if code_block:
        try:
            return json.loads(code_block.group(1))
        except json.JSONDecodeError:
            pass
    # 尝试从文本中提取JSON对象
    start = text.find('{')
    end = text.rfind('}')
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    raise ValueError(f"无法从LLM响应中解析JSON: {text[:200]}")


# 统一教学Agent实例（单例模式）
_teaching_agent = None

def get_teaching_agent() -> UnifiedTeachingAgent:
    """获取统一教学Agent实例"""
    global _teaching_agent
    if _teaching_agent is None:
        _teaching_agent = UnifiedTeachingAgent(provider=ProviderType.DOUBAO)
    return _teaching_agent


@router.get("/knowledge/components/{component_id}/explanation")
async def get_explanation(
    component_id: str,
    user_level: Optional[str] = Query("BEGINNER", description="用户级别")
):
    """
    获取知识点讲解（结构化JSON格式，8维度卡片展示）

    - **component_id**: 组件ID
    - **user_level**: 用户级别 (BEGINNER/INTERMEDIATE/ADVANCED)
    """
    try:
        # 查找组件的真实名称及所属知识体系上下文
        comp_info = find_component_info(component_id)
        knowledge_name = comp_info["component_name"] if comp_info else component_id
        topic_name = comp_info.get("topic_name", "") if comp_info else ""

        # 检查是否有已保存的结构化讲解缓存
        cached = load_explanation_from_file(component_id)
        if cached and cached.get("sections"):
            sections = cached["sections"]
            logger.info(f"知识点讲解命中缓存(结构化): component_id={component_id}")
        elif cached and cached.get("content"):
            # 旧格式缓存（纯文本），重新生成结构化版本
            agent = get_teaching_agent()
            result_data = await agent.explain_knowledge_json(knowledge_name, topic_name=topic_name)
            sections = result_data.get("sections", [])
            if sections:
                save_explanation_to_file(component_id, knowledge_name, "", sections=sections)
            logger.info(f"旧缓存格式，重新生成结构化讲解: component_id={component_id}")
        else:
            agent = get_teaching_agent()
            result_data = await agent.explain_knowledge_json(knowledge_name, topic_name=topic_name)
            sections = result_data.get("sections", [])
            if sections:
                save_explanation_to_file(component_id, knowledge_name, "", sections=sections)

        logger.info(f"知识点讲解成功(结构化): component_id={component_id}, knowledge_name={knowledge_name}, topic_name={topic_name}")

        return format_response(data={
            "component_id": component_id,
            "sections": sections if isinstance(sections, list) else [],
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

    优先从文件缓存加载，缓存命中则模拟流式输出；
    未命中则调用LLM，生成完成后保存到文件。
    """
    # 查找组件的真实名称
    comp_info = find_component_info(component_id)
    knowledge_name = comp_info["component_name"] if comp_info else component_id

    # 检查是否有已保存的讲解
    cached = load_explanation_from_file(component_id)
    if cached and cached.get("content"):
        # 缓存命中：将已保存的完整文本模拟为SSE流式输出
        cached_content = cached["content"]

        async def cached_event_generator():
            try:
                # 将缓存内容按小段发送，模拟流式效果
                chunk_size = 20
                for i in range(0, len(cached_content), chunk_size):
                    chunk = cached_content[i:i + chunk_size]
                    yield f"data: {chunk}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error(f"缓存讲解流式输出失败: {e}")
                yield f"data: [ERROR] {str(e)}\n\n"

        logger.info(f"知识点讲解命中缓存: component_id={component_id}, knowledge_name={knowledge_name}")
        return StreamingResponse(
            cached_event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )

    # 缓存未命中：调用LLM
    async def event_generator():
        try:
            agent = get_teaching_agent()
            full_content = ""
            async for chunk in agent.explain_knowledge_stream(knowledge_name):
                full_content += chunk
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
            # LLM生成完成后保存到文件
            if full_content.strip():
                save_explanation_to_file(component_id, knowledge_name, full_content)
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


@router.get("/exercises/generate")
async def generate_exercises(
    component_id: str = Query(..., description="知识组件ID"),
    total_questions: int = Query(1, ge=1, le=1, description="题目数量（每次固定出1道）")
):
    """生成练习题（每次出一道中等难度实操性问答题）"""
    comp_info = find_component_info(component_id)
    component_name = comp_info["component_name"] if comp_info else component_id
    topic_name = comp_info.get("topic_name", "") if comp_info else ""

    try:
        agent = get_teaching_agent()
        parsed = await agent.generate_exercises(component_name, topic_name)
        questions = parsed.get("questions", [])
        # Ensure IDs and fields, map field names for frontend compatibility
        for i, q in enumerate(questions):
            q.setdefault("id", f"q-{i+1}")
            q.setdefault("type", "FILL_BLANK")  # 前端使用FILL_BLANK类型来处理问答题
            q.setdefault("difficulty", "MEDIUM")
            q.setdefault("category", "方案设计")
            q.setdefault("hints", [])
            q.setdefault("key_points", [])
            q.setdefault("reference_answer", "")
            # Field name mapping: ensure 'content' field exists for frontend
            if "content" not in q and "question_text" in q:
                q["content"] = q.pop("question_text")
            elif "content" not in q:
                q["content"] = q.get("question_text", "请回答：")
        return format_response(data={"questions": questions})
    except Exception as e:
        logger.error(f"练习题生成失败: {e}", exc_info=True)
        return format_response(message=f"练习题生成失败: {str(e)}", data=None)


@router.post("/exercises/submit")
async def submit_exercises(
    component_id: str = Body(..., description="知识组件ID"),
    answers: List[dict] = Body(..., description="答案列表"),
    question_content: str = Body("", description="题目内容"),
    user_id: str = Body("default_user", description="用户ID")
):
    """提交练习答案（单题批改）"""
    comp_info = find_component_info(component_id)
    component_name = comp_info["component_name"] if comp_info else component_id
    point_id = comp_info.get("point_id", "") if comp_info else ""
    topic_name = comp_info.get("topic_name", "") if comp_info else ""
    point_name = comp_info.get("point_name", component_name) if comp_info else component_name

    user_answer = answers[0].get("answer", "未作答") if answers else "未作答"

    try:
        agent = get_teaching_agent()
        parsed = await agent.grade_answers(
            topic_name=topic_name,
            point_name=component_name,
            question_content=question_content,
            user_answer=user_answer
        )

        is_correct = parsed.get("is_correct", False)
        score = 100 if is_correct else 0

        # 记录知识点完成状态
        topic_id = find_topic_id_by_point(point_id)
        if topic_id:
            mark_point_completed(topic_id, point_id, score)
            logger.info(f"知识点 {point_id} 已标记为完成, topic={topic_id}, score={score}")

        # 保存练习记录
        try:
            repo = get_exercise_repo()
            record = ExerciseRecord(
                record_id="",
                user_id=user_id,
                component_id=component_id,
                component_name=component_name,
                topic_name=topic_name,
                point_name=point_name,
                question_content=question_content,
                user_answer=parsed.get("user_answer", user_answer),
                correct_answer=parsed.get("correct_answer", ""),
                is_correct=is_correct,
                error_analysis=parsed.get("error_analysis", ""),
                feedback=parsed.get("feedback", "")
            )
            repo.save_record(record)
            logger.info(f"练习记录已保存: user={user_id}, component={component_id}")
        except Exception as save_err:
            logger.warning(f"保存练习记录失败: {save_err}")

        return format_response(data={
            "score": score,
            "totalCount": 1,
            "correctCount": 1 if is_correct else 0,
            "feedback": parsed.get("feedback", "批改完成"),
            "isCorrect": is_correct,
            "userAnswer": parsed.get("user_answer", user_answer),
            "correctAnswer": parsed.get("correct_answer", ""),
            "errorAnalysis": parsed.get("error_analysis", ""),
            "questionContent": question_content
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
        llm_client = AgentLLMClient(provider=ProviderType.ZHIPU)
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


# ============================================
# 练习历史记录 API
# ============================================

@router.get("/exercises/history")
async def get_exercise_history(
    user_id: str = Query("default_user", description="用户ID"),
    limit: int = Query(50, description="返回数量限制")
):
    """获取用户练习历史记录"""
    try:
        repo = get_exercise_repo()
        records = repo.get_user_records(user_id, limit)

        history = []
        for r in records:
            history.append({
                "recordId": r.record_id,
                "componentId": r.component_id,
                "componentName": r.component_name,
                "topicName": r.topic_name,
                "isCorrect": r.is_correct,
                "submittedAt": r.submitted_at
            })

        return format_response(data={
            "total": len(history),
            "records": history
        })
    except Exception as e:
        logger.error(f"获取练习历史失败: {e}", exc_info=True)
        return format_response(message=f"获取练习历史失败: {str(e)}", data=None)


@router.get("/exercises/history/{record_id}")
async def get_exercise_detail(
    record_id: str,
    user_id: str = Query("default_user", description="用户ID")
):
    """获取单条练习记录详情"""
    try:
        repo = get_exercise_repo()
        record = repo.get_record_by_id(record_id)

        if not record:
            return format_response(message="记录不存在", data=None)

        if record.user_id != user_id:
            return format_response(message="无权访问此记录", data=None)

        return format_response(data={
            "recordId": record.record_id,
            "componentId": record.component_id,
            "componentName": record.component_name,
            "topicName": record.topic_name,
            "pointName": record.point_name,
            "questionContent": record.question_content,
            "userAnswer": record.user_answer,
            "correctAnswer": record.correct_answer,
            "isCorrect": record.is_correct,
            "errorAnalysis": record.error_analysis,
            "feedback": record.feedback,
            "submittedAt": record.submitted_at
        })
    except Exception as e:
        logger.error(f"获取练习详情失败: {e}", exc_info=True)
        return format_response(message=f"获取练习详情失败: {str(e)}", data=None)


# ============================================
# 定制综合练习 API
# ============================================

from app.agents.learning.custom_exercise import CustomExerciseAgent

_custom_exercise_agent = None

def get_custom_exercise_agent() -> CustomExerciseAgent:
    """获取定制综合练习Agent实例"""
    global _custom_exercise_agent
    if _custom_exercise_agent is None:
        _custom_exercise_agent = CustomExerciseAgent()
    return _custom_exercise_agent


@router.post("/custom-exercise/generate")
async def generate_custom_exercise(
    topic_name: str = Body("", description="知识主题名称"),
    point_names: List[str] = Body(..., description="知识点名称列表")
):
    """
    生成综合练习题

    根据用户选择的知识点生成覆盖多个知识点的综合练习题

    - **topic_name**: 知识主题名称
    - **point_names**: 知识点名称列表
    """
    try:
        agent = get_custom_exercise_agent()
        exercise_set = await agent.generate_exercise(
            topic_name=topic_name,
            point_names=point_names
        )
        return format_response(data=exercise_set.to_dict())
    except Exception as e:
        logger.error(f"生成综合练习题失败: {e}", exc_info=True)
        return format_response(message=f"生成综合练习题失败: {str(e)}", data=None)


@router.post("/custom-exercise/grade")
async def grade_custom_exercise(
    exercise_id: str = Body(..., description="练习ID"),
    questions: List[dict] = Body(..., description="题目列表"),
    answers: dict = Body(..., description="用户答案 {question_id: answer}")
):
    """
    批改综合练习题

    对用户提交的答案进行批改并返回批改报告

    - **exercise_id**: 练习ID
    - **questions**: 题目列表
    - **answers**: 用户答案字典
    """
    try:
        agent = get_custom_exercise_agent()
        grade_report = await agent.grade_answers(
            exercise_id=exercise_id,
            questions=questions,
            user_answers=answers
        )
        return format_response(data=grade_report.to_dict())
    except Exception as e:
        logger.error(f"批改综合练习题失败: {e}", exc_info=True)
        return format_response(message=f"批改综合练习题失败: {str(e)}", data=None)
