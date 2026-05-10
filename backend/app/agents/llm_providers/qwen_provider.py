"""
Qwen (通义千问) Provider 实现

支持阿里云通义千问系列模型
API文档: https://help.aliyun.com/zh/dashscope/developer-reference/api-details
"""

import logging
from typing import Any, Dict, List, Optional, AsyncGenerator

from .base import LLMProvider, LLMResponse, LLMMessage, ProviderConfig, ProviderType, ModelCapability

logger = logging.getLogger(__name__)

# 尝试导入dashscope库
try:
    import dashscope
    from dashscope import Generation
    HAS_DASHSCOPE = True
except ImportError:
    HAS_DASHSCOPE = False
    logger.warning("未安装dashscope库，QwenProvider将使用模拟模式")


class QwenProvider(LLMProvider):
    """
    通义千问 Provider实现

    支持qwen-turbo、qwen-plus、qwen-max等模型
    """

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self._client: Optional[Any] = None

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.QWEN

    @property
    def supported_capabilities(self) -> List[ModelCapability]:
        return [
            ModelCapability.CHAT,
            ModelCapability.FUNCTION_CALLING,
            ModelCapability.JSON_MODE,
            ModelCapability.STREAMING,
        ]

    async def initialize(self) -> None:
        """初始化通义千问客户端"""
        if not HAS_DASHSCOPE:
            logger.warning("dashscope库未安装，使用模拟模式")
            self._initialized = True
            return

        try:
            # 设置API Key
            dashscope.api_key = self.config.api_key
            self._initialized = True
            logger.info(f"通义千问 Provider已初始化，模型: {self.config.model}")
        except Exception as e:
            logger.error(f"通义千问 Provider初始化失败: {e}")
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
        if not HAS_DASHSCOPE:
            return self._mock_generate(messages)

        # 转换消息格式
        qwen_messages = [msg.to_dict() for msg in messages]

        # 获取生成参数
        params = self._get_generation_params(temperature, max_tokens)

        try:
            # dashscope使用同步调用，使用线程池执行
            import asyncio
            loop = asyncio.get_event_loop()

            def _sync_call():
                return Generation.call(
                    model=self.config.model,
                    messages=qwen_messages,
                    temperature=params["temperature"],
                    max_tokens=params["max_tokens"],
                    result_format="message",
                    **self.config.extra_params,
                    **kwargs
                )

            response = await loop.run_in_executor(None, _sync_call)

            # 检查响应状态
            if response.status_code != 200:
                raise Exception(f"API调用失败: {response.message}")

            # 解析响应
            output = response.output
            usage = response.usage

            content = ""
            if output and output.choices:
                content = output.choices[0].message.content or ""

            return LLMResponse(
                content=content,
                model=self.config.model,
                provider=self.provider_type,
                usage={
                    "prompt_tokens": usage.input_tokens if usage else 0,
                    "completion_tokens": usage.output_tokens if usage else 0,
                    "total_tokens": usage.total_tokens if usage else 0,
                },
                finish_reason=output.choices[0].finish_reason if output and output.choices else None,
                raw_response=response if kwargs.get("return_raw") else None,
            )

        except Exception as e:
            logger.error(f"通义千问 API调用失败: {e}")
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

        if not HAS_DASHSCOPE:
            response = self._mock_generate(messages)
            yield response.content
            return

        qwen_messages = [msg.to_dict() for msg in messages]
        params = self._get_generation_params(temperature, max_tokens)

        try:
            import asyncio
            loop = asyncio.get_event_loop()

            def _sync_stream():
                return Generation.call(
                    model=self.config.model,
                    messages=qwen_messages,
                    temperature=params["temperature"],
                    max_tokens=params["max_tokens"],
                    result_format="message",
                    stream=True,
                    **self.config.extra_params,
                    **kwargs
                )

            stream = await loop.run_in_executor(None, _sync_stream)

            for chunk in stream:
                if chunk.status_code == 200:
                    if chunk.output and chunk.output.choices:
                        content = chunk.output.choices[0].message.content
                        if content:
                            yield content
                else:
                    logger.warning(f"流式生成错误: {chunk.message}")

        except Exception as e:
            logger.error(f"通义千问流式生成失败: {e}")
            raise

    def _mock_generate(self, messages: List[LLMMessage]) -> LLMResponse:
        """模拟生成"""
        user_message = ""
        for msg in reversed(messages):
            if msg.role == "user":
                user_message = msg.content
                break

        mock_content = f"[通义千问模拟响应] 收到消息: {user_message[:50]}..."

        return LLMResponse(
            content=mock_content,
            model=self.config.model,
            provider=self.provider_type,
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            finish_reason="stop",
        )


# 注册Provider
from .factory import register_provider
register_provider(ProviderType.QWEN, QwenProvider)
