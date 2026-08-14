# 5. Thiết kế cơ sở dữ liệu

## 5.1. Nguyên tắc chung

- SQL Server là database chính; truy cập qua Flask-SQLAlchemy và pyodbc.
- Tên bảng dùng `snake_case` và số nhiều.
- Tiền lưu bằng `DECIMAL(12,2)`; số tiền gửi MoMo phải là số nguyên VND.
- Khoản cọc, tỷ lệ cọc và tổng tiền được snapshot trên booking; không suy lại từ cấu hình hiện hành.
- Tọa độ venue lưu bằng `DECIMAL(9,6)`; khoảng cách là giá trị tính toán, không phải giá do Google gửi để tin tuyệt đối.
- Các cột giờ dùng `TIME(0)`; booking, khung giá và bảo trì không đi qua nửa đêm trong MVP.
- Timestamp hệ thống lưu theo UTC bằng `DATETIME2`; `booking_date` và `TIME` được hiểu theo múi giờ `Asia/Ho_Chi_Minh`.
- Trạng thái phải có `CHECK CONSTRAINT` hoặc validation tương đương trong migration.
- Không xóa vật lý dữ liệu đã có booking, payment hoặc refund.
- Foreign key của dữ liệu lịch sử dùng `NO ACTION`; không cascade delete booking, contribution, payment, refund hoặc match.
- Các quy tắc unique theo trạng thái hoặc trên cột nullable phải dùng filtered unique index phù hợp SQL Server.
- Mọi index, foreign key, unique constraint và hành vi xóa phải được review trên SQL Server trước khi chạy migration.

## 5.2. Bảng `users`

| Cột | Kiểu dữ liệu | Ràng buộc |
|---|---|---|
| id | INT | PK, IDENTITY |
| full_name | NVARCHAR(100) | NOT NULL |
| email | VARCHAR(255) | UNIQUE, NOT NULL |
| phone | VARCHAR(20) | NULL |
| password_hash | VARCHAR(255) | NOT NULL |
| role | VARCHAR(20) | NOT NULL |
| status | VARCHAR(20) | NOT NULL |
| created_at | DATETIME2 | NOT NULL |
| updated_at | DATETIME2 | NULL |

Role: `USER`, `OWNER`, `ADMIN`.

Status: `ACTIVE`, `LOCKED`, `INACTIVE`.

## 5.3. Bảng `owner_applications`

| Cột | Kiểu dữ liệu | Ràng buộc |
|---|---|---|
| id | INT | PK, IDENTITY |
| user_id | INT | FK → users.id, NOT NULL |
| business_name | NVARCHAR(150) | NOT NULL |
| contact_phone | VARCHAR(20) | NOT NULL |
| note | NVARCHAR(500) | NULL |
| status | VARCHAR(20) | NOT NULL |
| rejection_reason | NVARCHAR(500) | NULL |
| reviewed_by | INT | FK → users.id, NULL |
| reviewed_at | DATETIME2 | NULL |
| created_at | DATETIME2 | NOT NULL |

Status: `PENDING`, `APPROVED`, `REJECTED`, `CANCELLED`.

Cần ngăn một user có hai yêu cầu `PENDING` đồng thời.

Filtered unique index cần có: `(user_id) WHERE status = 'PENDING'`.

## 5.4. Bảng `sports`

| Cột | Kiểu dữ liệu | Ràng buộc |
|---|---|---|
| id | INT | PK, IDENTITY |
| code | VARCHAR(30) | UNIQUE, NOT NULL |
| name | NVARCHAR(100) | UNIQUE, NOT NULL |
| status | VARCHAR(20) | NOT NULL |
| created_at | DATETIME2 | NOT NULL |
| updated_at | DATETIME2 | NULL |

Code được seed trong MVP: `FOOTBALL`, `BADMINTON`, `PICKLEBALL`, `TENNIS`.

Status: `ACTIVE`, `INACTIVE`.

Danh mục này do hệ thống quản lý; owner không tự thêm sport.

## 5.5. Bảng `field_types`

| Cột | Kiểu dữ liệu | Ràng buộc |
|---|---|---|
| id | INT | PK, IDENTITY |
| sport_id | INT | FK → sports.id, NOT NULL |
| code | VARCHAR(50) | UNIQUE, NOT NULL |
| name | NVARCHAR(100) | NOT NULL |
| standard_players_per_side | INT | NULL, CHECK > 0 nếu có |
| status | VARCHAR(20) | NOT NULL |
| created_at | DATETIME2 | NOT NULL |
| updated_at | DATETIME2 | NULL |

