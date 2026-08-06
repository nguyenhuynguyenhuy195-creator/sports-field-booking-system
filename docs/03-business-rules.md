# 3. Quy tắc nghiệp vụ

## 3.1. Tài khoản và phân quyền

### BR-001: Đăng nhập trước khi thao tác
User phải đăng nhập trước khi tạo booking, tạo kèo, gửi yêu cầu tham gia hoặc thanh toán.

### BR-002: Phân quyền backend
- USER không được truy cập chức năng OWNER hoặc ADMIN.
- OWNER không được truy cập chức năng ADMIN.
- Không dựa vào việc ẩn nút trên frontend để bảo vệ chức năng.

### BR-003: Yêu cầu trở thành owner
- Tài khoản đăng ký mới luôn có role `USER`.
- User có tối đa một yêu cầu trở thành owner đang `PENDING`.
- Chỉ admin được chấp nhận hoặc từ chối yêu cầu.
- Chỉ khi yêu cầu được chấp nhận, role mới chuyển thành `OWNER`.

### BR-004: Quyền sở hữu
- Owner chỉ được quản lý venue có `owner_id` của mình.
- Owner chỉ được quản lý field, giá, bảo trì và booking thuộc venue của mình.

### BR-005: Khóa tài khoản và xóa dữ liệu
- Tài khoản `LOCKED` không được đăng nhập hoặc thực hiện giao dịch mới.
- Admin không được xóa lịch sử booking, payment, contribution hoặc refund.
- Dữ liệu đã có quan hệ phải được xóa mềm hoặc chuyển trạng thái thay vì xóa vật lý.

## 3.2. Venue, field, giá và bảo trì

### BR-006: Duyệt venue
- Venue mới có trạng thái `PENDING`.
- Chỉ venue `ACTIVE` mới được hiển thị công khai.
- Admin có thể chuyển venue thành `ACTIVE` hoặc `HIDDEN`.

### BR-007: Kích hoạt field
- Field mới mặc định `INACTIVE`.
- Chỉ field `ACTIVE` thuộc venue `ACTIVE` mới nhận booking.
- Field chỉ được bật `ACTIVE` sau khi có đầy đủ cấu hình cần thiết và khung giá hợp lệ.

### BR-008: Khung giá
- Giá được cấu hình theo field, ngày trong tuần và khoảng giờ.
- Hai khung giá của cùng field trong cùng ngày áp dụng không được chồng nhau.
- `start_time` của khung giá phải nhỏ hơn `end_time` và `hourly_price` phải lớn hơn 0.
- Không sử dụng `base_price` làm giá thay thế khi thiếu cấu hình.

### BR-009: Tính giá booking
- Toàn bộ thời gian booking phải được phủ bởi các khung giá.
- Booking đi qua nhiều khung giá được tách thành các đoạn và cộng subtotal của từng đoạn.
- Giá phải lấy từ database; backend tự tính và lưu chi tiết giá tại thời điểm đặt.
- Không tin giá hoặc tổng tiền gửi từ frontend.

### BR-010: Lịch bảo trì
- Owner được tạo lịch bảo trì theo ngày và khoảng giờ cho field của mình.
- Không được tạo lịch bảo trì giao với booking `PENDING`, `CONFIRMED`, `PARTIALLY_PAID` hoặc `PAID`.
- Booking không được giao với lịch bảo trì đang hiệu lực.

## 3.3. Thời gian và trùng lịch

### BR-011: Thời gian booking
- `start_time` phải nhỏ hơn `end_time` và booking không đi qua nửa đêm trong MVP.
- Giờ bắt đầu và kết thúc phải theo bước 30 phút.
- Thời lượng tối thiểu là 60 phút.
- Booking phải nằm trong giờ mở cửa của venue.

### BR-012: Khoảng thời gian cho phép
- `FULL_PAYMENT` phải được tạo trước giờ bắt đầu ít nhất 60 phút.
- `SPLIT_OPPONENT` và `SPLIT_PLAYERS` phải được tạo trước giờ bắt đầu ít nhất 13 giờ.
- Không được đặt ngày trong quá khứ hoặc quá 30 ngày kể từ thời điểm tạo.

### BR-013: Trùng lịch
Một field không được có hai booking chiếm chỗ giao nhau.

