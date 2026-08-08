from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import gate_kernel  # noqa: E402
import omp_binding_registry as registry  # noqa: E402
import role_return_runtime as return_runtime  # noqa: E402
from substrate import jj_adapter  # noqa: E402
from tests._path_support import assert_same_path  # noqa: E402
from tests._fake_executable import write_python_executable  # noqa: E402

NODE = shutil.which("node")
JJ = os.environ.get("BBK_TEST_JJ") or shutil.which("jj")
EXTENSION = ROOT / "omp" / "extension" / "index.js"


def omp_projection_body(role: str) -> str:
    text = (ROOT / "projections" / "omp" / "agents" / f"{role}.md").read_text(encoding="utf-8")
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            text = parts[2]
    return text.strip()


def native_agent_system_block(role: str, context_expression: str) -> str:
    role_block = json.dumps(omp_projection_body(role))
    return (
        '"ROLE\\n===================================\\n" + '
        f"{role_block} + "
        '"\\n\\nCONTEXT\\n===================================\\n" + '
        f"{context_expression} + "
        '"\\n\\nPLAN\\n===================================\\n<plan path=\\"\\"></plan>" + '
        '"\\n\\nCOOP\\n===================================\\nNo peers." + '
        '"\\n\\nCOMPLETION\\n===================================\\nReturn through yield."'
    )


def run_node(source: str, *, environment: dict[str, str]) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as temporary:
        script = Path(temporary) / "test.mjs"
        script.write_text(source, encoding="utf-8")
        completed = subprocess.run(
            [NODE or "node", script],
            cwd=ROOT,
            env=environment,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
        )
        if completed.returncode != 0:
            raise AssertionError(completed.stderr or completed.stdout)
        return json.loads(completed.stdout)


def node_harness(invocation: str) -> str:
    return textwrap.dedent(
        f"""
        const chain = () => ({{ optional() {{ return this; }} }});
        const z = {{ object: value => value, string: chain, boolean: chain,
          enum: values => chain(), array: value => chain(), any: chain }};
        const tools = [], commands = new Map(), handlers = new Map(), bus = new Map();
        const pi = {{
          zod: {{ z }}, setLabel() {{}}, registerTool(value) {{ tools.push(value); }},
          registerCommand(name, value) {{ commands.set(name, value); }},
          on(name, value) {{ if (!handlers.has(name)) handlers.set(name, []); handlers.get(name).push(value); }},
          events: {{ on(name, value) {{ if (!bus.has(name)) bus.set(name, []); bus.get(name).push(value); return () => {{}}; }} }},
          appendEntry() {{}}, sendMessage() {{}}, async sendUserMessage() {{}},
        }};
        const mod = await import({json.dumps(EXTENSION.as_uri())});
        mod.default(pi);
        const hook = handlers.get("tool_call")?.[0];
        if (!hook) throw new Error("tool_call hook missing");
        const ctx = {{
          cwd: process.cwd(), sessionId: "parent-session-1", hasUI: false,
          sessionManager: {{ sessionId: "parent-session-1", getSessionId() {{ return "parent-session-1"; }}, getBranch() {{ return []; }} }},
          ui: {{ notify() {{}}, setStatus() {{}}, setWidget() {{}} }},
        }};
        {invocation}
        """
    )


