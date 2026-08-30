# 9. Test cases

## 9.1. Authentication và authorization

### TC-AUTH-001: Đăng ký thành công

Tạo USER/ACTIVE, email chuẩn hóa và password hash.

### TC-AUTH-002: Email trùng hoặc tài khoản khóa

Không tạo user trùng; LOCKED không đăng nhập.

### TC-AUTHZ-001: Truy cập sai role/owner

USER không vào owner/admin; owner A không sửa venue/field/booking của owner B.

### TC-OWNER-001: Owner application

Không tạo hai PENDING; admin duyệt đổi role trong cùng transaction.

## 9.2. Danh mục thể thao và migration

### TC-SPORT-001: Seed danh mục

Có đúng FOOTBALL, BADMINTON, PICKLEBALL, TENNIS và sáu field type MVP, code không trùng.

### TC-SPORT-002: Quan hệ field type

Mỗi field type thuộc một sport; không tạo field với type INACTIVE/không tồn tại.

### TC-MIGRATION-001: Ánh xạ sân bóng đá cũ

FIVE_A_SIDE/SEVEN_A_SIDE/ELEVEN_A_SIDE được map sang FOOTBALL_5/7/11; booking, giá và bảo trì giữ nguyên field_id.

### TC-MIGRATION-002: Dữ liệu lịch sử payment

Booking cũ được backfill LEGACY_FULL_ONLINE/rate 1/deposit bằng total; không tự diễn giải payment toàn bộ cũ thành tiền cọc 30%.

## 9.3. Venue, địa chỉ và tìm kiếm

### TC-VENUE-001: Venue mới

Owner hiện tại, PENDING và chưa công khai.

### TC-ADMIN-UNIT-001: Danh mục và dropdown phụ thuộc

Seed đủ 34 tỉnh/thành phố và 3.321 phường/xã/đặc khu; API ward chỉ trả đơn vị thuộc province hợp lệ, từ chối mã tỉnh thiếu hoặc không tồn tại.

### TC-ADMIN-UNIT-002: Validation và snapshot địa chỉ

Tạo/sửa venue với province/ward hợp lệ lưu đúng code và tên chính thức; ward thuộc province khác bị từ chối và rollback. Form edit giữ đúng hai lựa chọn.

### TC-ADMIN-UNIT-003: Hiển thị, tìm kiếm và legacy

`venue.full_address` ưu tiên địa chỉ chi tiết + ward_name + province_name; venue chỉ có district/city vẫn hiển thị và tìm được. Tìm riêng theo ward hoặc province trả đúng venue chuẩn hóa.

### TC-DIRECTIONS-001: Liên kết chỉ đường

Danh sách, chi tiết và Admin đều có nút mở Google Maps ở tab mới; URL luôn dùng `full_address` hiện tại, không phụ thuộc tọa độ legacy.

### TC-DIRECTIONS-002: Không nhúng Google Maps

HTML không tải `maps.googleapis.com`, không chứa map container, Places Autocomplete, API key hoặc script bản đồ.

### TC-DIRECTIONS-003: Giữ dữ liệu legacy

Owner sửa địa chỉ hoặc thông tin khác không làm mất Place ID/tọa độ legacy; form mới không hiển thị các trường này.

### TC-DIRECTIONS-004: Duyệt không phụ thuộc tọa độ

Admin có thể duyệt venue có địa chỉ hành chính hợp lệ mà không cần Place ID/tọa độ.

### TC-SEARCH-001: Kết hợp bộ lọc

Từ khóa + sport + field type + khoảng giá trả đúng venue có field ACTIVE phù hợp.

### TC-SEARCH-002: Sport/type không khớp

UI tự áp dụng tìm kiếm khi đổi sport, chỉ trả về venue có field thuộc sport đó và card chỉ liệt kê field type đang khớp. Danh sách nút field type không có nút “Tất cả”, chỉ hiển thị loại thuộc sport đã chọn, cho bấm lại để bỏ lọc chi tiết và tự xóa lựa chọn cũ khi đổi sport. URL bị sửa thành FOOTBALL cùng TENNIS_STANDARD vẫn hiển thị lỗi, không trả kết quả sai.

### TC-SEARCH-003: Wildcard và phân trang

%, _ và \ được hiểu như text; 10 kết quả chia 9/1 và giữ query.

## 9.4. Field, giá và bảo trì

### TC-FIELD-001: Field đa môn

Tạo field với field_type_id hợp lệ, mặc định INACTIVE; tên trùng trong cùng venue bị từ chối.

### TC-FIELD-002: Một field một sport

Không thể gắn nhiều field type/sport cho cùng field; field đã có booking không được đổi type.

### TC-PRICE-001: Khung giá chồng

