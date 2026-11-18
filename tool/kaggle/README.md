# Chạy v2.2-fast2 trên GPU Kaggle, không dùng API

## Fast2: sửa tên tương đương và bài dài

- Giữ workers=4/batch=2 của fast1; thêm `qwen_policy.py`, cache model có namespace fast2. Backend dùng policy chặt hơn riêng cho Qwen; pipeline API local giữ hành vi cũ.
- Không duyệt chỉ vì model khai `translation`/`number_equivalent`. Tên số phải khớp qua chuẩn hóa có ngữ cảnh; bản dịch/alias cần ánh xạ cấu hình hoặc câu nguồn chứng minh. Biến thể OCR chỉ cho phép một ký tự khác trên tên dài nhiều từ, giữ số/mã định danh; không dùng similarity để duyệt cả câu.
- Prompt so tên gọn, phân biệt rõ entity là câu hỏi và observed_blocks mới là bằng chứng. Không đưa entity vào bước OCR.
- Kiểm từng ngữ cảnh ảnh trước, rồi mới kiểm các đoạn toàn bài nếu cần chứng minh vắng tên. Mỗi đoạn khoảng 2.200 ký tự kể cả overhead ước lượng; giới hạn token thật vẫn do processor kiểm tra. Vượt token thì chia nhỏ và thử lại, không cắt bỏ phần cuối.
- Đổi ID gửi model thành E0/E1… rồi ánh xạ về ID nguồn. Toàn bài không thể làm bằng chứng chính cho ảnh. `other_entity` cần tên có loại đối tượng trong heading/alt của ảnh, không chỉ tên khác trong đoạn văn.
- Tối đa 24 lượt model cho một trang (kể cả lần bị từ chối vì context). Chạm giới hạn, lỗi hoặc thiếu phạm vi kiểm tra => trống. Nếu ngữ cảnh ảnh đã chưa rõ hoặc nguồn bị cắt, bỏ các lượt quét toàn bài không thể giúp kết luận an toàn.
- `checks.page_match.chunk_audit` ghi số lượt, số block đã kiểm và lỗi từng đoạn. Lỗi từng đoạn nằm ở đây; không nhất thiết có trong `errors` cấp record.

Đánh đổi: một số bản dịch hợp lệ chưa khai báo sẽ để trống; bài dài có thể cần nhiều lượt model hơn, nên không cam kết nhanh hơn fast1. Trường hợp nhóm cần tất cả từ chỉ phạm vi trong bằng chứng được trích; cách diễn đạt khác có thể chưa được duyệt. Không dùng bộ test offline để suy ra accuracy thực tế.

## Chạy lại 50 dòng với fast2

1. Upload lại `tool/tool_kaggle_bundle.zip` vừa tạo lên Dataset Kaggle, cập nhật input notebook.
2. Import lại `tool/kaggle/approve_images.ipynb`, bật GPU và Internet, chạy các cell theo thứ tự.
3. Giữ `MODE="pilot"`, `RUN_NAME="pilot_gpu_v2_2_fast2"`, `RESUME=False`, `WORKERS=4`, `BATCH_SIZE=2`.
4. Kết quả: `/kaggle/working/tool/outputs/pilot_gpu_v2_2_fast2/`. Tải `summary.json`, `manifest.json`, `results.jsonl` để đo và so sánh. Chạy tiếp cùng bản code/cấu hình: `RESUME=True`; chạy thử mới: đổi `RUN_NAME`.

**Không resume output của bản code cũ vào fast2.** Không thêm `--no-url-first` khi đo cấu hình tối ưu.

```bash
python /kaggle/working/tool/kaggle/run_gpu.py \
  --input /kaggle/working/tool/input/general_10m_part_02_copy.csv \
  --work-dir /kaggle/working/tool --run-name pilot_gpu_v2_2_fast2 \
  --limit 50 --selection-file /kaggle/working/tool/pilot_v1_selection.json \
  --overrides /kaggle/working/tool/name_overrides.json \
  --workers 4 --batch-size 2 --url-first
```

