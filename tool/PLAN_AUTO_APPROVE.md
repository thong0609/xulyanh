# Plan tool duyệt ảnh nhanh theo tên entity

**Phiên bản hiện tại: v2.2 (2026-11-11).** Xem mục 10 để biết bản sửa sau phân tích v2.1. Xem mục 9 để biết bản sửa bằng chứng sau khi chạy v2. Các thay đổi sau pilot và pipeline v2 được ghi riêng ở **mục 8 — Cải tiến v2**. Mục này cập nhật cách xử lý quan hệ nhóm/thành viên của v1; các quy tắc duyệt nhanh theo tên vẫn giữ nguyên.

## 1. Mục tiêu và phạm vi

Làm một tool chạy theo lô trong vài tiếng, tự động hóa cách duyệt đã thống nhất. Ưu tiên triển khai nhanh và giảm thao tác lặp lại; không xây hệ thống xác minh đầy đủ danh tính/chi nhánh của thực thể.

- Nguồn: `general_10m_part_02.csv`. Tạo bản copy tại `tool/input/general_10m_part_02_copy.csv`, kiểm tra SHA-256 bằng nhau rồi chỉ chạy trên bản copy. Không ghi vào CSV chính. Snapshot đã thống kê: 98.049 dòng, 287 `leaf_label`; script sẽ đếm lại khi chạy.
- Mọi code mới, cấu hình, bản copy, cache, checkpoint và output nằm trong `tool/`. Bản copy input giữ làm snapshot; kết quả nhãn xuất vào `tool/outputs/`.
- Không đọc/xử lý `thu_nghiem/`. Không sửa, di chuyển hoặc ghi bất kỳ file nào trong `done/`.
- Không sử dụng `mo_ta` làm bằng chứng.
- Kết quả: một CSV mới giữ nguyên các cột, bổ sung/cập nhật `approve`; một JSONL ghi lý do và bằng chứng ngắn.
- Nhãn đã có trong input được giữ nguyên mặc định. Chỉ xử lý dòng `approve` trống.

### Quy tắc đã chốt

1. Ảnh có **tên riêng của entity** → `yes`, không yêu cầu khớp địa điểm hoặc chi nhánh.
2. `image_url` **hoặc** `page_url` có tên entity → `yes`, không cần mở trang để xác nhận thêm.
3. Nếu hai bước trên chưa khớp: mở trang, tìm tên entity, kiểm tra ảnh thuộc phần nói về entity đó. Thuộc đúng phần → `yes`; xác định ảnh thuộc mục khác → `no`.
4. Đã kiểm tra đầy đủ nhưng không tìm thấy tên entity/bằng chứng khớp → `no`.
5. Không thể hoàn tất kiểm tra do lỗi tải, truy cập, đọc ảnh hoặc trích xuất nội dung → để trống, trừ khi bước khác đã đủ điều kiện `yes`.

Quy tắc này chấp nhận tên trùng giữa các địa điểm. `yes` có nghĩa đạt quy tắc duyệt nhanh trên, không có nghĩa đã xác minh đầy đủ ba quan hệ của plan cũ.

## 2. Pipeline tổng thể

```text
CSV + cấu hình model/API
         ↓
[0] Đọc dữ liệu, tạo khóa dòng, tách tên riêng
         ↓
[1] Tải ảnh → VLM đọc chữ → đối chiếu tên riêng
         ├── Khớp → yes → ghi kết quả
         ↓ Không khớp hoặc lỗi
[2] So tên với image_url và page_url
         ├── Khớp một URL → yes → ghi kết quả
         ↓ Không khớp
[3] Tải trang → tìm tên → tìm ảnh và mục chứa ảnh
         ├── Tên và ảnh cùng mục → yes
         ├── Ảnh thuộc mục khác, bằng chứng rõ → no
         ├── Không thấy tên sau khi kiểm tra đầy đủ → no (*)
         └── Không truy cập/không đọc đủ/không xác định được → trống
         ↓
[4] Ghi JSONL từng dòng → xuất CSV mới
```

(*) Nếu bước ảnh trước đó bị lỗi và chưa có bằng chứng rõ để kết luận, giữ trống: tên có thể nằm trong ảnh chưa đọc được. Lỗi ở một bước không ngăn bước khác đưa ra `yes`.

Thứ tự mặc định giữ đúng quy trình đã thống nhất. Có thể tối ưu sau bằng cách kiểm URL trước ảnh để tiết kiệm lượt gọi model; khi đó phải kiểm tra kết quả vẫn tuân cùng quy tắc. Không cần tối ưu này cho bản đầu.

## 3. Input/output và công nghệ từng bước

### 3.1. Bộ so khớp tên mềm dùng chung cho ảnh, URL và trang

`name_profile` chứa tên gốc, tên riêng, phần số/ngày nếu có và các biến thể gợi ý. Danh sách này giúp tìm nhanh; kết quả không bị giới hạn vào những chuỗi đã khai báo.

**Input:** hồ sơ tên + chữ thực tế đọc được hoặc đoạn URL/văn bản nguồn + ngữ cảnh gần nó. **Output:** `match`, `not_match` hoặc `uncertain`, kèm chuỗi đã khớp, cách khớp và lý do.

Ba tầng xử lý, dừng khi có kết quả:

1. **Chuẩn hóa và so trực tiếp:** không phân biệt hoa/thường, dấu tiếng Việt, khoảng trắng, dấu nối; nhận viết tắt loại hình như MN/mầm non, preschool/kindergarten khi phù hợp.
2. **Chuẩn hóa số và tìm ứng viên gần đúng:** số viết bằng chữ ↔ chữ số; ngày tháng viết nhiều cách; sai OCR nhỏ hoặc thừa/thiếu từ mô tả. Fuzzy matching chỉ tìm ứng viên, không dùng một ngưỡng similarity để tự duyệt mọi tên. Bản local dùng `difflib.SequenceMatcher` của Python để không cần cài thêm thư viện.
3. **Model xét cặp tên còn khó:** cùng API ở bước đọc ảnh, nhận tên entity và đoạn chữ/URL thực sự quan sát được, quyết định hai cách viết có biểu đạt cùng tên riêng không. Cho phép biến thể Anh–Việt, thứ tự từ hoặc khác một vài từ mô tả; không kết luận chỉ vì cùng nghĩa chung. Model phải trả cụm từ làm bằng chứng. `uncertain` thì thử nguồn khác; hết nguồn vẫn không xác định được thì để trống.

Tên số cần giữ nguyên danh tính số/ngày, không so mềm đến mức bỏ khác biệt:

| Entity | Chữ/URL quan sát | Xử lý mong muốn |
| --- | --- | --- |
| Trường Mầm non 8 | Trường Mầm non Tám / mam-non-8 | match → yes |
| Trường Mầm non 8 | Ngày 8/3 / ảnh rộng 800px / bài có ID 8 | Không có bằng chứng tên trường |
| Trường Mầm non 8 | Trường Mầm non 18 | not_match, tiếp tục bước khác |
| Trường Mầm non 19/5 | Mầm non Mười Chín Tháng 5 / Mười Chín Tháng Năm | match → yes |
| Trường Mầm non 19/5 | mam-non-19-5 / mam-non-19-thang-5 | match → yes |
| Trường Mầm non 19/5 | Mầm non 19/6 | not_match, không bỏ phần tháng |
| Trường Mầm non Hoa Hồng | Hoa Hồng Kindergarten | match → yes |
| Trường Mầm non Hoa Hồng | Rose Preschool | Cho model xét là biến thể dịch tên; nếu rõ thì match, nếu mơ hồ thì uncertain |
| Trường Mầm non Hoa Hồng | Trường Mầm non Hoa Mai | not_match dù nhiều từ giống nhau |

Số đứng một mình như `8` chỉ được coi là tên khi ngữ cảnh cho thấy nó thuộc tên/biển trường; không duyệt chỉ vì ảnh hoặc URL chứa một chữ số. Đây là nhận diện tên riêng, không thêm yêu cầu khớp chi nhánh/địa điểm.

