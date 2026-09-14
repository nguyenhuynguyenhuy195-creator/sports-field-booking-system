# 6. Kiến trúc hệ thống

> Phạm vi runtime hiện tại: Flask/Jinja/JavaScript gọi service và SQLAlchemy trên SQL Server; MOCK phục vụ phát triển/demo, VNPAY Sandbox được bật bằng cấu hình và MoMo đã bị vô hiệu hóa. Source, migration và test hiện hành là nguồn sự thật.

## 6.1. Kiến trúc tổng quát

```text
Browser
→ Flask Route / CLI Job
→ Service Layer
→ Repository query qua SQLAlchemy
→ SQL Server

Payment Service
→ Provider MOCK (phát triển và test)
→ Payment MOCK / Refund MOCK (transaction nội bộ, không gọi provider ngoài)

Browser
→ Flask nhận bộ lọc văn bản/khu vực
→ Venue Service truy vấn venue nội bộ
→ Liên kết ngoài mở Google Maps khi user yêu cầu chỉ đường
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
- Hiển thị địa chỉ hành chính và liên kết chỉ đường ngoài hệ thống.

Frontend không quyết định quyền, trạng thái availability cuối cùng, giá, tiền cọc, khoảng cách tin cậy, trạng thái payment hoặc refund.

## 6.3. Route Layer

Các blueprint hiện có gồm `main`, `auth`, `owner_applications`, `owner`, `venues`, `fields`, `pricing`, `maintenance`, `bookings`, `payments`, `matches`, `chatbot`, `notifications`, `media`, `admin` và `health`. Code hiện hỗ trợ danh mục đa môn, địa chỉ hành chính và liên kết chỉ đường Google Maps, ba booking mode, cọc 30%, `MOCK` và `VNPAY` Sandbox (MoMo chỉ giữ legacy disabled); booking lịch sử được giữ riêng bằng `LEGACY_FULL_ONLINE`.

Thiết kế đích của các blueprint chính:
- `auth`: đăng ký, đăng nhập, đăng xuất.
- `owner_applications`: gửi và xét duyệt yêu cầu owner.
- `owner`: dashboard và lịch vận hành của Chủ sân.
- `venues`: tìm/lọc theo sport, field type, giá, địa chỉ hành chính, `Sân gần tôi` và hiển thị venue.
- `fields`: quản lý field theo danh mục sport/field type.
- `media`: upload/xóa ảnh venue/field và chọn ảnh bìa.
- `bookings`: trả lịch trống theo ngày, báo giá, tạo giữ chỗ tự động, xem và hủy booking.
- `payments`: khởi tạo thanh toán MOCK/VNPAY, Return URL (chỉ đọc), IPN (mutate) và poll trạng thái; URL MoMo legacy bị chặn khi disabled. Refund được điều tra trong Booking Detail, không có blueprint riêng.
- `matches`: tạo kèo, tự giữ suất đối thủ, gửi/duyệt yêu cầu ghép người, xử lý rút và chat theo match.
- `chatbot`: nhận câu hỏi USER, trả lời bằng RAG chỉ đọc; không tạo/sửa/hủy booking hay payment.
- `notifications`: danh sách, đánh dấu đã đọc và poll số chưa đọc cho USER.
- `admin`: tài khoản, venue, booking (gồm điều tra payment/refund) và match; không còn workspace `/admin/monitoring`.

Route chỉ nhận request, kiểm tra authentication/authorization, validate form, gọi service và trả response.

Endpoint IPN (MoMo legacy và VNPAY) phải:
- Công khai qua HTTPS khi tích hợp sandbox.
- Miễn CSRF vì được gọi server-to-server.
- Bắt buộc xác minh chữ ký (HMAC với MoMo, secure hash với VNPAY) và idempotency trước khi thay đổi dữ liệu.

Return URL của trình duyệt (VNPAY) chỉ được đọc trạng thái Payment hiện có để hiển thị cho user; route Return URL không được tự quyết định hoặc ghi `SUCCESS`. Chỉ IPN đã xác minh chữ ký, đối chiếu mã tham chiếu và số tiền mới được phép mutate Payment/Contribution/Booking/MatchParticipant.

## 6.4. Service Layer

Các service chính:
- `pricing_service`: kiểm tra khung giá, tách thời lượng và tính snapshot giá.
- `availability_service`: sinh các đoạn 30 phút theo giờ hoạt động và phân loại từ booking, bảo trì, độ phủ giá, thời điểm hiện tại.
- `sport_catalog_service`: đọc danh mục sport/field type và validate quan hệ.
- `venue_service`: validate địa chỉ hành chính, tìm/lọc venue và tạo liên kết chỉ đường.
- `booking_service`: validate play format, tính mức cọc mục tiêu 30%, tạo booking, xử lý hủy/mất cọc và chuyển trạng thái.
- `contribution_service`: phân bổ tiền cọc creator/opponent; không tạo nghĩa vụ online cho người ghép.
- `payment_service`: tạo payment attempt, xử lý IPN và tổng tiền đã thu.
- `refund_service`: chỉ hoàn các khoản bắt buộc do owner/hệ thống hoặc trả lại cho bên không chủ động gây hủy; hoàn tiền MOCK hoàn tất ngay, refund VNPAY theo vòng đời `PENDING/PROCESSING/SUCCESS/FAILED`; nhánh MoMo chỉ giữ legacy disabled.
- `match_service`: tạo kèo, khóa match/contribution để tự giữ duy nhất một suất đối thủ trong 15 phút, duyệt yêu cầu FIND_PLAYERS, bảo vệ số Zalo, đóng bài theo giờ bắt đầu và mở lại vị trí khi hết hạn/rút.
- `match_chat_service`: kiểm tra quyền creator/participant `JOINED` trước khi đọc hoặc gửi `match_messages`, ghi các sự kiện hệ thống (tham gia, rút, đóng bài, hủy, hoàn tất) bằng `event_key` idempotent.
- `notification_service`: tạo notification USER-only sau khi transaction nghiệp vụ chính đã commit (best-effort, không rollback nghiệp vụ nếu lỗi), chống trùng bằng `(user_id, event_key)`, phục vụ chuông và poll ~30 giây.
- `owner_application_service`: xử lý yêu cầu chuyển role.
- `media_service`: upload, xóa và chọn ảnh bìa cho venue/field; mỗi ảnh chỉ thuộc một venue hoặc một field.
- `expiration_service`: hết hạn giữ chỗ đầu tiên, yêu cầu thanh toán đối thủ, bài tìm kèo và booking hoàn thành; funding deadline chỉ còn cho dữ liệu legacy.

Package `app/chatbot` (không đặt trong `app/services`) cung cấp chatbot RAG chỉ đọc: `retrieval.py` dùng LangChain `InMemoryVectorStore` (`langchain-core`) để tìm tài liệu `docs/chatbot` liên quan; `providers/gemini.py` gọi Gemini qua `google-genai` để sinh embedding (`gemini-embedding-001`) và câu trả lời; `context.py`/`context_gate.py` gắn ngữ cảnh động của user hiện tại và chặn câu hỏi ngoài phạm vi (evidence gate); `answering.py` tổng hợp câu trả lời có fallback xác định khi không đủ bằng chứng. Chatbot không có quyền gọi service ghi dữ liệu; không tạo, sửa, hủy booking/payment hoặc thao tác thay user.

Service chịu trách nhiệm kiểm tra quyền sở hữu, khóa dữ liệu cần thiết, quản lý transaction và rollback khi lỗi.

## 6.5. VNPAY Client và MoMo Client (legacy)

`app/integrations/vnpay.py` là lớp hạ tầng cho VNPAY Sandbox, không đặt trực tiếp trong route:
- Sinh URL thanh toán từ dữ liệu Payment đã persisted (amount, mã tham chiếu), không nhận amount từ form/query string của client.
- Ký và xác minh secure hash theo đúng thuật toán VNPAY.
- Xác minh chữ ký, đối chiếu mã tham chiếu và amount trước khi coi kết quả là hợp lệ.
- Chuẩn hóa timeout, response code và message.
- Không log secret hoặc dữ liệu nhạy cảm.

`VNPAY_ENABLED=true` và đủ cấu hình Sandbox mới bật được provider này; `payment_service` giữ MOCK làm fallback khi VNPAY tắt.

`app/integrations/momo.py` — LEGACY, không thuộc runtime hiện tại. MoMo Client vẫn giữ nguyên trách nhiệm cũ (raw signature, HMAC SHA-256, create/query payment, refund/query refund) nhưng bị chặn trước khi chạm DB/mạng khi `MOMO_ENABLED=false`.

Credential và endpoint của cả hai provider phải đọc từ biến môi trường, không commit vào Git. Sandbox và production phải tách cấu hình; runtime hiện tại chỉ bật sandbox.

## 6.6. Địa chỉ, bản đồ và tìm gần tôi

- Owner chọn tỉnh/thành phố và phường/xã từ catalog rồi nhập địa chỉ chi tiết.
- Endpoint chỉ dành cho Owner gọi Nominatim sau thao tác `Tìm vị trí`; kết quả geocoding là gợi ý, còn ghim Leaflet do Owner xác nhận mới là tọa độ tin cậy.
- Leaflet dùng tile tương thích OpenStreetMap với attribution; tile map và Nominatim geocoding là hai dịch vụ độc lập.
- Public map không geocode; chỉ dùng tọa độ Venue hợp lệ trong database. Venue thiếu tọa độ vẫn hiển thị bằng địa chỉ/fallback.
- `Sân gần tôi` chỉ gọi browser geolocation sau thao tác user; backend validate cặp latitude/longitude và tính Haversine, không dùng geospatial extension.
- Vị trí user không được lưu vào database, session, localStorage hoặc sessionStorage.
- Nút chỉ đường tạo URL Google Maps từ địa chỉ đầy đủ hiện tại.
- Frontend không tải Google Maps JavaScript API hoặc Places API.
- Không cần Maps API key trong cấu hình môi trường.

## 6.7. Model Layer

Trách nhiệm:
- Định nghĩa 20 bảng nghiệp vụ hiện tại và quan hệ trong `docs/05-database-design.md`.
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
├── chatbot/
│   ├── providers/
│   └── knowledge/
├── integrations/
│   ├── momo.py
│   └── vnpay.py
├── cli/
├── templates/
├── static/
├── extensions.py
└── __init__.py

tests/
├── unit/
└── integration/
```

