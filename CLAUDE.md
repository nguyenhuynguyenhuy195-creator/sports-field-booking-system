@AGENTS.md
@CURRENT_SPRINT.md

# Sports Field Booking System

## Project
Đây là đồ án ngành về hệ thống đặt sân thể thao đa môn tích hợp tìm kèo.

Công nghệ chính:
- Python Flask
- Flask-SQLAlchemy
- Flask-Migrate
- Microsoft SQL Server
- Jinja2
- HTML/CSS/JavaScript
- Bootstrap 5
- Leaflet
- Nominatim

Không rewrite project sang React, Vue, microservices hoặc framework khác.

## Architecture

Luồng chính:

Browser / Jinja
-> Flask Route
-> Service
-> SQLAlchemy Model
-> SQL Server

Business logic phải nằm trong service.
Route giữ đơn giản.
Không đưa business rule quan trọng vào JavaScript hoặc template.

## Source of truth

Khi thông tin mâu thuẫn, ưu tiên:

1. Yêu cầu mới nhất đã được xác nhận
2. Source code hiện tại
3. Models và migrations
4. Business rules hiện tại
5. ADR mới nhất chưa bị thay thế
6. README/docs
7. Báo cáo
8. Suy luận AI

Không tự bịa:
- chức năng
- bảng/cột database
- business rule
- kết quả test
- trạng thái payment
- API behavior

## Business rules quan trọng

DIRECT_BOOKING:
- creator cọc 30%

FIND_PLAYERS:
- creator cọc 30%
- người tham gia không thanh toán online

FIND_OPPONENT:
- creator cọc 15%
- opponent có thể cọc thêm 15%
- không tìm được opponent thì booking vẫn hợp lệ
- opponent thanh toán thành công thì participant chuyển JOINED

Phần còn lại thanh toán tại sân.

Không thay đổi các rule trên nếu chưa được yêu cầu rõ ràng.

## Payment / Refund

Runtime hiện tại dùng MOCK/SIMULATED.

Code MoMo cũ vẫn tồn tại nhưng đang disabled.

Sprint mới dự kiến bổ sung VNPAY Sandbox.

Khi làm VNPAY:
- tái sử dụng Payment
- tái sử dụng BookingContribution
- tái sử dụng Refund
- không xây lại payment từ đầu
- giữ MOCK làm fallback
- chưa xóa MoMo legacy
- không thay đổi business rule booking/matchmaking

Payment SUCCESS và Refund là hai bản ghi riêng.
Không đổi Payment SUCCESS thành REFUNDED.

## Maps

Hiện tại:
- Leaflet hiển thị bản đồ
- Nominatim geocoding
- Haversine tính khoảng cách
- vị trí hiện tại của user không lưu database

Không tự đổi sang Google Maps API.

## Safety

Không đọc hoặc sửa .env.
Không expose secret.
Không xóa migration cũ.
Không sửa test chỉ để test pass.
Không refactor file không liên quan.

Trước khi sửa code:
1. đọc source liên quan
2. giải thích behavior hiện tại
3. liệt kê file dự kiến sửa
4. chỉ ra rủi ro
5. đưa kế hoạch

Với payment, refund, booking, matchmaking, migration:
phải trình bày kế hoạch trước khi sửa.

## Testing

Sau mỗi task chạy test liên quan.

Trước khi kết luận hoàn thành:

.\.venv\Scripts\python.exe -m pytest

Không được tự bịa số lượng test pass.

## Git

Không commit, push, merge hoặc sửa main nếu chưa được yêu cầu rõ ràng.

## Run project

Migration:

.\.venv\Scripts\python.exe -m flask --app run.py db upgrade

Run:

.\.venv\Scripts\python.exe -m flask --app run.py run

Test:

.\.venv\Scripts\python.exe -m pytest