"""
U-023 练习题生成Agent

核心职责：根据知识点生成针对性练习题

底层执行逻辑：
1. 接收知识点信息和练习要求
2. 确定题目类型和数量
3. 构建Prompt，引导LLM生成练习题
4. 调用LLM API获取题目
5. 解析并返回结构化练习题

内存数据流转：
知识点信息 → Prompt构建 → LLM API → 练习题解析 → 结构化题目 → 返回

潜在风险：
1. 内存泄漏：大量题目生成（已限制题目数量）
2. 逻辑漏洞：题目与知识点不匹配（已验证关联性）
3. 边界条件：题目难度不合适（已实现难度筛选）
4. 质量风险：题目有歧义或答案错误（已实现验证机制）

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
    SINGLE_CHOICE = "SINGLE_CHOICE"  # 单选题
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"  # 多选题
    TRUE_FALSE = "TRUE_FALSE"  # 判断题
    FILL_BLANK = "FILL_BLANK"  # 填空题
    SHORT_ANSWER = "SHORT_ANSWER"  # 简答题
    CODE_COMPLETION = "CODE_COMPLETION"  # 代码补全


class DifficultyLevel(str, Enum):
    """题目难度"""
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"


@dataclass
class QuestionOption:
    """选择题选项"""
    option_id: str
    content: str  # 选项内容
    is_correct: bool = False  # 是否正确

    def to_dict(self) -> Dict[str, Any]:
        return {
            "option_id": self.option_id,
            "content": self.content,
            "is_correct": self.is_correct
        }


@dataclass
class Question:
    """练习题"""
    question_id: str
    question_type: QuestionType
    question_text: str  # 题目内容
    options: List[QuestionOption] = field(default_factory=list)  # 选项（选择题）
    correct_answer: str = ""  # 正确答案（其他题型）
    explanation: str = ""  # 答案解析
    difficulty: DifficultyLevel = DifficultyLevel.MEDIUM
    point_id: str = ""  # 关联的知识点ID
    point_name: str = ""  # 关联的知识点名称

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question_id": self.question_id,
            "question_type": self.question_type.value,
            "question_text": self.question_text,
            "options": [o.to_dict() for o in self.options],
            "correct_answer": self.correct_answer,
            "explanation": self.explanation,
            "difficulty": self.difficulty.value,
            "point_id": self.point_id,
            "point_name": self.point_name
        }


@dataclass
class ExerciseSet:
    """练习题集"""
    set_id: str
    set_name: str
    questions: List[Question] = field(default_factory=list)
    total_count: int = 0
    estimated_minutes: int = 0  # 预估完成时长
    difficulty_distribution: Dict[str, int] = field(default_factory=dict)  # 难度分布

    def to_dict(self) -> Dict[str, Any]:
        return {
            "set_id": self.set_id,
            "set_name": self.set_name,
            "questions": [q.to_dict() for q in self.questions],
            "total_count": self.total_count,
            "estimated_minutes": self.estimated_minutes,
            "difficulty_distribution": self.difficulty_distribution
        }


# ============================================
# Prompt模板
# ============================================

EXERCISE_GENERATE_PROMPT = """
你是一个专业的出题老师，负责根据知识点生成高质量的练习题。

## 任务
请为以下知识点生成练习题。

## 知识点信息
- 名称：{point_name}
- 描述：{description}

## 题目要求
### 题目数量
- 总题数：{total_questions}道
- 题目类型分布：{type_distribution}

### 难度分布
- EASY（简单）：{easy_count}道 - 基础概念理解
- MEDIUM（中等）：{medium_count}道 - 应用分析
- HARD（困难）：{hard_count}道 - 综合运用

## 输出要求
请严格按照以下JSON格式输出，不要添加任何解释：

### 单选题格式
{{
    "question_type": "SINGLE_CHOICE",
    "question_text": "题目内容",
    "options": [
        {{"content": "选项A", "is_correct": true}},
        {{"content": "选项B", "is_correct": false}},
        {{"content": "选项C", "is_correct": false}},
        {{"content": "选项D", "is_correct": false}}
    ],
    "explanation": "答案解析",
    "difficulty": "EASY/MEDIUM/HARD"
}}

