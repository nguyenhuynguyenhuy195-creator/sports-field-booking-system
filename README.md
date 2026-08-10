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
→ Hệ thống kiểm tra và giữ chỗ 15 phút
→ Thanh toán 100% hoặc thanh toán phần đầu
→ Tạo kèo nếu cần
→ Đối thủ/người ghép thanh toán
→ Booking đủ tiền
```

Ba hình thức thanh toán:
- `FULL_PAYMENT`: người đặt trả 100%.
- `SPLIT_OPPONENT`: hai đội chia 50/50.
- `SPLIT_PLAYERS`: chia theo đầu người.

Đích MVP dùng MoMo Sandbox và hỗ trợ hoàn tiền; MoMo Production không thuộc phạm vi đồ án ngành. Hiện repository đã có nền tảng phân bổ nghĩa vụ và provider `MOCK` để kiểm thử cập nhật tiền/trạng thái mà không trừ tiền thật. Kết nối HMAC, redirect và IPN MoMo Sandbox là bước tích hợp tiếp theo.

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

## 4. Cấu trúc thư mục

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
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Sao chép `.env.example` thành `.env` và cập nhật thông tin SQL Server. Không commit `.env` hoặc secret key. Credential MoMo chỉ bổ sung khi bắt đầu bước tích hợp Sandbox thật.

Cấu hình development hiện dùng Windows Authentication với SQL Server mặc định trên `localhost`. Database khởi tạo là `sports_field_booking`.

## 6. Chạy ứng dụng

Khởi tạo hoặc cập nhật cấu trúc database trước lần chạy đầu tiên:

```bash
.\.venv\Scripts\python.exe -m flask --app run.py db upgrade
```

Lệnh trên đọc các migration trong `migrations/` và áp dụng chúng theo đúng thứ tự. Các migration hiện tại tạo bảng `users`, `owner_applications`, `venues`, `fields`, `field_price_slots`, `field_maintenances`, `bookings`, `booking_price_details`, `booking_contributions`, `payments` và `refunds`; bảng `alembic_version` do Flask-Migrate dùng để ghi nhận phiên bản database.

Sau đó chạy website:

```bash
.\.venv\Scripts\python.exe -m flask --app run.py run
```

Kiểm tra ứng dụng:

```text
GET http://127.0.0.1:5000/health
GET http://127.0.0.1:5000/health/ready
GET http://127.0.0.1:5000/auth/register
GET http://127.0.0.1:5000/auth/login
GET http://127.0.0.1:5000/venues
```

`/health` kiểm tra tiến trình Flask. `/health/ready` chạy `SELECT 1` để xác nhận SQL Server sẵn sàng. Hai trang `/auth/register` và `/auth/login` cung cấp chức năng tài khoản đầu tiên của hệ thống.

## 7. Chức năng đã triển khai

- Đăng ký tài khoản người chơi bằng họ tên, email, số điện thoại tùy chọn và mật khẩu.
- Chuẩn hóa email, kiểm tra email không trùng và lưu mật khẩu ở dạng băm.
- Đăng nhập, ghi nhớ đăng nhập và đăng xuất bằng biểu mẫu POST có CSRF.
- Từ chối đăng nhập đối với tài khoản bị khóa hoặc ngừng hoạt động.
- Phân quyền nền tảng `USER`, `OWNER`, `ADMIN` ở phía backend.
- Người chơi gửi và theo dõi yêu cầu trở thành chủ sân.
- Admin chấp nhận hoặc từ chối yêu cầu; khi chấp nhận, tài khoản được chuyển thành `OWNER` trong cùng transaction.
- Lệnh CLI tạo tài khoản admin đầu tiên mà không mở đăng ký admin công khai.
- Giao diện responsive dùng Jinja2, Bootstrap 5 và CSS riêng.
- OWNER tạo, sửa và xem danh sách cơ sở của chính mình; venue mới luôn chờ admin duyệt.
- ADMIN duyệt công khai hoặc ẩn venue và hệ thống lưu dấu vết kiểm duyệt.
- Khách chỉ xem được danh sách và chi tiết venue có trạng thái `ACTIVE`.
- OWNER tạo, sửa và xem các sân con thuộc cơ sở của chính mình; sân mới luôn có trạng thái `INACTIVE`.
- Tên sân không được trùng trong cùng một cơ sở; khách chỉ thấy sân `ACTIVE` thuộc cơ sở `ACTIVE`.
- OWNER cấu hình giá theo sân, ngày trong tuần và khoảng giờ; các khung giá `ACTIVE` cùng ngày không được chồng nhau.
- Field chỉ được bật `ACTIVE` khi có khung giá hợp lệ; hệ thống có thể tách nhiều khung để tính đủ giá cho một khoảng thời gian.
- OWNER tạo và hủy lịch bảo trì theo sân, ngày và khoảng giờ; các lịch `ACTIVE` cùng sân không được chồng nhau.
- Lịch bảo trì hết giờ được hiển thị là đã hoàn thành và lịch đã hủy không còn chặn khoảng thời gian.
- USER/OWNER đặt field `ACTIVE`; backend kiểm tra bước 30 phút, thời lượng tối thiểu, giới hạn đặt trước, giờ mở cửa, bảo trì và booking trùng rồi tự động giữ chỗ 15 phút.
- Booking lưu snapshot từng đoạn giá và tổng tiền từ database, không nhận giá từ frontend.
- Người chơi xem báo giá trước khi xác nhận, theo dõi lịch sử/chi tiết và hủy booking hợp lệ; chủ sân theo dõi hoặc hủy booking khi có sự cố theo quyền sở hữu.
- Lệnh `flask bookings expire` cập nhật idempotent các booking giữ chỗ đã quá hạn thanh toán đầu tiên.
- Khi tạo booking, backend phân bổ tiền theo `FULL_PAYMENT`, `SPLIT_OPPONENT` hoặc `SPLIT_PLAYERS`; hình thức chia theo người dùng sức chứa field và số người còn thiếu, làm tròn đến từng đồng nhưng vẫn đúng tổng.
- Trang chi tiết hiển thị từng nghĩa vụ, tiến độ đã thu/còn thiếu và lịch sử giao dịch.
- Provider `MOCK` ghi nhận thanh toán thành công trong transaction để kiểm thử: trả 100%, trả phần đầu, chuyển `PARTIALLY_PAID`, và người tạo trả toàn bộ phần còn thiếu để chuyển `PAID`.
- Các nghĩa vụ được trả thay chuyển `WAIVED` nhưng giữ nguyên số tiền gốc để phục vụ đối soát; hệ thống không thu vượt `total_amount` và từ chối thanh toán lặp.

Tạo tài khoản quản trị viên đầu tiên:

```bash
.\.venv\Scripts\python.exe -m flask --app run.py users create-admin
```

Lệnh sẽ hỏi họ tên, email và mật khẩu. Mật khẩu được nhập ẩn và được lưu dưới dạng băm.

## 8. Chạy kiểm thử

```bash
.\.venv\Scripts\python.exe -m pytest
```

## 9. Tài liệu quan trọng

Tài liệu dự án nên được đọc theo thứ tự:
1. `docs/01-project-overview.md`
2. `docs/02-scope-mvp.md`
3. `docs/03-business-rules.md`
4. `docs/04-booking-workflow.md`
5. `docs/05-database-design.md`
6. `docs/06-system-architecture.md`
7. `docs/07-ui-requirements.md`
8. `docs/08-acceptance-criteria.md`
9. `docs/09-test-cases.md`
10. `docs/10-decision-log.md`
