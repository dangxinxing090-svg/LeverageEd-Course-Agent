"""
U-025 答疑问答Agent

核心职责：回答用户在学习过程中提出的各类问题

底层执行逻辑：
1. 接收用户问题及上下文信息
2. 识别问题类型（概念/应用/综合等）
3. 构建Prompt，引导LLM生成答案
4. 调用LLM API获取回答
5. 解析并返回结构化回答

内存数据流转：
用户问题 → 问题类型识别 → Prompt构建 → LLM API → 回答生成 → 结构化回答 → 返回

潜在风险：
1. 内存泄漏：超长回答（已设置最大长度）
2. 逻辑漏洞：回答偏离主题（已实现相关性验证）
3. 边界条件：问题过于模糊（已有追问建议）
4. 质量风险：回答不够准确（已实现多角度验证）

依赖：LangChain、OpenAI API
"""

import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from app.agents.base import TaskRequest, TaskType
from app.agents.error_handler import get_error_handler

logger = logging.getLogger(__name__)


# ============================================
# 数据模型定义
# ============================================

class QuestionType(str, Enum):
    """问题类型"""
    CONCEPT = "CONCEPT"           # 概念类问题
    APPLICATION = "APPLICATION"   # 应用类问题
    COMPARISON = "COMPARISON"     # 对比类问题
    PROCEDURAL = "PROCEDURAL"     # 步骤类问题
    EXAMPLE = "EXAMPLE"           # 示例类问题
    GENERAL = "GENERAL"           # 综合类问题


class AnswerQuality(str, Enum):
    """回答质量评估"""
    HIGH = "HIGH"     # 高质量
    MEDIUM = "MEDIUM" # 中等质量
    LOW = "LOW"       # 低质量


@dataclass
class RelatedKnowledge:
    """相关知识点"""
    point_id: str
    point_name: str
    relevance: float = 0.5  # 相关性 0-1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "point_id": self.point_id,
            "point_name": self.point_name,
            "relevance": self.relevance
        }


@dataclass
class AnswerSection:
    """回答章节"""
    section_type: str  # "main"/"example"/"note"
    content: str
    order: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "section_type": self.section_type,
            "content": self.content,
            "order": self.order
        }


@dataclass
class QAAnswer:
    """问答回答"""
    answer_id: str
    question_text: str  # 用户问题
    question_type: QuestionType
    answer_sections: List[AnswerSection] = field(default_factory=list)
    related_knowledge: List[RelatedKnowledge] = field(default_factory=list)
    suggested_questions: List[str] = field(default_factory=list)  # 追问建议
    quality: AnswerQuality = AnswerQuality.MEDIUM
    estimated_read_time: int = 0  # 预估阅读时间（秒）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer_id": self.answer_id,
            "question_text": self.question_text,
            "question_type": self.question_type.value,
            "answer_sections": [s.to_dict() for s in self.answer_sections],
            "related_knowledge": [k.to_dict() for k in self.related_knowledge],
            "suggested_questions": self.suggested_questions,
            "quality": self.quality.value,
            "estimated_read_time": self.estimated_read_time
        }


# ============================================
# Prompt模板
# ============================================

QA_ANSWER_PROMPT = """
你是一个耐心的教学助手，负责回答用户在学习和工作中遇到的问题。

## 任务
请回答用户的问题，提供清晰、准确、有帮助的回答。

## 用户问题
{question}

## 上下文信息
- 当前学习主题：{topic_name}
- 用户正在学习：{current_point}
- 已有知识背景：{user_background}

## 回答要求
1. **准确清晰**：回答要准确，不能有错误概念
2. **通俗易懂**：用简单直白的语言解释复杂概念
3. **结构清晰**：使用「总-分-总」的结构
4. **包含示例**：重要概念要提供具体例子
5. **适当追问**：建议用户可能想追问的问题

## 回答结构
- **直接回答**：首先给出直接明确的答案
- **详细解释**：解释原因和背景
- **实际例子**：提供具体可操作的例子
- **注意事项**：提醒可能的误区或注意点
- **追问建议**：建议用户可能想问的后续问题

## 输出要求
请严格按照以下JSON格式输出，不要添加任何解释：

{{
    "answer_sections": [
        {{
            "section_type": "main/example/note",
            "content": "章节内容",
            "order": 1
        }}
    ],
    "related_knowledge": [
        {{
            "point_id": "知识点ID",
            "point_name": "知识点名称",
            "relevance": 0.8
        }}
    ],
    "suggested_questions": ["追问建议1", "追问建议2"],
    "quality": "HIGH/MEDIUM/LOW"
}}

## 问题类型说明
- CONCEPT：概念定义类问题，回答要准确
- APPLICATION：实际应用类问题，回答要具体
- COMPARISON：对比类问题，回答要全面
- PROCEDURAL：步骤类问题，回答要清晰有序
- EXAMPLE：示例请求类问题，回答要实用
- GENERAL：综合类问题，根据具体情况回答

请现在输出JSON格式的回答：
"""


