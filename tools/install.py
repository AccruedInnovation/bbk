#!/usr/bin/env python3
"""Cautious BBK installer with verification, model routing, and language profiles."""
from __future__ import annotations

import argparse
import ctypes
import datetime as dt
from collections import OrderedDict
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from copy import copy
from pathlib import Path, PurePath, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence, TextIO

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from runtime_requirements import enforce_supported_python

enforce_supported_python(program="BBK installer")

import dependencies as dependency_tool
from generate_agents import MODEL_ROUTING_PATH, SPEC_PATH, rendered_controller_skill, rendered_projections
from compiled_procedures import globally_suppressed_procedures, physically_indexed_procedures
from model_routing import ModelRoutingError
from path_compat import canonical_path_text, portable_path_key
from profile_install import (
    PreparedProfile,
    ProfileInstallError,
    prepare_profile_sources,
    profile_summary,
)
from profile_registry import (
    REGISTRY_RELATIVE_PATH,
    REGISTRY_SKILL_NAME,
    profile_runtime_summary,
    registry_json_bytes,
    registry_skill_bytes,
)

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
BUNDLED_PROFILES_PATH = ROOT / "bundled-language-profiles"
SUBPROCESS_OUTPUT_ENCODING = "utf-8"
SUBPROCESS_OUTPUT_ERRORS = "backslashreplace"
LANGUAGE_PROFILE_LAYOUT_VERSION = 1
CODEX_ACTIVATION_BEGIN = "<!-- BEGIN BBK CODEX ACTIVATION -->"
CODEX_ACTIVATION_END = "<!-- END BBK CODEX ACTIVATION -->"
CODEX_ACTIVATION_SOURCE = "generated:codex-project-activation"

# Canonical adjacent Python runtime installed beside the OMP extension.  Both
# the full installer and the harness-scoped OMP updater must consume this exact
# inventory.  Keeping one owner prevents selective clean replacement from
# deleting a transitive runtime dependency that the full installer provided.
OMP_EXTENSION_RUNTIME_FILES: tuple[str, ...] = (
    "bbk.py",
    "contracts.py",
    "state_effect.py",
    "review_assurance.py",
    "verify_package.py",
    "path_compat.py",
    "dependencies.py",
    "runtime_requirements.py",
    "strict_json.py",
    "artifact_packages.py",
    "bbk_artifact.py",
    "context_packages.py",
    "host_preflight.py",
    "handoff_packages.py",
    "artifact_classification.py",
    "omp_model_routing.py",
    "gate_kernel.py",
    "governed_state.py",
    "omp_binding_registry.py",
    "governed_filesystem.py",
    "worker_spawn.py",
    "read_only_spawn.py",
    "control_plane.py",
    "qualified_task.py",
    "governance_status.py",
    "verification_economy.py",
    "return_contracts.py",
    "role_return_runtime.py",
    "atomic_finalizer.py",
    "evidence_replay.py",
    "planning_optimization.py",
    "runtime_identity.py",
    "substrate/__init__.py",
    "substrate/beads_adapter.py",
    "substrate/git_adapter.py",
    "substrate/jj_adapter.py",
    "substrate/mise_adapter.py",
)


class InstallError(RuntimeError):
    pass


ProjectionBundle = tuple[Path, dict[str, dict[str, bytes]], dict[str, Any]]
ProjectionCacheKey = tuple[str, str, str, tuple[str, ...]]
_PROJECTION_BUNDLE_CACHE: OrderedDict[ProjectionCacheKey, ProjectionBundle] = OrderedDict()
_PROJECTION_BUNDLE_CACHE_LIMIT = 3


class ProjectionBundleCache:
    """Render the selected model-routing projection at most once per command."""

    def __init__(self, routing_path: Path, targets: Sequence[str]) -> None:
        self.routing_path = routing_path
        self.targets = tuple(targets)
        self._bundle: ProjectionBundle | None = None

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "ProjectionBundleCache":
        routing_path = (
            Path(args.model_routing).expanduser().resolve()
            if args.model_routing
            else MODEL_ROUTING_PATH.resolve()
        )
        targets = tuple(
            name for name in HARNESS_ORDER if name in selected_harness_names(args)
        )
        return cls(routing_path, targets)

    def get(self) -> ProjectionBundle:
        if self._bundle is not None:
            return self._bundle

        try:
            routing_digest = hashlib.sha256(self.routing_path.read_bytes()).hexdigest()
            package_digest = hashlib.sha256(
                (ROOT / "PACKAGE-MANIFEST.json").read_bytes()
            ).hexdigest()
        except OSError as exc:
            raise InstallError(
                f"Could not read projection inputs for {self.routing_path}: {exc}"
            ) from exc
        key = (str(self.routing_path), routing_digest, package_digest, self.targets)
        cached = _PROJECTION_BUNDLE_CACHE.get(key)
        if cached is not None:
            _PROJECTION_BUNDLE_CACHE.move_to_end(key)
            self._bundle = cached
            return cached

        try:
            projections, routing_meta = rendered_projections(
                self.routing_path,
                targets=self.targets,
            )
        except (OSError, json.JSONDecodeError, ModelRoutingError, ValueError) as exc:
            raise InstallError(
                f"Invalid model-routing policy {self.routing_path}: {exc}"
            ) from exc
        self._bundle = (self.routing_path, projections, routing_meta)
        _PROJECTION_BUNDLE_CACHE[key] = self._bundle
        _PROJECTION_BUNDLE_CACHE.move_to_end(key)
        while len(_PROJECTION_BUNDLE_CACHE) > _PROJECTION_BUNDLE_CACHE_LIMIT:
            _PROJECTION_BUNDLE_CACHE.popitem(last=False)
        return self._bundle


def _stream_text(stream: TextIO, value: str) -> str:
    """Return text safe for strict CP1252 and other legacy host streams."""
    encoding = getattr(stream, "encoding", None)
    if not encoding:
        return value
    try:
        value.encode(encoding)
    except (LookupError, UnicodeEncodeError):
        try:
            return value.encode(encoding, errors="backslashreplace").decode(encoding)
        except LookupError:
            return value.encode("ascii", errors="backslashreplace").decode("ascii")
    return value


def _write_text(stream: TextIO, value: str, *, flush: bool = False) -> None:
    """Write without allowing console encoding to abort installation."""
    stream.write(_stream_text(stream, value))
    if flush:
        stream.flush()


def _configure_standard_stream(stream: TextIO) -> None:
    """Make direct console writes non-fatal without changing its encoding."""
    reconfigure = getattr(stream, "reconfigure", None)
    if not callable(reconfigure):
        return
    try:
        reconfigure(errors=SUBPROCESS_OUTPUT_ERRORS)
    except (AttributeError, OSError, TypeError, ValueError):
        pass


def _subprocess_environment() -> dict[str, str]:
    """Force Python verification children to emit the encoding we decode."""
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = (
        f"{SUBPROCESS_OUTPUT_ENCODING}:{SUBPROCESS_OUTPUT_ERRORS}"
    )
    return environment


class InstallProgress:
    """Low-noise progress for long preflight and file-install phases."""

    def __init__(self, *, enabled: bool, interval_files: int = 250, heartbeat_seconds: float = 10.0):
        self.enabled = enabled
        self.interval_files = max(interval_files, 1)
        self.heartbeat_seconds = max(heartbeat_seconds, 0.0)
        self.label = ""
        self.total: int | None = None
        self.count = 0
        self.started = 0.0
        self.last_report = 0.0

    def start(self, label: str, *, total: int | None = None) -> None:
        self.label = label
        self.total = total
        self.count = 0
        self.started = time.monotonic()
        self.last_report = self.started
        if self.enabled:
            total_text = f" ({total:,} files)" if total is not None else ""
            print(f"==> {label}{total_text}", flush=True)

    def advance(self, destination: Path, action: str) -> None:
        self.count += 1
        if not self.enabled:
            return
        now = time.monotonic()
        due_count = self.count == 1 or self.count % self.interval_files == 0
        due_time = self.heartbeat_seconds > 0 and now - self.last_report >= self.heartbeat_seconds
        complete = self.total is not None and self.count >= self.total
        if due_count or due_time or complete:
            total_text = f"/{self.total:,}" if self.total is not None else ""
            print(
                f"    ... {self.label}: {self.count:,}{total_text} files processed; "
                f"last={action} {destination.name} ({now - self.started:.1f}s)",
                flush=True,
            )
            self.last_report = now

    def finish(self, *, status: str = "PASS") -> None:
        if self.enabled:
            print(
                f"<== {self.label}: {status} — {self.count:,} files in "
                f"{time.monotonic() - self.started:.1f}s",
                flush=True,
            )


def progress_note(enabled: bool, message: str) -> None:
    if enabled:
        print(message, flush=True)


def stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write(path: Path, data: bytes, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.bbk-install-{os.getpid()}")
    temp.write_bytes(data)
    if mode is not None:
        os.chmod(temp, mode)
    os.replace(temp, path)


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")


def json_path(path: PurePath) -> str:
    """Serialize filesystem paths with stable forward slashes in JSON records."""
    return path.as_posix()


def model_routing_manifest_metadata(
    *,
    custom: bool,
    source: Path,
    effective_copy: Path,
    routing_meta: Mapping[str, Any],
) -> dict[str, Any]:
    """Return one canonical install-manifest model-routing record."""
    return {
        "custom": bool(custom),
        "source": json_path(source),
        "effective_copy": json_path(effective_copy),
        "sha256": routing_meta["model_routing_source_sha256"],
        "projection_source_sha256": routing_meta["source_sha256"],
        "schema_version": routing_meta["model_routing_schema"],
        "mode": routing_meta["model_routing_mode"],
        "route_count": routing_meta["model_route_count"],
        "legacy_profile_count": routing_meta["legacy_model_profile_count"],
        "legacy_role_profile_counts": routing_meta["legacy_role_profile_counts"],
    }


def canonical_path(path: str | os.PathLike[str] | Path) -> Path:
    """Return one physical spelling for install ownership and binding records."""
    return Path(canonical_path_text(path))


def selected_project_root(args: argparse.Namespace) -> Path | None:
    if args.root:
        return canonical_path(Path(args.root).expanduser())
    if args.scope == "project":
        return canonical_path(Path.cwd())
    return None


def user_home() -> Path:
    """Return the installer home before falling back to ``Path.home()``.

    ``BBK_HOME`` and ``HOME`` remain explicit test/automation overrides on
    every host, including native Windows.
    """
    for name in ("BBK_HOME", "HOME"):
        if value := os.environ.get(name):
            return canonical_path(Path(value).expanduser())
    return canonical_path(Path.home())


def data_root() -> Path:
    if value := os.environ.get("BBK_INSTALL_ROOT"):
        return canonical_path(Path(value).expanduser())
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(user_home() / "AppData" / "Local")
        return Path(base) / "BBK"
    if sys.platform == "darwin":
        return user_home() / "Library" / "Application Support" / "BBK"
    base = os.environ.get("XDG_DATA_HOME")
    return (Path(base).expanduser() if base else user_home() / ".local" / "share") / "bbk"


def bin_dir() -> Path:
    if value := os.environ.get("BBK_BIN_DIR"):
        return canonical_path(Path(value).expanduser())
    if os.name == "nt":
        return data_root() / "bin"
    return user_home() / ".local" / "bin"


def source_files(root: Path) -> Iterable[Path]:
    excluded = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
    for path in sorted(root.rglob("*"), key=lambda value: value.relative_to(root).as_posix()):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in excluded for part in rel.parts) or path.suffix in {".pyc", ".pyo"}:
            continue
        yield path


def backup_layout(destination: PurePath) -> tuple[str, tuple[str, ...]]:
    """Return a safe namespace and relative path for a backup destination."""
    anchor = destination.drive or destination.anchor
    raw_namespace = anchor or "relative"
    namespace = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_namespace).strip("._-") or "root"
    parts = destination.parts[1:] if destination.anchor else destination.parts
    return namespace, tuple(parts)


def backup_path(backup_root: Path, destination: Path) -> Path:
    namespace, parts = backup_layout(destination)
    return backup_root / namespace / Path(*parts)


def codex_activation_block() -> bytes:
    """Return the small, explicitly bounded project activation block."""
    return (
        f"{CODEX_ACTIVATION_BEGIN}\n"
        "For substantive work in this project, invoke `$bbk` and follow the installed BBK controller skill.\n"
        f"{CODEX_ACTIVATION_END}\n"
    ).encode("utf-8")


