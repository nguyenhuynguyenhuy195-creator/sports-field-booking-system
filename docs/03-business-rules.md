# 3. Quy tắc nghiệp vụ

## 3.1. Tài khoản, phân quyền và liên hệ

### BR-001: Đăng nhập trước khi thao tác

User phải đăng nhập trước khi tạo booking, tạo kèo, gửi yêu cầu tham gia hoặc thanh toán.

### BR-002: Phân quyền backend

- USER không được truy cập chức năng OWNER hoặc ADMIN.
- OWNER không được truy cập chức năng ADMIN.
- Không dựa vào việc ẩn nút trên frontend để bảo vệ chức năng.

### BR-003: Yêu cầu trở thành owner

- Tài khoản mới luôn có role USER.
- User có tối đa một yêu cầu trở thành owner đang PENDING.
- Chỉ admin được chấp nhận hoặc từ chối.
- Role chỉ chuyển thành OWNER khi yêu cầu được chấp nhận.

### BR-004: Quyền sở hữu

- Owner chỉ quản lý venue có owner_id của mình.
- Owner chỉ quản lý field, giá, bảo trì và booking thuộc venue của mình.

### BR-005: Khóa tài khoản và lịch sử

- Tài khoản LOCKED không được đăng nhập hoặc tạo giao dịch mới.
- Không xóa vật lý lịch sử booking, payment, contribution, refund hoặc match đã phát sinh.
- Dữ liệu đã được tham chiếu phải chuyển trạng thái thay vì cascade delete.

### BR-006: Số điện thoại dùng Zalo

- Yêu cầu tham gia kèo FIND_PLAYERS bắt buộc có số điện thoại liên hệ hợp lệ.
- Số có thể lấy sẵn từ tài khoản nhưng user phải kiểm tra và đồng ý chia sẻ khi gửi yêu cầu.
- Số điện thoại không xuất hiện trên danh sách/chi tiết kèo công khai.
- Chỉ creator của match được xem số sau khi yêu cầu đã được chấp nhận.
- Giao diện không tiếp tục hiển thị số sau khi booking hoàn thành hoặc bị hủy.

## 3.2. Bộ môn, venue, field, giá và bảo trì

### BR-007: Danh mục thể thao

- MVP chỉ có FOOTBALL, BADMINTON, PICKLEBALL và TENNIS.
- Danh mục do hệ thống seed và quản lý; owner không tự thêm sport hoặc field type.
- Field type thuộc đúng một sport.
- Bóng đá có FOOTBALL_5, FOOTBALL_7 và FOOTBALL_11.
- Ba môn dùng vợt dùng loại sân STANDARD trong MVP.

### BR-008: Mỗi field thuộc một bộ môn

- Mỗi field bắt buộc tham chiếu đúng một field type.
- Sport của field được suy ra qua field type; một field không phục vụ đồng thời nhiều sport.
- Một venue có thể chứa nhiều field thuộc nhiều sport.
- Field mới mặc định INACTIVE và chỉ field ACTIVE thuộc venue ACTIVE mới nhận booking.
- Không được đổi field type sau khi field đã có booking; owner phải chuyển field cũ INACTIVE và tạo field mới để không làm sai lịch sử.

### BR-009: Duyệt venue và vị trí

- Venue mới có trạng thái PENDING.
- Chỉ venue ACTIVE mới hiển thị công khai.
- Admin có thể chuyển venue thành ACTIVE hoặc HIDDEN.
- Venue mới phải có tỉnh/thành phố, phường/xã và địa chỉ chi tiết hợp lệ trước khi được duyệt ACTIVE.
- Place ID và tọa độ cũ không còn là điều kiện duyệt; dữ liệu legacy vẫn được giữ nguyên.

### BR-010: Tìm kiếm và lọc venue

