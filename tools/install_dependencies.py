#!/usr/bin/env python3
"""Install BBK's declared dependencies after explicit user consent.

Python 3.11+ is the bootstrap requirement for this script. The script can
install Git, mise, BBK's pinned jj and Beads versions, the Python schema
packages used at runtime, and Node.js when OMP is selected.
``--include-test-dependencies`` also installs any packages used only by
verification. Agent host programs remain separate and are reported, not
installed or updated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Mapping, Sequence

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from runtime_requirements import enforce_supported_python

enforce_supported_python(program="BBK dependency installer")

import dependencies

ROOT = TOOLS_DIR.parent
MISE_INSTALL_URL = "https://mise.run"


class BootstrapError(RuntimeError):
    pass


def _sudo_prefix() -> list[str]:
    if os.name == "nt" or getattr(os, "geteuid", lambda: 1)() == 0:
        return []
    sudo = shutil.which("sudo")
    if not sudo:
        raise BootstrapError("system package installation needs root or sudo")
    return [sudo]


def detect_package_manager(
    requested: str = "auto",
    *,
    environment: Mapping[str, str] | None = None,
) -> str | None:
    source = dict(os.environ if environment is None else environment)
    if os.name == "nt":
        candidates = ("winget", "scoop", "choco")
    elif sys.platform == "darwin":
        candidates = ("brew", "port")
    else:
        candidates = ("apt-get", "dnf", "yum", "pacman", "zypper", "apk")
    if requested != "auto":
        if requested not in candidates:
            raise BootstrapError(
                f"package manager {requested!r} is not supported on this platform"
            )
        if dependencies.discover_executable(requested, environment=source) is None:
            raise BootstrapError(f"requested package manager {requested!r} was not found")
        return requested
    return next(
        (name for name in candidates if dependencies.discover_executable(name, environment=source)),
        None,
    )


def system_install_commands(
    manager: str | None,
    *,
    need_git: bool,
    need_mise: bool,
) -> list[list[str]]:
    """Return package-manager commands for direct system dependencies.

    Node, jj, and Beads are installed from the package-root mise contract, not
    from platform package managers.
    """
    if not need_git and not need_mise:
        return []
    if manager == "scoop":
        packages = [name for name, needed in (("git", need_git), ("mise", need_mise)) if needed]
        return [["scoop", "install", *packages]] if packages else []
    if manager == "winget":
        result: list[list[str]] = []
        for package_id, needed in (("Git.Git", need_git), ("jdx.mise", need_mise)):
            if needed:
                result.append(
                    [
                        "winget", "install", "--id", package_id, "--exact",
                        "--accept-package-agreements", "--accept-source-agreements", "--silent",
                    ]
                )
        return result
    if manager == "choco":
        packages = [name for name, needed in (("git", need_git), ("mise", need_mise)) if needed]
        return [["choco", "install", *packages, "-y"]] if packages else []
    if manager == "brew":
        packages = [name for name, needed in (("git", need_git), ("mise", need_mise)) if needed]
        return [["brew", "install", *packages]] if packages else []
    if manager == "port":
        packages = [name for name, needed in (("git", need_git), ("mise", need_mise)) if needed]
        return [[*_sudo_prefix(), "port", "install", *packages]] if packages else []

    packages = ["git"] if need_git else []
    if manager in {"pacman", "apk"} and need_mise:
        packages.append("mise")
    if manager == "apt-get" and packages:
        return [
            [*_sudo_prefix(), "apt-get", "update"],
            [*_sudo_prefix(), "apt-get", "install", "-y", "ca-certificates", *packages],
        ]
    if manager in {"dnf", "yum"} and packages:
        return [[*_sudo_prefix(), manager, "install", "-y", "ca-certificates", *packages]]
    if manager == "pacman" and packages:
        return [[*_sudo_prefix(), "pacman", "-S", "--needed", "--noconfirm", "ca-certificates", *packages]]
    if manager == "zypper" and packages:
        return [[*_sudo_prefix(), "zypper", "--non-interactive", "install", "ca-certificates", *packages]]
    if manager == "apk" and packages:
        return [[*_sudo_prefix(), "apk", "add", "ca-certificates", *packages]]
    return []


def _display_command(command: Sequence[str]) -> str:
    return " ".join(str(value) for value in command)


def run_command(
    command: Sequence[str],
    *,
    environment: Mapping[str, str] | None = None,
    cwd: Path = ROOT,
    echo: bool = True,
) -> str:
    if echo:
        print(f"==> {_display_command(command)}", flush=True)
    kwargs: dict[str, Any] = {
        "cwd": cwd,
        "env": dict(os.environ if environment is None else environment),
        "stdin": None,
        "check": False,
    }
    if not echo:
        kwargs.update(
            {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
                "text": True,
                "encoding": "utf-8",
                "errors": "backslashreplace",
            }
        )
    try:
        completed = subprocess.run(list(command), **kwargs)
    except OSError as exc:
        raise BootstrapError(f"could not start {_display_command(command)}: {exc}") from exc
    output = str(getattr(completed, "stdout", "") or "")
    if completed.returncode != 0:
        tail = " ".join(output.split())[-500:]
        detail = f"; output: {tail}" if tail else ""
        raise BootstrapError(
            f"command failed with exit code {completed.returncode}: {_display_command(command)}{detail}"
        )
    return output


def install_mise_user_local(
    *,
    environment: Mapping[str, str] | None = None,
    echo: bool = True,
) -> Path:
    """Run the official mise installer into the current user's local bin dir."""
    if os.name == "nt":
        raise BootstrapError("Windows mise installation requires winget, Scoop, or Chocolatey")
    source = dict(os.environ if environment is None else environment)
    home = Path(source.get("HOME") or str(Path.home())).expanduser()
    destination = home / ".local" / "bin" / "mise"
    with tempfile.TemporaryDirectory(prefix="bbk-mise-installer-") as raw_temp:
        installer = Path(raw_temp) / "install-mise.sh"
        try:
            with urllib.request.urlopen(MISE_INSTALL_URL, timeout=60) as response:
                payload = response.read(2_000_001)
        except OSError as exc:
            raise BootstrapError(f"could not download {MISE_INSTALL_URL}: {exc}") from exc
        if not payload or len(payload) > 2_000_000:
            raise BootstrapError("the mise installer response was empty or unexpectedly large")
        installer.write_bytes(payload)
        if echo:
            digest = hashlib.sha256(payload).hexdigest()
            print(f"Downloaded {MISE_INSTALL_URL} (SHA-256 {digest})", flush=True)
        install_environment = dict(source)
        install_environment.update(
            {
                "MISE_INSTALL_PATH": str(destination),
                "MISE_INSTALL_SKIP_IF_EXISTS": "1",
            }
        )
        run_command(
            ["/bin/sh", str(installer)],
            environment=install_environment,
            echo=echo,
        )
    if not destination.is_file():
        raise BootstrapError(f"mise installer completed but {destination} was not created")
    return destination


