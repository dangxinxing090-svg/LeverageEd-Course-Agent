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

2. 重点知识点标注标准（is_key_point）
- **核心隐喻**：重点知识点是这个主题的"承重墙"——没有它，整个知识体系会坍塌
- **标注原则**：极少数知识点才是承重墙，大部分知识点是"填充墙"
- **严格判断标准**（必须同时满足以下2条以上才可标为重点）：
  ① 移除后，后续大量知识点（半数以上）失去学习基础
  ② 它是这个主题最底层的基石概念，其他知识点建立在它之上
  ③ 不掌握它，整个知识体系无法成立
- **比例约束**：重点知识点数量应控制在总知识点数的 25%-35% 左右
- **反例**（以下情况不应标为重点）：
  - 仅仅是"有用"或"重要"的知识点
  - 仅仅是某个子领域的入口，而非全局基石
  - 可以通过实践自然掌握，不需要专门重点学习的知识点
- **注意事项**：
  - 不要把"重要"和"重点"混淆，大多数知识点都重要，但只有承重墙级别的才是重点
  - 如果一个主题有10个知识点，重点知识点应该只有3个左右
  - 宁缺毋滥，重点知识点应该让学习者一眼就知道"这是整个体系的基石"

3. 难度标注标准（difficulty）
- **easy**：概念直观，容易理解，学习时间短
- **medium**：需要一定理解和练习，学习时间适中
- **hard**：概念抽象或复杂，需要大量练习和巩固

4. 必须输出内容包含：
① 该学习主题 全景知识版图总览（文字树形大图）
② 完整三层结构化列表 L1→L2→L3

