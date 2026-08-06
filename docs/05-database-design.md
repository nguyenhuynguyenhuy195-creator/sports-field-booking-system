# 5. Thiết kế cơ sở dữ liệu

## 5.1. Nguyên tắc chung

- SQL Server là database chính; truy cập qua Flask-SQLAlchemy và pyodbc.
- Tên bảng dùng `snake_case` và số nhiều.
- Tiền lưu bằng `DECIMAL(12,2)`; số tiền gửi MoMo phải là số nguyên VND.
- Timestamp hệ thống lưu theo UTC bằng `DATETIME2`; `booking_date` và `TIME` được hiểu theo múi giờ `Asia/Ho_Chi_Minh`.
- Trạng thái phải có `CHECK CONSTRAINT` hoặc validation tương đương trong migration.
- Không xóa vật lý dữ liệu đã có booking, payment hoặc refund.
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

## 5.4. Bảng `venues`

| Cột | Kiểu dữ liệu | Ràng buộc |
|---|---|---|
| id | INT | PK, IDENTITY |
| owner_id | INT | FK → users.id, NOT NULL |
| name | NVARCHAR(150) | NOT NULL |
| address | NVARCHAR(255) | NOT NULL |
| district | NVARCHAR(100) | NULL |
| city | NVARCHAR(100) | NOT NULL |
| phone | VARCHAR(20) | NULL |
| description | NVARCHAR(MAX) | NULL |
| opening_time | TIME | NOT NULL |
| closing_time | TIME | NOT NULL |
| status | VARCHAR(20) | NOT NULL, DEFAULT `PENDING` |
| created_at | DATETIME2 | NOT NULL |
| updated_at | DATETIME2 | NULL |

Status: `PENDING`, `ACTIVE`, `HIDDEN`, `INACTIVE`.

## 5.5. Bảng `fields`

| Cột | Kiểu dữ liệu | Ràng buộc |
|---|---|---|
| id | INT | PK, IDENTITY |
| venue_id | INT | FK → venues.id, NOT NULL |
| name | NVARCHAR(100) | NOT NULL |
| field_type | VARCHAR(50) | NOT NULL |
| surface_type | NVARCHAR(50) | NULL |
| capacity | INT | NOT NULL, CHECK > 0 |
| status | VARCHAR(20) | NOT NULL, DEFAULT `INACTIVE` |
| created_at | DATETIME2 | NOT NULL |
| updated_at | DATETIME2 | NULL |

Status: `ACTIVE`, `INACTIVE`.

Không dùng `base_price` vì toàn bộ giá được lấy từ bảng khung giá.

## 5.6. Bảng `field_price_slots`

| Cột | Kiểu dữ liệu | Ràng buộc |
|---|---|---|
| id | INT | PK, IDENTITY |
| field_id | INT | FK → fields.id, NOT NULL |
| day_of_week | TINYINT | NOT NULL, CHECK 0–6 |
| start_time | TIME | NOT NULL |
| end_time | TIME | NOT NULL |
| hourly_price | DECIMAL(12,2) | NOT NULL, CHECK > 0 |
| status | VARCHAR(20) | NOT NULL |
| created_at | DATETIME2 | NOT NULL |
| updated_at | DATETIME2 | NULL |

`day_of_week`: 0 = Monday, ..., 6 = Sunday.

Status: `ACTIVE`, `INACTIVE`.

Service phải ngăn các khung `ACTIVE` của cùng field và cùng ngày bị chồng nhau. Index cần có: `(field_id, day_of_week, status, start_time, end_time)`.

## 5.7. Bảng `field_maintenances`

| Cột | Kiểu dữ liệu | Ràng buộc |
|---|---|---|
| id | INT | PK, IDENTITY |
| field_id | INT | FK → fields.id, NOT NULL |
| maintenance_date | DATE | NOT NULL |
| start_time | TIME | NOT NULL |
| end_time | TIME | NOT NULL |
| reason | NVARCHAR(500) | NOT NULL |
| status | VARCHAR(20) | NOT NULL |
| created_by | INT | FK → users.id, NOT NULL |
| created_at | DATETIME2 | NOT NULL |

