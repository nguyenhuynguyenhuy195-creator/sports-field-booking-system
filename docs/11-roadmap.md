# ROADMAP – SPORTS FIELD BOOKING SYSTEM

## Mục tiêu sản phẩm

Hệ thống đặt sân thể thao sử dụng Python Flask.

Các nhóm nghiệp vụ chính:

### 1. USER

- Tìm sân theo loại hình thể thao và vị trí.
- Tìm sân theo địa chỉ và mở Google Maps để chỉ đường.
- Xem chi tiết sân.
- Đặt sân.
- Booking mới chỉ chọn DIRECT_BOOKING, FIND_OPPONENT hoặc FIND_PLAYERS; không dùng Singles/Doubles.
- Thanh toán tiền cọc.
- Theo dõi booking.
- Tạo / tìm / tham gia kèo chơi.
- Quản lý lịch cá nhân.

### 2. OWNER

- Đăng ký trở thành chủ sân.
- Quản lý cơ sở.
- Quản lý sân.
- Quản lý lịch sân.
- Cấu hình bảng giá theo ngày trong tuần và khung giờ.
- Quản lý bảo trì.
- Theo dõi booking.
- Theo dõi tài chính cơ bản.
- Cấu hình đích nhận chi trả ở Phase 2.6 cùng thiết kế settlement/payout.

### 3. ADMIN

- Quản trị tổng quan hệ thống.
- Duyệt chủ sân.
- Kiểm duyệt cơ sở.
- Giám sát booking.
- Giám sát kèo chơi.
- Giám sát Payment/Refund trong Booking Detail; quản lý settlement/đối soát ở Step 2.6.
- Quản lý tài khoản.
- Moderation và xử lý ngoại lệ.

### 4. PAYMENT

- Thanh toán tiền cọc bằng MoMo/ZaloPay sandbox.
- Booking tự xác nhận khi payment SUCCESS.
- Refund.
- Settlement cho Owner.
- Không dùng tiền thật trong đồ án.

---

## PHASE 1A – ADMIN FOUNDATION

**Trạng thái: HOÀN THÀNH**

Bao gồm:

- Admin permissions.
- Admin dashboard data.
- Owner application moderation foundation.
- Venue moderation foundation.
- Foundation địa chỉ venue và liên kết chỉ đường.
- Admin monitoring foundation.
- Tests.

---

## PHASE 1B – ADMIN FOUNDATION UI REDESIGN

**Trạng thái: HOÀN THÀNH**

### Mục tiêu

Hoàn thiện Admin theo phong cách SaaS Operations Dashboard.

### Step 1 – Admin Shell

**Trạng thái: HOÀN THÀNH**

- Collapsible sidebar.
- Sidebar 72px, hover khoảng 250px.
- Topbar.
- Bootstrap Icons.
- Responsive/offcanvas.
- Admin visual language.

### Step 2 – Admin Dashboard

**Trạng thái: HOÀN THÀNH**

- KPI.
- Việc cần xử lý.
- Tổng quan tài chính.
- Hierarchy.
- Responsive.

### Step 3 – Duyệt chủ sân

**Trạng thái: HOÀN THÀNH**

- Master-detail moderation workspace.
- Bộ lọc Chờ duyệt / Đã chấp thuận / Đã từ chối.
- Thông tin tài khoản.
- Thông tin đăng ký.
- Approve/reject.
- Rejection reason.
- Lịch sử xét duyệt.
- Trạng thái tài khoản.
- Ngày tạo tài khoản.

### Step 4 – Kiểm duyệt cơ sở + địa chỉ

**Trạng thái: HOÀN THÀNH**

#### Step 4.0 – Foundation địa chỉ hành chính Việt Nam

**Trạng thái: HOÀN THÀNH**

- Catalog hai cấp gồm 34 tỉnh/thành phố và 3.321 phường/xã/đặc khu.
- Venue lưu địa chỉ có cấu trúc Province/City và Ward/Commune/Special zone; giữ `district/city` để đọc dữ liệu legacy.
- Migration mới không map đoán district cũ sang ward mới và không thay đổi dữ liệu Place ID/tọa độ legacy.
- Form Owner dùng dropdown phụ thuộc; backend kiểm tra ward thuộc province.
- Tìm kiếm/hiển thị dùng `venue.full_address`, có fallback legacy.
- Luồng hiện tại không yêu cầu Google Place ID hoặc tọa độ; dữ liệu cũ được giữ. Hệ thống chỉ hỗ trợ mở Google Maps bên ngoài để xem vị trí/chỉ đường theo `full_address`, không nhúng Maps API.

Step 4.0 chỉ là foundation dữ liệu; **không đồng nghĩa Step 4 Admin UI đã hoàn thành**.

#### Step 4.1 – Kiểm duyệt cơ sở + địa chỉ (Admin UI)

**Trạng thái: HOÀN THÀNH**

- Venue list.
- Selected venue.
- Detail panel.
- Kiểm tra dữ liệu địa chỉ Province/Ward có cấu trúc; không bắt Google Place ID hoặc tọa độ.
- Liên kết chỉ đường Google Maps ngoài hệ thống theo `full_address`.
- Approve/reject/hide theo workflow hiện tại.

### Step 5 – Quản lý tài khoản

**Trạng thái: HOÀN THÀNH**

- Search/filter.
- Account detail.
- Status.
- Role.
- Guardrails.
- Audit UX.

