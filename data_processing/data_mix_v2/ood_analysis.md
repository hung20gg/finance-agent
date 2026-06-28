# Phân tích OOD (out-of-distribution) cho tập train

Tài liệu này mô tả **chi tiết lý do, quy tắc và suy luận** đằng sau việc chọn dữ liệu nào để loại khỏi tập train, sao cho khi model trả lời đúng lúc eval thì đó là bằng chứng cho khả năng **generalize** (suy luận tổ hợp), chứ không phải ghi nhớ pattern câu hỏi đã thấy nhiều lần.

`train.ood.jsonl` được tạo từ `train.norm.jsonl` qua **2 giai đoạn giảm dữ liệu**, tái lập được bằng `build_ood_train.py` (seed cố định `SEED=42`):

| Giai đoạn | Cơ chế | Số dòng loại | Vai trò |
|---|---|---|---|
| 1. Type holdout | Loại 7 `question_type` theo 2 quy tắc bên dưới | 127 | **Tạo tín hiệu OOD** |
| 2. Stratified downsample | Cắt phần còn lại (phân tầng theo `question_type`) còn 60% | 8,201 | Giảm khối lượng, **giữ nguyên phân bố** |

**Kết quả:** `train.norm.jsonl` (20,629) → `train.ood.jsonl` (**12,301 dòng**). Giữ đủ **32 question_type** in-distribution và **toàn bộ dải thời gian 2020–2025** (1,553 dòng kỳ 2025).

---

## 0. Nguyên lý nền tảng: thế nào là một holdout OOD *hợp lệ*

### 0.1. Memorization vs generalization

Một model text2sql có thể trả lời đúng vì **hai lý do hoàn toàn khác nhau**:

- **Ghi nhớ (memorization):** trong train đã có rất nhiều câu hỏi cùng `question_type`, cùng khuôn mẫu SQL. Model chỉ cần khớp khuôn và thay tham số (mã cổ phiếu, quý). Trả lời đúng ở đây **không chứng minh** model "hiểu" — nó chỉ tái tạo pattern.
- **Suy luận tổ hợp (compositional generalization):** model chưa từng thấy đúng *dạng câu hỏi* đó, nhưng đã thấy **các thành phần** của nó (entity, metric, kỳ thời gian, và các *kỹ năng con* như sort/argmax/so sánh). Để trả lời đúng, model phải **ghép** các mảnh đã biết theo một cách mới. Đây mới là tín hiệu generalization.

Mục tiêu của thiết kế OOD là tách bạch hai nguồn này: nếu một `question_type` **vắng mặt (gần như) hoàn toàn trong train** nhưng model vẫn trả lời đúng nó trong test, thì khả năng cao đó là suy luận, không phải học vẹt.

### 0.2. Điều kiện để holdout là OOD *hợp lệ* (không phải "miền chưa từng thấy")

Đây là điểm cốt lõi và dễ làm sai nhất. Có một ranh giới quan trọng:

> **OOD hợp lệ ≠ miền hoàn toàn không thấy (unseen domain).**

Nếu ta loại một kỹ năng mà model **chưa hề thấy ở bất kỳ đâu trong train**, thì việc nó trả lời sai là điều hiển nhiên — và việc nó trả lời đúng (nếu có) cũng không diễn giải được, vì ta đã yêu cầu nó làm điều bất khả thi (không có nền tảng để suy ra). Đó là test "ngoài khả năng", không phải test "ngoài phân bố".

Một holdout OOD hợp lệ phải thỏa **nguyên lý khối xây dựng (building-block principle):**

> Mọi **thành phần** của `question_type` bị loại — entity, metric, kỳ thời gian, và *kỹ năng con* — vẫn phải **xuất hiện ở các `question_type` còn giữ lại** trong train. Cái duy nhất bị giấu đi là **tổ hợp cụ thể** định nghĩa nên type đó.

Khi điều kiện này thỏa, một câu trả lời đúng cho type bị loại buộc phải đến từ việc ghép các mảnh đã biết → bằng chứng generalization sạch.

---

## 1. Quy tắc lựa chọn — chọn *thông tin nào* để loại

### 1.1. Hai quy tắc chọn type

Việc chọn 7 type không theo một tiêu chí duy nhất mà theo **hai quy tắc bổ trợ**, mỗi quy tắc nhắm một mục đích khác nhau:

**Quy tắc A — "đầu dò OOD đo được" (evaluable probe).**
Chọn type **phổ biến trong test nhưng gần như vắng trong train**. Tín hiệu định lượng là tỉ lệ `test_count / train_count` cao bất thường. Vì type đã gần như không có trong train, mọi câu đúng trong test là generalization; vì type có nhiều mẫu trong test, ta **đo được** khả năng đó một cách có ý nghĩa thống kê.

