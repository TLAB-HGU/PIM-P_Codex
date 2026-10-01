#!/usr/bin/env python3
"""Install the self-contained PIM-P skill without altering another installation."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile


class InstallError(RuntimeError):
    """An installation could not be completed safely."""


def default_target_dir() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    return Path(codex_home).expanduser() / "skills" if codex_home else Path.home() / ".codex" / "skills"


def _exists(path: Path) -> bool:
    # A broken symlink is still an existing installation and must be preserved.
    return os.path.lexists(path)


def _backup_path(destination: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    parent = destination.parent
    discovery_root = next((p for p in (parent, *parent.parents) if p.name == "skills" and p.parent.name in {".agents", ".codex"}), parent)
    backup_root = discovery_root.parent / ".pimp-skill-backups"
    candidate = backup_root / f"{destination.name}-{stamp}"
    serial = 1
    while _exists(candidate):
        candidate = backup_root / f"{destination.name}-{stamp}-{serial}"
        serial += 1
    return candidate


def _runtime_helper(source: Path):
    path = source / "scripts" / "setup_runtime.py"
    if not path.is_file():
        raise InstallError(f"Runtime setup helper is missing: {path}")
    spec = importlib.util.spec_from_file_location("pimp_runtime_install", path)
    module = importlib.util.module_from_spec(spec)
    # Keep --dry-run/preflight from populating source __pycache__.
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


def install_skill(
    source: Path,
    target_dir: Path,
    *,
    link: bool = False,
    replace: bool = False,
    dry_run: bool = False,
    setup: bool = False,
    node: str | None = None,
    npm: str | None = None,
    timeout: float = 300,
) -> dict:
    """Install ``source`` below a parent skills directory and return the result.

    Existing destinations, including unrelated folders and broken symlinks, are
    never removed. ``replace`` moves them outside the skill discovery directory.
    A failed copy or runtime setup restores the previous destination.
    """
    source = source.expanduser().resolve()
    target_dir = target_dir.expanduser().resolve()
    if not source.is_dir():
        raise InstallError(f"Skill source is not a directory: {source}")
    missing = [name for name in ("SKILL.md", "LICENSE", "UPSTREAM.md") if not (source / name).is_file()]
    if missing:
        raise InstallError(f"Skill source is missing required package files: {', '.join(missing)}")
    destination = target_dir / source.name
    # resolve(strict=False) would follow an existing destination symlink and
    # obscure the path that is actually being replaced. Inspect the parent only.
    if destination == source or source in destination.parents or destination in source.parents:
        raise InstallError("Source and destination must not overlap.")
    replacing = _exists(destination)
    if replacing and not replace:
        raise InstallError(f"Destination already exists: {destination}. Use --replace to preserve it as a backup and install again.")
    if target_dir.exists() and not target_dir.is_dir():
        raise InstallError(f"Target parent is not a directory: {target_dir}")
    if setup and link:
        raise InstallError("--setup requires a copy installation. For a development link, run scripts/setup_runtime.py in the source skill separately.")
    if timeout <= 0:
        raise InstallError("timeout must be positive")
    helper = _runtime_helper(source) if setup else None
    if helper:
        preflight = helper.preflight(source, node=node, npm=npm, timeout=timeout)
        if not preflight.get("ok"):
            raise InstallError(preflight.get("error", "Runtime prerequisites are incomplete"))
    backup = _backup_path(destination) if replacing else None
    result = {
        "source": str(source),
        "destination": str(destination),
        "mode": "link" if link else "copy",
        "dry_run": dry_run,
        "replacing": replacing,
        "backup": str(backup) if backup else None,
        "setup": setup,
    }
    if dry_run:
        return result

    target_dir.mkdir(parents=True, exist_ok=True)
    stage_root = Path(tempfile.mkdtemp(prefix=f".{source.name}-install-", dir=target_dir))
    staged = stage_root / source.name
    moved_previous = False
    installed_new = False
    previous_link = os.readlink(destination) if destination.is_symlink() else None
    try:
        if link:
            staged.symlink_to(source, target_is_directory=True)
        else:
            shutil.copytree(
                source,
                staged,
                symlinks=True,
                ignore=shutil.ignore_patterns(".git", ".venv", "node_modules", ".cache", "__pycache__", "*.pyc", "*.pyo", ".DS_Store", ".pytest_cache", ".pimp-runtime*.json", ".pimp-install.json"),
            )
            (staged / ".pimp-install.json").write_text(
                json.dumps({"source": str(source), "installed_at": datetime.now(timezone.utc).isoformat(), "mode": "copy"}, indent=2) + "\n",
                encoding="utf-8",
            )
        try:
            if backup:
                backup.parent.mkdir(parents=True, exist_ok=True)
                destination.rename(backup)
                moved_previous = True
                if previous_link is not None and not os.path.isabs(previous_link):
                    # A relative link moved to another parent must retain its
                    # original effective target, including dangling targets.
                    absolute_target = os.path.abspath(destination.parent / previous_link)
                    adjusted = stage_root / "backup-link"
                    adjusted.symlink_to(absolute_target, target_is_directory=True)
                    os.replace(adjusted, backup)
            elif _exists(destination):
                raise InstallError(f"Destination appeared during installation and was preserved: {destination}")
            staged.rename(destination)
            installed_new = True
            if helper:
                runtime = helper.setup_runtime(destination, node=node, npm=npm, timeout=timeout)
                if not runtime.get("ok"):
                    raise InstallError(runtime.get("error", "Runtime setup failed"))
                result["runtime"] = runtime
        except BaseException:
            if installed_new:
                if destination.is_symlink() or not destination.is_dir():
                    destination.unlink()
                else:
                    shutil.rmtree(destination)
            if moved_previous:
                backup.rename(destination)
                if previous_link is not None and os.readlink(destination) != previous_link:
                    restored = stage_root / "restore-link"
                    restored.symlink_to(previous_link, target_is_directory=True)
                    os.replace(restored, destination)
            raise
    finally:
        shutil.rmtree(stage_root)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1] / "skills" / "pimp", help="Skill folder (default: repository skills/pimp)")
    parser.add_argument("--target-dir", type=Path, default=default_target_dir(), help="Parent skills directory; the skill folder is created inside it")
    parser.add_argument("--link", action="store_true", help="Symlink to the source so local edits become available immediately")
    parser.add_argument("--replace", action="store_true", help="Replace an existing destination after backing it up outside the skills directory")
    parser.add_argument("--setup", action="store_true", help="Prepare skill-local Python and Node dependencies after copying; restore the old install if setup fails")
    parser.add_argument("--node", help="Node executable for --setup (otherwise PIMP_NODE or PATH)")
    parser.add_argument("--npm", help="npm executable or CLI script for --setup")
    parser.add_argument("--timeout", type=float, default=300, help="Per-step runtime setup timeout in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Validate and show the installation plan without writing anything")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable installation result")
    args = parser.parse_args(argv)
    try:
        result = install_skill(args.source, args.target_dir, link=args.link, replace=args.replace, dry_run=args.dry_run, setup=args.setup, node=args.node, npm=args.npm, timeout=args.timeout)
    except (InstallError, OSError) as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        else:
            print(f"Installation failed: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        verb = "Would install" if args.dry_run else "Installed"
        print(f"{verb} {result['mode']}: {result['destination']}")
        if result["backup"]:
            prefix = "Would preserve" if args.dry_run else "Preserved"
            print(f"{prefix} previous installation: {result['backup']}")
        if not args.dry_run:
            print("PPTX runtime is ready." if args.setup else "Run the installed skill's scripts/setup_runtime.py to prepare its runtime.")
            print("Start a new Codex chat to discover $pimp.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
