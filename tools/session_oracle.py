#!/usr/bin/env python3
"""Build and verify the anonymized Alpha.16 Session Inspector oracle fixture.

The raw OMP HTML export is authoritative.  The derived analyzer JSON is treated
as a secondary observation that may be incomplete or contradictory.  This tool
never evaluates embedded HTML or prompt content.  It decodes only the exact
``script#session-data`` base64 payload, retains hashes and structural facts, and
emits a compact fixture that excludes raw prompts, task prose, paths, session
identifiers, provider response identifiers, credentials, and API keys.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from gate_kernel import canonical_digest
except ImportError:  # pragma: no cover - installed-package import fallback
    from .gate_kernel import canonical_digest

MAX_SOURCE_BYTES = 128 * 1024 * 1024
SCRIPT_RE = re.compile(
    rb'<script\s+id=["\']session-data["\']\s+type=["\']application/json["\']\s*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
SAFE_LABEL_RE = re.compile(r"[^a-z0-9]+")
CAMEL_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
COST_QUANTUM = Decimal("0.000000000001")
RESPONSE_ID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
PROMPT_RECEIPT_TYPE = "bbk-effective-prompt-receipt"
TOOL_CALL_TYPE = "toolCall"
MANIFEST_SCHEMA = "bbk.session-inspector-oracle-manifest.v1"
CONTRADICTION_SCHEMA = "bbk.session-inspector-contradictions.v1"
VERIFICATION_SCHEMA = "bbk.session-inspector-oracle-verification.v1"
FIXTURE_ID = "session-inspector-alpha16-source-oracle"

TOKEN_FIELDS = (
    "input",
    "output",
    "cacheRead",
    "cacheWrite",
    "totalTokens",
    "reasoningTokens",
)
COST_FIELDS = ("input", "output", "cacheRead", "cacheWrite", "total")


class SessionOracleError(RuntimeError):
    """The source fixture is malformed, unsafe, or inconsistent."""

    def __init__(self, code: str, message: str, *, smallest_next_action: str = ""):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.smallest_next_action = smallest_next_action or (
            "Provide the exact immutable source export and derived analysis, then retry."
        )


def _sha256_bytes(value: bytes, *, prefixed: bool = True) -> str:
    digest = hashlib.sha256(value).hexdigest()
    return f"sha256:{digest}" if prefixed else digest


def _identity_digest(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise SessionOracleError("SESSION_IDENTITY_INVALID", "source identity is missing")
    return _sha256_bytes(value.encode("utf-8"))


def _slug(value: str) -> str:
    separated = CAMEL_BOUNDARY_RE.sub("-", value.strip())
    slug = SAFE_LABEL_RE.sub("-", separated.lower()).strip("-")
    if not slug:
        raise SessionOracleError("SESSION_LABEL_INVALID", "session/task label cannot be normalized")
    return slug


def _read_immutable_file(path: str | Path, *, label: str) -> tuple[Path, bytes]:
    selected = Path(path)
    if not selected.is_file():
        raise SessionOracleError("SOURCE_NOT_FOUND", f"{label} is not a regular file: {selected}")
    if selected.is_symlink():
        raise SessionOracleError("SOURCE_SYMLINK_REJECTED", f"{label} must not be a symlink: {selected}")
    try:
        size = selected.stat().st_size
    except OSError as exc:
        raise SessionOracleError("SOURCE_READ_FAILED", f"cannot stat {label}: {exc}") from exc
    if size > MAX_SOURCE_BYTES:
        raise SessionOracleError(
            "SOURCE_TOO_LARGE",
            f"{label} is {size} bytes; maximum is {MAX_SOURCE_BYTES}",
        )
    try:
        return selected.resolve(), selected.read_bytes()
    except OSError as exc:
        raise SessionOracleError("SOURCE_READ_FAILED", f"cannot read {label}: {exc}") from exc


def _json_load(value: bytes, *, label: str) -> Any:
    try:
        return json.loads(value.decode("utf-8"), parse_float=Decimal)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SessionOracleError("SOURCE_JSON_INVALID", f"{label} is not valid UTF-8 JSON: {exc}") from exc


def decode_session_export(path: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Decode one OMP HTML export without executing embedded content."""
    selected, raw = _read_immutable_file(path, label="session export")
    matches = SCRIPT_RE.findall(raw)
    if len(matches) != 1:
        raise SessionOracleError(
            "SESSION_DATA_SCRIPT_INVALID",
            f"expected exactly one script#session-data payload, found {len(matches)}",
        )
    encoded = re.sub(rb"\s+", b"", matches[0])
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SessionOracleError("SESSION_DATA_BASE64_INVALID", f"embedded session data is invalid: {exc}") from exc
    value = _json_load(decoded, label="decoded session payload")
    if not isinstance(value, dict):
        raise SessionOracleError("SESSION_EXPORT_INVALID", "decoded session payload must be an object")
    metadata = {
        "logical_name": "alpha16-session-export.html",
        "sha256": _sha256_bytes(raw),
        "byte_count": len(raw),
        "decoded_payload_sha256": _sha256_bytes(decoded),
        "decoded_byte_count": len(decoded),
        "raw_content_retained": False,
        "source_path_retained": False,
    }
    # Do not leak the local path through returned data.
    del selected
    return value, metadata


