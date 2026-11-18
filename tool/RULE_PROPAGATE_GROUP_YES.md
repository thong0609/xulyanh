# Rule mở rộng nhãn yes trong nhóm cùng ảnh

Phiên bản: 1.0 — ngày 14/11/2026.

Bổ sung 18/11/2026: runner Standard policy `user-rules-v5` thực hiện mở rộng bí danh
ngay cuối mỗi nhóm qua `group_aliases.py`, theo phạm vi bảo thủ hơn: tự đổi no do
`GROUP_OTHER_RECORD_SELECTED`, giữ nhãn có sẵn trong input, lỗi pending và no do
mâu thuẫn/loại rõ. Bước hậu kiểm riêng theo tài liệu này vẫn có thể rà rộng hơn bằng
danh sách cặp đã xác nhận. Xem [GROUPED_USER_RULES_V5.md](GROUPED_USER_RULES_V5.md).

## Mục đích và phạm vi

Khi người dùng yêu cầu “rà các nhóm và sửa các tên tương tự như lần trước”, áp dụng file này cho CSV kết quả được chỉ định. Đây là bước hậu kiểm nhãn, không phải thay thế toàn bộ pipeline OCR/URL/nguồn hoặc chính sách API v4.

Trong mỗi nhóm cùng `image_url`, lấy record đã có `approve=yes` làm mốc. Record khác cùng nhóm, có tên biểu diễn cùng thực thể và địa chỉ tương thích, được đổi thành `yes`, kể cả đang là `no`.

**Một nhóm được phép có nhiều yes. Không gán no cho các record khác chỉ vì vừa thêm một yes.**

## Ngoại lệ kiểm ảnh — bổ sung 16/11/2026

Với run bật `--image-quality`, phải đọc `quality_checks/` trước khi mở rộng yes.
Ảnh có `quality_decision=reject` (spam, watermark lớn, screenshot, chất lượng kém,
v.v.) hoặc `review` (cần người xem lại) không được đổi thành yes bằng rule alias,
kể cả nhóm đang có mốc yes từ kết quả cũ. Hai script trong file này đã có chặn này.
Nếu sao chép CSV ra thư mục khác để hậu kiểm, sao chép cả `quality_checks/` đi cùng;
không coi việc thiếu metadata kiểm ảnh là xác nhận ảnh đã đạt chất lượng.

## Đầu vào và đầu ra

- Đầu vào: CSV kết quả có `entity_name`, `image_url`, `approve`. Có thể đọc thêm thông tin loại thực thể, địa chỉ và `page_url` nếu có để phân biệt.
- Đầu ra: chính CSV được chỉ định, chỉ đổi `approve` của những record đã xác nhận khớp thành `yes`; giữ nguyên thứ tự, số dòng và các trường còn lại.
- Kèm theo: bản sao lưu trước sửa, danh sách thay đổi và thống kê trước/sau.
- Không dùng `description`/`mo_ta` do VLM sinh làm bằng chứng độc lập xác nhận danh tính.

## Cách thực hiện

1. Đọc toàn bộ CSV và ghi nhận hash, số dòng, số yes/no/blank.
2. Nhóm theo **giá trị image_url giống nhau**. URL ảnh rỗng không được gộp thành một nhóm. Không tự gộp hai URL khác nhau dù ảnh trông giống nhau.
3. Chụp danh sách record `yes` làm mốc tại thời điểm bắt đầu lượt rà. Nhóm không có mốc yes thì giữ nguyên.
4. So từng record chưa yes với các mốc yes **trong chính nhóm ảnh đó**. Không bắt buộc `page_url` giống nhau.
5. Chuẩn hóa và kiểm tra các biến thể bên dưới; đọc lại từng cặp chưa chắc chắn trước khi quyết định. Điểm giống chuỗi chỉ dùng để tìm ứng viên.
6. Lập danh sách đề xuất: record cần sửa, mốc yes, hai tên gốc và lý do khớp. Không lấy record vừa chuyển yes làm mốc để nối tiếp trong cùng lượt rà.
7. Sao lưu, kiểm tra CSV chưa bị thay đổi từ lúc đọc, rồi áp dụng danh sách đã rà.
8. Đọc lại CSV để xác nhận chỉ những ô approve được chỉ định đã đổi; thống kê và báo đường dẫn audit cho người dùng.

Không gọi API/model trả phí chỉ để thực hiện bước hậu kiểm này nếu người dùng chưa yêu cầu. Trường hợp chưa xác định được thì giữ nhãn hiện tại, không ép yes hoặc no.

