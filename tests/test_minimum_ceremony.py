from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import json

from tools.review_assurance import (
    artifact_requirements,
    classify_execution_level,
    compile_routine_validator_plan,
    lightweight_candidate_current,
    lightweight_candidate_identity,
)


class MinimumCeremonyTests(unittest.TestCase):
    def test_routine_routes_directly_and_keeps_validator_floor(self) -> None:
        level = classify_execution_level()
        self.assertEqual("LEVEL_0", level["name"])
        self.assertTrue(level["routine"])
        candidate = {"kind": "lightweight-file-set-v1", "digest": "a" * 64}
        plan = compile_routine_validator_plan(
            candidate=candidate,
            assertions=[{"assertionId": "A1"}, {"assertionId": "A2"}],
            method="python -m unittest tests.test_minimum_ceremony",
        )
        self.assertEqual(1, plan["validatorCount"])
        self.assertEqual(["A1", "A2"], plan["assignments"][0]["assertionRefs"])
        self.assertFalse(plan["reviewerRequired"])

    def test_named_escalation_and_unknowns(self) -> None:
        triggers = (
            "outcome_clear", "shared_interface", "multiple_owners", "external_effect",
            "recovery_contract", "qualitative_risk", "acceptance_or_release",
            "validator_inconclusive",
        )
        kwargs = {
            "outcome_clear": False,
            "shared_interface": True,
            "multiple_owners": True,
            "external_effect": True,
            "recovery_contract": True,
            "qualitative_risk": True,
            "acceptance_or_release": True,
            "validator_inconclusive": True,
        }
        level = classify_execution_level(**kwargs)
        self.assertEqual("LEVEL_2", level["name"])
        self.assertEqual(
            {"unclear_outcome", "shared_interface", "multiple_owners", "external_effect",
             "recovery_contract", "qualitative_risk", "acceptance_or_release",
             "validator_inconclusive"},
            set(level["escalation_triggers"]),
        )
        for trigger in triggers:
            self.assertIn("_".join(("unclear", "outcome")) if trigger == "outcome_clear" else trigger,
                          classify_execution_level(**{trigger: False} if trigger == "outcome_clear" else {trigger: True})["escalation_triggers"])
        self.assertEqual("LEVEL_0", classify_execution_level()["name"])

    def test_routine_excludes_review_manifest_and_sealing(self) -> None:
        plan = compile_routine_validator_plan(
            candidate={"kind": "lightweight-file-set-v1", "digest": "b" * 64},
            assertions=[{"assertionId": "A1"}, {"assertionId": "A2"}],
            method="focused",
        )
        self.assertEqual({"RV-1"}, {item["assignmentId"] for item in plan["assignments"]})
        self.assertTrue(plan["grouped"])
        self.assertTrue(all(item["independent"] for item in plan["assignments"]))
        self.assertFalse(plan["reviewerRequired"])

    def test_lightweight_identity_invalidates_on_byte_change(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "a.txt"
            path.write_text("one\n", encoding="utf-8")
            identity = lightweight_candidate_identity([path], revision="r1")
            self.assertTrue(lightweight_candidate_current(identity, [path], revision="r1"))
            path.write_text("two\n", encoding="utf-8")
            self.assertFalse(lightweight_candidate_current(identity, [path], revision="r1"))

    def test_artifact_policy_is_conditional(self) -> None:
        routine = artifact_requirements()
        self.assertFalse(routine["required"])
        self.assertEqual([], routine["operations"])
        self.assertFalse(routine["sealed_package"])
        for kwargs in ({"explicit_packaging": True}, {"durable_handoff": True},
                       {"binary_output": True}, {"level": 1}):
            required = artifact_requirements(**kwargs)
            self.assertTrue(required["required"])
            self.assertEqual(["finalize", "verify", "freshness"], required["operations"])
            self.assertTrue(required["sealed_package"])

    def test_compiled_method_and_harness_projection_parity(self) -> None:
        method = json.loads((Path("spec") / "method-content.json").read_text(encoding="utf-8"))
        controller = method["skills"]["bbk"]
        wayfind = method["skills"]["bbk-wayfind"]
        artifact = method["skills"]["bbk-artifact"]
        self.assertIn("exactly one compact `bbk_worker`", controller)
        self.assertIn("controller-owned path de-escalates", wayfind)
        self.assertIn("does not require finalize or freshness", artifact)
        for path in (
            Path("projections/omp/agents/bbk_root_wayfinder.md"),
            Path("projections/codex/agents/bbk_root_wayfinder.toml"),
            Path("projections/claude/agents/bbk-root-wayfinder.md"),
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("controller-owned path de-escalates", text, str(path))


if __name__ == "__main__":
    unittest.main()
