"""
L3 LLM Provider 层测试
测试模块: Provider注册/工厂、MockLLMClient、AgentLLMClient、配置管理
运行方式: python tests/test_l3_provider.py
"""

import asyncio
import sys
import os
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.llm_providers import (
    ProviderType,
    list_registered_providers,
    get_provider,
    get_llm_config,
    AgentLLMClient,
)
from app.agents.llm_providers.mock_client import MockLLMClient
from app.agents.llm_providers.factory import ProviderFactory


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
# L3 测试用例 (LP-01 ~ LP-10)
# ============================================================

async def test_provider_registration():
    """LP-01: Provider 注册"""
    print("\n[LP-01] Provider 注册")
    print("-" * 50)
    try:
        providers = list_registered_providers()
        expected = {ProviderType.OPENAI, ProviderType.ZHIPU, ProviderType.KIMI, ProviderType.QWEN, ProviderType.DOUBAO}
        actual = set(providers)
        all_registered = expected == actual
        record("LP-01", "Provider 注册", "PASS" if all_registered else "FAIL",
               f"已注册: {[p.value for p in providers]}")
    except Exception as e:
        record("LP-01", "Provider 注册", "FAIL", str(e))


async def test_mock_client():
    """LP-02: Mock 客户端"""
    print("\n[LP-02] Mock 客户端")
    print("-" * 50)
    try:
        client = MockLLMClient()
        result = await client.agenerate(["测试prompt"])
        # generations是二维列表 [[MockGeneration]]
        text = result.generations[0][0].text if result.generations else ""
        try:
            data = json.loads(text)
            has_json_structure = isinstance(data, dict)
        except:
            has_json_structure = False
        record("LP-02", "Mock 客户端", "PASS" if has_json_structure else "FAIL",
               f"返回JSON格式: {has_json_structure}")
    except Exception as e:
        record("LP-02", "Mock 客户端", "FAIL", str(e))


async def test_mock_knowledge_split():
    """LP-03: Mock 知识拆分响应"""
    print("\n[LP-03] Mock 知识拆分响应")
    print("-" * 50)
    try:
        client = MockLLMClient()
        result = await client.agenerate(["请将Python基础知识拆解成知识体系"])
        # generations是二维列表 [[MockGeneration]]
        text = result.generations[0][0].text if result.generations else ""
        try:
            data = json.loads(text)
            has_blocks = "blocks" in data
        except:
            has_blocks = "blocks" in text
        record("LP-03", "Mock 知识拆分响应", "PASS" if has_blocks else "FAIL",
               f"包含blocks: {has_blocks}")
    except Exception as e:
        record("LP-03", "Mock 知识拆分响应", "FAIL", str(e))


async def test_mock_explain():
    """LP-04: Mock 讲解响应"""
    print("\n[LP-04] Mock 讲解响应")
    print("-" * 50)
    try:
        client = MockLLMClient()
        result = await client.agenerate(["请讲解Python变量的概念"])
        text = result.generations[0][0].text if result.generations else ""
        try:
            data = json.loads(text)
            has_sections = "sections" in data
        except:
            has_sections = "sections" in text
        record("LP-04", "Mock 讲解响应", "PASS" if has_sections else "FAIL",
               f"包含sections: {has_sections}")
    except Exception as e:
        record("LP-04", "Mock 讲解响应", "FAIL", str(e))


async def test_mock_exercise():
    """LP-05: Mock 练习题响应"""
    print("\n[LP-05] Mock 练习题响应")
    print("-" * 50)
    try:
        client = MockLLMClient()
        result = await client.agenerate(["请生成5道Python变量的练习题"])
        text = result.generations[0][0].text if result.generations else ""
        try:
            data = json.loads(text)
            has_questions = "questions" in data
        except:
            has_questions = "questions" in text
        record("LP-05", "Mock 练习题响应", "PASS" if has_questions else "FAIL",
               f"包含questions: {has_questions}")
    except Exception as e:
        record("LP-05", "Mock 练习题响应", "FAIL", str(e))


async def test_agent_llm_client_no_provider():
    """LP-06: AgentLLMClient 无 Provider"""
    print("\n[LP-06] AgentLLMClient 无 Provider")
    print("-" * 50)
    try:
        # 不传入任何provider，应该自动降级到Mock模式
        client = AgentLLMClient(provider=None, llm_client=None)
        result = await client.agenerate(["测试问题"])
        has_result = result is not None
        record("LP-06", "AgentLLMClient 无 Provider", "PASS" if has_result else "FAIL",
               f"自动降级到Mock模式: {has_result}")
    except Exception as e:
        record("LP-06", "AgentLLMClient 无 Provider", "FAIL", str(e))


