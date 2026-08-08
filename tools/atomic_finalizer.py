#!/usr/bin/env python3
"""Atomic canonical JSON finalization with sidecar identity receipts."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
FINALIZER_ID = "bbk.atomic-json-finalizer"
FINALIZER_VERSION = "1"
CANONICALIZATION_PROFILE = "bbk-json-utf8-lf-v1"


class FinalizationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _utc(value: str | None = None) -> str:
    if value:
        try:
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise FinalizationError("BBK-FIN-001", f"invalid generated-at timestamp: {value}") from exc
        if parsed.tzinfo is None:
            raise FinalizationError("BBK-FIN-001", "generated-at timestamp must include a timezone")
        return parsed.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_regular_file(path: Path, *, code: str) -> None:
    try:
        info = path.lstat()
    except OSError as exc:
        raise FinalizationError(code, f"cannot inspect {path}: {exc}") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise FinalizationError(code, f"unsafe non-regular file: {path}")


def _load_draft(path: Path) -> dict[str, Any]:
    _safe_regular_file(path, code="BBK-FIN-001")
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FinalizationError("BBK-FIN-001", f"invalid JSON draft {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise FinalizationError("BBK-FIN-001", "finalization draft must be a JSON object")
    return value


def canonical_json(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _schema_registry(schema_root: Path):
    try:
        from jsonschema import Draft202012Validator
        from referencing import Registry, Resource
    except ImportError as exc:
        raise FinalizationError("BBK-FIN-002", "jsonschema/referencing tooling is unavailable") from exc
    schemas: list[dict[str, Any]] = []
    resources = []
    seen: dict[str, Path] = {}
    for path in sorted(schema_root.rglob("*.json"), key=lambda item: item.as_posix()):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FinalizationError("BBK-FIN-002", f"invalid schema {path}: {exc}") from exc
        if not isinstance(value, dict):
            continue
        schema_id = value.get("$id")
        if isinstance(schema_id, str) and schema_id:
            prior = seen.get(schema_id)
            if prior is not None:
                raise FinalizationError("SCHEMA_REGISTRY_DUPLICATE_ID", f"duplicate $id {schema_id}: {prior} and {path}")
            seen[schema_id] = path
            resources.append((schema_id, Resource.from_contents(value)))
        schemas.append(value)
    return Draft202012Validator, Registry().with_resources(resources), seen


def validate_schema(value: Mapping[str, Any], schema: str | Path, *, root: Path = ROOT) -> str:
    schema_root = root / "spec" / "schemas"
    Validator, registry, ids = _schema_registry(schema_root)
    raw = str(schema)
    target_path: Path | None = None
    if raw in ids:
        target_path = ids[raw]
    else:
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidates = [root / candidate, schema_root / candidate, *sorted(schema_root.rglob(candidate.name))]
        else:
            candidates = [candidate]
        matches = [item.resolve() for item in candidates if item.is_file()]
        unique = []
        for item in matches:
            if item not in unique:
                unique.append(item)
        if len(unique) != 1:
            raise FinalizationError("BBK-FIN-002", f"schema must resolve exactly once: {raw}; matches={unique}")
        target_path = unique[0]
    try:
        schema_value = json.loads(target_path.read_text(encoding="utf-8"))
        errors = sorted(Validator(schema_value, registry=registry).iter_errors(dict(value)), key=lambda e: list(e.path))
    except Exception as exc:
        if isinstance(exc, FinalizationError):
            raise
        raise FinalizationError("BBK-FIN-002", f"schema validation process failed: {exc}") from exc
    if errors:
        details = "; ".join(f"/{'/'.join(map(str, error.path))}: {error.message}" for error in errors[:10])
        raise FinalizationError("BBK-FIN-002", details)
    return str(schema_value.get("$id") or target_path.as_posix())


def reference_identities(references: Sequence[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for raw in references:
        path = raw.resolve()
        _safe_regular_file(path, code="BBK-FIN-003")
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise FinalizationError("BBK-FIN-003", f"cannot read referenced artifact {path}: {exc}") from exc
        records.append({"ref": raw.as_posix(), "byte_count": len(data), "sha256": _sha(data)})
    return records


def _stage_file(path: Path, data: bytes) -> Path:
    """Write and fsync one sibling temporary file without publishing it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        return temp
    except OSError as exc:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        raise FinalizationError("BBK-FIN-005", f"cannot stage atomic replacement for {path}: {exc}") from exc


def _replace_file(source: Path, target: Path) -> None:
    """Indirection used by the fault-injection regression tests."""
    os.replace(source, target)


def _snapshot_existing(path: Path) -> tuple[bool, bytes | None, int | None]:
    if not path.exists():
        return False, None, None
    if path.is_symlink():
        raise FinalizationError("BBK-FIN-005", f"refusing to replace symlink: {path}")
    _safe_regular_file(path, code="BBK-FIN-005")
    try:
        info = path.stat()
        return True, path.read_bytes(), stat.S_IMODE(info.st_mode)
    except OSError as exc:
        raise FinalizationError("BBK-FIN-005", f"cannot snapshot prior output {path}: {exc}") from exc


