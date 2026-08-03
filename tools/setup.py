#!/usr/bin/env python3
"""One-command BBK testing, installation, and language-profile setup.

Preferred entry points::

    python tools/setup.py --test-fast
    python tools/setup.py --test
    python tools/setup.py --release-test
    python tools/setup.py --test-and-install --scope user --omp --codex
    python tools/setup.py --test-and-install --profile-id rust
    python tools/setup.py --test-and-install --no-language-profiles
    python tools/setup.py --update-omp --scope user
    python tools/setup.py --test-and-update-omp --scope user
    python tools/setup.py --update-codex --scope user
    python tools/setup.py --test-and-update-codex --scope user

Ordinary installs include every profile bundled with BBK. An explicit
``--language-profiles`` source replaces that bundled source for the invocation.
Routine ``--test`` and ``--test-and-install`` use the standard product,
integration, and platform profile. ``--release-test`` retains exhaustive
release-author self-tests and optional duplicate schema-engine checks. Selective
test-and-update modes use the matching trust-gated OMP or Codex profile.

The older ``--verify`` and ``--verify-and-install`` spellings remain aliases.
All ordinary diagnostics are kept on stdout for PowerShell 5.1 compatibility.
"""
from __future__ import annotations

import argparse
import contextlib
import sys
from typing import Sequence

