# Thư mục kiểm thử

- `conftest.py`: tạo Flask app và database SQLite độc lập cho từng test.
- `integration/`: kiểm tra application factory, health routes và toàn bộ luồng đăng ký/đăng nhập/đăng xuất.
- `unit/`: kiểm tra model người dùng; sau này bổ sung pricing, booking, contribution, payment và refund services.

Testing config dùng SQLite trong bộ nhớ để test nhanh và độc lập. Migration vẫn được chạy trực tiếp trên SQL Server development để phát hiện khác biệt kiểu dữ liệu, constraint và identity.