Tham chiếu định lượng (đã kiểm chứng trên dữ liệu thực):

| Đại lượng | Giá trị |
|---|---|
| Trung vị `test/train ratio` của các type **in-distribution** | **0.018** |
| Max `test/train ratio` của type in-distribution | 0.485 |
| `macro_highest_year` | train=3, test=99 → ratio **33.0** (gấp ~68× max in-dist) |
| `macro_lowest_year` | train=3, test=99 → ratio **33.0** |

Hai type macro argmax/argmin nổi bật hẳn: chúng chiếm ~5% test mỗi loại nhưng chỉ có 3 mẫu train → ứng viên OOD lý tưởng theo Quy tắc A.

**Quy tắc B — "chặn rò rỉ học vẹt" (memorization-leak guard).**
Chọn type mà **không gian giá trị đóng và nhỏ**, nên nếu để lại trong train, model sẽ học thuộc lòng toàn bộ không gian đó và làm "ô nhiễm" tuyên bố generalization của chính các *kỹ năng anh em*. Các type này thường có ít mẫu cả ở train lẫn test (test ≤ 7), nên giá trị đo trực tiếp thấp, nhưng việc loại chúng giữ cho train **sạch** khỏi đúng pattern dễ bị nhớ.

| question_type | train | test | Vì sao là rủi ro học vẹt |
|---|---|---|---|
| `index_direct` | 57 | 7 | Chỉ có ~9 chỉ số (VN30, VNINDEX, FTSE, HSI, KOSPI, NASDAQ, NIKKEI, SP500, STI). Không gian entity cực nhỏ, đóng → giữ lại là mời gọi học thuộc. |
| `universe_top` | 7 | 1 | Xếp hạng trên *toàn thị trường* — một phạm vi cố định, dễ nhớ kết quả. |
| `company_vs_company_yearly_diff` | 41 | 2 | So sánh 2 công ty **theo năm** — biến thể hẹp của kỹ năng so sánh theo quý. |
| `stock_vs_commodity_diff` | 12 | 1 | So sánh chéo miền (cổ phiếu × hàng hóa) — tổ hợp đóng, hiếm. |
| `commodity_top` | 4 | 1 | Top-N hàng hóa — danh sách hàng hóa cố định. |

### 1.2. Kiểm chứng nguyên lý khối xây dựng (bằng chứng định lượng)

Đây là phần đảm bảo mỗi type bị loại là OOD hợp lệ chứ không phải "miền chưa thấy". Với từng type, ta kiểm tra: **các thành phần của nó có còn xuất hiện trong train còn giữ lại không?**

| Type bị loại | Thành phần | Có mặt trong train còn lại? (số đếm đã kiểm chứng) | Kỹ năng anh em (sibling) còn giữ |
|---|---|---|---|
| `macro_highest_year` / `_lowest_year` | metric `lending_rate_pct` | ✅ xuất hiện **50** lần trong `macro_direct`/`macro_yoy_change_pct` | `macro_direct` (truy vấn macro), `macro_yoy_change_pct` (biến thiên macro) |
| `index_direct` | entity chỉ số VN | ✅ `VNINDEX` **239** lần, `VN30` **79** lần (trong các type so sánh benchmark) | `stock_vs_benchmark_diff`, `company_vs_benchmark_time_range` |
| `commodity_top` | entity hàng hóa | ✅ **toàn bộ** hàng hóa (Gold, Copper, Coffee, Brent, Cocoa...) đều có trong `commodity_direct` | `commodity_direct` (truy vấn giá hàng hóa), `industry_top` (kỹ năng Top-N) |
| `universe_top` | kỹ năng xếp hạng Top-N | ✅ kỹ năng rank có trong `industry_top` (**521** mẫu) | `industry_top` (Top-N trong nhóm ngành) |
| `stock_vs_commodity_diff` | hai nửa của phép so sánh | ✅ `stock_vs_benchmark_diff` (**105**) + `commodity_direct` (**127**) | mỗi nửa có riêng, chỉ thiếu tổ hợp chéo miền |
| `company_vs_company_yearly_diff` | so sánh 2 công ty | ✅ `company_vs_company_diff` (**385**) + `company_vs_company_winner` (**410**), chỉ khác trục thời gian (quý→năm) | so sánh theo quý vẫn được luyện đầy đủ |

