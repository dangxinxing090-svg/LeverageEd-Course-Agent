"""
LLM Provider 配置管理

负责加载和管理Provider配置
支持环境变量、配置文件等多种配置方式
"""

import os
import json
import logging
from typing import Any, Dict, Optional
from dataclasses import dataclass, field

from .base import ProviderConfig, ProviderType

logger = logging.getLogger(__name__)


# 默认模型配置
DEFAULT_MODELS = {
    ProviderType.OPENAI: "gpt-3.5-turbo",
    ProviderType.ZHIPU: "glm-4",
    ProviderType.KIMI: "moonshot-v1-8k",
    ProviderType.QWEN: "qwen-turbo",
    ProviderType.DOUBAO: "doubao-pro-4k",
    ProviderType.DEEPSEEK: "deepseek-v4-flash",
}

# Provider API基础URL
DEFAULT_API_BASES = {
    ProviderType.OPENAI: "https://api.openai.com/v1",
    ProviderType.ZHIPU: "https://open.bigmodel.cn/api/paas/v4",
    ProviderType.KIMI: "https://api.moonshot.cn/v1",
    ProviderType.QWEN: "https://dashscope.aliyuncs.com/api/v1",
    ProviderType.DOUBAO: "https://ark.cn-beijing.volces.com/api/v3",
    ProviderType.DEEPSEEK: "https://api.deepseek.com/v1",
}

# 环境变量映射
ENV_VAR_MAPPING = {
    ProviderType.OPENAI: {
        "api_key": "OPENAI_API_KEY",
        "api_base": "OPENAI_API_BASE",
        "model": "OPENAI_MODEL",
    },
    ProviderType.ZHIPU: {
        "api_key": "ZHIPU_API_KEY",
        "api_base": "ZHIPU_API_BASE",
        "model": "ZHIPU_MODEL",
    },
    ProviderType.KIMI: {
        "api_key": "KIMI_API_KEY",
        "api_base": "KIMI_API_BASE",
        "model": "KIMI_MODEL",
    },
    ProviderType.QWEN: {
        "api_key": "QWEN_API_KEY",
        "api_base": "QWEN_API_BASE",
        "model": "QWEN_MODEL",
    },
    ProviderType.DOUBAO: {
        "api_key": "DOUBAO_API_KEY",
        "api_base": "DOUBAO_API_BASE",
        "model": "DOUBAO_MODEL",
    },
    ProviderType.DEEPSEEK: {
        "api_key": "DEEPSEEK_API_KEY",
        "api_base": "DEEPSEEK_API_BASE",
        "model": "DEEPSEEK_MODEL",
    },
}


@dataclass
class LLMGlobalConfig:
    """
    LLM全局配置

    包含默认Provider和全局参数
    """
    default_provider: ProviderType = ProviderType.OPENAI
    fallback_provider: Optional[ProviderType] = None
    request_timeout: int = 60
    max_retries: int = 3
    retry_delay: float = 1.0
    enable_caching: bool = True
    cache_ttl: int = 300  # 缓存时间（秒）


