# 2. Phạm vi MVP

## 2.1. Must Have

### Tài khoản

- Đăng ký, đăng nhập và đăng xuất.
- Phân quyền USER, OWNER và ADMIN ở backend.
- User gửi yêu cầu trở thành owner; admin chấp nhận hoặc từ chối.
- Admin khóa hoặc mở tài khoản.
- Số điện thoại của người xin ghép chỉ được chia sẻ đúng phạm vi và sau khi được chấp nhận.

### Danh mục thể thao

- Bốn bộ môn: bóng đá, cầu lông, pickleball và tennis.
- Loại sân bóng đá: 5 người, 7 người và 11 người.
- Cầu lông, pickleball và tennis dùng loại sân tiêu chuẩn trong MVP.
- Mỗi field thuộc đúng một field type; mỗi field type thuộc đúng một sport.
- Dữ liệu danh mục do hệ thống quản lý, owner không tự tạo bộ môn tùy ý.

### Quản lý cơ sở, vị trí và sân

- Owner tạo và sửa venue; venue mới ở trạng thái PENDING.
- Admin duyệt venue thành ACTIVE hoặc ẩn venue.
- Owner chọn địa chỉ bằng Google Places, kiểm tra ghim và lưu tọa độ.
- Venue có tọa độ được hiển thị trên bản đồ và tham gia tìm kiếm theo bán kính.
- Owner tạo field; field mới mặc định INACTIVE.
- Owner cấu hình giá theo field, ngày trong tuần và khoảng giờ.
- Owner tạo lịch bảo trì; không cho bảo trì trùng booking đang chiếm chỗ.
- Chỉ field ACTIVE thuộc venue ACTIVE mới được đặt.

### Tìm kiếm và Google Maps

- Tìm theo tên, địa chỉ, quận/huyện hoặc tỉnh/thành phố.
- Lọc theo bộ môn, loại sân và khoảng giá.
- Tìm venue đã được duyệt trong bán kính 3 km, 5 km hoặc 10 km từ vị trí user.
- Hiển thị khoảng cách gần đúng, ghim bản đồ và nút mở Google Maps để chỉ đường.
- Nếu user từ chối quyền vị trí hoặc venue chưa có tọa độ, tìm kiếm văn bản vẫn hoạt động.
- Không dùng Google Nearby Search để đưa cơ sở ngoài hệ thống vào kết quả.

### Booking

- User chọn ngày, giờ bắt đầu và kết thúc theo bước 30 phút; tối thiểu 60 phút.
- Cầu lông, pickleball và tennis bắt buộc chọn SINGLES hoặc DOUBLES.
- Bóng đá không chọn đơn/đôi; loại sân xác định quy mô thi đấu chính.
- User chọn DIRECT_BOOKING, FIND_OPPONENT hoặc FIND_PLAYERS.
- DIRECT_BOOKING và FIND_PLAYERS đặt trước tối thiểu 60 phút.
- FIND_OPPONENT chỉ được tạo trước giờ bắt đầu ít nhất 24 giờ.
- Không đặt quá 30 ngày, ngoài giờ mở cửa, trùng bảo trì hoặc trùng booking.
- Backend tính giá và lưu snapshot; không nhận giá từ frontend.
- Booking hợp lệ được giữ chỗ 15 phút để thanh toán khoản cọc đầu tiên.

### Thanh toán cọc MoMo Sandbox

- Khoản cọc bằng 30% tổng tiền sân, làm tròn đến đồng và lưu snapshot.
- 70% còn lại được hiển thị là thanh toán tại sân; hệ thống không thu hoặc xác nhận phần này trong MVP.
- DIRECT_BOOKING: creator thanh toán toàn bộ khoản cọc.
- FIND_PLAYERS: creator thanh toán toàn bộ khoản cọc; người ghép không có payment/contribution online.
- FIND_OPPONENT: creator và phía đối thủ mỗi bên thanh toán 50% khoản cọc.
- Backend tạo chữ ký, chuyển user đến MoMo Sandbox và nhận IPN.
- Chỉ IPN hợp lệ mới cập nhật payment thành công; redirect không phải bằng chứng.
- Hỗ trợ refund toàn bộ hoặc một phần khoản cọc qua MoMo Sandbox.
- Provider MOCK dùng cho phát triển/test và phải ghi rõ không trừ tiền thật.

### Tìm đối thủ

- Áp dụng cho bóng đá và các booking đánh đơn/đôi của môn dùng vợt.
- Một đại diện gửi yêu cầu; chỉ một phía đối thủ được chấp nhận.
- Đối thủ được chấp nhận có 15 phút để thanh toán phần cọc nhưng không được vượt quá hạn tìm đối thủ.
- Phải tìm được và nhận đủ phần cọc đối thủ trước giờ bắt đầu 12 giờ.
- Nếu không có đối thủ, creator có thêm 30 phút để top-up phần cọc còn thiếu.
- Không top-up đúng hạn: hoàn 80% khoản creator đã cọc, giữ 20% khoản đó làm phí giữ sân.

### Tìm thêm người

- Creator tự chọn số vị trí muốn tìm trong giới hạn hợp lệ của field/hình thức thi đấu.
- Người xin ghép bắt buộc đăng nhập và cung cấp số điện thoại dùng Zalo.
- Creator chấp nhận hoặc từ chối; người được chấp nhận chuyển JOINED ngay, không chờ payment.
- Số điện thoại chỉ hiện cho creator sau khi chấp nhận và không công khai trên danh sách kèo.
- Người ghép thanh toán trực tiếp cho creator tại sân; website chỉ hiển thị phần tiền dự kiến nếu cần.
- MVP không chấm điểm, tự động phạt hoặc khóa vì no-show.

### Admin

- Quản lý tài khoản, owner application và venue.
- Xem booking, contribution, payment, refund và match.
- Không xóa lịch sử giao dịch và không nhìn thấy secret key.

## 2.2. Should Have

- Dashboard owner và thống kê booking cơ bản.
- Upload ảnh venue.
- Lịch sử thay đổi trạng thái.
- Giao diện danh sách/bản đồ responsive.
- Thông báo trong ứng dụng cho deadline cọc và yêu cầu tham gia.

## 2.3. Could Have

- Đánh giá venue.
- Email thông báo.
- Mã giảm giá.
- Thống kê doanh thu nâng cao.
- Lưu danh sách yêu thích.

## 2.4. Ngoài phạm vi đồ án ngành

- MoMo Production và giao dịch tiền thật.
- QR ngân hàng thật của owner.
- Ví/số dư do admin giữ, payout hoặc yêu cầu rút tiền.
- Chuyển tiền trực tiếp giữa tài khoản người dùng.
- Google Routes/traffic, theo dõi vị trí thời gian thực hoặc dữ liệu venue ngoài hệ thống.
- Phân loại mặt sân tennis, thuê dụng cụ, huấn luyện viên và giải đấu.
- Chấm điểm hoặc xử phạt no-show tự động.
- AI lọc spam, phân tích cảm xúc, recommendation hoặc RAG chatbot.
- Chat thời gian thực, mobile application và mạng xã hội thể thao.

## 2.5. Ranh giới triển khai hiện tại

Phạm vi trên đã được triển khai bằng migration, code và test: danh mục đa môn, tọa độ Google Maps, cọc 30%, người ghép trả tại sân và nền tảng MoMo Sandbox. Việc gọi Sandbox thật chỉ được xem là đã xác nhận sau khi cấu hình credential M4B, URL HTTPS công khai và chạy một giao dịch thanh toán/hoàn tiền đầu-cuối; trước đó provider `MOCK` vẫn là mặc định.
