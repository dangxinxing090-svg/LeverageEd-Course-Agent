"""
M05 学习支持模块

核心职责：
- U-022 知识讲解Agent：生成知识点讲解内容
- U-023 练习题生成Agent：生成针对性练习题
- U-024 题目批改Agent：对用户答案进行批改反馈
- U-025 答疑问答Agent：回答用户的学习问题

底层执行逻辑：
1. 知识讲解：接收知识点 → LLM生成讲解 → 结构化内容 → 返回
2. 练习题生成：接收知识点 → 确定题型难度 → LLM生成 → 结构化题目 → 返回
3. 题目批改：接收题目+答案 → 客观题自动批改 → 主观题LLM批改 → 报告 → 返回
4. 答疑问答：接收问题+上下文 → 识别问题类型 → LLM回答 → 结构化回答 → 返回

内存数据流转：
用户请求 → Agent处理 → Prompt构建 → LLM API → JSON解析 → 结构化数据 → 返回

潜在风险：
1. 内存泄漏：长内容生成（已设置最大长度限制）
2. 逻辑漏洞：内容与知识点不匹配（已实现关联性验证）
3. 边界条件：空输入/超长输入（已做参数校验）
4. 质量风险：生成内容质量不稳定（已实现验证机制）

依赖：
- app.agents.base: TaskRequest, TaskType等基础类型
- app.agents.error_handler: 错误处理器
"""

# ============================================
# 数据模型导出
# ============================================

# U-022 知识讲解相关模型
from app.agents.learning.content_explain import (
    ExplanationSection,      # 讲解章节
    ExplanationContent,      # 完整讲解内容
    ContentExplainAgent,     # 知识讲解Agent
    explain_content,         # 便捷函数
)

# U-023 练习题生成相关模型
from app.agents.learning.exercise_generate import (
    QuestionType,            # 题目类型枚举
    DifficultyLevel,         # 题目难度枚举
    QuestionOption,          # 题目选项
    Question,               # 练习题
    ExerciseSet,             # 练习题集
    ExerciseGenerateAgent,    # 练习题生成Agent
    generate_exercise,       # 便捷函数
)

# U-024 题目批改相关模型
from app.agents.learning.answer_grade import (
    QuestionType as GradeQuestionType,  # 题目类型（别名，避免冲突）
    GradeResult,             # 批改结果枚举
    QuestionGrade,           # 单题批改结果
    GradeReport,             # 完整批改报告
    AnswerGradeAgent,        # 题目批改Agent
    grade_answers,           # 便捷函数
)

# U-025 答疑问答相关模型
from app.agents.learning.qa_answer import (
    QuestionType as QAQuestionType,  # 问题类型（别名，避免冲突）
    AnswerQuality,           # 回答质量评估
    RelatedKnowledge,         # 相关知识点
    AnswerSection,            # 回答章节
    QAAnswer,                 # 问答回答
    QAAnswerAgent,            # 答疑问答Agent
    answer_question,          # 便捷函数
)

# ============================================
# 模块元数据
# ============================================

__all__ = [
    # U-022 知识讲解
    "ExplanationSection",
    "ExplanationContent",
    "ContentExplainAgent",
    "explain_content",

    # U-023 练习题生成
    "QuestionType",
    "DifficultyLevel",
    "QuestionOption",
    "Question",
    "ExerciseSet",
    "ExerciseGenerateAgent",
    "generate_exercise",

    # U-024 题目批改
    "GradeQuestionType",
    "GradeResult",
    "QuestionGrade",
    "GradeReport",
    "AnswerGradeAgent",
    "grade_answers",

    # U-025 答疑问答
    "QAQuestionType",
    "AnswerQuality",
    "RelatedKnowledge",
    "AnswerSection",
    "QAAnswer",
    "QAAnswerAgent",
    "answer_question",
]
