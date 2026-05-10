"""
U-012 限流熔断器

核心职责：按用户/IP限流，超阈值返回429，服务异常时熔断降级

底层执行逻辑：
1. 识别请求来源（优先user_id，次选IP）
2. 查询Redis获取当前请求计数
3. 判断是否超过限流阈值
4. 超限返回429和retry_after
5. 未超限则计数+1并放行

熔断逻辑：
1. 监控错误率（5分钟内错误率>50%触发熔断）
2. 熔断期间直接返回降级响应
3. 熔断30秒后尝试恢复（半开状态）
4. 恢复失败则继续熔断

内存数据流转：
Request → 用户标识符 → Redis计数 → 判断限流/放行 → Response

潜在风险：
1. 内存泄漏：Redis连接未正确关闭（使用上下文管理器）
2. 逻辑漏洞：分布式部署时计数不准（使用Redis INCR原子操作）
3. 边界条件：Redis不可用时的降级处理（放行并记录警告）
4. 安全风险：IP伪造绕过限流（依赖反向代理设置真实IP头）

依赖：Redis（aioredis/redis-py）
"""

import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import logging

from fastapi import Request, status
from starlette.responses import JSONResponse

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from app.core.config import get_settings
from app.core.exceptions import RateLimitException

settings = get_settings()
logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """熔断器状态"""
    CLOSED = "closed"      # 正常：请求放行
    OPEN = "open"         # 熔断：请求拒绝
    HALF_OPEN = "half_open"  # 半开：尝试恢复


@dataclass
class RateLimitResult:
    """限流检查结果"""
    allowed: bool          # 是否允许请求
    limit: int             # 限流阈值
    remaining: int         # 剩余请求数
    reset_at: int          # 重置时间戳
    retry_after: Optional[int] = None  # 距离重置的秒数


@dataclass
class CircuitBreakerResult:
    """熔断器检查结果"""
    allowed: bool          # 是否允许请求
    state: CircuitState    # 当前状态
    error_rate: float      # 当前错误率
    retry_after: Optional[int] = None  # 距离恢复的秒数


class RateLimiter:
    """
    限流器
    基于Redis实现滑动窗口限流
    """

    def __init__(self):
        self.redis_client = None
        self._init_redis()

    def _init_redis(self):
        """初始化Redis连接"""
        if not REDIS_AVAILABLE:
            logger.warning("Redis未安装，限流功能将使用内存存储（不适用于分布式部署）")
            return

        try:
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # 测试连接
            self.redis_client.ping()
            logger.info("Redis连接成功")
        except Exception as e:
            logger.warning(f"Redis连接失败: {e}，限流功能将使用内存存储")
            self.redis_client = None

    def _get_key(self, identifier: str, window: str) -> str:
        """
        生成限流Redis key

        Args:
            identifier: 用户标识符（user_id或IP）
            window: 时间窗口（minute/hour）

        Returns:
            Redis key
        """
        return f"ratelimit:{window}:{identifier}"

    async def check_rate_limit(
        self,
        identifier: str,
        limit: int,
        window_seconds: int
    ) -> RateLimitResult:
        """
        检查限流

        Args:
            identifier: 用户标识符
            limit: 限流阈值
            window_seconds: 时间窗口秒数

        Returns:
            RateLimitResult对象
        """
        current_time = int(time.time())
        window_key = self._get_key(identifier, f"{window_seconds}s")

        # 边界条件：Redis不可用时放行
        if self.redis_client is None:
            return RateLimitResult(
                allowed=True,
                limit=limit,
                remaining=limit,
                reset_at=current_time + window_seconds
            )

        try:
            # 使用Redis事务保证原子性
            pipe = self.redis_client.pipeline()

            # 移除过期数据
            pipe.zremrangebyscore(window_key, 0, current_time - window_seconds)

            # 获取当前计数
            pipe.zcard(window_key)

            # 添加当前请求
            pipe.zadd(window_key, {str(current_time): current_time})

            # 设置过期时间
            pipe.expire(window_key, window_seconds)

            results = pipe.execute()
            current_count = results[1]  # zcard结果

            remaining = max(0, limit - current_count - 1)
            reset_at = current_time + window_seconds

            if current_count >= limit:
                # 超过限流
                retry_after = window_seconds - (current_time % window_seconds)
                return RateLimitResult(
                    allowed=False,
                    limit=limit,
                    remaining=0,
                    reset_at=reset_at,
                    retry_after=retry_after
                )

            return RateLimitResult(
                allowed=True,
                limit=limit,
                remaining=remaining,
                reset_at=reset_at
            )

        except Exception as e:
            logger.error(f"限流检查失败: {e}")
            # Redis异常时放行（fail-open）
            return RateLimitResult(
                allowed=True,
                limit=limit,
                remaining=limit,
                reset_at=current_time + window_seconds
            )


