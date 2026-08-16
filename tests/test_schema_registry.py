from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import bbk
from validate_contract_package import load_role_package, representative_role_return_v2
from tests._path_support import assert_same_path


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validation_args(schema: Path, instance: Path, *, tool_dir: Path | None = None) -> argparse.Namespace:
    return argparse.Namespace(
        root=None,
        tool_dir=str(tool_dir) if tool_dir else None,
        ensure=False,
        wheelhouse=None,
        timeout=30.0,
        schema=str(schema),
        instance=[str(instance)],
    )


class SchemaRegistryRegressionTests(unittest.TestCase):
    def test_exact_verification_designer_compact_return_resolves_nested_schema(self) -> None:
        _, roles, entries = load_role_package(ROOT)
        role = next(value for value in roles if value["name"] == "bbk_verification_designer")
        instance_value = representative_role_return_v2(
            role,
            entries[role["name"]],
            detail_level="COMPACT",
        )
        with tempfile.TemporaryDirectory() as raw:
            instance = Path(raw) / "verification-designer-compact.json"
            write_json(instance, instance_value)
            result = bbk.cmd_schema_validate(
                validation_args(
                    ROOT / "spec" / "schemas" / "role-returns" / "bbk-verification-designer-return-v2.schema.json",
                    instance,
                )
            )
        self.assertEqual(result["status"], "PASS", result)
        self.assertTrue(result["valid"])
        self.assertIsNone(result["code"])
        self.assertRegex(result["schema_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(result["instances"][0]["sha256"], r"^[0-9a-f]{64}$")
        self.assertGreaterEqual(result["registry"]["registered_schema_count"], 3)

    def test_recursive_registry_resolves_declared_id_independent_of_physical_layout(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "schemas"
            nested_id = "https://bbk.local/schemas/compact-result.schema.json"
            top = root / "top-level.schema.json"
            nested = root / "nested" / "role-results" / "compact-result.schema.json"
            instance = Path(raw) / "instance.json"
            write_json(
                top,
                {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "$id": "https://bbk.local/schemas/top-level.schema.json",
                    "type": "object",
                    "required": ["result"],
                    "properties": {"result": {"$ref": nested_id}},
                },
            )
            write_json(
                nested,
                {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "$id": nested_id,
                    "type": "object",
                    "required": ["ok"],
                    "properties": {"ok": {"const": True}},
                    "additionalProperties": False,
                },
            )
            write_json(instance, {"result": {"ok": True}})
            with mock.patch.object(bbk, "SCHEMA_DIR", root):
                result = bbk.cmd_schema_validate(validation_args(top, instance))
        self.assertEqual(result["status"], "PASS", result)
        self.assertTrue(result["valid"])
        self.assertEqual(result["registry"]["registered_schema_count"], 2)

    def test_missing_nested_schema_has_specific_reference_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "schemas"
            missing_id = "https://bbk.local/schemas/missing-result.schema.json"
            top = root / "top-level.schema.json"
            instance = Path(raw) / "instance.json"
            write_json(
                top,
                {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "$id": "https://bbk.local/schemas/top-level.schema.json",
                    "type": "object",
                    "required": ["result"],
                    "properties": {"result": {"$ref": missing_id}},
                },
            )
            write_json(instance, {"result": {"ok": True}})
            with mock.patch.object(bbk, "SCHEMA_DIR", root):
                result = bbk.cmd_schema_validate(validation_args(top, instance))
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertFalse(result["valid"])
        self.assertEqual(result["code"], "SCHEMA_REFERENCE_UNRESOLVED")
        self.assertEqual(result["unresolved_uri"], missing_id)
        self.assertEqual(result["candidate_physical_files"], [])
        self.assertEqual(result["instances"][0]["code"], "SCHEMA_REFERENCE_UNRESOLVED")
        self.assertIn("top-level.schema.json", result["referencing_schema"]["path"])
        self.assertTrue(result["exception_traceback"])

    def test_duplicate_declared_id_is_rejected_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "schemas"
            duplicate_id = "https://bbk.local/schemas/duplicate.schema.json"
            for name in ("a.schema.json", "nested/b.schema.json"):
                write_json(
                    root / name,
                    {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "$id": duplicate_id,
                        "type": "object",
                    },
                )
            with self.assertRaises(bbk.BbkError) as caught:
                bbk._build_schema_registry(root)
        diagnostic = caught.exception.diagnostic or {}
        self.assertEqual(diagnostic.get("code"), "SCHEMA_REGISTRY_DUPLICATE_ID")
        self.assertEqual(diagnostic.get("duplicate_uri"), duplicate_id)
        self.assertLess(diagnostic["first_path"], diagnostic["duplicate_path"])

    def test_semantic_validation_failure_is_not_a_process_or_reference_error(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "schemas"
            schema = root / "value.schema.json"
            instance = Path(raw) / "instance.json"
            write_json(
                schema,
                {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "$id": "https://bbk.local/schemas/value.schema.json",
                    "type": "object",
                    "required": ["value"],
                    "properties": {"value": {"type": "string"}},
                },
            )
            write_json(instance, {"value": 5})
            with mock.patch.object(bbk, "SCHEMA_DIR", root):
                result = bbk.cmd_schema_validate(validation_args(schema, instance))
        self.assertEqual(result["status"], "FAIL", result)
        self.assertEqual(result["code"], "SCHEMA_VALIDATION_FAILED")
        self.assertEqual(result["instances"][0]["code"], "SCHEMA_VALIDATION_FAILED")

    def test_managed_nonzero_exit_preserves_stderr_and_is_not_parsed_as_json(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tool_root = Path(raw) / "managed"
            python = tool_root / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
            python.parent.mkdir(parents=True)
            python.write_bytes(b"")
            args = validation_args(Path("unused.schema.json"), Path("unused.instance.json"), tool_dir=tool_root)
            child = {
                "argv": [str(python), "bbk.py"],
                "cwd": str(ROOT),
                "returncode": 2,
                "stdout": "",
                "stderr": "Traceback: unresolved schema reference",
                "duration_seconds": 0.01,
                "timed_out": False,
                "executable": str(python),
            }
            with mock.patch.object(bbk, "_jsonschema_runtime", return_value=(None, None)):
                result = bbk.cmd_schema_validate(args)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["valid"])
        self.assertIn("jsonschema package is not available", result["error"])

    def test_managed_success_with_malformed_json_has_output_error(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tool_root = Path(raw) / "managed"
            python = tool_root / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
            python.parent.mkdir(parents=True)
            python.write_bytes(b"")
            args = validation_args(Path("unused.schema.json"), Path("unused.instance.json"), tool_dir=tool_root)
            child = {
                "argv": [str(python), "bbk.py"],
                "cwd": str(ROOT),
                "returncode": 0,
                "stdout": "not-json",
                "stderr": "",
                "duration_seconds": 0.01,
                "timed_out": False,
                "executable": str(python),
            }
            with mock.patch.object(bbk, "_jsonschema_runtime", return_value=(None, None)):
                result = bbk.cmd_schema_validate(args)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["valid"])
        assert_same_path(self, result["managed_environment"], tool_root)

    def test_managed_semantic_failure_remains_parseable(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tool_root = Path(raw) / "managed"
            python = tool_root / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
            python.parent.mkdir(parents=True)
            python.write_bytes(b"")
            args = validation_args(Path("unused.schema.json"), Path("unused.instance.json"), tool_dir=tool_root)
            payload = {
                "schema": "bbk.schema-validation.v1",
                "status": "FAIL",
                "valid": False,
                "code": "SCHEMA_VALIDATION_FAILED",
                "instances": [],
            }
            child = {
                "argv": [str(python), "bbk.py"],
                "cwd": str(ROOT),
                "returncode": 1,
                "stdout": json.dumps(payload),
                "stderr": "",
                "duration_seconds": 0.01,
                "timed_out": False,
                "executable": str(python),
            }
            with mock.patch.object(bbk, "_jsonschema_runtime", return_value=(None, None)):
                result = bbk.cmd_schema_validate(args)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["valid"])
        assert_same_path(self, result["managed_environment"], tool_root)


if __name__ == "__main__":
    unittest.main()
