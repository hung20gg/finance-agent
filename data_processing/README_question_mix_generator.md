# README - Question Mix Generator V4

## Mục tiêu

File `question_mix_generator_v4.py` dùng để sinh bộ câu hỏi tài chính tiếng Việt từ BigQuery.

Bản này được viết theo các yêu cầu sau:

1. Trộn nhiều loại câu hỏi: `calculate`, `compare`, `roll_up`, `drill_down`.
2. Có so sánh `company vs industry average` bằng bảng `company_info(stock_code, industry)`.
3. Có câu hỏi `top 5`, `top 10`.
4. Có câu hỏi `liệt kê theo dải thời gian`.
5. Có câu hỏi `lấy nhiều dữ liệu để visualize`.
6. Một số câu khó có thể để `answer = null`.
7. Có thêm `metadata` rõ cho câu top, list và visualize.
8. Có lớp câu hỏi mơ hồ với tỷ lệ mặc định `10%`.
9. `val` và `test` được khóa tối đa `2.000` câu mỗi split.
10. Khi phải random downsample, hệ thống sẽ ưu tiên giữ câu ngành, chỉ số, commodity trước; phần stock-related sẽ tăng trọng số cho mã VN30 lên `x5`.

---

## Các bảng dữ liệu đang giả định

Code đang giả định các bảng sau nằm trong BigQuery dataset `neusolution.ktln` hoặc prefix bạn truyền vào:

- `stock_daily`
- `indices_daily`
- `commodities_daily`
- `financial_statement`
- `financial_ratio`
- `macro`
- `company_info`

### Các cột quan trọng đang dùng

#### `company_info`
- `stock_code`
- `industry`
- `is_bank`
- `is_securities`

#### `stock_daily`
- `stock_code`
- `time`
- `close`

#### `indices_daily`
- `index_name`
- `time`
- `close`

#### `commodities_daily`
- `indicator_name`
- `time`
- `value`

#### `financial_statement`
- `stock_code`
- `year`
- `quarter`
- `category_code`
- `data`
- `segment`

#### `financial_ratio`
- `stock_code`
- `year`
- `quarter`
- `ratio_code`
- `data`
- `segment`

#### `macro`
- `indicator_name`
- `datetime`
- `value`

Nếu schema thật khác một chút, bạn chỉ cần sửa các SQL trong lớp `BigQueryLoader`.

---

## Ý tưởng chính của pipeline

Code được chia thành 4 tầng.

### 1. `BigQueryLoader`
Chỉ lo query dữ liệu từ BigQuery.

Các việc chính:
- Lấy universe mã cổ phiếu từ BigQuery.
- Lấy `industry` thật từ `company_info`.
- Lấy dữ liệu stock/index/commodity theo tháng và quý.
- Lấy báo cáo tài chính, ratio và macro.

Ngoài ra, loader cũng đọc hai cờ `is_bank` và `is_securities` từ `company_info` để chuẩn hóa cách gọi tên doanh nghiệp trong câu hỏi.

### 2. `FeatureStoreBuilder`
Biến dữ liệu gốc thành các bảng trung gian dễ sinh câu hỏi hơn.

Các bảng trung gian quan trọng:
- `company_quarter`
- `company_month`
- `industry_avg_quarter`
- `peer_rollups`

Trong đó:
- `company_quarter` là bảng trung tâm.
- `industry_avg_quarter` là bảng để so sánh công ty với trung bình ngành.
- `peer_rollups` giữ thêm một số nhóm logic từ code cũ.

### 3. `QuestionGenerator`
Sinh câu hỏi theo từng họ.

- `generate_calculate_questions()`
- `generate_compare_questions()`
- `generate_rollup_questions()`
- `generate_drilldown_questions()`
- `generate_ambiguous_questions()`

### 4. Export
Xuất ra:
- `train.jsonl`
- `val.jsonl`
- `test.jsonl`
- `summary.json`