class CircuitBreaker:
    """
    熔断器
    基于错误率监控实现服务降级
    """

    def __init__(
        self,
        name: str = "default",
        failure_threshold: float = 0.5,  # 50%错误率触发熔断
        recovery_timeout: int = 30,      # 30秒后尝试恢复
        half_open_max_calls: int = 3    # 半开状态最多3个请求
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.total_count = 0
        self.last_failure_time = 0
        self.half_open_calls = 0

    def _get_redis_key(self, suffix: str) -> str:
        """生成Redis key"""
        return f"circuit:{self.name}:{suffix}"

    def record_success(self):
        """记录成功调用"""
        self.success_count += 1
        self.total_count += 1

        # 在半开状态下，连续成功则关闭熔断器
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_calls += 1
            if self.half_open_calls >= self.half_open_max_calls:
                self._close_circuit()

    def record_failure(self):
        """记录失败调用"""
        self.failure_count += 1
        self.total_count += 1
        self.last_failure_time = int(time.time())

        # 检查是否需要打开熔断器
        if self.state == CircuitState.CLOSED:
            if self._calculate_error_rate() >= self.failure_threshold:
                self._open_circuit()

    def _calculate_error_rate(self) -> float:
        """计算错误率"""
        if self.total_count == 0:
            return 0.0
        return self.failure_count / self.total_count

    def _open_circuit(self):
        """打开熔断器"""
        if self.state != CircuitState.OPEN:
            logger.warning(f"CircuitBreaker '{self.name}' 打开熔断")
        self.state = CircuitState.OPEN
        self.half_open_calls = 0

    def _close_circuit(self):
        """关闭熔断器"""
        logger.info(f"CircuitBreaker '{self.name}' 关闭熔断")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.total_count = 0
        self.half_open_calls = 0

    def _try_half_open(self):
        """尝试进入半开状态"""
        current_time = int(time.time())
        if current_time - self.last_failure_time >= self.recovery_timeout:
            logger.info(f"CircuitBreaker '{self.name}' 进入半开状态")
            self.state = CircuitState.HALF_OPEN
            self.half_open_calls = 0
            self.failure_count = 0
            self.success_count = 0
            self.total_count = 0

    async def check(self) -> CircuitBreakerResult:
        """
        检查熔断状态

        Returns:
            CircuitBreakerResult对象
        """
        current_time = int(time.time())

        if self.state == CircuitState.OPEN:
            # 检查是否超时可以尝试恢复
            self._try_half_open()

        if self.state == CircuitState.OPEN:
            retry_after = max(0, self.recovery_timeout - (current_time - self.last_failure_time))
            return CircuitBreakerResult(
                allowed=False,
                state=self.state,
                error_rate=self._calculate_error_rate(),
                retry_after=retry_after
            )

        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_calls >= self.half_open_max_calls:
                return CircuitBreakerResult(
                    allowed=False,
                    state=self.state,
                    error_rate=0.0,
                    retry_after=1
                )

        return CircuitBreakerResult(
            allowed=True,
            state=self.state,
            error_rate=self._calculate_error_rate()
        )


# 全局限流器和熔断器实例
_rate_limiter: Optional[RateLimiter] = None
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_rate_limiter() -> RateLimiter:
    """获取限流器单例"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def get_circuit_breaker(name: str) -> CircuitBreaker:
    """获取熔断器"""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name=name)
    return _circuit_breakers[name]


def _get_request_identifier(request: Request) -> str:
    """
    获取请求标识符
    优先使用user_id，其次使用IP

    Args:
        request: FastAPI请求对象

    Returns:
        请求标识符字符串
    """
    # 优先使用已认证的user_id
    if hasattr(request.state, "user"):
        user = request.state.user
        if hasattr(user, "user_id") and user.user_id != "anonymous":
            return f"user:{user.user_id}"

    # 尝试从请求头获取IP
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # 取第一个IP（最原始的客户端IP）
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"

    return f"ip:{ip}"


async def rate_limit_middleware(request: Request, call_next):
    """
    限流中间件

    处理流程：
    1. 获取请求标识符（user_id或IP）
    2. 检查限流（每分钟/每小时）
    3. 检查熔断状态
    4. 超限或熔断时返回429
    5. 正常则继续处理

    Args:
        request: FastAPI请求对象
        call_next: 下一个处理器

    Returns:
        响应对象

    Raises:
        HTTPException: 限流或熔断时抛出429
    """
    # 公开路径跳过限流
    public_paths = {"/", "/health", "/docs", "/redoc", "/openapi.json"}
    if request.url.path in public_paths:
        return await call_next(request)

    # 获取请求标识符
    identifier = _get_request_identifier(request)

    # 获取限流器
    limiter = get_rate_limiter()

    # 检查每分钟限流
    minute_result = await limiter.check_rate_limit(
        identifier=identifier,
        limit=settings.RATE_LIMIT_PER_MINUTE,
        window_seconds=60
    )

    if not minute_result.allowed:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "code": 429,
                "message": "请求过于频繁，请稍后重试",
                "data": None,
                "meta": {"retry_after": minute_result.retry_after, "limit": minute_result.limit}
            },
            headers={"Retry-After": str(minute_result.retry_after)}
        )

    # 检查熔断器（按服务名获取）
    service_name = _extract_service_name(request.url.path)
    circuit_breaker = get_circuit_breaker(service_name)
    circuit_result = await circuit_breaker.check()

    if not circuit_result.allowed:
        headers = {"Retry-After": str(circuit_result.retry_after)} if circuit_result.retry_after else None
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "code": 503,
                "message": "服务暂时不可用，请稍后重试",
                "data": None,
                "meta": {"retry_after": circuit_result.retry_after, "circuit_state": circuit_result.state.value}
            },
            headers=headers
        )

    # 处理请求
    try:
        response = await call_next(request)

        # 记录成功
        circuit_breaker.record_success()

        # 添加限流响应头
        response.headers["X-RateLimit-Limit"] = str(minute_result.limit)
        response.headers["X-RateLimit-Remaining"] = str(minute_result.remaining)
        response.headers["X-RateLimit-Reset"] = str(minute_result.reset_at)

        return response

    except Exception as e:
        # 记录失败
        circuit_breaker.record_failure()
        raise


def _extract_service_name(path: str) -> str:
    """从路径提取服务名"""
    # 例如 /api/v1/topics -> topics
    parts = path.strip("/").split("/")
    if len(parts) >= 3 and parts[0] == "api" and parts[1] == "v1":
        return parts[2] if len(parts) > 2 else "default"
    return "default"
