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
- User tìm cơ sở theo từ khóa, bộ môn, loại sân, giá và địa chỉ hành chính.
- Owner chọn tỉnh/thành phố, phường/xã và nhập địa chỉ chi tiết; user có thể mở Google Maps để chỉ đường.
- User xem lịch trống, đặt sân và chọn hình thức thi đấu phù hợp.
- Hệ thống tự kiểm tra trùng lịch, bảo trì, độ phủ giá và giữ chỗ 15 phút.
- User thanh toán khoản cọc đầu tiên qua MoMo Sandbox; số còn lại thanh toán tại sân.
- User mở kèo tìm đối thủ hoặc tìm thêm người cho booking.
- Với FIND_OPPONENT, cọc 15% của creator đã đủ giữ sân; đối thủ bấm nhận kèo, giữ suất 15 phút và trả thêm 15% để tự động tham gia, không cần creator duyệt. Bài tìm đối thủ tồn tại đến giờ bắt đầu.
- Không tìm được đối thủ không làm hủy booking; creator vẫn sử dụng sân và trả 85% còn lại tại sân.
- Người ghép không cọc, để lại số Zalo và trả tiền tại sân.
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
- Quản lý booking, tiền cọc và các trường hợp hoàn tiền ngoại lệ tập trung.
- Hỗ trợ người dùng tìm sân gần vị trí hiện tại.
- Hỗ trợ tìm đối thủ hoặc thành viên cho nhiều bộ môn.
- Giữ phạm vi đủ rõ để hoàn thành đồ án và mở rộng thành khóa luận.

## 1.6. Bộ môn và hình thức thi đấu

| Bộ môn | Loại sân MVP | Cấu hình đặt sân |
|---|---|---|
| Bóng đá | 5 người, 7 người, 11 người | Loại sân xác định số người thi đấu chính |
| Cầu lông | Sân tiêu chuẩn | Chọn một trong ba booking mode |
| Pickleball | Sân tiêu chuẩn | Chọn một trong ba booking mode |
| Tennis | Sân tiêu chuẩn | Chọn một trong ba booking mode |

MVP hiện tại không yêu cầu người dùng khai báo đánh đơn/đôi. Cột `play_format` nullable chỉ được giữ để đọc dữ liệu legacy; booking mới luôn lưu `NULL`. Các loại mặt sân tennis, cho thuê dụng cụ và luật thi đấu riêng không thuộc MVP.

## 1.7. Luồng nghiệp vụ chính

> Đăng nhập → tìm cơ sở → chọn sân con → chọn thời gian → chọn đặt cho nhóm, tìm đối thủ hoặc tìm thêm người → hệ thống giữ chỗ 15 phút → thanh toán cọc qua MoMo Sandbox → diễn ra hoạt động → thanh toán phần còn lại tại sân.

Ba hình thức booking:

- DIRECT_BOOKING: người tạo trả toàn bộ khoản cọc 30%.
- FIND_OPPONENT: người tạo trả 15% tổng tiền sân để giữ booking; phía đối thủ tự giữ suất khi bấm nhận kèo và trả thêm 15% để tham gia ngay. Bài tìm đối thủ mở đến giờ bắt đầu và không có đối thủ không làm mất booking.
- FIND_PLAYERS: người tạo trả toàn bộ khoản cọc 30%; người xin ghép không thanh toán online.

Số còn lại tại sân được tính từ tiền cọc thực thu: 85% với FIND_OPPONENT chỉ có cọc creator và 70% khi cả creator lẫn đối thủ đã cọc. Người chủ động hủy/rút hoặc no-show mất phần cọc của mình; chủ sân hủy hoặc lỗi hệ thống phải hoàn 100% cho bên không có lỗi.

MoMo Sandbox chỉ mô phỏng tích hợp, không giao dịch tiền thật. Provider MOCK tiếp tục dùng cho phát triển và kiểm thử tự động. MoMo Production, QR ngân hàng thật, ví admin và chức năng owner rút tiền nằm ngoài phạm vi.

## 1.8. Trạng thái triển khai

Thiết kế ngày 12/08/2026 đã được triển khai tuần tự bằng bốn migration: danh mục đa môn và dữ liệu vị trí legacy; chính sách cọc 30%; URL checkout MoMo; snapshot liên hệ riêng của người đăng kèo. Theo ADR-032, luồng hiện tại chỉ dùng địa chỉ hành chính và liên kết Google Maps, không tải Maps/Places API; cột Place ID/tọa độ cũ được giữ để tương thích. ADR-027 và ADR-028 được triển khai ở service/UI/test: booking mới bỏ deadline cũ và đối thủ tự giữ suất thanh toán, còn booking legacy có deadline vẫn giữ luồng duyệt cũ. ADR-029 bổ sung số Zalo có sự đồng ý, chỉ hiển thị sau khi tham gia chính thức và đưa kèo đã tham gia vào lịch cá nhân ở chế độ chỉ xem. Provider `MOCK` là mặc định an toàn; giao dịch MoMo Sandbox đầu-cuối cần credential M4B và URL HTTPS công khai của môi trường chạy.