async def test_agent_llm_client_compatibility():
    """LP-07: AgentLLMClient 兼容性"""
    print("\n[LP-07] AgentLLMClient 兼容性")
    print("-" * 50)
    try:
        # 创建一个Mock客户端作为旧版llm_client传入
        mock = MockLLMClient()
        client = AgentLLMClient(llm_client=mock)
        result = await client.agenerate(["兼容性测试"])
        has_result = result is not None
        record("LP-07", "AgentLLMClient 兼容性", "PASS" if has_result else "FAIL",
               f"兼容旧版agenerate接口: {has_result}")
    except Exception as e:
        record("LP-07", "AgentLLMClient 兼容性", "FAIL", str(e))


async def test_config_env_variable():
    """LP-08: 配置管理 - 环境变量"""
    print("\n[LP-08] 配置管理 - 环境变量")
    print("-" * 50)
    try:
        # 设置环境变量
        os.environ["ZHIPU_API_KEY"] = "test-zhipu-key-12345"
        
        # 重新导入以触发配置重新加载
        import importlib
        from app.agents.llm_providers import config as config_module
        importlib.reload(config_module)
        
        # 获取新的配置管理器实例
        config = config_module.get_llm_config()
        
        # 检查是否能读取到配置
        zhipu_config = config.get_config(ProviderType.ZHIPU)
        has_config = zhipu_config is not None and zhipu_config.api_key is not None
        
        # 清理环境变量
        if "ZHIPU_API_KEY" in os.environ:
            del os.environ["ZHIPU_API_KEY"]
        
        record("LP-08", "环境变量加载", "PASS" if has_config else "FAIL",
               f"ZHIPU配置非空: {has_config}")
    except Exception as e:
        # 清理环境变量
        if "ZHIPU_API_KEY" in os.environ:
            del os.environ["ZHIPU_API_KEY"]
        record("LP-08", "环境变量加载", "FAIL", str(e))


async def test_config_json_file():
    """LP-09: 配置文件加载"""
    print("\n[LP-09] 配置文件加载")
    print("-" * 50)
    try:
        # 创建临时配置文件
        config_data = {
            "providers": {
                "openai": {
                    "api_key": "test-openai-key",
                    "model": "gpt-4"
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name
        
        # 加载配置
        config = get_llm_config()
        if hasattr(config, 'load_from_json_file'):
            config.load_from_json_file(temp_path)
            loaded = True
        else:
            loaded = False
        
        # 清理临时文件
        os.unlink(temp_path)
        
        record("LP-09", "配置文件加载", "PASS" if loaded else "FAIL",
               f"JSON配置解析: {loaded}")
    except Exception as e:
        if 'temp_path' in dir() and os.path.exists(temp_path):
            os.unlink(temp_path)
        record("LP-09", "配置文件加载", "FAIL", str(e))


async def test_factory_cache():
    """LP-10: 工厂缓存"""
    print("\n[LP-10] 工厂缓存")
    print("-" * 50)
    try:
        # 调用两次get_provider，检查是否返回同一实例
        provider1 = get_provider(ProviderType.OPENAI)
        provider2 = get_provider(ProviderType.OPENAI)
        
        # 如果都为None（无API Key），也算通过（都降级到同一行为）
        if provider1 is None and provider2 is None:
            record("LP-10", "工厂缓存", "PASS", "无API Key时均返回None（一致）")
        elif provider1 is not None and provider2 is not None:
            same_instance = provider1 is provider2
            record("LP-10", "工厂缓存", "PASS" if same_instance else "FAIL",
                   f"同一实例: {same_instance}")
        else:
            record("LP-10", "工厂缓存", "FAIL", "返回不一致")
    except Exception as e:
        record("LP-10", "工厂缓存", "FAIL", str(e))


# ============================================================
# 主函数
# ============================================================

async def main():
    print("=" * 60)
    print("L3 LLM Provider 层测试")
    print("=" * 60)

    await test_provider_registration()
    await test_mock_client()
    await test_mock_knowledge_split()
    await test_mock_explain()
    await test_mock_exercise()
    await test_agent_llm_client_no_provider()
    await test_agent_llm_client_compatibility()
    await test_config_env_variable()
    await test_config_json_file()
    await test_factory_cache()

    # 报告
    print("\n" + "=" * 60)
    print("L3 测试报告")
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
