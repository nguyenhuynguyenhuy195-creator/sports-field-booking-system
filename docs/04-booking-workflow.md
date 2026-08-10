# 4. Quy trình booking và thanh toán

## 4.1. Luồng tạo booking chung

1. User đăng nhập và chọn một field đang `ACTIVE` thuộc venue `ACTIVE`.
2. User chọn ngày, giờ bắt đầu, giờ kết thúc và hình thức thanh toán.
3. Backend kiểm tra thời gian, giờ mở cửa, lịch bảo trì và giới hạn đặt trước.
4. Backend kiểm tra trùng lịch trong transaction.
5. Backend lấy các khung giá áp dụng, tách khoảng thời gian và tính tổng tiền.
6. Nếu có đoạn thời gian chưa được cấu hình giá, từ chối tạo booking.
7. Backend lưu booking, chi tiết giá chốt và trạng thái `CONFIRMED` trong cùng transaction.
8. Hệ thống giữ chỗ 15 phút và tạo hạn `initial_payment_due_at`; owner không cần duyệt thủ công.
9. Người tạo chuyển sang thanh toán khoản đầu tiên qua MoMo Sandbox.

## 4.2. Luồng thanh toán 100%

```text
CONFIRMED (giữ chỗ 15 phút)
→ Người tạo thanh toán 100% qua MoMo Sandbox
→ IPN hợp lệ
→ PAID
→ COMPLETED sau khi hết giờ sử dụng
```

Booking thông thường phải được tạo trước giờ bắt đầu ít nhất 60 phút.

## 4.3. Luồng tìm đội đối thủ 50/50

1. Booking phải được tạo trước giờ bắt đầu ít nhất 13 giờ.
2. Sau khi hệ thống giữ chỗ, người tạo thanh toán 50% trong 15 phút.
3. IPN hợp lệ chuyển booking sang `PARTIALLY_PAID` và mở kèo `FIND_OPPONENT`.
4. Đại diện đội đối thủ gửi yêu cầu.
5. Người tạo chấp nhận một đội; yêu cầu chuyển sang chờ thanh toán.
6. Đội đối thủ có 15 phút để thanh toán 50%.
7. Khi IPN hợp lệ và tổng tiền đủ, booking chuyển `PAID`, kèo chuyển `CONFIRMED`.
8. Nếu người tạo tự trả phần còn thiếu trước đó, booking chuyển `PAID`; đội đối thủ tham gia sau không còn nghĩa vụ đóng 50%.

## 4.4. Luồng tìm thêm người chơi

1. Hệ thống xác định tổng số người tiêu chuẩn và phần tiền mỗi người.
2. Người tạo khai số vị trí cần tìm; thành viên có sẵn không cần tài khoản.
3. Người tạo thanh toán phần của nhóm hiện có.
4. Payment thành công chuyển booking sang `PARTIALLY_PAID` và mở kèo `FIND_PLAYERS`.
5. User gửi yêu cầu tham gia; người tạo chấp nhận hoặc từ chối.
6. Người được chấp nhận có 15 phút để thanh toán phần của mình.
7. Payment thành công mới chuyển yêu cầu thành thành viên chính thức, trừ vị trí có nghĩa vụ bằng 0 vì người tạo đã trả đủ booking.
8. Khi tổng tiền đủ, booking chuyển `PAID`; kèo chỉ chuyển `FULL` khi số người chính thức đạt số vị trí cần tìm.

## 4.5. Hạn góp tiền

- Booking chia tiền phải thu đủ trước giờ bắt đầu 12 giờ.
- Trước hạn, người tạo có thể thanh toán toàn bộ phần còn thiếu.
- Nếu đến hạn vẫn thiếu và người tạo không trả thêm:
  1. Booking chuyển `REFUND_PENDING`.
  2. Hoàn 80% khoản người tạo đã đóng.
  3. Giữ 20% khoản người tạo đã đóng làm phí giữ sân cho owner.
  4. Hoàn 100% cho đối thủ/người ghép đã đóng đúng hạn.
  5. Khi refund hoàn tất, booking chuyển `CANCELLED` và giải phóng lịch.

## 4.6. Luồng hủy và hoàn tiền

### User hủy
- User được hủy `CONFIRMED` chưa thu tiền của mình trước giờ bắt đầu ít nhất 2 giờ.
- Người tạo hủy `PARTIALLY_PAID` được áp dụng chính sách hoàn tiền giống trường hợp không góp đủ.
- User không tự hủy `PAID` trong MVP.

