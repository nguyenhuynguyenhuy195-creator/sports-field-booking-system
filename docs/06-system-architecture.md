# 6. Kiến trúc hệ thống

## 6.1. Kiến trúc tổng quát

```text
Browser
→ Flask Route / MoMo IPN Endpoint / CLI Job
→ Service Layer
→ Repository query qua SQLAlchemy
→ SQL Server

Payment Service
→ Provider MOCK (đã triển khai, nội bộ)
→ MoMo Client → MoMo Sandbox API (bước kế tiếp)
```

Flask render giao diện bằng Jinja2. Nghiệp vụ không được đặt toàn bộ trong route.

## 6.2. Presentation Layer

Công nghệ: HTML, CSS, Bootstrap 5, Jinja2 và JavaScript thuần khi cần.

Trách nhiệm:
- Hiển thị dữ liệu và trạng thái.
- Nhận input và hiển thị validation.
- Gửi request đến backend.
- Hiển thị countdown và tiến độ đóng góp từ dữ liệu backend.

Frontend không quyết định quyền, giá, số tiền đóng góp, trạng thái payment hoặc refund.

## 6.3. Route Layer

Các blueprint đã có gồm `auth`, `owner_applications`, `venues`, `fields`, `pricing`, `maintenance`, `bookings`, `payments` và health checks. `payments` hiện nhận lệnh POST thanh toán/top-up mô phỏng có CSRF. Các endpoint redirect/IPN MoMo, `refunds`, `matches` và phần admin mở rộng sẽ được bổ sung ở các module kế tiếp.

Thiết kế đích của các blueprint thanh toán:
- `auth`: đăng ký, đăng nhập, đăng xuất.
- `owner_applications`: gửi và xét duyệt yêu cầu owner.
- `venues`: venue, field, giá và bảo trì.
- `bookings`: báo giá, tạo giữ chỗ tự động, xem và hủy booking.
- `payments`: bắt đầu thanh toán, redirect và IPN MoMo.
- `refunds`: yêu cầu/query refund theo quyền.
- `matches`: tạo kèo, gửi/duyệt/rút yêu cầu.
- `admin`: tài khoản, venue, booking, payment, refund và match.

Route chỉ nhận request, kiểm tra authentication/authorization, validate form, gọi service và trả response.

Endpoint IPN phải:
- Công khai qua HTTPS khi tích hợp sandbox.
- Miễn CSRF vì được gọi server-to-server.
- Bắt buộc xác minh HMAC và idempotency trước khi thay đổi dữ liệu.

## 6.4. Service Layer

Các service dự kiến:
- `pricing_service`: kiểm tra khung giá, tách thời lượng và tính snapshot giá.
- `availability_service`: kiểm tra giờ hoạt động, bảo trì và trùng lịch.
- `booking_service`: tạo booking và chuyển trạng thái.
- `contribution_service`: phân bổ nghĩa vụ 100%, 50/50 hoặc theo đầu người.
- `payment_service`: tạo payment attempt, xử lý IPN và tổng tiền đã thu.
- `refund_service`: tính số tiền hoàn, gọi/query MoMo và hoàn tất hủy.
- `match_service`: tạo kèo, duyệt yêu cầu, mở lại vị trí và gắn contribution.
- `owner_application_service`: xử lý yêu cầu chuyển role.
- `expiration_service`: hết hạn booking, yêu cầu thanh toán và hạn góp tiền.

Service chịu trách nhiệm kiểm tra quyền sở hữu, khóa dữ liệu cần thiết, quản lý transaction và rollback khi lỗi.

## 6.5. MoMo Client

MoMo Client là lớp hạ tầng riêng, không đặt trực tiếp trong route.

Trách nhiệm:
- Tạo chuỗi raw signature đúng thứ tự trường.
- Ký và xác minh HMAC SHA-256.
- Gọi create payment, query transaction, refund và query refund.
- Chuẩn hóa timeout, mã lỗi và response.
- Không log secret key hoặc dữ liệu nhạy cảm.

