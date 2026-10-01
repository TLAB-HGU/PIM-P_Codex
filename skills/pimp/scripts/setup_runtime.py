#!/usr/bin/env python3
r"""Prepare this skill's local Python/Node packages, or verify them offline.

Run with Python 3.10+: python3 <skill>/scripts/setup_runtime.py
On Windows: py -3 <skill>\scripts\setup_runtime.py
Python, Node.js and npm must already be installed. No runtime or OS package is
installed, and pip always runs inside the skill's own virtual environment.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


SCHEMA_VERSION = 1
RUNTIME_MARKER = ".pimp-runtime.json"
OWNER_MARKER = ".pimp-owner.json"
DEPENDENCY_FILES = ("requirements.txt", "package.json", "package-lock.json")


class RuntimeSetupError(RuntimeError):
    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage


def _result(root: Path, check: bool = False) -> dict:
    return {"schema_version": SCHEMA_VERSION, "ok": False, "status": "error", "stage": "preflight", "skill_root": str(root), "check": check}


def _failure(result: dict, exc: Exception) -> dict:
    result.update(ok=False, status="error", stage=getattr(exc, "stage", result["stage"]), error=str(exc))
    return result


def _read_json(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def _write_json_atomic(path: Path, data: dict) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=f".{path.name}-", suffix=".tmp", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def _dependency_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for name in DEPENDENCY_FILES:
        path = root / name
        if not path.is_file():
            raise RuntimeSetupError("preflight", f"Missing dependency file: {path}")
        data = path.read_bytes()
        digest.update(name.encode("utf-8") + b"\0" + str(len(data)).encode("ascii") + b"\0" + data)
    return digest.hexdigest()


def _locate(name: str, requested: str | None = None) -> Path:
    candidate = os.path.expanduser(requested) if requested else name
    located = shutil.which(candidate)
    path = Path(located or candidate)
    if not located and (not requested or not path.is_file()):
        raise RuntimeSetupError("preflight", f"{name} is unavailable. Install it separately or provide --{name} with its executable path.")
    return path.resolve()


def _process_env(node: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = str(node.parent) + os.pathsep + env.get("PATH", "")
    env["PIMP_NODE"] = str(node)
    # These variables can redirect Python imports or installation outside .venv.
    for key in ("PYTHONHOME", "PYTHONPATH", "PIP_TARGET", "PIP_PREFIX", "PIP_USER"):
        env.pop(key, None)
    return env


def _run(command: list[str], stage: str, root: Path, env: dict, timeout: float, *, allow_failure: bool = False):
    try:
        completed = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeSetupError(stage, f"{stage} timed out after {timeout:g} seconds.") from exc
    except OSError as exc:
        raise RuntimeSetupError(stage, f"Cannot run {command[0]}: {exc}") from exc
    if completed.returncode and not allow_failure:
        detail = (completed.stderr.strip() or completed.stdout.strip())[-4000:]
        raise RuntimeSetupError(stage, f"{stage} failed (exit {completed.returncode}): {detail}")
    return completed


def _npm_command(node: Path, npm: Path) -> list[str]:
    """Run npm's JS entry point with the selected Node, including Windows."""
    if npm.suffix.lower() in (".cmd", ".bat"):
        candidates = [npm.parent / "node_modules" / "npm" / "bin" / "npm-cli.js", node.parent / "node_modules" / "npm" / "bin" / "npm-cli.js"]
        cli = next((path for path in candidates if path.is_file()), None)
        if cli is None:
            raise RuntimeSetupError("preflight", f"Found Windows npm launcher {npm}, but npm-cli.js is missing. Provide --npm with the npm-cli.js path from that Node installation.")
        return [str(node), str(cli.resolve())]
    if npm.suffix.lower() == ".js":
        return [str(node), str(npm)]
    try:
        with npm.open("rb") as stream:
            first_line = stream.readline(512)
    except OSError:
        first_line = b""
    if first_line.startswith(b"#!") and b"node" in first_line:
        return [str(node), str(npm)]
    return [str(npm)]


