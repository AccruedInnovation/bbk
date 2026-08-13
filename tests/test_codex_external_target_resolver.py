import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import codex_external_targets as resolver


class ResolverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads((ROOT / "spec/codex-external-targets.json").read_text(encoding="utf-8"))
        cls.qualification = json.loads((ROOT / "evidence/qualification/deepseek-codex-provider-seam-r4/qualification-receipt.json").read_text(encoding="utf-8"))
        cls.schema = json.loads((ROOT / "spec/schemas/bbk-codex-resolved-external-target-v1.schema.json").read_text(encoding="utf-8"))

    def test_pro_and_flash_resolve_explicitly(self):
        for target in ("deepseek-v4-pro", "deepseek-v4-flash"):
            value = resolver.resolve_target(self.registry, {"mode": "EXPLICIT", "target_id": target}, self.qualification)
            self.assertEqual("RESOLVED", value["status"])
            Draft202012Validator(self.schema).validate(value)
            self.assertEqual(target, value["isolated_codex_projection"]["model"])
            self.assertFalse(value["invariants"]["user_config_mutated"])

    def test_rejections_are_typed_and_fail_closed(self):
        for request in ({}, {"mode": "DEFAULT", "target_id": "deepseek-v4-flash"}, {"mode": "EXPLICIT", "target_id": "unknown"}, {"mode": "EXPLICIT", "target_id": "deepseek-v4-flash", "capabilities": ["image-inputs"]}):
            value = resolver.resolve_target(self.registry, request, self.qualification)
            self.assertEqual("REJECTED", value["status"])
            Draft202012Validator(self.schema).validate(value)
            self.assertFalse(value["invariants"]["silent_fallback"])

    def test_enabled_false_does_not_block_explicit_resolution(self):
        registry = copy.deepcopy(self.registry)
        self.assertTrue(all(not target["enabled"] for target in registry["targets"]))
        self.assertEqual("RESOLVED", resolver.resolve_target(registry, "deepseek-v4-flash", self.qualification)["status"])

    def test_nonqualifying_or_stale_receipt_rejected(self):
        receipt = copy.deepcopy(self.qualification)
        receipt["disposition"] = "CONFIGURED_UNQUALIFIED"
        self.assertEqual("NONQUALIFYING_RECEIPT", resolver.resolve_target(self.registry, "deepseek-v4-flash", receipt)["rejection"]["reason_code"])
        receipt = copy.deepcopy(self.qualification)
        receipt["resolver_input_sufficiency"]["model_id"] = "other"
        self.assertEqual("STALE_QUALIFICATION", resolver.resolve_target(self.registry, "deepseek-v4-flash", receipt)["rejection"]["reason_code"])

    def test_cli_is_canonical_json(self):
        proc = subprocess.run([sys.executable, str(ROOT / "tools/codex_external_targets.py"), "--target", "deepseek-v4-flash", "--json"], capture_output=True, text=True)
        self.assertEqual(0, proc.returncode)
        value = json.loads(proc.stdout)
        self.assertEqual("RESOLVED", value["status"])
        self.assertEqual(proc.stdout, json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    unittest.main()