### Step 6 – Admin consistency / responsive / UX wording

**Trạng thái: HOÀN THÀNH**

- Desktop/tablet/mobile.
- Terminology.
- Statuses.
- Visual consistency.
- Navigation continuity / scroll preservation.

---

## PHASE 1.2 – USER UI FOUNDATION + FIND VENUE

**Trạng thái: HOÀN THÀNH – ĐÃ NGHIỆM THU NGÀY 30/08/2026**

### Đã hoàn thành

- Public Find Venue foundation.
- Search theo keyword.
- Search theo Province / City.
- Dependent Ward / Commune / Special zone filter.
- Backend validation ward thuộc province.
- Search theo Sport.
- Search theo Field Type.
- Search theo min/max price.
- Pagination giữ nguyên filters.
- Chỉ hiển thị Venue ACTIVE hợp lệ.
- Starting price lấy từ FieldPriceSlot.
- Venue / Field / FieldType / PriceSlot dùng cùng source of truth giữa USER / OWNER / ADMIN.
- Owner tạo/sửa Venue bằng structured administrative address.
- Admin duyệt Venue không yêu cầu Google Place ID hoặc tọa độ.
- External "Mở Google Maps" bằng `full_address`.
- Venue Detail foundation.
- Legacy Google Place ID / latitude / longitude vẫn giữ trong schema/data nhưng không còn dùng trong flow hiện tại.
- Google Maps API / Places / Nearby đã được loại khỏi MVP.
- Tests đã được cập nhật theo scope không Maps API.

### Kết quả nghiệm thu Prompt 3.1 / Prompt 4

- Find Venue UX redesign, Venue cards UX polish và Venue Detail light visual consistency: ĐẠT.
- Visual QA desktop 1440x900: ĐẠT; form tìm kiếm, bộ lọc nâng cao, danh sách kết quả và venue cards hiển thị đúng, không tràn ngang.
- Visual QA mobile 390x844: ĐẠT; navigation thu gọn, form/bộ lọc/card responsive và không tràn ngang.
- Search theo keyword và dependent Province/Ward filter hoạt động đúng trên UI thực tế.
- Browser console không ghi nhận lỗi JavaScript trong luồng kiểm tra.
- Full regression: 258 passed, 0 failed, 0 errors, 0 skipped trong 94.05 giây.
- Final Phase 1.2 audit: ĐẠT; không mở rộng phạm vi Maps API/Places/Nearby, chỉ giữ liên kết chỉ đường ngoài hệ thống từ `full_address`.
- Phase 1.2 được chấp thuận và đóng; không bổ sung tính năng mới trong bước nghiệm thu này.

---

## PHASE 1.3 – LOCATION & MAP ENHANCEMENT

**Trạng thái: DONE / ACCEPTED (03/09/2026)**

Phase này mở rộng foundation địa chỉ đã nghiệm thu ở Phase 1.2 bằng tọa độ Venue đáng tin cậy và bản đồ nhúng Leaflet. Leaflet chỉ render/tương tác bản đồ; tile và geocoding là các dịch vụ riêng. Liên kết Google Maps ngoài hệ thống từ `full_address` tiếp tục là fallback/tiện ích độc lập.

### 1.3A – Location Data & Map Readiness Audit

**Trạng thái: DONE / ACCEPTED (02/09/2026)**

- Schema đã có `Venue.latitude`/`Venue.longitude` nullable và đủ cho MVP storage.
- Development data hiện có địa chỉ cấu trúc nhưng chưa có tọa độ được xác nhận.
- Không có Leaflet/geocoding/geolocation/nearby runtime ở baseline đã audit.

### 1.3B0 – Location & Map Architecture Decision

**Trạng thái: DONE / ACCEPTED (02/09/2026)**

- ADR-036 chốt Leaflet + OpenStreetMap-compatible tiles cho embedded map MVP.
- Workflow: address → geocode → suggested marker → Owner xác nhận/sửa → persist latitude/longitude.
- Geocoder result chỉ là gợi ý; marker được Owner xác nhận là source of truth.
- Chưa chọn geocoding provider, chưa cài dependency và chưa thay đổi runtime/database.

### 1.3B1 – Owner Coordinate Lifecycle

**Trạng thái: DONE / ACCEPTED (02/09/2026)**

- Đánh giá và tích hợp geocoding provider.
- Leaflet trong Venue create/edit.
- Suggested marker và Owner confirmation/correction.
- Coordinate validation.
- Stale-coordinate handling khi address/Province/Ward thay đổi.
- Tích hợp moderation cho toàn bộ location identity.
- Không dự kiến migration.
- Chỉ thiết lập tọa độ Venue đáng tin cậy; không gồm browser geolocation, nearby, radius, Haversine hoặc distance sorting.
- Public Nominatim được chọn cho lưu lượng student/demo thấp, chỉ gọi khi Owner bấm tìm, có cache, giới hạn nhịp, timeout và manual-marker fallback; không xem đây là hạ tầng production không giới hạn.
- Leaflet 1.9.4 dùng OSM-compatible tiles có attribution trong riêng Owner Venue create/edit; Venue Detail/Find Venue chưa có embedded map.
- Focused location/Venue tests: 52 passed; related Owner Venue tests: 51 passed; final full regression: 328 passed trong 127.17 giây.
- Final visual review: trạng thái suggestion/unconfirmed/confirmed rõ ràng; Leaflet nhất quán với Owner Console; desktop 1440×900 và mobile 390×844 được chấp thuận.
- Final acceptance checks: `git diff --check` đạt; `flask db check` không phát hiện upgrade operation mới.
- Alembic head giữ nguyên `a6d8e4f2c913`; `flask db check` không phát hiện upgrade operation mới.

