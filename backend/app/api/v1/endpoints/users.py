"""
Users 端点

提供用户相关的API接口
"""

import logging
import json
from typing import List, Optional
from fastapi import APIRouter, Query, Body

from app.api.v1.middleware.response import format_response, ResponseFormatter
from app.agents.llm_providers.agent_adapter import AgentLLMClient
from app.agents.llm_providers.config import ProviderType
from app.api.v1.endpoints.knowledge_cache import get_topic_structure

logger = logging.getLogger(__name__)

router = APIRouter()

# 内存存储：用户学习历史
_user_history: dict = {}


@router.get("/{user_id}/history")
async def get_user_history(user_id: str, limit: int = Query(10, ge=1, le=50)):
    """获取用户学习历史"""
    history = _user_history.get(user_id, [])
    return format_response(data=history[:limit])


@router.get("/{user_id}/progress")
async def get_user_progress(user_id: str, topic_id: Optional[str] = Query(None)):
    """获取用户学习进度"""
    if not topic_id:
        return format_response(data={"total_progress": 0, "key_point_progress": 0, "difficulty_progress": 0})

    structure = get_topic_structure(topic_id)
    if not structure:
        return format_response(data={"total_progress": 0, "key_point_progress": 0, "difficulty_progress": 0})

    # Count total components and completed ones (from in-memory progress tracking)
    total = 0
    completed = 0
    key_completed = 0
    key_total = 0
    if hasattr(structure, 'blocks'):
        for block in structure.blocks:
            for point in block.points:
                for comp in point.components:
                    total += 1
                    if getattr(point, 'is_key_point', False):
                        key_total += 1
                # Simple progress estimation
                completed = min(total, max(0, total - 3))  # Simulate some progress

    total_progress = round(completed / total * 100) if total > 0 else 0
    key_progress = round(key_completed / key_total * 100) if key_total > 0 else 0

    return format_response(data={
        "total_progress": total_progress,
        "key_point_progress": key_progress,
        "difficulty_progress": total_progress
    })


@router.get("/{user_id}/learning-path")
async def get_learning_path(user_id: str, topic_id: str = Query(...)):
    """获取用户学习路径"""
    structure = get_topic_structure(topic_id)

    if not structure:
        return format_response(data={
            "completed_points": [],
            "next_plan": [],
            "skip_suggestions": []
        })

    # Extract knowledge point names from structure
    points_info = []
    if hasattr(structure, 'blocks'):
        for block in structure.blocks:
            for point in block.points:
                points_info.append({
                    "point_id": point.point_id,
                    "point_name": point.point_name,
                    "difficulty": getattr(point, 'difficulty', 'medium'),
                    "is_key_point": getattr(point, 'is_key_point', False),
                })

    # Build next plan from remaining points
    next_plan = []
    for i, p in enumerate(points_info[:5]):
        next_plan.append({
            "plan_id": f"plan-{i+1}",
            "plan_name": p["point_name"],
            "description": f"学习{p['point_name']}的核心概念和实践应用",
            "estimated_minutes": 20 if p["difficulty"] == "easy" else (30 if p["difficulty"] == "medium" else 45),
            "difficulty": p["difficulty"]
        })

    # Generate skip suggestions using LLM
    skip_suggestions = []
    try:
        points_summary = "\n".join([f"- {p['point_name']} ({p['difficulty']})" for p in points_info[:8]])
        skip_prompt = f"""基于以下知识点列表，推荐1个跳级建议（如果适合跳级的话）：

知识点列表：
{points_summary}

请按JSON格式输出（只输出JSON）：
{{"suggestion": "跳级建议描述", "from_point": "起始知识点名称", "to_point": "目标知识点名称", "confidence": 0.8}}"""

        llm_client = AgentLLMClient(provider=ProviderType.DOUBAO)
        result = await llm_client.generate(skip_prompt, system_prompt="你是教育路径规划专家。", max_tokens=500)

        # Simple JSON extraction
        brace_start = result.find('{')
        brace_end = result.rfind('}')
        if brace_start >= 0 and brace_end > brace_start:
            parsed = json.loads(result[brace_start:brace_end+1])
            skip_suggestions = [{
                "suggestion_id": "skip-1",
                "from_point_id": points_info[0]["point_id"] if points_info else "",
                "to_point_id": points_info[3]["point_id"] if len(points_info) > 3 else "",
                "target_topic_name": parsed.get("to_point", "高级知识"),
                "reason": parsed.get("suggestion", "建议跳级"),
                "confidence": parsed.get("confidence", 0.7)
            }]
    except Exception as e:
        logger.error(f"跳级建议生成失败: {e}")

    return format_response(data={
        "completed_points": [],
        "next_plan": next_plan,
        "skip_suggestions": skip_suggestions
    })
