"""
知识结构缓存

用于在API端点之间共享知识结构数据
"""

from typing import Dict, Optional, Any

# 内存缓存：topic_id -> 知识结构数据
_topic_cache: Dict[str, Any] = {}
# 内存缓存：topic_id -> 全景介绍文本
_topic_overview: Dict[str, str] = {}


def set_topic_structure(topic_id: str, structure: Any):
    """存储主题的知识结构"""
    _topic_cache[topic_id] = structure


def get_topic_structure(topic_id: str) -> Optional[Any]:
    """获取主题的知识结构"""
    return _topic_cache.get(topic_id)


def set_topic_overview(topic_id: str, overview: str):
    """存储主题的全景介绍"""
    _topic_overview[topic_id] = overview


def get_topic_overview(topic_id: str) -> Optional[str]:
    """获取主题的全景介绍"""
    return _topic_overview.get(topic_id)


def find_component_info(component_id: str) -> Optional[Dict[str, str]]:
    """
    根据component_id在所有缓存的知识结构中查找组件信息。
    同时支持新版dict结构和旧版dataclass结构。
    """
    for topic_id, structure in _topic_cache.items():
        # 新版：dict结构
        if isinstance(structure, dict) and "blocks" in structure:
            for block in structure["blocks"]:
                for point in block.get("points", []):
                    for comp in point.get("components", []):
                        if comp.get("component_id") == component_id:
                            return {
                                "component_id": comp["component_id"],
                                "component_name": comp["component_name"],
                                "point_id": point["point_id"],
                                "point_name": point["point_name"],
                                "block_name": block["block_name"],
                            }
        # 旧版：dataclass结构
        elif hasattr(structure, 'blocks'):
            for block in structure.blocks:
                for point in block.points:
                    for comp in point.components:
                        if comp.component_id == component_id:
                            return {
                                "component_id": comp.component_id,
                                "component_name": comp.component_name,
                                "point_id": point.point_id,
                                "point_name": point.point_name,
                                "block_name": block.block_name,
                            }
    return None