### 1.3B2 – Existing Venue Coordinate Population

**Trạng thái: DONE / ACCEPTED (02/09/2026)**

- Điền tọa độ cho Venue hiện có qua application flow có kiểm soát.
- Dùng cùng nguyên tắc geocode → Owner/Admin xác nhận.
- Không cập nhật SQL trực tiếp hoặc dùng tọa độ bịa làm dữ liệu production-like.
- Coverage trước population: 16 Venue; 1 có cặp tọa độ hợp lệ, 15 thiếu tọa độ.
- Owner đã review/confirm qua Venue edit flow cho Venue 21, 22 và 23; coverage sau population là 4/16, không có partial pair, `0,0` hoặc tọa độ ngoài phạm vi.
- Venue 9 không có kết quả Nominatim phù hợp; Venue 10 có địa chỉ chưa đủ rõ; Venue 11–20 dùng địa chỉ demo `Đường Trải Nghiệm`. Cả 12 Venue được giữ unconfirmed để manual review, không đoán tọa độ.
- Address/province/ward không thay đổi. Ba Venue ACTIVE được thiết lập tọa độ đã chuyển sang PENDING đúng moderation rule; Venue chưa xác nhận giữ nguyên trạng thái.
- Focused location/Venue tests: 52 passed; `git diff --check` đạt; `flask db check` không phát hiện upgrade operation mới; Alembic current/head giữ nguyên `a6d8e4f2c913`.

### 1.3C – Venue Detail Map

**Trạng thái: DONE / ACCEPTED (02/09/2026)**

- Venue Detail public chỉ render Leaflet khi Venue có cặp latitude/longitude hợp lệ đã được Owner xác nhận; map có một marker rõ ràng tại tọa độ đáng tin cậy đó.
- Không geocode khi public page load, không dùng marker giả/mặc định, browser geolocation, nearby/radius hay thay đổi search/booking logic.
- Venue thiếu tọa độ hiển thị fallback có chủ đích bằng `full_address`; external Google Maps directions vẫn luôn sẵn sàng.
- Nếu Leaflet/tile render lỗi, address, directions và booking content vẫn hoạt động; map chỉ chuyển sang thông báo fallback.
- Dữ liệu truyền cho public template tối thiểu: latitude, longitude, tên Venue và địa chỉ cần cho marker/popup; không lộ dữ liệu Owner/Admin.
- Reuse Leaflet 1.9.4 và OSM-compatible tile setup/attribution đã chấp thuận ở 1.3B1.
- Visual review desktop cho cả trường hợp có tọa độ và không tọa độ đã đạt; responsive QA 1440×900, 1366×768, tablet và 390×844 đạt, không horizontal overflow, marker/attribution/focus vẫn sử dụng được.
- Focused public Venue/detail và location/Venue tests: 54 passed; full regression: 330 passed trong 120.04 giây.
- `git diff --check` đạt; `flask db check` không phát hiện upgrade operation mới; không có thay đổi schema/model/migration/dependency; Alembic current/head giữ nguyên `a6d8e4f2c913`.

### 1.3D – Find Venue Map

**Trạng thái: DONE / ACCEPTED (02/09/2026)**

- Leaflet chỉ render marker cho Venue có cặp tọa độ hợp lệ trong result set của trang search/filter/pagination hiện tại.
- Popup marker hiển thị tên Venue, địa chỉ và liên kết `Xem chi tiết`; không lộ dữ liệu Owner/Admin.
- Venue thiếu tọa độ vẫn giữ nguyên card trong danh sách, không có marker giả. Khi result set không có marker, trang hiển thị fallback có chủ đích thay vì map mặc định vô nghĩa.
- Giữ nguyên keyword, Province/Ward, Sport, Field Type, giá và pagination; không geocode public, không browser geolocation, nearby/radius/distance hoặc thay đổi booking/search semantics.
- Reuse Leaflet 1.9.4, OSM-compatible tile URL và attribution đã chấp thuận ở 1.3B1/1.3C.
- Visual review user đã đạt: map đúng vị trí trong layout, marker/popup/list/filter/pagination/privacy behavior đều đúng; không có marker giả cho Venue thiếu tọa độ.
- Focused Venue/location tests: 69 passed; full regression: 333 passed trong 160.59 giây.
- `git diff --check` đạt; `flask db check` không phát hiện upgrade operation mới; không có thay đổi schema/model/migration/dependency; Alembic current/head giữ nguyên `a6d8e4f2c913`.

### 1.3E – Current Location / Nearby Search

**Trạng thái: DONE / ACCEPTED (03/09/2026)**

