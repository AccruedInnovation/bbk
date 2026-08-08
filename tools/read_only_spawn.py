#!/usr/bin/env python3
"""Compile one immutable, read-only OMP child task against a frozen candidate.

Unlike writable worker spawn, this adapter allocates no workspace and creates
no jj change.  It binds a reviewer/validator-style role to an existing exact
candidate workspace, freezes that candidate through the real Git/jj substrate,
reserves the exact OMP task payload, and emits an authenticated packet before
OMP may spawn the child.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from gate_kernel import canonical_digest
    from governed_state import all_receipts, append_receipt, utc_now
    from omp_binding_registry import (
        PLANNED_SESSION_PREFIX,
        OmpBindingError,
        build_dispatch_task_input,
        dispatch_envelope_digest,
        create_initial_binding,
        dispatch_status,
        create_spawn_reservation,
        resolve_binding_reference,
    )
    from substrate import git_adapter, jj_adapter
    from worker_spawn import packet_context
except ImportError:  # pragma: no cover - installed-package import fallback
    from .gate_kernel import canonical_digest
    from .governed_state import all_receipts, append_receipt, utc_now
    from .omp_binding_registry import (
        PLANNED_SESSION_PREFIX,
        OmpBindingError,
        build_dispatch_task_input,
        dispatch_envelope_digest,
        create_initial_binding,
        dispatch_status,
        create_spawn_reservation,
        resolve_binding_reference,
    )
    from .substrate import git_adapter, jj_adapter
    from .worker_spawn import packet_context

ROOT = Path(os.environ.get("BBK_PACKAGE_ROOT", Path(__file__).resolve().parents[1])).resolve()
CAPABILITY_ROOT = ROOT / "spec" / "role-capabilities"
QUALIFIED_HOST_VERSION = "omp/16.4.8"
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+\-]*$")
ROLE_RE = re.compile(r"^bbk_[A-Za-z0-9_]+$")
MAX_ASSIGNMENT_BYTES = 512 * 1024
REQUEST_FIELDS = frozenset({
    "schema", "host_version", "parent_binding_ref", "parent_session_id", "parent_invocation_id",
    "task_name", "role", "work_unit_id", "attempt_id", "baseline_ref", "candidate_id",
    "authority_ref", "return_contract", "workspace_ref", "path_prefixes", "semantic_scope",
    "assignment", "description", "idempotency_key", "candidate_admission_ref",
})
MUTATING_TOOLS = frozenset({
    "bbk_governed_write", "bbk_governed_edit", "bbk_governed_delete", "bbk_task_run",
    "bbk_control_bind", "bbk_control_spawn", "bbk_control_assign", "bbk_control_update",
    "bbk_control_integrate_request",
})


class ReadOnlySpawnError(RuntimeError):
    """A read-only child binding request is incomplete, stale, or unsafe."""

    def __init__(self, code: str, message: str, *, smallest_next_action: str = ""):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.smallest_next_action = smallest_next_action or "Correct the typed read-only binding request and retry."


def _text(value: Any, field: str, *, free_text: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReadOnlySpawnError("CONTROL_BIND_INCOMPLETE", f"{field} must be a non-empty string")
    result = value.strip()
    if not free_text and not SAFE_ID_RE.fullmatch(result):
        raise ReadOnlySpawnError("CONTROL_BIND_ID_INVALID", f"{field} contains unsupported characters")
    return result


def _string_list(value: Any, field: str, *, safe_ids: bool = True) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ReadOnlySpawnError("CONTROL_BIND_INCOMPLETE", f"{field} must be a non-empty array")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ReadOnlySpawnError("CONTROL_BIND_INCOMPLETE", f"{field} entries must be non-empty strings")
        normalized = item.strip()
        if safe_ids and not SAFE_ID_RE.fullmatch(normalized):
            raise ReadOnlySpawnError("CONTROL_BIND_ID_INVALID", f"{field} entry {normalized!r} is invalid")
        result.append(normalized)
    if len(result) != len(set(result)):
        raise ReadOnlySpawnError("CONTROL_BIND_DUPLICATE_VALUE", f"{field} contains duplicates")
    return sorted(result)


def _relative_scope_paths(value: Any) -> list[str]:
    values = _string_list(value, "path_prefixes", safe_ids=False)
    normalized: list[str] = []
    for raw in values:
        if raw == ".":
            normalized.append(".")
            continue
        path = Path(raw)
        if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
            raise ReadOnlySpawnError(
                "CONTROL_BIND_SCOPE_INVALID",
                f"path scope {raw!r} must be '.' or a clean workspace-relative path",
            )
        normalized.append(path.as_posix())
    return sorted(normalized)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReadOnlySpawnError("CONTROL_BIND_CAPABILITY_INVALID", f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReadOnlySpawnError("CONTROL_BIND_CAPABILITY_INVALID", f"{path} must contain an object")
    return value


def _capability(role: str, capability_root: str | Path | None = None) -> tuple[dict[str, Any], str, set[str]]:
    root = Path(os.environ.get("BBK_ROLE_CAPABILITY_ROOT") or capability_root or CAPABILITY_ROOT).resolve()
    path = root / f"{role}.json"
    if not path.is_file() or path.is_symlink():
        raise ReadOnlySpawnError("CONTROL_BIND_CAPABILITY_NOT_FOUND", f"compiled capability is missing for {role}")
    value = _read_json(path)
    if value.get("schema") != "bbk.role-capability.v1" or value.get("role") != role:
        raise ReadOnlySpawnError("CONTROL_BIND_CAPABILITY_INVALID", f"{path} is not the capability for {role}")
    manifest_digest = f"sha256:{canonical_digest({key: item for key, item in value.items() if key != 'manifest_digest'})}"
    if value.get("manifest_digest") != manifest_digest:
        raise ReadOnlySpawnError("CONTROL_BIND_CAPABILITY_DIGEST_MISMATCH", f"capability manifest is stale for {role}")
    policy_version = str(value.get("policy_version", ""))
    canonical_ref = f"role:{role}@{policy_version}#{manifest_digest}"
    return value, canonical_ref, {manifest_digest, f"role:{role}@{policy_version}", canonical_ref}


def _validate_parent(
    project_root: Path,
    *,
    binding_ref: str,
    session_id: str,
    invocation_id: str,
    capability_root: str | Path | None,
) -> dict[str, Any]:
    binding = resolve_binding_reference(project_root, binding_ref)
    if binding is None:
        raise ReadOnlySpawnError("CONTROL_BIND_PARENT_BINDING_NOT_ACTIVE", f"parent binding {binding_ref} is not active")
    request = binding.get("request", {})
    if request.get("session_id") != session_id or request.get("invocation_id") != invocation_id:
        raise ReadOnlySpawnError(
            "CONTROL_BIND_PARENT_CORRELATION_MISMATCH",
            "parent session/invocation do not match the active parent binding",
        )
    role = str(request.get("role", ""))
    capability, _, accepted_refs = _capability(role, capability_root)
    if str(binding.get("capability_ref", "")) not in accepted_refs:
        raise ReadOnlySpawnError(
            "CONTROL_BIND_PARENT_CAPABILITY_BINDING_MISMATCH",
            f"parent binding does not identify the current capability manifest for {role}",
        )
    if "bbk_control_bind" not in capability.get("allowed_tools", []):
        raise ReadOnlySpawnError("CONTROL_BIND_PARENT_ROLE_DENIED", f"{role} cannot use bbk_control_bind")
    return binding


def _validate_child_capability(role: str, capability_root: str | Path | None) -> tuple[dict[str, Any], str]:
    capability, capability_ref, _ = _capability(role, capability_root)
    if capability.get("scope_rules", {}).get("workspace_source") != "REGISTRY_BINDING":
        raise ReadOnlySpawnError("CONTROL_BIND_CHILD_WORKSPACE_POLICY_INVALID", f"{role} is not registry-workspace-bound")
    if capability.get("scope_rules", {}).get("path_scope") != "READ_ONLY":
        raise ReadOnlySpawnError("CONTROL_BIND_CHILD_NOT_READ_ONLY", f"{role} does not declare READ_ONLY path scope")
    if capability.get("allowed_mutation_classes", []) != []:
        raise ReadOnlySpawnError("CONTROL_BIND_CHILD_NOT_READ_ONLY", f"{role} has mutation classes and requires bbk_control_spawn")
    mutating = sorted(MUTATING_TOOLS & set(capability.get("allowed_tools", [])))
    if mutating:
        raise ReadOnlySpawnError("CONTROL_BIND_CHILD_NOT_READ_ONLY", f"{role} exposes mutating tools: {', '.join(mutating)}")
    if "bbk_governed_read" not in capability.get("allowed_tools", []):
        raise ReadOnlySpawnError("CONTROL_BIND_CHILD_READ_SURFACE_MISSING", f"{role} lacks bbk_governed_read")
    required = {"SESSION", "INVOCATION", "CANDIDATE", "WORKSPACE", "RETURN_CONTRACT"}
    missing = sorted(required - set(capability.get("required_bindings", [])))
    if missing:
        raise ReadOnlySpawnError("CONTROL_BIND_CHILD_CAPABILITY_INCOMPLETE", f"{role} omits bindings: {', '.join(missing)}")
    return capability, capability_ref


def _validate_request(request: Mapping[str, Any], project_root: Path) -> dict[str, Any]:
    if not isinstance(request, Mapping) or request.get("schema") != "bbk.bound-read-only-task-create.v1":
        raise ReadOnlySpawnError("CONTROL_BIND_SCHEMA_INVALID", "request schema must be bbk.bound-read-only-task-create.v1")
    unknown = sorted(set(request) - REQUEST_FIELDS)
    if unknown:
        raise ReadOnlySpawnError("CONTROL_BIND_SCHEMA_INVALID", f"unsupported fields: {', '.join(unknown)}")
    id_fields = (
        "host_version", "parent_binding_ref", "parent_session_id", "parent_invocation_id", "task_name", "role",
        "work_unit_id", "attempt_id", "baseline_ref", "candidate_id", "authority_ref", "return_contract",
        "idempotency_key",
    )
    normalized = {field: _text(request.get(field), field) for field in id_fields}
    normalized["workspace_ref"] = _text(request.get("workspace_ref"), "workspace_ref", free_text=True)
    normalized["assignment"] = _text(request.get("assignment"), "assignment", free_text=True)
    normalized["description"] = str(request.get("description") or f"{normalized['work_unit_id']} {normalized['attempt_id']}").strip()
    candidate_admission_ref = request.get("candidate_admission_ref")
    normalized["candidate_admission_ref"] = (
        _text(candidate_admission_ref, "candidate_admission_ref") if candidate_admission_ref is not None else None
    )
    normalized["path_prefixes"] = _relative_scope_paths(request.get("path_prefixes"))
    normalized["semantic_scope"] = _string_list(request.get("semantic_scope") or [f"candidate:{normalized['candidate_id']}"] , "semantic_scope")
    normalized["schema"] = "bbk.bound-read-only-task-create.v1"

    if normalized["host_version"] != QUALIFIED_HOST_VERSION:
        raise ReadOnlySpawnError(
            "OMP_HOST_UNQUALIFIED_FOR_CONTROL_BIND",
            f"host {normalized['host_version']!r} is not qualified for read-only child binding",
        )
    if not ROLE_RE.fullmatch(normalized["role"]):
        raise ReadOnlySpawnError("CONTROL_BIND_ROLE_INVALID", "role must be one canonical bbk_<name> identifier")
    if len(normalized["assignment"].encode("utf-8")) > MAX_ASSIGNMENT_BYTES:
        raise ReadOnlySpawnError("CONTROL_BIND_ASSIGNMENT_TOO_LARGE", f"assignment exceeds {MAX_ASSIGNMENT_BYTES} UTF-8 bytes")

    raw_workspace = Path(normalized["workspace_ref"]).expanduser()
    if not raw_workspace.is_absolute():
        raise ReadOnlySpawnError("CONTROL_BIND_WORKSPACE_INVALID", "workspace_ref must be explicit and absolute; CWD is not authority")
    if not raw_workspace.exists() or not raw_workspace.is_dir() or raw_workspace.is_symlink():
        raise ReadOnlySpawnError("CONTROL_BIND_WORKSPACE_INVALID", f"workspace_ref is not a real directory: {raw_workspace}")
    workspace = raw_workspace.resolve()
    if workspace == project_root:
        raise ReadOnlySpawnError(
            "CONTROL_BIND_WORKSPACE_CONFLATES_GOVERNANCE_ROOT",
            "read-only candidate workspace cannot be the governance-journal root; durable registration would change the candidate",
        )
    try:
        workspace.relative_to(project_root.parent)
    except ValueError as exc:
        raise ReadOnlySpawnError(
            "CONTROL_BIND_WORKSPACE_INVALID",
            f"workspace {workspace} is outside governed repository parent {project_root.parent}",
        ) from exc
    normalized["workspace_ref"] = str(workspace)
    return normalized



def _integrated_candidate_id(candidate_id: str) -> bool:
    return "integrated" in {part.lower() for part in candidate_id.split(":") if part}


def _validate_candidate_admission(
    project_root: Path,
    *,
    candidate_admission_ref: str | None,
    candidate: Mapping[str, Any],
    jj_identity: Mapping[str, Any],
    jj_path: str | Path | None,
) -> str | None:
    candidate_id = str(candidate.get("candidate_id") or "")
    required = _integrated_candidate_id(candidate_id)
    if not candidate_admission_ref:
        if required:
            raise ReadOnlySpawnError(
                "CONTROL_BIND_CANDIDATE_ADMISSION_REQUIRED",
                "an integrated candidate cannot be bound without a current candidate-integration admission receipt",
                smallest_next_action="Complete content-neutral integration and pass its candidate_admission_ref.",
            )
        return None
    matches = [receipt for receipt in all_receipts(project_root) if receipt.get("receipt_id") == candidate_admission_ref]
    if len(matches) != 1:
        code = "CONTROL_BIND_CANDIDATE_ADMISSION_NOT_FOUND" if not matches else "CONTROL_BIND_CANDIDATE_ADMISSION_AMBIGUOUS"
        raise ReadOnlySpawnError(code, "candidate admission reference does not resolve to exactly one immutable receipt")
    receipt = matches[0]
    if receipt.get("receipt_kind") != "CANDIDATE_INTEGRATION_ADMISSION":
        raise ReadOnlySpawnError(
            "CONTROL_BIND_CANDIDATE_ADMISSION_KIND_INVALID",
            "candidate admission reference is not a CANDIDATE_INTEGRATION_ADMISSION receipt",
        )
    content = receipt.get("content")
    if not isinstance(content, dict) or content.get("schema") != "bbk.candidate-integration-admission.v1":
        raise ReadOnlySpawnError("CONTROL_BIND_CANDIDATE_ADMISSION_INVALID", "candidate admission content has the wrong schema")
    core = {key: value for key, value in content.items() if key != "admission_digest"}
    if content.get("admission_digest") != f"sha256:{canonical_digest(core)}":
        raise ReadOnlySpawnError("CONTROL_BIND_CANDIDATE_ADMISSION_TAMPERED", "candidate admission integrity check failed")
    workspace = Path(str(candidate.get("workspace_path") or "")).resolve()
    expected = {
        "status": "PASS",
        "candidate_id": candidate_id,
        "candidate_digest": candidate.get("digest"),
        "workspace_ref": str(workspace),
        "jj_change_id": jj_identity.get("jj_change_id"),
        "git_tree": candidate.get("git_tree"),
        "unresolved_conflicts": False,
        "conflict_resolution_authority": "DENIED",
        "integration_mode": "CONTENT_NEUTRAL_DISJOINT_PATHS",
    }
    mismatched = [field for field, value in expected.items() if content.get(field) != value]
    source_changes = content.get("source_change_ids")
    source_commits = content.get("source_commit_ids")
    parents = content.get("parent_commit_ids")
    integrated_paths = content.get("integrated_paths")
    baseline_revision = str(content.get("baseline_revision") or "").strip()
    if not isinstance(source_changes, list) or len(source_changes) != 2 or len(set(source_changes)) != 2:
        mismatched.append("source_change_ids")
    if not isinstance(source_commits, list) or len(source_commits) != 2 or len(set(source_commits)) != 2:
        mismatched.append("source_commit_ids")
    if not isinstance(parents, list) or sorted(parents) != sorted(source_commits or []):
        mismatched.append("parent_commit_ids")
    if sorted(jj_identity.get("parent_commit_ids", [])) != sorted(parents or []):
        mismatched.append("current_parent_commit_ids")
    if not isinstance(integrated_paths, list) or len(integrated_paths) != 2 or integrated_paths != sorted(set(integrated_paths)):
        mismatched.append("integrated_paths")
    if not baseline_revision:
        mismatched.append("baseline_revision")
    else:
        observed_paths = jj_adapter.changed_paths_between(
            workspace,
            from_revision=baseline_revision,
            to_revision=str(jj_identity.get("jj_change_id") or "@"),
            jj_path=jj_path,
        )
        if observed_paths != integrated_paths:
            mismatched.append("current_integrated_paths")
    if mismatched:
        raise ReadOnlySpawnError(
            "CONTROL_BIND_CANDIDATE_ADMISSION_MISMATCH",
            f"candidate no longer matches its integration admission: {', '.join(sorted(set(mismatched)))}",
        )
    return candidate_admission_ref


def _prior_registrations(project_root: Path, idempotency_key: str) -> list[dict[str, Any]]:
    return [
        receipt for receipt in all_receipts(project_root)
        if receipt.get("receipt_kind") == "READ_ONLY_TASK_REGISTRATION"
        and receipt.get("content", {}).get("idempotency_key") == idempotency_key
    ]


def compile_read_only_spawn(
    project_root: str | Path,
    request: Mapping[str, Any],
    *,
    git_path: str | Path | None = None,
    jj_path: str | Path | None = None,
    capability_root: str | Path | None = None,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Freeze, bind, register, and reserve one exact read-only child task."""
    root = Path(project_root).resolve()
    if not root.is_dir():
        raise ReadOnlySpawnError("CONTROL_BIND_PROJECT_ROOT_INVALID", f"project root does not exist: {root}")
    normalized = _validate_request(request, root)
    _validate_parent(
        root,
        binding_ref=normalized["parent_binding_ref"],
        session_id=normalized["parent_session_id"],
        invocation_id=normalized["parent_invocation_id"],
        capability_root=capability_root,
    )
    _, capability_ref = _validate_child_capability(normalized["role"], capability_root)

    workspace = Path(normalized["workspace_ref"])
    try:
        jj_identity = jj_adapter.identity(workspace, jj_path=jj_path)
        git_root = jj_adapter.git_repository_root(workspace, jj_path=jj_path)
        candidate = git_adapter.freeze_candidate(
            workspace,
            candidate_id=normalized["candidate_id"],
            jj_change_id=jj_identity["jj_change_id"],
            git_path=git_path,
            git_repository_root=git_root,
        )
    except (jj_adapter.JjAdapterError, git_adapter.GitAdapterError) as exc:
        raise ReadOnlySpawnError(getattr(exc, "code", "CONTROL_BIND_CANDIDATE_FREEZE_FAILED"), getattr(exc, "message", str(exc))) from exc

    candidate_admission_ref = _validate_candidate_admission(
        root,
        candidate_admission_ref=normalized.get("candidate_admission_ref"),
        candidate=candidate,
        jj_identity=jj_identity,
        jj_path=jj_path,
    )

    stable_request = {
        **normalized,
        "candidate_digest": candidate["digest"],
        "jj_change_id": jj_identity["jj_change_id"],
        "git_tree": candidate.get("git_tree"),
    }
    request_digest = f"sha256:{canonical_digest(stable_request)}"
    prior = _prior_registrations(root, normalized["idempotency_key"])
    if len(prior) > 1:
        raise ReadOnlySpawnError("CONTROL_BIND_IDEMPOTENCY_AMBIGUOUS", "idempotency key has multiple registrations")
    if prior and prior[0].get("content", {}).get("request_digest") != request_digest:
        raise ReadOnlySpawnError(
            "CONTROL_BIND_IDEMPOTENCY_COLLISION",
            "idempotency key was reused after request or candidate content changed",
        )

    absolute_prefixes: list[str] = []
    for relative in normalized["path_prefixes"]:
        prefix = workspace if relative == "." else (workspace / relative).resolve(strict=False)
        try:
            prefix.relative_to(workspace)
        except ValueError as exc:
            raise ReadOnlySpawnError("CONTROL_BIND_SCOPE_ESCAPE", f"compiled path scope escapes workspace: {prefix}") from exc
        absolute_prefixes.append(str(prefix))

    identity = canonical_digest({
        "request_digest": request_digest,
        "workspace_ref": str(workspace),
        "candidate_digest": candidate["digest"],
        "jj_change_id": jj_identity["jj_change_id"],
    })
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
        "candidate_ref": candidate["digest"],
        "workspace_ref": str(workspace),
        "authority_ref": normalized["authority_ref"],
        "scope": {
            "path_prefixes": sorted(absolute_prefixes),
            "mutation_classes": ["READ_ONLY"],
            "semantic_scope": normalized["semantic_scope"],
        },
        "return_contract": normalized["return_contract"],
        "return_transport_mode": "STRUCTURED_RETURN_ONLY",
        "material_transport_reason": "",
        "jj_change_id": jj_identity["jj_change_id"],
        "idempotency_key": normalized["idempotency_key"],
    }
    binding, binding_created = create_initial_binding(
        root,
        binding_request,
        capability_ref=capability_ref,
        created_at=recorded_at,
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
        "candidate_ref": candidate["digest"],
        "workspace_ref": str(workspace),
        "jj_change_id": jj_identity["jj_change_id"],
        "authority_ref": normalized["authority_ref"],
        "scope": binding_request["scope"],
        "return_contract": normalized["return_contract"],
        "return_transport_mode": "STRUCTURED_RETURN_ONLY",
        "material_transport_reason": "",
        "capability_ref": capability_ref,
        "task_name": normalized["task_name"],
        "assignment_digest": f"sha256:{canonical_digest(normalized['assignment'])}",
    }
    if candidate_admission_ref:
        binding_context["candidate_admission_ref"] = candidate_admission_ref
    packet_core = {
        "schema": "bbk.bound-worker-packet.v1",
        "planned_binding_ref": binding["binding_id"],
        "binding_context": binding_context,
    }
    packet_digest = f"sha256:{canonical_digest(packet_core)}"
    packet = {**packet_core, "packet_digest": packet_digest}
    task_input = {
        "i": f"Spawn bound read-only {normalized['role']} for {normalized['work_unit_id']} {normalized['attempt_id']}",
        "context": packet_context(packet),
        "tasks": [{
            "agent": normalized["role"],
            "name": normalized["task_name"],
            "task": normalized["assignment"],
        }],
    }
    task_input_digest = f"sha256:{canonical_digest(task_input)}"
    dispatch_ref = f"dispatch:{canonical_digest({
        'planned_binding_ref': binding['binding_id'],
        'parent_session_id': normalized['parent_session_id'],
        'task_name': normalized['task_name'],
        'agent': normalized['role'],
        'task_input_digest': task_input_digest,
    })}"
    dispatch_input = build_dispatch_task_input(
        dispatch_ref=dispatch_ref,
        task_name=normalized["task_name"],
        agent=normalized["role"],
    )
    canonical_dispatch_digest = dispatch_envelope_digest(dispatch_input)

    registration_core = {
        "schema": "bbk.read-only-task-registration.v1",
        "idempotency_key": normalized["idempotency_key"],
        "request_digest": request_digest,
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
        "candidate_id": normalized["candidate_id"],
        "candidate_ref": candidate["digest"],
        "workspace_ref": str(workspace),
        "jj_change_id": jj_identity["jj_change_id"],
        "authority_ref": normalized["authority_ref"],
        "scope": binding_request["scope"],
        "return_contract": normalized["return_contract"],
        "return_transport_mode": "STRUCTURED_RETURN_ONLY",
        "material_transport_reason": "",
        "capability_ref": capability_ref,
        "task_name": normalized["task_name"],
        "assignment_digest": binding_context["assignment_digest"],
        "packet_digest": packet_digest,
        "task_input_digest": task_input_digest,
        "dispatch_ref": dispatch_ref,
        "dispatch_envelope_digest": canonical_dispatch_digest,
        "dispatch_input_digest": canonical_dispatch_digest,
        "status": "REGISTERED",
    }
    if candidate_admission_ref:
        registration_core["candidate_admission_ref"] = candidate_admission_ref
    registration_id = f"sha256:{canonical_digest(registration_core)}"
    registration_content = {**registration_core, "registration_id": registration_id}
    registration, registration_created = append_receipt(
        root,
        "READ_ONLY_TASK_REGISTRATION",
        registration_content,
        receipt_id=registration_id,
        recorded_at=recorded_at or utc_now(),
    )
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
    return {
        "schema": "bbk.bound-read-only-task.v1",
        "status": "READY_TO_DISPATCH",
        "dispatch_status": dispatch_status(root, dispatch_ref=dispatch_ref, parent_session_id=normalized["parent_session_id"]),
        "idempotent_reuse": bool(prior),
        "request_digest": request_digest,
        "binding_created": binding_created,
        "registration_created": registration_created,
        "planned_binding_ref": binding["binding_id"],
        "planned_session_id": planned_session,
        "invocation_id": invocation_id,
        "candidate": candidate,
        **({"candidate_admission_ref": candidate_admission_ref} if candidate_admission_ref else {}),
        "worker_packet": packet,
        "dispatch_ref": dispatch_ref,
        "dispatch_input": dispatch_input,
        "dispatch_envelope_digest": canonical_dispatch_digest,
        "dispatch_input_digest": canonical_dispatch_digest,
        "task_input_digest": task_input_digest,
        "task_registration_ref": registration["receipt_id"],
        "spawn_reservation_ref": reservation["receipt_ref"],
    }


