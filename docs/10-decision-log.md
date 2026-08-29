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

**Trạng thái:** Được thay thế bởi ADR-023 và ADR-024 cho booking mới; giữ để giải thích dữ liệu/code lịch sử.

- `FULL_PAYMENT`: người tạo trả 100%.
- `SPLIT_OPPONENT`: hai đội chia 50/50.
- `SPLIT_PLAYERS`: chia theo đầu người; người tạo trả phần nhóm có sẵn, người ghép trả phần của họ.

Thành viên có sẵn không bắt buộc tạo tài khoản. Người tạo có thể trả phần còn thiếu trước funding deadline; booking đủ tiền không tự làm kèo đủ người, và người tham gia sau đó không phải đóng thêm.

## ADR-008: Thời hạn booking và góp tiền

**Trạng thái:** Quy tắc 12/13 giờ được thay thế bởi ADR-027; giữ 15 phút cho khoản thanh toán đầu tiên/đối thủ và giới hạn đặt trước của từng booking mode.

- Booking thường đặt trước tối thiểu 60 phút; booking chia tiền tối thiểu 13 giờ; tối đa 30 ngày.
- Booking hợp lệ được giữ chỗ tự động; khoản thanh toán đầu tiên và payment của người được chấp nhận có hạn 15 phút.
- Booking chia tiền phải đủ trước giờ bắt đầu 12 giờ.

## ADR-009: Chính sách không góp đủ và hoàn tiền

**Trạng thái:** Được thay thế bởi ADR-027 cho booking mới; giữ để giải thích refund 80/20 của dữ liệu/code lịch sử.

- Không góp đủ đúng hạn: creator được hoàn 80%, 20% khoản creator đã đóng là phí giữ sân cho owner.
- Đối thủ/người ghép đã thanh toán đúng hạn được hoàn 100%.
- Owner hủy vì sự cố: hoàn 100% cho mọi người đã thanh toán.
- Chính sách owner hủy áp dụng cho cả booking `PARTIALLY_PAID` và `PAID`; booking chưa thu tiền không cần tạo refund.
- Refund là bản ghi riêng; không xóa hoặc ghi đè payment gốc.

## ADR-010: Chính sách rút khỏi kèo và no-show

**Trạng thái:** Được thay thế bởi ADR-024 đối với FIND_PLAYERS và ADR-027 đối với FIND_OPPONENT.

- Rút trước giờ bắt đầu trên 12 giờ: hoàn 100% và mở lại vị trí.
- Rút trong vòng 12 giờ hoặc no-show: không hoàn tiền.
- MVP chưa theo dõi điểm no-show hoặc tự động khóa tài khoản.

## ADR-011: Venue, field và bảo trì

- Venue mới `PENDING`, admin duyệt mới `ACTIVE`.
- Venue lưu người duyệt, thời điểm duyệt và ghi chú kiểm duyệt; tên field không được trùng trong cùng venue.
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

## ADR-015: Chốt ERD và ràng buộc SQL Server

**Trạng thái:** Số bảng và ERD được thay thế bởi ADR-022; nguyên tắc SQL Server/lịch sử vẫn còn hiệu lực.

- MVP sử dụng 13 bảng nghiệp vụ; chưa thêm notification, team, review, payout hoặc audit log riêng.
- Dữ liệu giao dịch dùng foreign key `NO ACTION` và chuyển trạng thái thay vì cascade delete.
- Unique trên mã giao dịch nullable và unique theo trạng thái phải dùng filtered unique index phù hợp SQL Server.
- `payments` và `refunds` là lịch sử tiền gốc; số tiền tại contribution và booking là dữ liệu tổng hợp cập nhật trong cùng transaction.
- Nguồn ERD được lưu cùng repository và phải đồng bộ với `docs/05-database-design.md` trước khi tạo migration.

## ADR-016: Tự động xác nhận và giữ chỗ booking

**Ngày quyết định:** 08/08/2026

