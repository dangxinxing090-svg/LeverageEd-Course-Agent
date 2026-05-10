"""
U-031 用户Repository

核心职责：用户数据的持久化存储和查询

底层执行逻辑：
1. 提供用户数据的CRUD接口
2. 内存存储实现（生产环境替换为数据库）
3. 支持按ID、邮箱、用户名查询
4. 支持批量操作

内存数据流转：
用户模型 → 序列化 → 内存存储/数据库 → 反序列化 → 用户模型 → 返回

潜在风险：
1. 内存泄漏：大量用户数据（已实现分页查询）
2. 逻辑漏洞：并发写入冲突（内存版本使用锁保护）
3. 边界条件：用户不存在（返回None或抛出异常）
4. 数据安全：密码明文存储（应由上层加密后传入）

依赖：无外部依赖
"""

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from threading import Lock
import uuid

logger = logging.getLogger(__name__)


# ============================================
# 数据模型定义
# ============================================

@dataclass
class User:
    """用户模型"""
    user_id: str
    username: str
    email: str
    password_hash: str = ""  # 密码哈希（由上层加密）
    nickname: str = ""
    avatar_url: str = ""
    role: str = "user"  # user/admin
    status: str = "active"  # active/inactive/banned
    created_at: str = ""
    updated_at: str = ""
    last_login_at: str = ""
    preferences: Dict[str, Any] = None  # 用户偏好设置

    def __post_init__(self):
        if self.preferences is None:
            self.preferences = {}
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "User":
        return cls(**data)


# ============================================
# Repository实现
# ============================================

class UserRepository:
    """
    用户Repository

    提供用户数据的CRUD操作
    """

    def __init__(self):
        """初始化用户Repository"""
        # 内存存储（生产环境替换为数据库连接）
        self._storage: Dict[str, User] = {}
        self._email_index: Dict[str, str] = {}  # email -> user_id
        self._username_index: Dict[str, str] = {}  # username -> user_id
        self._lock = Lock()

    def _validate_user_data(self, data: Dict[str, Any]) -> List[str]:
        """
        校验用户数据

        Args:
            data: 用户数据

        Returns:
            问题列表
        """
        issues = []

        if not data.get("username"):
            issues.append("用户名不能为空")
        elif len(data["username"]) < 2:
            issues.append("用户名至少2个字符")
        elif len(data["username"]) > 50:
            issues.append("用户名最多50个字符")

        if not data.get("email"):
            issues.append("邮箱不能为空")
        elif "@" not in data["email"]:
            issues.append("邮箱格式不正确")

        return issues

    async def create(
        self,
        username: str,
        email: str,
        password_hash: str = "",
        **kwargs
    ) -> User:
        """
        创建用户

        Args:
            username: 用户名
            email: 邮箱
            password_hash: 密码哈希
            **kwargs: 其他字段

        Returns:
            User对象

        Raises:
            ValueError: 参数无效或用户已存在
        """
        # 校验
        issues = self._validate_user_data({
            "username": username,
            "email": email
        })
        if issues:
            raise ValueError("; ".join(issues))

        with self._lock:
            # 检查唯一性
            if email in self._email_index:
                raise ValueError(f"邮箱已存在: {email}")
            if username in self._username_index:
                raise ValueError(f"用户名已存在: {username}")

            # 创建用户
            user_id = f"user-{uuid.uuid4().hex[:12]}"
            now = datetime.now(timezone.utc).isoformat()

            user = User(
                user_id=user_id,
                username=username,
                email=email,
                password_hash=password_hash,
                nickname=kwargs.get("nickname", username),
                avatar_url=kwargs.get("avatar_url", ""),
                role=kwargs.get("role", "user"),
                status=kwargs.get("status", "active"),
                created_at=now,
                updated_at=now,
                preferences=kwargs.get("preferences", {})
            )

            # 存储
            self._storage[user_id] = user
            self._email_index[email] = user_id
            self._username_index[username] = user_id

            logger.info(f"用户创建成功: {user_id}, username={username}")
            return user

    async def get_by_id(self, user_id: str) -> Optional[User]:
        """
        按ID查询用户

        Args:
            user_id: 用户ID

        Returns:
            User对象或None
        """
        return self._storage.get(user_id)

    async def get_by_email(self, email: str) -> Optional[User]:
        """
        按邮箱查询用户

        Args:
            email: 邮箱

        Returns:
            User对象或None
        """
        user_id = self._email_index.get(email)
        if user_id:
            return self._storage.get(user_id)
        return None

    async def get_by_username(self, username: str) -> Optional[User]:
        """
        按用户名查询用户

        Args:
            username: 用户名

        Returns:
            User对象或None
        """
        user_id = self._username_index.get(username)
        if user_id:
            return self._storage.get(user_id)
        return None

    async def update(
        self,
        user_id: str,
        **kwargs
    ) -> User:
        """
        更新用户信息

        Args:
            user_id: 用户ID
            **kwargs: 要更新的字段

        Returns:
            更新后的User对象

        Raises:
            ValueError: 用户不存在或参数无效
        """
        with self._lock:
            user = self._storage.get(user_id)
            if not user:
                raise ValueError(f"用户不存在: {user_id}")

            # 更新字段
            old_email = user.email
            old_username = user.username

            for key, value in kwargs.items():
                if hasattr(user, key) and key not in ("user_id", "created_at"):
                    setattr(user, key, value)

            # 更新时间戳
            user.updated_at = datetime.now(timezone.utc).isoformat()

            # 更新索引
            if "email" in kwargs and kwargs["email"] != old_email:
                del self._email_index[old_email]
                self._email_index[kwargs["email"]] = user_id

            if "username" in kwargs and kwargs["username"] != old_username:
                del self._username_index[old_username]
                self._username_index[kwargs["username"]] = user_id

            logger.info(f"用户更新成功: {user_id}")
            return user

    async def delete(self, user_id: str) -> bool:
        """
        删除用户

        Args:
            user_id: 用户ID

        Returns:
            是否删除成功
        """
        with self._lock:
            user = self._storage.get(user_id)
            if not user:
                return False

            # 删除索引
            del self._email_index[user.email]
            del self._username_index[user.username]

            # 删除存储
            del self._storage[user_id]

            logger.info(f"用户删除成功: {user_id}")
            return True

    async def list_users(
        self,
        page: int = 1,
        page_size: int = 20,
        status: str = None,
        role: str = None
    ) -> Dict[str, Any]:
        """
        分页查询用户列表

        Args:
            page: 页码（从1开始）
            page_size: 每页数量
            status: 状态过滤
            role: 角色过滤

        Returns:
            {users: [...], total: int, page: int, page_size: int}
        """
        users = list(self._storage.values())

        # 过滤
        if status:
            users = [u for u in users if u.status == status]
        if role:
            users = [u for u in users if u.role == role]

        # 排序（按创建时间倒序）
        users.sort(key=lambda u: u.created_at, reverse=True)

        # 分页
        total = len(users)
        start = (page - 1) * page_size
        end = start + page_size

        return {
            "users": [u.to_dict() for u in users[start:end]],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }

    async def update_last_login(self, user_id: str) -> None:
        """
        更新最后登录时间

        Args:
            user_id: 用户ID
        """
        user = self._storage.get(user_id)
        if user:
            user.last_login_at = datetime.now(timezone.utc).isoformat()
            user.updated_at = user.last_login_at


# 全局单例
_user_repository: Optional[UserRepository] = None


def get_user_repository() -> UserRepository:
    """获取用户Repository单例"""
    global _user_repository
    if _user_repository is None:
        _user_repository = UserRepository()
    return _user_repository
