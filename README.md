# Sports Field Booking System

## 1. Giới thiệu

Sports Field Booking System là website quản lý đặt sân thể thao đa môn, tìm địa điểm theo vị trí, đặt sân và tìm kèo trực tuyến. MVP mục tiêu hỗ trợ bóng đá, cầu lông, pickleball và tennis; kết nối người chơi, chủ sân và quản trị viên.

## 2. Luồng nghiệp vụ chính

```text
Đăng ký hoặc đăng nhập
→ Tìm cơ sở theo từ khóa, bộ môn hoặc vị trí xung quanh
→ Xem chi tiết
→ Chọn sân con, thời gian và hình thức thi đấu
→ Đặt sân
→ Hệ thống kiểm tra và giữ chỗ 15 phút
→ Thanh toán khoản cọc đầu tiên qua MoMo Sandbox
→ Tạo kèo nếu cần
→ Đối thủ cọc phần cam kết hoặc người ghép để lại số Zalo
→ Thanh toán số còn lại tại sân
```

Ba hình thức booking mục tiêu:
- `DIRECT_BOOKING`: người đặt thanh toán toàn bộ khoản cọc 30%.
- `FIND_OPPONENT`: creator trả 15% tổng tiền sân để giữ booking; đối thủ bấm nhận kèo, giữ suất 15 phút và trả thêm 15% để tự động tham gia, không cần creator duyệt. Không tìm được đối thủ không làm hủy booking.
- `FIND_PLAYERS`: người đặt thanh toán toàn bộ khoản cọc 30%; người ghép không thanh toán online và trả trực tiếp tại sân.

Với `FIND_OPPONENT`, bài tìm đối thủ tồn tại đến giờ trận bắt đầu. Nếu không có đối thủ, creator vẫn giữ sân và trả 85% còn lại tại sân; nếu đối thủ đã cọc, hai bên đã thanh toán tổng cộng 30% và còn 70% tại sân. Người chủ động hủy/rút hoặc no-show không được hoàn phần cọc của mình. Refund chỉ áp dụng khi chủ sân hủy, lỗi/thu trùng phía hệ thống hoặc cần trả lại tiền cho bên không có lỗi.

Đích MVP dùng MoMo Sandbox cho payment/refund ngoại lệ; MoMo Production, QR ngân hàng thật, ví admin và chức năng owner rút tiền không thuộc phạm vi đồ án ngành. Provider `MOCK` tiếp tục phục vụ phát triển và test tự động.

## 3. Công nghệ

### Backend
- Python
- Flask
- Flask-SQLAlchemy
- Flask-Migrate
- Flask-Login
- Flask-WTF

### Frontend
- HTML
- CSS
- Bootstrap 5
- Jinja2
- JavaScript

### Database
- Microsoft SQL Server
- pyodbc

## 4. Cấu trúc thư mục

```text
app/
├── models/
├── forms/
├── routes/
├── services/
├── integrations/
├── cli/
├── templates/
├── static/
├── extensions.py
└── __init__.py

docs/
tests/
migrations/
```

## 5. Cài đặt

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Sao chép `.env.example` thành `.env` và cập nhật thông tin SQL Server. Không commit `.env` hoặc secret key. Nếu dùng bản đồ, điền `GOOGLE_MAPS_BROWSER_API_KEY` đã giới hạn theo HTTP referrer và Maps JavaScript/Places API.

Mặc định `MOMO_ENABLED=false`, nên môi trường local tiếp tục dùng provider `MOCK` và không trừ tiền thật. Để kiểm thử MoMo Sandbox, cần bộ khóa M4B Sandbox và hai URL HTTPS công khai, sau đó cấu hình `MOMO_PARTNER_CODE`, `MOMO_ACCESS_KEY`, `MOMO_SECRET_KEY`, `MOMO_REDIRECT_URL`, `MOMO_IPN_URL` và đổi `MOMO_ENABLED=true`.

Cấu hình development hiện dùng Windows Authentication với SQL Server mặc định trên `localhost`. Database khởi tạo là `sports_field_booking`.

