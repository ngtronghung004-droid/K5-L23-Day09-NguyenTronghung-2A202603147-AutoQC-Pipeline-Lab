# BÁO CÁO DAY 09 – AUTOQC PIPELINE

**Họ và tên:** Nguyễn Trọng Hùng
**Mã học viên:** 2A202603147
**Bài thực hành:** Day 09 – AutoQC Pipeline

---

## 1. Kết luận tổng quan

Pipeline đã chạy hoàn tất và đưa ra kết luận **HOLD** vì tỉ lệ ảnh còn cảnh báo vượt ngưỡng cho phép.

Kết quả lần chạy thực tế:

| Chỉ tiêu | Kết quả |
|---|---:|
| Tổng ảnh đầu vào | 224 |
| Ảnh được Intake chấp nhận | 193 |
| Ảnh bị loại tại Intake | 31 |
| Lỗi ERROR cuối cùng | 0 |
| Số ảnh còn cảnh báo | 34 |
| Tổng số dòng cảnh báo | 66 |
| Tỉ lệ ảnh có cảnh báo | 17.62% |
| Ngưỡng cảnh báo cho phép | 10.00% |
| Số ảnh đã mô phỏng duyệt | 80/80 |
| Thời gian chạy Pipeline | 17.7 giây |
| Kết luận Gate | HOLD |

Dữ liệu đầu vào gồm 224 ảnh trong `data/raw`. Sau bước Intake, có 193 ảnh được chấp nhận và 31 ảnh bị loại do các điều kiện kiểm tra đầu vào.

Pipeline thực hiện kiểm tra chất lượng nhãn, tự động sửa các lỗi có thể xử lý an toàn, mô phỏng quá trình người duyệt và chạy kiểm tra cuối cùng.

Kết quả cuối cùng không còn lỗi bắt buộc (`n_errors = 0`). Tuy nhiên, vẫn còn 34/193 ảnh có cảnh báo, tương ứng 17.62%, cao hơn ngưỡng 10%.

Dataset được xuất dưới dạng bản nháp tại:

`submission/export/clean_v1`

Đây là bản nháp phục vụ thử nghiệm, chưa được phát hành chính thức do Gate đưa ra quyết định HOLD.

**Nhận xét:** HOLD không đồng nghĩa Pipeline chạy thất bại. Đây là cơ chế kiểm soát chất lượng nhằm ngăn dataset chưa được xác minh đầy đủ đi vào bước huấn luyện hoặc phát hành chính thức.

---

## 2. Quy trình kiểm tra và xử lý dữ liệu

Pipeline thực hiện các bước chính:

1. Intake: kiểm tra ảnh hỏng, kích thước, ảnh trùng và rò rỉ dữ liệu test.
2. QC vòng 1: kiểm tra định dạng nhãn và các vấn đề về bounding box.
3. Autofix: tự động sửa những lỗi có thể xử lý an toàn.
4. QC vòng 2: kiểm tra lại dữ liệu sau khi tự động sửa.
5. Human Review: mô phỏng người duyệt với ngân sách tối đa 80 ảnh.
6. QC vòng 3 và Gate: kiểm tra lần cuối, quyết định Release, Hold hoặc Rework.
7. Export: xuất dataset bản nháp nếu Pipeline cho phép.

### 2.1. Kết quả Intake

Pipeline ghi nhận:

- Tổng số ảnh đầu vào: 224.
- Số ảnh được chấp nhận: 193.
- Số ảnh bị loại: 31.

Các nhóm vấn đề được Intake kiểm tra gồm:

- `CORRUPT_IMAGE`: ảnh hỏng, không đọc được.
- `BAD_SIZE`: ảnh không đạt kích thước tối thiểu.
- `DUP_IMAGE_EXACT`: ảnh trùng hoàn toàn.
- `DUP_IMAGE_NEAR`: ảnh trùng gần đúng.
- `LEAK_TEST`: ảnh có nguy cơ rò rỉ từ tập test hoặc tập tham chiếu.

Việc loại bỏ các ảnh không hợp lệ, ảnh trùng và ảnh có nguy cơ rò rỉ giúp hạn chế dữ liệu không phù hợp trong tập huấn luyện.

