# 8. Tiêu chí nghiệm thu

## AC-001: Đăng ký và đăng nhập

- Email bắt buộc, không trùng; mật khẩu được hash và không lưu thô.
- Tài khoản mới có role `USER`, status `ACTIVE`.
- Đăng nhập đúng duy trì session; sai mật khẩu báo lỗi.
- Tài khoản `LOCKED` không đăng nhập được.

## AC-002: Yêu cầu trở thành owner

- User gửi được một yêu cầu `PENDING` và không tạo được yêu cầu `PENDING` thứ hai.
- Chỉ admin được duyệt hoặc từ chối.
- Duyệt thành công chuyển role user thành `OWNER` trong cùng transaction.
- Từ chối phải lưu lý do và không đổi role.

## AC-003: Owner tạo venue và field

- `owner_id` lấy từ `current_user`, không nhận từ form.
- Venue mới mặc định `PENDING`, chưa hiển thị công khai.
- Chỉ admin duyệt venue thành `ACTIVE`; hệ thống lưu người duyệt, thời điểm duyệt và ghi chú kiểm duyệt nếu có.
- Field phải thuộc venue của owner hiện tại và mặc định `INACTIVE`.
- Không tạo hai field trùng tên trong cùng venue.
- Chỉ field `ACTIVE` thuộc venue `ACTIVE` mới xuất hiện để đặt.

### AC-003A: Tìm kiếm và lọc sân công khai

