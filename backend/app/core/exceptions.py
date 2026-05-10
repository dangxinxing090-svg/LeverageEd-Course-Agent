"""
后端核心异常定义
定义业务异常和HTTP异常
"""

from typing import Any, Optional
from fastapi import HTTPException, status


class BaseAPIException(Exception):
    """基础API异常"""

    def __init__(
        self,
        message: str,
        code: int = 400,
        details: Optional[Any] = None
    ):
        self.message = message
        self.code = code
        self.details = details
        super().__init__(self.message)


class ValidationException(BaseAPIException):
    """参数校验异常"""
    def __init__(self, message: str = "参数校验失败", details: Optional[Any] = None):
        super().__init__(message, code=400, details=details)


class UnauthorizedException(BaseAPIException):
    """未授权异常"""
    def __init__(self, message: str = "未授权访问", details: Optional[Any] = None):
        super().__init__(message, code=401, details=details)


class ForbiddenException(BaseAPIException):
    """禁止访问异常"""
    def __init__(self, message: str = "禁止访问", details: Optional[Any] = None):
        super().__init__(message, code=403, details=details)


class NotFoundException(BaseAPIException):
    """资源不存在异常"""
    def __init__(self, message: str = "资源不存在", details: Optional[Any] = None):
        super().__init__(message, code=404, details=details)


class RateLimitException(BaseAPIException):
    """限流异常"""
    def __init__(self, message: str = "请求过于频繁，请稍后重试", retry_after: int = 60):
        super().__init__(message, code=429, details={"retry_after": retry_after})


class InternalServerException(BaseAPIException):
    """服务器内部异常"""
    def __init__(self, message: str = "服务器内部错误", details: Optional[Any] = None):
        super().__init__(message, code=500, details=details)


def api_exception_to_http_exception(exc: BaseAPIException) -> HTTPException:
    """将业务异常转换为HTTP异常"""
    return HTTPException(
        status_code=exc.code,
        detail={
            "code": exc.code,
            "message": exc.message,
            "details": exc.details
        }
    )
