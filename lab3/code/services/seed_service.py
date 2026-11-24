"""开发环境初始账户创建。首次启动时创建演示管理员。"""
from sqlalchemy import select
from models.entities import PlatformAdmin
from services.auth_service import AuthService



def ensure_default_admin(session) -> bool:
    if session.scalar(select(PlatformAdmin).where(PlatformAdmin.username == "admin")):
        return False
    AuthService.create_admin(session, "admin", "admin123")
    session.commit()
    return True
