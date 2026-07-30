from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BBK = ROOT / "tools" / "bbk.py"
A8 = ROOT / "fixtures" / "profiles" / "alpha8"
A7 = ROOT / "fixtures" / "profiles" / "alpha7"
SDE = ROOT / "fixtures" / "state-effect" / "contract-order.json"
ASSURANCE = ROOT / "fixtures" / "review" / "assurance-consequential.json"
MANIFEST = ROOT / "fixtures" / "review" / "manifest-consequential.json"
RECEIPT = ROOT / "fixtures" / "review" / "evidence-receipt-v2.json"


def run_json(args: list[str]) -> dict:
    completed = subprocess.run(
        [sys.executable, str(BBK), "--json", *[str(x) for x in args]],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return json.loads(completed.stdout)


class Alpha8ProfileDispatchTests(unittest.TestCase):
    def test_alpha7_declaration_remains_valid_but_is_not_auto_dispatched(self):
        inspected = run_json(["profile", "inspect", "--id", "alpha7-fixture", "--profile-dir", str(A7)])
        self.assertEqual(inspected["package_verification"]["status"], "PASS")
        self.assertEqual(inspected["validation"]["stateDecisionEffectDispatch"], "legacy-declared")
        self.assertEqual(inspected["validation"]["reviewAssuranceDispatch"], "legacy-declared")
        dispatched = run_json([
            "profile", "dispatch", "--operation", "state-effect", "--id", "alpha7-fixture",
            "--profile-dir", str(A7), "--source", str(ROOT), "--state-decision-effect", str(SDE),
        ])
        self.assertEqual(dispatched["status"], "UNSUPPORTED")
        self.assertIn("legacy alpha.7 declaration", dispatched["reason"])

    def test_alpha8_profile_declares_typed_capabilities(self):
        inspected = run_json(["profile", "inspect", "--id", "alpha8-fixture", "--profile-dir", str(A8)])
        self.assertEqual(inspected["package_verification"]["status"], "PASS")
        self.assertEqual(inspected["compatibility"]["status"], "PASS")
        self.assertEqual(inspected["validation"]["stateDecisionEffectDispatch"], "typed-v1")
        self.assertEqual(inspected["validation"]["reviewAssuranceDispatch"], "typed-v1")

    def test_standalone_dispatch_covers_all_operations(self):
        state = run_json([
            "profile", "dispatch", "--operation", "state-effect", "--id", "alpha8-fixture",
            "--profile-dir", str(A8), "--source", str(ROOT), "--state-decision-effect", str(SDE),
        ])
        self.assertEqual(state["status"], "PASS")
        inventory = run_json([
            "profile", "dispatch", "--operation", "state-effect-inventory", "--id", "alpha8-fixture",
            "--profile-dir", str(A8), "--source", str(ROOT), "--state-decision-effect", str(SDE),
        ])
        self.assertEqual(inventory["status"], "PASS")
        with tempfile.TemporaryDirectory() as temp:
            inventory_path = Path(temp) / "inventory.json"
            inventory_path.write_text(json.dumps(inventory["result"]["payload"]), encoding="utf-8")
            review = run_json([
                "profile", "dispatch", "--operation", "state-effect-review", "--id", "alpha8-fixture",
                "--profile-dir", str(A8), "--source", str(ROOT), "--state-decision-effect", str(SDE),
                "--state-effect-inventory", str(inventory_path),
            ])
            self.assertEqual(review["status"], "PASS")
            context = run_json([
                "profile", "dispatch", "--operation", "review-context", "--id", "alpha8-fixture",
                "--profile-dir", str(A8), "--source", str(ROOT), "--assurance-contract", str(ASSURANCE),
                "--review-manifest", str(MANIFEST),
            ])
            self.assertEqual(context["status"], "PASS")
            context_path = Path(temp) / "context.json"
            context_path.write_text(json.dumps(context["result"]["payload"]), encoding="utf-8")
            lens = run_json([
                "profile", "dispatch", "--operation", "review-lens", "--id", "alpha8-fixture",
                "--profile-dir", str(A8), "--source", str(ROOT), "--assurance-contract", str(ASSURANCE),
                "--review-manifest", str(MANIFEST), "--review-context", str(context_path),
                "--lens-id", "state-concurrency-effect-recovery", "--assignment-id", "LA-A-STATE-ONE",
            ])
            self.assertEqual(lens["status"], "PASS")
        evidence = run_json([
            "profile", "dispatch", "--operation", "evidence-adapter", "--id", "alpha8-fixture",
            "--profile-dir", str(A8), "--source", str(ROOT), "--evidence-input", str(RECEIPT),
        ])
        self.assertEqual(evidence["status"], "PASS")
        self.assertTrue(evidence["adaptedEvidenceValidation"]["valid"])

    def test_resolve_auto_dispatches_smallest_supported_set_and_is_stable(self):
        argv = [
            "profile", "resolve", "--id", "alpha8-fixture", "--profile-dir", str(A8),
            "--source", str(ROOT), "--role", "reviewer", "--task-profile", "interface-schema-migration",
            "--assurance-tier", "consequential", "--state-decision-effect", str(SDE),
            "--assurance-contract", str(ASSURANCE), "--review-manifest", str(MANIFEST),
            "--evidence-input", str(RECEIPT),
        ]
        first = run_json(argv); second = run_json(argv)
        self.assertEqual(first["schema"], "bbk.profile-resolution-wrapper.v3")
        self.assertEqual(first["effective_sha256"], second["effective_sha256"])
        self.assertEqual(len(first["profile_dispatch"]["operations"]), 7)
        self.assertEqual([item["status"] for item in first["profile_dispatch"]["operations"]], ["PASS"] * 7)
        self.assertEqual(first["profile_dispatch"]["unhandledReviewAssignments"], [{
            "manifestId": "RM-ORDER-001", "assignmentId": "LA-A-INTENT", "lens": "intent-outcome"
        }])
        for item in first["profile_dispatch"]["operations"]:
            if item.get("request"):
                for binding in item["request"]["inputs"]:
                    self.assertFalse(Path(binding["path"]).is_absolute())

    def test_profile_lock_binds_stable_dispatch(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"; project.mkdir()
            run_json(["init", "--root", str(project), "--project-id", "A8-PROFILE-LOCK"])
            value = run_json([
                "profile", "resolve", "--root", str(project), "--source", str(ROOT),
                "--id", "alpha8-fixture", "--profile-dir", str(A8),
                "--state-decision-effect", str(SDE), "--write-lock",
            ])
            lock = json.loads((project / ".bbk" / "profile-lock.json").read_text(encoding="utf-8"))
            profile = lock["profiles"][0]
            self.assertIn("capability_dispatch", profile)
            self.assertRegex(profile["capability_dispatch_sha256"], r"^[0-9a-f]{64}$")
            self.assertNotIn("executions", profile["capability_dispatch"])
            self.assertEqual(lock["effective_sha256"], value["effective_sha256"])

    def test_alpha8_package_surface_is_present(self):
        self.assertEqual((ROOT / "VERSION").read_text(encoding="utf-8").strip(), "0.1.0-alpha.11.7")
        for rel in [
            "docs/LANGUAGE-PROFILES.md",
            "docs/UPGRADING.md",
            "spec/schemas/bbk-profile-capability-request-v1.schema.json",
            "spec/schemas/bbk-profile-capability-result-v1.schema.json",
            "spec/schemas/bbk-profile-dispatch-v1.schema.json",
            "templates/profile-capability-request.json",
        ]:
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_omp_exposes_typed_profile_dispatch(self):
        source = (ROOT / "omp" / "extension" / "index.js").read_text(encoding="utf-8")
        self.assertIn("bbk_profile_dispatch", source)
        self.assertIn("bbk:profile:dispatch", source)
        self.assertIn("--evidence-input", source)


if __name__ == "__main__":
    unittest.main()
