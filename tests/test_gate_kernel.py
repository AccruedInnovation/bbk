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

import gate_kernel  # noqa: E402


class GateKernelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = gate_kernel.load_policy()

    def request(self, **changes):
        value = {
            "schema": "bbk.gate-evaluation-request.v1",
            "policy_ref": f"{self.policy['policy_id']}@{self.policy['policy_version']}",
            "actor": {
                "role": "bbk_worker",
                "actor_id": "actor:worker-1",
                "actor_kind": "MODEL",
            },
            "authority": {
                "authority_ref": "authority:user-1",
                "holder_kind": "USER",
                "scopes": ["candidate:candidate-1", "work-unit:WU-TEST"],
                "standing": True,
            },
            "intent": {
                "operation": "WRITE",
                "mutation_class": "PRODUCT_CONTENT",
                "path": "src/a.txt",
                "within_scope": True,
                "sealed_subject": False,
                "accepted_subject": False,
            },
            "state_snapshot": {
                "snapshot_ref": "snapshot:1",
                "binding_ref": "binding:1",
                "binding_valid": True,
                "evidence_current": True,
                "manual_gate_pass": False,
            },
            "candidate_ref": "candidate-1",
            "work_unit_id": "WU-TEST",
            "idempotency_key": "idem-1",
            "override": {
                "present": False,
                "requested_by_kind": "NONE",
                "authority_ref": "authority:user-1",
                "scopes": [],
            },
        }
        for key, item in changes.items():
            if key in value and isinstance(value[key], dict) and isinstance(item, dict):
                value[key].update(item)
            else:
                value[key] = item
        return value

    def test_bound_worker_write_is_allowed_and_deterministic(self):
        request = self.request()
        first = gate_kernel.evaluate(self.policy, request)
        second = gate_kernel.evaluate(copy.deepcopy(self.policy), copy.deepcopy(request))
        self.assertEqual("ALLOW", first["decision"])
        self.assertEqual([], first["reason_codes"])
        self.assertEqual(first, second)
        self.assertRegex(first["receipt_ref"], r"^sha256:[0-9a-f]{64}$")

    def test_orchestrator_product_mutation_is_invariant_block(self):
        decision = gate_kernel.evaluate(
            self.policy,
            self.request(actor={"role": "bbk_root_orchestrator"}),
        )
        self.assertEqual("BLOCK", decision["decision"])
        self.assertIn("ROLE_MUTATION_CLASS_FORBIDDEN", decision["reason_codes"])
        self.assertFalse(decision["override_eligibility"]["eligible"])

    def test_reviewer_mutation_is_invariant_block(self):
        decision = gate_kernel.evaluate(
            self.policy,
            self.request(actor={"role": "bbk_reviewer"}),
        )
        self.assertEqual("BLOCK", decision["decision"])
        self.assertIn("READ_ONLY_ROLE_MUTATION_FORBIDDEN", decision["reason_codes"])

    def test_explicit_role_capability_denial_is_invariant_block(self):
        decision = gate_kernel.evaluate(
            self.policy,
            self.request(intent={"capability_allowed": False}),
        )
        self.assertEqual("BLOCK", decision["decision"])
        self.assertIn("ROLE_CAPABILITY_FORBIDDEN", decision["reason_codes"])
        self.assertFalse(decision["override_eligibility"]["eligible"])

    def test_unbound_worker_and_scope_escape_are_both_reported(self):
        decision = gate_kernel.evaluate(
            self.policy,
            self.request(
                intent={"within_scope": False},
                state_snapshot={"binding_valid": False},
            ),
        )
        self.assertEqual("BLOCK", decision["decision"])
        self.assertEqual(
            ["WORKER_BINDING_REQUIRED", "WORKSPACE_SCOPE_ESCAPE"],
            decision["reason_codes"],
        )

    def test_enforce_rule_requires_exact_user_override(self):
        request = self.request(
            intent={
                "operation": "RESOLVE_CONTENT_CONFLICT",
                "mutation_class": "INTEGRATION_CONTENT",
            },
            actor={"role": "bbk_root_orchestrator"},
        )
        decision = gate_kernel.evaluate(self.policy, request)
        self.assertEqual("REQUIRE_OVERRIDE", decision["decision"])
        self.assertTrue(decision["override_eligibility"]["eligible"])
        self.assertIn("INTEGRATION_WORKER_REQUIRED", decision["reason_codes"])

        rule_id = next(
            rule["rule_id"]
            for rule in self.policy["rules"]
            if rule["reason_code"] == "INTEGRATION_WORKER_REQUIRED"
        )
        request["override"] = {
            "present": True,
            "requested_by_kind": "HUMAN",
            "authority_ref": "authority:user-1",
            "scopes": [
                f"rule:{rule_id}",
                "candidate:candidate-1",
                "work-unit:WU-TEST",
            ],
            "decision_ref": "decision:user-1",
        }
        decision = gate_kernel.evaluate(self.policy, request)
        self.assertEqual("ALLOW", decision["decision"])
        self.assertIn(
            "OVERRIDE_APPLIED:INTEGRATION_WORKER_REQUIRED",
            decision["observations"],
        )

    def test_model_self_waiver_is_never_effective(self):
        request = self.request(
            intent={
                "operation": "RESOLVE_CONTENT_CONFLICT",
                "mutation_class": "INTEGRATION_CONTENT",
            },
            actor={"role": "bbk_root_orchestrator"},
            override={
                "present": True,
                "requested_by_kind": "MODEL",
                "authority_ref": "authority:user-1",
                "scopes": [
                    "rule:content-changing-integration-conflict",
                    "candidate:candidate-1",
                    "work-unit:WU-TEST",
                ],
            },
        )
        decision = gate_kernel.evaluate(self.policy, request)
        self.assertEqual("BLOCK", decision["decision"])
        self.assertIn("MODEL_SELF_WAIVER_FORBIDDEN", decision["reason_codes"])

    def test_observe_rule_does_not_block(self):
        decision = gate_kernel.evaluate(
            self.policy,
            self.request(
                intent={
                    "operation": "UNINTERCEPTED_SHELL_EFFECT",
                    "mutation_class": "UNKNOWN_SHELL_EFFECT",
                }
            ),
        )
        self.assertEqual("ALLOW", decision["decision"])
        self.assertIn("OBSERVED:SHELL_BOUNDARY_DETECT_ONLY", decision["observations"])

    def test_wrong_policy_reference_fails_closed(self):
        with self.assertRaisesRegex(gate_kernel.GateKernelError, "policy_ref"):
            gate_kernel.evaluate(self.policy, self.request(policy_ref="other@1"))

    def test_invalid_policy_cannot_make_invariant_overrideable(self):
        policy = copy.deepcopy(self.policy)
        policy["rules"][0]["override_eligibility"] = {
            "eligible": True,
            "authorities": ["USER"],
            "requires_exact_scope": True,
        }
        with self.assertRaisesRegex(gate_kernel.GateKernelError, "invariant"):
            gate_kernel.validate_policy(policy)

    def test_decision_conforms_to_schema_when_jsonschema_is_available(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed")
        schema = json.loads(
            (ROOT / "spec" / "schemas" / "bbk-gate-decision-v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        jsonschema.Draft202012Validator(schema).validate(
            gate_kernel.evaluate(self.policy, self.request())
        )


if __name__ == "__main__":
    unittest.main()
