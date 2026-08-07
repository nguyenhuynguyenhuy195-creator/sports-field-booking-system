# Thư mục kiểm thử

- `conftest.py`: tạo Flask app và database SQLite độc lập cho từng test.
- `integration/`: kiểm tra application factory, health, xác thực, owner application, venue, field, pricing, maintenance, báo giá không ghi dữ liệu và luồng tự động giữ chỗ booking trước thanh toán.
- `unit/`: kiểm tra model và constraint/index của user, owner application, venue, field, price slot, maintenance, booking và price snapshot; sau này bổ sung contribution, payment và refund.

Testing config dùng SQLite trong bộ nhớ để test nhanh và độc lập. Migration vẫn được chạy trực tiếp trên SQL Server development để phát hiện khác biệt kiểu dữ liệu, constraint và identity.