Status: `ACTIVE`, `CANCELLED`, `COMPLETED`.

Index cần có: `(field_id, maintenance_date, status, start_time, end_time)`.

## 5.8. Bảng `bookings`

| Cột | Kiểu dữ liệu | Ràng buộc |
|---|---|---|
| id | INT | PK, IDENTITY |
| booking_code | VARCHAR(30) | UNIQUE, NOT NULL |
| user_id | INT | FK → users.id, NOT NULL |
| field_id | INT | FK → fields.id, NOT NULL |
| booking_date | DATE | NOT NULL |
| start_time | TIME | NOT NULL |
| end_time | TIME | NOT NULL |
| payment_mode | VARCHAR(30) | NOT NULL |
| total_amount | DECIMAL(12,2) | NOT NULL, CHECK > 0 |
| paid_amount | DECIMAL(12,2) | NOT NULL, DEFAULT 0 |
| cancellation_fee_amount | DECIMAL(12,2) | NOT NULL, DEFAULT 0 |
| status | VARCHAR(30) | NOT NULL |
| owner_response_due_at | DATETIME2 | NOT NULL |
| initial_payment_due_at | DATETIME2 | NULL |
| funding_deadline | DATETIME2 | NULL |
| note | NVARCHAR(500) | NULL |
| rejection_reason | NVARCHAR(500) | NULL |
| cancellation_reason | NVARCHAR(500) | NULL |
| created_at | DATETIME2 | NOT NULL |
| updated_at | DATETIME2 | NULL |

Payment mode: `FULL_PAYMENT`, `SPLIT_OPPONENT`, `SPLIT_PLAYERS`.

Status: `PENDING`, `CONFIRMED`, `PARTIALLY_PAID`, `PAID`, `REFUND_PENDING`, `COMPLETED`, `REJECTED`, `CANCELLED`, `EXPIRED`.

`paid_amount` là số tiền thành công ròng còn được phân bổ cho booking sau refund. `cancellation_fee_amount` ghi nhận phần phí giữ sân không hoàn cho owner và mặc định bằng 0.

Index tối thiểu:
- `(field_id, booking_date, status, start_time, end_time)` cho kiểm tra trùng.
- `(user_id, created_at)` cho lịch sử user.
- `(status, owner_response_due_at)` và `(status, funding_deadline)` cho xử lý hết hạn.

## 5.9. Bảng `booking_price_details`

| Cột | Kiểu dữ liệu | Ràng buộc |
|---|---|---|
| id | INT | PK, IDENTITY |
| booking_id | INT | FK → bookings.id, NOT NULL |
| price_slot_id | INT | FK → field_price_slots.id, NULL |
| start_time | TIME | NOT NULL |
| end_time | TIME | NOT NULL |
| duration_minutes | INT | NOT NULL, CHECK > 0 |
| hourly_price | DECIMAL(12,2) | NOT NULL |
| subtotal | DECIMAL(12,2) | NOT NULL |

Bảng này là snapshot giá; không cập nhật khi owner thay đổi khung giá sau đó.

## 5.10. Bảng `booking_contributions`

| Cột | Kiểu dữ liệu | Ràng buộc |
|---|---|---|
| id | INT | PK, IDENTITY |
| booking_id | INT | FK → bookings.id, NOT NULL |
| user_id | INT | FK → users.id, NOT NULL |
| match_participant_id | INT | FK → match_participants.id, NULL |
| contribution_type | VARCHAR(30) | NOT NULL |
| amount_due | DECIMAL(12,2) | NOT NULL, CHECK >= 0 |
| amount_paid | DECIMAL(12,2) | NOT NULL, DEFAULT 0 |
| status | VARCHAR(30) | NOT NULL |
| expires_at | DATETIME2 | NULL |
| created_at | DATETIME2 | NOT NULL |
| updated_at | DATETIME2 | NULL |

Contribution type: `CREATOR`, `OPPONENT`, `PLAYER`, `TOP_UP`.

