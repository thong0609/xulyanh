# Chọn model API ở local: Gemini và OpenAI

Dùng `tool/api_economy.py`. Giữ OCR ảnh và bước gửi nội dung nguồn; schema và validator của bản API dùng chung. Ảnh/HTML vẫn tải bằng Python, Gemini không tự mở URL, không dùng Google Search/grounding trả phí. Không cần GPU hoặc thư viện Google SDK; dùng urllib REST và môi trường Python có Pillow như bản local cũ.

## 1. Key

Tự mở tool/.env, giữ OPENAI_API_KEY cũ nếu có và thêm dòng:

```dotenv
GEMINI_API_KEY=YOUR_GOOGLE_AI_STUDIO_KEY
```

Lấy Gemini Developer API key tại https://aistudio.google.com/api-keys. Key chỉ gửi tới endpoint nhà cung cấp tương ứng qua header; không ghi vào output. Script không tự thử key hoặc gọi model khi chỉ setup. Không copy đè .env từ .env.example nếu đã có key.

## 2. Kiểm tra tên model, chưa chạy suy luận

```bash
/usr/bin/python3 tool/api_economy.py --provider gemini --model gemini-2.5-flash-lite --check-model
```

Đây là GET metadata, không generate ảnh/text. Metadata có thể tồn tại dù quota/permission generate chưa được cấp; khi chạy thật vẫn có thể lỗi 403/429. Theo [model card 2.5](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash-lite), quyền truy cập dòng 2.5 hiện giới hạn tài khoản đã sử dụng; dự án mới nên thử [3.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite).

## 3. Thử cùng 50 dòng đầu với hai model

Các lệnh dùng 50 dòng đầu dữ liệu, không phải 50 indices pilot OpenAI cũ. Hai lượt Gemini chọn cùng dòng để dễ so sánh. Dòng có approve sẵn giữ nguyên, không lấy bù từ phía sau.

Xem dự toán offline (không key/mạng):

```bash
/usr/bin/python3 tool/api_economy.py --provider gemini --model gemini-2.5-flash-lite --first 50 --budget-usd 1 --output-dir tool/outputs/gemini25_first50
```

Chạy thật 2.5:

```bash
/usr/bin/python3 tool/api_economy.py --provider gemini --model gemini-2.5-flash-lite --first 50 --workers 1 --budget-usd 1 --output-dir tool/outputs/gemini25_first50 --run
```

Nếu tài khoản không dùng được 2.5, chạy 3.5 với output mới:

```bash
/usr/bin/python3 tool/api_economy.py --provider gemini --model gemini-3.5-flash-lite --first 50 --workers 1 --budget-usd 1 --output-dir tool/outputs/gemini35_first50 --run
```

Không có tự chuyển model khi lỗi; người dùng chọn rõ model và ngân sách. HTTP/key/model/quota/network lỗi dừng run, giữ record đó pending và giữ reservation của request chưa xác nhận usage. HTTP 400 có thể do cấu hình/schema model chưa tương thích; xem stop_reason rồi sửa cấu hình hoặc dùng run mới. Không liên tục resume khi chưa sửa lỗi quota/permission. Không tự retry có thể phát sinh phí ngoài dự kiến.

## 4. Chạy 2.000 dòng đầu

Sau khi xem chất lượng 50 dòng, ví dụ chọn 3.5:

```bash
/usr/bin/python3 tool/api_economy.py --provider gemini --model gemini-3.5-flash-lite --first 2000 --workers 3 --budget-usd 5 --output-dir tool/outputs/gemini35_first2000 --run
```

Nếu free tier bị giới hạn tốc độ, dùng workers=1 từ đầu. Quota do tài khoản quyết định, không bảo đảm 3 workers chạy ổn. Dùng `--resume` với cùng tham số để tiếp tục sau ngắt, có thể tăng budget. Thay model/provider/workers/code phải dùng output mới; không resume journal giữa hai model hoặc code cũ.

Chọn lại OpenAI:

```bash
/usr/bin/python3 tool/api_economy.py --provider openai --model gpt-5.4-mini --first 50 --workers 1 --budget-usd 1 --output-dir tool/outputs/openai_economy_first50 --run
```

## 5. Model khác và giá

Có sẵn giá Standard, USD/triệu token input/output (kiểm 12/11/2026):

| Provider | Model | Input | Output |
|---|---|---:|---:|
| openai | gpt-5.4-mini | 0.75 | 4.50 |
| gemini | gemini-2.5-flash-lite | 0.10 | 0.40 |
| gemini | gemini-3.5-flash-lite | 0.30 | 2.50 |

