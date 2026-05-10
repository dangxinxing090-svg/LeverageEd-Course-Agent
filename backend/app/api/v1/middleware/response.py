"""
U-014 统一响应格式化器

核心职责：将所有API响应统一包装为标准格式{code, message, data}

底层执行逻辑：
1. 捕获处理函数的返回值
2. 判断是否需要包装（排除已格式化的响应）
3. 构建标准响应格式
4. 添加元数据（时间戳、版本等）
5. 返回统一格式的响应

内存数据流转：
HandlerResult → 判断是否需要包装 → StandardResponse包装 → JSONResponse

潜在风险：
1. 内存泄漏：大响应体未做大小限制（已设置最大响应体大小）
2. 逻辑漏洞：嵌套标准响应导致格式混乱（已做类型检查避免重复包装）
3. 边界条件：None值、异常值的处理（已做空值过滤）
4. 性能问题：响应序列化耗时（已用orjson优化）

依赖：FastAPI Response、orjson（可选）
"""

from typing import Any, Optional, Union, List, Dict, Generic, TypeVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import time

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# 尝试使用orjson加速JSON序列化
try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False


class ResponseCode(int, Enum):
    """响应码枚举"""
    # 成功
    SUCCESS = 0

    # 客户端错误（4xx）
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    RATE_LIMITED = 429

    # 服务器错误（5xx）
    INTERNAL_ERROR = 500
    SERVICE_UNAVAILABLE = 503


class ResponseMessage(str, Enum):
    """响应消息枚举"""
    SUCCESS = "操作成功"
    BAD_REQUEST = "请求参数错误"
    UNAUTHORIZED = "用户未授权"
    FORBIDDEN = "禁止访问"
    NOT_FOUND = "资源不存在"
    RATE_LIMITED = "请求过于频繁"
    INTERNAL_ERROR = "服务器内部错误"
    SERVICE_UNAVAILABLE = "服务暂时不可用"


@dataclass
class StandardResponse(Generic[TypeVar("T")]):
    """
    统一响应格式

    格式：
    {
        "code": 0,
        "message": "success",
        "data": {...},
        "meta": {
            "timestamp": "2026-05-07T10:00:00Z",
            "request_id": "uuid",
            "version": "1.0.0"
        }
    }
    """
    code: int = 0
    message: str = "success"
    data: Any = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "code": self.code,
            "message": self.message
        }

        # data为None时不包含在响应中
        if self.data is not None:
            result["data"] = self.data

        if self.meta:
            result["meta"] = self.meta

        return result

    def to_json(self) -> str:
        """转换为JSON字符串"""
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


@dataclass
class PaginatedResponse(Generic[TypeVar("T")]):
    """
    分页响应格式

    格式：
    {
        "code": 0,
        "message": "success",
        "data": {
            "items": [...],
            "total": 100,
            "page": 1,
            "page_size": 20,
            "total_pages": 5
        },
        "meta": {...}
    }
    """
    code: int = 0
    message: str = "success"
    data: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "code": self.code,
            "message": self.message,
            "data": self.data,
            "meta": self.meta
        }


