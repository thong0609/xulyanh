# Kiểm chủ thể ảnh trước khi áp dụng rule duyệt rộng

Phiên bản thử nghiệm: `image-subject-guard-v2`.

Mục tiêu: phân biệt nguồn mô tả chung với nguồn đã gắn ảnh cho một thực thể khác. Giữ `generic_description → yes` và `unconfirmed_branch → yes` khi đúng điều kiện; không chuyển toàn bộ hai nhóm này thành no.

## Cách hoạt động

Trong chính request kiểm nguồn hiện có, model phải bổ sung tên/loại chủ thể ảnh, một câu trích nguyên văn, ID block bằng chứng, quan hệ với ảnh (caption/alt/local_sentence/unbound) và ID ứng viên bị mâu thuẫn. Không thêm một lượt gọi model riêng.

Code chỉ dùng các trường mới để ghi đè quyết định dương khi:

- Quote tồn tại nguyên văn trong block local_text/alt được tham chiếu.
- Quote có tên chủ thể model nêu và được model xác định gắn với ảnh.
- Bằng chứng xác định một trường khác, loại thực thể xung đột (như đường dây/trạm biến áp), hoặc model chỉ rõ ID ứng viên bị mâu thuẫn.

Khi đó ứng viên được chuyển vào `different_entity_ids`, bỏ khỏi generic/branch yes, xóa winner nếu winner bị mâu thuẫn. Giữ thông tin chứng cứ và quyết định trước ghi đè trong `checks.group_source.source_subject_guard`.

Không dùng tên ở heading, menu, danh sách địa điểm lân cận hoặc quote không kiểm chứng được để tự ghi đè thành no. Các quyết định loại trực tiếp của model trong policy v4 vẫn được áp dụng như trước.

Tên dịch/bí danh được model chọn vẫn được phép. Villa, phòng, sảnh, hồ bơi có thể thuộc cùng khách sạn/resort; khác cách mô tả không tự là khác cơ sở. Số thứ tự ảnh không tự là số định danh cơ sở.

## Phạm vi triển khai

- Adapter `tool/source_subject_guard.py` được bật bằng `--source-guard` trong `tool/test_luna_key_pilot.py`.
- Chưa bật mặc định cho runner Standard hoặc Batch chạy toàn bộ dữ liệu. Không thay đổi chính sách của các run cũ khi resume.
- OCR và URL fast path giữ nguyên. Trường hợp URL duyệt nhanh sai không nằm trong sửa đổi này.
- Schema/prompt/task kiểm nguồn có namespace mới để không dùng đáp án kiểm nguồn cũ.
- `--reuse-ocr-from` chỉ chép cache đúng cấu trúc OCR; dùng để giữ OCR cố định khi so prompt kiểm nguồn. Không gọi lại OCR khi cache khớp.
- Cần output mới khi đổi adapter/schema/prompt. Marker trong output kiểm tra hash adapter để không resume lẫn phiên bản.

## Lệnh pilot đang dùng

```bash
env -u OPENAI_API_KEY /usr/bin/python3 tool/test_luna_key_pilot.py \
  --base-url https://modelapi.vn/v1 \
  --output-dir tool/outputs/luna_grouped_standard_v4_pilot50_modelapi_subject_v2 \
  --source-guard \
  --reuse-ocr-from tool/outputs/luna_grouped_standard_v4_pilot50_modelapi \
  --workers 8 --budget-usd 0.50 --run
```

Run này đã được chạy khi triển khai. Nếu cần tiếp tục run chưa hoàn thành, thêm `--resume`; để thử lại từ đầu, chọn output mới.

Chi phí ledger vẫn tính theo giá Luna cấu hình trong dự án, chưa xác minh giá hóa đơn ModelAPI. Phần xác định câu nào thực sự gắn với ảnh vẫn phụ thuộc model và cửa sổ ngữ cảnh extractor; quote kiểm chứng được chưa đảm bảo mọi diễn giải đều đúng.
