# Thư mục mã nguồn

Cấu trúc hiện tại:

- `__init__.py`: application factory, khởi tạo extensions, cấu hình Flask-Login và đăng ký blueprint.
- `extensions.py`: SQLAlchemy, Migrate, LoginManager và CSRFProtect dùng chung.
- `routes/`: trang chủ, xác thực, yêu cầu owner, venue, field, pricing, maintenance, booking, payment mô phỏng và health checks.
- `models/`: model tài khoản, sân, booking, `BookingContribution`, `Payment`, `Refund`, cùng các vai trò và trạng thái.
- `forms/`: biểu mẫu Flask-WTF cho xác thực, owner application, venue, field, khung giá, bảo trì và booking.
- `services/`: nghiệp vụ tài khoản, sân, booking, phân bổ tiền và thanh toán; bao gồm quyền sở hữu, khóa SQL Server, chống trùng lịch, snapshot giá, chống thu dư và transaction.
- `templates/`: layout chung và các trang Jinja2 responsive.
- `static/`: CSS và JavaScript thuần cho giao diện responsive, luồng booking bốn bước, báo giá và countdown giữ chỗ.
- `integrations/`: client dịch vụ ngoài; MoMo Sandbox thật sẽ được nối sau khi provider `MOCK` và quy tắc tiền ổn định.
- `cli/`: lệnh `users create-admin` và `bookings expire` cho booking quá hạn trước thanh toán.

Route chỉ tiếp nhận HTTP và điều phối. Validation nằm ở form, nghiệp vụ nằm ở service, dữ liệu nằm ở model; endpoint quote không tạo dữ liệu và thao tác tạo booking luôn kiểm tra lại trong transaction trước khi tự động giữ chỗ 15 phút.
