# Thư mục kiểm thử

- `conftest.py`: tạo Flask app và database SQLite độc lập cho từng test.
- `integration/`: kiểm tra application factory, health, xác thực và luồng gửi/duyệt/từ chối yêu cầu owner.
- `unit/`: kiểm tra model người dùng và filtered unique index của owner application; sau này bổ sung pricing, booking, contribution, payment và refund.

Testing config dùng SQLite trong bộ nhớ để test nhanh và độc lập. Migration vẫn được chạy trực tiếp trên SQL Server development để phát hiện khác biệt kiểu dữ liệu, constraint và identity.
