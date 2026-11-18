# Ngữ cảnh duyệt ảnh — bắt đầu đọc tại đây

Cập nhật: 18/11/2026. Đây là chỉ dẫn để một phiên ChatGPT khác hiểu bài toán và
duyệt thử; các báo cáo cũ trong repo không phải nhãn chuẩn.

## Dữ liệu và mục tiêu

- Dữ liệu công khai trong repo: `data/general_10m_part_02.csv`, 57.522 record,
  tất cả `approve` đang trống tại thời điểm chuẩn bị repo.
- CSV vận hành `general_10m_part_02.csv` ở root chỉ giữ local. Bản GitHub giữ đủ
  record nhưng để trống các URL có tên file giống mẫu API key, tránh đưa chuỗi
  bị GitHub Push Protection chặn lên repo. Đây là biện pháp lọc snapshot công
  khai, không phải kết luận các ảnh đó sai. Record thiếu URL cần kiểm nguồn hoặc
  để trống approve; không suy diễn là no. CSV gốc local không bị thay đổi.
- Các trường: `entity_id`, `entity_name`, `leaf_label`, `image_url`, `image_width`,
  `image_height`, `page_url`, `page_title`, `image_domain`, `mo_ta`, `approve`.
- Cần kiểm tra sự phù hợp giữa **entity_name — ảnh — nguồn page_url**.
- `mo_ta` do VLM sinh từ dữ liệu đã crawl, không phải bằng chứng độc lập. Không
  dựa vào mô tả đó để kết luận danh tính ảnh.
- `page_title`, slug URL và tên file ảnh cũng có thể mô tả chung cả bài; phân
  biệt tên ở caption/alt của đúng ảnh với tên chỉ xuất hiện ở phần khác.

## Thứ tự tài liệu

1. File này: mục đích và quy trình duyệt trực tiếp.
2. `tool/GROUPED_USER_RULES_V5.md`: policy pipeline mới nhất và những thay đổi đã
   được người dùng đồng ý.
3. `tool/RULE_PROPAGATE_GROUP_YES.md`: các tên tương đương, địa chỉ tương thích
   và những trường hợp không được tự mở rộng yes.
4. `rule_approve_image.md`: tiêu chí nhìn ảnh trực tiếp khi được yêu cầu kiểm
   chất lượng nội dung; không hiểu thành “cứ có logo là no”.
5. `AGENTS.md`: quy ước sửa, sao lưu và chuyển CSV vào done.

`tool/GROUPED_USER_RULES_V4.md`, các hướng dẫn model cũ, thống kê thử nghiệm và
phần lịch sử trong plan chỉ để tham khảo. Khi khác nhau, dùng chỉ dẫn mới nhất của
người dùng; policy mặc định hiện tại là **user-rules-v5**.

## Luồng duyệt một nhóm ảnh

1. Chọn số lượng record nhỏ mà người dùng yêu cầu, ghi rõ phạm vi. Gom các record
   có **image_url giống hệt nhau**, kể cả record cùng nhóm nằm ngoài phạm vi seed.
   Không gộp tất cả URL rỗng thành một nhóm.
2. Mở ảnh thật và đọc chữ nhìn thấy, không tự đoán tên/địa điểm từ cảnh chung.
   Các hoạt động trong lớp học không đủ xác định trường; chữ trên tuyến xe hay
   biển tòa nhà phía xa không tự xác định nơi chụp.
3. Khớp tên với OCR, image_url và page_url theo các rule hiện tại. Có thể chấp
   nhận tên riêng, tên viết tắt, số/ngày tháng và bí danh đã xác nhận; tỉnh/thành
   phố chung chưa đủ xác định cơ sở. Ghi rõ loại bằng chứng của quyết định.
4. Nếu cần kiểm nguồn, mở page_url, tìm **đúng ảnh** và chữ gắn với ảnh: caption,
   alt hoặc đoạn văn quanh ảnh. Tránh lấy caption của ảnh liền kề hoặc mục của
   thực thể khác. Không thấy ngữ cảnh không đồng nghĩa ảnh chắc chắn vắng mặt.
5. Đánh nhãn theo các nguyên tắc dưới đây; sau đó mở rộng yes trong chính nhóm
   cho các tên thực sự cùng thực thể và địa chỉ tương thích.

## Quyết định hiện tại

- Tên riêng phù hợp từ bằng chứng OCR/URL được chấp nhận theo pipeline, nhưng
  không bỏ qua bằng chứng mâu thuẫn rõ đã phát hiện trong ảnh/nguồn.
- Tìm thấy đúng ảnh trong nguồn nhưng không có chữ gắn với ảnh: yes.
- Không xác nhận được ảnh trong nguồn, không tải được ảnh/trang, hoặc công cụ
  không kiểm tra được: để trống, kèm lý do riêng. Không giả lập việc đã mở nguồn.
