# 10. Decision Log

## ADR-001: Sử dụng Flask

**Ngày quyết định:** 06/08/2026

Theo định hướng GVHD; phù hợp Python, phát triển nhanh và dễ giải thích kiến trúc khi bảo vệ.

## ADR-002: Sử dụng SQL Server

Phù hợp môi trường Windows và kiến thức tại trường; hỗ trợ transaction, khóa, index và constraint cần cho booking/payment.

## ADR-003: Sử dụng SQLAlchemy và Flask-Migrate

SQLAlchemy ánh xạ model và hỗ trợ truy vấn có transaction. Flask-Migrate quản lý lịch sử schema; migration phải được review trên SQL Server và không chỉnh schema thủ công thiếu kiểm soát.

## ADR-004: Sử dụng Jinja2 và Bootstrap 5

Giữ frontend/backend trong một dự án, giảm JavaScript và phù hợp thời gian đồ án. Không dùng React, Vue, Angular, Tailwind hoặc Flutter Web.

## ADR-005: Giá theo khung giờ và ngày trong tuần

- Không dùng một `base_price` duy nhất.
- Owner cấu hình giá theo field, ngày trong tuần và khoảng giờ.
- Khung giá không chồng nhau; booking phải được phủ đủ giá.
- Booking qua nhiều khung được tách và lưu price snapshot.

## ADR-006: Tích hợp MoMo Sandbox trong MVP

- Sử dụng MoMo Sandbox với HMAC, redirect, IPN, query và refund.
- Redirect không quyết định thanh toán thành công; IPN hợp lệ mới cập nhật dữ liệu.
- Credential nằm trong biến môi trường.
- MoMo Production và tiền thật không thuộc phiên bản đồ án ngành.

Tài liệu kỹ thuật tham chiếu:
- [MoMo Payment Notification](https://developers.momo.vn/v3/docs/payment/api/result-handling/notification/)
- [MoMo Reverse & Refund](https://developers.momo.vn/v3/vi/docs/payment/api/payment-api/refund/)

## ADR-007: Ba hình thức thanh toán booking

- `FULL_PAYMENT`: người tạo trả 100%.
- `SPLIT_OPPONENT`: hai đội chia 50/50.
- `SPLIT_PLAYERS`: chia theo đầu người; người tạo trả phần nhóm có sẵn, người ghép trả phần của họ.

Thành viên có sẵn không bắt buộc tạo tài khoản. Người tạo có thể trả phần còn thiếu trước funding deadline; booking đủ tiền không tự làm kèo đủ người, và người tham gia sau đó không phải đóng thêm.

## ADR-008: Thời hạn booking và góp tiền

- Booking thường đặt trước tối thiểu 60 phút; booking chia tiền tối thiểu 13 giờ; tối đa 30 ngày.
- Owner phản hồi trong 30 phút.
- Khoản thanh toán đầu tiên và payment của người được chấp nhận có hạn 15 phút.
- Booking chia tiền phải đủ trước giờ bắt đầu 12 giờ.

## ADR-009: Chính sách không góp đủ và hoàn tiền

- Không góp đủ đúng hạn: creator được hoàn 80%, 20% khoản creator đã đóng là phí giữ sân cho owner.
- Đối thủ/người ghép đã thanh toán đúng hạn được hoàn 100%.
- Owner hủy vì sự cố: hoàn 100% cho mọi người đã thanh toán.
- Refund là bản ghi riêng; không xóa hoặc ghi đè payment gốc.

## ADR-010: Chính sách rút khỏi kèo và no-show

- Rút trước giờ bắt đầu trên 12 giờ: hoàn 100% và mở lại vị trí.
- Rút trong vòng 12 giờ hoặc no-show: không hoàn tiền.
- MVP chưa theo dõi điểm no-show hoặc tự động khóa tài khoản.

## ADR-011: Venue, field và bảo trì

- Venue mới `PENDING`, admin duyệt mới `ACTIVE`.
- Field mới `INACTIVE`, chỉ bật sau khi đủ cấu hình.
- Bảo trì lưu theo ngày/khoảng giờ và không được trùng booking chiếm chỗ.

## ADR-012: Quy trình trở thành owner

User đăng ký với role `USER`, gửi owner application và chỉ chuyển thành `OWNER` sau khi admin duyệt.

## ADR-013: Trạng thái và tính nhất quán

- Bổ sung `PARTIALLY_PAID` và `REFUND_PENDING` cho booking.
- Booking `REFUND_PENDING` tiếp tục chiếm chỗ cho đến khi hoàn tiền xong.
- Payment/contribution/refund được xử lý idempotent và trong transaction phù hợp.
- Kiểm tra trùng và tạo booking phải chống race condition trên SQL Server.

## ADR-014: AI và chức năng mở rộng

AI lọc spam, phân tích cảm xúc, recommendation, chat thời gian thực, mobile app và theo dõi no-show nâng cao không thuộc MVP. Các mục này chỉ xem xét sau khi booking, MoMo, refund và chia tiền đã ổn định.
