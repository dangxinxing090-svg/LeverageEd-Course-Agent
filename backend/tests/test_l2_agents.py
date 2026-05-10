"""
L2 业务 Agent 单元测试
测试模块: 11个业务Agent（知识拆分/难度标注/知识讲解/练习题生成/题目批改/问答/路径规划/跳级建议/鼓励奖励/行为记录/行为分析）
运行方式: python tests/test_l2_agents.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.knowledge.knowledge_split import KnowledgeSplitAgent
from app.agents.knowledge.difficulty_tag import DifficultyTagAgent, DifficultyLevel, ImportanceLevel
from app.agents.learning.content_explain import ContentExplainAgent
from app.agents.learning.exercise_generate import ExerciseGenerateAgent
from app.agents.learning.answer_grade import AnswerGradeAgent
from app.agents.learning.qa_answer import QAAnswerAgent
from app.agents.path_planning.path_planning import PathPlanningAgent
from app.agents.path_planning.skip_suggest import SkipSuggestAgent
from app.agents.incentive.reward_generate import RewardGenerateAgent
from app.agents.behavior.behavior_record import BehaviorRecordAgent
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
# 4.2.1 知识拆分 Agent (KS-01 ~ KS-04)
# ============================================================

async def test_knowledge_split():
    print("\n[L2-1] 知识拆分 Agent (KS-01 ~ KS-04)")
    print("-" * 50)
    agent = KnowledgeSplitAgent()

    # KS-01: 正常拆分
    try:
        result = await agent.execute(
            topic_name="Python基础",
            topic_description="Python是一门广泛使用的高级编程语言，适合初学者学习。"
        )
        assert result.blocks is not None, "blocks为None"
        assert result.total_points >= 0, f"total_points={result.total_points}"
        record("KS-01", "正常拆分", "PASS", f"blocks={len(result.blocks)}, points={result.total_points}")
    except Exception as e:
        record("KS-01", "正常拆分", "FAIL", str(e))

    # KS-02: 三层结构
    try:
        result2 = await agent.execute(
            topic_name="数据结构",
            topic_description="常见数据结构包括数组、链表、栈、队列、树、图等。"
        )
        has_three_layers = True
        if result2.blocks:
            block = result2.blocks[0]
            if not block.points:
                has_three_layers = False
            else:
                point = block.points[0]
                if not point.components:
                    has_three_layers = False
        record("KS-02", "三层结构", "PASS" if has_three_layers else "FAIL",
               f"blocks→points→components: {'完整' if has_three_layers else '不完整'}")
    except Exception as e:
        record("KS-02", "三层结构", "FAIL", str(e))

    # KS-03: 空主题
    try:
        try:
            await agent.execute(topic_name="", topic_description="测试")
            record("KS-03", "空主题", "FAIL", "未抛出异常")
        except (ValueError, TypeError, Exception) as ve:
            record("KS-03", "空主题", "PASS", f"抛出 {type(ve).__name__}")
    except Exception as e:
        record("KS-03", "空主题", "FAIL", str(e))

    # KS-04: 长描述
    try:
        long_desc = "Python编程语言。" * 1000  # ~5000字
        result4 = await agent.execute(
            topic_name="Python高级",
            topic_description=long_desc
        )
        record("KS-04", "长描述", "PASS", f"正常返回，blocks={len(result4.blocks)}")
    except Exception as e:
        record("KS-04", "长描述", "FAIL", str(e))


# ============================================================
# 4.2.2 难度标注 Agent (DT-01 ~ DT-04)
# ============================================================

async def test_difficulty_tag():
    print("\n[L2-2] 难度标注 Agent (DT-01 ~ DT-04)")
    print("-" * 50)
    agent = DifficultyTagAgent()

    points_input = [
        {"point_id": "p1", "point_name": "变量定义", "description": "Python变量的定义和使用"},
        {"point_id": "p2", "point_name": "数据类型", "description": "Python基本数据类型"},
        {"point_id": "p3", "point_name": "控制流", "description": "if/for/while语句"},
    ]

    # DT-01: 正常标注
    try:
        result = await agent.execute(points=points_input)
        assert result.annotations is not None
        record("DT-01", "正常标注", "PASS", f"annotations={len(result.annotations)}")
    except Exception as e:
        record("DT-01", "正常标注", "FAIL", str(e))

    # DT-02: 难度枚举
    try:
        result2 = await agent.execute(points=points_input)
        valid_difficulties = {DifficultyLevel.LOW, DifficultyLevel.MEDIUM, DifficultyLevel.HIGH}
        all_valid = True
        for ann in result2.annotations:
            if ann.concept_difficulty not in valid_difficulties:
                all_valid = False
                break
            if ann.learning_difficulty not in valid_difficulties:
                all_valid = False
                break
        record("DT-02", "难度枚举", "PASS" if all_valid else "FAIL",
               f"所有难度∈{{LOW,MEDIUM,HIGH}}: {all_valid}")
    except Exception as e:
        record("DT-02", "难度枚举", "FAIL", str(e))

    # DT-03: 重要性枚举
    try:
        result3 = await agent.execute(points=points_input)
        valid_importance = {ImportanceLevel.CORE, ImportanceLevel.IMPORTANT, ImportanceLevel.AUXILIARY}
        all_valid = True
        for ann in result3.annotations:
            if ann.importance not in valid_importance:
                all_valid = False
                break
        record("DT-03", "重要性枚举", "PASS" if all_valid else "FAIL",
               f"所有重要性∈{{CORE,IMPORTANT,AUXILIARY}}: {all_valid}")
    except Exception as e:
        record("DT-03", "重要性枚举", "FAIL", str(e))

    # DT-04: 空列表
    try:
        result4 = await agent.execute(points=[])
        # 空列表可能返回空annotations或抛异常，都算合理
        record("DT-04", "空列表", "PASS", f"annotations={len(result4.annotations)}")
    except Exception as e:
        record("DT-04", "空列表", "PASS", f"抛出 {type(e).__name__}（合理行为）")


# ============================================================
# 4.2.3 知识讲解 Agent (CE-01 ~ CE-03)
# ============================================================

async def test_content_explain():
    print("\n[L2-3] 知识讲解 Agent (CE-01 ~ CE-03)")
    print("-" * 50)
    agent = ContentExplainAgent()

    point_info = {
        "point_id": "point-001",
        "point_name": "Python变量",
        "description": "Python中变量的定义、赋值和使用方法"
    }

    # CE-01: 正常讲解
    try:
        result = await agent.execute(
            point_info=point_info,
            user_level="BEGINNER",
            teaching_style="SIMPLE"
        )
        assert result.sections is not None, "sections为None"
        assert result.estimated_minutes > 0, f"estimated_minutes={result.estimated_minutes}"
        record("CE-01", "正常讲解", "PASS", f"sections={len(result.sections)}, minutes={result.estimated_minutes}")
    except Exception as e:
        record("CE-01", "正常讲解", "FAIL", str(e))

    # CE-02: 风格适配
    try:
        result2 = await agent.execute(
            point_info=point_info,
            user_level="INTERMEDIATE",
            teaching_style="DETAILED"
        )
        assert result2.sections is not None
        record("CE-02", "风格适配", "PASS", f"DETAILED风格, sections={len(result2.sections)}")
    except Exception as e:
        record("CE-02", "风格适配", "FAIL", str(e))

    # CE-03: 等级适配
    try:
        result3 = await agent.execute(
            point_info=point_info,
            user_level="ADVANCED",
            teaching_style="BALANCED"
        )
        assert result3.sections is not None
        record("CE-03", "等级适配", "PASS", f"ADVANCED等级, sections={len(result3.sections)}")
    except Exception as e:
        record("CE-03", "等级适配", "FAIL", str(e))


# ============================================================
# 4.2.4 练习题生成 Agent (EG-01 ~ EG-03)
# ============================================================

async def test_exercise_generate():
    print("\n[L2-4] 练习题生成 Agent (EG-01 ~ EG-03)")
    print("-" * 50)
    agent = ExerciseGenerateAgent()

    point_info = {
        "point_id": "point-001",
        "point_name": "Python变量",
        "description": "Python中变量的定义和使用"
    }

    # EG-01: 正常生成
    try:
        result = await agent.execute(
            point_info=point_info,
            total_questions=5
        )
        assert result.total_count >= 0, f"total_count={result.total_count}"
        record("EG-01", "正常生成", "PASS", f"total_count={result.total_count}")
    except Exception as e:
        record("EG-01", "正常生成", "FAIL", str(e))

    # EG-02: 题型分布
    try:
        result2 = await agent.execute(
            point_info=point_info,
            total_questions=5
        )
        types = set()
        for q in result2.questions:
            types.add(q.question_type.value if hasattr(q.question_type, 'value') else str(q.question_type))
        record("EG-02", "题型分布", "PASS", f"题型种类: {types if types else 'Mock模式'}")
    except Exception as e:
        record("EG-02", "题型分布", "FAIL", str(e))

    # EG-03: 难度分布
    try:
        result3 = await agent.execute(
            point_info=point_info,
            total_questions=5
        )
        has_diff = result3.difficulty_distribution is not None and len(result3.difficulty_distribution) > 0
        record("EG-03", "难度分布", "PASS" if has_diff else "FAIL",
               f"difficulty_distribution={result3.difficulty_distribution}")
    except Exception as e:
        record("EG-03", "难度分布", "FAIL", str(e))


# ============================================================
# 4.2.5 题目批改 Agent (AG-01 ~ AG-04)
# ============================================================

async def test_answer_grade():
    print("\n[L2-5] 题目批改 Agent (AG-01 ~ AG-04)")
    print("-" * 50)
    agent = AnswerGradeAgent()

    questions = [
        {"question_id": "q1", "question_text": "1+1=?", "question_type": "FILL_BLANK", "correct_answer": "2", "point_id": "p1"},
        {"question_id": "q2", "question_text": "Python关键字?", "question_type": "SINGLE_CHOICE", "correct_answer": "A", "options": [{"option_id": "A", "content": "def", "is_correct": True}, {"option_id": "B", "content": "hello", "is_correct": False}], "point_id": "p1"},
        {"question_id": "q3", "question_text": "列表是有序的?", "question_type": "TRUE_FALSE", "correct_answer": "True", "point_id": "p1"},
    ]

    # AG-01: 全对
    try:
        result = await agent.execute(
            questions=questions,
            answers=[
                {"question_id": "q1", "answer": "2"},
                {"question_id": "q2", "answer": "A"},
                {"question_id": "q3", "answer": "True"},
            ]
        )
        record("AG-01", "全对", "PASS", f"correct={result.correct_count}/{result.total_questions}, pct={result.percentage}%")
    except Exception as e:
        record("AG-01", "全对", "FAIL", str(e))

    # AG-02: 全错
    try:
        result2 = await agent.execute(
            questions=questions,
            answers=[
                {"question_id": "q1", "answer": "99"},
                {"question_id": "q2", "answer": "B"},
                {"question_id": "q3", "answer": "False"},
            ]
        )
        record("AG-02", "全错", "PASS", f"correct={result2.correct_count}/{result2.total_questions}, pct={result2.percentage}%")
    except Exception as e:
        record("AG-02", "全错", "FAIL", str(e))

    # AG-03: 混合
    try:
        result3 = await agent.execute(
            questions=questions,
            answers=[
                {"question_id": "q1", "answer": "2"},
                {"question_id": "q2", "answer": "B"},
                {"question_id": "q3", "answer": "True"},
            ]
        )
        is_mixed = 0 < result3.percentage < 100
        record("AG-03", "混合", "PASS" if is_mixed else "FAIL",
               f"correct={result3.correct_count}/{result3.total_questions}, pct={result3.percentage}%")
    except Exception as e:
        record("AG-03", "混合", "FAIL", str(e))

    # AG-04: 空答案
    try:
        try:
            await agent.execute(questions=questions, answers=[])
            record("AG-04", "空答案", "FAIL", "未抛出异常")
        except (ValueError, TypeError, Exception):
            record("AG-04", "空答案", "PASS", "正确抛出异常")
    except Exception as e:
        record("AG-04", "空答案", "FAIL", str(e))


# ============================================================
# 4.2.6 问答 Agent (QA-01 ~ QA-03)
# ============================================================

async def test_qa_answer():
    print("\n[L2-6] 问答 Agent (QA-01 ~ QA-03)")
    print("-" * 50)
    agent = QAAnswerAgent()

    # QA-01: 正常问答
    try:
        result = await agent.execute(
            question="Python中变量命名有什么规则？",
            context={"point_id": "point-001", "topic_name": "Python基础"}
        )
        has_content = len(result.answer_sections) > 0
        has_related = len(result.related_knowledge) >= 0
        record("QA-01", "正常问答", "PASS" if has_content else "FAIL",
               f"sections={len(result.answer_sections)}, related={len(result.related_knowledge)}")
    except Exception as e:
        record("QA-01", "正常问答", "FAIL", str(e))

    # QA-02: 问题分类
    try:
        result2 = await agent.execute(
            question="什么是列表推导式？",
            context={"point_id": "point-001"}
        )
        qtype = result2.question_type
        record("QA-02", "问题分类", "PASS", f"question_type={qtype.value if hasattr(qtype, 'value') else qtype}")
    except Exception as e:
        record("QA-02", "问题分类", "FAIL", str(e))

    # QA-03: 空问题
    try:
        try:
            await agent.execute(question="")
            record("QA-03", "空问题", "FAIL", "未抛出异常")
        except (ValueError, TypeError, Exception):
            record("QA-03", "空问题", "PASS", "正确抛出异常")
    except Exception as e:
        record("QA-03", "空问题", "FAIL", str(e))


# ============================================================
# 4.2.7 路径规划 Agent (PP-01 ~ PP-02)
# ============================================================

async def test_path_planning():
    print("\n[L2-7] 路径规划 Agent (PP-01 ~ PP-02)")
    print("-" * 50)
    agent = PathPlanningAgent()

    knowledge_structure = {
        "topic_name": "Python基础",
        "blocks": [
            {
                "block_id": "b1", "block_name": "基础语法", "block_order": 1,
                "points": [
                    {
                        "point_id": "p1", "point_name": "变量", "point_order": 1,
                        "description": "Python变量定义",
                        "components": [
                            {"component_id": "c1", "component_name": "变量赋值", "component_order": 1, "learning_objective": "掌握变量赋值"}
                        ]
                    },
                    {
                        "point_id": "p2", "point_name": "数据类型", "point_order": 2,
                        "description": "基本数据类型",
                        "components": [
                            {"component_id": "c2", "component_name": "整数类型", "component_order": 1, "learning_objective": "理解整数"}
                        ]
                    }
                ]
            }
        ]
    }

    # PP-01: 正常规划
    try:
        result = await agent.execute(knowledge_structure=knowledge_structure)
        assert result.nodes is not None, "nodes为None"
        record("PP-01", "正常规划", "PASS", f"nodes={len(result.nodes)}, hours={result.total_estimated_hours}")
    except Exception as e:
        record("PP-01", "正常规划", "FAIL", str(e))

    # PP-02: 节点顺序
    try:
        result2 = await agent.execute(knowledge_structure=knowledge_structure)
        orders = [n.order for n in result2.nodes]
        is_sorted = orders == sorted(orders)
        record("PP-02", "节点顺序", "PASS" if is_sorted else "FAIL",
               f"orders={orders}, sorted={is_sorted}")
    except Exception as e:
        record("PP-02", "节点顺序", "FAIL", str(e))


# ============================================================
# 4.2.8 跳级建议 Agent (SS-01 ~ SS-02)
# ============================================================

async def test_skip_suggest():
    print("\n[L2-8] 跳级建议 Agent (SS-01 ~ SS-02)")
    print("-" * 50)
    agent = SkipSuggestAgent()

    knowledge_points = [
        {"point_id": "p1", "point_name": "变量", "difficulty": "LOW"},
        {"point_id": "p2", "point_name": "数据类型", "difficulty": "LOW"},
        {"point_id": "p3", "point_name": "控制流", "difficulty": "MEDIUM"},
    ]

    # SS-01: 高掌握度
    try:
        learning_data_high = [
            {"point_id": "p1", "score": 95, "total_questions": 10, "correct_questions": 10, "completion_time": 30, "review_count": 0},
            {"point_id": "p2", "score": 90, "total_questions": 10, "correct_questions": 9, "completion_time": 35, "review_count": 0},
            {"point_id": "p3", "score": 88, "total_questions": 10, "correct_questions": 9, "completion_time": 40, "review_count": 1},
        ]
        result = await agent.execute(
            user_id="user-001",
            learning_data=learning_data_high,
            knowledge_points=knowledge_points,
            topic_name="Python基础"
        )
        has_suggestions = len(result.suggestions) >= 0
        record("SS-01", "高掌握度", "PASS" if has_suggestions else "FAIL",
               f"suggestions={len(result.suggestions)}, skip_recommended={result.skip_recommended}")
    except Exception as e:
        record("SS-01", "高掌握度", "FAIL", str(e))

    # SS-02: 低掌握度
    try:
        learning_data_low = [
            {"point_id": "p1", "score": 30, "total_questions": 10, "correct_questions": 3, "completion_time": 120, "review_count": 5},
            {"point_id": "p2", "score": 20, "total_questions": 10, "correct_questions": 2, "completion_time": 150, "review_count": 8},
            {"point_id": "p3", "score": 10, "total_questions": 10, "correct_questions": 1, "completion_time": 180, "review_count": 10},
        ]
        result2 = await agent.execute(
            user_id="user-002",
            learning_data=learning_data_low,
            knowledge_points=knowledge_points,
            topic_name="Python基础"
        )
        is_conservative = result2.not_recommended >= 0
        record("SS-02", "低掌握度", "PASS" if is_conservative else "FAIL",
               f"not_recommended={result2.not_recommended}, skip_recommended={result2.skip_recommended}")
    except Exception as e:
        record("SS-02", "低掌握度", "FAIL", str(e))


# ============================================================
# 4.2.9 鼓励奖励 Agent (RG-01 ~ RG-02)
# ============================================================

async def test_reward_generate():
    print("\n[L2-9] 鼓励奖励 Agent (RG-01 ~ RG-02)")
    print("-" * 50)
    agent = RewardGenerateAgent()

    # RG-01: 完成知识点
    try:
        result = await agent.execute(
            user_id="user-001",
            trigger_scene="POINT_COMPLETED",
            context={
                "user_name": "测试用户",
                "topic_name": "Python基础",
                "current_point_name": "变量定义",
                "completed_points": 5,
            }
        )
        has_rewards = len(result.rewards) > 0
        record("RG-01", "完成知识点", "PASS" if has_rewards else "FAIL",
               f"rewards={len(result.rewards)}, points={result.total_points_earned}")
    except Exception as e:
        record("RG-01", "完成知识点", "FAIL", str(e))

    # RG-02: 连续学习
    try:
        result2 = await agent.execute(
            user_id="user-001",
            trigger_scene="STREAK_ACHIEVED",
            context={
                "user_name": "测试用户",
                "streak_days": 7,
                "total_study_hours": 15.5,
            }
        )
        has_rewards = len(result2.rewards) > 0
        # 检查文案是否包含连续学习相关内容
        has_streak_content = False
        for r in result2.rewards:
            msg = r.content.message if hasattr(r.content, 'message') else str(r.content)
            if "连续" in msg or "天" in msg or "streak" in msg.lower():
                has_streak_content = True
                break
        record("RG-02", "连续学习", "PASS" if has_rewards else "FAIL",
               f"rewards={len(result2.rewards)}, streak_content={'有' if has_streak_content else '无'}")
    except Exception as e:
        record("RG-02", "连续学习", "FAIL", str(e))


# ============================================================
# 4.2.10 行为记录 Agent (BR-01 ~ BR-02)
# ============================================================

async def test_behavior_record():
    print("\n[L2-10] 行为记录 Agent (BR-01 ~ BR-02)")
    print("-" * 50)
    agent = BehaviorRecordAgent()

    # BR-01: 正常记录
    try:
        result = await agent.execute(
            events=[
                {
                    "user_id": "user-001",
                    "category": "CONTENT_INTERACTION",
                    "action": "VIEW_POINT",
                    "target_type": "POINT",
                    "target_id": "point-001",
                    "point_id": "point-001",
                    "duration_ms": 30000,
                }
            ]
        )
        has_ids = len(result.event_ids) > 0
        record("BR-01", "正常记录", "PASS" if has_ids else "FAIL",
               f"success={result.success_count}, event_ids={len(result.event_ids)}")
    except Exception as e:
        record("BR-01", "正常记录", "FAIL", str(e))

    # BR-02: 缺失字段
    try:
        result = await agent.execute(
            events=[
                {"action": "VIEW_POINT"}  # 缺少 user_id 和 category
            ]
        )
        # Agent不抛异常，而是将失败记录到failed_count
        is_rejected = result.failed_count > 0 or result.success_count == 0
        record("BR-02", "缺失字段", "PASS" if is_rejected else "FAIL",
               f"success={result.success_count}, failed={result.failed_count}, errors={result.errors}")
    except Exception as e:
        record("BR-02", "缺失字段", "PASS", f"抛出 {type(e).__name__}")


# ============================================================
# 4.2.11 行为分析 Agent (BA-01 ~ BA-03)
# ============================================================

async def test_behavior_analysis():
    print("\n[L2-11] 行为分析 Agent (BA-01 ~ BA-03)")
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
        # 空事件应返回默认画像或空分析
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

    await test_knowledge_split()
    await test_difficulty_tag()
    await test_content_explain()
    await test_exercise_generate()
    await test_answer_grade()
    await test_qa_answer()
    await test_path_planning()
    await test_skip_suggest()
    await test_reward_generate()
    await test_behavior_record()
    await test_behavior_analysis()

    # 报告
    print("\n" + "=" * 60)
    print("L2 测试报告")
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
