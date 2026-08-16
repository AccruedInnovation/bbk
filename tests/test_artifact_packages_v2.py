from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import artifact_packages


def write_canonical(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(artifact_packages.canonical_json_bytes(value))


def make_v2_package(root: Path) -> tuple[dict[str, object], dict[str, object]]:
    root.mkdir(parents=True, exist_ok=True)
    payload = {"schema": "bbk.test-payload.v1", "value": "stable"}
    payload_path = root / "payload.json"
    payload_bytes = artifact_packages.canonical_json_bytes(payload)
    payload_path.write_bytes(payload_bytes)
    entry = {
        "artifactId": "payload",
        "path": "payload.json",
        "schema": None,
        "role": "semantic",
        "references": [],
        "mediaType": "application/json",
        "bytes": len(payload_bytes),
        "sha256": artifact_packages.sha256_bytes(payload_bytes),
        "canonicalization": artifact_packages.BBK_JSON_1,
    }
    descriptor = {
        "schema": "bbk.artifact-package-manifest.v2",
        "packageId": "v2-fixture",
        "revision": "1",
        "profile": {"id": "generic", "version": "1"},
        "subject": {"kind": "test", "id": "v2-subject", "revision": "1"},
        "metadata": {"purpose": "integration"},
        "predecessor": None,
        "successorReason": None,
        "artifacts": [entry],
    }
    _, content_sha = artifact_packages._content_identity(descriptor, [entry], [])
    manifest = {
        **descriptor,
        "canonicalization": artifact_packages.BBK_JSON_1,
        "referenceGraph": [],
        "closure": {"artifactCount": 1, "referenceCount": 0, "unresolved": []},
        "contentSha256": content_sha,
    }
    manifest_bytes = artifact_packages.canonical_json_bytes(manifest)
    package = {
        "schema": "bbk.artifact-package.v2",
        "packageId": manifest["packageId"],
        "revision": manifest["revision"],
        "profile": manifest["profile"],
        "subject": manifest["subject"],
        "metadata": manifest["metadata"],
        "predecessor": None,
        "artifacts": [entry],
        "manifestSha256": artifact_packages.sha256_bytes(manifest_bytes),
        "contentSha256": content_sha,
        "canonicalization": artifact_packages.BBK_JSON_1,
        "lifecycle": "SEALED",
    }
    receipt = {
        "schema": "bbk.artifact-package-seal-receipt.v2",
        "packageId": manifest["packageId"],
        "revision": manifest["revision"],
        "profile": manifest["profile"],
        "subject": manifest["subject"],
        "contentSha256": content_sha,
        "manifestSha256": package["manifestSha256"],
        "sealedAtUtc": "2026-08-14T20:00:00Z",
        "tool": {"name": "bbk", "version": "test"},
        "authorityBoundary": artifact_packages.AUTHORITY_BOUNDARY,
        "operationId": str(uuid.uuid4()),
        "publicationState": "NON_PUBLISHED",
        "evidenceClass": "INFORMATIONAL",
    }
    write_canonical(root / artifact_packages.MANIFEST_FILE, manifest)
    write_canonical(root / artifact_packages.PACKAGE_FILE, package)
    write_canonical(root / artifact_packages.RECEIPT_FILE, receipt)
    return package, manifest


class ArtifactPackageV2Tests(unittest.TestCase):
    def test_doctor_returns_strict_environment_bound_capabilities(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = artifact_packages.doctor(root, root)
            self.assertEqual(result["status"], "PASS", result)
            self.assertEqual(artifact_packages.validate_schema_instance(result, result["schema"]), [])
            self.assertEqual(set(result["capabilities"]), {
                "runtime", "workspace", "sameVolume", "durableFileWrite", "directoryFlush",
                "atomicReplace", "fileNoReplace", "directoryNoReplace", "osLocks", "readback", "cleanup",
            })

    def test_finalize_records_ordered_terminal_journal_and_reconcile_is_non_regenerating(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            draft = project / "draft"
            draft.mkdir(parents=True)
            (draft / "payload.bin").write_bytes(b"payload\r\n")
            write_canonical(draft / artifact_packages.DRAFT_FILE, {
                "schema": "bbk.artifact-package-draft.v1", "packageId": "journal-fixture", "revision": "1",
                "profile": {"id": "generic", "version": "1"}, "subject": {"kind": "test", "id": "journal-fixture"},
                "artifacts": [{"artifactId": "payload", "path": "payload.bin", "role": "semantic", "references": []}],
            })
            result = artifact_packages.finalize_draft(draft, project_root=project, finalized_at_utc="2026-08-14T20:00:00Z")
            self.assertEqual(result["status"], "PASS")
            journal = artifact_packages.load_path(Path(result["journalPath"]))
            self.assertEqual(journal["disposition"], "COMPLETED")
            self.assertEqual(journal["phase"], "COMPLETED")
            phases = [event["toPhase"] for event in journal["events"]]
            self.assertLess(phases.index("RECEIPT_VERIFIED"), phases.index("TARGET_VERIFIED_DECISIVE"))
            self.assertLess(phases.index("TARGET_VERIFIED_DECISIVE"), phases.index("CURRENT_PROJECTED"))
            self.assertEqual(artifact_packages.validate_operation_journal(result["journalPath"])["status"], "PASS")
            reconciled = artifact_packages.reconcile_operation(result["journalPath"])
            self.assertTrue(reconciled["readOnly"])
            self.assertFalse(reconciled["regenerated"])

    def test_sharing_retry_uses_exact_six_attempt_schedule(self):
        calls = []

        class SharingError(OSError):
            winerror = 32

        def effect():
            calls.append(len(calls))
            if len(calls) < 6:
                raise SharingError("sharing")
            return "ok"

        with mock.patch("time.sleep") as sleep:
            self.assertEqual(artifact_packages.retry_sharing(effect, effect="fixture"), "ok")
        self.assertEqual(len(calls), 6)
        self.assertEqual([item.args[0] for item in sleep.call_args_list], [0.025, 0.05, 0.1, 0.2, 0.4])

    def test_stale_lock_age_never_authorizes_takeover(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lock = root / "held.lock"
            lock.mkdir()
            write_canonical(lock / "lock.json", {"pid": 1, "host": "fixture"})
            old = 1
            os.utime(lock, (old, old))
            with self.assertRaises(artifact_packages.ArtifactPackageError) as raised:
                with artifact_packages._exclusive_lock(lock, operation="fixture", target=root / "target", recover_stale=True):
                    pass
            self.assertEqual(raised.exception.result["code"], "PACKAGE_LOCK_STALE_OR_AMBIGUOUS")
            self.assertTrue(lock.is_dir())
    def test_registry_is_readers_first_and_keeps_v1_as_writer(self):
        registry = artifact_packages.load_profile_registry()
        compatibility = registry["compatibility"]
        self.assertEqual(compatibility["mode"], "READERS_FIRST")
        self.assertTrue(compatibility["dualRead"])
        self.assertFalse(compatibility["v2WritesEnabled"])
        for family, value in compatibility["families"].items():
            self.assertIn("v1.schema.json", value["writer"])
            self.assertTrue(any("v2.schema.json" in reader for reader in value["readers"]), family)

    def test_v2_control_schemas_are_strict_and_generated_fields_are_not_draft_owned(self):
        valid = {
            "schema": "bbk.artifact-package-draft.v2",
            "packageId": "draft-v2",
            "revision": "1",
            "profile": {"id": "generic", "version": "1"},
            "subject": {"kind": "test", "id": "subject"},
            "artifacts": [{"artifactId": "payload", "path": "payload.bin", "role": "semantic"}],
        }
        self.assertEqual(artifact_packages.validate_schema_instance(valid, valid["schema"]), [])
        invalid = {**valid, "contentSha256": "0" * 64}
        findings = artifact_packages.validate_schema_instance(invalid, valid["schema"])
        self.assertTrue(any(item["code"] == "SCHEMA_ADDITIONAL_PROPERTY" for item in findings))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "draft"
            root.mkdir()
            (root / "payload.bin").write_bytes(b"x")
            (root / artifact_packages.DRAFT_FILE).write_text(json.dumps(invalid), encoding="utf-8")
            result = artifact_packages.preflight_draft(root)
            self.assertEqual(result["status"], "REJECTED")
            self.assertTrue(any(item["code"] == "SCHEMA_ADDITIONAL_PROPERTY" for item in result["findings"]))

    def test_v2_package_manifest_and_receipt_validate_and_verify(self):
        with tempfile.TemporaryDirectory() as temp:
            package, manifest = make_v2_package(Path(temp) / "package")
            receipt = artifact_packages.load_path(Path(temp) / "package" / artifact_packages.RECEIPT_FILE)
            self.assertEqual(artifact_packages.validate_schema_instance(package, "bbk.artifact-package.v2"), [])
            self.assertEqual(artifact_packages.validate_schema_instance(manifest, "bbk.artifact-package-manifest.v2"), [])
            self.assertEqual(artifact_packages.validate_schema_instance(receipt, "bbk.artifact-package-seal-receipt.v2"), [])
            result = artifact_packages.verify_package(Path(temp) / "package")
            self.assertEqual(result["status"], "PASS", result)
            self.assertTrue(result["readOnly"])
            self.assertEqual(result["contentSha256"], manifest["contentSha256"])

    def test_v2_content_identity_is_independent_of_physical_root(self):
        with tempfile.TemporaryDirectory() as temp:
            first, second = Path(temp) / "first", Path(temp) / "second"
            package_one, manifest_one = make_v2_package(first)
            package_two, manifest_two = make_v2_package(second)
            self.assertEqual(manifest_one["contentSha256"], manifest_two["contentSha256"])
            self.assertEqual(package_one["manifestSha256"], package_two["manifestSha256"])
            self.assertEqual(artifact_packages.verify_package(first)["status"], "PASS")
            self.assertEqual(artifact_packages.verify_package(second)["status"], "PASS")

    def test_v2_identity_tampering_is_rejected_without_repair(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "package"
            _, manifest = make_v2_package(root)
            path = root / artifact_packages.MANIFEST_FILE
            tampered = dict(manifest)
            tampered["contentSha256"] = "0" * 64
            write_canonical(path, tampered)
            before = path.read_bytes()
            result = artifact_packages.verify_package(root)
            self.assertEqual(result["status"], "REJECTED")
            self.assertTrue(result["readOnly"])
            self.assertEqual(path.read_bytes(), before)
            self.assertTrue(any(item["code"] == "PACKAGE_CONTENT_DIGEST_MISMATCH" for item in result["findings"]))

    def test_v1_seal_writer_remains_native_v1(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            draft = root / "draft"
            draft.mkdir()
            (draft / "payload.json").write_text('{"value":1}\n', encoding="utf-8")
            (draft / artifact_packages.DRAFT_FILE).write_text(json.dumps({
                "schema": "bbk.artifact-package-draft.v1",
                "packageId": "v1-writer",
                "revision": "1",
                "profile": {"id": "generic", "version": "1"},
                "subject": {"kind": "test", "id": "writer"},
                "artifacts": [{"artifactId": "payload", "path": "payload.json", "role": "semantic", "references": []}],
            }), encoding="utf-8")
            output = root / "sealed"
            artifact_packages.seal_draft(draft, output, sealed_at_utc="2026-08-14T20:00:00Z")
            for filename, schema in ((artifact_packages.PACKAGE_FILE, "bbk.artifact-package.v1"), (artifact_packages.MANIFEST_FILE, "bbk.artifact-package-manifest.v1"), (artifact_packages.RECEIPT_FILE, "bbk.artifact-package-seal-receipt.v1")):
                self.assertEqual(artifact_packages.load_path(output / filename)["schema"], schema)


if __name__ == "__main__":
    unittest.main()


