"""M6 统计和 M7 操作日志服务测试。"""
from datetime import date, datetime, timedelta
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from models.base import Base
from models.entities import Hotel, RoomType, DailyInventory, Customer, PlatformAdmin, Order
from models.enums import HotelStatus, SaleStatus, OrderStatus
from services.statistics_service import StatisticsService
from services.log_service import LogService

@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    hotel = Hotel(name="统计测试酒店", city="东京", address="地址", status=HotelStatus.OPEN)
    db.add(hotel)
    db.flush()
    room = RoomType(hotel_id=hotel.id, name="标准房", capacity=2, sale_status=SaleStatus.ON_SALE)
    db.add(room)
    db.flush()
    db.add(DailyInventory(room_type_id=room.id, inventory_date=date(2032, 1, 1),
                         total_rooms=10, reserved_rooms=3, price=Decimal("120")))
    customer = Customer(username="test_customer", password_hash="x")
    admin = PlatformAdmin(username="test_admin", password_hash="x")
    db.add_all([customer, admin])
    db.flush()
    db.add(Order(order_number="TEST-001", customer_id=customer.id, hotel_id=hotel.id,
                room_type_id=room.id, check_in=date(2032, 1, 1), check_out=date(2032, 1, 2),
                guest_count=1, status=OrderStatus.PENDING, total_price=Decimal("120"),
                created_at=datetime(2032, 1, 1, 12, 0, 0)))
    db.commit()
    yield db, hotel, admin
    db.close()
    engine.dispose()

def test_hotel_daily_statistics(session):
    db, hotel, _ = session
    result = StatisticsService.hotel_daily(db, hotel.id, date(2032, 1, 1))
    assert result["total_rooms"] == 10
    assert result["reserved_rooms"] == 3
    assert result["remaining_rooms"] == 7

def test_platform_statistics(session):
    db, hotel, _ = session
    result = StatisticsService.platform_summary(db, date(2032, 1, 1), date(2032, 1, 1))
    assert result["hotel_total"] == 1
    assert result["open_hotel_total"] == 1
    assert result["order_total"] == 1

def test_statistics_reject_invalid_range(session):
    db, hotel, _ = session
    with pytest.raises(ValueError):
        StatisticsService.hotel_order_summary(db, hotel.id, date(2032, 1, 2), date(2032, 1, 1))
    with pytest.raises(ValueError):
        StatisticsService.platform_summary(db, date(2032, 1, 2), date(2032, 1, 1))

def test_admin_can_query_logs_and_action_filter(session):
    db, hotel, admin = session
    LogService.record(db, "平台管理员", admin.id, "酒店审核", "通过", "成功")
    db.commit()
    entries = LogService.query(db, admin, action="酒店审核")
    assert len(entries) == 1
    assert entries[0].result == "成功"

def test_customer_cannot_query_logs(session):
    db, hotel, _ = session
    customer = db.query(Customer).first()
    with pytest.raises(PermissionError):
        LogService.query(db, customer)

def test_hotel_order_summary_inclusive_calendar_dates(session):
    db, hotel, _ = session
    result = StatisticsService.hotel_order_summary(db, hotel.id, date(2032, 1, 1), date(2032, 1, 1))
    assert result["orders"] == 1
    assert result["cancelled"] == 0
