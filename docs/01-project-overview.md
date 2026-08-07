# 1. Tổng quan dự án

## 1.1. Tên đề tài

Xây dựng hệ thống quản lý đặt sân bóng đá tích hợp tìm kèo trực tuyến.

## 1.2. Vấn đề thực tế

Hiện nay nhiều sân bóng vẫn tiếp nhận đặt sân qua điện thoại, tin nhắn hoặc mạng xã hội. Các vấn đề thường gặp:
- Người dùng không biết sân nào còn trống.
- Phải gọi nhiều sân để hỏi giá và thời gian.
- Chủ sân dễ ghi nhận sai hoặc đặt trùng lịch.
- Việc xác nhận và thanh toán chưa được quản lý tập trung.
- Người chơi khó tìm thêm thành viên.
- Các đội bóng khó tìm đối thủ phù hợp.

## 1.3. Giải pháp

Xây dựng một hệ thống trực tuyến cho phép:
- Chủ sân đăng và quản lý sân.
- Người dùng tìm sân theo thông tin phù hợp.
- Người dùng xem lịch trống và đặt sân.
- Hệ thống tự động xác nhận giữ chỗ sau khi kiểm tra hợp lệ; chủ sân theo dõi và chỉ hủy khi có sự cố.
- Người dùng thanh toán qua MoMo Sandbox theo hình thức trả đủ, chia 50/50 với đội đối thủ hoặc chia theo đầu người.
- Hệ thống xử lý nhiều người cùng đóng tiền, hạn thanh toán và hoàn tiền.
- Người dùng tạo kèo tìm người hoặc tìm đối thủ; người tham gia chỉ được xác nhận sau khi hoàn thành phần tiền bắt buộc.

## 1.4. Đối tượng sử dụng

### Người chơi
Có nhu cầu tìm sân, đặt sân hoặc tham gia kèo.

### Chủ sân
Quản lý một hoặc nhiều cơ sở thể thao.

### Quản trị viên
Kiểm soát tài khoản, sân, booking và nội dung hệ thống.

## 1.5. Mục tiêu

- Số hóa quy trình đặt sân.
- Hạn chế tình trạng đặt trùng.
- Quản lý booking tập trung.
- Hỗ trợ chủ sân quản lý hoạt động.
- Hỗ trợ người chơi tìm thành viên hoặc đối thủ.
- Tạo nền tảng phát triển thành khóa luận tốt nghiệp.

## 1.6. Luồng nghiệp vụ chính

```text
Người dùng đăng ký
→ Đăng nhập
→ Tìm sân
→ Xem chi tiết
→ Chọn thời gian
→ Đặt sân
→ Hệ thống giữ chỗ 15 phút
→ Xác nhận hình thức thanh toán
→ Thanh toán đủ hoặc thanh toán phần đầu
→ Tạo kèo nếu cần
→ Đối thủ/người ghép thanh toán phần của mình
→ Booking đủ tiền và diễn ra
```

Trong MVP có ba hình thức thanh toán:
- `FULL_PAYMENT`: người đặt thanh toán 100%.
- `SPLIT_OPPONENT`: hai đội chia 50/50.
- `SPLIT_PLAYERS`: chia theo đầu người; người tạo trả phần nhóm có sẵn và người ghép trả phần của mình.

Phiên bản đồ án chỉ dùng MoMo Sandbox, không giao dịch tiền thật.
