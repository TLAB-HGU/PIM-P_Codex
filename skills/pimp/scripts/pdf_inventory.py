#!/usr/bin/env python3
"""
pdf_inventory.py — 논문 PDF를 리뷰 작업용으로 펼친다.

usage: python3 pdf_inventory.py paper.pdf OUTDIR [--dpi 110] [--ocr auto|on|off] [--ocr-lang eng+kor]

OUTDIR/
  full.txt              페이지 구분자(===== PAGE N =====)가 들어간 전체 텍스트
  text/page_NNN.txt     페이지별 텍스트
  pages/page-NNN.png    페이지 이미지 (Figure·표·수식 확인용)
  inventory.json        메타데이터 + Figure/Table 캡션 목록과 추천 크롭 영역

OCR is optional (off by default), uses an installed Tesseract, and never changes the
source PDF or evidence page images. OCR text and column reading order require visual
verification, especially for equations and tables. Detection is per-page so a scan
inside an otherwise text-based paper is not missed.

추천 크롭 영역(suggested_bbox)은 휴리스틱이다. 반드시 페이지 이미지를 보고 확인한 뒤
crop_figure.py로 잘라낼 것. 좌표 단위는 PDF point (x0, top, x1, bottom), 원점은 좌상단.
"""
import argparse
import csv
import io
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import sys

import pdfplumber

CAPTION_RE = re.compile(r"^\s*(Figure|Fig\.?|Table|그림|표)\s*([A-Z]?\d+)\s*(?:[:.|]|(?=\s))", re.UNICODE | re.IGNORECASE)


def group_lines(words, tol=3):
    """단어들을 줄 단위로 묶는다."""
    lines = []
    for w in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        if lines and abs(lines[-1]["top"] - w["top"]) <= tol:
            L = lines[-1]
            L["words"].append(w)
            L["x0"] = min(L["x0"], w["x0"]); L["x1"] = max(L["x1"], w["x1"])
            L["bottom"] = max(L["bottom"], w["bottom"])
        else:
            lines.append({"top": w["top"], "bottom": w["bottom"], "x0": w["x0"], "x1": w["x1"], "words": [w]})
    for L in lines:
        L["words"].sort(key=lambda w: w["x0"])
        L["text"] = " ".join(w["text"] for w in L["words"])
    return lines


def detect_column_split(words, page_w):
    """Look for a repeated wide central gutter, not merely short left text.

    This deliberately remains a heuristic: tables can resemble columns, so the
    output inventory labels inferred reading order and requires page review.
    """
    candidates = []
    for line in group_lines(words):
        row = line["words"]
        for left, right in zip(row, row[1:]):
            gap = right["x0"] - left["x1"]
            mid = (right["x0"] + left["x1"]) / 2
            if gap >= max(24, page_w * 0.045) and page_w * 0.35 <= mid <= page_w * 0.65:
                left_words = [w for w in row if w["x1"] <= left["x1"] + 1]
                right_words = [w for w in row if w["x0"] >= right["x0"] - 1]
                if len(left_words) >= 2 and len(right_words) >= 2:
                    candidates.append((left["x1"], right["x0"]))
    if len(candidates) < 3:
        return None
    # The shared gutter must exist across several rows; a single wide tab is insufficient.
    mid = statistics.median((a + b) / 2 for a, b in candidates)
    agreeing = [(a, b) for a, b in candidates if a <= mid <= b]
    if len(agreeing) < 3 or len(agreeing) < len(candidates) * 0.6:
        return None
    return mid


def reading_lines(words, page_w):
    """Split same-height left/right rows, then read columns between spanning rows."""
    raw = group_lines(words)
    split = detect_column_split(words, page_w)
    if split is None:
        for line in raw:
            line["column"] = "full"
            line["column_bounds"] = (0, page_w)
        return raw, None
    separated = []
    for line in raw:
        left = [w for w in line["words"] if w["x1"] <= split]
        right = [w for w in line["words"] if w["x0"] >= split]
        crossing = len(left) + len(right) != len(line["words"])
        tight = bool(left and right and min(w["x0"] for w in right) - max(w["x1"] for w in left) < 24)
        if crossing or tight:
            line.update({"column": "full", "column_bounds": (0, page_w)})
            separated.append(line)
        else:
            for name, subset, bounds in (("left", left, (0, split)), ("right", right, (split, page_w))):
                if subset:
                    part = group_lines(subset)[0]
                    part.update({"column": name, "column_bounds": bounds})
                    separated.append(part)
    ordered, band = [], []

    def flush_band():
        ordered.extend(sorted(band, key=lambda line: (line["column"] != "left", line["top"], line["x0"])))
        band.clear()

    for line in sorted(separated, key=lambda line: (line["top"], line["x0"])):
        if line["column"] == "full":
            flush_band()
            ordered.append(line)
        else:
            band.append(line)
    flush_band()
    return ordered, split


