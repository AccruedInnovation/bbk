from __future__ import annotations

import base64
import json
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import session_oracle

FIXTURE_ROOT = ROOT / "fixtures" / "session-inspector-alpha16"
MANIFEST_PATH = FIXTURE_ROOT / "source-session-oracle.json"
CONTRADICTIONS_PATH = FIXTURE_ROOT / "derived-analysis-contradictions.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def schema_validator(schema_name: str) -> Draft202012Validator:
    schema_root = ROOT / "spec" / "schemas"
    resources = []
    for path in sorted(schema_root.rglob("*.json")):
        value = read_json(path)
        if isinstance(value, dict) and value.get("$id"):
            resources.append((value["$id"], Resource.from_contents(value)))
    registry = Registry().with_resources(resources)
    return Draft202012Validator(read_json(schema_root / schema_name), registry=registry)


def message_entry(
    entry_id: str,
    timestamp: str,
    *,
    role: str,
    content: list[dict] | None = None,
    tool_call_id: str | None = None,
    usage: dict | None = None,
    response_id: str | None = None,
) -> dict:
    message: dict = {
        "role": role,
        "content": content or [],
        "timestamp": timestamp,
    }
    if tool_call_id is not None:
        message["toolCallId"] = tool_call_id
    if usage is not None:
        message.update(
            {
                "provider": "fixture-provider",
                "model": "fixture-model",
                "usage": usage,
                "responseId": response_id,
            }
        )
    return {
        "type": "message",
        "id": entry_id,
        "parentId": None,
        "timestamp": timestamp,
        "message": message,
    }


def prompt_receipt(entry_id: str, timestamp: str, *, session_id: str, role: str, phase: str) -> dict:
    data = {
        "schema": "bbk.effective-prompt-receipt.v2",
        "phase": phase,
        "session_id": session_id,
        "role": role,
    }
    if phase == "before_agent_start":
        data.update({"status": "REPLACED", "action": "BOUND"})
    else:
        data.update({"status": "VERIFIED", "action": "VERIFIED"})
    return {
        "type": "custom",
        "customType": "bbk-effective-prompt-receipt",
        "data": data,
        "id": entry_id,
        "parentId": None,
        "timestamp": timestamp,
    }


def usage(total_cost: str, *, tokens: int) -> dict:
    return {
        "input": tokens,
        "output": 0,
        "cacheRead": 0,
        "cacheWrite": 0,
        "reasoningTokens": 0,
        "totalTokens": tokens,
        "cost": {
            "input": float(total_cost),
            "output": 0,
            "cacheRead": 0,
            "cacheWrite": 0,
            "total": float(total_cost),
        },
    }


