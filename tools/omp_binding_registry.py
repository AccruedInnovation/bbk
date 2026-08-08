#!/usr/bin/env python3
"""OMP identity, spawn-admission, and binding-continuity adapter.

This adapter is the authoritative bridge between OMP host observations and
BBK's immutable invocation bindings.  It never treats process CWD as workspace
or candidate authority.  Raw prompts, tool payloads, credentials, and provider
messages are deliberately excluded; callers pass canonical SHA-256 identities.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from gate_kernel import canonical_digest, canonical_json_bytes
    from governed_state import (
        GovernanceStateError,
        all_bindings,
        all_receipts,
        append_receipt,
        create_binding,
        resolve_binding,
        utc_now,
    )
except ImportError:  # pragma: no cover - installed-package import fallback
    from .gate_kernel import canonical_digest, canonical_json_bytes
    from .governed_state import (
        GovernanceStateError,
        all_bindings,
        all_receipts,
        append_receipt,
        create_binding,
        resolve_binding,
        utc_now,
    )

QUALIFIED_HOSTS = frozenset({"omp/16.4.8", "16.4.8", "omp-v16.4.8"})
PRE_EFFECT_EVENT_TYPES = frozenset({"TOOL_CALL", "TASK_TOOL_CALL", "SPAWN_ADMISSION"})
POST_EFFECT_EVENT_TYPES = frozenset({
    "TOOL_EXECUTION_START",
    "TOOL_EXECUTION_END",
    "TOOL_RESULT",
    "TASK_LIFECYCLE",
    "SESSION_START",
    "SESSION_SWITCH",
    "SESSION_BRANCH",
    "SESSION_TREE",
    "SESSION_SHUTDOWN",
    "WAKE",
    "INJECT",
    "RESUME",
    "RETRY",
})
DIGEST_RE = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+\-]*$")
SENSITIVE_KEY_RE = re.compile(
    r"(?:api[_-]?key|authorization|bearer|cookie|credential|password|prompt|secret|token)",
    re.IGNORECASE,
)
CONTINUITY_EVENTS = frozenset({"WAKE", "INJECT", "RESUME"})
PLANNED_SESSION_PREFIX = "planned-session:"
DISPATCH_REF_RE = re.compile(r"^dispatch:[0-9a-f]{64}$")
DISPATCH_MARKER_RE = re.compile(r'^<bbk-spawn-dispatch ref="(dispatch:[0-9a-f]{64})"/>$')
DISPATCH_LEASE_SECONDS = 600
DISPATCH_STATES = frozenset({"READY", "LEASED", "ACTIVATED", "TERMINAL"})


class OmpBindingError(RuntimeError):
    """A host event or binding transition is unsafe or incomplete."""

    def __init__(self, code: str, message: str, *, smallest_next_action: str = ""):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.smallest_next_action = smallest_next_action or "Provide a complete typed host/binding record and retry."


def _text(value: Any, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise OmpBindingError("OMP_HOST_EVENT_INVALID", f"{field} must be a non-empty string")
    result = value.strip()
    if result and field not in {"host_version", "parent_session"} and not SAFE_ID_RE.fullmatch(result):
        raise OmpBindingError("OMP_HOST_EVENT_INVALID", f"{field} contains unsupported characters")
    return result


def _digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or not DIGEST_RE.fullmatch(value):
        raise OmpBindingError("OMP_HOST_EVENT_INVALID", f"{field} must be a SHA-256 identity")
    return f"sha256:{value.removeprefix('sha256:')}"


def _assert_no_sensitive_fields(value: Any, *, path: str = "event") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if SENSITIVE_KEY_RE.search(str(key)):
                raise OmpBindingError(
                    "OMP_HOST_EVENT_SENSITIVE_FIELD_FORBIDDEN",
                    f"{path}.{key} is not permitted in durable host records",
                    smallest_next_action="Replace raw provider/prompt/credential content with a canonical digest.",
                )
            _assert_no_sensitive_fields(item, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_no_sensitive_fields(item, path=f"{path}[{index}]")


def enforcement_boundary(host_version: str, event_type: str, *, pre_effect_blocking: bool = True) -> str:
    """Return an honest host enforcement classification.

    OMP 16.4.8 is the only qualified initial host.  Pre-effect ``tool_call``
    events are enforceable there.  Lifecycle and post-effect observations are
    useful evidence but are not represented as prevention.
    """
    normalized_type = str(event_type).strip().upper()
    qualified = str(host_version).strip() in QUALIFIED_HOSTS
    if not qualified:
        return "UNQUALIFIED"
    if normalized_type in PRE_EFFECT_EVENT_TYPES and pre_effect_blocking:
        return "ENFORCED"
    if normalized_type in POST_EFFECT_EVENT_TYPES or normalized_type in PRE_EFFECT_EVENT_TYPES:
        return "DETECT_ONLY"
    return "UNQUALIFIED"


def enforcement_status(host_version: str) -> dict[str, Any]:
    qualified = str(host_version).strip() in QUALIFIED_HOSTS
    return {
        "schema": "bbk.omp-enforcement-boundary-status.v1",
        "host_version": str(host_version),
        "qualification": "QUALIFIED" if qualified else "UNQUALIFIED",
        "qualified_hosts": sorted(QUALIFIED_HOSTS),
        "boundaries": {
            "built_in_write_edit_bash_tool_call": "ENFORCED" if qualified else "UNQUALIFIED",
            "task_spawn_tool_call": "ENFORCED" if qualified else "UNQUALIFIED",
            "tool_execution_start_end": "DETECT_ONLY" if qualified else "UNQUALIFIED",
            "task_lifecycle_and_session_navigation": "DETECT_ONLY" if qualified else "UNQUALIFIED",
            "operating_system_sandbox": "UNQUALIFIED",
            "unintercepted_subprocess_effects": "DETECT_ONLY" if qualified else "UNQUALIFIED",
        },
        "notes": [
            "CWD is observation context only and is never workspace or candidate authority.",
            "No operating-system sandbox is claimed.",
            "Raw prompts, credentials, and provider payloads are excluded from receipts.",
        ],
    }


def normalize_host_event(
    envelope: Mapping[str, Any],
    *,
    binding: Mapping[str, Any] | None = None,
    pre_effect_blocking: bool = True,
) -> dict[str, Any]:
    if not isinstance(envelope, Mapping):
        raise OmpBindingError("OMP_HOST_EVENT_INVALID", "host event envelope must be an object")
    _assert_no_sensitive_fields(envelope)
    host_version = _text(envelope.get("host_version"), "host_version")
    event_type = _text(envelope.get("event_type"), "event_type").upper()
    session_id = _text(envelope.get("session_id"), "session_id")
    task_or_tool_id = _text(envelope.get("task_or_tool_id"), "task_or_tool_id")
    parent_session = _text(envelope.get("parent_session", ""), "parent_session", allow_empty=True)
    payload_digest = _digest(envelope.get("payload_digest"), "payload_digest")
    observed_at = _text(envelope.get("observed_at"), "observed_at")

    request = binding.get("request", {}) if isinstance(binding, Mapping) else {}
    binding_id = str(binding.get("binding_id", "")) if isinstance(binding, Mapping) else ""
    normalized_identity = {
        "host": host_version,
        "session_id": session_id,
        "parent_session_id": parent_session or None,
        "task_or_tool_id": task_or_tool_id,
        "payload_digest": payload_digest,
    }
    correlation = {
        "binding_ref": binding_id or None,
        "invocation_id": request.get("invocation_id") or envelope.get("invocation_id") or None,
        "work_unit_id": request.get("work_unit_id") or envelope.get("work_unit_id") or None,
        "attempt_id": request.get("attempt_id") or envelope.get("attempt_id") or None,
        "role": request.get("role") or envelope.get("role") or None,
        "candidate_ref": request.get("candidate_ref") or envelope.get("candidate_ref") or None,
    }
    event_class = (
        "PRE_EFFECT_TOOL_DECISION"
        if event_type in PRE_EFFECT_EVENT_TYPES
        else "POST_EFFECT_OBSERVATION"
        if event_type in POST_EFFECT_EVENT_TYPES
        else "UNCLASSIFIED_HOST_OBSERVATION"
    )
    return {
        "schema": "bbk.host-event.v1",
        "host_version": host_version,
        "event_type": event_type,
        "session_id": session_id,
        "task_or_tool_id": task_or_tool_id,
        "parent_session": parent_session,
        "payload_digest": payload_digest,
        "observed_at": observed_at,
        "normalized_identity": normalized_identity,
        "correlation": correlation,
        "event_class": event_class,
        "enforcement_boundary": enforcement_boundary(
            host_version,
            event_type,
            pre_effect_blocking=pre_effect_blocking,
        ),
    }


def record_host_event(
    project_root: str | Path,
    envelope: Mapping[str, Any],
    *,
    binding_ref: str | None = None,
    pre_effect_blocking: bool = True,
) -> tuple[dict[str, Any], bool]:
    binding = None
    if binding_ref:
        binding = resolve_binding_reference(project_root, binding_ref)
        if binding is None:
            raise OmpBindingError("OMP_BINDING_NOT_FOUND", f"active binding {binding_ref} does not exist")
    normalized = normalize_host_event(
        envelope,
        binding=binding,
        pre_effect_blocking=pre_effect_blocking,
    )
    receipt_id = f"sha256:{canonical_digest(normalized)}"
    receipt, created = append_receipt(
        project_root,
        "OMP_HOST_EVENT",
        normalized,
        receipt_id=receipt_id,
        recorded_at=normalized["observed_at"],
    )
    return receipt, created


def create_initial_binding(
    project_root: str | Path,
    request: Mapping[str, Any],
    *,
    capability_ref: str,
    created_at: str | None = None,
) -> tuple[dict[str, Any], bool]:
    if request.get("supersedes"):
        raise OmpBindingError("OMP_INITIAL_BINDING_SUPERSESSION_FORBIDDEN", "initial binding cannot supersede another binding")
    return create_binding(project_root, request, capability_ref=capability_ref, created_at=created_at)


def _binding_record(project_root: str | Path, binding_ref: str) -> dict[str, Any] | None:
    matches = [record for record in all_bindings(project_root) if record.get("binding_id") == binding_ref]
    if not matches:
        return None
    if len(matches) > 1:  # pragma: no cover - immutable binding IDs make this a corruption guard
        raise OmpBindingError("OMP_BINDING_AMBIGUOUS", f"multiple bindings use identity {binding_ref}")
    return matches[0]


def _activation_receipts(project_root: str | Path, planned_binding_ref: str) -> list[dict[str, Any]]:
    return [
        receipt
        for receipt in all_receipts(project_root)
        if receipt.get("receipt_kind") == "SPAWN_SESSION_ACTIVATION"
        and receipt.get("content", {}).get("planned_binding_ref") == planned_binding_ref
    ]


def resolve_binding_reference(project_root: str | Path, binding_ref: str) -> dict[str, Any] | None:
    """Resolve an active binding, including a planned-spawn reference alias.

    The bound worker packet is compiled before OMP assigns the actual child
    session ID, so it carries the immutable planned binding reference.  Once
    the child starts, ``SPAWN_SESSION_ACTIVATION`` explicitly supersedes that
    binding with the observed session identity.  The packet reference remains
    a safe alias only to that one current successor; it is never inferred from
    CWD, task prose, or a mutable projection.
    """
    active = resolve_binding(project_root, binding_id=binding_ref)
    if active is not None:
        return active
    activations = _activation_receipts(project_root, binding_ref)
    if not activations:
        return None
    successor_refs = {
        str(receipt.get("content", {}).get("active_binding_ref", ""))
        for receipt in activations
        if receipt.get("content", {}).get("active_binding_ref")
    }
    if len(successor_refs) != 1:
        raise OmpBindingError(
            "OMP_SPAWN_ACTIVATION_AMBIGUOUS",
            f"planned binding {binding_ref} has {len(successor_refs)} activation successors",
        )
    return resolve_binding(project_root, binding_id=next(iter(successor_refs)))


def _continuity_stable_fields(record: Mapping[str, Any]) -> dict[str, Any]:
    request = record.get("request", {})
    return {
        "role": request.get("role"),
        "work_unit_id": request.get("work_unit_id"),
        "baseline_ref": request.get("baseline_ref"),
        "authority_ref": request.get("authority_ref"),
        "return_contract": request.get("return_contract"),
        "parent_session_id": request.get("parent_session_id"),
    }


def retain_binding(
    project_root: str | Path,
    *,
    event_type: str,
    binding_ref: str,
    session_id: str,
    invocation_id: str,
    payload_digest: str,
    observed_at: str | None = None,
) -> dict[str, Any]:
    event = str(event_type).strip().upper()
    if event not in CONTINUITY_EVENTS:
        raise OmpBindingError("OMP_CONTINUITY_EVENT_INVALID", f"{event_type!r} is not WAKE, INJECT, or RESUME")
    binding = resolve_binding_reference(project_root, binding_ref)
    if binding is None:
        raise OmpBindingError("OMP_BINDING_NOT_FOUND", f"active binding {binding_ref} does not exist")
    request = binding["request"]
    if request["session_id"] != session_id or request["invocation_id"] != invocation_id:
        raise OmpBindingError(
            "OMP_BINDING_CONTINUITY_MISMATCH",
            f"{event} must retain exact session and invocation identity",
            smallest_next_action="Use the original binding unchanged, or create an explicit RETRY successor.",
        )
    core = {
        "schema": "bbk.binding-continuity.v1",
        "event_type": event,
        "binding_ref": binding["binding_id"],
        "session_id": session_id,
        "invocation_id": invocation_id,
        "payload_digest": _digest(payload_digest, "payload_digest"),
        "immutable_binding_digest": binding.get("immutable_digest"),
    }
    receipt_id = f"sha256:{canonical_digest(core)}"
    append_receipt(
        project_root,
        "BINDING_CONTINUITY",
        core,
        receipt_id=receipt_id,
        recorded_at=observed_at or utc_now(),
    )
    return {**core, "status": "RETAINED", "receipt_ref": receipt_id}


def retry_binding(
    project_root: str | Path,
    *,
    predecessor_ref: str,
    successor_request: Mapping[str, Any],
    capability_ref: str,
    created_at: str | None = None,
) -> tuple[dict[str, Any], bool]:
    predecessor = resolve_binding(project_root, binding_id=predecessor_ref)
    if predecessor is None:
        raise OmpBindingError("OMP_BINDING_NOT_FOUND", f"active predecessor binding {predecessor_ref} does not exist")
    request = dict(successor_request)
    if request.get("supersedes") != predecessor_ref:
        raise OmpBindingError(
            "OMP_RETRY_SUPERSESSION_REQUIRED",
            "retry binding must explicitly supersede the active predecessor",
        )
    before = _continuity_stable_fields(predecessor)
    provisional = {"request": request}
    after = _continuity_stable_fields(provisional)
    changed = [field for field in before if before[field] != after[field]]
    if changed:
        raise OmpBindingError(
            "OMP_RETRY_AUTHORITY_DRIFT",
            f"retry changed stable binding fields: {', '.join(changed)}",
            smallest_next_action="Create a new work unit/authority assignment instead of disguising it as a retry.",
        )
    if request.get("attempt_id") == predecessor["request"].get("attempt_id"):
        raise OmpBindingError("OMP_RETRY_ATTEMPT_ID_REUSED", "retry requires a new attempt_id")
    if request.get("invocation_id") == predecessor["request"].get("invocation_id"):
        raise OmpBindingError("OMP_RETRY_INVOCATION_ID_REUSED", "retry requires a new invocation_id")
    return create_binding(
        project_root,
        request,
        capability_ref=capability_ref,
        created_at=created_at,
    )




def canonical_dispatch_envelope(task_input: Mapping[str, Any]) -> dict[str, Any]:
    """Return the integrity-bearing compact OMP dispatch envelope.

    OMP 16.4.8 normalizes its built-in ``task`` arguments before the
    pre-effect hook.  In particular the presentation-only ``i`` field is not
    present at the enforcement boundary.  Dispatch integrity therefore binds
    only the exact one-item task identity and the duplicated opaque marker;
    display labels, defaults, ordering hints, and any other host-only fields
    are deliberately excluded.
    """
    if not isinstance(task_input, Mapping):
        raise OmpBindingError("OMP_SPAWN_DISPATCH_INPUT_INVALID", "dispatch input must be an object")
    tasks = task_input.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 1 or not isinstance(tasks[0], Mapping):
        raise OmpBindingError(
            "OMP_SPAWN_DISPATCH_INPUT_INVALID",
            "dispatch input must contain exactly one task item",
        )
    item = tasks[0]
    context = str(task_input.get("context") or "").strip()
    task = str(item.get("task") or "").strip()
    context_match = DISPATCH_MARKER_RE.fullmatch(context)
    task_match = DISPATCH_MARKER_RE.fullmatch(task)
    if not context_match or not task_match or context_match.group(1) != task_match.group(1):
        raise OmpBindingError(
            "OMP_SPAWN_DISPATCH_MARKER_INVALID",
            "dispatch context and task must contain the same exact BBK dispatch marker",
        )
    return {
        "context": context,
        "tasks": [
            {
                "agent": _text(item.get("agent"), "agent"),
                "name": _text(item.get("name"), "task_name"),
                "task": task,
            }
        ],
    }


def dispatch_envelope_digest(task_input: Mapping[str, Any]) -> str:
    """Return the canonical digest used at OMP's normalized hook boundary."""
    return f"sha256:{canonical_digest(canonical_dispatch_envelope(task_input))}"


