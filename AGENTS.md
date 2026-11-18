# Quy ước xử lý CSV của người dùng

- Khi người dùng yêu cầu chuyển một CSV kết quả đã duyệt vào `done/`, hoàn tất cả hai việc: lưu vào `done/` theo format tên sẵn có và loại các record tương ứng khỏi CSV chính ở root. Đây là thao tác đã được người dùng cho phép từ ngày 15/11/2026; không cần hỏi lại riêng việc cắt khỏi CSV chính.
- Đối chiếu record theo các trường dữ liệu trừ `approve`, vì nhãn sau duyệt có thể khác CSV chính. Không loại cả nhóm chỉ vì trùng image_url; chỉ loại các record thuộc file kết quả.
- Sao lưu CSV chính vào `tool/backups/` trước khi ghi; giữ nguyên các record còn lại và kiểm tra không còn record giao nhau với file kết quả. Lưu audit trong `tool/outputs/`.
- File đã có trong `done/` được phép đọc để đối chiếu; không sửa, xóa hoặc ghi đè nếu người dùng chưa yêu cầu rõ. Bỏ qua `thu_nghiem/`.
- Khi chỉ chạy API, so sánh hoặc hậu kiểm nhãn trong output, không tự cắt CSV chính. Quy ước cắt áp dụng khi chuyển kết quả vào `done/` hoặc khi người dùng yêu cầu cắt trực tiếp.
- Báo số record loại, số còn lại và trạng thái không trùng sau khi hoàn tất. Nếu không đối chiếu được đầy đủ thì không xóa dựa trên tên hoặc URL gần giống; báo rõ phần chưa khớp.
