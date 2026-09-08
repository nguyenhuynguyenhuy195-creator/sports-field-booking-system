> **Ghi chú scope 08/09/2026:** Báo cáo này lưu kết quả audit trước khi GVHD chốt MOCK-only. Kết luận NOT READY và các ưu tiên MoMo bên dưới là lịch sử, không phải kết luận nghiệm thu hiện tại. Toàn bộ issue đã được phân loại lại và kết quả sửa nằm trong [AUDIT_REPORT_FINAL.md](AUDIT_REPORT_FINAL.md).

# Executive Summary

**Kết luận: NOT READY — cần xử lý các lỗi P0/P1 trước khi tuyên bố hoàn tất toàn bộ MVP.**

Audit ngày 08/09/2026, trên working tree thực tế tại `E:\HK3-2026 (NĂM 3)\ĐỒ ÁN NGÀNH\sports-field-booking-codex\SOURCE CODE DO AN NGANH`, HEAD `6f7a354008ec0739ee01995e4d45e3e3c196c9e4`. Kết luận bao gồm thay đổi chưa commit có sẵn, không chỉ nội dung HEAD.

**Chỉ tạo báo cáo này. Không sửa production code, test, migration, cấu hình, dữ liệu SQL Server; không commit/push.** Các phép tái hiện dùng SQLite trong bộ nhớ, tài khoản giả và transport MoMo giả. Các truy vấn SQL Server chỉ đọc metadata và số lượng tổng hợp. Không gọi thanh toán/refund thật.

Kết quả xác nhận:

- Full suite: **431 total, 431 pass, 0 fail, 0 skipped; 196,27 giây**. Lệnh: `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider`, với `PYTHONDONTWRITEBYTECODE=1`. Exit code 0. Không sửa test để làm pass.
- 18 bảng nghiệp vụ, 17 migration, một head `a6d8e4f2c913`; SQL Server hiện tại ở đúng head. Alembic `compare_metadata(compare_type=True)` trả `[]` sau khi loại bảng SSMS `sysdiagrams`.
- SQL Server có 54 CHECK và 32 FK; không có CHECK/FK bị disable hoặc không trusted. Tên CHECK khớp model; đối chiếu biểu thức đã tính đến cách SQL Server diễn giải `BETWEEN`/`IN`.
- Dựng từ rỗng qua đủ 17 migration trên SQLite trong bộ nhớ: thành công. **Dựng mới SQL Server và nâng cấp dữ liệu legacy thực tế: NEEDS VERIFICATION**; không áp migration lên DB đang dùng.
- 43 template parse được bằng Jinja; không thấy endpoint literal `url_for` không tồn tại. Toàn bộ 17 JS và 3 CSS có tham chiếu từ template.
- Các phép tái hiện ngoài suite xác nhận lỗi checkout sai người trả, MOCK vượt lựa chọn provider, không nhả suất khi payment thất bại, refund FAILED bị kẹt, response refund không đối chiếu giao dịch, giá hợp lệ phía Owner bị từ chối ở booking, và kiểm tra ảnh chỉ dựa vào chữ ký file.

**Điểm chặn chính:** H01, H02, H03. Suite xanh không phủ những tổ hợp này. H04–H07 cần xử lý cho luồng thanh toán/refund và đồng thời trên SQL Server.

`REPORT_GUIDE.md` không có trong cây thư mục đồ án đã tìm kiếm. Đã dùng yêu cầu audit được cung cấp, `AGENTS.md`, README, các tài liệu scope/business/workflow/database/architecture/test/ADR/roadmap và source thực tế. Không suy diễn yêu cầu từ tài liệu bị thiếu.

Phạm vi và mức chứng cứ:

- Kiểm kê toàn cây repository, routes, imports/calls, model metadata, form, liên kết template/JS, migration graph và tất cả file test bằng đọc source/AST; đọc sâu các nhánh mutation, payment/refund/match và negative tests liên quan.
- Bằng chứng source, phép tái hiện cô lập và kiểm tra DB hiện tại được phân biệt trong từng issue. Kiểm kê tĩnh không tương đương mọi nhánh đã chạy E2E.
- Chưa kiểm tra browser E2E desktop/mobile, MoMo Sandbox thật, tải đồng thời SQL Server, hiệu năng tải lớn, hay render báo cáo Word/PDF. Các vùng này là **NEEDS VERIFICATION**, không được suy ra PASS từ pytest.
- `OK` trong ma trận nghĩa là trace đủ các lớp cho hành vi được ghi ở dòng đó và có test tương ứng; không phải chứng nhận không còn lỗi ở toàn module.

# Architecture Observed

Hệ thống là Flask monolith với application factory `app/__init__.py`, SQLAlchemy ORM, Flask-Login, Flask-WTF/CSRF, Flask-Migrate/Alembic. Frontend server-rendered Jinja/Bootstrap, JavaScript thuần tăng cường tương tác. Không có SPA hay repository abstraction riêng: service trực tiếp truy vấn `db.session`.

| Thành phần | Vai trò thực tế và chứng cứ |
|---|---|
| `run.py`, `config.py`, `app/__init__.py` | Chọn development/testing, nạp env, bắt buộc SECRET_KEY, khởi tạo DB/login/CSRF, đăng ký 14 blueprint và CLI |
| `app/routes/` | Nhận path/query/form/JSON, role guard, gọi service; trả HTML, redirect hoặc JSON. Admin/Owner route còn dựng read-model và nhãn hiển thị |
| `app/forms/` | WTForms kiểm tra email, độ dài, lựa chọn, thời gian, số lượng, biểu mẫu có prefix; service lặp lại các kiểm tra nghiệp vụ chính |
| `app/services/auth.py`, `owner_application.py` | Chuẩn hóa tài khoản, hash password, tạo đơn PENDING; duyệt đơn và chuyển role trong cùng commit |
| `venue.py`, `field.py`, `pricing.py`, `maintenance.py` | Owner ownership, public ACTIVE, admin moderation, danh mục sân, khung giá/độ phủ và bảo trì |
| `booking.py`, `availability.py`, `contribution.py` | Kiểm tra thời gian/trùng lịch, snapshot giá, cọc 30%, giữ chỗ 15 phút; chia creator/opponent và xử lý lifecycle |
| `payment.py`, `refund.py`, `integrations/momo.py` | MOCK đồng bộ; MoMo create/IPN/return, HMAC; refund intent, submit/query, idempotency; có khoảng trống H01–H07 |
| `matchmaking.py` | Một match/booking, giữ suất đối thủ, phê duyệt người ghép, chia sẻ Zalo có điều kiện, hết hạn/rút/đóng bài |
| `owner.py`, `owner_finance.py`, `admin.py` | Read-model dashboard/lịch/tài chính/giám sát; Admin được đổi trạng thái tài khoản nhưng không có thao tác xóa lịch sử giao dịch |
| `media.py`, `models/media_image.py` | Upload filesystem dưới MEDIA_ROOT, metadata DB, cover/fallback, quyền đọc theo trạng thái và owner |
| `geocoding.py`, `administrative_unit.py`, `sport_catalog.py` | Catalog tỉnh/xã và sport/type; Nominatim có cache/timeout/rate pacing trong process; Leaflet hiển thị tọa độ đã xác nhận |
| `app/models/` | 18 bảng, CHECK/unique/filtered index, Decimal và UTC timestamp; quan hệ ORM, các thuộc tính trình bày như `balance_due_at_venue` |
| `migrations/` | Chuỗi Alembic có backfill dữ liệu legacy, seed catalog, cột cọc/vị trí/checkout/contact/media |
| `app/cli/` | Tạo admin, expire booking, complete booking, expire participant, funding legacy, xử lý refund MoMo và reset demo |
| `tests/` | SQLite độc lập từng test; HTTP integration qua Flask test client, service tests, model contracts, fake MoMo/geocoding; không phải browser automation |
| `database/` | SQL dữ liệu demo đã ẩn danh và README phục hồi; không chứa file ảnh vật lý |

Luồng thực tế: Browser → route/WTForm/role guard → service → SQLAlchemy model/SQL Server → commit → redirect/render. IPN đi vào `payments.momo_ipn` và được miễn CSRF, nhưng phải qua HMAC/đối chiếu payment. CLI gọi cùng service. Các GET không được coi là job tự đồng bộ database: nhiều màn hình dùng effective status chỉ để đọc.

# Cross-layer Traceability Matrix

Đường dẫn dưới đây tính từ repository root. Tên hàm và test là điểm tra cứu chính; phụ lục có inventory endpoint/model/test.

| Feature | Frontend | Route/API | Service | Model/Table | Business Rule | Test | Status |
|---|---|---|---|---|---|---|---|
| Đăng ký/đăng nhập/đăng xuất | `auth/*.html`, `base.html` | `auth.register/login/logout` | `auth.register_user/find_user_by_email` | User/users | Email normalized+unique, password hash, tài khoản ACTIVE | `test_auth.py`, `test_user_model.py` | OK |
| Gửi/theo dõi đơn Owner | `owner_applications/*.html` | `owner_applications.create/mine` | submit/list applications | OwnerApplication, User | USER, một PENDING/user | `test_owner_applications.py`, `test_owner_application_model.py` | OK |
| Duyệt đơn Owner | `admin/owner_applications.html` | `admin.review_owner_application_route` | `review_owner_application` | owner_applications/users | PENDING → APPROVED/REJECTED; approve đổi role cùng transaction | `test_admin_approves_application_and_promotes_user`, rollback test | NEEDS REVIEW — H04 đồng thời |
| Tạo/sửa/duyệt cơ sở | `owner/venues/*.html`, `admin/venues.html` | `venues.owner_create/owner_edit/admin_moderate` | create/update/moderate venue | venues/provinces/wards | Owner scope; tạo PENDING; sửa identity/location cần duyệt lại | `test_venues.py` | NEEDS REVIEW — H04 |
| Địa chỉ và geocode | `owner/venues/form.html`, location picker | `venues.administrative_wards/owner_geocode` | resolve address/geocode | provinces/wards/venues | Mã xã thuộc tỉnh; ghim xác nhận trước lưu | `test_venues.py`, `test_geocoding.py` | OK ở contract có mock; external E2E chưa xác minh |
| Tìm sân/bản đồ/gần tôi | `venues/index.html`, map/filter/nearby JS | `venues.index/detail` | `search_public_venues`, Haversine | Venue/Field/FieldType/Sport/PriceSlot | ACTIVE, filter kết hợp, không lưu vị trí user | `test_venues.py`, `test_multisport_maps.py` | OK ở source/test; tải lớn M11 |
| Quản lý sân con | `owner/fields/*.html` | `fields.owner_*` | create/update/get owner field | fields/field_types | Tên unique/venue, inactive ban đầu, không đổi type khi có history | `test_fields.py`, `test_multisport_maps.py` | NEEDS REVIEW — H04 đồng thời |
| Giá và bật sân | `owner/pricing/*.html` | `pricing.owner_*` | create/update slot, set activation | field_price_slots/fields | Không overlap, có giá trước ACTIVE | `test_pricing.py` | INCONSISTENT — H04, M03 |
| Bảo trì | `owner/maintenance/*.html` | `maintenance.owner_*` | create/cancel maintenance | field_maintenances/fields/bookings | Khóa field; không trùng booking; [start,end) | `test_maintenance.py`, `test_bookings.py` | OK ở tuần tự; SQL Server race NEEDS VERIFICATION |
| Availability/time quote/quote | `bookings/form.html`, `booking-flow.js` | `bookings.availability/time_quote/quote` | availability/quote/pricing | field/venue/price/maintenance/booking | Read-only, giá DB, bước 30 phút | `test_bookings.py` | INCONSISTENT — M03/M04 |
| Tạo booking/snapshot | `bookings/form.html` | `bookings.create` | `create_booking` | bookings/price_details/contributions | Tối thiểu 60 phút, trước 1 giờ, tối đa 30 ngày, giữ 15 phút | `test_user_creates_confirmed_hold_with_price_snapshot`, conflict/rollback tests | NEEDS REVIEW — M03; race thực tế chưa chạy |
| Cọc MOCK | booking/match detail | `payments.pay_mock/top_up_mock` | mock payment/top-up | Payment/Contribution/Booking | Chỉ payer của contribution, không thu dư/lặp | `test_payments.py` | MISSING VALIDATION — H01 |
| MoMo checkout | booking/match detail | `payments.pay_momo` | start/checkout | payments/contributions | Pending attempt đúng payer/hold | `test_momo_checkout_retries_same_request_after_network_error` | INCONSISTENT — H02, M10 |
| MoMo IPN và return | return redirect/chi tiết | `payments.momo_ipn/momo_return` | process/inspect/verify | Payment/Booking/Contribution/Participant | HMAC, amount/order/request; return không thu tiền | `test_momo_payments.py`, `test_booking_journey_ux.py` | INCONSISTENT — H03, H07 |
| Hủy bởi creator | `bookings/detail.html` | `bookings.cancel` | cancel/apply creator policy | Booking/Contribution/Refund/Match | Creator mất cọc, đối thủ không có lỗi được hoàn | `test_refunds.py` | NEEDS REVIEW — nhánh MoMo H05/H06 |
| Hủy bởi Owner | booking owner detail/modal | `bookings.owner_cancel` | cancel/apply owner refunds | Booking/Payment/Refund | Hoàn 100% đã thu; chờ refund mới CANCELLED | `test_refunds.py`, MoMo refund test | INCONSISTENT — H05/H06, M01/M02 |
| Tạo kèo | `matches/form.html`, booking detail | `matches.create` | validate/create match | Match/Booking | Đúng owner/mode/cọc, một match/booking | `test_matchmaking.py` | OK |
| Nhận đối thủ | `matches/detail.html` | `matches.join`, payment endpoints | request/reserve/payment | Participant/Contribution/Payment | Giữ tối đa min(15 phút, giờ bắt đầu), success → JOINED/CONFIRMED | `test_opponent_request_payment_confirms_match_and_booking` | INCONSISTENT — H02/H03 |
| Ghép thêm người | match detail | `matches.join/accept/reject` | request/decide/capacity | Match/Participant | Creator duyệt, JOINED không cọc online, không vượt required_players | `test_find_players_join_with_zalo_has_no_online_payment` | OK ở luồng đã test |
| Rút/đóng bài/hết hạn | match detail/mine, countdown | withdraw/close; CLI expire | withdraw/close/expire | Match/Participant/Contribution | Mất cọc khi tự rút; creator giữ booking khi đóng bài | `test_matchmaking_fixes.py`, `test_refunds.py` | NEEDS REVIEW — H02; ngoại lệ người thay thế ở BR-C02 |
| Liên hệ và lịch cá nhân | match detail, bookings index | matches.detail/mine, bookings.index | user requests/contact | Match/Participant/User | Contact snapshot; chỉ hai bên sau JOINED; không cấp quyền booking | `test_paid_opponent_appears_in_match_workspace_and_contacts_stay_private` | OK theo trạng thái UI trước giờ bắt đầu |
| Owner dashboard/schedule | `owner/dashboard.html`, `schedule.html` | `owner.dashboard/schedule` | owner summary/schedule | Venue/Field/Booking/Maintenance | Owner scope, effective status, bốn batch reads lịch | owner dashboard/schedule tests | OK ở service/HTML; layout E2E NEEDS VERIFICATION |
| Owner finance | `owner/finance.html` | `owner.finance` | owner finance summary | Booking/Payment/Refund | Tiền online và còn tại sân; không settlement | `test_owner_finance.py` | NEEDS REVIEW — M08 |
| Admin account | `admin/accounts.html` | accounts/status | admin account services | users | Không tự khóa, không khóa Admin khác, không xóa history | `test_admin.py` permission+CSRF tests | OK |
| Admin booking/match monitoring | `admin/bookings/*`, `admin/matches/*` | canonical list/detail | admin read-model | Booking/Contribution/Payment/Refund/Match | Read-only, audit events từ timestamps đã lưu | admin integration/polish tests | NEEDS REVIEW — M08/M09 |
| Ảnh cơ sở/sân | media manager/gallery | `media.*` | media validate/store/cover/delete | media_images + filesystem | Owner scope, type/size, one cover | `test_media.py` | MISSING VALIDATION — M05 |
| Dựng DB | CLI, không cần UI | Alembic | migrations/backfill | 18 tables | base→head, seed catalog | Audit SQLite migration smoke | NEEDS REVIEW — SQL Server rebuild chưa chạy |
| Query payment thất lạc IPN | Không có | Không có caller/CLI | Chỉ có `MomoClient.query_payment` | Payment tồn tại | Phục hồi provider success chưa ghi nhận | Không có test orchestration | MISSING BACKEND — H07 |

