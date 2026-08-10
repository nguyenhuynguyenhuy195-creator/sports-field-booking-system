# 7. Yêu cầu giao diện

## 7.1. Phong cách và khả dụng

- Hiện đại, thể thao, chuyên nghiệp và dễ sử dụng.
- Responsive trên desktop và mobile.
- Primary `#146C43`, Secondary `#0F2747`, Background `#F5F7FA`.
- Font Be Vietnam Pro hoặc Inter.
- Card bo góc 12–16px; button cao 42–48px.
- Button thanh toán/hủy phải có trạng thái disabled và loading để tránh gửi lặp.
- Mọi lỗi nghiệp vụ, hết hạn và trạng thái MoMo phải được diễn đạt rõ bằng tiếng Việt.

## 7.2. Trang chủ và danh sách sân

Trang chủ gồm navbar, hero, form tìm sân, venue nổi bật, kèo đang mở và footer.

Danh sách sân gồm bộ lọc, card venue, địa chỉ, loại sân, giá tham khảo thấp nhất, phân trang và empty state. Chỉ venue/field `ACTIVE` được hiển thị.

## 7.3. Trang chi tiết venue/field

- Thông tin venue, địa chỉ, giờ hoạt động và danh sách field.
- Loại sân, sức chứa, trạng thái và các khung giá theo ngày.
- Lịch trống và lịch bảo trì không cho chọn.
- Nút đặt sân chỉ bật với field `ACTIVE` và thời gian hợp lệ.

## 7.4. Trang tạo booking

- Thể hiện tiến trình bốn bước: sân đã chọn, chọn giờ, chọn hình thức và xác nhận.
- Chọn nhanh ngày trong dải 7 ngày hoặc bằng ô lịch; dải ngày cuộn ngang trên màn hình nhỏ và luôn đưa ngày đang chọn vào vùng nhìn thấy.
- Hiển thị lưới mốc giờ bước 30 phút từ giờ mở cửa đến giờ đóng cửa của venue.
- Phân biệt trực quan: còn trống, đã chọn, đã có người đặt, bảo trì, chưa áp dụng giá và thời gian đã qua.
- User chọn mốc bắt đầu rồi mốc kết thúc; không cho chọn qua ô bận/bảo trì/thiếu giá và chỉ bật nút tiếp tục khi đủ 60 phút.
- Hiển thị điều kiện tối thiểu 60 phút, giới hạn 30 ngày và thời gian đặt trước.
- Cho chọn một trong ba hình thức:
  - Thanh toán 100%.
  - Tìm đội đối thủ, chia 50/50.
  - Tìm thêm người, chia theo đầu người.
- Với tìm người: nhập số vị trí còn thiếu; hiển thị số người tiêu chuẩn và phần người tạo phải trả.
- Trước khi giữ chỗ, hiển thị riêng khoản người tạo trả trước và khoản chờ đối thủ/người ghép trả.
- Hiển thị từng đoạn khung giá, đơn giá, thời lượng, subtotal và tổng tiền dự kiến.
- Sau khi chọn đủ khoảng giờ, hiển thị ngay khoảng đã chọn, thời lượng và tạm tính từ endpoint báo giá.
- Hiển thị thông tin người đặt lấy từ tài khoản, không yêu cầu nhập lại họ tên/email.
- Nêu rõ booking hợp lệ được giữ chỗ tự động 15 phút, không chờ owner duyệt.
- Backend tính lại toàn bộ khi submit.

## 7.5. Chi tiết và lịch sử booking

Hiển thị:
- Mã booking, venue/field và ngày giờ.
- Hình thức thanh toán.
- Chi tiết giá chốt và `total_amount`.
- Số tiền đã thu, còn thiếu và hạn góp đủ.
- Badge trạng thái và timeline.
- Danh sách contribution/payment/refund mà user được phép xem.
- Bảng contribution hiển thị người/nhóm trả, vị trí, số phải trả, số đã trả và trạng thái; lịch sử payment tách riêng.
- Nút hủy, thanh toán lại hoặc trả phần còn thiếu theo quyền và trạng thái; owner không có nút xác nhận/từ chối booking thông thường.
- Trong giai đoạn provider `MOCK`, giao diện phải ghi rõ “Thanh toán mô phỏng” không trừ tiền thật và chưa gọi MoMo.

## 7.6. Trang thanh toán MoMo

- Hiển thị chính xác booking, người trả, số tiền và thời hạn.
- Nút “Thanh toán qua MoMo Sandbox”.
- Sau redirect, hiển thị “Đang xác minh” cho đến khi backend nhận/xác nhận IPN.
- Không hiển thị thành công chỉ dựa trên query string redirect.
- Cho phép thử lại khi payment thất bại và nghĩa vụ vẫn còn hạn.

## 7.7. Trang tìm kèo

### Danh sách và chi tiết
- Phân biệt `FIND_OPPONENT` và `FIND_PLAYERS`.
- Hiển thị field, ngày giờ, trình độ, số vị trí còn thiếu và tiến độ thanh toán.
- Không công khai secret hoặc thông tin giao dịch nhạy cảm.

### Người tạo
- Xem, chấp nhận hoặc từ chối yêu cầu.
- Thấy countdown 15 phút của yêu cầu đang chờ thanh toán.
- Thấy số tiền còn thiếu và nút trả phần còn lại.

### Người tham gia
- Gửi yêu cầu và xem trạng thái.
- Sau khi được chấp nhận, xem số tiền phải trả và countdown 15 phút.
- Chỉ hiển thị “Đã tham gia” sau payment thành công; nếu người tạo đã trả đủ booking thì hiển thị rõ vị trí không còn phải thanh toán.
- Có nút rút; giao diện phải hiển thị rõ chính sách hoàn tiền trên/dưới mốc 12 giờ.

## 7.8. Dashboard owner

- Venue chờ duyệt/đang hoạt động/bị ẩn.
- Field, khung giá theo ngày và lịch bảo trì.
- Booking hôm nay, booking đang giữ chỗ/chờ thanh toán và countdown 15 phút.
- Tiến độ thanh toán, booking chờ refund và lý do hủy.
- Owner không được sửa giá snapshot của booking đã tạo.

## 7.9. Dashboard admin

- Tài khoản và yêu cầu trở thành owner.
- Venue chờ duyệt và chức năng ẩn venue.
- Danh sách booking, payment, contribution, refund và match.
- Bộ lọc theo trạng thái, ngày và mã giao dịch.
- Không hiển thị secret key MoMo.

## 7.10. Màu trạng thái booking

- `PENDING`: vàng, chỉ dùng cho dữ liệu lịch sử.
- `CONFIRMED`: xanh dương, đang giữ chỗ/chờ thanh toán đầu tiên.
- `PARTIALLY_PAID`: tím hoặc xanh lam nhạt.
- `PAID`: xanh lá.
- `REFUND_PENDING`: cam.
- `COMPLETED`: xám hoặc xanh đậm.
- `CANCELLED`, `REJECTED`: đỏ.
- `EXPIRED`: xám.

## 7.11. Trạng thái rỗng và lỗi bắt buộc

- Không có khung giá phủ đủ thời gian.
- Khung giờ đã có người đặt hoặc đang bảo trì.
- Venue/field chưa hoạt động.
- Booking hoặc yêu cầu thanh toán đã hết hạn.
- Payment đang xác minh, thất bại hoặc đã được xử lý.
- Refund đang xử lý hoặc thất bại.
- Kèo đã đủ người, đã có đối thủ hoặc vị trí vừa được người khác thanh toán.