Seed MVP:

| Sport | Field type code | Tên | Người thi đấu chính mỗi bên |
|---|---|---|---:|
| FOOTBALL | FOOTBALL_5 | Sân bóng đá 5 người | 5 |
| FOOTBALL | FOOTBALL_7 | Sân bóng đá 7 người | 7 |
| FOOTBALL | FOOTBALL_11 | Sân bóng đá 11 người | 11 |
| BADMINTON | BADMINTON_STANDARD | Sân cầu lông tiêu chuẩn | NULL |
| PICKLEBALL | PICKLEBALL_STANDARD | Sân pickleball tiêu chuẩn | NULL |
| TENNIS | TENNIS_STANDARD | Sân tennis tiêu chuẩn | NULL |

Unique constraint cần có: `(sport_id, name)`. Sport/field type đã được field tham chiếu chỉ chuyển `INACTIVE`, không xóa vật lý.

## 5.6. Bảng `venues`

| Cột | Kiểu dữ liệu | Ràng buộc |
|---|---|---|
| id | INT | PK, IDENTITY |
| owner_id | INT | FK → users.id, NOT NULL |
| name | NVARCHAR(150) | NOT NULL |
| address | NVARCHAR(255) | NOT NULL |
| district | NVARCHAR(100) | NULL |
| city | NVARCHAR(100) | NOT NULL |
| google_place_id | VARCHAR(255) | NULL |
| latitude | DECIMAL(9,6) | NULL |
| longitude | DECIMAL(9,6) | NULL |
| phone | VARCHAR(20) | NULL |
| description | NVARCHAR(MAX) | NULL |
| opening_time | TIME(0) | NOT NULL |
| closing_time | TIME(0) | NOT NULL |
| status | VARCHAR(20) | NOT NULL, DEFAULT `PENDING` |
| reviewed_by | INT | FK → users.id, NULL |
| reviewed_at | DATETIME2 | NULL |
| moderation_note | NVARCHAR(500) | NULL |
| created_at | DATETIME2 | NOT NULL |
| updated_at | DATETIME2 | NULL |

Status: `PENDING`, `ACTIVE`, `HIDDEN`, `INACTIVE`.

`reviewed_by`, `reviewed_at` và `moderation_note` lưu dấu vết admin duyệt, ẩn hoặc từ chối kích hoạt venue.

Check constraint:

- `latitude BETWEEN -90 AND 90` nếu có.
- `longitude BETWEEN -180 AND 180` nếu có.
- Latitude và longitude phải cùng `NULL` hoặc cùng có giá trị.

Venue mới phải có `google_place_id` và tọa độ trước khi được duyệt `ACTIVE`. Dữ liệu venue cũ được migration để tọa độ `NULL`; venue đó vẫn tìm được theo văn bản nhưng chưa tham gia tìm bán kính.

## 5.7. Bảng `fields`

| Cột | Kiểu dữ liệu | Ràng buộc |
|---|---|---|
| id | INT | PK, IDENTITY |
| venue_id | INT | FK → venues.id, NOT NULL |
| name | NVARCHAR(100) | NOT NULL |
| field_type_id | INT | FK → field_types.id, NOT NULL |
| surface_type | NVARCHAR(50) | NULL |
| capacity | INT | NOT NULL, CHECK > 0 |
| status | VARCHAR(20) | NOT NULL, DEFAULT `INACTIVE` |
| created_at | DATETIME2 | NOT NULL |
| updated_at | DATETIME2 | NULL |

Status: `ACTIVE`, `INACTIVE`.

Không dùng `base_price` vì toàn bộ giá được lấy từ bảng khung giá.

Unique constraint cần có: `(venue_id, name)` để tránh trùng tên field trong cùng venue.

`capacity` là số người tối đa owner cho phép sử dụng field, gồm cả người dự bị nếu có. Field thuộc đúng một sport thông qua `field_type_id`; không lưu thêm `sport_id` trên `fields` để tránh dữ liệu mâu thuẫn.

`field_type_id` chỉ được đổi khi field chưa có booking. Nếu đã có lịch sử, owner chuyển field cũ `INACTIVE` và tạo field mới.

