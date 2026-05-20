"""
知识结构缓存

用于在API端点之间共享知识结构数据
"""

import hashlib
import json
import logging
import os
from typing import Dict, Optional, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)

# 内存缓存：topic_id -> 知识结构数据
_topic_cache: Dict[str, Any] = {}
# 内存缓存：topic_id -> 全景介绍文本
_topic_overview: Dict[str, str] = {}
# 内存缓存：记录已完成的知识点 (topic_id, point_id) -> 完成信息
_completed_points: Dict[str, Dict[str, Any]] = {}
# 内存缓存：记录每个知识组件的学习状态 (component_id) -> 状态信息
# status: "not_started" | "in_progress" | "learn_completed" | "practicing" | "exercise_passed"
_component_status: Dict[str, Dict[str, Any]] = {}

# 持久化存储目录
# knowledge_cache.py 位于 backend/app/api/v1/endpoints/，向上4级到backend/
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_THIS_DIR))))
_DATA_DIR = os.path.join(_BACKEND_DIR, "data", "topics")


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
    内存缓存未命中时，从持久化文件中加载。
    """
    # 第一层：内存缓存查找
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

    # 第二层：内存缓存未命中，从持久化文件中查找
    if os.path.isdir(_DATA_DIR):
        logger.debug(f"组件信息内存缓存未命中，尝试从持久化文件查找: component_id={component_id}")
        for filename in os.listdir(_DATA_DIR):
            if not filename.endswith(".json"):
                continue
            file_path = os.path.join(_DATA_DIR, filename)
            # 跳过子目录（如 explanations/），只处理主题数据文件
            if os.path.isdir(file_path):
                continue
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                structure = data.get("structure")
                if not structure or not isinstance(structure, dict) or "blocks" not in structure:
                    continue
                for block in structure["blocks"]:
                    for point in block.get("points", []):
                        for comp in point.get("components", []):
                            if comp.get("component_id") == component_id:
                                # 找到后恢复到内存缓存
                                topic_id = data.get("topic_id", "")
                                if topic_id:
                                    set_topic_structure(topic_id, structure)
                                logger.info(f"组件信息从持久化文件命中: component_id={component_id}, topic_id={topic_id}, file={filename}")
                                return {
                                    "component_id": comp["component_id"],
                                    "component_name": comp["component_name"],
                                    "point_id": point["point_id"],
                                    "point_name": point["point_name"],
                                    "block_name": block["block_name"],
                                    "topic_name": data.get("topic_text", ""),
                                }
            except Exception:
                continue

    logger.debug(f"组件信息未找到（内存缓存和持久化文件均未命中）: component_id={component_id}")
    return None


# ==================== 知识点完成状态管理 ====================

def _make_completed_key(topic_id: str, point_id: str) -> str:
    """生成已完成知识点的缓存key"""
    return f"{topic_id}:{point_id}"


def mark_point_completed(topic_id: str, point_id: str, score: float = 0):
    """
    标记知识点为已完成

    同时更新知识结构缓存中对应组件和知识点的状态
    """
    key = _make_completed_key(topic_id, point_id)
    _completed_points[key] = {
        "topic_id": topic_id,
        "point_id": point_id,
        "score": score,
        "completed_at": datetime.now().isoformat(),
    }

    # 同步更新知识结构缓存中的状态
    structure = _topic_cache.get(topic_id)
    if structure:
        if isinstance(structure, dict) and "blocks" in structure:
            for block in structure["blocks"]:
                for point in block.get("points", []):
                    if point.get("point_id") == point_id:
                        point["status"] = "completed"
                        for comp in point.get("components", []):
                            comp["status"] = "completed"
        elif hasattr(structure, 'blocks'):
            for block in structure.blocks:
                for point in block.points:
                    if point.point_id == point_id:
                        point.status = "completed"
                        for comp in point.components:
                            comp.status = "completed"


def get_completed_points(topic_id: str) -> List[Dict[str, Any]]:
    """
    获取指定主题下所有已完成的知识点列表

    返回格式: [{"point_id": ..., "point_name": ..., "score": ..., "completed_at": ...}]
    """
    result = []
    prefix = f"{topic_id}:"
    for key, info in _completed_points.items():
        if key.startswith(prefix):
            # 从知识结构中查找point_name
            point_name = info.get("point_id", "")
            structure = _topic_cache.get(topic_id)
            if structure:
                point_name = _find_point_name(structure, info["point_id"]) or point_name
            result.append({
                "point_id": info["point_id"],
                "point_name": point_name,
                "score": info.get("score", 0),
                "completed_at": info.get("completed_at", ""),
            })
    return result


def is_point_completed(topic_id: str, point_id: str) -> bool:
    """检查知识点是否已完成"""
    key = _make_completed_key(topic_id, point_id)
    return key in _completed_points


def find_topic_id_by_point(point_id: str) -> Optional[str]:
    """
    根据point_id查找所属的topic_id
    """
    for topic_id, structure in _topic_cache.items():
        if isinstance(structure, dict) and "blocks" in structure:
            for block in structure["blocks"]:
                for point in block.get("points", []):
                    if point.get("point_id") == point_id:
                        return topic_id
        elif hasattr(structure, 'blocks'):
            for block in structure.blocks:
                for point in block.points:
                    if point.point_id == point_id:
                        return topic_id
    return None


def _find_point_name(structure: Any, point_id: str) -> Optional[str]:
    """从知识结构中查找知识点名称"""
    if isinstance(structure, dict) and "blocks" in structure:
        for block in structure["blocks"]:
            for point in block.get("points", []):
                if point.get("point_id") == point_id:
                    return point.get("point_name", "")
    elif hasattr(structure, 'blocks'):
        for block in structure.blocks:
            for point in block.points:
                if point.point_id == point_id:
                    return point.point_name
    return None


# ==================== 组件学习状态管理 ====================

def set_component_status(component_id: str, status: str, topic_id: str = "", point_id: str = ""):
    """
    写入组件状态到内存缓存（由 behavior 端点调用）

    Args:
        component_id: 组件ID
        status: 状态值 (in_progress/learn_completed/practicing/exercise_passed)
        topic_id: 主题ID（可选）
        point_id: 知识点ID（可选）
    """
    _component_status[component_id] = {
        "status": status,
        "topic_id": topic_id,
        "point_id": point_id,
        "updated_at": datetime.now().isoformat(),
    }

    # 同步更新知识结构缓存中对应组件的 status
    if topic_id:
        structure = _topic_cache.get(topic_id)
        if structure and isinstance(structure, dict) and "blocks" in structure:
            for block in structure["blocks"]:
                for point in block.get("points", []):
                    for comp in point.get("components", []):
                        if comp.get("component_id") == component_id:
                            comp["status"] = status
                            break


def get_all_component_status(topic_id: str) -> Dict[str, str]:
    """
    获取指定主题下所有组件的内存缓存状态

    Returns:
        { component_id: status }
    """
    result = {}
    for comp_id, info in _component_status.items():
        if info.get("topic_id") == topic_id:
            result[comp_id] = info["status"]
    return result


# ==================== 主题数据持久化 ====================

def _topic_text_to_key(topic_text: str) -> str:
    """将主题文本转换为安全的文件名key（MD5哈希）"""
    return hashlib.md5(topic_text.strip().encode("utf-8")).hexdigest()


def _get_topic_file_path(topic_text: str) -> str:
    """获取主题数据的文件路径"""
    key = _topic_text_to_key(topic_text)
    return os.path.join(_DATA_DIR, f"{key}.json")


def save_topic_to_file(topic_text: str, topic_id: str, overview: str, structure: Any):
    """
    将LLM生成的主题数据持久化到本地JSON文件

    以topic_text为key，保存全景介绍和知识结构。
    同时记录topic_text，方便后续匹配。
    """
    os.makedirs(_DATA_DIR, exist_ok=True)
    file_path = _get_topic_file_path(topic_text)
    data = {
        "topic_text": topic_text,
        "topic_id": topic_id,
        "overview": overview,
        "structure": structure,
        "saved_at": datetime.now().isoformat(),
    }
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"主题数据已持久化: {topic_text} -> {file_path}")
    except Exception as e:
        logger.error(f"主题数据持久化失败: {e}", exc_info=True)


def load_topic_from_file(topic_text: str) -> Optional[Dict[str, Any]]:
    """
    根据主题文本从本地文件加载已保存的主题数据

    返回格式: {"topic_id": ..., "overview": ..., "structure": ..., "saved_at": ...}
    如果没有找到缓存文件，返回None。
    """
    file_path = _get_topic_file_path(topic_text)
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"主题数据已从文件加载: {topic_text} (saved_at={data.get('saved_at', 'unknown')})")
        return data
    except Exception as e:
        logger.error(f"主题数据文件加载失败: {e}", exc_info=True)
        return None


# ==================== 知识点讲解持久化 ====================

_EXPLANATIONS_DIR = os.path.join(_DATA_DIR, "explanations")


def _get_explanation_file_path(component_id: str) -> str:
    """获取知识点讲解的文件路径"""
    # 使用component_id的MD5作为文件名
    key = hashlib.md5(component_id.strip().encode("utf-8")).hexdigest()
    return os.path.join(_EXPLANATIONS_DIR, f"{key}.json")


def save_explanation_to_file(component_id: str, knowledge_name: str, content: str, sections: list = None):
    """
    将LLM生成的知识点讲解持久化到本地JSON文件

    以component_id为key，保存讲解内容。
    支持纯文本格式（content）和结构化格式（sections）。
    """
    os.makedirs(_EXPLANATIONS_DIR, exist_ok=True)
    file_path = _get_explanation_file_path(component_id)
    data = {
        "component_id": component_id,
        "knowledge_name": knowledge_name,
        "saved_at": datetime.now().isoformat(),
    }
    if content:
        data["content"] = content
    if sections:
        data["sections"] = sections
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"知识点讲解已持久化: component_id={component_id}, knowledge_name={knowledge_name}")
    except Exception as e:
        logger.error(f"知识点讲解持久化失败: {e}", exc_info=True)


def load_explanation_from_file(component_id: str) -> Optional[Dict[str, Any]]:
    """
    根据component_id从本地文件加载已保存的知识点讲解

    返回格式: {"component_id": ..., "knowledge_name": ..., "content": ..., "saved_at": ...}
    如果没有找到缓存文件，返回None。
    """
    file_path = _get_explanation_file_path(component_id)
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"知识点讲解已从文件加载: component_id={component_id} (saved_at={data.get('saved_at', 'unknown')})")
        return data
    except Exception as e:
        logger.error(f"知识点讲解文件加载失败: {e}", exc_info=True)
        return None