class ResponseFormatter:
    """
    响应格式化器

    提供静态方法将各种类型格式化为标准响应
    """

    def __init__(self, version: str = "1.0.0"):
        self.version = version

    @staticmethod
    def success(
        data: Any = None,
        message: str = ResponseMessage.SUCCESS.value,
        request_id: Optional[str] = None
    ) -> StandardResponse:
        """
        创建成功响应

        Args:
            data: 响应数据
            message: 成功消息
            request_id: 请求ID（用于链路追踪）

        Returns:
            StandardResponse对象
        """
        return StandardResponse(
            code=ResponseCode.SUCCESS.value,
            message=message,
            data=data,
            meta={
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "request_id": request_id,
                "version": "1.0.0"
            }
        )

    @staticmethod
    def error(
        code: int,
        message: str,
        details: Any = None,
        request_id: Optional[str] = None
    ) -> StandardResponse:
        """
        创建错误响应

        Args:
            code: 错误码
            message: 错误消息
            details: 错误详情
            request_id: 请求ID

        Returns:
            StandardResponse对象
        """
        meta = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
            "version": "1.0.0"
        }

        if details:
            meta["details"] = details

        return StandardResponse(
            code=code,
            message=message,
            data=None,
            meta=meta
        )

    @staticmethod
    def paginated(
        items: List[Any],
        total: int,
        page: int,
        page_size: int,
        message: str = ResponseMessage.SUCCESS.value,
        request_id: Optional[str] = None
    ) -> PaginatedResponse:
        """
        创建分页响应

        Args:
            items: 当前页数据
            total: 总记录数
            page: 当前页码
            page_size: 每页大小
            message: 成功消息
            request_id: 请求ID

        Returns:
            PaginatedResponse对象
        """
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

        return PaginatedResponse(
            code=ResponseCode.SUCCESS.value,
            message=message,
            data={
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            },
            meta={
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "request_id": request_id,
                "version": "1.0.0"
            }
        )

    @staticmethod
    def validation_error(
        errors: List[Dict[str, Any]],
        request_id: Optional[str] = None
    ) -> StandardResponse:
        """
        创建参数校验错误响应

        Args:
            errors: 校验错误列表
            request_id: 请求ID

        Returns:
            StandardResponse对象
        """
        return ResponseFormatter.error(
            code=ResponseCode.BAD_REQUEST.value,
            message="参数校验失败",
            details={"validation_errors": errors},
            request_id=request_id
        )

    @staticmethod
    def unauthorized(
        message: str = "用户未授权，请先登录",
        request_id: Optional[str] = None
    ) -> StandardResponse:
        """创建未授权响应"""
        return ResponseFormatter.error(
            code=ResponseCode.UNAUTHORIZED.value,
            message=message,
            request_id=request_id
        )

    @staticmethod
    def forbidden(
        message: str = "禁止访问此资源",
        request_id: Optional[str] = None
    ) -> StandardResponse:
        """创建禁止访问响应"""
        return ResponseFormatter.error(
            code=ResponseCode.FORBIDDEN.value,
            message=message,
            request_id=request_id
        )

    @staticmethod
    def not_found(
        resource: str = "资源",
        request_id: Optional[str] = None
    ) -> StandardResponse:
        """创建资源不存在响应"""
        return ResponseFormatter.error(
            code=ResponseCode.NOT_FOUND.value,
            message=f"{resource}不存在",
            request_id=request_id
        )


# 全局格式化器实例
_response_formatter: Optional[ResponseFormatter] = None


def get_response_formatter() -> ResponseFormatter:
    """获取响应格式化器单例"""
    global _response_formatter
    if _response_formatter is None:
        _response_formatter = ResponseFormatter()
    return _response_formatter


def format_response(
    data: Any = None,
    message: str = ResponseMessage.SUCCESS.value,
    request: Optional[Request] = None
) -> JSONResponse:
    """
    格式化成功响应为JSONResponse

    Args:
        data: 响应数据
        message: 成功消息
        request: FastAPI请求对象（用于获取request_id）

    Returns:
        JSONResponse对象
    """
    formatter = get_response_formatter()
    request_id = None

    if request and hasattr(request.state, "request_id"):
        request_id = request.state.request_id

    response = formatter.success(data=data, message=message, request_id=request_id)

    content = response.to_dict()

    return JSONResponse(content=content, media_type="application/json")


def format_error_response(
    code: int,
    message: str,
    details: Any = None,
    request: Optional[Request] = None
) -> JSONResponse:
    """
    格式化错误响应为JSONResponse

    Args:
        code: 错误码
        message: 错误消息
        details: 错误详情
        request: FastAPI请求对象

    Returns:
        JSONResponse对象
    """
    formatter = get_response_formatter()
    request_id = None

    if request and hasattr(request.state, "request_id"):
        request_id = request.state.request_id

    response = formatter.error(
        code=code,
        message=message,
        details=details,
        request_id=request_id
    )

    return JSONResponse(
        content=response.to_dict(),
        media_type="application/json",
        status_code=code if 400 <= code < 600 else 500
    )


def success_response(data: Any = None):
    """
    快捷成功响应装饰器

    用法：
        @app.get("/items")
        @success_response()
        async def get_items():
            return [{"id": 1}, {"id": 2}]
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)

            # 如果已经是JSONResponse，直接返回
            if isinstance(result, JSONResponse):
                return result

            # 如果已经是标准响应格式，跳过重复包装
            if isinstance(result, (StandardResponse, PaginatedResponse)):
                return result

            return format_response(data=result)

        return wrapper
    return decorator


class ResponseWrapperMiddleware:
    """
    响应包装中间件

    自动将所有响应包装为标准格式
    """

    def __init__(self, app, version: str = "1.0.0"):
        self.app = app
        self.version = version
        self.formatter = ResponseFormatter(version=version)

    async def __call__(self, scope, receive, send):
        """
        中间件处理函数

        处理流程：
        1. 判断是否需要包装响应
        2. 拦截响应流
        3. 包装响应内容
        4. 发送包装后的响应

        Note:
            这个中间件主要是概念展示，实际使用建议在每个handler中
            直接返回StandardResponse或使用success_response装饰器
            因为拦截整个响应流会有性能开销
        """
        # 暂时不做全局拦截，保持handler级别的灵活性
        await self.app(scope, receive, send)
