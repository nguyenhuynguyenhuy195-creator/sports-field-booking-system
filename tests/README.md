# Thư mục kiểm thử

- `conftest.py`: tạo Flask app với testing config cho pytest-flask.
- `integration/`: kiểm tra application factory và health routes.
- `unit/`: dành cho pricing, booking, contribution, payment và refund services sau này.

Testing config dùng SQLite trong bộ nhớ để test nền móng nhanh và độc lập. Các chức năng phụ thuộc hành vi SQL Server phải có integration test riêng trên SQL Server khi model được triển khai.
