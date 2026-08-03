from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from artifact_packages import validate_schema_instance


class PrototypeCharterV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.compact = json.loads((ROOT / "templates" / "prototype-charter-v2.json").read_text(encoding="utf-8"))

    def test_compact_template_is_valid(self) -> None:
        self.assertEqual(validate_schema_instance(self.compact, "bbk.prototype-charter.v2"), [])

    def test_each_bounded_compact_semantic_is_required(self) -> None:
        for field in ("uncertainty", "parentDecision", "evaluationThreshold", "budget", "fallback", "evidence", "cleanup", "authority", "artifactDisposition", "authorityBoundary"):
            with self.subTest(field=field):
                value = copy.deepcopy(self.compact)
                value.pop(field)
                self.assertTrue(validate_schema_instance(value, "bbk.prototype-charter.v2"))

    def test_full_requires_apparatus_commitment_plan_and_confounders(self) -> None:
        value = copy.deepcopy(self.compact)
        value["detailLevel"] = "FULL"
        findings = validate_schema_instance(value, "bbk.prototype-charter.v2")
        pointers = {item.get("pointer") for item in findings}
        self.assertTrue({"/apparatus", "/evaluationCommitment", "/runPlan", "/confounders"} <= pointers)
        value.update({
            "apparatus": {"workspace": "disposable"},
            "evaluationCommitment": {"decision": "accept only at threshold"},
            "runPlan": ["run one bounded trial"],
            "confounders": ["host load"],
        })
        self.assertEqual(validate_schema_instance(value, "bbk.prototype-charter.v2"), [])


if __name__ == "__main__":
    unittest.main()