- Chữ gắn với ảnh xác định rõ thực thể khác hoặc địa điểm/vai trò không phù hợp:
  no. Bằng chứng này ưu tiên hơn rule nguồn mô tả chung/chưa rõ cơ sở.
- Nguồn chỉ mô tả chung hoặc chưa xác định chi nhánh có thể yes theo policy người
  dùng, **khi không có bằng chứng mâu thuẫn rõ**. Không đổi thiếu bằng chứng thành
  câu khẳng định chắc chắn đã xác nhận danh tính.
- Cùng tuyến đường sắt không chứng minh là cùng ga. Sân bay không phải công ty
  dịch vụ sân bay. Ảnh nhà ga có thể phù hợp với chính sân bay cùng tên.
- Nếu phải chọn chi nhánh, dùng địa chỉ/số nhà/đường/tên cơ sở gắn với đúng ảnh.
  Không chọn chỉ vì “TP.HCM”, “Hà Nội” hoặc danh sách địa chỉ chung của thương hiệu.
- Một nhóm **được phép có nhiều yes** khi các record là cách gọi cùng thực thể,
  địa chỉ con–cha tương thích. Không giữ duy nhất một yes rồi tự loại tất cả bí danh.
- Không lan truyền sang chi nhánh khác, tên khác, số định danh khác, hoặc thành
  phần khác vai trò (hồ so với khu đô thị, cửa hàng so với trung tâm thương mại).
- Giữ nguyên nhãn người dùng đã duyệt nếu chưa được yêu cầu rà lại.

## Ví dụ đã rà

- `Times City`, `Vinhomes Times City`, `Khu Vinhomes Times City Hai Bà Trưng`,
  `Chung cư Vinhomes Times City` (tên chung, không chỉ tòa cụ thể) là các tên tổng
  thể đã chấp nhận trong cùng nhóm ảnh. Không tự coi hồ Times City, cửa hàng May 10
  hoặc phân khu Park Hill Premium là cùng thực thể tổng thể.
- `Sân bay quốc tế Phú Bài` và cùng tên thêm `(Huế)` có thể cùng yes.
- Ảnh có biển bến xe Yên Nghĩa, nguồn nói tuyến Cát Linh–Hà Đông: chưa thể lấy
  tên cả tuyến làm bằng chứng duyệt ga Cát Linh hoặc La Khê.
- Một ảnh xuất hiện dưới nhiều tên nghĩa trang khác tỉnh không được tự yes cả
  nhóm chỉ vì code chưa tìm thấy ngữ cảnh trong nguồn.

## Đầu ra và bảo toàn dữ liệu

- Mặc định chỉ duyệt thử theo phạm vi được giao; không tự chạy hết 57.522 record.
- Xuất bản kết quả riêng, giữ nguyên các cột, thứ tự và dữ liệu gốc; chỉ sửa
  `approve` thành `yes`, `no` hoặc chuỗi rỗng. Ghi lý do, trích dẫn, URL và các
  record cùng nhóm trong bảng audit riêng.
- Ghi cả số dòng snapshot và các trường nhận diện; số dòng sẽ thay đổi sau khi
  CSV chính bị cắt. Đối chiếu record theo đầy đủ các cột trừ `approve`.
- Báo số seed, số record sau mở rộng nhóm, số nhóm, yes/no/trống và phần chưa
  kiểm tra được. Không báo độ chính xác khi chưa có nhãn chuẩn độc lập.
- Không sửa/cắt CSV chính hoặc ghi vào done nếu người dùng chưa yêu cầu thao tác
  đó. Khi có yêu cầu, áp dụng đầy đủ `AGENTS.md`.
- Repo không chứa API key, cache ảnh/HTML, backup, done hay output cũ. Các đường
  dẫn đó trong tài liệu chỉ mô tả môi trường local; không giả định chúng tồn tại.

## Prompt gợi ý cho phiên mới

> Đọc LABELING_CONTEXT.md và các tài liệu được dẫn ở đó. Dùng CSV chính làm dữ
> liệu đầu vào. Duyệt thử 50 record chưa có nhãn đầu tiên, mở rộng các record cùng
> image_url ngoài phạm vi seed. Dùng công cụ mở ảnh/nguồn thật để kiểm tra; phần
> không truy cập được để trống. Xuất CSV kết quả riêng và audit lý do; chưa sửa
> CSV chính. Trước khi thực hiện, xác nhận đã truy cập được CSV và số record thực
> tế; nếu môi trường không đọc được file hoặc không xem được ảnh, báo rõ giới hạn.