## 5.8. Bảng `field_price_slots`

| Cột | Kiểu dữ liệu | Ràng buộc |
|---|---|---|
| id | INT | PK, IDENTITY |
| field_id | INT | FK → fields.id, NOT NULL |
| day_of_week | TINYINT | NOT NULL, CHECK 0–6 |
| start_time | TIME(0) | NOT NULL |
| end_time | TIME(0) | NOT NULL |
| hourly_price | DECIMAL(12,2) | NOT NULL, CHECK > 0 |
| status | VARCHAR(20) | NOT NULL |
| created_at | DATETIME2 | NOT NULL |
| updated_at | DATETIME2 | NULL |

`day_of_week`: 0 = Monday, ..., 6 = Sunday.

Status: `ACTIVE`, `INACTIVE`.

Check constraint: `start_time < end_time`.

Service phải ngăn các khung `ACTIVE` của cùng field và cùng ngày bị chồng nhau. Index cần có: `(field_id, day_of_week, status, start_time, end_time)`.

## 5.9. Bảng `field_maintenances`

| Cột | Kiểu dữ liệu | Ràng buộc |
|---|---|---|
| id | INT | PK, IDENTITY |
| field_id | INT | FK → fields.id, NOT NULL |
| maintenance_date | DATE | NOT NULL |
| start_time | TIME(0) | NOT NULL |
| end_time | TIME(0) | NOT NULL |
| reason | NVARCHAR(500) | NOT NULL |
| status | VARCHAR(20) | NOT NULL |
| created_by | INT | FK → users.id, NOT NULL |
| created_at | DATETIME2 | NOT NULL |

Status: `ACTIVE`, `CANCELLED`, `COMPLETED`.

Check constraint: `start_time < end_time`.

Service phải ngăn hai lịch bảo trì `ACTIVE` của cùng field bị chồng nhau và phải kiểm tra trùng booking trong cùng transaction.

Index cần có: `(field_id, maintenance_date, status, start_time, end_time)`.

## 5.10. Bảng `bookings`

| Cột | Kiểu dữ liệu | Ràng buộc |
|---|---|---|
| id | INT | PK, IDENTITY |
| booking_code | VARCHAR(30) | UNIQUE, NOT NULL |
| user_id | INT | FK → users.id, NOT NULL |
| field_id | INT | FK → fields.id, NOT NULL |
| booking_date | DATE | NOT NULL |
| start_time | TIME(0) | NOT NULL |
| end_time | TIME(0) | NOT NULL |
| booking_mode | VARCHAR(30) | NOT NULL |
| play_format | VARCHAR(20) | NULL |
| requested_players | INT | NULL |
| payment_policy | VARCHAR(30) | NOT NULL |
| total_amount | DECIMAL(12,2) | NOT NULL, CHECK > 0 |
| deposit_rate | DECIMAL(5,4) | NOT NULL |
| deposit_amount | DECIMAL(12,2) | NOT NULL, CHECK > 0 |
| paid_amount | DECIMAL(12,2) | NOT NULL, DEFAULT 0 |
| cancellation_fee_amount | DECIMAL(12,2) | NOT NULL, DEFAULT 0 |
| status | VARCHAR(30) | NOT NULL |
| initial_payment_due_at | DATETIME2 | NULL |
| matchmaking_deadline | DATETIME2 | NULL |
| funding_deadline | DATETIME2 | NULL |
| note | NVARCHAR(500) | NULL |
| cancellation_reason | NVARCHAR(500) | NULL |
| created_at | DATETIME2 | NOT NULL |
| updated_at | DATETIME2 | NULL |

Booking mode: `DIRECT_BOOKING`, `FIND_OPPONENT`, `FIND_PLAYERS`.

Play format: `SINGLES`, `DOUBLES` hoặc `NULL`. Booking của field thuộc bóng đá bắt buộc `NULL`; booking cầu lông, pickleball và tennis bắt buộc có giá trị. Quy tắc liên bảng này được kiểm tra trong service.

`requested_players` snapshot số vị trí creator muốn tìm trước khi match được mở. Cột bắt buộc dương với `FIND_PLAYERS` và bắt buộc `NULL` với mode khác.

Payment policy: `LEGACY_FULL_ONLINE`, `DEPOSIT_30`. Booking mới luôn dùng `DEPOSIT_30`; giá trị legacy chỉ bảo toàn cách diễn giải payment/contribution đã tồn tại trước migration.

