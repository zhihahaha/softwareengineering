"""房型和每日库存管理服务。"""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation


from sqlalchemy import select
from sqlalchemy.orm import Session

from models.entities import DailyInventory, Hotel, HotelStaff, PlatformAdmin, RoomType
from models.enums import SaleStatus
from services.hotel_service import HotelService
from services.log_service import LogService


class RoomService:
    """负责房型资料、销售状态、每日库存与价格，不负责订单状态。"""



    @staticmethod
    def list_room_types(session: Session, hotel_id: int, include_off_sale: bool = True):
        query = select(RoomType).where(RoomType.hotel_id == hotel_id).order_by(RoomType.id)
        if not include_off_sale:
            query = query.where(RoomType.sale_status == SaleStatus.ON_SALE)
        return list(session.scalars(query))


    @staticmethod
    def create_room_type(session: Session, operator, hotel_id: int, name: str,
                        capacity: int, description: str = "") -> RoomType:
        hotel = HotelService._get_hotel(session, hotel_id)
        HotelService._authorize_hotel(operator, hotel)
        if not name.strip():
            raise ValueError("房型名称不能为空")
        if not isinstance(capacity, int) or capacity <= 0:
            raise ValueError("入住人数必须为正整数")
        room_type = RoomType(hotel_id=hotel_id, name=name.strip(), capacity=capacity,
                           description=description.strip(), sale_status=SaleStatus.ON_SALE)
        session.add(room_type)
        session.flush()
        LogService.record(session, RoomService._role(operator), operator.id, "创建房型",
                         f"房型ID={room_type.id}，酒店ID={hotel_id}，名称={room_type.name}")
        return room_type



    @staticmethod
    def update_room_type(session: Session, operator, room_type_id: int, **changes) -> RoomType:
        room_type = RoomService._get_room_type(session, room_type_id)
        hotel = HotelService._get_hotel(session, room_type.hotel_id)
        HotelService._authorize_hotel(operator, hotel)
        allowed = {"name", "capacity", "description"}
        for key, value in changes.items():
            if key not in allowed:
                continue
            if key == "name" and not str(value).strip():
                raise ValueError("房型名称不能为空")
            if key == "capacity" and (not isinstance(value, int) or value <= 0):
                raise ValueError("入住人数必须为正整数")
            setattr(room_type, key, value.strip() if isinstance(value, str) else value)
        LogService.record(session, RoomService._role(operator), operator.id, "修改房型信息",
                         f"房型ID={room_type.id}")
        return room_type



    @staticmethod
    def set_sale_status(session: Session, operator, room_type_id: int,
                        status: SaleStatus) -> RoomType:
        room_type = RoomService._get_room_type(session, room_type_id)
        hotel = HotelService._get_hotel(session, room_type.hotel_id)
        HotelService._authorize_hotel(operator, hotel)
        if not isinstance(status, SaleStatus):
            raise ValueError("无效的房型销售状态")
        room_type.sale_status = status
        LogService.record(session, RoomService._role(operator), operator.id, "修改房型销售状态",
                         f"房型ID={room_type.id}，状态={status.value}")
        return room_type



    @staticmethod
    def set_inventory_range(session: Session, operator, room_type_id: int,
                           start_date: date, end_date: date, total_rooms: int,
                           price) -> list[DailyInventory]:
        """设置[start_date, end_date]日期范围内每天的房量和价格。"""
        room_type = RoomService._get_room_type(session, room_type_id)
        hotel = HotelService._get_hotel(session, room_type.hotel_id)
        HotelService._authorize_hotel(operator, hotel)
        if start_date > end_date:
            raise ValueError("开始日期不能晚于结束日期")
        if not isinstance(total_rooms, int) or total_rooms < 0:
            raise ValueError("总房间数不能为负数")
        try:
            price_value = Decimal(str(price))
        except (InvalidOperation, ValueError):
            raise ValueError("价格格式无效") from None
        if not price_value.is_finite() or price_value < 0:
            raise ValueError("价格不能为负数")

        results = []
        current = start_date
        while current <= end_date:
            inventory = session.scalar(select(DailyInventory).where(
                DailyInventory.room_type_id == room_type_id,
                DailyInventory.inventory_date == current,
            ))
            if inventory is None:
                inventory = DailyInventory(room_type_id=room_type_id,
                    inventory_date=current, total_rooms=total_rooms,
                    reserved_rooms=0, price=price_value)
                session.add(inventory)
            else:
                if total_rooms < inventory.reserved_rooms:
                    raise ValueError(f"{current} 总房间数不能小于已预订数量 {inventory.reserved_rooms}")
                inventory.total_rooms = total_rooms
                inventory.price = price_value
            results.append(inventory)
            current += timedelta(days=1)
        session.flush()
        LogService.record(session, RoomService._role(operator), operator.id, "批量设置库存价格",
            f"房型ID={room_type_id}，日期={start_date}至{end_date}，总房间数={total_rooms}，价格={price_value}")
        return results



    @staticmethod
    def list_inventory(session: Session, room_type_id: int, start_date: date = None,
                      end_date: date = None):
        query = select(DailyInventory).where(DailyInventory.room_type_id == room_type_id)
        if start_date is not None:
            query = query.where(DailyInventory.inventory_date >= start_date)
        if end_date is not None:
            query = query.where(DailyInventory.inventory_date <= end_date)
        query = query.order_by(DailyInventory.inventory_date)
        return list(session.scalars(query))



    @staticmethod
    def get_availability(session: Session, room_type_id: int, stay_date: date) -> int:
        room_type = RoomService._get_room_type(session, room_type_id)
        if room_type.sale_status != SaleStatus.ON_SALE:
            return 0
        inventory = session.scalar(select(DailyInventory).where(
            DailyInventory.room_type_id == room_type_id,
            DailyInventory.inventory_date == stay_date,
        ))
        if inventory is None:
            return 0
        return inventory.total_rooms - inventory.reserved_rooms



    @staticmethod
    def _get_room_type(session: Session, room_type_id: int) -> RoomType:
        room_type = session.get(RoomType, room_type_id)
        if room_type is None:
            raise ValueError("房型不存在")
        return room_type



    @staticmethod
    def _role(operator) -> str:
        if isinstance(operator, PlatformAdmin):
            return "平台管理员"
        if isinstance(operator, HotelStaff):
            return "酒店工作人员"
        raise PermissionError("无权执行房型与库存管理操作")
