"""酒店经营及平台统计服务。"""
from datetime import date
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from models.entities import Hotel, DailyInventory, RoomType, Order
from models.enums import HotelStatus, OrderStatus


class StatisticsService:
    """提供酒店与平台统计数据。"""
    @staticmethod
    def hotel_daily(session: Session, hotel_id: int, target_date: date) -> dict:
        hotel = session.get(Hotel, hotel_id)
        if hotel is None:
            raise ValueError("酒店不存在")
        rows = session.execute(
            select(DailyInventory.total_rooms, DailyInventory.reserved_rooms)
            .join(RoomType, RoomType.id == DailyInventory.room_type_id)
            .where(RoomType.hotel_id == hotel_id, DailyInventory.inventory_date == target_date)
        ).all()
        total = sum(row.total_rooms for row in rows)
        reserved = sum(row.reserved_rooms for row in rows)
        return {"hotel_id": hotel_id, "hotel_name": hotel.name, "date": target_date,
                "total_rooms": total, "reserved_rooms": reserved,
                "remaining_rooms": total - reserved}

    @staticmethod
    def hotel_order_summary(session: Session, hotel_id: int, start: date, end: date) -> dict:
        if end < start:
            raise ValueError("结束日期不能早于开始日期")
        hotel = session.get(Hotel, hotel_id)
        if hotel is None:
            raise ValueError("酒店不存在")
        # Date range is interpreted inclusively by calendar date.
        from datetime import datetime, time, timedelta
        begin_dt = datetime.combine(start, time.min)
        end_dt = datetime.combine(end + timedelta(days=1), time.min)
        orders = list(session.scalars(select(Order).where(Order.hotel_id == hotel_id,
                         Order.created_at >= begin_dt, Order.created_at < end_dt)))
        return {"hotel_id": hotel_id, "hotel_name": hotel.name, "start": start, "end": end,
                "orders": len(orders),
                "cancelled": sum(o.status == OrderStatus.CANCELLED for o in orders)}

    @staticmethod
    def platform_summary(session: Session, start: date, end: date) -> dict:
        if end < start:
            raise ValueError("结束日期不能早于开始日期")
        from datetime import datetime, time, timedelta
        hotel_total = session.scalar(select(func.count(Hotel.id))) or 0
        open_total = session.scalar(select(func.count(Hotel.id)).where(Hotel.status == HotelStatus.OPEN)) or 0
        begin_dt = datetime.combine(start, time.min)
        end_dt = datetime.combine(end + timedelta(days=1), time.min)
        order_total = session.scalar(select(func.count(Order.id)).where(
            Order.created_at >= begin_dt, Order.created_at < end_dt)) or 0
        return {"hotel_total": hotel_total, "open_hotel_total": open_total,
                "order_total": order_total, "start": start, "end": end}
