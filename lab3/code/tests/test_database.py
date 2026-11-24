"""数据库初始化的基础测试。"""

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from models.base import Base
import models.entities  # noqa: F401


def test_metadata_contains_core_tables():
    """检查核心领域模型已注册到 ORM 元数据。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    table_names = set(inspect(engine).get_table_names())

    assert {
        "customers",
        "hotel_staff",
        "platform_admins",
        "hotels",
        "room_types",
        "daily_inventories",
        "orders",
        "order_price_details",
        "operation_logs",
    }.issubset(table_names)
