"""
练习记录仓库

内存存储实现（生产环境替换为数据库）
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from threading import Lock
from datetime import datetime
import uuid


@dataclass
class ExerciseRecord:
    """练习记录"""
    record_id: str
    user_id: str
    component_id: str
    component_name: str
    topic_name: str
    point_name: str
    question_content: str
    user_answer: str
    correct_answer: str
    is_correct: bool
    error_analysis: str = ""
    feedback: str = ""
    submitted_at: str = ""


class ExerciseRepository:
    """练习记录仓库（内存存储实现）"""

    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # 内存存储
        self._records: Dict[str, ExerciseRecord] = {}  # record_id -> Record
        self._user_records: Dict[str, List[str]] = {}  # user_id -> [record_ids]
        self._component_records: Dict[str, List[str]] = {}  # component_id -> [record_ids]
        self._data_lock = Lock()
        self._initialized = True

    def save_record(self, record: ExerciseRecord) -> str:
        """保存练习记录"""
        with self._data_lock:
            # 生成 ID
            if not record.record_id:
                record.record_id = f"ex_{uuid.uuid4().hex[:12]}"

            # 设置时间
            if not record.submitted_at:
                record.submitted_at = datetime.now().isoformat()

            # 存储
            self._records[record.record_id] = record

            # 用户索引
            if record.user_id not in self._user_records:
                self._user_records[record.user_id] = []
            self._user_records[record.user_id].append(record.record_id)

            # 组件索引
            if record.component_id not in self._component_records:
                self._component_records[record.component_id] = []
            self._component_records[record.component_id].append(record.record_id)

            return record.record_id

    def get_user_records(self, user_id: str, limit: int = 50) -> List[ExerciseRecord]:
        """获取用户所有练习记录"""
        with self._data_lock:
            record_ids = self._user_records.get(user_id, [])
            records = [self._records[rid] for rid in record_ids if rid in self._records]
            # 按时间倒序
            records.sort(key=lambda x: x.submitted_at, reverse=True)
            return records[:limit]

    def get_component_records(self, user_id: str, component_id: str) -> List[ExerciseRecord]:
        """获取某知识组件的练习记录"""
        with self._data_lock:
            record_ids = self._component_records.get(component_id, [])
            records = [
                self._records[rid] for rid in record_ids
                if rid in self._records and self._records[rid].user_id == user_id
            ]
            records.sort(key=lambda x: x.submitted_at, reverse=True)
            return records

    def get_record_by_id(self, record_id: str) -> Optional[ExerciseRecord]:
        """根据 ID 获取记录"""
        with self._data_lock:
            return self._records.get(record_id)

    def delete_user_records(self, user_id: str) -> int:
        """删除用户所有记录"""
        with self._data_lock:
            record_ids = self._user_records.get(user_id, [])
            count = 0
            for rid in record_ids:
                if rid in self._records:
                    record = self._records[rid]
                    # 清理组件索引
                    if record.component_id in self._component_records:
                        self._component_records[record.component_id] = [
                            x for x in self._component_records[record.component_id] if x != rid
                        ]
                    del self._records[rid]
                    count += 1
            del self._user_records[user_id]
            return count


# 全局单例
_exercise_repo: Optional[ExerciseRepository] = None


def get_exercise_repo() -> ExerciseRepository:
    """获取练习记录仓库实例"""
    global _exercise_repo
    if _exercise_repo is None:
        _exercise_repo = ExerciseRepository()
    return _exercise_repo
