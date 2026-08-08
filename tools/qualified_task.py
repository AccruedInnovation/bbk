#!/usr/bin/env python3
"""Execute one declared mise task from an exact active worker binding.

The caller supplies task vocabulary, arguments, and idempotency only.  BBK
resolves the active binding, verifies the current role-capability manifest,
derives the workspace, jj change, candidate digest, and mise configuration
digest itself, and then invokes the real mise adapter.  Qualified tasks are
candidate-preserving: any candidate change is detected after effect and causes
a structured failure without claiming an operating-system sandbox.
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
    from omp_binding_registry import OmpBindingError, resolve_binding_reference
    from substrate import git_adapter, jj_adapter, mise_adapter
except ImportError:  # pragma: no cover - installed-package import fallback
    from .gate_kernel import canonical_digest
    from .governed_state import all_receipts, append_receipt, utc_now
    from .omp_binding_registry import OmpBindingError, resolve_binding_reference
    from .substrate import git_adapter, jj_adapter, mise_adapter

ROOT = Path(os.environ.get("BBK_PACKAGE_ROOT", Path(__file__).resolve().parents[1])).resolve()
CAPABILITY_ROOT = ROOT / "spec" / "role-capabilities"
QUALIFIED_HOST_VERSION = "omp/16.4.8"
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+\-]*$")
REQUEST_FIELDS = frozenset({
    "schema", "host_version", "session_id", "invocation_id", "binding_ref", "task",
    "arguments", "environment_allowlist", "idempotency_key",
})


class QualifiedTaskError(RuntimeError):
    """A bound task request is incomplete, unauthorized, stale, or unsafe."""

    def __init__(self, code: str, message: str, *, smallest_next_action: str = ""):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.smallest_next_action = smallest_next_action or "Use the current active worker binding and a declared candidate-preserving mise task."


def _text(value: Any, field: str, *, safe_id: bool = True) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QualifiedTaskError("BOUND_TASK_REQUEST_INVALID", f"{field} must be a non-empty string")
    result = value.strip()
    if safe_id and not SAFE_ID_RE.fullmatch(result):
        raise QualifiedTaskError("BOUND_TASK_REQUEST_INVALID", f"{field} contains unsupported characters")
    return result


def _string_list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise QualifiedTaskError("BOUND_TASK_REQUEST_INVALID", f"{field} must be an array of strings")
    result = [item for item in value]
    if field == "environment_allowlist" and len(result) != len(set(result)):
        raise QualifiedTaskError("BOUND_TASK_REQUEST_INVALID", "environment_allowlist contains duplicates")
    return result


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QualifiedTaskError("BOUND_TASK_CAPABILITY_INVALID", f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise QualifiedTaskError("BOUND_TASK_CAPABILITY_INVALID", f"{path} must contain an object")
    return value


def _capability(role: str, capability_root: str | Path | None = None) -> tuple[dict[str, Any], str, set[str]]:
    root = Path(os.environ.get("BBK_ROLE_CAPABILITY_ROOT") or capability_root or CAPABILITY_ROOT).resolve()
    path = root / f"{role}.json"
    if not path.is_file() or path.is_symlink():
        raise QualifiedTaskError("BOUND_TASK_CAPABILITY_NOT_FOUND", f"compiled capability is missing for {role}")
    value = _read_json(path)
    if value.get("schema") != "bbk.role-capability.v1" or value.get("role") != role:
        raise QualifiedTaskError("BOUND_TASK_CAPABILITY_INVALID", f"{path} is not the capability for {role}")
    manifest_digest = f"sha256:{canonical_digest({key: item for key, item in value.items() if key != 'manifest_digest'})}"
    if value.get("manifest_digest") != manifest_digest:
        raise QualifiedTaskError("BOUND_TASK_CAPABILITY_DIGEST_MISMATCH", f"capability manifest is stale for {role}")
    policy_version = str(value.get("policy_version", ""))
    canonical_ref = f"role:{role}@{policy_version}#{manifest_digest}"
    return value, canonical_ref, {manifest_digest, f"role:{role}@{policy_version}", canonical_ref}


def _validate_request(request: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(request, Mapping) or request.get("schema") != "bbk.bound-qualified-task-execution.v1":
        raise QualifiedTaskError("BOUND_TASK_SCHEMA_INVALID", "request schema must be bbk.bound-qualified-task-execution.v1")
    unknown = sorted(set(request) - REQUEST_FIELDS)
    if unknown:
        raise QualifiedTaskError("BOUND_TASK_SCHEMA_INVALID", f"unsupported fields: {', '.join(unknown)}")
    normalized = {
        "schema": "bbk.bound-qualified-task-execution.v1",
        "host_version": _text(request.get("host_version"), "host_version"),
        "session_id": _text(request.get("session_id"), "session_id"),
        "invocation_id": _text(request.get("invocation_id"), "invocation_id"),
        "binding_ref": _text(request.get("binding_ref"), "binding_ref"),
        "task": _text(request.get("task"), "task"),
        "idempotency_key": _text(request.get("idempotency_key"), "idempotency_key"),
        "arguments": _string_list(request.get("arguments", []), "arguments"),
        "environment_allowlist": _string_list(request.get("environment_allowlist", []), "environment_allowlist"),
    }
    if normalized["host_version"] != QUALIFIED_HOST_VERSION:
        raise QualifiedTaskError("OMP_HOST_UNQUALIFIED_FOR_BOUND_TASK", f"host {normalized['host_version']!r} is not qualified")
    return normalized


def _prior_bound_receipt(project_root: Path, idempotency_key: str) -> dict[str, Any] | None:
    matches = [
        receipt for receipt in all_receipts(project_root)
        if receipt.get("receipt_kind") == "BOUND_QUALIFIED_TASK"
        and receipt.get("content", {}).get("idempotency_key") == idempotency_key
    ]
    if len(matches) > 1:
        raise QualifiedTaskError(
            "BOUND_TASK_IDEMPOTENCY_STATE_CORRUPT",
            f"duplicate bound-task idempotency key {idempotency_key}",
        )
    return matches[0] if matches else None


def execute_bound_task(
    project_root: str | Path,
    request: Mapping[str, Any],
    *,
    git_path: str | Path | None = None,
    jj_path: str | Path | None = None,
    mise_path: str | Path | None = None,
    capability_root: str | Path | None = None,
    environment: Mapping[str, str] | None = None,
    test_adapter: bool = False,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Execute one candidate-preserving task through a current worker binding."""
    root = Path(project_root).resolve()
    if not root.is_dir():
        raise QualifiedTaskError("BOUND_TASK_PROJECT_ROOT_INVALID", f"project root does not exist: {root}")
    normalized = _validate_request(request)
    binding = resolve_binding_reference(root, normalized["binding_ref"])
    if binding is None:
        raise QualifiedTaskError("BOUND_TASK_BINDING_NOT_ACTIVE", f"binding {normalized['binding_ref']} is not active")
    bound = binding.get("request", {})
    mismatches = []
    if bound.get("session_id") != normalized["session_id"]:
        mismatches.append("session_id")
    if bound.get("invocation_id") != normalized["invocation_id"]:
        mismatches.append("invocation_id")
    if mismatches:
        raise QualifiedTaskError("BOUND_TASK_CORRELATION_MISMATCH", f"active binding differs from host identity: {', '.join(mismatches)}")

    role = str(bound.get("role", ""))
    capability, capability_ref, accepted_refs = _capability(role, capability_root)
    if str(binding.get("capability_ref", "")) not in accepted_refs:
        raise QualifiedTaskError("BOUND_TASK_CAPABILITY_BINDING_MISMATCH", f"binding does not identify current capability for {role}")
    if "bbk_task_run" not in capability.get("allowed_tools", []):
        raise QualifiedTaskError("BOUND_TASK_ROLE_DENIED", f"{role} cannot use bbk_task_run")
    if capability.get("scope_rules", {}).get("workspace_source") != "REGISTRY_BINDING":
        raise QualifiedTaskError("BOUND_TASK_WORKSPACE_POLICY_INVALID", f"{role} does not use a registry-bound workspace")

    raw_workspace = Path(str(bound.get("workspace_ref", "")))
    if not raw_workspace.is_absolute() or not raw_workspace.exists() or not raw_workspace.is_dir() or raw_workspace.is_symlink():
        raise QualifiedTaskError("BOUND_TASK_WORKSPACE_INVALID", "binding workspace_ref is not a real absolute directory")
    workspace = raw_workspace.resolve()
    if workspace == root:
        raise QualifiedTaskError(
            "BOUND_TASK_WORKSPACE_CONFLATES_GOVERNANCE_ROOT",
            "candidate workspace cannot be the governance-journal root; task receipts would change the candidate",
        )
    try:
        identity = jj_adapter.identity(workspace, jj_path=jj_path)
    except jj_adapter.JjAdapterError as exc:
        raise QualifiedTaskError(exc.code, exc.message) from exc
    bound_change = str(bound.get("jj_change_id", ""))
    if not bound_change or identity.get("jj_change_id") != bound_change:
        raise QualifiedTaskError(
            "BOUND_TASK_JJ_CHANGE_MISMATCH",
            f"workspace current jj change {identity.get('jj_change_id')!r} differs from binding {bound_change!r}",
        )
    try:
        git_root = jj_adapter.git_repository_root(workspace, jj_path=jj_path)
        before = git_adapter.freeze_candidate(
            workspace,
            candidate_id=str(bound.get("candidate_ref", "candidate:bound-task")),
            jj_change_id=bound_change,
            git_path=git_path,
            git_repository_root=git_root,
        )
        toolchain_digest = mise_adapter.toolchain_definition_digest(workspace)
    except (jj_adapter.JjAdapterError, git_adapter.GitAdapterError, mise_adapter.MiseAdapterError) as exc:
        raise QualifiedTaskError(getattr(exc, "code", "BOUND_TASK_CANDIDATE_FREEZE_FAILED"), getattr(exc, "message", str(exc))) from exc

    request_digest = f"sha256:{canonical_digest(normalized)}"
    prior = _prior_bound_receipt(root, normalized["idempotency_key"])
    if prior:
        content = prior.get("content", {})
        prior_after = content.get("candidate_after", {})
        if content.get("request_digest") != request_digest:
            raise QualifiedTaskError(
                "BOUND_TASK_IDEMPOTENCY_COLLISION",
                "idempotency key was reused for a different bound task request",
            )
        if content.get("binding_ref") != binding.get("binding_id"):
            raise QualifiedTaskError(
                "BOUND_TASK_IDEMPOTENCY_COLLISION",
                "idempotency key is bound to a different invocation binding",
            )
        if prior_after.get("digest") != before.get("digest"):
            raise QualifiedTaskError(
                "BOUND_TASK_IDEMPOTENCY_STATE_DRIFT",
                "candidate differs from the state recorded after the prior bound task result",
            )
        return {
            **content,
            "idempotent_reuse": True,
            "receipt_ref": prior["receipt_id"],
            "receipt_created": False,
        }

    internal_request = {
        "schema": "bbk.qualified-task-request.v1",
        "binding_ref": binding["binding_id"],
        "task": normalized["task"],
        "candidate_digest": before["digest"],
        "toolchain_definition_digest": toolchain_digest,
        "idempotency_key": normalized["idempotency_key"],
        "arguments": normalized["arguments"],
        "environment_allowlist": normalized["environment_allowlist"],
    }
    try:
        task_result = mise_adapter.execute(
            root,
            internal_request,
            mise_path_value=mise_path,
            test_adapter=test_adapter,
            environment=environment,
            execution_root=workspace,
        )
        after = git_adapter.freeze_candidate(
            workspace,
            candidate_id=str(bound.get("candidate_ref", "candidate:bound-task")),
            jj_change_id=bound_change,
            git_path=git_path,
            git_repository_root=git_root,
        )
    except (mise_adapter.MiseAdapterError, git_adapter.GitAdapterError) as exc:
        raise QualifiedTaskError(getattr(exc, "code", "BOUND_TASK_EXECUTION_FAILED"), getattr(exc, "message", str(exc))) from exc

    candidate_unchanged = before["digest"] == after["digest"]
    task_passed = task_result.get("status") == "PASS" and task_result.get("exit_status") == 0
    status = "PASS" if task_passed and candidate_unchanged else "FAIL"
    reason_code = None
    message = "Qualified task passed and preserved the exact candidate."
    if not task_passed:
        reason_code = "QUALIFIED_TASK_FAILED"
        message = f"Qualified task exited with status {task_result.get('exit_status')}; no semantic PASS is claimed."
    elif not candidate_unchanged:
        reason_code = "QUALIFIED_TASK_CANDIDATE_MUTATED"
        message = "Qualified task changed candidate content; the effect was detected after execution and was not rolled back."

    result_core = {
        "schema": "bbk.bound-qualified-task-result.v1",
        "status": status,
        "reason_code": reason_code,
        "message": message,
        "idempotency_key": normalized["idempotency_key"],
        "request_digest": request_digest,
        "binding_ref": binding["binding_id"],
        "capability_ref": capability_ref,
        "session_id": normalized["session_id"],
        "invocation_id": normalized["invocation_id"],
        "role": role,
        "task": normalized["task"],
        "workspace_ref": str(workspace),
        "jj_change_id": bound_change,
        "candidate_before": before,
        "candidate_after": after,
        "candidate_unchanged": candidate_unchanged,
        "toolchain_definition_digest": toolchain_digest,
        "qualified_task_receipt_ref": task_result.get("receipt_id"),
        "mise_path": task_result.get("mise_path"),
        "mise_version": task_result.get("mise_version"),
        "exit_status": task_result.get("exit_status"),
        "output_digest": task_result.get("output_digest"),
        "idempotent_reuse": False,
        "effect_boundary": "DETECT_ONLY_NO_OS_SANDBOX",
    }
    receipt_id = f"sha256:{canonical_digest(result_core)}"
    receipt, created = append_receipt(
        root,
        "BOUND_QUALIFIED_TASK",
        result_core,
        receipt_id=receipt_id,
        recorded_at=recorded_at or utc_now(),
    )
    return {**result_core, "receipt_ref": receipt["receipt_id"], "receipt_created": created}



