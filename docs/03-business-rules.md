# 3. Quy tắc nghiệp vụ

## 3.1. Tài khoản, phân quyền và liên hệ

### BR-001: Đăng nhập trước khi thao tác

User phải đăng nhập trước khi tạo booking, tạo kèo, gửi yêu cầu tham gia hoặc thanh toán.

### BR-002: Phân quyền backend

- USER không được truy cập chức năng OWNER hoặc ADMIN.
- OWNER không được truy cập chức năng ADMIN.
- Không dựa vào việc ẩn nút trên frontend để bảo vệ chức năng.

### BR-003: Yêu cầu trở thành owner

- Tài khoản mới luôn có role USER.
- User có tối đa một yêu cầu trở thành owner đang PENDING.
- Chỉ admin được chấp nhận hoặc từ chối.
- Role chỉ chuyển thành OWNER khi yêu cầu được chấp nhận.

### BR-004: Quyền sở hữu

- Owner chỉ quản lý venue có owner_id của mình.
- Owner chỉ quản lý field, giá, bảo trì và booking thuộc venue của mình.

### BR-005: Khóa tài khoản và lịch sử

- Tài khoản LOCKED không được đăng nhập hoặc tạo giao dịch mới.
- Không xóa vật lý lịch sử booking, payment, contribution, refund hoặc match đã phát sinh.
- Dữ liệu đã được tham chiếu phải chuyển trạng thái thay vì cascade delete.

### BR-006: Số điện thoại dùng Zalo

- Yêu cầu tham gia kèo FIND_PLAYERS bắt buộc có số điện thoại liên hệ hợp lệ.
- Số có thể lấy sẵn từ tài khoản nhưng user phải kiểm tra và đồng ý chia sẻ khi gửi yêu cầu.
- Số điện thoại không xuất hiện trên danh sách/chi tiết kèo công khai.
- Chỉ creator của match được xem số sau khi yêu cầu đã được chấp nhận.
- Giao diện không tiếp tục hiển thị số sau khi booking hoàn thành hoặc bị hủy.

## 3.2. Bộ môn, venue, field, giá và bảo trì

### BR-007: Danh mục thể thao

- MVP chỉ có FOOTBALL, BADMINTON, PICKLEBALL và TENNIS.
- Danh mục do hệ thống seed và quản lý; owner không tự thêm sport hoặc field type.
- Field type thuộc đúng một sport.
- Bóng đá có FOOTBALL_5, FOOTBALL_7 và FOOTBALL_11.
- Ba môn dùng vợt dùng loại sân STANDARD trong MVP.

### BR-008: Mỗi field thuộc một bộ môn

- Mỗi field bắt buộc tham chiếu đúng một field type.
- Sport của field được suy ra qua field type; một field không phục vụ đồng thời nhiều sport.
- Một venue có thể chứa nhiều field thuộc nhiều sport.
- Field mới mặc định INACTIVE và chỉ field ACTIVE thuộc venue ACTIVE mới nhận booking.
- Không được đổi field type sau khi field đã có booking; owner phải chuyển field cũ INACTIVE và tạo field mới để không làm sai lịch sử.

### BR-009: Duyệt venue và vị trí

- Venue mới có trạng thái PENDING.
- Chỉ venue ACTIVE mới hiển thị công khai.
- Admin có thể chuyển venue thành ACTIVE hoặc HIDDEN.
- Venue mới phải có địa chỉ, Google Place ID và cặp latitude/longitude hợp lệ trước khi được duyệt ACTIVE.
- Venue cũ chưa có tọa độ vẫn có thể tìm bằng văn bản nhưng không tham gia tìm theo bán kính cho đến khi owner bổ sung vị trí.

### BR-010: Tìm kiếm và lọc venue

- Từ khóa tìm trên tên, địa chỉ, quận/huyện và tỉnh/thành phố.
- Khoảng trắng được chuẩn hóa; ký tự wildcard phải được hiểu như văn bản thường.
- Chỉ trả venue ACTIVE có ít nhất một field ACTIVE.
- Bộ lọc sport, field type và khoảng giá được kết hợp đồng thời.
- “Giá từ” là hourly_price thấp nhất của price slot ACTIVE trên field ACTIVE còn phù hợp với bộ lọc.
- Giá tối thiểu không được lớn hơn giá tối đa; điều kiện được giữ khi chuyển trang.

