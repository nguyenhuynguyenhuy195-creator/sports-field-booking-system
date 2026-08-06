# Thư mục mã nguồn

Cấu trúc hiện tại:

- `__init__.py`: application factory, khởi tạo extensions, cấu hình Flask-Login và đăng ký blueprint.
- `extensions.py`: SQLAlchemy, Migrate, LoginManager và CSRFProtect dùng chung.
- `routes/`: trang chủ, xác thực, yêu cầu owner, trang duyệt admin và health checks.
- `models/`: model `User`, `OwnerApplication`, các vai trò và trạng thái.
- `forms/`: biểu mẫu Flask-WTF cho xác thực, gửi yêu cầu và xét duyệt owner.
- `services/`: nghiệp vụ tài khoản và owner application, bao gồm transaction đổi role.
- `templates/`: layout chung và các trang Jinja2 responsive.
- `static/`: CSS riêng theo bộ màu của dự án.
- `integrations/`: client dịch vụ ngoài, dự kiến có MoMo Sandbox.
- `cli/`: lệnh `users create-admin`; sau này bổ sung tác vụ định kỳ.

Route chỉ tiếp nhận HTTP và điều phối. Validation nằm ở form, nghiệp vụ nằm ở service, dữ liệu nằm ở model; cách tách này giúp các bước đặt sân và thanh toán tiếp theo dễ kiểm thử hơn.