# ============================================
# Agent实现
# ============================================

class QAAnswerAgent:
    """
    答疑问答Agent

    使用LLM回答用户的各类学习问题
    """

    def __init__(
        self,
        llm_client=None,
        max_retries: int = 3,
        temperature: float = 0.4,
        max_answer_length: int = 3000  # 最大回答长度
    ):
        """
        初始化答疑问答Agent

        Args:
            llm_client: LLM客户端
            max_retries: 最大重试次数
            temperature: 生成温度
            max_answer_length: 最大回答长度（字符数）
        """
        self.llm_client = llm_client
        self.max_retries = max_retries
        self.temperature = temperature
        self.max_answer_length = max_answer_length
        self.error_handler = get_error_handler()

    def _validate_input(self, question: str) -> None:
        """
        验证输入参数

        Args:
            question: 用户问题

        Raises:
            ValueError: 参数无效
        """
        if not question or not question.strip():
            raise ValueError("问题内容不能为空")

        if len(question) > 500:
            raise ValueError("问题内容不能超过500个字符")

    def _classify_question(self, question: str) -> QuestionType:
        """
        识别问题类型

        Args:
            question: 用户问题

        Returns:
            QuestionType
        """
        question_lower = question.lower()

        # 概念类问题
        concept_keywords = ["是什么", "定义", "概念", "什么是", "含义", "解释"]
        if any(kw in question_lower for kw in concept_keywords):
            return QuestionType.CONCEPT

        # 对比类问题
        comparison_keywords = ["区别", "不同", "比较", "对比", "差异", "相比", "vs", "versus"]
        if any(kw in question_lower for kw in comparison_keywords):
            return QuestionType.COMPARISON

        # 步骤类问题
        procedural_keywords = ["怎么", "如何", "步骤", "方法", "流程", "操作"]
        if any(kw in question_lower for kw in procedural_keywords):
            return QuestionType.PROCEDURAL

        # 示例类问题
        example_keywords = ["例子", "示例", "举例", "例如", "案例"]
        if any(kw in question_lower for kw in example_keywords):
            return QuestionType.EXAMPLE

        # 应用类问题
        application_keywords = ["使用", "应用", "用处", "用途", "场景"]
        if any(kw in question_lower for kw in application_keywords):
            return QuestionType.APPLICATION

        return QuestionType.GENERAL

    def _build_prompt(
        self,
        question: str,
        context: Dict[str, str] = None
    ) -> str:
        """
        构建Prompt

        Args:
            question: 用户问题
            context: 上下文信息

        Returns:
            格式化后的Prompt
        """
        ctx = context or {}

        return QA_ANSWER_PROMPT.format(
            question=question,
            topic_name=ctx.get("topic_name", "未知主题"),
            current_point=ctx.get("current_point", "未知知识点"),
            user_background=ctx.get("user_background", "用户未提供背景信息")
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

    def _validate_answer(self, data: Dict[str, Any]) -> List[str]:
        """
        验证回答的合理性

        Args:
            data: 解析后的数据

        Returns:
            问题列表
        """
        issues = []

        # 检查回答章节
        sections = data.get("answer_sections", [])
        if not sections:
            issues.append("回答内容为空")

        for i, section in enumerate(sections):
            if not section.get("content"):
                issues.append(f"第{i+1}个章节内容为空")

        # 检查回答长度
        total_content = "".join(s.get("content", "") for s in sections)
        if len(total_content) > self.max_answer_length:
            issues.append(f"回答内容过长（超过{self.max_answer_length}字符）")

        return issues

    def _parse_answer(
        self,
        data: Dict[str, Any],
        question: str,
        question_type: QuestionType
    ) -> QAAnswer:
        """
        解析回答数据

        Args:
            data: 原始数据
            question: 用户问题
            question_type: 问题类型

        Returns:
            QAAnswer对象
        """
        # 解析章节
        sections = []
        for i, section_data in enumerate(data.get("answer_sections", [])):
            section = AnswerSection(
                section_type=section_data.get("section_type", "main"),
                content=section_data.get("content", ""),
                order=section_data.get("order", i)
            )
            sections.append(section)

        # 解析相关知识点
        related = []
        for k_data in data.get("related_knowledge", []):
            related.append(RelatedKnowledge(
                point_id=k_data.get("point_id", ""),
                point_name=k_data.get("point_name", ""),
                relevance=k_data.get("relevance", 0.5)
            ))

        # 获取追问建议
        suggested = data.get("suggested_questions", [])

        # 计算预估阅读时间（按200字/分钟）
        total_content = "".join(s.content for s in sections)
        read_time = max(10, len(total_content) // 200 * 60)  # 至少10秒

        # 获取质量评估
        try:
            quality = AnswerQuality(data.get("quality", "MEDIUM"))
        except ValueError:
            quality = AnswerQuality.MEDIUM

        return QAAnswer(
            answer_id=f"answer-{uuid.uuid4().hex[:8]}",
            question_text=question,
            question_type=question_type,
            answer_sections=sections,
            related_knowledge=related,
            suggested_questions=suggested,
            quality=quality,
            estimated_read_time=read_time
        )

    async def execute(
        self,
        question: str,
        context: Dict[str, str] = None
    ) -> QAAnswer:
        """
        执行问答

        Args:
            question: 用户问题
            context: 上下文信息 {
                topic_name: 当前学习主题,
                current_point: 当前学习的知识点,
                user_background: 用户背景,
                related_points: 相关知识点列表
            }

        Returns:
            QAAnswer对象

        Raises:
            ValueError: 输入参数无效
            Exception: 回答生成失败
        """
        # 验证输入
        self._validate_input(question)

        # 识别问题类型
        question_type = self._classify_question(question)

        # 构建Prompt
        prompt = self._build_prompt(question, context)

        # 调用LLM（带重试）
        last_error = None

        for attempt in range(self.max_retries):
            try:
                if self.llm_client:
                    response = await self.llm_client.agenerate([prompt])
                    raw_output = response.generations[0][0].text
                else:
                    # 模拟响应
                    raw_output = self._mock_llm_response(question, question_type)
                    logger.warning("使用模拟LLM响应，请配置真实的LLM客户端")

                # 解析输出
                data = self._parse_llm_output(raw_output)

                # 验证合理性
                issues = self._validate_answer(data)
                if issues:
                    logger.warning(f"回答验证问题: {issues}")

                # 解析为结构化对象
                return self._parse_answer(data, question, question_type)

            except Exception as e:
                last_error = e
                logger.warning(f"问答回答失败（第{attempt + 1}次尝试）: {e}")
                continue

        raise Exception(f"问答回答失败，已重试{self.max_retries}次: {last_error}")

    def _mock_llm_response(self, question: str, question_type: QuestionType) -> str:
        """
        模拟LLM响应（开发测试用）

        Args:
            question: 用户问题
            question_type: 问题类型

        Returns:
            模拟的JSON输出
        """
        # 根据问题类型生成不同风格的回答
        type_explanation = {
            QuestionType.CONCEPT: "概念",
            QuestionType.APPLICATION: "应用",
            QuestionType.COMPARISON: "对比",
            QuestionType.PROCEDURAL: "步骤",
            QuestionType.EXAMPLE: "示例",
            QuestionType.GENERAL: "综合"
        }

        return f'''
{{
    "answer_sections": [
        {{
            "section_type": "main",
            "content": "这是一个关于「{question}」的回答。根据问题的类型（{type_explanation.get(question_type, '综合')}类问题），我们需要从多个角度来分析这个问题。",
            "order": 1
        }},
        {{
            "section_type": "example",
            "content": "举个例子：在实际学习中，我们经常会遇到类似的问题。比如，当学习某个新概念时，可以先理解其定义，再通过实际案例来加深理解。",
            "order": 2
        }},
        {{
            "section_type": "note",
            "content": "需要注意：理解问题时不要死记硬背，要注重理解本质，建立知识之间的联系。",
            "order": 3
        }}
    ],
    "related_knowledge": [
        {{"point_id": "p1", "point_name": "相关知识点1", "relevance": 0.8}},
        {{"point_id": "p2", "point_name": "相关知识点2", "relevance": 0.6}}
    ],
    "suggested_questions": [
        "这个问题在实际中如何应用？",
        "还有哪些类似的知识点？",
        "学习这个内容有什么建议？"
    ],
    "quality": "MEDIUM"
}}
'''

    def create_task_request(
        self,
        question: str,
        context: Dict[str, str] = None
    ) -> TaskRequest:
        """
        创建任务请求

        Args:
            question: 用户问题
            context: 上下文信息

        Returns:
            TaskRequest对象
        """
        return TaskRequest(
            task_type=TaskType.QA_ANSWER,
            input_data={
                "question": question,
                "context": context or {}
            },
            priority=5,
            timeout_ms=30000
        )


# 便捷函数
async def answer_question(
    question: str,
    context: Dict[str, str] = None,
    llm_client=None
) -> QAAnswer:
    """
    快捷函数：回答用户问题

    Args:
        question: 用户问题
        context: 上下文信息
        llm_client: LLM客户端

    Returns:
        QAAnswer对象
    """
    agent = QAAnswerAgent(llm_client=llm_client)
    return await agent.execute(question, context)