Chi tiết kết quả Intake được lưu trong:

- `submission/reports/01_intake.csv`
- `submission/reports/01_intake.txt`

### 2.2. Kiểm tra định dạng và chất lượng nhãn

Module `label_format.py` kiểm tra các vấn đề như:

| Mã lỗi | Ý nghĩa | Hướng xử lý |
|---|---|---|
| `BAD_FORMAT` | Dòng nhãn sai định dạng YOLO | Xác định dòng không hợp lệ |
| `BAD_CLASS_ID` | ID lớp nằm ngoài danh sách cho phép | Kiểm tra ID lớp |
| `BOX_ZERO` | Box có chiều rộng hoặc chiều cao bằng 0 | Loại bỏ box không hợp lệ |
| `BOX_OUT_OF_IMAGE` | Box vượt ngoài biên ảnh | Cắt tọa độ về giới hạn hợp lệ khi an toàn |
| `DUP_BOX` | Box bị trùng lặp | Loại bỏ box trùng theo quy tắc |
| `BOX_TINY` | Box có cạnh ngắn dưới 12 px | Cảnh báo người duyệt |
| `BOX_HUGE` | Box chiếm diện tích quá lớn | Cảnh báo người duyệt |

Các lỗi cú pháp và tọa độ có thể xử lý theo quy tắc được chuyển cho module Autofix. Những trường hợp có thể liên quan đến ý nghĩa thực tế của vật thể cần người kiểm tra.

### 2.3. Kết quả Autofix

Trong lần chạy Pipeline:

- QC vòng 1 phát hiện 36 lỗi bắt buộc và 149 cảnh báo.
- Autofix thực hiện 35 thay đổi.
- Kết quả thay đổi được lưu trong `03_fixes.csv`.
- QC vòng 2 còn 6 lỗi bắt buộc.
- Sau mô phỏng người duyệt và QC vòng 3, số lỗi bắt buộc còn lại là 0.

Autofix chỉ xử lý những vấn đề có quy tắc sửa an toàn. Máy không tự tạo nhãn cho vật thể khi chưa có đủ căn cứ.

Ví dụ, ảnh chưa có file nhãn cần được chuyển cho người gán nhãn thay vì tự động tạo ra tọa độ bounding box.

---

## 3. Cơ chế người duyệt và kết quả cảnh báo cuối cùng

### 3.1. Human Review

Pipeline sử dụng ngân sách mô phỏng người duyệt:

- Số ảnh trong hàng đợi: 121.
- Ngân sách duyệt: 80 ảnh.
- Số ảnh đã mô phỏng duyệt: 80/80.

Hàng đợi được sắp xếp theo điểm ưu tiên dựa trên các trọng số trong cấu hình `review.weights`.

Những vấn đề có mức độ ảnh hưởng lớn đến chất lượng dữ liệu được ưu tiên xử lý trước, đặc biệt là các trường hợp cần bổ sung nhãn hoặc nghi ngờ sai lớp, thiếu vật thể.

Kết quả mô phỏng người duyệt được lưu trong:

`submission/reports/06_review_log.csv`

### 3.2. Thống kê cảnh báo sau người duyệt

Báo cáo cuối cùng `07_error_list_v3.txt` ghi nhận:

| Mã cảnh báo | Số dòng |
|---|---:|
| `BOX_HUGE` | 3 |
| `BOX_TINY` | 7 |
| `EMPTY_LABEL` | 3 |
| `POSSIBLE_FALSE_POS` | 20 |
| `POSSIBLE_LOOSE_BOX` | 18 |
| `POSSIBLE_MISSING` | 12 |
| `POSSIBLE_WRONG_CLASS` | 3 |
| **Tổng cộng** | **66** |

66 là tổng số dòng cảnh báo, không phải số ảnh khác nhau. Các cảnh báo có thể cùng xuất hiện trên một ảnh. Tổng số ảnh duy nhất còn cảnh báo là 34.

### 3.3. Phân tích các loại cảnh báo

**POSSIBLE_FALSE_POS – 20 dòng**

Box nhãn không khớp với dự đoán nào của model checker. Có thể nhãn đã gán nhầm vật thể, nhưng cũng có thể model không phát hiện được vật thể thật. Cần đối chiếu với ảnh gốc.