- Bỏ bước owner xác nhận/từ chối đối với booking thông thường vì backend đã kiểm tra trạng thái sân, giờ hoạt động, bảo trì, độ phủ giá và trùng lịch trong transaction.
- Booking hợp lệ được tạo trực tiếp ở `CONFIRMED` và giữ chỗ 15 phút để người tạo hoàn thành khoản thanh toán đầu tiên.
- Quá hạn mà chưa thu tiền thì booking chuyển `EXPIRED` và giải phóng lịch; job hết hạn phải idempotent.
- Owner vẫn xem được booking và chỉ hủy khi có sự cố, bắt buộc nhập lý do; booking đã thu tiền phải đi qua quy trình refund.
- Trang đặt sân dùng bốn bước, lấy thông tin người đặt từ tài khoản và gọi backend báo giá trước khi submit; backend vẫn tính lại toàn bộ khi tạo booking.

## ADR-017: Nền tảng contribution và provider thanh toán mô phỏng

**Trạng thái:** Phân bổ SPLIT_PLAYERS được thay thế bởi ADR-023/024; top-up bắt buộc được thay thế bởi ADR-027; provider MOCK và nguyên tắc lịch sử vẫn còn hiệu lực.

**Ngày quyết định:** 08/08/2026

- Tạo contribution ngay trong transaction tạo booking để tổng nghĩa vụ luôn khớp `total_amount`.
- `SPLIT_PLAYERS` chụp lại sức chứa field và số người còn thiếu tại thời điểm booking; thành viên sẵn có không cần tài khoản riêng.
- Vị trí đối thủ/người ghép chưa được nhận có `user_id = NULL` và `slot_number` duy nhất; module matchmaking sẽ gắn tài khoản sau.
- Provider `MOCK` dùng để kiểm chứng quyền, deadline, chống thu dư và chuyển trạng thái trước khi nối MoMo Sandbox; giao diện phải nói rõ không trừ tiền thật.
- Khi creator top-up, nghĩa vụ còn lại chuyển `WAIVED` nhưng không sửa số tiền gốc; tạo contribution `TOP_UP` riêng để lịch sử đối soát không bị mất.
- Migration phải backfill contribution cho booking cũ và được chạy/kiểm tra trực tiếp trên SQL Server.

## ADR-018: Lưới mốc giờ availability cho booking

**Ngày quyết định:** 10/08/2026

- Endpoint availability trả trạng thái theo từng đoạn 30 phút, được tính từ giờ hoạt động của venue, booking chiếm chỗ, bảo trì `ACTIVE` và độ phủ giá.
- Giao diện hiển thị các mốc thời gian: user chọn mốc bắt đầu rồi mốc kết thúc; ví dụ 18:00 và 19:00 tạo đúng khoảng 18:00–19:00.
- Chỉ các đoạn nằm giữa hai mốc mới phải `AVAILABLE`, vì vậy booking có thể kết thúc đúng tại mốc bắt đầu của booking hoặc bảo trì kế tiếp.
- Lưới và báo giá là kiểm tra tư vấn, không khóa chỗ; thao tác tạo booking vẫn lặp lại validation và chống trùng trong transaction.
- Giờ hoạt động tiếp tục thuộc venue và áp dụng cho các field con trong MVP; không thêm bảng hoặc cấu hình lịch riêng theo từng field.

## ADR-019: Gắn yêu cầu tham gia kèo với contribution

**Trạng thái:** Cách gắn contribution còn hiệu lực, nhưng bước creator duyệt đối thủ được thay thế bởi ADR-028; top-up và refund khi rút được thay thế bởi ADR-027; người ghép mới không gắn contribution.

**Ngày quyết định:** 10/08/2026

