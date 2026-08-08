#!/usr/bin/env python3
"""Deterministically discover and qualify the governed execution substrate."""
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
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

TOOLS_DIR = Path(__file__).resolve().parents[1]
ROOT = TOOLS_DIR.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from gate_kernel import canonical_digest, canonical_json_bytes  # noqa: E402
from governed_state import initialize, state_root  # noqa: E402
from substrate.mise_adapter import (  # noqa: E402
    MiseAdapterError, managed_tool_command, managed_tool_definition, managed_tool_environment,
)

VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
SUPPORTED_TOOLS = ("git", "jj", "bd", "mise")
EXECUTABLE_NAMES = {
    "git": ("git", "git.exe", "git.cmd", "git.bat"),
    "jj": ("jj", "jj.exe", "jj.cmd", "jj.bat"),
    "bd": ("bd", "bd.exe", "bd.cmd", "bd.bat"),
    "mise": ("mise", "mise.exe", "mise.cmd", "mise.bat"),
}
VERSION_ARGS = {
    "git": ("--version",),
    "jj": ("--version",),
    "bd": ("--version",),
    "mise": ("--version",),
}
CAPABILITIES = {
    "git": ["DURABLE_COMMIT_IDENTITY", "TREE_IDENTITY", "STATUS_RECONCILIATION", "NO_REMOTE_CONTACT"],
    "jj": ["CHANGE_IDENTITY", "COLOCATED_GIT", "OPERATION_LOG", "WORKSPACE_ALLOCATION"],
    "bd": ["TYPED_COORDINATION_PROJECTION", "EXPECTED_REVISION", "IDEMPOTENT_TRANSITION", "SINGLE_WRITER_ADAPTER"],
    "mise": ["QUALIFIED_TASK_VOCABULARY", "VERSIONED_TASK_CONFIG", "TASK_DEFINITION_DIGEST", "NO_PERMISSION_AUTHORITY"],
}
SUPPORTED_EXECUTABLE_NAMES = {
    name: frozenset(value.casefold() for value in values)
    for name, values in EXECUTABLE_NAMES.items()
}
CONFIG_PATHS = {
    "git": (".git/config", ".gitmodules", ".gitattributes", ".gitignore"),
    "jj": (".jj/repo/config.toml", ".jj/repo/store/type", ".jj/repo/op_store/type"),
    "bd": (".beads/config.yaml", ".beads/metadata.json"),
    "mise": ("mise.toml", ".mise.toml", "mise.local.toml", ".config/mise/config.toml"),
}


class SubstrateDoctorError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return f"sha256:{digest.hexdigest()}"


def _approved_candidates(name: str, roots: Sequence[str | Path]) -> list[Path]:
    result: list[Path] = []
    for raw_root in roots:
        root = Path(raw_root).expanduser().resolve()
        for directory in (root, root / "bin"):
            for executable in EXECUTABLE_NAMES[name]:
                candidate = directory / executable
                if candidate.is_file() and not candidate.is_symlink() and os.access(candidate, os.X_OK):
                    result.append(candidate.resolve())
    return result


def discover_executable(
    name: str,
    *,
    search_policy: str = "PATH_AND_APPROVED_OFFLINE_ROOTS",
    approved_tool_roots: Sequence[str | Path] = (),
    environment: Mapping[str, str] | None = None,
) -> Path | None:
    if name not in SUPPORTED_TOOLS:
        raise SubstrateDoctorError("SUBSTRATE_TOOL_UNSUPPORTED", f"unsupported tool {name!r}")
    env = dict(os.environ if environment is None else environment)
    candidates: list[Path] = []
    path_match = shutil.which(name, path=env.get("PATH", ""))
    if path_match:
        path_candidate = Path(path_match).resolve()
        # ``shutil.which`` follows the host PATHEXT on Windows. Some systems
        # include .PY, but a Python source file is not a native command and
        # cannot be launched directly by CreateProcess. Accept only the bounded
        # executable spellings declared above.
        if path_candidate.name.casefold() in SUPPORTED_EXECUTABLE_NAMES[name]:
            candidates.append(path_candidate)
    if search_policy == "PATH_AND_APPROVED_OFFLINE_ROOTS":
        candidates.extend(_approved_candidates(name, approved_tool_roots))
    elif search_policy != "PATH_ONLY":
        raise SubstrateDoctorError("SUBSTRATE_SEARCH_POLICY_INVALID", f"unsupported search policy {search_policy!r}")
    seen: set[str] = set()
    for candidate in candidates:
        key = os.path.normcase(str(candidate))
        if key in seen:
            continue
        seen.add(key)
        if candidate.is_file() and not candidate.is_symlink() and os.access(candidate, os.X_OK):
            return candidate
    return None


