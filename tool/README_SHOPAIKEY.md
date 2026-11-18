# GPT-6 Luna qua ShopAIKey Cheap API

Endpoint hiện dùng: `https://api.shopaikey.com/v1/responses` (đã thử trực tiếp).
Đã bỏ đường Chat Completions vì thử nghiệm cùng key/model/câu ngắn báo thêm ~18k input.
Giá tham khảo ngày 16/11/2026: https://shopaikey.com/models .

## Key

Điền `SHOPAIKEY_API_KEY` trong `tool/.env`. Key phải được shop cấp cho nhóm Cheap API.
Code không thể ép đổi nhóm key. Không dùng fallback OPENAI_API_KEY hoặc DEEPSEEK_API_KEY.
Không in key và không gửi key lên API kiểm số dư dạng query URL.

## Pilot

### Kiểm spam/chất lượng ảnh và OCR cùng request

```bash
tool/.venv/bin/python tool/run_grouped_shopaikey.py \
  --pilot --image-quality --workers 8 --budget-credit 1 --run
```

Output riêng: `tool/outputs/luna_shopaikey_quality_pilot50/`. Preview: bỏ `--run`.
Chọn đúng 50 seed cũ, mở rộng 85 record. Resume giữ `--image-quality` và thêm
`--resume`. Không bật cờ này trên output cũ: các record đã hoàn tất sẽ bị bỏ qua,
nên runner chặn trộn policy và yêu cầu output mới.

Luồng: tải ảnh → một request kiểm ảnh + OCR → reject thì no cả nhóm, review thì
để pending, pass thì chạy URL/OCR/nguồn như cũ. OCR sau gate dùng lại cache của
chính request kiểm ảnh. Khớp URL không bỏ qua gate. Không có retry.

Rule tham chiếu: `rule_approve_image.md`. Biển hiệu/logo vật lý của POI, watermark
nhỏ không che chủ thể không bị loại chỉ vì có chữ/logo. Bản đồ hoặc chi tiết nghi
vấn cần phóng to: review; không giả định model đã kiểm đủ chi tiết nhỏ. Quyết định
reject/review phải có lý do và mô tả bằng chứng nhìn thấy.

`quality_checks/*.json` lưu verdict, OCR, URL và hash ảnh/rule. Kết quả `results.jsonl`
có `checks.image_quality`; reject dùng reason `IMAGE_QUALITY_REJECTED`. Review/lỗi
ở `deferred_groups.jsonl`; không được tính là hoàn tất và không gán no từ lỗi.
Nếu hậu kiểm alias trên CSV sao chép, mang theo thư mục quality_checks để giữ chặn.

Ảnh trước đây duyệt ngay bằng URL nay phải được xem nên có thể thêm lượt API.
Ảnh vốn cần OCR dùng chung request; prompt/output tăng. Ảnh bị reject tiết kiệm
lượt kiểm nguồn. Chưa đo chi phí/chất lượng thực tế cho mode này.

Sau khi pilot ổn, chạy mới trên CSV chính:

```bash
tool/.venv/bin/python tool/run_grouped_shopaikey.py \
  --image-quality --input general_10m_part_02.csv --first 100000 \
  --output-dir tool/outputs/luna_shopaikey_quality_remaining_all \
  --workers 16 --budget-credit 40 --run
```

Đây là một run mới kiểm lại tập chưa gắn nhãn trong CSV chính; không kế thừa tiến độ
run không có quality, không tự dừng tiến trình cũ, không tự cắt CSV chính hoặc done.

```bash
tool/.venv/bin/python tool/run_grouped_shopaikey.py --pilot --workers 8 --budget-credit 1 --run
```

Preview: bỏ `--run`. Chọn 50 seed cũ, mở rộng 85 record. Resume: thêm `--resume`.
Output mặc định: `tool/outputs/luna_shopaikey_cheap_pilot50/`.

## Chạy CSV chính

```bash
tool/.venv/bin/python tool/run_grouped_shopaikey.py \
  --input general_10m_part_02.csv --first 3000 \
  --output-dir tool/outputs/luna_shopaikey_cheap_3000 \
  --workers 8 --budget-credit 3 --run
```

Chọn các dòng approve trống, mở rộng đầy đủ nhóm ảnh. Giữ user-rules-v4,
source subject guard v2, OCR trước kiểm nguồn. Cache đáp án nằm riêng trong output;
không dùng lại câu trả lời Luna/DeepSeek trước đó. Không sửa/cắt CSV chính hoặc done.
Rule mở rộng yes theo bí danh vẫn là bước hậu kiểm riêng như các bản pilot trước.

## Credit và cache

- Một credit shop giá 3.250đ. Budget 1 tương đương 3.250đ số dư sử dụng,
  không phải giá gói nạp tối thiểu. Các trường cost/charged_or_reserved_usd là credit shop.
- Giá Cheap đã bao gồm hệ số nhóm: input 0.24 credit/M; output 0.90;
  cache read 0.024; cache write 0.30. Không nhân hệ số nhóm thêm lần nữa.
