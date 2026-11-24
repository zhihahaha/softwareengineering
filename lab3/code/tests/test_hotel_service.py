"""酒店服务授权及状态操作测试。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.base import Base
from models.entities import Customer, PlatformAdmin
from models.enums import HotelStatus
from services.auth_service import AuthService
from services.hotel_service import HotelService

@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    yield db
    db.close()
    engine.dispose()

def test_admin_create_and_approve_hotel(session):
    admin = AuthService.create_admin(session, "admin", "admin123")
    hotel = HotelService.create_hotel(session, admin, "测试酒店", "东京", "东京某地址")
    assert hotel.status == HotelStatus.PENDING
    HotelService.set_status(session, admin, hotel.id, HotelStatus.OPEN)
    session.commit()
    assert hotel.status == HotelStatus.OPEN

def test_non_admin_cannot_create_hotel(session):
    customer = AuthService.register_customer(session, "user1", "secret123")
    with pytest.raises(PermissionError):
        HotelService.create_hotel(session, customer, "测试酒店", "东京", "地址")

def test_staff_cannot_manage_other_hotel(session):
    admin = AuthService.create_admin(session, "admin", "admin123")
    hotel_a = HotelService.create_hotel(session, admin, "A酒店", "东京", "A地址")
    hotel_b = HotelService.create_hotel(session, admin, "B酒店", "大阪", "B地址")
    staff = AuthService.create_staff(session, "staff1", "staff123", hotel_a.id)
    with pytest.raises(PermissionError):
        HotelService.update_hotel(session, staff, hotel_b.id, name="越权修改")