Ảnh vẫn được đọc chữ trước khi so tên để hạn chế model tự điền tên theo kỳ vọng. `not_match` tại một bước là đi tiếp, không phải kết luận no ngay. Chỉ `no` khi đã hoàn tất các kiểm tra theo quy tắc chung. Lưu `match_method` (`exact`, `numeric_normalization`, `model_semantic`) và `matched_text` trong JSONL để xem nhanh trường hợp duyệt mềm.

### Bước 0 — Đọc CSV và chuẩn bị tên để so khớp

**Input**

- File CSV; các cột cần thiết: `entity_id`, `entity_name`, `image_url`, `page_url`.
- `leaf_label` giúp xác định loại thực thể để tách tên; `approve` dùng lọc dòng cần làm.
- File cấu hình và tùy chọn `--limit`, `--workers`, đường dẫn output.

**Xử lý**

- Kiểm tra header, đọc CSV đúng encoding và dấu phân cách.
- Tạo `row_id` từ bộ `(entity_id, image_url, page_url)` và lưu số thứ tự dòng. Khóa trùng trong cùng file cần thêm số occurrence.
- Chuẩn hóa Unicode, chữ hoa/thường, dấu tiếng Việt và khoảng trắng.
- Tách tên riêng khỏi tiền tố loại hình và hậu tố địa điểm rõ ràng. Ví dụ `Trường Mầm non Hoa Hồng — Nghĩa Tân` → `Hoa Hồng`.
- Giữ bản gốc, tên đầy đủ chuẩn hóa và tên riêng chuẩn hóa. Không xóa số thuộc tên như `19/5`; không biến `Mầm non 1` thành tên rỗng.
- Với tên khó tách, chuyển cả tên gốc và hồ sơ gợi ý vào bước so mềm hiện có; chưa thêm một API riêng để tách tên. Không dùng một từ chung chung làm bằng chứng duyệt.
- Các tên chuẩn hóa là gợi ý để so nhanh, không phải danh sách cố định. Khi không khớp trực tiếp, bộ so khớp mềm xét tên gốc và chữ thực tế quan sát được theo mục 3.1 bên dưới. Cho phép cấu hình thêm alias tại `tool/name_overrides.json`.

**Output mẫu**

```json
{
  "row_id": "hash-of-row-key",
  "row_index": 0,
  "entity_name": "Trường Mầm non Hoa Hồng — Nghĩa Tân",
  "name_profile": {
    "original": "Trường Mầm non Hoa Hồng — Nghĩa Tân",
    "core_name": "Hoa Hồng",
    "normalized_candidates": ["hoa hong"],
    "numeric_identity": null,
    "aliases": []
  },
  "image_url": "https://example.org/images/abc.jpg",
  "page_url": "https://example.org/bai-viet",
  "name_status": "ok"
}
```

**Công nghệ/tài nguyên**

- Python standard library: `csv`, `json`, `hashlib`, `unicodedata`, `re`, `urllib.parse`.
- Cần CSV hiện có; không cần database hoặc dữ liệu huấn luyện.
- Danh sách tiền tố dựa trên `leaf_label`; chỉ bổ sung ngoại lệ thực sự gặp trong pilot, không xây taxonomy 287 loại trước.

### Bước 1 — Nhìn ảnh và tìm tên riêng

**Input**

- `image_url`, `name_profile`, tên gốc của entity.
- API của một model hỗ trợ nhận ảnh và trả text/JSON.

**Xử lý**

- Tải ảnh bằng HTTP, kiểm tra decode được; gửi bytes ảnh cho model để không phụ thuộc khả năng model tự mở URL.
- Yêu cầu model chép chữ thực sự nhìn thấy, không suy đoán chữ từ tên entity. Sau đó code đối chiếu tên với chữ đã đọc.
- So khớp tên riêng bằng bộ so khớp mềm ở mục 3.1. Có tên riêng tương đương là `yes`, không yêu cầu địa điểm trùng và không thêm kiểm tra nguồn.
- Nếu ảnh đọc được, không có tên/chữ liên quan: đi tiếp bước 2. Chữ có khả năng là tên nhưng quá mờ không đọc được: ghi trạng thái chưa xác định, không coi là chắc chắn không có tên.
- Ảnh hỏng, timeout hoặc API lỗi: ghi lỗi, tiếp tục bước 2.

**Output mẫu**

```json
{
  "image_check": "match",
  "observed_text": ["TRƯỜNG MẦM NON HOA HỒNG"],
  "matched_name": "hoa hong",
  "approve": "yes",
  "reason": "IMAGE_NAME_MATCH"
}
```

Các giá trị `image_check`: `match`, `not_found`, `unreadable`, `error`.

**Công nghệ/tài nguyên**

- `urllib.request` của Python để tải; Pillow để đọc ảnh và giảm kích thước khi cần, giữ đủ nét để đọc biển hiệu.
- Một API VLM có khả năng đọc chữ tiếng Việt. Bản đầu dùng VLM trực tiếp, chưa cài OCR riêng hoặc chạy model local.
- Cần API endpoint, model ID, API key và ngân sách/số dòng giới hạn cho lần thử.

### Bước 2 — Kiểm tra cả hai URL

**Input**

- `image_url`, `page_url`, `name_profile` từ bước 0.

**Xử lý**

- Decode URL encoding, chuẩn hóa chữ không dấu, hoa/thường và dấu phân cách `-`, `_`, `/` thành khoảng trắng.
- Kiểm tra tên trong cả hai URL, gồm các thành phần URL có văn bản.
- Ví dụ `.../truong-mam-non-hoa-hong/...` khớp `hoa hong` → `yes`.
- So trực tiếp theo chuỗi từ có ranh giới trước; nếu chưa khớp thì dùng bộ so khớp mềm. Không dùng khớp substring thiếu ranh giới: `an` không tự khớp bên trong `thanh`. Số trong ngày đăng, kích thước ảnh hoặc ID URL không được coi là tên trường.
- Không yêu cầu tải được URL nếu bản thân chuỗi đã khớp.
- Không khớp cả hai → bước 3, chưa kết luận `no`.

**Output mẫu**

```json
{
  "url_check": "match",
  "matched_field": "page_url",
  "matched_name": "hoa hong",
  "approve": "yes",
  "reason": "PAGE_URL_NAME_MATCH"
}
```

**Công nghệ/tài nguyên**

- Python standard library cho so khớp trực tiếp; cùng API model cho so khớp ngữ nghĩa khi chưa khớp trực tiếp.
- Dùng cùng tên riêng đã tách như bước ảnh; tên đầy đủ cũng là một dạng được chấp nhận. Không yêu cầu địa điểm xuất hiện trong URL.

### Bước 3 — Mở nguồn, tìm tên và mục chứa ảnh

**Input**

- `page_url`, `image_url`, hồ sơ tên để tìm bằng bộ so khớp mềm; kết quả/lỗi từ các bước trước.

**Xử lý**

1. Tải HTML, theo redirect có giới hạn; lấy phần nội dung chính, heading, đoạn văn, caption và các thẻ ảnh.
2. Tìm tên trong phần nội dung, tránh lấy menu/footer hoặc danh sách bài liên quan làm chứng cứ của bài chính.
3. Tìm ảnh đang xét qua `src`, `srcset`, `data-src`, URL tương đối; giữ heading/card/figure chứa ảnh.
4. Nếu tên nằm trong chính card/mục chứa ảnh hoặc caption của ảnh → `yes`.
5. Nếu trang có nhiều entity và ảnh thuộc mục của entity khác rõ ràng → `no`.
6. Nếu đọc được nội dung đầy đủ mà không thấy tên, và bước ảnh cũng đã kiểm tra được không có tên → `no`.
7. Nếu trang có tên nhưng không xác định ảnh thuộc mục nào, HTML thiếu phần nội dung động, ảnh dùng URL biến thể chưa ghép được, bị chặn hoặc lỗi tải → trống.