### Owner hủy do sự cố
1. Owner nhập lý do hủy.
2. Booking `PARTIALLY_PAID` hoặc `PAID` chuyển `REFUND_PENDING`; booking `CONFIRMED` chưa thu tiền có thể chuyển thẳng `CANCELLED`.
3. Backend tạo refund toàn bộ qua MoMo Sandbox cho từng khoản hợp lệ.
4. Sau khi mọi refund thành công, booking chuyển `CANCELLED`.
5. Nếu refund thất bại hoặc đang xử lý, booking giữ `REFUND_PENDING` để retry/query.

### Người tham gia rút
- Rút trước giờ bắt đầu trên 12 giờ: hoàn 100%, yêu cầu chuyển `WITHDRAWN`, vị trí mở lại.
- Rút trong vòng 12 giờ: không hoàn tiền; khoản đã đóng vẫn tính cho booking.
- No-show không được hoàn tiền và chưa bị ghi điểm phạt trong MVP.

## 4.7. Trạng thái booking

- `PENDING`: trạng thái cũ được giữ trong schema để tương thích migration; luồng mới không tạo trạng thái này.
- `CONFIRMED`: hệ thống đã kiểm tra và đang giữ chỗ 15 phút, chờ khoản thanh toán đầu tiên.
- `PARTIALLY_PAID`: đã thu một phần, đang chờ góp đủ, chiếm chỗ.
- `PAID`: đã thu đủ tiền, chiếm chỗ.
- `REFUND_PENDING`: đang xử lý hoàn tiền, vẫn chiếm chỗ để tránh bán lại quá sớm.
- `COMPLETED`: đã sử dụng sân.
- `REJECTED`: trạng thái lịch sử của luồng duyệt cũ; luồng mới không tạo trạng thái này.
- `CANCELLED`: đã hủy và hoàn tiền cần thiết đã hoàn tất.
- `EXPIRED`: hết hạn trước khi có khoản thanh toán đầu tiên.

## 4.8. Chuyển trạng thái hợp lệ

```text
CONFIRMED → PAID
CONFIRMED → PARTIALLY_PAID
CONFIRMED → CANCELLED
CONFIRMED → EXPIRED

PARTIALLY_PAID → PAID
PARTIALLY_PAID → REFUND_PENDING

PAID → REFUND_PENDING
PAID → COMPLETED

REFUND_PENDING → CANCELLED
```

## 4.9. Kiểm tra trùng lịch

Hai khoảng thời gian giao nhau khi:

```text
new_start < existing_end
AND
new_end > existing_start
```

Với booking 18:00–20:00, phải từ chối 17:00–19:00, 18:00–20:00, 19:00–21:00, 18:30–19:30 và 17:00–21:00. Có thể chấp nhận 16:00–18:00 hoặc 20:00–22:00.

## 4.10. Xử lý MoMo

Giai đoạn nền tảng hiện dùng provider `MOCK`: service xác minh quyền và hạn, lấy amount từ contribution, tạo payment `SUCCESS`, rồi cập nhật contribution/booking trong cùng transaction. Không có chuyển hướng và không trừ tiền thật. Luồng MoMo Sandbox bên dưới là bước tích hợp kế tiếp trên cùng model/service.

1. Backend tạo payment `PENDING` với `orderId` và `requestId` duy nhất.
2. Backend ký HMAC bằng secret key từ biến môi trường.
3. User được chuyển đến `payUrl` của MoMo Sandbox.
4. Redirect chỉ hiển thị trạng thái chờ xác minh.
5. IPN được kiểm tra chữ ký, số tiền, booking, contribution và mã đối tác.
6. IPN lặp lại không được tạo payment hoặc cộng tiền lần hai.
7. Payment, contribution và booking được cập nhật trong một transaction.
8. Refund dùng request/order riêng, lưu kết quả và có thể query lại khi chưa có kết quả cuối cùng.

## 4.11. Trường hợp ngoại lệ chính

- Field hoặc venue không tồn tại/không hoạt động.
- Thời gian nằm ngoài giờ hoạt động, trùng bảo trì hoặc trùng booking.
- Thời gian không theo bước 30 phút, ngắn hơn 60 phút hoặc vượt giới hạn đặt trước.
- Thiếu khung giá cho một phần thời gian.
- Owner xử lý booking của sân khác.
- User thao tác booking hoặc nghĩa vụ thanh toán của người khác.
- Payment sai số tiền, sai chữ ký, hết hạn hoặc IPN bị gửi lặp.
- Tổng tiền có nguy cơ vượt `total_amount`.
- Yêu cầu tham gia hết hạn thanh toán hoặc kèo đã đủ người/đã có đối thủ.
- Refund thất bại hoặc đang xử lý.
