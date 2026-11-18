# Duyệt nhiều record Yes trong một nhóm ảnh

Khởi động lại group_images_server.py sau khi cập nhật để backend hỗ trợ danh sách lựa chọn. Checkbox cho phép chọn nhiều record; Áp dụng nhóm này gán yes cho mọi record được chọn, no cho các record còn lại trong toàn nhóm (kể cả đang ẩn bởi tìm kiếm). Bỏ chọn hết không thay nhãn; dùng Tất cả no nếu muốn gán toàn nhóm no. Không đổi nhãn nhóm hủy lựa chọn đang chờ. Đề xuất 1 yes vẫn là thao tác riêng có chủ đích.

Lựa chọn cũ một index được đọc tương thích; lựa chọn nhiều index được lưu trong selection.json. Chọn/chuyển trang/tìm kiếm không tự ghi approve. Nhãn chỉ đổi khi áp dụng hoặc khi xuất CSV với các lựa chọn đang chờ. Các rule tự động Luna không bị thay đổi bởi tính năng duyệt tay này.

```bash
/usr/bin/python3 tool/group_images_server.py \
  --input tool/outputs/luna_grouped_standard_unlabeled2000/selected_rows.csv \
  --port 8011
```

Mở http://127.0.0.1:8011. Chọn Tất cả ảnh nếu cần xem cả nhóm một record. Chỉ selected_rows.csv được ghi bởi server trên; CSV chính và done/ không bị đổi. Kiểm thử dùng CSV tạm riêng, không sửa dữ liệu người dùng.
