"""
U-025 定制综合练习Agent

核心职责：
1. 根据用户选择的多个知识点生成综合练习题
2. 对用户提交的答案进行批改

底层执行逻辑：
1. 接收知识点列表
2. 构建Prompt，引导LLM生成覆盖所有知识点的综合练习题
3. 调用LLM API获取题目
4. 解析并返回结构化练习题
5. 接收用户答案，调用LLM进行批改

依赖：LLM Provider
"""

import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================
# 数据模型定义
# ============================================

class QuestionType(str, Enum):
    """题目类型"""
    SINGLE_CHOICE = "SINGLE_CHOICE"
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    TRUE_FALSE = "TRUE_FALSE"
    FILL_BLANK = "FILL_BLANK"
    SHORT_ANSWER = "SHORT_ANSWER"


class DifficultyLevel(str, Enum):
    """题目难度"""
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"


@dataclass
class CustomQuestion:
    """综合练习题"""
    question_id: str
    question_type: QuestionType
    content: str
    options: List[str] = field(default_factory=list)
    correct_answer: str = ""
    explanation: str = ""
    related_points: List[str] = field(default_factory=list)
    difficulty: DifficultyLevel = DifficultyLevel.MEDIUM

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question_id": self.question_id,
            "question_type": self.question_type.value,
            "content": self.content,
            "options": self.options,
            "correct_answer": self.correct_answer,
            "explanation": self.explanation,
            "related_points": self.related_points,
            "difficulty": self.difficulty.value
        }


@dataclass
class CustomExerciseSet:
    """综合练习题集"""
    exercise_id: str
    questions: List[CustomQuestion]
    point_names: List[str]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exercise_id": self.exercise_id,
            "questions": [q.to_dict() for q in self.questions],
            "point_names": self.point_names,
            "created_at": self.created_at
        }


@dataclass
class GradeResult:
    """批改结果"""
    question_id: str
    user_answer: str
    is_correct: bool
    score: float
    feedback: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question_id": self.question_id,
            "user_answer": self.user_answer,
            "is_correct": self.is_correct,
            "score": self.score,
            "feedback": self.feedback
        }


@dataclass
class GradeReport:
    """批改报告"""
    exercise_id: str
    results: List[GradeResult]
    total_score: float
    correct_count: int
    total_count: int
    overall_feedback: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exercise_id": self.exercise_id,
            "results": [r.to_dict() for r in self.results],
            "total_score": self.total_score,
            "correct_count": self.correct_count,
            "total_count": self.total_count,
            "overall_feedback": self.overall_feedback
        }


# ============================================
# Prompt模板
# ============================================

CUSTOM_EXERCISE_PROMPT = """你是一位实战导师，专注于生成有针对性、注重实操的问答题。

## 核心任务
每次只生成**一道**问答题，必须满足以下标准：

### 题型要求（唯一允许的题型，必须严格遵守）
- 只能出问答题（开放性简答题/实操分析题）
- 题目必须包含真实场景背景，要求用户用文字详细作答
- 不要提供选项（A/B/C/D），不要提供填空横线，不要提供判断对错

### 难度要求
- 中等难度：围绕当前知识点的核心概念和应用场景
- 场景贴合：基于实际工作/项目中的常见问题
- 循序渐进：帮助学员巩固理解、学以致用

### 实操性要求
- 真实场景：基于实际工作/项目中的真实问题改编
- 可执行：学员可以动手实践验证答案

### 实用性要求
- 解决痛点：针对实际工作中常见难题
- 经验沉淀：考察最佳实践和工程化思维
- 举一反三：学完后能应用到类似场景

## 出题原则
1. 一题一练：每次只输出一道题，确保质量
2. 难度适中：围绕当前知识点的核心概念，帮助学员巩固理解

## 禁止事项（必须严格遵守）
- 基础概念题（如"什么是RESTful"）
- 纯理论题（如"描述CAP定理"）
- 任何形式的选择题（单选、多选）
- 任何形式的判断题（对错题）
- 任何形式的填空题
- 脱离实际的手写算法题

## 目标知识信息
- 知识主题：{topic_name}
- 知识点：{point_names}

请根据以上信息，生成一道针对当前知识的问答题。

请严格按照以下JSON格式输出（只输出JSON，不要其他内容）：
{{
  "questions": [
    {{
      "id": "q-1",
      "type": "FILL_BLANK",
      "content": "完整的题目描述，包含场景背景、约束条件、具体问题",
      "difficulty": "medium"
    }}
  ]
}}"""

GRADE_PROMPT = """你是一位专业的教育测评专家，请对以下答案进行批改。

## 题目信息
{question_info}

## 用户答案
{user_answer}

## 标准答案
{correct_answer}

## 要求
1. 判断用户答案是否正确（完全正确/部分正确/错误）
2. 给出得分（0-100分）
3. 提供详细的反馈和解析

## 输出格式（严格JSON）
{{
  "is_correct": true/false,
  "score": 100,
  "feedback": "详细反馈内容"
}}

请现在输出JSON格式的批改结果：
"""


# ============================================
# Agent实现
# ============================================

