#!/usr/bin/env python3
"""BBK/Codex JSONL analyzer.

A dependency-free analyzer for Codex rollout JSONL logs. It accepts individual
JSONL files, directories, and ZIP archives, then emits reproducible CSV/JSON/
Markdown reports covering sessions, roles, shell/tool use, skill reads,
verification activity, patches, polling, token totals, and duplicate commands.

The parser is intentionally tolerant of schema drift. Unknown records are
counted and preserved in warnings rather than causing the run to fail.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import sys
import textwrap
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Callable, Iterable, Iterator, Mapping, MutableMapping, Sequence

VERSION = "1.1.0"

TYPED_EVENT_SCHEMAS = {
    "bbk.prompt-compilation-event.v1",
    "bbk.planning-readiness.v1",
    "bbk.child-event.v1",
    "bbk.workspace-admission-receipt.v1",
    "bbk.project-coverage.v1",
    "bbk.identity-receipt.v1",
    "bbk.command-replay-admission.v1",
}


DEFAULT_CONFIG: dict[str, Any] = {
    "command_categories": {
        "skill_read": {
            "pattern": r"(?is)(?:Get-Content|\bgc\b|\bcat\b|\btype\b|\bmore\b|\bsed\b|\bhead\b|\btail\b|ReadAllText|\brg\b|Select-String|\bfindstr\b)[^\n]*(?:SKILL\.md|skills[\\/])",
            "description": "A shell command that appears to read an indexed skill file.",
        },
        "handoff_verify": {
            "pattern": r"(?i)(?:\bbb[kq](?:\.exe)?\b[^\n;|&]*\bhandoff\s+verify\b|\bhandoff\s+verify\b)",
            "description": "BBK handoff verification.",
        },
        "handoff_verify_help": {
            "pattern": r"(?i)\bhandoff\s+verify\b[^\n;|&]*(?:--help|-h\b)",
            "description": "Help lookup for handoff verification.",
        },
        "handoff_create": {
            "pattern": r"(?i)(?:\bbb[kq](?:\.exe)?\b[^\n;|&]*\bhandoff\s+create\b|\bhandoff\s+create\b)",
            "description": "BBK handoff creation.",
        },
        "schema_validate": {
            "pattern": r"(?i)(?:\bbb[kq](?:\.exe)?\b[^\n;|&]*\bschema\s+validate\b|\bschema\s+validate\b|jsonschema[^\n;|&]*validate)",
            "description": "Schema validation command.",
        },
        "schema_validate_cli": {
            "pattern": r"(?i)\bbb[kq](?:\.exe)?\b[^\n;|&]*\bschema\s+validate\b",
            "description": "Strict BBK schema validate CLI invocation.",
        },
        "repo_validator": {
            "pattern": r"(?i)(?:^|[\s'\"\\/])validate_generated_code\.py(?:[\s'\"]|$)",
            "description": "Repository-wide generated-code validator.",
        },
        "sha256_hash": {
            "pattern": r"(?i)(?:Get-FileHash|sha256sum|shasum\s+-a\s+256|certutil[^\n]*-hashfile[^\n]*sha256|hashlib\.sha256)",
            "description": "SHA-256 calculation or verification.",
        },
        "get_file_hash": {
            "pattern": r"(?i)\bGet-FileHash\b",
            "description": "PowerShell Get-FileHash invocation.",
        },
        "git_status": {
            "pattern": r"(?i)\bgit(?:\.exe)?\s+(?:(?:-C|--git-dir|--work-tree)\s+[^\s]+\s+)*status\b",
            "description": "Git status inspection.",
        },
        "git_diff": {
            "pattern": r"(?i)\bgit(?:\.exe)?\s+(?:(?:-C|--git-dir|--work-tree)\s+[^\s]+\s+)*diff\b",
            "description": "Git diff inspection.",
        },
        "test_or_build": {
            "pattern": r"(?i)(?:\bpytest\b|\bpython(?:\.exe)?\s+-m\s+unittest\b|\bdotnet\s+test\b|\bcargo\s+(?:test|check|build)\b|\b(?:npm|pnpm|yarn)\s+(?:test|run\s+test|build)\b|\bgo\s+test\b|\bctest\b|\bmsbuild\b)",
            "description": "Common test or build invocation.",
        },
        "process_poll": {
            "pattern": r"(?i)(?:Get-Process|Wait-Process|\btasklist\b|\bps\s+(?:aux|ef)\b|Get-CimInstance\s+Win32_Process)",
            "description": "Process inspection or polling.",
        },
        "file_search": {
            "pattern": r"(?i)(?:\brg\b|\bripgrep\b|Get-ChildItem|\bfind\b|\bfindstr\b|Select-String)",
            "description": "File listing or content search.",
        },
        "file_read": {
            "pattern": r"(?i)(?:Get-Content|\bgc\b|\bcat\b|\btype\b|\bmore\b|\bsed\s+-n\b|\bhead\b|\btail\b|ReadAllText)",
            "description": "File content read.",
        },
        "bbk_help": {
            "pattern": r"(?i)\bbb[kq](?:\.exe)?\b[^\n;|&]*(?:--help|-h\b)",
            "description": "BBK CLI help lookup.",
        },
    },
    "role_classes": {
        "execution": [
            r"^bbk_root_orchestrator$",
            r"^bbk_territory_orchestrator$",
            r"^bbk_worker_orchestrator$",
            r"^bbk_worker$",
        ],
        "planning_design_research": [
            r"^bbk_(?:root|territory|planning|phase)_wayfinder$",
            r"^bbk_(?:architect|researcher|prototyper|synthesizer|worker_designer|verification_designer|question_guide|questioning_wayfinder)$",
        ],
        "assurance": [
            r"^bbk_reviewer$",
            r"^bbk_validator(?:_orchestrator)?$",
        ],
        "controller": [r"^(?:controller_root|root|unknown)$"],
    },
    "skill_path_patterns": [
        r"(?i)(?:\.agents|agents)[\\/]+skills[\\/]+(?P<skill>[^\\/]+)[\\/]+SKILL\.md",
        r"(?i)skills://(?P<skill>[^/]+)/SKILL\.md",
        r"(?i)[\\/](?P<skill>bbk[^\\/]*)[\\/]+SKILL\.md",
    ],
    "read_verbs_pattern": r"(?i)(?:Get-Content|\bgc\b|\bcat\b|\btype\b|\bmore\b|\bsed\b|\bhead\b|\btail\b|ReadAllText|\brg\b|Select-String|\bfindstr\b)",
    "redaction": {
        "long_literal_threshold": 180,
        "secret_name_pattern": r"(?i)(?:api[_-]?key|token|secret|password|passwd|authorization|credential)",
    },
}


def iter_typed_event_objects(value: Any) -> Iterator[dict[str, Any]]:
    """Yield structured BBK records without parsing model-authored text strings."""
    if isinstance(value, Mapping):
        schema = value.get("schema")
        if isinstance(schema, str) and schema in TYPED_EVENT_SCHEMAS:
            yield dict(value)
        for child in value.values():
            if isinstance(child, (Mapping, list, tuple)):
                yield from iter_typed_event_objects(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            if isinstance(child, (Mapping, list, tuple)):
                yield from iter_typed_event_objects(child)


def typed_event_categories(value: Mapping[str, Any]) -> list[str]:
    schema = str(value.get("schema") or "")
    categories: list[str] = []
    if schema == "bbk.prompt-compilation-event.v1":
        event = str(value.get("event") or "")
        if event == "PROMPT_COMPILED":
            categories.extend(["compiled_procedure_selected", "compiled_catalog_suppressed"])
        elif event == "PROMPT_REUSED":
            categories.append("compiled_followup_reused")
    elif schema == "bbk.planning-readiness.v1":
        readiness = {str(item) for item in value.get("readiness") or []}
        if "ROADMAP_READY" in readiness:
            categories.append("roadmap_ready")
        if "FRONTIER_READY" in readiness:
            categories.append("frontier_ready")
        if any(isinstance(item, Mapping) and item.get("status") == "DEFERRED_UNTIL_FRONTIER" for item in value.get("deferred_refinements") or []):
            categories.append("future_deferred")
    elif schema == "bbk.child-event.v1" and value.get("state") == "STARTED":
        detail = value.get("detail") if isinstance(value.get("detail"), Mapping) else {}
        role = str(detail.get("role") or detail.get("agent_role") or value.get("child_ref") or "").lower()
        if "worker" in role:
            categories.append("worker_started")
    elif schema == "bbk.workspace-admission-receipt.v1":
        categories.append("workspace_receipt")
    elif schema == "bbk.project-coverage.v1":
        categories.append("project_coverage")
    elif schema == "bbk.identity-receipt.v1":
        categories.append("atomic_finalization")
    elif schema == "bbk.command-replay-admission.v1":
        categories.append("replay_admission")
    return categories


@dataclass
class LogSource:
    container: str
    member: str
    opener: Callable[[], BinaryIO]
    size: int | None = None

    @property
    def display(self) -> str:
        return f"{self.container}!{self.member}" if self.member else self.container


@dataclass
class WarningRecord:
    source: str
    line: int | None
    kind: str
    detail: str


@dataclass
class CommandRow:
    source: str
    member: str
    timestamp: str
    session_key: str
    session_id: str
    role: str
    role_class: str
    agent_path: str
    call_id: str
    custom_tool_name: str
    internal_tool: str
    internal_index: int
    command_full: str
    command_sha256: str
    normalized_sha256: str
    categories: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    output_chars: int = 0
    output_exit_code: int | None = None
    output_truncated: bool = False


@dataclass
class FunctionRow:
    source: str
    member: str
    timestamp: str
    session_key: str
    session_id: str
    role: str
    role_class: str
    agent_path: str
    call_id: str
    namespace: str
    name: str
    arguments_json: str
    task_name: str


@dataclass
class PatchRow:
    source: str
    member: str
    timestamp: str
    session_key: str
    session_id: str
    role: str
    role_class: str
    call_id: str
    path: str
    change_type: str
    success: bool | None


@dataclass
class SkillReadRow:
    source: str
    member: str
    timestamp: str
    session_key: str
    session_id: str
    role: str
    role_class: str
    call_id: str
    skill: str
    command_sha256: str
    output_chars_allocated: int
    output_chars_call_total: int
    read_index_in_call: int
    reads_in_call: int
    repeated_in_session: bool = False


@dataclass
class SessionState:
    source: str
    member: str
    source_size: int | None
    session_key: str = ""
    session_id: str = ""
    root_session_id: str = ""
    parent_thread_id: str = ""
    role: str = "unknown"
    role_class: str = "unknown"
    nickname: str = ""
    agent_path: str = ""
    depth: int | None = None
    model: str = ""
    effort: str = ""
    cwd: str = ""
    originator: str = ""
    cli_version: str = ""
    first_ts: datetime | None = None
    last_ts: datetime | None = None
    meta_ts: datetime | None = None
    lines: int = 0
    json_errors: int = 0
    record_types: Counter[str] = field(default_factory=Counter)
    response_types: Counter[str] = field(default_factory=Counter)
    event_types: Counter[str] = field(default_factory=Counter)
    structured_events: Counter[str] = field(default_factory=Counter)
    internal_tools: Counter[str] = field(default_factory=Counter)
    functions: Counter[str] = field(default_factory=Counter)
    categories: Counter[str] = field(default_factory=Counter)
    exec_blocks: int = 0
    shell_commands: int = 0
    patch_calls: int = 0
    patch_paths: int = 0
    compactions: int = 0
    task_starts: int = 0
    task_completes: int = 0
    agent_messages: int = 0
    final_message_chars: int = 0
    token_usage: dict[str, int] = field(default_factory=dict)
    commands: list[CommandRow] = field(default_factory=list)
    functions_rows: list[FunctionRow] = field(default_factory=list)
    patches: list[PatchRow] = field(default_factory=list)
    skill_reads: list[SkillReadRow] = field(default_factory=list)
    typed_events: list[dict[str, Any]] = field(default_factory=list)
    call_to_command_indices: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list))
    call_to_skill_indices: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list))

    def observe_ts(self, value: Any) -> None:
        dt = parse_timestamp(value)
        if dt is None:
            return
        if self.first_ts is None or dt < self.first_ts:
            self.first_ts = dt
        if self.last_ts is None or dt > self.last_ts:
            self.last_ts = dt


class Analyzer:
    def __init__(self, config: Mapping[str, Any], command_text_mode: str = "redacted") -> None:
        self.config = dict(config)
        self.command_text_mode = command_text_mode
        self.category_patterns: dict[str, re.Pattern[str]] = {}
        self.category_descriptions: dict[str, str] = {}
        self.structured_event_patterns: dict[str, re.Pattern[str]] = {}
        for name, spec in self.config.get("command_categories", {}).items():
            pattern = spec["pattern"] if isinstance(spec, Mapping) else str(spec)
            description = spec.get("description", "") if isinstance(spec, Mapping) else ""
            self.category_patterns[name] = re.compile(pattern)
            self.category_descriptions[name] = description
        self.role_patterns: list[tuple[str, re.Pattern[str]]] = []
        for name, spec in self.config.get("structured_event_categories", {}).items():
            pattern = spec["pattern"] if isinstance(spec, Mapping) else str(spec)
            self.structured_event_patterns[name] = re.compile(pattern)
        for role_class, patterns in self.config.get("role_classes", {}).items():
            for pattern in patterns:
                self.role_patterns.append((role_class, re.compile(pattern, re.I)))
        self.skill_patterns = [re.compile(x) for x in self.config.get("skill_path_patterns", [])]
        self.read_verbs = re.compile(self.config.get("read_verbs_pattern", DEFAULT_CONFIG["read_verbs_pattern"]))
        self.sessions: list[SessionState] = []
        self.warnings: list[WarningRecord] = []
        self.sources_seen = 0

    def classify_role(self, role: str) -> str:
        for role_class, pattern in self.role_patterns:
            if pattern.search(role or "unknown"):
                return role_class
        return "unknown"

    def classify_command(self, command: str) -> list[str]:
        return [name for name, pattern in self.category_patterns.items() if pattern.search(command)]

    def extract_skills(self, command: str) -> list[str]:
        if not self.read_verbs.search(command):
            return []
        found: list[str] = []
        for pattern in self.skill_patterns:
            for match in pattern.finditer(command):
                skill = (match.groupdict().get("skill") or "").strip()
                if skill and skill.lower() not in {x.lower() for x in found}:
                    found.append(skill)
        return found

    def analyze_sources(self, sources: Iterable[LogSource]) -> None:
        for source in sources:
            self.sources_seen += 1
            self.sessions.append(self._analyze_source(source))
        self._mark_repeated_skill_reads()

    def _analyze_source(self, source: LogSource) -> SessionState:
        state = SessionState(source=source.container, member=source.member, source_size=source.size)
        state.session_key = source.display
        try:
            raw = source.opener()
        except Exception as exc:  # pragma: no cover - operating-system dependent
            self.warnings.append(WarningRecord(source.display, None, "open_error", repr(exc)))
            return state

        with raw:
            text_stream = io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace", newline="")
            for line_number, line in enumerate(text_stream, 1):
                state.lines += 1
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except Exception as exc:
                    state.json_errors += 1
                    self.warnings.append(
                        WarningRecord(source.display, line_number, "json_decode_error", f"{type(exc).__name__}: {exc}")
                    )
                    continue
                self._process_record(state, record, line_number)

        if not state.session_id:
            state.session_id = Path(source.member or source.container).stem
        if not state.root_session_id:
            state.root_session_id = state.session_id
        state.session_key = f"{state.session_id}@{source.display}"
        state.role_class = self.classify_role(state.role)
        # Role metadata arrives near the start, but rows may have been created before it.
        for row in state.commands:
            row.session_key = state.session_key
            row.session_id = state.session_id
            row.role = state.role
            row.role_class = state.role_class
            row.agent_path = state.agent_path
        for row in state.functions_rows:
            row.session_key = state.session_key
            row.session_id = state.session_id
            row.role = state.role
            row.role_class = state.role_class
            row.agent_path = state.agent_path
        for row in state.patches:
            row.session_key = state.session_key
            row.session_id = state.session_id
            row.role = state.role
            row.role_class = state.role_class
        for row in state.skill_reads:
            row.session_key = state.session_key
            row.session_id = state.session_id
            row.role = state.role
            row.role_class = state.role_class
        for row in state.typed_events:
            row["_session_key"] = state.session_key
            row["_session_id"] = state.session_id
            row["_role"] = state.role
            row["_role_class"] = state.role_class
            row["_agent_path"] = state.agent_path
        return state

    def _process_record(self, state: SessionState, record: Mapping[str, Any], line_number: int) -> None:
        timestamp = str(record.get("timestamp") or "")
        state.observe_ts(timestamp)
        record_type = str(record.get("type") or "unknown")
        state.record_types[record_type] += 1
        payload = record.get("payload")
        if not isinstance(payload, Mapping):
            payload = {}

        typed_objects = list(iter_typed_event_objects(payload))
        for typed in typed_objects:
            row = dict(typed)
            row.update({
                "_source": state.source, "_member": state.member, "_timestamp": timestamp,
                "_session_key": state.session_key, "_session_id": state.session_id,
                "_role": state.role, "_role_class": state.role_class,
                "_agent_path": state.agent_path, "_record_type": record_type, "_line": line_number,
            })
            state.typed_events.append(row)
            for name in typed_event_categories(typed):
                state.structured_events[name] += 1
            # Retain configurable categories, but evaluate patterns only against
            # schema-bound structured objects, never arbitrary model prose.
            if self.structured_event_patterns:
                searchable = json.dumps(typed, ensure_ascii=False, sort_keys=True)
                intrinsic = set(typed_event_categories(typed))
                for name, pattern in self.structured_event_patterns.items():
                    if name not in intrinsic and pattern.search(searchable):
                        state.structured_events[name] += 1

        if record_type == "session_meta":
            state.session_id = str(payload.get("id") or payload.get("session_id") or state.session_id)
            state.root_session_id = str(payload.get("session_id") or state.root_session_id or state.session_id)
            state.parent_thread_id = str(payload.get("parent_thread_id") or "")
            state.role = str(payload.get("agent_role") or state.role or "unknown")
            if state.role == "unknown" and str(payload.get("thread_source") or "") == "user":
                state.role = "controller_root"
            state.nickname = str(payload.get("agent_nickname") or "")
            state.agent_path = str(payload.get("agent_path") or "")
            state.cwd = str(payload.get("cwd") or "")
            state.originator = str(payload.get("originator") or "")
            state.cli_version = str(payload.get("cli_version") or "")
            state.meta_ts = parse_timestamp(payload.get("timestamp"))
            source = payload.get("source")
            try:
                spawn = source["subagent"]["thread_spawn"] if isinstance(source, Mapping) else {}
                if isinstance(spawn, Mapping):
                    state.depth = int(spawn.get("depth")) if spawn.get("depth") is not None else state.depth
                    state.agent_path = str(spawn.get("agent_path") or state.agent_path)
                    state.nickname = str(spawn.get("agent_nickname") or state.nickname)
                    state.role = str(spawn.get("agent_role") or state.role)
            except (KeyError, TypeError, ValueError):
                pass
            state.role_class = self.classify_role(state.role)
            return

        if record_type == "turn_context":
            state.model = str(payload.get("model") or state.model)
            state.effort = str(payload.get("effort") or state.effort)
            state.cwd = str(payload.get("cwd") or state.cwd)
            return

        if record_type == "compacted":
            state.compactions += 1
            return

        if record_type == "response_item":
            subtype = str(payload.get("type") or "unknown")
            state.response_types[subtype] += 1
            if subtype == "custom_tool_call":
                self._process_custom_call(state, payload, timestamp)
            elif subtype == "custom_tool_call_output":
                self._process_custom_output(state, payload)
            elif subtype == "function_call":
                self._process_function_call(state, payload, timestamp)
            elif subtype in {"agent_message", "message"}:
                if subtype == "agent_message":
                    state.agent_messages += 1
                if subtype == "message" and str(payload.get("role") or "") == "assistant":
                    state.final_message_chars += len(extract_text(payload.get("content")))
            return

        if record_type == "event_msg":
            subtype = str(payload.get("type") or "unknown")
            state.event_types[subtype] += 1
            if subtype == "task_started":
                state.task_starts += 1
            elif subtype == "task_complete":
                state.task_completes += 1
            elif subtype == "context_compacted":
                # Some versions emit both event_msg/context_compacted and compacted.
                # Count the canonical compacted record when present; otherwise this event.
                if state.record_types.get("compacted", 0) == 0:
                    state.compactions += 1
            elif subtype == "token_count":
                self._process_token_count(state, payload)
            elif subtype == "patch_apply_end":
                self._process_patch_event(state, payload, timestamp)
            return

    def _process_custom_call(self, state: SessionState, payload: Mapping[str, Any], timestamp: str) -> None:
        state.exec_blocks += 1
        call_id = str(payload.get("call_id") or payload.get("id") or "")
        custom_name = str(payload.get("name") or "")
        input_text = str(payload.get("input") or "")
        tool_calls = extract_js_tool_calls(input_text)
        if not tool_calls and custom_name:
            state.internal_tools[custom_name] += 1
        for internal_index, (tool_name, argument_text) in enumerate(tool_calls, 1):
            state.internal_tools[tool_name] += 1
            if tool_name == "shell_command":
                state.shell_commands += 1
                command = extract_named_js_string(argument_text, "command")
                if command is None:
                    command = "<dynamic-or-unparsed-command>"
                    self.warnings.append(
                        WarningRecord(state.source + ("!" + state.member if state.member else ""), None, "unparsed_shell_command", call_id)
                    )
                categories = self.classify_command(command)
                skills = self.extract_skills(command)
                for category in categories:
                    state.categories[category] += 1
                command_hash = sha256_text(command)
                normalized_hash = sha256_text(normalize_command(command))
                row = CommandRow(
                    source=state.source,
                    member=state.member,
                    timestamp=timestamp,
                    session_key=state.session_key,
                    session_id=state.session_id,
                    role=state.role,
                    role_class=state.role_class,
                    agent_path=state.agent_path,
                    call_id=call_id,
                    custom_tool_name=custom_name,
                    internal_tool=tool_name,
                    internal_index=internal_index,
                    command_full=command,
                    command_sha256=command_hash,
                    normalized_sha256=normalized_hash,
                    categories=categories,
                    skills=skills,
                )
                command_index = len(state.commands)
                state.commands.append(row)
                state.call_to_command_indices[call_id].append(command_index)
                if skills:
                    for read_index, skill in enumerate(skills, 1):
                        skill_row = SkillReadRow(
                            source=state.source,
                            member=state.member,
                            timestamp=timestamp,
                            session_key=state.session_key,
                            session_id=state.session_id,
                            role=state.role,
                            role_class=state.role_class,
                            call_id=call_id,
                            skill=skill,
                            command_sha256=command_hash,
                            output_chars_allocated=0,
                            output_chars_call_total=0,
                            read_index_in_call=read_index,
                            reads_in_call=len(skills),
                        )
                        skill_index = len(state.skill_reads)
                        state.skill_reads.append(skill_row)
                        state.call_to_skill_indices[call_id].append(skill_index)
            elif tool_name == "apply_patch":
                state.patch_calls += 1

    def _process_custom_output(self, state: SessionState, payload: Mapping[str, Any]) -> None:
        call_id = str(payload.get("call_id") or "")
        text = extract_text(payload.get("output"))
        output_chars = len(text)
        exit_code = parse_exit_code(text)
        truncated = bool(re.search(r"(?i)truncated output|output truncated", text))
        for command_index in state.call_to_command_indices.get(call_id, []):
            row = state.commands[command_index]
            row.output_chars = output_chars
            row.output_exit_code = exit_code
            row.output_truncated = truncated
        skill_indices = state.call_to_skill_indices.get(call_id, [])
        if skill_indices:
            base, remainder = divmod(output_chars, len(skill_indices))
            for position, skill_index in enumerate(skill_indices):
                row = state.skill_reads[skill_index]
                row.output_chars_call_total = output_chars
                row.output_chars_allocated = base + (1 if position < remainder else 0)

    def _process_function_call(self, state: SessionState, payload: Mapping[str, Any], timestamp: str) -> None:
        name = str(payload.get("name") or "")
        namespace = str(payload.get("namespace") or "")
        call_id = str(payload.get("call_id") or payload.get("id") or "")
        state.functions[name] += 1
        arguments_raw = payload.get("arguments")
        arguments_json = ""
        task_name = ""
        if isinstance(arguments_raw, str):
            arguments_json = arguments_raw
            try:
                arguments = json.loads(arguments_raw)
            except Exception:
                arguments = {}
        elif isinstance(arguments_raw, Mapping):
            arguments = dict(arguments_raw)
            arguments_json = json.dumps(arguments_raw, ensure_ascii=False, sort_keys=True)
        else:
            arguments = {}
            arguments_json = ""
        if isinstance(arguments, Mapping):
            task_name = str(arguments.get("task_name") or arguments.get("recipient") or "")
        state.functions_rows.append(
            FunctionRow(
                source=state.source,
                member=state.member,
                timestamp=timestamp,
                session_key=state.session_key,
                session_id=state.session_id,
                role=state.role,
                role_class=state.role_class,
                agent_path=state.agent_path,
                call_id=call_id,
                namespace=namespace,
                name=name,
                arguments_json=redact_function_arguments(arguments_json),
                task_name=task_name,
            )
        )

    def _process_token_count(self, state: SessionState, payload: Mapping[str, Any]) -> None:
        info = payload.get("info")
        if not isinstance(info, Mapping):
            return
        usage = info.get("total_token_usage")
        if not isinstance(usage, Mapping):
            return
        candidate: dict[str, int] = {}
        for key in (
            "input_tokens",
            "cached_input_tokens",
            "cache_write_input_tokens",
            "output_tokens",
            "reasoning_output_tokens",
            "total_tokens",
        ):
            value = usage.get(key)
            if isinstance(value, (int, float)):
                candidate[key] = int(value)
        if candidate.get("total_tokens", -1) >= state.token_usage.get("total_tokens", -1):
            state.token_usage = candidate

    def _process_patch_event(self, state: SessionState, payload: Mapping[str, Any], timestamp: str) -> None:
        call_id = str(payload.get("call_id") or "")
        success_raw = payload.get("success")
        success = bool(success_raw) if isinstance(success_raw, bool) else None
        changes = payload.get("changes")
        rows_added = 0
        if isinstance(changes, Mapping):
            for path, spec in changes.items():
                change_type = "unknown"
                if isinstance(spec, Mapping):
                    change_type = str(spec.get("type") or "unknown")
                state.patches.append(
                    PatchRow(
                        source=state.source,
                        member=state.member,
                        timestamp=timestamp,
                        session_key=state.session_key,
                        session_id=state.session_id,
                        role=state.role,
                        role_class=state.role_class,
                        call_id=call_id,
                        path=str(path),
                        change_type=change_type,
                        success=success,
                    )
                )
                rows_added += 1
        if rows_added == 0:
            stdout = str(payload.get("stdout") or "")
            for line in stdout.splitlines():
                match = re.match(r"\s*([AMDR])\s+(.+?)\s*$", line)
                if match:
                    state.patches.append(
                        PatchRow(
                            source=state.source,
                            member=state.member,
                            timestamp=timestamp,
                            session_key=state.session_key,
                            session_id=state.session_id,
                            role=state.role,
                            role_class=state.role_class,
                            call_id=call_id,
                            path=match.group(2),
                            change_type={"A": "add", "M": "update", "D": "delete", "R": "rename"}.get(match.group(1), "unknown"),
                            success=success,
                        )
                    )
                    rows_added += 1
        state.patch_paths += rows_added

    def _mark_repeated_skill_reads(self) -> None:
        for session in self.sessions:
            counts = Counter(row.skill.lower() for row in session.skill_reads)
            for row in session.skill_reads:
                row.repeated_in_session = counts[row.skill.lower()] > 1

    def build_report(self, label: str = "analysis") -> dict[str, Any]:
        sessions = self.sessions
        commands = [row for session in sessions for row in session.commands]
        functions = [row for session in sessions for row in session.functions_rows]
        patches = [row for session in sessions for row in session.patches]
        skill_reads = [row for session in sessions for row in session.skill_reads]

        first = min((s.first_ts for s in sessions if s.first_ts), default=None)
        last = max((s.last_ts for s in sessions if s.last_ts), default=None)
        campaign_span_s = (last - first).total_seconds() if first and last else 0.0

        function_counts = Counter(row.name for row in functions)
        internal_tool_counts = Counter(row.internal_tool for row in commands)
        # Include non-shell internal tools stored only in session counters.
        internal_tool_counts = Counter()
        for session in sessions:
            internal_tool_counts.update(session.internal_tools)
        category_counts = Counter(category for row in commands for category in row.categories)
        structured_event_counts: Counter[str] = Counter()
        for session in sessions:
            structured_event_counts.update(session.structured_events)
        category_sessions: dict[str, set[str]] = defaultdict(set)
        category_roles: dict[str, set[str]] = defaultdict(set)
        for row in commands:
            for category in row.categories:
                category_sessions[category].add(row.session_key)
                category_roles[category].add(row.role)

        role_class_counts = Counter(session.role_class for session in sessions)
        role_counts = Counter(session.role for session in sessions)
        effort_counts = Counter(session.effort or "unknown" for session in sessions)
        model_counts = Counter(session.model or "unknown" for session in sessions)

        exact_counts = Counter(row.command_sha256 for row in commands)
        normalized_counts = Counter(row.normalized_sha256 for row in commands)
        exact_duplicates = sum(max(0, count - 1) for count in exact_counts.values())
        normalized_duplicates = sum(max(0, count - 1) for count in normalized_counts.values())

        token_totals = Counter()
        for session in sessions:
            token_totals.update(session.token_usage)

        repo_validator_non_execution = sum(
            1
            for row in commands
            if "repo_validator" in row.categories and row.role_class != "execution"
        )

        metrics: dict[str, Any] = {
            "sessions": len(sessions),
            "sources": self.sources_seen,
            "campaign_start": format_timestamp(first),
            "campaign_end": format_timestamp(last),
            "campaign_span_seconds": campaign_span_s,
            "campaign_span_hours": campaign_span_s / 3600.0,
            "summed_session_duration_seconds": sum(session_duration_s(s) for s in sessions),
            "jsonl_lines": sum(s.lines for s in sessions),
            "json_decode_errors": sum(s.json_errors for s in sessions),
            "exec_blocks": sum(s.exec_blocks for s in sessions),
            "direct_shell_commands": len(commands),
            "patch_calls": sum(s.patch_calls for s in sessions),
            "patch_path_events": len(patches),
            "context_compactions": sum(s.compactions for s in sessions),
            "task_starts": sum(s.task_starts for s in sessions),
            "task_completes": sum(s.task_completes for s in sessions),
            "skill_read_commands": sum(1 for row in commands if row.skills),
            "skill_read_events": len(skill_reads),
            "skill_read_output_chars_allocated": sum(row.output_chars_allocated for row in skill_reads),
            "skill_read_call_output_chars_distinct": sum(
                next(iter(group)).output_chars_call_total
                for _, group_iter in groupby_sorted(skill_reads, key=lambda x: (x.session_key, x.call_id))
                for group in [[*group_iter]]
                if group
            ),
            "exact_duplicate_shell_commands": exact_duplicates,
            "normalized_duplicate_shell_commands": normalized_duplicates,
            "repo_validator_calls_by_non_execution_roles": repo_validator_non_execution,
            "typed_event_records": sum(len(s.typed_events) for s in sessions),
            "warnings": len(self.warnings),
        }
        for key, value in token_totals.items():
            metrics[f"tokens_{key}"] = value
        for name, count in category_counts.items():
            metrics[f"category_{name}"] = count
        for name, count in function_counts.items():
            metrics[f"function_{name}"] = count
        for name, count in structured_event_counts.items():
            metrics[f"structured_event_{name}"] = count
        for name, count in internal_tool_counts.items():
            metrics[f"internal_tool_{name}"] = count
        for name, count in role_class_counts.items():
            metrics[f"role_class_{name}_sessions"] = count

        report = {
            "schema": "bbk.codex-jsonl-analysis.v1",
            "analyzer": {"name": "bbk-jsonl-analyzer", "version": VERSION},
            "label": label,
            "generated_at": format_timestamp(datetime.now(timezone.utc)),
            "methodology": {
                "shell_command_unit": "one tools.shell_command invocation inside a custom exec block",
                "exec_block_unit": "one response_item/custom_tool_call record",
                "token_method": "maximum cumulative total_token_usage observed per session, summed across sessions",
                "skill_output_allocation": "tool-output characters are divided evenly among unique skill reads in the same custom call",
                "duplicate_method": "exact and whitespace-normalized SHA-256 group counts; duplicate count excludes the first occurrence",
                "privacy": f"command text export mode: {self.command_text_mode}; raw message bodies and tool outputs are not exported",
                "typed_event_method": "only schema-bound JSON objects are counted; text strings containing event vocabulary are ignored",
            },
            "metrics": metrics,
            "role_class_counts": dict(sorted(role_class_counts.items())),
            "role_counts": dict(sorted(role_counts.items())),
            "effort_counts": dict(sorted(effort_counts.items())),
            "model_counts": dict(sorted(model_counts.items())),
            "function_counts": dict(sorted(function_counts.items())),
            "internal_tool_counts": dict(sorted(internal_tool_counts.items())),
            "category_counts": dict(sorted(category_counts.items())),
            "structured_event_counts": dict(sorted(structured_event_counts.items())),
            "category_sessions": {k: len(v) for k, v in sorted(category_sessions.items())},
            "category_roles": {k: sorted(v) for k, v in sorted(category_roles.items())},
            "signals": build_signals(metrics, role_class_counts, role_counts, category_counts, function_counts, sessions),
        }
        return report

    def write_report(self, output_dir: Path, label: str = "analysis") -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        report = self.build_report(label)
        sessions = self.sessions
        commands = [row for session in sessions for row in session.commands]
        functions = [row for session in sessions for row in session.functions_rows]
        patches = [row for session in sessions for row in session.patches]
        skill_reads = [row for session in sessions for row in session.skill_reads]
        typed_events = [row for session in sessions for row in session.typed_events]

        write_json(output_dir / "summary.json", report)
        (output_dir / "summary.md").write_text(render_summary_markdown(report, sessions, skill_reads), encoding="utf-8", newline="\n")
        write_sessions_csv(output_dir / "sessions.csv", sessions, self.category_patterns.keys())
        write_commands_csv(output_dir / "commands.csv", commands, self.command_text_mode, self.config)
        write_functions_csv(output_dir / "function_calls.csv", functions)
        write_patches_csv(output_dir / "patches.csv", patches)
        write_skill_reads_csv(output_dir / "skill_reads.csv", skill_reads)
        write_role_summary_csv(output_dir / "role_summary.csv", sessions)
        write_category_summary_csv(output_dir / "category_summary.csv", commands, self.category_descriptions)
        write_structured_event_summary_csv(output_dir / "structured_event_summary.csv", report)
        with (output_dir / "typed_events.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
            for event in typed_events:
                stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        write_tool_summary_csv(output_dir / "tool_summary.csv", sessions, functions)
        write_duplicate_commands_csv(output_dir / "duplicate_commands.csv", commands, self.command_text_mode, self.config)
        write_warnings_csv(output_dir / "warnings.csv", self.warnings)
        return report


def groupby_sorted(items: Sequence[Any], key: Callable[[Any], Any]) -> Iterator[tuple[Any, Iterator[Any]]]:
    import itertools

    return itertools.groupby(sorted(items, key=key), key=key)


def discover_sources(paths: Sequence[str]) -> Iterator[LogSource]:
    seen: set[tuple[str, str]] = set()
    for raw_path in paths:
        path = Path(raw_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(path)
        if path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file() and child.suffix.lower() in {".jsonl", ".zip"}:
                    yield from discover_sources([str(child)])
            continue
        if path.suffix.lower() == ".jsonl":
            key = (str(path), "")
            if key in seen:
                continue
            seen.add(key)
            yield LogSource(str(path), "", lambda p=path: p.open("rb"), path.stat().st_size)
            continue
        if path.suffix.lower() == ".zip":
            try:
                archive = zipfile.ZipFile(path)
            except zipfile.BadZipFile as exc:
                raise ValueError(f"Not a valid ZIP archive: {path}") from exc
            names = [info for info in archive.infolist() if not info.is_dir() and info.filename.lower().endswith(".jsonl")]
            # Keep archive open through closures by opening it anew per member. This is
            # slower than sharing one handle but safe across generators and platforms.
            archive.close()
            for info in sorted(names, key=lambda x: x.filename):
                key = (str(path), info.filename)
                if key in seen:
                    continue
                seen.add(key)

                def opener(p: Path = path, member: str = info.filename) -> BinaryIO:
                    zf = zipfile.ZipFile(p)
                    raw = zf.open(member, "r")
                    return ZipMemberStream(zf, raw)

                yield LogSource(str(path), info.filename, opener, info.file_size)
            continue
        raise ValueError(f"Unsupported input (expected .jsonl, .zip, or directory): {path}")


class ZipMemberStream(io.RawIOBase):
    """Binary stream that closes both the member and its ZipFile."""

    def __init__(self, archive: zipfile.ZipFile, member: BinaryIO) -> None:
        self.archive = archive
        self.member = member

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        return self.member.read(size)

    def readinto(self, b: bytearray | memoryview) -> int:
        data = self.member.read(len(b))
        n = len(data)
        b[:n] = data
        return n

    def readline(self, size: int = -1) -> bytes:
        return self.member.readline(size)

    def close(self) -> None:
        if not self.closed:
            try:
                self.member.close()
            finally:
                self.archive.close()
        super().close()

    def __enter__(self) -> "ZipMemberStream":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()


def extract_js_tool_calls(text: str) -> list[tuple[str, str]]:
    calls: list[tuple[str, str]] = []
    pattern = re.compile(r"tools\.([A-Za-z_][A-Za-z0-9_]*)\s*\(")
    position = 0
    while True:
        match = pattern.search(text, position)
        if not match:
            break
        open_index = match.end() - 1
        close_index = find_matching_delimiter(text, open_index, "(", ")")
        if close_index is None:
            argument = text[open_index + 1 :]
            position = len(text)
        else:
            argument = text[open_index + 1 : close_index]
            position = close_index + 1
        calls.append((match.group(1), argument))
    return calls


def find_matching_delimiter(text: str, start: int, opener: str, closer: str) -> int | None:
    depth = 0
    quote: str | None = None
    escape = False
    line_comment = False
    block_comment = False
    i = start
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if line_comment:
            if ch in "\r\n":
                line_comment = False
            i += 1
            continue
        if block_comment:
            if ch == "*" and nxt == "/":
                block_comment = False
                i += 2
            else:
                i += 1
            continue
        if quote:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                quote = None
            i += 1
            continue
        if ch in {"'", '"', "`"}:
            quote = ch
            i += 1
            continue
        if ch == "/" and nxt == "/":
            line_comment = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            block_comment = True
            i += 2
            continue
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def extract_named_js_string(argument_text: str, name: str) -> str | None:
    property_name = rf"(?:{re.escape(name)}|\"{re.escape(name)}\"|'{re.escape(name)}')"
    match = re.search(rf"(?:^|[,{{\s]){property_name}\s*:\s*", argument_text)
    if not match:
        return None
    position = match.end()
    while position < len(argument_text) and argument_text[position].isspace():
        position += 1
    if position >= len(argument_text) or argument_text[position] not in {"'", '"', "`"}:
        return None
    value, _ = parse_js_string(argument_text, position)
    return value


def parse_js_string(text: str, start: int) -> tuple[str, int]:
    quote = text[start]
    i = start + 1
    result: list[str] = []
    while i < len(text):
        ch = text[i]
        if ch == quote:
            return "".join(result), i + 1
        if ch != "\\":
            result.append(ch)
            i += 1
            continue
        i += 1
        if i >= len(text):
            result.append("\\")
            break
        esc = text[i]
        simple = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}
        if esc in simple:
            result.append(simple[esc])
            i += 1
        elif esc in {"\\", "'", '"', "`"}:
            result.append(esc)
            i += 1
        elif esc == "x" and i + 2 < len(text):
            try:
                result.append(chr(int(text[i + 1 : i + 3], 16)))
                i += 3
            except ValueError:
                result.append("\\x")
                i += 1
        elif esc == "u" and i + 4 < len(text):
            try:
                result.append(chr(int(text[i + 1 : i + 5], 16)))
                i += 5
            except ValueError:
                result.append("\\u")
                i += 1
        elif esc in "\r\n":
            # JavaScript line continuation.
            if esc == "\r" and i + 1 < len(text) and text[i + 1] == "\n":
                i += 2
            else:
                i += 1
        else:
            result.append(esc)
            i += 1
    return "".join(result), i


def extract_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        pieces: list[str] = []
        for key in ("text", "message", "output", "content"):
            if key in value:
                pieces.append(extract_text(value[key]))
        return "\n".join(x for x in pieces if x)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return "\n".join(x for x in (extract_text(item) for item in value) if x)
    return str(value)


def parse_exit_code(text: str) -> int | None:
    matches = re.findall(r"(?i)(?:exit code|process exited with code)\s*[:=]?\s*(-?\d+)", text)
    if not matches:
        return None
    try:
        return int(matches[-1])
    except ValueError:
        return None


def parse_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def format_timestamp(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_command(command: str) -> str:
    return re.sub(r"\s+", " ", command).strip()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def redact_function_arguments(text: str) -> str:
    if not text:
        return ""
    # Encrypted child messages are both large and not analytically useful.
    text = re.sub(r'("message"\s*:\s*")([^"\\]|\\.){160,}("\s*[,}])', r'\1<REDACTED_LONG_MESSAGE>\3', text)
    return redact_secrets(text, DEFAULT_CONFIG)


def redact_secrets(text: str, config: Mapping[str, Any]) -> str:
    redaction = config.get("redaction", {}) if isinstance(config, Mapping) else {}
    threshold = int(redaction.get("long_literal_threshold", 180))
    secret_pattern = str(redaction.get("secret_name_pattern", DEFAULT_CONFIG["redaction"]["secret_name_pattern"]))
    secret_pattern = re.sub(r"^\(\?i\)", "", secret_pattern)

    text = re.sub(
        rf"({secret_pattern}\s*[:=]\s*)(['\"]?)([^\s'\";,]+)(\2)",
        lambda m: f"{m.group(1)}<REDACTED:{sha256_text(m.group(3))[:12]}>",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"(?i)(Authorization\s*:\s*Bearer\s+)([^\s'\";,]+)",
        lambda m: f"{m.group(1)}<REDACTED:{sha256_text(m.group(2))[:12]}>",
        text,
    )

    long_literal = re.compile(rf"(['\"])([^\r\n]{{{threshold},}}?)\1")

    def replace_long(match: re.Match[str]) -> str:
        value = match.group(2)
        if any(marker in value for marker in ("Get-Content", "python", "git ", "bbk ", "{", "}")) and len(value) < threshold * 3:
            return match.group(0)
        return f"{match.group(1)}<LONG_LITERAL sha256={sha256_text(value)[:12]} chars={len(value)}>{match.group(1)}"

    return long_literal.sub(replace_long, text)


def command_for_export(command: str, mode: str, config: Mapping[str, Any]) -> str:
    if mode == "full":
        return command
    if mode == "redacted":
        return redact_secrets(command, config)
    if mode in {"hash-only", "none"}:
        return ""
    raise ValueError(mode)


def session_duration_s(session: SessionState) -> float:
    if session.first_ts and session.last_ts:
        return max(0.0, (session.last_ts - session.first_ts).total_seconds())
    return 0.0


def build_signals(
    metrics: Mapping[str, Any],
    role_class_counts: Counter[str],
    role_counts: Counter[str],
    category_counts: Counter[str],
    function_counts: Counter[str],
    sessions: Sequence[SessionState],
) -> list[dict[str, str]]:
    signals: list[dict[str, str]] = []

    def add(severity: str, code: str, message: str) -> None:
        signals.append({"severity": severity, "code": code, "message": message})

    skill_reads = int(metrics.get("skill_read_commands", 0))
    if skill_reads:
        add("INFO", "SKILL_FILES_READ", f"{skill_reads} shell calls read one or more skill files; compiled-procedure catalog suppression can be checked against this count.")

    non_execution_validator = int(metrics.get("repo_validator_calls_by_non_execution_roles", 0))
    if non_execution_validator:
        add("WARN", "REPO_VALIDATOR_OUTSIDE_EXECUTION", f"{non_execution_validator} repository-validator calls came from non-execution roles.")

    worker_sessions = role_counts.get("bbk_worker", 0)
    planning = role_class_counts.get("planning_design_research", 0)
    assurance = role_class_counts.get("assurance", 0)
    if worker_sessions == 0 and (planning or assurance):
        add("WARN", "NO_WORKER_SESSIONS", f"The run contains {planning} planning/design/research and {assurance} assurance sessions but no bbk_worker session.")
    elif worker_sessions and (planning + assurance) > worker_sessions * 3:
        add("WARN", "SUPPORT_FANOUT", f"Planning/design/research plus assurance sessions ({planning + assurance}) exceed Worker sessions ({worker_sessions}) by more than 3:1.")

    waits = function_counts.get("wait_agent", 0) + function_counts.get("wait", 0)
    spawns = function_counts.get("spawn_agent", 0) + function_counts.get("followup_task", 0)
    if spawns and waits / spawns > 12:
        add("INFO", "POLLING_DENSITY", f"Wait calls ({waits}) are {waits / spawns:.1f} per spawn/follow-up ({spawns}); completion events or longer waits may reduce coordination traffic.")

    shell = int(metrics.get("direct_shell_commands", 0))
    duplicates = int(metrics.get("exact_duplicate_shell_commands", 0))
    if shell and duplicates / shell > 0.05:
        add("INFO", "EXACT_COMMAND_REPETITION", f"{duplicates} shell commands ({duplicates / shell:.1%}) repeat an earlier exact command in the same corpus.")

    if category_counts.get("handoff_verify", 0) > max(20, len(sessions) * 2):
        add("INFO", "HANDOFF_VERIFY_DENSITY", f"Handoff verification appears {category_counts['handoff_verify']} times across {len(sessions)} sessions.")

    duration_by_role = Counter()
    for session in sessions:
        duration_by_role[session.role] += session_duration_s(session)
    total = sum(duration_by_role.values())
    if total:
        role, seconds = duration_by_role.most_common(1)[0]
        if seconds / total > 0.5:
            add("INFO", "ROLE_DURATION_CONCENTRATION", f"{role} accounts for {seconds / total:.1%} of summed session duration.")

    if not signals:
        add("INFO", "NO_HEURISTIC_FLAGS", "No built-in heuristic threshold was crossed. This is not a correctness finding.")
    return signals


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: scalar_csv(row.get(key, "")) for key in fieldnames})


def scalar_csv(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(x) for x in value)
    if isinstance(value, Mapping):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def write_sessions_csv(path: Path, sessions: Sequence[SessionState], category_names: Iterable[str]) -> None:
    category_names = list(category_names)
    function_names = sorted({name for session in sessions for name in session.functions})
    fields = [
        "source",
        "member",
        "session_id",
        "root_session_id",
        "parent_thread_id",
        "role",
        "role_class",
        "nickname",
        "agent_path",
        "depth",
        "model",
        "effort",
        "cwd",
        "originator",
        "cli_version",
        "start",
        "end",
        "duration_s",
        "lines",
        "json_errors",
        "exec_blocks",
        "shell_commands",
        "patch_calls",
        "patch_paths",
        "compactions",
        "task_starts",
        "task_completes",
        "agent_messages",
        "final_message_chars",
        "input_tokens",
        "cached_input_tokens",
        "cache_write_input_tokens",
        "output_tokens",
        "reasoning_output_tokens",
        "total_tokens",
        "exact_duplicate_shell_commands",
        "normalized_duplicate_shell_commands",
    ] + [f"func_{name}" for name in function_names] + [f"cat_{name}" for name in category_names]

    rows: list[dict[str, Any]] = []
    for session in sessions:
        exact_counts = Counter(row.command_sha256 for row in session.commands)
        normalized_counts = Counter(row.normalized_sha256 for row in session.commands)
        row: dict[str, Any] = {
            "source": session.source,
            "member": session.member,
            "session_id": session.session_id,
            "root_session_id": session.root_session_id,
            "parent_thread_id": session.parent_thread_id,
            "role": session.role,
            "role_class": session.role_class,
            "nickname": session.nickname,
            "agent_path": session.agent_path,
            "depth": session.depth,
            "model": session.model,
            "effort": session.effort,
            "cwd": session.cwd,
            "originator": session.originator,
            "cli_version": session.cli_version,
            "start": format_timestamp(session.first_ts),
            "end": format_timestamp(session.last_ts),
            "duration_s": round(session_duration_s(session), 3),
            "lines": session.lines,
            "json_errors": session.json_errors,
            "exec_blocks": session.exec_blocks,
            "shell_commands": session.shell_commands,
            "patch_calls": session.patch_calls,
            "patch_paths": session.patch_paths,
            "compactions": session.compactions,
            "task_starts": session.task_starts,
            "task_completes": session.task_completes,
            "agent_messages": session.agent_messages,
            "final_message_chars": session.final_message_chars,
            "input_tokens": session.token_usage.get("input_tokens", 0),
            "cached_input_tokens": session.token_usage.get("cached_input_tokens", 0),
            "cache_write_input_tokens": session.token_usage.get("cache_write_input_tokens", 0),
            "output_tokens": session.token_usage.get("output_tokens", 0),
            "reasoning_output_tokens": session.token_usage.get("reasoning_output_tokens", 0),
            "total_tokens": session.token_usage.get("total_tokens", 0),
            "exact_duplicate_shell_commands": sum(max(0, x - 1) for x in exact_counts.values()),
            "normalized_duplicate_shell_commands": sum(max(0, x - 1) for x in normalized_counts.values()),
        }
        for name in function_names:
            row[f"func_{name}"] = session.functions.get(name, 0)
        for name in category_names:
            row[f"cat_{name}"] = session.categories.get(name, 0)
        rows.append(row)
    write_csv(path, fields, rows)


def write_commands_csv(path: Path, commands: Sequence[CommandRow], mode: str, config: Mapping[str, Any]) -> None:
    fields = [
        "source",
        "member",
        "timestamp",
        "session_id",
        "role",
        "role_class",
        "agent_path",
        "call_id",
        "custom_tool_name",
        "internal_tool",
        "internal_index",
        "command",
        "command_sha256",
        "normalized_sha256",
        "categories",
        "skills",
        "output_chars",
        "output_exit_code",
        "output_truncated",
    ]
    rows = []
    for row in commands:
        rows.append(
            {
                **row.__dict__,
                "command": command_for_export(row.command_full, mode, config),
                "categories": row.categories,
                "skills": row.skills,
            }
        )
    write_csv(path, fields, rows)


def write_functions_csv(path: Path, rows: Sequence[FunctionRow]) -> None:
    fields = [
        "source",
        "member",
        "timestamp",
        "session_id",
        "role",
        "role_class",
        "agent_path",
        "call_id",
        "namespace",
        "name",
        "task_name",
        "arguments_json",
    ]
    write_csv(path, fields, (row.__dict__ for row in rows))


def write_patches_csv(path: Path, rows: Sequence[PatchRow]) -> None:
    fields = ["source", "member", "timestamp", "session_id", "role", "role_class", "call_id", "path", "change_type", "success"]
    write_csv(path, fields, (row.__dict__ for row in rows))


def write_skill_reads_csv(path: Path, rows: Sequence[SkillReadRow]) -> None:
    fields = [
        "source",
        "member",
        "timestamp",
        "session_id",
        "role",
        "role_class",
        "call_id",
        "skill",
        "command_sha256",
        "output_chars_allocated",
        "output_chars_call_total",
        "read_index_in_call",
        "reads_in_call",
        "repeated_in_session",
    ]
    write_csv(path, fields, (row.__dict__ for row in rows))


def write_role_summary_csv(path: Path, sessions: Sequence[SessionState]) -> None:
    grouped: dict[str, list[SessionState]] = defaultdict(list)
    for session in sessions:
        grouped[session.role].append(session)
    fields = [
        "role",
        "role_class",
        "sessions",
        "summed_duration_s",
        "exec_blocks",
        "shell_commands",
        "patch_paths",
        "compactions",
        "skill_reads",
        "total_tokens",
        "spawn_agent",
        "followup_task",
        "wait_agent",
        "list_agents",
        "send_message",
    ]
    rows = []
    for role, group in sorted(grouped.items()):
        rows.append(
            {
                "role": role,
                "role_class": group[0].role_class if group else "unknown",
                "sessions": len(group),
                "summed_duration_s": round(sum(session_duration_s(s) for s in group), 3),
                "exec_blocks": sum(s.exec_blocks for s in group),
                "shell_commands": sum(s.shell_commands for s in group),
                "patch_paths": sum(s.patch_paths for s in group),
                "compactions": sum(s.compactions for s in group),
                "skill_reads": sum(len(s.skill_reads) for s in group),
                "total_tokens": sum(s.token_usage.get("total_tokens", 0) for s in group),
                "spawn_agent": sum(s.functions.get("spawn_agent", 0) for s in group),
                "followup_task": sum(s.functions.get("followup_task", 0) for s in group),
                "wait_agent": sum(s.functions.get("wait_agent", 0) for s in group),
                "list_agents": sum(s.functions.get("list_agents", 0) for s in group),
                "send_message": sum(s.functions.get("send_message", 0) for s in group),
            }
        )
    write_csv(path, fields, rows)


def write_category_summary_csv(path: Path, commands: Sequence[CommandRow], descriptions: Mapping[str, str]) -> None:
    grouped: dict[str, list[CommandRow]] = defaultdict(list)
    for row in commands:
        for category in row.categories:
            grouped[category].append(row)
    fields = ["category", "description", "commands", "sessions", "roles", "output_chars", "nonzero_exit_calls", "sample_command_sha256"]
    rows = []
    for category in sorted(descriptions):
        group = grouped.get(category, [])
        rows.append(
            {
                "category": category,
                "description": descriptions.get(category, ""),
                "commands": len(group),
                "sessions": len({x.session_key for x in group}),
                "roles": len({x.role for x in group}),
                "output_chars": sum(x.output_chars for x in group),
                "nonzero_exit_calls": sum(1 for x in group if x.output_exit_code not in (None, 0)),
                "sample_command_sha256": group[0].command_sha256 if group else "",
            }
        )
    write_csv(path, fields, rows)


def write_structured_event_summary_csv(path: Path, report: Mapping[str, Any]) -> None:
    counts = report.get("structured_event_counts", {})
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["event", "count"])
        writer.writeheader()
        for name, count in sorted(counts.items()):
            writer.writerow({"event": name, "count": count})


def write_tool_summary_csv(path: Path, sessions: Sequence[SessionState], functions: Sequence[FunctionRow]) -> None:
    internal = Counter()
    for session in sessions:
        internal.update(session.internal_tools)
    function_counts = Counter(row.name for row in functions)
    rows = []
    for name, count in sorted(internal.items()):
        rows.append({"tool_kind": "internal", "name": name, "calls": count})
    for name, count in sorted(function_counts.items()):
        rows.append({"tool_kind": "collaboration_function", "name": name, "calls": count})
    write_csv(path, ["tool_kind", "name", "calls"], rows)


def write_duplicate_commands_csv(path: Path, commands: Sequence[CommandRow], mode: str, config: Mapping[str, Any]) -> None:
    grouped: dict[str, list[CommandRow]] = defaultdict(list)
    for row in commands:
        grouped[row.normalized_sha256].append(row)
    fields = [
        "normalized_sha256",
        "occurrences",
        "sessions",
        "roles",
        "first_timestamp",
        "command",
        "exact_variants",
        "categories",
    ]
    rows = []
    for digest, group in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        if len(group) < 2:
            continue
        command = group[0].command_full
        rows.append(
            {
                "normalized_sha256": digest,
                "occurrences": len(group),
                "sessions": len({x.session_key for x in group}),
                "roles": sorted({x.role for x in group}),
                "first_timestamp": min((x.timestamp for x in group), default=""),
                "command": command_for_export(command, mode, config),
                "exact_variants": len({x.command_sha256 for x in group}),
                "categories": sorted({category for x in group for category in x.categories}),
            }
        )
    write_csv(path, fields, rows)


def write_warnings_csv(path: Path, warnings: Sequence[WarningRecord]) -> None:
    write_csv(path, ["source", "line", "kind", "detail"], (row.__dict__ for row in warnings))


def render_summary_markdown(report: Mapping[str, Any], sessions: Sequence[SessionState], skill_reads: Sequence[SkillReadRow]) -> str:
    metrics = report["metrics"]
    lines: list[str] = [
        f"# {report['label']} — Codex JSONL analysis",
        "",
        f"Generated by `bbk-jsonl-analyzer` {report['analyzer']['version']} at {report['generated_at']}.",
        "",
        "## Run summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    key_metrics = [
        ("Sessions", metrics.get("sessions", 0)),
        ("Campaign span", format_duration(metrics.get("campaign_span_seconds", 0))),
        ("JSONL lines", metrics.get("jsonl_lines", 0)),
        ("Custom tool execution blocks", metrics.get("exec_blocks", 0)),
        ("Direct shell calls", metrics.get("direct_shell_commands", 0)),
        ("Patch-path events", metrics.get("patch_path_events", 0)),
        ("Context compactions", metrics.get("context_compactions", 0)),
        ("Skill-read shell calls", metrics.get("skill_read_commands", 0)),
        ("Handoff verify calls", metrics.get("category_handoff_verify", 0)),
        ("Handoff create calls", metrics.get("category_handoff_create", 0)),
        ("Schema validation calls", metrics.get("category_schema_validate", 0)),
        ("Repository validator calls", metrics.get("category_repo_validator", 0)),
        ("Exact duplicate shell calls", metrics.get("exact_duplicate_shell_commands", 0)),
        ("Total tokens across sessions", metrics.get("tokens_total_tokens", 0)),
        ("Parser warnings", metrics.get("warnings", 0)),
    ]
    lines.extend(f"| {name} | {format_number(value)} |" for name, value in key_metrics)

    lines.extend(["", "## Role distribution", "", "| Class | Sessions |", "|---|---:|"])
    for name, count in sorted(report.get("role_class_counts", {}).items()):
        lines.append(f"| {name} | {count} |")

    role_duration = Counter()
    role_shell = Counter()
    role_exec = Counter()
    for session in sessions:
        role_duration[session.role] += session_duration_s(session)
        role_shell[session.role] += session.shell_commands
        role_exec[session.role] += session.exec_blocks
    lines.extend(["", "## Highest-cost roles", "", "| Role | Sessions | Summed duration | Shell calls | Exec blocks |", "|---|---:|---:|---:|---:|"])
    session_counts = Counter(s.role for s in sessions)
    for role, seconds in role_duration.most_common(12):
        lines.append(f"| {role} | {session_counts[role]} | {format_duration(seconds)} | {role_shell[role]} | {role_exec[role]} |")

    skill_group: dict[str, list[SkillReadRow]] = defaultdict(list)
    for row in skill_reads:
        skill_group[row.skill].append(row)
    lines.extend(["", "## Skill-file reads", "", "| Skill | Read events | Sessions | Allocated output chars |", "|---|---:|---:|---:|"])
    if skill_group:
        for skill, group in sorted(skill_group.items(), key=lambda item: (-len(item[1]), item[0]))[:20]:
            lines.append(f"| {skill} | {len(group)} | {len({x.session_key for x in group})} | {sum(x.output_chars_allocated for x in group)} |")
    else:
        lines.append("| _None detected_ | 0 | 0 | 0 |")

    lines.extend(["", "## Heuristic indicators", ""])
    for signal in report.get("signals", []):
        lines.append(f"- **{signal['severity']} — {signal['code']}:** {signal['message']}")

    lines.extend(
        [
            "",
            "## Methodology and privacy",
            "",
            *[f"- **{key}:** {value}" for key, value in report.get("methodology", {}).items()],
            "",
            "The indicators above are diagnostic heuristics, not correctness findings. Raw message bodies and raw tool outputs are not copied into the report set.",
            "",
            "## Generated files",
            "",
            "- `summary.json` and `summary.md`",
            "- `sessions.csv`",
            "- `commands.csv`",
            "- `function_calls.csv`",
            "- `patches.csv`",
            "- `skill_reads.csv`",
            "- `role_summary.csv`",
            "- `category_summary.csv`",
            "- `tool_summary.csv`",
            "- `duplicate_commands.csv`",
            "- `warnings.csv`",
            "",
        ]
    )
    return "\n".join(lines)


def format_number(value: Any) -> str:
    if isinstance(value, float):
        if math.isfinite(value):
            return f"{value:,.3f}".rstrip("0").rstrip(".")
        return str(value)
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def format_duration(seconds: Any) -> str:
    try:
        seconds_float = float(seconds)
    except (TypeError, ValueError):
        return str(seconds)
    hours, rem = divmod(int(round(seconds_float)), 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def load_config(path: str | None) -> dict[str, Any]:
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    if not path:
        return config
    override = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    deep_merge(config, override)
    return config


def deep_merge(base: MutableMapping[str, Any], override: Mapping[str, Any]) -> None:
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(base.get(key), MutableMapping):
            deep_merge(base[key], value)
        else:
            base[key] = value


def flatten_metrics(summary: Mapping[str, Any]) -> dict[str, float]:
    metrics = summary.get("metrics", {})
    result: dict[str, float] = {}
    if isinstance(metrics, Mapping):
        for key, value in metrics.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                result[key] = float(value)
    for section_name in ("role_class_counts", "role_counts", "function_counts", "category_counts"):
        section = summary.get(section_name, {})
        if isinstance(section, Mapping):
            for key, value in section.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    result[f"{section_name}.{key}"] = float(value)
    return result


def load_summary(path_text: str) -> dict[str, Any]:
    path = Path(path_text)
    if path.is_dir():
        path = path / "summary.json"
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_comparison(before_path: str, after_path: str, output_dir: Path, before_label: str | None, after_label: str | None) -> dict[str, Any]:
    before = load_summary(before_path)
    after = load_summary(after_path)
    before_label = before_label or str(before.get("label") or "before")
    after_label = after_label or str(after.get("label") or "after")
    before_metrics = flatten_metrics(before)
    after_metrics = flatten_metrics(after)
    keys = sorted(set(before_metrics) | set(after_metrics))
    rows = []
    for key in keys:
        old = before_metrics.get(key, 0.0)
        new = after_metrics.get(key, 0.0)
        delta = new - old
        percent = None if old == 0 else delta / old * 100.0
        rows.append(
            {
                "metric": key,
                before_label: old,
                after_label: new,
                "delta": delta,
                "percent_change": percent,
            }
        )
    result = {
        "schema": "bbk.codex-jsonl-comparison.v1",
        "analyzer": {"name": "bbk-jsonl-analyzer", "version": VERSION},
        "generated_at": format_timestamp(datetime.now(timezone.utc)),
        "before": {"label": before_label, "source": before_path},
        "after": {"label": after_label, "source": after_path},
        "rows": rows,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "comparison.json", result)
    fields = ["metric", before_label, after_label, "delta", "percent_change"]
    write_csv(output_dir / "comparison.csv", fields, rows)
    lines = [
        f"# Codex JSONL comparison: {before_label} → {after_label}",
        "",
        "| Metric | Before | After | Delta | Change |",
        "|---|---:|---:|---:|---:|",
    ]
    priority = [
        "sessions",
        "campaign_span_hours",
        "direct_shell_commands",
        "exec_blocks",
        "patch_path_events",
        "context_compactions",
        "skill_read_commands",
        "category_handoff_verify",
        "category_handoff_create",
        "category_schema_validate",
        "category_repo_validator",
        "function_wait_agent",
        "function_list_agents",
        "function_send_message",
        "role_class_planning_design_research_sessions",
        "role_class_assurance_sessions",
        "role_class_execution_sessions",
    ]
    row_by_key = {row["metric"]: row for row in rows}
    ordered = [key for key in priority if key in row_by_key]
    ordered += [key for key in keys if key not in ordered]
    for key in ordered:
        row = row_by_key[key]
        pct = "n/a" if row["percent_change"] is None else f"{row['percent_change']:+.1f}%"
        lines.append(
            f"| {key} | {format_number(row[before_label])} | {format_number(row[after_label])} | {format_number(row['delta'])} | {pct} |"
        )
    (output_dir / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return result


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bbk-jsonl-analyzer",
        description="Analyze Codex rollout JSONL files, directories, or ZIP archives without third-party dependencies.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze", help="Analyze one corpus and write reports.")
    analyze.add_argument("inputs", nargs="+", help="JSONL file, directory, or ZIP archive. Multiple inputs are allowed.")
    analyze.add_argument("-o", "--output", required=True, help="Output directory.")
    analyze.add_argument("--label", default="analysis", help="Human-readable report label.")
    analyze.add_argument("--config", help="Optional JSON configuration override.")
    analyze.add_argument(
        "--command-text",
        choices=["redacted", "full", "hash-only", "none"],
        default="redacted",
        help="How commands are written to CSV reports. Parsing always uses the full in-memory text.",
    )

    compare = subparsers.add_parser("compare", help="Compare two summary.json reports or report directories.")
    compare.add_argument("before", help="Before summary.json or report directory.")
    compare.add_argument("after", help="After summary.json or report directory.")
    compare.add_argument("-o", "--output", required=True, help="Comparison output directory.")
    compare.add_argument("--before-label")
    compare.add_argument("--after-label")

    init_config = subparsers.add_parser("init-config", help="Write the default analyzer configuration.")
    init_config.add_argument("path", help="Destination JSON path.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        if args.command == "init-config":
            path = Path(args.path)
            path.parent.mkdir(parents=True, exist_ok=True)
            write_json(path, DEFAULT_CONFIG)
            print(path)
            return 0
        if args.command == "compare":
            write_comparison(args.before, args.after, Path(args.output), args.before_label, args.after_label)
            print(Path(args.output).resolve())
            return 0
        if args.command == "analyze":
            config = load_config(args.config)
            analyzer = Analyzer(config=config, command_text_mode=args.command_text)
            analyzer.analyze_sources(discover_sources(args.inputs))
            report = analyzer.write_report(Path(args.output), args.label)
            metrics = report["metrics"]
            print(f"Wrote {Path(args.output).resolve()}")
            print(
                f"sessions={metrics['sessions']} shell_calls={metrics['direct_shell_commands']} "
                f"exec_blocks={metrics['exec_blocks']} warnings={metrics['warnings']}"
            )
            return 0
    except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