## 6. Chạy ứng dụng

Khởi tạo hoặc cập nhật cấu trúc database trước lần chạy đầu tiên:

```bash
.\.venv\Scripts\python.exe -m flask --app run.py db upgrade
```

Lệnh trên đọc các migration trong `migrations/` và áp dụng chúng theo đúng thứ tự. Các migration hiện tại tạo thêm danh mục `sports`, `field_types`, vị trí Maps của venue, snapshot chính sách cọc trên booking và URL checkout MoMo trên payment. Bảng `alembic_version` do Flask-Migrate dùng để ghi nhận phiên bản database.

Sau đó chạy website:

```bash
.\.venv\Scripts\python.exe -m flask --app run.py run
```

Kiểm tra ứng dụng:

```text
GET http://127.0.0.1:5000/health
GET http://127.0.0.1:5000/health/ready
GET http://127.0.0.1:5000/auth/register
GET http://127.0.0.1:5000/auth/login
GET http://127.0.0.1:5000/venues
```

`/health` kiểm tra tiến trình Flask. `/health/ready` chạy `SELECT 1` để xác nhận SQL Server sẵn sàng. Hai trang `/auth/register` và `/auth/login` cung cấp chức năng tài khoản đầu tiên của hệ thống.

## 7. Trạng thái triển khai

Ba giai đoạn đã được triển khai vào model, migration, service, route, giao diện và test: danh mục đa môn + Google Maps; booking theo chính sách cọc 30%; MoMo Sandbox với HMAC, redirect, IPN, query và refund. Dữ liệu payment cũ được giữ nhãn `LEGACY_FULL_ONLINE`, không đổi nghĩa thành cọc 30%. Kết nối MoMo thật trên Sandbox chỉ hoạt động khi người triển khai cung cấp credential M4B và URL HTTPS công khai; nếu chưa có, hệ thống chủ động giữ `MOCK`.

**Cập nhật ngày 14/08/2026:** chính sách `FIND_OPPONENT` mới theo ADR-027 đã được triển khai: cọc 15% của creator đủ giữ sân, bài tìm đối thủ tồn tại đến giờ bắt đầu, không có top-up bắt buộc và người chủ động hủy không được hoàn cọc. Booking legacy có deadline vẫn được diễn giải theo chính sách cũ.

**Cập nhật ADR-028:** đối thủ của booking mới không gửi yêu cầu chờ creator duyệt. Thao tác “Nhận kèo” khóa duy nhất contribution đối thủ trong tối đa 15 phút; payment thành công chuyển thẳng participant sang `JOINED`. `FIND_PLAYERS` vẫn giữ bước creator xác nhận.

**Cập nhật ADR-029:** người đăng kèo và người nhận/ghép kèo đều cung cấp số Zalo và đồng ý chia sẻ trong phạm vi kèo. Chỉ sau khi participant ở trạng thái `JOINED` và booking còn hiệu lực, hai bên mới thấy số của nhau. Kèo đã tham gia xuất hiện trong “Lịch & kèo của tôi” nhưng không cấp quyền quản lý booking của người tạo.

### 7.1. Chức năng hiện đã triển khai