5. 输出格式：
- 先总览全景版图
- 再分层级结构化罗列

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


    EXPLAIN_JSON_PROMPT = """=== 知识向导 ===
=== 你的角色 ===
一位深谙学习之道的引路人。

=== 核心使命 ===
为渴望理解【{topic_name}】的探索者点亮第一盏灯。

=== 价值序列 ===
可理解性 > 完整性
实用性 > 系统性
激发兴趣 > 灌输知识
建立信心 > 展示深度

请以专业知识向导的身份，为我精讲单个知识点，遵循**先直觉、再逻辑、再底层、再实例**，不讲废话，不用晦涩术语，必要时用生活化类比。按以下5个维度输出结构化讲解内容：

## 目标知识信息
- 知识主题：{topic_name}
- 知识：{component_name}

## 维度说明
1. definition - 通俗定义：用一句通俗人话，给知识组件下定义
2. principle - 底层原理：讲底层本质原理，挖到深度层面
3. example - 入门示例：给出极简入门示例和实操案例
4. structure - 核心拆解：拆解核心/结构/组成要素
5. scenario - 适用场景：给出适用场景

请严格按照以下JSON格式输出（只输出JSON，不要输出其他内容）：
{{
  "sections": [
    {{
      "type": "definition",
      "title": "通俗定义",
      "icon": "💡",
      "content": "定义内容..."
    }},
    {{
      "type": "principle",
      "title": "底层原理",
      "icon": "🔬",
      "content": "原理内容..."
    }},
    {{
      "type": "example",
      "title": "入门示例",
      "icon": "📝",
      "content": "示例内容..."
    }},
    {{
      "type": "structure",
      "title": "核心拆解",
      "icon": "🔧",
      "content": "拆解内容..."
    }},
    {{
      "type": "scenario",
      "title": "适用场景",
      "icon": "🎯",
      "content": "场景内容..."
    }},
  ]
}}"""

    EXERCISE_PROMPT = """你是一位实战导师，专注于生成有针对性、注重实操的练习题。

## 核心任务
每次只生成**一道**练习题，必须满足以下标准：

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

## 禁止事项
- 基础概念题（如"什么是RESTful"）
- 纯理论题（如"描述CAP定理"）
- 简单选择题或判断题
- 脱离实际的手写算法题

## 目标知识信息
- 知识主题：{topic_name}
- 知识：{component_name}

请根据以上信息，生成一道针对当前知识的练习题。

请严格按照以下JSON格式输出（只输出JSON，不要其他内容）：
{{
  "questions": [
    {{
      "id": "q-1",
      "type": "practical_qa",
      "content": "完整的题目描述，包含场景背景、约束条件、具体问题",
      "difficulty": "medium"
    }}
  ]
}}"""

    GRADE_PROMPT = """你是一位专业的教师，请批改学生的练习答案。

知识主题：{topic_name}
知识点：{point_name}

题目：
{question_content}

学生答案：
{user_answer}

请按以下JSON格式输出批改结果（只输出JSON，不要输出其他内容）：
{{
  "is_correct": true,
  "user_answer": "学生的答案原文",
  "correct_answer": "如果学生答错，给出正确答案；如果答对，填空字符串",
  "error_analysis": "如果学生答错，指出答案中什么地方出错、为什么错；如果答对，填空字符串",
  "feedback": "对该题回答的整体评价和改进建议"
}}"""

    EXPLAIN_PROMPT = """=== 知识向导 ===
=== 你的角色 ===
一位深谙学习之道的引路人。你知道每个领域都有其隐秘的入口，也知道初学者最容易在哪里迷失。

=== 核心使命 ===
为渴望理解【{knowledge}】的探索者点亮第一盏灯。不是给他们一张地图，而是让他们看懂这片土地的纹理。

=== 价值序列 ===
可理解性 > 完整性
实用性 > 系统性
激发兴趣 > 灌输知识
建立信心 > 展示深度

讲解风格：由浅入深、先直觉再原理、再落地实操，不用晦涩术语，必要时用生活化类比。

请为我详细讲解【{knowledge}】这个知识概念，包括：
1. 通俗定义：用一句通俗人话，讲清它核心是什么、解决什么问题
2. 底层原理：讲底层本质原理，挖到深度层面，不只讲表面
3. 入门示例：给出极简入门示例和实操案例
4. 核心拆解：拆解核心/结构/组成要素，逐条解释每一部分作用
5. 易混对比：对比易混淆知识点，做异同区分，帮我避坑
6. 常见错误：列出新手高频错误、典型误区
7. 适用场景：给出适用场景、什么时候该用、什么时候不该用
"""

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
        data = self._parse_json(result)
        # 后处理：校验并调整重点知识点比例
        return self._validate_and_adjust_key_points(data)

    def _validate_and_adjust_key_points(self, data: dict) -> dict:
        """
        校验并调整重点知识点比例
        
        目标比例：25%-35%
        如果超出范围，按重要性排序，保留最核心的知识点为重点
        """
        if "blocks" not in data:
            return data
        
        # 收集所有知识点
        all_points = []
        for block in data["blocks"]:
            if "points" not in block:
                continue
            for point in block["points"]:
                all_points.append({
                    "block": block,
                    "point": point
                })
        
        if not all_points:
            return data
        
        total_points = len(all_points)
        key_points_count = sum(1 for item in all_points if item["point"].get("is_key_point", False))
        current_ratio = key_points_count / total_points if total_points > 0 else 0
        
        # 目标比例范围：25%-35%
        min_ratio = 0.25
        max_ratio = 0.35
        target_ratio = 0.30  # 目标30%
        
        # 如果比例在合理范围内，不做调整
        if min_ratio <= current_ratio <= max_ratio:
            logger.info(f"重点知识点比例 {current_ratio:.1%} 在合理范围内")
            return data
        
        # 计算目标数量（四舍五入，至少1个，最多不超过总数的25%）
        target_count = max(1, min(int(total_points * target_ratio + 0.5), int(total_points * max_ratio)))
        
        logger.info(f"调整重点知识点数量：{key_points_count} -> {target_count}（总数：{total_points}）")
        
        # 如果当前重点太多，需要减少
        if key_points_count > target_count:
            # 按难度排序，优先保留 hard 和 medium 难度的重点知识点
            # difficulty 优先级：hard > medium > easy
            difficulty_priority = {"hard": 3, "medium": 2, "easy": 1}
            
            # 获取所有当前重点知识点及其优先级
            key_points_with_priority = []
            for item in all_points:
                point = item["point"]
                if point.get("is_key_point", False):
                    difficulty = point.get("difficulty", "medium")
                    priority = difficulty_priority.get(difficulty, 2)
                    key_points_with_priority.append({
                        "item": item,
                        "priority": priority
                    })
            
            # 按优先级排序（高优先级在前）
            key_points_with_priority.sort(key=lambda x: x["priority"], reverse=True)
            
            # 先将所有知识点设为非重点
            for item in all_points:
                item["point"]["is_key_point"] = False
            
            # 保留优先级最高的 target_count 个知识点为重点
            for i, kp in enumerate(key_points_with_priority[:target_count]):
                kp["item"]["point"]["is_key_point"] = True
        
        # 如果当前重点太少，需要增加
        elif key_points_count < target_count:
            # 获取所有非重点知识点
            non_key_points = [item for item in all_points if not item["point"].get("is_key_point", False)]
            
            # 按难度排序，优先选择 hard 和 medium 难度的知识点作为重点
            difficulty_priority = {"hard": 3, "medium": 2, "easy": 1}
            non_key_points.sort(
                key=lambda x: difficulty_priority.get(x["point"].get("difficulty", "medium"), 2),
                reverse=True
            )
            
            # 选择难度最高的知识点设为重点
            need_add = target_count - key_points_count
            for item in non_key_points[:need_add]:
                item["point"]["is_key_point"] = True
        
        return data

    async def explain_knowledge(self, knowledge_name: str) -> str:
        """讲解单个知识点"""
        prompt = self.EXPLAIN_PROMPT.format(knowledge=knowledge_name)
        return await self._llm_client.generate(
            prompt,
            system_prompt="你是一位专业的教育内容生成专家，擅长深入浅出地讲解知识。",
            max_tokens=4000
        )

    async def explain_knowledge_json(self, knowledge_name: str, topic_name: str = "") -> dict:
        """讲解单个知识组件（结构化JSON输出，含知识体系上下文）"""
        prompt = self.EXPLAIN_JSON_PROMPT.format(
            component_name=knowledge_name,
            topic_name=topic_name or "未知主题",
        )
        result = await self._llm_client.generate(
            prompt,
            system_prompt="你是一位专业的教育内容生成专家，擅长深入浅出地讲解知识。请只输出JSON，不要输出其他内容。",
            max_tokens=4000
        )
        return self._parse_json(result)

    async def generate_exercises(self, component_name: str, topic_name: str = "", count: int = 1) -> dict:
        """生成练习题（每次只出一道中等难度实操性问答题，基于具体知识组件）"""
        prompt = self.EXERCISE_PROMPT.format(
            component_name=component_name,
            topic_name=topic_name or "未知主题"
        )
        result = await self._llm_client.generate(
            prompt,
            system_prompt="你是一位实战导师，专注于生成中等难度、注重实操的练习题，帮助学员巩固理解、学以致用。每次只出一道题，确保质量。",
            max_tokens=4000
        )
        return self._parse_json(result)

    async def grade_answers(self, topic_name: str, point_name: str, question_content: str, user_answer: str) -> dict:
        """批改练习答案（单题）"""
        prompt = self.GRADE_PROMPT.format(
            topic_name=topic_name,
            point_name=point_name,
            question_content=question_content,
            user_answer=user_answer
        )
        result = await self._llm_client.generate(
            prompt,
            system_prompt="你是一位专业的教育批改专家，擅长分析学生答案并给出精准反馈。",
            max_tokens=2000
        )
        return self._parse_json(result)

    async def explain_knowledge_stream(self, knowledge_name: str):
        """流式讲解单个知识点"""
        prompt = self.EXPLAIN_PROMPT.format(knowledge=knowledge_name)
        async for chunk in self._llm_client.generate_stream(
            prompt,
            system_prompt="你是一位专业的教育内容生成专家，擅长深入浅出地讲解知识。",
            max_tokens=4000
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