Từ chối price slot ACTIVE giao nhau cùng field/ngày.

### TC-PRICE-002: Booking qua nhiều giá

Tách đúng đoạn/subtotal và tổng.

### TC-MAINT-001: Bảo trì trùng

Từ chối bảo trì chồng booking hoặc bảo trì ACTIVE khác; booking không tạo trong bảo trì.

## 9.5. Availability, booking và play format

### TC-BOOKING-001: Booking hợp lệ

Tạo CONFIRMED, giữ 15 phút, snapshot giá/cọc và contribution đúng mode.

### TC-BOOKING-002: Bước/thời lượng sai

Từ chối 18:10–19:40 hoặc khoảng dưới 60 phút.

### TC-BOOKING-003: Trùng lịch

Booking 18:00–20:00 từ chối mọi khoảng giao nhau; chấp nhận kết thúc 18:00 hoặc bắt đầu 20:00.

### TC-BOOKING-004: Giới hạn đặt trước

Mọi booking mode dưới 60 phút đều bị từ chối; FIND_OPPONENT từ đủ 60 phút được chấp nhận; quá 30 ngày bị từ chối.

### TC-BOOKING-005: Availability hết hạn

CONFIRMED quá initial_payment_due_at chưa có payment không tiếp tục chặn lưới; job chuyển EXPIRED idempotent.

### TC-CONFIG-001: Booking mới không dùng play format

Với bóng đá, cầu lông, tennis và pickleball, quote/create cho phép cả ba booking mode mà không cần play format; booking mới lưu `NULL`. Payload legacy có `play_format` không được dùng để thay đổi rule hoặc dữ liệu mới.

### TC-CONFIG-002: Giới hạn FIND_PLAYERS

Chấp nhận `1 <= requested_players < field.capacity`; từ chối 0, số âm, thiếu giá trị hoặc giá trị lớn hơn hay bằng capacity.

## 9.6. Cọc và contribution

### TC-DEPOSIT-001: Tính 30%

Booking mới DEPOSIT_30, tổng 600.000đ → cọc 180.000đ và còn tại sân 420.000đ.

Riêng FIND_OPPONENT, creator trả 90.000đ đã giữ sân và giao diện còn 510.000đ tại sân; khi đối thủ trả thêm 90.000đ thì còn 420.000đ.

### TC-DEPOSIT-002: Làm tròn

Tổng không chia hết cho tỷ lệ → deposit/contribution là số nguyên VND, không thu dư và tổng contribution đúng deposit_amount.

### TC-DEPOSIT-003: Không tin frontend

Form sửa deposit_amount/amount → backend bỏ qua và tính lại từ total.

### TC-CONTRIB-001: DIRECT_BOOKING

Một CREATOR contribution bằng toàn bộ cọc.

### TC-CONTRIB-002: FIND_PLAYERS

Một CREATOR contribution bằng toàn bộ cọc; không tạo PLAYER contribution.

### TC-CONTRIB-003: FIND_OPPONENT

Creator/opponent mỗi bên một nửa cọc; tổng đúng deposit_amount.

## 9.7. Payment MoMo

### TC-PAYMENT-000: MOCK

User đúng quyền thanh toán contribution còn hạn → một MOCK/SUCCESS, cập nhật contribution/paid_amount/status trong transaction và ghi rõ không trừ tiền.

### TC-PAYMENT-001: Create Sandbox

Amount từ contribution; order/request duy nhất; HMAC đúng; trả payUrl.

### TC-PAYMENT-002: Không tin redirect

Redirect thành công nhưng chưa IPN → payment chưa SUCCESS.

### TC-PAYMENT-003: IPN hợp lệ/sai/lặp

IPN hợp lệ cập nhật đúng một lần; sai chữ ký/amount không cập nhật; gửi lặp idempotent.

### TC-PAYMENT-004: Thử lại và chống thu dư

FAILED có thể thử lại trong hạn; không payment nào làm paid_amount vượt deposit_amount.

## 9.8. FIND_PLAYERS

### TC-PLAYER-001: Mở kèo

Creator thanh toán đủ cọc → booking PAID và được tạo match FIND_PLAYERS.

### TC-PLAYER-002: Số vị trí

Creator chọn required_players hợp lệ; snapshot ở booking và copy sang match. Từ chối 0, âm hoặc vượt capacity/play format.

### TC-PLAYER-003: Số Zalo bắt buộc

Thiếu/sai định dạng hoặc chưa đồng ý chia sẻ → không tạo yêu cầu.

### TC-PLAYER-004: Bảo vệ số điện thoại

Trang công khai, user khác và creator trước khi chấp nhận không nhận số; sau chấp nhận chỉ creator thấy.

### TC-PLAYER-005: Chấp nhận không thanh toán