### BR-011: Tìm quanh vị trí

- Chỉ chấp nhận bán kính 3 km, 5 km hoặc 10 km.
- Vị trí user lấy từ Browser Geolocation sau khi được đồng ý; backend phải validate latitude/longitude.
- Kết quả chỉ gồm venue nội bộ đã ACTIVE và có tọa độ.
- Khoảng cách là đường chim bay gần đúng; nút chỉ đường mở Google Maps, hệ thống không tự tính tuyến đường.
- User từ chối quyền vị trí không làm hỏng tìm kiếm văn bản.
- Không dùng Google Nearby Search để đưa cơ sở ngoài hệ thống vào kết quả.

### BR-012: Khung giá

- Giá cấu hình theo field, ngày trong tuần và khoảng giờ.
- Hai khung giá ACTIVE cùng field/cùng ngày không được chồng nhau.
- start_time phải nhỏ hơn end_time và hourly_price phải lớn hơn 0.
- Không dùng base_price thay thế khi thiếu cấu hình.

### BR-013: Tính giá booking

- Toàn bộ thời gian booking phải được phủ bởi price slot ACTIVE.
- Booking qua nhiều khung giá được tách thành các đoạn và cộng subtotal.
- Backend lấy giá từ database và lưu snapshot; không tin giá hoặc tổng tiền từ frontend.

### BR-014: Lịch bảo trì

- Owner tạo bảo trì theo field, ngày và khoảng giờ.
- Hai lịch ACTIVE cùng field không được chồng nhau.
- Không tạo bảo trì giao với booking đang chiếm chỗ.
- Booking không được giao với bảo trì còn hiệu lực.

## 3.3. Thời gian, hình thức thi đấu và trùng lịch

### BR-015: Thời gian booking

- start_time phải nhỏ hơn end_time và không đi qua nửa đêm.
- Bước thời gian là 30 phút; thời lượng tối thiểu 60 phút.
- Booking nằm trong giờ mở cửa venue và không quá 30 ngày.
- Lưới giờ chỉ mang tính tư vấn; backend kiểm tra lại khi quote và khi tạo.

### BR-016: Thời gian đặt trước

- DIRECT_BOOKING và FIND_PLAYERS phải tạo trước giờ bắt đầu ít nhất 60 phút.
- FIND_OPPONENT phải tạo trước giờ bắt đầu ít nhất 24 giờ.
- Đối thủ phải được chấp nhận và thanh toán xong phần cọc trước giờ bắt đầu 12 giờ.

### BR-017: Hình thức thi đấu

- Booking bóng đá không chọn play format; loại sân xác định quy mô thi đấu chính.
- Booking cầu lông, pickleball hoặc tennis bắt buộc chọn SINGLES hoặc DOUBLES.
- SINGLES có tối đa 2 người và chỉ hỗ trợ DIRECT_BOOKING hoặc FIND_OPPONENT.
- DOUBLES có tối đa 4 người và hỗ trợ cả ba booking mode.
- FIND_PLAYERS cho bóng đá cho phép creator chọn số vị trí cần tìm trong giới hạn capacity của field.

### BR-018: Trùng lịch

Một field không có hai booking chiếm chỗ giao nhau:

> new_start < existing_end AND new_end > existing_start

Trạng thái chiếm chỗ: CONFIRMED, PARTIALLY_PAID, PAID và REFUND_PENDING.

Trạng thái không chiếm chỗ: REJECTED, CANCELLED, EXPIRED và COMPLETED.

Kiểm tra và tạo booking phải nằm trong cùng transaction.

## 3.4. Vòng đời booking và tiền cọc

### BR-019: Ba booking mode

- DIRECT_BOOKING: creator chịu toàn bộ khoản cọc.
- FIND_OPPONENT: creator và đối thủ mỗi bên chịu một nửa khoản cọc.
- FIND_PLAYERS: creator chịu toàn bộ khoản cọc; người ghép trả tại sân.
- booking_mode mô tả mục đích đặt sân, không phải cổng thanh toán.
- FIND_PLAYERS bắt buộc snapshot `requested_players` ngay trên booking để giữ lựa chọn trước khi match được mở.

