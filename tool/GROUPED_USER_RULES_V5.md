# Policy v5 — cải tiến sau đối chứng 100 record, 18/11/2026

Áp dụng cho runner Standard local OpenAI và ShopAIKey. Mặc định CLI mới là
`--policy user-rules-v5`. V4 vẫn được giữ để đối chiếu bằng cờ rõ ràng, nhưng không
trộn kết quả v5 vào output/journal v4 hoặc âm thầm chuyển policy khi resume.
Runner từ chối resume khác policy/fingerprint; dùng thư mục output mới.

## 1. Xác nhận ảnh trong nguồn

Sau OCR và các nhánh khớp tên nhanh hiện có:

- Có đúng ảnh được tìm thấy trong DOM nguồn (`target_found=true`), nhưng không có
  chữ/alt/heading đi kèm: **yes**, lý do `USER_FOUND_IMAGE_EMPTY_CONTEXT_YES`.
- Không xác nhận được ảnh trong nguồn: **trống**, lỗi `TARGET_IMAGE_NOT_CONFIRMED`.
  Không còn tự yes chỉ vì thiếu ngữ cảnh. Đây cũng bao gồm trường hợp bộ trích xuất
  chưa hỗ trợ cách nhúng ảnh; trống không có nghĩa chắc chắn ảnh vắng mặt.
- Không tải được ảnh/trang, trang bị chặn, JSON/model response lỗi: **trống**.
- Nguồn đủ bằng chứng xác định thực thể khác hoặc mâu thuẫn địa điểm/vai trò: **no**.

Trang rất ít chữ nhưng có đúng ảnh vẫn có thể yes nếu không phải trang chặn truy
cập. `source_page.py` trả thêm `access_blocked` và `text_too_short` để phân biệt.
Một footer bình luận ghi reCAPTCHA không còn tự biến cả bài đầy đủ thành trang chặn.

Nhánh URL/OCR khớp tên trực tiếp giữ nguyên về cơ bản: chỉ khi cần kiểm nguồn mới
áp điều kiện hiện diện ảnh trong nguồn. V5 không tự tăng thành hai lượt model so nguồn.

## 2. Chấm địa chỉ

`rank_addresses(..., strict_branch=True)` loại tên tỉnh/thành phố khỏi chuỗi
`branch` trước khi chấm điểm. “TP.HCM” trên bảng tuyến xe không có 30 điểm nhánh.
Địa chỉ đường + số nhà hoặc tên cơ sở/chi nhánh phân biệt vẫn có thể chọn ứng viên.
Điểm hành chính chỉ là thông tin bổ trợ; không dùng đơn độc để xác nhận cơ sở.

## 3. Mâu thuẫn ưu tiên trước rule nguồn chung

- Source request nhận thêm kết quả OCR, trong cùng request kiểm nguồn đang có.
- Prompt mới yêu cầu phân biệt chủ thể với biển nền hoặc điểm đến tuyến xe;
  mâu thuẫn rõ thắng `generic_description_ids`/`unconfirmed_branch_ids`.
- `image-subject-guard-v3` dùng trích dẫn đã kiểm chứng trong alt/chữ gắn với ảnh để
  chặn suy rộng “cùng tuyến” → một ga và “sân bay” → công ty dịch vụ sân bay.
- Nhà ga/chi tiết kiến trúc thuộc sân bay có cùng tên riêng vẫn có thể đại diện cho
  sân bay; không tự no chỉ vì ảnh chụp một thành phần. Mâu thuẫn địa điểm rõ vẫn no.
- Nhãn âm rõ từ model được giữ với lý do riêng trước khi mở rộng bí danh, kể cả khi
  cùng response chọn một record khác làm winner.

Task source mới: `group_source_user_rules_v5`, qua guard trở thành
`group_source_subject_guard_v3`. Cache source vì thế tách khỏi quyết định v4.
OCR độc lập về tên thực thể vẫn có thể tái sử dụng khi prompt/ảnh giống nhau.

## 4. Mở rộng yes trong nhóm ngay sau quyết định

`group_aliases.py` chạy sau khi nhóm hoàn tất:

- Cùng giá trị `image_url`, không gộp URL rỗng.
- Chụp các mốc yes trước lượt mở rộng; không nối chuỗi bằng record vừa đổi yes.
- Chỉ đổi no do `GROUP_OTHER_RECORD_SELECTED` khi xác nhận tên/địa chỉ tương thích.
- Các bí danh Times City đã rà được nhận trực tiếp; Phú Bài/Phú Bài (Huế) và các
  biến thể tương thích được kiểm bằng hàm so tên hiện có.
- Không ghi đè nhãn có sẵn trong input, lỗi chưa xử lý, hoặc no do model xác định
  thực thể khác/mâu thuẫn địa điểm/đề xuất loại rõ ràng.
- Không coi hồ, cửa hàng, phân khu Park Hill Premium, bến trực thuộc hay tên ghép
  nhiều địa điểm là bí danh của toàn khu chỉ vì có phần tên chung.

Lý do nhãn đổi: `GROUP_EQUIVALENT_ENTITY_YES`; `checks.group_alias` ghi tên và ID
mốc, nhãn/lý do trước sửa cùng loại quan hệ. Không thêm request API.

## Luồng và đầu ra

1. CSV → gom nhóm ảnh, giữ thứ tự và các ứng viên cùng nhóm.
2. Khớp URL/OCR, chấm địa chỉ nghiêm hơn; khi chưa đủ thì tải/trích nguồn bằng code.
3. Xác nhận đúng ảnh trong nguồn; không xác nhận được thì pending.
4. Một request so nguồn dùng blocks + OCR + các ứng viên; ưu tiên mâu thuẫn.
5. Mở rộng yes cho bí danh tương thích; ghi kết quả và bằng chứng vào journal.

Nếu bất kỳ record nào trong nhóm còn lỗi/pending, scheduler giữ cả nhóm pending,
ghi `deferred_groups.jsonl`, không nhập nhãn no do lỗi vào journal và tiếp tục nhóm
khác. Đây là cơ chế commit theo nhóm hiện có, không phải tự retry từng request.
Nhóm đã có nhãn trong input không tự bị sửa bởi bước alias.

## Chạy thử đúng mẫu đối chứng cũ

Input 101 record giữ trọn 75 nhóm, trong đó 100 record là mẫu đã rà. Chạy ở root:

```bash
env -u OPENAI_API_KEY tool/.venv/bin/python tool/run_grouped_luna_standard.py \
  --input tool/outputs/official_vs_shopaikey_latest100_20261118/input.csv \
  --first 101 --policy user-rules-v5 --group-yes multiple \
  --output-dir tool/outputs/luna_official_v5_latest100 \
  --model gpt-6-luna --workers 4 --budget-usd 0.50 --run
```

Bỏ `--run` để chỉ preview, không gọi API. Sau khi một run v5 đã bắt đầu, thêm
`--resume` với đúng output đó để tiếp tục. Lệnh v5 trên không dùng `--unlabeled-only`
để bảo đảm không thay đổi mẫu; file input là snapshot thử nghiệm riêng.

Không tự sửa file trong done, CSV chính, hoặc nhãn các lượt đã duyệt. Chưa có kết
quả trả phí v5 trong lượt triển khai code; kiểm tra tự động dùng mô phỏng lỗi và
các cặp dữ liệu từ audit. Cần đối chứng thực tế trước khi đánh giá chất lượng v5.
