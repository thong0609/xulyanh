# Pipeline user-rules-v4

Mặc định mới cho run_grouped_luna_standard.py và run_grouped_luna.py (Batch). Legacy nằm nguyên trong grouped_pipeline.py; bản mới nằm trong grouped_user_rules.py. Không sửa nhãn/output lịch sử khi cập nhật code.

## Quy tắc mới

| Tình huống đã kiểm tra | Nhãn |
|---|---|
| TARGET_IMAGE_CONTEXT_NOT_FOUND: không tìm được đúng ảnh hoặc tìm được nhưng không lấy được chữ/alt/heading quanh ảnh | yes |
| Lỗi ảnh/OCR, JSON OCR sai/chưa hoàn tất; nguồn bị chặn/thiếu dữ liệu, lỗi mạng/HTTP/redirect | no |
| Model chọn winner_id hợp lệ trong tập ứng viên đã gửi | yes ngay, không chặn bằng exact_match, tên trích nguyên văn, evidence_ids hoặc entity_type |
| Model trả rejected_ids/different_entity_ids | no, không bắt buộc cùng loại entity hoặc có bằng chứng tên nguyên văn |
| Model trả location_conflict_ids: nguồn xác định địa điểm mâu thuẫn rõ ràng | no |
| Model trả unconfirmed_branch_ids: cùng tên/thương hiệu/hệ thống nhưng chưa xác định chi nhánh, không có mâu thuẫn địa điểm rõ ràng | yes |
| Model trả generic_description_ids: chỉ mô tả chung, chưa xác định tên riêng/đối tượng khác | yes |
| Model trả response sai schema, ID ứng viên lạ, winner đồng thời bị loại, hoặc không phân loại ứng viên | no, kèm reason/error riêng |

“Chưa chứng minh chi nhánh” khác “địa điểm mâu thuẫn rõ ràng”: trường hợp thứ nhất yes, thứ hai no theo yêu cầu mới nhất. Phân loại bằng trường JSON riêng, không dùng regex suy đoán câu explanation tiếng Anh/Việt.

Các điều kiện URL/OCR khớp trực tiếp và chọn địa chỉ mạnh duy nhất được giữ. Khi cần gọi kiểm nguồn, vẫn phải nhận OCR hợp lệ trước; no_text/unreadable là OCR hợp lệ. Sau OCR lỗi, gán no và không gọi nguồn.

Model đã chọn/loại ứng viên thì code tuân theo mà không có guard ngữ nghĩa tên/evidence/type cũ. Code vẫn kiểm ID thuộc đúng các ứng viên đã gửi và không cho winner nằm trong rejected_ids: không thể áp dụng quyết định vào một record không tồn tại. evidence_ids được giữ để giải thích; ID bằng chứng không khớp chỉ được ghi unresolved_evidence_ids, không tự chặn nhãn.

## Nhóm ảnh

--group-yes multiple là mặc định cho các nhãn fallback theo rule mới: nhiều record cùng được rule yes thì giữ nhiều yes. Giữ các nhãn đã có khi kiểm các record còn trống. Model chọn rõ một winner hoặc code tìm địa chỉ mạnh duy nhất thì chọn record đó và gán phần chưa duyệt còn lại no; các yes đã có sẵn được giữ ở chế độ multiple.

--group-yes single ép mỗi ảnh một yes: giữ yes có sẵn đầu tiên hoặc chọn ứng viên thỏa rule đầu tiên; các record khác no. Tính năng chọn nhiều trên HTML duyệt tay độc lập với tùy chọn chạy tự động này.

Lỗi quyền truy cập model/quota, ngân sách, Ctrl+C và Batch đang pending KHÔNG phải một kết quả kiểm tra: dừng/chờ/resume và không gán no hàng loạt cho phần chưa xử lý. Trong các nhóm đã xử lý hoàn tất, rule v4 đưa ra yes/no, không giữ blank.

## Chạy Standard trên CSV chính còn lại

```bash
/usr/bin/python3 tool/run_grouped_luna_standard.py \
  --input general_10m_part_02.csv --unlabeled-only --first 2000 \
  --policy user-rules-v4 --group-yes multiple \
  --output-dir tool/outputs/luna_grouped_standard_rules_v4_2000 \
  --workers 8 --budget-usd 3 --run
```

Bỏ --run để preview offline. Chọn 2.000 dòng approve trống theo thứ tự CSV rồi mở rộng mọi record cùng image_url trong toàn snapshot, kể cả ngoài phạm vi seed. Không tự ghi CSV chính. Chạy tiếp cùng run thêm --resume; thay đổi policy/group-yes phải dùng output mới. Không resume run v2/v3 vào policy v4. Legacy chỉ dùng cho lượt mới với --policy legacy và output riêng.

## Batch

```bash
/usr/bin/python3 tool/run_grouped_luna.py \
  --execution batch --input general_10m_part_02.csv --first 2000 \
  --policy user-rules-v4 --group-yes multiple \
  --output-dir tool/outputs/luna_grouped_batch_rules_v4_2000 \
  --budget-usd 3 --run --watch
```

