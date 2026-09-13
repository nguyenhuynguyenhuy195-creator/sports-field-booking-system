# Đặt sân và tiền cọc

Tài liệu mô tả hành vi hiện hành của chức năng đặt sân, dùng làm kiến thức cho
trợ lý ảo. Mọi nội dung ở đây mô tả chính sách đặt cọc hiện tại (payment_policy
`DEPOSIT_30`) áp dụng cho lịch đặt mới.

## Ba hình thức đặt sân

Khi đặt sân, người dùng chọn một trong ba hình thức:

- **Đặt sân trực tiếp (DIRECT_BOOKING)**: chơi với nhóm của mình, không đăng
  kèo tìm người.
- **Tìm đối thủ (FIND_OPPONENT)**: đã có đội của mình, cần tìm một đội đối thủ.
- **Tìm thêm người (FIND_PLAYERS)**: cần tìm thêm người chơi vào cùng một đội
  hoặc cùng một trận.

Hình thức đặt sân được chọn lúc tạo lịch đặt và quyết định cách chia tiền cọc.
Chỉ hình thức Tìm đối thủ và Tìm thêm người mới tạo được bài đăng kèo.

## Tiền cọc là bao nhiêu

Tiền cọc của một lịch đặt sân mới luôn là **30% tổng tiền sân**, làm tròn lên
hoặc xuống tới đồng VND gần nhất (làm tròn nửa lên). Hệ thống tự tính, người
dùng không tự nhập số tiền cọc.

Phần còn lại của tổng tiền sân **không thanh toán trực tuyến**. Người chơi trả
trực tiếp tại sân cho chủ sân.

Ví dụ: tổng tiền sân 500.000 VND thì tiền cọc là 150.000 VND, phần trả tại sân
là 350.000 VND.

## Ai đóng tiền cọc

Cách chia khoản cọc 30% phụ thuộc hình thức đặt sân:

- **Đặt sân trực tiếp**: người đặt sân đóng toàn bộ khoản cọc 30%.
- **Tìm thêm người**: người đặt sân đóng toàn bộ khoản cọc 30%. Người tham gia
  kèo **không** phải thanh toán trực tuyến khoản nào.
- **Tìm đối thủ**: khoản cọc 30% được chia đôi giữa người tạo kèo và đội đối
  thủ. Mỗi bên đóng khoảng 15% tổng tiền sân.

Với hình thức Tìm đối thủ, nếu khoản cọc là số lẻ không chia hết cho hai thì
người tạo kèo đóng phần nhỏ hơn và đối thủ đóng phần lớn hơn. Ví dụ khoản cọc
150.001 VND sẽ chia thành 75.000 VND cho người tạo kèo và 75.001 VND cho đối
thủ.

## Thời hạn thanh toán khoản cọc đầu tiên

Ngay sau khi tạo, lịch đặt sân ở trạng thái **Đã xác nhận** và giữ khung giờ
đó. Người đặt sân có **15 phút** để thanh toán phần cọc của mình.

Nếu hết 15 phút mà chưa có đồng nào được thanh toán cho lịch đặt, lịch đặt
chuyển sang trạng thái **Đã hết hạn** và khung giờ được trả lại cho người khác
đặt. Không có cách gia hạn thời gian này; người dùng cần đặt lại lịch mới.

## Các trạng thái của lịch đặt sân

- **Đã xác nhận**: vừa tạo, đang giữ chỗ, chưa thanh toán khoản cọc nào.
- **Đã thanh toán một phần**: đã nhận được một phần khoản cọc, nhưng chưa đủ.
  Thường gặp ở hình thức Tìm đối thủ khi mới có người tạo kèo đóng tiền.
- **Đã thanh toán**: đã nhận đủ toàn bộ khoản cọc 30%.
- **Đã hết hạn**: quá 15 phút mà không ai thanh toán.
- **Đã hủy**: người đặt sân hoặc chủ sân đã hủy lịch.
- **Chờ hoàn tiền**: đang trong quá trình hoàn tiền.
- **Đã hoàn tất**: đã qua giờ kết thúc và lịch đặt hợp lệ.

## Hai con số tiền khác nhau

Trên trang chi tiết lịch đặt có hai con số dễ nhầm lẫn:

- **Khoản cọc còn thiếu**: phần của khoản cọc 30% chưa được đóng. Đây là số
  tiền còn phải thanh toán trực tuyến.
- **Số tiền trả tại sân**: tổng tiền sân trừ đi số tiền đã thanh toán trực
  tuyến. Đây là số tiền trả cho chủ sân khi tới chơi.

Hai con số này không giống nhau. Khi khoản cọc đã đóng đủ thì khoản cọc còn
thiếu bằng 0, nhưng số tiền trả tại sân vẫn còn khoảng 70% tổng tiền sân.

Ngoài ra, số tiền "đã thanh toán" của một lịch đặt là tổng tiền của tất cả mọi
người đóng vào lịch đặt đó, không phải riêng số tiền của một người.

## Khi nào lịch đặt được tính là hoàn tất

Sau khi qua giờ kết thúc, lịch đặt đã thanh toán đủ khoản cọc sẽ chuyển sang
**Đã hoàn tất**.

Lịch đặt hình thức Tìm đối thủ mới chỉ thanh toán một phần khoản cọc cũng được
tính là hoàn tất, miễn là đã có tiền cọc được đóng. Đây là lý do một kèo không
tìm được đối thủ vẫn giữ được sân và vẫn kết thúc bình thường.

## Sân bị trùng giờ hoặc đang bảo trì

Hệ thống không cho đặt trùng khung giờ với một lịch đặt đang giữ chỗ khác trên
cùng một sân, và không cho đặt vào khung giờ mà chủ sân đã khóa để bảo trì.
Người dùng cần chọn khung giờ khác hoặc sân khác.