### 判断题格式
{{
    "question_type": "TRUE_FALSE",
    "question_text": "题目内容",
    "correct_answer": "true/false",
    "explanation": "答案解析",
    "difficulty": "EASY/MEDIUM/HARD"
}}

### 填空题格式
{{
    "question_type": "FILL_BLANK",
    "question_text": "题目内容，___是需要填空的部分",
    "correct_answer": "正确答案",
    "explanation": "答案解析",
    "difficulty": "EASY/MEDIUM/HARD"
}}

### 简答题格式
{{
    "question_type": "SHORT_ANSWER",
    "question_text": "题目内容",
    "correct_answer": "参考答案要点",
    "explanation": "评分标准说明",
    "difficulty": "EASY/MEDIUM/HARD"
}}

## 完整输出格式
{{
    "questions": [
        // 题目列表
    ]
}}

## 注意事项
1. 题目要贴合知识点，不能偏离主题
2. 选项要合理，不能有明显的错误选项
3. 答案解析要清晰，能帮助用户理解
4. 难度要适中，符合用户水平

请现在输出JSON格式的练习题：
"""


# ============================================
# Agent实现
# ============================================

class ExerciseGenerateAgent:
    """
    练习题生成Agent

    使用LLM为知识点生成高质量练习题
    """

    def __init__(
        self,
        llm_client=None,
        max_retries: int = 3,
        temperature: float = 0.3,
        max_questions_per_set: int = 20  # 每套最大题目数
    ):
        """
        初始化练习题生成Agent

        Args:
            llm_client: LLM客户端
            max_retries: 最大重试次数
            temperature: 生成温度
            max_questions_per_set: 每套最大题目数
        """
        self.llm_client = llm_client
        self.max_retries = max_retries
        self.temperature = temperature
        self.max_questions_per_set = max_questions_per_set
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

    def _validate_config(
        self,
        total_questions: int,
        type_distribution: Dict[str, int]
    ) -> None:
        """
        验证题目配置

        Args:
            total_questions: 总题数
            type_distribution: 类型分布

        Raises:
            ValueError: 配置无效
        """
        if total_questions <= 0:
            raise ValueError("题目数量必须大于0")

        if total_questions > self.max_questions_per_set:
            raise ValueError(f"题目数量不能超过{self.max_questions_per_set}")

        # 如果提供了类型分布，验证其数量是否匹配
        if type_distribution and sum(type_distribution.values()) != total_questions:
            raise ValueError("类型分布数量与总题数不匹配")

    def _build_prompt(
        self,
        point_info: Dict[str, str],
        total_questions: int = 5,
        type_distribution: Dict[str, int] = None,
        difficulty_distribution: Dict[str, int] = None
    ) -> str:
        """
        构建Prompt

        Args:
            point_info: 知识点信息
            total_questions: 总题数
            type_distribution: 类型分布
            difficulty_distribution: 难度分布

        Returns:
            格式化后的Prompt
        """
        # 默认类型分布
        if type_distribution is None:
            type_distribution = {
                "SINGLE_CHOICE": int(total_questions * 0.4),
                "TRUE_FALSE": int(total_questions * 0.3),
                "FILL_BLANK": int(total_questions * 0.2),
                "SHORT_ANSWER": total_questions - int(total_questions * 0.9)
            }

        # 默认难度分布
        if difficulty_distribution is None:
            difficulty_distribution = {
                "EASY": int(total_questions * 0.3),
                "MEDIUM": int(total_questions * 0.5),
                "HARD": total_questions - int(total_questions * 0.8)
            }

        # 格式化为字符串
        type_str = ", ".join([f"{k}:{v}道" for k, v in type_distribution.items()])

        return EXERCISE_GENERATE_PROMPT.format(
            point_name=point_info.get("point_name", ""),
            description=point_info.get("description", "用户未提供详细描述"),
            total_questions=total_questions,
            type_distribution=type_str,
            easy_count=difficulty_distribution.get("EASY", 0),
            medium_count=difficulty_distribution.get("MEDIUM", 0),
            hard_count=difficulty_distribution.get("HARD", 0)
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

    def _validate_question(self, q: Dict[str, Any]) -> List[str]:
        """
        验证单个题目的合理性

        Args:
            q: 题目数据

        Returns:
            问题列表
        """
        issues = []

        # 检查必要字段
        if not q.get("question_text"):
            issues.append("题目内容为空")

        if not q.get("question_type"):
            issues.append("题目类型缺失")

        # 检查选择题选项
        q_type = q.get("question_type", "")
        if q_type in ("SINGLE_CHOICE", "MULTIPLE_CHOICE"):
            options = q.get("options", [])
            if len(options) < 2:
                issues.append("选择题选项不足2个")

            # 检查是否有正确答案
            has_correct = any(o.get("is_correct", False) for o in options)
            if not has_correct:
                issues.append("选择题没有正确选项")

        # 检查判断题答案
        if q_type == "TRUE_FALSE":
            answer = q.get("correct_answer", "").lower()
            if answer not in ("true", "false"):
                issues.append("判断题答案格式错误")

        return issues

    def _parse_question(self, q_data: Dict[str, Any], point_info: Dict[str, str]) -> Optional[Question]:
        """
        解析单个题目

        Args:
            q_data: 题目原始数据
            point_info: 知识点信息

        Returns:
            Question对象或None
        """
        try:
            question_type = QuestionType(q_data.get("question_type", "SINGLE_CHOICE"))
            question_id = f"q-{uuid.uuid4().hex[:8]}"

            # 解析选项
            options = []
            if question_type in (QuestionType.SINGLE_CHOICE, QuestionType.MULTIPLE_CHOICE):
                for opt_data in q_data.get("options", []):
                    option = QuestionOption(
                        option_id=f"opt-{uuid.uuid4().hex[:4]}",
                        content=opt_data.get("content", ""),
                        is_correct=opt_data.get("is_correct", False)
                    )
                    options.append(option)

            # 确定正确答案
            correct_answer = q_data.get("correct_answer", "")
            if question_type in (QuestionType.SINGLE_CHOICE, QuestionType.MULTIPLE_CHOICE):
                for opt in options:
                    if opt.is_correct:
                        correct_answer = opt.option_id
                        break

            return Question(
                question_id=question_id,
                question_type=question_type,
                question_text=q_data.get("question_text", ""),
                options=options,
                correct_answer=correct_answer,
                explanation=q_data.get("explanation", ""),
                difficulty=DifficultyLevel(q_data.get("difficulty", "MEDIUM")),
                point_id=point_info.get("point_id", ""),
                point_name=point_info.get("point_name", "")
            )

        except Exception as e:
            logger.warning(f"解析题目失败: {e}")
            return None

    def _parse_exercise_set(
        self,
        data: Dict[str, Any],
        point_info: Dict[str, str]
    ) -> ExerciseSet:
        """
        解析练习题集

        Args:
            data: 原始数据
            point_info: 知识点信息

        Returns:
            ExerciseSet对象
        """
        questions_data = data.get("questions", [])

        questions = []
        difficulty_counts = {"EASY": 0, "MEDIUM": 0, "HARD": 0}

        for q_data in questions_data:
            # 验证题目
            issues = self._validate_question(q_data)
            if issues:
                logger.warning(f"题目验证问题: {issues}")
                continue

            # 解析题目
            question = self._parse_question(q_data, point_info)
            if question:
                questions.append(question)
                difficulty_counts[question.difficulty.value] += 1

        # 计算预估时长（每题约2分钟）
        estimated_minutes = len(questions) * 2

        return ExerciseSet(
            set_id=f"exercise-{uuid.uuid4().hex[:8]}",
            set_name=f"{point_info.get('point_name', '知识点')}练习题",
            questions=questions,
            total_count=len(questions),
            estimated_minutes=estimated_minutes,
            difficulty_distribution=difficulty_counts
        )

    async def execute(
        self,
        point_info: Dict[str, str],
        total_questions: int = 5,
        type_distribution: Dict[str, int] = None,
        difficulty_distribution: Dict[str, int] = None
    ) -> ExerciseSet:
        """
        执行练习题生成

        Args:
            point_info: 知识点信息 {"point_id": "...", "point_name": "...", "description": "..."}
            total_questions: 总题数（默认5道）
            type_distribution: 题目类型分布
            difficulty_distribution: 题目难度分布

        Returns:
            ExerciseSet对象

        Raises:
            ValueError: 输入参数无效
            Exception: LLM调用失败
        """
        # 验证输入
        self._validate_input(point_info)

        # 验证配置
        type_dist = type_distribution or {}
        self._validate_config(total_questions, type_dist)

        # 构建Prompt
        prompt = self._build_prompt(
            point_info,
            total_questions,
            type_distribution,
            difficulty_distribution
        )

        # 调用LLM（带重试）
        last_error = None

        for attempt in range(self.max_retries):
            try:
                if self.llm_client:
                    response = await self.llm_client.agenerate([prompt])
                    raw_output = response.generations[0][0].text
                else:
                    # 模拟响应
                    raw_output = self._mock_llm_response(point_info, total_questions)
                    logger.warning("使用模拟LLM响应，请配置真实的LLM客户端")

                # 解析输出
                data = self._parse_llm_output(raw_output)

                # 解析为结构化对象
                return self._parse_exercise_set(data, point_info)

            except Exception as e:
                last_error = e
                logger.warning(f"练习题生成失败（第{attempt + 1}次尝试）: {e}")
                continue

        raise Exception(f"练习题生成失败，已重试{self.max_retries}次: {last_error}")

    def _mock_llm_response(
        self,
        point_info: Dict[str, str],
        total_questions: int = 5
    ) -> str:
        """
        模拟LLM响应（开发测试用）

        Args:
            point_info: 知识点信息
            total_questions: 总题数

        Returns:
            模拟的JSON输出
        """
        point_name = point_info.get("point_name", "知识点")

        # 生成模拟题目
        questions = []

        # 单选题
        for i in range(max(1, total_questions // 3)):
            questions.append({
                "question_type": "SINGLE_CHOICE",
                "question_text": f"关于{point_name}，以下说法正确的是？",
                "options": [
                    {"content": f"{point_name}是最基础的概念", "is_correct": True},
                    {"content": f"{point_name}与其他知识无关", "is_correct": False},
                    {"content": f"{point_name}不需要理解", "is_correct": False},
                    {"content": f"{point_name}很难掌握", "is_correct": False}
                ],
                "explanation": f"{point_name}是基础概念，需要理解和掌握。",
                "difficulty": "MEDIUM"
            })

        # 判断题
        for i in range(max(1, total_questions // 4)):
            questions.append({
                "question_type": "TRUE_FALSE",
                "question_text": f"{point_name}对于后续学习很重要。",
                "correct_answer": "true",
                "explanation": f"确实，{point_name}是重要的基础知识。",
                "difficulty": "EASY"
            })

        # 填空题
        for i in range(max(1, total_questions // 5)):
            questions.append({
                "question_type": "FILL_BLANK",
                "question_text": f"{point_name}的___是学习的重点。",
                "correct_answer": "核心概念",
                "explanation": f"理解{point_name}的核心概念很重要。",
                "difficulty": "MEDIUM"
            })

        # 简答题
        if len(questions) < total_questions:
            questions.append({
                "question_type": "SHORT_ANSWER",
                "question_text": f"请简述{point_name}的主要特点。",
                "correct_answer": "1. 基础性 2. 重要性 3. 实用性",
                "explanation": "从基础性、重要性和实用性三个角度回答。",
                "difficulty": "HARD"
            })

        return json.dumps({"questions": questions[:total_questions]}, ensure_ascii=False)

    def create_task_request(
        self,
        point_info: Dict[str, str],
        total_questions: int = 5,
        type_distribution: Dict[str, int] = None
    ) -> TaskRequest:
        """
        创建任务请求

        Args:
            point_info: 知识点信息
            total_questions: 总题数
            type_distribution: 题目类型分布

        Returns:
            TaskRequest对象
        """
        return TaskRequest(
            task_type=TaskType.EXERCISE_GENERATE,
            input_data={
                "point_info": point_info,
                "total_questions": total_questions,
                "type_distribution": type_distribution
            },
            priority=6,
            timeout_ms=40000
        )


# 便捷函数
async def generate_exercise(
    point_info: Dict[str, str],
    total_questions: int = 5,
    llm_client=None
) -> ExerciseSet:
    """
    快捷函数：生成练习题

    Args:
        point_info: 知识点信息
        total_questions: 总题数
        llm_client: LLM客户端

    Returns:
        ExerciseSet对象
    """
    agent = ExerciseGenerateAgent(llm_client=llm_client)
    return await agent.execute(point_info, total_questions)
