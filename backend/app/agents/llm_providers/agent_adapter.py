"""
Agent LLM适配器

为现有Agent提供统一的LLM调用接口
兼容旧版llm_client参数，同时支持新的Provider系统
"""

import logging
from typing import Any, Dict, List, Optional, Union

from .base import LLMProvider, LLMMessage, LLMResponse
from .factory import get_provider, ProviderFactory
from .config import ProviderType
from .mock_client import get_mock_client

logger = logging.getLogger(__name__)


class AgentLLMClient:
    """
    Agent LLM客户端适配器

    为Agent提供统一的LLM调用接口
    兼容旧版LangChain风格的agenerate方法
    同时支持新的Provider系统
    """

    def __init__(
        self,
        provider: Optional[Union[LLMProvider, ProviderType, str]] = None,
        llm_client=None  # 兼容旧版参数
    ):
        """
        初始化Agent LLM客户端

        Args:
            provider: Provider实例、ProviderType或Provider名称
            llm_client: 兼容旧版llm_client参数
        """
        self._provider: Optional[LLMProvider] = None
        self._legacy_client = llm_client
        self._mock_client = get_mock_client()  # 模拟客户端

        # 如果传入了Provider，直接使用
        if isinstance(provider, LLMProvider):
            self._provider = provider
        # 如果传入了ProviderType，获取对应Provider
        elif isinstance(provider, ProviderType):
            self._provider = get_provider(provider)
        # 如果传入了字符串，尝试解析为ProviderType
        elif isinstance(provider, str):
            try:
                provider_type = ProviderType(provider.lower())
                self._provider = get_provider(provider_type)
            except ValueError:
                logger.warning(f"未知的Provider类型: {provider}")

        # 如果没有指定Provider，尝试使用默认Provider
        if self._provider is None and llm_client is None:
            self._provider = ProviderFactory.get_default()
            if self._provider is None:
                logger.info("使用模拟LLM客户端（无需API Key）")

    @property
    def provider(self) -> Optional[LLMProvider]:
        """获取当前使用的Provider"""
        return self._provider

    async def agenerate(self, prompts: List[str], **kwargs) -> "LLMGenerationResult":
        """
        兼容LangChain风格的批量生成接口

        Args:
            prompts: Prompt列表
            **kwargs: 额外参数

        Returns:
            LLMGenerationResult对象
        """
        # 优先使用新Provider系统
        if self._provider:
            return await self._provider.agenerate(prompts, **kwargs)

        # 兼容旧版llm_client
        if self._legacy_client:
            return await self._legacy_client.agenerate(prompts, **kwargs)

        # 使用模拟客户端
        return await self._mock_client.agenerate(prompts, **kwargs)

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        单条生成接口

        Args:
            prompt: 用户输入
            system_prompt: 系统提示
            temperature: 温度
            max_tokens: 最大token数
            **kwargs: 额外参数

        Returns:
            生成的文本
        """
        if self._provider:
            messages = []
            if system_prompt:
                messages.append(LLMMessage(role="system", content=system_prompt))
            messages.append(LLMMessage(role="user", content=prompt))

            response = await self._provider.generate(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            return response.content

        # 兼容旧版
        if self._legacy_client:
            result = await self._legacy_client.agenerate([prompt], **kwargs)
            return result.generations[0][0].text

        # 使用模拟客户端
        result = await self._mock_client.agenerate([prompt], **kwargs)
        return result.generations[0][0].text

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        """
        流式生成接口

        Args:
            prompt: 用户输入
            system_prompt: 系统提示
            temperature: 温度
            max_tokens: 最大token数
            **kwargs: 额外参数

        Yields:
            生成的文本片段
        """
        if self._provider:
            messages = []
            if system_prompt:
                messages.append(LLMMessage(role="system", content=system_prompt))
            messages.append(LLMMessage(role="user", content=prompt))

            async for chunk in self._provider.generate_stream(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            ):
                yield chunk
        else:
            # fallback: 非流式生成后逐字输出
            result = await self.generate(prompt, system_prompt, temperature, max_tokens, **kwargs)
            for char in result:
                yield char


# 便捷函数
def create_llm_client(
    provider: Optional[Union[ProviderType, str]] = None,
    **kwargs
) -> AgentLLMClient:
    """
    创建LLM客户端

    Args:
        provider: Provider类型或名称
        **kwargs: 额外参数

    Returns:
        AgentLLMClient实例
    """
    return AgentLLMClient(provider=provider, **kwargs)


def get_default_llm_client() -> AgentLLMClient:
    """
    获取默认LLM客户端

    Returns:
        AgentLLMClient实例
    """
    return AgentLLMClient()
