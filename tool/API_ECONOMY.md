# API local tiết kiệm — 2.000 dòng đầu

Runner mới `tool/api_economy.py`, dùng gpt-5.4-mini qua Responses API trực tiếp. Không dùng Batch API trong bản này; không áp dụng giảm giá Batch vào dự toán. Không thay đổi bản Kaggle. CSV nguồn/baseline giữ nguyên, chỉ ghi trong tool/outputs.

Lấy 2.000 dòng dữ liệu đầu (không tính header), rồi bỏ dòng đã có approve; không lấy bù từ dòng 2.001 trở đi. Snapshot hiện tại có 2.000 dòng chưa nhãn, đều là Trường mầm non & nhà trẻ. Có 367 dòng khớp URL bằng rule và 1.633 dòng cần kiểm tiếp; nhóm sau có 1.471 URL ảnh khác nhau. URL khác nhau nhưng trả cùng ảnh JPEG còn có thể dùng chung OCR sau khi tải.

Tối ưu:
- URL rule trước tải ảnh, bỏ API cho 367 dòng khớp.
- Tên OCR rõ và 2–3 dòng biển hiệu liền nhau khớp thì duyệt bằng code.
- Gộp so tên OCR và hai URL trong một lượt model, thay cho hai lượt riêng. Giữ provenance trong combined_name_match; đây là thay đổi prompt cần xem chất lượng sau chạy.
- Dùng chung cache OCR giữa entity khác nhau nếu ảnh giống; khóa các request trùng giữa workers. Tái sử dụng cache OCR local cũ khi đúng prompt/input/model; các quyết định so tên mới có cache riêng.
- JSON đầu vào gọn; yêu cầu giải thích ngắn; output giới hạn 900 tokens. Vẫn giữ chất lượng ảnh và toàn bộ dữ liệu bằng chứng gửi bước page như v2.2. Lượt chạm giới hạn output là lỗi chưa kiểm tra được, không kết luận no. Không tự retry thêm token gây phí.
- Giữ validator bằng chứng của API v2.2. Không áp dụng policy Qwen fast2 vốn có đánh đổi nhiều nhãn trống. Lỗ hổng quan hệ dịch/OCR do model khai trong validator v2.2 vẫn là giới hạn cần kiểm mẫu, không tuyên bố đã sửa chất lượng đó ở bản tiết kiệm.

## Chi phí dự kiến, không phải báo giá cố định

Pilot cũ: 0,200469 USD / 50 = 0,00400938 USD/record (cách tính bảo thủ không trừ cached input). Ngoại suy 2.000 record với code cũ: 8,019 USD. Bản mới bỏ API cho 367 URL-hit. Áp dụng các mức chi phí còn lại 60%, 100%, 150% so với đơn giá bình quân pilot vào 1.633 record còn lại, được 3,928 / 6,547 / 9,821 USD. Đây là kịch bản giả định; mẫu đầu CSV toàn trường mầm non nên khác pilot hỗn hợp. Chưa chạy API tối ưu để đo; không khẳng định tiết kiệm 50% hay chắc hoàn thành dưới 10 USD.

Giá Standard đã đối chiếu [OpenAI GPT-5.4 mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini): input 0,75 / cached input 0,075 / output 4,50 USD mỗi triệu token. Ledger hiện giữ cách tính bảo thủ toàn input theo giá thường; usage.json lưu cached_tokens để đối chiếu. Không cộng giảm giá cache và không đổi model trong dự toán.

Ngân sách mặc định 10 USD. Dừng trước cấp request khi phần dự phòng không đủ; có thể dừng dù tổng chi phí thực còn dưới ngưỡng vì dự phòng token/ảnh bảo thủ. Ngân sách không bảo đảm xử lý đủ 2.000 dòng. Chi phí này chỉ là model API, không gồm thuế/phí tài khoản nếu có.

## Lệnh chạy từ thư mục dự án

Xem dự toán/chọn dòng offline (không đọc key, không gọi mạng):

```bash
/usr/bin/python3 tool/api_economy.py --first 2000 --budget-usd 10
```

Sau khi tự kiểm dự toán, dùng key đã có trong tool/.env và môi trường Python có Pillow:

```bash
/usr/bin/python3 tool/api_economy.py --first 2000 --budget-usd 10 --workers 3 --run
```

Tiếp tục sau khi dừng:

```bash
/usr/bin/python3 tool/api_economy.py --first 2000 --budget-usd 10 --workers 3 --run --resume
```

Nếu đã hết ngân sách, resume với budget-usd cao hơn (ví dụ 12) mới cấp tiếp request; các cấu hình/input/code khác phải giữ nguyên. Dùng Python môi trường của bạn nếu /usr/bin/python3 không có Pillow. Script pilot cũ vẫn giới hạn 50 dòng; lệnh 2.000 dòng là api_economy.py.

Output: tool/outputs/api_economy_first_2000/:
- cost_estimate.json và selection_preview.json: tạo offline, không phải kết quả approve.
- manifest.json, results.jsonl, usage.json: checkpoint và token/chi phí.
- first_rows.csv: đúng 2.000 dòng đầu, nhãn mới cho record đã hoàn tất.
- reviewed.csv: đủ 98.049 dòng, chỉ sửa approve các record đã chọn và hoàn tất.
- summary.json: completed/remaining, yes/no/trống, stop_reason, chi phí; xuất CSV mỗi 25 record và khi kết thúc/ngắt bình thường.

Record hết ngân sách không được ghi hoàn tất; resume sẽ chạy tiếp. Record thực sự kiểm không xong do nguồn/model đã ghi trống thì được tính hoàn tất lần thử, không tự chạy lại vô hạn. Khi ngắt, các request đang chạy được chờ hoàn tất tính phí; có thể chỉ được cache và chưa ghi journal, sẽ xử lý lại qua cache khi resume. Không xoá cache/usage khi tiếp tục run.

## Chọn Gemini / đổi model

Runner hiện hỗ trợ `--provider openai|gemini --model MODEL_ID`. Hướng dẫn key, lệnh thử Gemini 2.5/3.5, giá Standard theo provider, giới hạn quota và output riêng tại [LOCAL_MODELS.md](LOCAL_MODELS.md). Vẫn OCR và kiểm nguồn. Không resume output từ phiên bản api-economy-v1 bằng code mới; tạo run riêng.
