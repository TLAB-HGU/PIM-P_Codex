#!/usr/bin/env python3
"""Report PIM-P runtime dependencies without downloading or installing anything."""

from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


PYTHON_MODULES = (
    ("pdfplumber", "pdfplumber", True, "PDF text and layout extraction"),
    ("pypdf", "pypdf", True, "PDF page metadata and validation"),
    ("PIL", "Pillow", True, "Figure crops and image inspection"),
    ("matplotlib", "matplotlib", True, "Equation rendering"),
    ("yaml", "PyYAML", True, "Skill metadata validation"),
    ("reportlab", "reportlab", False, "Synthetic PDF fixtures for development tests"),
)


def _entry(name: str, kind: str, required: bool, available: bool, purpose: str, **details) -> dict:
    return {"name": name, "kind": kind, "required": required, "available": available, "purpose": purpose, **details}


def _python_checks() -> list[dict]:
    # A dependency probe should not attempt to populate a sandbox-unwritable
    # home cache. Respect an explicit user choice; otherwise use OS temp storage.
    os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "pimp-matplotlib"))
    checks = []
    for module_name, distribution, required, purpose in PYTHON_MODULES:
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            checks.append(_entry(distribution, "python", required, False, purpose, import_name=module_name, error=f"{type(exc).__name__}: {exc}"))
        else:
            checks.append(_entry(distribution, "python", required, True, purpose, import_name=module_name, version=str(getattr(module, "__version__", "unknown"))))
    return checks


def _executable(command: str, env_key: str, override: str | None = None) -> tuple[str | None, str]:
    configured = override or os.environ.get(env_key)
    if configured:
        configured = os.path.expanduser(configured)
        return shutil.which(configured), f"--{command}" if override else env_key
    return shutil.which(command), "PATH"


def _node_checks(skill_root: Path, override: str | None) -> list[dict]:
    node, source = _executable("node", "PIMP_NODE", override)
    node_check = _entry("node", "executable", True, bool(node), "PPTX generation", path=node, resolved_from=source)
    if not node:
        node_check["hint"] = "Put Node.js on PATH, or set PIMP_NODE to a Node executable returned by Codex load_workspace_dependencies."
        return [node_check, _entry("pptxgenjs", "node-package", True, False, "PPTX layout engine", error="Node.js is unavailable")]
    # require.resolve honors NODE_PATH, plus node_modules beside this installed
    # skill. Execute directly with an argument array; never invoke a shell.
    script = """const root = process.argv[1];
try {
  const resolved = require.resolve('pptxgenjs', { paths: [root, root + '/scripts'] });
  require(resolved);
  console.log(JSON.stringify({ available: true, path: resolved, node: process.version }));
} catch (error) {
  console.log(JSON.stringify({ available: false, error: error.message, node: process.version }));
}
"""
    try:
        result = subprocess.run([node, "-e", script, str(skill_root)], capture_output=True, text=True, timeout=20, check=False)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or f"Node exited with code {result.returncode}")
        info = json.loads(result.stdout.strip())
        node_check["version"] = info.get("node", "unknown")
        package = _entry("pptxgenjs", "node-package", True, bool(info.get("available")), "PPTX layout engine", node_path=os.environ.get("NODE_PATH", ""))
        for key in ("path", "error"):
            if key in info:
                package[key] = info[key]
        if not package["available"]:
            package["hint"] = f"Run npm install in {skill_root}, or set NODE_PATH to a runtime that already provides pptxgenjs."
        return [node_check, package]
    except (OSError, subprocess.TimeoutExpired, RuntimeError, json.JSONDecodeError) as exc:
        node_check["available"] = False
        node_check["error"] = f"Node execution failed: {exc}"
        return [node_check, _entry("pptxgenjs", "node-package", True, False, "PPTX layout engine", error="Node dependency probe could not complete")]


def _optional_tools() -> tuple[list[dict], list[str]]:
    checks = []
    warnings = []
    tools = (
        ("soffice", "PIMP_SOFFICE", "PPTX to PDF preview rendering"),
        ("pdftoppm", "PIMP_PDFTOPPM", "PDF to slide preview images"),
        ("tesseract", "PIMP_TESSERACT", "OCR for scanned paper pages"),
    )
    for command, env_key, purpose in tools:
        executable, source = _executable(command, env_key)
        check = _entry(command, "executable", False, bool(executable), purpose, path=executable, resolved_from=source)
        if command == "tesseract" and executable:
            try:
                result = subprocess.run([executable, "--list-langs"], capture_output=True, text=True, timeout=15, check=False)
                if result.returncode:
                    check["error"] = result.stderr.strip() or f"Language query exited with code {result.returncode}"
                    check["languages"] = []
                else:
                    lines = (result.stdout + "\n" + result.stderr).splitlines()
                    check["languages"] = sorted(line.strip() for line in lines if line.strip() and not line.strip().startswith("List of available languages"))
                if "eng" not in check["languages"]:
                    warnings.append("Tesseract English language data (eng) is unavailable; English OCR cannot be assumed.")
                if "kor" not in check["languages"]:
                    warnings.append("Tesseract Korean language data (kor) is unavailable; Korean OCR cannot be assumed.")
            except (OSError, subprocess.TimeoutExpired) as exc:
                check["error"] = str(exc)
                check["languages"] = []
                warnings.append("Tesseract is present, but its language data could not be checked.")
        checks.append(check)
    found = {check["name"]: check["available"] for check in checks}
    if not found["soffice"] or not found["pdftoppm"]:
        warnings.append("Local PPTX preview rendering is unavailable: both soffice and pdftoppm are needed. Use an available presentation renderer or PowerPoint, and report visual verification accurately.")
    if not found["tesseract"]:
        warnings.append("OCR is unavailable. Scanned PDFs need a configured OCR engine or a text version of the paper.")
    return checks, warnings


def diagnose(skill_root: Path | None = None, node: str | None = None) -> dict:
    skill_root = (skill_root or Path(__file__).resolve().parents[1]).expanduser().resolve()
    optional, warnings = _optional_tools()
    checks = _python_checks() + _node_checks(skill_root, node) + optional
    missing_required = [check["name"] for check in checks if check["required"] and not check["available"]]
    return {
        "schema_version": 1,
        "python": sys.executable,
        "skill_root": str(skill_root),
        "ready": not missing_required,
        "missing_required": missing_required,
        "checks": checks,
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print a structured dependency report")
    parser.add_argument("--strict", action="store_true", help="Exit 1 when required Python/Node components are unavailable; preview and OCR remain optional")
    parser.add_argument("--node", help="Node executable override (otherwise PIMP_NODE or PATH)")
    parser.add_argument("--skill-root", type=Path, help="Skill root for Node package resolution (default: this installed skill)")
    args = parser.parse_args(argv)
    report = diagnose(args.skill_root, args.node)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Python: {report['python']}")
        print(f"Skill: {report['skill_root']}")
        for check in report["checks"]:
            label = "OK" if check["available"] else "MISSING"
            necessity = "required" if check["required"] else "optional"
            detail = check.get("path") or check.get("version") or check.get("error", "")
            print(f"[{label}] {check['name']} ({necessity}): {detail}")
            if "languages" in check:
                print(f"  OCR languages: {', '.join(check['languages']) or 'none'}")
            if not check["available"] and check.get("hint"):
                print(f"  {check['hint']}")
        print("Required runtime: ready" if report["ready"] else "Required runtime: incomplete")
        for warning in report["warnings"]:
            print(f"Note: {warning}")
    return 1 if args.strict and not report["ready"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