- Browser geolocation chỉ chạy sau khi người dùng bấm `Sân gần tôi`; các trường hợp từ chối quyền, không khả dụng, timeout hoặc trình duyệt không hỗ trợ đều có thông báo tiếng Việt và không làm hỏng tìm kiếm thông thường.
- Backend xác thực latitude/longitude theo nguyên tắc cả hai hoặc không có, đúng phạm vi; khoảng cách được tính server-side bằng Haversine và sắp xếp gần nhất với tie-break ổn định.
- Nearby mode chỉ dùng Venue có cặp tọa độ hợp lệ; Venue thiếu tọa độ vẫn xuất hiện trong tìm kiếm thông thường và chỉ bị loại khi người dùng chủ động bật nearby.
- Vị trí người dùng hiển thị khác biệt với marker Venue; map tiếp tục giữ popup/link chi tiết và tự fit viewport phù hợp.
- Không lưu vị trí người dùng vào database, session, localStorage hoặc sessionStorage; không có logging tọa độ chính xác do ứng dụng bổ sung.
- Giữ nguyên keyword, Province/Ward, Sport, Field Type, giá và pagination; không thêm radius filter hoặc geospatial database extension.
- Focused Find Venue/location tests: 81 passed; full regression: 345 passed trong 131.72 giây.
- Visual review đã đạt; trạng thái nearby, khoảng cách, marker Venue và vị trí người dùng hiển thị đúng, không có horizontal overflow hoặc browser console error.
- `git diff --check`, Python/JavaScript syntax checks và `flask db check` đều đạt; không có thay đổi schema/model/migration/dependency; Alembic current/head giữ nguyên `a6d8e4f2c913`.

### 1.3F – Final QA / Acceptance

**Trạng thái: DONE / ACCEPTED (03/09/2026)**

- Functional audit toàn bộ Owner location lifecycle, dữ liệu Venue hiện có, Venue Detail map, Find Venue map và `Sân gần tôi` đạt; không phát hiện regression nghiệp vụ.
- Geocoding chỉ chạy theo thao tác Owner, kết quả chỉ là gợi ý, ghim phải được xác nhận; stale location và thay đổi tọa độ của Venue ACTIVE vẫn đưa Venue về PENDING, geocoder lỗi vẫn có manual-marker fallback.
- Public map chỉ nhận latitude/longitude hợp lệ cùng tên, địa chỉ và link chi tiết cần thiết; không geocode public, không có marker giả hoặc dữ liệu Owner/Admin bị lộ.
- Nearby chỉ kích hoạt theo thao tác user, validate cặp vị trí, tính Haversine server-side, sắp xếp gần nhất và không lưu vị trí user.
- Audit development data tại thời điểm đóng Phase: 16 Venue, 6 cặp tọa độ hợp lệ và 10 Venue thiếu cả cặp; không có partial pair, `0,0` hoặc tọa độ ngoài phạm vi. Coverage 4/16 ở 1.3B2 vẫn là snapshot nghiệm thu population ngày 02/09/2026.
- UI wording đã đổi các câu kỹ thuật như “có tọa độ” sang ngôn ngữ tự nhiên về sân/vị trí; Owner wording vẫn phân biệt rõ gợi ý, chưa xác nhận và đã xác nhận.
- Tài liệu kỹ thuật đã đồng bộ trách nhiệm: Leaflet render bản đồ, OSM-compatible tiles cung cấp tile/attribution, Nominatim geocode địa chỉ, browser geolocation lấy vị trí user và Haversine tính khoảng cách; ADR lịch sử được giữ kèm supersession rõ ràng.
- Focused Owner/Public Venue, location, map, nearby và geocoding tests: 88 passed trong 25.53 giây; full regression: 345 passed trong 146.10 giây.
- Browser QA xác nhận microcopy mới, marker Venue/vị trí user phân biệt, attribution hiển thị, không horizontal overflow, không có browser log error hoặc static-resource issue quan sát được.
- `git diff --check`, Python/JavaScript syntax checks và `flask db check` đều đạt; không thay đổi model/schema/migration/dependency; Alembic current/head giữ nguyên `a6d8e4f2c913`.

---

## THỨ TỰ THỰC HIỆN CHÍNH THỨC

Theo quyết định ngày 31/08/2026 và bổ sung Phase 1.3 ngày 02/09/2026:

> **Phase 1.2 → Phase 3 → Phase 1.3 → Phase 2 → Phase 4 → Phase 4.1 → Phase 5 → Phase 6 → Final**

- Lịch sử: Phase 2 từng được tạm hoãn để ưu tiên Owner Console và Phase 1.3
  Location & Map Enhancement.
- Sau khi các phần ưu tiên đã hoàn tất, Phase 2 đã được kích hoạt: Step 2.1 và
  2.2 accepted; Step 2.3 và 2.6 là phần implementation còn lại.

---

## PHASE 2 – ADMIN OPERATIONS

**Trạng thái: IN PROGRESS — Step 2.1 và Step 2.2 DONE / ACCEPTED**

- Step 2.1 và 2.2 đã hoàn thành trên các route canonical `/admin/bookings` và
  `/admin/bookings/<booking_code>`.
- Payment/Refund backend engines, database records và immutable history được
  giữ nguyên; Admin điều tra chúng trong Booking Detail, không qua module UI riêng.
- Step 2.3 và Step 2.6 là phần implementation còn lại của Phase 2.

### Step 2.1 – Lịch đặt sân

**Trạng thái: DONE / ACCEPTED**

- Booking Operations tại `/admin/bookings`.
- Search/filter/status, location và attention read-only.

### Step 2.2 – Chi tiết Booking

**Trạng thái: DONE / ACCEPTED**

- Booking information, financial summary, contribution breakdown và Match context.
- Payment/Refund immutable history, quan hệ Payment ↔ Refund, transaction IDs,
  attention state, historical events và current financial state.
- Không bao gồm Settlement/Payout action.

### Step 2.3 – Kèo chơi

