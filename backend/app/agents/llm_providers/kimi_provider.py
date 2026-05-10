"""
Kimi (Moonshot) Provider 实现

支持Moonshot AI的Kimi系列模型
API文档: https://platform.moonshot.cn/docs
"""

import logging
from typing import Any, Dict, List, Optional, AsyncGenerator

from .base import LLMProvider, LLMResponse, LLMMessage, ProviderConfig, ProviderType, ModelCapability

logger = logging.getLogger(__name__)

# 尝试导入openai库（Kimi使用OpenAI兼容API）
try:
    from openai import AsyncOpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    logger.warning("未安装openai库，KimiProvider将使用模拟模式")


class KimiProvider(LLMProvider):
    """
    Kimi (Moonshot) Provider实现

    支持moonshot-v1-8k、moonshot-v1-32k、moonshot-v1-128k等模型
    """

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self._client: Optional[Any] = None

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.KIMI

    @property
    def supported_capabilities(self) -> List[ModelCapability]:
        return [
            ModelCapability.CHAT,
            ModelCapability.FUNCTION_CALLING,
            ModelCapability.JSON_MODE,
            ModelCapability.STREAMING,
        ]

    async def initialize(self) -> None:
        """初始化Kimi客户端"""
        if not HAS_OPENAI:
            logger.warning("openai库未安装，使用模拟模式")
            self._initialized = True
            return

        try:
            # Kimi使用OpenAI兼容API
            api_base = self.config.api_base or "https://api.moonshot.cn/v1"
            self._client = AsyncOpenAI(
                api_key=self.config.api_key,
                base_url=api_base,
                timeout=self.config.timeout,
                max_retries=self.config.max_retries,
            )
            self._initialized = True
            logger.info(f"Kimi Provider已初始化，模型: {self.config.model}")
        except Exception as e:
            logger.error(f"Kimi Provider初始化失败: {e}")
            raise

    async def generate(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        生成文本

        Args:
            messages: 消息列表
            temperature: 温度
            max_tokens: 最大token数
            **kwargs: 额外参数

        Returns:
            LLMResponse对象
        """
        if not self._initialized:
            await self.initialize()

        # 模拟模式
        if not HAS_OPENAI or self._client is None:
            return self._mock_generate(messages)

        # 转换消息格式
        kimi_messages = [msg.to_dict() for msg in messages]

        # 获取生成参数
        params = self._get_generation_params(temperature, max_tokens)

        try:
            response = await self._client.chat.completions.create(
                model=self.config.model,
                messages=kimi_messages,
                temperature=params["temperature"],
                max_tokens=params["max_tokens"],
                **self.config.extra_params,
                **kwargs
            )

            # 解析响应
            choice = response.choices[0]
            content = choice.message.content or ""

            return LLMResponse(
                content=content,
                model=response.model,
                provider=self.provider_type,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                },
                finish_reason=choice.finish_reason,
                raw_response=response if kwargs.get("return_raw") else None,
            )

        except Exception as e:
            logger.error(f"Kimi API调用失败: {e}")
            raise

    async def generate_stream(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        流式生成文本

        Args:
            messages: 消息列表
            temperature: 温度
            max_tokens: 最大token数
            **kwargs: 额外参数

        Yields:
            生成的文本片段
        """
        if not self._initialized:
            await self.initialize()

        if not HAS_OPENAI or self._client is None:
            response = self._mock_generate(messages)
            yield response.content
            return

        kimi_messages = [msg.to_dict() for msg in messages]
        params = self._get_generation_params(temperature, max_tokens)

        try:
            stream = await self._client.chat.completions.create(
                model=self.config.model,
                messages=kimi_messages,
                temperature=params["temperature"],
                max_tokens=params["max_tokens"],
                stream=True,
                **self.config.extra_params,
                **kwargs
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"Kimi流式生成失败: {e}")
            raise

    def _mock_generate(self, messages: List[LLMMessage]) -> LLMResponse:
        """模拟生成"""
        user_message = ""
        for msg in reversed(messages):
            if msg.role == "user":
                user_message = msg.content
                break

        mock_content = f"[Kimi模拟响应] 收到消息: {user_message[:50]}..."

        return LLMResponse(
            content=mock_content,
            model=self.config.model,
            provider=self.provider_type,
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            finish_reason="stop",
        )


# 注册Provider
from .factory import register_provider
register_provider(ProviderType.KIMI, KimiProvider)
