# 7. Yêu cầu giao diện

## 7.1. Phong cách và khả dụng

- Hiện đại, thể thao, chuyên nghiệp và dễ dùng.
- Responsive trên desktop/mobile.
- Primary #146C43, Secondary #0F2747, Background #F5F7FA.
- Font Be Vietnam Pro hoặc Inter.
- Card bo góc 12–16px; button cao 42–48px.
- Button thanh toán/hủy có disabled/loading để tránh gửi lặp.
- Lỗi nghiệp vụ, deadline, vị trí và trạng thái MoMo được diễn đạt rõ bằng tiếng Việt.
- Giao diện phân biệt rõ “Tổng tiền sân”, “Cọc online 30%” và “Còn lại trả tại sân”.

## 7.2. Trang chủ và danh sách venue

- Ô tìm theo tên, địa chỉ, quận/huyện hoặc tỉnh/thành phố.
- Bộ lọc sport, field type và khoảng giá.
- Nút “Dùng vị trí của tôi” và bán kính 3/5/10 km.
- Nếu browser từ chối vị trí, hiển thị hướng dẫn ngắn và giữ tìm kiếm văn bản hoạt động.
- Hai chế độ xem: danh sách và bản đồ; mobile ưu tiên danh sách và cho mở bản đồ riêng.
- Card venue hiển thị địa chỉ, sport/field type đang hoạt động, giờ hoạt động, giá từ và khoảng cách nếu có.
- Marker hiển thị tên, khoảng cách, giá từ và nút xem chi tiết.
- Điều kiện đang lọc hiển thị thành chip; phân trang giữ nguyên query.
- Chỉ venue ACTIVE có field ACTIVE xuất hiện.

## 7.3. Form owner tạo/sửa venue

- Nhập tên, số liên hệ, mô tả và giờ hoạt động.
- Ô địa chỉ dùng Places Autocomplete.
- Sau khi chọn gợi ý, hiển thị bản đồ và marker để owner kiểm tra.
- Lưu place ID, địa chỉ chuẩn hóa và tọa độ trong hidden fields nhưng backend vẫn validate.
- Nếu owner sửa chữ trong địa chỉ sau khi chọn place, yêu cầu chọn/xác nhận lại vị trí.
- Không hiển thị API key server hoặc chi tiết billing.

Venue cũ chưa có tọa độ phải có cảnh báo riêng: vẫn hoạt động theo tìm kiếm văn bản nhưng chưa xuất hiện trong “gần tôi”.

## 7.4. Trang chi tiết venue/field

- Hiển thị venue, địa chỉ, giờ hoạt động và các field theo từng sport.
- Bản đồ có marker và nút “Mở chỉ đường trên Google Maps”.
- Field hiển thị sport, field type, capacity, trạng thái và khung giá.
- Nút đặt sân chỉ bật với field ACTIVE.
- Không hiển thị đánh giá Google hoặc cơ sở bên ngoài trong MVP.

## 7.5. Trang tạo booking

Tiến trình bốn bước:

1. Sân đã chọn.
2. Chọn ngày/giờ.
3. Chọn hình thức.
4. Xác nhận và thanh toán cọc.

Yêu cầu:

- Dải ngày 7 ngày và lưới mốc 30 phút theo giờ hoạt động.
- Phân biệt còn trống, đã chọn, đã đặt, bảo trì, thiếu giá và đã qua.
- Chọn khoảng liên tục tối thiểu 60 phút.
- Với cầu lông, pickleball và tennis: chọn Đánh đơn hoặc Đánh đôi.
- Với bóng đá: không hiển thị lựa chọn đơn/đôi.
- Ba booking mode:
  - Đặt sân cho nhóm của tôi.
  - Tìm đối thủ.
  - Tìm thêm người chơi.
- SINGLES không hiển thị FIND_PLAYERS.
- FIND_PLAYERS hiển thị ô số vị trí muốn tìm và giải thích người ghép trả tại sân.
- Số vị trí FIND_PLAYERS được lưu cùng booking trước khi creator thanh toán cọc/mở match.
- FIND_OPPONENT ghi rõ phải đặt trước 24 giờ, tìm xong trước 12 giờ và hai phía chia đôi tiền cọc.
- Trước submit hiển thị các đoạn giá, total, cọc 30%, creator cần trả ngay và 70% trả tại sân.
- Nêu rõ booking giữ chỗ 15 phút và không chờ owner duyệt.
- Backend tính lại khi submit.

## 7.6. Chi tiết và lịch sử booking

Hiển thị:

