#!/usr/bin/env python3
"""Typed orchestrator control plane for governed BBK execution.

The module exposes the three agent-facing coordination effects required by
Alpha.17: assignment, state update, and integration request.  Every request is
correlated to an active immutable OMP invocation binding and the current
compiled role-capability manifest before it can reach the single-writer Beads
adapter.  The control plane never accepts paths, shell commands, product
content, patches, or conflict-resolution instructions.
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
    from governed_state import all_receipts
    from omp_binding_registry import OmpBindingError, resolve_binding_reference
    from substrate import beads_adapter
except ImportError:  # pragma: no cover - installed-package import fallback
    from .gate_kernel import canonical_digest
    from .governed_state import all_receipts
    from .omp_binding_registry import OmpBindingError, resolve_binding_reference
    from .substrate import beads_adapter

ROOT = Path(os.environ.get("BBK_PACKAGE_ROOT", Path(__file__).resolve().parents[1])).resolve()
CAPABILITY_ROOT = ROOT / "spec" / "role-capabilities"
QUALIFIED_HOST_VERSION = "omp/16.4.8"
ORCHESTRATOR_ROLES = frozenset(
    {
        "bbk_root_orchestrator",
        "bbk_territory_orchestrator",
        "bbk_worker_orchestrator",
        "bbk_validator_orchestrator",
    }
)
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+\-]*$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SUMMARY_FORBIDDEN_FRAGMENTS = ("```", "diff --git", "@@ ", "*** Begin Patch", "*** End Patch")
UPDATE_TRANSITIONS = frozenset({"START", "BLOCK", "UNBLOCK", "COMPLETE", "FAIL", "ANNOTATE"})
CONFLICT_CLASSIFICATIONS = frozenset({"NONE", "CONTENT_NEUTRAL", "CONTENT_CHANGING", "UNKNOWN"})

COMMON_FIELDS = frozenset(
    {
        "schema",
        "host_version",
        "session_id",
        "binding_ref",
        "invocation_id",
        "command_id",
        "work_unit_id",
        "attempt_id",
        "correlation_id",
        "payload_summary",
        "expected_revision",
        "idempotency_key",
        "evidence_refs",
        "finding_refs",
    }
)
REQUEST_FIELDS = {
    "bbk.control-assign.v1": COMMON_FIELDS | {"worker_binding_ref", "attempt_registration_ref"},
    "bbk.control-update.v1": COMMON_FIELDS | {"transition"},
    "bbk.control-integrate-request.v1": COMMON_FIELDS
    | {"source_candidate_refs", "target_candidate_ref", "conflict_classification"},
}
TOOL_BY_SCHEMA = {
    "bbk.control-assign.v1": "bbk_control_assign",
    "bbk.control-update.v1": "bbk_control_update",
    "bbk.control-integrate-request.v1": "bbk_control_integrate_request",
}
OPERATION_BY_SCHEMA = {
    "bbk.control-assign.v1": "ASSIGN",
    "bbk.control-update.v1": "UPDATE",
    "bbk.control-integrate-request.v1": "INTEGRATE_REQUEST",
}


class ControlPlaneError(RuntimeError):
    """A typed control-plane request is unauthorized, inconsistent, or unsafe."""

    def __init__(self, code: str, message: str, *, smallest_next_action: str = ""):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.smallest_next_action = smallest_next_action or "Correct the typed control-plane request and retry."


def _text(value: Any, field: str, *, max_bytes: int = 512) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ControlPlaneError("CONTROL_PLANE_REQUEST_INCOMPLETE", f"{field} must be a non-empty string")
    result = value.strip()
    if len(result.encode("utf-8")) > max_bytes:
        raise ControlPlaneError("CONTROL_PLANE_VALUE_TOO_LARGE", f"{field} exceeds {max_bytes} UTF-8 bytes")
    if not SAFE_ID_RE.fullmatch(result):
        raise ControlPlaneError("CONTROL_PLANE_ID_INVALID", f"{field} contains unsupported characters")
    return result


def _summary(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ControlPlaneError("CONTROL_PLANE_REQUEST_INCOMPLETE", "payload_summary must be a non-empty string")
    result = value.strip()
    if len(result.encode("utf-8")) > 512:
        raise ControlPlaneError("CONTROL_PLANE_SUMMARY_TOO_LARGE", "payload_summary exceeds 512 UTF-8 bytes")
    if any(character in result for character in ("\x00", "\r", "\n")) or any(
        fragment in result for fragment in SUMMARY_FORBIDDEN_FRAGMENTS
    ):
        raise ControlPlaneError(
            "CONTROL_PLANE_PRODUCT_PAYLOAD_FORBIDDEN",
            "payload_summary must be a single-line coordination summary, not product content, a patch, or conflict repair",
            smallest_next_action="Move product work into a bound worker attempt and retain only a concise coordination summary.",
        )
    return result


def _string_list(value: Any, field: str, *, required: bool = False) -> list[str]:
    if value is None and not required:
        return []
    if not isinstance(value, list) or (required and not value):
        qualifier = "a non-empty" if required else "an"
        raise ControlPlaneError("CONTROL_PLANE_REQUEST_INVALID", f"{field} must be {qualifier} array")
    normalized = [_text(item, f"{field}[]", max_bytes=512) for item in value]
    if len(normalized) != len(set(normalized)):
        raise ControlPlaneError("CONTROL_PLANE_DUPLICATE_REFERENCE", f"{field} contains duplicate references")
    return sorted(normalized)


def _expected_revision(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ControlPlaneError(
            "CONTROL_PLANE_EXPECTED_REVISION_INVALID",
            "expected_revision must be a non-negative integer",
        )
    return value


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ControlPlaneError("CONTROL_PLANE_CAPABILITY_INVALID", f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ControlPlaneError("CONTROL_PLANE_CAPABILITY_INVALID", f"{path} must contain an object")
    return value


def _capability(role: str, capability_root: str | Path | None = None) -> tuple[dict[str, Any], str, set[str]]:
    root = Path(os.environ.get("BBK_ROLE_CAPABILITY_ROOT") or capability_root or CAPABILITY_ROOT).resolve()
    path = root / f"{role}.json"
    if not path.is_file() or path.is_symlink():
        raise ControlPlaneError("CONTROL_PLANE_CAPABILITY_NOT_FOUND", f"compiled capability is missing for {role}")
    value = _read_json(path)
    if value.get("schema") != "bbk.role-capability.v1" or value.get("role") != role:
        raise ControlPlaneError("CONTROL_PLANE_CAPABILITY_INVALID", f"{path} is not the capability for {role}")
    manifest_digest = f"sha256:{canonical_digest({key: item for key, item in value.items() if key != 'manifest_digest'})}"
    if value.get("manifest_digest") != manifest_digest:
        raise ControlPlaneError("CONTROL_PLANE_CAPABILITY_DIGEST_MISMATCH", f"capability manifest is stale for {role}")
    policy_version = str(value.get("policy_version", ""))
    canonical_ref = f"role:{role}@{policy_version}#{manifest_digest}"
    accepted_refs = {manifest_digest, f"role:{role}@{policy_version}", canonical_ref}
    return value, canonical_ref, accepted_refs


def _validate_request_shape(request: Mapping[str, Any]) -> tuple[str, str]:
    if not isinstance(request, Mapping):
        raise ControlPlaneError("CONTROL_PLANE_SCHEMA_INVALID", "request must be an object")
    schema = str(request.get("schema") or "")
    allowed = REQUEST_FIELDS.get(schema)
    if allowed is None:
        raise ControlPlaneError(
            "CONTROL_PLANE_SCHEMA_INVALID",
            "schema must be bbk.control-assign.v1, bbk.control-update.v1, or bbk.control-integrate-request.v1",
        )
    unknown = sorted(set(request) - allowed)
    if unknown:
        raise ControlPlaneError(
            "CONTROL_PLANE_SCHEMA_INVALID",
            f"request contains unsupported fields: {', '.join(unknown)}",
        )
    return schema, TOOL_BY_SCHEMA[schema]


def _actor(
    project_root: Path,
    request: Mapping[str, Any],
    *,
    tool_name: str,
    capability_root: str | Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    host_version = _text(request.get("host_version"), "host_version")
    if host_version != QUALIFIED_HOST_VERSION:
        raise ControlPlaneError(
            "CONTROL_PLANE_HOST_UNQUALIFIED",
            f"host {host_version} is not qualified for enforced orchestrator control effects",
            smallest_next_action="Use OMP 16.4.8 or re-qualify the changed host contract.",
        )
    binding_ref = _text(request.get("binding_ref"), "binding_ref")
    session_id = _text(request.get("session_id"), "session_id")
    invocation_id = _text(request.get("invocation_id"), "invocation_id")
    binding = resolve_binding_reference(project_root, binding_ref)
    if binding is None:
        raise ControlPlaneError("CONTROL_PLANE_BINDING_NOT_ACTIVE", f"binding {binding_ref} is not active")
    bound = binding.get("request", {})
    if bound.get("session_id") != session_id or bound.get("invocation_id") != invocation_id:
        raise ControlPlaneError(
            "CONTROL_PLANE_CORRELATION_MISMATCH",
            "session_id and invocation_id do not match the active orchestrator binding",
        )
    role = str(bound.get("role") or "")
    if role not in ORCHESTRATOR_ROLES:
        raise ControlPlaneError(
            "CONTROL_PLANE_ROLE_DENIED",
            f"{role or 'unknown role'} is not an orchestrator control-plane role",
            smallest_next_action="Use the bound orchestrator for coordination and keep product effects in worker roles.",
        )
    capability, canonical_ref, accepted_refs = _capability(role, capability_root)
    if str(binding.get("capability_ref") or "") not in accepted_refs:
        raise ControlPlaneError(
            "CONTROL_PLANE_CAPABILITY_BINDING_MISMATCH",
            f"binding does not identify the current capability for {role}",
        )
    if tool_name not in capability.get("allowed_tools", []):
        raise ControlPlaneError("CONTROL_PLANE_TOOL_DENIED", f"{role} is not permitted to use {tool_name}")
    if "COORDINATION_METADATA" not in capability.get("allowed_mutation_classes", []):
        raise ControlPlaneError(
            "CONTROL_PLANE_MUTATION_CLASS_DENIED",
            f"{role} capability does not permit COORDINATION_METADATA",
        )
    bound_classes = bound.get("scope", {}).get("mutation_classes", [])
    if "COORDINATION_METADATA" not in bound_classes:
        raise ControlPlaneError(
            "CONTROL_PLANE_BINDING_SCOPE_DENIED",
            "active orchestrator binding does not include COORDINATION_METADATA",
        )
    actor = {
        "role": role,
        "session_id": session_id,
        "invocation_id": invocation_id,
        "binding_ref": binding["binding_id"],
        "authority_ref": str(bound.get("authority_ref") or ""),
        "capability_ref": canonical_ref,
    }
    if not actor["authority_ref"]:
        raise ControlPlaneError("CONTROL_PLANE_AUTHORITY_MISSING", "active binding has no authority_ref")
    return actor, binding


def _receipt(project_root: Path, receipt_ref: str, kind: str) -> dict[str, Any]:
    if not DIGEST_RE.fullmatch(receipt_ref):
        raise ControlPlaneError("CONTROL_PLANE_RECEIPT_REF_INVALID", f"{kind} reference must be sha256:<64 hex>")
    matches = [
        item
        for item in all_receipts(project_root)
        if item.get("receipt_id") == receipt_ref and item.get("receipt_kind") == kind
    ]
    if not matches:
        raise ControlPlaneError("CONTROL_PLANE_RECEIPT_NOT_FOUND", f"{kind} receipt {receipt_ref} was not found")
    if len(matches) != 1:
        raise ControlPlaneError("CONTROL_PLANE_RECEIPT_AMBIGUOUS", f"{kind} receipt {receipt_ref} is ambiguous")
    return matches[0]


def _common(request: Mapping[str, Any], actor: Mapping[str, Any], operation: str) -> dict[str, Any]:
    return {
        "schema": "bbk.coordination-command.v1",
        "command_id": _text(request.get("command_id"), "command_id"),
        "operation": operation,
        "actor": dict(actor),
        "work_unit": _text(request.get("work_unit_id"), "work_unit_id"),
        "attempt": _text(request.get("attempt_id"), "attempt_id"),
        "correlation_id": _text(request.get("correlation_id"), "correlation_id"),
        "payload_summary": _summary(request.get("payload_summary")),
        "expected_revision": _expected_revision(request.get("expected_revision")),
        "idempotency_key": _text(request.get("idempotency_key"), "idempotency_key"),
        "evidence_refs": _string_list(request.get("evidence_refs"), "evidence_refs"),
        "finding_refs": _string_list(request.get("finding_refs"), "finding_refs"),
    }


def _assignment(
    project_root: Path,
    request: Mapping[str, Any],
    actor: Mapping[str, Any],
    actor_binding: Mapping[str, Any],
    *,
    capability_root: str | Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    common = _common(request, actor, "ASSIGN")
    worker_binding_ref = _text(request.get("worker_binding_ref"), "worker_binding_ref")
    registration_ref = _text(request.get("attempt_registration_ref"), "attempt_registration_ref")
    if not DIGEST_RE.fullmatch(registration_ref):
        raise ControlPlaneError(
            "CONTROL_PLANE_ATTEMPT_REGISTRATION_INVALID",
            "attempt_registration_ref must be sha256:<64 lowercase hex>",
        )
    registration_record = _receipt(project_root, registration_ref, "WORK_UNIT_ATTEMPT_REGISTRATION")
    registration = registration_record.get("content", {})
    if registration.get("schema") != "bbk.work-unit-attempt-registration.v1":
        raise ControlPlaneError("CONTROL_PLANE_ATTEMPT_REGISTRATION_INVALID", "attempt registration schema is invalid")
    if registration.get("registration_id") != registration_ref:
        raise ControlPlaneError("CONTROL_PLANE_ATTEMPT_REGISTRATION_INVALID", "attempt registration identity is inconsistent")
    registered_binding_ref = str(registration.get("planned_binding_ref") or "")
    worker_binding = resolve_binding_reference(project_root, worker_binding_ref)
    registered_binding = resolve_binding_reference(project_root, registered_binding_ref)
    if worker_binding is None or registered_binding is None or worker_binding.get("binding_id") != registered_binding.get("binding_id"):
        raise ControlPlaneError(
            "CONTROL_PLANE_ASSIGNMENT_BINDING_MISMATCH",
            "worker_binding_ref does not resolve to the registered attempt binding",
        )
    worker_request = worker_binding.get("request", {})
    worker_role = str(worker_request.get("role") or "")
    _, worker_capability_ref, worker_capability_refs = _capability(worker_role, capability_root)
    if str(worker_binding.get("capability_ref") or "") not in worker_capability_refs:
        raise ControlPlaneError(
            "CONTROL_PLANE_WORKER_CAPABILITY_BINDING_MISMATCH",
            f"worker binding does not identify the current capability for {worker_role or 'unknown role'}",
        )
    if registration.get("capability_ref") != worker_capability_ref:
        raise ControlPlaneError(
            "CONTROL_PLANE_WORKER_CAPABILITY_REGISTRATION_MISMATCH",
            "attempt registration does not identify the current worker capability",
        )
    checks = {
        "host_version": QUALIFIED_HOST_VERSION,
        "invocation_id": worker_request.get("invocation_id"),
        "work_unit_id": common["work_unit"],
        "attempt_id": common["attempt"],
        "role": worker_role,
        "baseline_ref": worker_request.get("baseline_ref"),
        "candidate_ref": worker_request.get("candidate_ref"),
        "workspace_ref": worker_request.get("workspace_ref"),
        "jj_change_id": worker_request.get("jj_change_id"),
        "authority_ref": worker_request.get("authority_ref"),
        "scope": worker_request.get("scope"),
        "return_contract": worker_request.get("return_contract"),
    }
    for field, expected in checks.items():
        if registration.get(field) != expected:
            raise ControlPlaneError(
                "CONTROL_PLANE_ASSIGNMENT_REGISTRATION_MISMATCH",
                f"attempt registration {field} does not match the bound assignment",
            )
    parent_checks = {
        "parent_binding_ref": actor_binding.get("binding_id"),
        "parent_session_id": actor["session_id"],
        "parent_invocation_id": actor["invocation_id"],
        "authority_ref": actor["authority_ref"],
    }
    for field, expected in parent_checks.items():
        if registration.get(field) != expected:
            raise ControlPlaneError(
                "CONTROL_PLANE_ASSIGNMENT_PARENT_MISMATCH",
                f"attempt registration {field} does not match the active orchestrator",
            )
    if worker_request.get("parent_session_id") != actor["session_id"]:
        raise ControlPlaneError(
            "CONTROL_PLANE_ASSIGNMENT_PARENT_MISMATCH",
            "worker binding parent_session_id does not match the active orchestrator session",
        )
    common["transition"] = "CREATE" if common["expected_revision"] == 0 else "ANNOTATE"
    common["assignment"] = {
        "worker_binding_ref": registered_binding_ref,
        "attempt_registration_ref": registration_ref,
        "assignee_role": str(registration["role"]),
        "task_name": str(registration["task_name"]),
        "candidate_ref": str(registration["candidate_ref"]),
        "workspace_ref": str(registration["workspace_ref"]),
        "jj_change_id": str(registration["jj_change_id"]),
        "assignment_digest": str(registration["assignment_digest"]),
        "packet_digest": str(registration["packet_digest"]),
        "task_input_digest": str(registration["task_input_digest"]),
    }
    policy = {
        "effect_class": "COORDINATION_METADATA",
        "product_mutation_authority": "DENIED",
        "raw_bd_authority": "DENIED",
        "assignment_binding": "IMMUTABLE_ATTEMPT_REGISTRATION",
    }
    return common, policy


def _update(request: Mapping[str, Any], actor: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    common = _common(request, actor, "UPDATE")
    transition = _text(request.get("transition"), "transition")
    if transition not in UPDATE_TRANSITIONS:
        raise ControlPlaneError(
            "CONTROL_PLANE_TRANSITION_INVALID",
            f"UPDATE transition must be one of {', '.join(sorted(UPDATE_TRANSITIONS))}",
        )
    common["transition"] = transition
    policy = {
        "effect_class": "COORDINATION_METADATA",
        "product_mutation_authority": "DENIED",
        "raw_bd_authority": "DENIED",
    }
    return common, policy


def _integration(
    project_root: Path,
    request: Mapping[str, Any],
    actor: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build an integration request without requiring model-authored revision state.

    The OMP integration tool deliberately omits ``expectedRevision``.  BBK
    derives the current Beads revision under the same canonical state used by
    the projection adapter.  Exact retries reuse the revision from the prior
    immutable idempotency record, so a retry cannot collide merely because the
    successful first projection advanced the work-unit revision.
    """
    normalized = dict(request)
    supplied_revision = normalized.get("expected_revision")
    if supplied_revision is None:
        work_unit = _text(normalized.get("work_unit_id"), "work_unit_id")
        idempotency_key = _text(normalized.get("idempotency_key"), "idempotency_key")
        prior = beads_adapter.find_coordination_idempotent(project_root, idempotency_key)
        if prior is not None:
            prior_command = prior.get("content", {}).get("command", {})
            prior_revision = prior_command.get("expected_revision")
            normalized["expected_revision"] = _expected_revision(prior_revision)
            revision_source = "IDEMPOTENT_RECORD"
        else:
            normalized["expected_revision"] = beads_adapter.current_revision(project_root, work_unit)
            revision_source = "DERIVED_CURRENT"
    else:
        normalized["expected_revision"] = _expected_revision(supplied_revision)
        revision_source = "CALLER_SUPPLIED_COMPATIBILITY"

    common = _common(normalized, actor, "INTEGRATE_REQUEST")
    classification = _text(normalized.get("conflict_classification"), "conflict_classification")
    if classification not in CONFLICT_CLASSIFICATIONS:
        raise ControlPlaneError(
            "CONTROL_PLANE_CONFLICT_CLASSIFICATION_INVALID",
            f"conflict_classification must be one of {', '.join(sorted(CONFLICT_CLASSIFICATIONS))}",
        )
    sources = _string_list(request.get("source_candidate_refs"), "source_candidate_refs", required=True)
    target = _text(request.get("target_candidate_ref"), "target_candidate_ref")
    if target in sources:
        raise ControlPlaneError(
            "CONTROL_PLANE_INTEGRATION_TARGET_INVALID",
            "target_candidate_ref must not also appear in source_candidate_refs",
        )
    worker_required = classification in {"CONTENT_CHANGING", "UNKNOWN"}
    route = "BOUND_INTEGRATION_WORKER" if worker_required else "CONTENT_NEUTRAL_INTEGRATION_ADAPTER"
    common["transition"] = "CREATE" if common["expected_revision"] == 0 else "ANNOTATE"
    common["integration"] = {
        "source_candidate_refs": sources,
        "target_candidate_ref": target,
        "conflict_classification": classification,
        "requested_route": route,
        "integration_worker_required": worker_required,
        "orchestrator_conflict_resolution_authority": "DENIED",
        "effect_performed": "REQUEST_RECORDED_ONLY",
    }
    policy = {
        "effect_class": "COORDINATION_METADATA",
        "product_mutation_authority": "DENIED",
        "raw_bd_authority": "DENIED",
        "orchestrator_conflict_resolution_authority": "DENIED",
        "content_changing_route": "BOUND_INTEGRATION_WORKER",
        "requested_route": route,
        "integration_worker_required": worker_required,
        "effect_performed": "REQUEST_RECORDED_ONLY",
        "expected_revision_source": revision_source,
    }
    return common, policy



