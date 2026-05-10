"""
API v1 中间件模块

导出所有中间件组件
"""

# U-010 JWT认证中间件
from .auth import (
    jwt_auth_middleware,
    get_current_user,
    require_subscription,
    UserInfo,
    JWTValidator,
    get_jwt_validator,
)

# U-011 请求路由中间件
from .router import (
    route_request,
    router_config,
    get_path_params,
    get_handler,
    RouteHandler,
    RouterConfig,
)

# U-012 限流熔断器
from .rate_limiter import (
    rate_limit_middleware,
    get_rate_limiter,
    get_circuit_breaker,
    RateLimiter,
    CircuitBreaker,
    RateLimitResult,
    CircuitBreakerResult,
    CircuitState,
)

# U-013 请求日志中间件
from .logging import (
    RequestLoggingMiddleware,
    get_request_logger,
    get_log_buffer,
    get_async_writer,
    RequestLogRecord,
    LogBuffer,
    ConsoleLogWriter,
    FileLogWriter,
)

# U-014 统一响应格式化器
from .response import (
    format_response,
    format_error_response,
    success_response,
    get_response_formatter,
    ResponseFormatter,
    StandardResponse,
    PaginatedResponse,
    ResponseCode,
    ResponseMessage,
)

__all__ = [
    # Auth
    "jwt_auth_middleware",
    "get_current_user",
    "require_subscription",
    "UserInfo",
    "JWTValidator",
    "get_jwt_validator",
    # Router
    "route_request",
    "router_config",
    "get_path_params",
    "get_handler",
    "RouteHandler",
    "RouterConfig",
    # Rate Limiter
    "rate_limit_middleware",
    "get_rate_limiter",
    "get_circuit_breaker",
    "RateLimiter",
    "CircuitBreaker",
    "RateLimitResult",
    "CircuitBreakerResult",
    "CircuitState",
    # Logging
    "RequestLoggingMiddleware",
    "get_request_logger",
    "get_log_buffer",
    "get_async_writer",
    "RequestLogRecord",
    "LogBuffer",
    "ConsoleLogWriter",
    "FileLogWriter",
    # Response
    "format_response",
    "format_error_response",
    "success_response",
    "get_response_formatter",
    "ResponseFormatter",
    "StandardResponse",
    "PaginatedResponse",
    "ResponseCode",
    "ResponseMessage",
]