def _managed_activation_span(data: bytes) -> tuple[int, int] | None:
    """Locate one structurally valid managed block without changing other bytes."""
    begin = CODEX_ACTIVATION_BEGIN.encode("utf-8")
    end = CODEX_ACTIVATION_END.encode("utf-8")
    begins = [match.start() for match in re.finditer(re.escape(begin), data)]
    ends = [match.start() for match in re.finditer(re.escape(end), data)]
    if not begins and not ends:
        return None
    if len(begins) != 1 or len(ends) != 1 or begins[0] >= ends[0]:
        raise InstallError("AGENTS.md contains malformed or duplicate BBK activation markers")
    start = begins[0]
    finish = ends[0] + len(end)
    if finish < len(data) and data[finish : finish + 2] == b"\r\n":
        finish += 2
    elif finish < len(data) and data[finish : finish + 1] == b"\n":
        finish += 1
    return start, finish


def render_codex_activation(existing: bytes, *, replace_existing: bool) -> bytes:
    """Append or replace only BBK's marked activation block."""
    block = codex_activation_block()
    span = _managed_activation_span(existing)
    if span is not None:
        if not replace_existing:
            raise InstallError("AGENTS.md already contains a BBK activation block not owned by this install")
        return existing[: span[0]] + block + existing[span[1] :]
    if not existing:
        return block
    separator = b"" if existing.endswith((b"\n\n", b"\r\n\r\n")) else (b"\n" if existing.endswith((b"\n", b"\r\n")) else b"\n\n")
    return existing + separator + block


