from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BBK = ROOT / "tools" / "bbk.py"
sys.path.insert(0, str(ROOT / "tools"))
from state_effect import (  # noqa: E402
    compare_state_effect_inventory,
    validate_slice_v2,
    validate_state_decision_effect,
    validate_structure_v2,
    validate_transition_trace,
    validate_transition_trace_set,
)
from contracts import validate_profile, validate_work_unit  # noqa: E402


def load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def run_json(argv, *, cwd=ROOT, env=None, check=True):
    completed = subprocess.run([str(x) for x in argv], cwd=str(cwd), env=env, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check)
    return json.loads(completed.stdout), completed


class Alpha7StateEffectTests(unittest.TestCase):
    def test_valid_and_invalid_state_effect_designs(self):
        valid = validate_state_decision_effect(load("fixtures/state-effect/contract-order.json"))
        self.assertTrue(valid["valid"], valid)
        self.assertEqual(valid["summary"]["applicability"], "CONTRACT")
        invalid = validate_state_decision_effect(load("fixtures/state-effect/invalid-authoritative-derived.json"))
        self.assertFalse(invalid["valid"])
        self.assertTrue(any("authoritative state and derived" in message for message in invalid["errors"]))

    def test_transition_trace_set_and_stale_design_revision(self):
        design = load("fixtures/state-effect/contract-order.json")
        traces = [load(f"fixtures/state-effect/trace-{name}.json") for name in ("happy", "duplicate", "ack-lost")]
        report = validate_transition_trace_set(traces, design)
        self.assertTrue(report["valid"], report)
        self.assertEqual(report["traceCount"], 3)
        stale = json.loads(json.dumps(traces[0]))
        stale["designRevision"] = "0"
        result = validate_transition_trace_set([stale], design)
        self.assertFalse(result["valid"])
        self.assertTrue(any("revision" in message.lower() for message in result["errors"]))

    def test_structure_and_slice_v2_preserve_v1_compatibility(self):
        structure = load("fixtures/structure/software-contract-v2.json")
        slice_value = load("fixtures/slices/software-slice-v2.json")
        structure_result = validate_structure_v2(structure)
        slice_result = validate_slice_v2(slice_value)
        self.assertTrue(structure_result["valid"], structure_result)
        self.assertTrue(slice_result["valid"], slice_result)
        self.assertEqual(structure_result["stateDecisionEffect"]["summary"]["applicability"], "CONTRACT")
        self.assertTrue(slice_value["stateTransitionTouchpoints"])
        self.assertTrue(slice_value["effectBoundaryTouchpoints"])

    def test_planned_actual_review_classifies_material_divergence(self):
        contract = load("fixtures/structure/software-contract-v2.json")
        design = contract["stateDecisionEffectDesign"]
        conformant = compare_state_effect_inventory(design, load("fixtures/state-effect/inventory-conformant.json"))
        divergent = compare_state_effect_inventory(design, load("fixtures/state-effect/inventory-divergent.json"))
        self.assertEqual(conformant["disposition"], "accept-with-advisories")
        self.assertTrue(any(item["divergenceClass"] == "advisory-drift" for item in conformant["stateDecisionEffectFindings"]))
        self.assertEqual(divergent["disposition"], "revise")
        self.assertTrue(any(item["divergenceClass"] == "material-divergence" for item in divergent["stateDecisionEffectFindings"]))

    def test_work_unit_state_effect_and_review_bindings(self):
        work = load("fixtures/work-units/query-service.json")
        work.update({
            "profileHints": ["stateful", "recovery"],
            "stateDecisionEffectRefs": ["SDE-ORDER-001@1"],
            "stateTransitionTraceRefs": ["TRACE-ORDER-HAPPY"],
            "assuranceContractRefs": ["AC-ORDER-001@1"],
            "reviewManifestRefs": ["RM-ORDER-001@1"],
        })
        result = validate_work_unit(work)
        self.assertTrue(result["valid"], result)
        broken = dict(work)
        broken["stateDecisionEffectRefs"] = []
        self.assertFalse(validate_work_unit(broken)["valid"])

    def test_profile_capability_states_are_explicit(self):
        legacy = validate_profile(load("fixtures/profiles/legacy/PROFILE.json"))
        alpha7 = validate_profile(load("fixtures/profiles/alpha7/PROFILE.json"))
        self.assertEqual(legacy["stateDecisionEffectSupport"], "legacy-summary")
        self.assertEqual(legacy["reviewAssuranceSupport"], "legacy-no-review-manifest")
        self.assertEqual(alpha7["stateDecisionEffectSupport"], "supported")
        self.assertEqual(alpha7["reviewAssuranceSupport"], "supported")
        self.assertTrue(alpha7["valid"], alpha7)
        inspected, _ = run_json([
            sys.executable,
            BBK,
            "--json",
            "profile",
            "inspect",
            "--profile-dir",
            ROOT / "fixtures" / "profiles" / "alpha7",
            "--id",
            "alpha7-fixture",
        ])
        self.assertEqual(inspected["package_verification"]["status"], "PASS")

    def test_candidate_bound_inventory_change_invalidates_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project = base / "project"; project.mkdir()
            source = project
            subprocess.run(["git", "init", "-q"], cwd=source, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(["git", "config", "user.email", "bbk@example.invalid"], cwd=source, check=True)
            subprocess.run(["git", "config", "user.name", "BBK Test"], cwd=source, check=True)
            (source / "main.txt").write_text("v1\n", encoding="utf-8")
            subprocess.run(["git", "add", "main.txt"], cwd=source, check=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=source, check=True, stdout=subprocess.PIPE)
            run_json([sys.executable, BBK, "--json", "init", "--root", project, "--project-id", "TEST-ALPHA7-CANDIDATE"])
            inventory = base / "inventory.json"
            inventory.write_text(json.dumps(load("fixtures/state-effect/inventory-conformant.json"), sort_keys=True), encoding="utf-8")
            frozen, _ = run_json([sys.executable, BBK, "--json", "candidate", "freeze", "--root", project, "--id", "C-001", "--structure-inventory", inventory])
            self.assertEqual(frozen["status"], "FROZEN")
            current, _ = run_json([sys.executable, BBK, "--json", "candidate", "check", "--root", project, "--id", "C-001"])
            self.assertTrue(current["current"])
            inventory.write_text(inventory.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            stale, _ = run_json([sys.executable, BBK, "--json", "candidate", "check", "--root", project, "--id", "C-001"])
            self.assertFalse(stale["current"])
            self.assertEqual(stale["comparison"]["summary"]["bound_dependency_changed"], 1)


if __name__ == "__main__":
    unittest.main()
