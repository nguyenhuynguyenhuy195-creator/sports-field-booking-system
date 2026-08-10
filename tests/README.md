# Thư mục kiểm thử

- `conftest.py`: tạo Flask app và database SQLite độc lập cho từng test.
- `integration/`: kiểm tra application factory, health, xác thực, owner application, venue, field, pricing, maintenance, trạng thái lưới giờ booking, phân bổ tiền, thanh toán mô phỏng, creator top-up và vòng đời tìm đối thủ/ghép người.
- `unit/`: kiểm tra model, constraint/index và thuật toán chia 100%, 50/50, theo đầu người, gồm trường hợp làm tròn số nguyên VND.

Testing config dùng SQLite trong bộ nhớ để test nhanh và độc lập. Migration vẫn được chạy trực tiếp trên SQL Server development để phát hiện khác biệt kiểu dữ liệu, constraint và identity.
