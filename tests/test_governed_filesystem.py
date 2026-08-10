from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import governed_filesystem as filesystem  # noqa: E402
import governed_state  # noqa: E402
import omp_binding_registry as registry  # noqa: E402
from tests._vcs_fixture import prepare_git_seed  # noqa: E402


class GovernedFilesystemTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.project = self.base / "campaign"
        self.project.mkdir()
        self.seed = prepare_git_seed(
            self.base / "attempt-workspace",
            files={"src/a.txt": b"before\n"}, fixture_id="governed-filesystem",
        )
        self.workspace = self.seed.root
        (self.workspace / "docs").mkdir()
        baseline_commit = self.git("rev-parse", "HEAD").stdout.strip()
        self.jj_identity = {
            "jj_change_id": "change-1",
            "jj_commit_id": "commit-1",
            "operation_id": "a" * 64,
            "repository_root": str(self.workspace),
            "workspace_path": str(self.workspace),
            "workspace_name": "test",
            "identity_digest": "sha256:" + "b" * 64,
            "parent_commit_ids": [baseline_commit],
        }
        self.jj_patch = mock.patch.object(filesystem.jj_adapter, "identity", return_value=self.jj_identity)
        self.jj_patch.start()

    def tearDown(self):
        self.jj_patch.stop()
        self.temporary.cleanup()

    def git(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *arguments],
            cwd=self.workspace,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def binding(
        self,
        *,
        role: str = "bbk_worker",
        prefixes: list[Path] | None = None,
        mutation_classes: list[str] | None = None,
        session_id: str = "session-1",
        invocation_id: str = "invocation-1",
    ) -> dict:
        request = {
            "schema": "bbk.invocation-binding-create.v1",
            "session_id": session_id,
            "invocation_id": invocation_id,
            "role": role,
            "work_unit_id": "WU-TEST",
            "attempt_id": "attempt-1",
            "baseline_ref": "git:baseline",
            "candidate_ref": "candidate-1",
            "workspace_ref": str(self.workspace.resolve()),
            "authority_ref": "authority:user",
            "scope": {
                "path_prefixes": [str(path.resolve()) for path in (prefixes or [self.workspace / "src"])],
                "mutation_classes": mutation_classes or ["PRODUCT_CONTENT", "TEST_CONTENT"],
                "semantic_scope": ["component:test"],
            },
            "return_contract": "bbk.role-return.v2",
            "jj_change_id": "change-1",
            "idempotency_key": "binding-1",
        }
        return registry.create_initial_binding(
            self.project,
            request,
            capability_ref=f"role:{role}@1.0.0-alpha.17",
            created_at="2026-08-04T00:00:00Z",
        )[0]

    def envelope(
        self,
        binding: dict,
        *,
        operation: str,
        path: str = "src/a.txt",
        payload: dict | None = None,
        precondition: dict | None = None,
        mutation_class: str = "PRODUCT_CONTENT",
        idempotency_key: str = "mutation-1",
        session_id: str = "session-1",
        invocation_id: str = "invocation-1",
    ) -> dict:
        payload_value = payload or {}
        return {
            "schema": "bbk.governed-filesystem-execution.v1",
            "host_version": "omp/16.4.8",
            "session_id": session_id,
            "invocation_id": invocation_id,
            "intent": {
                "schema": "bbk.mutation-intent.v1",
                "binding_ref": binding["binding_id"],
                "operation": operation,
                "path": path,
                "content_or_patch_digest": filesystem.payload_digest(payload_value),
                "expected_precondition": precondition or {"kind": "ANY"},
                "mutation_class": mutation_class,
                "idempotency_key": idempotency_key,
            },
            "payload": payload_value,
        }

    @staticmethod
    def digest(value: bytes) -> str:
        return "sha256:" + hashlib.sha256(value).hexdigest()

    def test_write_uses_bound_workspace_not_process_cwd_and_records_all_receipts(self):
        binding = self.binding()
        other_cwd = self.base / "ambient-cwd"
        other_cwd.mkdir()
        payload = {"content": "after\n", "encoding": "utf-8"}
        envelope = self.envelope(
            binding,
            operation="WRITE",
            payload=payload,
            precondition={"kind": "SHA256", "sha256": self.digest(b"before\n")},
        )
        previous = Path.cwd()
        try:
            os.chdir(other_cwd)
            value = filesystem.execute(self.project, envelope)
        finally:
            os.chdir(previous)
        self.assertEqual("PASS", value["status"])
        self.assertEqual("APPLIED", value["result"]["effect_status"])
        self.assertEqual("src/a.txt", value["result"]["observed_path"])
        self.assertEqual("after\n", (self.workspace / "src" / "a.txt").read_text(encoding="utf-8"))
        self.assertFalse((other_cwd / "src" / "a.txt").exists())
        self.assertEqual([], list((self.workspace / "src").glob("*.bbk-*.tmp")))
        kinds = [item["receipt_kind"] for item in governed_state.all_receipts(self.project)]
        self.assertIn("GATE_DECISION", kinds)
        self.assertIn("VCS_MUTATION", kinds)
        self.assertIn("FILESYSTEM_MUTATION", kinds)
        self.assertRegex(value["result"]["receipt_ref"], r"^sha256:[0-9a-f]{64}$")

    def test_reviewer_can_read_but_cannot_write(self):
        binding = self.binding(role="bbk_reviewer", mutation_classes=["READ_ONLY"])
        read = filesystem.execute(
            self.project,
            self.envelope(
                binding,
                operation="READ",
                payload={},
                mutation_class="READ_ONLY",
                idempotency_key="read-1",
                precondition={"kind": "PRESENT"},
            ),
        )
        self.assertEqual("PASS", read["status"])
        self.assertEqual("before\n", read["content"])
        self.assertEqual("NO_CHANGE", read["result"]["effect_status"])

        payload = {"content": "forbidden\n", "encoding": "utf-8"}
        denied = filesystem.execute(
            self.project,
            self.envelope(
                binding,
                operation="WRITE",
                payload=payload,
                idempotency_key="write-denied",
            ),
        )
        self.assertEqual("BLOCK", denied["status"])
        self.assertIn(denied["reason_code"], {"ROLE_CAPABILITY_FORBIDDEN", "READ_ONLY_ROLE_MUTATION_FORBIDDEN"})
        self.assertEqual("before\n", (self.workspace / "src" / "a.txt").read_text(encoding="utf-8"))

    def test_parent_absolute_scope_and_symlink_escapes_fail_before_effect(self):
        binding = self.binding()
        payload = {"content": "escape\n", "encoding": "utf-8"}
        for path, code in (
            ("../escape.txt", "TRAVERSAL"),
            (str((self.base / "absolute.txt").resolve()), "ABSOLUTE"),
            ("src/../escape.txt", "TRAVERSAL"),
        ):
            with self.subTest(path=path), self.assertRaisesRegex(filesystem.GovernedFilesystemError, code):
                filesystem.execute(self.project, self.envelope(binding, operation="WRITE", path=path, payload=payload))
        self.assertFalse((self.base / "escape.txt").exists())
        self.assertFalse((self.base / "absolute.txt").exists())

        outside = self.base / "outside"
        outside.mkdir()
        link = self.workspace / "src" / "linked"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")
        with self.assertRaisesRegex(filesystem.GovernedFilesystemError, "SYMLINK"):
            filesystem.execute(
                self.project,
                self.envelope(binding, operation="WRITE", path="src/linked/escape.txt", payload=payload),
            )
        self.assertFalse((outside / "escape.txt").exists())

    def test_scope_escape_is_gate_blocked(self):
        binding = self.binding()
        payload = {"content": "outside scope\n", "encoding": "utf-8"}
        value = filesystem.execute(
            self.project,
            self.envelope(binding, operation="WRITE", path="docs/out.txt", payload=payload),
        )
        self.assertEqual("BLOCK", value["status"])
        self.assertEqual("WORKSPACE_SCOPE_ESCAPE", value["reason_code"])
        self.assertFalse((self.workspace / "docs" / "out.txt").exists())

    def test_designated_and_declared_sealed_packages_are_immutable(self):
        binding = self.binding(prefixes=[self.workspace])
        payload = {"content": "mutated\n", "encoding": "utf-8"}
        sealed = self.workspace / ".bbk" / "artifacts" / "sealed" / "pkg"
        sealed.mkdir(parents=True)
        target = sealed / "artifact.txt"
        target.write_text("sealed\n", encoding="utf-8")
        result = filesystem.execute(
            self.project,
            self.envelope(binding, operation="WRITE", path=".bbk/artifacts/sealed/pkg/artifact.txt", payload=payload),
        )
        self.assertEqual("BLOCK", result["status"])
        self.assertEqual("SEALED_SUBJECT_MUTATION_FORBIDDEN", result["reason_code"])
        self.assertEqual("sealed\n", target.read_text(encoding="utf-8"))

        package = self.workspace / "src" / "declared-package"
        package.mkdir()
        (package / "bbk-package.json").write_text(
            json.dumps({"schema": "bbk.artifact-package.v1", "lifecycle": "SEALED"}),
            encoding="utf-8",
        )
        artifact = package / "artifact.txt"
        artifact.write_text("declared sealed\n", encoding="utf-8")
        result = filesystem.execute(
            self.project,
            self.envelope(
                binding,
                operation="DELETE",
                path="src/declared-package/artifact.txt",
                payload={},
                idempotency_key="sealed-delete",
            ),
        )
        self.assertEqual("BLOCK", result["status"])
        self.assertEqual("SEALED_SUBJECT_MUTATION_FORBIDDEN", result["reason_code"])
        self.assertTrue(artifact.exists())

    def test_precondition_mismatch_is_structured_and_has_no_effect(self):
        binding = self.binding()
        payload = {"content": "after\n", "encoding": "utf-8"}
        value = filesystem.execute(
            self.project,
            self.envelope(
                binding,
                operation="WRITE",
                payload=payload,
                precondition={"kind": "SHA256", "sha256": "sha256:" + "0" * 64},
            ),
        )
        self.assertEqual("BLOCK", value["status"])
        self.assertEqual("MUTATION_PRECONDITION_FAILED", value["reason_code"])
        self.assertEqual("before\n", (self.workspace / "src" / "a.txt").read_text(encoding="utf-8"))
        self.assertEqual("BLOCKED", value["result"]["effect_status"])

    def test_exact_edit_and_delete_are_reconciled(self):
        binding = self.binding()
        edit_payload = {"old_text": "before", "new_text": "after", "replace_all": False}
        edit = filesystem.execute(
            self.project,
            self.envelope(
                binding,
                operation="EDIT",
                payload=edit_payload,
                precondition={"kind": "SHA256", "sha256": self.digest(b"before\n")},
                idempotency_key="edit-1",
            ),
        )
        self.assertEqual("APPLIED", edit["result"]["effect_status"])
        self.assertEqual("after\n", (self.workspace / "src" / "a.txt").read_text(encoding="utf-8"))
        delete = filesystem.execute(
            self.project,
            self.envelope(
                binding,
                operation="DELETE",
                payload={},
                precondition={"kind": "SHA256", "sha256": self.digest(b"after\n")},
                idempotency_key="delete-1",
            ),
        )
        self.assertEqual("APPLIED", delete["result"]["effect_status"])
        self.assertFalse((self.workspace / "src" / "a.txt").exists())
        self.assertIn("src/a.txt", delete["result"]["changed_paths"])

    def test_idempotent_retry_reuses_receipt_and_collision_blocks(self):
        binding = self.binding()
        payload = {"content": "after\n", "encoding": "utf-8"}
        request = self.envelope(binding, operation="WRITE", payload=payload, idempotency_key="stable-key")
        first = filesystem.execute(self.project, request)
        second = filesystem.execute(self.project, request)
        self.assertFalse(first["idempotent_reuse"])
        self.assertTrue(second["idempotent_reuse"])
        self.assertEqual(first["result"]["receipt_ref"], second["result"]["receipt_ref"])
        other_payload = {"content": "different\n", "encoding": "utf-8"}
        with self.assertRaisesRegex(filesystem.GovernedFilesystemError, "IDEMPOTENCY_COLLISION"):
            filesystem.execute(
                self.project,
                self.envelope(binding, operation="WRITE", payload=other_payload, idempotency_key="stable-key"),
            )

    def test_payload_digest_and_exact_host_binding_are_enforced(self):
        binding = self.binding()
        payload = {"content": "after\n", "encoding": "utf-8"}
        request = self.envelope(binding, operation="WRITE", payload=payload)
        request["intent"]["content_or_patch_digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(filesystem.GovernedFilesystemError, "PAYLOAD_DIGEST_MISMATCH"):
            filesystem.execute(self.project, request)

        request = self.envelope(binding, operation="WRITE", payload=payload, invocation_id="other-invocation")
        with self.assertRaisesRegex(filesystem.GovernedFilesystemError, "IDENTITY_MISMATCH"):
            filesystem.execute(self.project, request)

        request = self.envelope(binding, operation="WRITE", payload=payload)
        request["host_version"] = "omp/17.0.0"
        with self.assertRaisesRegex(filesystem.GovernedFilesystemError, "HOST_UNQUALIFIED"):
            filesystem.execute(self.project, request)

    def test_preexisting_out_of_scope_vcs_drift_blocks_before_target_effect(self):
        binding = self.binding()
        (self.workspace / "outside.txt").write_text("unrelated\n", encoding="utf-8")
        payload = {"content": "after\n", "encoding": "utf-8"}
        with self.assertRaisesRegex(filesystem.GovernedFilesystemError, "PREEXISTING_SCOPE_DRIFT"):
            filesystem.execute(self.project, self.envelope(binding, operation="WRITE", payload=payload))
        self.assertEqual("before\n", (self.workspace / "src" / "a.txt").read_text(encoding="utf-8"))

    def test_result_conforms_to_contract_schema(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed")
        binding = self.binding()
        value = filesystem.execute(
            self.project,
            self.envelope(binding, operation="READ", payload={}, mutation_class="READ_ONLY"),
        )
        schema = json.loads((ROOT / "spec" / "schemas" / "bbk-mutation-result-v1.schema.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(value["result"])


if __name__ == "__main__":
    unittest.main()
