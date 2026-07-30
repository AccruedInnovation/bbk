#!/usr/bin/env python3
"""Cautious BBK installer with verification, model routing, and language profiles."""
from __future__ import annotations

import argparse
import datetime as dt
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
from typing import Any, Iterable, Mapping, Sequence

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from generate_agents import MODEL_ROUTING_PATH, rendered_projections
from model_routing import ModelRoutingError
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


class InstallError(RuntimeError):
    pass


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


def user_home() -> Path:
    """Return the installer home before falling back to ``Path.home()``.

    ``BBK_HOME`` and ``HOME`` remain explicit test/automation overrides on
    every host, including native Windows.
    """
    for name in ("BBK_HOME", "HOME"):
        if value := os.environ.get(name):
            return Path(value).expanduser().resolve()
    return Path.home().resolve()


def data_root() -> Path:
    if value := os.environ.get("BBK_INSTALL_ROOT"):
        return Path(value).expanduser().resolve()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(user_home() / "AppData" / "Local")
        return Path(base) / "BBK"
    if sys.platform == "darwin":
        return user_home() / "Library" / "Application Support" / "BBK"
    base = os.environ.get("XDG_DATA_HOME")
    return (Path(base).expanduser() if base else user_home() / ".local" / "share") / "bbk"


def bin_dir() -> Path:
    if value := os.environ.get("BBK_BIN_DIR"):
        return Path(value).expanduser().resolve()
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
        key = os.path.normcase(os.path.abspath(os.fspath(destination))).replace("\\", "/")
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
        install_bytes(
            data,
            destination / filename,
            source=f"generated:{target}-agent:{routing_digest}:{filename}",
            **kwargs,
        )


def generic_agent_manifest_bytes(metadata: Mapping[str, Any]) -> bytes:
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
            "spawns": list(value.get("spawns") or []),
            "may_mutate": bool(value.get("may_mutate")),
            "model_profile": value.get("model_profile"),
            "model_routing": value.get("model_routing"),
            "file": files.get("generic") if isinstance(files, Mapping) else None,
        }
    return json_bytes(
        {
            "schema": "bbk.installed-generic-agent-manifest.v1",
            "package_version": metadata.get("package_version"),
            "projection_source_sha256": metadata.get("source_sha256"),
            "role_source_sha256": metadata.get("role_source_sha256"),
            "model_routing_source_sha256": metadata.get("model_routing_source_sha256"),
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
            f'@echo off\r\nif defined BBK_PYTHON ("%BBK_PYTHON%" "{script}" %*) else (py -3 "{script}" %*)\r\n'.encode(),
        )
    return "bbk", f'#!/bin/sh\nexec "${{BBK_PYTHON:-python3}}" {json.dumps(str(script))} "$@"\n'.encode()


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
            f'@echo off\r\nif defined BBK_PYTHON ("%BBK_PYTHON%" "{script}" %*) else (py -3 "{script}" %*)\r\n'.encode(),
        )
    return command, f'#!/bin/sh\nexec "${{BBK_PYTHON:-python3}}" {json.dumps(str(script))} "$@"\n'.encode()


def manifest_path(scope: str, project: Path | None, root: Path) -> Path:
    return root / "install-manifest.json" if scope == "user" else project / ".bbk-kit-install.json"  # type: ignore[operator]


def selected_harnesses(args: argparse.Namespace) -> tuple[bool, bool, bool, bool]:
    codex, omp, claude, generic = bool(args.codex), bool(args.omp), bool(args.claude), bool(args.generic)
    if not (codex or omp or claude or generic):
        codex = omp = claude = generic = True
    return codex, omp, claude, generic


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
        if codex or omp or generic:
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


def run_verification_gate(
    *,
    failfast: bool,
    require_node: bool,
    echo: bool,
) -> dict[str, Any]:
    """Run verification in a child process while streaming human progress."""
    with tempfile.TemporaryDirectory(prefix="bbk-verification-report-") as raw_temp:
        report_path = Path(raw_temp) / "verification.json"
        command = [
            sys.executable,
            str(ROOT / "tools" / "verify_all.py"),
            "--report-file",
            str(report_path),
        ]
        if failfast:
            command.append("--failfast")
        if require_node:
            command.append("--require-node")
        try:
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            raise InstallError(f"Verification runner could not start: {exc}") from exc

        chunks: list[str] = []
        assert process.stdout is not None
        for line in process.stdout:
            chunks.append(line)
            if echo:
                sys.stdout.write(line)
                sys.stdout.flush()
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
    return run_verification_gate(
        failfast=bool(args.failfast),
        require_node=bool(args.require_node),
        echo=not args.json,
    )


