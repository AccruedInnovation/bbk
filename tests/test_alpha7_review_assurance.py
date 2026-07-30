from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from contracts import canonical_digest  # noqa: E402
from review_assurance import (  # noqa: E402
    aggregate_review,
    build_review_run,
    compile_review_context,
    compile_review_manifest,
    create_finding_disposition,
    reconcile_findings,
    validate_assurance_contract,
    validate_evidence_receipt,
    validate_review_attempt,
    validate_review_context,
    validate_review_manifest,
    validate_review_run,
)


def load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


class Alpha7ReviewAssuranceTests(unittest.TestCase):
    def setUp(self):
        self.assurance = load("fixtures/review/assurance-consequential.json")
        self.manifest = load("fixtures/review/manifest-consequential.json")
        self.context = load("fixtures/review/context-complete.json")
        self.attempts = [load("fixtures/review/attempt-blind.json"), load("fixtures/review/attempt-intent.json")]
        self.receipts = [load("fixtures/review/evidence-receipt-v2.json"), load("fixtures/review/evidence-intent.json")]

    def test_assurance_contract_and_duplicate_assertions(self):
        self.assertTrue(validate_assurance_contract(self.assurance)["valid"])
        invalid = validate_assurance_contract(load("fixtures/review/invalid-assurance-duplicate.json"))
        self.assertFalse(invalid["valid"])
        self.assertTrue(any("duplicate" in message.lower() for message in invalid["errors"]))

    def test_manifest_compilation_is_deterministic_and_intent_aware(self):
        first = compile_review_manifest(self.assurance, manifest_id="RM-COMPILED", purpose="acceptance")
        second = compile_review_manifest(self.assurance, manifest_id="RM-COMPILED", purpose="acceptance")
        self.assertEqual(canonical_digest(first), canonical_digest(second))
        self.assertTrue(validate_review_manifest(first, self.assurance)["valid"])
        lenses = {item["lens"] for item in first["lensAssignments"]}
        self.assertIn("intent-outcome", lenses)
        self.assertIn("state-concurrency-effect-recovery", lenses)
        self.assertEqual(len(first["lensAssignments"]), 3)
        self.assertEqual(first["provenance"]["bbkVersion"], "0.1.0-alpha.11.7")

    def test_manifest_rejects_unjustified_assertion_overlap(self):
        value = copy.deepcopy(self.manifest)
        duplicate = copy.deepcopy(value["lensAssignments"][0])
        duplicate["assignmentId"] = "LA-DUPLICATE"
        duplicate["independence"] = {"required": False, "dimensions": [], "reason": ""}
        value["lensAssignments"].append(duplicate)
        result = validate_review_manifest(value, self.assurance)
        self.assertFalse(result["valid"])
        self.assertTrue(any("overlap" in message.lower() for message in result["errors"]))

    def test_context_uses_full_content_and_blocks_missing_required_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "README.md").write_text("alpha\n", encoding="utf-8")
            manifest = copy.deepcopy(self.manifest)
            complete = compile_review_context(manifest, root, context_id="RCM-1")
            self.assertEqual(complete["completeness"], "COMPLETE")
            self.assertTrue(validate_review_context(complete, manifest)["valid"])
            root_digest = complete["contentRoot"]
            (root / "README.md").write_text("beta\n", encoding="utf-8")
            changed = compile_review_context(manifest, root, context_id="RCM-1")
            self.assertNotEqual(root_digest, changed["contentRoot"])
            manifest["contextPolicy"]["requiredPaths"] = ["README.md", "required.md"]
            blocked = compile_review_context(manifest, root, context_id="RCM-2")
            self.assertEqual(blocked["completeness"], "BLOCKED_REQUIRED_CONTEXT_MISSING")
            self.assertTrue(blocked["blockers"])

    def test_cross_shard_assertion_requires_cross_shard_lens_and_attempt(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["shardPlan"] = {
            "mode": "semantic",
            "grouping": "execution-slice-or-responsibility",
            "crossShardAssertionRefs": ["A-INTENT"],
        }
        invalid = validate_review_manifest(manifest, self.assurance)
        self.assertFalse(invalid["valid"])
        intent_assignment = next(item for item in manifest["lensAssignments"] if "A-INTENT" in item["primaryAssertionRefs"])
        intent_assignment["lens"] = "cross-shard-integration"
        intent_assignment["reviewerCapabilityRequirements"] = ["cross-shard-integration"]
        self.assertTrue(validate_review_manifest(manifest, self.assurance)["valid"])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "README.md").write_text("root\n", encoding="utf-8")
            (root / "provider").mkdir(); (root / "provider" / "a.txt").write_text("a\n", encoding="utf-8")
            (root / "consumer").mkdir(); (root / "consumer" / "b.txt").write_text("b\n", encoding="utf-8")
            context = compile_review_context(manifest, root, context_id="RCM-SHARDED")
            self.assertGreaterEqual(len(context["shards"]), 2)
            self.assertTrue(validate_review_context(context, manifest)["valid"])
            missing = aggregate_review(manifest, context, self.attempts, [], receipts=self.receipts)
            self.assertEqual(missing["result"], "INCONCLUSIVE")
            cross_attempt = copy.deepcopy(self.attempts[1])
            cross_attempt["lens"] = "cross-shard-integration"
            complete = aggregate_review(manifest, context, [self.attempts[0], cross_attempt], [], receipts=self.receipts)
            self.assertEqual(complete["result"], "PASS")

    def test_unstructured_evidence_is_not_silent_strong_evidence(self):
        receipt = copy.deepcopy(self.receipts[0])
        receipt["receiptId"] = "ER-UNSTRUCTURED"
        receipt["trustClass"] = "UNSTRUCTURED_OBSERVATION"
        receipt["assertionRefs"] = ["A-EFFECT-ONCE"]
        result = validate_evidence_receipt(receipt)
        self.assertTrue(result["valid"], result)
        self.assertTrue(any("not assertion-satisfying" in message for message in result["warnings"]))
        aggregate = aggregate_review(
            self.manifest,
            self.context,
            self.attempts,
            [],
            receipts=[receipt, self.receipts[1]],
        )
        self.assertEqual(aggregate["result"], "INCONCLUSIVE")
        effect = next(item for item in aggregate["assertionResults"] if item["assertionRef"] == "A-EFFECT-ONCE")
        self.assertEqual(effect["status"], "INCONCLUSIVE")

    def test_wrong_subject_required_receipt_makes_review_stale(self):
        receipt = copy.deepcopy(self.receipts[0])
        receipt["subject"]["digest"] = "f" * 64
        aggregate = aggregate_review(
            self.manifest,
            self.context,
            self.attempts,
            [],
            receipts=[receipt, self.receipts[1]],
        )
        self.assertEqual(aggregate["result"], "STALE")
        self.assertTrue(any("another subject" in blocker for blocker in aggregate["blockers"]))

    def test_complete_run_passes_and_is_content_bound(self):
        run = build_review_run(self.manifest, self.context, run_id="RR-ORDER-001", attempts=self.attempts, receipts=self.receipts, findings=[], dispositions=[])
        self.assertEqual(run["aggregate"]["result"], "PASS")
        self.assertTrue(validate_review_run(run, self.manifest, self.context)["valid"])
        changed = copy.deepcopy(run)
        changed["subject"]["ref"] = "OTHER"
        self.assertFalse(validate_review_run(changed, self.manifest, self.context)["valid"])

    def test_reviewer_infrastructure_failure_is_not_candidate_failure(self):
        broken = copy.deepcopy(self.attempts[0])
        broken["completionState"] = "ERROR"
        broken["assertionEvaluations"] = []
        broken["infrastructureErrors"] = ["model provider unavailable"]
        aggregate = aggregate_review(self.manifest, self.context, [broken, self.attempts[1]], [], receipts=self.receipts)
        self.assertEqual(aggregate["result"], "ERROR")
        self.assertFalse(any("failed" in item.lower() for item in aggregate["blockers"]))

    def test_nonrediscovery_does_not_close_finding(self):
        finding = load("fixtures/review/finding-open.json")
        aggregate = aggregate_review(self.manifest, self.context, self.attempts, [finding], receipts=self.receipts)
        self.assertEqual(aggregate["result"], "NEEDS_REVISION")
        self.assertIn(finding["findingId"], aggregate["openFindingRefs"])
        disposition = load("fixtures/review/finding-disposition-fixed.json")
        closed = aggregate_review(self.manifest, self.context, self.attempts, [finding], [disposition], self.receipts)
        self.assertEqual(closed["result"], "PASS")
        self.assertNotIn(finding["findingId"], closed["openFindingRefs"])

    def test_targeted_and_blind_attempt_visibility_remain_distinct(self):
        blind = self.attempts[0]
        self.assertEqual(blind["priorFindingsVisibility"], "HIDDEN")
        targeted = copy.deepcopy(blind)
        targeted["attemptId"] = "ATT-TARGETED"
        targeted["priorFindingsVisibility"] = "TARGETED"
        targeted["assignmentRef"] = "LA-A-EFFECT-ONCE"
        self.assertTrue(validate_review_attempt(targeted)["valid"])
        self.assertNotEqual(canonical_digest(blind), canonical_digest(targeted))

    def test_reconciliation_preserves_original_findings(self):
        left = load("fixtures/review/finding-open.json")
        right = copy.deepcopy(left)
        right["findingId"] = "F-ORDER-002"
        proposal = reconcile_findings([left, right])
        self.assertEqual(proposal["proposals"][0]["relationship"], "PROBABLE_DUPLICATE")
        self.assertTrue(proposal["proposals"][0]["requiresConfirmation"])
        self.assertEqual(left["lifecycle"], "OPEN")
        self.assertEqual(right["lifecycle"], "OPEN")

    def test_explicit_disposition_requires_closure_evidence(self):
        finding = load("fixtures/review/finding-open.json")
        with self.assertRaises(ValueError):
            create_finding_disposition(
                finding,
                disposition="FIXED",
                successor_ref="CANDIDATE-ORDER-002",
                successor_digest="a" * 64,
                evidence_refs=[],
                review_attempt_ref="ATT-CLOSURE",
                authority_ref=None,
                residual_impact="none",
                reopening_triggers=[],
                disposition_id="FDISP-BAD",
                created_at="2026-07-24T00:00:00Z",
            )


if __name__ == "__main__":
    unittest.main()