def column_range(line, page_w):
    """캡션이 속한 단(column) 범위 추정: 2단 논문이면 반쪽, 아니면 전체."""
    if "column_bounds" in line:
        return line["column_bounds"]
    mid = page_w / 2
    if line["x1"] <= mid + 10:
        return 0, mid
    if line["x0"] >= mid - 10:
        return mid, page_w
    return 0, page_w


def graphic_boxes(page):
    boxes = []
    for obj in list(page.images) + list(page.rects) + list(page.curves) + list(page.lines):
        x0, top, x1, bottom = obj["x0"], obj["top"], obj["x1"], obj["bottom"]
        if (x1 - x0) > page.width * 0.95 and (bottom - top) > page.height * 0.95:
            continue  # 페이지 전체 배경
        boxes.append((x0, top, x1, bottom))
    return boxes


def suggest_bbox(page, cap_line, kind, lines):
    """Figure: 캡션 위쪽 그래픽 요소의 합집합 / Table: 캡션 아래쪽(없으면 위쪽).
    먼저 캡션이 속한 단(column)에서 찾고, 없으면 페이지 전체 폭에서 다시 찾는다."""
    col = column_range(cap_line, page.width)
    ranges = [col] if col == (0, page.width) else [col, (0, page.width)]
    for cx0, cx1 in ranges:
        u = _suggest_in_range(page, cap_line, kind, lines, cx0, cx1)
        if u is not None:
            pad = 6
            b = [max(0, u[0] - pad), max(0, u[1] - pad), min(page.width, u[2] + pad), min(page.height, u[3] + pad)]
            # 패딩이 캡션을 침범하지 않도록
            if u[3] <= cap_line["top"]:
                b[3] = min(b[3], cap_line["top"] - 4)
            if u[1] >= cap_line["bottom"]:
                b[1] = max(b[1], cap_line["bottom"] + 4)
            return [round(v, 1) for v in b]
    return None


def _union(bs):
    if not bs:
        return None
    return [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)]


def _cluster(bs, start, direction, first_gap=90, gap_max=40):
    """캡션에서 시작해 연속으로 이어지는 요소만 모은다 (첫 요소는 first_gap, 이후는 gap_max 이내)."""
    bs = sorted(bs, key=lambda b: b[3] if direction < 0 else b[1], reverse=direction < 0)
    out, edge = [], start
    for b in bs:
        gap = (edge - b[3]) if direction < 0 else (b[1] - edge)
        if gap > (first_gap if not out else gap_max):
            break
        out.append(b)
        edge = min(edge, b[1]) if direction < 0 else max(edge, b[3])
    return out


def _grow(u, allboxes, touch=3):
    """맞닿아 이어진 요소(표의 옆 칸 등)까지 영역을 넓힌다."""
    if u is None:
        return None
    changed = True
    while changed:
        changed = False
        for b in allboxes:
            vert = b[1] < u[3] and b[3] > u[1]
            hgap = max(b[0] - u[2], u[0] - b[2], 0)
            inside = b[0] >= u[0] and b[2] <= u[2] and b[1] >= u[1] and b[3] <= u[3]
            if vert and hgap <= touch and not inside:
                u = [min(u[0], b[0]), min(u[1], b[1]), max(u[2], b[2]), max(u[3], b[3])]
                changed = True
    return u