def _load_json_argument(value: str) -> dict[str, Any]:
    raw = sys.stdin.read() if value == "-" else (Path(value).read_text(encoding="utf-8") if Path(value).is_file() else value)
    try:
        parsed = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise ReadOnlySpawnError("CONTROL_BIND_JSON_INVALID", f"cannot load request JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ReadOnlySpawnError("CONTROL_BIND_JSON_INVALID", "request JSON must be an object")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    compile_parser = sub.add_parser("compile")
    compile_parser.add_argument("--request", required=True, help="JSON object, file path, or - for stdin")
    compile_parser.add_argument("--git", default=os.environ.get("BBK_GIT"))
    compile_parser.add_argument("--jj", default=os.environ.get("BBK_JJ"))
    compile_parser.add_argument("--recorded-at")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = compile_read_only_spawn(
            args.root,
            _load_json_argument(args.request),
            git_path=args.git,
            jj_path=args.jj,
            recorded_at=args.recorded_at,
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (ReadOnlySpawnError, OmpBindingError, jj_adapter.JjAdapterError, git_adapter.GitAdapterError) as exc:
        print(json.dumps({
            "schema": "bbk.bound-read-only-task-error.v1",
            "status": "BLOCK",
            "reason_code": getattr(exc, "code", "CONTROL_BIND_FAILED"),
            "message": getattr(exc, "message", str(exc)),
            "smallest_next_action": getattr(exc, "smallest_next_action", "Correct the typed read-only binding request and retry."),
        }, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
