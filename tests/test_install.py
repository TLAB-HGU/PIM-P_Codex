"""Installation tests use temporary directories and never modify real skills."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install_skill.py"
spec = importlib.util.spec_from_file_location("pimp_installer", INSTALL_SCRIPT)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)
DOCTOR_SCRIPT = REPO_ROOT / "skills" / "pimp" / "scripts" / "doctor.py"


class InstallSkillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pimp installation test ")
        self.root = Path(self.temp.name)
        self.source = self.root / "source with spaces" / "pimp"
        self.source.mkdir(parents=True)
        for filename in ("SKILL.md", "LICENSE", "UPSTREAM.md"):
            (self.source / filename).write_text(f"original {filename}\n", encoding="utf-8")
        (self.source / "scripts").mkdir()
        (self.source / "scripts" / "run.py").write_text("print('ready')\n", encoding="utf-8")
        self.target = self.root / "target with spaces" / "skills"

    def tearDown(self):
        self.temp.cleanup()

    def test_copy_is_self_contained_and_does_not_mutate_source(self):
        result = installer.install_skill(self.source, self.target)
        destination = Path(result["destination"])
        self.assertFalse(destination.is_symlink())
        for filename in ("SKILL.md", "LICENSE", "UPSTREAM.md", "scripts/run.py"):
            self.assertEqual((destination / filename).read_bytes(), (self.source / filename).read_bytes())
        self.assertTrue((destination / ".pimp-install.json").is_file())
        self.assertFalse((self.source / ".pimp-install.json").exists())
        (self.source / "SKILL.md").write_text("changed\n", encoding="utf-8")
        self.assertEqual((destination / "SKILL.md").read_text(encoding="utf-8"), "original SKILL.md\n")

    def test_generated_dependencies_and_caches_are_not_copied(self):
        for name in ("node_modules", ".venv", "__pycache__"):
            (self.source / name).mkdir()
            (self.source / name / "data").write_text("cache")
        destination = Path(installer.install_skill(self.source, self.target)["destination"])
        for name in ("node_modules", ".venv", "__pycache__"):
            self.assertFalse((destination / name).exists())

    def test_dry_run_does_not_create_parent_directory(self):
        result = installer.install_skill(self.source, self.target, dry_run=True)
        self.assertTrue(result["dry_run"])
        self.assertFalse(self.target.exists())

    def test_existing_unrelated_installation_is_refused(self):
        destination = self.target / "pimp"
        destination.mkdir(parents=True)
        (destination / "personal.txt").write_text("preserve me")
        with self.assertRaises(installer.InstallError):
            installer.install_skill(self.source, self.target)
        self.assertEqual((destination / "personal.txt").read_text(), "preserve me")

    def test_replace_preserves_entire_previous_installation(self):
        old = self.target / "pimp"
        old.mkdir(parents=True)
        (old / "personal.txt").write_text("preserve me")
        result = installer.install_skill(self.source, self.target, replace=True)
        backup = Path(result["backup"])
        self.assertEqual((backup / "personal.txt").read_text(), "preserve me")
        self.assertTrue((old / "SKILL.md").is_file())
        self.assertFalse((old / "personal.txt").exists())

    def test_replace_dry_run_does_not_move_old_installation(self):
        old = self.target / "pimp"
        old.mkdir(parents=True)
        (old / "personal.txt").write_text("preserve me")
        result = installer.install_skill(self.source, self.target, replace=True, dry_run=True)
        self.assertFalse(Path(result["backup"]).exists())
        self.assertEqual((old / "personal.txt").read_text(), "preserve me")

    def test_link_tracks_source_changes(self):
        result = installer.install_skill(self.source, self.target, link=True)
        destination = Path(result["destination"])
        self.assertTrue(destination.is_symlink())
        self.assertEqual(destination.resolve(), self.source.resolve())
        (self.source / "SKILL.md").write_text("updated")
        self.assertEqual((destination / "SKILL.md").read_text(), "updated")

    def test_broken_symlink_is_preserved_when_replaced(self):
        self.target.mkdir(parents=True)
        old = self.target / "pimp"
        dangling = self.root / "missing skill"
        old.symlink_to(dangling, target_is_directory=True)
        with self.assertRaises(installer.InstallError):
            installer.install_skill(self.source, self.target)
        result = installer.install_skill(self.source, self.target, replace=True)
        backup = Path(result["backup"])
        self.assertTrue(backup.is_symlink())
        self.assertEqual(os.readlink(backup), str(dangling))

    def test_failed_replacement_rolls_back_previous_installation(self):
        old = self.target / "pimp"
        old.mkdir(parents=True)
        (old / "personal.txt").write_text("preserve me")
        real_rename = Path.rename

        def fail_staged_rename(path, target):
            if path.parent.name.startswith(".pimp-install-"):
                raise OSError("simulated final rename failure")
            return real_rename(path, target)

        with mock.patch.object(Path, "rename", fail_staged_rename):
            with self.assertRaisesRegex(OSError, "simulated"):
                installer.install_skill(self.source, self.target, replace=True)
        self.assertEqual((old / "personal.txt").read_text(), "preserve me")
        self.assertEqual(sorted(path.name for path in self.target.iterdir()), ["pimp"])

    def test_missing_license_is_refused_before_writing(self):
        (self.source / "LICENSE").unlink()
        with self.assertRaisesRegex(installer.InstallError, "LICENSE"):
            installer.install_skill(self.source, self.target)
        self.assertFalse(self.target.exists())

    def test_overlapping_paths_are_refused(self):
        with self.assertRaisesRegex(installer.InstallError, "overlap"):
            installer.install_skill(self.source, self.source / "nested")
        with self.assertRaisesRegex(installer.InstallError, "overlap"):
            installer.install_skill(self.source, self.source.parent)

    def test_cli_paths_are_literals_and_json_is_parseable(self):
        # Characters significant to a shell remain plain filesystem names.
        special_target = self.root / "skills $(touch injected) `touch injected2`"
        result = subprocess.run(
            [sys.executable, str(INSTALL_SCRIPT), "--source", str(self.source), "--target-dir", str(special_target), "--json"],
            capture_output=True, text=True, check=True, cwd=self.root,
        )
        report = json.loads(result.stdout)
        self.assertEqual(Path(report["destination"]), (special_target / "pimp").resolve())
        self.assertTrue((special_target / "pimp" / "LICENSE").is_file())
        self.assertFalse((self.root / "injected").exists())
        self.assertFalse((self.root / "injected2").exists())

    def test_cli_failure_is_nonzero_without_removing_destination(self):
        installer.install_skill(self.source, self.target)
        result = subprocess.run(
            [sys.executable, str(INSTALL_SCRIPT), "--source", str(self.source), "--target-dir", str(self.target), "--json"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("already exists", json.loads(result.stdout)["error"])
        self.assertTrue((self.target / "pimp" / "LICENSE").is_file())


class DoctorTests(unittest.TestCase):
    def test_strict_missing_node_fails_with_structured_report(self):
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run(
                [sys.executable, str(DOCTOR_SCRIPT), "--node", str(Path(temp) / "nonexistent-node"), "--json", "--strict"],
                capture_output=True, text=True, check=False,
            )
        report = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["ready"])
        self.assertIn("node", report["missing_required"])
        self.assertIn("pptxgenjs", report["missing_required"])
        self.assertEqual(report["schema_version"], 1)

    def test_non_strict_missing_runtime_reports_without_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run(
                [sys.executable, str(DOCTOR_SCRIPT), "--node", str(Path(temp) / "nonexistent-node"), "--json"],
                capture_output=True, text=True, check=False,
            )
        self.assertEqual(result.returncode, 0)
        self.assertFalse(json.loads(result.stdout)["ready"])

    @unittest.skipUnless(shutil.which("node"), "Node is not installed")
    def test_node_path_can_supply_bundled_pptxgenjs(self):
        with tempfile.TemporaryDirectory(prefix="pimp doctor path ") as temp:
            root = Path(temp).resolve()
            skill = root / "standalone skill"
            skill.mkdir()
            modules = root / "bundled runtime" / "modules"
            package = modules / "pptxgenjs"
            package.mkdir(parents=True)
            (package / "package.json").write_text('{"name":"pptxgenjs","version":"0.0.0","main":"index.js"}')
            (package / "index.js").write_text("module.exports = function PptxGenJS() {};\n")
            environment = {**os.environ, "NODE_PATH": str(modules)}
            result = subprocess.run(
                [sys.executable, str(DOCTOR_SCRIPT), "--node", shutil.which("node"), "--skill-root", str(skill), "--json"],
                env=environment, capture_output=True, text=True, check=True,
            )
            report = json.loads(result.stdout)
            check = next(item for item in report["checks"] if item["name"] == "pptxgenjs")
            self.assertTrue(check["available"])
            self.assertEqual(Path(check["path"]), package / "index.js")


if __name__ == "__main__":
    unittest.main()
