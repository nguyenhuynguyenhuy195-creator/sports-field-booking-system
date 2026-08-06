# Thư mục kiểm thử

- `conftest.py`: tạo Flask app và database SQLite độc lập cho từng test.
- `integration/`: kiểm tra application factory, health, xác thực, owner application và luồng tạo/sửa/duyệt/ẩn venue.
- `unit/`: kiểm tra model người dùng, owner application và constraint/index của venue; sau này bổ sung field, pricing, booking, contribution, payment và refund.

Testing config dùng SQLite trong bộ nhớ để test nhanh và độc lập. Migration vẫn được chạy trực tiếp trên SQL Server development để phát hiện khác biệt kiểu dữ liệu, constraint và identity.
