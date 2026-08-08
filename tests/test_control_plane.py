from __future__ import annotations

import json
import os
import shutil
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

import control_plane  # noqa: E402
from gate_kernel import canonical_digest  # noqa: E402
from governed_state import append_receipt  # noqa: E402
from omp_binding_registry import create_initial_binding  # noqa: E402
from substrate import beads_adapter  # noqa: E402

BD = os.environ.get("BBK_TEST_BD") or shutil.which("bd")


def capability_ref(role: str) -> str:
    value = json.loads((ROOT / "spec" / "role-capabilities" / f"{role}.json").read_text(encoding="utf-8"))
    return f"role:{role}@{value['policy_version']}#{value['manifest_digest']}"


class ControlPlaneFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.project = Path(self.temporary.name) / "project"
        self.project.mkdir()
        (self.project / ".bbk" / "coordination").mkdir(parents=True)
        self.actor = self.create_actor()
        self.worker, self.registration_ref = self.create_worker_attempt()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def create_actor(
        self,
        *,
        role: str = "bbk_root_orchestrator",
        session_id: str = "parent-session-1",
        invocation_id: str = "parent-invocation-1",
        mutation_classes: list[str] | None = None,
        capability: str | None = None,
    ) -> dict:
        request = {
            "schema": "bbk.invocation-binding-create.v1",
            "session_id": session_id,
            "invocation_id": invocation_id,
            "role": role,
            "work_unit_id": "WU-CONTROL",
            "attempt_id": "attempt-control-1",
            "baseline_ref": "git:main",
            "candidate_ref": "candidate:control",
            "workspace_ref": str(self.project.resolve()),
            "authority_ref": "authority:user",
            "scope": {
                "path_prefixes": [str((self.project / ".bbk" / "coordination").resolve())],
                "mutation_classes": mutation_classes or ["COORDINATION_METADATA"],
                "semantic_scope": ["campaign:alpha17"],
            },
            "return_contract": f"bbk.{role.removeprefix('bbk_').replace('_', '-')}-return.v2",
            "jj_change_id": "control-plane",
            "idempotency_key": f"binding:{role}:{session_id}",
        }
        binding, _ = create_initial_binding(
            self.project,
            request,
            capability_ref=capability or capability_ref(role),
            created_at="2026-08-04T00:00:00Z",
        )
        return binding

    def create_worker_attempt(self) -> tuple[dict, str]:
        workspace = self.project / "attempts" / "wu-one"
        (workspace / "src").mkdir(parents=True)
        planned = "planned-session:" + ("a" * 64)
        request = {
            "schema": "bbk.invocation-binding-create.v1",
            "session_id": planned,
            "parent_session_id": "parent-session-1",
            "invocation_id": "invocation:" + ("b" * 64),
            "role": "bbk_worker",
            "work_unit_id": "WU-ONE",
            "attempt_id": "attempt-1",
            "baseline_ref": "git:main",
            "candidate_ref": "candidate:one",
            "workspace_ref": str(workspace.resolve()),
            "authority_ref": "authority:user",
            "scope": {
                "path_prefixes": [str((workspace / "src").resolve())],
                "mutation_classes": ["PRODUCT_CONTENT"],
                "semantic_scope": ["component:one"],
            },
            "return_contract": "bbk.worker-return.v2",
            "jj_change_id": "change-worker-one",
            "idempotency_key": "worker-binding-one",
        }
        binding, _ = create_initial_binding(
            self.project,
            request,
            capability_ref=capability_ref("bbk_worker"),
            created_at="2026-08-04T00:01:00Z",
        )
        core = {
            "schema": "bbk.work-unit-attempt-registration.v1",
            "idempotency_key": "spawn-one-attempt-1",
            "request_digest": "sha256:" + ("1" * 64),
            "planned_binding_ref": binding["binding_id"],
            "planned_session_id": planned,
            "parent_binding_ref": self.actor["binding_id"],
            "parent_session_id": "parent-session-1",
            "parent_invocation_id": "parent-invocation-1",
            "host_version": "omp/16.4.8",
            "invocation_id": request["invocation_id"],
            "role": "bbk_worker",
            "work_unit_id": "WU-ONE",
            "attempt_id": "attempt-1",
            "baseline_ref": "git:main",
            "candidate_ref": "candidate:one",
            "workspace_ref": str(workspace.resolve()),
            "jj_change_id": "change-worker-one",
            "authority_ref": "authority:user",
            "scope": request["scope"],
            "return_contract": "bbk.worker-return.v2",
            "capability_ref": capability_ref("bbk_worker"),
            "task_name": "worker-one",
            "assignment_digest": "sha256:" + ("2" * 64),
            "packet_digest": "sha256:" + ("3" * 64),
            "task_input_digest": "sha256:" + ("4" * 64),
            "status": "REGISTERED",
        }
        registration_ref = f"sha256:{canonical_digest(core)}"
        content = {**core, "registration_id": registration_ref}
        append_receipt(
            self.project,
            "WORK_UNIT_ATTEMPT_REGISTRATION",
            content,
            receipt_id=registration_ref,
            recorded_at="2026-08-04T00:02:00Z",
        )
        return binding, registration_ref

    def common(self, schema: str, *, work_unit: str = "WU-ONE", attempt: str = "attempt-1", revision: int = 0) -> dict:
        return {
            "schema": schema,
            "host_version": "omp/16.4.8",
            "session_id": "parent-session-1",
            "binding_ref": self.actor["binding_id"],
            "invocation_id": "parent-invocation-1",
            "command_id": f"command:{schema}:{revision}",
            "work_unit_id": work_unit,
            "attempt_id": attempt,
            "correlation_id": f"correlation:{work_unit}:{attempt}",
            "payload_summary": f"Coordinate {work_unit} {attempt}",
            "expected_revision": revision,
            "idempotency_key": f"idempotency:{schema}:{work_unit}:{revision}",
            "evidence_refs": [],
            "finding_refs": [],
        }

    def assign_request(self, *, revision: int = 0) -> dict:
        return {
            **self.common("bbk.control-assign.v1", revision=revision),
            "worker_binding_ref": self.worker["binding_id"],
            "attempt_registration_ref": self.registration_ref,
        }


