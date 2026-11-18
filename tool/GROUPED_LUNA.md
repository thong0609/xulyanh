# Luna theo nhóm ảnh + địa chỉ chi nhánh + Batch API

Runner mới: `tool/run_grouped_luna.py`. Mặc định dùng **OpenAI Batch API** (`--execution batch`) với `gpt-6-luna`, key OPENAI_API_KEY đã có trong tool/.env; vẫn OCR ảnh. Không thay runner per-record cũ, không tự ghi nhãn vào CSV chính và không chạm file done/.

## Quy tắc

1. Gom toàn bộ record cùng image_url, giữ thứ tự CSV. Nếu có nhiều yes sẵn, yes đầu tiên thắng, các record khác thành no. Nếu tất cả đã no, không gọi model.
2. Với record còn trống, chuẩn hóa tên và tạo array địa chỉ có ID ngắn R0/R1…: số nhà, đường, tên chi nhánh/mall, phường, quận/huyện, tỉnh/thành.
3. Nếu là cùng thương hiệu nhưng khác địa chỉ, KHÔNG duyệt sớm chỉ vì URL có thương hiệu. Đọc OCR một lần và kiểm các ngữ cảnh gắn với đúng ảnh trong nguồn trước.
4. Điểm bằng chứng: số nhà + đường khớp 40; tên chi nhánh/mall cụ thể 30; đường đơn lẻ 12; quận/huyện 2, phường 1, tỉnh/thành 3. Mâu thuẫn số nhà hoặc tỉnh/thành rõ ràng loại bằng chứng địa chỉ đó. Chỉ chốt chi nhánh khi có bằng chứng mạnh, duy nhất trong ngữ cảnh ảnh. Bằng chứng về thương hiệu/entity cũng phải được xác minh.
5. Không lấy số lần tên địa chỉ xuất hiện trên toàn trang làm độ tin cậy. Nếu một đoạn liệt kê nhiều địa chỉ ứng viên, hoặc nhiều lần xuất hiện ảnh dẫn tới các chi nhánh khác nhau, coi là chưa phân biệt được. Phần text toàn trang không gắn với ảnh không được dùng để chốt địa chỉ.
6. Địa chỉ xác định rõ => GROUP_ADDRESS_MATCH, branch_identified=true. Nếu chỉ xác minh thương hiệu chung => record khớp đầu tiên đại diện ảnh nhận yes, phần còn lại no, lý do GROUP_BRAND_FALLBACK và branch_identified=false. Đây là rule người dùng đã chọn, không phải khẳng định ảnh đúng chi nhánh đó.
7. Gom page_url cùng nguồn, bỏ riêng tham số theo dõi utm_* và srsltid; không bỏ query mang nội dung như id. Mỗi nguồn kiểm chung array ứng viên trong một lượt model nếu code chưa giải quyết được. Gửi các ID bằng chứng, kiểm tên quan sát có thật trong ngữ cảnh, không tin ID/tên bịa.
8. Một kết quả no chỉ loại các ứng viên có bằng chứng đối tượng khác. Không tự suy no cho phần còn lại. Không tìm đủ bằng chứng giữ trống. Khi có yes, toàn bộ record khác của nhóm ảnh thành no theo rule một ảnh/một record.

Các điểm số và việc tách địa chỉ là heuristic, chưa giải quyết mọi cách viết địa chỉ hoặc alias. Model chưa được benchmark thật với prompt grouped/address mới. Không khẳng định mọi yes là đúng địa điểm; kiểm reason/branch_identified để phân biệt đại diện thương hiệu và chi nhánh đã chứng minh.

## Chạy

Xem phạm vi offline (không đọc key, không gọi API):

```bash
/usr/bin/python3 tool/run_grouped_luna.py --first 2000 \
  --output-dir tool/outputs/preview_grouped_batch_2000
```

Chạy thật với output mới:

```bash
/usr/bin/python3 tool/run_grouped_luna.py \
  --execution batch --first 2000 --workers 8 --budget-usd 3 \
  --output-dir tool/outputs/luna_grouped_batch_2000 --run --watch
```