- Từ khóa tìm trên tên, địa chỉ chi tiết, phường/xã/đặc khu và tỉnh/thành phố; venue legacy chưa chuẩn hóa vẫn có fallback đọc `district/city`.
- Khoảng trắng được chuẩn hóa; ký tự wildcard phải được hiểu như văn bản thường.
- Chỉ trả venue ACTIVE có ít nhất một field ACTIVE.
- Bộ lọc sport, field type và khoảng giá được kết hợp đồng thời.
- “Giá từ” là hourly_price thấp nhất của price slot ACTIVE trên field ACTIVE còn phù hợp với bộ lọc.
- Giá tối thiểu không được lớn hơn giá tối đa; điều kiện được giữ khi chuyển trang.

### BR-011: Bản đồ và chỉ đường ngoài hệ thống

- Nút chỉ đường mở Google Maps bằng địa chỉ đầy đủ hiện tại.
- Hệ thống nhúng Leaflet cho Venue có tọa độ hợp lệ nhưng không tự tính tuyến đường và không dùng Google Maps/Places API.
- `Sân gần tôi` chỉ dùng browser geolocation theo thao tác người dùng, tính khoảng cách Haversine tới Venue nội bộ và không lưu vị trí người dùng.
- Kết quả tìm kiếm chỉ gồm venue nội bộ đã ACTIVE.

### BR-012: Khung giá

- Giá cấu hình theo field, ngày trong tuần và khoảng giờ.
- Hai khung giá ACTIVE cùng field/cùng ngày không được chồng nhau.
- start_time phải nhỏ hơn end_time và hourly_price phải lớn hơn 0.
- Không dùng base_price thay thế khi thiếu cấu hình.

### BR-013: Tính giá booking

- Toàn bộ thời gian booking phải được phủ bởi price slot ACTIVE.
- Booking qua nhiều khung giá được tách thành các đoạn và cộng subtotal.
- Backend lấy giá từ database và lưu snapshot; không tin giá hoặc tổng tiền từ frontend.

### BR-014: Lịch bảo trì

- Owner tạo bảo trì theo field, ngày và khoảng giờ.
- Hai lịch ACTIVE cùng field không được chồng nhau.
- Không tạo bảo trì giao với booking đang chiếm chỗ.
- Booking không được giao với bảo trì còn hiệu lực.

## 3.3. Thời gian, hình thức thi đấu và trùng lịch

### BR-015: Thời gian booking

- start_time phải nhỏ hơn end_time và không đi qua nửa đêm.
- Bước thời gian là 30 phút; thời lượng tối thiểu 60 phút.
- Booking nằm trong giờ mở cửa venue và không quá 30 ngày.
- Lưới giờ chỉ mang tính tư vấn; backend kiểm tra lại khi quote và khi tạo.

### BR-016: Thời gian đặt trước

- DIRECT_BOOKING, FIND_PLAYERS và FIND_OPPONENT đều phải tạo trước giờ bắt đầu ít nhất 60 phút.
- Bài FIND_OPPONENT được nhận yêu cầu đến giờ booking bắt đầu; không có deadline riêng trước 12 giờ.

### BR-017: Cấu hình booking hiện tại

- Booking mới không hỏi, không validate và không suy diễn `play_format`; service luôn lưu `NULL`.
- Cột và enum `play_format` tiếp tục tồn tại ở schema để đọc dữ liệu legacy, không được dùng để quyết định booking mode mới.
- Mọi field hỗ trợ DIRECT_BOOKING, FIND_OPPONENT và FIND_PLAYERS nếu các rule thời gian tương ứng hợp lệ.
- FIND_PLAYERS yêu cầu `1 <= requested_players < field.capacity`.

### BR-018: Trùng lịch

Một field không có hai booking chiếm chỗ giao nhau:

> new_start < existing_end AND new_end > existing_start

Trạng thái chiếm chỗ: CONFIRMED, PARTIALLY_PAID, PAID và REFUND_PENDING.

Trạng thái không chiếm chỗ: REJECTED, CANCELLED, EXPIRED và COMPLETED.

Kiểm tra và tạo booking phải nằm trong cùng transaction.

## 3.4. Vòng đời booking và tiền cọc

### BR-019: Ba booking mode

