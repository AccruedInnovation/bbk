from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import diagnostics
import deterministic_operations
import source_sanity
import build_release


def schema(name: str) -> dict:
    return json.loads((ROOT / "spec" / "schemas" / name).read_text(encoding="utf-8"))


class M3DiagnosticTests(unittest.TestCase):
    def test_diagnostic_keeps_semantic_result_and_mechanical_envelope_distinct(self) -> None:
        value = diagnostics.typed_diagnostic(
            code="INNER_PASS_OUTER_FAIL",
            subject="WU-ER-03-STREAMLINED",
            semantic_status="PASS",
            semantic_value={"inner": "PASS"},
            mechanical_status="FAIL",
            effects_observed="NONE",
            cleanup="COMPLETE",
            diagnostic_class="MECHANICAL",
        )
        jsonschema.Draft202012Validator(schema("bbk-diagnostic-v1.schema.json")).validate(value)
        self.assertEqual(value["semantic_result"]["status"], "PASS")
        self.assertEqual(value["mechanical_envelope"]["status"], "FAIL")

    def test_immediate_stop_and_static_dynamic_limits_are_explicit(self) -> None:
        stop = diagnostics.classify_failure("WRONG_SUBJECT", subject="other")
        self.assertTrue(stop["immediate_stop"])
        self.assertEqual(stop["class"], "IMMEDIATE_STOP")
        claim = diagnostics.static_dynamic_claim(static_inventory="PASS", dynamic_execution="NOT_RUN")
        self.assertEqual(claim["semantic_result"]["status"], "PASS")
        self.assertIn("dynamic execution", claim["claims"]["not_established"])


class M3OperationTests(unittest.TestCase):
    def test_registered_operation_and_qualification_are_schema_valid(self) -> None:
        registry = deterministic_operations.load_registry()
        jsonschema.Draft202012Validator(schema("bbk-deterministic-operation-registry-v1.schema.json")).validate(registry)
        result = deterministic_operations.qualify_operation(
            "bbk.source-sanity", subject=str(ROOT), argv=["--json"]
        )
        jsonschema.Draft202012Validator(schema("bbk-operation-qualification-v1.schema.json")).validate(result)
        self.assertEqual(result["status"], "QUALIFIED")

    def test_unregistered_operation_fails_before_callable_effect(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            marker = Path(raw) / "must-not-exist"
            with self.assertRaises(deterministic_operations.OperationAdmissionError) as raised:
                deterministic_operations.run_registered_operation(
                    "ad-hoc.wrapper", subject=str(marker), argv=[]
                )
            self.assertEqual(raised.exception.code, "OPERATION_NOT_REGISTERED")
            self.assertFalse(marker.exists())

    def test_v2_receipt_is_additive_to_v1_shape(self) -> None:
        value = {
            "schema": "bbk.command-attempt.v2",
            "semantic_command_id": "bbk.source-sanity",
            "execution_attempt_ref": "attempt:1",
            "physical_command_attempt": 1,
            "invocation_identity": {
                "executable": "deterministic_operations:run_source_sanity",
                "arguments_sha256": "0" * 64,
                "inputs_sha256": "1" * 64,
                "environment_constraints_sha256": "2" * 64,
            },
            "effect_class": "READ_ONLY",
            "disposition": "PASS",
            "effects_observed": {"product_mutation": "NONE", "external_effect": "NONE"},
            "cleanup": {"state": "COMPLETE", "remaining_processes_or_handles": False},
            "replay": {"eligible": True, "reason": "read-only", "maximum_replays": 1, "replay_of_physical_attempt": None},
            "operation_id": "bbk.source-sanity",
            "operation_version": "1.0.0",
            "operation_implementation_sha256": "3" * 64,
            "subject": str(ROOT),
            "argv": ["--json"],
            "environment_policy": {"mode": "NONE", "allowed_variables": []},
            "allowed_effects": ["READ_ONLY"],
            "output_schema": "bbk.source-sanity.v1",
            "invalidation_keys": ["source-tree"],
            "qualification": "QUALIFIED",
            "semantic_result": {"status": "PASS"},
            "mechanical_envelope": {"status": "PASS", "effects_observed": "NONE", "cleanup": "COMPLETE"},
        }
        jsonschema.Draft202012Validator(schema("bbk-command-attempt-v2.schema.json"), format_checker=jsonschema.FormatChecker()).validate(value)


class M3SourceSanityScopeTests(unittest.TestCase):
    def _validate_in(self, files: dict[str, str]) -> dict:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for name, content in files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            with mock.patch.object(source_sanity, "ROOT", root):
                return source_sanity.validate()

    def test_workspace_control_roots_are_not_product_source_inputs(self) -> None:
        value = self._validate_in({
            ".bbk/evidence.py": "def broken(:\n",
            ".beads/control.json": "{broken",
            ".jj/state.py": "def broken(:\n",
            ".git/control.py": "def broken(:\n",
            "src/product.py": "from pathlib import Path\nPath('x').read_text(encoding='utf-8')\n",
            "spec/product.json": "{}",
        })
        self.assertEqual(value["status"], "PASS", value)

    def test_source_sanity_reuses_release_selection_and_skips_unselected_evidence(self) -> None:
        self.assertEqual(source_sanity.EXCLUDED_PARTS, build_release.EXCLUDED_PARTS)
        self.assertEqual(source_sanity.INCLUDED_EVIDENCE_FILES, build_release.INCLUDED_EVIDENCE_FILES)
        value = self._validate_in({
            "evidence/assurance/third_party/broken.py": "def broken(:\n",
            "evidence/assurance/third_party/broken.json": "{broken",
            "src/product.py": "value = 1\n",
            "spec/product.json": "{}",
        })
        self.assertEqual(value["status"], "PASS", value)

    def test_exact_selected_evidence_remains_checked(self) -> None:
        selected = "evidence/alpha17-rc6-work-unit-dispositions.json"
        self.assertIn(selected, source_sanity.INCLUDED_EVIDENCE_FILES)
        value = self._validate_in({selected: "{broken", "src/product.py": "value = 1\n"})
        self.assertEqual(value["status"], "FAIL")
        self.assertTrue(any("JSON parse failed" in item and selected in item for item in value["errors"]))

    def test_product_python_and_json_failures_still_fail(self) -> None:
        value = self._validate_in({"src/broken.py": "def broken(:\n", "spec/broken.json": "{broken"})
        self.assertEqual(value["status"], "FAIL")
        self.assertTrue(any("python compile failed" in item for item in value["errors"]))
        self.assertTrue(any("JSON parse failed" in item for item in value["errors"]))


if __name__ == "__main__":
    unittest.main()