def synthetic_pair(root: Path) -> tuple[Path, Path]:
    main_id = "fixture-main-session"
    child_id = "fixture-child-session"
    task_call_id = "fixture-task-call"
    ask_call_id = "fixture-ask-call"
    response_main = "11111111-1111-4111-8111-111111111111"
    response_child = "22222222-2222-4222-8222-222222222222"
    main_entries = [
        prompt_receipt("main-bound", "2026-08-04T00:00:00.001Z", session_id=main_id, role="Main", phase="before_agent_start"),
        prompt_receipt("main-verified", "2026-08-04T00:00:00.002Z", session_id=main_id, role="Main", phase="provider_request_finalization"),
        message_entry(
            "main-response",
            "2026-08-04T00:00:01.000Z",
            role="assistant",
            usage=usage("0.01", tokens=10),
            response_id=response_main,
            content=[
                {
                    "type": "toolCall",
                    "id": task_call_id,
                    "name": "task",
                    "arguments": {
                        "i": "fixture child",
                        "context": "redacted by oracle",
                        "tasks": [
                            {
                                "agent": "bbk_worker",
                                "name": "FixtureWorker",
                                "task": "Sensitive assignment text must not be retained.",
                            }
                        ],
                    },
                }
            ],
        ),
        message_entry(
            "ask-response",
            "2026-08-04T00:00:02.000Z",
            role="assistant",
            content=[
                {
                    "type": "toolCall",
                    "id": ask_call_id,
                    "name": "ask",
                    "arguments": {"questions": [{"id": "q1", "question": "continue?"}]},
                }
            ],
        ),
        message_entry(
            "ask-result",
            "2026-08-04T00:00:03.250Z",
            role="toolResult",
            tool_call_id=ask_call_id,
            content=[{"type": "text", "text": "accepted"}],
        ),
        message_entry(
            "job-poll",
            "2026-08-04T00:00:04.000Z",
            role="assistant",
            content=[{"type": "toolCall", "id": "job-call", "name": "job", "arguments": {}}],
        ),
    ]
    child_entries = [
        {
            "type": "session_init",
            "id": "child-init",
            "parentId": None,
            "timestamp": "2026-08-04T00:00:01.050Z",
            "task": "Sensitive child task text.",
        },
        prompt_receipt(
            "child-bound",
            "2026-08-04T00:00:01.051Z",
            session_id=child_id,
            role="bbk_worker",
            phase="before_agent_start",
        ),
        prompt_receipt(
            "child-verified",
            "2026-08-04T00:00:01.052Z",
            session_id=child_id,
            role="bbk_worker",
            phase="provider_request_finalization",
        ),
        message_entry(
            "child-response",
            "2026-08-04T00:00:02.500Z",
            role="assistant",
            usage=usage("0.02", tokens=20),
            response_id=response_child,
        ),
    ]
    export = {
        "header": {
            "type": "session",
            "version": 3,
            "id": main_id,
            "timestamp": "2026-08-04T00:00:00.000Z",
            "cwd": "C:/sensitive/path",
            "title": "sensitive title",
        },
        "entries": main_entries,
        "subSessions": {
            "FixtureWorker": {
                "agentId": "bbk_worker",
                "parent": None,
                "header": {
                    "type": "session",
                    "version": 3,
                    "id": child_id,
                    "timestamp": "2026-08-04T00:00:01.050Z",
                    "cwd": "C:/sensitive/path",
                    "title": "child",
                },
                "entries": child_entries,
                "leafId": "child-response",
            }
        },
        "leafId": "job-poll",
    }
    encoded = base64.b64encode(json.dumps(export, separators=(",", ":")).encode("utf-8")).decode("ascii")
    html = root / "source.html"
    html.write_text(
        '<!doctype html><script id="session-data" type="application/json">'
        + encoded
        + "</script>",
        encoding="utf-8",
    )
    derived = {
        "header": {**export["header"], "entryCount": len(main_entries)},
        "entries": main_entries,
        "totals": {
            "grandTotal": {
                "inputTokens": 10,
                "outputTokens": 0,
                "cacheReadTokens": 0,
                "cacheWriteTokens": 0,
                "reasoningTokens": 0,
                "totalTokens": 10,
                "costInputUsd": 0.01,
                "costOutputUsd": 0,
                "costCacheReadUsd": 0,
                "costCacheWriteUsd": 0,
                "costTotalUsd": 0.01,
            }
        },
        "agents": [
            {"agentId": "agent:system"},
            {"agentId": "agent:toolResult"},
            {"agentId": "agent:Main"},
            {"agentId": "agent:user"},
            {"agentId": response_main},
        ],
        "waitIntervals": [
            {
                "fromTs": "2026-08-04T00:00:00.000Z",
                "toTs": "2026-08-04T00:00:00.500Z",
                "durationS": 0.5,
            }
        ],
        "bbkEvents": [main_entries[0], main_entries[1]],
    }
    derived_path = root / "derived.json"
    write_json(derived_path, derived)
    return html, derived_path