### BR-020: Tính khoản cọc

- deposit_rate của MVP là 30% tổng tiền sân.
- deposit_amount được backend tính, làm tròn đến đồng và lưu snapshot khi tạo booking.
- Booking mới dùng payment_policy DEPOSIT_30. Booking cũ được gắn LEGACY_FULL_ONLINE để lịch sử thanh toán toàn bộ không bị diễn giải thành cọc.
- paid_amount chỉ theo dõi khoản cọc online ròng sau refund và không vượt deposit_amount.
- Số còn lại tại sân bằng total_amount trừ deposit_amount; hệ thống chỉ hiển thị, không thu hoặc xác nhận phần này.

### BR-021: Tạo và giữ chỗ tự động

- Backend kiểm tra field/venue, sport, play format, thời gian, bảo trì, trùng lịch và giá.
- Booking hợp lệ tạo ở CONFIRMED và giữ chỗ 15 phút.
- initial_payment_due_at bằng thời điểm tạo cộng 15 phút.
- Owner không duyệt booking thông thường; chỉ theo dõi hoặc hủy khi có sự cố.

### BR-022: Khoản cọc đầu tiên

- DIRECT_BOOKING và FIND_PLAYERS: creator phải thanh toán đủ deposit_amount trong 15 phút.
- FIND_OPPONENT: creator thanh toán 50% deposit_amount trong 15 phút.
- CONFIRMED chưa có khoản cọc đầu tiên sau 15 phút chuyển EXPIRED.
- Khi đã thu một phần cọc, booking chuyển PARTIALLY_PAID; khi đủ deposit_amount, booking chuyển PAID.
- Trạng thái PAID trong MVP nghĩa là đã hoàn thành nghĩa vụ cọc online, không có nghĩa 70% tại sân đã được ghi nhận.

### BR-023: Hạn tìm đối thủ và top-up

- matchmaking_deadline bằng giờ bắt đầu trừ 12 giờ.
- Đối thủ được chấp nhận có 15 phút thanh toán nhưng payment_due_at không được vượt matchmaking_deadline.
- Đến matchmaking_deadline chưa nhận đủ phần cọc đối thủ, creator có thêm 30 phút để top-up.
- funding_deadline bằng matchmaking_deadline cộng 30 phút.
- Creator top-up đủ thì booking chuyển PAID và kèo không còn yêu cầu đối thủ thanh toán online.

### BR-024: Không đủ cọc tìm đối thủ

- Quá funding_deadline mà creator không top-up, booking chuyển REFUND_PENDING.
- Hoàn 80% khoản creator đã đóng.
- Giữ 20% khoản creator đã đóng làm phí giữ sân; đây không phải 20% total_amount.
- Nếu phía đối thủ đã có payment hợp lệ nhưng booking không hoàn thành do lỗi không thuộc về họ, hoàn 100%.
- Booking chỉ chuyển CANCELLED khi mọi refund bắt buộc thành công.

### BR-025: Hủy booking

- User được hủy CONFIRMED chưa thu tiền của mình trước giờ bắt đầu ít nhất 2 giờ.
- Creator hủy FIND_OPPONENT đang PARTIALLY_PAID áp dụng chính sách 80/20 tại BR-024.
- User không tự hủy booking PAID qua hệ thống trong MVP.
- Owner được hủy CONFIRMED, PARTIALLY_PAID hoặc PAID khi có sự cố và bắt buộc nhập lý do.
- Owner hủy booking đã thu cọc phải hoàn 100% mọi khoản đã thu.

### BR-026: Hoàn thành

Booking PAID được chuyển COMPLETED sau khi thời gian sử dụng kết thúc. MVP không yêu cầu owner xác nhận 70% thanh toán tại sân.

## 3.5. MoMo Sandbox, contribution và refund

### BR-027: Ranh giới provider

- MoMo Sandbox dùng trong bản trình diễn, không có tiền thật.
- MOCK dùng cho phát triển/test và áp dụng cùng quy tắc số tiền nhưng không gọi MoMo.
- MoMo Production, QR ngân hàng thật, ví admin và payout không thuộc MVP.

### BR-028: Phân bổ contribution