**Trạng thái: PENDING**

- Monitoring.
- Moderation-related information.

### Step 2.4 – Dedicated Payment Operations

**Trạng thái: ĐÃ LOẠI KHỎI IMPLEMENTATION SCOPE**

- Không tạo `/admin/payments` hoặc `/admin/payments/<id>`.
- Payment engine, database records, immutable history và test coverage được giữ nguyên.
- Admin giám sát Payment qua Booking Operations và Booking Detail.

### Step 2.5 – Dedicated Refund Operations

**Trạng thái: ĐÃ LOẠI KHỎI IMPLEMENTATION SCOPE**

- Không tạo `/admin/refunds` hoặc `/admin/refunds/<id>`.
- Refund engine, database records, immutable history và test coverage được giữ nguyên.
- Admin giám sát Refund cùng Payment gốc qua Booking Detail.

### Step 2.6 – Settlement / đối soát chủ sân

**Trạng thái: PENDING**

- PENDING.
- ELIGIBLE.
- SETTLED.
- FAILED.
- ON_HOLD.
- Payout sandbox hoặc simulated payout.

---

## PHASE 3 – OWNER CONSOLE

**Trạng thái: DONE / ACCEPTED (02/09/2026)**

- Dedicated `/owner` workspace dùng sidebar/topbar riêng, không dùng navbar ngang dài như giao diện User.
- Một tài khoản `OWNER` vẫn có thể chuyển giữa Trang người chơi và Quản lý sân.
- Dropdown tài khoản Owner gồm: Trang người chơi và Đăng xuất; giao diện User của tài khoản `OWNER` có entry Quản lý sân.
- Owner sidebar target: Tổng quan → Lịch sân → Booking → Cơ sở & Sân → Bảng giá → Bảo trì → Tài chính.
- Cơ sở và Sân được gộp ở tầng UX vì Field luôn thuộc Venue; vẫn giữ nguyên route, service, domain và ownership validation riêng cho Venue/Field.
- Ảnh được quản lý theo entity Venue/Field; không có menu hoặc trang Hình ảnh riêng.

### Step 3.1 – Owner Shell + Dashboard — DONE / ACCEPTED (31/08/2026)

- `/owner` là landing page chính thức và chỉ cho phép role `OWNER`; anonymous được chuyển tới đăng nhập, `USER`/`ADMIN` nhận 403.
- Sidebar, sticky topbar, account dropdown và Bootstrap offcanvas mobile dùng chung cho toàn bộ Owner Console.
- Hỗ trợ chuyển Trang người chơi ↔ Quản lý sân trong cùng một tài khoản `OWNER`, không thay đổi role/session.
- Dashboard dùng dữ liệu thật theo ownership ở SQL: booking hôm nay, booking sắp tới, cơ sở, sân đang bật, cơ sở chờ duyệt, sân chưa bật và maintenance hiện tại/sắp tới.
- Trạng thái booking và maintenance trên dashboard tái sử dụng helper expiration/timezone hiện có; không thêm KPI tài chính.
- Tổng quan, Booking và Cơ sở & Sân có entry hoạt động; Bảng giá/Bảo trì tiếp tục dùng nested field route hiện có.
- Shared booking detail chọn đúng Owner Shell hoặc User Shell theo `owner_view`; không fork template và không thay đổi booking/payment/refund/match logic.
- Không tạo global Field/Pricing/Maintenance route, model, migration hoặc JavaScript Owner riêng.
- Browser QA đạt ở desktop 1440×900 và mobile 390×844; offcanvas, active navigation, dropdown, overflow và console JavaScript đều đạt.
- Regression: 5 test Owner Dashboard mới đạt; 142 test liên quan đạt; full suite 267 passed (baseline 262 + 5 test mới), 0 failed.
- Tại thời điểm nghiệm thu Step 3.1, Lịch sân và Tài chính chưa được triển khai trước hạn.

### Step 3.2 – Schedule & Booking Operations — DONE / ACCEPTED (31/08/2026)

- `GET /owner/schedule` là lịch vận hành chính thức theo một Venue/ngày với query `date`, `venue_id`, `view=matrix|list` và bộ lọc `field_id` tùy chọn.
- Khi chưa chọn Venue, route chuyển tới Venue đầu tiên theo thứ tự ổn định và tạo URL context rõ ràng; ownership được kiểm tra trước khi tải lịch.
- Matrix responsive dùng time × field, guide 30 phút, sticky header/time rail và cuộn nội bộ; 1–4 sân chia đều phần rộng còn lại, nhiều sân giữ tối thiểu 230px/cột và cuộn ngang trong matrix, không làm tràn trang.
- Matrix giữ sân inactive để Owner thấy đầy đủ vận hành; cả desktop/mobile dùng selector `Tất cả sân` hoặc một sân cụ thể, không pagination cột.
- List view là agenda theo ngày của Venue đã chọn, gồm cả booking và maintenance; không trùng vai trò với trang quản lý Booking.
- Booking đang giữ chỗ dùng đúng effective status hiện có; stale `CONFIRMED`, `PENDING`, `REJECTED`, `CANCELLED`, `EXPIRED` không chiếm lịch và GET không persist trạng thái. Booking/maintenance đã hoàn thành được hiển thị muted để tra cứu lịch sử.
- Booking block đi tới Owner Booking Detail; maintenance đi tới nested maintenance route hiện có. Owner hủy booking qua modal có lý do bắt buộc, lỗi inline và số tiền cọc/hoàn tiền từ dữ liệu thực; service/rule hoàn tiền hiện có không đổi.
- Read-model tải batch theo Venue, Field, Booking và Maintenance (4 query chính), filter ownership tại SQL/service và không query theo từng ô.
- Permission đạt: anonymous chuyển đăng nhập; `OWNER` được truy cập; `USER`/`ADMIN` nhận 403; dữ liệu giữa các Owner không bị lộ.
- Browser QA đạt ở 1920×1080, 1440×900, 1366×768 và 390×844; matrix 1/2/3/10 sân, sticky/internal scroll, mobile, empty day, inactive field và console JavaScript đều đạt.
- Regression: 9 test Owner Schedule mới đạt; full suite 277 passed, 0 failed.