Trường hợp cấu trúc khó, gửi đoạn HTML đã làm gọn gồm heading/text/thẻ ảnh cho cùng API model để chọn mục và trả lại đoạn bằng chứng. Không gửi `mo_ta`. Nếu model không chỉ ra được bằng chứng trong nội dung đã cung cấp thì giữ trống.

**Output mẫu**

```json
{
  "page_check": "match",
  "entity_mentioned": true,
  "image_section": "Trường Mầm non Hoa Hồng",
  "evidence": "Đoạn văn hoặc caption gắn với ảnh",
  "approve": "yes",
  "reason": "PAGE_SECTION_MATCH"
}
```

Các giá trị `page_check`: `match`, `other_entity_section`, `name_not_found`, `unresolved`, `error`.

**Công nghệ/tài nguyên**

- Bản local dùng `urllib.request` + `html.parser` của Python để đọc HTTP/DOM; parser tổng quát cho heading/card/figure. Trang động/khó trích xuất để trống.
- Cùng API model của bước 1 cho ca cần hiểu đoạn nội dung; không cần API thứ hai.
- Cần máy có mạng truy cập website nguồn.
- Bản đầu chưa làm trình duyệt tự động, vượt CAPTCHA, đối chiếu ảnh bằng embedding hoặc adapter từng website. Trang không đọc đủ bằng HTTP được để trống. Playwright chỉ là bổ sung sau nếu pilot cho thấy nhiều dòng cần nó.

### Bước 4 — Tổng hợp quyết định và xuất kết quả

**Input**

- Bản ghi gốc và các kết quả bước 0–3.

**Xử lý quyết định**

| Điều kiện | approve | reason |
| --- | --- | --- |
| Tên riêng xuất hiện trong ảnh | `yes` | `IMAGE_NAME_MATCH` |
| Tên xuất hiện trong URL ảnh | `yes` | `IMAGE_URL_NAME_MATCH` |
| Tên xuất hiện trong URL trang | `yes` | `PAGE_URL_NAME_MATCH` |
| Ảnh thuộc mục nói về entity trên trang | `yes` | `PAGE_SECTION_MATCH` |
| Xác định ảnh thuộc mục entity khác | `no` | `PAGE_SECTION_OTHER_ENTITY` |
| Đọc ảnh/trang thành công, không tìm được tên | `no` | `NAME_NOT_FOUND` |
| Không đủ khả năng kiểm tra, chưa có kết luận ở trên | trống | `CHECK_INCOMPLETE` |

- `yes` từ bước trước là kết quả cuối, không chạy kiểm tra tiếp để lật nhãn.
- API lỗi/JSON lỗi không được biến thành `not_found`.
- Lưu kết quả mỗi dòng vào JSONL để có thể resume. Cache đơn giản nội dung trang theo URL và chữ ảnh theo URL/hash để giảm tải trùng.
- Ghi CSV mới theo lô hoặc khi kết thúc; không ghi lại cả CSV cho mỗi dòng.
- Khi resume, kiểm tra hash input và phiên bản cấu hình; không tái sử dụng quyết định của một snapshot khác mà không đối chiếu.

**Output**

- `tool/outputs/<run_id>/reviewed.csv`: nguyên các cột/giá trị gốc, thay `approve` của những dòng được xử lý.
- `tool/outputs/<run_id>/results.jsonl`: `row_id`, `approve`, `reason`, tên đã tách, chữ OCR/VLM, URL/mục khớp, lỗi nếu có.
- `tool/outputs/<run_id>/summary.json`: tổng dòng, số yes/no/trống, lỗi từng bước, số lần gọi model và usage nếu API cung cấp.
- `tool/outputs/<run_id>/manifest.json`: input hash, model, cấu hình và thời gian chạy.

**Công nghệ/tài nguyên**

- Python standard library; không cần SQLite, server mới hoặc hàng đợi dịch vụ.
- Dùng lại `review_server.py` để mở CSV kết quả và xem/sửa nhãn. Chưa cần sửa UI trong bản đầu; lý do xem trong file JSONL.

## 4. Bạn cần cung cấp gì để triển khai và chạy?

| Tài nguyên/thông tin | Hiện trạng | Cần làm |
| --- | --- | --- |
| CSV đầu vào | Đã có | Dùng CSV chính, không cần gửi lại |
| Quy tắc yes/no/trống | Đã chốt | Áp dụng đúng mục 1 |
| API VLM | Đã chọn OpenAI `gpt-5.4-mini` | Responses API, dùng chung ảnh và text |
| API key | Chưa xác nhận | Đặt trong biến môi trường hoặc file `.env` local; không ghi key vào CSV, code hay báo cáo |
| Giới hạn lần chạy thử | Đã chốt | 50 dòng, 3 workers, ngân sách tối đa 0,50 USD; bộ đếm chi phí dự phòng trước mỗi request |
| Python và thư viện | Repository đã có Python reviewer | Python 3.10+ và Pillow; HTTP, HTML parser, CSV và JSON dùng thư viện chuẩn |
| Mạng truy cập ảnh/trang/API | Cần kiểm tra khi bắt đầu | Test một số URL trước khi chạy lô |
| GPU riêng, dữ liệu train, database | Không cần cho bản đầu | Dùng API sẵn có và file local |

Có thể viết phần đọc CSV, URL matching, parser, export và client interface ngay. Để chạy thật bước đọc ảnh, cần cấu hình API model và quyền truy cập mạng. Model/provider đã chốt nhưng chưa đo được chi phí thực; đo bằng pilot thay vì dự đoán theo toàn bộ 98 nghìn dòng.

## 5. Phạm vi code và lịch làm trong vài tiếng

Cấu trúc tối thiểu:

```text
tool/
  PLAN_AUTO_APPROVE.md       # bản plan đầy đủ
  approve_tool.py            # pipeline, matching, client, checkpoint/export
  requirements-approve.txt   # dependencies
  .env.example               # tên biến; không có secret
  name_overrides.json        # alias tùy chọn
  input/
    general_10m_part_02_copy.csv  # bản copy, không ghi đè khi chạy lại
    snapshot.json            # hash và nguồn bản copy
  cache/                     # ảnh/HTML/chữ quan sát đã xử lý
  outputs/<run_id>/          # CSV mới, bằng chứng, checkpoint
```

Ước lượng triển khai, với API và mạng sẵn sàng:

| Thời gian | Công việc | Kết quả kiểm tra được |
| --- | --- | --- |
| 0–45 phút | CSV, tách tên, chuẩn hóa URL, output | Khớp tên theo ví dụ; giữ nguyên dữ liệu ngoài approve |
| 45–105 phút | Tải ảnh, kết nối VLM, xử lý lỗi | Biển hiệu có tên → yes; ảnh lớp học → đi tiếp |
| 105–165 phút | Tải trang, tìm tên, liên kết ảnh với mục | Trang đơn entity và trang nhiều mục hoạt động trên mẫu |
| 165–240 phút | Chạy thử 50 dòng, sửa lỗi chính, resume và hướng dẫn chạy | CSV mới + lý do, thống kê yes/no/trống |

Đây là ước lượng làm bản đầu, không bao gồm thời gian xử lý hết dữ liệu. Chạy toàn bộ có thể lâu hơn do tải mạng, giới hạn API và số lần gọi; pilot sẽ cho tốc độ thực tế.

CLI đã triển khai. Không có `--run` chỉ chuẩn bị mẫu offline; thêm `--run` mới tải mạng và gọi API:

```bash
python3 tool/approve_tool.py --baseline-dir tool/outputs/pilot_v1 --limit 50
python3 tool/approve_tool.py --baseline-dir tool/outputs/pilot_v1 --limit 50 --workers 3 --budget-usd 0.50 --run
python3 review_server.py tool/outputs/pilot_v2/pilot_50.csv --port 8001
```

CSV pilot giữ đủ các dòng gốc, chỉ thử xử lý 50 dòng chưa có nhãn; các dòng còn lại giữ nguyên. Báo cáo ghi rõ đã xử lý bao nhiêu để không nhầm với kết quả toàn bộ.

