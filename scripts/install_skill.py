#!/usr/bin/env python3
"""Install the self-contained PIM-P skill without altering another installation."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
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
    candidate = destination.with_name(f"{destination.name}.backup-{stamp}")
    serial = 1
    while _exists(candidate):
        candidate = destination.with_name(f"{destination.name}.backup-{stamp}-{serial}")
        serial += 1
    return candidate


def install_skill(
    source: Path,
    target_dir: Path,
    *,
    link: bool = False,
    replace: bool = False,
    dry_run: bool = False,
) -> dict:
    """Install ``source`` below a parent skills directory and return the result.

    Existing destinations, including unrelated folders and broken symlinks, are
    never removed. ``replace`` moves them to a sibling backup first. A failed
    replacement restores the previous destination.
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
    backup = _backup_path(destination) if replacing else None
    result = {
        "source": str(source),
        "destination": str(destination),
        "mode": "link" if link else "copy",
        "dry_run": dry_run,
        "replacing": replacing,
        "backup": str(backup) if backup else None,
    }
    if dry_run:
        return result

    target_dir.mkdir(parents=True, exist_ok=True)
    stage_root = Path(tempfile.mkdtemp(prefix=f".{source.name}-install-", dir=target_dir))
    staged = stage_root / source.name
    moved_previous = False
    try:
        if link:
            staged.symlink_to(source, target_is_directory=True)
        else:
            shutil.copytree(
                source,
                staged,
                symlinks=True,
                ignore=shutil.ignore_patterns(".git", ".venv", "node_modules", "__pycache__", "*.pyc", "*.pyo", ".DS_Store", ".pytest_cache"),
            )
            (staged / ".pimp-install.json").write_text(
                json.dumps({"source": str(source), "installed_at": datetime.now(timezone.utc).isoformat(), "mode": "copy"}, indent=2) + "\n",
                encoding="utf-8",
            )
        if backup:
            destination.rename(backup)
            moved_previous = True
        elif _exists(destination):
            raise InstallError(f"Destination appeared during installation and was preserved: {destination}")
        try:
            staged.rename(destination)
        except BaseException:
            if moved_previous:
                backup.rename(destination)
            raise
    finally:
        shutil.rmtree(stage_root)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1] / "skills" / "pimp", help="Skill folder (default: repository skills/pimp)")
    parser.add_argument("--target-dir", type=Path, default=default_target_dir(), help="Parent skills directory; the skill folder is created inside it")
    parser.add_argument("--link", action="store_true", help="Symlink to the source so local edits become available immediately")
    parser.add_argument("--replace", action="store_true", help="Replace an existing destination after preserving it as a sibling backup")
    parser.add_argument("--dry-run", action="store_true", help="Validate and show the installation plan without writing anything")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable installation result")
    args = parser.parse_args(argv)
    try:
        result = install_skill(args.source, args.target_dir, link=args.link, replace=args.replace, dry_run=args.dry_run)
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
            print("Start a new Codex chat to discover $pimp. Install the skill's runtime dependencies before generating slides.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
