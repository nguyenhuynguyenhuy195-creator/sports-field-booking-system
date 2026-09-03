# CONTRACT – PHASE 2 ADMIN OPERATIONS

**Trạng thái:** ACCEPTED – cập nhật sau Step 2.1 và Step 2.2
**Baseline áp dụng:** `ac955c2`, Alembic `a6d8e4f2c913`
**Tài liệu liên quan:** `docs/11-roadmap.md`, `docs/10-decision-log.md`

## 1. Mục tiêu và phạm vi

Phase 2 tách các Admin Operations còn lại thành module nghiệp vụ độc lập, thay
vì tiếp tục mở rộng trang `/admin/monitoring` đang gộp nhiều loại dữ liệu.
Booking là workspace điều tra cho Payment/Refund liên quan; không tạo module
Payment hoặc Refund primary riêng.

Contract này chỉ chốt kiến trúc, trách nhiệm và guardrail. Nó không tự tạo
route, template, service, CSS, JavaScript, migration hoặc thao tác dữ liệu.
Admin Foundation, Owner Console và Location & Map đã nghiệm thu vẫn là nền
tảng cần giữ nguyên.

Nguyên tắc tổ chức:

- List là màn hình vận hành nhanh: tìm, lọc, nhận diện trạng thái và mở hồ sơ.
- Detail là màn hình điều tra đầy đủ: đọc dữ liệu liên quan và dấu vết đã có.
- Một màn hình chỉ có một thực thể vận hành chính; không dùng tab/focus để biến
  Booking list thành Match list hoặc danh sách Payment/Refund độc lập.
- Các engine Booking, Payment, Refund và Matchmaking hiện có là source of
  truth. Phase 2 trình bày hoặc gọi đúng capability đã được chấp thuận, không
  viết lại lifecycle hay sửa trực tiếp dữ liệu lịch sử.

## 2. Điều hướng Admin

Sidebar Phase 2 có cấu trúc sau. Nhãn và thứ tự này là chuẩn cho các module
mới; sidebar Admin Foundation hiện hữu chỉ được thay đổi trong bước điều hướng
được phê duyệt riêng.

```text
Tổng quan

KIỂM DUYỆT
  Duyệt chủ sân
  Kiểm duyệt cơ sở

VẬN HÀNH
  Lịch đặt sân
  Kèo chơi

TÀI CHÍNH
  Đối soát (chỉ sau khi Step 2.6 được implement)

HỆ THỐNG
  Tài khoản
```

- Một link Phase 2 chỉ được hiển thị/active như module vận hành sau khi module
  đó đã được implement và accepted; không tạo dead link, placeholder page hay
  trang Settlement giả.
- Tiến độ link: Step 2.1 đã đưa link Booking vào vận hành; Match chỉ trở thành
  operational ở Step 2.3 và Settlement/Đối soát chỉ ở Step 2.6. Không tạo link
  Thanh toán hoặc Hoàn tiền riêng.
- Khi đã vận hành, mỗi link dẫn tới module dedicated tương ứng, không dẫn tới
  một `focus` của `/admin/monitoring`; chỉ link của module hoặc detail đang xem
  được active.
- Tổng quan, kiểm duyệt, tài khoản và các route Admin Foundation giữ nguyên
  permission, action, URL và hành vi accepted.

## 3. Kiến trúc route

Route đích của Phase 2 là:

| Module | List | Detail | Khóa định danh |
| --- | --- | --- | --- |
| Booking Operations | `/admin/bookings` | `/admin/bookings/<booking_code>` | `booking_code` |
| Match Operations | `/admin/matches` | `/admin/matches/<id>` | `Match.id` |
| Settlement Operations | `/admin/settlements` | `/admin/settlements/<id>` | `Settlement.id` khi Step 2.6 chốt model |

Quy tắc route:

- Tất cả route Phase 2 yêu cầu `ADMIN`; detail không được suy quyền từ việc
  biết mã hoặc id.
- URL list dùng query string cho filter, search và page; link pagination,
  clear filter và detail/back phải giữ filter đang có khi điều đó hữu ích cho
  luồng điều tra.
- Booking Detail là nơi Admin điều tra Payment/Refund: contribution, immutable
  Payment history, immutable Refund history, quan hệ Payment ↔ Refund,
  transaction IDs, attention state, historical events và số tiền hiện tại.
  Không có route primary `/admin/payments`, `/admin/payments/<id>`,
  `/admin/refunds` hoặc `/admin/refunds/<id>`.
