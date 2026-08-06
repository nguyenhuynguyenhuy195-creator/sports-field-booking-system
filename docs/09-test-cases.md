# 9. Test cases

## 9.1. Authentication và authorization

### TC-AUTH-001: Đăng ký thành công
Email chưa tồn tại → tạo user, hash password, role `USER`, status `ACTIVE`.

### TC-AUTH-002: Email trùng
Không tạo user và hiển thị lỗi.

### TC-AUTH-003: Tài khoản bị khóa
Không đăng nhập được.

### TC-AUTHZ-001: USER truy cập owner dashboard
Trả 403 hoặc chuyển về trang phù hợp.

### TC-AUTHZ-002: OWNER A sửa dữ liệu OWNER B
Bị từ chối; venue, field, giá, bảo trì và booking không thay đổi.

### TC-OWNER-001: Gửi yêu cầu owner trùng
Không tạo yêu cầu `PENDING` thứ hai.

### TC-OWNER-002: Admin duyệt owner
Application `APPROVED` và role chuyển `OWNER` trong cùng transaction.

## 9.2. Venue, field, giá và bảo trì

### TC-VENUE-001: Venue mới
Tạo với owner hiện tại, trạng thái `PENDING`, không xuất hiện công khai.

### TC-VENUE-002: Admin duyệt venue
Chuyển `ACTIVE` và xuất hiện công khai.

### TC-FIELD-001: Field mới
Trạng thái mặc định `INACTIVE`.

### TC-PRICE-001: Hai khung giá chồng nhau
Đã có 17:00–19:00; từ chối tạo 18:00–21:00 trong cùng ngày áp dụng.

### TC-PRICE-002: Booking qua hai khung giá
17:00–18:00 giá 200.000đ/giờ, 18:00–21:00 giá 300.000đ/giờ; booking 17:30–19:00 có total 400.000đ và hai price detail.

### TC-PRICE-003: Thiếu khung giá
Booking 16:00–18:00 nhưng chỉ có giá 17:00–18:00 → không tạo booking và báo khoảng thiếu.

### TC-MAINT-001: Bảo trì trùng booking
Từ chối tạo bảo trì; booking không thay đổi.

### TC-MAINT-002: Booking trùng bảo trì
Từ chối tạo booking.

## 9.3. Booking

### TC-BOOKING-001: Booking hợp lệ
Field/venue `ACTIVE`, thời gian hợp lệ, đủ giá, không trùng → tạo `PENDING` và price snapshot.

### TC-BOOKING-002: Bước thời gian sai
Từ chối 18:10–19:40.

### TC-BOOKING-003: Thời lượng dưới 60 phút
Từ chối 18:00–18:30.

### TC-BOOKING-004: Giới hạn đặt trước
- `FULL_PAYMENT` trước dưới 60 phút → từ chối.
- Booking chia tiền trước dưới 13 giờ → từ chối.
- Ngày quá 30 ngày → từ chối.

### TC-BOOKING-005: Trùng lịch
Đã có booking chiếm chỗ 18:00–20:00. Từ chối 17:00–19:00, 18:00–20:00, 19:00–21:00, 18:30–19:30 và 17:00–21:00. Chấp nhận 16:00–18:00 và 20:00–22:00.

### TC-BOOKING-006: Trạng thái không chiếm chỗ
Booking `REJECTED`, `CANCELLED`, `EXPIRED` hoặc `COMPLETED` không làm khung giờ bận.

### TC-BOOKING-007: Owner xác nhận sân khác
Bị từ chối và dữ liệu không đổi.

### TC-BOOKING-008: PENDING hết hạn
Quá 30 phút → `EXPIRED`; chạy job lần hai không tạo thay đổi mới.

### TC-BOOKING-009: CONFIRMED hết hạn
Không có khoản thanh toán đầu tiên sau 15 phút → `EXPIRED`.

### TC-BOOKING-010: Hai request đồng thời
Chỉ một booking giao nhau được commit; request còn lại nhận lỗi hết chỗ.

## 9.4. Payment MoMo