- Tổng amount_due của contribution còn hiệu lực phải bằng deposit_amount, không phải total_amount.
- DIRECT_BOOKING/FIND_PLAYERS tạo một contribution CREATOR bằng toàn bộ deposit_amount.
- FIND_OPPONENT tạo CREATOR và OPPONENT, mỗi contribution bằng 50% deposit_amount; phần cuối được điều chỉnh nếu làm tròn.
- FIND_PLAYERS không tạo contribution PLAYER cho người ghép.
- Contribution PLAYER cũ chỉ được giữ để bảo toàn lịch sử migration, service mới không tạo thêm.

### BR-029: Xác nhận kết quả MoMo

- Amount lấy từ contribution trong database.
- Redirect chỉ dùng hiển thị; chỉ IPN hợp lệ mới cập nhật SUCCESS.
- Backend xác minh HMAC và đối chiếu orderId, requestId, amount và partnerCode.
- IPN, query và refund phải idempotent.
- Payment thành công, contribution, booking và match participant liên quan cập nhật trong transaction phù hợp.

### BR-030: Hoàn tiền

- Refund không ghi đè payment SUCCESS; mỗi lần hoàn là bản ghi riêng.
- Không hoàn vượt số tiền payment gốc.
- Owner hủy: hoàn 100% khoản cọc đã thu.
- Refund chưa xong giữ booking ở REFUND_PENDING.
- Chỉ chuyển CANCELLED sau khi các refund bắt buộc SUCCESS.

## 3.6. Tìm đối thủ và tìm thêm người

### BR-031: Tạo match

- Creator phải sở hữu booking và mỗi booking có tối đa một match.
- booking_mode FIND_OPPONENT chỉ tạo match FIND_OPPONENT.
- booking_mode FIND_PLAYERS chỉ tạo match FIND_PLAYERS.
- Match chỉ mở sau khi khoản cọc creator tương ứng đã thành công.
- Không tạo match cho booking đã hủy, hết hạn, chờ refund hoặc hoàn thành.

### BR-032: Tìm đối thủ

- Một đại diện gửi yêu cầu thay cho phía đối thủ.
- Creator không được tham gia match của chính mình.
- Chỉ creator chấp nhận/từ chối và chỉ một đối thủ được chấp nhận.
- Đối thủ chỉ chính thức JOINED/CONFIRMED sau khi payment cọc SUCCESS, trừ khi creator đã top-up.
- FIND_OPPONENT dùng được cho bóng đá, SINGLES và DOUBLES của môn dùng vợt.

### BR-033: Tìm thêm người

- required_players là số vị trí creator muốn tìm và không tính creator.
- Không chấp nhận vượt required_players hoặc giới hạn của field/play format.
- Người ghép không có contribution, payment_due_at hoặc refund online.
- Khi creator chấp nhận, participant chuyển thẳng JOINED.
- Người ghép thanh toán trực tiếp cho creator tại sân.
- Match chuyển FULL khi số participant JOINED đạt required_players.

### BR-034: Rút khỏi kèo FIND_PLAYERS

- Participant có thể rút trước khi booking bắt đầu; trạng thái chuyển WITHDRAWN và vị trí mở lại.
- Vì participant chưa thanh toán online nên không tạo refund.
- Việc liên hệ, xác nhận và thu tiền tại sân do creator và participant trao đổi qua Zalo.

### BR-035: No-show

- MVP không thu cọc người ghép, không chấm điểm uy tín và không tự động khóa vì no-show.
- Website không bảo đảm participant sẽ đến; creator dùng số Zalo được chia sẻ sau khi chấp nhận để liên hệ.

## 3.7. Quy tắc Google Maps và bảo mật

### BR-036: Google Places và tọa độ

- Owner chọn một dự đoán từ Places Autocomplete rồi kiểm tra ghim.
- Backend không tin tọa độ ẩn từ frontend nếu thiếu validation.
- latitude nằm trong [-90, 90], longitude trong [-180, 180] và phải cùng NULL hoặc cùng có giá trị.
- google_place_id không thay thế primary key nội bộ.

### BR-037: API key

- Key frontend phải giới hạn theo HTTP referrer và chỉ bật API cần thiết.
- Server key, nếu có, phải nằm trong biến môi trường và giới hạn theo API/IP phù hợp.
- Không commit key vào Git, không log secret và phải cấu hình quota/cảnh báo ngân sách.