### Step 3.3 – Venue & Field Management + Media — DONE / ACCEPTED (01/09/2026)

- Step 3.3A Venue Management, Step 3.3B Field Management và Step 3.3C Media đã hoàn tất và được nghiệm thu; Venue/Field/Media cùng nằm trong workspace Cơ sở & Sân nhưng vẫn giữ domain, ownership và route riêng.

#### Step 3.3A – Owner Venue Management — DONE / ACCEPTED (01/09/2026)

- `/owner/venues` là workspace Cơ sở & Sân trong Owner Console, chỉ liệt kê Venue thuộc `OWNER` hiện tại cùng địa chỉ cấu trúc, giờ hoạt động, moderation status và số sân thực tế.
- Có empty state, Thêm cơ sở, Chỉnh sửa và entry Xem sân theo từng Venue; chưa thay đổi hay polish Field Management.
- Create/Edit Venue dùng Owner Console shell và visual language hiện có; giữ Province/Ward validation, rule giờ mở/đóng, ownership 403 và Admin moderation workflow.
- Query read-model chỉ bổ sung số sân theo Venue; không tạo model/migration và không thay đổi booking, pricing, maintenance, payment hoặc match logic.
- Browser QA đạt cho 0/1/2/3/nhiều Venue ở desktop 1440×900 và mobile 390×844; grid 1 Venue tối đa 560px, 2 Venue tối đa 1100px, từ 3 Venue giữ card width hiện có; không page-level horizontal overflow.
- Regression: focused Venue tests 41 passed; full suite 282 passed, 0 failed.

#### Step 3.3B – Owner Field Management — DONE / ACCEPTED (01/09/2026)

- Danh sách sân theo Venue đã được tích hợp vào workspace Cơ sở & Sân trong Owner Console, gồm empty state, loại sân/môn thể thao, sức chứa, mặt sân, trạng thái và các entry Chỉnh sửa/Bảng giá/Bảo trì.
- Create/Edit Field dùng Owner Console shell và visual language đã nghiệm thu; tái sử dụng `FieldForm`, route/service/domain hiện có và giữ Field mới mặc định chưa hoạt động.
- Ownership được kiểm tra ở cả Venue và quan hệ Field–Venue; `USER`/`ADMIN`, Owner khác và cặp `venue_id`/`field_id` không khớp không được truy cập hoặc làm lộ dữ liệu.
- Không thay đổi model/migration hay booking, pricing, maintenance, payment, refund và matchmaking rules; quan hệ Pricing/Maintenance được giữ nguyên khi sửa Field.
- Browser QA đạt cho Venue có 0/1/2/nhiều Field ở desktop 1440×900 và mobile 390×844; không page-level horizontal overflow.
- Regression: focused Field/Pricing/Maintenance tests 39 passed; full suite 287 passed, 0 failed.

#### Step 3.3C – Venue & Field Media — DONE / ACCEPTED (01/09/2026)

- Owner quản lý ảnh đại diện và gallery cho Venue/Field ngay trong form chỉnh sửa tương ứng; card thông tin và Media Manager độc lập, upload form không lồng vào form cập nhật entity.
- File được lưu dưới `MEDIA_ROOT`, database chỉ giữ metadata/path; upload kiểm tra JPG/PNG/WebP, kích thước tối đa 5 MB, nội dung thực, tên file an toàn và filename duy nhất.
- Cover duy nhất được bảo vệ bằng filtered unique index cho Venue/Field; xóa cover chọn fallback ổn định, thiếu file vật lý trả 404 và rollback DB không làm mất hoặc bỏ sót file ngoài kiểm soát.
- Ownership được kiểm tra server-side cho mọi upload/set-cover/delete; nested Venue–Field scope, media không công khai và đường dẫn filesystem đều không thể bị truy cập chéo.
- Storage/security audit: PASS trên SQL Server migration head `a6d8e4f2c913`.
- Browser QA đạt cho Venue/Field có 0/1/nhiều ảnh ở desktop 1440×900 và mobile 390×844; gallery responsive, không page-level horizontal overflow, upload/set-cover/delete hoạt động và console sạch.
- Regression: focused Media/Venue/Field tests 64 passed; full suite 296 passed, 0 failed.

### Step 3.4 – Pricing & Maintenance Operations — DONE / ACCEPTED (01/09/2026)