```text
new_start < existing_end
AND
new_end > existing_start
```

Trạng thái chiếm chỗ: `PENDING`, `CONFIRMED`, `PARTIALLY_PAID`, `PAID` và `REFUND_PENDING`.

Trạng thái không chiếm chỗ: `REJECTED`, `CANCELLED`, `EXPIRED` và `COMPLETED`.

Việc kiểm tra và tạo booking phải nằm trong cùng transaction để hạn chế đặt trùng đồng thời.

## 3.4. Vòng đời booking

### BR-014: Tạo và xác nhận booking
- Booking mới có trạng thái `PENDING`.
- Chỉ owner sở hữu field mới được xác nhận hoặc từ chối.
- Chỉ booking `PENDING` được xác nhận hoặc từ chối.
- Từ chối phải lưu lý do.

### BR-015: Hết hạn
- `PENDING` hết hạn sau 30 phút nếu owner chưa phản hồi.
- Sau khi owner xác nhận, người tạo có 15 phút để hoàn thành khoản thanh toán đầu tiên.
- `CONFIRMED` chưa có khoản thanh toán đầu tiên sau 15 phút chuyển `EXPIRED`.
- Booking `EXPIRED` không chiếm chỗ.

### BR-016: Hạn góp đủ tiền
- Booking chia tiền phải thu đủ trước giờ bắt đầu 12 giờ.
- Người tạo được thanh toán phần còn thiếu bất kỳ lúc nào trước hạn.
- Khi tổng tiền thành công bằng `total_amount`, booking chuyển `PAID`.
- Nếu người tạo đã trả đủ phần thiếu, người tham gia sau đó không còn nghĩa vụ thanh toán cho booking đó.

### BR-017: Hủy booking
- User chỉ được hủy booking của mình ở trạng thái `PENDING` hoặc `CONFIRMED` và trước giờ bắt đầu ít nhất 2 giờ.
- Người tạo hủy booking `PARTIALLY_PAID` được xử lý như trường hợp không góp đủ đúng hạn.
- User không được tự hủy booking `PAID` trong MVP.
- Owner được hủy `CONFIRMED` hoặc `PAID` khi có sự cố và bắt buộc nhập lý do.
- Booking `PAID` do owner hủy phải hoàn tiền thành công trước khi chuyển `CANCELLED`.

### BR-018: Hoàn thành booking
Booking chỉ chuyển từ `PAID` sang `COMPLETED` sau khi thời gian sử dụng sân kết thúc.

## 3.5. Thanh toán và hoàn tiền MoMo

### BR-019: Nguyên tắc thanh toán
- Chỉ dùng MoMo Sandbox trong phiên bản đồ án ngành.
- Số tiền thanh toán được lấy từ nghĩa vụ đóng góp trong database.
- Tổng payment `SUCCESS` sau khi trừ refund không được vượt `total_amount`.
- Mỗi nghĩa vụ đóng góp chỉ được có một kết quả thanh toán thành công còn hiệu lực.
- Cho phép thử lại khi giao dịch thất bại hoặc bị hủy trong thời hạn còn hiệu lực.

### BR-020: Xác nhận kết quả MoMo
- Redirect của trình duyệt chỉ dùng để hiển thị kết quả, không phải bằng chứng thanh toán cuối cùng.
- Chỉ IPN hợp lệ sau khi kiểm tra chữ ký HMAC và đối chiếu `orderId`, `amount`, `partnerCode` mới được cập nhật `SUCCESS`.
- IPN và yêu cầu hoàn tiền phải có xử lý idempotency.
- Payment thành công và cập nhật booking/contribution phải nằm trong cùng transaction database.

### BR-021: Hình thức thanh toán
- `FULL_PAYMENT`: người tạo có nghĩa vụ thanh toán 100%.
- `SPLIT_OPPONENT`: người tạo thanh toán 50%; đội đối thủ được chấp nhận thanh toán 50%.
- `SPLIT_PLAYERS`: backend chia tổng tiền theo tổng số người tiêu chuẩn; người tạo trả phần nhóm hiện có, mỗi vị trí cần tìm chịu một phần.
- Thành viên có sẵn không bắt buộc có tài khoản.
- Số vị trí cần tìm bị khóa sau payment thành công đầu tiên.

