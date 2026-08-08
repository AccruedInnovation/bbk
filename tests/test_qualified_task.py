from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import governed_state  # noqa: E402
import omp_binding_registry as registry  # noqa: E402
import qualified_task  # noqa: E402
from substrate import jj_adapter, mise_adapter  # noqa: E402
from tests._fake_executable import write_python_executable  # noqa: E402
from tests._alpha17_surface_support import (  # noqa: E402
    JJ,
    fake_mise,
    init_candidate,
    schema_validate,
    worker_binding,
)


@unittest.skipUnless(Path(JJ).is_file(), "real jj executable is required")
class QualifiedTaskTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.governance = self.base / "campaign"
        self.governance.mkdir()
        self.candidate = init_candidate(self.base / "worker-candidate")
        self.binding = worker_binding(registry, jj_adapter, self.governance, self.candidate)
        self.mise = fake_mise(self.base / "mise")
        self.environment = {**os.environ, "BBK_ALLOW_TEST_ADAPTER": "1", "PATH": os.environ.get("PATH", "")}
        os.environ["BBK_ALLOW_TEST_ADAPTER"] = "1"

    def tearDown(self):
        os.environ.pop("BBK_ALLOW_TEST_ADAPTER", None)
        self.temporary.cleanup()

    def request(self, **changes):
        value = {
            "schema": "bbk.bound-qualified-task-execution.v1",
            "host_version": "omp/16.4.8",
            "session_id": "worker-session-1",
            "invocation_id": "worker-invocation-1",
            "binding_ref": self.binding["binding_id"],
            "task": "verify:candidate",
            "arguments": [],
            "environment_allowlist": ["LANG"],
            "idempotency_key": "qualified-task-1",
        }
        value.update(changes)
        return value

    def execute(self, **changes):
        return qualified_task.execute_bound_task(
            self.governance,
            self.request(**changes),
            jj_path=JJ,
            mise_path=self.mise,
            environment=self.environment,
            test_adapter=True,
            recorded_at="2026-08-04T00:00:01Z",
        )

    def test_bound_task_derives_candidate_and_toolchain_and_preserves_candidate(self):
        schema_validate(self.request(), "bbk-bound-qualified-task-execution-v1.schema.json")
        before_product = (self.candidate / "src" / "product.txt").read_bytes()
        result = self.execute()
        schema_validate(result, "bbk-bound-qualified-task-result-v1.schema.json")
        self.assertEqual("PASS", result["status"])
        self.assertTrue(result["candidate_unchanged"])
        self.assertEqual(result["candidate_before"]["digest"], result["candidate_after"]["digest"])
        self.assertEqual(mise_adapter.toolchain_definition_digest(self.candidate), result["toolchain_definition_digest"])
        self.assertEqual(str(self.mise), result["mise_path"])
        self.assertIn("mise TEST-1.0", result["mise_version"])
        self.assertEqual(before_product, (self.candidate / "src" / "product.txt").read_bytes())
        self.assertFalse((self.candidate / ".bbk" / "governance").exists())
        kinds = [item["receipt_kind"] for item in governed_state.all_receipts(self.governance)]
        self.assertIn("QUALIFIED_TASK", kinds)
        self.assertIn("BOUND_QUALIFIED_TASK", kinds)

    def test_exact_retry_reuses_outer_receipt_without_rerunning_mise(self):
        first = self.execute()
        self.mise = write_python_executable(self.mise, "raise SystemExit(99)\n")
        second = self.execute()
        self.assertTrue(second["idempotent_reuse"])
        self.assertFalse(second["receipt_created"])
        self.assertEqual(first["receipt_ref"], second["receipt_ref"])
        wrappers = [item for item in governed_state.all_receipts(self.governance) if item["receipt_kind"] == "BOUND_QUALIFIED_TASK"]
        self.assertEqual(1, len(wrappers))

    def test_task_failure_and_candidate_mutation_are_distinct_truthful_failures(self):
        failing = fake_mise(self.base / "mise-fail", exit_status=7)
        failed = qualified_task.execute_bound_task(
            self.governance,
            self.request(idempotency_key="qualified-fail"),
            jj_path=JJ,
            mise_path=failing,
            environment=self.environment,
            test_adapter=True,
        )
        self.assertEqual("FAIL", failed["status"])
        self.assertEqual("QUALIFIED_TASK_FAILED", failed["reason_code"])
        self.assertTrue(failed["candidate_unchanged"])

        mutating = fake_mise(self.base / "mise-mutate", mutate=True)
        mutated = qualified_task.execute_bound_task(
            self.governance,
            self.request(idempotency_key="qualified-mutate"),
            jj_path=JJ,
            mise_path=mutating,
            environment=self.environment,
            test_adapter=True,
        )
        schema_validate(mutated, "bbk-bound-qualified-task-result-v1.schema.json")
        self.assertEqual("FAIL", mutated["status"])
        self.assertEqual("QUALIFIED_TASK_CANDIDATE_MUTATED", mutated["reason_code"])
        self.assertFalse(mutated["candidate_unchanged"])
        self.assertEqual("DETECT_ONLY_NO_OS_SANDBOX", mutated["effect_boundary"])
        self.assertEqual("changed", (self.candidate / "src" / "product.txt").read_text(encoding="utf-8"))

    def test_request_cannot_supply_candidate_or_toolchain_authority(self):
        with self.assertRaisesRegex(qualified_task.QualifiedTaskError, "SCHEMA_INVALID"):
            self.execute(candidate_digest="sha256:" + "a" * 64)
        with self.assertRaisesRegex(qualified_task.QualifiedTaskError, "SCHEMA_INVALID"):
            self.execute(toolchain_definition_digest="sha256:" + "b" * 64)
        with self.assertRaisesRegex(qualified_task.QualifiedTaskError, "CORRELATION_MISMATCH"):
            self.execute(session_id="wrong-session", idempotency_key="wrong-session")
        with self.assertRaisesRegex(qualified_task.QualifiedTaskError, "HOST_UNQUALIFIED"):
            self.execute(host_version="omp/changed", idempotency_key="wrong-host")

    def test_role_without_task_surface_and_governance_root_conflation_are_blocked(self):
        identity = jj_adapter.identity(self.candidate, jj_path=JJ)
        reviewer = registry.create_initial_binding(
            self.governance,
            {
                **self.binding["request"],
                "session_id": "review-session",
                "invocation_id": "review-invocation",
                "role": "bbk_reviewer",
                "return_contract": "bbk.reviewer-return.v2",
                "scope": {
                    "path_prefixes": [str(self.candidate)],
                    "mutation_classes": ["READ_ONLY"],
                    "semantic_scope": ["candidate:test"],
                },
                "jj_change_id": identity["jj_change_id"],
                "idempotency_key": "review-binding",
            },
            capability_ref="role:bbk_reviewer@1.0.0-alpha.17",
        )[0]
        with self.assertRaisesRegex(qualified_task.QualifiedTaskError, "ROLE_DENIED"):
            qualified_task.execute_bound_task(
                self.governance,
                self.request(
                    session_id="review-session",
                    invocation_id="review-invocation",
                    binding_ref=reviewer["binding_id"],
                    idempotency_key="review-task",
                ),
                jj_path=JJ,
                mise_path=self.mise,
                environment=self.environment,
                test_adapter=True,
            )

        conflated = registry.create_initial_binding(
            self.governance,
            {
                **self.binding["request"],
                "session_id": "root-worker-session",
                "invocation_id": "root-worker-invocation",
                "workspace_ref": str(self.governance),
                "scope": {
                    "path_prefixes": [str(self.governance.resolve())],
                    "mutation_classes": ["PRODUCT_CONTENT"],
                    "semantic_scope": ["component:test"],
                },
                "idempotency_key": "root-worker-binding",
            },
            capability_ref="role:bbk_worker@1.0.0-alpha.17",
        )[0]
        with self.assertRaisesRegex(qualified_task.QualifiedTaskError, "CONFLATES_GOVERNANCE_ROOT"):
            qualified_task.execute_bound_task(
                self.governance,
                self.request(
                    session_id="root-worker-session",
                    invocation_id="root-worker-invocation",
                    binding_ref=conflated["binding_id"],
                    idempotency_key="root-task",
                ),
                jj_path=JJ,
                mise_path=self.mise,
                environment=self.environment,
                test_adapter=True,
            )

    def test_idempotent_retry_detects_candidate_state_drift(self):
        self.execute()
        (self.candidate / "src" / "product.txt").write_text("drift\n", encoding="utf-8")
        with self.assertRaisesRegex(qualified_task.QualifiedTaskError, "IDEMPOTENCY_STATE_DRIFT"):
            self.execute()


if __name__ == "__main__":
    unittest.main()
