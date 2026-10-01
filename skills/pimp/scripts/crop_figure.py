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
import os
import sys

import pdfplumber


def crop(pdf, page_no, out, bbox=None, frac=None, dpi=250, pad=0):
    page = pdf.pages[page_no - 1]
    W, H = page.width, page.height
    if frac:
        bbox = [frac[0] * W, frac[1] * H, frac[2] * W, frac[3] * H]
    x0, top, x1, bottom = bbox
    box = (max(0, x0 - pad), max(0, top - pad), min(W, x1 + pad), min(H, bottom + pad))
    im = page.crop(box, relative=False, strict=False).to_image(resolution=dpi)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    im.save(out)
    pil = im.original
    print(f"saved {out}  page={page_no} bbox={[round(v, 1) for v in box]}  size={pil.size[0]}x{pil.size[1]}px")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--page", type=int)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--bbox", type=float, nargs=4, metavar=("X0", "TOP", "X1", "BOTTOM"))
    g.add_argument("--frac", type=float, nargs=4, metavar=("FX0", "FTOP", "FX1", "FBOTTOM"))
    g.add_argument("--batch")
    ap.add_argument("-o", "--out")
    ap.add_argument("--dpi", type=int, default=250)
    a = ap.parse_args()

    with pdfplumber.open(a.pdf) as pdf:
        if a.batch:
            for job in json.load(open(a.batch)):
                crop(pdf, job["page"], job["out"], bbox=job.get("bbox"), frac=job.get("frac"), dpi=job.get("dpi", a.dpi))
        else:
            if not (a.page and a.out and (a.bbox or a.frac)):
                ap.error("--page, -o, and one of --bbox/--frac are required (or use --batch)")
            crop(pdf, a.page, a.out, bbox=a.bbox, frac=a.frac, dpi=a.dpi)


if __name__ == "__main__":
    sys.exit(main())