Lấy CSV chính hiện tại ở gốc dự án, copy thành input_snapshot.csv trong output. **2.000 dòng là phạm vi khởi đầu để chọn ảnh**; sau đó đưa TẤT CẢ record cùng ảnh trong CSV vào xử lý, kể cả nằm ngoài 2.000 dòng. Preview lúc triển khai: 2.000 seed rows mở rộng thành 3.133 record thuộc 1.812 nhóm; 341 nhóm đã có yes. Số này có thể thay đổi nếu bạn tiếp tục sửa CSV chính.

Muốn chọn phạm vi khác dùng --start-row và --first, hoặc --input để chọn CSV. Không dùng baseline-dir/per-record output. Resume bằng đúng lệnh cũ thêm --resume; dùng snapshot trong output, không tự lấy lại nhãn từ CSV chính đã thay đổi. Có thể đổi workers hoặc tăng budget; đổi policy/code/selection phải dùng run mới.

Ngân sách dùng reservation có khóa. Batch tính 50% đơn giá Standard cho cùng lượng token; Luna input vẫn nhân bảo thủ 1,25 lần để bao phủ cache-write. Đây là giới hạn bảo thủ của runner, không phải thiết lập hard cap cho tài khoản OpenAI. Hết ngân sách/quota/lỗi API hệ thống sẽ dừng, group chưa ghi còn pending. Mỗi worker sở hữu một nhóm, không có hai worker duyệt hai yes trong cùng nhóm. Model cache/ảnh HTML được tái sử dụng; không xóa usage/cache nếu cần resume.

Output: reviewed.csv đầy đủ snapshot với nhãn mới, selected_rows.csv cho toàn bộ nhóm được chọn, results.jsonl, summary.json, manifest.json và thư mục batch/ (state.json, request, answer và file JSONL gốc). Chế độ Standard vẫn có usage.json riêng. Các record ngoài nhóm giữ nguyên. source CSV chính không bị sửa bởi runner; cần đối chiếu trước khi ghép kết quả lại vào file đang duyệt thủ công.

Khi cần xem vì sao chọn một chi nhánh, đọc checks.group_decision.proof.address_candidates, address_audit, branch_identified. Dự phòng brand không chứng minh địa chỉ, nhưng vẫn chọn một yes đại diện theo yêu cầu người dùng.

Đã kiểm thử offline: first yes thắng kể cả nhiều yes, Juno không cần đúng chi nhánh khi chỉ biết thương hiệu, địa chỉ đúng ưu tiên ứng viên phía sau, số nhà mâu thuẫn, directory nhiều địa chỉ, ngữ cảnh ảnh mâu thuẫn, gộp nguồn bỏ tracking, no không lan cả nhóm, mở rộng scope, checkpoint/resume và giữ nguyên CSV nguồn. Chưa gọi API trả phí khi setup.

## Batch API: chạy và tiếp tục

OCR ảnh là đợt đầu. Với mỗi nhóm cần OCR, chỉ sau khi nhận response completed, ghép đúng custom_id và kiểm JSON/schema hợp lệ mới cho tạo lượt kiểm nguồn. no_text/unreadable là response hợp lệ và được đi tiếp; ảnh lỗi, OCR lỗi hoặc JSON sai giữ trống các ứng viên chưa duyệt, không gọi nguồn cho nhóm đó. Nhóm giải quyết sớm bằng nhãn có sẵn/URL không cần OCR. Khi nhận OCR, code chạy lại các bước bằng kết quả đã lưu và gửi đợt kiểm nguồn cần thiết. Không gửi lại các lượt có kết quả. Nhóm có nhiều nguồn có thể cần nhiều đợt; mỗi đợt có completion_window=24h, tổng thời gian toàn pipeline có thể dài hơn. Batch là lựa chọn giảm phí; không đảm bảo trả ngay như API thường.

`--watch` tự chờ, kiểm tra mỗi 30 giây và chuyển bước tiếp theo. Có thể Ctrl+C/tắt máy; batch đã gửi tiếp tục trên OpenAI. Chạy tiếp **đúng lệnh cũ, thêm --resume**:

