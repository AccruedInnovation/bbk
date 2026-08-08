#!/usr/bin/env python3
"""Update BBK's Codex custom-agent and Codex-facing skill surface.

This command is intended for an existing BBK installation. It updates BBK's
installed Codex custom-agent definitions, the effective optional external-skill
catalog (excluding compiled primary procedures), and the unified installation
manifest. It
deliberately preserves the installed package copy, current pointer, launcher,
effective model-routing file, OMP agent/extension state, Claude Code, generic
agent files, language-profile packages, and OMP runtime model-routing state.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from runtime_requirements import enforce_supported_python

enforce_supported_python(program='BBK Codex updater')

import dependencies as dependency_tool
import install as install_tool
from path_compat import path_key
from generate_agents import rendered_projections
from model_routing import ModelRoutingError

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


class CodexUpdateError(RuntimeError):
    """Raised when a targeted Codex update cannot be performed safely."""


@dataclass(frozen=True)
class DesiredFile:
    path: Path
    data: bytes
    source: str
    executable: bool = False


@dataclass
class PlannedFile:
    desired: DesiredFile
    action: str
    old_record: dict[str, Any] | None
    backup: Path | None = None
    original: bytes | None = None
    original_mode: int | None = None


@dataclass
class StaleFile:
    path: Path
    record: dict[str, Any]
    backup: Path | None = None
    original: bytes | None = None
    original_mode: int | None = None


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalized(path: Path) -> str:
    return path_key(path)


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def executable(path: Path) -> bool:
    return os.name != "nt" and bool(path.stat().st_mode & 0o111)


def project_and_root(scope: str, raw_root: str | None) -> tuple[Path | None, Path]:
    project = (
        Path(raw_root).expanduser().resolve()
        if raw_root
        else (Path.cwd().resolve() if scope == "project" else None)
    )
    root = install_tool.data_root() if scope == "user" else project / ".bbk-kit"  # type: ignore[operator]
    return project, root


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CodexUpdateError(f"Cannot read existing BBK install manifest {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema") != "bbk.install-manifest.v1":
        raise CodexUpdateError(f"Unsupported BBK install manifest: {path}")
    if not value.get("codex"):
        raise CodexUpdateError("The existing BBK installation does not own a Codex installation")
    return value


def record_map(manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in manifest.get("files", []):
        if not isinstance(raw, dict) or not isinstance(raw.get("path"), str):
            raise CodexUpdateError("Existing install manifest contains an invalid file record")
        key = normalized(Path(raw["path"]))
        if key in result:
            raise CodexUpdateError(f"Existing install manifest contains duplicate path {raw['path']}")
        result[key] = raw
    return result


def add_desired(
    desired: dict[str, DesiredFile],
    path: Path,
    data: bytes,
    *,
    source: str,
    is_executable: bool = False,
) -> None:
    item = DesiredFile(path=path, data=data, source=source, executable=bool(is_executable))
    key = normalized(path)
    prior = desired.get(key)
    if prior is not None:
        if prior.data != data or prior.executable != item.executable:
            raise CodexUpdateError(
                f"Codex update destination collision at {path}: {prior.source} != {source}"
            )
        return
    desired[key] = item



def owned_json(path: Path, records: Mapping[str, Mapping[str, Any]], label: str) -> dict[str, Any]:
    record = records.get(normalized(path))
    if record is None:
        raise CodexUpdateError(f"Existing manifest does not own {label}: {path}")
    if not path.is_file():
        raise CodexUpdateError(f"{label} is missing: {path}")
    actual = install_tool.sha256_file(path)
    if actual != record.get("sha256"):
        raise CodexUpdateError(
            f"{label} differs from the existing install manifest: {path}; restore it before updating Codex"
        )
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CodexUpdateError(f"Cannot read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CodexUpdateError(f"{label} must be a JSON object: {path}")
    return value


def render_preserved_codex(
    old_manifest: Mapping[str, Any],
    old_records: Mapping[str, Mapping[str, Any]],
    temp_root: Path,
) -> tuple[dict[str, bytes], dict[str, Any], Path]:
    """Render current Codex agents with the installed model assignments.

    The installed effective policy is treated as immutable shared state because
    OMP and other installed surfaces may still be bound to its package version.
    A temporary version-rebound copy is used only as generator input.
    """
    metadata = old_manifest.get("model_routing")
    if not isinstance(metadata, Mapping) or not isinstance(metadata.get("effective_copy"), str):
        raise CodexUpdateError("Existing installation has no effective model-routing policy")
    effective_path = Path(str(metadata["effective_copy"]))
    policy = owned_json(effective_path, old_records, "effective model-routing policy")
    policy["package_version"] = VERSION
    candidate = temp_root / "effective-model-routing.json"
    candidate.write_bytes(install_tool.json_bytes(policy))
    try:
        projections, projection_meta = rendered_projections(candidate, targets=("codex",))
    except (OSError, json.JSONDecodeError, ModelRoutingError, ValueError) as exc:
        raise CodexUpdateError(f"Cannot render current Codex agents with the preserved routing policy: {exc}") from exc
    codex = projections.get("codex")
    if not isinstance(codex, dict) or not codex:
        raise CodexUpdateError("Current role catalogue produced no Codex agents")
    return codex, projection_meta, effective_path


def make_desired_files(
    *,
    scope: str,
    project: Path | None,
    old_manifest: Mapping[str, Any],
    old_records: Mapping[str, Mapping[str, Any]],
    temp_root: Path,
) -> tuple[dict[str, DesiredFile], dict[str, Any], Path]:
    desired: dict[str, DesiredFile] = {}
    targets = install_tool.installation_targets(scope=scope, project=project)
    codex_agents = targets["codex_agents"]
    if codex_agents is None:
        raise CodexUpdateError("Cannot resolve Codex installation target")

    codex, projection_meta, effective_path = render_preserved_codex(
        old_manifest, old_records, temp_root
    )
    for filename, data in sorted(codex.items()):
        # Controller projections are package-owned runtime inputs, not Codex
        # role definitions.  Keep them out of the host agent directory.
        if filename.startswith("../controllers/"):
            continue
        add_desired(
            desired,
            codex_agents / filename,
            data,
            source=f"generated:codex-agent:update:{filename}",
        )

    agent_skills = targets.get("agent_skills")
    if agent_skills is None:
        raise CodexUpdateError("Cannot resolve Codex skill installation target")
    skill_source = ROOT / "shared" / "skills"
    if not skill_source.is_dir():
        raise CodexUpdateError(f"Canonical shared skill source is missing: {skill_source}")
    exclusions = install_tool.compiled_skill_catalog_exclusions(ROOT)
    registry_rel = install_tool.REGISTRY_RELATIVE_PATH.as_posix()
    for source_path in install_tool.source_files(skill_source):
        relative = source_path.relative_to(skill_source)
        rel_text = relative.as_posix()
        if rel_text in exclusions or rel_text == registry_rel:
            continue
        add_desired(
            desired,
            agent_skills / relative,
            source_path.read_bytes(),
            source=install_tool.json_path(source_path),
            is_executable=bool(source_path.stat().st_mode & 0o111),
        )
    return desired, projection_meta, effective_path


def plan_files(
    desired: Mapping[str, DesiredFile],
    old_records: Mapping[str, Mapping[str, Any]],
    *,
    force: bool,
    backup_root: Path,
) -> list[PlannedFile]:
    planned: list[PlannedFile] = []
    problems: list[str] = []
    for key, item in sorted(desired.items(), key=lambda pair: install_tool.json_path(pair[1].path)):
        record = old_records.get(key)
        wanted_digest = digest_bytes(item.data)
        if not item.path.exists():
            planned.append(PlannedFile(item, "create", dict(record) if record else None))
            continue
        if not item.path.is_file():
            problems.append(f"not a regular file: {item.path}")
            continue
        current_digest = install_tool.sha256_file(item.path)
        mode_matches = os.name == "nt" or executable(item.path) == item.executable
        if current_digest == wanted_digest and mode_matches:
            planned.append(PlannedFile(item, "unchanged", dict(record) if record else None))
            continue
        owned_current = (
            record is not None
            and current_digest == record.get("sha256")
            and (
                os.name == "nt"
                or "executable" not in record
                or executable(item.path) == bool(record.get("executable"))
            )
        )
        if not owned_current and not force:
            problems.append(
                f"locally modified or unowned destination: {item.path}; rerun with --force to back it up and replace it"
            )
            continue
        backup = install_tool.backup_path(backup_root, item.path) if not owned_current else None
        planned.append(
            PlannedFile(
                item,
                "replace" if current_digest != wanted_digest else "chmod",
                dict(record) if record else None,
                backup=backup,
                original=item.path.read_bytes(),
                original_mode=item.path.stat().st_mode,
            )
        )
    if problems:
        raise CodexUpdateError("Codex-only update preflight failed:\n- " + "\n- ".join(problems))
    return planned


def path_is_within(path: Path, directory: Path) -> bool:
    path_key_value = normalized(path)
    root_key = normalized(directory).rstrip("/")
    return path_key_value == root_key or path_key_value.startswith(root_key + "/")


def plan_stale_files(
    old_records: Mapping[str, Mapping[str, Any]],
    desired: Mapping[str, DesiredFile],
    *,
    codex_agents: Path,
    agent_skills: Path,
    force: bool,
    backup_root: Path,
) -> list[StaleFile]:
    stale: list[StaleFile] = []
    problems: list[str] = []
    for key, raw in sorted(old_records.items()):
        path = Path(str(raw["path"]))
        if key in desired:
            continue
        source = str(raw.get("source") or "")
        in_codex_agents = path_is_within(path, codex_agents)
        in_bbk_skills = path_is_within(path, agent_skills) and (
            source.startswith("shared/skills/")
            or source.startswith("generated:installed-profile-registry-skill")
            or "/shared/skills/" in source.replace("\\", "/")
        )
        if not (in_codex_agents or in_bbk_skills):
            continue
        record = dict(raw)
        if not path.exists():
            stale.append(StaleFile(path=path, record=record))
            continue
        if not path.is_file():
            problems.append(f"stale manifest-owned path is not a regular file: {path}")
            continue
        current_digest = install_tool.sha256_file(path)
        mode_matches = (
            os.name == "nt"
            or "executable" not in record
            or executable(path) == bool(record.get("executable"))
        )
        owned_current = current_digest == record.get("sha256") and mode_matches
        if not owned_current and not force:
            problems.append(
                f"stale Codex file is locally modified: {path}; rerun with --force to back it up before removal"
            )
            continue
        backup = install_tool.backup_path(backup_root, path) if not owned_current else None
        stale.append(
            StaleFile(
                path=path,
                record=record,
                backup=backup,
                original=path.read_bytes(),
                original_mode=path.stat().st_mode,
            )
        )
    if problems:
        raise CodexUpdateError("Codex clean-replacement preflight failed:\n- " + "\n- ".join(problems))
    return stale


def stale_record(item: StaleFile) -> dict[str, Any]:
    return {
        "path": install_tool.json_path(item.path),
        "action": "remove-stale",
        "source": item.record.get("source"),
        "expected": item.record.get("sha256"),
        "backup": install_tool.json_path(item.backup) if item.backup else None,
    }


def apply_stale_files(plan: Sequence[StaleFile], *, dry_run: bool) -> list[dict[str, Any]]:
    if dry_run:
        return [stale_record(item) for item in plan]
    completed: list[StaleFile] = []
    try:
        for item in plan:
            if item.path.exists():
                if item.backup is not None:
                    item.backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item.path, item.backup)
                item.path.unlink()
            completed.append(item)
    except Exception as exc:
        restore_stale_files(completed)
        raise CodexUpdateError(
            f"Codex stale-file removal failed and rollback was attempted: {exc}"
        ) from exc
    return [stale_record(item) for item in plan]


def restore_stale_files(plan: Sequence[StaleFile]) -> None:
    for item in reversed(plan):
        if item.original is None:
            continue
        try:
            install_tool.atomic_write(
                item.path,
                item.original,
                (item.original_mode or 0o644) & 0o777,
            )
        except Exception:
            pass


def record_for(item: PlannedFile) -> dict[str, Any]:
    return {
        "path": install_tool.json_path(item.desired.path),
        "sha256": digest_bytes(item.desired.data),
        "action": item.action,
        "source": item.desired.source,
        "backup": install_tool.json_path(item.backup) if item.backup else None,
        "executable": item.desired.executable,
    }


def apply_plan(plan: Sequence[PlannedFile], *, dry_run: bool) -> list[dict[str, Any]]:
    if dry_run:
        return [record_for(item) for item in plan]
    completed: list[PlannedFile] = []
    try:
        for item in plan:
            if item.action != "unchanged":
                if item.backup is not None and item.desired.path.exists():
                    item.backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item.desired.path, item.backup)
                install_tool.atomic_write(
                    item.desired.path,
                    item.desired.data,
                    0o755 if item.desired.executable else 0o644,
                )
            completed.append(item)
    except Exception as exc:
        for item in reversed(completed):
            try:
                if item.original is None:
                    if item.action == "create":
                        item.desired.path.unlink(missing_ok=True)
                else:
                    install_tool.atomic_write(
                        item.desired.path,
                        item.original,
                        (item.original_mode or 0o644) & 0o777,
                    )
            except Exception:
                pass
        raise CodexUpdateError(f"Codex-only update failed and rollback was attempted: {exc}") from exc
    return [record_for(item) for item in plan]


def merge_manifest(
    old: Mapping[str, Any],
    updated_records: Sequence[Mapping[str, Any]],
    *,
    effective_path: Path,
    projection_meta: Mapping[str, Any],
    verification: Mapping[str, Any] | None,
    backup_root: Path,
    removed_stale: Sequence[StaleFile] = (),
    clean: bool = False,
) -> dict[str, Any]:
    """Update Codex ownership records without rebinding shared package state."""
    merged_records = record_map(old)
    for item in removed_stale:
        merged_records.pop(normalized(item.path), None)
    for record in updated_records:
        merged_records[normalized(Path(str(record["path"])))] = dict(record)
    result = dict(old)
    installation_version = str(old.get("version") or "unknown")
    harness_versions = dict(old.get("harness_versions") or {})
    for name in ("codex", "omp", "claude", "generic"):
        if old.get(name) and name not in harness_versions:
            harness_versions[name] = installation_version
    previous_codex_version = str(harness_versions.get("codex") or installation_version)
    harness_versions["codex"] = VERSION

    result.update(
        {
            "schema": "bbk.install-manifest.v1",
            # Keep the shared installation/package version unchanged. An OMP
            # binding from that release validates against this field.
            "version": old.get("version"),
            "package_root": old.get("package_root"),
            "updated_at": utc_now(),
            "files": sorted(
                merged_records.values(),
                key=lambda item: str(item["path"]).replace("\\", "/").casefold(),
            ),
            "backup_root": install_tool.json_path(backup_root),
            "harness_versions": harness_versions,
        }
    )
    history = [item for item in old.get("update_history", []) if isinstance(item, Mapping)]
    history.append(
        {
            "kind": "codex-only",
            "from_version": previous_codex_version,
            "to_version": VERSION,
            "at": result["updated_at"],
            "shared_installation_version": installation_version,
            "shared_package_updated": False,
            "effective_model_routing_updated": False,
            "effective_model_routing_path": install_tool.json_path(effective_path),
            "projection_source_sha256": projection_meta.get("source_sha256"),
            "model_routing_source_sha256": projection_meta.get("model_routing_source_sha256"),
            "untouched_harnesses": [name for name in ("omp", "claude", "generic") if old.get(name)],
            "verification": dict(verification) if verification else None,
            "clean_replacement": bool(clean),
            "removed_stale_count": len(removed_stale),
        }
    )
    result["update_history"] = history
    result["last_codex_update"] = history[-1]
    if verification is not None:
        result["last_update_verification"] = dict(verification)
    return result


def update_codex(args: argparse.Namespace) -> dict[str, Any]:
    if os.environ.get("BBK_TEST_ALLOW_MISSING_DEPENDENCIES") == "1":
        dependency_report: dict[str, Any] = {
            "schema": "bbk.install-dependency-report.v1",
            "status": "SKIPPED_TEST",
            "selected_harnesses": ["codex"],
            "checks": [],
            "host_checks": [],
            "blocking_count": 0,
            "warning_count": 0,
            "network_accessed": False,
            "mutation_performed": False,
        }
    else:
        try:
            dependency_report = dependency_tool.check_dependencies(("codex",))
        except dependency_tool.DependencyError as exc:
            raise CodexUpdateError(f"Dependency preflight could not be evaluated: {exc}") from exc
        if not args.json:
            print(dependency_tool.format_report(dependency_report), flush=True)
        if dependency_report.get("status") != "PASS":
            remediation = dependency_report.get("remediation_command")
            suffix = f" Run: {remediation}" if remediation else ""
            raise CodexUpdateError(f"Dependency preflight failed; update was not started.{suffix}")

    verification = None
    if args.verify:
        try:
            verification = install_tool.run_verification_gate(
                failfast=bool(args.verification_failfast),
                require_node=False,
                echo=not args.json,
                profile="codex",
                jobs=1,
            )
        except install_tool.InstallError as exc:
            raise CodexUpdateError(str(exc)) from exc

    project, root = project_and_root(args.scope, args.root)
    mpath = install_tool.manifest_path(args.scope, project, root)
    old_manifest = load_manifest(mpath)
    old_records = record_map(old_manifest)
    backup_root = root / "backups" / f"codex-update-{install_tool.stamp()}"

    with tempfile.TemporaryDirectory(prefix="bbk-codex-update-") as raw_temp:
        desired, projection_meta, effective_path = make_desired_files(
            scope=args.scope,
            project=project,
            old_manifest=old_manifest,
            old_records=old_records,
            temp_root=Path(raw_temp),
        )
        plan = plan_files(desired, old_records, force=bool(args.force), backup_root=backup_root)
        targets = install_tool.installation_targets(scope=args.scope, project=project)
        codex_agents = targets.get("codex_agents")
        agent_skills = targets.get("agent_skills")
        if codex_agents is None or agent_skills is None:
            raise CodexUpdateError("Cannot resolve Codex installation targets")
        stale_plan = (
            plan_stale_files(
                old_records,
                desired,
                codex_agents=codex_agents,
                agent_skills=agent_skills,
                force=bool(args.force),
                backup_root=backup_root,
            )
            if bool(getattr(args, "clean", False))
            else []
        )
        stale_records = apply_stale_files(stale_plan, dry_run=bool(args.dry_run))
        try:
            update_records = apply_plan(plan, dry_run=bool(args.dry_run))
        except Exception:
            if not args.dry_run:
                restore_stale_files(stale_plan)
            raise
        merged = merge_manifest(
            old_manifest,
            update_records,
            effective_path=effective_path,
            projection_meta=projection_meta,
            verification=verification,
            backup_root=backup_root,
            removed_stale=stale_plan,
            clean=bool(getattr(args, "clean", False)),
        )
        merged["dependency_preflight"] = dependency_report
        if not args.dry_run:
            install_tool.atomic_write(mpath, install_tool.json_bytes(merged), 0o600)

    actions: dict[str, int] = {}
    for item in update_records:
        action = str(item.get("action"))
        actions[action] = actions.get(action, 0) + 1
    untouched = [name for name in ("omp", "claude", "generic") if old_manifest.get(name)]
    prior_versions = old_manifest.get("harness_versions")
    previous_codex_version = (
        prior_versions.get("codex")
        if isinstance(prior_versions, Mapping) and prior_versions.get("codex")
        else old_manifest.get("version")
    )
    return {
        "schema": "bbk.codex-update-result.v1",
        "status": "DRY-RUN" if args.dry_run else "PASS",
        "scope": args.scope,
        "from_version": previous_codex_version,
        "to_version": VERSION,
        "dry_run": bool(args.dry_run),
        "manifest_path": install_tool.json_path(mpath),
        "package_root": old_manifest.get("package_root"),
        "shared_package_updated": False,
        "effective_model_routing_updated": False,
        "source_release_root": install_tool.json_path(ROOT),
        "dependency_preflight": dependency_report,
        "files": update_records,
        "removed_stale_files": stale_records,
        "removed_stale_count": len(stale_records),
        "clean_replacement": bool(getattr(args, "clean", False)),
        "actions": actions,
        "codex_agent_count": len(projection_meta.get("agents", {})),
        "codex_skill_file_count": sum(
            1 for item in update_records
            if "/.agents/skills/bbk-artifact/" in str(item.get("path", "")).replace("\\", "/")
        ),
        "untouched_harnesses": untouched,
        "omp_files_touched": 0,
        "claude_files_touched": 0,
        "generic_files_touched": 0,
        "verification": verification,
    }


def human(value: Mapping[str, Any]) -> str:
    return (
        f"BBK Codex-only update: {value.get('status')}\n"
        f"Version: {value.get('from_version')} -> {value.get('to_version')}\n"
        f"Files: {value.get('actions')}\n"
        f"Codex agents: {value.get('codex_agent_count')}\n"
        f"Codex artifact skill files: {value.get('codex_skill_file_count')}\n"
        f"Stale Codex files removed: {value.get('removed_stale_count', 0)}\n"
        f"Untouched harnesses: {', '.join(value.get('untouched_harnesses') or []) or 'none'}\n"
        f"Manifest: {value.get('manifest_path')}\n"
        "The update changes BBK's Codex agent files, the canonical bbk-artifact skill under Codex's shared skill root, and manifest metadata. It does not modify the shared package, launcher, model-routing file, OMP agent/extension state, Claude Code, or generic agent files. "
        "Start a fresh Codex turn or session if the running host has cached custom-agent definitions or skills."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=["user", "project"], default="user")
    parser.add_argument("--root", help="project root for project-scoped installation")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="run package trust/drift checks and the Codex-focused regression selection before updating",
    )
    parser.add_argument("--verification-failfast", action="store_true")
    parser.add_argument("--force", action="store_true", help="back up and replace locally modified targeted Codex files")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="remove manifest-owned Codex files that are no longer part of the successor projection",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        value = update_codex(args)
    except (CodexUpdateError, install_tool.InstallError) as exc:
        if args.json:
            print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"bbk Codex update: error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) if args.json else human(value))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
