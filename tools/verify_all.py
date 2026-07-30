#!/usr/bin/env python3
"""Run the complete BBK verification sequence in deterministic order.

This is the one-command package verification entry point. It verifies package
integrity before executing package code, checks every generated surface,
compiles Python, parses JSON, validates semantic fixtures, runs every unittest
module in filename order, validates the OMP extension when Node.js is present,
and re-verifies package integrity after the run. Child stderr is merged into
stdout for PowerShell-safe reporting, and a final summary repeats every failed
check and its terminal cause.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence, TextIO

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class CheckSpec:
    name: str
    command: tuple[str, ...]
    optional_reason: str | None = None
    trust_gate: bool = False


@dataclass(frozen=True)
class CheckResult:
    name: str
    command: tuple[str, ...]
    status: str
    returncode: int | None
    output: str
    cause: str | None = None

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    @property
    def skipped(self) -> bool:
        return self.status == "SKIP"


def verification_steps(*, require_node: bool = False, skip_package_manifest: bool = False) -> list[CheckSpec]:
    python = sys.executable
    steps: list[CheckSpec] = []
    if not skip_package_manifest:
        steps.append(
            CheckSpec(
                "Package manifest integrity (pre-execution trust gate)",
                (python, "tools/verify_package.py", "--strict-mode"),
                trust_gate=True,
            )
        )
    steps.extend(
        [
            CheckSpec("Method-content projection drift", (python, "tools/create_method_content.py", "--check")),
            CheckSpec("Role-specification projection drift", (python, "tools/create_role_spec.py", "--check")),
            CheckSpec("Model-routing policy", (python, "tools/model_routing.py", "--check")),
            CheckSpec("Agent projection drift", (python, "tools/generate_agents.py", "--check")),
            CheckSpec("Python compilation and JSON parsing", (python, "tools/source_sanity.py")),
            CheckSpec("Alpha.7 semantic fixtures", (python, "tools/validate_alpha7_fixtures.py")),
            CheckSpec("Alpha.8 typed-profile fixtures", (python, "tools/validate_alpha8_fixtures.py")),
            CheckSpec("All unittest suites", (python, "tools/run_tests.py", "-v")),
        ]
    )
    node = shutil.which("node")
    if node:
        steps.append(CheckSpec("OMP extension JavaScript syntax", (node, "--check", "omp/extension/index.js")))
    elif require_node:
        steps.append(CheckSpec("OMP extension JavaScript syntax", ("node", "--check", "omp/extension/index.js")))
    else:
        steps.append(
            CheckSpec(
                "OMP extension JavaScript syntax",
                (),
                "Node.js is unavailable; use --require-node to make this a blocking check.",
            )
        )
    if not skip_package_manifest:
        steps.append(
            CheckSpec(
                "Package manifest integrity (post-test mutation check)",
                (python, "tools/verify_package.py", "--strict-mode"),
            )
        )
    return steps


def command_text(command: Sequence[str]) -> str:
    return " ".join(str(value) for value in command)


def terminal_cause(output: str, returncode: int) -> str:
    lines = [line.strip() for line in output.replace("\r\n", "\n").replace("\r", "\n").split("\n") if line.strip()]
    for marker in ("Cause:", "bbk install: error:", "error:", "FAILED", "FAIL"):
        for line in reversed(lines):
            if marker.lower() in line.lower() and not line.startswith("Result:"):
                return line
    for line in reversed(lines):
        if set(line) <= {"=", "-"} or line.startswith("Exit code:"):
            continue
        return line
    return f"process exited with code {returncode} without diagnostic output"


def execute_step(spec: CheckSpec, *, stream: TextIO) -> CheckResult:
    if spec.optional_reason is not None:
        stream.write(f"SKIP: {spec.optional_reason}\n")
        stream.flush()
        return CheckResult(spec.name, spec.command, "SKIP", None, "", spec.optional_reason)
    try:
        process = subprocess.Popen(
            list(spec.command),
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        cause = f"{type(exc).__name__}: {exc}"
        stream.write(cause + "\n")
        stream.flush()
        return CheckResult(spec.name, spec.command, "FAIL", 2, "", cause)

    chunks: list[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        chunks.append(line)
        stream.write(line)
        stream.flush()
    returncode = process.wait()
    output = "".join(chunks)
    return CheckResult(
        spec.name,
        spec.command,
        "PASS" if returncode == 0 else "FAIL",
        returncode,
        output,
        None if returncode == 0 else terminal_cause(output, returncode),
    )


def report_dict(results: Sequence[CheckResult], *, expected: int, exit_code: int) -> dict[str, object]:
    passed = sum(result.passed for result in results)
    skipped = sum(result.skipped for result in results)
    failed = len(results) - passed - skipped
    return {
        "schema": "bbk.verification-report.v1",
        "status": "PASS" if exit_code == 0 else "FAIL",
        "exit_code": exit_code,
        "checks_expected": expected,
        "checks_run": len(results),
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "not_run": max(expected - len(results), 0),
        "checks": [
            {
                "name": result.name,
                "command": list(result.command),
                "status": result.status,
                "returncode": result.returncode,
                "cause": result.cause,
            }
            for result in results
        ],
    }


def print_final_summary(results: Sequence[CheckResult], *, expected: int, exit_code: int, stream: TextIO) -> None:
    report = report_dict(results, expected=expected, exit_code=exit_code)
    stream.write("\n" + "=" * 70 + "\n")
    stream.write("BBK FINAL VERIFICATION SUMMARY\n")
    stream.write("=" * 70 + "\n")
    disposition = "FAILED" if exit_code else ("PASS WITH SKIPS" if report["skipped"] else "PASS")
    stream.write(f"Result: {disposition}\n")
    stream.write(
        f"Checks: {report['checks_run']}/{report['checks_expected']} run; "
        f"{report['passed']} passed; {report['failed']} failed; "
        f"{report['skipped']} skipped; {report['not_run']} not run\n"
    )
    failures = [result for result in results if result.status == "FAIL"]
    if failures:
        stream.write("\nFailure list:\n")
        for number, result in enumerate(failures, start=1):
            stream.write(f"{number}. {result.name}\n")
            stream.write(f"   Command: {command_text(result.command)}\n")
            stream.write(f"   Exit code: {result.returncode}\n")
            stream.write(f"   Cause: {result.cause}\n")
    skips = [result for result in results if result.skipped]
    if skips:
        stream.write("\nSkipped checks:\n")
        for result in skips:
            stream.write(f"- {result.name}: {result.cause}\n")
    if not failures and not skips:
        stream.write("All verification checks passed.\n")
    stream.write(f"Exit code: {exit_code}\n")
    stream.write("=" * 70 + "\n")
    stream.flush()


def run_all_report(
    *,
    failfast: bool = False,
    require_node: bool = False,
    skip_package_manifest: bool = False,
    stream: TextIO | None = None,
    executor: Callable[[CheckSpec], CheckResult] | None = None,
) -> tuple[int, list[CheckResult]]:
    target = stream if stream is not None else sys.stdout
    steps = verification_steps(require_node=require_node, skip_package_manifest=skip_package_manifest)
    results: list[CheckResult] = []
    total_started = time.monotonic()
    target.write(f"BBK ordered verification starting: {len(steps)} checks.\n")
    target.flush()
    for index, spec in enumerate(steps, start=1):
        step_started = time.monotonic()
        target.write(f"\n==> [{index}/{len(steps)}] {spec.name}\n")
        if spec.command:
            target.write(f"    {command_text(spec.command)}\n")
        target.flush()
        result = executor(spec) if executor is not None else execute_step(spec, stream=target)
        results.append(result)
        elapsed = time.monotonic() - step_started
        target.write(f"<== {spec.name}: {result.status} ({elapsed:.1f}s)\n")
        target.flush()
        # A failed package trust gate stops before any package code executes.
        if result.status == "FAIL" and (failfast or spec.trust_gate):
            break
    exit_code = 1 if any(result.status == "FAIL" for result in results) else 0
    target.write(
        f"Verification checks completed in {time.monotonic() - total_started:.1f}s.\n"
    )
    target.flush()
    print_final_summary(results, expected=len(steps), exit_code=exit_code, stream=target)
    return exit_code, results


def run_all(**kwargs: object) -> int:
    exit_code, _ = run_all_report(**kwargs)  # type: ignore[arg-type]
    return exit_code


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--failfast", action="store_true", help="stop after the first failed verification check")
    parser.add_argument("--require-node", action="store_true", help="fail if Node.js is unavailable for OMP syntax validation")
    parser.add_argument("--skip-package-manifest", action="store_true", help="source-build mode: skip pre/post immutable package checks")
    parser.add_argument("--list", action="store_true", help="list ordered checks without running them")
    parser.add_argument("--json", action="store_true", help="emit one JSON report containing captured human output")
    parser.add_argument(
        "--report-file",
        help="write the machine-readable report to this file while streaming normal human output",
    )
    args = parser.parse_args(argv)
    if args.json and args.report_file:
        parser.error("--json and --report-file are mutually exclusive")
    if args.list:
        for index, spec in enumerate(
            verification_steps(require_node=args.require_node, skip_package_manifest=args.skip_package_manifest), start=1
        ):
            suffix = command_text(spec.command) if spec.command else f"SKIP — {spec.optional_reason}"
            print(f"{index}. {spec.name}: {suffix}")
        return 0
    if args.json:
        stream = io.StringIO()
        exit_code, results = run_all_report(
            failfast=args.failfast,
            require_node=args.require_node,
            skip_package_manifest=args.skip_package_manifest,
            stream=stream,
        )
        value = report_dict(
            results,
            expected=len(verification_steps(require_node=args.require_node, skip_package_manifest=args.skip_package_manifest)),
            exit_code=exit_code,
        )
        value["output"] = stream.getvalue()
        print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True))
        return exit_code
    exit_code, results = run_all_report(
        failfast=args.failfast,
        require_node=args.require_node,
        skip_package_manifest=args.skip_package_manifest,
    )
    if args.report_file:
        destination = Path(args.report_file).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        value = report_dict(
            results,
            expected=len(
                verification_steps(
                    require_node=args.require_node,
                    skip_package_manifest=args.skip_package_manifest,
                )
            ),
            exit_code=exit_code,
        )
        temp = destination.with_name(f".{destination.name}.bbk-{os.getpid()}.tmp")
        temp.write_text(
            json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temp, destination)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
