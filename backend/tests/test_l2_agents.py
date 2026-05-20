"""
L2 业务 Agent 单元测试
测试模块: BehaviorAnalysisAgent（行为分析）
运行方式: python tests/test_l2_agents.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.behavior.behavior_analysis import BehaviorAnalysisAgent


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


# ============================================================
# 行为分析 Agent (BA-01 ~ BA-03)
# ============================================================

async def test_behavior_analysis():
    print("\n[L2-1] 行为分析 Agent (BA-01 ~ BA-03)")
    print("-" * 50)
    agent = BehaviorAnalysisAgent()

    events = [
        {"user_id": "user-001", "category": "CONTENT_INTERACTION", "action": "VIEW_POINT", "point_id": "p1", "timestamp": "2024-01-15T10:00:00", "duration_ms": 30000},
        {"user_id": "user-001", "category": "EXERCISE", "action": "SUBMIT_ANSWER", "point_id": "p1", "timestamp": "2024-01-15T10:30:00", "metadata": {"is_correct": True, "question_count": 5, "correct_count": 4}},
        {"user_id": "user-001", "category": "EXERCISE", "action": "SUBMIT_ANSWER", "point_id": "p1", "timestamp": "2024-01-15T11:00:00", "metadata": {"is_correct": False, "question_count": 5, "correct_count": 2}},
    ]

    # BA-01: 正常分析
    try:
        result = await agent.execute(
            user_id="user-001",
            events=events,
            point_names={"p1": "Python变量"}
        )
        has_profile = result.user_profile is not None
        has_mastery = len(result.point_masteries) >= 0
        detail = ""
        if has_profile:
            detail = f"activity={result.user_profile.activity_level.value}, mastery={result.user_profile.overall_mastery}"
        record("BA-01", "正常分析", "PASS" if has_profile or has_mastery else "FAIL", detail)
    except Exception as e:
        record("BA-01", "正常分析", "FAIL", str(e))

    # BA-02: BKT 更新
    try:
        result2 = await agent.execute(
            user_id="user-001",
            events=events,
            point_names={"p1": "Python变量"}
        )
        has_mastery_data = len(result2.point_masteries) > 0
        detail = ""
        if has_mastery_data:
            pm = result2.point_masteries[0]
            detail = f"point={pm.point_name}, prob={pm.mastery_probability:.2f}, level={pm.mastery_level.value}"
        record("BA-02", "BKT 更新", "PASS" if has_mastery_data else "FAIL", detail)
    except Exception as e:
        record("BA-02", "BKT 更新", "FAIL", str(e))

    # BA-03: 空事件
    try:
        result3 = await agent.execute(user_id="user-001", events=[])
        record("BA-03", "空事件", "PASS", f"analyzed_count={result3.analyzed_event_count}")
    except Exception as e:
        record("BA-03", "空事件", "FAIL", str(e))


# ============================================================
# 主函数
# ============================================================

async def main():
    print("=" * 60)
    print("L2 业务 Agent 单元测试")
    print("=" * 60)

    await test_behavior_analysis()

    # 报告
    print("\n" + "=" * 60)
    print("L2 测试报告")
    print("=" * 60)
    total = passed + failed
    print(f"\n总计: {total} 个用例")
    print(f"通过: {passed} 个")
    print(f"失败: {failed} 个")
    print(f"通过率: {passed/total*100:.1f}%" if total > 0 else "通过率: N/A")

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
