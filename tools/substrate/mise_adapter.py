#!/usr/bin/env python3
"""Qualified task execution through a declared, version-locked mise vocabulary."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import tomllib
from pathlib import Path
from typing import Any, Mapping, Sequence

from gate_kernel import canonical_digest, canonical_json_bytes
from governed_state import all_receipts, append_receipt
from dependencies import command_argv, discover_executable
import shutil


class MiseAdapterError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


ESSENTIAL_ENVIRONMENT = (
    'PATH',
    'PATHEXT',
    'SYSTEMROOT',
    'WINDIR',
    'COMSPEC',
    'TMP',
    'TEMP',
    'TMPDIR',
    'LANG',
    'LC_ALL',
    'USERPROFILE',
    'APPDATA',
    'LOCALAPPDATA',
    'HOMEDRIVE',
    'HOMEPATH',
    'MISE_CONFIG_DIR',
    'MISE_CACHE_DIR',
    'MISE_DATA_DIR',
    'MISE_STATE_DIR',
    'MISE_INSTALLS_DIR',
    'MISE_DOWNLOADS_DIR',
    'MISE_SHIMS_DIR',
    'MISE_GLOBAL_CONFIG_FILE',
    'MISE_SYSTEM_CONFIG_FILE',
    'MISE_CEILING_PATHS',
    'MISE_TRUSTED_CONFIG_PATHS',
    'MISE_DISABLE_TOOLS',
    'MISE_AUTO_INSTALL',
    'MISE_EXEC_AUTO_INSTALL',
    'MISE_NOT_FOUND_AUTO_INSTALL',
    'MISE_TASK_RUN_AUTO_INSTALL',
    'MISE_OFFLINE',
    'MISE_LOCKFILE',
    'MISE_NO_HOOKS',
    'MISE_NO_ENV',
    'MISE_NO_DOTENV',
    'PYTHONDONTWRITEBYTECODE',
)
SENSITIVE_NAME = re.compile(r"(?:TOKEN|SECRET|PASSWORD|PASSWD|API[_-]?KEY|CREDENTIAL|AUTH)", re.IGNORECASE)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def task_config_path(project_root: str | Path) -> Path:
    root = Path(project_root).resolve()
    for name in ("mise.toml", ".mise.toml"):
        path = root / name
        if path.is_file() and not path.is_symlink():
            return path
    raise MiseAdapterError("MISE_TASK_CONFIG_UNAVAILABLE", f"no canonical mise.toml or .mise.toml exists under {root}")


def toolchain_definition_digest(project_root: str | Path) -> str:
    return sha256_bytes(task_config_path(project_root).read_bytes())


def declared_tasks(project_root: str | Path) -> set[str]:
    path = task_config_path(project_root)
    try:
        parsed = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise MiseAdapterError("MISE_TASK_CONFIG_INVALID", f"cannot parse {path}: {exc}") from exc
    tasks = parsed.get("tasks", {})
    if not isinstance(tasks, dict):
        raise MiseAdapterError("MISE_TASK_CONFIG_INVALID", "[tasks] must be a table")
    result = {str(key) for key, value in tasks.items() if isinstance(value, (dict, str))}
    if not result:
        raise MiseAdapterError("MISE_TASK_CONFIG_EMPTY", f"{path} declares no tasks")
    return result


MANAGED_TOOL_KEYS: dict[str, tuple[str, str]] = {
    "jj": ("jj", "jj"),
    "bd": ("github:gastownhall/beads", "bd"),
}


def _parsed_mise_config(path: Path) -> dict[str, Any]:
    try:
        value = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise MiseAdapterError("MISE_TASK_CONFIG_INVALID", f"cannot parse {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise MiseAdapterError("MISE_TASK_CONFIG_INVALID", f"{path} is not a TOML table")
    return value


def _tool_config_candidates(project_root: str | Path) -> list[Path]:
    root = Path(project_root).resolve()
    candidates: list[Path] = []
    for base in (root, Path(__file__).resolve().parents[2]):
        for name in ("mise.toml", ".mise.toml"):
            path = base / name
            if path.is_file() and not path.is_symlink() and path not in candidates:
                candidates.append(path)
    return candidates


def declared_tools(project_root: str | Path) -> dict[str, str]:
    """Return the effective BBK-managed tool definitions.

    A project may override a canonical package definition by declaring the same
    key in its own ``mise.toml``. Package definitions remain available when a
    governed project has no tool table of its own.
    """
    result: dict[str, str] = {}
    # Package defaults are applied first; project-local declarations then win.
    for path in reversed(_tool_config_candidates(project_root)):
        tools = _parsed_mise_config(path).get("tools", {})
        if tools is None:
            continue
        if not isinstance(tools, dict):
            raise MiseAdapterError("MISE_TOOL_CONFIG_INVALID", f"[tools] in {path} must be a table")
        for key, value in tools.items():
            if not isinstance(key, str) or not key.strip():
                raise MiseAdapterError("MISE_TOOL_CONFIG_INVALID", f"invalid tool key in {path}")
            if not isinstance(value, str) or not value.strip():
                raise MiseAdapterError("MISE_TOOL_CONFIG_INVALID", f"tool {key!r} in {path} must have a version string")
            result[key] = value.strip()
    return result


def managed_tool_definition(project_root: str | Path, executable_name: str) -> dict[str, str]:
    try:
        tool_key, executable = MANAGED_TOOL_KEYS[executable_name]
    except KeyError as exc:
        raise MiseAdapterError("MISE_TOOL_UNSUPPORTED", f"no BBK managed-tool definition for {executable_name!r}") from exc
    tools = declared_tools(project_root)
    version = tools.get(tool_key)
    if not version:
        raise MiseAdapterError(
            "MISE_TOOL_NOT_DECLARED",
            f"canonical mise configuration does not declare {tool_key!r} for {executable_name}",
        )
    return {
        "tool_key": tool_key,
        "version": version,
        "tool_spec": f"{tool_key}@{version}",
        "executable": executable,
    }


def managed_tool_plan_command(
    project_root: str | Path,
    executable_name: str,
    *,
    launcher: str = "mise",
) -> tuple[list[str], dict[str, str]]:
    """Return the declarative mise-owned argv without resolving executables.

    This is intended for dry-run plans and operator-visible receipts. Actual
    execution must use :func:`managed_tool_command`, which resolves and
    qualifies the mise launcher before effect.
    """
    definition = managed_tool_definition(project_root, executable_name)
    command = [launcher, "exec", definition["tool_spec"], "--", definition["executable"]]
    return command, {
        **definition,
        "mise_path": launcher,
        "execution_mode": "MISE_MANAGED",
        "binding_status": "DECLARED_NOT_EXECUTED",
    }


def managed_tool_command(
    project_root: str | Path,
    executable_name: str,
    *,
    mise_path_value: str | Path | None = None,
    environment: Mapping[str, str] | None = None,
    test_adapter: bool = False,
) -> tuple[list[str], dict[str, str]]:
    """Return a mise-owned command prefix and its deterministic binding.

    The returned command is suitable for appending tool arguments, e.g.
    ``[*prefix, "root"]``. It never resolves the managed tool from global
    PATH; only the mise launcher itself must be operator-visible.
    """
    definition = managed_tool_definition(project_root, executable_name)
    source = dict(os.environ if environment is None else environment)
    explicit_mise = mise_path_value or source.get("BBK_MISE")
    mise = _mise_path(explicit_mise, test_adapter=test_adapter, environment=source)
    command = command_argv(
        mise,
        ["exec", definition["tool_spec"], "--", definition["executable"]],
        environment=source,
    )
    return command, {**definition, "mise_path": str(mise), "execution_mode": "MISE_MANAGED"}


def managed_tool_environment(source: Mapping[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if source is None else source)
    env.update({
        "MISE_YES": "1",
        "MISE_NO_DOTENV": "1",
        "MISE_AUTO_INSTALL": "0",
        "MISE_EXEC_AUTO_INSTALL": "0",
        "MISE_NOT_FOUND_AUTO_INSTALL": "0",
        "MISE_OFFLINE": "1",
        "NO_COLOR": "1",
        "CLICOLOR": "0",
    })
    return env


def assert_task_config_mutation_authority(binding: Mapping[str, Any]) -> None:
    """Enforce bounded foundation/toolchain ownership for mise.toml mutations."""
    request = binding.get("request", binding)
    role = request.get("role")
    scope = request.get("scope", {})
    mutation_classes = set(scope.get("mutation_classes", [])) if isinstance(scope, Mapping) else set()
    semantic_scope = set(scope.get("semantic_scope", [])) if isinstance(scope, Mapping) else set()
    if role != "bbk_worker" or "TOOLCHAIN_CONFIGURATION" not in mutation_classes or not (
        {"FOUNDATION_TOOLCHAIN", "foundation/toolchain", "toolchain"} & semantic_scope
    ):
        raise MiseAdapterError(
            "MISE_CONFIG_MUTATION_AUTHORITY_REQUIRED",
            "mise task definitions may change only in a bbk_worker binding that explicitly grants TOOLCHAIN_CONFIGURATION and foundation/toolchain semantic scope",
        )


def _mise_path(
    explicit: str | Path | None = None,
    *,
    test_adapter: bool = False,
    environment: Mapping[str, str] | None = None,
) -> Path:
    """Resolve runtime mise only from an explicit binding or the supplied PATH.

    Dependency preflight may inspect approved conventional install locations so
    it can give a new user useful guidance. Runtime execution is deliberately
    narrower: an empty fixture PATH must remain empty and must never fall
    through to a real user-level WinGet/Scoop/Chocolatey installation.
    """
    source = dict(os.environ if environment is None else environment)
    explicit_value = os.fspath(explicit) if explicit is not None else source.get("BBK_MISE")
    value = explicit_value or shutil.which("mise", path=source.get("PATH", ""))
    if not value:
        raise MiseAdapterError(
            "SUBSTRATE_MISE_UNAVAILABLE",
            "Provide an operator-installed real mise executable on PATH or an explicitly approved offline path; BBK will not download it.",
        )
    path = Path(value).expanduser().resolve()
    safe_suffixes = {"", ".exe", ".cmd", ".bat"}
    if (
        not path.is_file()
        or path.is_symlink()
        or (os.name == "nt" and path.suffix.casefold() not in safe_suffixes)
        or (os.name != "nt" and not os.access(path, os.X_OK))
    ):
        raise MiseAdapterError(
            "SUBSTRATE_MISE_UNSAFE_PATH",
            f"mise executable is not a safe regular executable: {path}",
        )
    authorized = source.get("BBK_ALLOW_TEST_ADAPTER") == "1" or os.environ.get("BBK_ALLOW_TEST_ADAPTER") == "1"
    if test_adapter and not authorized:
        raise MiseAdapterError(
            "MISE_TEST_ADAPTER_NOT_AUTHORIZED",
            "test adapters require BBK_ALLOW_TEST_ADAPTER=1",
        )
    return path


def mise_version(path: Path, *, environment: Mapping[str, str] | None = None) -> str:
    completed = subprocess.run(
        command_argv(path, ["--version"], environment=environment),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="backslashreplace",
        timeout=10,
        env={**(os.environ if environment is None else dict(environment)), "NO_COLOR": "1"},
    )
    output = " ".join(completed.stdout.split())
    if completed.returncode != 0 or not output:
        raise MiseAdapterError("SUBSTRATE_MISE_VERSION_FAILED", f"{path} returned {completed.returncode}: {output or '<no output>'}")
    return output


def _validate_request(request: Mapping[str, Any]) -> None:
    if request.get("schema") != "bbk.qualified-task-request.v1":
        raise MiseAdapterError("QUALIFIED_TASK_SCHEMA_INVALID", "expected bbk.qualified-task-request.v1")
    for field in ("binding_ref", "task", "candidate_digest", "toolchain_definition_digest", "idempotency_key"):
        if not isinstance(request.get(field), str) or not request[field]:
            raise MiseAdapterError("QUALIFIED_TASK_REQUEST_INVALID", f"{field} is required")
    for field in ("candidate_digest", "toolchain_definition_digest"):
        if not re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", request[field]):
            raise MiseAdapterError("QUALIFIED_TASK_REQUEST_INVALID", f"{field} is not a SHA-256 identity")
    arguments = request.get("arguments", [])
    if not isinstance(arguments, list) or any(not isinstance(item, str) for item in arguments):
        raise MiseAdapterError("QUALIFIED_TASK_REQUEST_INVALID", "arguments must be a string list")
    allowlist = request.get("environment_allowlist", [])
    if not isinstance(allowlist, list) or len(allowlist) != len(set(allowlist)) or any(not isinstance(item, str) for item in allowlist):
        raise MiseAdapterError("QUALIFIED_TASK_REQUEST_INVALID", "environment_allowlist must be a unique string list")
    sensitive = [name for name in allowlist if SENSITIVE_NAME.search(name)]
    if sensitive:
        raise MiseAdapterError("QUALIFIED_TASK_SENSITIVE_ENVIRONMENT_FORBIDDEN", f"sensitive environment names cannot enter receipts: {', '.join(sensitive)}")


def _stable_request(request: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(canonical_json_bytes(dict(request)).decode("utf-8"))


def _prior_receipt(project_root: str | Path, idempotency_key: str) -> dict[str, Any] | None:
    matches = [
        receipt
        for receipt in all_receipts(project_root)
        if receipt.get("receipt_kind") == "QUALIFIED_TASK"
        and receipt.get("content", {}).get("request", {}).get("idempotency_key") == idempotency_key
    ]
    if len(matches) > 1:
        raise MiseAdapterError("QUALIFIED_TASK_IDEMPOTENCY_STATE_CORRUPT", f"duplicate task idempotency key {idempotency_key}")
    return matches[0] if matches else None


def _environment(
    request: Mapping[str, Any],
    source: Mapping[str, str] | None = None,
) -> tuple[dict[str, str], dict[str, str]]:
    source_value = dict(os.environ if source is None else source)
    names = list(dict.fromkeys([*ESSENTIAL_ENVIRONMENT, *request.get("environment_allowlist", [])]))
    execution = {name: source_value[name] for name in names if name in source_value}
    # Qualified tasks are verification effects, not dependency-install effects.
    # These defaults prevent a check from consulting the network, installing a
    # missing tool, writing a lockfile, loading dotenv state, or firing hooks.
    safe_defaults = {
        "MISE_YES": "1",
        "MISE_NO_DOTENV": "1",
        "MISE_AUTO_INSTALL": "0",
        "MISE_EXEC_AUTO_INSTALL": "0",
        "MISE_NOT_FOUND_AUTO_INSTALL": "0",
        "MISE_TASK_RUN_AUTO_INSTALL": "0",
        "MISE_OFFLINE": "1",
        "MISE_LOCKFILE": "0",
        "MISE_NO_HOOKS": "1",
        "MISE_NO_ENV": "1",
        "NO_COLOR": "1",
        "CLICOLOR": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    # A qualified task is never an implicit dependency-install path.
    # Override inherited values rather than allowing a user/session-wide
    # auto-install setting to weaken the verification boundary.
    execution.update(safe_defaults)
    receipt_names = set(request.get("environment_allowlist", [])) | {"PATH", "LANG", "LC_ALL"}
    receipt = {name: value for name, value in execution.items() if name in receipt_names}
    return execution, receipt


def execute(
    project_root: str | Path,
    request: Mapping[str, Any],
    *,
    mise_path_value: str | Path | None = None,
    test_adapter: bool = False,
    environment: Mapping[str, str] | None = None,
    execution_root: str | Path | None = None,
) -> dict[str, Any]:
    """Run one declared task and append an immutable evidence receipt.

    ``project_root`` owns the governance journal. ``execution_root`` may name
    the exact candidate workspace bound by the caller, keeping task evidence
    outside candidate content. Existing callers default to one shared root.
    """
    _validate_request(request)
    stable = _stable_request(request)
    prior = _prior_receipt(project_root, request["idempotency_key"])
    if prior:
        if prior.get("content", {}).get("request") != stable:
            raise MiseAdapterError("QUALIFIED_TASK_IDEMPOTENCY_COLLISION", "idempotency key was reused for different task input")
        return {**prior["content"]["result"], "idempotent_reuse": True}

    execution = Path(execution_root or project_root).resolve()
    if not execution.is_dir():
        raise MiseAdapterError("MISE_EXECUTION_ROOT_INVALID", f"task execution root does not exist: {execution}")
    tasks = declared_tasks(execution)
    if request["task"] not in tasks:
        raise MiseAdapterError("MISE_TASK_NOT_DECLARED", f"task {request['task']!r} is absent from canonical mise configuration")
    actual_toolchain = toolchain_definition_digest(execution)
    expected_toolchain = request["toolchain_definition_digest"]
    if expected_toolchain.removeprefix("sha256:") != actual_toolchain.removeprefix("sha256:"):
        raise MiseAdapterError(
            "MISE_TOOLCHAIN_DEFINITION_DIGEST_MISMATCH",
            f"request binds {expected_toolchain}, current task configuration is {actual_toolchain}",
        )
    executable = _mise_path(
        mise_path_value,
        test_adapter=test_adapter,
        environment=environment,
    )
    execution_environment, receipt_environment = _environment(request, environment)
    version = mise_version(executable, environment=execution_environment)
    arguments = ["run", request["task"]]
    if request.get("arguments"):
        arguments.extend(["--", *request["arguments"]])
    command = command_argv(executable, arguments, environment=execution_environment)
    started = utc_now()
    completed = subprocess.run(
        command,
        cwd=execution,
        env=execution_environment,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=1800,
    )
    finished = utc_now()
    output_evidence = {
        "stdout_sha256": sha256_bytes(completed.stdout),
        "stderr_sha256": sha256_bytes(completed.stderr),
        "stdout_bytes": len(completed.stdout),
        "stderr_bytes": len(completed.stderr),
    }
    output_digest = f"sha256:{canonical_digest(output_evidence)}"
    result_core = {
        "schema": "bbk.qualified-task-result.v1",
        "task": request["task"],
        "candidate_digest": request["candidate_digest"],
        "toolchain_definition_digest": actual_toolchain,
        "mise_path": str(executable),
        "mise_version": version,
        "environment": receipt_environment,
        "command": command,
        "exit_status": completed.returncode,
        "output_digest": output_digest,
        "started_at": started,
        "finished_at": finished,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
    }
    receipt_id = f"sha256:{canonical_digest({'request': stable, 'result': result_core, 'adapter_class': 'TEST' if test_adapter else 'REAL'})}"
    result = {**result_core, "receipt_id": receipt_id}
    append_receipt(
        project_root,
        "QUALIFIED_TASK",
        {
            "request": stable,
            "result": result,
            "adapter_class": "TEST_ADAPTER" if test_adapter else "REAL_MISE",
            "output_evidence": output_evidence,
        },
        receipt_id=receipt_id,
    )
    return {**result, "idempotent_reuse": False}


def assert_release_qualified(result_receipt: Mapping[str, Any]) -> None:
    """Reject fake adapters and failed tasks at a release boundary."""
    content = result_receipt.get("content", result_receipt)
    if content.get("adapter_class") != "REAL_MISE":
        raise MiseAdapterError("MISE_REAL_ADAPTER_REQUIRED", "release qualification cannot use a fake/test mise adapter")
    result = content.get("result", {})
    if result.get("status") != "PASS" or result.get("exit_status") != 0:
        raise MiseAdapterError("MISE_QUALIFIED_TASK_FAILED", "release qualification task did not pass")


__all__ = [
    "MiseAdapterError", "assert_release_qualified", "assert_task_config_mutation_authority",
    "declared_tasks", "declared_tools", "execute", "managed_tool_command",
    "managed_tool_definition", "managed_tool_environment", "mise_version",
    "task_config_path", "toolchain_definition_digest",
]
