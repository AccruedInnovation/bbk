from __future__ import annotations

import json
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


class GovernedStateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()

    def tearDown(self):
        self.temporary.cleanup()

    def binding_request(self, **changes):
        value = {
            "schema": "bbk.invocation-binding-create.v1",
            "session_id": "session-1",
            "invocation_id": "invocation-1",
            "role": "bbk_worker",
            "work_unit_id": "WU-1",
            "attempt_id": "attempt-1",
            "baseline_ref": "git:abc",
            "candidate_ref": "candidate-1",
            "workspace_ref": str(self.workspace),
            "authority_ref": "authority:user",
            "scope": {
                "path_prefixes": [str(self.workspace / "src")],
                "mutation_classes": ["PRODUCT_CONTENT"],
                "semantic_scope": ["component:test"],
            },
            "return_contract": "bbk.role-return.v2",
            "idempotency_key": "bind-1",
        }
        value.update(changes)
        return value

    def gate_request(self):
        policy = gate_kernel.load_policy()
        return policy, {
            "schema": "bbk.gate-evaluation-request.v1",
            "policy_ref": f"{policy['policy_id']}@{policy['policy_version']}",
            "actor": {"role": "bbk_worker", "actor_id": "actor-1", "actor_kind": "MODEL"},
            "authority": {"authority_ref": "authority:user", "holder_kind": "USER", "scopes": []},
            "intent": {"operation": "WRITE", "mutation_class": "PRODUCT_CONTENT", "within_scope": True},
            "state_snapshot": {"snapshot_ref": "snapshot-1", "binding_valid": True},
            "candidate_ref": "candidate-1",
            "work_unit_id": "WU-1",
            "idempotency_key": "gate-1",
        }

    def test_gate_receipt_retry_is_idempotent_and_immutable(self):
        policy, request = self.gate_request()
        decision = gate_kernel.evaluate(policy, request)
        first, created = governed_state.append_gate_receipt(
            self.root, request, decision, invocation_id="invocation-1", recorded_at="2026-08-04T00:00:00Z"
        )
        second, created_again = governed_state.append_gate_receipt(
            self.root, request, decision, invocation_id="invocation-1", recorded_at="2026-08-05T00:00:00Z"
        )
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first, second)
        self.assertEqual(1, len(governed_state.all_receipts(self.root)))

    def test_generic_receipt_collision_fails_closed(self):
        record, _ = governed_state.append_receipt(
            self.root, "TEST", {"value": 1}, receipt_id="sha256:" + "a" * 64
        )
        self.assertEqual(1, record["content"]["value"])
        with self.assertRaisesRegex(governed_state.GovernanceStateError, "COLLISION"):
            governed_state.append_receipt(
                self.root, "TEST", {"value": 2}, receipt_id="sha256:" + "a" * 64
            )

    def test_binding_is_immutable_and_supersession_is_derived(self):
        first, created = governed_state.create_binding(
            self.root, self.binding_request(), capability_ref="role:bbk_worker@1", created_at="2026-08-04T00:00:00Z"
        )
        self.assertTrue(created)
        retry, created_again = governed_state.create_binding(
            self.root, self.binding_request(), capability_ref="role:bbk_worker@1", created_at="2026-08-05T00:00:00Z"
        )
        self.assertFalse(created_again)
        self.assertEqual(first, retry)

        successor_request = self.binding_request(
            invocation_id="invocation-2",
            attempt_id="attempt-2",
            idempotency_key="bind-2",
            supersedes=first["binding_id"],
        )
        successor, _ = governed_state.create_binding(
            self.root, successor_request, capability_ref="role:bbk_worker@1"
        )
        self.assertEqual(successor, governed_state.resolve_binding(self.root, session_id="session-1"))
        projection = json.loads(
            (governed_state.state_root(self.root) / "projections" / "bindings.json").read_text(
                encoding="utf-8"
            )
        )
        by_id = {item["binding_id"]: item for item in projection["bindings"]}
        self.assertEqual("SUPERSEDED", by_id[first["binding_id"]]["status"])
        self.assertEqual(successor["binding_id"], by_id[first["binding_id"]]["superseded_by"])
        original = governed_state.all_bindings(self.root)[0]
        self.assertEqual("ACTIVE", original["status"], "canonical predecessor must not be rewritten")

    def test_scope_prefix_outside_workspace_is_rejected(self):
        request = self.binding_request()
        request["scope"]["path_prefixes"] = [str(self.root.parent)]
        with self.assertRaisesRegex(governed_state.GovernanceStateError, "SCOPE_ESCAPE"):
            governed_state.create_binding(self.root, request, capability_ref="role:bbk_worker@1")

    def test_projection_rebuild_is_reproducible_and_nonauthoritative(self):
        governed_state.create_binding(self.root, self.binding_request(), capability_ref="role:bbk_worker@1")
        first = governed_state.rebuild_projections(self.root)
        digest = governed_state.projection_digest(self.root)
        for path in (governed_state.state_root(self.root) / "projections").glob("*"):
            path.unlink()
        second = governed_state.rebuild_projections(self.root)
        self.assertEqual(first, second)
        self.assertEqual(digest, governed_state.projection_digest(self.root))
        self.assertEqual("NON_AUTHORITATIVE_PROJECTION", second["authority"])


if __name__ == "__main__":
    unittest.main()
