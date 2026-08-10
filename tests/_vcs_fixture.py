"""Small, isolated Git/JJ/Beads fixtures used by substrate tests.

The fixture deliberately starts with plain Git.  JJ and Beads are opt-in because
most adapter tests only need a byte-exact Git tree; opting in creates fresh,
project-local metadata instead of copying or sharing hidden stores.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


def _tool(name: str, override: str | None = None) -> Path | None:
    value = override or os.environ.get(f"BBK_TEST_{name.upper()}") or shutil.which(name)
    if not value:
        return None
    path = Path(value).resolve()
    return path if path.is_file() else None


GIT = _tool("git") or Path("git")
JJ = _tool("jj")
BD = _tool("bd")


@dataclass(frozen=True)
class GitSeed:
    root: Path
    branch: str
    head: str
    files: Mapping[str, bytes]

    def run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(GIT), *args], cwd=self.root, check=check,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )


def prepare_git_seed(
    root: Path,
    *,
    files: Mapping[str, bytes] | None = None,
    fixture_id: str = "fixture",
    branch: str | None = None,
) -> GitSeed:
    """Create a fresh plain-Git repository with exact LF bytes.

    The branch namespace and commit message include a path-derived token so
    independent fixtures cannot accidentally share a branch/head identity.
    """
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    payload = dict(files or {"README.md": b"baseline\n"})
    for relative, content in payload.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    token = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:12]
    safe_id = re.sub(r"[^A-Za-z0-9._-]+", "-", fixture_id).strip("-.") or "fixture"
    branch_name = branch or f"bbk/{safe_id}/{token}"
    subprocess.run([str(GIT), "init", "-b", branch_name], cwd=root, check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for key, value in (("user.name", "BBK Test"), ("user.email", "bbk@example.invalid"),
                       ("core.autocrlf", "false"), ("core.eol", "lf")):
        subprocess.run([str(GIT), "config", key, value], cwd=root, check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run([str(GIT), "add", "."], cwd=root, check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run([str(GIT), "commit", "-m", f"{fixture_id} baseline {token}"], cwd=root,
                   check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    head = subprocess.run([str(GIT), "rev-parse", "HEAD"], cwd=root, check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout.strip()
    return GitSeed(root=root, branch=branch_name, head=head, files=payload)


def init_jj(seed_or_root: GitSeed | Path, *, jj_path: str | Path | None = None) -> Path:
    """Create a fresh colocated JJ store for one seed and return its path."""
    root = seed_or_root.root if isinstance(seed_or_root, GitSeed) else Path(seed_or_root).resolve()
    executable = Path(jj_path or JJ or "jj").resolve()
    subprocess.run([str(executable), "--no-pager", "--color=never", "git", "init", "--colocate", "."],
                   cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    metadata = root / ".jj"
    if not metadata.is_dir() or metadata.is_symlink():
        raise AssertionError(f"JJ metadata is not a fresh local directory: {metadata}")
    return metadata


def init_beads(seed_or_root: GitSeed | Path, *, bd_path: str | Path | None = None) -> Path:
    """Create a fresh project-local Beads store; caller must opt in explicitly."""
    root = seed_or_root.root if isinstance(seed_or_root, GitSeed) else Path(seed_or_root).resolve()
    executable = Path(bd_path or BD or "bd").resolve()
    subprocess.run(
        [str(executable), "--sandbox", "--json", "init", "--init-if-missing",
         "--non-interactive", "--skip-agents", "--skip-hooks", "--setup-exclude", "--prefix", "BBK"],
        cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env={**os.environ, "BD_NON_INTERACTIVE": "1", "BEADS_DISABLE_METRICS": "1"},
    )
    metadata = root / ".beads"
    if not metadata.is_dir() or metadata.is_symlink():
        raise AssertionError(f"Beads metadata is not a fresh local directory: {metadata}")
    return metadata


def assert_isolated(*roots: Path) -> None:
    """Assert hidden stores are physically local and never shared."""
    seen: dict[str, Path] = {}
    for root in roots:
        root = Path(root).resolve()
        for name in (".git", ".jj", ".beads", ".bbk"):
            path = root / name
            if not path.exists():
                continue
            if path.is_symlink():
                raise AssertionError(f"fixture metadata must not be a symlink: {path}")
            marker = str(path)
            prior = seen.get(name)
            if prior is not None and prior == path:
                raise AssertionError(f"fixture metadata is shared: {path}")
            seen[name] = path
