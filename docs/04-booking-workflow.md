# 4. Quy trình booking, tìm kèo và thanh toán

## 4.1. Luồng tạo booking chung

1. User đăng nhập và chọn field ACTIVE thuộc venue ACTIVE.
2. Hệ thống biết sport qua field type của field.
3. Với cầu lông, pickleball hoặc tennis, user chọn SINGLES hoặc DOUBLES; bóng đá không có bước này.
4. User chọn ngày và xem lưới availability 30 phút.
5. User chọn khoảng liên tục tối thiểu 60 phút.
6. User chọn DIRECT_BOOKING, FIND_OPPONENT hoặc FIND_PLAYERS.
7. Với FIND_PLAYERS, user nhập số vị trí cần tìm; backend snapshot vào `bookings.requested_players`.
8. Backend kiểm tra thời gian đặt trước, giờ hoạt động, bảo trì, trùng lịch và độ phủ giá.
9. Backend tính total_amount, deposit_amount bằng 30% và balance_due_at_venue bằng 70%.
10. Backend lưu booking, snapshot giá, khoản cọc và contribution trong một transaction.
11. Booking ở CONFIRMED và giữ chỗ 15 phút để creator thanh toán phần cọc đầu tiên.

## 4.2. Luồng DIRECT_BOOKING

> CONFIRMED → creator thanh toán 100% khoản cọc 30% → IPN hợp lệ → PAID → trả 70% tại sân → COMPLETED sau giờ sử dụng.

- Booking được tạo trước giờ bắt đầu ít nhất 60 phút.
- Website không thu và không xác nhận phần thanh toán tại sân.
- Trạng thái PAID được hiển thị là “Đã thanh toán cọc”.

## 4.3. Luồng FIND_PLAYERS

1. Booking được tạo trước giờ bắt đầu ít nhất 60 phút.
2. Creator chọn số vị trí muốn tìm.
3. Creator thanh toán toàn bộ khoản cọc 30% trong 15 phút.
4. IPN hợp lệ chuyển booking sang PAID và cho phép mở match FIND_PLAYERS.
5. User nhập lời nhắn và số điện thoại dùng Zalo rồi gửi yêu cầu.
6. Trước khi được chấp nhận, số điện thoại không hiển thị cho creator hoặc công khai.
7. Creator chấp nhận hoặc từ chối.
8. Chấp nhận thành công chuyển participant thẳng JOINED, không tạo contribution/payment.
9. Số Zalo chỉ hiển thị cho creator để hai bên liên hệ.
10. Khi đủ required_players, match chuyển FULL.
11. Tại sân, người ghép trả tiền trực tiếp cho creator; creator thanh toán phần còn lại cho owner.

Nếu participant rút, trạng thái chuyển WITHDRAWN và vị trí mở lại. Vì không có payment online nên không phát sinh refund. MVP không tự phạt no-show.

## 4.4. Luồng FIND_OPPONENT

Ví dụ total_amount 600.000đ:

- deposit_amount: 180.000đ.
- Creator contribution: 90.000đ.
- Opponent contribution: 90.000đ.
- Số còn lại tại sân: 420.000đ; hai phía tự chia 210.000đ mỗi bên nếu thỏa thuận 50/50.

Quy trình:

1. Booking phải được tạo trước giờ bắt đầu ít nhất 24 giờ.
2. Trong 15 phút giữ chỗ, creator thanh toán 50% deposit_amount.
3. IPN hợp lệ chuyển booking PARTIALLY_PAID và cho phép mở match FIND_OPPONENT.
4. Đại diện phía đối thủ gửi yêu cầu.
5. Creator chấp nhận một yêu cầu.
6. Đối thủ có 15 phút thanh toán contribution, nhưng không được vượt matchmaking_deadline.
7. IPN hợp lệ làm đủ deposit_amount, booking chuyển PAID và match chuyển CONFIRMED.
8. Phần 70% còn lại được thanh toán tại sân.

FIND_OPPONENT áp dụng cho bóng đá, đánh đơn và đánh đôi. Với đánh đôi, đại diện đối thủ chịu trách nhiệm cho cặp của mình.

## 4.5. Hạn tìm đối thủ và creator top-up

- matchmaking_deadline = thời điểm bắt đầu trừ 12 giờ.
- Đến hạn mà chưa có payment đối thủ, hệ thống đóng nghĩa vụ nhận cọc từ đối thủ.
- Creator có thêm 30 phút để thanh toán phần cọc còn thiếu.
- funding_deadline = matchmaking_deadline cộng 30 phút.
- Top-up thành công chuyển booking PAID; match có thể tiếp tục phục vụ liên hệ nhưng đối thủ không còn nghĩa vụ online.
- Không top-up đúng hạn chuyển booking REFUND_PENDING.

Chính sách refund khi creator không top-up:

1. Hoàn 80% khoản creator đã đóng.
2. Giữ 20% khoản creator đã đóng làm phí giữ sân.
3. Hoàn 100% cho payment đối thủ nếu có trường hợp cần khôi phục lỗi.
4. Sau khi refund thành công, booking chuyển CANCELLED và giải phóng lịch.

## 4.6. Hình thức thi đấu theo bộ môn

### Bóng đá

- Field type là sân 5, 7 hoặc 11 người.
- Creator không chọn SINGLES/DOUBLES.
- Có thể DIRECT_BOOKING, FIND_OPPONENT hoặc FIND_PLAYERS.
- Với FIND_PLAYERS, creator tự chọn required_players trong giới hạn capacity của field.

### Cầu lông, pickleball và tennis

