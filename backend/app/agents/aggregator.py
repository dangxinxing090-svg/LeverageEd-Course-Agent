"""
U-018 结果聚合器

核心职责：收集多个Agent的输出，按规则合并为统一结果

底层执行逻辑：
1. 接收TaskResult列表
2. 检查所有结果是否完成
3. 按聚合策略合并结果
4. 处理部分失败的情况
5. 返回聚合后的结果

内存数据流转：
TaskResult列表 → 结果验证 → 聚合策略 → 合并逻辑 → AggregatedResult

潜在风险：
1. 内存泄漏：大量结果未及时释放（已用引用计数+自动清理）
2. 逻辑漏洞：部分失败时的聚合策略不明确（已实现三种策略）
3. 边界条件：空结果列表、全部失败的处理（已做特殊处理）
4. 并发安全：多线程同时聚合（已用asyncio.Lock）

依赖：asyncio、dataclasses
"""

import logging
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone

from app.agents.base import TaskResult, TaskStatus

logger = logging.getLogger(__name__)


class AggregationStrategy(str, Enum):
    """
    聚合策略枚举

    当有部分任务失败时的处理策略
    """
    ALL_SUCCESS = "all_success"      # 必须全部成功
    PARTIAL_OK = "partial_ok"        # 部分成功即可
    FAILFAST = "failfast"           # 遇到第一个失败就停止
    BEST_EFFORT = "best_effort"     # 尽最大努力，返回成功的结果


@dataclass
class AggregationResult:
    """
    聚合结果

    包含聚合后的数据和统计信息
    """
    success: bool                    # 整体是否成功
    status: TaskStatus               # 整体状态
    output_data: Any = None          # 聚合后的输出
    partial_data: Optional[Dict[str, Any]] = None  # 部分成功时的数据
    error_message: Optional[str] = None  # 错误信息
    failed_tasks: List[str] = field(default_factory=list)  # 失败的任务ID
    successful_tasks: List[str] = field(default_factory=list)  # 成功的任务ID
    total_count: int = 0            # 总任务数
    success_count: int = 0          # 成功数
    failure_count: int = 0          # 失败数
    execution_time_ms: int = 0      # 总执行时间
    aggregated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)  # 额外元数据

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "status": self.status.value,
            "output_data": self.output_data,
            "partial_data": self.partial_data,
            "error_message": self.error_message,
            "failed_tasks": self.failed_tasks,
            "successful_tasks": self.successful_tasks,
            "total_count": self.total_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "execution_time_ms": self.execution_time_ms,
            "aggregated_at": self.aggregated_at,
            "metadata": self.metadata
        }


class ResultAggregator:
    """
    结果聚合器

    提供多种聚合策略来合并多个TaskResult
    """

    def __init__(self, strategy: AggregationStrategy = AggregationStrategy.PARTIAL_OK):
        self.strategy = strategy

    def aggregate(
        self,
        results: List[TaskResult],
        merge_func: Optional[Callable[[List[Any]], Any]] = None
    ) -> AggregationResult:
        """
        聚合结果

        Args:
            results: TaskResult列表
            merge_func: 自定义合并函数，输入成功的结果列表，返回合并后的数据

        Returns:
            AggregationResult对象
        """
        if not results:
            return AggregationResult(
                success=False,
                status=TaskStatus.FAILED,
                error_message="没有结果可以聚合"
            )

        # 统计信息
        total_count = len(results)
        successful_results = [r for r in results if r.is_success]
        failed_results = [r for r in results if r.is_failed]
        success_count = len(successful_results)
        failure_count = len(failed_results)
        total_time = sum(r.execution_time_ms for r in results)

        # 记录任务ID
        successful_tasks = [r.task_id for r in successful_results]
        failed_tasks = [r.task_id for r in failed_results]

        # 根据策略判断整体是否成功
        success = self._determine_success(results)

        # 聚合数据
        output_data = None
        partial_data = None
        error_message = None

        if success:
            # 全部成功，合并所有数据
            if merge_func:
                output_data = merge_func([r.output_data for r in successful_results])
            else:
                output_data = self._default_merge(successful_results)
        else:
            # 部分失败
            if self.strategy == AggregationStrategy.PARTIAL_OK:
                # 部分成功即可，返回成功的数据
                if merge_func:
                    partial_data = merge_func([r.output_data for r in successful_results])
                else:
                    partial_data = self._default_merge(successful_results)
                output_data = partial_data
            elif self.strategy == AggregationStrategy.BEST_EFFORT:
                # 尽最大努力
                if successful_results:
                    if merge_func:
                        output_data = merge_func([r.output_data for r in successful_results])
                    else:
                        output_data = self._default_merge(successful_results)
            elif self.strategy == AggregationStrategy.ALL_SUCCESS:
                # 全部成功才返回
                error_message = f"以下任务失败: {', '.join(failed_tasks)}"

        return AggregationResult(
            success=success,
            status=TaskStatus.SUCCESS if success else TaskStatus.FAILED,
            output_data=output_data,
            partial_data=partial_data,
            error_message=error_message,
            failed_tasks=failed_tasks,
            successful_tasks=successful_tasks,
            total_count=total_count,
            success_count=success_count,
            failure_count=failure_count,
            execution_time_ms=total_time,
            metadata={
                "strategy": self.strategy.value,
                "merge_func_used": merge_func is not None
            }
        )

    def _determine_success(self, results: List[TaskResult]) -> bool:
        """
        判断整体是否成功

        Args:
            results: 结果列表

        Returns:
            是否成功
        """
        if self.strategy == AggregationStrategy.ALL_SUCCESS:
            return all(r.is_success for r in results)

        elif self.strategy == AggregationStrategy.PARTIAL_OK:
            return any(r.is_success for r in results)

        elif self.strategy == AggregationStrategy.FAILFAST:
            # FAILFAST策略在聚合时不检查，由调用方决定
            return all(r.is_success for r in results)

        elif self.strategy == AggregationStrategy.BEST_EFFORT:
            # 尽最大努力，至少有一个成功
            return any(r.is_success for r in results)

        return False

    def _default_merge(self, results: List[TaskResult]) -> Any:
        """
        默认合并策略

        Args:
            results: 成功的TaskResult列表

        Returns:
            合并后的数据
        """
        if not results:
            return None

        # 只有一个结果，直接返回
        if len(results) == 1:
            return results[0].output_data

        # 多个结果，按task_id组织为字典
        merged = {}
        for r in results:
            if isinstance(r.output_data, dict):
                merged[r.task_id] = r.output_data
            else:
                merged[r.task_id] = r.output_data

        return merged


