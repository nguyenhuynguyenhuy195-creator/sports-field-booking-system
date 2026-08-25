# Danh mục hành chính Việt Nam

`vietnam_administrative_units_2025.json` là snapshot chỉ đọc dùng cho migration và seed database.

- Căn cứ pháp lý: Quyết định 19/2025/QĐ-TTg ngày 30/06/2025, hiệu lực từ 01/07/2025.
- Văn bản chính thức: <https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/7/19ttg.signed.pdf>.
- Dữ liệu máy đọc được: `mantisvn/Vietnamese-Administrative-Units-Dataset`, xây dựng từ Nghị quyết 202/2025/QH15 và các nghị quyết sắp xếp cấp xã, ghim tại commit `8ea0fe381df85429a8ba39351aa34ef8d3ab6f3c`.
- Kiểm tra snapshot: đúng 34 tỉnh/thành phố, 3.321 đơn vị gồm 2.621 xã, 687 phường và 13 đặc khu; mã tỉnh không trùng và mã phường/xã không trùng.
- Chuẩn hóa có chủ đích: chuỗi được đưa về Unicode NFC và viết hoa thống nhất tiền tố loại đơn vị; không đổi mã, tên riêng hoặc quan hệ tỉnh-phường. Metadata trong JSON ghi lại phép chuẩn hóa.

Không sửa snapshot tại chỗ khi danh mục hành chính thay đổi. Hãy tạo snapshot và migration mới để dữ liệu triển khai có thể tái lập và rollback.
