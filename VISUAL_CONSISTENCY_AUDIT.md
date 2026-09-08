# AUDIT NHẤT QUÁN THỊ GIÁC

**Ngày:** 09/09/2026
**Phạm vi:** Public, Người dùng, Chủ sân và Quản trị viên của MVP thanh toán mô phỏng
**Kết luận:** **PASS — không có lỗi nhất quán thị giác mức blocker**

## Phương pháp

- Kiểm tra trực tiếp các màn hình đại diện ở 1280×720, 768×1024 và 390×844.
- Kiểm tra tràn ngang, control nằm ngoài viewport, focus keyboard, typography và contrast text thường.
- Rà các khu vực Owner: dashboard, lịch, booking, tài chính, cơ sở, form cơ sở và bảng giá.
- Rà các khu vực Admin: dashboard, duyệt Chủ sân, cơ sở, booking, kèo, tài khoản và giám sát.
- Public/User gồm đăng nhập, danh sách sân và form đặt sân. Ba nút ngày nằm ngoài mép mobile của form đặt sân thuộc vùng cuộn ngang nội bộ, không tạo document overflow.

## Kết quả theo nhóm

| Hạng mục | Public/User | Owner | Admin | Kết quả |
|---|---|---|---|---|
| Typography | Heading, mô tả và CTA có phân cấp rõ. | Metadata/control tối thiểu 13 px sau UI-01. | Metadata/control tối thiểu 13 px sau UI-01. | Pass |
| Spacing | Card, form đặt sân và filter giữ khoảng cách đọc được ở mobile. | Card, form, bảng và sidebar không chồng lấn. | Danh sách master-detail vẫn phân tách rõ ở desktop và chuyển một cột trên mobile. | Pass |
| Button hierarchy | CTA xanh là thao tác chính, outline/link là thao tác phụ. | Hero và thao tác vận hành giữ phân cấp chính-phụ. | Chấp thuận/Từ chối và filter phân biệt bằng màu/kiểu nút. | Pass |
| Form | Label và validation hiển thị rõ. | Input ảnh có accessible name. | Textarea lý do từ chối có label, placeholder và help text. | Pass |
| Card/table/empty state | Card sân và wizard không tràn ngang. | Empty state có icon, heading và mô tả; table có wrapper cuộn riêng. | Card hồ sơ, table vận hành và trạng thái rỗng giữ cấu trúc nhất quán. | Pass |
| Màu sắc | Xanh chính/đậm duy trì tương phản link đăng ký. | Nền xanh Owner, surface trắng và muted text đủ phân cấp. | Navy/green/neutral đúng phong cách operations dashboard và text thường đạt ngưỡng đo. | Pass |
| Responsive | Không có document overflow ở ba viewport. | Không có document overflow hoặc control vô tình ra ngoài viewport. | Không có document overflow hoặc control vô tình ra ngoài viewport. | Pass |
| Keyboard focus | Focus link đăng ký hiện outline 3 px. | Nút menu mobile nhận outline 3 px khi Tab. | Menu, filter, hồ sơ và action nhận outline 3 px khi Tab. | Pass |

## Điểm cần theo dõi

- Bản đồ Leaflet/OpenStreetMap vẫn là phụ thuộc mạng ngoài. Lần kiểm chứng hiện tại tải đủ 8/8 tile và không có lỗi console, nên chưa mở rộng sửa UI-05.
- Audit này kiểm tra rendering thực tế và computed style của các trang đã nêu; không phải chứng nhận WCAG hoặc kiểm thử với mọi trình duyệt/screen reader.

## Final visual readiness

**READY.** Không phát hiện vấn đề typography, spacing, button hierarchy, form, card, table, empty state, màu sắc hoặc responsive cần sửa thêm trong phạm vi MVP hiện tại.