def _grow_text(u, lines, cap_line, near=12):
    """그림에 붙은 글자(축 눈금·축 제목·범례)를 포함하도록 넓힌다. 캡션 줄은 제외."""
    if u is None:
        return None
    for _ in range(3):
        grown = False
        for L in lines:
            for w in L["words"]:
                if abs(w["top"] - cap_line["top"]) < 1:
                    continue
                if w["x0"] >= u[0] and w["x1"] <= u[2] and w["top"] >= u[1] and w["bottom"] <= u[3]:
                    continue
                vgap = max(w["top"] - u[3], u[1] - w["bottom"], 0)
                hgap = max(w["x0"] - u[2], u[0] - w["x1"], 0)
                # 그림 가장자리에 붙은 짧은 단어만 (본문 줄을 끌어들이지 않도록)
                if vgap <= near and hgap <= near and (w["x1"] - w["x0"]) < 80:
                    between_caption = (w["top"] < cap_line["top"] <= u[1]) or (u[3] <= cap_line["top"] < w["top"])
                    if between_caption:
                        continue
                    u = [min(u[0], w["x0"]), min(u[1], w["top"]), max(u[2], w["x1"]), max(u[3], w["bottom"])]
                    grown = True
        if not grown:
            break
    return u


def _suggest_in_range(page, cap_line, kind, lines, cx0, cx1):
    allb = graphic_boxes(page)
    u = _suggest_core(page, cap_line, kind, lines, cx0, cx1)
    return _grow_text(_grow(u, allb), lines, cap_line)


def _suggest_core(page, cap_line, kind, lines, cx0, cx1):
    # 단과 겹치는 요소를 모두 후보로 (단 폭을 넘는 전체폭 Figure/표도 통째로 잡히도록)
    boxes = [b for b in graphic_boxes(page) if b[0] < cx1 - 5 and b[2] > cx0 + 5]
    above = [b for b in boxes if b[3] <= cap_line["top"] + 2]
    below = [b for b in boxes if b[1] >= cap_line["bottom"] - 2]
    if kind == "figure":
        return _union(_cluster(above, cap_line["top"], -1)) or _union(_cluster(below, cap_line["bottom"], +1))
    u = _union(_cluster(below, cap_line["bottom"], +1)) or _union(_cluster(above, cap_line["top"], -1))
    if u is not None:
        return u
    # 선 없는 표(booktabs 등): 캡션 아래 숫자가 많은 줄들
    rows = []
    for L in lines:
        if L["top"] > cap_line["bottom"] and L["x0"] >= cx0 - 5 and L["x1"] <= cx1 + 5:
            if rows and L["top"] - rows[-1]["bottom"] > 25:
                break
            if len(re.findall(r"\d", L["text"])) >= 3 or rows:
                rows.append(L)
    if rows:
        return [min(r["x0"] for r in rows), rows[0]["top"], max(r["x1"] for r in rows), rows[-1]["bottom"]]
    return None


def find_captions(page, lines, page_no, text_source="native"):
    captions = []
    for idx, line in enumerate(lines):
        match = CAPTION_RE.match(line["text"])
        if not match:
            continue
        kind = "table" if match.group(1).lower().startswith(("tab", "표")) else "figure"
        parts, prev = [line], line
        line_h = max(4.0, line["bottom"] - line["top"])
        for nxt in lines[idx + 1: idx + 4]:
            gap = nxt["top"] - prev["bottom"]
            same_column = nxt.get("column") == line.get("column")
            # A negative jump means reading moved to another column or region.
            if not same_column or gap < -2 or gap > 0.8 * line_h or CAPTION_RE.match(nxt["text"]):
                break
            parts.append(nxt)
            prev = nxt
        captions.append({
            "id": f"{'Table' if kind == 'table' else 'Fig'} {match.group(2)}",
            "kind": kind, "page": page_no, "text_source": text_source,
            "caption": " ".join(part["text"] for part in parts)[:300],
            "caption_bbox": [round(min(part["x0"] for part in parts), 1), round(line["top"], 1),
                             round(max(part["x1"] for part in parts), 1), round(prev["bottom"], 1)],
            "suggested_bbox": suggest_bbox(page, line, kind, lines) if text_source == "native" else None,
            "detection": "heuristic", "review_required": True,
        })
    return captions


def image_coverage(page):
    area = sum(max(0, min(page.width, obj["x1"]) - max(0, obj["x0"])) *
               max(0, min(page.height, obj["bottom"]) - max(0, obj["top"])) for obj in page.images)
    return min(1.0, area / (page.width * page.height))