- DIRECT_BOOKING: creator chịu toàn bộ khoản cọc.
- FIND_OPPONENT: creator và đối thủ mỗi bên chịu một nửa khoản cọc.
- FIND_PLAYERS: creator chịu toàn bộ khoản cọc; người ghép trả tại sân.
- booking_mode mô tả mục đích đặt sân, không phải cổng thanh toán.
- FIND_PLAYERS bắt buộc snapshot `requested_players` ngay trên booking để giữ lựa chọn trước khi match được mở.

### BR-020: Tính khoản cọc

- deposit_rate của MVP là 30% tổng tiền sân.
- deposit_amount được backend tính, làm tròn đến đồng và lưu snapshot khi tạo booking.
- Booking mới dùng payment_policy DEPOSIT_30. Booking cũ được gắn LEGACY_FULL_ONLINE để lịch sử thanh toán toàn bộ không bị diễn giải thành cọc.
- paid_amount chỉ theo dõi khoản cọc online ròng sau refund và không vượt deposit_amount.
- Số còn lại tại sân bằng total_amount trừ paid_amount thực thu ròng; hệ thống chỉ hiển thị, không thu hoặc xác nhận phần này.
- DIRECT_BOOKING/FIND_PLAYERS đủ cọc 30% nên còn 70% tại sân.
- FIND_OPPONENT chỉ có cọc creator 15% vẫn là booking hợp lệ và còn 85% tại sân; nếu đối thủ trả thêm 15% thì còn 70% tại sân.

### BR-021: Tạo và giữ chỗ tự động

- Backend kiểm tra field/venue, sport, play format, thời gian, bảo trì, trùng lịch và giá.
- Booking hợp lệ tạo ở CONFIRMED và giữ chỗ 15 phút.
- initial_payment_due_at bằng thời điểm tạo cộng 15 phút.
- Owner không duyệt booking thông thường; chỉ theo dõi hoặc hủy khi có sự cố.

### BR-022: Khoản cọc đầu tiên

- DIRECT_BOOKING và FIND_PLAYERS: creator phải thanh toán đủ deposit_amount trong 15 phút.
- FIND_OPPONENT: creator thanh toán 50% deposit_amount trong 15 phút.
- CONFIRMED chưa có khoản cọc đầu tiên sau 15 phút chuyển EXPIRED.
- FIND_OPPONENT chuyển PARTIALLY_PAID ngay khi creator trả 15%; đây là trạng thái đã giữ sân hợp lệ, không phải trạng thái sắp bị hủy vì thiếu cọc.
- Khi đối thủ trả phần còn lại, booking chuyển PAID.
- Trạng thái PAID trong MVP nghĩa là đã hoàn thành nghĩa vụ cọc online, không có nghĩa 70% tại sân đã được ghi nhận.

### BR-023: Thời gian tồn tại của bài tìm đối thủ

- Match FIND_OPPONENT mở sau khi creator thanh toán thành công 15% tổng tiền sân.
- Bài tồn tại đến giờ booking bắt đầu, trừ khi creator chủ động đóng hoặc đã có đối thủ thanh toán thành công.
- Đối thủ bấm nhận kèo được tự động giữ suất thanh toán tối đa 15 phút; payment_due_at bằng thời điểm sớm hơn giữa `claimed_at + 15 phút` và giờ booking bắt đầu, không cần creator duyệt.
- Đến giờ booking bắt đầu, service từ chối nhận suất/payment mới, làm hết hạn suất ACCEPTED_AWAITING_PAYMENT chưa trả và không còn trả bài trong danh sách kèo đang mở.
- Không có matchmaking_deadline trước 12 giờ, funding_deadline hoặc cửa sổ creator top-up đối với booking mới.

### BR-024: Không tìm được đối thủ

- Không tìm được đối thủ không làm hủy booking và không tạo refund.
- Khoản creator đã cọc 15% tiếp tục giữ sân; booking có thể giữ PARTIALLY_PAID cho đến khi COMPLETED.
- Creator có thể dùng sân cho đội mình, tự tìm đối thủ bên ngoài và thanh toán 85% còn lại tại sân.
- Việc bài hết hiệu lực lúc trận bắt đầu không thay đổi trạng thái chiếm chỗ của booking.

### BR-025: Hủy booking

