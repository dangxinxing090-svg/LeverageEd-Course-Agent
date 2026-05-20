"""
M05 学习支持模块

核心职责：
- UnifiedTeachingAgent：统一教学Agent，负责知识讲解、出题、批改、问答
- CustomExerciseAgent：定制综合练习Agent，负责多知识点综合练习

底层执行逻辑：
1. 知识讲解：接收知识点 → LLM生成7维度结构化讲解 → 返回
2. 练习题生成：接收知识点 → LLM生成针对性练习题 → 返回
3. 题目批改：接收题目+答案 → LLM批改 → 报告 → 返回
4. 实时问答：接收问题+上下文 → LLM回答 → 返回
5. 定制综合练习：多知识点 → LLM生成问答题 → 批改 → 返回

依赖：
- app.agents.llm_providers: LLM Provider 多模型支持
"""
