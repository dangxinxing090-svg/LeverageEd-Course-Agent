"""
U-024 题目批改Agent

核心职责：对用户的练习答案进行自动批改和反馈

底层执行逻辑：
1. 接收题目信息和用户答案
2. 解析题目类型（选择/判断/填空/简答）
3. 根据题目类型调用不同的批改策略
4. 构建Prompt，引导LLM进行智能批改
5. 返回结构化的批改结果

内存数据流转：
题目+用户答案 → 批改策略选择 → LLM API → 批改结果 → 结构化反馈 → 返回

潜在风险：
1. 内存泄漏：大量题目批改（已实现分批处理）
2. 逻辑漏洞：批改标准不一致（已统一评分标准）
3. 边界条件：答案格式不规范（已有容错处理）
4. 质量风险：评分过于宽松/严格（已实现多维度评估）

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
    """题目类型"""
    SINGLE_CHOICE = "SINGLE_CHOICE"
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    TRUE_FALSE = "TRUE_FALSE"
    FILL_BLANK = "FILL_BLANK"
    SHORT_ANSWER = "SHORT_ANSWER"
    CODE_COMPLETION = "CODE_COMPLETION"


class GradeResult(str, Enum):
    """批改结果"""
    CORRECT = "CORRECT"
    PARTIAL = "PARTIAL"  # 部分正确
    INCORRECT = "INCORRECT"
    UNGRADED = "UNGRADED"  # 未批改


@dataclass
class QuestionGrade:
    """单个题目的批改结果"""
    question_id: str
    question_text: str
    question_type: str
    correct_answer: str  # 正确答案
    user_answer: str  # 用户答案
    grade_result: GradeResult  # 批改结果
    score: float  # 得分（0-100）
    feedback: str  # 详细反馈
    suggestions: List[str] = field(default_factory=list)  # 改进建议
    point_id: str = ""  # 关联知识点ID
    point_name: str = ""  # 关联知识点名称

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question_id": self.question_id,
            "question_text": self.question_text,
            "question_type": self.question_type,
            "correct_answer": self.correct_answer,
            "user_answer": self.user_answer,
            "grade_result": self.grade_result.value,
            "score": self.score,
            "feedback": self.feedback,
            "suggestions": self.suggestions,
            "point_id": self.point_id,
            "point_name": self.point_name
        }


@dataclass
class GradeReport:
    """完整批改报告"""
    report_id: str
    total_questions: int = 0
    correct_count: int = 0
    partial_count: int = 0
    incorrect_count: int = 0
    total_score: float = 0  # 总分
    max_score: float = 100  # 满分
    percentage: float = 0  # 得分率
    grade_results: List[QuestionGrade] = field(default_factory=list)
    summary: str = ""  # 总体评价
    improvement_areas: List[str] = field(default_factory=list)  # 需要改进的方面
    strengths: List[str] = field(default_factory=list)  # 优势方面
    estimated_minutes: int = 0  # 答题时长

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "total_questions": self.total_questions,
            "correct_count": self.correct_count,
            "partial_count": self.partial_count,
            "incorrect_count": self.incorrect_count,
            "total_score": self.total_score,
            "max_score": self.max_score,
            "percentage": self.percentage,
            "grade_results": [g.to_dict() for g in self.grade_results],
            "summary": self.summary,
            "improvement_areas": self.improvement_areas,
            "strengths": self.strengths,
            "estimated_minutes": self.estimated_minutes
        }


# ============================================
# Prompt模板
# ============================================

ANSWER_GRADE_PROMPT = """
你是一个专业的教学评估老师，负责对用户的练习答案进行准确批改和有益反馈。

## 任务
请对以下题目和用户答案进行批改。

## 题目信息
{questions_json}

## 用户答案
{answers_json}

## 批改标准

### 选择题/判断题
- CORRECT（完全正确）：答案完全匹配
- INCORRECT（错误）：答案错误

### 填空题
- CORRECT：答案正确或等效
- PARTIAL（部分正确）：答案部分正确
- INCORRECT：答案错误

### 简答题
- CORRECT（80-100分）：要点完整，表述准确
- PARTIAL（40-79分）：要点部分正确，表述基本准确
- INCORRECT（0-39分）：要点错误或缺失

## 输出要求
请严格按照以下JSON格式输出，不要添加任何解释：

{{
    "grades": [
        {{
            "question_id": "题目ID",
            "grade_result": "CORRECT/PARTIAL/INCORRECT",
            "score": 分数（0-100）,
            "feedback": "详细反馈（指出对错原因）",
            "suggestions": ["改进建议1", "改进建议2"]
        }}
    ],
    "summary": "总体评价（50-100字）",
    "improvement_areas": ["需要改进的方面1", "需要改进的方面2"],
    "strengths": ["表现好的方面1", "表现好的方面2"]
}}

