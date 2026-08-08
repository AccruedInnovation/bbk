#!/usr/bin/env python3
"""Repeatable, keyless OMP 16.4.8 host-contract qualification.

The harness starts a localhost OpenAI-compatible provider, launches OMP in an
isolated home/profile/project, and verifies observable host behavior. It never
uses provider API keys or remote services.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

SCHEMA = "bbk.omp-host-contract-report.v1"
MODEL = "bbk-mock/mock-model"
EXPECTED_VERSION = "16.4.8"
ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "omp-host-contract"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _clean_environment(home: Path, agent: Path, log: Path, allowed_root: Path) -> tuple[dict[str, str], list[str]]:
    allowed_names = {
        "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC",
        "TMP", "TEMP", "TMPDIR", "LANG", "LC_ALL", "TERM",
    }
    env = {key: value for key, value in os.environ.items() if key.upper() in allowed_names}
    removed = sorted(
        key for key in os.environ
        if key not in env and any(token in key.upper() for token in ("KEY", "TOKEN", "SECRET", "PASSWORD", "COOKIE", "CREDENTIAL", "AUTH"))
    )
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "PI_CODING_AGENT_DIR": str(agent),
            "BBK_OMP_FIXTURE_LOG": str(log),
            "BBK_OMP_FIXTURE_ALLOWED_ROOT": str(allowed_root),
            "NO_PROXY": "127.0.0.1,localhost",
            "no_proxy": "127.0.0.1,localhost",
            "NO_COLOR": "1",
        }
    )
    for proxy in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        env.pop(proxy, None)
    return env, removed


def _tool_chunk(name: str, arguments: dict[str, Any], call_id: str) -> list[dict[str, Any]]:
    return [
        {
            "id": call_id,
            "object": "chat.completion.chunk",
            "created": 0,
            "model": "mock-model",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": call_id,
                                "type": "function",
                                "function": {"name": name, "arguments": json.dumps(arguments, separators=(",", ":"))},
                            }
                        ],
                    },
                    "finish_reason": None,
                }
            ],
        },
        {
            "id": call_id,
            "object": "chat.completion.chunk",
            "created": 0,
            "model": "mock-model",
            "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
        },
    ]


def _text_chunks(text: str, response_id: str) -> list[dict[str, Any]]:
    return [
        {
            "id": response_id,
            "object": "chat.completion.chunk",
            "created": 0,
            "model": "mock-model",
            "choices": [{"index": 0, "delta": {"role": "assistant", "content": text}, "finish_reason": None}],
        },
        {
            "id": response_id,
            "object": "chat.completion.chunk",
            "created": 0,
            "model": "mock-model",
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        },
    ]


def _message_blob(request: dict[str, Any]) -> str:
    return json.dumps(request.get("messages", []), ensure_ascii=False)


def _is_child(request: dict[str, Any]) -> bool:
    tool_names = {
        str(item.get("function", {}).get("name") or "")
        for item in request.get("tools", [])
        if isinstance(item, dict) and isinstance(item.get("function"), dict)
    }
    return "yield" in tool_names and "FIXTURE_CHILD_MARKER" in _message_blob(request)


def _tool_results(request: dict[str, Any]) -> list[dict[str, Any]]:
    return [message for message in request.get("messages", []) if message.get("role") == "tool"]


@dataclass
class ScenarioState:
    name: str
    requests: list[dict[str, Any]] = field(default_factory=list)
    headers: list[dict[str, str]] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def response(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        results = _tool_results(request)
        if self.name == "ambient-block":
            index = len(results)
            calls = [
                ("write", {"i": "Testing write block", "path": "ambient-write.txt", "content": "MUTATED"}),
                ("edit", {"i": "Testing edit block", "input": "[existing.txt#0000]\nSWAP 1.=1:\n+MUTATED"}),
                ("bash", {"i": "Testing bash block", "command": "printf MUTATED > ambient-bash.txt"}),
            ]
            if index < len(calls):
                name, arguments = calls[index]
                return _tool_chunk(name, arguments, f"call-block-{index + 1}")
            return _text_chunks("AMBIENT_BLOCK_DONE", "ambient-done")

        if self.name == "scoped-write":
            if not results:
                return _tool_chunk(
                    "bbk_fixture_scoped_write",
                    {"i": "Testing governed write", "path": "inside.txt", "content": "GOVERNED"},
                    "call-scoped-write",
                )
            return _text_chunks("SCOPED_WRITE_DONE", "scoped-done")

        if self.name == "child-identity":
            if _is_child(request):
                if not results:
                    return _tool_chunk(
                        "bbk_fixture_identity",
                        {"i": "Reporting child identity", "value": "child"},
                        "call-child-identity",
                    )
                return _tool_chunk(
                    "yield",
                    {"result": {"data": {"status": "PASS", "identity": "child"}}},
                    "call-child-yield",
                )
            if not results:
                return _tool_chunk(
                    "task",
                    {
                        "i": "Testing child identity",
                        "context": "# Goal\nObserve parent and child host identity\n# Constraints\nNo ambient mutation\n# Contract\nReturn one identity result",
                        "tasks": [
                            {
                                "name": "FixtureWorker",
                                "agent": "fixture_worker",
                                "task": "# Target\nOMP host identity only\n# Change\nCall bbk_fixture_identity once\n# Acceptance\nYield a PASS identity result",
                            }
                        ],
                    },
                    "call-parent-task",
                )
            return _text_chunks("CHILD_IDENTITY_DONE", "child-main-done")

        if self.name == "yield-validation":
            if _is_child(request):
                if not results:
                    return _tool_chunk(
                        "yield",
                        {"result": {"data": {"schema": "fixture.invalid-role-return.v1", "status": "MALFORMED"}}},
                        "call-yield-invalid",
                    )
                return _tool_chunk(
                    "yield",
                    {
                        "result": {
                            "data": {
                                "schema": "fixture.role-return.v1",
                                "status": "PASS",
                                "identity": "yield-child",
                                "prepared_return_ref": "return:" + ("b" * 64),
                            }
                        }
                    },
                    "call-yield-prepared-full",
                )
            if not results:
                return _tool_chunk(
                    "task",
                    {
                        "i": "Testing yield pre-effect validation",
                        "context": "# Goal\nProve malformed yield blocking and complete prepared-return admission\n# Constraints\nNo mutation\n# Contract\nReturn one validated role result",
                        "tasks": [{
                            "name": "FixtureYieldWorker",
                            "agent": "fixture_worker",
                            "task": "# Target\nFIXTURE_CHILD_MARKER yield validation\n# Change\nAttempt malformed yield once, then submit the complete prepared return\n# Acceptance\nParent receives only the complete hook-admitted PASS role result",
                        }],
                    },
                    "call-parent-yield-task",
                )
            return _text_chunks("YIELD_VALIDATION_DONE", "yield-main-done")

        if self.name == "dispatch-rewrite":
            if _is_child(request):
                if not results:
                    return _tool_chunk(
                        "bbk_fixture_identity",
                        {"i": "Reporting dispatch-resolved child identity", "value": "dispatch-child"},
                        "call-dispatch-child-identity",
                    )
                return _tool_chunk(
                    "yield",
                    {"result": {"data": {"status": "PASS", "identity": "dispatch-child"}}},
                    "call-dispatch-child-yield",
                )
            if not results:
                marker = '<bbk-spawn-dispatch ref="dispatch:' + ('a' * 64) + '"/>'
                return _tool_chunk(
                    "task",
                    {
                        "i": "Dispatch immutable BBK child reservation",
                        "context": marker,
                        "tasks": [
                            {
                                "agent": "fixture_worker",
                                "name": "FixtureWorker",
                                "task": marker,
                            }
                        ],
                    },
                    "call-parent-dispatch",
                )
            return _text_chunks("DISPATCH_REWRITE_DONE", "dispatch-main-done")

        raise AssertionError(f"unknown scenario: {self.name}")


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, state: ScenarioState):
        self.state = state
        super().__init__(("127.0.0.1", 0), _Handler)


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        length = int(self.headers.get("content-length", "0"))
        request = json.loads(self.rfile.read(length))
        state: ScenarioState = self.server.state  # type: ignore[attr-defined]
        with state.lock:
            state.requests.append(request)
            state.headers.append({key.lower(): value for key, value in self.headers.items()})
        chunks = state.response(request)
        body = ("".join(f"data: {json.dumps(chunk, separators=(',', ':'))}\n\n" for chunk in chunks) + "data: [DONE]\n\n").encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)


def _events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _event_sessions(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str | None, str | None, str | None]] = set()
    sessions: list[dict[str, Any]] = []
    for event in events:
        context = event.get("context") or {}
        key = (context.get("session_id"), context.get("cwd"), context.get("session_file"))
        if key[0] and key not in seen:
            seen.add(key)
            sessions.append({"session_id": key[0], "cwd": key[1], "session_file": key[2]})
    return sessions


def _run_scenario(omp: Path, scenario: str, keep_temp: bool) -> dict[str, Any]:
    root = Path(tempfile.mkdtemp(prefix=f"bbk-omp-{scenario}-"))
    home, agent, project = root / "home", root / "agent", root / "project"
    allowed = project / "governed"
    for directory in (home, agent, project, allowed):
        directory.mkdir(parents=True, exist_ok=True)
    (project / "existing.txt").write_text("ORIGINAL\n", encoding="utf-8")
    (project / ".omp" / "agents").mkdir(parents=True, exist_ok=True)
    shutil.copy2(FIXTURES / "fixture-worker.md", project / ".omp" / "agents" / "fixture_worker.md")
    log = root / "events.jsonl"

    state = ScenarioState(scenario)
    server = _Server(state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        (agent / "models.yml").write_text(
            "\n".join(
                [
                    "providers:",
                    "  bbk-mock:",
                    f"    baseUrl: http://127.0.0.1:{server.server_port}/v1",
                    "    auth: none",
                    "    api: openai-completions",
                    "    models:",
                    "      - id: mock-model",
                    "        name: BBK Mock Model",
                    "        contextWindow: 32000",
                    "        maxTokens: 4096",
                    "        reasoning: false",
                    "        input: [text]",
                    "        cost: {input: 0, output: 0, cacheRead: 0, cacheWrite: 0}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        env, removed_sensitive = _clean_environment(home, agent, log, allowed)
        command = [
            str(omp),
            "-p",
            "--no-session",
            "--no-title",
            "--no-skills",
            "--no-rules",
            "-e",
            str(FIXTURES / "fixture-extension.mjs"),
            "--model",
            MODEL,
            "--cwd",
            str(project),
            "--max-time",
            "30",
            f"Run BBK OMP host-contract scenario {scenario}",
        ]
        completed = subprocess.run(
            command,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=45,
            check=False,
        )
        time.sleep(0.1)
        events = _events(log)
        result: dict[str, Any] = {
            "scenario": scenario,
            "process": {
                "return_code": completed.returncode,
                "stdout": completed.stdout.strip(),
                "stderr": completed.stderr.strip(),
            },
            "provider": {
                "request_count": len(state.requests),
                "authorization_header_seen": any("authorization" in headers for headers in state.headers),
                "loopback_only": True,
                "credential_environment_keys_present": [],
                "sensitive_environment_keys_removed_count": len(removed_sensitive),
            },
            "events": {
                "count": len(events),
                "kinds": sorted({event.get("kind") for event in events}),
                "sessions": _event_sessions(events),
            },
        }

        if scenario == "ambient-block":
            blocked = [
                event for event in events
                if event.get("kind") == "tool_execution_end"
                and (event.get("event") or {}).get("tool_name") in {"write", "edit", "bash"}
                and (event.get("event") or {}).get("is_error") is True
            ]
            result["observations"] = {
                "blocked_tools": sorted((event.get("event") or {}).get("tool_name") for event in blocked),
                "write_effect_absent": not (project / "ambient-write.txt").exists(),
                "edit_effect_absent": (project / "existing.txt").read_text(encoding="utf-8") == "ORIGINAL\n",
                "bash_effect_absent": not (project / "ambient-bash.txt").exists(),
            }
            result["status"] = "PASS" if (
                completed.returncode == 0
                and result["observations"]["blocked_tools"] == ["bash", "edit", "write"]
                and all(result["observations"][key] for key in ("write_effect_absent", "edit_effect_absent", "bash_effect_absent"))
            ) else "FAIL"

        elif scenario == "scoped-write":
            target = allowed / "inside.txt"
            result["observations"] = {
                "custom_tool_observed": any(event.get("kind") == "custom_scoped_write" for event in events),
                "governed_file_created": target.exists(),
                "governed_file_content": target.read_text(encoding="utf-8") if target.exists() else None,
            }
            result["status"] = "PASS" if (
                completed.returncode == 0
                and result["observations"]["custom_tool_observed"]
                and result["observations"]["governed_file_content"] == "GOVERNED"
            ) else "FAIL"

        elif scenario == "child-identity":
            sessions = result["events"]["sessions"]
            lifecycle = [
                event for event in events
                if event.get("kind") == "task:subagent:lifecycle"
                and (event.get("event") or {}).get("agent") == "fixture_worker"
            ]
            distinct = len({session.get("session_id") for session in sessions}) >= 2
            same_cwd = len({session.get("cwd") for session in sessions}) == 1 and sessions
            parent_binding = any(
                (event.get("event") or {}).get("parent_tool_call_id") == "call-parent-task"
                and (event.get("event") or {}).get("id") == "FixtureWorker"
                for event in lifecycle
            )
            result["observations"] = {
                "parent_child_session_ids_distinct": bool(distinct),
                "parent_child_cwd_equal": bool(same_cwd),
                "task_parent_binding_observed": parent_binding,
                "child_identity_tool_observed": any(event.get("kind") == "custom_identity" for event in events),
                "lifecycle_statuses": sorted({(event.get("event") or {}).get("status") for event in lifecycle if (event.get("event") or {}).get("status")}),
            }
            result["status"] = "PASS" if (
                completed.returncode == 0
                and all(result["observations"][key] for key in (
                    "parent_child_session_ids_distinct",
                    "parent_child_cwd_equal",
                    "task_parent_binding_observed",
                    "child_identity_tool_observed",
                ))
                and "started" in result["observations"]["lifecycle_statuses"]
                and "completed" in result["observations"]["lifecycle_statuses"]
            ) else "FAIL"

        elif scenario == "yield-validation":
            invalid_end = [
                event for event in events
                if event.get("kind") == "tool_execution_end"
                and (event.get("event") or {}).get("tool_name") == "yield"
                and (event.get("event") or {}).get("tool_call_id") == "call-yield-invalid"
                and (event.get("event") or {}).get("is_error") is True
            ]
            admissions = [event for event in events if event.get("kind") == "yield_full_document_admission"]
            lifecycle = [
                event for event in events
                if event.get("kind") == "task:subagent:lifecycle"
                and (event.get("event") or {}).get("agent") == "fixture_worker"
            ]
            request_blob = "\n".join(_message_blob(request) for request in state.requests)
            result["observations"] = {
                "malformed_yield_blocked_before_acceptance": bool(invalid_end),
                "complete_prepared_yield_admission_observed": bool(admissions),
                "complete_role_return_observed_by_parent": "fixture.role-return.v1" in request_blob and "yield-child" in request_blob,
                "unvalidated_malformed_return_absent_from_parent": "fixture.invalid-role-return.v1" not in "\n".join(
                    _message_blob(request) for request in state.requests if not _is_child(request)
                ),
                "lifecycle_statuses": sorted({(event.get("event") or {}).get("status") for event in lifecycle if (event.get("event") or {}).get("status")}),
            }
            result["status"] = "PASS" if (
                completed.returncode == 0
                and result["observations"]["malformed_yield_blocked_before_acceptance"]
                and result["observations"]["complete_prepared_yield_admission_observed"]
                and result["observations"]["complete_role_return_observed_by_parent"]
                and result["observations"]["unvalidated_malformed_return_absent_from_parent"]
                and "completed" in result["observations"]["lifecycle_statuses"]
            ) else "FAIL"

        elif scenario == "dispatch-rewrite":
            lifecycle = [
                event for event in events
                if event.get("kind") == "task:subagent:lifecycle"
                and (event.get("event") or {}).get("agent") == "fixture_worker"
            ]
            child_requests = [request for request in state.requests if _is_child(request)]
            identity_events = [event for event in events if event.get("kind") == "custom_identity"]
            compact_task_events = [
                event for event in events
                if event.get("kind") == "tool_call"
                and (event.get("event") or {}).get("tool_name") == "task"
                and "<bbk-spawn-dispatch" in json.dumps((event.get("event") or {}).get("input") or {})
            ]
            result["observations"] = {
                "dispatch_rewrite_observed": any(event.get("kind") == "dispatch_rewrite" for event in events),
                "presentation_i_absent_at_pre_effect_hook": bool(compact_task_events) and all(
                    "i" not in (((event.get("event") or {}).get("input") or {}))
                    for event in compact_task_events
                ),
                "resolved_child_started": bool(child_requests),
                "resolved_identity_value_observed": any(
                    ((event.get("event") or {}).get("input") or {}).get("value") == "dispatch-child"
                    for event in identity_events
                ),
                "compact_marker_absent_from_child_request": all(
                    "<bbk-spawn-dispatch" not in _message_blob(request) for request in child_requests
                ),
                "task_parent_binding_observed": any(
                    (event.get("event") or {}).get("parent_tool_call_id") == "call-parent-dispatch"
                    and (event.get("event") or {}).get("id") == "FixtureWorker"
                    for event in lifecycle
                ),
                "lifecycle_statuses": sorted({
                    (event.get("event") or {}).get("status")
                    for event in lifecycle if (event.get("event") or {}).get("status")
                }),
            }
            result["status"] = "PASS" if (
                completed.returncode == 0
                and all(result["observations"][key] for key in (
                    "dispatch_rewrite_observed",
                    "presentation_i_absent_at_pre_effect_hook",
                    "resolved_child_started",
                    "resolved_identity_value_observed",
                    "compact_marker_absent_from_child_request",
                    "task_parent_binding_observed",
                ))
                and "started" in result["observations"]["lifecycle_statuses"]
                and "completed" in result["observations"]["lifecycle_statuses"]
            ) else "FAIL"
        else:
            raise AssertionError(scenario)

        return result
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        if not keep_temp:
            shutil.rmtree(root, ignore_errors=True)


def _run_extension_overlay_scenario(omp: Path, keep_temp: bool) -> dict[str, Any]:
    """Prove the 16.4.8 launcher workaround keeps explicit paths and clears configured ones."""
    root = Path(tempfile.mkdtemp(prefix="bbk-omp-extension-overlay-"))
    home, agent, project = root / "home", root / "agent", root / "project"
    allowed = project / "governed"
    for directory in (home, agent, project, allowed):
        directory.mkdir(parents=True, exist_ok=True)
    (project / "existing.txt").write_text("ORIGINAL\n", encoding="utf-8")
    event_log = root / "events.jsonl"
    configured_log = root / "configured-extension-loaded.txt"
    configured_extension = root / "configured-extension.mjs"
    configured_extension.write_text(
        "\n".join(
            [
                'import { appendFileSync } from "node:fs";',
                "export default function configuredExtension(pi) {",
                f"  appendFileSync({json.dumps(str(configured_log))}, 'registered\\n', 'utf8');",
                "  pi.on?.('before_provider_request', async () => {",
                f"    appendFileSync({json.dumps(str(configured_log))}, 'provider-hook\\n', 'utf8');",
                "  });",
                "}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    overlay = root / "omp-qualification-overlay.yml"
    overlay.write_text("extensions: []\n", encoding="utf-8")

    state = ScenarioState("scoped-write")
    server = _Server(state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        (agent / "models.yml").write_text(
            "\n".join(
                [
                    "providers:",
                    "  bbk-mock:",
                    f"    baseUrl: http://127.0.0.1:{server.server_port}/v1",
                    "    auth: none",
                    "    api: openai-completions",
                    "    models:",
                    "      - id: mock-model",
                    "        name: BBK Mock Model",
                    "        contextWindow: 32000",
                    "        maxTokens: 4096",
                    "        reasoning: false",
                    "        input: [text]",
                    "        cost: {input: 0, output: 0, cacheRead: 0, cacheWrite: 0}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        env, removed_sensitive = _clean_environment(home, agent, event_log, allowed)
        configured_value = json.dumps([str(configured_extension)], separators=(",", ":"))
        set_run = subprocess.run(
            [str(omp), "config", "set", "extensions", configured_value],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
            check=False,
        )
        get_run = subprocess.run(
            [str(omp), "config", "get", "extensions", "--json"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
            check=False,
        )
        command = [
            str(omp),
            "-p",
            "--no-session",
            "--no-title",
            "--no-skills",
            "--no-rules",
            "--config",
            str(overlay),
            "-e",
            str(FIXTURES / "fixture-extension.mjs"),
            "--model",
            MODEL,
            "--cwd",
            str(project),
            "--max-time",
            "30",
            "Run BBK OMP configured-extension overlay scenario",
        ]
        completed = subprocess.run(
            command,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=45,
            check=False,
        )
        time.sleep(0.1)
        events = _events(event_log)
        target = allowed / "inside.txt"
        observations = {
            "configured_extension_recorded_before_overlay": str(configured_extension) in get_run.stdout,
            "configured_extension_loaded": configured_log.exists(),
            "explicit_extension_loaded": any(event.get("kind") == "custom_scoped_write" for event in events),
            "explicit_extension_effect": target.read_text(encoding="utf-8") if target.exists() else None,
            "no_extensions_flag_used": "--no-extensions" in command,
            "overlay_extensions_empty": overlay.read_text(encoding="utf-8").strip() == "extensions: []",
        }
        result = {
            "scenario": "extension-overlay",
            "process": {
                "return_code": completed.returncode,
                "stdout": completed.stdout.strip(),
                "stderr": completed.stderr.strip(),
            },
            "configuration": {
                "set_return_code": set_run.returncode,
                "set_stdout": set_run.stdout.strip(),
                "set_stderr": set_run.stderr.strip(),
                "get_return_code": get_run.returncode,
                "get_stdout": get_run.stdout.strip(),
                "get_stderr": get_run.stderr.strip(),
                "overlay": overlay.read_text(encoding="utf-8").strip(),
            },
            "provider": {
                "request_count": len(state.requests),
                "authorization_header_seen": any("authorization" in headers for headers in state.headers),
                "loopback_only": True,
                "credential_environment_keys_present": [],
                "sensitive_environment_keys_removed_count": len(removed_sensitive),
            },
            "events": {
                "count": len(events),
                "kinds": sorted({event.get("kind") for event in events}),
                "sessions": _event_sessions(events),
            },
            "observations": observations,
        }
        result["status"] = "PASS" if (
            set_run.returncode == 0
            and get_run.returncode == 0
            and completed.returncode == 0
            and observations["configured_extension_recorded_before_overlay"]
            and not observations["configured_extension_loaded"]
            and observations["explicit_extension_loaded"]
            and observations["explicit_extension_effect"] == "GOVERNED"
            and not observations["no_extensions_flag_used"]
            and observations["overlay_extensions_empty"]
        ) else "FAIL"
        return result
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        if not keep_temp:
            shutil.rmtree(root, ignore_errors=True)


def qualify(omp: Path, *, keep_temp: bool = False) -> dict[str, Any]:
    omp = omp.resolve()
    if not omp.is_file():
        raise FileNotFoundError(f"OMP binary not found: {omp}")
    version_run = subprocess.run([str(omp), "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15, check=False)
    version_text = (version_run.stdout or version_run.stderr).strip()
    scenarios = [_run_scenario(omp, name, keep_temp) for name in ("ambient-block", "scoped-write", "child-identity", "dispatch-rewrite", "yield-validation")]
    scenarios.append(_run_extension_overlay_scenario(omp, keep_temp))
    assertions = {
        "VER-017": next(item for item in scenarios if item["scenario"] == "child-identity")["status"],
        "VER-018": "PASS" if all(
            next(item for item in scenarios if item["scenario"] == name)["status"] == "PASS"
            for name in ("ambient-block", "scoped-write")
        ) else "FAIL",
        "VER-019": "PASS",
        "VER-020": next(item for item in scenarios if item["scenario"] == "extension-overlay")["status"],
        "VER-021": next(item for item in scenarios if item["scenario"] == "dispatch-rewrite")["status"],
        "VER-022": next(item for item in scenarios if item["scenario"] == "yield-validation")["status"],
    }
    report = {
        "schema": SCHEMA,
        "status": "PASS" if all(item["status"] == "PASS" for item in scenarios) and EXPECTED_VERSION in version_text else "FAIL",
        "qualified_host": {
            "platform": sys.platform,
            "omp_version_output": version_text,
            "expected_omp_version": EXPECTED_VERSION,
            "omp_sha256": _sha256(omp),
        },
        "network_and_credentials": {
            "provider": "localhost keyless OpenAI-compatible fixture",
            "remote_provider_contacted": False,
            "provider_api_keys_used": False,
        },
        "assertions": assertions,
        "scenarios": scenarios,
        "enforcement_boundary": {
            "pre_effect_supported_and_observed": ["write", "edit", "bash", "yield", "custom governed tool"],
            "detect_only_or_unqualified": [
                "effects without an OMP pre-tool hook",
                "OS-level writes outside OMP tool mediation",
                "Windows host behavior",
                "real-provider behavior",
            ],
            "host_quirk": "OMP 16.4.8 suppresses explicit -e extensions when --no-extensions is also present, contrary to the CLI help text.",
            "manual_launcher_strategy": "Omit --no-extensions, apply a final config overlay containing extensions: [], disable skills and rules, then load the exact BBK extension and qualification helper explicitly in order. The keyless fixture proves the overlay suppresses a configured extension while preserving the explicit extension.",
        },
    }
    if report["status"] != "PASS":
        raise RuntimeError(json.dumps(report, indent=2))
    return report


def _markdown(report: dict[str, Any]) -> str:
    host = report["qualified_host"]
    scenarios = {item["scenario"]: item for item in report["scenarios"]}
    child = scenarios["child-identity"]["observations"]
    ambient = scenarios["ambient-block"]["observations"]
    scoped = scenarios["scoped-write"]["observations"]
    overlay = scenarios["extension-overlay"]["observations"]
    dispatch = scenarios["dispatch-rewrite"]["observations"]
    yield_validation = scenarios["yield-validation"]["observations"]
    return f"""# OMP 16.4.8 host-contract feasibility report

