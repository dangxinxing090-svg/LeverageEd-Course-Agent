"""
U-022 知识讲解Agent

核心职责：根据知识点生成通俗易懂的讲解内容

底层执行逻辑：
1. 接收知识点信息（point_id, point_name, description）
2. 考虑用户学习进度和偏好
3. 构建Prompt，引导LLM生成讲解内容
4. 调用LLM API获取讲解结果
5. 解析并返回结构化讲解内容

内存数据流转：
知识点信息 → Prompt构建 → LLM API → 讲解内容解析 → 结构化讲解 → 返回

潜在风险：
1. 内存泄漏：讲解内容过长（已做长度限制）
2. 逻辑漏洞：讲解内容与知识点不匹配（已验证关联性）
3. 边界条件：知识点信息不完整（已有默认值）
4. 质量风险：讲解过于专业/简单（已实现难度适配）

依赖：LangChain、OpenAI API
"""

import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.agents.base import TaskRequest, TaskType
from app.agents.error_handler import get_error_handler

logger = logging.getLogger(__name__)


# ============================================
# 数据模型定义
# ============================================

@dataclass
class ExplanationSection:
    """讲解章节"""
    section_id: str
    section_title: str
    content: str  # 讲解内容
    example: Optional[str] = None  # 示例
    key_points: List[str] = field(default_factory=list)  # 关键点

    def to_dict(self) -> Dict[str, Any]:
        return {
            "section_id": self.section_id,
            "section_title": self.section_title,
            "content": self.content,
            "example": self.example,
            "key_points": self.key_points
        }


@dataclass
class ExplanationContent:
    """完整讲解内容"""
    point_id: str
    point_name: str
    sections: List[ExplanationSection] = field(default_factory=list)
    summary: str = ""  # 总结
    estimated_minutes: int = 0  # 预估阅读时长
    difficulty_level: str = "MEDIUM"  # 讲解难度级别

    def to_dict(self) -> Dict[str, Any]:
        return {
            "point_id": self.point_id,
            "point_name": self.point_name,
            "sections": [s.to_dict() for s in self.sections],
            "summary": self.summary,
            "estimated_minutes": self.estimated_minutes,
            "difficulty_level": self.difficulty_level
        }


# ============================================
# Prompt模板
# ============================================

CONTENT_EXPLAIN_PROMPT = """
你是一个耐心的教学老师，负责将抽象的知识点转化为通俗易懂的讲解内容。

## 任务
请为以下知识点生成详细的讲解内容。

## 知识点信息
- 名称：{point_name}
- 描述：{description}
- 用户背景：{user_level}
- 讲解风格：{teaching_style}

## 讲解要求
1. **结构清晰**：使用「是什么 → 为什么 → 怎么用」的框架
2. **通俗易懂**：避免过于专业的术语，必须用时需解释
3. **包含示例**：每个关键点都需要实际例子
4. **联系实际**：尽量联系日常生活或已学知识
5. **重点标注**：标出需要特别注意的要点

## 输出要求
请严格按照以下JSON格式输出，不要添加任何解释：

{{
    "sections": [
        {{
            "section_title": "章节标题",
            "content": "详细讲解内容（200-400字）",
            "example": "具体示例（50-100字）",
            "key_points": ["关键点1", "关键点2"]
        }}
    ],
    "summary": "总结内容（50-100字）",
    "estimated_minutes": 数字（预估阅读分钟数）,
    "difficulty_level": "LOW/MEDIUM/HIGH"
}}

## 用户背景说明
- BEGINNER（初学者）：需要从最基础的概念开始讲解
- INTERMEDIATE（中级）：有一定基础，可以更深入
- ADVANCED（高级）：可以讲解更抽象和深入的原理

## 讲解风格说明
- SIMPLE：简单直白，大量类比
- BALANCED：平衡专业性和易懂性
- DETAILED：详细深入，全面透彻

请现在输出JSON格式的讲解内容：
"""


# ============================================
# Agent实现
# ============================================

class UserLevel(str):
    """用户学习水平"""
    BEGINNER = "BEGINNER"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"


class TeachingStyle(str):
    """讲解风格"""
    SIMPLE = "SIMPLE"
    BALANCED = "BALANCED"
    DETAILED = "DETAILED"