- Đăng ký tài khoản người chơi bằng họ tên, email, số điện thoại tùy chọn và mật khẩu.
- Chuẩn hóa email, kiểm tra email không trùng và lưu mật khẩu ở dạng băm.
- Đăng nhập, ghi nhớ đăng nhập và đăng xuất bằng biểu mẫu POST có CSRF.
- Từ chối đăng nhập đối với tài khoản bị khóa hoặc ngừng hoạt động.
- Phân quyền nền tảng `USER`, `OWNER`, `ADMIN` ở phía backend.
- Người chơi gửi và theo dõi yêu cầu trở thành chủ sân.
- Admin chấp nhận hoặc từ chối yêu cầu; khi chấp nhận, tài khoản được chuyển thành `OWNER` trong cùng transaction.
- Lệnh CLI tạo tài khoản admin đầu tiên mà không mở đăng ký admin công khai.
- Giao diện responsive dùng Jinja2, Bootstrap 5 và CSS riêng.
- OWNER tạo, sửa và xem danh sách cơ sở của chính mình; venue mới luôn chờ admin duyệt.
- ADMIN duyệt công khai hoặc ẩn venue và hệ thống lưu dấu vết kiểm duyệt.
- Khách chỉ xem được danh sách và chi tiết venue có trạng thái `ACTIVE`.
- Danh sách công khai cho tìm theo tên/địa chỉ/quận-thành phố, lọc loại sân và khoảng “giá từ”; chỉ field `ACTIVE` tham gia bộ lọc, kết quả được phân trang và giữ nguyên điều kiện khi chuyển trang.
- OWNER tạo, sửa và xem các sân con thuộc cơ sở của chính mình; sân mới luôn có trạng thái `INACTIVE`.
- Tên sân không được trùng trong cùng một cơ sở; khách chỉ thấy sân `ACTIVE` thuộc cơ sở `ACTIVE`.
- OWNER cấu hình giá theo sân, ngày trong tuần và khoảng giờ; các khung giá `ACTIVE` cùng ngày không được chồng nhau.
- Field chỉ được bật `ACTIVE` khi có khung giá hợp lệ; hệ thống có thể tách nhiều khung để tính đủ giá cho một khoảng thời gian.
- OWNER tạo và hủy lịch bảo trì theo sân, ngày và khoảng giờ; các lịch `ACTIVE` cùng sân không được chồng nhau.
- Lịch bảo trì hết giờ được hiển thị là đã hoàn thành và lịch đã hủy không còn chặn khoảng thời gian.
- USER/OWNER đặt field `ACTIVE`; backend kiểm tra bước 30 phút, thời lượng tối thiểu, giới hạn đặt trước, giờ mở cửa, bảo trì và booking trùng rồi tự động giữ chỗ 15 phút.
- Trang đặt sân tải lưới mốc giờ 30 phút theo ngày, phân biệt còn trống, đã đặt, bảo trì, thiếu giá và thời gian đã qua; user chọn mốc bắt đầu/kết thúc liên tục tối thiểu 60 phút và xem tạm tính ngay trên màn hình.
- Booking lưu snapshot từng đoạn giá và tổng tiền từ database, không nhận giá từ frontend.
- Người chơi xem báo giá trước khi xác nhận, theo dõi lịch sử/chi tiết và hủy booking hợp lệ; chủ sân theo dõi hoặc hủy booking khi có sự cố theo quyền sở hữu.
- Lệnh `flask bookings expire` cập nhật idempotent các booking giữ chỗ đã quá hạn thanh toán đầu tiên.
- Khi tạo booking, backend dùng `DIRECT_BOOKING`, `FIND_OPPONENT` hoặc `FIND_PLAYERS`, snapshot cọc 30% và phần 70% trả tại sân; booking lịch sử vẫn giữ chính sách cũ.
- Với `FIND_OPPONENT`, người tạo và đại diện đối thủ mỗi bên thanh toán 15% tổng tiền sân. Với `FIND_PLAYERS`, người tạo thanh toán cả khoản cọc 30%, còn người ghép trả tại sân.
- Provider `MOCK` và MoMo Sandbox cùng tuân theo giới hạn khoản cọc, chống thu lặp và chuyển `PARTIALLY_PAID`/`PAID`; trạng thái chỉ đổi sau kết quả hợp lệ.
- Người tạo mở tối đa một kèo từ booking đủ điều kiện; bộ môn vợt bắt buộc chọn `SINGLES` hoặc `DOUBLES` và chỉ `DOUBLES` mới được tìm thêm người.
- Người đăng và người xin tham gia đều cung cấp số điện thoại dùng Zalo, đồng ý chia sẻ có điều kiện; hai bên chỉ xem được số của nhau sau khi participant chính thức `JOINED`.
- Với FIND_OPPONENT mới, đội bấm nhận kèo tự giữ vị trí thanh toán tối đa 15 phút nhưng không vượt giờ trận bắt đầu; payment thành công là tự động tham gia. Người ghép FIND_PLAYERS không có bước thanh toán online và vẫn cần creator xác nhận.
- Người đã `JOINED` thấy kèo trong “Lịch & kèo của tôi” và mở chi tiết để liên hệ; họ không được xem/sửa/hủy booking với tư cách chủ booking.
- Lệnh `flask matches expire` xử lý idempotent các suất đối thủ giữ quá hạn thanh toán.
- Chủ sân hủy booking đã thu cọc sẽ hoàn 100% khoản đã thu. Refund `MOCK` hoàn tất ngay; refund MoMo được lưu `PENDING` trước khi gọi API và chỉ hoàn tất booking khi các khoản bắt buộc thành công.
- Payment gốc tiếp tục giữ `SUCCESS`; mỗi lần hoàn được lưu riêng trong `refunds`, cập nhật số tiền cọc ròng của contribution/booking và hiển thị trên trang chi tiết.
- Lệnh `flask refunds funding-expire` chỉ xử lý booking legacy có `funding_deadline`; booking ADR-027 mới không đi qua luồng này.
- Lệnh `flask bookings complete` hoàn tất booking đã qua giờ sử dụng, gồm FIND_OPPONENT chỉ có phần cọc creator nhưng booking vẫn hợp lệ.
- Lệnh `flask refunds momo-pending` query/thử lại các refund MoMo còn chờ xử lý theo hướng idempotent.

