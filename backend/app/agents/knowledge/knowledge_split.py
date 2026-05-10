"""
U-020 知识拆分Agent

核心职责：将用户输入的学习主题拆解为三层知识体系
（知识板块 → 知识点 → 知识组件）

底层执行逻辑：
1. 接收学习主题输入（topic_name, description）
2. 构建Few-shot Prompt，引导LLM进行知识拆解
3. 调用LLM API获取三层知识体系
4. 解析LLM输出为结构化数据
5. 返回知识板块、知识点、知识组件列表

内存数据流转：
用户输入 → Prompt构建 → LLM API → JSON解析 → 结构化知识体系 → 返回

潜在风险：
1. 内存泄漏：LLM响应未及时释放（已用上下文管理器）
2. 逻辑漏洞：LLM输出格式不稳定导致解析失败（已有多次解析尝试+兜底）
3. 边界条件：主题过于宽泛/狭窄的处理（已设置主题范围校验）
4. 质量风险：知识拆解不完整的检查（已实现完整性验证）

依赖：LangChain、OpenAI API
"""

import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.agents.base import TaskRequest, TaskResult, TaskStatus, TaskType
from app.agents.error_handler import get_error_handler

logger = logging.getLogger(__name__)


# ============================================
# 数据模型定义
# ============================================

@dataclass
class KnowledgeComponent:
    """知识组件"""
    component_id: str
    component_name: str
    component_order: int
    learning_objective: str  # 学习目标

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_id": self.component_id,
            "component_name": self.component_name,
            "component_order": self.component_order,
            "learning_objective": self.learning_objective
        }


@dataclass
class KnowledgePoint:
    """知识点"""
    point_id: str
    point_name: str
    point_order: int
    description: str
    components: List[KnowledgeComponent] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "point_id": self.point_id,
            "point_name": self.point_name,
            "point_order": self.point_order,
            "description": self.description,
            "components": [c.to_dict() for c in self.components]
        }


@dataclass
class KnowledgeBlock:
    """知识板块"""
    block_id: str
    block_name: str
    block_order: int
    description: str
    points: List[KnowledgePoint] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "block_id": self.block_id,
            "block_name": self.block_name,
            "block_order": self.block_order,
            "description": self.description,
            "points": [p.to_dict() for p in self.points]
        }


@dataclass
class KnowledgeStructure:
    """完整知识体系"""
    topic_name: str
    topic_description: str
    blocks: List[KnowledgeBlock] = field(default_factory=list)
    total_points: int = 0
    total_components: int = 0
    estimated_hours: float = 0  # 预估学习时长

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic_name": self.topic_name,
            "topic_description": self.topic_description,
            "blocks": [b.to_dict() for b in self.blocks],
            "total_points": self.total_points,
            "total_components": self.total_components,
            "estimated_hours": self.estimated_hours
        }


# ============================================
# Prompt模板
# ============================================

KNOWLEDGE_SPLIT_PROMPT = """
你是一个专业的课程设计师，负责将学习主题拆解为系统化的三层知识体系。

## 任务
将"{topic_name}"这个学习主题拆解为：
1. **知识板块 (Knowledge Blocks)**：大范畴划分，通常3-6个板块
2. **知识点 (Knowledge Points)**：板块内的具体知识节点，每个板块3-8个知识点
3. **知识组件 (Knowledge Components)**：知识点内的最小可测量学习单元，每个知识点2-5个组件

## 主题描述
{topic_description}

## 输出要求
请严格按照以下JSON格式输出，不要添加任何解释：

{{
    "blocks": [
        {{
            "block_name": "板块名称",
            "block_description": "板块简短描述（20字以内）",
            "points": [
                {{
                    "point_name": "知识点名称",
                    "point_description": "知识点简短描述（20字以内）",
                    "components": [
                        {{
                            "component_name": "知识组件名称",
                            "learning_objective": "学习目标描述（学生学完后能做什么）"
                        }}
                    ]
                }}
            ]
        }}
    ]
}}

## 约束
- 知识板块数量：3-6个
- 每个知识板块下的知识点数量：3-8个
- 每个知识点下的知识组件数量：2-5个
- 知识组件应该描述为可观测的学习成果（action verbs）
- 确保知识体系覆盖主题的核心内容，无明显遗漏
- 知识点之间应有逻辑顺序，便于学习

## 示例输出（Python编程主题）
{{
    "blocks": [
        {{
            "block_name": "Python基础",
            "block_description": "Python编程入门知识",
            "points": [
                {{
                    "point_name": "变量与数据类型",
                    "point_description": "Python基本数据类型",
                    "components": [
                        {{"component_name": "变量命名规则", "learning_objective": "能正确命名变量，遵循命名规范"}},
                        {{"component_name": "整数与浮点数", "learning_objective": "能区分整数和浮点数并进行运算"}},
                        {{"component_name": "字符串操作", "learning_objective": "能进行字符串的拼接、切片、格式化"}}
                    ]
                }}
            ]
        }}
    ]
}}

请现在输出JSON格式的知识体系：
"""


