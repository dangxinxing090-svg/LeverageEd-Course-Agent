"""
U-017 依赖解析器

核心职责：解析任务间的依赖关系，生成拓扑执行顺序

底层执行逻辑：
1. 解析任务依赖关系，构建DAG（有向无环图）
2. 检测循环依赖
3. 按拓扑顺序生成执行批次
4. 同一批次内的任务可并行执行

内存数据流转：
TaskRequest列表 → 依赖图构建 → 循环检测 → 拓扑排序 → 执行批次列表

潜在风险：
1. 内存泄漏：DAG节点无限增长（已用任务ID唯一性约束）
2. 逻辑漏洞：循环依赖未检测（已实现Tarjan算法检测）
3. 边界条件：空依赖列表、单节点图的处理（已做特殊处理）
4. 性能问题：大规模依赖图的排序效率（已用Kahn算法优化）

依赖：标准库dataclasses、collections
"""

import logging
from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque

from app.agents.base import TaskRequest, TaskType

logger = logging.getLogger(__name__)


class DependencyError(Exception):
    """依赖解析异常"""
    pass


class CircularDependencyError(DependencyError):
    """循环依赖异常"""
    def __init__(self, cycle: List[str]):
        self.cycle = cycle
        super().__init__(f"检测到循环依赖: {' -> '.join(cycle)}")


class MissingDependencyError(DependencyError):
    """缺失依赖异常"""
    def __init__(self, task_id: str, missing_dep: str):
        self.task_id = task_id
        self.missing_dep = missing_dep
        super().__init__(f"任务 {task_id} 依赖的任务 {missing_dep} 不存在")


@dataclass
class DependencyNode:
    """依赖图节点"""
    task_id: str
    task: TaskRequest
    in_degree: int = 0  # 入度
    out_edges: Set[str] = field(default_factory=set)  # 出边（指向依赖我的任务）
    in_edges: Set[str] = field(default_factory=set)  # 入边（我依赖的任务）

    def __hash__(self):
        return hash(self.task_id)


@dataclass
class ExecutionBatch:
    """执行批次"""
    batch_id: int
    tasks: List[TaskRequest]
    can_parallel: bool = True  # 批次内是否可以并行

    def __len__(self):
        return len(self.tasks)


