"""
后端项目配置文件
定义全局配置项
"""

import os
from typing import Optional
from pydantic import BaseModel
from functools import lru_cache


class Settings(BaseModel):
    """应用全局配置"""
    # 应用信息
    APP_NAME: str = "AI智能教育课程平台"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # 服务配置
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # 数据库配置
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/education")

    # Redis配置
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # JWT配置
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24小时

    # API限流配置
    RATE_LIMIT_PER_MINUTE: int = 60  # 每分钟最大请求数
    RATE_LIMIT_PER_HOUR: int = 1000  # 每小时最大请求数

    # CORS配置
    CORS_ORIGINS: list[str] = ["*"]

    # 日志配置
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


@lru_cache()
def get_settings() -> Settings:
    """获取全局配置单例"""
    return Settings()