class ControlPlaneUnitTests(ControlPlaneFixture):
    @staticmethod
    def projection(operation: str = "ASSIGN") -> dict:
        return {
            "schema": "bbk.beads-projection-receipt.v1",
            "status": "PASS",
            "operation": operation,
            "subject": {"work_unit": "WU-ONE", "attempt": "attempt-1"},
            "previous_revision": 0,
            "new_revision": 1,
            "bd_receipt": "sha256:" + ("5" * 64),
            "semantic_record_ref": "sha256:" + ("6" * 64),
            "backend": {"issue_id": "WU-ONE", "transition": "CREATE", "projected_status": "open", "exit_code": 0},
            "projection_id": "sha256:" + ("7" * 64),
            "idempotent_reuse": False,
        }

    def test_assign_is_bound_to_attempt_registration_and_never_carries_product_content(self) -> None:
        with mock.patch.object(beads_adapter, "execute_coordination", return_value=self.projection()) as execute:
            value = control_plane.execute_control(self.project, self.assign_request())
        self.assertEqual("PASS", value["status"])
        self.assertEqual("ASSIGN", value["operation"])
        command = execute.call_args.args[2]
        self.assertEqual("bbk.coordination-command.v1", command["schema"])
        self.assertEqual("CREATE", command["transition"])
        self.assertEqual(self.worker["binding_id"], command["assignment"]["worker_binding_ref"])
        self.assertEqual(self.registration_ref, command["assignment"]["attempt_registration_ref"])
        self.assertEqual("bbk_worker", command["assignment"]["assignee_role"])
        self.assertNotIn("content", command)
        self.assertNotIn("patch", command)
        self.assertEqual("DENIED", value["policy"]["product_mutation_authority"])
        self.assertEqual("DENIED", value["policy"]["raw_bd_authority"])

    def test_reassignment_uses_annotation_without_recreating_bead(self) -> None:
        with mock.patch.object(beads_adapter, "execute_coordination", return_value=self.projection()) as execute:
            control_plane.execute_control(self.project, self.assign_request(revision=4))
        self.assertEqual("ANNOTATE", execute.call_args.args[2]["transition"])

    def test_update_requires_typed_transition_attempt_and_correlation(self) -> None:
        request = {**self.common("bbk.control-update.v1", revision=2), "transition": "BLOCK"}
        projection = self.projection("UPDATE")
        projection.update(previous_revision=2, new_revision=3)
        projection["backend"]["transition"] = "BLOCK"
        with mock.patch.object(beads_adapter, "execute_coordination", return_value=projection) as execute:
            value = control_plane.execute_control(self.project, request)
        command = execute.call_args.args[2]
        self.assertEqual(("WU-ONE", "attempt-1", "BLOCK"), (command["work_unit"], command["attempt"], command["transition"]))
        self.assertEqual("correlation:WU-ONE:attempt-1", command["correlation_id"])
        self.assertEqual("UPDATE", value["operation"])

    def test_integration_request_derives_current_revision_when_omitted(self) -> None:
        request = {
            **self.common("bbk.control-integrate-request.v1", work_unit="WU-INTEGRATE", attempt="attempt-int"),
            "source_candidate_refs": ["candidate:one", "candidate:two"],
            "target_candidate_ref": "candidate:integrated",
            "conflict_classification": "CONTENT_NEUTRAL",
        }
        request.pop("expected_revision")
        projection = self.projection("INTEGRATE_REQUEST")
        projection.update(previous_revision=3, new_revision=4)
        with (
            mock.patch.object(beads_adapter, "current_revision", return_value=3) as current_revision,
            mock.patch.object(beads_adapter, "find_coordination_idempotent", return_value=None),
            mock.patch.object(beads_adapter, "execute_coordination", return_value=projection) as execute,
        ):
            value = control_plane.execute_control(self.project, request)
        current_revision.assert_called_once_with(self.project.resolve(), "WU-INTEGRATE")
        command = execute.call_args.args[2]
        self.assertEqual(3, command["expected_revision"])
        self.assertEqual("ANNOTATE", command["transition"])
        self.assertEqual("DERIVED_CURRENT", value["policy"]["expected_revision_source"])

    def test_integration_request_retry_reuses_idempotent_record_revision(self) -> None:
        request = {
            **self.common("bbk.control-integrate-request.v1", work_unit="WU-INTEGRATE", attempt="attempt-int"),
            "source_candidate_refs": ["candidate:one"],
            "target_candidate_ref": "candidate:integrated",
            "conflict_classification": "CONTENT_NEUTRAL",
        }
        request.pop("expected_revision")
        prior = {"content": {"command": {"expected_revision": 0}}}
        with (
            mock.patch.object(beads_adapter, "find_coordination_idempotent", return_value=prior),
            mock.patch.object(beads_adapter, "current_revision") as current_revision,
            mock.patch.object(beads_adapter, "execute_coordination", return_value=self.projection("INTEGRATE_REQUEST")) as execute,
        ):
            value = control_plane.execute_control(self.project, request)
        current_revision.assert_not_called()
        self.assertEqual(0, execute.call_args.args[2]["expected_revision"])
        self.assertEqual("CREATE", execute.call_args.args[2]["transition"])
        self.assertEqual("IDEMPOTENT_RECORD", value["policy"]["expected_revision_source"])

    def test_content_changing_integration_is_request_only_and_routes_to_worker(self) -> None:
        request = {
            **self.common("bbk.control-integrate-request.v1", work_unit="WU-INTEGRATE", attempt="attempt-int-1"),
            "source_candidate_refs": ["candidate:backend", "candidate:frontend"],
            "target_candidate_ref": "candidate:integrated",
            "conflict_classification": "CONTENT_CHANGING",
        }
        projection = self.projection("INTEGRATE_REQUEST")
        projection["subject"] = {"work_unit": "WU-INTEGRATE", "attempt": "attempt-int-1"}
        with mock.patch.object(beads_adapter, "execute_coordination", return_value=projection) as execute:
            value = control_plane.execute_control(self.project, request)
        integration = execute.call_args.args[2]["integration"]
        self.assertTrue(integration["integration_worker_required"])
        self.assertEqual("BOUND_INTEGRATION_WORKER", integration["requested_route"])
        self.assertEqual("DENIED", integration["orchestrator_conflict_resolution_authority"])
        self.assertEqual("REQUEST_RECORDED_ONLY", integration["effect_performed"])
        self.assertTrue(value["policy"]["integration_worker_required"])
        self.assertIn("must not repair", value["smallest_next_action"])

    def test_content_neutral_integration_remains_request_only(self) -> None:
        request = {
            **self.common("bbk.control-integrate-request.v1", work_unit="WU-INTEGRATE", attempt="attempt-int-1"),
            "source_candidate_refs": ["candidate:one"],
            "target_candidate_ref": "candidate:integrated",
            "conflict_classification": "CONTENT_NEUTRAL",
        }
        with mock.patch.object(beads_adapter, "execute_coordination", return_value=self.projection("INTEGRATE_REQUEST")):
            value = control_plane.execute_control(self.project, request)
        self.assertFalse(value["policy"]["integration_worker_required"])
        self.assertEqual("CONTENT_NEUTRAL_INTEGRATION_ADAPTER", value["policy"]["requested_route"])
        self.assertEqual("REQUEST_RECORDED_ONLY", value["policy"]["effect_performed"])

    def test_non_orchestrator_and_stale_capability_fail_before_adapter(self) -> None:
        worker_actor = self.create_actor(
            role="bbk_worker",
            session_id="worker-session",
            invocation_id="worker-invocation",
            mutation_classes=["PRODUCT_CONTENT"],
        )
        request = {**self.common("bbk.control-update.v1"), "transition": "START"}
        request.update(binding_ref=worker_actor["binding_id"], session_id="worker-session", invocation_id="worker-invocation")
        with mock.patch.object(beads_adapter, "execute_coordination") as execute:
            with self.assertRaisesRegex(control_plane.ControlPlaneError, "ROLE_DENIED"):
                control_plane.execute_control(self.project, request)
            execute.assert_not_called()

        stale_actor = self.create_actor(
            session_id="stale-session",
            invocation_id="stale-invocation",
            capability="role:bbk_root_orchestrator@stale-policy",
        )
        request.update(
            binding_ref=stale_actor["binding_id"],
            session_id="stale-session",
            invocation_id="stale-invocation",
        )
        with mock.patch.object(beads_adapter, "execute_coordination") as execute:
            with self.assertRaisesRegex(control_plane.ControlPlaneError, "CAPABILITY_BINDING_MISMATCH"):
                control_plane.execute_control(self.project, request)
            execute.assert_not_called()

    def test_stale_worker_capability_blocks_assignment_before_adapter(self) -> None:
        capability_root = Path(self.temporary.name) / "role-capabilities"
        shutil.copytree(ROOT / "spec" / "role-capabilities", capability_root)
        worker_path = capability_root / "bbk_worker.json"
        worker = json.loads(worker_path.read_text(encoding="utf-8"))
        worker["policy_version"] = worker["policy_version"] + ".successor"
        worker["manifest_digest"] = "sha256:" + canonical_digest(
            {key: value for key, value in worker.items() if key != "manifest_digest"}
        )
        worker_path.write_text(json.dumps(worker, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        with mock.patch.object(beads_adapter, "execute_coordination") as execute:
            with self.assertRaisesRegex(control_plane.ControlPlaneError, "WORKER_CAPABILITY_BINDING_MISMATCH"):
                control_plane.execute_control(
                    self.project,
                    self.assign_request(),
                    capability_root=capability_root,
                )
            execute.assert_not_called()

    def test_single_writer_revalidates_strict_coordination_shape(self) -> None:
        with mock.patch.object(beads_adapter, "execute_coordination", return_value=self.projection()) as execute:
            control_plane.execute_control(self.project, self.assign_request())
        command = execute.call_args.args[2]
        beads_adapter._validate_coordination(command)

        with self.assertRaisesRegex(beads_adapter.BeadsAdapterError, "unsupported coordination fields"):
            beads_adapter._validate_coordination({**command, "raw_prompt": "secret"})
        with self.assertRaisesRegex(beads_adapter.BeadsAdapterError, "UPDATE forbids"):
            beads_adapter._validate_coordination({**command, "operation": "UPDATE", "transition": "START"})
        with self.assertRaisesRegex(beads_adapter.BeadsAdapterError, "PRODUCT_PAYLOAD_FORBIDDEN"):
            beads_adapter._validate_coordination({**command, "payload_summary": "diff --git a/x b/x"})

        integration = {
            **command,
            "operation": "INTEGRATE_REQUEST",
            "assignment": None,
            "integration": {
                "source_candidate_refs": ["candidate:one"],
                "target_candidate_ref": "candidate:target",
                "conflict_classification": "CONTENT_CHANGING",
                "requested_route": "CONTENT_NEUTRAL_INTEGRATION_ADAPTER",
                "integration_worker_required": False,
                "orchestrator_conflict_resolution_authority": "DENIED",
                "effect_performed": "REQUEST_RECORDED_ONLY",
            },
        }
        with self.assertRaisesRegex(beads_adapter.BeadsAdapterError, "route does not match"):
            beads_adapter._validate_coordination(integration)

    def test_product_payload_unknown_resolution_and_registration_mismatch_fail_closed(self) -> None:
        request = {**self.assign_request(), "content": "write the product directly"}
        with mock.patch.object(beads_adapter, "execute_coordination") as execute:
            with self.assertRaisesRegex(control_plane.ControlPlaneError, "SCHEMA_INVALID"):
                control_plane.execute_control(self.project, request)
            execute.assert_not_called()

        request = self.assign_request()
        request["payload_summary"] = "```diff\nproduct patch\n```"
        with mock.patch.object(beads_adapter, "execute_coordination") as execute:
            with self.assertRaisesRegex(control_plane.ControlPlaneError, "PRODUCT_PAYLOAD_FORBIDDEN"):
                control_plane.execute_control(self.project, request)
            execute.assert_not_called()

        integration = {
            **self.common("bbk.control-integrate-request.v1", work_unit="WU-I", attempt="attempt-i"),
            "source_candidate_refs": ["candidate:one"],
            "target_candidate_ref": "candidate:target",
            "conflict_classification": "CONTENT_CHANGING",
            "resolution": "take ours",
        }
        with self.assertRaisesRegex(control_plane.ControlPlaneError, "SCHEMA_INVALID"):
            control_plane.execute_control(self.project, integration)

        assignment = self.assign_request()
        assignment["attempt_id"] = "attempt-wrong"
        with self.assertRaisesRegex(control_plane.ControlPlaneError, "REGISTRATION_MISMATCH"):
            control_plane.execute_control(self.project, assignment)

    def test_control_plane_source_has_no_raw_beads_or_shell_execution_path(self) -> None:
        source = (TOOLS / "control_plane.py").read_text(encoding="utf-8")
        self.assertNotIn("subprocess.run", source)
        self.assertNotIn("subprocess.Popen", source)
        self.assertNotIn("os.system", source)
        self.assertIn("beads_adapter.execute_coordination", source)

    def test_cli_preserves_structured_denial(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(TOOLS / "control_plane.py"), "--root", str(self.project), "execute", "--request", "-"],
            input=json.dumps({"schema": "invalid"}),
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(2, completed.returncode)
        value = json.loads(completed.stdout)
        self.assertEqual("BLOCK", value["status"])
        self.assertEqual("CONTROL_PLANE_SCHEMA_INVALID", value["reason_code"])
        self.assertEqual("", completed.stderr)


@unittest.skipUnless(BD, "real bd executable not configured")
class ControlPlaneRealBeadsTests(ControlPlaneFixture):
    def setUp(self) -> None:
        super().setUp()
        subprocess.run(["git", "init", "-q"], cwd=self.project, check=True)
        subprocess.run(["git", "config", "user.name", "BBK Test"], cwd=self.project, check=True)
        subprocess.run(["git", "config", "user.email", "bbk@example.invalid"], cwd=self.project, check=True)
        subprocess.run(
            [str(BD), "init", "--non-interactive", "--prefix", "bbkt", "--skip-agents", "--skip-hooks", "--stealth"],
            cwd=self.project,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env={**os.environ, "BEADS_DISABLE_METRICS": "1"},
        )

    def test_assign_update_and_integration_request_project_through_single_writer(self) -> None:
        assigned = control_plane.execute_control(self.project, self.assign_request(), bd_path=BD)
        self.assertEqual("PASS", assigned["status"])
        self.assertEqual(1, assigned["projection"]["new_revision"])
        retry = control_plane.execute_control(self.project, self.assign_request(), bd_path=BD)
        self.assertTrue(retry["projection"]["idempotent_reuse"])
        self.assertEqual(assigned["projection"]["projection_id"], retry["projection"]["projection_id"])

        update = {**self.common("bbk.control-update.v1", revision=1), "transition": "START"}
        started = control_plane.execute_control(self.project, update, bd_path=BD)
        self.assertEqual(2, started["projection"]["new_revision"])
        issue = beads_adapter.read_backend_issue(self.project, "WU-ONE", bd_path=BD)
        issue = issue[0] if isinstance(issue, list) else issue
        self.assertEqual("in_progress", issue["status"])
        self.assertEqual("bbk_worker", issue.get("assignee"))

        integration = {
            **self.common("bbk.control-integrate-request.v1", work_unit="WU-INTEGRATE", attempt="attempt-int"),
            "source_candidate_refs": ["candidate:one"],
            "target_candidate_ref": "candidate:integrated",
            "conflict_classification": "UNKNOWN",
        }
        integration.pop("expected_revision")
        requested = control_plane.execute_control(self.project, integration, bd_path=BD)
        self.assertEqual("BOUND_INTEGRATION_WORKER", requested["policy"]["requested_route"])
        self.assertEqual("REQUEST_RECORDED_ONLY", requested["policy"]["effect_performed"])

        governance = self.project / ".bbk" / "governance" / "receipts"
        self.assertEqual(3, len(list((governance / "BEADS_COMMAND").glob("*.json"))))
        self.assertEqual(3, len(list((governance / "COORDINATION_COMMAND").glob("*.json"))))
        self.assertEqual(3, len(list((governance / "BEADS_PROJECTION").glob("*.json"))))
        projection = beads_adapter.rebuild_projection(self.project)
        self.assertEqual(2, projection["work_units"]["WU-ONE"]["revision"])
        self.assertEqual(1, projection["work_units"]["WU-INTEGRATE"]["revision"])


if __name__ == "__main__":
    unittest.main()
