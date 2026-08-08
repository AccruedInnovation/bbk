from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import governed_filesystem as filesystem  # noqa: E402
import governed_state  # noqa: E402
from gate_kernel import canonical_digest  # noqa: E402
import omp_binding_registry as registry  # noqa: E402
import read_only_spawn  # noqa: E402
from substrate import git_adapter, jj_adapter  # noqa: E402
from tests._alpha17_surface_support import JJ, control_parent, init_candidate, schema_validate  # noqa: E402


@unittest.skipUnless(Path(JJ).is_file(), "real jj executable is required")
class ReadOnlySpawnTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.governance = self.base / "campaign"
        self.governance.mkdir()
        self.candidate = init_candidate(self.base / "review-candidate")
        self.parent = control_parent(registry, self.governance)
        self.identity_before = jj_adapter.identity(self.candidate, jj_path=JJ)

    def tearDown(self):
        self.temporary.cleanup()

    def request(self, **changes):
        value = {
            "schema": "bbk.bound-read-only-task-create.v1",
            "host_version": "omp/16.4.8",
            "parent_binding_ref": self.parent["binding_id"],
            "parent_session_id": "parent-session-1",
            "parent_invocation_id": "parent-invocation-1",
            "task_name": "review-frozen-candidate",
            "role": "bbk_reviewer",
            "work_unit_id": "WU-REVIEW",
            "attempt_id": "attempt-review-1",
            "baseline_ref": "git:main",
            "candidate_id": "candidate:review-fixture",
            "authority_ref": "authority:user",
            "return_contract": "bbk.reviewer-return.v2",
            "workspace_ref": str(self.candidate),
            "path_prefixes": ["."],
            "semantic_scope": ["candidate:review-fixture"],
            "assignment": "Review the exact frozen candidate without changing it.",
            "description": "Read-only frozen-candidate review",
            "idempotency_key": "bind-review-fixture-1",
        }
        value.update(changes)
        return value

    def compile(self, **changes):
        return read_only_spawn.compile_read_only_spawn(
            self.governance,
            self.request(**changes),
            jj_path=JJ,
            recorded_at="2026-08-04T00:00:01Z",
        )


    def integrated_candidate(self):
        baseline = jj_adapter.identity(self.candidate, revision="@-", jj_path=JJ)["jj_commit_id"]
        first = jj_adapter.allocate_workspace(
            self.candidate, self.base / "source-a", work_unit_id="WU-A", attempt_id="worker-a-1",
            parent_revision=baseline, description="source A", jj_path=JJ,
        )
        second = jj_adapter.allocate_workspace(
            self.candidate, self.base / "source-b", work_unit_id="WU-B", attempt_id="worker-b-1",
            parent_revision=baseline, description="source B", jj_path=JJ,
        )
        first_root = Path(first["workspace_path"])
        second_root = Path(second["workspace_path"])
        (first_root / "src" / "worker-a").mkdir(parents=True)
        (first_root / "src" / "worker-a" / "result.txt").write_bytes(b"A\n")
        (second_root / "src" / "worker-b").mkdir(parents=True)
        (second_root / "src" / "worker-b" / "result.txt").write_bytes(b"B\n")
        integrated = jj_adapter.merge_content_neutral(
            self.candidate, self.base / "integrated-candidate",
            work_unit_id="WU-INTEGRATE", attempt_id="integration-1",
            source_revisions=[first["jj_change_id"], second["jj_change_id"]],
            parent_revision=baseline, description="integrate A and B", jj_path=JJ,
        )
        workspace = Path(integrated["workspace_path"]).resolve()
        identity = jj_adapter.identity(workspace, revision=integrated["jj_change_id"], jj_path=JJ)
        candidate = git_adapter.freeze_candidate(
            workspace, candidate_id="candidate:integrated", jj_change_id=integrated["jj_change_id"],
            git_repository_root=jj_adapter.git_repository_root(workspace, jj_path=JJ),
        )
        integration_core = {
            "schema": "bbk.test-integration.v1",
            "status": "INTEGRATED",
            "candidate": candidate,
            "adapter_result": integrated,
        }
        integration_core["integration_record_digest"] = f"sha256:{canonical_digest(integration_core)}"
        integration_receipt, _ = governed_state.append_receipt(
            self.governance, "TEST_CONTENT_NEUTRAL_INTEGRATION", integration_core,
            recorded_at="2026-08-04T00:00:00Z",
        )
        admission_core = {
            "schema": "bbk.candidate-integration-admission.v1",
            "status": "PASS",
            "integration_receipt_ref": integration_receipt["receipt_id"],
            "integration_record_digest": integration_core["integration_record_digest"],
            "candidate_id": candidate["candidate_id"],
            "candidate_digest": candidate["digest"],
            "workspace_ref": candidate["workspace_path"],
            "jj_change_id": candidate["jj_change_id"],
            "git_tree": candidate.get("git_tree"),
            "baseline_revision": baseline,
            "source_change_ids": integrated["source_change_ids"],
            "source_commit_ids": integrated["source_commit_ids"],
            "parent_commit_ids": identity["parent_commit_ids"],
            "integrated_paths": integrated["integrated_paths"],
            "unresolved_conflicts": False,
            "conflict_resolution_authority": "DENIED",
            "integration_mode": "CONTENT_NEUTRAL_DISJOINT_PATHS",
        }
        admission_core["admission_digest"] = f"sha256:{canonical_digest(admission_core)}"
        admission, _ = governed_state.append_receipt(
            self.governance, "CANDIDATE_INTEGRATION_ADMISSION", admission_core,
            recorded_at="2026-08-04T00:00:00Z",
        )
        return workspace, candidate, admission["receipt_id"]

    @staticmethod
    def payload_digest(payload):
        return filesystem.payload_digest(payload)

    def envelope(self, binding, *, operation, payload, key):
        return {
            "schema": "bbk.governed-filesystem-execution.v1",
            "host_version": "omp/16.4.8",
            "session_id": binding["request"]["session_id"],
            "invocation_id": binding["request"]["invocation_id"],
            "intent": {
                "schema": "bbk.mutation-intent.v1",
                "binding_ref": binding["binding_id"],
                "operation": operation,
                "path": "src/product.txt",
                "content_or_patch_digest": self.payload_digest(payload),
                "expected_precondition": {"kind": "PRESENT"},
                "mutation_class": "PRODUCT_CONTENT" if operation != "READ" else "READ_ONLY",
                "idempotency_key": key,
            },
            "payload": payload,
        }

    def activate(self, compiled):
        registry.admit_spawn_dispatch(
            self.governance,
            dispatch_ref=compiled["dispatch_ref"],
            dispatch_input_digest=compiled["dispatch_input_digest"],
            parent_session_id="parent-session-1",
            tool_call_id="task-call-review-1",
            host_version="omp/16.4.8",
            observed_at="2026-08-04T00:00:02Z",
        )
        return registry.activate_spawn_session(
            self.governance,
            planned_binding_ref=compiled["planned_binding_ref"],
            actual_session_id="actual-review-session-1",
            packet_digest=compiled["worker_packet"]["packet_digest"],
            host_version="omp/16.4.8",
            observed_at="2026-08-04T00:00:03Z",
        )

    def test_compile_freezes_existing_candidate_without_allocating_workspace_or_change(self):
        schema_validate(self.request(), "bbk-bound-read-only-task-create-v1.schema.json")
        siblings_before = sorted(path.name for path in self.base.iterdir())
        result = self.compile()
        schema_validate(result, "bbk-bound-read-only-task-v1.schema.json")
        schema_validate(
            next(
                item["content"]
                for item in governed_state.all_receipts(self.governance)
                if item["receipt_kind"] == "READ_ONLY_TASK_REGISTRATION"
            ),
            "bbk-read-only-task-registration-v1.schema.json",
        )
        self.assertEqual(siblings_before, sorted(path.name for path in self.base.iterdir()))
        self.assertEqual(str(self.candidate), result["candidate"]["workspace_path"])
        self.assertEqual(self.identity_before["jj_change_id"], result["candidate"]["jj_change_id"])
        self.assertEqual(self.identity_before["jj_change_id"], jj_adapter.identity(self.candidate, jj_path=JJ)["jj_change_id"])
        self.assertEqual("bbk_reviewer", result["dispatch_input"]["tasks"][0]["agent"])
        self.assertEqual(result["dispatch_ref"], registry.parse_dispatch_ref(result["dispatch_input"]))
        self.assertNotIn("Review the exact", str(result["dispatch_input"]))
        self.assertTrue(result["planned_session_id"].startswith("planned-session:"))
        self.assertNotIn("Review the exact", str(governed_state.all_receipts(self.governance)))

    def test_exact_retry_reuses_binding_registration_and_candidate_identity(self):
        first = self.compile()
        second = self.compile()
        self.assertTrue(second["idempotent_reuse"])
        self.assertEqual(first["planned_binding_ref"], second["planned_binding_ref"])
        self.assertEqual(first["task_input_digest"], second["task_input_digest"])
        self.assertEqual(first["dispatch_ref"], second["dispatch_ref"])
        self.assertEqual(first["dispatch_input_digest"], second["dispatch_input_digest"])
        registrations = [
            item for item in governed_state.all_receipts(self.governance)
            if item["receipt_kind"] == "READ_ONLY_TASK_REGISTRATION"
        ]
        self.assertEqual(1, len(registrations))

    def test_admission_activation_allows_read_and_blocks_write_before_effect(self):
        compiled = self.compile()
        activation = self.activate(compiled)
        active = activation["binding"]
        read = filesystem.execute(
            self.governance,
            self.envelope(active, operation="READ", payload={}, key="read-review-1"),
            jj_path=JJ,
        )
        self.assertEqual("PASS", read["status"])
        self.assertEqual("baseline\n", read["content"])
        before = (self.candidate / "src" / "product.txt").read_bytes()
        payload = {"content": "forbidden\n", "encoding": "utf-8"}
        blocked = filesystem.execute(
            self.governance,
            self.envelope(active, operation="WRITE", payload=payload, key="write-review-1"),
            jj_path=JJ,
        )
        self.assertEqual("BLOCK", blocked["status"])
        self.assertEqual(before, (self.candidate / "src" / "product.txt").read_bytes())
        self.assertEqual(self.identity_before["jj_change_id"], jj_adapter.identity(self.candidate, jj_path=JJ)["jj_change_id"])


    def test_integrated_candidate_requires_current_candidate_admission(self):
        with self.assertRaisesRegex(read_only_spawn.ReadOnlySpawnError, "CANDIDATE_ADMISSION_REQUIRED"):
            self.compile(
                candidate_id="candidate:integrated",
                semantic_scope=["candidate:integrated"],
                idempotency_key="bind-integrated-without-admission",
            )

    def test_exact_two_parent_candidate_admission_allows_read_only_binding(self):
        workspace, candidate, admission_ref = self.integrated_candidate()
        result = self.compile(
            workspace_ref=str(workspace),
            candidate_id=candidate["candidate_id"],
            candidate_admission_ref=admission_ref,
            semantic_scope=["candidate:integrated"],
            idempotency_key="bind-integrated-with-admission",
        )
        self.assertEqual(admission_ref, result["candidate_admission_ref"])
        self.assertEqual(candidate["digest"], result["candidate"]["digest"])

    def test_integrated_candidate_admission_fails_closed_after_candidate_drift(self):
        workspace, candidate, admission_ref = self.integrated_candidate()
        (workspace / "src" / "worker-a" / "result.txt").write_text("changed\n", encoding="utf-8")
        with self.assertRaisesRegex(read_only_spawn.ReadOnlySpawnError, "CANDIDATE_ADMISSION_MISMATCH"):
            self.compile(
                workspace_ref=str(workspace),
                candidate_id=candidate["candidate_id"],
                candidate_admission_ref=admission_ref,
                semantic_scope=["candidate:integrated"],
                idempotency_key="bind-integrated-after-drift",
            )

    def test_integrated_candidate_requires_current_candidate_admission_receipt(self):
        with self.assertRaisesRegex(read_only_spawn.ReadOnlySpawnError, "CANDIDATE_ADMISSION_REQUIRED"):
            self.compile(
                candidate_id="candidate:alpha17-manual:integrated",
                semantic_scope=["candidate:integrated"],
                idempotency_key="bind-integrated-without-admission",
            )

    def test_writable_child_parent_mismatch_and_idempotency_collision_fail_closed(self):
        with self.assertRaisesRegex(read_only_spawn.ReadOnlySpawnError, "CHILD_NOT_READ_ONLY"):
            self.compile(role="bbk_worker", return_contract="bbk.worker-return.v2", idempotency_key="bind-worker-invalid")
        with self.assertRaisesRegex(read_only_spawn.ReadOnlySpawnError, "PARENT_CORRELATION_MISMATCH"):
            self.compile(parent_invocation_id="wrong", idempotency_key="bind-wrong-parent")
        self.compile()
        with self.assertRaisesRegex(read_only_spawn.ReadOnlySpawnError, "IDEMPOTENCY_COLLISION"):
            self.compile(assignment="Different read-only assignment")

    def test_cwd_workspace_escape_and_governance_root_conflation_are_rejected(self):
        ambient = self.base / "ambient"
        ambient.mkdir()
        previous = Path.cwd()
        try:
            os.chdir(ambient)
            result = self.compile(idempotency_key="bind-from-ambient")
        finally:
            os.chdir(previous)
        self.assertEqual(str(self.candidate), result["candidate"]["workspace_path"])
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: outside.exists() and __import__("shutil").rmtree(outside))
        with self.assertRaisesRegex(read_only_spawn.ReadOnlySpawnError, "WORKSPACE_INVALID"):
            self.compile(workspace_ref=str(outside), idempotency_key="bind-outside")
        with self.assertRaisesRegex(read_only_spawn.ReadOnlySpawnError, "CONFLATES_GOVERNANCE_ROOT"):
            self.compile(workspace_ref=str(self.governance), idempotency_key="bind-root")


if __name__ == "__main__":
    unittest.main()
