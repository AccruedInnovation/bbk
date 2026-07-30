#!/usr/bin/env python3
"""Verify a mutable BBK Git source checkout without release-manifest gates."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Check:
    name: str
    command: tuple[str, ...]
    optional: bool = False


def checks(require_node: bool) -> list[Check]:
    py = sys.executable
    values = [
        Check("Method-content projection drift", (py, "tools/create_method_content.py", "--check")),
        Check("Role-specification projection drift", (py, "tools/create_role_spec.py", "--check")),
    ]
    if (ROOT / "tools/model_routing.py").exists():
        values.append(Check("Model-routing policy", (py, "tools/model_routing.py", "--check")))
    values.extend([
        Check("Agent projection drift", (py, "tools/generate_agents.py", "--check")),
    ])
    if (ROOT / "tools/source_sanity.py").exists():
        values.append(Check("Python compilation and JSON parsing", (py, "tools/source_sanity.py")))
    if (ROOT / "tools/validate_alpha7_fixtures.py").exists():
        values.append(Check("Semantic and schema fixtures", (py, "tools/validate_alpha7_fixtures.py")))
    if (ROOT / "tools/validate_alpha8_fixtures.py").exists():
        values.append(Check("Typed profile-dispatch fixtures", (py, "tools/validate_alpha8_fixtures.py")))
    if (ROOT / "tools/run_tests.py").exists():
        values.append(Check("Ordered unittest corpus", (py, "tools/run_tests.py", "-v")))
    else:
        values.append(Check("Unittest corpus", (py, "-m", "unittest", "discover", "-s", "tests", "-v")))
    node = shutil.which("node")
    if node:
        values.append(Check("OMP extension JavaScript syntax", (node, "--check", "omp/extension/index.js")))
    elif require_node:
        values.append(Check("OMP extension JavaScript syntax", ("node", "--check", "omp/extension/index.js")))
    else:
        values.append(Check("OMP extension JavaScript syntax", (), optional=True))
    return values


def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-node", action="store_true")
    parser.add_argument("--failfast", action="store_true")
    args = parser.parse_args(argv)

    plan = checks(args.require_node)
    results: list[tuple[str, str, int | None]] = []
    for index, check in enumerate(plan, start=1):
        print(f"\n==> [{index}/{len(plan)}] {check.name}", flush=True)
        if not check.command:
            print("    SKIP — Node.js is unavailable; use --require-node to make this blocking.", flush=True)
            results.append((check.name, "SKIP", None))
            continue
        print("    " + " ".join(check.command), flush=True)
        try:
            completed = subprocess.run(
                list(check.command), cwd=ROOT,
                stdout=None, stderr=subprocess.STDOUT,
                check=False,
            )
            code = completed.returncode
        except OSError as exc:
            print(f"    ERROR: {type(exc).__name__}: {exc}", flush=True)
            code = 2
        state = "PASS" if code == 0 else "FAIL"
        results.append((check.name, state, code))
        print(f"<== {check.name}: {state}", flush=True)
        if code and args.failfast:
            break

    failed = [result for result in results if result[1] == "FAIL"]
    skipped = [result for result in results if result[1] == "SKIP"]
    print("\n" + "=" * 70)
    print("BBK SOURCE REPOSITORY VERIFICATION SUMMARY")
    print("=" * 70)
    print(f"Result: {'PASS' if not failed else 'FAILED'}")
    print(
        f"Checks: {len(results)}/{len(plan)} run; "
        f"{sum(state == 'PASS' for _, state, _ in results)} passed; "
        f"{len(failed)} failed; {len(skipped)} skipped; "
        f"{len(plan) - len(results)} not run"
    )
    if failed:
        print("\nFailures:")
        for name, _, code in failed:
            print(f"- {name}: exit code {code}")
    if skipped:
        print("\nSkipped:")
        for name, _, _ in skipped:
            print(f"- {name}")
    exit_code = 1 if failed else 0
    print(f"Exit code: {exit_code}")
    print("=" * 70)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(run())
