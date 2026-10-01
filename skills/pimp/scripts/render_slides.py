#!/usr/bin/env python3
"""Render a PPTX with an isolated LibreOffice profile and fontconfig.

Runtime paths are supplied by PIMP_SOFFICE/PIMP_RUNTIME_DIR or PATH. This
script never installs fonts or changes the user's LibreOffice/font config.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import xml.etree.ElementTree as ET


FONT_ROOTS = {
    "darwin": ["/System/Library/Fonts", "/Library/Fonts", "~/Library/Fonts"],
    "linux": ["/usr/share/fonts", "/usr/local/share/fonts", "~/.local/share/fonts", "~/.fonts"],
    "win32": [str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts")],
}


def find_soffice(explicit: str | None = None) -> Path:
    """Resolve an explicit executable, a supplied runtime root, then PATH."""
    requested = explicit or os.environ.get("PIMP_SOFFICE")
    if requested:
        located = shutil.which(requested)
        path = Path(located or requested).expanduser()
        if path.is_file():
            return path.resolve()
        raise FileNotFoundError(f"LibreOffice executable not found: {requested}")
    runtime = os.environ.get("PIMP_RUNTIME_DIR")
    if runtime:
        for relative in ("bin/override/soffice", "bin/soffice", "soffice"):
            path = Path(runtime).expanduser() / relative
            if path.is_file():
                return path.resolve()
    for name in ("soffice", "libreoffice"):
        located = shutil.which(name)
        if located:
            return Path(located).resolve()
    if sys.platform == "darwin":
        path = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")
        if path.is_file():
            return path
    raise FileNotFoundError("Set PIMP_SOFFICE to the LibreOffice executable or add soffice to PATH.")


def find_pdftoppm() -> Path:
    requested = os.environ.get("PIMP_PDFTOPPM")
    if requested:
        path = Path(shutil.which(requested) or requested).expanduser()
        if path.is_file():
            return path.resolve()
        raise FileNotFoundError(f"pdftoppm executable not found: {requested}")
    runtime = os.environ.get("PIMP_RUNTIME_DIR")
    if runtime:
        for relative in ("bin/override/pdftoppm", "bin/pdftoppm", "pdftoppm"):
            path = Path(runtime).expanduser() / relative
            if path.is_file():
                return path.resolve()
    located = shutil.which("pdftoppm")
    if located:
        return Path(located).resolve()
    raise FileNotFoundError("Install PyMuPDF or provide pdftoppm via PIMP_PDFTOPPM/PATH.")


def font_directories(extra: list[str]) -> list[Path]:
    directories = []
    for item in FONT_ROOTS.get(sys.platform, []) + extra:
        path = Path(item).expanduser().resolve()
        if path.is_dir() and path not in directories:
            directories.append(path)
        elif item in extra and not path.is_dir():
            raise FileNotFoundError(f"Font directory does not exist: {path}")
    return directories


def prepare_fontconfig(work: Path, dirs: list[Path], files: list[str], family: str | None) -> tuple[Path, str]:
    """Expose OS fonts to headless builds that ship their own fontconfig."""
    extra = work / "fonts"
    extra.mkdir()
    for i, item in enumerate(files):
        path = Path(item).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Font file does not exist: {path}")
        # Copy into this run's private directory: fontconfig has directory nodes,
        # not file nodes. No global font folder is changed.
        shutil.copy2(path, extra / f"{i}-{path.name}")
    if files:
        dirs = [extra] + dirs
    family = family or os.environ.get("PIMP_FONT") or {
        "darwin": "Apple SD Gothic Neo", "linux": "Noto Sans CJK KR", "win32": "Malgun Gothic"
    }.get(sys.platform, "sans-serif")
    root = ET.Element("fontconfig")
    for path in dirs:
        ET.SubElement(root, "dir").text = str(path)
    cache = work / "font-cache"
    cache.mkdir()
    ET.SubElement(root, "cachedir").text = str(cache)
    for alias in ("Malgun Gothic", "Noto Sans CJK KR", "Noto Sans KR", "sans-serif"):
        element = ET.SubElement(root, "alias", {"binding": "strong"})
        ET.SubElement(element, "family").text = alias
        prefer = ET.SubElement(element, "prefer")
        ET.SubElement(prefer, "family").text = family
    config = work / "fonts.conf"
    config.write_text('<?xml version="1.0"?>\n<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">\n' + ET.tostring(root, encoding="unicode"), encoding="utf-8")
    return config, family


def normalized(text: str) -> str:
    return "".join(unicodedata.normalize("NFC", text).split())


def render(args: argparse.Namespace) -> dict:
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise RuntimeError("Rendering requires Pillow. Run the repository bootstrap first.") from exc
    try:
        import fitz
    except ImportError:
        fitz = None
    source = Path(args.pptx).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() != ".pptx":
        raise FileNotFoundError(f"Expected a PPTX file: {source}")
    if not (36 <= args.dpi <= 600):
        raise ValueError("--dpi must be between 36 and 600")
    if args.timeout <= 0:
        raise ValueError("--timeout must be positive")
    output = Path(args.output or source.parent / (source.stem + "_render")).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    soffice = find_soffice(args.soffice)
    dirs = font_directories(args.font_dir)
    with tempfile.TemporaryDirectory(prefix="pimp-render-") as tmp:
        work = Path(tmp)
        config, family = prepare_fontconfig(work, dirs, args.font_file, args.font_family)
        env = os.environ.copy()
        env.update({"FONTCONFIG_FILE": str(config), "FONTCONFIG_PATH": str(work), "XDG_CACHE_HOME": str(work / "cache")})
        conversion = work / "converted"
        conversion.mkdir()
        command = [str(soffice), f"-env:UserInstallation={(work / 'profile').as_uri()}", "--headless", "--convert-to", "pdf:impress_pdf_Export", "--outdir", str(conversion), str(source)]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, env=env, timeout=args.timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"LibreOffice conversion exceeded {args.timeout:g} seconds") from exc
        converted = conversion / (source.stem + ".pdf")
        if completed.returncode != 0 or not converted.is_file():
            diagnostics = (completed.stdout + "\n" + completed.stderr).strip()[-4000:]
            raise RuntimeError(f"LibreOffice PDF conversion failed ({completed.returncode}): {diagnostics}")
        pdf = output / (source.stem + ".pdf")
        shutil.copy2(converted, pdf)
    # Only remove files owned by this renderer, so re-running after deleting a
    # slide cannot leave a stale slide-999.png that looks current.
    for existing in output.glob("slide-[0-9][0-9][0-9][0-9].png"):
        existing.unlink()
    text_pages, page_files = [], []
    if fitz is not None:
        with fitz.open(pdf) as document:
            if document.page_count == 0:
                raise RuntimeError("LibreOffice produced an empty PDF")
            for i, page in enumerate(document):
                text_pages.append(page.get_text())
                path = output / f"slide-{i + 1:04d}.png"
                page.get_pixmap(dpi=args.dpi, alpha=False).save(path)
                page_files.append(path)
        render_backend = "pymupdf"
    else:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("Rendering requires PyMuPDF or pypdf with Poppler pdftoppm.") from exc
        document = PdfReader(str(pdf))
        if not document.pages:
            raise RuntimeError("LibreOffice produced an empty PDF")
        pdftoppm = find_pdftoppm()
        with tempfile.TemporaryDirectory(prefix="pimp-pages-") as tmp:
            prefix = Path(tmp) / "page"
            try:
                result = subprocess.run([str(pdftoppm), "-png", "-r", str(args.dpi), str(pdf), str(prefix)], capture_output=True, text=True, timeout=args.timeout, check=False)
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(f"PDF rasterization exceeded {args.timeout:g} seconds") from exc
            generated = sorted(Path(tmp).glob("page-*.png"), key=lambda path: int(path.stem.rsplit("-", 1)[-1]))
            if result.returncode or len(generated) != len(document.pages):
                raise RuntimeError(f"pdftoppm failed ({result.returncode}): {result.stderr.strip()[-4000:]}")
            for i, (page, image_file) in enumerate(zip(document.pages, generated)):
                text_pages.append(page.extract_text() or "")
                path = output / f"slide-{i + 1:04d}.png"
                shutil.copy2(image_file, path)
                page_files.append(path)
        render_backend = "poppler"
    (output / "rendered_text.txt").write_text("\n\n".join(text_pages), encoding="utf-8")
    expected = list(args.expect_text)
    if args.expect_text_file:
        expected.extend(line.strip() for line in Path(args.expect_text_file).read_text(encoding="utf-8").splitlines() if line.strip())
    haystack = normalized("\n".join(text_pages))
    missing = [item for item in expected if normalized(item) not in haystack]
    cols = min(4, len(page_files))
    thumb_w, thumb_h, label_h, gap = 400, 225, 26, 12
    rows = (len(page_files) + cols - 1) // cols
    montage = Image.new("RGB", (cols * (thumb_w + gap) + gap, rows * (thumb_h + label_h + gap) + gap), "#e8e8e8")
    draw = ImageDraw.Draw(montage)
    for i, page_file in enumerate(page_files):
        with Image.open(page_file) as full:
            thumb = full.convert("RGB")
            thumb.thumbnail((thumb_w, thumb_h))
        x, y = gap + (i % cols) * (thumb_w + gap), gap + (i // cols) * (thumb_h + label_h + gap)
        montage.paste(thumb, (x + (thumb_w - thumb.width) // 2, y))
        draw.text((x + 4, y + thumb_h + 4), f"Slide {i + 1}", fill="#222222")
    montage_file = output / "montage.png"
    montage.save(montage_file)
    report = {
        "ok": not missing, "pptx": str(source), "pdf": str(pdf), "slide_count": len(page_files),
        "slides": [str(path) for path in page_files], "montage": str(montage_file),
        "render_backend": render_backend,
        "font_family": family, "font_directories": [str(path) for path in dirs],
        "expected_text": expected, "missing_text": missing,
        "text_check": "passed" if expected and not missing else "failed" if missing else "not_requested",
        "scope": "Expected text extraction detects missing glyphs/text; visual review is still required for clipping, overlaps, and correct paper interpretation.",
    }
    report_file = output / "render_report.json"
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["report"] = str(report_file)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pptx")
    parser.add_argument("--output", "--outdir", "-o")
    parser.add_argument("--soffice", help="LibreOffice executable (also PIMP_SOFFICE)")
    parser.add_argument("--font-dir", action="append", default=[], help="Additional font directory, repeatable")
    parser.add_argument("--font-file", action="append", default=[], help="Additional font file, repeatable; copied to a temporary directory")
    parser.add_argument("--font-family", help="Korean fallback family (also PIMP_FONT)")
    parser.add_argument("--expect-text", action="append", default=[], help="Required rendered text, repeatable; use a Korean phrase for glyph verification")
    parser.add_argument("--expect-text-file", help="UTF-8 text file with one expected phrase per line")
    parser.add_argument("--dpi", type=int, default=120)
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    try:
        report = render(args)
    except (OSError, RuntimeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
