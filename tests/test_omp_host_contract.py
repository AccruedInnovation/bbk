from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "evidence" / "qualification" / "omp-host-contract-rc9.json"
RUNNER = ROOT / "tools" / "qualification" / "omp_host_contract.py"


class OmpHostContractEvidenceTests(unittest.TestCase):
    def test_checked_in_evidence_satisfies_alpha17_assertions(self) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertEqual(report["schema"], "bbk.omp-host-contract-report.v1")
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["qualified_host"]["expected_omp_version"], "16.4.8")
        self.assertEqual(report["assertions"], {"VER-017": "PASS", "VER-018": "PASS", "VER-019": "PASS", "VER-020": "PASS", "VER-021": "PASS", "VER-022": "PASS"})
        scenarios = {item["scenario"]: item for item in report["scenarios"]}
        self.assertEqual(scenarios["ambient-block"]["observations"]["blocked_tools"], ["bash", "edit", "write"])
        self.assertTrue(scenarios["ambient-block"]["observations"]["write_effect_absent"])
        self.assertTrue(scenarios["ambient-block"]["observations"]["edit_effect_absent"])
        self.assertTrue(scenarios["ambient-block"]["observations"]["bash_effect_absent"])
        self.assertTrue(scenarios["scoped-write"]["observations"]["governed_file_created"])
        self.assertTrue(scenarios["child-identity"]["observations"]["parent_child_session_ids_distinct"])
        self.assertTrue(scenarios["child-identity"]["observations"]["parent_child_cwd_equal"])
        self.assertTrue(scenarios["child-identity"]["observations"]["task_parent_binding_observed"])
        overlay = scenarios["extension-overlay"]["observations"]
        self.assertTrue(overlay["configured_extension_recorded_before_overlay"])
        self.assertFalse(overlay["configured_extension_loaded"])
        self.assertTrue(overlay["explicit_extension_loaded"])
        self.assertEqual(overlay["explicit_extension_effect"], "GOVERNED")
        self.assertFalse(overlay["no_extensions_flag_used"])
        dispatch = scenarios["dispatch-rewrite"]["observations"]
        self.assertTrue(dispatch["dispatch_rewrite_observed"])
        self.assertTrue(dispatch["presentation_i_absent_at_pre_effect_hook"])
        self.assertTrue(dispatch["resolved_child_started"])
        self.assertTrue(dispatch["resolved_identity_value_observed"])
        self.assertTrue(dispatch["compact_marker_absent_from_child_request"])
        self.assertTrue(dispatch["task_parent_binding_observed"])
        yield_validation = scenarios["yield-validation"]["observations"]
        self.assertTrue(yield_validation["malformed_yield_blocked_before_acceptance"])
        self.assertTrue(yield_validation["complete_prepared_yield_admission_observed"])
        self.assertTrue(yield_validation["complete_role_return_observed_by_parent"])
        self.assertTrue(yield_validation["unvalidated_malformed_return_absent_from_parent"])
        self.assertFalse(report["network_and_credentials"]["remote_provider_contacted"])
        self.assertFalse(report["network_and_credentials"]["provider_api_keys_used"])

    def test_runner_help_and_fixture_outputs_are_packaged(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(RUNNER), "--help"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("keyless OMP 16.4.8 host-contract qualification", completed.stdout)
        self.assertTrue((ROOT / "tests" / "fixtures" / "omp-host-contract" / "fixture-extension.mjs").is_file())
        self.assertTrue((ROOT / "tests" / "fixtures" / "omp-host-contract" / "fixture-worker.md").is_file())
        self.assertTrue((ROOT / "docs" / "qualification" / "OMP-HOST-CONTRACT-FEASIBILITY.md").is_file())
        self.assertTrue((ROOT / "docs" / "qualification" / "OMP-HOST-CONTRACT-RC9.md").is_file())

    @unittest.skipUnless(os.environ.get("BBK_OMP_BINARY"), "set BBK_OMP_BINARY for live OMP contract qualification")
    def test_live_omp_contract(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(RUNNER), "--omp", os.environ["BBK_OMP_BINARY"]],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
