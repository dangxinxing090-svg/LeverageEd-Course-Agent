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
    # 行为分析
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
        self.provider_type = provider_type
        self.llm_client = None
        self.test_results: List[Dict[str, Any]] = []

    def setup(self):
        """初始化测试环境"""
        print("=" * 60)
        print("AI智能教育课程平台 - Agent系统测试")
        print("=" * 60)

        self.llm_client = AgentLLMClient()
        print("\n使用模拟模式（无需API Key）")
        print("-" * 60)

    async def run_all_tests(self):
        """运行所有测试"""
        print("\n开始运行测试...\n")

        # 行为分析测试
        await self.test_behavior_analysis()

        # 打印测试报告
        self.print_report()

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
        print(f"通过率: {passed/total*100:.1f}%" if total > 0 else "通过率: N/A")

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

    available = list_available_providers()
    print(f"\n已配置的Provider: {[p.value for p in available]}")

    print("\n测试模拟模式...")
    client = create_llm_client()
    result = await client.generate("测试消息")
    print(f"模拟响应: {result[:50]}...")

    print("\n✓ 多模型Provider测试完成")


async def main():
    """主函数"""
    runner = AgentTestRunner(provider_type=None)
    runner.setup()
    await runner.run_all_tests()
    await test_multi_provider()


if __name__ == "__main__":
    asyncio.run(main())
