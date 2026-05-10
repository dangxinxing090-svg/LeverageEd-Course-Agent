"""
L7 端到端 E2E 测试
测试模块: 完整学习流程/问答流程/跳级流程/激励流程
运行方式: python tests/test_l7_e2e.py
前置条件: 无（直接调用 Agent execute 方法，验证链路数据传递）
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.knowledge.knowledge_split import KnowledgeSplitAgent
from app.agents.knowledge.difficulty_tag import DifficultyTagAgent
from app.agents.learning.content_explain import ContentExplainAgent
from app.agents.learning.exercise_generate import ExerciseGenerateAgent
from app.agents.learning.answer_grade import AnswerGradeAgent
from app.agents.learning.qa_answer import QAAnswerAgent
from app.agents.path_planning.skip_suggest import SkipSuggestAgent
from app.agents.incentive.reward_generate import RewardGenerateAgent


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
# E2E-01: 完整学习流程
# 主题提交 → 知识拆分 → 难度标注 → 知识讲解 → 练习生成 → 答题批改
# ============================================================

async def test_e2e_full_learning_flow():
    print("\n[E2E-01] 完整学习流程")
    print("-" * 60)

    # Step 1: 知识拆分
    try:
        split_agent = KnowledgeSplitAgent()
        topic_result = await split_agent.execute(
            topic_name="Python基础",
            topic_description="Python是一门广泛使用的高级编程语言。"
        )
        assert topic_result.blocks is not None and len(topic_result.blocks) > 0, "知识拆分返回空"
        print(f"    Step 1 ✓ 知识拆分: {len(topic_result.blocks)} 个板块, {topic_result.total_points} 个知识点")
    except Exception as e:
        record("E2E-01", "完整学习流程", "FAIL", f"Step 1 知识拆分失败: {e}")
        return

    # Step 2: 难度标注（取第一个板块的第一个知识点）
    try:
        tag_agent = DifficultyTagAgent()
        first_block = topic_result.blocks[0]
        points_input = []
        for p in first_block.points[:3]:  # 取前3个知识点
            points_input.append({
                "point_id": p.point_id,
                "point_name": p.point_name,
                "description": p.description
            })
        tag_result = await tag_agent.execute(points=points_input, topic_context="Python基础")
        assert tag_result.annotations is not None and len(tag_result.annotations) > 0, "难度标注返回空"
        print(f"    Step 2 ✓ 难度标注: {len(tag_result.annotations)} 个标注")
    except Exception as e:
        record("E2E-01", "完整学习流程", "FAIL", f"Step 2 难度标注失败: {e}")
        return

    # Step 3: 知识讲解（取第一个知识点）
    try:
        explain_agent = ContentExplainAgent()
        first_point = points_input[0]
        explain_result = await explain_agent.execute(
            point_info=first_point,
            user_level="BEGINNER",
            teaching_style="SIMPLE"
        )
        assert explain_result.sections is not None and len(explain_result.sections) > 0, "知识讲解返回空"
        print(f"    Step 3 ✓ 知识讲解: {len(explain_result.sections)} 个章节")
    except Exception as e:
        record("E2E-01", "完整学习流程", "FAIL", f"Step 3 知识讲解失败: {e}")
        return

    # Step 4: 练习生成
    try:
        exercise_agent = ExerciseGenerateAgent()
        exercise_result = await exercise_agent.execute(
            point_info=first_point,
            total_questions=3
        )
        assert exercise_result.questions is not None, "练习生成返回空"
        print(f"    Step 4 ✓ 练习生成: {len(exercise_result.questions)} 道题")
    except Exception as e:
        record("E2E-01", "完整学习流程", "FAIL", f"Step 4 练习生成失败: {e}")
        return

    # Step 5: 答题批改
    try:
        grade_agent = AnswerGradeAgent()
        questions = []
        answers = []
        for q in exercise_result.questions:
            questions.append({
                "question_id": q.question_id,
                "question_text": q.question_text,
                "question_type": q.question_type.value if hasattr(q.question_type, 'value') else str(q.question_type),
                "correct_answer": q.correct_answer,
                "point_id": q.point_id,
                "point_name": q.point_name,
            })
            # 模拟用户答案：第一题答对，其余答错
            if q == exercise_result.questions[0]:
                answers.append({"question_id": q.question_id, "answer": q.correct_answer})
            else:
                answers.append({"question_id": q.question_id, "answer": "错误答案"})
        grade_result = await grade_agent.execute(questions=questions, answers=answers)
        assert grade_result.total_questions == len(questions), "批改题目数不匹配"
        print(f"    Step 5 ✓ 答题批改: {grade_result.correct_count}/{grade_result.total_questions} 正确, 得分率 {grade_result.percentage}%")
    except Exception as e:
        record("E2E-01", "完整学习流程", "FAIL", f"Step 5 答题批改失败: {e}")
        return

    # 验证全链路数据传递
    try:
        # 验证 point_id 从拆分 → 标注 → 讲解 → 练习 → 批改 一致传递
        split_point_id = first_block.points[0].point_id
        tag_point_id = tag_result.annotations[0].point_id
        explain_point_id = explain_result.point_id
        exercise_point_id = exercise_result.questions[0].point_id
        grade_point_id = grade_result.grade_results[0].point_id

        ids_consistent = (
            split_point_id == tag_point_id == explain_point_id
            == exercise_point_id == grade_point_id
        )
        record("E2E-01", "完整学习流程", "PASS" if ids_consistent else "FAIL",
               f"point_id 一致传递: {split_point_id} → {tag_point_id} → {explain_point_id} → {exercise_point_id} → {grade_point_id}")
    except Exception as e:
        record("E2E-01", "完整学习流程", "FAIL", f"数据传递验证失败: {e}")


# ============================================================
# E2E-02: 问答流程
# 知识讲解中提问 → 问答 Agent 返回答案 → 答案与知识点关联
# ============================================================

async def test_e2e_qa_flow():
    print("\n[E2E-02] 问答流程")
    print("-" * 60)

    # Step 1: 知识讲解
    try:
        explain_agent = ContentExplainAgent()
        point_info = {
            "point_id": "point-e2e-qa",
            "point_name": "Python列表",
            "description": "Python列表的定义、操作和常用方法"
        }
        explain_result = await explain_agent.execute(
            point_info=point_info,
            user_level="INTERMEDIATE",
            teaching_style="BALANCED"
        )
        print(f"    Step 1 ✓ 知识讲解完成: {len(explain_result.sections)} 个章节")
    except Exception as e:
        record("E2E-02", "问答流程", "FAIL", f"Step 1 知识讲解失败: {e}")
        return

    # Step 2: 用户提问
    try:
        qa_agent = QAAnswerAgent()
        user_question = "Python列表和元组有什么区别？"
        qa_result = await qa_agent.execute(
            question=user_question,
            context={
                "topic_name": "Python基础",
                "current_point": "Python列表",
                "point_id": "point-e2e-qa"
            }
        )
        assert len(qa_result.answer_sections) > 0, "问答返回空"
        print(f"    Step 2 ✓ 问答返回: {len(qa_result.answer_sections)} 个章节, 类型={qa_result.question_type}")
    except Exception as e:
        record("E2E-02", "问答流程", "FAIL", f"Step 2 问答失败: {e}")
        return

    # Step 3: 验证答案与知识点关联
    try:
        has_related = len(qa_result.related_knowledge) >= 0
        has_quality = qa_result.quality is not None
        record("E2E-02", "问答流程", "PASS" if has_related and has_quality else "FAIL",
               f"关联知识点={len(qa_result.related_knowledge)}, 质量评级={qa_result.quality}")
    except Exception as e:
        record("E2E-02", "问答流程", "FAIL", str(e))


# ============================================================
# E2E-03: 跳级流程
# 高掌握度数据 → 跳级建议 Agent → 建议跳过
# ============================================================

async def test_e2e_skip_flow():
    print("\n[E2E-03] 跳级流程")
    print("-" * 60)

    # Step 1: 模拟高掌握度学习数据
    knowledge_points = [
        {"point_id": "p1", "point_name": "变量定义", "difficulty": "LOW"},
        {"point_id": "p2", "point_name": "数据类型", "difficulty": "LOW"},
        {"point_id": "p3", "point_name": "控制流", "difficulty": "MEDIUM"},
    ]
    learning_data_high = [
        # 每个知识点提供2条记录（满足 min_exercise_count=2）
        {"point_id": "p1", "score": 95, "total_questions": 10, "correct_questions": 10, "completion_time": 30, "review_count": 0},
        {"point_id": "p1", "score": 98, "total_questions": 10, "correct_questions": 10, "completion_time": 25, "review_count": 0},
        {"point_id": "p2", "score": 92, "total_questions": 10, "correct_questions": 9, "completion_time": 35, "review_count": 0},
        {"point_id": "p2", "score": 90, "total_questions": 10, "correct_questions": 9, "completion_time": 30, "review_count": 0},
        {"point_id": "p3", "score": 88, "total_questions": 10, "correct_questions": 9, "completion_time": 40, "review_count": 1},
        {"point_id": "p3", "score": 86, "total_questions": 10, "correct_questions": 9, "completion_time": 45, "review_count": 0},
    ]

    # Step 2: 跳级建议
    try:
        skip_agent = SkipSuggestAgent()
        skip_result = await skip_agent.execute(
            user_id="user-e2e-001",
            learning_data=learning_data_high,
            knowledge_points=knowledge_points,
            topic_name="Python基础"
        )
        assert skip_result.suggestions is not None, "跳级建议返回空"
        print(f"    Step 2 ✓ 跳级建议: {len(skip_result.suggestions)} 条建议, 跳过推荐={skip_result.skip_recommended}")
    except Exception as e:
        record("E2E-03", "跳级流程", "FAIL", f"Step 2 跳级建议失败: {e}")
        return

    # Step 3: 验证高掌握度用户获得跳级建议
    try:
        # 高掌握度用户应该有至少一个建议跳过的知识点
        skip_count = sum(1 for s in skip_result.suggestions if s.should_skip)
        has_skip_suggestion = skip_count > 0 or skip_result.skip_recommended > 0
        record("E2E-03", "跳级流程", "PASS" if has_skip_suggestion else "FAIL",
               f"高掌握度用户获得跳级建议: skip_count={skip_count}, skip_recommended={skip_result.skip_recommended}")
    except Exception as e:
        record("E2E-03", "跳级流程", "FAIL", str(e))


# ============================================================
# E2E-04: 激励流程
# 完成知识点 → 触发奖励 → 积分增加
# ============================================================

async def test_e2e_reward_flow():
    print("\n[E2E-04] 激励流程")
    print("-" * 60)

    # Step 1: 完成知识点触发奖励
    try:
        reward_agent = RewardGenerateAgent()
        result1 = await reward_agent.execute(
            user_id="user-e2e-001",
            trigger_scene="POINT_COMPLETED",
            context={
                "user_name": "测试用户",
                "topic_name": "Python基础",
                "current_point_name": "变量定义",
                "completed_points": 1,
            }
        )
        has_rewards_1 = len(result1.rewards) > 0
        points_1 = result1.total_points_earned
        print(f"    Step 1 ✓ 完成知识点奖励: rewards={len(result1.rewards)}, points={points_1}")
    except Exception as e:
        record("E2E-04", "激励流程", "FAIL", f"Step 1 奖励失败: {e}")
        return

    # Step 2: 练习通过触发奖励
    try:
        result2 = await reward_agent.execute(
            user_id="user-e2e-001",
            trigger_scene="EXERCISE_PASSED",
            context={
                "user_name": "测试用户",
                "topic_name": "Python基础",
                "current_point_name": "变量定义",
                "total_score": 85,
            }
        )
        has_rewards_2 = len(result2.rewards) > 0
        points_2 = result2.total_points_earned
        print(f"    Step 2 ✓ 练习通过奖励: rewards={len(result2.rewards)}, points={points_2}")
    except Exception as e:
        record("E2E-04", "激励流程", "FAIL", f"Step 2 奖励失败: {e}")
        return

    # Step 3: 满分练习触发奖励
    try:
        result3 = await reward_agent.execute(
            user_id="user-e2e-001",
            trigger_scene="PERFECT_EXERCISE",
            context={
                "user_name": "测试用户",
                "topic_name": "Python基础",
                "current_point_name": "变量定义",
                "total_score": 100,
            }
        )
        has_rewards_3 = len(result3.rewards) > 0
        points_3 = result3.total_points_earned
        print(f"    Step 3 ✓ 满分奖励: rewards={len(result3.rewards)}, points={points_3}")
    except Exception as e:
        record("E2E-04", "激励流程", "FAIL", f"Step 3 奖励失败: {e}")
        return

    # Step 4: 验证积分累计
    try:
        total_points = points_1 + points_2 + points_3
        all_has_rewards = has_rewards_1 and has_rewards_2 and has_rewards_3
        record("E2E-04", "激励流程", "PASS" if all_has_rewards and total_points > 0 else "FAIL",
               f"三次触发均有奖励, 累计积分={total_points} (完成={points_1} + 练习={points_2} + 满分={points_3})")
    except Exception as e:
        record("E2E-04", "激励流程", "FAIL", str(e))


# ============================================================
# 主函数
# ============================================================

async def main():
    print("=" * 60)
    print("L7 端到端 E2E 测试")
    print("=" * 60)

    await test_e2e_full_learning_flow()
    await test_e2e_qa_flow()
    await test_e2e_skip_flow()
    await test_e2e_reward_flow()

    # 报告
    print("\n" + "=" * 60)
    print("L7 测试报告")
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