def _load_json_argument(value: str) -> dict[str, Any]:
    raw = sys.stdin.read() if value == "-" else (Path(value).read_text(encoding="utf-8") if Path(value).is_file() else value)
    try:
        parsed = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise QualifiedTaskError("BOUND_TASK_JSON_INVALID", f"cannot load request JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise QualifiedTaskError("BOUND_TASK_JSON_INVALID", "request JSON must be an object")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    execute = sub.add_parser("execute")
    execute.add_argument("--request", required=True, help="JSON object, file path, or - for stdin")
    execute.add_argument("--git", default=os.environ.get("BBK_GIT"))
    execute.add_argument("--jj", default=os.environ.get("BBK_JJ"))
    execute.add_argument("--mise", default=os.environ.get("BBK_MISE"))
    execute.add_argument("--test-adapter", action="store_true")
    execute.add_argument("--recorded-at")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = execute_bound_task(
            args.root,
            _load_json_argument(args.request),
            git_path=args.git,
            jj_path=args.jj,
            mise_path=args.mise,
            environment=os.environ,
            test_adapter=bool(args.test_adapter),
            recorded_at=args.recorded_at,
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result.get("status") == "PASS" else 1
    except (QualifiedTaskError, OmpBindingError, jj_adapter.JjAdapterError, git_adapter.GitAdapterError, mise_adapter.MiseAdapterError) as exc:
        print(json.dumps({
            "schema": "bbk.bound-qualified-task-error.v1",
            "status": "BLOCK",
            "reason_code": getattr(exc, "code", "BOUND_TASK_FAILED"),
            "message": getattr(exc, "message", str(exc)),
            "smallest_next_action": getattr(exc, "smallest_next_action", "Use the current worker binding and a declared candidate-preserving task."),
        }, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
