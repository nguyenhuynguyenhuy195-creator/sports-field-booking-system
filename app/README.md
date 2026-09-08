# Thư mục mã nguồn

> Scope nghiệm thu từ 08/09/2026 (GVHD xác nhận, ADR-039): **Hệ thống sử dụng thanh toán mô phỏng trong môi trường thử nghiệm.** MVP chỉ dùng MOCK/SIMULATED PAYMENT; MoMo Sandbox không phải runtime provider. Nội dung MoMo/HMAC/IPN/query còn được giữ dưới đây là thiết kế hoặc kiểm thử legacy, không phải tính năng đang hoạt động hay điều kiện nghiệm thu.

Cấu trúc hiện tại:

- `__init__.py`: application factory, khởi tạo extensions, cấu hình Flask-Login và đăng ký blueprint.
- `extensions.py`: SQLAlchemy, Migrate, LoginManager và CSRFProtect dùng chung.
- `routes/`: trang chủ, xác thực, yêu cầu owner, venue, field, pricing, maintenance, booking, payment mô phỏng, tìm kèo và health checks.
- `models/`: model tài khoản, sân, booking, contribution/payment/refund, `Match` và `MatchParticipant`, cùng các vai trò và trạng thái.
- `forms/`: biểu mẫu Flask-WTF cho xác thực, owner application, venue, field, khung giá, bảo trì, booking và tìm kèo.
- `services/`: nghiệp vụ tài khoản, sân, lịch trống, booking, phân bổ tiền, thanh toán và ghép người; bao gồm quyền sở hữu, khóa SQL Server, chống trùng lịch, snapshot giá, hạn 15 phút, chống thu dư và transaction.
- `templates/`: layout chung và các trang Jinja2 responsive.
- `static/`: CSS và JavaScript thuần cho giao diện responsive, lưới mốc giờ 30 phút, luồng booking bốn bước, báo giá và countdown giữ chỗ.
- `integrations/`: client dịch vụ ngoài; client MoMo chỉ giữ làm legacy, disabled trong MVP; không có kế hoạch nối Sandbox trong scope hiện hành.
- `cli/`: lệnh `users create-admin`, `bookings expire` và `matches expire` cho các hạn thanh toán.

Route chỉ tiếp nhận HTTP và điều phối. Validation nằm ở form, nghiệp vụ nằm ở service, dữ liệu nằm ở model; endpoint availability/quote không tạo booking và thao tác tạo booking luôn kiểm tra lại trong transaction trước khi tự động giữ chỗ 15 phút.