- Booking ↔ Match chỉ dùng canonical detail sau khi Step 2.3 được accepted;
  từ Step 2.6, Booking/Payment/Refund có thể liên kết với Settlement theo
  thiết kế được duyệt.
- `/admin/monitoring` là Admin Foundation accepted và có thể tạm thời tồn tại
  để compatibility trong Phase 2. Không tiếp tục xây capability Phase 2 mới
  tại đó. Khi một module dedicated được accepted, legacy link/URL liên quan
  nên được redirect hoặc map tới canonical route nếu an toàn, có kiểm thử và
  được thực hiện trong đúng step. Đến cuối Phase 2, `/admin/monitoring` không
  còn là workspace Admin Operations chính; không duy trì hai primary UI cạnh
  tranh cho cùng một module. Contract này không triển khai redirect.
- Các route Settlement được dành trước trong contract; không được đăng ký hay
  giả lập dữ liệu trước Step 2.6.

## 4. Ranh giới Phase 2.1 đến 2.6

### Step 2.1 – Booking Operations

Chủ thể chính là `Booking`. List toàn hệ thống cho phép tìm/lọc theo dữ liệu
Booking thực có: mã booking, khách, Venue, Field, Sport, ngày/giờ, mode,
status và các attention state đã được định nghĩa. Bộ lọc vị trí theo thứ tự:

```text
Tỉnh/Thành phố → Phường/Xã/Đặc khu → Cơ sở → Sân
```

Province/Ward dùng catalog hành chính canonical và phải giữ fallback đọc dữ
liệu Venue legacy; Venue/Field luôn là dữ liệu thực có trong hệ thống. Step
2.1 không là nơi tạo payment/refund action hoặc settlement.

### Step 2.2 – Booking Detail

Chủ thể chính vẫn là một `Booking`. Detail là hồ sơ điều tra read-only, tập
trung vào booking context, contribution, Payment/Refund liên quan, Match liên
quan, status hiện tại và các sự kiện có timestamp được lưu.

Timeline chỉ được nêu những sự kiện có dữ liệu thời gian nguồn. Không dùng
`updated_at`, giờ kết thúc sân, hoặc một status hiện tại để suy diễn một mốc
lifecycle không được lưu. Cancellation reason được hiển thị khi bản ghi có.
Step này là nơi điều tra Payment/Refund theo Booking context, nhưng không tạo
Payment/Refund primary module hoặc Settlement detail thay thế.

### Step 2.3 – Match Operations

Chủ thể chính là `Match`. List và detail trình bày kèo, Booking liên quan,
creator, participant/contribution context, thời gian, capacity và status.
Moderation hoặc exception action chỉ được thêm khi có policy, permission và
service capability tương ứng; không dùng Admin UI để sửa participant,
contribution hoặc booking lifecycle thủ công.

### Step 2.4 – Dedicated Payment Operations (đã loại khỏi implementation scope)

Không implement list/detail hay route Payment primary. `Payment` vẫn được giữ
nguyên là backend engine, database record và immutable financial history có
test coverage. Admin tra cứu và điều tra Payment trong `/admin/bookings` và
`/admin/bookings/<booking_code>`; Payment attention vẫn giữ đúng nghĩa,
trong đó `PENDING` là chờ completion/confirmation, không phải failure.

### Step 2.5 – Dedicated Refund Operations (đã loại khỏi implementation scope)

Không implement queue/detail hay route Refund primary. `Refund` vẫn được giữ
nguyên là backend engine, database record và immutable financial history có
test coverage. Admin điều tra Refund, Payment gốc, reason, status và metadata
trong Booking Detail; không xóa, sửa amount/reason lịch sử hoặc tự chuyển
trạng thái Refund trong database.

### Step 2.6 – Settlement / đối soát chủ sân

Chủ thể chính là Settlement. Đây là ranh giới duy nhất của Phase 2 cho model,
engine, queue và payout sandbox/simulated payout, theo ADR-031. Trước Step
2.6, không thêm cột, migration, receiving account, payout button hay số liệu
Owner payable giả.

Khi Step 2.6 bắt đầu, thiết kế phải chốt riêng relation Settlement với
Booking/Payment/Refund, trạng thái `PENDING`, `ELIGIBLE`, `SETTLED`, `FAILED`,
`ON_HOLD`, action được phép, idempotency, audit và migration nếu thật sự cần.