def load_derived_analysis(path: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    selected, raw = _read_immutable_file(path, label="derived analysis")
    value = _json_load(raw, label="derived analysis")
    if not isinstance(value, dict):
        raise SessionOracleError("DERIVED_ANALYSIS_INVALID", "derived analysis must be an object")
    metadata = {
        "logical_name": "alpha16-derived-analysis.json",
        "sha256": _sha256_bytes(raw),
        "byte_count": len(raw),
        "truth_status": "INCOMPLETE_SECONDARY",
        "raw_content_retained": False,
        "source_path_retained": False,
    }
    del selected
    return value, metadata


def _timestamp(value: Any, *, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise SessionOracleError("TIMESTAMP_INVALID", f"{label} is missing")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SessionOracleError("TIMESTAMP_INVALID", f"{label} is invalid: {value}") from exc


def _offset_ms(value: Any, origin: datetime, *, label: str) -> int:
    return round((_timestamp(value, label=label) - origin).total_seconds() * 1000)


def _mapping(value: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SessionOracleError("SESSION_EXPORT_INVALID", f"{label} must be an object")
    return value


def _entries(session: Mapping[str, Any], *, label: str) -> list[Mapping[str, Any]]:
    raw = session.get("entries")
    if not isinstance(raw, list):
        raise SessionOracleError("SESSION_EXPORT_INVALID", f"{label}.entries must be an array")
    result: list[Mapping[str, Any]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise SessionOracleError("SESSION_EXPORT_INVALID", f"{label}.entries[{index}] must be an object")
        result.append(item)
    return result


def _tool_calls(entries: Iterable[Mapping[str, Any]]) -> Iterable[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    for entry in entries:
        if entry.get("type") != "message":
            continue
        message = entry.get("message")
        if not isinstance(message, Mapping) or message.get("role") != "assistant":
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if isinstance(item, Mapping) and item.get("type") == TOOL_CALL_TYPE:
                yield entry, item


def _tool_results(entries: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for entry in entries:
        if entry.get("type") != "message":
            continue
        message = entry.get("message")
        if not isinstance(message, Mapping) or message.get("role") != "toolResult":
            continue
        call_id = message.get("toolCallId")
        if isinstance(call_id, str) and call_id:
            result[call_id] = entry
    return result


def _prompt_receipts(entries: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [
        entry
        for entry in entries
        if entry.get("type") in {"custom", "custom_message"}
        and entry.get("customType") == PROMPT_RECEIPT_TYPE
        and isinstance(entry.get("data"), Mapping)
    ]


def _usage(entries: Iterable[Mapping[str, Any]]) -> tuple[int, dict[str, int], dict[str, Decimal], set[str], Counter[tuple[str, str]]]:
    response_count = 0
    tokens = {field: 0 for field in TOKEN_FIELDS}
    costs = {field: Decimal("0") for field in COST_FIELDS}
    response_ids: set[str] = set()
    models: Counter[tuple[str, str]] = Counter()
    for entry in entries:
        if entry.get("type") != "message":
            continue
        message = entry.get("message")
        if not isinstance(message, Mapping) or message.get("role") != "assistant":
            continue
        usage = message.get("usage")
        if not isinstance(usage, Mapping):
            continue
        response_count += 1
        provider = str(message.get("provider") or "unknown")
        model = str(message.get("model") or "unknown")
        models[(provider, model)] += 1
        response_id = message.get("responseId")
        if isinstance(response_id, str) and RESPONSE_ID_RE.fullmatch(response_id):
            response_ids.add(response_id)
        for field in TOKEN_FIELDS:
            raw = usage.get(field) or 0
            if not isinstance(raw, int) or isinstance(raw, bool):
                raise SessionOracleError("USAGE_INVALID", f"usage.{field} must be an integer")
            tokens[field] += raw
        cost = usage.get("cost")
        if not isinstance(cost, Mapping):
            continue
        for field in COST_FIELDS:
            raw = cost.get(field) or Decimal("0")
            try:
                costs[field] += raw if isinstance(raw, Decimal) else Decimal(str(raw))
            except (InvalidOperation, ValueError) as exc:
                raise SessionOracleError("USAGE_INVALID", f"usage.cost.{field} is invalid") from exc
    return response_count, tokens, costs, response_ids, models


def _decimal_text(value: Decimal) -> str:
    rounded = value.quantize(COST_QUANTUM, rounding=ROUND_HALF_EVEN)
    if rounded == 0:
        return "0"
    normalized = format(rounded.normalize(), "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized


def _token_output(tokens: Mapping[str, int]) -> dict[str, int]:
    return {
        "input": int(tokens["input"]),
        "output": int(tokens["output"]),
        "cache_read": int(tokens["cacheRead"]),
        "cache_write": int(tokens["cacheWrite"]),
        "reasoning": int(tokens["reasoningTokens"]),
        "total": int(tokens["totalTokens"]),
    }


def _cost_output(costs: Mapping[str, Decimal]) -> dict[str, str]:
    return {
        "input_usd": _decimal_text(costs["input"]),
        "output_usd": _decimal_text(costs["output"]),
        "cache_read_usd": _decimal_text(costs["cacheRead"]),
        "cache_write_usd": _decimal_text(costs["cacheWrite"]),
        "total_usd": _decimal_text(costs["total"]),
    }


def _session_role(entries: Iterable[Mapping[str, Any]], *, default: str) -> str:
    for receipt in _prompt_receipts(entries):
        data = receipt["data"]
        if data.get("phase") == "before_agent_start" and isinstance(data.get("role"), str):
            return str(data["role"])
    return default


def _structural_digest(entries: Iterable[Mapping[str, Any]]) -> str:
    structural = [
        {
            "id_sha256": _identity_digest(str(entry.get("id", ""))),
            "parent_id_sha256": _identity_digest(str(entry["parentId"])) if entry.get("parentId") else None,
            "type": str(entry.get("type", "")),
            "timestamp": str(entry.get("timestamp", "")),
        }
        for entry in entries
    ]
    return f"sha256:{canonical_digest(structural)}"


def _session_records(export: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Mapping[str, Any]], datetime]:
    main_header = _mapping(export.get("header"), label="header")
    origin = _timestamp(main_header.get("timestamp"), label="header.timestamp")
    raw_subsessions = export.get("subSessions") or {}
    if not isinstance(raw_subsessions, Mapping):
        raise SessionOracleError("SESSION_EXPORT_INVALID", "subSessions must be an object")

    source_sessions: list[tuple[str, Mapping[str, Any]]] = [("Main", export)]
    for name, session in raw_subsessions.items():
        if not isinstance(name, str) or not isinstance(session, Mapping):
            raise SessionOracleError("SESSION_EXPORT_INVALID", "subSessions entries must be named objects")
        source_sessions.append((name, session))
    def child_timestamp(item: tuple[str, Mapping[str, Any]]) -> datetime:
        name, session = item
        header = _mapping(session.get("header"), label=f"subSessions.{name}.header")
        return _timestamp(
            header.get("timestamp"),
            label=f"subSessions.{name}.header.timestamp",
        )

    source_sessions[1:] = sorted(source_sessions[1:], key=child_timestamp)

    records: list[dict[str, Any]] = []
    aliases: dict[str, Mapping[str, Any]] = {}
    seen_aliases: set[str] = set()
    for index, (name, session) in enumerate(source_sessions):
        alias = "session:main" if index == 0 else f"session:{_slug(name)}"
        if alias in seen_aliases:
            raise SessionOracleError("SESSION_ALIAS_DUPLICATE", f"duplicate anonymized session alias {alias}")
        seen_aliases.add(alias)
        aliases[name] = session
        header = _mapping(session.get("header"), label=f"session {name}.header")
        entries = _entries(session, label=f"session {name}")
        response_count, tokens, costs, _, _ = _usage(entries)
        receipts = _prompt_receipts(entries)
        binding_receipts = sum(1 for item in receipts if item["data"].get("phase") == "before_agent_start")
        provider_receipts = sum(
            1
            for item in receipts
            if item["data"].get("phase") == "provider_request_finalization"
            and item["data"].get("status") == "VERIFIED"
            and item["data"].get("action") == "VERIFIED"
        )
        record = {
            "alias": alias,
            "label": "Main" if index == 0 else name,
            "role": _session_role(entries, default="Main" if index == 0 else "unknown"),
            "parent_alias": None if index == 0 else "session:main",
            "source_session_id_sha256": _identity_digest(header.get("id")),
            "start_offset_ms": _offset_ms(header.get("timestamp"), origin, label=f"session {name}.timestamp"),
            "entry_count": len(entries),
            "structural_digest": _structural_digest(entries),
            "provider_response_count": response_count,
            "tokens": _token_output(tokens),
            "costs": _cost_output(costs),
            "prompt_integrity": {
                "binding_receipts": binding_receipts,
                "provider_verified_receipts": provider_receipts,
                "total_receipts": len(receipts),
            },
        }
        records.append(record)
    return records, aliases, origin


def _task_records(main_entries: list[Mapping[str, Any]], sessions: list[dict[str, Any]], origin: datetime) -> list[dict[str, Any]]:
    child_alias_by_label = {item["label"]: item["alias"] for item in sessions if item["parent_alias"]}
    records: list[dict[str, Any]] = []
    for entry, call in _tool_calls(main_entries):
        if call.get("name") != "task":
            continue
        arguments = call.get("arguments")
        if not isinstance(arguments, Mapping):
            raise SessionOracleError("TASK_RECORD_INVALID", "task tool call arguments must be an object")
        tasks = arguments.get("tasks")
        if not isinstance(tasks, list) or not tasks:
            raise SessionOracleError("TASK_RECORD_INVALID", "task tool call must contain at least one task")
        for task in tasks:
            if not isinstance(task, Mapping):
                raise SessionOracleError("TASK_RECORD_INVALID", "task item must be an object")
            name = task.get("name")
            role = task.get("agent")
            assignment = task.get("task")
            if not isinstance(name, str) or not isinstance(role, str) or not isinstance(assignment, str):
                raise SessionOracleError("TASK_RECORD_INVALID", "task name, agent, and assignment must be strings")
            child_alias = child_alias_by_label.get(name)
            records.append(
                {
                    "alias": f"task:{_slug(name)}",
                    "name": name,
                    "agent_role": role,
                    "parent_session_alias": "session:main",
                    "child_session_alias": child_alias,
                    "observed_at": str(entry.get("timestamp")),
                    "invocation_offset_ms": _offset_ms(entry.get("timestamp"), origin, label=f"task {name}.timestamp"),
                    "source_tool_call_id_sha256": _identity_digest(call.get("id")),
                    "assignment_sha256": _sha256_bytes(assignment.encode("utf-8")),
                    "status": "CORRELATED" if child_alias else "UNRESOLVED",
                }
            )
    aliases = [item["alias"] for item in records]
    if len(aliases) != len(set(aliases)):
        raise SessionOracleError("TASK_ALIAS_DUPLICATE", "anonymized task aliases must be unique")
    return records


def _wait_records(main_entries: list[Mapping[str, Any]], origin: datetime) -> list[dict[str, Any]]:
    results = _tool_results(main_entries)
    records: list[dict[str, Any]] = []
    for entry, call in _tool_calls(main_entries):
        if call.get("name") != "ask":
            continue
        call_id = call.get("id")
        if not isinstance(call_id, str) or call_id not in results:
            raise SessionOracleError("ASK_WAIT_UNRESOLVED", "ask tool call has no correlated result")
        result_entry = results[call_id]
        start = _timestamp(entry.get("timestamp"), label="ask start timestamp")
        end = _timestamp(result_entry.get("timestamp"), label="ask result timestamp")
        duration_ms = round((end - start).total_seconds() * 1000)
        arguments = call.get("arguments") if isinstance(call.get("arguments"), Mapping) else {}
        questions = arguments.get("questions") if isinstance(arguments, Mapping) else []
        question_count = len(questions) if isinstance(questions, list) else 0
        records.append(
            {
                "alias": f"wait:ask-{len(records) + 1}",
                "mechanism": "ask",
                "source_tool_call_id_sha256": _identity_digest(call_id),
                "observed_at": str(entry.get("timestamp")),
                "start_offset_ms": round((start - origin).total_seconds() * 1000),
                "end_offset_ms": round((end - origin).total_seconds() * 1000),
                "duration_ms": duration_ms,
                "question_count": question_count,
                "correlation": "EXACT_TOOL_CALL_ID",
            }
        )
    return records


def _polling_counts(sessions: Mapping[str, Mapping[str, Any]]) -> dict[str, int]:
    inclusive = Counter()
    main = Counter()
    for name, session in sessions.items():
        for _, call in _tool_calls(_entries(session, label=f"session {name}")):
            tool_name = call.get("name")
            if tool_name in {"job", "irc"}:
                inclusive[str(tool_name)] += 1
                if name == "Main":
                    main[str(tool_name)] += 1
    return {
        "main_job_calls": main["job"],
        "main_irc_calls": main["irc"],
        "main_total": main["job"] + main["irc"],
        "inclusive_job_calls": inclusive["job"],
        "inclusive_irc_calls": inclusive["irc"],
        "inclusive_total": inclusive["job"] + inclusive["irc"],
    }


def build_source_manifest(export: Mapping[str, Any], source_metadata: Mapping[str, Any]) -> dict[str, Any]:
    sessions, session_values, origin = _session_records(export)
    main_entries = _entries(export, label="Main")
    tasks = _task_records(main_entries, sessions, origin)
    waits = _wait_records(main_entries, origin)

    all_entries: list[Mapping[str, Any]] = []
    response_ids: set[str] = set()
    aggregate_tokens = {field: 0 for field in TOKEN_FIELDS}
    aggregate_costs = {field: Decimal("0") for field in COST_FIELDS}
    model_counts: Counter[tuple[str, str]] = Counter()
    for session in session_values.values():
        entries = _entries(session, label="session")
        all_entries.extend(entries)
        _, tokens, costs, session_response_ids, session_models = _usage(entries)
        response_ids.update(session_response_ids)
        for field in TOKEN_FIELDS:
            aggregate_tokens[field] += tokens[field]
        for field in COST_FIELDS:
            aggregate_costs[field] += costs[field]
        model_counts.update(session_models)

    main_record = next(item for item in sessions if item["alias"] == "session:main")
    child_entries = sum(item["entry_count"] for item in sessions if item["parent_alias"])
    prompt_binding = sum(item["prompt_integrity"]["binding_receipts"] for item in sessions)
    prompt_verified = sum(item["prompt_integrity"]["provider_verified_receipts"] for item in sessions)
    prompt_total = sum(item["prompt_integrity"]["total_receipts"] for item in sessions)
    explicit_wait_total = sum(item["duration_ms"] for item in waits)
    unresolved_tasks = [item["alias"] for item in tasks if item["status"] != "CORRELATED"]
    if unresolved_tasks:
        raise SessionOracleError(
            "TASK_SESSION_CORRELATION_FAILED",
            f"task records do not resolve to child sessions: {', '.join(unresolved_tasks)}",
        )

    manifest: dict[str, Any] = {
        "schema": MANIFEST_SCHEMA,
        "fixture_id": FIXTURE_ID,
        "release_source": "0.1.0-alpha.16",
        "source_authority": "RAW_SESSION_EXPORT",
        "privacy": {
            "anonymized": True,
            "raw_prompts_retained": False,
            "raw_task_assignments_retained": False,
            "raw_paths_retained": False,
            "raw_session_ids_retained": False,
            "provider_response_ids_retained": False,
            "credentials_retained": False,
        },
        "sources": {
            "session_export": dict(source_metadata),
        },
        "interface_binding": {
            "interface_id": "IF-014",
            "host_version": "UNOBSERVED_IN_EXPORT",
            "host_version_provenance": "NOT_PRESENT_IN_SOURCE_EXPORT",
            "identity_source": "SESSION_TASK_AND_TOOL_CORRELATION",
            "provider_response_ids_are_agent_authority": False,
            "enforcement_boundary": "DETECT_ONLY",
        },
        "expected": {
            "session_count": len(sessions),
            "main_entry_count": main_record["entry_count"],
            "child_entry_count": child_entries,
            "inclusive_entry_count": len(all_entries),
            "task_invocation_count": len(tasks),
            "explicit_user_wait_count": len(waits),
            "explicit_user_wait_total_ms": explicit_wait_total,
            "provider_response_count": sum(item["provider_response_count"] for item in sessions),
            "provider_response_identity_count": len(response_ids),
            "prompt_binding_receipt_count": prompt_binding,
            "prompt_provider_verified_receipt_count": prompt_verified,
            "prompt_integrity_receipt_count": prompt_total,
            "polling_tool_calls": _polling_counts(session_values),
            "tokens": _token_output(aggregate_tokens),
            "costs": _cost_output(aggregate_costs),
        },
        "sessions": sessions,
        "tasks": tasks,
        "waits": waits,
        "models": [
            {
                "provider": provider,
                "model": model,
                "provider_response_count": count,
            }
            for (provider, model), count in sorted(model_counts.items())
        ],
        "host_events": [
            *[
                {
                    "schema": "bbk.host-event.v1",
                    "host_version": "UNOBSERVED_IN_EXPORT",
                    "event_type": "task-spawn-observed",
                    "session_id": item["child_session_alias"],
                    "task_or_tool_id": item["alias"],
                    "parent_session": item["parent_session_alias"],
                    "payload_digest": item["assignment_sha256"],
                    "observed_at": item["observed_at"],
                    "normalized_identity": {
                        "task_alias": item["alias"],
                        "agent_role": item["agent_role"],
                        "child_session_alias": item["child_session_alias"],
                    },
                    "correlation": {
                        "method": "TASK_NAME_TO_SUBSESSION_LABEL",
                        "status": item["status"],
                    },
                    "event_class": "task-lifecycle",
                    "enforcement_boundary": "DETECT_ONLY",
                }
                for item in tasks
            ],
            *[
                {
                    "schema": "bbk.host-event.v1",
                    "host_version": "UNOBSERVED_IN_EXPORT",
                    "event_type": "user-wait-observed",
                    "session_id": "session:main",
                    "task_or_tool_id": item["alias"],
                    "parent_session": "",
                    "payload_digest": item["source_tool_call_id_sha256"],
                    "observed_at": item["observed_at"],
                    "normalized_identity": {
                        "wait_alias": item["alias"],
                        "mechanism": item["mechanism"],
                    },
                    "correlation": {
                        "method": item["correlation"],
                        "duration_ms": item["duration_ms"],
                    },
                    "event_class": "user-wait",
                    "enforcement_boundary": "DETECT_ONLY",
                }
                for item in waits
            ],
        ],
        "positive_oracles": [
            {
                "id": "SOURCE_SESSION_CONSERVATION",
                "status": "PASS",
                "observed": len(all_entries),
                "expected": sum(item["entry_count"] for item in sessions),
            },
            {
                "id": "TASK_SESSION_CORRELATION",
                "status": "PASS",
                "observed": sum(1 for item in tasks if item["status"] == "CORRELATED"),
                "expected": len(tasks),
            },
            {
                "id": "EXPLICIT_ASK_WAIT_CORRELATION",
                "status": "PASS",
                "observed": len(waits),
                "expected": len(waits),
            },
            {
                "id": "PROMPT_INTEGRITY_CONSERVATION",
                "status": "PASS",
                "observed": prompt_total,
                "expected": prompt_binding + prompt_verified,
            },
            {
                "id": "PROVIDER_USAGE_CONSERVATION",
                "status": "PASS",
                "observed": sum(item["provider_response_count"] for item in sessions),
                "expected": len(response_ids),
            },
        ],
    }
    manifest["fixture_digest"] = f"sha256:{canonical_digest(manifest)}"
    return manifest


def _derived_grand_total(derived: Mapping[str, Any]) -> tuple[dict[str, int], dict[str, Decimal]]:
    totals = derived.get("totals")
    if not isinstance(totals, Mapping) or not isinstance(totals.get("grandTotal"), Mapping):
        raise SessionOracleError("DERIVED_ANALYSIS_INVALID", "totals.grandTotal is missing")
    grand = totals["grandTotal"]
    tokens: dict[str, int] = {}
    token_map = {
        "input": "inputTokens",
        "output": "outputTokens",
        "cacheRead": "cacheReadTokens",
        "cacheWrite": "cacheWriteTokens",
        "reasoningTokens": "reasoningTokens",
        "totalTokens": "totalTokens",
    }
    for target, source in token_map.items():
        raw = grand.get(source) or 0
        if not isinstance(raw, int) or isinstance(raw, bool):
            raise SessionOracleError("DERIVED_ANALYSIS_INVALID", f"totals.grandTotal.{source} must be an integer")
        tokens[target] = raw
    costs: dict[str, Decimal] = {}
    cost_map = {
        "input": "costInputUsd",
        "output": "costOutputUsd",
        "cacheRead": "costCacheReadUsd",
        "cacheWrite": "costCacheWriteUsd",
        "total": "costTotalUsd",
    }
    for target, source in cost_map.items():
        raw = grand.get(source) or Decimal("0")
        try:
            costs[target] = raw if isinstance(raw, Decimal) else Decimal(str(raw))
        except (InvalidOperation, ValueError) as exc:
            raise SessionOracleError("DERIVED_ANALYSIS_INVALID", f"totals.grandTotal.{source} is invalid") from exc
    return tokens, costs



def _contradiction_confirmed(item: Mapping[str, Any]) -> bool:
    if item.get("severity") != "BLOCKING":
        return False
    if item.get("id") == "PROVIDER_RESPONSE_IDS_MISIDENTIFIED_AS_AGENTS":
        return int(item.get("provider_response_ids_as_agents", 0)) > 0
    if item.get("id") == "EXPLICIT_ASK_WAIT_OMITTED":
        return int(item.get("missing_explicit_wait_count", 0)) > 0
    if item.get("id") == "INCLUSIVE_COST_UNDERCOUNTED":
        try:
            return Decimal(str(item.get("excluded_value_usd", "0"))) > 0
        except InvalidOperation:
            return False
    return int(item.get("delta", 0)) > 0

def build_contradictions(
    export: Mapping[str, Any],
    derived: Mapping[str, Any],
    manifest: Mapping[str, Any],
    derived_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    main_entries = _entries(export, label="Main")
    main_response_count, main_tokens, main_costs, main_response_ids, _ = _usage(main_entries)
    main_receipts = _prompt_receipts(main_entries)
    derived_entries = derived.get("entries")
    derived_agents = derived.get("agents")
    derived_waits = derived.get("waitIntervals")
    derived_bbk = derived.get("bbkEvents")
    if not isinstance(derived_entries, list) or not isinstance(derived_agents, list):
        raise SessionOracleError("DERIVED_ANALYSIS_INVALID", "entries and agents must be arrays")
    if not isinstance(derived_waits, list) or not isinstance(derived_bbk, list):
        raise SessionOracleError("DERIVED_ANALYSIS_INVALID", "waitIntervals and bbkEvents must be arrays")

    derived_tokens, derived_costs = _derived_grand_total(derived)
    derived_agent_ids = {
        str(item.get("agentId"))
        for item in derived_agents
        if isinstance(item, Mapping) and isinstance(item.get("agentId"), str)
    }
    response_ids_as_agents = len(main_response_ids & derived_agent_ids)
    pseudo_role_agents = sum(1 for value in derived_agent_ids if value.startswith("agent:"))
    derived_prompt_receipts = sum(
        1
        for item in derived_bbk
        if isinstance(item, Mapping) and item.get("customType") == PROMPT_RECEIPT_TYPE
    )
    derived_task_records = len(derived.get("tasks")) if isinstance(derived.get("tasks"), list) else 0

    waits = manifest["waits"]
    exact_wait_pairs = {
        (
            str(item.get("fromTs")),
            str(item.get("toTs")),
        )
        for item in derived_waits
        if isinstance(item, Mapping)
    }
    source_wait_pairs: set[tuple[str, str]] = set()
    # Reconstruct the exact source timestamps using call/result correlation.
    results = _tool_results(main_entries)
    for entry, call in _tool_calls(main_entries):
        if call.get("name") == "ask" and isinstance(call.get("id"), str) and call["id"] in results:
            source_wait_pairs.add((str(entry.get("timestamp")), str(results[call["id"]].get("timestamp"))))
    matching_waits = len(source_wait_pairs & exact_wait_pairs)

    source_cost = Decimal(str(manifest["expected"]["costs"]["total_usd"]))
    excluded_cost = source_cost - derived_costs["total"]
    source_sessions = int(manifest["expected"]["session_count"])
    source_tasks = int(manifest["expected"]["task_invocation_count"])
    source_entries = int(manifest["expected"]["inclusive_entry_count"])
    source_responses = int(manifest["expected"]["provider_response_count"])
    source_prompt_receipts = int(manifest["expected"]["prompt_integrity_receipt_count"])

    positive_controls = [
        {
            "id": "MAIN_ENTRY_COUNT_PRESERVED",
            "status": "PASS" if len(derived_entries) == len(main_entries) else "FAIL",
            "source_value": len(main_entries),
            "derived_value": len(derived_entries),
        },
        {
            "id": "MAIN_PROVIDER_USAGE_PRESERVED",
            "status": "PASS"
            if _token_output(main_tokens) == _token_output(derived_tokens)
            and _cost_output(main_costs) == _cost_output(derived_costs)
            else "FAIL",
            "source_provider_responses": main_response_count,
            "derived_total_tokens": _token_output(derived_tokens)["total"],
            "source_total_tokens": _token_output(main_tokens)["total"],
            "derived_cost_total_usd": _decimal_text(derived_costs["total"]),
            "source_cost_total_usd": _decimal_text(main_costs["total"]),
        },
        {
            "id": "MAIN_PROMPT_RECEIPTS_PRESERVED",
            "status": "PASS" if derived_prompt_receipts == len(main_receipts) else "FAIL",
            "source_value": len(main_receipts),
            "derived_value": derived_prompt_receipts,
        },
    ]

    contradictions = [
        {
            "id": "INCLUSIVE_ENTRIES_UNDERCOUNTED",
            "code": "DERIVED_SESSION_SCOPE_INCOMPLETE",
            "severity": "BLOCKING",
            "source_value": source_entries,
            "derived_value": len(derived_entries),
            "delta": source_entries - len(derived_entries),
        },
        {
            "id": "CHILD_SESSIONS_OMITTED",
            "code": "DERIVED_CHILD_SESSIONS_OMITTED",
            "severity": "BLOCKING",
            "source_value": source_sessions,
            "derived_value": 1,
            "delta": source_sessions - 1,
        },
        {
            "id": "PROVIDER_RESPONSE_IDS_MISIDENTIFIED_AS_AGENTS",
            "code": "DERIVED_AGENT_IDENTITY_CONTAMINATED",
            "severity": "BLOCKING",
            "source_valid_session_identities": source_sessions,
            "derived_agent_count": len(derived_agents),
            "provider_response_ids_as_agents": response_ids_as_agents,
            "pseudo_role_agents": pseudo_role_agents,
        },
        {
            "id": "TASK_RECORDS_OMITTED",
            "code": "DERIVED_TASK_TOPOLOGY_OMITTED",
            "severity": "BLOCKING",
            "source_value": source_tasks,
            "derived_value": derived_task_records,
            "delta": source_tasks - derived_task_records,
        },
        {
            "id": "EXPLICIT_ASK_WAIT_OMITTED",
            "code": "DERIVED_WAIT_SEMANTICS_INCORRECT",
            "severity": "BLOCKING",
            "source_explicit_wait_count": len(waits),
            "derived_wait_interval_count": len(derived_waits),
            "derived_matching_explicit_wait_count": matching_waits,
            "missing_explicit_wait_count": len(waits) - matching_waits,
        },
        {
            "id": "PROVIDER_RESPONSES_UNDERCOUNTED",
            "code": "DERIVED_PROVIDER_SCOPE_INCOMPLETE",
            "severity": "BLOCKING",
            "source_value": source_responses,
            "derived_value": main_response_count,
            "delta": source_responses - main_response_count,
        },
        {
            "id": "INCLUSIVE_COST_UNDERCOUNTED",
            "code": "DERIVED_COST_SCOPE_INCOMPLETE",
            "severity": "BLOCKING",
            "source_value_usd": _decimal_text(source_cost),
            "derived_value_usd": _decimal_text(derived_costs["total"]),
            "excluded_value_usd": _decimal_text(excluded_cost),
        },
        {
            "id": "CHILD_PROMPT_INTEGRITY_OMITTED",
            "code": "DERIVED_PROMPT_RECEIPT_SCOPE_INCOMPLETE",
            "severity": "BLOCKING",
            "source_value": source_prompt_receipts,
            "derived_value": derived_prompt_receipts,
            "delta": source_prompt_receipts - derived_prompt_receipts,
        },
    ]

    value: dict[str, Any] = {
        "schema": CONTRADICTION_SCHEMA,
        "fixture_id": f"{FIXTURE_ID}-derived-contradictions",
        "source_manifest_ref": str(manifest["fixture_digest"]),
        "derived_source": dict(derived_metadata),
        "truth_policy": {
            "authoritative_source": "RAW_SESSION_EXPORT",
            "derived_analysis_role": "SECONDARY_OBSERVATION",
            "derived_analysis_complete_truth": False,
        },
        "positive_controls": positive_controls,
        "contradictions": contradictions,
        "verdict": {
            "status": "NEGATIVE_ORACLE_CONFIRMED"
            if all(item["status"] == "PASS" for item in positive_controls)
            and all(_contradiction_confirmed(item) for item in contradictions)
            else "ORACLE_MISMATCH",
            "contradiction_count": len(contradictions),
            "derived_analysis_can_establish_complete_truth": False,
        },
    }
    value["fixture_digest"] = f"sha256:{canonical_digest(value)}"
    return value


def build_oracle(source_html: str | Path, derived_json: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    export, source_metadata = decode_session_export(source_html)
    derived, derived_metadata = load_derived_analysis(derived_json)
    manifest = build_source_manifest(export, source_metadata)
    manifest["sources"]["derived_analysis"] = dict(derived_metadata)
    # Recompute after binding both immutable source identities.
    manifest.pop("fixture_digest", None)
    manifest["fixture_digest"] = f"sha256:{canonical_digest(manifest)}"
    contradictions = build_contradictions(export, derived, manifest, derived_metadata)
    return manifest, contradictions


def _read_json_object(path: str | Path, *, label: str) -> dict[str, Any]:
    selected, raw = _read_immutable_file(path, label=label)
    value = _json_load(raw, label=label)
    if not isinstance(value, dict):
        raise SessionOracleError("FIXTURE_INVALID", f"{label} must be an object")
    del selected
    return value


def _verify_self_digest(value: Mapping[str, Any], *, label: str) -> None:
    expected = value.get("fixture_digest")
    if not isinstance(expected, str):
        raise SessionOracleError("FIXTURE_DIGEST_MISSING", f"{label}.fixture_digest is missing")
    copy = dict(value)
    copy.pop("fixture_digest", None)
    observed = f"sha256:{canonical_digest(copy)}"
    if observed != expected:
        raise SessionOracleError(
            "FIXTURE_DIGEST_MISMATCH",
            f"{label} digest mismatch: expected {expected}, observed {observed}",
        )


def verify_oracle(
    manifest: Mapping[str, Any],
    contradictions: Mapping[str, Any],
    *,
    source_html: str | Path | None = None,
    derived_json: str | Path | None = None,
) -> dict[str, Any]:
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise SessionOracleError("FIXTURE_SCHEMA_INVALID", f"manifest schema must be {MANIFEST_SCHEMA}")
    if contradictions.get("schema") != CONTRADICTION_SCHEMA:
        raise SessionOracleError("FIXTURE_SCHEMA_INVALID", f"contradiction schema must be {CONTRADICTION_SCHEMA}")
    _verify_self_digest(manifest, label="manifest")
    _verify_self_digest(contradictions, label="contradictions")
    if contradictions.get("source_manifest_ref") != manifest.get("fixture_digest"):
        raise SessionOracleError("FIXTURE_REFERENCE_MISMATCH", "contradictions do not bind the exact source manifest")

    expected = _mapping(manifest.get("expected"), label="manifest.expected")
    sessions = manifest.get("sessions")
    tasks = manifest.get("tasks")
    waits = manifest.get("waits")
    if not isinstance(sessions, list) or not isinstance(tasks, list) or not isinstance(waits, list):
        raise SessionOracleError(
            "FIXTURE_INVALID",
            "manifest sessions, tasks, and waits must be arrays",
        )
    inclusive_entries = sum(int(item["entry_count"]) for item in sessions)
    provider_responses = sum(int(item["provider_response_count"]) for item in sessions)
    prompt_receipts = sum(
        int(item["prompt_integrity"]["total_receipts"]) for item in sessions
    )
    positive_oracles = manifest.get("positive_oracles", [])
    checks = {
        "session_count": len(sessions) == expected.get("session_count"),
        "entry_conservation": inclusive_entries == expected.get("inclusive_entry_count"),
        "task_count": len(tasks) == expected.get("task_invocation_count"),
        "task_correlation": all(
            item.get("status") == "CORRELATED" and item.get("child_session_alias")
            for item in tasks
        ),
        "wait_count": len(waits) == expected.get("explicit_user_wait_count"),
        "wait_duration": sum(int(item["duration_ms"]) for item in waits)
        == expected.get("explicit_user_wait_total_ms"),
        "provider_response_count": provider_responses
        == expected.get("provider_response_count"),
        "prompt_receipt_count": prompt_receipts
        == expected.get("prompt_integrity_receipt_count"),
        "positive_oracles": isinstance(positive_oracles, list)
        and bool(positive_oracles)
        and all(item.get("status") == "PASS" for item in positive_oracles),
        "host_event_count": len(manifest.get("host_events", [])) == len(tasks) + len(waits),
        "host_event_identity": all(
            isinstance(item, Mapping)
            and item.get("schema") == "bbk.host-event.v1"
            and item.get("enforcement_boundary") == "DETECT_ONLY"
            for item in manifest.get("host_events", [])
        ),
        "negative_oracle": _mapping(
            contradictions.get("verdict"),
            label="contradictions.verdict",
        ).get("status")
        == "NEGATIVE_ORACLE_CONFIRMED",
    }

    regenerated = False
    if source_html is not None or derived_json is not None:
        if source_html is None or derived_json is None:
            raise SessionOracleError("SOURCE_PAIR_INCOMPLETE", "source HTML and derived JSON must be supplied together")
        rebuilt_manifest, rebuilt_contradictions = build_oracle(source_html, derived_json)
        checks["source_manifest_reproduced"] = rebuilt_manifest == dict(manifest)
        checks["contradictions_reproduced"] = rebuilt_contradictions == dict(contradictions)
        regenerated = True

    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "schema": VERIFICATION_SCHEMA,
        "fixture_id": manifest.get("fixture_id"),
        "status": status,
        "source_regenerated": regenerated,
        "checks": checks,
        "manifest_digest": manifest.get("fixture_digest"),
        "contradictions_digest": contradictions.get("fixture_digest"),
        "smallest_next_action": (
            "Proceed with the bound Alpha.17 qualification fixture."
            if status == "PASS"
            else "Rebuild the fixture from the exact immutable sources and inspect failed checks."
        ),
    }


def _write_json(path: str | Path, value: Mapping[str, Any]) -> None:
    selected = Path(path)
    selected.parent.mkdir(parents=True, exist_ok=True)
    selected.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="build anonymized fixtures from exact source files")
    build.add_argument("--source-html", required=True)
    build.add_argument("--derived-json", required=True)
    build.add_argument("--manifest-out", required=True)
    build.add_argument("--contradictions-out", required=True)

    verify = subparsers.add_parser("verify", help="verify checked-in fixtures and optionally reproduce from sources")
    verify.add_argument("--manifest", required=True)
    verify.add_argument("--contradictions", required=True)
    verify.add_argument("--source-html")
    verify.add_argument("--derived-json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "build":
            manifest, contradictions = build_oracle(args.source_html, args.derived_json)
            _write_json(args.manifest_out, manifest)
            _write_json(args.contradictions_out, contradictions)
            result = {
                "schema": "bbk.session-inspector-oracle-build.v1",
                "status": "PASS",
                "manifest": str(Path(args.manifest_out)),
                "contradictions": str(Path(args.contradictions_out)),
                "manifest_digest": manifest["fixture_digest"],
                "contradictions_digest": contradictions["fixture_digest"],
            }
        else:
            manifest = _read_json_object(args.manifest, label="manifest")
            contradictions = _read_json_object(args.contradictions, label="contradictions")
            result = verify_oracle(
                manifest,
                contradictions,
                source_html=args.source_html,
                derived_json=args.derived_json,
            )
        print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
        return 0 if result.get("status") == "PASS" else 1
    except SessionOracleError as exc:
        print(
            json.dumps(
                {
                    "schema": "bbk.session-inspector-oracle-error.v1",
                    "status": "BLOCKED",
                    "code": exc.code,
                    "message": exc.message,
                    "smallest_next_action": exc.smallest_next_action,
                },
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