### 7.2. Phạm vi đã chốt và giới hạn môi trường

- Danh mục `sports` và `field_types` hỗ trợ bóng đá, cầu lông, pickleball và tennis.
- Mỗi field thuộc đúng một loại sân và qua đó thuộc đúng một bộ môn.
- Cầu lông, pickleball và tennis chọn `SINGLES` hoặc `DOUBLES` khi booking.
- Venue lưu Google Place ID và tọa độ để ghim bản đồ, mở chỉ đường và tìm sân trong bán kính 3/5/10 km.
- DIRECT_BOOKING/FIND_PLAYERS thu cọc 30%; FIND_OPPONENT thu 15% từ creator và thêm 15% nếu có đối thủ.
- Số còn lại tại sân bằng tổng tiền trừ số cọc online thực thu: 85% khi FIND_OPPONENT chưa có đối thủ, 70% khi đã đủ hai phía.
- Kèo tìm đối thủ chia đôi khoản cọc; kèo tìm thêm người chỉ thu cọc từ người tạo.
- Người ghép để lại số điện thoại dùng Zalo; số chỉ hiện cho người tạo sau khi yêu cầu được chấp nhận.
- Chưa thể xác nhận giao dịch MoMo Sandbox đầu-cuối nếu chưa có credential M4B và URL HTTPS công khai.
- Không triển khai chấm điểm, phạt no-show, MoMo Production, QR ngân hàng thật, ví admin hoặc payout trong MVP.

Tạo tài khoản quản trị viên đầu tiên:

```bash
.\.venv\Scripts\python.exe -m flask --app run.py users create-admin
```

Lệnh sẽ hỏi họ tên, email và mật khẩu. Mật khẩu được nhập ẩn và được lưu dưới dạng băm.

## 8. Chạy kiểm thử

```bash
.\.venv\Scripts\python.exe -m pytest
```

## 9. Tài liệu quan trọng

Tài liệu dự án nên được đọc theo thứ tự:
1. `docs/01-project-overview.md`
2. `docs/02-scope-mvp.md`
3. `docs/03-business-rules.md`
4. `docs/04-booking-workflow.md`
5. `docs/05-database-design.md`
6. `docs/06-system-architecture.md`
7. `docs/07-ui-requirements.md`
8. `docs/08-acceptance-criteria.md`
9. `docs/09-test-cases.md`
10. `docs/10-decision-log.md`
