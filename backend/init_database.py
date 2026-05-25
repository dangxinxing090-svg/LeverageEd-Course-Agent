#!/usr/bin/env python3
"""
数据库初始化脚本
创建所有表结构
"""
import sys
sys.path.insert(0, '/sessions/6a1177758b0ed9aae363c1e4/workspace/backend')

from app.db.database import engine, Base
from app.models.teaching_session import TeachingSession, ChatMessage
from app.models.user import UserProfile
from app.models.behavior import BehaviorLog
from app.models.exercise import ExerciseHistory
from app.models.progress import LearningProgress

def init_database():
    print("正在创建数据库表...")
    Base.metadata.create_all(bind=engine)
    print("数据库表创建完成！")
    
    # 列出创建的表
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"\n已创建的表 ({len(tables)}个):")
    for table in tables:
        print(f"  - {table}")

if __name__ == "__main__":
    init_database()
