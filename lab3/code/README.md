# 酒店预订系统

课程实验项目：Python + PySide6 + SQLite + SQLAlchemy。

## 环境要求

- Python 3.11
- Windows / macOS / Linux
- 建议使用 PyCharm 或 VS Code

## 初始化

```bash
python -m venv .venv
```

Windows PowerShell：
```powershell
.venv\Scripts\Activate.ps1
```

macOS / Linux：
```bash
source .venv/bin/activate
```

安装依赖：
```bash
python -m pip install -r requirements.txt
```

启动：
```bash
python main.py
```

运行测试：
```bash
pytest
```

## 当前进度

第一阶段：项目骨架、数据库连接、基础领域模型和主窗口。

后续按模块逐步实现：
1. 用户与权限
2. 酒店管理
3. 房型与库存
4. 酒店查询
5. 订单管理
6. 统计
7. 操作日志
8. 平台管理

注意：当前骨架尚未实现完整业务功能，后续会逐模块补齐并测试。

## 第一批业务功能（M1 / M2）

- 顾客注册与登录（密码 PBKDF2-SHA256哈希保存，不存明文）。
- 顾客、酒店工作人员、平台管理员登录认证。
- 酒店信息查询、创建、资料修改服务。
- 酒店营业状态：待审核、营业、停业、审核未通过。
- 管理权限：平台管理员创建酒店并修改状态；工作人员只能管理所属酒店。
- 操作日志服务记录酒店创建、信息修改及状态变化。
- 桌面UI提供顾客注册/登录、酒店列表、管理员新增酒店和审核/状态按钮。

首次启动会创建演示管理员账户：`admin / admin123`。实际部署时请更改演示密码并避免使用默认凭据。

测试：
```bash
pytest -q
```
当前测试覆盖注册认证、重复用户名、短密码、酒店创建与审核、权限拒绝等基础场景。

## 第三阶段：房型与库存管理

当前实现包括：
- 房型创建、信息修改、列表查询
- 房型在售/停售切换
- 按包含首尾日期的范围批量设置每日房量与价格
- 每日库存查询与剩余房间数计算
- 预订数量约束检查，不能把总房量设置为低于已预订数量
- 酒店工作人员仅可操作所属酒店，平台管理员可管理酒店房型
- 房型和库存操作写入操作日志

房型库存批量设置的日期范围为包含首尾日期；订单住宿日期范围仍应在订单模块采用入住日包含、退房日不包含的规则。

测试命令：`pytest -v`

## Stage 4：酒店查询模块

- 支持城市、入住/退房日期、入住人数、房型名称筛选。
- 价格筛选基于所选住宿日期内的平均每晚价格。
- 只返回营业酒店、在售房型，且入住区间每一天均配置库存并有剩余房间的结果。
- 退房日期采用不包含边界（入住日包含、退房日不包含）。
- 查询结果展示每晚价格、住宿总价及住宿期间最少剩余房间数。

查询页当前为筛选和结果展示，不包含下单功能。

## Stage 5: Order management (M5)

Implemented order-service functions:
- customer order creation with hotel/room/date/capacity checks
- per-night atomic inventory reservation and price snapshots
- exact duplicate active-order prevention
- customer cancellation of pending/confirmed orders
- staff cancellation of pending orders with a required reason
- staff confirmation, check-in, and check-out status transitions
- customer order modification with inventory reallocation
- order list visibility scoped to customer, staff's hotel, or platform admin
- order operations logged through the operation-log service

The desktop UI now includes an Order Management tab, a create-order action from selected hotel-search results, and basic order actions for the logged-in role.

Run tests with `pytest -v`.

## Stage 6：统计、日志与平台管理

- M6：酒店每日库存统计、酒店日期范围订单/取消统计、平台酒店数量/营业酒店数量/日期范围订单统计。
- M7：操作日志查询；管理员查询全局日志，酒店工作人员查询本人产生的工作人员日志；按操作和结果筛选。
- M8：平台酒店列表、审核通过、审核未通过、停业和恢复营业入口。
- 自动化测试覆盖新增统计与日志服务。

统计口径说明：订单区间统计按订单创建时间筛选，并包含起止日期。酒店每日房间统计汇总该酒店当日库存表中的房型库存数据。
