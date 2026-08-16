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
import contextlib
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from runtime_requirements import enforce_supported_python, direct_python_executable, python_command, python_environment

enforce_supported_python(program='BBK OMP updater')

import dependencies as dependency_tool
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
    if not installed_ids:
        return [], []
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
) -> tuple[dict[str, DesiredFile], dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
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
        "python": install_tool.json_path(Path(direct_python_executable())),
        "script": install_tool.json_path(package_root / "tools" / "bbk.py"),
    }

    routing_state_meta = old_manifest.get("omp_runtime_routing")
    if not isinstance(routing_state_meta, Mapping) or not isinstance(routing_state_meta.get("state_path"), str):
        raise OmpUpdateError("Existing installation has no mutable OMP routing-state binding")
    state_path = Path(str(routing_state_meta["state_path"]))
    state = owned_json(state_path, old_records, "OMP routing state")

    try:
        projections, projection_meta = rendered_projections(MODEL_ROUTING_PATH.resolve(), targets=("omp",))
    except (OSError, json.JSONDecodeError, ModelRoutingError, ValueError) as exc:
        raise OmpUpdateError(f"Cannot render current OMP agents: {exc}") from exc
    role_names = sorted(projection_meta.get("agents", {}))
    if not role_names:
        raise OmpUpdateError("Current role catalogue produced no OMP agents")
    routes, baseline = validated_routes(state, role_names)

    # Preserve explicit custom policy ownership, but refresh packaged-default
    # metadata and its installed effective copy to this successor release.
    # OMP runtime routes remain preserved independently in ``state``.
    old_model_routing = old_manifest.get("model_routing")
    if isinstance(old_model_routing, Mapping) and bool(old_model_routing.get("custom")):
        model_routing_manifest = dict(old_model_routing)
    else:
        effective_routing = root / "effective-model-routing.json"
        add_file(desired, MODEL_ROUTING_PATH.resolve(), effective_routing)
        model_routing_manifest = install_tool.model_routing_manifest_metadata(
            custom=False,
            source=MODEL_ROUTING_PATH.resolve(),
            effective_copy=effective_routing,
            routing_meta=projection_meta,
        )

    for filename, data in sorted(projections["omp"].items()):
        # The generated controller remains inside the installed version
        # package and is loaded by the OMP extension from there.  It is not a
        # role agent and has no mutable per-role route to preserve.
        if filename.startswith("../controllers/"):
            continue
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
    for name in install_tool.OMP_EXTENSION_RUNTIME_FILES:
        add_file(desired, ROOT / "tools" / name, extension / name)
    add_file(desired, ROOT / "VERSION", extension / "VERSION")
    add_desired(
        desired,
        extension / "bbk-package-root.json",
        install_tool.json_bytes(
            {
                "schema": "bbk.omp-package-binding.v3",
                "version": VERSION,
                "path": install_tool.json_path(package_root),
                "package_root": install_tool.json_path(package_root),
                "scope": scope,
                "project_root": install_tool.json_path(project) if project else None,
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

    return desired, updated_state, updated_profiles, model_routing_manifest



def validate_runtime_inventory(
    desired: Mapping[str, DesiredFile],
    *,
    extension: Path,
) -> dict[str, Any]:
    """Prove that the selective updater owns the complete adjacent runtime."""
    expected = [extension / name for name in install_tool.OMP_EXTENSION_RUNTIME_FILES]
    missing = [install_tool.json_path(path) for path in expected if normalized(path) not in desired]
    if missing:
        raise OmpUpdateError(
            "OMP selective-update runtime inventory is incomplete; missing desired files:\n- "
            + "\n- ".join(missing)
        )
    return {
        "schema": "bbk.omp-runtime-inventory.v1",
        "status": "PASS",
        "extension": install_tool.json_path(extension),
        "file_count": len(expected),
        "files": [install_tool.json_path(path) for path in expected],
    }


def restore_planned_files(plan: Sequence[PlannedFile]) -> None:
    """Best-effort rollback for a plan after a post-install smoke failure."""
    for item in reversed(plan):
        try:
            if item.action == "unchanged":
                continue
            if item.original is None:
                if item.action == "create":
                    item.desired.path.unlink(missing_ok=True)
                continue
            install_tool.atomic_write(
                item.desired.path,
                item.original,
                (item.original_mode or 0o644) & 0o777,
            )
        except Exception:
            pass


def _strict_subprocess_json(command: Sequence[str], *, cwd: Path) -> dict[str, Any]:
    env = python_environment(os.environ, extra={"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    try:
        completed = subprocess.run(
            list(command), cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=45,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OmpUpdateError(f"Installed OMP runtime smoke command could not run: {exc}") from exc
    try:
        stdout = completed.stdout.decode(install_tool.SUBPROCESS_OUTPUT_ENCODING, errors="strict")
        stderr = completed.stderr.decode(install_tool.SUBPROCESS_OUTPUT_ENCODING, errors="strict")
    except UnicodeDecodeError as exc:
        raise OmpUpdateError(f"Installed OMP runtime smoke command returned invalid UTF-8: {exc}") from exc
    try:
        value = json.loads(stdout) if stdout.strip() else None
    except json.JSONDecodeError as exc:
        raise OmpUpdateError(
            f"Installed OMP runtime smoke command returned invalid JSON (exit {completed.returncode}): {exc}; "
            f"stderr={stderr.strip()!r}"
        ) from exc
    if completed.returncode != 0:
        message = value.get("error") if isinstance(value, Mapping) else None
        raise OmpUpdateError(
            f"Installed OMP runtime smoke command failed (exit {completed.returncode}): "
            f"{message or stderr.strip() or stdout.strip()}"
        )
    if not isinstance(value, dict):
        raise OmpUpdateError("Installed OMP runtime smoke command returned no JSON object")
    return value


def smoke_installed_runtime(*, extension: Path, package_root: Path) -> dict[str, Any]:
    """Execute the installed routing and CLI surfaces after selective replacement."""
    import_probe = (
        "import artifact_packages, bbk_artifact, context_packages, handoff_packages, "
        "host_preflight, omp_model_routing, strict_json, governed_filesystem; "
        "print('PASS')"
    )
    env = python_environment(os.environ, extra={"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    try:
        imported = subprocess.run(
            [direct_python_executable(), "-B", "-X", "utf8", "-c", import_probe],
            cwd=extension, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=45,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OmpUpdateError(f"Installed OMP runtime import smoke could not run: {exc}") from exc
    if imported.returncode != 0 or imported.stdout.decode("utf-8", errors="replace").strip() != "PASS":
        raise OmpUpdateError(
            "Installed OMP runtime import smoke failed: "
            + imported.stderr.decode("utf-8", errors="backslashreplace").strip()
        )
    routing = _strict_subprocess_json(
        python_command(extension / "omp_model_routing.py", "--json", "status"),
        cwd=extension,
    )
    if routing.get("status") != "PASS":
        raise OmpUpdateError(f"Installed OMP model-routing status did not pass: {routing}")
    schemas = _strict_subprocess_json(
        python_command(extension / "bbk.py", "--json", "schema", "list"),
        cwd=package_root,
    )
    if not isinstance(schemas.get("count"), int) or int(schemas["count"]) <= 0:
        raise OmpUpdateError(f"Installed BBK CLI schema surface did not return a catalogue: {schemas}")
    return {
        "schema": "bbk.omp-runtime-smoke.v1",
        "status": "PASS",
        "import_closure": "PASS",
        "routing_status": "PASS",
        "routing_active_profile": routing.get("active_profile"),
        "schema_catalogue_count": schemas.get("count"),
    }

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


def path_is_within(path: Path, directory: Path) -> bool:
    path_key_value = normalized(path)
    root_key = normalized(directory).rstrip("/")
    return path_key_value == root_key or path_key_value.startswith(root_key + "/")


def plan_stale_files(
    old_records: Mapping[str, Mapping[str, Any]],
    desired: Mapping[str, DesiredFile],
    *,
    omp_agents: Path,
    omp_extensions: Path,
    state_path: Path,
    preserve_roots: Sequence[Path] = (),
    force: bool,
    backup_root: Path,
) -> list[StaleFile]:
    stale: list[StaleFile] = []
    problems: list[str] = []
    state_key = normalized(state_path)
    for key, raw in sorted(old_records.items()):
        path = Path(str(raw["path"]))
        targeted = (
            path_is_within(path, omp_agents)
            or path_is_within(path, omp_extensions)
            or key == state_key
        )
        preserved_private_profile = any(path_is_within(path, root) for root in preserve_roots)
        if key in desired or not targeted or preserved_private_profile:
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
                f"stale OMP file is locally modified: {path}; rerun with --force to back it up before removal"
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
        raise OmpUpdateError("OMP clean-replacement preflight failed:\n- " + "\n- ".join(problems))
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
        raise OmpUpdateError(
            f"OMP stale-file removal failed and rollback was attempted: {exc}"
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
    model_routing: Mapping[str, Any],
    updated_profiles: Sequence[Mapping[str, Any]],
    skipped_profiles: Sequence[str],
    verification: Mapping[str, Any] | None,
    backup_root: Path,
    removed_stale: Sequence[StaleFile] = (),
    clean: bool = False,
) -> dict[str, Any]:
    merged_records = record_map(old)
    for item in removed_stale:
        merged_records.pop(normalized(item.path), None)
    for record in updated_records:
        merged_records[normalized(Path(str(record["path"])))] = dict(record)
    result = dict(old)
    previous_version = str(old.get("version") or "unknown")
    result.update(
        {
            "schema": "bbk.install-manifest.v1",
            "version": VERSION,
            "package_root": install_tool.json_path(package_root),
            "model_routing": dict(model_routing),
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
            "clean_replacement": bool(clean),
            "removed_stale_count": len(removed_stale),
        }
    )
    result["update_history"] = history
    result["last_omp_update"] = history[-1]
    if verification is not None:
        result["last_update_verification"] = dict(verification)
    return result


def update_omp(args: argparse.Namespace) -> dict[str, Any]:
    if os.environ.get("BBK_TEST_ALLOW_MISSING_DEPENDENCIES") == "1":
        dependency_report: dict[str, Any] = {
            "schema": "bbk.install-dependency-report.v1",
            "status": "SKIPPED_TEST",
            "selected_harnesses": ["omp"],
            "checks": [],
            "host_checks": [],
            "blocking_count": 0,
            "warning_count": 0,
            "network_accessed": False,
            "mutation_performed": False,
        }
    else:
        try:
            dependency_report = dependency_tool.check_dependencies(("omp",))
        except dependency_tool.DependencyError as exc:
            raise OmpUpdateError(f"Dependency preflight could not be evaluated: {exc}") from exc
        if not args.json:
            print(dependency_tool.format_report(dependency_report), flush=True)
        if dependency_report.get("status") != "PASS":
            remediation = dependency_report.get("remediation_command")
            suffix = f" Run: {remediation}" if remediation else ""
            raise OmpUpdateError(f"Dependency preflight failed; update was not started.{suffix}")

    verification = None
    if args.verify:
        try:
            verification = install_tool.run_verification_gate(
                failfast=bool(args.verification_failfast),
                require_node=True,
                echo=not args.json,
                profile="omp",
                jobs=1,
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
        desired, state, updated_profiles, model_routing_manifest = make_desired_files(
            scope=args.scope,
            project=project,
            root=root,
            manifest_path=mpath,
            old_manifest=old_manifest,
            old_records=old_records,
            prepared_profiles=prepared,
        )
        plan = plan_files(desired, old_records, force=bool(args.force), backup_root=backup_root)
        targets = install_tool.installation_targets(scope=args.scope, project=project)
        omp_agents = targets.get("omp_agents")
        omp_extensions = targets.get("omp_extensions")
        state_meta = old_manifest.get("omp_runtime_routing")
        state_path_raw = state_meta.get("state_path") if isinstance(state_meta, Mapping) else None
        if omp_agents is None or omp_extensions is None or not isinstance(state_path_raw, str):
            raise OmpUpdateError("Cannot resolve OMP clean-replacement targets")
        skipped_roots = [
            Path(str(item["omp_extension"]))
            for item in old_manifest.get("language_profiles", [])
            if isinstance(item, Mapping)
            and str(item.get("id") or "") in set(skipped)
            and isinstance(item.get("omp_extension"), str)
        ]
        extension = omp_extensions / "bbk"
        runtime_inventory = validate_runtime_inventory(desired, extension=extension)
        stale_plan = (
            plan_stale_files(
                old_records,
                desired,
                omp_agents=omp_agents,
                omp_extensions=omp_extensions,
                state_path=Path(state_path_raw),
                preserve_roots=skipped_roots,
                force=bool(args.force),
                backup_root=backup_root,
            )
            if bool(getattr(args, "clean", False))
            else []
        )
        manifest_original = mpath.read_bytes()
        manifest_mode = mpath.stat().st_mode & 0o777
        manifest_written = False
        stale_records: list[dict[str, Any]] = []
        update_records: list[dict[str, Any]] = []
        runtime_smoke: dict[str, Any] = {
            "schema": "bbk.omp-runtime-smoke.v1",
            "status": "NOT_RUN" if args.dry_run else "PENDING",
        }
        try:
            stale_records = apply_stale_files(stale_plan, dry_run=bool(args.dry_run))
            update_records = apply_plan(plan, dry_run=bool(args.dry_run))
            package_root = root / "versions" / VERSION
            merged = merge_manifest(
                old_manifest,
                update_records,
                package_root=package_root,
                state=state,
                model_routing=model_routing_manifest,
                updated_profiles=updated_profiles,
                skipped_profiles=skipped,
                verification=verification,
                backup_root=backup_root,
                removed_stale=stale_plan,
                clean=bool(getattr(args, "clean", False)),
            )
            merged["dependency_preflight"] = dependency_report
            merged_records = record_map(merged)
            for name in install_tool.OMP_EXTENSION_RUNTIME_FILES:
                runtime_path = extension / name
                desired_item = desired.get(normalized(runtime_path))
                record = merged_records.get(normalized(runtime_path))
                if desired_item is None or record is None or record.get("sha256") != digest_bytes(desired_item.data):
                    raise OmpUpdateError(
                        f"OMP selective-update manifest does not own the current runtime dependency: {runtime_path}"
                    )
            if not args.dry_run:
                install_tool.atomic_write(mpath, install_tool.json_bytes(merged), 0o600)
                manifest_written = True
                runtime_smoke = smoke_installed_runtime(extension=extension, package_root=package_root)
        except Exception:
            if not args.dry_run:
                if manifest_written:
                    with contextlib.suppress(Exception):
                        install_tool.atomic_write(mpath, manifest_original, manifest_mode)
                restore_planned_files(plan)
                restore_stale_files(stale_plan)
            raise

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
        "dependency_preflight": dependency_report,
        "files": update_records,
        "removed_stale_files": stale_records,
        "removed_stale_count": len(stale_records),
        "clean_replacement": bool(getattr(args, "clean", False)),
        "actions": actions,
        "preserved_profile": state.get("active_profile"),
        "preserved_routes_sha256": state.get("routes_sha256"),
        "updated_profile_extensions": [item.profile_id for item in prepared],
        "skipped_profile_extensions": skipped,
        "untouched_harnesses": untouched,
        "codex_files_touched": 0,
        "reload_required": True,
        "reload_command": "/reload-plugins",
        "runtime_inventory": runtime_inventory,
        "runtime_smoke": runtime_smoke,
        "verification": verification,
    }


def human(value: Mapping[str, Any]) -> str:
    return (
        f"BBK OMP-only update: {value.get('status')}\n"
        f"Version: {value.get('from_version')} -> {value.get('to_version')}\n"
        f"Files: {value.get('actions')}\n"
        f"Preserved OMP routing: {value.get('preserved_profile')}\n"
        f"Updated profile extensions: {', '.join(value.get('updated_profile_extensions') or []) or 'none'}\n"
        f"Stale OMP files removed: {value.get('removed_stale_count', 0)}\n"
        f"Untouched harnesses: {', '.join(value.get('untouched_harnesses') or []) or 'none'}\n"
        f"Codex files touched: {value.get('codex_files_touched')}\n"
        f"Manifest: {value.get('manifest_path')}\n"
        "Run /reload-plugins in OMP after the update. A running Codex session does not need to be stopped."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=["user", "project"], default="user")
    parser.add_argument("--root", help="project root for project-scoped installation")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="run package trust/drift checks and the OMP-focused regression suite before updating",
    )
    parser.add_argument("--verification-failfast", action="store_true")
    parser.add_argument("--force", action="store_true", help="back up and replace locally modified targeted OMP files")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="remove manifest-owned OMP files that are no longer part of the successor projection",
    )
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