def build_dispatch_task_input(*, dispatch_ref: str, task_name: str, agent: str) -> dict[str, Any]:
    """Return the smallest token-addressed task envelope accepted by OMP.

    The dispatch token is authoritative.  The full authenticated assignment is
    retained privately and resolved by the pre-effect hook.  OMP's optional
    presentation-only ``i`` label remains model-visible, but it is deliberately
    excluded by :func:`canonical_dispatch_envelope` because OMP 16.4.8 removes
    it before the pre-effect hook.
    """
    if not isinstance(dispatch_ref, str) or not DISPATCH_REF_RE.fullmatch(dispatch_ref):
        raise OmpBindingError("OMP_SPAWN_DISPATCH_REF_INVALID", "dispatch_ref must be dispatch:<64 lowercase hex>")
    marker = f'<bbk-spawn-dispatch ref="{dispatch_ref}"/>'
    return {
        "i": "Dispatch immutable BBK child reservation",
        "context": marker,
        "tasks": [
            {
                "name": _text(task_name, "task_name"),
                "agent": _text(agent, "agent"),
                "task": marker,
            }
        ],
    }


def parse_dispatch_ref(task_input: Mapping[str, Any]) -> str | None:
    """Extract an exact dispatch marker from a compact flat or batch envelope."""
    if not isinstance(task_input, Mapping):
        return None
    tasks = task_input.get("tasks")
    if isinstance(tasks, list):
        try:
            canonical = canonical_dispatch_envelope(task_input)
        except OmpBindingError:
            return None
        match = DISPATCH_MARKER_RE.fullmatch(canonical["context"])
        return match.group(1) if match else None
    match = DISPATCH_MARKER_RE.fullmatch(str(task_input.get("task") or "").strip())
    return match.group(1) if match else None


