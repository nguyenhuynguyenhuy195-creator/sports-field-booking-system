# BÁO CÁO AUDIT TOÀN BỘ GIAO DIỆN

**Ngày audit:** 08/09/2026
**Phạm vi:** giao diện công khai, Người dùng, Chủ sân và Quản trị viên của MVP thanh toán mô phỏng
**Kết luận ban đầu:** **READY WITH MINOR UI ISSUES**

## 1. Nguyên tắc và phạm vi

Audit này là kiểm tra chỉ đọc. Không thay đổi route, model, schema, quy tắc nghiệp vụ, luồng thanh toán hoặc mã giao diện. Các thay đổi đang có sẵn trong working tree trước audit được giữ nguyên.

Phạm vi thanh toán được đánh giá theo quyết định hiện hành: hệ thống sử dụng thanh toán mô phỏng trong môi trường thử nghiệm; MoMo Sandbox đã tắt và không phải runtime provider của MVP. Không ghi nhận lỗi giao diện MoMo-only là blocker.

Đã kiểm tra:

- 43 Jinja template, 3 file CSS và 17 file JavaScript;
- 33 mẫu route/trạng thái hiển thị thực tế thuộc bốn nhóm vai trò;
- desktop 1280×720, mobile 390×844 và tablet 768×1024;
- điều hướng, sidebar, biểu mẫu, trạng thái rỗng/danh sách/chi tiết, ảnh, bản đồ, nhãn điều khiển, heading, tràn ngang, chữ nhỏ và tương phản màu;
- luồng đặt sân đến bước xác nhận, gồm chọn giờ và báo giá 120.000₫, nhưng không gửi yêu cầu tạo booking;
- giao diện Owner và Admin bằng phiên đăng nhập cục bộ chỉ phục vụ audit, không thay đổi dữ liệu.

Không thực hiện pentest, kiểm thử với screen reader thật, ma trận mọi trình duyệt/hệ điều hành hoặc đo hiệu năng mạng diện rộng. Vì vậy báo cáo không tuyên bố đạt chứng nhận WCAG đầy đủ.

## Cập nhật khắc phục ngày 09/09/2026

| Issue | Before | After | Xác minh |
|---|---|---|---|
| UI-01 | Metadata Owner/Admin có thể nhỏ 9–11 px và một số màu dưới 4,5:1. | Thêm readability floor 13 px cho metadata, bảng, label và control của hai console; màu muted được làm đậm. | Quét 7 route Owner và 7 route Admin: không có metadata dưới 12 px, không có text thường dưới 4,5:1 trong các mẫu đã render. |
| UI-02 | Input ảnh chỉ có `aria-describedby`. | Thêm label ẩn trực quan “Chọn ảnh tải lên”, liên kết bằng `for` với ID WTForms. | Browser tìm được một input bằng label; regression test render route Owner pass. |
| UI-03 | Textarea từ chối chỉ có placeholder/help text. | Thêm label hiển thị “Lý do từ chối”, liên kết bằng `for` với ID có prefix hồ sơ. Placeholder, help text, required và maxlength không đổi. | Browser tìm được 3 textarea bằng label trên danh sách hồ sơ; regression test pass. |
| UI-04 | Link “Đăng ký ngay” màu `#146c43`, khoảng 4,30:1 trên nền sáng. | Thêm class riêng, màu `#0f5736`, underline, hover đậm hơn và focus ring 3 px. | Tab keyboard hiển thị outline 3 px; không tràn ngang tại ba viewport. |
| UI-05 | Nghi ngờ tile/CDN tải dở. | Không thay đổi theo yêu cầu. | Không tái hiện: 8/8 tile đã tải, không có tile lỗi hay warn/error console. Giữ như technical debt, không là blocker. |

**Kết luận sau khắc phục:** **READY.** UI-01 đến UI-04 đã được sửa mà không thay đổi route, model, database, business rule hoặc luồng MOCK. UI-05 chưa có bằng chứng tái hiện trong môi trường audit.

## 2. Ma trận màn hình đã kiểm tra trực tiếp

