"""
模拟LLM客户端

用于测试环境，无需真实API Key
返回符合Agent期望的JSON格式响应
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MockLLMClient:
    """
    模拟LLM客户端

    用于测试环境，返回预设的JSON格式响应
    """

    def __init__(self):
        """初始化模拟客户端"""
        self.call_count = 0

    async def agenerate(self, prompts: List[str], **kwargs) -> "MockGenerationResult":
        """
        模拟批量生成

        Args:
            prompts: Prompt列表
            **kwargs: 额外参数

        Returns:
            MockGenerationResult对象
        """
        self.call_count += 1
        generations = []

        for prompt in prompts:
            # 根据Prompt内容生成对应的模拟响应
            mock_text = self._generate_mock_response(prompt)
            gen = MockGeneration(text=mock_text)
            generations.append([gen])

        return MockGenerationResult(
            generations=generations,
            llm_output={"model_name": "mock", "token_usage": 0}
        )

    def _generate_mock_response(self, prompt: str) -> str:
        """
        根据Prompt生成模拟响应

        使用权重评分机制，避免通用关键字误匹配。
        每个模式定义强关键字（权重高）和弱关键字（权重低），
        取得分最高的模式。

        Args:
            prompt: 输入Prompt

        Returns:
            模拟的JSON响应
        """
        # 模式定义：(名称, 强关键字列表, 弱关键字列表, 处理函数)
        patterns = [
            ("exercise",    ["练习题", "出题", "生成.*题"],       ["题目"],         self._mock_exercise),
            ("grade",       ["批改", "评分", "判卷"],             [],               self._mock_grade),
            ("split",       ["拆解", "拆分", "知识体系"],         [],               self._mock_knowledge_split),
            ("encouragement",["鼓励", "奖励", "激励"],            [],               self._mock_encouragement),
            ("qa",          ["用户问题", "回答用户", "追问建议", "问答", "答疑"], ["问题"], self._mock_qa),
            ("difficulty",  ["难度标注", "标注难度"],             ["难度"],          self._mock_difficulty),
            ("explain",     ["讲解内容", "通俗易懂", "讲解"],     ["解释"],          self._mock_content_explain),
        ]

        best_match = None
        best_score = 0

        import re
        for name, strong_kw, weak_kw, handler in patterns:
            score = 0
            # 强关键字：每个 +10 分
            for kw in strong_kw:
                if re.search(kw, prompt):
                    score += 10
            # 弱关键字：每个 +1 分
            for kw in weak_kw:
                if kw in prompt:
                    score += 1
            if score > best_score:
                best_score = score
                best_match = handler

        if best_match and best_score >= 10:
            return best_match(prompt)

        # 默认响应
        return json.dumps({
            "message": "这是一个模拟响应",
            "prompt_preview": prompt[:100]
        }, ensure_ascii=False)

    def _mock_knowledge_split(self, prompt: str) -> str:
        """模拟知识拆分响应"""
        # 尝试提取主题名称
        import re
        match = re.search(r'"([^"]+)"', prompt)
        topic = match.group(1) if match else "学习主题"

        return json.dumps({
            "blocks": [
                {
                    "block_name": f"{topic}基础概念",
                    "block_description": "入门必备基础知识",
                    "points": [
                        {
                            "point_name": "核心概念",
                            "point_description": "理解核心概念",
                            "components": [
                                {"component_name": "基本定义", "learning_objective": "能够解释基本定义"},
                                {"component_name": "关键特性", "learning_objective": "能够识别关键特性"}
                            ]
                        },
                        {
                            "point_name": "基本原理",
                            "point_description": "掌握基本原理",
                            "components": [
                                {"component_name": "原理说明", "learning_objective": "能够说明基本原理"},
                                {"component_name": "应用场景", "learning_objective": "能够识别应用场景"}
                            ]
                        }
                    ]
                },
                {
                    "block_name": f"{topic}实践应用",
                    "block_description": "实际应用技能",
                    "points": [
                        {
                            "point_name": "操作方法",
                            "point_description": "掌握操作方法",
                            "components": [
                                {"component_name": "步骤流程", "learning_objective": "能够执行操作步骤"},
                                {"component_name": "注意事项", "learning_objective": "能够注意关键事项"}
                            ]
                        }
                    ]
                }
            ]
        }, ensure_ascii=False)

    def _mock_content_explain(self, prompt: str) -> str:
        """模拟知识讲解响应"""
        import re
        match = re.search(r'名称[：:]\s*([^\n]+)', prompt)
        point_name = match.group(1).strip() if match else "知识点"

        return json.dumps({
            "sections": [
                {
                    "section_title": f"什么是{point_name}",
                    "content": f"{point_name}是一个重要的概念。简单来说，它帮助我们理解和处理特定类型的问题。在实际应用中，我们经常需要用到这个概念。",
                    "example": f"比如在日常生活中，我们可以用{point_name}来解释很多现象。",
                    "key_points": ["定义清晰", "易于理解", "应用广泛"]
                },
                {
                    "section_title": f"为什么学习{point_name}",
                    "content": f"理解{point_name}对于后续学习非常重要。它是很多高级概念的基础，掌握好了之后，学习其他内容会变得更容易。",
                    "example": "就像建房子需要打好地基一样，学好基础知识就是打好了学习的地基。",
                    "key_points": ["基础性作用", "承上启下", "实际价值"]
                },
                {
                    "section_title": f"如何掌握{point_name}",
                    "content": f"要掌握{point_name}，需要多练习、多思考。可以从简单的例子开始，逐步加深理解。",
                    "example": "试着找找生活中有哪些例子可以用这个概念来解释。",
                    "key_points": ["学习方法", "练习技巧", "常见误区"]
                }
            ],
            "summary": f"{point_name}是学习中的重要概念，需要理解其定义、作用和运用方法。",
            "estimated_minutes": 5,
            "difficulty_level": "MEDIUM"
        }, ensure_ascii=False)

    def _mock_exercise(self, prompt: str) -> str:
        """模拟练习题生成响应"""
        import re
        match = re.search(r'名称[：:]\s*([^\n]+)', prompt)
        point_name = match.group(1).strip() if match else "知识点"

        return json.dumps({
            "questions": [
                {
                    "question_type": "SINGLE_CHOICE",
                    "question_text": f"关于{point_name}，以下说法正确的是？",
                    "options": [
                        {"content": f"{point_name}是基础概念", "is_correct": True},
                        {"content": f"{point_name}与其他知识无关", "is_correct": False},
                        {"content": f"{point_name}不需要理解", "is_correct": False},
                        {"content": f"{point_name}很难掌握", "is_correct": False}
                    ],
                    "explanation": f"{point_name}是基础概念，需要理解和掌握。",
                    "difficulty": "MEDIUM"
                },
                {
                    "question_type": "TRUE_FALSE",
                    "question_text": f"{point_name}对于后续学习很重要。",
                    "correct_answer": "true",
                    "explanation": f"确实，{point_name}是重要的基础知识。",
                    "difficulty": "EASY"
                },
                {
                    "question_type": "FILL_BLANK",
                    "question_text": f"{point_name}的___是学习的重点。",
                    "correct_answer": "核心概念",
                    "explanation": f"理解{point_name}的核心概念很重要。",
                    "difficulty": "MEDIUM"
                },
                {
                    "question_type": "SHORT_ANSWER",
                    "question_text": f"请简述{point_name}的主要特点。",
                    "correct_answer": "1. 基础性 2. 重要性 3. 实用性",
                    "explanation": "从基础性、重要性和实用性三个角度回答。",
                    "difficulty": "HARD"
                },
                {
                    "question_type": "SINGLE_CHOICE",
                    "question_text": f"学习{point_name}的最佳方式是？",
                    "options": [
                        {"content": "多练习多思考", "is_correct": True},
                        {"content": "死记硬背", "is_correct": False},
                        {"content": "只看不练", "is_correct": False},
                        {"content": "跳过不学", "is_correct": False}
                    ],
                    "explanation": "学习需要多练习、多思考才能掌握。",
                    "difficulty": "EASY"
                }
            ]
        }, ensure_ascii=False)

    def _mock_grade(self, prompt: str) -> str:
        """模拟批改响应"""
        return json.dumps({
            "grades": [
                {
                    "question_id": "q-001",
                    "grade_result": "CORRECT",
                    "score": 100,
                    "feedback": "回答正确，理解到位。",
                    "suggestions": []
                }
            ],
            "summary": "表现优秀，继续保持！",
            "improvement_areas": [],
            "strengths": ["概念理解准确", "表述清晰"]
        }, ensure_ascii=False)

    def _mock_qa(self, prompt: str) -> str:
        """模拟问答响应"""
        import re
        match = re.search(r'问[题题]?\s*[：:]\s*([^\n]+)', prompt)
        question = match.group(1).strip() if match else "这个问题"

        return json.dumps({
            "question_type": "CONCEPT",
            "answer_sections": [
                {
                    "section_type": "main",
                    "content": f"关于{question[:20]}，核心在于理解基本概念。简单来说，我们需要从定义出发，逐步深入理解。",
                    "order": 1
                },
                {
                    "section_type": "example",
                    "content": "例如在日常生活中，我们可以用这个概念来解释很多现象。在学习中，掌握好基础知识是关键。",
                    "order": 2
                }
            ],
            "related_knowledge": [
                {"point_id": "point-001", "point_name": "相关知识点1", "relevance": "HIGH"},
                {"point_id": "point-002", "point_name": "相关知识点2", "relevance": "MEDIUM"}
            ],
            "suggested_questions": ["建议复习相关章节", "可以尝试做练习题巩固"],
            "quality": "GOOD"
        }, ensure_ascii=False)

    def _mock_difficulty(self, prompt: str) -> str:
        """模拟难度标注响应"""
        return json.dumps({
            "annotations": [
                {
                    "point_name": "核心概念",
                    "difficulty": "MEDIUM",
                    "importance": "HIGH",
                    "reason": "是后续学习的基础"
                },
                {
                    "point_name": "基本原理",
                    "difficulty": "EASY",
                    "importance": "MEDIUM",
                    "reason": "容易理解，但需要记忆"
                },
                {
                    "point_name": "高级应用",
                    "difficulty": "HARD",
                    "importance": "HIGH",
                    "reason": "需要综合运用多个知识点"
                }
            ]
        }, ensure_ascii=False)

    def _mock_encouragement(self, prompt: str) -> str:
        """模拟鼓励文案响应"""
        import re
        match = re.search(r'用户名[：:]\s*([^\n]+)', prompt)
        user_name = match.group(1).strip() if match else "同学"

        return json.dumps({
            "title": "做得好！",
            "message": f"{user_name}，你的努力值得肯定，继续加油！"
        }, ensure_ascii=False)


class MockGeneration:
    """模拟生成结果"""
    def __init__(self, text: str):
        self.text = text
        self.generation_info = {"finish_reason": "stop"}


class MockGenerationResult:
    """模拟批量生成结果"""
    def __init__(self, generations: List[List[MockGeneration]], llm_output: Dict[str, Any]):
        self.generations = generations
        self.llm_output = llm_output


# 全局模拟客户端实例
_mock_client = None


def get_mock_client() -> MockLLMClient:
    """获取模拟客户端实例"""
    global _mock_client
    if _mock_client is None:
        _mock_client = MockLLMClient()
    return _mock_client
