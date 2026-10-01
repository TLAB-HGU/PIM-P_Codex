#!/usr/bin/env python3
"""
render_equation.py — LaTeX 수식을 투명 배경 PNG로 렌더링 (matplotlib mathtext, TeX 설치 불필요).

usage:
  python3 render_equation.py "\\mathrm{Attention}(Q,K,V)=\\mathrm{softmax}\\left(\\frac{QK^T}{\\sqrt{d_k}}\\right)V" -o assets/eq1.png
  python3 render_equation.py --batch equations.json --outdir assets/
      equations.json = [{"name": "eq1", "latex": "..."}, ...]

옵션: --color 1F2933 (hex, '#' 없이) --fontsize 30 --dpi 300

mathtext는 LaTeX 부분집합만 지원한다. 자주 걸리는 것과 대체:
  \\text{..}        → \\mathrm{..}
  \\operatorname{f} → \\mathrm{f}
  \\mathbb{E}       → 지원됨 (\\mathbb{R} 등)
  \\begin{aligned}  → 미지원: 수식을 줄 단위로 나눠 각각 렌더링
  \\left( \\right)   → 지원됨,  \\big( → 지원됨
  \\coloneqq        → :=
  \\tag{}           → 빼고 슬라이드에서 eqLabels로 번호 표시
실패하면 에러 메시지와 함께 해당 수식 이름을 출력한다 — 수식을 단순화해 다시 시도할 것.
"""
import argparse
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

matplotlib.rcParams["mathtext.fontset"] = "cm"


def render(latex, out, color="1F2933", fontsize=30, dpi=300):
    latex = latex.strip().strip("$")
    fig = plt.figure(figsize=(0.01, 0.01))
    fig.text(0, 0, f"${latex}$", fontsize=fontsize, color=f"#{color}")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    fig.savefig(out, dpi=dpi, transparent=True, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
    print(f"saved {out}")


def _err(e):
    lines = [l for l in str(e).splitlines() if l.strip()]
    return " | ".join(lines[-3:]) if lines else type(e).__name__


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("latex", nargs="?")
    ap.add_argument("-o", "--out")
    ap.add_argument("--batch")
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--color", default="1F2933")
    ap.add_argument("--fontsize", type=int, default=30)
    ap.add_argument("--dpi", type=int, default=300)
    a = ap.parse_args()

    failed = 0
    if a.batch:
        for item in json.load(open(a.batch)):
            out = os.path.join(a.outdir, f"{item['name']}.png")
            try:
                render(item["latex"], out, item.get("color", a.color), item.get("fontsize", a.fontsize), a.dpi)
            except Exception as e:  # mathtext 파싱 실패
                failed += 1
                print(f"FAILED {item['name']}: {_err(e)}", file=sys.stderr)
    else:
        if not (a.latex and a.out):
            ap.error("latex and -o are required (or use --batch)")
        try:
            render(a.latex, a.out, a.color, a.fontsize, a.dpi)
        except Exception as e:
            failed = 1
            print(f"FAILED: {_err(e)}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
