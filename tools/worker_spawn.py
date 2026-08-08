#!/usr/bin/env python3
"""Compile and register one fully bound writable OMP worker spawn.

The compiler is deliberately split from OMP's built-in ``task`` tool.  It
allocates the attempt's jj workspace/change, creates an immutable planned
binding, emits a worker packet, and reserves the exact task payload before the
host is permitted to spawn anything.  OMP's eventual child session identity is
bound separately by :func:`omp_binding_registry.activate_spawn_session` during
``before_agent_start``.

No authority is inferred from process CWD or free-form task prose.  Raw worker
assignment text is returned to the caller but is not persisted in governance
receipts; durable records contain only canonical digests and typed references.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from gate_kernel import canonical_digest
    from governed_state import all_receipts, append_receipt, utc_now
    from control_plane import ControlPlaneError, project_spawn_assignment
    from omp_binding_registry import (
        PLANNED_SESSION_PREFIX,
        OmpBindingError,
        build_dispatch_task_input,
        dispatch_envelope_digest,
        dispatch_status,
        create_initial_binding,
        create_spawn_reservation,
        resolve_binding_reference,
    )
    from substrate import beads_adapter, jj_adapter
except ImportError:  # pragma: no cover - installed-package import fallback
    from .gate_kernel import canonical_digest
    from .governed_state import all_receipts, append_receipt, utc_now
    from .control_plane import ControlPlaneError, project_spawn_assignment
    from .omp_binding_registry import (
        PLANNED_SESSION_PREFIX,
        OmpBindingError,
        build_dispatch_task_input,
        dispatch_envelope_digest,
        dispatch_status,
        create_initial_binding,
        create_spawn_reservation,
        resolve_binding_reference,
    )
    from .substrate import beads_adapter, jj_adapter

ROOT = Path(os.environ.get("BBK_PACKAGE_ROOT", Path(__file__).resolve().parents[1])).resolve()
CAPABILITY_ROOT = ROOT / "spec" / "role-capabilities"
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+\-]*$")
ROLE_RE = re.compile(r"^bbk_[A-Za-z0-9_]+$")
DIGEST_RE = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")
QUALIFIED_HOST_VERSION = "omp/16.4.8"
MAX_ASSIGNMENT_BYTES = 512 * 1024
REQUEST_FIELDS = frozenset(
    {
        "schema", "host_version", "parent_binding_ref", "parent_session_id",
        "parent_invocation_id", "task_name", "role", "work_unit_id", "attempt_id",
        "baseline_ref", "candidate_ref", "authority_ref", "return_contract",
        "parent_revision", "workspace_parent", "path_prefixes", "mutation_classes",
        "semantic_scope", "assignment", "description", "idempotency_key",
        "return_transport_mode", "material_transport_reason",
    }
)
PACKET_MARKER_PREFIX = "<bbk-bound-worker-packet "
PACKET_MARKER_RE = re.compile(
    r'^<bbk-bound-worker-packet planned-binding-ref="(?P<binding>[A-Za-z0-9._:/@+\-]+)" '
    r'packet-digest="(?P<digest>sha256:[0-9a-f]{64})">$',
)


class WorkerSpawnError(RuntimeError):
    """A bound-spawn request is incomplete, inconsistent, or unsafe."""

    def __init__(self, code: str, message: str, *, smallest_next_action: str = ""):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.smallest_next_action = smallest_next_action or "Correct the typed spawn request and retry."


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WorkerSpawnError("BOUND_SPAWN_INCOMPLETE", f"{field} must be a non-empty string")
    result = value.strip()
    if field not in {"assignment", "description", "workspace_parent", "project_root", "parent_revision"} and not SAFE_ID_RE.fullmatch(result):
        raise WorkerSpawnError("BOUND_SPAWN_ID_INVALID", f"{field} contains unsupported characters")
    return result


def _string_list(value: Any, field: str, *, safe_ids: bool = True) -> list[str]:
    if not isinstance(value, list) or not value:
        raise WorkerSpawnError("BOUND_SPAWN_INCOMPLETE", f"{field} must be a non-empty array")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise WorkerSpawnError("BOUND_SPAWN_INCOMPLETE", f"{field} entries must be non-empty strings")
        normalized = item.strip()
        if safe_ids and not SAFE_ID_RE.fullmatch(normalized):
            raise WorkerSpawnError("BOUND_SPAWN_ID_INVALID", f"{field} entry {normalized!r} is invalid")
        result.append(normalized)
    if len(result) != len(set(result)):
        raise WorkerSpawnError("BOUND_SPAWN_DUPLICATE_VALUE", f"{field} contains duplicates")
    return sorted(result)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkerSpawnError("BOUND_SPAWN_CAPABILITY_INVALID", f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkerSpawnError("BOUND_SPAWN_CAPABILITY_INVALID", f"{path} must contain an object")
    return value


def _capability(role: str, capability_root: str | Path | None = None) -> tuple[dict[str, Any], str, set[str]]:
    root = Path(os.environ.get("BBK_ROLE_CAPABILITY_ROOT") or capability_root or CAPABILITY_ROOT).resolve()
    path = root / f"{role}.json"
    if not path.is_file() or path.is_symlink():
        raise WorkerSpawnError("BOUND_SPAWN_CAPABILITY_NOT_FOUND", f"compiled capability manifest is missing for {role}")
    value = _read_json(path)
    if value.get("schema") != "bbk.role-capability.v1" or value.get("role") != role:
        raise WorkerSpawnError("BOUND_SPAWN_CAPABILITY_INVALID", f"{path} is not the capability for {role}")
    manifest_digest = f"sha256:{canonical_digest({key: item for key, item in value.items() if key != 'manifest_digest'})}"
    if value.get("manifest_digest") != manifest_digest:
        raise WorkerSpawnError("BOUND_SPAWN_CAPABILITY_DIGEST_MISMATCH", f"capability manifest digest is stale for {role}")
    policy_version = str(value.get("policy_version", ""))
    accepted_refs = {
        manifest_digest,
        f"role:{role}@{policy_version}",
        f"role:{role}@{policy_version}#{manifest_digest}",
    }
    return value, f"role:{role}@{policy_version}#{manifest_digest}", accepted_refs


def _validate_parent(
    project_root: Path,
    *,
    parent_binding_ref: str,
    parent_session_id: str,
    parent_invocation_id: str,
    capability_root: str | Path | None = None,
) -> dict[str, Any]:
    binding = resolve_binding_reference(project_root, parent_binding_ref)
    if binding is None:
        raise WorkerSpawnError("BOUND_SPAWN_PARENT_BINDING_NOT_ACTIVE", f"parent binding {parent_binding_ref} is not active")
    request = binding.get("request", {})
    if request.get("session_id") != parent_session_id or request.get("invocation_id") != parent_invocation_id:
        raise WorkerSpawnError(
            "BOUND_SPAWN_PARENT_CORRELATION_MISMATCH",
            "parent session/invocation do not match the active parent binding",
        )
    parent_role = str(request.get("role", ""))
    capability, _, accepted_refs = _capability(parent_role, capability_root)
    if str(binding.get("capability_ref", "")) not in accepted_refs:
        raise WorkerSpawnError(
            "BOUND_SPAWN_PARENT_CAPABILITY_BINDING_MISMATCH",
            f"parent binding does not identify the current capability manifest for {parent_role}",
        )
    if "bbk_control_spawn" not in capability.get("allowed_tools", []):
        raise WorkerSpawnError(
            "BOUND_SPAWN_PARENT_CAPABILITY_DENIED",
            f"{parent_role} is not permitted to use bbk_control_spawn",
        )
    return binding


def _relative_scope_paths(raw: Any) -> list[str]:
    values = _string_list(raw, "path_prefixes", safe_ids=False)
    normalized: list[str] = []
    for value in values:
        path = Path(value)
        if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
            raise WorkerSpawnError(
                "BOUND_SPAWN_SCOPE_INVALID",
                f"path scope {value!r} must be a clean workspace-relative path",
            )
        normalized.append(path.as_posix())
    return sorted(normalized)


def _validate_request(
    request: Mapping[str, Any],
    project_root: Path,
    *,
    capability_root: str | Path | None = None,
) -> dict[str, Any]:
    if not isinstance(request, Mapping) or request.get("schema") != "bbk.bound-worker-spawn-create.v1":
        raise WorkerSpawnError("BOUND_SPAWN_SCHEMA_INVALID", "request schema must be bbk.bound-worker-spawn-create.v1")
    unknown_fields = sorted(set(request) - REQUEST_FIELDS)
    if unknown_fields:
        raise WorkerSpawnError(
            "BOUND_SPAWN_SCHEMA_INVALID",
            f"request contains unsupported fields: {', '.join(unknown_fields)}",
        )
    required_text = (
        "host_version", "parent_binding_ref", "parent_session_id", "parent_invocation_id", "task_name", "role",
        "work_unit_id", "attempt_id", "baseline_ref", "candidate_ref", "authority_ref",
        "return_contract", "parent_revision", "workspace_parent", "assignment", "idempotency_key",
    )
    normalized = {field: _text(request.get(field), field) for field in required_text}
    normalized["description"] = str(request.get("description") or f"{normalized['work_unit_id']} {normalized['attempt_id']}").strip()
    normalized["mutation_classes"] = _string_list(request.get("mutation_classes"), "mutation_classes")
    normalized["semantic_scope"] = _string_list(request.get("semantic_scope") or [f"work-unit:{normalized['work_unit_id']}"], "semantic_scope")
    normalized["path_prefixes"] = _relative_scope_paths(request.get("path_prefixes"))
    transport_mode = str(request.get("return_transport_mode") or "STRUCTURED_RETURN_FIRST").strip().upper()
    allowed_transport_modes = {"STRUCTURED_RETURN_FIRST", "STRUCTURED_RETURN_ONLY", "SEALED_HANDOFF_REQUIRED"}
    if transport_mode not in allowed_transport_modes:
        raise WorkerSpawnError(
            "BOUND_SPAWN_RETURN_TRANSPORT_INVALID",
            f"return_transport_mode must be one of {', '.join(sorted(allowed_transport_modes))}",
        )
    material_reason = str(request.get("material_transport_reason") or "").strip()
    if transport_mode == "SEALED_HANDOFF_REQUIRED" and not material_reason:
        raise WorkerSpawnError(
            "BOUND_SPAWN_MATERIAL_TRANSPORT_REASON_REQUIRED",
            "SEALED_HANDOFF_REQUIRED requires a named material transport reason",
        )
    if transport_mode == "STRUCTURED_RETURN_ONLY" and material_reason:
        raise WorkerSpawnError(
            "BOUND_SPAWN_RETURN_TRANSPORT_CONTRADICTION",
            "STRUCTURED_RETURN_ONLY cannot declare a sealed-handoff transport reason",
        )
    normalized["return_transport_mode"] = transport_mode
    normalized["material_transport_reason"] = material_reason
    normalized["schema"] = "bbk.bound-worker-spawn-create.v1"

    if not ROLE_RE.fullmatch(normalized["role"]):
        raise WorkerSpawnError(
            "BOUND_SPAWN_ROLE_INVALID",
            "role must be one canonical bbk_<name> identifier",
        )

    if normalized["host_version"] != QUALIFIED_HOST_VERSION:
        raise WorkerSpawnError(
            "OMP_HOST_UNQUALIFIED_FOR_BOUND_SPAWN",
            f"host {normalized['host_version']!r} is not qualified for writable worker spawn",
            smallest_next_action="Use OMP 16.4.8 or re-qualify the changed host before compiling a writable child.",
        )
    if len(normalized["assignment"].encode("utf-8")) > MAX_ASSIGNMENT_BYTES:
        raise WorkerSpawnError(
            "BOUND_SPAWN_ASSIGNMENT_TOO_LARGE",
            f"assignment exceeds {MAX_ASSIGNMENT_BYTES} UTF-8 bytes",
        )

    workspace_parent_raw = Path(normalized["workspace_parent"]).expanduser()
    if not workspace_parent_raw.is_absolute():
        raise WorkerSpawnError(
            "BOUND_SPAWN_WORKSPACE_PARENT_INVALID",
            "workspace_parent must be explicit and absolute; process CWD is not authority",
        )
    if workspace_parent_raw.exists() and workspace_parent_raw.is_symlink():
        raise WorkerSpawnError(
            "BOUND_SPAWN_WORKSPACE_PARENT_INVALID",
            "workspace_parent cannot be a symlink",
        )
    workspace_parent = workspace_parent_raw.resolve()
    try:
        workspace_parent.relative_to(project_root.parent)
    except ValueError as exc:
        raise WorkerSpawnError(
            "BOUND_SPAWN_WORKSPACE_PARENT_INVALID",
            f"workspace_parent {workspace_parent} is outside the governed repository parent {project_root.parent}",
            smallest_next_action="Choose an explicit sibling/descendant attempt-workspace root; do not rely on CWD.",
        ) from exc
    if workspace_parent == project_root:
        raise WorkerSpawnError("BOUND_SPAWN_WORKSPACE_PARENT_INVALID", "attempt workspaces cannot overwrite the main project root")
    normalized["workspace_parent"] = str(workspace_parent)

    capability, capability_ref, _ = _capability(normalized["role"], capability_root)
    if capability.get("scope_rules", {}).get("workspace_source") != "REGISTRY_BINDING":
        raise WorkerSpawnError(
            "BOUND_SPAWN_ROLE_NOT_WRITABLE",
            f"{normalized['role']} does not use registry-bound writable workspaces",
        )
    allowed_classes = set(capability.get("allowed_mutation_classes", []))
    denied = sorted(set(normalized["mutation_classes"]) - allowed_classes)
    if denied:
        raise WorkerSpawnError(
            "BOUND_SPAWN_MUTATION_CLASS_DENIED",
            f"{normalized['role']} is not permitted mutation classes: {', '.join(denied)}",
        )
    required_bindings = set(capability.get("required_bindings", []))
    required_worker = {
        "SESSION", "INVOCATION", "WORK_UNIT", "ATTEMPT", "CANDIDATE", "WORKSPACE",
        "JJ_CHANGE", "AUTHORITY", "PATH_SCOPE", "MUTATION_CLASS", "RETURN_CONTRACT",
    }
    missing_contract = sorted(required_worker - required_bindings)
    if missing_contract:
        raise WorkerSpawnError(
            "BOUND_SPAWN_CAPABILITY_INCOMPLETE",
            f"worker capability omits required bindings: {', '.join(missing_contract)}",
        )
    normalized["capability_ref"] = capability_ref
    return normalized


def _compilation_receipts(project_root: Path, idempotency_key: str) -> list[dict[str, Any]]:
    return [
        receipt
        for receipt in all_receipts(project_root)
        if receipt.get("receipt_kind") == "WORK_UNIT_ATTEMPT_REGISTRATION"
        and receipt.get("content", {}).get("idempotency_key") == idempotency_key
    ]


def _logical_attempt_receipts(
    project_root: Path,
    *,
    parent_binding_ref: str,
    work_unit_id: str,
    attempt_id: str,
) -> list[dict[str, Any]]:
    return [
        receipt
        for receipt in all_receipts(project_root)
        if receipt.get("receipt_kind") == "WORK_UNIT_ATTEMPT_REGISTRATION"
        and receipt.get("content", {}).get("parent_binding_ref") == parent_binding_ref
        and receipt.get("content", {}).get("work_unit_id") == work_unit_id
        and receipt.get("content", {}).get("attempt_id") == attempt_id
    ]




def _reservation_ref_for_dispatch(project_root: Path, dispatch_ref: str) -> str:
    matches = [
        receipt for receipt in all_receipts(project_root)
        if receipt.get("receipt_kind") == "SPAWN_RESERVATION"
        and receipt.get("content", {}).get("dispatch_ref") == dispatch_ref
    ]
    if len(matches) != 1:
        code = "BOUND_SPAWN_RESERVATION_MISSING" if not matches else "BOUND_SPAWN_RESERVATION_AMBIGUOUS"
        raise WorkerSpawnError(code, f"dispatch {dispatch_ref} requires exactly one reservation; found {len(matches)}")
    return str(matches[0]["receipt_id"])

def _logical_request_digest(normalized: Mapping[str, Any]) -> str:
    semantic = {key: value for key, value in normalized.items() if key != "idempotency_key"}
    return f"sha256:{canonical_digest(semantic)}"


def _logical_attempt_ref(normalized: Mapping[str, Any]) -> str:
    return f"attempt:{canonical_digest({
        'parent_binding_ref': normalized['parent_binding_ref'],
        'work_unit_id': normalized['work_unit_id'],
        'attempt_id': normalized['attempt_id'],
    })}"


def _binding_context_from_registration(registration: Mapping[str, Any]) -> dict[str, Any]:
    fields = (
        "planned_binding_ref", "planned_session_id", "parent_binding_ref",
        "parent_session_id", "host_version", "invocation_id", "role",
        "work_unit_id", "attempt_id", "baseline_ref", "candidate_ref",
        "workspace_ref", "jj_change_id", "authority_ref", "scope",
        "return_contract", "return_transport_mode", "material_transport_reason",
        "capability_ref", "task_name", "assignment_digest",
    )
    return {
        "schema": "bbk.worker-packet-binding-context.v1",
        **{field: registration.get(field) for field in fields},
    }


def _result_from_registration(
    project_root: Path,
    registration_receipt: Mapping[str, Any],
    *,
    jj_path: str | Path | None,
    bd_path: str | Path | None,
    capability_root: str | Path | None,
) -> dict[str, Any]:
    registration = registration_receipt.get("content", {})
    packet_core = {
        "schema": "bbk.bound-worker-packet.v1",
        "planned_binding_ref": registration["planned_binding_ref"],
        "binding_context": _binding_context_from_registration(registration),
    }
    packet = {**packet_core, "packet_digest": registration["packet_digest"]}
    dispatch_input = build_dispatch_task_input(
        dispatch_ref=str(registration["dispatch_ref"]),
        task_name=str(registration["task_name"]),
        agent=str(registration["role"]),
    )
    canonical_dispatch_digest = dispatch_envelope_digest(dispatch_input)
    if canonical_dispatch_digest != (registration.get("dispatch_envelope_digest") or registration.get("dispatch_input_digest")):
        raise WorkerSpawnError(
            "BOUND_SPAWN_REGISTRATION_STALE",
            "stored attempt registration does not match the canonical Alpha.17 dispatch envelope",
        )
    identity = jj_adapter.identity(str(registration["workspace_ref"]), jj_path=jj_path)
    workspace = {
        "schema": "bbk.jj-attempt-workspace.v1",
        "status": "REUSED",
        "work_unit_id": registration["work_unit_id"],
        "attempt_id": registration["attempt_id"],
        "parent_revision": registration.get("parent_revision", ""),
        **identity,
    }
    assignment_projection = project_spawn_assignment(
        project_root,
        parent_binding_ref=str(registration["parent_binding_ref"]),
        attempt_registration_ref=str(registration_receipt["receipt_id"]),
        bd_path=bd_path,
        capability_root=capability_root,
    )
    lifecycle = dispatch_status(
        project_root,
        dispatch_ref=str(registration["dispatch_ref"]),
        parent_session_id=str(registration["parent_session_id"]),
    )
    status_by_lifecycle = {
        "READY": "READY_TO_DISPATCH",
        "LEASED": "DISPATCH_LEASED",
        "ACTIVATED": "ACTIVATED",
        "TERMINAL": "TERMINAL",
    }
    reservations = [
        item for item in all_receipts(project_root)
        if item.get("receipt_kind") == "SPAWN_RESERVATION"
        and item.get("content", {}).get("dispatch_ref") == registration.get("dispatch_ref")
    ]
    if len(reservations) != 1:
        raise WorkerSpawnError(
            "BOUND_SPAWN_RESERVATION_STATE_INVALID",
            f"logical attempt requires exactly one spawn reservation; observed {len(reservations)}",
        )
    return {
        "schema": "bbk.bound-worker-spawn.v1",
        "status": status_by_lifecycle.get(str(lifecycle.get("status")), "READY_TO_DISPATCH"),
        "dispatch_status": lifecycle,
        "logical_attempt_ref": registration.get("logical_attempt_ref"),
        "idempotent_reuse": True,
        "request_digest": registration.get("request_digest"),
        "logical_request_digest": registration.get("logical_request_digest"),
        "binding_created": False,
        "registration_created": False,
        "planned_binding_ref": registration["planned_binding_ref"],
        "planned_session_id": registration["planned_session_id"],
        "invocation_id": registration["invocation_id"],
        "workspace": workspace,
        "worker_packet": packet,
        "dispatch_ref": registration["dispatch_ref"],
        "dispatch_input": dispatch_input,
        "dispatch_envelope_digest": canonical_dispatch_digest,
        "dispatch_input_digest": canonical_dispatch_digest,
        "task_input_digest": registration["task_input_digest"],
        "attempt_registration_ref": registration_receipt["receipt_id"],
        "spawn_reservation_ref": registration.get("spawn_reservation_ref") or _reservation_ref_for_dispatch(
            project_root, str(registration["dispatch_ref"])
        ),
        "assignment_projection": assignment_projection,
    }


def packet_context(packet: Mapping[str, Any]) -> str:
    """Return authenticated shared context for OMP's batch task shape.

    The assignment remains in the native ``tasks[]`` item so OMP presents it as
    the child user message.  Only immutable binding data is placed in shared
    context, where ``before_agent_start`` can authenticate the marker before
    the first provider request.
    """
    marker = (
        f'{PACKET_MARKER_PREFIX}planned-binding-ref="{packet["planned_binding_ref"]}" '
        f'packet-digest="{packet["packet_digest"]}">'
    )
    machine = json.dumps(packet["binding_context"], ensure_ascii=False, sort_keys=True, indent=2)
    return (
        f"{marker}\n"
        "This invocation is governed only under the immutable BBK binding below. "
        "Use the exact binding, invocation, workspace, scope, mutation classes, authority, and return contract. "
        "Do not use process CWD as authority and do not mutate Beads directly.\n\n"
        "```json\n"
        f"{machine}\n"
        "```\n"
    )


# Backward-compatible private alias for any out-of-tree Alpha.17 prerelease callers.
_packet_context = packet_context


def parse_packet_marker(prompt: str) -> dict[str, str] | None:
    """Parse only the first-line activation marker from a task prompt."""
    if not isinstance(prompt, str) or not prompt:
        return None
    first = prompt.splitlines()[0].strip()
    match = PACKET_MARKER_RE.fullmatch(first)
    if not match:
        return None
    return {
        "planned_binding_ref": match.group("binding"),
        "packet_digest": match.group("digest"),
    }


def _compile_bound_spawn_unlocked(
    project_root: str | Path,
    request: Mapping[str, Any],
    *,
    jj_path: str | Path | None = None,
    bd_path: str | Path | None = None,
    capability_root: str | Path | None = None,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Allocate, assign, and register one exact writable worker attempt.

    Logical attempt identity is independent of a model-selected idempotency key.
    Exact retries reuse the existing workspace, binding, assignment projection,
    and dispatch token; changed content under the same logical attempt fails
    closed and requires a genuinely new attempt_id.
    """
    root = Path(project_root).resolve()
    if not root.is_dir():
        raise WorkerSpawnError("BOUND_SPAWN_PROJECT_ROOT_INVALID", f"project root does not exist: {root}")
    normalized = _validate_request(request, root, capability_root=capability_root)
    _validate_parent(
        root,
        parent_binding_ref=normalized["parent_binding_ref"],
        parent_session_id=normalized["parent_session_id"],
        parent_invocation_id=normalized["parent_invocation_id"],
        capability_root=capability_root,
    )
    request_digest = f"sha256:{canonical_digest(normalized)}"
    logical_request_digest = _logical_request_digest(normalized)
    logical_attempt_ref = _logical_attempt_ref(normalized)

    logical_prior = _logical_attempt_receipts(
        root,
        parent_binding_ref=normalized["parent_binding_ref"],
        work_unit_id=normalized["work_unit_id"],
        attempt_id=normalized["attempt_id"],
    )
    if len(logical_prior) > 1:
        raise WorkerSpawnError(
            "BOUND_SPAWN_LOGICAL_ATTEMPT_AMBIGUOUS",
            "logical attempt has multiple immutable registrations; preserve evidence and repair the registry before dispatch",
        )
    if logical_prior:
        previous = logical_prior[0].get("content", {})
        previous_logical = previous.get("logical_request_digest")
        compatible_legacy = (
            previous_logical is None
            and previous.get("idempotency_key") == normalized["idempotency_key"]
            and previous.get("request_digest") == request_digest
        )
        if previous_logical != logical_request_digest and not compatible_legacy:
            raise WorkerSpawnError(
                "BOUND_SPAWN_LOGICAL_ATTEMPT_CONFLICT",
                "the same parent/work-unit/attempt identity already exists with different immutable content",
                smallest_next_action="Use the existing attempt unchanged or allocate a genuinely new attempt_id; changing idempotency_key cannot create a duplicate.",
            )
        return _result_from_registration(
            root,
            logical_prior[0],
            jj_path=jj_path,
            bd_path=bd_path,
            capability_root=capability_root,
        )

    key_prior = _compilation_receipts(root, normalized["idempotency_key"])
    if len(key_prior) > 1:
        raise WorkerSpawnError("BOUND_SPAWN_IDEMPOTENCY_AMBIGUOUS", "idempotency key has multiple attempt registrations")
    if key_prior and key_prior[0].get("content", {}).get("request_digest") != request_digest:
        raise WorkerSpawnError(
            "BOUND_SPAWN_IDEMPOTENCY_COLLISION",
            "idempotency key was already used for different immutable spawn content",
        )

    workspace_name = jj_adapter.workspace_name_for_attempt(normalized["work_unit_id"], normalized["attempt_id"])
    workspace_path = Path(normalized["workspace_parent"]) / workspace_name
    workspace = jj_adapter.allocate_workspace(
        root,
        workspace_path,
        work_unit_id=normalized["work_unit_id"],
        attempt_id=normalized["attempt_id"],
        parent_revision=normalized["parent_revision"],
        description=normalized["description"],
        jj_path=jj_path,
        workspace_name=workspace_name,
    )
    workspace_resolved = Path(workspace["workspace_path"]).resolve()
    absolute_prefixes = [str((workspace_resolved / value).resolve()) for value in normalized["path_prefixes"]]
    for prefix in absolute_prefixes:
        try:
            Path(prefix).relative_to(workspace_resolved)
        except ValueError as exc:  # pragma: no cover
            raise WorkerSpawnError("BOUND_SPAWN_SCOPE_ESCAPE", f"compiled scope escapes workspace: {prefix}") from exc

    identity_core = {
        "logical_attempt_ref": logical_attempt_ref,
        "logical_request_digest": logical_request_digest,
        "workspace_path": str(workspace_resolved),
        "jj_change_id": workspace["jj_change_id"],
        "jj_commit_id": workspace["jj_commit_id"],
    }
    identity = canonical_digest(identity_core)
    planned_session = f"{PLANNED_SESSION_PREFIX}{identity}"
    invocation_id = f"invocation:{identity}"
    binding_request = {
        "schema": "bbk.invocation-binding-create.v1",
        "session_id": planned_session,
        "parent_session_id": normalized["parent_session_id"],
        "invocation_id": invocation_id,
        "role": normalized["role"],
        "work_unit_id": normalized["work_unit_id"],
        "attempt_id": normalized["attempt_id"],
        "baseline_ref": normalized["baseline_ref"],
        "candidate_ref": normalized["candidate_ref"],
        "workspace_ref": str(workspace_resolved),
        "authority_ref": normalized["authority_ref"],
        "scope": {
            "path_prefixes": absolute_prefixes,
            "mutation_classes": normalized["mutation_classes"],
            "semantic_scope": normalized["semantic_scope"],
        },
        "return_contract": normalized["return_contract"],
        "return_transport_mode": normalized["return_transport_mode"],
        "material_transport_reason": normalized["material_transport_reason"],
        "jj_change_id": workspace["jj_change_id"],
        "idempotency_key": f"spawn-binding:{canonical_digest({'logical_attempt_ref': logical_attempt_ref})}",
    }
    binding, binding_created = create_initial_binding(
        root, binding_request, capability_ref=normalized["capability_ref"], created_at=recorded_at,
    )
    binding_context = {
        "schema": "bbk.worker-packet-binding-context.v1",
        "planned_binding_ref": binding["binding_id"],
        "planned_session_id": planned_session,
        "parent_binding_ref": normalized["parent_binding_ref"],
        "parent_session_id": normalized["parent_session_id"],
        "host_version": normalized["host_version"],
        "invocation_id": invocation_id,
        "role": normalized["role"],
        "work_unit_id": normalized["work_unit_id"],
        "attempt_id": normalized["attempt_id"],
        "baseline_ref": normalized["baseline_ref"],
        "candidate_ref": normalized["candidate_ref"],
        "workspace_ref": str(workspace_resolved),
        "jj_change_id": workspace["jj_change_id"],
        "authority_ref": normalized["authority_ref"],
        "scope": binding_request["scope"],
        "return_contract": normalized["return_contract"],
        "return_transport_mode": normalized["return_transport_mode"],
        "material_transport_reason": normalized["material_transport_reason"],
        "capability_ref": normalized["capability_ref"],
        "task_name": normalized["task_name"],
        "assignment_digest": f"sha256:{canonical_digest(normalized['assignment'])}",
    }
    packet_core = {
        "schema": "bbk.bound-worker-packet.v1",
        "planned_binding_ref": binding["binding_id"],
        "binding_context": binding_context,
    }
    packet_digest = f"sha256:{canonical_digest(packet_core)}"
    packet = {**packet_core, "packet_digest": packet_digest}
    task_input = {
        "i": f"Spawn bound {normalized['role']} for {normalized['work_unit_id']} {normalized['attempt_id']}",
        "context": packet_context(packet),
        "tasks": [{"agent": normalized["role"], "name": normalized["task_name"], "task": normalized["assignment"].strip()}],
    }
    task_input_digest = f"sha256:{canonical_digest(task_input)}"
    dispatch_ref = f"dispatch:{canonical_digest({
        'logical_attempt_ref': logical_attempt_ref,
        'planned_binding_ref': binding['binding_id'],
        'parent_session_id': normalized['parent_session_id'],
        'task_input_digest': task_input_digest,
    })}"
    dispatch_input = build_dispatch_task_input(
        dispatch_ref=dispatch_ref, task_name=normalized["task_name"], agent=normalized["role"],
    )
    canonical_dispatch_digest = dispatch_envelope_digest(dispatch_input)
    reservation = create_spawn_reservation(
        root,
        binding_ref=binding["binding_id"],
        parent_session_id=normalized["parent_session_id"],
        task_name=normalized["task_name"],
        agent=normalized["role"],
        input_digest=task_input_digest,
        task_input=task_input,
        dispatch_envelope_digest=canonical_dispatch_digest,
        dispatch_ref=dispatch_ref,
        recorded_at=recorded_at,
    )

    registration_core = {
        "schema": "bbk.work-unit-attempt-registration.v1",
        "idempotency_key": normalized["idempotency_key"],
        "request_digest": request_digest,
        "logical_attempt_ref": logical_attempt_ref,
        "logical_request_digest": logical_request_digest,
        "planned_binding_ref": binding["binding_id"],
        "planned_session_id": planned_session,
        "parent_binding_ref": normalized["parent_binding_ref"],
        "parent_session_id": normalized["parent_session_id"],
        "parent_invocation_id": normalized["parent_invocation_id"],
        "host_version": normalized["host_version"],
        "invocation_id": invocation_id,
        "role": normalized["role"],
        "work_unit_id": normalized["work_unit_id"],
        "attempt_id": normalized["attempt_id"],
        "baseline_ref": normalized["baseline_ref"],
        "candidate_ref": normalized["candidate_ref"],
        "parent_revision": normalized["parent_revision"],
        "workspace_ref": str(workspace_resolved),
        "jj_change_id": workspace["jj_change_id"],
        "jj_commit_id": workspace["jj_commit_id"],
        "authority_ref": normalized["authority_ref"],
        "scope": binding_request["scope"],
        "return_contract": normalized["return_contract"],
        "return_transport_mode": normalized["return_transport_mode"],
        "material_transport_reason": normalized["material_transport_reason"],
        "capability_ref": normalized["capability_ref"],
        "task_name": normalized["task_name"],
        "assignment_digest": binding_context["assignment_digest"],
        "packet_digest": packet_digest,
        "task_input_digest": task_input_digest,
        "dispatch_ref": dispatch_ref,
        "dispatch_envelope_digest": canonical_dispatch_digest,
        "dispatch_input_digest": canonical_dispatch_digest,
        "spawn_reservation_ref": reservation["receipt_ref"],
        "status": "REGISTERED",
    }
    registration_id = f"sha256:{canonical_digest(registration_core)}"
    registration_content = {**registration_core, "registration_id": registration_id}
    registration, registration_created = append_receipt(
        root, "WORK_UNIT_ATTEMPT_REGISTRATION", registration_content,
        receipt_id=registration_id, recorded_at=recorded_at or utc_now(),
    )
    # Assignment is a spawn-compiler effect, not a second model-authored step.
    assignment_projection = project_spawn_assignment(
        root,
        parent_binding_ref=normalized["parent_binding_ref"],
        attempt_registration_ref=registration["receipt_id"],
        bd_path=bd_path,
        capability_root=capability_root,
    )
    return {
        "schema": "bbk.bound-worker-spawn.v1",
        "status": "READY_TO_DISPATCH",
        "dispatch_status": dispatch_status(root, dispatch_ref=dispatch_ref, parent_session_id=normalized["parent_session_id"]),
        "logical_attempt_ref": logical_attempt_ref,
        "idempotent_reuse": False,
        "request_digest": request_digest,
        "logical_request_digest": logical_request_digest,
        "binding_created": binding_created,
        "registration_created": registration_created,
        "planned_binding_ref": binding["binding_id"],
        "planned_session_id": planned_session,
        "invocation_id": invocation_id,
        "workspace": workspace,
        "worker_packet": packet,
        "dispatch_ref": dispatch_ref,
        "dispatch_input": dispatch_input,
        "dispatch_envelope_digest": canonical_dispatch_digest,
        "dispatch_input_digest": canonical_dispatch_digest,
        "task_input_digest": task_input_digest,
        "attempt_registration_ref": registration["receipt_id"],
        "spawn_reservation_ref": reservation["receipt_ref"],
        "assignment_projection": assignment_projection,
    }

