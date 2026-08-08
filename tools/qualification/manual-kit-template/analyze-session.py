#!/usr/bin/env python3
"""Classify an exported OMP manual-qualification session without executing it."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SESSION_RE = re.compile(
    r'<script\s+id=["\']session-data["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def decode_payload(raw: str) -> dict[str, Any]:
    text = raw.strip()
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass
    compact = re.sub(r"\s+", "", text)
    padding = "=" * ((4 - len(compact) % 4) % 4)
    failures: list[str] = []
    for decoder in (base64.b64decode, base64.urlsafe_b64decode):
        try:
            decoded = decoder(compact + padding)
            value = json.loads(decoded.decode("utf-8"))
            if isinstance(value, dict):
                return value
        except Exception as exc:  # noqa: BLE001 - diagnostic aggregation
            failures.append(str(exc))
    raise ValueError("session-data is neither JSON nor base64 JSON: " + "; ".join(failures[-2:]))


def load_session(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="strict")
    match = SESSION_RE.search(text)
    if not match:
        raise ValueError("session-data script tag not found")
    return decode_payload(match.group(1))


def flatten_session_entries(session: dict[str, Any]) -> list[dict[str, Any]]:
    """Return root and nested OMP sub-session entries with stable provenance."""
    flattened: list[dict[str, Any]] = []

    def visit(value: dict[str, Any], name: str, parent_session_id: str | None = None) -> None:
        header = value.get("header") if isinstance(value.get("header"), dict) else {}
        session_id = str(header.get("id") or name)
        agent_id = str(value.get("agentId") or value.get("agent_id") or ("Main" if name == "Main" else name))
        for entry in value.get("entries", []):
            if not isinstance(entry, dict):
                continue
            flattened.append({
                **entry,
                "_bbk_session_id": session_id,
                "_bbk_agent_id": agent_id,
                "_bbk_session_name": name,
                "_bbk_parent_session_id": parent_session_id,
            })
        subs = value.get("subSessions") or value.get("sub_sessions") or {}
        if isinstance(subs, dict):
            for child_name, child in sorted(subs.items(), key=lambda item: str(item[0])):
                if isinstance(child, dict):
                    visit(child, str(child_name), session_id)
        elif isinstance(subs, list):
            for index, child in enumerate(subs):
                if isinstance(child, dict):
                    visit(child, str(child.get("agentId") or child.get("agent_id") or f"sub-{index}"), session_id)

    visit(session, "Main")
    return flattened


def entry_custom_type(entry: dict[str, Any]) -> str:
    return str(entry.get("customType") or entry.get("custom_type") or "")


def entry_data(entry: dict[str, Any]) -> dict[str, Any]:
    value = entry.get("data")
    return value if isinstance(value, dict) else {}


def message_content(entry: dict[str, Any]) -> list[dict[str, Any]]:
    message = entry.get("message")
    if not isinstance(message, dict):
        return []
    content = message.get("content")
    return [item for item in content if isinstance(item, dict)] if isinstance(content, list) else []


def tool_results(entries: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Index OMP tool-result messages by their physical tool-call identity."""
    results: dict[str, dict[str, Any]] = {}
    for entry in entries:
        message = entry.get("message")
        if not isinstance(message, dict) or str(message.get("role") or "") != "toolResult":
            continue
        call_id = str(
            message.get("toolCallId")
            or message.get("tool_call_id")
            or ""
        ).strip()
        if not call_id:
            continue
        fragments: list[str] = []
        content = message.get("content")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    fragments.append(item["text"])
        elif isinstance(content, str):
            fragments.append(content)
        results[call_id] = {
            "tool_name": str(message.get("toolName") or message.get("tool_name") or ""),
            "is_error": bool(message.get("isError") or message.get("is_error")),
            "text": "\n".join(fragments),
            "details": message.get("details") if isinstance(message.get("details"), dict) else {},
            "timestamp": entry.get("timestamp"),
            "entry_id": entry.get("id"),
            "session_id": entry.get("_bbk_session_id"),
            "agent_id": entry.get("_bbk_agent_id"),
            "session_name": entry.get("_bbk_session_name"),
        }
    return results


