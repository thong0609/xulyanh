# Đối chiếu ảnh CSV

Nếu dùng repo để nhờ ChatGPT duyệt nhãn, bắt đầu với
[LABELING_CONTEXT.md](LABELING_CONTEXT.md). Dữ liệu công khai là
[`data/general_10m_part_02.csv`](data/general_10m_part_02.csv); CSV vận hành ở root
được giữ local. Bản công khai giữ đủ record, lọc các URL trùng mẫu khóa API mà
GitHub Push Protection chặn; không thay đổi CSV gốc. Policy mới nhất ở
[GROUPED_USER_RULES_V5.md](tool/GROUPED_USER_RULES_V5.md).
Các hướng dẫn giao diện và thử nghiệm cũ bên dưới được giữ để tham khảo.

Yêu cầu Python 3, không cần cài thêm thư viện.

```bash
cd /home/tts/prj/xulyanh
python3 review_server.py
```

Mở **http://127.0.0.1:8000** trên trình duyệt của máy chạy Python.
Để chọn file hoặc cổng khác:

```bash
python3 review_server.py general_10m_part_02.csv --port 8001
```

- `entity_name` nằm cạnh ảnh từ `image_url`; có nút mở ảnh gốc.
- Approve ghi `yes`, Reject ghi `no` vào cột `approve` của đúng dòng CSV.
- Bỏ đánh dấu trả ô `approve` về trống. Có thể đổi quyết định bất cứ lúc nào.
- Tìm theo tên, lọc danh mục `leaf_label`, lọc trạng thái, phân trang. Ô danh mục có gợi ý từ CSV; chọn một danh mục hoặc gõ từ khóa như `chợ`, `mầm non` để lọc các nhóm chứa từ khóa đó. Xóa ô để xem tất cả. Mở lại trang vẫn giữ kết quả đã lưu.
- Lần ghi đầu trong mỗi phiên tạo bản sao nguyên gốc `.csv.bak` (hoặc `.bak.1`, `.bak.2` nếu đã tồn tại).
- Mỗi thao tác ghi lại CSV qua file tạm rồi thay thế file chính, giữ các cột và giá trị khác. File 61 MB có thể mất vài giây mỗi lần lưu; hãy đợi thông báo thành công.
- Không sửa CSV bằng ứng dụng khác trong khi server đang chạy. Nếu phát hiện thay đổi ngoài, server từ chối ghi và yêu cầu khởi động lại.
- Chỉ mở HTML bằng cách nhấp đúp sẽ không thể ghi file; cần chạy server như trên.
- Server chỉ lắng nghe trên máy cục bộ. Ảnh tải trực tiếp từ website nguồn, nên một số ảnh có thể hết hạn hoặc bị website chặn.

Nhấn `Ctrl+C` trong terminal để dừng.

- Duyệt cả trang: tích các ảnh muốn giữ rồi bấm **Approve trang này** trên thanh dưới màn hình. Các ảnh được tích trong trang hiện tại ghi `yes`, các ảnh không tích ghi `no`, kể cả ảnh đã có trạng thái trước đó. Nếu không tích ảnh nào, toàn bộ trang nhận `no`. Mỗi lần áp dụng chỉ ghi CSV một lần và chỉ tác động các dòng đang hiển thị.

## Đối chiếu Qwen và Luna (chỉ đọc)

Trang riêng hiển thị 1.000 dòng đầu từ `reviewed (1).csv` và dòng dữ liệu 2.001–2.300 từ run Luna. Hai khoảng dòng khác nhau; nhãn Luna cập nhật tự động khi run ghi kết quả.

```bash
python3 review_compare_server.py
```

Mở **http://127.0.0.1:8001**. Mặc định file Qwen là `/home/tts/Downloads/reviewed (1).csv`; có thể chỉ định file khác bằng `--qwen-csv PATH`. Trang này không ghi thay đổi vào CSV hoặc kết quả.
