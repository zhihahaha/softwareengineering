"""订单管理服务：创建、修改、取消、确认、入住及退房。"""
from datetime import date, datetime, timedelta
from decimal import Decimal
import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from models.entities import DailyInventory, Hotel, HotelStaff, PlatformAdmin, Customer, RoomType, Order, OrderPriceDetail
from models.enums import HotelStatus, OrderStatus, SaleStatus
from services.hotel_service import HotelService
from services.log_service import LogService


class OrderService:
    """负责订单业务规则；库存变更由本服务调用数据库原子更新完成。"""

    ACTIVE_DUPLICATE_STATUSES = (OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.CHECKED_IN)
    INVENTORY_HOLD_STATUSES = (OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.CHECKED_IN)



    @staticmethod
    def create_order(session: Session, customer: Customer, hotel_id: int, room_type_id: int,
                    check_in: date, check_out: date, guest_count: int) -> Order:
        if not isinstance(customer, Customer):
            raise PermissionError("只有顾客可以创建订单")
        OrderService._validate_dates(check_in, check_out)
        if not isinstance(guest_count, int) or guest_count <= 0:
            raise ValueError("入住人数必须为正整数")
        hotel = session.get(Hotel, hotel_id)
        room = session.get(RoomType, room_type_id)
        if hotel is None:
            raise ValueError("酒店不存在")
        if room is None or room.hotel_id != hotel_id:
            raise ValueError("房型不属于所选酒店")
        if hotel.status != HotelStatus.OPEN:
            raise ValueError("酒店当前不营业，无法预订")
        if room.sale_status != SaleStatus.ON_SALE:
            raise ValueError("房型当前停售，无法预订")
        if room.capacity < guest_count:
            raise ValueError("房型可入住人数不足")
        duplicate = session.scalar(select(Order).where(
            Order.customer_id == customer.id,
            Order.room_type_id == room_type_id,
            Order.check_in == check_in,
            Order.check_out == check_out,
            Order.status.in_(OrderService.ACTIVE_DUPLICATE_STATUSES),
        ))
        if duplicate:
            raise ValueError("相同房型和日期已有有效订单，不能重复预订")
        with session.begin_nested():
            prices = OrderService._reserve_inventory(session, room.id, check_in, check_out)
            total = sum(prices.values(), Decimal("0.00"))
            order = Order(
                order_number=f"HB-{datetime.now():%Y%m%d%H%M%S}-{uuid.uuid4().hex[:6].upper()}",
                customer_id=customer.id, hotel_id=hotel_id, room_type_id=room.id,
                check_in=check_in, check_out=check_out, guest_count=guest_count,
                status=OrderStatus.PENDING, total_price=total,
            )
            session.add(order)
            session.flush()
            for stay_date, nightly_price in prices.items():
                session.add(OrderPriceDetail(order_id=order.id, stay_date=stay_date,
                                           nightly_price=nightly_price))
            LogService.record(session, "顾客", customer.id, "创建订单",
                             f"订单号={order.order_number}，酒店ID={hotel_id}，房型ID={room.id}，价格={total}")
            session.flush()
        return order



    @staticmethod
    def list_orders(session: Session, operator, hotel_id=None):
        query = select(Order).order_by(Order.created_at.desc(), Order.id.desc())
        if isinstance(operator, Customer):
            query = query.where(Order.customer_id == operator.id)
        elif isinstance(operator, HotelStaff):
            query = query.where(Order.hotel_id == operator.hotel_id)
        elif isinstance(operator, PlatformAdmin):
            if hotel_id is not None:
                query = query.where(Order.hotel_id == hotel_id)
        else:
            raise PermissionError("无权查询订单")
        return list(session.scalars(query))



    @staticmethod
    def cancel_by_customer(session: Session, customer: Customer, order_id: int) -> Order:
        order = OrderService._get_order(session, order_id)
        if order.customer_id != customer.id:
            raise PermissionError("只能取消自己的订单")
        if order.status not in (OrderStatus.PENDING, OrderStatus.CONFIRMED):
            raise ValueError("当前订单状态不允许取消")
        with session.begin_nested():
            OrderService._release_inventory(session, order.room_type_id, order.check_in, order.check_out)
            order.status = OrderStatus.CANCELLED
            LogService.record(session, "顾客", customer.id, "取消订单", f"订单号={order.order_number}")
            session.flush()
        return order



    @staticmethod
    def cancel_by_staff(session: Session, staff: HotelStaff, order_id: int, reason: str) -> Order:
        order = OrderService._get_order(session, order_id)
        if order.hotel_id != staff.hotel_id:
            raise PermissionError("只能处理所属酒店订单")
        if order.status != OrderStatus.PENDING:
            raise ValueError("工作人员只能取消待确认订单")
        if not reason.strip():
            raise ValueError("取消原因不能为空")
        with session.begin_nested():
            OrderService._release_inventory(session, order.room_type_id, order.check_in, order.check_out)
            order.status = OrderStatus.CANCELLED
            LogService.record(session, "酒店工作人员", staff.id, "工作人员取消订单",
                             f"订单号={order.order_number}，原因={reason.strip()}")
            session.flush()
        return order



    @staticmethod
    def confirm_order(session: Session, staff: HotelStaff, order_id: int) -> Order:
        order = OrderService._get_order(session, order_id)
        OrderService._authorize_staff_order(staff, order)
        if order.status != OrderStatus.PENDING:
            raise ValueError("只有待确认订单可以确认")
        order.status = OrderStatus.CONFIRMED
        LogService.record(session, "酒店工作人员", staff.id, "确认订单", f"订单号={order.order_number}")
        session.flush()
        return order



    @staticmethod
    def check_in(session: Session, staff: HotelStaff, order_id: int) -> Order:
        order = OrderService._get_order(session, order_id)
        OrderService._authorize_staff_order(staff, order)
        if order.status != OrderStatus.CONFIRMED:
            raise ValueError("只有已确认订单可以办理入住")
        order.status = OrderStatus.CHECKED_IN
        LogService.record(session, "酒店工作人员", staff.id, "办理入住", f"订单号={order.order_number}")
        session.flush()
        return order



    @staticmethod
    def check_out(session: Session, staff: HotelStaff, order_id: int) -> Order:
        order = OrderService._get_order(session, order_id)
        OrderService._authorize_staff_order(staff, order)
        if order.status != OrderStatus.CHECKED_IN:
            raise ValueError("只有已入住订单可以办理退房")
        order.status = OrderStatus.CHECKED_OUT
        LogService.record(session, "酒店工作人员", staff.id, "办理退房", f"订单号={order.order_number}")
        session.flush()
        return order



    @staticmethod
    def modify_order(session: Session, customer: Customer, order_id: int, *,
                    check_in: date, check_out: date, guest_count: int) -> Order:
        order = OrderService._get_order(session, order_id)
        if order.customer_id != customer.id:
            raise PermissionError("只能修改自己的订单")
        if order.status not in (OrderStatus.PENDING, OrderStatus.CONFIRMED):
            raise ValueError("当前订单状态不允许修改")
        OrderService._validate_dates(check_in, check_out)
        if not isinstance(guest_count, int) or guest_count <= 0:
            raise ValueError("入住人数必须为正整数")
        room = session.get(RoomType, order.room_type_id)
        hotel = session.get(Hotel, order.hotel_id)
        if hotel.status != HotelStatus.OPEN:
            raise ValueError("酒店当前不营业，无法修改订单")
        if room.sale_status != SaleStatus.ON_SALE:
            raise ValueError("房型当前停售，无法修改订单")
        if room.capacity < guest_count:
            raise ValueError("房型可入住人数不足")
        duplicate = session.scalar(select(Order).where(
            Order.customer_id == customer.id, Order.room_type_id == order.room_type_id,
            Order.check_in == check_in, Order.check_out == check_out,
            Order.status.in_(OrderService.ACTIVE_DUPLICATE_STATUSES), Order.id != order.id,
        ))
        if duplicate:
            raise ValueError("修改后与其他有效订单重复")
        with session.begin_nested():
            OrderService._release_inventory(session, order.room_type_id, order.check_in, order.check_out)
            prices = OrderService._reserve_inventory(session, order.room_type_id, check_in, check_out)
            order.check_in = check_in
            order.check_out = check_out
            order.guest_count = guest_count
            order.total_price = sum(prices.values(), Decimal("0.00"))
            order.price_details.clear()
            session.flush()
            for stay_date, nightly_price in prices.items():
                session.add(OrderPriceDetail(order_id=order.id, stay_date=stay_date,
                                           nightly_price=nightly_price))
            LogService.record(session, "顾客", customer.id, "修改订单",
                             f"订单号={order.order_number}，新日期={check_in}至{check_out}，人数={guest_count}")
            session.flush()
        return order



    @staticmethod
    def _reserve_inventory(session: Session, room_type_id: int, check_in: date,
                          check_out: date) -> dict[date, Decimal]:
        prices = {}
        current = check_in
        while current < check_out:
            inventory = session.scalar(select(DailyInventory).where(
                DailyInventory.room_type_id == room_type_id,
                DailyInventory.inventory_date == current,
            ))
            if inventory is None:
                raise ValueError(f"{current} 未配置库存")
            result = session.execute(update(DailyInventory).where(
                DailyInventory.id == inventory.id,
                DailyInventory.reserved_rooms < DailyInventory.total_rooms,
            ).values(reserved_rooms=DailyInventory.reserved_rooms + 1))
            if result.rowcount != 1:
                raise ValueError(f"{current} 房间库存不足")
            prices[current] = Decimal(inventory.price)
            current += timedelta(days=1)
        return prices



    @staticmethod
    def _release_inventory(session: Session, room_type_id: int, check_in: date,
                         check_out: date) -> None:
        current = check_in
        while current < check_out:
            result = session.execute(update(DailyInventory).where(
                DailyInventory.room_type_id == room_type_id,
                DailyInventory.inventory_date == current,
                DailyInventory.reserved_rooms > 0,
            ).values(reserved_rooms=DailyInventory.reserved_rooms - 1))
            if result.rowcount != 1:
                raise ValueError(f"{current} 库存释放失败，库存数据异常")
            current += timedelta(days=1)



    @staticmethod
    def _authorize_staff_order(staff: HotelStaff, order: Order) -> None:
        if staff.hotel_id != order.hotel_id:
            raise PermissionError("只能处理所属酒店订单")



    @staticmethod
    def _get_order(session: Session, order_id: int) -> Order:
        order = session.get(Order, order_id)
        if order is None:
            raise ValueError("订单不存在")
        return order



    @staticmethod
    def _validate_dates(check_in: date, check_out: date) -> None:
        if not isinstance(check_in, date) or not isinstance(check_out, date):
            raise ValueError("入住日期和退房日期无效")
        if check_in >= check_out:
            raise ValueError("退房日期必须晚于入住日期")