## 6. Kiểm tra tối thiểu trước khi chạy lớn

- Tên có dấu ↔ URL không dấu; URL encoded; dấu gạch nối.
- Tên số `8` ↔ `Tám`; `19/5` ↔ `Mười Chín Tháng Năm`; không nhầm với 18, 19/6, ngày đăng hoặc số trong ID URL.
- Biến thể Anh–Việt, viết tắt, OCR lỗi nhẹ, thiếu từ mô tả; tên riêng khác nghĩa không được match chỉ vì câu gần giống.
- Khởi chạy/resume chỉ đọc bản copy trong tool/input; không ghi CSV chính và không đọc/ghi done hoặc thu_nghiem.
- Tên riêng trùng nhưng khác địa điểm vẫn yes theo quy tắc người dùng.
- Ảnh tải lỗi nhưng URL khớp vẫn yes.
- Ảnh đọc được không có tên, trang không có tên và đọc đầy đủ → no.
- Ảnh lỗi + URL không khớp + trang không có tên → trống.
- Trang có tên nhưng ảnh thuộc mục khác → no; không xác định được mục → trống.
- Trang 403/timeout hoặc chỉ là khung JavaScript → trống, không giả thành no.
- Model lỗi/đọc không rõ → chưa xác định, không giả thành không tìm thấy.
- CSV output giữ số dòng, thứ tự và dữ liệu ngoài approve; nhãn cũ được giữ; input không bị ghi đè.

Pilot xem trực tiếp một số dòng yes/no/trống và lý do, sửa lỗi thao tác rõ ràng rồi chạy lô lớn hơn. Chưa làm gold set hàng nghìn mẫu, fine-tune, calibration thống kê, dashboard hay bộ policy ngoài yêu cầu hiện tại.

**Tiêu chí hoàn tất bản đầu:** chạy được một lô từ CSV đến CSV mới, áp dụng đúng các nhánh quyết định, có lý do để bạn kiểm tra và tiếp tục duyệt bằng công cụ hiện có.

## 7. Bản GPU Kaggle đã triển khai

- Notebook: `tool/kaggle/approve_images.ipynb`; runner: `tool/kaggle/run_gpu.py`; hướng dẫn: `tool/kaggle/README.md`.
- Dùng Qwen2.5-VL-3B-Instruct local trên GPU, không gọi OpenAI API. Bản local API không thay đổi.
- Mặc định kiểm URL khớp trực tiếp trước để giảm lượt GPU; những dòng chưa khớp tiếp tục pipeline ảnh/URL mềm/nguồn. Có `--no-url-first`.
- Chạy 50 dòng kiểm tra model mới trước, rồi dùng `--all`; checkpoint mỗi dòng, CSV định kỳ, resume bundle cho phiên Kaggle sau.
- Model/API khác nhau có thể cho nhãn khác nhau. Đã kiểm tra logic offline, chưa chạy inference GPU thực tế do môi trường phát triển không có CUDA/torch.


## 8. Cải tiến v2 — sửa lỗi pilot và bổ sung quan hệ ngữ nghĩa

### 8.1. Phiên bản và dữ liệu đối chiếu

| Phiên bản | Vai trò | Thư mục |
| --- | --- | --- |
| v1 | Kết quả đã chạy: 21 yes, 3 no, 26 trống; giữ làm mốc đối chiếu, không phải nhãn chuẩn | `tool/outputs/pilot_v1/` |
| v2 | Chạy lại đúng 50 record và đúng thứ tự của manifest v1 | `tool/outputs/pilot_v2/` |

Đã sao chép nguyên kết quả cũ sang `pilot_v1`, giữ nguyên cả `outputs/pilot` ban đầu. Code/plan v1 lưu tại `tool/versions/v1/`. Không ghi đè baseline. `--baseline-dir` kiểm tra hash input, số dòng, danh sách chỉ số và row_id; không lấy một mẫu ngẫu nhiên khác. Record 14/47 là vị trí trong mẫu này, không phải dòng 14/47 của CSV chính.

### 8.2. Những lỗi được sửa

| Vấn đề ở v1 | Xử lý ở v2 |
| --- | --- |
| URL ảnh chứa dấu phẩy bị cắt thành nhiều URL | Giữ nguyên src/data-src/content; chỉ phân tích danh sách ở srcset. Đọc cả link ảnh gốc bọc quanh thumbnail. |
| URL khác cách viết hoặc CDN đổi kích thước | Chuẩn hóa Unicode/percent encoding, http/https và một số mẫu Cloudflare/Cloudinary có cấu trúc rõ; giữ query định danh. Không ghép ảnh chỉ vì giống basename. |
| Caption hoặc URL đúng nhưng model trích có ngoặc kép/dấu khác | Kiểm chứng chuỗi từ liên tiếp sau chuẩn hóa dấu, Unicode, khoảng trắng và URL decoding. Không dùng fuzzy để hợp thức hóa bằng chứng bịa. |
| Ảnh lấy nhầm heading của card trước | Ưu tiên đúng card chứa ảnh và tiêu đề của chính card, kể cả tiêu đề đứng sau ảnh; không coi card-img-top là cả card. Với bài nhiều mục, chặn ngữ cảnh tại heading tiếp theo cùng/cao hơn cấp. |
| Tách tên còn giữ Ga/Đường/địa chỉ; bỏ nhầm tên trong ngoặc | Bổ sung loại hình, tách địa chỉ rõ; tên trong ngoặc là ứng viên để model xét. Vẫn đưa tên gốc cho model, không buộc chỉ khớp core_name. |
| URL không có tên bị trả uncertain dù đọc được | Prompt phân biệt không có ứng viên trong chuỗi URL → not_match với ứng viên thật sự mơ hồ → uncertain. not_match chỉ chuyển sang bước đọc nguồn. |
| Số thứ tự/ngày/tham số ảnh bị nhầm thành tên | Giữ số/ngày/mã định danh; bằng chứng tên số phải kèm ngữ cảnh loại thực thể. T2 khác T3; 19/5 khác 19/6. |
| Chỉ có CSV đủ 98.049 dòng nên khó xem mẫu đã chạy | Tự xuất `pilot_50.csv` có approve và `comparison_v1_v2.csv` theo đúng thứ tự mẫu. |

### 8.3. Quy tắc ngữ nghĩa mới

Phân biệt **tên riêng** với **một nhóm/đối tượng được mô tả**. Với tên riêng, vẫn duyệt khi thấy tên, không bắt khớp chi nhánh. Với nhóm, loại hình và phạm vi trong tên là điều kiện thành viên; không tách “Hà Nội” rồi dùng riêng địa danh đó để duyệt.

| Quan hệ trả về | Điều kiện | Nhãn ở bước nguồn |
| --- | --- | --- |
| same_entity | Cùng tên/đối tượng, kể cả diễn đạt lại hoặc Anh–Việt; có bằng chứng gắn với ảnh | yes |
| instance_of / part_of | Ảnh thuộc một thành viên/bộ phận của nhóm; nguồn chứng minh loại hình và phạm vi liên quan | yes |
| same_topic | Cùng chủ đề/hoạt động, chưa chứng minh là đối tượng hoặc thành viên | Trống nếu quan hệ còn chưa xác định |
| different | Ngữ cảnh ảnh chứng minh đối tượng khác; với nhóm phải có bằng chứng trái loại/phạm vi | no |
| unknown | Không tìm được ảnh trong bài, thiếu bằng chứng, không đọc được hoặc quan hệ mơ hồ | Trống |