Batch vẫn cần các đợt OCR rồi kiểm nguồn. Payload kiểm nguồn dùng task/schema mới group_source_user_rules_v4 nên không dùng nhầm cache quyết định v2/v3. Cache OCR cùng model/prompt/ảnh vẫn được tận dụng. Không phát sinh API trả phí trong lúc triển khai/kiểm thử.

## Batch song song: tối đa 6–8 batch đang hoạt động

Runner Batch có --max-active-batches (1–8, mặc định 1). Đây là số batch đang hoạt động trên OpenAI; upload/create được thực hiện tuần tự cục bộ, sau khi gửi các batch chạy cùng lúc trên máy chủ. workers chỉ điều khiển bước chuẩn bị ảnh/nguồn trên máy cục bộ.

```bash
/usr/bin/python3 tool/run_grouped_luna.py \
  --execution batch --input general_10m_part_02.csv \
  --unlabeled-only --first 2000 --policy user-rules-v4 --group-yes multiple \
  --output-dir tool/outputs/luna_grouped_batch_v4_parallel_2000 \
  --max-active-batches 8 --batch-requests 250 --batch-mb 50 \
  --workers 8 --budget-usd 3 --run --watch
```

Đổi 8 thành 6 nếu muốn giới hạn 6 batch. --batch-requests là tối đa request mỗi batch; batch có thể nhỏ hơn khi chạm giới hạn dung lượng hoặc hết việc sẵn sàng. Không đảm bảo luôn tạo đủ 8 batch: phải có đủ request độc lập đang chờ. Một batch có thể chứa nhiều request; request không đồng nghĩa record.

- Mỗi job claim danh sách custom_id vào state.json trước khi upload. Các job không dùng chung request, kể cả sau khi tắt máy/resume.
- Chỉ những nhóm có response OCR của chính nó mới được tiến tới kiểm nguồn. Các nhóm này không phải chờ toàn bộ batch OCR khác hoàn tất.
- Mỗi vòng kiểm tra tất cả batch hiện có, tải kết quả batch đã xong, gửi thêm công việc vào slot trống. Không --watch sẽ gửi/kiểm tra tối đa số slot rồi thoát với WAITING_BATCH; thêm --resume để tiếp tục.
- Có thể đổi max-active-batches khi resume cùng bản code; giảm số slot không hủy các batch đã gửi. Code dừng gửi thêm cho đến khi số batch còn hoạt động thấp hơn giới hạn mới.
- Ngân sách dùng chung cho mọi batch, không phải ngân sách mỗi batch. Vẫn dừng khi gặp lỗi quyền/quota hoặc trạng thái gửi không chắc chắn; không âm thầm gửi lại.
- Nhiều batch không đảm bảo giảm thời gian hoàn tất từng batch; tổng input token đang chờ phải nằm trong hạn mức tài khoản/model. Runner không tự tăng hạn mức của OpenAI.
- Summary thêm active_batches và max_active_batches. Khi dừng, batch đã gửi vẫn chạy remote. Để tự gửi các bước phụ thuộc thì runner --watch cần còn chạy.

Đây là bản scheduler mới; dùng thư mục output mới thay vì resume các run tạo bởi scheduler cũ. Bản Standard và CSV chính không bị thay đổi. Kiểm thử bằng API giả lập, không gửi batch thật khi triển khai.

### Sửa thứ tự hàng đợi sau run qua đêm

Run 10.000 seed đã nhận 3 batch/463 OCR nhưng 300 lượt kiểm nguồn còn nằm sau 1.314 OCR trong hàng đợi cục bộ FIFO. Scheduler đã được sửa để ưu tiên request kiểm nguồn sẵn sàng trước OCR chưa gửi. Không hủy/thay các batch đang hoạt động, không gửi lại request, không thay rule nhãn.

Các checkpoint cũ nhận diện loại request từ schema nếu chưa có trường task. Summary/log mới tách reported_cost_usd, reserved_cost_usd và số queued_source_requests/queued_ocr_requests. Tiền giữ chỗ bao gồm cả các request chuẩn bị cục bộ, chưa đồng nghĩa đã trả phí OpenAI.

Bản vá runtime pin đúng cặp hash trước/sau trong batch_runtime_compatibility.json. Chỉ cho resume nếu input/policy/model và các cấu hình quyết định giữ nguyên; không mở migration tùy ý. Sau Ctrl+C và thoát, chạy đúng lệnh cũ thêm --resume --watch để nạp scheduler mới. runtime_upgrade.json ghi dấu vết nâng cấp khi khởi động lại. Không sửa manifest/state của tiến trình đang chạy trong lúc triển khai bản vá.

### Standard: một lượt lỗi mạng không dừng toàn run

Bản Standard mới tạm hoãn riêng nhóm gặp API_NETWORK_ERROR rồi tiếp tục các nhóm khác. Không tự retry lượt có thể đã được tính phí. Cuối lượt chạy, nếu còn nhóm lỗi mạng, summary có stop_reason=NETWORK_GROUPS_PENDING_RESUME và network_deferred_row_indices; dùng cùng lệnh --resume để xử lý những nhóm đó. Không ghi nhãn no vì lỗi mạng hệ thống. Lỗi key/quota/ngân sách vẫn dừng để kiểm tra. Runtime upgrade pin đúng cặp hash trong standard_runtime_compatibility.json, không đổi input/selection/policy và giữ mọi kết quả đã lưu.