```bash
/usr/bin/python3 tool/run_grouped_luna.py \
  --execution batch --first 2000 --workers 8 --budget-usd 3 \
  --output-dir tool/outputs/luna_grouped_batch_2000 --run --watch --resume
```

Bỏ `--watch` nếu chỉ muốn gửi/kiểm tra một lần rồi thoát; `WAITING_BATCH` và `complete=false` là đang chờ, chưa xong. Chạy lại với `--resume` để lấy kết quả/gửi bước sau. Không xóa output hoặc đổi tên thư mục khi đang có batch chờ.

- `--batch-requests 500 --batch-mb 50`: tối đa mỗi file; runner chia nhỏ nếu vượt. Mỗi thời điểm theo dõi một batch. workers chỉ song song tải ảnh/nguồn và chuẩn bị nhóm, không quyết định số lượt model chạy trên OpenAI.
- `summary.json`: completed/remaining/counts, billing_mode=batch, charged_or_reserved_usd, batch_jobs chứa batch ID/trạng thái.
- Budget được giữ chỗ trước khi thêm request. Lỗi không có usage vẫn giữ reservation; batch_expired chưa chạy tính 0 và để lỗi kiểm tra, không gán no. Lỗi quyền/quota/model hoặc thiếu/sai custom_id dừng để đối chiếu.
- Nếu mất mạng đúng lúc tạo batch, lần resume tìm batch qua metadata trước. Không tìm thấy sẽ dừng SUBMISSION_UNCERTAIN; kiểm dashboard để tránh gửi trùng tính phí.
- Code chỉ upload Files và gọi /batches cho suy luận. Không chuyển âm thầm sang Standard. `--execution standard` là lựa chọn rõ ràng nếu muốn dùng runner đồng bộ cũ, phải dùng output mới.
- Run grouped/Standard cũ không dùng chung output với Batch. Snapshot CSV chính và done/ không bị sửa.

Tài liệu API: https://developers.openai.com/api/docs/guides/batch

Kiểm thử bổ sung bằng API giả lập: hai giai đoạn OCR/nguồn, kết quả khác thứ tự, giới hạn ngân sách, chia file, resume không tạo batch trùng, khôi phục khi mất phản hồi tạo batch, ID lạ, batch hết hạn và giữ nguyên CSV nguồn. Chưa gửi batch thật hoặc gọi model trả phí khi triển khai.

## Chạy lại đúng pilot 50 Luna v2.2 cũ

Lệnh mặc định dùng CSV chính hiện tại. Muốn đối chiếu pilot cũ phải dùng bản snapshot gốc trong tool/input/ và danh sách selected_indices từ manifest cũ; không dùng --first 50 vì pilot cũ được chọn rải rác. --baseline-dir chỉ lấy phạm vi/kiểm identity, không lấy nhãn cũ làm nhãn đầu vào.

```bash
/usr/bin/python3 tool/run_grouped_luna.py \
  --execution batch --input tool/input/general_10m_part_02_copy.csv \
  --baseline-dir tool/outputs/luna_v2_2_pilot50 \
  --output-dir tool/outputs/luna_grouped_batch_pilot50 \
  --budget-usd 1 --run --watch
```

50 record pilot mở rộng thành 85 record thuộc 50 nhóm ảnh. Phải xử lý hết 85 record trước khi so sánh; bảng so sánh chỉ chứa 50 record pilot. Đây là so sánh pipeline grouped/address mới với pipeline Luna v2.2 cũ, không phải chỉ đổi cách thanh toán Batch.

```bash
/usr/bin/python3 tool/compare_local_runs.py \
  --baseline-dir tool/outputs/luna_v2_2_pilot50 \
  --candidate-dir tool/outputs/luna_grouped_batch_pilot50 \
  --output-dir tool/outputs/comparison_luna_v2_2_grouped_batch_pilot50 \
  --baseline-rows --left-label 'Luna v2.2' --right-label 'Luna grouped Batch'
```

Output comparison.csv, comparison.html và comparison_summary.json cạnh nhau trong thư mục comparison. Dùng --resume với đúng lệnh runner nếu tắt giữa chừng. Tạo preview không cần key bằng cách bỏ --run --watch.

## Bản Standard riêng: cần kết quả sớm