- **Khu tập thể cũ Hà Nội ↔ Kim Liên:** có thể xét quan hệ instance_of. Phải tìm được ảnh trong nguồn, có nội dung xác nhận Kim Liên là khu tập thể thuộc Hà Nội, và nội dung ảnh phù hợp. Nếu đây là phối cảnh đề xuất cải tạo, không tự coi là ảnh hiện trạng cũ. Không hard-code record 14 thành yes.
- **Nhà kính ↔ bài tưới nhỏ giọt cà chua trong nhà kính:** khác chủ đề bài viết vẫn có thể cùng đối tượng ảnh. Tuy nhiên entity hiện tại còn chỉ **khu nông nghiệp công nghệ cao TP.HCM**; cần nguồn xác nhận thuộc khu này. Địa chỉ công ty bán thiết bị ở TP.HCM không chứng minh địa điểm của nhà kính. Thiếu quan hệ này → trống, không tự gán yes hoặc no cho record 47.
- Với nhóm, thiếu nguyên văn tên không đủ để no. Với tên riêng, đã đọc đủ ảnh/URL/trang và không có tên/biến thể → no như trước. Lỗi API/tải/trích xuất không được đổi thành không có tên.
- Bộ nhận diện nhóm ban đầu dùng một số mẫu loại hình và có thể điều chỉnh bằng `scope` trong overrides; model vẫn xét tên gốc và quan hệ khi đọc nguồn. Chưa phải bộ phân loại hoàn chỉnh cho toàn bộ 287 loại.

### 8.4. Pipeline v2: input, output và tài nguyên

| Bước | Input | Xử lý và tài nguyên/công nghệ | Output |
| --- | --- | --- | --- |
| 0. Cố định mẫu | CSV copy + manifest/results v1 + overrides | Python CSV/JSON/hash; kiểm tra cùng snapshot, lấy đúng 50 row_id/chỉ số | Danh sách 50 dòng + name_profile gồm tên gốc, tên riêng gợi ý, alias, số/mã và scope |
| 1. Đọc ảnh và so tên | image_url + name_profile | HTTP cache, Pillow; VLM chỉ đọc chữ trước, không được xem tên cần tìm; sau đó exact/numeric hoặc model so mềm | Chữ quan sát + match/not_match/uncertain + bằng chứng. Match → yes |
| 2. So hai URL | image_url + page_url + name_profile | Chuẩn hóa chuỗi, so trực tiếp, model so mềm nếu cần; không cần mở trang để duyệt URL có tên | Match → yes; không thấy tên → tiếp bước 3; lỗi/không rõ được lưu lại |
| 3. Tìm ảnh trong nguồn | page_url + image_url | HTTP + HTMLParser; xác nhận URL ảnh và lấy đúng card/caption/mục | text, contexts, target_found và cờ thiếu/cắt nội dung; lỗi truy cập → trống nếu chưa có kết luận |
| 4. So tên/quan hệ trong nguồn | name_profile + contexts + text; thêm ảnh đã tải cho trường hợp nhóm | Model hiện có, không thêm dịch vụ. Xét same_entity/instance_of/part_of/same_topic/different/unknown; code kiểm chứng trích dẫn trong ngữ cảnh ảnh và nguồn | status + relation + scope_status + evidence + supporting_evidence + visual_status + explanation |
| 5. Quyết định và xuất | Kết quả từng bước + baseline v1 | Python; chỉ yes/no khi đủ điều kiện; checkpoint từng dòng, bảo vệ nhãn input | approve, reason, errors; CSV mẫu, CSV đầy đủ, JSONL, thống kê, bảng so sánh v1/v2 |

Không dùng description/mo_ta. GPU local, database, OCR service riêng, embedding, browser tự động và dữ liệu huấn luyện đều không cần. Cần Python/Pillow hiện có, API key trong `tool/.env`, mạng tới OpenAI và tới URL chưa có cache. Model local vẫn dùng `gpt-5.4-mini`, tối đa 3 workers và trần dự phòng 0,50 USD/lần chạy; đây không phải chi phí cố định của 50 dòng.

### 8.5. Cache, chạy lại và tiêu chí kiểm tra

Dùng lại **bytes ảnh/HTML đã tải** từ v1 để giảm tải mạng và giữ cùng nguồn so sánh. Toàn bộ kết quả model v2 có namespace phiên bản mới, không tái dùng quyết định hoặc OCR v1. Lần chạy mới gọi model lại và ghi usage riêng. Nội dung web trong cache là bản đã tải trước đó, không phải lần cập nhật mới nhất của website.

Lệnh từ thư mục dự án:

```bash
# Chỉ chuẩn bị đúng mẫu cũ, không gọi API:
python3 tool/approve_tool.py --baseline-dir tool/outputs/pilot_v1

# Bạn tự chạy sau khi đã có API key:
python3 tool/approve_tool.py --baseline-dir tool/outputs/pilot_v1 --run

# Chỉ dùng để tiếp tục khi lần chạy trên bị ngắt:
python3 tool/approve_tool.py --baseline-dir tool/outputs/pilot_v1 --run --resume
```

Output v2:

- `pilot_50.csv`: đúng 50 record cũ, cùng thứ tự, approve mới.
- `comparison_v1_v2.csv`: số thứ tự mẫu, row_index (bắt đầu từ 0), tên/URL, approve/reason của hai bản, nhãn có đổi hay không, quan hệ và lỗi v2.
- `reviewed.csv`: đủ dòng gốc, chỉ cập nhật approve của mẫu được xử lý.
- `results.jsonl`, `summary.json`, `usage.json`, `manifest.json`: bằng chứng, số nhãn chuyển, lỗi, usage và cấu hình để resume.
- `sample_preview.json`: danh sách chọn trước khi gọi API; không phải file nhãn đã xử lý.

Đã kiểm tra offline bằng bộ test, gồm lỗi parser từ HTML cache thực tế của pilot, bằng chứng có dấu/ngoặc kép, tên số, quan hệ nhóm thiếu/đủ bằng chứng, đúng 50 row_id, xuất approve vào CSV mẫu, so sánh baseline, resume và giữ nguyên input/v1. Các bài kiểm tra inference dùng model giả lập; **chưa đo chất lượng nhãn v2 bằng API thật**. Số nhãn đổi không đồng nghĩa số nhãn đúng hơn; cần mở mẫu v2 đối chiếu sau khi chạy. Chưa mở rộng chạy toàn CSV trong lần sửa này.


## 9. Cải tiến v2.1 — chọn bằng chứng bằng ID

**Vấn đề thực tế:** v2 có 17/23 dòng trống gặp lỗi bằng chứng. Model thường thêm `alt=`, ghép nhiều trích dẫn bằng “và”, hoặc chèn dấu `...`; code tìm nguyên chuỗi nên loại cả kết luận có thể đúng. Một số lỗi vẫn phải chặn vì model lấy tên ở mục khác, không xác nhận được ảnh hoặc tự suy diễn alias.

**Hướng đã chọn và triển khai:** code chuẩn bị các đoạn nguồn có ID; model chọn ID và giải thích riêng. Không dùng model viết lại câu trích, không bỏ cơ chế kiểm chứng, không thêm lượt API riêng cho mỗi trích dẫn.

| Bước | Input | Xử lý | Output |
| --- | --- | --- | --- |
| Chuẩn bị ảnh/URL | Các dòng OCR hoặc hai URL | Gán obs_0, obs_1…; giữ nguyên nội dung | blocks gồm id/text/field/context_index |
| Chuẩn bị nguồn | Văn bản bài và từng context ảnh | Chia đoạn tối đa 600 ký tự, gán ID riêng cho heading/alt/local_text và bài; giữ các lát văn bản gốc | Danh mục bằng chứng, chỉ số context và cờ thiếu/cắt nội dung |
| Model lựa chọn | Hồ sơ tên + danh mục bằng chứng; ảnh nếu đang xét nhóm | Trả evidence_ids, supporting_evidence_ids, observed_name, name_relation và kết luận; giải thích tách riêng | ID của các đoạn được chọn, không phải lời trích tự sinh |
| Code kiểm chứng | Kết quả model + danh mục gốc | ID phải tồn tại, không lặp; bằng chứng chính của match/other_entity phải thuộc đúng context ảnh; bằng chứng hỗ trợ có thể ở phần khác bài | Nguyên văn nguồn, metadata ID/context/field và kết quả kiểm chứng |
| Chốt danh tính | Tên thực tế + loại quan hệ tên | exact phải khớp tên; alias phải do người dùng cung cấp/ghi trong tên hoặc có nguồn trực tiếp nối hai tên; số/mã vẫn được bảo vệ | Thiếu chứng minh danh tính → uncertain, không tự duyệt yes |

