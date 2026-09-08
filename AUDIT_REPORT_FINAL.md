# AUDIT REPORT FINAL — MOCK-only MVP

Ngày kiểm tra: 08/09/2026. Repository: `SOURCE CODE DO AN NGANH`, HEAD nền `6f7a354008ec0739ee01995e4d45e3e3c196c9e4`, gồm các thay đổi working tree có sẵn và bản sửa trong lượt này. Không commit/push.

## 1. Scope cuối cùng

**Hệ thống sử dụng thanh toán mô phỏng trong môi trường thử nghiệm.**

Theo xác nhận GVHD được người dùng cung cấp, MOCK/SIMULATED PAYMENT ONLY là phạm vi thanh toán chính thức của MVP. Không yêu cầu MoMo Sandbox, credential M4B, URL callback HTTPS, IPN thật hoặc giao dịch hoàn tiền qua provider ngoài để nghiệm thu. ADR-039 ghi quyết định này và thay thế phạm vi provider trong tài liệu cũ.

Giữ nguyên các quy tắc cọc 30%, creator/opponent chia khoản cọc, quyền sở hữu, hạn giữ suất, forfeiture/refund hiện có. Không thêm settlement, payout, ví, thanh toán thật hoặc giao diện mới. Model, enum provider, field checkout, migration và lịch sử MoMo không bị xóa hay đổi nghĩa.

Báo cáo này thay thế kết luận readiness của `AUDIT_REPORT.md`. Báo cáo gốc giữ bằng chứng lịch sử và được thêm ghi chú chuyển scope. Lỗi chỉ thuộc MoMo không được dùng làm blocker cho runtime MOCK đã cô lập.

## 2. Xác minh trước khi sửa

Không chỉ dựa vào kết luận cũ: đã đọc lại source đang chạy, config, route, service, test và các vị trí có `with_for_update()`.

- Bộ regression ban đầu: **7 failed**, trước sửa production. Callback MoMo disabled ném `MomoConfigurationError` không được route xử lý; SQL biên dịch cho MSSQL thiếu lock hint; giá `100001.50` và `100000.001` được chấp nhận; booking 90 phút với giá `100001` lỗi tổng tiền không nguyên; PNG giả chỉ có magic bytes được chấp nhận; SQLite FK đang OFF.
- M04 được xác nhận bằng source: helper trả giờ Việt Nam naive nhưng gọi `astimezone(UTC)` trực tiếp, khiến Python dùng timezone host. Regression mô phỏng host UTC xác minh giữ chỗ còn hạn lúc 10:05 Việt Nam, hết hạn lúc 10:16.
- Các lỗi H02/H03/H05/H06/H07 được đối chiếu lại: nhánh gây lỗi chỉ chạy trong MoMo checkout/IPN/refund; không mở rộng triển khai những nhánh này.
- Không tác động dữ liệu nghiệp vụ SQL Server. Tái hiện booking/payment/image/FK bằng test app SQLite cô lập; kiểm tra SQL Server bằng metadata và transaction chỉ SELECT có lock rồi rollback.

## 3. Phân loại lại toàn bộ issue

Ba nhóm: **Applicable MOCK** = vẫn thuộc scope; **Không applicable MoMo-only** = không thuộc nghiệm thu; **Technical debt/legacy** = giữ lại, công khai giới hạn. FIXED không đồng nghĩa toàn hệ thống đã được kiểm thử mọi trường hợp đồng thời.

