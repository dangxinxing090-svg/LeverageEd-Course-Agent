"""
FastAPI 应用入口

整合所有中间件和路由
"""

# 加载环境变量（必须在其他导入之前）
from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.api.v1.middleware.auth import jwt_auth_middleware
from app.api.v1.middleware.rate_limiter import rate_limit_middleware
from app.api.v1.middleware.logging import RequestLoggingMiddleware
from app.api.v1 import api_router

settings = get_settings()


class _JWTMiddleware(BaseHTTPMiddleware):
    """JWT认证中间件包装器"""
    async def dispatch(self, request: Request, call_next) -> Response:
        return await jwt_auth_middleware(request, call_next)


class _RateLimitMiddleware(BaseHTTPMiddleware):
    """限流中间件包装器"""
    async def dispatch(self, request: Request, call_next) -> Response:
        return await rate_limit_middleware(request, call_next)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    print(f"启动 {settings.APP_NAME} v{settings.APP_VERSION}")
    yield
    # 关闭时
    print("应用关闭")


# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI智能教育课程平台 API",
    lifespan=lifespan,
)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求日志中间件（最外层，最后执行）
app.add_middleware(RequestLoggingMiddleware, service_name="api")

# 限流中间件
app.add_middleware(_RateLimitMiddleware)

# JWT认证中间件
app.add_middleware(_JWTMiddleware)


# 注册API路由
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    """根路径 - 统一响应格式"""
    return {
        "code": 0,
        "message": "success",
        "data": {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "running"
        },
        "meta": {
            "timestamp": __import__('time').time(),
            "version": settings.APP_VERSION
        }
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "code": 0,
        "message": "success",
        "data": {"status": "healthy"},
        "meta": {
            "timestamp": __import__('time').time(),
            "version": settings.APP_VERSION
        }
    }
