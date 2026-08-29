# ROADMAP – SPORTS FIELD BOOKING SYSTEM

## Mục tiêu sản phẩm

Hệ thống đặt sân thể thao sử dụng Python Flask.

Các nhóm nghiệp vụ chính:

### 1. USER

- Tìm sân theo loại hình thể thao và vị trí.
- Tìm sân theo địa chỉ và mở Google Maps để chỉ đường.
- Xem chi tiết sân.
- Đặt sân.
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
- Khai báo tài khoản nhận tiền.

### 3. ADMIN

- Quản trị tổng quan hệ thống.
- Duyệt chủ sân.
- Kiểm duyệt cơ sở.
- Giám sát booking.
- Giám sát kèo chơi.
- Quản lý payment / refund / settlement.
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

**Trạng thái: ĐANG THỰC HIỆN**

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

### Đang thực hiện

- Find Venue UX redesign.
- Venue cards UX polish.
- Responsive desktop/mobile.
- Venue Detail light visual consistency.

### Còn lại trước khi đóng Phase 1.2

- Prompt 3.1 – Find Venue UX redesign.
- Visual QA desktop 1440x900.
- Visual QA mobile 390x844.
- Full regression tests.
- Final Phase 1.2 audit.
- Roadmap close / acceptance review.

---

## PHASE 2 – ADMIN OPERATIONS

**Trạng thái: CHƯA LÀM**

### Step 2.1 – Lịch đặt sân

- Admin monitoring toàn hệ thống.
- Search/filter/status.

### Step 2.2 – Chi tiết Booking

- Booking info.
- Payment.
- Refund.
- Settlement.
- Timeline.
- Audit.

### Step 2.3 – Kèo chơi

- Monitoring.
- Moderation-related information.

### Step 2.4 – Thanh toán

- Payment transactions.
- Gateway.
- Status.
- Failures.

### Step 2.5 – Hoàn tiền

- Refund queue.
- Refund detail.
- Reason.
- Status.

### Step 2.6 – Settlement / đối soát chủ sân

- PENDING.
- ELIGIBLE.
- SETTLED.
- FAILED.
- ON_HOLD.
- Payout sandbox hoặc simulated payout.

### Step 2.7 – Admin Operations polish

- Responsive.
- Consistency.
- UX wording.

---

## PHASE 3 – OWNER CONSOLE

**Trạng thái: CHƯA LÀM**

- Dedicated `/owner` workspace.
- Owner Shell.
- Owner Dashboard.

### Lịch sân

- Primary = time × field matrix.
- Secondary = list view.

### Quản lý

- Cơ sở.
- Sân.
- Bảng giá.
- Bảo trì.

### Bảng giá

- Theo khung giờ.
- Theo ngày trong tuần.

### Bảo trì

- Date.
- Start time.
- End time.
- Reason.
- Không cho tạo nếu xung đột booking chưa xử lý.

### Tài chính

- Tiền cọc.
- Khoản chờ quyết toán.
- Khoản đã quyết toán.
- Tài khoản nhận tiền.
- Không làm accounting phức tạp.

---

## PHASE 4 – MATCH BUSINESS LOGIC

**Trạng thái: CHƯA NGHIỆM THU THEO ROADMAP**

- Source hiện đã có một phần đáng kể Match/booking-related business logic.
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
- Phase 1.2: IN PROGRESS.
- Phase 2: NOT STARTED.
- Phase 3: NOT STARTED.
- Phase 4: NOT YET AUDITED / ACCEPTED.
- Phase 4.1: NOT STARTED.
- Phase 5: NOT STARTED.
- Phase 6: NOT STARTED.

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

CURRENT:

- Prompt 3.1 – Find Venue UX redesign.

NEXT:

- Prompt 4 – Phase 1.2 final audit / tests / acceptance / roadmap close.

### TASK TIẾP THEO

**PHASE 1.2 – PROMPT 3.1: FIND VENUE UX REDESIGN**

Sau khi Prompt 3.1 được người dùng chấp thuận:

**PHASE 1.2 – PROMPT 4: FINAL AUDIT + CLOSE PHASE**

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