**POSSIBLE_LOOSE_BOX – 18 dòng**

Model phát hiện cùng lớp nhưng bounding box có IoU thấp hơn ngưỡng khớp. Đây là dấu hiệu box có thể quá rộng hoặc lệch vị trí.

**POSSIBLE_MISSING – 12 dòng**

Model phát hiện vật thể nhưng không tìm thấy box nhãn tương ứng. Người duyệt cần xác minh vật thể có thực sự tồn tại hay không trước khi bổ sung nhãn.

**POSSIBLE_WRONG_CLASS – 3 dòng**

Model dự đoán lớp khác với nhãn hiện tại dù vị trí box tương đối khớp. Đây là trường hợp cần người có chuyên môn xác minh lớp vật thể.

**BOX_TINY – 7 dòng**

Box có cạnh ngắn nhỏ hơn 12 px. Cần kiểm tra xem vật thể có thực sự nhỏ hay box được vẽ do nhiễu.

**BOX_HUGE – 3 dòng**

Box chiếm trên 95% diện tích ảnh. Cần xác minh vật thể có thực sự chiếm gần hết khung hình hay người gán nhãn đã chọn sai vùng.

**EMPTY_LABEL – 3 dòng**

File nhãn rỗng. Cần xác định ảnh có phải ảnh nền không chứa vật thể hay bị bỏ sót nhãn.

Các cảnh báo từ model checker chỉ mang tính chất gợi ý kiểm tra, không phải kết luận chắc chắn nhãn sai.

---

## 4. Calibration – Hiệu chỉnh hai ngưỡng

Calibration được thực hiện trên tập `data/calib/` gồm 39 ảnh. Mục tiêu là lựa chọn ngưỡng phù hợp dựa trên kết quả Precision, Recall và F1-score.

### 4.1. Ngưỡng duplicates.phash_dist

Tham số `duplicates.phash_dist` quyết định khoảng cách Hamming tối đa giữa hai perceptual hash để xem xét hai ảnh là trùng gần đúng.

Kết quả sweep:

| phash_dist | Exact F1 | Near F1 |
|---:|---:|---:|
| 2 | 1.00 | 0.67 |
| 4 | 1.00 | 0.80 |
| 6 | 1.00 | 0.80 |
| 8 | 1.00 | 0.80 |
| 10 | 1.00 | 0.80 |
| 12 | 1.00 | 0.80 |
| 14 | 1.00 | 0.80 |
| 16 | 1.00 | 0.91 |
| 20 | 0.50 | 0.67 |

Giá trị được lựa chọn: **16**.

Lý do:

- Ở ngưỡng 16, F1 của phát hiện ảnh trùng gần đạt 0.91, cao nhất trong các giá trị thử nghiệm.
- Khả năng phát hiện ảnh trùng gần được cải thiện so với các ngưỡng thấp hơn.
- Ở ngưỡng 20, hiệu quả phát hiện ảnh trùng chính xác giảm rõ rệt.

Tuy nhiên, tập calibration chỉ gồm 39 ảnh nên kết quả này chưa đủ để khẳng định ngưỡng 16 tối ưu cho mọi bộ dữ liệu. Những ảnh giao thông có bối cảnh giống nhau vẫn cần được kiểm tra để tránh loại nhầm ảnh độc lập.

### 4.2. Ngưỡng second_opinion.conf

Tham số `second_opinion.conf` quy định mức confidence tối thiểu của dự đoán từ model checker được sử dụng trong quá trình kiểm tra chéo.

Một số kết quả đáng chú ý:

| conf | WRONG_CLASS F1 | MISSING Precision | MISSING Recall | MISSING F1 |
|---:|---:|---:|---:|---:|
| 0.50 | 0.67 | 0.57 | 1.00 | 0.73 |
| 0.60 | 0.71 | 0.57 | 1.00 | 0.73 |
| 0.70 | 0.70 | 0.58 | 0.88 | 0.70 |
| 0.80 | 0.91 | 0.67 | 0.75 | 0.71 |

Giá trị được lựa chọn: **0.60**.

Lý do:

- F1 của WRONG_CLASS tăng từ 0.67 ở conf 0.50 lên 0.71 ở conf 0.60.
- Recall của MISSING vẫn đạt 1.00.
- Mức conf 0.80 giúp tăng F1 của WRONG_CLASS nhưng làm Recall của MISSING giảm còn 0.75.
- Mức 0.60 là lựa chọn cân bằng hơn giữa việc phát hiện sai lớp và không bỏ sót vật thể.

### 4.3. Cấu hình cuối cùng

Hai giá trị được sử dụng trong `configs/pipeline.yaml`:

```yaml
duplicates:
  phash_dist: 16

second_opinion:
  conf: 0.60
```

Các tham số còn lại được giữ theo quy tắc dự án.

**Lưu ý:** Calibration trên tập nhỏ có thể chưa đại diện đầy đủ cho dữ liệu thực tế. Vì vậy, kết quả cần được đánh giá thêm bằng kiểm tra thủ công và các lần chạy tiếp theo.

---

## 5. Gate – Cửa chặn chất lượng dữ liệu

Gate là thành phần quyết định dataset có đủ điều kiện được phát hành hay không.

Trong cấu hình hiện tại:

```yaml
gate:
  warn_ratio_hold: 0.10
```

Điều kiện Hold được kích hoạt khi tỉ lệ ảnh có cảnh báo chưa được người duyệt đạt hoặc vượt 10%.

Kết quả cuối cùng:

- Tổng số ảnh: 193.
- Số ảnh có cảnh báo: 34.
- Tỉ lệ cảnh báo: 17.62%.
- Ngưỡng cho phép: 10.00%.
- Số lỗi ERROR: 0.

Do 17.62% lớn hơn 10.00%, Gate kết luận HOLD.

Kết quả này được xác nhận trong `submission/reports/08_summary.json`.

### 5.1. Phân biệt các trạng thái

- **Release:** Dataset đáp ứng điều kiện chất lượng và được phép phát hành.
- **Hold:** Chưa có lỗi bắt buộc nhưng tỉ lệ cảnh báo còn vượt giới hạn.
- **Rework:** Còn lỗi bắt buộc cần xử lý trước khi tiếp tục.

Trong lần chạy hiện tại, dataset ở trạng thái HOLD chứ không phải REWORK.

### 5.2. Những giới hạn của Pipeline

Pipeline sử dụng các quy tắc và dự đoán của model để hỗ trợ kiểm tra, vì vậy vẫn tồn tại một số điểm mù:

1. Bounding box bị lỏng nhẹ nhưng IoU vẫn đạt ngưỡng khớp có thể không được phát hiện.
2. Vật thể bị che khuất hoặc quá khó nhận diện có thể bị bỏ sót nếu cả nhãn gốc và model checker đều không phát hiện.
3. Ảnh bị cắt cúp hoặc biến đổi mạnh có thể không được nhận diện là ảnh trùng gần đúng bằng perceptual hash.
4. Model checker có thể dự đoán sai lớp hoặc bỏ sót vật thể. Vì vậy không thể sử dụng dự đoán của model làm đáp án tuyệt đối.
5. Ảnh nhãn rỗng không nhất thiết là ảnh lỗi vì có thể đó là ảnh nền hợp lệ.

Do đó, kiểm tra thủ công vẫn là bước quan trọng để đảm bảo chất lượng dữ liệu.

---

## 6. Kiểm thử phần mềm và kiểm tra submission

Sau khi hoàn thiện các module:

- `label_format.py`
- `autofix.py`
- `gate.py`
- `second_opinion.py`

Đã thực hiện chạy bộ kiểm thử:

```bash
python -m pytest -q
```

Kết quả:

```text
79 passed
```

Toàn bộ 79 bài kiểm thử đều thành công.

Tiếp tục chạy:

```bash
python scripts/check_submission.py --no-train
```

Kết quả:

```text
pytest: 79 passed in 32.81s

kết luận pipeline: Hold - Tỉ lệ ảnh có cảnh báo
17.62% (34/193) >= ngưỡng 10.00%.

CẢNH BÁO: bỏ qua phần train (--no-train):
phần train 15 điểm chấm riêng, làm sau khi có Colab

0 lỗi, 1 cảnh báo
```