Creator chấp nhận → JOINED ngay, contribution_id/payment_due_at NULL và không tạo payment.

### TC-PLAYER-006: Đủ người và cạnh tranh

Hai request cạnh tranh vị trí cuối → chỉ một JOINED; match FULL đúng required_players.

### TC-PLAYER-007: Rút

JOINED rút → WITHDRAWN, mở vị trí, không tạo refund.

### TC-PLAYER-008: Booking kết thúc

UI không tiếp tục hiển thị số liên hệ sau COMPLETED/CANCELLED.

## 9.9. FIND_OPPONENT

### TC-OPPONENT-001: Creator cọc

Creator trả 50% deposit_amount trong 15 phút → PARTIALLY_PAID và mở match.

### TC-OPPONENT-002: Đối thủ cọc

Một đại diện bấm nhận kèo → tự chuyển ACCEPTED_AWAITING_PAYMENT, không cần creator duyệt; trả phần còn lại → participant JOINED, booking PAID/match CONFIRMED.

### TC-OPPONENT-003: Hết 15 phút

Không thanh toán → participant EXPIRED, contribution được giải phóng và kèo mở lại.

### TC-OPPONENT-004: Không vượt giờ bắt đầu

Thời hạn 15 phút được cắt tại giờ booking bắt đầu; sau giờ này không nhận suất hoặc bắt đầu payment đối thủ mới.

### TC-OPPONENT-005: Không tìm được đối thủ

Đến giờ bắt đầu chưa có đối thủ → bài không còn mở, yêu cầu chưa hoàn tất hết hiệu lực, booking vẫn PARTIALLY_PAID/chiếm chỗ và không tạo top-up/refund. Số còn lại tại sân bằng 85% total.

### TC-OPPONENT-006: Đối thủ đã cọc chủ động rút

Participant chuyển WITHDRAWN, contribution chuyển FORFEITED, không refund, kèo mở lại và paid_amount không giảm. Người thay thế được chấp nhận mà không bị thu lại cùng phần cọc.

### TC-OPPONENT-007: Tranh chấp một suất

Hai đội bấm nhận gần đồng thời → khóa match/contribution chỉ cho một participant ở ACCEPTED_AWAITING_PAYMENT; đội còn lại nhận thông báo suất đang được giữ và không tạo payment/contribution dư.

### TC-OPPONENT-008: Yêu cầu PENDING trước ADR-028

Đại diện có yêu cầu PENDING cũ tự bấm tiếp tục → chính participant đó chuyển ACCEPTED_AWAITING_PAYMENT và giữ suất; không cần creator duyệt lại.

### TC-OPPONENT-009: Lịch cá nhân và liên hệ sau cọc

Trước payment SUCCESS, participant không thấy số creator. Sau payment SUCCESS, participant `JOINED`, kèo xuất hiện trong “Lịch & kèo của tôi”; creator và participant thấy đúng số Zalo của nhau, còn khách/user không liên quan không thấy số.

### TC-OPPONENT-010: Kèo lịch sử thiếu snapshot liên hệ

Match đã JOINED nhưng snapshot liên hệ NULL hiển thị form bổ sung cho đúng bên; sau khi nhập số và đồng ý chia sẻ, hai snapshot được lưu và chỉ hai bên xem được. Participant vẫn không truy cập được route sửa/hủy booking của creator.

## 9.10. Refund

### TC-REFUND-001: Owner hủy

PARTIALLY_PAID/PAID → refund 100% mọi khoản cọc; chỉ CANCELLED sau SUCCESS.

### TC-REFUND-002: Creator chủ động hủy

DIRECT_BOOKING/FIND_PLAYERS hoặc FIND_OPPONENT chưa có payment đối thủ: creator không được refund, payment giữ SUCCESS, khoản đã đóng được ghi nhận là bị giữ và booking chuyển CANCELLED.

### TC-REFUND-003: Creator hủy sau khi đối thủ đã cọc

Creator mất phần cọc của mình; chỉ tạo refund 100% payment đối thủ. Booking giữ REFUND_PENDING và chỉ CANCELLED sau khi refund SUCCESS.

### TC-REFUND-004: Refund đang xử lý/lặp

Giữ REFUND_PENDING; query/retry idempotent và không hoàn quá payment gốc.

### TC-REFUND-005: Thu trùng/sai do hệ thống

Hoàn 100% khoản bị ảnh hưởng, không sửa payment SUCCESS gốc và không tạo refund trùng khi retry callback/job.

### TC-REFUND-006: FIND_PLAYERS rút

Không có payment online nên không tạo refund.

## 9.11. Transaction, constraint và bảo mật

### TC-TX-001: Commit booking thất bại

Rollback booking, price detail và contribution.