### BR-022: Làm tròn tiền chia
- Tiền được lưu bằng `DECIMAL(12,2)` nhưng nghĩa vụ thanh toán MoMo dùng số nguyên VND.
- Các phần được tính đến từng đồng; phần cuối cùng được điều chỉnh để tổng nghĩa vụ đúng bằng `total_amount`.
- Không được thu dư rồi giữ phần chênh lệch.

### BR-023: Không góp đủ đúng hạn
- Nếu đến hạn 12 giờ mà booking chưa đủ tiền, người tạo được yêu cầu thanh toán phần thiếu.
- Nếu người tạo không thanh toán, booking chuyển `REFUND_PENDING`.
- Hoàn 80% khoản người tạo đã đóng; 20% còn lại là phí giữ sân ghi nhận cho owner.
- Hoàn 100% cho đối thủ/người ghép đã thanh toán đúng hạn.
- Chỉ chuyển booking sang `CANCELLED` khi các refund cần thiết đã thành công.

### BR-024: Owner hủy booking đã thanh toán
- Khi owner hủy vì sự cố, hệ thống hoàn 100% các khoản đã thu.
- Phải lưu lý do, mã giao dịch hoàn tiền và trạng thái refund.
- Nếu refund chưa thành công, booking giữ `REFUND_PENDING`.

## 3.6. Tìm kèo và tham gia

### BR-025: Tạo kèo
- Người tạo phải sở hữu booking liên quan.
- Booking `FULL_PAYMENT` chỉ tạo kèo sau khi `PAID`.
- Booking chia tiền được tạo kèo sau khi khoản thanh toán đầu tiên thành công và booking chuyển `PARTIALLY_PAID`.
- Không tạo kèo cho booking `REJECTED`, `CANCELLED`, `EXPIRED`, `REFUND_PENDING` hoặc `COMPLETED`.
- Một booking có tối đa một kèo trong MVP.

### BR-026: Kèo tìm đối thủ
- Một đại diện gửi yêu cầu thay cho cả đội.
- Người tạo không được gửi yêu cầu vào kèo của chính mình.
- Mỗi user chỉ có một yêu cầu `PENDING` cho cùng một kèo.
- Chỉ người tạo được chấp nhận hoặc từ chối yêu cầu.
- Chỉ một đội đối thủ được chấp nhận; sau khi hoàn thành nghĩa vụ thanh toán, kèo chuyển `CONFIRMED`.

### BR-027: Kèo tìm người
- `required_players` là số vị trí còn thiếu, không tính người tạo.
- Thành viên hiện có không bắt buộc có tài khoản; người tạo chịu phần thanh toán của nhóm này.
- Không chấp nhận quá số vị trí còn thiếu.
- Kèo chỉ chuyển `FULL` khi số người `JOINED` đạt `required_players`; trạng thái đủ người độc lập với trạng thái đủ tiền của booking.
- Nếu người tạo đã trả đủ booking, người ghép được chấp nhận sau đó có nghĩa vụ bằng 0 và có thể chuyển `JOINED` mà không phải thanh toán.

### BR-028: Thời hạn thanh toán yêu cầu tham gia
- Sau khi được chấp nhận, đối thủ/người ghép có 15 phút để thanh toán.
- Quá hạn, yêu cầu chuyển `EXPIRED` và vị trí được mở lại.
- Người tham gia chỉ trở thành thành viên chính thức sau payment `SUCCESS`, trừ khi booking đã được người tạo trả đủ và nghĩa vụ của vị trí đã được điều chỉnh về 0.

### BR-029: Rút khỏi kèo
- Người đã thanh toán rút trước giờ bắt đầu trên 12 giờ được hoàn 100% và vị trí được mở lại.
- Trong vòng 12 giờ trước trận, người tham gia có thể báo không tham gia nhưng không được hoàn tiền.
- Khoản không hoàn vẫn được tính vào tổng tiền booking; vị trí thay thế không bị thu thêm nếu booking đã đủ tiền.

### BR-030: No-show
Người đã thanh toán nhưng không đến sân không được hoàn tiền. MVP chưa lưu điểm vi phạm hoặc tự động khóa tài khoản vì no-show.