- User được chủ động hủy booking của mình trước giờ bắt đầu; CONFIRMED chưa thu tiền chuyển thẳng CANCELLED.
- Người chủ động hủy/rút hoặc no-show không được hoàn phần cọc của chính mình. Payment gốc vẫn SUCCESS và contribution đã đóng chuyển FORFEITED khi phù hợp.
- DIRECT_BOOKING/FIND_PLAYERS đã cọc mà creator hủy: toàn bộ khoản creator đã đóng được giữ lại và booking chuyển CANCELLED, không tạo refund.
- FIND_OPPONENT mà creator hủy: creator mất 15% đã cọc. Nếu đối thủ đã cọc thì đối thủ được hoàn 100%; booking giữ REFUND_PENDING đến khi refund này thành công rồi mới CANCELLED.
- Đại diện đối thủ đã cọc mà chủ động rút/no-show: mất phần cọc 15%; vị trí đối thủ mở lại nhưng khoản đã thu tiếp tục tính vào booking và người thay thế không bị thu cọc lần hai.
- Owner được hủy CONFIRMED, PARTIALLY_PAID hoặc PAID khi có sự cố và bắt buộc nhập lý do.
- Owner hủy booking đã thu cọc phải hoàn 100% mọi khoản đã thu.
- Thanh toán trùng/sai do hệ thống phải hoàn 100% khoản bị ảnh hưởng.

### BR-026: Hoàn thành

Booking PAID hoặc FIND_OPPONENT PARTIALLY_PAID hợp lệ được chuyển COMPLETED sau khi thời gian sử dụng kết thúc. MVP không yêu cầu owner xác nhận số còn lại thanh toán tại sân.

Mốc cộng 30 phút không trì hoãn lifecycle Booking; mốc này chỉ được dùng để
xác định thời điểm đủ điều kiện Settlement sớm nhất theo ADR-037.

## 3.5. MoMo Sandbox, contribution và refund

### BR-027: Ranh giới provider

- MoMo Sandbox dùng trong bản trình diễn, không có tiền thật.
- MOCK dùng cho phát triển/test và áp dụng cùng quy tắc số tiền nhưng không gọi MoMo.
- MoMo Production, QR ngân hàng thật, ví admin và payout tiền thật không thuộc
  MVP. Phase 2.6 chỉ cho phép simulated payout theo ADR-037.

### BR-028: Phân bổ contribution

- Tổng amount_due mục tiêu của contribution phải bằng deposit_amount, không phải total_amount; paid_amount có thể thấp hơn deposit_amount đối với FIND_OPPONENT không có đối thủ.
- DIRECT_BOOKING/FIND_PLAYERS tạo một contribution CREATOR bằng toàn bộ deposit_amount.
- FIND_OPPONENT tạo CREATOR và OPPONENT, mỗi contribution bằng 50% deposit_amount; phần cuối được điều chỉnh nếu làm tròn.
- FIND_PLAYERS không tạo contribution PLAYER cho người ghép.
- Contribution PLAYER cũ chỉ được giữ để bảo toàn lịch sử migration, service mới không tạo thêm.

### BR-029: Xác nhận kết quả MoMo

- Amount lấy từ contribution trong database.
- Redirect chỉ dùng hiển thị; chỉ IPN hợp lệ mới cập nhật SUCCESS.
- Backend xác minh HMAC và đối chiếu orderId, requestId, amount và partnerCode.
- IPN, query và refund phải idempotent.
- Payment thành công, contribution, booking và match participant liên quan cập nhật trong transaction phù hợp.

### BR-030: Hoàn tiền

- Refund không ghi đè payment SUCCESS; mỗi lần hoàn là bản ghi riêng.
- Không hoàn vượt số tiền payment gốc.
- Không tạo refund cho bên chủ động hủy/rút hoặc no-show.
- Owner hủy: hoàn 100% khoản cọc đã thu.
- Creator hủy FIND_OPPONENT sau khi đối thủ đã cọc: chỉ hoàn 100% payment của đối thủ; creator mất phần của mình.
- Thanh toán trùng/sai do hệ thống: hoàn 100% khoản bị ảnh hưởng.
- Refund chưa xong giữ booking ở REFUND_PENDING.
- Chỉ chuyển CANCELLED sau khi các refund bắt buộc SUCCESS.

