"""酒店预订系统应用入口。"""

import sys

from PySide6.QtWidgets import QApplication

from database.db import initialize_database, get_session
from ui.main_window import MainWindow
from services.seed_service import ensure_default_admin


def main() -> int:
    """初始化数据库并启动桌面应用。"""
    initialize_database()
    seed_session = get_session()
    try:
        ensure_default_admin(seed_session)
    finally:
        seed_session.close()

    app = QApplication(sys.argv)
    app.setApplicationName("酒店预订系统")
    app.setOrganizationName("HotelBookingCourseProject")

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
