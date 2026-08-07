# Thư mục kiểm thử

- `conftest.py`: tạo Flask app và database SQLite độc lập cho từng test.
- `integration/`: kiểm tra application factory, health, xác thực, owner application, venue, field và luồng cấu hình/tính pricing.
- `unit/`: kiểm tra model người dùng, owner application, constraint/index của venue, field và field price slot; sau này bổ sung booking, contribution, payment và refund.

Testing config dùng SQLite trong bộ nhớ để test nhanh và độc lập. Migration vẫn được chạy trực tiếp trên SQL Server development để phát hiện khác biệt kiểu dữ liệu, constraint và identity.