## 5. Trách nhiệm list và detail

| Module | List chịu trách nhiệm | Detail chịu trách nhiệm | Không thuộc module |
| --- | --- | --- | --- |
| Booking | Tóm tắt lịch, location, khách, mode, status, tiền online/tại sân, attention | Điều tra đầy đủ Booking và liên kết nghiệp vụ | Xử lý gateway/refund/payout trực tiếp |
| Match | Tóm tắt kèo, Booking context, participant count, status | Thành phần kèo và mốc đã ghi nhận | Sửa Booking hoặc Payment |
| Settlement | Queue/status đối soát và payout khi đã có engine | Căn cứ online, exception và payout audit | Thu phần tiền trả tại sân |

List desktop ưu tiên table-first, mỗi dòng mở đúng detail. List mobile chuyển
thành card có các trường tóm tắt tương đương, không giấu status/attention hay
liên kết điều tra. Không đặt danh sách Payment/Refund lồng trong từng Booking
row; Payment/Refund được điều tra read-only trong Booking Detail.

## 6. Quy tắc UI dùng chung

- Tham chiếu tinh thần Tabler về mật độ, hierarchy, badge, toolbar và
  responsive; không thêm dependency Tabler hoặc đổi Flask/Jinja/Bootstrap.
- Một page có page heading rõ mục tiêu, toolbar filter compact, result summary,
  empty state, table/card và pagination nhất quán.
- Desktop: table có cột ổn định, không dùng nhiều nested card/accordion để
  chứa dữ liệu vận hành. Mobile: card có label rõ cho từng thông tin.
- Filter theo logic phụ thuộc được xếp theo luồng đọc, đặc biệt
  Province → Ward → Venue → Field. `Áp dụng` áp dụng toàn bộ form; việc cập
  nhật Ward theo Province phải dùng source/API canonical đã accepted, không
  tạo danh sách hard-code.
- Status dùng Vietnamese business wording, `status-badge` và màu có ý nghĩa
  nhất quán; không chỉ truyền nghĩa bằng màu.
- Detail có thể dùng section, definition list, chronology và related-record
  list; không biến một detail thành dashboard hoặc tạo action không có policy.
- Giữ accessibility của Admin Foundation: heading hierarchy, label cho input,
  keyboard focus, aria-current, trạng thái không chỉ bằng màu và responsive
  không overflow ngang.

### Định nghĩa attention state

Attention có nghĩa: **Admin nên kiểm tra hoặc theo dõi bản ghi này**. Attention
không tự động đồng nghĩa với system failure và không thay đổi lifecycle/enum.

- Payment attention gồm `PENDING`, `FAILED`, `CANCELLED`, `EXPIRED`.
  `PENDING` nghĩa là đang chờ completion/confirmation, **không phải** failure.
- Refund attention gồm `PENDING`, `PROCESSING`, `FAILED`.
- `SUCCESS` không phải attention state. Refund chưa `SUCCESS` không được trình
  bày là đã hoàn thành.

## 7. Guardrail tài chính và nghiệp vụ

Các quy tắc sau bắt buộc ở mọi list/detail/summary Phase 2:

```text
paid_amount = số tiền online ròng hiện đang được ghi nhận
balance_due_at_venue = total_amount - paid_amount
```

- Không hard-code phần trả tại sân là 70%. Số tiền phải được tính từ hai giá
  trị của bản ghi Booking.
- `DIRECT_BOOKING` và `FIND_PLAYERS` mới thường có `DEPOSIT_30`; đây không
  biến mọi Booking thành cùng một tỷ lệ trình bày.
- `FIND_OPPONENT` hợp lệ có thể mới thu 15% tổng tiền online từ creator. Ví dụ
  `total_amount = 300.000`, `paid_amount = 45.000` thì
  `balance_due_at_venue = 255.000`.
- `LEGACY_FULL_ONLINE` là lịch sử thanh toán online toàn phần, phải hiển thị
  khác `DEPOSIT_30`; không gắn nhãn cọc 30% cho dữ liệu legacy.
- Payment/Refund là lịch sử độc lập, idempotent và không bị xóa/ghi đè chỉ để
  làm đẹp số tổng hợp. Payment `SUCCESS` và Refund `SUCCESS` là các chứng cứ
  giao dịch thành công; trạng thái pending/processing/failed/cancelled/expired
  phải được biểu diễn đúng nghĩa vụ hiện tại.
