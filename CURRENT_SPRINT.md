# Current Capstone Sprint

## Tình trạng hiện tại

Đây là giai đoạn hoàn thiện cuối của đồ án ngành.

Hệ thống hiện tại đã có:
- Flask backend
- SQL Server database
- User / Owner / Admin
- Quản lý cơ sở và sân
- Giá và bảo trì
- Đặt sân
- Tìm kèo
- Payment/Refund foundation
- Thanh toán MOCK
- Leaflet + Nominatim
- Tìm sân gần tôi bằng Haversine
- Automated tests

Runtime payment hiện tại là MOCK/SIMULATED.

Code MoMo cũ vẫn còn nhưng đang disabled.

Sau buổi demo gần nhất, có đề xuất bổ sung thêm:

1. VNPAY Sandbox
2. Chat giữa những người chơi trong cùng kèo
3. Chatbot hỗ trợ người dùng

Các chức năng trên hiện CHƯA được xem là hoàn thành.

---

# Priority 1 - VNPAY Sandbox

Mục tiêu:
Tích hợp VNPAY Sandbox vào payment foundation hiện tại.

Yêu cầu:
- Giữ MOCK làm fallback
- Không xây lại payment system từ đầu
- Tái sử dụng Payment
- Tái sử dụng BookingContribution
- Tái sử dụng Refund
- Không thay đổi business rule booking
- Không thay đổi business rule matchmaking
- Chưa xóa code MoMo legacy

Luồng cần đạt:

User bấm thanh toán
-> tạo Payment PENDING
-> sinh URL VNPAY Sandbox
-> redirect sang VNPAY
-> VNPAY trả kết quả
-> backend verify signature
-> verify transaction reference
-> verify amount
-> xử lý idempotent
-> Payment SUCCESS/FAILED
-> cập nhật Contribution
-> cập nhật Booking
-> cập nhật MatchParticipant nếu cần

Return URL của trình duyệt không được tự quyết định Payment SUCCESS.

Payment core phải ổn định trước khi làm VNPAY refund.

---

# Priority 2 - Chat trong kèo

Chỉ làm chat theo Match.

Cho phép:
- creator của match
- participant đã JOINED

Chat chỉ cần:
- text message
- sender
- match
- content
- created_at

Phải có backend authorization.

Có thể dùng AJAX polling.

Không làm:
- inbox tổng quát
- kết bạn
- online status
- typing indicator
- read receipt
- gửi file
- gửi ảnh
- voice/video

---

# Priority 3 - Chatbot MVP

Mục tiêu:
Tạo chatbot AI hỗ trợ người dùng hiểu cách sử dụng hệ thống.

Chatbot có thể trả lời về:
- tìm sân
- đặt sân
- tiền cọc
- VNPAY
- hủy booking
- hoàn tiền
- tìm đối thủ
- tìm thêm người
- tham gia kèo
- đăng ký Chủ sân
- các chức năng của hệ thống

Chatbot chỉ tư vấn.

Không được:
- tự tạo booking
- tự thanh toán
- tự sửa database
- tự hủy booking
- thực hiện hành động thay user

Trong sprint hiện tại không cần:
- RAG
- vector database
- embeddings
- LangChain nếu không thật sự cần
- lưu lịch sử chat lâu dài

---

# Thứ tự ưu tiên

VNPAY
-> Chat trong kèo
-> Chatbot

Nếu thiếu thời gian:
bỏ Chatbot trước.

Không hy sinh độ ổn định của booking/payment để thêm chức năng.

---

# Kế hoạch cuối

Sau khi các chức năng hoàn thành:

1. Chạy targeted tests
2. Chạy full pytest
3. Manual test website
4. Kiểm tra database
5. Chụp ảnh giao diện thật
6. Cập nhật tài liệu
7. Sửa báo cáo theo source code cuối cùng

Không ghi một chức năng vào báo cáo là "đã hoàn thành" nếu chưa implement và test thực tế.