| ID | Nhóm trong scope mới | Kết quả / xử lý |
|---|---|---|
| H01 | Không applicable MoMo-only | MOCK là provider chính thức nên việc ghi nhận MOCK không phải bypass provider bắt buộc. Cấu hình MVP không bật MoMo từ env; không chặn payment MOCK hợp lệ. |
| H02 | Không applicable MoMo-only | Checkout MoMo dùng lại sai payer không được chạy: start service/route bị chặn. Không sửa checkout legacy. |
| H03 | Không applicable MoMo-only | Issue gốc là IPN MoMo báo resultCode thất bại nhưng giữ participant. MOCK hiện ghi SUCCESS đồng bộ hoặc rollback lỗi transaction; không có callback thất bại provider ngoài. Không thêm tính năng giả lập payment FAILED. Hạn giữ suất MOCK vẫn áp dụng. |
| H04 | Applicable MOCK — FIXED | Thay khóa ORM không hiệu lực MSSQL bằng helper `UPDLOCK,HOLDLOCK`; khóa parent cho pricing/media; refresh ORM instance sau lock. Có SQL compilation regression và kiểm tra hai transaction SQL Server. |
| H05 | Không applicable MoMo-only | Refund MoMo FAILED/retry ngoài scope; job disabled trả 0 trước truy vấn. Refund MOCK đồng bộ giữ nguyên. |
| H06 | Không applicable MoMo-only | Không nhận refund response provider ngoài trong MOCK. Không hoàn thiện response binding MoMo. |
| H07 | Không applicable MoMo-only | Không cần khôi phục IPN bị mất vì MOCK không chờ IPN; giữ query client legacy. |
| M01 | Không applicable MoMo-only | Không chạy batch HTTP refund, nên transaction chờ HTTP MoMo không xảy ra trong MVP. |
| M02 | Technical debt/legacy | Thông báo thành công khi refund còn PENDING là nhánh MoMo bất đồng bộ. Refund MOCK kết thúc cùng transaction; tests owner cancel/refund vẫn được giữ. Chưa sửa message phục vụ legacy MoMo. |
| M03 | Applicable MOCK — FIXED | Form/service từ chối đơn giá lẻ VND; subtotal làm tròn HALF_UP đến đồng, vẫn xuất JSON `.00`. Giữ Numeric(12,2) và snapshot cũ. Min/max riêng của MoMo không áp dụng. |
| M04 | Applicable MOCK — FIXED | Gắn timezone Việt Nam trước đổi UTC khi kiểm tra hạn giữ chỗ availability. |
| M05 | Applicable MOCK — FIXED | Giải mã JPG/PNG/WebP bằng Pillow, verify và load; giới hạn pixel và request; giữ kiểm tra MIME/extension/bytes/quyền/path. |
| M06 | Applicable MOCK — FIXED phần test nền | SQLite fixture bật FK mỗi connection; test orphan bị từ chối; test database rỗng chạy 17 migration đến head và so model. SQL Server schema đã kiểm tra live. Populated legacy upgrade và dựng mới SQL Server chưa thực hiện. |
| M07 | Applicable MOCK — FIXED | Đồng bộ README/scope/business/workflow/architecture/UI/acceptance/tests/roadmap; sửa mâu thuẫn play_format, tọa độ và số bảng; ADR-039 supersede provider cũ. |
| M08 | Technical debt/legacy | Đối soát late-success MoMo ngoài runtime. Database hiện tại chỉ có 13 Payment MOCK, không có Payment MoMo. Giữ lịch sử; nếu nhập lại dữ liệu MoMo thì cần review hiển thị tài chính legacy riêng. |
| M09 | Applicable MOCK — còn minor issue | KPI Admin đếm một số trạng thái persisted và dùng ngày host; có thể lệch trang dùng effective status khi job lifecycle chưa chạy. Không đổi dashboard trong lượt ưu tiên này. |
| M10 | Applicable MOCK — FIXED | Chặn sớm URL MoMo; service báo PaymentError trước truy vấn/network kể cả có injected client; job refund disabled không truy vấn. Không còn exception MoMo disabled phá luồng người dùng. |
| M11 | Applicable MOCK — còn minor issue | Một số danh sách lấy toàn bộ rồi phân trang/giới hạn trong Python. Chưa benchmark quy mô lớn; không tái hiện lỗi giao dịch trên dữ liệu demo. |
| L01 | Technical debt | Dependency khác chưa khóa toàn bộ; cấu hình development không là cấu hình production Internet. Pillow mới được pin phiên bản đã cài/kiểm thử. |
| L02 | Technical debt/legacy | Giữ helper/API có thể thừa và engine legacy; không cleanup/xóa ngoài scope. |
| L03 | Technical debt/tài liệu | `REPORT_GUIDE.md` vẫn không có trong workspace. Không tự tạo yêu cầu giả; không coi đây là lỗi runtime MOCK. |
| BR-C02 | Applicable MOCK — giữ contract hiện có | Ngoại lệ đối thủ thay thế sau forfeiture đã được docs BR-032 và test xác nhận trong repository: không thu lại khoản cọc đã còn trong booking. Không tự đổi thành thu lần hai; scope provider mới không thay đổi rule này. |

