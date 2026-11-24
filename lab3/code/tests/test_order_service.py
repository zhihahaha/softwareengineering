"""订单服务测试。"""
from datetime import date, timedelta
from decimal import Decimal
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from models.base import Base
from models.entities import Customer, Hotel, HotelStaff, DailyInventory, RoomType, Order, OrderPriceDetail
from models.enums import HotelStatus, OrderStatus, SaleStatus
from services.security import hash_password
from services.order_service import OrderService


BASE = date(2031, 4, 1)


def setup_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    customer = Customer(username="customer", password_hash=hash_password("password123"))
    hotel = Hotel(name="测试酒店", city="东京", address="地址", status=HotelStatus.OPEN)
    session.add_all([customer, hotel])
    session.flush()
    staff = HotelStaff(username="staff", password_hash=hash_password("password123"), hotel_id=hotel.id)
    room = RoomType(hotel_id=hotel.id, name="标准双人房", capacity=2, sale_status=SaleStatus.ON_SALE)
    session.add_all([staff, room])
    session.flush()
    for offset in range(5):
        session.add(DailyInventory(room_type_id=room.id, inventory_date=BASE + timedelta(days=offset),
            total_rooms=2, reserved_rooms=0, price=Decimal("100") + offset * 10))
    session.commit()
    return session, customer, hotel, staff, room



def test_create_order_reserves_each_night_and_snapshots_price():
    session, customer, hotel, staff, room = setup_session()
    order = OrderService.create_order(session, customer, hotel.id, room.id, BASE, BASE + timedelta(days=3), 2)
    session.commit()
    assert order.status == OrderStatus.PENDING
    assert order.total_price == Decimal("330.00")
    details = session.scalars(select(OrderPriceDetail).where(OrderPriceDetail.order_id == order.id)).all()
    assert [d.nightly_price for d in details] == [Decimal("100"), Decimal("110"), Decimal("120")]
    assert [i.reserved_rooms for i in session.scalars(select(DailyInventory).order_by(DailyInventory.inventory_date)).all()[:3]] == [1, 1, 1]
    session.close()


def test_duplicate_active_order_rejected():
    session, customer, hotel, staff, room = setup_session()
    OrderService.create_order(session, customer, hotel.id, room.id, BASE, BASE + timedelta(days=2), 1)
    with pytest.raises(ValueError, match="重复预订"):
        OrderService.create_order(session, customer, hotel.id, room.id, BASE, BASE + timedelta(days=2), 1)
    session.close()



def test_sold_out_day_rolls_back_reservation_attempt():
    session, customer, hotel, staff, room = setup_session()
    day2 = session.scalar(select(DailyInventory).where(DailyInventory.inventory_date == BASE + timedelta(days=1)))
    day2.reserved_rooms = day2.total_rooms
    session.commit()
    with pytest.raises(ValueError, match="库存不足"):
        OrderService.create_order(session, customer, hotel.id, room.id, BASE, BASE + timedelta(days=3), 1)
    session.commit()
    day1 = session.scalar(select(DailyInventory).where(DailyInventory.inventory_date == BASE))
    assert day1.reserved_rooms == 0
    session.close()



def test_customer_cancel_releases_inventory_and_rejects_other_customer():
    session, customer, hotel, staff, room = setup_session()
    order = OrderService.create_order(session, customer, hotel.id, room.id, BASE, BASE + timedelta(days=2), 1)
    other = Customer(username="other", password_hash=hash_password("password123"))
    session.add(other)
    session.commit()
    with pytest.raises(PermissionError):
        OrderService.cancel_by_customer(session, other, order.id)
    OrderService.cancel_by_customer(session, customer, order.id)
    session.commit()
    assert order.status == OrderStatus.CANCELLED
    assert [i.reserved_rooms for i in session.scalars(select(DailyInventory).order_by(DailyInventory.inventory_date)).all()[:2]] == [0, 0]
    session.close()



def test_staff_order_lifecycle_and_wrong_hotel_permission():
    session, customer, hotel, staff, room = setup_session()
    order = OrderService.create_order(session, customer, hotel.id, room.id, BASE, BASE + timedelta(days=1), 1)
    session.commit()
    other_hotel = Hotel(name="其他酒店", city="大阪", address="地址", status=HotelStatus.OPEN)
    session.add(other_hotel)
    session.flush()
    wrong_staff = HotelStaff(username="otherstaff", password_hash=hash_password("password123"), hotel_id=other_hotel.id)
    session.add(wrong_staff)
    session.commit()
    with pytest.raises(PermissionError):
        OrderService.confirm_order(session, wrong_staff, order.id)
    OrderService.confirm_order(session, staff, order.id)
    assert order.status == OrderStatus.CONFIRMED
    OrderService.check_in(session, staff, order.id)
    assert order.status == OrderStatus.CHECKED_IN
    OrderService.check_out(session, staff, order.id)
    session.commit()
    assert order.status == OrderStatus.CHECKED_OUT
    with pytest.raises(ValueError):
        OrderService.check_out(session, staff, order.id)
    session.close()



