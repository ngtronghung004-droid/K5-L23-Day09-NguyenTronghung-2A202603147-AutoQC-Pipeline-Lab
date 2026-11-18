"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
import time
from collections import defaultdict
from pathlib import Path

import yaml

from ..common import ERROR, parse_yolo_line

REMOVE_IMAGE_CODES = {"LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}
DROP_LINE_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}


def _safe_write_text(path: Path, text: str):
    for _ in range(5):
        try:
            path.write_text(text, encoding="utf-8")
            return
        except PermissionError:
            time.sleep(0.05)
    path.write_text(text, encoding="utf-8")


def fix(ds, issues, cfg):
    error_issues = [i for i in issues if i.severity == ERROR]
    if not error_issues:
        return []

    fixes = []
    removed_images = set()

    # 1. remove_image
    for iss in error_issues:
        if iss.code.startswith("DUP_IMAGE_") or iss.code in REMOVE_IMAGE_CODES:
            stem = iss.image
            if stem not in removed_images:
                removed_images.add(stem)
                im_path = ds.image_path(stem)
                if im_path and im_path.exists():
                    im_path.unlink()
                lbl_path = ds.label_path(stem)
                if lbl_path and lbl_path.exists():
                    lbl_path.unlink()
                ds._size_cache.pop(stem, None)
                fixes.append({
                    "image": stem,
                    "line": "",
                    "action": "remove_image",
                    "before": stem,
                    "after": "(đã xoá)",
                })

    # 2. rename_classes
    for iss in error_issues:
        if iss.code == "BAD_CLASS_NAME":
            if ds.yaml_path.exists():
                data = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
                before_str = str(data.get("names", ""))
                data["names"] = list(cfg["classes"])
                content = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
                _safe_write_text(ds.yaml_path, content)
                fixes.append({
                    "image": "data.yaml",
                    "line": "",
                    "action": "rename_classes",
                    "before": before_str,
                    "after": str(cfg["classes"]),
                })
            break

    # 3. needs_label
    for iss in error_issues:
        if iss.code == "MISSING_LABEL_FILE":
            stem = iss.image
            if stem not in removed_images:
                fixes.append({
                    "image": stem,
                    "line": "",
                    "action": "needs_label",
                    "before": "(không có file)",
                    "after": "chuyển người gán",
                })

    # 4. line-level fixes (drop_line, clip_box)
    line_issues_by_stem = defaultdict(list)
    for iss in error_issues:
        if iss.line is not None and (iss.code in DROP_LINE_CODES or iss.code == "BOX_OUT_OF_IMAGE"):
            line_issues_by_stem[iss.image].append(iss)

    for stem, stem_issues in line_issues_by_stem.items():
        if stem in removed_images:
            continue
        lbl_path = ds.label_path(stem)
        if not lbl_path.exists():
            continue

        raw_lines = lbl_path.read_text(encoding="utf-8", errors="replace").splitlines()
        n_lines = len(raw_lines)

        issues_by_line = defaultdict(list)
        for iss in stem_issues:
            issues_by_line[iss.line].append(iss)

        modified = False
        for line_no in range(1, n_lines + 1):
            if line_no not in issues_by_line:
                continue
            line_iss = issues_by_line[line_no]
            original_text = raw_lines[line_no - 1]
            codes = {i.code for i in line_iss}

            if any(c in DROP_LINE_CODES for c in codes):
                raw_lines[line_no - 1] = None
                modified = True
                fixes.append({
                    "image": stem,
                    "line": line_no,
                    "action": "drop_line",
                    "before": original_text,
                    "after": "(đã xoá)",
                })
            elif "BOX_OUT_OF_IMAGE" in codes:
                try:
                    parts = original_text.split()
                    c = int(float(parts[0]))
                    cx, cy, w, h = map(float, parts[1:5])
                    x1 = cx - w / 2
                    y1 = cy - h / 2
                    x2 = cx + w / 2
                    y2 = cy + h / 2
                    nx1 = max(0.0, min(1.0, x1))
                    ny1 = max(0.0, min(1.0, y1))
                    nx2 = max(0.0, min(1.0, x2))
                    ny2 = max(0.0, min(1.0, y2))
                    nw = nx2 - nx1
                    nh = ny2 - ny1
                    if nw <= 0.0 or nh <= 0.0:
                        raw_lines[line_no - 1] = None
                        modified = True
                        fixes.append({
                            "image": stem,
                            "line": line_no,
                            "action": "drop_line",
                            "before": original_text,
                            "after": "(đã xoá)",
                        })
                    else:
                        ncx = (nx1 + nx2) / 2
                        ncy = (ny1 + ny2) / 2
                        new_line_str = f"{c} {ncx:.6f} {ncy:.6f} {nw:.6f} {nh:.6f}"
                        raw_lines[line_no - 1] = new_line_str
                        modified = True
                        fixes.append({
                            "image": stem,
                            "line": line_no,
                            "action": "clip_box",
                            "before": original_text,
                            "after": new_line_str,
                        })
                except Exception:
                    raw_lines[line_no - 1] = None
                    modified = True
                    fixes.append({
                        "image": stem,
                        "line": line_no,
                        "action": "drop_line",
                        "before": original_text,
                        "after": "(đã xoá)",
                    })

        if modified:
            kept_lines = [l for l in raw_lines if l is not None]
            if kept_lines:
                _safe_write_text(lbl_path, "\n".join(kept_lines) + "\n")
            else:
                _safe_write_text(lbl_path, "")

    return fixes
