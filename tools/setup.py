#!/usr/bin/env python3
"""One-command BBK dependency setup, testing, installation, and updates.

Preferred entry points::

    python tools/setup.py --check-dependencies --codex
    python tools/setup.py --install-dependencies --codex
    python tools/setup.py --install --scope user --codex
    python tools/setup.py --test-and-install --scope user --codex
    python tools/setup.py --test-and-install --scope user --omp
    python tools/setup.py --test
    python tools/setup.py --release-test

The dependency preflight runs before tests or file writes. It disables network
access and automatic tool installation. ``--install-dependencies`` is the
explicit opt-in bootstrap.
Codex-only verification uses the Codex profile and does not require Node.js.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path
from typing import Mapping, Sequence

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from runtime_requirements import enforce_supported_python

enforce_supported_python(program="BBK setup")

import dependencies
import install as install_tool
import install_dependencies as dependency_installer
import update_codex as update_codex_tool
import update_omp as update_omp_tool


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--check-dependencies",
        action="store_true",
        help="run the offline, non-installing dependency preflight",
    )
    action.add_argument(
        "--install-dependencies",
        action="store_true",
        help="install declared dependencies after consent; does not install agent host apps",
    )
    action.add_argument(
        "--test-fast",
        action="store_true",
        help="run canonical contract and deterministic-transformation checks",
    )
    action.add_argument(
        "--test", "--verify", dest="test", action="store_true",
        help="run verification; --codex and --omp select host-focused profiles",
    )
    action.add_argument(
        "--release-test",
        action="store_true",
        help="run exhaustive release qualification, including test-runner self-tests",
    )
    action.add_argument(
        "--install",
        action="store_true",
        help="preflight and install without first running tests",
    )
    action.add_argument(
        "--test-and-install", "--verify-and-install", "--verify-install",
        dest="test_and_install",
        action="store_true",
        help="run the host-aware verification profile and install only on PASS",
    )
    action.add_argument(
        "--release-test-and-install",
        action="store_true",
        help="run release qualification and install only on PASS",
    )
    action.add_argument(
        "--update-omp",
        action="store_true",
        help="update only OMP and preserve Codex and other installed harnesses",
    )
    action.add_argument(
        "--test-and-update-omp", "--verify-and-update-omp",
        dest="test_and_update_omp", action="store_true",
    )
    action.add_argument(
        "--update-codex",
        action="store_true",
        help="update only Codex and preserve OMP and other installed harnesses",
    )
    action.add_argument(
        "--test-and-update-codex", "--verify-and-update-codex",
        dest="test_and_update_codex", action="store_true",
    )

    parser.add_argument("--scope", choices=["user", "project"], default="user")
    parser.add_argument("--root", help="project root for project-scoped installation")
    for harness in dependencies.HARNESS_ORDER:
        parser.add_argument(f"--{harness}", action="store_true")
    parser.add_argument("--model-routing")
    parser.add_argument(
        "--language-profiles", "--profiles", "--profiles-bundle",
        dest="language_profiles", action="append", metavar="PATH",
        help="replace bundled profiles with one or more profile sources",
    )
    parser.add_argument(
        "--profile-id", "--profile", action="append", metavar="ID",
        help="select one profile id; repeat as needed",
    )
    parser.add_argument("--no-language-profiles", action="store_true")
    existing = parser.add_mutually_exclusive_group()
    existing.add_argument("--uninstall-existing", action="store_true")
    existing.add_argument("--keep-existing", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--failfast", action="store_true")
    parser.add_argument("--require-node", action="store_true")
    parser.add_argument(
        "--test-mode",
        choices=["auto", "pooled", "batch", "isolated"],
        default="auto",
    )
    parser.add_argument("--test-jobs", type=int, default=0)
    parser.add_argument("--test-report")
    parser.add_argument("--no-test-report", action="store_true")

    parser.add_argument(
        "--include-test-dependencies",
        action="store_true",
        help="with a dependency action, also check or install any test-only Python packages",
    )
    parser.add_argument(
        "--package-manager",
        default="auto",
        choices=(
            "auto", "scoop", "winget", "choco", "brew", "port",
            "apt-get", "dnf", "yum", "pacman", "zypper", "apk",
        ),
        help="with --install-dependencies, select the system package manager",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="with --install-dependencies, approve non-interactive changes",
    )
    parser.add_argument("--json", action="store_true")
    return parser


def selected_harnesses(args: argparse.Namespace) -> tuple[str, ...]:
    return dependencies.selected_harnesses_from_namespace(args)


def install_verification_profile(args: argparse.Namespace) -> str:
    if args.release_test_and_install:
        return "release"
    selected = selected_harnesses(args)
    if selected == ("codex",):
        return "codex"
    if selected == ("omp",):
        return "omp"
    return "standard"


def emit_dependency_report(report: Mapping[str, object], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print(dependencies.format_report(report))


def install_arguments(
    args: argparse.Namespace,
    *,
    profile: str | None = None,
) -> list[str]:
    if profile is None and (args.test_and_install or args.release_test_and_install):
        profile = install_verification_profile(args)
    values = ["install", "--scope", args.scope]
    if args.root:
        values.extend(["--root", args.root])
    for flag in dependencies.HARNESS_ORDER:
        if getattr(args, flag):
            values.append(f"--{flag}")
    if args.model_routing:
        values.extend(["--model-routing", args.model_routing])
    for source in args.language_profiles or []:
        values.extend(["--language-profiles", source])
    for profile_id in args.profile_id or []:
        values.extend(["--profile-id", profile_id])
    if args.no_language_profiles:
        values.append("--no-language-profiles")
    if args.uninstall_existing:
        values.append("--uninstall-existing")
    if args.keep_existing:
        values.append("--keep-existing")
    if args.force:
        values.append("--force")
    if args.dry_run:
        values.append("--dry-run")
    if profile is not None:
        values.extend(
            [
                "--verify",
                "--verification-profile",
                profile,
                "--test-mode",
                args.test_mode,
                "--test-jobs",
                str(args.test_jobs),
            ]
        )
        if args.test_report:
            values.extend(["--timing-report", args.test_report])
        elif args.no_test_report:
            values.append("--no-timing-report")
        if args.failfast:
            values.append("--verification-failfast")
        if args.require_node:
            values.append("--require-node")
    return values


def update_arguments(args: argparse.Namespace, *, harness: str) -> list[str]:
    values = ["--scope", args.scope]
    if args.root:
        values.extend(["--root", args.root])
    if args.force:
        values.append("--force")
    if args.dry_run:
        values.append("--dry-run")
    verify = args.test_and_update_omp if harness == "omp" else args.test_and_update_codex
    if verify:
        values.append("--verify")
        if args.failfast:
            values.append("--verification-failfast")
    if args.json:
        values.append("--json")
    return values


def dependency_installer_arguments(args: argparse.Namespace) -> list[str]:
    values: list[str] = []
    for harness in dependencies.HARNESS_ORDER:
        if getattr(args, harness):
            values.append(f"--{harness}")
    if args.include_test_dependencies:
        values.append("--include-test-dependencies")
    if args.package_manager != "auto":
        values.extend(["--package-manager", args.package_manager])
    if args.yes:
        values.append("--yes")
    if args.dry_run:
        values.append("--dry-run")
    if args.json:
        values.append("--json")
    return values


def _validate_options(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.test_jobs < 0:
        parser.error("--test-jobs must be zero or positive")
    if args.test_report and args.no_test_report:
        parser.error("--test-report and --no-test-report are mutually exclusive")
    if args.no_language_profiles and (args.language_profiles or args.profile_id):
        parser.error("--no-language-profiles cannot be combined with profile sources or --profile-id")

    dependency_action = bool(args.check_dependencies or args.install_dependencies)
    if not dependency_action and (args.include_test_dependencies or args.package_manager != "auto" or args.yes):
        parser.error("--include-test-dependencies, --package-manager, and --yes apply only to dependency actions")
    if args.check_dependencies and args.dry_run:
        parser.error("--dry-run is unnecessary with the non-installing --check-dependencies action")

    pure_test = bool(args.test_fast or args.test or args.release_test)
    if pure_test and (
        args.language_profiles or args.profile_id or args.no_language_profiles or args.dry_run
        or args.force or args.uninstall_existing or args.keep_existing or args.model_routing
        or args.root
    ):
        parser.error("installation options cannot be combined with a test-only action")
    explicit_test_harnesses = tuple(
        name for name in dependencies.HARNESS_ORDER if getattr(args, name)
    )
    if (args.test_fast or args.release_test) and explicit_test_harnesses:
        parser.error("host selection applies only to --test")
    if args.test and explicit_test_harnesses not in {(), ("codex",), ("omp",)}:
        parser.error("--test accepts either --codex or --omp as its sole host selection")
    if args.test_fast and args.require_node:
        parser.error("--test-fast is host-neutral and cannot be combined with --require-node")

    selective_update = bool(
        args.update_omp or args.test_and_update_omp or args.update_codex or args.test_and_update_codex
    )
    if selective_update and (
        args.language_profiles or args.profile_id or args.no_language_profiles or args.model_routing
        or args.test_report or args.no_test_report or args.uninstall_existing or args.keep_existing
        or any(getattr(args, name) for name in dependencies.HARNESS_ORDER)
    ):
        target = "an OMP-only update" if (args.update_omp or args.test_and_update_omp) else "a Codex-only update"
        parser.error(f"host, model-routing, profile, and test-report options do not apply to {target}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _validate_options(parser, args)

    if args.install_dependencies:
        with contextlib.redirect_stderr(sys.stdout):
            return dependency_installer.main(dependency_installer_arguments(args))

    if args.check_dependencies:
        try:
            report = dependencies.check_dependencies(
                selected_harnesses(args),
                include_test_dependencies=bool(args.include_test_dependencies),
            )
        except dependencies.DependencyError as exc:
            if args.json:
                print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False))
            else:
                print(f"BBK dependency preflight error: {exc}")
            return 2
        emit_dependency_report(report, as_json=bool(args.json))
        return 0 if report["status"] == "PASS" else 2

    omp_update = bool(args.update_omp or args.test_and_update_omp)
    codex_update = bool(args.update_codex or args.test_and_update_codex)
    pure_test = bool(args.test_fast or args.test or args.release_test)

    if pure_test:
        if args.test_fast:
            profile = "fast"
            harnesses = ("generic",)
        elif args.release_test:
            profile = "release"
            harnesses = dependencies.HARNESS_ORDER
        else:
            explicit = tuple(
                name for name in dependencies.HARNESS_ORDER if getattr(args, name)
            )
            profile = explicit[0] if explicit in {("codex",), ("omp",)} else "standard"
            harnesses = explicit or dependencies.HARNESS_ORDER
    elif omp_update:
        profile = "omp" if args.test_and_update_omp else None
        harnesses = ("omp",)
    elif codex_update:
        profile = "codex" if args.test_and_update_codex else None
        harnesses = ("codex",)
    else:
        profile = install_verification_profile(args) if (args.test_and_install or args.release_test_and_install) else None
        harnesses = selected_harnesses(args)

    if profile == "codex" and args.require_node:
        parser.error("Codex-only verification does not use Node.js; remove --require-node")

    if pure_test:
        values = [
            "verify", "--profile", profile or "standard",
            "--test-mode", args.test_mode,
            "--test-jobs", str(args.test_jobs),
        ]
        if args.test_report:
            values.extend(["--timing-report", args.test_report])
        elif args.no_test_report:
            values.append("--no-timing-report")
        if args.failfast:
            values.append("--failfast")
        if args.require_node:
            values.append("--require-node")
        if args.json:
            values.insert(0, "--json")
        target = install_tool.main
    elif omp_update:
        values = update_arguments(args, harness="omp")
        target = update_omp_tool.main
    elif codex_update:
        values = update_arguments(args, harness="codex")
        target = update_codex_tool.main
    else:
        values = install_arguments(args, profile=profile)
        if args.json:
            values.insert(0, "--json")
        target = install_tool.main

    with contextlib.redirect_stderr(sys.stdout):
        return target(values)


if __name__ == "__main__":
    raise SystemExit(main())
