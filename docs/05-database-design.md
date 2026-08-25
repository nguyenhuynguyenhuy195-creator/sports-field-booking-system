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

## 5.6. Bảng `provinces`

| Cột | Kiểu dữ liệu | Ràng buộc |
|---|---|---|
| code | VARCHAR(2) | PK |
| name | NVARCHAR(100) | NOT NULL, UNIQUE |

Catalog chỉ đọc, dùng mã cấp tỉnh chính thức theo Quyết định 19/2025/QĐ-TTg. Owner không có API tạo/sửa/xóa catalog.

## 5.7. Bảng `wards`

| Cột | Kiểu dữ liệu | Ràng buộc |
|---|---|---|
| code | VARCHAR(5) | PK |
| province_code | VARCHAR(2) | FK → provinces.code, NOT NULL |
| name | NVARCHAR(100) | NOT NULL |
| type | VARCHAR(20) | NOT NULL |

`type`: `PHUONG`, `XA`, `DAC_KHU`. Index `(province_code, name)` phục vụ dropdown phụ thuộc. Catalog snapshot có 34 tỉnh/thành phố và 3.321 đơn vị gồm 2.621 xã, 687 phường, 13 đặc khu; migration kiểm tra cả tổng số, cơ cấu loại, mã trùng và quan hệ parent trước khi seed.

## 5.8. Bảng `venues`

| Cột | Kiểu dữ liệu | Ràng buộc |
|---|---|---|
| id | INT | PK, IDENTITY |
| owner_id | INT | FK → users.id, NOT NULL |
| name | NVARCHAR(150) | NOT NULL |
| address | NVARCHAR(255) | NOT NULL |
| province_code | VARCHAR(2) | FK → provinces.code, NULL cho legacy |
| province_name | NVARCHAR(100) | NULL cho legacy |
| ward_code | VARCHAR(5) | FK → wards.code, NULL cho legacy |
| ward_name | NVARCHAR(100) | NULL cho legacy |
| district | NVARCHAR(100) | NULL, chỉ fallback legacy |
| city | NVARCHAR(100) | NULL, chỉ fallback legacy |
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

Backend phải tra catalog để xác nhận province tồn tại, ward tồn tại và `ward.province_code == province.code`; frontend không được tự gửi tên snapshot. Index `(status, province_code, ward_code)` phục vụ tìm kiếm và phạm vi quản trị.

`full_address` ưu tiên `address + ward_name + province_name`; nếu venue chưa chuẩn hóa thì fallback `address + district + city`. Venue mới phải có `google_place_id` và tọa độ trước khi được duyệt `ACTIVE`. Migration không sửa `google_place_id/latitude/longitude`, không map đoán district cũ sang ward mới và giữ nguyên hai cột legacy để đọc dữ liệu cũ.

## 5.9. Bảng `fields`

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

## 5.10. Bảng `field_price_slots`

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

## 5.11. Bảng `field_maintenances`

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

## 5.12. Bảng `bookings`

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

Với `DEPOSIT_30`, `deposit_rate` được snapshot ở `0.3000`; `deposit_amount` là mức cọc online mục tiêu tối đa bằng 30% `total_amount` sau khi làm tròn đến đồng. `paid_amount` là tiền cọc online thành công ròng sau refund và vẫn bao gồm khoản đã thu hợp lệ nhưng bị người nộp từ bỏ. Số còn lại tại sân được suy ra bằng `total_amount - paid_amount`, không phải luôn bằng `total_amount - deposit_amount`, và không lưu trạng thái thanh toán riêng trong MVP.

DIRECT_BOOKING/FIND_PLAYERS đạt `PAID` sau khi creator trả đủ 30%. FIND_OPPONENT đạt `PARTIALLY_PAID` sau khi creator trả 15% và trạng thái này đã giữ sân hợp lệ; nếu đối thủ trả thêm 15% thì chuyển `PAID`. FIND_OPPONENT không có đối thủ có thể chuyển từ `PARTIALLY_PAID` sang `COMPLETED` sau giờ sử dụng. Booking `LEGACY_FULL_ONLINE` dùng rate 1 và được gắn nhãn lịch sử riêng trên UI.

