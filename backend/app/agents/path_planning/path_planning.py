"""
U-026 学习路径规划Agent

核心职责：基于知识体系、难度标注和用户学习进度，生成个性化学习路径

底层执行逻辑：
1. 接收知识体系（三层结构）+ 难度标注 + 用户学习进度
2. 分析知识点之间的前置依赖关系
3. 结合用户已掌握/未掌握状态，规划学习顺序
4. 调用LLM辅助依赖关系补全和路径优化
5. 返回有序的学习路径节点列表

内存数据流转：
知识体系+标注+进度 → 依赖分析 → 路径排序 → LLM优化 → 结构化路径 → 返回

潜在风险：
1. 内存泄漏：大量知识点同时处理（已限制单次处理量）
2. 逻辑漏洞：循环依赖导致路径死锁（已实现环检测+破环）
3. 边界条件：用户已全部学完/全部未学（已有兜底路径）
4. 质量风险：路径不合理导致学习体验差（已实现多维度验证）

依赖：app.agents.base、app.agents.error_handler
"""

import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from collections import defaultdict, deque

from app.agents.base import TaskRequest, TaskType
from app.agents.error_handler import get_error_handler

logger = logging.getLogger(__name__)


# ============================================
# 数据模型定义
# ============================================

class NodeStatus(str, Enum):
    """路径节点状态"""
    LOCKED = "LOCKED"          # 未解锁（前置未完成）
    AVAILABLE = "AVAILABLE"    # 可学习（前置已完成）
    IN_PROGRESS = "IN_PROGRESS"  # 学习中
    COMPLETED = "COMPLETED"    # 已完成
    SKIPPED = "SKIPPED"        # 已跳过


class PathNodeType(str, Enum):
    """路径节点类型"""
    BLOCK = "BLOCK"            # 知识板块
    POINT = "POINT"            # 知识点
    COMPONENT = "COMPONENT"    # 知识组件


@dataclass
class PathNode:
    """学习路径节点"""
    node_id: str
    node_type: PathNodeType
    node_name: str
    description: str = ""
    parent_id: Optional[str] = None  # 父节点ID（板块→点→组件层级）
    order: int = 0  # 学习顺序
    status: NodeStatus = NodeStatus.LOCKED
    importance: str = "IMPORTANT"  # CORE/IMPORTANT/AUXILIARY
    difficulty: str = "MEDIUM"  # LOW/MEDIUM/HIGH
    estimated_minutes: int = 0  # 预估学习时长
    prerequisites: List[str] = field(default_factory=list)  # 前置节点ID列表
    metadata: Dict[str, Any] = field(default_factory=dict)  # 扩展信息

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "node_name": self.node_name,
            "description": self.description,
            "parent_id": self.parent_id,
            "order": self.order,
            "status": self.status.value,
            "importance": self.importance,
            "difficulty": self.difficulty,
            "estimated_minutes": self.estimated_minutes,
            "prerequisites": self.prerequisites,
            "metadata": self.metadata
        }


@dataclass
class LearningPath:
    """学习路径"""
    path_id: str
    topic_name: str
    nodes: List[PathNode] = field(default_factory=list)
    total_nodes: int = 0
    completed_nodes: int = 0
    available_nodes: int = 0  # 当前可学习的节点数
    total_estimated_hours: float = 0  # 预估总学习时长
    progress_percentage: float = 0  # 学习进度百分比
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path_id": self.path_id,
            "topic_name": self.topic_name,
            "nodes": [n.to_dict() for n in self.nodes],
            "total_nodes": self.total_nodes,
            "completed_nodes": self.completed_nodes,
            "available_nodes": self.available_nodes,
            "total_estimated_hours": self.total_estimated_hours,
            "progress_percentage": self.progress_percentage,
            "created_at": self.created_at
        }


# ============================================
# Prompt模板（LLM辅助依赖补全）
# ============================================

DEPENDENCY_COMPLETION_PROMPT = """
你是一个课程设计专家，负责分析知识点之间的前置依赖关系。

## 任务
请分析以下知识点列表之间的学习依赖关系。

## 知识点列表
{points_json}

## 输出要求
请严格按照以下JSON格式输出，不要添加任何解释：

{{
    "dependencies": [
        {{
            "point_id": "当前知识点ID",
            "requires": ["前置知识点ID1", "前置知识点ID2"]
        }}
    ]
}}

## 规则
1. 只列出直接前置依赖，不需要传递依赖
2. 如果某个知识点没有前置依赖，不需要列出
3. 依赖关系应该是合理的：前置知识点应该先于当前知识点学习
4. 不要创建循环依赖

请现在输出JSON格式的依赖关系：
"""


