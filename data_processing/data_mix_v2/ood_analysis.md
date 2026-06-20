# Phân tích question_type cho OOD (out-of-distribution)

Mục tiêu: xác định các `question_type` cần loại khỏi tập train để khi model trả lời đúng các type này lúc eval, đó là bằng chứng cho khả năng generalize ("suy luận"), không phải ghi nhớ pattern câu hỏi đã thấy nhiều lần.

Phương pháp: so sánh số lượng theo `question_type` giữa `train` và `test` (từ `summary.json`). Một type là ứng viên OOD tốt khi nó hiếm/vắng trong train nhưng có mặt trong test — model gần như không có cơ hội học vẹt pattern đó, nên câu trả lời đúng phải đến từ khả năng generalize có tính kết hợp (compositional) trên các entity/metric/period mà nó *đã* từng thấy.

## Các type được chọn cho OOD

| question_type | số lượng train | số lượng test | Lý do |
|---|---|---|---|
| `macro_highest_year` | 3 | 99 | Train hầu như không có ví dụ dạng "năm nào cao nhất" trên chuỗi thời gian macro; đòi hỏi suy luận trên cả dãy số (argmax), không phải ghi nhớ. |
| `macro_lowest_year` | 3 | 99 | Tương tự như trên, biến thể argmin. |
| `commodity_top` | 4 | 1 | Xếp hạng Top-N giữa các loại hàng hóa; kỹ năng sort/rank tổng quát ít được luyện trong train. |
| `universe_top` | 7 | 1 | Xếp hạng Top-N trên *toàn bộ* thị trường cổ phiếu, không phải một nhóm peer cố định như các nơi khác trong train. |
| `stock_vs_commodity_diff` | 12 | 1 | So sánh chéo miền dữ liệu (tỷ suất sinh lời cổ phiếu vs hàng hóa) — kết hợp hai nguồn bảng dữ liệu không được so sánh ở nơi khác trong train. |
| `company_vs_company_yearly_diff` | 41 | 2 | So sánh 2 công ty theo năm (không phải theo quý); số lượng ít, dễ kiểm tra xem model có generalize được pattern so sánh theo quý sang theo năm không. |
| `index_direct` | 57 | 7 | Truy vấn trực tiếp cấp chỉ số; tập entity chỉ số nhỏ (8 chỉ số: VN30, VNINDEX, FTSE, HSI, KOSPI, NASDAQ, NIKKEI, SP500, STI) nên rất dễ bị học vẹt nếu giữ trong train. |

Tổng số dòng bị loại: 127/20,629 dòng trong `train.norm.jsonl` (0.6%).

## Vì sao chọn các type này mà không chọn các type hiếm khác

Một số type khác cũng có số lượng thấp trong train (ví dụ các subtype của `commodity_top5_return_pct`, nhóm `universe_positive_count`) nhưng được giữ lại vì:
- Chúng chia sẻ phần lớn pattern suy luận với một type "anh em" có số lượng cao hơn đã có trong train (ví dụ `industry_top` đã có nhiều mẫu, nên chỉ loại `universe_top` sẽ cô lập đúng phần generalize "toàn thị trường", thay vì cả kỹ năng "xếp hạng" nói chung).
- Loại các type đó sẽ không cải thiện đáng kể độ phủ OOD trên tập test, vì `test.jsonl` không có đủ mẫu của type đó để đánh giá (ví dụ `universe_positive_count` chỉ có 1 mẫu trong test).

## Các file output

- `train.ood.jsonl` — tập train sau khi loại 7 type trên (20,502 dòng).
- `train_ood_removed.jsonl` — 127 dòng bị loại, giữ lại để kiểm tra (các question_type này vẫn có mặt tự nhiên trong `test.jsonl`, nên không cần thêm xử lý phía test để eval OOD vẫn hợp lệ).

Được tạo bởi `build_ood_train.py` từ `train.norm.jsonl` (tập train đã chuẩn hóa bởi `normalize_questions.py`).
