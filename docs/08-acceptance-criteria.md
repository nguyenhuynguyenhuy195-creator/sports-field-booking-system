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
- Venue mới phải có địa chỉ/place ID/tọa độ hợp lệ trước khi admin duyệt ACTIVE.
- Admin duyệt lưu người/thời điểm/ghi chú.
- Field thuộc venue của owner, mặc định INACTIVE và không trùng tên trong cùng venue.
- Chỉ field ACTIVE thuộc venue ACTIVE xuất hiện để đặt.

## AC-004: Google Places và tìm vị trí

- Owner chọn gợi ý địa chỉ, xem được marker và lưu place ID/latitude/longitude.
- Backend từ chối latitude ngoài [-90,90], longitude ngoài [-180,180] hoặc cặp tọa độ thiếu một phía.
- Venue cũ không tọa độ vẫn tìm theo từ khóa nhưng không xuất hiện trong kết quả bán kính.
- User chọn 3/5/10 km và nhận đúng venue ACTIVE nội bộ nằm trong bán kính, sắp theo khoảng cách.
- Từ chối vị trí browser không làm lỗi trang; tìm kiếm văn bản vẫn dùng được.
- Nút chỉ đường mở Google Maps; hệ thống không tự xây tuyến đường.
- Không có venue ngoài database xuất hiện do Nearby Search.

## AC-005: Tìm kiếm và lọc

- Tìm theo tên/địa chỉ/quận/thành phố không phân biệt hoa thường.
- Wildcard được escape.
- Lọc sport, field type và giá dùng riêng hoặc kết hợp được.
- Field type phải thuộc sport đã chọn.
- “Giá từ” lấy từ price slot ACTIVE phù hợp.
- Kết quả tối đa 9 venue/trang và giữ query khi chuyển trang.
- Bộ lọc/tọa độ sai hiển thị lỗi tiếng Việt, không làm lỗi server.

## AC-006: Giá và bảo trì

- Khung giá không chồng nhau và phải phủ toàn bộ booking.
- Backend tách đúng đoạn giá, tính total và lưu snapshot.
- Bảo trì ACTIVE không chồng bảo trì/booking chiếm chỗ.
- Booking không tạo được trong thời gian bảo trì.

## AC-007: Availability và tạo booking

- Endpoint trả mốc 30 phút với trạng thái AVAILABLE, BOOKED, MAINTENANCE, NO_PRICE hoặc PAST.
- Chọn khoảng liên tục tối thiểu 60 phút, trong giờ mở cửa và tối đa 30 ngày.
- DIRECT_BOOKING/FIND_PLAYERS đặt trước tối thiểu 60 phút.
- FIND_OPPONENT đặt trước tối thiểu 24 giờ.
- Submit kiểm tra lại trùng lịch/giá/bảo trì trong transaction.
- Booking tạo CONFIRMED, giữ chỗ 15 phút và có price snapshot.

## AC-008: Play format

- Bóng đá không nhận SINGLES/DOUBLES.
- Cầu lông, pickleball và tennis bắt buộc SINGLES hoặc DOUBLES.
- SINGLES không chấp nhận FIND_PLAYERS.
- DOUBLES cho phép DIRECT_BOOKING, FIND_OPPONENT hoặc FIND_PLAYERS.
- Validation nằm ở backend, không chỉ ẩn option frontend.

## AC-009: Tính cọc 30%

- deposit_rate snapshot bằng 0.3000.
- deposit_amount được tính server-side từ total_amount và làm tròn đến đồng.
- Booking mới là DEPOSIT_30; booking cũ là LEGACY_FULL_ONLINE với rate 1 để bảo toàn payment/contribution.
- balance tại sân bằng total_amount trừ deposit_amount.
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
- required_players do creator chọn nhưng không vượt giới hạn field/play format.
- Lựa chọn được snapshot ở `bookings.requested_players` và copy chính xác sang match sau khi creator cọc thành công.
- Người xin ghép bắt buộc nhập số Zalo và đồng ý chia sẻ có điều kiện.
- Creator không xem được số trước khi chấp nhận; user khác không xem được.
- Chấp nhận chuyển participant JOINED ngay, không tạo payment_due_at/contribution/payment.
- Người ghép rút chuyển WITHDRAWN và mở lại vị trí, không tạo refund.
- Match FULL khi đủ participant JOINED.

## AC-014: FIND_OPPONENT

- Creator thanh toán 50% deposit_amount trong 15 phút.
- Payment thành công chuyển booking PARTIALLY_PAID và cho mở match.
- Chỉ một đại diện đối thủ được chấp nhận.
- Đối thủ có tối đa 15 phút thanh toán và không vượt matchmaking_deadline.
- Đối thủ thanh toán đủ làm booking PAID/match CONFIRMED.
- Creator top-up đủ trước funding_deadline làm booking PAID và nghĩa vụ đối thủ WAIVED.

## AC-015: Deadline tìm đối thủ

- matchmaking_deadline bằng giờ bắt đầu trừ 12 giờ.
- funding_deadline bằng matchmaking_deadline cộng 30 phút.
- Không cho tạo FIND_OPPONENT nếu còn dưới 24 giờ.
- Sau matchmaking_deadline không nhận payment đối thủ mới.
- Quá funding_deadline chưa đủ cọc chuyển REFUND_PENDING.

## AC-016: Refund 80/20

- Không đủ cọc FIND_OPPONENT: creator được hoàn 80% khoản đã đóng.
- 20% khoản đã đóng được lưu ở cancellation_fee_amount.
- Không tính phí trên total_amount.
- Payment đối thủ cần hoàn do lỗi không thuộc họ được hoàn 100%.
- Chỉ chuyển CANCELLED sau khi refund bắt buộc thành công.

## AC-017: Owner hủy

- Chỉ owner của field được hủy và bắt buộc nhập lý do.
- CONFIRMED chưa thu tiền chuyển thẳng CANCELLED.
- PARTIALLY_PAID/PAID chuyển REFUND_PENDING.
- Hoàn 100% mọi khoản cọc đã thu.
- Payment gốc giữ SUCCESS, refund lưu riêng và idempotent.

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
- Hai yêu cầu đối thủ không cùng chiếm contribution cuối.
- Hai yêu cầu người ghép không làm match vượt required_players.
- Commit lỗi rollback toàn bộ thay đổi.
- Filtered unique index hoạt động đúng trên SQL Server.

## AC-021: Ranh giới MVP

- Không có MoMo Production, QR ngân hàng thật, ví admin hoặc payout.
- Không ghi nhận thanh toán 70% tại sân.
- Không tự chấm điểm hoặc khóa user vì no-show.
- Không lấy venue ngoài hệ thống từ Google Nearby Search.
- README/UI phân biệt rõ phần đã triển khai và thiết kế chờ migration.
