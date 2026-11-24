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