class LLMConfigManager:
    """
    LLM配置管理器

    单例模式管理所有Provider配置
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        # 检查是否需要强制重新加载
        import os
        if os.environ.get('_LLM_CONFIG_FORCE_RELOAD') == '1':
            cls._instance = None
            cls._initialized = False
            os.environ['_LLM_CONFIG_FORCE_RELOAD'] = '0'
        
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if LLMConfigManager._initialized:
            return

        self._configs: Dict[ProviderType, ProviderConfig] = {}
        self._global_config = LLMGlobalConfig()

        # 优先从 JSON 配置文件加载
        import os
        config_dir = os.path.dirname(os.path.abspath(__file__))
        json_config_path = os.path.join(config_dir, 'llm_config.json')
        if os.path.exists(json_config_path):
            self.load_from_json_file(json_config_path)
        else:
            # 备选：从环境变量加载
            self._load_all_configs()

        LLMConfigManager._initialized = True

    def _load_all_configs(self) -> None:
        """加载所有Provider配置"""
        for provider_type in ProviderType:
            config = self._load_provider_config(provider_type)
            if config:
                self._configs[provider_type] = config
                logger.info(f"已加载 {provider_type.value} Provider配置")

    def reload_configs(self) -> None:
        """重新加载所有Provider配置"""
        self._configs.clear()
        self._load_all_configs()
        logger.info("已重新加载所有Provider配置")

    def _load_provider_config(self, provider_type: ProviderType) -> Optional[ProviderConfig]:
        """
        从环境变量加载Provider配置

        Args:
            provider_type: Provider类型

        Returns:
            ProviderConfig对象或None
        """
        env_mapping = ENV_VAR_MAPPING.get(provider_type, {})

        # 获取API Key（必需）
        api_key = os.getenv(env_mapping.get("api_key", ""))
        if not api_key:
            logger.debug(f"未找到 {provider_type.value} 的API Key配置")
            return None

        # 获取其他配置
        api_base = os.getenv(env_mapping.get("api_base", ""))
        if not api_base:
            api_base = DEFAULT_API_BASES.get(provider_type)

        model = os.getenv(env_mapping.get("model", ""))
        if not model:
            model = DEFAULT_MODELS.get(provider_type, "default")

        return ProviderConfig(
            provider_type=provider_type,
            api_key=api_key,
            api_base=api_base,
            model=model,
        )

    def get_config(self, provider_type: ProviderType) -> Optional[ProviderConfig]:
        """
        获取Provider配置

        Args:
            provider_type: Provider类型

        Returns:
            ProviderConfig对象或None
        """
        return self._configs.get(provider_type)

    def set_config(self, provider_type: ProviderType, config: ProviderConfig) -> None:
        """
        设置Provider配置

        Args:
            provider_type: Provider类型
            config: Provider配置
        """
        self._configs[provider_type] = config

    def get_available_providers(self) -> list:
        """
        获取所有可用Provider列表

        Returns:
            ProviderType列表
        """
        return list(self._configs.keys())

    def get_global_config(self) -> LLMGlobalConfig:
        """
        获取全局配置

        Returns:
            LLMGlobalConfig对象
        """
        return self._global_config

    def set_global_config(self, config: LLMGlobalConfig) -> None:
        """
        设置全局配置

        Args:
            config: 全局配置
        """
        self._global_config = config

    def get_default_provider(self) -> Optional[ProviderType]:
        """
        获取默认Provider

        Returns:
            ProviderType或None
        """
        # 如果配置的默认Provider可用，使用它
        if self._global_config.default_provider in self._configs:
            return self._global_config.default_provider

        # 否则返回第一个可用的Provider
        if self._configs:
            return list(self._configs.keys())[0]

        return None

    def load_from_dict(self, config_dict: Dict[str, Any]) -> None:
        """
        从字典加载配置

        Args:
            config_dict: 配置字典
        """
        # 加载全局配置
        if "global" in config_dict:
            global_cfg = config_dict["global"]
            self._global_config = LLMGlobalConfig(
                default_provider=ProviderType(global_cfg.get("default_provider", "openai")),
                fallback_provider=ProviderType(global_cfg.get("fallback_provider")) if global_cfg.get("fallback_provider") else None,
                request_timeout=global_cfg.get("request_timeout", 60),
                max_retries=global_cfg.get("max_retries", 3),
                retry_delay=global_cfg.get("retry_delay", 1.0),
                enable_caching=global_cfg.get("enable_caching", True),
                cache_ttl=global_cfg.get("cache_ttl", 300),
            )

        # 加载Provider配置
        for provider_name, provider_cfg in config_dict.get("providers", {}).items():
            try:
                provider_type = ProviderType(provider_name)
                config = ProviderConfig(
                    provider_type=provider_type,
                    api_key=provider_cfg.get("api_key", ""),
                    api_base=provider_cfg.get("api_base"),
                    model=provider_cfg.get("model", DEFAULT_MODELS.get(provider_type, "default")),
                    temperature=provider_cfg.get("temperature", 0.7),
                    max_tokens=provider_cfg.get("max_tokens", 2048),
                    timeout=provider_cfg.get("timeout", 60),
                    max_retries=provider_cfg.get("max_retries", 3),
                    retry_delay=provider_cfg.get("retry_delay", 1.0),
                    extra_headers=provider_cfg.get("extra_headers"),
                    extra_params=provider_cfg.get("extra_params"),
                )
                self._configs[provider_type] = config
            except ValueError:
                logger.warning(f"未知的Provider类型: {provider_name}")

    def load_from_json_file(self, file_path: str) -> None:
        """
        从JSON文件加载配置

        Args:
            file_path: 配置文件路径
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)
            self.load_from_dict(config_dict)
            logger.info(f"已从 {file_path} 加载配置")
        except FileNotFoundError:
            logger.warning(f"配置文件不存在: {file_path}")
        except json.JSONDecodeError as e:
            logger.error(f"配置文件解析失败: {e}")

    def to_dict(self) -> Dict[str, Any]:
        """
        导出配置为字典

        Returns:
            配置字典
        """
        return {
            "global": {
                "default_provider": self._global_config.default_provider.value,
                "fallback_provider": self._global_config.fallback_provider.value if self._global_config.fallback_provider else None,
                "request_timeout": self._global_config.request_timeout,
                "max_retries": self._global_config.max_retries,
                "retry_delay": self._global_config.retry_delay,
                "enable_caching": self._global_config.enable_caching,
                "cache_ttl": self._global_config.cache_ttl,
            },
            "providers": {
                pt.value: {
                    "api_key": "***" if cfg.api_key else "",  # 隐藏真实API Key
                    "api_base": cfg.api_base,
                    "model": cfg.model,
                    "temperature": cfg.temperature,
                    "max_tokens": cfg.max_tokens,
                }
                for pt, cfg in self._configs.items()
            }
        }


# 全局配置管理器实例
_config_manager = None


def get_llm_config() -> LLMConfigManager:
    """
    获取LLM配置管理器实例

    Returns:
        LLMConfigManager单例
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = LLMConfigManager()
    return _config_manager


def load_provider_config(provider_type: ProviderType) -> Optional[ProviderConfig]:
    """
    加载指定Provider的配置

    Args:
        provider_type: Provider类型

    Returns:
        ProviderConfig对象或None
    """
    return get_llm_config().get_config(provider_type)
