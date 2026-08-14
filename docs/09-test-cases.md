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

## 9.3. Venue, Google Maps và tìm kiếm

### TC-VENUE-001: Venue mới

Owner hiện tại, PENDING và chưa công khai.

### TC-MAP-001: Lưu place hợp lệ

Chọn Places prediction → lưu address/place_id/latitude/longitude, render đúng marker.

### TC-MAP-002: Tọa độ sai

Từ chối latitude 91, longitude -181 hoặc chỉ có một tọa độ; rollback.

### TC-MAP-003: Venue cũ thiếu tọa độ

Vẫn tìm theo tên/địa chỉ, không xuất hiện trong tìm bán kính và UI có cảnh báo owner.

### TC-MAP-004: Tìm bán kính

Với user location xác định, 3/5/10 km trả đúng venue ACTIVE nội bộ và sắp theo khoảng cách tăng dần.

### TC-MAP-005: Từ chối Geolocation

Không gọi tìm gần, trang không lỗi và tìm văn bản vẫn hoạt động.

### TC-MAP-006: Không nhập venue ngoài hệ thống

Kết quả không chứa địa điểm chỉ tồn tại trên Google nhưng không có trong bảng venues.

### TC-SEARCH-001: Kết hợp bộ lọc

Từ khóa + sport + field type + khoảng giá trả đúng venue có field ACTIVE phù hợp.

### TC-SEARCH-002: Sport/type không khớp

Chọn FOOTBALL cùng TENNIS_STANDARD hiển thị lỗi, không trả kết quả sai.

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

DIRECT_BOOKING/FIND_PLAYERS dưới 60 phút bị từ chối; FIND_OPPONENT dưới 24 giờ bị từ chối; quá 30 ngày bị từ chối.

### TC-BOOKING-005: Availability hết hạn

CONFIRMED quá initial_payment_due_at chưa có payment không tiếp tục chặn lưới; job chuyển EXPIRED idempotent.

### TC-FORMAT-001: Bóng đá

Từ chối SINGLES/DOUBLES trên field FOOTBALL; cho phép ba booking mode.

### TC-FORMAT-002: Môn dùng vợt

Thiếu play_format bị từ chối; SINGLES + FIND_PLAYERS bị từ chối; DOUBLES cho phép cả ba mode.

## 9.6. Cọc và contribution

### TC-DEPOSIT-001: Tính 30%

Booking mới DEPOSIT_30, tổng 600.000đ → cọc 180.000đ và còn tại sân 420.000đ.

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

Một đại diện được chấp nhận, trả phần còn lại → booking PAID/match CONFIRMED.

### TC-OPPONENT-003: Hết 15 phút

Không thanh toán → participant EXPIRED, contribution được giải phóng và kèo mở lại.

### TC-OPPONENT-004: Không vượt deadline

Thời hạn 15 phút được cắt tại matchmaking_deadline; sau deadline không bắt đầu payment đối thủ mới.

### TC-OPPONENT-005: Creator top-up

Trong 30 phút sau matchmaking_deadline, creator trả phần thiếu → PAID; OPPONENT WAIVED và không thu thêm.

### TC-OPPONENT-006: Không top-up

Quá funding_deadline → REFUND_PENDING; hoàn creator 80%, giữ 20% khoản creator đã cọc.

## 9.10. Refund

### TC-REFUND-001: Owner hủy

PARTIALLY_PAID/PAID → refund 100% mọi khoản cọc; chỉ CANCELLED sau SUCCESS.

### TC-REFUND-002: Refund 80/20

Creator đóng 90.000đ → refund 72.000đ, cancellation fee 18.000đ; không lấy 20% của total.

### TC-REFUND-003: Refund đang xử lý/lặp

Giữ REFUND_PENDING; query/retry idempotent và không hoàn quá payment gốc.

### TC-REFUND-004: FIND_PLAYERS rút

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

## 9.12. Kiểm tra hồi quy

- Booking/availability/price/maintenance hiện có vẫn hoạt động sau migration.
- Venue bóng đá cũ vẫn xuất hiện đúng sport/type.
- Provider MOCK vẫn dùng được cho test tự động.
- Các trang lịch sử phân nhóm và owner booking không bị hỏng.
- flask db upgrade/check chạy thành công trên SQL Server; git diff --check không có lỗi.