def project_spawn_assignment(
    project_root: str | Path,
    *,
    parent_binding_ref: str,
    attempt_registration_ref: str,
    bd_path: str | Path | None = None,
    capability_root: str | Path | None = None,
) -> dict[str, Any]:
    """Project the immutable worker assignment as part of spawn compilation.

    The orchestrator model no longer authors actor correlation, Beads revision,
    command identity, or idempotency fields between packet compilation and
    dispatch.  All values are derived from the active parent binding and the
    immutable attempt registration, then passed through the ordinary typed
    control-plane validation and single-writer adapter.
    """
    root = Path(project_root).resolve()
    parent = resolve_binding_reference(root, parent_binding_ref)
    if parent is None:
        raise ControlPlaneError(
            "CONTROL_PLANE_BINDING_NOT_ACTIVE",
            f"parent binding {parent_binding_ref} is not active",
        )
    parent_request = parent.get("request", {})
    registration_record = _receipt(root, attempt_registration_ref, "WORK_UNIT_ATTEMPT_REGISTRATION")
    registration = registration_record.get("content", {})
    logical_attempt_ref = str(
        registration.get("logical_attempt_ref")
        or f"attempt:{canonical_digest({
            'parent_binding_ref': parent_binding_ref,
            'work_unit_id': registration.get('work_unit_id'),
            'attempt_id': registration.get('attempt_id'),
        })}"
    )
    identity = canonical_digest({
        "logical_attempt_ref": logical_attempt_ref,
        "attempt_registration_ref": attempt_registration_ref,
        "parent_binding_ref": parent_binding_ref,
    })
    assignment_idempotency_key = f"spawn-assignment:{identity}"
    prior_semantic = beads_adapter.find_coordination_idempotent(root, assignment_idempotency_key)
    if prior_semantic is not None:
        prior_command = prior_semantic.get("content", {}).get("command", {})
        revision = int(prior_command.get("expected_revision", 0))
    else:
        revision = beads_adapter.current_revision(root, str(registration.get("work_unit_id") or ""))
    request = {
        "schema": "bbk.control-assign.v1",
        "host_version": str(registration.get("host_version") or QUALIFIED_HOST_VERSION),
        "session_id": str(parent_request.get("session_id") or ""),
        "binding_ref": parent_binding_ref,
        "invocation_id": str(parent_request.get("invocation_id") or ""),
        "command_id": f"command:spawn-assign:{identity}",
        "work_unit_id": str(registration.get("work_unit_id") or ""),
        "attempt_id": str(registration.get("attempt_id") or ""),
        "correlation_id": f"correlation:spawn:{identity}",
        "payload_summary": (
            f"Assign {registration.get('work_unit_id')} {registration.get('attempt_id')} "
            f"to {registration.get('role')}"
        ),
        "expected_revision": revision,
        "idempotency_key": assignment_idempotency_key,
        "evidence_refs": [attempt_registration_ref],
        "finding_refs": [],
        "worker_binding_ref": str(registration.get("planned_binding_ref") or ""),
        "attempt_registration_ref": attempt_registration_ref,
    }
    result = execute_control(
        root,
        request,
        bd_path=bd_path,
        capability_root=capability_root,
    )
    return {
        **result,
        "logical_attempt_ref": logical_attempt_ref,
        "assignment_generated_by": "BBK_SPAWN_COMPILER",
    }