`matchmaking_deadline` và `funding_deadline` chỉ giữ để diễn giải booking FIND_OPPONENT theo chính sách cũ. Booking tạo theo ADR-027 để cả hai cột `NULL`; giờ booking bắt đầu là thời điểm đóng bài tìm đối thủ. Service phải nhận biết bản ghi legacy có deadline để không đổi hồi tố lịch sử đang diễn ra.

`cancellation_fee_amount` lưu tổng tiền creator bị giữ khi chính creator hủy booking. Dữ liệu cũ có thể chứa phí 20% theo chính sách 80/20; booking mới có thể bằng toàn bộ phần creator đã đóng. Khoản đối thủ bị giữ khi họ rút nhưng booking vẫn tiếp tục được thể hiện bằng contribution `FORFEITED`, không cộng vào cancellation_fee_amount của booking.

Check constraint tối thiểu:
- `start_time < end_time`.
- `total_amount > 0`.
- `deposit_rate > 0 AND deposit_rate <= 1`.
- `deposit_amount > 0 AND deposit_amount <= total_amount`.
- `DEPOSIT_30` bắt buộc `deposit_rate = 0.3000`; `LEGACY_FULL_ONLINE` bắt buộc `deposit_rate = 1.0000`.
- `paid_amount >= 0 AND paid_amount <= deposit_amount`.
- `cancellation_fee_amount >= 0 AND cancellation_fee_amount <= paid_amount`.
- `FIND_PLAYERS` bắt buộc `requested_players > 0`; mode khác bắt buộc `requested_players IS NULL`.

Ở tầng service, booking mới theo ADR-027 luôn để cả `matchmaking_deadline` và `funding_deadline` là `NULL`. Hai cột nullable không có check constraint mới vì cần giữ nguyên các snapshot legacy đã tồn tại.

Index tối thiểu:
- `(field_id, booking_date, status, start_time, end_time)` cho kiểm tra trùng.
- `(user_id, created_at)` cho lịch sử user.
- `(status, initial_payment_due_at)` cho giữ chỗ 15 phút. Hai index deadline cũ có thể được giữ tạm để xử lý booking legacy nhưng không còn phục vụ booking ADR-027.

## 5.13. Bảng `booking_price_details`

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

## 5.14. Bảng `booking_contributions`

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

`DIRECT_BOOKING` và `FIND_PLAYERS` mới chỉ tạo một contribution `CREATOR` bằng toàn bộ tiền cọc. `FIND_OPPONENT` tạo `CREATOR` và `OPPONENT`, mỗi bên chịu một nửa tiền cọc; phần cuối điều chỉnh sai số làm tròn. `user_id` của `OPPONENT` để `NULL` cho đến khi một đại diện bấm nhận kèo và service khóa được suất thanh toán.

`PLAYER` chỉ được giữ để bảo toàn lịch sử booking cũ trong migration; service mới không tạo contribution/payment cho người ghép. `slot_number` là `NULL` với `CREATOR`/`TOP_UP` và bắt buộc dương với `OPPONENT` hoặc dữ liệu `PLAYER` lịch sử. Filtered unique index `(booking_id, contribution_type, slot_number) WHERE slot_number IS NOT NULL AND status <> 'REFUNDED'` tiếp tục bảo vệ nghĩa vụ còn hiệu lực.

`amount_paid` không được vượt `amount_due`. `TOP_UP` và việc chuyển `OPPONENT` sang `WAIVED` chỉ còn dùng để bảo toàn lịch sử chính sách cũ; service ADR-027 không tạo creator top-up bắt buộc.

Với FIND_OPPONENT mới, contribution CREATOR `PAID` bằng 15% đã đủ làm booking hợp lệ. Contribution OPPONENT chưa có người có thể giữ `PENDING` đến giờ bắt đầu rồi chuyển `EXPIRED` mà không hủy booking. Nếu đối thủ đã thanh toán rồi chủ động rút/no-show, contribution chuyển `FORFEITED`, payment vẫn `SUCCESS`, khoản đó tiếp tục nằm trong `bookings.paid_amount` và người thay thế không được tạo thêm payment cho cùng nghĩa vụ.