- Ledger phân biệt cache read/write khi response báo trong prompt_tokens_details.
  Chưa đối chiếu hóa đơn gateway; response không báo cache write sẽ được tính input thường.
- Không thêm cấu hình cache riêng trong request; phụ thuộc cơ chế endpoint.
  Không bảo đảm cache hit hoặc hóa đơn bằng ước tính.
- Theo yêu cầu mới: KHÔNG retry tự động ở API, OCR, kiểm nguồn, tải ảnh/trang hay group.
  HTTP redirect hợp lệ vẫn được đi theo, không phải thử lại request thất bại.
- Lỗi model, mạng, tải ảnh/nguồn, schema/ID hoặc lỗi
  xử lý: tạm bỏ TOÀN BỘ group, không ghi nhãn lỗi thành no, tiếp tục
  group khác. Ghi nguyên nhân vào `deferred_groups.jsonl`; resume sẽ thử lại các group
  chưa có kết quả. Nhóm lỗi ở lượt trước được xếp cuối, dữ liệu mới được ưu tiên.
- Lỗi hiện gọn cạnh tiến độ, ví dụ `128/70253 records | group 2 | cost<=$0.1 | skip=1 HTTP_403`.
  Chi tiết trong deferred_groups.jsonl; số completed không tăng do skip.
- `TARGET_IMAGE_CONTEXT_NOT_FOUND` vẫn theo rule thiếu ngữ cảnh cho yes; không coi
  việc không tìm được chữ quanh ảnh là lỗi kỹ thuật. Các lỗi lấy trang/response khác
  được defer. Kết quả cũ bị lỗi đã được backup và đưa về pending khi nâng cấp run chính.
- Vẫn dừng khi hết budget, bị ngắt, lỗi xác thực/quota toàn key (HTTP 401/402/403),
  hoặc không thể ghi checkpoint. Nhóm bị 403 lúc tải trang nguồn được defer, khác với
  403 từ API model. Khi chỉ còn nhóm defer: hoàn tất lượt quét và báo cần resume,
  không lặp vô hạn. Không đánh dấu complete khi vẫn còn pending.

## So sánh sau pilot

```bash
tool/.venv/bin/python tool/compare_local_runs.py \
  --baseline-dir tool/outputs/luna_grouped_standard_v4_pilot50_modelapi_subject_v2 \
  --candidate-dir tool/outputs/luna_shopaikey_cheap_pilot50 \
  --output-dir tool/outputs/comparison_luna_shopaikey_cheap \
  --input tool/input/general_10m_part_02_copy.csv \
  --left-label 'Luna modelapi subject v2' --right-label 'Luna ShopAIKey Cheap'
```

So sánh thô trước hậu kiểm; cần áp dụng cùng rule alias lên bản sao cả hai CSV
để so công bằng. Không sửa journal API thành nhãn hậu kiểm.

Setup đã kiểm tra offline adapter/định tuyến model, payload ảnh, công thức credit cache
và preview 50→85; chưa gọi API trả phí bằng key người dùng.

## Điều tra và nâng cấp Responses 16/11/2026

Các kiểm tra có giới hạn sau setup đã dùng key thật, lưu trong
`tool/outputs/shopaikey_diagnostics/`:

- Shop Chat, `Reply OK.`: 18.467 input; cùng câu qua Shop Responses: 9 input.
- Cùng request Chat qua OpenAI trực tiếp: 9 input.
- OCR mẫu cũ qua Chat: 19.823 input, JSON có explanation thừa.
- OCR cùng record qua Responses: 1.160 input, 16 output, JSON đúng schema;
  bước kiểm nguồn: 1.659 input, 200 output, không lỗi schema.

Kết luận quan sát được: overhead xuất hiện ở đường Chat của gateway; chưa biết
chính xác prompt upstream hay phép quy đổi nào tạo ra nó. Không quy kết gian lận.
Đổi endpoint và cache riêng cho các request pending; không ghi đè nhãn journal cũ.
Runner cho phép resume có audit với hash bản trước đã xác nhận; selection và
entity rules giữ nguyên. Phải chạy bản mới/resume để áp dụng, không tự chạy toàn CSV.
# Cập nhật 18/11/2026: policy v5

Runner mới mặc định `--policy user-rules-v5`: phân biệt ảnh không xác nhận được
trong nguồn với ảnh có thật nhưng thiếu chữ; chấm địa chỉ nghiêm hơn; ưu tiên
mâu thuẫn và mở rộng yes cho bí danh trong cùng nhóm. Xem
[GROUPED_USER_RULES_V5.md](GROUPED_USER_RULES_V5.md) để biết chi tiết và lệnh thử.
Các lệnh/thống kê v4 bên dưới là tài liệu lịch sử. Dùng output mới cho v5;
không resume output `luna_shopaikey_cheap_remaining_all` để trộn hai policy.