Status: `PENDING`, `PAID`, `EXPIRED`, `REFUND_PENDING`, `PARTIALLY_REFUNDED`, `REFUNDED`, `FORFEITED`.

Tổng `amount_due` của các contribution còn hiệu lực phải đúng bằng `total_amount`; service phải khóa booking khi phân bổ hoặc cập nhật nghĩa vụ.

## 5.11. Bảng `payments`

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
| provider_trans_id | VARCHAR(100) | UNIQUE, NULL |
| status | VARCHAR(20) | NOT NULL |
| result_code | VARCHAR(20) | NULL |
| paid_at | DATETIME2 | NULL |
| created_at | DATETIME2 | NOT NULL |
| updated_at | DATETIME2 | NULL |

Provider: `MOMO`.

Status: `PENDING`, `SUCCESS`, `FAILED`, `CANCELLED`, `EXPIRED`.

Một contribution có thể có nhiều payment attempt nhưng chỉ một kết quả `SUCCESS` còn hiệu lực.

## 5.12. Bảng `refunds`

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
| provider_refund_trans_id | VARCHAR(100) | UNIQUE, NULL |
| status | VARCHAR(30) | NOT NULL |
| result_code | VARCHAR(20) | NULL |
| refunded_at | DATETIME2 | NULL |
| created_at | DATETIME2 | NOT NULL |
| updated_at | DATETIME2 | NULL |

Status: `PENDING`, `PROCESSING`, `SUCCESS`, `FAILED`.

Không sửa payment `SUCCESS` thành thất bại khi hoàn tiền; refund là bản ghi lịch sử riêng.

## 5.13. Bảng `matches`

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

## 5.14. Bảng `match_participants`

| Cột | Kiểu dữ liệu | Ràng buộc |
|---|---|---|
| id | INT | PK, IDENTITY |
| match_id | INT | FK → matches.id, NOT NULL |
| user_id | INT | FK → users.id, NOT NULL |
| participant_type | VARCHAR(20) | NOT NULL |
| message | NVARCHAR(500) | NULL |
| status | VARCHAR(30) | NOT NULL |
| payment_due_at | DATETIME2 | NULL |
| created_at | DATETIME2 | NOT NULL |
| decided_at | DATETIME2 | NULL |
| updated_at | DATETIME2 | NULL |

Participant type: `PLAYER`, `OPPONENT_REPRESENTATIVE`.

Status: `PENDING`, `ACCEPTED_AWAITING_PAYMENT`, `JOINED`, `REJECTED`, `EXPIRED`, `WITHDRAWN`.

Service phải ngăn một user có hai yêu cầu đang hoạt động cho cùng một match.

## 5.15. Quan hệ chính

- User 1–N OwnerApplication; Admin 1–N OwnerApplication đã review.
- User 1–N Venue; Venue 1–N Field.
- Field 1–N FieldPriceSlot và 1–N FieldMaintenance.
- User 1–N Booking; Field 1–N Booking.
- Booking 1–N BookingPriceDetail.
- Booking 1–N BookingContribution.
- BookingContribution 1–N Payment attempt.
- Payment 1–N Refund.
- Booking 1–0..1 Match.
- Match 1–N MatchParticipant.
- MatchParticipant 1–0..1 BookingContribution đang hoạt động.

## 5.16. Ràng buộc cần kiểm tra trong service và transaction

- Không trùng booking hoặc lịch bảo trì.
- Không chồng khung giá và phải phủ đủ thời gian booking.
- Không thu vượt `total_amount`.
- Không có hai payment `SUCCESS` cho cùng một contribution.
- Không refund vượt số tiền payment đã thành công.
- Không nhận quá số vị trí còn thiếu hoặc quá sức chứa field.
- Không tạo hai match cho cùng một booking.
- Không xử lý IPN/refund callback lặp lại hai lần.

## 5.17. Tài liệu và migration còn phải tạo

- Cập nhật ERD tại `docs/diagrams/erd.png` sau khi model được duyệt.
- Review kiểu dữ liệu, filtered index, check constraint và locking với SQL Server.
- Chỉ tạo migration sau khi schema này được xác nhận; không tạo hoặc sửa migration thủ công.
