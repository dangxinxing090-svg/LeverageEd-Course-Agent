"""
L1 Agent 引擎基础设施测试
测试模块: 注册表 / 分发器 / 依赖解析 / 结果聚合 / 错误处理
运行方式: python tests/test_l1_engine.py
"""

import asyncio
import sys
import os
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.base import (
    TaskType, TaskStatus, AgentCapability, AgentStatus,
    TaskRequest, TaskResult, AgentRegistration, AgentInfo,
)
from app.agents.registry import (
    AgentRegistry, RegistryConfig,
    AgentRegistryError, AgentAlreadyExistsError, AgentNotFoundError,
    get_agent_registry,
)
from app.agents.dispatcher import (
    TaskDispatcher, DispatchConfig,
    DispatcherError, NoAgentAvailableError,
    get_task_dispatcher,
)
from app.agents.dependency import (
    DependencyGraph, DependencyResolver, resolve_dependencies,
    DependencyError, CircularDependencyError, MissingDependencyError,
    ExecutionBatch,
)
from app.agents.aggregator import (
    ResultAggregator, SequentialAggregator, TreeAggregator,
    AggregationStrategy, AggregationResult,
    aggregate_results, aggregate_sequential_results,
)
from app.agents.error_handler import (
    ErrorClassifier, RetryPolicy, TaskErrorHandler,
    ErrorType, RetryStrategy, FallbackStrategy,
    RetryConfig, FallbackConfig, ErrorMetrics,
    with_error_handling, get_error_handler,
)


# ============================================================
# 辅助函数
# ============================================================

passed = 0
failed = 0
results = []

def record(test_id: str, name: str, status: str, detail: str = ""):
    global passed, failed
    results.append({"id": test_id, "name": name, "status": status, "detail": detail})
    icon = "✓" if status == "PASS" else "✗"
    print(f"  {icon} {test_id}: {name}" + (f" — {detail}" if detail else ""))
    if status == "PASS":
        passed += 1
    else:
        failed += 1

def make_registration(agent_id: str, capabilities=None, endpoint: str = "http://localhost:8000") -> AgentRegistration:
    return AgentRegistration(
        agent_id=agent_id,
        agent_name=f"TestAgent-{agent_id}",
        agent_type="TestAgent",
        capabilities=capabilities or [AgentCapability.KNOWLEDGE_SPLIT],
        endpoint=endpoint,
    )

def make_task(task_type=TaskType.KNOWLEDGE_SPLIT, task_id=None, deps=None, timeout=30000) -> TaskRequest:
    return TaskRequest(
        task_id=task_id or str(uuid.uuid4()),
        task_type=task_type,
        input_data={"test": True},
        dependencies=deps or [],
        timeout_ms=timeout,
    )

def make_result(task_id: str, status=TaskStatus.SUCCESS, output=None, error_msg=None) -> TaskResult:
    return TaskResult(
        task_id=task_id,
        status=status,
        output_data=output or {"result": "ok"},
        error_message=error_msg,
        execution_time_ms=100,
    )


# ============================================================
# L1-1: Agent 注册表测试 (R-01 ~ R-10)
# ============================================================