Nguồn: [Google Standard pricing](https://ai.google.dev/gemini-api/docs/pricing), [OpenAI mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini). Không dùng giá Batch/Flex để tính request Standard. Giá có thể đổi; truyền override để cập nhật hoặc dùng model chưa có trong bảng:

```text
--model EXACT_MODEL_ID --input-usd-per-million RATE --output-usd-per-million RATE
```

Cần kiểm tên model hỗ trợ ảnh và structured JSON trên Gemini generateContent/OpenAI Responses. Tham số model không biến model text-only thành VLM và không bảo đảm mọi model mới tương thích với thinking config.

`usage.json` tính theo provider/model đã chọn, Gemini bao gồm candidatesTokenCount + thoughtsTokenCount. Giữ giá input thường cho cả cached tokens để dự toán bảo thủ. Raw usage/resolved model version lưu trong usage để kiểm tra. Cache tách theo provider/model nên Gemini không dùng nhầm OCR OpenAI; ảnh/HTML thô dùng chung. Dự toán offline chỉ quy đổi token pilot cũ theo đơn giá, không phải chi phí đo trên Gemini vì tokenizer ảnh và số token khác nhau.

## 6. Output và kiểm thử

Trong output-dir đã chọn: first_rows.csv, reviewed.csv, results.jsonl, usage.json, summary.json, manifest.json. first_rows.csv đủ số dòng đầu yêu cầu; complete=true mới có nghĩa mọi record pending đã chọn đều hoàn tất lần thử. approve trống có thể là kiểm chưa đủ, không tự tương đương no. Model nhỏ có thể trả sai quan hệ dù JSON hợp lệ; cần xem evidence trong results.jsonl và đối chiếu ảnh/nguồn.

Đã kiểm thử offline adapter ảnh+schema, bỏ thought text khỏi JSON, tính tiền reasoning tokens, cache giữa model không lẫn, lỗi API dừng sớm, budget/checkpoint/resume. Chưa gọi Gemini thật hoặc đo chất lượng/chi phí thực; người dùng tự điền key và chạy.

## Qwen 3.7 Flash API

Đã thêm provider=qwen, model ID `qwen3.7-flash`. Đây là API Alibaba Cloud, không phải model Qwen2.5-VL-3B tự host trên Kaggle. Theo [model card](https://www.alibabacloud.com/help/en/model-studio/qwen3-7-flash), hỗ trợ ảnh và structured output. Backend dùng Chat Completions, JSON Schema strict, enable_thinking=false; vẫn OCR và kiểm nguồn bằng cùng model. Không bật web search.

1. Lấy API key và endpoint ở Alibaba Cloud Model Studio console, cùng region/workspace. Thêm `DASHSCOPE_API_KEY=...` vào tool/.env, không dùng Gemini key.
2. Copy Base URL từ console, kết thúc `/compatible-mode/v1`. Ví dụ workspace Singapore:
   `https://YOUR_WORKSPACE_ID.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1`
   Thay YOUR_WORKSPACE_ID bằng giá trị console, không chạy nguyên placeholder. Nếu console cấp URL khác trên aliyuncs.com thì dùng URL thực đó.
3. Từ thư mục dự án, chạy thử 50 dòng đầu:

```bash
/usr/bin/python3 tool/api_economy.py \
  --provider qwen --model qwen3.7-flash \
  --qwen-base-url 'https://YOUR_WORKSPACE_ID.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1' \
  --first 50 --workers 1 --budget-usd 1 \
  --output-dir tool/outputs/qwen37_first50 --run
```

Thêm --resume với cùng tham số khi cần tiếp tục. Nếu muốn 2.000 dòng, đổi --first 2000 và output-dir thành tool/outputs/qwen37_first2000. Lỗi HTTP/quota dừng và giữ record pending, không chuyển sang provider/model khác. Cache tách cả endpoint để tránh trộn deployment.

Giá Qwen thay đổi theo region và độ dài input. Với Singapore, model card hiện ghi input/output mỗi triệu token: <=32k là 0,03/0,13 USD, 32k–256k là 0,10/0,40 USD, trên 256k là 0,20/0,80 USD. Code mặc định tính bảo thủ theo mức cao nhất 0,20/0,80 cho mọi request; `charged_or_reserved_usd` vì vậy là mức ước lượng trên, không nhất thiết bằng hóa đơn thực tế. Không lấy mức thấp nhất áp cho mọi request. Có thể khai báo giá riêng nếu đã xác nhận tier/region thực tế, nhưng phải giữ giá đủ bao phủ workload. Chưa đo chất lượng Qwen 3.7 trên bộ dữ liệu này và chưa gọi API thật trong bước setup.

## GPT-6 Luna, so với đúng 50 record v2.2

Dùng key OPENAI_API_KEY đã có trong tool/.env. Model chính xác `gpt-6-luna`, Responses API, reasoning effort none. Giá Standard <=272k input: input 0,10/output 0,50 USD mỗi triệu token, có cache-write rate 0,125. [Model card OpenAI](https://developers.openai.com/api/docs/models/gpt-6-luna). Runner tính bảo thủ input Luna ở 1,25 lần giá thường cho mọi input để bao phủ cache-write, chưa trừ cached-read discount; usage lưu token thực để đối chiếu hóa đơn. Không dùng Fast/Batch hoặc tự đổi model.

Để so riêng tác dụng đổi model, dùng --pipeline v2.2: giữ trình tự ảnh trước URL, hai phép so tên riêng và prompt/giới hạn output 1.800 của bản cũ. Không thêm câu rút gọn giải thích. Chỉ JSON input được serialize gọn hơn, không thay đổi nội dung. Cache ảnh/HTML có thể dùng chung; OCR/kết quả model Luna tách riêng, không dùng kết quả OCR mini. So nhãn với v2.2 vẫn không phải đo accuracy vì chưa có ground truth độc lập.

--baseline-dir lấy chính xác selected_indices và row_id của v2.2; không dùng --first 50. Dùng output mới, không resume một run khác.

Chọn mẫu và tính giá offline:

```bash
/usr/bin/python3 tool/api_economy.py \
  --provider openai --model gpt-6-luna --pipeline v2.2 \
  --baseline-dir tool/outputs/pilot_v2_2 \
  --workers 3 --budget-usd 1 \
  --output-dir tool/outputs/luna_v2_2_pilot50
```

Chạy thật:

```bash
/usr/bin/python3 tool/api_economy.py \
  --provider openai --model gpt-6-luna --pipeline v2.2 \
  --baseline-dir tool/outputs/pilot_v2_2 \
  --workers 3 --budget-usd 1 \
  --output-dir tool/outputs/luna_v2_2_pilot50 --run
```

Thêm --resume vào cùng lệnh nếu cần tiếp tục. Nếu key không có quyền model, runner dừng với lỗi HTTP; không bịa nhãn. Dự toán quy đổi lượng token pilot cũ ~0,026 USD/50 record trước cache-write; không phải giá đo Luna, lượng token ảnh/output có thể khác. Cap 1 USD là dự phòng, không phải chi phí dự kiến phải dùng hết.

Kết quả mẫu: selected_rows.csv đúng 50 dòng chọn từ baseline, reviewed.csv đủ CSV gốc, results.jsonl, summary.json, usage.json. Khi dùng baseline-dir, first_rows.csv không được xuất để tránh nhầm với 50 dòng đầu.

Sau khi summary complete=true, tạo CSV + HTML so sánh:

```bash
/usr/bin/python3 tool/compare_local_runs.py
```

Mặc định đối chiếu outputs/pilot_v2_2 với outputs/luna_v2_2_pilot50, xuất outputs/comparison_v2_2_luna/comparison.csv, comparison.html, comparison_summary.json. Script từ chối nếu thiếu record hoặc SHA/row_id/selection khác nhau. Không gọi API. Muốn chọn đường dẫn khác dùng --baseline-dir, --candidate-dir, --output-dir, --left-label và --right-label.

Sau khi đánh giá Luna, muốn dùng pipeline tiết kiệm thì chạy run mới với --pipeline economy. Không trộn kết quả hai pipeline vào một journal; thay pipeline yêu cầu output-dir mới.

## Tăng xử lý song song ở local

Runner hỗ trợ 1–16 workers (mặc định vẫn 3), khuyến nghị thử 8 cho API trả phí. Một worker xử lý một record và có tối đa một lượt API đang chờ; các bước phụ thuộc trong cùng record vẫn theo thứ tự. Bounded executor chỉ giữ tối đa workers record đang chạy, không gửi cả 2.000 request cùng lúc. Ledger có khóa chung và reserve trước khi gọi, journal chỉ do luồng chính ghi.

Với run Luna dòng 2.001–4.000 đã khởi tạo trước bản tăng song song, code nhận diện chính xác hash bản tiền nhiệm chỉ khác cấu hình/runtime scheduling để cho resume. Các dependency quyết định phải giữ đúng hash; input/model/selection/policy vẫn phải giống. Không bỏ qua hash cho các bản code lạ. Run mới có thể đổi workers khi resume, không được hạ ngân sách.

Nếu tiến trình cũ đang chạy, Ctrl+C một lần rồi đợi lưu checkpoint/thoát. Không mở hai tiến trình trên cùng output. Tiếp tục:

```bash
/usr/bin/python3 tool/api_economy.py \
  --provider openai --model gpt-6-luna --pipeline v2.2 \
  --start-row 2001 --first 2000 --workers 8 --budget-usd 3 \
  --output-dir tool/outputs/luna_rows_2001_4000 --run --resume
```

Summary thêm workers, processed_this_session và rows_per_hour_this_session. Tăng workers không bảo đảm tốc độ tuyến tính vì còn quota API, mạng, tải trang và cache. Lỗi 429 vẫn dừng để kiểm tra quota; khi đó resume với workers=4 thay vì liên tục tăng. Không thay model hay bật retry ngầm. Request đang chạy lúc Ctrl+C vẫn có thể hoàn tất và tính phí, kết quả có thể chỉ vào cache rồi được dùng lại khi resume.
