"""酒店查询服务测试。"""
from datetime import date, timedelta
from decimal import Decimal
import pytest



from sqlalchemy import create_engine
from sqlalchemy.orm import Session


from models.base import Base
from models.entities import DailyInventory, Hotel, RoomType
from models.enums import HotelStatus, SaleStatus
from services.search_service import HotelSearchService


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def seed(session, inventory_days=3, reserved_on=None, sold_out_on=None,
         status=HotelStatus.OPEN, sale_status=SaleStatus.ON_SALE):
    hotel = Hotel(name="示例酒店", city="东京", address="测试地址", phone="",
                 description="", status=status)
    session.add(hotel)
    session.flush()
    room = RoomType(hotel_id=hotel.id, name="双人房", capacity=2,
                   description="测试房型", sale_status=sale_status)
    session.add(room)
    session.flush()
    start = date(2030, 1, 1)
    for offset in range(inventory_days):
        day = start + timedelta(days=offset)
        reserved = 3 if sold_out_on == day else (1 if reserved_on == day else 0)
        session.add(DailyInventory(room_type_id=room.id, inventory_date=day,
            total_rooms=3, reserved_rooms=reserved, price=Decimal("100.00") + offset * 10))
    session.commit()
    return hotel, room



def test_search_returns_room_when_all_nights_have_inventory():
    session = make_session()
    seed(session)
    results = HotelSearchService.search(session, "东京", date(2030, 1, 1),
        date(2030, 1, 3), 2)
    assert len(results) == 1
    assert results[0].total_price == Decimal("210.00")
    assert results[0].minimum_available == 3
    session.close()



def test_checkout_date_inventory_is_not_required():
    session = make_session()
    seed(session, inventory_days=2)
    results = HotelSearchService.search(session, "", date(2030, 1, 1),
        date(2030, 1, 3), 1)
    assert len(results) == 1
    session.close()



def test_missing_night_inventory_excludes_room():
    session = make_session()
    seed(session, inventory_days=1)
    results = HotelSearchService.search(session, "", date(2030, 1, 1),
        date(2030, 1, 3), 1)
    assert results == []
    session.close()



def test_sold_out_night_excludes_room():
    session = make_session()
    seed(session, sold_out_on=date(2030, 1, 2))
    results = HotelSearchService.search(session, "", date(2030, 1, 1),
        date(2030, 1, 3), 1)
    assert results == []
    session.close()



def test_city_guest_capacity_and_price_filters():
    session = make_session()
    seed(session)
    assert len(HotelSearchService.search(session, "大阪", date(2030, 1, 1),
        date(2030, 1, 2), 1)) == 0
    assert len(HotelSearchService.search(session, "东京", date(2030, 1, 1),
        date(2030, 1, 2), 3)) == 0
    assert len(HotelSearchService.search(session, "东京", date(2030, 1, 1),
        date(2030, 1, 3), 2, min_price=105, max_price=105)) == 1
    session.close()



def test_closed_hotel_and_off_sale_room_not_in_results():
    session = make_session()
    seed(session, status=HotelStatus.CLOSED)
    assert HotelSearchService.search(session, "", date(2030, 1, 1),
        date(2030, 1, 2), 1) == []
    session.close()

    session = make_session()
    seed(session, sale_status=SaleStatus.OFF_SALE)
    assert HotelSearchService.search(session, "", date(2030, 1, 1),
        date(2030, 1, 2), 1) == []
    session.close()



def test_invalid_search_parameters_raise_value_error():
    session = make_session()
    seed(session)
    with pytest.raises(ValueError):
        HotelSearchService.search(session, "", date(2030, 1, 2), date(2030, 1, 2), 1)
    with pytest.raises(ValueError):
        HotelSearchService.search(session, "", date(2030, 1, 1), date(2030, 1, 2), 0)
    with pytest.raises(ValueError):
        HotelSearchService.search(session, "", date(2030, 1, 1), date(2030, 1, 2), 1,
                                min_price=300, max_price=100)
    session.close()