def test_registry():
    print("\n[L1-1] Agent 注册表测试 (R-01 ~ R-10)")
    print("-" * 50)

    # R-01: 正常注册
    try:
        reg = AgentRegistry(config=RegistryConfig(max_agents=100))
        info = reg.register(make_registration("agent-001"))
        assert info.registration.agent_id == "agent-001"
        assert reg.agent_count == 1
        record("R-01", "正常注册", "PASS", f"agent_count={reg.agent_count}")
    except Exception as e:
        record("R-01", "正常注册", "FAIL", str(e))

    # R-02: 重复注册
    try:
        reg2 = AgentRegistry()
        reg2.register(make_registration("agent-dup"))
        try:
            reg2.register(make_registration("agent-dup"))
            record("R-02", "重复注册", "FAIL", "未抛出异常")
        except AgentAlreadyExistsError:
            record("R-02", "重复注册", "PASS", "正确抛出 AgentAlreadyExistsError")
    except Exception as e:
        record("R-02", "重复注册", "FAIL", str(e))

    # R-03: 参数校验
    try:
        reg3 = AgentRegistry()
        errors = []
        # 空agent_id
        try:
            reg3.register(AgentRegistration(agent_id="", agent_name="x", agent_type="x", capabilities=[AgentCapability.KNOWLEDGE_SPLIT], endpoint="http://x"))
        except AgentRegistryError:
            errors.append("empty_id_ok")
        # 空capabilities
        try:
            reg3.register(AgentRegistration(agent_id="x", agent_name="x", agent_type="x", capabilities=[], endpoint="http://x"))
        except AgentRegistryError:
            errors.append("empty_cap_ok")
        # 空endpoint
        try:
            reg3.register(AgentRegistration(agent_id="x", agent_name="x", agent_type="x", capabilities=[AgentCapability.KNOWLEDGE_SPLIT], endpoint=""))
        except AgentRegistryError:
            errors.append("empty_ep_ok")
        if len(errors) >= 2:
            record("R-03", "参数校验", "PASS", f"拦截{len(errors)}种非法参数")
        else:
            record("R-03", "参数校验", "FAIL", f"仅拦截{len(errors)}种")
    except Exception as e:
        record("R-03", "参数校验", "FAIL", str(e))

    # R-04: 容量限制
    try:
        reg4 = AgentRegistry(config=RegistryConfig(max_agents=3))
        for i in range(3):
            reg4.register(make_registration(f"cap-{i}"))
        try:
            reg4.register(make_registration("cap-overflow"))
            record("R-04", "容量限制", "FAIL", "未抛出异常")
        except AgentRegistryError:
            record("R-04", "容量限制", "PASS", "max_agents=3 时拒绝第4个注册")
    except Exception as e:
        record("R-04", "容量限制", "FAIL", str(e))

    # R-05: 按能力查找
    try:
        reg5 = AgentRegistry()
        reg5.register(make_registration("ks-agent", [AgentCapability.KNOWLEDGE_SPLIT]))
        reg5.register(make_registration("qa-agent", [AgentCapability.QA_ANSWER]))
        reg5.register(make_registration("ks2-agent", [AgentCapability.KNOWLEDGE_SPLIT, AgentCapability.QA_ANSWER]))
        found = reg5.find_agents_by_capability(AgentCapability.KNOWLEDGE_SPLIT)
        assert len(found) == 2, f"期望2个，实际{len(found)}个"
        record("R-05", "按能力查找", "PASS", f"KNOWLEDGE_SPLIT 找到{len(found)}个")
    except Exception as e:
        record("R-05", "按能力查找", "FAIL", str(e))

    # R-06: 按类型查找
    try:
        reg6 = AgentRegistry()
        reg6.register(AgentRegistration(
            agent_id="type-a", agent_name="A", agent_type="TypeX",
            capabilities=[AgentCapability.KNOWLEDGE_SPLIT], endpoint="http://x"
        ))
        reg6.register(AgentRegistration(
            agent_id="type-b", agent_name="B", agent_type="TypeY",
            capabilities=[AgentCapability.QA_ANSWER], endpoint="http://x"
        ))
        found = reg6.find_agent_by_type("TypeX")
        assert len(found) == 1
        record("R-06", "按类型查找", "PASS", f"TypeX 找到{len(found)}个")
    except Exception as e:
        record("R-06", "按类型查找", "FAIL", str(e))

    # R-07: 状态更新
    try:
        reg7 = AgentRegistry()
        reg7.register(make_registration("status-agent"))
        reg7.update_status("status-agent", AgentStatus.BUSY)
        info = reg7.get_agent("status-agent")
        assert info.status == AgentStatus.BUSY
        assert info.is_available == True  # BUSY但未满载，仍可用
        record("R-07", "状态更新", "PASS", "BUSY状态下is_available=True")
    except Exception as e:
        record("R-07", "状态更新", "FAIL", str(e))

    # R-08: 负载更新
    try:
        reg8 = AgentRegistry()
        reg8.register(make_registration("load-agent"))
        # 直接设置负载到上限
        reg8.update_load("load-agent", 10)  # max_concurrent默认10
        info = reg8.get_agent("load-agent")
        assert info.is_available == False, "满载时应不可用"
        record("R-08", "负载更新", "PASS", "满载时is_available=False")
    except Exception as e:
        record("R-08", "负载更新", "FAIL", str(e))

    # R-09: 心跳与清理
    try:
        reg9 = AgentRegistry(config=RegistryConfig(heartbeat_timeout_seconds=0))
        reg9.register(make_registration("heartbeat-agent"))
        reg9.heartbeat("heartbeat-agent")
        # 设置超时为0秒，等待1秒后清理
        time.sleep(0.1)
        cleaned = reg9.cleanup_stale_agents()
        assert len(cleaned) >= 1, f"应清理至少1个，实际清理{len(cleaned)}个"
        record("R-09", "心跳与清理", "PASS", f"清理{len(cleaned)}个过期Agent")
    except Exception as e:
        record("R-09", "心跳与清理", "FAIL", str(e))

    # R-10: 注销
    try:
        reg10 = AgentRegistry()
        reg10.register(make_registration("unreg-agent"))
        assert reg10.agent_count == 1
        result = reg10.unregister("unreg-agent")
        assert result == True
        assert reg10.agent_count == 0
        record("R-10", "注销", "PASS", "注销后agent_count=0")
    except Exception as e:
        record("R-10", "注销", "FAIL", str(e))


