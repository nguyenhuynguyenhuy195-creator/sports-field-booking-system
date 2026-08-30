# 8. Tiêu chí nghiệm thu

## AC-001: Tài khoản và phân quyền

- Email không trùng, mật khẩu được hash, tài khoản mới là USER/ACTIVE.
- Tài khoản LOCKED không đăng nhập được.
- USER/OWNER/ADMIN bị giới hạn đúng quyền ở backend.
- User chỉ có một owner application PENDING; duyệt đổi role trong cùng transaction.

## AC-002: Danh mục đa môn

- Database có đúng bốn sport ACTIVE: bóng đá, cầu lông, pickleball và tennis.
- Có ba field type bóng đá và một field type tiêu chuẩn cho mỗi môn dùng vợt.
- Mỗi field tham chiếu một field type hợp lệ và suy ra đúng một sport.
- Không tạo field với field type INACTIVE hoặc thuộc danh mục không tồn tại.
- Không đổi field type sau khi field đã có booking.
- Dữ liệu field bóng đá cũ được ánh xạ đầy đủ, không mất booking/giá/bảo trì.

## AC-003: Owner tạo venue và field

- owner_id lấy từ current_user.
- Venue mới PENDING và chưa công khai.
- Province phải tồn tại; ward phải tồn tại và thuộc đúng province. Backend lưu cả code và tên từ catalog, không tin tên do frontend gửi.
- Venue mới phải có tỉnh/thành phố, phường/xã và địa chỉ chi tiết hợp lệ trước khi admin duyệt ACTIVE.
- Admin duyệt lưu người/thời điểm/ghi chú.
- Field thuộc venue của owner, mặc định INACTIVE và không trùng tên trong cùng venue.
- Chỉ field ACTIVE thuộc venue ACTIVE xuất hiện để đặt.

## AC-004: Địa chỉ và chỉ đường

- Owner chọn tỉnh rồi chỉ thấy phường/xã/đặc khu trực thuộc; edit load đúng lựa chọn hiện tại.
- Owner nhập địa chỉ chi tiết; backend lưu tên tỉnh/phường từ catalog và không yêu cầu Place ID/tọa độ.
- Form không tải Maps/Places API, không hiển thị bản đồ và không xin quyền vị trí.
- Dữ liệu Place ID/tọa độ legacy được giữ khi Owner sửa thông tin khác.
- Nút chỉ đường mở Google Maps ở tab mới; hệ thống không tự xây tuyến đường.
- Không có venue ngoài database xuất hiện do Nearby Search.

## AC-005: Tìm kiếm và lọc

- Tìm theo tên/địa chỉ/phường-xã/tỉnh-thành phố không phân biệt hoa thường; venue legacy vẫn có fallback `district/city`.
- Wildcard được escape.
- Lọc sport, field type và giá dùng riêng hoặc kết hợp được.
- Field type phải thuộc sport đã chọn.
- “Giá từ” lấy từ price slot ACTIVE phù hợp.
- Kết quả tối đa 9 venue/trang và giữ query khi chuyển trang.
- Bộ lọc sai hiển thị lỗi tiếng Việt, không làm lỗi server.

## AC-006: Giá và bảo trì

- Khung giá không chồng nhau và phải phủ toàn bộ booking.
- Backend tách đúng đoạn giá, tính total và lưu snapshot.
- Bảo trì ACTIVE không chồng bảo trì/booking chiếm chỗ.
- Booking không tạo được trong thời gian bảo trì.

## AC-007: Availability và tạo booking

- Endpoint trả mốc 30 phút với trạng thái AVAILABLE, BOOKED, MAINTENANCE, NO_PRICE hoặc PAST.
- Chọn khoảng liên tục tối thiểu 60 phút, trong giờ mở cửa và tối đa 30 ngày.
- DIRECT_BOOKING/FIND_PLAYERS/FIND_OPPONENT đặt trước tối thiểu 60 phút.
- Submit kiểm tra lại trùng lịch/giá/bảo trì trong transaction.
- Booking tạo CONFIRMED, giữ chỗ 15 phút và có price snapshot.