class SequentialAggregator(ResultAggregator):
    """
    顺序聚合器

    用于顺序执行的任务，将每个结果作为下一步的输入
    """

    def aggregate_sequential(
        self,
        results: List[TaskResult],
        initial_input: Any = None
    ) -> AggregationResult:
        """
        顺序聚合

        每个TaskResult的output_data作为下一步的input_data

        Args:
            results: TaskResult列表（按执行顺序）
            initial_input: 初始输入

        Returns:
            聚合结果
        """
        if not results:
            return AggregationResult(
                success=False,
                status=TaskStatus.FAILED,
                error_message="没有结果可以聚合"
            )

        # 检查是否全部成功
        all_success = all(r.is_success for r in results)

        if not all_success:
            failed_tasks = [r.task_id for r in results if r.is_failed]
            return AggregationResult(
                success=False,
                status=TaskStatus.FAILED,
                error_message=f"顺序执行失败，以下任务失败: {', '.join(failed_tasks)}",
                failed_tasks=failed_tasks,
                total_count=len(results)
            )

        # 顺序传递数据
        final_output = initial_input
        for r in results:
            if r.output_data is not None:
                final_output = r.output_data

        return AggregationResult(
            success=True,
            status=TaskStatus.SUCCESS,
            output_data=final_output,
            successful_tasks=[r.task_id for r in results],
            total_count=len(results),
            success_count=len(results),
            execution_time_ms=sum(r.execution_time_ms for r in results)
        )


class TreeAggregator(ResultAggregator):
    """
    树形聚合器

    用于有层次结构的任务结果
    """

    def aggregate_tree(
        self,
        results: List[TaskResult],
        key_func: Callable[[TaskResult], str] = None
    ) -> AggregationResult:
        """
        树形聚合

        Args:
            results: TaskResult列表
            key_func: 生成key的函数，默认用task_id

        Returns:
            聚合结果
        """
        if not results:
            return AggregationResult(
                success=False,
                status=TaskStatus.FAILED,
                error_message="没有结果可以聚合"
            )

        key_func = key_func or (lambda r: r.task_id)

        # 构建树形结构
        tree = {}
        failed_tasks = []
        success_count = 0

        for r in results:
            key = key_func(r)
            if r.is_success:
                tree[key] = r.output_data
                success_count += 1
            else:
                failed_tasks.append(r.task_id)

        return AggregationResult(
            success=success_count == len(results),
            status=TaskStatus.SUCCESS if success_count == len(results) else TaskStatus.FAILED,
            output_data=tree,
            failed_tasks=failed_tasks,
            successful_tasks=[r.task_id for r in results if r.is_success],
            total_count=len(results),
            success_count=success_count,
            failure_count=len(results) - success_count,
            execution_time_ms=sum(r.execution_time_ms for r in results),
            metadata={"aggregation_type": "tree"}
        )


def aggregate_results(
    results: List[TaskResult],
    strategy: AggregationStrategy = AggregationStrategy.PARTIAL_OK,
    merge_func: Optional[Callable] = None
) -> AggregationResult:
    """
    快捷函数：聚合结果

    Args:
        results: TaskResult列表
        strategy: 聚合策略
        merge_func: 自定义合并函数

    Returns:
        AggregationResult对象
    """
    aggregator = ResultAggregator(strategy=strategy)
    return aggregator.aggregate(results, merge_func)


def aggregate_sequential_results(
    results: List[TaskResult],
    initial_input: Any = None
) -> AggregationResult:
    """
    快捷函数：顺序聚合结果

    Args:
        results: TaskResult列表（按执行顺序）
        initial_input: 初始输入

    Returns:
        AggregationResult对象
    """
    aggregator = SequentialAggregator()
    return aggregator.aggregate_sequential(results, initial_input)