Ở bản V4, sau bước split theo `time_asked`, generator sẽ còn áp dụng thêm một lớp cắt kích thước cho `val` và `test` để mỗi split chỉ còn tối đa `2.000` câu.

---

## Quy tắc gọi tên doanh nghiệp

Từ bản cập nhật này, code sẽ không gọi mọi mã là `công ty` theo một cách cố định nữa.

Quy tắc ưu tiên:
1. Nếu `company_info.is_bank = True` thì gọi là `ngân hàng {MÃ}`
2. Nếu `company_info.is_securities = True` thì gọi là `công ty chứng khoán {MÃ}`
3. Còn lại gọi là `công ty {MÃ}`

Ví dụ:
- `MSB` -> `ngân hàng MSB`
- `SSI` -> `công ty chứng khoán SSI`
- `FPT` -> `công ty FPT`

Rule này được áp dụng cho các câu hỏi kiểu doanh nghiệp như calculate theo báo cáo tài chính, compare công ty với công ty, compare công ty với trung bình ngành, và các câu liệt kê theo dải thời gian.

## So sánh công ty với trung bình ngành

Đây là thay đổi quan trọng nhất.

Code không dùng ngành hard-code để so sánh.
Thay vào đó nó:

1. Lấy `industry` của từng `stock_code` từ `company_info`.
2. Gắn `industry` vào `company_quarter`.
3. Group theo `(industry, year, quarter)`.
4. Tính `mean` và `median` cho từng metric.
5. Sinh câu hỏi:
   - công ty cao hơn hay thấp hơn trung bình ngành
   - công ty chênh trung bình ngành bao nhiêu
   - trung bình ngành của một metric là bao nhiêu

Ví dụ:
- `Trong quý 2 năm 2025, ROE của ngân hàng MBB cao hơn hay thấp hơn mức trung bình ngành Ngân hàng?`
- `Trong quý 2 năm 2025, ROE của ngân hàng MBB chênh trung bình ngành Ngân hàng bao nhiêu?`

---

## Các loại câu hỏi chính

## 1. Calculate
Ví dụ:
- Giá trị trực tiếp của công ty theo quý
- Giá trị trực tiếp của công ty theo tháng
- Giá trị trực tiếp của index / commodity
- Trung bình ngành của một metric

## 2. Compare
Ví dụ:
- Công ty A vs công ty B trong cùng kỳ
- Cùng công ty qua 2 kỳ
- Công ty vs benchmark index
- Công ty vs trung bình ngành
- Cổ phiếu vs commodity liên quan

## 3. Roll up
Ví dụ:
- Mean / median theo ngành
- Số lượng công ty có metric dương trong ngành
- Số lượng công ty có metric dương trên toàn universe
- Mean / median cho peer group

## 4. Drill down
Ví dụ:
- Top 1, top 5, top 10 trong ngành
- Top 5, top 10 trên toàn universe
- Top index / commodity theo quý
- Liệt kê theo dải thời gian
- Câu lấy dữ liệu để vẽ chart

---

## Câu hỏi top 5, top 10

Code có sinh:
- `top 5`
- `top 10`

Ví dụ:
- `Trong ngành Ngân hàng ở quý 1 năm 2025, top 5 mã theo ROE là những mã nào?`
- `Trong quý 2 năm 2025, top 10 cổ phiếu theo tỷ suất sinh lời trên toàn bộ universe là những mã nào?`

### Chính sách answer
- Câu `top 5` thường vẫn có answer.
- Câu `top 10` có thể để `answer = null` nếu bật chế độ bỏ answer cho câu khó.

---

## Câu liệt kê theo dải thời gian

Nhóm này trả về nhiều điểm dữ liệu hơn, phù hợp cho line chart hoặc table.

Ví dụ:
- `Liệt kê ROE theo từng quý của công ty FPT từ 2024-Q1 đến 2024-Q4.`
- `Liệt kê tỷ suất sinh lời theo từng quý của công ty FPT và VNINDEX từ 2024-Q1 đến 2024-Q4.`

