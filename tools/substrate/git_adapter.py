#!/usr/bin/env python3
"""Safe local Git identity and reconciliation adapter for governed candidates."""
from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from gate_kernel import canonical_digest
from dependencies import command_argv, discover_executable


class GitAdapterError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


VCS_METADATA_ROOTS = frozenset({".git", ".jj"})


def _git_path(
    explicit: str | Path | None = None,
    *,
    environment: Mapping[str, str] | None = None,
) -> Path:
    source = dict(os.environ if environment is None else environment)
    configured = str(explicit) if explicit else source.get("BBK_GIT") or source.get("BBK_TEST_GIT")
    path = Path(configured).expanduser().resolve() if configured else discover_executable("git", environment=source)
    if path is None:
        raise GitAdapterError(
            "SUBSTRATE_GIT_UNAVAILABLE",
            "Git is required and was not found on PATH or in a supported install location",
        )
    if not path.is_file() or path.is_symlink():
        raise GitAdapterError("SUBSTRATE_GIT_UNSAFE_PATH", f"Git executable is not a regular file: {path}")
    return path


def _run(
    project_root: str | Path,
    arguments: Sequence[str],
    *,
    git_path: str | Path | None = None,
    git_repository_root: str | Path | None = None,
    environment: Mapping[str, str] | None = None,
    check: bool = True,
    input_bytes: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    root = Path(project_root).resolve()
    execution_environment = {
        **os.environ,
        **dict(environment or {}),
        "GIT_TERMINAL_PROMPT": "0",
    }
    executable = _git_path(git_path, environment=execution_environment)
    if git_repository_root is not None:
        repository = Path(git_repository_root).resolve()
        git_directory = _git_directory(repository, git_path=git_path)
        execution_environment.update(
            {
                "GIT_DIR": str(git_directory),
                "GIT_WORK_TREE": str(root),
            }
        )
    completed = subprocess.run(
        command_argv(executable, arguments, environment=execution_environment),
        cwd=root,
        env=execution_environment,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )
    if check and completed.returncode != 0:
        message = completed.stderr.decode("utf-8", "backslashreplace").strip()
        raise GitAdapterError("GIT_COMMAND_FAILED", f"git {' '.join(arguments)}: {message or completed.returncode}")
    return completed


def _git_directory(repository_root_value: str | Path, *, git_path: str | Path | None = None) -> Path:
    repository = Path(repository_root_value).resolve()
    completed = _run(repository, ("rev-parse", "--absolute-git-dir"), git_path=git_path)
    output = completed.stdout.decode("utf-8", "surrogateescape").strip()
    if not output:
        raise GitAdapterError("GIT_DIRECTORY_NOT_FOUND", f"cannot resolve Git directory for {repository}")
    path = Path(output).resolve()
    if not path.is_dir() or path.is_symlink():
        raise GitAdapterError("GIT_DIRECTORY_UNSAFE", f"Git directory is not a safe directory: {path}")
    return path


def repository_root(project_root: str | Path, *, git_path: str | Path | None = None) -> Path:
    completed = _run(project_root, ("rev-parse", "--show-toplevel"), git_path=git_path)
    output = completed.stdout.decode("utf-8", "surrogateescape").strip()
    if not output:
        raise GitAdapterError("GIT_REPOSITORY_NOT_FOUND", f"no Git repository at {project_root}")
    return Path(output).resolve()


def assert_repository_boundary(
    project_root: str | Path,
    *,
    git_path: str | Path | None = None,
    require_exact_root: bool = True,
) -> Path:
    requested = Path(project_root).resolve()
    detected = repository_root(requested, git_path=git_path)
    if (requested / ".git").exists() and requested != detected:
        raise GitAdapterError(
            "GIT_NESTED_REPOSITORY_REJECTED",
            f"{requested} has a .git boundary but resolves to parent repository {detected}",
        )
    if require_exact_root and requested != detected:
        raise GitAdapterError(
            "GIT_PROJECT_ROOT_MISMATCH",
            f"governed project root {requested} is inside repository {detected}; bind the exact repository root",
        )
    return detected


def _jj_workspace_repository(worktree: Path) -> Path | None:
    """Resolve the repository store named by a secondary jj workspace marker."""
    marker = worktree / ".jj" / "repo"
    if not marker.is_file() or marker.is_symlink():
        return None
    try:
        raw = marker.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise GitAdapterError("GIT_JJ_WORKSPACE_MARKER_INVALID", f"cannot read {marker}: {exc}") from exc
    if not raw:
        raise GitAdapterError("GIT_JJ_WORKSPACE_MARKER_INVALID", f"{marker} is empty")
    return (marker.parent / raw).resolve()


def _worktree_context(
    project_root: str | Path,
    *,
    git_repository_root: str | Path | None = None,
    git_path: str | Path | None = None,
) -> tuple[Path, Path]:
    """Return an exact work tree and the Git repository that owns its objects.

    Secondary jj workspaces intentionally are not Git worktrees. For those
    workspaces the caller must supply the colocated repository root. The jj
    workspace marker is checked before Git may read the alternate work tree.
    """
    worktree = Path(project_root).resolve()
    if not worktree.is_dir() or worktree.is_symlink():
        raise GitAdapterError("GIT_WORKTREE_UNSAFE", f"candidate work tree is not a safe directory: {worktree}")
    if git_repository_root is None:
        return worktree, assert_repository_boundary(worktree, git_path=git_path)

    repository = assert_repository_boundary(git_repository_root, git_path=git_path)
    if worktree == repository:
        return worktree, repository
    marker_repository = _jj_workspace_repository(worktree)
    expected_store = (repository / ".jj" / "repo").resolve()
    if marker_repository != expected_store:
        raise GitAdapterError(
            "GIT_ALTERNATE_WORKTREE_UNBOUND",
            f"{worktree} is not a secondary jj workspace of {repository}",
        )
    return worktree, repository


def _metadata_path(relative: str) -> bool:
    parts = Path(relative).parts
    return bool(parts and parts[0] in VCS_METADATA_ROOTS)


@contextmanager
def _temporary_index(
    worktree: Path,
    repository: Path,
    *,
    git_path: str | Path | None = None,
    baseline_commit: str | None = None,
) -> Iterator[dict[str, str]]:
    """Yield an index isolated from the repository's shared Git index."""
    with tempfile.TemporaryDirectory(prefix="bbk-git-index-") as temporary:
        environment = {"GIT_INDEX_FILE": str(Path(temporary) / "index")}
        commit_target = str(baseline_commit or "HEAD").strip()
        if not commit_target:
            raise GitAdapterError("GIT_BASELINE_INVALID", "baseline commit must be non-empty when supplied")
        commit = _run(
            worktree,
            ("rev-parse", "--verify", commit_target),
            git_path=git_path,
            git_repository_root=repository,
            environment=environment,
            check=False,
        )
        if commit.returncode == 0:
            _run(
                worktree,
                ("read-tree", commit.stdout.decode("ascii", "strict").strip()),
                git_path=git_path,
                git_repository_root=repository,
                environment=environment,
            )
        else:
            _run(
                worktree,
                ("read-tree", "--empty"),
                git_path=git_path,
                git_repository_root=repository,
                environment=environment,
            )
        yield environment


def head_commit(
    project_root: str | Path,
    *,
    git_path: str | Path | None = None,
    git_repository_root: str | Path | None = None,
) -> str | None:
    worktree, repository = _worktree_context(
        project_root,
        git_repository_root=git_repository_root,
        git_path=git_path,
    )
    completed = _run(
        worktree,
        ("rev-parse", "--verify", "HEAD"),
        git_path=git_path,
        git_repository_root=repository,
        check=False,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.decode("ascii", "strict").strip()


def status_entries(
    project_root: str | Path,
    *,
    git_path: str | Path | None = None,
    git_repository_root: str | Path | None = None,
    baseline_commit: str | None = None,
) -> list[dict[str, str]]:
    """Return stable candidate status without reading or mutating the shared index."""
    worktree, repository = _worktree_context(
        project_root,
        git_repository_root=git_repository_root,
        git_path=git_path,
    )
    with _temporary_index(
        worktree, repository, git_path=git_path, baseline_commit=baseline_commit
    ) as environment:
        completed = _run(
            worktree,
            ("status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignore-submodules=none"),
            git_path=git_path,
            git_repository_root=repository,
            environment=environment,
        )
    parts = completed.stdout.split(b"\0")
    result: list[dict[str, str]] = []
    index = 0
    while index < len(parts):
        raw = parts[index]
        index += 1
        if not raw:
            continue
        text = raw.decode("utf-8", "surrogateescape")
        if len(text) < 4:
            raise GitAdapterError("GIT_STATUS_PARSE_FAILED", f"unexpected porcelain entry {text!r}")
        status = text[:2]
        path = text[3:]
        item = {"status": status, "path": path}
        if "R" in status or "C" in status:
            if index >= len(parts) or not parts[index]:
                raise GitAdapterError("GIT_STATUS_PARSE_FAILED", "rename/copy entry lacks source path")
            item["source_path"] = parts[index].decode("utf-8", "surrogateescape")
            index += 1
        if not _metadata_path(path) and not _metadata_path(item.get("source_path", "")):
            result.append(item)
    return sorted(result, key=lambda item: (item["path"], item["status"], item.get("source_path", "")))


def worktree_tree(
    project_root: str | Path,
    *,
    git_path: str | Path | None = None,
    git_repository_root: str | Path | None = None,
    baseline_commit: str | None = None,
) -> str:
    """Materialize the exact candidate work tree as an unreferenced Git tree.

    A temporary index is used; the repository's shared index, refs, commits,
    and remotes are not changed. Git may add otherwise-unreferenced local blob
    and tree objects to the colocated repository object store.
    """
    worktree, repository = _worktree_context(
        project_root,
        git_repository_root=git_repository_root,
        git_path=git_path,
    )
    with _temporary_index(
        worktree, repository, git_path=git_path, baseline_commit=baseline_commit
    ) as environment:
        # Stage the candidate through the temporary index.  Git rejects an
        # explicit exclusion pathspec when the same administrative path is
        # ignored, so stage normally and then remove all VCS metadata from the
        # isolated index.  Neither operation can touch the operator's index.
        _run(
            worktree,
            ("add", "-A", "--", "."),
            git_path=git_path,
            git_repository_root=repository,
            environment=environment,
        )
        _run(
            worktree,
            ("rm", "-r", "--cached", "--ignore-unmatch", "--", ".jj", ".git"),
            git_path=git_path,
            git_repository_root=repository,
            environment=environment,
            check=False,
        )
        completed = _run(
            worktree,
            ("write-tree",),
            git_path=git_path,
            git_repository_root=repository,
            environment=environment,
        )
    tree = completed.stdout.decode("ascii", "strict").strip()
    if not tree or len(tree) not in {40, 64}:
        raise GitAdapterError("GIT_TREE_ID_INVALID", f"git write-tree returned {tree!r}")
    return tree


def precommit_snapshot_digest(
    project_root: str | Path,
    *,
    git_path: str | Path | None = None,
    git_repository_root: str | Path | None = None,
    baseline_commit: str | None = None,
) -> str:
    """Return a documented fallback digest without adding Git objects."""
    root, repository = _worktree_context(
        project_root,
        git_repository_root=git_repository_root,
        git_path=git_path,
    )
    status = status_entries(
        root, git_path=git_path, git_repository_root=repository, baseline_commit=baseline_commit
    )
    files: list[dict[str, Any]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() or item.is_symlink()):
        relative = path.relative_to(root).as_posix()
        if _metadata_path(relative):
            continue
        if path.is_symlink():
            files.append({"path": relative, "kind": "symlink", "target": os.readlink(path)})
        else:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            files.append({"path": relative, "kind": "file", "sha256": digest, "size": path.stat().st_size})
    return f"sha256:{canonical_digest({'schema': 'bbk.precommit-snapshot.v1', 'status': status, 'files': files})}"


def freeze_candidate(
    project_root: str | Path,
    *,
    candidate_id: str,
    jj_change_id: str = "",
    workspace_path: str | Path | None = None,
    git_path: str | Path | None = None,
    git_repository_root: str | Path | None = None,
    baseline_commit: str | None = None,
    materialize_tree: bool = True,
) -> dict[str, Any]:
    root, repository = _worktree_context(
        project_root,
        git_repository_root=git_repository_root,
        git_path=git_path,
    )
    commit = str(baseline_commit).strip() if baseline_commit else head_commit(
        root, git_path=git_path, git_repository_root=repository
    )
    status = status_entries(
        root, git_path=git_path, git_repository_root=repository, baseline_commit=baseline_commit
    )
    tree = (
        worktree_tree(
            root, git_path=git_path, git_repository_root=repository, baseline_commit=baseline_commit
        )
        if materialize_tree
        else None
    )
    fallback = (
        None
        if tree
        else precommit_snapshot_digest(
            root, git_path=git_path, git_repository_root=repository, baseline_commit=baseline_commit
        )
    )
    identity_core = {
        "candidate_id": candidate_id,
        "git_commit": commit,
        "git_tree": tree,
        "precommit_snapshot_digest": fallback,
        "jj_change_id": jj_change_id,
        "workspace_path": str(Path(workspace_path or root).resolve()),
        "status": status,
    }
    return {
        "schema": "bbk.candidate-ref.v1",
        **identity_core,
        "state": "FROZEN",
        "digest": f"sha256:{canonical_digest(identity_core)}",
        "identity_kind": "GIT_TREE" if tree else "PRECOMMIT_SNAPSHOT",
    }


def _path_within(relative: str, prefixes: Sequence[str]) -> bool:
    path = Path(relative)
    for raw in prefixes:
        prefix = Path(raw)
        try:
            path.relative_to(prefix)
            return True
        except ValueError:
            continue
    return False


def reconcile(
    project_root: str | Path,
    *,
    binding_ref: str,
    candidate_ref: str,
    before: Mapping[str, Any],
    jj_change_id: str,
    scope_prefixes: Sequence[str],
    git_path: str | Path | None = None,
    git_repository_root: str | Path | None = None,
    baseline_commit: str | None = None,
) -> dict[str, Any]:
    after = freeze_candidate(
        project_root,
        candidate_id=candidate_ref,
        jj_change_id=jj_change_id,
        git_path=git_path,
        git_repository_root=git_repository_root,
        baseline_commit=baseline_commit,
    )
    entries = status_entries(
        project_root,
        git_path=git_path,
        git_repository_root=git_repository_root,
        baseline_commit=baseline_commit,
    )
    changed_paths = sorted({item["path"] for item in entries})
    out_of_scope = sorted(path for path in changed_paths if not _path_within(path, scope_prefixes))
    core = {
        "schema": "bbk.vcs-mutation-receipt.v1",
        "binding_ref": binding_ref,
        "candidate_ref": candidate_ref,
        "before": {
            "git_commit": before.get("git_commit") or "",
            "git_tree": before.get("git_tree") or before.get("precommit_snapshot_digest") or "",
            "jj_change_id": before.get("jj_change_id") or "",
        },
        "after": {
            "git_commit": after.get("git_commit") or "",
            "git_tree": after.get("git_tree") or after.get("precommit_snapshot_digest") or "",
            "jj_change_id": jj_change_id,
        },
        "changed_paths": changed_paths,
        "scope_conformance": "FAIL" if out_of_scope else "PASS",
        "out_of_scope_paths": out_of_scope,
    }
    return {**core, "receipt_id": f"sha256:{canonical_digest(core)}", "recorded_at": _utc_now()}


def _utc_now() -> str:
    import datetime as dt

    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = [
    "GitAdapterError",
    "assert_repository_boundary",
    "freeze_candidate",
    "head_commit",
    "precommit_snapshot_digest",
    "reconcile",
    "repository_root",
    "status_entries",
    "worktree_tree",
]