# Critical Issues

Không ghi nhận issue mức Critical đã đủ bằng chứng trong phạm vi **đồ án MOCK/Sandbox**. Điều này không hạ mức ưu tiên P0 của lỗi sai checkout/đi vòng payment. Không đánh giá khả năng vận hành tiền thật.

# High Issues

## H01 — MOCK vẫn ghi nhận cọc khi đã chọn MoMo

- **ID:** H01
- **Severity:** High — **P0**
- **Category:** Authorization / payment provider validation
- **Files:** `app/routes/payments.py:40`, `app/services/payment.py:57`, `app/services/payment.py:88`, `app/templates/bookings/detail.html:344`, `app/templates/matches/detail.html:222`.
- **Evidence:** Template chọn MoMo theo `momo_enabled`; route MOCK và service chỉ kiểm tra payer/state/deadline, không kiểm tra provider đang được cho phép. Tái hiện trên app testing đặt `MOMO_ENABLED=True`, đăng nhập payer rồi POST `/bookings/<code>/contributions/<id>/payments/mock`: HTTP 302, tạo payment `MOCK/SUCCESS`, contribution `PAID`.
- **Problem:** Ẩn nút MOCK không chặn endpoint; người dùng vẫn có thể hoàn tất khoản cọc mô phỏng khi hệ thống đang chạy luồng MoMo.
- **Impact:** Demo Sandbox có thể nhận booking/match như đã cọc mà không có giao dịch MoMo. Quyền sở hữu vẫn được kiểm tra; đây không phải thu cọc hộ người khác.
- **Recommended fix:** Chốt policy bật provider ở backend, chặn mock ngoài chế độ cho phép; test trực tiếp endpoint với MoMo enabled và bảo đảm không tạo payment/đổi trạng thái. Chưa thực hiện sửa.

## H02 — Người giữ suất mới nhận checkout của người cũ

- **ID:** H02
- **Severity:** High — **P0**
- **Category:** Payment idempotency / match lifecycle
- **Files:** `app/services/payment.py:384`, `app/services/matchmaking.py:914`, `app/services/matchmaking.py:1142`, `tests/integration/test_matchmaking.py:431`, `tests/integration/test_momo_payments.py:543`.
- **Evidence:** `_start_momo_checkout` tìm payment PENDING chỉ theo `contribution_id`, provider và status; không theo payer/lần giữ suất. Expiry nhả contribution để người khác dùng nhưng không đóng attempt cũ. Tái hiện A nhận suất → tạo checkout → expire sau 16 phút → B nhận cùng contribution → tạo checkout: `same_payment=True`, `old_payer=3`, `new_payer=4`, contribution thuộc B nhưng payment vẫn payer A.
- **Problem:** Idempotency theo contribution kéo dài qua các lần thay người. Trả nguyên checkout_url cũ cho người mới.
- **Impact:** B mở đơn của A; callback gặp `contribution.user_id != payment.payer_id` nên nhánh late refund thay vì ghi JOINED cho B. Luồng cọc đối thủ bị hỏng mặc dù giữ suất mới hợp lệ.
- **Recommended fix:** Ràng buộc checkout với payer và generation/attempt của suất; đóng hiệu lực attempt cũ khi hết hạn/rút, vẫn tiếp nhận late IPN để hoàn đúng người. Test expiry, withdrawal, same-user retry và new-user retry riêng biệt.

## H03 — BUSINESS RULE CONFLICT: payment thất bại không giải phóng suất

- **ID:** H03
- **Severity:** High — **P0** vì khác rule người dùng xác nhận
- **Category:** Business rule / state transition
- **Files:** `app/services/payment.py:286`, `app/services/matchmaking.py:1072`, `app/services/matchmaking.py:1089`, `app/routes/matches.py:391`.
- **Evidence:** Nhánh IPN `result_code != '0'` chỉ đặt Payment FAILED và commit. Tái hiện IPN có HMAC đúng và `resultCode=1006`: `Payment=FAILED`, participant vẫn `ACCEPTED_AWAITING_PAYMENT`, contribution vẫn giữ `user_id`, payment_due_at vẫn tồn tại.
- **Problem:** Rule yêu cầu “thất bại/hết hạn → giải phóng suất”; implementation giữ suất cho retry đến deadline hoặc user tự rút.
- **Impact:** Người khác không thể nhận suất ngay khi thanh toán đã thất bại; UI kèo có thể vẫn mở nhưng service báo đủ người đang giữ chỗ.
- **Recommended fix:** Áp dụng rule đã chốt cho kết quả thất bại cuối cùng trong cùng transaction; phân biệt lỗi kết nối chưa xác định với provider failure. Test failed IPN → người khác nhận ngay, cùng late success sau release.

## H04 — Khóa cập nhật không có hiệu lực SQL Server ở một số service

- **ID:** H04
- **Severity:** High — **P1**
- **Category:** Concurrency / transaction
- **Files:** `app/services/pricing.py:353`, `app/services/pricing.py:106`, `app/services/owner_application.py:140`, `app/services/venue.py:598`, `app/services/venue.py:712`, `app/services/field.py:163`, `app/services/media.py:325`, đối chiếu `app/services/locking.py:8`.
- **Evidence:** Các vị trí này gọi trực tiếp `.with_for_update()` thay vì helper SQL Server. Compile query Field với dialect MSSQL trong môi trường hiện tại cho `SELECT ... FROM fields WHERE fields.id = :id_1`, **không có UPDLOCK/HOLDLOCK/FOR UPDATE**. Pricing check overlap rồi insert; model price slot chỉ có CHECK cục bộ/index lookup, không có constraint loại trừ khoảng chồng.
- **Problem:** Giả định đã serialize nhưng câu SELECT trên SQL Server không tạo update lock dự kiến.
- **Impact:** Có cửa sổ hai request tạo khung giá chồng nhau; approve/reject cùng đơn có thể ghi đè nhau. **Xác nhận thiếu lock bằng SQL compile; kết quả cuộc đua cụ thể: NEEDS VERIFICATION** bằng hai connection SQL Server. Unique field name/cover vẫn bảo vệ một phần, không quy kết mọi thao tác đều nhân đôi dữ liệu.
- **Recommended fix:** Dùng cơ chế lock thống nhất theo dialect, thứ tự lock nhất quán và refresh entity sau đợi lock; thêm SQL Server concurrent tests cho pricing, moderation và OwnerApplication.

## H05 — Refund FAILED không có đường phục hồi được nối vào hệ thống

- **ID:** H05
- **Severity:** High — **P1**
- **Category:** Refund state / missing recovery
- **Files:** `app/services/refund.py:259`, `app/services/refund.py:333`, `app/services/refund.py:395`, `app/services/booking.py:458`, `app/cli/refunds.py:24`.
- **Evidence:** Job chỉ chọn PENDING/PROCESSING; kết quả khác success/7002 trở thành FAILED. Booking REFUND_PENDING không được hủy Owner lần nữa. Tái hiện refund resultCode=1001: `REFUND_PENDING`; lần chạy sau trả `0`, refund vẫn `FAILED` và booking vẫn `REFUND_PENDING`.
- **Problem:** Không có route/service/CLI được nối để query lại hoặc phục hồi FAILED. Admin chỉ đọc.
- **Impact:** Booking có thể bị kẹt và tiếp tục chặn giờ; có dấu vết lỗi nhưng không có thao tác hợp lệ để giải quyết trong ứng dụng.
- **Recommended fix:** Thiết kế đường query/reconcile/retry có idempotency, phân biệt failed cuối cùng và unknown/timeout; duy trì order/request bảo đảm không hoàn hai lần. Không đổi DB thủ công để bỏ qua lịch sử.

## H06 — Refund response không được đối chiếu đủ với refund intent

- **ID:** H06
- **Severity:** High — **P1**
- **Category:** Provider response validation / financial integrity
- **Files:** `app/services/refund.py:292`, `app/services/refund.py:318`, `app/services/refund.py:383`, `app/integrations/momo.py:118`, `app/integrations/momo.py:147`.
- **Evidence:** Nhánh refund submit đọc resultCode/transId rồi áp dụng success, không so orderId/requestId/amount với intent. Client refund/query trả transport dict trực tiếp. Tái hiện transport trả `resultCode=0`, transId có giá trị nhưng order/request là đơn khác và amount=1: refund vẫn SUCCESS, booking CANCELLED.
- **Problem:** Success của response không được gắn chắc với đúng yêu cầu đang hoàn.
- **Impact:** Response sai/misrouted có thể làm hệ thống ghi hoàn tiền dù chưa đủ chứng cứ. Phép thử dùng fake transport; **không khẳng định đã khai thác được MoMo thật hay có lỗi tại provider**.
- **Recommended fix:** Xác minh các trường định danh/số tiền theo contract provider trước cập nhật; kiểm tra chữ ký khi contract response quy định; bảo vệ query result và test wrong order/request/amount/transaction. Contract Sandbox thật còn NEEDS VERIFICATION.

## H07 — Có client query payment nhưng không có quy trình phục hồi IPN thất lạc

- **ID:** H07
- **Severity:** High — **P1**
- **Category:** Missing backend orchestration
- **Files:** `app/integrations/momo.py:104`, `app/services/payment.py:338`, `app/cli/__init__.py`, `app/cli/bookings.py`, `docs/06-system-architecture.md` phần 6.13.
- **Evidence:** Tìm toàn `app/tests/docs` chỉ thấy định nghĩa `query_payment`, không có call site. Browser return đúng chủ đích chỉ đọc, các job hiện có không query payment. Expire booking không query provider để xác nhận tiền thực thu.
- **Problem:** Nếu provider đã thu nhưng toàn bộ IPN không tới ứng dụng, không có reconciliation payment để tìm giao dịch và hoàn/ghi nhận theo thời điểm.
- **Impact:** Payment PENDING có thể tồn tại, booking hết hạn dù tiền đã thu. Late-IPN refund hiện có chỉ giúp khi IPN cuối cùng thực sự tới.
- **Recommended fix:** Bổ sung quy trình query payment pending quá hạn và xử lý kết quả bằng cùng rule/idempotency, kèm hướng dẫn chạy job. Test mất IPN, query success sau deadline, query pending/failure. Đây là khoảng trống source, chưa phải sự cố đã quan sát trên MoMo thật.

# Medium Issues

## M01 — Giữ transaction/lock trong lúc gọi refund HTTP

- **ID:** M01
- **Severity:** Medium — **P1**
- **Category:** Transaction / availability
- **Files:** `app/services/refund.py:259`, `app/services/refund.py:278`, `app/services/refund.py:295`, `app/services/refund.py:346`; `docs/06-system-architecture.md` phần 6.12.
- **Evidence:** Chọn toàn bộ refund bằng update lock, gọi HTTP trong vòng lặp rồi mới commit cuối hàm. Việc commit intent ở caller không kết thúc transaction mới vừa mở trong processor. Client timeout tối thiểu 30 giây (`app/integrations/momo.py:47`).
- **Problem:** Khác mô tả “gọi API ngoài transaction dài”; các refund/booking khác có thể chờ cùng batch.
- **Impact:** Chờ lock kéo dài, lỗi ở item sau làm rollback phần ghi nhận DB item trước trong khi provider đã xử lý. Idempotency provider là lớp bảo vệ cần kiểm chứng.
- **Recommended fix:** Claim intent và commit ngắn, gọi provider ngoài transaction, reacquire/recheck từng intent rồi cập nhật; test slow provider và lỗi giữa batch. Deadlock/tải thực: NEEDS VERIFICATION.

## M02 — Owner được báo đã hoàn 100% khi refund vẫn chờ/thất bại

- **ID:** M02
- **Severity:** Medium — **P1**
- **Category:** Frontend ↔ backend status
- **Files:** `app/routes/bookings.py:555`, `app/services/booking.py:976`, `tests/integration/test_momo_payments.py:211`.
- **Evidence:** Success flash luôn nói “Đã hủy ... đã được hoàn 100%”. Service có thể trả sau khi `_attempt_momo_refunds` bắt lỗi và để PENDING. Test có sẵn xác nhận hủy Owner trả về booking REFUND_PENDING trước khi fake refund processor hoàn tất.
- **Problem:** HTTP action thành công bị diễn giải thành refund đã thành công.
- **Impact:** Chủ sân có thông tin sai về tình trạng hoàn tiền; mâu thuẫn badge/history trên cùng màn hình.
- **Recommended fix:** Dựng thông báo từ booking/refund thực tế: đã tiếp nhận hủy, đang hoàn, hoàn thất bại hoặc đã hoàn tất; test cả MOCK và MoMo pending/failure.

## M03 — Giá hợp lệ phía Owner có thể khiến sân không đặt được

- **ID:** M03
- **Severity:** Medium — **P1**
- **Category:** Cross-layer money validation
- **Files:** `app/forms/pricing.py:51`, `app/services/pricing.py:381`, `app/services/pricing.py:323`, `app/services/contribution.py:50`, `app/services/contribution.py:145`, `app/integrations/momo.py` hàm `_whole_vnd`.
- **Evidence:** Owner nhập giá có 2 chữ số thập phân; pricing tính subtotal 0,01 VND. Contribution bắt buộc **tổng tiền** là VND nguyên trước khi tính cọc. Tái hiện giá giờ `100001.50`, khoảng 18:00–19:00: `BookingError: Tổng tiền sân phải là số nguyên VND lớn hơn 0.` Giá nguyên lẻ và thời lượng 90 phút cũng có thể tạo tổng nửa đồng.
- **Problem:** Pricing, booking và ngưỡng MoMo 1.000–50.000.000 không được validate thống nhất từ lúc cấu hình/báo giá.
- **Impact:** Khung giá lưu và ACTIVE hợp lệ, nhưng người đặt bị chặn hoặc checkout không tạo được với cọc ngoài ngưỡng.
- **Recommended fix:** Chốt quy tắc làm tròn VND ở đúng lớp, kiểm tra khả năng thanh toán trước giữ chỗ; không tự chọn cách làm tròn trong audit. Test giá lẻ, nhiều segment, 90 phút và cọc min/max.

