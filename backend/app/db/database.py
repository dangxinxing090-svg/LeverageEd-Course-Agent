"""
数据库连接配置
使用SQLAlchemy，支持PostgreSQL和SQLite自动fallback
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import os

# 数据库连接配置
# 优先使用环境变量，PostgreSQL不可用时自动fallback到SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "")

# 判断是否需要使用SQLite fallback
_use_sqlite = False
if not DATABASE_URL or DATABASE_URL.startswith("postgresql"):
    # 尝试检测PostgreSQL是否可用
    if DATABASE_URL.startswith("postgresql"):
        try:
            import socket
            # 解析host和port
            # postgresql://user:pass@host:port/db
            parts = DATABASE_URL.replace("postgresql://", "").split("/")[0]
            if "@" in parts:
                parts = parts.split("@")[1]
            if ":" in parts:
                host, port_str = parts.split(":")
                port = int(port_str)
            else:
                host = parts
                port = 5432
            # 测试连接
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, port))
            sock.close()
            if result != 0:
                _use_sqlite = True
        except Exception:
            _use_sqlite = True
    else:
        _use_sqlite = True

if _use_sqlite:
    # 使用SQLite，存储在项目目录下
    sqlite_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "ai_education.db")
    DATABASE_URL = f"sqlite:///{sqlite_path}"
    print(f"[Database] PostgreSQL不可用，自动使用SQLite: {sqlite_path}")
else:
    print(f"[Database] 使用PostgreSQL")

# 创建引擎（SQLite需要check_same_thread=False）
engine_kwargs = {
    "echo": False,
}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    })

engine = create_engine(DATABASE_URL, **engine_kwargs)

# 会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 声明基类
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    获取数据库会话的依赖函数
    用于FastAPI的Depends
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