Đọc bảng trên theo nguyên lý khối xây dựng:
- Model **đã thấy** chỉ số VNINDEX (239 lần) trong ngữ cảnh so sánh benchmark, chỉ **chưa thấy** câu "giá trị chỉ số X là bao nhiêu" trực tiếp → nếu trả lời đúng `index_direct`, đó là chuyển giao (transfer) ngữ cảnh.
- Model **đã thấy** `lending_rate_pct` (50 lần) và **đã thấy** kỹ năng argmax (qua các type "quý tốt nhất trong năm") → ghép hai mảnh để trả lời "năm nào lãi suất cao nhất" là suy luận tổ hợp đúng nghĩa.
- Model **đã thấy** mọi hàng hóa trong `commodity_direct` và **đã thấy** kỹ năng Top-N trong `industry_top` → `commodity_top` chỉ là tổ hợp mới của hai thứ đã biết.

### 1.3. Một sắc thái trung thực (caveat)

Không phải mọi thành phần đều thỏa nguyên lý khối xây dựng một cách hoàn hảo. Cụ thể: các chỉ số **nước ngoài** (FTSE, HSI, KOSPI, NASDAQ, NIKKEI, SP500, STI) **không** xuất hiện ở bất kỳ type nào còn giữ lại trong train (chỉ VN30 và VNINDEX còn). Do đó:

> Với phần chỉ số nước ngoài, `index_direct` thực chất là **entity-OOD** (entity chưa từng thấy), gần với "miền chưa thấy" hơn là "tổ hợp chưa thấy".

Đây là giới hạn cần ghi nhớ khi diễn giải kết quả: nếu model sai trên các chỉ số nước ngoài, đừng quy kết là "không generalize" — nó đơn giản chưa từng thấy các entity đó. Phần `index_direct` có giá trị OOD compositional **chỉ** cho VN30/VNINDEX.

---

## 2. Các trục OOD đã cân nhắc và vì sao **không** dùng

Việc chọn loại theo `question_type` là một trong nhiều trục khả dĩ. Dưới đây là các trục đã cân nhắc và lý do loại bỏ:

| Trục OOD | Mô tả | Vì sao không dùng (cho thiết kế hiện tại) |
|---|---|---|
| **Loại thêm type để đạt 40%** | Mở rộng type holdout (thêm `industry_mean` 540, `macro_direct` 198, `industry_top` 133...) đến khi cắt đủ 40% | Sẽ phải bỏ **trọn họ kỹ năng** industry/macro. Model không còn thấy kỹ năng đó *ở bất kỳ đâu* → vi phạm nguyên lý khối xây dựng → biến thành "miền chưa thấy", không phải OOD. |
| **Temporal holdout** | Loại toàn bộ kỳ 2025 khỏi train, tạo OOD "ngoại suy tương lai" (train ≤ 2024, test = 2025-Q3/Q4) | Đã cân nhắc và **bỏ** theo yêu cầu: ta muốn **giữ 2025 trong train** để model học được pattern gần đây. Đánh đổi: từ bỏ một trục OOD thời gian rất sạch (test vốn bị chi phối bởi 2025-Q3/Q4). |
| **Entity holdout có chủ đích** | Giấu một tập mã cổ phiếu/ngành khỏi train để test entity chưa thấy | Khó kiểm soát: nhiều type chia sẻ entity, dễ rò rỉ; và làm méo phân bố theo entity. Không chọn để giữ phân bố train sạch. |
| **Random downsample không phân tầng** | Cắt 40% hoàn toàn ngẫu nhiên | Rủi ro làm lệch phân bố type (type hiếm có thể bị cắt mất tỉ lệ lớn). Thay bằng **phân tầng** (Giai đoạn 2). |

---

## 3. Giai đoạn 2 — Stratified downsample (giữ phân bố)

Sau Giai đoạn 1 còn 20,502 dòng. Giai đoạn 2 cắt còn **12,301 dòng** = 60% (giảm thêm 40%).

**Vì sao downsample KHÔNG làm ô nhiễm tín hiệu OOD:**
- Nó được áp dụng **sau** type holdout, **chỉ trên** các type in-distribution. Nó không đụng tới việc type nào bị giấu.
- **Phân tầng theo `question_type`**: quota mỗi type tỉ lệ với kích thước (làm tròn largest-remainder), lấy mẫu trong từng type bằng seed cố định → cả 32 type đều còn, và tỉ trọng từng type trước/sau khớp đến **0.01%** (đã kiểm chứng: `company_direct` 16.25%→16.25%, `industry_mean` 10.87%→10.87%).
- Vì cắt theo tỉ lệ, **mọi kỳ thời gian (kể cả 2025) được giữ proportionally** (còn 1,553 dòng kỳ 2025).