import install as install_tool
import update_codex as update_codex_tool
import update_omp as update_omp_tool


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--test-fast", dest="test_fast", action="store_true",
        help="run canonical contract and deterministic-transformation checks",
    )
    action.add_argument(
        "--test", "--verify", dest="test", action="store_true",
        help="run the standard product, integration, and platform verification profile",
    )
    action.add_argument(
        "--release-test", dest="release_test", action="store_true",
        help="run exhaustive release qualification, including test-runner self-tests",
    )
    action.add_argument(
        "--install", action="store_true",
        help="preflight and install without first running the package test sequence",
    )
    action.add_argument(
        "--test-and-install", "--verify-and-install", "--verify-install",
        dest="test_and_install", action="store_true",
        help="run the standard verification profile and install only if every blocking check passes",
    )
    action.add_argument(
        "--release-test-and-install",
        dest="release_test_and_install", action="store_true",
        help="run exhaustive release qualification and install only on PASS",
    )
    action.add_argument(
        "--update-omp", action="store_true",
        help="update only the installed OMP surface; preserve Codex, Claude, and generic agent files",
    )
    action.add_argument(
        "--test-and-update-omp", "--verify-and-update-omp",
        dest="test_and_update_omp", action="store_true",
        help="run package trust/drift checks plus OMP-focused regressions, then update only OMP on PASS",
    )
    action.add_argument(
        "--update-codex", action="store_true",
        help="update only the installed Codex surface; preserve OMP, Claude, and generic agent files",
    )
    action.add_argument(
        "--test-and-update-codex", "--verify-and-update-codex",
        dest="test_and_update_codex", action="store_true",
        help="run package trust/drift checks plus Codex-focused regressions, then update only Codex on PASS",
    )
    parser.add_argument("--scope", choices=["user", "project"], default="user")
    parser.add_argument("--root", help="project root for project-scoped installation")
    parser.add_argument("--codex", action="store_true")
    parser.add_argument("--omp", action="store_true")
    parser.add_argument("--claude", action="store_true")
    parser.add_argument("--generic", action="store_true")
    parser.add_argument("--model-routing")
    parser.add_argument(
        "--language-profiles", "--profiles", "--profiles-bundle",
        dest="language_profiles", action="append", metavar="PATH",
        help="replace bundled profiles with a profile ZIP, extracted tree/repository, or verified release bundle; repeat as needed",
    )
    parser.add_argument(
        "--profile-id", "--profile", action="append", metavar="ID",
        help="select one profile id; repeat as needed; default is every bundled profile",
    )
    parser.add_argument(
        "--no-language-profiles", action="store_true",
        help="install BBK core only instead of the bundled language profiles",
    )
    existing = parser.add_mutually_exclusive_group()
    existing.add_argument(
        "--uninstall-existing", action="store_true",
        help="clean-replace one selected installed OMP/Codex harness while preserving peers; selecting every installed harness performs a full replacement",
    )
    existing.add_argument(
        "--keep-existing", action="store_true",
        help="retain a pre-existing BBK install and reconcile files in place",
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--failfast", action="store_true", help="stop verification after the first failed non-trust-gate check")
    parser.add_argument("--require-node", action="store_true")
    parser.add_argument(
        "--test-mode",
        choices=["auto", "pooled", "batch", "isolated"],
        default="auto",
        help="unittest process strategy for test-bearing actions (default: auto)",
    )
    parser.add_argument(
        "--test-jobs",
        type=int,
        default=0,
        help="unittest worker count; 0 selects a conservative automatic value (default: 0)",
    )
    parser.add_argument("--test-report", help="write the unittest timing/performance report to this path")
    parser.add_argument("--no-test-report", action="store_true", help="disable the default package-external unittest timing report")
    parser.add_argument("--json", action="store_true")
    return parser


def install_arguments(args: argparse.Namespace) -> list[str]:
    values = ["install", "--scope", args.scope]
    if args.root:
        values.extend(["--root", args.root])
    for flag in ("codex", "omp", "claude", "generic"):
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
    if args.test_and_install or args.release_test_and_install:
        values.extend([
            "--verify",
            "--verification-profile",
            "release" if args.release_test_and_install else "standard",
            "--test-mode",
            args.test_mode,
            "--test-jobs",
            str(args.test_jobs),
        ])
        if args.test_report:
            values.extend(["--timing-report", args.test_report])
        elif args.no_test_report:
            values.append("--no-timing-report")
        if args.failfast:
            values.append("--verification-failfast")
        if args.require_node:
            values.append("--require-node")
    return values


def update_omp_arguments(args: argparse.Namespace) -> list[str]:
    values = ["--scope", args.scope]
    if args.root:
        values.extend(["--root", args.root])
    if args.force:
        values.append("--force")
    if args.dry_run:
        values.append("--dry-run")
    if args.test_and_update_omp:
        values.append("--verify")
        if args.failfast:
            values.append("--verification-failfast")
    if args.json:
        values.append("--json")
    return values


def update_codex_arguments(args: argparse.Namespace) -> list[str]:
    values = ["--scope", args.scope]
    if args.root:
        values.extend(["--root", args.root])
    if args.force:
        values.append("--force")
    if args.dry_run:
        values.append("--dry-run")
    if args.test_and_update_codex:
        values.append("--verify")
        if args.failfast:
            values.append("--verification-failfast")
    if args.json:
        values.append("--json")
    return values


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    omp_update = bool(args.update_omp or args.test_and_update_omp)
    codex_update = bool(args.update_codex or args.test_and_update_codex)
    selective_update = bool(omp_update or codex_update)
    if args.test_jobs < 0:
        parser.error("--test-jobs must be zero or positive")
    if args.test_report and args.no_test_report:
        parser.error("--test-report and --no-test-report are mutually exclusive")
    pure_test = bool(args.test_fast or args.test or args.release_test)
    if pure_test and (
        args.language_profiles or args.profile_id or args.no_language_profiles or args.dry_run or args.force
        or args.uninstall_existing or args.keep_existing
        or args.model_routing or args.root or any(getattr(args, name) for name in ("codex", "omp", "claude", "generic"))
    ):
        parser.error("installation/profile selection options cannot be combined with a test-only action")
    if args.no_language_profiles and (args.language_profiles or args.profile_id):
        parser.error("--no-language-profiles cannot be combined with profile sources or --profile-id")
    if selective_update and (
        args.language_profiles or args.profile_id or args.no_language_profiles or args.model_routing
        or args.test_report or args.no_test_report
        or args.uninstall_existing or args.keep_existing
        or any(getattr(args, name) for name in ("codex", "omp", "claude", "generic"))
    ):
        target_name = "OMP-only" if omp_update else "Codex-only"
        article = "an" if omp_update else "a"
        parser.error(f"harness, model-routing, and language-profile selection options do not apply to {article} {target_name} update")
    if pure_test:
        profile = "fast" if args.test_fast else ("release" if args.release_test else "standard")
        values = [
            "verify",
            "--profile",
            profile,
            "--test-mode",
            args.test_mode,
            "--test-jobs",
            str(args.test_jobs),
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
        values = update_omp_arguments(args)
        target = update_omp_tool.main
    elif codex_update:
        values = update_codex_arguments(args)
        target = update_codex_tool.main
    else:
        values = install_arguments(args)
        if args.json:
            values.insert(0, "--json")
        target = install_tool.main
    with contextlib.redirect_stderr(sys.stdout):
        return target(values)


if __name__ == "__main__":
    raise SystemExit(main())
