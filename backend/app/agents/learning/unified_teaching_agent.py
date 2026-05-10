"""
统一教学Agent

合并了原全景知识讲解Agent、知识点讲解Agent、出题和批改Agent的职责。
负责所有教学内容的LLM生成：全景介绍、知识讲解、练习题生成、答案批改。

核心职责：
1. 生成主题全景介绍（知识向导）
2. 拆分三层知识体系
3. 讲解单个知识点（8维度结构化讲解）
4. 生成针对性练习题
5. 批改用户答案并给出反馈
6. 实时问答

所有LLM调用均通过AgentLLMClient直接调用，使用精心设计的Prompt模板。
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from app.agents.llm_providers.agent_adapter import AgentLLMClient
from app.agents.llm_providers.config import ProviderType

logger = logging.getLogger(__name__)


class UnifiedTeachingAgent:
    """统一教学Agent - 合并全景讲解、知识讲解、出题批改"""

    def __init__(self, provider: ProviderType = ProviderType.DOUBAO):
        self._llm_client = AgentLLMClient(provider=provider)

    # ==================== Prompt模板 ====================

    OVERVIEW_PROMPT = """=== 知识向导 ====== 你的角色 ===一位深谙学习之道的引路人。你知道每个领域都有其隐秘的入口，也知道初学者最容易在哪里迷失。=== 核心使命 ===为渴望理解【{topic}】的探索者点亮第一盏灯。不是给他们一张地图，而是让他们看懂这片土地的纹理。=== 引导原则 ===- 先见森林，再看树木——整体图景比细节更重要- 先通脉络，再填血肉——核心概念比周边知识更关键- 先建直觉，再立逻辑——感性认识是理性理解的基础- 先解决"为什么"，再回答"是什么"——动机比定义更能驱动学习=== 价值序列 ===可理解性 > 完整性实用性 > 系统性激发兴趣 > 灌输知识建立信心 > 展示深度=== 呈现智慧 ===像一位经验丰富的登山向导：知道哪条路最适合初学者，哪些风景不容错过，哪里需要停下来适应，哪里可以加快脚步。你的材料应该让学习者感到："原来这个领域是这样的格局！"=== 终极目标 ===让学习者在最短时间内获得"我能学会这个"的信心，和"我知道该往哪个方向深入"的方向感。"""

    SPLIT_PROMPT = """请为我指定的学习主题，搭建标准三层知识体系全景版图，严格分为：
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

