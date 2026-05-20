"""
LLM Provider 多模型支持模块

核心职责：提供统一接口支持多种LLM模型
支持：OpenAI、智谱GLM、Kimi、Qwen、豆包

底层执行逻辑：
1. 定义统一的LLMProvider接口
2. 为每个模型实现特定的Provider适配器
3. 提供Provider工厂和配置管理
4. 支持运行时动态切换模型

内存数据流转：
配置加载 → Provider初始化 → 统一接口调用 → 响应解析 → 返回

潜在风险：
1. 内存泄漏：Provider实例未正确释放（已实现单例模式）
2. 逻辑漏洞：不同模型响应格式不一致（已统一解析）
3. 边界条件：API限流和超时处理（已实现重试机制）
4. 质量风险：模型输出质量差异（已添加质量校验）
"""

from .base import (
    LLMProvider,
    LLMResponse,
    LLMMessage,
    ProviderConfig,
    ProviderType,
    ModelCapability,
)

from .config import (
    LLMConfigManager,
    get_llm_config,
    load_provider_config,
)

from .factory import (
    ProviderFactory,
    get_provider,
    create_provider,
    list_available_providers,
    list_registered_providers,
)

# 具体Provider实现
from .openai_provider import OpenAIProvider
from .zhipu_provider import ZhipuProvider
from .kimi_provider import KimiProvider
from .qwen_provider import QwenProvider
from .doubao_provider import DoubaoProvider
from .deepseek_provider import DeepSeekProvider

# Agent适配器
from .agent_adapter import (
    AgentLLMClient,
    create_llm_client,
    get_default_llm_client,
)

__all__ = [
    # 基础接口
    "LLMProvider",
    "LLMResponse",
    "LLMMessage",
    "ProviderConfig",
    "ProviderType",
    "ModelCapability",
    # 配置管理
    "LLMConfigManager",
    "get_llm_config",
    "load_provider_config",
    # 工厂
    "ProviderFactory",
    "get_provider",
    "create_provider",
    "list_available_providers",
    "list_registered_providers",
    # Provider实现
    "OpenAIProvider",
    "ZhipuProvider",
    "KimiProvider",
    "QwenProvider",
    "DoubaoProvider",
    # Agent适配器
    "AgentLLMClient",
    "create_llm_client",
    "get_default_llm_client",
]
