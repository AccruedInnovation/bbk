from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import gate_kernel  # noqa: E402
import governed_state  # noqa: E402
import omp_binding_registry as registry  # noqa: E402


class OmpBindingRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.workspace = self.root / "workspace"
        (self.workspace / "src").mkdir(parents=True)

    def tearDown(self):
        self.temporary.cleanup()

    def request(self, **changes):
        value = {
            "schema": "bbk.invocation-binding-create.v1",
            "session_id": "child-session-1",
            "parent_session_id": "parent-session-1",
            "invocation_id": "invocation-1",
            "role": "bbk_worker",
            "work_unit_id": "WU-TEST",
            "attempt_id": "attempt-1",
            "baseline_ref": "git:abc123",
            "candidate_ref": "candidate-1",
            "workspace_ref": str(self.workspace),
            "authority_ref": "authority:user",
            "scope": {
                "path_prefixes": [str(self.workspace / "src")],
                "mutation_classes": ["PRODUCT_CONTENT", "TEST_CONTENT"],
                "semantic_scope": ["component:test"],
            },
            "return_contract": "bbk.role-return.v2",
            "jj_change_id": "change-1",
            "idempotency_key": "binding-1",
        }
        value.update(changes)
        return value

    def binding(self):
        return registry.create_initial_binding(
            self.root,
            self.request(),
            capability_ref="role:bbk_worker@1.0.0-alpha.17",
            created_at="2026-08-04T00:00:00Z",
        )[0]

    def test_enforcement_boundary_is_honest_about_host_and_hook_phase(self):
        self.assertEqual("ENFORCED", registry.enforcement_boundary("omp/16.4.8", "TOOL_CALL"))
        self.assertEqual("DETECT_ONLY", registry.enforcement_boundary("omp/16.4.8", "TOOL_EXECUTION_END"))
        self.assertEqual("UNQUALIFIED", registry.enforcement_boundary("omp/17.0.0", "TOOL_CALL"))
        status = registry.enforcement_status("omp/16.4.8")
        self.assertEqual("QUALIFIED", status["qualification"])
        self.assertEqual("UNQUALIFIED", status["boundaries"]["operating_system_sandbox"])
        self.assertIn("never workspace", " ".join(status["notes"]))

    def test_normalized_host_event_correlates_without_raw_payload(self):
        binding = self.binding()
        event = registry.normalize_host_event(
            {
                "host_version": "omp/16.4.8",
                "event_type": "TOOL_CALL",
                "session_id": "child-session-1",
                "parent_session": "parent-session-1",
                "task_or_tool_id": "tool-call-1",
                "payload_digest": "a" * 64,
                "observed_at": "2026-08-04T00:00:01Z",
            },
            binding=binding,
        )
        self.assertEqual("bbk.host-event.v1", event["schema"])
        self.assertEqual("ENFORCED", event["enforcement_boundary"])
        self.assertEqual(binding["binding_id"], event["correlation"]["binding_ref"])
        self.assertEqual("candidate-1", event["correlation"]["candidate_ref"])
        self.assertNotIn("raw_payload", event)
        self.assertNotIn("prompt", event)
        self.assertRegex(event["payload_digest"], r"^sha256:[0-9a-f]{64}$")

    def test_raw_prompt_or_credential_fields_are_rejected(self):
        base = {
            "host_version": "omp/16.4.8",
            "event_type": "TOOL_CALL",
            "session_id": "session-1",
            "parent_session": "",
            "task_or_tool_id": "tool-1",
            "payload_digest": "a" * 64,
            "observed_at": "2026-08-04T00:00:00Z",
        }
        for field in ("prompt", "api_key", "authorization_token"):
            with self.subTest(field=field), self.assertRaisesRegex(registry.OmpBindingError, "SENSITIVE"):
                registry.normalize_host_event({**base, field: "must-not-persist"})

    def test_host_event_receipt_is_immutable_and_idempotent(self):
        binding = self.binding()
        envelope = {
            "host_version": "omp/16.4.8",
            "event_type": "TASK_LIFECYCLE",
            "session_id": "child-session-1",
            "parent_session": "parent-session-1",
            "task_or_tool_id": "task-1",
            "payload_digest": "b" * 64,
            "observed_at": "2026-08-04T00:00:02Z",
        }
        first, created = registry.record_host_event(self.root, envelope, binding_ref=binding["binding_id"])
        second, created_again = registry.record_host_event(self.root, envelope, binding_ref=binding["binding_id"])
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first, second)
        self.assertEqual("DETECT_ONLY", first["content"]["enforcement_boundary"])

    def test_wake_inject_resume_retain_exact_binding(self):
        binding = self.binding()
        for event in ("WAKE", "INJECT", "RESUME"):
            with self.subTest(event=event):
                result = registry.retain_binding(
                    self.root,
                    event_type=event,
                    binding_ref=binding["binding_id"],
                    session_id="child-session-1",
                    invocation_id="invocation-1",
                    payload_digest=gate_kernel.canonical_digest({"event": event}),
                    observed_at="2026-08-04T00:00:03Z",
                )
                self.assertEqual("RETAINED", result["status"])
                self.assertEqual(binding["immutable_digest"], result["immutable_binding_digest"])

        with self.assertRaisesRegex(registry.OmpBindingError, "CONTINUITY_MISMATCH"):
            registry.retain_binding(
                self.root,
                event_type="WAKE",
                binding_ref=binding["binding_id"],
                session_id="other-session",
                invocation_id="invocation-1",
                payload_digest="c" * 64,
            )

    def test_retry_requires_explicit_supersession_and_stable_authority(self):
        first = self.binding()
        successor_request = self.request(
            session_id="child-session-2",
            invocation_id="invocation-2",
            attempt_id="attempt-2",
            candidate_ref="candidate-2",
            workspace_ref=str(self.workspace),
            jj_change_id="change-2",
            idempotency_key="binding-2",
            supersedes=first["binding_id"],
        )
        successor, created = registry.retry_binding(
            self.root,
            predecessor_ref=first["binding_id"],
            successor_request=successor_request,
            capability_ref="role:bbk_worker@1.0.0-alpha.17",
        )
        self.assertTrue(created)
        self.assertEqual(first["binding_id"], successor["supersedes"])
        self.assertIsNone(governed_state.resolve_binding(self.root, binding_id=first["binding_id"]))
        self.assertEqual(successor, governed_state.resolve_binding(self.root, session_id="child-session-2"))

        with self.assertRaisesRegex(registry.OmpBindingError, "AUTHORITY_DRIFT"):
            registry.retry_binding(
                self.root,
                predecessor_ref=successor["binding_id"],
                successor_request={
                    **successor_request,
                    "session_id": "child-session-3",
                    "invocation_id": "invocation-3",
                    "attempt_id": "attempt-3",
                    "authority_ref": "authority:model",
                    "idempotency_key": "binding-3",
                    "supersedes": successor["binding_id"],
                },
                capability_ref="role:bbk_worker@1.0.0-alpha.17",
            )

    def test_spawn_reservation_is_exact_active_and_single_use(self):
        binding = self.binding()
        digest = gate_kernel.canonical_digest(
            {"agent": "bbk_worker", "name": "worker-one", "task": "bounded work"},
            prefixed=True,
        )
        reservation = registry.create_spawn_reservation(
            self.root,
            binding_ref=binding["binding_id"],
            parent_session_id="parent-session-1",
            task_name="worker-one",
            agent="bbk_worker",
            input_digest=digest,
        )
        self.assertEqual("RESERVED", reservation["status"])
        admitted = registry.admit_spawn(
            self.root,
            input_digest=digest,
            parent_session_id="parent-session-1",
            task_name="worker-one",
            agent="bbk_worker",
            tool_call_id="tool-call-1",
            host_version="omp/16.4.8",
            observed_at="2026-08-04T00:00:04Z",
        )
        self.assertEqual("ADMITTED", admitted["status"])
        self.assertEqual("ENFORCED", admitted["enforcement_boundary"])
        retry = registry.admit_spawn(
            self.root,
            input_digest=digest,
            parent_session_id="parent-session-1",
            task_name="worker-one",
            agent="bbk_worker",
            tool_call_id="tool-call-1",
            host_version="omp/16.4.8",
        )
        self.assertTrue(retry["idempotent_reuse"])
        with self.assertRaisesRegex(registry.OmpBindingError, "ALREADY_CONSUMED"):
            registry.admit_spawn(
                self.root,
                input_digest=digest,
                parent_session_id="parent-session-1",
                task_name="worker-one",
                agent="bbk_worker",
                tool_call_id="tool-call-2",
                host_version="omp/16.4.8",
            )

    def test_binding_execution_policy_exposes_structured_return_fence(self):
        binding = registry.create_initial_binding(
            self.root,
            self.request(
                return_transport_mode="STRUCTURED_RETURN_ONLY",
                material_transport_reason="",
            ),
            capability_ref="role:bbk_worker@1.0.0-alpha.17",
            created_at="2026-08-04T00:00:00Z",
        )[0]
        policy = registry.binding_execution_policy(self.root, session_id="child-session-1")
        self.assertEqual("PASS", policy["status"])
        self.assertEqual(binding["binding_id"], policy["binding_ref"])
        self.assertEqual("STRUCTURED_RETURN_ONLY", policy["return_transport_mode"])
        self.assertEqual("", policy["material_transport_reason"])

    def test_spawn_without_exact_reservation_fails_closed(self):
        self.binding()
        with self.assertRaisesRegex(registry.OmpBindingError, "BINDING_REQUIRED"):
            registry.admit_spawn(
                self.root,
                input_digest="d" * 64,
                parent_session_id="parent-session-1",
                task_name="worker-one",
                agent="bbk_worker",
                tool_call_id="tool-call-1",
                host_version="omp/16.4.8",
            )

    def test_cli_status_reports_unqualified_unknown_host(self):
        completed = subprocess.run(
            [sys.executable, str(TOOLS / "omp_binding_registry.py"), "--root", str(self.root), "status", "--host-version", "omp/99"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        value = json.loads(completed.stdout)
        self.assertEqual("UNQUALIFIED", value["qualification"])


if __name__ == "__main__":
    unittest.main()