def _select_npm(node: Path, requested: str | None) -> Path:
    requested = requested or os.environ.get("PIMP_NPM")
    if requested:
        return _locate("npm", requested)
    for name in ("npm.cmd", "npm") if os.name == "nt" else ("npm", "npm.cmd"):
        candidate = node.parent / name
        if candidate.is_file():
            return candidate.resolve()
    return _locate("npm")


def _venv_python(root: Path) -> Path:
    return root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _matching_identity(marker: dict | None, root: Path) -> bool:
    return bool(marker and marker.get("schema_version") == SCHEMA_VERSION and marker.get("skill_root") == str(root))


def _check_existing_env(root: Path) -> None:
    venv = root / ".venv"
    if not os.path.lexists(venv):
        return
    if venv.is_symlink() or not venv.is_dir():
        raise RuntimeSetupError("preflight", f"Refusing nonlocal .venv: {venv}. Move it aside, then rerun setup at this final skill location.")
    owner = _read_json(venv / OWNER_MARKER)
    marker = _read_json(root / RUNTIME_MARKER)
    if owner is not None and not _matching_identity(owner, root):
        raise RuntimeSetupError("preflight", f"This .venv was created at another location and cannot be relocated: {venv}. Move it aside, then rerun setup here.")
    if not _matching_identity(owner, root) and not _matching_identity(marker, root):
        raise RuntimeSetupError("preflight", f"Refusing an unmarked or copied .venv: {venv}. Move that directory aside, then rerun setup to create a local environment here.")
    if not _venv_python(root).is_file():
        raise RuntimeSetupError("preflight", f"The owned .venv is incomplete: {_venv_python(root)} is missing. Move .venv aside, then rerun setup.")


def _preflight(root: Path, node: str | None, npm: str | None, timeout: float, *, need_npm: bool, check_environment: bool = True) -> dict:
    if not math.isfinite(timeout) or timeout <= 0:
        raise RuntimeSetupError("preflight", "--timeout must be a positive finite number of seconds.")
    if sys.version_info[:2] < (3, 10):
        raise RuntimeSetupError("preflight", "Python 3.10 or newer is required. Rerun this script with a supported Python (Windows: py -3).")
    if not root.is_dir() or not (root / "scripts" / "doctor.py").is_file():
        raise RuntimeSetupError("preflight", f"Not a complete PIM-P skill folder: {root}")
    digest = _dependency_digest(root)
    selected_node = _locate("node", node or os.environ.get("PIMP_NODE"))
    env = _process_env(selected_node)
    version = _run([str(selected_node), "--version"], "preflight", root, env, timeout).stdout.strip()
    match = re.fullmatch(r"v?(\d+)\.\d+\.\d+(?:[-+][\w.-]+)?", version)
    if not match or int(match.group(1)) < 20:
        raise RuntimeSetupError("preflight", f"Node.js >=20 is required; selected {selected_node} reported {version!r}.")
    info = {"bootstrap_python": sys.executable, "python": str(_venv_python(root)), "node": str(selected_node), "node_version": version, "digest": digest}
    if need_npm:
        selected_npm = _select_npm(selected_node, npm)
        npm_command = _npm_command(selected_node, selected_npm)
        npm_version = _run(npm_command + ["--version"], "preflight", root, env, timeout).stdout.strip()
        if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][\w.-]+)?", npm_version):
            raise RuntimeSetupError("preflight", f"The selected npm did not report a valid version: {npm_version!r}")
        info.update(npm=str(selected_npm), npm_version=npm_version, npm_command=npm_command)
    if check_environment:
        _check_existing_env(root)
    return info


