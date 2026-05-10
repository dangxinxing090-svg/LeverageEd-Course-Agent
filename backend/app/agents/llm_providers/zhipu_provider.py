"""
智谱GLM Provider 实现

支持智谱AI的GLM系列模型
API文档: https://open.bigmodel.cn/dev/howuse/glm-4
"""

import logging
from typing import Any, Dict, List, Optional, AsyncGenerator

from .base import LLMProvider, LLMResponse, LLMMessage, ProviderConfig, ProviderType, ModelCapability

logger = logging.getLogger(__name__)

# 尝试导入zhipuai库
try:
    from zhipuai import ZhipuAI
    HAS_ZHIPUAI = True
except ImportError:
    HAS_ZHIPUAI = False
    logger.warning("未安装zhipuai库，ZhipuProvider将使用模拟模式")


class ZhipuProvider(LLMProvider):
    """
    智谱GLM Provider实现

    支持GLM-4、GLM-3-Turbo等模型
    """

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self._client: Optional[Any] = None

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.ZHIPU

    @property
    def supported_capabilities(self) -> List[ModelCapability]:
        return [
            ModelCapability.CHAT,
            ModelCapability.FUNCTION_CALLING,
            ModelCapability.JSON_MODE,
            ModelCapability.STREAMING,
        ]

    async def initialize(self) -> None:
        """初始化智谱客户端"""
        if not HAS_ZHIPUAI:
            logger.warning("zhipuai库未安装，使用模拟模式")
            self._initialized = True
            return

        try:
            self._client = ZhipuAI(
                api_key=self.config.api_key,
                base_url=self.config.api_base,
            )
            self._initialized = True
            logger.info(f"智谱GLM Provider已初始化，模型: {self.config.model}")
        except Exception as e:
            logger.error(f"智谱GLM Provider初始化失败: {e}")
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
        if not HAS_ZHIPUAI or self._client is None:
            return self._mock_generate(messages)

        # 转换消息格式（智谱使用OpenAI兼容格式）
        zhipu_messages = [msg.to_dict() for msg in messages]

        # 获取生成参数
        params = self._get_generation_params(temperature, max_tokens)

        try:
            # 智谱SDK使用同步调用，使用线程池执行
            import asyncio
            loop = asyncio.get_event_loop()

            def _sync_call():
                return self._client.chat.completions.create(
                    model=self.config.model,
                    messages=zhipu_messages,
                    temperature=params["temperature"],
                    max_tokens=params["max_tokens"],
                    **self.config.extra_params,
                    **kwargs
                )

            response = await loop.run_in_executor(None, _sync_call)

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
            logger.error(f"智谱GLM API调用失败: {e}")
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

        if not HAS_ZHIPUAI or self._client is None:
            response = self._mock_generate(messages)
            yield response.content
            return

        zhipu_messages = [msg.to_dict() for msg in messages]
        params = self._get_generation_params(temperature, max_tokens)

        try:
            import asyncio
            loop = asyncio.get_event_loop()

            def _sync_stream():
                return self._client.chat.completions.create(
                    model=self.config.model,
                    messages=zhipu_messages,
                    temperature=params["temperature"],
                    max_tokens=params["max_tokens"],
                    stream=True,
                    **self.config.extra_params,
                    **kwargs
                )

            stream = await loop.run_in_executor(None, _sync_stream)

            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"智谱GLM流式生成失败: {e}")
            raise

    def _mock_generate(self, messages: List[LLMMessage]) -> LLMResponse:
        """模拟生成"""
        user_message = ""
        for msg in reversed(messages):
            if msg.role == "user":
                user_message = msg.content
                break

        mock_content = f"[智谱GLM模拟响应] 收到消息: {user_message[:50]}..."

        return LLMResponse(
            content=mock_content,
            model=self.config.model,
            provider=self.provider_type,
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            finish_reason="stop",
        )


# 注册Provider
from .factory import register_provider
register_provider(ProviderType.ZHIPU, ZhipuProvider)