## M04 — Availability phụ thuộc timezone hệ điều hành

- **ID:** M04
- **Severity:** Medium — **P2**
- **Category:** Datetime portability
- **Files:** `app/services/availability.py:57`, `app/services/availability.py:144`; đối chiếu `app/services/booking.py:960`.
- **Evidence:** `_normalize_local_datetime` trả datetime Việt Nam **naive**, rồi gọi `.astimezone(UTC)`. Python diễn giải naive theo timezone host, trong khi booking gắn rõ UTC+7. Hiện máy là Asia/Saigon nên các test không phơi bày.
- **Problem:** Host UTC và host Việt Nam diễn giải cùng `now` khác nhau.
- **Impact:** Khi chuyển môi trường, khả năng bỏ qua/giữ hold quá hạn sai lệch 7 giờ trong availability; create_booking vẫn có kiểm tra cuối nên không suy ra đặt trùng tự động.
- **Recommended fix:** Chuyển timezone tường minh, test cùng UTC instant trên môi trường host UTC. Sai lệch khi deploy: NEEDS VERIFICATION, lỗi chuyển đổi thể hiện rõ trong source.

## M05 — File ảnh chỉ được xác nhận bằng magic bytes

- **ID:** M05
- **Severity:** Medium — **P2**
- **Category:** Upload validation
- **Files:** `app/services/media.py:235`, `app/services/media.py:268`, `config.py` MEDIA_MAX_BYTES, `tests/integration/test_media.py:231`.
- **Evidence:** File bắt đầu bằng PNG signature và phần còn lại `not-a-real-image` vẫn qua `_validate_image`. JPEG/WebP cũng chỉ kiểm tra dấu hiệu cơ bản, không decode/verify ảnh.
- **Problem:** Extension/MIME/header đúng không bảo đảm ảnh hợp lệ. MEDIA_MAX_BYTES chỉ giới hạn phần stream đọc; không có cấu hình MAX_CONTENT_LENGTH của app trong source.
- **Impact:** Ảnh hỏng được lưu và hiển thị lỗi; giới hạn kích thước request tổng cần làm rõ. Không có bằng chứng thực thi mã/XSS từ file này; route dùng image MIME và nosniff.
- **Recommended fix:** Decode/verify ảnh với giới hạn kích thước pixel và byte, cân nhắc chuẩn hóa; giới hạn request ở app/deployment; test truncated/polyglot/malformed header. Không đồng nhất việc nhận ảnh hỏng với RCE.

## M06 — Suite không xác minh FK và migration như SQL Server

- **ID:** M06
- **Severity:** Medium — **P1**
- **Category:** Test environment / database verification
- **Files:** `tests/conftest.py:8`, `config.py` TestingConfig, `tests/unit/test_payment_models.py:42`, `tests/unit/test_booking_model.py:37`.
- **Evidence:** Fixture dùng `db.create_all()`/`drop_all()`, không upgrade migration. Kiểm tra engine testing cho `PRAGMA foreign_keys = 0`. Nhiều model test kiểm tra tên constraint/index trong metadata, không thử INSERT bị từ chối trên SQL Server.
- **Problem:** Suite 431 pass có thể bỏ lọt FK/cascade và khác biệt dialect/lock/backfill.
- **Impact:** Không được dùng suite này để kết luận rebuild SQL Server/concurrency đã hoàn chỉnh.
- **Recommended fix:** Bật FK ở engine test và bổ sung migration smoke/concurrency SQL Server cô lập trong quy trình kiểm thử. Audit đã chạy riêng migration SQLite thành công; chưa thay fixture/test.

## M07 — Tài liệu hiện hành tự mâu thuẫn với source

- **ID:** M07
- **Severity:** Medium — **P1**
- **Category:** Documentation / submission
- **Files:** `README.md:155`, `README.md:170`, `docs/03-business-rules.md:288`, `docs/06-system-architecture.md:105`, `app/services/booking.py:155`, `app/routes/venues.py:302`, `docs/10-decision-log.md:368`.
- **Evidence:** README còn bắt buộc Singles/Doubles; source luôn lưu play_format=None theo ADR-033. BR-036 nói latitude/longitude chỉ legacy và không nhận mới; route Owner create yêu cầu coordinates confirmed. Architecture nói 15 bảng, model thực có 18. `app/README.md` còn mô tả MoMo client sẽ nối sau; client đã tồn tại.
- **Problem:** Người đọc khó phân biệt policy mới, legacy và roadmap lịch sử.
- **Impact:** Demo/bảo vệ có thể mô tả chức năng khác implementation. Các mốc test cũ trong tài liệu là lịch sử, không thay thế kết quả 431 của audit này.
- **Recommended fix:** Đồng bộ tài liệu hiện hành sau review; giữ ADR lịch sử với supersession rõ ràng. Không đánh dấu roadmap accepted chỉ vì code/test tồn tại.

## M08 — Khoản MoMo thành công đến muộn gây lệch đối soát hiển thị

- **ID:** M08
- **Severity:** Medium — **P1**
- **Category:** Payment/refund status semantics / finance read-model
- **Files:** `app/services/payment.py:542`, `app/services/refund.py:513`, `app/services/admin.py:548`, `app/services/admin.py:613`, `app/services/owner_finance.py:178`.
- **Evidence:** Late provider success lưu Payment EXPIRED/result_code=0 và tạo refund; refund success không trừ booking balance vì tiền chưa từng áp vào booking. Admin/Owner tổng thu chỉ cộng Payment SUCCESS nhưng tổng hoàn cộng mọi Refund SUCCESS. Ví dụ late thu X rồi hoàn X: booking net=0, công thức history thu SUCCESS(0)−refund(X)=−X.
- **Problem:** Read-model không tách tiền thu rồi trả ngoài nghĩa vụ booking khỏi tiền đã áp cọc.
- **Impact:** Cảnh báo reconciliation có thể tồn tại dù late refund đã hoàn đúng; tổng thu/hoàn không giải thích được. **Xác nhận từ công thức source; rendering E2E trạng thái này: NEEDS VERIFICATION.**
- **Recommended fix:** Xây read-model provider gross/refund và booking applied net riêng, vẫn giữ lịch sử late payment; test admin/owner sau late refund. Không đổi hồi tố Payment EXPIRED thành SUCCESS một cách máy móc vì có filtered unique index.

## M09 — KPI Admin dùng trạng thái persisted trong khi trang khác dùng effective status

- **ID:** M09
- **Severity:** Medium — **P2**
- **Category:** Status / observability
- **Files:** `app/services/admin.py:246`, `app/services/booking.py:509`, `app/services/matchmaking.py:879`, `app/routes/admin.py:247`.
- **Evidence:** Dashboard đếm Booking CONFIRMED/PARTIALLY_PAID/PAID và Match OPEN không kiểm tra deadline/start/end. Dùng `date.today()` theo host. Public match search lọc thời gian; Owner dashboard gọi effective booking status.
- **Problem:** Nếu job chưa chạy, “đang hoạt động/kèo mở” ở Admin có thể khác trạng thái công khai; ngày hôm nay phụ thuộc host.
- **Impact:** KPI cần làm rõ nghĩa “DB status” hay “còn hiệu lực”; không thể quy kết DB sai chỉ từ khác số đếm.
- **Recommended fix:** Đồng nhất định nghĩa KPI và timestamp, hoặc ghi rõ trạng thái lưu; test stale hold và trận đã qua giờ nhưng CLI chưa chạy.

## M10 — MoMo bị tắt có thể phát sinh exception ngoài error contract route

- **ID:** M10
- **Severity:** Medium — **P2**
- **Category:** Exception handling / endpoint config
- **Files:** `app/integrations/momo.py:52`, `app/services/payment.py:273`, `app/services/payment.py:344`, `app/services/payment.py:392`, `app/routes/payments.py:98`, `app/routes/payments.py:201`.
- **Evidence:** `MomoClient.from_app_config()` ném MomoConfigurationError (MomoAPIError/RuntimeError); được gọi ngoài khối chuyển thành PaymentError. Route payment/IPN/return chủ yếu bắt PaymentError. MOCK là cấu hình hiện tại, MOMO_ENABLED=False.
- **Problem:** Truy cập trực tiếp endpoint MoMo khi disabled có thể thành 500 thay vì báo trạng thái không khả dụng có kiểm soát.
- **Impact:** Hành vi lỗi không thân thiện, đặc biệt callback cũ khi cấu hình bị tắt. **Source-confirmed exception mismatch; không gọi endpoint live.**
- **Recommended fix:** Guard enabled và chuẩn hóa exception tại service boundary; test disabled/incomplete config với return/IPN/start.

## M11 — Một số danh sách đọc toàn bộ rồi mới phân trang/giới hạn

- **ID:** M11
- **Severity:** Medium — **P2**
- **Category:** Performance / scale
- **Files:** `app/services/venue.py:265`, `app/services/venue.py:295`, `app/services/booking.py:323`, `app/services/owner_finance.py:240`, `app/services/owner.py:142`.
- **Evidence:** Venue search `.all()` rồi Haversine/slice; lịch cá nhân và finance history không paginate; Owner dashboard lấy toàn bộ booking tương lai rồi giới hạn phần hiển thị.
- **Problem:** Pagination UI không luôn tương đương pagination SQL.
- **Impact:** Khi số dữ liệu lớn, dùng nhiều RAM/thời gian hơn cần thiết. **Chưa có benchmark: NEEDS VERIFICATION**, không kết luận app hiện chậm.
- **Recommended fix:** Paginate ở SQL cho text search/history; tối ưu nearest phù hợp quy mô đã đo; test query count và dataset lớn trước chọn giải pháp.

# Low Issues

## L01 — Dependency và cấu hình triển khai chưa tái lập chặt chẽ

- **ID:** L01
- **Severity:** Low — **P2**
- **Category:** Dependencies / configuration
- **Files:** `requirements.txt:1`, `config.py`, `README.md` phần cài đặt.
- **Evidence:** Requirements chỉ là tên package, không pin version; config chỉ có development (DEBUG=True) và testing. SESSION_COOKIE_SECURE=False ở cấu hình thực tế; HttpOnly và SameSite=Lax có bật.
- **Problem:** Máy cài mới có thể nhận bộ dependency khác; chưa có profile deploy riêng.
- **Impact:** Giới hạn về tái lập và deploy public. Development localhost là đúng ngữ cảnh hiện tại, không coi riêng DEBUG=True là lỗ hổng Critical.
- **Recommended fix:** Ghi/pin phiên bản đã kiểm chứng và hướng dẫn local; nếu có deploy công khai mới bổ sung profile tương ứng. Không có dependency advisory/CVE scan trong audit này.

## L02 — Code thừa và duplication làm khó bảo trì

- **ID:** L02
- **Severity:** Low — **P3**
- **Category:** Dead/redundant code
- **Files:** `app/routes/admin.py:944`, `app/routes/admin.py:828`, `app/services/payment.py:88`, `app/services/payment.py:582`, `app/services/__init__.py`.
- **Evidence:** `_group_accounts` chỉ có định nghĩa trong app/tests/docs. Nhánh monitoring matches nằm sau redirect không thể đi đến từ route hiện tại. Top-up validation lặp trong MOCK và MoMo; nhãn trạng thái/occupancy lặp giữa booking/admin/owner/availability.
- **Problem:** Nhiều điểm phải sửa cùng lúc khi policy thay đổi.
- **Impact:** Technical debt; không phải lý do tự xóa legacy engine.
- **Recommended fix:** Review call graph và dynamic callers trước cleanup; giữ các nhánh legacy còn test/data. Chưa xóa/refactor gì.

## L03 — Thiếu tài liệu được yêu cầu đọc trước audit

- **ID:** L03
- **Severity:** Low — **P2**
- **Category:** Audit input / documentation
- **Files:** `REPORT_GUIDE.md` — không tìm thấy dưới thư mục đồ án.
- **Evidence:** Tìm file theo tên trong toàn workspace không trả kết quả; README có bộ tài liệu docs nhưng không có file này.
- **Problem:** Không xác minh được các quy định bổ sung của REPORT_GUIDE.
- **Impact:** Báo cáo này tuân theo yêu cầu đã cung cấp; tuân thủ tài liệu bị thiếu là NEEDS VERIFICATION.
- **Recommended fix:** Bổ sung hoặc xác định đúng vị trí nếu tài liệu này tồn tại ở ngoài workspace; sau đó đối chiếu phần chênh. Không tự tạo nội dung giả cho guide.

# Frontend ↔ Backend Issues

Không phát hiện **UI EXISTS BUT BACKEND MISSING** ở endpoint literal đã kiểm kê. 43 template parse thành công; method/path các form nghiệp vụ chính khớp route. Điều này không loại trừ lỗi tương tác browser động.

| Contract | Kết quả audit |
|---|---|
| Booking form → availability | GET, query `date`; JSON `ok/date/step_minutes/minimum_duration_minutes/slots`; JS đọc đúng các key |
| Booking form → time-quote/quote | POST FormData gồm `booking_date`, `start_hour/start_minute`, `end_hour/end_minute`, mode/count ở full quote; CSRF nằm trong form; JSON money là chuỗi, JS format để trình bày |
| Owner geocode | POST urlencoded address/province_code/ward_code/csrf_token; JSON latitude/longitude/display_name hoặc error; caller kiểm tra response.ok |
| Ward picker | GET province_code, trả wards với code/name/type; frontend xây option, mã được validate lại server |
| Match request/action | FormData/POST truyền contact_phone/share_contact/message; accept/reject dùng participant_id+match_id và kiểm tra creator |
| Payment form | Prefix `payment`; top-up prefix `top-up`; endpoint có thật nhưng lựa chọn provider chỉ ở UI gây H01 |
| Owner cancel | Prefix `owner-cancel`, invalid reason trả 422 và mở lại modal; success flash sai trạng thái MoMo ở M02 |
| Admin partial navigation | GET HTML từ endpoint cùng origin, DOMParser/clone và fallback navigation; không có API JSON bí mật bị thiếu |
| Upload | POST multipart field `image`; action cover/delete có form CSRF; validation nội dung chưa đủ ở M05 |
| Zalo | Template nhánh creator/participant JOINED mới xuất số đối tác; số riêng của chính user có thể được điền vào form. Không thấy public contact serialization trái rule trong nhánh đã kiểm tra |

**BACKEND EXISTS BUT UI MISSING:** `query_payment` chỉ là client chưa có orchestration (H07). Các helper danh sách tài chính Admin không có UI riêng là hệ quả contract Admin tập trung vào Booking Detail, không tự coi là feature thiếu. CLI expiry/completion không cần nút UI; MoMo IPN là server-to-server, không cần frontend gọi.

Browser E2E cho request chồng nhau, focus, responsive, CDN Leaflet/Bootstrap mất kết nối và template variable ở mọi tổ hợp dữ liệu: **NEEDS VERIFICATION**. Test HTML/CSS source không chứng minh các hành vi này.

# Backend ↔ Database Issues