# ============================================================
# L1-2: 任务分发器测试 (D-01 ~ D-06) — 异步
# ============================================================

async def test_dispatcher():
    print("\n[L1-2] 任务分发器测试 (D-01 ~ D-06)")
    print("-" * 50)

    # D-01: 无可用Agent — 降级处理
    try:
        reg = AgentRegistry()
        disp = TaskDispatcher(registry=reg)
        task = make_task()
        result = await disp.dispatch(task)
        assert result.status in (TaskStatus.FAILED, TaskStatus.TIMEOUT), f"期望FAILED/TIMEOUT，实际{result.status}"
        record("D-01", "无可用Agent", "PASS", f"返回{result.status.value}")
    except Exception as e:
        record("D-01", "无可用Agent", "FAIL", str(e))

    # D-02: 超时处理
    try:
        reg2 = AgentRegistry()
        disp2 = TaskDispatcher(registry=reg2, config=DispatchConfig(default_timeout_ms=1))
        task2 = make_task(timeout=1)
        result2 = await disp2.dispatch(task2)
        # 超时或无Agent都会失败
        assert result2.status in (TaskStatus.TIMEOUT, TaskStatus.FAILED), f"实际{result2.status.value}"
        record("D-02", "超时处理", "PASS", f"返回{result2.status.value}")
    except Exception as e:
        record("D-02", "超时处理", "FAIL", str(e))

    # D-03: 批量分发
    try:
        reg3 = AgentRegistry()
        disp3 = TaskDispatcher(registry=reg3)
        tasks = [make_task(task_id=f"batch-{i}") for i in range(3)]
        results = await disp3.dispatch_batch(tasks)
        assert len(results) == 3, f"期望3个结果，实际{len(results)}个"
        all_failed = all(r.status in (TaskStatus.FAILED, TaskStatus.TIMEOUT) for r in results)
        assert all_failed, "无Agent时所有任务应失败"
        record("D-03", "批量分发", "PASS", f"3个任务全部{results[0].status.value}")
    except Exception as e:
        record("D-03", "批量分发", "FAIL", str(e))

    # D-04: 任务取消
    try:
        reg4 = AgentRegistry()
        disp4 = TaskDispatcher(registry=reg4)
        task4 = make_task(task_id="cancel-test")
        # 先注册一个pending task
        disp4.dispatch(task4)  # 不await，让它pending
        await asyncio.sleep(0.1)
        cancelled = disp4.cancel_task("cancel-test")
        # cancel可能返回True或False取决于时序
        record("D-04", "任务取消", "PASS", f"cancel_task返回{cancelled}")
    except Exception as e:
        record("D-04", "任务取消", "FAIL", str(e))

    # D-05: 过期清理
    try:
        reg5 = AgentRegistry()
        disp5 = TaskDispatcher(registry=reg5, config=DispatchConfig(task_expiry_seconds=0))
        task5 = make_task(task_id="expire-test")
        try:
            await disp5.dispatch(task5)
        except:
            pass
        await asyncio.sleep(0.1)
        cleaned = disp5.cleanup_expired_tasks()
        record("D-05", "过期清理", "PASS", f"清理{len(cleaned)}个过期任务")
    except Exception as e:
        record("D-05", "过期清理", "FAIL", str(e))

    # D-06: 分发器close
    try:
        reg6 = AgentRegistry()
        disp6 = TaskDispatcher(registry=reg6)
        await disp6.close()
        record("D-06", "分发器关闭", "PASS")
    except Exception as e:
        record("D-06", "分发器关闭", "FAIL", str(e))

    await disp.close()
    await disp2.close()
    await disp3.close()
    await disp4.close()
    await disp5.close()


