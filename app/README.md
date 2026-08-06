# Thư mục mã nguồn

Cấu trúc hiện tại:

- `__init__.py`: application factory, khởi tạo extensions, cấu hình Flask-Login và đăng ký blueprint.
- `extensions.py`: SQLAlchemy, Migrate, LoginManager và CSRFProtect dùng chung.
- `routes/`: trang chủ, đăng ký, đăng nhập, đăng xuất, liveness và readiness health checks.
- `models/`: model `User`, vai trò và trạng thái tài khoản.
- `forms/`: biểu mẫu Flask-WTF và validation cho đăng ký/đăng nhập.
- `services/`: chuẩn hóa dữ liệu và nghiệp vụ tạo/tìm tài khoản, tách khỏi route.
- `templates/`: layout chung và các trang Jinja2 responsive.
- `static/`: CSS riêng theo bộ màu của dự án.
- `integrations/`: client dịch vụ ngoài, dự kiến có MoMo Sandbox.
- `cli/`: tác vụ định kỳ và lệnh quản trị.

Route chỉ tiếp nhận HTTP và điều phối. Validation nằm ở form, nghiệp vụ nằm ở service, dữ liệu nằm ở model; cách tách này giúp các bước đặt sân và thanh toán tiếp theo dễ kiểm thử hơn.
