# 2. Phạm vi MVP

## 2.1. Must Have

### Tài khoản
- Đăng ký, đăng nhập và đăng xuất.
- Phân quyền `USER`, `OWNER` và `ADMIN` ở backend.
- User gửi yêu cầu trở thành owner; admin chấp nhận hoặc từ chối.
- Admin khóa hoặc mở tài khoản.

### Quản lý cơ sở và sân
- Owner tạo và sửa cơ sở thể thao (venue).
- Venue mới có trạng thái `PENDING` và chỉ hiển thị công khai sau khi admin duyệt thành `ACTIVE`.
- Owner tạo field; field mới mặc định `INACTIVE`.
- Owner cấu hình giá field theo khung giờ và từng ngày trong tuần.
- Owner chỉ bật field thành `ACTIVE` sau khi đã cấu hình đủ thông tin và giá.
- Owner tạo lịch bảo trì theo ngày và khoảng giờ.
- Không cho tạo lịch bảo trì trùng booking đang chiếm chỗ.
- User xem danh sách và chi tiết venue/field đang hoạt động.

### Booking
- User chọn ngày, giờ bắt đầu, giờ kết thúc và hình thức thanh toán.
- Thời gian bắt đầu theo bước 30 phút; thời lượng tối thiểu 60 phút.
- Booking thông thường phải được tạo trước giờ bắt đầu ít nhất 60 phút.
- Booking chia tiền phải được tạo trước giờ bắt đầu ít nhất 13 giờ.
- Chỉ được đặt trước tối đa 30 ngày.
- Hệ thống kiểm tra giờ hoạt động, lịch bảo trì và trùng lịch.
- Backend tính giá theo các khung giờ từ database và lưu chi tiết giá tại thời điểm đặt.
- Owner xác nhận hoặc từ chối booking.
- User xem lịch sử booking và hủy khi hợp lệ.
- Hệ thống xử lý hết hạn booking theo thời hạn đã quy định.

### Thanh toán MoMo Sandbox
- Tích hợp luồng thanh toán MoMo Sandbox, không dùng tiền thật.
- Backend tạo chữ ký, chuyển người dùng đến MoMo và nhận IPN.
- Chỉ IPN hợp lệ sau khi kiểm tra chữ ký và đối chiếu dữ liệu mới được cập nhật thanh toán thành công.
- Cho phép nhiều lần thử thanh toán nhưng không được ghi nhận vượt số tiền booking còn thiếu.
- Hỗ trợ ba hình thức thanh toán:
  - `FULL_PAYMENT`: người đặt thanh toán 100%.
  - `SPLIT_OPPONENT`: đội tạo trả 50%, đội đối thủ trả 50%.
  - `SPLIT_PLAYERS`: người tạo trả phần của nhóm hiện có, người ghép trả theo đầu người.
- Hỗ trợ hoàn toàn bộ và hoàn một phần qua MoMo Sandbox.
- Lưu riêng lịch sử payment, contribution và refund.

### Tìm kèo
- User tạo và xem danh sách kèo.
- Kèo tìm đối thủ nhận yêu cầu từ đại diện đội; chỉ một đội đối thủ được chấp nhận.
- Kèo tìm người nhận yêu cầu theo từng người và giới hạn theo số vị trí còn thiếu.
- Người được chấp nhận có 15 phút để thanh toán; quá hạn thì yêu cầu hết hiệu lực và vị trí được mở lại.
- Người ghép hoặc đội đối thủ chỉ chính thức tham gia sau khi hoàn thành khoản thanh toán bắt buộc.
- Thành viên có sẵn của đội không bắt buộc có tài khoản; người tạo thanh toán phần của nhóm này.
- Người tạo có thể thanh toán phần còn thiếu trước hạn góp tiền.

### Admin
- Xem danh sách tài khoản và yêu cầu trở thành owner.
- Khóa hoặc mở tài khoản.
- Duyệt hoặc ẩn venue.
- Xem booking, payment, refund và kèo.

## 2.2. Should Have

- Tìm kiếm sân theo tên hoặc khu vực.
- Lọc theo loại sân và giá.
- Dashboard owner.
- Thống kê booking cơ bản.
- Lịch sử thay đổi trạng thái booking.
- Upload ảnh sân.

## 2.3. Could Have

- Google Maps.
- Đánh giá sân.
- Email thông báo.
- Mã giảm giá.
- Thống kê doanh thu nâng cao.
- Theo dõi và xử phạt no-show.

## 2.4. Không làm trong phiên bản đồ án ngành

- AI lọc spam.
- Phân tích cảm xúc.
- Mạng xã hội thể thao.
- Chat thời gian thực.
- Mobile application.
- Recommendation system.
- Thanh toán MoMo Production bằng tiền thật.
- Chuyển tiền trực tiếp giữa các tài khoản người dùng.
