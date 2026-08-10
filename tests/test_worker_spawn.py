from __future__ import annotations

import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import gate_kernel  # noqa: E402
import governed_state  # noqa: E402
import omp_binding_registry as registry  # noqa: E402
import worker_spawn  # noqa: E402
from tests._path_support import assert_different_path  # noqa: E402
from tests._alpha17_surface_support import schema_validate  # noqa: E402

JJ = (
    os.environ.get("BBK_TEST_JJ")
    or shutil.which("jj")
    or "/mnt/data/bbk-alpha17-18-work/toolkit/blueprint-one-shot-toolkit-linux-x86_64/bin/jj"
)
BD = (
    os.environ.get("BBK_TEST_BD")
    or shutil.which("bd")
    or "/mnt/data/bbk-alpha17-18-work/toolkit-bin/bd"
)


@unittest.skipUnless(Path(JJ).is_file() and Path(BD).is_file(), "real jj and bd executables are required")
class WorkerSpawnTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.project = self.base / "project"
        self.project.mkdir()
        (self.project / "README.md").write_text("baseline\n", encoding="utf-8")
        (self.project / ".bbk" / "coordination").mkdir(parents=True)
        subprocess.run(["git", "init", "-b", "main"], cwd=self.project, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["git", "config", "user.name", "BBK Test"], cwd=self.project, check=True)
        subprocess.run(["git", "config", "user.email", "bbk@example.invalid"], cwd=self.project, check=True)
        subprocess.run(["git", "add", "."], cwd=self.project, check=True)
        subprocess.run(["git", "commit", "-m", "baseline"], cwd=self.project, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run([str(JJ), "--no-pager", "--color=never", "git", "init", "--colocate", "."], cwd=self.project, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.parent = registry.create_initial_binding(
            self.project,
            {
                "schema": "bbk.invocation-binding-create.v1",
                "session_id": "parent-session-1",
                "invocation_id": "parent-invocation-1",
                "role": "bbk_root_orchestrator",
                "work_unit_id": "WU-CONTROL",
                "attempt_id": "attempt-control-1",
                "baseline_ref": "git:main",
                "candidate_ref": "candidate:control",
                "workspace_ref": str(self.project.resolve()),
                "authority_ref": "authority:user",
                "scope": {
                    "path_prefixes": [str((self.project / ".bbk" / "coordination").resolve())],
                    "mutation_classes": ["COORDINATION_METADATA"],
                    "semantic_scope": ["campaign:alpha17"],
                },
                "return_contract": "bbk.root-orchestrator-return.v2",
                "jj_change_id": "control-plane",
                "idempotency_key": "control-binding-1",
            },
            capability_ref="role:bbk_root_orchestrator@1.0.0-alpha.17",
            created_at="2026-08-04T00:00:00Z",
        )[0]

    def tearDown(self):
        self.temporary.cleanup()

    def request(self, **changes):
        value = {
            "schema": "bbk.bound-worker-spawn-create.v1",
            "host_version": "omp/16.4.8",
            "parent_binding_ref": self.parent["binding_id"],
            "parent_session_id": "parent-session-1",
            "parent_invocation_id": "parent-invocation-1",
            "task_name": "worker-one",
            "role": "bbk_worker",
            "work_unit_id": "WU-TEST-1",
            "attempt_id": "attempt-1",
            "baseline_ref": "git:main",
            "candidate_ref": "candidate:wu-test-1",
            "authority_ref": "authority:user",
            "return_contract": "bbk.worker-return.v2",
            "parent_revision": "@-",
            "workspace_parent": str(self.base / "attempt-workspaces"),
            "path_prefixes": ["src", "tests"],
            "mutation_classes": ["PRODUCT_CONTENT", "TEST_CONTENT"],
            "semantic_scope": ["component:demo"],
            "assignment": "Implement the assigned demo component and its tests.",
            "description": "WU-TEST-1 attempt-1",
            "idempotency_key": "spawn-wu-test-1-attempt-1",
        }
        value.update(changes)
        return value

    def compile(self, **changes):
        return worker_spawn.compile_bound_spawn(
            self.project,
            self.request(**changes),
            jj_path=JJ,
            bd_path=BD,
            recorded_at="2026-08-04T00:00:01Z",
        )

    def assert_schema_valid(self, instance, schema_name):
        schema_validate(instance, schema_name)

    def test_compile_allocates_one_workspace_binding_packet_and_reservation(self):
        self.assert_schema_valid(self.request(), "bbk-bound-worker-spawn-create-v1.schema.json")
        git_head_before = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.project, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        ).stdout.strip()
        result = self.compile()
        git_head_after = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.project, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        ).stdout.strip()
        self.assertEqual(git_head_before, git_head_after, "spawn-time Beads initialization must not advance product Git HEAD")
        tracked_beads = subprocess.run(
            ["git", "ls-files", ".beads"], cwd=self.project, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        ).stdout.strip()
        self.assertEqual("", tracked_beads)
        product_status = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=self.project, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        ).stdout
        self.assertNotIn(".beads/", product_status)
        self.assertNotIn(".gitignore", product_status)
        self.assert_schema_valid(result, "bbk-bound-worker-spawn-v1.schema.json")
        self.assert_schema_valid(result["worker_packet"], "bbk-bound-worker-packet-v1.schema.json")
        self.assertEqual("READY_TO_DISPATCH", result["status"])
        self.assertEqual("PASS", result["assignment_projection"]["status"])
        self.assertEqual("BBK_SPAWN_COMPILER", result["assignment_projection"]["assignment_generated_by"])
        self.assertEqual("READY", result["dispatch_status"]["status"])
        self.assertTrue(Path(result["workspace"]["workspace_path"]).is_dir())
        assert_different_path(self, self.project, result["workspace"]["workspace_path"])
        self.assertTrue(result["planned_session_id"].startswith("planned-session:"))
        # OMP accepts a presentation-only label, but the integrity-bearing
        # canonical envelope deliberately excludes it because 16.4.8 removes
        # the field before the BBK pre-effect hook.
        self.assertEqual("Dispatch immutable BBK child reservation", result["dispatch_input"].get("i"))
        self.assertEqual("bbk_worker", result["dispatch_input"]["tasks"][0]["agent"])
        self.assertEqual("worker-one", result["dispatch_input"]["tasks"][0]["name"])
        self.assertEqual(result["dispatch_ref"], registry.parse_dispatch_ref(result["dispatch_input"]))
        self.assertEqual(
            result["dispatch_input_digest"],
            registry.dispatch_envelope_digest(result["dispatch_input"]),
        )
        self.assertNotIn("task_input", result)
        self.assertNotIn("Implement the assigned", json.dumps(result["dispatch_input"]))
        admitted = registry.admit_spawn_dispatch(
            self.project,
            dispatch_ref=result["dispatch_ref"],
            dispatch_input_digest=result["dispatch_input_digest"],
            parent_session_id="parent-session-1",
            tool_call_id="task-call-compile-test",
            host_version="omp/16.4.8",
        )
        resolved = admitted["resolved_task_input"]
        self.assertEqual(1, len(resolved["tasks"]))
        self.assertEqual("bbk_worker", resolved["tasks"][0]["agent"])
        self.assertEqual("worker-one", resolved["tasks"][0]["name"])
        self.assertEqual("Implement the assigned demo component and its tests.", resolved["tasks"][0]["task"])
        marker = worker_spawn.parse_packet_marker(resolved["context"])
        self.assertEqual(result["planned_binding_ref"], marker["planned_binding_ref"])
        self.assertEqual(result["worker_packet"]["packet_digest"], marker["packet_digest"])
        self.assertEqual(result["task_input_digest"], admitted["resolved_task_input_digest"])
        context = result["worker_packet"]["binding_context"]
        self.assertEqual(result["workspace"]["jj_change_id"], context["jj_change_id"])
        self.assertEqual("omp/16.4.8", context["host_version"])
        self.assertEqual("worker-one", context["task_name"])
        self.assertEqual(["PRODUCT_CONTENT", "TEST_CONTENT"], context["scope"]["mutation_classes"])
        self.assertTrue(all(Path(item).is_absolute() for item in context["scope"]["path_prefixes"]))
        self.assertNotIn("Implement the assigned", json.dumps(governed_state.all_receipts(self.project)))
        kinds = {item["receipt_kind"] for item in governed_state.all_receipts(self.project)}
        self.assertIn("WORK_UNIT_ATTEMPT_REGISTRATION", kinds)
        self.assertIn("SPAWN_RESERVATION", kinds)
        registration = next(
            item["content"]
            for item in governed_state.all_receipts(self.project)
            if item["receipt_kind"] == "WORK_UNIT_ATTEMPT_REGISTRATION"
        )
        self.assert_schema_valid(registration, "bbk-work-unit-attempt-registration-v1.schema.json")
        self.assertEqual(registration["registration_id"], result["attempt_registration_ref"])

    def test_exact_retry_reuses_workspace_and_immutable_identities(self):
        first = self.compile()
        second = self.compile()
        self.assertTrue(second["idempotent_reuse"])
        for field in ("planned_binding_ref", "planned_session_id", "invocation_id", "dispatch_ref", "dispatch_input_digest", "task_input_digest"):
            self.assertEqual(first[field], second[field])
        self.assertEqual(first["workspace"]["workspace_path"], second["workspace"]["workspace_path"])
        registrations = [r for r in governed_state.all_receipts(self.project) if r["receipt_kind"] == "WORK_UNIT_ATTEMPT_REGISTRATION"]
        self.assertEqual(1, len(registrations))

    def test_fresh_idempotency_key_reuses_same_logical_attempt(self):
        first = self.compile()
        second = self.compile(idempotency_key="fresh-key-same-logical-attempt")
        self.assertTrue(second["idempotent_reuse"])
        self.assertEqual(first["logical_attempt_ref"], second["logical_attempt_ref"])
        self.assertEqual(first["planned_binding_ref"], second["planned_binding_ref"])
        self.assertEqual(first["dispatch_ref"], second["dispatch_ref"])
        registrations = [r for r in governed_state.all_receipts(self.project) if r["receipt_kind"] == "WORK_UNIT_ATTEMPT_REGISTRATION"]
        activations = [r for r in governed_state.all_receipts(self.project) if r["receipt_kind"] == "SPAWN_SESSION_ACTIVATION"]
        self.assertEqual(1, len(registrations))
        self.assertEqual(0, len(activations))

    def test_same_logical_attempt_changed_content_is_rejected_even_with_fresh_key(self):
        self.compile()
        with self.assertRaisesRegex(worker_spawn.WorkerSpawnError, "LOGICAL_ATTEMPT_CONFLICT"):
            self.compile(
                idempotency_key="fresh-key-different-content",
                assignment="Different assignment must require a new attempt identity.",
            )

    def test_host_normalization_ignores_presentation_i_but_not_task_identity(self):
        compiled = self.compile(idempotency_key="spawn-normalized-host-shape")
        with_i = {"i": "host display only", **compiled["dispatch_input"]}
        self.assertEqual(compiled["dispatch_envelope_digest"], registry.dispatch_envelope_digest(with_i))
        admitted = registry.admit_spawn_dispatch(
            self.project,
            dispatch_ref=compiled["dispatch_ref"],
            dispatch_envelope_digest=registry.dispatch_envelope_digest(with_i),
            parent_session_id="parent-session-1",
            task_name="worker-one",
            agent="bbk_worker",
            tool_call_id="normalized-host-task-call",
            host_version="omp/16.4.8",
            observed_at="2026-08-04T00:00:02Z",
        )
        self.assertEqual("ADMITTED", admitted["status"])
        tampered = json.loads(json.dumps(compiled["dispatch_input"]))
        tampered["tasks"][0]["name"] = "different-worker"
        with self.assertRaisesRegex(registry.OmpBindingError, "DISPATCH_MISMATCH"):
            registry.admit_spawn_dispatch(
                self.project,
                dispatch_ref=compiled["dispatch_ref"],
                dispatch_envelope_digest=registry.dispatch_envelope_digest(tampered),
                parent_session_id="parent-session-1",
                task_name="different-worker",
                agent="bbk_worker",
                tool_call_id="tampered-host-task-call",
                host_version="omp/16.4.8",
                observed_at="2026-08-04T00:00:03Z",
            )

    def test_failed_launch_releases_same_dispatch_for_retry_and_one_activation(self):
        compiled = self.compile(idempotency_key="spawn-lease-retry")
        first = registry.admit_spawn_dispatch(
            self.project,
            dispatch_ref=compiled["dispatch_ref"],
            dispatch_envelope_digest=compiled["dispatch_envelope_digest"],
            parent_session_id="parent-session-1",
            task_name="worker-one",
            agent="bbk_worker",
            tool_call_id="failed-native-call",
            host_version="omp/16.4.8",
            observed_at="2026-08-04T00:00:02Z",
        )
        self.assertEqual("LEASED", registry.dispatch_status(self.project, dispatch_ref=compiled["dispatch_ref"], observed_at="2026-08-04T00:00:03Z")["status"])
        released = registry.release_spawn_dispatch(
            self.project,
            dispatch_ref=compiled["dispatch_ref"],
            tool_call_id="failed-native-call",
            reason="HOST_TASK_LAUNCH_FAILED",
            observed_at="2026-08-04T00:00:04Z",
        )
        self.assertTrue(released["released"])
        self.assertEqual("READY", released["status"])
        second = registry.admit_spawn_dispatch(
            self.project,
            dispatch_ref=compiled["dispatch_ref"],
            dispatch_envelope_digest=compiled["dispatch_envelope_digest"],
            parent_session_id="parent-session-1",
            task_name="worker-one",
            agent="bbk_worker",
            tool_call_id="successful-native-call",
            host_version="omp/16.4.8",
            observed_at="2026-08-04T00:00:05Z",
        )
        activated = registry.activate_spawn_session(
            self.project,
            planned_binding_ref=compiled["planned_binding_ref"],
            actual_session_id="actual-retry-child",
            packet_digest=compiled["worker_packet"]["packet_digest"],
            host_version="omp/16.4.8",
            observed_at="2026-08-04T00:00:06Z",
        )
        self.assertEqual(second["lease_ref"], activated["lease_ref"])
        self.assertEqual("successful-native-call", activated["tool_call_id"])
        self.assertEqual("ACTIVATED", registry.dispatch_status(self.project, dispatch_ref=compiled["dispatch_ref"], observed_at="2026-08-04T00:00:07Z")["status"])
        with self.assertRaisesRegex(registry.OmpBindingError, "ALREADY_ACTIVATED"):
            registry.admit_spawn_dispatch(
                self.project,
                dispatch_ref=compiled["dispatch_ref"],
                dispatch_envelope_digest=compiled["dispatch_envelope_digest"],
                parent_session_id="parent-session-1",
                task_name="worker-one",
                agent="bbk_worker",
                tool_call_id="duplicate-after-activation",
                host_version="omp/16.4.8",
                observed_at="2026-08-04T00:00:08Z",
            )

    def test_activated_child_terminal_status_prevents_redispatch(self):
        compiled = self.compile(idempotency_key="spawn-terminal-lifecycle")
        registry.admit_spawn_dispatch(
            self.project,
            dispatch_ref=compiled["dispatch_ref"],
            dispatch_envelope_digest=compiled["dispatch_envelope_digest"],
            parent_session_id="parent-session-1",
            task_name="worker-one",
            agent="bbk_worker",
            tool_call_id="terminal-native-call",
            host_version="omp/16.4.8",
            observed_at="2026-08-04T00:00:02Z",
        )
        registry.activate_spawn_session(
            self.project,
            planned_binding_ref=compiled["planned_binding_ref"],
            actual_session_id="actual-terminal-child",
            packet_digest=compiled["worker_packet"]["packet_digest"],
            host_version="omp/16.4.8",
            observed_at="2026-08-04T00:00:03Z",
        )
        terminal = registry.mark_spawn_dispatch_terminal(
            self.project,
            dispatch_ref=compiled["dispatch_ref"],
            actual_session_id="actual-terminal-child",
            outcome="COMPLETED",
            reason="OMP_CHILD_AGENT_END_COMPLETED",
            observed_at="2026-08-04T00:00:04Z",
        )
        self.assert_schema_valid(terminal, "bbk-spawn-dispatch-terminal-v1.schema.json")
        state = registry.dispatch_status(
            self.project, dispatch_ref=compiled["dispatch_ref"], observed_at="2026-08-04T00:00:05Z"
        )
        self.assert_schema_valid(state, "bbk-dispatch-status-v1.schema.json")
        self.assertEqual("TERMINAL", state["status"])
        self.assertEqual("COMPLETED", state["terminal_outcome"])
        reused = registry.mark_spawn_dispatch_terminal(
            self.project,
            dispatch_ref=compiled["dispatch_ref"],
            actual_session_id="actual-terminal-child",
            outcome="COMPLETED",
            reason="OMP_CHILD_AGENT_END_COMPLETED",
            observed_at="2026-08-04T00:00:06Z",
        )
        self.assertTrue(reused["idempotent_reuse"])
        with self.assertRaisesRegex(registry.OmpBindingError, "DISPATCH_TERMINAL"):
            registry.admit_spawn_dispatch(
                self.project,
                dispatch_ref=compiled["dispatch_ref"],
                dispatch_envelope_digest=compiled["dispatch_envelope_digest"],
                parent_session_id="parent-session-1",
                task_name="worker-one",
                agent="bbk_worker",
                tool_call_id="redispatch-after-terminal",
                host_version="omp/16.4.8",
                observed_at="2026-08-04T00:00:07Z",
            )

    def test_retry_after_activation_reuses_one_logical_attempt_without_respawn(self):
        compiled = self.compile(idempotency_key="spawn-activated-reuse")
        registry.admit_spawn_dispatch(
            self.project,
            dispatch_ref=compiled["dispatch_ref"],
            dispatch_envelope_digest=compiled["dispatch_envelope_digest"],
            parent_session_id="parent-session-1",
            task_name="worker-one",
            agent="bbk_worker",
            tool_call_id="activation-call",
            host_version="omp/16.4.8",
            observed_at="2026-08-04T00:00:02Z",
        )
        registry.activate_spawn_session(
            self.project,
            planned_binding_ref=compiled["planned_binding_ref"],
            actual_session_id="actual-activated-child",
            packet_digest=compiled["worker_packet"]["packet_digest"],
            host_version="omp/16.4.8",
            observed_at="2026-08-04T00:00:03Z",
        )
        reused = self.compile(idempotency_key="fresh-key-after-activation")
        self.assertEqual("ACTIVATED", reused["status"])
        self.assertEqual("ACTIVATED", reused["dispatch_status"]["status"])
        self.assertEqual(compiled["planned_binding_ref"], reused["planned_binding_ref"])
        registrations = [r for r in governed_state.all_receipts(self.project) if r["receipt_kind"] == "WORK_UNIT_ATTEMPT_REGISTRATION"]
        activations = [r for r in governed_state.all_receipts(self.project) if r["receipt_kind"] == "SPAWN_SESSION_ACTIVATION"]
        self.assertEqual(1, len(registrations))
        self.assertEqual(1, len(activations))

    def test_concurrent_preparation_serializes_control_plane_then_returns_distinct_dispatches(self):
        requests = [
            self.request(
                task_name="worker-a", work_unit_id="WU-CONCURRENT-A", attempt_id="attempt-a-1",
                candidate_ref="candidate:concurrent-a", description="concurrent worker A",
                idempotency_key="spawn-concurrent-a", semantic_scope=["component:a"],
            ),
            self.request(
                task_name="worker-b", work_unit_id="WU-CONCURRENT-B", attempt_id="attempt-b-1",
                candidate_ref="candidate:concurrent-b", description="concurrent worker B",
                idempotency_key="spawn-concurrent-b", semantic_scope=["component:b"],
            ),
        ]
        def compile_request(request):
            return worker_spawn.compile_bound_spawn(
                self.project, request, jj_path=JJ, bd_path=BD, recorded_at="2026-08-04T00:00:01Z"
            )
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(compile_request, requests))
        self.assertEqual(["READY_TO_DISPATCH", "READY_TO_DISPATCH"], [item["status"] for item in results])
        self.assertEqual(2, len({item["dispatch_ref"] for item in results}))
        self.assertEqual(2, len({item["workspace"]["workspace_path"] for item in results}))
        self.assertTrue(all(item["assignment_projection"]["status"] == "PASS" for item in results))
        registrations = [r for r in governed_state.all_receipts(self.project) if r["receipt_kind"] == "WORK_UNIT_ATTEMPT_REGISTRATION"]
        self.assertEqual(2, len(registrations))

    def test_released_lease_can_retry_same_host_call_identity(self):
        compiled = self.compile(idempotency_key="spawn-same-call-retry")
        first = registry.admit_spawn_dispatch(
            self.project,
            dispatch_ref=compiled["dispatch_ref"],
            dispatch_envelope_digest=compiled["dispatch_envelope_digest"],
            parent_session_id="parent-session-1",
            task_name="worker-one",
            agent="bbk_worker",
            tool_call_id="reused-host-call",
            host_version="omp/16.4.8",
            observed_at="2026-08-04T00:00:02Z",
        )
        registry.release_spawn_dispatch(
            self.project, dispatch_ref=compiled["dispatch_ref"],
            tool_call_id="reused-host-call", reason="HOST_RETRY",
            observed_at="2026-08-04T00:00:03Z",
        )
        second = registry.admit_spawn_dispatch(
            self.project,
            dispatch_ref=compiled["dispatch_ref"],
            dispatch_envelope_digest=compiled["dispatch_envelope_digest"],
            parent_session_id="parent-session-1",
            task_name="worker-one",
            agent="bbk_worker",
            tool_call_id="reused-host-call",
            host_version="omp/16.4.8",
            observed_at="2026-08-04T00:00:04Z",
        )
        self.assertNotEqual(first["lease_ref"], second["lease_ref"])
        activated = registry.activate_spawn_session(
            self.project, planned_binding_ref=compiled["planned_binding_ref"],
            actual_session_id="actual-same-call-retry",
            packet_digest=compiled["worker_packet"]["packet_digest"],
            host_version="omp/16.4.8", observed_at="2026-08-04T00:00:05Z",
        )
        self.assertEqual(second["lease_ref"], activated["lease_ref"])

    def test_idempotency_collision_fails_closed(self):
        self.compile()
        with self.assertRaisesRegex(worker_spawn.WorkerSpawnError, "LOGICAL_ATTEMPT_CONFLICT"):
            self.compile(assignment="Different assignment under reused key")

    def test_incomplete_or_escaping_scope_fails_before_workspace_effect(self):
        bad = self.request()
        del bad["authority_ref"]
        with self.assertRaisesRegex(worker_spawn.WorkerSpawnError, "INCOMPLETE"):
            worker_spawn.compile_bound_spawn(self.project, bad, jj_path=JJ)
        self.assertFalse((self.base / "attempt-workspaces").exists())
        with self.assertRaisesRegex(worker_spawn.WorkerSpawnError, "SCOPE_INVALID"):
            self.compile(path_prefixes=["../escape"])

    def test_unknown_request_fields_and_noncanonical_roles_fail_before_capability_lookup(self):
        request = self.request()
        request["ambient_override"] = "forbidden"
        with self.assertRaisesRegex(worker_spawn.WorkerSpawnError, "SCHEMA_INVALID"):
            worker_spawn.compile_bound_spawn(self.project, request, jj_path=JJ)
        with self.assertRaisesRegex(worker_spawn.WorkerSpawnError, "ROLE_INVALID"):
            self.compile(role="bbk_worker/../../escape", idempotency_key="spawn-role-escape")

    def test_parent_binding_and_parent_capability_are_mandatory(self):
        with self.assertRaisesRegex(worker_spawn.WorkerSpawnError, "PARENT_BINDING_NOT_ACTIVE"):
            self.compile(parent_binding_ref="binding:not-real")
        with self.assertRaisesRegex(worker_spawn.WorkerSpawnError, "PARENT_CORRELATION_MISMATCH"):
            self.compile(parent_invocation_id="wrong-invocation")

        stale_parent, _ = registry.create_initial_binding(
            self.project,
            {
                **self.parent["request"],
                "session_id": "parent-session-stale-capability",
                "invocation_id": "parent-invocation-stale-capability",
                "idempotency_key": "control-binding-stale-capability",
            },
            capability_ref="role:bbk_root_orchestrator@stale-policy",
        )
        with self.assertRaisesRegex(worker_spawn.WorkerSpawnError, "CAPABILITY_BINDING_MISMATCH"):
            self.compile(
                parent_binding_ref=stale_parent["binding_id"],
                parent_session_id="parent-session-stale-capability",
                parent_invocation_id="parent-invocation-stale-capability",
                idempotency_key="spawn-stale-parent-capability",
            )

    def test_capability_digest_host_and_absolute_workspace_are_fail_closed(self):
        with self.assertRaisesRegex(worker_spawn.WorkerSpawnError, "HOST_UNQUALIFIED"):
            self.compile(host_version="omp/changed")
        with self.assertRaisesRegex(worker_spawn.WorkerSpawnError, "WORKSPACE_PARENT_INVALID"):
            self.compile(workspace_parent="relative-attempts")

        capability_root = self.base / "capabilities"
        shutil.copytree(ROOT / "spec" / "role-capabilities", capability_root)
        worker_path = capability_root / "bbk_worker.json"
        manifest = json.loads(worker_path.read_text(encoding="utf-8"))
        manifest["allowed_mutation_classes"] = ["PRODUCT_CONTENT"]
        worker_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(worker_spawn.WorkerSpawnError, "CAPABILITY_DIGEST_MISMATCH"):
            worker_spawn.compile_bound_spawn(
                self.project,
                self.request(idempotency_key="spawn-stale-child-capability"),
                jj_path=JJ,
                capability_root=capability_root,
            )

    def test_admitted_spawn_activates_actual_child_and_packet_alias_remains_valid(self):
        compiled = self.compile()
        payload_path = (
            self.project / ".bbk" / "governance" / "spawn-payloads"
            / f"{compiled['dispatch_ref'].removeprefix('dispatch:')}.json"
        )
        self.assertTrue(payload_path.is_file())
        registry.admit_spawn_dispatch(
            self.project,
            dispatch_ref=compiled["dispatch_ref"],
            dispatch_input_digest=compiled["dispatch_input_digest"],
            parent_session_id="parent-session-1",
            tool_call_id="task-call-1",
            host_version="omp/16.4.8",
            observed_at="2026-08-04T00:00:02Z",
        )
        activated = registry.activate_spawn_session(
            self.project,
            planned_binding_ref=compiled["planned_binding_ref"],
            actual_session_id="actual-child-session-1",
            packet_digest=compiled["worker_packet"]["packet_digest"],
            host_version="omp/16.4.8",
            observed_at="2026-08-04T00:00:03Z",
        )
        self.assertEqual("ACTIVATED", activated["status"])
        self.assertTrue(activated["dispatch_payload_removed"])
        self.assertFalse(payload_path.exists())
        self.assertEqual("actual-child-session-1", activated["binding"]["request"]["session_id"])
        self.assert_schema_valid(
            {key: value for key, value in activated.items() if key not in {"receipt_ref", "binding", "idempotent_reuse"}},
            "bbk-spawn-session-activation-v1.schema.json",
        )
        alias = registry.resolve_binding_reference(self.project, compiled["planned_binding_ref"])
        self.assertEqual(activated["active_binding_ref"], alias["binding_id"])
        retained = registry.retain_binding(
            self.project,
            event_type="WAKE",
            binding_ref=compiled["planned_binding_ref"],
            session_id="actual-child-session-1",
            invocation_id=compiled["invocation_id"],
            payload_digest="a" * 64,
            observed_at="2026-08-04T00:00:04Z",
        )
        self.assertEqual(activated["active_binding_ref"], retained["binding_ref"])
        retry = registry.activate_spawn_session(
            self.project,
            planned_binding_ref=compiled["planned_binding_ref"],
            actual_session_id="actual-child-session-1",
            packet_digest=compiled["worker_packet"]["packet_digest"],
            host_version="omp/16.4.8",
        )
        self.assertTrue(retry["idempotent_reuse"])


    def test_tampered_private_dispatch_payload_fails_before_task_admission(self):
        compiled = self.compile(idempotency_key="spawn-dispatch-tamper")
        payload_path = (
            self.project / ".bbk" / "governance" / "spawn-payloads"
            / f"{compiled['dispatch_ref'].removeprefix('dispatch:')}.json"
        )
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        payload["task_input"]["tasks"][0]["task"] = "tampered assignment"
        payload_path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(registry.OmpBindingError, "PAYLOAD_TAMPERED"):
            registry.admit_spawn_dispatch(
                self.project,
                dispatch_ref=compiled["dispatch_ref"],
                dispatch_input_digest=compiled["dispatch_input_digest"],
                parent_session_id="parent-session-1",
                tool_call_id="task-call-tampered",
                host_version="omp/16.4.8",
            )

    def test_activation_requires_exact_admission_and_packet_registration(self):
        compiled = self.compile()
        with self.assertRaisesRegex(registry.OmpBindingError, "ADMISSION_REQUIRED"):
            registry.activate_spawn_session(
                self.project,
                planned_binding_ref=compiled["planned_binding_ref"],
                actual_session_id="actual-child-session-1",
                packet_digest=compiled["worker_packet"]["packet_digest"],
                host_version="omp/16.4.8",
            )
        registry.admit_spawn_dispatch(
            self.project,
            dispatch_ref=compiled["dispatch_ref"],
            dispatch_input_digest=compiled["dispatch_input_digest"],
            parent_session_id="parent-session-1",
            tool_call_id="task-call-1",
            host_version="omp/16.4.8",
        )
        with self.assertRaisesRegex(registry.OmpBindingError, "PACKET_REGISTRATION_REQUIRED"):
            registry.activate_spawn_session(
                self.project,
                planned_binding_ref=compiled["planned_binding_ref"],
                actual_session_id="actual-child-session-1",
                packet_digest="f" * 64,
                host_version="omp/16.4.8",
            )

    def test_marker_parser_rejects_marker_not_on_first_line_or_malformed(self):
        self.assertIsNone(worker_spawn.parse_packet_marker("prefix\n<bbk-bound-worker-packet planned-binding-ref=\"x\" packet-digest=\"sha256:" + "a" * 64 + "\">"))
        self.assertIsNone(worker_spawn.parse_packet_marker("<bbk-bound-worker-packet bad>"))


if __name__ == "__main__":
    unittest.main()