def preflight(skill_root, node=None, npm=None, timeout=300, *, check_environment=False) -> dict:
    """Read-only prerequisites before copying; source .venv is excluded by default.

    Set ``check_environment=True`` when validating this exact final skill
    location. ``setup_runtime`` always checks the final environment's ownership.
    """
    root = Path(skill_root).expanduser().resolve()
    result = _result(root)
    try:
        result.update(_preflight(root, node, npm, timeout, need_npm=True, check_environment=check_environment))
        result.update(ok=True, status="prerequisites_ready")
    except (RuntimeSetupError, OSError, ValueError, TypeError) as exc:
        _failure(result, exc)
    return result


def _verify_venv(root: Path, node: Path, timeout: float) -> None:
    probe = "import json,sys; print(json.dumps({'prefix':sys.prefix,'base_prefix':sys.base_prefix,'version':list(sys.version_info[:2])}))"
    output = _run([str(_venv_python(root)), "-I", "-c", probe], "venv", root, _process_env(node), timeout).stdout
    try:
        info = json.loads(output)
        local = Path(info["prefix"]).resolve() == (root / ".venv").resolve()
        isolated = info["prefix"] != info["base_prefix"]
        supported = tuple(info["version"]) >= (3, 10)
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeSetupError("venv", "Could not verify the local Python virtual environment.") from exc
    if not local or not isolated or not supported:
        raise RuntimeSetupError("venv", "The selected .venv Python is not an isolated Python >=3.10 environment at this skill's final location. Move .venv aside and rerun setup.")


def _doctor(root: Path, node: Path, timeout: float) -> tuple[dict, int]:
    command = [str(_venv_python(root)), "-I", str(root / "scripts" / "doctor.py"), "--strict", "--json", "--node", str(node), "--skill-root", str(root)]
    completed = _run(command, "doctor", root, _process_env(node), timeout, allow_failure=True)
    try:
        report = json.loads(completed.stdout)
        if not isinstance(report, dict) or report.get("schema_version") != 1 or not isinstance(report.get("ready"), bool):
            raise ValueError("invalid doctor schema")
    except ValueError as exc:
        detail = (completed.stderr.strip() or completed.stdout.strip())[-2000:]
        raise RuntimeSetupError("doctor", f"Doctor did not return a valid JSON report: {detail}") from exc
    return report, completed.returncode


