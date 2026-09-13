# Hủy lịch và hoàn tiền

Tài liệu mô tả hành vi hiện hành khi hủy lịch đặt sân và khi hoàn tiền. Nội
dung áp dụng cho lịch đặt theo chính sách cọc hiện tại (`DEPOSIT_30`).

## Người đặt sân tự hủy lịch

Người đặt sân hủy được lịch của mình **bất cứ lúc nào trước giờ bắt đầu**. Sau
khi trận đã bắt đầu thì không hủy trên hệ thống được nữa.

Chính sách hiện hành khi người đặt sân chủ động hủy:

- **Phần cọc do chính người đặt sân đã đóng sẽ bị mất**, không được hoàn lại.
  Khoản này được ghi nhận là phí hủy.
- **Phần cọc do đối thủ đã đóng được hoàn lại 100%**.
- Phần cọc mà đối thủ trước đó đã bị mất do tự rút thì không được hoàn lại lần
  nữa.

Nếu người đặt sân hủy khi **chưa thanh toán đồng nào**, thì không mất gì cả:
lịch đặt chỉ đơn giản được hủy.

Lịch đặt theo chính sách cũ có thêm điều kiện phải hủy trước giờ bắt đầu ít
nhất 2 giờ. Điều kiện đó **không áp dụng cho lịch đặt mới**.

## Chủ sân hủy lịch

Khi chủ sân hủy lịch đặt vì sự cố, lịch được hủy ngay và **toàn bộ số tiền đã
thu được hoàn lại 100%** cho từng người đã đóng, kể cả người đặt sân. Không có
phí hủy trong trường hợp này.

Ngoại lệ duy nhất: phần cọc mà một người tham gia đã tự làm mất do rút khỏi kèo
trước đó thì không được khôi phục thành khoản hoàn tiền.

Chủ sân bắt buộc phải nhập lý do hủy, và lý do đó hiển thị cho người đặt sân.

## Hoàn tiền diễn ra như thế nào

Việc hủy lịch và việc hoàn tiền là hai bước tách rời. Lịch đặt được hủy ngay
lập tức, khung giờ được trả lại, kèo được đóng — **không chờ tiền về tài khoản
mới thực hiện các việc đó**.

Bản ghi hoàn tiền có các trạng thái:

- **Đang chờ**: đã tạo yêu cầu, chưa gửi tới cổng thanh toán.
- **Đang xử lý**: đã gửi tới cổng thanh toán, đang đợi kết quả.
- **Thành công**: cổng thanh toán xác nhận đã hoàn tiền.
- **Thất bại**: cổng thanh toán từ chối; yêu cầu có thể được thử lại.

Khoản hoàn tiền qua VNPAY là **không đồng bộ** và có thể nằm ở trạng thái đang
chờ hoặc đang xử lý trong một khoảng thời gian. Thời gian tiền thực sự về tài
khoản phụ thuộc ngân hàng và VNPAY, không do hệ thống quyết định.

Khoản hoàn tiền của hình thức thanh toán mô phỏng được ghi nhận thành công ngay.

Số tiền đã thanh toán của lịch đặt chỉ giảm xuống **khi khoản hoàn tiền đạt
trạng thái Thành công**, không giảm ngay lúc tạo yêu cầu hoàn tiền.

## Rút khỏi kèo thì có được hoàn tiền không

Không. Theo chính sách hiện hành, người **chủ động rút** khỏi kèo sau khi đã
thanh toán sẽ mất phần cọc đã đóng.

Việc được hoàn tiền chỉ xảy ra khi người khác hủy lịch: người đặt sân hủy (đối
thủ được hoàn 100%) hoặc chủ sân hủy (mọi người được hoàn 100%).

Một số lịch đặt cũ theo chính sách trước đây cho hoàn tiền nếu rút sớm hơn 12
giờ trước giờ bắt đầu. Đó là quy tắc lịch sử, **không áp dụng cho lịch đặt mới**.

## Chính sách cũ về thiếu tiền cọc

Các lịch đặt cũ theo hình thức Tìm đối thủ có mốc hạn đóng đủ tiền. Khi quá hạn
mà vẫn thiếu, lịch bị hủy và áp dụng tỷ lệ hoàn 80% cho người tạo kèo, 100% cho
những người đóng khác, phần 20% còn lại được giữ làm phí.

Đây là **chính sách lịch sử**. Lịch đặt mới không có mốc hạn đóng đủ tiền nên
không rơi vào trường hợp này.

## Xem tình trạng hoàn tiền ở đâu

Trang chi tiết lịch đặt sân hiển thị các khoản hoàn tiền liên quan tới lịch đặt
đó. Trong trang chi tiết kèo, mỗi người chỉ nhìn thấy khoản hoàn tiền của chính
mình, không thấy giao dịch của người khác trong kèo.