def tool_calls(entries: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    observed: list[dict[str, Any]] = []
    for entry in entries:
        timestamp = entry.get("timestamp")
        custom = entry_custom_type(entry)
        data = entry_data(entry)
        if custom == "tool_execution_start" and data.get("toolName"):
            observed.append({
                "name": str(data.get("toolName")),
                "arguments": data.get("args") if isinstance(data.get("args"), dict) else {},
                "timestamp": timestamp,
                "entry_id": entry.get("id"),
                "turn_id": None,
                "tool_call_id": str(data.get("toolCallId") or data.get("tool_call_id") or "").strip() or None,
                "source": "tool_execution_start",
                "session_id": entry.get("_bbk_session_id"),
                "agent_id": entry.get("_bbk_agent_id"),
                "session_name": entry.get("_bbk_session_name"),
            })
        for item in message_content(entry):
            if str(item.get("type") or "").lower() not in {"toolcall", "tool_call"}:
                continue
            name = str(item.get("name") or "")
            arguments = item.get("arguments")
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {"raw": arguments}
            if not isinstance(arguments, dict):
                arguments = {}
            observed.append({
                "name": name,
                "arguments": arguments,
                "timestamp": timestamp,
                "entry_id": entry.get("id"),
                "turn_id": entry.get("id"),
                "tool_call_id": str(item.get("id") or item.get("toolCallId") or item.get("tool_call_id") or "").strip() or None,
                "source": "assistant_message",
                "session_id": entry.get("_bbk_session_id"),
                "agent_id": entry.get("_bbk_agent_id"),
                "session_name": entry.get("_bbk_session_name"),
            })

    # OMP exports the same physical call twice: once as a custom
    # tool_execution_start record and once inside the assistant message.  The
    # shared tool-call ID is the physical identity. Entry IDs are unrelated and
    # must never be used to count those two projections as separate calls.
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for call in observed:
        call_id = call.get("tool_call_id")
        if call_id:
            key = ("tool_call_id", str(call_id))
        else:
            # No host call identity is available, so preserve the record rather
            # than guessing that two nearby calls are equivalent.
            key = ("entry", str(call.get("entry_id") or id(call)))
        prior = unique.get(key)
        if prior is None:
            unique[key] = {**call, "sources": [call["source"]]}
            continue
        if prior["name"] != call["name"]:
            # A reused call ID with different tool names is corrupt evidence;
            # retain both using a deterministic collision key.
            unique[("collision", f"{call_id}:{call['name']}:{call.get('entry_id')}")] = {
                **call,
                "sources": [call["source"]],
                "tool_call_id_collision": True,
            }
            continue
        prior["sources"] = sorted(set([*prior.get("sources", []), call["source"]]))
        if call.get("turn_id") and not prior.get("turn_id"):
            prior["turn_id"] = call["turn_id"]
        # The tool_execution_start projection may contain only a filtered
        # subset of the physical call arguments. The assistant-message
        # projection carries the complete model-submitted payload and must win
        # for analysis. Otherwise identity-bearing fields such as bindingRef
        # disappear and distinct-role reads can be misclassified as same-
        # binding duplicate verification.
        if call.get("source") == "assistant_message" and call.get("arguments"):
            prior["arguments"] = call["arguments"]
        elif not prior.get("arguments") and call.get("arguments"):
            prior["arguments"] = call["arguments"]
        prior_time = parse_time(prior.get("timestamp"))
        call_time = parse_time(call.get("timestamp"))
        if prior_time is None or (call_time is not None and call_time < prior_time):
            prior["timestamp"] = call.get("timestamp")
    return list(unique.values())


def parse_time(value: Any) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def result_details(call: dict[str, Any]) -> dict[str, Any]:
    result = call.get("result")
    if not isinstance(result, dict):
        return {}
    details = result.get("details")
    if isinstance(details, dict) and details:
        return details
    text = str(result.get("text") or "").strip()
    if text:
        try:
            value = json.loads(text)
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass
    return {}


def call_failed(call: dict[str, Any]) -> bool:
    result = call.get("result")
    if not isinstance(result, dict):
        return False
    if result.get("is_error"):
        return True
    details = result_details(call)
    return str(details.get("status") or "").upper() in {"BLOCK", "FAIL", "FAILED", "ERROR", "BLOCKED_TECHNICAL"}


def call_succeeded(call: dict[str, Any]) -> bool:
    return isinstance(call.get("result"), dict) and not call_failed(call)


def call_reason_code(call: dict[str, Any]) -> str:
    details = result_details(call)
    result = call.get("result") if isinstance(call.get("result"), dict) else {}
    return str(details.get("reason_code") or details.get("code") or result.get("reason_code") or "")


def all_message_text(entries: Iterable[dict[str, Any]]) -> str:
    fragments: list[str] = []
    for entry in entries:
        message = entry.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str):
            fragments.append(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    for key in ("text", "thinking"):
                        if isinstance(item.get(key), str):
                            fragments.append(item[key])
    return "\n".join(fragments)


def _contract_source(expected_version: str, script_dir: Path):
    """Load the exact RC role schemas from source or the embedded release ZIP."""
    try:
        import jsonschema
        from referencing import Registry, Resource
    except ImportError as exc:
        return None, f"jsonschema unavailable: {exc}"

    source_root = None
    for candidate in [script_dir, *script_dir.parents]:
        if (candidate / "spec" / "roles" / "catalog.json").is_file():
            source_root = candidate
            break

    schemas: dict[str, dict[str, Any]] = {}
    role_docs: list[dict[str, Any]] = []
    origins: dict[str, str] = {}
    if source_root is not None:
        schema_paths = sorted((source_root / "spec" / "schemas").rglob("*.json"), key=lambda item: item.as_posix())
        for path in schema_paths:
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict) and isinstance(value.get("$id"), str):
                schema_id = value["$id"]
                relative = path.relative_to(source_root).as_posix()
                if schema_id in schemas:
                    return None, f"duplicate schema $id {schema_id} in {origins[schema_id]} and {relative}"
                schemas[schema_id] = value
                origins[schema_id] = relative
        role_docs = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((source_root / "spec" / "roles").glob("*-role.json"))
        ]
    else:
        archive = script_dir / f"bbk-{expected_version}.zip"
        if not archive.is_file():
            return None, f"exact RC archive is unavailable beside analyzer: {archive.name}"
        with zipfile.ZipFile(archive) as bundle:
            for name in sorted(bundle.namelist()):
                normalized = name.replace("\\", "/")
                if "/spec/schemas/" in normalized and normalized.endswith(".json"):
                    value = json.loads(bundle.read(name).decode("utf-8"))
                    if isinstance(value, dict) and isinstance(value.get("$id"), str):
                        schema_id = value["$id"]
                        if schema_id in schemas:
                            return None, f"duplicate schema $id {schema_id} in {origins[schema_id]} and {normalized}"
                        schemas[schema_id] = value
                        origins[schema_id] = normalized
                elif "/spec/roles/" in normalized and normalized.endswith("-role.json"):
                    value = json.loads(bundle.read(name).decode("utf-8"))
                    if isinstance(value, dict):
                        role_docs.append(value)
    registry = Registry()
    for schema_id in sorted(schemas):
        registry = registry.with_resource(schema_id, Resource.from_contents(schemas[schema_id]))
    contracts: dict[str, dict[str, Any]] = {}
    for role in role_docs:
        contract = role.get("return_contract") if isinstance(role.get("return_contract"), dict) else {}
        for contract_key, schema_key in (("v2_contract_id", "v2_return_schema"), ("contract_id", "return_schema")):
            contract_id = contract.get(contract_key)
            schema_path = contract.get(schema_key)
            if not isinstance(contract_id, str) or not isinstance(schema_path, str):
                continue
            schema_id = "https://bbk.local/schemas/" + Path(schema_path).name
            contracts[contract_id] = {
                "role": role.get("name"),
                "schema_id": schema_id,
                "schema": schemas.get(schema_id),
            }

    def validate(document: Any) -> dict[str, Any]:
        if not isinstance(document, dict):
            return {"status": "FAIL", "role": None, "errors": [{"instance_pointer": "", "message": "return data is not an object"}]}
        contract_id = document.get("contract")
        contract = contracts.get(str(contract_id))
        if not contract or not isinstance(contract.get("schema"), dict):
            return {"status": "FAIL", "role": document.get("role"), "contract": contract_id, "errors": [{"instance_pointer": "/contract", "message": "unknown or unavailable role-return contract"}]}
        validator = jsonschema.Draft202012Validator(contract["schema"], registry=registry)
        errors = sorted(validator.iter_errors(document), key=lambda item: (list(item.absolute_path), item.message))
        return {
            "status": "PASS" if not errors else "FAIL",
            "role": contract.get("role"),
            "contract": contract_id,
            "document_digest": "sha256:" + hashlib.sha256(canonical(document)).hexdigest(),
            "errors": [
                {
                    "instance_pointer": "/" + "/".join(str(part).replace("~", "~0").replace("/", "~1") for part in error.absolute_path) if error.absolute_path else "",
                    "message": error.message,
                }
                for error in errors[:40]
            ],
        }

    return validate, None


