"""Runtime setup regression tests never install packages or contact a registry."""

from __future__ import annotations

from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "pimp" / "scripts" / "setup_runtime.py"
spec = importlib.util.spec_from_file_location("pimp_setup_runtime", SCRIPT)
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class RuntimeSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pimp 런타임 spaces ")
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / "skill $(touch injected) `touch injected2`"
        (self.root / "scripts").mkdir(parents=True)
        (self.root / "scripts" / "doctor.py").write_text("# fixture doctor\n")
        (self.root / "requirements.txt").write_text("pdfplumber>=0.11,<0.12\n")
        (self.root / "package.json").write_text('{"name":"pimp","dependencies":{"pptxgenjs":"4.0.1"}}\n')
        (self.root / "package-lock.json").write_text('{"name":"pimp","lockfileVersion":3}\n')
        self.node = self.base / "runtime with 한글" / "node"
        self.node.parent.mkdir()
        self.node.write_text("node fixture")
        self.npm = self.node.parent / "npm-cli.js"
        self.npm.write_text("// npm fixture")
        self.calls = []
        self.fail_stage = None
        self.node_version = "v20.11.1"
        self.doctor = {"schema_version": 1, "ready": True, "missing_required": [], "checks": [], "warnings": ["Preview renderer optional and unavailable"]}
        self.probe_prefix = None
        self.patcher = mock.patch.object(runtime.subprocess, "run", side_effect=self.run_fake)
        self.patcher.start()
        self.environ = mock.patch.dict(os.environ, {}, clear=False)
        self.environ.start()
        os.environ.pop("PIMP_NODE", None)
        os.environ.pop("PIMP_NPM", None)

    def tearDown(self):
        self.environ.stop()
        self.patcher.stop()
        self.temp.cleanup()

    def run_fake(self, command, **kwargs):
        self.assertIsInstance(command, list)
        self.assertNotIn("shell", kwargs)
        self.assertEqual(Path(kwargs["cwd"]), self.root)
        self.calls.append((command, kwargs))
        if command == [str(self.node), "--version"]:
            stage, stdout = "node", self.node_version + "\n"
        elif command == [str(self.node), str(self.npm), "--version"]:
            stage, stdout = "npm-version", "10.2.4\n"
        elif "venv" in command and "-m" in command:
            stage, stdout = "venv-create", ""
            self.assertEqual(Path(command[-1]), self.root / ".venv")
            python = runtime._venv_python(self.root)
            python.parent.mkdir(parents=True)
            python.write_text("venv python fixture")
        elif "-c" in command:
            stage = "venv-probe"
            stdout = json.dumps({"prefix": self.probe_prefix or str(self.root / ".venv"), "base_prefix": "/existing/system/python", "version": [3, 11]})
        elif "pip" in command:
            stage, stdout = "pip", "Installed local packages\n"
            self.assertEqual(command[0], str(runtime._venv_python(self.root)))
            self.assertTrue((self.root / ".venv" / runtime.OWNER_MARKER).exists())
            self.assertFalse((self.root / runtime.RUNTIME_MARKER).exists())
        elif "ci" in command:
            stage, stdout = "npm", "Installed local npm packages\n"
            self.assertEqual(command[:2], [str(self.node), str(self.npm)])
            self.assertEqual(command[command.index("--prefix") + 1], str(self.root))
            self.assertFalse((self.root / runtime.RUNTIME_MARKER).exists())
        elif str(self.root / "scripts" / "doctor.py") in command:
            stage, stdout = "doctor", json.dumps(self.doctor)
            self.assertIn("--strict", command)
            self.assertIn("--json", command)
            self.assertEqual(command[command.index("--node") + 1], str(self.node))
        else:
            self.fail(f"Unexpected subprocess: {command}")
        if self.fail_stage == stage:
            return subprocess.CompletedProcess(command, 1, stdout, f"simulated {stage} failure")
        return subprocess.CompletedProcess(command, 0, stdout, "")

    def setup_runtime(self, **kwargs):
        return runtime.setup_runtime(self.root, node=str(self.node), npm=str(self.npm), **kwargs)

    def setup_success(self):
        report = self.setup_runtime()
        self.assertTrue(report["ok"], report)
        return report

    def test_success_records_final_paths_only_after_doctor(self):
        report = self.setup_success()
        marker = json.loads((self.root / runtime.RUNTIME_MARKER).read_text())
        self.assertEqual(marker, report)
        self.assertEqual(marker["schema_version"], 1)
        self.assertEqual(marker["skill_root"], str(self.root))
        self.assertEqual(marker["python"], str(runtime._venv_python(self.root)))
        self.assertEqual(marker["node"], str(self.node))
        self.assertEqual(marker["digest"], runtime._dependency_digest(self.root))
        self.assertTrue(marker["doctor"]["ready"])
        self.assertEqual(report["doctor"]["warnings"], self.doctor["warnings"])
        self.assertNotIn("npm_command", marker)

    def test_old_python_is_rejected_before_writes_or_subprocesses(self):
        with mock.patch.object(runtime.sys, "version_info", (3, 9, 8)):
            report = self.setup_runtime()
        self.assertFalse(report["ok"])
        self.assertIn("3.10", report["error"])
        self.assertEqual(self.calls, [])
        self.assertFalse((self.root / ".venv").exists())

    def test_old_node_is_rejected_before_writes(self):
        self.node_version = "v18.20.0"
        report = self.setup_runtime()
        self.assertFalse(report["ok"])
        self.assertIn(">=20", report["error"])
        self.assertEqual(len(self.calls), 1)
        self.assertFalse((self.root / ".venv").exists())

    def test_missing_npm_is_rejected_before_writes(self):
        report = runtime.setup_runtime(self.root, node=str(self.node), npm=str(self.base / "missing npm"))
        self.assertFalse(report["ok"])
        self.assertIn("npm is unavailable", report["error"])
        self.assertFalse((self.root / ".venv").exists())
        self.assertFalse((self.root / runtime.RUNTIME_MARKER).exists())

    def test_pip_failure_invalidates_old_success_and_allows_retry(self):
        self.setup_success()
        self.calls.clear()
        self.fail_stage = "pip"
        report = self.setup_runtime()
        self.assertFalse(report["ok"])
        self.assertEqual(report["stage"], "pip")
        self.assertFalse((self.root / runtime.RUNTIME_MARKER).exists())
        self.assertTrue((self.root / ".venv" / runtime.OWNER_MARKER).exists())
        self.fail_stage = None
        self.setup_success()

    def test_npm_failure_does_not_publish_success(self):
        self.fail_stage = "npm"
        report = self.setup_runtime()
        self.assertFalse(report["ok"])
        self.assertEqual(report["stage"], "npm")
        self.assertFalse((self.root / runtime.RUNTIME_MARKER).exists())
        self.assertFalse(any(str(self.root / "scripts" / "doctor.py") in cmd for cmd, _ in self.calls))

    def test_doctor_failure_preserves_diagnostics_without_success(self):
        self.doctor.update(ready=False, missing_required=["matplotlib"])
        report = self.setup_runtime()
        self.assertFalse(report["ok"])
        self.assertEqual(report["stage"], "doctor")
        self.assertEqual(report["doctor"]["missing_required"], ["matplotlib"])
        self.assertFalse((self.root / runtime.RUNTIME_MARKER).exists())

    def test_offline_check_uses_stored_node_and_never_installs(self):
        self.setup_success()
        marker_path = self.root / runtime.RUNTIME_MARKER
        before = marker_path.read_bytes()
        self.calls.clear()
        self.npm.unlink()  # npm is not required to validate installed packages.
        report = runtime.setup_runtime(self.root, check=True)
        self.assertTrue(report["ok"], report)
        self.assertTrue(report["check"])
        self.assertEqual(report["node"], str(self.node))
        self.assertEqual(len(self.calls), 3)  # Node version, venv identity, doctor.
        self.assertFalse(any("pip" in cmd or "ci" in cmd for cmd, _ in self.calls))
        self.assertEqual(marker_path.read_bytes(), before)

    def test_changed_requirements_are_stale_even_when_doctor_ready(self):
        self.setup_success()
        marker_path = self.root / runtime.RUNTIME_MARKER
        before = marker_path.read_bytes()
        (self.root / "requirements.txt").write_text("pdfplumber>=0.11.5,<0.12\n")
        self.calls.clear()
        report = self.setup_runtime(check=True)
        self.assertFalse(report["ok"])
        self.assertEqual(report["status"], "stale")
        self.assertTrue(report["doctor"]["ready"])
        self.assertTrue(any(str(self.root / "scripts" / "doctor.py") in cmd for cmd, _ in self.calls))
        self.assertEqual(marker_path.read_bytes(), before)

    def test_copying_whole_skill_does_not_trust_foreign_venv(self):
        self.setup_success()
        copied = self.base / "copied skill"
        shutil.copytree(self.root, copied)
        self.root = copied
        before = (copied / runtime.RUNTIME_MARKER).read_bytes()
        report = self.setup_runtime(check=True)
        self.assertFalse(report["ok"])
        self.assertIn("another location", report["error"])
        self.assertEqual((copied / runtime.RUNTIME_MARKER).read_bytes(), before)

    def test_unmarked_venv_is_refused_without_mutation(self):
        (self.root / ".venv").mkdir()
        personal = self.root / ".venv" / "personal.txt"
        personal.write_text("preserve existing environment")
        report = self.setup_runtime()
        self.assertFalse(report["ok"])
        self.assertIn("unmarked", report["error"])
        self.assertEqual(personal.read_text(), "preserve existing environment")
        self.assertFalse((self.root / runtime.RUNTIME_MARKER).exists())

    def test_venv_that_resolves_to_global_python_never_runs_pip(self):
        self.probe_prefix = "/existing/system/python"
        report = self.setup_runtime()
        self.assertFalse(report["ok"])
        self.assertEqual(report["stage"], "venv")
        self.assertFalse(any("pip" in cmd for cmd, _ in self.calls))

    def test_literal_paths_and_local_caches_are_used_without_shell(self):
        os.environ["PIP_TARGET"] = "/unrelated/global/site-packages"
        os.environ["PIP_CONFIG_FILE"] = "/unrelated/pip-redirect.conf"
        os.environ["PYTHONPATH"] = "/unrelated/import-path"
        self.setup_success()
        pip_cmd, pip_args = next((cmd, kwargs) for cmd, kwargs in self.calls if "pip" in cmd)
        self.assertIn("--isolated", pip_cmd)
        self.assertEqual(pip_cmd[pip_cmd.index("-r") + 1], str(self.root / "requirements.txt"))
        self.assertEqual(pip_cmd[pip_cmd.index("--cache-dir") + 1], str(self.root / ".cache" / "pip"))
        self.assertNotIn("PIP_TARGET", pip_args["env"])
        self.assertEqual(pip_args["env"]["PIP_CONFIG_FILE"], os.devnull)
        self.assertNotIn("PYTHONPATH", pip_args["env"])
        npm_cmd, npm_args = next((cmd, kwargs) for cmd, kwargs in self.calls if "ci" in cmd)
        self.assertTrue(set(("--ignore-scripts", "--no-audit", "--no-fund")).issubset(npm_cmd))
        self.assertEqual(npm_args["env"]["npm_config_cache"], str(self.root / ".cache" / "npm"))
        self.assertFalse((self.base / "injected").exists())
        self.assertFalse((self.base / "injected2").exists())

    def test_preflight_timeout_is_clear_and_read_only(self):
        with mock.patch.object(runtime.subprocess, "run", side_effect=subprocess.TimeoutExpired("node", 2)):
            report = runtime.preflight(self.root, node=str(self.node), npm=str(self.npm), timeout=2)
        self.assertFalse(report["ok"])
        self.assertIn("timed out", report["error"])
        self.assertFalse((self.root / ".venv").exists())

    def test_successful_public_preflight_is_read_only(self):
        report = runtime.preflight(self.root, node=str(self.node), npm=str(self.npm))
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["status"], "prerequisites_ready")
        self.assertFalse((self.root / ".venv").exists())
        self.assertFalse((self.root / runtime.RUNTIME_MARKER).exists())

    def test_copy_preflight_ignores_excluded_source_venv(self):
        (self.root / ".venv").mkdir()
        report = runtime.preflight(self.root, node=str(self.node), npm=str(self.npm))
        self.assertTrue(report["ok"], report)
        report = runtime.preflight(self.root, node=str(self.node), npm=str(self.npm), check_environment=True)
        self.assertFalse(report["ok"])
        self.assertIn("unmarked", report["error"])

    def test_windows_npm_cmd_is_run_via_selected_node_js_cli(self):
        launcher = self.node.parent / "npm.cmd"
        launcher.write_text("@echo off\n")
        cli = self.node.parent / "node_modules" / "npm" / "bin" / "npm-cli.js"
        cli.parent.mkdir(parents=True)
        cli.write_text("// npm cli fixture")
        self.assertEqual(runtime._npm_command(self.node, launcher), [str(self.node), str(cli)])
        with mock.patch.object(runtime.os, "name", "nt"):
            self.assertEqual(runtime._venv_python(self.root), self.root / ".venv" / "Scripts" / "python.exe")

    def test_json_cli_failure_has_only_json_stdout_and_nonzero_exit(self):
        report = {"schema_version": 1, "ok": False, "status": "error", "stage": "preflight", "error": "missing Node"}
        stdout = io.StringIO()
        with mock.patch.object(runtime, "setup_runtime", return_value=report), redirect_stdout(stdout):
            code = runtime.main(["--json", "--check"])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(stdout.getvalue()), report)


if __name__ == "__main__":
    unittest.main()
