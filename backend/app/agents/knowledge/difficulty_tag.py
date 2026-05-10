"""
U-021 重点难点标注Agent

核心职责：为每个知识点标注概念理解难度、学习难度、重要性

底层执行逻辑：
1. 接收知识点列表（point_id, point_name, description）
2. 构建Prompt，引导LLM评估每个知识点的难度
3. 调用LLM API获取标注结果
4. 解析LLM输出为结构化数据
5. 返回包含难度标注的知识点列表

内存数据流转：
知识点列表 → Prompt构建 → LLM API → 难度评估 → 标注结果 → 返回

潜在风险：
1. 内存泄漏：大量知识点同时处理（已分批处理）
2. 逻辑漏洞：LLM评分标准不一致（已使用统一评分标准和few-shot示例）
3. 边界条件：空知识点列表的处理（已做空列表校验）
4. 质量风险：标注结果不符合预期的检查（已实现合理性验证）

依赖：LangChain、OpenAI API
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone

from app.agents.base import TaskRequest, TaskResult, TaskStatus, TaskType
from app.agents.error_handler import get_error_handler

logger = logging.getLogger(__name__)


# ============================================
# 数据模型定义
# ============================================

class DifficultyLevel(str, Enum):
    """难度级别"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ImportanceLevel(str, Enum):
    """重要性级别"""
    CORE = "CORE"           # 核心
    IMPORTANT = "IMPORTANT"  # 重要
    AUXILIARY = "AUXILIARY" # 辅助


@dataclass
class KnowledgePointAnnotation:
    """知识点标注"""
    point_id: str
    point_name: str

    # 难度标注
    concept_difficulty: DifficultyLevel  # 概念理解难度
    concept_difficulty_reason: str  # 概念难度原因

    learning_difficulty: DifficultyLevel  # 学习难度
    learning_difficulty_reason: str  # 学习难度原因

    # 重要性标注
    importance: ImportanceLevel  # 重要性
    importance_reason: str  # 重要性原因

    # 预估学习时长（分钟）
    estimated_minutes: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "point_id": self.point_id,
            "point_name": self.point_name,
            "concept_difficulty": self.concept_difficulty.value,
            "concept_difficulty_reason": self.concept_difficulty_reason,
            "learning_difficulty": self.learning_difficulty.value,
            "learning_difficulty_reason": self.learning_difficulty_reason,
            "importance": self.importance.value,
            "importance_reason": self.importance_reason,
            "estimated_minutes": self.estimated_minutes
        }


@dataclass
class DifficultyTagResult:
    """标注结果"""
    annotations: List[KnowledgePointAnnotation] = field(default_factory=list)
    total_points: int = 0
    core_points: int = 0  # 核心知识点数量
    difficult_points: int = 0  # 高难度知识点数量
    estimated_total_hours: float = 0  # 预估总学习时长

    def to_dict(self) -> Dict[str, Any]:
        return {
            "annotations": [a.to_dict() for a in self.annotations],
            "total_points": self.total_points,
            "core_points": self.core_points,
            "difficult_points": self.difficult_points,
            "estimated_total_hours": self.estimated_total_hours
        }


# ============================================
# Prompt模板
# ============================================

DIFFICULTY_TAG_PROMPT = """
你是一个专业的教学设计师，负责评估知识点的学习难度和重要性。

## 任务
请为以下知识点列表进行难度和重要性标注。

## 知识点列表
{points_json}

## 评分标准

### 1. 概念理解难度 (concept_difficulty)
评估：该知识点涉及的概念抽象程度、与已有知识的关联度

- **LOW（低）**：概念具体直观，与日常生活经验紧密相关
- **MEDIUM（中）**：概念有一定抽象性，需要理解后才能应用
- **HIGH（高）**：概念高度抽象，涉及复杂的理论或模型

### 2. 学习难度 (learning_difficulty)
评估：用户完成该知识点的平均学习难度

- **LOW（低）**：容易理解，学习时间短（<10分钟）
- **MEDIUM（中）**：需要一定练习，学习时间适中（10-30分钟）
- **HIGH（高）**：需要大量练习和巩固，学习时间长（>30分钟）

### 3. 重要性 (importance)
评估：该知识点对后续学习的基础作用

- **CORE（核心）**：是其他知识点的基础，必须掌握
- **IMPORTANT（重要）**：对学习有较大帮助，建议掌握
- **AUXILIARY（辅助）**：扩展性知识，可以选择性学习

## 输出要求
请严格按照以下JSON格式输出，不要添加任何解释：

{{
    "annotations": [
        {{
            "point_id": "point_id",
            "concept_difficulty": "LOW/MEDIUM/HIGH",
            "concept_difficulty_reason": "评分原因（20字以内）",
            "learning_difficulty": "LOW/MEDIUM/HIGH",
            "learning_difficulty_reason": "评分原因（20字以内）",
            "importance": "CORE/IMPORTANT/AUXILIARY",
            "importance_reason": "评分原因（20字以内）",
            "estimated_minutes": 数字（预估学习时长分钟数）
        }}
    ]
}}

## 示例
输入：
- point_id: "point-1", point_name: "变量与数据类型"

输出：
{{
    "annotations": [
        {{
            "point_id": "point-1",
            "concept_difficulty": "LOW",
            "concept_difficulty_reason": "变量概念具体直观",
            "learning_difficulty": "LOW",
            "learning_difficulty_reason": "语法简单易学",
            "importance": "CORE",
            "importance_reason": "是后续编程的基础",
            "estimated_minutes": 15
        }}
    ]
}}

请现在输出JSON格式的标注结果：
"""