def execute_control(
    project_root: str | Path,
    request: Mapping[str, Any],
    *,
    bd_path: str | Path | None = None,
    capability_root: str | Path | None = None,
) -> dict[str, Any]:
    """Validate and execute one typed orchestrator control-plane request."""
    root = Path(project_root).resolve()
    if not root.is_dir():
        raise ControlPlaneError("CONTROL_PLANE_PROJECT_ROOT_INVALID", f"project root does not exist: {root}")
    schema, tool_name = _validate_request_shape(request)
    actor, binding = _actor(root, request, tool_name=tool_name, capability_root=capability_root)
    if schema == "bbk.control-assign.v1":
        coordination, policy = _assignment(
            root, request, actor, binding, capability_root=capability_root
        )
    elif schema == "bbk.control-update.v1":
        coordination, policy = _update(request, actor)
    else:
        coordination, policy = _integration(root, request, actor)
    projection = beads_adapter.execute_coordination(
        root,
        root,
        coordination,
        bd_path=bd_path or os.environ.get("BBK_BD"),
    )
    operation = OPERATION_BY_SCHEMA[schema]
    if operation == "ASSIGN":
        next_action = "Invoke the exact reserved OMP task input for the recorded bound attempt."
    elif operation == "INTEGRATE_REQUEST" and policy["integration_worker_required"]:
        next_action = "Compile and spawn a bound Integration Worker attempt; the orchestrator must not repair content conflicts."
    elif operation == "INTEGRATE_REQUEST":
        next_action = "Submit the request to a qualified content-neutral integration adapter; no candidate effect has occurred."
    else:
        next_action = "Continue only from the returned revision and immutable projection receipt."
    return {
        "schema": "bbk.control-plane-result.v1",
        "status": "PASS",
        "operation": operation,
        "actor": actor,
        "subject": {"work_unit": coordination["work_unit"], "attempt": coordination["attempt"]},
        "coordination_command_digest": f"sha256:{canonical_digest(coordination)}",
        "projection": projection,
        "policy": policy,
        "smallest_next_action": next_action,
    }


