"""房型与库存管理服务测试。"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.base import Base
from models.entities import DailyInventory, Hotel, RoomType
from models.enums import HotelStatus, SaleStatus
from services.auth_service import AuthService
from services.hotel_service import HotelService
from services.room_service import RoomService


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    yield db
    db.close()
    engine.dispose()


@pytest.fixture
def actors_and_hotel(session):
    admin = AuthService.create_admin(session, "admin", "admin123")
    hotel = HotelService.create_hotel(session, admin, "测试酒店", "东京", "测试地址")
    HotelService.set_status(session, admin, hotel.id, HotelStatus.OPEN)
    staff = AuthService.create_staff(session, "staff", "staff123", hotel.id)
    session.commit()
    return admin, staff, hotel



def test_staff_can_create_room_type(session, actors_and_hotel):
    _, staff, hotel = actors_and_hotel
    room = RoomService.create_room_type(session, staff, hotel.id, "标准双人间", 2, "测试房型")
    session.commit()
    assert room.name == "标准双人间"
    assert room.capacity == 2
    assert room.sale_status == SaleStatus.ON_SALE



def test_customer_cannot_create_room_type(session, actors_and_hotel):
    _, _, hotel = actors_and_hotel
    customer = AuthService.register_customer(session, "guest", "guest123")
    with pytest.raises(PermissionError):
        RoomService.create_room_type(session, customer, hotel.id, "标准间", 2)



def test_staff_cannot_manage_room_type_in_other_hotel(session, actors_and_hotel):
    admin, staff, _ = actors_and_hotel
    other = HotelService.create_hotel(session, admin, "另一家酒店", "大阪", "另一个地址")
    room = RoomService.create_room_type(session, admin, other.id, "豪华间", 3)
    with pytest.raises(PermissionError):
        RoomService.update_room_type(session, staff, room.id, name="越权修改")



def test_batch_inventory_and_availability(session, actors_and_hotel):
    _, staff, hotel = actors_and_hotel
    room = RoomService.create_room_type(session, staff, hotel.id, "大床房", 2)
    first = date(2026, 12, 1)
    records = RoomService.set_inventory_range(session, staff, room.id, first,
                                             first + timedelta(days=2), 5, "299.50")
    session.commit()
    assert len(records) == 3
    assert RoomService.get_availability(session, room.id, first) == 5
    assert RoomService.get_availability(session, room.id, first + timedelta(days=1)) == 5
    assert records[0].price == Decimal("299.50")



def test_inventory_range_invalid_values(session, actors_and_hotel):
    _, staff, hotel = actors_and_hotel
    room = RoomService.create_room_type(session, staff, hotel.id, "大床房", 2)
    today = date.today()
    with pytest.raises(ValueError):
        RoomService.set_inventory_range(session, staff, room.id, today,
                                        today - timedelta(days=1), 2, 100)
    with pytest.raises(ValueError):
        RoomService.set_inventory_range(session, staff, room.id, today, today, -1, 100)
    with pytest.raises(ValueError):
        RoomService.set_inventory_range(session, staff, room.id, today, today, 2, -10)



def test_inventory_cannot_be_reduced_below_reserved(session, actors_and_hotel):
    _, staff, hotel = actors_and_hotel
    room = RoomService.create_room_type(session, staff, hotel.id, "大床房", 2)
    day = date(2026, 12, 5)
    RoomService.set_inventory_range(session, staff, room.id, day, day, 4, 200)
    inventory = session.query(DailyInventory).filter_by(room_type_id=room.id).one()
    inventory.reserved_rooms = 3
    session.commit()
    with pytest.raises(ValueError):
        RoomService.set_inventory_range(session, staff, room.id, day, day, 2, 180)
    session.rollback()
    assert inventory.total_rooms == 4



def test_off_sale_room_has_zero_availability(session, actors_and_hotel):
    _, staff, hotel = actors_and_hotel
    room = RoomService.create_room_type(session, staff, hotel.id, "套房", 4)
    day = date(2026, 12, 10)
    RoomService.set_inventory_range(session, staff, room.id, day, day, 3, 500)
    RoomService.set_sale_status(session, staff, room.id, SaleStatus.OFF_SALE)
    session.commit()
    assert RoomService.get_availability(session, room.id, day) == 0



def test_room_type_list_filter(session, actors_and_hotel):
    _, staff, hotel = actors_and_hotel
    room = RoomService.create_room_type(session, staff, hotel.id, "经济房", 1)
    RoomService.set_sale_status(session, staff, room.id, SaleStatus.OFF_SALE)
    session.commit()
    assert len(RoomService.list_room_types(session, hotel.id)) == 1
    assert RoomService.list_room_types(session, hotel.id, include_off_sale=False) == []