Không phát hiện table/column đang dùng bị thiếu trong SQL Server đã đọc. Model↔DB autogenerate diff rỗng không đủ chứng minh mọi invariant nghiệp vụ: overlap interval, payer của lần giữ suất, refund amount tổng và role ownership còn do service kiểm soát.

- H04: lock dự kiến không tồn tại trong SQL MSSQL ở pricing/moderation; đây là vấn đề service↔dialect, không phải thiếu bảng.
- H02: payment liên kết hợp lệ về FK nhưng không đúng người đang giữ contribution; FK đơn không bảo vệ temporal ownership.
- M06: SQLite tests không bật FK; cần phân biệt kiểm tra ORM schema với enforcement.
- CHECK tiền không âm/range và filtered unique payment success/contribution đã có. Không có constraint SQL loại trừ booking overlap; `create_booking` dựa vào khóa Field và kiểm tra interval.
- Payment.booking_id và contribution.booking_id là FK riêng; Refund.booking_id và Payment.booking_id cũng riêng. Service phải kiểm tra quan hệ chéo. Truy vấn dữ liệu hiện tại không thấy mismatch ở các liên kết này.
- Tiền dùng Numeric(12,2), deposit_rate Numeric(5,4), tọa độ Numeric(9,6). Đơn vị VND nguyên ở contribution tạo bất đồng với pricing (M03).
- BookingDate/time là giờ địa phương, timestamp created/deadline là UTC naive; DATETIME2 trên MSSQL. M04 là chỗ chuyển UTC không tường minh.

# Business Rule / Status Issues

## Đối chiếu các rule người dùng đã xác nhận

| Rule | Implementation | Kết luận |
|---|---|---|
| Booking đủ điều kiện mới tạo kèo | `validate_match_creation` kiểm owner, cọc/status/mode, trước giờ bắt đầu, unique match/booking | Khớp cho booking mới ở trạng thái thông thường |
| Người nhận giữ suất tối đa 15 phút | `_reserve_or_join_participant`: min(now+15m, cutoff/start) | Khớp; có test cap tại start |
| Người nhận cọc 15% | Chia deposit 30% thành hai phần nguyên VND; phần cuối nhận sai số làm tròn | Khớp cho người nhận đầu tiên; xem BR-C02 |
| Success → tham gia, “Đã có đối thủ” | Payment success → Participant JOINED → Match CONFIRMED | Khớp trong luồng chuẩn; H02 phá luồng người thay suất pending |
| Failure/expiry → nhả suất | Expiry nhả; failure chỉ FAILED payment | **BUSINESS RULE CONFLICT — H03** |

**BR-C02 — BUSINESS RULE CONFLICT: ngoại lệ người nhận thay thế**

- **ID:** BR-C02.
- **Severity:** Medium / P1 để xác nhận contract; không phải lỗi đã chứng minh.
- **Category:** Business Rule / Documentation.
- **Files:** `app/services/matchmaking.py:979`, `app/services/matchmaking.py:623`, `tests/integration/test_refunds.py:297`, `docs/03-business-rules.md` BR-032.
- **Evidence:** Nhánh booking PAID không lấy contribution mới; đối thủ đã cọc rồi tự rút chuyển khoản cọc sang FORFEITED. Tài liệu và test cho phép người thay thế JOINED không thu lại vì tiền vẫn nằm trong booking.
- **Problem:** Yêu cầu audit hiện tại nói người nhận thanh toán cọc 15% nhưng không nêu ngoại lệ người thay thế. Repository đã có ngoại lệ được tài liệu/test chốt.
- **Impact:** Nếu áp rule 15% cho mọi người nhận kể cả người thay thế, hành vi hiện tại khác contract đó. Tự sửa thành thu lần hai có thể làm sai tổng tiền và chính sách forfeiture.
- **Recommended fix:** Ghi rõ ngoại lệ trong contract hoặc phê duyệt thay đổi nghiệp vụ trước khi sửa. Không tự coi ngoại lệ hiện tại là bug.

## Bảng trạng thái và điểm chuyển

| Entity/current state | Allowed action → next state | Validation/persistence | UI |
|---|---|---|---|
| User mới | register → USER/ACTIVE | `auth.register_user`, email unique, password hash | auth/register |
| User ACTIVE/LOCKED | Admin khóa/mở → LOCKED/ACTIVE | `admin.set_admin_account_status`; cấm tự sửa/Admin/INACTIVE | admin/accounts |
| User USER | đơn APPROVED → OWNER | `owner_application.review_owner_application`; cùng commit đơn | admin/owner-applications |
| User INACTIVE | Không có action đổi trong UI hiện tại | Service chủ động từ chối | Chỉ lọc/xem; trạng thái bảo lưu, không tự suy ra thiếu feature |
| OwnerApplication chưa có PENDING | submit → PENDING | Role USER, filtered unique một pending/user | new/mine |
| OwnerApplication PENDING | approve/reject → APPROVED/REJECTED | Admin, lý do khi reject, không xử lý lại; lock H04 | admin form |
| OwnerApplication CANCELLED | Enum tồn tại; không có route hủy đơn hiện hành | Không thấy assignment production | Label lịch sử; POSSIBLY UNUSED |
| Venue mới | create → PENDING | Owner và address/pin validation | owner venue form |
| Venue PENDING/ACTIVE/HIDDEN | PENDING→ACTIVE/HIDDEN; ACTIVE→HIDDEN; HIDDEN→ACTIVE | Admin allowlist trong moderate_venue | admin venues |
| Venue ACTIVE | sửa identity/location → PENDING | update_venue xóa dấu xét duyệt hiện tại | owner form/admin queue |
| Venue INACTIVE | Không có transition moderation hiện hành | Enum/DB cho phép, allowlist không có | Legacy/NEEDS VERIFICATION dữ liệu cần phục hồi |
| Field INACTIVE/ACTIVE | bật/tắt → ACTIVE/INACTIVE | Có active price mới bật; tắt giá cuối tắt field | pricing/field UI |
| PriceSlot ACTIVE/INACTIVE | create/update/toggle | Interval/overlap/hours; H04 | owner pricing |
| Maintenance ACTIVE | cancel → CANCELLED; qua end → effective COMPLETED | Service cấm hủy khi đã qua end | history/upcoming, không bắt buộc job ghi COMPLETED |
| Booking mới | create → CONFIRMED | Field lock, future/overlap/price; initial due now+15m | giữ chỗ/countdown |
| Booking CONFIRMED | cọc đầu → PAID hoặc PARTIALLY_PAID; không cọc quá hạn → EXPIRED | payment/expiry services | payment/detail/list |
| Booking PARTIALLY_PAID current opponent | opponent cọc → PAID; không đối thủ vẫn giữ sân; hết giờ → COMPLETED | `_booking_can_complete`, no funding deadline | lịch cá nhân/Owner |
| Booking còn hiệu lực | user cancel → CANCELLED hoặc REFUND_PENDING; Owner cancel → refund policy | owner/user ownership; creator cấm từ start; owner xét stored status | cancel forms |
| Booking REFUND_PENDING | mọi refund bắt buộc SUCCESS → CANCELLED | `_all_booking_refunds_succeeded` | refund status; FAILED kẹt H05 |
| Booking PENDING/REJECTED | Không phải trạng thái create mới | Enum/labels legacy được giữ | Chỉ lịch sử; không phải lý do tái thêm owner approval |
| Payment PENDING | IPN success → SUCCESS; failure → FAILED; success đến muộn → EXPIRED+refund | HMAC/order/request/amount, unique provider trans/success contribution | Labels/debug disclosure; M08 |
| Payment SUCCESS | Callback lặp → giữ nguyên; refund không ghi đè payment | provider_trans_id idempotency | history |
| Payment FAILED/CANCELLED/EXPIRED | Callback với payment nonpending được trả về, trừ kiểm tra success đã lưu | `process_momo_payment_notification` | CANCELLED không thấy producer hiện hành; không phải nút user hủy riêng |
| Refund PENDING/PROCESSING | submit/query → SUCCESS/PROCESSING/FAILED | H05/H06/M01 | booking history; CLI |
| Refund FAILED | Không có phục hồi nối vào app | H05 | Chỉ xem |
| Match OPEN | JOINED opponent → CONFIRMED; đủ player → FULL; close listing → CANCELLED | capacity, actor, booking còn hiệu lực | “Đã có đối thủ”/“Đủ người”/“Đã đóng bài” |
| Match CONFIRMED/FULL | participant rút trước start → OPEN; booking hoàn tất → COMPLETED | withdraw/complete | match detail/mine |
| Participant PENDING (FIND_PLAYERS/legacy) | creator accept → JOINED (players mới) hoặc AWAITING_PAYMENT (legacy); reject → REJECTED | creator guard; pending state; capacity | creator action |
| Participant mới FIND_OPPONENT | request → ACCEPTED_AWAITING_PAYMENT; covered replacement → JOINED | auto policy, contact consent, one occupied opponent | join/payment |
| Participant AWAITING_PAYMENT | payment success → JOINED; deadline/start → EXPIRED; rút → WITHDRAWN | release unpaid contribution, H03 failure gap | countdown/actions |
| Participant JOINED | rút trước start → WITHDRAWN; cọc current → FORFEITED | current/legacy policy tách biệt | withdrawal/contact |
| Contribution PENDING | payment → PAID; expire creator → EXPIRED; opponent hold expire → release user/time | Không xóa contribution history | financial detail |
| Contribution PAID | current opponent rút → FORFEITED; refund → REFUND_PENDING/REFUNDED/PARTIALLY_REFUNDED | money range và refund ledger | amount_paid là net |
| Contribution WAIVED/TOP_UP/PLAYER | Các nhánh legacy hoặc nghĩa vụ trả thay | Chỉ hoạt động khi booking/deadline policy cho phép | Không phải flow thu online người ghép mới |

Các trạng thái trình bày `PAST`, `INACTIVE`, `CLOSED_LISTING`, `ENDED` không nhất thiết là giá trị persisted của Match. Không kết luận “sai enum” chỉ vì UI dùng trạng thái hiệu lực. No-show không có bằng chứng tự phát hiện trong MVP; tài liệu chủ động đưa scoring/phạt tự động ra ngoài phạm vi.

# Missing / Incomplete Features

1. **Thiếu orchestration phục hồi payment khi mất IPN:** H07.
2. **Thiếu phục hồi refund FAILED:** H05. Không cần tự tạo màn hình refund riêng; có thể giải quyết qua quy trình vận hành phù hợp sau review.
3. **Chưa có bằng chứng scheduler tự chạy CLI:** source có commands, không thấy scheduler in-process/config job trong repo. Availability bỏ qua hold expired; persisted trạng thái/late refund vẫn cần job. Lịch Windows Task Scheduler bên ngoài repo: **NEEDS VERIFICATION**. Không tạo automation trong audit.
4. **MoMo Sandbox thật chưa được chứng minh:** cấu hình hiện tại `MOMO_ENABLED=False`, nên runtime mặc định là MOCK không trừ tiền thật. Fake transport tests không phải Sandbox E2E. Cần payment/IPN/duplicate/failure/late/refund/query với credential và HTTPS được cấu hình hợp lệ.
5. `REPORT_GUIDE.md` thiếu; tài liệu hiện hành cần đồng bộ M07.
6. **Không tính thiếu:** settlement, payout, ví Admin, owner rút tiền, Production MoMo, chat realtime, email, coupon, rating, AI/no-show scoring nằm ngoài MVP hoặc Could Have theo scope/ADR-038. Admin moderation hiện là account/owner/venue; không có nút xóa payment/refund hoặc trực tiếp sửa match, phù hợp Admin read-only contract.

# Dead / Redundant Code

| Phân loại | File/symbol | Evidence và nhận định |
|---|---|---|
| CONFIRMED DEAD CODE trong call graph repository | `app/routes/admin.py:944` `_group_accounts` | Không có call/import/template reference trong app/tests/docs; helper private không đăng ký route |
| CONFIRMED DEAD CODE qua HTTP route hiện tại | `app/routes/admin.py:828` nhánh `_load_monitoring_page(section='matches')` | `monitoring()` redirect matches trước khi tới loader; direct external Python call chưa khảo sát |
| POSSIBLY UNUSED | `app/services/admin.py:311` get_admin_monitoring_summary; `:1254/:1300/:1352` list_admin_contributions/payments/refunds | Chỉ định nghĩa và re-export trong `services/__init__.py`; finance sections cũ redirect về booking |
| POSSIBLY UNUSED | `app/services/venue.py:109/:396` list_public_venues/list_owner_venues; `owner_application.py:52` list_pending_applications | Các route dùng search/summaries/list_owner_applications; public exports có thể có caller ngoài repo |
| POSSIBLY UNUSED ở runtime | `maintenance_blocks_time`, `list_open_matches` | Có test/direct public exports; không gọi từ route hiện hành. Không gọi là hoàn toàn dead |
| INCOMPLETE / POSSIBLY UNUSED | `MomoClient.query_payment` | Chưa có caller; liên quan chức năng cần bổ sung H07, không khuyến nghị xóa |
| LEGACY, không đánh dấu dead | play_format, funding_deadline, matchmaking_deadline, LEGACY_FULL_ONLINE, TOP_UP/PLAYER, 80/20 refund | Có nhánh đọc/điều kiện và legacy tests; migration/backfill phụ thuộc |
| LEGACY/NEEDS VERIFICATION | `google_place_id`, city/district, enum INACTIVE/CANCELLED hiếm | Có fallback/migration, không được tự drop column hay enum |
| Không dead ở cấp asset | Toàn bộ 17 JS + 3 CSS | Đều được load trong template; CSS selector riêng lẻ cần browser coverage trước kết luận |
| Không dead ở cấp template | 43 template | Có render/include/extends/import reference; syntax parse thành công |
| Tài liệu/mockup | `docs/mockups/admin-monitoring-redesign.html`, diagram/design files | Không render từ Flask nhưng là artifact tài liệu; không phải production orphan cần xóa |

Duplication có thật: timezone/status/occupancy label ở nhiều module, top-up validation hai provider. Ưu tiên sửa correctness trước khi gom helper. Re-export không được xem là bằng chứng có runtime caller; route không có link không đủ chứng minh unused vì còn callback/CLI/bookmark/alias.

# Test Coverage Gaps

Suite hiện có negative cases đáng kể: role/ownership, path mismatch, invalid input/state, overlap và boundary adjacency, expired hold, duplicate payment/request, rollback khi commit lỗi, creator/owner cancellation, forfeiture/refund legacy, privacy Zalo, read-only GET, late MoMo success và browser return không ghi tiền. Không mô tả suite là “chỉ happy path”.

Khoảng trống ưu tiên:

