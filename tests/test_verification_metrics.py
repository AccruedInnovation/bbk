from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import verification_metrics  # noqa: E402


class VerificationMetricsTests(unittest.TestCase):
    def load(self, name: str):
        return json.loads((ROOT / "fixtures" / "verification-economy" / name).read_text(encoding="utf-8"))

    def test_reported_alpha16_pattern_is_replayed_without_expanding_7562_calls(self):
        result = verification_metrics.extract_metrics(self.load("excessive-verification-alpha16-codex.json"))
        self.assertEqual("FAIL", result["status"])
        self.assertEqual(79, result["sessions"]["total"])
        self.assertEqual(4, result["sessions"]["worker"])
        self.assertEqual(75, result["sessions"]["planning_coordination_assurance"])
        self.assertEqual(7562, result["totals"]["shell_call"])
        self.assertEqual(470, result["verification"]["underlying_handoff_verifications"])
        self.assertEqual(33, result["verification"]["repository_validator_invocations"])
        self.assertEqual(30, result["verification"]["metadata_only_repository_validator_invocations"])
        self.assertEqual(4, sum(result["attempts"]["churn_by_cause"].values()))
        self.assertGreater(result["budgets"]["violation_count"], 0)

    def test_alpha17_compliant_replay_passes_every_routine_budget(self):
        result = verification_metrics.extract_metrics(self.load("alpha17-compliant-replay.json"))
        self.assertEqual("PASS", result["status"])
        self.assertEqual(0, result["budgets"]["violation_count"])
        self.assertEqual(3, result["verification"]["receipt_reuse_count"])
        self.assertEqual(3, result["verification"]["avoided_check_count"])
        self.assertEqual(2, result["attempts"]["mechanical_repairs_completed_in_place"])
        self.assertEqual(35.0, result["latency"]["seconds_to_first_outcome_bearing_worker_action"])

    def test_metrics_validate_against_draft_2020_12_schema(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema unavailable")
        result = verification_metrics.extract_metrics(self.load("alpha17-compliant-replay.json"))
        schema = json.loads((ROOT / "spec" / "schemas" / "bbk-verification-economy-metrics-v1.schema.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(result)


if __name__ == "__main__":
    unittest.main()
