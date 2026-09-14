# Tìm đối thủ và tìm thêm người

Tài liệu mô tả hành vi hiện hành của chức năng ghép kèo. Nội dung áp dụng cho
lịch đặt theo chính sách cọc hiện tại (`DEPOSIT_30`).

## Kèo là gì

Kèo là bài đăng gắn với một lịch đặt sân cụ thể. Người tạo kèo là người đã đặt
sân và đã hoặc sẽ đóng phần cọc của mình. Có hai loại kèo:

- **Kèo tìm đối thủ**: cần một đội đối thủ tới đá cùng.
- **Kèo tìm thêm người**: cần thêm người chơi tham gia vào trận.

Danh sách kèo đang mở nằm ở mục Tìm kèo. Người dùng có thể xem chi tiết kèo mà
không cần đăng nhập, nhưng phải đăng nhập mới tham gia được.

## Kèo tìm đối thủ: cách tham gia

Với kèo tìm đối thủ, người tham gia đại diện cho **cả đội đối thủ**, không phải
một cá nhân lẻ. Vì vậy một kèo tìm đối thủ chỉ nhận **một** suất tham gia. Khi
bài đăng ghi còn thiếu 1, nghĩa là còn thiếu một đội đối thủ, không phải còn
thiếu một cầu thủ.

Kèo tìm đối thủ hiện **không cần người tạo kèo duyệt**. Khi bấm tham gia, hệ
thống giữ suất ngay cho người bấm và chuyển sang trạng thái chờ thanh toán.

Người tham gia có **15 phút** để thanh toán phần cọc đối thủ. Nếu giờ bắt đầu
trận tới sớm hơn 15 phút thì hạn thanh toán được rút ngắn về đúng giờ bắt đầu.
Hết hạn mà chưa thanh toán, suất bị hủy và kèo mở lại cho người khác.

Thanh toán thành công thì trạng thái tham gia chuyển sang **Đã tham gia**.

## Kèo tìm thêm người: cách tham gia

Với kèo tìm thêm người, người đặt sân đã đóng toàn bộ khoản cọc 30%. Người tham
gia **không phải thanh toán trực tuyến** khoản nào.

Kèo tìm thêm người vẫn dùng **luồng duyệt**: người dùng gửi yêu cầu tham gia,
sau đó người tạo kèo chấp nhận hoặc từ chối. Được chấp nhận thì trạng thái
chuyển thẳng sang Đã tham gia mà không cần thanh toán.

Số người cần tìm do người đặt sân khai báo lúc đặt sân, và phải nhỏ hơn sức
chứa của sân.

## Bài kèo mở tới khi nào

Bài kèo **không có một mốc hết hạn riêng**. Hệ thống không lưu thời điểm hết hạn
cho bài đăng kèo và không tự gỡ bài theo đồng hồ đếm ngược.

Một bài kèo ngừng nhận người mới khi xảy ra một trong các việc sau:

- đã tới **giờ bắt đầu** của lịch đặt sân, hoặc
- người tạo kèo chủ động đóng bài tìm đối thủ, hoặc
- kèo đã đủ người hoặc đã có đối thủ thanh toán thành công, hoặc
- kèo bị hủy, hoặc lịch đặt sân gắn với kèo bị hủy hay hết hiệu lực.

Vì vậy, khi người dùng hỏi "kèo này khi nào hết hạn", câu trả lời đúng là nêu
**thời gian diễn ra trận** và **trạng thái hiện tại của kèo**, đồng thời nói rõ
hệ thống không có mốc hết hạn riêng cho bài kèo.

## Hạn 15 phút không phải là hạn của bài kèo

Đây là hai thứ hoàn toàn khác nhau và rất dễ nhầm:

- **Hạn giữ suất 15 phút**: chỉ áp dụng cho một người vừa bấm nhận kèo tìm đối
  thủ. Hết 15 phút mà người đó chưa thanh toán thì **suất của riêng người đó**
  bị hủy, còn bài kèo vẫn mở lại cho người khác.
- **Thời điểm bài kèo đóng**: là giờ bắt đầu của lịch đặt sân, như mô tả ở mục
  trên.

Không dùng hạn 15 phút để trả lời câu hỏi về thời điểm diễn ra trận hay thời
điểm bài kèo kết thúc.

## Không tìm được đối thủ thì sao

Nếu tới giờ mà không có đội nào nhận kèo, **lịch đặt sân vẫn có hiệu lực**. Hệ
thống không tự hủy lịch đặt chỉ vì thiếu đối thủ, và không tự hoàn lại phần cọc
của người tạo kèo.

Người tạo kèo vẫn giữ khung giờ đã đặt và vẫn trả phần tiền còn lại tại sân như
bình thường. Người tạo kèo cũng có thể chủ động đóng bài tìm đối thủ; việc đó
chỉ dừng việc nhận đối thủ mới, còn lịch đặt sân và toàn bộ tiền đã đóng vẫn
giữ nguyên.

## Rút khỏi kèo

Người đang tham gia có thể báo rút trước giờ bắt đầu trận. Sau khi trận đã bắt
đầu thì không báo rút được nữa.

Chính sách hiện hành: **người chủ động rút khỏi kèo không được hoàn lại phần
cọc đã đóng.** Khoản tiền đó bị mất.

Trường hợp kèo tìm thêm người thì người tham gia vốn không đóng tiền trực tuyến,
nên việc rút không kéo theo hậu quả tài chính nào.

Một số lịch đặt cũ theo chính sách trước đây có quy tắc hoàn tiền khi rút sớm
hơn 12 giờ. Quy tắc đó **không áp dụng** cho lịch đặt mới.

## Đối thủ thay thế

Khi một đối thủ đã thanh toán rồi rút khỏi kèo, phần cọc của họ bị mất nhưng
vẫn nằm lại trong lịch đặt. Lúc đó nghĩa vụ đóng cọc của vị trí đối thủ coi như
đã được thực hiện đủ.

Vì vậy, trong trường hợp này **người nhận kèo thay thế có thể tham gia ngay mà
không phải đóng thêm 15% nữa**. Giao diện kèo sẽ cho biết có cần thanh toán hay
không trước khi người dùng bấm tham gia.

Đây không phải quy tắc chung cho mọi đối thủ: đối thủ đầu tiên của một kèo tìm
đối thủ vẫn phải đóng phần cọc của mình.

## Trạng thái yêu cầu tham gia

- **Chờ duyệt**: đã gửi yêu cầu, đang đợi người tạo kèo quyết định (kèo tìm
  thêm người).
- **Đã nhận suất, chờ thanh toán**: đã giữ chỗ, đang trong hạn thanh toán (kèo
  tìm đối thủ).
- **Đã tham gia**: chính thức có mặt trong kèo.
- **Bị từ chối**: người tạo kèo không chấp nhận yêu cầu.
- **Đã hết hạn**: quá hạn thanh toán hoặc đã qua giờ bắt đầu trận.
- **Đã rút**: tự báo rút khỏi kèo.

## Số điện thoại liên hệ

Khi tham gia kèo hoặc khi tạo kèo, người dùng cần chia sẻ một số điện thoại
liên hệ để hai bên liên lạc. Số này được lưu vào hồ sơ người dùng.

Danh sách người tham gia kèo cùng số liên hệ của họ chỉ hiển thị cho người tạo
kèo. Số liên hệ chỉ được hiển thị trong khi lịch đặt sân đã có tiền cọc và chưa
qua giờ kết thúc; sau đó trang kèo báo thông tin liên hệ không còn được hiển
thị nữa.