def _dispatch_payload_path(project_root: str | Path, dispatch_ref: str, *, create_parent: bool = True) -> Path:
    if not DISPATCH_REF_RE.fullmatch(str(dispatch_ref)):
        raise OmpBindingError("OMP_SPAWN_DISPATCH_REF_INVALID", "dispatch_ref must be dispatch:<64 lowercase hex>")
    root = Path(project_root).resolve() / ".bbk" / "governance" / "spawn-payloads"
    if create_parent:
        root.mkdir(parents=True, exist_ok=True)
    if root.exists() and (root.is_symlink() or not root.is_dir()):
        raise OmpBindingError("OMP_SPAWN_DISPATCH_PATH_UNSAFE", f"unsafe dispatch payload root {root}")
    path = root / f"{dispatch_ref.removeprefix('dispatch:')}.json"
    if path.is_symlink():
        raise OmpBindingError("OMP_SPAWN_DISPATCH_PATH_UNSAFE", f"unsafe dispatch payload path {path}")
    return path


def _write_dispatch_payload(
    project_root: str | Path,
    *,
    dispatch_ref: str,
    binding_ref: str,
    input_digest: str,
    task_input: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(task_input, Mapping):
        raise OmpBindingError("OMP_SPAWN_DISPATCH_PAYLOAD_INVALID", "resolved task input must be an object")
    normalized_input = dict(task_input)
    expected_digest = _digest(input_digest, "input_digest")
    if f"sha256:{canonical_digest(normalized_input)}" != expected_digest:
        raise OmpBindingError(
            "OMP_SPAWN_DISPATCH_PAYLOAD_DIGEST_MISMATCH",
            "resolved task input does not match its declared immutable digest",
        )
    core = {
        "schema": "bbk.spawn-dispatch-payload.v1",
        "dispatch_ref": dispatch_ref,
        "binding_ref": binding_ref,
        "input_digest": expected_digest,
        "task_input": normalized_input,
    }
    payload = {**core, "payload_digest": f"sha256:{canonical_digest(core)}"}
    path = _dispatch_payload_path(project_root, dispatch_ref)
    encoded = canonical_json_bytes(payload) + b"\n"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if path.read_bytes() != encoded:
            raise OmpBindingError(
                "OMP_SPAWN_DISPATCH_PAYLOAD_COLLISION",
                "dispatch reference already identifies different immutable task bytes",
            )
        return {**payload, "path": str(path), "created": False}
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return {**payload, "path": str(path), "created": True}


def _load_dispatch_payload(project_root: str | Path, reservation: Mapping[str, Any]) -> dict[str, Any]:
    dispatch_ref = str(reservation.get("dispatch_ref") or "")
    path = _dispatch_payload_path(project_root, dispatch_ref, create_parent=False)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OmpBindingError(
            "OMP_SPAWN_DISPATCH_PAYLOAD_UNAVAILABLE",
            f"cannot read immutable dispatch payload: {exc}",
        ) from exc
    if not isinstance(payload, dict):
        raise OmpBindingError("OMP_SPAWN_DISPATCH_PAYLOAD_INVALID", "dispatch payload must be a JSON object")
    core = {key: value for key, value in payload.items() if key != "payload_digest"}
    if payload.get("payload_digest") != f"sha256:{canonical_digest(core)}":
        raise OmpBindingError("OMP_SPAWN_DISPATCH_PAYLOAD_TAMPERED", "dispatch payload integrity check failed")
    if payload.get("dispatch_ref") != dispatch_ref or payload.get("binding_ref") != reservation.get("binding_ref"):
        raise OmpBindingError("OMP_SPAWN_DISPATCH_PAYLOAD_MISMATCH", "dispatch payload identity differs from reservation")
    task_input = payload.get("task_input")
    if not isinstance(task_input, dict):
        raise OmpBindingError("OMP_SPAWN_DISPATCH_PAYLOAD_INVALID", "dispatch payload task_input must be an object")
    if f"sha256:{canonical_digest(task_input)}" != reservation.get("input_digest"):
        raise OmpBindingError("OMP_SPAWN_DISPATCH_PAYLOAD_TAMPERED", "resolved task input digest differs from reservation")
    if payload.get("payload_digest") != reservation.get("dispatch_payload_digest"):
        raise OmpBindingError("OMP_SPAWN_DISPATCH_PAYLOAD_TAMPERED", "dispatch payload digest differs from reservation")
    return payload


def _discard_dispatch_payload(project_root: str | Path, dispatch_ref: str) -> bool:
    path = _dispatch_payload_path(project_root, dispatch_ref, create_parent=False)
    if not path.exists():
        return False
    try:
        path.unlink()
    except OSError as exc:
        raise OmpBindingError(
            "OMP_SPAWN_DISPATCH_PAYLOAD_CLEANUP_FAILED",
            f"cannot remove consumed dispatch payload: {exc}",
        ) from exc
    return True


def binding_execution_policy(project_root: str | Path, *, session_id: str) -> dict[str, Any]:
    """Return the current session-bound execution/transport policy.

    This is a read-only host-hook query.  It lets OMP enforce deterministic
    transport constraints without exposing or reconstructing the bound task
    payload.  Absence or ambiguity fails closed through ``resolve_binding``.
    """
    session = _text(session_id, "session_id")
    binding = resolve_binding(project_root, session_id=session)
    if binding is None:
        raise OmpBindingError(
            "OMP_ACTIVE_BINDING_REQUIRED",
            f"no current invocation binding exists for session {session}",
            smallest_next_action="Use the exact activated BBK child session and binding.",
        )
    request = binding.get("request", {})
    mode = str(request.get("return_transport_mode") or "STRUCTURED_RETURN_FIRST").strip().upper()
    if mode not in {"STRUCTURED_RETURN_FIRST", "STRUCTURED_RETURN_ONLY", "SEALED_HANDOFF_REQUIRED"}:
        raise OmpBindingError(
            "OMP_RETURN_TRANSPORT_POLICY_INVALID",
            f"binding {binding.get('binding_id')} has invalid return transport mode {mode!r}",
        )
    parent_binding = None
    parent_session_id = request.get("parent_session_id")
    if isinstance(parent_session_id, str) and parent_session_id:
        parent_binding = resolve_binding(project_root, session_id=parent_session_id)
    parent_request = parent_binding.get("request", {}) if parent_binding else {}
    return {
        "schema": "bbk.binding-execution-policy.v1",
        "status": "PASS",
        "session_id": session,
        "binding_ref": binding.get("binding_id"),
        "invocation_id": request.get("invocation_id"),
        "role": request.get("role"),
        "work_unit_id": request.get("work_unit_id"),
        "attempt_id": request.get("attempt_id"),
        "baseline_ref": request.get("baseline_ref"),
        "candidate_ref": request.get("candidate_ref"),
        "workspace_ref": request.get("workspace_ref"),
        "authority_ref": request.get("authority_ref"),
        "scope": request.get("scope"),
        "return_contract": request.get("return_contract"),
        "jj_change_id": request.get("jj_change_id"),
        "parent_session_id": parent_session_id,
        "parent_binding_ref": parent_binding.get("binding_id") if parent_binding else None,
        "parent_role": parent_request.get("role") if parent_binding else None,
        "parent_invocation_id": parent_request.get("invocation_id") if parent_binding else None,
        "return_transport_mode": mode,
        "material_transport_reason": str(request.get("material_transport_reason") or ""),
        "binding_digest": binding.get("immutable_digest"),
    }


def create_spawn_reservation(
    project_root: str | Path,
    *,
    binding_ref: str,
    parent_session_id: str,
    task_name: str,
    agent: str,
    input_digest: str,
    task_input: Mapping[str, Any] | None = None,
    dispatch_envelope_digest: str | None = None,
    dispatch_input_digest: str | None = None,
    dispatch_ref: str | None = None,
    tool_name: str = "task",
    reservation_id: str | None = None,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    binding = resolve_binding(project_root, binding_id=binding_ref)
    if binding is None:
        raise OmpBindingError("OMP_BINDING_NOT_FOUND", f"active binding {binding_ref} does not exist")
    request = binding["request"]
    parent = _text(parent_session_id, "parent_session_id")
    if request.get("parent_session_id") and request.get("parent_session_id") != parent:
        raise OmpBindingError("OMP_SPAWN_PARENT_MISMATCH", "reservation parent session differs from binding")
    if request.get("role") != agent:
        raise OmpBindingError("OMP_SPAWN_ROLE_MISMATCH", "reservation agent differs from bound role")

    normalized_input_digest = _digest(input_digest, "input_digest")
    normalized_reservation_id = reservation_id or f"reservation:{canonical_digest({'binding_ref': binding_ref, 'input_digest': normalized_input_digest})}"
    normalized_dispatch_ref: str | None = None
    payload: dict[str, Any] | None = None
    supplied_dispatch_digest = dispatch_envelope_digest or dispatch_input_digest
    if task_input is not None or dispatch_ref is not None or supplied_dispatch_digest is not None:
        if task_input is None or supplied_dispatch_digest is None:
            raise OmpBindingError(
                "OMP_SPAWN_DISPATCH_INPUT_REQUIRED",
                "stored dispatch requires task_input and dispatch_envelope_digest",
            )
        normalized_dispatch_ref = dispatch_ref or f"dispatch:{canonical_digest({'reservation_id': normalized_reservation_id, 'binding_ref': binding_ref, 'input_digest': normalized_input_digest})}"
        if not DISPATCH_REF_RE.fullmatch(normalized_dispatch_ref):
            raise OmpBindingError("OMP_SPAWN_DISPATCH_REF_INVALID", "dispatch_ref must be dispatch:<64 lowercase hex>")
        payload = _write_dispatch_payload(
            project_root,
            dispatch_ref=normalized_dispatch_ref,
            binding_ref=binding_ref,
            input_digest=normalized_input_digest,
            task_input=task_input,
        )

    core = {
        "schema": "bbk.spawn-reservation.v1",
        "reservation_id": normalized_reservation_id,
        "binding_ref": binding_ref,
        "parent_session_id": parent,
        "child_session_id": request.get("session_id"),
        "invocation_id": request.get("invocation_id"),
        "work_unit_id": request.get("work_unit_id"),
        "attempt_id": request.get("attempt_id"),
        "candidate_ref": request.get("candidate_ref"),
        "workspace_ref": request.get("workspace_ref"),
        "authority_ref": request.get("authority_ref"),
        "scope": request.get("scope"),
        "return_contract": request.get("return_contract"),
        "task_name": _text(task_name, "task_name"),
        "agent": _text(agent, "agent"),
        "tool_name": _text(tool_name, "tool_name"),
        "input_digest": normalized_input_digest,
        "binding_digest": binding.get("immutable_digest"),
    }
    if normalized_dispatch_ref is not None and payload is not None:
        normalized_envelope_digest = _digest(supplied_dispatch_digest, "dispatch_envelope_digest")
        core.update({
            "dispatch_ref": normalized_dispatch_ref,
            "dispatch_envelope_digest": normalized_envelope_digest,
            # Read compatibility for RC5/RC6 records and external tooling.  RC7
            # gives this alias the canonical normalized-envelope meaning.
            "dispatch_input_digest": normalized_envelope_digest,
            "dispatch_payload_digest": payload["payload_digest"],
        })
    receipt_id = f"sha256:{canonical_digest(core)}"
    receipt, _ = append_receipt(
        project_root,
        "SPAWN_RESERVATION",
        core,
        receipt_id=receipt_id,
        recorded_at=recorded_at,
    )
    return {**core, "receipt_ref": receipt["receipt_id"], "status": "RESERVED"}


def _reservations(project_root: str | Path, input_digest: str) -> list[dict[str, Any]]:
    expected = _digest(input_digest, "input_digest")
    return [
        receipt
        for receipt in all_receipts(project_root)
        if receipt.get("receipt_kind") == "SPAWN_RESERVATION"
        and receipt.get("content", {}).get("input_digest") == expected
    ]


def _reservations_by_dispatch(project_root: str | Path, dispatch_ref: str) -> list[dict[str, Any]]:
    if not isinstance(dispatch_ref, str) or not DISPATCH_REF_RE.fullmatch(dispatch_ref):
        raise OmpBindingError("OMP_SPAWN_DISPATCH_REF_INVALID", "dispatch_ref must be dispatch:<64 lowercase hex>")
    return [
        receipt
        for receipt in all_receipts(project_root)
        if receipt.get("receipt_kind") == "SPAWN_RESERVATION"
        and receipt.get("content", {}).get("dispatch_ref") == dispatch_ref
    ]


def _parse_time(value: str | None) -> dt.datetime:
    if not value:
        return dt.datetime.now(dt.timezone.utc)
    normalized = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise OmpBindingError("OMP_HOST_EVENT_INVALID", f"invalid timestamp {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _format_time(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _dispatch_reservation(project_root: str | Path, dispatch_ref: str) -> dict[str, Any]:
    matches = _reservations_by_dispatch(project_root, dispatch_ref)
    if not matches:
        raise OmpBindingError(
            "OMP_SPAWN_DISPATCH_NOT_FOUND",
            "no immutable spawn reservation matches the dispatch reference",
            smallest_next_action="Use the dispatch_input returned by the current BBK spawn/bind result.",
        )
    if len(matches) != 1:
        raise OmpBindingError("OMP_SPAWN_DISPATCH_AMBIGUOUS", "multiple reservations match one dispatch reference")
    return matches[0]


def _dispatch_receipts(project_root: str | Path, dispatch_ref: str, kinds: Iterable[str]) -> list[dict[str, Any]]:
    accepted = set(kinds)
    return sorted(
        [
            receipt
            for receipt in all_receipts(project_root)
            if receipt.get("receipt_kind") in accepted
            and receipt.get("content", {}).get("dispatch_ref") == dispatch_ref
        ],
        key=lambda item: (str(item.get("recorded_at") or ""), str(item.get("receipt_id") or "")),
    )


def _terminal_attempt_state(project_root: str | Path, reservation: Mapping[str, Any]) -> dict[str, Any] | None:
    work_unit = reservation.get("work_unit_id")
    attempt = reservation.get("attempt_id")
    records = sorted(
        [
            receipt
            for receipt in all_receipts(project_root)
            if receipt.get("receipt_kind") == "BEADS_COMMAND"
            and receipt.get("content", {}).get("command", {}).get("work_unit_id") == work_unit
            and receipt.get("content", {}).get("command", {}).get("attempt_id") == attempt
        ],
        key=lambda item: (str(item.get("recorded_at") or ""), str(item.get("receipt_id") or "")),
    )
    if not records:
        return None
    command = records[-1].get("content", {}).get("command", {})
    transition = str(command.get("transition") or "")
    if transition not in {"COMPLETE", "FAIL"}:
        return None
    return {
        "transition": transition,
        "receipt_ref": records[-1].get("receipt_id"),
    }


def dispatch_status(
    project_root: str | Path,
    *,
    dispatch_ref: str,
    parent_session_id: str | None = None,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Return the durable lifecycle state of one token-addressed spawn.

    ``READY`` and expired/released leases may be retried using the same token.
    ``LEASED`` means one native OMP task call is currently in flight.
    ``ACTIVATED`` binds the token to exactly one actual child session.
    ``TERMINAL`` is derived only from a current COMPLETE/FAIL coordination
    transition for the exact work-unit attempt.
    """
    reservation_receipt = _dispatch_reservation(project_root, dispatch_ref)
    reservation = reservation_receipt.get("content", {})
    if parent_session_id is not None and reservation.get("parent_session_id") != parent_session_id:
        raise OmpBindingError(
            "OMP_SPAWN_DISPATCH_PARENT_MISMATCH",
            "dispatch reservation does not belong to the active parent session",
        )
    base = {
        "schema": "bbk.dispatch-status.v1",
        "dispatch_ref": dispatch_ref,
        "reservation_ref": reservation_receipt.get("receipt_id"),
        "binding_ref": reservation.get("binding_ref"),
        "parent_session_id": reservation.get("parent_session_id"),
        "work_unit_id": reservation.get("work_unit_id"),
        "attempt_id": reservation.get("attempt_id"),
        "task_name": reservation.get("task_name"),
        "agent": reservation.get("agent"),
    }

    terminal = _terminal_attempt_state(project_root, reservation)
    explicit_terminals = _dispatch_receipts(project_root, dispatch_ref, {"SPAWN_DISPATCH_TERMINAL"})
    if len(explicit_terminals) > 1:
        raise OmpBindingError("OMP_SPAWN_DISPATCH_TERMINAL_AMBIGUOUS", "dispatch has multiple terminal receipts")
    activations = _dispatch_receipts(project_root, dispatch_ref, {"SPAWN_SESSION_ACTIVATION"})
    if terminal and not activations:
        return {**base, "status": "TERMINAL", "terminal": terminal}
    if activations:
        if len(activations) != 1:
            raise OmpBindingError("OMP_SPAWN_ACTIVATION_AMBIGUOUS", "dispatch has multiple activation receipts")
        content = activations[0].get("content", {})
        explicit_terminal = explicit_terminals[0] if explicit_terminals else None
        return {
            **base,
            "status": "TERMINAL" if (terminal or explicit_terminal) else "ACTIVATED",
            "activation_ref": activations[0].get("receipt_id"),
            "active_binding_ref": content.get("active_binding_ref"),
            "actual_session_id": content.get("actual_session_id"),
            "tool_call_id": content.get("tool_call_id"),
            **({"terminal": terminal} if terminal else {}),
            **({
                "terminal_ref": explicit_terminal.get("receipt_id"),
                "terminal_outcome": explicit_terminal.get("content", {}).get("outcome"),
            } if explicit_terminal else {}),
        }

    leases = _dispatch_receipts(project_root, dispatch_ref, {"SPAWN_DISPATCH_LEASE"})
    releases = _dispatch_receipts(project_root, dispatch_ref, {"SPAWN_DISPATCH_RELEASE"})
    if leases:
        lease_receipt = leases[-1]
        lease = lease_receipt.get("content", {})
        released = any(
            release.get("content", {}).get("lease_ref") == lease_receipt.get("receipt_id")
            for release in releases
        )
        now = _parse_time(observed_at)
        expires_at = _parse_time(str(lease.get("expires_at") or ""))
        if not released and now < expires_at:
            return {
                **base,
                "status": "LEASED",
                "lease_ref": lease_receipt.get("receipt_id"),
                "tool_call_id": lease.get("tool_call_id"),
                "leased_at": lease.get("leased_at"),
                "expires_at": lease.get("expires_at"),
            }
    return {**base, "status": "READY"}


def _acquire_dispatch_lease(
    project_root: str | Path,
    *,
    dispatch_ref: str,
    reservation_receipt: Mapping[str, Any],
    parent_session_id: str,
    tool_call_id: str,
    host_version: str,
    observed_at: str | None = None,
) -> dict[str, Any]:
    current = dispatch_status(
        project_root,
        dispatch_ref=dispatch_ref,
        parent_session_id=parent_session_id,
        observed_at=observed_at,
    )
    call_id = _text(tool_call_id, "tool_call_id")
    if current["status"] == "ACTIVATED":
        raise OmpBindingError(
            "OMP_SPAWN_DISPATCH_ALREADY_ACTIVATED",
            "dispatch already activated exactly one child session",
            smallest_next_action="Use bbk_control_dispatch_status and consume the existing child result; do not respawn the attempt.",
        )
    if current["status"] == "TERMINAL":
        raise OmpBindingError(
            "OMP_SPAWN_DISPATCH_TERMINAL",
            "logical attempt is terminal and cannot be dispatched again",
            smallest_next_action="Create a genuinely new attempt_id only when the governing workflow authorizes a successor attempt.",
        )
    if current["status"] == "LEASED":
        if current.get("tool_call_id") == call_id:
            return {
                "lease_ref": current.get("lease_ref"),
                "leased_at": current.get("leased_at"),
                "expires_at": current.get("expires_at"),
                "idempotent_reuse": True,
            }
        raise OmpBindingError(
            "OMP_SPAWN_DISPATCH_LEASED",
            "dispatch is already leased to another in-flight native task call",
            smallest_next_action="Wait for activation or lease expiry, then query bbk_control_dispatch_status; do not create another binding.",
        )

    now = _parse_time(observed_at)
    expires = now + dt.timedelta(seconds=DISPATCH_LEASE_SECONDS)
    reservation = reservation_receipt.get("content", {})
    core = {
        "schema": "bbk.spawn-dispatch-lease.v1",
        "dispatch_ref": dispatch_ref,
        "reservation_ref": reservation_receipt.get("receipt_id"),
        "binding_ref": reservation.get("binding_ref"),
        "parent_session_id": parent_session_id,
        "tool_call_id": call_id,
        "host_version": host_version,
        "leased_at": _format_time(now),
        "expires_at": _format_time(expires),
        "status": "LEASED",
    }
    receipt_id = f"sha256:{canonical_digest(core)}"
    receipt, _ = append_receipt(
        project_root,
        "SPAWN_DISPATCH_LEASE",
        core,
        receipt_id=receipt_id,
        recorded_at=_format_time(now),
    )
    return {
        "lease_ref": receipt.get("receipt_id"),
        "leased_at": core["leased_at"],
        "expires_at": core["expires_at"],
        "idempotent_reuse": False,
    }


def release_spawn_dispatch(
    project_root: str | Path,
    *,
    dispatch_ref: str,
    tool_call_id: str,
    reason: str,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Return an unactivated dispatch lease to READY after host launch failure."""
    current = dispatch_status(project_root, dispatch_ref=dispatch_ref, observed_at=observed_at)
    call_id = _text(tool_call_id, "tool_call_id")
    if current["status"] == "ACTIVATED" or current["status"] == "TERMINAL":
        return {**current, "released": False, "idempotent_reuse": True}
    if current["status"] == "READY":
        return {**current, "released": False, "idempotent_reuse": True}
    if current.get("tool_call_id") != call_id:
        raise OmpBindingError(
            "OMP_SPAWN_DISPATCH_LEASE_MISMATCH",
            "only the tool call that owns the active lease may release it",
        )
    normalized_reason = str(reason or "HOST_TASK_LAUNCH_FAILED").strip()
    if not normalized_reason or len(normalized_reason.encode("utf-8")) > 256:
        raise OmpBindingError("OMP_HOST_EVENT_INVALID", "release reason must be 1-256 UTF-8 bytes")
    now = _parse_time(observed_at)
    core = {
        "schema": "bbk.spawn-dispatch-release.v1",
        "dispatch_ref": dispatch_ref,
        "lease_ref": current.get("lease_ref"),
        "tool_call_id": call_id,
        "reason": normalized_reason,
        "released_at": _format_time(now),
        "status": "READY",
    }
    receipt_id = f"sha256:{canonical_digest(core)}"
    receipt, _ = append_receipt(
        project_root,
        "SPAWN_DISPATCH_RELEASE",
        core,
        receipt_id=receipt_id,
        recorded_at=_format_time(now),
    )
    return {
        **dispatch_status(project_root, dispatch_ref=dispatch_ref, observed_at=_format_time(now)),
        "release_ref": receipt.get("receipt_id"),
        "released": True,
        "idempotent_reuse": False,
    }


def mark_spawn_dispatch_terminal(
    project_root: str | Path,
    *,
    dispatch_ref: str,
    actual_session_id: str,
    outcome: str,
    reason: str = "",
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Record terminal child completion without permitting another spawn.

    Host lifecycle evidence is distinct from semantic WorkUnit completion.
    This record only establishes that the one activated child session ended;
    the control plane remains responsible for product-state transitions.
    """
    current = dispatch_status(project_root, dispatch_ref=dispatch_ref, observed_at=observed_at)
    normalized_outcome = str(outcome or "").strip().upper()
    if normalized_outcome not in {"COMPLETED", "FAILED", "CANCELLED"}:
        raise OmpBindingError(
            "OMP_SPAWN_DISPATCH_TERMINAL_OUTCOME_INVALID",
            "terminal outcome must be COMPLETED, FAILED, or CANCELLED",
        )
    session = _text(actual_session_id, "actual_session_id")
    if current.get("status") in {"READY", "LEASED"}:
        raise OmpBindingError(
            "OMP_SPAWN_DISPATCH_NOT_ACTIVATED",
            "a dispatch cannot become terminal before exact child activation",
        )
    if current.get("actual_session_id") != session:
        raise OmpBindingError(
            "OMP_SPAWN_DISPATCH_SESSION_MISMATCH",
            "terminal session does not match the activated child",
        )
    existing = _dispatch_receipts(project_root, dispatch_ref, {"SPAWN_DISPATCH_TERMINAL"})
    if existing:
        if len(existing) != 1:
            raise OmpBindingError("OMP_SPAWN_DISPATCH_TERMINAL_AMBIGUOUS", "dispatch has multiple terminal receipts")
        content = existing[0].get("content", {})
        if content.get("actual_session_id") != session or content.get("outcome") != normalized_outcome:
            raise OmpBindingError(
                "OMP_SPAWN_DISPATCH_TERMINAL_CONFLICT",
                "dispatch was already closed with a different terminal outcome",
            )
        return {**content, "receipt_ref": existing[0].get("receipt_id"), "idempotent_reuse": True}
    normalized_reason = str(reason or "").strip()
    if len(normalized_reason.encode("utf-8")) > 512:
        raise OmpBindingError("OMP_HOST_EVENT_INVALID", "terminal reason exceeds 512 UTF-8 bytes")
    now = _parse_time(observed_at)
    core = {
        "schema": "bbk.spawn-dispatch-terminal.v1",
        "dispatch_ref": dispatch_ref,
        "activation_ref": current.get("activation_ref"),
        "active_binding_ref": current.get("active_binding_ref"),
        "actual_session_id": session,
        "outcome": normalized_outcome,
        "reason": normalized_reason,
        "terminal_at": _format_time(now),
        "status": "TERMINAL",
    }
    receipt_id = f"sha256:{canonical_digest(core)}"
    receipt, _ = append_receipt(
        project_root,
        "SPAWN_DISPATCH_TERMINAL",
        core,
        receipt_id=receipt_id,
        recorded_at=_format_time(now),
    )
    return {**core, "receipt_ref": receipt.get("receipt_id"), "idempotent_reuse": False}


def admit_spawn(
    project_root: str | Path,
    *,
    input_digest: str,
    parent_session_id: str,
    task_name: str,
    agent: str,
    tool_call_id: str,
    host_version: str,
    lease_ref: str | None = None,
    lease_expires_at: str | None = None,
    observed_at: str | None = None,
) -> dict[str, Any]:
    matches = _reservations(project_root, input_digest)
    if not matches:
        raise OmpBindingError(
            "OMP_SPAWN_BINDING_REQUIRED",
            "no immutable spawn reservation matches the exact task input",
            smallest_next_action="Create a complete bound spawn reservation before invoking the task tool.",
        )
    if len(matches) > 1:
        raise OmpBindingError("OMP_SPAWN_RESERVATION_AMBIGUOUS", "multiple reservations match the same task input")
    reservation_receipt = matches[0]
    reservation = reservation_receipt["content"]
    expected = {
        "parent_session_id": parent_session_id,
        "task_name": task_name,
        "agent": agent,
    }
    mismatched = [field for field, value in expected.items() if reservation.get(field) != value]
    if mismatched:
        raise OmpBindingError(
            "OMP_SPAWN_RESERVATION_MISMATCH",
            f"task call differs from reservation fields: {', '.join(mismatched)}",
        )
    binding = resolve_binding(project_root, binding_id=reservation["binding_ref"])
    if binding is None or binding.get("immutable_digest") != reservation.get("binding_digest"):
        raise OmpBindingError("OMP_SPAWN_BINDING_STALE", "reserved binding is missing, superseded, or changed")
    boundary = enforcement_boundary(host_version, "SPAWN_ADMISSION")
    if boundary != "ENFORCED":
        raise OmpBindingError(
            "OMP_HOST_UNQUALIFIED_FOR_SPAWN",
            f"host {host_version!r} has enforcement boundary {boundary}, not ENFORCED",
            smallest_next_action="Use the qualified OMP 16.4.8 host or re-qualify the changed host before writable execution.",
        )

    existing = [
        receipt
        for receipt in all_receipts(project_root)
        if receipt.get("receipt_kind") == "SPAWN_ADMISSION"
        and receipt.get("content", {}).get("reservation_ref") == reservation_receipt["receipt_id"]
    ]
    call_id = _text(tool_call_id, "tool_call_id")
    for receipt in existing:
        content = receipt.get("content", {})
        if content.get("tool_call_id") != call_id:
            continue
        # A released/expired compact lease may be retried under the same host
        # call identity.  Reuse only the admission bound to the current lease;
        # otherwise emit a successor admission for the same immutable token.
        if reservation.get("dispatch_ref") is None or content.get("lease_ref") == lease_ref:
            return {**content, "receipt_ref": receipt["receipt_id"], "idempotent_reuse": True}
    if existing and reservation.get("dispatch_ref") is None:
        raise OmpBindingError(
            "OMP_SPAWN_RESERVATION_ALREADY_CONSUMED",
            "spawn reservation was already admitted for a different tool call",
        )
    if reservation.get("dispatch_ref") is not None:
        current = dispatch_status(
            project_root,
            dispatch_ref=str(reservation.get("dispatch_ref")),
            parent_session_id=parent_session_id,
            observed_at=observed_at,
        )
        if current.get("status") != "LEASED" or current.get("tool_call_id") != call_id:
            raise OmpBindingError(
                "OMP_SPAWN_DISPATCH_LEASE_REQUIRED",
                "compact dispatch admission requires the current lease for this exact tool call",
            )
        if lease_ref is not None and current.get("lease_ref") != lease_ref:
            raise OmpBindingError("OMP_SPAWN_DISPATCH_LEASE_MISMATCH", "admission lease reference is stale")

    core = {
        "schema": "bbk.spawn-admission.v1",
        "reservation_ref": reservation_receipt["receipt_id"],
        "binding_ref": reservation["binding_ref"],
        "input_digest": reservation["input_digest"],
        "parent_session_id": parent_session_id,
        "child_session_id": reservation.get("child_session_id"),
        "task_name": task_name,
        "agent": agent,
        "tool_call_id": call_id,
        "host_version": host_version,
        "enforcement_boundary": boundary,
        "status": "ADMITTED",
    }
    if lease_ref is not None:
        core["lease_ref"] = lease_ref
        core["lease_expires_at"] = lease_expires_at
    for field in ("dispatch_ref", "dispatch_envelope_digest", "dispatch_input_digest", "dispatch_payload_digest"):
        if reservation.get(field) is not None:
            core[field] = reservation[field]
    receipt_id = f"sha256:{canonical_digest(core)}"
    receipt, _ = append_receipt(
        project_root,
        "SPAWN_ADMISSION",
        core,
        receipt_id=receipt_id,
        recorded_at=observed_at or utc_now(),
    )
    return {**core, "receipt_ref": receipt["receipt_id"], "idempotent_reuse": False}


def admit_spawn_dispatch(
    project_root: str | Path,
    *,
    dispatch_ref: str,
    dispatch_envelope_digest: str | None = None,
    dispatch_input_digest: str | None = None,
    parent_session_id: str,
    task_name: str | None = None,
    agent: str | None = None,
    tool_call_id: str,
    host_version: str,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Resolve, lease, and admit a token-addressed compact dispatch."""
    reservation_receipt = _dispatch_reservation(project_root, dispatch_ref)
    reservation = reservation_receipt.get("content", {})
    supplied_digest = dispatch_envelope_digest or dispatch_input_digest
    if supplied_digest is None:
        raise OmpBindingError(
            "OMP_SPAWN_DISPATCH_INPUT_REQUIRED",
            "dispatch_envelope_digest is required at the normalized OMP hook boundary",
        )
    compact_digest = _digest(supplied_digest, "dispatch_envelope_digest")
    mismatched: list[str] = []
    expected_digest = reservation.get("dispatch_envelope_digest") or reservation.get("dispatch_input_digest")
    if expected_digest != compact_digest:
        mismatched.append("dispatch_envelope_digest")
    if reservation.get("parent_session_id") != parent_session_id:
        mismatched.append("parent_session_id")
    if task_name is not None and reservation.get("task_name") != task_name:
        mismatched.append("task_name")
    if agent is not None and reservation.get("agent") != agent:
        mismatched.append("agent")
    if mismatched:
        raise OmpBindingError(
            "OMP_SPAWN_DISPATCH_MISMATCH",
            f"compact dispatch call differs from reservation fields: {', '.join(mismatched)}",
        )
    # Resolve lifecycle before touching the private payload.  Activation removes
    # that payload deliberately, so a later duplicate native task call must be
    # classified as ALREADY_ACTIVATED rather than as missing private state.
    lease = _acquire_dispatch_lease(
        project_root,
        dispatch_ref=dispatch_ref,
        reservation_receipt=reservation_receipt,
        parent_session_id=parent_session_id,
        tool_call_id=tool_call_id,
        host_version=host_version,
        observed_at=observed_at,
    )
    try:
        payload = _load_dispatch_payload(project_root, reservation)
        admission = admit_spawn(
            project_root,
            input_digest=str(reservation.get("input_digest") or ""),
            parent_session_id=parent_session_id,
            task_name=str(reservation.get("task_name") or ""),
            agent=str(reservation.get("agent") or ""),
            tool_call_id=tool_call_id,
            host_version=host_version,
            lease_ref=str(lease.get("lease_ref") or ""),
            lease_expires_at=str(lease.get("expires_at") or ""),
            observed_at=observed_at,
        )
    except Exception:
        release_spawn_dispatch(
            project_root,
            dispatch_ref=dispatch_ref,
            tool_call_id=tool_call_id,
            reason="SPAWN_ADMISSION_FAILED",
            observed_at=observed_at,
        )
        raise
    return {
        **admission,
        "dispatch_ref": dispatch_ref,
        "dispatch_envelope_digest": compact_digest,
        "dispatch_input_digest": compact_digest,
        "lease_ref": lease.get("lease_ref"),
        "lease_expires_at": lease.get("expires_at"),
        "resolved_task_input": payload["task_input"],
        "resolved_task_input_digest": reservation["input_digest"],
    }

def _spawn_admissions_for_binding(project_root: str | Path, binding_ref: str) -> list[dict[str, Any]]:
    return [
        receipt
        for receipt in all_receipts(project_root)
        if receipt.get("receipt_kind") == "SPAWN_ADMISSION"
        and receipt.get("content", {}).get("binding_ref") == binding_ref
    ]


def _attempt_registrations_for_binding(project_root: str | Path, binding_ref: str) -> list[dict[str, Any]]:
    """Return the one immutable child registration accepted by spawn activation.

    Writable workers use ``WORK_UNIT_ATTEMPT_REGISTRATION``; candidate-bound
    reviewer/validator tasks use ``READ_ONLY_TASK_REGISTRATION``.  Both carry
    the same authenticated packet and exact task-input digests, while keeping
    their different effect contracts explicit in the durable receipt kind.
    """
    accepted_kinds = {"WORK_UNIT_ATTEMPT_REGISTRATION", "READ_ONLY_TASK_REGISTRATION"}
    return [
        receipt
        for receipt in all_receipts(project_root)
        if receipt.get("receipt_kind") in accepted_kinds
        and receipt.get("content", {}).get("planned_binding_ref") == binding_ref
    ]


def activate_spawn_session(
    project_root: str | Path,
    *,
    planned_binding_ref: str,
    actual_session_id: str,
    packet_digest: str,
    host_version: str,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Bind the one currently leased dispatch to OMP's actual child.

    Historical failed native task calls may leave admission receipts, but only
    the admission attached to the current dispatch lease can activate a child.
    This makes launch retry safe without allowing more than one activation for
    the logical work-unit attempt.
    """
    boundary = enforcement_boundary(host_version, "SPAWN_ADMISSION")
    if boundary != "ENFORCED":
        raise OmpBindingError(
            "OMP_HOST_UNQUALIFIED_FOR_SPAWN_ACTIVATION",
            f"host {host_version!r} has enforcement boundary {boundary}, not ENFORCED",
            smallest_next_action="Use the qualified OMP 16.4.8 host or re-qualify the changed host.",
        )
    actual_session = _text(actual_session_id, "actual_session_id")
    if actual_session.startswith(PLANNED_SESSION_PREFIX):
        raise OmpBindingError(
            "OMP_SPAWN_ACTUAL_SESSION_INVALID",
            "actual child session identity cannot use the planned-session namespace",
        )
    normalized_packet_digest = _digest(packet_digest, "packet_digest")

    prior_activations = _activation_receipts(project_root, planned_binding_ref)
    if prior_activations:
        if len(prior_activations) != 1:
            raise OmpBindingError(
                "OMP_SPAWN_ACTIVATION_AMBIGUOUS",
                f"planned binding {planned_binding_ref} has multiple activation receipts",
            )
        prior = prior_activations[0]
        content = prior.get("content", {})
        exact_retry = (
            content.get("actual_session_id") == actual_session
            and content.get("packet_digest") == normalized_packet_digest
            and content.get("host_version") == host_version
        )
        if not exact_retry:
            raise OmpBindingError(
                "OMP_SPAWN_SESSION_ALREADY_ACTIVATED",
                "logical attempt was already activated for a different child identity",
                smallest_next_action="Use the existing activated child; do not respawn the same logical attempt.",
            )
        active = resolve_binding(project_root, binding_id=str(content.get("active_binding_ref", "")))
        if active is None:
            raise OmpBindingError(
                "OMP_SPAWN_ACTIVE_BINDING_STALE",
                "activation successor is no longer the active binding",
            )
        return {
            **content,
            "receipt_ref": prior["receipt_id"],
            "binding": active,
            "idempotent_reuse": True,
        }

    planned = resolve_binding(project_root, binding_id=planned_binding_ref)
    if planned is None:
        raise OmpBindingError(
            "OMP_SPAWN_PLANNED_BINDING_NOT_ACTIVE",
            f"planned binding {planned_binding_ref} does not exist or was superseded",
        )
    request = dict(planned.get("request", {}))
    planned_session = str(request.get("session_id", ""))
    if not planned_session.startswith(PLANNED_SESSION_PREFIX):
        raise OmpBindingError(
            "OMP_SPAWN_PLANNED_SESSION_REQUIRED",
            "spawn activation requires a binding in the planned-session namespace",
        )

    registrations = _attempt_registrations_for_binding(project_root, planned_binding_ref)
    matching_registrations = [
        receipt
        for receipt in registrations
        if receipt.get("content", {}).get("packet_digest") == normalized_packet_digest
    ]
    if len(registrations) != 1 or len(matching_registrations) != 1:
        code = "OMP_WORKER_PACKET_REGISTRATION_REQUIRED" if not matching_registrations else "OMP_WORKER_PACKET_REGISTRATION_AMBIGUOUS"
        raise OmpBindingError(
            code,
            "planned binding requires exactly one immutable attempt registration "
            f"and one matching worker packet; registrations={len(registrations)}, "
            f"matches={len(matching_registrations)}",
        )
    registration_receipt = matching_registrations[0]
    registration = registration_receipt.get("content", {})
    dispatch_ref = registration.get("dispatch_ref")

    admissions = _spawn_admissions_for_binding(project_root, planned_binding_ref)
    if not admissions:
        raise OmpBindingError(
            "OMP_SPAWN_ADMISSION_REQUIRED",
            "planned binding has no admitted native task call",
        )
    lifecycle: dict[str, Any] | None = None
    if dispatch_ref is not None:
        lifecycle = dispatch_status(
            project_root,
            dispatch_ref=str(dispatch_ref),
            parent_session_id=str(request.get("parent_session_id") or ""),
            observed_at=observed_at,
        )
        if lifecycle.get("status") != "LEASED":
            raise OmpBindingError(
                "OMP_SPAWN_DISPATCH_LEASE_REQUIRED",
                f"spawn activation requires a current lease; observed {lifecycle.get('status')}",
                smallest_next_action="Retry the same dispatch_ref through one native task call, then activate the resulting child.",
            )
        admissions = [
            receipt for receipt in admissions
            if receipt.get("content", {}).get("dispatch_ref") == dispatch_ref
            and receipt.get("content", {}).get("tool_call_id") == lifecycle.get("tool_call_id")
            and receipt.get("content", {}).get("lease_ref") == lifecycle.get("lease_ref")
        ]
    if len(admissions) != 1:
        code = "OMP_SPAWN_ADMISSION_REQUIRED" if not admissions else "OMP_SPAWN_ADMISSION_AMBIGUOUS"
        raise OmpBindingError(
            code,
            f"planned binding requires exactly one current admitted task call; found {len(admissions)}",
        )
    admission_receipt = admissions[0]
    admission = admission_receipt.get("content", {})
    if admission.get("host_version") != host_version or admission.get("status") != "ADMITTED":
        raise OmpBindingError(
            "OMP_SPAWN_ADMISSION_HOST_MISMATCH",
            "spawn activation host/status differs from the immutable admission",
        )
    if registration.get("task_input_digest") != admission.get("input_digest"):
        raise OmpBindingError(
            "OMP_WORKER_PACKET_ADMISSION_MISMATCH",
            "attempt registration and admitted task call do not identify the same exact task input",
        )

    dispatch_payload_removed: bool | None = None
    if dispatch_ref is not None:
        registration_digest = registration.get("dispatch_envelope_digest") or registration.get("dispatch_input_digest")
        admission_digest = admission.get("dispatch_envelope_digest") or admission.get("dispatch_input_digest")
        dispatch_mismatches: list[str] = []
        if registration.get("dispatch_ref") != admission.get("dispatch_ref"):
            dispatch_mismatches.append("dispatch_ref")
        if registration_digest != admission_digest:
            dispatch_mismatches.append("dispatch_envelope_digest")
        if dispatch_mismatches:
            raise OmpBindingError(
                "OMP_WORKER_PACKET_DISPATCH_MISMATCH",
                f"attempt registration and admitted dispatch differ: {', '.join(dispatch_mismatches)}",
            )

    successor_request = {
        **request,
        "session_id": actual_session,
        "supersedes": planned_binding_ref,
    }
    active, _ = create_binding(
        project_root,
        successor_request,
        capability_ref=str(planned.get("capability_ref", "")),
        created_at=observed_at or utc_now(),
    )
    if dispatch_ref is not None:
        dispatch_payload_removed = _discard_dispatch_payload(project_root, str(dispatch_ref))
    core = {
        "schema": "bbk.spawn-session-activation.v1",
        "planned_binding_ref": planned_binding_ref,
        "active_binding_ref": active["binding_id"],
        "planned_session_id": planned_session,
        "actual_session_id": actual_session,
        "parent_session_id": request.get("parent_session_id"),
        "invocation_id": request.get("invocation_id"),
        "work_unit_id": request.get("work_unit_id"),
        "attempt_id": request.get("attempt_id"),
        "packet_digest": normalized_packet_digest,
        "attempt_registration_ref": registration_receipt["receipt_id"],
        "spawn_admission_ref": admission_receipt["receipt_id"],
        "tool_call_id": admission.get("tool_call_id"),
        "host_version": host_version,
        "status": "ACTIVATED",
    }
    if dispatch_ref is not None:
        core.update({
            "dispatch_ref": dispatch_ref,
            "dispatch_envelope_digest": registration.get("dispatch_envelope_digest") or registration.get("dispatch_input_digest"),
            "lease_ref": admission.get("lease_ref"),
            "dispatch_payload_removed": bool(dispatch_payload_removed),
        })
    receipt_id = f"sha256:{canonical_digest(core)}"
    receipt, _ = append_receipt(
        project_root,
        "SPAWN_SESSION_ACTIVATION",
        core,
        receipt_id=receipt_id,
        recorded_at=observed_at or utc_now(),
    )
    return {
        **core,
        "receipt_ref": receipt["receipt_id"],
        "binding": active,
        "idempotent_reuse": False,
    }


def _load_json_argument(value: str) -> dict[str, Any]:
    path = Path(value)
    try:
        parsed = json.loads(path.read_text(encoding="utf-8") if path.is_file() else value)
    except (OSError, json.JSONDecodeError) as exc:
        raise OmpBindingError("OMP_JSON_INPUT_INVALID", f"cannot load JSON input: {exc}") from exc
    if not isinstance(parsed, dict):
        raise OmpBindingError("OMP_JSON_INPUT_INVALID", "JSON input must be an object")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status")
    status.add_argument("--host-version", required=True)

    policy = sub.add_parser("binding-policy")
    policy.add_argument("--session-id", required=True)

    normalize = sub.add_parser("record-host-event")
    normalize.add_argument("--event", required=True, help="JSON object or path")
    normalize.add_argument("--binding-ref")
    normalize.add_argument("--post-effect", action="store_true")

    reserve = sub.add_parser("reserve-spawn")
    for name in ("binding-ref", "parent-session-id", "task-name", "agent", "input-digest"):
        reserve.add_argument(f"--{name}", required=True)
    reserve.add_argument("--tool-name", default="task")
    reserve.add_argument("--reservation-id")

    admit = sub.add_parser("admit-spawn")
    for name in (
        "input-digest", "parent-session-id", "task-name", "agent", "tool-call-id", "host-version"
    ):
        admit.add_argument(f"--{name}", required=True)
    admit.add_argument("--observed-at")

    dispatch = sub.add_parser("admit-dispatch")
    for name in ("dispatch-ref", "parent-session-id", "task-name", "agent", "tool-call-id", "host-version"):
        dispatch.add_argument(f"--{name}", required=True)
    dispatch.add_argument("--dispatch-envelope-digest")
    dispatch.add_argument("--dispatch-input-digest", help="RC5/RC6 compatibility alias")
    dispatch.add_argument("--observed-at")

    dispatch_state = sub.add_parser("dispatch-status")
    dispatch_state.add_argument("--dispatch-ref", required=True)
    dispatch_state.add_argument("--parent-session-id")
    dispatch_state.add_argument("--observed-at")

    release = sub.add_parser("release-dispatch")
    release.add_argument("--dispatch-ref", required=True)
    release.add_argument("--tool-call-id", required=True)
    release.add_argument("--reason", required=True)
    release.add_argument("--observed-at")

    terminal = sub.add_parser("terminal-dispatch")
    terminal.add_argument("--dispatch-ref", required=True)
    terminal.add_argument("--actual-session-id", required=True)
    terminal.add_argument("--outcome", required=True)
    terminal.add_argument("--reason", default="")
    terminal.add_argument("--observed-at")

    activate = sub.add_parser("activate-spawn")
    activate.add_argument("--planned-binding-ref", required=True)
    activate.add_argument("--actual-session-id", required=True)
    activate.add_argument("--packet-digest", required=True)
    activate.add_argument("--host-version", required=True)
    activate.add_argument("--observed-at")

    retain = sub.add_parser("retain-binding")
    retain.add_argument("--event-type", required=True)
    retain.add_argument("--binding-ref", required=True)
    retain.add_argument("--session-id", required=True)
    retain.add_argument("--invocation-id", required=True)
    retain.add_argument("--payload-digest", required=True)
    retain.add_argument("--observed-at")

    retry = sub.add_parser("retry-binding")
    retry.add_argument("--predecessor-ref", required=True)
    retry.add_argument("--request", required=True, help="JSON object or path")
    retry.add_argument("--capability-ref", required=True)
    retry.add_argument("--created-at")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "status":
            result: Any = enforcement_status(args.host_version)
        elif args.command == "binding-policy":
            result = binding_execution_policy(args.root, session_id=args.session_id)
        elif args.command == "record-host-event":
            receipt, created = record_host_event(
                args.root,
                _load_json_argument(args.event),
                binding_ref=args.binding_ref,
                pre_effect_blocking=not args.post_effect,
            )
            result = {"status": "PASS", "receipt": receipt, "created": created}
        elif args.command == "reserve-spawn":
            result = create_spawn_reservation(
                args.root,
                binding_ref=args.binding_ref,
                parent_session_id=args.parent_session_id,
                task_name=args.task_name,
                agent=args.agent,
                input_digest=args.input_digest,
                tool_name=args.tool_name,
                reservation_id=args.reservation_id,
            )
        elif args.command == "admit-spawn":
            result = admit_spawn(
                args.root,
                input_digest=args.input_digest,
                parent_session_id=args.parent_session_id,
                task_name=args.task_name,
                agent=args.agent,
                tool_call_id=args.tool_call_id,
                host_version=args.host_version,
                observed_at=args.observed_at,
            )
        elif args.command == "admit-dispatch":
            result = admit_spawn_dispatch(
                args.root,
                dispatch_ref=args.dispatch_ref,
                dispatch_envelope_digest=args.dispatch_envelope_digest,
                dispatch_input_digest=args.dispatch_input_digest,
                parent_session_id=args.parent_session_id,
                task_name=args.task_name,
                agent=args.agent,
                tool_call_id=args.tool_call_id,
                host_version=args.host_version,
                observed_at=args.observed_at,
            )
        elif args.command == "dispatch-status":
            result = dispatch_status(
                args.root,
                dispatch_ref=args.dispatch_ref,
                parent_session_id=args.parent_session_id,
                observed_at=args.observed_at,
            )
        elif args.command == "release-dispatch":
            result = release_spawn_dispatch(
                args.root,
                dispatch_ref=args.dispatch_ref,
                tool_call_id=args.tool_call_id,
                reason=args.reason,
                observed_at=args.observed_at,
            )
        elif args.command == "terminal-dispatch":
            result = mark_spawn_dispatch_terminal(
                args.root,
                dispatch_ref=args.dispatch_ref,
                actual_session_id=args.actual_session_id,
                outcome=args.outcome,
                reason=args.reason,
                observed_at=args.observed_at,
            )
        elif args.command == "activate-spawn":
            result = activate_spawn_session(
                args.root,
                planned_binding_ref=args.planned_binding_ref,
                actual_session_id=args.actual_session_id,
                packet_digest=args.packet_digest,
                host_version=args.host_version,
                observed_at=args.observed_at,
            )
        elif args.command == "retain-binding":
            result = retain_binding(
                args.root,
                event_type=args.event_type,
                binding_ref=args.binding_ref,
                session_id=args.session_id,
                invocation_id=args.invocation_id,
                payload_digest=args.payload_digest,
                observed_at=args.observed_at,
            )
        else:
            result, created = retry_binding(
                args.root,
                predecessor_ref=args.predecessor_ref,
                successor_request=_load_json_argument(args.request),
                capability_ref=args.capability_ref,
                created_at=args.created_at,
            )
            result = {"status": "PASS", "binding": result, "created": created}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (OmpBindingError, GovernanceStateError) as exc:
        code = getattr(exc, "code", "OMP_BINDING_ERROR")
        message = getattr(exc, "message", str(exc))
        next_action = getattr(exc, "smallest_next_action", "Inspect the typed error and retry with corrected input.")
        print(json.dumps({
            "status": "BLOCK",
            "reason_code": code,
            "message": message,
            "smallest_next_action": next_action,
        }, ensure_ascii=False, sort_keys=True))
        return 2


__all__ = [
    "OmpBindingError",
    "QUALIFIED_HOSTS",
    "PLANNED_SESSION_PREFIX",
    "activate_spawn_session",
    "admit_spawn",
    "admit_spawn_dispatch",
    "binding_execution_policy",
    "build_dispatch_task_input",
    "canonical_dispatch_envelope",
    "dispatch_envelope_digest",
    "dispatch_status",
    "mark_spawn_dispatch_terminal",
    "create_initial_binding",
    "create_spawn_reservation",
    "enforcement_boundary",
    "enforcement_status",
    "normalize_host_event",
    "parse_dispatch_ref",
    "record_host_event",
    "release_spawn_dispatch",
    "resolve_binding_reference",
    "retain_binding",
    "retry_binding",
]

if __name__ == "__main__":
    raise SystemExit(main())