## 4. Bản sửa và bằng chứng

### H04 — khóa SQL Server

Files: `app/services/locking.py`, `pricing.py`, `field.py`, `venue.py`, `owner_application.py`, `media.py`.

Các đường mutation dùng `with_update_lock(statement, entity)`. MSSQL phát `WITH (UPDLOCK, HOLDLOCK)`; dialect khác dùng cơ chế hiện có. Parent Field được khóa trước kiểm tra overlap/ghi price slot; media khóa Venue hoặc Field trước chọn/đổi ảnh cover để tuần tự hóa thao tác cùng parent. Helper dùng `populate_existing=True` để không quyết định trên instance cũ trong identity map sau khi chờ lock. Không thêm constraint hay migration.

Regression: `test_sql_server_pricing_parent_lock_is_emitted`, `test_locked_read_refreshes_previously_cached_field`, cùng các test pricing/venue/field/owner application/media hiện có.

Kiểm tra live: transaction A SELECT một Field bằng helper; transaction B dùng cùng statement với LOCK_TIMEOUT=600ms bị SQL Server chặn (1222). Sau rollback A, B đọc được. Rollback B và khôi phục LOCK_TIMEOUT=-1. Không UPDATE/INSERT/DELETE dữ liệu nghiệp vụ. Đây là bằng chứng mutual exclusion của lock thực tế, **không phải benchmark tải hoặc kiểm thử mọi race/deadlock end-to-end**.

### M03 — số tiền VND

Files: `app/forms/pricing.py`, `app/services/pricing.py`.

Đơn giá mới phải là VND nguyên dương, kiểm tra trước lưu; không âm thầm làm tròn input lẻ thành hợp lệ. Tiền mỗi đoạn thuê làm tròn HALF_UP đến một đồng; tổng booking bằng tổng subtotal. Ví dụ 100001 VND/giờ × 90 phút → 150002 VND. Cọc tiếp tục theo contribution policy. JSON giữ dạng `150002.00`, schema/snapshot cũ không đổi. Đơn giá legacy lẻ không bị sửa hàng loạt; quote mới làm tròn subtotal.

Regression: hai giá lẻ bị từ chối; booking 90 phút lưu đúng tổng và snapshot; các test quote/time-quote cũ giữ nguyên assertion định dạng JSON và đã chạy lại. Không thêm giới hạn giao dịch MoMo vào MOCK.

### M04 — timezone

File: `app/services/availability.py`.

Chuẩn hóa giờ Việt Nam naive → gắn UTC+7 → chuyển UTC naive để so với deadline lưu DB. Không còn phụ thuộc timezone hệ điều hành ở phép so sánh này. Regression `test_availability_hold_uses_vietnam_time_on_utc_host` kiểm tra cả trước và sau hạn 15 phút. Không thay đổi quy ước timestamp/schema toàn hệ thống.

### M05 — ảnh

Files: `app/services/media.py`, `config.py`, `requirements.txt`.

Pillow 12.3.0 xác nhận định dạng thực, verify cấu trúc và load dữ liệu ảnh; từ chối ảnh hỏng/giả và ảnh vượt 20 triệu pixel. Giữ byte cap 5 MiB mặc định. Request body giới hạn MEDIA_MAX_BYTES + 1 MiB để có chỗ multipart. Không resize/re-encode ảnh hoặc redesign UI. Ảnh lịch sử không được quét/sửa tự động.

Regression: PNG có header nhưng không có ảnh bị từ chối; ảnh thật PNG/JPEG/WebP được nhận; pixel cap từ chối ảnh quá giới hạn; request quá giới hạn trả 413. Fixture test ảnh trước đây chỉ là magic bytes đã được thay bằng PNG thật, không bỏ assertion kiểm tra quyền/rollback/storage.