## AC-008: Cấu hình booking không dùng play format

- UI và BookingForm không có lựa chọn đánh đơn/đôi ở mọi bộ môn.
- Quote/create service không nhận hoặc phụ thuộc `play_format`.
- DIRECT_BOOKING, FIND_OPPONENT và FIND_PLAYERS hoạt động cho mọi bộ môn được hỗ trợ.
- Booking mới luôn lưu `play_format = NULL`; bản ghi legacy có giá trị vẫn đọc được an toàn.

## AC-009: Tính cọc 30%

- deposit_rate snapshot bằng 0.3000.
- deposit_amount được tính server-side từ total_amount và làm tròn đến đồng.
- Booking mới là DEPOSIT_30; booking cũ là LEGACY_FULL_ONLINE với rate 1 để bảo toàn payment/contribution.
- balance tại sân bằng total_amount trừ paid_amount thực thu ròng.
- FIND_OPPONENT chỉ có cọc creator hiển thị còn 85%; khi đối thủ đã cọc hiển thị còn 70%.
- paid_amount không vượt deposit_amount.
- Giao diện không gọi trạng thái PAID là đã thanh toán toàn bộ tiền sân.

## AC-010: Phân bổ contribution

- DIRECT_BOOKING tạo một CREATOR contribution bằng toàn bộ deposit_amount.
- FIND_PLAYERS tạo một CREATOR contribution bằng toàn bộ deposit_amount và không tạo PLAYER contribution mới.
- FIND_OPPONENT tạo CREATOR/OPPONENT; tổng hai phần đúng deposit_amount.
- Tiền lẻ do làm tròn được điều chỉnh ở phần cuối, không thu dư.

## AC-011: MoMo Sandbox và MOCK

- MOCK lấy amount từ contribution, không nhận amount từ form và ghi rõ không trừ tiền thật.
- MoMo tạo order/request duy nhất và HMAC đúng.
- Redirect không tự đánh dấu thành công.
- IPN hợp lệ đúng chữ ký/order/amount/partner mới cập nhật SUCCESS.
- IPN lặp xử lý idempotent; payment thất bại có thể thử lại trong hạn.
- Không thu cọc vượt deposit_amount.

## AC-012: DIRECT_BOOKING

- Creator thanh toán toàn bộ deposit_amount trong 15 phút.
- Payment thành công chuyển contribution PAID và booking PAID.
- Booking PAID vẫn hiển thị 70% trả tại sân.
- Hết 15 phút chưa có payment đầu tiên chuyển EXPIRED.

## AC-013: FIND_PLAYERS

- Creator thanh toán toàn bộ deposit_amount trước khi mở match.
- required_players do creator chọn và phải thỏa `1 <= required_players < field.capacity`.
- Lựa chọn được snapshot ở `bookings.requested_players` và copy chính xác sang match sau khi creator cọc thành công.
- Người xin ghép bắt buộc nhập số Zalo và đồng ý chia sẻ có điều kiện.
- Creator không xem được số trước khi chấp nhận; user khác không xem được.
- Chấp nhận chuyển participant JOINED ngay, không tạo payment_due_at/contribution/payment.
- Người ghép rút chuyển WITHDRAWN và mở lại vị trí, không tạo refund.
- Match FULL khi đủ participant JOINED.

## AC-014: FIND_OPPONENT

- Creator thanh toán 50% deposit_amount trong 15 phút.
- Payment thành công chuyển booking PARTIALLY_PAID, giữ sân hợp lệ và cho mở match.
- Đại diện bấm nhận kèo chuyển thẳng ACCEPTED_AWAITING_PAYMENT, không cần creator duyệt.
- Khóa transaction bảo đảm chỉ một đại diện giữ contribution đối thủ tại một thời điểm.
- Đối thủ có tối đa 15 phút thanh toán và không vượt giờ booking bắt đầu.
- Đối thủ thanh toán đủ làm booking PAID/match CONFIRMED.
- Creator và đối thủ đều phải cung cấp số Zalo cùng sự đồng ý; trước payment thành công hai bên chưa xem số của nhau.
- Sau payment thành công, participant thấy match trong lịch cá nhân và hai bên thấy nút Zalo; user khác không thấy số, participant không có quyền quản lý booking.
- Không có đối thủ thì booking vẫn PARTIALLY_PAID hợp lệ, không yêu cầu creator top-up và không tạo refund.

