# Sports Field Booking System

## 1. Giới thiệu

Sports Field Booking System là website quản lý đặt sân bóng đá, thanh toán MoMo Sandbox và tìm kèo trực tuyến. Hệ thống kết nối người chơi, chủ sân và quản trị viên; hỗ trợ thanh toán đủ, chia 50/50 với đội đối thủ hoặc chia tiền theo đầu người.

## 2. Luồng nghiệp vụ chính

```text
Đăng ký hoặc đăng nhập
→ Tìm sân
→ Xem chi tiết
→ Chọn thời gian
→ Đặt sân
→ Chủ sân xác nhận
→ Thanh toán 100% hoặc thanh toán phần đầu
→ Tạo kèo nếu cần
→ Đối thủ/người ghép thanh toán
→ Booking đủ tiền
```

Ba hình thức thanh toán:
- `FULL_PAYMENT`: người đặt trả 100%.
- `SPLIT_OPPONENT`: hai đội chia 50/50.
- `SPLIT_PLAYERS`: chia theo đầu người.

MVP dùng MoMo Sandbox và hỗ trợ hoàn tiền; MoMo Production không thuộc phạm vi đồ án ngành.

## 3. Công nghệ

### Backend
- Python
- Flask
- Flask-SQLAlchemy
- Flask-Migrate
- Flask-Login
- Flask-WTF

### Frontend
- HTML
- CSS
- Bootstrap 5
- Jinja2
- JavaScript

### Database
- Microsoft SQL Server
- pyodbc

## 4. Cấu trúc thư mục dự kiến

```text
app/
├── models/
├── forms/
├── routes/
├── services/
├── integrations/
├── cli/
├── templates/
├── static/
├── extensions.py
└── __init__.py

docs/
tests/
migrations/
```

## 5. Cài đặt

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Sao chép `.env.example` thành `.env`, cập nhật thông tin SQL Server và credential MoMo Sandbox. Không commit `.env` hoặc secret key.

Cấu hình development hiện dùng Windows Authentication với SQL Server mặc định trên `localhost`. Database khởi tạo là `sports_field_booking`.

## 6. Chạy ứng dụng

```bash
.venv\Scripts\python.exe -m flask --app run.py run
```

Kiểm tra ứng dụng:

```text
GET http://127.0.0.1:5000/health
GET http://127.0.0.1:5000/health/ready
```

`/health` kiểm tra tiến trình Flask. `/health/ready` chạy `SELECT 1` để xác nhận SQL Server sẵn sàng. Chưa chạy `flask db init` hoặc tạo migration ở giai đoạn khởi tạo.

## 7. Chạy kiểm thử

```bash
.venv\Scripts\python.exe -m pytest
```

## 8. Tài liệu quan trọng

Codex phải đọc theo thứ tự:
1. `AGENTS.md`
2. `docs/01-project-overview.md`
3. `docs/02-scope-mvp.md`
4. `docs/03-business-rules.md`
5. `docs/04-booking-workflow.md`
6. `docs/05-database-design.md`
7. `docs/06-system-architecture.md`
8. `docs/07-ui-requirements.md`
9. `docs/08-acceptance-criteria.md`
10. `docs/09-test-cases.md`
11. `docs/10-decision-log.md`