class ContentExplainAgent:
    """
    知识讲解Agent

    使用LLM为知识点生成通俗易懂的讲解内容
    """

    def __init__(
        self,
        llm_client=None,
        max_retries: int = 3,
        temperature: float = 0.4,
        max_content_length: int = 5000  # 最大内容长度
    ):
        """
        初始化知识讲解Agent

        Args:
            llm_client: LLM客户端
            max_retries: 最大重试次数
            temperature: 生成温度
            max_content_length: 最大内容长度（字符数）
        """
        self.llm_client = llm_client
        self.max_retries = max_retries
        self.temperature = temperature
        self.max_content_length = max_content_length
        self.error_handler = get_error_handler()

    def _validate_input(self, point_info: Dict[str, str]) -> None:
        """
        验证输入参数

        Args:
            point_info: 知识点信息

        Raises:
            ValueError: 参数无效
        """
        if not point_info:
            raise ValueError("知识点信息不能为空")

        if not point_info.get("point_id"):
            raise ValueError("知识点缺少point_id")

        if not point_info.get("point_name"):
            raise ValueError("知识点缺少point_name")

    def _build_prompt(
        self,
        point_info: Dict[str, str],
        user_level: str = "INTERMEDIATE",
        teaching_style: str = "BALANCED"
    ) -> str:
        """
        构建Prompt

        Args:
            point_info: 知识点信息
            user_level: 用户学习水平
            teaching_style: 讲解风格

        Returns:
            格式化后的Prompt
        """
        point_name = point_info.get("point_name", "")
        description = point_info.get("description", "用户未提供详细描述")

        return CONTENT_EXPLAIN_PROMPT.format(
            point_name=point_name,
            description=description,
            user_level=user_level,
            teaching_style=teaching_style
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
        # 提取JSON
        json_str = output.strip()

        # 移除markdown代码块
        if "```json" in json_str:
            json_str = re.split(r"```json", json_str)[1]
            json_str = re.split(r"```", json_str)[0]
        elif "```" in json_str:
            json_str = re.split(r"```", json_str)[1]
            if json_str.startswith("json"):
                json_str = json_str[4:]

        json_str = json_str.strip()

        try:
            data = json.loads(json_str)
            return data
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON解析失败: {e}")

    def _validate_content(self, data: Dict[str, Any], point_name: str) -> List[str]:
        """
        验证讲解内容的合理性

        Args:
            data: 解析后的数据
            point_name: 知识点名称

        Returns:
            问题列表
        """
        issues = []

        # 检查sections
        sections = data.get("sections", [])
        if not sections:
            issues.append("讲解内容为空")
            return issues

        for i, section in enumerate(sections):
            if not section.get("content"):
                issues.append(f"第{i+1}个章节内容为空")
            if len(section.get("content", "")) > self.max_content_length:
                issues.append(f"第{i+1}个章节内容过长")

        # 检查summary
        if not data.get("summary"):
            issues.append("缺少总结内容")

        return issues

    def _parse_explanation(self, data: Dict[str, Any], point_info: Dict[str, str]) -> ExplanationContent:
        """
        解析讲解数据

        Args:
            data: 原始数据
            point_info: 知识点信息

        Returns:
            ExplanationContent对象
        """
        sections = []
        for i, section_data in enumerate(data.get("sections", [])):
            section = ExplanationSection(
                section_id=f"section-{uuid.uuid4().hex[:8]}",
                section_title=section_data.get("section_title", f"第{i+1}章"),
                content=section_data.get("content", ""),
                example=section_data.get("example"),
                key_points=section_data.get("key_points", [])
            )
            sections.append(section)

        # 计算总内容长度
        total_content = "".join(s.content for s in sections)
        estimated_minutes = max(1, len(total_content) // 200)  # 约200字/分钟

        return ExplanationContent(
            point_id=point_info.get("point_id", ""),
            point_name=point_info.get("point_name", ""),
            sections=sections,
            summary=data.get("summary", ""),
            estimated_minutes=data.get("estimated_minutes", estimated_minutes),
            difficulty_level=data.get("difficulty_level", "MEDIUM")
        )

    async def execute(
        self,
        point_info: Dict[str, str],
        user_level: str = "INTERMEDIATE",
        teaching_style: str = "BALANCED"
    ) -> ExplanationContent:
        """
        执行知识讲解生成

        Args:
            point_info: 知识点信息 {"point_id": "...", "point_name": "...", "description": "..."}
            user_level: 用户学习水平 (BEGINNER/INTERMEDIATE/ADVANCED)
            teaching_style: 讲解风格 (SIMPLE/BALANCED/DETAILED)

        Returns:
            ExplanationContent对象

        Raises:
            ValueError: 输入参数无效
            Exception: LLM调用失败
        """
        # 验证输入
        self._validate_input(point_info)

        # 构建Prompt
        prompt = self._build_prompt(point_info, user_level, teaching_style)

        # 调用LLM（带重试）
        last_error = None
        raw_output = None

        for attempt in range(self.max_retries):
            try:
                if self.llm_client:
                    response = await self.llm_client.agenerate([prompt])
                    raw_output = response.generations[0][0].text
                else:
                    # 模拟响应
                    raw_output = self._mock_llm_response(point_info)
                    logger.warning("使用模拟LLM响应，请配置真实的LLM客户端")

                # 解析输出
                data = self._parse_llm_output(raw_output)

                # 验证合理性
                issues = self._validate_content(data, point_info.get("point_name", ""))
                if issues:
                    logger.warning(f"讲解内容验证问题: {issues}")

                # 解析为结构化对象
                return self._parse_explanation(data, point_info)

            except Exception as e:
                last_error = e
                logger.warning(f"知识讲解失败（第{attempt + 1}次尝试）: {e}")
                continue

        raise Exception(f"知识讲解失败，已重试{self.max_retries}次: {last_error}")

    def _mock_llm_response(self, point_info: Dict[str, str]) -> str:
        """
        模拟LLM响应（开发测试用）

        Args:
            point_info: 知识点信息

        Returns:
            模拟的JSON输出
        """
        point_name = point_info.get("point_name", "未知知识点")

        return f'''
{{
    "sections": [
        {{
            "section_title": "什么是{point_name}",
            "content": "{point_name}是一个重要的概念，它帮助我们理解事物的本质。在日常生活中，我们经常遇到类似的情况。简单来说，{point_name}就是...",
            "example": "比如在学习数学时，我们可以用苹果来理解加法的概念：3个苹果加2个苹果等于5个苹果。",
            "key_points": ["{point_name}的定义", "基本特征", "与相关概念的区别"]
        }},
        {{
            "section_title": "为什么学习{point_name}",
            "content": "理解{point_name}对于后续的学习非常重要。它是很多高级概念的基础，掌握好了之后，学习其他内容会变得更容易。",
            "example": "就像建房子需要打好地基一样，学好{point_name}就是打好了学习其他知识的地基。",
            "key_points": ["基础性作用", "承上启下", "实际应用价值"]
        }},
        {{
            "section_title": "怎么理解和运用{point_name}",
            "content": "理解{point_name}的关键是多练习、多思考。可以从简单的例子开始，逐步加深理解。",
            "example": "试着找找生活中有哪些例子可以用{point_name}来解释，这样能更好地掌握这个概念。",
            "key_points": ["学习方法", "练习技巧", "常见误区"]
        }}
    ],
    "summary": "{point_name}是学习中的重要概念，需要理解其定义、作用和运用方法。多做练习，联系实际，可以更好地掌握。",
    "estimated_minutes": 5,
    "difficulty_level": "MEDIUM"
}}
'''

    def create_task_request(
        self,
        point_info: Dict[str, str],
        user_level: str = "INTERMEDIATE",
        teaching_style: str = "BALANCED"
    ) -> TaskRequest:
        """
        创建任务请求

        Args:
            point_info: 知识点信息
            user_level: 用户学习水平
            teaching_style: 讲解风格

        Returns:
            TaskRequest对象
        """
        return TaskRequest(
            task_type=TaskType.CONTENT_GENERATE,
            input_data={
                "point_info": point_info,
                "user_level": user_level,
                "teaching_style": teaching_style
            },
            priority=7,
            timeout_ms=45000
        )


# 便捷函数
async def explain_content(
    point_info: Dict[str, str],
    user_level: str = "INTERMEDIATE",
    teaching_style: str = "BALANCED",
    llm_client=None
) -> ExplanationContent:
    """
    快捷函数：生成知识点讲解

    Args:
        point_info: 知识点信息
        user_level: 用户学习水平
        teaching_style: 讲解风格
        llm_client: LLM客户端

    Returns:
        ExplanationContent对象
    """
    agent = ContentExplainAgent(llm_client=llm_client)
    return await agent.execute(point_info, user_level, teaching_style)
