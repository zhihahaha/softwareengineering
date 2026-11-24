"""项目配置。"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "hotel_booking.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"
APP_NAME = "酒店预订系统"