## 3.6. Tìm đối thủ và tìm thêm người

### BR-031: Tạo match

- Creator phải sở hữu booking và mỗi booking có tối đa một match.
- booking_mode FIND_OPPONENT chỉ tạo match FIND_OPPONENT.
- booking_mode FIND_PLAYERS chỉ tạo match FIND_PLAYERS.
- Match chỉ mở sau khi khoản cọc creator tương ứng đã thành công.
- Không tạo match cho booking đã hủy, hết hạn, chờ refund hoặc hoàn thành.
- Match FIND_OPPONENT không còn được nhận yêu cầu từ thời điểm booking bắt đầu, kể cả khi job hết hạn chưa chạy.
- Creator phải nhập số Zalo hợp lệ và đồng ý chia sẻ; hệ thống lưu snapshot riêng trên match thay vì tự động công khai số hồ sơ.

### BR-032: Tìm đối thủ

- Một đại diện bấm nhận kèo thay cho phía đối thủ.
- Creator không được tham gia match của chính mình.
- Service khóa match/contribution và chỉ cho một đối thủ giữ suất thanh toán tại một thời điểm; creator không chấp nhận hoặc từ chối đối thủ của booking mới.
- Participant chuyển thẳng `ACCEPTED_AWAITING_PAYMENT` với thời hạn tối đa 15 phút; payment thành công chuyển `JOINED` và match `CONFIRMED`.
- Đối thủ chỉ chính thức JOINED/CONFIRMED sau khi payment cọc SUCCESS, trừ khi phần đối thủ đã được một người rút trước đó để lại và booking không còn nghĩa vụ cọc chưa thanh toán.
- Booking legacy có deadline tiếp tục dùng bước creator duyệt để không đổi hồi tố dữ liệu đang diễn ra.
- Đối thủ đã cọc mà chủ động rút chuyển WITHDRAWN/FORFEITED, bài mở lại và người thay thế không thanh toán lại cùng phần cọc.
- FIND_OPPONENT dùng được cho mọi field thuộc bộ môn đang được MVP hỗ trợ.
- Đại diện đối thủ phải nhập số Zalo và đồng ý chia sẻ trước khi giữ suất thanh toán; số được lưu snapshot trên participant.
- Chỉ khi participant `JOINED` và booking chưa kết thúc/hủy, creator và participant mới xem được số của nhau; khách và user không liên quan không được nhận dữ liệu này.
- Participant `JOINED` thấy kèo trong lịch cá nhân nhưng không trở thành chủ booking và không có quyền sửa/hủy booking.

### BR-033: Tìm thêm người

- required_players là số vị trí creator muốn tìm và không tính creator.
- Không chấp nhận vượt required_players; giá trị snapshot phải thỏa `1 <= required_players < field.capacity`.
- Người ghép không có contribution, payment_due_at hoặc refund online.
- Khi creator chấp nhận, participant chuyển thẳng JOINED.
- Người ghép thanh toán trực tiếp cho creator tại sân.
- Match chuyển FULL khi số participant JOINED đạt required_players.

### BR-034: Rút khỏi kèo FIND_PLAYERS

- Participant có thể rút trước khi booking bắt đầu; trạng thái chuyển WITHDRAWN và vị trí mở lại.
- Vì participant chưa thanh toán online nên không tạo refund.
- Việc liên hệ, xác nhận và thu tiền tại sân do creator và participant trao đổi qua Zalo.

### BR-035: No-show

- Creator hoặc đối thủ đã cọc nhưng no-show không được hoàn phần cọc của mình.
- MVP không tự chấm điểm uy tín, tự động khóa tài khoản hoặc tự xác minh no-show.
- Người ghép FIND_PLAYERS không cọc online nên no-show không phát sinh thu/hoàn tiền tự động.
- Website không bảo đảm participant sẽ đến; creator dùng số Zalo được chia sẻ sau khi chấp nhận để liên hệ.

## 3.7. Quy tắc địa chỉ và liên kết chỉ đường

### BR-036: Địa chỉ venue