现在学习主题为：【{topic}】

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

    EXPLAIN_PROMPT = """请以专业知识向导的身份，为我精讲单个知识点，遵循以下固定讲解结构：
1. 先用一句通俗人话，给知识点下定义，讲清它核心是什么、解决什么问题
2. 再讲底层本质原理，挖到深度层面，不只讲表面
3. 给出极简入门示例 + 实操案例
4. 拆解核心/结构/组成要素，逐条解释每一部分作用
5. 对比易混淆知识点，做异同区分，帮我避坑
6. 列出新手高频错误、典型误区
7. 给出适用场景、什么时候该用、什么时候不该用
8. 最后总结一句核心口诀，方便记忆
讲解风格：由浅入深、先直觉再原理、再落地实操，不用晦涩术语，必要时用生活化类比，结构清晰、分层讲解。
现在要讲解的知识点：【{knowledge}】"""

    EXERCISE_PROMPT = """你是一位资深的技术面试官和实战导师，专注于生成高质量、有深度的实操性练习题。

## 核心任务
每次只生成**一道**练习题，必须满足以下标准：

### 难度要求
- 高级难度：不是基础概念背诵，而是需要综合运用多个知识点
- 场景复杂：涉及真实业务场景中的多维度问题
- 陷阱设计：包含容易忽略的细节或常见误区

### 实操性要求
- 真实场景：基于实际工作/项目中的真实问题改编
- 可执行：学员可以动手实践验证答案
- 工具/技术明确：涉及具体的技术栈、工具或框架

### 实用性要求
- 解决痛点：针对实际工作中常见难题
- 经验沉淀：考察最佳实践和工程化思维
- 举一反三：学完后能应用到类似场景

## 题目类型（随机选择一种）

### 1. 故障排查类
场景：描述一个复杂的生产环境问题，给出症状描述、日志片段或监控信息，包含多个可能的原因线索，需要系统性分析才能定位根因。
方向：性能瓶颈分析、分布式系统一致性问题、并发竞争或死锁问题、数据异常或丢失问题。

### 2. 方案设计类
场景：给定业务需求和技术约束，需要权衡多个技术选型，考虑性能、可用性、扩展性、成本，需要给出架构设计或核心代码。
方向：高并发系统架构设计、数据一致性保障方案、海量数据存储/查询优化、微服务拆分与治理。

### 3. 代码优化类
场景：给出一段有问题的代码或低效实现，代码能运行但存在隐患或性能问题，需要指出3个以上改进点并给出重构代码。
方向：算法复杂度优化、内存泄漏/资源未释放、并发安全问题、SQL/查询性能优化。

### 4. 安全攻防类
场景：描述一个安全漏洞或攻击场景，需要理解攻击原理和利用条件，给出防御方案和修复代码，考虑纵深防御策略。
方向：Web安全漏洞、加密/签名方案设计、API安全防护、数据脱敏与隐私保护。

### 5. 工程实践类
场景：给出一个工程化场景和挑战，涉及DevOps/CI/CD/监控/测试等实践，需要设计完整的流程或脚本，考虑可维护性和自动化。
方向：自动化部署流水线设计、监控告警体系搭建、测试策略与质量保障、容灾备份与恢复方案。

## 出题原则
1. 一题一练：每次只输出一道题，确保质量
2. 场景新鲜：避免经典面试题，使用真实案例改编
3. 答案开放：允许有多个合理答案，鼓励深度思考
4. 紧跟趋势：涉及云原生、AI工程、现代架构等前沿技术

## 禁止事项
- 基础概念题（如"什么是RESTful"）
- 纯理论题（如"描述CAP定理"）
- 简单选择题或判断题
- 脱离实际的手写算法题

## 当前知识点信息
- 知识点：{knowledge}
- 所属板块：{block}

请根据以上知识点，生成一道符合标准的高质量实操性问答题。

请严格按照以下JSON格式输出（只输出JSON，不要其他内容）：
{{
  "questions": [
    {{
      "id": "q-1",
      "type": "practical_qa",
      "category": "故障排查/方案设计/代码优化/安全攻防/工程实践",
      "content": "完整的题目描述，包含场景背景、约束条件、具体问题",
      "hints": ["提示1：考察方向", "提示2：关键思路", "提示3：易错点"],
      "reference_answer": "详细的参考答案，包含核心结论、分析过程、最佳实践",
      "key_points": ["考察的知识点1", "考察的知识点2", "考察的知识点3"],
      "difficulty": "hard"
    }}
  ]
}}"""

    GRADE_PROMPT = """你是一位专业的教师，请批改学生的练习答案。

知识点：{knowledge}

学生的答案：
{answers}

请按以下JSON格式输出批改结果（只输出JSON）：
{{
  "total_score": 100,
  "correct_count": 3,
  "total_count": 5,
  "details": [
    {{"question_id": "q-1", "is_correct": true, "user_answer": "A", "correct_answer": "A"}},
    {{"question_id": "q-2", "is_correct": false, "user_answer": "B", "correct_answer": "A"}}
  ],
  "feedback": "整体评价和改进建议"
}}"""

    QA_PROMPT = """你是一位耐心的AI学习助手。用户正在学习一个知识点，请针对用户的问题给出清晰、准确的回答。
回答要求：
- 通俗易懂，避免过于专业的术语
- 适当举例说明
- 如果问题与当前知识点相关，结合知识点内容回答
- 回答简洁，不超过300字

用户问题：{question}"""

    # ==================== 核心方法 ====================

    async def generate_overview(self, topic: str) -> str:
        """生成主题全景介绍"""
        prompt = self.OVERVIEW_PROMPT.format(topic=topic)
        return await self._llm_client.generate(
            prompt,
            system_prompt="你是一位专业的教育内容生成专家。",
            max_tokens=4000
        )

    async def split_knowledge(self, topic: str) -> dict:
        """拆分三层知识体系"""
        prompt = self.SPLIT_PROMPT.format(topic=topic)
        result = await self._llm_client.generate(
            prompt,
            system_prompt="你是一位专业的教育内容生成专家，擅长结构化知识体系搭建。请只输出JSON，不要输出其他内容。",
            max_tokens=8000
        )
        return self._parse_json(result)

    async def explain_knowledge(self, knowledge_name: str) -> str:
        """讲解单个知识点"""
        prompt = self.EXPLAIN_PROMPT.format(knowledge=knowledge_name)
        return await self._llm_client.generate(
            prompt,
            system_prompt="你是一位专业的教育内容生成专家，擅长深入浅出地讲解知识。",
            max_tokens=4000
        )

    async def generate_exercises(self, knowledge_name: str, block_name: str = "", count: int = 1) -> dict:
        """生成练习题（每次只出一道高难度实操性问答题）"""
        prompt = self.EXERCISE_PROMPT.format(
            knowledge=knowledge_name,
            block=block_name
        )
        result = await self._llm_client.generate(
            prompt,
            system_prompt="你是一位资深的技术面试官和实战导师，专注于生成高难度、实操性、实用性的问答题。每次只出一道题，确保质量。",
            max_tokens=4000
        )
        return self._parse_json(result)

    async def grade_answers(self, knowledge_name: str, answers_text: str) -> dict:
        """批改练习答案"""
        prompt = self.GRADE_PROMPT.format(knowledge=knowledge_name, answers=answers_text)
        result = await self._llm_client.generate(
            prompt,
            system_prompt="你是一位专业的教育批改专家，擅长分析学生答案并给出精准反馈。",
            max_tokens=2000
        )
        return self._parse_json(result)

    async def answer_question(self, question: str) -> str:
        """实时问答"""
        prompt = self.QA_PROMPT.format(question=question)
        return await self._llm_client.generate(
            prompt,
            system_prompt="你是一位专业的教育AI助手，擅长用通俗易懂的语言解答学习问题。",
            max_tokens=1000
        )

    # ==================== 流式方法 ====================

    async def explain_knowledge_stream(self, knowledge_name: str):
        """流式讲解单个知识点"""
        prompt = self.EXPLAIN_PROMPT.format(knowledge=knowledge_name)
        async for chunk in self._llm_client.generate_stream(
            prompt,
            system_prompt="你是一位专业的教育内容生成专家，擅长深入浅出地讲解知识。",
            max_tokens=4000
        ):
            yield chunk

    async def answer_question_stream(self, question: str):
        """流式问答"""
        prompt = self.QA_PROMPT.format(question=question)
        async for chunk in self._llm_client.generate_stream(
            prompt,
            system_prompt="你是一位专业的教育AI助手，擅长用通俗易懂的语言解答学习问题。",
            max_tokens=1000
        ):
            yield chunk

    # ==================== 工具方法 ====================

    @staticmethod
    def _parse_json(text: str) -> dict:
        """从LLM响应中解析JSON"""
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        code_block = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
        if code_block:
            try:
                return json.loads(code_block.group(1))
            except json.JSONDecodeError:
                pass
        start = text.find('{')
        end = text.rfind('}')
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        raise ValueError(f"无法从LLM响应中解析JSON: {text[:200]}")