## Các biến thể được chấp nhận

Chấp nhận khi vẫn xác định được cùng tên riêng và không có mâu thuẫn rõ về địa điểm hoặc loại thực thể:

| Kiểu biến thể | Ví dụ | Cách xử lý |
| --- | --- | --- |
| Chữ hoa/thường, dấu, dấu câu, khoảng trắng | `INschool` / `INSchool` | Chuẩn hóa để so |
| Địa chỉ viết tắt | `Q7` / `Q.7` / `Quận 7`, `TP.HCM` / `TP Hồ Chí Minh` | Quy đổi đúng ngữ cảnh |
| Một bên ghi địa chỉ đầy đủ hơn | `Kids House - Tân Định - Bến Cát` / cùng tên thêm `(Bến Cát, Bình Dương)` | Cho yes nếu không đổi cơ sở |
| Địa danh nằm đầu/cuối hoặc trong ngoặc | `Hanoi Lotte Mall West Lake` / `Lotte Mall West Lake (Hà Nội)` | Tách địa danh khỏi tên để so |
| Đảo vị trí từ chỉ địa điểm | `Vincom Plaza Hải Phòng (Imperia)` / `Vincom Plaza Imperia Hải Phòng` | Giữ đủ tên chi nhánh khi so |
| Cách viết Anh–Việt tương đương đã xác nhận | `Hanoi` / `Hà Nội`, `Saigon Centre` / `Sài Gòn Center` | Không coi mọi tên Anh–Việt gần nghĩa là tương đương |
| Lỗi chính tả nhẹ trong tên riêng | `Cresent Mall` / `Crescent Mall` | Chấp nhận khi tên và địa điểm còn lại tương thích |
| Tên số/ngày tháng viết khác | `19/12` / `19 tháng 12`, `Tháng Tám` / `Tháng 8` | So giá trị số trong tên, không lấy số bất kỳ làm bằng chứng |
| Lặp từ hoặc khác từ chỉ loại chung | `Nhà máy nước BOO Thủ Đức` / `Nhà máy nước BOO Nước Thủ Đức` | Bỏ từ lặp, giữ yếu tố phân biệt |
| Bí danh có trong tên mốc | `Bốt Hàng Đậu / Tháp nước Hàng Đậu` / `Tháp nước Hàng Đậu (Bốt Hàng Đậu)` | Có thể nhận là hai cách gọi cùng thực thể |
| Thêm mô tả góc chụp, hoạt động, ngành hàng | `Phố Hàng Bạc` / `Phố Hàng Bạc tiệm vàng`; cùng tên mall thêm `mặt tiền` | Chấp nhận khi chỉ bổ sung mô tả, không đổi sang một thực thể khác |

Với nhóm Lotte West Lake đã rà: các biến thể có `Lotte`, `West Lake` và `Hanoi/Hà Nội/Tây Hồ` đã được xác nhận cùng thực thể. Không suy rộng thành quy tắc “West Lake luôn đồng nghĩa Tây Hồ” trong mọi tên.

Với Times City tại Hai Bà Trưng, Hà Nội, đã rà ngày 17/11/2026: `Times City`, `Vinhomes Times City`, `Khu Vinhomes Times City Hai Bà Trưng`, `Khu đô thị Vinhomes Times City`, `Chung cư Vinhomes Times City` (tên chung, không chỉ tòa cụ thể), và `Times City — Vinhomes Times City` là các cách gọi được chấp nhận trong cùng nhóm ảnh có mốc yes. Không tự mở rộng sang hồ Times City, cửa hàng May 10, phân khu Park Hill Premium hoặc tên ghép `Times City, Royal City`. Đây là các bí danh đã rà, không phải quy tắc bỏ thương hiệu, phân khu hoặc loại thực thể cho mọi dự án. Heuristic hiện tại chưa nhận đủ các cặp này; dùng danh sách cặp đã rà cho snapshot tương ứng.

## Những trường hợp không tự mở rộng yes