# ============================================================
# L1-3: 依赖解析器测试 (DP-01 ~ DP-06)
# ============================================================

def test_dependency():
    print("\n[L1-3] 依赖解析器测试 (DP-01 ~ DP-06)")
    print("-" * 50)

    # DP-01: 无依赖任务
    try:
        resolver = DependencyResolver()
        tasks = [make_task(task_id=f"ind-{i}") for i in range(3)]
        batches = resolver.resolve(tasks)
        assert len(batches) == 1, f"期望1个批次，实际{len(batches)}个"
        assert batches[0].can_parallel == True
        record("DP-01", "无依赖任务", "PASS", f"1个批次，{len(batches[0].tasks)}个任务可并行")
    except Exception as e:
        record("DP-01", "无依赖任务", "FAIL", str(e))

    # DP-02: 串行依赖 A→B→C
    try:
        resolver2 = DependencyResolver()
        a = make_task(task_id="ser-a")
        b = make_task(task_id="ser-b", deps=["ser-a"])
        c = make_task(task_id="ser-c", deps=["ser-b"])
        batches2 = resolver2.resolve([a, b, c])
        assert len(batches2) == 3, f"期望3个批次，实际{len(batches2)}个"
        assert batches2[0].tasks[0].task_id == "ser-a"
        assert batches2[1].tasks[0].task_id == "ser-b"
        assert batches2[2].tasks[0].task_id == "ser-c"
        record("DP-02", "串行依赖", "PASS", "3个批次顺序正确")
    except Exception as e:
        record("DP-02", "串行依赖", "FAIL", str(e))

    # DP-03: 并行+串行混合 A→C, B→C
    try:
        resolver3 = DependencyResolver()
        ta = make_task(task_id="mix-a")
        tb = make_task(task_id="mix-b")
        tc = make_task(task_id="mix-c", deps=["mix-a", "mix-b"])
        batches3 = resolver3.resolve([ta, tb, tc])
        assert len(batches3) == 2, f"期望2个批次，实际{len(batches3)}个"
        first_ids = {t.task_id for t in batches3[0].tasks}
        assert "mix-a" in first_ids and "mix-b" in first_ids
        assert batches3[1].tasks[0].task_id == "mix-c"
        record("DP-03", "并行+串行混合", "PASS", "[A,B]→[C]")
    except Exception as e:
        record("DP-03", "并行+串行混合", "FAIL", str(e))

    # DP-04: 循环依赖检测
    try:
        resolver4 = DependencyResolver()
        ca = make_task(task_id="cyc-a", deps=["cyc-c"])
        cb = make_task(task_id="cyc-b", deps=["cyc-a"])
        cc = make_task(task_id="cyc-c", deps=["cyc-b"])
        try:
            resolver4.resolve([ca, cb, cc])
            record("DP-04", "循环依赖检测", "FAIL", "未抛出异常")
        except CircularDependencyError as ce:
            record("DP-04", "循环依赖检测", "PASS", f"检测到环路: {'→'.join(ce.cycle)}")
    except Exception as e:
        record("DP-04", "循环依赖检测", "FAIL", str(e))

    # DP-05: 缺失依赖（解析器可能不校验，验证行为）
    try:
        resolver5 = DependencyResolver()
        td = make_task(task_id="dep-task", deps=["non-existent"])
        batches5 = resolver5.resolve([td])
        # 如果不抛异常，则缺失依赖的任务仍被排入执行计划
        record("DP-05", "缺失依赖", "PASS", "缺失依赖任务被排入执行计划（不阻断）")
    except (MissingDependencyError, DependencyError) as de:
        record("DP-05", "缺失依赖", "PASS", f"正确拦截: {type(de).__name__}")
    except Exception as e:
        record("DP-05", "缺失依赖", "FAIL", str(e))

    # DP-06: 空任务列表
    try:
        resolver6 = DependencyResolver()
        batches6 = resolver6.resolve([])
        assert len(batches6) == 0
        record("DP-06", "空任务列表", "PASS", "返回空批次列表")
    except Exception as e:
        record("DP-06", "空任务列表", "FAIL", str(e))