### M06 — FK/migration tests

Files: `tests/conftest.py`, `tests/integration/test_migration_head.py`, `tests/integration/test_mock_only_audit.py`.

Mọi connection của fixture SQLite dùng FK ON. Có test INSERT orphan FieldPriceSlot gây IntegrityError. Có test riêng dựng database SQLite trống qua migration, kiểm tra head/table set, `compare_metadata == []` và `foreign_key_check == []`. Suite nghiệp vụ vẫn dùng create_all để giữ tốc độ/cô lập, được bổ sung migration test thay vì tuyên bố create_all là kiểm thử migration.

### M10 và ranh giới provider

Files: `config.py`, `.env`, `.env.example`, `app/routes/payments.py`, `app/services/payment.py`, `app/services/refund.py`.

MOMO_ENABLED=false cố định trong BaseConfig, không bị env true bật lại; `.env` local cũng ghi false. Các URL start/top-up/return/IPN MoMo bị chặn khi disabled. Với request hợp lệ đi đến provider guard, trả 404; CSRF có thể từ chối POST thiếu token trước đó mà không gọi service. Service start/top-up/return/IPN kiểm tra cờ trước validation/query/mutation/client. Refund job disabled trả 0 trước query/lock/client, không ảnh hưởng refund MOCK.

Regression kiểm tra từng URL không gọi service; injected client không vượt được guard; env true không bật runtime; sau IPN bị từ chối, người dùng vẫn xem nút MOCK và thanh toán thành công, gửi lại không tạo Payment thứ hai. Test MoMo lịch sử được bật cờ rõ ràng trong test app cô lập và dùng transport giả; không phải provider runtime được bật lại.

### M07 — tài liệu

Files: README, `.env.example`, `app/README.md`, `tests/README.md`, `docs/01-project-overview.md` đến `docs/11-roadmap.md` (các tài liệu liên quan).

Bổ sung scope chính thức và ADR-039; bỏ hướng dẫn bật MoMo để demo MVP; đánh dấu IPN/HMAC/query/refund là legacy. Sửa README đang đòi SINGLES/DOUBLES trong booking mới; sửa BR-036 để phân biệt google_place_id legacy với tọa độ hiện hành theo ADR-036; architecture mô tả đúng 18 bảng. Tài liệu lịch sử ADR giữ nguyên, có quyết định mới supersede. Test count cuối lấy ở mục 6, không suy ra từ số cũ.

## 5. Issue còn lại và giới hạn

- **M09:** KPI persisted/effective và ngày host vẫn có thể khác nhau ở thời điểm chuyển trạng thái. Môi trường hiện tại Việt Nam; cần chạy job lifecycle đúng lịch khi demo dữ liệu có deadline. Chưa sửa hoặc tuyên bố tất cả KPI đồng bộ tức thời.
- **M11:** cần phân trang SQL/benchmark nếu tăng dữ liệu lớn. Không có benchmark đủ để khẳng định tải production.
- **L01/L02/L03:** dependency lock toàn bộ, cleanup có kiểm chứng và guide chưa cung cấp là công việc nhỏ/tài liệu/technical debt; không mở scope provider.
- **BR-C02:** giữ ngoại lệ đã có trong source/docs/tests. Nếu muốn thu 15% cho cả người thay thế thì đó là quyết định nghiệp vụ mới, không phải sửa provider.
- Fresh SQL Server rebuild, populated legacy upgrade và tải đồng thời toàn bộ workflows: **NEEDS VERIFICATION**. Không có thay đổi schema trong lượt này nên không áp migration lên database đang dùng.
- Browser E2E/mobile và kiểm tra ảnh lịch sử bằng trình duyệt không được thực hiện lại; không tuyên bố đã visual QA toàn UI. Không yêu cầu Sandbox E2E cho readiness MOCK-only.
- Code MoMo vẫn có các giới hạn audit cũ. Không xóa để che vấn đề; guard runtime là điều kiện để chúng không ảnh hưởng MVP.