Status: `PENDING`, `CONFIRMED`, `PARTIALLY_PAID`, `PAID`, `REFUND_PENDING`, `COMPLETED`, `REJECTED`, `CANCELLED`, `EXPIRED`.

Luồng tự động mới tạo booking trực tiếp ở `CONFIRMED` và bắt buộc có `initial_payment_due_at` bằng thời điểm tạo cộng 15 phút. `PENDING` và `REJECTED` chỉ còn trong CHECK constraint để tương thích dữ liệu/migration của luồng duyệt cũ, không được service mới tạo ra.

Với `DEPOSIT_30`, `deposit_rate` được snapshot ở `0.3000`; `deposit_amount` là 30% `total_amount` sau khi làm tròn đến đồng. `paid_amount` là tiền cọc online thành công ròng sau refund. Số còn lại tại sân được suy ra bằng `total_amount - deposit_amount` và không lưu trạng thái thanh toán riêng trong MVP. `PAID` nghĩa là đã đủ cọc. Booking `LEGACY_FULL_ONLINE` dùng rate 1 và được gắn nhãn lịch sử riêng trên UI.

`matchmaking_deadline` chỉ dùng cho `FIND_OPPONENT` và bằng giờ bắt đầu trừ 12 giờ. `funding_deadline` bằng `matchmaking_deadline + 30 phút`, là hạn creator top-up. Hai cột để `NULL` cho mode khác.

Check constraint tối thiểu:
- `start_time < end_time`.
- `total_amount > 0`.
- `deposit_rate > 0 AND deposit_rate <= 1`.
- `deposit_amount > 0 AND deposit_amount <= total_amount`.
- `DEPOSIT_30` bắt buộc `deposit_rate = 0.3000`; `LEGACY_FULL_ONLINE` bắt buộc `deposit_rate = 1.0000`.
- `paid_amount >= 0 AND paid_amount <= deposit_amount`.
- `cancellation_fee_amount >= 0 AND cancellation_fee_amount <= paid_amount`.
- `FIND_PLAYERS` bắt buộc `requested_players > 0`; mode khác bắt buộc `requested_players IS NULL`.
- `FIND_OPPONENT` bắt buộc có hai deadline và `matchmaking_deadline < funding_deadline`; mode khác bắt buộc hai cột này `NULL`.

Index tối thiểu:
- `(field_id, booking_date, status, start_time, end_time)` cho kiểm tra trùng.
- `(user_id, created_at)` cho lịch sử user.
- `(status, initial_payment_due_at)`, `(status, matchmaking_deadline)` và `(status, funding_deadline)` cho job deadline.

## 5.11. Bảng `booking_price_details`

| Cột | Kiểu dữ liệu | Ràng buộc |
|---|---|---|
| id | INT | PK, IDENTITY |
| booking_id | INT | FK → bookings.id, NOT NULL |
| price_slot_id | INT | FK → field_price_slots.id, NOT NULL |
| start_time | TIME(0) | NOT NULL |
| end_time | TIME(0) | NOT NULL |
| duration_minutes | INT | NOT NULL, CHECK > 0 |
| hourly_price | DECIMAL(12,2) | NOT NULL |
| subtotal | DECIMAL(12,2) | NOT NULL |

Bảng này là snapshot giá; không cập nhật khi owner thay đổi khung giá sau đó.

Check constraint: `start_time < end_time`, `duration_minutes > 0`, `hourly_price > 0` và `subtotal > 0`. Khung giá đã được dùng phải chuyển `INACTIVE` thay vì xóa vật lý.

## 5.12. Bảng `booking_contributions`

| Cột | Kiểu dữ liệu | Ràng buộc |
|---|---|---|
| id | INT | PK, IDENTITY |
| booking_id | INT | FK → bookings.id, NOT NULL |
| user_id | INT | FK → users.id, NULL |
| contribution_type | VARCHAR(30) | NOT NULL |
| slot_number | INT | NULL |
| amount_due | DECIMAL(12,2) | NOT NULL, CHECK >= 0 |
| amount_paid | DECIMAL(12,2) | NOT NULL, DEFAULT 0, CHECK >= 0 |
| status | VARCHAR(30) | NOT NULL |
| expires_at | DATETIME2 | NULL |
| created_at | DATETIME2 | NOT NULL |
| updated_at | DATETIME2 | NULL |

