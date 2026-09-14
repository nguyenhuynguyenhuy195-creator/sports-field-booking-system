# Thư mục kiểm thử

> Bộ test hiện tại bao phủ cả MOCK và VNPAY Sandbox bằng transport giả; MoMo chỉ còn regression legacy cô lập và bị vô hiệu hóa trong runtime. Kết quả cuối phải lấy từ lần chạy full suite mới nhất.

- `conftest.py`: tạo Flask app và database SQLite độc lập cho từng test.
- `integration/`: kiểm tra application factory, health, xác thực, owner application, venue, field, pricing, maintenance, trạng thái lưới giờ booking, phân bổ tiền, thanh toán mô phỏng, creator top-up và vòng đời tìm đối thủ/ghép người.
- `unit/`: kiểm tra model, constraint/index và thuật toán chia 100%, 50/50, theo đầu người, gồm trường hợp làm tròn số nguyên VND.

Testing config dùng SQLite trong bộ nhớ để test nhanh và độc lập. Migration vẫn được chạy trực tiếp trên SQL Server development để phát hiện khác biệt kiểu dữ liệu, constraint và identity.


## Regression sau audit MOCK-only (08/09/2026)

`tests/integration/test_mock_only_audit.py` kiểm tra các lối vào MoMo bị chặn, service không chạm DB dù nhận injected client, cấu hình môi trường không bật lại MoMo, MOCK vẫn thanh toán và chống thu lặp; SQL Server SQL hint và refresh identity map; đơn giá nguyên VND, booking 90 phút với đơn giá lẻ đồng; timezone Việt Nam trên host UTC; ảnh thật/ảnh giả/pixel cap/request cap; FK từ chối orphan.

Fixture SQLite bật `PRAGMA foreign_keys=ON` trên mỗi connection. `test_migration_head.py` dựng database SQLite rỗng qua đủ migration, đối chiếu metadata và kiểm tra foreign_key_check; không thay thế kiểm thử nâng cấp SQL Server chứa dữ liệu legacy. Các module test MoMo chủ động bật cờ chỉ trên app testing và dùng fake transport; test đó không chứng minh Sandbox thật hoạt động. Fixture ảnh cũ chỉ chứa magic bytes đã được thay bằng PNG thật để đáp ứng validation, không bỏ assertion.

Kết quả canonical của lần chạy full suite cuối: **1308 passed, 8 warnings, 0 failed** (xem `README.md` mục 8). Không sử dụng số đếm lịch sử trong tài liệu như kết quả hiện tại; chạy lại `pytest` để lấy số mới nhất sau mỗi thay đổi.
