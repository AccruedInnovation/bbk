from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from tests._cli_support import run_cli as pooled_run_cli

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "tools" / "bbk.py"


class Alpha17OptimizationCliTests(unittest.TestCase):
    def run_cli(self, *args: str, cwd: Path | None = None, force_subprocess: bool = False, env=None):
        """Use the pooled entrypoint; retain an explicit child-process escape hatch."""
        return pooled_run_cli(
            [sys.executable, str(CLI), *args],
            cwd=cwd or ROOT,
            env=env,
            check=False,
            force_subprocess=force_subprocess,
        )

    def test_help_exposes_new_bounded_operations(self):
        result = self.run_cli("--help")
        self.assertEqual(0, result.returncode, result.stderr)
        for item in ("result", "manifest", "plan", "worker-contract", "assertion-contract", "command", "profile", "coverage", "workspace", "child-event"):
            self.assertIn(item, result.stdout)

    def test_result_finalize_cli(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); draft = root / "draft.json"; output = root / "final.json"
            draft.write_text('{"value":1}', encoding="utf-8")
            result = self.run_cli("result", "finalize", "--input", str(draft), "--output", str(output), "--generated-at", "2026-08-06T00:00:00Z")
            self.assertEqual(0, result.returncode, result.stderr)
            parsed = json.loads(result.stdout)
            self.assertEqual("PASS", parsed["status"])
            self.assertTrue(output.is_file())

    def test_bounded_operation_help_documents_effect_atomicity_and_replay(self):
        expectations = {
            ("result", "finalize"): ("Effect:", "Atomic:", "Replay legal"),
            ("plan", "migrate-readiness"): ("Effect:", "legacy", "artifact unchanged", "Replay legal"),
            ("command", "replay-evaluate"): ("Read-only", "replay", "effects are proven NONE"),
        }
        for command, markers in expectations.items():
            with self.subTest(command=command):
                result = self.run_cli(*command, "--help")
                self.assertEqual(0, result.returncode, result.stderr)
                for marker in markers:
                    self.assertIn(marker, result.stdout)

    def test_migrate_readiness_cli_preserves_legacy_source(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            legacy = root / "legacy.json"
            output = root / "readiness.json"
            legacy_value = {
                "schema": "bbk.legacy-planning-state.v1",
                "id": "legacy-plan",
                "fully_planned": False,
                "phases": [{"id": "phase-1"}, {"id": "phase-2"}],
            }
            legacy.write_text(json.dumps(legacy_value, indent=2) + "\n", encoding="utf-8")
            roadmap = root / "roadmap.json"
            frontier = root / "frontier.json"
            coverage = root / "coverage.json"
            roadmap.write_text(json.dumps({"id": "roadmap:legacy", "revision": 1}) + "\n", encoding="utf-8")
            frontier.write_text(json.dumps({"id": "frontier:phase-1", "revision": 1}) + "\n", encoding="utf-8")
            coverage.write_text(json.dumps({"id": "coverage:legacy", "revision": 1}) + "\n", encoding="utf-8")
            before = legacy.read_bytes()
            result = self.run_cli(
                "plan", "migrate-readiness",
                "--legacy", str(legacy),
                "--roadmap", str(roadmap),
                "--frontier", str(frontier),
                "--coverage", str(coverage),
                "--authority", "authority:accepted",
                "--generated-at", "2026-08-06T00:00:00Z",
                "--output", str(output),
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(before, legacy.read_bytes())
            parsed = json.loads(result.stdout)
            self.assertEqual("PASS", parsed["status"])
            migrated = json.loads(output.read_text(encoding="utf-8"))
            readiness = migrated["readiness"]
            self.assertEqual(["ROADMAP_READY", "FRONTIER_READY", "FULLY_COMPILED"], readiness["readiness"])
            self.assertEqual("STANDARD", readiness["planning_mode"])
            self.assertEqual("ADOPT_AND_GAP", readiness["architecture_mode"])
            self.assertTrue(readiness["migration"]["source_preserved_immutable"])
            self.assertEqual("BASELINE_ADVANCED", migrated["migration_anchor_event"]["event_type"])

    def test_in_process_and_real_process_are_differentially_equivalent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            in_process = self.run_cli("--json", "status", "--root", root)
            real_process = self.run_cli(
                "--json", "status", "--root", root, force_subprocess=True
            )
            self.assertEqual(in_process.returncode, real_process.returncode)
            self.assertEqual(in_process.stdout, real_process.stdout)
            self.assertEqual(in_process.stderr, real_process.stderr)

    def test_in_process_restores_cwd_environment_and_argv_state(self):
        before_cwd = Path.cwd()
        before_env = os.environ.copy()
        before_argv = list(sys.argv)
        with tempfile.TemporaryDirectory() as td:
            result = self.run_cli("--json", "status", "--root", Path(td))
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path.cwd(), before_cwd)
        self.assertEqual(os.environ, before_env)
        self.assertEqual(sys.argv, before_argv)

    def test_python_isolation_flags_keep_real_process_boundary(self):
        for flag in ("-S", "-I"):
            with self.subTest(flag=flag):
                result = pooled_run_cli(
                    [sys.executable, flag, str(CLI), "--json", "status"],
                    cwd=ROOT,
                    check=False,
                    force_subprocess=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["status"], "PASS")

    def test_nested_profile_runner_uses_fixture_script_without_extra_process(self):
        profile = ROOT / "fixtures" / "profiles" / "alpha8"
        state_effect = ROOT / "fixtures" / "state-effect" / "contract-order.json"
        result = self.run_cli(
            "--json",
            "profile",
            "dispatch",
            "--operation",
            "state-effect",
            "--id",
            "alpha8-fixture",
            "--profile-dir",
            profile,
            "--source",
            ROOT,
            "--state-decision-effect",
            state_effect,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "PASS")

    def test_installed_thin_launcher_smoke_remains_a_real_process(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            home = root / "home"
            env = os.environ.copy()
            env.update(
                {
                    "HOME": str(home),
                    "BBK_HOME": str(home),
                    "USERPROFILE": str(home),
                    "BBK_INSTALL_ROOT": str(root / "data"),
                    "BBK_BIN_DIR": str(root / "bin"),
                    "BBK_PYTHON": sys.executable,
                }
            )
            installed = pooled_run_cli(
                [
                    sys.executable,
                    str(ROOT / "tools" / "install.py"),
                    "--json",
                    "install",
                    "--scope",
                    "user",
                    "--omp",
                    "--no-language-profiles",
                ],
                cwd=ROOT,
                env=env,
                check=False,
            )
            self.assertEqual(installed.returncode, 0, installed.stderr)
            record = json.loads(installed.stdout)
            launcher = Path(next(item["path"] for item in record["files"] if item.get("source") == "generated:launcher"))
            self.assertTrue(launcher.is_file())
            if os.name == "nt":
                command = ["cmd", "/d", "/c", str(launcher), "--json", "status"]
            else:
                command = [str(launcher), "--json", "status"]
            smoke = pooled_run_cli(command, cwd=ROOT, env=env, check=False, force_subprocess=True)
            self.assertEqual(smoke.returncode, 0, smoke.stderr)
            self.assertEqual(json.loads(smoke.stdout)["status"], "PASS")

    def test_external_boundaries_stay_subprocesses(self):
        cases = [("git", ["--version"]), ("node", ["--version"]), ("jj", ["--version"]), ("bd", ["--version"])]
        for executable, args in cases:
            if shutil.which(executable) is None:
                continue
            with self.subTest(executable=executable):
                result = pooled_run_cli([executable, *args], cwd=ROOT, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(result.stdout.strip(), result.stderr)

    def test_process_tree_smoke_is_not_collapsed_into_parent(self):
        with tempfile.TemporaryDirectory() as td:
            script = Path(td) / "tree.py"
            script.write_text(
                "import subprocess, sys\n"
                "child = subprocess.run([sys.executable, '-c', 'print(\\\"child-ok\\\")'], capture_output=True, text=True)\n"
                "print(child.stdout, end='')\n",
                encoding="utf-8",
            )
            result = pooled_run_cli(
                [sys.executable, str(script)],
                cwd=Path(td),
                check=False,
                force_subprocess=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "child-ok")


if __name__ == "__main__":
    unittest.main()
