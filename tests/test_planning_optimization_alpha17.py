from __future__ import annotations

import json
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import planning_optimization as po  # noqa: E402
import runtime_identity as ri  # noqa: E402


class PlanningOptimizationTests(unittest.TestCase):
    def test_roadmap_and_frontier_admit_execution_without_full_compilation(self):
        value = po.build_planning_readiness(
            roadmap={"id": "roadmap:1", "revision": 3, "digest": "a" * 64},
            frontier={"id": "frontier:1", "revision": 2, "digest": "b" * 64},
            coverage={"id": "coverage:1", "revision": 4, "digest": "c" * 64},
            deferred_refinements=[{
                "work_unit_id": "WU-FUTURE-1", "owner": "phase:2",
                "interfaces": ["api:v1"], "dependencies": ["WU-NOW-1"],
                "risk_class": "ROUTINE", "refinement_triggers": ["frontier:2"],
                "state": "DEFERRED_UNTIL_FRONTIER",
            }],
        )
        self.assertEqual(["ROADMAP_READY", "FRONTIER_READY"], value["readiness"])
        self.assertTrue(value["execution_admissible"])
        self.assertNotIn("FULLY_COMPILED", value["readiness"])
        with self.assertRaises(po.PlanningOptimizationError):
            po.validate_planning_readiness({"schema": "bbk.planning-readiness.v1", "readiness": ["FRONTIER_READY"], "execution_admissible": True})

    def test_routine_worker_contract_and_specialist_trigger(self):
        workspace = po.issue_workspace_receipt(
            repository_ref="repo:1", baseline_ref="base:1", protected_tree_state="CLEAN",
            known_unrelated_dirt=[], owned_roots=["src/a"], mutation_owner="worker:a",
            serialization_state="EXCLUSIVE", issued_at="2026-08-06T00:00:00Z",
        )
        work = {
            "id": "WU-1", "revision": 1, "scope": ["src/a"],
            "effect_classes": ["WORKSPACE_IMPLEMENTATION"],
            "required_inputs": ["input:1"], "expected_outputs": ["src/a/result.txt"],
            "focused_checks": ["test:focused"], "completion_checks": ["test:complete"],
        }
        generated = po.generate_worker_contract(work, {"id": "auth:1", "allowed_effects": ["WORKSPACE_IMPLEMENTATION"]}, workspace, {"profile": "python"})
        self.assertEqual("GENERATED", generated["status"])
        self.assertEqual("WU-1", generated["contract"]["work_unit_ref"])
        ambiguous = dict(work, mutation_owners=["worker:a", "worker:b"])
        specialist = po.generate_worker_contract(ambiguous, {"id": "auth:1"}, workspace, {"profile": "python"})
        self.assertEqual("SPECIALIST_REQUIRED", specialist["status"])
        self.assertEqual("bbk.worker-design-trigger.v1", specialist["trigger"]["schema"])

    def test_routine_assertion_and_verification_trigger(self):
        generated = po.generate_assertion_contract(
            {"id": "AC-1", "statement": "result exists", "expected": True},
            {"method": "pytest", "environment": {"kind": "local"}, "evidence": ["junit"], "independence": "INLINE"},
            candidate_stage="FINAL",
        )
        self.assertEqual("GENERATED", generated["status"])
        specialist = po.generate_assertion_contract(
            {"id": "AC-2", "method_ambiguity": "two methods disagree"},
            {"method": "pytest"}, candidate_stage="FINAL",
        )
        self.assertEqual("SPECIALIST_REQUIRED", specialist["status"])
        self.assertEqual("bbk.verification-design-trigger.v1", specialist["trigger"]["schema"])

    def test_candidate_pass_does_not_claim_project_complete(self):
        coverage = {
            "schema": "bbk.project-coverage.v1",
            "master_graph_ref": "graph:1",
            "delivered_scope": ["cap:a"],
            "claims_not_established": ["claim:b"],
            "next_executable_frontier": "frontier:2",
            "capabilities": [
                {"id": "cap:a", "status": "COMPLETED", "remaining_scope": [], "unmet_claims": []},
                {"id": "cap:b", "status": "NOT_STARTED", "remaining_scope": ["future"], "unmet_claims": ["claim:b"]},
            ],
        }
        projected = po.coverage_return_projection(coverage)
        self.assertFalse(projected["project_complete"])
        self.assertEqual(["cap:a"], projected["capabilities_completed"])
        self.assertEqual(["cap:b"], projected["capabilities_not_started"])

    def test_plan_transaction_is_atomic_and_conflict_checked(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            roadmap = root / "roadmap.json"
            receipt = po.transact_plan(
                root,
                [{"event_type": "ROADMAP_REVISED", "subject_ref": "roadmap:1", "payload": {"projection": "roadmap", "revision": 2}}],
                authority_ref="auth:1", projection_outputs={"roadmap": roadmap}, expected_head=po.digest([]),
                transaction_id="plan-tx:test", created_at="2026-08-06T00:00:00Z",
            )
            self.assertEqual("PASS", receipt["status"])
            self.assertTrue(roadmap.is_file())
            self.assertTrue((root / "events.jsonl").is_file())
            with self.assertRaises(po.PlanningOptimizationError) as cm:
                po.transact_plan(root, [], authority_ref="auth:1", expected_head="wrong")
            self.assertEqual("BBK-PLAN-TX-CONFLICT", cm.exception.code)

    def test_continuation_transaction_stays_within_ten_logical_durable_writes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            names = (
                "accepted-baseline", "standing-authority", "roadmap",
                "active-frontier", "project-coverage", "root-wayfinder-return",
            )
            outputs = {name: root / f"{name}.json" for name in names}
            receipt = po.transact_plan(
                root,
                [
                    {"event_type": "BASELINE_ADVANCED", "subject_ref": "baseline:1", "payload": {"projection": "accepted-baseline"}},
                    {"event_type": "AUTHORITY_UPDATED", "subject_ref": "authority:1", "payload": {"projection": "standing-authority"}},
                    {"event_type": "ROADMAP_REVISED", "subject_ref": "roadmap:1", "payload": {"projection": "roadmap"}},
                    {"event_type": "FRONTIER_REVISED", "subject_ref": "frontier:1", "payload": {"projection": "active-frontier"}},
                    {"event_type": "PROJECT_COVERAGE_UPDATED", "subject_ref": "coverage:1", "payload": {"projection": "project-coverage"}},
                    {"event_type": "FRONTIER_ADVANCED", "subject_ref": "return:1", "payload": {"projection": "root-wayfinder-return"}},
                ],
                authority_ref="auth:continuation", projection_outputs=outputs,
                expected_head=po.digest([]), transaction_id="plan-tx:continuation",
                created_at="2026-08-06T00:00:00Z",
            )
            self.assertEqual(9, receipt["durable_planning_write_count"])
            self.assertLessEqual(receipt["durable_planning_write_count"], 10)
            self.assertEqual("LOGICAL_DURABLE_ARTIFACTS", receipt["write_accounting_basis"])
            self.assertEqual(6, len(receipt["projection_identities"]))

    def test_runtime_equivalent_digest_difference_does_not_reopen_planning(self):
        receipt = ri.resolve_effective_profile(
            {"selector": "python", "required_capabilities": ["python"], "required_gates": ["unit"], "allowed_families": ["python"], "predicted_sha256": "a" * 64},
            {"id": "python:actual", "family": "python", "capabilities": ["python", "lint"], "gates": ["unit"], "sha256": "b" * 64},
            {"os": "windows"}, registry_revision="profiles:1", observed_at="2026-08-06T00:00:00Z",
        )
        self.assertEqual("PASS", receipt["status"])
        self.assertEqual("EQUIVALENT", receipt["semantic_equivalence"])
        self.assertFalse(receipt["planning_reopen_required"])
        failed = ri.resolve_effective_profile(
            {"required_capabilities": ["python"], "required_gates": ["integration"]},
            {"id": "python:actual", "family": "python", "capabilities": ["python"], "gates": []},
            {"os": "windows"}, registry_revision="profiles:1",
        )
        self.assertEqual("FAIL", failed["status"])
        self.assertTrue(failed["planning_reopen_required"])

    def test_typed_child_events_and_workspace_receipt_avoid_global_polling(self):
        receipt = po.issue_workspace_receipt(
            repository_ref="repo", baseline_ref="base", protected_tree_state="OBSERVED",
            known_unrelated_dirt=["notes.txt"], owned_roots=["src/a"], mutation_owner="worker:a",
            serialization_state="EXCLUSIVE", issued_at="2026-08-06T00:00:00Z",
        )
        self.assertEqual(["src/a"], receipt["owned_roots"])
        event = po.child_event(child_ref="child:a", state="RETURN_READY", observed_at="2026-08-06T00:01:00Z")
        self.assertFalse(event["poll_required"])
        with self.assertRaises(po.PlanningOptimizationError):
            po.child_event(child_ref="child:a", state="POLL")

    def test_legacy_readiness_migration_preserves_source_and_emits_anchor(self):
        legacy = {"schema": "bbk.plan.v1", "id": "legacy:1", "governance_mode": "FULL", "phases": [1, 2]}
        before = json.loads(json.dumps(legacy))
        result = po.migrate_legacy_planning_readiness(
            legacy,
            roadmap={"id": "roadmap:legacy", "revision": 1, "digest": "a" * 64},
            frontier={"id": "frontier:legacy", "revision": 1, "digest": "b" * 64},
            coverage={"id": "coverage:legacy", "revision": 1, "digest": "c" * 64},
            authority_ref="auth:migration", generated_at="2026-08-06T00:00:00Z",
        )
        self.assertEqual(before, legacy)
        self.assertFalse(result["legacy_source_modified"])
        self.assertEqual("FULL_GOVERNED", result["readiness"]["planning_mode"])
        self.assertEqual(["ROADMAP_READY", "FRONTIER_READY", "FULLY_COMPILED"], result["readiness"]["readiness"])
        self.assertEqual("BASELINE_ADVANCED", result["migration_anchor_event"]["event_type"])

    def test_plan_pointer_failure_restores_prior_authoritative_state(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            roadmap = root / "roadmap.json"
            first = po.transact_plan(
                root,
                [{"event_type": "ROADMAP_REVISED", "subject_ref": "roadmap:1", "payload": {"projection": "roadmap", "revision": 1}}],
                authority_ref="auth:1", projection_outputs={"roadmap": roadmap},
                expected_head=po.digest([]), transaction_id="plan-tx:first", created_at="2026-08-06T00:00:00Z",
            )
            prior_pointer = (root / "current.json").read_bytes()
            prior_log = (root / "events.jsonl").read_bytes()
            prior_projection = roadmap.read_bytes()
            real_replace = po._replace_file

            def fail_pointer(source, target):
                if Path(target).name == "current.json":
                    raise OSError("injected pointer failure")
                return real_replace(source, target)

            with mock.patch.object(po, "_replace_file", side_effect=fail_pointer):
                with self.assertRaises(po.PlanningOptimizationError) as cm:
                    po.transact_plan(
                        root,
                        [{"event_type": "FRONTIER_REVISED", "subject_ref": "frontier:1", "payload": {"projection": "roadmap", "revision": 1}}],
                        authority_ref="auth:1", projection_outputs={"roadmap": roadmap},
                        expected_head=first["head"], transaction_id="plan-tx:second", created_at="2026-08-06T00:01:00Z",
                    )
            self.assertEqual("BBK-PLAN-TX-PUBLISH", cm.exception.code)
            self.assertEqual(prior_pointer, (root / "current.json").read_bytes())
            self.assertEqual(prior_log, (root / "events.jsonl").read_bytes())
            self.assertEqual(prior_projection, roadmap.read_bytes())
            events, head, _ = po._read_current_state(root)
            self.assertEqual(first["head"], head)
            self.assertEqual(1, len(events))

    def test_plan_lock_produces_retryable_conflict(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            root.mkdir(exist_ok=True)
            (root / ".plan-transaction.lock").write_text("held", encoding="utf-8")
            with self.assertRaises(po.PlanningOptimizationError) as cm:
                po.transact_plan(root, [], authority_ref="auth:1")
            self.assertEqual("BBK-PLAN-TX-CONFLICT", cm.exception.code)
            self.assertTrue(cm.exception.retryable)


if __name__ == "__main__":
    unittest.main()
