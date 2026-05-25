"""
Topics 端点

提供主题相关的API接口
"""

import asyncio
import json
import logging
import re
import uuid
from typing import List, Optional

from fastapi import APIRouter, Query, Body
from fastapi.responses import StreamingResponse

from app.api.v1.middleware.response import format_response, ResponseFormatter
from app.agents.llm_providers.agent_adapter import AgentLLMClient
from app.agents.llm_providers.config import ProviderType
from app.api.v1.endpoints.knowledge_cache import (
    set_topic_structure,
    get_topic_structure as cache_get_structure,
    set_topic_overview,
    get_topic_overview as cache_get_overview,
    save_topic_to_file,
    load_topic_from_file,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== Prompt 模板 ====================

OVERVIEW_PROMPT_TEMPLATE = """=== 知识向导 ====== 你的角色 ===一位深谙学习之道的引路人。你知道每个领域都有其隐秘的入口，也知道初学者最容易在哪里迷失。=== 核心使命 ===为渴望理解【{topic_text}】的探索者点亮第一盏灯。不是给他们一张地图，而是让他们看懂这片土地的纹理。=== 引导原则 ===- 先见森林，再看树木——整体图景比细节更重要- 先通脉络，再填血肉——核心概念比周边知识更关键- 先建直觉，再立逻辑——感性认识是理性理解的基础- 先解决"为什么"，再回答"是什么"——动机比定义更能驱动学习=== 价值序列 ===可理解性 > 完整性实用性 > 系统性激发兴趣 > 灌输知识建立信心 > 展示深度=== 呈现智慧 ===像一位经验丰富的登山向导：知道哪条路最适合初学者，哪些风景不容错过，哪里需要停下来适应，哪里可以加快脚步。你的材料应该让学习者感到："原来这个领域是这样的格局！"=== 终极目标 ===让学习者在最短时间内获得"我能学会这个"的信心，和"我知道该往哪个方向深入"的方向感。"""

SPLIT_PROMPT_TEMPLATE = """请为我指定的学习主题，搭建标准三层知识体系全景版图，严格分为：
L1 知识板块 → L2 知识点 → L3 知识组件

要求：
1. 层级规范
- L1：顶级大知识板块，为整个领域的一级划分
- L2：每个L1下拆分为若干核心知识点
- L3：每个L2下拆到最小学习组件，不可再拆分，是可单次学习、单次刷题、单次测评的最小单元

2. 必须输出内容包含：
① 该学习主题 全景知识版图总览（文字树形大图）
② 完整三层结构化列表 L1→L2→L3
③ 梳理所有知识点前置依赖关系
④ 生成最优线性学习路径（按先后顺序，循序渐进）
⑤ 配套精细化评估体系：
   - L3组件掌握度自评维度
   - L2知识点阶段考核标准
   - L1板块结业评估标准
   - 薄弱点定位、查漏补缺建议

3. 输出格式：
- 先总览全景版图
- 再分层级结构化罗列
- 再单独给出学习路径路线图
- 最后给出完整评估&测评方案

现在学习主题为：【{topic_text}】

重要：请严格按照以下JSON格式输出知识体系（不要输出其他内容，只输出JSON）：
{{
  "blocks": [
    {{
      "block_name": "L1板块名称",
      "points": [
        {{
          "point_name": "L2知识点名称",
          "difficulty": "easy/medium/hard",
          "is_key_point": true/false,
          "components": [
            {{
              "component_name": "L3组件名称"
            }}
          ]
        }}
      ]
    }}
  ]
}}"""


# ==================== 辅助函数 ====================

def _parse_json_from_llm_response(text: str) -> dict:
    """
    从LLM响应文本中提取JSON对象。
    LLM可能返回markdown代码块包裹的JSON，需要做容错处理。
    """
    # 尝试直接解析
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试从markdown代码块中提取
    code_block_pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
    matches = re.findall(code_block_pattern, text, re.DOTALL)
    for match in matches:
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue

    # 尝试找到第一个 { 和最后一个 } 之间的内容
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(text[first_brace:last_brace + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"无法从LLM响应中解析JSON: {text[:200]}")


def _build_structure_dict(parsed: dict) -> dict:
    """
    将LLM返回的JSON解析结果转换为带UUID的内部结构字典。
    同时保留原始数据以便后续直接返回给前端。
    """
    blocks = []
    for block_data in parsed.get("blocks", []):
        block_id = f"block-{uuid.uuid4().hex[:8]}"
        points = []
        for point_data in block_data.get("points", []):
            point_id = f"point-{uuid.uuid4().hex[:8]}"
            components = []
            for comp_data in point_data.get("components", []):
                component_id = f"comp-{uuid.uuid4().hex[:8]}"
                components.append({
                    "component_id": component_id,
                    "component_name": comp_data.get("component_name", ""),
                    "status": "not_started",
                })
            points.append({
                "point_id": point_id,
                "point_name": point_data.get("point_name", ""),
                "status": "not_started",
                "is_key_point": point_data.get("is_key_point", False),
                "difficulty": point_data.get("difficulty", "medium"),
                "components": components,
            })
        blocks.append({
            "block_id": block_id,
            "block_name": block_data.get("block_name", ""),
            "points": points,
        })
    return {"blocks": blocks}


# ==================== API 端点 ====================

async def _process_topic_background(topic_id: str, topic_name: str):
    """后台任务：并行生成全景介绍和知识拆分结构"""
    try:
        llm_client = AgentLLMClient(provider=ProviderType.DOUBAO)

        overview_prompt = OVERVIEW_PROMPT_TEMPLATE.format(topic_text=topic_name)
        split_prompt = SPLIT_PROMPT_TEMPLATE.format(topic_text=topic_name)

        overview_task = llm_client.generate(
            overview_prompt,
            system_prompt="你是一位专业的教育内容生成专家。",
            max_tokens=4000
        )
        split_task = llm_client.generate(
            split_prompt,
            system_prompt="你是一位专业的教育内容生成专家，擅长结构化知识体系搭建。请只输出JSON，不要输出其他内容。",
            max_tokens=8000
        )

        overview_result, split_result = await asyncio.gather(
            overview_task, split_task
        )

        # 存储全景介绍（纯文本）
        set_topic_overview(topic_id, overview_result)

        # 解析知识拆分JSON并存储
        parsed = _parse_json_from_llm_response(split_result)
        structure = _build_structure_dict(parsed)
        set_topic_structure(topic_id, structure)

        # 持久化到本地文件（以topic_name为key）
        save_topic_to_file(topic_name, topic_id, overview_result, structure)

        logger.info(f"主题 {topic_id} 后台处理完成")
    except Exception as e:
        logger.error(f"主题 {topic_id} 后台处理失败: {e}", exc_info=True)


@router.post("")
async def create_topic(
    body: dict = Body(..., description="主题数据")
):
    """
    创建学习主题

    立即返回topic_id，后台异步生成全景介绍和知识拆分结构。
    客户端可通过 /{topic_id}/status 端点查询处理进度。
    - **topic_text**: 主题文本
    """
    topic_text = body.get("topic_text", "")
    if not topic_text:
        return format_response(message="topic_text不能为空", data=None)

    topic_id = f"topic-{uuid.uuid4().hex[:12]}"
    topic_name = topic_text

    # 检查是否有已保存的主题数据（以topic_text为key匹配）
    cached_data = load_topic_from_file(topic_text)
    if cached_data:
        # 有缓存：直接加载到内存缓存，无需调用LLM
        cached_overview = cached_data.get("overview", "")
        cached_structure = cached_data.get("structure")
        if cached_overview:
            set_topic_overview(topic_id, cached_overview)
        if cached_structure:
            set_topic_structure(topic_id, cached_structure)
        logger.info(f"主题命中文件缓存: topic_text={topic_text}, topic_id={topic_id}")
    else:
        # 无缓存：启动后台任务处理LLM调用
        asyncio.create_task(_process_topic_background(topic_id, topic_name))

    logger.info(f"主题创建已接受: topic_id={topic_id}, topic_name={topic_text}")

    return format_response(data={
        "topic_id": topic_id,
        "topic_name": topic_name,
        "status": "processing"
    })


@router.get("/recommend")
async def get_recommend_topics(
    user_id: Optional[str] = Query(None, description="用户ID")
):
    """获取推荐主题"""
    try:
        recommend_prompt = """请推荐5个适合在线学习的技术主题，覆盖不同领域和难度。

要求：
- 涵盖编程、数据科学、产品设计等不同方向
- 难度从入门到进阶
- 每个主题有简短描述（30字以内）

请严格按以下JSON格式输出（只输出JSON）：
{
  "topics": [
    {"topic_name": "主题名称", "description": "简短描述", "category": "分类", "difficulty": "easy"}
  ]
}"""

        llm_client = AgentLLMClient(provider=ProviderType.DOUBAO)
        result_text = await llm_client.generate(
            recommend_prompt,
            system_prompt="你是一位教育内容策划专家。",
            max_tokens=2000
        )

        brace_start = result_text.find('{')
        brace_end = result_text.rfind('}')
        if brace_start >= 0 and brace_end > brace_start:
            parsed = json.loads(result_text[brace_start:brace_end+1])
            topics = []
            for i, t in enumerate(parsed.get("topics", [])):
                topics.append({
                    "topic_id": f"topic-rec-{i+1}",
                    "topic_name": t.get("topic_name", ""),
                    "description": t.get("description", ""),
                    "category": t.get("category", "综合"),
                    "difficulty": t.get("difficulty", "medium")
                })
            return format_response(data=topics)
    except Exception as e:
        logger.error(f"推荐主题生成失败: {e}", exc_info=True)

    # Fallback to static recommendations
    fallback = [
        {"topic_id": "topic-rec-1", "topic_name": "Python编程", "description": "从零开始学习Python编程语言", "category": "编程", "difficulty": "easy"},
        {"topic_id": "topic-rec-2", "topic_name": "数据分析", "description": "学习数据分析的基本方法和工具", "category": "数据科学", "difficulty": "medium"},
        {"topic_id": "topic-rec-3", "topic_name": "产品经理", "description": "掌握产品设计和管理的核心技能", "category": "产品设计", "difficulty": "medium"},
    ]
    return format_response(data=fallback)


@router.get("/{topic_id}/status")
async def get_topic_status(topic_id: str):
    """
    查询主题处理状态

    返回overview和structure的生成进度，前端可据此轮询。
    - **topic_id**: 主题ID
    """
    structure = cache_get_structure(topic_id)
    overview = cache_get_overview(topic_id)

    has_structure = structure is not None
    has_overview = overview is not None

    return format_response(data={
        "topic_id": topic_id,
        "structure_ready": has_structure,
        "overview_ready": has_overview,
        "status": "completed" if (has_structure and has_overview) else "processing"
    })


@router.get("/{topic_id}/structure")
async def get_topic_structure(
    topic_id: str,
    user_id: Optional[str] = Query(None, description="用户ID（可选）")
):
    """
    获取主题的三层知识体系结构

    - **topic_id**: 主题ID
    - **user_id**: 用户ID（可选，用于获取个性化进度）
    """
    # 如果内存中有LLM生成的知识体系，优先返回
    structure = cache_get_structure(topic_id)
    if structure:
        # 新流程存储的是dict结构，直接返回blocks列表
        if isinstance(structure, dict) and "blocks" in structure:
            blocks = structure["blocks"]
            # 从数据库加载组件学习状态并合并
            try:
                from app.db.database import SessionLocal
                from app.models.progress import LearningProgress
                db = SessionLocal()
                try:
                    progresses = db.query(LearningProgress).filter(
                        LearningProgress.topic_id == topic_id
                    ).all()
                    if progresses:
                        import copy
                        blocks = copy.deepcopy(blocks)
                        status_map = {p.component_id: p.status for p in progresses}
                        for block in blocks:
                            for point in block.get("points", []):
                                for comp in point.get("components", []):
                                    comp_id = comp.get("component_id")
                                    if comp_id and comp_id in status_map:
                                        comp["status"] = status_map[comp_id]
                finally:
                    db.close()
            except Exception as e:
                logger.warning(f"加载组件学习状态失败: {e}")
            return format_response(data=blocks)

        # 兼容旧版dataclass结构
        data = []
        for block in structure.blocks:
            points = []
            for point in block.points:
                components = []
                for comp in point.components:
                    components.append({
                        "component_id": comp.component_id,
                        "component_name": comp.component_name,
                        "status": "not_started"
                    })
                points.append({
                    "point_id": point.point_id,
                    "point_name": point.point_name,
                    "status": "not_started",
                    "is_key_point": getattr(point, 'is_key_point', False),
                    "difficulty": getattr(point, 'difficulty', 'medium'),
                    "components": components
                })
            data.append({
                "block_id": block.block_id,
                "block_name": block.block_name,
                "points": points
            })
        return format_response(data=data)

    # 兜底：返回mock数据
    mock_data = [
        {
            "block_id": "block-1",
            "block_name": "基础知识",
            "points": [
                {
                    "point_id": "point-1",
                    "point_name": "变量与数据类型",
                    "status": "completed",
                    "is_key_point": True,
                    "difficulty": "easy",
                    "components": [
                        {"component_id": "comp-1", "component_name": "变量定义", "status": "completed"},
                        {"component_id": "comp-2", "component_name": "数据类型", "status": "completed"}
                    ]
                },
                {
                    "point_id": "point-2",
                    "point_name": "条件语句与循环",
                    "status": "in_progress",
                    "is_key_point": True,
                    "difficulty": "medium",
                    "components": [
                        {"component_id": "comp-3", "component_name": "if语句", "status": "completed"},
                        {"component_id": "comp-4", "component_name": "for循环", "status": "in_progress"},
                        {"component_id": "comp-5", "component_name": "while循环", "status": "not_started"}
                    ]
                }
            ]
        },
        {
            "block_id": "block-2",
            "block_name": "进阶知识",
            "points": [
                {
                    "point_id": "point-3",
                    "point_name": "函数与模块",
                    "status": "not_started",
                    "is_key_point": False,
                    "difficulty": "medium",
                    "components": [
                        {"component_id": "comp-6", "component_name": "函数定义", "status": "not_started"},
                        {"component_id": "comp-7", "component_name": "参数传递", "status": "not_started"}
                    ]
                },
                {
                    "point_id": "point-4",
                    "point_name": "面向对象编程",
                    "status": "not_started",
                    "is_key_point": True,
                    "difficulty": "hard",
                    "components": [
                        {"component_id": "comp-8", "component_name": "类与对象", "status": "not_started"},
                        {"component_id": "comp-9", "component_name": "继承与多态", "status": "not_started"}
                    ]
                }
            ]
        },
        {
            "block_id": "block-3",
            "block_name": "实战应用",
            "points": [
                {
                    "point_id": "point-5",
                    "point_name": "文件操作",
                    "status": "not_started",
                    "is_key_point": False,
                    "difficulty": "easy",
                    "components": [
                        {"component_id": "comp-10", "component_name": "文件读写", "status": "not_started"}
                    ]
                }
            ]
        }
    ]

    return format_response(data=mock_data)


@router.get("/{topic_id}/overview")
async def get_topic_overview(
    topic_id: str,
):
    """
    获取主题的全景介绍

    - **topic_id**: 主题ID
    """
    overview = cache_get_overview(topic_id)
    if overview:
        # 尝试从知识结构缓存中获取topic_name
        structure = cache_get_structure(topic_id)
        topic_name = ""
        if isinstance(structure, dict):
            topic_name = structure.get("topic_name", "")
        elif hasattr(structure, 'topic_name'):
            topic_name = structure.topic_name

        return format_response(data={
            "topic_id": topic_id,
            "topic_name": topic_name,
            "overview": overview,
        })

    return format_response(code=404, message="未找到该主题的全景介绍", data=None)


@router.get("/{topic_id}/progress")
async def get_topic_progress_stream(topic_id: str):
    """
    SSE 流式推送主题处理完成状态
    
    每2秒检查一次缓存状态，最长120秒（60次循环）
    完成后立即推送数据并关闭连接，超时推送超时标记
    
    - **topic_id**: 主题ID
    """
    async def event_generator():
        for _ in range(60):  # 120秒 / 2秒间隔 = 60次
            structure = cache_get_structure(topic_id)
            overview = cache_get_overview(topic_id)
            
            if structure and overview:
                # 已完成，推送数据并结束
                yield f"data: {json.dumps({'completed': True, 'structure': structure, 'overview': overview})}\n\n"
                return
            
            # 未完成，等待2秒后继续
            await asyncio.sleep(2)
        
        # 120秒超时，推送超时消息
        yield f"data: {json.dumps({'timeout': True, 'message': '处理时间较长，请稍后再来查看'})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
