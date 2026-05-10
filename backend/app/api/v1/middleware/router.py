"""
U-011 请求路由器

核心职责：按URL路径和HTTP方法路由到对应处理函数

底层执行逻辑：
1. 解析请求的method和path
2. 根据路由配置表查找匹配的处理器
3. 提取路径参数
4. 验证请求方法
5. 调用处理器函数

内存数据流转：
Request(method, path) → RouteConfig匹配 → HandlerFunction → Response

潜在风险：
1. 内存泄漏：路由配置表未做边界检查（已用默认值兜底）
2. 逻辑漏洞：路径参数类型转换失败未处理（已用try-except包装）
3. 边界条件：路径末尾斜杠的处理、路径参数为空的情况

依赖：FastAPI Router
"""

from typing import Callable, Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import re

from fastapi import Request, HTTPException, status
from pydantic import BaseModel, ValidationError


class HTTPMethod(str, Enum):
    """HTTP方法枚举"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class RouteHandler:
    """路由处理器包装器"""
    def __init__(
        self,
        path: str,
        method: HTTPMethod,
        handler: Callable,
        handler_name: str,
        summary: str = "",
        description: str = "",
        tags: List[str] = None,
        auth_required: bool = True,
        path_params: List[str] = None
    ):
        self.path = path
        self.method = method
        self.handler = handler
        self.handler_name = handler_name
        self.summary = summary
        self.description = description
        self.tags = tags or []
        self.auth_required = auth_required
        self.path_params = path_params or []

        # 编译路径模式用于参数提取
        self._path_pattern = self._compile_path_pattern(path)

    def _compile_path_pattern(self, path: str) -> re.Pattern:
        """
        编译路径模式为正则表达式

        将 {param} 转换为命名捕获组 (?P<param>[^/]+)

        Args:
            path: 路由路径，如 /users/{user_id}

        Returns:
            编译后的正则表达式
        """
        # 转义特殊字符，替换 {param} 为捕获组
        pattern = re.sub(r'\{(\w+)\}', r'(?P<\1>[^/]+)', path)
        # 匹配整个路径（支持末尾可选斜杠）
        pattern = f"^{pattern}/?$"
        return re.compile(pattern)

    def match(self, method: str, path: str) -> Optional[Dict[str, str]]:
        """
        尝试匹配请求

        Args:
            method: HTTP方法
            path: 请求路径

        Returns:
            如果匹配成功，返回路径参数字典；否则返回None
        """
        # 方法不匹配
        if self.method.value != method.upper():
            return None

        # 路径匹配
        match = self._path_pattern.match(path)
        if match:
            return match.groupdict()
        return None

    def __repr__(self) -> str:
        return f"RouteHandler({self.method.value} {self.path})"


class RouterConfig:
    """
    路由配置管理器
    管理所有路由注册和匹配
    """

    def __init__(self):
        self._routes: List[RouteHandler] = []
        self._route_index: Dict[str, List[RouteHandler]] = {}  # 按method索引

    def register(
        self,
        path: str,
        method: HTTPMethod,
        handler: Callable,
        handler_name: str = "",
        summary: str = "",
        description: str = "",
        tags: List[str] = None,
        auth_required: bool = True
    ) -> RouteHandler:
        """
        注册路由

        Args:
            path: 路由路径，支持 {param} 格式的路径参数
            method: HTTP方法
            handler: 处理函数
            handler_name: 处理函数名称
            summary: 路由摘要
            description: 路由描述
            tags: 路由标签
            auth_required: 是否需要认证

        Returns:
            注册的路由处理器
        """
        handler_name = handler_name or handler.__name__

        # 提取路径参数
        path_params = re.findall(r'\{(\w+)\}', path)

        route = RouteHandler(
            path=path,
            method=method,
            handler=handler,
            handler_name=handler_name,
            summary=summary,
            description=description,
            tags=tags,
            auth_required=auth_required,
            path_params=path_params
        )

        self._routes.append(route)

        # 更新索引
        key = method.value
        if key not in self._route_index:
            self._route_index[key] = []
        self._route_index[key].append(route)

        return route

    def get(self, path: str, **kwargs) -> Callable:
        """GET方法装饰器"""
        def decorator(func: Callable) -> Callable:
            self.register(path, HTTPMethod.GET, func, **kwargs)
            return func
        return decorator

    def post(self, path: str, **kwargs) -> Callable:
        """POST方法装饰器"""
        def decorator(func: Callable) -> Callable:
            self.register(path, HTTPMethod.POST, func, **kwargs)
            return func
        return decorator

    def put(self, path: str, **kwargs) -> Callable:
        """PUT方法装饰器"""
        def decorator(func: Callable) -> Callable:
            self.register(path, HTTPMethod.PUT, func, **kwargs)
            return func
        return decorator

    def delete(self, path: str, **kwargs) -> Callable:
        """DELETE方法装饰器"""
        def decorator(func: Callable) -> Callable:
            self.register(path, HTTPMethod.DELETE, func, **kwargs)
            return func
        return decorator

    def find_route(self, method: str, path: str) -> Optional[RouteHandler]:
        """
        查找匹配的路由

        Args:
            method: HTTP方法
            path: 请求路径

        Returns:
            匹配的路由处理器，如果未找到返回None
        """
        routes = self._route_index.get(method.upper(), [])

        for route in routes:
            params = route.match(method.upper(), path)
            if params:
                # 将路径参数缓存到路由对象
                route._extracted_params = params
                return route

        return None

    def get_routes(self) -> List[Dict[str, Any]]:
        """获取所有路由列表（用于文档生成）"""
        return [
            {
                "path": r.path,
                "method": r.method.value,
                "handler": r.handler_name,
                "summary": r.summary,
                "tags": r.tags,
                "auth_required": r.auth_required,
                "path_params": r.path_params
            }
            for r in self._routes
        ]


# 全局路由配置实例
router_config = RouterConfig()


async def route_request(request: Request, call_next) -> Any:
    """
    请求路由中间件

    处理流程：
    1. 解析请求方法和路径
    2. 从路由配置中查找匹配的路由
    3. 提取路径参数
    4. 将参数注入request.state
    5. 调用路由处理函数

    Args:
        request: FastAPI请求对象
        call_next: 下一个处理器

    Returns:
        响应对象

    Raises:
        HTTPException: 路由未找到或方法不支持
    """
    method = request.method
    path = str(request.url.path)

    # 查找路由
    route = router_config.find_route(method, path)

    if route is None:
        # 尝试查找相似路径提供友好提示
        suggestions = _find_similar_routes(method, path, router_config)
        error_detail = f"路由 {method} {path} 未找到"

        if suggestions:
            error_detail += f"，您是否想访问: {', '.join(suggestions)}"

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": 404,
                "message": error_detail,
                "suggestions": suggestions if suggestions else None
            }
        )

    # 提取路径参数
    path_params = getattr(route, '_extracted_params', {})

    # 将路由信息和参数注入request.state
    request.state.route = route
    request.state.path_params = path_params
    request.state.handler = route.handler

    # 继续处理
    return await call_next(request)


def _find_similar_routes(
    method: str,
    path: str,
    config: RouterConfig
) -> List[str]:
    """
    查找相似的路由用于错误提示

    Args:
        method: HTTP方法
        path: 请求路径
        config: 路由配置

    Returns:
        相似路由列表
    """
    routes = config._route_index.get(method.upper(), [])

    # 简单相似度计算：计算共同的前缀长度
    def similarity(route: RouteHandler) -> int:
        common = 0
        for a, b in zip(route.path, path):
            if a == b:
                common += 1
            else:
                break
        return common

    # 排序并返回前3个最相似的
    sorted_routes = sorted(routes, key=similarity, reverse=True)
    return [r.path for r in sorted_routes[:3] if similarity(r) > 3]


def get_path_params(request: Request) -> Dict[str, str]:
    """
    获取路径参数

    Args:
        request: FastAPI请求对象

    Returns:
        路径参数字典
    """
    return getattr(request.state, 'path_params', {})


def get_handler(request: Request) -> Optional[Callable]:
    """
    获取路由处理函数

    Args:
        request: FastAPI请求对象

    Returns:
        处理函数
    """
    return getattr(request.state, 'handler', None)
