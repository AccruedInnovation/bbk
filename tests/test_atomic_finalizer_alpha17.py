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

import atomic_finalizer as af  # noqa: E402


class AtomicFinalizerTests(unittest.TestCase):
    def test_bom_crlf_and_lf_drafts_finalize_to_same_canonical_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            d1 = root / "one.json"
            d2 = root / "two.json"
            d1.write_bytes(b'\xef\xbb\xbf{\r\n  "b": 2,\r\n  "a": 1\r\n}\r\n')
            d2.write_text('{"a":1,"b":2}\n', encoding="utf-8")
            o1, o2 = root / "one.out.json", root / "two.out.json"
            r1 = af.finalize_json(d1, o1, subject_kind="TEST", generated_at="2026-08-06T00:00:00Z")
            r2 = af.finalize_json(d2, o2, subject_kind="TEST", generated_at="2026-08-06T00:00:00Z")
            self.assertEqual(o1.read_bytes(), o2.read_bytes())
            self.assertEqual(r1["sha256"], r2["sha256"])
            self.assertTrue(Path(r1["identity_receipt"]).is_file())
            value = json.loads(o1.read_text(encoding="utf-8"))
            self.assertNotIn("sha256", value)
            self.assertNotIn("byte_count", value)

    def test_existing_output_conflict_fails_without_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); draft = root / "draft.json"; output = root / "out.json"
            draft.write_text('{"value":1}', encoding="utf-8")
            output.write_text('{"existing":true}\n', encoding="utf-8")
            before = output.read_bytes()
            with self.assertRaises(af.FinalizationError) as cm:
                af.finalize_json(draft, output, subject_kind="TEST")
            self.assertEqual("BBK-FIN-006", cm.exception.code)
            self.assertEqual(before, output.read_bytes())

    def test_schema_failure_publishes_no_output(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); schemas = root / "spec" / "schemas"; schemas.mkdir(parents=True)
            (schemas / "value.schema.json").write_text(json.dumps({
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": "https://bbk.local/schemas/value.schema.json",
                "type": "object", "required": ["value"], "properties": {"value": {"type": "integer"}}, "additionalProperties": False,
            }), encoding="utf-8")
            draft = root / "draft.json"; output = root / "out.json"
            draft.write_text('{"value":"bad"}', encoding="utf-8")
            with self.assertRaises(af.FinalizationError) as cm:
                af.finalize_json(draft, output, subject_kind="TEST", schema=schemas / "value.schema.json", root=root)
            self.assertEqual("BBK-FIN-002", cm.exception.code)
            self.assertFalse(output.exists())

    def test_receipt_publication_failure_restores_prior_current_pair(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            draft = root / "draft.json"
            output = root / "out.json"
            receipt = root / "out.json.identity.json"
            draft.write_text('{"value":2}', encoding="utf-8")
            output.write_text('{"value":1}\n', encoding="utf-8")
            receipt.write_text('{"schema":"prior"}\n', encoding="utf-8")
            prior_output = output.read_bytes()
            prior_receipt = receipt.read_bytes()
            calls = 0
            real_replace = af._replace_file

            def fail_second(source, target):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected receipt replace failure")
                return real_replace(source, target)

            with mock.patch.object(af, "_replace_file", side_effect=fail_second):
                with self.assertRaises(af.FinalizationError) as cm:
                    af.finalize_json(draft, output, subject_kind="TEST", replace=True)
            self.assertEqual("BBK-FIN-007", cm.exception.code)
            self.assertEqual(prior_output, output.read_bytes())
            self.assertEqual(prior_receipt, receipt.read_bytes())

    def test_receipt_publication_failure_leaves_no_new_pair_without_prior(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            draft = root / "draft.json"
            output = root / "out.json"
            receipt = root / "out.json.identity.json"
            draft.write_text('{"value":2}', encoding="utf-8")
            calls = 0
            real_replace = af._replace_file

            def fail_second(source, target):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected receipt replace failure")
                return real_replace(source, target)

            with mock.patch.object(af, "_replace_file", side_effect=fail_second):
                with self.assertRaises(af.FinalizationError) as cm:
                    af.finalize_json(draft, output, subject_kind="TEST")
            self.assertEqual("BBK-FIN-007", cm.exception.code)
            self.assertFalse(output.exists())
            self.assertFalse(receipt.exists())


if __name__ == "__main__":
    unittest.main()