@contextlib.contextmanager
def _spawn_preparation_lock(project_root: str | Path):
    """Serialize complete spawn preparation while preserving parallel children.

    jj workspace allocation, immutable registration, and the initial Beads
    assignment form one control-plane transaction.  Concurrent orchestrator
    calls wait for this bounded lock instead of racing and manufacturing a
    second logical attempt.  The lock is released before native OMP task
    dispatch, so independent child execution remains parallel.
    """
    root = Path(project_root).resolve()
    locks = root / ".bbk" / "governance" / "locks"
    locks.mkdir(parents=True, exist_ok=True)
    if locks.is_symlink() or not locks.is_dir():
        raise WorkerSpawnError("BOUND_SPAWN_LOCK_PATH_UNSAFE", f"unsafe spawn lock directory {locks}")
    lock = locks / "spawn-preparation.lock"
    try:
        wait_seconds = float(os.environ.get("BBK_SPAWN_PREPARATION_WAIT_SECONDS", "60"))
        poll_seconds = float(os.environ.get("BBK_SPAWN_PREPARATION_POLL_SECONDS", "0.05"))
        stale_seconds = float(os.environ.get("BBK_SPAWN_PREPARATION_STALE_SECONDS", "300"))
    except ValueError as exc:
        raise WorkerSpawnError("BOUND_SPAWN_LOCK_CONFIG_INVALID", "spawn lock timings must be numeric") from exc
    if wait_seconds < 0 or poll_seconds <= 0 or stale_seconds <= 0:
        raise WorkerSpawnError("BOUND_SPAWN_LOCK_CONFIG_INVALID", "spawn wait must be non-negative and poll/stale positive")
    deadline = time.monotonic() + wait_seconds
    fd = None
    while fd is None:
        try:
            fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            try:
                age = time.time() - lock.stat().st_mtime
            except FileNotFoundError:
                continue
            if age >= stale_seconds:
                stale = lock.with_name(f"spawn-preparation.lock.stale-{int(time.time())}")
                try:
                    os.replace(lock, stale)
                except FileNotFoundError:
                    pass
                continue
            if time.monotonic() >= deadline:
                raise WorkerSpawnError(
                    "BOUND_SPAWN_PREPARATION_TIMEOUT",
                    f"timed out after {wait_seconds:g}s waiting for spawn preparation lock {lock}",
                    smallest_next_action="Query existing logical-attempt and dispatch status; do not create another attempt.",
                ) from exc
            time.sleep(min(poll_seconds, max(0.0, deadline - time.monotonic())))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(json.dumps({"pid": os.getpid(), "acquired_at": utc_now()}, sort_keys=True))
            stream.flush()
            os.fsync(stream.fileno())
        yield
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def compile_bound_spawn(
    project_root: str | Path,
    request: Mapping[str, Any],
    *,
    jj_path: str | Path | None = None,
    bd_path: str | Path | None = None,
    capability_root: str | Path | None = None,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Serialize one complete control-plane preparation transaction."""
    with _spawn_preparation_lock(project_root):
        return _compile_bound_spawn_unlocked(
            project_root,
            request,
            jj_path=jj_path,
            bd_path=bd_path,
            capability_root=capability_root,
            recorded_at=recorded_at,
        )


def _load_json_argument(value: str) -> dict[str, Any]:
    if value == "-":
        raw = sys.stdin.read()
    else:
        path = Path(value)
        raw = path.read_text(encoding="utf-8") if path.is_file() else value
    try:
        parsed = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkerSpawnError("BOUND_SPAWN_JSON_INVALID", f"cannot load request JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise WorkerSpawnError("BOUND_SPAWN_JSON_INVALID", "request JSON must be an object")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    compile_parser = sub.add_parser("compile")
    compile_parser.add_argument("--request", required=True, help="JSON object, file path, or - for stdin")
    compile_parser.add_argument("--jj", default=os.environ.get("BBK_JJ"))
    compile_parser.add_argument("--bd", default=os.environ.get("BBK_BD"))
    compile_parser.add_argument("--recorded-at")
    parse_parser = sub.add_parser("parse-marker")
    parse_parser.add_argument("--prompt", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "compile":
            result = compile_bound_spawn(
                args.root,
                _load_json_argument(args.request),
                jj_path=args.jj,
                bd_path=args.bd,
                recorded_at=args.recorded_at,
            )
        else:
            result = {"status": "PASS", "marker": parse_packet_marker(args.prompt)}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (WorkerSpawnError, OmpBindingError, ControlPlaneError, jj_adapter.JjAdapterError, beads_adapter.BeadsAdapterError) as exc:
        code = getattr(exc, "code", "BOUND_SPAWN_FAILED")
        message = getattr(exc, "message", str(exc))
        action = getattr(exc, "smallest_next_action", "Correct the typed request and retry.")
        print(json.dumps({
            "schema": "bbk.bound-worker-spawn-error.v1",
            "status": "BLOCK",
            "reason_code": code,
            "message": message,
            "smallest_next_action": action,
        }, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
