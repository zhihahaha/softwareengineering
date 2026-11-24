"""用户注册与认证测试。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.base import Base
from services.auth_service import AuthService

@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    db = factory()
    yield db
    db.close()
    engine.dispose()

def test_customer_register_and_authenticate(session):
    customer = AuthService.register_customer(session, "alice", "secret123", "123")
    session.commit()
    assert customer.password_hash != "secret123"
    assert AuthService.authenticate(session, AuthService.ROLE_CUSTOMER, "alice", "secret123")
    assert AuthService.authenticate(session, AuthService.ROLE_CUSTOMER, "alice", "wrong") is None

def test_duplicate_customer_username_rejected(session):
    AuthService.register_customer(session, "alice", "secret123")
    with pytest.raises(ValueError, match="用户名已存在"):
        AuthService.register_customer(session, "alice", "secret123")

def test_short_password_rejected(session):
    with pytest.raises(ValueError, match="至少需要6个字符"):
        AuthService.register_customer(session, "alice", "123")


def test_platform_admin_can_create_staff_bound_to_hotel(session):
    from models.entities import Hotel
    from models.enums import HotelStatus

    hotel = Hotel(name="测试酒店", city="测试城市", address="测试地址", status=HotelStatus.OPEN)
    session.add(hotel)
    session.flush()

    staff = AuthService.create_staff(session, "hotel_staff_1", "staff123", hotel.id)
    session.commit()

    assert staff.hotel_id == hotel.id
    assert AuthService.authenticate(session, AuthService.ROLE_STAFF, "hotel_staff_1", "staff123") is not None
    assert AuthService.authenticate(session, AuthService.ROLE_STAFF, "hotel_staff_1", "wrong") is None


def test_staff_username_conflicts_across_roles(session):
    from models.entities import Hotel
    from models.enums import HotelStatus



    hotel = Hotel(name="测试酒店", city="测试城市", address="测试地址", status=HotelStatus.OPEN)
    session.add(hotel)
    session.flush()
    AuthService.register_customer(session, "shared_username", "customer123")

    with pytest.raises(ValueError, match="用户名已存在"):
        AuthService.create_staff(session, "shared_username", "staff123", hotel.id)
