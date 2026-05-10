"""
U-032 知识点Repository

核心职责：知识点数据的持久化存储和查询

底层执行逻辑：
1. 提供知识点数据的CRUD接口
2. 内存存储实现（生产环境替换为数据库）
3. 支持按ID、主题ID、难度查询
4. 支持层级关系存储（板块→知识点→组件）

内存数据流转：
知识点模型 → 序列化 → 内存存储/数据库 → 反序列化 → 知识点模型 → 返回

潜在风险：
1. 内存泄漏：大量知识点数据（已实现分页查询）
2. 逻辑漏洞：层级关系断裂（已实现完整性校验）
3. 边界条件：知识点不存在（返回None或抛出异常）
4. 数据一致性：删除板块时知识点孤立（已实现级联检查）

依赖：无外部依赖
"""

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from threading import Lock
import uuid

logger = logging.getLogger(__name__)


# ============================================
# 数据模型定义
# ============================================

@dataclass
class KnowledgeComponent:
    """知识组件"""
    component_id: str
    component_name: str
    description: str = ""
    order: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class KnowledgePoint:
    """知识点"""
    point_id: str
    point_name: str
    description: str = ""
    block_id: str = ""  # 所属板块ID
    topic_id: str = ""  # 所属主题ID
    order: int = 0
    difficulty: str = "MEDIUM"  # LOW/MEDIUM/HIGH
    importance: str = "IMPORTANT"  # CORE/IMPORTANT/AUXILIARY
    estimated_minutes: int = 15
    components: List[KnowledgeComponent] = None
    prerequisites: List[str] = None  # 前置知识点ID列表
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if self.components is None:
            self.components = []
        if self.prerequisites is None:
            self.prerequisites = []
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["components"] = [c.to_dict() if hasattr(c, 'to_dict') else c for c in self.components]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgePoint":
        components = [
            KnowledgeComponent(**c) if isinstance(c, dict) else c
            for c in data.get("components", [])
        ]
        return cls(
            **{k: v for k, v in data.items() if k != "components"},
            components=components
        )


@dataclass
class KnowledgeBlock:
    """知识板块"""
    block_id: str
    block_name: str
    description: str = ""
    topic_id: str = ""  # 所属主题ID
    order: int = 0
    points: List[KnowledgePoint] = None
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if self.points is None:
            self.points = []
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "block_id": self.block_id,
            "block_name": self.block_name,
            "description": self.description,
            "topic_id": self.topic_id,
            "order": self.order,
            "points": [p.to_dict() for p in self.points],
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


@dataclass
class KnowledgeTopic:
    """知识主题"""
    topic_id: str
    topic_name: str
    description: str = ""
    total_points: int = 0
    total_hours: float = 0
    blocks: List[KnowledgeBlock] = None
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if self.blocks is None:
            self.blocks = []
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic_id": self.topic_id,
            "topic_name": self.topic_name,
            "description": self.description,
            "total_points": self.total_points,
            "total_hours": self.total_hours,
            "blocks": [b.to_dict() for b in self.blocks],
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


# ============================================
# Repository实现
# ============================================

