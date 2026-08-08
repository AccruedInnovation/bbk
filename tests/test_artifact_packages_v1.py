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
from tests._cli_support import run_cli as run_bbk_cli
from tests._path_support import assert_same_path, create_symlink_or_skip


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

    def test_finalize_publishes_project_local_sealed_package_and_external_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            project.mkdir()
            draft = make_draft(project / "drafts" / "pkg")
            result = artifact_packages.finalize_draft(
                draft,
                project_root=project,
                finalized_at_utc="2026-08-04T00:00:00Z",
            )
            sealed = project / ".bbk" / "artifacts" / "sealed" / "pkg-test-1"
            publication = project / ".bbk" / "artifacts" / "publications" / "pkg-test-1.json"
            current = project / ".bbk" / "artifacts" / "current" / "pkg-test.json"
            self.assertEqual(result["status"], "PASS")
            assert_same_path(self, result["outputRoot"], sealed)
            assert_same_path(self, result["publicationReceipt"], publication)
            assert_same_path(self, result["currentPointer"], current)
            self.assertTrue(sealed.is_dir())
            self.assertTrue(publication.is_file())
            self.assertTrue(current.is_file())
            self.assertFalse(publication.is_relative_to(sealed))
            self.assertFalse(current.is_relative_to(sealed))
            verified = artifact_packages.verify_package(sealed)
            self.assertEqual(verified["status"], "PASS")
            published = strict_json.load_path(publication)
            self.assertEqual(published["schema"], "bbk.artifact-package-publication.v1")
            self.assertEqual(
                artifact_packages.validate_schema_instance(published, published["schema"]),
                [],
            )
            self.assertEqual(published["artifactCount"], result["artifactCount"])
            self.assertEqual(published["completionClaims"], ["BYTE_INTEGRITY_VERIFIED"])
            self.assertTrue(published["policy"]["publicationMetadataOutsideSealedTree"])
            self.assertFalse(published["policy"]["mutableCoordinationOverrideUsed"])
            self.assertEqual(published["policy"]["mutableCoordinationPaths"], [])
            self.assertIn("semantic acceptance", published["claimsNotEstablished"])
            pointer = strict_json.load_path(current)
            self.assertEqual(
                artifact_packages.validate_schema_instance(pointer, pointer["schema"]),
                [],
            )
            self.assertEqual(pointer["contentSha256"], result["contentSha256"])
            self.assertEqual(pointer["publicationSha256"], artifact_packages.sha256_file(publication))
            self.assertEqual(result["publicationReceiptSha256"], artifact_packages.sha256_file(publication))
            self.assertFalse(any("publication" in path.relative_to(sealed).as_posix() for path in sealed.rglob("*")))

    def test_finalize_rejects_live_coordination_artifacts_by_default(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            draft = project / "draft"
            draft.mkdir(parents=True)
            (draft / "primary.json").write_text('{"value":1}\n', encoding="utf-8")
            (draft / "status.json").write_text('{"status":"active"}\n', encoding="utf-8")
            descriptor = draft_descriptor(artifacts=[
                {"artifactId": "primary", "path": "primary.json", "role": "semantic", "references": []},
                {"artifactId": "live-status", "path": "status.json", "role": "context", "references": []},
            ])
            write_json(draft / artifact_packages.DRAFT_FILE, descriptor)
            with self.assertRaises(artifact_packages.ArtifactPackageError) as raised:
                artifact_packages.finalize_draft(draft, project_root=project)
            self.assertEqual(raised.exception.result["code"], "PACKAGE_MUTABLE_COORDINATION_INCLUDED")
            self.assertFalse((project / ".bbk" / "artifacts" / "sealed" / "pkg-test-1").exists())

            result = artifact_packages.finalize_draft(
                draft,
                project_root=project,
                allow_mutable_coordination=True,
                finalized_at_utc="2026-08-04T00:00:00Z",
            )
            self.assertEqual(result["status"], "PASS")
            published = strict_json.load_path(Path(result["publicationReceipt"]))
            self.assertTrue(published["policy"]["mutableCoordinationOverrideUsed"])
            self.assertEqual(published["policy"]["mutableCoordinationPaths"], ["status.json"])

    def test_finalize_rolls_back_external_metadata_on_publication_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            project.mkdir()
            draft = make_draft(project / "draft")
            current = project / ".bbk" / "artifacts" / "current" / "pkg-test.json"
            prior = b'{"schema":"prior-current-pointer","revision":"0"}\n'
            current.parent.mkdir(parents=True)
            current.write_bytes(prior)

            with self.assertRaises(artifact_packages.ArtifactPackageError) as raised:
                artifact_packages.finalize_draft(
                    draft,
                    project_root=project,
                    finalized_at_utc="2026-08-04T00:00:00Z",
                    _test_fail_phase="after-current",
                )
            self.assertEqual(raised.exception.result["code"], "PACKAGE_FINALIZE_PUBLICATION_WRITE_FAILED")
            publication = project / ".bbk" / "artifacts" / "publications" / "pkg-test-1.json"
            self.assertFalse(publication.exists())
            self.assertEqual(current.read_bytes(), prior)
            sealed = project / ".bbk" / "artifacts" / "sealed" / "pkg-test-1"
            self.assertEqual(artifact_packages.verify_package(sealed)["status"], "PASS")

    def test_finalize_rejects_draft_and_output_containment(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            project.mkdir()
            draft = make_draft(project / "draft")
            with self.assertRaises(artifact_packages.ArtifactPackageError) as raised:
                artifact_packages.finalize_draft(
                    draft,
                    output_root=draft / "sealed",
                    project_root=project,
                )
            self.assertEqual(raised.exception.result["code"], "PACKAGE_FINALIZE_DRAFT_OUTPUT_OVERLAP")

    def test_finalize_rejects_publication_metadata_inside_draft(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            project.mkdir()
            draft = make_draft(project / "draft")
            with self.assertRaises(artifact_packages.ArtifactPackageError) as raised:
                artifact_packages.finalize_draft(
                    draft,
                    project_root=project,
                    publication_root=draft / "publication-metadata",
                )
            self.assertEqual(
                raised.exception.result["code"],
                "PACKAGE_FINALIZE_PUBLICATION_INSIDE_DRAFT",
            )

    def test_finalize_without_current_pointer_publishes_only_immutable_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            project.mkdir()
            draft = make_draft(project / "draft")
            result = artifact_packages.finalize_draft(
                draft,
                project_root=project,
                write_current_pointer=False,
                finalized_at_utc="2026-08-04T00:00:00Z",
            )
            self.assertEqual(result["status"], "PASS")
            self.assertIsNone(result["currentPointer"])
            self.assertTrue(Path(result["publicationReceipt"]).is_file())
            self.assertFalse((project / ".bbk" / "artifacts" / "current").exists())

    def test_one_shot_software_finalization_builds_generic_draft_and_binds_source_freshness(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            (project / "tests").mkdir(parents=True)
            (project / "app.py").write_text('print("hello")\n', encoding="utf-8")
            (project / "index.html").write_text("<html></html>\n", encoding="utf-8")
            (project / "README.md").write_text("# Demo\n", encoding="utf-8")
            (project / "tests" / "test_app.py").write_text("import unittest\n", encoding="utf-8")
            (project / "node_modules").mkdir()
            (project / "node_modules" / "ignored.js").write_text("ignored", encoding="utf-8")

            result = artifact_packages.finalize_source_set(
                project_root=project,
                package_id="demo-tool",
                revision="1",
                sources=["."],
                finalized_at_utc="2026-08-04T00:00:00Z",
            )
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["finalizationMode"], "software-source-set")
            self.assertIsNone(result["draftRoot"])
            self.assertTrue(result["stagedDraftRemoved"])
            self.assertEqual(result["sourceFreshness"], "PASS")
            self.assertEqual(result["artifactCount"], 4)
            sealed = Path(result["outputRoot"])
            self.assertTrue((sealed / "app.py").is_file())
            self.assertTrue((sealed / "index.html").is_file())
            self.assertFalse((sealed / "node_modules").exists())
            publication = json.loads(Path(result["publicationReceipt"]).read_text(encoding="utf-8"))
            self.assertEqual(publication["sourceBinding"]["mode"], "software-source-set")
            self.assertEqual(publication["sourceBinding"]["snapshot"]["fileCount"], 4)

            fresh = artifact_packages.verify_publication_freshness(
                result["publicationReceipt"], project_root=project
            )
            self.assertEqual(fresh["status"], "PASS")
            self.assertEqual(fresh["sourceStatus"], "PASS")
            pointer_from_elsewhere = artifact_packages.verify_publication_freshness(
                result["currentPointer"]
            )
            self.assertEqual(pointer_from_elsewhere["status"], "PASS")

            (project / "app.py").write_text('print("changed")\n', encoding="utf-8")
            stale = artifact_packages.verify_publication_freshness(
                result["publicationReceipt"], project_root=project
            )
            self.assertEqual(stale["status"], "REJECTED")
            self.assertEqual(stale["sourceStatus"], "STALE")
            self.assertEqual(
                [item["path"] for item in stale["findings"] if item["code"] == "PACKAGE_SOURCE_FILE_CHANGED"],
                ["app.py"],
            )

    def test_one_shot_software_exclusions_are_case_insensitive_across_hosts(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            (project / ".GIT").mkdir(parents=True)
            (project / "Node_Modules").mkdir()
            (project / "__PYCACHE__").mkdir()
            (project / "app.py").write_text('print("ready")\n', encoding="utf-8")
            (project / ".GIT" / "config").write_text("secret-ish metadata", encoding="utf-8")
            (project / "Node_Modules" / "dep.js").write_text("ignored", encoding="utf-8")
            (project / "__PYCACHE__" / "app.PYC").write_bytes(b"ignored")

            result = artifact_packages.finalize_source_set(
                project_root=project, package_id="case-demo", revision="1", sources=["."]
            )
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(
                [item["path"] for item in result["sourceSnapshot"]["files"]],
                ["app.py"],
            )

    def test_one_shot_finalization_detects_newly_selected_file_before_return(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            project.mkdir()
            (project / "app.py").write_text('print("ready")\n', encoding="utf-8")
            original_finalize = artifact_packages.finalize_draft

            def publish_then_mutate(*args, **kwargs):
                value = original_finalize(*args, **kwargs)
                Path(kwargs["project_root"], "late.py").write_text(
                    'print("late")\n', encoding="utf-8"
                )
                return value

            with mock.patch.object(artifact_packages, "finalize_draft", side_effect=publish_then_mutate):
                result = artifact_packages.finalize_source_set(
                    project_root=project, package_id="race-demo", revision="1", sources=["."]
                )
            self.assertEqual(result["status"], "REJECTED")
            self.assertEqual(result["code"], "PACKAGE_FINALIZE_SOURCE_CHANGED_AFTER_PUBLICATION")
            self.assertEqual(result["sourceFreshness"], "STALE")
            self.assertEqual(result["observedSourceSelection"], ["app.py", "late.py"])

    def test_freshness_returns_structured_error_for_missing_explicit_project_root(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            project.mkdir()
            (project / "app.py").write_text('print("ready")\n', encoding="utf-8")
            result = artifact_packages.finalize_source_set(
                project_root=project, package_id="root-demo", revision="1", sources=["app.py"]
            )
            missing = project / "missing-root"
            freshness = artifact_packages.verify_publication_freshness(
                result["publicationReceipt"], project_root=missing
            )
            self.assertEqual(freshness["status"], "REJECTED")
            self.assertEqual(freshness["code"], "PACKAGE_FRESHNESS_PROJECT_ROOT_INVALID")

    def test_one_shot_software_finalization_rejects_empty_selection(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            project.mkdir()
            (project / "ignored.pyc").write_bytes(b"x")
            with self.assertRaises(artifact_packages.ArtifactPackageError) as empty:
                artifact_packages.finalize_source_set(
                    project_root=project, package_id="demo", revision="1", sources=["."]
                )
            self.assertEqual(empty.exception.result["code"], "PACKAGE_FINALIZE_SOURCE_SET_EMPTY")

    def test_one_shot_software_finalization_rejects_native_symlink_source_root(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            project.mkdir()
            source = project / "source"
            source.mkdir()
            (source / "app.py").write_text('print("ready")\n', encoding="utf-8")
            link = project / "source-link"
            create_symlink_or_skip(self, link, source, target_is_directory=True)
            with self.assertRaises(artifact_packages.ArtifactPackageError) as raised:
                artifact_packages.finalize_source_set(
                    project_root=project,
                    package_id="demo",
                    revision="1",
                    sources=["source-link"],
                )
            self.assertEqual(raised.exception.result["code"], "PACKAGE_FINALIZE_SOURCE_SYMLINK")

    def test_freshness_rejects_tampered_publication_identity_and_pointer_digest(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            project.mkdir()
            (project / "app.py").write_text('print("ready")\n', encoding="utf-8")
            result = artifact_packages.finalize_source_set(
                project_root=project,
                package_id="demo",
                revision="1",
                sources=["app.py"],
                finalized_at_utc="2026-08-04T00:00:00Z",
            )
            publication_path = Path(result["publicationReceipt"])
            publication = json.loads(publication_path.read_text(encoding="utf-8"))
            publication["packageId"] = "other-demo"
            publication_path.write_text(
                json.dumps(publication, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            direct = artifact_packages.verify_publication_freshness(
                publication_path,
                project_root=project,
            )
            self.assertEqual(direct["status"], "REJECTED")
            self.assertIn(
                "PACKAGE_PUBLICATION_SEALED_IDENTITY_MISMATCH",
                {item["code"] for item in direct["metadataFindings"]},
            )

            through_pointer = artifact_packages.verify_publication_freshness(
                result["currentPointer"],
                project_root=project,
            )
            self.assertEqual(through_pointer["status"], "REJECTED")
            self.assertIn(
                "PACKAGE_PUBLICATION_DIGEST_MISMATCH",
                {item["code"] for item in through_pointer["metadataFindings"]},
            )

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
    def run_cli(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return run_bbk_cli(
            [sys.executable, str(ROOT / "tools" / "bbk.py"), "--json", *args],
            cwd=cwd or ROOT,
            check=False,
        )

    def test_bbk_cli_preflight_seal_verify_successor(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            draft = make_draft(root / "draft")
            preflight = self.run_cli("artifact", "preflight", str(draft))
            self.assertEqual(preflight.returncode, 0, preflight.stderr)
            self.assertEqual(json.loads(preflight.stdout)["status"], "PASS")
            finalize_project = root / "finalize-project"
            finalize_project.mkdir()
            finalize_draft = make_draft(finalize_project / "draft")
            finalized = self.run_cli("artifact", "finalize", str(finalize_draft), "--root", str(finalize_project))
            self.assertEqual(finalized.returncode, 0, finalized.stderr)
            finalized_value = json.loads(finalized.stdout)
            self.assertEqual(finalized_value["status"], "PASS")
            assert_same_path(
                self, finalized_value["outputRoot"],
                finalize_project / ".bbk" / "artifacts" / "sealed" / "pkg-test-1",
            )

            seal = self.run_cli("artifact", "seal", str(draft), "--output", str(root / "sealed"))
            self.assertEqual(seal.returncode, 0, seal.stderr)
            verify = self.run_cli("artifact", "verify", str(root / "sealed"))
            self.assertEqual(verify.returncode, 0, verify.stderr)
            successor = self.run_cli("artifact", "successor", str(root / "sealed"), "--output", str(root / "successor"), "--revision", "2", "--reason", "test")
            self.assertEqual(successor.returncode, 0, successor.stderr)


    def test_finalize_resolves_relative_draft_against_explicit_project_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "project"
            project.mkdir()
            make_draft(project / "draft")
            elsewhere = root / "elsewhere"
            elsewhere.mkdir()
            finalized = self.run_cli(
                "artifact", "finalize", "draft", "--root", str(project),
                cwd=elsewhere,
            )
            self.assertEqual(finalized.returncode, 0, finalized.stderr)
            value = json.loads(finalized.stdout)
            self.assertEqual(value["status"], "PASS")
            assert_same_path(self, value["draftRoot"], project / "draft")
            assert_same_path(
                self, value["outputRoot"],
                project / ".bbk" / "artifacts" / "sealed" / "pkg-test-1",
            )

    def test_cli_one_shot_finalize_and_freshness_for_python_html_project(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            project.mkdir()
            (project / "server.py").write_text("print('server')\n", encoding="utf-8")
            (project / "index.html").write_text("<html></html>\n", encoding="utf-8")
            finalized = self.run_cli(
                "artifact", "finalize", "--root", str(project),
                "--package-id", "session-inspector", "--revision", "1",
            )
            self.assertEqual(finalized.returncode, 0, finalized.stderr)
            value = json.loads(finalized.stdout)
            self.assertEqual(value["status"], "PASS")
            self.assertEqual(value["artifactCount"], 2)
            fresh = self.run_cli(
                "artifact", "freshness", value["publicationReceipt"], "--root", str(project)
            )
            self.assertEqual(fresh.returncode, 0, fresh.stderr)
            self.assertEqual(json.loads(fresh.stdout)["sourceStatus"], "PASS")

    def test_cli_argument_errors_are_structured_and_actionable(self):
        invalid = self.run_cli(
            "schema", "template", "--kind", "not-a-kind", "--output", "out.json"
        )
        self.assertEqual(invalid.returncode, 2)
        invalid_value = json.loads(invalid.stdout)
        self.assertEqual(invalid_value["schema"], "bbk.cli-error.v1")
        self.assertEqual(invalid_value["status"], "INVALID_ARGUMENT")
        self.assertEqual(invalid_value["code"], "INVALID_CHOICE")
        self.assertEqual(invalid_value["field"], "kind")
        self.assertEqual(invalid_value["received"], "not-a-kind")
        self.assertIn("artifact-manifest", invalid_value["valid_values"])
        self.assertIn("--kind", invalid_value["example_command"])
        self.assertEqual(invalid_value["documentation_command"], "bbk schema template --help")

        missing = self.run_cli("artifact", "finalize")
        self.assertEqual(missing.returncode, 2)
        missing_value = json.loads(missing.stdout)
        self.assertEqual(missing_value["schema"], "bbk.cli-error.v1")
        self.assertEqual(missing_value["status"], "INVALID_ARGUMENT")
        self.assertEqual(missing_value["code"], "INVALID_ARGUMENT")
        self.assertEqual(missing_value["field"], "finalization_mode")
        self.assertIn("--package-id", missing_value["example_command"])
        self.assertEqual(missing_value["documentation_command"], "bbk artifact finalize --help")

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