## AC-015: Thời gian tồn tại của bài tìm đối thủ

- Không cho tạo FIND_OPPONENT nếu còn dưới 60 phút.
- Bài mở đến giờ booking bắt đầu, trừ khi creator đóng sớm hoặc đối thủ thanh toán thành công.
- Tại giờ bắt đầu, không nhận suất/payment mới và các suất chưa hoàn tất hết hiệu lực.
- Đóng bài không hủy booking, không giải phóng sân và không làm mất cọc creator.
- Booking mới để matchmaking_deadline/funding_deadline NULL; deadline cũ chỉ còn cho dữ liệu legacy.

## AC-016: Người chơi chủ động hủy/rút hoặc no-show

- Creator chủ động hủy hoặc no-show không được hoàn phần cọc của mình.
- Đối thủ đã cọc mà chủ động rút/no-show chuyển WITHDRAWN/FORFEITED, không refund và vị trí mở lại.
- Khoản đối thủ bị giữ tiếp tục tính vào paid_amount; người thay thế không bị thu cọc lần hai.
- Creator hủy FIND_OPPONENT sau khi đối thủ đã cọc: creator mất phần của mình, đối thủ được hoàn 100%.
- Payment gốc vẫn SUCCESS; cancellation_fee_amount/contribution FORFEITED lưu đúng lịch sử khoản bị giữ.

## AC-017: Owner hủy

- Chỉ owner của field được hủy và bắt buộc nhập lý do.
- CONFIRMED chưa thu tiền chuyển thẳng CANCELLED.
- PARTIALLY_PAID/PAID chuyển REFUND_PENDING.
- Hoàn 100% mọi khoản cọc đã thu.
- Payment gốc giữ SUCCESS, refund lưu riêng và idempotent.
- Thanh toán trùng/sai do hệ thống cũng hoàn 100% khoản bị ảnh hưởng.

## AC-018: Số điện thoại và riêng tư

- contact_phone được validate và lưu snapshot trên yêu cầu FIND_PLAYERS.
- Response/template công khai không chứa số điện thoại.
- Chỉ creator được xem sau trạng thái chấp nhận/JOINED.
- Khi booking COMPLETED/CANCELLED, giao diện không tiếp tục hiển thị số.
- Không log số đầy đủ trong log thông thường.

## AC-019: Admin giám sát

- Admin xem account, owner application, sport/field type, venue, booking, contribution, payment, refund và match.
- Admin khóa tài khoản/ẩn venue nhưng không xóa lịch sử.
- API key/secret/connection string không xuất hiện trên UI hoặc log.

## AC-020: Transaction và đồng thời

- Hai request đồng thời không tạo booking giao nhau.
- Payment/IPN đồng thời không làm paid_amount vượt deposit_amount.
- Hai thao tác nhận kèo đồng thời không cùng chiếm contribution đối thủ; chỉ một đội nhận được payment_due_at.
- Hai yêu cầu người ghép không làm match vượt required_players.
- Commit lỗi rollback toàn bộ thay đổi.
- Filtered unique index hoạt động đúng trên SQL Server.

## AC-021: Ranh giới MVP

- Không có MoMo Production, QR ngân hàng thật, ví admin hoặc payout.
- Không ghi nhận thanh toán 70% tại sân.
- Không tự chấm điểm hoặc khóa user vì no-show.
- Không lấy venue ngoài hệ thống từ Google Nearby Search.
- README/UI phân biệt rõ phần đã triển khai và thiết kế chờ migration.