Credential và endpoint phải đọc từ biến môi trường. Sandbox và production phải tách cấu hình; MVP chỉ bật sandbox.

## 6.6. Model Layer

Trách nhiệm:
- Định nghĩa 13 bảng và quan hệ trong `docs/05-database-design.md`.
- Khai báo primary key, foreign key, unique/check constraint và index.
- Dùng `DECIMAL` cho tiền và `DATETIME2` cho timestamp UTC.
- Không chứa orchestration nghiệp vụ dài trong model.

## 6.7. Cấu trúc thư mục dự kiến

```text
app/
├── models/
├── forms/
├── routes/
├── services/
├── integrations/
│   └── momo/
├── cli/
├── templates/
├── static/
├── extensions.py
└── __init__.py

tests/
├── unit/
└── integration/
```

## 6.8. Transaction tạo booking

1. Route validate form và gọi service.
2. Service khóa phạm vi dữ liệu cần kiểm tra của field/ngày.
3. Kiểm tra field, venue, giờ hoạt động và bảo trì.
4. Truy vấn booking chiếm chỗ giao nhau.
5. Truy vấn toàn bộ khung giá và kiểm tra độ phủ.
6. Tính total, tạo booking `CONFIRMED`, hạn thanh toán 15 phút và price details.
7. Commit một lần; lỗi thì rollback.

Mục tiêu là tránh hai request đồng thời cùng vượt qua bước kiểm tra trùng.

## 6.9. Transaction xử lý IPN

1. Xác minh chữ ký và đối chiếu dữ liệu MoMo.
2. Tìm payment theo `order_id` và khóa payment/contribution/booking.
3. Nếu payment đã có kết quả cuối cùng, trả response idempotent.
4. Cập nhật payment và contribution.
5. Tính lại tổng tiền thành công của booking.
6. Chuyển `PARTIALLY_PAID` hoặc `PAID` khi đúng điều kiện.
7. Cập nhật trạng thái match participant nếu đây là payment tham gia.
8. Commit một lần; lỗi thì rollback.

Không giữ transaction database mở trong lúc chờ HTTP call ra MoMo. Tạo bản ghi `PENDING`, commit, gọi MoMo, rồi xử lý kết quả trong transaction riêng.

## 6.10. Transaction refund

1. Service tính chính sách hoàn và tạo refund `PENDING` với request id duy nhất.
2. Commit refund intent trước khi gọi MoMo.
3. Gọi refund API ngoài transaction database dài.
4. Trong transaction mới, cập nhật refund và contribution.
5. Chỉ chuyển booking `CANCELLED` khi mọi refund bắt buộc đã `SUCCESS`.
6. Kết quả đang xử lý được query lại; retry phải idempotent.

## 6.11. Xử lý thời hạn

Tạo Flask CLI command hoặc worker định kỳ để:
- Hết hạn `CONFIRMED` chưa có khoản thanh toán đầu tiên sau 15 phút.
- Hết hạn yêu cầu tham gia chờ thanh toán quá 15 phút.
- Xử lý booking chia tiền còn thiếu tại mốc 12 giờ.
- Chuyển `PAID` sang `COMPLETED` sau giờ sử dụng.
- Query lại payment/refund chưa có kết quả cuối cùng.

Availability service cũng phải bỏ qua dữ liệu đã quá hạn theo timestamp ngay cả khi job định kỳ chưa chạy.

## 6.12. Nguyên tắc bảo mật và lỗi

- Bật CSRF cho form người dùng.
- IPN không dùng CSRF nhưng phải xác minh HMAC.
- Secret, connection string và MoMo key chỉ nằm trong biến môi trường.
- Không log password, secret key hoặc toàn bộ payload nhạy cảm.
- Backend luôn kiểm tra quyền và quyền sở hữu.
- Rollback khi commit thất bại.
- Hiển thị thông báo thân thiện cho user; ghi log kỹ thuật bằng correlation id.