class SessionInspectorOracleTests(unittest.TestCase):
    def test_checked_in_oracle_is_schema_valid_and_exact(self) -> None:
        manifest = read_json(MANIFEST_PATH)
        contradictions = read_json(CONTRADICTIONS_PATH)
        schema_validator("bbk-session-inspector-oracle-manifest-v1.schema.json").validate(manifest)
        schema_validator("bbk-session-inspector-contradictions-v1.schema.json").validate(contradictions)
        result = session_oracle.verify_oracle(manifest, contradictions)
        schema_validator("bbk-session-inspector-oracle-verification-v1.schema.json").validate(result)
        host_validator = schema_validator("bbk-host-event-v1.schema.json")
        for host_event in manifest["host_events"]:
            host_validator.validate(host_event)
        self.assertEqual("PASS", result["status"])
        self.assertFalse(result["source_regenerated"])

        expected = manifest["expected"]
        self.assertEqual(5, expected["session_count"])
        self.assertEqual(690, expected["main_entry_count"])
        self.assertEqual(629, expected["child_entry_count"])
        self.assertEqual(1319, expected["inclusive_entry_count"])
        self.assertEqual(4, expected["task_invocation_count"])
        self.assertEqual(1, expected["explicit_user_wait_count"])
        self.assertEqual(5217, expected["explicit_user_wait_total_ms"])
        self.assertEqual(281, expected["provider_response_count"])
        self.assertEqual(286, expected["prompt_integrity_receipt_count"])
        self.assertEqual(31239337, expected["tokens"]["total"])
        self.assertEqual("0.47572615", expected["costs"]["total_usd"])
        self.assertEqual(30, expected["polling_tool_calls"]["main_job_calls"])
        self.assertEqual(44, expected["polling_tool_calls"]["main_total"])
        self.assertEqual("IF-014", manifest["interface_binding"]["interface_id"])
        self.assertEqual("UNOBSERVED_IN_EXPORT", manifest["interface_binding"]["host_version"])
        self.assertEqual("DETECT_ONLY", manifest["interface_binding"]["enforcement_boundary"])
        self.assertEqual(5, len(manifest["host_events"]))

    def test_negative_oracle_preserves_main_controls_and_blocks_complete_truth(self) -> None:
        value = read_json(CONTRADICTIONS_PATH)
        self.assertEqual("NEGATIVE_ORACLE_CONFIRMED", value["verdict"]["status"])
        self.assertFalse(value["verdict"]["derived_analysis_can_establish_complete_truth"])
        self.assertTrue(all(item["status"] == "PASS" for item in value["positive_controls"]))
        by_id = {item["id"]: item for item in value["contradictions"]}
        self.assertEqual(4, by_id["CHILD_SESSIONS_OMITTED"]["delta"])
        self.assertEqual(166, by_id["PROVIDER_RESPONSE_IDS_MISIDENTIFIED_AS_AGENTS"]["provider_response_ids_as_agents"])
        self.assertEqual(4, by_id["TASK_RECORDS_OMITTED"]["delta"])
        self.assertEqual(1, by_id["EXPLICIT_ASK_WAIT_OMITTED"]["missing_explicit_wait_count"])
        self.assertEqual("0.295132594", by_id["INCLUSIVE_COST_UNDERCOUNTED"]["excluded_value_usd"])
        self.assertEqual(119, by_id["CHILD_PROMPT_INTEGRITY_OMITTED"]["delta"])

    def test_fixture_retains_hashes_not_raw_sensitive_source_content(self) -> None:
        text = MANIFEST_PATH.read_text(encoding="utf-8") + CONTRADICTIONS_PATH.read_text(encoding="utf-8")
        for forbidden in (
            "D:\\\\projects",
            "C:/sensitive/path",
            "019fcd6c-8520-7000-ae55-907ccf4bf682",
            "call_00_",
            "Execute the OMP Session Inspector",
            "Sensitive assignment text",
            "api_key",
        ):
            self.assertNotIn(forbidden, text)
        manifest = read_json(MANIFEST_PATH)
        self.assertTrue(manifest["privacy"]["anonymized"])
        self.assertTrue(all(not value for key, value in manifest["privacy"].items() if key != "anonymized"))
        self.assertRegex(manifest["sources"]["session_export"]["sha256"], r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(manifest["sources"]["derived_analysis"]["sha256"], r"^sha256:[0-9a-f]{64}$")

    def test_synthetic_nested_export_builds_positive_and_negative_oracles(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            html, derived = synthetic_pair(Path(raw))
            manifest, contradictions = session_oracle.build_oracle(html, derived)
        self.assertEqual(2, manifest["expected"]["session_count"])
        self.assertEqual(10, manifest["expected"]["inclusive_entry_count"])
        self.assertEqual(1, manifest["expected"]["task_invocation_count"])
        self.assertEqual(1250, manifest["expected"]["explicit_user_wait_total_ms"])
        self.assertEqual(2, manifest["expected"]["provider_response_count"])
        self.assertEqual("0.03", manifest["expected"]["costs"]["total_usd"])
        self.assertEqual("session:fixture-worker", manifest["tasks"][0]["child_session_alias"])
        self.assertEqual("NEGATIVE_ORACLE_CONFIRMED", contradictions["verdict"]["status"])
        schema_validator("bbk-session-inspector-oracle-manifest-v1.schema.json").validate(manifest)
        schema_validator("bbk-session-inspector-contradictions-v1.schema.json").validate(contradictions)

    def test_exact_source_reproduction_detects_changed_source_or_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            html, derived = synthetic_pair(root)
            manifest, contradictions = session_oracle.build_oracle(html, derived)
            result = session_oracle.verify_oracle(
                manifest,
                contradictions,
                source_html=html,
                derived_json=derived,
            )
            self.assertEqual("PASS", result["status"])
            self.assertTrue(result["checks"]["source_manifest_reproduced"])

            tampered = dict(manifest)
            tampered["expected"] = dict(manifest["expected"])
            tampered["expected"]["session_count"] = 99
            with self.assertRaisesRegex(session_oracle.SessionOracleError, "FIXTURE_DIGEST_MISMATCH"):
                session_oracle.verify_oracle(tampered, contradictions)

            changed = root / "changed.html"
            changed.write_bytes(html.read_bytes() + b"\n")
            changed_result = session_oracle.verify_oracle(
                manifest,
                contradictions,
                source_html=changed,
                derived_json=derived,
            )
            self.assertEqual("FAIL", changed_result["status"])
            self.assertFalse(changed_result["checks"]["source_manifest_reproduced"])

    def test_malformed_or_ambiguous_session_payload_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            missing = root / "missing.html"
            missing.write_text("<html></html>", encoding="utf-8")
            with self.assertRaisesRegex(session_oracle.SessionOracleError, "SESSION_DATA_SCRIPT_INVALID"):
                session_oracle.decode_session_export(missing)

            duplicate = root / "duplicate.html"
            payload = base64.b64encode(b"{}").decode("ascii")
            script = f'<script id="session-data" type="application/json">{payload}</script>'
            duplicate.write_text(script + script, encoding="utf-8")
            with self.assertRaisesRegex(session_oracle.SessionOracleError, "SESSION_DATA_SCRIPT_INVALID"):
                session_oracle.decode_session_export(duplicate)

            invalid = root / "invalid.html"
            invalid.write_text('<script id="session-data" type="application/json">not-base64!</script>', encoding="utf-8")
            with self.assertRaisesRegex(session_oracle.SessionOracleError, "SESSION_DATA_BASE64_INVALID"):
                session_oracle.decode_session_export(invalid)


if __name__ == "__main__":
    unittest.main()
