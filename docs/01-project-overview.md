# 1. Tổng quan dự án

## 1.1. Tên đề tài

Xây dựng hệ thống quản lý đặt sân thể thao đa môn tích hợp tìm kèo trực tuyến.

## 1.2. Vấn đề thực tế

Nhiều cơ sở thể thao vẫn tiếp nhận đặt sân qua điện thoại, tin nhắn hoặc mạng xã hội. Các vấn đề thường gặp:

- Người dùng không biết sân nào còn trống hoặc phù hợp với bộ môn cần chơi.
- Phải liên hệ nhiều cơ sở để hỏi giá, vị trí và thời gian.
- Chủ sân dễ ghi nhận sai hoặc đặt trùng lịch.
- Việc xác nhận đặt sân, thu cọc và hoàn cọc chưa được quản lý tập trung.
- Người chơi khó tìm đối thủ hoặc tìm thêm người cho lịch đã đặt.
- Địa chỉ dạng văn bản chưa giúp người dùng đánh giá khoảng cách từ vị trí hiện tại.

## 1.3. Giải pháp

Hệ thống trực tuyến cho phép:

- Owner đăng và quản lý cơ sở thể thao cùng các sân con.
- Mỗi sân con thuộc đúng một bộ môn; một cơ sở có thể phục vụ nhiều bộ môn.
- MVP hỗ trợ bóng đá, cầu lông, pickleball và tennis.
- User tìm cơ sở theo từ khóa, bộ môn, loại sân, giá hoặc bán kính quanh vị trí hiện tại.
- Owner chọn địa chỉ bằng Google Places; user xem ghim bản đồ và mở Google Maps để chỉ đường.
- User xem lịch trống, đặt sân và chọn hình thức thi đấu phù hợp.
- Hệ thống tự kiểm tra trùng lịch, bảo trì, độ phủ giá và giữ chỗ 15 phút.
- User thanh toán khoản cọc 30% qua MoMo Sandbox; 70% còn lại thanh toán tại sân.
- User mở kèo tìm đối thủ hoặc tìm thêm người cho booking.
- Đối thủ phải hoàn thành phần cọc cam kết; người ghép không cọc, để lại số Zalo và trả tiền tại sân.
- Hệ thống lưu payment/refund Sandbox riêng biệt và xử lý idempotent.

## 1.4. Đối tượng sử dụng

### Người chơi

Tìm và đặt sân, tạo kèo, tìm đối thủ hoặc xin ghép vào lịch đã có.

### Chủ sân

Quản lý một hoặc nhiều cơ sở, sân con, khung giá, bảo trì và booking.

### Quản trị viên

Duyệt owner/venue, giám sát tài khoản, booking, payment, refund và nội dung kèo.

## 1.5. Mục tiêu

- Số hóa quy trình đặt sân thể thao.
- Hạn chế đặt trùng và sai giá.
- Quản lý booking và tiền cọc tập trung.
- Hỗ trợ người dùng tìm sân gần vị trí hiện tại.
- Hỗ trợ tìm đối thủ hoặc thành viên cho nhiều bộ môn.
- Giữ phạm vi đủ rõ để hoàn thành đồ án và mở rộng thành khóa luận.

## 1.6. Bộ môn và hình thức thi đấu

| Bộ môn | Loại sân MVP | Hình thức thi đấu |
|---|---|---|
| Bóng đá | 5 người, 7 người, 11 người | Loại sân xác định số người thi đấu chính |
| Cầu lông | Sân tiêu chuẩn | Đánh đơn hoặc đánh đôi |
| Pickleball | Sân tiêu chuẩn | Đánh đơn hoặc đánh đôi |
| Tennis | Sân tiêu chuẩn | Đánh đơn hoặc đánh đôi |

Đánh đơn/đôi là thuộc tính của booking, không phải một loại sân. Các loại mặt sân tennis, cho thuê dụng cụ và luật thi đấu riêng không thuộc MVP.

## 1.7. Luồng nghiệp vụ chính

> Đăng nhập → tìm cơ sở → chọn sân con → chọn thời gian và hình thức thi đấu → chọn đặt cho nhóm, tìm đối thủ hoặc tìm thêm người → hệ thống giữ chỗ 15 phút → thanh toán cọc qua MoMo Sandbox → diễn ra hoạt động → thanh toán phần còn lại tại sân.

Ba hình thức booking:

- DIRECT_BOOKING: người tạo trả toàn bộ khoản cọc 30%.
- FIND_OPPONENT: người tạo và phía đối thủ mỗi bên trả một nửa khoản cọc, tương đương 15% tổng tiền sân.
- FIND_PLAYERS: người tạo trả toàn bộ khoản cọc 30%; người xin ghép không thanh toán online.

MoMo Sandbox chỉ mô phỏng tích hợp, không giao dịch tiền thật. Provider MOCK tiếp tục dùng cho phát triển và kiểm thử tự động. MoMo Production, QR ngân hàng thật, ví admin và chức năng owner rút tiền nằm ngoài phạm vi.

## 1.8. Trạng thái triển khai

Thiết kế ngày 12/08/2026 đã được triển khai tuần tự bằng ba migration: danh mục đa môn và vị trí Google Maps; chính sách cọc 30%; URL checkout MoMo. Code hiện hỗ trợ cả dữ liệu mới và booking lịch sử `LEGACY_FULL_ONLINE`. Provider `MOCK` vẫn là mặc định an toàn; giao dịch MoMo Sandbox đầu-cuối cần credential M4B và URL HTTPS công khai của môi trường chạy.