- Tối đa 4 record đang chạy: tải ảnh/trang và suy luận được chồng lấp giữa các record. Không tạo 4 bản model.
- Một worker GPU gom yêu cầu cùng tác vụ/cùng loại đầu vào, tối đa batch 2, chờ tối đa 40 ms để gom. Padding bên trái; gắn mỗi kết quả đúng request và xử lý EOS riêng từng dòng.
- Giới hạn tổng token có padding + dự phòng output là 8.192 cho batch; vượt thì tách. Batch OOM tự giảm xuống 1 và thử lại, không tự hạ chất lượng ảnh. Nếu batch 1 vẫn OOM thì dừng, record lỗi còn pending.
- JSON đầu vào gọn hơn, yêu cầu giải thích ngắn, tối đa 512 output tokens. Chạm giới hạn output vẫn là lỗi chưa kiểm tra được, không thành `no`. Không cắt mất bằng chứng nguồn để vừa context.
- Dùng `logits_to_keep=1`, giữ allocator cache sau lần gọi bình thường; chỉ `empty_cache` sau OOM. Tham số logits được hỗ trợ trong [Transformers 4.57.1](https://huggingface.co/docs/transformers/v4.57.1/en/model_doc/qwen2_5_vl#transformers.Qwen2_5_VLForConditionalGeneration.forward).
- Checkpoint chỉ ghi từ luồng chính, CSV vẫn đúng thứ tự gốc; journal có thể khác thứ tự hoàn thành. Khi dừng vì lỗi, một số request đang chạy có thể chỉ được cache và record chưa ghi journal sẽ được chạy tiếp khi resume.

Trong `summary.json`, xem session mới nhất: `rows_per_hour_excluding_load`, `model_load_seconds`, `generation_seconds`, `preprocess_seconds`, `fetch_and_parse_seconds_sum`, `batch_histogram`, `oom_retries`. Thời gian tải/parse và chờ queue là tổng thời gian của nhiều yêu cầu chạy chồng lấp; không cộng chúng để suy ra thời gian thực. Tốc độ vẫn gồm I/O và checkpoint, chỉ loại thời gian nạp model/chuẩn bị ban đầu. Đánh giá sau đủ 50 dòng, không ngoại suy từ dòng đầu.

Để đo tác dụng riêng batching, chạy cùng fast2 với `--workers 1 --batch-size 1` và run-name khác. Cache nóng/lạnh phải được ghi nhận (xem `cache_hits`); không lấy lần dùng cache model so với lần suy luận mới. Đối chiếu nhãn bằng row_id như trước. Chưa có benchmark GPU thực tế của fast2 trên máy phát triển.

## Những gì đã có

- Backend `Qwen/Qwen2.5-VL-3B-Instruct`, chạy FP16 trên **một GPU**; không dùng API key, không có fallback sang API trả phí.
- Dùng chung code quyết định v2.2 với bản local: tách tên, kiểm chứng bằng chứng theo ID và giới hạn ngữ cảnh ảnh. Backend Qwen chạy trên GPU, không dùng OpenAI API. Mặc định kiểm tra **khớp URL trực tiếp trước** để tránh đọc ảnh không cần thiết; chỉ trả sớm khi khớp chắc theo rule. Có `--no-url-first` nếu muốn giữ thứ tự ảnh trước như pilot local.
- Chế độ thử đúng 50 record v1 (cùng thứ tự) hoặc `--all` cho mọi dòng approve trống.
- Checkpoint từng dòng, CSV/summary mỗi 100 dòng, gói resume mỗi 1.000 dòng và khi dừng bình thường. Đọc journal theo dòng; không giữ toàn bộ nội dung trang trong RAM/output.
- Tự dừng sau 8 giờ mặc định, trước khi bắt đầu dòng mới; đây không phải dự đoán thời gian xử lý toàn bộ. Request đang chạy có thể kéo dài thêm.
- HTTP cache giới hạn khoảng 1 GiB, dọn sau mỗi lần xuất định kỳ dưới khóa chống đọc/ghi cache đồng thời. Model weights/HF cache riêng, không đóng vào checkpoint.

Chọn model 3B để bắt đầu với bộ nhớ hạn chế. Mức phù hợp cho GPU 16 GB là **dự kiến theo kích thước model/cấu hình**, chưa benchmark trên tài khoản Kaggle của bạn. FP16 + SDPA tránh yêu cầu FlashAttention/BF16. Nếu có hai T4, bản đầu chỉ dùng GPU 0; chưa nhân đôi worker GPU.

## 1. Đưa lên Kaggle

1. Tạo **Dataset riêng tư**, upload bản mới nhất của `tool/tool_kaggle_bundle.zip` (có code v2.2 và selection manifest 50 dòng). Nếu đã tạo dataset từ zip cũ, thêm hoặc thay bằng zip mới rồi refresh input trong notebook. Gói có code và bản copy CSV, không có `.env`, key hoặc output pilot local.
2. Tạo Notebook, import `tool/kaggle/approve_images.ipynb`.
3. Add Input dataset vừa tạo. Trong Session options bật **GPU** và **Internet**. Internet cần để tải model và ảnh/trang nguồn.
4. Chạy các cell theo thứ tự. Notebook tự tìm dataset có `tool/kaggle/run_gpu.py`; nếu có nhiều dataset tương tự, điền `DATASET_TOOL` chính xác.

Nếu Kaggle chưa bung zip, notebook cũng hỗ trợ tìm file `tool_kaggle_bundle.zip` rồi bung code/data vào working. Không upload `.env`.

## 2. Thử GPU trước, rồi chạy toàn bộ

Notebook pilot mặc định dùng đúng 50 chỉ số và đúng thứ tự từ `tool/pilot_v1_selection.json`, tạo từ manifest pilot local. Script kiểm tra SHA-256 CSV; nếu CSV khác snapshot, nó dừng thay vì chọn nhầm record. Pilot vẫn chạy Qwen GPU nên nhãn có thể khác local OpenAI.

Trong cell cấu hình:

```python
MODE = "pilot"  # 50 dòng với Qwen GPU
RESUME = False
RUN_NAME = "pilot_gpu_v2_2_fast2"
MAX_HOURS = 8
```

Xem `summary.json` và một số nhãn/ảnh thực. Model nhỏ có thể đọc biển và hiểu tên khác OpenAI; các test logic local không chứng minh chất lượng model GPU.

Để chạy toàn bộ đổi:

```python
MODE = "full"
RUN_NAME = "full_gpu_fast2"
RESUME = False
```

Pilot GPU ghi vào `outputs/pilot_gpu_v2_2_fast2/`, full theo RUN_NAME (ví dụ `outputs/full_gpu_fast2/`), không dùng lại nhãn OpenAI hoặc nhãn pilot GPU tự động. Cache suy luận thành công có thể dùng chung nếu input/config/prompt/model revision giống nhau.

Lệnh tương đương (notebook đã chuẩn bị code và copy):

```bash
python /kaggle/working/tool/kaggle/run_gpu.py \
  --input /kaggle/working/tool/input/general_10m_part_02_copy.csv \
  --work-dir /kaggle/working/tool --run-name full_gpu --all --max-hours 8
```

Không cài lại torch/torchvision mặc định của Kaggle; requirements chỉ cài Transformers, Accelerate và Pillow. Nếu notebook đã import phiên bản Transformers khác trước cell cài đặt, restart session/kernel rồi chạy lại các cell. Backend chạy trong subprocess để tránh module import cũ trong notebook.

## 3. Output và tiếp tục phiên khác

Output tại `/kaggle/working/tool/outputs/full_gpu/`:

- `reviewed.csv`: đủ mọi dòng, nhãn mới cho các dòng đã xử lý; dòng chưa xử lý giữ nguyên.
- `results.jsonl`: quyết định, lý do, bằng chứng ngắn; append + fsync sau mỗi dòng.
- `manifest.json`: input hash, code hash, model revision đã tải, cấu hình và danh sách dòng.
- `summary.json`: completed/remaining, yes/no/trống, thống kê GPU từng phiên. `complete=false` nghĩa còn dòng chưa xử lý.
- `resume_bundle.zip`: bản copy input + journal + manifest + CSV + summary + overrides; không có trọng số model/cache.

**Trước khi mất phiên, tải `resume_bundle.zip` hoặc lưu output bằng cơ chế Save Version của Kaggle.** Checkpoint trên ổ working không tự đảm bảo tồn tại qua phiên mới. Notebook có cell tạo link download. Nếu phiên bị kill đột ngột, bundle gần nhất có thể chậm tối đa khoảng `bundle_every` dòng; journal trên ổ hiện tại mới hơn nếu còn truy cập được. Có thể giảm `--bundle-every 100` để giảm phần mất tiến độ, đổi lại tốn I/O hơn.

Trong cùng phiên: chạy lại cell lệnh với `RESUME=True` (không restore bundle cũ vào output mới hơn).

Ở phiên mới:

1. Add Input dataset code/data ban đầu **và** dataset/output phiên trước.
2. Đặt `PREVIOUS_CHECKPOINT` thành đường dẫn tới `resume_bundle.zip` đã lưu. Nếu Kaggle tự bung zip, đặt thành thư mục chứa `tool/input/` và `tool/outputs/`.
3. Giữ cùng MODE/model/cấu hình; đặt `RESUME=True` và chạy notebook.
4. Script xác minh input, code hash và model commit. Khác biệt sẽ dừng thay vì trộn kết quả của hai phiên bản.

Dòng trống đã ghi checkpoint do không kiểm tra được được coi là hoàn tất lần thử, không tự lặp vô hạn khi resume. Muốn thử lại nhóm lỗi cần run riêng sau khi xem nguyên nhân, tránh tiêu hết phiên GPU vì website chặn.

## 4. Bộ nhớ, lỗi và thời gian

- Mặc định ảnh tối đa 602.112 pixels ở processor, input tối đa 4.096 tokens, output tối đa 512 tokens. Prompt quá dài không bị cắt âm thầm để kết luận no: bước đó trả chưa kiểm tra được.
- Batch OOM: tự giảm batch và thử lại. Nếu batch 1 vẫn OOM/runtime GPU: dừng run, giữ dòng lỗi ở pending. Có thể thử run mới với `--max-pixels 401408 --batch-size 1`; đổi cấu hình không resume trộn với run cũ.
- JSON model không hợp schema, quote không tồn tại, trang bị chặn, mạng lỗi: giữ trống theo pipeline. Không tự bịa JSON bằng regex hay đổi lỗi thành no.
- Cần nhiều dung lượng hơn kích thước zip upload do weights, snapshot, CSV output và checkpoint. Script dừng khi còn dưới 1,5 GiB trống; con số này có thể chỉnh bằng `--min-free-gb`.
- Tốc độ phụ thuộc GPU, ảnh, website và số lượt model. Xem rows/hour từ pilot; **không bảo đảm 98 nghìn dòng xong trong một phiên**. Chạy nhiều phiên bằng resume nếu cần.

## 5. Kiểm tra đã thực hiện và giới hạn

Local kiểm tra được JSON/schema, luật quyết định, chọn dòng, xuất CSV, checkpoint/resume, archive không có secret và notebook syntax. Máy phát triển không có torch/CUDA, nên **chưa chạy inference thật trên GPU hoặc đo chất lượng Qwen**. Cần chạy lại 50 dòng trên Kaggle để đo hiệu quả và chất lượng của fast2.

Nguồn cấu hình model: [Qwen model card](https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct), [Transformers 4.57.1 Qwen2.5-VL](https://huggingface.co/docs/transformers/v4.57.1/en/model_doc/qwen2_5_vl). Hướng dẫn môi trường: [Kaggle Notebooks](https://www.kaggle.com/docs/notebooks).


### Chạy v2.2 với 50 dòng pilot cũ

Notebook đã tự truyền `--selection-file tool/pilot_v1_selection.json` cho MODE=`pilot`; không cần chỉnh lệnh. Selection manifest xác nhận đúng hash CSV và danh sách row index của pilot local, vì vậy phép so sánh dùng cùng record. Qwen GPU dùng cùng pipeline v2.2 nhưng model khác OpenAI, nên label có thể khác.

Đổi MODE thành `full` sau khi đã xem pilot nếu muốn chạy mọi dòng chưa có nhãn. Full dùng run riêng `full_gpu`; output pilot cũ không bị ghi lên. Sau khi cập nhật zip, dùng một run mới; không resume journal tạo từ phiên bản code/backend cũ.

## Chạy Qwen local và so với OpenAI v2.2

Có thể chạy `run_gpu.py` trực tiếp từ máy local có GPU NVIDIA và môi trường Python đã cài PyTorch bản CUDA tương thích. Cài phần phụ thuộc còn lại trong đúng môi trường đó:

```bash
pip install -r tool/kaggle/requirements.txt
```

Chạy đúng 50 record của pilot local v1, theo cùng thứ tự; `--no-url-first` giữ thứ tự kiểm ảnh/URL/trang giống runner local OpenAI:

```bash
python3 tool/kaggle/run_gpu.py \
  --input tool/input/general_10m_part_02_copy.csv \
  --work-dir tool --run-name pilot_qwen_v2_2 \
  --limit 50 --selection-file tool/pilot_v1_selection.json --no-url-first
```

Output sẽ ở `tool/outputs/pilot_qwen_v2_2/`. Nếu máy không có CUDA hoặc PyTorch CUDA thì lệnh dừng; model 3B chạy CPU sẽ rất chậm. Chạy tiếp khi tiến trình bị ngắt:

```bash
python3 tool/kaggle/run_gpu.py \
  --input tool/input/general_10m_part_02_copy.csv \
  --work-dir tool --run-name pilot_qwen_v2_2 \
  --limit 50 --selection-file tool/pilot_v1_selection.json --no-url-first --resume
```

Sau khi Qwen xử lý đủ 50 dòng, tạo CSV đối chiếu với OpenAI v2.2:

```bash
python3 tool/kaggle/compare_runs.py
```

Mặc định script so `outputs/pilot_v2_2` với `outputs/pilot_qwen_v2_2`, xác minh SHA-256 và danh sách record giống nhau rồi xuất CSV + thống kê tại `tool/outputs/qwen_compare_v2_2/`. Tạo HTML có tên hai model:

```bash
python3 tool/render_comparison.py \
  tool/outputs/qwen_compare_v2_2/comparison_openai_qwen_v2_2.csv \
  --left-label "OpenAI v2.2" --right-label "Qwen v2.2"
```


## Chạy đúng 2.000 dòng đầu và thử batch 4

Notebook mới mặc định MODE="first", FIRST_ROWS=2000, RUN_NAME="qwen_fast2_first2000_b4", WORKERS=8, BATCH_SIZE=4, BATCH_TOKEN_BUDGET=12288, RESUME=False. Upload bundle và import notebook mới. Đây là cấu hình thử nghiệm chưa đo GPU thật; thiếu VRAM runner tự giảm batch, không đảm bảo nhanh hơn batch 2. Muốn cấu hình đã đo: WORKERS=4, BATCH_SIZE=2, BATCH_TOKEN_BUDGET=8192, tên run khác.

CLI: dùng `--first 2000 --workers 8 --batch-size 4 --batch-token-budget 12288`, không dùng --selection-file/--limit/--all cùng --first. --first đếm dòng dữ liệu trước khi bỏ nhãn cũ, không lấy bù dòng sau. Model vẫn chỉ nạp một bản trên GPU 0, hai T4 chưa được dùng đồng thời. max-hours=8 có checkpoint nếu chưa hoàn tất. Resume giữ đúng tên run và cấu hình đã khởi tạo, kể cả khi batch thực tế đã tự giảm; batch có thể thử giảm lại ở phiên mới. Do code runner đã đổi, không resume run tạo bằng bundle trước lần cập nhật này.

Xem batch_histogram và effective_batch_size trong summary để biết có thực sự chạy batch 4. Tăng workers chủ yếu giúp gom đủ request và chồng lấp mạng, không tự làm GPU nhanh gấp đôi. Lần thử 2.000 có thể tốn hơn một phiên 8 giờ.
