#!/usr/bin/env python3
"""Verify and install BBK from sibling Git source repositories."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]


def sibling_profiles() -> Path | None:
    candidate = ROOT.parent / "bbk-language-profiles"
    if (candidate / "REPOSITORY-MANIFEST.json").is_file() or (candidate / "packages").is_dir():
        return candidate
    return None


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    action = value.add_mutually_exclusive_group(required=True)
    action.add_argument("--verify", action="store_true")
    action.add_argument("--install", action="store_true")
    action.add_argument("--test-and-install", action="store_true")
    value.add_argument("--scope", choices=["user", "project"], default="user")
    value.add_argument("--root")
    for flag in ("omp", "codex", "claude", "generic"):
        value.add_argument(f"--{flag}", action="store_true")
    value.add_argument("--language-profiles", action="append", metavar="PATH")
    value.add_argument("--profile-id", action="append")
    value.add_argument("--no-language-profiles", action="store_true")
    value.add_argument("--model-routing")
    value.add_argument("--force", action="store_true")
    value.add_argument("--dry-run", action="store_true")
    value.add_argument("--require-node", action="store_true")
    value.add_argument("--failfast", action="store_true")
    return value


def call(command: list[str]) -> int:
    print("    " + " ".join(command), flush=True)
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)

    if args.verify or args.test_and_install:
        command = [sys.executable, "tools/verify_source_repository.py"]
        if args.require_node:
            command.append("--require-node")
        if args.failfast:
            command.append("--failfast")
        print("==> Verifying mutable BBK source checkout", flush=True)
        code = call(command)
        if code:
            print("BBK source verification failed; installation was not started.", flush=True)
            return code
        print("<== Source verification: PASS", flush=True)
        if args.verify:
            return 0

    command = [sys.executable, "tools/setup.py", "--install", "--scope", args.scope]
    if args.root:
        command.extend(["--root", args.root])
    for flag in ("omp", "codex", "claude", "generic"):
        if getattr(args, flag):
            command.append(f"--{flag}")
    if args.model_routing:
        command.extend(["--model-routing", args.model_routing])
    if args.force:
        command.append("--force")
    if args.dry_run:
        command.append("--dry-run")

    if args.no_language_profiles:
        command.append("--no-language-profiles")
    else:
        sources = [Path(item).expanduser().resolve() for item in (args.language_profiles or [])]
        if not sources:
            detected = sibling_profiles()
            if detected is None:
                print(
                    "No language-profile source was supplied and ../bbk-language-profiles was not found.\n"
                    "Use --language-profiles PATH or --no-language-profiles.",
                    file=sys.stderr,
                )
                return 2
            sources = [detected]
            print(f"==> Auto-detected sibling language-profile repository: {detected}", flush=True)
        for source in sources:
            command.extend(["--language-profiles", str(source)])
        for profile_id in args.profile_id or []:
            command.extend(["--profile-id", profile_id])

    print("==> Installing from source repository", flush=True)
    code = call(command)
    print(f"<== Installation: {'PASS' if code == 0 else 'FAIL'}", flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
