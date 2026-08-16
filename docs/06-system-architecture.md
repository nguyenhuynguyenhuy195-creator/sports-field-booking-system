# 6. Kiến trúc hệ thống

## 6.1. Kiến trúc tổng quát

```text
Browser
→ Flask Route / MoMo IPN Endpoint / CLI Job
→ Service Layer
→ Repository query qua SQLAlchemy
→ SQL Server

Payment Service
→ Provider MOCK (phát triển và test)
→ MoMo Client → MoMo Sandbox API (bật bằng cấu hình môi trường)

Browser
→ Google Maps JavaScript / Places Autocomplete
→ Flask nhận place ID và tọa độ đã validate
→ Location Service lọc venue nội bộ theo bán kính
```

Flask render giao diện bằng Jinja2. Nghiệp vụ không được đặt toàn bộ trong route.

## 6.2. Presentation Layer

Công nghệ: HTML, CSS, Bootstrap 5, Jinja2 và JavaScript thuần khi cần.

Trách nhiệm:
- Hiển thị dữ liệu và trạng thái.
- Nhận input và hiển thị validation.
- Gửi request đến backend.
- Render lưới mốc giờ từ dữ liệu availability và gửi khoảng đã chọn sang endpoint quote.
- Hiển thị countdown thanh toán đầu tiên, mức cọc mục tiêu 30%, số đã cọc và số còn lại tại sân từ dữ liệu backend. FIND_OPPONENT có thể còn 85% hoặc 70% tại sân tùy cọc thực thu.
- Hiển thị Places Autocomplete, bản đồ/marker và xin quyền Geolocation khi user chủ động yêu cầu.

Frontend không quyết định quyền, trạng thái availability cuối cùng, giá, tiền cọc, khoảng cách tin cậy, trạng thái payment hoặc refund.

## 6.3. Route Layer

Các blueprint hiện có gồm `auth`, `owner_applications`, `venues`, `fields`, `pricing`, `maintenance`, `bookings`, `payments`, `matches` và health checks. Code hiện hỗ trợ danh mục đa môn, vị trí Google Maps, ba booking mode, cọc 30%, `MOCK` và MoMo Sandbox; booking lịch sử được giữ riêng bằng `LEGACY_FULL_ONLINE`.

Thiết kế đích của các blueprint thanh toán:
- `auth`: đăng ký, đăng nhập, đăng xuất.
- `owner_applications`: gửi và xét duyệt yêu cầu owner.
- `venues`: tìm/lọc theo sport, field type, giá, vị trí và hiển thị venue.
- `fields`: quản lý field theo danh mục sport/field type.
- `bookings`: trả lịch trống theo ngày, báo giá, tạo giữ chỗ tự động, xem và hủy booking.
- `payments`: bắt đầu thanh toán, redirect và IPN MoMo.
- `refunds`: yêu cầu/query refund theo quyền.
- `matches`: tạo kèo, tự giữ suất đối thủ, gửi/duyệt yêu cầu ghép người và xử lý rút.
- `admin`: tài khoản, venue, booking, payment, refund và match.

Route chỉ nhận request, kiểm tra authentication/authorization, validate form, gọi service và trả response.

Endpoint IPN phải:
- Công khai qua HTTPS khi tích hợp sandbox.
- Miễn CSRF vì được gọi server-to-server.
- Bắt buộc xác minh HMAC và idempotency trước khi thay đổi dữ liệu.

## 6.4. Service Layer