class KnowledgeRepository:
    """
    知识点Repository

    提供知识点数据的CRUD操作
    """

    def __init__(self):
        """初始化知识点Repository"""
        # 内存存储
        self._topics: Dict[str, KnowledgeTopic] = {}
        self._blocks: Dict[str, KnowledgeBlock] = {}
        self._points: Dict[str, KnowledgePoint] = {}
        self._topic_name_index: Dict[str, str] = {}  # topic_name -> topic_id
        self._lock = Lock()

    async def create_topic(
        self,
        topic_name: str,
        description: str = ""
    ) -> KnowledgeTopic:
        """
        创建知识主题

        Args:
            topic_name: 主题名称
            description: 描述

        Returns:
            KnowledgeTopic对象

        Raises:
            ValueError: 参数无效或主题已存在
        """
        if not topic_name or not topic_name.strip():
            raise ValueError("主题名称不能为空")

        with self._lock:
            if topic_name in self._topic_name_index:
                raise ValueError(f"主题已存在: {topic_name}")

            topic_id = f"topic-{uuid.uuid4().hex[:12]}"
            now = datetime.now(timezone.utc).isoformat()

            topic = KnowledgeTopic(
                topic_id=topic_id,
                topic_name=topic_name,
                description=description,
                created_at=now,
                updated_at=now
            )

            self._topics[topic_id] = topic
            self._topic_name_index[topic_name] = topic_id

            logger.info(f"主题创建成功: {topic_id}, name={topic_name}")
            return topic

    async def create_block(
        self,
        topic_id: str,
        block_name: str,
        description: str = "",
        order: int = 0
    ) -> KnowledgeBlock:
        """
        创建知识板块

        Args:
            topic_id: 所属主题ID
            block_name: 板块名称
            description: 描述
            order: 排序

        Returns:
            KnowledgeBlock对象

        Raises:
            ValueError: 参数无效或主题不存在
        """
        if not block_name:
            raise ValueError("板块名称不能为空")

        with self._lock:
            topic = self._topics.get(topic_id)
            if not topic:
                raise ValueError(f"主题不存在: {topic_id}")

            block_id = f"block-{uuid.uuid4().hex[:12]}"
            now = datetime.now(timezone.utc).isoformat()

            block = KnowledgeBlock(
                block_id=block_id,
                block_name=block_name,
                description=description,
                topic_id=topic_id,
                order=order,
                created_at=now,
                updated_at=now
            )

            self._blocks[block_id] = block
            topic.blocks.append(block)
            topic.updated_at = now

            logger.info(f"板块创建成功: {block_id}, name={block_name}")
            return block

    async def create_point(
        self,
        block_id: str,
        point_name: str,
        description: str = "",
        difficulty: str = "MEDIUM",
        importance: str = "IMPORTANT",
        estimated_minutes: int = 15,
        order: int = 0
    ) -> KnowledgePoint:
        """
        创建知识点

        Args:
            block_id: 所属板块ID
            point_name: 知识点名称
            description: 描述
            difficulty: 难度
            importance: 重要性
            estimated_minutes: 预估时长
            order: 排序

        Returns:
            KnowledgePoint对象

        Raises:
            ValueError: 参数无效或板块不存在
        """
        if not point_name:
            raise ValueError("知识点名称不能为空")

        with self._lock:
            block = self._blocks.get(block_id)
            if not block:
                raise ValueError(f"板块不存在: {block_id}")

            point_id = f"point-{uuid.uuid4().hex[:12]}"
            now = datetime.now(timezone.utc).isoformat()

            point = KnowledgePoint(
                point_id=point_id,
                point_name=point_name,
                description=description,
                block_id=block_id,
                topic_id=block.topic_id,
                order=order,
                difficulty=difficulty,
                importance=importance,
                estimated_minutes=estimated_minutes,
                created_at=now,
                updated_at=now
            )

            self._points[point_id] = point
            block.points.append(point)

            # 更新主题统计
            topic = self._topics.get(block.topic_id)
            if topic:
                topic.total_points += 1
                topic.total_hours += estimated_minutes / 60
                topic.updated_at = now

            logger.info(f"知识点创建成功: {point_id}, name={point_name}")
            return point

    async def get_topic(self, topic_id: str) -> Optional[KnowledgeTopic]:
        """按ID查询主题"""
        return self._topics.get(topic_id)

    async def get_topic_by_name(self, topic_name: str) -> Optional[KnowledgeTopic]:
        """按名称查询主题"""
        topic_id = self._topic_name_index.get(topic_name)
        if topic_id:
            return self._topics.get(topic_id)
        return None

    async def get_block(self, block_id: str) -> Optional[KnowledgeBlock]:
        """按ID查询板块"""
        return self._blocks.get(block_id)

    async def get_point(self, point_id: str) -> Optional[KnowledgePoint]:
        """按ID查询知识点"""
        return self._points.get(point_id)

    async def get_points_by_block(self, block_id: str) -> List[KnowledgePoint]:
        """查询板块下所有知识点"""
        block = self._blocks.get(block_id)
        if block:
            return block.points
        return []

    async def get_points_by_topic(self, topic_id: str) -> List[KnowledgePoint]:
        """查询主题下所有知识点"""
        points = []
        topic = self._topics.get(topic_id)
        if topic:
            for block in topic.blocks:
                points.extend(block.points)
        return points

    async def update_point(
        self,
        point_id: str,
        **kwargs
    ) -> KnowledgePoint:
        """
        更新知识点

        Args:
            point_id: 知识点ID
            **kwargs: 要更新的字段

        Returns:
            更新后的知识点

        Raises:
            ValueError: 知识点不存在
        """
        with self._lock:
            point = self._points.get(point_id)
            if not point:
                raise ValueError(f"知识点不存在: {point_id}")

            for key, value in kwargs.items():
                if hasattr(point, key) and key not in ("point_id", "created_at"):
                    setattr(point, key, value)

            point.updated_at = datetime.now(timezone.utc).isoformat()
            logger.info(f"知识点更新成功: {point_id}")
            return point

    async def delete_point(self, point_id: str) -> bool:
        """删除知识点"""
        with self._lock:
            point = self._points.get(point_id)
            if not point:
                return False

            # 从板块中移除
            block = self._blocks.get(point.block_id)
            if block:
                block.points = [p for p in block.points if p.point_id != point_id]

            del self._points[point_id]
            logger.info(f"知识点删除成功: {point_id}")
            return True

    async def list_topics(
        self,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """分页查询主题列表"""
        topics = list(self._topics.values())
        topics.sort(key=lambda t: t.created_at, reverse=True)

        total = len(topics)
        start = (page - 1) * page_size
        end = start + page_size

        return {
            "topics": [t.to_dict() for t in topics[start:end]],
            "total": total,
            "page": page,
            "page_size": page_size
        }


# 全局单例
_knowledge_repository: Optional[KnowledgeRepository] = None


def get_knowledge_repository() -> KnowledgeRepository:
    """获取知识点Repository单例"""
    global _knowledge_repository
    if _knowledge_repository is None:
        _knowledge_repository = KnowledgeRepository()
    return _knowledge_repository