- Owner quản lý Bảng giá và Bảo trì theo đúng nested context Venue → Field trong Owner Console; list/form, trạng thái, thao tác, empty state và responsive UI dùng cùng visual language đã nghiệm thu ở Step 3.3.
- Pricing tiếp tục tái sử dụng `FieldPriceSlot`, form, route và service hiện có; khung giá phải có `start_time < end_time`, nằm trong giờ hoạt động của Venue và các slot `ACTIVE` cùng Field/ngày không được chồng nhau. Không tự sửa hoặc tắt slot khác để giải quyết overlap và không thay đổi cách tính giá booking.
- Field mới vẫn mặc định `INACTIVE`; chỉ được bật khi có ít nhất một price slot `ACTIVE`. Khi tạm ngưng price slot `ACTIVE` cuối cùng, Field tự trở về `INACTIVE`; việc sửa một slot `INACTIVE` không tự bật lại slot hoặc Field.
- Maintenance tiếp tục dùng model/form/service create/cancel hiện có; thời gian phải chưa kết thúc, có `start_time < end_time`, nằm trong giờ hoạt động của Venue và không chồng maintenance `ACTIVE` khác. Source hiện không có edit capability nên Step 3.4 không tự tạo route/service sửa Maintenance mới.
- Danh sách Maintenance phân biệt hiện tại/sắp tới với lịch sử; trạng thái `ACTIVE` đã kết thúc được hiển thị hiệu lực là `COMPLETED`, còn `CANCELLED` không khóa lịch. Owner Schedule tiếp tục hiển thị maintenance theo cùng source of truth.
- Xung đột booking–maintenance giữ effective occupancy hiện có: `CONFIRMED` còn hạn, `PARTIALLY_PAID`, `PAID` và `REFUND_PENDING` chặn maintenance; hold `CONFIRMED` đã hết hạn cùng `REJECTED`, `CANCELLED`, `EXPIRED` không chặn sai. Maintenance `ACTIVE` tạo thành công tiếp tục chặn booking mới trong khoảng giao nhau.
- Ownership và nested IDs được kiểm tra server-side: `USER`/`ADMIN` không có quyền Owner; Owner khác nhận 403; Venue/Field/PriceSlot/Maintenance ID không khớp nhận 404 và không lộ dữ liệu.
- Browser QA đạt ở desktop 1440×900 và mobile 390×844 cho Pricing populated/empty, create/edit, Field activation/deactivation, Maintenance populated/empty, create/cancel và Owner Schedule; không page-level horizontal overflow, browser console sạch.
- Regression: focused Pricing/Maintenance 38 passed; related Pricing/Maintenance/Booking/Owner Schedule/Dashboard/Field 111 passed; full suite 312 passed, 0 failed.
- Không tạo model/migration mới; không thay đổi payment, refund, matchmaking, Media hoặc Finance.

### Step 3.5 – Owner Finance Foundation — DONE / ACCEPTED (02/09/2026)

- Owner Finance là read-model theo phạm vi Owner → Venue → Field, dùng Booking, Payment và Refund làm source of truth.
- Khách thanh toán online tiền cọc booking bắt buộc 30% qua MoMo/MOCK; phần còn lại thanh toán trực tiếp tại sân.
- Dashboard có KPI, lọc theo cơ sở/sân, lịch sử thanh toán/hoàn tiền và wording tiếng Việt nghiệp vụ.
- KPI “Giá trị booking đã giữ sân” là tổng giá trị booking đã giữ sân/hoàn thành, không phải tiền cọc hoặc doanh thu thực nhận.
- KPI “Dự kiến thanh toán tại sân” chỉ phản ánh phần thanh toán trực tiếp dự kiến của booking còn hiệu lực; không suy diễn khoản đã thu sau khi booking hoàn thành.
- Giữ trạng thái thông tin “Chưa có dữ liệu đối soát”. Không có settlement/payout engine, tài khoản nhận tiền Owner hoặc trạng thái chi trả giả trong Step 3.5.
- Settlement/payout và cấu hình đích nhận chi trả được hoãn sang Phase 2.6 cùng thiết kế đối soát.
- Verification: Finance-focused 5 passed; Payment/Refund/Booking 73 passed; full regression 317 passed; migration head `a6d8e4f2c913`; `flask db check` sạch.

### Step 3.6 – Owner Console Final Polish & Audit — DONE / ACCEPTED (02/09/2026)

- Final visual review đạt cho toàn bộ Owner Console, gồm Owner Schedule Matrix: hierarchy giờ tròn/nửa giờ, header sân, event Booking xanh, event Bảo trì amber, lịch sử muted, legend compact, trạng thái trống “Trống” và chỉ báo “Bây giờ” trong ngày/giờ hoạt động.
- Responsive/browser QA đạt ở desktop 1440×900, 1366×768, tablet và mobile 390×844; matrix giữ vị trí, sticky rail/header, internal scroll và semantics hiện có.
- Permission/ownership audit đạt; không thay đổi route, ownership validation, query, filter, Matrix/List switch hoặc booking/maintenance rules.
- Focused Owner audit: 166 passed. Schedule-focused: 14 passed. Final full regression: 317 passed, 0 failed.
- `compileall` đạt; `flask db check` không phát hiện upgrade operation; migration current/head giữ `a6d8e4f2c913`.
- Không có thay đổi model, schema, migration hoặc dependency. Final visual review: PASSED.

---

## PHASE 4 – MATCH BUSINESS LOGIC

**Trạng thái: CHƯA NGHIỆM THU THEO ROADMAP**

