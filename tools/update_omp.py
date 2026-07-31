#!/usr/bin/env python3
"""Update only BBK's OMP surface while preserving other installed harnesses.

This command is intended for an existing BBK installation. It updates the
installed package copy, BBK launcher, OMP agents, core OMP extension, bundled
language-profile OMP extensions, mutable OMP routing state, and the compact
installed-profile registry. It does not modify Codex, Claude Code, or generic
agent definitions.
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
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import install as install_tool
from path_compat import path_key
from generate_agents import MODEL_ROUTING_PATH, rendered_projections
from model_routing import ModelRoutingError
from omp_model_routing import RoutingError, patch_agent_route, validate_route
from profile_install import ProfileInstallError, PreparedProfile, prepare_profile_sources, profile_summary
from profile_registry import (
    REGISTRY_RELATIVE_PATH,
    profile_runtime_summary,
    registry_json_bytes,
    registry_skill_bytes,
)

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


class OmpUpdateError(RuntimeError):
    """Raised when a targeted OMP update cannot be performed safely."""


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
        raise OmpUpdateError(f"Cannot read existing BBK install manifest {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema") != "bbk.install-manifest.v1":
        raise OmpUpdateError(f"Unsupported BBK install manifest: {path}")
    if not value.get("omp"):
        raise OmpUpdateError("The existing BBK installation does not own an OMP installation")
    return value


def record_map(manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in manifest.get("files", []):
        if not isinstance(raw, dict) or not isinstance(raw.get("path"), str):
            raise OmpUpdateError("Existing install manifest contains an invalid file record")
        key = normalized(Path(raw["path"]))
        if key in result:
            raise OmpUpdateError(f"Existing install manifest contains duplicate path {raw['path']}")
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
            raise OmpUpdateError(
                f"OMP update destination collision at {path}: {prior.source} != {source}"
            )
        return
    desired[key] = item


def add_file(desired: dict[str, DesiredFile], source: Path, destination: Path, *, label: str | None = None) -> None:
    add_desired(
        desired,
        destination,
        source.read_bytes(),
        source=label or install_tool.json_path(source),
        is_executable=bool(source.stat().st_mode & 0o111),
    )


def add_tree(
    desired: dict[str, DesiredFile],
    source: Path,
    destination: Path,
    *,
    label_prefix: str | None = None,
) -> None:
    for path in install_tool.source_files(source):
        rel = path.relative_to(source)
        label = f"{label_prefix}:{rel.as_posix()}" if label_prefix else install_tool.json_path(path)
        add_file(desired, path, destination / rel, label=label)


def owned_json(path: Path, records: Mapping[str, Mapping[str, Any]], label: str) -> dict[str, Any]:
    record = records.get(normalized(path))
    if record is None:
        raise OmpUpdateError(f"Existing manifest does not own {label}: {path}")
    if not path.is_file():
        raise OmpUpdateError(f"{label} is missing: {path}")
    actual = install_tool.sha256_file(path)
    if actual != record.get("sha256"):
        raise OmpUpdateError(
            f"{label} differs from the existing install manifest: {path}; "
            "restore it before updating OMP"
        )
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OmpUpdateError(f"Cannot read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise OmpUpdateError(f"{label} must be a JSON object: {path}")
    return value


def validated_routes(
    state: Mapping[str, Any], role_names: list[str]
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    expected = set(role_names)
    raw_routes = state.get("roles")
    raw_baseline = state.get("installation_default")
    if not isinstance(raw_routes, Mapping) or set(raw_routes) != expected:
        raise OmpUpdateError("Existing OMP routing state does not cover the current canonical roles")
    if not isinstance(raw_baseline, Mapping) or set(raw_baseline) != expected:
        raise OmpUpdateError("Existing OMP routing state has no complete installation_default")
    try:
        routes = {name: validate_route(raw_routes[name], f"roles.{name}") for name in role_names}
        baseline = {
            name: validate_route(raw_baseline[name], f"installation_default.{name}")
            for name in role_names
        }
    except RoutingError as exc:
        raise OmpUpdateError(f"Existing OMP routing state is invalid: {exc}") from exc
    return routes, baseline


def prepared_bundled_profiles(installed_ids: list[str], temp_root: Path) -> tuple[list[PreparedProfile], list[str]]:
    try:
        all_profiles = prepare_profile_sources(
            [str(install_tool.BUNDLED_PROFILES_PATH)], temp_root=temp_root, selected_ids=None
        )
    except ProfileInstallError as exc:
        raise OmpUpdateError(f"Cannot prepare bundled language profiles: {exc}") from exc
    by_id = {item.profile_id: item for item in all_profiles}
    selected = [by_id[item] for item in installed_ids if item in by_id]
    skipped = [item for item in installed_ids if item not in by_id]
    return selected, skipped


def make_desired_files(
    *,
    scope: str,
    project: Path | None,
    root: Path,
    manifest_path: Path,
    old_manifest: Mapping[str, Any],
    old_records: Mapping[str, Mapping[str, Any]],
    prepared_profiles: Sequence[PreparedProfile],
) -> tuple[dict[str, DesiredFile], dict[str, Any], list[dict[str, Any]]]:
    desired: dict[str, DesiredFile] = {}
    targets = install_tool.installation_targets(scope=scope, project=project)
    omp_agents = targets["omp_agents"]
    omp_extensions = targets["omp_extensions"]
    if omp_agents is None or omp_extensions is None:
        raise OmpUpdateError("Cannot resolve OMP installation targets")

    package_root = root / "versions" / VERSION
    add_tree(desired, ROOT, package_root, label_prefix=f"package:{VERSION}")
    add_desired(
        desired,
        root / "current.json",
        install_tool.json_bytes(
            {"schema": "bbk.current-install.v1", "version": VERSION, "path": install_tool.json_path(package_root)}
        ),
        source="generated:current-install",
    )
    bbk_launcher_path: Path | None = None
    if targets["binaries"] is not None:
        launcher_name, launcher_bytes = install_tool.launcher(package_root)
        bbk_launcher_path = targets["binaries"] / launcher_name
        add_desired(
            desired,
            bbk_launcher_path,
            launcher_bytes,
            source="generated:launcher",
            is_executable=True,
        )
    bbk_cli_binding = {
        "launcher": install_tool.json_path(bbk_launcher_path) if bbk_launcher_path else None,
        "python": install_tool.json_path(Path(sys.executable).resolve()),
        "script": install_tool.json_path(package_root / "tools" / "bbk.py"),
    }

    routing_state_meta = old_manifest.get("omp_runtime_routing")
    if not isinstance(routing_state_meta, Mapping) or not isinstance(routing_state_meta.get("state_path"), str):
        raise OmpUpdateError("Existing installation has no mutable OMP routing-state binding")
    state_path = Path(str(routing_state_meta["state_path"]))
    state = owned_json(state_path, old_records, "OMP routing state")

    try:
        projections, projection_meta = rendered_projections(MODEL_ROUTING_PATH.resolve())
    except (OSError, json.JSONDecodeError, ModelRoutingError, ValueError) as exc:
        raise OmpUpdateError(f"Cannot render current OMP agents: {exc}") from exc
    role_names = sorted(projection_meta.get("agents", {}))
    if not role_names:
        raise OmpUpdateError("Current role catalogue produced no OMP agents")
    routes, baseline = validated_routes(state, role_names)

    for filename, data in sorted(projections["omp"].items()):
        role = Path(filename).stem
        if role not in routes:
            raise OmpUpdateError(f"Generated OMP agent has no preserved route: {role}")
        try:
            patched = patch_agent_route(data, role, routes[role])
        except RoutingError as exc:
            raise OmpUpdateError(f"Cannot preserve route for {role}: {exc}") from exc
        add_desired(
            desired,
            omp_agents / filename,
            patched,
            source=f"generated:omp-agent:update:{filename}",
        )

    updated_state = dict(state)
    updated_state.update(
        {
            "schema": "bbk.omp-model-routing-state.v1",
            "package_version": VERSION,
            "installation_default": baseline,
            "roles": routes,
            "routes_sha256": hashlib.sha256(
                json.dumps(routes, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
        }
    )
    add_desired(
        desired,
        state_path,
        install_tool.json_bytes(updated_state),
        source="generated:effective-omp-model-routing:update",
    )

    extension = omp_extensions / "bbk"
    for name in ["index.js", "package.json", "README.md"]:
        add_file(desired, ROOT / "omp" / "extension" / name, extension / name)
    for name in [
        "bbk.py",
        "contracts.py",
        "state_effect.py",
        "review_assurance.py",
        "verify_package.py",
        "path_compat.py",
        "omp_model_routing.py",
    ]:
        add_file(desired, ROOT / "tools" / name, extension / name)
    add_file(desired, ROOT / "VERSION", extension / "VERSION")
    add_desired(
        desired,
        extension / "bbk-package-root.json",
        install_tool.json_bytes(
            {
                "schema": "bbk.omp-package-binding.v2",
                "version": VERSION,
                "path": install_tool.json_path(package_root),
                "package_root": install_tool.json_path(package_root),
                "scope": scope,
                "manifest_path": install_tool.json_path(manifest_path),
                "omp_agents": install_tool.json_path(omp_agents),
                "state_path": install_tool.json_path(state_path),
            }
        ),
        source="generated:omp-package-root-binding:update",
    )
    add_tree(desired, ROOT / "templates", extension / "templates")
    add_tree(desired, ROOT / "spec", extension / "spec")
    add_tree(desired, ROOT / "fixtures", extension / "fixtures")

    old_profiles = [item for item in old_manifest.get("language_profiles", []) if isinstance(item, Mapping)]
    prepared_by_id = {item.profile_id: item for item in prepared_profiles}
    updated_profiles: list[dict[str, Any]] = []
    for old in old_profiles:
        profile_id = str(old.get("id") or "")
        item = prepared_by_id.get(profile_id)
        if item is None:
            updated_profiles.append(dict(old))
            continue
        identity = f"{item.profile_id}@{item.version}"
        package_destination = root / "profiles" / item.profile_id / item.version
        add_tree(
            desired,
            item.root,
            package_destination,
            label_prefix=f"profile:{identity}:package:update",
        )
        add_desired(
            desired,
            root / "profiles" / item.profile_id / "current.json",
            install_tool.json_bytes(
                {
                    "schema": "bbk.current-profile.v1",
                    "id": item.profile_id,
                    "version": item.version,
                    "path": install_tool.json_path(package_destination),
                }
            ),
            source=f"generated:profile-current:update:{identity}",
        )
        extension_source = install_tool._profile_subpath(item, "omp_extension")
        extension_destination = omp_extensions / item.package_name
        if extension_source is not None:
            add_tree(
                desired,
                extension_source,
                extension_destination,
                label_prefix=f"profile:{identity}:omp-extension:update",
            )
        summary = dict(old)
        summary.update(profile_summary(item))
        summary.update(profile_runtime_summary(item))
        summary.update(
            {
                "package_root": install_tool.json_path(package_destination),
                "current": install_tool.json_path(root / "profiles" / item.profile_id / "current.json"),
                "omp_extension": install_tool.json_path(extension_destination) if extension_source else None,
            }
        )
        updated_profiles.append(summary)

    # The compact registry is shared across hosts. Refresh it only when every
    # installed profile was resolved from this release; otherwise preserving the
    # old registry is safer than silently dropping an external/private profile.
    # A running Codex process need not stop: no .codex file is changed, and
    # already-loaded skill context is immutable for that process.
    if len(prepared_profiles) == len(old_profiles):
        profile_json = root / "effective-language-profiles.json"
        add_desired(
            desired,
            profile_json,
            registry_json_bytes(
                prepared_profiles, bbk_version=VERSION, bbk_cli=bbk_cli_binding
            ),
            source="generated:effective-language-profiles:update",
        )
        agent_skills = targets.get("agent_skills")
        if agent_skills is not None:
            add_desired(
                desired,
                agent_skills.joinpath(*REGISTRY_RELATIVE_PATH.parts),
                registry_skill_bytes(
                    prepared_profiles, bbk_version=VERSION, bbk_cli=bbk_cli_binding
                ),
                source="generated:installed-profile-registry-skill:update-omp",
            )

    return desired, updated_state, updated_profiles


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
        raise OmpUpdateError("OMP-only update preflight failed:\n- " + "\n- ".join(problems))
    return planned


def apply_plan(plan: Sequence[PlannedFile], *, dry_run: bool) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if dry_run:
        return [
            {
                "path": install_tool.json_path(item.desired.path),
                "sha256": digest_bytes(item.desired.data),
                "action": item.action,
                "source": item.desired.source,
                "backup": install_tool.json_path(item.backup) if item.backup else None,
                "executable": item.desired.executable,
            }
            for item in plan
        ]

    completed: list[PlannedFile] = []
    try:
        for item in plan:
            if item.action == "unchanged":
                pass
            else:
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
        raise OmpUpdateError(f"OMP-only update failed and rollback was attempted: {exc}") from exc

    for item in plan:
        records.append(
            {
                "path": install_tool.json_path(item.desired.path),
                "sha256": digest_bytes(item.desired.data),
                "action": item.action,
                "source": item.desired.source,
                "backup": install_tool.json_path(item.backup) if item.backup else None,
                "executable": item.desired.executable,
            }
        )
    return records


def merge_manifest(
    old: Mapping[str, Any],
    updated_records: Sequence[Mapping[str, Any]],
    *,
    package_root: Path,
    state: Mapping[str, Any],
    updated_profiles: Sequence[Mapping[str, Any]],
    skipped_profiles: Sequence[str],
    verification: Mapping[str, Any] | None,
    backup_root: Path,
) -> dict[str, Any]:
    merged_records = record_map(old)
    for record in updated_records:
        merged_records[normalized(Path(str(record["path"])))] = dict(record)
    result = dict(old)
    previous_version = str(old.get("version") or "unknown")
    result.update(
        {
            "schema": "bbk.install-manifest.v1",
            "version": VERSION,
            "package_root": install_tool.json_path(package_root),
            "language_profiles": [dict(item) for item in updated_profiles],
            "updated_at": utc_now(),
            "files": sorted(merged_records.values(), key=lambda item: str(item["path"]).replace("\\", "/").casefold()),
            "backup_root": install_tool.json_path(backup_root),
        }
    )
    harness_versions = dict(old.get("harness_versions") or {})
    for name in ("codex", "omp", "claude", "generic"):
        if old.get(name) and name not in harness_versions:
            harness_versions[name] = previous_version
    harness_versions["omp"] = VERSION
    result["harness_versions"] = harness_versions
    result["omp_runtime_routing"] = {
        "schema": "bbk.omp-runtime-routing.v1",
        "active_profile": state.get("active_profile"),
        "source": state.get("source"),
        "description": state.get("description"),
        "state_path": old.get("omp_runtime_routing", {}).get("state_path"),
        "routes_sha256": state.get("routes_sha256"),
        "changed_role_count": old.get("omp_runtime_routing", {}).get("changed_role_count", 0),
        "updated_at": state.get("updated_at"),
    }
    history = [item for item in old.get("update_history", []) if isinstance(item, Mapping)]
    history.append(
        {
            "kind": "omp-only",
            "from_version": previous_version,
            "to_version": VERSION,
            "at": result["updated_at"],
            "untouched_harnesses": [name for name in ("codex", "claude", "generic") if old.get(name)],
            "skipped_profile_extensions": list(skipped_profiles),
            "verification": dict(verification) if verification else None,
        }
    )
    result["update_history"] = history
    result["last_omp_update"] = history[-1]
    if verification is not None:
        result["last_update_verification"] = dict(verification)
    return result


def update_omp(args: argparse.Namespace) -> dict[str, Any]:
    verification = None
    if args.verify:
        try:
            verification = install_tool.run_verification_gate(
                failfast=bool(args.verification_failfast),
                require_node=True,
                echo=not args.json,
            )
        except install_tool.InstallError as exc:
            raise OmpUpdateError(str(exc)) from exc

    project, root = project_and_root(args.scope, args.root)
    mpath = install_tool.manifest_path(args.scope, project, root)
    old_manifest = load_manifest(mpath)
    old_records = record_map(old_manifest)
    installed_ids = [
        str(item.get("id"))
        for item in old_manifest.get("language_profiles", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    ]
    backup_root = root / "backups" / f"omp-update-{install_tool.stamp()}"

    with tempfile.TemporaryDirectory(prefix="bbk-omp-update-profiles-") as raw_temp:
        prepared, skipped = prepared_bundled_profiles(installed_ids, Path(raw_temp))
        desired, state, updated_profiles = make_desired_files(
            scope=args.scope,
            project=project,
            root=root,
            manifest_path=mpath,
            old_manifest=old_manifest,
            old_records=old_records,
            prepared_profiles=prepared,
        )
        plan = plan_files(desired, old_records, force=bool(args.force), backup_root=backup_root)
        update_records = apply_plan(plan, dry_run=bool(args.dry_run))
        package_root = root / "versions" / VERSION
        merged = merge_manifest(
            old_manifest,
            update_records,
            package_root=package_root,
            state=state,
            updated_profiles=updated_profiles,
            skipped_profiles=skipped,
            verification=verification,
            backup_root=backup_root,
        )
        if not args.dry_run:
            install_tool.atomic_write(mpath, install_tool.json_bytes(merged), 0o600)

    actions: dict[str, int] = {}
    for item in update_records:
        action = str(item.get("action"))
        actions[action] = actions.get(action, 0) + 1
    untouched = [name for name in ("codex", "claude", "generic") if old_manifest.get(name)]
    return {
        "schema": "bbk.omp-update-result.v1",
        "status": "DRY-RUN" if args.dry_run else "PASS",
        "scope": args.scope,
        "from_version": old_manifest.get("version"),
        "to_version": VERSION,
        "dry_run": bool(args.dry_run),
        "manifest_path": install_tool.json_path(mpath),
        "package_root": install_tool.json_path(root / "versions" / VERSION),
        "files": update_records,
        "actions": actions,
        "preserved_profile": state.get("active_profile"),
        "preserved_routes_sha256": state.get("routes_sha256"),
        "updated_profile_extensions": [item.profile_id for item in prepared],
        "skipped_profile_extensions": skipped,
        "untouched_harnesses": untouched,
        "codex_files_touched": 0,
        "reload_required": True,
        "reload_command": "/reload-plugins",
        "verification": verification,
    }


def human(value: Mapping[str, Any]) -> str:
    return (
        f"BBK OMP-only update: {value.get('status')}\n"
        f"Version: {value.get('from_version')} -> {value.get('to_version')}\n"
        f"Files: {value.get('actions')}\n"
        f"Preserved OMP routing: {value.get('preserved_profile')}\n"
        f"Updated profile extensions: {', '.join(value.get('updated_profile_extensions') or []) or 'none'}\n"
        f"Untouched harnesses: {', '.join(value.get('untouched_harnesses') or []) or 'none'}\n"
        f"Codex files touched: {value.get('codex_files_touched')}\n"
        f"Manifest: {value.get('manifest_path')}\n"
        "Run /reload-plugins in OMP after the update. A running Codex session does not need to be stopped."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=["user", "project"], default="user")
    parser.add_argument("--root", help="project root for project-scoped installation")
    parser.add_argument("--verify", action="store_true", help="run complete package verification before updating")
    parser.add_argument("--verification-failfast", action="store_true")
    parser.add_argument("--force", action="store_true", help="back up and replace locally modified targeted OMP files")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        value = update_omp(args)
    except (OmpUpdateError, install_tool.InstallError) as exc:
        if args.json:
            print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"bbk OMP update: error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) if args.json else human(value))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