- Tiền trả trực tiếp tại sân không trở thành một Payment online chỉ vì cần
  hiển thị balance. Settlement chỉ đối soát các khoản online hệ thống có căn
  cứ ghi nhận.
- Payment `SUCCESS` không đồng nghĩa Owner đã được settlement/payout.

## 8. Hành động được phép và bị cấm

### Được phép trong Phase 2

- Xem, search, filter, paginate và liên kết chéo các bản ghi mà Admin được
  quyền xem.
- Hiển thị rõ attention, status và dữ liệu lịch sử nguồn.
- Duy trì các action Admin Foundation đã được accepted trong chính module của
  chúng: duyệt chủ sân, kiểm duyệt Venue và quản lý trạng thái tài khoản.
- Ở Step 2.6, thực hiện đúng những action Settlement/Payout đã được thiết kế,
  có engine, idempotency và audit phù hợp.

### Bị cấm nếu chưa có một thiết kế/engine được duyệt riêng

- Sửa `Booking.status`, `total_amount`, `deposit_amount`, `paid_amount`,
  `payment_policy`, contribution hoặc Booking mode bằng form Admin.
- Đánh dấu Payment/Refund thành công/thất bại, sửa mã provider, hoặc tạo/xóa
  giao dịch trực tiếp từ Admin UI/database.
- Sửa participant/match lifecycle hay tạo refund để giải quyết bằng tay một
  exception của Booking/Match.
- Viết lại Payment, Refund, Booking hoặc Matchmaking engine chỉ để phục vụ UI.
- Tạo Settlement/Payout, receiving account, schema hoặc migration trước Step
  2.6.
- Mở rộng Phase 2 sang moderation nâng cao, dispute, notification hoặc báo
  cáo kế toán khi step hiện tại chưa được acceptance.

## 9. Trình tự triển khai

Mỗi step được tách thành một prompt/PR nhỏ, review được độc lập:

1. Step 2.1 Booking Operations — DONE / ACCEPTED.
2. Step 2.2 Booking Detail — DONE / ACCEPTED.
3. Tách Match Operations Step 2.3, không đổi matchmaking engine.
4. Step 2.4 và 2.5 được giữ số lịch sử nhưng đã loại khỏi dedicated Admin UI;
   Payment/Refund engine và history vẫn được bảo toàn trong Booking Detail.
5. Audit riêng schema và architecture trước Step 2.6; chỉ sau approval mới tạo
   Settlement/Payout engine, UI và migration nếu cần.

Sau khi các Step còn lại 2.3 và 2.6 được accepted, thực hiện UI consistency,
full regression và polish cuối nếu cần. Đây là phần hoàn tất Phase 2, không
phải một Step 2.7 độc lập.

Không gộp nhiều step trong một thay đổi. Bất kỳ phát hiện schema thiếu,
business-rule mơ hồ hoặc requirement mâu thuẫn phải được báo cáo để quyết định
trước, thay vì tự suy diễn trong code.

## 10. Workflow nghiệm thu

Mỗi module phải đi qua workflow sau:

1. Xác nhận scope của đúng Step và các guardrail trong document này.
2. Audit source/model/service hiện có; phân biệt read-model UI với thay đổi
   engine/lifecycle.
3. Thiết kế route, query/filter, URL compatibility và permission trước khi
   chỉnh template/CSS/JS.
4. Implement theo phạm vi nhỏ nhất; không sửa code accepted không liên quan.
5. Thêm focused integration tests cho route permission, list/detail,
   search/filter/pagination, financial wording và edge case của module.
6. Chạy targeted tests, full regression, `git diff --check` và `flask db
   check`; kiểm tra Alembic head/current. Nếu có migration, chỉ chấp nhận khi
   nó đã được duyệt trong Step 2.6 hoặc một quyết định schema riêng.
7. Review desktop/mobile bằng UI thực tế: table/card, filter toolbar, badge,
   pagination, empty state, accessibility và link detail/back.
8. Review `git diff`/`git status`, xác nhận không có Phase khác bị lẫn, sau đó
   mới xin acceptance. Không commit khi chưa được yêu cầu.

## 11. Tiêu chí hoàn thành kiến trúc

Một step còn implementation scope được xem là hoàn thành khi module dedicated
của chính nó hoạt động, các guardrail tài chính còn đúng, engine đã có không
regression, scope tiếp theo không bị kéo vào, và validation trong workflow
nghiệm thu đều có bằng chứng.
