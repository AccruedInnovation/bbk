#!/usr/bin/env python3
"""BBK dependency contract and non-installing installation preflight.

This module disables mise network access and automatic installation. It never
downloads or installs tools and never changes BBK installation files. Use
``tools/install_dependencies.py`` or ``tools/setup.py --install-dependencies``
for an explicit, opt-in bootstrap.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from runtime_requirements import (
    MINIMUM_PYTHON,
    MINIMUM_PYTHON_TEXT,
    enforce_supported_python,
)

enforce_supported_python(program="BBK dependency preflight")

import tomllib

ROOT = TOOLS_DIR.parent
CORE_MISE_CONFIG = Path("mise.toml")
OMP_RUNTIME_MISE_CONFIG = Path("tools/omp-runtime.mise.toml")
HARNESS_ORDER = ("codex", "omp", "claude", "pi", "generic")
HOST_COMMANDS: dict[str, str | None] = {
    "codex": "codex",
    "omp": "omp",
    "claude": "claude",
    "pi": "pi",
    "generic": None,
}
RUNTIME_PYTHON_REQUIREMENTS: dict[str, dict[str, str]] = {
    "jsonschema": {"minimum": "4.25.1", "maximum_exclusive": "5", "specifier": ">=4.25.1,<5"},
    "referencing": {"minimum": "0.36.2", "maximum_exclusive": "1", "specifier": ">=0.36.2,<1"},
}
# Reserved for packages needed only by verification. Runtime schema validation
# uses both packages above, so they must never be hidden behind a test-only flag.
TEST_REQUIREMENTS: dict[str, dict[str, str]] = {}
SUPPORTED_WINDOWS_SUFFIXES = ("", ".exe", ".cmd", ".bat")
READ_ONLY_MISE_ENVIRONMENT = {
    "MISE_NO_DOTENV": "1",
    "MISE_AUTO_INSTALL": "0",
    "MISE_EXEC_AUTO_INSTALL": "0",
    "MISE_NOT_FOUND_AUTO_INSTALL": "0",
    "MISE_OFFLINE": "1",
    "NO_COLOR": "1",
    "CLICOLOR": "0",
}


class DependencyError(RuntimeError):
    """Raised when the dependency contract cannot be evaluated."""


def selected_harnesses(names: Iterable[str] | None = None) -> tuple[str, ...]:
    """Return canonical selected harnesses; an empty selection means all."""
    values = {str(value) for value in (names or []) if str(value)}
    unknown = sorted(values - set(HARNESS_ORDER))
    if unknown:
        raise DependencyError(f"unknown BBK harness selection: {', '.join(unknown)}")
    if not values:
        values = set(HARNESS_ORDER)
    return tuple(name for name in HARNESS_ORDER if name in values)


def selected_harnesses_from_namespace(args: Any) -> tuple[str, ...]:
    return selected_harnesses(
        name for name in HARNESS_ORDER if bool(getattr(args, name, False))
    )


def _mise_tools_from_path(path: Path, *, purpose: str) -> dict[str, str]:
    try:
        value = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise DependencyError(f"cannot read the {purpose} mise tool table {path}: {exc}") from exc
    tools = value.get("tools")
    if not isinstance(tools, dict):
        raise DependencyError(f"{purpose} mise tool table is missing from {path}")
    result: dict[str, str] = {}
    for key, version in tools.items():
        if not isinstance(key, str) or not isinstance(version, str) or not version.strip():
            raise DependencyError(f"invalid mise tool declaration in {path}: {key!r}={version!r}")
        result[key] = version.strip()
    return result


def _mise_tools(root: Path = ROOT) -> dict[str, str]:
    return _mise_tools_from_path(root / CORE_MISE_CONFIG, purpose="canonical core")


def _omp_runtime_mise_tools(root: Path = ROOT) -> dict[str, str]:
    return _mise_tools_from_path(
        root / OMP_RUNTIME_MISE_CONFIG,
        purpose="OMP-only runtime",
    )


def managed_tool_contract(
    root: Path = ROOT,
    *,
    include_node: bool = False,
) -> tuple[dict[str, str], ...]:
    """Return the selected mise-managed tool contract.

    Core substrate pins come from the root ``mise.toml``. The Node pin comes
    from the non-default OMP runtime file only when OMP is selected. Keeping the
    files separate prevents ordinary root mise tasks from acquiring a Node
    dependency or triggering a Node auto-install.
    """
    core_tools = _mise_tools(root)
    expected = [
        (core_tools, CORE_MISE_CONFIG, "jj", "jj", "BBK_TEST_JJ", "BBK_JJ", "core"),
        (
            core_tools,
            CORE_MISE_CONFIG,
            "github:gastownhall/beads",
            "bd",
            "BBK_TEST_BD",
            "BBK_BD",
            "core",
        ),
    ]
    if include_node:
        expected.append(
            (
                _omp_runtime_mise_tools(root),
                OMP_RUNTIME_MISE_CONFIG,
                "node",
                "node",
                "BBK_TEST_NODE",
                "BBK_NODE",
                "omp-runtime",
            )
        )
    records: list[dict[str, str]] = []
    for (
        tools,
        config_path,
        tool_key,
        executable,
        test_environment,
        runtime_environment,
        kind,
    ) in expected:
        version = tools.get(tool_key)
        if not version:
            raise DependencyError(
                f"{config_path.as_posix()} does not declare {tool_key!r} for {executable}"
            )
        records.append(
            {
                "id": executable,
                "kind": kind,
                "tool_key": tool_key,
                "version": version,
                "tool_spec": f"{tool_key}@{version}",
                "executable": executable,
                "test_environment": test_environment,
                "runtime_environment": runtime_environment,
                "source_config": config_path.as_posix(),
            }
        )
    return tuple(records)


def dependency_contract(
    harnesses: Iterable[str] | None = None,
    *,
    include_test_dependencies: bool = False,
    require_omp_node: bool | None = None,
    root: Path = ROOT,
) -> dict[str, Any]:
    selected = selected_harnesses(harnesses)
    node_required = "omp" in selected if require_omp_node is None else bool(require_omp_node)
    return {
        "schema": "bbk.install-dependency-contract.v1",
        "python_minimum": MINIMUM_PYTHON_TEXT,
        "selected_harnesses": list(selected),
        "system_tools": ["git", "mise"],
        "managed_tools": list(managed_tool_contract(root, include_node=node_required)),
        "runtime_python_requirements": {
            name: dict(requirement) for name, requirement in RUNTIME_PYTHON_REQUIREMENTS.items()
        },
        "test_requirements": {
            name: dict(requirement) for name, requirement in TEST_REQUIREMENTS.items()
        } if include_test_dependencies else {},
        "host_commands": {
            name: HOST_COMMANDS[name] for name in selected if HOST_COMMANDS[name]
        },
        "host_commands_block_install": False,
        "omp_node_required": node_required,
    }


def _candidate_paths(name: str, environment: Mapping[str, str]) -> list[Path]:
    home = Path(environment.get("HOME") or environment.get("USERPROFILE") or str(Path.home()))
    values: list[Path] = []
    if name == "mise":
        values.extend([home / ".local" / "bin" / "mise", home / "bin" / "mise"])
    if os.name != "nt":
        values.extend(
            [
                Path("/usr/local/bin") / name,
                Path("/opt/homebrew/bin") / name,
                Path("/opt/local/bin") / name,
                Path("/usr/bin") / name,
                Path("/bin") / name,
            ]
        )
    else:
        local = Path(environment.get("LOCALAPPDATA", home / "AppData" / "Local"))
        program_files = Path(environment.get("ProgramFiles", "C:/Program Files"))
        program_files_x86 = Path(environment.get("ProgramFiles(x86)", "C:/Program Files (x86)"))
        scoop = Path(environment.get("SCOOP", home / "scoop"))
        winget_links = local / "Microsoft" / "WinGet" / "Links"
        if name == "mise":
            choco_root = Path(environment.get("ChocolateyInstall", "C:/ProgramData/chocolatey"))
            values.extend(
                [
                    winget_links / "mise.exe",
                    local / "mise" / "bin" / "mise.exe",
                    scoop / "shims" / "mise.exe",
                    scoop / "shims" / "mise.cmd",
                    choco_root / "bin" / "mise.exe",
                    choco_root / "bin" / "mise.cmd",
                ]
            )
        elif name == "git":
            values.extend(
                [
                    program_files / "Git" / "cmd" / "git.exe",
                    program_files / "Git" / "bin" / "git.exe",
                    program_files_x86 / "Git" / "cmd" / "git.exe",
                    scoop / "shims" / "git.exe",
                ]
            )
        elif name == "node":
            values.extend(
                [
                    program_files / "nodejs" / "node.exe",
                    program_files_x86 / "nodejs" / "node.exe",
                    scoop / "shims" / "node.exe",
                    winget_links / "node.exe",
                ]
            )
        elif name == "winget":
            values.append(local / "Microsoft" / "WindowsApps" / "winget.exe")
        elif name == "scoop":
            values.append(scoop / "shims" / "scoop.cmd")
        elif name == "choco":
            choco_root = Path(environment.get("ChocolateyInstall", "C:/ProgramData/chocolatey"))
            values.append(choco_root / "bin" / "choco.exe")
    return values


def _usable_executable(path: Path) -> bool:
    try:
        candidate = path.expanduser().resolve()
        if not candidate.is_file():
            return False
        if os.name == "nt":
            return candidate.suffix.lower() in SUPPORTED_WINDOWS_SUFFIXES
        return os.access(candidate, os.X_OK)
    except OSError:
        return False


def discover_executable(
    name: str,
    *,
    environment: Mapping[str, str] | None = None,
) -> Path | None:
    """Find one supported executable without accepting source-file PATHEXT hits."""
    source = dict(os.environ if environment is None else environment)
    found = shutil.which(name, path=source.get("PATH", ""))
    candidates = ([Path(found)] if found else []) + _candidate_paths(name, source)
    seen: set[str] = set()
    for value in candidates:
        key = os.path.normcase(str(value))
        if key in seen:
            continue
        seen.add(key)
        if _usable_executable(value):
            return value.expanduser().resolve()
    return None


def command_argv(
    executable: str | Path,
    arguments: Sequence[str] = (),
    *,
    environment: Mapping[str, str] | None = None,
) -> list[str]:
    """Return a CreateProcess-safe argv for native or Windows batch launchers."""
    path = Path(executable)
    if os.name == "nt" and path.suffix.lower() in {".cmd", ".bat"}:
        source = os.environ if environment is None else environment
        return [source.get("COMSPEC") or "cmd.exe", "/d", "/s", "/c", str(path), *map(str, arguments)]
    return [str(path), *map(str, arguments)]


def readonly_mise_environment(
    source: Mapping[str, str] | None = None,
) -> dict[str, str]:
    environment = dict(os.environ if source is None else source)
    environment.update(READ_ONLY_MISE_ENVIRONMENT)
    return environment


def _run_capture(
    command: Sequence[str],
    *,
    environment: Mapping[str, str],
    cwd: Path = ROOT,
    timeout: float = 20.0,
) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            list(command),
            cwd=cwd,
            env=dict(environment),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="backslashreplace",
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"{type(exc).__name__}: {exc}"
    output = completed.stdout.strip()
    if completed.returncode != 0:
        return False, " ".join(output.split()) or f"exit code {completed.returncode}"
    return True, output


def _run_version(
    executable: str | Path,
    *,
    environment: Mapping[str, str],
    cwd: Path = ROOT,
) -> tuple[bool, str]:
    ok, output = _run_capture(
        command_argv(executable, ("--version",), environment=environment),
        environment=environment,
        cwd=cwd,
    )
    return ok, " ".join(output.split()) if ok else output


def _check_direct(
    name: str,
    *,
    environment: Mapping[str, str],
    kind: str = "system",
) -> dict[str, Any]:
    path = discover_executable(name, environment=environment)
    if path is None:
        return {
            "id": name,
            "kind": kind,
            "required": True,
            "status": "BLOCK",
            "path": None,
            "version": None,
            "reason": f"{name} was not found on PATH or in a supported install location",
        }
    ok, version = _run_version(path, environment=environment)
    return {
        "id": name,
        "kind": kind,
        "required": True,
        "status": "PASS" if ok else "BLOCK",
        "path": str(path),
        "version": version if ok else None,
        "reason": None if ok else f"{name} could not be executed: {version}",
    }


def _resolve_mise_executable(
    mise: Path,
    record: Mapping[str, str],
    *,
    environment: Mapping[str, str],
    root: Path = ROOT,
) -> tuple[Path | None, str | None]:
    """Resolve an already-installed managed binary without invoking it through mise."""
    managed_environment = readonly_mise_environment(environment)
    command = command_argv(
        mise,
        ["which", str(record["executable"]), "--tool", str(record["tool_spec"])],
        environment=managed_environment,
    )
    ok, output = _run_capture(command, environment=managed_environment, cwd=root)
    if not ok:
        return None, output
    lines = [line.strip().strip('"') for line in output.splitlines() if line.strip()]
    if not lines:
        return None, "mise returned no executable path"
    candidate = Path(lines[-1]).expanduser()
    if not candidate.is_absolute():
        candidate = (root / candidate).resolve()
    if not _usable_executable(candidate):
        return None, f"mise resolved an unsafe or missing executable: {candidate}"
    return candidate.resolve(), None


def _check_managed(
    record: Mapping[str, str],
    *,
    mise: Path | None,
    environment: Mapping[str, str],
    root: Path = ROOT,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": str(record["id"]),
        "kind": "mise-managed" if record.get("kind") == "core" else str(record.get("kind")),
        "required": True,
        "tool_key": record["tool_key"],
        "tool_spec": record["tool_spec"],
        "expected_version": record["version"],
        "executable": record["executable"],
        "check_mode": "mise-which-non-installing-offline",
    }
    if mise is None:
        return {
            **base,
            "status": "BLOCK",
            "path": None,
            "version": None,
            "reason": "mise is unavailable, so the pinned tool cannot be checked",
        }
    path, error = _resolve_mise_executable(
        mise,
        record,
        environment=environment,
        root=root,
    )
    if path is None:
        return {
            **base,
            "status": "BLOCK",
            "path": None,
            "version": None,
            "reason": f"{record['tool_spec']} is not installed: {error}",
        }
    managed_environment = readonly_mise_environment(environment)
    ok, version = _run_version(path, environment=managed_environment, cwd=root)
    expected = str(record["version"])
    expected_numeric = _numeric_version(expected)
    actual_numeric = _numeric_version(version) if ok else None
    version_matches = bool(
        ok
        and expected_numeric is not None
        and actual_numeric is not None
        and _compare_versions(actual_numeric, expected_numeric) == 0
    )
    return {
        **base,
        "status": "PASS" if version_matches else "BLOCK",
        "path": str(path),
        "version": version if ok else None,
        "reason": None
        if version_matches
        else (
            f"{path} could not be executed: {version}"
            if not ok
            else f"{record['tool_spec']} resolved to an unexpected version: {version}"
        ),
    }


def _numeric_version(value: str) -> tuple[int, ...] | None:
    match = re.search(r"(?:^|\s|v)(\d+(?:\.\d+)*)", value)
    if not match:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def _compare_versions(left: tuple[int, ...], right: tuple[int, ...]) -> int:
    length = max(len(left), len(right))
    a = left + (0,) * (length - len(left))
    b = right + (0,) * (length - len(right))
    return (a > b) - (a < b)


def _version_in_range(actual: str, minimum: str, maximum_exclusive: str | None = None) -> bool:
    current = _numeric_version(actual)
    low = _numeric_version(minimum)
    high = _numeric_version(maximum_exclusive or "") if maximum_exclusive else None
    if current is None or low is None or _compare_versions(current, low) < 0:
        return False
    return high is None or _compare_versions(current, high) < 0


def _resolve_node_runtime(
    *,
    environment: Mapping[str, str],
    mise: Path | None = None,
    root: Path = ROOT,
) -> tuple[Path | None, str | None, str | None]:
    direct = discover_executable("node", environment=environment)
    if direct is not None:
        ok, version = _run_version(direct, environment=environment, cwd=root)
        if ok and _version_in_range(version, "22"):
            return direct, version, "direct"
    if mise is None:
        mise = discover_executable("mise", environment=environment)
    if mise is None:
        return None, None, "Node.js 22+ was not found and mise is unavailable"
    record = managed_tool_contract(root, include_node=True)[-1]
    check = _check_managed(record, mise=mise, environment=environment, root=root)
    if check["status"] == "PASS":
        return Path(str(check["path"])), str(check["version"]), "mise"
    return None, None, str(check.get("reason") or "managed Node.js is unavailable")


def command_with_node_runtime(
    command: Sequence[str],
    *,
    environment: Mapping[str, str] | None = None,
    root: Path = ROOT,
) -> tuple[list[str], dict[str, str]]:
    """Return *command* and an environment exposing a compatible Node runtime."""
    source = dict(os.environ if environment is None else environment)
    node, _version, error = _resolve_node_runtime(environment=source, root=root)
    if node is None:
        raise DependencyError(
            f"Node.js 22+ was not found: {error}. Run tools/setup.py --install-dependencies --omp"
        )
    _prepend_path(source, node.parent)
    source["BBK_TEST_NODE"] = str(node)
    source["BBK_NODE"] = str(node)
    return list(command), source


def _prepend_path(environment: dict[str, str], directory: Path) -> None:
    raw = str(directory)
    parts = [part for part in environment.get("PATH", "").split(os.pathsep) if part]
    if not any(os.path.normcase(part) == os.path.normcase(raw) for part in parts):
        environment["PATH"] = os.pathsep.join([raw, *parts])


def verification_environment(
    source: Mapping[str, str] | None = None,
    *,
    include_node: bool = False,
    root: Path = ROOT,
    strict: bool = False,
) -> dict[str, str]:
    """Expose qualified tools to verification without allowing downloads.

    Preflight may find Git or mise in a supported install location even when the
    parent process has not refreshed ``PATH``. Export their exact paths and add
    their parent directories so the process that passed preflight is also the
    process environment used by all child checks.
    """
    environment = readonly_mise_environment(source)
    failures: list[str] = []

    git = discover_executable("git", environment=environment)
    if git is None:
        failures.append("git: unavailable")
    else:
        environment["BBK_TEST_GIT"] = str(git)
        environment["BBK_GIT"] = str(git)
        _prepend_path(environment, git.parent)

    mise = discover_executable("mise", environment=environment)
    if mise is None:
        failures.append("mise: unavailable")
    else:
        environment["BBK_TEST_MISE"] = str(mise)
        environment["BBK_MISE"] = str(mise)
        _prepend_path(environment, mise.parent)

    for record in managed_tool_contract(root):
        if mise is None:
            failures.append(f"{record['tool_spec']}: mise unavailable")
            continue
        path, error = _resolve_mise_executable(mise, record, environment=environment, root=root)
        if path is None:
            failures.append(f"{record['tool_spec']}: {error}")
            continue
        environment[str(record["test_environment"])] = str(path)
        environment[str(record["runtime_environment"])] = str(path)
        _prepend_path(environment, path.parent)
    if include_node:
        node, _version, error = _resolve_node_runtime(
            environment=environment,
            mise=mise,
            root=root,
        )
        if node is None:
            failures.append(f"node: {error}")
        else:
            environment["BBK_TEST_NODE"] = str(node)
            environment["BBK_NODE"] = str(node)
            _prepend_path(environment, node.parent)
    if strict and failures:
        raise DependencyError("; ".join(failures))
    return environment


def _check_python_requirement(
    distribution: str,
    requirement: Mapping[str, str],
    *,
    kind: str,
    purpose: str,
) -> dict[str, Any]:
    minimum = str(requirement["minimum"])
    maximum = requirement.get("maximum_exclusive")
    try:
        actual = importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        actual = None
    passed = actual is not None and _version_in_range(actual, minimum, maximum)
    return {
        "id": f"python-package:{distribution}",
        "kind": kind,
        "required": True,
        "status": "PASS" if passed else "BLOCK",
        "minimum_version": minimum,
        "maximum_exclusive": maximum,
        "specifier": str(requirement["specifier"]),
        "version": actual,
        "reason": None
        if passed
        else (
            f"{distribution}{requirement['specifier']} is required for {purpose}"
            if actual is None
            else f"{distribution} {actual} is installed; {purpose} requires {requirement['specifier']}"
        ),
    }


def _check_test_requirement(distribution: str, requirement: Mapping[str, str]) -> dict[str, Any]:
    return _check_python_requirement(
        distribution,
        requirement,
        kind="test-only",
        purpose="standard/release verification",
    )


def check_test_dependencies() -> dict[str, Any]:
    checks = [
        _check_test_requirement(distribution, requirement)
        for distribution, requirement in TEST_REQUIREMENTS.items()
    ]
    blocking = [item for item in checks if item["status"] != "PASS"]
    requirements = [
        f"{distribution}{requirement['specifier']}"
        for distribution, requirement in TEST_REQUIREMENTS.items()
    ]
    return {
        "schema": "bbk.test-dependency-report.v1",
        "status": "BLOCK" if blocking else "PASS",
        "checks": checks,
        "blocking_count": len(blocking),
        "remediation_command": " ".join(
            [Path(sys.executable).name or "python", "-m", "pip", "install", "--upgrade", *requirements]
        ) if blocking else None,
        "network_accessed": False,
        "mutation_performed": False,
    }


def format_test_report(report: Mapping[str, Any]) -> str:
    lines = [f"BBK test dependency preflight: {report.get('status')}"]
    for item in report.get("checks", []):
        detail = item.get("version") or item.get("reason") or ""
        lines.append(f"[{item.get('status')}] {item.get('id')}: {detail}")
    if report.get("status") != "PASS":
        lines.extend(["", "Install the verification packages with:", f"  {report.get('remediation_command')}", "", "No BBK files were changed."])
    return "\n".join(lines)


def check_dependencies(
    harnesses: Iterable[str] | None = None,
    *,
    include_test_dependencies: bool = False,
    require_omp_node: bool | None = None,
    environment: Mapping[str, str] | None = None,
    root: Path = ROOT,
    check_hosts: bool = True,
) -> dict[str, Any]:
    """Evaluate the install contract without network access or tool installs."""
    source = dict(os.environ if environment is None else environment)
    contract = dependency_contract(
        harnesses,
        include_test_dependencies=include_test_dependencies,
        require_omp_node=require_omp_node,
        root=root,
    )
    selected = tuple(contract["selected_harnesses"])
    checks: list[dict[str, Any]] = [
        {
            "id": "python",
            "kind": "runtime",
            "required": True,
            "status": "PASS" if sys.version_info >= MINIMUM_PYTHON else "BLOCK",
            "path": sys.executable,
            "version": ".".join(map(str, sys.version_info[:3])),
            "minimum_version": MINIMUM_PYTHON_TEXT,
            "reason": None if sys.version_info >= MINIMUM_PYTHON else f"Python {MINIMUM_PYTHON_TEXT}+ is required",
        }
    ]
    git = _check_direct("git", environment=source)
    mise_check = _check_direct("mise", environment=source)
    checks.extend([git, mise_check])
    mise = Path(str(mise_check["path"])) if mise_check["status"] == "PASS" else None
    for record in managed_tool_contract(root):
        checks.append(_check_managed(record, mise=mise, environment=source, root=root))
    for distribution, requirement in RUNTIME_PYTHON_REQUIREMENTS.items():
        checks.append(
            _check_python_requirement(
                distribution,
                requirement,
                kind="python-runtime",
                purpose="BBK runtime schema validation",
            )
        )
    if contract["omp_node_required"]:
        node, version, source_kind = _resolve_node_runtime(
            environment=source,
            mise=mise,
            root=root,
        )
        checks.append(
            {
                "id": "node",
                "kind": "omp-runtime",
                "required": True,
                "status": "PASS" if node else "BLOCK",
                "path": str(node) if node else None,
                "version": version if node else None,
                "source": source_kind if node else None,
                "minimum_version": "22",
                "reason": None if node else str(source_kind),
            }
        )
    if include_test_dependencies:
        for distribution, requirement in TEST_REQUIREMENTS.items():
            checks.append(_check_test_requirement(distribution, requirement))

    host_checks: list[dict[str, Any]] = []
    if check_hosts:
        for harness in selected:
            command = HOST_COMMANDS[harness]
            if command is None:
                continue
            path = discover_executable(command, environment=source)
            host_checks.append(
                {
                    "id": f"host:{harness}",
                    "kind": "selected-host",
                    "required": False,
                    "status": "PASS" if path else "NOT_INSTALLED",
                    "command": command,
                    "path": str(path) if path else None,
                    "reason": None if path else f"the {harness} host command was not found; BBK files may be installed before the host",
                }
            )

    blocking = [item for item in checks if item.get("required") and item.get("status") != "PASS"]
    install_args = [f"--{name}" for name in selected]
    if include_test_dependencies:
        install_args.append("--include-test-dependencies")
    remediation_command = " ".join(
        [Path(sys.executable).name or "python", "tools/setup.py", "--install-dependencies", *install_args]
    )
    return {
        "schema": "bbk.install-dependency-report.v1",
        "status": "BLOCK" if blocking else "PASS",
        "python_minimum": MINIMUM_PYTHON_TEXT,
        "selected_harnesses": list(selected),
        "include_test_dependencies": include_test_dependencies,
        "omp_node_required": bool(contract["omp_node_required"]),
        "checks": checks,
        "host_checks": host_checks,
        "blocking_count": len(blocking),
        "warning_count": sum(1 for item in host_checks if item["status"] != "PASS"),
        "remediation_command": remediation_command if blocking else None,
        "network_accessed": False,
        "tool_installation_performed": False,
        "mutation_performed": False,
    }


def format_report(report: Mapping[str, Any]) -> str:
    lines = [f"BBK dependency preflight: {report.get('status')}"]
    for item in report.get("checks", []):
        detail = item.get("version") or item.get("reason") or item.get("path") or ""
        lines.append(f"[{item.get('status')}] {item.get('id')}: {detail}")
    for item in report.get("host_checks", []):
        detail = item.get("path") or item.get("reason") or ""
        lines.append(f"[{item.get('status')}] {item.get('id')}: {detail}")
    if report.get("status") != "PASS":
        lines.extend(["", "Install the missing BBK dependencies with:", f"  {report.get('remediation_command')}", "", "No BBK files were changed."])
    elif report.get("warning_count"):
        lines.append("Selected host warnings do not block installing BBK files.")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    for harness in HARNESS_ORDER:
        parser.add_argument(f"--{harness}", action="store_true")
    parser.add_argument("--include-test-dependencies", action="store_true")
    parser.add_argument("--no-host-checks", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = check_dependencies(
            selected_harnesses_from_namespace(args),
            include_test_dependencies=bool(args.include_test_dependencies),
            check_hosts=not bool(args.no_host_checks),
        )
    except DependencyError as exc:
        if args.json:
            print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"bbk dependencies: error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) if args.json else format_report(report))
    return 0 if report["status"] == "PASS" else 1


__all__ = [
    "DependencyError",
    "HARNESS_ORDER",
    "HOST_COMMANDS",
    "MINIMUM_PYTHON",
    "MINIMUM_PYTHON_TEXT",
    "READ_ONLY_MISE_ENVIRONMENT",
    "RUNTIME_PYTHON_REQUIREMENTS",
    "SUPPORTED_WINDOWS_SUFFIXES",
    "TEST_REQUIREMENTS",
    "check_dependencies",
    "check_test_dependencies",
    "command_argv",
    "command_with_node_runtime",
    "dependency_contract",
    "discover_executable",
    "format_report",
    "format_test_report",
    "managed_tool_contract",
    "readonly_mise_environment",
    "selected_harnesses",
    "selected_harnesses_from_namespace",
    "verification_environment",
]


if __name__ == "__main__":
    raise SystemExit(main())