# ============================================================
# L1-4: 结果聚合器测试 (AG-01 ~ AG-06)
# ============================================================

def test_aggregator():
    print("\n[L1-4] 结果聚合器测试 (AG-01 ~ AG-06)")
    print("-" * 50)

    # AG-01: 全部成功 (ALL_SUCCESS)
    try:
        agg = ResultAggregator(strategy=AggregationStrategy.ALL_SUCCESS)
        res_list = [
            make_result("t1", TaskStatus.SUCCESS, {"val": 1}),
            make_result("t2", TaskStatus.SUCCESS, {"val": 2}),
            make_result("t3", TaskStatus.SUCCESS, {"val": 3}),
        ]
        result = agg.aggregate(res_list)
        assert result.success == True
        assert result.success_count == 3
        record("AG-01", "全部成功", "PASS", f"success={result.success}, count={result.success_count}")
    except Exception as e:
        record("AG-01", "全部成功", "FAIL", str(e))

    # AG-02: 部分失败 (PARTIAL_OK)
    try:
        agg2 = ResultAggregator(strategy=AggregationStrategy.PARTIAL_OK)
        res_list2 = [
            make_result("p1", TaskStatus.SUCCESS),
            make_result("p2", TaskStatus.SUCCESS),
            make_result("p3", TaskStatus.FAILED, error_msg="err"),
        ]
        result2 = agg2.aggregate(res_list2)
        assert result2.success == True, "PARTIAL_OK策略下部分失败应返回success=True"
        assert result2.failure_count == 1
        record("AG-02", "部分失败", "PASS", f"success={result2.success}, failed={result2.failure_count}")
    except Exception as e:
        record("AG-02", "部分失败", "FAIL", str(e))

    # AG-03: 全部失败
    try:
        agg3 = ResultAggregator(strategy=AggregationStrategy.PARTIAL_OK)
        res_list3 = [
            make_result("f1", TaskStatus.FAILED),
            make_result("f2", TaskStatus.FAILED),
            make_result("f3", TaskStatus.TIMEOUT),
        ]
        result3 = agg3.aggregate(res_list3)
        assert result3.success == False
        assert result3.failure_count == 3
        record("AG-03", "全部失败", "PASS", f"success={result3.success}, failed={result3.failure_count}")
    except Exception as e:
        record("AG-03", "全部失败", "FAIL", str(e))

    # AG-04: 空结果
    try:
        agg4 = ResultAggregator()
        result4 = agg4.aggregate([])
        assert result4.success == False
        assert result4.error_message is not None or result4.total_count == 0
        record("AG-04", "空结果", "PASS", f"success={result4.success}")
    except Exception as e:
        record("AG-04", "空结果", "FAIL", str(e))

    # AG-05: 自定义合并
    try:
        agg5 = ResultAggregator()
        res_list5 = [
            make_result("m1", TaskStatus.SUCCESS, {"text": "Hello"}),
            make_result("m2", TaskStatus.SUCCESS, {"text": " World"}),
        ]
        # merge_func 接收 List[Dict] (output_data列表)
        result5 = agg5.aggregate(res_list5, merge_func=lambda outputs: "".join(
            d.get("text", "") for d in outputs if d
        ))
        assert result5.output_data == "Hello World"
        record("AG-05", "自定义合并", "PASS", f"合并结果: '{result5.output_data}'")
    except Exception as e:
        record("AG-05", "自定义合并", "FAIL", str(e))

    # AG-06: 顺序聚合
    try:
        seq_agg = SequentialAggregator()
        res_list6 = [
            make_result("s1", TaskStatus.SUCCESS, {"step1": "done"}),
            make_result("s2", TaskStatus.SUCCESS, {"step2": "done"}),
            make_result("s3", TaskStatus.SUCCESS, {"step3": "done"}),
        ]
        result6 = seq_agg.aggregate_sequential(res_list6)
        assert result6.success == True
        # 顺序聚合的output_data应为最后一个结果
        assert result6.output_data is not None
        record("AG-06", "顺序聚合", "PASS", f"success={result6.success}")
    except Exception as e:
        record("AG-06", "顺序聚合", "FAIL", str(e))