JavaScript venue client-side chỉ quản lý bộ lọc phụ thuộc; logic validate địa chỉ và truy vấn nằm trong service, không đặt trong template hoặc route.

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

Áp dụng cho cả MoMo IPN (legacy, disabled) và VNPAY IPN (runtime hiện tại):

1. Xác minh chữ ký (HMAC với MoMo, secure hash với VNPAY) và đối chiếu dữ liệu provider.
2. Tìm payment theo `order_id`/mã tham chiếu và khóa payment/contribution/booking.
3. Nếu payment đã có kết quả cuối cùng, trả response idempotent — callback lặp không ghi trùng.
4. Đối chiếu amount với payment đã persisted trước khi chấp nhận kết quả.
5. Cập nhật payment và contribution.
6. Tính lại tổng tiền cọc thành công của booking.
7. Chuyển `PARTIALLY_PAID` hoặc `PAID` khi đúng điều kiện. `PARTIALLY_PAID` sau cọc creator FIND_OPPONENT đã là booking giữ sân hợp lệ.
8. Cập nhật match participant nếu đây là payment của đại diện đối thủ; người ghép không đi qua IPN.
9. Commit một lần; lỗi thì rollback.

Với VNPAY, Return URL (route trình duyệt quay về) chỉ được đọc trạng thái Payment hiện có để hiển thị; nó không xác minh chữ ký theo cùng mức độ IPN và không được coi là nguồn xác nhận giao dịch. IPN là đường duy nhất được phép chuyển Payment sang `SUCCESS`/`FAILED`; success đến muộn sau khi booking đã bị hủy vẫn được ghi nhận rồi tạo refund theo rule hiện hành thay vì bị bỏ qua.

