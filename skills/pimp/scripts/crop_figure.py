#!/usr/bin/env python3
"""
crop_figure.py — 논문 PDF 페이지의 일부 영역을 고해상도 PNG로 잘라낸다.

usage:
  # PDF point 좌표 (x0 top x1 bottom, 원점 좌상단) — inventory.json의 suggested_bbox 그대로
  python3 crop_figure.py paper.pdf --page 3 --bbox 50 80 560 330 -o assets/fig1.png

  # 페이지 비율 좌표 (0~1) — 페이지 이미지를 보고 눈으로 잡을 때 편함
  python3 crop_figure.py paper.pdf --page 3 --frac 0.08 0.10 0.92 0.42 -o assets/fig1.png

  # 여러 개를 한 번에: [{"page":3,"bbox":[...],"out":"assets/fig1.png"}, {"page":5,"frac":[...],"out":...}]
  python3 crop_figure.py paper.pdf --batch crops.json

잘라낸 뒤 반드시 결과 PNG를 열어 캡션·본문 글자가 섞이지 않았는지, 축 레이블이 잘리지 않았는지 확인할 것.
"""
import argparse
import json
import math
import os
import sys

import pdfplumber


def crop(pdf, page_no, out, bbox=None, frac=None, dpi=250, pad=0):
    """Render a validated crop. Coordinates are PDF points from the top left.

    Padding alone may be clipped to the page; invalid requested bounds are never
    silently clipped. Return the actual bounds for a provenance report.
    """
    if isinstance(page_no, bool) or not isinstance(page_no, int) or not 1 <= page_no <= len(pdf.pages):
        raise ValueError(f"page must be an integer from 1 to {len(pdf.pages)} (got {page_no!r})")
    if (bbox is None) == (frac is None):
        raise ValueError("supply exactly one of bbox or frac")
    if not isinstance(dpi, (int, float)) or not math.isfinite(dpi) or dpi <= 0:
        raise ValueError("dpi must be a positive number")
    if not isinstance(pad, (int, float)) or not math.isfinite(pad) or pad < 0:
        raise ValueError("pad must be a nonnegative number")
    if not isinstance(out, (str, os.PathLike)) or not str(out):
        raise ValueError("out must be a nonempty output path")
    page = pdf.pages[page_no - 1]
    W, H = page.width, page.height
    coords = frac if frac is not None else bbox
    if not isinstance(coords, (list, tuple)) or len(coords) != 4:
        raise ValueError("bbox/frac must contain four coordinates: x0, top, x1, bottom")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in coords):
        raise ValueError("bbox/frac coordinates must be finite numbers")
    if frac is not None:
        if any(v < 0 or v > 1 for v in frac):
            raise ValueError("frac coordinates must be between 0 and 1")
        bbox = [frac[0] * W, frac[1] * H, frac[2] * W, frac[3] * H]
    x0, top, x1, bottom = bbox
    if x0 >= x1 or top >= bottom:
        raise ValueError("bbox must have positive width and height (x0 < x1, top < bottom)")
    if x0 < 0 or top < 0 or x1 > W or bottom > H:
        raise ValueError(f"bbox lies outside page {page_no}: bounds are [0, 0, {W:g}, {H:g}] points")
    box = (max(0, x0 - pad), max(0, top - pad), min(W, x1 + pad), min(H, bottom + pad))
    im = page.crop(box, relative=False, strict=True).to_image(resolution=dpi)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    im.save(out)
    pil = im.original
    print(f"saved {out}  page={page_no} bbox={[round(v, 1) for v in box]}  size={pil.size[0]}x{pil.size[1]}px")
    return {"page": page_no, "bbox": list(box), "out": os.path.abspath(out), "size_px": list(pil.size)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--page", type=int)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--bbox", type=float, nargs=4, metavar=("X0", "TOP", "X1", "BOTTOM"))
    g.add_argument("--frac", type=float, nargs=4, metavar=("FX0", "FTOP", "FX1", "FBOTTOM"))
    g.add_argument("--batch")
    ap.add_argument("-o", "--out")
    ap.add_argument("--dpi", type=int, default=250)
    ap.add_argument("--pad", type=float, default=0, help="extra padding in PDF points; clipped at page edges")
    a = ap.parse_args(argv)

    with pdfplumber.open(a.pdf) as pdf:
        if a.batch:
            with open(a.batch, encoding="utf-8") as f:
                jobs = json.load(f)
            if not isinstance(jobs, list):
                ap.error("batch JSON must be a list of crop objects")
            for n, job in enumerate(jobs, 1):
                try:
                    crop(pdf, job["page"], job["out"], bbox=job.get("bbox"), frac=job.get("frac"),
                         dpi=job.get("dpi", a.dpi), pad=job.get("pad", a.pad))
                except (KeyError, TypeError, ValueError) as e:
                    ap.error(f"crop {n}: {e}")
        else:
            if not (a.page and a.out and (a.bbox or a.frac)):
                ap.error("--page, -o, and one of --bbox/--frac are required (or use --batch)")
            try:
                crop(pdf, a.page, a.out, bbox=a.bbox, frac=a.frac, dpi=a.dpi, pad=a.pad)
            except ValueError as e:
                ap.error(str(e))


if __name__ == "__main__":
    sys.exit(main())