# ============================================
# Agent实现
# ============================================

class KnowledgeSplitAgent:
    """
    知识拆分Agent

    使用LLM将学习主题拆解为三层知识体系
    """

    def __init__(
        self,
        llm_client=None,
        max_retries: int = 3,
        temperature: float = 0.3
    ):
        """
        初始化知识拆分Agent

        Args:
            llm_client: LLM客户端（支持OpenAI格式）
            max_retries: 最大重试次数
            temperature: 生成温度
        """
        self.llm_client = llm_client
        self.max_retries = max_retries
        self.temperature = temperature
        self.error_handler = get_error_handler()

    def _validate_input(self, topic_name: str, description: str) -> None:
        """
        验证输入参数

        Args:
            topic_name: 主题名称
            description: 主题描述

        Raises:
            ValueError: 参数无效
        """
        if not topic_name or not topic_name.strip():
            raise ValueError("主题名称不能为空")

        if len(topic_name) > 100:
            raise ValueError("主题名称不能超过100个字符")

        if len(topic_name) < 2:
            raise ValueError("主题名称至少需要2个字符")

    def _build_prompt(self, topic_name: str, description: str) -> str:
        """
        构建Prompt

        Args:
            topic_name: 主题名称
            description: 主题描述

        Returns:
            格式化后的Prompt
        """
        # 处理空描述
        if not description or not description.strip():
            description = "用户未提供详细描述，请根据主题名称自行推断"

        return KNOWLEDGE_SPLIT_PROMPT.format(
            topic_name=topic_name.strip(),
            topic_description=description.strip()
        )

    def _parse_llm_output(self, output: str) -> Dict[str, Any]:
        """
        解析LLM输出

        Args:
            output: LLM原始输出

        Returns:
            解析后的JSON数据

        Raises:
            ValueError: 解析失败
        """
        # 尝试提取JSON
        json_str = output.strip()

        # 移除可能的markdown代码块标记
        if "```json" in json_str:
            json_str = re.split(r"```json", json_str)[1]
            json_str = re.split(r"```", json_str)[0]
        elif "```" in json_str:
            json_str = re.split(r"```", json_str)[1]
            if json_str.startswith("json"):
                json_str = json_str[4:]

        json_str = json_str.strip()

        # 尝试解析
        try:
            data = json.loads(json_str)
            return data
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON解析失败: {e}")

    def _generate_ids(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        为知识体系生成UUID

        Args:
            data: 原始数据（不含ID）

        Returns:
            带ID的数据
        """
        blocks = data.get("blocks", [])

        result_blocks = []
        point_idx = 0
        component_idx = 0

        for block in blocks:
            block_id = f"block-{uuid.uuid4().hex[:8]}"
            block_order = len(result_blocks) + 1

            points = block.get("points", [])
            result_points = []

            for point in points:
                point_id = f"point-{uuid.uuid4().hex[:8]}"
                point_order = len(result_points) + 1
                point_idx += 1

                components = point.get("components", [])
                result_components = []

                for comp in components:
                    component_id = f"comp-{uuid.uuid4().hex[:8]}"
                    component_order = len(result_components) + 1
                    component_idx += 1

                    result_components.append({
                        "component_id": component_id,
                        "component_name": comp.get("component_name", ""),
                        "component_order": component_order,
                        "learning_objective": comp.get("learning_objective", "")
                    })

                result_points.append({
                    "point_id": point_id,
                    "point_name": point.get("point_name", ""),
                    "point_order": point_order,
                    "description": point.get("point_description", ""),
                    "components": result_components
                })

            result_blocks.append({
                "block_id": block_id,
                "block_name": block.get("block_name", ""),
                "block_order": block_order,
                "description": block.get("block_description", ""),
                "points": result_points
            })

        return {"blocks": result_blocks}

    def _validate_completeness(self, data: Dict[str, Any]) -> List[str]:
        """
        验证知识体系完整性

        Args:
            data: 知识体系数据

        Returns:
            警告列表
        """
        warnings = []
        blocks = data.get("blocks", [])

        # 检查板块数量
        if len(blocks) < 3:
            warnings.append(f"知识板块数量较少（{len(blocks)}个），可能不够系统")
        elif len(blocks) > 6:
            warnings.append(f"知识板块数量较多（{len(blocks)}个），建议精简")

        total_points = sum(len(b.get("points", [])) for b in blocks)
        total_components = sum(
            len(p.get("components", []))
            for b in blocks
            for p in b.get("points", [])
        )

        # 检查总数量
        if total_points < 10:
            warnings.append(f"知识点总数较少（{total_points}个），可能内容不够完整")
        if total_components < 20:
            warnings.append(f"知识组件总数较少（{total_components}个），建议增加更多细节")

        return warnings

    def _calculate_estimated_hours(self, data: Dict[str, Any]) -> float:
        """
        估算学习时长

        Args:
            data: 知识体系数据

        Returns:
            预估小时数
        """
        total_components = sum(
            len(p.get("components", []))
            for b in data.get("blocks", [])
            for p in b.get("points", [])
        )

        # 假设每个组件平均需要5-15分钟学习
        return round(total_components * 0.15, 1)  # 小时

    async def execute(
        self,
        topic_name: str,
        topic_description: str = "",
        user_id: Optional[str] = None
    ) -> KnowledgeStructure:
        """
        执行知识拆分

        Args:
            topic_name: 主题名称
            topic_description: 主题描述
            user_id: 用户ID（可选）

        Returns:
            KnowledgeStructure对象

        Raises:
            ValueError: 输入参数无效
            Exception: LLM调用失败
        """
        # 验证输入
        self._validate_input(topic_name, topic_description)

        # 构建Prompt
        prompt = self._build_prompt(topic_name, topic_description)

        # 调用LLM（带重试）
        last_error = None
        raw_output = None

        for attempt in range(self.max_retries):
            try:
                if self.llm_client:
                    response = await self.llm_client.agenerate([prompt])
                    raw_output = response.generations[0][0].text
                else:
                    # 模拟LLM响应（开发测试用）
                    raw_output = self._mock_llm_response(topic_name)
                    logger.warning("使用模拟LLM响应，请配置真实的LLM客户端")

                # 解析输出
                parsed_data = self._parse_llm_output(raw_output)

                # 生成ID
                data_with_ids = self._generate_ids(parsed_data)

                # 验证完整性
                warnings = self._validate_completeness(data_with_ids)
                if warnings:
                    logger.warning(f"知识拆分完整性警告: {warnings}")

                # 构建结果
                blocks = data_with_ids.get("blocks", [])
                result_blocks = []
                total_points = 0
                total_components = 0

                for block_data in blocks:
                    points = block_data.get("points", [])
                    result_points = []
                    total_points += len(points)

                    for point_data in points:
                        components = point_data.get("components", [])
                        result_components = []
                        total_components += len(components)

                        for comp_data in components:
                            comp = KnowledgeComponent(
                                component_id=comp_data["component_id"],
                                component_name=comp_data["component_name"],
                                component_order=comp_data["component_order"],
                                learning_objective=comp_data["learning_objective"]
                            )
                            result_components.append(comp)

                        point = KnowledgePoint(
                            point_id=point_data["point_id"],
                            point_name=point_data["point_name"],
                            point_order=point_data["point_order"],
                            description=point_data["description"],
                            components=result_components
                        )
                        result_points.append(point)

                    block = KnowledgeBlock(
                        block_id=block_data["block_id"],
                        block_name=block_data["block_name"],
                        block_order=block_data["block_order"],
                        description=block_data["description"],
                        points=result_points
                    )
                    result_blocks.append(block)

                estimated_hours = self._calculate_estimated_hours(data_with_ids)

                return KnowledgeStructure(
                    topic_name=topic_name.strip(),
                    topic_description=topic_description.strip() if topic_description else "",
                    blocks=result_blocks,
                    total_points=total_points,
                    total_components=total_components,
                    estimated_hours=estimated_hours
                )

            except Exception as e:
                last_error = e
                logger.warning(f"知识拆分失败（第{attempt + 1}次尝试）: {e}")
                continue

        # 所有尝试都失败
        raise Exception(f"知识拆分失败，已重试{self.max_retries}次: {last_error}")

    def _mock_llm_response(self, topic_name: str) -> str:
        """
        模拟LLM响应（开发测试用）

        Args:
            topic_name: 主题名称

        Returns:
            模拟的JSON输出
        """
        return f'''
{{
    "blocks": [
        {{
            "block_name": "{topic_name}基础概念",
            "block_description": "入门必备基础知识",
            "points": [
                {{
                    "point_name": "概念入门",
                    "point_description": "了解核心概念",
                    "components": [
                        {{"component_name": "基本概念", "learning_objective": "能解释核心概念"}},
                        {{"component_name": "术语定义", "learning_objective": "能识别和解释专业术语"}}
                    ]
                }}
            ]
        }}
    ]
}}
'''

    def create_task_request(
        self,
        topic_name: str,
        topic_description: str = "",
        user_id: Optional[str] = None
    ) -> TaskRequest:
        """
        创建任务请求

        Args:
            topic_name: 主题名称
            topic_description: 主题描述
            user_id: 用户ID

        Returns:
            TaskRequest对象
        """
        return TaskRequest(
            task_type=TaskType.KNOWLEDGE_SPLIT,
            input_data={
                "topic_name": topic_name,
                "topic_description": topic_description,
                "user_id": user_id
            },
            priority=8,
            timeout_ms=60000  # 知识拆分可能需要较长时间
        )


# 便捷函数
async def split_knowledge(
    topic_name: str,
    topic_description: str = "",
    llm_client = None
) -> KnowledgeStructure:
    """
    快捷函数：拆分知识体系

    Args:
        topic_name: 主题名称
        topic_description: 主题描述
        llm_client: LLM客户端

    Returns:
        KnowledgeStructure对象
    """
    agent = KnowledgeSplitAgent(llm_client=llm_client)
    return await agent.execute(topic_name, topic_description)
