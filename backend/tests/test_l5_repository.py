"""
L5 数据仓库层单元测试
测试模块: 用户仓库 / 知识仓库 / 进度仓库
运行方式: python tests/test_l5_repository.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.repositories.user_repo import UserRepository, get_user_repository
from app.repositories.knowledge_repo import KnowledgeRepository, get_knowledge_repository
from app.repositories.progress_repo import ProgressRepository, get_progress_repository


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
# L5 测试用例 (RE-01 ~ RE-05)
# ============================================================

async def test_user_repo():
    """RE-01 ~ RE-03: 用户仓库"""
    print("\n[RE-01~03] 用户仓库")
    print("-" * 50)
    repo = UserRepository()  # 每次新建，避免单例污染

    # RE-01: 用户创建
    try:
        user = await repo.create(
            username="testuser",
            email="test@example.com",
            password_hash="hashed123"
        )
        assert user.user_id is not None and len(user.user_id) > 0, "user_id为空"
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.status == "active"
        record("RE-01", "用户创建", "PASS", f"user_id={user.user_id}, username={user.username}")
    except Exception as e:
        record("RE-01", "用户创建", "FAIL", str(e))

    # RE-02: 用户查询
    try:
        user2 = await repo.create(username="queryuser", email="query@example.com")
        # 按ID查询
        found = await repo.get_by_id(user2.user_id)
        assert found is not None, "get_by_id返回None"
        assert found.username == "queryuser"
        # 按邮箱查询
        found2 = await repo.get_by_email("query@example.com")
        assert found2 is not None, "get_by_email返回None"
        assert found2.user_id == user2.user_id
        # 按用户名查询
        found3 = await repo.get_by_username("queryuser")
        assert found3 is not None, "get_by_username返回None"
        record("RE-02", "用户查询", "PASS", "ID/邮箱/用户名三种查询均通过")
    except Exception as e:
        record("RE-02", "用户查询", "FAIL", str(e))

    # RE-03: 用户不存在
    try:
        not_found = await repo.get_by_id("not-exist-id-12345")
        assert not_found is None, f"期望None，实际返回{not_found}"
        record("RE-03", "用户不存在", "PASS", "get_by_id返回None")
    except Exception as e:
        record("RE-03", "用户不存在", "FAIL", str(e))


async def test_knowledge_repo():
    """RE-04: 知识仓库"""
    print("\n[RE-04] 知识仓库")
    print("-" * 50)
    repo = KnowledgeRepository()

    # RE-04: 知识保存
    try:
        # 创建主题
        topic = await repo.create_topic(
            topic_name="Python编程基础",
            description="Python语言基础教程"
        )
        assert topic.topic_id is not None and len(topic.topic_id) > 0
        assert topic.topic_name == "Python编程基础"

        # 创建板块
        block = await repo.create_block(
            topic_id=topic.topic_id,
            block_name="基础语法",
            description="Python基础语法学习"
        )
        assert block.block_id is not None
        assert block.topic_id == topic.topic_id

        # 创建知识点
        point = await repo.create_point(
            block_id=block.block_id,
            point_name="变量与数据类型",
            description="Python变量定义和数据类型"
        )
        assert point.point_id is not None
        assert point.block_id == block.block_id

        # 验证层级关系
        topic_fetched = await repo.get_topic(topic.topic_id)
        assert topic_fetched is not None
        assert len(topic_fetched.blocks) >= 1
        assert topic_fetched.total_points >= 1

        record("RE-04", "知识保存", "PASS",
               f"topic={topic.topic_id}, block={block.block_id}, point={point.point_id}, total_points={topic_fetched.total_points}")
    except Exception as e:
        record("RE-04", "知识保存", "FAIL", str(e))


async def test_progress_repo():
    """RE-05: 进度仓库"""
    print("\n[RE-05] 进度仓库")
    print("-" * 50)
    repo = ProgressRepository()

    # RE-05: 进度更新
    try:
        # 创建进度
        progress = await repo.get_or_create_progress(
            user_id="user-prog-001",
            point_id="point-prog-001",
            topic_id="topic-prog-001"
        )
        assert progress.status == "NOT_STARTED"
        assert progress.mastery_score == 0

        # 更新为学习中
        p1 = await repo.update_progress(
            user_id="user-prog-001",
            point_id="point-prog-001",
            status="IN_PROGRESS",
            study_seconds=600,
            exercise_count=5,
            correct_rate=0.8
        )
        assert p1.status == "IN_PROGRESS"
        assert p1.study_seconds == 600
        assert p1.exercise_count == 5

        # 累加学习时长
        p2 = await repo.update_progress(
            user_id="user-prog-001",
            point_id="point-prog-001",
            study_seconds=300,
            exercise_count=3,
            correct_rate=0.9
        )
        assert p2.study_seconds == 900, f"期望900，实际{p2.study_seconds}"
        assert p2.exercise_count == 8, f"期望8，实际{p2.exercise_count}"

        # 更新为已完成
        p3 = await repo.update_progress(
            user_id="user-prog-001",
            point_id="point-prog-001",
            status="COMPLETED"
        )
        assert p3.status == "COMPLETED"
        assert p3.completed_at is not None and len(p3.completed_at) > 0

        record("RE-05", "进度更新", "PASS",
               f"NOT_STARTED→IN_PROGRESS→COMPLETED, study={p3.study_seconds}s, exercises={p3.exercise_count}")
    except Exception as e:
        record("RE-05", "进度更新", "FAIL", str(e))


# ============================================================
# 主函数
# ============================================================

async def main():
    print("=" * 60)
    print("L5 数据仓库层单元测试")
    print("=" * 60)

    await test_user_repo()
    await test_knowledge_repo()
    await test_progress_repo()

    # 报告
    print("\n" + "=" * 60)
    print("L5 测试报告")
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