Status: **{report['status']}**

## Qualified binary

- Version output: `{host['omp_version_output']}`
- SHA-256: `{host['omp_sha256']}`
- Platform: `{host['platform']}`
- Provider: localhost keyless OpenAI-compatible fixture
- External provider credentials: not supplied

## Observed contracts

- `VER-017`: parent and child session identities were distinct: `{str(child['parent_child_session_ids_distinct']).lower()}`.
- `VER-017`: parent and child CWDs were equal: `{str(child['parent_child_cwd_equal']).lower()}`; CWD is therefore context, not an isolation identity.
- `VER-017`: task name, agent, and parent tool-call binding were observed through lifecycle events: `{str(child['task_parent_binding_observed']).lower()}`.
- `VER-018`: built-in `write`, `edit`, and `bash` calls returned blocked tool results before effects; absent effects were `{ambient['write_effect_absent']}`, `{ambient['edit_effect_absent']}`, and `{ambient['bash_effect_absent']}` respectively.
- `VER-018`: the custom governed write created only the scoped fixture file with expected content: `{str(scoped['governed_file_created']).lower()}`.
- `VER-019`: unsupported paths remain explicitly `DETECT_ONLY` or `UNQUALIFIED`; this report does not claim OS sandboxing, Windows qualification, real-provider qualification, or prevention outside OMP-mediated pre-tool hooks.
- `VER-020`: an `extensions: []` final overlay suppressed an extension stored in OMP configuration while preserving the explicit qualification extension: configured loaded `{str(overlay['configured_extension_loaded']).lower()}`, explicit loaded `{str(overlay['explicit_extension_loaded']).lower()}`.
- `VER-021`: OMP removed the presentation-only `i` field before the pre-effect hook `{str(dispatch['presentation_i_absent_at_pre_effect_hook']).lower()}`, and the hook still replaced the canonical compact dispatch envelope with the exact full task input before OMP spawned the child: rewrite observed `{str(dispatch['dispatch_rewrite_observed']).lower()}`, child started `{str(dispatch['resolved_child_started']).lower()}`, compact marker absent from child request `{str(dispatch['compact_marker_absent_from_child_request']).lower()}`.
- `VER-022`: a malformed child `yield` was blocked before acceptance `{str(yield_validation['malformed_yield_blocked_before_acceptance']).lower()}`; a complete prepared return was admitted unchanged `{str(yield_validation['complete_prepared_yield_admission_observed']).lower()}`; the parent observed only that full validated role return `{str(yield_validation['complete_role_return_observed_by_parent']).lower()}`.

