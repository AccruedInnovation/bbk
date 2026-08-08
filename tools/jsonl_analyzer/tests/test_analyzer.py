from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import bbk_jsonl_analyzer as analyzer  # noqa: E402


def record(timestamp: str, record_type: str, payload: dict) -> str:
    return json.dumps({"timestamp": timestamp, "type": record_type, "payload": payload}) + "\n"


def sample_log(role: str = "bbk_worker") -> str:
    session_id = "worker-001"
    root_id = "root-001"
    parts = [
        record(
            "2026-08-05T10:00:00Z",
            "session_meta",
            {
                "session_id": root_id,
                "id": session_id,
                "parent_thread_id": root_id,
                "timestamp": "2026-08-05T10:00:00Z",
                "cwd": "C:\\repo",
                "thread_source": "subagent",
                "agent_role": role,
                "agent_nickname": "Test",
                "agent_path": "/root/worker",
                "source": {
                    "subagent": {
                        "thread_spawn": {
                            "parent_thread_id": root_id,
                            "depth": 1,
                            "agent_path": "/root/worker",
                            "agent_nickname": "Test",
                            "agent_role": role,
                        }
                    }
                },
            },
        ),
        record(
            "2026-08-05T10:00:01Z",
            "turn_context",
            {"model": "gpt-test", "effort": "medium", "cwd": "C:\\repo"},
        ),
        record(
            "2026-08-05T10:00:02Z",
            "response_item",
            {
                "type": "custom_tool_call",
                "id": "ctc-1",
                "call_id": "call-1",
                "name": "exec",
                "input": "const r=await tools.shell_command({\"command\":\"Get-Content -Raw 'C:\\\\Users\\\\u\\\\.agents\\\\skills\\\\bbk-work-unit-execution\\\\SKILL.md'; bbk handoff verify --path x\",\"workdir\":\"C:\\\\repo\"}); text(r);",
            },
        ),
        record(
            "2026-08-05T10:00:03Z",
            "response_item",
            {
                "type": "custom_tool_call_output",
                "call_id": "call-1",
                "output": [{"type": "input_text", "text": "Exit code: 0\nOutput:\nOK\n"}],
            },
        ),
        record(
            "2026-08-05T10:00:04Z",
            "response_item",
            {
                "type": "custom_tool_call",
                "id": "ctc-2",
                "call_id": "call-2",
                "name": "exec",
                "input": "const patch=\"*** Begin Patch\\n*** Add File: C:/repo/a.txt\\n+x\\n*** End Patch\"; const r=await tools.apply_patch({patch}); text(r);",
            },
        ),
        record(
            "2026-08-05T10:00:05Z",
            "event_msg",
            {
                "type": "patch_apply_end",
                "call_id": "call-2",
                "success": True,
                "changes": {"C:\\repo\\a.txt": {"type": "add", "content": "x\n"}},
            },
        ),
        record(
            "2026-08-05T10:00:06Z",
            "response_item",
            {
                "type": "function_call",
                "id": "fc-1",
                "call_id": "fc-call-1",
                "name": "wait_agent",
                "namespace": "collaboration",
                "arguments": "{\"ids\":[\"child\"],\"timeout_ms\":1000}",
            },
        ),
        record(
            "2026-08-05T10:00:07Z",
            "event_msg",
            {
                "type": "token_count",
                "info": {
                    "total_token_usage": {
                        "input_tokens": 100,
                        "cached_input_tokens": 20,
                        "cache_write_input_tokens": 0,
                        "output_tokens": 30,
                        "reasoning_output_tokens": 10,
                        "total_tokens": 130,
                    }
                },
            },
        ),
        record("2026-08-05T10:00:08Z", "event_msg", {"type": "task_complete"}),
    ]
    return "".join(parts)


class ExtractorTests(unittest.TestCase):
    def test_extracts_quoted_and_bare_command_properties(self) -> None:
        quoted = 'const r=await tools.shell_command({"command":"echo hi"});'
        bare = 'const r=await tools.shell_command({command:"echo bye"});'
        self.assertEqual(analyzer.extract_named_js_string(analyzer.extract_js_tool_calls(quoted)[0][1], "command"), "echo hi")
        self.assertEqual(analyzer.extract_named_js_string(analyzer.extract_js_tool_calls(bare)[0][1], "command"), "echo bye")

    def test_js_string_decoding(self) -> None:
        value, _ = analyzer.parse_js_string('"a\\nb\\\\c"', 0)
        self.assertEqual(value, "a\nb\\c")


