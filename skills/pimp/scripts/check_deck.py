#!/usr/bin/env python3
"""Check PPTX package integrity, speaker notes, placeholders and evidence manifest.

This checker verifies structure and provenance declarations. It cannot decide
whether a paper actually supports a claim or whether a slide looks good.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import posixpath
import re
import sys
from urllib.parse import unquote
import xml.etree.ElementTree as ET
import zipfile


NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}
PLACEHOLDER = re.compile(r"\b(?:TODO|TBD|LOREM\s+IPSUM|PLACEHOLDER)\b|\[(?:insert|add|replace|여기에|입력)[^\]]*\]", re.IGNORECASE)
NONCONTENT = {"titleSlide", "agendaSlide", "sectionSlide", "thankYouSlide", "referencesSlide", "title", "agenda", "section", "divider", "thankyou", "thanks", "references"}


def substantive(text: str) -> int:
    return sum(char.isalnum() for char in text)


def rels_path(part: str) -> str:
    directory, basename = posixpath.split(part)
    return posixpath.join(directory, "_rels", basename + ".rels")


def target_part(part: str, target: str) -> str:
    if target.startswith("/"):
        return unquote(target.lstrip("/"))
    return posixpath.normpath(posixpath.join(posixpath.dirname(part), unquote(target)))


def slide_text(root: ET.Element) -> str:
    return "\n".join(element.text or "" for element in root.findall(".//a:t", NS))


def note_text(root: ET.Element) -> str:
    values = []
    for shape in root.findall(".//p:sp", NS):
        placeholder = shape.find("p:nvSpPr/p:nvPr/p:ph", NS)
        if placeholder is not None and placeholder.get("type") in {"sldNum", "sldImg", "dt", "hdr", "ftr"}:
            continue
        values.extend(element.text or "" for element in shape.findall(".//a:t", NS))
    return "\n".join(values)


def check_deck(pptx: Path | str, manifest: Path | str | None = None, require_sources: bool = False, min_notes_chars: int = 20) -> dict:
    source = Path(pptx).expanduser().resolve()
    report = {
        "ok": False, "pptx": str(source), "slide_count": 0, "slides": [], "errors": [], "warnings": [],
        "scope": "Validates package structure, substantive speaker notes, placeholders and declared evidence. Source links do not prove claim accuracy. Render and review every slide.",
    }
    errors, warnings = report["errors"], report["warnings"]

    def error(code: str, message: str, slide: int | None = None) -> None:
        errors.append({"code": code, "message": message, **({"slide": slide} if slide else {})})

    if not source.is_file():
        error("missing_file", "PPTX file does not exist")
        return report
    try:
        archive = zipfile.ZipFile(source)
    except (OSError, zipfile.BadZipFile) as exc:
        error("invalid_zip", str(exc))
        return report
    with archive:
        names = set(archive.namelist())
        duplicate_names = len(archive.namelist()) - len(names)
        if duplicate_names:
            error("duplicate_parts", f"Package has {duplicate_names} duplicate entries")
        bad_crc = archive.testzip()
        if bad_crc:
            error("invalid_crc", f"Corrupt package part: {bad_crc}")
        for required in ("[Content_Types].xml", "_rels/.rels", "ppt/presentation.xml", "ppt/_rels/presentation.xml.rels"):
            if required not in names:
                error("missing_part", f"Missing required package part: {required}")
        parsed = {}
        for name in names:
            if name.endswith((".xml", ".rels")):
                try:
                    parsed[name] = ET.fromstring(archive.read(name))
                except (ET.ParseError, OSError, zipfile.BadZipFile) as exc:
                    error("invalid_xml", f"{name}: {exc}")
        relationships = {}
        for name, root in parsed.items():
            if not name.endswith(".rels"):
                continue
            if name == "_rels/.rels":
                part = ""
            else:
                directory, filename = posixpath.split(name)
                part = posixpath.join(posixpath.dirname(directory), filename[:-5])
            records = []
            ids = set()
            for relationship in root:
                rid, target, kind = relationship.get("Id"), relationship.get("Target"), relationship.get("Type", "")
                if not rid or rid in ids or not target:
                    error("invalid_relationship", f"Malformed or duplicate relationship in {name}")
                    continue
                ids.add(rid)
                external = relationship.get("TargetMode") == "External"
                resolved = target if external else target_part(part, target)
                records.append({"id": rid, "target": resolved, "type": kind, "external": external})
                if not external and resolved not in names:
                    error("missing_target", f"{part or 'package'} refers to missing part {resolved}")
            relationships[part] = records
        presentation = parsed.get("ppt/presentation.xml")
        if presentation is None:
            return report
        presentation_rels = {item["id"]: item for item in relationships.get("ppt/presentation.xml", [])}
        slide_parts = []
        for entry in presentation.findall("p:sldIdLst/p:sldId", NS):
            rid = entry.get(f"{{{NS['r']}}}id")
            relationship = presentation_rels.get(rid)
            if not relationship or not relationship["type"].endswith("/slide"):
                error("invalid_slide_relationship", f"Unresolvable presentation slide id: {rid}")
            else:
                slide_parts.append(relationship["target"])
        report["slide_count"] = len(slide_parts)
        if not slide_parts:
            error("empty_deck", "Presentation contains no slides")
        size = presentation.find("p:sldSz", NS)
        try:
            width, height = (int(size.get("cx", "0")), int(size.get("cy", "0"))) if size is not None else (0, 0)
        except ValueError:
            width, height = 0, 0
        if width <= 0 or height <= 0:
            error("invalid_slide_size", "Missing or invalid slide canvas dimensions")
        for index, part in enumerate(slide_parts, 1):
            root = parsed.get(part)
            if root is None:
                continue
            text = slide_text(root)
            if PLACEHOLDER.search(text):
                error("placeholder", "Slide contains TODO/TBD/placeholder text", index)
            notes_rels = [item for item in relationships.get(part, []) if item["type"].endswith("/notesSlide")]
            notes = ""
            if len(notes_rels) != 1:
                error("missing_notes", "Slide must have exactly one speaker-notes part", index)
            else:
                note_root = parsed.get(notes_rels[0]["target"])
                if note_root is not None:
                    notes = note_text(note_root)
                if substantive(notes) < min_notes_chars:
                    error("short_notes", f"Speaker notes need at least {min_notes_chars} letters/numbers; found {substantive(notes)}", index)
                if PLACEHOLDER.search(notes):
                    error("placeholder_notes", "Speaker notes contain placeholder text", index)
            overflow = []
            # Check top-level content geometry only. Group/rotated transforms need
            # renderer review; decorative shapes can intentionally cross edges.
            tree = root.find("p:cSld/p:spTree", NS)
            if tree is not None and width and height:
                for shape in tree:
                    if shape.tag not in {f"{{{NS['p']}}}sp", f"{{{NS['p']}}}pic", f"{{{NS['p']}}}graphicFrame"}:
                        continue
                    transform = shape.find("p:spPr/a:xfrm", NS)
                    if transform is None:
                        transform = shape.find("p:xfrm", NS)
                    if transform is None or transform.get("rot") not in {None, "0"}:
                        continue
                    offset, extent = transform.find("a:off", NS), transform.find("a:ext", NS)
                    if offset is None or extent is None:
                        continue
                    try:
                        x, y, w, h = [int(value) for value in (offset.get("x"), offset.get("y"), extent.get("cx"), extent.get("cy"))]
                    except (TypeError, ValueError):
                        error("invalid_geometry", "Shape contains nonnumeric coordinates", index)
                        continue
                    # Plain decorative geometry is excluded, but text boxes,
                    # pictures and charts outside the canvas are review warnings.
                    has_content = bool(shape.findall(".//a:t", NS)) or shape.tag != f"{{{NS['p']}}}sp"
                    tolerance = 9144  # 0.01 inch rounding tolerance
                    if has_content and (x < -tolerance or y < -tolerance or x + w > width + tolerance or y + h > height + tolerance):
                        overflow.append({"x": x, "y": y, "width": w, "height": h})
            if overflow:
                warnings.append({"code": "out_of_bounds", "slide": index, "message": "Content crosses slide edges; inspect the rendered slide", "objects": overflow})
            report["slides"].append({"index": index, "part": part, "notes_chars": substantive(notes), "text_chars": substantive(text)})

    if manifest is not None:
        manifest_path = Path(manifest).expanduser().resolve()
        report["manifest"] = str(manifest_path)
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            error("invalid_manifest", str(exc))
            data = None
        if data is not None:
            if not isinstance(data, dict) or data.get("version") != 1 or data.get("mode") not in {"normal", "easy"} or not isinstance(data.get("slides"), list):
                error("invalid_manifest", "Expected version:1, mode:normal|easy and slides array")
            else:
                entries = data["slides"]
                paper_pages = data.get("paper_pages")
                if paper_pages is not None and (type(paper_pages) is not int or paper_pages < 1):
                    error("invalid_paper_pages", "Manifest paper_pages must be a positive integer when provided")
                    paper_pages = None
                if len(entries) != report["slide_count"]:
                    error("manifest_slide_count", "Manifest slide count differs from PPTX")
                for expected_index, entry in enumerate(entries, 1):
                    if not isinstance(entry, dict):
                        error("invalid_manifest_slide", "Slide entry must be an object", expected_index)
                        continue
                    if entry.get("index") != expected_index:
                        error("manifest_slide_index", "Manifest indices must match PPTX order, starting at 1", expected_index)
                    for field in ("title", "archetype", "notes"):
                        if not isinstance(entry.get(field), str) or not entry[field].strip():
                            error("manifest_field", f"Manifest slide needs nonempty {field}", expected_index)
                    if not isinstance(entry.get("section"), str):
                        error("manifest_field", "Manifest slide section must be a string", expected_index)
                    sources = entry.get("sources", [])
                    if not isinstance(sources, list):
                        error("invalid_sources", "sources must be an array", expected_index)
                        continue
                    if require_sources and not sources and entry.get("archetype") not in NONCONTENT:
                        error("missing_sources", "Content slide requires at least one declared source", expected_index)
                    for source_entry in sources:
                        if not isinstance(source_entry, dict) or source_entry.get("kind") not in {"paper", "reviewer"} or not isinstance(source_entry.get("label"), str) or not source_entry["label"].strip():
                            error("invalid_source", "Source needs kind:paper|reviewer and a nonempty label", expected_index)
                            continue
                        page = source_entry.get("page")
                        if type(page) is not int or page < 1:
                            error("invalid_source_page", "Paper and reviewer sources need a positive 1-based PDF page", expected_index)
                        if type(page) is int and paper_pages and page > paper_pages:
                            error("source_page_out_of_range", f"Source page {page} exceeds paper_pages={paper_pages}", expected_index)
                        if source_entry.get("file"):
                            asset = Path(source_entry["file"])
                            if not asset.is_absolute():
                                asset = manifest_path.parent / asset
                            if not asset.is_file():
                                error("missing_source_file", f"Source file does not exist: {asset}", expected_index)
    elif require_sources:
        error("missing_manifest", "--require-sources needs --manifest")
    report["ok"] = not errors
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pptx")
    parser.add_argument("--manifest")
    parser.add_argument("--require-sources", action="store_true", help="Require a declared source for each content slide")
    parser.add_argument("--min-notes-chars", type=int, default=20)
    parser.add_argument("--report", help="Write the JSON report to this path")
    args = parser.parse_args()
    if args.min_notes_chars < 1:
        parser.error("--min-notes-chars must be positive")
    result = check_deck(args.pptx, args.manifest, args.require_sources, args.min_notes_chars)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        report_path = Path(args.report).expanduser().resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