def setup_runtime(skill_root, node=None, npm=None, timeout=300, *, check=False) -> dict:
    """Set up local packages or check an existing runtime, returning its status.

    Expected operational failures return ``ok=False`` and never claim a stale
    success marker is current. ``check=True`` performs no package installation
    and does not create, update, or delete the runtime/ownership markers.
    """
    root = Path(skill_root).expanduser().resolve()
    result = _result(root, check)
    try:
        if check and not node and not os.environ.get("PIMP_NODE"):
            stored = _read_json(root / RUNTIME_MARKER)
            if _matching_identity(stored, root):
                node = stored.get("node")
        result.update(_preflight(root, node, npm, timeout, need_npm=not check))
        selected_node = Path(result["node"])
        marker_path = root / RUNTIME_MARKER
        if check:
            marker = _read_json(marker_path)
            if not _matching_identity(marker, root) or not marker.get("ok"):
                raise RuntimeSetupError("check", "No successful runtime marker for this skill location. Run setup here; copied virtual environments cannot be relocated.")
            if not _venv_python(root).is_file():
                raise RuntimeSetupError("check", "The local .venv Python is missing. Run setup at this skill location.")
            _verify_venv(root, selected_node, timeout)
            report, exit_code = _doctor(root, selected_node, timeout)
            result["doctor"] = report
            if exit_code or not report["ready"]:
                raise RuntimeSetupError("doctor", "Required runtime dependencies are unavailable. Rerun setup; see the doctor report.")
            if marker.get("digest") != result["digest"]:
                result.update(ok=False, status="stale", stage="check", error="Dependency files changed since setup. Rerun setup to update local packages.")
                return result
            result.update(ok=True, status="ready", stage="check", npm=marker.get("npm"), npm_version=marker.get("npm_version"))
            return result

        # Only a complete executable/version preflight allows writes. Readiness
        # is invalidated before package updates so a failure cannot leave a
        # misleading previous success marker. Ownership alone means no success.
        if os.path.lexists(marker_path):
            marker_path.unlink()
        venv = root / ".venv"
        if not venv.exists():
            result["stage"] = "venv"
            _run([sys.executable, "-I", "-m", "venv", str(venv)], "venv", root, _process_env(selected_node), timeout)
            _write_json_atomic(venv / OWNER_MARKER, {"schema_version": SCHEMA_VERSION, "skill_root": str(root), "bootstrap_python": sys.executable})
        _verify_venv(root, selected_node, timeout)
        if not (venv / OWNER_MARKER).is_file():
            _write_json_atomic(venv / OWNER_MARKER, {"schema_version": SCHEMA_VERSION, "skill_root": str(root), "bootstrap_python": sys.executable})
        install_env = _process_env(selected_node)
        # --isolated still reads global/site config and PIP_CONFIG_FILE.
        # Disable every pip config file so target/prefix cannot escape .venv.
        install_env["PIP_CONFIG_FILE"] = os.devnull
        install_env["npm_config_cache"] = str(root / ".cache" / "npm")
        result["stage"] = "pip"
        # Ignore pip environment options as well; the executable is verified
        # as a venv and all package/cache destinations remain skill-local.
        _run([str(_venv_python(root)), "-I", "-m", "pip", "--isolated", "--cache-dir", str(root / ".cache" / "pip"), "install", "-r", str(root / "requirements.txt")], "pip", root, install_env, timeout)
        result["stage"] = "npm"
        _run(result["npm_command"] + ["ci", "--prefix", str(root), "--ignore-scripts", "--no-audit", "--no-fund"], "npm", root, install_env, timeout)
        result["stage"] = "doctor"
        report, exit_code = _doctor(root, selected_node, timeout)
        result["doctor"] = report
        if exit_code or not report["ready"]:
            raise RuntimeSetupError("doctor", "Required runtime validation failed. Local packages may be incomplete; see the doctor report and rerun setup.")
        # Do not label packages as current if manifests changed during install.
        if _dependency_digest(root) != result["digest"]:
            raise RuntimeSetupError("doctor", "Dependency files changed during setup. Rerun setup with the current files.")
        result.update(ok=True, status="ready", stage="complete", configured_at=datetime.now(timezone.utc).isoformat())
        result.pop("npm_command", None)
        _write_json_atomic(marker_path, result)
        return result
    except (RuntimeSetupError, OSError, ValueError, TypeError) as exc:
        result.pop("npm_command", None)
        return _failure(result, exc)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", help="Existing Node executable (otherwise PIMP_NODE or PATH)")
    parser.add_argument("--npm", help="Existing npm executable or npm-cli.js (otherwise PIMP_NPM, Node sibling or PATH)")
    parser.add_argument("--json", action="store_true", help="Print a structured status report")
    parser.add_argument("--timeout", type=float, default=300, help="Maximum seconds for each subprocess (default: 300)")
    parser.add_argument("--check", action="store_true", help="Verify existing runtime and dependency-file freshness offline; do not install packages")
    args = parser.parse_args(argv)
    report = setup_runtime(Path(__file__).resolve().parents[1], args.node, args.npm, args.timeout, check=args.check)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif report["ok"]:
        print(f"Local runtime ready: {report['skill_root']}")
        print(f"Python: {report['python']}")
        print(f"Node: {report['node']}")
        for warning in report["doctor"].get("warnings", []):
            print(f"Note: {warning}")
    else:
        print(f"Runtime {report['stage']} failed: {report['error']}", file=sys.stderr)
        print("No runtime download or global/OS installation was attempted.", file=sys.stderr)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
