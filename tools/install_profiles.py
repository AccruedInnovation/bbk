#!/usr/bin/env python3
"""Verify and install BBK with language profiles.

With no ``--bundle`` argument this wrapper installs every profile bundled in the
BBK archive. Supplying ``--bundle`` replaces the bundled source for that run.
The core installer verifies every package, preflights all destinations, and
records core plus profile files in one install manifest.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from runtime_requirements import enforce_supported_python

enforce_supported_python(program="BBK profile installer")

import setup as setup_tool


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", help="replacement profile-bundle ZIP or extracted directory; default is the bundled set")
    parser.add_argument("--profile", action="append", help="install only this profile id; repeat as needed")
    parser.add_argument("--scope", choices=["user", "project"], default="user")
    parser.add_argument("--root")
    parser.add_argument("--codex", action="store_true")
    parser.add_argument("--omp", action="store_true")
    parser.add_argument("--claude", action="store_true")
    parser.add_argument("--generic", action="store_true")
    parser.add_argument("--model-routing")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-verification", action="store_true")
    parser.add_argument("--failfast", action="store_true")
    parser.add_argument("--require-node", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    values = ["--install" if args.skip_verification else "--test-and-install", "--scope", args.scope]
    if args.root:
        values.extend(["--root", args.root])
    for flag in ("codex", "omp", "claude", "generic"):
        if getattr(args, flag):
            values.append(f"--{flag}")
    if args.model_routing:
        values.extend(["--model-routing", args.model_routing])
    if args.bundle:
        values.extend(["--language-profiles", args.bundle])
    for profile_id in args.profile or []:
        values.extend(["--profile-id", profile_id])
    for flag in ("force", "dry_run", "failfast", "require_node", "json"):
        if getattr(args, flag):
            values.append("--" + flag.replace("_", "-"))
    return setup_tool.main(values)


if __name__ == "__main__":
    raise SystemExit(main())
