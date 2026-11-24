"""重要操作日志写入与查询。"""
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from models.entities import OperationLog, PlatformAdmin, HotelStaff


class LogService:
    @staticmethod
    def record(session: Session, role: str, operator_id: int, action: str,
              detail: str = "", result: str = "成功") -> OperationLog:
        entry = OperationLog(operator_role=role, operator_id=operator_id,
                           action=action, detail=detail, result=result)
        session.add(entry)
        return entry


    @staticmethod
    def query(session: Session, operator, start: datetime = None, end: datetime = None,
              action: str = "", result: str = ""):
        if not isinstance(operator, (PlatformAdmin, HotelStaff)):
            raise PermissionError("无权查询操作日志")
        query = select(OperationLog).order_by(OperationLog.created_at.desc(), OperationLog.id.desc())
        if isinstance(operator, HotelStaff):
            query = query.where(OperationLog.operator_role == "酒店工作人员",
                             OperationLog.operator_id == operator.id)
        if start is not None:
            query = query.where(OperationLog.created_at >= start)
        if end is not None:
            query = query.where(OperationLog.created_at <= end)
        if action.strip():
            query = query.where(OperationLog.action.contains(action.strip()))
        if result.strip():
            query = query.where(OperationLog.result == result.strip())
        return list(session.scalars(query.limit(1000)))