class AnalyzerTests(unittest.TestCase):
    def test_analyzes_jsonl_and_writes_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / "rollout.jsonl"
            log.write_text(sample_log(), encoding="utf-8")
            out = root / "report"
            instance = analyzer.Analyzer(analyzer.load_config(None), command_text_mode="redacted")
            instance.analyze_sources(analyzer.discover_sources([str(log)]))
            report = instance.write_report(out, "synthetic")

            metrics = report["metrics"]
            self.assertEqual(metrics["sessions"], 1)
            self.assertEqual(metrics["direct_shell_commands"], 1)
            self.assertEqual(metrics["exec_blocks"], 2)
            self.assertEqual(metrics["patch_path_events"], 1)
            self.assertEqual(metrics["skill_read_commands"], 1)
            self.assertEqual(metrics["category_handoff_verify"], 1)
            self.assertEqual(metrics["function_wait_agent"], 1)
            self.assertEqual(metrics["tokens_total_tokens"], 130)
            self.assertEqual(report["role_class_counts"]["execution"], 1)
            for name in (
                "summary.json",
                "summary.md",
                "sessions.csv",
                "commands.csv",
                "function_calls.csv",
                "patches.csv",
                "skill_reads.csv",
                "role_summary.csv",
            ):
                self.assertTrue((out / name).exists(), name)

    def test_analyzes_zip_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "logs.zip"
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("nested/rollout.jsonl", sample_log())
            instance = analyzer.Analyzer(analyzer.load_config(None))
            instance.analyze_sources(analyzer.discover_sources([str(archive)]))
            report = instance.build_report("zip")
            self.assertEqual(report["metrics"]["sessions"], 1)
            self.assertEqual(report["metrics"]["direct_shell_commands"], 1)

    def test_compare_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = root / "before"
            after = root / "after"
            before.mkdir()
            after.mkdir()
            analyzer.write_json(before / "summary.json", {"label": "before", "metrics": {"sessions": 10, "direct_shell_commands": 100}})
            analyzer.write_json(after / "summary.json", {"label": "after", "metrics": {"sessions": 8, "direct_shell_commands": 50}})
            comparison = analyzer.write_comparison(str(before), str(after), root / "comparison", None, None)
            rows = {row["metric"]: row for row in comparison["rows"]}
            self.assertEqual(rows["direct_shell_commands"]["delta"], -50)
            self.assertEqual(rows["direct_shell_commands"]["percent_change"], -50)
            self.assertTrue((root / "comparison" / "comparison.md").exists())

    def test_alpha17_structured_event_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / "alpha17.jsonl"
            prompt_event = {
                "schema": "bbk.prompt-compilation-event.v1", "event": "PROMPT_COMPILED",
                "logical_child_id": "child:worker", "physical_attempt_id": "attempt:1",
                "identity_kind": "ROLE", "role": "bbk_worker", "harness": "CODEX",
                "effective_prompt_sha256": "a" * 64, "procedure_ids": ["bbk-work-unit-execution"],
                "external_catalog_sha256": "b" * 64, "source_reads_by_compiler": 1,
                "procedure_reads_by_model": 0, "reused": False,
            }
            reuse_event = dict(prompt_event, event="PROMPT_REUSED", source_reads_by_compiler=0, reused=True)
            readiness = {
                "schema": "bbk.planning-readiness.v1", "readiness": ["ROADMAP_READY", "FRONTIER_READY"],
                "execution_admissible": True, "frontier_ref": {"id": "frontier"},
                "deferred_refinements": [{"id": "later", "status": "DEFERRED_UNTIL_FRONTIER"}],
            }
            worker = {
                "schema": "bbk.child-event.v1", "child_ref": "worker:1", "state": "STARTED",
                "detail": {"role": "bbk_worker"}, "observed_at": "2026-08-05T10:00:12Z", "poll_required": False,
            }
            content = sample_log()
            for index, value in enumerate((prompt_event, reuse_event, readiness, worker), 9):
                content += record(f"2026-08-05T10:00:{index:02d}Z", "event_msg", value)
            # Magic vocabulary in prose must not create a typed event.
            content += record("2026-08-05T10:00:20Z", "response_item", {
                "type": "message", "role": "assistant",
                "content": [{"type": "output_text", "text": "COMPILED_COMPLETE FOLLOWUP_REUSED ROADMAP_READY FRONTIER_READY worker_started"}],
            })
            log.write_text(content, encoding="utf-8")
            config = analyzer.load_config(str(HERE / "alpha17-config.json"))
            instance = analyzer.Analyzer(config)
            instance.analyze_sources(analyzer.discover_sources([str(log)]))
            out = root / "report"
            report = instance.write_report(out, "alpha17")
            self.assertEqual(1, report["metrics"]["structured_event_compiled_procedure_selected"])
            self.assertEqual(1, report["metrics"]["structured_event_compiled_catalog_suppressed"])
            self.assertEqual(1, report["metrics"]["structured_event_compiled_followup_reused"])
            self.assertEqual(1, report["metrics"]["structured_event_frontier_ready"])
            self.assertEqual(1, report["metrics"]["structured_event_worker_started"])
            self.assertEqual(4, report["metrics"]["typed_event_records"])
            typed = [json.loads(line) for line in (out / "typed_events.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(4, len(typed))
            self.assertTrue((out / "structured_event_summary.csv").is_file())



if __name__ == "__main__":
    unittest.main()
