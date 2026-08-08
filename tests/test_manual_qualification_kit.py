from __future__ import annotations

import base64
import hashlib
import json
import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "tools" / "qualification" / "manual-kit-template"
ANALYZER = TEMPLATE / "analyze-session.py"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def session_html(payload: dict) -> str:
    encoded = base64.b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")).decode("ascii")
    return f'<!doctype html><script id="session-data" type="application/json">{encoded}</script>'


class Alpha17ManualQualificationKitTests(unittest.TestCase):
    def test_launcher_emits_exact_manual_command_and_never_starts_omp(self):
        text = (TEMPLATE / "start-alpha17-qualification.ps1").read_text(encoding="utf-8")
        for expected in (
            "omp-qualification-overlay.yml",
            "--config",
            "--no-skills",
            "--no-rules",
            "BBK_EXPECTED_PACKAGE_VERSION",
            "launch-alpha17-qualification-command.ps1",
            "No OMP process was started",
            "Copy the command block below",
            "$record.rc_version",
        ):
            self.assertIn(expected, text)
        for forbidden in (
            "Invoke-ForegroundInteractive",
            "System.Diagnostics.Process",
            "Start-Process",
            "$process.WaitForExit()",
            "& $omp @arguments",
        ):
            self.assertNotIn(forbidden, text)
        self.assertNotIn("'--no-extensions'", text)
        self.assertLess(text.index("'--extension', $extension"), text.index("'--extension', $helper"))
        self.assertIn("$lines.Add('& ' +", text)
        overlay = (TEMPLATE / "omp-qualification-overlay.yml").read_text(encoding="utf-8")
        self.assertIn("extensions: []", overlay)

    def test_installer_resolves_mise_when_current_powershell_path_is_stale(self):
        text = (TEMPLATE / "install-isolated-rc.ps1").read_text(encoding="utf-8")
        for expected in (
            "function Resolve-MiseTool",
            "$MisePath = Resolve-MiseTool $Mise",
            "$env:MISE_EXE",
            "$env:MISE_PATH",
            "Microsoft\\WinGet\\Links\\mise.exe",
            "Microsoft\\WinGet\\Packages",
            "Get-ChildItem -LiteralPath $wingetPackages",
            "mise\\shims\\mise.exe",
            ".local\\bin\\mise.exe",
            "scoop\\shims\\mise.exe",
            '-Mise "C:\\path\\to\\mise.exe"',
        ):
            self.assertIn(expected, text)
        self.assertNotIn("$MisePath = Resolve-Tool $Mise", text)

    def test_role_return_validator_runtime_is_bound_end_to_end(self):
        installer = (TEMPLATE / "install-isolated-rc.ps1").read_text(encoding="utf-8")
        launcher = (TEMPLATE / "start-alpha17-qualification.ps1").read_text(encoding="utf-8")
        collector = (TEMPLATE / "collect-evidence.ps1").read_text(encoding="utf-8")
        for expected in (
            "function Get-JsonSchemaRuntime",
            "function Resolve-RoleReturnPython",
            "jsonschema==4.25.1",
            "SchemaWheelhouse",
            'tools["role_return_python"]',
            "role-return-python.json",
        ):
            self.assertIn(expected, installer)
        self.assertIn('$roleReturnPython = Require-File ([string]$record.tools.role_return_python.path)', launcher)
        self.assertIn('BBK_PYTHON = $roleReturnPython', launcher)
        self.assertIn('BBK_OPERATOR_PYTHON = $python', launcher)
        self.assertIn('$roleReturnPython = [string]$record.tools.role_return_python.path', collector)
        self.assertIn('$analysisCaptured = @(& $roleReturnPython @analysisArguments 2>&1)', collector)
        self.assertIn('role-return-jsonschema-version', collector)

    def test_collector_treats_native_stderr_as_evidence_and_preserves_nonpass(self):
        text = (TEMPLATE / "collect-evidence.ps1").read_text(encoding="utf-8")
        for expected in (
            'PSNativeCommandUseErrorActionPreference',
            "$ErrorActionPreference = 'Continue'",
            "[System.Management.Automation.ErrorRecord]",
            "session-admission.json",
            "Evidence was preserved",
            "analyze-session.py",
            "--full-gate",
            "RESULT-RECORD.json",
        ):
            self.assertIn(expected, text)
        capture = text[text.index("function Capture"):text.index('Capture "git-status"')]
        self.assertIn("$code = $LASTEXITCODE", capture)
        self.assertNotIn("throw", capture)

    def test_redaction_and_rollback_paths_are_release_tokenized(self):
        redact = (TEMPLATE / "redact-and-package.ps1").read_text(encoding="utf-8")
        rollback = (TEMPLATE / "rollback-isolated-rc.ps1").read_text(encoding="utf-8")
        for text in (redact, rollback):
            self.assertIn("bbk-alpha17-@BBK_RC_SLUG@-manual", text)
            self.assertNotRegex(text, r"alpha17-rc(?:3|4|5|6|7|8)(?![0-9])")
        self.assertIn("bbk-alpha17-@BBK_RC_SLUG@-redacted-evidence.zip", redact)
        self.assertIn("bbk-alpha17-@BBK_RC_SLUG@-manual", rollback)

    def test_redactor_requires_a_real_secret_token_boundary(self):
        spec = importlib.util.spec_from_file_location(
            "bbk_manual_redactor",
            TEMPLATE / "redact-evidence.py",
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        redactor = module.Redactor()
        source = (
            "WORK_UNIT_ATTEMPT_REGISTRATION\n"
            "bbk.work-unit-attempt-registration.v1\n"
            "credential=rk_abcdefghijklmnop1234567890\n"
        )
        redacted = redactor.text(source)
        self.assertIn("WORK_UNIT_ATTEMPT_REGISTRATION", redacted)
        self.assertIn("bbk.work-unit-attempt-registration.v1", redacted)
        self.assertNotIn("rk_abcdefghijklmnop1234567890", redacted)
        self.assertIn("[REDACTED_SECRET]", redacted)
        self.assertFalse(module.scan_secret(redacted))

    def test_installer_uses_a_temporary_python_source_file_for_runtime_probe(self):
        text = (TEMPLATE / "install-isolated-rc.ps1").read_text(encoding="utf-8")
        section = text[text.index("function Get-JsonSchemaRuntime"):text.index("function Test-ExactJsonSchemaRuntime")]
        for expected in (
            "$probeScript",
            "$probeResult",
            "[System.IO.File]::WriteAllText",
            '@("-I","-X","utf8",$probeScript,$probeResult)',
            "Remove-Item -LiteralPath $probeScript,$probeResult",
        ):
            self.assertIn(expected, section)
        self.assertNotIn('@("-I","-X","utf8","-c"', section)

    def test_collector_uses_a_temporary_python_source_file_for_jsonschema_probe(self):
        text = (TEMPLATE / "collect-evidence.ps1").read_text(encoding="utf-8")
        section = text[text.index('$jsonschemaProbe ='):text.index('Capture "package-status"')]
        self.assertIn("bbk-jsonschema-version-", section)
        self.assertIn("Set-Content -LiteralPath $jsonschemaProbe", section)
        self.assertIn("@('-I','-X','utf8',$jsonschemaProbe)", section)
        self.assertIn("Remove-Item -LiteralPath $jsonschemaProbe", section)
        self.assertNotIn("'-c'", section)

    def test_redactor_preserves_python_identifiers_but_redacts_real_response_ids(self):
        spec = importlib.util.spec_from_file_location(
            "bbk_manual_redactor_response_ids",
            TEMPLATE / "redact-evidence.py",
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        redactor = module.Redactor()
        source = (
            "call_succeeded\n"
            "call_reason_code\n"
            "response_status\n"
            "tool_call=call_00_WETnLZ3kZTd9yv5509sB2205\n"
        )
        redacted = redactor.text(source)
        self.assertIn("call_succeeded", redacted)
        self.assertIn("call_reason_code", redacted)
        self.assertIn("response_status", redacted)
        self.assertNotIn("call_00_WETnLZ3kZTd9yv5509sB2205", redacted)
        self.assertIn("[RESPONSE:", redacted)

    @unittest.skipUnless(shutil.which("node"), "Node.js is required for OMP JavaScript syntax validation")
    def test_manual_helper_requires_exact_extension_runtime_and_prompt_receipts(self):
        text = (TEMPLATE / "manual-bootstrap-extension.mjs").read_text(encoding="utf-8")
        for expected in (
            'Symbol.for("bbk.omp.runtime.v1")',
            'runtime.enterMode(ctx)',
            'runtime.ensureMode(ctx)',
            'runtime.isModeEnabled()',
            'BBK_OMP_EXTENSION_NOT_ACTIVE',
            'BBK_PROVIDER_PROMPT_RECEIPT_NOT_CURRENT',
            'skill_fallback_permitted: false',
            'bbk_manual_qualification_status',
        ):
            self.assertIn(expected, text)
        completed = subprocess.run(
            ["node", "--check", str(TEMPLATE / "manual-bootstrap-extension.mjs")],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_bootstrap_is_create_once_and_child_sessions_preserve_root_identity(self):
        spec = importlib.util.spec_from_file_location(
            "bbk_manual_bootstrap",
            TEMPLATE / "bootstrap-binding.py",
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as raw:
            temp = Path(raw)
            project = temp / "project"
            package = temp / "package"
            project.mkdir()
            package.mkdir()
            (package / "VERSION").write_text(VERSION + "\n", encoding="utf-8")
            core = {
                "schema": "bbk.alpha17-manual-bootstrap.v1",
                "status": "PASS",
                "host_version": "omp/16.4.8",
                "project_root": str(project.resolve()),
                "package_root": str(package.resolve()),
                "package_version": VERSION,
                "root_binding_ref": "sha256:" + "1" * 64,
                "root_invocation_id": "manual-root:" + "2" * 64,
                "root_session_id": "root-session",
                "root_parent_session_id": None,
            }
            encoded = json.dumps(core, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            existing = {
                **core,
                "bootstrap_digest": "sha256:" + hashlib.sha256(encoded).hexdigest(),
                "bootstrap_receipt_ref": "sha256:" + "3" * 64,
            }
            root = module.existing_result(
                existing,
                project=project.resolve(),
                package=package.resolve(),
                session_id="root-session",
                parent_session_id="",
                host_version="omp/16.4.8",
            )
            self.assertTrue(root["bootstrap_reused"])
            self.assertTrue(root["is_root_session"])
            child = module.existing_result(
                existing,
                project=project.resolve(),
                package=package.resolve(),
                session_id="child-session",
                parent_session_id="root-session",
                host_version="omp/16.4.8",
            )
            self.assertEqual("ROOT_PRESERVED", child["status"])
            self.assertFalse(child["is_root_session"])
            self.assertEqual("root-session", child["root_session_id"])
            self.assertEqual(existing, child["root_bootstrap"])
            tampered = {**existing, "root_invocation_id": "manual-root:tampered"}
            with self.assertRaisesRegex(RuntimeError, "bootstrap_integrity"):
                module.existing_result(
                    tampered,
                    project=project.resolve(),
                    package=package.resolve(),
                    session_id="child-session",
                    parent_session_id="root-session",
                    host_version="omp/16.4.8",
                )

    def run_analyzer(self, payload: dict, expected_version: str) -> tuple[int, dict]:
        with tempfile.TemporaryDirectory() as raw:
            temp = Path(raw)
            source = temp / "session.html"
            output = temp / "result.json"
            source.write_text(session_html(payload), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ANALYZER),
                    "--session-html", str(source),
                    "--expected-version", expected_version,
                    "--output", str(output),
                ],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            return completed.returncode, json.loads(output.read_text(encoding="utf-8"))

    def test_session_analyzer_accepts_only_extension_owned_mode(self):
        expected = VERSION
        payload = {
            "header": {"id": "session-pass", "timestamp": "2026-08-05T00:00:00Z", "cwd": "C:\\fixture"},
            "entries": [
                {"type": "custom", "customType": "bbk-mode-state", "data": {"package_version": expected, "enabled": True}},
                {"type": "custom", "customType": "bbk-effective-prompt-receipt", "data": {"package_version": expected, "phase": "before_agent_start", "prompt_kind": "controller", "status": "REPLACED"}},
                {"type": "custom", "customType": "bbk-effective-prompt-receipt", "data": {"package_version": expected, "phase": "provider_request_finalization", "prompt_kind": "controller", "action": "VERIFIED"}},
                {"type": "custom", "customType": "tool_execution_start", "timestamp": "2026-08-05T00:00:01Z", "data": {"toolName": "bbk_manual_qualification_status", "args": {}}},
                {"type": "custom", "customType": "tool_execution_start", "timestamp": "2026-08-05T00:00:02Z", "data": {"toolName": "bbk_governance_status", "args": {}}},
            ],
        }
        code, value = self.run_analyzer(payload, expected)
        self.assertEqual(code, 0)
        self.assertEqual(value["status"], "PASS")
        self.assertEqual(value["reason_codes"], [])
        self.assertEqual(value["mode"]["active_expected_version_count"], 1)
        self.assertEqual(value["mode"]["skill_prompt_count"], 0)

    def test_session_analyzer_rejects_skill_and_polling_fallback(self):
        payload = {
            "header": {"id": "session-fallback", "timestamp": "2026-08-05T00:00:00Z", "cwd": "C:\\fixture"},
            "entries": [
                {"type": "custom_message", "customType": "skill-prompt", "timestamp": "2026-08-05T00:00:00Z"},
                {"type": "custom", "customType": "tool_execution_start", "timestamp": "2026-08-05T00:00:01Z", "data": {"toolName": "eval", "args": {}}},
                {"type": "custom", "customType": "tool_execution_start", "timestamp": "2026-08-05T00:00:02Z", "data": {"toolName": "job", "args": {"poll": ["Worker"]}}},
            ],
        }
        code, value = self.run_analyzer(payload, VERSION)
        self.assertEqual(code, 2)
        self.assertEqual(value["status"], "INCONCLUSIVE")
        for expected in (
            "BBK_MODE_STATE_MISSING",
            "CONTROLLER_PROMPT_RECEIPT_MISSING",
            "PROVIDER_PROMPT_RECEIPT_MISSING",
            "SKILL_FALLBACK_OBSERVED",
            "MANUAL_HARNESS_STATUS_NOT_CALLED",
            "GENERIC_EVAL_FALLBACK_OBSERVED",
            "SPECIFIC_JOB_POLL_UNENFORCED_OR_UNOBSERVED",
        ):
            self.assertIn(expected, value["reason_codes"])


    def test_session_analyzer_treats_pre_effect_denied_specific_poll_as_enforcement_success(self):
        expected = VERSION
        call_id = "call-denied-poll"
        payload = {
            "header": {"id": "session-denied-poll", "timestamp": "2026-08-05T00:00:00Z", "cwd": "C:\\fixture"},
            "entries": [
                {"type": "custom", "customType": "bbk-mode-state", "data": {"package_version": expected, "enabled": True}},
                {"type": "custom", "customType": "bbk-effective-prompt-receipt", "data": {"package_version": expected, "phase": "before_agent_start", "prompt_kind": "controller", "status": "REPLACED"}},
                {"type": "custom", "customType": "bbk-effective-prompt-receipt", "data": {"package_version": expected, "phase": "provider_request_finalization", "prompt_kind": "controller", "action": "VERIFIED"}},
                {"type": "custom", "customType": "tool_execution_start", "timestamp": "2026-08-05T00:00:01Z", "data": {"toolCallId": "status-call", "toolName": "bbk_manual_qualification_status", "args": {}}},
                {"type": "message", "id": "poll-turn", "timestamp": "2026-08-05T00:00:02Z", "message": {"role": "assistant", "content": [
                    {"type": "toolCall", "id": call_id, "name": "job", "arguments": {"poll": ["WorkerA"]}},
                ]}},
                {"type": "message", "id": "poll-result", "timestamp": "2026-08-05T00:00:02.001Z", "message": {
                    "role": "toolResult", "toolCallId": call_id, "toolName": "job", "isError": True,
                    "content": [{"type": "text", "text": "BBK_COORDINATION_SPECIFIC_POLL_FORBIDDEN: denied before effect"}],
                    "details": {"reason_code": "BBK_COORDINATION_SPECIFIC_POLL_FORBIDDEN"},
                }},
            ],
        }
        code, value = self.run_analyzer(payload, expected)
        self.assertEqual(0, code)
        self.assertEqual("PASS", value["status"])
        self.assertEqual([], value["reason_codes"])
        self.assertEqual(1, value["coordination"]["specific_job_poll_attempt_count"])
        self.assertEqual(1, value["coordination"]["specific_job_poll_denied_before_effect_count"])
        self.assertEqual(0, value["coordination"]["specific_job_poll_unenforced_or_unobserved_count"])
        self.assertEqual(0, value["coordination"]["nonblocking_probe_count"])
        self.assertIn(
            "SPECIFIC_JOB_POLL_ATTEMPT_BLOCKED_BEFORE_EFFECT",
            value["coordination"]["efficiency_findings"],
        )

    def test_session_analyzer_deduplicates_host_and_assistant_projections_by_tool_call_id(self):
        expected = VERSION
        call_id = "call-shared-1"
        payload = {
            "header": {"id": "session-dedup", "timestamp": "2026-08-05T00:00:00Z", "cwd": "C:\\fixture"},
            "entries": [
                {"type": "custom", "customType": "bbk-mode-state", "data": {"package_version": expected, "enabled": True}},
                {"type": "custom", "customType": "bbk-effective-prompt-receipt", "data": {"package_version": expected, "phase": "before_agent_start", "prompt_kind": "controller", "status": "REPLACED"}},
                {"type": "custom", "customType": "bbk-effective-prompt-receipt", "data": {"package_version": expected, "phase": "provider_request_finalization", "prompt_kind": "controller", "action": "VERIFIED"}},
                {"type": "custom", "customType": "tool_execution_start", "id": "custom-entry", "timestamp": "2026-08-05T00:00:01Z", "data": {"toolCallId": call_id, "toolName": "bbk_manual_qualification_status", "args": {}}},
                {"type": "message", "id": "assistant-entry", "timestamp": "2026-08-05T00:00:01.001Z", "message": {"role": "assistant", "content": [{"type": "toolCall", "id": call_id, "name": "bbk_manual_qualification_status", "arguments": {}}]}},
            ],
        }
        code, value = self.run_analyzer(payload, expected)
        self.assertEqual(code, 0)
        self.assertEqual(1, value["tools"]["total_calls"])
        self.assertEqual(1, value["tools"]["physical_tool_call_ids"])
        self.assertEqual(1, value["tools"]["multi_projection_call_count"])
        self.assertIsNone(value["coordination"]["minimum_observed_probe_interval_seconds"])

    def test_session_analyzer_prefers_complete_assistant_arguments_over_filtered_host_projection(self):
        module = self.analyzer_module()
        call_id = "call-arguments-1234"
        payload = {
            "header": {"id": "root-session"},
            "entries": [
                {
                    "type": "custom",
                    "customType": "tool_execution_start",
                    "id": "host-entry",
                    "timestamp": "2026-08-05T00:00:01Z",
                    "data": {
                        "toolCallId": call_id,
                        "toolName": "bbk_governed_read",
                        "args": {"path": "src/worker-a/result.txt"},
                    },
                },
                {
                    "type": "message",
                    "id": "assistant-entry",
                    "timestamp": "2026-08-05T00:00:01.001Z",
                    "message": {
                        "role": "assistant",
                        "content": [{
                            "type": "toolCall",
                            "id": call_id,
                            "name": "bbk_governed_read",
                            "arguments": {
                                "bindingRef": "binding:reviewer",
                                "path": "src/worker-a/result.txt",
                            },
                        }],
                    },
                },
            ],
        }
        calls = module.tool_calls(module.flatten_session_entries(payload))
        self.assertEqual(1, len(calls))
        self.assertEqual("binding:reviewer", calls[0]["arguments"]["bindingRef"])
        self.assertEqual(
            ["assistant_message", "tool_execution_start"],
            calls[0]["sources"],
        )

    def test_session_analyzer_groups_parallel_status_probes_into_one_wake_burst(self):
        expected = VERSION
        first_turn = "assistant-turn-1"
        second_turn = "assistant-turn-2"
        payload = {
            "header": {"id": "session-bursts", "timestamp": "2026-08-05T00:00:00Z", "cwd": "C:\\fixture"},
            "entries": [
                {"type": "custom", "customType": "bbk-mode-state", "data": {"package_version": expected, "enabled": True}},
                {"type": "custom", "customType": "bbk-effective-prompt-receipt", "data": {"package_version": expected, "phase": "before_agent_start", "prompt_kind": "controller", "status": "REPLACED"}},
                {"type": "custom", "customType": "bbk-effective-prompt-receipt", "data": {"package_version": expected, "phase": "provider_request_finalization", "prompt_kind": "controller", "action": "VERIFIED"}},
                {"type": "message", "id": first_turn, "timestamp": "2026-08-05T00:00:01Z", "message": {"role": "assistant", "content": [
                    {"type": "toolCall", "id": "call-status", "name": "bbk_manual_qualification_status", "arguments": {}},
                    {"type": "toolCall", "id": "call-irc", "name": "irc", "arguments": {"op": "list"}},
                    {"type": "toolCall", "id": "call-job", "name": "job", "arguments": {"list": True}},
                ]}},
                {"type": "message", "id": second_turn, "timestamp": "2026-08-05T00:05:01Z", "message": {"role": "assistant", "content": [
                    {"type": "toolCall", "id": "call-irc-2", "name": "irc", "arguments": {"op": "inbox"}},
                ]}},
            ],
        }
        code, value = self.run_analyzer(payload, expected)
        self.assertEqual(code, 0)
        self.assertEqual(3, value["coordination"]["nonblocking_probe_count"])
        self.assertEqual(2, value["coordination"]["nonblocking_probe_burst_count"])
        self.assertEqual([300.0], value["coordination"]["nonblocking_probe_intervals_seconds"])
        self.assertEqual(300.0, value["coordination"]["minimum_observed_probe_interval_seconds"])


    def analyzer_module(self):
        spec = importlib.util.spec_from_file_location("bbk_manual_analyzer", ANALYZER)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_full_analyzer_flattens_nested_child_sessions(self):
        module = self.analyzer_module()
        payload = {
            "header": {"id": "root-session"},
            "entries": [{"id": "root-entry", "type": "message"}],
            "subSessions": {
                "Alpha17WorkerA": {
                    "header": {"id": "worker-session"},
                    "agentId": "Alpha17WorkerA",
                    "entries": [{"id": "worker-entry", "type": "message"}],
                }
            },
        }
        entries = module.flatten_session_entries(payload)
        self.assertEqual(["root-entry", "worker-entry"], [item["id"] for item in entries])
        self.assertEqual("worker-session", entries[1]["_bbk_session_id"])
        self.assertEqual("root-session", entries[1]["_bbk_parent_session_id"])
        self.assertEqual("Alpha17WorkerA", entries[1]["_bbk_session_name"])

    def test_full_analyzer_rejects_unvalidated_freehand_child_returns(self):
        module = self.analyzer_module()
        calls = [
            {
                "name": "yield",
                "tool_call_id": f"yield-{index}",
                "session_name": session,
                "agent_id": session,
                "arguments": {"result": {"data": {"schema": "bbk.role-return.v2", "contract": contract}}},
            }
            for index, (session, contract) in enumerate((
                ("Alpha17WorkerA", "bbk.worker-return.v2"),
                ("Alpha17WorkerB", "bbk.worker-return.v2"),
                ("Alpha17Reviewer", "bbk.reviewer-return.v2"),
                ("Alpha17Validator", "bbk.validator-return.v2"),
            ), start=1)
        ]
        result = module.analyze_role_returns([], calls, VERSION, TEMPLATE)
        self.assertEqual("FAIL", result["status"])
        self.assertIn("UNVALIDATED_ROLE_RETURN_ACCEPTED", result["reason_codes"])
        self.assertIn("VALIDATED_RETURN_BUILDER_NOT_USED_FOR_ALL_CHILDREN", result["reason_codes"])
        self.assertEqual(0, result["prepared_return_success_count"])

    def test_full_analyzer_counts_rejected_then_corrected_prepare_as_same_attempt_repair(self):
        module = self.analyzer_module()
        calls = [
            {
                "name": "bbk_return_prepare",
                "tool_call_id": "prepare-failed",
                "timestamp": "2026-08-05T00:00:00Z",
                "session_name": "Alpha17WorkerA",
                "arguments": {"bindingRef": "binding:a"},
                "result": {"is_error": True, "details": {"status": "FAIL"}},
            },
            {
                "name": "bbk_return_prepare",
                "tool_call_id": "prepare-passed",
                "timestamp": "2026-08-05T00:00:01Z",
                "session_name": "Alpha17WorkerA",
                "arguments": {"bindingRef": "binding:a"},
                "result": {"is_error": False, "details": {"status": "PASS"}},
            },
        ]
        result = module.analyze_role_returns([], calls, VERSION, TEMPLATE)
        self.assertEqual(1, result["same_attempt_prepare_repair_count"])
        self.assertEqual(1, result["same_attempt_schema_repair_count"])

    def test_full_analyzer_detects_worker_reread_and_ad_hoc_hash(self):
        module = self.analyzer_module()
        success = {"is_error": False, "details": {"status": "PASS"}}
        calls = [
            {
                "name": "bbk_governed_write",
                "tool_call_id": "write-a",
                "timestamp": "2026-08-05T00:00:00Z",
                "session_name": "Alpha17WorkerA",
                "arguments": {"bindingRef": "binding:a", "path": "src/worker-a/result.txt"},
                "result": success,
            },
            {
                "name": "bbk_governed_read",
                "tool_call_id": "read-a",
                "timestamp": "2026-08-05T00:00:01Z",
                "session_name": "Alpha17WorkerA",
                "arguments": {"bindingRef": "binding:a", "path": "src/worker-a/result.txt"},
                "result": success,
            },
            {
                "name": "bash",
                "tool_call_id": "hash-a",
                "timestamp": "2026-08-05T00:00:02Z",
                "session_name": "Alpha17WorkerA",
                "arguments": {"command": "sha256sum src/worker-a/result.txt"},
                "result": {"is_error": True, "text": "blocked before effect"},
            },
        ]
        result = module.analyze_verification_economy(calls)
        self.assertEqual("FAIL", result["status"])
        self.assertIn("UNCHANGED_SUBJECT_REREAD", result["reason_codes"])
        self.assertIn("AD_HOC_DUPLICATE_HASH_ATTEMPT", result["reason_codes"])
        self.assertEqual(2, result["duplicate_deterministic_check_count"])

    def test_result_record_population_leaves_only_redaction_attestation_manual(self):
        module = self.analyzer_module()
        with tempfile.TemporaryDirectory() as raw:
            temp = Path(raw)
            template = temp / "template.json"
            output = temp / "result.json"
            template.write_text(json.dumps({
                "template": True,
                "operator_result": None,
                "candidate_digest": None,
                "evidence_files": [],
                "missing_evidence": [],
                "smallest_next_action": None,
                "critical_path_observations": {},
                "observed_invariants": [{"id": f"M17-{index:03d}", "result": None} for index in range(1, 17)],
                "redaction_attestation": {"inspected": None, "secrets_absent": None, "operator": None},
            }), encoding="utf-8")
            report = {
                "status": "PASS",
                "reason_codes": [],
                "product": {"integration_candidate_digest": "sha256:" + "1" * 64},
                "verification_economy": {"duplicate_deterministic_check_count": 0, "unnecessary_handoff_attempt_count": 0, "status": "PASS", "metadata_or_broad_validator_call_count": 0},
                "role_returns": {"same_attempt_schema_repair_count": 1},
                "coordination": {"minimum_observed_probe_interval_seconds": 300, "specific_job_poll_attempt_count": 0, "blocking_wait_count": 1},
                "mode": {"active_expected_version_count": 1, "skill_prompt_count": 0},
            }
            invariants = {f"M17-{index:03d}": {"result": "PASS", "evidence_pointers": ["fixture"], "operator_note": "", "reason_codes": []} for index in range(1, 17)}
            module.populate_result_record(template, output, report, invariants)
            value = json.loads(output.read_text(encoding="utf-8"))
            self.assertFalse(value["template"])
            self.assertEqual("PASS", value["operator_result"])
            self.assertTrue(all(item["result"] == "PASS" for item in value["observed_invariants"]))
            self.assertEqual({"inspected": None, "secrets_absent": None, "operator": None}, value["redaction_attestation"])

    def test_manual_kit_zip_excludes_interpreter_caches_and_is_deterministic(self):
        spec = importlib.util.spec_from_file_location("bbk_build_manual_kit", ROOT / "tools" / "qualification" / "build_manual_kit.py")
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as raw:
            temp = Path(raw)
            source = temp / "manual-qualification-kit-alpha17-test"
            (source / "nested" / "__pycache__").mkdir(parents=True)
            (source / "operator.txt").write_text("stable\n", encoding="utf-8")
            (source / "nested" / "script.py").write_text("print('ok')\n", encoding="utf-8")
            (source / "nested" / "__pycache__" / "script.cpython-313.pyc").write_bytes(b"unstable-cache")
            first = temp / "first.zip"
            second = temp / "second.zip"
            module.build_zip(source, first)
            module.build_zip(source, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                names = archive.namelist()
            self.assertFalse(any("__pycache__" in name or name.endswith(".pyc") for name in names))
            self.assertIn(f"{source.name}/operator.txt", names)

    def test_expected_manual_gate_includes_mode_and_coordination_assertions(self):
        invariants = json.loads((TEMPLATE / "expected-invariants.json").read_text(encoding="utf-8"))
        ids = [item["id"] for item in invariants["invariants"]]
        self.assertEqual(ids, [f"M17-{index:03d}" for index in range(1, 17)])
        self.assertIn("session admission PASS", invariants["pass_rule"])
        prompt = (TEMPLATE / "EXACT-OMP-PROMPT.md").read_text(encoding="utf-8")
        self.assertIn("Do not invoke `/bbk`", prompt)
        self.assertIn("once per 300 seconds", prompt)
        self.assertIn("all sixteen assertions", prompt)
        self.assertIn("compact token-addressed `dispatch_input`", prompt)
        self.assertIn("`bbk_control_dispatch_status`", prompt)
        self.assertIn("do not respawn the same logical attempt", prompt)
        self.assertIn("current `candidate_admission_ref`", prompt)
        self.assertIn("use `eval`, Python, shell, JavaScript", prompt)
        self.assertIn("Do not call `bbk_handoff_create`", prompt)
        self.assertIn("`bbk_return_template`", prompt)
        self.assertIn("`bbk_return_prepare`", prompt)
        self.assertIn("returned `yield_input`", prompt)


if __name__ == "__main__":
    unittest.main()