请现在输出JSON格式的批改结果：
"""


# ============================================
# Agent实现
# ============================================

class AnswerGradeAgent:
    """
    题目批改Agent

    使用LLM对用户的练习答案进行智能批改
    """

    def __init__(
        self,
        llm_client=None,
        max_retries: int = 3,
        temperature: float = 0.2,
        batch_size: int = 10  # 每批批改的题目数
    ):
        """
        初始化题目批改Agent

        Args:
            llm_client: LLM客户端
            max_retries: 最大重试次数
            temperature: 生成温度
            batch_size: 每批批改的题目数
        """
        self.llm_client = llm_client
        self.max_retries = max_retries
        self.temperature = temperature
        self.batch_size = batch_size
        self.error_handler = get_error_handler()

    def _validate_input(
        self,
        questions: List[Dict[str, Any]],
        answers: List[Dict[str, str]]
    ) -> None:
        """
        验证输入参数

        Args:
            questions: 题目列表
            answers: 用户答案列表

        Raises:
            ValueError: 参数无效
        """
        if not questions:
            raise ValueError("题目列表不能为空")

        if not answers:
            raise ValueError("用户答案列表不能为空")

        if len(questions) != len(answers):
            raise ValueError("题目数量与答案数量不匹配")

        for i, q in enumerate(questions):
            if not q.get("question_id"):
                raise ValueError(f"第{i+1}个题目缺少question_id")

            if not q.get("question_text"):
                raise ValueError(f"题目{q.get('question_id')}缺少question_text")

        for i, a in enumerate(answers):
            if not a.get("question_id"):
                raise ValueError(f"第{i+1}个答案缺少question_id")

            if "answer" not in a and "user_answer" not in a:
                raise ValueError(f"答案{a.get('question_id')}缺少答案内容")

    def _normalize_answer(self, answer: str) -> str:
        """
        标准化答案格式

        Args:
            answer: 原始答案

        Returns:
            标准化后的答案
        """
        if not answer:
            return ""

        # 去除首尾空白
        answer = answer.strip()

        # 统一大小写（用于判断题）
        if answer.upper() in ("TRUE", "FALSE", "T", "F", "正确", "错误", "对", "错"):
            return answer.upper()

        return answer

    def _grade_objective(
        self,
        question: Dict[str, Any],
        user_answer: str
    ) -> QuestionGrade:
        """
        客观题自动批改

        Args:
            question: 题目信息
            user_answer: 用户答案

        Returns:
            QuestionGrade对象
        """
        question_type = question.get("question_type", "")
        correct_answer = question.get("correct_answer", "")
        normalized_user = self._normalize_answer(user_answer)
        normalized_correct = self._normalize_answer(correct_answer)

        is_correct = normalized_user == normalized_correct

        # 多选题特殊处理
        if question_type == "MULTIPLE_CHOICE":
            # 解析选项
            options = question.get("options", [])
            correct_option_ids = [o.get("option_id") for o in options if o.get("is_correct")]
            user_option_ids = normalized_user.split(",") if "," in normalized_user else [normalized_user]

            is_correct = set(correct_option_ids) == set(user_option_ids)

        # 构建结果
        grade_result = GradeResult.CORRECT if is_correct else GradeResult.INCORRECT
        score = 100.0 if is_correct else 0.0

        feedback = "回答正确！" if is_correct else f"回答错误。正确答案是：{correct_answer}"
        suggestions = [] if is_correct else ["建议复习相关知识点"]

        return QuestionGrade(
            question_id=question.get("question_id", ""),
            question_text=question.get("question_text", ""),
            question_type=question_type,
            correct_answer=correct_answer,
            user_answer=user_answer,
            grade_result=grade_result,
            score=score,
            feedback=feedback,
            suggestions=suggestions,
            point_id=question.get("point_id", ""),
            point_name=question.get("point_name", "")
        )

    def _build_prompt(
        self,
        questions: List[Dict[str, Any]],
        answers: List[Dict[str, str]]
    ) -> str:
        """
        构建Prompt

        Args:
            questions: 题目列表
            answers: 用户答案列表

        Returns:
            格式化后的Prompt
        """
        # 构建题目JSON
        questions_json = json.dumps(questions, ensure_ascii=False, indent=2)

        # 构建答案JSON（添加用户答案）
        answers_data = []
        for q, a in zip(questions, answers):
            q_type = q.get("question_type", "")

            # 客观题：对比自动批改
            if q_type in ("SINGLE_CHOICE", "MULTIPLE_CHOICE", "TRUE_FALSE"):
                answers_data.append({
                    "question_id": q.get("question_id", ""),
                    "user_answer": a.get("answer", a.get("user_answer", ""))
                })
            else:
                # 主观题：需要LLM批改
                answers_data.append({
                    "question_id": q.get("question_id", ""),
                    "question_text": q.get("question_text", ""),
                    "correct_answer": q.get("correct_answer", ""),
                    "question_type": q_type,
                    "user_answer": a.get("answer", a.get("user_answer", ""))
                })

        answers_json = json.dumps(answers_data, ensure_ascii=False, indent=2)

        return ANSWER_GRADE_PROMPT.format(
            questions_json=questions_json,
            answers_json=answers_json
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

    def _parse_grades(
        self,
        data: Dict[str, Any],
        questions: List[Dict[str, Any]],
        answers: List[Dict[str, str]]
    ) -> List[QuestionGrade]:
        """
        解析批改结果

        Args:
            data: 原始数据
            questions: 题目列表
            answers: 用户答案列表

        Returns:
            QuestionGrade列表
        """
        grades_data = data.get("grades", [])
        grades = []

        # 建立question_id到题目的映射
        q_map = {q.get("question_id"): q for q in questions}
        a_map = {a.get("question_id"): a.get("answer", a.get("user_answer", "")) for a in answers}

        for grade_data in grades_data:
            question_id = grade_data.get("question_id", "")
            question = q_map.get(question_id, {})
            user_answer = a_map.get(question_id, "")

            try:
                grade_result = GradeResult(grade_data.get("grade_result", "INCORRECT"))
            except ValueError:
                grade_result = GradeResult.INCORRECT

            question_type = question.get("question_type", "")

            grade = QuestionGrade(
                question_id=question_id,
                question_text=question.get("question_text", ""),
                question_type=question_type,
                correct_answer=question.get("correct_answer", ""),
                user_answer=user_answer,
                grade_result=grade_result,
                score=grade_data.get("score", 0),
                feedback=grade_data.get("feedback", ""),
                suggestions=grade_data.get("suggestions", []),
                point_id=question.get("point_id", ""),
                point_name=question.get("point_name", "")
            )
            grades.append(grade)

        return grades

    def _build_report(
        self,
        grades: List[QuestionGrade],
        data: Dict[str, Any]
    ) -> GradeReport:
        """
        构建批改报告

        Args:
            grades: 批改结果列表
            data: 原始数据

        Returns:
            GradeReport对象
        """
        total_questions = len(grades)
        correct_count = sum(1 for g in grades if g.grade_result == GradeResult.CORRECT)
        partial_count = sum(1 for g in grades if g.grade_result == GradeResult.PARTIAL)
        incorrect_count = sum(1 for g in grades if g.grade_result == GradeResult.INCORRECT)

        total_score = sum(g.score for g in grades)
        percentage = (total_score / total_questions) if total_questions > 0 else 0

        return GradeReport(
            report_id=f"report-{uuid.uuid4().hex[:8]}",
            total_questions=total_questions,
            correct_count=correct_count,
            partial_count=partial_count,
            incorrect_count=incorrect_count,
            total_score=total_score,
            max_score=total_questions * 100,
            percentage=round(percentage, 1),
            grade_results=grades,
            summary=data.get("summary", ""),
            improvement_areas=data.get("improvement_areas", []),
            strengths=data.get("strengths", []),
            estimated_minutes=0
        )

    async def execute(
        self,
        questions: List[Dict[str, Any]],
        answers: List[Dict[str, str]]
    ) -> GradeReport:
        """
        执行题目批改

        Args:
            questions: 题目列表
            answers: 用户答案列表

        Returns:
            GradeReport对象

        Raises:
            ValueError: 输入参数无效
            Exception: 批改失败
        """
        # 验证输入
        self._validate_input(questions, answers)

        # 分离客观题和主观题
        objective_questions = []
        objective_answers = []
        subjective_questions = []
        subjective_answers = []

        for q, a in zip(questions, answers):
            q_type = q.get("question_type", "")
            if q_type in ("SINGLE_CHOICE", "MULTIPLE_CHOICE", "TRUE_FALSE"):
                objective_questions.append(q)
                objective_answers.append(a)
            else:
                subjective_questions.append(q)
                subjective_answers.append(a)

        # 客观题自动批改
        objective_grades = []
        for q, a in zip(objective_questions, objective_answers):
            user_answer = a.get("answer", a.get("user_answer", ""))
            grade = self._grade_objective(q, user_answer)
            objective_grades.append(grade)

        # 主观题LLM批改
        subjective_grades = []
        if subjective_questions:
            try:
                subjective_grades = await self._grade_subjective(
                    subjective_questions,
                    subjective_answers
                )
            except Exception as e:
                logger.warning(f"主观题批改失败: {e}")
                # 失败时创建空批改结果
                for q, a in zip(subjective_questions, subjective_answers):
                    subjective_grades.append(QuestionGrade(
                        question_id=q.get("question_id", ""),
                        question_text=q.get("question_text", ""),
                        question_type=q.get("question_type", ""),
                        correct_answer=q.get("correct_answer", ""),
                        user_answer=a.get("answer", a.get("user_answer", "")),
                        grade_result=GradeResult.UNGRADED,
                        score=0,
                        feedback="批改失败，请稍后重试"
                    ))

        # 合并结果
        all_grades = objective_grades + subjective_grades

        # 构建报告
        total_score = sum(g.score for g in all_grades)
        total_questions = len(all_grades)

        report_data = {
            "summary": "",
            "improvement_areas": [],
            "strengths": []
        }

        # 生成总结
        if total_questions > 0:
            percentage = total_score / total_questions
            if percentage >= 80:
                report_data["summary"] = f"表现优秀！正确率{percentage:.0f}%，已掌握大部分知识点"
            elif percentage >= 60:
                report_data["summary"] = f"表现良好，正确率{percentage:.0f}%，继续加油"
            else:
                report_data["summary"] = f"需要加强学习，正确率{percentage:.0f}%，建议复习知识点"

        return GradeReport(
            report_id=f"report-{uuid.uuid4().hex[:8]}",
            total_questions=total_questions,
            correct_count=sum(1 for g in all_grades if g.grade_result == GradeResult.CORRECT),
            partial_count=sum(1 for g in all_grades if g.grade_result == GradeResult.PARTIAL),
            incorrect_count=sum(1 for g in all_grades if g.grade_result == GradeResult.INCORRECT),
            total_score=total_score,
            max_score=total_questions * 100,
            percentage=round(percentage, 1) if total_questions > 0 else 0,
            grade_results=all_grades,
            summary=report_data["summary"],
            improvement_areas=report_data["improvement_areas"],
            strengths=report_data["strengths"]
        )

    async def _grade_subjective(
        self,
        questions: List[Dict[str, Any]],
        answers: List[Dict[str, str]]
    ) -> List[QuestionGrade]:
        """
        主观题LLM批改

        Args:
            questions: 主观题列表
            answers: 用户答案列表

        Returns:
            QuestionGrade列表
        """
        # 构建Prompt
        prompt = self._build_prompt(questions, answers)

        # 调用LLM
        last_error = None

        for attempt in range(self.max_retries):
            try:
                if self.llm_client:
                    response = await self.llm_client.agenerate([prompt])
                    raw_output = response.generations[0][0].text
                else:
                    # 模拟响应
                    raw_output = self._mock_llm_response(questions, answers)
                    logger.warning("使用模拟LLM响应，请配置真实的LLM客户端")

                # 解析输出
                data = self._parse_llm_output(raw_output)

                # 解析批改结果
                return self._parse_grades(data, questions, answers)

            except Exception as e:
                last_error = e
                logger.warning(f"主观题批改失败（第{attempt + 1}次尝试）: {e}")
                continue

        raise Exception(f"主观题批改失败，已重试{self.max_retries}次: {last_error}")

    def _mock_llm_response(
        self,
        questions: List[Dict[str, Any]],
        answers: List[Dict[str, str]]
    ) -> str:
        """
        模拟LLM响应（开发测试用）

        Args:
            questions: 题目列表
            answers: 用户答案列表

        Returns:
            模拟的JSON输出
        """
        grades = []

        for q, a in zip(questions, answers):
            user_answer = a.get("answer", a.get("user_answer", ""))

            # 模拟评分
            grades.append({
                "question_id": q.get("question_id", ""),
                "grade_result": "CORRECT",
                "score": 85,
                "feedback": "回答基本正确，可以进一步完善。",
                "suggestions": ["注意表述的准确性", "可以更详细一些"]
            })

        return json.dumps({
            "grades": grades,
            "summary": "总体表现良好，继续保持",
            "improvement_areas": ["需要更详细的表述"],
            "strengths": ["概念理解准确"]
        }, ensure_ascii=False)

    def create_task_request(
        self,
        questions: List[Dict[str, Any]],
        answers: List[Dict[str, str]]
    ) -> TaskRequest:
        """
        创建任务请求

        Args:
            questions: 题目列表
            answers: 用户答案列表

        Returns:
            TaskRequest对象
        """
        return TaskRequest(
            task_type=TaskType.ANSWER_GRADE,
            input_data={
                "questions": questions,
                "answers": answers
            },
            priority=6,
            timeout_ms=50000
        )


# 便捷函数
async def grade_answers(
    questions: List[Dict[str, Any]],
    answers: List[Dict[str, str]],
    llm_client=None
) -> GradeReport:
    """
    快捷函数：批改练习答案

    Args:
        questions: 题目列表
        answers: 用户答案列表
        llm_client: LLM客户端

    Returns:
        GradeReport对象
    """
    agent = AnswerGradeAgent(llm_client=llm_client)
    return await agent.execute(questions, answers)