Thông thường các câu này có metadata kiểu:
- `request_mode = time_range_listing`
- `range_type = quarter`
- `start_period`
- `end_period`
- `result_columns`
- `suggested_visualization`

Một phần các câu này có thể để `answer = null`.

---

## Câu phục vụ visualize

Đây là nhóm câu không chỉ hỏi một scalar đơn.
Mục tiêu là yêu cầu lấy ra data frame nhỏ để vẽ chart.

Ví dụ:
- `Lấy dữ liệu để vẽ bar chart top 10 công ty ngành Ngân hàng theo ROE trong quý 2 năm 2025.`
- `Lấy dữ liệu để vẽ heatmap tỷ suất sinh lời theo quý cho top 10 mã của ngành Dầu khí trong 4 quý gần nhất.`
- `Lấy dữ liệu để vẽ scatter so sánh ROE của từng công ty với mức trung bình ngành trong quý 1 năm 2025.`

Các câu này mặc định thường có:
- `answer = null`
- metadata rất rõ để downstream biết cần query / render thế nào

Metadata thường gồm:
- `request_mode = visualize`
- `visualization_hint`
- `group_by`
- `industry`
- `is_bank`
- `is_securities`
- `sort_metric`
- `result_columns`
- `answer_expected = false`

---

## Câu mơ hồ 10%

Code giữ tỷ lệ mặc định `10%` câu hỏi mơ hồ.

Nó hoạt động bằng cách:
1. Sinh bộ câu hỏi rõ nghĩa trước.
2. Chọn ngẫu nhiên một phần câu hỏi.
3. Đổi một số từ hoặc cụm từ theo rule có kiểm soát.

Ví dụ:
- `VNINDEX` -> `thị trường chung`
- `tỷ suất sinh lời` -> `mức sinh lời`
- `trung bình ngành` -> `mức trung bình của ngành`

Câu mơ hồ vẫn giữ được metadata và quan hệ với câu gốc qua:
- `resolved_from_clear_question`
- `ambiguity_rule`

---

## Cấu trúc output JSONL

Mỗi dòng có dạng gần như sau:

```json
{
  "id": "train-00000001",
  "question_raw": "Trong quý 2 năm 2025, ROE của ngân hàng MBB cao hơn hay thấp hơn mức trung bình ngành Ngân hàng?",
  "answer_type": "entity",
  "answer": "cao hơn",
  "question_family": "compare",
  "question_subtype": "company_vs_industry_avg_direction_ROE",
  "ambiguity": "clear",
  "time_asked": "2025-08-14",
  "gap": 2,
  "data_cutoff": "2025-08-14",
  "entities": ["MBB", "Banking"],
  "metrics": ["ROE"],
  "periods": ["2025-Q2"],
  "sources": ["company_quarter", "industry_avg_quarter"],
  "reasoning_hops": 2,
  "extra_info": {
    "company_value": 18.23,
    "industry_mean": 15.44,
    "industry": "Banking"
  }
}
```

### Lưu ý
- `answer_type` chỉ có `entity` hoặc `tuple`.
- `answer` có thể là `null` ở một số câu khó.

---

## Chạy code

### Cách 1: dùng credential từ biến môi trường

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service_account.json
python question_mix_generator_v4.py --output-dir data_mix_v4
```

### Cách 2: truyền key path trực tiếp

```bash
python question_mix_generator_v4.py \
  --key-path /path/to/service_account.json \
  --output-dir data_mix_v4 \
  --total-target-samples 22000 \
  --ambiguous-ratio 0.10
```

### Nếu muốn giữ answer cả ở câu khó

```bash
python question_mix_generator_v4.py \
  --key-path /path/to/service_account.json \
  --keep-answer-for-complex