def _load_json_argument(value: str) -> dict[str, Any]:
    raw = sys.stdin.read() if value == "-" else Path(value).read_text(encoding="utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ControlPlaneError("CONTROL_PLANE_SCHEMA_INVALID", "request must contain a JSON object")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="exact BBK project root")
    parser.add_argument("--capability-root", help="compiled role-capability directory")
    parser.add_argument("--bd", help="qualified bd executable path")
    subparsers = parser.add_subparsers(dest="command", required=True)
    execute = subparsers.add_parser("execute", help="execute one typed control-plane request")
    execute.add_argument("--request", required=True, help="JSON path or - for stdin")
    return parser


def _error_result(error: BaseException) -> dict[str, Any]:
    if isinstance(error, ControlPlaneError):
        code, message, next_action = error.code, error.message, error.smallest_next_action
    elif isinstance(error, beads_adapter.BeadsAdapterError):
        code, message = error.code, error.message
        next_action = "Repair the typed Beads projection precondition or qualified local Beads substrate, then retry exactly."
    elif isinstance(error, OmpBindingError):
        code, message = error.code, error.message
        next_action = "Repair or renew the exact OMP invocation binding before retrying."
    elif isinstance(error, (json.JSONDecodeError, OSError)):
        code, message = "CONTROL_PLANE_INPUT_ERROR", str(error)
        next_action = "Provide one readable UTF-8 JSON control-plane request."
    else:  # pragma: no cover - defensive structured transport boundary
        code, message = "CONTROL_PLANE_INTERNAL_ERROR", str(error)
        next_action = "Preserve the failure evidence and repair the control-plane implementation before retrying."
    return {
        "schema": "bbk.control-plane-result.v1",
        "status": "BLOCK",
        "reason_code": code,
        "message": message,
        "smallest_next_action": next_action,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        request = _load_json_argument(args.request)
        result = execute_control(
            args.root,
            request,
            bd_path=args.bd,
            capability_root=args.capability_root,
        )
        code = 0
    except BaseException as error:  # structured CLI boundary; never emit a raw traceback
        result = _error_result(error)
        code = 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