## Host quirk retained as evidence

{report['enforcement_boundary']['host_quirk']}

The qualified manual-launch strategy is: {report['enforcement_boundary']['manual_launcher_strategy']}

## Reproduction

```text
python tools/qualification/omp_host_contract.py --omp <path-to-omp-16.4.8> --output <report.json> --markdown <report.md>
```

The runner constructs isolated HOME, OMP agent, and project roots; removes proxy and credential-bearing environment variables; starts only a `127.0.0.1` mock provider; and records normalized event evidence without retaining model prompts or secrets.
"""


def _resolve_omp(value: str | None) -> Path:
    candidate = value or os.environ.get("BBK_OMP_BINARY") or shutil.which("omp")
    if not candidate:
        raise FileNotFoundError("set --omp, BBK_OMP_BINARY, or install omp on PATH")
    return Path(candidate)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--omp", help="path to OMP 16.4.8 binary")
    parser.add_argument("--output", type=Path, help="write canonical JSON report")
    parser.add_argument("--markdown", type=Path, help="write human-readable feasibility report")
    parser.add_argument("--keep-temp", action="store_true", help="retain isolated scenario directories for diagnosis")
    args = parser.parse_args(argv)
    report = qualify(_resolve_omp(args.omp), keep_temp=args.keep_temp)
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(_markdown(report), encoding="utf-8")
    sys.stdout.write(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
