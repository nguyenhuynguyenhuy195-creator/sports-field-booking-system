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
- Owner chọn tỉnh/thành phố, phường/xã và nhập địa chỉ chi tiết.
- Dữ liệu Place ID/tọa độ cũ được giữ để tương thích nhưng không bắt buộc trong luồng mới.
- Owner tạo field; field mới mặc định INACTIVE.
- Owner cấu hình giá theo field, ngày trong tuần và khoảng giờ.
- Owner tạo lịch bảo trì; không cho bảo trì trùng booking đang chiếm chỗ.
- Chỉ field ACTIVE thuộc venue ACTIVE mới được đặt.

### Tìm kiếm và chỉ đường

- Tìm theo tên, địa chỉ chi tiết, phường/xã/đặc khu hoặc tỉnh/thành phố.
- Lọc theo bộ môn, loại sân và khoảng giá.
- Hiển thị nút mở Google Maps để chỉ đường theo địa chỉ đầy đủ hiện tại.
- Không nhúng bản đồ, không yêu cầu quyền vị trí và không dùng Google Maps/Places API.
- Không đưa cơ sở ngoài hệ thống vào kết quả.

### Booking

- User chọn ngày, giờ bắt đầu và kết thúc theo bước 30 phút; tối thiểu 60 phút.
- Không hỏi hoặc yêu cầu hình thức đánh đơn/đôi ở bất kỳ bộ môn nào; booking mới lưu `play_format = NULL`.
- User chọn DIRECT_BOOKING, FIND_OPPONENT hoặc FIND_PLAYERS.
- DIRECT_BOOKING, FIND_PLAYERS và FIND_OPPONENT đều phải đặt trước tối thiểu 60 phút.
- Không đặt quá 30 ngày, ngoài giờ mở cửa, trùng bảo trì hoặc trùng booking.
- Backend tính giá và lưu snapshot; không nhận giá từ frontend.
- Booking hợp lệ được giữ chỗ 15 phút để thanh toán khoản cọc đầu tiên.

### Thanh toán cọc MoMo Sandbox

- Khoản cọc bằng 30% tổng tiền sân, làm tròn đến đồng và lưu snapshot.
- Số còn lại tại sân bằng tổng tiền trừ cọc online thực thu; hệ thống không thu hoặc xác nhận phần này trong MVP.
- DIRECT_BOOKING: creator thanh toán toàn bộ khoản cọc.
- FIND_PLAYERS: creator thanh toán toàn bộ khoản cọc; người ghép không có payment/contribution online.
- FIND_OPPONENT: creator thanh toán 50% khoản cọc dự kiến, tương đương 15% tổng tiền sân, và khoản này đã đủ giữ booking; phía đối thủ bấm nhận kèo và thanh toán 15% còn lại để tự động tham gia.
- Backend tạo chữ ký, chuyển user đến MoMo Sandbox và nhận IPN.
- Chỉ IPN hợp lệ mới cập nhật payment thành công; redirect không phải bằng chứng.
- Hỗ trợ refund qua MoMo Sandbox cho trường hợp chủ sân hủy, lỗi/thu trùng phía hệ thống hoặc hoàn lại cho bên không chủ động gây hủy.
- Provider MOCK dùng cho phát triển/test và phải ghi rõ không trừ tiền thật.

### Tìm đối thủ

- Áp dụng cho mọi field thuộc bộ môn đang được MVP hỗ trợ.
- Một đại diện bấm nhận kèo; hệ thống khóa để chỉ một phía đối thủ được giữ suất thanh toán tại một thời điểm.
- Bài tìm đối thủ tồn tại đến giờ trận bắt đầu, trừ khi creator chủ động đóng hoặc đã có đối thủ thanh toán thành công.
- Đối thủ tự chuyển `ACCEPTED_AWAITING_PAYMENT`, có tối đa 15 phút thanh toán nhưng payment_due_at không được vượt giờ trận bắt đầu; không có bước creator duyệt.
- Đến giờ bắt đầu, các suất `ACCEPTED_AWAITING_PAYMENT` chưa trả hết hiệu lực và bài không còn xuất hiện trong danh sách đang mở.
- Không tìm được đối thủ không làm hủy booking; creator vẫn giữ sân và trả 85% còn lại tại sân.
- Không có top-up bắt buộc và không có refund 80/20 do thiếu đối thủ.
- Đại diện đối thủ chủ động rút/no-show mất phần cọc đã đóng; khoản này tiếp tục được tính vào booking và người thay thế không bị thu cọc lần hai.
- Người đăng và đại diện đối thủ bắt buộc cung cấp số Zalo, đồng ý chia sẻ; hai bên chỉ thấy số của nhau sau khi tiền cọc đối thủ thành công và participant chuyển `JOINED`.
- Kèo đã nhận thành công xuất hiện trong lịch cá nhân của đại diện đối thủ ở chế độ chỉ xem; quyền sửa/hủy booking vẫn thuộc người đặt sân.

### Tìm thêm người

- Creator tự chọn số vị trí muốn tìm trong giới hạn hợp lệ của field/hình thức thi đấu.
- Người đăng và người xin ghép bắt buộc đăng nhập, cung cấp số điện thoại dùng Zalo và đồng ý chia sẻ trong phạm vi kèo.
- Creator chấp nhận hoặc từ chối; người được chấp nhận chuyển JOINED ngay, không chờ payment.
- Số điện thoại chỉ hiện cho creator sau khi chấp nhận và không công khai trên danh sách kèo.
- Người ghép thanh toán trực tiếp cho creator tại sân; website chỉ hiển thị phần tiền dự kiến nếu cần.
- MVP không chấm điểm, tự động phạt hoặc khóa vì no-show.

### Hủy booking và hoàn tiền

- Người đặt chủ động hủy hoặc no-show mất toàn bộ phần cọc của mình.
- Nếu creator hủy sau khi đối thủ đã cọc, creator mất cọc nhưng đối thủ được hoàn 100% vì không phải bên chủ động hủy.
- Chủ sân hủy hoặc hệ thống thu trùng/sai phải hoàn 100% khoản bị ảnh hưởng.
- Người ghép FIND_PLAYERS không cọc online nên rút không phát sinh refund.

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

Danh mục đa môn, địa chỉ hành chính, liên kết chỉ đường Google Maps, cọc 30%, người ghép trả tại sân, nền tảng MoMo Sandbox và khu quản trị Admin đã có code/test. Admin có dashboard, khóa/mở tài khoản và màn hình chỉ xem để giám sát danh mục, booking, contribution, payment, refund và match; lịch sử giao dịch không có thao tác xóa. Maps/Places API, bản đồ nhúng và tìm theo bán kính đã được bỏ theo ADR-032; dữ liệu Place ID/tọa độ cũ vẫn được giữ. ADR-027 và ADR-028 đã được triển khai ở service/UI/test; deadline, top-up, refund 80/20 và bước duyệt đối thủ chỉ còn phục vụ dữ liệu legacy có deadline. Việc gọi Sandbox thật chỉ được xem là đã xác nhận sau khi cấu hình credential M4B, URL HTTPS công khai và chạy một giao dịch thanh toán/hoàn tiền đầu-cuối; trước đó provider `MOCK` vẫn là mặc định.
