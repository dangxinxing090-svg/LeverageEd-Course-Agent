"""
LLM Provider 工厂

负责创建和管理Provider实例
"""

import logging
from typing import Dict, List, Optional, Type

from .base import LLMProvider, ProviderConfig, ProviderType
from .config import get_llm_config

logger = logging.getLogger(__name__)

# Provider类注册表
_provider_registry: Dict[ProviderType, Type[LLMProvider]] = {}

# Provider实例缓存
_provider_instances: Dict[ProviderType, LLMProvider] = {}


def register_provider(provider_type: ProviderType, provider_class: Type[LLMProvider]) -> None:
    """
    注册Provider类

    Args:
        provider_type: Provider类型
        provider_class: Provider类
    """
    _provider_registry[provider_type] = provider_class
    logger.debug(f"已注册Provider: {provider_type.value}")


def create_provider(
    provider_type: ProviderType,
    config: Optional[ProviderConfig] = None
) -> Optional[LLMProvider]:
    """
    创建Provider实例

    Args:
        provider_type: Provider类型
        config: Provider配置（为None时从配置管理器加载）

    Returns:
        Provider实例或None
    """
    # 获取配置
    if config is None:
        config = get_llm_config().get_config(provider_type)

    if config is None:
        logger.warning(f"未找到 {provider_type.value} 的配置")
        return None

    # 获取Provider类
    provider_class = _provider_registry.get(provider_type)
    if provider_class is None:
        logger.error(f"未注册Provider类: {provider_type.value}")
        return None

    # 创建实例
    try:
        provider = provider_class(config)
        logger.info(f"已创建 {provider_type.value} Provider实例")
        return provider
    except Exception as e:
        logger.error(f"创建 {provider_type.value} Provider失败: {e}")
        return None


def get_provider(provider_type: Optional[ProviderType] = None) -> Optional[LLMProvider]:
    """
    获取Provider实例（带缓存）

    Args:
        provider_type: Provider类型（为None时使用默认Provider）

    Returns:
        Provider实例或None
    """
    # 确定Provider类型
    if provider_type is None:
        provider_type = get_llm_config().get_default_provider()
        if provider_type is None:
            logger.error("没有可用的Provider")
            return None

    # 检查缓存
    if provider_type in _provider_instances:
        return _provider_instances[provider_type]

    # 创建新实例
    provider = create_provider(provider_type)
    if provider:
        _provider_instances[provider_type] = provider

    return provider


def clear_provider_cache(provider_type: Optional[ProviderType] = None) -> None:
    """
    清除Provider缓存

    Args:
        provider_type: Provider类型（为None时清除所有缓存）
    """
    global _provider_instances

    if provider_type is None:
        _provider_instances.clear()
        logger.info("已清除所有Provider缓存")
    elif provider_type in _provider_instances:
        del _provider_instances[provider_type]
        logger.info(f"已清除 {provider_type.value} Provider缓存")


def list_available_providers() -> List[ProviderType]:
    """
    列出所有可用的Provider

    Returns:
        ProviderType列表
    """
    return get_llm_config().get_available_providers()


def list_registered_providers() -> List[ProviderType]:
    """
    列出所有已注册的Provider类型

    Returns:
        ProviderType列表
    """
    return list(_provider_registry.keys())


class ProviderFactory:
    """
    Provider工厂类

    提供静态方法创建和管理Provider
    """

    @staticmethod
    def register(provider_type: ProviderType, provider_class: Type[LLMProvider]) -> None:
        """注册Provider"""
        register_provider(provider_type, provider_class)

    @staticmethod
    def create(
        provider_type: ProviderType,
        config: Optional[ProviderConfig] = None
    ) -> Optional[LLMProvider]:
        """创建Provider实例"""
        return create_provider(provider_type, config)

    @staticmethod
    def get(provider_type: Optional[ProviderType] = None) -> Optional[LLMProvider]:
        """获取Provider实例（带缓存）"""
        return get_provider(provider_type)

    @staticmethod
    def get_default() -> Optional[LLMProvider]:
        """获取默认Provider"""
        return get_provider(None)

    @staticmethod
    def clear_cache(provider_type: Optional[ProviderType] = None) -> None:
        """清除缓存"""
        clear_provider_cache(provider_type)

    @staticmethod
    def available() -> List[ProviderType]:
        """获取可用Provider列表"""
        return list_available_providers()

    @staticmethod
    def registered() -> List[ProviderType]:
        """获取已注册Provider列表"""
        return list_registered_providers()