Contribution type: `CREATOR`, `OPPONENT`, `PLAYER`, `TOP_UP`.

Status: `PENDING`, `PAID`, `EXPIRED`, `WAIVED`, `REFUND_PENDING`, `PARTIALLY_REFUNDED`, `REFUNDED`, `FORFEITED`.

Tổng `amount_due` của các contribution còn hiệu lực phải đúng bằng `deposit_amount`; service phải khóa booking khi phân bổ hoặc cập nhật nghĩa vụ.

`DIRECT_BOOKING` và `FIND_PLAYERS` mới chỉ tạo một contribution `CREATOR` bằng toàn bộ tiền cọc. `FIND_OPPONENT` tạo `CREATOR` và `OPPONENT`, mỗi bên chịu một nửa tiền cọc; phần cuối điều chỉnh sai số làm tròn. `user_id` của `OPPONENT` để `NULL` cho đến khi creator chấp nhận đại diện đối thủ.

`PLAYER` chỉ được giữ để bảo toàn lịch sử booking cũ trong migration; service mới không tạo contribution/payment cho người ghép. `slot_number` là `NULL` với `CREATOR`/`TOP_UP` và bắt buộc dương với `OPPONENT` hoặc dữ liệu `PLAYER` lịch sử. Filtered unique index `(booking_id, contribution_type, slot_number) WHERE slot_number IS NOT NULL AND status <> 'REFUNDED'` tiếp tục bảo vệ nghĩa vụ còn hiệu lực.

`amount_paid` không được vượt `amount_due`. Khi creator top-up phần cọc đối thủ, nghĩa vụ `OPPONENT` chuyển `WAIVED` và contribution `TOP_UP` được tạo để bảo toàn lịch sử; chỉ nghĩa vụ còn hiệu lực dùng khi tính số tiền cần thu.

## 5.13. Bảng `payments`

| Cột | Kiểu dữ liệu | Ràng buộc |
|---|---|---|
| id | INT | PK, IDENTITY |
| booking_id | INT | FK → bookings.id, NOT NULL |
| contribution_id | INT | FK → booking_contributions.id, NOT NULL |
| payer_id | INT | FK → users.id, NOT NULL |
| provider | VARCHAR(20) | NOT NULL |
| payment_method | VARCHAR(30) | NOT NULL |
| amount | DECIMAL(12,2) | NOT NULL, CHECK > 0 |
| order_id | VARCHAR(100) | UNIQUE, NOT NULL |
| request_id | VARCHAR(100) | UNIQUE, NOT NULL |
| provider_trans_id | VARCHAR(100) | NULL |
| status | VARCHAR(20) | NOT NULL |
| result_code | VARCHAR(20) | NULL |
| paid_at | DATETIME2 | NULL |
| created_at | DATETIME2 | NOT NULL |
| updated_at | DATETIME2 | NULL |

Provider: `MOCK`, `MOMO`. `MOCK` chỉ dùng cho phát triển/kiểm thử; `MOMO` dành cho Sandbox khi tích hợp client thật.

Status: `PENDING`, `SUCCESS`, `FAILED`, `CANCELLED`, `EXPIRED`.

Một contribution có thể có nhiều payment attempt nhưng chỉ một kết quả `SUCCESS` còn hiệu lực.

Index/constraint bắt buộc:
- Unique `order_id` và `request_id`.
- Filtered unique `provider_trans_id WHERE provider_trans_id IS NOT NULL` để SQL Server cho phép nhiều payment chưa có mã giao dịch.
- Filtered unique `contribution_id WHERE status = 'SUCCESS'` để ngăn hai payment thành công cho cùng nghĩa vụ.

## 5.14. Bảng `refunds`

| Cột | Kiểu dữ liệu | Ràng buộc |
|---|---|---|
| id | INT | PK, IDENTITY |
| booking_id | INT | FK → bookings.id, NOT NULL |
| payment_id | INT | FK → payments.id, NOT NULL |
| recipient_id | INT | FK → users.id, NOT NULL |
| amount | DECIMAL(12,2) | NOT NULL, CHECK > 0 |
| reason | NVARCHAR(500) | NOT NULL |
| order_id | VARCHAR(100) | UNIQUE, NOT NULL |
| request_id | VARCHAR(100) | UNIQUE, NOT NULL |
| provider_refund_trans_id | VARCHAR(100) | NULL |
| status | VARCHAR(30) | NOT NULL |
| result_code | VARCHAR(20) | NULL |
| refunded_at | DATETIME2 | NULL |
| created_at | DATETIME2 | NOT NULL |
| updated_at | DATETIME2 | NULL |