Như vậy, phần kiểm tra cốt lõi của submission không phát hiện lỗi. Cảnh báo duy nhất liên quan đến việc chưa thực hiện phần huấn luyện mô hình.

---

## 7. Huấn luyện và so sánh mô hình

Tại thời điểm hoàn thành báo cáo này, phần huấn luyện so sánh `raw` và `clean` chưa được thực hiện.

Phần này dự kiến được thực hiện trên Google Colab thông qua notebook:

`notebooks/day09_train_compare.ipynb`

Mục tiêu của thực nghiệm:

- Huấn luyện mô hình trên dữ liệu raw.
- Huấn luyện mô hình trên dữ liệu clean.
- So sánh kết quả giữa hai phiên bản dữ liệu.
- Đánh giá ảnh hưởng của quá trình QC đến chất lượng mô hình.

Do chưa có kết quả thực nghiệm nên chưa đưa ra kết luận rằng dataset clean cho kết quả huấn luyện tốt hơn dataset raw.

Phần train được chấm riêng 15 điểm theo thông báo của công cụ kiểm tra submission.

---

## 8. Quyết định cuối cùng

Kết quả lần chạy Pipeline:

**HOLD – Chưa phát hành dataset chính thức.**

Nguyên nhân:

- Không còn lỗi bắt buộc.
- Còn 34 ảnh có cảnh báo.
- Tỉ lệ cảnh báo 17.62%, vượt ngưỡng 10%.

Hướng xử lý tiếp theo:

1. Kiểm tra thủ công các ảnh còn cảnh báo, ưu tiên `POSSIBLE_MISSING`, `POSSIBLE_WRONG_CLASS` và `POSSIBLE_FALSE_POS`.
2. Xác minh các cảnh báo `POSSIBLE_LOOSE_BOX`, `BOX_TINY` và `BOX_HUGE` bằng ảnh gốc.
3. Xác định các file `EMPTY_LABEL` là ảnh nền hợp lệ hay ảnh thiếu nhãn.
4. Cập nhật nhãn nếu phát hiện lỗi thực tế.
5. Chạy lại Pipeline và đánh giá kết quả Gate.

Không tự ý hạ ngưỡng Gate chỉ để chuyển trạng thái HOLD thành RELEASE. Mọi quyết định phát hành cần dựa trên chất lượng dữ liệu đã được xác minh.

---

## 9. Ghi chú sử dụng trợ lý AI

Trợ lý AI được sử dụng để hỗ trợ:

- Giải thích cấu trúc và luồng hoạt động của AutoQC Pipeline.
- Hướng dẫn triển khai và kiểm tra các module Python theo phương pháp TDD.
- Phân tích kết quả pytest.
- Giải thích các chỉ số Precision, Recall và F1-score trong quá trình Calibration.
- Hướng dẫn chạy Pipeline và đọc các báo cáo QC.
- Hỗ trợ phân tích kết quả Gate và hoàn thiện báo cáo.

Việc kiểm tra kết quả được thực hiện bằng cách chạy trực tiếp các lệnh kiểm thử và Pipeline trên môi trường local, không chỉ dựa vào nội dung do AI đề xuất.

Các kết quả được sử dụng trong báo cáo được đối chiếu với file đầu ra thực tế trong thư mục `submission/reports/`.

---

## 10. Tổng kết

Qua bài thực hành Day 09, đã hoàn thành các nội dung cốt lõi:

- Triển khai và kiểm tra các module QC.
- Chạy 79 bài kiểm thử và đạt 79/79 PASS.
- Thực hiện Calibration cho hai ngưỡng quan trọng.
- Chạy toàn bộ Pipeline trên dữ liệu đầu vào.
- Thực hiện Autofix và mô phỏng Human Review.
- Kiểm tra quyết định Gate.
- Xuất dataset bản nháp `clean_v1`.
- Chạy kiểm tra submission với kết quả 0 lỗi.

Kết quả HOLD cho thấy Pipeline đã phát hiện được các vấn đề còn tồn tại và ngăn dataset được phát hành khi chưa đáp ứng ngưỡng chất lượng.

Phần huấn luyện và so sánh mô hình trên Google Colab vẫn là công việc tiếp theo cần thực hiện để hoàn thiện phần chấm điểm train riêng.