### TC-TX-002: IPN commit thất bại

Rollback payment/contribution/booking; xử lý lại an toàn.

### TC-TX-003: Đồng thời

Chỉ một booking giao nhau, một payment SUCCESS/contribution và một participant ở vị trí cuối được commit.

### TC-DB-001: Filtered index

Cho nhiều provider_trans_id NULL nhưng không cho trùng mã khác NULL hoặc hai SUCCESS cùng contribution.

### TC-SEC-001: Secret và API key

Không có MoMo secret, server Maps key hoặc connection string trong Git/UI/log.

### TC-SEC-002: Phạm vi số điện thoại

Serialization/template/log không làm lộ contact_phone ngoài creator sau khi chấp nhận.

## 9.12. Admin

### TC-ADMIN-001: Phân quyền khu quản trị

USER/OWNER truy cập dashboard, tài khoản hoặc giám sát Admin → backend trả 403.

### TC-ADMIN-002: Khóa và mở khóa tài khoản

Admin khóa user → user không đăng nhập được, dữ liệu lịch sử vẫn còn; mở khóa → user đăng nhập lại được. Admin không được tự khóa tài khoản đang dùng và không được gửi trạng thái ngoài ACTIVE/LOCKED.

### TC-ADMIN-003: Tìm kiếm tài khoản và bảo vệ secret

Lọc theo tên/email, role và status → kết quả đúng; HTML không chứa password hash, secret key hoặc connection string.

### TC-ADMIN-004: Giám sát dữ liệu MVP

Admin xem được sport/field type, booking và match; contribution, payment, refund được gom đúng dưới booking liên quan. Bộ lọc trạng thái/sport/ngày/mã hoạt động và màn hình không có thao tác xóa lịch sử.

### TC-ADMIN-005: Tổng hợp cảnh báo và chi tiết booking

Dashboard tổng quan giữ các số liệu cảnh báo; màn hình giám sát không lặp lại khối cảnh báo lớn. Admin lọc booking chưa đủ cọc, lỗi payment, refund đang xử lý hoặc đã hoàn thành; mở một booking → xem được thông tin sân, người đặt, tiến độ cọc, contribution, payment, refund, match và dòng thời gian ở chế độ chỉ xem; mã booking không tồn tại được xử lý an toàn.

### TC-ADMIN-006: Nhóm dữ liệu quản trị và nội dung thân thiện

Admin chọn cơ sở rồi chọn sân → “Đặt sân & dòng tiền” và “Kèo thi đấu” chỉ hiển thị dữ liệu của sân đã chọn; khi xem toàn hệ thống, dữ liệu được gom thành từng sân có thể thu gọn. Mỗi booking chỉ có một thẻ và dòng tiền có thể mở rộng. Trang tài khoản gom theo vai trò rồi trạng thái. Nội dung dùng tiếng Việt dành cho người sử dụng, không hiển thị trực tiếp mã kỹ thuật như MOCK hoặc OWNER.

### TC-ADMIN-007: Tìm kiếm và phân trang khi có nhiều cơ sở

Tạo 50 cơ sở ở nhiều phường/xã → Admin tìm được theo tên hoặc địa chỉ, lọc đúng tỉnh/thành phố và phường/xã/đặc khu, mỗi trang chỉ hiển thị tối đa 10 cơ sở. Cơ sở có 30 sân vẫn tìm được mọi sân, chỉ hiện 8 sân đầu và nút “Xem thêm”. Chuyển trang vẫn giữ điều kiện lọc; chọn một cơ sở ở trang sau vẫn hiển thị đúng danh sách sân.

### TC-ADMIN-009: Người nhận kèo thực tế

Kèo có 5 bản ghi participant gồm 1 `JOINED` và 4 `WITHDRAWN` → màn hình hiển thị 1 người đã nhận kèo cùng đúng tên; 4 bản ghi đã rút chỉ xuất hiện dưới dạng số lịch sử, không bị tính thành người tham gia.

### TC-ADMIN-008: Cập nhật trang giám sát tại chỗ

Admin chọn cơ sở, sân, nhóm dữ liệu, bộ lọc hoặc phân trang → chỉ vùng giám sát được cập nhật, thanh điều hướng không tải lại; URL thay đổi đúng và nút Back/Forward khôi phục được trạng thái trước đó.

## 9.13. Kiểm tra hồi quy

- Booking/availability/price/maintenance hiện có vẫn hoạt động sau migration.
- Venue bóng đá cũ vẫn xuất hiện đúng sport/type.
- Provider MOCK vẫn dùng được cho test tự động.
- Các trang lịch sử phân nhóm và owner booking không bị hỏng.
- flask db upgrade/check chạy thành công trên SQL Server; git diff --check không có lỗi.