| Gap | Production | Test gần nhất nhưng chưa phủ tổ hợp | Cần kiểm tra |
|---|---|---|---|
| Provider gating H01 | payment route/mock service | `test_mock_payment_route_updates_booking_and_renders_deposit_copy` | MOMO enabled + direct mock POST; assert DB unchanged |
| Checkout reuse H02 | start checkout + release hold | same-request retry, expire same contribution | A pending checkout → expiry/withdraw → B checkout; đúng payer/order |
| Failed hold H03 | process IPN | success/idempotent/late notification | signed failure → release; user khác nhận được |
| SQL Server locks H04 | pricing/moderation | overlap và reviewed-again tests đều tuần tự | Hai session concurrent, isolation/lock wait, unique/check còn đúng |
| Refund failed/recovery H05 | refund processor | owner refund happy path, retry late refund | failed, unknown timeout, retry/query và không double refund |
| Wrong refund response H06 | provider response handling | fake client always matching order | wrong IDs/amount, repeated response/provider ID |
| Missing IPN H07 | query client | browser return stays pending | query reconciliation, deadline, provider success sau cancel |
| Transaction M01 | refund batch | chưa có slow HTTP/batch rollback | timeout sau một refund provider success, DB rollback, retry |
| VND/limits M03 | pricing/contribution/MoMo | round deposit, quote segments | giá 100001.50; integer odd × 90 phút; provider min/max |
| FK/migration M06 | schema | metadata name checks/create_all | INSERT FK sai, cascade, base/head và backfill populated DB |
| Browser tương tác | mọi JS/UI | HTML/string assertions | Browser chạy thật, keyboard/mobile, response lỗi/out-of-order |
| Financial edge M08 | admin/owner read-model | normal SUCCESS payment/refund | late EXPIRED/result0 + successful refund |

Một số test UI/accessibility kiểm tra chuỗi trong source hoặc HTML (`test_phase_4_1c_accessibility.py`, geolocation script test). Chúng hữu ích để giữ cấu trúc nhưng không chứng minh focus/scroll/map/API hoạt động trong browser. Model tests kiểm tên constraint/index không thay enforcement test. Có parametrize nên số test function trong phụ lục khác số 431 case thực thi.

Các test legacy không tự động obsolete: `test_legacy_opponent_deposit_and_creator_top_up_are_auditable`, `test_legacy_paid_participant_withdraws_over_12_hours_with_full_refund` kiểm tương thích có chủ đích. Tên `test_user_can_cancel_own_booking_before_two_hour_boundary` còn dấu wording cũ; không từ tên này suy ra rule mới vẫn phải trước hai giờ.

Không đo line/branch coverage nên **không công bố % coverage**. Không thêm test vào repository trong audit; các probe bổ sung chạy qua stdin và DB in-memory.

# Database / Migration Audit

## Schema đang dùng

- Model/DB: 18 bảng nghiệp vụ; thêm `alembic_version` và `sysdiagrams` ở SQL Server. `sysdiagrams` được loại đúng trong `migrations/env.py`, không phải bảng nghiệp vụ thiếu model.
- 54 CHECK, 32 FK; CHECK names khớp model; không disabled/untrusted constraint.
- `compare_metadata` không thấy add/remove/type/nullability/FK/index drift trong khả năng autogenerate của dialect. CHECK được kiểm riêng qua `sys.check_constraints` do inspector dialect không hỗ trợ `get_check_constraints`. Không dùng việc inspector không hỗ trợ để kết luận DB không có CHECK.
- Snapshot truy vấn chỉ đọc: payment↔contribution booking mismatch = 0; refund↔payment booking/recipient mismatch = 0; booking.paid_amount↔sum(contribution.amount_paid) mismatch = 0; payment PENDING = 0; refund FAILED = 0. Đây là snapshot hiện tại, không phủ mọi invariant hay dữ liệu tương lai.

## Ràng buộc quan trọng

| Domain | Bảo vệ có thật | Giới hạn |
|---|---|---|
| User/OwnerApplication | Email unique, role/status CHECK, filtered unique PENDING/user | Race approve/reject còn H04 |
| Venue/Field | FK owner/catalog/address; coordinate range/hours; unique name theo venue | Coordinate/address snapshot được service xác minh; state concurrency H04 |
| Booking | Unique booking_code, money/time/status checks, index field/date/time/status | Không có exclusion overlap DB; Field lock là điều kiện correctness |
| Price detail | FK booking/price_slot; giá/subtotal/duration checks | Snapshot không đổi khi giá hiện hành đổi; price non-integer M03 |
| Contribution | Range amount_paid, slot/type CHECK; unique external slot trừ REFUNDED | Không encode người giữ suất theo thế hệ attempt |
| Payment | Order/request unique, provider_trans_id filtered unique, một SUCCESS/contribution | Không có unique PENDING/payer/hold; cần service lifecycle đúng |
| Refund | Order/request/provider refund transaction unique, amount>0 | Tổng refund≤payment và eligibility nằm ở service |
| Match/Participant | Unique booking trên Match; filtered active user/match | Không có DB max-capacity constraint; phụ thuộc transaction service |
| Media | XOR venue/field, unique cover theo parent, storage_path unique, FK CASCADE | DB cascade không tự xóa file vật lý |

Không có route xóa transaction history. Quan hệ tài chính không dùng cascade delete toàn bộ lịch sử qua action public. Media có `ondelete=CASCADE` vào venue/field và ORM delete-orphan; kiểm tra riêng có FK bật cho reset demo và media **không tái hiện lỗi FK**, nên không ghi issue “reset thiếu xóa media làm lỗi DB”. Cleanup file ảnh khi reset bulk vẫn cần review nếu dùng command này, không chạy trên DB hiện tại.

## Migration và dựng lại

17 revision nối tuyến tính từ `378937fd70e9` đến `a6d8e4f2c913`, không thấy missing parent/multiple head. Upgrade base→head trên SQLite rỗng thành công, bao gồm catalog/address backfill và media. Không tạo migration mới.

**NEEDS VERIFICATION:** chạy base→head trên SQL Server mới, upgrade populated legacy dataset, downgrade dữ liệu đã có, khôi phục SQL demo kèm ảnh và read-only parity sau restore. DB hiện tại đúng head/schema là bằng chứng hữu ích nhưng không thay thử dựng từ rỗng.

README backup yêu cầu chạy migration rồi import data. SQL import có thao tác xóa dữ liệu đích, audit không thực thi. Đường dẫn ví dụ SQLCMD trong `database/README.md` dùng filename trần; nếu chạy từ root phải chọn đúng cwd/path `database/...`. File ảnh vật lý không nằm trong backup, nên bản phục hồi có metadata nhưng ảnh có thể 404; README đã công khai giới hạn này.

# Security / Configuration

| Hạng mục | Evidence / kết luận |
|---|---|
| Login/role | `roles_required` bọc login_required; owner/admin actions có role guard; user_loader trả None nếu inactive/locked |
| Ownership/IDOR | Booking user/Owner, field/venue/pricing/maintenance/media, participant/creator có kiểm tra id/parent scope. Test IDOR có ở suite. H01 là provider bypass đã tái hiện |
| CSRF | CSRFProtect global; POST form có token, IPN là exemption chủ đích; test một số action bật CSRF lại. Testing mặc định tắt CSRF nên không coi toàn suite đã chứng minh tất cả token |
| XSS | Jinja autoescape, money/contact/map data không dùng `safe` tùy tiện; JS dùng textContent/tojson và DOM nodes. innerHTML của location picker lấy icon/label nội bộ. Chưa có browser payload fuzzing |
| SQL injection | ORM expressions/bind params; raw SQL production quan sát được là SELECT 1 health và SQL literal cho index/constraint; không phát hiện raw SQL ghép trực tiếp input HTTP |
| Password | Werkzeug generate/check_password_hash; đăng ký validate 8–128 ký tự; Admin view có test không lộ password_hash |
| Secrets | SECRET_KEY bắt buộc env; MoMo key đọc env. Git tracked không có `.env`, `.pem`, `.key`; quét literal assignment credential trong app/config không thấy candidate. Không in nội dung `.env`/secret. Không thực hiện toàn bộ Git-history secret scan |
| Demo data | Mật khẩu demo được công khai có chủ đích trong database README; không coi đó là secret production. Không dùng trên public deployment |
| Debug/cookies | Hiện development, DEBUG=True, MOMO_ENABLED=False, CSRF=True, HttpOnly/Lax; secure cookie chưa bật — L01 |
| Upload | Ownership/path.resolve containment, extension/MIME/byte cap, UUID storage, nosniff; M05 vẫn thiếu decode ảnh; ảnh riêng trả cache header cần review nếu triển khai shared cache |
| Rate limiting | Không thấy limiter đăng nhập/register trong app/dependencies; không thử brute force. P2 nếu triển khai công khai; không tự thêm khóa/no-show/business rule |
| Provider validation | IPN HMAC+partner/order/request/amount; return chỉ đọc là đúng. Refund thiếu binding H06, disabled exception M10 |

Không chứng nhận hệ thống an toàn tuyệt đối. Audit source này không phải penetration test hay chứng nhận compliance; không suy ra CVE từ việc dependency không pin.

# Recommended Fix Order

| Ưu tiên | Việc cần làm sau khi người dùng review | Điều kiện xác minh |
|---|---|---|
| **P0 — phải sửa trước khi nộp bản hoàn tất MVP** | H01 provider gating; H02 checkout đúng payer/lần giữ; H03 failure nhả suất đúng rule | Test regression tái hiện từng lỗi, DB không đổi khi bị chặn, late IPN hoàn đúng payer |
| **P1 — nên sửa trước khi nộp** | H04 locks SQL Server; H05 recovery refund; H06 response binding; H07 payment reconciliation | Test concurrent SQL Server, fake failure/query và Sandbox E2E khi có môi trường |
| **P1** | M01 transaction HTTP; M02 message; M03 VND; M06 FK/migration test; M07 docs; M08 late-money reconciliation | So sánh UI/DB/state/history, full suite sau sửa, rebuild SQL Server cô lập |
| **P1 review rule** | BR-C02 ngoại lệ thay đối thủ không cọc lại | Xác nhận scope của rule 15%, giữ lịch sử FORFEITED đúng nghĩa |
| **P2 — nếu còn thời gian** | M04/M09 timezone+effective KPI; M05 decode/request limits; M10 config error; M11 performance; L01 dependency; L03 guide | Browser/error/timezone probes, benchmark nếu quy mô cần |
| **P3 — technical debt** | L02 dead helpers/duplication, rà selector CSS, docs lịch sử | Call graph + regression, không xóa nhánh legacy khi chưa kiểm dữ liệu |

Không thực hiện bất kỳ đề xuất sửa nào trong báo cáo này. Không cần bổ sung settlement/payout hay framework mới để xử lý các lỗi trên.

# Final Submission Readiness

**NOT READY** cho tuyên bố “toàn bộ hệ thống đã audit xong và đủ đúng nghiệp vụ thanh toán/tìm đối thủ”. Lý do là các lỗi P0 được tái hiện, không phải chỉ vì thiếu tài liệu hay chưa deploy tiền thật.

Có thể dùng các phần đã trace/test làm nền tảng demo nội bộ, nhưng cần mô tả đúng **MOCK/Sandbox**, không coi 431 pass là chứng minh mọi luồng MoMo đã chạy thật. Chưa có cơ sở đổi đánh giá sang READY WITH MINOR FIXES vì H01/H02/H03 tác động trực tiếp luồng cọc và nhận kèo.

Trước đánh giá lại: review báo cáo → sửa trong scope được duyệt → bổ sung regression cho lỗi đã tái hiện → chạy full suite → kiểm chứng SQL Server concurrency/rebuild và MoMo Sandbox E2E hoặc công khai rõ giới hạn được chấp thuận → đồng bộ tài liệu/test count → kiểm tra gói source/database/ảnh. Các yêu cầu Word/PDF và quy định khoa không được audit lại trong lượt source audit này.

**Files changed bởi audit:** `AUDIT_REPORT.md` duy nhất. **Business logic changed:** Không. Những thay đổi có sẵn ở route/CSS/template/test và hai file database staged đã được giữ nguyên; audit không commit/push.

Các phụ lục dưới đây là inventory từ source/runtime dùng để truy ngược; một dòng inventory không tự mang nghĩa OK.

## Phụ lục A — Route inventory

Inventory dưới đây lấy từ Flask URL map và AST source; service gọi qua helper có thể không xuất hiện trong cột lời gọi trực tiếp.

