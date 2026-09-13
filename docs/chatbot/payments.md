# Thanh toán

Tài liệu mô tả hành vi hiện hành của chức năng thanh toán khoản cọc.

## Thanh toán trực tuyến chỉ dành cho khoản cọc

Hệ thống chỉ thu **khoản cọc 30%** qua thanh toán trực tuyến. Phần tiền còn lại
của tổng tiền sân được trả trực tiếp tại sân cho chủ sân, không đi qua hệ thống.

Mỗi khoản phải đóng của một lịch đặt là một mục riêng. Người dùng chỉ thanh
toán được đúng khoản đã gán cho mình; không thanh toán hộ khoản của người khác.

## Các hình thức thanh toán

- **Thanh toán mô phỏng**: hình thức dành cho môi trường phát triển và trình
  diễn, ghi nhận thành công ngay lập tức và không gọi ra ngoài Internet.
- **VNPAY Sandbox**: cổng thanh toán thật ở môi trường thử nghiệm. Chỉ hoạt
  động khi quản trị viên đã bật VNPAY trong cấu hình và đã khai báo thông tin
  đơn vị chấp nhận thanh toán.
- **MoMo**: là tích hợp cũ và đã bị **vô hiệu hóa vĩnh viễn ở mức mã nguồn**.
  Người dùng không chọn được MoMo, kể cả khi cấu hình môi trường có khai báo.

## Luồng thanh toán VNPAY

1. Người dùng bấm thanh toán khoản cọc của mình.
2. Hệ thống tạo một giao dịch ở trạng thái **Đang chờ** và sinh đường dẫn thanh
   toán VNPAY đã được ký.
3. Trình duyệt chuyển sang trang VNPAY để người dùng trả tiền.
4. VNPAY gọi ngược về hệ thống theo hai đường: trả trình duyệt về trang kết
   quả, và gửi thông báo máy chủ tới máy chủ (IPN).
5. Hệ thống kiểm tra chữ ký, đối chiếu mã đơn hàng và đối chiếu số tiền.
6. Nếu hợp lệ và VNPAY báo thành công, giao dịch chuyển sang **Thành công**.

**Trang kết quả trên trình duyệt không quyết định giao dịch thành công.** Trang
đó chỉ hiển thị tình trạng để người dùng theo dõi. Chỉ thông báo máy chủ tới
máy chủ đã được xác thực mới làm thay đổi trạng thái tiền. Nếu trang kết quả
báo đang chờ xác nhận, người dùng chỉ cần tải lại trang sau ít phút.

Đường dẫn thanh toán VNPAY có hạn hiệu lực mặc định khoảng 15 phút.

## Điều gì xảy ra khi thanh toán thành công

Khi một khoản cọc được ghi nhận thành công:

- Khoản đóng góp đó chuyển sang **Đã thanh toán**.
- Số tiền đã thanh toán của lịch đặt tăng thêm đúng số tiền vừa nhận.
- Lịch đặt chuyển sang **Đã thanh toán** nếu đã đủ khoản cọc, hoặc **Đã thanh
  toán một phần** nếu chưa đủ.
- Nếu khoản vừa trả là phần cọc của đối thủ đang chờ thanh toán thì người đó
  được chuyển sang trạng thái **Đã tham gia** kèo.

Mỗi khoản đóng góp chỉ có duy nhất một giao dịch thành công. Hệ thống chặn ở
mức cơ sở dữ liệu để không ghi nhận hai lần cho cùng một khoản.

## Xử lý trùng lặp và báo về muộn

Thông báo từ VNPAY có thể tới nhiều lần cho cùng một giao dịch. Hệ thống xử lý
theo nguyên tắc chỉ có tác dụng một lần: lần báo thứ hai không tạo thêm bất kỳ
thay đổi tiền bạc nào.

Nếu VNPAY báo thành công **sau khi** khoản đóng góp đã hết hạn hoặc lịch đặt đã
đổi trạng thái, hệ thống vẫn ghi nhận giao dịch đó để giữ lịch sử, rồi đưa vào
hàng đợi hoàn tiền, thay vì âm thầm bỏ qua tiền của người dùng.

## Trả phần cọc còn thiếu

Ở một số lịch đặt cũ theo hình thức Tìm đối thủ, người đặt sân có thể trả nốt
phần cọc mà đối thủ chưa đóng. Chức năng này phụ thuộc các mốc thời hạn của
chính sách cũ và **không áp dụng cho lịch đặt mới**.

## Giao dịch thanh toán và giao dịch hoàn tiền là hai bản ghi riêng

Một giao dịch thanh toán đã thành công **không bao giờ bị sửa thành đã hoàn
tiền**. Khi có hoàn tiền, hệ thống tạo một bản ghi hoàn tiền riêng trỏ về giao
dịch gốc. Giao dịch thanh toán vẫn giữ nguyên trạng thái Thành công như lịch sử
vĩnh viễn.
