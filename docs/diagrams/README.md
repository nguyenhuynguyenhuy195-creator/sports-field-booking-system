# Sơ đồ cần bổ sung

Hãy tạo và đặt các file sau vào thư mục này:
- `use-case.png`
- `erd.mmd` và `erd.png`
- `booking-activity.png`
- `booking-sequence.png`

Có thể vẽ bằng Draw.io. Các sơ đồ là tài liệu tham khảo và phải được cập nhật đồng bộ khi nghiệp vụ trong tài liệu Markdown thay đổi.

## ERD

- `erd.mmd`: nguồn Mermaid có thể chỉnh sửa, gồm 13 bảng và các quan hệ chính.
- `erd.png`: bản xuất độ phân giải cao dùng trong báo cáo và review thiết kế.
- Ký hiệu `PK`: khóa chính; `FK`: khóa ngoại; `UK`: khóa duy nhất.
- Check constraint, filtered unique index, trạng thái và hành vi xóa chi tiết được quy định tại `docs/05-database-design.md`; ERD không thay thế tài liệu này.