@unittest.skipUnless(NODE, "Node.js is required for governed OMP hook behavior")
class OmpGovernedProfileTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.project = Path(self.temporary.name) / "project"
        self.project.mkdir()
        self.environment = os.environ.copy()
        self.environment.update(
            {
                "BBK_PROJECT_ROOT": str(self.project),
                "BBK_OMP_HOST_VERSION": "omp/16.4.8",
                "BBK_PYTHON": sys.executable,
            }
        )

    def tearDown(self):
        self.temporary.cleanup()

    def create_binding_and_reservation(self, task_input: dict[str, object]):
        workspace = self.project / "workers" / "worker-1"
        (workspace / "src").mkdir(parents=True)
        binding, _ = registry.create_initial_binding(
            self.project,
            {
                "schema": "bbk.invocation-binding-create.v1",
                "session_id": "child-session-1",
                "parent_session_id": "parent-session-1",
                "invocation_id": "invocation-1",
                "role": "bbk_worker",
                "work_unit_id": "WU-TEST",
                "attempt_id": "attempt-1",
                "baseline_ref": "git:abc",
                "candidate_ref": "candidate-1",
                "workspace_ref": str(workspace),
                "authority_ref": "authority:user",
                "scope": {
                    "path_prefixes": [str(workspace / "src")],
                    "mutation_classes": ["PRODUCT_CONTENT"],
                    "semantic_scope": ["component:test"],
                },
                "return_contract": "bbk.role-return.v2",
                "jj_change_id": "change-1",
                "idempotency_key": "binding-1",
            },
            capability_ref="role:bbk_worker@1.0.0-alpha.17",
        )
        digest = gate_kernel.canonical_digest(task_input, prefixed=True)
        registry.create_spawn_reservation(
            self.project,
            binding_ref=binding["binding_id"],
            parent_session_id="parent-session-1",
            task_name=str(task_input["name"]),
            agent=str(task_input["agent"]),
            input_digest=digest,
        )
        return binding

    def create_mutation_binding(self):
        if not JJ:
            self.skipTest("real jj executable not configured")
        workspace = self.project / "workers" / "mutation-worker"
        (workspace / "src").mkdir(parents=True)
        (workspace / "src" / "a.txt").write_text("before\n", encoding="utf-8")
        (workspace / "mise.toml").write_text(
            '[tasks."verify:candidate"]\nrun = "printf pass"\n',
            encoding="utf-8",
        )
        subprocess.run(["git", "init"], cwd=workspace, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["git", "config", "user.name", "BBK Test"], cwd=workspace, check=True)
        subprocess.run(["git", "config", "user.email", "bbk@example.invalid"], cwd=workspace, check=True)
        subprocess.run(["git", "config", "core.autocrlf", "false"], cwd=workspace, check=True)
        subprocess.run(["git", "config", "core.eol", "lf"], cwd=workspace, check=True)
        subprocess.run(["git", "add", "."], cwd=workspace, check=True)
        subprocess.run(["git", "commit", "-m", "baseline"], cwd=workspace, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run([str(JJ), "--no-pager", "--color=never", "git", "init", "--colocate", "."], cwd=workspace, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        identity = jj_adapter.identity(workspace, jj_path=JJ)
        binding, _ = registry.create_initial_binding(
            self.project,
            {
                "schema": "bbk.invocation-binding-create.v1",
                "session_id": "parent-session-1",
                "invocation_id": "invocation-1",
                "role": "bbk_worker",
                "work_unit_id": "WU-MUTATION",
                "attempt_id": "attempt-1",
                "baseline_ref": "git:baseline",
                "candidate_ref": "candidate-mutation-1",
                "workspace_ref": str(workspace.resolve()),
                "authority_ref": "authority:user",
                "scope": {
                    "path_prefixes": [str((workspace / "src").resolve())],
                    "mutation_classes": ["PRODUCT_CONTENT"],
                    "semantic_scope": ["component:test"],
                },
                "return_contract": "bbk.role-return.v2",
                "jj_change_id": identity["jj_change_id"],
                "idempotency_key": "binding-mutation-1",
            },
            capability_ref="role:bbk_worker@1.0.0-alpha.17",
        )
        return binding, workspace

    def create_return_binding(self):
        parent, _ = registry.create_initial_binding(
            self.project,
            {
                "schema": "bbk.invocation-binding-create.v1",
                "session_id": "root-session-1",
                "invocation_id": "root-invocation-1",
                "role": "bbk_root_orchestrator",
                "work_unit_id": "WU-ROOT",
                "attempt_id": "root-1",
                "baseline_ref": "git:baseline",
                "candidate_ref": "candidate:root",
                "workspace_ref": str(self.project.resolve()),
                "authority_ref": "authority:user",
                "scope": {
                    "path_prefixes": [str((self.project / ".bbk").resolve())],
                    "mutation_classes": ["COORDINATION_METADATA"],
                    "semantic_scope": ["campaign:alpha17"],
                },
                "return_contract": "bbk.root-orchestrator-return.v2",
                "jj_change_id": "root-change",
                "idempotency_key": "root-return-binding",
            },
            capability_ref="role:bbk_root_orchestrator@1.0.0-alpha.17",
        )
        workspace = self.project / "workers" / "return-worker"
        (workspace / "src").mkdir(parents=True)
        worker, _ = registry.create_initial_binding(
            self.project,
            {
                "schema": "bbk.invocation-binding-create.v1",
                "session_id": "parent-session-1",
                "parent_session_id": "root-session-1",
                "invocation_id": "worker-return-invocation-1",
                "role": "bbk_worker",
                "work_unit_id": "WU-RETURN",
                "attempt_id": "worker-return-1",
                "baseline_ref": "git:baseline",
                "candidate_ref": "candidate:return",
                "workspace_ref": str(workspace.resolve()),
                "authority_ref": "authority:user",
                "scope": {
                    "path_prefixes": [str((workspace / "src").resolve())],
                    "mutation_classes": ["PRODUCT_CONTENT"],
                    "semantic_scope": ["manual:alpha17", "worker:return"],
                },
                "return_contract": "bbk.worker-return.v2",
                "return_transport_mode": "STRUCTURED_RETURN_ONLY",
                "jj_change_id": "worker-return-change",
                "idempotency_key": "worker-return-binding",
            },
            capability_ref="role:bbk_worker@1.0.0-alpha.17",
        )
        return parent, worker

    @staticmethod
    def valid_worker_result():
        return {
            "work_unit_ref": {"id": "WU-RETURN"},
            "changed_artifacts": {"paths": ["src/result.txt"]},
            "checks_and_evidence": {"alpha17:verify": "PASS"},
            "claims_established_and_not_established": {
                "established": ["bounded implementation"],
                "not_established": ["release"],
            },
            "cleanup_and_residuals": {"cleanup": "complete", "residuals": []},
            "blockers": [],
        }

    def create_control_binding(self):
        coordination = self.project / ".bbk" / "coordination"
        coordination.mkdir(parents=True, exist_ok=True)
        binding, _ = registry.create_initial_binding(
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
                    "path_prefixes": [str(coordination.resolve())],
                    "mutation_classes": ["COORDINATION_METADATA"],
                    "semantic_scope": ["campaign:alpha17"],
                },
                "return_contract": "bbk.root-orchestrator-return.v2",
                "jj_change_id": "control-plane",
                "idempotency_key": "control-binding-1",
            },
            capability_ref="role:bbk_root_orchestrator@1.0.0-alpha.17",
        )
        return binding

    def test_bbk_mode_enforces_event_driven_waiting_and_five_minute_probe_floor(self):
        environment = dict(self.environment)
        environment.pop("BBK_GOVERNED_PROFILE", None)
        value = run_node(
            node_harness(
                """
                let now = 1000;
                Date.now = () => now;
                await commands.get("bbk").handler("", ctx);
                const taskDecision = await hook({toolName:"task", toolCallId:"task-1", input:{
                  context:"# Goal\\nrun\\n# Constraints\\nbounded\\n# Contract\\nreturn",
                  tasks:[{name:"WorkerOne", agent:"bbk_worker", task:"# Target\\na\\n# Change\\nb\\n# Acceptance\\nc"}]
                }}, ctx);
                for (const handler of (bus.get("task:subagent:lifecycle") || [])) {
                  handler({id:"WorkerOne", name:"WorkerOne", agent:"bbk_worker", status:"running"});
                }
                const earlyList = await hook({toolName:"job", toolCallId:"job-list-1", input:{list:true}}, ctx);
                const specificPoll = await hook({toolName:"job", toolCallId:"job-poll-1", input:{poll:["WorkerOne"]}}, ctx);
                const blockingWait = await hook({toolName:"job", toolCallId:"job-wait-1", input:{}}, ctx);
                const ircInbox = await hook({toolName:"irc", toolCallId:"irc-inbox-1", input:{op:"inbox"}}, ctx);
                const ircWait = await hook({toolName:"irc", toolCallId:"irc-wait-1", input:{op:"wait"}}, ctx);
                now += 300001;
                const lateList = await hook({toolName:"job", toolCallId:"job-list-2", input:{list:true}}, ctx);
                const repeatedList = await hook({toolName:"irc", toolCallId:"irc-list-2", input:{op:"list"}}, ctx);
                const runtime = globalThis[Symbol.for("bbk.omp.runtime.v1")];
                console.log(JSON.stringify({
                  taskAllowed: taskDecision === undefined,
                  earlyList, specificPoll,
                  blockingWaitAllowed: blockingWait === undefined,
                  ircInbox, ircWaitAllowed: ircWait === undefined,
                  lateListAllowed: lateList === undefined,
                  repeatedList,
                  status: runtime.coordinationStatus(ctx),
                }));
                """
            ),
            environment=environment,
        )
        self.assertTrue(value["taskAllowed"])
        self.assertEqual(value["earlyList"]["details"]["reason_code"], "BBK_COORDINATION_PROBE_TOO_EARLY")
        self.assertEqual(value["specificPoll"]["details"]["reason_code"], "BBK_COORDINATION_SPECIFIC_POLL_FORBIDDEN")
        self.assertTrue(value["blockingWaitAllowed"])
        self.assertEqual(value["ircInbox"]["details"]["reason_code"], "BBK_COORDINATION_PROBE_TOO_EARLY")
        self.assertTrue(value["ircWaitAllowed"])
        self.assertTrue(value["lateListAllowed"])
        self.assertEqual(value["repeatedList"]["details"]["reason_code"], "BBK_COORDINATION_PROBE_TOO_EARLY")
        self.assertEqual(value["status"]["minimum_probe_interval_ms"], 300000)
        self.assertEqual(value["status"]["active_count"], 1)


    def test_generic_dispatch_fallback_is_blocked_before_effect(self):
        environment = {**self.environment, "BBK_GOVERNED_PROFILE": "governed-software"}
        marker = '<bbk-spawn-dispatch ref="dispatch:' + ('a' * 64) + '"/>'
        value = run_node(
            node_harness(
                f"""
                const decision = await hook({{toolName:"eval", toolCallId:"eval-dispatch-1", input:{{
                  code:{json.dumps('await tool.task({context: ' + repr(marker) + ', tasks: []})')}
                }}}}, ctx);
                console.log(JSON.stringify(decision));
                """
            ),
            environment=environment,
        )
        self.assertTrue(value["block"])
        self.assertEqual("BBK_GENERIC_DISPATCH_FALLBACK_FORBIDDEN", value["details"]["reason_code"])

    def test_dispatch_status_tool_exposes_durable_lifecycle_without_mutation(self):
        fake = Path(self.temporary.name) / "fake-dispatch-status.py"
        fake.write_text(
            textwrap.dedent(
                """
                import json
                import sys

                dispatch_ref = sys.argv[sys.argv.index("--dispatch-ref") + 1]
                print(json.dumps({
                    "schema": "bbk.dispatch-status.v1",
                    "dispatch_ref": dispatch_ref,
                    "reservation_ref": "sha256:" + "a" * 64,
                    "binding_ref": "binding:test",
                    "parent_session_id": "parent-session-1",
                    "work_unit_id": "WU-TEST",
                    "attempt_id": "attempt-1",
                    "task_name": "Worker",
                    "agent": "bbk_worker",
                    "status": "READY",
                }))
                """
            ).lstrip(),
            encoding="utf-8",
        )
        environment = {
            **self.environment,
            "BBK_GOVERNED_PROFILE": "governed-software",
            "BBK_OMP_BINDING_REGISTRY_CLI": str(fake),
        }
        dispatch_ref = "dispatch:" + "b" * 64
        value = run_node(
            node_harness(
                f"""
                const statusTool = tools.find(item => item.name === "bbk_control_dispatch_status");
                const before = JSON.stringify([...handlers.keys()]);
                const result = await statusTool.execute("status-call-1", {{dispatchRef:{json.dumps(dispatch_ref)}}}, undefined, undefined, ctx);
                console.log(JSON.stringify({{details:result.details, before}}));
                """
            ),
            environment=environment,
        )
        self.assertEqual("READY", value["details"]["status"])
        self.assertEqual(dispatch_ref, value["details"]["dispatch_ref"])

    def test_default_profile_preserves_baseline_write_behavior(self):
        environment = dict(self.environment)
        environment.pop("BBK_GOVERNED_PROFILE", None)
        value = run_node(
            node_harness(
                """
                const result = await hook({toolName:"write", toolCallId:"write-1", input:{path:"ordinary.txt", content:"ok"}}, ctx);
                console.log(JSON.stringify({allowed: result === undefined}));
                """
            ),
            environment=environment,
        )
        self.assertTrue(value["allowed"])

    def test_governed_profile_blocks_builtin_write_edit_and_bash_before_effect(self):
        environment = {**self.environment, "BBK_GOVERNED_PROFILE": "governed-software"}
        value = run_node(
            node_harness(
                """
                const results = {};
                for (const toolName of ["write", "edit", "bash"]) {
                  results[toolName] = await hook({toolName, toolCallId:`${toolName}-1`, input:{path:"ordinary.txt", command:"echo unsafe"}}, ctx);
                }
                console.log(JSON.stringify(results));
                """
            ),
            environment=environment,
        )
        for tool_name in ("write", "edit", "bash"):
            self.assertTrue(value[tool_name]["block"])
            self.assertEqual("AMBIENT_MUTATION_TOOL_FORBIDDEN", value[tool_name]["details"]["reason_code"])
        receipts = list((self.project / ".bbk" / "governance" / "receipts" / "OMP_HOST_EVENT").glob("*.json"))
        self.assertEqual(3, len(receipts))
        self.assertTrue(
            all(
                json.loads(path.read_text(encoding="utf-8"))["content"]["enforcement_boundary"]
                == "ENFORCED"
                for path in receipts
            )
        )

    def test_orchestrator_control_tools_project_exact_host_identity_without_product_write_surface(self):
        binding = self.create_control_binding()
        fake = Path(self.temporary.name) / "fake-control-plane.py"
        fake.write_text(
            textwrap.dedent(
                """
                import hashlib
                import json
                import sys

                request = json.load(sys.stdin)
                operation = {
                    "bbk.control-assign.v1": "ASSIGN",
                    "bbk.control-update.v1": "UPDATE",
                    "bbk.control-integrate-request.v1": "INTEGRATE_REQUEST",
                }[request["schema"]]
                digest = "sha256:" + hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
                print(json.dumps({
                    "schema": "bbk.control-plane-result.v1",
                    "status": "PASS",
                    "operation": operation,
                    "actor": {"session_id": request["session_id"], "invocation_id": request["invocation_id"]},
                    "subject": {"work_unit": request["work_unit_id"], "attempt": request["attempt_id"]},
                    "coordination_command_digest": digest,
                    "projection": {"projection_id": digest},
                    "policy": {"product_mutation_authority": "DENIED", "raw_bd_authority": "DENIED"},
                    "smallest_next_action": "continue",
                    "echoed_request": request,
                }))
                """
            ),
            encoding="utf-8",
        )
        environment = {
            **self.environment,
            "BBK_GOVERNED_PROFILE": "governed-software",
            "BBK_CONTROL_PLANE_CLI": str(fake),
        }
        common = {
            "bindingRef": binding["binding_id"],
            "invocationId": "parent-invocation-1",
            "commandId": "command-1",
            "workUnitId": "WU-ONE",
            "attemptId": "attempt-1",
            "correlationId": "correlation-1",
            "payloadSummary": "Coordinate WU-ONE attempt-1",
            "expectedRevision": 0,
            "idempotencyKey": "idempotency-1",
            "evidenceRefs": [],
            "findingRefs": [],
        }
        value = run_node(
            node_harness(
                f"""
                const names = tools.map(item => item.name).filter(name => name.startsWith("bbk_control_")).sort();
                const assign = tools.find(item => item.name === "bbk_control_assign");
                const update = tools.find(item => item.name === "bbk_control_update");
                const integrate = tools.find(item => item.name === "bbk_control_integrate_request");
                const common = {json.dumps(common)};
                const assigned = await assign.execute("control-assign-1", {{...common,
                  workerBindingRef:"binding:worker", attemptRegistrationRef:"sha256:{'a' * 64}"}}, undefined, undefined, ctx);
                const updated = await update.execute("control-update-1", {{...common,
                  commandId:"command-2", idempotencyKey:"idempotency-2", transition:"START"}}, undefined, undefined, ctx);
                const {{expectedRevision: _omittedIntegrationRevision, ...integrationCommon}} = common;
                const integrated = await integrate.execute("control-integrate-1", {{...integrationCommon,
                  commandId:"command-3", workUnitId:"WU-INTEGRATE", attemptId:"attempt-int",
                  idempotencyKey:"idempotency-3", sourceCandidateRefs:["candidate:one"],
                  targetCandidateRef:"candidate:target", conflictClassification:"CONTENT_CHANGING"}}, undefined, undefined, ctx);
                console.log(JSON.stringify({{names, assigned, updated, integrated}}));
                """
            ),
            environment=environment,
        )
        self.assertTrue(
            {
                "bbk_control_assign",
                "bbk_control_update",
                "bbk_control_integrate_request",
                "bbk_control_spawn",
            }.issubset(set(value["names"]))
        )
        for key, schema in (
            ("assigned", "bbk.control-assign.v1"),
            ("updated", "bbk.control-update.v1"),
            ("integrated", "bbk.control-integrate-request.v1"),
        ):
            self.assertFalse(value[key]["isError"])
            request = value[key]["details"]["echoed_request"]
            self.assertEqual(schema, request["schema"])
            self.assertEqual("parent-session-1", request["session_id"])
            self.assertEqual("parent-invocation-1", request["invocation_id"])
            self.assertEqual(binding["binding_id"], request["binding_ref"])
            if key == "integrated":
                self.assertNotIn("expected_revision", request)
            else:
                self.assertEqual(0, request["expected_revision"])
            self.assertEqual("DENIED", value[key]["details"]["policy"]["product_mutation_authority"])
        receipts = list((self.project / ".bbk" / "governance" / "receipts" / "OMP_HOST_EVENT").glob("*.json"))
        self.assertEqual(3, len(receipts))

    def test_yield_hook_fails_closed_without_active_child_binding(self):
        environment = {**self.environment, "BBK_GOVERNED_PROFILE": "governed-software"}
        value = run_node(
            node_harness(
                """
                const decision = await hook({toolName:"yield", toolCallId:"yield-unbound-1", input:{result:{data:{schema:"bbk.role-return.v2"}}}}, ctx);
                console.log(JSON.stringify(decision));
                """
            ),
            environment=environment,
        )
        self.assertTrue(value["block"])
        self.assertTrue(value["details"]["reason_code"])
        self.assertIn("binding", value["details"]["message"].lower())

    def test_yield_hook_blocks_malformed_bound_role_return_before_effect(self):
        _parent, worker = self.create_return_binding()
        environment = {**self.environment, "BBK_GOVERNED_PROFILE": "governed-software"}
        malformed = {"schema": "bbk.role-return.v2", "contract": "bbk.worker-return.v2"}
        value = run_node(
            node_harness(
                f"""
                const decision = await hook({{toolName:"yield", toolCallId:"yield-invalid-1", input:{{result:{{data:{json.dumps(malformed)}}}}}}}, ctx);
                console.log(JSON.stringify(decision));
                """
            ),
            environment=environment,
        )
        self.assertTrue(value["block"])
        self.assertEqual("BBK_ROLE_RETURN_SCHEMA_INVALID", value["details"]["reason_code"])
        self.assertIn("first error", value["details"]["message"])
        self.assertEqual(worker["binding_id"], registry.binding_execution_policy(self.project, session_id="parent-session-1")["binding_ref"])

    def test_return_prepare_tool_and_complete_yield_is_admitted(self):
        _parent, worker = self.create_return_binding()
        environment = {**self.environment, "BBK_GOVERNED_PROFILE": "governed-software"}
        result_literal = json.dumps(self.valid_worker_result(), separators=(",", ":"))
        value = run_node(
            node_harness(
                f"""
                const templateTool = tools.find(value => value.name === "bbk_return_template");
                const prepareTool = tools.find(value => value.name === "bbk_return_prepare");
                if (!templateTool || !prepareTool) throw new Error("role-return tools missing");
                const template = await templateTool.execute("return-template-1", {{
                  bindingRef:{json.dumps(worker['binding_id'])}, invocationId:"worker-return-invocation-1"
                }}, undefined, undefined, ctx);
                const prepared = await prepareTool.execute("return-prepare-1", {{
                  bindingRef:{json.dumps(worker['binding_id'])}, invocationId:"worker-return-invocation-1",
                  returnKind:"WORK_UNIT_RESULT", detailLevel:"COMPACT", operationalDisposition:"COMPLETE",
                  semanticStateValue:"READY_FOR_PARENT_INTEGRATION", summary:"bounded worker complete",
                  result:{result_literal}, nextAction:"Integrate candidate",
                  nextActionOwner:"bbk_root_orchestrator", nextActionReason:"schema-valid worker completion",
                  nextActionAffectedRefs:["candidate:return"], unaffectedWorkMayContinue:true,
                  effectsUsed:[{{effect_class:"PRODUCT_CONTENT", path:"src/result.txt"}}],
                  checksAndEvidence:[{{id:"alpha17:verify", status:"PASS"}}],
                  prohibitedClaims:["release"], idempotencyKey:"return-prepare-1"
                }}, undefined, undefined, ctx);
                const decision = await hook({{toolName:"yield", toolCallId:"yield-complete-1", input:prepared.details.yield_input}}, ctx);
                console.log(JSON.stringify({{template, prepared, allowed: decision === undefined}}));
                """
            ),
            environment=environment,
        )
        self.assertFalse(value["template"]["isError"])
        self.assertEqual("CANDIDATE_PRODUCTION", value["template"]["details"]["invocation_mode"])
        self.assertFalse(value["prepared"]["isError"])
        self.assertTrue(value["allowed"])
        document = value["prepared"]["details"]["yield_input"]["result"]["data"]
        self.assertEqual("bbk.role-return.v2", document["schema"])
        self.assertEqual("bbk.worker-return.v2", document["contract"])
        self.assertEqual("bbk_root_orchestrator", document["parent_ref"]["role"])
        return_runtime.validate_role_return(document, "bbk_worker", ROOT)

    def test_yield_hook_allows_exact_prepared_complete_return(self):
        _parent, worker = self.create_return_binding()
        prepared = return_runtime.prepare(
            self.project,
            ROOT,
            {
                "schema": return_runtime.PREPARE_SCHEMA,
                "session_id": "parent-session-1",
                "binding_ref": worker["binding_id"],
                "invocation_id": "worker-return-invocation-1",
                "return_kind": "WORK_UNIT_RESULT",
                "operational_disposition": "COMPLETE",
                "semantic_state_value": "READY_FOR_PARENT_INTEGRATION",
                "summary": "bounded worker complete",
                "result": self.valid_worker_result(),
                "smallest_valid_next_action": {
                    "action": "Integrate candidate", "owner": "bbk_root_orchestrator",
                    "reason": "schema-valid completion",
                },
                "effects_used": [], "denied_or_uncovered_effects": [], "violations_or_ambiguities": [],
                "idempotency_key": "direct-valid-1",
            },
        )
        record_path = self.project / ".bbk" / "governance" / "role-returns" / f"{prepared['return_ref'].split(':', 1)[1]}.json"
        document = json.loads(record_path.read_text(encoding="utf-8"))["document"]
        environment = {**self.environment, "BBK_GOVERNED_PROFILE": "governed-software"}
        value = run_node(
            node_harness(
                f"""
                const decision = await hook({{toolName:"yield", toolCallId:"yield-direct-1", input:{{result:{{data:{json.dumps(document)}}}}}}}, ctx);
                console.log(JSON.stringify({{allowed: decision === undefined}}));
                """
            ),
            environment=environment,
        )
        self.assertTrue(value["allowed"])

    def test_yield_hook_blocks_schema_valid_but_unprepared_return(self):
        _parent, worker = self.create_return_binding()
        prepared = return_runtime.prepare(
            self.project,
            ROOT,
            {
                "schema": return_runtime.PREPARE_SCHEMA,
                "session_id": "parent-session-1",
                "binding_ref": worker["binding_id"],
                "invocation_id": "worker-return-invocation-1",
                "return_kind": "WORK_UNIT_RESULT",
                "operational_disposition": "COMPLETE",
                "semantic_state_value": "READY_FOR_PARENT_INTEGRATION",
                "summary": "bounded worker complete",
                "result": self.valid_worker_result(),
                "smallest_valid_next_action": {
                    "action": "Integrate candidate", "owner": "bbk_root_orchestrator",
                    "reason": "schema-valid completion",
                },
                "effects_used": [], "denied_or_uncovered_effects": [], "violations_or_ambiguities": [],
                "idempotency_key": "direct-unprepared-1",
            },
        )
        document = prepared["yield_input"]["result"]["data"]
        record_path = self.project / ".bbk" / "governance" / "role-returns" / f"{prepared['return_ref'].split(':', 1)[1]}.json"
        record_path.unlink()
        environment = {**self.environment, "BBK_GOVERNED_PROFILE": "governed-software"}
        value = run_node(
            node_harness(
                f"""
                const decision = await hook({{toolName:"yield", toolCallId:"yield-unprepared-1", input:{{result:{{data:{json.dumps(document)}}}}}}}, ctx);
                console.log(JSON.stringify(decision));
                """
            ),
            environment=environment,
        )
        self.assertTrue(value["block"])
        self.assertEqual("ROLE_RETURN_PREPARATION_REQUIRED", value["details"]["reason_code"])

    def test_structured_return_only_binding_blocks_handoff_before_effect(self):
        workspace = self.project / "workers" / "structured-return-worker"
        (workspace / "src").mkdir(parents=True)
        binding, _ = registry.create_initial_binding(
            self.project,
            {
                "schema": "bbk.invocation-binding-create.v1",
                "session_id": "parent-session-1",
                "invocation_id": "invocation-structured-1",
                "role": "bbk_worker",
                "work_unit_id": "WU-STRUCTURED",
                "attempt_id": "attempt-structured-1",
                "baseline_ref": "git:abc",
                "candidate_ref": "candidate:structured",
                "workspace_ref": str(workspace.resolve()),
                "authority_ref": "authority:user",
                "scope": {
                    "path_prefixes": [str((workspace / "src").resolve())],
                    "mutation_classes": ["PRODUCT_CONTENT"],
                    "semantic_scope": ["component:structured"],
                },
                "return_contract": "bbk.worker-return.v2",
                "return_transport_mode": "STRUCTURED_RETURN_ONLY",
                "material_transport_reason": "",
                "jj_change_id": "change-structured-1",
                "idempotency_key": "binding-structured-1",
            },
            capability_ref="role:bbk_worker@1.0.0-alpha.17",
        )
        environment = {**self.environment, "BBK_GOVERNED_PROFILE": "governed-software"}
        value = run_node(
            node_harness(
                f"""
                const result = await hook({{toolName:"bbk_handoff_create", toolCallId:"handoff-1", input:{{
                  root:{json.dumps(str(self.project))}, workUnit:"WU-STRUCTURED", disposition:"COMPLETED",
                  summary:"unnecessary", nextAction:"return"
                }}}}, ctx);
                console.log(JSON.stringify(result));
                """
            ),
            environment=environment,
        )
        self.assertTrue(value["block"])
        self.assertEqual("BBK_STRUCTURED_RETURN_ONLY", value["details"]["reason_code"])
        self.assertEqual(binding["binding_id"], registry.binding_execution_policy(self.project, session_id="parent-session-1")["binding_ref"])
        self.assertFalse((self.project / ".bbk" / "handoffs").exists())

    def test_governed_profile_blocks_unbound_task_spawn(self):
        environment = {**self.environment, "BBK_GOVERNED_PROFILE": "governed-software"}
        task_input = {"name": "worker-one", "agent": "bbk_worker", "task": "bounded work"}
        value = run_node(
            node_harness(
                f"""
                const result = await hook({{toolName:"task", toolCallId:"task-1", input:{json.dumps(task_input)}}}, ctx);
                console.log(JSON.stringify(result));
                """
            ),
            environment=environment,
        )
        self.assertTrue(value["block"])
        self.assertEqual("OMP_SPAWN_BINDING_REQUIRED", value["details"]["reason_code"])

    def test_exact_reserved_task_is_admitted_once(self):
        environment = {**self.environment, "BBK_GOVERNED_PROFILE": "governed-software"}
        task_input = {"agent": "bbk_worker", "name": "worker-one", "task": "bounded work"}
        binding = self.create_binding_and_reservation(task_input)
        value = run_node(
            node_harness(
                f"""
                const result = await hook({{toolName:"task", toolCallId:"task-1", input:{json.dumps(task_input)}}}, ctx);
                console.log(JSON.stringify({{allowed: result === undefined}}));
                """
            ),
            environment=environment,
        )
        self.assertTrue(value["allowed"])
        admissions = list((self.project / ".bbk" / "governance" / "receipts" / "SPAWN_ADMISSION").glob("*.json"))
        self.assertEqual(1, len(admissions))
        content = json.loads(admissions[0].read_text(encoding="utf-8"))["content"]
        self.assertEqual(binding["binding_id"], content["binding_ref"])
        self.assertEqual("ENFORCED", content["enforcement_boundary"])

        second = run_node(
            node_harness(
                f"""
                const result = await hook({{toolName:"task", toolCallId:"task-2", input:{json.dumps(task_input)}}}, ctx);
                console.log(JSON.stringify(result));
                """
            ),
            environment=environment,
        )
        self.assertTrue(second["block"])
        self.assertEqual("OMP_SPAWN_RESERVATION_ALREADY_CONSUMED", second["details"]["reason_code"])

    def test_unqualified_host_cannot_consume_reserved_spawn(self):
        environment = {
            **self.environment,
            "BBK_GOVERNED_PROFILE": "governed-software",
            "BBK_OMP_HOST_VERSION": "omp/99.0.0",
        }
        task_input = {"agent": "bbk_worker", "name": "worker-one", "task": "bounded work"}
        self.create_binding_and_reservation(task_input)
        value = run_node(
            node_harness(
                f"""
                const result = await hook({{toolName:"task", toolCallId:"task-1", input:{json.dumps(task_input)}}}, ctx);
                console.log(JSON.stringify(result));
                """
            ),
            environment=environment,
        )
        self.assertTrue(value["block"])
        self.assertEqual("OMP_HOST_UNQUALIFIED_FOR_SPAWN", value["details"]["reason_code"])
        admissions = self.project / ".bbk" / "governance" / "receipts" / "SPAWN_ADMISSION"
        self.assertFalse(admissions.exists())

    def test_governed_profile_rejects_cwd_as_session_or_project_authority(self):
        environment = dict(self.environment)
        environment["BBK_GOVERNED_PROFILE"] = "governed-software"
        environment.pop("BBK_PROJECT_ROOT")
        source = node_harness(
            """
            delete ctx.sessionId;
            ctx.sessionManager = { getBranch() { return []; } };
            const result = await hook({toolName:"task", toolCallId:"task-1", input:{name:"x",agent:"bbk_worker",task:"x"}}, ctx);
            console.log(JSON.stringify(result));
            """
        )
        value = run_node(source, environment=environment)
        self.assertTrue(value["block"])
        self.assertEqual("GOVERNED_PROJECT_ROOT_REQUIRED", value["details"]["reason_code"])

    def test_governed_filesystem_tools_are_registered_and_write_through_exact_binding(self):
        binding, workspace = self.create_mutation_binding()
        environment = {
            **self.environment,
            "BBK_GOVERNED_PROFILE": "governed-software",
            "BBK_JJ": str(JJ),
        }
        value = run_node(
            node_harness(
                f"""
                const names = tools.map(tool => tool.name).filter(name => name.startsWith("bbk_governed_")).sort();
                const tool = tools.find(item => item.name === "bbk_governed_write");
                const output = await tool.execute("governed-write-1", {{
                  bindingRef: {json.dumps(binding['binding_id'])}, invocationId: "invocation-1",
                  path: "src/a.txt", mutationClass: "PRODUCT_CONTENT", idempotencyKey: "omp-write-1",
                  preconditionKind: "PRESENT", content: "after\\n", encoding: "utf-8"
                }}, undefined, undefined, ctx);
                console.log(JSON.stringify({{names, output}}));
                """
            ),
            environment=environment,
        )
        self.assertEqual(
            ["bbk_governed_delete", "bbk_governed_edit", "bbk_governed_read", "bbk_governed_write"],
            value["names"],
        )
        self.assertFalse(value["output"]["isError"])
        self.assertEqual("PASS", value["output"]["details"]["status"])
        self.assertEqual("APPLIED", value["output"]["details"]["result"]["effect_status"])
        self.assertEqual("after\n", (workspace / "src" / "a.txt").read_text(encoding="utf-8"))
        host_receipts = list((self.project / ".bbk" / "governance" / "receipts" / "OMP_HOST_EVENT").glob("*.json"))
        self.assertEqual(1, len(host_receipts))
        self.assertEqual(
            binding["binding_id"],
            json.loads(host_receipts[0].read_text(encoding="utf-8"))["content"]["correlation"]["binding_ref"],
        )

    def test_control_spawn_compiles_exact_task_and_child_start_activates_actual_session(self):
        if not JJ:
            self.skipTest("real jj executable not configured")
        (self.project / ".bbk" / "coordination").mkdir(parents=True)
        (self.project / "README.md").write_text("baseline\n", encoding="utf-8")
        subprocess.run(["git", "init", "-b", "main"], cwd=self.project, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["git", "config", "user.name", "BBK Test"], cwd=self.project, check=True)
        subprocess.run(["git", "config", "user.email", "bbk@example.invalid"], cwd=self.project, check=True)
        subprocess.run(["git", "config", "core.autocrlf", "false"], cwd=self, check=True)
        subprocess.run(["git", "config", "core.eol", "lf"], cwd=self, check=True)
        subprocess.run(["git", "add", "."], cwd=self.project, check=True)
        subprocess.run(["git", "commit", "-m", "baseline"], cwd=self.project, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run([str(JJ), "--no-pager", "--color=never", "git", "init", "--colocate", "."], cwd=self.project, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        parent, _ = registry.create_initial_binding(
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
        )
        environment = {
            **self.environment,
            "BBK_GOVERNED_PROFILE": "governed-software",
            "BBK_JJ": str(JJ),
        }
        params = {
            "parentBindingRef": parent["binding_id"],
            "parentInvocationId": "parent-invocation-1",
            "taskName": "worker-one",
            "role": "bbk_worker",
            "workUnitId": "WU-ONE",
            "attemptId": "attempt-1",
            "baselineRef": "git:main",
            "candidateRef": "candidate:one",
            "authorityRef": "authority:user",
            "returnContract": "bbk.worker-return.v2",
            "parentRevision": "@-",
            "workspaceParent": str(self.project.parent / "attempts"),
            "pathPrefixes": ["src"],
            "mutationClasses": ["PRODUCT_CONTENT"],
            "semanticScope": ["component:one"],
            "assignment": "Implement component one.",
            "description": "WU-ONE attempt-1",
            "idempotencyKey": "spawn-one-attempt-1",
        }
        value = run_node(
            node_harness(
                f"""
                const spawnTool = tools.find(item => item.name === "bbk_control_spawn");
                if (!spawnTool) throw new Error("bbk_control_spawn missing");
                const spawned = await spawnTool.execute("spawn-control-1", {json.dumps(params)}, undefined, undefined, ctx);
                const compact = JSON.parse(JSON.stringify(spawned.details.dispatch_input));
                // OMP 16.4.8 removes this presentation-only label before the
                // extension's pre-effect hook. Exercise that exact host shape.
                delete compact.i;
                const hostShapeHadI = Object.prototype.hasOwnProperty.call(compact, "i");
                const admission = await hook({{toolName:"task", toolCallId:"task-call-1", input:compact}}, ctx);
                const resolved = admission?.input || compact;
                const before = handlers.get("before_agent_start")?.[0];
                const childCtx = {{...ctx, sessionId:"actual-child-session-1", sessionManager:{{...ctx.sessionManager, sessionId:"actual-child-session-1", getSessionId(){{return "actual-child-session-1";}}}}}};
                const systemBlock = {native_agent_system_block('bbk_worker', 'resolved.context')};
                const activation = await before({{prompt:resolved.tasks[0].task, systemPrompt:[systemBlock]}}, childCtx);
                console.log(JSON.stringify({{spawned, admitted: Boolean(admission?.input), hostShapeHadI, resolved, activation: activation ?? null}}));
                """
            ),
            environment=environment,
        )
        self.assertFalse(value["spawned"]["isError"])
        self.assertTrue(value["admitted"])
        self.assertFalse(value["hostShapeHadI"])
        details = value["spawned"]["details"]
        active = registry.resolve_binding_reference(self.project, details["planned_binding_ref"])
        self.assertEqual("actual-child-session-1", active["request"]["session_id"])
        activation_receipts = list((self.project / ".bbk" / "governance" / "receipts" / "SPAWN_SESSION_ACTIVATION").glob("*.json"))
        self.assertEqual(1, len(activation_receipts))

    def test_generic_dispatch_fallback_is_blocked_before_effect(self):
        environment = {**self.environment, "BBK_GOVERNED_PROFILE": "governed-software"}
        dispatch_ref = "dispatch:" + ("a" * 64)
        fallback_code = f'await tool.task({{"context":"<bbk-spawn-dispatch ref=\"{dispatch_ref}\"/>","tasks":[]}})'
        value = run_node(
            node_harness(
                f"""
                const decision = await hook({{
                  toolName:"eval", toolCallId:"eval-dispatch-fallback",
                  input:{{code:{json.dumps(fallback_code)}}}
                }}, ctx);
                console.log(JSON.stringify(decision));
                """
            ),
            environment=environment,
        )
        self.assertTrue(value["block"])
        self.assertEqual("BBK_GENERIC_DISPATCH_FALLBACK_FORBIDDEN", value["details"]["reason_code"])

    def test_advertised_governance_status_surface_is_registered_and_read_only(self):
        binding = self.create_control_binding()
        before = {
            path.relative_to(self.project).as_posix(): path.read_bytes()
            for path in sorted((self.project / ".bbk").rglob("*"))
            if path.is_file()
        }
        environment = {**self.environment, "BBK_GOVERNED_PROFILE": "governed-software"}
        value = run_node(
            node_harness(
                f"""
                const names = tools.map(item => item.name).filter(name =>
                  ["bbk_governance_status", "bbk_control_bind", "bbk_control_dispatch_status", "bbk_task_run"].includes(name)).sort();
                const statusTool = tools.find(item => item.name === "bbk_governance_status");
                const output = await statusTool.execute("status-1", {{
                  bindingRef: {json.dumps(binding['binding_id'])}, invocationId: "parent-invocation-1"
                }}, undefined, undefined, ctx);
                console.log(JSON.stringify({{names, output}}));
                """
            ),
            environment=environment,
        )
        after = {
            path.relative_to(self.project).as_posix(): path.read_bytes()
            for path in sorted((self.project / ".bbk").rglob("*"))
            if path.is_file()
        }
        self.assertEqual(["bbk_control_bind", "bbk_control_dispatch_status", "bbk_governance_status", "bbk_task_run"], value["names"])
        self.assertFalse(value["output"]["isError"])
        self.assertEqual("PASS", value["output"]["details"]["status"])
        self.assertEqual(binding["binding_id"], value["output"]["details"]["binding"]["binding_ref"])
        self.assertEqual(before, after)

    def test_control_bind_activates_read_only_child_and_blocks_product_write(self):
        if not JJ:
            self.skipTest("real jj executable not configured")
        parent = self.create_control_binding()
        candidate = self.project.parent / "integrated-candidate"
        (candidate / "src").mkdir(parents=True)
        (candidate / "src" / "a.txt").write_bytes(b"candidate\n")
        subprocess.run(["git", "init", "-b", "main"], cwd=candidate, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["git", "config", "user.name", "BBK Test"], cwd=candidate, check=True)
        subprocess.run(["git", "config", "user.email", "bbk@example.invalid"], cwd=candidate, check=True)
        subprocess.run(["git", "config", "core.autocrlf", "false"], cwd=candidate, check=True)
        subprocess.run(["git", "config", "core.eol", "lf"], cwd=candidate, check=True)
        subprocess.run(["git", "add", "."], cwd=candidate, check=True)
        subprocess.run(["git", "commit", "-m", "candidate"], cwd=candidate, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run([str(JJ), "--no-pager", "--color=never", "git", "init", "--colocate", "."], cwd=candidate, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        environment = {
            **self.environment,
            "BBK_GOVERNED_PROFILE": "governed-software",
            "BBK_JJ": str(JJ),
        }
        params = {
            "parentBindingRef": parent["binding_id"],
            "parentInvocationId": "parent-invocation-1",
            "taskName": "review-integrated",
            "role": "bbk_reviewer",
            "workUnitId": "WU-REVIEW",
            "attemptId": "attempt-review-1",
            "baselineRef": "git:main",
            "candidateId": "candidate:review-subject",
            "authorityRef": "authority:user",
            "returnContract": "bbk.reviewer-return.v2",
            "workspaceRef": str(candidate.resolve()),
            "pathPrefixes": ["."],
            "semanticScope": ["candidate:review-subject"],
            "assignment": "Review the exact candidate without mutation.",
            "description": "read-only review",
            "idempotencyKey": "bind-review-1",
        }
        value = run_node(
            node_harness(
                f"""
                const bindTool = tools.find(item => item.name === "bbk_control_bind");
                const bound = await bindTool.execute("bind-control-1", {json.dumps(params)}, undefined, undefined, ctx);
                const compact = JSON.parse(JSON.stringify(bound.details.dispatch_input));
                const admission = await hook({{toolName:"task", toolCallId:"task-review-1", input:compact}}, ctx);
                const resolved = admission?.input || compact;
                const before = handlers.get("before_agent_start")?.[0];
                const childCtx = {{...ctx, sessionId:"actual-review-session-1", sessionManager:{{...ctx.sessionManager,
                  sessionId:"actual-review-session-1", getSessionId(){{return "actual-review-session-1";}}}}}};
                const systemBlock = {native_agent_system_block('bbk_reviewer', 'resolved.context')};
                await before({{prompt:resolved.tasks[0].task, systemPrompt:[systemBlock]}}, childCtx);
                const readTool = tools.find(item => item.name === "bbk_governed_read");
                const writeTool = tools.find(item => item.name === "bbk_governed_write");
                const statusTool = tools.find(item => item.name === "bbk_governance_status");
                const read = await readTool.execute("review-read-1", {{
                  bindingRef:bound.details.planned_binding_ref, invocationId:bound.details.invocation_id,
                  path:"src/a.txt", mutationClass:"READ_ONLY", idempotencyKey:"review-read-1", preconditionKind:"PRESENT"
                }}, undefined, undefined, childCtx);
                const write = await writeTool.execute("review-write-1", {{
                  bindingRef:bound.details.planned_binding_ref, invocationId:bound.details.invocation_id,
                  path:"src/a.txt", mutationClass:"PRODUCT_CONTENT", idempotencyKey:"review-write-1",
                  preconditionKind:"PRESENT", content:"forbidden\\n", encoding:"utf-8"
                }}, undefined, undefined, childCtx);
                const status = await statusTool.execute("review-status-1", {{
                  bindingRef:bound.details.planned_binding_ref, invocationId:bound.details.invocation_id
                }}, undefined, undefined, childCtx);
                console.log(JSON.stringify({{bound, admitted:Boolean(admission?.input), read, write, status}}));
                """
            ),
            environment=environment,
        )
        self.assertFalse(value["bound"]["isError"])
        self.assertTrue(value["admitted"])
        self.assertFalse(value["read"]["isError"])
        self.assertEqual("candidate\n", value["read"]["details"]["content"])
        self.assertTrue(value["write"]["isError"])
        self.assertEqual("ROLE_CAPABILITY_FORBIDDEN", value["write"]["details"]["reason_code"])
        self.assertFalse(value["status"]["isError"])
        self.assertEqual("bbk_reviewer", value["status"]["details"]["binding"]["role"])
        self.assertEqual("candidate\n", (candidate / "src" / "a.txt").read_text(encoding="utf-8"))
        self.assertFalse((candidate / ".bbk").exists())

    def test_control_bind_rejects_integrated_candidate_without_admission_receipt(self):
        if not JJ:
            self.skipTest("real jj executable not configured")
        parent = self.create_control_binding()
        candidate = self.project.parent / "partial-integrated-candidate"
        (candidate / "src").mkdir(parents=True)
        (candidate / "src" / "a.txt").write_bytes(b"candidate\n")
        subprocess.run(["git", "init", "-b", "main"], cwd=candidate, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["git", "config", "user.name", "BBK Test"], cwd=candidate, check=True)
        subprocess.run(["git", "config", "user.email", "bbk@example.invalid"], cwd=candidate, check=True)
        subprocess.run(["git", "config", "core.autocrlf", "false"], cwd=candidate, check=True)
        subprocess.run(["git", "config", "core.eol", "lf"], cwd=candidate, check=True)
        subprocess.run(["git", "add", "."], cwd=candidate, check=True)
        subprocess.run(["git", "commit", "-m", "candidate"], cwd=candidate, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run([str(JJ), "--no-pager", "--color=never", "git", "init", "--colocate", "."], cwd=candidate, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        environment = {**self.environment, "BBK_GOVERNED_PROFILE": "governed-software", "BBK_JJ": str(JJ)}
        params = {
            "parentBindingRef": parent["binding_id"], "parentInvocationId": "parent-invocation-1",
            "taskName": "review-integrated", "role": "bbk_reviewer", "workUnitId": "WU-REVIEW",
            "attemptId": "attempt-review-integrated-1", "baselineRef": "git:main",
            "candidateId": "candidate:alpha17-manual:integrated", "authorityRef": "authority:user",
            "returnContract": "bbk.reviewer-return.v2", "workspaceRef": str(candidate.resolve()),
            "pathPrefixes": ["."], "semanticScope": ["candidate:integrated"],
            "assignment": "Review integrated candidate.", "description": "must fail closed",
            "idempotencyKey": "bind-integrated-missing-admission",
        }
        value = run_node(
            node_harness(
                f"""
                const bindTool = tools.find(item => item.name === "bbk_control_bind");
                const bound = await bindTool.execute("bind-no-admission", {json.dumps(params)}, undefined, undefined, ctx);
                console.log(JSON.stringify(bound));
                """
            ),
            environment=environment,
        )
        self.assertTrue(value["isError"])
        self.assertEqual("CONTROL_BIND_CANDIDATE_ADMISSION_REQUIRED", value["details"]["reason_code"])

    def test_task_run_executes_declared_candidate_preserving_mise_task(self):
        if not JJ:
            self.skipTest("real jj executable not configured")
        binding, workspace = self.create_mutation_binding()
        fake = write_python_executable(
            Path(self.temporary.name) / "mise",
            "import sys\n"
            "args = sys.argv[1:]\n"
            "if args == ['--version']:\n"
            "    print('mise OMP-TEST-1.0')\n"
            "    raise SystemExit(0)\n"
            "if args[:2] == ['run', 'verify:candidate']:\n"
            "    print('pass')\n"
            "    raise SystemExit(0)\n"
            "raise SystemExit(9)\n",
        )
        before = {path.relative_to(workspace).as_posix(): path.read_bytes() for path in workspace.rglob("*") if path.is_file() and ".jj" not in path.parts and ".git" not in path.parts}
        environment = {
            **self.environment,
            "BBK_GOVERNED_PROFILE": "governed-software",
            "BBK_JJ": str(JJ),
            "BBK_MISE": str(fake),
        }
        value = run_node(
            node_harness(
                f"""
                const taskTool = tools.find(item => item.name === "bbk_task_run");
                const output = await taskTool.execute("qualified-task-1", {{
                  bindingRef:{json.dumps(binding['binding_id'])}, invocationId:"invocation-1",
                  task:"verify:candidate", arguments:[], environmentAllowlist:[], idempotencyKey:"omp-qualified-1"
                }}, undefined, undefined, ctx);
                console.log(JSON.stringify(output));
                """
            ),
            environment=environment,
        )
        after = {path.relative_to(workspace).as_posix(): path.read_bytes() for path in workspace.rglob("*") if path.is_file() and ".jj" not in path.parts and ".git" not in path.parts}
        self.assertFalse(value["isError"])
        self.assertEqual("PASS", value["details"]["status"])
        self.assertTrue(value["details"]["candidate_unchanged"])
        assert_same_path(self, fake, value["details"]["mise_path"])
        self.assertEqual(before, after)
        kinds = {path.parent.name for path in (self.project / ".bbk" / "governance" / "receipts").rglob("*.json")}
        self.assertIn("QUALIFIED_TASK", kinds)
        self.assertIn("BOUND_QUALIFIED_TASK", kinds)

    def test_bound_child_start_without_matching_admission_is_aborted(self):
        if not JJ:
            self.skipTest("real jj executable not configured")
        # Python-level compilation is covered exhaustively in test_worker_spawn;
        # here the host hook must refuse a marker that has no admitted task call.
        environment = {**self.environment, "BBK_GOVERNED_PROFILE": "governed-software"}
        marker = '<bbk-bound-worker-packet planned-binding-ref="binding:not-real" packet-digest="sha256:' + ('a' * 64) + '">\nassignment'
        value = run_node(
            node_harness(
                f"""
                const before = handlers.get("before_agent_start")?.[0];
                let error = null;
                try {{
                  const childCtx = {{...ctx, sessionId:"actual-child-session-1", sessionManager:{{...ctx.sessionManager, getSessionId(){{return "actual-child-session-1";}}}}}};
                  const systemBlock = {native_agent_system_block('bbk_worker', json.dumps(marker))};
                  await before({{prompt:"assignment", systemPrompt:[systemBlock]}}, childCtx);
                }} catch (caught) {{ error = {{code:caught.code || null, message:String(caught.message || caught)}}; }}
                console.log(JSON.stringify({{error}}));
                """
            ),
            environment=environment,
        )
        self.assertIsNotNone(value["error"])
        self.assertIn("OMP_SPAWN", value["error"]["code"])

    def test_governed_filesystem_tool_is_blocked_outside_explicit_profile(self):
        binding, workspace = self.create_mutation_binding()
        environment = {**self.environment, "BBK_JJ": str(JJ)}
        environment.pop("BBK_GOVERNED_PROFILE", None)
        value = run_node(
            node_harness(
                f"""
                const tool = tools.find(item => item.name === "bbk_governed_write");
                const output = await tool.execute("governed-write-1", {{
                  bindingRef: {json.dumps(binding['binding_id'])}, invocationId: "invocation-1",
                  path: "src/a.txt", mutationClass: "PRODUCT_CONTENT", idempotencyKey: "omp-write-1",
                  content: "forbidden\\n"
                }}, undefined, undefined, ctx);
                console.log(JSON.stringify(output));
                """
            ),
            environment=environment,
        )
        self.assertTrue(value["isError"])
        self.assertEqual("GOVERNED_PROFILE_REQUIRED", value["details"]["reason_code"])
        self.assertEqual("before\n", (workspace / "src" / "a.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