def install_codex_activation(
    project: Path,
    *,
    dry_run: bool,
    backup_root: Path,
    prior: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Install project activation while keeping AGENTS.md outside file ownership."""
    path = project / "AGENTS.md"
    if path.exists() and not path.is_file():
        raise InstallError(f"Refusing to modify non-file project activation target: {path}")
    existed = path.exists()
    original = path.read_bytes() if existed else b""
    replace_existing = prior is not None
    if replace_existing:
        if portable_path_key(Path(str(prior.get("path")))) != portable_path_key(path):
            raise InstallError("Existing Codex project activation metadata names a different AGENTS.md")
        span = _managed_activation_span(original)
        if span is None or hashlib.sha256(original[slice(*span)]).hexdigest() != prior.get("block_sha256"):
            raise InstallError("Existing BBK activation block differs from its manifest; restore it before reinstalling")
    desired = render_codex_activation(original, replace_existing=replace_existing)
    original_backup = (
        Path(str(prior["original_backup"]))
        if prior is not None and isinstance(prior.get("original_backup"), str)
        else (backup_path(backup_root, path) if existed else None)
    )
    if not dry_run:
        if original_backup is not None and prior is None:
            original_backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, original_backup)
        atomic_write(path, desired, 0o644)
    return {
        "schema": "bbk.codex-project-activation.v1",
        "path": json_path(path),
        "source": CODEX_ACTIVATION_SOURCE,
        "block_sha256": hashlib.sha256(codex_activation_block()).hexdigest(),
        "installed_file_sha256": hashlib.sha256(desired).hexdigest(),
        "created_file": bool(prior.get("created_file")) if prior is not None else not existed,
        "original_sha256": prior.get("original_sha256") if prior is not None else (hashlib.sha256(original).hexdigest() if existed else None),
        "original_backup": json_path(original_backup) if original_backup else None,
        "action": "create" if not existed else ("replace-managed-block" if prior is not None else "update-managed-block"),
    }


def install_bytes(
    data: bytes,
    destination: Path,
    *,
    source: str,
    force: bool,
    dry_run: bool,
    backup_root: Path,
    records: list[dict[str, Any]],
    planned: dict[str, int] | None = None,
    executable: bool = False,
    progress: InstallProgress | None = None,
) -> None:
    digest = hashlib.sha256(data).hexdigest()
    # Keep a single manifest record per physical destination. This catches
    # core/profile or profile/profile collisions during the dry-run preflight,
    # before an actual installation writes any files. Identical co-owned bytes
    # are safe and retain all source provenance on the first record.
    if planned is not None:
        key = portable_path_key(destination)
        prior_index = planned.get(key)
        if prior_index is not None:
            prior = records[prior_index]
            if prior.get("sha256") != digest:
                raise InstallError(
                    "Install-plan collision at "
                    f"{destination}: {prior.get('source')} ({prior.get('sha256')}) "
                    f"!= {source} ({digest})"
                )
            if bool(prior.get("executable")) != bool(executable):
                raise InstallError(
                    "Install-plan mode collision at "
                    f"{destination}: {prior.get('source')} (executable={prior.get('executable')}) "
                    f"!= {source} (executable={bool(executable)})"
                )
            if source != prior.get("source"):
                also_sources = prior.setdefault("also_sources", [])
                if source not in also_sources:
                    also_sources.append(source)
            return
        planned[key] = len(records)
    action = "create"
    backup: Path | None = None
    if destination.exists():
        if not destination.is_file():
            raise InstallError(f"Refusing to replace non-file destination: {destination}")
        existing = sha256_file(destination)
        if existing == digest:
            action = "unchanged"
            previous_executable: bool | None = None
            if os.name != "nt":
                actual_executable = bool(destination.stat().st_mode & 0o111)
                if actual_executable != bool(executable):
                    action = "chmod"
                    previous_executable = actual_executable
                    if not dry_run:
                        os.chmod(destination, 0o755 if executable else 0o644)
            records.append(
                {
                    "path": json_path(destination),
                    "sha256": digest,
                    "action": action,
                    "source": source,
                    "backup": None,
                    "executable": bool(executable),
                    "previous_executable": previous_executable,
                }
            )
            if progress is not None:
                progress.advance(destination, action)
            return
        if not force:
            raise InstallError(
                f"Destination differs: {destination}; rerun with --force to back it up and replace it"
            )
        backup = backup_path(backup_root, destination)
        action = "replace"
        if not dry_run:
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destination, backup)
    if not dry_run:
        atomic_write(destination, data, 0o755 if executable else 0o644)
    records.append(
        {
            "path": json_path(destination),
            "sha256": digest,
            "action": action,
            "source": source,
            "backup": json_path(backup) if backup else None,
            "executable": bool(executable),
        }
    )
    if progress is not None:
        progress.advance(destination, action)


def install_file(
    source: Path,
    destination: Path,
    *,
    source_label: str | None = None,
    **kwargs: Any,
) -> None:
    install_bytes(
        source.read_bytes(),
        destination,
        source=source_label or json_path(source),
        executable=bool(source.stat().st_mode & 0o111),
        **kwargs,
    )


def copy_tree(
    source: Path,
    destination: Path,
    *,
    source_prefix: str | None = None,
    exclude: set[str] | None = None,
    **kwargs: Any,
) -> None:
    excluded = exclude or set()
    for path in source_files(source):
        rel = path.relative_to(source)
        if rel.as_posix() in excluded:
            continue
        label = f"{source_prefix}:{rel.as_posix()}" if source_prefix else None
        install_file(path, destination / rel, source_label=label, **kwargs)


def compiled_skill_catalog_exclusions(root: Path = ROOT) -> set[str]:
    """Return shared-skill files that must stay outside automatic catalogs.

    The canonical sources remain present in the installed version package for
    deterministic prompt compilation and replay.  They are omitted only from
    host discovery roots such as ``.agents/skills`` and ``.claude/skills``.
    """
    excluded: set[str] = set()
    skill_root = root / "shared" / "skills"
    for procedure_id in globally_suppressed_procedures(root):
        source = skill_root / procedure_id
        if not source.is_dir():
            raise InstallError(f"Compiled procedure source is missing: {source}")
        for path in source_files(source):
            excluded.add((Path(procedure_id) / path.relative_to(source)).as_posix())
    return excluded


def install_rendered_agents(
    files: Mapping[str, bytes],
    destination: Path,
    *,
    target: str,
    routing_digest: str,
    **kwargs: Any,
) -> None:
    """Install model-routed projections without mutating the package tree."""
    for filename, data in sorted(files.items()):
        # Controller projections are package-owned runtime inputs.  They are
        # emitted alongside role projections by the shared compiler using a
        # relative pseudo-path, but must never escape or be copied into a
        # host's role-agent discovery directory.
        if filename.startswith("../controllers/"):
            continue
        install_bytes(
            data,
            destination / filename,
            source=f"generated:{target}-agent:{routing_digest}:{filename}",
            **kwargs,
        )


def generic_agent_manifest_bytes(metadata: Mapping[str, Any], *, target: str = "generic") -> bytes:
    """Return host-neutral metadata kept outside model-facing agent prompts."""
    agents: dict[str, Any] = {}
    for name, value in sorted((metadata.get("agents") or {}).items()):
        if not isinstance(value, Mapping):
            continue
        files = value.get("files") or {}
        agents[name] = {
            "description": value.get("description"),
            "family": value.get("family"),
            "skills": list(value.get("skills") or []),
            "compiled_procedures": value.get("compiled_procedures"),
            "effective_external_catalogs": value.get("effective_external_catalogs"),
            "spawns": list(value.get("spawns") or []),
            "may_mutate": bool(value.get("may_mutate")),
            "model_route": value.get("model_route"),
            "model_routing_mode": value.get("model_routing_mode"),
            "model_routing": value.get("model_routing"),
            "return_contract": value.get("return_contract"),
            "file": files.get(target) if isinstance(files, Mapping) else None,
        }
    return json_bytes(
        {
            "schema": "bbk.installed-host-neutral-agent-manifest.v4",
            "target": target,
            "package_version": metadata.get("package_version"),
            "contract_package": metadata.get("contract_package"),
            "role_return_registry": metadata.get("role_return_registry"),
            "projection_source_sha256": metadata.get("source_sha256"),
            "role_source_sha256": metadata.get("role_source_sha256"),
            "model_routing_source_sha256": metadata.get("model_routing_source_sha256"),
            "procedure_registry_source": metadata.get("procedure_registry_source"),
            "procedure_registry_revision": metadata.get("procedure_registry_revision"),
            "procedure_registry_sha256": metadata.get("procedure_registry_sha256"),
            "globally_suppressed_procedures": list(metadata.get("globally_suppressed_procedures") or []),
            "agents": agents,
        }
    )


def omp_runtime_routing_state_bytes(metadata: Mapping[str, Any]) -> bytes:
    """Return the initial mutable OMP routing state for this installation."""
    routes: dict[str, dict[str, str]] = {}
    for role_name, value in sorted((metadata.get("agents") or {}).items()):
        if not isinstance(value, Mapping):
            continue
        routing = value.get("model_routing") or {}
        omp = routing.get("omp") if isinstance(routing, Mapping) else None
        if not isinstance(omp, Mapping):
            raise InstallError(f"Rendered OMP route is missing for {role_name}")
        model = omp.get("model")
        thinking = omp.get("thinkingLevel")
        if not isinstance(model, str) or not isinstance(thinking, str):
            raise InstallError(f"Rendered OMP route is invalid for {role_name}")
        routes[str(role_name)] = {"model": model, "thinkingLevel": thinking}
    routes_digest = hashlib.sha256(
        json.dumps(routes, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return json_bytes(
        {
            "schema": "bbk.omp-model-routing-state.v1",
            "package_version": VERSION,
            "active_profile": "installation-default",
            "source": "installation-default",
            "description": "Exact OMP routes selected when this BBK installation was created.",
            "updated_at": None,
            "installation_default": routes,
            "roles": routes,
            "routes_sha256": routes_digest,
        }
    )


def install_package_copy(root: Path, **kwargs: Any) -> Path:
    version_root = root / "versions" / VERSION
    copy_tree(ROOT, version_root, **kwargs)
    install_bytes(
        json_bytes(
            {
                "schema": "bbk.current-install.v1",
                "version": VERSION,
                "path": json_path(version_root),
            }
        ),
        root / "current.json",
        source="generated:current-install",
        **kwargs,
    )
    return version_root


def launcher(package_root: Path) -> tuple[str, bytes]:
    script = package_root / "tools" / "bbk.py"
    if os.name == "nt":
        return (
            "bbk.cmd",
            f'@echo off\r\nif defined BBK_PYTHON ("%BBK_PYTHON%" -X utf8 "{script}" %*) else (py -3 -X utf8 "{script}" %*)\r\n'.encode(),
        )
    return "bbk", f'#!/bin/sh\nexec "${{BBK_PYTHON:-python3}}" -X utf8 {json.dumps(str(script))} "$@"\n'.encode()


def profile_launcher(item: PreparedProfile, package_root: Path) -> tuple[str, bytes]:
    installation = item.profile.get("installation") or {}
    raw = installation.get("cli")
    if not isinstance(raw, str):
        raise InstallError(f"Profile {item.profile_id}@{item.version} has no installation.cli")
    rel = PurePosixPath(raw)
    script = package_root.joinpath(*rel.parts)
    command = rel.stem.replace("_", "-")
    if os.name == "nt":
        return (
            f"{command}.cmd",
            f'@echo off\r\nif defined BBK_PYTHON ("%BBK_PYTHON%" -X utf8 "{script}" %*) else (py -3 -X utf8 "{script}" %*)\r\n'.encode(),
        )
    return command, f'#!/bin/sh\nexec "${{BBK_PYTHON:-python3}}" -X utf8 {json.dumps(str(script))} "$@"\n'.encode()


def manifest_path(scope: str, project: Path | None, root: Path) -> Path:
    return root / "install-manifest.json" if scope == "user" else project / ".bbk-kit-install.json"  # type: ignore[operator]


def install_scope_paths(args: argparse.Namespace) -> tuple[Path | None, Path, Path]:
    project = selected_project_root(args)
    root = data_root() if args.scope == "user" else project / ".bbk-kit"  # type: ignore[operator]
    return project, root, manifest_path(args.scope, project, root)


def load_existing_install(args: argparse.Namespace) -> dict[str, Any] | None:
    project, root, mpath = install_scope_paths(args)
    if not mpath.exists():
        return None
    try:
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallError(f"Cannot read existing BBK install manifest {mpath}: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema") not in {"bbk.install-manifest.v1", "bbk.install-manifest.v2"}:
        raise InstallError(f"Unsupported existing BBK install manifest: {mpath}")
    harnesses = [name for name in ("codex", "omp", "claude", "pi", "generic") if manifest.get(name)]
    return {
        "project": project,
        "root": root,
        "manifest_path": mpath,
        "manifest": manifest,
        "version": str(manifest.get("version") or "unknown"),
        "harnesses": harnesses,
        "file_count": len(manifest.get("files", [])),
    }


def _native_windows_console_input() -> bool:
    """Return whether the unwrapped Windows stdin is a real console handle."""
    # Only use the console API for the unwrapped process stdin.  ``isatty`` is
    # not authoritative under PowerShell/Windows Terminal, where a console
    # stream can report a misleading result while ``readline`` still stalls.
    if os.name != "nt" or sys.stdin is not getattr(sys, "__stdin__", None):
        return False
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE
        handle_value = getattr(handle, "value", handle)
        if handle_value in (0, -1, None):
            return False
        mode = ctypes.c_ulong()
        return bool(kernel32.GetConsoleMode(handle, ctypes.byref(mode)))
    except (AttributeError, OSError, TypeError, ValueError, OverflowError, ctypes.ArgumentError):
        return False


def _interactive_stdin() -> bool:
    """Use native console truth, retaining ``isatty`` for wrapped streams."""
    if _native_windows_console_input():
        return True
    # An unwrapped Windows stream was checked by the native detector.  Do not
    # fall back to ``isatty`` after a failed/negative console probe: doing so
    # would route back to the blocking text reader that this guard avoids.
    if os.name == "nt" and sys.stdin is getattr(sys, "__stdin__", None):
        return False
    try:
        return bool(sys.stdin.isatty())
    except (AttributeError, OSError, ValueError):
        return False


def _read_windows_console_line(*, read_key: Any = None) -> str | None:
    # Read and echo one line directly from the Windows console input buffer.
    if read_key is None:
        try:
            import msvcrt
        except ImportError:
            return None
        read_key = msvcrt.getwch
    characters: list[str] = []
    try:
        while True:
            value = read_key()
            if not isinstance(value, str) or value == "":
                return None
            if value in {"\r", "\n"}:
                _write_text(sys.stdout, "\n", flush=True)
                return "".join(characters)
            if value in {"\x00", "\xe0"}:
                # Consume the scan code paired with a special key.
                read_key()
                continue
            if value == "\x03":
                raise KeyboardInterrupt
            if value == "\x1a":
                return None
            if value == "\b":
                if characters:
                    characters.pop()
                    _write_text(sys.stdout, "\b \b", flush=True)
                continue
            if value.isprintable():
                characters.append(value)
                _write_text(sys.stdout, value, flush=True)
    except (OSError, UnicodeError):
        return None


def _read_interactive_confirmation() -> str | None:
    # Avoid the PowerShell TextIO path when a native console is available.
    if _native_windows_console_input():
        return _read_windows_console_line()
    try:
        return input()
    except (EOFError, OSError, UnicodeError):
        return None

def choose_existing_install_action(args: argparse.Namespace, existing: Mapping[str, Any] | None) -> str:
    # Return ``replace`` or ``keep`` without hanging interactive shells.
    # Native Windows confirmation uses ``msvcrt`` instead of the text
    # stream path that can stall under PowerShell/Windows Terminal.
    if existing is None:
        return "none"
    if bool(getattr(args, "uninstall_existing", False)):
        return "replace"
    if bool(getattr(args, "keep_existing", False)):
        return "keep"
    if bool(getattr(args, "json", False)) or bool(getattr(args, "dry_run", False)):
        return "keep"
    is_interactive = _interactive_stdin()
    if not is_interactive:
        progress_note(
            True,
            "Existing BBK installation detected; noninteractive install will preserve it. "
            "Use --uninstall-existing for an explicit clean replacement.",
        )
        return "keep"

    harnesses = ", ".join(existing.get("harnesses", [])) or "none recorded"
    scope = replacement_scope(args, existing)
    validate_replacement_scope(scope)
    selected_text = ", ".join(name for name in HARNESS_ORDER if name in scope["selected"])
    preserved_text = ", ".join(name for name in HARNESS_ORDER if name in scope["preserved"])
    if scope["kind"] == "harness":
        replacement_text = (
            f"A harness-scoped clean replacement refreshes only: {selected_text}. "
            f"It preserves the existing {preserved_text} installation and shared ownership records.\n"
        )
        question_text = f"Clean-replace the selected {selected_text} harness now? [Y/n]\n"
    else:
        replacement_text = (
            "A full clean replacement removes obsolete or changed manifest-owned BBK files, "
            "reuses byte-identical successor files in place, and installs only the harnesses and "
            "profiles selected by this command.\n"
        )
        question_text = "Uninstall the existing BBK installation first? [Y/n]\n"
    prompt_text = (
        "\nExisting BBK installation detected:\n"
        f"  version: {existing.get('version')}\n"
        f"  harnesses: {harnesses}\n"
        f"  files: {existing.get('file_count')}\n"
        f"  manifest: {existing.get('manifest_path')}\n"
        f"{replacement_text}"
        # Preserve the newline: PowerShell may mediate native stdout
        # through a line-oriented host while stdin remains a console.
        f"{question_text}"
    )
    _write_text(sys.stdout, prompt_text, flush=True)
    answer = _read_interactive_confirmation()
    if answer is None:
        progress_note(
            True,
            "Interactive confirmation could not be read; preserving the existing installation. "
            "Use --uninstall-existing for an explicit clean replacement.",
        )
        return "keep"
    return "keep" if answer.strip().lower() in {"n", "no"} else "replace"


def selected_harnesses(args: argparse.Namespace) -> tuple[bool, bool, bool, bool, bool]:
    codex, omp, claude, pi, generic = (
        bool(args.codex), bool(args.omp), bool(args.claude), bool(args.pi), bool(args.generic)
    )
    if not (codex or omp or claude or pi or generic):
        codex = omp = claude = pi = generic = True
    return codex, omp, claude, pi, generic


HARNESS_ORDER = ("codex", "omp", "claude", "pi", "generic")


def selected_harness_names(args: argparse.Namespace) -> set[str]:
    codex, omp, claude, pi, generic = selected_harnesses(args)
    values = {"codex": codex, "omp": omp, "claude": claude, "pi": pi, "generic": generic}
    return {name for name in HARNESS_ORDER if values[name]}


def automatic_verification_profile(args: argparse.Namespace) -> str:
    """Choose the smallest profile that verifies the selected install surface."""
    selected = selected_harness_names(args)
    if selected == {"codex"}:
        return "codex"
    if selected == {"omp"}:
        return "omp"
    if len(selected) == 1:
        return "fast"
    return "standard"


def dependency_test_packages_required(args: argparse.Namespace, profile: str) -> bool:
    return bool(args.verify and profile in {"fast", "standard", "release"})


def run_dependency_preflight(
    args: argparse.Namespace,
    *,
    profile: str,
    echo: bool,
) -> dict[str, Any]:
    """Block before writes when declared dependencies are unavailable."""
    selected = selected_harness_names(args)
    include_tests = dependency_test_packages_required(args, profile)
    if os.environ.get("BBK_TEST_ALLOW_MISSING_DEPENDENCIES") == "1":
        return {
            "schema": "bbk.install-dependency-report.v1",
            "status": "SKIPPED_TEST",
            "selected_harnesses": sorted(selected),
            "include_test_dependencies": include_tests,
            "omp_node_required": "omp" in selected,
            "checks": [],
            "host_checks": [],
            "blocking_count": 0,
            "warning_count": 0,
            "network_accessed": False,
            "mutation_performed": False,
        }
    try:
        report = dependency_tool.check_dependencies(
            selected,
            include_test_dependencies=include_tests,
            require_omp_node="omp" in selected,
        )
    except dependency_tool.DependencyError as exc:
        raise InstallError(f"Dependency preflight could not be evaluated: {exc}") from exc
    if echo:
        print(dependency_tool.format_report(report), flush=True)
    if report.get("status") != "PASS":
        remediation = report.get("remediation_command")
        suffix = f" Run: {remediation}" if remediation else ""
        raise InstallError(f"Dependency preflight failed; installation was not started.{suffix}")
    return report


def existing_harness_names(existing: Mapping[str, Any]) -> set[str]:
    return {str(name) for name in existing.get("harnesses", []) if name in HARNESS_ORDER}


def replacement_scope(args: argparse.Namespace, existing: Mapping[str, Any]) -> dict[str, Any]:
    selected = selected_harness_names(args)
    installed = existing_harness_names(existing)
    preserved = installed - selected
    if not preserved:
        kind = "full"
    elif len(selected) == 1 and selected <= {"omp", "codex"} and selected <= installed:
        kind = "harness"
    else:
        kind = "unsupported-partial"
    return {
        "selected": selected,
        "installed": installed,
        "preserved": preserved,
        "kind": kind,
    }


def validate_replacement_scope(scope: Mapping[str, Any]) -> None:
    if scope.get("kind") != "unsupported-partial":
        return
    selected_values = set(scope.get("selected") or [])
    preserved_values = set(scope.get("preserved") or [])
    selected = ", ".join(name for name in HARNESS_ORDER if name in selected_values) or "none"
    preserved = ", ".join(name for name in HARNESS_ORDER if name in preserved_values) or "none"
    raise InstallError(
        "A partial clean replacement currently supports exactly one already-installed --omp or --codex "
        f"harness. Selected: {selected}; would preserve: {preserved}. No files were removed. "
        "Run separate OMP/Codex selective replacements, use --keep-existing for additive reconciliation, "
        "or select every installed harness for a full clean replacement."
    )


def installation_targets(
    *,
    scope: str,
    project: Path | None,
) -> dict[str, Path | None]:
    if scope == "user":
        home = user_home()
        return {
            "agent_skills": home / ".agents" / "skills",
            "codex_agents": home / ".codex" / "agents",
            "omp_agents": home / ".omp" / "agent" / "agents",
            "omp_extensions": home / ".omp" / "agent" / "extensions",
            "claude_agents": home / ".claude" / "agents",
            "claude_skills": home / ".claude" / "skills",
            "pi_agents": home / ".pi" / "agent" / "agents",
            "generic_agents": home / ".agents" / "bbk" / "agents",
            "binaries": bin_dir(),
        }
    assert project is not None
    return {
        "agent_skills": project / ".agents" / "skills",
        "codex_agents": project / ".codex" / "agents",
        "omp_agents": project / ".omp" / "agents",
        "omp_extensions": project / ".omp" / "extensions",
        "claude_agents": project / ".claude" / "agents",
        "claude_skills": project / ".claude" / "skills",
        "pi_agents": project / ".pi" / "agents",
        "generic_agents": project / ".agents" / "bbk" / "agents",
        "binaries": None,
    }


def _profile_subpath(item: PreparedProfile, key: str) -> Path | None:
    installation = item.profile.get("installation") or {}
    raw = installation.get(key)
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise InstallError(f"Profile {item.profile_id}@{item.version} installation.{key} is invalid")
    return item.root.joinpath(*PurePosixPath(raw).parts)


def install_language_profile(
    item: PreparedProfile,
    *,
    root: Path,
    targets: Mapping[str, Path | None],
    codex: bool,
    omp: bool,
    claude: bool,
    pi: bool,
    generic: bool,
    common: dict[str, Any],
) -> dict[str, Any]:
    identity = f"{item.profile_id}@{item.version}"
    base = root / "profiles" / item.profile_id
    package_root = base / item.version
    copy_tree(item.root, package_root, source_prefix=f"profile:{identity}:package", **common)
    current = base / "current.json"
    install_bytes(
        json_bytes(
            {
                "schema": "bbk.current-profile.v1",
                "id": item.profile_id,
                "version": item.version,
                "path": json_path(package_root),
            }
        ),
        current,
        source=f"generated:profile-current:{identity}",
        **common,
    )

    skill_source = _profile_subpath(item, "skill_root")
    if skill_source is not None:
        if codex or omp or pi or generic:
            assert targets["agent_skills"] is not None
            copy_tree(
                skill_source,
                targets["agent_skills"],
                source_prefix=f"profile:{identity}:skills",
                **common,
            )
        if claude:
            assert targets["claude_skills"] is not None
            copy_tree(
                skill_source,
                targets["claude_skills"],
                source_prefix=f"profile:{identity}:claude-skills",
                **common,
            )

    extension_source = _profile_subpath(item, "omp_extension")
    extension_destination: Path | None = None
    if omp and extension_source is not None:
        assert targets["omp_extensions"] is not None
        extension_destination = targets["omp_extensions"] / item.package_name
        copy_tree(
            extension_source,
            extension_destination,
            source_prefix=f"profile:{identity}:omp-extension",
            **common,
        )

    launcher_path: Path | None = None
    if targets["binaries"] is not None:
        name, content = profile_launcher(item, package_root)
        launcher_path = targets["binaries"] / name
        install_bytes(
            content,
            launcher_path,
            source=f"generated:profile-launcher:{identity}",
            executable=True,
            **common,
        )

    result = profile_summary(item)
    result.update(profile_runtime_summary(item))
    result.update(
        {
            "package_root": json_path(package_root),
            "current": json_path(current),
            "omp_extension": json_path(extension_destination) if extension_destination else None,
            "launcher": json_path(launcher_path) if launcher_path else None,
        }
    )
    return result




def _profile_identity(profile_id: str, version: str) -> str:
    return f"{profile_id}@{version}"


def _record_sources(record: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    source = record.get("source")
    if isinstance(source, str):
        values.append(source)
    for value in record.get("also_sources") or []:
        if isinstance(value, str) and value not in values:
            values.append(value)
    return values


def _source_belongs_to_profile(source: str, identity: str) -> bool:
    return (
        source.startswith(f"profile:{identity}:")
        or source == f"generated:profile-current:{identity}"
        or source == f"generated:profile-launcher:{identity}"
    )


def _profile_record_view(record: Mapping[str, Any], identity: str) -> dict[str, Any] | None:
    sources = [
        source for source in _record_sources(record)
        if _source_belongs_to_profile(source, identity)
    ]
    if not sources:
        return None
    raw_path = record.get("path")
    digest = record.get("sha256")
    if not isinstance(raw_path, str) or not isinstance(digest, str):
        return None
    value = {
        "path": raw_path,
        "sha256": digest,
        "executable": bool(record.get("executable")),
        "sources": sources,
    }
    return value


def _current_file_matches(record: Mapping[str, Any]) -> tuple[bool, str | None]:
    path = Path(str(record["path"]))
    if not path.exists():
        return False, f"missing installed file: {path}"
    if not path.is_file():
        return False, f"installed destination is not a file: {path}"
    try:
        current = sha256_file(path)
    except OSError as exc:
        return False, f"cannot read installed file {path}: {exc}"
    if current != record.get("sha256"):
        return False, f"installed file differs: {path}"
    if os.name != "nt":
        actual_executable = bool(path.stat().st_mode & 0o111)
        if actual_executable != bool(record.get("executable")):
            return False, f"installed file mode differs: {path}"
    return True, None


def language_profile_reuse_plan(
    existing: Mapping[str, Any] | None,
    prepared_profiles: Sequence[PreparedProfile],
    *,
    args: argparse.Namespace,
) -> dict[str, Any]:
    """Return verified unchanged-profile records safe to retain in place.

    Reuse is deliberately conservative. It requires reconciliation mode, the
    same installed harness set, the same profile identity and package digest,
    a compatible installation layout, and current bytes/modes for every
    profile-owned destination. Any uncertainty falls back to the ordinary
    preflight/install path; it never silently adopts changed local files.
    """
    report: dict[str, Any] = {
        "schema": "bbk.language-profile-reuse.v1",
        "layout_version": LANGUAGE_PROFILE_LAYOUT_VERSION,
        "enabled": False,
        "attempted": False,
        "reused_profile_count": 0,
        "reused_file_count": 0,
        "profiles": {},
    }
    if existing is None:
        report["reason"] = "no pre-existing installation"
        return report
    if bool(getattr(args, "uninstall_existing", False)):
        report["reason"] = "clean replacement requested"
        return report
    manifest = existing.get("manifest")
    if not isinstance(manifest, Mapping):
        report["reason"] = "existing manifest unavailable"
        return report
    layout = int(manifest.get("language_profile_layout_version", 1))
    if layout != LANGUAGE_PROFILE_LAYOUT_VERSION:
        report["reason"] = f"layout version {layout} is not reusable"
        return report
    selected_harnesses_set = selected_harness_names(args)
    installed_harnesses_set = {
        name for name in HARNESS_ORDER if bool(manifest.get(name))
    }
    if selected_harnesses_set != installed_harnesses_set:
        report["reason"] = "selected harness set differs from the installed profile projection"
        return report

    report["enabled"] = True
    report["attempted"] = bool(prepared_profiles)
    old_profiles = {
        _profile_identity(str(value.get("id")), str(value.get("version"))): value
        for value in manifest.get("language_profiles", [])
        if isinstance(value, Mapping) and value.get("id") and value.get("version")
    }
    requested_identities = {
        _profile_identity(item.profile_id, item.version) for item in prepared_profiles
    }
    if requested_identities != set(old_profiles):
        report["reason"] = "selected language-profile set differs from the existing installation"
        return report
    manifest_files = [value for value in manifest.get("files", []) if isinstance(value, Mapping)]
    reusable: dict[str, Any] = {}
    for item in prepared_profiles:
        identity = _profile_identity(item.profile_id, item.version)
        outcome: dict[str, Any] = {
            "id": item.profile_id,
            "version": item.version,
            "root_sha256": item.root_sha256,
            "reused": False,
        }
        previous = old_profiles.get(identity)
        if previous is None:
            outcome["reason"] = "profile identity was not previously installed"
            report["profiles"][identity] = outcome
            continue
        if previous.get("root_sha256") != item.root_sha256:
            outcome["reason"] = "profile package digest changed"
            report["profiles"][identity] = outcome
            continue
        records = [
            view
            for record in manifest_files
            if (view := _profile_record_view(record, identity)) is not None
        ]
        if not records:
            outcome["reason"] = "existing manifest has no profile-owned files"
            report["profiles"][identity] = outcome
            continue
        failure: str | None = None
        for record in records:
            matched, reason = _current_file_matches(record)
            if not matched:
                failure = reason or "installed profile file could not be verified"
                break
        if failure:
            outcome["reason"] = failure
            report["profiles"][identity] = outcome
            continue
        outcome.update({
            "reused": True,
            "file_count": len(records),
            "reason": "identity, package digest, harness projection, and installed bytes match",
        })
        report["profiles"][identity] = outcome
        reusable[identity] = {"summary": dict(previous), "records": records}
    report["reused_profile_count"] = len(reusable)
    report["reused_file_count"] = sum(len(value["records"]) for value in reusable.values())
    report["reusable"] = reusable
    return report


def _register_reused_record(
    record: Mapping[str, Any],
    *,
    records: list[dict[str, Any]],
    planned: dict[str, int],
    progress: InstallProgress | None,
    verify_current: bool,
) -> None:
    if verify_current:
        matched, reason = _current_file_matches(record)
        if not matched:
            raise InstallError(
                "An unchanged language-profile file changed after reuse preflight: "
                + str(reason)
            )
    destination = Path(str(record["path"]))
    digest = str(record["sha256"])
    executable = bool(record.get("executable"))
    sources = list(record.get("sources") or [])
    if not sources:
        raise InstallError(f"Reusable language-profile record has no source provenance: {destination}")
    key = portable_path_key(destination)
    prior_index = planned.get(key)
    if prior_index is not None:
        prior = records[prior_index]
        if prior.get("sha256") != digest or bool(prior.get("executable")) != executable:
            raise InstallError(f"Reusable language-profile collision at {destination}")
        provenance = [str(prior.get("source"))] + list(prior.get("also_sources") or [])
        for source in sources:
            if source not in provenance:
                prior.setdefault("also_sources", []).append(source)
                provenance.append(source)
        return
    planned[key] = len(records)
    value: dict[str, Any] = {
        "path": json_path(destination),
        "sha256": digest,
        "action": "reused",
        "source": sources[0],
        "backup": None,
        "executable": executable,
    }
    if len(sources) > 1:
        value["also_sources"] = sources[1:]
    records.append(value)
    if progress is not None:
        progress.advance(destination, "reused")


def install_reused_language_profile(
    item: PreparedProfile,
    reuse: Mapping[str, Any],
    *,
    common: Mapping[str, Any],
) -> dict[str, Any]:
    records = common.get("records")
    planned = common.get("planned")
    if not isinstance(records, list) or not isinstance(planned, dict):
        raise InstallError("Language-profile reuse requires installation-plan records")
    for record in reuse.get("records", []):
        _register_reused_record(
            record,
            records=records,
            planned=planned,
            progress=common.get("progress"),
            verify_current=not bool(common.get("dry_run")),
        )
    result = profile_summary(item)
    result.update(profile_runtime_summary(item))
    previous = reuse.get("summary") if isinstance(reuse.get("summary"), Mapping) else {}
    for key in ("package_root", "current", "omp_extension", "launcher"):
        result[key] = previous.get(key)
    result["install_action"] = "reused"
    result["reused_file_count"] = len(reuse.get("records", []))
    return result


def run_verification_gate(
    *,
    failfast: bool,
    require_node: bool,
    echo: bool,
    profile: str = "standard",
    jobs: int = 0,
    test_mode: str = "auto",
    timing_report: str | None = None,
    no_timing_report: bool = False,
) -> dict[str, Any]:
    """Run verification in a child process while streaming human progress."""
    with tempfile.TemporaryDirectory(prefix="bbk-verification-report-") as raw_temp:
        report_path = Path(raw_temp) / "verification.json"
        command = [
            sys.executable,
            str(ROOT / "tools" / "verify_all.py"),
            "--report-file",
            str(report_path),
            "--profile",
            profile,
            "--jobs",
            str(jobs),
            "--test-mode",
            test_mode,
        ]
        if timing_report:
            command.extend(["--timing-report", timing_report])
        elif no_timing_report:
            command.append("--no-timing-report")
        if failfast:
            command.append("--failfast")
        if require_node:
            command.append("--require-node")
        try:
            environment = dependency_tool.verification_environment(
                _subprocess_environment(),
                include_node=require_node,
                strict=os.environ.get("BBK_TEST_ALLOW_MISSING_DEPENDENCIES") != "1",
            )
        except dependency_tool.DependencyError as exc:
            raise InstallError(f"Verification dependencies are unavailable: {exc}") from exc
        try:
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding=SUBPROCESS_OUTPUT_ENCODING,
                errors=SUBPROCESS_OUTPUT_ERRORS,
                env=environment,
            )
        except OSError as exc:
            raise InstallError(f"Verification runner could not start: {exc}") from exc

        chunks: list[str] = []
        assert process.stdout is not None
        with process.stdout:
            for line in process.stdout:
                chunks.append(line)
                if echo:
                    _write_text(sys.stdout, line, flush=True)
        returncode = process.wait()
        output = "".join(chunks)
        if not report_path.is_file():
            tail = output[-4000:].strip() or "no output"
            raise InstallError(
                "Verification runner did not produce its report; output tail:\n" + tail
            )
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            tail = output[-4000:].strip() or "no output"
            raise InstallError(
                f"Verification runner returned an invalid report: {exc}; output tail:\n{tail}"
            ) from exc
        if returncode != 0 or report.get("status") != "PASS":
            failures = [
                str(item.get("name"))
                for item in report.get("checks", [])
                if isinstance(item, dict) and item.get("status") == "FAIL"
            ]
            raise InstallError(
                "Verification failed; installation was not started"
                + (f": {', '.join(failures)}" if failures else "")
            )
        report = dict(report)
        report["output_sha256"] = hashlib.sha256(output.encode("utf-8")).hexdigest()
        report["output_streamed"] = bool(echo)
        return report


def verify_command(args: argparse.Namespace) -> dict[str, Any]:
    raw_profile = str(args.profile)
    profile = {"full": "release", "quick": "fast"}.get(raw_profile, raw_profile)
    if profile == "codex":
        harnesses = ("codex",)
    elif profile in {"standard", "release"} or profile == "omp" or bool(args.require_node):
        harnesses = dependency_tool.HARNESS_ORDER if profile in {"standard", "release"} else ("omp",)
    else:
        harnesses = ("generic",)
    if os.environ.get("BBK_TEST_ALLOW_MISSING_DEPENDENCIES") == "1":
        dependency_report: dict[str, Any] = {
            "schema": "bbk.install-dependency-report.v1",
            "status": "SKIPPED_TEST",
            "selected_harnesses": list(harnesses),
            "checks": [],
            "host_checks": [],
            "blocking_count": 0,
            "warning_count": 0,
            "network_accessed": False,
            "mutation_performed": False,
        }
    else:
        try:
            dependency_report = dependency_tool.check_dependencies(
                harnesses,
                include_test_dependencies=profile in {"fast", "standard", "release"},
                require_omp_node=profile in {"standard", "release", "omp"} or bool(args.require_node),
                check_hosts=False,
            )
        except dependency_tool.DependencyError as exc:
            raise InstallError(f"Dependency preflight could not be evaluated: {exc}") from exc
        if not args.json:
            print(dependency_tool.format_report(dependency_report), flush=True)
        if dependency_report.get("status") != "PASS":
            remediation = dependency_report.get("remediation_command")
            suffix = f" Run: {remediation}" if remediation else ""
            raise InstallError(f"Dependency preflight failed; verification was not started.{suffix}")
    result = run_verification_gate(
        failfast=bool(args.failfast),
        require_node=bool(args.require_node or profile in {"standard", "release", "omp"}),
        echo=not args.json,
        profile=raw_profile,
        jobs=int(args.test_jobs),
        test_mode=str(args.test_mode),
        timing_report=getattr(args, "timing_report", None),
        no_timing_report=bool(getattr(args, "no_timing_report", False)),
    )
    result["dependency_preflight"] = dependency_report
    return result


def _perform_install(
    args: argparse.Namespace,
    *,
    prepared_profiles: Sequence[PreparedProfile],
    verification: dict[str, Any] | None,
    progress: InstallProgress | None = None,
    profile_reuse: Mapping[str, Any] | None = None,
    projection_cache: ProjectionBundleCache | None = None,
) -> dict[str, Any]:
    codex, omp, claude, pi, generic = selected_harnesses(args)
    project = selected_project_root(args)
    root = data_root() if args.scope == "user" else project / ".bbk-kit"  # type: ignore[operator]
    mpath = manifest_path(args.scope, project, root)
    cache = projection_cache or ProjectionBundleCache.from_args(args)
    routing_path, projections, routing_meta = cache.get()

    backups = root / "backups" / stamp()
    records: list[dict[str, Any]] = []
    planned: dict[str, int] = {}
    common = {
        "force": args.force,
        "dry_run": args.dry_run,
        "backup_root": backups,
        "records": records,
        "planned": planned,
        "progress": progress,
    }
    package_root = install_package_copy(root, **common)
    effective_routing = root / "effective-model-routing.json"
    install_file(routing_path, effective_routing, **common)
    targets = installation_targets(scope=args.scope, project=project)
    omp_routing_state: Path | None = None
    if omp:
        omp_routing_state = root / "effective-omp-model-routing.json"
        install_bytes(
            omp_runtime_routing_state_bytes(routing_meta),
            omp_routing_state,
            source="generated:effective-omp-model-routing",
            **common,
        )

    registry_relative = REGISTRY_RELATIVE_PATH.as_posix()
    compiled_exclusions = compiled_skill_catalog_exclusions(ROOT)
    catalog_exclusions = {registry_relative, *compiled_exclusions}
    if codex or omp or pi or generic:
        assert targets["agent_skills"] is not None
        copy_tree(
            ROOT / "shared" / "skills",
            targets["agent_skills"],
            exclude=catalog_exclusions,
            **common,
        )
    controller_spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    shared_controller_host = "codex" if codex else ("pi" if pi else ("generic" if generic else None))
    if shared_controller_host is not None:
        assert targets["agent_skills"] is not None
        install_bytes(
            rendered_controller_skill(controller_spec, host=shared_controller_host).encode("utf-8"),
            targets["agent_skills"] / "bbk" / "SKILL.md",
            source=f"generated:{shared_controller_host}-controller-skill",
            **common,
        )
    routing_digest = routing_meta["model_routing_source_sha256"]
    if codex:
        assert targets["codex_agents"] is not None
        install_rendered_agents(
            projections["codex"],
            targets["codex_agents"],
            target="codex",
            routing_digest=routing_digest,
            **common,
        )
    if omp:
        assert targets["omp_agents"] is not None and targets["omp_extensions"] is not None
        install_rendered_agents(
            projections["omp"],
            targets["omp_agents"],
            target="omp",
            routing_digest=routing_digest,
            **common,
        )
        omp_extension = targets["omp_extensions"] / "bbk"
        for name in ["index.js", "package.json", "README.md"]:
            install_file(ROOT / "omp" / "extension" / name, omp_extension / name, **common)
        for name in OMP_EXTENSION_RUNTIME_FILES:
            install_file(ROOT / "tools" / name, omp_extension / name, **common)
        install_file(ROOT / "VERSION", omp_extension / "VERSION", **common)
        install_bytes(
            json_bytes(
                {
                    "schema": "bbk.omp-package-binding.v3",
                    "version": VERSION,
                    "path": json_path(package_root),
                    "package_root": json_path(package_root),
                    "scope": args.scope,
                    "project_root": json_path(project) if project else None,
                    "manifest_path": json_path(mpath),
                    "omp_agents": json_path(targets["omp_agents"]),
                    "state_path": json_path(omp_routing_state),
                }
            ),
            omp_extension / "bbk-package-root.json",
            source="generated:omp-package-root-binding",
            **common,
        )
        copy_tree(ROOT / "templates", omp_extension / "templates", **common)
        copy_tree(ROOT / "spec", omp_extension / "spec", **common)
        copy_tree(ROOT / "fixtures", omp_extension / "fixtures", **common)
    if claude:
        assert targets["claude_skills"] is not None and targets["claude_agents"] is not None
        copy_tree(
            ROOT / "shared" / "skills",
            targets["claude_skills"],
            exclude=catalog_exclusions,
            **common,
        )
        install_bytes(
            rendered_controller_skill(controller_spec, host="claude").encode("utf-8"),
            targets["claude_skills"] / "bbk" / "SKILL.md",
            source="generated:claude-controller-skill",
            **common,
        )
        install_rendered_agents(
            projections["claude"],
            targets["claude_agents"],
            target="claude",
            routing_digest=routing_digest,
            **common,
        )
    pi_manifest_path: Path | None = None
    if pi:
        assert targets["pi_agents"] is not None
        install_rendered_agents(
            projections["pi"],
            targets["pi_agents"],
            target="pi",
            routing_digest=routing_digest,
            **common,
        )
        pi_manifest_path = targets["pi_agents"].parent / "agent-manifest.json"
        install_bytes(
            generic_agent_manifest_bytes(routing_meta, target="pi"),
            pi_manifest_path,
            source=f"generated:pi-agent-manifest:{routing_digest}",
            **common,
        )
    generic_manifest_path: Path | None = None
    if generic:
        assert targets["generic_agents"] is not None
        install_rendered_agents(
            projections["generic"],
            targets["generic_agents"],
            target="generic",
            routing_digest=routing_digest,
            **common,
        )
        generic_manifest_path = targets["generic_agents"].parent / "agent-manifest.json"
        install_bytes(
            generic_agent_manifest_bytes(routing_meta, target="generic"),
            generic_manifest_path,
            source=f"generated:generic-agent-manifest:{routing_digest}",
            **common,
        )
    bbk_launcher_path: Path | None = None
    if targets["binaries"] is not None:
        name, content = launcher(package_root)
        bbk_launcher_path = targets["binaries"] / name
        install_bytes(
            content,
            bbk_launcher_path,
            source="generated:launcher",
            executable=True,
            **common,
        )

    bbk_cli_binding = {
        "launcher": json_path(bbk_launcher_path) if bbk_launcher_path else None,
        "python": json_path(Path(sys.executable).resolve()),
        "script": json_path(package_root / "tools" / "bbk.py"),
    }

    reusable = (profile_reuse or {}).get("reusable", {})
    installed_profiles: list[dict[str, Any]] = []
    for item in prepared_profiles:
        identity = _profile_identity(item.profile_id, item.version)
        reuse = reusable.get(identity) if isinstance(reusable, Mapping) else None
        if isinstance(reuse, Mapping):
            installed_profiles.append(
                install_reused_language_profile(item, reuse, common=common)
            )
        else:
            result = install_language_profile(
                item,
                root=root,
                targets=targets,
                codex=codex,
                omp=omp,
                claude=claude,
                pi=pi,
                generic=generic,
                common=common,
            )
            result["install_action"] = "installed"
            result["reused_file_count"] = 0
            installed_profiles.append(result)

    installed_package_roots = {
        f"{item.get('id')}@{item.get('version')}": str(item.get("package_root"))
        for item in installed_profiles
        if isinstance(item, Mapping)
        and isinstance(item.get("id"), str)
        and isinstance(item.get("version"), str)
        and isinstance(item.get("package_root"), str)
    }
    registry_json = registry_json_bytes(
        prepared_profiles,
        bbk_version=VERSION,
        bbk_cli=bbk_cli_binding,
        installed_package_roots=installed_package_roots,
    )
    registry_skill = registry_skill_bytes(
        prepared_profiles,
        bbk_version=VERSION,
        bbk_cli=bbk_cli_binding,
        installed_package_roots=installed_package_roots,
    )
    registry_digest = hashlib.sha256(registry_skill).hexdigest()
    effective_profiles = root / "effective-language-profiles.json"
    install_bytes(
        registry_json,
        effective_profiles,
        source="generated:effective-language-profiles",
        **common,
    )
    registry_paths: list[str] = []
    if codex or omp or pi or generic:
        assert targets["agent_skills"] is not None
        path = targets["agent_skills"].joinpath(*REGISTRY_RELATIVE_PATH.parts)
        install_bytes(
            registry_skill,
            path,
            source="generated:installed-profile-registry-skill",
            **common,
        )
        registry_paths.append(json_path(path))
    if claude:
        assert targets["claude_skills"] is not None
        path = targets["claude_skills"].joinpath(*REGISTRY_RELATIVE_PATH.parts)
        install_bytes(
            registry_skill,
            path,
            source="generated:installed-profile-registry-skill:claude",
            **common,
        )
        registry_paths.append(json_path(path))

    prior_codex_activation: Mapping[str, Any] | None = None
    if codex and args.scope == "project" and mpath.is_file():
        try:
            prior_manifest = json.loads(mpath.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InstallError(f"Cannot read existing project install manifest {mpath}: {exc}") from exc
        candidate_activation = prior_manifest.get("codex_project_activation") if isinstance(prior_manifest, Mapping) else None
        if isinstance(candidate_activation, Mapping):
            prior_codex_activation = candidate_activation
    codex_activation = (
        install_codex_activation(
            project,
            dry_run=bool(args.dry_run),
            backup_root=backups,
            prior=prior_codex_activation,
        )
        if codex and args.scope == "project" and project is not None
        else None
    )
    selected_harness_map = {"codex": codex, "omp": omp, "claude": claude, "pi": pi, "generic": generic}
    manifest = {
        "schema": "bbk.install-manifest.v1",
        "version": VERSION,
        "scope": args.scope,
        "project_root": json_path(project) if project else None,
        "package_root": json_path(package_root),
        "codex": codex,
        "omp": omp,
        "claude": claude,
        "pi": pi,
        "generic": generic,
        "pi_agent_manifest": json_path(pi_manifest_path) if pi_manifest_path else None,
        "generic_agent_manifest": json_path(generic_manifest_path) if generic_manifest_path else None,
        "codex_project_activation": codex_activation,
        "dry_run": args.dry_run,
        "verification": verification,
        "model_routing": model_routing_manifest_metadata(
            custom=args.model_routing is not None,
            source=routing_path,
            effective_copy=effective_routing,
            routing_meta=routing_meta,
        ),
        "compiled_procedures": {
            "schema": "bbk.installed-compiled-procedure-layout.v2",
            "registry_source": json_path(package_root / "spec" / "procedures" / "catalog.json"),
            "registry_revision": routing_meta.get("procedure_registry_revision"),
            "registry_sha256": routing_meta.get("procedure_registry_sha256"),
            "canonical_source_root": json_path(package_root / "shared" / "skills"),
            "catalog_projection_mode": "IDENTITY_AWARE_COMPILER_SELECTABLE_SOURCES",
            "physical_catalog_classes": routing_meta.get("physical_catalog_classes", {}),
            "suppressed_procedure_ids": sorted(globally_suppressed_procedures(ROOT)),
            "physically_indexed_procedure_ids": sorted(physically_indexed_procedures(ROOT)),
            "indexed_skill_roots": [
                json_path(targets["agent_skills"]) if targets.get("agent_skills") is not None and (codex or omp or pi or generic) else None,
                json_path(targets["claude_skills"]) if targets.get("claude_skills") is not None and claude else None,
            ],
            "source_retained_in_version_package": True,
        },
        "harness_prompt_compilation": {
            target: {
                "prompt_compiler_revision": routing_meta.get("procedure_registry_revision"),
                "role_projection_digest": hashlib.sha256(
                    json.dumps(
                        {
                            name: value.get("compiled_procedures", {}).get(target)
                            for name, value in sorted(routing_meta.get("agents", {}).items())
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest(),
                "controller_projection_digest": (
                    routing_meta.get("controllers", {}).get(target, {}).get("compiled_procedures", {}).get("compiled_prompt_sha256")
                ),
                "procedure_registry_revision": routing_meta.get("procedure_registry_revision"),
                "effective_catalog_digest": hashlib.sha256(
                    json.dumps(
                        {
                            name: value.get("effective_external_catalogs", {}).get(target)
                            for name, value in sorted(routing_meta.get("agents", {}).items())
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest(),
                "model_routing_digest": routing_meta.get("model_routing_source_sha256"),
                "adapter_digest": hashlib.sha256(target.encode("utf-8")).hexdigest(),
            }
            for target in HARNESS_ORDER
            if selected_harness_map[target]
        },
        "omp_runtime_routing": (
            {
                "schema": "bbk.omp-runtime-routing.v1",
                "active_profile": "installation-default",
                "source": "installation-default",
                "description": "Exact OMP routes selected when this BBK installation was created.",
                "state_path": json_path(omp_routing_state),
                "routes_sha256": hashlib.sha256(
                    json.dumps(
                        {
                            name: value["model_routing"]["omp"]
                            for name, value in sorted(routing_meta["agents"].items())
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest(),
                "changed_role_count": 0,
                "updated_at": None,
            }
            if omp_routing_state is not None
            else None
        ),
        "language_profiles": installed_profiles,
        "language_profile_layout_version": LANGUAGE_PROFILE_LAYOUT_VERSION,
        "language_profile_reuse": {
            key: value for key, value in (profile_reuse or {}).items() if key != "reusable"
        },
        "language_profile_source_mode": getattr(args, "language_profile_source_mode", "explicit"),
        "language_profile_registry": {
            "schema": "bbk.installed-profile-registry.v1",
            "skill": REGISTRY_SKILL_NAME,
            "effective_copy": json_path(effective_profiles),
            "skill_sha256": registry_digest,
            "skill_paths": registry_paths,
            "profile_count": len(installed_profiles),
            "bbk_cli": bbk_cli_binding,
        },
        "created_at": dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "files": records,
        "backup_root": json_path(backups),
    }
    if not args.dry_run:
        atomic_write(mpath, json_bytes(manifest), 0o600)
    manifest["manifest_path"] = json_path(mpath)
    return manifest


def validate_install_plan(manifest: Mapping[str, Any]) -> None:
    """Reject duplicate destination ownership before any installation write."""
    seen: dict[str, dict[str, Any]] = {}
    conflicts: list[str] = []
    for record in manifest.get("files", []):
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            raise InstallError("installer preflight produced an invalid file record")
        key = portable_path_key(Path(record["path"]))
        previous = seen.get(key)
        if previous is None:
            seen[key] = record
            continue
        conflicts.append(
            f"{record['path']}: {previous.get('source')} ({previous.get('sha256')}) "
            f"and {record.get('source')} ({record.get('sha256')})"
        )
    if conflicts:
        raise InstallError(
            "multiple package components claim the same installation destination:\n- "
            + "\n- ".join(conflicts)
        )


def _uninstall_args(
    args: argparse.Namespace,
    *,
    force: bool,
    dry_run: bool,
    reusable_successor_files: Mapping[str, Mapping[str, Any]] | None = None,
) -> argparse.Namespace:
    return argparse.Namespace(
        scope=args.scope,
        root=args.root,
        force=force,
        dry_run=dry_run,
        json=bool(getattr(args, "json", False)),
        reusable_successor_files=dict(reusable_successor_files or {}),
    )


def _is_language_profile_source(source: object) -> bool:
    value = str(source or "")
    return value.startswith("profile:") or value.startswith("generated:profile-")


def _backup_preserved_install_files(
    preserved: Sequence[Mapping[str, Any]],
    *,
    backup_root: Path,
) -> list[dict[str, str]]:
    backups: list[dict[str, str]] = []
    for index, item in enumerate(preserved, 1):
        raw_path = item.get("path")
        if not isinstance(raw_path, str):
            continue
        source = Path(raw_path)
        if not source.is_file():
            continue
        identity = hashlib.sha256(str(source).encode("utf-8")).hexdigest()[:12]
        destination = backup_root / f"{index:04d}-{identity}-{source.name}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        backups.append(
            {
                "source": json_path(source),
                "backup": json_path(destination),
                "sha256": sha256_file(destination),
            }
        )
    return backups


def clean_replace_existing_install(
    args: argparse.Namespace,
    *,
    existing: Mapping[str, Any],
    prepared_profiles: Sequence[PreparedProfile],
    verification: dict[str, Any] | None,
    progress_enabled: bool,
    projection_cache: ProjectionBundleCache | None = None,
) -> dict[str, Any]:
    """Preflight the successor, then conservatively remove the old install."""
    progress_note(progress_enabled, "==> Preflighting clean replacement against the existing installation...")
    replacement_args = copy(args)
    replacement_args.dry_run = True
    replacement_args.force = True
    replacement_plan = _perform_install(
        replacement_args,
        prepared_profiles=prepared_profiles,
        verification=verification,
        progress=InstallProgress(enabled=False),
        projection_cache=projection_cache,
    )
    validate_install_plan(replacement_plan)

    old_manifest = existing.get("manifest") if isinstance(existing.get("manifest"), Mapping) else {}
    old_owned = {
        portable_path_key(Path(item["path"]))
        for item in old_manifest.get("files", [])
        if isinstance(item, Mapping) and isinstance(item.get("path"), str)
    }
    reusable_successor_files: dict[str, dict[str, Any]] = {}
    for item in replacement_plan.get("files", []):
        if not isinstance(item, Mapping) or item.get("action") != "unchanged":
            continue
        raw_path = item.get("path")
        if not isinstance(raw_path, str):
            continue
        key = portable_path_key(Path(raw_path))
        if key not in old_owned:
            continue
        reusable_successor_files[key] = {
            "path": raw_path,
            "sha256": item.get("sha256"),
            "executable": item.get("executable"),
            "source": item.get("source"),
        }
    unowned_conflicts = []
    for item in replacement_plan.get("files", []):
        if not isinstance(item, Mapping) or item.get("action") != "replace":
            continue
        raw_path = item.get("path")
        if not isinstance(raw_path, str):
            continue
        destination = Path(raw_path)
        if destination.exists() and portable_path_key(destination) not in old_owned:
            unowned_conflicts.append(raw_path)
    if unowned_conflicts and not args.force:
        raise InstallError(
            "clean replacement found locally owned files at successor destinations; "
            "nothing was uninstalled. Re-run with --force to back up and replace them, "
            "or use --keep-existing and reconcile manually:\n- "
            + "\n- ".join(unowned_conflicts[:20])
        )

    preview = uninstall(
        _uninstall_args(
            args,
            force=False,
            dry_run=True,
            reusable_successor_files=reusable_successor_files,
        )
    )
    preserved = list(preview.get("preserved", []))
    non_regular = [
        item
        for item in preserved
        if isinstance(item.get("path"), str)
        and Path(str(item["path"])).exists()
        and not Path(str(item["path"])).is_file()
    ]
    if non_regular:
        paths = [str(item.get("path")) for item in non_regular[:20]]
        raise InstallError(
            "the existing installation contains a non-regular object at a manifest-owned path; "
            "nothing was uninstalled. Move or remove it manually before a clean replacement:\n- "
            + "\n- ".join(paths)
        )
    if preserved and not args.force:
        paths = [str(item.get("path")) for item in preserved[:20]]
        raise InstallError(
            "the existing installation has locally modified manifest-owned files; "
            "nothing was uninstalled. Re-run with --force to back them up before removal, "
            "or use --keep-existing:\n- "
            + "\n- ".join(paths)
        )

    backups: list[dict[str, str]] = []
    backup_root: Path | None = None
    if preserved:
        root = Path(existing["root"])
        backup_root = root / "backups" / f"{stamp()}-preinstall"
        backups = _backup_preserved_install_files(preserved, backup_root=backup_root)
        if len(backups) != len(preserved):
            raise InstallError("could not back up every modified manifest-owned file; nothing was uninstalled")

    removed = uninstall(
        _uninstall_args(
            args,
            force=bool(args.force),
            dry_run=False,
            reusable_successor_files=reusable_successor_files,
        )
    )
    reused = list(removed.get("reused", []))
    reused_profile_count = sum(
        1 for item in reused if _is_language_profile_source(item.get("source"))
    )
    progress_note(
        progress_enabled,
        f"<== Existing BBK {existing.get('version')} replaced: "
        f"{len(removed.get('removed', [])):,} files removed; "
        f"{len(reused):,} identical successor files reused "
        f"({reused_profile_count:,} language-profile files); "
        f"{len(backups):,} modified files backed up.",
    )
    return {
        "detected": True,
        "decision": "replace",
        "previous_version": existing.get("version"),
        "previous_manifest_path": json_path(Path(existing["manifest_path"])),
        "previous_harnesses": list(existing.get("harnesses", [])),
        "previous_file_count": existing.get("file_count"),
        "uninstalled": True,
        "removed_count": len(removed.get("removed", [])),
        "reused_identical_count": len(reused),
        "reused_language_profile_file_count": reused_profile_count,
        "reused_language_profile_sources": sorted({
            str(item.get("source"))
            for item in reused
            if _is_language_profile_source(item.get("source"))
        }),
        "reused_identical_sample": reused[:20],
        "modified_backup_count": len(backups),
        "modified_backup_root": json_path(backup_root) if backup_root else None,
        "modified_backups": backups,
    }


def selective_clean_replace_existing_install(
    args: argparse.Namespace,
    *,
    existing: Mapping[str, Any],
    verification: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Clean-replace one installed OMP or Codex surface without touching peers."""
    scope = replacement_scope(args, existing)
    selected = set(scope["selected"])
    preserved = set(scope["preserved"])
    if not preserved:
        raise InstallError("internal error: selective replacement requested without preserved harnesses")
    if len(selected) != 1 or not selected <= {"omp", "codex"}:
        raise InstallError(
            "A harness-scoped clean replacement currently supports exactly one of --omp or --codex. "
            "No files were removed. Select every installed harness for a full clean replacement, "
            "or run separate selective updates."
        )
    if not selected <= set(scope["installed"]):
        missing = sorted(selected - set(scope["installed"]))
        raise InstallError(
            f"Cannot clean-replace harnesses not owned by the existing installation: {missing}. "
            "Use --keep-existing for an additive reconciliation or perform a full replacement."
        )
    incompatible: list[str] = []
    if getattr(args, "model_routing", None):
        incompatible.append("--model-routing")
    if list(getattr(args, "language_profiles", None) or []):
        incompatible.append("--language-profiles")
    if list(getattr(args, "profile_id", None) or []):
        incompatible.append("--profile-id")
    if bool(getattr(args, "no_language_profiles", False)):
        incompatible.append("--no-language-profiles")
    if incompatible:
        raise InstallError(
            "Harness-scoped clean replacement preserves the installed shared routing and profile set; "
            f"these options require a full replacement: {', '.join(incompatible)}. No files were removed."
        )

    common = argparse.Namespace(
        scope=args.scope,
        root=args.root,
        verify=False,
        verification_failfast=False,
        force=bool(args.force),
        dry_run=bool(args.dry_run),
        json=bool(args.json),
        clean=True,
    )
    selected_name = next(iter(selected))
    try:
        if selected_name == "omp":
            import update_omp as selective_tool

            update_result = selective_tool.update_omp(common)
        else:
            import update_codex as selective_tool

            update_result = selective_tool.update_codex(common)
    except Exception as exc:
        # Import locally to avoid a top-level install/update import cycle. Both
        # selective tools expose user-facing typed errors, but a stable install
        # error is preferable to coupling this boundary to their class names.
        raise InstallError(f"{selected_name.upper()} harness-scoped clean replacement failed: {exc}") from exc

    selected_ordered = [name for name in HARNESS_ORDER if name in selected]
    preserved_ordered = [name for name in HARNESS_ORDER if name in preserved]
    preexisting = {
        "detected": True,
        "decision": "replace-selected",
        "previous_version": existing.get("version"),
        "previous_manifest_path": json_path(Path(existing["manifest_path"])),
        "previous_harnesses": list(existing.get("harnesses", [])),
        "previous_file_count": existing.get("file_count"),
        "selected_harnesses": selected_ordered,
        "preserved_harnesses": preserved_ordered,
        "selected_harnesses_replaced": not bool(args.dry_run),
        "full_install_uninstalled": False,
        "removed_stale_count": int(update_result.get("removed_stale_count") or 0),
        "verification": dict(verification) if verification else None,
    }
    if args.dry_run:
        return {
            "schema": "bbk.selective-clean-replacement-plan.v1",
            "status": "DRY-RUN",
            "scope": args.scope,
            "selected_harnesses": selected_ordered,
            "preserved_harnesses": preserved_ordered,
            "preexisting_install": preexisting,
            "update": update_result,
            "manifest_path": json_path(Path(existing["manifest_path"])),
        }

    mpath = Path(existing["manifest_path"])
    try:
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallError(
            f"Selective replacement completed but the unified manifest cannot be read: {mpath}: {exc}"
        ) from exc
    if not isinstance(manifest, dict) or manifest.get("schema") not in {"bbk.install-manifest.v1", "bbk.install-manifest.v2"}:
        raise InstallError(f"Selective replacement produced an unsupported manifest: {mpath}")
    manifest["preexisting_install"] = preexisting
    manifest["last_selective_clean_replacement"] = {
        "harness": selected_name,
        "from_version": existing.get("version"),
        "to_version": VERSION,
        "preserved_harnesses": preserved_ordered,
        "removed_stale_count": preexisting["removed_stale_count"],
    }
    if verification is not None:
        manifest["last_install_verification"] = dict(verification)
    atomic_write(mpath, json_bytes(manifest), 0o600)
    manifest["manifest_path"] = json_path(mpath)
    return manifest


def install(args: argparse.Namespace) -> dict[str, Any]:
    progress_enabled = not bool(args.json)
    verification_profile = (
        automatic_verification_profile(args)
        if str(args.verification_profile) == "auto"
        else str(args.verification_profile)
    )
    selected = selected_harness_names(args)
    if args.verify and verification_profile == "codex" and selected != {"codex"}:
        raise InstallError("the codex verification profile requires a Codex-only install selection")
    if args.verify and verification_profile == "omp" and selected != {"omp"}:
        raise InstallError("the omp verification profile requires an OMP-only install selection")
    dependency_report = run_dependency_preflight(
        args,
        profile=verification_profile,
        echo=progress_enabled,
    )
    existing = load_existing_install(args)
    existing_action = choose_existing_install_action(args, existing)
    replacement = replacement_scope(args, existing) if existing is not None else None
    if existing is not None and existing_action == "replace":
        validate_replacement_scope(replacement or {})
    existing_result: dict[str, Any] = {
        "detected": existing is not None,
        "decision": existing_action,
        "previous_version": existing.get("version") if existing else None,
        "previous_manifest_path": json_path(Path(existing["manifest_path"])) if existing else None,
        "previous_harnesses": list(existing.get("harnesses", [])) if existing else [],
        "previous_file_count": existing.get("file_count") if existing else 0,
        "uninstalled": False,
    }
    verification = None
    if args.verify:
        progress_note(progress_enabled, f"==> Running {verification_profile} BBK verification before installation...")
        _, omp_selected, _, _, _ = selected_harnesses(args)
        verification = run_verification_gate(
            failfast=bool(args.verification_failfast),
            require_node=bool(args.require_node or omp_selected),
            echo=not args.json,
            profile=verification_profile,
            jobs=int(args.test_jobs),
            test_mode=str(args.test_mode),
            timing_report=getattr(args, "timing_report", None),
            no_timing_report=bool(getattr(args, "no_timing_report", False)),
        )
        progress_note(progress_enabled, "<== Verification: PASS; installation preparation may proceed.")

    if existing is not None and existing_action == "replace" and replacement and replacement["kind"] == "harness":
        progress_note(
            progress_enabled,
            "==> Performing harness-scoped clean replacement; unselected harnesses will be preserved...",
        )
        result = selective_clean_replace_existing_install(
            args,
            existing=existing,
            verification=verification,
        )
        result["dependency_preflight"] = dependency_report
        # The selective updater has already written the canonical unified
        # install manifest. Do not serialize the user-facing result object over
        # that manifest; it contains summary-only fields and a manifest_path.
        progress_note(progress_enabled, "<== Harness-scoped clean replacement complete.")
        return result

    explicit_sources = list(args.language_profiles or [])
    selected_ids = list(args.profile_id or [])
    no_language_profiles = bool(getattr(args, "no_language_profiles", False))
    if no_language_profiles and explicit_sources:
        raise InstallError("--no-language-profiles cannot be combined with --language-profiles")
    if no_language_profiles and selected_ids:
        raise InstallError("--no-language-profiles cannot be combined with --profile-id")
    if no_language_profiles:
        sources: list[str] = []
        source_mode = "disabled"
    elif explicit_sources:
        sources = explicit_sources
        source_mode = "explicit"
    else:
        if not BUNDLED_PROFILES_PATH.is_dir():
            raise InstallError(
                f"Bundled language profiles are missing: {BUNDLED_PROFILES_PATH}; "
                "use --no-language-profiles for a core-only install"
            )
        sources = [str(BUNDLED_PROFILES_PATH)]
        source_mode = "bundled-default"
    args.language_profile_source_mode = source_mode
    progress_note(
        progress_enabled,
        f"==> Preparing language profiles ({source_mode}; {len(sources)} source(s))...",
    )

    with tempfile.TemporaryDirectory(prefix="bbk-language-profiles-") as raw_temp:
        try:
            prepared = prepare_profile_sources(
                sources,
                temp_root=Path(raw_temp),
                selected_ids=selected_ids or None,
                progress=(
                    (lambda message: progress_note(True, message))
                    if progress_enabled
                    else None
                ),
            ) if sources else []
        except ProfileInstallError as exc:
            raise InstallError(f"Language-profile preparation failed: {exc}") from exc
        profile_names = ", ".join(f"{item.profile_id}@{item.version}" for item in prepared) or "none"
        progress_note(
            progress_enabled,
            f"<== Language profiles verified: {len(prepared)} ({profile_names})",
        )
        profile_reuse = language_profile_reuse_plan(
            existing if existing_action != "replace" else None,
            prepared,
            args=args,
        )
        if profile_reuse.get("reused_profile_count"):
            progress_note(
                progress_enabled,
                "<== Reusing "
                f"{profile_reuse['reused_profile_count']} unchanged language profiles "
                f"({profile_reuse['reused_file_count']:,} manifest-owned files).",
            )
        projection_cache = ProjectionBundleCache.from_args(args)
        if args.dry_run:
            planning_args = copy(args)
            if existing_action == "replace":
                # Model the successor after the selected clean removal without
                # mutating the existing installation during a dry run.
                planning_args.force = True
            dry_progress = InstallProgress(enabled=progress_enabled)
            dry_progress.start("Building dry-run installation plan")
            try:
                plan = _perform_install(
                    planning_args,
                    prepared_profiles=prepared,
                    verification=verification,
                    progress=dry_progress,
                    profile_reuse=profile_reuse,
                    projection_cache=projection_cache,
                )
                validate_install_plan(plan)
            except Exception:
                dry_progress.finish(status="FAIL")
                raise
            dry_progress.finish()
            plan["preexisting_install"] = existing_result
            plan["dependency_preflight"] = dependency_report
            return plan

        if existing is not None and existing_action == "replace":
            existing_result = clean_replace_existing_install(
                args,
                existing=existing,
                prepared_profiles=prepared,
                verification=verification,
                progress_enabled=progress_enabled,
                projection_cache=projection_cache,
            )
        elif existing is not None:
            progress_note(
                progress_enabled,
                f"Existing BBK {existing.get('version')} retained; installing in reconciliation mode.",
            )

        # Perform a complete no-write preflight before the first destination is
        # created. This catches divergence, invalid destinations, mode conflicts,
        # and cross-component collisions before a core/profile install can be partial.
        preflight_args = copy(args)
        preflight_args.dry_run = True
        preflight_progress = InstallProgress(enabled=progress_enabled)
        preflight_progress.start("Preflighting the complete installation plan")
        try:
            plan = _perform_install(
                preflight_args,
                prepared_profiles=prepared,
                verification=verification,
                progress=preflight_progress,
                profile_reuse=profile_reuse,
                projection_cache=projection_cache,
            )
            validate_install_plan(plan)
        except Exception:
            preflight_progress.finish(status="FAIL")
            raise
        preflight_progress.finish()

        install_progress = InstallProgress(enabled=progress_enabled)
        install_progress.start(
            "Writing manifest-owned installation files",
            total=len(plan.get("files", [])),
        )
        try:
            result = _perform_install(
                args,
                prepared_profiles=prepared,
                verification=verification,
                progress=install_progress,
                profile_reuse=profile_reuse,
                projection_cache=projection_cache,
            )
            validate_install_plan(result)
        except Exception:
            install_progress.finish(status="FAIL")
            raise
        install_progress.finish()
        actions: dict[str, int] = {}
        for item in plan.get("files", []):
            action = str(item.get("action"))
            actions[action] = actions.get(action, 0) + 1
        result["preflight"] = {
            "status": "PASS",
            "file_count": len(plan.get("files", [])),
            "actions": actions,
            "language_profile_count": len(plan.get("language_profiles", [])),
            "language_profile_source_mode": source_mode,
        }
        result["preexisting_install"] = existing_result
        result["dependency_preflight"] = dependency_report
        project, root, final_manifest_path = install_scope_paths(args)
        progress_note(progress_enabled, "==> Finalizing the unified installation manifest...")
        atomic_write(final_manifest_path, json_bytes({
            key: value for key, value in result.items() if key != "manifest_path"
        }), 0o600)
        progress_note(
            progress_enabled,
            f"<== Installation complete: {len(result.get('files', [])):,} manifest-owned files.",
        )
        return result


def status(args: argparse.Namespace) -> dict[str, Any]:
    project = selected_project_root(args)
    root = data_root() if args.scope == "user" else project / ".bbk-kit"  # type: ignore[operator]
    mpath = manifest_path(args.scope, project, root)
    result: dict[str, Any] = {
        "schema": "bbk.install-status.v1",
        "source_package": json_path(ROOT),
        "source_version": VERSION,
        "scope": args.scope,
        "data_root": json_path(root),
        "manifest_path": json_path(mpath),
        "installed": mpath.exists(),
    }
    if not mpath.exists():
        return result
    try:
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        result["manifest_error"] = str(exc)
        return result
    files = []
    for item in manifest.get("files", []):
        path = Path(item["path"])
        if not path.exists():
            state, current = "missing", None
        elif not path.is_file():
            state, current = "not-file", None
        else:
            current = sha256_file(path)
            if current != item.get("sha256"):
                state = "modified"
            elif os.name != "nt" and "executable" in item and (
                bool(path.stat().st_mode & 0o111) != bool(item.get("executable"))
            ):
                state = "mode-mismatch"
            else:
                state = "current"
        expected_executable = item.get("executable") if "executable" in item else None
        current_executable = (
            bool(path.stat().st_mode & 0o111)
            if os.name != "nt" and path.exists() and path.is_file()
            else None
        )
        files.append(
            {
                "path": json_path(path),
                "state": state,
                "expected": item.get("sha256"),
                "current": current,
                "expected_executable": expected_executable,
                "current_executable": current_executable,
            }
        )
    result.update(
        {
            "installed_version": manifest.get("version"),
            "harnesses": {
                "codex": manifest.get("codex"),
                "omp": manifest.get("omp"),
                "claude": manifest.get("claude"),
                "pi": manifest.get("pi"),
                "generic": manifest.get("generic"),
            },
            "verification": manifest.get("verification"),
            "model_routing": manifest.get("model_routing"),
            "omp_runtime_routing": manifest.get("omp_runtime_routing"),
            "language_profiles": manifest.get("language_profiles", []),
            "language_profile_source_mode": manifest.get("language_profile_source_mode"),
            "language_profile_registry": manifest.get("language_profile_registry"),
            "files": files,
            "summary": {
                state: sum(1 for item in files if item["state"] == state)
                for state in {item["state"] for item in files}
            },
        }
    )
    return result


def uninstall(args: argparse.Namespace) -> dict[str, Any]:
    """Plan, then conservatively remove manifest-owned files.

    Clean replacement may provide exact successor records. Files whose current
    bytes and executable mode already equal the successor are retained in place
    and adopted by the successor manifest instead of being deleted and copied
    again. The complete plan is computed before any mutation, preserving the
    existing conservative behavior for locally modified or non-regular paths.
    """
    project = selected_project_root(args)
    root = data_root() if args.scope == "user" else project / ".bbk-kit"  # type: ignore[operator]
    mpath = manifest_path(args.scope, project, root)
    if not mpath.exists():
        raise InstallError(f"No BBK install manifest found: {mpath}")
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    reusable_raw = getattr(args, "reusable_successor_files", {}) or {}
    reusable = {
        str(key): dict(value)
        for key, value in reusable_raw.items()
        if isinstance(key, str) and isinstance(value, Mapping)
    }

    removals: list[Path] = []
    removed: list[str] = []
    preserved: list[dict[str, Any]] = []
    reused: list[dict[str, Any]] = []
    for item in reversed(manifest.get("files", [])):
        path = Path(item["path"])
        if not path.exists():
            continue
        if not path.is_file():
            preserved.append({"path": json_path(path), "reason": "not a regular file"})
            continue
        current = sha256_file(path)
        current_executable = (bool(path.stat().st_mode & 0o111) if os.name != "nt" else None)
        key = portable_path_key(path)
        successor = reusable.get(key)
        if successor is not None:
            expected_digest = successor.get("sha256")
            expected_executable = successor.get("executable")
            successor_mode_matches = (
                os.name == "nt"
                or expected_executable is None
                or current_executable == bool(expected_executable)
            )
            if current == expected_digest and successor_mode_matches:
                reused.append(
                    {
                        "path": json_path(path),
                        "sha256": current,
                        "source": successor.get("source"),
                        "reason": "identical successor file reused in place",
                        "executable": expected_executable,
                    }
                )
                continue

        mode_modified = (
            os.name != "nt"
            and "executable" in item
            and current_executable != bool(item.get("executable"))
        )
        if (current != item.get("sha256") or mode_modified) and not args.force:
            preserved.append(
                {
                    "path": json_path(path),
                    "reason": "modified since install",
                    "expected": item.get("sha256"),
                    "current": current,
                    "expected_executable": item.get("executable"),
                    "current_executable": current_executable,
                }
            )
            continue
        removals.append(path)
        removed.append(json_path(path))

    activation_result: dict[str, Any] | None = None
    activation = manifest.get("codex_project_activation")
    if isinstance(activation, Mapping) and isinstance(activation.get("path"), str):
        activation_path = Path(str(activation["path"]))
        activation_result = {
            "path": json_path(activation_path),
            "action": "missing",
        }
        if activation_path.exists() and not activation_path.is_file():
            activation_result["action"] = "preserved"
            activation_result["reason"] = "not a regular file"
        elif activation_path.is_file():
            current = activation_path.read_bytes()
            try:
                span = _managed_activation_span(current)
            except InstallError as exc:
                span = None
                activation_result["reason"] = str(exc)
            exact_block = span is not None and hashlib.sha256(current[slice(*span)]).hexdigest() == activation.get("block_sha256")
            if not exact_block:
                activation_result["action"] = "preserved"
                activation_result.setdefault("reason", "managed BBK activation block differs from the manifest")
            elif hashlib.sha256(current).hexdigest() == activation.get("installed_file_sha256"):
                if activation.get("created_file"):
                    activation_result["action"] = "remove-file"
                    if not args.dry_run:
                        activation_path.unlink()
                elif isinstance(activation.get("original_backup"), str):
                    original_backup = Path(str(activation["original_backup"]))
                    if not original_backup.is_file() or sha256_file(original_backup) != activation.get("original_sha256"):
                        activation_result["action"] = "preserved"
                        activation_result["reason"] = "original AGENTS.md backup is missing or differs"
                    else:
                        activation_result["action"] = "restore-original"
                        if not args.dry_run:
                            atomic_write(activation_path, original_backup.read_bytes(), 0o644)
                else:
                    activation_result["action"] = "remove-block"
                    if not args.dry_run:
                        atomic_write(activation_path, current[: span[0]] + current[span[1] :], 0o644)
            else:
                activation_result["action"] = "remove-block"
                if not args.dry_run:
                    atomic_write(activation_path, current[: span[0]] + current[span[1] :], 0o644)

    if not args.dry_run:
        for path in removals:
            path.unlink()
        mpath.unlink(missing_ok=True)
        stop_dirs = {
            path.resolve()
            for path in (user_home(), project, root.parent)
            if path is not None
        }
        for raw in sorted({str(path.parent) for path in removals}, key=len, reverse=True):
            directory = Path(raw).resolve()
            while directory.exists() and directory.is_dir():
                if directory in stop_dirs or directory == Path(directory.anchor):
                    break
                try:
                    directory.rmdir()
                except OSError:
                    break
                directory = directory.parent
    return {
        "schema": "bbk.uninstall-result.v1",
        "scope": args.scope,
        "dry_run": args.dry_run,
        "removed": removed,
        "preserved": preserved,
        "reused": reused,
        "codex_project_activation": activation_result,
        "manifest_path": json_path(mpath),
    }


def human(value: dict[str, Any]) -> str:
    schema = value.get("schema")
    if schema == "bbk.verification-report.v1":
        return (
            f"BBK verification: {value.get('status')}\n"
            f"Checks: {value.get('checks_run')}/{value.get('checks_expected')}\n"
            f"Exit code: {value.get('exit_code')}"
        )
    if schema == "bbk.selective-clean-replacement-plan.v1":
        update = value.get("update") or {}
        return (
            "BBK harness-scoped clean replacement: DRY-RUN\n"
            f"Selected: {', '.join(value.get('selected_harnesses') or []) or 'none'}\n"
            f"Preserved: {', '.join(value.get('preserved_harnesses') or []) or 'none'}\n"
            f"Stale files to remove: {update.get('removed_stale_count', 0)}\n"
            f"Manifest: {value.get('manifest_path')}"
        )
    if schema in {"bbk.install-manifest.v1", "bbk.install-manifest.v2"}:
        actions: dict[str, int] = {}
        for item in value["files"]:
            actions[item["action"]] = actions.get(item["action"], 0) + 1
        routing = value.get("model_routing", {})
        routing_kind = "custom" if routing.get("custom") else "packaged default"
        profiles = value.get("language_profiles", [])
        profile_text = ", ".join(f"{item['id']}@{item['version']}" for item in profiles) or "none"
        verification_text = "PASS" if value.get("verification") else "not requested"
        return (
            f"BBK install {'dry run' if value['dry_run'] else 'complete'}\n"
            f"Scope: {value['scope']}\n"
            f"Verification: {verification_text}\n"
            f"Harnesses: Codex={value['codex']} OMP={value['omp']} Claude={value['claude']} Pi={value.get('pi')} Generic={value['generic']}\n"
            f"Model routing: {routing_kind} — {routing.get('source')} ({routing.get('sha256')})\n"
            f"Language profiles: {profile_text} ({value.get('language_profile_source_mode', 'unknown')})\n"
            f"Files: {actions}\n"
            f"{'Planned manifest' if value['dry_run'] else 'Manifest'}: {value['manifest_path']}"
        )
    if schema == "bbk.install-status.v1":
        routing = value.get("model_routing") or {}
        routing_line = (
            f"\nModel routing: {routing.get('source')} ({routing.get('sha256')})"
            if routing else ""
        )
        omp_runtime = value.get("omp_runtime_routing") or {}
        omp_runtime_line = (
            f"\nOMP runtime routing: {omp_runtime.get('active_profile')} ({omp_runtime.get('routes_sha256')})"
            if omp_runtime else ""
        )
        profiles = value.get("language_profiles") or []
        profile_line = (
            "\nLanguage profiles: "
            + (", ".join(f"{item.get('id')}@{item.get('version')}" for item in profiles) or "none")
            + f" ({value.get('language_profile_source_mode') or 'unknown'})"
        )
        return (
            f"BBK source {value['source_version']}\nScope: {value['scope']}\n"
            f"Installed: {value['installed']}\nFiles: {value.get('summary', {})}"
            f"{routing_line}{omp_runtime_line}{profile_line}\nManifest: {value['manifest_path']}"
        )
    if schema == "bbk.uninstall-result.v1":
        return (
            f"BBK uninstall {'dry run' if value['dry_run'] else 'complete'}\n"
            f"Removed: {len(value['removed'])}\nPreserved: {len(value['preserved'])}"
        )
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)