- Tìm được venue theo tên, địa chỉ, quận/huyện hoặc tỉnh/thành phố mà không phân biệt chữ hoa/thường.
- Ký tự `%`, `_` và `\` trong từ khóa được hiểu là văn bản thường, không mở rộng thành wildcard SQL.
- Chỉ venue `ACTIVE` có ít nhất một field `ACTIVE` xuất hiện; field chưa hoạt động không làm venue khớp bộ lọc.
- Lọc loại sân và khoảng giá có thể dùng riêng hoặc kết hợp với từ khóa.
- “Giá từ” và khoảng giá lấy mức thấp nhất của khung giá `ACTIVE`; khi lọc loại sân, phép tính chỉ xét field `ACTIVE` thuộc loại đó.
- Giá âm, vượt giới hạn hoặc giá tối thiểu lớn hơn giá tối đa hiển thị lỗi tiếng Việt và không làm lỗi trang.
- Kết quả hiển thị tối đa 9 venue/trang, có tổng số kết quả và giữ nguyên điều kiện khi chuyển trang.
- Không có kết quả phải hiển thị empty state và nút xóa bộ lọc.

## AC-004: Cấu hình khung giá

- Owner chỉ cấu hình giá cho field của mình.
- Có ngày trong tuần, giờ bắt đầu, giờ kết thúc và giá theo giờ lớn hơn 0.
- Không chấp nhận khung giá chồng nhau trong cùng ngày áp dụng.
- Field chưa có cấu hình giá hợp lệ không được bật `ACTIVE`.

## AC-005: Lịch bảo trì

- Owner chỉ tạo bảo trì cho field của mình.
- Thời gian hợp lệ và nằm trong ngày đã chọn.
- Không tạo hai lịch bảo trì `ACTIVE` chồng nhau cho cùng field.
- Không tạo được lịch bảo trì giao với booking đang chiếm chỗ.
- Booking không được tạo trong khoảng bảo trì `ACTIVE`.

## AC-006: Tạo booking và tính giá

- User đăng nhập; venue và field đều `ACTIVE`.
- Thời gian theo bước 30 phút, tối thiểu 60 phút và không qua nửa đêm.
- Không nằm trong quá khứ, không vượt 30 ngày và đáp ứng thời gian đặt trước của payment mode.
- Nằm trong giờ mở cửa, không trùng bảo trì và booking chiếm chỗ.
- Toàn bộ thời gian được phủ bởi khung giá.
- Endpoint báo giá trả đúng các đoạn giá nhưng không tạo booking; submit cuối cùng phải kiểm tra lại toàn bộ.
- Backend tách đúng từng đoạn giá, tính `total_amount` và lưu price snapshot.
- Booking mới là `CONFIRMED`, chiếm chỗ và có hạn thanh toán đầu tiên 15 phút.

### AC-006A: Lưới giờ trống

- Endpoint availability trả các đoạn 30 phút nằm trọn trong giờ hoạt động của venue và không tạo dữ liệu.
- Mỗi đoạn có đúng một trạng thái: `AVAILABLE`, `BOOKED`, `MAINTENANCE`, `NO_PRICE` hoặc `PAST`.
- Giữ chỗ `CONFIRMED` đã hết hạn và chưa thanh toán không làm đoạn giờ tiếp tục hiển thị là bận.
- Giao diện cho chọn mốc bắt đầu/kết thúc liên tục; khoảng dưới 60 phút hoặc đi qua đoạn không `AVAILABLE` không được tiếp tục.
- Tạm tính hiển thị từ endpoint quote; tạo booking vẫn kiểm tra lại để xử lý dữ liệu thay đổi đồng thời.

## AC-007: Giữ chỗ tự động

- Booking chỉ được tạo sau khi backend kiểm tra hợp lệ trong transaction.
- Không có bước hoặc endpoint owner xác nhận/từ chối booking thông thường.
- Owner xem được booking thuộc sân của mình và có thể hủy do sự cố với lý do bắt buộc.
- Owner khác bị từ chối và dữ liệu không thay đổi.

## AC-008: Hết hạn booking

- `CONFIRMED` quá 15 phút chưa có khoản thanh toán đầu tiên chuyển `EXPIRED`.
- Booking hết hạn không còn chiếm chỗ.
- Job chạy lại không thay đổi trạng thái lần hai hoặc tạo tác dụng phụ trùng.

## AC-009: MoMo Sandbox payment

- Amount lấy từ contribution, không nhận từ frontend.
- Tạo `order_id`, `request_id` duy nhất và chữ ký HMAC đúng.
- Redirect không tự đánh dấu thành công.
- Chỉ IPN chữ ký hợp lệ, đúng order/amount/partner mới tạo kết quả `SUCCESS`.
- IPN lặp lại được xử lý idempotent.
- Payment thất bại được thử lại khi contribution còn hạn.
- Không được thu vượt `total_amount`.

### AC-009A: Nền tảng payment mô phỏng

- Provider `MOCK` lấy amount từ contribution và không nhận amount từ form.
- Chỉ user được gắn với contribution mới được thanh toán; request lặp hoặc contribution đã xử lý bị từ chối.
- Payment `SUCCESS`, `contribution.amount_paid`, `booking.paid_amount` và trạng thái booking được cập nhật trong cùng transaction.
- Giao diện ghi rõ đây là mô phỏng, không trừ tiền thật và không giả vờ là giao dịch MoMo.

## AC-010: Thanh toán 100%

- `FULL_PAYMENT` yêu cầu người tạo trả toàn bộ `total_amount`.
- IPN thành công cập nhật contribution `PAID` và booking `PAID` trong cùng transaction.
- Không tạo match trước khi booking `PAID`.

## AC-011: Chia 50/50 tìm đối thủ

- Người tạo trả đúng 50% trong thời gian giữ chỗ tự động.
- Payment thành công chuyển booking `PARTIALLY_PAID` và cho phép mở kèo.
- Chỉ một đại diện đội đối thủ được chấp nhận.
- Người được chấp nhận có 15 phút để trả 50%; hết hạn thì vị trí mở lại.
- Khi đủ tiền, booking `PAID` và match `CONFIRMED` sau khi đội đối thủ được chấp nhận; nếu người tạo đã top-up đủ trước đó thì đại diện đội được chấp nhận không phải trả thêm.

## AC-012: Chia theo đầu người

- `required_players` là số vị trí còn thiếu và không tính người tạo.
- Thành viên có sẵn không bắt buộc có tài khoản.
- Backend tính phần người tạo và từng vị trí; tổng nghĩa vụ bằng `total_amount`.
- Số tiền tính đến từng đồng, phần cuối điều chỉnh đúng tổng.
- Không nhận quá số vị trí hoặc vượt sức chứa field.
- Người ghép chỉ thành `JOINED` sau payment thành công, trừ khi người tạo đã trả đủ booking và nghĩa vụ vị trí bằng 0.
- Match chỉ `FULL` khi đủ số người `JOINED`, không chỉ vì booking đã `PAID`.

## AC-013: Người tạo trả phần còn thiếu

- Người tạo được xem số tiền còn thiếu và trả trước funding deadline.
- Payment thành công đủ tổng chuyển booking `PAID`.
- Contribution chưa thanh toán của đối thủ/người ghép chuyển `WAIVED` để không thu thêm nhưng vẫn giữ `amount_due` gốc phục vụ đối soát; kèo vẫn mở cho đến khi có đủ đối thủ/người cần tìm.

## AC-014: Không góp đủ đúng hạn

- Funding deadline là trước giờ bắt đầu 12 giờ.
- Booking thiếu tiền chuyển `REFUND_PENDING`.
- Refund người tạo bằng 80% khoản đã đóng; 20% được lưu vào `cancellation_fee_amount` làm phí giữ sân cho owner.
- Đối thủ/người ghép đã đóng đúng hạn được refund 100%.
- Booking chỉ chuyển `CANCELLED` sau khi refund bắt buộc thành công.

## AC-015: Owner hủy booking

- Chỉ owner của field được hủy và phải nhập lý do.
- Booking `CONFIRMED` chưa thu tiền có thể chuyển thẳng `CANCELLED`.
- Booking `PARTIALLY_PAID` hoặc `PAID` phải chuyển `REFUND_PENDING`.
- Mọi khoản đã thu được hoàn 100% qua MoMo Sandbox.
- Payment gốc vẫn giữ `SUCCESS`; refund được lưu riêng.
- Refund chưa xong giữ booking `REFUND_PENDING`; hoàn tất mới `CANCELLED`.

## AC-016: Người tham gia rút

- Rút trước giờ bắt đầu trên 12 giờ được refund 100% và mở lại vị trí.
- Rút trong vòng 12 giờ không được refund.
- Khoản không hoàn tiếp tục được tính vào tổng booking.
- No-show không được refund và không tự tạo điểm phạt trong MVP.

## AC-017: Admin giám sát

- Admin xem được account, owner application, venue, booking, contribution, payment, refund và match.
- Admin khóa tài khoản hoặc ẩn venue nhưng không xóa lịch sử giao dịch.
- Secret key và connection string không xuất hiện trên giao diện hoặc log thông thường.

## AC-018: Transaction và đồng thời

- Hai request đồng thời không tạo được hai booking giao nhau cho cùng field.
- Hai payment/IPN đồng thời không làm tổng tiền vượt booking.
- Hai yêu cầu thanh toán vị trí cuối không làm match vượt số chỗ.
- Lỗi commit phải rollback toàn bộ thay đổi liên quan.
- Filtered unique index phải cho phép nhiều mã giao dịch nullable nhưng không cho phép trùng mã đã có hoặc hai payment `SUCCESS` cho cùng contribution.