def analyze_role_returns(
    entries: list[dict[str, Any]],
    calls: list[dict[str, Any]],
    expected_version: str,
    script_dir: Path,
) -> dict[str, Any]:
    validation_events = [
        entry_data(entry)
        for entry in entries
        if entry_custom_type(entry) == "bbk-role-return-validation"
    ]
    events_by_call = {
        str(event.get("tool_call_id")): event
        for event in validation_events
        if str(event.get("tool_call_id") or "")
    }
    validate_exact, validator_error = _contract_source(expected_version, script_dir)
    yield_calls = [call for call in calls if call.get("name") == "yield"]
    prepared_calls = [call for call in calls if call.get("name") == "bbk_return_prepare"]
    records: list[dict[str, Any]] = []
    successful_roles: list[str] = []
    unvalidated_successes: list[str] = []
    blocked_repairs = 0
    for call in yield_calls:
        call_id = str(call.get("tool_call_id") or "")
        data = call.get("arguments", {}).get("result", {}).get("data") if isinstance(call.get("arguments"), dict) else None
        event = events_by_call.get(call_id)
        direct_validation = None
        if isinstance(data, dict) and data.get("schema") != "bbk.prepared-role-return.v1" and validate_exact is not None:
            direct_validation = validate_exact(data)
        event_status = str((event or {}).get("status") or "").upper()
        admitted = event_status in {"PASS", "ADMITTED"}
        blocked = call_failed(call) or event_status in {"BLOCK", "FAIL", "ERROR"}
        if blocked:
            blocked_repairs += 1
        role = str((event or {}).get("role") or (direct_validation or {}).get("role") or call.get("agent_id") or "")
        if admitted:
            successful_roles.append(role)
        elif not blocked:
            unvalidated_successes.append(call_id or str(call.get("entry_id") or "unknown"))
        records.append({
            "tool_call_id": call_id or None,
            "session_name": call.get("session_name"),
            "agent_id": call.get("agent_id"),
            "role": role or None,
            "input_kind": "PREPARED_TOKEN" if isinstance(data, dict) and data.get("schema") == "bbk.prepared-role-return.v1" else "DIRECT_DOCUMENT",
            "hook_validation": event or None,
            "independent_validation": direct_validation,
            "accepted": admitted,
            "blocked_for_repair": blocked,
        })
    role_counts = {role: successful_roles.count(role) for role in sorted(set(successful_roles)) if role}
    expected_counts = {"bbk_worker": 2, "bbk_reviewer": 1, "bbk_validator": 1}
    missing = {
        role: expected - role_counts.get(role, 0)
        for role, expected in expected_counts.items()
        if role_counts.get(role, 0) < expected
    }
    direct_failures = [
        record for record in records
        if record.get("independent_validation") and record["independent_validation"].get("status") != "PASS"
        and not record.get("blocked_for_repair")
    ]
    prepared_successes = [call for call in prepared_calls if call_succeeded(call)]
    # A schema/binding defect rejected by bbk_return_prepare and corrected by a
    # later successful prepare under the same child session and immutable
    # binding is an in-place mechanical repair. Count it even though malformed
    # data never reached hidden yield.
    prepared_success_keys: dict[tuple[str, str], list[float]] = {}
    for call in prepared_successes:
        args = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
        key = (
            str(call.get("session_name") or ""),
            str(args.get("bindingRef") or args.get("binding_ref") or ""),
        )
        prepared_success_keys.setdefault(key, []).append(parse_time(call.get("timestamp")) or 0.0)
    prepare_repairs = 0
    for call in prepared_calls:
        if not call_failed(call):
            continue
        args = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
        key = (
            str(call.get("session_name") or ""),
            str(args.get("bindingRef") or args.get("binding_ref") or ""),
        )
        failed_at = parse_time(call.get("timestamp")) or 0.0
        if any(success_at >= failed_at for success_at in prepared_success_keys.get(key, [])):
            prepare_repairs += 1
    blocked_repairs += prepare_repairs
    reason_codes: list[str] = []
    if unvalidated_successes:
        reason_codes.append("UNVALIDATED_ROLE_RETURN_ACCEPTED")
    if missing:
        reason_codes.append("REQUIRED_ROLE_RETURNS_MISSING")
    if direct_failures:
        reason_codes.append("DIRECT_ROLE_RETURN_SCHEMA_INVALID")
    if len(prepared_successes) < 4:
        reason_codes.append("VALIDATED_RETURN_BUILDER_NOT_USED_FOR_ALL_CHILDREN")
    status = "PASS" if not reason_codes else "FAIL"
    return {
        "status": status,
        "reason_codes": reason_codes,
        "yield_call_count": len(yield_calls),
        "prepared_return_call_count": len(prepared_calls),
        "prepared_return_success_count": len(prepared_successes),
        "hook_validation_event_count": len(validation_events),
        "same_attempt_schema_repair_count": blocked_repairs,
        "same_attempt_prepare_repair_count": prepare_repairs,
        "successful_role_counts": role_counts,
        "missing_role_returns": missing,
        "unvalidated_successful_yield_calls": unvalidated_successes,
        "validator_error": validator_error,
        "records": records,
    }


