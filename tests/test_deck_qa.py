"""Regression checks for failures that can survive a successful PPTX save."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "skills/pimp/scripts"
spec = importlib.util.spec_from_file_location("check_deck", SCRIPT_DIR / "check_deck.py")
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)
render_spec = importlib.util.spec_from_file_location("render_slides", SCRIPT_DIR / "render_slides.py")
renderer = importlib.util.module_from_spec(render_spec)
render_spec.loader.exec_module(renderer)


REL = "http://schemas.openxmlformats.org/package/2006/relationships"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"


def fixture(path, notes=True, placeholder=False, broken_target=False, outside=False, substantive_notes=True):
    """A package containing slide-number boilerplate plus genuine notes."""
    visible = "TODO" if placeholder else "한글 논문 리뷰"
    shape = f'<p:sp><p:nvSpPr><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="{15000000 if outside else 0}" y="0"/><a:ext cx="1000000" cy="1000000"/></a:xfrm></p:spPr><p:txBody><a:p><a:r><a:t>{visible}</a:t></a:r></a:p></p:txBody></p:sp>'
    parts = {
        "[Content_Types].xml": '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        "_rels/.rels": f'<Relationships xmlns="{REL}"><Relationship Id="rId1" Type="{R}/officeDocument" Target="ppt/presentation.xml"/></Relationships>',
        "ppt/presentation.xml": f'<p:presentation xmlns:p="{P}" xmlns:r="{R}"><p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst><p:sldSz cx="12192000" cy="6858000"/></p:presentation>',
        "ppt/_rels/presentation.xml.rels": f'<Relationships xmlns="{REL}"><Relationship Id="rId1" Type="{R}/slide" Target="slides/slide1.xml"/></Relationships>',
        "ppt/slides/slide1.xml": f'<p:sld xmlns:p="{P}" xmlns:a="{A}"><p:cSld><p:spTree>{shape}</p:spTree></p:cSld></p:sld>',
    }
    if notes:
        target = "../notesSlides/missing.xml" if broken_target else "../notesSlides/notesSlide1.xml"
        parts["ppt/slides/_rels/slide1.xml.rels"] = f'<Relationships xmlns="{REL}"><Relationship Id="rId1" Type="{R}/notesSlide" Target="{target}"/></Relationships>'
        actual_notes = "논문의 핵심 문제와 실험 조건을 설명하고 결과를 원문과 대조합니다." if substantive_notes else ""
        parts["ppt/notesSlides/notesSlide1.xml"] = f'<p:notes xmlns:p="{P}" xmlns:a="{A}"><p:cSld><p:spTree><p:sp><p:nvSpPr><p:nvPr><p:ph type="sldNum"/></p:nvPr></p:nvSpPr><p:txBody><a:p><a:r><a:t>1</a:t></a:r></a:p></p:txBody></p:sp><p:sp><p:nvSpPr><p:nvPr><p:ph type="body"/></p:nvPr></p:nvSpPr><p:txBody><a:p><a:r><a:t>{actual_notes}</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:notes>'
    with zipfile.ZipFile(path, "w") as archive:
        for name, text in parts.items():
            archive.writestr(name, text)


class DeckQATests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pimp-qa-test-")
        self.directory = Path(self.temp.name)
        self.pptx = self.directory / "deck.pptx"

    def tearDown(self):
        self.temp.cleanup()

    def test_valid_korean_notes_and_evidence(self):
        fixture(self.pptx)
        manifest = self.directory / "deck_manifest.json"
        manifest.write_text(json.dumps({"version": 1, "mode": "normal", "slides": [{"index": 1, "title": "한글 논문 리뷰", "archetype": "resultSlide", "section": "Results", "notes": "충분한 발표자 설명", "sources": [{"page": 2, "kind": "paper", "label": "Table 1"}]}]}, ensure_ascii=False), encoding="utf-8")
        result = qa.check_deck(self.pptx, manifest, require_sources=True)
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["slide_count"], 1)
        self.assertGreater(result["slides"][0]["notes_chars"], 20)

    def test_missing_notes_fails_even_if_pptx_is_valid_zip(self):
        fixture(self.pptx, notes=False)
        result = qa.check_deck(self.pptx)
        self.assertFalse(result["ok"])
        self.assertIn("missing_notes", {error["code"] for error in result["errors"]})

    def test_automatic_slide_number_is_not_substantive_notes(self):
        fixture(self.pptx, substantive_notes=False)
        result = qa.check_deck(self.pptx)
        self.assertFalse(result["ok"])
        self.assertEqual(result["slides"][0]["notes_chars"], 0)
        self.assertIn("short_notes", {error["code"] for error in result["errors"]})

    def test_dangling_relationship_and_placeholder_fail(self):
        fixture(self.pptx, placeholder=True, broken_target=True)
        result = qa.check_deck(self.pptx)
        codes = {error["code"] for error in result["errors"]}
        self.assertFalse(result["ok"])
        self.assertTrue({"missing_target", "placeholder", "short_notes"}.issubset(codes))

    def test_missing_content_evidence_fails_when_required(self):
        fixture(self.pptx)
        manifest = self.directory / "manifest.json"
        manifest.write_text(json.dumps({"version": 1, "mode": "easy", "slides": [{"index": 1, "title": "문제", "archetype": "problemSlide", "section": "Problem", "notes": "발표 설명", "sources": []}]}), encoding="utf-8")
        result = qa.check_deck(self.pptx, manifest, require_sources=True)
        self.assertFalse(result["ok"])
        self.assertIn("missing_sources", {error["code"] for error in result["errors"]})

    def test_source_cannot_refer_past_end_of_paper(self):
        fixture(self.pptx)
        manifest = self.directory / "manifest.json"
        manifest.write_text(json.dumps({"version": 1, "mode": "normal", "paper_pages": 3, "slides": [{"index": 1, "title": "결과", "archetype": "statSlide", "section": "", "notes": "발표 설명", "sources": [{"kind": "paper", "page": 99, "label": "Table 1"}]}]}), encoding="utf-8")
        result = qa.check_deck(self.pptx, manifest)
        self.assertFalse(result["ok"])
        self.assertIn("source_page_out_of_range", {error["code"] for error in result["errors"]})

    def test_outside_content_requests_visual_review(self):
        fixture(self.pptx, outside=True)
        result = qa.check_deck(self.pptx)
        self.assertTrue(result["ok"])
        self.assertIn("out_of_bounds", {warning["code"] for warning in result["warnings"]})

    def test_fontconfig_is_private_and_escapes_paths(self):
        font_dir = self.directory / "fonts & custom"
        font_dir.mkdir()
        work = self.directory / "work"
        work.mkdir()
        config, family = renderer.prepare_fontconfig(work, [font_dir], [], "Custom Korean")
        tree = renderer.ET.parse(config)
        self.assertEqual(tree.find("dir").text, str(font_dir))
        self.assertEqual(tree.find("cachedir").text, str(work / "font-cache"))
        self.assertEqual(family, "Custom Korean")


if __name__ == "__main__":
    unittest.main()
