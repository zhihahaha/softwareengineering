"""系统主窗口，第一阶段提供账户注册/登录和酒店管理入口。"""
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QTabWidget, QDialog,
    QTextEdit, QVBoxLayout, QWidget, QDateEdit, QSpinBox, QDoubleSpinBox, QInputDialog,
)
from database.db import get_session
from models.entities import PlatformAdmin, HotelStaff
from models.enums import HotelStatus, SaleStatus
from models.entities import Hotel
from services.room_service import RoomService
from services.search_service import HotelSearchService
from datetime import date, datetime, timedelta
from services.auth_service import AuthService
from services.hotel_service import HotelService
from services.order_service import OrderService
from models.entities import Customer, Order
from models.enums import OrderStatus
from services.seed_service import ensure_default_admin
from services.statistics_service import StatisticsService
from services.log_service import LogService



class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("酒店预订系统")
        self.resize(1000, 680)
        self.current_operator = None
        self.current_role = ""
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.tabs.addTab(self._build_account_page(), "账户注册 / 登录")
        self.tabs.addTab(self._build_hotel_page(), "酒店管理")
        self.tabs.addTab(self._build_room_page(), "房型与库存")
        self.tabs.addTab(self._build_search_page(), "酒店查询")
        self.tabs.addTab(self._build_order_page(), "订单管理")
        self.tabs.addTab(self._build_statistics_page(), "统计")
        self.tabs.addTab(self._build_log_page(), "操作日志")
        self.tabs.addTab(self._build_platform_page(), "平台管理")
        self.statusBar().showMessage("请先登录。演示管理员：admin / admin123")
        self._refresh_hotels()


    def _build_account_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        self.reg_username = QLineEdit()
        self.reg_password = QLineEdit()
        self.reg_password.setEchoMode(QLineEdit.Password)
        self.reg_phone = QLineEdit()
        form.addRow("用户名", self.reg_username)
        form.addRow("密码（至少6位）", self.reg_password)
        form.addRow("手机号（选填）", self.reg_phone)
        register_btn = QPushButton("注册顾客账户")
        register_btn.clicked.connect(self._register_customer)
        layout.addLayout(form)
        layout.addWidget(register_btn)
        layout.addWidget(QLabel("登录"))
        login_form = QFormLayout()
        self.login_role = QComboBox()
        self.login_role.addItems([AuthService.ROLE_CUSTOMER, AuthService.ROLE_STAFF,
                                 AuthService.ROLE_ADMIN])
        self.login_username = QLineEdit()
        self.login_password = QLineEdit()
        self.login_password.setEchoMode(QLineEdit.Password)
        login_form.addRow("角色", self.login_role)
        login_form.addRow("用户名", self.login_username)
        login_form.addRow("密码", self.login_password)
        login_btn = QPushButton("登录")
        login_btn.clicked.connect(self._login)
        layout.addLayout(login_form)
        layout.addWidget(login_btn)
        layout.addStretch()
        return page



    def _build_search_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QHBoxLayout()
        self.search_city = QLineEdit()
        self.search_city.setPlaceholderText("城市（可选）")
        self.search_check_in = QDateEdit()
        self.search_check_in.setCalendarPopup(True)
        self.search_check_in.setDate(date.today())
        self.search_check_out = QDateEdit()
        self.search_check_out.setCalendarPopup(True)
        self.search_check_out.setDate(self.search_check_in.date().addDays(1))
        self.search_guests = QSpinBox()
        self.search_guests.setRange(1, 20)
        self.search_guests.setValue(1)
        self.search_room_name = QLineEdit()
        self.search_room_name.setPlaceholderText("房型名称（可选）")
        self.search_min_price = QDoubleSpinBox()
        self.search_min_price.setRange(0, 10000000)
        self.search_min_price.setDecimals(2)
        self.search_min_price.setSpecialValueText("不限")
        self.search_max_price = QDoubleSpinBox()
        self.search_max_price.setRange(0, 10000000)
        self.search_max_price.setDecimals(2)
        self.search_max_price.setSpecialValueText("不限")
        form.addWidget(QLabel("城市"))
        form.addWidget(self.search_city)
        form.addWidget(QLabel("入住"))
        form.addWidget(self.search_check_in)
        form.addWidget(QLabel("退房"))
        form.addWidget(self.search_check_out)
        form.addWidget(QLabel("人数"))
        form.addWidget(self.search_guests)
        form.addWidget(QLabel("房型"))
        form.addWidget(self.search_room_name)
        form.addWidget(QLabel("最低均价"))
        form.addWidget(self.search_min_price)
        form.addWidget(QLabel("最高均价"))
        form.addWidget(self.search_max_price)
        search_btn = QPushButton("查询酒店")
        search_btn.clicked.connect(self._run_hotel_search)
        form.addWidget(search_btn)
        layout.addLayout(form)
        self.search_results_table = QTableWidget(0, 8)
        self.search_results_table.setHorizontalHeaderLabels([
            "酒店", "城市", "地址", "房型", "入住人数", "每晚均价", "住宿总价", "最少剩余房间"
        ])
        self.search_results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.search_results = []
        self.search_results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.search_results_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.search_results_table)
        order_button = QPushButton("预订选中房型")
        order_button.clicked.connect(self._create_order_from_search)
        layout.addWidget(order_button)
        self.search_summary = QLabel("输入查询条件后点击‘查询酒店’。价格筛选按照住宿期间平均每晚价格计算。")
        self.search_summary.setWordWrap(True)
        layout.addWidget(self.search_summary)
        return page

    def _run_hotel_search(self):
        check_in = self.search_check_in.date().toPython()
        check_out = self.search_check_out.date().toPython()
        if check_in >= check_out:
            QMessageBox.warning(self, "日期错误", "退房日期必须晚于入住日期。")
            return
        min_price = self.search_min_price.value() if self.search_min_price.value() > 0 else None
        max_price = self.search_max_price.value() if self.search_max_price.value() > 0 else None
        session = get_session()
        try:
            results = HotelSearchService.search(
                session, self.search_city.text(), check_in, check_out,
                self.search_guests.value(), self.search_room_name.text(),
                min_price, max_price,
            )
            self.search_results = results
            self.search_results_table.setRowCount(len(results))
            for row, result in enumerate(results):
                values = [
                    result.hotel.name, result.hotel.city, result.hotel.address,
                    result.room_type.name, result.room_type.capacity,
                    f"{result.average_nightly_price:.2f}",
                    f"{result.total_price:.2f}", result.minimum_available,
                ]
                for col, value in enumerate(values):
                    self.search_results_table.setItem(row, col, QTableWidgetItem(str(value)))
            self.search_results_table.resizeColumnsToContents()
            nights = (check_out - check_in).days
            self.search_summary.setText(
                f"查询完成：{len(results)} 条房型结果；住宿 {nights} 晚。"
                "价格筛选采用住宿期间平均每晚价格；最少剩余房间数为各入住日剩余量的最小值。"
            )
        except Exception as exc:
            QMessageBox.warning(self, "查询失败", str(exc))
        finally:
            session.close()

    def _build_order_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.order_table = QTableWidget(0, 9)
        self.order_table.setHorizontalHeaderLabels([
            "订单ID", "订单号", "酒店ID", "房型ID", "入住", "退房", "人数", "总价", "状态"
        ])
        self.order_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.order_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.order_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.order_table)
        buttons = QHBoxLayout()
        refresh_btn = QPushButton("刷新订单")
        refresh_btn.clicked.connect(self._refresh_orders)
        cancel_btn = QPushButton("取消订单")
        cancel_btn.clicked.connect(self._cancel_selected_order)
        confirm_btn = QPushButton("确认订单")
        confirm_btn.clicked.connect(lambda: self._order_action(OrderService.confirm_order, "确认订单"))
        checkin_btn = QPushButton("办理入住")
        checkin_btn.clicked.connect(lambda: self._order_action(OrderService.check_in, "办理入住"))
        checkout_btn = QPushButton("办理退房")
        checkout_btn.clicked.connect(lambda: self._order_action(OrderService.check_out, "办理退房"))
        for button in (refresh_btn, cancel_btn, confirm_btn, checkin_btn, checkout_btn):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        note = QLabel("顾客可取消自己的待确认或已确认订单；工作人员可确认订单、办理入住/退房，并取消待确认订单（需填写原因）。")
        note.setWordWrap(True)
        layout.addWidget(note)
        return page


    def _create_order_from_search(self):
        if not isinstance(self.current_operator, Customer):
            QMessageBox.warning(self, "需要顾客登录", "请先登录顾客账户，再提交预订。")
            return
        row = self.search_results_table.currentRow()
        if row < 0 or row >= len(self.search_results):
            QMessageBox.warning(self, "提示", "请先选择查询结果中的房型。")
            return
        result = self.search_results[row]
        session = get_session()
        try:
            order = OrderService.create_order(
                session, self.current_operator, result.hotel.id, result.room_type.id,
                self.search_check_in.date().toPython(), self.search_check_out.date().toPython(),
                self.search_guests.value(),
            )
            session.commit()
            QMessageBox.information(self, "预订成功", f"订单已提交，订单号：{order.order_number}\n当前状态：待确认")
            self._refresh_orders()
        except Exception as exc:
            session.rollback()
            QMessageBox.warning(self, "预订失败", str(exc))
        finally:
            session.close()


    def _refresh_orders(self):
        if not hasattr(self, "order_table"):
            return
        self.order_table.setRowCount(0)
        if self.current_operator is None:
            return
        session = get_session()
        try:
            orders = OrderService.list_orders(session, self.current_operator)
            self.order_table.setRowCount(len(orders))
            for row, order in enumerate(orders):
                values = [order.id, order.order_number, order.hotel_id, order.room_type_id,
                         order.check_in, order.check_out, order.guest_count,
                         f"{order.total_price:.2f}", order.status.value]
                for col, value in enumerate(values):
                    self.order_table.setItem(row, col, QTableWidgetItem(str(value)))
            self.order_table.resizeColumnsToContents()
        except Exception as exc:
            QMessageBox.warning(self, "订单查询失败", str(exc))
        finally:
            session.close()


    def _selected_order_id(self):
        row = self.order_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先选择一条订单。")
            return None
        return int(self.order_table.item(row, 0).text())



    def _order_action(self, action, action_name):
        if not isinstance(self.current_operator, HotelStaff):
            QMessageBox.warning(self, "权限不足", "该操作仅酒店工作人员可以执行。")
            return
        order_id = self._selected_order_id()
        if order_id is None:
            return
        session = get_session()
        try:
            action(session, self.current_operator, order_id)
            session.commit()
            QMessageBox.information(self, "操作成功", f"{action_name}已完成。")
            self._refresh_orders()
        except Exception as exc:
            session.rollback()
            QMessageBox.warning(self, "操作失败", str(exc))
        finally:
            session.close()


    def _cancel_selected_order(self):
        order_id = self._selected_order_id()
        if order_id is None:
            return
        session = get_session()
        try:
            if isinstance(self.current_operator, Customer):
                OrderService.cancel_by_customer(session, self.current_operator, order_id)
            elif isinstance(self.current_operator, HotelStaff):
                reason, accepted = QInputDialog.getText(self, "取消订单", "请输入取消原因：")
                if not accepted:
                    return
                OrderService.cancel_by_staff(session, self.current_operator, order_id, reason)
            else:
                QMessageBox.warning(self, "权限不足", "平台管理员不执行顾客订单取消操作。")
                return
            session.commit()
            QMessageBox.information(self, "操作成功", "订单已取消，库存已释放。")
            self._refresh_orders()
        except Exception as exc:
            session.rollback()
            QMessageBox.warning(self, "操作失败", str(exc))
        finally:
            session.close()


    def _build_hotel_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.hotel_table = QTableWidget(0, 6)
        self.hotel_table.setHorizontalHeaderLabels(["ID", "酒店名称", "城市", "地址", "电话", "状态"])
        self.hotel_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.hotel_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.hotel_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.hotel_table)

        button_row = QHBoxLayout()
        add_btn = QPushButton("新增酒店（管理员）")
        add_btn.clicked.connect(self._add_hotel)
        approve_btn = QPushButton("审核通过")
        approve_btn.clicked.connect(lambda: self._change_status(HotelStatus.OPEN))
        close_btn = QPushButton("设为停业")
        close_btn.clicked.connect(lambda: self._change_status(HotelStatus.CLOSED))
        reopen_btn = QPushButton("恢复营业")
        reopen_btn.clicked.connect(lambda: self._change_status(HotelStatus.OPEN))
        refresh_btn = QPushButton("刷新列表")
        refresh_btn.clicked.connect(self._refresh_hotels)
        button_row.addWidget(add_btn)
        button_row.addWidget(approve_btn)
        button_row.addWidget(close_btn)
        button_row.addWidget(reopen_btn)
        button_row.addWidget(refresh_btn)
        layout.addLayout(button_row)
        note = QLabel("酒店工作人员可修改所属酒店的基本资料；平台管理员负责新增酒店及审核/状态管理。")
        note.setWordWrap(True)
        layout.addWidget(note)
        return page



    def _build_room_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        selector_row = QHBoxLayout()
        selector_row.addWidget(QLabel("酒店"))
        self.room_hotel_combo = QComboBox()
        self.room_hotel_combo.currentIndexChanged.connect(self._refresh_room_types)
        selector_row.addWidget(self.room_hotel_combo)
        refresh_hotels_btn = QPushButton("刷新酒店列表")
        refresh_hotels_btn.clicked.connect(self._refresh_room_hotel_combo)
        selector_row.addWidget(refresh_hotels_btn)
        selector_row.addStretch()
        layout.addLayout(selector_row)

        layout.addWidget(QLabel("房型列表"))
        self.room_type_table = QTableWidget(0, 5)
        self.room_type_table.setHorizontalHeaderLabels(["ID", "房型名称", "入住人数", "描述", "销售状态"])
        self.room_type_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.room_type_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.room_type_table.horizontalHeader().setStretchLastSection(True)
        self.room_type_table.itemSelectionChanged.connect(self._refresh_inventory)
        layout.addWidget(self.room_type_table)

        room_buttons = QHBoxLayout()
        add_room_btn = QPushButton("新增房型")
        add_room_btn.clicked.connect(self._add_room_type)
        toggle_sale_btn = QPushButton("切换停售 / 在售")
        toggle_sale_btn.clicked.connect(self._toggle_room_sale)
        room_buttons.addWidget(add_room_btn)
        room_buttons.addWidget(toggle_sale_btn)
        room_buttons.addStretch()
        layout.addLayout(room_buttons)

        layout.addWidget(QLabel("选中房型的每日库存与价格"))
        self.inventory_table = QTableWidget(0, 5)
        self.inventory_table.setHorizontalHeaderLabels(["日期", "总房间数", "已预订", "剩余", "价格"])
        self.inventory_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.inventory_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.inventory_table)
        inventory_buttons = QHBoxLayout()
        set_inventory_btn = QPushButton("批量设置日期范围库存 / 价格")
        set_inventory_btn.clicked.connect(self._set_inventory_range_dialog)
        inventory_refresh_btn = QPushButton("刷新库存")
        inventory_refresh_btn.clicked.connect(self._refresh_inventory)
        inventory_buttons.addWidget(set_inventory_btn)
        inventory_buttons.addWidget(inventory_refresh_btn)
        inventory_buttons.addStretch()
        layout.addLayout(inventory_buttons)
        self._refresh_room_hotel_combo()
        return page

    def _refresh_room_hotel_combo(self):
        if not hasattr(self, "room_hotel_combo"):
            return
        session = get_session()
        try:
            hotels = HotelService.list_hotels(session)
            current_id = self.room_hotel_combo.currentData()
            self.room_hotel_combo.blockSignals(True)
            self.room_hotel_combo.clear()
            if isinstance(self.current_operator, HotelStaff):
                hotels = [hotel for hotel in hotels if hotel.id == self.current_operator.hotel_id]
            for hotel in hotels:
                self.room_hotel_combo.addItem(f"{hotel.id} - {hotel.name} ({hotel.city})", hotel.id)
            index = self.room_hotel_combo.findData(current_id)
            if index >= 0:
                self.room_hotel_combo.setCurrentIndex(index)
            self.room_hotel_combo.blockSignals(False)
            self._refresh_room_types()
        finally:
            session.close()

    def _selected_room_type_id(self):
        row = self.room_type_table.currentRow()
        if row < 0:
            return None
        return int(self.room_type_table.item(row, 0).text())

    def _refresh_room_types(self):
        if not hasattr(self, "room_type_table"):
            return
        hotel_id = self.room_hotel_combo.currentData()
        self.room_type_table.setRowCount(0)
        self.inventory_table.setRowCount(0)
        if hotel_id is None:
            return
        session = get_session()
        try:
            room_types = RoomService.list_room_types(session, hotel_id)
            self.room_type_table.setRowCount(len(room_types))
            for row, room_type in enumerate(room_types):
                values = [room_type.id, room_type.name, room_type.capacity,
                          room_type.description, room_type.sale_status.value]
                for col, value in enumerate(values):
                    self.room_type_table.setItem(row, col, QTableWidgetItem(str(value)))
            self.room_type_table.resizeColumnsToContents()
        finally:
            session.close()

    def _refresh_inventory(self):
        room_type_id = self._selected_room_type_id()
        self.inventory_table.setRowCount(0)
        if room_type_id is None:
            return
        session = get_session()
        try:
            records = RoomService.list_inventory(session, room_type_id)
            self.inventory_table.setRowCount(len(records))
            for row, record in enumerate(records):
                remaining = record.total_rooms - record.reserved_rooms
                values = [record.inventory_date, record.total_rooms, record.reserved_rooms,
                          remaining, f"{record.price:.2f}"]
                for col, value in enumerate(values):
                    self.inventory_table.setItem(row, col, QTableWidgetItem(str(value)))
            self.inventory_table.resizeColumnsToContents()
        finally:
            session.close()

    def _add_room_type(self):
        hotel_id = self.room_hotel_combo.currentData()
        if hotel_id is None:
            QMessageBox.warning(self, "提示", "请先选择酒店。")
            return
        if self.current_operator is None:
            QMessageBox.warning(self, "未登录", "请先登录工作人员或管理员账户。")
            return
        dialog = QWidget()
        dialog.setWindowTitle("新增房型")
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        form = QFormLayout(dialog)
        name = QLineEdit()
        capacity = QSpinBox()
        capacity.setRange(1, 20)
        capacity.setValue(2)
        description = QTextEdit()
        description.setFixedHeight(70)
        form.addRow("房型名称", name)
        form.addRow("入住人数", capacity)
        form.addRow("描述", description)
        save = QPushButton("保存")
        save.clicked.connect(lambda: self._save_room_type(dialog, hotel_id, name, capacity, description))
        form.addRow(save)
        dialog.resize(360, 280)
        dialog.show()
        self._room_dialog = dialog

    def _save_room_type(self, dialog, hotel_id, name, capacity, description):
        session = get_session()
        try:
            room_type = RoomService.create_room_type(session, self.current_operator, hotel_id,
                name.text(), capacity.value(), description.toPlainText())
            session.commit()
            QMessageBox.information(self, "成功", f"房型已创建，ID={room_type.id}")
            dialog.close()
            self._refresh_room_types()
        except Exception as exc:
            session.rollback()
            QMessageBox.warning(self, "创建失败", str(exc))
        finally:
            session.close()

    def _toggle_room_sale(self):
        room_type_id = self._selected_room_type_id()
        if room_type_id is None:
            QMessageBox.warning(self, "提示", "请先选择房型。")
            return
        current_status = self.room_type_table.item(self.room_type_table.currentRow(), 4).text()
        target = SaleStatus.OFF_SALE if current_status == SaleStatus.ON_SALE.value else SaleStatus.ON_SALE
        session = get_session()
        try:
            RoomService.set_sale_status(session, self.current_operator, room_type_id, target)
            session.commit()
            self._refresh_room_types()
        except Exception as exc:
            session.rollback()
            QMessageBox.warning(self, "操作失败", str(exc))
        finally:
            session.close()

    def _set_inventory_range_dialog(self):
        room_type_id = self._selected_room_type_id()
        if room_type_id is None:
            QMessageBox.warning(self, "提示", "请先选择房型。")
            return
        if self.current_operator is None:
            QMessageBox.warning(self, "未登录", "请先登录工作人员或管理员账户。")
            return
        dialog = QWidget()
        dialog.setWindowTitle("批量设置库存和价格")
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        form = QFormLayout(dialog)
        start = QDateEdit()
        start.setCalendarPopup(True)
        start.setDate(date.today())
        end = QDateEdit()
        end.setCalendarPopup(True)
        end.setDate(date.today())
        rooms = QSpinBox()
        rooms.setRange(0, 10000)
        price = QDoubleSpinBox()
        price.setRange(0, 10000000)
        price.setDecimals(2)
        price.setSuffix(" 元")
        form.addRow("开始日期", start)
        form.addRow("结束日期", end)
        form.addRow("每天总房间数", rooms)
        form.addRow("每天价格", price)
        save = QPushButton("应用")
        save.clicked.connect(lambda: self._save_inventory_range(dialog, room_type_id, start, end, rooms, price))
        form.addRow(save)
        dialog.resize(360, 260)
        dialog.show()
        self._inventory_dialog = dialog

    def _save_inventory_range(self, dialog, room_type_id, start, end, rooms, price):
        session = get_session()
        try:
            start_date = start.date().toPython()
            end_date = end.date().toPython()
            RoomService.set_inventory_range(session, self.current_operator, room_type_id,
                start_date, end_date, rooms.value(), price.value())
            session.commit()
            QMessageBox.information(self, "成功", "日期范围内库存和价格已更新。")
            dialog.close()
            self._refresh_inventory()
        except Exception as exc:
            session.rollback()
            QMessageBox.warning(self, "设置失败", str(exc))
        finally:
            session.close()

    def _register_customer(self):
        username = self.reg_username.text().strip()
        password = self.reg_password.text()
        phone = self.reg_phone.text().strip()
        session = get_session()
        try:
            customer = AuthService.register_customer(session, username, password, phone)
            session.commit()
            QMessageBox.information(self, "注册成功", f"账户 {customer.username} 已创建。")
            self.login_role.setCurrentText(AuthService.ROLE_CUSTOMER)
            self.login_username.setText(username)
            self.login_password.clear()
        except Exception as exc:
            session.rollback()
            QMessageBox.warning(self, "注册失败", str(exc))
        finally:
            session.close()


    def _login(self):
        role = self.login_role.currentText()
        session = get_session()
        try:
            user = AuthService.authenticate(session, role, self.login_username.text(),
                                          self.login_password.text())
            if user is None:
                QMessageBox.warning(self, "登录失败", "用户名或密码错误")
                return
            self.current_operator = user
            self.current_role = role
            self.statusBar().showMessage(f"已登录：{user.username}（{role}）")
            self._refresh_hotels()
            self._refresh_room_hotel_combo()
            self._refresh_orders()
            QMessageBox.information(self, "登录成功", f"欢迎，{user.username}！")
        except Exception as exc:
            QMessageBox.warning(self, "登录失败", str(exc))
        finally:
            session.close()


    def _add_hotel(self):
        if not isinstance(self.current_operator, PlatformAdmin):
            QMessageBox.warning(self, "权限不足", "新增酒店仅平台管理员可操作。请先登录管理员账户。")
            return
        dialog = QWidget()
        dialog.setWindowTitle("新增酒店")
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        form = QFormLayout(dialog)
        name, city, address, phone = QLineEdit(), QLineEdit(), QLineEdit(), QLineEdit()
        description = QTextEdit()
        description.setFixedHeight(80)
        form.addRow("酒店名称*", name)
        form.addRow("城市*", city)
        form.addRow("地址*", address)
        form.addRow("电话", phone)
        form.addRow("介绍", description)
        save = QPushButton("保存")
        save.clicked.connect(lambda: self._save_hotel(dialog, name, city, address, phone, description))
        form.addRow(save)
        dialog.resize(400, 360)
        dialog.show()
        self._hotel_dialog = dialog


    def _save_hotel(self, dialog, name, city, address, phone, description):
        session = get_session()
        try:
            hotel = HotelService.create_hotel(session, self.current_operator, name.text(),
                city.text(), address.text(), phone.text(), description.toPlainText())
            session.commit()
            QMessageBox.information(self, "保存成功", f"酒店已创建，ID={hotel.id}，当前状态为待审核。")
            dialog.close()
            self._refresh_hotels()
        except Exception as exc:
            session.rollback()
            QMessageBox.warning(self, "保存失败", str(exc))
        finally:
            session.close()


    def _change_status(self, status):
        if not isinstance(self.current_operator, PlatformAdmin):
            QMessageBox.warning(self, "权限不足", "酒店状态管理仅平台管理员可操作。")
            return
        hotel_id = self._selected_hotel_id()
        if hotel_id is None:
            return
        session = get_session()
        try:
            HotelService.set_status(session, self.current_operator, hotel_id, status)
            session.commit()
            self._refresh_hotels()
        except Exception as exc:
            session.rollback()
            QMessageBox.warning(self, "操作失败", str(exc))
        finally:
            session.close()


    def _selected_hotel_id(self):
        row = self.hotel_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先选择一条酒店记录。")
            return None
        return int(self.hotel_table.item(row, 0).text())



    def _refresh_hotels(self):
        session = get_session()
        try:
            hotels = HotelService.list_hotels(session)
            self.hotel_table.setRowCount(len(hotels))
            for row, hotel in enumerate(hotels):
                values = [hotel.id, hotel.name, hotel.city, hotel.address, hotel.phone,
                         hotel.status.value]
                for col, value in enumerate(values):
                    self.hotel_table.setItem(row, col, QTableWidgetItem(str(value)))
            self.hotel_table.resizeColumnsToContents()
        finally:
            session.close()


    def _build_statistics_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        hotel_row = QHBoxLayout()
        self.stats_hotel_combo = QComboBox()
        self.stats_date = QDateEdit()
        self.stats_date.setCalendarPopup(True)
        self.stats_date.setDate(QDate.currentDate())
        daily_btn = QPushButton("查询酒店每日库存统计")
        daily_btn.clicked.connect(self._query_hotel_daily_stats)
        hotel_row.addWidget(QLabel("酒店"))
        hotel_row.addWidget(self.stats_hotel_combo)
        hotel_row.addWidget(QLabel("日期"))
        hotel_row.addWidget(self.stats_date)
        hotel_row.addWidget(daily_btn)
        layout.addLayout(hotel_row)
        self.hotel_stats_label = QLabel("请选择酒店和日期后查询。")
        layout.addWidget(self.hotel_stats_label)

        range_row = QHBoxLayout()
        self.stats_start = QDateEdit()
        self.stats_start.setCalendarPopup(True)
        self.stats_start.setDate(QDate.currentDate())
        self.stats_end = QDateEdit()
        self.stats_end.setCalendarPopup(True)
        self.stats_end.setDate(QDate.currentDate())
        platform_btn = QPushButton("查询平台统计")
        platform_btn.clicked.connect(self._query_platform_stats)
        hotel_orders_btn = QPushButton("查询酒店订单统计")
        hotel_orders_btn.clicked.connect(self._query_hotel_order_stats)
        range_row.addWidget(QLabel("统计开始"))
        range_row.addWidget(self.stats_start)
        range_row.addWidget(QLabel("统计结束"))
        range_row.addWidget(self.stats_end)
        range_row.addWidget(platform_btn)
        range_row.addWidget(hotel_orders_btn)
        layout.addLayout(range_row)
        self.hotel_order_stats_label = QLabel("酒店订单统计尚未查询。")
        self.hotel_order_stats_label.setWordWrap(True)
        layout.addWidget(self.hotel_order_stats_label)
        self.platform_stats_label = QLabel("平台统计尚未查询。")
        self.platform_stats_label.setWordWrap(True)
        layout.addWidget(self.platform_stats_label)
        layout.addStretch()
        self._refresh_stats_hotels()
        return page

    def _refresh_stats_hotels(self):
        if not hasattr(self, "stats_hotel_combo"):
            return
        session = get_session()
        try:
            self.stats_hotel_combo.clear()
            hotels = HotelService.list_hotels(session)
            for hotel in hotels:
                self.stats_hotel_combo.addItem(f"{hotel.id} - {hotel.name}", hotel.id)
        finally:
            session.close()

    def _query_hotel_daily_stats(self):
        hotel_id = self.stats_hotel_combo.currentData()
        if not isinstance(self.current_operator, (PlatformAdmin, HotelStaff)):
            QMessageBox.warning(self, "权限不足", "酒店经营统计仅酒店工作人员或平台管理员可查看。")
            return
        if isinstance(self.current_operator, HotelStaff) and hotel_id != self.current_operator.hotel_id:
            QMessageBox.warning(self, "权限不足", "酒店工作人员只能查看所属酒店统计。")
            return
        if hotel_id is None:
            QMessageBox.information(self, "提示", "当前没有可统计的酒店。")
            return
        target = self.stats_date.date().toPython()
        session = get_session()
        try:
            data = StatisticsService.hotel_daily(session, hotel_id, target)
            self.hotel_stats_label.setText(
                f"{data['hotel_name']} | {target} | 总房间数：{data['total_rooms']} | "
                f"已预订：{data['reserved_rooms']} | 剩余：{data['remaining_rooms']}"
            )
        except Exception as exc:
            QMessageBox.warning(self, "统计失败", str(exc))
        finally:
            session.close()

    def _query_hotel_order_stats(self):
        hotel_id = self.stats_hotel_combo.currentData()
        if not isinstance(self.current_operator, (PlatformAdmin, HotelStaff)):
            QMessageBox.warning(self, "权限不足", "酒店订单统计仅酒店工作人员或平台管理员可查看。")
            return
        if isinstance(self.current_operator, HotelStaff) and hotel_id != self.current_operator.hotel_id:
            QMessageBox.warning(self, "权限不足", "酒店工作人员只能查看所属酒店统计。")
            return
        if hotel_id is None:
            QMessageBox.information(self, "提示", "当前没有可统计的酒店。")
            return
        start = self.stats_start.date().toPython()
        end = self.stats_end.date().toPython()
        session = get_session()
        try:
            data = StatisticsService.hotel_order_summary(session, hotel_id, start, end)
            self.hotel_order_stats_label.setText(
                f"{data['hotel_name']} | {start} 至 {end} | 订单数量：{data['orders']} | "
                f"取消数量：{data['cancelled']}"
            )
        except Exception as exc:
            QMessageBox.warning(self, "统计失败", str(exc))
        finally:
            session.close()


    def _query_platform_stats(self):
        if not isinstance(self.current_operator, PlatformAdmin):
            QMessageBox.warning(self, "权限不足", "平台统计仅平台管理员可查看。")
            return
        start = self.stats_start.date().toPython()
        end = self.stats_end.date().toPython()
        session = get_session()
        try:
            data = StatisticsService.platform_summary(session, start, end)
            self.platform_stats_label.setText(
                f"酒店总数：{data['hotel_total']} | 正常营业酒店：{data['open_hotel_total']} | "
                f"{start} 至 {end} 订单总数：{data['order_total']}"
            )
        except Exception as exc:
            QMessageBox.warning(self, "统计失败", str(exc))
        finally:
            session.close()

    def _build_log_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        filter_row = QHBoxLayout()
        self.log_action_filter = QLineEdit()
        self.log_action_filter.setPlaceholderText("操作名称包含…")
        self.log_result_filter = QComboBox()
        self.log_result_filter.addItems(["全部结果", "成功", "失败"])
        query_btn = QPushButton("查询日志")
        query_btn.clicked.connect(self._query_logs)
        filter_row.addWidget(self.log_action_filter)
        filter_row.addWidget(self.log_result_filter)
        filter_row.addWidget(query_btn)
        layout.addLayout(filter_row)
        self.log_table = QTableWidget(0, 6)
        self.log_table.setHorizontalHeaderLabels(["时间", "角色", "操作人ID", "操作", "详情", "结果"])
        self.log_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.log_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.log_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.log_table)
        layout.addWidget(QLabel("平台管理员可查询平台日志；酒店工作人员仅可查询本人产生的工作人员日志。顾客无日志查询权限。"))
        return page

    def _query_logs(self):
        if self.current_operator is None:
            QMessageBox.warning(self, "权限不足", "请先登录。")
            return
        result = self.log_result_filter.currentText()
        if result == "全部结果":
            result = ""
        session = get_session()
        try:
            entries = LogService.query(session, self.current_operator,
                                     action=self.log_action_filter.text(), result=result)
            self.log_table.setRowCount(len(entries))
            for row, entry in enumerate(entries):
                values = [entry.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                          entry.operator_role, entry.operator_id, entry.action, entry.detail, entry.result]
                for col, value in enumerate(values):
                    self.log_table.setItem(row, col, QTableWidgetItem(str(value)))
            self.log_table.resizeColumnsToContents()
        except Exception as exc:
            QMessageBox.warning(self, "查询失败", str(exc))
        finally:
            session.close()

    def _build_platform_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("平台酒店审核与状态管理。下列操作仅平台管理员可执行。"))
        self.platform_hotel_table = QTableWidget(0, 6)
        self.platform_hotel_table.setHorizontalHeaderLabels(["ID", "酒店名称", "城市", "地址", "电话", "状态"])
        self.platform_hotel_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.platform_hotel_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.platform_hotel_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.platform_hotel_table)
        buttons = QHBoxLayout()
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._refresh_platform_hotels)
        approve_btn = QPushButton("审核通过 / 恢复营业")
        approve_btn.clicked.connect(lambda: self._platform_change_status(HotelStatus.OPEN))
        reject_btn = QPushButton("审核未通过")
        reject_btn.clicked.connect(lambda: self._platform_change_status(HotelStatus.REJECTED))
        close_btn = QPushButton("停业")
        close_btn.clicked.connect(lambda: self._platform_change_status(HotelStatus.CLOSED))
        staff_btn = QPushButton("为选中酒店创建工作人员账号")
        staff_btn.clicked.connect(self._create_staff_for_selected_hotel)
        list_staff_btn = QPushButton("查看选中酒店工作人员")
        list_staff_btn.clicked.connect(self._show_staff_for_selected_hotel)
        for button in (refresh_btn, approve_btn, reject_btn, close_btn, staff_btn, list_staff_btn):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        layout.addStretch()
        self._refresh_platform_hotels()
        return page


    def _selected_platform_hotel(self):
        if not isinstance(self.current_operator, PlatformAdmin):
            QMessageBox.warning(self, "权限不足", "创建及管理酒店工作人员账号仅平台管理员可操作。")
            return None
        row = self.platform_hotel_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先在平台酒店列表中选择酒店。")
            return None
        hotel_id = int(self.platform_hotel_table.item(row, 0).text())
        session = get_session()
        try:
            hotel = session.get(Hotel, hotel_id)
            if hotel is None:
                QMessageBox.warning(self, "操作失败", "所选酒店不存在。")
                return None
            return hotel_id, hotel.name
        finally:
            session.close()


    def _create_staff_for_selected_hotel(self):
        selected = self._selected_platform_hotel()
        if selected is None:
            return
        hotel_id, hotel_name = selected
        dialog = QDialog(self)
        dialog.setWindowTitle(f"创建工作人员账号 - {hotel_name}")
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        form = QFormLayout(dialog)
        username = QLineEdit()
        password = QLineEdit()
        password.setEchoMode(QLineEdit.EchoMode.Password)
        confirm = QLineEdit()
        confirm.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("所属酒店", QLabel(f"{hotel_name}（ID: {hotel_id}）"))
        form.addRow("工作人员用户名", username)
        form.addRow("密码（至少6位）", password)
        form.addRow("确认密码", confirm)
        buttons = QHBoxLayout()
        create_btn = QPushButton("创建账号")
        cancel_btn = QPushButton("取消")
        create_btn.clicked.connect(lambda: self._save_staff_account(
            dialog, hotel_id, hotel_name, username, password, confirm))
        cancel_btn.clicked.connect(dialog.reject)
        buttons.addWidget(create_btn)
        buttons.addWidget(cancel_btn)
        form.addRow(buttons)
        dialog.resize(380, 180)
        dialog.exec()


    def _save_staff_account(self, dialog, hotel_id, hotel_name, username, password, confirm):
        if password.text() != confirm.text():
            QMessageBox.warning(dialog, "创建失败", "两次输入的密码不一致。")
            return
        session = get_session()
        try:
            staff = AuthService.create_staff(session, username.text(), password.text(), hotel_id)
            LogService.record(session, "平台管理员", self.current_operator.id, "创建酒店工作人员账号",
                             f"酒店ID={hotel_id}，酒店名称={hotel_name}，工作人员用户名={staff.username}")
            session.commit()
            QMessageBox.information(dialog, "创建成功",
                                  f"工作人员账号已创建。\n用户名：{staff.username}\n所属酒店：{hotel_name}")
            dialog.accept()
        except Exception as exc:
            session.rollback()
            QMessageBox.warning(dialog, "创建失败", str(exc))
        finally:
            session.close()


    def _show_staff_for_selected_hotel(self):
        selected = self._selected_platform_hotel()
        if selected is None:
            return
        hotel_id, hotel_name = selected
        session = get_session()
        try:
            staff_members = list(session.query(HotelStaff).filter_by(hotel_id=hotel_id).order_by(HotelStaff.id))
            dialog = QDialog(self)
            dialog.setWindowTitle(f"工作人员列表 - {hotel_name}")
            dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
            layout = QVBoxLayout(dialog)
            table = QTableWidget(len(staff_members), 2)
            table.setHorizontalHeaderLabels(["员工ID", "用户名"])
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            for row, staff in enumerate(staff_members):
                table.setItem(row, 0, QTableWidgetItem(str(staff.id)))
                table.setItem(row, 1, QTableWidgetItem(staff.username))
            table.resizeColumnsToContents()
            layout.addWidget(table)
            close_btn = QPushButton("关闭")
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn)
            dialog.resize(360, 300)
            dialog.exec()
        finally:
            session.close()


    def _refresh_platform_hotels(self):
        if not hasattr(self, "platform_hotel_table"):
            return
        session = get_session()
        try:
            hotels = HotelService.list_hotels(session)
            self.platform_hotel_table.setRowCount(len(hotels))
            for row, hotel in enumerate(hotels):
                values = [hotel.id, hotel.name, hotel.city, hotel.address, hotel.phone, hotel.status.value]
                for col, value in enumerate(values):
                    self.platform_hotel_table.setItem(row, col, QTableWidgetItem(str(value)))
            self.platform_hotel_table.resizeColumnsToContents()
        finally:
            session.close()


    def _platform_change_status(self, status):
        if not isinstance(self.current_operator, PlatformAdmin):
            QMessageBox.warning(self, "权限不足", "平台酒店管理仅平台管理员可操作。")
            return
        row = self.platform_hotel_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择酒店。")
            return
        hotel_id = int(self.platform_hotel_table.item(row, 0).text())
        session = get_session()
        try:
            HotelService.set_status(session, self.current_operator, hotel_id, status)
            session.commit()
            self._refresh_platform_hotels()
            self._refresh_hotels()
        except Exception as exc:
            session.rollback()
            QMessageBox.warning(self, "操作失败", str(exc))
        finally:
            session.close()