def analyze_verification_economy(calls: list[dict[str, Any]]) -> dict[str, Any]:
    """Detect deterministic re-execution after a current same-subject receipt.

    Worker-owned reads or ad-hoc hashes after the governed write are redundant
    because the write receipt binds exact bytes and the declared mise task is
    the one authorized independent completion check. Reviewer/Validator reads
    use distinct bindings and remain independently material.
    """
    ordered = sorted(calls, key=lambda call: parse_time(call.get("timestamp")) or 0.0)
    writes: dict[tuple[str, str], list[dict[str, Any]]] = {}
    governed_reads: dict[tuple[str, str], list[dict[str, Any]]] = {}
    tasks: dict[tuple[str, str], list[dict[str, Any]]] = {}
    handoffs: list[dict[str, Any]] = []
    raw_hash_attempts: list[dict[str, Any]] = []
    raw_read_attempts: list[dict[str, Any]] = []
    broad_validator_calls: list[dict[str, Any]] = []
    worker_result_paths = {"src/worker-a/result.txt", "src/worker-b/result.txt"}

    for call in ordered:
        name = str(call.get("name") or "")
        args = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
        binding = str(args.get("bindingRef") or args.get("binding_ref") or "")
        path_value = str(args.get("path") or args.get("file") or "").replace("\\", "/")
        if name == "bbk_governed_write" and call_succeeded(call):
            writes.setdefault((binding, path_value), []).append(call)
        elif name == "bbk_governed_read" and call_succeeded(call):
            governed_reads.setdefault((binding, path_value), []).append(call)
        elif name == "bbk_task_run" and call_succeeded(call):
            task = str(args.get("task") or "")
            tasks.setdefault((binding, task), []).append(call)
        elif name == "bbk_handoff_create":
            handoffs.append(call)

        encoded = json.dumps(args, ensure_ascii=False).lower().replace("\\\\", "/")
        is_worker_session = str(call.get("session_name") or "").startswith("Alpha17Worker")
        if is_worker_session and name in {"read", "grep", "cat", "view"}:
            if any(path in encoded for path in worker_result_paths):
                raw_read_attempts.append(call)
        if name in {"bash", "shell", "python", "eval", "mcp__node_repl_js", "powershell"}:
            if ("sha256" in encoded or "hashlib" in encoded or "get-filehash" in encoded) and any(
                path in encoded or Path(path).name in encoded for path in worker_result_paths
            ):
                raw_hash_attempts.append(call)
        if name in {"bbk_gate", "bbk_validate", "bbk_repository_validate"}:
            phase = str(args.get("phase") or args.get("scope") or "").lower()
            if phase in {"repository", "full", "release", "all"}:
                broad_validator_calls.append(call)

    duplicate_reads: list[dict[str, Any]] = []
    for key, read_calls in governed_reads.items():
        write_calls = writes.get(key, [])
        if not write_calls:
            continue
        first_write_time = min(parse_time(call.get("timestamp")) or 0.0 for call in write_calls)
        for call in read_calls:
            if (parse_time(call.get("timestamp")) or 0.0) >= first_write_time:
                duplicate_reads.append({
                    "binding_ref": key[0],
                    "path": key[1],
                    "tool_call_id": call.get("tool_call_id"),
                    "session_name": call.get("session_name"),
                    "kind": "GOVERNED_REREAD",
                })

    # A raw read is duplicate only when it occurred after the successful write
    # in the same Worker session. This avoids classifying the independent
    # Reviewer/Validator evidence reads as duplicates.
    for call in raw_read_attempts:
        observed = parse_time(call.get("timestamp")) or 0.0
        encoded = json.dumps(call.get("arguments", {}), ensure_ascii=False).lower().replace("\\\\", "/")
        for (binding, path_value), write_calls in writes.items():
            del binding
            if path_value not in encoded and Path(path_value).name not in encoded:
                continue
            if any((parse_time(write.get("timestamp")) or 0.0) <= observed and write.get("session_name") == call.get("session_name") for write in write_calls):
                duplicate_reads.append({
                    "binding_ref": None,
                    "path": path_value,
                    "tool_call_id": call.get("tool_call_id"),
                    "session_name": call.get("session_name"),
                    "kind": "RAW_REREAD",
                })
                break

    duplicate_tasks = [
        {
            "binding_ref": key[0],
            "task": key[1],
            "count": len(value),
            "tool_call_ids": [call.get("tool_call_id") for call in value],
        }
        for key, value in tasks.items()
        if len(value) > 1
    ]
    reason_codes: list[str] = []
    if duplicate_reads:
        reason_codes.append("UNCHANGED_SUBJECT_REREAD")
    if raw_hash_attempts:
        reason_codes.append("AD_HOC_DUPLICATE_HASH_ATTEMPT")
    if duplicate_tasks:
        reason_codes.append("DUPLICATE_QUALIFIED_TASK")
    if handoffs:
        reason_codes.append("UNNECESSARY_HANDOFF_PACKAGE_ATTEMPT")
    if broad_validator_calls:
        reason_codes.append("BROAD_VALIDATOR_SCOPE_UNPROVED")
    return {
        "status": "PASS" if not reason_codes else "FAIL",
        "reason_codes": reason_codes,
        "duplicate_deterministic_check_count": (
            len(duplicate_reads)
            + len(raw_hash_attempts)
            + sum(item["count"] - 1 for item in duplicate_tasks)
        ),
        "unchanged_subject_rereads": duplicate_reads,
        "raw_hash_attempts": [
            {
                "tool_call_id": call.get("tool_call_id"),
                "session_name": call.get("session_name"),
                "name": call.get("name"),
            }
            for call in raw_hash_attempts
        ],
        "duplicate_qualified_tasks": duplicate_tasks,
        "unnecessary_handoff_attempt_count": len(handoffs),
        "metadata_or_broad_validator_call_count": len(broad_validator_calls),
        "qualified_task_counts": [
            {"binding_ref": key[0], "task": key[1], "count": len(value)}
            for key, value in sorted(tasks.items())
        ],
    }


def _path_call(
    calls: list[dict[str, Any]],
    name: str,
    path_value: str,
    *,
    success: bool | None = None,
) -> list[dict[str, Any]]:
    expected = path_value.replace("\\", "/")
    result: list[dict[str, Any]] = []
    for call in calls:
        if call.get("name") != name:
            continue
        observed = str(call.get("arguments", {}).get("path") or "").replace("\\", "/")
        if observed != expected:
            continue
        if success is True and not call_succeeded(call):
            continue
        if success is False and not call_failed(call):
            continue
        result.append(call)
    return result


def _result_state(
    state: str,
    evidence: list[str],
    note: str = "",
    reason_codes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "result": state,
        "evidence_pointers": evidence,
        "operator_note": note,
        "reason_codes": reason_codes or [],
    }


def _pass(condition: bool, evidence: list[str], note: str = "", reason: str = "ASSERTION_NOT_ESTABLISHED") -> dict[str, Any]:
    return _result_state("PASS" if condition else "FAIL", evidence, note, [] if condition else [reason])