Nói cách khác: Giai đoạn 2 chỉ giảm **mật độ lặp** của các pattern in-distribution (giảm chi phí train, giảm rủi ro overfit do lặp), mà **không** thêm hay bớt bất kỳ trục OOD nào. Toàn bộ tín hiệu OOD đến từ Giai đoạn 1.

---

## 4. Giả định & rủi ro với hiệu lực của thiết kế (threats to validity)

| Giả định / rủi ro | Hệ quả nếu sai | Giảm thiểu |
|---|---|---|
| Type bị loại **thực sự gần như vắng** trong train | Nếu còn sót nhiều mẫu, "OOD" bị nhiễm bởi memorization | Đã kiểm: train count ≤ 57, đa số ≤ 12; macro chỉ 3 |
| Thành phần của type bị loại **vẫn có** trong train còn lại | Nếu không, thành "miền chưa thấy" → sai mất đi ý nghĩa | Đã kiểm chứng bảng §1.2; ngoại lệ chỉ số nước ngoài đã ghi ở §1.3 |
| Test **có đủ mẫu** của type bị loại để đo | Nếu test chỉ 1–2 mẫu, ước lượng độ chính xác OOD nhiễu lớn | Quy tắc A (macro) test=99 đủ tốt; Quy tắc B (test ≤ 7) **chủ yếu để giữ train sạch**, không kỳ vọng đo chính xác |
| Không rò rỉ qua `extra_info`/`question_raw` chứa lời giải | Model học tắt | Train không chứa SQL/đáp án ở phần prompt khi eval |
| Downsample không vô tình bỏ hết một biến thể hiếm | Mất coverage kỹ năng in-dist | Phân tầng theo type + largest-remainder đảm bảo mọi type còn ≥ quota |

---

## 5. Cách đọc kết quả eval (falsifiability)

- **Đầu dò chính (Quy tắc A) — `macro_highest_year` / `macro_lowest_year`:** đây là phép đo OOD đáng tin nhất (test=99 mỗi loại, train≈0). Độ chính xác cao ở đây = bằng chứng mạnh cho suy luận argmax/argmin trên chuỗi macro mà model **không** học vẹt được.
- **Các type Quy tắc B (`index_direct`, `commodity_top`, `universe_top`, `stock_vs_commodity_diff`, `company_vs_company_yearly_diff`):** test ít mẫu nên xem là tín hiệu **định tính**, không phải con số chính xác. Đúng → gợi ý transfer/compositional tốt; sai → cần soi xem là do thiếu kỹ năng hay thiếu entity (xem caveat §1.3).
- **In-distribution (32 type còn lại):** dùng làm **baseline** — nếu OOD ≈ in-dist thì generalization tốt; nếu OOD ≪ in-dist thì model đang dựa vào memorization nhiều hơn.

---

## 6. Các file output

| File | Số dòng | Ý nghĩa |
|---|---|---|
| `train.ood.jsonl` | 12,301 | Tập train cuối cùng. Năm 2020–2025, đủ 32 question_type, phân bố bảo toàn. |
| `train_ood_removed.jsonl` | 127 | 127 dòng bị loại ở Giai đoạn 1 (type holdout). Các type này vẫn có trong `test.jsonl` nên eval OOD theo type hợp lệ. |

Các dòng bị loại ở Giai đoạn 2 (downsample) không lưu riêng — tái lập được bằng cách chạy lại `build_ood_train.py` (cùng `SEED=42`).

---

### Phụ lục — bảng 7 type holdout (tóm tắt lý do, gộp cả 2 quy tắc)

| question_type | train | test | Quy tắc | Lý do cô đọng |
|---|---|---|---|---|
| `macro_highest_year` | 3 | 99 | A | argmax trên chuỗi macro; gần như vắng train, dày test. |
| `macro_lowest_year` | 3 | 99 | A | argmin, biến thể của trên. |
| `index_direct` | 57 | 7 | B | ~9 chỉ số, không gian entity đóng/nhỏ → dễ học vẹt. |
| `company_vs_company_yearly_diff` | 41 | 2 | B | so sánh 2 công ty theo năm; biến thể hẹp của so sánh theo quý. |
| `stock_vs_commodity_diff` | 12 | 1 | B | so sánh chéo miền cổ phiếu × hàng hóa; tổ hợp đóng hiếm. |
| `universe_top` | 7 | 1 | B | Top-N toàn thị trường; phạm vi cố định. |
| `commodity_top` | 4 | 1 | B | Top-N hàng hóa; danh sách cố định. |

Được tạo bởi `build_ood_train.py` từ `train.norm.jsonl` (đã chuẩn hóa bởi `normalize_questions.py`).