Các service chính:
- `pricing_service`: kiểm tra khung giá, tách thời lượng và tính snapshot giá.
- `availability_service`: sinh các đoạn 30 phút theo giờ hoạt động và phân loại từ booking, bảo trì, độ phủ giá, thời điểm hiện tại.
- `sport_catalog_service`: đọc danh mục sport/field type và validate quan hệ.
- `location_service`: validate tọa độ, tạo bounding box/tính khoảng cách và sắp xếp venue nội bộ.
- `booking_service`: validate play format, tính mức cọc mục tiêu 30%, tạo booking, xử lý hủy/mất cọc và chuyển trạng thái.
- `contribution_service`: phân bổ tiền cọc creator/opponent; không tạo nghĩa vụ online cho người ghép.
- `payment_service`: tạo payment attempt, xử lý IPN và tổng tiền đã thu.
- `refund_service`: chỉ hoàn các khoản bắt buộc do owner/hệ thống hoặc trả lại cho bên không chủ động gây hủy; gọi/query MoMo và hoàn tất hủy.
- `match_service`: tạo kèo, khóa match/contribution để tự giữ duy nhất một suất đối thủ trong 15 phút, duyệt yêu cầu FIND_PLAYERS, bảo vệ số Zalo, đóng bài theo giờ bắt đầu và mở lại vị trí khi hết hạn/rút.
- `owner_application_service`: xử lý yêu cầu chuyển role.
- `expiration_service`: hết hạn giữ chỗ đầu tiên, yêu cầu thanh toán đối thủ, bài tìm kèo và booking hoàn thành; funding deadline chỉ còn cho dữ liệu legacy.

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

## 6.6. Google Maps và Places

- Maps JavaScript API hiển thị bản đồ/marker ở frontend.
- Places API (New) hỗ trợ autocomplete địa chỉ của owner.
- Browser Geolocation chỉ chạy khi user bấm cho phép.
- Backend chỉ tìm trong bảng `venues`; không dùng Nearby Search để nhập địa điểm ngoài hệ thống.
- Tọa độ từ request được validate trước khi lưu hoặc tính khoảng cách.
- Danh sách theo bán kính phải lọc/sắp xếp trước khi phân trang; MVP có thể dùng bounding box rồi Haversine trong service.
- API key browser được giới hạn HTTP referrer và API; server key nếu có dùng biến môi trường.

## 6.7. Model Layer

Trách nhiệm:
- Định nghĩa 15 bảng mục tiêu và quan hệ trong `docs/05-database-design.md`.
- Khai báo primary key, foreign key, unique/check constraint và index.
- Dùng `DECIMAL` cho tiền và `DATETIME2` cho timestamp UTC.
- Không chứa orchestration nghiệp vụ dài trong model.

## 6.8. Cấu trúc thư mục dự kiến

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

Google Maps client-side nằm trong `static/js`; logic validate/tìm khoảng cách nằm trong service, không đặt trong template hoặc route.

## 6.9. API lịch trống và báo giá

1. Frontend gửi ngày đã chọn đến endpoint availability.
2. Service lấy giờ mở/đóng từ venue và sinh các đoạn 30 phút nằm trọn trong cùng ngày.
3. Service truy vấn theo lô booking chiếm chỗ, bảo trì `ACTIVE` và khung giá `ACTIVE`, rồi gán trạng thái cho từng đoạn.
4. Frontend chỉ cho chọn một khoảng liên tục tối thiểu 60 phút và gửi khoảng đó đến endpoint quote.
5. Quote kiểm tra lại thời gian, trùng lịch, bảo trì và độ phủ giá rồi trả các đoạn giá/tổng tiền nhưng không tạo dữ liệu.

Availability và quote không khóa chỗ. Transaction tạo booking bên dưới luôn lặp lại toàn bộ kiểm tra để xử lý trường hợp dữ liệu thay đổi sau khi user xem lịch.

## 6.10. Transaction tạo booking

1. Route validate form và gọi service.
2. Service khóa phạm vi dữ liệu cần kiểm tra của field/ngày.
3. Kiểm tra field, venue, giờ hoạt động và bảo trì.
4. Truy vấn booking chiếm chỗ giao nhau.
5. Truy vấn toàn bộ khung giá và kiểm tra độ phủ.
6. Validate sport/play format/booking mode, tính total và snapshot mức cọc mục tiêu 30%.
7. Tạo booking `CONFIRMED`, initial_payment_due_at, price details và contribution tiền cọc. FIND_OPPONENT theo ADR-027 không tạo matchmaking/funding deadline.
8. Commit một lần; lỗi thì rollback.

