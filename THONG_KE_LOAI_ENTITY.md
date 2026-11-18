# Thống kê loại entity trong CSV chính

Nguồn: `general_10m_part_02.csv`. Đếm nguyên giá trị `leaf_label`, chưa gộp các nhãn cùng loại nhưng khác vùng hoặc phân nhóm. Không sử dụng `done/` hoặc `thu_nghiem/`.

- Tổng: 98.049 dòng; 19.704 entity duy nhất; 287 loại theo `leaf_label`.
- Số dòng ảnh là số bản ghi, không phải số ảnh khác nhau theo nội dung. Số entity đếm riêng trong từng loại; một entity có thể mang nhiều loại.

| STT | Loại entity (`leaf_label`) | Số dòng ảnh | Số entity | Số URL ảnh riêng biệt | Tỷ lệ dòng |
|---:|---|---:|---:|---:|---:|
| 1 | Trường mầm non & nhà trẻ | 17457 | 5750 | 11499 | 17.80% |
| 2 | Chợ truyền thống | 3668 | 808 | 3145 | 3.74% |
| 3 | Nhà thờ Công giáo — Giáo tỉnh Hà Nội (TGP Hà Nội, GP Bắc Ninh, Bùi Chu, Hải Phòng, Hưng Hóa, Lạng Sơn-Cao Bằng, Phát Diệm, Thái Bình, Thanh Hóa, Vinh, Hà Tĩnh) | 3532 | 1119 | 2272 | 3.60% |
| 4 | Cửa hàng thời trang thương hiệu (Việt Tiến, An Phước, Routine, Canifa, Yody, Owen, Couple TX...) | 3458 | 372 | 1736 | 3.53% |
| 5 | Khu đô thị mới cao cấp Hà Nội (Vinhomes Riverside/Ocean Park/Smart City, Royal City, Times City, Ciputra, Gamuda Gardens, Splendora…) | 2992 | 321 | 2562 | 3.05% |
| 6 | Trung tâm thương mại (TTTM / Shopping Mall) | 2952 | 364 | 2307 | 3.01% |
| 7 | Đường vành đai & trục chính đô thị có danh (Vành đai 1–4 Hà Nội/TP.HCM; đại lộ–trục đặt tên: Võ Nguyên Giáp, Phạm Văn Đồng, Mai Chí Thọ, Võ Văn Kiệt, Phạm Hùng...) | 2376 | 160 | 2132 | 2.42% |
| 8 | Phố thương mại & phố chợ truyền thống | 2254 | 192 | 1944 | 2.30% |
| 9 | Khu chung cư hỗn hợp & phức hợp đô thị đa chức năng | 1784 | 185 | 1723 | 1.82% |
| 10 | Sân vận động | 1630 | 168 | 1279 | 1.66% |
| 11 | Khu đô thị mới cao cấp ĐBSH & các tỉnh phía Bắc khác (Ecopark Hưng Yên, Vinhomes các tỉnh, KĐT Hạ Long/Hải Phòng/Bắc Ninh/Bắc Giang…) | 1624 | 206 | 1393 | 1.66% |
| 12 | Trường trung học cơ sở (THCS) | 1469 | 233 | 1303 | 1.50% |
| 13 | Quảng trường | 1391 | 119 | 1255 | 1.42% |
| 14 | Hồ công cộng đô thị | 1112 | 180 | 1036 | 1.13% |
| 15 | Cảng hàng không & sân bay | 1066 | 123 | 903 | 1.09% |
| 16 | Cao ốc văn phòng thương mại hạng B (toàn quốc, gộp; có danh xưng & ảnh) | 942 | 216 | 850 | 0.96% |
| 17 | Công viên đô thị tại TP.HCM & vùng Đông Nam Bộ | 916 | 138 | 806 | 0.93% |
| 18 | Siêu thị & đại siêu thị | 861 | 140 | 692 | 0.88% |
| 19 | Bến cảng biển — miền Nam & ĐBSCL (TP.HCM, Bà Rịa–Vũng Tàu/Cái Mép, Đồng Nai, Cần Thơ, ĐBSCL) | 839 | 105 | 682 | 0.86% |
| 20 | Vườn ươm & cơ sở sản xuất giống cây trồng (ngoài trời / lâm-nông nghiệp) | 833 | 99 | 769 | 0.85% |
| 21 | Công viên đô thị Tây Nguyên & Đồng bằng sông Cửu Long (Đà Lạt, Buôn Ma Thuột, Cần Thơ, Mỹ Tho...) | 820 | 69 | 720 | 0.84% |
| 22 | Bến xe khách — cấp tỉnh / đầu mối lớn (loại 1–2 theo QCVN) | 809 | 89 | 648 | 0.83% |
| 23 | Bến cảng biển — miền Trung (Thanh Hóa → Bình Thuận: Nghi Sơn, Đà Nẵng, Dung Quất, Quy Nhơn, Vân Phong) | 786 | 90 | 664 | 0.80% |
| 24 | Khu đô thị vệ tinh & thành phố mới quy hoạch (Hòa Lạc, Sơn Tây, Phú Mỹ, Nhơn Trạch, Bình Dương New City, Thủ Thiêm…) | 772 | 34 | 769 | 0.79% |
| 25 | Đại lý & showroom ô tô (Toyota, Hyundai, VinFast, Ford, Mercedes... 3S/4S) | 768 | 123 | 668 | 0.78% |
| 26 | Doanh trại & căn cứ quân sự lịch sử | 715 | 90 | 662 | 0.73% |
| 27 | Tòa nhà hỗn hợp đa năng (văn phòng – căn hộ – TTTM) | 704 | 159 | 663 | 0.72% |
| 28 | Nghĩa trang liệt sĩ tỉnh – huyện | 700 | 182 | 560 | 0.71% |
| 29 | Công viên đô thị Bắc Trung Bộ & Duyên hải miền Trung (Thanh Hóa→Khánh Hòa: Vinh, Huế, Đà Nẵng, Nha Trang...) | 693 | 91 | 655 | 0.71% |
| 30 | Vườn hoa & hoa viên đô thị — miền Trung & Tây Nguyên (Đà Lạt, Huế, Đà Nẵng, Nha Trang...) | 661 | 52 | 608 | 0.67% |
| 31 | Nghĩa trang liệt sĩ vùng Bắc Trung Bộ | 659 | 102 | 478 | 0.67% |
| 32 | Công viên đô thị các thành phố miền Bắc & Trung du–miền núi phía Bắc (Hải Phòng, Quảng Ninh, Thái Nguyên, Lào Cai...) | 655 | 71 | 596 | 0.67% |
| 33 | Sân golf | 651 | 104 | 587 | 0.66% |
| 34 | Kênh thoát nước & rạch tiêu đô thị — TP.HCM & Đông Nam Bộ (Nhiêu Lộc – Thị Nghè, Tân Hóa – Lò Gốm, Tàu Hủ – Bến Nghé, Tham Lương – Bến Cát...) | 649 | 71 | 544 | 0.66% |
| 35 | Siêu thị điện máy (Điện Máy Xanh, Điện Máy Chợ Lớn, Nguyễn Kim, Pico, Media Mart, HC...) | 630 | 116 | 366 | 0.64% |
| 36 | Cầu đồng bằng sông Hồng (cầu vượt sông Hồng–Thái Bình–Đuống–Đáy–Luộc ở Bắc Ninh, Hưng Yên, Hải Dương, Hải Phòng, Thái Bình, Nam Định, Hà Nam, Ninh Bình, Vĩnh Phúc có danh) | 627 | 119 | 557 | 0.64% |
| 37 | Khu đô thị mới cao cấp TP.HCM (Phú Mỹ Hưng, Vinhomes Central Park/Grand Park, Sala Đại Quang Minh-Thủ Thiêm, Celadon City…) | 612 | 178 | 540 | 0.62% |
| 38 | Khu đô thị mới cao cấp Đông Nam Bộ & ĐBSCL khác (Aqua City/Waterpoint, Bình Dương New City, KĐT Đồng Nai/Long An/Cần Thơ…) | 604 | 66 | 583 | 0.62% |
| 39 | Nhà thi đấu thể thao đa năng | 589 | 158 | 490 | 0.60% |
| 40 | Khu đô thị mới cao cấp miền Trung & Tây Nguyên (FPT City Đà Nẵng, Vinhomes Ocean Park Đà Nẵng, Phú Mỹ An, KN Paradise Cam Ranh, Eco Charm…) | 575 | 108 | 557 | 0.59% |
| 41 | Khu đô thị sinh thái & thông minh (Ecopark, Vinhomes Smart City, FPT City, Phú Mỹ Hưng eco-zone, Aqua City…) | 571 | 57 | 557 | 0.58% |
| 42 | Resort & khu nghỉ dưỡng | 558 | 114 | 469 | 0.57% |
| 43 | Cảng & bến thủy nội địa — đồng bằng Nam Bộ (hệ sông Mê Kông – Đồng Nai) | 545 | 79 | 513 | 0.56% |
| 44 | Pháo đài & công sự kiên cố | 526 | 53 | 509 | 0.54% |
| 45 | Cửa hàng giày dép & phụ kiện (Biti's, Juno, Vascara, Ananas, các store sneaker...) | 518 | 87 | 354 | 0.53% |
| 46 | Tòa nhà văn phòng hạng A/A+ & biểu tượng đô thị (Landmark 81, Bitexco, Keangnam/Landmark 72, Lotte Center, Capital Place, IFC One Saigon, Saigon Centre, Vietcombank/VietinBank/Techcombank Tower...) | 513 | 85 | 389 | 0.52% |
| 47 | Khu tái định cư Nam Bộ (TĐC Thủ Thiêm & dự án đô thị TP.HCM; TĐC sạt lở/sắp xếp dân cư ĐBSCL) | 497 | 48 | 358 | 0.51% |
| 48 | Cửa hàng điện thoại & công nghệ (Thế Giới Di Động, FPT Shop, CellphoneS, Viettel Store, Hoàng Hà...) | 482 | 133 | 325 | 0.49% |
| 49 | Vườn hoa & hoa viên đô thị — TP.HCM & vùng Đông Nam Bộ | 476 | 41 | 452 | 0.49% |
| 50 | Cao ốc văn phòng thương mại hạng C (toàn quốc, gộp; danh xưng ổn định & có ảnh) | 472 | 122 | 463 | 0.48% |
| 51 | Phố đi bộ & tuyến đi bộ đô thị | 450 | 116 | 358 | 0.46% |
| 52 | Khu nhà ở xã hội & nhà ở công nhân Bắc Bộ (Đặng Xá, Ecohome HN; nhà ở công nhân KCN Bắc Ninh, Hải Phòng, Thái Nguyên…) | 446 | 48 | 426 | 0.45% |
| 53 | Tòa nhà hỗn hợp đa năng (văn phòng – căn hộ – TTTM): Vinhomes/Times City/Sun Grand mixed-blocks, The Manor, Saigon Pearl, Masteri, Vincom mixed-use, Mplaza... | 433 | 115 | 429 | 0.44% |
| 54 | Tượng đài sự kiện & biểu tượng tập thể — Nam Trung Bộ, Tây Nguyên & Nam Bộ (Mẹ VN Anh hùng Quảng Nam, Đồng Khởi Bến Tre, Chiến thắng Núi Thành, Đội du kích...) | 419 | 54 | 379 | 0.43% |
| 55 | Nghĩa trang liệt sĩ vùng Trung du & miền núi Bắc Bộ | 403 | 94 | 296 | 0.41% |
| 56 | Cửa khẩu quốc tế đường bộ | 399 | 31 | 391 | 0.41% |
| 57 | Làng cổ vùng cao & dân tộc thiểu số | 399 | 141 | 339 | 0.41% |
| 58 | Kho hàng & bãi hàng thông thường | 391 | 85 | 372 | 0.40% |
| 59 | Trung tâm logistics & phân phối | 391 | 63 | 364 | 0.40% |
| 60 | Tượng đài sự kiện & biểu tượng tập thể — miền Bắc & Bắc Trung Bộ (Mẹ VN Anh hùng, Tổng tiến công, công nhân–nông dân, thanh niên xung phong, dân công hỏa tuyến...) | 377 | 36 | 334 | 0.38% |
| 61 | Bến cảng biển — miền Bắc (Quảng Ninh, Hải Phòng, Thái Bình, Nam Định) | 345 | 68 | 278 | 0.35% |
| 62 | Mộ & khu lưu niệm danh nhân văn hóa-khoa học | 330 | 37 | 271 | 0.34% |
| 63 | Lăng tẩm & mộ vua chúa phong kiến | 326 | 42 | 298 | 0.33% |
| 64 | Cảng & bến thủy nội địa — đồng bằng Bắc Bộ (hệ sông Hồng – Thái Bình) | 325 | 41 | 311 | 0.33% |
| 65 | Nghĩa trang liệt sĩ vùng Đông Nam Bộ | 324 | 48 | 280 | 0.33% |
| 66 | Tượng đài & đài tưởng niệm liệt sĩ — Quảng Bình – Quảng Trị – TT Huế (tuyến lửa, vĩ tuyến 17, Trường Sơn) | 318 | 47 | 246 | 0.32% |
| 67 | Ga đường sắt đô thị / metro — Hà Nội (tuyến 2A Cát Linh–Hà Đông + tuyến 3 Nhổn–Cầu Giấy) | 309 | 35 | 245 | 0.32% |
| 68 | Kênh thoát nước & mương đô thị — đô thị Trung Bộ, Tây Nguyên & ĐBSCL (kênh tiêu thoát đô thị Đà Nẵng, Huế, Cần Thơ...) | 305 | 55 | 292 | 0.31% |
| 69 | Bãi chôn lấp & khu liên hợp xử lý chất thải rắn — Trung Bộ & Tây Nguyên (Khánh Sơn – Đà Nẵng, Cẩm Hà – Hội An, Lộc Thủy – Huế...) | 301 | 46 | 260 | 0.31% |
| 70 | Công viên nghĩa trang (memorial park thương mại) | 301 | 34 | 229 | 0.31% |
| 71 | Khu tập thể vành đai/cận trung tâm Hà Nội (Thanh Xuân Bắc, Khương Thượng, Nghĩa Tân, Nghĩa Đô, Bách Khoa, Phương Mai, Vĩnh Hồ…) | 301 | 33 | 268 | 0.31% |
| 72 | Trại nuôi cá cảnh & thủy sản giống (cá bột, tôm giống, nghêu giống) | 298 | 36 | 271 | 0.30% |
| 73 | Trang trại bò sữa (Vinamilk, TH true MILK, Mộc Châu...) | 286 | 48 | 180 | 0.29% |
| 74 | Nhà ga đường sắt quốc gia — tuyến Bắc – Nam (Hà Nội – Sài Gòn / đường sắt Thống Nhất) | 282 | 79 | 243 | 0.29% |
| 75 | Khu tái định cư Bắc Bộ (TĐC giải phóng mặt bằng đô thị HN; TĐC thủy điện/thủy lợi miền núi phía Bắc — Sơn La, Lai Châu…) | 280 | 51 | 259 | 0.29% |
| 76 | Bờ kè & không gian công cộng ven sông/biển đô thị | 277 | 76 | 250 | 0.28% |
| 77 | Tòa nhà văn phòng hạng A+ & biểu tượng đô thị | 275 | 84 | 251 | 0.28% |
| 78 | Tượng đài & đài tưởng niệm liệt sĩ — Đông Nam Bộ (TP.HCM, Đồng Nai, Tây Ninh, Bà Rịa-Vũng Tàu, Bình Dương, Bình Phước) | 274 | 54 | 240 | 0.28% |
| 79 | Khu nhà ở xã hội & nhà ở công nhân Trung Bộ & Tây Nguyên (Đà Nẵng, Huế, Khánh Hòa; nhà ở công nhân KCN miền Trung) | 273 | 25 | 266 | 0.28% |
| 80 | Nhà tang lễ & cơ sở hỏa táng | 271 | 35 | 251 | 0.28% |
| 81 | Bãi chôn lấp & khu liên hợp xử lý chất thải rắn — Tây Nam Bộ / ĐBSCL (Phước Hiệp – Long An, Đông Thắng – Cần Thơ, bãi rác cấp tỉnh ĐBSCL...) | 262 | 43 | 224 | 0.27% |
| 82 | Công trình tưởng niệm khác (hồ tưởng niệm, ngọn lửa vĩnh cửu, chuông/khánh tưởng niệm, mô hình–biểu tượng tưởng niệm dạng khác có danh) | 262 | 27 | 256 | 0.27% |
| 83 | Khu nhà ở xã hội & nhà ở công nhân Nam Bộ (Lê Thành TP.HCM; nhà ở công nhân KCN Bình Dương, Đồng Nai, Long An, ĐBSCL) | 260 | 29 | 217 | 0.27% |
| 84 | Trạm bơm thoát nước & điều tiết ngập — Nam Bộ (TP.HCM: Nhiêu Lộc – Thị Nghè, Bình Lợi, trạm bơm chống ngập ĐBSCL...) | 254 | 36 | 236 | 0.26% |
| 85 | Trạm dừng nghỉ & trạm thu phí đường bộ | 244 | 61 | 213 | 0.25% |
| 86 | Khu dân cư nông thôn quy hoạch mới (nông thôn mới) | 240 | 42 | 227 | 0.24% |
| 87 | Tháp mộ & bảo tháp cao tăng | 229 | 20 | 224 | 0.23% |
| 88 | Nhà máy nước Nam Trung Bộ (Đà Nẵng, Quảng Nam, Quảng Ngãi, Bình Định, Phú Yên, Khánh Hòa, Ninh Thuận, Bình Thuận — Cầu Đỏ, Võ Cạnh...) | 227 | 60 | 186 | 0.23% |
| 89 | Thành Vauban triều Nguyễn (thành xây gạch/đá kiểu bát giác – ngôi sao, thành tỉnh & kinh thành) | 220 | 50 | 186 | 0.22% |
| 90 | Cảng & bến thủy nội địa — miền Trung | 215 | 17 | 173 | 0.22% |
| 91 | Trường đua | 210 | 25 | 199 | 0.21% |
| 92 | Nghĩa trang liệt sĩ vùng Đồng bằng sông Cửu Long | 207 | 77 | 167 | 0.21% |
| 93 | Hải đăng Nam Trung Bộ (Đà Nẵng → Bình Thuận) | 205 | 33 | 165 | 0.21% |
| 94 | Kho lạnh & kho bảo quản đặc biệt | 204 | 48 | 171 | 0.21% |
| 95 | Công sự – đồn lũy thời Pháp thuộc (pháo đài, đồn binh, nhà tù – thành quân sự kiểu Tây) | 200 | 26 | 198 | 0.20% |
| 96 | Cửa hàng thời trang quốc tế tại VN (Uniqlo, Zara, H&M, Adidas, Nike... store) | 196 | 21 | 191 | 0.20% |
| 97 | Lăng mộ danh nhân văn hóa & nhân sĩ lịch sử | 190 | 31 | 177 | 0.19% |
| 98 | Nghĩa trang nhân dân & cộng đồng có danh | 187 | 34 | 174 | 0.19% |
| 99 | Homestay & lưu trú cộng đồng | 186 | 69 | 184 | 0.19% |
| 100 | Trạm biến áp 220kV | 186 | 77 | 174 | 0.19% |
| 101 | Công viên giải trí có chủ đề (theme park & khu vui chơi) | 184 | 29 | 183 | 0.19% |
| 102 | Bia tưởng niệm & bia ghi công vùng Đông Nam Bộ (TP Hồ Chí Minh, Đồng Nai, Tây Ninh, Bà Rịa-Vũng Tàu...) | 180 | 44 | 168 | 0.18% |
| 103 | Công viên đô thị tại Hà Nội & vùng Đồng bằng sông Hồng | 176 | 55 | 162 | 0.18% |
| 104 | Lăng tẩm hoàng triều phong kiến | 176 | 80 | 128 | 0.18% |
| 105 | Nghĩa trang liệt sĩ vùng Tây Nguyên | 176 | 43 | 149 | 0.18% |
| 106 | Lũy phòng thủ & chiến lũy nội chiến (lũy Trường Dục/Thầy, lũy phân giới Trịnh–Nguyễn, Tây Sơn) | 175 | 20 | 147 | 0.18% |
| 107 | Nghĩa trang liệt sĩ vùng Duyên hải Nam Trung Bộ | 170 | 62 | 143 | 0.17% |
| 108 | Lò đốt rác & nhà máy điện rác (lò đốt CTR cấp huyện/xã + nhà máy đốt rác phát điện: Sóc Sơn, Cần Thơ, Phú Thọ, Bình Dương...) | 168 | 57 | 137 | 0.17% |
| 109 | Trạm xử lý nước thải — Đông Nam Bộ & TP.HCM (Bình Hưng, Tham Lương – Bến Cát, Nhiêu Lộc – Thị Nghè, KCN Đồng Nai – Bình Dương...) | 165 | 15 | 132 | 0.17% |
| 110 | Nhà thờ Tin Lành — Tây Nguyên (Êđê, Jrai, Bahnar, Kơ Ho; Kon Tum, Gia Lai, Đắk Lắk, Đắk Nông, Lâm Đồng) | 163 | 29 | 141 | 0.17% |
| 111 | Đường dây 500kV | 159 | 46 | 118 | 0.16% |
| 112 | Công viên đô thị các tỉnh Đồng bằng sông Hồng & duyên hải còn lại ngoài Hà Nội (Bắc Ninh, Hải Dương, Nam Định, Thái Bình...) | 158 | 28 | 156 | 0.16% |
| 113 | Cảng cạn & ICD | 158 | 58 | 122 | 0.16% |
| 114 | Đường dây 220kV | 157 | 31 | 150 | 0.16% |
| 115 | Khu mộ cổ & địa điểm khảo cổ mai táng | 156 | 25 | 148 | 0.16% |
| 116 | Vườn bách thảo & công viên sinh thái có tên | 156 | 43 | 146 | 0.16% |
| 117 | Kè sông & chỉnh trị lòng sông Nam Bộ & ĐBSCL (kè chống sạt lở bờ sông Tiền, sông Hậu, kênh rạch; kè bảo vệ đô thị ven sông) | 154 | 50 | 133 | 0.16% |
| 118 | Bãi chôn lấp & khu liên hợp xử lý chất thải rắn — Đông Nam Bộ & TP.HCM (Đa Phước, Phước Hiệp, Tây Bắc Củ Chi, Nam Bình Dương...) | 153 | 43 | 118 | 0.16% |
| 119 | Nhà máy nước cụm Hà Nội & vùng Thủ đô (Sông Đà, Sông Đuống, Bắc Thăng Long, Yên Phụ, Cáu Bây, Hà Đông, Sơn Tây...) | 152 | 35 | 122 | 0.16% |
| 120 | Đê biển & đê cửa sông Nam Bộ (đê biển Gò Công, Bạc Liêu, Gành Hào, đê biển Tây Cà Mau, đê biển Đông) | 148 | 27 | 130 | 0.15% |
| 121 | Chợ đầu mối & chợ bán buôn | 147 | 23 | 140 | 0.15% |
| 122 | Trạm biến áp 110kV — Bắc Bộ (Hà Nội + ĐB sông Hồng + trung du-miền núi phía Bắc) | 142 | 66 | 113 | 0.14% |
| 123 | Đê biển & đê cửa sông Bắc Bộ (Quảng Ninh → Ninh Bình; đê biển Hải Hậu, Cát Hải, Tiền Hải, Giao Thủy, Bình Minh) | 142 | 33 | 133 | 0.14% |
| 124 | Tượng đài & đài tưởng niệm liệt sĩ — Tây Nam Bộ / ĐB sông Cửu Long (Long An, Tiền Giang, Bến Tre, Trà Vinh, Vĩnh Long, Đồng Tháp, An Giang, Kiên Giang, Cần Thơ, Hậu Giang, Sóc Trăng, Bạc Liêu, Cà Mau) | 140 | 18 | 140 | 0.14% |
| 125 | Nghĩa trang liệt sĩ vùng Đồng bằng sông Hồng | 134 | 50 | 116 | 0.14% |
| 126 | Phủ & điện thờ Mẫu — Trung du & miền núi Bắc Bộ (Mẫu Thượng Ngàn: Lạng Sơn, Lào Cai, Tuyên Quang, Bắc Giang, Phú Thọ, Yên Bái...) | 134 | 18 | 128 | 0.14% |
| 127 | Chợ phiên vùng cao | 130 | 16 | 120 | 0.13% |
| 128 | Trung tâm thể dục thể thao & khu liên hợp thể thao | 128 | 44 | 123 | 0.13% |
| 129 | Kè sông & chỉnh trị lòng sông miền Trung & Tây Nguyên (kè chống sạt lở bờ sông Thu Bồn, Vu Gia, Trà Khúc, Sê San...) | 125 | 19 | 120 | 0.13% |
| 130 | Vườn hoa & hoa viên đô thị — Hà Nội & vùng Đồng bằng sông Hồng | 119 | 40 | 104 | 0.12% |
| 131 | Cao ốc văn phòng thương mại hạng B/C & tỉnh thành | 117 | 54 | 117 | 0.12% |
| 132 | Bến xe khách — cấp huyện / khu vực (loại 3–4 theo QCVN) | 116 | 53 | 115 | 0.12% |
| 133 | Trạm bơm thoát nước & điều tiết ngập — Bắc Bộ & Trung Bộ (Yên Sở, Đông Mỹ, Liên Mạc, trạm bơm chống ngập đô thị...) | 115 | 17 | 98 | 0.12% |
| 134 | Cống & công trình điều tiết nước ĐBSCL (cống Cái Lớn–Cái Bé, Ninh Quới, Âu thuyền Tắc Thủ, cống ngăn mặn ven biển Tây/Đông) | 114 | 22 | 102 | 0.12% |
| 135 | Lăng mộ lãnh tụ & danh nhân cách mạng cận-hiện đại | 113 | 24 | 110 | 0.12% |
| 136 | Đồn biên phòng & tiền đồn lịch sử | 111 | 48 | 106 | 0.11% |
| 137 | Nhà kính nông nghiệp công nghệ cao tổng hợp có thương hiệu (Vineco, Dalat Hasfarm...) | 109 | 27 | 83 | 0.11% |
| 138 | Nhà máy nước Đông Nam Bộ ngoài TP.HCM (Đồng Nai, Bình Dương, Bà Rịa – Vũng Tàu, Bình Phước, Tây Ninh — Thiện Tân, Dĩ An, Sông Đồng Nai...) | 109 | 49 | 85 | 0.11% |
| 139 | Cơ sở thể thao chuyên ngành (sân bắn, câu trường, trường đạo cụ) | 107 | 16 | 99 | 0.11% |
| 140 | Nhà tù & trại giam lịch sử | 106 | 19 | 102 | 0.11% |
| 141 | Phố cổ & khu phố cổ đô thị | 105 | 27 | 96 | 0.11% |
| 142 | Trạm xử lý nước thải — Bắc Bộ (Hà Nội & ĐBSH, Đông Bắc: Yên Sở, Hồ Tây, Bắc Thăng Long, Cầu Ngà, Yên Xá...) | 105 | 32 | 99 | 0.11% |
| 143 | Trạm biến áp 110kV — Trung Bộ & Tây Nguyên (Bắc TB + Nam TB + Tây Nguyên) | 104 | 45 | 87 | 0.11% |
| 144 | Hầm đường bộ xuyên núi & qua sông | 103 | 47 | 92 | 0.11% |
| 145 | Nhà ga đường sắt quốc gia — tuyến Đà Lạt – Trại Mát & nhánh miền Trung – Tây Nguyên | 103 | 14 | 101 | 0.11% |
| 146 | Trạm biến áp 500kV | 102 | 26 | 93 | 0.10% |
| 147 | Trạm nạp khí (LPG/CNG) & trạm sạc xe điện có thương hiệu (V-Green/VinFast, EVN...) | 101 | 7 | 100 | 0.10% |
| 148 | Hầm & kết cấu ngầm đường sắt – metro (bore/đoạn ngầm) | 97 | 10 | 90 | 0.10% |
| 149 | Nhà máy nước Bắc Trung Bộ (Thanh Hóa, Nghệ An, Hà Tĩnh, Quảng Bình, Quảng Trị, Thừa Thiên Huế — Hưng Vĩnh, Cầu Bạc, Vạn Niên...) | 97 | 47 | 83 | 0.10% |
| 150 | Cống & công trình điều tiết nước Bắc Trung Bộ & Nam Trung Bộ | 96 | 22 | 92 | 0.10% |
| 151 | Ga đường sắt đô thị / metro — TP.HCM (tuyến 1 Bến Thành–Suối Tiên) | 95 | 28 | 53 | 0.10% |
| 152 | Khu tái định cư Trung Bộ & Tây Nguyên (TĐC thủy điện miền Trung, ven biển, di dời vùng thiên tai) | 94 | 9 | 92 | 0.10% |
| 153 | Nhà máy nước Đông Bắc Bộ (Quảng Ninh, Hải Phòng, Bắc Ninh, Bắc Giang, Lạng Sơn, Cao Bằng — Diễn Vọng, Đồng Hòa, An Dương...) | 93 | 43 | 72 | 0.09% |
| 154 | Địa đạo & hầm chiến đấu | 93 | 33 | 70 | 0.09% |
| 155 | Phủ & điện thờ Mẫu — Đồng bằng sông Hồng & vùng Thủ đô (Hà Nội, Nam Định - Phủ Dầy, Ninh Bình, Hải Dương, Hưng Yên, Thái Bình, Hà Nam, Bắc Ninh, Vĩnh Phúc, Hải Phòng) | 92 | 32 | 85 | 0.09% |
| 156 | Khách sạn (cơ sở lưu trú cấp hạng sao) | 91 | 28 | 90 | 0.09% |
| 157 | Bãi/nhà gửi xe máy – xe đạp công cộng có tên (nhà xe trường ĐH/khu đô thị/bến xe, điểm trông giữ xe máy có danh riêng) | 90 | 20 | 89 | 0.09% |
| 158 | Làng chài & khu định cư ven biển cổ | 89 | 33 | 84 | 0.09% |
| 159 | Khác (cơ sở kho vận chưa phân loại) | 88 | 12 | 88 | 0.09% |
| 160 | Hồ điều hòa & hồ điều tiết đô thị miền Trung, TP.HCM & Nam Bộ (hồ điều tiết Đà Nẵng, hồ Khánh Hội, Bàu Cát, hồ điều hòa các KĐT mới) | 87 | 17 | 86 | 0.09% |
| 161 | Nhà máy nước cụm TP. Hồ Chí Minh (Thủ Đức, Tân Hiệp, BOO Thủ Đức, Bình An, Kênh Đông, Tân Phú...) | 87 | 23 | 72 | 0.09% |
| 162 | Thành cổ tiền-Nguyễn (thành đất/lũy đắp, kinh đô & trị sở trước thế kỷ 19) | 84 | 28 | 73 | 0.09% |
| 163 | Bia tưởng niệm & bia ghi công vùng Bắc Bộ (Hà Nội, đồng bằng & trung du sông Hồng, Đông Bắc) | 83 | 30 | 82 | 0.08% |
| 164 | Trạm xử lý nước thải — Trung Bộ & Tây Nguyên (Đà Nẵng Hòa Cường/Phú Lộc, Huế, Quy Nhơn, Nha Trang, Buôn Ma Thuột...) | 83 | 22 | 75 | 0.08% |
| 165 | Bể bơi & trung tâm bơi lội — miền Trung & Tây Nguyên | 82 | 10 | 78 | 0.08% |
| 166 | Bể bơi & trung tâm bơi lội — Hà Nội & vùng đồng bằng sông Hồng | 81 | 19 | 80 | 0.08% |
| 167 | Depot container & bãi rỗng container | 81 | 22 | 80 | 0.08% |
| 168 | Tượng đài & đài tưởng niệm liệt sĩ — Hà Nội & vùng Thủ đô (Hà Nội, Hòa Bình, Vĩnh Phúc, Bắc Ninh): tượng đài liệt sĩ, đài tưởng niệm anh hùng LS cấp xã/huyện/tỉnh | 79 | 28 | 68 | 0.08% |
| 169 | Chùa Bắc Tông — Trung du & miền núi Bắc Bộ (Phú Thọ, Thái Nguyên, Bắc Giang, Lạng Sơn, Quảng Ninh, Tuyên Quang, Yên Bái, Lào Cai, Hòa Bình, Sơn La...) | 77 | 10 | 77 | 0.08% |
| 170 | Mốc biên giới Việt Nam – Trung Quốc (hệ mốc 1999–2008, ~1.971 mốc) | 76 | 23 | 66 | 0.08% |
| 171 | Kho ngoại quan & CFS | 74 | 17 | 71 | 0.08% |
| 172 | Đập thủy điện & hồ chứa đa mục tiêu lớn — sông Sê San, Srêpốk, Đồng Nai, Vu Gia–Thu Bồn & miền Trung–Tây Nguyên (Yali, Sê San 3/4, Buôn Tua Srah, Đồng Nai 3/4, Sông Tranh 2, A Vương, Đa Nhim...) | 74 | 49 | 57 | 0.08% |
| 173 | Nhà thờ Tin Lành — Đồng bằng sông Cửu Long (13 tỉnh thành miền Tây) | 71 | 12 | 71 | 0.07% |
| 174 | Tháp nước (đài nước trên cao) đô thị & di sản (Tháp nước Hàng Đậu, đài nước kiểu Pháp, tháp nước thị xã...) | 71 | 9 | 67 | 0.07% |
| 175 | Hải đăng hải đảo xa (Trường Sa, Hoàng Sa, Côn Đảo, Phú Quốc, Bạch Long Vĩ, Cô Tô) | 70 | 13 | 61 | 0.07% |
| 176 | Khu tập thể nội thành Hà Nội (Kim Liên, Trung Tự, Giảng Võ, Thành Công, Quỳnh Mai, Nguyễn Công Trứ, Văn Chương…) | 67 | 28 | 56 | 0.07% |
| 177 | Từ đường & nhà thờ Tổ — Đồng bằng sông Hồng (Hà Nội, Bắc Ninh, Hải Dương, Hưng Yên, Nam Định, Thái Bình, Hà Nam, Ninh Bình, Vĩnh Phúc, Hải Phòng) | 67 | 10 | 67 | 0.07% |
| 178 | Lăng tẩm & mộ chí nguyên thủ – lãnh tụ cận đại | 66 | 21 | 52 | 0.07% |
| 179 | Bể bơi & trung tâm bơi lội — TP.HCM & vùng Đông Nam Bộ | 65 | 14 | 63 | 0.07% |
| 180 | Hải đăng Nam Bộ (Bà Rịa–Vũng Tàu → Kiên Giang) | 65 | 16 | 46 | 0.07% |
| 181 | Từ đường & nhà thờ Tổ — Bắc Trung Bộ (Thanh Hóa, Nghệ An, Hà Tĩnh, Quảng Bình, Quảng Trị, Thừa Thiên Huế) | 64 | 14 | 63 | 0.07% |
| 182 | Nhà thờ Tin Lành — Đông Nam Bộ (TP.HCM, Đồng Nai, Bình Dương, BR-VT, Tây Ninh, Bình Phước) | 62 | 10 | 51 | 0.06% |
| 183 | Phủ & điện thờ Mẫu — Đông Nam Bộ (TP.HCM, Đồng Nai, Bình Dương, BR-VT, Tây Ninh, Bình Phước) | 61 | 6 | 58 | 0.06% |
| 184 | Tượng đài lãnh tụ & lãnh đạo cách mạng — Tôn Đức Thắng, Lê Duẩn, Trường Chinh, Phạm Văn Đồng, Võ Nguyên Giáp, Nguyễn Văn Linh & lãnh đạo khác (quảng trường, công viên, khu lưu niệm) | 61 | 22 | 61 | 0.06% |
| 185 | Bãi chôn lấp & khu liên hợp xử lý chất thải rắn — Bắc Bộ (Nam Sơn – Sóc Sơn, Xuân Sơn, Tràng Cát, Đình Vũ...) | 60 | 18 | 45 | 0.06% |
| 186 | Nhà ga đường sắt quốc gia — tuyến Hà Nội – Hải Phòng | 58 | 9 | 53 | 0.06% |
| 187 | Đê bao & đê bối ĐBSCL — vùng giữa & ven biển (Vĩnh Long, Cần Thơ, Hậu Giang, Sóc Trăng, Bạc Liêu, Cà Mau) | 58 | 16 | 57 | 0.06% |
| 188 | Hải đăng Bắc Bộ (Quảng Ninh → Ninh Bình) | 57 | 12 | 37 | 0.06% |
| 189 | Làng cổ đồng bằng & trung du | 54 | 21 | 53 | 0.06% |
| 190 | Trạm biến áp 110kV — Đông Nam Bộ (TP.HCM + Đồng Nai/Bình Dương/BR-VT/Bình Phước/Tây Ninh) | 54 | 25 | 49 | 0.06% |
| 191 | Bãi đỗ xe ngầm đã xây / đã phê duyệt có tên (bãi ngầm phố cổ, công viên/quảng trường, dưới TTTM... — đã định danh) | 53 | 8 | 40 | 0.05% |
| 192 | Bãi đỗ xe công cộng có tên (bãi đỗ xe quận/phường, bãi điểm du lịch–danh thắng, bãi đỗ trông giữ xe có biển danh được nguồn độc lập đưa tin) | 50 | 14 | 50 | 0.05% |
| 193 | Trang trại chăn nuôi hỗn hợp / tổng hợp đa loài có tên | 50 | 13 | 50 | 0.05% |
| 194 | Tượng đài & đài tưởng niệm liệt sĩ — Tây Nguyên (Kon Tum, Gia Lai, Đắk Lắk, Đắk Nông, Lâm Đồng) | 50 | 20 | 45 | 0.05% |
| 195 | Ga tàu điện ngầm & metro | 48 | 15 | 38 | 0.05% |
| 196 | Cơ sở lưu trú & ăn uống khác | 46 | 12 | 46 | 0.05% |
| 197 | Bể bơi & trung tâm bơi lội — đồng bằng sông Cửu Long & các tỉnh còn lại | 45 | 11 | 45 | 0.05% |
| 198 | Bể chứa & đài nước hiện đại của hệ cấp nước (bể chứa nước sạch, bồn áp lực, đài nước bê-tông khu đô thị) | 44 | 9 | 41 | 0.04% |
| 199 | Nhà máy nước Tây Nam Bộ đông (Long An, Tiền Giang, Bến Tre, Trà Vinh, Vĩnh Long, Đồng Tháp) | 42 | 22 | 36 | 0.04% |
| 200 | Tuyến cáp viễn thông & trạm cáp ngầm / cáp biển | 41 | 17 | 39 | 0.04% |
| 201 | Hầm chui nút giao đô thị | 40 | 22 | 38 | 0.04% |
| 202 | Mốc biên giới Việt Nam – Lào (phân giới 1977–2007, ~905 mốc) | 40 | 8 | 35 | 0.04% |
| 203 | Khu tập thể Hải Phòng & các đô thị ven biển Bắc Bộ (Đồng Tâm, Cầu Tre, Vạn Mỹ…) | 39 | 10 | 38 | 0.04% |
| 204 | Đập & hồ chứa lớn quốc gia mục tiêu thủy lợi/cấp nước — đập Cửa Đạt, Dầu Tiếng, Trị An (thủy lợi-thủy điện), Ngàn Trươi, Tả Trạch, Ngàn Sâu... | 37 | 13 | 29 | 0.04% |
| 205 | Cơ sở thờ tự Phật giáo Hòa Hảo (chùa, An Hòa Tự, hội quán, Tổ đình) | 35 | 5 | 33 | 0.04% |
| 206 | Nhà để xe cao tầng & bãi đỗ xe đầu mối có danh riêng (nhà xe sân bay Nội Bài/Tân Sơn Nhất, nhà xe TTTM/Vincom, bãi đỗ SVĐ/bệnh viện lớn có tên) | 35 | 8 | 35 | 0.04% |
| 207 | Đập thủy điện & hồ chứa đa mục tiêu lớn quốc gia — bậc thang sông Đà & sông Lô–Gâm (Hòa Bình, Sơn La, Lai Châu, Thác Bà, Tuyên Quang, Bản Chát, Huội Quảng...) | 33 | 19 | 28 | 0.03% |
| 208 | Tòa án & công trình tư pháp (di sản kiến trúc tư pháp) | 31 | 3 | 30 | 0.03% |
| 209 | Bến xe khách — loại 5–6 & bến phụ tại trung tâm xã/thị trấn | 30 | 22 | 29 | 0.03% |
| 210 | Khu tập thể Việt Trì, Thái Nguyên, Nam Định & đô thị công nghiệp miền Bắc khác | 30 | 3 | 30 | 0.03% |
| 211 | Hệ thống kênh Bắc Hưng Hải & kênh trục lớn Đồng bằng sông Hồng | 29 | 13 | 25 | 0.03% |
| 212 | Tháp & cột viễn thông vi ba / chuyển tiếp | 29 | 12 | 29 | 0.03% |
| 213 | Trạm biến áp 110kV — Tây Nam Bộ (ĐBSCL) | 29 | 19 | 27 | 0.03% |
| 214 | Bãi/tháp đỗ xe ô tô thông minh giàn thép cao tầng có tên (Nguyễn Công Hoan, Nguyễn Công Trứ, Trần Nhật Duật, Lê Văn Lương... — Hà Nội & các TP có dự án) | 27 | 5 | 19 | 0.03% |
| 215 | Hải đăng Bắc Trung Bộ (Thanh Hóa → Thừa Thiên Huế) | 26 | 8 | 26 | 0.03% |
| 216 | Kênh thoát nước & mương đô thị — Hà Nội & Bắc Bộ (Tô Lịch, Kim Ngưu, Sét, Lừ, mương thoát nước nội đô...) | 26 | 20 | 22 | 0.03% |
| 217 | Chuỗi cửa hàng tiện lợi & bán lẻ hiện đại | 25 | 8 | 25 | 0.03% |
| 218 | Chợ nổi | 25 | 3 | 24 | 0.03% |
| 219 | Nhà kính / nhà lưới trồng hoa (hồng, cúc, lan, ly) | 25 | 10 | 24 | 0.03% |
| 220 | Đập & hồ chứa thủy lợi Trung du – miền núi phía Bắc (Núi Cốc, Cấm Sơn, Ngòi Là, Khe Chè...) | 25 | 9 | 24 | 0.03% |
| 221 | Nhà nghỉ, motel & khách sạn bình dân | 24 | 12 | 24 | 0.02% |
| 222 | Vườn thú, safari & thủy cung | 23 | 13 | 23 | 0.02% |
| 223 | Cửa hàng máy tính, linh kiện & gaming gear (GearVN, An Phát, Phong Vũ, Hà Nội Computer...) | 22 | 9 | 22 | 0.02% |
| 224 | Nhà máy nước Tây Bắc & thượng du (Lào Cai, Yên Bái, Sơn La, Điện Biên, Lai Châu, Hòa Bình, Hà Giang, Tuyên Quang) | 22 | 10 | 21 | 0.02% |
| 225 | Nhà máy nước Tây Nam Bộ tây (Cần Thơ, Hậu Giang, An Giang, Kiên Giang, Sóc Trăng, Bạc Liêu, Cà Mau — Cần Thơ 1/2, Hưng Phú...) | 22 | 18 | 19 | 0.02% |
| 226 | Hội quán người Hoa (Phúc Kiến, Quảng Triệu, Triều Châu, Hải Nam, Quỳnh Phủ; Hội An, Chợ Lớn, Biên Hòa, Hà Tiên...) | 21 | 1 | 21 | 0.02% |
| 227 | Mốc biên giới Việt Nam – Campuchia (đến 2019, ~314 mốc) | 21 | 10 | 18 | 0.02% |
| 228 | Thánh thất Cao Đài — Hội thánh Cao Đài Tây Ninh (Tòa Thánh & họ đạo) | 21 | 8 | 18 | 0.02% |
| 229 | Nhà kính trồng cây ăn quả trong nhà (dâu tây, nho, dưa lưới Tây Nguyên) | 20 | 6 | 18 | 0.02% |
| 230 | Nhà máy nước Tây Nguyên (Kon Tum, Gia Lai, Đắk Lắk, Đắk Nông, Lâm Đồng — Buôn Ma Thuột, Đan Kia – Suối Vàng...) | 20 | 11 | 20 | 0.02% |
| 231 | Tháp nước kỹ thuật | 20 | 5 | 20 | 0.02% |
| 232 | Trạm bơm thủy lợi Đồng bằng sông Hồng & Trung du Bắc Bộ (Cổ Đam, Cốc Thành, Như Trác, Hữu Bị, Vân Đình, Yên Lệnh, Đại Định...) | 20 | 13 | 15 | 0.02% |
| 233 | Từ đường & nhà thờ Tổ — Đông Nam Bộ (TP.HCM, Đồng Nai, Bình Dương, BR-VT, Tây Ninh, Bình Phước) | 20 | 3 | 20 | 0.02% |
| 234 | Nghĩa trang liệt sĩ cấp quốc gia | 19 | 7 | 19 | 0.02% |
| 235 | Nhà thờ Tin Lành — Duyên hải Nam Trung Bộ (Đà Nẵng, Quảng Nam, Quảng Ngãi, Bình Định, Phú Yên, Khánh Hòa, Ninh Thuận, Bình Thuận) | 19 | 5 | 19 | 0.02% |
| 236 | Biệt thự Pháp Đà Lạt — cụm Trần Hưng Đạo, Hùng Vương, Quang Trung (Lâm Đồng) | 18 | 1 | 18 | 0.02% |
| 237 | Cửa hàng xe đạp, phụ tùng & dịch vụ ô tô–xe máy (phụ tùng, lốp, dầu nhớt...) | 18 | 3 | 18 | 0.02% |
| 238 | Nhà thờ Tin Lành — Đồng bằng sông Hồng & vùng Thủ đô (Hà Nội, Hải Phòng, Nam Định, Thái Bình...) | 18 | 7 | 12 | 0.02% |
| 239 | Tháp truyền hình & phát sóng quảng bá | 18 | 13 | 18 | 0.02% |
| 240 | Hầm đi bộ & kết nối ngầm đô thị | 17 | 3 | 17 | 0.02% |
| 241 | Bến cá – chợ đầu mối thủy sản | 16 | 9 | 16 | 0.02% |
| 242 | Hầm đường sắt | 15 | 9 | 12 | 0.02% |
| 243 | Tịnh thất, am, cốc & cơ sở thờ tự nhỏ khác | 15 | 2 | 15 | 0.02% |
| 244 | Kênh đào ĐBSCL — vùng giữa, ven biển & bán đảo Cà Mau (Chợ Gạo, Quản Lộ–Phụng Hiệp, Xà No, Phụng Hiệp, Nicôlôn) | 14 | 7 | 7 | 0.01% |
| 245 | Phủ & điện thờ Mẫu — Nam Trung Bộ & Tây Nguyên (thờ Thiên Y A Na / Po Nagar; Khánh Hòa, Ninh Thuận, Bình Thuận, Lâm Đồng...) | 14 | 3 | 14 | 0.01% |
| 246 | Chùa Khmer Nam Tông — Kiên Giang | 13 | 2 | 13 | 0.01% |
| 247 | Nghĩa trang quốc tế & đa quốc gia | 13 | 4 | 12 | 0.01% |
| 248 | Phủ & điện thờ Mẫu — Bắc Trung Bộ (Thanh Hóa, Nghệ An, Hà Tĩnh, Quảng Bình, Quảng Trị, Thừa Thiên Huế) | 13 | 5 | 12 | 0.01% |
| 249 | Tháp nước công nghiệp & tháp nước nhà ga – nhà máy (tháp nước đầu mối đường sắt, tháp nước KCN có danh) | 13 | 5 | 13 | 0.01% |
| 250 | Hồ điều hòa & hồ điều tiết đô thị Hà Nội & vùng phía Bắc (Yên Sở, Linh Đàm, Văn Quán, Định Công, Đền Lừ, Bảy Mẫu, Thành Công...) | 12 | 10 | 12 | 0.01% |
| 251 | Vườn hoa & hoa viên đô thị — Đồng bằng sông Cửu Long & các tỉnh còn lại | 10 | 7 | 10 | 0.01% |
| 252 | Đập & hồ chứa thủy lợi Bắc Trung Bộ (Thanh Hóa → Thừa Thiên Huế) | 10 | 6 | 8 | 0.01% |
| 253 | Đập & hồ chứa thủy lợi Nam Trung Bộ (Đà Nẵng → Bình Thuận) | 10 | 7 | 9 | 0.01% |
| 254 | Đền thờ — Đồng bằng sông Hồng & vùng Thủ đô (Hà Nội, Nam Định, Ninh Bình, Hải Dương, Hưng Yên, Thái Bình, Hà Nam, Bắc Ninh, Vĩnh Phúc, Hải Phòng) | 9 | 2 | 9 | 0.01% |
| 255 | Nhà ga đường sắt quốc gia — tuyến Hà Nội – Đồng Đăng (Lạng Sơn) | 8 | 4 | 8 | 0.01% |
| 256 | Thánh đường Hồi giáo (masjid, surau, chùa Bà Ni; Ninh Thuận, Bình Thuận, An Giang, TP.HCM, Tây Ninh, Đồng Nai) | 8 | 1 | 8 | 0.01% |
| 257 | Tháp tiêu / cột tiêu / đăng tiêu / chập tiêu cố định — kiểu báo hiệu thị giác cố định | 8 | 2 | 8 | 0.01% |
| 258 | Phủ & điện thờ Mẫu — Đồng bằng sông Cửu Long (13 tỉnh thành miền Tây) | 7 | 1 | 7 | 0.01% |
| 259 | Thánh thất Cao Đài — Ban Chỉnh Đạo (Bến Tre & họ đạo) | 7 | 2 | 7 | 0.01% |
| 260 | Dinh thự & biệt thự thuộc địa Hải Phòng, Nam Định, Huế, Sa Pa | 6 | 1 | 6 | 0.01% |
| 261 | Khu tập thể Vinh, Thanh Hóa & đô thị Bắc Trung Bộ | 6 | 4 | 4 | 0.01% |
| 262 | Nhà ga đường sắt quốc gia — tuyến Hà Nội – Lào Cai (Yên Viên – Lào Cai) | 6 | 4 | 6 | 0.01% |
| 263 | Đê sông Hồng (đê Hữu Hồng, Tả Hồng, đê Bối Hà Nội–Hưng Yên...) | 6 | 6 | 5 | 0.01% |
| 264 | Chùa Khmer Nam Tông — An Giang | 5 | 1 | 5 | 0.01% |
| 265 | Kênh tưới Bắc Trung Bộ (hệ thống Đô Lương, Bái Thượng, Nam Đàn, sông Chu, Linh Cảm) | 5 | 3 | 5 | 0.01% |
| 266 | Nhà thờ Tin Lành — Bắc Trung Bộ (Thanh Hóa, Nghệ An, Hà Tĩnh, Quảng Bình, Quảng Trị, Thừa Thiên Huế) | 5 | 1 | 5 | 0.01% |
| 267 | Trạm xử lý nước thải — Tây Nam Bộ / ĐBSCL (Cần Thơ, Long Xuyên, Rạch Giá, Cà Mau, KCN miền Tây...) | 5 | 4 | 5 | 0.01% |
| 268 | Kênh tiêu – kênh trục cấp 1 có tên riêng (toàn quốc) | 4 | 2 | 4 | 0.00% |
| 269 | Nhà ga đường sắt quốc gia — tuyến Hà Nội – Quán Triều / Kép – Lưu Xá (Thái Nguyên) | 4 | 2 | 4 | 0.00% |
| 270 | Nhà ga đường sắt quốc gia — tuyến Đông Anh – Quán Triều & Kép – Hạ Long (Đông Bắc) | 4 | 2 | 4 | 0.00% |
| 271 | Phao báo hiệu hàng hải — kiểu IALA (phao luồng trái/phải, cardinal Bắc/Nam/Đông/Tây, chướng ngại biệt lập, nước an toàn, chuyên dùng) | 4 | 3 | 3 | 0.00% |
| 272 | Thánh thất Cao Đài — Chiếu Minh & các hệ phái nhỏ (Bạch Y, Chơn Lý, Cầu Kho Tam Quan, Bình Đức) | 4 | 1 | 4 | 0.00% |
| 273 | Thánh thất Cao Đài — Truyền giáo Cao Đài (Đà Nẵng - Trung Bộ) | 4 | 1 | 4 | 0.00% |
| 274 | Đài thông tin duyên hải (mạng Vishipel — Coastal radio / GMDSS) | 4 | 3 | 4 | 0.00% |
| 275 | Đê sông Thái Bình & hệ thống Đuống – Luộc – Trà Lý – Hóa | 4 | 4 | 4 | 0.00% |
| 276 | Đập & hồ chứa thủy lợi Tây Nguyên (Kon Tum → Lâm Đồng) | 4 | 4 | 4 | 0.00% |
| 277 | Đập & hồ chứa thủy lợi Đông Nam Bộ | 4 | 2 | 4 | 0.00% |
| 278 | Thánh thất, thánh tịnh Cao Đài độc lập tiêu biểu | 3 | 2 | 3 | 0.00% |
| 279 | Biệt thự cổ Pháp TP.HCM (Quận 1, Quận 3 — Lê Duẩn, Tú Xương, Nguyễn Đình Chiểu) | 2 | 1 | 2 | 0.00% |
| 280 | Công ty / vùng hoa tiêu hàng hải (Pilot stations) | 2 | 1 | 2 | 0.00% |
| 281 | Hầm kỹ thuật & hạ tầng ngầm đô thị | 2 | 2 | 2 | 0.00% |
| 282 | Trạm vệ tinh mặt đất & anten parabol lớn | 2 | 1 | 2 | 0.00% |
| 283 | Đê sông Đáy – Hoàng Long (Tả Đáy, Hữu Đáy, đê Hoàng Long Ninh Bình) | 2 | 1 | 2 | 0.00% |
| 284 | Chùa Khmer Nam Tông — Bạc Liêu | 1 | 1 | 1 | 0.00% |
| 285 | Chùa Khmer Nam Tông — Vĩnh Long, Hậu Giang & Cần Thơ | 1 | 1 | 1 | 0.00% |
| 286 | Tháp Chăm & đền Bà La Môn (Mỹ Sơn, Po Nagar, Po Klong Garai, Po Rome, Bánh Ít, Dương Long, Cánh Tiên, Pô Sah Inư...) | 1 | 1 | 1 | 0.00% |
| 287 | Đê sông Mã – sông Chu (Thanh Hóa) | 1 | 1 | 1 | 0.00% |
