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
- Venue lưu `province_code/province_name/ward_code/ward_name`; giữ `district/city` để đọc dữ liệu legacy.
- Migration mới không map đoán district cũ sang ward mới và không thay đổi dữ liệu Place ID/tọa độ legacy.
- Form Owner dùng dropdown phụ thuộc; backend kiểm tra ward thuộc province.
- Tìm kiếm/hiển thị dùng `venue.full_address`, có fallback legacy.
- Luồng hiện tại không yêu cầu Place ID/tọa độ; dữ liệu cũ được giữ và liên kết Google Maps chỉ dùng để mở chỉ đường.

Step 4.0 chỉ là foundation dữ liệu; **không đồng nghĩa Step 4 Admin UI đã hoàn thành**.

#### Step 4.1 – Kiểm duyệt cơ sở + địa chỉ (Admin UI)

**Trạng thái: HOÀN THÀNH**

- Venue list.
- Selected venue.
- Detail panel.
- Liên kết chỉ đường Google Maps ngoài hệ thống.
- Kiểm tra dữ liệu địa chỉ.
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

**Trạng thái: CHƯA LÀM**

- User UI foundation.
- Find Venue.
- Địa chỉ hành chính và liên kết chỉ đường Google Maps.
- Venue cards.
- Distance.
- Sport / field type filters.
- Venue detail.

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

**Trạng thái: CHƯA LÀM**

- Tạo kèo.
- Join match.

### Creator chọn

- AUTO ACCEPT nếu còn chỗ.
- Hoặc MANUAL APPROVAL.

### Participant

- Được rút tự do trước khi match bắt đầu.

### Creator

- Có thể Đóng tuyển người.
- Participant hiện tại vẫn giữ nguyên.
- Booking không thay đổi.

### Chia tiền

- Hệ thống tính số tiền dự kiến/người.
- Creator trả tiền cọc online.
- Phần còn lại chia và thanh toán trực tiếp tại sân.
- Không thu online từng participant.

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
- Kiểm tra liên kết chỉ đường Google Maps và không tải Maps/Places API.
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

### Phase 1B

- Step 1: DONE.
- Step 2: DONE.
- Step 3: DONE.
- Step 4.0: DONE.
- Step 4.1: DONE.
- Step 5: DONE.
- Step 6: DONE.

### TASK TIẾP THEO

**PHASE 1.2 – USER UI FOUNDATION + FIND VENUE: NEXT.**

Phase 1.2 chưa được triển khai trong task này.

---

## NGUYÊN TẮC SỬ DỤNG ROADMAP

Trước mỗi task:

1. Đọc `AGENTS.md`.
2. Đọc `docs/11-roadmap.md`.
3. Xác định Phase/Step hiện tại.
4. Chỉ sửa file thuộc scope task.
5. Không tự làm trước các Phase tương lai.

Sau khi một Step hoàn tất và đã được người dùng chấp thuận:

- Cập nhật trạng thái trong `docs/11-roadmap.md`.
- Chỉ cập nhật khi prompt yêu cầu cập nhật roadmap.

Cuối task báo:

- Phase / Step đang thực hiện.
- Files changed.
- Business logic changed hay không.
- Test result.
- Có thay đổi ngoài scope không.