| Endpoint | Method / URL | Source | Decorator / lời gọi trực tiếp |
|---|---|---|---|
| `main.home` | GET `/` | `app/routes/main.py:8` |  |
| `admin.dashboard` | GET `/admin` | `app/routes/admin.py:247` | roles_required(UserRole.ADMIN); get_admin_dashboard_summary |
| `admin.accounts` | GET `/admin/accounts` | `app/routes/admin.py:258` | roles_required(UserRole.ADMIN) |
| `admin.update_account_status` | POST `/admin/accounts/<int:account_id>/status` | `app/routes/admin.py:319` | roles_required(UserRole.ADMIN); set_admin_account_status |
| `admin.booking_operations` | GET `/admin/bookings` | `app/routes/admin.py:429` | roles_required(UserRole.ADMIN); _parse_booking_filter_id; get_admin_booking_filter_options; list_admin_booking_operations; list_admin_catalog |
| `admin.booking_detail` | GET `/admin/bookings/<string:booking_code>` | `app/routes/admin.py:502` | roles_required(UserRole.ADMIN); _booking_list_return_params; get_admin_booking_detail |
| `admin.match_operations` | GET `/admin/matches` | `app/routes/admin.py:531` | roles_required(UserRole.ADMIN); _parse_booking_filter_id; get_admin_booking_filter_options; list_admin_catalog; list_admin_match_operations |
| `admin.match_detail` | GET `/admin/matches/<int:match_id>` | `app/routes/admin.py:608` | roles_required(UserRole.ADMIN); _match_list_return_params; get_admin_match_detail |
| `admin.monitoring` | GET `/admin/monitoring` | `app/routes/admin.py:648` | roles_required(UserRole.ADMIN); _match_list_return_params; list_admin_catalog; list_admin_monitoring_locations; list_admin_monitoring_provinces; list_admin_monitoring_wards |
| `admin.booking_monitoring_detail` | GET `/admin/monitoring/bookings/<string:booking_code>` | `app/routes/admin.py:794` | roles_required(UserRole.ADMIN); _booking_list_return_params |
| `admin.owner_applications` | GET `/admin/owner-applications` | `app/routes/admin.py:368` | roles_required(UserRole.ADMIN); list_owner_applications |
| `admin.review_owner_application_route` | POST `/admin/owner-applications/<int:application_id>/review` | `app/routes/admin.py:395` | roles_required(UserRole.ADMIN); review_owner_application |
| `admin.accounts` | GET `/admin/users` | `app/routes/admin.py:258` | roles_required(UserRole.ADMIN) |
| `admin.account_detail` | GET `/admin/users/<int:account_id>` | `app/routes/admin.py:264` | roles_required(UserRole.ADMIN) |
| `admin.update_account_status` | POST `/admin/users/<int:account_id>/status` | `app/routes/admin.py:319` | roles_required(UserRole.ADMIN); set_admin_account_status |
| `venues.admin_index` | GET `/admin/venues` | `app/routes/venues.py:405` | roles_required(UserRole.ADMIN); list_admin_venues |
| `venues.admin_moderate` | POST `/admin/venues/<int:venue_id>/moderate` | `app/routes/venues.py:462` | roles_required(UserRole.ADMIN); moderate_venue |
| `venues.administrative_wards` | GET `/api/administrative-units/wards` | `app/routes/venues.py:440` |  |
| `auth.login` | GET, POST `/auth/login` | `app/routes/auth.py:45` |  |
| `auth.logout` | POST `/auth/logout` | `app/routes/auth.py:72` | login_required |
| `auth.register` | GET, POST `/auth/register` | `app/routes/auth.py:22` |  |
| `bookings.index` | GET `/bookings` | `app/routes/bookings.py:361` | roles_required(UserRole.USER, UserRole.OWNER); _group_bookings_for_display; list_user_bookings; list_user_match_requests |
| `bookings.detail` | GET `/bookings/<string:booking_code>` | `app/routes/bookings.py:380` | roles_required(UserRole.USER, UserRole.OWNER); _successful_refund_total; get_effective_booking_status; get_user_booking |
| `bookings.cancel` | POST `/bookings/<string:booking_code>/cancel` | `app/routes/bookings.py:417` | roles_required(UserRole.USER, UserRole.OWNER); cancel_user_booking |
| `payments.pay_mock` | POST `/bookings/<string:booking_code>/contributions/<int:contribution_id>/payments/mock` | `app/routes/payments.py:38` | roles_required(UserRole.USER, UserRole.OWNER); _payment_redirect |
| `payments.pay_momo` | POST `/bookings/<string:booking_code>/contributions/<int:contribution_id>/payments/momo` | `app/routes/payments.py:96` | roles_required(UserRole.USER, UserRole.OWNER); _payment_redirect; start_momo_payment |
| `matches.create` | GET, POST `/bookings/<string:booking_code>/matches/new` | `app/routes/matches.py:220` | roles_required(UserRole.USER, UserRole.OWNER); _default_match_title; _locked_match_type; create_match; get_user_booking; validate_match_creation |
| `payments.top_up_mock` | POST `/bookings/<string:booking_code>/payments/mock/top-up` | `app/routes/payments.py:66` | roles_required(UserRole.USER, UserRole.OWNER); _booking_redirect; top_up_booking_with_mock |
| `payments.top_up_momo` | POST `/bookings/<string:booking_code>/payments/momo/top-up` | `app/routes/payments.py:121` | roles_required(UserRole.USER, UserRole.OWNER); _booking_redirect |
| `health.health` | GET `/health` | `app/routes/health.py:12` |  |
| `health.readiness` | GET `/health/ready` | `app/routes/health.py:23` |  |
| `matches.index` | GET `/matches` | `app/routes/matches.py:112` | _match_view_label; _match_view_status; match_accepts_actions; search_open_matches |
| `matches.detail` | GET `/matches/<int:match_id>` | `app/routes/matches.py:295` | _match_has_joined_opponent; _match_view_status; get_match; match_accepts_actions; participant_withdrawal_gets_refund |
| `matches.close` | POST `/matches/<int:match_id>/close` | `app/routes/matches.py:385` | roles_required(UserRole.USER, UserRole.OWNER) |
| `matches.update_contact` | POST `/matches/<int:match_id>/contact` | `app/routes/matches.py:439` | roles_required(UserRole.USER, UserRole.OWNER); update_match_contact |
| `matches.join` | POST `/matches/<int:match_id>/requests` | `app/routes/matches.py:405` | roles_required(UserRole.USER, UserRole.OWNER); request_to_join_match |
| `matches.accept` | POST `/matches/<int:match_id>/requests/<int:participant_id>/accept` | `app/routes/matches.py:466` | roles_required(UserRole.USER, UserRole.OWNER) |
| `matches.reject` | POST `/matches/<int:match_id>/requests/<int:participant_id>/reject` | `app/routes/matches.py:474` | roles_required(UserRole.USER, UserRole.OWNER) |
| `matches.withdraw` | POST `/matches/<int:match_id>/requests/withdraw` | `app/routes/matches.py:480` | roles_required(UserRole.USER, UserRole.OWNER); withdraw_match_request |
| `matches.mine` | GET `/matches/mine` | `app/routes/matches.py:193` | roles_required(UserRole.USER, UserRole.OWNER); _match_view_label; _match_view_status; list_created_matches; list_user_match_requests; match_accepts_actions |
| `media.image` | GET `/media/<int:media_id>` | `app/routes/media.py:26` | resolve_media_path |
| `owner.dashboard` | GET `/owner` | `app/routes/owner.py:61` | roles_required(UserRole.OWNER); get_owner_dashboard_summary |
| `owner_applications.mine` | GET `/owner-applications/mine` | `app/routes/owner_applications.py:53` | login_required |
| `owner_applications.create` | GET, POST `/owner-applications/new` | `app/routes/owner_applications.py:23` | roles_required(UserRole.USER); submit_owner_application |
| `bookings.owner_index` | GET `/owner/bookings` | `app/routes/bookings.py:440` | roles_required(UserRole.OWNER); _group_bookings_for_display; list_owner_bookings |
| `bookings.owner_detail` | GET `/owner/bookings/<string:booking_code>` | `app/routes/bookings.py:453` | roles_required(UserRole.OWNER); _load_owner_booking; _render_owner_booking_detail |
| `bookings.owner_cancel` | POST `/owner/bookings/<string:booking_code>/cancel` | `app/routes/bookings.py:486` | roles_required(UserRole.OWNER); _load_owner_booking; _render_owner_booking_detail; cancel_owner_booking |
| `owner.finance` | GET `/owner/finance` | `app/routes/owner.py:124` | roles_required(UserRole.OWNER); get_owner_finance_summary |
| `owner.schedule` | GET `/owner/schedule` | `app/routes/owner.py:72` | roles_required(UserRole.OWNER); get_owner_schedule_summary |
| `venues.owner_index` | GET `/owner/venues` | `app/routes/venues.py:265` | roles_required(UserRole.OWNER); list_owner_venue_summaries |
| `venues.owner_edit` | GET, POST `/owner/venues/<int:venue_id>/edit` | `app/routes/venues.py:347` | roles_required(UserRole.OWNER); _configure_administrative_choices; get_owner_venue; update_venue |
| `fields.owner_index` | GET `/owner/venues/<int:venue_id>/fields` | `app/routes/fields.py:29` | roles_required(UserRole.OWNER); list_owner_fields |
| `fields.owner_edit` | GET, POST `/owner/venues/<int:venue_id>/fields/<int:field_id>/edit` | `app/routes/fields.py:104` | roles_required(UserRole.OWNER); _configure_field_type_choices; get_owner_field; update_field |
| `maintenance.owner_index` | GET `/owner/venues/<int:venue_id>/fields/<int:field_id>/maintenances` | `app/routes/maintenance.py:35` | roles_required(UserRole.OWNER); _load_field_for_path |
| `maintenance.owner_cancel` | POST `/owner/venues/<int:venue_id>/fields/<int:field_id>/maintenances/<int:maintenance_id>/cancel` | `app/routes/maintenance.py:138` | roles_required(UserRole.OWNER) |
| `maintenance.owner_create` | GET, POST `/owner/venues/<int:venue_id>/fields/<int:field_id>/maintenances/new` | `app/routes/maintenance.py:95` | roles_required(UserRole.OWNER); _load_field_for_path |
| `media.field_upload` | POST `/owner/venues/<int:venue_id>/fields/<int:field_id>/media` | `app/routes/media.py:128` | roles_required(UserRole.OWNER); upload_field_image |
| `media.field_cover` | POST `/owner/venues/<int:venue_id>/fields/<int:field_id>/media/<int:media_id>/cover` | `app/routes/media.py:168` | roles_required(UserRole.OWNER); set_field_cover |
| `media.field_delete` | POST `/owner/venues/<int:venue_id>/fields/<int:field_id>/media/<int:media_id>/delete` | `app/routes/media.py:199` | roles_required(UserRole.OWNER); delete_field_image |
| `pricing.owner_index` | GET `/owner/venues/<int:venue_id>/fields/<int:field_id>/prices` | `app/routes/pricing.py:37` | roles_required(UserRole.OWNER); _load_field_for_path |
| `pricing.owner_edit` | GET, POST `/owner/venues/<int:venue_id>/fields/<int:field_id>/prices/<int:slot_id>/edit` | `app/routes/pricing.py:98` | roles_required(UserRole.OWNER); update_price_slot |
| `pricing.owner_set_slot_status` | POST `/owner/venues/<int:venue_id>/fields/<int:field_id>/prices/<int:slot_id>/status/<string:status>` | `app/routes/pricing.py:148` | roles_required(UserRole.OWNER); set_price_slot_status |
| `pricing.owner_create` | GET, POST `/owner/venues/<int:venue_id>/fields/<int:field_id>/prices/new` | `app/routes/pricing.py:54` | roles_required(UserRole.OWNER); _load_field_for_path; create_price_slot |
| `pricing.owner_set_field_status` | POST `/owner/venues/<int:venue_id>/fields/<int:field_id>/status/<string:status>` | `app/routes/pricing.py:202` | roles_required(UserRole.OWNER); _load_field_for_path; set_field_activation |
| `fields.owner_create` | GET, POST `/owner/venues/<int:venue_id>/fields/new` | `app/routes/fields.py:53` | roles_required(UserRole.OWNER); _configure_field_type_choices; create_field; list_owner_fields |
| `media.venue_upload` | POST `/owner/venues/<int:venue_id>/media` | `app/routes/media.py:56` | roles_required(UserRole.OWNER); upload_venue_image |
| `media.venue_cover` | POST `/owner/venues/<int:venue_id>/media/<int:media_id>/cover` | `app/routes/media.py:82` | roles_required(UserRole.OWNER); set_venue_cover |
| `media.venue_delete` | POST `/owner/venues/<int:venue_id>/media/<int:media_id>/delete` | `app/routes/media.py:105` | roles_required(UserRole.OWNER); delete_venue_image |
| `venues.owner_geocode` | POST `/owner/venues/geocode` | `app/routes/venues.py:275` | roles_required(UserRole.OWNER); geocode_venue_address |
| `venues.owner_create` | GET, POST `/owner/venues/new` | `app/routes/venues.py:302` | roles_required(UserRole.OWNER); _configure_administrative_choices; create_venue |
| `payments.momo_ipn` | POST `/payments/momo/ipn` | `app/routes/payments.py:204` | csrf.exempt; process_momo_payment_notification |
| `payments.momo_return` | GET `/payments/momo/return` | `app/routes/payments.py:144` | _safe_booking_return |
| `venues.index` | GET `/venues` | `app/routes/venues.py:108` | _venue_search_context; search_public_venues |
| `venues.detail` | GET `/venues/<int:venue_id>` | `app/routes/venues.py:202` | _public_venue_map_data; _venue_search_context; get_public_venue; list_public_fields |
| `bookings.availability` | GET `/venues/<int:venue_id>/fields/<int:field_id>/bookings/availability` | `app/routes/bookings.py:319` | roles_required(UserRole.USER, UserRole.OWNER); build_field_availability; get_booking_field |
| `bookings.create` | GET, POST `/venues/<int:venue_id>/fields/<int:field_id>/bookings/new` | `app/routes/bookings.py:148` | roles_required(UserRole.USER, UserRole.OWNER); create_booking; get_booking_field |
| `bookings.quote` | POST `/venues/<int:venue_id>/fields/<int:field_id>/bookings/quote` | `app/routes/bookings.py:248` | roles_required(UserRole.USER, UserRole.OWNER); get_booking_field; quote_booking |
| `bookings.time_quote` | POST `/venues/<int:venue_id>/fields/<int:field_id>/bookings/time-quote` | `app/routes/bookings.py:201` | roles_required(UserRole.USER, UserRole.OWNER); get_booking_field; quote_booking_time |

## Phụ lục B — Model / column inventory

`?` = nullable; giá trị default ghi từ metadata SQLAlchemy (không khẳng định mọi default đều là server default). Các CHECK/FK đã đối chiếu live được đánh giá ở phần Database / Migration Audit.

### `booking_contributions`

| Column | Type | Nullable | Primary key | Default / server default |
|---|---|---|---|---|
| `id` | `INTEGER` | NO | PK |  |
| `booking_id` | `INTEGER` | NO |  |  |
| `user_id` | `INTEGER` | ? |  |  |
| `contribution_type` | `VARCHAR(30)` | NO |  |  |
| `slot_number` | `INTEGER` | ? |  |  |
| `amount_due` | `NUMERIC(12, 2)` | NO |  |  |
| `amount_paid` | `NUMERIC(12, 2)` | NO |  | 0.00 / 0 |
| `status` | `VARCHAR(30)` | NO |  | PENDING / PENDING |
| `expires_at` | `DATETIME` | ? |  |  |
| `created_at` | `DATETIME` | NO |  | utc_now |
| `updated_at` | `DATETIME` | ? |  |  |

Foreign keys: `user_id` → `users.id` (ondelete=default); `booking_id` → `bookings.id` (ondelete=default).

Constraints: `ForeignKeyConstraint:unnamed`; `ForeignKeyConstraint:unnamed`; `PrimaryKeyConstraint:unnamed`; `CheckConstraint:ck_booking_contributions_amount_due_non_negative` amount_due >= 0; `CheckConstraint:ck_booking_contributions_amount_paid_range` amount_paid >= 0 AND amount_paid <= amount_due; `CheckConstraint:ck_booking_contributions_slot_number` ((contribution_type IN ('CREATOR', 'TOP_UP') AND slot_number IS NULL) OR (contribution_type IN ('OPPONENT', 'PLAYER') AND slot_number IS NOT NULL AND slot_number > 0)); `CheckConstraint:ck_booking_contributions_status` status IN ('PENDING', 'PAID', 'EXPIRED', 'WAIVED', 'REFUND_PENDING', 'PARTIALLY_REFUNDED', 'REFUNDED', 'FORFEITED'); `CheckConstraint:ck_booking_contributions_type` contribution_type IN ('CREATOR', 'OPPONENT', 'PLAYER', 'TOP_UP').

### `booking_price_details`

| Column | Type | Nullable | Primary key | Default / server default |
|---|---|---|---|---|
| `id` | `INTEGER` | NO | PK |  |
| `booking_id` | `INTEGER` | NO |  |  |
| `price_slot_id` | `INTEGER` | NO |  |  |
| `start_time` | `TIME` | NO |  |  |
| `end_time` | `TIME` | NO |  |  |
| `duration_minutes` | `INTEGER` | NO |  |  |
| `hourly_price` | `NUMERIC(12, 2)` | NO |  |  |
| `subtotal` | `NUMERIC(12, 2)` | NO |  |  |

Foreign keys: `booking_id` → `bookings.id` (ondelete=default); `price_slot_id` → `field_price_slots.id` (ondelete=default).

Constraints: `ForeignKeyConstraint:unnamed`; `PrimaryKeyConstraint:unnamed`; `ForeignKeyConstraint:unnamed`; `CheckConstraint:ck_booking_price_details_duration_positive` duration_minutes > 0; `CheckConstraint:ck_booking_price_details_hourly_price_positive` hourly_price > 0; `CheckConstraint:ck_booking_price_details_start_before_end` start_time < end_time; `CheckConstraint:ck_booking_price_details_subtotal_positive` subtotal > 0.

### `bookings`