def derive_invariant_results(
    entries: list[dict[str, Any]],
    calls: list[dict[str, Any]],
    role_returns: dict[str, Any],
    economy: dict[str, Any],
    admission_pass: bool,
) -> dict[str, dict[str, Any]]:
    custom = [(entry_custom_type(entry), entry_data(entry)) for entry in entries]
    activations = [data for kind, data in custom if kind == "bbk-spawn-activation"]
    worker_activations = [
        data for data in activations
        if str(data.get("binding", {}).get("request", {}).get("role") or data.get("role") or "") == "bbk_worker"
    ]
    spawn_calls = [call for call in calls if call.get("name") == "bbk_control_spawn" and call_succeeded(call)]
    bind_calls = [call for call in calls if call.get("name") == "bbk_control_bind" and call_succeeded(call)]
    task_calls = [
        call for call in calls
        if call.get("name") == "bbk_task_run"
        and call_succeeded(call)
        and call.get("arguments", {}).get("task") == "alpha17:verify"
    ]
    integration_calls = [
        call for call in calls
        if call.get("name") == "bbk_manual_qualification_integrate" and call_succeeded(call)
    ]
    integration = result_details(integration_calls[-1]) if integration_calls else {}
    adapter = integration.get("adapter_result") if isinstance(integration.get("adapter_result"), dict) else {}
    admission = integration.get("candidate_admission") if isinstance(integration.get("candidate_admission"), dict) else {}
    candidate = integration.get("candidate") if isinstance(integration.get("candidate"), dict) else {}
    integrated_paths = adapter.get("integrated_paths") if isinstance(adapter.get("integrated_paths"), list) else integration.get("integrated_paths")
    expected_paths = ["src/worker-a/result.txt", "src/worker-b/result.txt"]
    expected_hashes = {
        "src/worker-a/result.txt": "581dd1b85ffaf4e2622841147bbc3fa704d1e510c279364a247650ace336a656",
        "src/worker-b/result.txt": "38ab9f21d110330fa638e32b8f5f4cb7675f056ac80cd427e18d13a89bd27543",
    }
    raw_tool_names = {str(call.get("name") or "") for call in calls}
    status_calls = [
        call for call in calls
        if call.get("name") == "bbk_manual_qualification_status" and call_succeeded(call)
    ]
    status_details = result_details(status_calls[-1]) if status_calls else {}

    asks = [call for call in calls if call.get("name") == "ask" and call_succeeded(call)]
    accepted = False
    acceptance_time = None
    for call in asks:
        details = result_details(call)
        selected = details.get("selectedOptions") if isinstance(details.get("selectedOptions"), list) else []
        text = str(call.get("result", {}).get("text") or "")
        if "Accept and proceed" in selected or "Accept and proceed" in text:
            accepted = True
            acceptance_time = parse_time(call.get("result", {}).get("timestamp") or call.get("timestamp"))
            break
    first_spawn_time = min((parse_time(call.get("timestamp")) or 0.0 for call in spawn_calls), default=None)
    exact_baseline = "WU-MANUAL-WORKER-A" in all_message_text(entries) and "WU-MANUAL-WORKER-B" in all_message_text(entries)

    worker_sessions = {
        str(item.get("actual_session_id") or item.get("session_id") or "")
        for item in worker_activations if item.get("actual_session_id") or item.get("session_id")
    }
    worker_bindings = {
        str(item.get("active_binding_ref") or item.get("binding_ref") or "")
        for item in worker_activations if item.get("active_binding_ref") or item.get("binding_ref")
    }
    worker_attempts = {
        str(item.get("attempt_id") or item.get("binding", {}).get("request", {}).get("attempt_id") or "")
        for item in worker_activations
    }
    worker_changes = {
        str(item.get("binding", {}).get("request", {}).get("jj_change_id") or "")
        for item in worker_activations
    }
    worker_workspaces = {
        str(item.get("binding", {}).get("request", {}).get("workspace_ref") or "")
        for item in worker_activations
    }

    forbidden_paths = set(str(value).replace("\\", "/") for value in integration.get("forbidden_paths_present", []) if isinstance(value, str))
    files = integration.get("files") if isinstance(integration.get("files"), dict) else {}

    def blocked_exact(path: str, allowed: set[str]) -> bool:
        calls_for_path = _path_call(calls, "bbk_governed_write", path, success=False)
        return bool(calls_for_path) and all(call_reason_code(call) in allowed for call in calls_for_path)

    support_names = {
        "bbk_root_wayfinder", "bbk_territory_wayfinder", "bbk_architect",
        "bbk_worker_designer", "bbk_verification_designer",
    }
    support_fanout = [
        call for call in calls
        if call.get("name") == "task"
        and str(call.get("arguments", {}).get("agent") or "") in support_names
    ]
    generic_dispatch = [
        call for call in calls
        if call.get("name") in {"eval", "python", "bash", "shell", "mcp__node_repl_js", "powershell"}
        and "dispatch" in json.dumps(call.get("arguments", {}), ensure_ascii=False).lower()
    ]

    results: dict[str, dict[str, Any]] = {}
    results["M17-001"] = _pass(
        accepted and exact_baseline and (first_spawn_time is None or acceptance_time is not None and acceptance_time <= first_spawn_time),
        ["tool:ask:baseline_acceptance", "session:exact-two-work-unit-baseline"],
    )
    results["M17-002"] = _pass(
        blocked_exact("src/root-orchestrator-forbidden.txt", {"ROLE_CAPABILITY_FORBIDDEN", "MUTATION_CLASS_FORBIDDEN", "WORKSPACE_SCOPE_ESCAPE"})
        and not _path_call(calls, "bbk_governed_write", "src/root-orchestrator-forbidden.txt", success=True),
        ["tool:bbk_governed_write:src/root-orchestrator-forbidden.txt"],
    )
    results["M17-003"] = _pass(
        len(spawn_calls) == 2
        and len(worker_activations) == 2
        and all(len(values) == 2 and "" not in values for values in (worker_sessions, worker_bindings, worker_attempts, worker_changes, worker_workspaces)),
        ["custom:bbk-spawn-activation", "tool:bbk_control_spawn"],
    )
    results["M17-004"] = _pass(
        all(_path_call(calls, "bbk_governed_write", path, success=True) for path in expected_paths)
        and all(isinstance(files.get(path), dict) and files[path].get("sha256") == digest for path, digest in expected_hashes.items()),
        [f"tool:bbk_governed_write:{path}" for path in expected_paths] + ["integration:files"],
    )
    results["M17-005"] = _pass(
        blocked_exact("../escape.txt", {"MUTATION_PATH_TRAVERSAL_FORBIDDEN", "WORKSPACE_SCOPE_ESCAPE", "MUTATION_PATH_SCOPE_FORBIDDEN"})
        and blocked_exact("src/worker-b/cross-worker-forbidden.txt", {"WORKSPACE_SCOPE_ESCAPE", "MUTATION_PATH_SCOPE_FORBIDDEN"})
        and not ({"escape.txt", "src/worker-b/cross-worker-forbidden.txt"} & forbidden_paths),
        ["tool:blocked-traversal", "tool:blocked-cross-worker", "integration:forbidden_paths_present"],
    )
    results["M17-006"] = _pass(
        blocked_exact("src/reviewer-forbidden.txt", {"ROLE_CAPABILITY_FORBIDDEN", "MUTATION_CLASS_FORBIDDEN"})
        and blocked_exact("src/validator-forbidden.txt", {"ROLE_CAPABILITY_FORBIDDEN", "MUTATION_CLASS_FORBIDDEN"})
        and not ({"src/reviewer-forbidden.txt", "src/validator-forbidden.txt"} & forbidden_paths),
        ["tool:reviewer-write-block", "tool:validator-write-block", "integration:forbidden_paths_present"],
    )
    results["M17-007"] = _pass(
        len(spawn_calls) == 2
        and all(result_details(call).get("assignment_projection", {}).get("status") == "PASS" for call in spawn_calls)
        and "bbk_control_assign" not in raw_tool_names
        and "bd" not in raw_tool_names,
        ["tool:bbk_control_spawn:assignment_projection", "session:tool-name-inventory"],
    )
    results["M17-008"] = _pass(
        len(task_calls) == 2
        and all(result_details(call).get("candidate_unchanged") is True and result_details(call).get("status") == "PASS" for call in task_calls),
        ["tool:bbk_task_run:alpha17:verify"],
    )
    results["M17-009"] = _pass(
        bool(integration_calls)
        and integrated_paths == expected_paths
        and len(adapter.get("parent_commit_ids", [])) == 2
        and len(adapter.get("source_change_ids", [])) == 2
        and adapter.get("conflict_resolution_authority") == "DENIED"
        and admission.get("unresolved_conflicts") is False,
        ["tool:bbk_manual_qualification_integrate", "integration:parent_commit_ids"],
    )
    results["M17-010"] = _pass(
        bool(integration_calls)
        and integrated_paths == expected_paths
        and admission.get("status") == "PASS"
        and not forbidden_paths
        and set(files) == set(expected_paths)
        and len(bind_calls) == 2,
        ["integration:candidate_admission", "integration:files", "tool:bbk_control_bind"],
    )
    bootstrap = status_details.get("bootstrap") if isinstance(status_details.get("bootstrap"), dict) else {}
    results["M17-011"] = _pass(
        bootstrap.get("jj_execution_mode") == "MISE_MANAGED"
        and bootstrap.get("jj_tool_spec") == "jj@0.43.0"
        and bool(bootstrap.get("mise_path"))
        and not ({"jj", "bd"} & raw_tool_names),
        ["tool:bbk_manual_qualification_status", "session:tool-name-inventory"],
    )
    results["M17-012"] = _pass(
        len(spawn_calls) == 2 and len(worker_activations) == 2 and not support_fanout and not generic_dispatch,
        ["tool:bbk_control_spawn", "custom:bbk-spawn-activation", "session:no-generic-dispatch-fallback"],
    )
    results["M17-013"] = _pass(
        economy.get("status") == "PASS" and role_returns.get("status") == "PASS",
        ["analysis:verification_economy", "analysis:role_returns"],
        reason="STRUCTURED_RETURN_OR_VERIFICATION_ECONOMY_NONPASS",
    )
    results["M17-014"] = _pass(admission_pass, ["analysis:mode-and-prompt-admission"])
    results["M17-015"] = _pass(
        admission_pass and not generic_dispatch,
        ["analysis:mode-and-prompt-admission", "session:no-generic-dispatch-fallback"],
    )
    results["M17-016"] = _pass(admission_pass, ["analysis:coordination-contract"])
    return results