| Khu vực | Màn hình/luồng tiêu biểu | Kết quả chính |
|---|---|---|
| Công khai | Trang chủ, đăng nhập, danh sách sân | Bố cục rõ, điều hướng hoạt động, không tràn ngang |
| Người dùng | Chi tiết sân, tìm trận, chi tiết trận, trận của tôi, booking của tôi, chi tiết booking, đăng ký Chủ sân | Không thấy ảnh hỏng ngoài tile bản đồ; trạng thái và CTA rõ |
| Đặt sân | Chọn sân → chọn ngày/giờ → báo giá → bước xác nhận | JavaScript và cập nhật giá hoạt động; không tạo dữ liệu trong audit |
| Chủ sân | Dashboard, lịch sân, booking, tài chính, cơ sở, tạo/sửa cơ sở, sân con, bảng giá, bảo trì, thư viện ảnh | Responsive ổn; phát hiện chữ phụ nhỏ và input ảnh thiếu tên truy cập |
| Quản trị | Dashboard, duyệt Chủ sân, cơ sở, booking/chi tiết, trận/chi tiết, tài khoản, giám sát | Sidebar mobile hoạt động; phát hiện chữ phụ tương phản thấp và textarea thiếu label |

## 3. Issue được phát hiện trước khi khắc phục

### UI-01 — Chữ phụ quá nhỏ và tương phản thấp ở Owner/Admin

**Mức độ:** Medium
**Loại:** Accessibility/readability
**Trạng thái:** CONFIRMED

Một số metadata được hiển thị ở khoảng 9,28–10,88 px và dùng màu xám nhạt. Mẫu đo trực tiếp cho thấy:

- nhãn `Owner Console`: tỷ lệ tương phản khoảng 3,34:1 ở 9,76 px;
- kích thước file ảnh: khoảng 3,25:1 ở 9,28 px;
- ID hồ sơ Admin: khoảng 2,30–2,50:1 ở 10,88 px;
- ngày và metadata Admin: khoảng 3,45–3,75:1 ở 10,88 px;
- một số link lọc/nút phụ Admin: khoảng 4,28–4,41:1 ở cỡ 11–12 px.

Các giá trị liên quan nằm tại `app/static/css/owner.css:305-308`, `app/static/css/owner.css:1973-1977`, `app/static/css/admin.css:1809-1815` và các block metadata tương tự. Chữ thường cỡ nhỏ cần đạt tối thiểu 4,5:1 theo tiêu chí WCAG 1.4.3; đồng thời cỡ dưới 11 px gây khó đọc trên màn hình mật độ cao.

**Khuyến nghị:** tăng metadata lên tối thiểu 12 px, ưu tiên 13 px; dùng màu xám đậm hơn và kiểm lại tương phản sau khi sửa. Có thể sửa tập trung ở token/selector metadata, không cần redesign.

### UI-02 — Input tải ảnh chưa có accessible name

**Mức độ:** Medium
**Loại:** Form accessibility
**Trạng thái:** CONFIRMED

`app/templates/owner/_media_manager.html:23` render input file và chỉ gắn `aria-describedby`; không render `label` hoặc `aria-label`. Trình duyệt không có tên mô tả ổn định cho điều khiển này.

**Ảnh hưởng:** người dùng screen reader khó biết đây là trường chọn ảnh cơ sở/sân.
**Khuyến nghị:** render `media_upload_form.image.label` hoặc gắn một `<label for="...">Chọn ảnh tải lên</label>`. Giữ nguyên validation và luồng upload hiện tại.

### UI-03 — Lý do từ chối hồ sơ Chủ sân dùng placeholder thay cho label

**Mức độ:** Medium
**Loại:** Form accessibility/usability
**Trạng thái:** CONFIRMED

Textarea tại `app/templates/admin/owner_applications.html:180` có placeholder và help text nhưng không có label/`aria-label`. Placeholder biến mất sau khi nhập và không thay thế được nhãn trường.

**Ảnh hưởng:** tên trường không rõ với công nghệ hỗ trợ; Admin có thể khó đối chiếu dữ liệu khi đã nhập nội dung dài.
**Khuyến nghị:** thêm label hiển thị “Lý do từ chối” liên kết bằng `for/id`; tiếp tục giữ help text và giới hạn 500 ký tự.