def _perform_install(
    args: argparse.Namespace,
    *,
    prepared_profiles: Sequence[PreparedProfile],
    verification: dict[str, Any] | None,
    progress: InstallProgress | None = None,
) -> dict[str, Any]:
    codex, omp, claude, generic = selected_harnesses(args)
    project = (
        Path(args.root).expanduser().resolve()
        if args.root
        else (Path.cwd().resolve() if args.scope == "project" else None)
    )
    root = data_root() if args.scope == "user" else project / ".bbk-kit"  # type: ignore[operator]
    mpath = manifest_path(args.scope, project, root)
    routing_path = (
        Path(args.model_routing).expanduser().resolve()
        if args.model_routing
        else MODEL_ROUTING_PATH.resolve()
    )
    try:
        projections, routing_meta = rendered_projections(routing_path)
    except (OSError, json.JSONDecodeError, ModelRoutingError, ValueError) as exc:
        raise InstallError(f"Invalid model-routing policy {routing_path}: {exc}") from exc

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
    if codex or omp or generic:
        assert targets["agent_skills"] is not None
        copy_tree(
            ROOT / "shared" / "skills",
            targets["agent_skills"],
            exclude={registry_relative},
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
        for name in [
            "bbk.py",
            "contracts.py",
            "state_effect.py",
            "review_assurance.py",
            "verify_package.py",
            "omp_model_routing.py",
        ]:
            install_file(ROOT / "tools" / name, omp_extension / name, **common)
        install_file(ROOT / "VERSION", omp_extension / "VERSION", **common)
        install_bytes(
            json_bytes(
                {
                    "schema": "bbk.omp-package-binding.v2",
                    "version": VERSION,
                    "path": json_path(package_root),
                    "package_root": json_path(package_root),
                    "scope": args.scope,
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
            exclude={registry_relative},
            **common,
        )
        install_rendered_agents(
            projections["claude"],
            targets["claude_agents"],
            target="claude",
            routing_digest=routing_digest,
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
            generic_agent_manifest_bytes(routing_meta),
            generic_manifest_path,
            source=f"generated:generic-agent-manifest:{routing_digest}",
            **common,
        )
    if targets["binaries"] is not None:
        name, content = launcher(package_root)
        install_bytes(
            content,
            targets["binaries"] / name,
            source="generated:launcher",
            executable=True,
            **common,
        )

    installed_profiles = [
        install_language_profile(
            item,
            root=root,
            targets=targets,
            codex=codex,
            omp=omp,
            claude=claude,
            generic=generic,
            common=common,
        )
        for item in prepared_profiles
    ]

    registry_json = registry_json_bytes(prepared_profiles, bbk_version=VERSION)
    registry_skill = registry_skill_bytes(prepared_profiles, bbk_version=VERSION)
    registry_digest = hashlib.sha256(registry_skill).hexdigest()
    effective_profiles = root / "effective-language-profiles.json"
    install_bytes(
        registry_json,
        effective_profiles,
        source="generated:effective-language-profiles",
        **common,
    )
    registry_paths: list[str] = []
    if codex or omp or generic:
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

    manifest = {
        "schema": "bbk.install-manifest.v1",
        "version": VERSION,
        "scope": args.scope,
        "project_root": json_path(project) if project else None,
        "package_root": json_path(package_root),
        "codex": codex,
        "omp": omp,
        "claude": claude,
        "generic": generic,
        "generic_agent_manifest": json_path(generic_manifest_path) if generic_manifest_path else None,
        "dry_run": args.dry_run,
        "verification": verification,
        "model_routing": {
            "custom": args.model_routing is not None,
            "source": json_path(routing_path),
            "effective_copy": json_path(effective_routing),
            "sha256": routing_meta["model_routing_source_sha256"],
            "projection_source_sha256": routing_meta["source_sha256"],
            "profile_count": routing_meta["model_profile_count"],
            "role_profile_counts": routing_meta["role_profile_counts"],
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
        "language_profile_source_mode": getattr(args, "language_profile_source_mode", "explicit"),
        "language_profile_registry": {
            "schema": "bbk.installed-profile-registry.v1",
            "skill": REGISTRY_SKILL_NAME,
            "effective_copy": json_path(effective_profiles),
            "skill_sha256": registry_digest,
            "skill_paths": registry_paths,
            "profile_count": len(installed_profiles),
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
        key = record["path"].replace("\\", "/").casefold()
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


def install(args: argparse.Namespace) -> dict[str, Any]:
    progress_enabled = not bool(args.json)
    verification = None
    if args.verify:
        progress_note(progress_enabled, "==> Running complete BBK verification before installation...")
        _, omp_selected, _, _ = selected_harnesses(args)
        verification = run_verification_gate(
            failfast=bool(args.verification_failfast),
            require_node=bool(args.require_node or omp_selected),
            echo=not args.json,
        )
        progress_note(progress_enabled, "<== Verification: PASS; installation preparation may proceed.")

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
        sibling_profiles = ROOT.parent / "bbk-language-profiles"
        if BUNDLED_PROFILES_PATH.is_dir():
            sources = [str(BUNDLED_PROFILES_PATH)]
            source_mode = "bundled-default"
        elif (sibling_profiles / "REPOSITORY-MANIFEST.json").is_file() or (sibling_profiles / "packages").is_dir():
            sources = [str(sibling_profiles)]
            source_mode = "sibling-default"
        else:
            raise InstallError(
                "No default language-profile source is available. "
                f"Expected bundled profiles at {BUNDLED_PROFILES_PATH} or a sibling repository at {sibling_profiles}; "
                "use --language-profiles PATH or --no-language-profiles."
            )
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
        if args.dry_run:
            dry_progress = InstallProgress(enabled=progress_enabled)
            dry_progress.start("Building dry-run installation plan")
            try:
                plan = _perform_install(
                    args,
                    prepared_profiles=prepared,
                    verification=verification,
                    progress=dry_progress,
                )
                validate_install_plan(plan)
            except Exception:
                dry_progress.finish(status="FAIL")
                raise
            dry_progress.finish()
            return plan

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
        project = (
            Path(args.root).expanduser().resolve()
            if args.root
            else (Path.cwd().resolve() if args.scope == "project" else None)
        )
        root = data_root() if args.scope == "user" else project / ".bbk-kit"  # type: ignore[operator]
        progress_note(progress_enabled, "==> Finalizing the unified installation manifest...")
        atomic_write(manifest_path(args.scope, project, root), json_bytes({
            key: value for key, value in result.items() if key != "manifest_path"
        }), 0o600)
        progress_note(
            progress_enabled,
            f"<== Installation complete: {len(result.get('files', [])):,} manifest-owned files.",
        )
        return result


def status(args: argparse.Namespace) -> dict[str, Any]:
    project = (
        Path(args.root).expanduser().resolve()
        if args.root
        else (Path.cwd().resolve() if args.scope == "project" else None)
    )
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
    project = (
        Path(args.root).expanduser().resolve()
        if args.root
        else (Path.cwd().resolve() if args.scope == "project" else None)
    )
    root = data_root() if args.scope == "user" else project / ".bbk-kit"  # type: ignore[operator]
    mpath = manifest_path(args.scope, project, root)
    if not mpath.exists():
        raise InstallError(f"No BBK install manifest found: {mpath}")
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    removed: list[str] = []
    preserved: list[dict[str, Any]] = []
    for item in reversed(manifest.get("files", [])):
        path = Path(item["path"])
        if not path.exists():
            continue
        if not path.is_file():
            preserved.append({"path": json_path(path), "reason": "not a regular file"})
            continue
        current = sha256_file(path)
        current_executable = (bool(path.stat().st_mode & 0o111) if os.name != "nt" else None)
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
        if not args.dry_run:
            path.unlink()
        removed.append(json_path(path))
    if not args.dry_run:
        mpath.unlink(missing_ok=True)
        stop_dirs = {
            path.resolve()
            for path in (user_home(), project, root.parent)
            if path is not None
        }
        for raw in sorted({str(Path(path).parent) for path in removed}, key=len, reverse=True):
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
    if schema == "bbk.install-manifest.v1":
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
            f"Harnesses: Codex={value['codex']} OMP={value['omp']} Claude={value['claude']} Generic={value['generic']}\n"
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
    parser.add_argument("--generic", action="store_true")
    parser.add_argument(
        "--model-routing",
        help="external bbk.model-routing.v1 JSON used to render installed agents without modifying the package",
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
        help="install only this profile id; repeat as needed; defaults to every profile in the selected, bundled, or sibling source",
    )
    parser.add_argument(
        "--no-language-profiles",
        action="store_true",
        help="install BBK core only instead of the selected, bundled, or sibling language profiles",
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    verify = sub.add_parser("verify", help="run all BBK verification checks in canonical order")
    verify.add_argument("--failfast", action="store_true")
    verify.add_argument("--require-node", action="store_true")
    verify.set_defaults(func=verify_command)

    installer = sub.add_parser("install", help="install BBK and optional language profiles")
    add_install_selection_flags(installer)
    installer.add_argument(
        "--verify",
        action="store_true",
        help="run the complete verification sequence first and install only on PASS",
    )
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
    normalized = list(sys.argv[1:] if argv is None else argv)
    if "--json" in normalized and normalized and normalized[0] != "--json":
        normalized.remove("--json")
        normalized.insert(0, "--json")
    args = build_parser().parse_args(normalized)
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