`tool/run_grouped_luna_standard.py` là bản copy runner riêng, chỉ hỗ trợ Standard API. Mặc định 8 nhóm song song; từng nhóm vẫn phải nhận OCR hợp lệ rồi mới kiểm nguồn. Không sửa code/checkpoint của Batch đang chạy; output Standard riêng. Batch đã gửi vẫn tiếp tục trên OpenAI; chạy thêm Standard có thể phát sinh phí cho cả hai run.

Chạy đúng pilot cũ (50 seed mở rộng 85 record):

```bash
/usr/bin/python3 tool/run_grouped_luna_standard.py \
  --input tool/input/general_10m_part_02_copy.csv \
  --baseline-dir tool/outputs/luna_v2_2_pilot50 \
  --output-dir tool/outputs/luna_grouped_standard_pilot50 \
  --workers 8 --budget-usd 1 --run
```

Resume thêm --resume. Không dùng --watch trong bản Standard. Kết quả ra theo nhóm, không phải chờ một batch hoàn tất. Không cam kết số phút vì còn phụ thuộc tải nguồn và quota API. Thiết lập chỉ chạy preview offline, chưa gọi API trả phí.

So sánh:

```bash
/usr/bin/python3 tool/compare_local_runs.py \
  --baseline-dir tool/outputs/luna_v2_2_pilot50 \
  --candidate-dir tool/outputs/luna_grouped_standard_pilot50 \
  --output-dir tool/outputs/comparison_luna_v2_2_grouped_standard_pilot50 \
  --baseline-rows --left-label 'Luna v2.2' --right-label 'Luna grouped Standard'
```

## Standard: 2.000 dòng đầu chưa có nhãn trong CSV chính

```bash
/usr/bin/python3 tool/run_grouped_luna_standard.py \
  --input general_10m_part_02.csv --unlabeled-only --first 2000 \
  --output-dir tool/outputs/luna_grouped_standard_unlabeled2000 \
  --workers 8 --budget-usd 3 --run
```

--unlabeled-only chọn tối đa 2.000 dòng approve trống theo thứ tự CSV (bỏ qua các dòng đã gán nhãn), rồi gom tất cả record cùng image_url trong toàn snapshot, kể cả ở ngoài phạm vi seed và kể cả đã có yes/no. Không dùng cùng --baseline-dir. Số record thực xử lý có thể lớn hơn 2.000; số ảnh có thể nhỏ hơn do seed trùng ảnh. Không sửa CSV chính. Preview bằng cách bỏ --run; resume thêm --resume.

### Standard: lỗi Unicode và resume

Run unlabeled2000 đã dừng ở 2.626/3.086 record với INTERNAL_ERROR: UnicodeEncodeError, không phải giới hạn ngân sách (charged_or_reserved_usd=0.406827, budget=3). Log cũ chỉ lưu loại exception nên chưa xác định chính xác URL/redirect hay response model gây lỗi. Bản Standard bổ sung guard cho cả hai bước: FETCH_URL_ENCODING_ERROR hoặc MODEL_UNICODE_ENCODING_ERROR được ghi như lỗi kiểm tra, không chuyển thành no và không dừng cả run. Không sửa shared code của Batch.

standard_runtime_compatibility.json pin đúng cặp hash trước/sau của bản sửa runtime này, chỉ cho resume khi selection/input/model/policy/config còn khớp. Không bỏ kiểm hash tổng quát. Manifest nâng cấp được ghi khi người dùng chạy --run --resume; runtime_upgrade.json lưu dấu vết. Backup runner trước sửa nằm trong tool/backups/run_grouped_luna_standard_before_unicode_guard.py. Đã kiểm tra resume offline thành công; chưa gọi API trả phí khi sửa.

## Policy hiện tại: user-rules-v4

Mặc định mới của cả Standard và Batch đã thay các rule để blank bằng quyết định yes/no theo yêu cầu cập nhật. Dùng output mới; xem toàn bộ thứ tự quyết định, các mã reason và lệnh tại [GROUPED_USER_RULES_V4.md](GROUPED_USER_RULES_V4.md). Các phần trước trong tài liệu mô tả policy legacy và các run lịch sử.