| Column | Type | Nullable | Primary key | Default / server default |
|---|---|---|---|---|
| `id` | `INTEGER` | NO | PK |  |
| `booking_code` | `VARCHAR(30)` | NO |  |  |
| `user_id` | `INTEGER` | NO |  |  |
| `field_id` | `INTEGER` | NO |  |  |
| `booking_date` | `DATE` | NO |  |  |
| `start_time` | `TIME` | NO |  |  |
| `end_time` | `TIME` | NO |  |  |
| `booking_mode` | `VARCHAR(30)` | NO |  |  |
| `play_format` | `VARCHAR(20)` | ? |  |  |
| `requested_players` | `INTEGER` | ? |  |  |
| `payment_policy` | `VARCHAR(30)` | NO |  |  |
| `total_amount` | `NUMERIC(12, 2)` | NO |  |  |
| `deposit_rate` | `NUMERIC(5, 4)` | NO |  |  |
| `deposit_amount` | `NUMERIC(12, 2)` | NO |  |  |
| `paid_amount` | `NUMERIC(12, 2)` | NO |  | 0.00 / 0 |
| `cancellation_fee_amount` | `NUMERIC(12, 2)` | NO |  | 0.00 / 0 |
| `status` | `VARCHAR(30)` | NO |  | CONFIRMED / PENDING |
| `initial_payment_due_at` | `DATETIME` | ? |  |  |
| `funding_deadline` | `DATETIME` | ? |  |  |
| `matchmaking_deadline` | `DATETIME` | ? |  |  |
| `note` | `VARCHAR(500)` | ? |  |  |
| `cancellation_reason` | `VARCHAR(500)` | ? |  |  |
| `created_at` | `DATETIME` | NO |  | utc_now |
| `updated_at` | `DATETIME` | ? |  |  |

Foreign keys: `user_id` → `users.id` (ondelete=default); `field_id` → `fields.id` (ondelete=default).

Constraints: `ForeignKeyConstraint:unnamed`; `PrimaryKeyConstraint:unnamed`; `UniqueConstraint:unnamed`; `ForeignKeyConstraint:unnamed`; `CheckConstraint:ck_bookings_booking_mode` booking_mode IN ('DIRECT_BOOKING', 'FIND_OPPONENT', 'FIND_PLAYERS'); `CheckConstraint:ck_bookings_cancellation_fee_range` cancellation_fee_amount >= 0 AND cancellation_fee_amount <= paid_amount; `CheckConstraint:ck_bookings_deposit_amount_range` deposit_amount > 0 AND deposit_amount <= total_amount; `CheckConstraint:ck_bookings_deposit_rate` deposit_rate > 0 AND deposit_rate <= 1; `CheckConstraint:ck_bookings_paid_amount_range` paid_amount >= 0 AND paid_amount <= deposit_amount; `CheckConstraint:ck_bookings_payment_policy` payment_policy IN ('LEGACY_FULL_ONLINE', 'DEPOSIT_30'); `CheckConstraint:ck_bookings_play_format` play_format IS NULL OR play_format IN ('SINGLES', 'DOUBLES'); `CheckConstraint:ck_bookings_requested_players` ((booking_mode = 'FIND_PLAYERS' AND requested_players IS NOT NULL AND requested_players > 0) OR (booking_mode <> 'FIND_PLAYERS' AND requested_players IS NULL)); `CheckConstraint:ck_bookings_start_before_end` start_time < end_time; `CheckConstraint:ck_bookings_status` status IN ('PENDING', 'CONFIRMED', 'PARTIALLY_PAID', 'PAID', 'REFUND_PENDING', 'COMPLETED', 'REJECTED', 'CANCELLED', 'EXPIRED'); `CheckConstraint:ck_bookings_total_amount_positive` total_amount > 0.

### `field_maintenances`

| Column | Type | Nullable | Primary key | Default / server default |
|---|---|---|---|---|
| `id` | `INTEGER` | NO | PK |  |
| `field_id` | `INTEGER` | NO |  |  |
| `maintenance_date` | `DATE` | NO |  |  |
| `start_time` | `TIME` | NO |  |  |
| `end_time` | `TIME` | NO |  |  |
| `reason` | `VARCHAR(500)` | NO |  |  |
| `status` | `VARCHAR(20)` | NO |  | ACTIVE / ACTIVE |
| `created_by` | `INTEGER` | NO |  |  |
| `created_at` | `DATETIME` | NO |  | utc_now |

Foreign keys: `created_by` → `users.id` (ondelete=default); `field_id` → `fields.id` (ondelete=default).

Constraints: `ForeignKeyConstraint:unnamed`; `PrimaryKeyConstraint:unnamed`; `ForeignKeyConstraint:unnamed`; `CheckConstraint:ck_field_maintenances_start_before_end` start_time < end_time; `CheckConstraint:ck_field_maintenances_status` status IN ('ACTIVE', 'CANCELLED', 'COMPLETED').

### `field_price_slots`

| Column | Type | Nullable | Primary key | Default / server default |
|---|---|---|---|---|
| `id` | `INTEGER` | NO | PK |  |
| `field_id` | `INTEGER` | NO |  |  |
| `day_of_week` | `SMALLINT` | NO |  |  |
| `start_time` | `TIME` | NO |  |  |
| `end_time` | `TIME` | NO |  |  |
| `hourly_price` | `NUMERIC(12, 2)` | NO |  |  |
| `status` | `VARCHAR(20)` | NO |  | ACTIVE / ACTIVE |
| `created_at` | `DATETIME` | NO |  | utc_now |
| `updated_at` | `DATETIME` | ? |  |  |

Foreign keys: `field_id` → `fields.id` (ondelete=default).

Constraints: `PrimaryKeyConstraint:unnamed`; `ForeignKeyConstraint:unnamed`; `CheckConstraint:ck_price_slots_day_of_week` day_of_week BETWEEN 0 AND 6; `CheckConstraint:ck_price_slots_hourly_price_positive` hourly_price > 0; `CheckConstraint:ck_price_slots_start_before_end` start_time < end_time; `CheckConstraint:ck_price_slots_status` status IN ('ACTIVE', 'INACTIVE').

### `field_types`

| Column | Type | Nullable | Primary key | Default / server default |
|---|---|---|---|---|
| `id` | `INTEGER` | NO | PK |  |
| `sport_id` | `INTEGER` | NO |  |  |
| `code` | `VARCHAR(50)` | NO |  |  |
| `name` | `VARCHAR(100)` | NO |  |  |
| `standard_players_per_side` | `INTEGER` | ? |  |  |
| `status` | `VARCHAR(20)` | NO |  | ACTIVE / ACTIVE |
| `created_at` | `DATETIME` | NO |  | utc_now |
| `updated_at` | `DATETIME` | ? |  |  |

Foreign keys: `sport_id` → `sports.id` (ondelete=default).

Constraints: `ForeignKeyConstraint:unnamed`; `UniqueConstraint:unnamed`; `PrimaryKeyConstraint:unnamed`; `CheckConstraint:ck_field_types_players_per_side_positive` standard_players_per_side IS NULL OR standard_players_per_side > 0; `CheckConstraint:ck_field_types_status` status IN ('ACTIVE', 'INACTIVE'); `UniqueConstraint:uq_field_types_sport_name`.

### `fields`

| Column | Type | Nullable | Primary key | Default / server default |
|---|---|---|---|---|
| `id` | `INTEGER` | NO | PK |  |
| `venue_id` | `INTEGER` | NO |  |  |
| `name` | `VARCHAR(100)` | NO |  |  |
| `field_type_id` | `INTEGER` | NO |  |  |
| `surface_type` | `VARCHAR(50)` | ? |  |  |
| `capacity` | `INTEGER` | NO |  |  |
| `status` | `VARCHAR(20)` | NO |  | INACTIVE / INACTIVE |
| `created_at` | `DATETIME` | NO |  | utc_now |
| `updated_at` | `DATETIME` | ? |  |  |

Foreign keys: `venue_id` → `venues.id` (ondelete=default); `field_type_id` → `field_types.id` (ondelete=default).

Constraints: `ForeignKeyConstraint:unnamed`; `ForeignKeyConstraint:unnamed`; `PrimaryKeyConstraint:unnamed`; `CheckConstraint:ck_fields_capacity_positive` capacity > 0; `CheckConstraint:ck_fields_status` status IN ('ACTIVE', 'INACTIVE'); `UniqueConstraint:uq_fields_venue_name`.

### `match_participants`

| Column | Type | Nullable | Primary key | Default / server default |
|---|---|---|---|---|
| `id` | `INTEGER` | NO | PK |  |
| `match_id` | `INTEGER` | NO |  |  |
| `user_id` | `INTEGER` | NO |  |  |
| `contribution_id` | `INTEGER` | ? |  |  |
| `participant_type` | `VARCHAR(30)` | NO |  |  |
| `message` | `VARCHAR(500)` | ? |  |  |
| `contact_phone` | `VARCHAR(20)` | ? |  |  |
| `status` | `VARCHAR(30)` | NO |  | PENDING / PENDING |
| `payment_due_at` | `DATETIME` | ? |  |  |
| `created_at` | `DATETIME` | NO |  | utc_now |
| `decided_at` | `DATETIME` | ? |  |  |
| `updated_at` | `DATETIME` | ? |  |  |

Foreign keys: `user_id` → `users.id` (ondelete=default); `contribution_id` → `booking_contributions.id` (ondelete=default); `match_id` → `matches.id` (ondelete=default).

Constraints: `ForeignKeyConstraint:unnamed`; `ForeignKeyConstraint:unnamed`; `PrimaryKeyConstraint:unnamed`; `ForeignKeyConstraint:unnamed`; `CheckConstraint:ck_match_participants_status` status IN ('PENDING', 'ACCEPTED_AWAITING_PAYMENT', 'JOINED', 'REJECTED', 'EXPIRED', 'WITHDRAWN'); `CheckConstraint:ck_match_participants_type` participant_type IN ('PLAYER', 'OPPONENT_REPRESENTATIVE').

### `matches`

| Column | Type | Nullable | Primary key | Default / server default |
|---|---|---|---|---|
| `id` | `INTEGER` | NO | PK |  |
| `creator_id` | `INTEGER` | NO |  |  |
| `booking_id` | `INTEGER` | NO |  |  |
| `match_type` | `VARCHAR(30)` | NO |  |  |
| `title` | `VARCHAR(200)` | NO |  |  |
| `description` | `TEXT` | ? |  |  |
| `skill_level` | `VARCHAR(30)` | ? |  |  |
| `creator_contact_phone` | `VARCHAR(20)` | ? |  |  |
| `total_players` | `INTEGER` | ? |  |  |
| `required_players` | `INTEGER` | NO |  |  |
| `status` | `VARCHAR(20)` | NO |  | OPEN / OPEN |
| `created_at` | `DATETIME` | NO |  | utc_now |
| `updated_at` | `DATETIME` | ? |  |  |

Foreign keys: `creator_id` → `users.id` (ondelete=default); `booking_id` → `bookings.id` (ondelete=default).

Constraints: `ForeignKeyConstraint:unnamed`; `UniqueConstraint:unnamed`; `ForeignKeyConstraint:unnamed`; `PrimaryKeyConstraint:unnamed`; `CheckConstraint:ck_matches_configuration` ((match_type = 'FIND_OPPONENT' AND required_players = 1 AND total_players IS NULL) OR (match_type = 'FIND_PLAYERS' AND total_players IS NOT NULL AND total_players > 1 AND required_players < total_players)); `CheckConstraint:ck_matches_required_players_positive` required_players > 0; `CheckConstraint:ck_matches_status` status IN ('OPEN', 'FULL', 'CONFIRMED', 'CANCELLED', 'COMPLETED'); `CheckConstraint:ck_matches_type` match_type IN ('FIND_PLAYERS', 'FIND_OPPONENT').

### `media_images`

| Column | Type | Nullable | Primary key | Default / server default |
|---|---|---|---|---|
| `id` | `INTEGER` | NO | PK |  |
| `venue_id` | `INTEGER` | ? |  |  |
| `field_id` | `INTEGER` | ? |  |  |
| `storage_path` | `VARCHAR(255)` | NO |  |  |
| `original_filename` | `VARCHAR(255)` | NO |  |  |
| `content_type` | `VARCHAR(50)` | NO |  |  |
| `size_bytes` | `INTEGER` | NO |  |  |
| `is_cover` | `BOOLEAN` | NO |  | False / false |
| `created_at` | `DATETIME` | NO |  | utc_now |

Foreign keys: `venue_id` → `venues.id` (ondelete=CASCADE); `field_id` → `fields.id` (ondelete=CASCADE).

Constraints: `ForeignKeyConstraint:unnamed`; `UniqueConstraint:unnamed`; `PrimaryKeyConstraint:unnamed`; `ForeignKeyConstraint:unnamed`; `CheckConstraint:ck_media_images_single_parent` (venue_id IS NOT NULL AND field_id IS NULL) OR (venue_id IS NULL AND field_id IS NOT NULL); `CheckConstraint:ck_media_images_size_positive` size_bytes > 0.

### `owner_applications`

| Column | Type | Nullable | Primary key | Default / server default |
|---|---|---|---|---|
| `id` | `INTEGER` | NO | PK |  |
| `user_id` | `INTEGER` | NO |  |  |
| `business_name` | `VARCHAR(150)` | NO |  |  |
| `contact_phone` | `VARCHAR(20)` | NO |  |  |
| `note` | `VARCHAR(500)` | ? |  |  |
| `status` | `VARCHAR(20)` | NO |  | PENDING |
| `rejection_reason` | `VARCHAR(500)` | ? |  |  |
| `reviewed_by` | `INTEGER` | ? |  |  |
| `reviewed_at` | `DATETIME` | ? |  |  |
| `created_at` | `DATETIME` | NO |  | utc_now |

Foreign keys: `user_id` → `users.id` (ondelete=default); `reviewed_by` → `users.id` (ondelete=default).

Constraints: `PrimaryKeyConstraint:unnamed`; `ForeignKeyConstraint:unnamed`; `ForeignKeyConstraint:unnamed`; `CheckConstraint:ck_owner_applications_status` status IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED').

### `payments`

| Column | Type | Nullable | Primary key | Default / server default |
|---|---|---|---|---|
| `id` | `INTEGER` | NO | PK |  |
| `booking_id` | `INTEGER` | NO |  |  |
| `contribution_id` | `INTEGER` | NO |  |  |
| `payer_id` | `INTEGER` | NO |  |  |
| `provider` | `VARCHAR(20)` | NO |  |  |
| `payment_method` | `VARCHAR(30)` | NO |  |  |
| `amount` | `NUMERIC(12, 2)` | NO |  |  |
| `order_id` | `VARCHAR(100)` | NO |  |  |
| `request_id` | `VARCHAR(100)` | NO |  |  |
| `provider_trans_id` | `VARCHAR(100)` | ? |  |  |
| `status` | `VARCHAR(20)` | NO |  |  |
| `result_code` | `VARCHAR(20)` | ? |  |  |
| `checkout_url` | `VARCHAR(2000)` | ? |  |  |
| `paid_at` | `DATETIME` | ? |  |  |
| `created_at` | `DATETIME` | NO |  | utc_now |
| `updated_at` | `DATETIME` | ? |  |  |

Foreign keys: `payer_id` → `users.id` (ondelete=default); `contribution_id` → `booking_contributions.id` (ondelete=default); `booking_id` → `bookings.id` (ondelete=default).

