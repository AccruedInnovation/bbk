from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "tools" / "bbk.py"


class Alpha17OptimizationCliTests(unittest.TestCase):
    def run_cli(self, *args: str, cwd: Path | None = None):
        return subprocess.run([sys.executable, str(CLI), *args], cwd=cwd or ROOT, text=True, capture_output=True)

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


if __name__ == "__main__":
    unittest.main()
