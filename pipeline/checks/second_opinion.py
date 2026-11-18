"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa (slide). Các lỗi như thiếu nhãn / gán nhầm lớp hợp lệ / box lỏng
KHÔNG bắt được bằng quy tắc cú pháp. Ta nhờ một model mạnh hơn "nhìn lại" và CHỈ CẢNH BÁO (model cũng có thể sai):
những ảnh bị cờ sẽ vào hàng đợi cho NGƯỜI duyệt.

`preds[stem]` = list `[id_lớp, conf, cx, cy, w, h]` của model (lấy qua `get_preds(ds, cfg, "checker")` nếu preds=None).
`L = ds.valid_boxes(stem)` = list `(id_lớp, cx, cy, w, h)` của nhãn (đã bỏ dòng hỏng).
Ngưỡng ở `cfg["second_opinion"]`: conf, min_area_px, fp_conf, iou_missing, iou_match, iou_loose.

Thuật toán gợi ý, với từng ảnh (bỏ qua ảnh không có trong preds hoặc không có file nhãn):
  P = dự đoán có conf >= conf  VÀ diện tích px (w*W * h*H) >= min_area_px
  Với mỗi dự đoán r trong P: lấy các nhãn có IoU(r, nhãn) >= iou_missing  (cands)
   - không có cands                            -> POSSIBLE_MISSING     (model thấy vật mà nhãn không có box)
   - có cands cùng lớp, tốt nhất IoU < iou_loose -> POSSIBLE_LOOSE_BOX  (đúng vật, box lỏng/lệch)
   - không có cands cùng lớp, nhưng cands tốt nhất IoU >= iou_match (khác lớp) -> POSSIBLE_WRONG_CLASS
  Với mỗi dòng nhãn hợp lệ: nếu IoU với MỌI dự đoán (conf >= fp_conf, không lọc diện tích) đều < iou_missing
                                             -> POSSIBLE_FALSE_POS  (box nhãn không khớp vật nào model thấy; Issue.line = số dòng)

Chi tiết các ca biên (test kiểm đúng các ca này)
- `cands` gồm nhãn MỌI lớp có IoU >= iou_missing; "tốt nhất cùng lớp" = cands cùng lớp có IoU lớn nhất; "tốt nhất khác lớp" tương tự với cands khác lớp.
- Thứ tự quyết định cho mỗi dự đoán: (1) cands rỗng -> MISSING. (2) có cands cùng lớp: IoU tốt nhất < iou_loose -> LOOSE_BOX, ngược lại KHÔNG cờ
  (nhãn đúng lớp đã phủ vật này, kể cả khi còn nhãn khác lớp chồng lên). (3) không có cands cùng lớp: nếu IoU tốt nhất khác lớp >= iou_match -> WRONG_CLASS;
  nếu chỉ có khác lớp với IoU trong [iou_missing, iou_match) -> không cờ gì (mơ hồ: để cho FALSE_POS / lần duyệt khác).
- Một dự đoán sinh tối đa MỘT issue (MISSING / LOOSE_BOX / WRONG_CLASS); một ảnh có thể có nhiều issue.
- Thứ tự issue: theo `ds.image_files()` rồi theo thứ tự dự đoán trong `preds[stem]`, cuối cùng là các FALSE_POS theo số dòng; `Issue.image` = stem, `Issue.line` chỉ đặt cho FALSE_POS.

Lưu ý số dòng: dùng `ds.read_label_lines(stem)` (giữ số dòng gốc, kể cả dòng hỏng/trống) để lấy `Issue.line`; `valid_boxes` KHÔNG giữ số dòng.

Tất cả severity WARN; `Issue.extra` nên có {"conf": ...} hoặc {"iou": ...} (hàng đợi duyệt dùng conf để xếp ưu tiên).

Gợi ý
- `iou_xywh` có sẵn. Dòng nhãn hỏng không được làm script chết (dùng `ds.valid_boxes` và `parse_yolo_line` trong try).
- Kết quả phụ thuộc mạnh vào ngưỡng: calibrate chúng ở Bước 3 thay vì đoán.
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line
from ..model_cache import get_preds


