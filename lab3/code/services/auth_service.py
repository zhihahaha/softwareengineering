"""用户注册、认证及角色权限服务。"""
from sqlalchemy import select
from sqlalchemy.orm import Session
from models.entities import Customer, HotelStaff, PlatformAdmin
from services.security import hash_password, verify_password



class AuthService:
    ROLE_CUSTOMER = "顾客"
    ROLE_STAFF = "酒店工作人员"
    ROLE_ADMIN = "平台管理员"

    @staticmethod
    def register_customer(session: Session, username: str, password: str, phone: str = "") -> Customer:
        username = username.strip()
        if not username:
            raise ValueError("用户名不能为空")
        if session.scalar(select(Customer).where(Customer.username == username)):
            raise ValueError("用户名已存在")
        customer = Customer(username=username, password_hash=hash_password(password), phone=phone.strip())
        session.add(customer)
        session.flush()
        return customer

    @staticmethod
    def authenticate(session: Session, role: str, username: str, password: str):
        model_by_role = {
            AuthService.ROLE_CUSTOMER: Customer,
            AuthService.ROLE_STAFF: HotelStaff,
            AuthService.ROLE_ADMIN: PlatformAdmin,
        }
        model = model_by_role.get(role)
        if model is None:
            raise ValueError("未知用户角色")
        user = session.scalar(select(model).where(model.username == username.strip()))
        if user is None or not verify_password(password, user.password_hash):
            return None
        return user

    @staticmethod
    def create_staff(session: Session, username: str, password: str, hotel_id: int) -> HotelStaff:
        username = username.strip()
        if not username:
            raise ValueError("用户名不能为空")
        exists = session.scalar(select(HotelStaff).where(HotelStaff.username == username)
                                ) or session.scalar(select(Customer).where(Customer.username == username))
        exists = exists or session.scalar(select(PlatformAdmin).where(PlatformAdmin.username == username)
                                        )
        if exists:
            raise ValueError("用户名已存在")
        staff = HotelStaff(username=username, password_hash=hash_password(password), hotel_id=hotel_id)
        session.add(staff)
        session.flush()
        return staff

    @staticmethod
    def create_admin(session: Session, username: str, password: str) -> PlatformAdmin:
        username = username.strip()
        if not username:
            raise ValueError("用户名不能为空")
        if session.scalar(select(PlatformAdmin).where(PlatformAdmin.username == username)):
            raise ValueError("管理员用户名已存在")
        admin = PlatformAdmin(username=username, password_hash=hash_password(password))
        session.add(admin)
        session.flush()
        return admin
