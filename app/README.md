# Thư mục mã nguồn

Cấu trúc hiện tại:

- `__init__.py`: application factory, khởi tạo extensions và đăng ký blueprint.
- `extensions.py`: SQLAlchemy, Migrate, LoginManager và CSRFProtect dùng chung.
- `routes/`: HTTP routes; hiện có liveness và readiness health checks.
- `models/`: model sẽ được tạo sau khi ERD được duyệt.
- `forms/`: Flask-WTF forms và validation.
- `services/`: nghiệp vụ tách khỏi route.
- `integrations/`: client dịch vụ ngoài, dự kiến có MoMo Sandbox.
- `cli/`: tác vụ định kỳ và lệnh quản trị.

Chưa có model, migration hoặc chức năng người dùng trong giai đoạn khởi tạo.