## 6. Kết quả kiểm thử

**453 passed, 0 failed, 0 skipped, 2 warnings — 210,51 giây (3 phút 30 giây), exit code 0.** Tăng 22 case so với baseline 431.

Lệnh: `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider`, `PYTHONDONTWRITEBYTECODE=1`.

Nhóm regression mới: **22 passed**, gồm 21 case MOCK audit và 1 migration case. Trước sửa có 7 failing regression; các case bổ sung kiểm tra scope guard, host UTC, ảnh thật, request limit, FK enforcement, ORM refresh và schema rebuild. Lần chạy toàn bộ trung gian phát hiện 5 assertion JSON subtotal bị mất `.00`; đã sửa production để giữ contract và không sửa assertion cũ.

Hai cảnh báo DeprecationWarning từ `migrations/env.py` dùng `get_engine()` là technical debt tương thích Flask-SQLAlchemy tương lai; không xóa migration hoặc bỏ kiểm thử để che cảnh báo.

## 7. Trạng thái SQL Server / migration

- 18 bảng nghiệp vụ; 17 migration, head `a6d8e4f2c913`.
- Live SQL Server ở đúng revision; Alembic compare_metadata với compare_type=True trả `[]`, loại bảng công cụ SSMS `sysdiagrams` khỏi so sánh.
- Không có CHECK/FK disabled hoặc untrusted. Model và migration không thay đổi trong lượt sửa này.
- Live Payment: 13 bản ghi MOCK, không có Payment MoMo; không cần chuyển đổi hay xóa lịch sử để đạt scope mới.
- Probe lock hai transaction đã xác nhận chặn/nhả như mục 4; chỉ SELECT và rollback.
- Fresh SQLite migration test khớp model; không suy diễn thành đã rebuild SQL Server hoặc đã kiểm thử backfill dữ liệu legacy.

## 8. Files changed và phạm vi thay đổi

Production: `config.py`; `app/routes/payments.py`; `app/forms/pricing.py`; services `locking`, `pricing`, `field`, `venue`, `owner_application`, `media`, `availability`, `payment`, `refund`; `requirements.txt`; `.env` local chỉ cập nhật cờ provider, không in secret.

Tests: `tests/conftest.py`; thêm `test_mock_only_audit.py` và `test_migration_head.py`; cập nhật ảnh fixture trong `test_media.py`; opt-in test app legacy trong `test_momo_payments.py`, `test_booking_journey_ux.py` và test MoMo liên quan trong `test_matchmaking_fixes.py`. Giữ các assertion nghiệp vụ cũ.

Documentation: README, `.env.example`, app/tests README, bộ docs và ADR-039; ghi chú scope trên audit gốc; báo cáo final này.

Các thay đổi có sẵn ở Admin route/CSS/template, booking detail, test Admin/booking journey và hai file database đã staged được giữ; không reset, stage, commit hoặc push. Không sửa model, migration, dump SQL hoặc dữ liệu nghiệp vụ live. Không redesign UI.

**Business logic changed:** Có, có giới hạn: scope provider MOCK-only, guard MoMo, VND rounding/validation, khóa đồng thời, timezone availability, validation ảnh. Không thay tỷ lệ cọc, quyền sở hữu, policy hủy/forfeiture/refund hoặc cấu trúc dữ liệu lịch sử.

## 9. Final readiness

**READY WITH MINOR ISSUES** cho MVP MOCK-only trong môi trường thử nghiệm. Các lỗi ưu tiên thuộc phạm vi đã được sửa và full suite qua; M09/M11 cùng technical debt/giới hạn kiểm chứng ở mục 5 vẫn được công khai. Không còn blocker đã chứng minh thuộc các luồng MOCK được kiểm tra trong lượt này.

Đánh giá áp dụng cho đồ án trong môi trường thử nghiệm MOCK-only, không phải hệ thống thanh toán thật hay deployment production Internet. Các lỗi MoMo-only không là blocker vì provider đã bị disable và đã có regression chứng minh không đi vào DB/network qua các entry point MVP. Những giới hạn còn lại được công khai ở mục 5.