### TC-PAYMENT-001: Tạo payment
Amount lấy từ contribution; order/request unique; signature đúng; trả payUrl sandbox.

### TC-PAYMENT-002: Không tin redirect
Redirect báo thành công nhưng chưa có IPN → payment chưa `SUCCESS`, booking chưa `PAID`.

### TC-PAYMENT-003: IPN hợp lệ
Chữ ký, amount, order và partner đúng → payment `SUCCESS`; cập nhật contribution/booking đúng transaction.

### TC-PAYMENT-004: IPN sai chữ ký hoặc số tiền
Không cập nhật tiền; ghi log lỗi phù hợp.

### TC-PAYMENT-005: IPN lặp lại
Xử lý idempotent; paid amount không tăng lần hai.

### TC-PAYMENT-006: Thanh toán lại
Attempt đầu `FAILED`; attempt sau trong hạn `SUCCESS`; chỉ cộng tiền một lần.

### TC-PAYMENT-007: Chống thu dư
Từ chối payment làm tổng thành công vượt `total_amount`.

## 9.5. Chia tiền và tìm kèo

### TC-SPLIT-001: Tìm đối thủ 50/50
Người tạo trả 50% → `PARTIALLY_PAID`; đối thủ được chấp nhận trả 50% → booking `PAID`, match `CONFIRMED`.

### TC-SPLIT-002: Yêu cầu đối thủ hết hạn
Không thanh toán trong 15 phút → participant `EXPIRED`, contribution hết hiệu lực, kèo mở lại.

### TC-SPLIT-003: Tìm người theo đầu người
Tổng 10 người, thiếu 3 → người tạo chịu 7 phần, tạo ba contribution bằng nhau và điều chỉnh phần cuối đúng tổng.

### TC-SPLIT-004: Không yêu cầu tài khoản thành viên có sẵn
Người tạo thanh toán phần nhóm hiện có mà không cần tạo 7 tài khoản thành viên.

### TC-SPLIT-005: Vị trí cuối bị cạnh tranh
Hai user thanh toán vị trí cuối đồng thời → chỉ một người `JOINED`; không thu dư và không vượt sức chứa.

### TC-SPLIT-006: Người tạo top-up
Người tạo trả toàn bộ số còn thiếu → booking `PAID`; contribution chưa trả được điều chỉnh về 0 để không thu thêm. Match vẫn `OPEN` nếu chưa có đủ đối thủ/người; người được chấp nhận sau đó tham gia không phải thanh toán.

### TC-SPLIT-007: Không đủ tiền tại deadline
Booking chuyển `REFUND_PENDING`; creator refund 80%, người tham gia refund 100%, phí giữ sân bằng 20% khoản creator đã đóng.

## 9.6. Refund và rút kèo

### TC-REFUND-001: Owner hủy PAID
Lưu lý do; tạo refund 100% cho mọi payment; chỉ `CANCELLED` sau khi refund thành công.

### TC-REFUND-002: Refund đang xử lý
MoMo chưa có kết quả cuối → booking giữ `REFUND_PENDING`; query/retry không tạo refund trùng.

### TC-REFUND-003: Refund callback/query lặp
Không cộng số tiền refund lần hai.

### TC-WITHDRAW-001: Rút trước trên 12 giờ
Refund 100%, participant `WITHDRAWN`, vị trí mở lại.

### TC-WITHDRAW-002: Rút trong 12 giờ
Không tạo refund; contribution vẫn tính vào booking.

### TC-NOSHOW-001: Đã trả nhưng không đến
Không refund và không tự khóa tài khoản trong MVP.

## 9.7. Kiểm tra rollback

### TC-TX-001: Commit booking thất bại
Rollback booking và price details; không để dữ liệu dở dang.

### TC-TX-002: IPN commit thất bại
Rollback payment/contribution/booking; có thể xử lý lại IPN an toàn.

### TC-TX-003: Một refund trong nhóm thất bại
Booking giữ `REFUND_PENDING`; refund thành công không bị tạo lại, refund thất bại có thể retry/query.
