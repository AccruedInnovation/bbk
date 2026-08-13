"""Deterministic checks for the activation-neutral Codex target registry."""

import csv
import hashlib
import json
import subprocess
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "spec" / "codex-external-targets.json"
SCHEMA_PATH = ROOT / "spec" / "schemas" / "bbk-codex-external-target-registry-v1.schema.json"
UPSTREAM_ROOT = ROOT / "third_party" / "codex-deepseek-subagent"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CodexExternalTargetsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_registry_validates_and_is_activation_neutral(self):
        Draft202012Validator.check_schema(self.schema)
        Draft202012Validator(self.schema).validate(self.registry)
        self.assertEqual(self.registry["activation"], "ACTIVATION_NEUTRAL")
        self.assertEqual({t["model"] for t in self.registry["targets"]}, {"deepseek-v4-pro", "deepseek-v4-flash"})
        self.assertTrue(all(t["selection"] == "EXPLICIT_ONLY" for t in self.registry["targets"]))
        self.assertTrue(all(t["qualification_state"] == "CONFIGURED_UNQUALIFIED" for t in self.registry["targets"]))
        self.assertTrue(all(not t["enabled"] for t in self.registry["targets"]))

    def test_provenance_map_closes_all_pinned_files(self):
        with (UPSTREAM_ROOT / "UPSTREAM-FILE-MAP.csv").open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 33)
        self.assertEqual(self.registry["provenance"]["tracked_file_count"], len(rows))
        self.assertEqual({r["classification"] for r in rows}, {"COPIED"})
        for row in rows:
            path = ROOT / row["bbk_path"]
            self.assertTrue(path.is_file(), row["bbk_path"])
            self.assertEqual(sha256(path), row["local_sha256"], row["bbk_path"])
            self.assertRegex(row["upstream_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(row["license"], "MIT")

    def test_pinned_upstream_bytes_match_read_only_source(self):
        commit = self.registry["provenance"]["upstream_commit"]
        for row in csv.DictReader((UPSTREAM_ROOT / "UPSTREAM-FILE-MAP.csv").read_text(encoding="utf-8").splitlines()):
            source = subprocess.check_output(["git", "-C", r"D:\Projects\BBK-codex-deepseek-subagent", "show", f"{commit}:{row['upstream_path']}"])
            local = (ROOT / row["bbk_path"]).read_bytes()
            self.assertEqual(local, source, row["upstream_path"])

    def test_protected_routing_matches_repository_baseline(self):
        protected = ["spec/model-routing.json", "spec/omp-model-routing-profiles.json"]
        for relative in protected:
            current = (ROOT / relative).read_bytes()
            baseline = subprocess.check_output(["git", "show", f"HEAD:{relative}"], cwd=ROOT)
            self.assertEqual(current, baseline, relative)
        self.assertEqual(self.registry["protected_routing"]["role_count"], 19)
        self.assertTrue(self.registry["protected_routing"]["default_unchanged"])

    def test_canonical_model_routing_has_19_unchanged_roles(self):
        canonical = json.loads((ROOT / "spec" / "model-routing.json").read_text(encoding="utf-8"))
        baseline = json.loads((ROOT / "tests" / "fixtures" / "alpha17-default-model-routing.json").read_text(encoding="utf-8"))
        self.assertEqual(set(canonical["roles"]), set(baseline["roles"]))
        self.assertEqual(len(canonical["roles"]), 19)
        self.assertEqual(canonical, baseline)


if __name__ == "__main__":
    unittest.main()
