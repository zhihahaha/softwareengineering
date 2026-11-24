"""数据库引擎、会话和初始化。"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from config import DATA_DIR, DATABASE_URL
from models.base import Base

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(connection, _record) -> None:
    """SQLite 默认不强制外键，连接时显式开启。"""
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def initialize_database() -> None:
    """创建数据目录和当前模型对应的数据表。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 导入模型，确保模型类已注册到 Base.metadata。
    import models.entities  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_session():
    """创建一个数据库会话；调用方负责关闭。"""
    return SessionLocal()