Mục tiêu là tránh hai request đồng thời cùng vượt qua bước kiểm tra trùng.

## 6.11. Transaction xử lý IPN

1. Xác minh chữ ký và đối chiếu dữ liệu MoMo.
2. Tìm payment theo `order_id` và khóa payment/contribution/booking.
3. Nếu payment đã có kết quả cuối cùng, trả response idempotent.
4. Cập nhật payment và contribution.
5. Tính lại tổng tiền cọc thành công của booking.
6. Chuyển `PARTIALLY_PAID` hoặc `PAID` khi đúng điều kiện. `PARTIALLY_PAID` sau cọc creator FIND_OPPONENT đã là booking giữ sân hợp lệ.
7. Cập nhật match participant nếu đây là payment của đại diện đối thủ; người ghép không đi qua IPN.
8. Commit một lần; lỗi thì rollback.

Không giữ transaction database mở trong lúc chờ HTTP call ra MoMo. Tạo bản ghi `PENDING`, commit, gọi MoMo, rồi xử lý kết quả trong transaction riêng.

## 6.12. Transaction refund

1. Service xác định đây là trường hợp được hoàn (owner hủy, lỗi/thu trùng hệ thống hoặc trả lại bên không chủ động gây hủy) rồi tạo refund `PENDING` với request id duy nhất.
2. Commit refund intent trước khi gọi MoMo.
3. Gọi refund API ngoài transaction database dài.
4. Trong transaction mới, cập nhật refund và contribution.
5. Chỉ chuyển booking `CANCELLED` khi mọi refund bắt buộc đã `SUCCESS`.
6. Kết quả đang xử lý được query lại; retry phải idempotent.

## 6.13. Xử lý thời hạn

Tạo Flask CLI command hoặc worker định kỳ để:
- Hết hạn `CONFIRMED` chưa có khoản thanh toán đầu tiên sau 15 phút.
- Hết hạn suất đối thủ tự giữ nhưng chưa thanh toán sau 15 phút hoặc tại giờ booking bắt đầu, tùy mốc nào đến trước.
- Tại giờ bắt đầu, đóng hiệu lực bài FIND_OPPONENT và hết hạn các yêu cầu chưa hoàn tất nhưng không hủy booking.
- Không mở creator top-up và không xử lý thiếu cọc đối thủ cho booking ADR-027; job funding-expire chỉ xử lý booking legacy còn deadline.
- Chuyển `PAID` và FIND_OPPONENT `PARTIALLY_PAID` hợp lệ sang `COMPLETED` sau giờ sử dụng.
- Query lại payment/refund chưa có kết quả cuối cùng.

Availability service cũng phải bỏ qua dữ liệu đã quá hạn theo timestamp ngay cả khi job định kỳ chưa chạy.

## 6.14. Nguyên tắc bảo mật và lỗi

- Bật CSRF cho form người dùng.
- IPN không dùng CSRF nhưng phải xác minh HMAC.
- Secret, connection string và MoMo key chỉ nằm trong biến môi trường.
- Google Maps browser key phải bị giới hạn theo referrer/API; server key không được đưa vào template hoặc Git.
- Không log password, secret key hoặc toàn bộ payload nhạy cảm.
- Không log/công khai số điện thoại của hai bên. Service lưu snapshot có sự đồng ý và template chỉ trả số khi participant `JOINED`, booking còn hiệu lực và user hiện tại là creator hoặc chính participant đó.
- Trang lịch cá nhân hợp nhất booking do user tạo với match user đã `JOINED`; match tham gia là liên kết chỉ xem, không làm thay đổi kiểm tra quyền sở hữu booking ở service.
- Backend luôn kiểm tra quyền và quyền sở hữu.
- Rollback khi commit thất bại.
- Hiển thị thông báo thân thiện cho user; ghi log kỹ thuật bằng correlation id.
