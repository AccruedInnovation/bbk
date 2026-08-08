#!/usr/bin/env python3
"""Return binding-aware governed execution status without mutating projections.

The query is intentionally read-only.  It resolves the exact active OMP
session/invocation binding, verifies that the binding names the current
compiled role-capability manifest, and then summarizes canonical bindings and
receipts in memory.  Process CWD and generated projections are never treated
as authority.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from gate_kernel import canonical_digest
    from governed_state import all_bindings, all_receipts, resolve_binding
    from omp_binding_registry import OmpBindingError, enforcement_status, resolve_binding_reference
except ImportError:  # pragma: no cover - installed-package import fallback
    from .gate_kernel import canonical_digest
    from .governed_state import all_bindings, all_receipts, resolve_binding
    from .omp_binding_registry import OmpBindingError, enforcement_status, resolve_binding_reference

ROOT = Path(os.environ.get("BBK_PACKAGE_ROOT", Path(__file__).resolve().parents[1])).resolve()
CAPABILITY_ROOT = ROOT / "spec" / "role-capabilities"
REQUEST_FIELDS = frozenset({"schema", "host_version", "session_id", "invocation_id", "binding_ref"})


class GovernanceStatusError(RuntimeError):
    """The status query could not be correlated to current governed authority."""

    def __init__(self, code: str, message: str, *, smallest_next_action: str = ""):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.smallest_next_action = smallest_next_action or "Use the current active binding for this OMP session and retry."


def _text(value: Any, field: str, *, required: bool = True) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str) or (required and not value.strip()):
        qualifier = "a non-empty string" if required else "a string"
        raise GovernanceStatusError("GOVERNANCE_STATUS_REQUEST_INVALID", f"{field} must be {qualifier}")
    return value.strip()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GovernanceStatusError("GOVERNANCE_STATUS_CAPABILITY_INVALID", f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise GovernanceStatusError("GOVERNANCE_STATUS_CAPABILITY_INVALID", f"{path} must contain an object")
    return value


def _capability(role: str, capability_root: str | Path | None = None) -> tuple[dict[str, Any], str, set[str]]:
    root = Path(os.environ.get("BBK_ROLE_CAPABILITY_ROOT") or capability_root or CAPABILITY_ROOT).resolve()
    path = root / f"{role}.json"
    if not path.is_file() or path.is_symlink():
        raise GovernanceStatusError("GOVERNANCE_STATUS_CAPABILITY_NOT_FOUND", f"compiled capability is missing for {role}")
    value = _read_json(path)
    if value.get("schema") != "bbk.role-capability.v1" or value.get("role") != role:
        raise GovernanceStatusError("GOVERNANCE_STATUS_CAPABILITY_INVALID", f"{path} is not the capability for {role}")
    manifest_digest = f"sha256:{canonical_digest({key: item for key, item in value.items() if key != 'manifest_digest'})}"
    if value.get("manifest_digest") != manifest_digest:
        raise GovernanceStatusError("GOVERNANCE_STATUS_CAPABILITY_DIGEST_MISMATCH", f"capability manifest is stale for {role}")
    policy_version = str(value.get("policy_version", ""))
    canonical_ref = f"role:{role}@{policy_version}#{manifest_digest}"
    accepted_refs = {manifest_digest, f"role:{role}@{policy_version}", canonical_ref}
    return value, canonical_ref, accepted_refs


def query_status(
    project_root: str | Path,
    request: Mapping[str, Any],
    *,
    capability_root: str | Path | None = None,
) -> dict[str, Any]:
    """Resolve one current binding and summarize canonical governance state."""
    root = Path(project_root).resolve()
    if not root.is_dir():
        raise GovernanceStatusError("GOVERNANCE_STATUS_PROJECT_ROOT_INVALID", f"project root does not exist: {root}")
    if not isinstance(request, Mapping) or request.get("schema") != "bbk.governance-status-query.v1":
        raise GovernanceStatusError("GOVERNANCE_STATUS_SCHEMA_INVALID", "request schema must be bbk.governance-status-query.v1")
    unknown = sorted(set(request) - REQUEST_FIELDS)
    if unknown:
        raise GovernanceStatusError("GOVERNANCE_STATUS_SCHEMA_INVALID", f"unsupported fields: {', '.join(unknown)}")

    host_version = _text(request.get("host_version"), "host_version")
    session_id = _text(request.get("session_id"), "session_id")
    invocation_id = _text(request.get("invocation_id"), "invocation_id", required=False)
    binding_ref = _text(request.get("binding_ref"), "binding_ref", required=False)

    if binding_ref:
        binding = resolve_binding_reference(root, binding_ref)
    else:
        binding = resolve_binding(root, session_id=session_id)
    if binding is None:
        raise GovernanceStatusError(
            "GOVERNANCE_STATUS_BINDING_NOT_ACTIVE",
            "no current binding matches the supplied session/binding identity",
        )
    bound = binding.get("request", {})
    mismatches: list[str] = []
    if bound.get("session_id") != session_id:
        mismatches.append("session_id")
    if invocation_id and bound.get("invocation_id") != invocation_id:
        mismatches.append("invocation_id")
    if mismatches:
        raise GovernanceStatusError(
            "GOVERNANCE_STATUS_CORRELATION_MISMATCH",
            f"active binding differs from the host identity: {', '.join(mismatches)}",
        )

    role = str(bound.get("role", ""))
    capability, capability_ref, accepted_refs = _capability(role, capability_root)
    if str(binding.get("capability_ref", "")) not in accepted_refs:
        raise GovernanceStatusError(
            "GOVERNANCE_STATUS_CAPABILITY_BINDING_MISMATCH",
            f"binding does not identify the current capability manifest for {role}",
        )
    if "bbk_governance_status" not in capability.get("allowed_tools", []):
        raise GovernanceStatusError("GOVERNANCE_STATUS_ROLE_DENIED", f"{role} cannot use bbk_governance_status")

    bindings = all_bindings(root)
    receipts = all_receipts(root)
    superseded = {
        str(item.get("content", {}).get("predecessor_binding_id", ""))
        for item in receipts
        if item.get("receipt_kind") == "BINDING_SUPERSESSION"
    }
    receipt_kinds: dict[str, int] = {}
    for receipt in receipts:
        kind = str(receipt.get("receipt_kind", "UNKNOWN"))
        receipt_kinds[kind] = receipt_kinds.get(kind, 0) + 1

    binding_summary = {
        "binding_ref": binding.get("binding_id"),
        "immutable_digest": binding.get("immutable_digest"),
        "capability_ref": capability_ref,
        "session_id": bound.get("session_id"),
        "invocation_id": bound.get("invocation_id"),
        "role": role,
        "work_unit_id": bound.get("work_unit_id"),
        "attempt_id": bound.get("attempt_id"),
        "candidate_ref": bound.get("candidate_ref"),
        "workspace_ref": bound.get("workspace_ref"),
        "authority_ref": bound.get("authority_ref"),
        "scope": bound.get("scope"),
        "return_contract": bound.get("return_contract"),
    }
    journal = {
        "binding_count": len(bindings),
        "active_binding_count": sum(1 for item in bindings if item.get("binding_id") not in superseded),
        "superseded_binding_count": len(superseded),
        "receipt_count": len(receipts),
        "receipt_kinds": dict(sorted(receipt_kinds.items())),
        "canonical_digest": f"sha256:{canonical_digest({'bindings': bindings, 'receipts': receipts})}",
    }
    return {
        "schema": "bbk.governance-status-query-result.v1",
        "status": "PASS",
        "authority": "CANONICAL_BINDINGS_AND_RECEIPTS",
        "enforcement": enforcement_status(host_version),
        "binding": binding_summary,
        "journal": journal,
    }


def _load_json_argument(value: str) -> dict[str, Any]:
    raw = sys.stdin.read() if value == "-" else (Path(value).read_text(encoding="utf-8") if Path(value).is_file() else value)
    try:
        parsed = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise GovernanceStatusError("GOVERNANCE_STATUS_JSON_INVALID", f"cannot load query JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise GovernanceStatusError("GOVERNANCE_STATUS_JSON_INVALID", "query JSON must be an object")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    status = sub.add_parser("status")
    status.add_argument("--request", required=True, help="JSON object, file path, or - for stdin")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = query_status(args.root, _load_json_argument(args.request))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (GovernanceStatusError, OmpBindingError) as exc:
        print(json.dumps({
            "schema": "bbk.governance-status-query-error.v1",
            "status": "BLOCK",
            "reason_code": getattr(exc, "code", "GOVERNANCE_STATUS_FAILED"),
            "message": getattr(exc, "message", str(exc)),
            "smallest_next_action": getattr(exc, "smallest_next_action", "Use the current active binding and retry."),
        }, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