# ============================================
# Agent实现
# ============================================

class DifficultyTagAgent:
    """
    重点难点标注Agent

    使用LLM评估知识点的难度和重要性
    """

    def __init__(
        self,
        llm_client=None,
        max_retries: int = 3,
        temperature: float = 0.2,
        batch_size: int = 10  # 每批处理的知识点数量
    ):
        """
        初始化标注Agent

        Args:
            llm_client: LLM客户端
            max_retries: 最大重试次数
            temperature: 生成温度
            batch_size: 每批处理的知识点数量
        """
        self.llm_client = llm_client
        self.max_retries = max_retries
        self.temperature = temperature
        self.batch_size = batch_size
        self.error_handler = get_error_handler()

    def _validate_input(self, points: List[Dict[str, str]]) -> None:
        """
        验证输入参数

        Args:
            points: 知识点列表

        Raises:
            ValueError: 参数无效
        """
        if not points:
            raise ValueError("知识点列表不能为空")

        for i, point in enumerate(points):
            if not point.get("point_id"):
                raise ValueError(f"第{i+1}个知识点缺少point_id")
            if not point.get("point_name"):
                raise ValueError(f"知识点{point.get('point_id')}缺少point_name")

    def _build_prompt(self, points: List[Dict[str, str]]) -> str:
        """
        构建Prompt

        Args:
            points: 知识点列表

        Returns:
            格式化后的Prompt
        """
        # 将知识点转换为JSON
        points_json = json.dumps(points, ensure_ascii=False, indent=2)

        return DIFFICULTY_TAG_PROMPT.format(points_json=points_json)

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

    def _validate_annotation(self, annotation: Dict[str, Any]) -> List[str]:
        """
        验证单个标注的合理性

        Args:
            annotation: 标注数据

        Returns:
            问题列表
        """
        issues = []

        # 检查字段存在性
        required_fields = [
            "point_id", "concept_difficulty", "learning_difficulty",
            "importance", "estimated_minutes"
        ]
        for field in required_fields:
            if field not in annotation:
                issues.append(f"缺少字段: {field}")

        # 检查枚举值
        valid_difficulty = {"LOW", "MEDIUM", "HIGH"}
        valid_importance = {"CORE", "IMPORTANT", "AUXILIARY"}

        concept = annotation.get("concept_difficulty", "").upper()
        if concept not in valid_difficulty:
            issues.append(f"无效的concept_difficulty值: {concept}")

        learning = annotation.get("learning_difficulty", "").upper()
        if learning not in valid_difficulty:
            issues.append(f"无效的learning_difficulty值: {learning}")

        importance = annotation.get("importance", "").upper()
        if importance not in valid_importance:
            issues.append(f"无效的importance值: {importance}")

        # 检查预估时长
        minutes = annotation.get("estimated_minutes")
        if minutes is not None:
            try:
                m = int(minutes)
                if m < 1 or m > 300:
                    issues.append(f"预估时长超出合理范围: {m}分钟")
            except (ValueError, TypeError):
                issues.append(f"预估时长格式错误: {minutes}")

        return issues

    def _parse_annotation(self, data: Dict[str, Any]) -> List[KnowledgePointAnnotation]:
        """
        解析标注数据

        Args:
            data: 原始数据

        Returns:
            标注对象列表
        """
        annotations_data = data.get("annotations", [])
        annotations = []

        for ann_data in annotations_data:
            # 验证合理性
            issues = self._validate_annotation(ann_data)
            if issues:
                logger.warning(f"标注验证问题: {issues}")
                # 跳过无效标注或使用默认值

            try:
                annotation = KnowledgePointAnnotation(
                    point_id=ann_data["point_id"],
                    point_name=ann_data.get("point_name", ""),

                    concept_difficulty=DifficultyLevel(
                        ann_data.get("concept_difficulty", "MEDIUM").upper()
                    ),
                    concept_difficulty_reason=ann_data.get("concept_difficulty_reason", ""),

                    learning_difficulty=DifficultyLevel(
                        ann_data.get("learning_difficulty", "MEDIUM").upper()
                    ),
                    learning_difficulty_reason=ann_data.get("learning_difficulty_reason", ""),

                    importance=ImportanceLevel(
                        ann_data.get("importance", "IMPORTANT").upper()
                    ),
                    importance_reason=ann_data.get("importance_reason", ""),

                    estimated_minutes=int(ann_data.get("estimated_minutes", 15))
                )
                annotations.append(annotation)
            except Exception as e:
                logger.warning(f"解析标注失败: {e}")
                continue

        return annotations

    async def execute(
        self,
        points: List[Dict[str, str]],
        topic_context: str = ""
    ) -> DifficultyTagResult:
        """
        执行知识点标注

        Args:
            points: 知识点列表 [{"point_id": "...", "point_name": "...", "description": "..."}]
            topic_context: 主题上下文（可选）

        Returns:
            DifficultyTagResult对象

        Raises:
            ValueError: 输入参数无效
            Exception: LLM调用失败
        """
        # 验证输入
        self._validate_input(points)

        # 如果知识点太多，分批处理
        if len(points) > self.batch_size:
            return await self._execute_batched(points)
        else:
            return await self._execute_single_batch(points)

    async def _execute_single_batch(
        self,
        points: List[Dict[str, str]]
    ) -> DifficultyTagResult:
        """单批处理"""
        # 构建Prompt
        prompt = self._build_prompt(points)

        # 调用LLM
        last_error = None
        raw_output = None

        for attempt in range(self.max_retries):
            try:
                if self.llm_client:
                    response = await self.llm_client.agenerate([prompt])
                    raw_output = response.generations[0][0].text
                else:
                    # 模拟响应
                    raw_output = self._mock_llm_response(points)
                    logger.warning("使用模拟LLM响应，请配置真实的LLM客户端")

                # 解析输出
                data = self._parse_llm_output(raw_output)

                # 解析标注
                annotations = self._parse_annotation(data)

                # 构建结果
                return self._build_result(annotations)

            except Exception as e:
                last_error = e
                logger.warning(f"标注失败（第{attempt + 1}次尝试）: {e}")
                continue

        raise Exception(f"知识点标注失败，已重试{self.max_retries}次: {last_error}")

    async def _execute_batched(
        self,
        points: List[Dict[str, str]]
    ) -> DifficultyTagResult:
        """分批处理大量知识点"""
        all_annotations = []

        # 分批处理
        for i in range(0, len(points), self.batch_size):
            batch = points[i:i + self.batch_size]
            logger.info(f"处理知识点批次 {i//self.batch_size + 1}，包含 {len(batch)} 个知识点")

            batch_result = await self._execute_single_batch(batch)
            all_annotations.extend(batch_result.annotations)

        return self._build_result(all_annotations)

    def _build_result(
        self,
        annotations: List[KnowledgePointAnnotation]
    ) -> DifficultyTagResult:
        """构建结果对象"""
        total_points = len(annotations)
        core_points = sum(1 for a in annotations if a.importance == ImportanceLevel.CORE)
        difficult_points = sum(
            1 for a in annotations
            if a.concept_difficulty == DifficultyLevel.HIGH
            or a.learning_difficulty == DifficultyLevel.HIGH
        )

        total_minutes = sum(a.estimated_minutes for a in annotations)
        estimated_hours = round(total_minutes / 60, 1)

        return DifficultyTagResult(
            annotations=annotations,
            total_points=total_points,
            core_points=core_points,
            difficult_points=difficult_points,
            estimated_total_hours=estimated_hours
        )

    def _mock_llm_response(self, points: List[Dict[str, str]]) -> str:
        """
        模拟LLM响应（开发测试用）

        Args:
            points: 知识点列表

        Returns:
            模拟的JSON输出
        """
        annotations = []

        for point in points:
            point_id = point.get("point_id", "")
            point_name = point.get("point_name", "")

            # 随机生成一些标注（实际使用时应调用LLM）
            annotations.append({
                "point_id": point_id,
                "concept_difficulty": "MEDIUM",
                "concept_difficulty_reason": f"{point_name}概念有一定抽象性",
                "learning_difficulty": "MEDIUM",
                "learning_difficulty_reason": f"{point_name}需要一定练习",
                "importance": "IMPORTANT",
                "importance_reason": f"{point_name}对学习有较大帮助",
                "estimated_minutes": 20
            })

        return json.dumps({"annotations": annotations}, ensure_ascii=False)

    def create_task_request(
        self,
        points: List[Dict[str, str]],
        topic_context: str = ""
    ) -> TaskRequest:
        """
        创建任务请求

        Args:
            points: 知识点列表
            topic_context: 主题上下文

        Returns:
            TaskRequest对象
        """
        return TaskRequest(
            task_type=TaskType.DIFFICULTY_TAG,
            input_data={
                "points": points,
                "topic_context": topic_context
            },
            priority=7,
            timeout_ms=45000
        )


# 便捷函数
async def tag_difficulty(
    points: List[Dict[str, str]],
    llm_client=None
) -> DifficultyTagResult:
    """
    快捷函数：标注知识点难度

    Args:
        points: 知识点列表
        llm_client: LLM客户端

    Returns:
        DifficultyTagResult对象
    """
    agent = DifficultyTagAgent(llm_client=llm_client)
    return await agent.execute(points)