Constraints: `UniqueConstraint:unnamed`; `ForeignKeyConstraint:unnamed`; `ForeignKeyConstraint:unnamed`; `PrimaryKeyConstraint:unnamed`; `UniqueConstraint:unnamed`; `ForeignKeyConstraint:unnamed`; `CheckConstraint:ck_payments_amount_positive` amount > 0; `CheckConstraint:ck_payments_method` payment_method IN ('SIMULATED', 'MOMO_WALLET'); `CheckConstraint:ck_payments_provider` provider IN ('MOCK', 'MOMO'); `CheckConstraint:ck_payments_status` status IN ('PENDING', 'SUCCESS', 'FAILED', 'CANCELLED', 'EXPIRED').

### `provinces`

| Column | Type | Nullable | Primary key | Default / server default |
|---|---|---|---|---|
| `code` | `VARCHAR(2)` | NO | PK |  |
| `name` | `VARCHAR(100)` | NO |  |  |

Foreign keys: không có.

Constraints: `PrimaryKeyConstraint:unnamed`; `UniqueConstraint:uq_provinces_name`.

### `refunds`

| Column | Type | Nullable | Primary key | Default / server default |
|---|---|---|---|---|
| `id` | `INTEGER` | NO | PK |  |
| `booking_id` | `INTEGER` | NO |  |  |
| `payment_id` | `INTEGER` | NO |  |  |
| `recipient_id` | `INTEGER` | NO |  |  |
| `amount` | `NUMERIC(12, 2)` | NO |  |  |
| `reason` | `VARCHAR(500)` | NO |  |  |
| `order_id` | `VARCHAR(100)` | NO |  |  |
| `request_id` | `VARCHAR(100)` | NO |  |  |
| `provider_refund_trans_id` | `VARCHAR(100)` | ? |  |  |
| `status` | `VARCHAR(30)` | NO |  |  |
| `result_code` | `VARCHAR(20)` | ? |  |  |
| `refunded_at` | `DATETIME` | ? |  |  |
| `created_at` | `DATETIME` | NO |  | utc_now |
| `updated_at` | `DATETIME` | ? |  |  |

Foreign keys: `recipient_id` → `users.id` (ondelete=default); `booking_id` → `bookings.id` (ondelete=default); `payment_id` → `payments.id` (ondelete=default).

Constraints: `UniqueConstraint:unnamed`; `ForeignKeyConstraint:unnamed`; `UniqueConstraint:unnamed`; `PrimaryKeyConstraint:unnamed`; `ForeignKeyConstraint:unnamed`; `ForeignKeyConstraint:unnamed`; `CheckConstraint:ck_refunds_amount_positive` amount > 0; `CheckConstraint:ck_refunds_status` status IN ('PENDING', 'PROCESSING', 'SUCCESS', 'FAILED').

### `sports`

| Column | Type | Nullable | Primary key | Default / server default |
|---|---|---|---|---|
| `id` | `INTEGER` | NO | PK |  |
| `code` | `VARCHAR(30)` | NO |  |  |
| `name` | `VARCHAR(100)` | NO |  |  |
| `status` | `VARCHAR(20)` | NO |  | ACTIVE / ACTIVE |
| `created_at` | `DATETIME` | NO |  | utc_now |
| `updated_at` | `DATETIME` | ? |  |  |

Foreign keys: không có.

Constraints: `PrimaryKeyConstraint:unnamed`; `UniqueConstraint:unnamed`; `UniqueConstraint:unnamed`; `CheckConstraint:ck_sports_status` status IN ('ACTIVE', 'INACTIVE').

### `users`

| Column | Type | Nullable | Primary key | Default / server default |
|---|---|---|---|---|
| `id` | `INTEGER` | NO | PK |  |
| `full_name` | `VARCHAR(100)` | NO |  |  |
| `email` | `VARCHAR(255)` | NO |  |  |
| `phone` | `VARCHAR(20)` | ? |  |  |
| `password_hash` | `VARCHAR(255)` | NO |  |  |
| `role` | `VARCHAR(20)` | NO |  | USER |
| `status` | `VARCHAR(20)` | NO |  | ACTIVE |
| `created_at` | `DATETIME` | NO |  | utc_now |
| `updated_at` | `DATETIME` | ? |  |  |

Foreign keys: không có.

Constraints: `UniqueConstraint:unnamed`; `PrimaryKeyConstraint:unnamed`; `CheckConstraint:ck_users_role` role IN ('USER', 'OWNER', 'ADMIN'); `CheckConstraint:ck_users_status` status IN ('ACTIVE', 'LOCKED', 'INACTIVE').

### `venues`

| Column | Type | Nullable | Primary key | Default / server default |
|---|---|---|---|---|
| `id` | `INTEGER` | NO | PK |  |
| `owner_id` | `INTEGER` | NO |  |  |
| `name` | `VARCHAR(150)` | NO |  |  |
| `address` | `VARCHAR(255)` | NO |  |  |
| `district` | `VARCHAR(100)` | ? |  |  |
| `city` | `VARCHAR(100)` | ? |  |  |
| `province_code` | `VARCHAR(2)` | ? |  |  |
| `province_name` | `VARCHAR(100)` | ? |  |  |
| `ward_code` | `VARCHAR(5)` | ? |  |  |
| `ward_name` | `VARCHAR(100)` | ? |  |  |
| `google_place_id` | `VARCHAR(255)` | ? |  |  |
| `latitude` | `NUMERIC(9, 6)` | ? |  |  |
| `longitude` | `NUMERIC(9, 6)` | ? |  |  |
| `phone` | `VARCHAR(20)` | ? |  |  |
| `description` | `TEXT` | ? |  |  |
| `opening_time` | `TIME` | NO |  |  |
| `closing_time` | `TIME` | NO |  |  |
| `status` | `VARCHAR(20)` | NO |  | PENDING / PENDING |
| `reviewed_by` | `INTEGER` | ? |  |  |
| `reviewed_at` | `DATETIME` | ? |  |  |
| `moderation_note` | `VARCHAR(500)` | ? |  |  |
| `created_at` | `DATETIME` | NO |  | utc_now |
| `updated_at` | `DATETIME` | ? |  |  |

Foreign keys: `ward_code` → `wards.code` (ondelete=default); `owner_id` → `users.id` (ondelete=default); `province_code` → `provinces.code` (ondelete=default); `reviewed_by` → `users.id` (ondelete=default).

Constraints: `ForeignKeyConstraint:unnamed`; `ForeignKeyConstraint:unnamed`; `ForeignKeyConstraint:unnamed`; `ForeignKeyConstraint:unnamed`; `PrimaryKeyConstraint:unnamed`; `CheckConstraint:ck_venues_coordinate_pair` (latitude IS NULL AND longitude IS NULL) OR (latitude IS NOT NULL AND longitude IS NOT NULL); `CheckConstraint:ck_venues_latitude_range` latitude IS NULL OR (latitude >= -90 AND latitude <= 90); `CheckConstraint:ck_venues_longitude_range` longitude IS NULL OR (longitude >= -180 AND longitude <= 180); `CheckConstraint:ck_venues_opening_before_closing` opening_time < closing_time; `CheckConstraint:ck_venues_status` status IN ('PENDING', 'ACTIVE', 'HIDDEN', 'INACTIVE').

### `wards`

| Column | Type | Nullable | Primary key | Default / server default |
|---|---|---|---|---|
| `code` | `VARCHAR(5)` | NO | PK |  |
| `province_code` | `VARCHAR(2)` | NO |  |  |
| `name` | `VARCHAR(100)` | NO |  |  |
| `type` | `VARCHAR(20)` | NO |  |  |

Foreign keys: `province_code` → `provinces.code` (ondelete=default).

Constraints: `PrimaryKeyConstraint:unnamed`; `ForeignKeyConstraint:unnamed`; `CheckConstraint:ck_wards_type` type IN ('PHUONG', 'XA', 'DAC_KHU').

## Phụ lục C — Migration inventory

| File | Revision | Down revision | Mô tả trong migration |
|---|---|---|---|
| `migrations/versions/1991532703dc_create_fields_table.py` | `1991532703dc` | `46d144661ea0` | create fields table |
| `migrations/versions/378937fd70e9_create_users_table.py` | `378937fd70e9` | `None` | create users table |
| `migrations/versions/3dae30a3dfcb_remove_manual_owner_approval_fields.py` | `3dae30a3dfcb` | `8aecda33c702` | remove manual owner approval fields |
| `migrations/versions/3f1f38dab5f1_add_payment_foundation_and_contribution_.py` | `3f1f38dab5f1` | `3dae30a3dfcb` | add payment foundation and contribution allocation |
| `migrations/versions/46d144661ea0_create_venues_table.py` | `46d144661ea0` | `90b6736cc5ac` | create venues table |
| `migrations/versions/5bcf59c01c23_create_matches_and_match_participants.py` | `5bcf59c01c23` | `3f1f38dab5f1` | create matches and match participants |
| `migrations/versions/78fbcd7c9576_create_field_price_slots_table.py` | `78fbcd7c9576` | `1991532703dc` | create field price slots table |
| `migrations/versions/7c4e2a1b9d60_reopen_refunded_match_slots.py` | `7c4e2a1b9d60` | `5bcf59c01c23` | reopen refunded match slots |
| `migrations/versions/8aecda33c702_create_bookings_and_price_snapshots.py` | `8aecda33c702` | `95239df4b6b1` | create bookings and price snapshots |
| `migrations/versions/90b6736cc5ac_create_owner_applications_table.py` | `90b6736cc5ac` | `378937fd70e9` | create owner applications table |
| `migrations/versions/95239df4b6b1_create_field_maintenances_table.py` | `95239df4b6b1` | `78fbcd7c9576` | create field maintenances table |
| `migrations/versions/a6d8e4f2c913_add_venue_and_field_media_images.py` | `a6d8e4f2c913` | `f3a7c9d2e410` | add venue and field media images |
| `migrations/versions/b2e91c4a7d10_add_multisport_catalog_and_venue_location.py` | `b2e91c4a7d10` | `7c4e2a1b9d60` | add multisport catalog and venue location |
| `migrations/versions/c4f8d2a6e901_add_deposit_booking_policy.py` | `c4f8d2a6e901` | `b2e91c4a7d10` | add deposit booking policy |
| `migrations/versions/d7a1b9e4c320_add_momo_checkout_url.py` | `d7a1b9e4c320` | `c4f8d2a6e901` | add momo checkout url |
| `migrations/versions/e8c4a2d9f701_add_match_creator_contact.py` | `e8c4a2d9f701` | `d7a1b9e4c320` | add match creator contact |
| `migrations/versions/f3a7c9d2e410_add_vietnam_administrative_catalog.py` | `f3a7c9d2e410` | `e8c4a2d9f701` | add vietnam administrative catalog |

## Phụ lục D — Test source inventory

Đếm AST các hàm `test_*`, câu lệnh `assert` và lời gọi `pytest.raises` trong từng file. Số hàm khác số case vì parametrization; kết quả thực thi chuẩn vẫn là **431 passed**. Cột import là liên kết source, không tự chứng minh coverage nhánh.

| File | Test functions | Assert statements | pytest.raises | App modules imported |
|---|---:|---:|---:|---|
| `tests/integration/test_admin.py` | 42 | 431 | 0 | `app.extensions`, `app.models`, `app.models.user`, `app.routes.admin`, `app.services` |
| `tests/integration/test_admin_booking_detail_polish.py` | 5 | 30 | 0 | `app.models` |
| `tests/integration/test_auth.py` | 11 | 46 | 0 | `app.decorators`, `app.extensions`, `app.models`, `app.services` |
| `tests/integration/test_booking_journey_ux.py` | 11 | 63 | 0 | `app.extensions`, `app.integrations`, `app.models`, `app.services` |
| `tests/integration/test_bookings.py` | 25 | 102 | 8 | `app.extensions`, `app.models`, `app.services` |
| `tests/integration/test_demo_data.py` | 3 | 24 | 1 | `app.extensions`, `app.models`, `app.services` |
| `tests/integration/test_fields.py` | 14 | 77 | 1 | `app.extensions`, `app.models`, `app.services` |
| `tests/integration/test_health.py` | 4 | 9 | 0 | `app`, `app.extensions` |
| `tests/integration/test_maintenance.py` | 17 | 47 | 3 | `app.extensions`, `app.models`, `app.services` |
| `tests/integration/test_match_journey_ux.py` | 9 | 73 | 0 | `app.extensions`, `app.models`, `app.routes.matches`, `app.services` |
| `tests/integration/test_matchmaking.py` | 20 | 133 | 5 | `app.extensions`, `app.models`, `app.services` |
| `tests/integration/test_matchmaking_fixes.py` | 10 | 53 | 6 | `app.extensions`, `app.models`, `app.services`, `app.services.matchmaking` |
| `tests/integration/test_media.py` | 9 | 59 | 3 | `app.extensions`, `app.models`, `app.services` |
| `tests/integration/test_momo_payments.py` | 7 | 79 | 1 | `app.extensions`, `app.integrations`, `app.models`, `app.services` |
| `tests/integration/test_multisport_maps.py` | 19 | 95 | 2 | `app.extensions`, `app.models`, `app.services` |
| `tests/integration/test_owner_applications.py` | 13 | 86 | 1 | `app.extensions`, `app.models`, `app.services` |
| `tests/integration/test_owner_dashboard.py` | 5 | 48 | 0 | `app.extensions`, `app.models`, `app.services`, `app.services.maintenance` |
| `tests/integration/test_owner_finance.py` | 5 | 67 | 0 | `app.extensions`, `app.models`, `app.services` |
| `tests/integration/test_owner_schedule.py` | 9 | 89 | 0 | `app.extensions`, `app.models`, `app.services`, `app.services.maintenance` |
| `tests/integration/test_payments.py` | 7 | 35 | 2 | `app.extensions`, `app.models`, `app.services` |
| `tests/integration/test_phase_4_1c_accessibility.py` | 4 | 16 | 0 | `app.models` |
| `tests/integration/test_pricing.py` | 15 | 55 | 4 | `app.extensions`, `app.models`, `app.services` |
| `tests/integration/test_refunds.py` | 9 | 84 | 0 | `app.extensions`, `app.models`, `app.services` |
| `tests/integration/test_venues.py` | 51 | 263 | 1 | `app.extensions`, `app.models`, `app.services` |
| `tests/unit/test_booking_model.py` | 3 | 16 | 0 | `app.models` |
| `tests/unit/test_contribution_service.py` | 5 | 12 | 1 | `app.models`, `app.services` |
| `tests/unit/test_field_maintenance_model.py` | 3 | 4 | 0 | `app.models` |
| `tests/unit/test_field_model.py` | 3 | 14 | 0 | `app.models` |
| `tests/unit/test_geocoding.py` | 2 | 8 | 1 | `app.services.geocoding` |
| `tests/unit/test_momo_client.py` | 3 | 7 | 1 | `app.integrations` |
| `tests/unit/test_owner_application_model.py` | 2 | 1 | 1 | `app.extensions`, `app.models`, `app.services` |
| `tests/unit/test_payment_models.py` | 2 | 14 | 0 | `app.models` |
| `tests/unit/test_price_slot_model.py` | 3 | 7 | 0 | `app.models` |
| `tests/unit/test_template_filters.py` | 4 | 5 | 0 | `app.template_filters` |
| `tests/unit/test_user_model.py` | 3 | 6 | 0 | `app.models` |
| `tests/unit/test_venue_model.py` | 5 | 11 | 0 | `app.models` |
