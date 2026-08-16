"""Atomic, repository-owned process launch records for qualification runs.

The recorder is deliberately small: callers provide an externally owned
evidence root and the effective argv/cwd/environment, while this module owns
validation, atomic persistence, and deterministic aggregation.  It does not
inspect process trees or infer state from the host.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA = "bbk.launch-record.v1"
LEDGER_SCHEMA = "bbk.launch-ledger.v1"
ROOT_ENV = "BBK_LAUNCH_RECORD_ROOT"
LEGACY_ROOT_ENV = "BBK_NATIVE_EVIDENCE_ROOT"
RECORDS_DIR = "launch-records"
LEDGER_NAME = "launch-ledger.json"
DIRECT_PYTHON = r"C:\Python313\python.exe"
_SECRET = re.compile(r"(?:pass|secret|token|key|credential|auth|cookie)", re.I)


class LaunchRecordError(RuntimeError):
    """A launch cannot be safely recorded or validated."""

    def __init__(self, message: str, *, records: Sequence[Mapping[str, Any]] = ()) -> None:
        self.records = [dict(record) for record in records]
        super().__init__(message)


def _record_details(path: Path, value: Mapping[str, Any] | None, current_pid: int) -> dict[str, Any]:
    """Return stable ownership details for every record-integrity failure."""
    record = value or {}
    return {
        "path": str(path),
        "record_id": str(record.get("record_id") or path.stem),
        "state": record.get("state", "unknown"),
        "owner_pid": record.get("owner_pid"),
        "current_pid": current_pid,
        "owner_scope": record.get("owner_scope", "unknown"),
    }


def _record_error(message: str, path: Path, value: Mapping[str, Any] | None = None) -> LaunchRecordError:
    details = _record_details(path, value, os.getpid())
    suffix = (
        f"record_id={details['record_id']} state={details['state']} "
        f"owner_pid={details['owner_pid']} current_pid={details['current_pid']} "
        f"owner_scope={details['owner_scope']}"
    )
    return LaunchRecordError(f"{message}; {suffix}", records=(details,))


def evidence_root(environment: Mapping[str, str] | None = None) -> Path | None:
    """Resolve the explicitly supplied attempt evidence root, if any."""
    source = os.environ if environment is None else environment
    primary, legacy = source.get(ROOT_ENV), source.get(LEGACY_ROOT_ENV)

    def resolve(value: str | None, name: str) -> Path | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip() or "\x00" in value:
            raise LaunchRecordError(f"invalid launch evidence root: {name}")
        try:
            resolved = Path(value).expanduser().resolve(strict=False)
            if resolved.exists() and not resolved.is_dir():
                raise LaunchRecordError(f"invalid launch evidence root: {name}")
            return resolved
        except (OSError, RuntimeError, ValueError) as exc:
            raise LaunchRecordError(f"invalid launch evidence root: {name}") from exc

    primary_path, legacy_path = resolve(primary, ROOT_ENV), resolve(legacy, LEGACY_ROOT_ENV)
    if primary_path is not None and legacy_path is not None and primary_path != legacy_path:
        raise LaunchRecordError("conflicting launch evidence roots")
    return primary_path or legacy_path


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _canonical(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _canonical(value)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def persist_error_diagnostic(
    exc: LaunchRecordError,
    *,
    report: dict[str, Any] | None = None,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any] | None:
    """Persist one append-only integrity diagnostic without masking ``exc``."""
    target = report if report is not None else {}
    current_pid = os.getpid()
    observed_at = _now()
    source = os.environ if environment is None else environment
    material_environment = {
        key: ("<redacted>" if _SECRET.search(key) else str(source[key]))
        for key in sorted(str(name) for name in source)
        if _SECRET.search(key)
        or key
        in {
            "TEMP", "TMP", "TMPDIR", "BBK_CACHE_DIR", "BBK_TEST_CACHE_DIR",
            "PYTHONPYCACHEPREFIX", ROOT_ENV, "BBK_LAUNCH_EVIDENCE_ROOT",
            "BBK_QUALIFIED_EVIDENCE_ROOT", "PYTHONDONTWRITEBYTECODE",
            "PYTHONNOUSERSITE", "PYTHONPATH", "BBK_QUALIFIED_PYTHONPATH",
        }
    }
    environment_digest = hashlib.sha256(_canonical(material_environment)).hexdigest()
    snapshots: list[dict[str, Any]] = []
    for details in exc.records:
        item = dict(details)
        path_value = item.get("path")
        snapshot: dict[str, Any] = {"path": path_value, "status": "unavailable"}
        if isinstance(path_value, str) and path_value:
            path = Path(path_value)
            try:
                raw = path.read_bytes()
                snapshot.update({"status": "captured", "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
                try:
                    snapshot["value"] = json.loads(raw.decode("utf-8"))
                except (UnicodeError, json.JSONDecodeError) as parse_error:
                    snapshot.update({"status": "malformed", "parse_error": f"{type(parse_error).__name__}: {parse_error}"})
            except OSError as read_error:
                snapshot["read_error"] = f"{type(read_error).__name__}: {read_error}"
        value = snapshot.get("value") if isinstance(snapshot.get("value"), Mapping) else {}
        item["snapshot"] = snapshot
        item["state"] = item.get("state", value.get("state", "unknown"))
        item["returncode"] = value.get("returncode")
        item["owner_pid"] = item.get("owner_pid", value.get("owner_pid"))
        item["parent_pid"] = value.get("parent_pid")
        item["current_pid"] = item.get("current_pid", current_pid)
        item["owner_scope"] = item.get("owner_scope", value.get("owner_scope", "unknown"))
        item["operation"] = item.get("operation", value.get("operation", target.get("operation", "runner-finalize")))
        item["subtree"] = item.get("subtree", value.get("subtree", target.get("subtree", "current-process")))
        item["argv"] = value.get("argv", target.get("argv", []))
        item["resolved_cwd"] = value.get("resolved_cwd", value.get("cwd", target.get("cwd")))
        item["material_env_digest"] = (
            hashlib.sha256(_canonical(value["environment"])).hexdigest()
            if isinstance(value.get("environment"), Mapping) else environment_digest
        )
        snapshots.append(item)
    diagnostic = {
        "schema": "bbk.launch-record-error.v1",
        "record_id": hashlib.sha256(f"{observed_at}:{current_pid}:{uuid.uuid4().hex}".encode("utf-8")).hexdigest(),
        "exception": {"type": type(exc).__name__, "text": str(exc)},
        "records": snapshots,
        "observation": {"timestamp": observed_at, "current_pid": current_pid, "aggregation_scope": "current-process", "aggregation_root": None},
        "operation": target.get("operation") or (snapshots[0].get("operation") if snapshots else "runner-finalize"),
        "subtree": target.get("subtree", "current-process"),
        "argv": target.get("argv") or (snapshots[0].get("argv", []) if snapshots else []),
        "resolved_cwd": target.get("cwd") or (snapshots[0].get("resolved_cwd") if snapshots else None),
        "material_environment_digest": environment_digest,
        "append_only": True,
    }
    try:
        root = evidence_root(environment)
        diagnostic["observation"]["aggregation_root"] = str(root) if root else None
        if root is not None:
            path = root / "launch-record-errors" / f"{diagnostic['record_id']}.json"
            _atomic_json(path, diagnostic)
            target["launch_ledger_error_diagnostic"] = {"path": str(path), "record_id": diagnostic["record_id"], "append_only": True}
    except (OSError, LaunchRecordError) as persist_error:
        target["launch_ledger_error_diagnostic_persistence"] = f"{type(persist_error).__name__}: {persist_error}"
    target["launch_ledger_error"] = f"{type(exc).__name__}: {exc}"
    target["launch_ledger_error_records"] = list(exc.records)
    target["launch_ledger_error_context"] = {"current_pid": current_pid, "scope": "current-process", "ordering": "all waited descendants must be terminal before finalization"}
    return diagnostic


def _resolved_cwd(cwd: str | os.PathLike[str] | None) -> str:
    selected = Path(cwd if cwd is not None else os.getcwd())
    try:
        return str(selected.resolve())
    except OSError as exc:
        raise LaunchRecordError(f"cannot resolve launch cwd: {selected}") from exc


def _material_environment(environment: Mapping[str, str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key in sorted((str(name) for name in environment)):
        value = str(environment[key])
        result[key] = "<redacted>" if _SECRET.search(key) else value
    return result


def _is_python(argv0: str) -> bool:
    normalized = argv0.replace("/", "\\").casefold()
    name = normalized.rsplit("\\", 1)[-1]
    return normalized == DIRECT_PYTHON.casefold() or name in {
        "python", "python.exe", "python3", "python3.exe", "py", "py.exe",
    } or Path(argv0).resolve() == Path(os.sys.executable).resolve()


def _validate_python(argv: Sequence[str], environment: Mapping[str, str]) -> None:
    if os.name == "nt" and argv[0].replace("/", "\\").casefold() != DIRECT_PYTHON.casefold():
        raise LaunchRecordError(f"managed Python must use {DIRECT_PYTHON} at argv[0]")
    if "-B" not in argv[1:3]:
        raise LaunchRecordError("managed Python argv must include -B before the script/module")
    if environment.get("PYTHONDONTWRITEBYTECODE") != "1":
        raise LaunchRecordError("managed Python requires PYTHONDONTWRITEBYTECODE=1")
    if environment.get("PYTHONNOUSERSITE") != "1":
        raise LaunchRecordError("managed Python requires PYTHONNOUSERSITE=1")
    qualified = environment.get("BBK_QUALIFIED_PYTHONPATH")
    pythonpath = environment.get("PYTHONPATH")
    if not qualified or pythonpath != qualified:
        raise LaunchRecordError("managed Python requires an explicit qualified PYTHONPATH")
    roots = [part for part in qualified.split(os.pathsep) if part]
    if len(roots) != 3:
        raise LaunchRecordError("managed Python requires exactly three qualified PYTHONPATH roots")
    project, tools, managed = (Path(part) for part in roots)
    if tools.name.casefold() != "tools" or tools.parent != project:
        raise LaunchRecordError("managed Python qualified PYTHONPATH must start with project and tools roots")
    if managed.name.casefold() != "site-packages":
        raise LaunchRecordError("managed Python qualified PYTHONPATH must end in managed site-packages")


def _validate_external_roots(
    environment: Mapping[str, str],
    cwd: str | None,
    *,
    require_evidence_root: bool = False,
) -> None:
    """Require the attempt-owned roots when a qualification ledger is enabled."""
    root = evidence_root(environment)
    if root is None:
        if require_evidence_root:
            raise LaunchRecordError("qualified launch requires an explicit evidence root")
        return
    if not cwd:
        raise LaunchRecordError("qualified launch requires an explicit resolved cwd")
    required = ("TEMP", "TMP", "TMPDIR", "PYTHONPYCACHEPREFIX", "BBK_TEST_CACHE_DIR")
    missing = [name for name in required if not str(environment.get(name) or "").strip()]
    if missing:
        raise LaunchRecordError("qualified launch missing attempt-owned roots: " + ", ".join(missing))


def validate_launch(argv: Sequence[str], cwd: str | os.PathLike[str] | None, environment: Mapping[str, str]) -> tuple[list[str], str, dict[str, str]]:
    """Validate and normalize one pre-spawn launch without creating a process."""
    values = [str(item) for item in argv]
    if not values:
        raise LaunchRecordError("launch argv must not be empty")
    resolved = _resolved_cwd(cwd)
    material = _material_environment(environment)
    if _is_python(values[0]):
        _validate_python(values, environment)
    return values, resolved, material


@dataclass
class LaunchHandle:
    """A validated launch whose actual process receipt is persisted on commit."""

    argv: list[str]
    cwd: str
    environment: dict[str, str]
    root: Path | None
    kind: str
    _path: Path | None = None

    def started(self, pid: int) -> None:
        if self.root is None:
            return
        base = {
            "schema": SCHEMA,
            "record_id": self.identity(pid),
            "kind": self.kind,
            "argv": self.argv,
            "cwd": self.cwd,
            "resolved_cwd": self.cwd,
            "environment": self.environment,
            "env": self.environment,
            "pid": int(pid),
            "owner_pid": os.getpid(),
            "owner_scope": "parent-process",
            "state": "running",
            "started_at": _now(),
        }
        self._path = self.root / RECORDS_DIR / f"{base['record_id']}.json"
        _atomic_json(self._path, base)

    def completed(self, *, returncode: int | None, state: str = "completed", error: str | None = None) -> None:
        if self.root is None:
            return
        if self._path is None:
            raise LaunchRecordError("cannot complete a launch before started(pid)")
        try:
            value = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise _record_error(f"launch record disappeared or became invalid: {self._path}", self._path) from exc
        value.update({"state": state, "returncode": returncode, "completed_at": _now()})
        if error:
            value["error"] = str(error)
        _atomic_json(self._path, value)

    def spawn_failed(self, error: BaseException) -> None:
        if self.root is None:
            return
        value = {
            "schema": SCHEMA,
            "record_id": self.identity(f"failed-{uuid.uuid4().hex}"),
            "kind": self.kind,
            "argv": self.argv,
            "cwd": self.cwd,
            "resolved_cwd": self.cwd,
            "environment": self.environment,
            "env": self.environment,
            "pid": None,
            "state": "spawn-failed",
            "returncode": None,
            "started_at": _now(),
            "completed_at": _now(),
            "error": f"{type(error).__name__}: {error}",
        }
        _atomic_json(self.root / RECORDS_DIR / f"{value['record_id']}.json", value)

    def identity(self, pid: int | str) -> str:
        value = {"kind": self.kind, "argv": self.argv, "cwd": self.cwd, "environment": self.environment, "pid": str(pid)}
        return hashlib.sha256(_canonical(value)).hexdigest()


def prepare(
    argv: Sequence[str],
    *,
    cwd: str | os.PathLike[str] | None = None,
    environment: Mapping[str, str] | None = None,
    kind: str = "subprocess",
    require_evidence_root: bool = False,
) -> LaunchHandle:
    """Validate one launch and return a receipt handle for the Popen call."""
    env = dict(os.environ if environment is None else environment)
    values, resolved, material = validate_launch(argv, cwd, env)
    if _is_python(values[0]):
        _validate_external_roots(env, resolved, require_evidence_root=require_evidence_root)
    root = evidence_root(env)
    if root is not None:
        (root / RECORDS_DIR).mkdir(parents=True, exist_ok=True)
    return LaunchHandle(values, resolved, material, root, str(kind))


def record_no_child(*, argv: Sequence[str], cwd: str | os.PathLike[str] | None = None, environment: Mapping[str, str] | None = None, kind: str = "in-process", status: str = "completed") -> Path | None:
    """Persist an honest no-child record for an in-process check."""
    env = dict(os.environ if environment is None else environment)
    values = [str(item) for item in argv]
    if not values:
        raise LaunchRecordError("no-child argv must not be empty")
    resolved, material = _resolved_cwd(cwd), _material_environment(env)
    root = evidence_root(env)
    if root is None:
        return None
    identity = hashlib.sha256(_canonical({"kind": kind, "argv": values, "cwd": resolved, "environment": material, "pid": None})).hexdigest()
    path = root / RECORDS_DIR / f"{identity}.json"
    _atomic_json(path, {"schema": SCHEMA, "record_id": identity, "kind": kind, "argv": values, "cwd": resolved, "resolved_cwd": resolved, "environment": material, "env": material, "pid": None, "owner_pid": os.getpid(), "owner_scope": "current-process", "state": "no-child", "status": status, "returncode": 0, "started_at": _now(), "completed_at": _now()})
    return path


def _record_files(root: Path) -> list[Path]:
    directory = root / RECORDS_DIR if root.name != RECORDS_DIR else root
    return sorted(directory.glob("*.json"))


def _is_enclosing_ancestor(value: Mapping[str, Any], current_pid: int) -> bool:
    """Identify the exact running parent-owned record that launched this child."""
    owner_pid = value.get("owner_pid")
    return (
        value.get("state") == "running"
        and
        isinstance(value.get("pid"), int)
        and not isinstance(value.get("pid"), bool)
        and value["pid"] == current_pid
        and isinstance(owner_pid, int)
        and not isinstance(owner_pid, bool)
        and owner_pid != current_pid
    )


def _is_externally_owned_pending(value: Mapping[str, Any], current_pid: int) -> bool:
    """Identify any running record owned by another process for child scope."""
    owner_pid = value.get("owner_pid")
    return (
        value.get("state") == "running"
        and isinstance(owner_pid, int)
        and not isinstance(owner_pid, bool)
        and owner_pid != current_pid
    )


def aggregate(
    root: str | os.PathLike[str],
    *,
    output: str | os.PathLike[str] | None = None,
    exclude_enclosing_ancestor: bool = False,
) -> dict[str, Any]:
    """Read, validate, deduplicate and deterministically aggregate records."""
    base = Path(root).expanduser()
    records: dict[str, dict[str, Any]] = {}
    excluded_ancestors: list[dict[str, Any]] = []
    current_pid = os.getpid()
    for path in _record_files(base):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise _record_error(f"malformed launch record: {path}", path) from exc
        required = ("schema", "record_id", "kind", "argv", "cwd", "resolved_cwd", "environment", "env", "pid", "state")
        if value.get("schema") != SCHEMA or any(key not in value for key in required) or not isinstance(value["argv"], list) or not isinstance(value["environment"], dict):
            raise _record_error(f"incomplete launch record: {path}", path, value)
        if value["cwd"] != value["resolved_cwd"] or value["environment"] != value["env"]:
            raise _record_error(f"conflicting launch fields: {path}", path, value)
        if "owner_pid" in value and (not isinstance(value["owner_pid"], int) or isinstance(value["owner_pid"], bool)):
            raise _record_error(f"invalid launch ownership: {path}", path, value)
        if "owner_scope" in value and value["owner_scope"] not in {"parent-process", "current-process"}:
            raise _record_error(f"invalid launch ownership scope: {path}", path, value)
        if exclude_enclosing_ancestor and _is_externally_owned_pending(value, current_pid):
            pending = dict(value)
            pending["aggregation"] = "excluded-externally-owned-pending"
            pending["ownership_status"] = "externally-owned-pending"
            excluded_ancestors.append(pending)
            continue
        if value["state"] not in {"completed", "timed-out", "spawn-failed", "no-child"} or "returncode" not in value:
            raise _record_error(f"incomplete launch state: {path}", path, value)
        identity = str(value["record_id"])
        previous = records.get(identity)
        if previous is not None and previous != value:
            details = [_record_details(path, previous, current_pid), _record_details(path, value, current_pid)]
            raise LaunchRecordError(
                f"conflicting launch records for identity {identity}; "
                + "; ".join(
                    f"record_id={item['record_id']} state={item['state']} owner_pid={item['owner_pid']} "
                    f"current_pid={item['current_pid']} owner_scope={item['owner_scope']}" for item in details
                ),
                records=details,
            )
        records[identity] = value
    ordered = [records[key] for key in sorted(records)]
    result: dict[str, Any] = {"schema": LEDGER_SCHEMA, "status": "PASS", "records": ordered, "record_count": len(ordered)}
    if excluded_ancestors:
        result["excluded_ancestors"] = sorted(excluded_ancestors, key=lambda item: str(item["record_id"]))
    if output is not None:
        destination = Path(output)
    else:
        destination = base / LEDGER_NAME
    _atomic_json(destination, result)
    return result


def finalize(
    environment: Mapping[str, str] | None = None,
    *,
    exclude_enclosing_ancestor: bool = False,
) -> dict[str, Any] | None:
    """Write the current attempt ledger when an explicit root is configured."""
    root = evidence_root(environment)
    return aggregate(root, exclude_enclosing_ancestor=exclude_enclosing_ancestor) if root is not None else None


record_launch = prepare
aggregate_records = aggregate

__all__ = ["LEDGER_NAME", "LEDGER_SCHEMA", "LaunchHandle", "LaunchRecordError", "aggregate", "aggregate_records", "evidence_root", "finalize", "persist_error_diagnostic", "prepare", "record_launch", "record_no_child", "validate_launch"]