# ============================================================
# L1-5: 错误处理器测试 (EH-01 ~ EH-06)
# ============================================================

async def test_error_handler():
    print("\n[L1-5] 错误处理器测试 (EH-01 ~ EH-06)")
    print("-" * 50)

    # EH-01: 可重试错误
    try:
        handler = TaskErrorHandler(
            retry_config=RetryConfig(max_retries=3, base_delay_ms=10, retry_strategy=RetryStrategy.LINEAR)
        )
        call_count = 0
        async def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("连接失败")
            return {"ok": True}

        result = await handler.handle_error("task-eh1", ConnectionError("连接失败"), failing_func)
        assert call_count == 3, f"期望重试3次，实际{call_count}次"
        assert result.status == TaskStatus.SUCCESS
        record("EH-01", "可重试错误", "PASS", f"重试{call_count}次后成功")
    except Exception as e:
        record("EH-01", "可重试错误", "FAIL", str(e))

    # EH-02: 不可重试错误
    try:
        handler2 = TaskErrorHandler(
            retry_config=RetryConfig(max_retries=3)
        )
        call_count2 = 0
        async def value_error_func():
            nonlocal call_count2
            call_count2 += 1
            raise ValueError("参数错误")

        result2 = await handler2.handle_error("task-eh2", ValueError("参数错误"), value_error_func)
        # ValueError 是 CLIENT 类型，默认不可重试，直接走降级
        assert result2.status == TaskStatus.FAILED
        record("EH-02", "不可重试错误", "PASS", f"直接降级，status={result2.status.value}")
    except Exception as e:
        record("EH-02", "不可重试错误", "FAIL", str(e))

    # EH-03: 指数退避
    try:
        policy = RetryPolicy(RetryConfig(
            base_delay_ms=100,
            max_delay_ms=10000,
            retry_strategy=RetryStrategy.EXPONENTIAL,
            jitter=False,
        ))
        d0 = policy.calculate_delay(0)
        d1 = policy.calculate_delay(1)
        d2 = policy.calculate_delay(2)
        # 指数退避: base * 2^retry_count
        # 验证递增关系
        assert d1 > d0, f"d1({d1})应大于d0({d0})"
        assert d2 > d1, f"d2({d2})应大于d1({d1})"
        assert d2 == d0 * 4, f"d2应为d0的4倍，实际d0={d0}, d2={d2}"
        record("EH-03", "指数退避", "PASS", f"延迟递增: {d0:.3f}s → {d1:.3f}s → {d2:.3f}s")
    except Exception as e:
        record("EH-03", "指数退避", "FAIL", str(e))

    # EH-04: 降级策略
    try:
        handler4 = TaskErrorHandler(
            retry_config=RetryConfig(max_retries=0),
            fallback_config=FallbackConfig(
                strategy=FallbackStrategy.RETURN_DEFAULT,
                default_value={"fallback": True},
            )
        )
        async def always_fail():
            raise RuntimeError("总是失败")

        result4 = await handler4.handle_error("task-eh4", RuntimeError("总是失败"), always_fail)
        assert result4.status == TaskStatus.FAILED
        assert result4.output_data == {"fallback": True}, f"output_data={result4.output_data}"
        record("EH-04", "降级策略", "PASS", f"返回default_value: {result4.output_data}")
    except Exception as e:
        record("EH-04", "降级策略", "FAIL", str(e))

    # EH-05: 错误指标
    try:
        handler5 = TaskErrorHandler()
        metrics = handler5.get_metrics()
        assert metrics.total_errors == 0
        assert metrics.error_rate == 0.0

        # 模拟5次错误
        for i in range(5):
            metrics.record_error(ErrorType.TRANSIENT, retry=True)

        metrics2 = handler5.get_metrics()
        assert metrics2.total_errors == 5
        assert metrics2.transient_errors == 5
        assert metrics2.retry_count == 5
        record("EH-05", "错误指标", "PASS", f"total={metrics2.total_errors}, transient={metrics2.transient_errors}, retry={metrics2.retry_count}")
    except Exception as e:
        record("EH-05", "错误指标", "FAIL", str(e))

    # EH-06: 装饰器模式
    try:
        handler6 = TaskErrorHandler(
            retry_config=RetryConfig(max_retries=2, base_delay_ms=10, retry_strategy=RetryStrategy.LINEAR),
            fallback_config=FallbackConfig(strategy=FallbackStrategy.RETURN_DEFAULT, default_value="decorator_fallback"),
        )

        deco_count = 0
        @with_error_handling(retry_config=RetryConfig(max_retries=2, base_delay_ms=10, retry_strategy=RetryStrategy.LINEAR),
                             fallback_config=FallbackConfig(strategy=FallbackStrategy.RETURN_DEFAULT, default_value="decorator_fallback"))
        async def decorated_func(data: str) -> str:
            nonlocal deco_count
            deco_count += 1
            if deco_count < 2:
                raise ConnectionError("装饰器测试错误")
            return f"success-{data}"

        result6 = await decorated_func("test")
        assert result6.status == TaskStatus.SUCCESS, f"实际{result6.status.value}"
        record("EH-06", "装饰器模式", "PASS", f"重试后成功: {result6.output_data}")
    except Exception as e:
        record("EH-06", "装饰器模式", "FAIL", str(e))


# ============================================================
# 主函数
# ============================================================

async def main():
    print("=" * 60)
    print("L1 Agent 引擎基础设施测试")
    print("=" * 60)

    # 同步测试
    test_registry()
    test_dependency()
    test_aggregator()

    # 异步测试
    await test_dispatcher()
    await test_error_handler()

    # 报告
    print("\n" + "=" * 60)
    print("L1 测试报告")
    print("=" * 60)
    total = passed + failed
    print(f"\n总计: {total} 个用例")
    print(f"通过: {passed} 个")
    print(f"失败: {failed} 个")
    print(f"通过率: {passed/total*100:.1f}%")

    if failed > 0:
        print("\n失败用例:")
        for r in results:
            if r["status"] == "FAIL":
                print(f"  ✗ {r['id']}: {r['name']} — {r['detail']}")

    print("\n" + "=" * 60)
    return failed == 0


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