def run_version(path: Path, name: str, *, timeout: float = 5.0, environment: Mapping[str, str] | None = None) -> str:
    try:
        completed = subprocess.run(
            [str(path), *VERSION_ARGS[name]],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="backslashreplace",
            timeout=timeout,
            env={**(os.environ if environment is None else environment), "NO_COLOR": "1", "CLICOLOR": "0"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SubstrateDoctorError(f"SUBSTRATE_{name.upper()}_UNEXECUTABLE", str(exc)) from exc
    output = " ".join(completed.stdout.split())
    if completed.returncode != 0 or not output:
        raise SubstrateDoctorError(
            f"SUBSTRATE_{name.upper()}_VERSION_FAILED",
            f"{path} returned {completed.returncode}: {output or '<no output>'}",
        )
    return output


def run_command_version(
    command_prefix: Sequence[str],
    name: str,
    *,
    timeout: float = 300.0,
    environment: Mapping[str, str] | None = None,
) -> str:
    try:
        completed = subprocess.run(
            [*command_prefix, *VERSION_ARGS[name]],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="backslashreplace",
            timeout=timeout,
            env=managed_tool_environment(environment),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SubstrateDoctorError(f"SUBSTRATE_{name.upper()}_UNEXECUTABLE", str(exc)) from exc
    output = " ".join(completed.stdout.split())
    if completed.returncode != 0 or not output:
        raise SubstrateDoctorError(
            f"SUBSTRATE_{name.upper()}_VERSION_FAILED",
            f"{' '.join(command_prefix)} returned {completed.returncode}: {output or '<no output>'}",
        )
    return output


def configuration_digests(project_root: Path, name: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for relative in CONFIG_PATHS[name]:
        path = project_root / relative
        if path.is_file() and not path.is_symlink():
            result[relative] = sha256_file(path)
    return result


def _run_identity_command(
    command_prefix: Sequence[str],
    arguments: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str] | None = None,
) -> tuple[int, str]:
    completed = subprocess.run(
        [*command_prefix, *arguments],
        cwd=cwd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="backslashreplace",
        timeout=300,
        env=managed_tool_environment(environment),
    )
    return completed.returncode, completed.stdout.strip()


def repository_observations(
    project_root: Path,
    commands: Mapping[str, Sequence[str]],
    *,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "git": {"repository": False, "root": None, "project_is_root": False, "nested_repository": False},
        "jj": {"repository": False, "root": None, "colocated_git_root": None, "project_is_root": False},
    }
    git = commands.get("git")
    if git:
        rc, output = _run_identity_command(git, ("rev-parse", "--show-toplevel"), cwd=project_root, environment=environment)
        if rc == 0 and output:
            detected = Path(output).resolve()
            result["git"].update({
                "repository": True,
                "root": str(detected),
                "project_is_root": detected == project_root,
                "nested_repository": (project_root / ".git").exists() and detected != project_root,
            })
    jj = commands.get("jj")
    if jj:
        rc, output = _run_identity_command([*jj, "--no-pager", "--color=never"], ("root",), cwd=project_root, environment=environment)
        if rc == 0 and output:
            detected = Path(output).resolve()
            result["jj"].update({"repository": True, "root": str(detected), "project_is_root": detected == project_root})
            git_rc, git_output = _run_identity_command(
                [*jj, "--no-pager", "--color=never"], ("git", "root"), cwd=project_root, environment=environment
            )
            if git_rc == 0 and git_output:
                jj_git = Path(git_output).resolve()
                if jj_git.name == ".git":
                    jj_git = jj_git.parent
                result["jj"]["colocated_git_root"] = str(jj_git)
    return result


def _validate_request(request: Mapping[str, Any]) -> None:
    if request.get("schema") != "bbk.substrate-doctor-request.v1":
        raise SubstrateDoctorError("SUBSTRATE_REQUEST_SCHEMA_INVALID", "expected bbk.substrate-doctor-request.v1")
    for field in ("project_root", "profile", "search_policy"):
        if not isinstance(request.get(field), str) or not request[field]:
            raise SubstrateDoctorError("SUBSTRATE_REQUEST_INVALID", f"{field} is required")
    required = request.get("required_tools")
    if not isinstance(required, list) or not required:
        raise SubstrateDoctorError("SUBSTRATE_REQUEST_INVALID", "required_tools must be a non-empty list")
    if len(set(required)) != len(required) or any(item not in SUPPORTED_TOOLS for item in required):
        raise SubstrateDoctorError("SUBSTRATE_REQUEST_INVALID", "required_tools contains duplicates or unsupported names")
    if request.get("search_policy") not in {"PATH_ONLY", "PATH_AND_APPROVED_OFFLINE_ROOTS"}:
        raise SubstrateDoctorError("SUBSTRATE_REQUEST_INVALID", "search_policy is invalid")


def inspect(
    request: Mapping[str, Any],
    *,
    environment: Mapping[str, str] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Return an IF-018 lock without installing, downloading, or mutating tools."""
    _validate_request(request)
    project_root = Path(str(request["project_root"])).expanduser().resolve()
    if not project_root.is_dir():
        raise SubstrateDoctorError("SUBSTRATE_PROJECT_ROOT_INVALID", f"project root does not exist: {project_root}")
    required = list(request["required_tools"])
    approved = request.get("approved_tool_roots", [])
    source_environment = dict(os.environ if environment is None else environment)
    mise_path = discover_executable(
        "mise",
        search_policy=request["search_policy"],
        approved_tool_roots=approved,
        environment=source_environment,
    )
    discovered: dict[str, Path | None] = {}
    commands: dict[str, list[str]] = {}
    tool_records: list[dict[str, Any]] = []
    remediation: list[str] = []
    for name in required:
        execution_mode = "DIRECT_EXECUTABLE"
        binding: dict[str, str] = {}
        if name in {"jj", "bd"}:
            path = mise_path
            if path is not None:
                try:
                    command, binding = managed_tool_command(
                        project_root, name, mise_path_value=path, environment=source_environment
                    )
                except MiseAdapterError as exc:
                    command = []
                    path = None
                    binding = {"configuration_error": f"{exc.code}: {exc.message}"}
                else:
                    commands[name] = command
                    execution_mode = "MISE_MANAGED"
        else:
            path = mise_path if name == "mise" else discover_executable(
                name,
                search_policy=request["search_policy"],
                approved_tool_roots=approved,
                environment=source_environment,
            )
            command = [str(path)] if path is not None else []
            if command:
                commands[name] = command
        discovered[name] = path
        if path is None or not command:
            if name in {"jj", "bd"}:
                code = f"SUBSTRATE_{name.upper()}_MISE_UNAVAILABLE"
                detail = binding.get("configuration_error", "mise is unavailable")
                message = (
                    f"Provide mise on PATH or an approved offline path and retain the canonical [tools] declaration; "
                    f"BBK does not require global {name}. {detail}"
                )
            else:
                code = f"SUBSTRATE_{name.upper()}_UNAVAILABLE"
                message = (
                    f"Provide an operator-installed {name} executable on PATH or in an explicitly approved offline tool root; "
                    "BBK will not download it."
                )
            remediation.append(f"{code}: {message}")
            tool_records.append({
                "name": name,
                "status": "BLOCK",
                "path": None,
                "version": None,
                "capabilities": CAPABILITIES[name],
                "configuration_digests": configuration_digests(project_root, name),
                "reason_code": code,
                "remediation": message,
                "execution_mode": execution_mode,
                **({k: binding[k] for k in ("tool_key", "tool_spec") if k in binding}),
            })
            continue
        try:
            version = (
                run_command_version(command, name, environment=source_environment)
                if execution_mode == "MISE_MANAGED"
                else run_version(path, name, environment=source_environment)
            )
            status = "PASS"
            reason_code = ""
            message = ""
        except SubstrateDoctorError as exc:
            version = None
            status = "BLOCK"
            reason_code = exc.code
            message = exc.message
            remediation.append(f"{exc.code}: {exc.message}")
        record = {
            "name": name,
            "status": status,
            "path": str(path),
            "version": version,
            "capabilities": CAPABILITIES[name],
            "configuration_digests": configuration_digests(project_root, name),
            "execution_mode": execution_mode,
        }
        if execution_mode == "MISE_MANAGED":
            record.update({
                "launcher_path": str(path),
                "tool_key": binding["tool_key"],
                "tool_spec": binding["tool_spec"],
            })
        if reason_code:
            record.update({"reason_code": reason_code, "remediation": message})
        tool_records.append(record)

    repository = repository_observations(project_root, commands, environment=source_environment)
    git_observation = repository["git"]
    jj_observation = repository["jj"]
    if "git" in required and not git_observation["repository"]:
        code = "SUBSTRATE_GIT_REPOSITORY_REQUIRED"
        remediation.append(f"{code}: initialize or select the intended existing Git repository explicitly; nested initialization is not automatic.")
        next(item for item in tool_records if item["name"] == "git").update({
            "status": "BLOCK", "reason_code": code,
            "remediation": "Select or explicitly initialize the intended Git repository root; BBK will not initialize a nested repository.",
        })
    if git_observation.get("nested_repository"):
        code = "SUBSTRATE_GIT_NESTED_REPOSITORY_REJECTED"
        remediation.append(f"{code}: remove/select away from the accidental nested .git boundary.")
        next(item for item in tool_records if item["name"] == "git").update({
            "status": "BLOCK", "reason_code": code,
            "remediation": "Use the established repository root or explicitly approve a distinct repository boundary.",
        })
    if "jj" in required and jj_observation["repository"]:
        git_root = jj_observation.get("colocated_git_root")
        if git_root and git_observation.get("root") and Path(git_root).resolve() != Path(git_observation["root"]).resolve():
            code = "SUBSTRATE_JJ_GIT_ROOT_MISMATCH"
            remediation.append(f"{code}: repair or recreate the disposable jj workspace against the intended Git root.")
            next(item for item in tool_records if item["name"] == "jj").update({
                "status": "BLOCK", "reason_code": code,
                "remediation": "Use a reversible colocated jj workspace bound to the same Git root.",
            })
    elif "jj" in required and commands.get("jj"):
        code = "SUBSTRATE_JJ_REPOSITORY_REQUIRED"
        remediation.append(f"{code}: initialize jj colocated with the intended Git repository using an explicit reversible action.")
        next(item for item in tool_records if item["name"] == "jj").update({
            "status": "BLOCK", "reason_code": code,
            "remediation": "Explicitly initialize jj in colocated Git mode; the doctor is inspection-only.",
        })

    status = "BLOCK" if any(item["status"] == "BLOCK" for item in tool_records) else "PASS"
    core = {
        "schema": "bbk.substrate-lock.v1",
        "profile": request["profile"],
        "project_root": str(project_root),
        "tools": tool_records,
        "status": status,
        "remediation": sorted(set(remediation)),
        "implementation_version": VERSION,
        "network_bootstrap_performed": False,
        "repository_observations": repository,
    }
    # repository_observations is useful evidence but v1 schema is intentionally
    # closed. Keep it in a companion field only until schema explicitly owns it.
    schema_core = {key: value for key, value in core.items() if key != "repository_observations"}
    lock_digest = f"sha256:{canonical_digest(schema_core)}"
    return {
        **schema_core,
        "lock_digest": lock_digest,
        "created_at": created_at or utc_now(),
    }


def write_lock(project_root: str | Path, lock: Mapping[str, Any]) -> Path:
    """Write an immutable lock named by its digest and a derived current pointer."""
    root = initialize(project_root)
    digest = str(lock.get("lock_digest", ""))
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise SubstrateDoctorError("SUBSTRATE_LOCK_DIGEST_INVALID", "lock_digest is invalid")
    path = root / "locks" / f"substrate-{digest.removeprefix('sha256:')}.json"
    payload = canonical_json_bytes(lock) + b"\n"
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if path.read_bytes() != payload:
            raise SubstrateDoctorError("SUBSTRATE_LOCK_COLLISION", f"existing immutable lock differs: {path}")
    else:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    projection = root / "projections" / "substrate-lock.json"
    projection.parent.mkdir(parents=True, exist_ok=True)
    temporary = projection.with_suffix(".tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, projection)
    return path


def default_request(
    project_root: str | Path,
    *,
    approved_tool_roots: Sequence[str | Path] = (),
    profile: str = "governed-software",
) -> dict[str, Any]:
    return {
        "schema": "bbk.substrate-doctor-request.v1",
        "project_root": str(Path(project_root).resolve()),
        "profile": profile,
        "required_tools": list(SUPPORTED_TOOLS),
        "search_policy": "PATH_AND_APPROVED_OFFLINE_ROOTS" if approved_tool_roots else "PATH_ONLY",
        "approved_tool_roots": [str(Path(item).resolve()) for item in approved_tool_roots],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--profile", default="governed-software")
    parser.add_argument("--approved-tool-root", action="append", default=[])
    parser.add_argument("--write-lock", action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _parser().parse_args(list(argv) if argv is not None else None)
    try:
        request = default_request(args.root, approved_tool_roots=args.approved_tool_root, profile=args.profile)
        lock = inspect(request)
        if args.write_lock:
            lock["lock_path"] = str(write_lock(args.root, lock))
        print(json.dumps(lock, indent=2, sort_keys=True))
        return 0 if lock["status"] == "PASS" else 2
    except SubstrateDoctorError as exc:
        print(json.dumps({"status": "BLOCK", "reason_code": exc.code, "message": exc.message}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
