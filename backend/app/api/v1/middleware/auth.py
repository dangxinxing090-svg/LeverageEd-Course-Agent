"""
U-010 JWT认证中间件

核心职责：验证请求中的JWT Token，解析用户身份

底层执行逻辑：
1. 从请求头提取 Authorization: Bearer {token}
2. 验证token格式（Bearer前缀）
3. 解码并验证JWT签名
4. 检查token是否过期
5. 提取用户ID和订阅类型
6. 将用户信息注入request.state，供后续处理器使用

内存数据流转：
Request Headers → JWT Token字符串 → 解码验证 → UserInfo dict → request.state.user

潜在风险：
1. 内存泄漏：token验证结果未缓存，大量并发请求重复验证（已用lru_cache缓存公钥）
2. 逻辑漏洞：未校验token的颁发者(issuer)和受众(audience)
3. 安全风险：JWT密钥硬编码在代码中（依赖环境变量）
4. 边界条件：空token、格式错误token、过期token的处理

依赖：PyJWT库
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.responses import JSONResponse
import jwt

from app.core.config import get_settings
from app.core.exceptions import UnauthorizedException

# JWT认证安全方案
security = HTTPBearer(auto_error=False)

# 认证配置
settings = get_settings()


@dataclass
class UserInfo:
    """用户信息数据类"""
    user_id: str
    subscription_type: str  # "FREE" | "PRO"
    exp: Optional[int] = None  # token过期时间戳
    iat: Optional[int] = None  # token签发时间戳

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "user_id": self.user_id,
            "subscription_type": self.subscription_type,
            "exp": self.exp,
            "iat": self.iat
        }


class JWTValidator:
    """
    JWT验证器
    负责token的解码和验证
    """

    def __init__(self):
        self.secret_key = settings.JWT_SECRET_KEY
        self.algorithm = settings.JWT_ALGORITHM

    def decode_token(self, token: str) -> Dict[str, Any]:
        """
        解码并验证JWT token

        Args:
            token: JWT token字符串

        Returns:
            解码后的payload字典

        Raises:
            UnauthorizedException: token无效或已过期
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "require": ["user_id", "subscription_type"]
                }
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise UnauthorizedException("Token已过期，请重新登录")
        except jwt.InvalidTokenError as e:
            raise UnauthorizedException(f"Token无效: {str(e)}")
        except Exception as e:
            raise UnauthorizedException(f"Token验证失败: {str(e)}")

    def extract_user_info(self, payload: Dict[str, Any]) -> UserInfo:
        """
        从payload中提取用户信息

        Args:
            payload: 解码后的JWT payload

        Returns:
            UserInfo对象

        Raises:
            UnauthorizedException: payload缺少必要字段
        """
        # 字段校验
        if "user_id" not in payload:
            raise UnauthorizedException("Token缺少user_id字段")
        if "subscription_type" not in payload:
            raise UnauthorizedException("Token缺少subscription_type字段")

        # subscription_type校验
        sub_type = payload.get("subscription_type", "FREE").upper()
        if sub_type not in ("FREE", "PRO"):
            raise UnauthorizedException("无效的订阅类型")

        return UserInfo(
            user_id=payload["user_id"],
            subscription_type=sub_type,
            exp=payload.get("exp"),
            iat=payload.get("iat")
        )


# 全局验证器实例
_jwt_validator: Optional[JWTValidator] = None


def get_jwt_validator() -> JWTValidator:
    """获取JWT验证器单例"""
    global _jwt_validator
    if _jwt_validator is None:
        _jwt_validator = JWTValidator()
    return _jwt_validator


async def jwt_auth_middleware(request: Request, call_next):
    """
    JWT认证中间件

    处理流程：
    1. 公开路径（白名单）直接放行
    2. 提取Authorization头
    3. 验证JWT token
    4. 将用户信息注入request.state
    5. 传递给下一个处理器

    Args:
        request: FastAPI请求对象
        call_next: 下一个处理器

    Returns:
        响应对象
    """
    # 公开路径白名单（不需要认证）
    public_paths = {
        "/",
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
    }

    # 检查是否在白名单中
    # 公开路径模式：试运行阶段全部开放
    is_public = (
        request.url.path in public_paths
        or request.url.path.startswith("/api/v1/topics")
        or request.url.path.startswith("/api/v1/learning")
        or request.url.path.startswith("/api/v1/users")
        or request.url.path.startswith("/api/v1/auth")
        or request.url.path.startswith("/api/v1/knowledge")
        or request.url.path.startswith("/api/v1/qa")
        or request.url.path.startswith("/api/v1/exercises")
        or request.url.path.startswith("/api/v1/skip")
        or request.url.path.startswith("/api/v1/custom-exercise")
        or request.url.path.startswith("/api/v1/sessions")
        or request.url.path.startswith("/api/v1/behavior")
    )
    if is_public:
        # 公开路径，设置默认用户信息（未登录用户）
        request.state.user = UserInfo(
            user_id="anonymous",
            subscription_type="FREE"
        )
        return await call_next(request)

    # 提取Authorization头
    auth_header = request.headers.get("Authorization")

    # 边界条件：没有Authorization头
    if not auth_header:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "code": 401,
                "message": "缺少Authorization请求头"
            }
        )

    # 边界条件：格式错误（不是Bearer token）
    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "code": 401,
                "message": "Authorization头格式错误，应为: Bearer {token}"
            }
        )

    # 提取token
    token = auth_header[7:]  # 去掉"Bearer "前缀

    # 边界条件：空token
    if not token or not token.strip():
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "code": 401,
                "message": "Token不能为空"
            }
        )

    # 验证token
    validator = get_jwt_validator()
    try:
        payload = validator.decode_token(token)
        user_info = validator.extract_user_info(payload)

        # 将用户信息注入request.state
        request.state.user = user_info

    except UnauthorizedException as e:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "code": 401,
                "message": e.message
            }
        )

    # 继续处理
    return await call_next(request)


def get_current_user(request: Request) -> UserInfo:
    """
    获取当前请求的用户信息

    从request.state中获取已认证的用户信息

    Args:
        request: FastAPI请求对象

    Returns:
        UserInfo对象

    Raises:
        HTTPException: 用户未认证
    """
    if not hasattr(request.state, "user"):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "code": 401,
                "message": "用户未认证"
            }
        )

    return request.state.user


def require_subscription(required_type: str = "PRO"):
    """
    订阅类型装饰器
    要求用户具有指定或更高级别的订阅

    Args:
        required_type: 需要的订阅类型

    Usage:
        @app.get("/pro-feature")
        @require_subscription("PRO")
        async def pro_feature():
            return {"message": "Pro功能"}
    """
    def decorator(func):
        async def wrapper(request: Request, *args, **kwargs):
            user = get_current_user(request)

            # FREE用户不能访问PRO功能
            if required_type == "PRO" and user.subscription_type == "FREE":
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "code": 403,
                        "message": "此功能需要专业版订阅"
                    }
                )
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator
