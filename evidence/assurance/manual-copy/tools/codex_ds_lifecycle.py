#!/usr/bin/env python3
"""Project-scoped, keyless DeepSeek Codex actor lifecycle.

The lifecycle is deliberately explicit: callers must provide one BBK role and
one registered DeepSeek target.  Credentials are represented only by the
``DEEPSEEK_API_KEY`` environment-variable reference; values are never read or
written.  Files are copied from the checked-in Codex projections into an
isolated ``CODEX_HOME`` and guarded by a small manifest for status and rollback.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
PROJECTION_ROOT = ROOT / "projections" / "codex_ds"
ROLE_SPEC = ROOT / "spec" / "roles.json"
TARGETS = {"deepseek-v4-pro", "deepseek-v4-flash"}
SCHEMA = "bbk.codex-ds-lifecycle.v1"
MANIFEST_NAME = ".bbk-codex-ds-manifest.json"
BULK_MANIFEST_NAME = ".bbk-codex-bulk-manifest.json"
BULK_JOURNAL_NAME = ".bbk-codex-bulk-journal.json"
BULK_LOCK_NAME = ".bbk-codex-bulk.lock"


class LifecycleError(RuntimeError):
    pass


def _acquire_bulk_lock(home: Path) -> Path:
    """Acquire the exact Codex-home bulk lock without global/user state."""
    home.mkdir(parents=True, exist_ok=True)
    lock = home / BULK_LOCK_NAME
    try:
        handle = lock.open("x", encoding="utf-8")
        handle.write(json.dumps({"pid": os.getpid(), "scope": str(home)}) + "\n")
        handle.close()
    except FileExistsError as exc:
        raise LifecycleError("bulk lifecycle lock is already held") from exc
    return lock


def _bulk_outputs() -> dict[str, bytes]:
    try:
        from generate_agents import rendered_packaged_omp_codex
        outputs, _ = rendered_packaged_omp_codex()
        return outputs
    except Exception as exc:  # preserve a typed fail-before-mutation error
        raise LifecycleError(f"cannot derive packaged OMP Codex bundle: {exc}") from exc


def bulk_status(*, codex_home: Path) -> dict[str, Any]:
    """Read-only status for the 20-object bulk transaction."""
    manifest_path = codex_home / BULK_MANIFEST_NAME
    journal_path = codex_home / BULK_JOURNAL_NAME
    if journal_path.is_file():
        try:
            journal = json.loads(journal_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {"status": "RECOVERY_REQUIRED", "error": str(exc), "codex_home": str(codex_home)}
        return {"status": "RECOVERY_REQUIRED", "schema": SCHEMA, "journal": journal, "codex_home": str(codex_home)}
    if not manifest_path.is_file():
        return {"status": "ABSENT", "schema": SCHEMA, "codex_home": str(codex_home)}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "DEGRADED_RECOVERY_FAILED", "error": str(exc), "codex_home": str(codex_home)}
    drift: list[str] = []
    for item in manifest.get("files", []):
        path = codex_home / str(item.get("relative", ""))
        if not path.is_file() or _digest(path) != item.get("sha256"):
            drift.append(str(item.get("relative")))
    return {"status": "CURRENT" if not drift else "DRIFTED", "schema": SCHEMA, "mode": manifest.get("mode"), "codex_home": str(codex_home), "role_count": len(manifest.get("files", [])), "drift": drift, "credential_value_persisted": False}


def bulk_install(*, codex_home: Path, force: bool = False, mode: str = "install") -> dict[str, Any]:
    """Install/update all 19 mirror agents as one journaled transaction."""
    outputs = _bulk_outputs()  # pure; fail before acquiring mutation lock
    lock = _acquire_bulk_lock(codex_home)
    journal_path = codex_home / BULK_JOURNAL_NAME
    manifest_path = codex_home / BULK_MANIFEST_NAME
    try:
        if journal_path.exists():
            raise LifecycleError("unfinished bulk journal requires reconciliation")
        existing = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else None
        per_agent = codex_home / MANIFEST_NAME
        if per_agent.is_file():
            raise LifecycleError("BLOCKED_OWNERSHIP_CONFLICT: per-agent lifecycle owns this Codex home")
        if existing and mode == "install" and not force:
            raise LifecycleError("bulk mirror is already installed; use update or --force")
        agent_dir = codex_home / "agents"
        snapshot: dict[str, Any] = {"manifest": existing, "files": {}}
        for name in outputs:
            dest = agent_dir / name
            snapshot["files"][name] = {"present": dest.is_file(), "bytes": dest.read_bytes().hex() if dest.is_file() else None}
        journal = {"schema": "bbk.codex-bulk-journal.v1", "state": "PREPARED", "mode": mode, "snapshot": snapshot, "role_count": len(outputs)}
        journal_path.write_text(json.dumps(journal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        agent_dir.mkdir(parents=True, exist_ok=True)
        records = []
        for name, content in sorted(outputs.items()):
            dest = agent_dir / name
            dest.write_bytes(content)
            records.append({"relative": str(Path("agents") / name), "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)})
        manifest = {"schema": "bbk.codex-bulk-manifest.v2", "lifecycle": mode, "mode": "MIRROR_CANONICAL_OMP", "codex_home": str(codex_home), "role_count": len(records), "files": records, "predecessor": snapshot, "credential_value_persisted": False}
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        journal["state"] = "COMMITTED"
        journal_path.unlink(missing_ok=True)
        return {"status": "PASS", **manifest}
    except Exception:
        # Restore exact pre-state and preserve a journal if restoration fails.
        try:
            if 'snapshot' in locals():
                for name, record in snapshot["files"].items():
                    dest = codex_home / "agents" / name
                    if record["present"]:
                        dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(bytes.fromhex(record["bytes"]))
                    else:
                        dest.unlink(missing_ok=True)
                if snapshot["manifest"] is None: manifest_path.unlink(missing_ok=True)
                else: manifest_path.write_text(json.dumps(snapshot["manifest"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
                journal_path.unlink(missing_ok=True)
        except Exception:
            raise LifecycleError("DEGRADED_RECOVERY_FAILED: predecessor restoration failed")
        raise
    finally:
        lock.unlink(missing_ok=True)


def bulk_rollback(*, codex_home: Path) -> dict[str, Any]:
    manifest_path = codex_home / BULK_MANIFEST_NAME
    if not manifest_path.is_file():
        raise LifecycleError("no bulk predecessor is available")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    predecessor = manifest.get("predecessor")
    if not isinstance(predecessor, Mapping):
        raise LifecycleError("bulk rollback requires a preserved predecessor snapshot")
    lock = _acquire_bulk_lock(codex_home)
    try:
        for name, record in (predecessor.get("files") or {}).items():
            dest = codex_home / "agents" / name
            if record.get("present"):
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(bytes.fromhex(str(record.get("bytes", ""))))
            else:
                dest.unlink(missing_ok=True)
        prior_manifest = predecessor.get("manifest")
        if prior_manifest is None:
            manifest_path.unlink(missing_ok=True)
        else:
            manifest_path.write_text(json.dumps(prior_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    finally:
        lock.unlink(missing_ok=True)
    return {"status": "PASS", "schema": SCHEMA, "codex_home": str(codex_home), "state": "ROLLED_BACK"}


def bulk_uninstall(*, codex_home: Path, force: bool = False) -> dict[str, Any]:
    manifest_path = codex_home / BULK_MANIFEST_NAME
    if not manifest_path.is_file():
        return {"status": "ABSENT", "schema": SCHEMA, "codex_home": str(codex_home)}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    drift = [item for item in manifest.get("files", []) if not (codex_home / item["relative"]).is_file() or _digest(codex_home / item["relative"]) != item.get("sha256")]
    if drift and not force:
        raise LifecycleError("bulk-owned files diverged; use --force to uninstall")
    lock = _acquire_bulk_lock(codex_home)
    try:
        for item in manifest.get("files", []):
            (codex_home / item["relative"]).unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)
    finally:
        lock.unlink(missing_ok=True)
    return {"status": "PASS", "schema": SCHEMA, "codex_home": str(codex_home), "removed": len(manifest.get("files", []))}


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def available_roles() -> set[str]:
    try:
        value = json.loads(ROLE_SPEC.read_text(encoding="utf-8"))
        roles = value.get("roles", [])
        return {str(item["name"]) for item in roles if isinstance(item, Mapping) and item.get("name")}
    except (OSError, json.JSONDecodeError, TypeError, KeyError) as exc:
        raise LifecycleError(f"cannot load role registry: {exc}") from exc


def resolve_actor(role: str | None, target: str | None, *, codex_home: Path) -> dict[str, Any]:
    """Resolve an actor without consulting or persisting a credential value."""
    if not isinstance(role, str) or not role:
        raise LifecycleError("explicit --role is required")
    if role not in available_roles():
        raise LifecycleError(f"unknown role: {role}")
    if not isinstance(target, str) or not target:
        raise LifecycleError("explicit --target is required")
    if target not in TARGETS:
        raise LifecycleError(f"unknown target: {target}")
    source = PROJECTION_ROOT / target / "agents" / f"{role}.toml"
    if not source.is_file():
        raise LifecycleError(f"projection is unavailable for role/target: {role}/{target}")
    return {
        "role": role,
        "target": target,
        "projection": source,
        "credential_ref": {"kind": "environment", "env_key": "DEEPSEEK_API_KEY", "value_persisted": False},
        "codex_home": codex_home,
    }


def _home(value: str | None, project: str | None) -> Path:
    raw = value or os.environ.get("CODEX_HOME")
    if raw:
        return Path(raw).expanduser().resolve()
    if project:
        return (Path(project).expanduser().resolve() / ".codex").resolve()
    raise LifecycleError("project CODEX_HOME is required (use --codex-home, CODEX_HOME, or --project)")


def _manifest(home: Path) -> Path:
    return home / MANIFEST_NAME


def _read_manifest(home: Path) -> dict[str, Any] | None:
    path = _manifest(home)
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleError(f"invalid lifecycle manifest: {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise LifecycleError(f"unsupported lifecycle manifest: {path}")
    return value


def _write_manifest(home: Path, value: Mapping[str, Any]) -> None:
    home.mkdir(parents=True, exist_ok=True)
    temp = home / f"{MANIFEST_NAME}.tmp"
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(_manifest(home))


def install(*, role: str, target: str, codex_home: Path, mode: str = "install", force: bool = False) -> dict[str, Any]:
    actor = resolve_actor(role, target, codex_home=codex_home)
    previous = _read_manifest(codex_home)
    if mode == "install" and previous and not force:
        raise LifecycleError("actor is already installed; use reinstall or update")
    agent_dir = codex_home / "agents"
    destination = agent_dir / f"{role}.toml"
    if destination.exists() and not force and not previous:
        raise LifecycleError(f"refusing to replace unmanaged actor file: {destination}")
    backup = None
    if previous:
        backup_dir = codex_home / ".bbk-codex-ds-backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / f"{int(time.time() * 1000)}.json"
        backup.write_text(json.dumps(previous, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    agent_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(actor["projection"], destination)
    record = {
        "schema": SCHEMA,
        "lifecycle": mode,
        "role": role,
        "target": target,
        "codex_home": str(codex_home),
        "credential_ref": actor["credential_ref"],
        "file": {"path": str(destination), "sha256": _digest(destination)},
        "previous_manifest": str(backup) if backup else None,
    }
    _write_manifest(codex_home, record)
    return {"status": "PASS", **record}


def status(*, codex_home: Path, provider_error: str | None = None) -> dict[str, Any]:
    # Presence is enough for diagnostics; never retrieve or serialize the
    # credential value itself.
    credential_state = "AVAILABLE" if "DEEPSEEK_API_KEY" in os.environ else "ABSENT"
    provider_state = "ERROR" if provider_error else ("READY" if credential_state == "AVAILABLE" else "CREDENTIAL_ABSENT")
    value = _read_manifest(codex_home)
    if value is None:
        result = {"status": "ABSENT", "schema": SCHEMA, "codex_home": str(codex_home)}
        result.update({"credential_state": credential_state, "provider_state": provider_state})
        if provider_error:
            result["provider_error"] = provider_error
        return result
    path = Path(value.get("file", {}).get("path", ""))
    current = _digest(path) if path.is_file() else None
    result = {"status": "CURRENT" if current == value.get("file", {}).get("sha256") else "DRIFTED", **value, "current_sha256": current, "credential_state": credential_state, "provider_state": provider_state}
    if provider_error:
        result["provider_error"] = provider_error
    return result


def rollback(*, codex_home: Path) -> dict[str, Any]:
    current = _read_manifest(codex_home)
    if not current or not current.get("previous_manifest"):
        raise LifecycleError("no lifecycle predecessor is available for rollback")
    predecessor = Path(str(current["previous_manifest"]))
    try:
        value = json.loads(predecessor.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleError(f"cannot read rollback predecessor: {exc}") from exc
    destination = Path(value.get("file", {}).get("path", ""))
    source = PROJECTION_ROOT / str(value.get("target")) / "agents" / f"{value.get('role')}.toml"
    if not source.is_file():
        raise LifecycleError("rollback projection is unavailable")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    value["lifecycle"] = "rollback"
    value["file"]["sha256"] = _digest(destination)
    _write_manifest(codex_home, value)
    return {"status": "PASS", **value}


def uninstall(*, codex_home: Path, force: bool = False) -> dict[str, Any]:
    value = _read_manifest(codex_home)
    if value is None:
        return {"status": "ABSENT", "schema": SCHEMA, "codex_home": str(codex_home)}
    path = Path(value.get("file", {}).get("path", ""))
    if path.exists() and not force and _digest(path) != value.get("file", {}).get("sha256"):
        raise LifecycleError("actor file was modified; use --force to uninstall")
    if path.is_file():
        path.unlink()
    _manifest(codex_home).unlink(missing_ok=True)
    return {"status": "PASS", "schema": SCHEMA, "codex_home": str(codex_home), "removed": str(path)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["install", "reinstall", "update", "status", "rollback", "uninstall", "bulk-install", "bulk-update", "bulk-status", "bulk-rollback", "bulk-uninstall"])
    parser.add_argument("--role")
    parser.add_argument("--target")
    parser.add_argument("--codex-home")
    parser.add_argument("--project")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--provider-error", help="record a provider error for deterministic status diagnostics; no fallback is attempted")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        home = _home(args.codex_home, args.project)
        if args.command == "bulk-status":
            result = bulk_status(codex_home=home)
        elif args.command in {"bulk-install", "bulk-update"}:
            result = bulk_install(codex_home=home, force=args.force, mode="update" if args.command == "bulk-update" else "install")
        elif args.command == "bulk-rollback":
            result = bulk_rollback(codex_home=home)
        elif args.command == "bulk-uninstall":
            result = bulk_uninstall(codex_home=home, force=args.force)
        elif args.command == "status":
            result = status(codex_home=home, provider_error=args.provider_error)
        elif args.command == "rollback":
            result = rollback(codex_home=home)
        elif args.command == "uninstall":
            result = uninstall(codex_home=home, force=args.force)
        else:
            if not args.role or not args.target:
                raise LifecycleError("install, reinstall, and update require explicit --role and --target")
            result = install(role=args.role, target=args.target, codex_home=home, mode=args.command, force=args.force)
    except LifecycleError as exc:
        result = {"status": "REJECTED", "schema": SCHEMA, "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") in {"PASS", "CURRENT", "ABSENT"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