def populate_result_record(
    template_path: Path,
    output_path: Path,
    report: dict[str, Any],
    invariants: dict[str, dict[str, Any]],
) -> None:
    template = json.loads(template_path.read_text(encoding="utf-8-sig"))
    template["template"] = False
    template["operator_result"] = report.get("status")
    template["candidate_digest"] = report.get("product", {}).get("integration_candidate_digest")
    template["evidence_files"] = ["session/omp-session.html", "session/session-admission.json"]
    template["missing_evidence"] = [] if report.get("status") == "PASS" else list(report.get("reason_codes", []))
    template["smallest_next_action"] = (
        "Complete the manual redaction attestation, inspect the redacted archive, and return the packet."
        if report.get("status") == "PASS"
        else "Repair the reported nonpassing invariant in the same bounded release-candidate line and rerun the exact campaign."
    )
    observations = template.get("critical_path_observations", {})
    economy = report.get("verification_economy", {})
    returns = report.get("role_returns", {})
    coordination = report.get("coordination", {})
    observations.update({
        "duplicate_deterministic_checks": economy.get("duplicate_deterministic_check_count"),
        "extension_owned_mode_active": report.get("mode", {}).get("active_expected_version_count", 0) > 0,
        "minimum_nonblocking_probe_interval_seconds": coordination.get("minimum_observed_probe_interval_seconds"),
        "specific_job_poll_attempts": coordination.get("specific_job_poll_attempt_count"),
        "blocking_wait_or_event_delivery_observed": coordination.get("blocking_wait_count", 0) > 0,
        "skill_fallback_observed": report.get("mode", {}).get("skill_prompt_count", 0) > 0,
        "unnecessary_handoff_packages": economy.get("unnecessary_handoff_attempt_count"),
        "receipt_reuse_observed": economy.get("status") == "PASS",
        "same_attempt_mechanical_repairs": returns.get("same_attempt_schema_repair_count"),
        "metadata_only_product_validator_runs": economy.get("metadata_or_broad_validator_call_count"),
        "four_fact_dispatch": invariants.get("M17-012", {}).get("result") == "PASS",
        "support_role_fanout_after_executable_work": 0 if invariants.get("M17-012", {}).get("result") == "PASS" else None,
    })
    template["critical_path_observations"] = observations
    for item in template.get("observed_invariants", []):
        value = invariants.get(str(item.get("id")))
        if value:
            item.update(value)
    # Analyzer-owned fields are complete. The human-only redaction attestation
    # deliberately remains untouched and is the sole remaining manual section.
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(template, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-html", required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--full-gate", action="store_true", help="evaluate all M17 invariants, role returns, and verification economy")
    parser.add_argument("--result-record-template")
    parser.add_argument("--result-record-output")
    args = parser.parse_args(argv)

    source = Path(args.session_html).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    expected_version = args.expected_version.strip()

    try:
        session = load_session(source)
    except Exception as exc:  # noqa: BLE001 - structured nonpass
        report = {
            "schema": "bbk.alpha17-manual-qualification-analysis.v1" if args.full_gate else "bbk.alpha17-manual-session-admission.v2",
            "status": "BLOCKED_TECHNICAL",
            "reason_codes": ["SESSION_EXPORT_UNREADABLE"],
            "error": str(exc),
            "source": {"path": str(source), "sha256": sha256_bytes(source.read_bytes()) if source.is_file() else None},
        }
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        return 2

    header = session.get("header") if isinstance(session.get("header"), dict) else {}
    entries = flatten_session_entries(session)
    custom_entries = [(entry_custom_type(entry), entry_data(entry), entry) for entry in entries]
    modes = [data for custom, data, _entry in custom_entries if custom == "bbk-mode-state"]
    receipts = [data for custom, data, _entry in custom_entries if custom == "bbk-effective-prompt-receipt"]
    skills = [entry for custom, _data, entry in custom_entries if custom == "skill-prompt"]

    active_modes = [
        value for value in modes
        if value.get("enabled") is True and value.get("package_version") == expected_version
    ]
    controller_receipts = [
        value for value in receipts
        if value.get("package_version") == expected_version
        and value.get("phase") == "before_agent_start"
        and value.get("prompt_kind") == "controller"
        and str(value.get("status") or value.get("action") or "").upper() in {"REPLACED", "BOUND", "VERIFIED", "REPAIRED"}
    ]
    provider_receipts = [
        value for value in receipts
        if value.get("package_version") == expected_version
        and value.get("phase") in {"provider_request_finalization", "before_provider_request"}
        and str(value.get("action") or value.get("status") or "").upper() in {"VERIFIED", "REPAIRED"}
    ]

    calls = tool_calls(entries)
    results_by_call = tool_results(entries)
    for call in calls:
        call_id = call.get("tool_call_id")
        if call_id and call_id in results_by_call:
            call["result"] = results_by_call[call_id]
    names = [call["name"] for call in calls]
    status_calls = [call for call in calls if call["name"] == "bbk_manual_qualification_status"]
    governed_calls = [call for call in calls if call["name"].startswith("bbk_")]
    generic_eval_calls = [
        call for call in calls
        if call["name"] in {"eval", "mcp__node_repl_js"}
        or (call["name"] == "python" and str(call["arguments"].get("mode") or "").lower() in {"eval", "exec"})
    ]

    coordination_calls = [call for call in calls if call["name"] in {"job", "irc", "hub"}]
    specific_job_polls = [
        call for call in coordination_calls
        if call["name"] == "job" and bool(call["arguments"].get("poll"))
    ]

    def specific_poll_denied_before_effect(call: dict[str, Any]) -> bool:
        result = call.get("result")
        if not isinstance(result, dict) or not result.get("is_error"):
            return False
        details = result.get("details") if isinstance(result.get("details"), dict) else {}
        reason_code = str(details.get("reason_code") or details.get("code") or "")
        text = str(result.get("text") or "")
        return (
            reason_code == "BBK_COORDINATION_SPECIFIC_POLL_FORBIDDEN"
            or "BBK_COORDINATION_SPECIFIC_POLL_FORBIDDEN" in text
        )

    denied_specific_job_polls = [call for call in specific_job_polls if specific_poll_denied_before_effect(call)]
    unenforced_specific_job_polls = [call for call in specific_job_polls if not specific_poll_denied_before_effect(call)]
    nonblocking_probes: list[dict[str, Any]] = []
    blocking_waits: list[dict[str, Any]] = []
    for call in coordination_calls:
        arguments = call["arguments"]
        if call["name"] == "job":
            keys = {key for key in arguments if key not in {"i", "intent"}}
            if not keys:
                blocking_waits.append(call)
            elif arguments.get("list"):
                nonblocking_probes.append(call)
            elif arguments.get("poll") and not specific_poll_denied_before_effect(call):
                nonblocking_probes.append(call)
        else:
            op = str(arguments.get("op") or "").lower()
            if op == "wait" or arguments.get("await") is True:
                blocking_waits.append(call)
            elif op in {"inbox", "list", "roster"}:
                nonblocking_probes.append(call)

    # One assistant turn may deliberately issue compatible status observations
    # in parallel (for example IRC roster plus job list).  That is one
    # controller wake/check burst, not a zero-second polling loop.  The shared
    # assistant-message entry ID is retained while physical calls are
    # deduplicated by tool-call ID above.
    probe_bursts: dict[str, float] = {}
    for call in nonblocking_probes:
        observed = parse_time(call.get("timestamp"))
        if observed is None:
            continue
        burst_key = str(call.get("turn_id") or call.get("tool_call_id") or call.get("entry_id") or observed)
        previous = probe_bursts.get(burst_key)
        probe_bursts[burst_key] = observed if previous is None else min(previous, observed)
    probe_intervals: list[float] = []
    times = sorted(probe_bursts.values())
    for previous, current in zip(times, times[1:]):
        probe_intervals.append(current - previous)

    reasons: list[str] = []
    if not active_modes:
        reasons.append("BBK_MODE_STATE_MISSING")
    if not controller_receipts:
        reasons.append("CONTROLLER_PROMPT_RECEIPT_MISSING")
    if not provider_receipts:
        reasons.append("PROVIDER_PROMPT_RECEIPT_MISSING")
    if skills:
        reasons.append("SKILL_FALLBACK_OBSERVED")
    if not status_calls:
        reasons.append("MANUAL_HARNESS_STATUS_NOT_CALLED")
    if generic_eval_calls:
        reasons.append("GENERIC_EVAL_FALLBACK_OBSERVED")
    if unenforced_specific_job_polls:
        reasons.append("SPECIFIC_JOB_POLL_UNENFORCED_OR_UNOBSERVED")

    efficiency_findings: list[str] = []
    if denied_specific_job_polls:
        efficiency_findings.append("SPECIFIC_JOB_POLL_ATTEMPT_BLOCKED_BEFORE_EFFECT")

    status = "PASS" if not reasons else "INCONCLUSIVE"
    report = {
        "schema": "bbk.alpha17-manual-session-admission.v2",
        "status": status,
        "reason_codes": reasons,
        "expected_package_version": expected_version,
        "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": {
            "path": str(source),
            "sha256": sha256_bytes(source.read_bytes()),
            "bytes": source.stat().st_size,
        },
        "session": {
            "id": header.get("id"),
            "timestamp": header.get("timestamp"),
            "cwd": header.get("cwd"),
            "entry_count": len(entries),
        },
        "mode": {
            "mode_state_count": len(modes),
            "active_expected_version_count": len(active_modes),
            "controller_prompt_receipt_count": len(controller_receipts),
            "provider_prompt_receipt_count": len(provider_receipts),
            "skill_prompt_count": len(skills),
        },
        "tools": {
            "total_calls": len(calls),
            "unique_names": sorted(set(names)),
            "governed_call_count": len(governed_calls),
            "manual_status_call_count": len(status_calls),
            "generic_eval_count": len(generic_eval_calls),
            "physical_tool_call_ids": len({call.get("tool_call_id") for call in calls if call.get("tool_call_id")}),
            "multi_projection_call_count": sum(1 for call in calls if len(call.get("sources", [])) > 1),
        },
        "coordination": {
            "specific_job_poll_attempt_count": len(specific_job_polls),
            "specific_job_poll_denied_before_effect_count": len(denied_specific_job_polls),
            "specific_job_poll_unenforced_or_unobserved_count": len(unenforced_specific_job_polls),
            "efficiency_findings": efficiency_findings,
            "nonblocking_probe_count": len(nonblocking_probes),
            "nonblocking_probe_burst_count": len(probe_bursts),
            "blocking_wait_count": len(blocking_waits),
            "nonblocking_probe_intervals_seconds": probe_intervals,
            "minimum_observed_probe_interval_seconds": min(probe_intervals) if probe_intervals else None,
            "enforced_minimum_seconds": 300,
        },
        "claim_limit": "PASS establishes only extension-owned mode/prompt admission, absence of skill/eval fallback, and either absence or pre-effect denial of specific-job polling in this export. Product invariants require separate evaluation.",
        "integrity": {},
    }
    if args.full_gate:
        admission_status = status
        admission_reason_codes = list(reasons)
        role_returns = analyze_role_returns(entries, calls, expected_version, Path(__file__).resolve().parent)
        verification_economy = analyze_verification_economy(calls)
        invariants = derive_invariant_results(
            entries,
            calls,
            role_returns,
            verification_economy,
            admission_status == "PASS",
        )
        integration_calls = [
            call for call in calls
            if call.get("name") == "bbk_manual_qualification_integrate" and call_succeeded(call)
        ]
        integration = result_details(integration_calls[-1]) if integration_calls else {}
        candidate = integration.get("candidate") if isinstance(integration.get("candidate"), dict) else {}
        candidate_admission = integration.get("candidate_admission") if isinstance(integration.get("candidate_admission"), dict) else {}
        invariant_failures = [item_id for item_id, item in invariants.items() if item.get("result") == "FAIL"]
        invariant_inconclusive = [item_id for item_id, item in invariants.items() if item.get("result") == "INCONCLUSIVE"]
        full_reasons: list[str] = [*admission_reason_codes]
        full_reasons.extend(str(value) for value in role_returns.get("reason_codes", []))
        full_reasons.extend(str(value) for value in verification_economy.get("reason_codes", []))
        full_reasons.extend(f"INVARIANT_FAILED:{item_id}" for item_id in invariant_failures)
        full_reasons.extend(f"INVARIANT_INCONCLUSIVE:{item_id}" for item_id in invariant_inconclusive)
        validator_error = role_returns.get("validator_error")
        if validator_error:
            full_status = "BLOCKED_TECHNICAL"
            full_reasons.append("ROLE_RETURN_VALIDATOR_UNAVAILABLE")
        elif admission_status != "PASS":
            full_status = "INCONCLUSIVE"
        elif role_returns.get("status") != "PASS" or verification_economy.get("status") != "PASS" or invariant_failures:
            full_status = "FAIL"
        elif invariant_inconclusive:
            full_status = "INCONCLUSIVE"
        else:
            full_status = "PASS"
        report.update({
            "schema": "bbk.alpha17-manual-qualification-analysis.v1",
            "status": full_status,
            "reason_codes": list(dict.fromkeys(full_reasons)),
            "session_admission": {
                "status": admission_status,
                "reason_codes": admission_reason_codes,
            },
            "role_returns": role_returns,
            "verification_economy": verification_economy,
            "invariants": invariants,
            "product": {
                "integration_status": integration.get("status"),
                "integration_candidate_digest": candidate.get("digest"),
                "candidate_admission_ref": integration.get("candidate_admission_ref"),
                "candidate_admission_status": candidate_admission.get("status"),
                "integrated_paths": integration.get("exact_integrated_paths") or candidate_admission.get("integrated_paths"),
                "parent_commit_ids": integration.get("exact_source_parent_commit_ids") or candidate_admission.get("parent_commit_ids"),
                "unresolved_conflicts": candidate_admission.get("unresolved_conflicts"),
            },
            "claim_limit": "PASS establishes all sixteen exact manual-campaign invariants, four hook-admitted role returns, and absence of redundant Worker deterministic rechecks in this export. It does not authorize Alpha.17 final without the remaining release-governance decision and required credentialed host gates.",
        })
        status = full_status
        if bool(args.result_record_template) != bool(args.result_record_output):
            report["status"] = "BLOCKED_TECHNICAL"
            report["reason_codes"] = list(dict.fromkeys([*report["reason_codes"], "RESULT_RECORD_ARGUMENTS_INCOMPLETE"]))
            status = "BLOCKED_TECHNICAL"
        elif args.result_record_template and args.result_record_output:
            try:
                populate_result_record(
                    Path(args.result_record_template).expanduser().resolve(),
                    Path(args.result_record_output).expanduser().resolve(),
                    report,
                    invariants,
                )
                report["result_record"] = {
                    "path": str(Path(args.result_record_output).expanduser().resolve()),
                    "status": "POPULATED_ANALYZER_FIELDS",
                    "manual_fields_remaining": ["redaction_attestation"],
                }
            except Exception as exc:  # noqa: BLE001 - preserve structured evidence
                report["status"] = "BLOCKED_TECHNICAL"
                report["reason_codes"] = list(dict.fromkeys([*report["reason_codes"], "RESULT_RECORD_POPULATION_FAILED"]))
                report["result_record_error"] = str(exc)
                status = "BLOCKED_TECHNICAL"

    report["integrity"] = {}
    report["integrity"]["report_sha256"] = sha256_bytes(canonical({**report, "integrity": {}}))
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
