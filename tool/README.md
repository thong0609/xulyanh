# Tool duyệt ảnh — pilot local v2.2, cùng 50 record cũ

Chạy trên bản copy `tool/input/general_10m_part_02_copy.csv`. Tool chỉ nhận input trong `tool/input/`, output trong `tool/outputs/`. Không ghi CSV chính, không sử dụng `done/` và `thu_nghiem/`. `mo_ta` không được gửi vào model.

## Chuẩn bị API key

Mở `tool/.env`, điền tại máy local:

```dotenv
OPENAI_API_KEY=YOUR_ACTUAL_KEY
```

Không cần gửi key vào chat. Model được cố định là `gpt-5.4-mini`, endpoint OpenAI Responses API. Chưa có key vẫn chạy được chế độ offline và bộ test.

## Chạy từ thư mục dự án

```bash
# Chuẩn bị mẫu, không truy cập mạng và không tính phí:
python3 tool/approve_tool.py --baseline-dir tool/outputs/pilot_v1 --limit 50

# Chỉ chạy lệnh này khi đã điền key và muốn bắt đầu pilot có phí:
python3 tool/approve_tool.py --baseline-dir tool/outputs/pilot_v1 --limit 50 --workers 3 --budget-usd 0.50 --run

# Tiếp tục run bị ngắt, không xử lý lại dòng đã ghi checkpoint:
python3 tool/approve_tool.py --baseline-dir tool/outputs/pilot_v1 --limit 50 --workers 3 --budget-usd 0.50 --run --resume

# Xem CSV kết quả bằng giao diện hiện có:
python3 review_server.py tool/outputs/pilot_v2_2/pilot_50.csv --port 8001
```

Các lệnh trên lấy chính xác 50 dòng và thứ tự từ manifest v1, kiểm tra cùng hash input và row_id. Nếu bỏ `--baseline-dir`, tool chọn mẫu bằng seed; không dùng cách đó khi so v1/v2. File `sample_preview.json` chứa danh sách được chọn. Tham số seed, input, limit và overrides phải giữ nguyên khi resume. Bản pilot giới hạn tối đa 50 dòng và 0,50 USD; chưa có chế độ chạy toàn bộ CSV.

Run tồn tại sẽ bị từ chối nếu không có `--resume`. Dòng đã hoàn tất nhưng để trống do lỗi vẫn là một checkpoint hoàn tất; resume không tự gọi lại các dòng này. Muốn thử lại dùng `--output-dir tool/outputs/pilot_retry`; đây là một run mới với ngân sách riêng. Ảnh/HTML thô dùng lại cache v1; kết quả model v2.2 có namespace mới và được gọi lại. Cache model chỉ dùng lại trong cùng phiên bản/prompt/input. Resume còn kiểm tra hash code và baseline.

## Kết quả

Baseline v1 giữ ở `tool/outputs/pilot_v1/`; bản `outputs/pilot/` ban đầu vẫn giữ nguyên. Code cũ ở `tool/versions/v1/` và `tool/versions/v2/`. Output v2 cũ vẫn ở `tool/outputs/pilot_v2/`. Kết quả mới trong `tool/outputs/pilot_v2_2/`:

- `sample_preview.json`: 50 dòng chọn và hồ sơ tên (tạo khi chạy offline).
- `manifest.json`: phiên bản, hash input, danh sách dòng, ngân sách, hash overrides.
- `results.jsonl`: kết quả và bằng chứng mỗi dòng, ghi ngay khi xử lý xong để resume.
- `usage.json`: token do API báo và chi phí dự phòng của request chưa xác nhận được tính phí.
- `summary.json`: tổng yes/no/trống trên mẫu, số request và chi phí.
- `pilot_50.csv`: đúng 50 record được chạy, có nhãn approve; chỉ tạo sau khi chạy thật.
- `comparison_v1_v2.csv`: nhãn, lý do v1/v2, số thứ tự mẫu, quan hệ và lỗi mới; tạo khi có baseline.
- `reviewed.csv`: giữ **toàn bộ** dòng của bản copy, chỉ cập nhật approve của mẫu đã chạy. Không xuất nhãn giả khi chạy offline.