def add_install_selection_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--scope", choices=["user", "project"], default="user")
    parser.add_argument("--root")
    parser.add_argument("--codex", action="store_true")
    parser.add_argument("--omp", action="store_true")
    parser.add_argument("--claude", action="store_true")
    parser.add_argument("--pi", action="store_true")
    parser.add_argument("--generic", action="store_true")
    parser.add_argument(
        "--model-routing",
        help="external bbk.model-routing.v2 JSON (legacy v1 accepted) used to render installed agents without modifying the package",
    )
    parser.add_argument(
        "--language-profiles",
        "--profiles",
        dest="language_profiles",
        action="append",
        metavar="PATH",
        help="explicit profile ZIP, extracted root/tree/repository, or bundle replacing the bundled source for this run; repeat as needed",
    )
    parser.add_argument(
        "--profile-id",
        action="append",
        metavar="ID",
        help="install only this profile id; repeat as needed; defaults to every bundled profile",
    )
    parser.add_argument(
        "--no-language-profiles",
        action="store_true",
        help="install BBK core only instead of the bundled language profiles",
    )
    existing = parser.add_mutually_exclusive_group()
    existing.add_argument(
        "--uninstall-existing",
        action="store_true",
        help="clean-replace selected installed OMP/Codex harnesses while preserving unselected harnesses; selecting every installed harness performs a full replacement",
    )
    existing.add_argument(
        "--keep-existing",
        action="store_true",
        help="do not offer clean replacement; reconcile the new install against the existing files",
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    verify = sub.add_parser("verify", help="run BBK verification checks in canonical order")
    verify.add_argument("--failfast", action="store_true")
    verify.add_argument("--require-node", action="store_true")
    verify.add_argument(
        "--profile",
        choices=["fast", "standard", "release", "full", "quick", "omp", "codex"],
        default="standard",
    )
    verify.add_argument(
        "--test-mode", choices=["auto", "pooled", "batch", "isolated"], default="auto"
    )
    verify.add_argument("--test-jobs", type=int, default=0)
    verify.add_argument("--timing-report")
    verify.add_argument("--no-timing-report", action="store_true")
    verify.set_defaults(func=verify_command)

    installer = sub.add_parser("install", help="install BBK and optional language profiles")
    add_install_selection_flags(installer)
    installer.add_argument(
        "--verify",
        action="store_true",
        help="run the selected verification profile first and install only on PASS",
    )
    installer.add_argument(
        "--verification-profile",
        choices=["auto", "fast", "standard", "release", "omp", "codex"],
        default="auto",
        help="with --verify, select a profile; auto uses the smallest host-aware profile",
    )
    installer.add_argument(
        "--test-mode", choices=["auto", "pooled", "batch", "isolated"], default="auto"
    )
    installer.add_argument("--test-jobs", type=int, default=0)
    installer.add_argument("--timing-report")
    installer.add_argument("--no-timing-report", action="store_true")
    installer.add_argument(
        "--verification-failfast",
        action="store_true",
        help="with --verify, stop after the first non-trust-gate verification failure",
    )
    installer.add_argument(
        "--require-node",
        action="store_true",
        help="with --verify, require Node.js for OMP JavaScript syntax validation",
    )
    installer.set_defaults(func=install)

    status_parser = sub.add_parser("status", help="inspect an installation and all manifest-owned files")
    status_parser.add_argument("--scope", choices=["user", "project"], default="user")
    status_parser.add_argument("--root")
    status_parser.set_defaults(func=status)

    remover = sub.add_parser("uninstall", help="remove manifest-owned files conservatively")
    remover.add_argument("--scope", choices=["user", "project"], default="user")
    remover.add_argument("--root")
    remover.add_argument("--force", action="store_true")
    remover.add_argument("--dry-run", action="store_true")
    remover.set_defaults(func=uninstall)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    _configure_standard_stream(sys.stdout)
    _configure_standard_stream(sys.stderr)
    normalized = list(sys.argv[1:] if argv is None else argv)
    if "--json" in normalized and normalized and normalized[0] != "--json":
        normalized.remove("--json")
        normalized.insert(0, "--json")
    args = build_parser().parse_args(normalized)
    if getattr(args, "test_jobs", 0) < 0:
        build_parser().error("--test-jobs must be zero or positive")
    if getattr(args, "timing_report", None) and getattr(args, "no_timing_report", False):
        build_parser().error("--timing-report and --no-timing-report are mutually exclusive")
    try:
        value = args.func(args)
    except InstallError as exc:
        if args.json:
            print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"bbk install: error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) if args.json else human(value))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