### UI-04 — Link đăng ký ở trang đăng nhập thiếu nhẹ tương phản

**Mức độ:** Low
**Loại:** Accessibility
**Trạng thái:** CONFIRMED

Link “Đăng ký ngay” tại `app/templates/auth/login.html:29` kế thừa màu xanh link toàn cục. Mẫu đo trực tiếp cho tỷ lệ khoảng 4,30:1 trên nền `#f8f9fa` ở 15 px, thấp hơn ngưỡng 4,5:1 cho chữ thường.

**Khuyến nghị:** dùng sắc xanh đậm hơn cho link trên nền sáng và giữ trạng thái hover/focus nhìn thấy rõ.

### UI-05 — Bản đồ phụ thuộc CDN/tile bên ngoài

**Mức độ:** Low
**Loại:** Resilience/technical debt
**Trạng thái:** NEEDS VERIFICATION

Leaflet CSS/JS được tải từ `unpkg.com` trong các template danh sách sân, chi tiết sân và form cơ sở; tile mặc định tải từ OpenStreetMap qua `MAP_TILE_URL`. Trong một số lần tải audit, tile có trạng thái tải chưa hoàn tất nhưng marker và phần còn lại của trang vẫn hiển thị, không có lỗi console tái hiện ổn định.

**Ảnh hưởng:** khi mạng/CDN chậm, vùng bản đồ có thể trống hoặc tải dở; danh sách và địa chỉ chữ vẫn dùng được.
**Khuyến nghị:** hiển thị thông báo fallback trong vùng bản đồ khi Leaflet/tile thất bại. Không cần thay provider trong phạm vi MVP.

## 4. Các điểm đã đạt

- Không phát hiện document-level horizontal overflow ở các màn hình đã kiểm tra trên desktop, mobile hoặc tablet.
- Thanh ngày ở form đặt sân có cuộn ngang nội bộ trên màn hình hẹp; đây là hành vi chủ đích và không làm tràn toàn trang.
- Luồng chọn khung giờ, cập nhật báo giá và chuyển bước xác nhận hoạt động đúng trong phiên kiểm tra.
- Sidebar Owner/Admin trên mobile mở/đóng được, có tên nút và lớp overlay phù hợp.
- Heading chính, CTA, trạng thái nghiệp vụ và bố cục danh sách/chi tiết nhìn chung rõ ràng.
- Không phát hiện ảnh nội dung hỏng; ngoại lệ duy nhất là rủi ro tile bản đồ bên ngoài nêu tại UI-05.
- Các template bản đồ dùng Subresource Integrity cho Leaflet CDN.
- CSS có xử lý `prefers-reduced-motion`; các tương tác chính không bắt buộc animation để hoàn thành tác vụ.
- Không phát hiện endpoint literal hoặc asset nội bộ bị thiếu trong kiểm kê source.
- Luồng MOCK không bị endpoint/code MoMo đã tắt làm thay đổi giao diện hoặc cản trở thao tác được kiểm tra.

## 5. Ưu tiên xử lý đề xuất

| Ưu tiên | Công việc | Phạm vi |
|---|---|---|
| P1 | Sửa UI-01, UI-02, UI-03 | CSS và hai template; không đổi nghiệp vụ |
| P2 | Sửa UI-04 | Một token/link color và regression test |
| P3 | Kiểm chứng mất mạng rồi cân nhắc fallback UI-05 | Chỉ bổ sung trạng thái lỗi bản đồ nếu tái hiện |

Mỗi thay đổi nên có regression test cho tên truy cập của control, label liên kết đúng, và guard CSS cho cỡ chữ/màu. Sau khi sửa cần chạy full `pytest` và kiểm tra lại ba viewport.

## 6. Readiness ban đầu

**READY WITH MINOR UI ISSUES.** Không có bằng chứng về lỗi giao diện làm chặn demo MVP, luồng đặt sân hoặc thanh toán mô phỏng. Ba issue Medium ảnh hưởng khả năng đọc và hỗ trợ truy cập, nên sửa trước buổi nghiệm thu nếu còn thời gian. UI-04 và UI-05 không phải blocker. Không có lỗi MoMo-only nào được dùng để hạ readiness của MOCK-only MVP.
