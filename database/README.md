# Bản sao dữ liệu đã ẩn danh

File `sports_field_booking_sanitized_20260906.sql` là bản backup logic dành cho
demo và nộp đồ án. File giữ nguyên ID, quan hệ, trạng thái, lịch, giá và số tiền,
nhưng đã thay thế thông tin cá nhân, địa chỉ, tọa độ, ghi chú, liên hệ kèo, mã
giao dịch và tên file tải lên.

## Cách phục hồi

1. Tạo database trống tên `sports_field_booking` và cấu hình `.env` trỏ tới đó.
2. Từ repository, chạy migrations:

   ```powershell
   .\.venv\Scripts\python.exe -m flask --app run.py db upgrade
   ```

3. Chạy file dữ liệu bằng SQLCMD:

   ```powershell
   sqlcmd -S localhost -d sports_field_booking -E -b -i "sports_field_booking_sanitized_20260906.sql"
   ```

Script sẽ xóa dữ liệu nghiệp vụ hiện có trong database đích trước khi nhập.
Không chạy trên database đang chứa dữ liệu cần giữ.

Tài khoản sau khi phục hồi có email dạng `user####@example.test`. Mật khẩu dùng
chung cho bản demo là `Demo@123456`; vai trò và trạng thái tài khoản được giữ
nguyên như nguồn.

Metadata ảnh được giữ để bảo toàn quan hệ nhưng file ảnh vật lý không nằm trong
backup CSDL này.
