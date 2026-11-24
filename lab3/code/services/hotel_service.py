"""酒店信息管理与角色授权。"""
from sqlalchemy import select
from sqlalchemy.orm import Session
from models.entities import Hotel, HotelStaff, PlatformAdmin
from models.enums import HotelStatus
from services.log_service import LogService



class HotelService:
    @staticmethod
    def list_hotels(session: Session, city: str = "", include_closed: bool = True):
        query = select(Hotel).order_by(Hotel.id)
        if city.strip():
            query = query.where(Hotel.city.contains(city.strip()))
        if not include_closed:
            query = query.where(Hotel.status == HotelStatus.OPEN)
        return list(session.scalars(query))

    @staticmethod
    def create_hotel(session: Session, operator: PlatformAdmin, name: str, city: str,
                     address: str, phone: str = "", description: str = "") -> Hotel:
        HotelService._require_admin(operator)
        if not name.strip() or not city.strip() or not address.strip():
            raise ValueError("酒店名称、城市和地址不能为空")
        hotel = Hotel(name=name.strip(), city=city.strip(), address=address.strip(),
                     phone=phone.strip(), description=description.strip(),
                     status=HotelStatus.PENDING)
        session.add(hotel)
        session.flush()
        LogService.record(session, "平台管理员", operator.id, "创建酒店", f"酒店ID={hotel.id}，名称={hotel.name}")
        return hotel


    @staticmethod
    def update_hotel(session: Session, operator, hotel_id: int, **changes) -> Hotel:
        hotel = HotelService._get_hotel(session, hotel_id)
        HotelService._authorize_hotel(operator, hotel)
        allowed = {"name", "city", "address", "phone", "description"}
        for key, value in changes.items():
            if key in allowed:
                if key in {"name", "city", "address"} and not str(value).strip():
                    raise ValueError(f"{key}不能为空")
                setattr(hotel, key, value.strip() if isinstance(value, str) else value)
        LogService.record(session, HotelService._role(operator), operator.id, "修改酒店信息",
                         f"酒店ID={hotel.id}")
        return hotel


    @staticmethod
    def set_status(session: Session, operator: PlatformAdmin, hotel_id: int,
                   status: HotelStatus, reason: str = "") -> Hotel:
        HotelService._require_admin(operator)
        hotel = HotelService._get_hotel(session, hotel_id)
        hotel.status = status
        LogService.record(session, "平台管理员", operator.id, "修改酒店状态",
                         f"酒店ID={hotel.id}，状态={status.value}，原因={reason}")
        return hotel


    @staticmethod
    def _get_hotel(session: Session, hotel_id: int) -> Hotel:
        hotel = session.get(Hotel, hotel_id)
        if hotel is None:
            raise ValueError("酒店不存在")
        return hotel



    @staticmethod
    def _role(operator) -> str:
        if isinstance(operator, PlatformAdmin):
            return "平台管理员"
        if isinstance(operator, HotelStaff):
            return "酒店工作人员"
        raise PermissionError("无权执行酒店管理操作")


    @staticmethod
    def _require_admin(operator) -> None:
        if not isinstance(operator, PlatformAdmin):
            raise PermissionError("该操作仅平台管理员可执行")


    @staticmethod
    def _authorize_hotel(operator, hotel: Hotel) -> None:
        if isinstance(operator, PlatformAdmin):
            return
        if isinstance(operator, HotelStaff) and operator.hotel_id == hotel.id:
            return
        raise PermissionError("无权管理该酒店")
