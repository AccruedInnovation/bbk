#!/usr/bin/env python3
"""Bound, pre-effect-authorized filesystem tools for governed OMP workers.

The adapter never accepts process CWD as workspace authority.  Every request is
resolved through an active immutable invocation binding, checked against the
compiled role-capability manifest and Gate Kernel, applied atomically where
possible, reconciled against Git/jj observations, and recorded as an immutable
receipt below the campaign project root.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import stat
import tempfile
from pathlib import Path, PureWindowsPath
from typing import Any, Mapping, Sequence

from gate_kernel import canonical_digest, evaluate, load_policy
from governed_state import (
    GovernanceStateError,
    all_receipts,
    append_gate_receipt,
    append_receipt,
    append_vcs_receipt,
)
from omp_binding_registry import QUALIFIED_HOSTS, resolve_binding_reference
from substrate import git_adapter, jj_adapter

MODULE_ROOT = Path(__file__).resolve().parent
ROOT = MODULE_ROOT if (MODULE_ROOT / "spec").is_dir() else MODULE_ROOT.parent
CAPABILITY_ROOT = ROOT / "spec" / "role-capabilities"
POLICY_PATH = ROOT / "spec" / "policies" / "governed-software-v1.json"
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]*$")
DIGEST_RE = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")
MAX_CONTENT_BYTES = 16 * 1024 * 1024
MUTATING_OPERATIONS = frozenset({"WRITE", "EDIT", "DELETE"})
TOOL_FOR_OPERATION = {
    "READ": "bbk_governed_read",
    "WRITE": "bbk_governed_write",
    "EDIT": "bbk_governed_edit",
    "DELETE": "bbk_governed_delete",
}


class GovernedFilesystemError(RuntimeError):
    """A governed filesystem request failed closed before truthful completion."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        smallest_next_action: str = "Correct the typed request or binding and retry.",
        details: Mapping[str, Any] | None = None,
    ):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.smallest_next_action = smallest_next_action
        self.details = dict(details or {})