def tesseract_check(lang):
    requested = os.environ.get("PIMP_TESSERACT", "tesseract")
    executable = shutil.which(requested)
    if not executable:
        raise RuntimeError(f"OCR requires an executable Tesseract (selected: {requested!r}). "
                           "Install tesseract and the requested language data or set PIMP_TESSERACT "
                           "to its executable path, then rerun with --ocr auto/on; "
                           "use --ocr off only for a manual review")
    try:
        proc = subprocess.run([executable, "--list-langs"], capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError(f"cannot inspect Tesseract languages: {e}") from e
    if proc.returncode:
        raise RuntimeError(f"Tesseract --list-langs failed: {proc.stderr.strip() or proc.stdout.strip()}")
    available = set(proc.stdout.splitlines()[1:])
    missing = set(lang.split("+")) - available
    if missing:
        raise RuntimeError(f"Tesseract language data missing: {', '.join(sorted(missing))}. "
                           f"Installed languages: {', '.join(sorted(available))}. Install the language data "
                           "or select an installed language with --ocr-lang")
    return executable


def ocr_words(image_path, page, executable, lang, timeout=60):
    """Keep OCR text as unverified evidence; map TSV pixels to original PDF points."""
    from PIL import Image
    proc = subprocess.run([executable, image_path, "stdout", "-l", lang, "tsv"],
                          capture_output=True, text=True, timeout=timeout, check=False)
    if proc.returncode:
        raise RuntimeError(f"Tesseract exited {proc.returncode}: {proc.stderr.strip()}")
    with Image.open(image_path) as image:
        sx, sy = page.width / image.width, page.height / image.height
    words, confidence = [], []
    for row in csv.DictReader(io.StringIO(proc.stdout), delimiter="\t"):
        if row.get("level") != "5" or not row.get("text", "").strip():
            continue
        try:
            conf = float(row["conf"])
            left, top, width, height = (float(row[key]) for key in ("left", "top", "width", "height"))
        except (KeyError, ValueError) as e:
            raise RuntimeError("Tesseract returned malformed TSV word coordinates") from e
        if conf < 0:
            continue
        words.append({"text": row["text"].strip(), "x0": left * sx, "x1": (left + width) * sx,
                      "top": top * sy, "bottom": (top + height) * sy})
        confidence.append(conf)
    if not words:
        raise RuntimeError("Tesseract found no words. Inspect the evidence image; try higher --dpi or "
                           "the correct --ocr-lang, and manually transcribe inaccessible equations")
    return words, round(statistics.mean(confidence), 1)


def build_inventory(pdf_path, outdir, dpi=110, ocr="off", ocr_lang="eng", ocr_timeout=60):
    if ocr not in ("auto", "on", "off"):
        raise ValueError("ocr must be auto, on, or off")
    if not math.isfinite(dpi) or dpi <= 0 or ocr_timeout <= 0:
        raise ValueError("dpi and ocr_timeout must be positive")
    os.makedirs(os.path.join(outdir, "text"), exist_ok=True)
    os.makedirs(os.path.join(outdir, "pages"), exist_ok=True)
    inv = {"schema_version": 2, "pdf": os.path.abspath(pdf_path), "pages": [], "captions": [],
           "ocr_mode": ocr, "ocr_lang": ocr_lang, "warnings": [], "errors": [],
           "bbox_units": "PDF points; [x0, top, x1, bottom]; origin=top-left",
           "caption_detection": "advisory heuristic; verify every caption and crop visually"}
    full, total_chars, executable, ocr_setup_error = [], 0, None, None
    with pdfplumber.open(pdf_path) as pdf:
        inv["num_pages"] = len(pdf.pages)
        inv["metadata"] = {k: str(v) for k, v in (pdf.metadata or {}).items()
                           if k in ("Title", "Author", "Subject", "CreationDate")}
        for page_no, page in enumerate(pdf.pages, 1):
            native_words = page.extract_words(keep_blank_chars=False, use_text_flow=False)
            native_lines, split = reading_lines(native_words, page.width)
            native_txt = "\n".join(line["text"] for line in native_lines)
            native_chars = len(native_txt.strip())
            coverage = image_coverage(page)
            likely_scanned = native_chars < 40 and coverage >= 0.5
            png = os.path.join(outdir, "pages", f"page-{page_no:03d}.png")
            # Save the original page rendering before OCR; never overwrite it with OCR overlays.
            page.to_image(resolution=dpi).save(png)
            entry = {"page": page_no, "width_pt": round(page.width, 1), "height_pt": round(page.height, 1),
                     "image": png, "native_chars": native_chars, "likely_scanned": likely_scanned,
                     "text_sparse": native_chars < 40, "image_coverage": round(coverage, 3),
                     "ocr": {"status": "not_requested", "lang": ocr_lang}}
            txt, lines, source = native_txt, native_lines, "native" if native_chars else "none"
            should_ocr = ocr == "on" or (ocr == "auto" and likely_scanned)
            if should_ocr:
                if executable is None and ocr_setup_error is None:
                    try:
                        executable = tesseract_check(ocr_lang)
                    except RuntimeError as e:
                        ocr_setup_error = str(e)
                try:
                    if ocr_setup_error:
                        raise RuntimeError(ocr_setup_error)
                    words, confidence = ocr_words(png, page, executable, ocr_lang, timeout=ocr_timeout)
                    lines, split = reading_lines(words, page.width)
                    txt, source = "\n".join(line["text"] for line in lines), "ocr"
                    entry["ocr"].update({"status": "success", "mean_confidence": confidence,
                                           "review_required": True})
                    with open(os.path.join(outdir, "text", f"page_{page_no:03d}.native.txt"), "w", encoding="utf-8") as f:
                        f.write(native_txt)
                    inv["warnings"].append(f"p.{page_no}: OCR text is unverified; check symbols/numbers against the original page image")
                except (OSError, RuntimeError, subprocess.TimeoutExpired) as e:
                    message = f"p.{page_no}: OCR failed: {e}"
                    entry["ocr"].update({"status": "failed", "error": str(e)})
                    inv["errors"].append(message)
            elif likely_scanned:
                inv["warnings"].append(f"p.{page_no}: likely scanned; rerun with --ocr auto --ocr-lang {ocr_lang} or review/transcribe the page manually")
            entry.update({"chars": len(txt.strip()), "text_source": source,
                          "reading_order": "two-column heuristic" if split is not None else "top-to-bottom",
                          "column_split_pt": round(split, 1) if split is not None else None})
            total_chars += len(txt.strip())
            with open(os.path.join(outdir, "text", f"page_{page_no:03d}.txt"), "w", encoding="utf-8") as f:
                f.write(txt)
            full.append(f"\n===== PAGE {page_no} =====\n{txt}")
            inv["pages"].append(entry)
            inv["captions"].extend(find_captions(page, lines, page_no, source))
    # Preserve duplicate IDs on different pages: main-paper and appendix labels can collide.
    seen, dedup = {}, []
    for caption in inv["captions"]:
        key = (caption["id"], caption["page"])
        if key not in seen:
            seen[key] = len(dedup)
            dedup.append(caption)
        elif dedup[seen[key]]["suggested_bbox"] is None and caption["suggested_bbox"] is not None:
            dedup[seen[key]] = caption
    inv["captions"] = dedup
    inv["scanned_pages"] = [entry["page"] for entry in inv["pages"] if entry["likely_scanned"]]
    inv["likely_scanned"] = bool(inv["scanned_pages"])
    inv["text_chars"] = total_chars
    inv["complete"] = not inv["errors"]
    with open(os.path.join(outdir, "full.txt"), "w", encoding="utf-8") as f:
        f.write("".join(full))
    with open(os.path.join(outdir, "inventory.json"), "w", encoding="utf-8") as f:
        json.dump(inv, f, ensure_ascii=False, indent=2)
    return inv


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("outdir")
    ap.add_argument("--dpi", type=int, default=110)
    ap.add_argument("--ocr", choices=("auto", "on", "off"), default="off")
    ap.add_argument("--ocr-lang", default="eng", help="installed Tesseract language(s), for example eng+kor")
    ap.add_argument("--ocr-timeout", type=int, default=60, help="maximum OCR seconds per page")
    a = ap.parse_args(argv)
    try:
        inv = build_inventory(a.pdf, a.outdir, a.dpi, a.ocr, a.ocr_lang, a.ocr_timeout)
    except (OSError, ValueError) as e:
        ap.error(str(e))
    print(f"pages: {inv['num_pages']}  text chars: {inv['text_chars']}  scanned pages: {inv['scanned_pages']}")
    print(f"captions found: {len(inv['captions'])}; advisory candidates require visual review")
    for caption in inv["captions"]:
        print(f"  {caption['id']:<10} p.{caption['page']:<3} bbox={caption['suggested_bbox']}  {caption['caption'][:70]}")
    for message in inv["warnings"]:
        print(f"WARNING: {message}", file=sys.stderr)
    for message in inv["errors"]:
        print(f"ERROR: {message}", file=sys.stderr)
    print(f"-> {a.outdir}/inventory.json, full.txt, text/, pages/")
    return 2 if inv["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
