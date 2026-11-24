"""顾客酒店查询服务。"""
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.entities import DailyInventory, Hotel, RoomType
from models.enums import HotelStatus, SaleStatus


@dataclass(frozen=True)
class HotelSearchResult:
    """一个符合查询条件的酒店房型及住宿价格结果。"""
    hotel: Hotel
    room_type: RoomType
    nightly_prices: tuple[Decimal, ...]
    total_price: Decimal
    minimum_available: int

    @property
    def average_nightly_price(self) -> Decimal:
        return self.total_price / len(self.nightly_prices)



class HotelSearchService:
    """按查询条件筛选营业酒店、在售房型及连续住宿库存。"""


    @staticmethod
    def search(session: Session, city: str, check_in: date, check_out: date,
               guests: int, room_type_name: str = "", min_price=None,
               max_price=None) -> list[HotelSearchResult]:
        if check_in >= check_out:
            raise ValueError("退房日期必须晚于入住日期")
        if not isinstance(guests, int) or guests <= 0:
            raise ValueError("入住人数必须为正整数")
        min_value = HotelSearchService._price_value(min_price, "最低价格")
        max_value = HotelSearchService._price_value(max_price, "最高价格")
        if min_value is not None and max_value is not None and min_value > max_value:
            raise ValueError("最低价格不能大于最高价格")

        query = (select(Hotel, RoomType)
                 .join(RoomType, RoomType.hotel_id == Hotel.id)
                 .where(Hotel.status == HotelStatus.OPEN,
                        RoomType.sale_status == SaleStatus.ON_SALE,
                        RoomType.capacity >= guests)
                 .order_by(Hotel.city, Hotel.name, RoomType.name))
        city_text = (city or "").strip()
        if city_text:
            query = query.where(Hotel.city.ilike(f"%{city_text}%"))
        type_text = (room_type_name or "").strip()
        if type_text:
            query = query.where(RoomType.name.ilike(f"%{type_text}%"))

        results = []
        stay_dates = []
        current = check_in
        while current < check_out:
            stay_dates.append(current)
            current += timedelta(days=1)

        for hotel, room_type in session.execute(query):
            inventories = session.scalars(select(DailyInventory).where(
                DailyInventory.room_type_id == room_type.id,
                DailyInventory.inventory_date >= check_in,
                DailyInventory.inventory_date < check_out,
            ).order_by(DailyInventory.inventory_date)).all()
            inventory_by_date = {item.inventory_date: item for item in inventories}
            # 必须每一晚都配置库存且有空房；缺失日期也视为不可预订。
            if any(day not in inventory_by_date for day in stay_dates):
                continue
            selected = [inventory_by_date[day] for day in stay_dates]
            remaining_each_day = [item.total_rooms - item.reserved_rooms for item in selected]
            if any(count <= 0 for count in remaining_each_day):
                continue
            prices = tuple(Decimal(item.price) for item in selected)
            total = sum(prices, Decimal("0.00"))
            average = total / len(prices)
            if min_value is not None and average < min_value:
                continue
            if max_value is not None and average > max_value:
                continue
            results.append(HotelSearchResult(
                hotel=hotel,
                room_type=room_type,
                nightly_prices=prices,
                total_price=total,
                minimum_available=min(remaining_each_day),
            ))
        return results


    @staticmethod
    def _price_value(value, label: str) -> Optional[Decimal]:
        if value is None or str(value).strip() == "":
            return None
        try:
            converted = Decimal(str(value))
        except Exception:
            raise ValueError(f"{label}格式无效") from None
        if not converted.is_finite() or converted < 0:
            raise ValueError(f"{label}不能为负数")
        return converted