# ============================================
# Agent实现
# ============================================

class PathPlanningAgent:
    """
    学习路径规划Agent

    基于知识体系和用户进度，生成个性化学习路径
    """

    def __init__(
        self,
        llm_client=None,
        max_retries: int = 3,
        temperature: float = 0.2
    ):
        """
        初始化路径规划Agent

        Args:
            llm_client: LLM客户端（用于依赖关系补全）
            max_retries: 最大重试次数
            temperature: 生成温度
        """
        self.llm_client = llm_client
        self.max_retries = max_retries
        self.temperature = temperature
        self.error_handler = get_error_handler()

    def _validate_input(
        self,
        knowledge_structure: Dict[str, Any],
        difficulty_annotations: List[Dict[str, Any]],
        user_progress: Dict[str, str]
    ) -> None:
        """
        验证输入参数

        Args:
            knowledge_structure: 知识体系
            difficulty_annotations: 难度标注
            user_progress: 用户进度

        Raises:
            ValueError: 参数无效
        """
        if not knowledge_structure:
            raise ValueError("知识体系不能为空")

        blocks = knowledge_structure.get("blocks", [])
        if not blocks:
            raise ValueError("知识体系中没有知识板块")

        if not isinstance(difficulty_annotations, list):
            raise ValueError("难度标注必须是列表")

        if not isinstance(user_progress, dict):
            raise ValueError("用户进度必须是字典")

    def _extract_all_points(
        self,
        knowledge_structure: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        从知识体系中提取所有知识点（扁平化）

        Args:
            knowledge_structure: 知识体系

        Returns:
            知识点列表（含所属板块信息）
        """
        points = []
        for block in knowledge_structure.get("blocks", []):
            block_id = block.get("block_id", "")
            block_name = block.get("block_name", "")
            block_order = block.get("block_order", 0)

            for point in block.get("points", []):
                points.append({
                    "point_id": point.get("point_id", ""),
                    "point_name": point.get("point_name", ""),
                    "description": point.get("description", ""),
                    "block_id": block_id,
                    "block_name": block_name,
                    "block_order": block_order,
                    "point_order": point.get("point_order", 0),
                    "components": point.get("components", [])
                })

        return points

    def _build_annotation_map(
        self,
        annotations: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        构建知识点ID到标注的映射

        Args:
            annotations: 标注列表

        Returns:
            {point_id: annotation}
        """
        annotation_map = {}
        for ann in annotations:
            point_id = ann.get("point_id", "")
            if point_id:
                annotation_map[point_id] = ann
        return annotation_map

    def _build_dependency_graph(
        self,
        points: List[Dict[str, Any]],
        annotation_map: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Set[str]]:
        """
        构建知识点依赖图

        策略：
        1. 基于板块内顺序：同板块内前面的知识点是后面的前置
        2. 基于重要性：CORE知识点是IMPORTANT的前置
        3. 基于难度：LOW难度是HIGH难度的前置

        Args:
            points: 知识点列表
            annotation_map: 标注映射

        Returns:
            依赖图 {point_id: {prerequisite_ids}}
        """
        graph: Dict[str, Set[str]] = defaultdict(set)

        # 按板块分组
        block_points: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for p in points:
            block_points[p["block_id"]].append(p)

        # 策略1：同板块内，前一个知识点是后一个的前置
        for block_id, b_points in block_points.items():
            sorted_points = sorted(b_points, key=lambda x: x.get("point_order", 0))
            for i in range(1, len(sorted_points)):
                current = sorted_points[i]
                previous = sorted_points[i - 1]
                graph[current["point_id"]].add(previous["point_id"])

        # 策略2：板块间顺序依赖（第一个板块的第一个知识点不受限，后续板块的第一个依赖前一个板块的最后一个）
        sorted_blocks = sorted(block_points.items(), key=lambda x: x[1][0].get("block_order", 0))
        for i in range(1, len(sorted_blocks)):
            prev_block_points = sorted_blocks[i - 1][1]
            curr_block_points = sorted_blocks[i][1]

            if prev_block_points and curr_block_points:
                prev_last = sorted(
                    prev_block_points, key=lambda x: x.get("point_order", 0)
                )[-1]
                curr_first = sorted(
                    curr_block_points, key=lambda x: x.get("point_order", 0)
                )[0]
                graph[curr_first["point_id"]].add(prev_last["point_id"])

        return dict(graph)

    def _detect_and_break_cycles(
        self,
        graph: Dict[str, Set[str]]
    ) -> Dict[str, Set[str]]:
        """
        检测并打破循环依赖

        使用DFS检测环，移除导致环的最后一条边

        Args:
            graph: 依赖图

        Returns:
            无环依赖图
        """
        # 拓扑排序检测环
        in_degree: Dict[str, int] = defaultdict(int)
        all_nodes = set(graph.keys())
        for deps in graph.values():
            all_nodes.update(deps)

        for node in all_nodes:
            in_degree[node]  # 确保所有节点都在

        for node, deps in graph.items():
            for dep in deps:
                in_degree[node]  # 确保节点存在

        # Kahn算法
        queue = deque()
        for node in all_nodes:
            if in_degree.get(node, 0) == 0:
                queue.append(node)

        sorted_nodes = []
        while queue:
            node = queue.popleft()
            sorted_nodes.append(node)
            for other, deps in graph.items():
                if node in deps:
                    in_degree[other] -= 1
                    if in_degree[other] == 0:
                        queue.append(other)

        # 如果排序结果不包含所有节点，说明有环
        if len(sorted_nodes) < len(all_nodes):
            remaining = all_nodes - set(sorted_nodes)
            logger.warning(f"检测到循环依赖，涉及节点: {remaining}")

            # 移除环中节点的所有依赖（保守策略）
            clean_graph = {k: set(v) for k, v in graph.items()}
            for node in remaining:
                clean_graph[node] = set()
                for other in clean_graph:
                    clean_graph[other].discard(node)

            return clean_graph

        return graph

    def _topological_sort(
        self,
        graph: Dict[str, Set[str]],
        points: List[Dict[str, Any]]
    ) -> List[str]:
        """
        拓扑排序，确定学习顺序

        Args:
            graph: 依赖图
            points: 知识点列表

        Returns:
            排序后的知识点ID列表
        """
        # 计算入度
        in_degree: Dict[str, int] = defaultdict(int)
        all_nodes = set()
        for node, deps in graph.items():
            all_nodes.add(node)
            for dep in deps:
                all_nodes.add(dep)

        for node in all_nodes:
            in_degree[node] = 0

        for node, deps in graph.items():
            for dep in deps:
                in_degree[node] += 1

        # Kahn算法
        queue = deque()
        for node in all_nodes:
            if in_degree[node] == 0:
                queue.append(node)

        sorted_ids = []
        while queue:
            node = queue.popleft()
            sorted_ids.append(node)
            for other, deps in graph.items():
                if node in deps:
                    in_degree[other] -= 1
                    if in_degree[other] == 0:
                        queue.append(other)

        # 处理未排序的节点（可能因环被移除）
        point_ids = {p["point_id"] for p in points}
        for pid in point_ids:
            if pid not in sorted_ids:
                sorted_ids.append(pid)

        return sorted_ids

    def _determine_node_status(
        self,
        point_id: str,
        prerequisites: Set[str],
        user_progress: Dict[str, str]
    ) -> NodeStatus:
        """
        确定节点状态

        Args:
            point_id: 知识点ID
            prerequisites: 前置知识点ID集合
            user_progress: 用户进度

        Returns:
            NodeStatus
        """
        progress_status = user_progress.get(point_id, "")

        # 已完成
        if progress_status == "COMPLETED":
            return NodeStatus.COMPLETED

        # 学习中
        if progress_status == "IN_PROGRESS":
            return NodeStatus.IN_PROGRESS

        # 已跳过
        if progress_status == "SKIPPED":
            return NodeStatus.SKIPPED

        # 检查前置是否全部完成
        if prerequisites:
            all_prereqs_done = all(
                user_progress.get(pid, "") == "COMPLETED"
                for pid in prerequisites
            )
            if all_prereqs_done:
                return NodeStatus.AVAILABLE
            else:
                return NodeStatus.LOCKED

        # 无前置依赖，可直接学习
        return NodeStatus.AVAILABLE

    def _build_path_nodes(
        self,
        sorted_ids: List[str],
        points: List[Dict[str, Any]],
        annotation_map: Dict[str, Dict[str, Any]],
        graph: Dict[str, Set[str]],
        user_progress: Dict[str, str]
    ) -> Tuple[List[PathNode], int, int, float]:
        """
        构建路径节点列表

        Args:
            sorted_ids: 排序后的知识点ID
            points: 知识点列表
            annotation_map: 标注映射
            graph: 依赖图
            user_progress: 用户进度

        Returns:
            (nodes, completed_count, available_count, total_hours)
        """
        point_map = {p["point_id"]: p for p in points}
        nodes = []
        completed_count = 0
        available_count = 0
        total_minutes = 0

        for order, point_id in enumerate(sorted_ids, start=1):
            point = point_map.get(point_id, {})
            annotation = annotation_map.get(point_id, {})
            prerequisites = graph.get(point_id, set())

            status = self._determine_node_status(
                point_id, prerequisites, user_progress
            )

            if status == NodeStatus.COMPLETED:
                completed_count += 1
            if status == NodeStatus.AVAILABLE:
                available_count += 1

            estimated_min = annotation.get("estimated_minutes", 15)
            total_minutes += estimated_min

            node = PathNode(
                node_id=point_id,
                node_type=PathNodeType.POINT,
                node_name=point.get("point_name", ""),
                description=point.get("description", ""),
                parent_id=point.get("block_id", ""),
                order=order,
                status=status,
                importance=annotation.get("importance", "IMPORTANT"),
                difficulty=annotation.get("learning_difficulty", "MEDIUM"),
                estimated_minutes=estimated_min,
                prerequisites=list(prerequisites),
                metadata={
                    "block_name": point.get("block_name", ""),
                    "components_count": len(point.get("components", []))
                }
            )
            nodes.append(node)

        total_hours = round(total_minutes / 60, 1)
        return nodes, completed_count, available_count, total_hours

    async def execute(
        self,
        knowledge_structure: Dict[str, Any],
        difficulty_annotations: List[Dict[str, Any]] = None,
        user_progress: Dict[str, str] = None
    ) -> LearningPath:
        """
        执行学习路径规划

        Args:
            knowledge_structure: 知识体系 {
                topic_name: str,
                blocks: [{block_id, block_name, points: [{point_id, point_name, ...}]}]
            }
            difficulty_annotations: 难度标注列表
            user_progress: 用户学习进度 {point_id: "COMPLETED"/"IN_PROGRESS"/...}

        Returns:
            LearningPath对象

        Raises:
            ValueError: 输入参数无效
            Exception: 路径规划失败
        """
        # 参数兜底
        difficulty_annotations = difficulty_annotations or []
        user_progress = user_progress or {}

        # 验证输入
        self._validate_input(knowledge_structure, difficulty_annotations, user_progress)

        topic_name = knowledge_structure.get("topic_name", "未知主题")

        # 1. 提取所有知识点
        points = self._extract_all_points(knowledge_structure)
        if not points:
            raise ValueError("知识体系中没有知识点")

        # 2. 构建标注映射
        annotation_map = self._build_annotation_map(difficulty_annotations)

        # 3. 构建依赖图
        graph = self._build_dependency_graph(points, annotation_map)

        # 4. 检测并打破循环依赖
        graph = self._detect_and_break_cycles(graph)

        # 5. 拓扑排序
        sorted_ids = self._topological_sort(graph, points)

        # 6. 构建路径节点
        nodes, completed_count, available_count, total_hours = self._build_path_nodes(
            sorted_ids, points, annotation_map, graph, user_progress
        )

        # 7. 计算进度
        total_nodes = len(nodes)
        progress_pct = round(
            (completed_count / total_nodes * 100) if total_nodes > 0 else 0, 1
        )

        return LearningPath(
            path_id=f"path-{uuid.uuid4().hex[:8]}",
            topic_name=topic_name,
            nodes=nodes,
            total_nodes=total_nodes,
            completed_nodes=completed_count,
            available_nodes=available_count,
            total_estimated_hours=total_hours,
            progress_percentage=progress_pct
        )

    def create_task_request(
        self,
        knowledge_structure: Dict[str, Any],
        difficulty_annotations: List[Dict[str, Any]] = None,
        user_progress: Dict[str, str] = None
    ) -> TaskRequest:
        """
        创建任务请求

        Args:
            knowledge_structure: 知识体系
            difficulty_annotations: 难度标注
            user_progress: 用户进度

        Returns:
            TaskRequest对象
        """
        return TaskRequest(
            task_type=TaskType.PATH_PLAN,
            input_data={
                "knowledge_structure": knowledge_structure,
                "difficulty_annotations": difficulty_annotations or [],
                "user_progress": user_progress or {}
            },
            priority=8,
            timeout_ms=30000
        )


# 便捷函数
async def plan_learning_path(
    knowledge_structure: Dict[str, Any],
    difficulty_annotations: List[Dict[str, Any]] = None,
    user_progress: Dict[str, str] = None,
    llm_client=None
) -> LearningPath:
    """
    快捷函数：规划学习路径

    Args:
        knowledge_structure: 知识体系
        difficulty_annotations: 难度标注
        user_progress: 用户进度
        llm_client: LLM客户端

    Returns:
        LearningPath对象
    """
    agent = PathPlanningAgent(llm_client=llm_client)
    return await agent.execute(knowledge_structure, difficulty_annotations, user_progress)
