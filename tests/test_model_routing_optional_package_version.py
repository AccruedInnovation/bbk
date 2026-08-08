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

import model_routing  # noqa: E402


class ModelRoutingOptionalPackageVersionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roles = json.loads((ROOT / "spec" / "roles.json").read_text(encoding="utf-8"))
        cls.role_names = {item["name"] for item in cls.roles["roles"]}
        cls.version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        cls.canonical = json.loads((ROOT / "spec" / "model-routing.json").read_text(encoding="utf-8"))

    def test_supplied_no_package_version_policy_is_the_canonical_default(self):
        reviewed = json.loads((ROOT / "tests" / "fixtures" / "alpha17-default-model-routing.json").read_text(encoding="utf-8"))
        self.assertEqual(reviewed, self.canonical)
        self.assertNotIn("package_version", self.canonical)
        self.assertEqual([], model_routing.validate_model_routing(self.canonical, version=self.version, role_names=self.role_names))

    def test_mismatched_package_version_is_accepted_as_optional_provenance(self):
        value = copy.deepcopy(self.canonical)
        value["package_version"] = "unrelated-package-label"
        self.assertEqual([], model_routing.validate_model_routing(value, version=self.version, role_names=self.role_names))

    def test_present_package_version_must_still_be_a_nonempty_string(self):
        for invalid in ("", 17, None):
            value = copy.deepcopy(self.canonical)
            value["package_version"] = invalid
            errors = model_routing.validate_model_routing(value, version=self.version, role_names=self.role_names)
            self.assertTrue(any("package_version must be a non-empty string" in item for item in errors), errors)

    def test_schema_version_remains_governing(self):
        value = copy.deepcopy(self.canonical)
        value["schema_version"] = "bbk.model-routing.v999"
        errors = model_routing.validate_model_routing(value, version=self.version, role_names=self.role_names)
        self.assertTrue(any("schema_version" in item for item in errors), errors)

    def test_v2_normalization_omits_unavailable_package_label(self):
        normalized = model_routing.as_v2(self.canonical)
        self.assertNotIn("package_version", normalized)
        with_label = model_routing.as_v2(self.canonical, package_version="release-provenance")
        self.assertEqual("release-provenance", with_label["package_version"])


if __name__ == "__main__":
    unittest.main()