- Mỗi booking có tối đa một match; payment mode chia tiền quyết định loại `FIND_OPPONENT` hoặc `FIND_PLAYERS` để không tạo kèo sai nghĩa vụ.
- Quy trình lịch sử bắt đầu ở `PENDING` và creator chấp nhận/từ chối; ADR-028 thay thế bước này cho FIND_OPPONENT mới nhưng giữ nguyên cho FIND_PLAYERS/booking legacy.
- Khi một suất cần trả tiền được nhận, hệ thống khóa và gắn một `booking_contribution` còn trống, đặt hạn 15 phút và chuyển sang `ACCEPTED_AWAITING_PAYMENT`.
- Payment thành công cập nhật contribution, booking, match participant và match trong cùng transaction; kèo tìm người chỉ `FULL` theo số người `JOINED`, độc lập với việc booking đã đủ tiền.
- Nếu hết 15 phút, yêu cầu thành `EXPIRED`, tài khoản được tháo khỏi contribution chưa trả và vị trí được mở lại; CLI `matches expire` xử lý idempotent.
- Nếu creator top-up đủ tiền, participant đang được duyệt và participant được duyệt sau đó vào kèo không cần trả thêm; contribution gốc giữ `WAIVED` để đối soát.
- Rút yêu cầu chưa thanh toán thuộc module này; rút sau khi đã thanh toán phải đi qua module refund để không thay đổi lịch sử tiền sai quy trình.

## ADR-020: Mở lại vị trí sau refund

**Trạng thái:** Chỉ áp dụng cho contribution PLAYER lịch sử; FIND_PLAYERS mới rút không có refund theo ADR-024.

**Ngày quyết định:** 11/08/2026

- Khi người tham gia đã thanh toán rút trước trận trên 12 giờ, contribution cũ chuyển `REFUNDED` và tiếp tục gắn với payment/refund lịch sử.
- Hệ thống tạo contribution mới cùng `slot_number` cho người thay thế; không tái sử dụng nghĩa vụ đã có payment `SUCCESS`.
- Filtered unique index chỉ cho phép một nghĩa vụ chưa hoàn hết trên mỗi vị trí, đồng thời cho phép lưu nhiều contribution `REFUNDED` theo thời gian.

## ADR-021: Tìm kiếm và lọc venue công khai

**Trạng thái:** Phần Google Maps/tìm gần được mở rộng bởi ADR-025; tìm kiếm văn bản và giá từ vẫn còn hiệu lực.

**Ngày quyết định:** 12/08/2026

- Tận dụng các cột venue, field và khung giá hiện có; không thêm bảng hoặc migration cho module tìm kiếm MVP.
- Từ khóa tìm trên tên, địa chỉ, phường/xã/đặc khu và tỉnh/thành phố; ký tự wildcard do người dùng nhập phải được escape trước khi tạo điều kiện `LIKE`. Venue legacy tiếp tục fallback `district/city` cho đến khi backfill an toàn.
- Chỉ venue `ACTIVE` có field `ACTIVE` được đưa vào danh sách công khai.
- “Giá từ” là mức `hourly_price` thấp nhất của khung giá `ACTIVE` trên field `ACTIVE`; khi chọn loại sân, giá và khoảng lọc cùng xét đúng loại đó.
- Các điều kiện tìm kiếm được kết hợp bằng `AND`, truy vấn và tính giá nằm trong service, route chỉ validate query string và render kết quả.
- Kết quả được sắp theo tên và phân trang 9 venue/trang; điều kiện tìm/lọc được giữ trong liên kết chuyển trang.
- Google Maps, tìm quanh vị trí GPS, đánh giá và gợi ý thông minh tiếp tục nằm ngoài module này.

## ADR-022: Mở rộng thành hệ thống đặt sân thể thao đa môn

**Ngày quyết định:** 12/08/2026

- MVP hỗ trợ bóng đá, cầu lông, pickleball và tennis.
- Tạo hai bảng danh mục `sports` và `field_types`; ERD mục tiêu tăng từ 13 lên 15 bảng.
- Mỗi field thuộc đúng một field type và qua đó thuộc đúng một sport; một venue có thể có nhiều field thuộc nhiều sport.
- Field đã có booking không được đổi field type; owner phải ngừng field cũ và tạo field mới để bảo toàn lịch sử.
- Seed bóng đá 5/7/11 người và một field type tiêu chuẩn cho mỗi môn dùng vợt.
- Cầu lông, pickleball và tennis chọn `SINGLES`/`DOUBLES` ở booking; bóng đá không chọn play format.
- Không phân loại mặt sân tennis, thuê dụng cụ, huấn luyện viên hoặc giải đấu trong MVP.
- Dữ liệu `field_type` bóng đá cũ phải được backfill trước khi bỏ cột/check constraint cũ.

