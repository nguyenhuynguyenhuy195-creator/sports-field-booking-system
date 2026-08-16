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
9. Backend tính total_amount và deposit_amount mục tiêu bằng 30%. Số trả tại sân được hiển thị từ số cọc thực thu: 70% với DIRECT_BOOKING/FIND_PLAYERS, còn FIND_OPPONENT có thể là 85% hoặc 70%.
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
- Chưa có đối thủ: creator đã giữ sân bằng 90.000đ và còn 510.000đ tại sân.
- Có đối thủ đã cọc: tổng cọc online 180.000đ, còn 420.000đ tại sân; hai phía tự chia phần còn lại theo thỏa thuận.

Quy trình:

1. Booking phải được tạo trước giờ bắt đầu ít nhất 24 giờ.
2. Trong 15 phút giữ chỗ, creator thanh toán 50% deposit_amount.
3. IPN hợp lệ chuyển booking PARTIALLY_PAID và cho phép mở match FIND_OPPONENT.
4. Đại diện phía đối thủ nhập số Zalo, đồng ý chia sẻ rồi bấm “Nhận kèo”.
5. Trong transaction, service khóa match và contribution OPPONENT; nếu còn trống thì participant chuyển thẳng `ACCEPTED_AWAITING_PAYMENT` và giữ suất tối đa 15 phút, không cần creator duyệt.
6. Đối thủ thanh toán contribution trước payment_due_at và trước giờ booking bắt đầu.
7. IPN hợp lệ làm đủ deposit_amount, participant chuyển JOINED, booking chuyển PAID và match chuyển CONFIRMED.
8. Nếu hết hạn chưa trả, participant chuyển EXPIRED, contribution được giải phóng và bài mở lại. Nếu không có đối thủ, booking vẫn PARTIALLY_PAID hợp lệ và creator trả 85% tại sân; nếu có đối thủ, phần còn lại tại sân là 70%.
9. Sau khi JOINED, kèo xuất hiện trong “Lịch & kèo của tôi” của đại diện đối thủ; trang chi tiết cho hai bên xem số Zalo của nhau. Trước đó và sau khi booking kết thúc/hủy, số liên hệ không được hiển thị.

FIND_OPPONENT áp dụng cho bóng đá, đánh đơn và đánh đôi. Với đánh đôi, đại diện đối thủ chịu trách nhiệm cho cặp của mình.

## 4.5. Thời gian tồn tại của bài tìm đối thủ

- Bài FIND_OPPONENT tồn tại từ khi creator cọc thành công đến giờ booking bắt đầu.
- Bài đóng sớm khi creator chủ động đóng hoặc một đối thủ đã thanh toán thành công.
- Đội bấm nhận kèo có tối đa 15 phút thanh toán; nếu nhận sát giờ thì hạn được cắt đúng tại giờ booking bắt đầu.
- Đến giờ bắt đầu, các suất ACCEPTED_AWAITING_PAYMENT chưa trả chuyển hết hiệu lực và bài không còn hiển thị trong danh sách kèo đang mở.
- Không tìm được đối thủ không hủy booking, không tạo refund và không yêu cầu creator top-up.
- Creator tiếp tục sử dụng sân, tự tìm đối thủ bên ngoài nếu muốn và thanh toán 85% còn lại tại sân.

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

### User chủ động hủy

- User được hủy booking của mình trước giờ bắt đầu.
- CONFIRMED chưa có payment chuyển thẳng CANCELLED.
- Creator đã cọc không được hoàn phần cọc của mình; contribution/payment giữ lịch sử và phần đã đóng chuyển FORFEITED khi phù hợp.
- DIRECT_BOOKING/FIND_PLAYERS chuyển thẳng CANCELLED vì không có bên thứ ba cần hoàn.
- FIND_OPPONENT chưa có payment đối thủ chuyển thẳng CANCELLED và creator mất 15% đã cọc.
- FIND_OPPONENT đã có payment đối thủ chuyển REFUND_PENDING để hoàn 100% cho đối thủ; creator vẫn mất phần cọc của mình.

### Đối thủ chủ động rút hoặc no-show

- Đối thủ đã cọc không được hoàn 15% đã đóng.
- Participant chuyển WITHDRAWN, contribution chuyển FORFEITED và vị trí đối thủ mở lại.
- Khoản cọc bị mất vẫn tính vào booking; người thay thế không bị thu cọc lần hai.
- Booking không bị hủy và số còn lại tại sân tiếp tục bằng total_amount trừ paid_amount.

### Owner hủy do sự cố

1. Owner nhập lý do.
2. CONFIRMED chưa thu cọc chuyển thẳng CANCELLED.
3. PARTIALLY_PAID hoặc PAID chuyển REFUND_PENDING.
4. Backend hoàn 100% mọi khoản cọc đã thu qua provider.
5. Chỉ sau khi tất cả refund thành công mới chuyển CANCELLED.

Thanh toán trùng/sai do hệ thống cũng phải hoàn 100% khoản bị ảnh hưởng. Refund không dùng cho người chủ động hủy/rút hoặc no-show.

### Participant FIND_PLAYERS rút

- Chuyển WITHDRAWN, mở lại vị trí và không tạo refund.
- Số điện thoại không tiếp tục hiển thị sau khi booking kết thúc/hủy.

## 4.8. Trạng thái booking

- PENDING: lịch sử của luồng cũ, service mới không tạo.
- CONFIRMED: đang giữ chỗ 15 phút, chờ khoản cọc đầu tiên.
- PARTIALLY_PAID: creator FIND_OPPONENT đã cọc 15% và booking đã giữ sân hợp lệ; có thể giữ trạng thái này đến khi COMPLETED nếu không có đối thủ.
- PAID: đã thu đủ deposit_amount; giao diện phải ghi “Đã thanh toán cọc”.
- REFUND_PENDING: đang xử lý hoàn cọc và vẫn chiếm chỗ.
- COMPLETED: thời gian sử dụng đã kết thúc.
- REJECTED: lịch sử của luồng cũ.
- CANCELLED: đã hủy và hoàn các khoản bắt buộc.
- EXPIRED: hết hạn trước khi có khoản cọc đầu tiên.

## 4.9. Chuyển trạng thái hợp lệ

> CONFIRMED → PAID | PARTIALLY_PAID | CANCELLED | EXPIRED

> PARTIALLY_PAID → PAID | CANCELLED | REFUND_PENDING | COMPLETED

> PAID → CANCELLED | REFUND_PENDING | COMPLETED

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
- Đối thủ nhận kèo sát giờ và thời hạn giữ suất 15 phút bị cắt tại giờ booking bắt đầu.
- Bài tìm đối thủ hoặc yêu cầu thanh toán vẫn còn trạng thái lưu nhưng giờ booking đã bắt đầu; backend phải xử lý theo effective state và từ chối thao tác mới.
- Người ghép thiếu số điện thoại hoặc creator cố xem số trước khi chấp nhận.
- Match đã đủ người/đã có đối thủ.
- Refund thất bại hoặc đang xử lý.
