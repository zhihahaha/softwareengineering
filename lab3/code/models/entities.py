"""酒店预订系统核心领域实体。"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base
from models.enums import HotelStatus, OrderStatus, SaleStatus


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class HotelStaff(Base):
    __tablename__ = "hotel_staff"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotels.id"), nullable=False)
    hotel: Mapped["Hotel"] = relationship(back_populates="staff_members")


class PlatformAdmin(Base):
    __tablename__ = "platform_admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)


class Hotel(Base):
    __tablename__ = "hotels"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    city: Mapped[str] = mapped_column(String(80), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[HotelStatus] = mapped_column(
        SqlEnum(HotelStatus, native_enum=False), default=HotelStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    staff_members: Mapped[list["HotelStaff"]] = relationship(back_populates="hotel")
    room_types: Mapped[list["RoomType"]] = relationship(back_populates="hotel")


class RoomType(Base):
    __tablename__ = "room_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotels.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    sale_status: Mapped[SaleStatus] = mapped_column(
        SqlEnum(SaleStatus, native_enum=False), default=SaleStatus.ON_SALE
    )

    hotel: Mapped["Hotel"] = relationship(back_populates="room_types")
    inventories: Mapped[list["DailyInventory"]] = relationship(back_populates="room_type")

    __table_args__ = (CheckConstraint("capacity > 0", name="ck_room_capacity_positive"),)


class DailyInventory(Base):
    __tablename__ = "daily_inventories"

    id: Mapped[int] = mapped_column(primary_key=True)
    room_type_id: Mapped[int] = mapped_column(ForeignKey("room_types.id"), nullable=False)
    inventory_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_rooms: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved_rooms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    room_type: Mapped["RoomType"] = relationship(back_populates="inventories")

    __table_args__ = (
        UniqueConstraint("room_type_id", "inventory_date", name="uq_inventory_room_date"),
        CheckConstraint("total_rooms >= 0", name="ck_inventory_total_nonnegative"),
        CheckConstraint("reserved_rooms >= 0", name="ck_inventory_reserved_nonnegative"),
        CheckConstraint("reserved_rooms <= total_rooms", name="ck_inventory_not_oversold"),
        CheckConstraint("price >= 0", name="ck_inventory_price_nonnegative"),
    )


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotels.id"), nullable=False)
    room_type_id: Mapped[int] = mapped_column(ForeignKey("room_types.id"), nullable=False)
    check_in: Mapped[date] = mapped_column(Date, nullable=False)
    check_out: Mapped[date] = mapped_column(Date, nullable=False)
    guest_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        SqlEnum(OrderStatus, native_enum=False), default=OrderStatus.PENDING
    )
    total_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    price_details: Mapped[list["OrderPriceDetail"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("check_out > check_in", name="ck_order_date_range"),
        CheckConstraint("guest_count > 0", name="ck_order_guest_count_positive"),
        CheckConstraint("total_price >= 0", name="ck_order_price_nonnegative"),
    )


class OrderPriceDetail(Base):
    __tablename__ = "order_price_details"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    stay_date: Mapped[date] = mapped_column(Date, nullable=False)
    nightly_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    order: Mapped["Order"] = relationship(back_populates="price_details")

    __table_args__ = (
        UniqueConstraint("order_id", "stay_date", name="uq_order_price_date"),
        CheckConstraint("nightly_price >= 0", name="ck_nightly_price_nonnegative"),
    )


class OperationLog(Base):
    __tablename__ = "operation_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    operator_role: Mapped[str] = mapped_column(String(30), nullable=False)
    operator_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="")
    result: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
