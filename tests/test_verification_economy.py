from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import verification_economy as economy  # noqa: E402


class VerificationEconomyTests(unittest.TestCase):
    def verification_request(self):
        return {
            "schema": "bbk.verification-precheck.v1",
            "claim_id": "claim:package-integrity",
            "subject": {"kind": "package", "id": "pkg:1", "raw_digest": "sha256:" + "a" * 64},
            "method": {"method_id": "bbk-handoff-verify", "method_version": "v2", "tool_identity": "bbk@alpha17"},
            "context": {"configuration_digest": "sha256:" + "b" * 64},
            "invalidation_keys": [
                {"key": "subject.raw_digest", "value": "sha256:" + "a" * 64},
                {"key": "configuration_digest", "value": "sha256:" + "b" * 64},
            ],
            "producer": {"role": "bbk_worker", "semantic_run_id": "run:1", "physical_attempt_id": "attempt:1"},
        }

    def test_one_check_is_reused_across_three_consumers(self):
        request = self.verification_request()
        receipt = economy.create_receipt(request, {"status": "PASS", "evidence_refs": ["evidence:1"]}, observed_at="2026-08-05T00:00:00Z")
        results = [economy.pre_check(request, [receipt]) for _ in range(3)]
        self.assertEqual(["REUSED_RECEIPT"] * 3, [item["status"] for item in results])
        self.assertTrue(all(not item["execution_authorized"] for item in results))
        self.assertEqual({receipt["receipt_id"]}, {item["receipt_id"] for item in results})

    def test_changed_invalidation_key_authorizes_exactly_one_recheck(self):
        request = self.verification_request()
        receipt = economy.create_receipt(request, {"status": "PASS", "evidence_refs": []}, observed_at="2026-08-05T00:00:00Z")
        changed = copy.deepcopy(request)
        changed["invalidation_keys"][1]["value"] = "sha256:" + "c" * 64
        first = economy.pre_check(changed, [receipt])
        self.assertEqual("AUTHORIZED_CHECK", first["status"])
        successor = economy.create_receipt(changed, {"status": "PASS", "evidence_refs": []}, observed_at="2026-08-05T00:01:00Z")
        second = economy.pre_check(changed, [receipt, successor])
        self.assertEqual("REUSED_RECEIPT", second["status"])

    def test_explicit_independent_method_can_execute_despite_current_receipt(self):
        request = self.verification_request()
        receipt = economy.create_receipt(request, {"status": "PASS", "evidence_refs": []})
        request["independent_method_required"] = True
        result = economy.pre_check(request, [receipt])
        self.assertEqual("AUTHORIZED_CHECK", result["status"])
        self.assertEqual("INDEPENDENT_METHOD_REQUIRED", result["reason_code"])

    def complete_dispatch_request(self):
        return {
            "schema": "bbk.dispatch-admission-request.v1",
            "subject": {"work_unit_id": "WU-1", "revision": "r1"},
            "facts": {
                "work_scope_return": {"scope": ["src/**"], "return_route": "parent:1"},
                "authority_effect_fence": {"authority_ref": "auth:1", "effects": ["WORKSPACE_WRITE"]},
                "workspace_mutation_ownership": {"workspace": "/work/wu1", "owner": "attempt:1"},
                "inputs_toolchain_carrier_checks": {"inputs": ["input:1"], "toolchain": "mise:1", "carrier": "STRUCTURED_RETURN", "checks": ["test:unit"]},
            },
            "invalidation_keys": [{"key": "work_unit_revision", "value": "r1"}],
        }

    def test_four_facts_admit_immediate_dispatch(self):
        result = economy.dispatch_admission(self.complete_dispatch_request(), issued_at="2026-08-05T00:00:00Z")
        self.assertEqual("ADMITTED", result["status"])
        self.assertEqual([], result["blockers"])
        self.assertIn("Dispatch", result["smallest_next_action"])

    def test_each_missing_dispatch_fact_produces_only_that_typed_blocker(self):
        for field in list(self.complete_dispatch_request()["facts"]):
            request = self.complete_dispatch_request()
            request["facts"][field] = None
            result = economy.dispatch_admission(request)
            self.assertEqual("BLOCKED", result["status"])
            self.assertEqual([field], [item["fact"] for item in result["blockers"]])

    def test_pre_freeze_mechanical_defects_repair_in_same_attempt(self):
        for defect in (
            "LINE_ENDING", "BOM", "TERMINAL_NEWLINE", "SERIALIZATION", "PATH_NORMALIZATION",
            "BYTE_COUNT", "DIGEST", "MANIFEST", "PACKAGE", "PROFILE_PROJECTION",
        ):
            result = economy.mechanical_transition({
                "schema": "bbk.mechanical-transition-request.v1",
                "defect_class": defect,
                "candidate_frozen": False,
                "irreversible_or_external_effect_occurred": False,
                "changed_governing_keys": [],
            })
            self.assertEqual("SAME_ATTEMPT_REPAIR", result["transition"])
            self.assertTrue(result["same_semantic_run"])
            self.assertTrue(result["same_physical_attempt"])
            self.assertFalse(result["successor_plan_required"])
            self.assertEqual("AFFECTED_MECHANICAL_GATE_ONLY", result["recheck_scope"])

    def test_frozen_byte_repair_creates_successor_candidate_not_successor_plan(self):
        result = economy.mechanical_transition({
            "schema": "bbk.mechanical-transition-request.v1",
            "defect_class": "TERMINAL_NEWLINE",
            "candidate_frozen": True,
            "irreversible_or_external_effect_occurred": False,
            "changed_governing_keys": [],
        })
        self.assertEqual("SUCCESSOR_CANDIDATE", result["transition"])
        self.assertFalse(result["successor_plan_required"])

    def test_changed_shared_interface_routes_to_semantic_owner(self):
        result = economy.mechanical_transition({
            "schema": "bbk.mechanical-transition-request.v1",
            "defect_class": "SERIALIZATION",
            "candidate_frozen": False,
            "irreversible_or_external_effect_occurred": False,
            "changed_governing_keys": ["interface"],
        })
        self.assertEqual("SEMANTIC_OWNER_ESCALATION", result["transition"])
        self.assertTrue(result["successor_plan_required"])

    def test_metadata_only_change_runs_no_product_validator(self):
        result = economy.validator_scope({
            "schema": "bbk.validator-scope-request.v1",
            "changed_paths": [".bbk/evidence/receipt.json", ".bbk/status.md"],
            "inspected_inputs": ["src/**", "tests/**"],
            "candidate_frozen": True,
            "final_pass_already_recorded": False,
            "validator_implementation_changed": False,
            "validator_configuration_changed": False,
            "invalidation_key_changed": False,
        })
        self.assertFalse(result["targeted_checks_authorized"])
        self.assertFalse(result["broad_final_pass_authorized"])
        self.assertEqual("METADATA_ONLY_NO_INSPECTED_INPUT_CHANGE", result["reason_code"])

    def test_relevant_change_allows_targeted_and_one_frozen_final_pass(self):
        request = {
            "schema": "bbk.validator-scope-request.v1",
            "changed_paths": ["src/main.py"],
            "inspected_inputs": ["src/**"],
            "candidate_frozen": True,
            "final_pass_already_recorded": False,
            "validator_implementation_changed": False,
            "validator_configuration_changed": False,
            "invalidation_key_changed": False,
        }
        first = economy.validator_scope(request)
        self.assertTrue(first["targeted_checks_authorized"])
        self.assertTrue(first["broad_final_pass_authorized"])
        request["final_pass_already_recorded"] = True
        second = economy.validator_scope(request)
        self.assertFalse(second["broad_final_pass_authorized"])
        self.assertEqual(1, second["maximum_broad_final_passes"])

    def test_compatible_assertions_group_and_reviewer_requires_named_risk(self):
        base = {
            "candidate_ref": "candidate:1", "method_id": "pytest", "toolchain_ref": "mise:1",
            "environment_ref": "env:1", "fixture_ref": "fixture:1", "exposure_class": "LOCAL",
            "independence_requirement": "NONE", "deterministic_evidence_sufficient": True,
        }
        request = {"schema": "bbk.assurance-dispatch-request.v1", "assertions": [
            {**base, "assertion_id": "A-1"}, {**base, "assertion_id": "A-2"},
        ]}
        result = economy.assurance_dispatch(request)
        self.assertEqual(1, len(result["validator_assignments"]))
        self.assertEqual(1, result["evidence_operation_count"])
        self.assertEqual(0, result["reviewer_invocation_count"])
        request["assertions"].append({**base, "assertion_id": "A-3", "qualitative_risk": "cross-cutting API usability", "deterministic_evidence_sufficient": False})
        focused = economy.assurance_dispatch(request)
        self.assertEqual(1, focused["reviewer_invocation_count"])

    def test_planning_stops_when_work_is_executable(self):
        result = economy.planning_stop({"schema": "bbk.planning-stop-request.v1", "executable_work_exists": True, "unresolved_support_work": None})
        self.assertEqual("STOP_PLANNING", result["status"])
        self.assertFalse(result["support_work_authorized"])
        unsupported = economy.planning_stop({
            "schema": "bbk.planning-stop-request.v1", "executable_work_exists": True,
            "unresolved_support_work": {"material_risk": "", "unresolved_proposition": "x"},
        })
        self.assertEqual("NO_MATERIAL_SUPPORT_WORK", unsupported["status"])

    def test_receipts_persist_immutably_and_validate_against_schema(self):
        request = self.verification_request()
        receipt = economy.create_receipt(request, {"status": "PASS", "evidence_refs": []}, observed_at="2026-08-05T00:00:00Z")
        with tempfile.TemporaryDirectory() as directory:
            path = economy.persist_receipt(directory, receipt)
            self.assertEqual(path, economy.persist_receipt(directory, receipt))
            self.assertEqual(receipt, json.loads(path.read_text(encoding="utf-8")))
        try:
            import jsonschema
        except ImportError:
            return
        schema = json.loads((ROOT / "spec" / "schemas" / "bbk-verification-receipt-v1.schema.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(receipt)

    def test_reuse_has_zero_execution_and_integrity_tampering_is_not_current(self):
        request = self.verification_request()
        receipt = economy.create_receipt(request, {"status": "PASS", "evidence_refs": []})
        reused = economy.pre_check(request, [receipt])
        self.assertEqual(0, reused["execution_count"])
        self.assertFalse(reused["underlying_method_invoked"])
        tampered = copy.deepcopy(receipt)
        tampered["method"]["method_version"] = "changed"
        self.assertEqual("AUTHORIZED_CHECK", economy.pre_check(request, [tampered])["status"])

    def test_recurrence_fingerprint_ignores_volatile_carriers(self):
        base = {"logical_subject": {"id": "subject-1"}, "assertion": "A-1", "failure_code": "SCHEMA_SHAPE", "failure_class": "SCHEMA", "method_revision": "m5", "environment": {"python": "3.13"}}
        noisy = {**base, "observed_at": "2026-01-01T00:00:00Z", "physical_attempt_id": "a2", "carrier_id": "c9", "absolute_path": "C:\\temp\\x", "message": "different formatting"}
        self.assertEqual(economy.recurrence_fingerprint(base), economy.recurrence_fingerprint(noisy))

    def test_recurrence_first_second_and_immediate_stop(self):
        event = {"logical_subject": "s", "operation": "verify", "failure_code": "SCHEMA_SHAPE", "failure_class": "SCHEMA", "method_revision": "m5", "environment": {"python": "3.13"}}
        first = economy.classify_recurrence(event)
        second = economy.classify_recurrence(event, [event])
        stop = economy.classify_recurrence({**event, "failure_class": "UNOWNED_WRITE"})
        self.assertEqual("SAME_WORK_UNIT_REPAIR", first["transition"])
        self.assertTrue(first["execution_authorized"])
        self.assertEqual("SECOND_RECURRENCE_STOP", second["transition"])
        self.assertFalse(second["third_execution_admitted"])
        self.assertEqual("IMMEDIATE_STOP", stop["transition"])

    def test_layered_stage_receipt_preserves_inner_pass_on_outer_failure(self):
        request = {"stage_id": "stage-1", "subject": {"id": "s"}, "operation": {"id": "op"}}
        receipt = economy.create_stage_receipt(request, {"status": "PASS", "value": {"count": 1}}, finalization="FAIL")
        self.assertEqual("PASS", receipt["inner_result"]["status"])
        self.assertEqual("BLOCKED_TECHNICAL", receipt["aggregate"]["status"])
        aggregate = economy.aggregate_stage_receipts([receipt])
        self.assertEqual("BLOCKED_TECHNICAL", aggregate["overall_status"])
        reused = economy.reuse_stage_receipt(receipt)
        self.assertEqual(0, reused["execution_count"])
        self.assertFalse(reused["launch_invoked"])


if __name__ == "__main__":
    unittest.main()