def managed_install_environment(source: Mapping[str, str] | None = None) -> dict[str, str]:
    environment = dict(os.environ if source is None else source)
    environment.update(
        {
            "MISE_YES": "1",
            "MISE_NO_DOTENV": "1",
            "MISE_AUTO_INSTALL": "0",
            "MISE_EXEC_AUTO_INSTALL": "0",
            "MISE_NOT_FOUND_AUTO_INSTALL": "0",
            "MISE_OFFLINE": "0",
            "NO_COLOR": "1",
            "CLICOLOR": "0",
        }
    )
    return environment


def planned_managed_specs(harnesses: Sequence[str] = ()) -> list[str]:
    return [
        str(item["tool_spec"])
        for item in dependencies.managed_tool_contract(include_node="omp" in set(harnesses))
    ]


def planned_python_requirements(*, include_test_dependencies: bool = False) -> list[str]:
    requirements = dict(dependencies.RUNTIME_PYTHON_REQUIREMENTS)
    if include_test_dependencies:
        requirements.update(dependencies.TEST_REQUIREMENTS)
    return [
        f"{distribution}{requirement['specifier']}"
        for distribution, requirement in requirements.items()
    ]


def pip_available(*, environment: Mapping[str, str] | None = None) -> bool:
    source = dict(os.environ if environment is None else environment)
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            cwd=ROOT,
            env=source,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def _confirmation(plan: Sequence[str], *, assume_yes: bool) -> None:
    if not plan or assume_yes:
        return
    if not sys.stdin.isatty():
        raise BootstrapError("dependency installation needs --yes when stdin is not interactive")
    print("\nThe commands above may download software and change user or system packages.")
    answer = input("Continue? [y/N] ").strip().lower()
    if answer not in {"y", "yes"}:
        raise BootstrapError("dependency installation cancelled")