- Owner chọn tỉnh/thành phố và phường/xã từ catalog rồi nhập địa chỉ chi tiết.
- Backend tự tra tên đơn vị hành chính từ mã và không nhận tên snapshot do frontend tự gửi.
- `google_place_id`, `latitude` và `longitude` chỉ là dữ liệu legacy; luồng mới không tạo hoặc yêu cầu các giá trị này.

### BR-037: Liên kết Google Maps

- Liên kết chỉ đường không chứa API key và mở ở tab mới với `noopener noreferrer`.
- Ứng dụng không tải Maps JavaScript API hoặc Places API.

## 3.8. Settlement và simulated payout

Các quy tắc trong mục này là contract cho implementation Phase 2.6; ADR-037 là
nguồn quyết định đầy đủ.

### BR-038: Phạm vi và số tiền Settlement

- Settlement chỉ đại diện cho tiền online hệ thống đã thu và phải trả cho
  Owner; tiền dự kiến trả trực tiếp tại sân không thuộc Settlement.
- `Booking.paid_amount` là số tiền online ròng hiện đang được ghi nhận và
  `balance_due_at_venue = Booking.total_amount - Booking.paid_amount`.
- Không hard-code 70%, 30% hoặc 15%; phải đọc chứng cứ tài chính thực tế và
  giữ đúng `DEPOSIT_30`, trường hợp `FIND_OPPONENT` mới thu 15%, cùng
  `LEGACY_FULL_ONLINE`.
- Với Booking hợp lệ, `gross_online_amount` là tổng Payment `SUCCESS` được
  chấp nhận, `successful_refund_amount` là tổng Refund `SUCCESS` áp dụng và
  `settlement_amount = gross_online_amount - successful_refund_amount`.
- Settlement amount phải đối soát với online net hiện hành. Contribution chỉ
  dùng để kiểm tra phân bổ/nghĩa vụ, không được cộng trùng với Payment.
- Booking chưa từng có khoản online được nhận diện thì không tạo Settlement.

### BR-039: Trạng thái Settlement

- `PENDING`: có tiền online được nhận diện nhưng chưa đến mốc đủ điều kiện hoặc
  còn prerequisite không phải ngoại lệ.
- `ELIGIBLE`: hiện tại an toàn để Admin thực hiện simulated payout.
- `ON_HOLD`: còn cancellation, refund hoặc sai lệch tài chính chưa giải quyết.
- `FAILED`: simulated payout gần nhất lỗi kỹ thuật; được retry sau revalidation.
- `SETTLED`: simulated payout đã thành công và là terminal trong Phase 2.6.
- `CLOSED`: terminal, nhãn “Đã đóng – không chi trả”, dùng khi Settlement cần
  được giữ làm chứng cứ nhưng số tiền phải trả cuối cùng bằng 0 trước payout.
- Không tạo `PayoutAttempt` số tiền 0 và không có payout action cho `PENDING`,
  `ON_HOLD`, `SETTLED` hoặc `CLOSED`.

### BR-040: Điều kiện đủ để chi trả

- Booking lifecycle hoàn thành ngay sau thời gian sử dụng kết thúc; Settlement
  chỉ đủ điều kiện bình thường từ thời gian kết thúc cộng 30 phút, theo thời
  gian địa phương Việt Nam.
- `ELIGIBLE` yêu cầu Booking ở trạng thái hoàn thành/phải trả được chấp nhận,
  payable online amount dương, Payment/Refund/contribution đối soát được,
  không có Refund `PENDING`/`PROCESSING`/`FAILED`, không có late provider
  payment chưa được xử lý đúng, quan hệ Owner/Venue hợp lệ và có simulated
  payout destination.
- Creator-cancelled có khoản cọc bị giữ hợp lệ có thể phải trả sau cùng mốc
  thời gian nếu refund đã giải quyết, số tiền bị giữ dương, đối soát đạt và có
  destination. Booking vẫn giữ `CANCELLED`; Settlement không sửa lifecycle đó.
- Owner-cancelled không bao giờ là trường hợp có số tiền phải trả cho Owner.

### BR-041: Refund, cancellation và zero net

