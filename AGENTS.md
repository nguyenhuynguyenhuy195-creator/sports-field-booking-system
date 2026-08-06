# AGENTS.md

## 1. Thông tin dự án

**Tên dự án:** Hệ thống quản lý đặt sân bóng đá tích hợp tìm kèo trực tuyến.

**Mục tiêu:** Xây dựng website giúp chủ sân đăng và quản lý sân; người dùng tìm sân, đặt sân, thanh toán MoMo Sandbox và tạo kèo tìm người chơi hoặc tìm đội đối thủ. Hệ thống hỗ trợ trả đủ, chia 50/50 với đội đối thủ và chia tiền theo đầu người. Dự án là đồ án ngành và có thể phát triển tiếp thành khóa luận tốt nghiệp.

## 2. Công nghệ bắt buộc

### Backend
- Python
- Flask
- Flask-SQLAlchemy
- Flask-Migrate
- Flask-Login
- Flask-WTF

### Frontend
- HTML
- CSS
- Bootstrap 5
- Jinja2
- JavaScript thuần khi cần thiết

### Database
- Microsoft SQL Server
- SQLAlchemy ORM
- pyodbc

### Thanh toán
- MoMo Sandbox API
- HMAC SHA-256
- IPN server-to-server
- Payment/refund idempotency

### Testing
- pytest
- pytest-flask

Không tự ý chuyển sang React, Vue, Angular, Tailwind, Flutter Web hoặc framework khác.

## 3. Vai trò trong hệ thống

### USER
- Đăng ký, đăng nhập và đăng xuất.
- Xem danh sách và chi tiết sân.
- Tạo, xem và hủy booking của mình khi hợp lệ.
- Chọn hình thức thanh toán và thanh toán phần của mình qua MoMo Sandbox.
- Tạo kèo, gửi yêu cầu tham gia kèo và thanh toán để xác nhận tham gia khi bắt buộc.
- Gửi yêu cầu trở thành OWNER.

### OWNER
- Quản lý cơ sở thể thao thuộc sở hữu của mình.
- Quản lý các sân con.
- Xem booking thuộc sân của mình.
- Xác nhận hoặc từ chối booking.
- Hủy booking khi có sự cố, bắt buộc lưu lý do và xử lý hoàn tiền nếu đã thu tiền.
- Xem lịch hoạt động của sân.
- Quản lý khung giá theo ngày trong tuần và lịch bảo trì.

### ADMIN
- Quản lý người dùng và chủ sân.
- Duyệt hoặc từ chối yêu cầu trở thành OWNER.
- Duyệt hoặc ẩn cơ sở thể thao.
- Xem booking, contribution, payment, refund và bài tìm kèo.

## 4. Kiến trúc bắt buộc

Dự án được chia thành:
- `models`: ánh xạ dữ liệu.
- `forms`: form và validation.
- `routes`: tiếp nhận HTTP request và trả response.
- `services`: xử lý nghiệp vụ.
- `integrations`: client tích hợp MoMo và dịch vụ ngoài.
- `cli`: tác vụ định kỳ hết hạn, hoàn tất booking và query giao dịch.
- `templates`: giao diện Jinja2.
- `static`: CSS, JavaScript và hình ảnh.
- `tests`: unit test và integration test.

Không đặt toàn bộ nghiệp vụ trực tiếp trong route.

Route chỉ nên:
1. Nhận request.
2. Kiểm tra authentication.
3. Kiểm tra form cơ bản.
4. Gọi service.
5. Trả response.

Service chịu trách nhiệm:
- Kiểm tra quy tắc nghiệp vụ.
- Tính giá.
- Kiểm tra trùng lịch.
- Thay đổi trạng thái.
- Xử lý transaction.
- Phân bổ nghĩa vụ đóng tiền.
- Xử lý IPN, idempotency và refund.

## 5. Quy tắc code

