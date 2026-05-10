"""
Agent系统测试脚本

用于测试AI智能教育课程平台的Agent功能
支持多模型Provider测试

运行方式:
    python tests/test_agents.py
"""

import asyncio
import sys
import os
from typing import Dict, Any, List

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入Agent模块
from app.agents import (
    # 知识处理
    KnowledgeSplitAgent,
    DifficultyTagAgent,
    # 学习支持
    ContentExplainAgent,
    ExerciseGenerateAgent,
    AnswerGradeAgent,
    QAAnswerAgent,
    # 路径规划
    PathPlanningAgent,
    SkipSuggestAgent,
    # 激励系统
    RewardGenerateAgent,
    # 行为分析
    BehaviorRecordAgent,
    BehaviorAnalysisAgent,
    # LLM Provider
    ProviderType,
    get_provider,
    create_llm_client,
    AgentLLMClient,
)


class AgentTestRunner:
    """Agent测试运行器"""

    def __init__(self, provider_type: str = None):
        """
        初始化测试运行器

        Args:
            provider_type: 指定Provider类型 (openai/zhipu/kimi/qwen/doubao)
        """
        self.provider_type = provider_type
        self.llm_client = None
        self.test_results: List[Dict[str, Any]] = []

    def setup(self):
        """初始化测试环境"""
        print("=" * 60)
        print("AI智能教育课程平台 - Agent系统测试")
        print("=" * 60)

        # 创建LLM客户端（模拟模式，无需API Key）
        self.llm_client = AgentLLMClient()

        print("\n使用模拟模式（无需API Key）")
        print("-" * 60)

    async def run_all_tests(self):
        """运行所有测试"""
        print("\n开始运行测试...\n")

        # 知识处理测试
        await self.test_knowledge_split()
        await self.test_difficulty_tag()

        # 学习支持测试
        await self.test_content_explain()
        await self.test_exercise_generate()
        await self.test_answer_grade()
        await self.test_qa_answer()

        # 激励系统测试
        await self.test_reward_generate()

        # 行为分析测试
        await self.test_behavior_record()
        await self.test_behavior_analysis()

        # 打印测试报告
        self.print_report()

    async def test_knowledge_split(self):
        """测试知识拆分Agent"""
        print("\n[测试] 知识拆分Agent")
        print("-" * 40)

        agent = KnowledgeSplitAgent(llm_client=self.llm_client)

        try:
            result = await agent.execute(
                topic_name="Python编程基础",
                topic_description="学习Python编程的基础知识，包括变量、数据类型、控制结构等"
            )

            print(f"✓ 主题: {result.topic_name}")
            print(f"✓ 知识板块数: {len(result.blocks)}")
            print(f"✓ 知识点总数: {result.total_points}")
            print(f"✓ 知识组件总数: {result.total_components}")
            print(f"✓ 预估学习时长: {result.estimated_hours}小时")

            self.test_results.append({
                "test": "知识拆分Agent",
                "status": "PASS",
                "details": f"生成{len(result.blocks)}个板块, {result.total_points}个知识点"
            })
        except Exception as e:
            print(f"✗ 测试失败: {e}")
            self.test_results.append({
                "test": "知识拆分Agent",
                "status": "FAIL",
                "error": str(e)
            })

    async def test_difficulty_tag(self):
        """测试难度标注Agent"""
        print("\n[测试] 难度标注Agent")
        print("-" * 40)

        agent = DifficultyTagAgent(llm_client=self.llm_client)

        try:
            result = await agent.execute(
                points=[
                    {"point_id": "p1", "point_name": "变量定义", "description": "Python变量的定义方式"},
                    {"point_id": "p2", "point_name": "数据类型", "description": "Python基本数据类型"},
                ]
            )

            print(f"✓ 标注结果数: {len(result.annotations)}")
            for ann in result.annotations[:3]:
                print(f"  - {ann.point_name}: 概念难度{ann.concept_difficulty.value}")

            self.test_results.append({
                "test": "难度标注Agent",
                "status": "PASS",
                "details": f"标注{len(result.annotations)}个知识点"
            })
        except Exception as e:
            print(f"✗ 测试失败: {e}")
            self.test_results.append({
                "test": "难度标注Agent",
                "status": "FAIL",
                "error": str(e)
            })

    async def test_content_explain(self):
        """测试知识讲解Agent"""
        print("\n[测试] 知识讲解Agent")
        print("-" * 40)

        agent = ContentExplainAgent(llm_client=self.llm_client)

        try:
            result = await agent.execute(
                point_info={
                    "point_id": "point-001",
                    "point_name": "Python变量",
                    "description": "Python中变量的定义和使用"
                },
                user_level="BEGINNER",
                teaching_style="SIMPLE"
            )

            print(f"✓ 知识点: {result.point_name}")
            print(f"✓ 章节数: {len(result.sections)}")
            print(f"✓ 预估阅读时长: {result.estimated_minutes}分钟")
            print(f"✓ 难度级别: {result.difficulty_level}")

            self.test_results.append({
                "test": "知识讲解Agent",
                "status": "PASS",
                "details": f"生成{len(result.sections)}个章节"
            })
        except Exception as e:
            print(f"✗ 测试失败: {e}")
            self.test_results.append({
                "test": "知识讲解Agent",
                "status": "FAIL",
                "error": str(e)
            })

    async def test_exercise_generate(self):
        """测试练习题生成Agent"""
        print("\n[测试] 练习题生成Agent")
        print("-" * 40)

        agent = ExerciseGenerateAgent(llm_client=self.llm_client)

        try:
            result = await agent.execute(
                point_info={
                    "point_id": "point-001",
                    "point_name": "Python变量",
                    "description": "Python中变量的定义和使用"
                },
                total_questions=5
            )

            print(f"✓ 题目总数: {result.total_count}")
            print(f"✓ 预估完成时长: {result.estimated_minutes}分钟")
            print(f"✓ 难度分布: {result.difficulty_distribution}")

            for q in result.questions[:2]:
                print(f"  - [{q.question_type.value}] {q.question_text[:30]}...")

            self.test_results.append({
                "test": "练习题生成Agent",
                "status": "PASS",
                "details": f"生成{result.total_count}道题目"
            })
        except Exception as e:
            print(f"✗ 测试失败: {e}")
            self.test_results.append({
                "test": "练习题生成Agent",
                "status": "FAIL",
                "error": str(e)
            })

    async def test_answer_grade(self):
        """测试题目批改Agent"""
        print("\n[测试] 题目批改Agent")
        print("-" * 40)

        agent = AnswerGradeAgent(llm_client=self.llm_client)

        try:
            result = await agent.execute(
                questions=[
                    {
                        "question_id": "q-001",
                        "question_type": "SINGLE_CHOICE",
                        "question_text": "Python中用什么关键字定义变量？",
                        "correct_answer": "A",
                        "options": [
                            {"option_id": "A", "content": "不需要关键字", "is_correct": True},
                            {"option_id": "B", "content": "var", "is_correct": False},
                        ]
                    }
                ],
                answers=[
                    {"question_id": "q-001", "answer": "A"}
                ]
            )

            print(f"✓ 总题数: {result.total_questions}")
            print(f"✓ 正确数: {result.correct_count}")
            print(f"✓ 得分率: {result.percentage}%")
            print(f"✓ 总体评价: {result.summary[:50]}...")

            self.test_results.append({
                "test": "题目批改Agent",
                "status": "PASS",
                "details": f"得分率{result.percentage}%"
            })
        except Exception as e:
            print(f"✗ 测试失败: {e}")
            self.test_results.append({
                "test": "题目批改Agent",
                "status": "FAIL",
                "error": str(e)
            })

    async def test_qa_answer(self):
        """测试答疑问答Agent"""
        print("\n[测试] 答疑问答Agent")
        print("-" * 40)

        agent = QAAnswerAgent(llm_client=self.llm_client)

        try:
            result = await agent.execute(
                question="Python中变量命名有什么规则？",
                context={
                    "point_id": "point-001",
                    "point_name": "Python变量",
                    "user_level": "BEGINNER"
                }
            )

            print(f"✓ 问题类型: {result.question_type.value}")
            print(f"✓ 答案质量: {result.quality.value}")
            print(f"✓ 相关知识点数: {len(result.related_knowledge)}")
            main_section = next(
                (s for s in result.answer_sections if hasattr(s, 'section_type') and s.section_type == "main"),
                result.answer_sections[0] if result.answer_sections else None
            )
            if main_section:
                print(f"✓ 答案预览: {main_section.content[:50]}...")

            self.test_results.append({
                "test": "答疑问答Agent",
                "status": "PASS",
                "details": f"质量{result.quality.value}"
            })
        except Exception as e:
            print(f"✗ 测试失败: {e}")
            self.test_results.append({
                "test": "答疑问答Agent",
                "status": "FAIL",
                "error": str(e)
            })

    async def test_reward_generate(self):
        """测试鼓励奖励Agent"""
        print("\n[测试] 鼓励奖励Agent")
        print("-" * 40)

        agent = RewardGenerateAgent(llm_client=self.llm_client)

        try:
            result = await agent.execute(
                user_id="user-001",
                trigger_scene="POINT_COMPLETED",
                context={
                    "user_name": "小明",
                    "current_point_name": "Python变量",
                    "completed_points": 5,
                    "streak_days": 3
                }
            )

            print(f"✓ 奖励数量: {len(result.rewards)}")
            print(f"✓ 获得积分: {result.total_points_earned}")
            for r in result.rewards:
                print(f"  - {r.content.title}: {r.content.message[:30]}...")

            self.test_results.append({
                "test": "鼓励奖励Agent",
                "status": "PASS",
                "details": f"获得{result.total_points_earned}积分"
            })
        except Exception as e:
            print(f"✗ 测试失败: {e}")
            self.test_results.append({
                "test": "鼓励奖励Agent",
                "status": "FAIL",
                "error": str(e)
            })

    async def test_behavior_record(self):
        """测试行为记录Agent"""
        print("\n[测试] 行为记录Agent")
        print("-" * 40)

        agent = BehaviorRecordAgent()

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
                        "context": {"duration_seconds": 300}
                    }
                ]
            )

            print(f"✓ 成功记录数: {result.success_count}")
            if result.event_ids:
                print(f"✓ 记录ID: {result.event_ids[0]}")
            print(f"✓ 失败数: {result.failed_count}, 重复数: {result.duplicate_count}")

            self.test_results.append({
                "test": "行为记录Agent",
                "status": "PASS",
                "details": f"成功记录{result.success_count}条"
            })
        except Exception as e:
            print(f"✗ 测试失败: {e}")
            self.test_results.append({
                "test": "行为记录Agent",
                "status": "FAIL",
                "error": str(e)
            })

    async def test_behavior_analysis(self):
        """测试行为分析Agent"""
        print("\n[测试] 行为分析Agent")
        print("-" * 40)

        agent = BehaviorAnalysisAgent()

        try:
            result = await agent.execute(
                user_id="user-001",
                events=[
                    {
                        "action": "VIEW_POINT",
                        "target_id": "point-001",
                        "point_id": "point-001",
                        "timestamp": "2024-01-15T10:00:00"
                    }
                ]
            )

            if result.user_profile:
                print(f"✓ 活跃等级: {result.user_profile.activity_level.value}")
                print(f"✓ 总体掌握度: {result.user_profile.overall_mastery}")
            if result.point_masteries:
                print(f"✓ 知识点掌握等级: {result.point_masteries[0].mastery_level.value}")

            self.test_results.append({
                "test": "行为分析Agent",
                "status": "PASS",
                "details": f"活跃等级: {result.user_profile.activity_level.value if result.user_profile else 'N/A'}"
            })
        except Exception as e:
            print(f"✗ 测试失败: {e}")
            self.test_results.append({
                "test": "行为分析Agent",
                "status": "FAIL",
                "error": str(e)
            })

    def print_report(self):
        """打印测试报告"""
        print("\n" + "=" * 60)
        print("测试报告")
        print("=" * 60)

        passed = sum(1 for r in self.test_results if r["status"] == "PASS")
        failed = sum(1 for r in self.test_results if r["status"] == "FAIL")
        total = len(self.test_results)

        print(f"\n总计: {total} 个测试")
        print(f"通过: {passed} 个")
        print(f"失败: {failed} 个")
        print(f"通过率: {passed/total*100:.1f}%")

        print("\n详细结果:")
        print("-" * 40)
        for r in self.test_results:
            status_icon = "✓" if r["status"] == "PASS" else "✗"
            print(f"{status_icon} {r['test']}: {r['status']}")
            if "details" in r:
                print(f"  └─ {r['details']}")
            if "error" in r:
                print(f"  └─ 错误: {r['error']}")

        print("\n" + "=" * 60)


async def test_multi_provider():
    """测试多模型切换"""
    print("\n" + "=" * 60)
    print("多模型Provider测试")
    print("=" * 60)

    from app.agents.llm_providers import list_available_providers, ProviderType

    # 列出可用Provider
    available = list_available_providers()
    print(f"\n已配置的Provider: {[p.value for p in available]}")

    # 测试模拟模式
    print("\n测试模拟模式...")
    client = create_llm_client()
    result = await client.generate("测试消息")
    print(f"模拟响应: {result[:50]}...")

    print("\n✓ 多模型Provider测试完成")


async def main():
    """主函数"""
    # 创建测试运行器
    runner = AgentTestRunner(provider_type=None)  # 使用模拟模式

    # 初始化
    runner.setup()

    # 运行所有测试
    await runner.run_all_tests()

    # 测试多模型
    await test_multi_provider()


if __name__ == "__main__":
    asyncio.run(main())
