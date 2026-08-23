# Quy ước chung của dự án

- Dự án sử dụng Python Flask, Jinja và Bootstrap.
- Không chuyển sang React, Vue hoặc framework frontend lớn.
- Không thay đổi route, model, database schema hoặc business logic nếu task không yêu cầu rõ ràng.
- Không tạo migration chỉ để phục vụ thay đổi giao diện.
- UI dùng tiếng Việt nghiệp vụ; tránh thuật ngữ kỹ thuật tiếng Anh khi hiển thị cho người dùng.
- Admin UI theo phong cách SaaS Operations Dashboard: navy, green và neutral; bố cục sạch, ít shadow, phân cấp rõ ràng.
- Dùng một hệ thống icon thống nhất, ưu tiên Bootstrap Icons; không dùng emoji hoặc ký tự Unicode làm icon chính.
- User UI, Owner UI và Admin UI phải thể hiện rõ vai trò và phong cách riêng.
- Giao diện luôn responsive trên desktop, tablet và mobile.
- Ưu tiên tái sử dụng code hiện có; không rewrite toàn bộ project.
- Chỉ đọc và sửa các file liên quan trực tiếp đến task để tránh thay đổi lan rộng.
- Sau mỗi task, chạy `python -m pytest`.
- Không xóa hoặc sửa test chỉ để che regression.
- Không tự commit nếu chưa được yêu cầu.
- Cuối mỗi task phải báo cáo: files changed, thay đổi chính, business logic có thay đổi hay không và kết quả test.
