#!/usr/bin/env python3
"""Render exact supplied math with matplotlib, or crop the original PDF.

Existing CLI: render_equation.py 'E=mc^2' -o assets/eq.png
Batch: --batch equations.json --outdir assets [--report equations-report.json]
  [{"name":"eq1", "latex":"...", "pdf":"paper.pdf", "page":3,
    "bbox":[50,100,550,150]}]

Mathtext is a LaTeX subset. Never rewrite, simplify, or silently drop unsupported
notation. On a mathtext failure, optional pdf/page/bbox fields crop the original
equation faithfully. A crop-only item may omit latex. Relative PDF paths in batch
items resolve against the JSON file's directory. Coordinates are top-left PDF
points. Inspect each crop against the original page and cite its page/equation.
"""
import argparse
import json
import math
import os
import re
import sys
import tempfile


def _prepare_matplotlib_cache():
    """Keep default caches writable in sandboxed Codex runs; honor user settings."""
    if "MPLCONFIGDIR" not in os.environ:
        user_id = os.getuid() if hasattr(os, "getuid") else "user"
        cache_root = os.path.join(tempfile.gettempdir(), f"pimp-cache-{user_id}")
        config_dir = os.path.join(cache_root, "matplotlib")
        os.makedirs(config_dir, exist_ok=True)
        os.environ["MPLCONFIGDIR"] = config_dir
        # Fontconfig subprocesses use XDG_CACHE_HOME independently of matplotlib.
        if "XDG_CACHE_HOME" not in os.environ:
            xdg_cache = os.path.join(cache_root, "xdg")
            os.makedirs(xdg_cache, exist_ok=True)
            os.environ["XDG_CACHE_HOME"] = xdg_cache


def render(latex, out, color="1F2933", fontsize=30, dpi=300):
    """Atomically save mathtext output; an unsuccessful parse writes no image."""
    if not isinstance(latex, str) or not latex.strip().strip("$").strip():
        raise ValueError("latex must be a nonempty string")
    if not isinstance(color, str) or not re.fullmatch(r"[0-9a-fA-F]{6}", color):
        raise ValueError("color must be six hexadecimal digits, for example 1F2933")
    if any(not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 for v in (fontsize, dpi)):
        raise ValueError("fontsize and dpi must be positive numbers")
    _prepare_matplotlib_cache()
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as e:
        raise RuntimeError("matplotlib is unavailable; run the repository bootstrap with the selected Python, "
                           "or provide pdf/page/bbox to crop the original equation") from e
    matplotlib.rcParams["mathtext.fontset"] = "cm"
    latex = latex.strip().strip("$")
    output_dir = os.path.dirname(os.path.abspath(out))
    os.makedirs(output_dir, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output_dir, prefix=".equation-", suffix=".png", delete=False) as tmp:
        temp_path = tmp.name
    fig = None
    try:
        fig = plt.figure(figsize=(0.01, 0.01))
        fig.text(0, 0, f"${latex}$", fontsize=fontsize, color=f"#{color}")
        fig.savefig(temp_path, dpi=dpi, transparent=True, bbox_inches="tight", pad_inches=0.05)
        os.replace(temp_path, out)
    finally:
        if fig is not None:
            plt.close(fig)
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    print(f"saved {out}  mode=mathtext")
    return {"out": os.path.abspath(out), "mode": "mathtext", "latex": latex}


def _err(e):
    lines = [line for line in str(e).splitlines() if line.strip()]
    return " | ".join(lines[-3:]) if lines else type(e).__name__


def render_item(item, out, defaults=None, base_dir="."):
    """Render a batch item; only an explicit source crop can recover failure."""
    if not isinstance(item, dict):
        raise ValueError("each equation item must be an object")
    defaults = defaults or {}
    render_error = None
    if item.get("latex") is not None:
        try:
            return render(item["latex"], out, item.get("color", defaults.get("color", "1F2933")),
                          item.get("fontsize", defaults.get("fontsize", 30)),
                          item.get("dpi", defaults.get("dpi", 300)))
        except Exception as e:
            render_error = _err(e)
    if not all(key in item and item[key] is not None for key in ("pdf", "page", "bbox")):
        reason = render_error or "no latex or complete PDF crop source was provided"
        raise ValueError(f"{reason}. Supply verified pdf/page/bbox fields for an exact PDF crop; "
                         "do not simplify the equation to make it parse")
    import pdfplumber
    from crop_figure import crop
    source = os.path.abspath(os.path.join(base_dir, item["pdf"]))
    try:
        with pdfplumber.open(source) as pdf:
            result = crop(pdf, item["page"], out, bbox=item["bbox"],
                          dpi=item.get("dpi", defaults.get("dpi", 300)))
    except Exception as e:
        detail = f"; mathtext also failed: {render_error}" if render_error else ""
        raise ValueError(f"PDF crop failed for {source}: {_err(e)}{detail}") from e
    result.update({"mode": "pdf_crop", "pdf": source, "render_error": render_error,
                   "review_required": True})
    if render_error:
        print(f"mathtext failed; saved faithful PDF crop {out}: {render_error}", file=sys.stderr)
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("latex", nargs="?")
    ap.add_argument("-o", "--out")
    ap.add_argument("--batch")
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--report", help="write equation provenance/status JSON, including failed items")
    ap.add_argument("--color", default="1F2933")
    ap.add_argument("--fontsize", type=int, default=30)
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--pdf", help="original PDF used for a faithful crop fallback")
    ap.add_argument("--page", type=int, help="one-based PDF page")
    ap.add_argument("--bbox", type=float, nargs=4, metavar=("X0", "TOP", "X1", "BOTTOM"))
    a = ap.parse_args(argv)
    defaults = {"color": a.color, "fontsize": a.fontsize, "dpi": a.dpi}
    if a.batch:
        with open(a.batch, encoding="utf-8") as f:
            jobs = json.load(f)
        if not isinstance(jobs, list):
            ap.error("batch JSON must be a list of equation objects")
        base_dir = os.path.dirname(os.path.abspath(a.batch))
    else:
        if not a.out or not (a.latex or (a.pdf and a.page and a.bbox)):
            ap.error("supply latex and -o, or --pdf/--page/--bbox and -o (or use --batch)")
        jobs = [{"name": "equation", "latex": a.latex}]
        if a.pdf is not None:
            jobs[0].update({"pdf": a.pdf, "page": a.page, "bbox": a.bbox})
        base_dir = os.getcwd()
    failed, results = 0, []
    for idx, item in enumerate(jobs, 1):
        name = item.get("name", f"item_{idx}") if isinstance(item, dict) else f"item_{idx}"
        try:
            if a.batch and (not isinstance(name, str) or not name or os.path.basename(name) != name or name in (".", "..")):
                raise ValueError("name must be a nonempty filename without directory components")
            out = os.path.join(a.outdir, f"{name}.png") if a.batch else a.out
            result = render_item(item, out, defaults, base_dir)
            result.update({"name": name, "status": "success"})
        except Exception as e:
            failed += 1
            result = {"name": name, "status": "failed", "error": _err(e)}
            print(f"FAILED {name}: {result['error']}", file=sys.stderr)
        results.append(result)
    if a.report:
        os.makedirs(os.path.dirname(os.path.abspath(a.report)), exist_ok=True)
        with open(a.report, "w", encoding="utf-8") as f:
            json.dump({"equations": results, "failed": failed}, f, ensure_ascii=False, indent=2)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
