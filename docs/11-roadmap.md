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

## THỨ TỰ THỰC HIỆN CHÍNH THỨC

Theo quyết định của người dùng ngày 31/08/2026:

> **Phase 1.2 → Phase 3 → Phase 2 → Phase 4 → Phase 4.1 → Phase 5 → Phase 6 → Final**

- Phase 2 không bị loại khỏi roadmap; Phase này chỉ được tạm hoãn để ưu tiên hoàn thiện giao diện và nghiệp vụ Owner Console trước.
- Sau Phase 3, dự án quay lại Phase 2 – Admin Operations rồi tiếp tục theo thứ tự trên.

---

## PHASE 2 – ADMIN OPERATIONS

**Trạng thái: NOT STARTED – DEFERRED BY USER DECISION**

- Phase 2 vẫn giữ nguyên phạm vi và không bị bỏ.
- Admin Operations được chủ động tạm hoãn vì Owner Console được ưu tiên thực hiện trước.
- Actual payment, refund và settlement/payout engine vẫn được hoàn thiện tại Step 2.4–2.6 sau khi Phase 3 kết thúc.

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

**Trạng thái: NEXT / IN PROGRESS**

- Dedicated `/owner` workspace dùng sidebar/topbar riêng, không dùng navbar ngang dài như giao diện User.
- Một tài khoản `OWNER` vẫn có thể chuyển giữa Trang người chơi và Quản lý sân.
- Dropdown tài khoản Owner gồm: Trang người chơi, Quản lý sân, Hồ sơ và Đăng xuất.

### Step 3.1 – Owner Shell + Dashboard — NEXT

- Sidebar/topbar riêng cho Owner Console.
- Hỗ trợ chuyển User ↔ Owner trong cùng một tài khoản `OWNER`.
- Dashboard tổng quan cho chủ sân.

### Step 3.2 – Lịch sân — NOT STARTED

- Primary view = time × field matrix.
- Secondary view = list view.

### Step 3.3 – Quản lý cơ sở — NOT STARTED

- Tạo và sửa cơ sở.
- Xem trạng thái duyệt venue.

### Step 3.4 – Quản lý sân — NOT STARTED

- Field type.
- Capacity.
- Trạng thái sân.

### Step 3.5 – Ảnh cơ sở & ảnh sân — NOT STARTED

- Upload ảnh.
- Chọn ảnh đại diện.
- Quản lý gallery.

### Step 3.6 – Bảng giá — NOT STARTED

- Giá theo ngày trong tuần.
- Giá theo khung giờ.

### Step 3.7 – Bảo trì — NOT STARTED

- Tạo lịch bảo trì.
- Kiểm tra conflict với booking trước khi lưu.

### Step 3.8 – Booking Owner — NOT STARTED

- Theo dõi booking của các sân thuộc Owner.

### Step 3.9 – Owner Finance Foundation — NOT STARTED

- Hiển thị tiền cọc.
- Hiển thị khoản chờ đối soát và khoản đã đối soát.
- Quản lý thông tin tài khoản nhận tiền.
- Phase này chỉ chuẩn bị giao diện và dữ liệu Owner cần nhìn thấy; không triển khai sâu actual settlement/payout.
- Actual payment, refund và settlement/payout engine được giữ lại cho Phase 2.4 – Thanh toán, Phase 2.5 – Hoàn tiền và Phase 2.6 – Settlement / đối soát chủ sân.

### Step 3.10 – Owner Console Polish — NOT STARTED

- Responsive.
- Consistency.
- UX wording.
- Final audit.

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
- Phase 2: NOT STARTED / DEFERRED BY USER DECISION.
- Phase 3: NEXT / IN PROGRESS.
- Phase 4: NOT YET AUDITED / ACCEPTED.
- Phase 4.1: NOT STARTED.
- Phase 5: NOT STARTED.
- Phase 6: NOT STARTED.

Thứ tự thực hiện hiện hành:

> **Phase 1.2 → Phase 3 → Phase 2 → Phase 4 → Phase 4.1 → Phase 5 → Phase 6 → Final**

Lý do: Owner Console được chủ động ưu tiên trước Admin Operations theo quyết định của người dùng.

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

**PHASE 3 – STEP 3.1 OWNER SHELL + DASHBOARD**

Phase 1.2 đã đóng. Phase 2 được tạm hoãn và Phase 3 là Phase tiếp theo. Task cập nhật roadmap này không triển khai Step 3.1 hoặc bất kỳ mã nguồn nào.

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
