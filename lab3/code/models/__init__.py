"""领域模型包。"""

from models.entities import (
    Customer,
    Hotel,
    HotelStaff,
    DailyInventory,
    OperationLog,
    Order,
    OrderPriceDetail,
    PlatformAdmin,
    RoomType,
)
from models.enums import HotelStatus, OrderStatus, SaleStatus

__all__ = [
    "Customer",
    "Hotel",
    "HotelStaff",
    "DailyInventory",
    "OperationLog",
    "Order",
    "OrderPriceDetail",
    "PlatformAdmin",
    "RoomType",
    "HotelStatus",
    "OrderStatus",
    "SaleStatus",
]