Ví dụ: model chọn `c0_alt_0_0`; code tự lấy nội dung `Phủ Tây Hồ` từ alt của context 0. Chọn đồng thời nhiều ID cho phép nhiều trích dẫn độc lập; code lưu từng đoạn, không yêu cầu cả câu ghép xuất hiện trong HTML. IDs không hợp lệ hoặc thuộc mục ảnh khác vẫn báo lỗi và giữ trống.

`observed_name` chỉ là tên ngắn cần nhận diện, phải xuất hiện trong đoạn được chọn (cho phép URL decoding/chuẩn hóa). `name_relation` phân biệt exact/translation/ocr_variant/number_equivalent/alias/not_applicable. Prompt cấm coi hai tên riêng tiếng Việt khác nhau là bản dịch hoặc lỗi OCR. Quan hệ thành viên phải đúng chiều: đối tượng trong ảnh là thành viên/bộ phận của entity cần duyệt.

**Giới hạn:** ID chứng minh nguồn trích và vị trí, không bảo đảm model hiểu đúng mọi quan hệ. Bản dịch, OCR sai và quan hệ nhóm vẫn cần model; chưa thể cam kết hết lỗi suy luận. Bản này tập trung sửa bằng chứng và chặn alias không có căn cứ; chưa sửa toàn bộ các vấn đề tách tên/chính sách đã phát hiện trong phân tích v2.

**Version/output:** code v2 lưu ở `tool/versions/v2/`; output mới mặc định `tool/outputs/pilot_v2_1/`; giữ kết quả v1/v2 để đối chiếu. Namespace model đổi sang pilot-v2.1, không dùng lại quyết định model cũ. Bytes ảnh/HTML vẫn dùng cache thô cũ. Hash code thay đổi nên không resume vào run v2 cũ.

```bash
# Đúng 50 record v1, chỉ chuẩn bị offline:
python3 tool/approve_tool.py --baseline-dir tool/outputs/pilot_v1

# Bạn tự chạy API và ghi output v2.1:
python3 tool/approve_tool.py --baseline-dir tool/outputs/pilot_v1 --run

# Khi bị ngắt mới thêm --resume; dòng đã hoàn tất không tự chạy lại.
```

Trong `pilot_v2_1`, các tên cột `approve_v2`/`reason_v2` của comparison CSV chỉ kết quả bản hiện tại (v2.1); manifest ghi phiên bản chính xác. CSV mẫu vẫn là `pilot_50.csv`, bảng đối chiếu v1 là `comparison_v1_v2.csv`. Tạo giao diện HTML cho run mới bằng:

```bash
python3 tool/render_comparison.py tool/outputs/pilot_v2_1/comparison_v1_v2.csv
```

**Kiểm tra:** 52 test offline đã đạt, gồm lấy nhiều đoạn nguyên văn theo ID, chọn URL, ID giả/lặp/sai context, chọn tên chỉ có trong phần khác bài, alias không có chứng minh giữa hai tên khác nhau và alias có nguồn xác nhận. Backend Kaggle dùng chung schema/validator và đã qua test tương thích. Chưa chạy API thật hoặc inference GPU; chưa có số đo chất lượng/chi phí v2.1.


## 10. Cải tiến v2.2 — tên riêng và ngữ cảnh ảnh

### Phần đã sửa

- Tách thêm tiền tố loại hình như tòa nhà, khu đô thị, sân ga, sân gôn/golf, tháp nước, trạm biến áp, âu tàu, bến đò, lăng, phủ. Tên riêng/số/mã vẫn được giữ. Không cấu hình nhãn theo số record.
- Các trường hợp như Crescent Plaza, Lakeview City, Hải Phòng, Montgomerie Links và Hàng Đậu không phải có cả tiền tố loại hình mới khớp. Giữ quy tắc tên riêng trùng thì duyệt, không đòi chi nhánh/địa điểm.
- Nếu OCR tách tên thành 2–3 dòng ngắn liên tiếp, thử ghép để so trực tiếp, ví dụ LAKEVIEW / CITY. Lưu source_lines, source_line_indices và method exact_ocr_lines để kiểm tra lại. Không ghép hai URL với nhau. OCR hiện chưa trả tọa độ, nên ghép dòng vẫn dựa trên thứ tự đọc, chưa bảo đảm các dòng thuộc cùng một biển.
- Các tên chỉ còn từ chung như thiếu nhi, tuổi trẻ, văn hóa, trung tâm cần ngữ cảnh loại thực thể. Công viên Thiếu nhi có thể khớp; Quốc tế Thiếu nhi không được dùng riêng để duyệt công viên. Chốt này áp dụng cả fast match và kết quả so mềm.
- Bỏ mục lục khỏi văn bản trích; nội dung từng mục vẫn còn. Ngữ cảnh ảnh dừng trước heading kế tiếp kể cả heading con, và giới hạn quanh ảnh cạnh nhau. Ảnh bìa trước mục đầu tiên không thu cả nội dung các mục phía dưới.
- Danh mục ID dùng làm bằng chứng chính chỉ giữ heading sâu nhất của context, alt và local_text. Heading cấp trên vẫn có thể xuất hiện trong văn bản bài để hỗ trợ, nhưng không được chọn ID context của heading đó làm bằng chứng trực tiếp cho ảnh.
- Tên trong ngoặc có Q7/P1… được nhận là địa chỉ, tránh nhầm thành alias.

### Pipeline, input/output và tài nguyên

Giữ pipeline v2.1 và API/model hiện có. Input vẫn CSV copy + đúng 50 chỉ số từ baseline v1; bước tên trả thêm entity_type/requires_type_context. Bước OCR có thể trả kết quả match trực tiếp từ vài dòng ngắn; bước nguồn đưa ngữ cảnh đã thu hẹp vào danh mục ID. Kết quả vẫn gồm approve/reason/checks/errors, CSV mẫu, CSV đầy đủ và bảng so sánh với v1. Không cần dịch vụ, API key hoặc dependency mới.

Code v2.1 lưu ở `tool/versions/v2_1/`. Namespace model đổi sang pilot-v2.2; output mới mặc định `tool/outputs/pilot_v2_2/`; giữ nguyên kết quả các bản trước. Dùng lại bytes ảnh/HTML, không dùng lại quyết định model của bản cũ. Không resume v2.1 bằng code v2.2.

```bash
# Chuẩn bị đúng 50 record cũ, offline:
python3 tool/approve_tool.py --baseline-dir tool/outputs/pilot_v1

# Bạn tự chạy API:
python3 tool/approve_tool.py --baseline-dir tool/outputs/pilot_v1 --run

# Sau khi có CSV, tạo HTML ngay cạnh CSV:
python3 tool/render_comparison.py tool/outputs/pilot_v2_2/comparison_v1_v2.csv
```

### Kiểm tra và giới hạn

59 test offline đã đạt. Có kiểm tra bằng chữ OCR thực của #25 và #31: pipeline duyệt yes trực tiếp, không cần so mềm hoặc mở bài. Có kiểm tra HTML cache thực của #34: ảnh bìa còn được nhận diện, local_text không chứa tên Hạnh Phúc Tăng từ các mục sau. Kiểm tra thêm tên loại hình, trường hợp thiếu nhi, mục lục, heading con, heading cha không được làm bằng chứng chính, và giữ các bài kiểm tra số/mã, alias, checkpoint, CSV, Kaggle.

Chưa gọi API thật cho v2.2; các kiểm tra trên không phải số đo độ chính xác 50 dòng. Parser vẫn có thể không xác định được mục ở website cấu trúc lạ; loại từ chung/prefix chỉ là tập ban đầu và model vẫn cần xét ngữ nghĩa. Bản này không tự đổi nhãn ở output cũ.


