#!/usr/bin/env python3
"""Reversible jj workspace/change allocation for governed work-unit attempts."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

from gate_kernel import canonical_digest
try:
    from .mise_adapter import MiseAdapterError, managed_tool_command, managed_tool_environment
except ImportError:  # pragma: no cover - direct script compatibility
    from mise_adapter import MiseAdapterError, managed_tool_command, managed_tool_environment


class JjAdapterError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def _jj_path(explicit: str | Path) -> Path:
    """Validate an explicit compatibility/test override.

    Normal BBK execution does not discover jj on global PATH; it resolves the
    versioned tool through canonical mise configuration.
    """
    path = Path(str(explicit)).resolve()
    if not path.is_file() or path.is_symlink() or not os.access(path, os.X_OK):
        raise JjAdapterError("SUBSTRATE_JJ_UNSAFE_PATH", f"jj executable is not a safe regular executable: {path}")
    return path


def _jj_command(
    cwd: str | Path,
    *,
    jj_path: str | Path | None = None,
    environment: Mapping[str, str] | None = None,
) -> tuple[list[str], dict[str, str]]:
    if jj_path is not None:
        executable = _jj_path(jj_path)
        return [str(executable)], {
            "execution_mode": "EXPLICIT_EXECUTABLE",
            "jj_path": str(executable),
        }
    source = dict(os.environ if environment is None else environment)
    try:
        command, binding = managed_tool_command(
            cwd,
            "jj",
            mise_path_value=source.get("BBK_MISE"),
            environment=source,
        )
    except MiseAdapterError as exc:
        raise JjAdapterError(
            "SUBSTRATE_JJ_MISE_UNAVAILABLE",
            f"jj must be resolved through mise and canonical [tools] configuration: {exc.code}: {exc.message}",
        ) from exc
    return command, binding


def execution_binding(
    cwd: str | Path,
    *,
    jj_path: str | Path | None = None,
    environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    return dict(_jj_command(cwd, jj_path=jj_path, environment=environment)[1])


def _run(
    cwd: str | Path,
    arguments: Sequence[str],
    *,
    jj_path: str | Path | None = None,
    check: bool = True,
    environment: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    command_prefix, _binding = _jj_command(cwd, jj_path=jj_path, environment=environment)
    completed = subprocess.run(
        [*command_prefix, "--no-pager", "--color=never", *arguments],
        cwd=Path(cwd).resolve(),
        env=managed_tool_environment({**os.environ, **dict(environment or {})}),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="backslashreplace",
        timeout=300,
    )
    if check and completed.returncode != 0:
        raise JjAdapterError(
            "JJ_COMMAND_FAILED",
            f"jj {' '.join(arguments)}: {(completed.stderr or completed.stdout).strip() or completed.returncode}",
        )
    return completed


def repository_root(cwd: str | Path, *, jj_path: str | Path | None = None) -> Path:
    output = _run(cwd, ("root",), jj_path=jj_path).stdout.strip()
    if not output:
        raise JjAdapterError("JJ_REPOSITORY_NOT_FOUND", f"no jj repository at {cwd}")
    return Path(output).resolve()


def git_repository_root(cwd: str | Path, *, jj_path: str | Path | None = None) -> Path:
    output = _run(cwd, ("git", "root"), jj_path=jj_path).stdout.strip()
    if not output:
        raise JjAdapterError("JJ_GIT_ROOT_UNAVAILABLE", f"jj repository at {cwd} is not Git-backed")
    path = Path(output).resolve()
    return path.parent if path.name == ".git" else path


def assert_colocated(
    project_root: str | Path,
    *,
    jj_path: str | Path | None = None,
    git_root: str | Path | None = None,
) -> Path:
    requested = Path(project_root).resolve()
    root = repository_root(requested, jj_path=jj_path)
    if root != requested:
        raise JjAdapterError("JJ_PROJECT_ROOT_MISMATCH", f"governed root {requested} resolves to jj root {root}")
    jj_git_root = git_repository_root(root, jj_path=jj_path)
    expected = Path(git_root).resolve() if git_root else requested
    if jj_git_root != expected:
        raise JjAdapterError("JJ_GIT_ROOT_MISMATCH", f"jj Git root {jj_git_root} does not match {expected}")
    return root


def _template(cwd: Path, revision: str, template: str, *, jj_path: str | Path | None = None) -> str:
    return _run(cwd, ("log", "-r", revision, "--no-graph", "-T", template), jj_path=jj_path).stdout.strip()


def operation_id(cwd: str | Path, *, jj_path: str | Path | None = None) -> str:
    output = _run(cwd, ("op", "log", "--limit", "1", "--no-graph", "-T", 'id ++ "\\n"'), jj_path=jj_path).stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{64,128}", output):
        raise JjAdapterError("JJ_OPERATION_ID_INVALID", f"unexpected operation identity {output!r}")
    return output


def identity(cwd: str | Path, *, revision: str = "@", jj_path: str | Path | None = None) -> dict[str, Any]:
    root = repository_root(cwd, jj_path=jj_path)
    change_id = _template(root, revision, 'change_id ++ "\\n"', jj_path=jj_path)
    commit_id = _template(root, revision, 'commit_id ++ "\\n"', jj_path=jj_path)
    parents = _template(root, revision, 'parents.map(|p| p.commit_id()).join(",") ++ "\\n"', jj_path=jj_path)
    workspace_name = _run(cwd, ("workspace", "list", "-T", 'name ++ "\\t" ++ root ++ "\\n"'), jj_path=jj_path).stdout
    current_workspace = None
    resolved_cwd = Path(cwd).resolve()
    for line in workspace_name.splitlines():
        name, _, raw_root = line.partition("\t")
        if raw_root and Path(raw_root).resolve() == resolved_cwd:
            current_workspace = name
            break
    if not change_id or not commit_id:
        raise JjAdapterError("JJ_CHANGE_ID_INVALID", f"cannot resolve {revision}")
    core = {
        "jj_execution": execution_binding(cwd, jj_path=jj_path),
        "jj_change_id": change_id,
        "jj_commit_id": commit_id,
        "parent_commit_ids": [item for item in parents.split(",") if item],
        "operation_id": operation_id(root, jj_path=jj_path),
        "repository_root": str(root),
        "workspace_path": str(resolved_cwd),
        "workspace_name": current_workspace,
    }
    return {**core, "identity_digest": f"sha256:{canonical_digest(core)}"}


def _workspace_map(repository: Path, *, jj_path: str | Path | None = None) -> dict[str, Path]:
    output = _run(repository, ("workspace", "list", "-T", 'name ++ "\\t" ++ root ++ "\\n"'), jj_path=jj_path).stdout
    result: dict[str, Path] = {}
    for line in output.splitlines():
        name, separator, raw_root = line.partition("\t")
        if separator and name and raw_root:
            result[name] = Path(raw_root).resolve()
    return result


def workspace_name_for_attempt(work_unit_id: str, attempt_id: str) -> str:
    raw = f"bbk-{work_unit_id}-{attempt_id}".lower()
    cleaned = re.sub(r"[^a-z0-9._-]+", "-", raw).strip("-.")
    suffix = canonical_digest({"work_unit_id": work_unit_id, "attempt_id": attempt_id})[:10]
    return f"{cleaned[:48]}-{suffix}"


def allocate_workspace(
    project_root: str | Path,
    destination: str | Path,
    *,
    work_unit_id: str,
    attempt_id: str,
    parent_revision: str,
    description: str,
    jj_path: str | Path | None = None,
    workspace_name: str | None = None,
) -> dict[str, Any]:
    """Allocate exactly one new jj change/workspace for an attempt.

    Repeating the exact call returns the existing matching workspace. A name or
    destination collision with different identity fails closed.
    """
    repository = assert_colocated(project_root, jj_path=jj_path)
    destination_path = Path(destination).resolve()
    name = workspace_name or workspace_name_for_attempt(work_unit_id, attempt_id)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", name):
        raise JjAdapterError("JJ_WORKSPACE_NAME_INVALID", f"unsafe workspace name {name!r}")
    workspaces = _workspace_map(repository, jj_path=jj_path)
    if name in workspaces:
        if workspaces[name] != destination_path:
            raise JjAdapterError("JJ_WORKSPACE_IDENTITY_COLLISION", f"workspace {name} already maps to {workspaces[name]}")
        existing = identity(destination_path, jj_path=jj_path)
        return {
            "schema": "bbk.jj-attempt-workspace.v1",
            "status": "REUSED",
            "work_unit_id": work_unit_id,
            "attempt_id": attempt_id,
            "parent_revision": parent_revision,
            **existing,
        }
    if destination_path.exists():
        if any(destination_path.iterdir()) if destination_path.is_dir() else True:
            raise JjAdapterError("JJ_WORKSPACE_DESTINATION_OCCUPIED", f"destination is not empty: {destination_path}")
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    before_operation = operation_id(repository, jj_path=jj_path)
    _run(
        repository,
        (
            "workspace", "add", "--name", name, "-r", parent_revision,
            "-m", description, "--sparse-patterns", "full", str(destination_path),
        ),
        jj_path=jj_path,
    )
    created = identity(destination_path, jj_path=jj_path)
    if created.get("workspace_name") != name:
        raise JjAdapterError("JJ_WORKSPACE_POSTCONDITION_FAILED", f"created workspace identity does not resolve to {name}")
    return {
        "schema": "bbk.jj-attempt-workspace.v1",
        "status": "CREATED",
        "work_unit_id": work_unit_id,
        "attempt_id": attempt_id,
        "parent_revision": parent_revision,
        "operation_before": before_operation,
        **created,
    }


def _canonical_repository_path(raw: str) -> str:
    """Return one platform-neutral repository-relative path.

    ``jj diff --name-only`` emits host-native separators on Windows.  BBK
    contracts, receipts, scope prefixes, and candidate manifests use POSIX
    repository paths on every host.  Canonicalize the separator at the adapter
    boundary and reject absolute, traversal, or ambiguous path forms before a
    path can participate in scope, integration, or candidate-admission logic.

    A literal backslash in a repository filename is intentionally outside the
    portable BBK path contract because it is indistinguishable from a Windows
    separator in host tool output.
    """
    if not isinstance(raw, str):
        raise JjAdapterError("JJ_CHANGED_PATH_INVALID", "jj changed path must be text")
    if "\x00" in raw or "\n" in raw or "\r" in raw:
        raise JjAdapterError("JJ_CHANGED_PATH_INVALID", f"jj returned a control character in changed path {raw!r}")
    canonical = raw.replace("\\", "/")
    if not canonical:
        raise JjAdapterError("JJ_CHANGED_PATH_INVALID", "jj returned an empty changed path")
    if canonical.startswith("/") or canonical.startswith("//") or re.match(r"^[A-Za-z]:", canonical):
        raise JjAdapterError("JJ_CHANGED_PATH_INVALID", f"jj returned an absolute changed path {raw!r}")
    parts = canonical.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise JjAdapterError("JJ_CHANGED_PATH_INVALID", f"jj returned an ambiguous or traversing changed path {raw!r}")
    return "/".join(parts)


def _changed_path_output(output: str) -> list[str]:
    paths: set[str] = set()
    for line in output.splitlines():
        # ``splitlines`` removes the line ending without stripping filename
        # whitespace.  Empty records are ignored; every non-empty record must
        # satisfy the portable repository-path contract.
        if line == "":
            continue
        paths.add(_canonical_repository_path(line))
    return sorted(paths)


def changed_paths(cwd: str | Path, *, revision: str = "@", jj_path: str | Path | None = None) -> list[str]:
    output = _run(cwd, ("diff", "--name-only", "-r", revision), jj_path=jj_path).stdout
    return _changed_path_output(output)


def changed_paths_between(
    cwd: str | Path,
    *,
    from_revision: str,
    to_revision: str = "@",
    jj_path: str | Path | None = None,
) -> list[str]:
    """Return the exact path delta between two revisions.

    A content-neutral merge can have an empty ordinary ``jj diff -r`` because
    its tree is the automatic merge of its parents. Candidate admission needs
    the delta from the common baseline instead, so integrated path closure is
    measured explicitly with ``--from``/``--to``.
    """
    source = str(from_revision).strip()
    target = str(to_revision).strip()
    if not source or not target:
        raise JjAdapterError("JJ_DIFF_REVISIONS_REQUIRED", "from_revision and to_revision must be non-empty")
    output = _run(
        cwd,
        ("diff", "--name-only", "--from", source, "--to", target),
        jj_path=jj_path,
    ).stdout
    return _changed_path_output(output)



def merge_content_neutral(
    project_root: str | Path,
    destination: str | Path,
    *,
    work_unit_id: str,
    attempt_id: str,
    source_revisions: Sequence[str],
    parent_revision: str,
    description: str,
    jj_path: str | Path | None = None,
    workspace_name: str | None = None,
) -> dict[str, Any]:
    """Create a merge candidate only when source path sets are disjoint.

    This is deliberately a content-neutral adapter.  Any overlapping path,
    duplicate source, or unresolved jj conflict is rejected so semantic
    conflict resolution remains assigned to a bound Integration Worker.
    """
    repository = assert_colocated(project_root, jj_path=jj_path)
    baseline_identity = identity(repository, revision=parent_revision, jj_path=jj_path)
    sources = [str(item).strip() for item in source_revisions]
    if len(sources) < 2 or any(not item for item in sources):
        raise JjAdapterError(
            "JJ_CONTENT_NEUTRAL_SOURCES_INVALID",
            "at least two non-empty source revisions are required",
        )
    if len(sources) != len(set(sources)):
        raise JjAdapterError(
            "JJ_CONTENT_NEUTRAL_SOURCES_DUPLICATE",
            "source revisions must be unique",
        )

    # Jujutsu snapshots a workspace when a command runs in that workspace.
    # Refresh isolated attempt workspaces before resolving source revisions so
    # worker writes are not mistaken for empty changes.  Do not refresh the
    # repository/root workspace: it carries mutable BBK coordination metadata,
    # is not an integration source, and snapshotting it can serialize unrelated
    # governance state into the product merge or hold the workspace lock.
    for workspace_path in _workspace_map(repository, jj_path=jj_path).values():
        if workspace_path.resolve() == repository.resolve():
            continue
        _run(workspace_path, ("status",), jj_path=jj_path, check=False)

    source_identities: list[dict[str, Any]] = []
    source_paths: dict[str, list[str]] = {}
    owners: dict[str, list[str]] = {}
    for revision in sources:
        item = identity(repository, revision=revision, jj_path=jj_path)
        resolved = str(item["jj_change_id"])
        paths = changed_paths(repository, revision=revision, jj_path=jj_path)
        source_identities.append(item)
        source_paths[resolved] = paths
        for path in paths:
            owners.setdefault(path, []).append(resolved)
    overlaps = {path: revisions for path, revisions in sorted(owners.items()) if len(revisions) > 1}
    if overlaps:
        rendered = ", ".join(f"{path} ({'/'.join(revisions)})" for path, revisions in overlaps.items())
        raise JjAdapterError(
            "JJ_CONTENT_NEUTRAL_PATH_OVERLAP",
            f"content-neutral integration cannot resolve overlapping source paths: {rendered}",
        )

    allocated = allocate_workspace(
        repository,
        destination,
        work_unit_id=work_unit_id,
        attempt_id=attempt_id,
        parent_revision=parent_revision,
        description=f"{description} allocation",
        jj_path=jj_path,
        workspace_name=workspace_name,
    )
    workspace = Path(allocated["workspace_path"]).resolve()
    operation_before = operation_id(repository, jj_path=jj_path)
    _run(workspace, ("new", *sources, "-m", description), jj_path=jj_path)
    conflict_state = _template(workspace, "@", 'conflict ++ "\n"', jj_path=jj_path).strip().lower()
    if conflict_state not in {"true", "false"}:
        raise JjAdapterError(
            "JJ_CONTENT_NEUTRAL_CONFLICT_STATE_INVALID",
            f"jj returned unexpected conflict state {conflict_state!r}",
        )
    if conflict_state == "true":
        conflicts = _run(workspace, ("resolve", "--list"), jj_path=jj_path, check=False)
        conflict_text = (conflicts.stdout or conflicts.stderr).strip()
        raise JjAdapterError(
            "JJ_CONTENT_NEUTRAL_CONFLICT",
            f"jj reported unresolved integration conflicts: {conflict_text or 'unspecified conflict'}",
        )
    merged = identity(workspace, jj_path=jj_path)
    expected_parents = {item["jj_commit_id"] for item in source_identities}
    if set(merged.get("parent_commit_ids", [])) != expected_parents:
        raise JjAdapterError(
            "JJ_CONTENT_NEUTRAL_POSTCONDITION_FAILED",
            "integration candidate parents do not match the exact source revisions",
        )
    integrated_paths = sorted(owners)
    observed_integrated_paths = changed_paths_between(
        workspace,
        from_revision=baseline_identity["jj_commit_id"],
        to_revision=merged["jj_change_id"],
        jj_path=jj_path,
    )
    if observed_integrated_paths != integrated_paths:
        raise JjAdapterError(
            "JJ_CONTENT_NEUTRAL_PATH_CLOSURE_FAILED",
            f"integration candidate path closure {observed_integrated_paths!r} does not match source union {integrated_paths!r}",
        )
    core = {
        "schema": "bbk.jj-content-neutral-integration.v1",
        "status": "INTEGRATED",
        "work_unit_id": work_unit_id,
        "attempt_id": attempt_id,
        "baseline_change_id": baseline_identity["jj_change_id"],
        "baseline_commit_id": baseline_identity["jj_commit_id"],
        "source_change_ids": [item["jj_change_id"] for item in source_identities],
        "source_commit_ids": [item["jj_commit_id"] for item in source_identities],
        "source_changed_paths": source_paths,
        "integrated_paths": integrated_paths,
        "workspace_name": merged.get("workspace_name"),
        "workspace_path": merged["workspace_path"],
        "jj_change_id": merged["jj_change_id"],
        "jj_commit_id": merged["jj_commit_id"],
        "parent_commit_ids": merged["parent_commit_ids"],
        "operation_before": operation_before,
        "operation_after": operation_id(repository, jj_path=jj_path),
        "conflict_resolution_authority": "DENIED",
        "integration_mode": "CONTENT_NEUTRAL_DISJOINT_PATHS",
    }
    return {**core, "integration_digest": f"sha256:{canonical_digest(core)}"}

def forget_workspace(
    project_root: str | Path,
    workspace_name: str,
    *,
    jj_path: str | Path | None = None,
) -> dict[str, Any]:
    repository = assert_colocated(project_root, jj_path=jj_path)
    existing = _workspace_map(repository, jj_path=jj_path)
    if workspace_name not in existing:
        return {"status": "NOT_FOUND", "workspace_name": workspace_name}
    before = operation_id(repository, jj_path=jj_path)
    _run(repository, ("workspace", "forget", workspace_name), jj_path=jj_path)
    return {
        "status": "FORGOTTEN",
        "workspace_name": workspace_name,
        "workspace_path": str(existing[workspace_name]),
        "operation_before": before,
        "operation_after": operation_id(repository, jj_path=jj_path),
    }


__all__ = [
    "JjAdapterError", "allocate_workspace", "assert_colocated", "changed_paths", "changed_paths_between", "forget_workspace",
    "merge_content_neutral",
    "git_repository_root", "identity", "operation_id", "repository_root", "workspace_name_for_attempt",
]