- Source hiện đã có một phần đáng kể Match/booking-related business logic.
- Quyết định MVP hiện tại: booking mới không dùng `play_format`; FIND_PLAYERS giới hạn theo `field.capacity`, cột cũ chỉ giữ cho legacy.
- Chưa thực hiện Phase 4 audit riêng theo roadmap.
- Chỉ mark DONE sau khi audit source, business rules, tests và UI flow.

---

## PHASE 4.1 – USER EXPERIENCE REDESIGN

**Trạng thái: CHƯA LÀM**

- Find Venue.
- Venue Detail.
- Booking flow.
- My Bookings.
- Find Match.
- My Matches.
- My Schedule.
- Match Detail.
- Booking Detail.

---

## PHASE 5 – ADMIN ADVANCED

**Trạng thái: CHƯA LÀM**

### Account / Role

- USER → OWNER chỉ qua Owner Application.
- OWNER → USER cần lý do + audit.
- ADMIN promotion cần xác nhận đặc biệt.
- Admin không tự demote tài khoản đang đăng nhập.
- Log actor/time/reason/old/new values.

### Match Moderation

- Admin xem.
- Search/filter.
- Hide/close bài vi phạm.
- Không tùy tiện sửa nội dung hoặc participant.

---

## PHASE 6 – TEST / POLISH / DEMO

**Trạng thái: CHƯA LÀM**

- Full pytest.
- Responsive.
- Permissions.
- Booking E2E.
- Payment/refund/settlement E2E.
- Kiểm tra external Google Maps directions link.
- Xác minh app không tải Maps JavaScript API / Places API và không yêu cầu API key.
- Owner flow.
- Match flow.
- Demo data.
- UI consistency.
- Demo preparation.

---

## FINAL – SUBMISSION CLEANUP

Chỉ làm sau khi toàn bộ nghiệp vụ ổn định.

- Freeze version.
- Tạo backup/tag.
- Audit-only repo.
- Tìm dead code.
- Tìm file dư.
- Tìm duplication.
- Review trước khi xóa.
- Cleanup có kiểm soát.
- Cập nhật README.
- Cập nhật docs.
- Kiểm tra `.env` / secrets.
- Requirements.
- Migrations.
- Full tests.
- Tạo submission version.

---

## CURRENT POSITION

Hiện tại:

- Phase 1A: DONE.
- Phase 1B: DONE.
- Phase 1.2: DONE / ACCEPTED (30/08/2026).
- Phase 1.3: DONE / ACCEPTED (03/09/2026); 1.3A đến 1.3F đều đã nghiệm thu.
- Phase 2: IN PROGRESS — Step 2.1 và 2.2 DONE / ACCEPTED; Step 2.3 và 2.6 PENDING.
- Phase 3: DONE / ACCEPTED (02/09/2026).
- Phase 4: NOT YET AUDITED / ACCEPTED.
- Phase 4.1: NOT STARTED.
- Phase 5: NOT STARTED.
- Phase 6: NOT STARTED.

Thứ tự thực hiện hiện hành:

> **Phase 1.2 → Phase 3 → Phase 1.3 → Phase 2 → Phase 4 → Phase 4.1 → Phase 5 → Phase 6 → Final**

Lý do: Owner Console và Location & Map Enhancement đã hoàn tất; Phase 2 tiếp tục
với Match Operations (Step 2.3), Settlement/Payout (Step 2.6), sau đó là review
consistency/regression cuối. Step 2.4 và 2.5 được giữ số lịch sử nhưng không có
dedicated Admin UI.

### Phase 1B

- Step 1: DONE.
- Step 2: DONE.
- Step 3: DONE.
- Step 4.0: DONE.
- Step 4.1: DONE.
- Step 5: DONE.
- Step 6: DONE.

### Phase 1.2 progress

DONE:

- Structured location search.
- Province/Ward.
- Sport.
- Field Type.
- Price.
- Pagination.
- External Google Maps directions.
- Remove Maps API / Places / Nearby.
- USER/OWNER/ADMIN Venue data consistency foundation.
- Prompt 3.1 – Find Venue UX redesign.
- Visual QA desktop 1440x900 và mobile 390x844.
- Full regression: 258 passed.
- Prompt 4 – Final audit / acceptance / roadmap close.

### TASK TIẾP THEO

**PHASE 2 – ADMIN OPERATIONS — IN PROGRESS**

Step 2.1 Booking Operations và Step 2.2 Booking Detail đã DONE / ACCEPTED.
Payment/Refund tiếp tục được bảo toàn là engine và immutable history, được Admin
giám sát trong Booking Detail thay vì dedicated screen. Phần còn lại là Step 2.3
Match Operations, Step 2.6 Settlement/Payout và review consistency/regression
cuối; không có Step 2.7.

---

## NGUYÊN TẮC SỬ DỤNG ROADMAP

Trước mỗi task:

1. Đọc `AGENTS.md`.
2. Đọc `docs/11-roadmap.md`.
3. Xác định Phase/Step hiện tại.
4. Chỉ sửa file thuộc scope task.
5. Không tự làm trước các Phase tương lai.
6. Trạng thái roadmap phải phản ánh mức nghiệm thu, không chỉ sự tồn tại của code.

Sau khi một Step hoàn tất và đã được người dùng chấp thuận:

- Cập nhật trạng thái trong `docs/11-roadmap.md`.
- Chỉ cập nhật khi prompt yêu cầu cập nhật roadmap.

Cuối task báo:

- Phase / Step đang thực hiện.
- Files changed.
- Business logic changed hay không.
- Test result.
- Có thay đổi ngoài scope không.