def test_staff_can_cancel_pending_order_only_with_reason():
    session, customer, hotel, staff, room = setup_session()
    order = OrderService.create_order(session, customer, hotel.id, room.id, BASE, BASE + timedelta(days=2), 1)
    session.commit()
    with pytest.raises(ValueError, match="原因不能为空"):
        OrderService.cancel_by_staff(session, staff, order.id, "  ")
    OrderService.cancel_by_staff(session, staff, order.id, "酒店无法接待")
    session.commit()
    assert order.status == OrderStatus.CANCELLED
    session.close()



def test_modify_order_updates_inventory_and_price_details():
    session, customer, hotel, staff, room = setup_session()
    order = OrderService.create_order(session, customer, hotel.id, room.id, BASE, BASE + timedelta(days=2), 1)
    session.commit()
    new_in = BASE + timedelta(days=1)
    new_out = BASE + timedelta(days=3)
    OrderService.modify_order(session, customer, order.id, check_in=new_in, check_out=new_out, guest_count=2)
    session.commit()
    assert order.check_in == new_in
    assert order.check_out == new_out
    assert order.total_price == Decimal("230.00")
    inventories = session.scalars(select(DailyInventory).order_by(DailyInventory.inventory_date)).all()
    assert [i.reserved_rooms for i in inventories[:4]] == [0, 1, 1, 0]
    session.close()



def test_hotel_closed_or_room_off_sale_blocks_order():
    session, customer, hotel, staff, room = setup_session()
    hotel.status = HotelStatus.CLOSED
    session.commit()
    with pytest.raises(ValueError, match="不营业"):
        OrderService.create_order(session, customer, hotel.id, room.id, BASE, BASE + timedelta(days=1), 1)
    hotel.status = HotelStatus.OPEN
    room.sale_status = SaleStatus.OFF_SALE
    session.commit()
    with pytest.raises(ValueError, match="停售"):
        OrderService.create_order(session, customer, hotel.id, room.id, BASE, BASE + timedelta(days=1), 1)
    session.close()



def test_list_orders_scoped_by_role():
    session, customer, hotel, staff, room = setup_session()
    order = OrderService.create_order(session, customer, hotel.id, room.id, BASE, BASE + timedelta(days=1), 1)
    session.commit()
    assert [o.id for o in OrderService.list_orders(session, customer)] == [order.id]
    assert [o.id for o in OrderService.list_orders(session, staff)] == [order.id]
    session.close()


def test_checked_in_exact_duplicate_is_blocked():
    session, customer, hotel, staff, room = setup_session()
    order = OrderService.create_order(session, customer, hotel.id, room.id, BASE, BASE + timedelta(days=1), 1)
    OrderService.confirm_order(session, staff, order.id)
    OrderService.check_in(session, staff, order.id)
    session.commit()
    with pytest.raises(ValueError, match="重复预订"):
        OrderService.create_order(session, customer, hotel.id, room.id, BASE, BASE + timedelta(days=1), 1)
    session.close()


def test_failed_modify_keeps_original_order_and_inventory():
    session, customer, hotel, staff, room = setup_session()
    order = OrderService.create_order(session, customer, hotel.id, room.id, BASE, BASE + timedelta(days=2), 1)
    session.commit()
    # Mark the target night as fully occupied, so modification must fail.
    target = session.scalar(select(DailyInventory).where(DailyInventory.inventory_date == BASE + timedelta(days=3)))
    target.reserved_rooms = target.total_rooms
    session.commit()
    old_total = order.total_price
    with pytest.raises(ValueError, match="库存不足"):
        OrderService.modify_order(session, customer, order.id, check_in=BASE + timedelta(days=2),
                                 check_out=BASE + timedelta(days=4), guest_count=1)
    session.commit()
    assert order.check_in == BASE
    assert order.check_out == BASE + timedelta(days=2)
    assert order.total_price == old_total
    first_two = session.scalars(select(DailyInventory).where(DailyInventory.inventory_date < BASE + timedelta(days=2)).order_by(DailyInventory.inventory_date)).all()
    assert [item.reserved_rooms for item in first_two] == [1, 1]
    session.close()