- Mã booking, venue/field, sport, field type, play format và ngày giờ.
- Booking mode.
- Snapshot giá và total_amount.
- Deposit rate/amount, đã cọc, còn thiếu cọc và balance trả tại sân.
- Badge phải dùng “Đã thanh toán cọc”, không gây hiểu nhầm đã thanh toán toàn bộ.
- Booking `LEGACY_FULL_ONLINE` phải có nhãn “Thanh toán online theo chính sách cũ”, không dùng nhãn cọc 30%.
- Timeline và deadline 15 phút/12 giờ/30 phút khi áp dụng.
- Contribution/payment/refund mà user được phép xem.
- Nút thanh toán lại, top-up hoặc hủy theo quyền/trạng thái.
- Owner không có nút duyệt booking thông thường.
- Provider MOCK phải ghi “Thanh toán mô phỏng, không trừ tiền thật”.

## 7.7. Trang thanh toán MoMo

- Hiển thị đúng booking, người trả, contribution và số tiền cọc.
- Nút “Thanh toán qua MoMo Sandbox”.
- Sau redirect hiển thị “Đang xác minh” cho đến khi IPN hợp lệ.
- Không hiển thị thành công chỉ dựa trên query string.
- Cho thử lại khi payment thất bại và nghĩa vụ còn hạn.
- Không hiển thị QR ngân hàng owner, ví admin hoặc chức năng rút tiền.

## 7.8. Trang tìm kèo

### Danh sách và chi tiết

- Phân biệt Tìm đối thủ và Tìm thêm người.
- Hiển thị sport, play format, field, ngày giờ, trình độ và số vị trí.
- Không công khai số điện thoại participant.

### Creator – FIND_OPPONENT

- Xem/chấp nhận/từ chối yêu cầu.
- Xem countdown 15 phút và deadline trước trận 12 giờ.
- Xem phần cọc đối thủ còn thiếu và nút creator top-up trong cửa sổ 30 phút.

### Creator – FIND_PLAYERS

- Xem số vị trí còn thiếu.
- Chấp nhận/từ chối không phụ thuộc payment.
- Chỉ sau khi chấp nhận mới thấy số điện thoại và nút liên hệ qua Zalo.
- Giao diện ghi rõ tiền được thu trực tiếp tại sân.

### Người tham gia

- Form FIND_PLAYERS bắt buộc số điện thoại dùng Zalo và checkbox đồng ý chia sẻ với creator nếu được chấp nhận.
- Trước khi được chấp nhận, hiển thị trạng thái chờ duyệt nhưng không hiển thị số cho bên khác.
- Sau khi được chấp nhận, hiển thị “Đã tham gia – thanh toán tại sân”, không có nút MoMo/countdown.
- Cho phép rút; vị trí mở lại và không có refund vì chưa thanh toán online.

## 7.9. Dashboard owner

- Venue chờ duyệt/đang hoạt động/bị ẩn và cảnh báo thiếu tọa độ.
- Field nhóm theo sport, khung giá và bảo trì.
- Booking hôm nay, đang giữ chỗ/chờ cọc/chờ đối thủ.
- Tiền cọc, phần dự kiến trả tại sân, refund và lý do hủy.
- Owner không được sửa snapshot booking.

## 7.10. Dashboard admin

- Account, owner application và venue chờ duyệt.
- Kiểm tra địa chỉ/marker trước khi kích hoạt venue mới.
- Danh sách booking, contribution, payment, refund và match.
- Bộ lọc theo trạng thái, sport, ngày và mã giao dịch.
- Không hiển thị secret key; số liên hệ chỉ hiện theo quyền cần thiết.

## 7.11. Màu trạng thái

- CONFIRMED: xanh dương, đang giữ chỗ/chờ cọc đầu tiên.
- PARTIALLY_PAID: tím, đã cọc một phần.
- PAID: xanh lá với nhãn “Đã thanh toán cọc”.
- REFUND_PENDING: cam.
- COMPLETED: xanh đậm hoặc xám.
- CANCELLED/REJECTED: đỏ.
- EXPIRED: xám.
- PENDING chỉ dùng dữ liệu lịch sử.

## 7.12. Empty state và lỗi bắt buộc

- Không có venue theo bộ lọc hoặc bán kính.
- Không cấp quyền vị trí hoặc venue chưa có tọa độ.
- Field/venue chưa hoạt động.
- Play format không hợp lệ với sport/booking mode.
- Khung giờ bận, bảo trì, thiếu giá hoặc quá hạn.
- Payment đang xác minh, thất bại hoặc đã xử lý.
- Refund đang xử lý/thất bại.
- Kèo đủ người/đã có đối thủ.
- Yêu cầu FIND_PLAYERS thiếu số Zalo.
- User không có quyền xem số liên hệ.
