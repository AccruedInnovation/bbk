#!/usr/bin/env python3
"""Append-only governed-execution records and regenerable projections.

Canonical records live below ``.bbk/governance/receipts`` and
``.bbk/governance/bindings``.  Everything below ``projections`` is derived and
may be deleted and rebuilt.  Callers never mutate an accepted record in place.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from gate_kernel import canonical_digest, canonical_json_bytes
except ImportError:  # pragma: no cover - package import fallback
    from .gate_kernel import canonical_digest, canonical_json_bytes

ROOT = Path(__file__).resolve().parents[1]
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@+/-]*$")


class GovernanceStateError(RuntimeError):
    """A governed record cannot be accepted without violating an invariant."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def state_root(project_root: str | Path) -> Path:
    return Path(project_root).resolve() / ".bbk" / "governance"


def _safe_component(value: str, label: str) -> str:
    if not isinstance(value, str) or not value or not ID_RE.fullmatch(value):
        raise GovernanceStateError("GOVERNANCE_ID_INVALID", f"{label} is not a safe identifier")
    return value.replace("/", "__").replace(":", "__")


def _ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or not path.is_dir():
        raise GovernanceStateError("GOVERNANCE_STATE_PATH_UNSAFE", f"{path} is not a real directory")
    return path


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GovernanceStateError("GOVERNANCE_RECORD_INVALID", f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise GovernanceStateError("GOVERNANCE_RECORD_INVALID", f"{path} is not a JSON object")
    return value


def _write_exclusive(path: Path, value: Mapping[str, Any]) -> bool:
    """Create one immutable JSON record. Return False for byte-identical retry."""
    parent = _ensure_directory(path.parent)
    if parent.resolve() != path.parent.resolve() or path.is_symlink():
        raise GovernanceStateError("GOVERNANCE_STATE_PATH_UNSAFE", f"unsafe record path {path}")
    payload = canonical_json_bytes(value) + b"\n"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        try:
            existing = path.read_bytes()
        except OSError as exc:
            raise GovernanceStateError("GOVERNANCE_RECORD_COLLISION", f"cannot inspect existing {path}: {exc}") from exc
        if existing == payload:
            return False
        raise GovernanceStateError(
            "GOVERNANCE_RECORD_COLLISION",
            f"immutable identity {path.name} already exists with different bytes",
        )
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            path.unlink(missing_ok=True)
        finally:
            raise
    return True


def _write_projection(path: Path, value: Mapping[str, Any] | str) -> None:
    """Atomically replace a non-authoritative generated projection."""
    _ensure_directory(path.parent)
    if path.is_symlink():
        raise GovernanceStateError("GOVERNANCE_PROJECTION_PATH_UNSAFE", f"unsafe projection path {path}")
    if isinstance(value, str):
        payload = value.encode("utf-8")
    else:
        payload = canonical_json_bytes(value) + b"\n"
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def initialize(project_root: str | Path) -> Path:
    root = state_root(project_root)
    for relative in ("receipts", "bindings", "projections", "locks"):
        _ensure_directory(root / relative)
    marker = root / "README.md"
    if not marker.exists():
        marker.write_text(
            "# BBK governed execution state\n\n"
            "`receipts/` and `bindings/` are append-only canonical records. "
            "`projections/` is generated and non-authoritative. Do not hand-edit "
            "canonical records or use projections as effect authority.\n",
            encoding="utf-8",
        )
    return root


def append_receipt(
    project_root: str | Path,
    receipt_kind: str,
    content: Mapping[str, Any],
    *,
    receipt_id: str | None = None,
    recorded_at: str | None = None,
) -> tuple[dict[str, Any], bool]:
    """Append a generic immutable receipt and return ``(record, created)``."""
    root = initialize(project_root)
    if not isinstance(content, Mapping):
        raise GovernanceStateError("GOVERNANCE_RECEIPT_INVALID", "receipt content must be an object")
    kind = _safe_component(receipt_kind, "receipt_kind")
    content_value = dict(content)
    identity = receipt_id or f"sha256:{canonical_digest({'receipt_kind': receipt_kind, 'content': content_value})}"
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", identity):
        raise GovernanceStateError("GOVERNANCE_RECEIPT_ID_INVALID", "receipt_id must be sha256:<64 lowercase hex>")
    safe_id = identity.removeprefix("sha256:")
    path = root / "receipts" / kind / f"{safe_id}.json"
    if path.exists():
        existing = _read_json(path)
        expected = {key: value for key, value in existing.items() if key != "recorded_at"}
        candidate = {
            "schema": "bbk.governance-receipt.v1",
            "receipt_id": identity,
            "receipt_kind": receipt_kind,
            "content": content_value,
        }
        if expected != candidate:
            raise GovernanceStateError(
                "GOVERNANCE_RECEIPT_COLLISION",
                f"receipt {identity} exists with different immutable content",
            )
        return existing, False
    record = {
        "schema": "bbk.governance-receipt.v1",
        "receipt_id": identity,
        "receipt_kind": receipt_kind,
        "recorded_at": recorded_at or utc_now(),
        "content": content_value,
    }
    return record, _write_exclusive(path, record)


def append_gate_receipt(
    project_root: str | Path,
    request: Mapping[str, Any],
    decision: Mapping[str, Any],
    *,
    invocation_id: str,
    recorded_at: str | None = None,
) -> tuple[dict[str, Any], bool]:
    """Persist an IF-001 decision under its deterministic Gate Kernel identity."""
    identity = str(decision.get("receipt_ref", ""))
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", identity):
        raise GovernanceStateError("GATE_RECEIPT_ID_INVALID", "decision.receipt_ref is missing or invalid")
    subject = {
        "actor_id": request.get("actor", {}).get("actor_id", "unknown"),
        "invocation_id": invocation_id,
        "work_unit_id": request.get("work_unit_id", "unknown"),
        "candidate_ref": request.get("candidate_ref", "unknown"),
        "authority_ref": request.get("authority", {}).get("authority_ref", "unknown"),
        "policy_version": decision.get("policy_version", "unknown"),
    }
    schema_record = {
        "schema": "bbk.gate-receipt.v1",
        "receipt_id": identity,
        "receipt_kind": "GATE_DECISION",
        "recorded_at": recorded_at or utc_now(),
        "request": dict(request),
        "decision": dict(decision),
        "subject": subject,
        "implementation_version": decision.get("implementation_version", "unknown"),
    }
    root = initialize(project_root)
    path = root / "receipts" / "GATE_DECISION" / f"{identity.removeprefix('sha256:')}.json"
    if path.exists():
        existing = _read_json(path)
        stable_existing = {k: v for k, v in existing.items() if k != "recorded_at"}
        stable_candidate = {k: v for k, v in schema_record.items() if k != "recorded_at"}
        if stable_existing != stable_candidate:
            raise GovernanceStateError("GATE_RECEIPT_COLLISION", f"gate receipt {identity} has conflicting content")
        return existing, False
    return schema_record, _write_exclusive(path, schema_record)


def _validate_binding_request(request: Mapping[str, Any]) -> None:
    if request.get("schema") != "bbk.invocation-binding-create.v1":
        raise GovernanceStateError("BINDING_SCHEMA_INVALID", "binding request schema is invalid")
    required = (
        "session_id", "invocation_id", "role", "work_unit_id", "attempt_id",
        "baseline_ref", "candidate_ref", "workspace_ref", "authority_ref", "scope",
        "return_contract",
    )
    missing = [field for field in required if not request.get(field)]
    if missing:
        raise GovernanceStateError("BINDING_INCOMPLETE", f"missing required fields: {', '.join(missing)}")
    scope = request.get("scope")
    if not isinstance(scope, Mapping) or not scope.get("path_prefixes") or not scope.get("mutation_classes"):
        raise GovernanceStateError("BINDING_SCOPE_INCOMPLETE", "path_prefixes and mutation_classes are required")
    workspace = Path(str(request["workspace_ref"])).resolve()
    prefixes = [Path(str(item)).resolve() for item in scope["path_prefixes"]]
    for prefix in prefixes:
        try:
            prefix.relative_to(workspace)
        except ValueError as exc:
            raise GovernanceStateError("BINDING_SCOPE_ESCAPE", f"scope prefix {prefix} escapes workspace {workspace}") from exc


def create_binding(
    project_root: str | Path,
    request: Mapping[str, Any],
    *,
    capability_ref: str,
    created_at: str | None = None,
) -> tuple[dict[str, Any], bool]:
    """Create one immutable invocation/work-unit binding.

    Supersession is represented by a separate immutable ``BINDING_SUPERSESSION``
    receipt; the predecessor binding file is never rewritten.
    """
    _validate_binding_request(request)
    request_value = dict(request)
    digest = canonical_digest({"request": request_value, "capability_ref": capability_ref})
    binding_id = f"binding:{digest}"
    record = {
        "schema": "bbk.work-unit-binding.v1",
        "binding_id": binding_id,
        "status": "ACTIVE",
        "immutable_digest": f"sha256:{digest}",
        "created_at": created_at or utc_now(),
        "request": request_value,
        "capability_ref": capability_ref,
    }
    if request_value.get("supersedes"):
        record["supersedes"] = request_value["supersedes"]
    root = initialize(project_root)
    path = root / "bindings" / f"{digest}.json"
    if path.exists():
        existing = _read_json(path)
        stable_existing = {k: v for k, v in existing.items() if k != "created_at"}
        stable_candidate = {k: v for k, v in record.items() if k != "created_at"}
        if stable_existing != stable_candidate:
            raise GovernanceStateError("BINDING_COLLISION", f"binding identity {binding_id} has conflicting content")
        return existing, False
    created = _write_exclusive(path, record)
    predecessor = request_value.get("supersedes")
    if predecessor:
        append_receipt(
            project_root,
            "BINDING_SUPERSESSION",
            {
                "predecessor_binding_id": predecessor,
                "successor_binding_id": binding_id,
                "session_id": request_value["session_id"],
                "invocation_id": request_value["invocation_id"],
                "attempt_id": request_value["attempt_id"],
            },
        )
    rebuild_projections(project_root)
    return record, created


def all_bindings(project_root: str | Path) -> list[dict[str, Any]]:
    root = initialize(project_root)
    return [_read_json(path) for path in sorted((root / "bindings").glob("*.json"))]


def all_receipts(project_root: str | Path) -> list[dict[str, Any]]:
    root = initialize(project_root)
    return [_read_json(path) for path in sorted((root / "receipts").glob("*/*.json"))]


def resolve_binding(
    project_root: str | Path,
    *,
    binding_id: str | None = None,
    session_id: str | None = None,
    invocation_id: str | None = None,
) -> dict[str, Any] | None:
    """Resolve the current non-superseded binding by exact typed identity."""
    bindings = all_bindings(project_root)
    superseded: set[str] = set()
    for receipt in all_receipts(project_root):
        if receipt.get("receipt_kind") == "BINDING_SUPERSESSION":
            superseded.add(str(receipt.get("content", {}).get("predecessor_binding_id", "")))
    candidates = []
    for record in bindings:
        request = record.get("request", {})
        if binding_id and record.get("binding_id") != binding_id:
            continue
        if session_id and request.get("session_id") != session_id:
            continue
        if invocation_id and request.get("invocation_id") != invocation_id:
            continue
        if record.get("binding_id") in superseded:
            continue
        candidates.append(record)
    if not candidates:
        return None
    if len(candidates) > 1:
        raise GovernanceStateError("BINDING_AMBIGUOUS", "more than one current binding matches the supplied identity")
    return candidates[0]


def append_vcs_receipt(project_root: str | Path, receipt: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
    identity = str(receipt.get("receipt_id", ""))
    if not identity:
        stable = {key: value for key, value in receipt.items() if key not in {"receipt_id", "recorded_at"}}
        identity = f"sha256:{canonical_digest(stable)}"
    content = dict(receipt)
    content["receipt_id"] = identity
    content.setdefault("recorded_at", utc_now())
    return append_receipt(project_root, "VCS_MUTATION", content, receipt_id=identity)


def rebuild_projections(project_root: str | Path) -> dict[str, Any]:
    root = initialize(project_root)
    receipts = all_receipts(project_root)
    bindings = all_bindings(project_root)
    superseded_by: dict[str, str] = {}
    for receipt in receipts:
        if receipt.get("receipt_kind") == "BINDING_SUPERSESSION":
            content = receipt.get("content", {})
            predecessor = str(content.get("predecessor_binding_id", ""))
            successor = str(content.get("successor_binding_id", ""))
            if predecessor and successor:
                superseded_by[predecessor] = successor
    projected_bindings = []
    for binding in bindings:
        item = dict(binding)
        if binding["binding_id"] in superseded_by:
            item["status"] = "SUPERSEDED"
            item["superseded_by"] = superseded_by[binding["binding_id"]]
        projected_bindings.append(item)
    receipt_index = {
        "schema": "bbk.governance-receipt-index.v1",
        "authority": "NON_AUTHORITATIVE_PROJECTION",
        "generated_from": [record.get("receipt_id") for record in receipts],
        "count": len(receipts),
        "receipts": [
            {
                "receipt_id": record.get("receipt_id"),
                "receipt_kind": record.get("receipt_kind"),
                "recorded_at": record.get("recorded_at"),
            }
            for record in receipts
        ],
    }
    status = {
        "schema": "bbk.governance-status.v1",
        "authority": "NON_AUTHORITATIVE_PROJECTION",
        "canonical_roots": ["receipts", "bindings"],
        "receipt_count": len(receipts),
        "binding_count": len(bindings),
        "active_bindings": [item["binding_id"] for item in projected_bindings if item["status"] == "ACTIVE"],
        "superseded_bindings": [item["binding_id"] for item in projected_bindings if item["status"] == "SUPERSEDED"],
        "blocked_gate_receipts": [
            record.get("receipt_id")
            for record in receipts
            if record.get("receipt_kind") == "GATE_DECISION"
            and record.get("decision", {}).get("decision") in {"BLOCK", "REQUIRE_OVERRIDE"}
        ],
    }
    bindings_projection = {
        "schema": "bbk.binding-projection.v1",
        "authority": "NON_AUTHORITATIVE_PROJECTION",
        "bindings": projected_bindings,
    }
    projection_root = root / "projections"
    _write_projection(projection_root / "receipt-index.json", receipt_index)
    _write_projection(projection_root / "bindings.json", bindings_projection)
    _write_projection(projection_root / "status.json", status)
    lines = [
        "# BBK governed execution status",
        "",
        "> Generated, non-authoritative projection. Rebuild from canonical receipts and bindings.",
        "",
        f"- Receipts: {len(receipts)}",
        f"- Bindings: {len(bindings)}",
        f"- Active bindings: {len(status['active_bindings'])}",
        f"- Superseded bindings: {len(status['superseded_bindings'])}",
        f"- Blocking gate decisions: {len(status['blocked_gate_receipts'])}",
        "",
    ]
    _write_projection(projection_root / "status.md", "\n".join(lines))
    return status


def projection_digest(project_root: str | Path) -> str:
    root = state_root(project_root) / "projections"
    payload = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.glob("*"))
        if path.is_file()
    }
    return f"sha256:{canonical_digest(payload)}"


def _cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    sub.add_parser("rebuild")
    sub.add_parser("status")
    resolve = sub.add_parser("resolve-binding")
    resolve.add_argument("--binding-id")
    resolve.add_argument("--session-id")
    resolve.add_argument("--invocation-id")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _cli().parse_args(list(argv) if argv is not None else None)
    try:
        if args.command == "init":
            result: Any = {"status": "PASS", "root": str(initialize(args.root))}
        elif args.command == "rebuild":
            result = rebuild_projections(args.root)
        elif args.command == "status":
            projection = state_root(args.root) / "projections" / "status.json"
            result = _read_json(projection) if projection.exists() else rebuild_projections(args.root)
        else:
            result = resolve_binding(
                args.root,
                binding_id=args.binding_id,
                session_id=args.session_id,
                invocation_id=args.invocation_id,
            )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result is not None else 1
    except GovernanceStateError as exc:
        print(json.dumps({"status": "BLOCK", "reason_code": exc.code, "message": exc.message}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