## 11. Cải tiến GPU v2.2-fast1 — tối ưu thực thi, giữ luật v2.2

Mục tiêu: giảm GPU chờ I/O và gom nhiều request vào một lần generate, không dùng API trả phí.

| Bước | Input | Xử lý / công nghệ | Output |
|---|---|---|---|
| Chọn mẫu | CSV snapshot + selection JSON | Kiểm tra SHA, đúng 50 row_id cũ | Danh sách record pending |
| Xử lý song song | Tối đa 4 record | ThreadPoolExecutor; URL exact trước, ảnh/trang dùng cache có khóa | Kết quả URL hoặc request model độc lập |
| Gom batch | Request có schema, bằng chứng, ảnh tùy chọn | Một thread sở hữu Qwen/processor/CUDA; gom cùng task/modality tối đa 2, chờ 40 ms | Batch có padding trái, giữ ánh xạ request |
| Suy luận | Batch trên GPU 0, FP16 SDPA | Giới hạn token batch; logits_to_keep=1; OOM chia batch, batch 1 vẫn lỗi thì dừng | JSON riêng từng request hoặc lỗi, không đổi lỗi thành no |
| Kiểm chứng / xuất | JSON + evidence gốc | Các validator v2.2; luồng chính ghi journal/fsync, CSV theo thứ tự nguồn | approve yes/no/trống, evidence, checkpoint, summary thời gian |

Tài nguyên cần: Kaggle GPU CUDA, Internet tải Qwen/ảnh/trang, bundle và notebook mới; không cần API key. Mặc định workers=4, batch=2, pixels=602112, input=4096, output=512, batch-token-budget=8192. Output ngắn hơn có thể tăng LOCAL_OUTPUT_LIMIT nếu OCR nhiều chữ; giữ trống thay vì kết luận thiếu căn cứ. Không rút gọn nội dung nguồn bằng cắt token âm thầm.

Run mới `pilot_gpu_v2_2_fast1`, không resume lẫn bản cũ. Chạy đủ 50 record, so nhãn và tỷ lệ lỗi với lần trước, đo rows/hour loại thời gian tải model, cache_hits, batch_histogram, OOM và thời gian fetch/parse/preprocess/generate. Kiểm thử offline xác minh concurrency, ánh xạ record, EOS, OOM, checkpoint; không thay thế benchmark GPU thật. Một GPU được sử dụng; chưa triển khai phân tải hai T4 hay continuous batching/vLLM.


## 12. Cải tiến v2.2-fast2 — xác minh tên và kiểm nguồn từng đoạn

Dữ liệu kích hoạt: run Qwen fast1 50 record, 33 yes/17 trống, 12 quyết định so tên semantic viện dẫn chữ không tương đương entity; 9 trang vượt context và 6 trang có ID bằng chứng không hợp lệ.

| Bước | Input | Công nghệ / quy tắc | Output |
|---|---|---|---|
| OCR | Ảnh, không có entity gợi ý | Qwen như trước | Chữ quan sát, trạng thái đọc |
| So tên | Entity, chữ OCR hoặc URL, aliases | Prompt ngắn + validator Python độc lập với quan hệ do model khai; số có chuẩn hóa/ngữ cảnh, alias có chứng cứ, OCR sai khác hẹp | match nếu xác minh được; không chứng minh được thì uncertain và kiểm tiếp |
| Chia nguồn | Trang đã trích xuất và contexts ảnh | Tách block giữ nguyên ID/nội dung, gom khoảng 2.200 ký tự; contexts trước toàn bài | Danh sách đoạn không cắt mất đuôi |
| Kiểm đoạn | Entity, đoạn, ảnh nếu là nhóm | Qwen trả schema ngắn với ID E0/E1; ánh xạ và validate lại với nguồn; quá token chia tiếp | Match có bằng chứng hoặc trạng thái từng đoạn |
| Tổng hợp | Quyết định đoạn + độ phủ | Chỉ vắng tên khi mọi block được kiểm và nguồn không bị cắt; tối đa 24 calls/trang; chưa đủ thì trống | Page decision + chunk_audit, approve theo pipeline |

Cần cung cấp: chỉ bundle/notebook mới và GPU Kaggle hiện có, không API key. Nếu có bản dịch/alias đáng tin, thêm name_overrides.json; không tự biến tên mới do Qwen đoán thành alias. Quy tắc mới áp dụng backend Qwen riêng; phần dùng chung được tách hàm validate/page_blocks để tái sử dụng, không đổi hành vi API local.

Run mới pilot_gpu_v2_2_fast2; không resume fast1. Giữ 4 record workers và batch tối đa 2, cùng 50 indices đã chốt. Bản nguồn fast1 lưu tại versions/kaggle_fast1, output cũ giữ nguyên. Đo cả chất lượng và throughput sau chạy lại; prompt gọn không đảm bảo model 3B hết sai và kiểm nguồn nhiều đoạn có thể chậm hơn.

Kiểm thử cần có: replay 12 quan hệ sai từ fast1, tên đúng và số viết bằng chữ, alias cấu hình, tên xuất hiện cuối bài, chia tiếp khi token dài, block lỗi/thiếu/call cap không thành no, ID bịa không được duyệt, nguồn ngoài context không chứng minh ảnh. Kết quả replay chỉ đánh giá validator trên output cũ, không phải nhãn mới của 50 record.

## 13. API economy v1 — 2.000 dòng đầu CSV

Triển khai riêng api_economy.py. Input: snapshot hiện có, first=2000 trước khi lọc approve, overrides và key trong .env khi --run. Bước 1 chọn prefix, thống kê URL match và tính dự toán offline. Bước 2 URL exact bỏ API; OCR cần thiết dùng cache theo ảnh. Bước 3 so OCR+URL một lượt thay hai. Bước 4 kiểm trang bằng model/validator API v2.2. Output: journal/checkpoint, first_rows.csv, reviewed.csv, usage và summary tại outputs/api_economy_first_2000. Không dùng Batch API hoặc policy Qwen fast2; không giảm giá Batch trong dự toán.

Snapshot: 2.000 pending, 367 URL exact, 1.633 cần kiểm tiếp, 1.471 URL ảnh khác nhau ở nhóm còn lại. Kịch bản 3,93–6,55 USD, thận trọng 9,82 USD; chưa đo API phiên bản mới. Cap mặc định 10 USD bằng reservation trước request; hết cap dừng, record chưa hoàn tất còn pending. Cho resume tăng budget, không đổi code/cấu hình khác. Chi tiết giả định và lệnh chạy ở API_ECONOMY.md.

## 14. API economy v2 — lựa chọn provider/model local

Thêm api_providers.py và --provider/--model vào api_economy.py. Giữ OCR ảnh, so tên gộp và kiểm nguồn, không triển khai ý tưởng bỏ OCR. Provider Gemini dùng generateContent REST, inline JPEG, responseJsonSchema; chuyển usage và finishReason về interface dùng chung để validator vẫn áp dụng. Cache tách provider/model, ledger tính đúng giá mỗi model và gồm Gemini thinking tokens. Không fallback tự động; lỗi API fatal dừng, record còn pending, usage chưa xác nhận giữ dự phòng. Model 2.5/3.5 chọn bằng CLI với output riêng; có --check-model metadata không generate. Tài liệu và lệnh ở LOCAL_MODELS.md; chưa chạy API trả phí khi setup.

## 15. Pilot GPT-6 Luna đối chiếu v2.2

Thêm giá Standard gpt-6-luna và hỗ trợ --baseline-dir trong local runner. --pipeline v2.2 giữ prompt, bước ảnh/URL/nguồn và max output 1.800 của baseline; reasoning none. Mẫu lấy đúng selected_indices từ manifest và kiểm đủ row_id, không thay bằng first50. Input Luna tính bảo thủ 1,25 giá input thường để bao phủ cache-write. Output mới outputs/luna_v2_2_pilot50, selected_rows.csv cho mẫu, không sửa baseline. compare_local_runs.py đối chiếu hai run đủ record và xuất CSV/HTML ở outputs/comparison_v2_2_luna. Chưa gọi API thật khi setup; lệnh chạy/so sánh ở LOCAL_MODELS.md.