class CustomExerciseAgent:
    """
    定制综合练习Agent
    
    支持多知识点综合练习题生成和答案批改
    """

    def __init__(
        self,
        llm_client=None,
        max_retries: int = 3,
        temperature: float = 0.3
    ):
        """
        初始化Agent
        
        Args:
            llm_client: LLM客户端
            max_retries: 最大重试次数
            temperature: 生成温度
        """
        self.llm_client = llm_client
        self.max_retries = max_retries
        self.temperature = temperature

    def _get_llm_client(self):
        """获取LLM客户端"""
        if self.llm_client:
            return self.llm_client
        
        # 使用AgentLLMClient
        from app.agents.llm_providers.agent_adapter import AgentLLMClient
        return AgentLLMClient()

    async def generate_exercise(
        self,
        topic_name: str,
        point_names: List[str]
    ) -> CustomExerciseSet:
        """
        生成综合练习题
        
        Args:
            topic_name: 知识主题名称
            point_names: 知识点名称列表
            
        Returns:
            CustomExerciseSet: 综合练习题集
        """
        if not point_names:
            raise ValueError("知识点列表不能为空")

        # 构建Prompt
        prompt = CUSTOM_EXERCISE_PROMPT.format(
            topic_name=topic_name,
            point_names="\n".join([f"- {p}" for p in point_names])
        )

        # 调用LLM
        llm = self._get_llm_client()
        response = await llm.generate(prompt, temperature=self.temperature)

        # 解析结果
        questions = self._parse_exercise_response(response)

        # 生成练习题集
        exercise_id = f"custom-{uuid.uuid4().hex[:8]}"
        return CustomExerciseSet(
            exercise_id=exercise_id,
            questions=questions,
            point_names=point_names
        )

    def _parse_exercise_response(self, response: str) -> List[CustomQuestion]:
        """解析LLM返回的练习题"""
        questions = []
        
        try:
            # 提取JSON
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                for idx, q in enumerate(data.get("questions", [])):
                    # 字段映射：支持新prompt格式（id/type/question_text）和旧格式
                    question_id = q.get("id") or f"q-{idx+1}"
                    question_type_raw = q.get("type") or q.get("question_type", "SINGLE_CHOICE")
                    # 类型映射：所有类型统一映射为 FILL_BLANK（前端用 textarea 渲染）
                    type_mapping = {"practical_qa": "FILL_BLANK", "SHORT_ANSWER": "FILL_BLANK"}
                    question_type = type_mapping.get(question_type_raw, "FILL_BLANK")
                    content = q.get("content") or q.get("question_text", "")
                    
                    question = CustomQuestion(
                        question_id=question_id,
                        question_type=QuestionType(question_type),
                        content=content,
                        options=q.get("options", []),
                        correct_answer=q.get("correct_answer", ""),
                        explanation=q.get("explanation", ""),
                        related_points=q.get("related_points", []),
                        difficulty=DifficultyLevel(q.get("difficulty", "MEDIUM").upper())
                    )
                    questions.append(question)
        except Exception as e:
            logger.error(f"解析练习题失败: {e}, response={response[:200]}")
            # 返回一个默认题目
            questions.append(CustomQuestion(
                question_id="q-1",
                question_type=QuestionType.SINGLE_CHOICE,
                content="生成练习题时出错，请重试",
                options=["A. 重试", "B. 取消"],
                correct_answer="A",
                explanation="请重新生成练习题"
            ))

        return questions

    async def grade_answers(
        self,
        exercise_id: str,
        questions: List[Dict[str, Any]],
        user_answers: Dict[str, str]
    ) -> GradeReport:
        """
        批改用户答案
        
        Args:
            exercise_id: 练习ID
            questions: 题目列表
            user_answers: 用户答案 {question_id: answer}
            
        Returns:
            GradeReport: 批改报告
        """
        results = []
        total_score = 0.0
        correct_count = 0

        for q in questions:
            question_id = q.get("question_id", "")
            user_answer = user_answers.get(question_id, "")
            correct_answer = q.get("correct_answer", "")
            
            # 构建题目信息
            question_info = f"题目: {q.get('content', '')}\n"
            if q.get("options"):
                question_info += f"选项: {', '.join(q.get('options', []))}\n"
            question_info += f"题目类型: {q.get('question_type', 'SINGLE_CHOICE')}"

            # 调用LLM批改
            llm = self._get_llm_client()
            prompt = GRADE_PROMPT.format(
                question_info=question_info,
                user_answer=user_answer,
                correct_answer=correct_answer
            )
            
            try:
                response = await llm.generate(prompt, temperature=0.1)
                grade_result = self._parse_grade_response(response, question_id, user_answer)
            except Exception as e:
                logger.error(f"批改失败: {e}")
                # 简单比较
                is_correct = user_answer.strip().upper() == correct_answer.strip().upper()
                grade_result = GradeResult(
                    question_id=question_id,
                    user_answer=user_answer,
                    is_correct=is_correct,
                    score=100.0 if is_correct else 0.0,
                    feedback="自动批改完成" if is_correct else f"正确答案: {correct_answer}"
                )

            results.append(grade_result)
            total_score += grade_result.score
            if grade_result.is_correct:
                correct_count += 1

        # 生成总体反馈
        avg_score = total_score / len(questions) if questions else 0
        if avg_score >= 90:
            overall_feedback = "优秀！你对这些知识点掌握得很好。"
        elif avg_score >= 70:
            overall_feedback = "良好！继续努力，还有提升空间。"
        elif avg_score >= 60:
            overall_feedback = "及格！建议复习相关知识点。"
        else:
            overall_feedback = "需要加强！请认真复习这些知识点。"

        return GradeReport(
            exercise_id=exercise_id,
            results=results,
            total_score=total_score,
            correct_count=correct_count,
            total_count=len(questions),
            overall_feedback=overall_feedback
        )

    def _parse_grade_response(self, response: str, question_id: str, user_answer: str) -> GradeResult:
        """解析批改结果"""
        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                return GradeResult(
                    question_id=question_id,
                    user_answer=user_answer,
                    is_correct=data.get("is_correct", False),
                    score=float(data.get("score", 0)),
                    feedback=data.get("feedback", "")
                )
        except Exception as e:
            logger.error(f"解析批改结果失败: {e}")

        return GradeResult(
            question_id=question_id,
            user_answer=user_answer,
            is_correct=False,
            score=0.0,
            feedback="批改解析失败"
        )
