"""系统状态枚举。"""

from enum import Enum


class HotelStatus(str, Enum):
    OPEN = "营业"
    CLOSED = "停业"
    PENDING = "待审核"
    REJECTED = "审核未通过"


class SaleStatus(str, Enum):
    ON_SALE = "在售"
    OFF_SALE = "停售"


class OrderStatus(str, Enum):
    PENDING = "待确认"
    CONFIRMED = "已确认"
    CANCELLED = "已取消"
    CHECKED_IN = "已入住"
    CHECKED_OUT = "已退房"
