"""
API v1 路由模块

统一导出所有路由
"""

from fastapi import APIRouter

from .endpoints import topics, learning, users

# 创建主路由
api_router = APIRouter()

# 注册各模块路由
api_router.include_router(topics.router, prefix="/topics", tags=["Topics"])
api_router.include_router(learning.router, prefix="/learning", tags=["Learning"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])

# 兼容前端直接调用的路径（不带 /learning 前缀）
# 前端 api.ts 直接请求 /api/v1/knowledge/...、/api/v1/qa/... 等路径
api_router.include_router(learning.router, prefix="", tags=["Learning-Direct"])

__all__ = ["api_router"]
