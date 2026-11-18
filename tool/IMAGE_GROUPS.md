# Duyệt yes/no theo nhóm URL ảnh

Chạy `/usr/bin/python3 tool/group_images_server.py --port 8010`, mở http://127.0.0.1:8010 và tải lại trang sau khi cập nhật code.

Mỗi nhóm là các record có image_url giống hệt. Chọn một radio rồi bấm **Áp dụng nhóm này**:
- Chỉ nhóm có nút vừa bấm được ghi; các nhóm khác, kể cả đã có lựa chọn chờ, không bị áp dụng.
- Record được chọn nhận approve=yes.
- Tất cả record còn lại trong cùng nhóm nhận approve=no, kể cả khi trước đó có nhãn khác.
- Nhóm chưa chọn hoặc bấm Không đổi nhãn nhóm được giữ nguyên nhãn.
- Giữ đủ mọi record, nội dung khác và thứ tự CSV; không xóa dòng.

Khi mới chọn, giao diện hiện “Sau áp dụng: yes/no”; nhãn file chính chỉ đổi lúc bấm Áp dụng. Lựa chọn lưu trong tool/outputs/image_groups/general_10m_part_02/selection.json và được giữ sau khi áp dụng để theo dõi nhóm đã duyệt.

Nút Đề xuất 1 yes mỗi nhóm chỉ điền các nhóm chưa chọn, ưu tiên dòng yes hiện có, rồi trống, rồi no; cùng nhãn chọn dòng đầu. Bạn có thể đổi radio trước khi áp dụng. Nút bỏ lựa chọn không hoàn tác các nhãn đã ghi.

Xuất CSV đã gán nhãn tạo bản riêng labelled_<timestamp>.csv trong thư mục output, đủ số dòng gốc và nhãn dự kiến. Áp dụng nhóm cập nhật CSV chính cho riêng nhóm đó. Mỗi phiên server có một bản sao lưu CSV đầy đủ trước lần ghi đầu trong tool/backups; mỗi lần áp dụng có audit JSON lưu nhãn cũ/mới từng dòng để đối chiếu. Cách này tránh tạo thêm bản CSV ~60 MB cho mỗi nhóm. Nút áp dụng chung ở cuối trang đã bỏ. Nếu CSV bị chỉnh từ nơi khác, server từ chối ghi; cần khởi động lại và đối chiếu trước khi chọn lại.

Chỉ so URL nguyên chuỗi, chưa phát hiện ảnh giống nội dung nhưng URL khác. URL trống được giữ riêng từng record. File trong done/ không được chỉnh.

Nhãn Luna trước đó đã ghép vào file chính: 422 yes và 499 no; 466 record Luna chưa kết luận giữ trống, 613 record đã xóa trước đó không thêm lại. Backup/audit lần ghép ở tool/backups.

Bộ lọc Đã duyệt/Chưa duyệt dựa vào CSV: mọi record trong nhóm có yes hoặc no mới là Đã duyệt; chỉ cần một record trống thì nhóm là Chưa duyệt. Chọn radio hoặc đề xuất mà chưa áp dụng không đổi trạng thái bộ lọc.

Nút Tất cả no nằm cạnh Áp dụng nhóm này: ghi no cho mọi record của riêng nhóm, không cần chọn radio, không xóa dòng. Lựa chọn yes cũ của nhóm được bỏ để lần xuất sau không khôi phục yes. Các nhóm khác giữ nguyên.