## 16. Grouped Luna + địa chỉ chi nhánh

Thêm grouped_pipeline.py, address_rules.py và run_grouped_luna.py. Một worker/nhóm image_url; array ứng viên R0/R1 chứa tên và các thành phần địa chỉ; kiểm nguồn chung theo page_url chuẩn hóa tham số theo dõi. Giữ rule yes đầu tiên đã có thắng cả nhóm, những record khác thành no. Không có yes thì ưu tiên địa chỉ có bằng chứng gắn với ảnh; directory liệt kê mọi địa chỉ không phân biệt được chi nhánh. Nếu chỉ biết thương hiệu, chọn record khớp đầu tiên làm đại diện, ghi GROUP_BRAND_FALLBACK/branch_identified=false; khi địa chỉ chứng minh rõ ghi GROUP_ADDRESS_MATCH/true. Không có bằng chứng giữ trống, no một ứng viên không kéo cả nhóm no.

Input là snapshot mới từ CSV chính hiện tại; phạm vi --first là seed ảnh, mở rộng sang toàn bộ record cùng ảnh ở bất kỳ vị trí trong CSV. Output ở run riêng, không tự sửa file chính/done và không trộn checkpoint per-record cũ. Lệnh/giới hạn heuristic ở GROUPED_LUNA.md. Kiểm thử offline đủ pipeline mới và runner; chưa inference thật nên chưa chốt mức giảm chi phí/chất lượng.


## 17. Cải tiến v3: Grouped Luna qua OpenAI Batch API

- Giữ rule nhóm ảnh và ưu tiên địa chỉ ở phần cải tiến trước; runner mới mặc định execution=batch. Không thay đổi các runner per-record cũ.
- Input: bản sao bất biến của CSV chính trong output; first/start-row chọn seed, mở rộng tất cả record cùng image_url. Output: reviewed.csv, selected_rows.csv, results.jsonl, summary.json, manifest.json và batch/state.json cùng JSONL request/result.
- Bước chuẩn bị: Python stdlib, Pillow, bộ tải ảnh/nguồn sẵn có; tạo profile tên, array địa chỉ có ID và áp dụng nhãn/rule có sẵn. Không gọi VLM tại bước này.
- OCR: mỗi ảnh cần kiểm tạo request Responses có ảnh + OCR schema. Gộp file JSONL, upload Files purpose=batch rồi tạo /batches endpoint=/v1/responses, completion_window=24h. Cần OPENAI_API_KEY và tài khoản có quyền model gpt-6-luna/Batch.
- Nhận kết quả: poll batch ID, tải output/error files, ghép bằng custom_id, kiểm schema. Lưu cache theo payload/model, usage và chi phí Batch có reservation. Không phụ thuộc thứ tự kết quả.
- Kiểm nguồn: chạy tiếp bằng OCR đã lưu; tải ngữ cảnh gắn đúng ảnh, kiểm địa chỉ bằng rule. Những nhóm chưa giải quyết gửi batch tiếp theo với array ứng viên + bằng chứng chung mỗi nguồn. Có thể cần nhiều đợt cho nhiều nguồn.
- Quyết định: địa chỉ mạnh duy nhất ưu tiên; chỉ xác minh thương hiệu thì chọn đại diện đầu tiên theo rule đã duyệt; một yes kéo các record khác cùng ảnh thành no; no riêng lẻ không tự lan cả nhóm; thiếu bằng chứng/lỗi kiểm tra giữ trống.
- Checkpoint trước/sau gửi và sau nhận; resume đối chiếu batch ID/metadata, tránh gửi trùng. Ctrl+C không hủy batch remote. Không tự fallback Standard.
- Tài nguyên/phí: Batch 50% Standard cho cùng token; không phải cam kết chi phí toàn dataset vì số lượt phụ thuộc nhóm/nguồn. Mỗi đợt tối đa 24h, tổng pipeline có thể lâu hơn; không phù hợp nếu phải có toàn bộ kết quả trong vài phút.
- Hướng dẫn và lệnh: tool/GROUPED_LUNA.md. Triển khai chỉ kiểm thử offline, chưa phát sinh phí API; CSV chính/done/ không bị ghi.

### 17.1. Khóa phụ thuộc OCR trước kiểm nguồn

Bản Batch chỉ tạo request kiểm nguồn cho nhóm cần OCR sau khi đã nhận và kiểm response OCR hợp lệ theo custom_id + status completed + schema. Đang chờ OCR thì nhóm tạm dừng. no_text/unreadable vẫn hợp lệ; lỗi ảnh, lỗi API OCR hoặc JSON sai giữ trống phần chưa duyệt và không phát sinh lượt kiểm nguồn. Các fast path nhãn/URL vẫn được quyết định không cần OCR. Kiểm thử riêng xác nhận lúc OCR pending không tải trang/tạo request nguồn và khi OCR invalid không tiếp tục gọi model.

## 18. Cải tiến v4: áp dụng rule nhãn mới trực tiếp trong pipeline

Đã chuyển các yêu cầu duyệt thủ công thành policy user-rules-v4 cho Standard và Batch. Không còn chỉ sửa CSV hậu xử lý: nhóm thiếu ngữ cảnh ảnh yes, các lỗi kiểm tra khác no; model xác định đối tượng khác/địa điểm mâu thuẫn no; chưa rõ chi nhánh/mô tả chung yes; model chọn/loại ứng viên hợp lệ thì tuân theo trực tiếp, bỏ guard exact_match/evidence nguyên văn/entity_type cho quyết định đó. Giữ kiểm schema/ID thật, checkpoint, ngân sách và phụ thuộc OCR trước kiểm nguồn.

Model dùng JSON có các tập ID theo nguyên nhân thay vì phải đoán explanation. Mặc định --group-yes multiple cho các nhãn fallback, có thể chọn single. Model chọn rõ winner vẫn được chọn làm đại diện. Code mới, manifest mới và output mới; không trộn resume/cache quyết định cũ. Hướng dẫn và giới hạn chính xác ở tool/GROUPED_USER_RULES_V4.md. Chỉ kiểm thử offline, không ghi lại các nhãn đã duyệt và không gọi model trả phí.

## 19. Bộ điều phối Batch song song (v4-parallel1)

Thêm --max-active-batches 1–8 cho run_grouped_luna.py, giữ cùng policy user-rules-v4 đã test pilot. Claim request trước upload, giới hạn số job remote, poll mọi job, đánh thức đúng nhóm đã có OCR, và lấp slot bằng request sẵn sàng. Không dùng barrier chờ toàn bộ OCR của dataset. Resume không tạo job trùng; ngân sách dùng chung. Thêm --unlabeled-only cho Batch để chọn đủ first dòng approve trống rồi mở rộng nhóm như Standard. Tài liệu/lệnh tại GROUPED_USER_RULES_V4.md. Chỉ thử bằng API giả lập, không gọi API trả phí hoặc sửa CSV chính.
# Cải tiến v5 — 18/11/2026

Đã triển khai trên Standard local OpenAI và ShopAIKey: ảnh không xác nhận trong
nguồn để trống; ảnh có thật nhưng thiếu chữ vẫn yes; tỉnh/thành phố không tự đủ
chọn chi nhánh; mâu thuẫn thực thể/địa điểm/vai trò ưu tiên hơn nguồn chung; mở rộng
yes cho tên tương đương ngay cuối nhóm, có audit và không thêm request. Giữ output
v5 riêng, không resume lẫn v4. Chi tiết đầu vào/đầu ra và lệnh thử tại
[GROUPED_USER_RULES_V5.md](GROUPED_USER_RULES_V5.md). Chưa chạy đối chứng API v5;
kiểm thử trong lượt triển khai này dùng dữ liệu mô phỏng và preview không trả phí.