## 5.15. Bảng `payments`

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

## 5.16. Bảng `refunds`

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

Booking mới không tạo refund cho creator/đối thủ chủ động hủy, rút hoặc no-show. Refund được dùng khi owner hủy, hệ thống thu trùng/sai hoặc creator hủy khiến payment của đối thủ vô can phải được hoàn 100%.

Filtered unique index cần có: `provider_refund_trans_id WHERE provider_refund_trans_id IS NOT NULL`. Service phải khóa payment và kiểm tra tổng refund `SUCCESS`/đang xử lý không vượt số tiền payment thành công.

## 5.17. Bảng `matches`

| Cột | Kiểu dữ liệu | Ràng buộc |
|---|---|---|
| id | INT | PK, IDENTITY |
| creator_id | INT | FK → users.id, NOT NULL |
| booking_id | INT | FK → bookings.id, UNIQUE, NOT NULL |
| match_type | VARCHAR(30) | NOT NULL |
| title | NVARCHAR(200) | NOT NULL |
| description | NVARCHAR(MAX) | NULL |
| skill_level | VARCHAR(30) | NULL |
| creator_contact_phone | VARCHAR(20) | NULL |
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

FIND_OPPONENT có effective state “đã đóng” từ giờ booking bắt đầu dù job chưa kịp cập nhật status lưu trữ. Query danh sách mở và service nhận kèo/thanh toán phải luôn đối chiếu ngày giờ booking, không chỉ dựa vào `matches.status`.

`creator_contact_phone` là snapshot có sự đồng ý cho từng kèo. Migration để cột nullable nhằm giữ tương thích dữ liệu cũ; hệ thống không tự sao chép số hồ sơ vào match lịch sử. Creator của bản ghi cũ phải chủ động bổ sung và đồng ý chia sẻ.

## 5.18. Bảng `match_participants`

| Cột | Kiểu dữ liệu | Ràng buộc |
|---|---|---|
| id | INT | PK, IDENTITY |
| match_id | INT | FK → matches.id, NOT NULL |
| user_id | INT | FK → users.id, NOT NULL |
| contribution_id | INT | FK → booking_contributions.id, NULL |
| participant_type | VARCHAR(20) | NOT NULL |
| message | NVARCHAR(500) | NULL |
| contact_phone | VARCHAR(20) | NULL; snapshot Zalo có sự đồng ý |
| status | VARCHAR(30) | NOT NULL |
| payment_due_at | DATETIME2 | NULL |
| created_at | DATETIME2 | NOT NULL |
| decided_at | DATETIME2 | NULL |
| updated_at | DATETIME2 | NULL |

Participant type: `PLAYER`, `OPPONENT_REPRESENTATIVE`.

Status: `PENDING`, `ACCEPTED_AWAITING_PAYMENT`, `JOINED`, `REJECTED`, `EXPIRED`, `WITHDRAWN`.

Service phải ngăn một user có hai yêu cầu đang hoạt động cho cùng một match.

`contact_phone` bắt buộc với yêu cầu `PLAYER`; đây là snapshot số dùng Zalo tại thời điểm gửi. Backend chỉ trả số này cho creator sau khi participant được chấp nhận và giao diện ẩn lại khi booking hoàn thành/hủy.

`contribution_id` chỉ được gắn cho đại diện đối thủ cần thanh toán cọc. Với booking mới, thao tác nhận kèo gắn contribution và chuyển participant thẳng sang `ACCEPTED_AWAITING_PAYMENT`; `decided_at` được dùng như thời điểm hệ thống tự xác nhận giữ suất. Participant `PLAYER` không có contribution/payment; khi creator chấp nhận thì chuyển thẳng `JOINED` và `payment_due_at = NULL`.

`PENDING` tiếp tục dùng cho FIND_PLAYERS và yêu cầu đối thủ cũ tạo trước ADR-028. Booking FIND_OPPONENT mới không tạo `PENDING`; booking legacy có deadline vẫn có thể dùng bước duyệt cũ.