## ADR-023: Cọc 30% qua MoMo Sandbox

**Trạng thái:** Mức cọc và ba booking mode còn hiệu lực; deadline 12 giờ, top-up 30 phút và refund 80/20 được thay thế bởi ADR-027.

**Ngày quyết định:** 12/08/2026

- Không thu 100% tiền sân online trong thiết kế mới.
- Backend snapshot `deposit_rate = 30%` và `deposit_amount`; 70% còn lại thanh toán tại sân và không được hệ thống xác nhận trong MVP.
- Booking mới gắn `payment_policy = DEPOSIT_30`; booking cũ backfill `LEGACY_FULL_ONLINE`, rate 1 và deposit bằng total để không làm sai lịch sử.
- `DIRECT_BOOKING` và `FIND_PLAYERS`: creator thanh toán toàn bộ khoản cọc.
- `FIND_OPPONENT`: creator/opponent mỗi bên thanh toán một nửa khoản cọc, tương đương 15% total mỗi bên.
- `PAID` được giữ để giảm độ phức tạp migration nhưng có nghĩa “đã đủ cọc”; UI phải ghi rõ.
- FIND_OPPONENT đặt trước tối thiểu 24 giờ, tìm và nhận cọc đối thủ trước 12 giờ; creator có thêm 30 phút top-up.
- Không top-up: hoàn 80% khoản creator đã đóng, giữ 20% chính khoản đó làm phí giữ sân.
- MoMo Sandbox dùng trình diễn, MOCK dùng test. MoMo Production, QR ngân hàng thật, ví admin và payout nằm ngoài MVP.

ADR này thay thế mô hình FULL_PAYMENT/SPLIT_OPPONENT/SPLIT_PLAYERS đối với booking mới. Migration phải giữ nguyên ý nghĩa payment lịch sử, không tự biến giao dịch 100% cũ thành cọc 30%.

## ADR-024: Tìm thêm người không thanh toán online

**Ngày quyết định:** 12/08/2026

- Creator tự chọn số vị trí FIND_PLAYERS trong giới hạn field/play format.
- Số vị trí được snapshot ở `bookings.requested_players` trước khi match được mở.
- Creator chịu toàn bộ khoản cọc booking; người ghép không có contribution, payment_due_at hoặc refund online.
- Khi creator chấp nhận, participant chuyển thẳng `JOINED`.
- Người ghép trả trực tiếp cho creator tại sân.
- Yêu cầu phải có số điện thoại dùng Zalo; chỉ creator xem được sau khi chấp nhận, không công khai và không tiếp tục hiển thị sau khi booking kết thúc/hủy.
- Participant rút thì mở lại vị trí, không tạo refund.
- MVP không chấm điểm, tự động cảnh cáo hoặc khóa vì no-show.
- Đối với môn dùng vợt, SINGLES chỉ tìm đối thủ; DOUBLES có thể tìm đối thủ hoặc tìm thêm người.

ADR này thay thế việc gắn contribution/payment cho PLAYER trong ADR-017/019. Contribution PLAYER cũ chỉ giữ cho lịch sử.

## ADR-025: Google Maps cho venue nội bộ

**Ngày quyết định:** 12/08/2026

- Venue lưu `google_place_id`, `latitude`, `longitude`.
- Owner dùng Places Autocomplete và kiểm tra marker khi tạo/sửa venue.
- User tìm venue đã ACTIVE trong bán kính 3/5/10 km, xem khoảng cách gần đúng, marker và nút mở Google Maps chỉ đường.
- Browser Geolocation là tùy chọn; từ chối quyền không làm mất tìm kiếm văn bản.
- Không dùng Nearby Search để đưa địa điểm ngoài database vào hệ thống.
- Venue cũ chưa tọa độ vẫn tìm theo văn bản nhưng không tham gia tìm bán kính.
- API key phải giới hạn referrer/API, nằm ngoài source khi cần và có quota/cảnh báo chi phí.