- Refund `SUCCESS` là lịch sử bất biến và được trừ khi tính online net; nó
  không chặn Settlement vĩnh viễn nếu phần còn lại vẫn phải trả và đối soát.
- Refund `PENDING`, `PROCESSING` hoặc `FAILED` bắt buộc Settlement `ON_HOLD`.
  Sau khi ngoại lệ được giải quyết, service được revalidate trạng thái.
- Tiền online của creator bị giữ theo cancellation policy thuộc Owner như bồi
  thường cho khung giờ đã giữ, không phải doanh thu nền tảng. Refund phải trả
  participant khác được xử lý trước khi chốt số tiền phải trả.
- Owner cancellation giữ Settlement `ON_HOLD` trong lúc refund chưa xong và
  chuyển `CLOSED` khi số tiền phải trả cuối cùng bằng 0.
- Full Refund hoặc một ngoại lệ hợp lệ làm zero net trước payout cũng chuyển
  Settlement hiện có sang `CLOSED`.

### BR-042: Payment và dữ liệu legacy

- Payment `FAILED`, `CANCELLED` hoặc `EXPIRED` lịch sử không giữ Settlement
  vĩnh viễn nếu Payment được chấp nhận sau đó tạo financial state hợp lệ.
- Payment `EXPIRED` nhưng được provider xác nhận thành công muộn không được
  tính là payable nếu chưa thuộc financial state đã chấp nhận; nếu đang chờ
  refund thì Settlement là `ON_HOLD` hoặc không payable tùy chứng cứ.
- `LEGACY_FULL_ONLINE` có `paid_amount` nhưng thiếu Payment evidence phải là
  `ON_HOLD`; không tạo Payment giả.
- Legacy có Payment/Refund hợp lệ và positive net được tạo `PENDING` hoặc
  `ELIGIBLE`; financial mismatch là `ON_HOLD`; chứng cứ zero net/full refund
  có thể tạo `CLOSED` để giữ audit trail.

### BR-043: Simulated payout destination và attempt

- Mỗi Owner có tối đa một destination đang hoạt động với
  `provider = SIMULATED`, `destination_label` và demo `account_reference`;
  không lưu credential ngân hàng/MoMo thật.
- Trước payout, UI hiển thị destination hiện tại sẽ được snapshot khi xác
  nhận. Mỗi `PayoutAttempt` lưu snapshot riêng; đổi destination không sửa
  attempt lịch sử.
- Chỉ Admin POST payout từ Settlement Detail. Owner chỉ xem trạng thái và kết
  quả, không được sửa amount/status hoặc kích hoạt payout.
- Chỉ `ELIGIBLE` được payout; `FAILED` được retry sau revalidation. Mỗi attempt
  có idempotency key/reference duy nhất; request trùng không tạo attempt trùng,
  retry tạo attempt mới và không có giới hạn retry cố định trong MVP.

### BR-044: SETTLED và ngoại lệ phát sinh muộn

- `SETTLED` không tự reverse, không bị giảm số tiền lịch sử, không tạo payout
  bù trừ và không gọi adapter lần nữa.
- Refund hoặc sai lệch xuất hiện sau `SETTLED` giữ nguyên Settlement/attempt và
  được biểu diễn thành post-settlement variance/manual-review trong Admin read
  model khi có thể.
- Clawback, adjustment và Dispute model nằm ngoài Phase 2.6 MVP.

### BR-045: Đồng bộ Settlement

- Dùng Flask CLI idempotent `flask settlements sync`; không dùng Celery,
  APScheduler hoặc background worker.
- CLI phát hiện khoản online, tạo/backfill Settlement, refresh số tiền chưa
  terminal và chuyển `PENDING`/`ELIGIBLE`/`ON_HOLD`/`CLOSED`.
- CLI được revalidate `FAILED` nhưng không tự retry payout; payout chỉ xảy ra
  qua POST Admin có kiểm soát.
- CLI và Admin/Owner GET không sửa Booking lifecycle, Payment, Refund hoặc
  Match, không payout và không tạo lịch sử giả.
- Legacy backfill thuộc application service/CLI, không thuộc Alembic migration.
