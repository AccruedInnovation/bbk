from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import omp_binding_registry as registry  # noqa: E402
import role_return_runtime as runtime  # noqa: E402


class RoleReturnRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.project = Path(self.temporary.name) / "project"
        self.project.mkdir()
        self.parent = registry.create_initial_binding(
            self.project,
            {
                "schema": "bbk.invocation-binding-create.v1",
                "session_id": "parent-session-1",
                "invocation_id": "parent-invocation-1",
                "role": "bbk_root_orchestrator",
                "work_unit_id": "WU-ROOT",
                "attempt_id": "root-1",
                "baseline_ref": "git:baseline",
                "candidate_ref": "candidate:root",
                "workspace_ref": str(self.project),
                "authority_ref": "authority:user",
                "scope": {
                    "path_prefixes": [str(self.project / ".bbk")],
                    "mutation_classes": ["COORDINATION_METADATA"],
                    "semantic_scope": ["campaign:alpha17"],
                },
                "return_contract": "bbk.root-orchestrator-return.v2",
                "jj_change_id": "root-change",
                "idempotency_key": "root-binding",
            },
            capability_ref="role:bbk_root_orchestrator@1.0.0-alpha.17",
        )[0]
        self.worker = registry.create_initial_binding(
            self.project,
            {
                "schema": "bbk.invocation-binding-create.v1",
                "session_id": "worker-session-1",
                "parent_session_id": "parent-session-1",
                "invocation_id": "worker-invocation-1",
                "role": "bbk_worker",
                "work_unit_id": "WU-WORKER",
                "attempt_id": "worker-1",
                "baseline_ref": "git:baseline",
                "candidate_ref": "candidate:worker",
                "workspace_ref": str(self.project),
                "authority_ref": "authority:user",
                "scope": {
                    "path_prefixes": [str(self.project / "src" / "worker")],
                    "mutation_classes": ["PRODUCT_CONTENT"],
                    "semantic_scope": ["manual:alpha17", "worker:a"],
                },
                "return_contract": "bbk.worker-return.v2",
                "return_transport_mode": "STRUCTURED_RETURN_ONLY",
                "jj_change_id": "worker-change",
                "idempotency_key": "worker-binding",
            },
            capability_ref="role:bbk_worker@1.0.0-alpha.17",
        )[0]

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def identity(self) -> dict[str, str]:
        return {
            "session_id": "worker-session-1",
            "binding_ref": self.worker["binding_id"],
            "invocation_id": "worker-invocation-1",
        }

    @staticmethod
    def compact_result() -> dict[str, object]:
        return {
            "work_unit_ref": {"id": "WU-WORKER"},
            "changed_artifacts": {"paths": ["src/worker/result.txt"]},
            "checks_and_evidence": {"alpha17:verify": "PASS"},
            "claims_established_and_not_established": {
                "established": ["implementation artifact produced"],
                "not_established": ["release"],
            },
            "cleanup_and_residuals": {"cleanup": "complete", "residuals": []},
            "blockers": [],
        }

    def prepare_request(self, *, result: dict[str, object] | None = None, key: str = "return-1") -> dict[str, object]:
        return {
            "schema": runtime.PREPARE_SCHEMA,
            **self.identity(),
            "return_kind": "WORK_UNIT_RESULT",
            "detail_level": "COMPACT",
            "operational_disposition": "COMPLETE",
            "semantic_state_value": "READY_FOR_PARENT_INTEGRATION",
            "summary": "Worker completed the exact bounded WorkUnit.",
            "result": result if result is not None else self.compact_result(),
            "smallest_valid_next_action": {
                "action": "Integrate the admitted worker candidate.",
                "owner": "bbk_root_orchestrator",
                "reason": "The worker result is complete and schema-valid.",
                "affected_refs": [{"id": "candidate:worker"}],
                "unaffected_work_may_continue": True,
            },
            "effects_used": [{"effect_class": "PRODUCT_CONTENT", "path": "src/worker/result.txt"}],
            "denied_or_uncovered_effects": [],
            "violations_or_ambiguities": [],
            "checks_and_evidence": [{"id": "alpha17:verify", "status": "PASS"}],
            "prohibited_claims": ["This return does not establish Alpha.17 release acceptance."],
            "idempotency_key": key,
        }

    def test_managed_validator_candidates_are_bounded_and_deterministic(self) -> None:
        explicit = self.project / "managed-python.exe"
        with mock.patch.dict(os.environ, {"BBK_JSONSCHEMA_PYTHON": str(explicit)}, clear=False):
            candidates = runtime._validator_python_candidates(self.project)
        self.assertEqual(explicit, candidates[0])
        self.assertIn(
            self.project / ".bbk" / "tooling" / "jsonschema-4.25.1" / ("Scripts/python.exe" if os.name == "nt" else "bin/python"),
            candidates,
        )
        self.assertEqual(len(candidates), len({os.path.normcase(os.path.abspath(str(item))) for item in candidates}))

    def test_managed_validator_is_imported_in_place_without_python_reexec(self) -> None:
        managed = self.project / ".bbk" / "tooling" / "jsonschema-4.25.1"
        executable = managed / "Scripts" / "python.exe"
        site_packages = managed / "Lib" / "site-packages"
        executable.parent.mkdir(parents=True)
        site_packages.joinpath("jsonschema").mkdir(parents=True)
        site_packages.joinpath("referencing").mkdir(parents=True)
        executable.write_bytes(b"managed interpreter marker")
        site_packages.joinpath("jsonschema", "__init__.py").write_text("__version__ = 'test'\n", encoding="utf-8")
        site_packages.joinpath("referencing", "__init__.py").write_text(
            "class Resource:\n    @classmethod\n    def from_contents(cls, value): return value\n\nclass Registry:\n    def with_resource(self, *args): return self\n",
            encoding="utf-8",
        )
        previous_path = list(sys.path)
        previous_modules = {name: sys.modules.pop(name, None) for name in ("jsonschema", "referencing")}
        before = sorted(path.relative_to(self.project).as_posix() for path in self.project.rglob("*") if path.is_file())
        try:
            sys.path[:] = [item for item in previous_path if "site-packages" not in item.lower()]
            with mock.patch.dict(os.environ, {"BBK_JSONSCHEMA_PYTHON": str(executable), "PYTHONPATH": "ambient-forbidden"}, clear=False):
                with mock.patch.object(os, "execve", side_effect=AssertionError("managed Python must never be re-execed")):
                    result = runtime._maybe_reexec_managed_validator(self.project)
                configured_pythonpath = os.environ["PYTHONPATH"]
            self.assertEqual("CONFIGURED", result["status"])
            self.assertEqual([str(site_packages)], result["site_packages"])
            self.assertEqual(result["pythonpath"], configured_pythonpath)
            self.assertIn(str(site_packages), result["pythonpath"])
            self.assertNotIn("ambient-forbidden", result["pythonpath"])
            self.assertNotIn(str(executable), result["pythonpath"])
            self.assertEqual(before, sorted(path.relative_to(self.project).as_posix() for path in self.project.rglob("*") if path.is_file()))
            self.assertEqual([], list(self.project.rglob("*.pyc")))
        finally:
            sys.path[:] = previous_path
            for name, module in previous_modules.items():
                sys.modules.pop(name, None)
                if module is not None:
                    sys.modules[name] = module

    def test_direct_python_environment_fails_closed_on_wrong_executable(self) -> None:
        with mock.patch.dict(os.environ, {"BBK_DIRECT_PYTHON_EXECUTABLE": str(self.project / "wrong-python.exe")}, clear=False):
            with self.assertRaises(runtime.RoleReturnRuntimeError) as raised:
                runtime._enforce_direct_python_environment()
        self.assertEqual("ROLE_RETURN_PYTHON_EXECUTABLE_INVALID", raised.exception.code)

    def test_direct_python_environment_records_exact_flags(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "BBK_DIRECT_PYTHON_EXECUTABLE": sys.executable,
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONNOUSERSITE": "1",
            },
            clear=False,
        ):
            runtime._enforce_direct_python_environment()
        self.assertTrue(sys.flags.dont_write_bytecode)
        self.assertIn("-B", getattr(sys, "orig_argv", []))

    def test_all_role_compact_examples_are_schema_valid(self) -> None:
        _catalog, roles, _entries = runtime.load_package(ROOT)
        jsonschema, registry, _resources, _origins = runtime._validation_registry(ROOT)
        for role in roles:
            contract = role["return_contract"]
            example = {
                name: runtime._sample_for_field(name, contract["result_fields"][name])
                for name in contract["compact_result_fields"]
            }
            schema_path = ROOT / contract["compact_result_schema"]
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            errors = list(jsonschema.Draft202012Validator(schema, registry=registry).iter_errors(example))
            self.assertEqual([], errors, msg=f"{role['name']}: {[error.message for error in errors]}")

    def test_template_derives_direct_root_worker_parent_without_fabrication(self) -> None:
        value = runtime.template(
            self.project,
            ROOT,
            {"schema": runtime.TEMPLATE_SCHEMA, **self.identity()},
        )
        self.assertEqual("PASS", value["status"])
        self.assertEqual("CANDIDATE_PRODUCTION", value["invocation_mode"])
        self.assertEqual("bbk_root_orchestrator", value["parent_ref"]["role"])
        self.assertEqual(6, len(value["compact_result_fields"]))

    def test_prepare_and_resolve_round_trip_is_schema_valid_and_bound(self) -> None:
        prepared = runtime.prepare(self.project, ROOT, self.prepare_request())
        self.assertEqual("PASS", prepared["status"])
        self.assertRegex(prepared["return_ref"], r"^return:[0-9a-f]{64}$")
        document_from_prepare = prepared["yield_input"]["result"]["data"]
        self.assertEqual("bbk.role-return.v2", document_from_prepare["schema"])
        resolved = runtime.resolve_prepared(
            self.project,
            ROOT,
            {
                "schema": runtime.RESOLVE_SCHEMA,
                **self.identity(),
                "return_ref": prepared["return_ref"],
                "tool_call_id": "yield-1",
            },
        )
        self.assertEqual("ADMITTED", resolved["status"])
        document = resolved["yield_input"]["result"]["data"]
        self.assertEqual("bbk.role-return.v2", document["schema"])
        self.assertEqual("bbk.worker-return.v2", document["contract"])
        self.assertEqual("bbk_root_orchestrator", document["parent_ref"]["role"])
        runtime.validate_role_return(document, "bbk_worker", ROOT)

    def test_manual_worker_reviewer_and_validator_templates_prepare_valid_returns(self) -> None:
        roles = (
            ("bbk_reviewer", "REVIEW_REPORT", "READY_FOR_PARENT_INTEGRATION"),
            ("bbk_validator", "ASSERTION_REPORT", "READY_FOR_ORCHESTRATOR_INTEGRATION"),
        )
        for role_name, return_kind, semantic_state in roles:
            with self.subTest(role=role_name):
                slug = role_name.removeprefix("bbk_").replace("_", "-")
                session_id = f"{slug}-session"
                invocation_id = f"{slug}-invocation"
                binding = registry.create_initial_binding(
                    self.project,
                    {
                        "schema": "bbk.invocation-binding-create.v1",
                        "session_id": session_id,
                        "parent_session_id": "parent-session-1",
                        "invocation_id": invocation_id,
                        "role": role_name,
                        "work_unit_id": slug.upper(),
                        "attempt_id": f"{slug}-1",
                        "baseline_ref": "git:baseline",
                        "candidate_ref": "candidate:integrated",
                        "workspace_ref": str(self.project),
                        "authority_ref": "authority:user",
                        "scope": {
                            "path_prefixes": [str(self.project)],
                            "mutation_classes": ["COORDINATION_METADATA"],
                            "semantic_scope": ["manual:alpha17"],
                        },
                        "return_contract": f"bbk.{slug}-return.v2",
                        "return_transport_mode": "STRUCTURED_RETURN_ONLY",
                        "jj_change_id": f"{slug}-change",
                        "idempotency_key": f"{slug}-binding",
                    },
                    capability_ref=f"role:{role_name}@1.0.0-alpha.17",
                )[0]
                identity = {
                    "session_id": session_id,
                    "binding_ref": binding["binding_id"],
                    "invocation_id": invocation_id,
                }
                template = runtime.template(
                    self.project,
                    ROOT,
                    {"schema": runtime.TEMPLATE_SCHEMA, **identity},
                )
                prepared = runtime.prepare(
                    self.project,
                    ROOT,
                    {
                        "schema": runtime.PREPARE_SCHEMA,
                        **identity,
                        "return_kind": return_kind,
                        "detail_level": "COMPACT",
                        "operational_disposition": "COMPLETE",
                        "semantic_state_value": semantic_state,
                        "summary": f"{role_name} completed its bounded assignment.",
                        "result": json.loads(template["result_json_example"]),
                        "smallest_valid_next_action": {
                            "action": "Continue with the accepted parent route.",
                            "owner": "bbk_root_orchestrator",
                            "reason": "The structured return is complete and validated.",
                            "unaffected_work_may_continue": True,
                        },
                        "effects_used": [],
                        "denied_or_uncovered_effects": [],
                        "violations_or_ambiguities": [],
                        "idempotency_key": f"{slug}-return",
                    },
                )
                document = prepared["yield_input"]["result"]["data"]
                self.assertEqual(role_name, document["role"])
                self.assertEqual(f"bbk.{slug}-return.v2", document["contract"])
                runtime.validate_role_return(document, role_name, ROOT)

    def test_invalid_role_result_returns_focused_json_pointer_diagnostics(self) -> None:
        request = self.prepare_request(result={"work_unit_ref": "WU-WORKER"})
        with self.assertRaises(runtime.RoleReturnRuntimeError) as raised:
            runtime.prepare(self.project, ROOT, request)
        self.assertEqual("BBK_ROLE_RETURN_SCHEMA_INVALID", raised.exception.code)
        self.assertTrue(raised.exception.diagnostics)
        pointers = {item["instance_pointer"] for item in raised.exception.diagnostics}
        self.assertTrue(any(pointer.startswith("/result") for pointer in pointers))

    def test_idempotency_key_cannot_be_reused_for_changed_return(self) -> None:
        runtime.prepare(self.project, ROOT, self.prepare_request())
        changed = self.compact_result()
        changed["changed_artifacts"] = {"paths": ["src/worker/other.txt"]}
        with self.assertRaises(runtime.RoleReturnRuntimeError) as raised:
            runtime.prepare(self.project, ROOT, self.prepare_request(result=changed))
        self.assertEqual("ROLE_RETURN_IDEMPOTENCY_COLLISION", raised.exception.code)

    def test_direct_validation_rejects_schema_valid_return_for_wrong_subject(self) -> None:
        prepared = runtime.prepare(self.project, ROOT, self.prepare_request())
        resolved = runtime.resolve_prepared(
            self.project,
            ROOT,
            {
                "schema": runtime.RESOLVE_SCHEMA,
                **self.identity(),
                "return_ref": prepared["return_ref"],
                "tool_call_id": "yield-source",
            },
        )
        document = resolved["yield_input"]["result"]["data"]
        document["subject_ref"]["id"] = "WU-OTHER"
        with self.assertRaises(runtime.RoleReturnRuntimeError) as raised:
            runtime.validate_request(
                self.project,
                ROOT,
                {
                    "schema": runtime.VALIDATE_SCHEMA,
                    **self.identity(),
                    "tool_call_id": "yield-direct-wrong-subject",
                    "document": document,
                },
            )
        self.assertEqual("BBK_ROLE_RETURN_BINDING_INVALID", raised.exception.code)
        self.assertIn("/subject_ref/id", {item["instance_pointer"] for item in raised.exception.diagnostics})

    def test_direct_validation_rejects_schema_valid_return_for_wrong_session(self) -> None:
        prepared = runtime.prepare(self.project, ROOT, self.prepare_request())
        resolved = runtime.resolve_prepared(
            self.project,
            ROOT,
            {
                "schema": runtime.RESOLVE_SCHEMA,
                **self.identity(),
                "return_ref": prepared["return_ref"],
                "tool_call_id": "yield-source-session",
            },
        )
        document = resolved["yield_input"]["result"]["data"]
        document["executor"]["host_session_id"] = "other-session"
        document["attempt_ref"]["host_session_id"] = "other-session"
        with self.assertRaises(runtime.RoleReturnRuntimeError) as raised:
            runtime.validate_request(
                self.project,
                ROOT,
                {
                    "schema": runtime.VALIDATE_SCHEMA,
                    **self.identity(),
                    "tool_call_id": "yield-direct-wrong-session",
                    "document": document,
                },
            )
        self.assertEqual("BBK_ROLE_RETURN_BINDING_INVALID", raised.exception.code)
        pointers = {item["instance_pointer"] for item in raised.exception.diagnostics}
        self.assertEqual({"/executor/host_session_id", "/attempt_ref/host_session_id"}, pointers)

    def test_direct_validation_emits_durable_admission_receipt(self) -> None:
        prepared = runtime.prepare(self.project, ROOT, self.prepare_request())
        resolved = runtime.resolve_prepared(
            self.project,
            ROOT,
            {
                "schema": runtime.RESOLVE_SCHEMA,
                **self.identity(),
                "return_ref": prepared["return_ref"],
                "tool_call_id": "yield-source-admission",
            },
        )
        document = resolved["yield_input"]["result"]["data"]
        value = runtime.validate_request(
            self.project,
            ROOT,
            {
                "schema": runtime.VALIDATE_SCHEMA,
                **self.identity(),
                "tool_call_id": "yield-direct-admission",
                "document": document,
            },
        )
        self.assertEqual("PASS", value["status"])
        self.assertRegex(value["return_ref"], r"^return:[0-9a-f]{64}$")
        self.assertRegex(value["binding_identity_digest"], r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(value["admission_receipt_ref"], r"^sha256:[0-9a-f]{64}$")
        self.assertTrue(value["prepared_return_verified"])
        receipt_root = self.project / ".bbk" / "governance" / "receipts" / "ROLE_RETURN_ADMISSION"
        self.assertTrue(receipt_root.is_dir())
        admissions = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(receipt_root.glob("*.json"))]
        self.assertGreaterEqual(len(admissions), 2)
        matching = [item for item in admissions if item["receipt_id"] == value["admission_receipt_ref"]]
        self.assertEqual(1, len(matching))
        self.assertEqual(value["binding_identity_digest"], matching[0]["content"]["binding_identity_digest"])

    def test_schema_valid_but_unprepared_direct_return_is_blocked(self) -> None:
        prepared = runtime.prepare(self.project, ROOT, self.prepare_request())
        document = prepared["yield_input"]["result"]["data"]
        record_path = self.project / ".bbk" / "governance" / "role-returns" / f"{prepared['return_ref'].split(':', 1)[1]}.json"
        record_path.unlink()
        with self.assertRaises(runtime.RoleReturnRuntimeError) as raised:
            runtime.validate_request(
                self.project,
                ROOT,
                {
                    "schema": runtime.VALIDATE_SCHEMA,
                    **self.identity(),
                    "tool_call_id": "yield-unprepared",
                    "document": document,
                },
            )
        self.assertEqual("ROLE_RETURN_PREPARATION_REQUIRED", raised.exception.code)
        self.assertIn("bbk_return_prepare", raised.exception.smallest_next_action)

    def test_prepared_return_state_rejects_symlinked_directory(self) -> None:
        governance = self.project / ".bbk" / "governance"
        governance.mkdir(parents=True, exist_ok=True)
        target = Path(self.temporary.name) / "outside-role-returns"
        target.mkdir()
        link = governance / "role-returns"
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")
        with self.assertRaises(runtime.RoleReturnRuntimeError) as raised:
            runtime.prepare(self.project, ROOT, self.prepare_request())
        self.assertEqual("ROLE_RETURN_STATE_PATH_UNSAFE", raised.exception.code)

    def test_cli_project_root_rejects_symlink(self) -> None:
        link = Path(self.temporary.name) / "project-link"
        try:
            link.symlink_to(self.project, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")
        with self.assertRaises(runtime.RoleReturnRuntimeError) as raised:
            runtime._project_root(link)  # noqa: SLF001 - security boundary regression
        self.assertEqual("ROLE_RETURN_PROJECT_ROOT_INVALID", raised.exception.code)

    def test_token_is_not_transferable_to_another_active_binding(self) -> None:
        prepared = runtime.prepare(self.project, ROOT, self.prepare_request())
        second = registry.create_initial_binding(
            self.project,
            {
                **self.worker["request"],
                "session_id": "worker-session-2",
                "invocation_id": "worker-invocation-2",
                "attempt_id": "worker-2",
                "idempotency_key": "worker-binding-2",
            },
            capability_ref="role:bbk_worker@1.0.0-alpha.17",
        )[0]
        with self.assertRaises(runtime.RoleReturnRuntimeError) as raised:
            runtime.resolve_prepared(
                self.project,
                ROOT,
                {
                    "schema": runtime.RESOLVE_SCHEMA,
                    "session_id": "worker-session-2",
                    "binding_ref": second["binding_id"],
                    "invocation_id": "worker-invocation-2",
                    "return_ref": prepared["return_ref"],
                    "tool_call_id": "yield-2",
                },
            )
        self.assertEqual("ROLE_RETURN_TOKEN_BINDING_MISMATCH", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