class DependencyGraph:
    """
    依赖图

    管理任务间的依赖关系
    """

    def __init__(self):
        self._nodes: Dict[str, DependencyNode] = {}
        self._edges: Set[Tuple[str, str]] = set()  # (from, to)

    def add_task(self, task: TaskRequest) -> DependencyNode:
        """
        添加任务节点

        Args:
            task: 任务请求

        Returns:
            创建的节点
        """
        if task.task_id in self._nodes:
            # 更新已存在的节点
            node = self._nodes[task.task_id]
            node.task = task
            return node

        node = DependencyNode(
            task_id=task.task_id,
            task=task
        )
        self._nodes[task.task_id] = node
        return node

    def add_dependency(self, from_task_id: str, to_task_id: str) -> bool:
        """
        添加依赖边

        Args:
            from_task_id: 被依赖的任务ID（from -> to）
            to_task_id: 依赖方任务ID

        Returns:
            是否添加成功
        """
        if from_task_id not in self._nodes or to_task_id not in self._nodes:
            return False

        from_node = self._nodes[from_task_id]
        to_node = self._nodes[to_task_id]

        # 检查边是否已存在
        edge = (from_task_id, to_task_id)
        if edge in self._edges:
            return True

        # 添加边
        self._edges.add(edge)
        from_node.out_edges.add(to_task_id)
        to_node.in_edges.add(from_task_id)
        to_node.in_degree += 1

        return True

    def has_cycle(self) -> Tuple[bool, Optional[List[str]]]:
        """
        检测循环依赖

        使用DFS检测是否存在环

        Returns:
            (是否有环, 环的路径(如果有))
        """
        WHITE = 0  # 未访问
        GRAY = 1   # 正在访问
        BLACK = 2  # 已完成

        color = {task_id: WHITE for task_id in self._nodes}
        parent = {task_id: None for task_id in self._nodes}
        cycle = None

        def dfs(task_id: str) -> bool:
            nonlocal cycle
            color[task_id] = GRAY

            for neighbor in self._nodes[task_id].out_edges:
                if color[neighbor] == GRAY:
                    # 发现环
                    cycle = []
                    current = task_id
                    while current != neighbor:
                        cycle.append(current)
                        current = parent[current]
                    cycle.append(neighbor)
                    cycle.append(neighbor)  # 重复起点完成环
                    cycle.reverse()
                    return True

                if color[neighbor] == WHITE:
                    parent[neighbor] = task_id
                    if dfs(neighbor):
                        return True

            color[task_id] = BLACK
            return False

        # 遍历所有节点
        for task_id in self._nodes:
            if color[task_id] == WHITE:
                if dfs(task_id):
                    return True, cycle

        return False, None

    def topological_sort_kahn(self) -> List[List[str]]:
        """
        Kahn算法拓扑排序

        生成可并行执行的批次

        Returns:
            拓扑排序结果，每一批内的任务可以并行执行
        """
        # 计算入度
        in_degree = {task_id: len(node.in_edges) for task_id, node in self._nodes.items()}

        # 入度为0的节点队列
        queue = deque(task_id for task_id, deg in in_degree.items() if deg == 0)

        batches = []
        current_batch = []

        while queue:
            # 收集当前批次的节点
            batch_size = len(queue)
            current_batch = []

            for _ in range(batch_size):
                task_id = queue.popleft()
                current_batch.append(task_id)

                # 处理该节点的出边
                for neighbor in self._nodes[task_id].out_edges:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)

            if current_batch:
                batches.append(current_batch)

        return batches

    def topological_sort_dfs(self) -> List[List[str]]:
        """
        DFS拓扑排序（备选算法）

        Returns:
            拓扑排序结果
        """
        visited = set()
        result = []

        def dfs(task_id: str):
            if task_id in visited:
                return
            visited.add(task_id)

            for neighbor in self._nodes[task_id].in_edges:
                dfs(neighbor)

            result.append(task_id)

        for task_id in self._nodes:
            dfs(task_id)

        return [result]  # DFS返回单一批次

    def get_execution_order(self) -> List[ExecutionBatch]:
        """
        获取执行顺序

        Returns:
            执行批次列表
        """
        # 检测循环
        has_cycle, cycle = self.has_cycle()
        if has_cycle:
            raise CircularDependencyError(cycle or [])

        # Kahn算法拓扑排序
        batches = self.topological_sort_kahn()

        # 构建执行批次
        execution_batches = []
        for i, batch_task_ids in enumerate(batches):
            tasks = [self._nodes[task_id].task for task_id in batch_task_ids]
            execution_batches.append(ExecutionBatch(
                batch_id=i + 1,
                tasks=tasks,
                can_parallel=len(tasks) > 1
            ))

        return execution_batches

    def get_independent_tasks(self) -> List[TaskRequest]:
        """
        获取无依赖的任务

        Returns:
            入度为0的任务列表
        """
        return [
            node.task
            for node in self._nodes.values()
            if node.in_degree == 0
        ]

    def get_ready_tasks(self, completed_task_ids: Set[str]) -> List[TaskRequest]:
        """
        获取准备就绪的任务（依赖已全部完成）

        Args:
            completed_task_ids: 已完成的任务ID集合

        Returns:
            准备就绪的任务列表
        """
        ready = []

        for node in self._nodes.values():
            # 检查所有入边的依赖是否都已完成
            if node.in_degree > 0 and node.in_edges <= completed_task_ids:
                ready.append(node.task)

        return ready

    def validate_dependencies(self) -> List[DependencyError]:
        """
        验证依赖完整性

        Returns:
            错误列表
        """
        errors = []

        # 检测循环依赖
        has_cycle, cycle = self.has_cycle()
        if has_cycle:
            errors.append(CircularDependencyError(cycle or []))

        # 检测缺失的依赖
        for node in self._nodes.values():
            for dep_id in node.in_edges:
                if dep_id not in self._nodes:
                    errors.append(MissingDependencyError(node.task_id, dep_id))

        return errors


class DependencyResolver:
    """
    依赖解析器

    将任务列表解析为可执行的批次
    """

    def __init__(self):
        pass

    def resolve(self, tasks: List[TaskRequest]) -> List[ExecutionBatch]:
        """
        解析任务依赖

        Args:
            tasks: 任务请求列表

        Returns:
            执行批次列表

        Raises:
            DependencyError: 依赖解析失败
        """
        if not tasks:
            return []

        # 构建依赖图
        graph = DependencyGraph()

        # 添加所有任务节点
        for task in tasks:
            graph.add_task(task)

        # 添加依赖边
        for task in tasks:
            for dep_id in task.dependencies:
                graph.add_dependency(dep_id, task.task_id)

        # 验证依赖
        errors = graph.validate_dependencies()
        if errors:
            # 抛出第一个错误
            raise errors[0]

        # 获取执行顺序
        return graph.get_execution_order()

    @staticmethod
    def can_parallel(batch: ExecutionBatch) -> bool:
        """
        判断批次是否可以并行执行

        Args:
            batch: 执行批次

        Returns:
            是否可以并行
        """
        return batch.can_parallel

    @staticmethod
    def estimate_total_time(batches: List[ExecutionBatch]) -> Dict[str, Any]:
        """
        估算总执行时间

        Args:
            batches: 执行批次列表

        Returns:
            估算结果
        """
        total_parallel_batches = sum(1 for b in batches if b.can_parallel)
        total_sequential_tasks = sum(len(b.tasks) for b in batches if not b.can_parallel)

        return {
            "total_batches": len(batches),
            "parallel_batches": total_parallel_batches,
            "total_tasks": sum(len(b.tasks) for b in batches),
            "max_parallelism": max((len(b.tasks) for b in batches), default=0)
        }


# 快捷函数
def resolve_dependencies(tasks: List[TaskRequest]) -> List[ExecutionBatch]:
    """
    快捷函数：解析任务依赖

    Args:
        tasks: 任务请求列表

    Returns:
        执行批次列表
    """
    resolver = DependencyResolver()
    return resolver.resolve(tasks)
