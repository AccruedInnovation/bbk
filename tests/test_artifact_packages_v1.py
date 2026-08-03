from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import artifact_packages
import strict_json
from tests._path_support import create_symlink_or_skip


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def draft_descriptor(
    *,
    artifacts: list[dict[str, object]] | None = None,
    profile: dict[str, str] | None = None,
    package_id: str = "pkg-test",
    revision: str = "1",
) -> dict[str, object]:
    return {
        "schema": "bbk.artifact-package-draft.v1",
        "packageId": package_id,
        "revision": revision,
        "profile": profile or {"id": "generic", "version": "1"},
        "subject": {"kind": "test", "id": "subject-1", "revision": "1"},
        "predecessor": None,
        "artifacts": artifacts
        or [
            {
                "artifactId": "primary",
                "path": "primary.json",
                "role": "semantic",
                "references": [],
            }
        ],
        "metadata": {"note": "test"},
    }


def make_draft(root: Path, descriptor: dict[str, object] | None = None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "primary.json").write_text('{"z":1,"a":2}\n', encoding="utf-8")
    write_json(root / artifact_packages.DRAFT_FILE, descriptor or draft_descriptor())
    return root


class StrictJsonTests(unittest.TestCase):
    def rejection(self, raw: bytes, code: str, *, max_depth: int = 128) -> dict[str, object]:
        with self.assertRaises(strict_json.StrictJsonError) as raised:
            strict_json.loads_bytes(raw, source="fixture.json", max_depth=max_depth)
        result = raised.exception.as_dict()
        self.assertEqual(result["schema"], "bbk.strict-json-diagnostic.v1")
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["classification"], "MECHANICAL")
        self.assertEqual(result["code"], code)
        self.assertTrue(result["remediation"])
        return result

    def test_duplicate_root_key_rejected_with_pointer_and_key(self):
        result = self.rejection(b'{"a":1,"a":2}', "JSON_DUPLICATE_KEY")
        self.assertEqual(result["pointer"], "")
        self.assertEqual(result["duplicate_key"], "a")
        self.assertEqual(result["line"], 1)

    def test_duplicate_nested_key_reports_containing_pointer(self):
        result = self.rejection(b'{"outer":{"x":1,"x":2}}', "JSON_DUPLICATE_KEY")
        self.assertEqual(result["pointer"], "/outer")
        self.assertEqual(result["duplicate_key"], "x")

    def test_invalid_utf8_rejected(self):
        result = self.rejection(b'{"x":"\xff"}', "JSON_INVALID_UTF8")
        self.assertIn("offset", result)

    def test_all_common_boms_rejected(self):
        for raw in (
            b"\xef\xbb\xbf{}",
            b"\xff\xfe{}",
            b"\xfe\xff{}",
            b"\xff\xfe\x00\x00{}",
            b"\x00\x00\xfe\xff{}",
        ):
            with self.subTest(raw=raw):
                self.rejection(raw, "JSON_FORBIDDEN_BOM")

    def test_nonfinite_numbers_rejected(self):
        for token in (b"NaN", b"Infinity", b"-Infinity"):
            with self.subTest(token=token):
                self.rejection(b'{"x":' + token + b"}", "JSON_NONFINITE_NUMBER")

    def test_malformed_escape_rejected(self):
        result = self.rejection(b'{"x":"\\q"}', "JSON_MALFORMED_ESCAPE")
        self.assertEqual(result["pointer"], "/x")

    def test_trailing_data_rejected(self):
        self.rejection(b'{} {}', "JSON_TRAILING_DATA")

    def test_excessive_depth_rejected(self):
        self.rejection(b'[[[0]]]', "JSON_MAX_DEPTH_EXCEEDED", max_depth=2)

    def test_valid_strict_json_loads(self):
        value = strict_json.loads_bytes(' {"é":[true,false,null,-1.25e2]} \n'.encode())
        self.assertEqual(value, {"é": [True, False, None, -125.0]})

    def test_path_result_is_structured(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "value.json"
            path.write_bytes(b'{"x":1,"x":2}')
            result = strict_json.try_load_path(path)
            self.assertEqual(result["code"], "JSON_DUPLICATE_KEY")
            self.assertEqual(result["source"], str(path))


class SchemaReferenceTests(unittest.TestCase):
    def test_recursive_schema_is_not_treated_as_artifact_cycle(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            schema = {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": "https://bbk.local/schemas/bbk-recursive-node-v1.schema.json",
                "type": "object",
                "required": ["schema", "value"],
                "properties": {
                    "schema": {"const": "bbk.recursive-node.v1"},
                    "value": {"type": "string"},
                    "next": {"anyOf": [{"type": "null"}, {"$ref": "#"}]},
                },
                "additionalProperties": False,
            }
            write_json(root / "bbk-recursive-node-v1.schema.json", schema)
            instance = {
                "schema": "bbk.recursive-node.v1",
                "value": "a",
                "next": {"schema": "bbk.recursive-node.v1", "value": "b", "next": None},
            }
            findings = artifact_packages.validate_schema_instance(
                instance,
                "bbk.recursive-node.v1",
                schema_root=root,
            )
            self.assertEqual(findings, [])


class ArtifactPreflightTests(unittest.TestCase):
    def test_valid_generic_draft_passes(self):
        with tempfile.TemporaryDirectory() as temp:
            draft = make_draft(Path(temp) / "draft")
            result = artifact_packages.preflight_draft(draft)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["summary"]["artifacts"], 1)

    def test_generated_identity_fields_are_rejected_in_draft(self):
        with tempfile.TemporaryDirectory() as temp:
            descriptor = draft_descriptor()
            descriptor["artifacts"][0]["sha256"] = "0" * 64
            draft = make_draft(Path(temp) / "draft", descriptor)
            result = artifact_packages.preflight_draft(draft)
            self.assertEqual(result["status"], "REJECTED")
            self.assertIn("PACKAGE_GENERATED_FIELD_MANUALLY_OWNED", {x["code"] for x in result["findings"]})

    def test_unknown_profile_is_semantic_owner_finding(self):
        with tempfile.TemporaryDirectory() as temp:
            descriptor = draft_descriptor(profile={"id": "missing", "version": "1"})
            result = artifact_packages.preflight_draft(make_draft(Path(temp) / "draft", descriptor))
            finding = next(x for x in result["findings"] if x["code"] == "PACKAGE_PROFILE_UNKNOWN")
            self.assertEqual(finding["classification"], "SEMANTIC_OWNER_REQUIRED")

    def test_duplicate_artifact_identity_and_path_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            descriptor = draft_descriptor(artifacts=[
                {"artifactId": "same", "path": "primary.json", "role": "semantic", "references": []},
                {"artifactId": "same", "path": "primary.json", "role": "evidence", "references": []},
            ])
            result = artifact_packages.preflight_draft(make_draft(Path(temp) / "draft", descriptor))
            codes = {x["code"] for x in result["findings"]}
            self.assertIn("PACKAGE_ARTIFACT_ID_DUPLICATE", codes)
            self.assertIn("PACKAGE_ARTIFACT_PATH_DUPLICATE", codes)

    def test_unresolved_reference_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            descriptor = draft_descriptor()
            descriptor["artifacts"][0]["references"] = ["missing"]
            result = artifact_packages.preflight_draft(make_draft(Path(temp) / "draft", descriptor))
            self.assertIn("PACKAGE_REFERENCE_UNRESOLVED", {x["code"] for x in result["findings"]})

    def test_artifact_graph_cycle_rejected_separately(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "draft"
            root.mkdir(parents=True)
            (root / "a.bin").write_bytes(b"a")
            (root / "b.bin").write_bytes(b"b")
            descriptor = draft_descriptor(artifacts=[
                {"artifactId": "a", "path": "a.bin", "role": "semantic", "references": ["b"]},
                {"artifactId": "b", "path": "b.bin", "role": "evidence", "references": ["a"]},
            ])
            write_json(root / artifact_packages.DRAFT_FILE, descriptor)
            result = artifact_packages.preflight_draft(root)
            item = next(x for x in result["findings"] if x["code"] == "PACKAGE_ARTIFACT_REFERENCE_CYCLE")
            self.assertIn("recursive JSON Schema", item["remediation"])

    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            draft = root / "draft"
            draft.mkdir()
            (root / "outside.bin").write_bytes(b"outside")
            descriptor = draft_descriptor(artifacts=[
                {"artifactId": "outside", "path": "../outside.bin", "role": "semantic", "references": []}
            ])
            write_json(draft / artifact_packages.DRAFT_FILE, descriptor)
            result = artifact_packages.preflight_draft(draft)
            self.assertIn("PACKAGE_ARTIFACT_PATH_INVALID", {x["code"] for x in result["findings"]})

    def test_symlink_artifact_rejected(self):
        """Exercise the rejection path without requiring host link privilege."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            draft = root / "draft"
            draft.mkdir()
            link = draft / "link.bin"
            link.write_bytes(b"x")
            descriptor = draft_descriptor(artifacts=[
                {"artifactId": "link", "path": "link.bin", "role": "semantic", "references": []}
            ])
            write_json(draft / artifact_packages.DRAFT_FILE, descriptor)

            real_is_symlink = Path.is_symlink

            def report_fixture_as_symlink(path: Path) -> bool:
                try:
                    if os.path.samefile(path, link):
                        return True
                except (OSError, ValueError):
                    pass
                return real_is_symlink(path)

            with mock.patch.object(Path, "is_symlink", report_fixture_as_symlink):
                result = artifact_packages.preflight_draft(draft)
            self.assertEqual(result["status"], "REJECTED")
            self.assertIn("PACKAGE_ARTIFACT_PATH_INVALID", {item["code"] for item in result["findings"]})
            self.assertIn("symbolic links", json.dumps(result["findings"]))

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink API required")
    def test_real_symlink_artifact_rejected_when_host_allows_creation(self):
        """Confirm the same behavior against an actual link where available."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            draft = root / "draft"
            draft.mkdir()
            target = root / "target.bin"
            target.write_bytes(b"x")
            create_symlink_or_skip(self, draft / "link.bin", target)
            descriptor = draft_descriptor(artifacts=[
                {"artifactId": "link", "path": "link.bin", "role": "semantic", "references": []}
            ])
            write_json(draft / artifact_packages.DRAFT_FILE, descriptor)
            result = artifact_packages.preflight_draft(draft)
            self.assertEqual(result["status"], "REJECTED")
            self.assertIn("PACKAGE_ARTIFACT_PATH_INVALID", {item["code"] for item in result["findings"]})
            self.assertIn("symbolic links", json.dumps(result["findings"]))


class ArtifactTransactionTests(unittest.TestCase):
    def test_seal_canonicalizes_json_and_hashes_exact_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            draft = make_draft(root / "draft")
            sealed = root / "sealed"
            result = artifact_packages.seal_draft(draft, sealed, sealed_at_utc="2026-08-03T00:00:00Z")
            self.assertEqual(result["status"], "PASS")
            raw = (sealed / "primary.json").read_bytes()
            self.assertEqual(raw, b'{\n  "a": 2,\n  "z": 1\n}\n')
            manifest = strict_json.load_path(sealed / artifact_packages.MANIFEST_FILE)
            entry = manifest["artifacts"][0]
            self.assertEqual(entry["bytes"], len(raw))
            self.assertEqual(entry["sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(entry["canonicalization"], "BBK-JSON-1")

    def test_two_seals_have_same_content_and_manifest_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            draft = make_draft(root / "draft")
            first = artifact_packages.seal_draft(draft, root / "one", sealed_at_utc="2026-08-03T00:00:00Z")
            second = artifact_packages.seal_draft(draft, root / "two", sealed_at_utc="2026-08-04T00:00:00Z")
            self.assertEqual(first["contentSha256"], second["contentSha256"])
            self.assertEqual(first["manifestSha256"], second["manifestSha256"])
            self.assertEqual((root / "one" / artifact_packages.MANIFEST_FILE).read_bytes(), (root / "two" / artifact_packages.MANIFEST_FILE).read_bytes())
            self.assertNotEqual((root / "one" / artifact_packages.RECEIPT_FILE).read_bytes(), (root / "two" / artifact_packages.RECEIPT_FILE).read_bytes())

    def test_seal_refuses_existing_target_without_mutating_it(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            draft = make_draft(root / "draft")
            target = root / "sealed"
            target.mkdir()
            marker = target / "marker.txt"
            marker.write_text("preserve", encoding="utf-8")
            with self.assertRaises(artifact_packages.ArtifactPackageError) as raised:
                artifact_packages.seal_draft(draft, target)
            self.assertEqual(raised.exception.result["code"], "PACKAGE_TARGET_EXISTS")
            self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")

    def test_failure_before_publish_leaves_no_final_target(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            draft = make_draft(root / "draft")
            target = root / "sealed"
            with self.assertRaises(artifact_packages.ArtifactPackageError):
                artifact_packages.seal_draft(draft, target, _test_fail_phase="before-publish")
            self.assertFalse(target.exists())
            self.assertFalse(any(root.glob(".sealed.bbk-stage-*")))

    def test_existing_lock_fails_closed_with_owner_diagnostics(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            draft = make_draft(root / "draft")
            target = root / "sealed"
            lock = root / ".sealed.bbk-seal.lock"
            lock.mkdir()
            write_json(lock / "lock.json", {"pid": 1, "host": "fixture"})
            with self.assertRaises(artifact_packages.ArtifactPackageError) as raised:
                artifact_packages.seal_draft(draft, target)
            self.assertEqual(raised.exception.result["code"], "PACKAGE_LOCK_HELD")
            self.assertFalse(target.exists())

    def test_verify_is_read_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sealed = root / "sealed"
            artifact_packages.seal_draft(make_draft(root / "draft"), sealed)
            before = {p.relative_to(sealed).as_posix(): (p.stat().st_mtime_ns, p.read_bytes()) for p in sealed.rglob("*") if p.is_file()}
            result = artifact_packages.verify_package(sealed)
            after = {p.relative_to(sealed).as_posix(): (p.stat().st_mtime_ns, p.read_bytes()) for p in sealed.rglob("*") if p.is_file()}
            self.assertEqual(result["status"], "PASS")
            self.assertTrue(result["readOnly"])
            self.assertEqual(before, after)

    def test_tamper_and_undeclared_file_are_rejected_without_repair(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sealed = root / "sealed"
            artifact_packages.seal_draft(make_draft(root / "draft"), sealed)
            artifact = sealed / "primary.json"
            artifact.write_text('{"changed":true}\n', encoding="utf-8")
            (sealed / "extra.txt").write_text("extra", encoding="utf-8")
            before = artifact.read_bytes()
            result = artifact_packages.verify_package(sealed)
            self.assertEqual(result["status"], "REJECTED")
            codes = {x["code"] for x in result["findings"]}
            self.assertIn("PACKAGE_ARTIFACT_DIGEST_MISMATCH", codes)
            self.assertIn("PACKAGE_UNDECLARED_FILE", codes)
            self.assertEqual(artifact.read_bytes(), before)

    def test_successor_preserves_predecessor_and_binds_digest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sealed = root / "sealed"
            artifact_packages.seal_draft(make_draft(root / "draft"), sealed)
            predecessor = {p.relative_to(sealed).as_posix(): p.read_bytes() for p in sealed.rglob("*") if p.is_file()}
            result = artifact_packages.create_successor(sealed, root / "successor", revision="2", reason="repair exact finding")
            self.assertEqual(result["status"], "PASS")
            descriptor = strict_json.load_path(root / "successor" / artifact_packages.DRAFT_FILE)
            manifest = strict_json.load_path(sealed / artifact_packages.MANIFEST_FILE)
            self.assertEqual(descriptor["packageId"], manifest["packageId"])
            self.assertEqual(descriptor["predecessor"]["contentSha256"], manifest["contentSha256"])
            self.assertEqual(predecessor, {p.relative_to(sealed).as_posix(): p.read_bytes() for p in sealed.rglob("*") if p.is_file()})

    def test_non_json_artifact_bytes_are_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            draft = root / "draft"
            draft.mkdir()
            payload = b"\x00\xffbinary\r\n"
            (draft / "blob.bin").write_bytes(payload)
            descriptor = draft_descriptor(artifacts=[
                {"artifactId": "blob", "path": "blob.bin", "role": "evidence", "references": []}
            ])
            write_json(draft / artifact_packages.DRAFT_FILE, descriptor)
            artifact_packages.seal_draft(draft, root / "sealed")
            self.assertEqual((root / "sealed" / "blob.bin").read_bytes(), payload)


class ArtifactCompatibilityAndCliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / "tools" / "bbk.py"), "--json", *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_bbk_cli_preflight_seal_verify_successor(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            draft = make_draft(root / "draft")
            preflight = self.run_cli("artifact", "preflight", str(draft))
            self.assertEqual(preflight.returncode, 0, preflight.stderr)
            self.assertEqual(json.loads(preflight.stdout)["status"], "PASS")
            seal = self.run_cli("artifact", "seal", str(draft), "--output", str(root / "sealed"))
            self.assertEqual(seal.returncode, 0, seal.stderr)
            verify = self.run_cli("artifact", "verify", str(root / "sealed"))
            self.assertEqual(verify.returncode, 0, verify.stderr)
            successor = self.run_cli("artifact", "successor", str(root / "sealed"), "--output", str(root / "successor"), "--revision", "2", "--reason", "test")
            self.assertEqual(successor.returncode, 0, successor.stderr)

    def test_cli_strict_json_error_is_structured(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "manifest.json"
            path.write_bytes(b'{"schema":"bbk.artifact-manifest.v1","schema":"duplicate"}')
            result = self.run_cli("artifact", "verify", str(path), "--root", temp)
            self.assertEqual(result.returncode, 2)
            value = json.loads(result.stdout)
            self.assertEqual(value["status"], "ERROR")
            self.assertEqual(value["diagnostic"]["code"], "JSON_DUPLICATE_KEY")

    def test_legacy_manifest_uses_shared_primitives(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "a.txt").write_text("a", encoding="utf-8")
            generated = self.run_cli("artifact", "manifest", "--root", str(root), "--path", "a.txt", "--output", "manifest.json")
            self.assertEqual(generated.returncode, 0, generated.stderr)
            verified = self.run_cli("artifact", "verify", "manifest.json", "--root", str(root))
            self.assertEqual(verified.returncode, 0, verified.stderr)
            self.assertEqual(json.loads(verified.stdout)["status"], "PASS")

    def test_thin_wrapper_imports_canonical_main_only(self):
        source = (ROOT / "tools" / "bbk_artifact.py").read_text(encoding="utf-8")
        self.assertIn("from artifact_packages import main", source)
        self.assertNotIn("def seal", source)
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "bbk_artifact.py"), "--help"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