- Python dùng `snake_case` cho biến và hàm.
- Class dùng `PascalCase`.
- Tên bảng SQL dùng `snake_case` và số nhiều.
- Không hard-code mật khẩu, API key hoặc connection string.
- Không đưa file `.env` lên Git.
- Không sửa file không liên quan đến nhiệm vụ.
- Không tự ý thêm chức năng ngoài phạm vi MVP.
- Không tạo một file `app.py` quá lớn.
- Không tin dữ liệu giá tiền gửi từ frontend.
- Không tin kết quả thanh toán từ redirect; chỉ xác nhận qua IPN hợp lệ.
- Không log hoặc commit MoMo secret key.
- Backend luôn kiểm tra quyền truy cập.
- Phải rollback database nếu commit thất bại.
- Mỗi nhiệm vụ chỉ xử lý một chức năng nhỏ.
- Phải giải thích những file đã thay đổi.

## 6. Quy tắc SQL Server

- Sử dụng Flask-SQLAlchemy để truy cập dữ liệu.
- Sử dụng Flask-Migrate để quản lý schema.
- Không chạy `DROP DATABASE`.
- Không xóa bảng nếu chưa được yêu cầu rõ ràng.
- Không xóa migration cũ.
- Không reset database khi chưa được cho phép.
- Trước khi chạy migration phải mô tả thay đổi.
- Chi tiết giá tại thời điểm đặt phải được lưu thành snapshot của booking.
- Primary key, foreign key và unique constraint phải được khai báo rõ.

## 7. Quy tắc kiểm tra trùng lịch

Hai khoảng thời gian bị trùng khi:

```text
new_start < existing_end
AND
new_end > existing_start
```

Các trạng thái booking chiếm chỗ:
- `PENDING`
- `CONFIRMED`
- `PARTIALLY_PAID`
- `PAID`
- `REFUND_PENDING`

Các trạng thái không chiếm chỗ:
- `REJECTED`
- `CANCELLED`
- `EXPIRED`
- `COMPLETED`

## 7.1. Quy tắc thanh toán và chia tiền

- `FULL_PAYMENT`: người tạo trả 100%.
- `SPLIT_OPPONENT`: người tạo trả 50%, đội đối thủ trả 50%.
- `SPLIT_PLAYERS`: người tạo trả phần nhóm hiện có, người ghép trả theo đầu người.
- Booking chia tiền phải tạo trước ít nhất 13 giờ và đủ tiền trước giờ bắt đầu 12 giờ.
- Người được chấp nhận có 15 phút để thanh toán.
- Tổng payment thành công sau refund không được vượt `total_amount`.
- Payment gốc không bị xóa hoặc ghi đè khi refund; refund phải có lịch sử riêng.
- Mọi callback/IPN và retry phải idempotent.

## 8. Quy trình bắt buộc trước khi sửa code

Trước khi viết hoặc sửa code, phải:
1. Đọc các tài liệu liên quan trong thư mục `docs`.
2. Tóm tắt yêu cầu.
3. Liệt kê quy tắc nghiệp vụ.
4. Liệt kê trường hợp biên.
5. Liệt kê những file dự kiến thay đổi.
6. Nêu migration cần tạo nếu schema thay đổi.
7. Chờ xác nhận nếu có thay đổi kiến trúc hoặc database lớn.

## 9. Quy trình sau khi sửa code

Sau khi sửa code, phải:
1. Chạy test liên quan.
2. Báo kết quả test.
3. Liệt kê file đã thay đổi.
4. Giải thích luồng dữ liệu.
5. Giải thích truy vấn database.
6. Nêu rủi ro còn tồn tại.
7. Không tự commit nếu chưa được yêu cầu.

## 10. Definition of Done

Một chức năng chỉ được coi là hoàn thành khi:
- Đúng yêu cầu nghiệp vụ.
- Có validation.
- Có kiểm tra authentication.
- Có kiểm tra authorization.
- Có xử lý lỗi database.
- Có test cho trường hợp chính.
- Có test cho trường hợp thất bại quan trọng.
- Không làm hỏng chức năng cũ.
- Giao diện có thông báo lỗi rõ ràng.
- Tài liệu được cập nhật nếu yêu cầu thay đổi.