Status: `PENDING`, `PROCESSING`, `SUCCESS`, `FAILED`.

Không sửa payment `SUCCESS` thành thất bại khi hoàn tiền; refund là bản ghi lịch sử riêng.

Filtered unique index cần có: `provider_refund_trans_id WHERE provider_refund_trans_id IS NOT NULL`. Service phải khóa payment và kiểm tra tổng refund `SUCCESS`/đang xử lý không vượt số tiền payment thành công.

## 5.15. Bảng `matches`

| Cột | Kiểu dữ liệu | Ràng buộc |
|---|---|---|
| id | INT | PK, IDENTITY |
| creator_id | INT | FK → users.id, NOT NULL |
| booking_id | INT | FK → bookings.id, UNIQUE, NOT NULL |
| match_type | VARCHAR(30) | NOT NULL |
| title | NVARCHAR(200) | NOT NULL |
| description | NVARCHAR(MAX) | NULL |
| skill_level | VARCHAR(30) | NULL |
| total_players | INT | NULL, CHECK > 0 |
| required_players | INT | NOT NULL, CHECK > 0 |
| status | VARCHAR(20) | NOT NULL |
| created_at | DATETIME2 | NOT NULL |
| updated_at | DATETIME2 | NULL |

Match type: `FIND_PLAYERS`, `FIND_OPPONENT`.

Status: `OPEN`, `FULL`, `CONFIRMED`, `CANCELLED`, `COMPLETED`.

Với `FIND_OPPONENT`, `required_players` được hiểu là một vị trí đội đối thủ. Với `FIND_PLAYERS`, đây là số người còn thiếu và không tính người tạo.

Validation có điều kiện:
- `FIND_OPPONENT`: `required_players = 1`.
- `FIND_PLAYERS`: `required_players` do creator chọn nhưng không vượt capacity/play format.
- Booking `SINGLES` không được tạo `FIND_PLAYERS`; booking `DOUBLES` tối đa 4 người.

## 5.16. Bảng `match_participants`

| Cột | Kiểu dữ liệu | Ràng buộc |
|---|---|---|
| id | INT | PK, IDENTITY |
| match_id | INT | FK → matches.id, NOT NULL |
| user_id | INT | FK → users.id, NOT NULL |
| contribution_id | INT | FK → booking_contributions.id, NULL |
| participant_type | VARCHAR(20) | NOT NULL |
| message | NVARCHAR(500) | NULL |
| contact_phone | VARCHAR(20) | NULL |
| status | VARCHAR(30) | NOT NULL |
| payment_due_at | DATETIME2 | NULL |
| created_at | DATETIME2 | NOT NULL |
| decided_at | DATETIME2 | NULL |
| updated_at | DATETIME2 | NULL |

Participant type: `PLAYER`, `OPPONENT_REPRESENTATIVE`.

Status: `PENDING`, `ACCEPTED_AWAITING_PAYMENT`, `JOINED`, `REJECTED`, `EXPIRED`, `WITHDRAWN`.

Service phải ngăn một user có hai yêu cầu đang hoạt động cho cùng một match.

`contact_phone` bắt buộc với yêu cầu `PLAYER`; đây là snapshot số dùng Zalo tại thời điểm gửi. Backend chỉ trả số này cho creator sau khi participant được chấp nhận và giao diện ẩn lại khi booking hoàn thành/hủy.

`contribution_id` chỉ được gắn cho đại diện đối thủ cần thanh toán cọc. Participant `PLAYER` không có contribution/payment; khi được chấp nhận chuyển thẳng `JOINED` và `payment_due_at = NULL`.

Filtered unique index hoặc cơ chế khóa tương đương cần áp dụng cho `(match_id, user_id)` ở các trạng thái `PENDING`, `ACCEPTED_AWAITING_PAYMENT` và `JOINED`.

## 5.17. Quan hệ chính

