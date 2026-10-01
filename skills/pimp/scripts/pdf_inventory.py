#!/usr/bin/env python3
"""
pdf_inventory.py — 논문 PDF를 리뷰 작업용으로 펼친다.

usage: python3 pdf_inventory.py paper.pdf OUTDIR [--dpi 110]

OUTDIR/
  full.txt              페이지 구분자(===== PAGE N =====)가 들어간 전체 텍스트
  text/page_NNN.txt     페이지별 텍스트
  pages/page-NNN.png    페이지 이미지 (Figure·표·수식 확인용)
  inventory.json        메타데이터 + Figure/Table 캡션 목록과 추천 크롭 영역

추천 크롭 영역(suggested_bbox)은 휴리스틱이다. 반드시 페이지 이미지를 보고 확인한 뒤
crop_figure.py로 잘라낼 것. 좌표 단위는 PDF point (x0, top, x1, bottom), 원점은 좌상단.
"""
import argparse
import json
import os
import re
import sys

import pdfplumber

CAPTION_RE = re.compile(r"^\s*(Figure|Fig\.|FIGURE|Table|TABLE|그림|표)\s*([A-Z]?\d+)\s*[:.|]", re.UNICODE)


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


def column_range(line, page_w):
    """캡션이 속한 단(column) 범위 추정: 2단 논문이면 반쪽, 아니면 전체."""
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("outdir")
    ap.add_argument("--dpi", type=int, default=110)
    a = ap.parse_args()

    os.makedirs(os.path.join(a.outdir, "text"), exist_ok=True)
    os.makedirs(os.path.join(a.outdir, "pages"), exist_ok=True)

    inv = {"pdf": os.path.abspath(a.pdf), "pages": [], "captions": []}
    full = []
    total_chars = 0
    with pdfplumber.open(a.pdf) as pdf:
        inv["num_pages"] = len(pdf.pages)
        inv["metadata"] = {k: str(v) for k, v in (pdf.metadata or {}).items() if k in ("Title", "Author", "Subject", "CreationDate")}
        for i, page in enumerate(pdf.pages, start=1):
            txt = page.extract_text(layout=False) or ""
            total_chars += len(txt.strip())
            with open(os.path.join(a.outdir, "text", f"page_{i:03d}.txt"), "w") as f:
                f.write(txt)
            full.append(f"\n===== PAGE {i} =====\n{txt}")
            png = os.path.join(a.outdir, "pages", f"page-{i:03d}.png")
            page.to_image(resolution=a.dpi).save(png)
            inv["pages"].append({"page": i, "width_pt": round(page.width, 1), "height_pt": round(page.height, 1),
                                 "chars": len(txt.strip()), "image": png})

            words = page.extract_words(keep_blank_chars=False, use_text_flow=False)
            lines = group_lines(words)
            for idx, L in enumerate(lines):
                m = CAPTION_RE.match(L["text"])
                if not m:
                    continue
                # 본문 속 참조("as shown in Figure 3.")를 거르기: 캡션은 줄 맨 앞에서 시작
                kind = "table" if m.group(1).lower().startswith(("tab", "표")) else "figure"
                cap, prev = L["text"], L
                line_h = max(4.0, L["bottom"] - L["top"])
                for nxt in lines[idx + 1: idx + 4]:  # 캡션 이어지는 줄 최대 3줄 (촘촘히 붙은 줄만)
                    if nxt["top"] - prev["bottom"] > 0.8 * line_h or CAPTION_RE.match(nxt["text"]):
                        break
                    cap += " " + nxt["text"]
                    prev = nxt
                inv["captions"].append({
                    "id": f"{'Table' if kind == 'table' else 'Fig'} {m.group(2)}",
                    "kind": kind, "page": i,
                    "caption": cap[:300],
                    "caption_bbox": [round(L["x0"], 1), round(L["top"], 1), round(L["x1"], 1), round(L["bottom"], 1)],
                    "suggested_bbox": suggest_bbox(page, L, kind, lines),
                })

    # 같은 ID가 여러 번 잡히면(본문 참조 오탐) 추천 영역이 있는 첫 번째를 우선
    seen, dedup = {}, []
    for c in inv["captions"]:
        k = c["id"]
        if k not in seen:
            seen[k] = len(dedup); dedup.append(c)
        elif dedup[seen[k]]["suggested_bbox"] is None and c["suggested_bbox"] is not None:
            dedup[seen[k]] = c
    inv["captions"] = dedup
    inv["likely_scanned"] = total_chars < 200 * max(1, inv["num_pages"]) * 0.2

    with open(os.path.join(a.outdir, "full.txt"), "w") as f:
        f.write("".join(full))
    with open(os.path.join(a.outdir, "inventory.json"), "w") as f:
        json.dump(inv, f, ensure_ascii=False, indent=2)

    print(f"pages: {inv['num_pages']}  text chars: {total_chars}  scanned?: {inv['likely_scanned']}")
    print(f"captions found: {len(inv['captions'])}")
    for c in inv["captions"]:
        print(f"  {c['id']:<10} p.{c['page']:<3} bbox={c['suggested_bbox']}  {c['caption'][:70]}")
    print(f"-> {a.outdir}/inventory.json, full.txt, text/, pages/")


if __name__ == "__main__":
    sys.exit(main())
