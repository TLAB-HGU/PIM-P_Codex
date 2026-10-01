"""Public synthetic fixtures exercise reading, evidence preservation, and crop fidelity."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from PIL import Image
import pdfplumber
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "pimp" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import crop_figure
import pdf_inventory
import render_equation


class PDFToolsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.columns = self.root / "columns.pdf"
        c = canvas.Canvas(str(self.columns), pagesize=(612, 792))
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(306, 752, "A SYNTHETIC TWO COLUMN RESEARCH PAPER")
        c.setFont("Helvetica", 10)
        for row in range(9):
            c.drawString(50, 700 - row * 13, f"LEFT section row {row:02d} stays left")
            c.drawString(330, 700 - row * 13, f"RIGHT section row {row:02d} stays right")
        c.rect(50, 462, 210, 55)
        c.rect(330, 462, 210, 55)
        c.setFont("Helvetica", 9)
        c.drawString(50, 442, "Figure 1. Left result only")
        c.drawString(330, 442, "Figure 2. Right result only")
        c.drawString(50, 431, "Left caption continuation.")
        c.drawString(330, 431, "Right caption continuation.")
        c.drawString(50, 390, "E = m c squared; original equation evidence")
        c.save()
        scan_source = self.root / "scan-source.pdf"
        c = canvas.Canvas(str(scan_source), pagesize=(612, 792))
        c.setFont("Helvetica", 22)
        for row in range(12):
            c.drawString(40, 730 - row * 42, f"SCANNED TEST PAGE row {row:02d}")
        c.save()
        with pdfplumber.open(scan_source) as pdf:
            scan_image = pdf.pages[0].to_image(resolution=150).original.copy()
        self.mixed = self.root / "mixed.pdf"
        c = canvas.Canvas(str(self.mixed), pagesize=(612, 792))
        c.setFont("Helvetica", 12)
        for row in range(12):
            c.drawString(50, 700 - row * 20, f"Native selectable text row {row:02d} for mixed page detection.")
        c.showPage()
        c.drawImage(ImageReader(scan_image), 0, 0, width=612, height=792)
        c.showPage()
        c.showPage()  # genuinely blank page must not be labeled scanned
        c.save()

    def tearDown(self):
        self.tmp.cleanup()

    def test_two_column_reading_and_caption_separation(self):
        inv = pdf_inventory.build_inventory(self.columns, self.root / "columns-out")
        text = (self.root / "columns-out/text/page_001.txt").read_text()
        self.assertEqual(inv["pages"][0]["reading_order"], "two-column heuristic")
        self.assertLess(text.index("LEFT section row 08"), text.index("RIGHT section row 00"))
        captions = {item["id"]: item for item in inv["captions"]}
        self.assertIn("Left caption continuation.", captions["Fig 1"]["caption"])
        self.assertNotIn("Right", captions["Fig 1"]["caption"])
        self.assertNotIn("Left", captions["Fig 2"]["caption"])
        self.assertEqual(captions["Fig 1"]["detection"], "heuristic")
        self.assertTrue(captions["Fig 1"]["review_required"])
        self.assertLess(captions["Fig 1"]["suggested_bbox"][2], 330)

    def test_mixed_pdf_scan_detection_is_per_page(self):
        inv = pdf_inventory.build_inventory(self.mixed, self.root / "mixed-out")
        self.assertEqual(inv["scanned_pages"], [2])
        self.assertTrue(inv["likely_scanned"])
        self.assertFalse(inv["pages"][0]["likely_scanned"])
        self.assertFalse(inv["pages"][2]["likely_scanned"])
        self.assertEqual(inv["pages"][1]["text_source"], "none")
        self.assertTrue(any("p.2" in warning and "--ocr auto" in warning for warning in inv["warnings"]))
        for entry in inv["pages"]:
            self.assertTrue(Path(entry["image"]).exists())

    def test_auto_ocr_keeps_original_evidence_and_marks_text(self):
        baseline = pdf_inventory.build_inventory(self.mixed, self.root / "baseline")
        words = [{"text": "SCANNED", "x0": 40, "x1": 150, "top": 42, "bottom": 64},
                 {"text": "EVIDENCE", "x0": 170, "x1": 290, "top": 42, "bottom": 64}]
        with mock.patch.object(pdf_inventory, "tesseract_check", return_value="tesseract"), \
             mock.patch.object(pdf_inventory, "ocr_words", return_value=(words, 91.0)) as ocr:
            inv = pdf_inventory.build_inventory(self.mixed, self.root / "ocr", ocr="auto", ocr_lang="eng+kor")
        self.assertEqual(ocr.call_count, 1)
        self.assertEqual(inv["pages"][1]["text_source"], "ocr")
        self.assertEqual(inv["pages"][1]["ocr"]["lang"], "eng+kor")
        self.assertTrue(inv["pages"][1]["ocr"]["review_required"])
        self.assertEqual((self.root / "ocr/text/page_002.native.txt").read_text(), "")
        self.assertIn("SCANNED EVIDENCE", (self.root / "ocr/full.txt").read_text())
        self.assertEqual(Path(baseline["pages"][1]["image"]).read_bytes(),
                         Path(inv["pages"][1]["image"]).read_bytes())

    def test_ocr_failure_writes_inventory_and_returns_failure(self):
        with mock.patch.object(pdf_inventory, "tesseract_check", side_effect=RuntimeError("Install Tesseract eng data")), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = pdf_inventory.main([str(self.mixed), str(self.root / "failed-ocr"), "--ocr", "auto"])
        inv = json.loads((self.root / "failed-ocr/inventory.json").read_text())
        self.assertEqual(code, 2)
        self.assertFalse(inv["complete"])
        self.assertEqual(inv["pages"][1]["ocr"]["status"], "failed")
        self.assertIn("Install Tesseract", inv["errors"][0])
        self.assertTrue((self.root / "failed-ocr/pages/page-002.png").exists())

    def test_missing_ocr_language_is_actionable(self):
        result = subprocess.CompletedProcess([], 0, "List of available languages (2):\neng\nosd\n", "")
        with mock.patch.object(pdf_inventory.shutil, "which", return_value="/usr/bin/tesseract"), \
             mock.patch.object(pdf_inventory.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(RuntimeError, "missing: kor.*--ocr-lang"):
                pdf_inventory.tesseract_check("eng+kor")

    def test_tesseract_executable_override_is_honored(self):
        executable = "/custom/Tesseract tool"
        result = subprocess.CompletedProcess([], 0, "List of available languages (1):\neng\n", "")
        with mock.patch.dict(os.environ, {"PIMP_TESSERACT": executable}), \
             mock.patch.object(pdf_inventory.shutil, "which", return_value=executable) as which, \
             mock.patch.object(pdf_inventory.subprocess, "run", return_value=result) as run:
            self.assertEqual(pdf_inventory.tesseract_check("eng"), executable)
        which.assert_called_once_with(executable)
        self.assertEqual(run.call_args.args[0], [executable, "--list-langs"])

    def test_ocr_tsv_maps_pixels_to_pdf_points(self):
        image_path = self.root / "tsv-image.png"
        Image.new("RGB", (1224, 1584), "white").save(image_path)
        tsv = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        tsv += "5\t1\t1\t1\t1\t1\t100\t200\t80\t40\t92.5\tEvidence\n"
        result = subprocess.CompletedProcess([], 0, tsv, "")
        with pdfplumber.open(self.columns) as pdf, \
             mock.patch.object(pdf_inventory.subprocess, "run", return_value=result) as run:
            words, confidence = pdf_inventory.ocr_words(str(image_path), pdf.pages[0], "tesseract", "eng")
        self.assertEqual(words[0]["x0"], 50)
        self.assertEqual(words[0]["top"], 100)
        self.assertEqual(words[0]["x1"], 90)
        self.assertEqual(words[0]["bottom"], 120)
        self.assertEqual(confidence, 92.5)
        self.assertEqual(run.call_args.args[0][-3:], ["-l", "eng", "tsv"])

    def test_point_crop_has_expected_dimensions(self):
        output = self.root / "crop.png"
        with pdfplumber.open(self.columns) as pdf, contextlib.redirect_stdout(io.StringIO()):
            result = crop_figure.crop(pdf, 1, output, bbox=[50, 275, 260, 330], dpi=144)
        with Image.open(output) as image:
            self.assertEqual(image.size, (420, 110))
        self.assertEqual(result["bbox"], [50, 275, 260, 330])
        self.assertEqual(result["page"], 1)

    def test_invalid_crop_never_writes_output(self):
        output = self.root / "invalid.png"
        with pdfplumber.open(self.columns) as pdf:
            cases = [(0, [0, 0, 100, 100]), (-1, [0, 0, 100, 100]), (2, [0, 0, 100, 100]),
                     (1, [-10, 0, 100, 100]), (1, [0, 0, 613, 100]),
                     (1, [100, 0, 50, 100]), (1, [0, 0, float("nan"), 100])]
            for page, bbox in cases:
                with self.subTest(page=page, bbox=bbox), self.assertRaises(ValueError):
                    crop_figure.crop(pdf, page, output, bbox=bbox)
                self.assertFalse(output.exists())

    def test_equation_crop_fallback_preserves_supplied_latex(self):
        latex = r"\begin{aligned}E &= mc^2\end{aligned}"
        batch = self.root / "equations.json"
        batch.write_text(json.dumps([{"name": "original", "latex": latex, "pdf": "columns.pdf", "page": 1,
                                      "bbox": [45, 385, 330, 411]}]))
        report = self.root / "equation-report.json"
        with mock.patch.object(render_equation, "render", side_effect=ValueError("unsupported aligned")) as render, \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = render_equation.main(["--batch", str(batch), "--outdir", str(self.root / "assets"),
                                         "--report", str(report)])
        self.assertEqual(code, 0)
        self.assertEqual(render.call_args.args[0], latex)
        item = json.loads(report.read_text())["equations"][0]
        self.assertEqual(item["mode"], "pdf_crop")
        self.assertEqual(item["pdf"], str(self.columns))
        self.assertEqual(item["page"], 1)
        self.assertTrue(item["review_required"])
        self.assertTrue((self.root / "assets/original.png").exists())

    def test_equation_crop_only_does_not_need_matplotlib(self):
        with mock.patch.object(render_equation, "render") as render, contextlib.redirect_stdout(io.StringIO()):
            item = render_equation.render_item({"pdf": str(self.columns), "page": 1,
                                                "bbox": [45, 385, 330, 411]}, self.root / "crop-only.png")
        render.assert_not_called()
        self.assertEqual(item["mode"], "pdf_crop")

    def test_failed_equation_without_fallback_is_not_success(self):
        output = self.root / "failed-equation.png"
        report = self.root / "failed-equation.json"
        with mock.patch.object(render_equation, "render", side_effect=ValueError("unsupported notation")), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = render_equation.main([r"\unsupported{x}", "-o", str(output), "--report", str(report)])
        self.assertEqual(code, 1)
        self.assertFalse(output.exists())
        item = json.loads(report.read_text())["equations"][0]
        self.assertEqual(item["status"], "failed")
        self.assertIn("pdf/page/bbox", item["error"])

    def test_equation_cache_defaults_are_writable_and_user_settings_preserved(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
             mock.patch.object(render_equation.tempfile, "gettempdir", return_value=str(self.root)):
            render_equation._prepare_matplotlib_cache()
            self.assertTrue(Path(os.environ["MPLCONFIGDIR"]).is_dir())
            self.assertTrue(Path(os.environ["XDG_CACHE_HOME"]).is_dir())
        with mock.patch.dict(os.environ, {"MPLCONFIGDIR": "/my/config", "XDG_CACHE_HOME": "/my/cache"}, clear=True):
            render_equation._prepare_matplotlib_cache()
            self.assertEqual(os.environ["MPLCONFIGDIR"], "/my/config")
            self.assertEqual(os.environ["XDG_CACHE_HOME"], "/my/cache")

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "matplotlib not installed in this Python")
    def test_real_mathtext_render_and_atomic_parse_failure(self):
        output = self.root / "equation.png"
        with contextlib.redirect_stdout(io.StringIO()):
            render_equation.render(r"E=mc^2", output)
        with Image.open(output) as image:
            self.assertEqual(image.mode, "RGBA")
            self.assertGreater(image.width, 30)
        invalid = self.root / "unsupported.png"
        with self.assertRaises(Exception):
            render_equation.render(r"\begin{aligned}x &= y\end{aligned}", invalid)
        self.assertFalse(invalid.exists())
        self.assertEqual(list(self.root.glob(".equation-*.png")), [])

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "matplotlib not installed in this Python")
    def test_mathtext_italic_overhang_has_transparent_margin(self):
        # The original tight-bbox export cut off the final italic V in Attention
        # even though it returned success. Inspect actual ink bounds, not layout
        # estimates; every edge must retain transparent pixels at the final DPI.
        formulas = [r"\mathrm{Attention}(Q,K,V)=\mathrm{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V",
                    r"V", r"f", r"x^2V"]
        for dpi in (150, 300):
            for index, latex in enumerate(formulas):
                with self.subTest(dpi=dpi, latex=latex), contextlib.redirect_stdout(io.StringIO()):
                    output = self.root / f"overhang-{dpi}-{index}.png"
                    render_equation.render(latex, output, dpi=dpi)
                    with Image.open(output) as image:
                        ink = image.getchannel("A").getbbox()
                        self.assertIsNotNone(ink)
                        margins = (ink[0], ink[1], image.width - ink[2], image.height - ink[3])
                        self.assertTrue(all(value >= max(8, int(dpi * .05)) for value in margins), margins)
                        self.assertEqual(len(set(margins)), 1, margins)

    @unittest.skipUnless(shutil.which("tesseract"), "Tesseract is optional")
    def test_real_tesseract_reads_synthetic_scan(self):
        try:
            pdf_inventory.tesseract_check("eng")
        except RuntimeError as e:
            self.skipTest(str(e))
        inv = pdf_inventory.build_inventory(self.mixed, self.root / "real-ocr", dpi=150, ocr="auto")
        self.assertTrue(inv["complete"], inv["errors"])
        self.assertEqual(inv["pages"][1]["text_source"], "ocr")
        self.assertIn("SCANNED TEST PAGE", (self.root / "real-ocr/text/page_002.txt").read_text())


if __name__ == "__main__":
    unittest.main()