Thiết kế legacy mong muốn cho MoMo (chưa là bảo đảm implementation, xem H04–H07/M01 audit cũ): không giữ transaction database mở trong lúc chờ HTTP call ra MoMo. Tạo bản ghi `PENDING`, commit, gọi MoMo, rồi xử lý kết quả trong transaction riêng.

## 6.12. Transaction refund

1. Service xác định đây là trường hợp được hoàn (owner hủy, lỗi/thu trùng hệ thống hoặc trả lại bên không chủ động gây hủy) rồi tạo refund `PENDING` với request id duy nhất.
2. Refund MOCK hoàn tất ngay trong transaction. Refund MoMo (legacy) commit refund intent trước khi gọi MoMo, gọi refund API ngoài transaction database dài rồi cập nhật trong transaction mới. Refund VNPAY đi qua vòng đời `PENDING → PROCESSING → SUCCESS/FAILED`; `PROCESSING` bị kẹt được đối soát thủ công vì VNPAY queryDr không định danh chắc chắn một refund cụ thể.
3. Cập nhật refund và contribution cùng transaction với bước ghi kết quả.
4. Chỉ chuyển booking `CANCELLED` khi mọi refund bắt buộc đã `SUCCESS`.
5. Kết quả đang xử lý được query lại; retry phải idempotent.
6. Payment gốc luôn giữ nguyên `SUCCESS`; không đổi thành `REFUNDED`. Mỗi lần hoàn là một bản ghi `refunds` riêng.

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
- IPN không dùng CSRF nhưng phải xác minh chữ ký (HMAC với MoMo, secure hash với VNPAY).
- Secret, connection string, MoMo key và VNPAY hash secret/TMN code chỉ nằm trong biến môi trường, không commit vào Git.
- Liên kết Google Maps không chứa API key; `google_place_id` không được dùng trong form mới. Latitude/longitude nằm ở trường ẩn và chỉ được lưu sau khi Owner xác nhận ghim.
- Không log password, secret key, Gemini API key hoặc toàn bộ payload nhạy cảm.
- Không log/công khai số điện thoại của hai bên. Service lưu snapshot có sự đồng ý và template chỉ trả số khi participant `JOINED`, booking còn hiệu lực và user hiện tại là creator hoặc chính participant đó.
- Trang lịch cá nhân hợp nhất booking do user tạo với match user đã `JOINED`; match tham gia là liên kết chỉ xem, không làm thay đổi kiểm tra quyền sở hữu booking ở service.
- Chatbot chỉ đọc dữ liệu allowlist của chính user đang đăng nhập (không phải ORM object thô, không lộ order/request/transaction id, checkout URL hay dữ liệu người khác) và không thể gọi service ghi dữ liệu.
- Backend luôn kiểm tra quyền và quyền sở hữu.
- Rollback khi commit thất bại.
- Hiển thị thông báo thân thiện cho user; ghi log kỹ thuật bằng correlation id.