- User 1–N OwnerApplication; Admin 1–N OwnerApplication đã review.
- Sport 1–N FieldType.
- FieldType 1–N Field; mỗi Field chỉ có một FieldType.
- User 1–N Venue theo vai trò owner; Admin 1–N Venue đã review; Venue 1–N Field.
- Field 1–N FieldPriceSlot và 1–N FieldMaintenance.
- User 1–N Booking; Field 1–N Booking.
- Booking 1–N BookingPriceDetail.
- Booking 1–N BookingContribution.
- BookingContribution 1–N Payment attempt.
- Payment 1–N Refund.
- Booking 1–0..1 Match.
- Match 1–N MatchParticipant.
- MatchParticipant 1–0..1 BookingContribution đang hoạt động.

## 5.18. Ràng buộc cần kiểm tra trong service và transaction

- Không trùng booking hoặc lịch bảo trì.
- Không tạo hai lịch bảo trì `ACTIVE` chồng nhau cho cùng field.
- Không chồng khung giá và phải phủ đủ thời gian booking.
- Không thu tiền cọc vượt `deposit_amount`.
- Không có hai payment `SUCCESS` cho cùng một contribution.
- Không refund vượt số tiền payment đã thành công.
- Không nhận quá số vị trí còn thiếu hoặc quá capacity/play format.
- Không tạo hai match cho cùng một booking.
- Không xử lý IPN/refund callback lặp lại hai lần.
- `payments` và `refunds` là lịch sử tiền gốc; `booking_contributions.amount_paid` và `bookings.paid_amount` là số tổng hợp phải cập nhật cùng transaction.
- Không cascade delete dữ liệu lịch sử; dữ liệu đã được tham chiếu phải chuyển trạng thái.
- Không trả `match_participants.contact_phone` cho người không phải creator hoặc trước khi yêu cầu được chấp nhận.
- Tìm theo bán kính chỉ dùng venue `ACTIVE` có cặp tọa độ hợp lệ.

## 5.19. Kế hoạch migration và tài liệu còn phải tạo

Migration chưa được tạo ở giai đoạn cập nhật tài liệu. Khi ERD được duyệt, migration phải thực hiện theo thứ tự an toàn:

1. Tạo `sports` và `field_types`, seed 4 sport và 6 field type.
2. Thêm `fields.field_type_id` nullable; ánh xạ `FIVE_A_SIDE`, `SEVEN_A_SIDE`, `ELEVEN_A_SIDE` sang ba field type bóng đá.
3. Kiểm tra không còn bản ghi chưa ánh xạ, chuyển `field_type_id` thành NOT NULL rồi mới bỏ cột/check constraint `field_type` cũ.
4. Thêm `google_place_id`, `latitude`, `longitude` nullable cho venue; không tự bịa tọa độ dữ liệu cũ.
5. Thêm các cột booking mới (`booking_mode`, `play_format`, `requested_players`, `payment_policy`, snapshot cọc và deadline) ở trạng thái nullable, backfill:
   - `FULL_PAYMENT` → `DIRECT_BOOKING`.
   - `SPLIT_OPPONENT` → `FIND_OPPONENT`.
   - `SPLIT_PLAYERS` → `FIND_PLAYERS`.
6. Ánh xạ `split_required_players` cũ sang `requested_players` cho FIND_PLAYERS trước khi bỏ hai cột split cũ.
7. Backfill booking cũ thành `payment_policy = LEGACY_FULL_ONLINE`, `deposit_rate = 1.0000`, `deposit_amount = total_amount` để giữ nguyên payment/contribution lịch sử. Booking tạo sau migration dùng `DEPOSIT_30` và rate 0.3000.
8. Thêm `match_participants.contact_phone` nullable; chỉ bắt buộc ở service cho yêu cầu PLAYER mới.
9. Thay check constraint/index sau khi backfill và kiểm tra trực tiếp trên SQL Server.

Migration phải kiểm kê booking tương lai đang `CONFIRMED`/`PARTIALLY_PAID`/`PAID`. Không tự chuyển luồng nghiệp vụ của booking đang diễn ra; cần hoàn tất/hủy chúng hoặc có kế hoạch tương thích rõ trước khi bật service mới.

Không xóa migration cũ, không reset database và không chạy DROP. Cần backup trước khi upgrade dữ liệu thật.

Nguồn ERD nằm tại `docs/diagrams/erd.mmd`; `erd.png` được xuất từ đúng nguồn hiện hành và phải xuất lại nếu thiết kế tiếp tục thay đổi.