def install_dependencies(args: argparse.Namespace) -> dict[str, Any]:
    harnesses = dependencies.selected_harnesses_from_namespace(args)
    include_tests = bool(args.include_test_dependencies)
    before = dependencies.check_dependencies(
        harnesses,
        include_test_dependencies=include_tests,
    )
    if before["status"] == "PASS":
        return {
            "schema": "bbk.dependency-bootstrap-result.v1",
            "status": "PASS",
            "changed": False,
            "selected_harnesses": list(harnesses),
            "include_test_dependencies": include_tests,
            "before": before,
            "after": before,
            "commands": [],
        }

    source = os.environ.copy()
    missing = {item["id"] for item in before["checks"] if item["status"] != "PASS"}
    need_git = "git" in missing
    need_mise = "mise" in missing
    need_system = need_git or need_mise
    manager = detect_package_manager(args.package_manager, environment=source) if need_system else None
    system_mise_managers = {"brew", "port", "pacman", "apk"}
    use_official_mise = (
        need_mise
        and os.name != "nt"
        and manager not in system_mise_managers
    )

    if need_git and manager is None:
        raise BootstrapError("Git is missing and no supported system package manager was found")
    if need_mise and os.name == "nt" and manager is None:
        raise BootstrapError("mise is missing and winget, Scoop, or Chocolatey was not found")

    system_commands = system_install_commands(
        manager,
        need_git=need_git,
        need_mise=need_mise and not use_official_mise,
    )
    managed_specs = [
        str(item["tool_spec"])
        for item in dependencies.managed_tool_contract(include_node="omp" in harnesses)
        if item["id"] in missing
    ]
    declared_python_requirements = dict(dependencies.RUNTIME_PYTHON_REQUIREMENTS)
    if include_tests:
        declared_python_requirements.update(dependencies.TEST_REQUIREMENTS)
    python_requirements = [
        f"{distribution}{requirement['specifier']}"
        for distribution, requirement in declared_python_requirements.items()
        if f"python-package:{distribution}" in missing
    ]
    need_pip_bootstrap = bool(python_requirements) and not pip_available(environment=source)

    displayed = [_display_command(command) for command in system_commands]
    if use_official_mise:
        displayed.append(f"download and run {MISE_INSTALL_URL} into ~/.local/bin/mise")
    displayed.extend(f"mise install {spec}" for spec in managed_specs)
    if need_pip_bootstrap:
        displayed.append(_display_command([sys.executable, "-m", "ensurepip", "--upgrade"]))
    if python_requirements:
        displayed.append(
            _display_command([sys.executable, "-m", "pip", "install", "--upgrade", *python_requirements])
        )

    if not args.json:
        print("BBK dependency installation plan:")
        for item in displayed:
            print(f"  - {item}")
    if args.dry_run:
        return {
            "schema": "bbk.dependency-bootstrap-result.v1",
            "status": "DRY_RUN",
            "changed": False,
            "selected_harnesses": list(harnesses),
            "include_test_dependencies": include_tests,
            "before": before,
            "commands": displayed,
            "package_manager": manager,
        }
    _confirmation(displayed, assume_yes=bool(args.yes))

    echo = not bool(args.json)
    for command in system_commands:
        executable = dependencies.discover_executable(command[0], environment=source)
        actual = dependencies.command_argv(
            executable or command[0],
            command[1:],
            environment=source,
        )
        run_command(actual, environment=source, echo=echo)

    mise = dependencies.discover_executable("mise", environment=source)
    if mise is None and use_official_mise:
        mise = install_mise_user_local(environment=source, echo=echo)
    if managed_specs and mise is None:
        mise = dependencies.discover_executable("mise", environment=source)
    if managed_specs and mise is None:
        raise BootstrapError(
            "mise was installed but is not visible in this process; start a new shell and rerun this script"
        )

    managed_environment = managed_install_environment(source)
    for spec in managed_specs:
        command = dependencies.command_argv(
            mise or "mise",
            ["install", spec],
            environment=managed_environment,
        )
        run_command(command, environment=managed_environment, echo=echo)

    if need_pip_bootstrap:
        run_command(
            [sys.executable, "-m", "ensurepip", "--upgrade"],
            environment=source,
            echo=echo,
        )
        if not pip_available(environment=source):
            raise BootstrapError(
                "pip is unavailable and Python's ensurepip bootstrap did not make it available; "
                "install pip for this Python 3.11+ interpreter and rerun"
            )
    if python_requirements:
        run_command(
            [sys.executable, "-m", "pip", "install", "--upgrade", *python_requirements],
            environment=source,
            echo=echo,
        )

    after = dependencies.check_dependencies(
        harnesses,
        include_test_dependencies=include_tests,
        environment=source,
    )
    if after["status"] != "PASS":
        raise BootstrapError(
            "dependency installation completed, but preflight still reports blocking items; "
            "start a new shell and rerun this script with the same host flags"
        )
    return {
        "schema": "bbk.dependency-bootstrap-result.v1",
        "status": "PASS",
        "changed": True,
        "selected_harnesses": list(harnesses),
        "include_test_dependencies": include_tests,
        "before": before,
        "after": after,
        "commands": displayed,
        "package_manager": manager,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    for harness in dependencies.HARNESS_ORDER:
        parser.add_argument(f"--{harness}", action="store_true")
    parser.add_argument(
        "--include-test-dependencies",
        action="store_true",
        help="also install compatible Python packages used by standard/release verification",
    )
    parser.add_argument(
        "--package-manager",
        default="auto",
        choices=(
            "auto",
            "scoop",
            "winget",
            "choco",
            "brew",
            "port",
            "apt-get",
            "dnf",
            "yum",
            "pacman",
            "zypper",
            "apk",
        ),
    )
    parser.add_argument("--yes", action="store_true", help="approve non-interactive installation")
    parser.add_argument("--dry-run", action="store_true", help="show the install plan without changing the system")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = install_dependencies(args)
    except (BootstrapError, dependencies.DependencyError) as exc:
        if args.json:
            print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"bbk dependencies: error: {exc}", file=sys.stderr)
            print("No BBK installation files were changed.", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    elif result["status"] == "DRY_RUN":
        print("BBK dependency installation: DRY RUN")
    else:
        print(dependencies.format_report(result["after"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
