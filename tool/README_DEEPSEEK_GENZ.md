# DeepSeek GenzShop local

Tài liệu đọc ngày 16/11/2026:

- Sản phẩm và mẫu request: https://genzshop.vn/vi/san-pham/deepseek/api-deepseek
- Trang hướng dẫn: https://genzshop.vn/vi/huong-dan/deepseek
- Link Notion từ hướng dẫn không truy cập được trong phiên setup. Adapter dựa trên mẫu cURL công khai tại trang sản phẩm: POST `https://1gw.gwai.cloud/v1/messages`, `x-api-key`, `anthropic-version: 2023-06-01`.

## Cấu hình

Điền vào `tool/.env`:

```dotenv
DEEPSEEK_API_KEY=YOUR_KEY
DEEPSEEK_BASE_URL=https://1gw.gwai.cloud/v1
DEEPSEEK_MODEL=deepseek-v4.1-flash-1017
```

Key OpenAI độc lập với key DeepSeek. Không cần thay OPENAI_API_KEY.

## Pilot và so sánh

Từ root dự án, preview mặc định không gọi API:

```bash
tool/.venv/bin/python tool/run_grouped_deepseek.py --pilot
```

Chạy đúng pilot 50 cũ, mở rộng 85 record:

```bash
tool/.venv/bin/python tool/run_grouped_deepseek.py \
  --pilot --workers 8 --budget-credit 1 --run
```

Resume: thêm `--resume` và giữ nguyên cấu hình, output. Có thể tăng budget.

So sánh sau khi pilot hoàn tất:

```bash
tool/.venv/bin/python tool/compare_local_runs.py \
  --baseline-dir tool/outputs/luna_grouped_standard_v4_pilot50_modelapi_subject_v2 \
  --candidate-dir tool/outputs/deepseek_genz_pilot50 \
  --output-dir tool/outputs/comparison_luna_deepseek_genz_pilot50 \
  --input tool/input/general_10m_part_02_copy.csv \
  --left-label 'Luna subject v2' --right-label 'DeepSeek GenzShop'
```

## CSV chính

Sau khi đánh giá pilot:

```bash
tool/.venv/bin/python tool/run_grouped_deepseek.py \
  --input general_10m_part_02.csv --first 3000 \
  --output-dir tool/outputs/deepseek_genz_3000 \
  --workers 8 --budget-credit 3 --run
```

Chọn các record approve trống đầu tiên, mở rộng toàn bộ nhóm cùng image_url. Lưu snapshot và kết quả riêng trong output; không tự sửa/cắt CSV chính hoặc done.

## Pipeline, ngân sách và giới hạn

- Giữ scheduler nhóm, OCR trước rồi mới so tên/kiểm nguồn, user-rules-v4, multiple yes và source subject guard v2. Group pipeline dùng chung runner local; cache câu trả lời DeepSeek nằm riêng trong output, không dùng đáp án Luna.
- Schema JSON được gửi trong system instruction do mẫu API công khai không công bố chế độ strict JSON schema. Kết quả vẫn qua bộ kiểm tra schema/ID/bằng chứng của pipeline. JSON sai không được coi là đáp án hợp lệ.
- Bước mở rộng yes theo `RULE_PROPAGATE_GROUP_YES.md` vẫn là hậu kiểm riêng như runner Luna; runner không tuyên bố đã rà đủ các alias ngữ nghĩa.
- `--budget-credit` và trường `cost<=$...`/`charged_or_reserved_usd` dùng **USD credit shop**, không phải USD tiền thật. Giá cấu hình: input $0.30/M, output $1.20/M, cache read $0.006/M; $1 credit mua giá 1.500đ. Ví dụ budget 1 credit tương đương 1.500đ số dư sử dụng, không phải giá gói nạp tối thiểu.
- Usage Anthropic được chuẩn hóa, cộng input thường + cache read/write một lần. Không có giá cache write công khai cho model này nên tạm tính như input thường. Chi phí còn phải đối chiếu usage trên cổng shop.
- Không thử gọi trả phí khi chưa có key. Trang chưa khẳng định endpoint self-host này hỗ trợ ảnh; pilot sẽ xác nhận. HTTP lỗi (bao gồm không nhận ảnh) dừng run để kiểm tra, không tự chuyển thành nhãn no. Không tự chuyển sang model khác hoặc fallback dịch vụ trả phí.
- Prompt injection trong nội dung nguồn vẫn bị coi là dữ liệu theo system instruction hiện tại. Không in key/body lỗi của gateway.