`yes`: tên riêng trên ảnh hoặc URL khớp, hoặc ảnh thuộc mục entity trong nguồn. `no`: xác định ảnh thuộc mục entity khác, hoặc hoàn tất đọc ảnh/URL/trang nhưng không tìm thấy tên. Không thể hoàn tất kiểm tra → trống. Tên riêng được phép khớp dù khác địa điểm/chi nhánh. Với nhóm như khu tập thể/nhà kính, nguồn phải chứng minh loại hình và phạm vi của thành viên; chỉ cùng chủ đề hoặc thiếu chứng cứ thuộc khu cụ thể thì để trống. Chi tiết và ví dụ Kim Liên/nhà kính ở [mục 8 của plan](PLAN_AUTO_APPROVE.md#8-cải-tiến-v2--sửa-lỗi-pilot-và-bổ-sung-quan-hệ-ngữ-nghĩa).

Tên số có chuẩn hóa (Tám ↔ 8, Mười Chín Tháng Năm ↔ 19/5). Khác số như 19/6 không được khớp trực tiếp. URL có số trong ID/ngày đăng không tự được coi là tên. Tên Anh–Việt và sai khác chữ được đưa sang model so mềm; điểm difflib chỉ ghi chẩn đoán, không tự quyết định nhãn.

Để thêm tên tương đương đã biết, sửa `tool/name_overrides.json` theo entity_id:

```json
{
  "ENTITY_ID_HERE": {
    "core_name": "Hoa Hồng",
    "aliases": ["Rose Preschool"]
  }
}
```

## Ngân sách và xử lý lỗi

Giá cấu hình: input 0,75 USD/triệu token, output 4,50 USD/triệu token; chưa trừ giảm giá cached input. Không dùng công cụ web search trả phí của API. Mỗi request dự phòng chi phí text, ảnh và tối đa 1.800 output token dưới lock chung cho 3 workers. Sau khi có usage, thay dự phòng bằng chi phí tính từ usage. Request lỗi hoặc không có usage giữ nguyên dự phòng vì có thể đã được tính phí. Dừng cấp request khi phần ngân sách còn lại không đủ; các URL khớp trực tiếp vẫn được duyệt mà không gọi model.

Đây là bộ giới hạn dựa trên giá/token và ước lượng bảo thủ, không phải giới hạn thanh toán của nhà cung cấp. Usage và giá thực tế trên tài khoản API là căn cứ đối chiếu. 0,50 USD là trần pilot được đề xuất, không phải chi phí mặc định của 50 dòng.

HTTP tải ảnh/trang thử lại tối đa 2 lần cho lỗi tạm thời. API model không tự thử lại request lỗi ở bản đầu để tránh phát sinh chi phí khó xác định. HTTP timeout 20 giây; API timeout 90 giây. Ảnh gửi model được giữ tối đa 1.600 px mỗi chiều, detail high. Biển nhỏ/mờ có thể chưa đọc được và sẽ chuyển bước tiếp theo hoặc để trống.

Chưa chạy browser JavaScript; trang chỉ có khung, CAPTCHA, paywall rõ hoặc nội dung bị cắt không được dùng để kết luận không có tên. Parser đọc src/srcset/lazy-src/content và link ảnh gốc; hỗ trợ chuẩn hóa Unicode, http/https, một số wrapper Cloudflare/Cloudinary. CDN khác chưa ghép được thì chuyển chưa xác định. Trang tĩnh có cấu trúc lạ vẫn có thể bị trích xuất sai; cần xem bằng chứng của pilot trước khi mở rộng.

## Môi trường và kiểm tra

Tool dùng Python 3.10+ và Pillow; HTTP, HTML, so chuỗi và đọc .env dùng thư viện chuẩn. Máy hiện tại chạy được bằng `python3` với Pillow đã có; không cần dùng `.venv` tạo dở trước đó.

Nếu chạy trên máy chưa có Pillow:

```bash
python3 -m pip install -r tool/requirements-approve.txt
```

Chạy kiểm tra không cần API/mạng:

```bash
python3 -m unittest discover -s tool/tests -v
```

Bộ test có luồng 50 dòng với model/HTTP giả lập, xác nhận nhãn, resume, budget và bảo toàn CSV. Đây không phải phép đo chất lượng VLM trên ảnh thật.

Ở môi trường agent hiện tại, DNS tới `api.openai.com` và PyPI chưa hoạt động. Nếu vẫn gặp lỗi này khi chạy, cần chạy script từ terminal local có mạng. Không coi việc offline test thành công là API đã kết nối thành công.

## GPU Kaggle

Đã bổ sung backend Qwen local, runner toàn bộ CSV và notebook trong [kaggle/README.md](kaggle/README.md). Upload `tool/tool_kaggle_bundle.zip` làm dataset riêng tư và import `tool/kaggle/approve_images.ipynb`. Không cần API key; output/checkpoint của GPU tách riêng với pilot local. Chưa benchmark inference GPU thật trên máy phát triển.


## Bản sửa bằng chứng v2.1

Model chọn ID của đoạn có sẵn thay vì tự viết câu trích. Code lấy nguyên văn, lưu `evidence_blocks`/`supporting_evidence_blocks` kèm ID, field và context; từ chối ID không tồn tại, trùng hoặc sai mục ảnh. Alias giữa hai tên khác nhau cần tên được cung cấp hoặc nguồn xác nhận trực tiếp. Xem mục 9 trong plan để biết input/output và giới hạn. Giữ namespace/output riêng cho v2.1, không resume vào thư mục v2.


## Bản sửa tên và ngữ cảnh v2.2

Xem mục 10 của plan: tách thêm loại hình, nhận tên trải trên các dòng OCR liền nhau, chặn từ chung thiếu nhi không có ngữ cảnh công viên, bỏ mục lục và chặn ngữ cảnh ảnh vượt qua heading kế tiếp. Giữ ID bằng chứng của v2.1. Output v2.1 cũ vẫn nằm ở `tool/outputs/pilot_v2_1/`; lần chạy mới dùng `tool/outputs/pilot_v2_2/`.

Sau khi chạy xong, tạo HTML cho kết quả mới:

```bash
python3 tool/render_comparison.py tool/outputs/pilot_v2_2/comparison_v1_v2.csv
```