def run(ds, cfg, preds=None):
    if preds is None:
        preds = get_preds(ds, cfg, "checker")

    conf_thresh = cfg["second_opinion"]["conf"]
    min_area_px = cfg["second_opinion"]["min_area_px"]
    fp_conf = cfg["second_opinion"]["fp_conf"]
    iou_missing = cfg["second_opinion"]["iou_missing"]
    iou_match = cfg["second_opinion"]["iou_match"]
    iou_loose = cfg["second_opinion"]["iou_loose"]

    issues = []

    for img_p in ds.image_files():
        stem = img_p.stem
        if preds is None or stem not in preds:
            continue
        if not ds.label_path(stem).exists():
            continue

        img_size = ds.image_size(stem)
        if img_size is None:
            continue
        W, H = img_size

        stem_preds = preds.get(stem, [])
        valid_labels = ds.valid_boxes(stem)

        # 1. Dự đoán của model -> POSSIBLE_MISSING / POSSIBLE_LOOSE_BOX / POSSIBLE_WRONG_CLASS
        P = [
            r for r in stem_preds
            if r[1] >= conf_thresh and (r[4] * W * r[5] * H) >= min_area_px
        ]

        for r in P:
            r_cls = int(r[0])
            r_conf = float(r[1])
            r_box = (float(r[2]), float(r[3]), float(r[4]), float(r[5]))

            cands = []
            for l in valid_labels:
                l_cls = int(l[0])
                l_box = (float(l[1]), float(l[2]), float(l[3]), float(l[4]))
                iou = iou_xywh(r_box, l_box)
                if iou >= iou_missing:
                    cands.append((l_cls, iou))

            if not cands:
                issues.append(Issue(
                    "second_opinion",
                    WARN,
                    "POSSIBLE_MISSING",
                    stem,
                    f"model phát hiện lớp {r_cls} (conf={r_conf:.2f}) nhưng nhãn không có box",
                    line=None,
                    extra={"conf": r_conf},
                ))
            else:
                same_cands = [c for c in cands if c[0] == r_cls]
                if same_cands:
                    best_same_iou = max(c[1] for c in same_cands)
                    if best_same_iou < iou_loose:
                        issues.append(Issue(
                            "second_opinion",
                            WARN,
                            "POSSIBLE_LOOSE_BOX",
                            stem,
                            f"nhãn cùng lớp {r_cls} nhưng box lỏng/lệch (IoU={best_same_iou:.2f})",
                            line=None,
                            extra={"conf": r_conf, "iou": float(best_same_iou)},
                        ))
                else:
                    best_diff_iou = max(c[1] for c in cands)
                    if best_diff_iou >= iou_match:
                        issues.append(Issue(
                            "second_opinion",
                            WARN,
                            "POSSIBLE_WRONG_CLASS",
                            stem,
                            f"model đoán lớp {r_cls} nhưng nhãn gán lớp khác (IoU={best_diff_iou:.2f})",
                            line=None,
                            extra={"conf": r_conf, "iou": float(best_diff_iou)},
                        ))

        # 2. Nhãn hợp lệ -> POSSIBLE_FALSE_POS
        fp_preds = [r for r in stem_preds if r[1] >= fp_conf]
        raw_lines = ds.read_label_lines(stem) or []
        n_classes = len(ds.classes)

        for line_no, ln in raw_lines:
            try:
                c, cx, cy, w, h = parse_yolo_line(ln)
            except ValueError:
                continue
            if c < 0 or c >= n_classes:
                continue

            l_box = (cx, cy, w, h)
            max_iou = 0.0
            if fp_preds:
                max_iou = max(iou_xywh(l_box, (p[2], p[3], p[4], p[5])) for p in fp_preds)

            if not fp_preds or max_iou < iou_missing:
                issues.append(Issue(
                    "second_opinion",
                    WARN,
                    "POSSIBLE_FALSE_POS",
                    stem,
                    f"box nhãn ở dòng {line_no} không khớp vật nào model thấy",
                    line=line_no,
                    extra={"iou": float(max_iou)},
                ))

    return issues