```

---

## Các file output

Trong thư mục output sẽ có:

- `train.jsonl`
- `val.jsonl`
- `test.jsonl`
- `summary.json`

### `summary.json` có gì
- số lượng record theo split
- số câu ambiguous
- số câu thiếu answer
- phân bố theo family
- phân bố theo subtype
- phân bố theo answer_type

---

## Những chỗ bạn có thể chỉnh nhanh

## 1. Thêm metric mới
Sửa ở các chỗ:
- `FINANCIAL_CATEGORY_MAP`
- `FINANCIAL_NAMES`
- `RATIO_NAMES`
- các list metric trong từng generator

## 2. Thêm câu compare mới
Sửa trong:
- `generate_compare_questions()`

## 3. Thêm chart mới
Sửa trong:
- `_generate_visualize_questions()`

## 4. Thay chiến lược bỏ answer
Sửa trong:
- `GeneratorConfig.answerless_modes`
- `QuestionGenerator._maybe_answer()`

## 5. Đổi split train/val/test
Sửa trong:
- `GeneratorConfig.train_end`
- `GeneratorConfig.val_end`

---

## Các điểm cần kiểm tra khi chạy thật

1. Tên bảng và cột trong BigQuery có khớp không.
2. `company_info.industry` có đúng format string như kỳ vọng không.
3. Các index có tồn tại đúng tên: FTSE, HSI, KOSPI, NASDAQ, NIKKEI, SP500, STI, VN30, VNINDEX.
4. Commodity names trong DB có khớp với `DEFAULT_COMMODITY_DISPLAY` không.
5. Các cột financial / ratio có đủ coverage cho 150 mã không.

---

## Gợi ý mở rộng tiếp

- Thêm mapping ngành -> commodity nhạy cảm để compare phong phú hơn.
- Thêm `rank within industry` vào metadata.
- Thêm câu dạng contributor / attribution.
- Thêm câu list theo tháng cho market data.
- Thêm export một file `debug_samples.json` để xem nhanh 100 record đầu.



## Rule downsample cho val/test

Đây là thay đổi mới trong bản V4.

Sau khi toàn bộ câu hỏi được sinh xong và chia theo `train / val / test` bằng `time_asked`, code sẽ kiểm tra kích thước của `val` và `test`:

- nếu số câu nhỏ hơn hoặc bằng `2.000` thì giữ nguyên
- nếu lớn hơn `2.000` thì downsample theo thứ tự ưu tiên

### Thứ tự ưu tiên

### Nhóm 1: giữ trước
Bao gồm các câu hỏi có trọng tâm là:
- ngành
- chỉ số
- commodity

Ví dụ:
- `industry_mean_*`
- `industry_top*`
- `company_vs_industry_*`
- `index_direct_*`
- `index_top*`
- `commodity_direct_*`
- `commodity_top*`
- các câu visualize / time range có chuẩn ngành

### Nhóm 2: stock-related
Phần còn lại được xem là stock-related.
Ví dụ:
- company direct
- company vs company
- stock vs benchmark
- time range của doanh nghiệp
- top universe theo cổ phiếu

Trong nhóm này, nếu câu hỏi chứa ít nhất một mã thuộc VN30 thì xác suất được giữ lại sẽ cao hơn `5` lần so với câu không chứa mã VN30.

### Cách hiểu thực tế

Điều này giúp:
- không làm mất các câu ngành / index / commodity khi `val` và `test` bị cắt bớt
- giữ nhiều hơn các câu liên quan đến nhóm bluechip VN30 trong phần stock-related
- vẫn giữ tính ngẫu nhiên thay vì hard-code chọn toàn bộ một tập con cố định

---

## CLI mới

Ngoài các tham số cũ, bản V4 thêm:

- `--val-target-size`
- `--test-target-size`

Mặc định:

```bash
--val-target-size 2000
--test-target-size 2000
```

Ví dụ chạy:

```bash
python question_mix_generator_v4.py \
  --key-path /path/to/service_account.json \
  --project-table-prefix neusolution.ktln \
  --output-dir data_mix_v4 \
  --total-target-samples 22000 \
  --ambiguous-ratio 0.10 \
  --val-target-size 2000 \
  --test-target-size 2000
```

