"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line


def run(ds, cfg):
    issues = []
    tol = cfg["label_format"]["overflow_tol"]
    dup_iou = cfg["label_format"]["dup_box_iou"]
    min_px = cfg["label_format"]["min_box_px"]
    max_frac = cfg["label_format"]["max_box_frac"]
    n_classes = len(ds.classes)

    for lp in ds.label_files():
        stem = lp.stem
        lines = ds.read_label_lines(stem)
        if lines is None:
            continue

        seen_boxes = []
        img_size = ds.image_size(stem)

        for line_no, ln in lines:
            try:
                c, cx, cy, w, h = parse_yolo_line(ln)
            except ValueError:
                issues.append(Issue("label_format", ERROR, "BAD_FORMAT", stem, f"dòng nhãn sai định dạng: {ln}", line=line_no))
                continue

            if c < 0 or c >= n_classes:
                issues.append(Issue("label_format", ERROR, "BAD_CLASS_ID", stem, f"id lớp {c} ngoài dải 0..{n_classes - 1}", line=line_no))
                continue

            if w <= 0 or h <= 0:
                issues.append(Issue("label_format", ERROR, "BOX_ZERO", stem, f"kích thước box <= 0 (w={w}, h={h})", line=line_no))
                continue

            x1 = cx - w / 2
            y1 = cy - h / 2
            x2 = cx + w / 2
            y2 = cy + h / 2
            overflow = max(0.0, -x1, -y1, x2 - 1.0, y2 - 1.0)
            if overflow > tol:
                issues.append(Issue("label_format", ERROR, "BOX_OUT_OF_IMAGE", stem, f"box tràn ra ngoài ảnh: {overflow:.4f}", line=line_no, extra={"overflow": float(overflow)}))

            is_dup = any(pc == c and iou_xywh((cx, cy, w, h), (pcx, pcy, pw, ph)) > dup_iou for pc, pcx, pcy, pw, ph in seen_boxes)
            if is_dup:
                issues.append(Issue("label_format", ERROR, "DUP_BOX", stem, "box trùng lặp với dòng trước", line=line_no))

            seen_boxes.append((c, cx, cy, w, h))

            if img_size is not None:
                short_side = min(w * img_size[0], h * img_size[1])
                if short_side < min_px:
                    issues.append(Issue("label_format", WARN, "BOX_TINY", stem, f"cạnh ngắn của box < {min_px}px: {short_side:.1f}px", line=line_no, extra={"px": float(short_side)}))

            if w * h > max_frac:
                issues.append(Issue("label_format", WARN, "BOX_HUGE", stem, f"box chiếm quá nhiều diện tích: {w*h:.2f} > {max_frac}", line=line_no, extra={"frac": float(w * h)}))

    return issues