def _sha256_bytes(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def payload_digest(payload: Mapping[str, Any]) -> str:
    """Digest an operation payload without persisting its raw content."""
    return f"sha256:{canonical_digest(dict(payload))}"


def _normalized_digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or not DIGEST_RE.fullmatch(value):
        raise GovernedFilesystemError("MUTATION_INTENT_INVALID", f"{field} must be a SHA-256 digest")
    return f"sha256:{value.removeprefix('sha256:')}"


def _safe_id(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or not SAFE_ID_RE.fullmatch(value):
        raise GovernedFilesystemError("MUTATION_INTENT_INVALID", f"{field} is missing or contains unsupported characters")
    return value


def validate_intent(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or value.get("schema") != "bbk.mutation-intent.v1":
        raise GovernedFilesystemError("MUTATION_INTENT_INVALID", "intent schema must be bbk.mutation-intent.v1")
    allowed = {
        "schema", "binding_ref", "operation", "path", "content_or_patch_digest",
        "expected_precondition", "mutation_class", "idempotency_key",
    }
    extra = sorted(set(value) - allowed)
    if extra:
        raise GovernedFilesystemError("MUTATION_INTENT_INVALID", f"unsupported intent fields: {', '.join(extra)}")
    operation = str(value.get("operation", "")).upper()
    if operation not in TOOL_FOR_OPERATION:
        raise GovernedFilesystemError("MUTATION_OPERATION_INVALID", f"unsupported operation {operation!r}")
    raw_path = value.get("path")
    if not isinstance(raw_path, str) or not raw_path or len(raw_path) > 4096 or "\x00" in raw_path:
        raise GovernedFilesystemError("MUTATION_PATH_INVALID", "path must be a non-empty bounded string")
    precondition = value.get("expected_precondition")
    if not isinstance(precondition, Mapping):
        raise GovernedFilesystemError("MUTATION_PRECONDITION_INVALID", "expected_precondition must be an object")
    if set(precondition) - {"kind", "sha256"}:
        raise GovernedFilesystemError("MUTATION_PRECONDITION_INVALID", "precondition contains unsupported fields")
    kind = str(precondition.get("kind", "")).upper()
    if kind not in {"ANY", "ABSENT", "PRESENT", "SHA256"}:
        raise GovernedFilesystemError("MUTATION_PRECONDITION_INVALID", f"unsupported precondition kind {kind!r}")
    normalized_precondition: dict[str, Any] = {"kind": kind}
    if kind == "SHA256":
        normalized_precondition["sha256"] = _normalized_digest(precondition.get("sha256"), "expected_precondition.sha256")
    elif "sha256" in precondition:
        raise GovernedFilesystemError("MUTATION_PRECONDITION_INVALID", "sha256 is valid only with kind SHA256")
    return {
        "schema": "bbk.mutation-intent.v1",
        "binding_ref": _safe_id(value.get("binding_ref"), "binding_ref"),
        "operation": operation,
        "path": raw_path,
        "content_or_patch_digest": _normalized_digest(value.get("content_or_patch_digest"), "content_or_patch_digest"),
        "expected_precondition": normalized_precondition,
        "mutation_class": _safe_id(value.get("mutation_class"), "mutation_class"),
        "idempotency_key": _safe_id(value.get("idempotency_key"), "idempotency_key"),
    }


def validate_payload(operation: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise GovernedFilesystemError("MUTATION_PAYLOAD_INVALID", "payload must be an object")
    value = dict(payload)
    if operation in {"READ", "DELETE"}:
        if value:
            raise GovernedFilesystemError("MUTATION_PAYLOAD_INVALID", f"{operation} payload must be empty")
        return {}
    if operation == "WRITE":
        if set(value) - {"content", "encoding"} or not isinstance(value.get("content"), str):
            raise GovernedFilesystemError("MUTATION_PAYLOAD_INVALID", "WRITE requires string content and optional encoding")
        encoding = str(value.get("encoding", "utf-8")).lower()
        if encoding not in {"utf-8", "base64"}:
            raise GovernedFilesystemError("MUTATION_PAYLOAD_INVALID", "WRITE encoding must be utf-8 or base64")
        normalized = {"content": value["content"], "encoding": encoding}
        _write_payload_bytes(normalized)
        return normalized
    if set(value) - {"old_text", "new_text", "replace_all"}:
        raise GovernedFilesystemError("MUTATION_PAYLOAD_INVALID", "EDIT payload contains unsupported fields")
    if not isinstance(value.get("old_text"), str) or not isinstance(value.get("new_text"), str):
        raise GovernedFilesystemError("MUTATION_PAYLOAD_INVALID", "EDIT requires old_text and new_text strings")
    replace_all = value.get("replace_all", False)
    if not isinstance(replace_all, bool):
        raise GovernedFilesystemError("MUTATION_PAYLOAD_INVALID", "EDIT replace_all must be boolean")
    if value["old_text"] == "":
        raise GovernedFilesystemError("MUTATION_PAYLOAD_INVALID", "EDIT old_text cannot be empty")
    return {"old_text": value["old_text"], "new_text": value["new_text"], "replace_all": replace_all}


def _write_payload_bytes(payload: Mapping[str, Any]) -> bytes:
    if payload.get("encoding") == "base64":
        try:
            result = base64.b64decode(str(payload["content"]), validate=True)
        except (ValueError, TypeError) as exc:
            raise GovernedFilesystemError("MUTATION_PAYLOAD_INVALID", f"WRITE base64 content is invalid: {exc}") from exc
    else:
        result = str(payload["content"]).encode("utf-8")
    if len(result) > MAX_CONTENT_BYTES:
        raise GovernedFilesystemError("MUTATION_CONTENT_TOO_LARGE", f"content exceeds {MAX_CONTENT_BYTES} bytes")
    return result


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GovernedFilesystemError("ROLE_CAPABILITY_INVALID", f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise GovernedFilesystemError("ROLE_CAPABILITY_INVALID", f"{path} is not a JSON object")
    return value


def _load_capability(role: str, capability_ref: str, capability_root: Path | None = None) -> dict[str, Any]:
    root = Path(os.environ.get("BBK_ROLE_CAPABILITY_ROOT") or capability_root or CAPABILITY_ROOT).resolve()
    path = root / f"{role}.json"
    if not path.is_file() or path.is_symlink():
        raise GovernedFilesystemError("ROLE_CAPABILITY_NOT_FOUND", f"compiled capability manifest is missing for {role}")
    manifest = _read_json(path)
    if manifest.get("schema") != "bbk.role-capability.v1" or manifest.get("role") != role:
        raise GovernedFilesystemError("ROLE_CAPABILITY_INVALID", f"capability manifest does not bind role {role}")
    expected_digest = f"sha256:{canonical_digest({key: item for key, item in manifest.items() if key != 'manifest_digest'})}"
    if manifest.get("manifest_digest") != expected_digest:
        raise GovernedFilesystemError("ROLE_CAPABILITY_DIGEST_MISMATCH", f"capability manifest digest is stale for {role}")
    policy_version = str(manifest.get("policy_version", ""))
    accepted_refs = {
        expected_digest,
        f"role:{role}@{policy_version}",
        f"role:{role}@{policy_version}#{expected_digest}",
    }
    if capability_ref not in accepted_refs:
        raise GovernedFilesystemError(
            "ROLE_CAPABILITY_BINDING_MISMATCH",
            f"binding capability_ref does not identify the current manifest for {role}",
            details={"expected_refs": sorted(accepted_refs), "received": capability_ref},
        )
    return manifest


def _resolve_binding_exact(
    project_root: Path,
    *,
    binding_ref: str,
    session_id: str,
    invocation_id: str,
) -> dict[str, Any]:
    binding = resolve_binding_reference(project_root, binding_ref)
    if binding is None:
        raise GovernedFilesystemError(
            "MUTATION_BINDING_NOT_ACTIVE",
            f"active binding {binding_ref} does not exist",
            smallest_next_action="Use the current non-superseded binding for this invocation.",
        )
    request = binding.get("request", {})
    mismatches = []
    if request.get("session_id") != session_id:
        mismatches.append("session_id")
    if request.get("invocation_id") != invocation_id:
        mismatches.append("invocation_id")
    if mismatches:
        raise GovernedFilesystemError(
            "MUTATION_BINDING_IDENTITY_MISMATCH",
            f"binding differs from exact host identity: {', '.join(mismatches)}",
            smallest_next_action="Use the binding created for the current session and invocation.",
        )
    return binding


def _portable_absolute(raw: str) -> bool:
    windows = PureWindowsPath(raw)
    return Path(raw).is_absolute() or windows.is_absolute() or bool(windows.drive) or raw.startswith(("/", "\\"))


def _is_within(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def _assert_no_symlink_ancestry(root: Path, candidate: Path) -> None:
    if root.is_symlink():
        raise GovernedFilesystemError("MUTATION_WORKSPACE_SYMLINK_FORBIDDEN", f"workspace is a symlink: {root}")
    relative = candidate.relative_to(root)
    probe = root
    parts = relative.parts
    for index, component in enumerate(parts):
        probe = probe / component
        if not os.path.lexists(probe):
            continue
        try:
            mode = os.lstat(probe).st_mode
        except OSError as exc:
            raise GovernedFilesystemError("MUTATION_PATH_INSPECTION_FAILED", f"cannot inspect {probe}: {exc}") from exc
        if stat.S_ISLNK(mode):
            raise GovernedFilesystemError(
                "MUTATION_PATH_SYMLINK_FORBIDDEN",
                f"bound path traverses symlink component {probe}",
                smallest_next_action="Use a real path inside the bound workspace; symlink traversal is not an authority boundary.",
            )
        if index < len(parts) - 1 and not stat.S_ISDIR(mode):
            raise GovernedFilesystemError("MUTATION_PATH_PARENT_NOT_DIRECTORY", f"path parent is not a directory: {probe}")


def _canonical_workspace(request: Mapping[str, Any]) -> Path:
    raw = str(request.get("workspace_ref", ""))
    if not raw or _portable_absolute(raw) is False:
        raise GovernedFilesystemError(
            "MUTATION_WORKSPACE_NOT_ABSOLUTE",
            "binding workspace_ref must be absolute; it cannot be interpreted relative to process CWD",
        )
    workspace = Path(raw).resolve(strict=True)
    if not workspace.is_dir() or workspace.is_symlink():
        raise GovernedFilesystemError("MUTATION_WORKSPACE_INVALID", f"bound workspace is not a real directory: {workspace}")
    return workspace


def _canonical_target(workspace: Path, raw: str) -> tuple[Path, str]:
    if _portable_absolute(raw):
        raise GovernedFilesystemError(
            "MUTATION_ABSOLUTE_PATH_FORBIDDEN",
            "tool path must be workspace-relative",
            smallest_next_action="Provide a relative path inside the bound workspace.",
        )
    normalized = raw.replace("\\", "/")
    parts = normalized.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise GovernedFilesystemError("MUTATION_PATH_TRAVERSAL_FORBIDDEN", "path contains empty, dot, or parent components")
    candidate = workspace.joinpath(*parts)
    _assert_no_symlink_ancestry(workspace, candidate)
    resolved = candidate.resolve(strict=False)
    if not _is_within(workspace, resolved):
        raise GovernedFilesystemError("MUTATION_WORKSPACE_ESCAPE", f"resolved path escapes bound workspace: {raw}")
    return resolved, resolved.relative_to(workspace).as_posix()


def _scope_prefixes(workspace: Path, scope: Mapping[str, Any]) -> tuple[list[Path], list[str]]:
    raw_prefixes = scope.get("path_prefixes")
    if not isinstance(raw_prefixes, list) or not raw_prefixes:
        raise GovernedFilesystemError("MUTATION_SCOPE_INVALID", "binding has no path_prefixes")
    physical: list[Path] = []
    relative: list[str] = []
    for raw_value in raw_prefixes:
        raw = str(raw_value)
        if not _portable_absolute(raw):
            raise GovernedFilesystemError(
                "MUTATION_SCOPE_NOT_ABSOLUTE",
                "binding path_prefixes must be absolute and independent of process CWD",
            )
        prefix = Path(raw).resolve(strict=False)
        if not _is_within(workspace, prefix):
            raise GovernedFilesystemError("MUTATION_SCOPE_ESCAPE", f"binding prefix escapes workspace: {prefix}")
        _assert_no_symlink_ancestry(workspace, prefix)
        physical.append(prefix)
        rel = prefix.relative_to(workspace).as_posix()
        relative.append(rel if rel != "." else ".")
    return physical, relative


def _sealed_marker(workspace: Path, target: Path, relative_path: str) -> Path | None:
    parts = tuple(part.casefold() for part in Path(relative_path).parts)
    if parts[:3] == (".bbk", "artifacts", "sealed"):
        return workspace / ".bbk" / "artifacts" / "sealed"
    probe = target if target.exists() and target.is_dir() else target.parent
    while _is_within(workspace, probe):
        marker = probe / "bbk-package.json"
        if os.path.lexists(marker):
            if marker.is_symlink() or not marker.is_file():
                raise GovernedFilesystemError("SEALED_MARKER_UNSAFE", f"unsafe package marker at {marker}")
            try:
                package = json.loads(marker.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise GovernedFilesystemError("SEALED_MARKER_INVALID", f"cannot inspect package marker {marker}: {exc}") from exc
            if isinstance(package, Mapping) and str(package.get("lifecycle", "")).upper() == "SEALED":
                return marker
        if probe == workspace:
            break
        probe = probe.parent
    return None


def _accepted_subject(relative_path: str) -> bool:
    parts = tuple(part.casefold() for part in Path(relative_path).parts)
    protected = (
        (".bbk", "governance", "receipts"),
        (".bbk", "governance", "bindings"),
        (".bbk", "artifacts", "publications"),
    )
    return any(parts[: len(prefix)] == prefix for prefix in protected)


def _file_state(path: Path) -> tuple[bool, bytes | None, str | None]:
    if not os.path.lexists(path):
        return False, None, None
    mode = os.lstat(path).st_mode
    if stat.S_ISLNK(mode):
        raise GovernedFilesystemError("MUTATION_PATH_SYMLINK_FORBIDDEN", f"target is a symlink: {path}")
    if not stat.S_ISREG(mode):
        raise GovernedFilesystemError("MUTATION_TARGET_NOT_REGULAR_FILE", f"target is not a regular file: {path}")
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise GovernedFilesystemError("MUTATION_TARGET_READ_FAILED", f"cannot read target {path}: {exc}") from exc
    if len(data) > MAX_CONTENT_BYTES:
        raise GovernedFilesystemError("MUTATION_CONTENT_TOO_LARGE", f"target exceeds {MAX_CONTENT_BYTES} bytes")
    return True, data, _sha256_bytes(data)


def _check_precondition(precondition: Mapping[str, Any], exists: bool, digest: str | None) -> tuple[bool, str]:
    kind = precondition["kind"]
    if kind == "ANY":
        return True, ""
    if kind == "ABSENT":
        return (not exists), "target is present but ABSENT was required"
    if kind == "PRESENT":
        return exists, "target is absent but PRESENT was required"
    expected = precondition["sha256"]
    return exists and digest == expected, f"target digest is {digest or 'ABSENT'}, expected {expected}"


def _holder_kind(authority_ref: str) -> str:
    lowered = authority_ref.casefold()
    if "user" in lowered or "human" in lowered:
        return "USER"
    if "system" in lowered or "adapter" in lowered:
        return "SYSTEM"
    return "EXTERNAL"


def _gate_request(
    *,
    policy: Mapping[str, Any],
    binding: Mapping[str, Any],
    intent: Mapping[str, Any],
    session_id: str,
    relative_path: str,
    within_scope: bool,
    sealed_subject: bool,
    capability_allowed: bool,
) -> dict[str, Any]:
    request = binding["request"]
    authority_ref = str(request["authority_ref"])
    return {
        "schema": "bbk.gate-evaluation-request.v1",
        "policy_ref": f"{policy['policy_id']}@{policy['policy_version']}",
        "actor": {
            "role": request["role"],
            "actor_id": f"session:{session_id}",
            "actor_kind": "MODEL",
        },
        "authority": {
            "authority_ref": authority_ref,
            "holder_kind": _holder_kind(authority_ref),
            "scopes": [f"binding:{binding['binding_id']}"],
        },
        "intent": {
            "operation": intent["operation"],
            "mutation_class": intent["mutation_class"],
            "path": relative_path,
            "within_scope": within_scope,
            "sealed_subject": sealed_subject,
            "accepted_subject": _accepted_subject(relative_path),
            "capability_allowed": capability_allowed,
        },
        "state_snapshot": {
            "snapshot_ref": binding["immutable_digest"],
            "binding_valid": True,
            "evidence_current": True,
            "manual_gate_pass": False,
        },
        "candidate_ref": request["candidate_ref"],
        "work_unit_id": request["work_unit_id"],
        "idempotency_key": intent["idempotency_key"],
        "override": {
            "present": False,
            "requested_by_kind": "NONE",
            "authority_ref": authority_ref,
            "scopes": [],
        },
    }


def _result_receipt(
    project_root: Path,
    *,
    binding: Mapping[str, Any],
    intent: Mapping[str, Any],
    request_digest: str,
    session_id: str,
    invocation_id: str,
    gate_decision_ref: str,
    effect_status: str,
    observed_path: str,
    vcs_reconciliation_ref: str,
    before_digest: str | None,
    after_digest: str | None,
    changed_paths: Sequence[str],
    reason_code: str = "",
    message: str = "",
) -> dict[str, Any]:
    result_core: dict[str, Any] = {
        "schema": "bbk.mutation-result.v1",
        "gate_decision_ref": gate_decision_ref,
        "effect_status": effect_status,
        "observed_path": observed_path,
        "vcs_reconciliation_ref": vcs_reconciliation_ref,
    }
    if before_digest:
        result_core["before_digest"] = before_digest
    if after_digest:
        result_core["after_digest"] = after_digest
    if changed_paths:
        result_core["changed_paths"] = sorted(set(changed_paths))
    content = {
        "schema": "bbk.filesystem-mutation-receipt.v1",
        "binding_ref": binding["binding_id"],
        "session_id": session_id,
        "invocation_id": invocation_id,
        "candidate_ref": binding["request"]["candidate_ref"],
        "work_unit_id": binding["request"]["work_unit_id"],
        "idempotency_key": intent["idempotency_key"],
        "request_digest": request_digest,
        "intent": dict(intent),
        "result": result_core,
        "reason_code": reason_code,
        "message": message,
    }
    receipt_id = f"sha256:{canonical_digest(content)}"
    receipt, _ = append_receipt(project_root, "FILESYSTEM_MUTATION", content, receipt_id=receipt_id)
    return {**result_core, "receipt_ref": receipt["receipt_id"]}


def _find_idempotent_receipt(project_root: Path, idempotency_key: str) -> dict[str, Any] | None:
    matches = [
        receipt for receipt in all_receipts(project_root)
        if receipt.get("receipt_kind") == "FILESYSTEM_MUTATION"
        and receipt.get("content", {}).get("idempotency_key") == idempotency_key
    ]
    if len(matches) > 1:
        raise GovernedFilesystemError("MUTATION_IDEMPOTENCY_AMBIGUOUS", "multiple mutation receipts use the same idempotency key")
    return matches[0] if matches else None


def _read_output(data: bytes | None) -> dict[str, Any]:
    if data is None:
        return {}
    try:
        return {"content": data.decode("utf-8"), "encoding": "utf-8"}
    except UnicodeDecodeError:
        return {"content": base64.b64encode(data).decode("ascii"), "encoding": "base64"}


def _atomic_write(path: Path, data: bytes, previous_mode: int | None) -> None:
    parent = path.parent
    if not parent.is_dir() or parent.is_symlink():
        raise GovernedFilesystemError("MUTATION_PARENT_MISSING", f"target parent is not a real directory: {parent}")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.bbk-", suffix=".tmp", dir=parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if previous_mode is not None:
            os.chmod(temporary, previous_mode)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _git_backing_root(workspace: Path, *, jj_path: str | Path | None) -> Path:
    """Resolve the Git object store backing a jj workspace without CWD authority.

    Real secondary jj workspaces resolve through ``jj git root``.  Ordinary
    Git roots and bounded unit-test adapters may not expose a runnable jj
    binary, so they fall back only to the exact Git repository boundary.
    """
    try:
        return jj_adapter.git_repository_root(workspace, jj_path=jj_path)
    except jj_adapter.JjAdapterError as jj_exc:
        try:
            return git_adapter.repository_root(workspace)
        except git_adapter.GitAdapterError as git_exc:
            raise GovernedFilesystemError(
                jj_exc.code,
                jj_exc.message,
                details={
                    "git_fallback_code": git_exc.code,
                    "git_fallback_message": git_exc.message,
                },
            ) from jj_exc


def _vcs_context(
    workspace: Path,
    binding: Mapping[str, Any],
    scope_prefixes: Sequence[str],
    *,
    jj_path: str | Path | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    request = binding["request"]
    bound_change = str(request.get("jj_change_id", ""))
    if not bound_change:
        raise GovernedFilesystemError("MUTATION_JJ_CHANGE_BINDING_REQUIRED", "mutating operations require jj_change_id")
    try:
        jj_identity = jj_adapter.identity(workspace, jj_path=jj_path)
    except jj_adapter.JjAdapterError as exc:
        raise GovernedFilesystemError(exc.code, exc.message) from exc
    if jj_identity.get("jj_change_id") != bound_change:
        raise GovernedFilesystemError(
            "MUTATION_JJ_CHANGE_MISMATCH",
            f"workspace change {jj_identity.get('jj_change_id')} differs from binding {bound_change}",
        )
    parent_commits = [str(item).strip() for item in jj_identity.get("parent_commit_ids", []) if str(item).strip()]
    if len(parent_commits) != 1:
        raise GovernedFilesystemError(
            "MUTATION_JJ_PARENT_BINDING_INVALID",
            "writable governed workspaces require exactly one immutable parent commit",
            details={"parent_commit_ids": parent_commits},
        )
    baseline_commit = parent_commits[0]
    try:
        git_repository = _git_backing_root(workspace, jj_path=jj_path)
        before = git_adapter.freeze_candidate(
            workspace,
            candidate_id=request["candidate_ref"],
            jj_change_id=bound_change,
            git_repository_root=git_repository,
            baseline_commit=baseline_commit,
        )
        entries = git_adapter.status_entries(
            workspace,
            git_repository_root=git_repository,
            baseline_commit=baseline_commit,
        )
    except git_adapter.GitAdapterError as exc:
        raise GovernedFilesystemError(exc.code, exc.message) from exc
    out_of_scope = []
    for entry in entries:
        path = Path(entry["path"])
        if not any(_is_within(Path(prefix), path) for prefix in scope_prefixes):
            out_of_scope.append(entry["path"])
    if out_of_scope:
        raise GovernedFilesystemError(
            "MUTATION_PREEXISTING_SCOPE_DRIFT",
            "workspace already contains changes outside the bound path scope",
            details={"out_of_scope_paths": sorted(set(out_of_scope))},
        )
    return before, jj_identity


def _reconcile(
    project_root: Path,
    workspace: Path,
    binding: Mapping[str, Any],
    before: Mapping[str, Any],
    scope_prefixes: Sequence[str],
    *,
    jj_path: str | Path | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    request = binding["request"]
    try:
        after_jj = jj_adapter.identity(workspace, jj_path=jj_path)
    except jj_adapter.JjAdapterError as exc:
        raise GovernedFilesystemError(exc.code, exc.message) from exc
    if after_jj.get("jj_change_id") != request.get("jj_change_id"):
        raise GovernedFilesystemError("MUTATION_JJ_CHANGE_DRIFT", "jj change identity changed during filesystem effect")
    parent_commits = [str(item).strip() for item in after_jj.get("parent_commit_ids", []) if str(item).strip()]
    baseline_commit = str(before.get("git_commit") or "").strip()
    if len(parent_commits) != 1 or not baseline_commit or parent_commits[0] != baseline_commit:
        raise GovernedFilesystemError(
            "MUTATION_JJ_PARENT_DRIFT",
            "writable workspace parent changed during the governed effect",
            details={"before_parent": baseline_commit, "after_parent_commit_ids": parent_commits},
        )
    try:
        git_repository = _git_backing_root(workspace, jj_path=jj_path)
        vcs = git_adapter.reconcile(
            workspace,
            binding_ref=binding["binding_id"],
            candidate_ref=request["candidate_ref"],
            before=before,
            jj_change_id=str(request["jj_change_id"]),
            scope_prefixes=scope_prefixes,
            git_repository_root=git_repository,
            baseline_commit=baseline_commit,
        )
    except git_adapter.GitAdapterError as exc:
        raise GovernedFilesystemError(exc.code, exc.message) from exc
    receipt, _ = append_vcs_receipt(project_root, vcs)
    return vcs, receipt


def execute(
    project_root: str | Path,
    envelope: Mapping[str, Any],
    *,
    capability_root: str | Path | None = None,
    policy_path: str | Path | None = None,
    jj_path: str | Path | None = None,
) -> dict[str, Any]:
    """Execute one exact governed filesystem request and return a typed result."""
    root = Path(project_root).resolve()
    if not isinstance(envelope, Mapping) or envelope.get("schema") != "bbk.governed-filesystem-execution.v1":
        raise GovernedFilesystemError("MUTATION_ENVELOPE_INVALID", "execution schema must be bbk.governed-filesystem-execution.v1")
    host_version = str(envelope.get("host_version", ""))
    if host_version not in QUALIFIED_HOSTS:
        raise GovernedFilesystemError(
            "MUTATION_HOST_UNQUALIFIED",
            f"host {host_version or 'unknown'} is not qualified for governed pre-effect mutation",
            smallest_next_action="Use the qualified OMP host or re-run host qualification before mutation.",
        )
    session_id = _safe_id(envelope.get("session_id"), "session_id")
    invocation_id = _safe_id(envelope.get("invocation_id"), "invocation_id")
    intent = validate_intent(envelope.get("intent", {}))
    payload = validate_payload(intent["operation"], envelope.get("payload", {}))
    computed_payload_digest = payload_digest(payload)
    if computed_payload_digest != intent["content_or_patch_digest"]:
        raise GovernedFilesystemError(
            "MUTATION_PAYLOAD_DIGEST_MISMATCH",
            "content_or_patch_digest does not match the supplied operation payload",
            details={"declared": intent["content_or_patch_digest"], "computed": computed_payload_digest},
        )

    binding = _resolve_binding_exact(
        root,
        binding_ref=intent["binding_ref"],
        session_id=session_id,
        invocation_id=invocation_id,
    )
    request = binding["request"]
    capability = _load_capability(
        str(request["role"]),
        str(binding.get("capability_ref", "")),
        Path(capability_root).resolve() if capability_root else None,
    )
    workspace = _canonical_workspace(request)
    target, relative_path = _canonical_target(workspace, intent["path"])
    physical_prefixes, relative_prefixes = _scope_prefixes(workspace, request["scope"])
    within_scope = any(_is_within(prefix, target) for prefix in physical_prefixes)
    tool_name = TOOL_FOR_OPERATION[intent["operation"]]
    tool_allowed = tool_name in capability.get("allowed_tools", [])
    class_allowed = (
        intent["operation"] == "READ"
        or (
            intent["mutation_class"] in capability.get("allowed_mutation_classes", [])
            and intent["mutation_class"] in request["scope"].get("mutation_classes", [])
        )
    )
    capability_allowed = bool(tool_allowed and class_allowed)
    sealed_marker = _sealed_marker(workspace, target, relative_path) if intent["operation"] in MUTATING_OPERATIONS else None

    policy = load_policy(policy_path or POLICY_PATH)
    gate_request = _gate_request(
        policy=policy,
        binding=binding,
        intent=intent,
        session_id=session_id,
        relative_path=relative_path,
        within_scope=within_scope,
        sealed_subject=sealed_marker is not None,
        capability_allowed=capability_allowed,
    )
    gate_decision = evaluate(policy, gate_request)
    append_gate_receipt(root, gate_request, gate_decision, invocation_id=invocation_id)

    request_identity = {
        "schema": "bbk.filesystem-mutation-request-identity.v1",
        "binding_ref": binding["binding_id"],
        "session_id": session_id,
        "invocation_id": invocation_id,
        "intent": intent,
        "payload_digest": computed_payload_digest,
        "host_version": host_version,
    }
    request_digest = f"sha256:{canonical_digest(request_identity)}"

    prior = _find_idempotent_receipt(root, intent["idempotency_key"])
    if prior:
        content = prior["content"]
        if content.get("request_digest") != request_digest:
            raise GovernedFilesystemError(
                "MUTATION_IDEMPOTENCY_COLLISION",
                "idempotency key was already used for a different request",
                details={"prior_receipt_ref": prior.get("receipt_id")},
            )
        exists_now, bytes_now, digest_now = _file_state(target)
        expected_after = content.get("result", {}).get("after_digest")
        if expected_after and digest_now != expected_after:
            raise GovernedFilesystemError(
                "MUTATION_IDEMPOTENCY_STATE_DRIFT",
                "target changed after the prior idempotent result",
                details={"prior_after_digest": expected_after, "current_digest": digest_now},
            )
        if not expected_after and exists_now and intent["operation"] == "DELETE":
            raise GovernedFilesystemError("MUTATION_IDEMPOTENCY_STATE_DRIFT", "deleted target exists after prior result")
        result_value = {**content["result"], "receipt_ref": prior["receipt_id"]}
        return {
            "status": "PASS" if result_value["effect_status"] in {"APPLIED", "NO_CHANGE"} else "BLOCK",
            "result": result_value,
            "idempotent_reuse": True,
            **(_read_output(bytes_now) if intent["operation"] == "READ" else {}),
            **({"reason_code": content.get("reason_code"), "message": content.get("message")} if content.get("reason_code") else {}),
        }

    exists_before, bytes_before, before_digest = _file_state(target)
    precondition_ok, precondition_message = _check_precondition(intent["expected_precondition"], exists_before, before_digest)

    if gate_decision["decision"] != "ALLOW":
        reason_code = gate_decision["reason_codes"][0] if gate_decision["reason_codes"] else "MUTATION_GATE_BLOCKED"
        message = (
            f"Gate Kernel blocked {intent['operation']} for {relative_path}."
            + (f" Sealed marker: {sealed_marker}" if sealed_marker else "")
        )
        result_value = _result_receipt(
            root,
            binding=binding,
            intent=intent,
            request_digest=request_digest,
            session_id=session_id,
            invocation_id=invocation_id,
            gate_decision_ref=gate_decision["receipt_ref"],
            effect_status="BLOCKED",
            observed_path=relative_path,
            vcs_reconciliation_ref="vcs:none:gate-blocked",
            before_digest=before_digest,
            after_digest=before_digest,
            changed_paths=[],
            reason_code=reason_code,
            message=message,
        )
        return {
            "status": "BLOCK",
            "reason_code": reason_code,
            "message": message,
            "smallest_next_action": gate_decision["smallest_next_action"],
            "result": result_value,
            "idempotent_reuse": False,
        }

    if not precondition_ok:
        result_value = _result_receipt(
            root,
            binding=binding,
            intent=intent,
            request_digest=request_digest,
            session_id=session_id,
            invocation_id=invocation_id,
            gate_decision_ref=gate_decision["receipt_ref"],
            effect_status="BLOCKED",
            observed_path=relative_path,
            vcs_reconciliation_ref="vcs:none:precondition-blocked",
            before_digest=before_digest,
            after_digest=before_digest,
            changed_paths=[],
            reason_code="MUTATION_PRECONDITION_FAILED",
            message=precondition_message,
        )
        return {
            "status": "BLOCK",
            "reason_code": "MUTATION_PRECONDITION_FAILED",
            "message": precondition_message,
            "smallest_next_action": "Refresh the target digest/state and issue a new idempotency key.",
            "result": result_value,
            "idempotent_reuse": False,
        }

    if intent["operation"] == "READ":
        if not exists_before:
            result_value = _result_receipt(
                root,
                binding=binding,
                intent=intent,
                request_digest=request_digest,
                session_id=session_id,
                invocation_id=invocation_id,
                gate_decision_ref=gate_decision["receipt_ref"],
                effect_status="BLOCKED",
                observed_path=relative_path,
                vcs_reconciliation_ref="vcs:none:read-missing",
                before_digest=None,
                after_digest=None,
                changed_paths=[],
                reason_code="MUTATION_READ_TARGET_MISSING",
                message="read target does not exist",
            )
            return {
                "status": "BLOCK",
                "reason_code": "MUTATION_READ_TARGET_MISSING",
                "message": "read target does not exist",
                "result": result_value,
                "idempotent_reuse": False,
            }
        result_value = _result_receipt(
            root,
            binding=binding,
            intent=intent,
            request_digest=request_digest,
            session_id=session_id,
            invocation_id=invocation_id,
            gate_decision_ref=gate_decision["receipt_ref"],
            effect_status="NO_CHANGE",
            observed_path=relative_path,
            vcs_reconciliation_ref="vcs:none:read-only",
            before_digest=before_digest,
            after_digest=before_digest,
            changed_paths=[],
        )
        return {
            "status": "PASS",
            "result": result_value,
            "idempotent_reuse": False,
            **_read_output(bytes_before),
        }

    before_vcs, _ = _vcs_context(
        workspace,
        binding,
        relative_prefixes,
        jj_path=jj_path or os.environ.get("BBK_JJ"),
    )
    effect_status = "APPLIED"
    try:
        if intent["operation"] == "WRITE":
            after_bytes_expected = _write_payload_bytes(payload)
            if bytes_before == after_bytes_expected:
                effect_status = "NO_CHANGE"
            else:
                previous_mode = stat.S_IMODE(os.lstat(target).st_mode) if exists_before else None
                _assert_no_symlink_ancestry(workspace, target)
                _atomic_write(target, after_bytes_expected, previous_mode)
        elif intent["operation"] == "EDIT":
            if not exists_before or bytes_before is None:
                raise GovernedFilesystemError("MUTATION_EDIT_TARGET_MISSING", "EDIT target must exist")
            try:
                text = bytes_before.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise GovernedFilesystemError("MUTATION_EDIT_NOT_UTF8", "EDIT supports UTF-8 text files only") from exc
            count = text.count(payload["old_text"])
            if count == 0:
                raise GovernedFilesystemError("MUTATION_EDIT_MATCH_MISSING", "old_text does not occur in target")
            if count > 1 and not payload["replace_all"]:
                raise GovernedFilesystemError(
                    "MUTATION_EDIT_MATCH_AMBIGUOUS",
                    f"old_text occurs {count} times; set replace_all only when all replacements are intended",
                )
            replacement_count = -1 if payload["replace_all"] else 1
            after_bytes_expected = text.replace(payload["old_text"], payload["new_text"], replacement_count).encode("utf-8")
            if after_bytes_expected == bytes_before:
                effect_status = "NO_CHANGE"
            else:
                _assert_no_symlink_ancestry(workspace, target)
                _atomic_write(target, after_bytes_expected, stat.S_IMODE(os.lstat(target).st_mode))
        else:
            after_bytes_expected = None
            if not exists_before:
                effect_status = "NO_CHANGE"
            else:
                _assert_no_symlink_ancestry(workspace, target)
                target.unlink()
    except GovernedFilesystemError:
        raise
    except OSError as exc:
        raise GovernedFilesystemError("MUTATION_EFFECT_FAILED", f"filesystem effect failed: {exc}") from exc

    exists_after, bytes_after, after_digest = _file_state(target)
    if intent["operation"] in {"WRITE", "EDIT"} and (not exists_after or bytes_after != after_bytes_expected):
        effect_status = "FAILED"
    if intent["operation"] == "DELETE" and exists_after:
        effect_status = "FAILED"

    vcs, vcs_receipt = _reconcile(
        root,
        workspace,
        binding,
        before_vcs,
        relative_prefixes,
        jj_path=jj_path or os.environ.get("BBK_JJ"),
    )
    reason_code = ""
    message = ""
    if vcs.get("scope_conformance") != "PASS":
        effect_status = "FAILED"
        reason_code = "MUTATION_VCS_SCOPE_RECONCILIATION_FAILED"
        message = "VCS observed paths outside the bound scope after effect"
    elif effect_status == "FAILED":
        reason_code = "MUTATION_POSTCONDITION_FAILED"
        message = "target state does not match the requested postcondition"

    result_value = _result_receipt(
        root,
        binding=binding,
        intent=intent,
        request_digest=request_digest,
        session_id=session_id,
        invocation_id=invocation_id,
        gate_decision_ref=gate_decision["receipt_ref"],
        effect_status=effect_status,
        observed_path=relative_path,
        vcs_reconciliation_ref=vcs_receipt["receipt_id"],
        before_digest=before_digest,
        after_digest=after_digest,
        changed_paths=vcs.get("changed_paths", []),
        reason_code=reason_code,
        message=message,
    )
    return {
        "status": "PASS" if effect_status in {"APPLIED", "NO_CHANGE"} else "ERROR",
        "result": result_value,
        "idempotent_reuse": False,
        **({"reason_code": reason_code, "message": message} if reason_code else {}),
    }


def _load_envelope(value: str) -> dict[str, Any]:
    try:
        if value == "-":
            parsed = json.load(__import__("sys").stdin)
        else:
            path = Path(value)
            parsed = json.loads(path.read_text(encoding="utf-8") if path.is_file() else value)
    except (OSError, json.JSONDecodeError) as exc:
        raise GovernedFilesystemError("MUTATION_ENVELOPE_INVALID", f"cannot load request: {exc}") from exc
    if not isinstance(parsed, dict):
        raise GovernedFilesystemError("MUTATION_ENVELOPE_INVALID", "request must be a JSON object")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="campaign project root containing canonical governance state")
    parser.add_argument("--capability-root")
    parser.add_argument("--policy")
    parser.add_argument("--jj-path")
    sub = parser.add_subparsers(dest="command", required=True)
    execute_parser = sub.add_parser("execute")
    execute_parser.add_argument("--request", required=True, help="JSON object, JSON file, or - for stdin")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        value = execute(
            args.root,
            _load_envelope(args.request),
            capability_root=args.capability_root,
            policy_path=args.policy,
            jj_path=args.jj_path,
        )
        print(json.dumps(value, ensure_ascii=False, sort_keys=True))
        return 0 if value.get("status") == "PASS" else 2 if value.get("status") == "BLOCK" else 3
    except (GovernedFilesystemError, GovernanceStateError) as exc:
        print(json.dumps({
            "status": "BLOCK",
            "reason_code": getattr(exc, "code", "GOVERNED_FILESYSTEM_ERROR"),
            "message": getattr(exc, "message", str(exc)),
            "smallest_next_action": getattr(exc, "smallest_next_action", "Inspect the typed failure and retry safely."),
            "details": getattr(exc, "details", {}),
        }, ensure_ascii=False, sort_keys=True))
        return 2


__all__ = [
    "GovernedFilesystemError",
    "execute",
    "payload_digest",
    "validate_intent",
    "validate_payload",
]


if __name__ == "__main__":
    raise SystemExit(main())