Tài liệu tham chiếu:

- [Places API](https://developers.google.com/maps/documentation/places/web-service)
- [Place Autocomplete (New)](https://developers.google.com/maps/documentation/javascript/place-autocomplete-new)
- [Google Maps API Security](https://developers.google.com/maps/api-security-best-practices)

## ADR-026: Cập nhật tài liệu trước migration đa môn

**Ngày quyết định:** 12/08/2026

- README, docs/01–docs/10 và ERD được cập nhật trước khi sửa model/code.
- Chưa tạo hoặc chạy migration trong bước tài liệu.
- Sau khi user duyệt ERD, triển khai theo các PR riêng: catalog/migration → Maps/search → booking đa môn → matchmaking → cọc 30% → MoMo Sandbox.
- Mỗi migration phải backfill an toàn, review constraint/index trên SQL Server, chạy test hồi quy và không xóa migration cũ.

**Cập nhật triển khai 13/08/2026:** Chuỗi thay đổi đã được thực hiện bằng các migration `b2e91c4a7d10`, `c4f8d2a6e901` và `d7a1b9e4c320`. SQL Server giữ nguyên dữ liệu booking cũ dưới chính sách `LEGACY_FULL_ONLINE`. Tích hợp MoMo đã có create payment, HMAC, redirect, IPN, query và refund; kiểm thử gọi Sandbox thật còn phụ thuộc credential M4B và URL HTTPS công khai, không dùng secret giả hoặc commit secret vào Git.

## ADR-027: Cọc giữ sân, vòng đời bài tìm đối thủ và hủy không hoàn cọc

**Ngày quyết định:** 14/08/2026

- DIRECT_BOOKING và FIND_PLAYERS giữ chính sách creator cọc 30% tổng tiền sân.
- FIND_OPPONENT giữ mức cọc online mục tiêu 30% nhưng creator chỉ cần đóng 15% tổng tiền sân để booking được giữ hợp lệ; đối thủ đóng thêm 15% khi nhận kèo.
- Không tìm được đối thủ không phải hành động hủy của creator, không làm hủy booking và không tạo refund. Creator vẫn dùng sân và trả 85% còn lại tại sân.
- Khi đối thủ đã cọc, paid_amount đạt 30% và số còn lại tại sân là 70%.
- Bài FIND_OPPONENT tồn tại đến giờ booking bắt đầu, trừ khi creator đóng sớm hoặc đối thủ thanh toán thành công.
- Đối thủ nhận kèo có tối đa 15 phút thanh toán nhưng không vượt giờ booking bắt đầu. Tại giờ bắt đầu, suất chưa thanh toán hết hiệu lực và bài không còn được xem là OPEN.
- Bỏ matchmaking deadline trước 12 giờ, funding deadline và creator top-up bắt buộc cho booking mới.
- Người chủ động hủy/rút hoặc no-show không được hoàn phần cọc của chính mình.
- Đối thủ đã cọc rồi chủ động rút: contribution chuyển FORFEITED, vị trí mở lại, khoản đã thu tiếp tục tính vào booking và người thay thế không bị thu cọc lần hai.
- Creator hủy sau khi đối thủ đã cọc: creator mất phần của mình, đối thủ được hoàn 100% vì không phải bên chủ động hủy.
- Owner hủy hoặc hệ thống thu trùng/sai: hoàn 100% khoản bị ảnh hưởng.
- Refund vẫn là bản ghi riêng và idempotent; payment SUCCESS không bị xóa/ghi đè.
- Số còn lại tại sân luôn bằng total_amount trừ paid_amount thực thu ròng, không mặc định bằng 70%.
- Booking FIND_OPPONENT PARTIALLY_PAID có thể chuyển COMPLETED nếu đến giờ sử dụng mà không có đối thủ.
- `matchmaking_deadline`, `funding_deadline`, TOP_UP, WAIVED và refund 80/20 được giữ để đọc đúng lịch sử; booking mới không tạo dữ liệu theo luồng cũ.

**Ghi chú schema:** Không cần migration mới vì hai cột deadline hiện đã nullable và schema không có constraint bắt buộc FIND_OPPONENT phải có deadline. Giữ nguyên cột/index cho dữ liệu legacy; thay đổi nằm ở service, route, UI và test.

**Trạng thái triển khai:** README và docs/01–docs/10 đã được đồng bộ; code và test được triển khai trên nhánh riêng và chỉ được xem là hoàn tất sau khi vượt qua toàn bộ kiểm thử, Alembic check và smoke test.

## ADR-028: Đối thủ tự nhận kèo bằng thanh toán cọc

**Ngày quyết định:** 14/08/2026

- FIND_OPPONENT mới bỏ bước gửi yêu cầu chờ creator chấp nhận/từ chối.
- Đại diện đối thủ bấm “Nhận kèo”; service khóa match và contribution để chỉ một đội giữ suất thanh toán tại một thời điểm.
- Participant chuyển thẳng `ACCEPTED_AWAITING_PAYMENT`; payment_due_at là thời điểm sớm hơn giữa lúc nhận cộng 15 phút và giờ booking bắt đầu.
- Payment cọc thành công chuyển participant `JOINED`, booking `PAID` và match `CONFIRMED`.
- Hết hạn chưa thanh toán chuyển participant `EXPIRED`, gỡ user khỏi contribution và mở lại kèo.
- Nếu contribution đối thủ đã được thanh toán/forfeit từ người trước, người thay thế được `JOINED` ngay và không bị thu trùng khoản cọc.
- Yêu cầu `PENDING` tạo trước quyết định có thể được chính người đó bấm tiếp tục để chuyển sang giữ suất; không bắt creator duyệt lại.
- FIND_PLAYERS vẫn giữ creator chấp nhận/từ chối vì người ghép không cọc online và cần phù hợp đội hình/thông tin Zalo.
- Booking legacy có deadline tiếp tục dùng luồng duyệt cũ để không đổi hồi tố dữ liệu đang diễn ra.

**Ghi chú schema:** Không cần migration mới; tận dụng `ACCEPTED_AWAITING_PAYMENT`, `payment_due_at`, khóa match/contribution và các filtered unique index hiện có.

## ADR-029: Liên hệ riêng sau khi tham gia và lịch kèo của participant

**Ngày quyết định:** 14/08/2026

- Creator và người xin tham gia đều phải nhập số điện thoại dùng Zalo, đồng thời xác nhận đồng ý chia sẻ trong phạm vi kèo.
- Số creator được snapshot ở `matches.creator_contact_phone`; số participant tiếp tục snapshot ở `match_participants.contact_phone`. Không tự động công khai số từ hồ sơ người dùng cho match lịch sử.
- Chỉ participant `JOINED` và creator được xem số của nhau khi booking còn hiệu lực. Khách, user không liên quan, participant còn chờ cọc/chờ duyệt và booking đã kết thúc/hủy không được xem.
- Sau khi đối thủ thanh toán cọc và chuyển `JOINED`, kèo xuất hiện trong “Lịch & kèo của tôi” của đối thủ để mở trang chi tiết và liên hệ.
- Việc hiển thị này không tạo booking mới, không đổi `bookings.user_id` và không cấp cho participant quyền sửa/hủy booking của creator.
- Dữ liệu lịch sử thiếu snapshot hiển thị form để đúng bên chủ động bổ sung số và xác nhận chia sẻ.

**Ghi chú schema:** Migration `e8c4a2d9f701` thêm cột nullable `matches.creator_contact_phone`; nullable để không suy diễn sự đồng ý của dữ liệu cũ.

## ADR-030: Chuẩn hóa địa chỉ hành chính venue theo mô hình hai cấp

**Ngày ghi nhận:** 16/08/2026
**Trạng thái:** Foundation đã triển khai tại Step 4.0 ngày 25/08/2026; Admin Step 4 UI chưa triển khai.

- Form tạo/sửa cơ sở không cho owner nhập tự do tên đơn vị hành chính.
- Ô thứ nhất chọn `Tỉnh/Thành phố` từ danh mục chính thức; ô thứ hai phụ thuộc vào ô thứ nhất và chỉ hiển thị `Phường/Xã/Đặc khu` thuộc địa phương đã chọn.
- Không xây luồng mới theo `Quận/Huyện` vì mô hình chính quyền địa phương hai cấp đã kết thúc cấp huyện từ ngày 01/07/2025.
- Hệ thống lưu cả mã và tên đơn vị hành chính để tránh sai chính tả và giữ snapshot hiển thị khi catalog được cập nhật.
- Owner vẫn nhập địa chỉ chi tiết; Google Maps tiếp tục dùng để xác nhận place ID, marker và tọa độ, không thay thế danh mục hành chính chính thức.
- Bộ lọc Admin dùng thứ tự `Tỉnh/Thành phố → Phường/Xã/Đặc khu → Cơ sở → Sân`.
- Dữ liệu venue cũ trong `city` và `district` phải được giữ nguyên cho đến khi có migration và kế hoạch backfill đã kiểm thử; không đổi hoặc xóa trực tiếp dữ liệu hiện có.
- Catalog dùng mã hành chính theo Quyết định 19/2025/QĐ-TTg; snapshot máy đọc được được ghim phiên bản, kiểm tra đủ 34 tỉnh/thành phố và 3.321 phường/xã/đặc khu trước khi seed.
- Migration `f3a7c9d2e410` thêm catalog cùng các cột `province_code/province_name/ward_code/ward_name`; giữ `city/district` nullable làm fallback legacy, không tự suy diễn district cũ thành ward mới.
- Backend tự tra mã và kiểm tra ward thuộc province; Google Maps chỉ lưu place ID/tọa độ và hiển thị formatted address để đối chiếu.

Foundation này không thay đổi workflow kiểm duyệt venue và chưa redesign màn Admin Step 4.

Tài liệu tham chiếu:

- [Chính phủ: tổ chức chính quyền địa phương hai cấp](https://xaydungchinhsach.chinhphu.vn/trung-uong-thong-nhat-to-chuc-chinh-quyen-dia-phuong-2-cap-ca-nuoc-se-con-34-tinh-thanh-pho-sau-sap-nhap-119250412184121461.htm)
- [Bộ Nội vụ: danh mục và mã số 34 đơn vị hành chính cấp tỉnh](https://moha.gov.vn/tin-tuc/---oid57326)
- [Quyết định 19/2025/QĐ-TTg: Bảng danh mục và mã số các đơn vị hành chính Việt Nam](https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/7/19ttg.signed.pdf)
- [Structured snapshot đối chiếu từ các nghị quyết sắp xếp hành chính](https://github.com/mantisvn/Vietnamese-Administrative-Units-Dataset)

## ADR-031: Thanh toán sandbox và đối soát cho Owner

**Ngày quyết định:** 23/08/2026
**Trạng thái:** Đã chốt định hướng nghiệp vụ; triển khai thuộc Phase 2 – Admin Operations và Phase 3 – Owner Console.

- Đồ án sử dụng MoMo/ZaloPay sandbox và không thực hiện giao dịch tiền thật.
- `Payment SUCCESS` là căn cứ để hệ thống tự động xác nhận booking (`CONFIRMED`); không yêu cầu Owner duyệt booking sau thanh toán.
- `Payment SUCCESS` không đồng nghĩa Owner đã được quyết toán. Payment, refund và settlement là các bản ghi/vòng đời độc lập để bảo toàn đối soát.
- Settlement sử dụng các trạng thái: `PENDING`, `ELIGIBLE`, `SETTLED`, `FAILED` và `ON_HOLD`.
- Sau khi ca sân kết thúc 30 phút, nếu không có cancellation, refund hoặc dispute: booking chuyển `COMPLETED` và settlement chuyển `ELIGIBLE`.
- Owner không tự xác nhận để nhận tiền; User cũng không bắt buộc xác nhận đã chơi xong. Admin chỉ can thiệp vào các trường hợp ngoại lệ.
- Khi Owner hủy booking, settlement bị chặn (`ON_HOLD`) và booking đi vào refund workflow; chỉ tiếp tục đối soát khi các nghĩa vụ hoàn tiền/ngoại lệ đã được giải quyết đúng quy trình.
- Payout cho Owner ưu tiên sandbox disbursement nếu provider hỗ trợ và dễ tích hợp. Nếu không phù hợp, hệ thống dùng simulated payout adapter để trình diễn đầy đủ vòng đời đối soát mà không chuyển tiền thật.
- Payout thành công chuyển settlement sang `SETTLED`; lỗi payout được ghi nhận là `FAILED` hoặc `ON_HOLD` tùy nguyên nhân và cần luồng xử lý ngoại lệ của Admin.
- Phần tiền còn lại sau tiền cọc được thanh toán trực tiếp tại sân; settlement chỉ đối soát các khoản online mà hệ thống có căn cứ ghi nhận.
- Owner cấu hình tài khoản nhận tiền trong Owner Console. Thông tin tài khoản nhận tiền không thuộc Owner Application.

ADR này mở rộng ADR-006 về sandbox và làm rõ phần đối soát chưa được triển khai. ADR-016 vẫn giữ nguyên nguyên tắc booking không chờ Owner xác nhận; việc ánh xạ trạng thái chi tiết trong code hiện hữu chỉ được điều chỉnh khi Phase 2 được yêu cầu riêng.

## ADR-032: Bỏ Maps/Places API, chỉ giữ liên kết chỉ đường Google Maps

**Ngày quyết định:** 29/08/2026
**Trạng thái:** Đã triển khai trong code, UI, test và tài liệu.

- Không tải Google Maps JavaScript API hoặc Places API trong bất kỳ giao diện nào.
- Bỏ bản đồ/marker nhúng, Places Autocomplete, Browser Geolocation và tìm venue theo bán kính 3/5/10 km.
- Owner khai báo venue bằng tỉnh/thành phố, phường/xã và địa chỉ chi tiết; Admin không yêu cầu Place ID/tọa độ để duyệt ACTIVE.
- Danh sách, trang chi tiết và Admin vẫn có liên kết “Mở chỉ đường trên Google Maps”; đây là URL ngoài hệ thống, không chứa API key.
- `google_place_id`, `latitude` và `longitude` vẫn nằm trong schema để giữ dữ liệu legacy; form mới không hiển thị hoặc ghi đè các cột này.
- Không có migration và không xóa dữ liệu venue hiện có.

ADR này thay thế hành vi runtime của ADR-025 và phần Google Maps trong ADR-030; các ADR cũ được giữ để ghi lại lịch sử quyết định.

## ADR-033: Bỏ Singles/Doubles khỏi booking flow MVP hiện tại

**Ngày quyết định:** 29/08/2026
**Trạng thái:** Đã áp dụng cho form, quote/create service, UI, test và tài liệu.

- User chỉ chọn một trong ba mục đích: `DIRECT_BOOKING`, `FIND_OPPONENT` hoặc `FIND_PLAYERS`.
- Không hỏi, không validate và không suy diễn `SINGLES`/`DOUBLES` ở bất kỳ bộ môn nào.
- Booking mới luôn lưu `play_format = NULL`; không dùng giá trị mặc định giả để vượt validation.
- Cột nullable, enum và constraint hiện có được giữ nguyên để đọc dữ liệu legacy; không migration, không xóa hoặc sửa hồi tố bản ghi cũ.
- `FIND_PLAYERS` yêu cầu `1 <= requested_players < field.capacity`; không còn phụ thuộc play format.
- Step 2 chỉ kiểm tra ngày/giờ, availability, maintenance, conflict và pricing. Step 3 kiểm tra booking mode/requested_players/note. Step 4 báo full quote, contribution/deposit và xác nhận cuối.
- `create_booking()` vẫn lặp lại toàn bộ guardrail liên quan trước khi commit; pricing, contribution, deposit, payment, match, cancellation và refund không đổi.

ADR này thay thế phần quy định play format mới trong ADR-022 và ADR-024. Các ADR cũ và dữ liệu cũ được giữ để ghi lại lịch sử quyết định.
