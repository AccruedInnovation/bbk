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
        self.assertEqual({r["classification"] for r in rows}, {"COPIED", "TRANSFORMED"})
        transformed = [r for r in rows if r["classification"] == "TRANSFORMED"]
        self.assertEqual(len(transformed), 1)
        self.assertEqual(transformed[0]["bbk_path"], "third_party/codex-deepseek-subagent/tests/test_plaintext_handoff.py")
        self.assertIn("codex-ds-plaintext-handoff-explicit-utf8-v1", transformed[0]["reason"])
        self.assertIn("14 occurrences", transformed[0]["reason"])
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
            if row["classification"] == "TRANSFORMED":
                operation = b".read_text()"
                replacement = b'.read_text(encoding="utf-8")'
                self.assertEqual(source.count(operation), 14, row["upstream_path"])
                source = source.replace(operation, replacement)
            local = (ROOT / row["bbk_path"]).read_bytes()
            self.assertEqual(local, source, row["upstream_path"])

    def test_transformation_record_preserves_both_file_identities(self):
        metadata = json.loads((UPSTREAM_ROOT / "UPSTREAM.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["copy_policy"], "byte_for_byte_except_declared_transformations")
        self.assertEqual(metadata["transformed_file_count"], 1)
        self.assertEqual(len(metadata["transformations"]), 1)
        transformation = metadata["transformations"][0]
        self.assertEqual(transformation["transformation_id"], "codex-ds-plaintext-handoff-explicit-utf8-v1")
        self.assertEqual(transformation["operation"], '.read_text() -> .read_text(encoding="utf-8")')
        self.assertEqual(transformation["occurrence_count"], 14)
        self.assertEqual(transformation["upstream_sha256"], "3f5c47b78b6038b964e06e30fc18490ba52b591fb207dc458ff233f231047cd8")
        self.assertEqual(transformation["local_sha256"], "77ec4c343866918f91815ef7ca031901601d041a1cb44bdb1e4c9418c239da85")

    def test_protected_routing_matches_repository_baseline(self):
        git_root = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        if git_root.returncode != 0 or Path(git_root.stdout.strip()).resolve() != ROOT.resolve():
            self.skipTest("repository-baseline comparison requires the exact Git checkout context")
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