Đại diện đối thủ đã cọc rồi chủ động rút chuyển `WITHDRAWN`; contribution cũ giữ lịch sử ở `FORFEITED`. Nếu bài mở lại, người thay thế được tham gia mà không bị thu lại phần cọc đã nằm trong booking.

Filtered unique index hoặc cơ chế khóa tương đương cần áp dụng cho `(match_id, user_id)` ở các trạng thái `PENDING`, `ACCEPTED_AWAITING_PAYMENT` và `JOINED`.

## 5.19. Quan hệ chính

- User 1–N OwnerApplication; Admin 1–N OwnerApplication đã review.
- Sport 1–N FieldType.
- Province 1–N Ward; Venue tham chiếu một Province và Ward khi đã chuẩn hóa.
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

## 5.20. Ràng buộc cần kiểm tra trong service và transaction

- Không trùng booking hoặc lịch bảo trì.
- Không tạo hai lịch bảo trì `ACTIVE` chồng nhau cho cùng field.
- Không chồng khung giá và phải phủ đủ thời gian booking.
- Không thu tiền cọc vượt `deposit_amount`.
- Số còn lại tại sân luôn lấy `total_amount - paid_amount` ròng; không mặc định 70% khi FIND_OPPONENT chưa có đối thủ.
- Không có hai payment `SUCCESS` cho cùng một contribution.
- Không refund vượt số tiền payment đã thành công.
- Không tạo refund cho bên chủ động hủy/rút/no-show; hoàn 100% cho bên không có lỗi khi owner/creator phía kia/hệ thống gây hủy hoặc thu sai.
- Không nhận quá số vị trí còn thiếu hoặc quá capacity/play format.
- Không tạo hai match cho cùng một booking.
- Không xử lý IPN/refund callback lặp lại hai lần.
- `payments` và `refunds` là lịch sử tiền gốc; `booking_contributions.amount_paid` và `bookings.paid_amount` là số tổng hợp phải cập nhật cùng transaction.
- Không cascade delete dữ liệu lịch sử; dữ liệu đã được tham chiếu phải chuyển trạng thái.
- Không trả `matches.creator_contact_phone` hoặc `match_participants.contact_phone` cho user không liên quan, trước khi participant `JOINED`, hoặc sau khi booking kết thúc/hủy.
- Việc participant xuất hiện trong lịch cá nhân được suy ra từ `match_participants.user_id/status`; không tạo booking thứ hai và không thay đổi `bookings.user_id`.
- Tìm theo bán kính chỉ dùng venue `ACTIVE` có cặp tọa độ hợp lệ.
- Không lưu venue mới với province/ward không tồn tại hoặc ward không thuộc province đã chọn.

## 5.21. Tương thích dữ liệu khi triển khai ADR-027

Rà soát model và chuỗi migration hiện có cho thấy `matchmaking_deadline` và `funding_deadline` đều đã nullable, đồng thời không có check constraint bắt buộc FIND_OPPONENT phải có deadline. Vì vậy ADR-027 không cần migration schema mới:

1. Service tạo booking mới để cả hai deadline là `NULL`.
2. Giữ hai cột và index deadline để xử lý booking legacy; chưa drop cột hoặc xóa migration cũ.
3. Giữ `cancellation_fee_amount`, `TOP_UP`, `WAIVED` và refund 80/20 cũ để đọc đúng lịch sử; service mới không tạo top-up/refund 80/20.
4. Booking đã có deadline tiếp tục theo chính sách snapshot cũ; booking tạo mới dùng ADR-027.
5. Job funding-expire chỉ xử lý bản ghi legacy có deadline; bài ADR-027 hết hiệu lực theo giờ booking bắt đầu.

Không reset database, không chạy DROP và không sửa migration cũ. Vẫn phải chạy `flask db upgrade`, `flask db check`, test SQL Server và test hồi quy để xác nhận model đang khớp migration head.

Nguồn ERD `docs/diagrams/erd.mmd` chưa cần đổi cấu trúc vì hai cột deadline vẫn được giữ để tương thích; ý nghĩa mới được mô tả trong tài liệu này.
