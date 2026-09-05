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

**Trạng thái:** Mức cọc và ba booking mode còn hiệu lực; deadline 12 giờ, top-up 30 phút và refund 80/20 được thay thế bởi ADR-027. Câu loại mọi payout khỏi MVP được ADR-037 thay thế riêng cho simulated payout Phase 2.6; payout tiền thật vẫn ngoài MVP.

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
**Trạng thái:** Quyết định lịch sử; hành vi runtime đã bị ADR-032 thay thế, sau đó kiến trúc vị trí/bản đồ được ADR-036 xác lập lại bằng Leaflet/Nominatim.

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

**Ghi chú supersession:** Các câu về Google Maps/Place ID trong ADR này là bối cảnh lịch sử. ADR-032 đã bỏ Maps/Places API; ADR-036 sau đó chọn Leaflet cho bản đồ và Nominatim cho geocoding, không đưa Google Maps API trở lại.

Tài liệu tham chiếu:

- [Chính phủ: tổ chức chính quyền địa phương hai cấp](https://xaydungchinhsach.chinhphu.vn/trung-uong-thong-nhat-to-chuc-chinh-quyen-dia-phuong-2-cap-ca-nuoc-se-con-34-tinh-thanh-pho-sau-sap-nhap-119250412184121461.htm)
- [Bộ Nội vụ: danh mục và mã số 34 đơn vị hành chính cấp tỉnh](https://moha.gov.vn/tin-tuc/---oid57326)
- [Quyết định 19/2025/QĐ-TTg: Bảng danh mục và mã số các đơn vị hành chính Việt Nam](https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/7/19ttg.signed.pdf)
- [Structured snapshot đối chiếu từ các nghị quyết sắp xếp hành chính](https://github.com/mantisvn/Vietnamese-Administrative-Units-Dataset)

## ADR-031: Thanh toán sandbox và đối soát cho Owner

**Ngày quyết định:** 23/08/2026
**Trạng thái:** Đã chốt định hướng nghiệp vụ; các điểm mơ hồ về lifecycle, status, exception, destination và payout đã được ADR-037 làm rõ/thay thế cho Phase 2.6.

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
- Cấu hình tài khoản hoặc đích nhận chi trả chỉ được thiết kế và triển khai cùng settlement/payout ở Phase 2.6; không thuộc Step 3.5 hoặc Owner Application.

ADR này mở rộng ADR-006 về sandbox và làm rõ phần đối soát chưa được triển khai. ADR-016 vẫn giữ nguyên nguyên tắc booking không chờ Owner xác nhận; việc ánh xạ trạng thái chi tiết trong code hiện hữu chỉ được điều chỉnh khi Phase 2 được yêu cầu riêng.

## ADR-032: Bỏ Maps/Places API, chỉ giữ liên kết chỉ đường Google Maps

**Ngày quyết định:** 29/08/2026
**Trạng thái:** Đã triển khai ngày 29/08/2026; phần cấm bản đồ nhúng/geolocation đã được ADR-036 và Phase 1.3 thay thế. Quyết định không dùng Google Maps/Places API và giữ liên kết chỉ đường ngoài hệ thống vẫn còn hiệu lực.

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

## ADR-034: Thống nhất thời gian đặt trước tối thiểu cho mọi booking mode

**Ngày quyết định:** 30/08/2026
**Trạng thái:** Đã áp dụng cho booking service, test và tài liệu.

- DIRECT_BOOKING, FIND_PLAYERS và FIND_OPPONENT đều phải được tạo trước giờ bắt đầu ít nhất 60 phút.
- Bỏ ngoại lệ yêu cầu FIND_OPPONENT phải đặt trước 24 giờ.
- Các quy tắc thời gian còn lại không đổi: booking ở tương lai, thời lượng tối thiểu 60 phút, bước 30 phút, giờ mở cửa và giới hạn tối đa 30 ngày.
- Kiểm tra trùng booking/bảo trì không đổi.
- Matchmaking, payment, deposit, cancellation và refund không đổi.

ADR này chỉ thay thế điều kiện đặt trước 24 giờ của FIND_OPPONENT trong ADR-023 và các tài liệu dẫn xuất; các quyết định còn lại vẫn giữ nguyên.

## ADR-035: Điều hướng Owner Pricing và Maintenance theo Field

**Ngày quyết định:** 02/09/2026
**Trạng thái:** Đã áp dụng và nghiệm thu trong Phase 3 – Owner Console.

- Bảng giá và Bảo trì là thao tác theo từng Field, vì rule giá, trạng thái kích hoạt Field, lịch bảo trì và kiểm tra chồng lịch đều có phạm vi Field.
- Owner đi từ Cơ sở & Sân theo ngữ cảnh Venue → Field đến Bảng giá hoặc Bảo trì; không tạo menu global, route global hay màn danh sách chéo Field mới chỉ để điều hướng.
- Các nested route, service, permission và ownership validation hiện có là source of truth; quyết định này chỉ chuẩn hóa hierarchy điều hướng và không thay đổi nghiệp vụ.

## ADR-036: Kiến trúc vị trí và bản đồ Leaflet cho MVP

**Ngày quyết định:** 02/09/2026
**Trạng thái:** Đã triển khai và nghiệm thu toàn bộ Phase 1.3 ngày 03/09/2026.

### Quan hệ với các quyết định trước

- ADR-032 được giữ nguyên để ghi lại quyết định và runtime không Maps đã được nghiệm thu ngày 29/08/2026.
- ADR này thay thế ADR-032 đối với các hành vi vị trí/bản đồ được đưa trở lại theo Phase 1.3: hệ thống được phép dùng bản đồ nhúng Leaflet, geocoding và tọa độ Venue đã được xác nhận.
- Việc thay thế đã hoàn tất theo Phase 1.3: Owner location picker, Venue Detail map, Find Venue map và `Sân gần tôi` đã được triển khai, trong khi liên kết chỉ đường ngoài hệ thống vẫn được giữ.
- Kiến trúc Google Places/Nearby trong ADR-025 không còn là thiết kế runtime được chọn. Phần Google Maps trong ADR-030 cũng không quyết định công nghệ bản đồ mới.
- Liên kết ngoài “Mở chỉ đường trên Google Maps” từ `full_address` có thể tiếp tục tồn tại như một tiện ích độc lập, trừ khi có quyết định khác sau này.

### Công nghệ và ranh giới trách nhiệm

- Leaflet là thư viện frontend được chọn để render bản đồ, đặt marker và hỗ trợ tương tác sửa vị trí.
- Tile phải đến từ một nhà cung cấp tương thích OpenStreetMap và giao diện phải hiển thị attribution bắt buộc theo điều khoản của nhà cung cấp.
- Leaflet không chuyển địa chỉ thành tọa độ. Geocoding là trách nhiệm riêng.
- Dịch vụ tile và dịch vụ geocoding là hai dịch vụ độc lập; không được coi tile OpenStreetMap công khai là một geocoder.
- MVP mới không đưa Google Maps JavaScript API hoặc Google Places trở lại.
- Tại thời điểm ADR-036/B0, nhà cung cấp geocoding chưa được chọn. Phase 1.3B1 sau đó đã chọn Nominatim công khai cho lưu lượng student/demo thấp, có timeout, cache, giới hạn nhịp và manual-marker fallback.

Nhà cung cấp geocoding được đánh giá ở Phase 1.3B1 phải:

- hỗ trợ chuyển địa chỉ thành tọa độ và phù hợp với địa chỉ Việt Nam;
- có usage/rate limit được công bố;
- không bị gọi bulk một cách âm thầm;
- cho phép xử lý lỗi rõ ràng, có kiểm soát;
- có yêu cầu attribution/licensing minh bạch;
- không yêu cầu commit API key hoặc secret vào source code.

Dịch vụ Nominatim công khai không được xem là hạ tầng production không giới hạn. Tích hợp Phase 1.3B1 chỉ gọi theo hành động tra cứu của Owner, tuân thủ cache/giới hạn nhịp/timeout hiện có và không thực hiện bulk geocoding.

### Workflow tọa độ kết hợp đã chấp thuận

Owner tiếp tục nhập tên Venue, địa chỉ chi tiết, Province, Ward và metadata Venue hiện có. Luồng vị trí được chốt là:

> **Address input → Geocoding → Approximate coordinates → Leaflet marker → Owner confirmation/correction → Persist latitude/longitude**

Chi tiết:

1. Hệ thống tạo/sử dụng `full_address` của Venue.
2. Owner chủ động yêu cầu tra cứu vị trí trong flow tạo/sửa Venue.
3. Geocoder chuyển địa chỉ thành cặp latitude/longitude gần đúng.
4. Leaflet hiển thị vị trí và đặt marker tại tọa độ được gợi ý.
5. Owner phải kiểm tra marker và có thể kéo hoặc chọn lại vị trí.
6. Chỉ cặp tọa độ của marker đã được Owner xác nhận mới được persist thành tọa độ đáng tin cậy của Venue.
7. Venue được lưu với address, Province, Ward, latitude và longitude đồng bộ.

**Nguyên tắc source of truth:** Kết quả geocoder chỉ là gợi ý; marker được Owner xác nhận là source of truth cho tọa độ Venue.

Không chấp nhận luồng `address → geocoder → âm thầm lưu tọa độ`. Geocoder có thể trả sai cổng vào, trả một đường lân cận, hiểu nhầm địa chỉ, trả nhiều/kết quả confidence thấp hoặc thất bại. Không kết quả nào được tin cậy nếu Owner chưa xác nhận hoặc sửa marker.

### Location identity, stale coordinates và moderation

Location identity của Venue gồm:

- `address`;
- `province`;
- `ward`;
- `latitude`;
- `longitude`.

Các giá trị này phải được giữ đồng bộ. Đối với Venue đang `ACTIVE`, thay đổi bất kỳ thành phần nào của location identity đều là thay đổi nhạy cảm với moderation và phải đưa Venue về `PENDING` theo semantics kiểm duyệt hiện có.

Khi Owner thay đổi address, Province hoặc Ward, tọa độ đã xác nhận trước đó lập tức trở thành stale và không còn được xem là đáng tin cậy. Implementation tương lai phải yêu cầu xác nhận lại theo lifecycle:

> **Existing confirmed location → Owner modifies address → Location confirmation becomes stale → Geocode again → Show suggested marker → Owner confirms/corrects marker → Save new location**

Không được âm thầm giữ tọa độ thuộc địa chỉ cũ như vị trí của địa chỉ mới.

### Lỗi geocoding và manual fallback

Nếu geocoding không có kết quả, lỗi provider/network hoặc trả vị trí rõ ràng không đúng, Owner vẫn phải có một cách có kiểm soát để đặt hoặc sửa marker thủ công trên Leaflet. Ứng dụng không được tự bịa tọa độ.

Phase 1.3B1 phải hỗ trợ:

- luồng chính: `address → geocode → Owner xác nhận marker`;
- fallback: Owner tự chọn hoặc sửa marker rồi xác nhận.

### Tương thích dữ liệu thiếu tọa độ và schema

- `Venue.latitude` và `Venue.longitude` hiện tại đủ cho nhu cầu lưu tọa độ MVP; chưa có kế hoạch migration.
- Hai cột tiếp tục nullable để tương thích với dữ liệu hiện có.
- Không thêm geometry/geography, `map_url`, location JSON hoặc bảng tọa độ mới nếu chưa có defect triển khai cụ thể chứng minh là cần thiết.
- `google_place_id` không bắt buộc trong kiến trúc Leaflet mới.
- Public page chỉ render Leaflet marker khi Venue có cặp tọa độ hợp lệ đã được xác nhận.
- Venue thiếu tọa độ phải dùng fallback có chủ đích như `full_address` và liên kết chỉ đường ngoài hệ thống; không được hiển thị marker mặc định hoặc giả như vị trí thật.

Phase 1.3B2 đã dùng application flow có kiểm soát để nâng coverage development từ 1/16 lên 4/16 Venue có tọa độ được xác nhận. Mười hai Venue có địa chỉ demo/mơ hồ vẫn để lại cho manual review; không cập nhật SQL trực tiếp và không dùng tọa độ bịa làm dữ liệu production-like.

### Ranh giới Phase 1.3B1 và Nearby

Phase 1.3B1 chỉ thiết lập tọa độ Venue đáng tin cậy. Browser current location, Haversine và sắp xếp theo khoảng cách được triển khai riêng ở Phase 1.3E; MVP không thêm radius filter hoặc geospatial database extension.

### Current location và nearby đã triển khai

- Browser geolocation chỉ được gọi sau khi người dùng bấm `Sân gần tôi`; lỗi quyền/thiết bị/timeout không làm hỏng tìm kiếm thông thường.
- Backend xác thực cặp latitude/longitude và tính khoảng cách bằng Haversine; chỉ Venue có tọa độ hợp lệ tham gia nearby mode.
- Vị trí người dùng chỉ phục vụ request hiện tại, không được lưu vào database, session, localStorage hoặc sessionStorage.

### Rủi ro yêu cầu Google Maps

- Bằng chứng hiện có trong repository không xác lập Google Maps API là công nghệ runtime bắt buộc.
- Leaflet + OpenStreetMap-compatible tiles là kiến trúc bản đồ nhúng MVP được chọn; geocoding provider là quyết định riêng.
- Không được mô tả Leaflet là tương đương Google Maps API.
- Nếu giảng viên hướng dẫn yêu cầu rõ Google Maps API là công nghệ bắt buộc ở ngoài tài liệu repository, ADR này phải được xem xét lại trước khi triển khai tiếp.

## ADR-037: Chính sách Settlement và simulated payout cho Owner

**Ngày quyết định:** 05/09/2026
**Trạng thái:** Đã chốt chính sách; implementation thuộc Phase 2.6 và chưa được triển khai.

### Quan hệ với ADR-031

ADR này giữ định hướng tách biệt Payment, Refund và Settlement của ADR-031,
đồng thời làm rõ và thay thế các phần còn mơ hồ sau:

- Booking hoàn thành theo lifecycle hiện có ngay sau khi thời gian sử dụng kết
  thúc; không chờ Settlement.
- Mốc cộng 30 phút chỉ là thời điểm đủ điều kiện Settlement sớm nhất, không
  phải thời điểm chuyển Booking sang `COMPLETED`.
- Phase 2.6 chỉ dùng `SimulatedPayoutAdapter`; không ưu tiên hoặc tích hợp
  sandbox disbursement của provider.
- Bổ sung trạng thái terminal `CLOSED` cho Settlement có chứng cứ tài chính
  nhưng số tiền phải chi trả cuối cùng bằng 0.

Các ADR lịch sử tiếp tục được giữ nguyên. Khi nội dung ADR-031 mâu thuẫn với
ADR này về lifecycle, trạng thái, payout hoặc ngoại lệ, ADR-037 là quyết định
hiện hành.

### Phạm vi và số tiền Settlement

- Settlement chỉ đại diện cho tiền online hệ thống đã thu và cuối cùng phải
  trả cho Owner; không bao gồm tiền dự kiến thanh toán trực tiếp tại sân.
- `Booking.paid_amount` là số tiền online ròng đang được trạng thái tài chính
  Booking ghi nhận.
- `balance_due_at_venue = Booking.total_amount - Booking.paid_amount`.
- Không hard-code 70%, 30% hoặc 15%. `FIND_OPPONENT` chỉ thu 15% từ creator
  vẫn có thể là trạng thái tài chính hợp lệ; `LEGACY_FULL_ONLINE` tiếp tục được
  phân biệt với `DEPOSIT_30`.
- Với Booking hoàn thành hợp lệ:

  ```text
  gross_online_amount = tổng Payment SUCCESS online được chấp nhận
  successful_refund_amount = tổng Refund SUCCESS áp dụng cho khoản thu đó
  settlement_amount = gross_online_amount - successful_refund_amount
  ```

- Kết quả phải đối soát được với online net hiện hành. Contribution chỉ dùng
  để kiểm tra phân bổ/nghĩa vụ, không được cộng lại với Payment và gây tính
  trùng.

### Refund và cancellation

- Refund `SUCCESS` là lịch sử tài chính bất biến. Refund thành công không chặn
  Settlement vĩnh viễn nếu Booking vẫn phải trả và phần online net còn lại
  đối soát đúng.
- Refund `PENDING`, `PROCESSING` hoặc `FAILED` là ngoại lệ chưa giải quyết và
  buộc Settlement ở `ON_HOLD`. Khi ngoại lệ được giải quyết, service được phép
  revalidate và chuyển Settlement ra khỏi `ON_HOLD`.
- Nếu creator hủy và policy hiện hành giữ lại một phần hoặc toàn bộ tiền online
  của creator, phần bị giữ cuối cùng thuộc Owner như bồi thường cho khung giờ
  đã giữ; đây không phải doanh thu nền tảng. Refund bắt buộc cho participant
  khác phải hoàn tất trước khi xác định số tiền phải trả cuối cùng.
- Booking creator-cancelled có thể vẫn ở `CANCELLED` nhưng có Settlement phải
  trả. Payout chỉ được phép sau giờ kết thúc lịch đặt cộng 30 phút, khi refund
  đã giải quyết, số tiền bị giữ hợp lệ lớn hơn 0, đối soát đạt và có đích nhận.
- Owner cancellation không bao giờ tạo doanh thu Settlement phải trả. Trong
  lúc refund/ngoại lệ chưa xong, Settlement là `ON_HOLD`; sau khi số tiền phải
  trả về 0, Settlement chuyển `CLOSED`.

### Trạng thái Settlement

- `PENDING`: đã nhận diện tiền online có khả năng phải trả nhưng chưa đến mốc
  đủ điều kiện bình thường hoặc còn prerequisite không phải ngoại lệ.
- `ELIGIBLE`: dữ liệu hiện tại an toàn để Admin thực hiện simulated payout.
- `ON_HOLD`: có cancellation, refund hoặc sai lệch tài chính chưa giải quyết.
- `FAILED`: lần simulated payout gần nhất lỗi kỹ thuật; được retry sau khi
  service revalidate.
- `SETTLED`: simulated payout đã thành công.
- `CLOSED`: terminal, không chi trả vì số tiền phải trả cuối cùng bằng 0. Nhãn
  nghiệp vụ là **“Đã đóng – không chi trả”**.

Không tạo Settlement nếu Booking chưa từng có khoản online được nhận diện.
Nếu Settlement đã tồn tại hoặc cần giữ chứng cứ tài chính nhưng online net trở
về 0 trước payout, chuyển `CLOSED`; không tạo `PayoutAttempt` số tiền 0.

### Điều kiện đủ để chi trả

Booking hoàn thành thông thường chỉ chuyển Settlement sang `ELIGIBLE` khi tất
cả điều kiện sau đúng, sử dụng thời gian địa phương Việt Nam nhất quán:

- thời gian kết thúc lịch đặt cộng 30 phút đã qua;
- Booking ở trạng thái hoàn thành/phải trả được chấp nhận;
- số tiền online phải trả hiện tại lớn hơn 0;
- Payment/Refund `SUCCESS` và contribution liên quan đối soát được;
- không có Refund `PENDING`, `PROCESSING` hoặc `FAILED`;
- không có khoản provider xác nhận thành công muộn nhưng Payment còn `EXPIRED`
  và chưa được xử lý đúng vào trạng thái tài chính Booking;
- quan hệ Owner/Venue hợp lệ;
- Owner đã cấu hình simulated payout destination.

Creator cancellation có tiền bị giữ hợp lệ áp dụng cùng điều kiện về thời
gian, refund, đối soát, số tiền dương và destination. Owner cancellation luôn
không phải trường hợp phải trả.

Payment `FAILED`, `CANCELLED` hoặc `EXPIRED` trong lịch sử không giữ Settlement
vĩnh viễn nếu một Payment được chấp nhận sau đó tạo trạng thái tài chính hợp lệ
và đối soát được. Payment bị đánh dấu `EXPIRED` nhưng provider xác nhận thành
công muộn không được tính là tiền phải trả nếu chưa thuộc trạng thái tài chính
Booking đã chấp nhận; nếu khoản đó đang chờ refund thì Settlement tiếp tục
`ON_HOLD` hoặc không phải trả tùy chứng cứ hiện hành. Không được tạo Payment giả
để làm khớp dữ liệu.

### Simulated payout và destination

- Phase 2.6 chỉ dùng `SimulatedPayoutAdapter`; không lưu hoặc sử dụng credential
  ngân hàng/MoMo thật.
- Mỗi Owner có tối đa một simulated destination đang hoạt động với
  `provider = SIMULATED`, `destination_label` và
  `account_reference`/demo reference. UI phải cảnh báo không nhập thông tin tài
  chính thật.
- Trước payout, UI hiển thị destination hiện tại sẽ được snapshot khi Admin
  xác nhận. Sau khi có `PayoutAttempt`, UI hiển thị snapshot lịch sử gắn với
  attempt đó. Thay đổi destination sau này không sửa lịch sử cũ.
- Chỉ Admin được POST payout từ Settlement Detail. Owner chỉ được xem.
- Chỉ `ELIGIBLE` được payout; `FAILED` được retry sau revalidation. Không có
  payout action cho `PENDING`, `ON_HOLD`, `SETTLED` hoặc `CLOSED`.
- Mỗi attempt có idempotency key/reference duy nhất; request trùng không tạo
  payout trùng. Retry tạo attempt mới và MVP không áp giới hạn cố định số lần.
- `SETTLED` là terminal: không gọi adapter lần nữa, không tự reverse, không
  giảm số tiền lịch sử, không tạo compensating payout hoặc clawback.
- Nếu Refund hoặc ngoại lệ xuất hiện sau `SETTLED`, giữ nguyên Settlement và
  mọi attempt, đồng thời hiển thị post-settlement variance/manual-review ở
  Admin read model khi có thể. Clawback, adjustment và Dispute model nằm ngoài
  Phase 2.6 MVP.

### Đồng bộ và dữ liệu legacy

Không dùng Celery, APScheduler hoặc background worker. Phase 2.6 cung cấp lệnh
Flask CLI idempotent:

```text
flask settlements sync
```

Lệnh này:

- phát hiện các khoản online được nhận diện và tạo Settlement còn thiếu;
- backfill các bản ghi legacy hợp lệ;
- làm mới số tiền của Settlement chưa terminal;
- chuyển đổi idempotent giữa `PENDING`, `ELIGIBLE`, `ON_HOLD` và `CLOSED`;
- revalidate `FAILED` khi phù hợp nhưng không tự động retry payout.

Lệnh không payout, không sửa lifecycle Booking, không sửa Payment/Refund/Match
và không tạo lịch sử giả. Admin/Owner GET luôn read-only.

Chính sách legacy:

- Có Payment/Refund hợp lệ và online net dương: tạo `PENDING` hoặc `ELIGIBLE`
  theo thời gian và các điều kiện hiện hành.
- `LEGACY_FULL_ONLINE` có `paid_amount` nhưng thiếu Payment evidence:
  `ON_HOLD`; không tạo Payment giả.
- Không có khoản online được nhận diện: không tạo Settlement.
- Có chứng cứ full refund/zero net: `CLOSED` nếu tạo/backfill Settlement để giữ
  audit evidence.
- Sai lệch tài chính: `ON_HOLD`.

Backfill thuộc CLI/application service, không thuộc Alembic migration.