def _restore_snapshot(path: Path, snapshot: tuple[bool, bytes | None, int | None]) -> None:
    existed, data, mode = snapshot
    if not existed:
        path.unlink(missing_ok=True)
        return
    assert data is not None
    staged = _stage_file(path, data)
    try:
        os.replace(staged, path)
        if mode is not None:
            os.chmod(path, mode)
    finally:
        staged.unlink(missing_ok=True)


def _publish_pair(output: Path, output_data: bytes, receipt_path: Path, receipt_data: bytes, *, replace: bool) -> None:
    """Publish output and receipt as one recoverable two-file transaction.

    Both byte streams are staged before either path changes.  If the second
    replace fails, the exact prior output/receipt pair is restored.  Thus a
    caller observes either the prior current pair or the complete new pair,
    never a newly published output without its current identity receipt.
    """
    if (output.exists() or receipt_path.exists()) and not replace:
        existing = output if output.exists() else receipt_path
        raise FinalizationError("BBK-FIN-006", f"output exists: {existing}")
    output_snapshot = _snapshot_existing(output)
    receipt_snapshot = _snapshot_existing(receipt_path)
    output_temp = _stage_file(output, output_data)
    receipt_temp = _stage_file(receipt_path, receipt_data)
    output_published = False
    try:
        _replace_file(output_temp, output)
        output_published = True
        _replace_file(receipt_temp, receipt_path)
    except OSError as exc:
        restore_errors: list[str] = []
        if output_published:
            try:
                _restore_snapshot(output, output_snapshot)
            except OSError as restore_exc:
                restore_errors.append(f"output restore failed: {restore_exc}")
        try:
            _restore_snapshot(receipt_path, receipt_snapshot)
        except OSError as restore_exc:
            restore_errors.append(f"receipt restore failed: {restore_exc}")
        detail = f"atomic pair publication failed for {output}: {exc}"
        if restore_errors:
            detail += "; " + "; ".join(restore_errors)
        raise FinalizationError("BBK-FIN-007" if output_published else "BBK-FIN-005", detail) from exc
    finally:
        output_temp.unlink(missing_ok=True)
        receipt_temp.unlink(missing_ok=True)


def _atomic_write(path: Path, data: bytes, *, replace: bool) -> None:
    """Single-file atomic writer retained for internal compatibility."""
    if path.exists() and not replace:
        raise FinalizationError("BBK-FIN-006", f"output exists: {path}")
    _snapshot_existing(path)
    temp = _stage_file(path, data)
    try:
        _replace_file(temp, path)
    except OSError as exc:
        raise FinalizationError("BBK-FIN-005", f"atomic replace failed for {path}: {exc}") from exc
    finally:
        temp.unlink(missing_ok=True)

def finalize_json(
    draft: Path,
    output: Path,
    *,
    subject_kind: str,
    schema: str | Path | None = None,
    references: Sequence[Path] = (),
    generated_at: str | None = None,
    replace: bool = False,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Finalize JSON and emit ``<output>.identity.json`` atomically.

    The finalized object does not contain its own current byte identity.  That
    identity is published only in the sidecar after the final bytes exist.
    """
    value = _load_draft(draft.resolve())
    forbidden = {"raw_byte_digest", "current_raw_digest", "self_sha256", "byte_count", "sha256"}
    # Only reject common self-identity fields at the object root.  Nested
    # artifact references may legitimately contain byte identities.
    for key in sorted(forbidden & set(value)):
        raise FinalizationError("BBK-FIN-001", f"draft contains prohibited self-identity field {key}")
    schema_id = validate_schema(value, schema, root=root) if schema else None
    ref_records = reference_identities(references)
    data = canonical_json(value)
    output = output.resolve()
    receipt_path = output.with_name(output.name + ".identity.json")
    identity = {
        "schema": "bbk.identity-receipt.v1",
        "subject_ref": output.as_posix(),
        "subject_kind": subject_kind,
        "byte_count": len(data),
        "sha256": _sha(data),
        "canonicalization_profile": CANONICALIZATION_PROFILE,
        "schema_id": schema_id,
        "schema_validation": "PASS" if schema else "NOT_APPLICABLE",
        "referenced_artifact_identities": ref_records,
        "finalizer": {
            "id": FINALIZER_ID,
            "version": FINALIZER_VERSION,
            "sha256": _sha(Path(__file__).read_bytes()),
        },
        "generated_at": _utc(generated_at),
        "invalidation_keys": [
            f"subject:{_sha(data)}",
            f"finalizer:{_sha(Path(__file__).read_bytes())}",
            *[f"reference:{item['ref']}:{item['sha256']}" for item in ref_records],
        ],
    }
    _publish_pair(output, data, receipt_path, canonical_json(identity), replace=replace)
    return {
        "schema": "bbk.finalization-result.v1",
        "status": "PASS",
        "output": output.as_posix(),
        "identity_receipt": receipt_path.as_posix(),
        "subject_kind": subject_kind,
        "byte_count": len(data),
        "sha256": identity["sha256"],
        "schema_id": schema_id,
        "referenced_artifacts": ref_records,
        "atomic": True,
        "effect_class": "WORKSPACE_IMPLEMENTATION",
        "replay_legal": False,
    }
