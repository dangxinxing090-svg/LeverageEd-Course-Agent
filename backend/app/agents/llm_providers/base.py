"""
LLM Provider 基础接口定义

定义统一的LLM Provider抽象基类和数据模型
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, AsyncGenerator
from datetime import datetime, timezone
import uuid


class ProviderType(str, Enum):
    """Provider类型枚举"""
    OPENAI = "openai"
    ZHIPU = "zhipu"      # 智谱GLM
    KIMI = "kimi"        # Moonshot
    QWEN = "qwen"        # 阿里通义千问
    DOUBAO = "doubao"    # 字节豆包
    DEEPSEEK = "deepseek"  # DeepSeek


class ModelCapability(str, Enum):
    """模型能力枚举"""
    CHAT = "chat"                    # 对话能力
    COMPLETION = "completion"        # 文本补全
    FUNCTION_CALLING = "function_calling"  # 函数调用
    JSON_MODE = "json_mode"          # JSON输出
    STREAMING = "streaming"          # 流式输出
    VISION = "vision"                # 图像理解


@dataclass
class LLMMessage:
    """
    LLM消息

    统一的消息格式，适配不同模型的输入
    """
    role: str  # system/user/assistant/tool
    content: str
    name: Optional[str] = None  # 用于function calling
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "role": self.role,
            "content": self.content,
        }
        if self.name:
            data["name"] = self.name
        if self.tool_calls:
            data["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            data["tool_call_id"] = self.tool_call_id
        return data


@dataclass
class LLMResponse:
    """
    LLM响应

    统一的响应格式，屏蔽不同模型的差异
    """
    content: str  # 生成的文本内容
    model: str  # 使用的模型名称
    provider: ProviderType  # Provider类型
    usage: Dict[str, int] = field(default_factory=dict)  # token使用情况
    finish_reason: Optional[str] = None  # 结束原因
    generation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    raw_response: Optional[Any] = None  # 原始响应（调试用）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "model": self.model,
            "provider": self.provider.value,
            "usage": self.usage,
            "finish_reason": self.finish_reason,
            "generation_id": self.generation_id,
            "created_at": self.created_at,
        }


@dataclass
class ProviderConfig:
    """
    Provider配置

    统一的配置格式
    """
    provider_type: ProviderType
    api_key: str
    api_base: Optional[str] = None
    model: str = "default"
    temperature: float = 0.7
    max_tokens: int = 2048
    timeout: int = 60
    max_retries: int = 3
    retry_delay: float = 1.0
    extra_headers: Optional[Dict[str, str]] = None
    extra_params: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.extra_headers is None:
            self.extra_headers = {}
        if self.extra_params is None:
            self.extra_params = {}


class LLMProvider(ABC):
    """
    LLM Provider抽象基类

    所有Provider必须实现此接口，提供统一的调用方式
    """

    def __init__(self, config: ProviderConfig):
        """
        初始化Provider

        Args:
            config: Provider配置
        """
        self.config = config
        self._client = None
        self._initialized = False

    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        """返回Provider类型"""
        pass

    @property
    @abstractmethod
    def supported_capabilities(self) -> List[ModelCapability]:
        """返回支持的模型能力列表"""
        pass

    @abstractmethod
    async def initialize(self) -> None:
        """
        初始化Provider客户端

        异步初始化，建立连接等
        """
        pass

    @abstractmethod
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
            temperature: 温度（覆盖配置）
            max_tokens: 最大token数（覆盖配置）
            **kwargs: 额外参数

        Returns:
            LLMResponse对象
        """
        pass

    @abstractmethod
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
        pass

    async def agenerate(self, prompts: List[str], **kwargs) -> "LLMGenerationResult":
        """
        兼容LangChain风格的批量生成接口

        Args:
            prompts: Prompt列表
            **kwargs: 额外参数

        Returns:
            LLMGenerationResult对象
        """
        # 将prompts转换为messages格式
        messages = [LLMMessage(role="user", content=prompt) for prompt in prompts]

        # 调用统一的generate方法
        responses = []
        for msg in messages:
            response = await self.generate([msg], **kwargs)
            responses.append(response)

        # 转换为LLMGenerationResult格式
        generations = []
        for resp in responses:
            gen = LLMGeneration(
                text=resp.content,
                generation_info={
                    "finish_reason": resp.finish_reason,
                    "model": resp.model,
                }
            )
            generations.append([gen])

        llm_output = {
            "token_usage": sum(r.usage.get("total_tokens", 0) for r in responses),
            "model_name": self.config.model,
        }

        return LLMGenerationResult(
            generations=generations,
            llm_output=llm_output,
        )

    def supports_capability(self, capability: ModelCapability) -> bool:
        """
        检查是否支持某能力

        Args:
            capability: 能力类型

        Returns:
            是否支持
        """
        return capability in self.supported_capabilities

    def _build_messages(self, prompt: str, system_prompt: Optional[str] = None) -> List[LLMMessage]:
        """
        构建消息列表

        Args:
            prompt: 用户输入
            system_prompt: 系统提示

        Returns:
            消息列表
        """
        messages = []
        if system_prompt:
            messages.append(LLMMessage(role="system", content=system_prompt))
        messages.append(LLMMessage(role="user", content=prompt))
        return messages

    def _get_generation_params(
        self,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        获取生成参数

        Args:
            temperature: 温度
            max_tokens: 最大token数

        Returns:
            参数字典
        """
        return {
            "temperature": temperature if temperature is not None else self.config.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.config.max_tokens,
        }


@dataclass
class LLMGeneration:
    """单条生成结果（兼容LangChain格式）"""
    text: str
    generation_info: Optional[Dict[str, Any]] = None


@dataclass
class LLMGenerationResult:
    """批量生成结果（兼容LangChain格式）"""
    generations: List[List[LLMGeneration]]
    llm_output: Optional[Dict[str, Any]] = None