- **Khác số định danh:** Sao Sáng 3 / Sao Sáng 5; Hòa Liên / Hòa Liên 2. Không bỏ số chỉ vì phần tên còn lại giống nhau.
- **Khác tên riêng:** Yên Sở / Yên Nghĩa; Bình Hưng / Bình Hưng Hòa.
- **Mâu thuẫn địa điểm:** cùng tên Nguyễn Văn Linh nhưng một bên Cần Thơ, bên kia TP.HCM; cùng trường nhưng khác quận được ghi rõ.
- **Chỉ chung thương hiệu, thiếu cơ sở:** `Lotte Department Store` chưa đủ để nhận là `Lotte Mall West Lake`; `Aeon Mall` chưa xác định được Bình Tân hay Bình Dương New City trong nhóm có nhiều cơ sở.
- **Khác chi nhánh có tên rõ:** Vincom Imperia / Vincom Lê Thánh Tông; Maximark Cộng Hòa / Maximark 3 Tháng 2.
- **Thực thể con khác vai trò:** cửa hàng Coach trong Saigon Centre không tự là tòa nhà Saigon Centre; May 10 trong Savico Megamall không tự là cả trung tâm thương mại.
- **Khác loại thực thể dù cùng tên hoặc vị trí:** công viên / trạm bơm / cầu; khu đô thị Royal City / Vincom Mega Mall Royal City; Crescent Plaza / Crescent Mall.
- **Tên ghép nhiều địa điểm:** `Hàng Buồm/Hàng Đào` không tự tương đương riêng `Hàng Buồm`. Chỉ chấp nhận dấu `/` khi đã xác nhận là bí danh cùng thực thể hoặc ký hiệu số/ngày tháng.
- **Địa chỉ chỉ gần giống:** cùng thành phố, cùng tỉnh hoặc có nhiều từ địa chỉ chung chưa đủ xác nhận cùng cơ sở. Quan hệ địa chỉ con–cha cần tương thích thực tế, không chỉ là tập từ chứa nhau.

Các trường hợp này giữ nguyên nhãn trong lượt hậu kiểm; file này không yêu cầu tự đổi chúng sang no. Nếu người dùng yêu cầu riêng khác với rule này, áp dụng yêu cầu mới và ghi lại ngoại lệ.

## Bảo toàn dữ liệu và kiểm chứng

- Chỉ sửa file kết quả người dùng đang chỉ định. Không tự sửa CSV chính ở root, không tự cắt/ghép/xóa record.
- Không động vào `done/`; bỏ qua `thu_nghiem/`, trừ khi có yêu cầu mới chỉ rõ khác.
- Lưu script, bản copy, backup và audit trong `tool/`.
- Không sửa `results.jsonl`, journal API hoặc thống kê chi phí để giả như model đã trả các nhãn hậu kiểm. CSV và audit ghi nhận đây là thay đổi sau chạy model.
- Nếu file thay đổi trong lúc rà, dừng ghi, đọc lại và đối chiếu; không ghi đè thao tác duyệt của người dùng.
- Audit cần có: hash trước/sau, hàng dữ liệu (không tính header), row ID nếu có, tên trước sửa, nhãn cũ/mới, hàng/tên mốc yes, image_url và lý do.
- Báo số record đổi, số nhóm có thay đổi, tổng yes/no/blank sau sửa. Nếu server HTML đang mở, hướng dẫn dừng rồi chạy lại để tải CSV mới.

## Công cụ hiện có và giới hạn

- `tool/propagate_group_yes.py`: tìm cặp bằng chuẩn hóa tên/địa chỉ và heuristic; có preview mặc định, `--apply` để ghi. **Không bao phủ toàn bộ biến thể ngữ nghĩa trong file này; phải kiểm tra đề xuất trước khi áp dụng.**
- `tool/apply_reviewed_group_aliases.py`: áp dụng danh sách cặp đã rà trong JSON, kiểm tra hash, mốc yes, cùng nhóm ảnh và tên gốc; có backup/audit. Script này không tự xác nhận ý nghĩa của cặp tên.
- Danh sách `reviewed_alias_pairs_20261114.json` trong output 4.000 là kết quả rà cho đúng snapshot đó. Không dùng lại số dòng này cho CSV khác hoặc sau khi file đổi hash.

Lệnh cho một danh sách cặp mới đã được rà:

```bash
# Xem thống kê đề xuất, chưa sửa CSV:
python3 tool/apply_reviewed_group_aliases.py --review PATH_TO_NEW_REVIEW.json

# Áp dụng sau khi đã kiểm tra các cặp:
python3 tool/apply_reviewed_group_aliases.py --review PATH_TO_NEW_REVIEW.json --apply
```

Lần sau có thể yêu cầu: **“Áp dụng tool/RULE_PROPAGATE_GROUP_YES.md cho file …; rà thêm các biến thể chưa được script nhận ra và cập nhật CSV.”**