- Bắt buộc chọn SINGLES hoặc DOUBLES.
- SINGLES: tối đa 2 người; DIRECT_BOOKING hoặc FIND_OPPONENT.
- DOUBLES: tối đa 4 người; cho phép cả ba booking mode.
- FIND_PLAYERS trong DOUBLES dùng để tìm thêm đồng đội/người chơi, không thu cọc từ người ghép.

## 4.7. Hủy và hoàn tiền

### User hủy khi chưa thu cọc

- User được hủy CONFIRMED của mình trước giờ bắt đầu ít nhất 2 giờ.
- Không có payment nên chuyển thẳng CANCELLED.

### Creator hủy FIND_OPPONENT đang PARTIALLY_PAID

- Áp dụng hoàn 80% và giữ 20% khoản creator đã cọc.
- Chuyển REFUND_PENDING cho đến khi refund xong.

### Owner hủy do sự cố

1. Owner nhập lý do.
2. CONFIRMED chưa thu cọc chuyển thẳng CANCELLED.
3. PARTIALLY_PAID hoặc PAID chuyển REFUND_PENDING.
4. Backend hoàn 100% mọi khoản cọc đã thu qua provider.
5. Chỉ sau khi tất cả refund thành công mới chuyển CANCELLED.

### Participant FIND_PLAYERS rút

- Chuyển WITHDRAWN, mở lại vị trí và không tạo refund.
- Số điện thoại không tiếp tục hiển thị sau khi booking kết thúc/hủy.

## 4.8. Trạng thái booking

- PENDING: lịch sử của luồng cũ, service mới không tạo.
- CONFIRMED: đang giữ chỗ 15 phút, chờ khoản cọc đầu tiên.
- PARTIALLY_PAID: đã thu một phần deposit_amount, chỉ dùng chủ yếu cho FIND_OPPONENT.
- PAID: đã thu đủ deposit_amount; giao diện phải ghi “Đã thanh toán cọc”.
- REFUND_PENDING: đang xử lý hoàn cọc và vẫn chiếm chỗ.
- COMPLETED: thời gian sử dụng đã kết thúc.
- REJECTED: lịch sử của luồng cũ.
- CANCELLED: đã hủy và hoàn các khoản bắt buộc.
- EXPIRED: hết hạn trước khi có khoản cọc đầu tiên.

## 4.9. Chuyển trạng thái hợp lệ

> CONFIRMED → PAID | PARTIALLY_PAID | CANCELLED | EXPIRED

> PARTIALLY_PAID → PAID | REFUND_PENDING

> PAID → REFUND_PENDING | COMPLETED

> REFUND_PENDING → CANCELLED

## 4.10. Availability, quote và trùng lịch

Hai khoảng thời gian giao nhau khi:

> new_start < existing_end AND new_end > existing_start

Availability và quote không khóa chỗ. Transaction tạo booking phải kiểm tra lại toàn bộ dữ liệu. Booking 18:00–20:00 từ chối mọi khoảng giao nhau nhưng cho phép kết thúc đúng 18:00 hoặc bắt đầu đúng 20:00.

## 4.11. Google Maps

### Owner khai báo venue

1. Owner nhập địa chỉ.
2. Places Autocomplete trả gợi ý.
3. Owner chọn một địa điểm và kiểm tra ghim.
4. Form gửi place ID, address, latitude và longitude.
5. Backend validate và lưu cùng venue.

### User tìm sân gần đây

1. User bấm “Dùng vị trí của tôi”.
2. Browser xin quyền Geolocation.
3. User chọn bán kính 3/5/10 km.
4. Backend lọc venue ACTIVE có tọa độ và tính khoảng cách gần đúng.
5. Kết quả sắp xếp theo khoảng cách và có nút mở Google Maps.

Nếu không cấp quyền vị trí, user tiếp tục tìm theo từ khóa/bộ lọc. Hệ thống không nhập venue bên ngoài từ Google Nearby Search.

## 4.12. Xử lý MoMo Sandbox

Provider MOCK hiện tại:

- Lấy amount từ contribution.
- Ghi nhận payment giả lập để test.
- Không redirect, không gọi MoMo và không trừ tiền thật.

Luồng MoMo Sandbox mục tiêu:

1. Tạo payment PENDING với orderId/requestId duy nhất.
2. Ký HMAC bằng secret từ biến môi trường.
3. Gọi create payment và chuyển user đến payUrl Sandbox.
4. Redirect chỉ hiển thị trạng thái đang xác minh.
5. IPN được xác minh chữ ký và đối chiếu dữ liệu.
6. Payment/contribution/booking cập nhật idempotent.
7. Refund dùng order/request riêng và query lại nếu chưa có kết quả cuối.

## 4.13. Trường hợp biên chính

- Field type không thuộc sport hợp lệ hoặc field/venue chưa ACTIVE.
- Booking môn dùng vợt thiếu play format; SINGLES chọn FIND_PLAYERS.
- Vị trí, bán kính hoặc tọa độ không hợp lệ.
- User từ chối Geolocation hoặc venue cũ chưa có tọa độ.
- Thời gian ngoài giờ, trùng bảo trì/booking hoặc thiếu giá.
- Creator/đối thủ thanh toán sai nghĩa vụ, quá hạn hoặc IPN lặp.
- Opponent payment window vượt matchmaking_deadline.
- Người ghép thiếu số điện thoại hoặc creator cố xem số trước khi chấp nhận.
- Match đã đủ người/đã có đối thủ.
- Refund thất bại hoặc đang xử lý.
