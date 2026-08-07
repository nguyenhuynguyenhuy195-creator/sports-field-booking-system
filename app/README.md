# Thư mục mã nguồn

Cấu trúc hiện tại:

- `__init__.py`: application factory, khởi tạo extensions, cấu hình Flask-Login và đăng ký blueprint.
- `extensions.py`: SQLAlchemy, Migrate, LoginManager và CSRFProtect dùng chung.
- `routes/`: trang chủ, xác thực, yêu cầu owner, quản lý/kiểm duyệt venue, field, pricing, maintenance và health checks.
- `models/`: model `User`, `OwnerApplication`, `Venue`, `Field`, `FieldPriceSlot`, `FieldMaintenance`, các vai trò và trạng thái.
- `forms/`: biểu mẫu Flask-WTF cho xác thực, owner application, venue, field, khung giá và lịch bảo trì.
- `services/`: nghiệp vụ tài khoản, owner application, venue, field, pricing và maintenance, bao gồm kiểm tra quyền sở hữu, chống chồng giờ, tính giá và transaction.
- `templates/`: layout chung và các trang Jinja2 responsive.
- `static/`: CSS riêng theo bộ màu của dự án.
- `integrations/`: client dịch vụ ngoài, dự kiến có MoMo Sandbox.
- `cli/`: lệnh `users create-admin`; sau này bổ sung tác vụ định kỳ.

Route chỉ tiếp nhận HTTP và điều phối. Validation nằm ở form, nghiệp vụ nằm ở service, dữ liệu nằm ở model; cách tách này giúp các bước đặt sân và thanh toán tiếp theo dễ kiểm thử hơn.
