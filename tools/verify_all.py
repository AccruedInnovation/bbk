#!/usr/bin/env python3
"""Run BBK verification profiles in deterministic order.

The ``release`` profile is the release-author/CI qualification path.
``standard`` is the routine development and preinstallation path: it preserves
all product, integration, and platform coverage while omitting test-runner
self-tests and optional duplicate external-schema cross-checks. ``fast`` runs
canonical contract and deterministic-transformation checks. Targeted ``omp``
and ``codex`` profiles retain package trust gates and generated-source checks.
Legacy ``full`` and ``quick`` spellings remain aliases for ``release`` and
``fast`` respectively. Unittest checks use
quiet suite summaries by default; ``--verbose-tests`` restores a complete
per-test transcript for diagnostics. Child stderr is merged into stdout for
PowerShell-safe reporting, and a final summary repeats every failed check and
its terminal cause.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import inspect
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

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from runtime_requirements import enforce_supported_python

enforce_supported_python(program="BBK verification")

import dependencies

ROOT = Path(__file__).resolve().parents[1]
SUBPROCESS_OUTPUT_ENCODING = "utf-8"
SUBPROCESS_OUTPUT_ERRORS = "backslashreplace"


@dataclass(frozen=True)
class CheckSpec:
    name: str
    command: tuple[str, ...]
    optional_reason: str | None = None
    trust_gate: bool = False
    cwd: Path = ROOT
    in_process: bool = False
    include_node: bool = False


@dataclass(frozen=True)
class CheckResult:
    name: str
    command: tuple[str, ...]
    status: str
    returncode: int | None
    output: str
    cause: str | None = None
    execution: str = "subprocess"

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    @property
    def skipped(self) -> bool:
        return self.status == "SKIP"


def _stream_text(stream: TextIO, value: str) -> str:
    """Return text that a strict legacy Windows stream can encode safely."""
    encoding = getattr(stream, "encoding", None)
    if not encoding:
        return value
    try:
        value.encode(encoding)
    except (LookupError, UnicodeEncodeError):
        try:
            return value.encode(encoding, errors="backslashreplace").decode(encoding)
        except LookupError:
            return value.encode("ascii", errors="backslashreplace").decode("ascii")
    return value


def _write_text(stream: TextIO, value: str, *, flush: bool = False) -> None:
    """Write verification output without propagating encoding limitations."""
    stream.write(_stream_text(stream, value))
    if flush:
        stream.flush()


def _configure_standard_stream(stream: TextIO) -> None:
    """Make direct console writes non-fatal without changing its encoding."""
    reconfigure = getattr(stream, "reconfigure", None)
    if not callable(reconfigure):
        return
    try:
        reconfigure(errors=SUBPROCESS_OUTPUT_ERRORS)
    except (AttributeError, OSError, TypeError, ValueError):
        pass


def _subprocess_environment(*, include_node: bool = False) -> dict[str, str]:
    """Return a deterministic, non-mutating verification environment."""
    environment = dependencies.verification_environment(
        os.environ,
        include_node=include_node,
        strict=False,
    )
    environment["PYTHONIOENCODING"] = (
        f"{SUBPROCESS_OUTPUT_ENCODING}:{SUBPROCESS_OUTPUT_ERRORS}"
    )
    # Product tests exercise setup/install behavior with isolated fake tools.
    # This explicit runner-only hook prevents those tests from depending on the
    # qualification host's real toolchain.
    environment["BBK_TEST_ALLOW_MISSING_DEPENDENCIES"] = "1"
    return environment


VERIFICATION_PROFILES = ("fast", "standard", "release", "full", "quick", "omp", "codex")
TEST_EXECUTION_MODES = ("auto", "pooled", "batch", "isolated")


def canonical_profile(profile: str) -> str:
    """Return the current profile name for legacy public aliases."""
    aliases = {"full": "release", "quick": "fast"}
    return aliases.get(profile, profile)


def verification_steps(
    *,
    profile: str = "standard",
    require_node: bool = False,
    skip_package_manifest: bool = False,
    jobs: int = 0,
    test_mode: str = "auto",
    verbose_tests: bool = False,
    timing_report: str | None = None,
    no_timing_report: bool = False,
) -> list[CheckSpec]:
    if profile not in VERIFICATION_PROFILES:
        raise ValueError(f"unknown verification profile: {profile}")
    selected_profile = canonical_profile(profile)
    if test_mode not in TEST_EXECUTION_MODES:
        raise ValueError(f"unknown test execution mode: {test_mode}")
    python = sys.executable
    test_output_flag = "-v" if verbose_tests else "-q"
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
            CheckSpec("Method-content projection drift", (python, "tools/create_method_content.py", "--check"), in_process=True),
            CheckSpec("Role-specification projection drift", (python, "tools/create_role_spec.py", "--check"), in_process=True),
            CheckSpec("Model-routing policy", (python, "tools/model_routing.py", "--check"), in_process=True),
            CheckSpec("Agent projection drift", (python, "tools/generate_agents.py", "--check"), in_process=True),
            CheckSpec("Python compilation and JSON parsing", (python, "tools/source_sanity.py"), in_process=True),
        ]
    )

    if selected_profile in {"fast", "standard", "release"}:
        if selected_profile in {"standard", "release"}:
            steps.append(
                CheckSpec("Alpha.7 semantic fixtures", (python, "tools/validate_alpha7_fixtures.py"), in_process=True)
            )
        suite_name = {
            "fast": "Fast contract unittest suite",
            "standard": "Standard unittest suite",
            "release": "Complete release unittest suite",
        }[selected_profile]
        test_command = [
            python, "tools/run_tests.py", test_output_flag,
            "--profile", selected_profile,
            "--mode", test_mode, "--jobs", str(jobs),
        ]
        if timing_report:
            test_command.extend(["--timing-report", timing_report])
        elif no_timing_report:
            test_command.append("--no-timing-report")
        steps.append(
            CheckSpec(
                suite_name,
                tuple(test_command),
                include_node=selected_profile in {"standard", "release"},
            )
        )
    elif selected_profile == "omp":
        omp_test_command = [
            python, "tools/run_tests.py", test_output_flag,
            "--profile", "standard", "--pattern", "test_omp_runtime.py",
            "--jobs", "1",
        ]
        if timing_report:
            omp_test_command.extend(["--timing-report", timing_report])
        elif no_timing_report:
            omp_test_command.append("--no-timing-report")
        steps.append(CheckSpec("OMP-focused unittest suite", tuple(omp_test_command), include_node=True))
    elif selected_profile == "codex":
        steps.append(
            CheckSpec(
                "Codex-focused unittest selection",
                (
                    python,
                    "-m",
                    "unittest",
                    "-v",
                    "tests.test_core_contracts.Alpha10ModelRoutingTests",
                    "tests.test_installation_portability.Alpha116CodexWorkspaceTests",
                    "tests.test_codex_manual_qualification_kit.CodexManualQualificationKitTests",
                    "tests.test_artifact_skill.BbkArtifactSkillTests",
                ),
                cwd=ROOT,
            )
        )
    if selected_profile in {"standard", "release", "omp"}:
        node = os.environ.get("BBK_TEST_NODE") or shutil.which("node")
        if not node:
            try:
                _command, node_environment = dependencies.command_with_node_runtime((), environment=os.environ)
                node = node_environment.get("BBK_TEST_NODE")
            except dependencies.DependencyError:
                node = None
        if node:
            steps.append(
                CheckSpec(
                    "OMP extension JavaScript syntax",
                    (node, "--check", "omp/extension/index.js"),
                    include_node=True,
                )
            )
        elif require_node:
            steps.append(
                CheckSpec(
                    "OMP extension JavaScript syntax",
                    ("node", "--check", "omp/extension/index.js"),
                    include_node=True,
                )
            )
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


def _execute_python_step_in_process(spec: CheckSpec, *, stream: TextIO) -> CheckResult:
    """Run one trusted package-local Python check without another interpreter.

    The pre-execution package trust gate always remains a subprocess. These
    checks run only after it passes. Process-global state is restored so one
    generator or validator cannot influence the next check.
    """
    command = list(spec.command)
    if len(command) < 2 or Path(command[0]).resolve() != Path(sys.executable).resolve():
        cause = "in-process check is not a package-local Python command"
        return CheckResult(spec.name, spec.command, "FAIL", 2, "", cause)
    script = (spec.cwd / command[1]).resolve()
    try:
        script.relative_to((ROOT / "tools").resolve())
    except ValueError:
        cause = f"in-process check is outside tools/: {script}"
        return CheckResult(spec.name, spec.command, "FAIL", 2, "", cause)

    saved_cwd = Path.cwd()
    saved_argv = list(sys.argv)
    saved_sys_path = list(sys.path)
    saved_environment = os.environ.copy()
    output_stream = io.StringIO()
    returncode = 2
    module_name = f"_bbk_verify_{script.stem}_{os.getpid()}_{time.monotonic_ns()}"
    try:
        os.chdir(spec.cwd)
        sys.argv = [str(script), *command[2:]]
        sys.path.insert(0, str(script.parent))
        module_spec = importlib.util.spec_from_file_location(module_name, script)
        if module_spec is None or module_spec.loader is None:
            raise RuntimeError(f"cannot load package-local verifier: {script}")
        module = importlib.util.module_from_spec(module_spec)
        sys.modules[module_name] = module
        module_spec.loader.exec_module(module)
        main_function = getattr(module, "main", None)
        if not callable(main_function):
            raise RuntimeError(f"{script.name} has no callable main")
        with contextlib.redirect_stdout(output_stream), contextlib.redirect_stderr(output_stream):
            signature = inspect.signature(main_function)
            result = main_function() if len(signature.parameters) == 0 else main_function(command[2:])
        returncode = int(result or 0)
    except SystemExit as exc:
        returncode = int(exc.code or 0) if isinstance(exc.code, (int, type(None))) else 2
    except BaseException as exc:
        output_stream.write(f"{type(exc).__name__}: {exc}\n")
        returncode = 2
    finally:
        sys.modules.pop(module_name, None)
        os.chdir(saved_cwd)
        sys.argv = saved_argv
        sys.path[:] = saved_sys_path
        os.environ.clear()
        os.environ.update(saved_environment)

    output = output_stream.getvalue()
    if output:
        _write_text(stream, output, flush=True)
    return CheckResult(
        spec.name,
        spec.command,
        "PASS" if returncode == 0 else "FAIL",
        returncode,
        output,
        None if returncode == 0 else terminal_cause(output, returncode),
        "in-process",
    )


def execute_step(spec: CheckSpec, *, stream: TextIO) -> CheckResult:
    if spec.optional_reason is not None:
        _write_text(stream, f"SKIP: {spec.optional_reason}\n", flush=True)
        return CheckResult(spec.name, spec.command, "SKIP", None, "", spec.optional_reason)
    if spec.in_process:
        return _execute_python_step_in_process(spec, stream=stream)
    try:
        process = subprocess.Popen(
            list(spec.command),
            cwd=spec.cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding=SUBPROCESS_OUTPUT_ENCODING,
            errors=SUBPROCESS_OUTPUT_ERRORS,
            env=_subprocess_environment(include_node=spec.include_node),
        )
    except OSError as exc:
        cause = f"{type(exc).__name__}: {exc}"
        _write_text(stream, cause + "\n", flush=True)
        return CheckResult(spec.name, spec.command, "FAIL", 2, "", cause)

    chunks: list[str] = []
    assert process.stdout is not None
    with process.stdout:
        for line in process.stdout:
            chunks.append(line)
            _write_text(stream, line, flush=True)
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


def report_dict(
    results: Sequence[CheckResult],
    *,
    expected: int,
    exit_code: int,
    profile: str = "standard",
) -> dict[str, object]:
    passed = sum(result.passed for result in results)
    skipped = sum(result.skipped for result in results)
    failed = len(results) - passed - skipped
    return {
        "schema": "bbk.verification-report.v1",
        "profile": profile,
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
                "execution": result.execution,
            }
            for result in results
        ],
    }


def print_final_summary(
    results: Sequence[CheckResult],
    *,
    expected: int,
    exit_code: int,
    stream: TextIO,
    profile: str = "standard",
) -> None:
    report = report_dict(results, expected=expected, exit_code=exit_code, profile=profile)
    _write_text(stream, "\n" + "=" * 70 + "\n")
    _write_text(stream, "BBK FINAL VERIFICATION SUMMARY\n")
    _write_text(stream, "=" * 70 + "\n")
    _write_text(stream, f"Profile: {profile}\n")
    disposition = "FAILED" if exit_code else ("PASS WITH SKIPS" if report["skipped"] else "PASS")
    _write_text(stream, f"Result: {disposition}\n")
    _write_text(
        stream,
        f"Checks: {report['checks_run']}/{report['checks_expected']} run; "
        f"{report['passed']} passed; {report['failed']} failed; "
        f"{report['skipped']} skipped; {report['not_run']} not run\n"
    )
    failures = [result for result in results if result.status == "FAIL"]
    if failures:
        _write_text(stream, "\nFailure list:\n")
        for number, result in enumerate(failures, start=1):
            _write_text(stream, f"{number}. {result.name}\n")
            _write_text(stream, f"   Command: {command_text(result.command)}\n")
            _write_text(stream, f"   Exit code: {result.returncode}\n")
            _write_text(stream, f"   Cause: {result.cause}\n")
    skips = [result for result in results if result.skipped]
    if skips:
        _write_text(stream, "\nSkipped checks:\n")
        for result in skips:
            _write_text(stream, f"- {result.name}: {result.cause}\n")
    if not failures and not skips:
        _write_text(stream, "All verification checks passed.\n")
    _write_text(stream, f"Exit code: {exit_code}\n")
    _write_text(stream, "=" * 70 + "\n")
    stream.flush()


def run_all_report(
    *,
    profile: str = "standard",
    failfast: bool = False,
    require_node: bool = False,
    skip_package_manifest: bool = False,
    jobs: int = 0,
    test_mode: str = "auto",
    verbose_tests: bool = False,
    timing_report: str | None = None,
    no_timing_report: bool = False,
    stream: TextIO | None = None,
    executor: Callable[[CheckSpec], CheckResult] | None = None,
) -> tuple[int, list[CheckResult]]:
    target = stream if stream is not None else sys.stdout
    steps = verification_steps(
        profile=profile,
        require_node=require_node,
        skip_package_manifest=skip_package_manifest,
        jobs=jobs,
        test_mode=test_mode,
        verbose_tests=verbose_tests,
        timing_report=timing_report,
        no_timing_report=no_timing_report,
    )
    results: list[CheckResult] = []
    total_started = time.monotonic()
    _write_text(
        target,
        f"BBK ordered verification starting: profile={profile}; {len(steps)} checks.\n",
        flush=True,
    )
    for index, spec in enumerate(steps, start=1):
        step_started = time.monotonic()
        _write_text(target, f"\n==> [{index}/{len(steps)}] {spec.name}\n")
        if spec.command:
            _write_text(target, f"    {command_text(spec.command)}\n")
        target.flush()
        result = executor(spec) if executor is not None else execute_step(spec, stream=target)
        results.append(result)
        elapsed = time.monotonic() - step_started
        _write_text(target, f"<== {spec.name}: {result.status} ({elapsed:.1f}s)\n", flush=True)
        # A failed package trust gate stops before any package code executes.
        if result.status == "FAIL" and (failfast or spec.trust_gate):
            break
    exit_code = 1 if any(result.status == "FAIL" for result in results) else 0
    _write_text(
        target,
        f"Verification checks completed in {time.monotonic() - total_started:.1f}s.\n",
        flush=True,
    )
    print_final_summary(
        results,
        expected=len(steps),
        exit_code=exit_code,
        stream=target,
        profile=profile,
    )
    return exit_code, results


def run_all(**kwargs: object) -> int:
    exit_code, _ = run_all_report(**kwargs)  # type: ignore[arg-type]
    return exit_code


def main(argv: Sequence[str] | None = None) -> int:
    _configure_standard_stream(sys.stdout)
    _configure_standard_stream(sys.stderr)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--failfast", action="store_true", help="stop after the first failed verification check")
    parser.add_argument(
        "--profile",
        choices=VERIFICATION_PROFILES,
        default="standard",
        help="verification scope: fast contracts, standard routine checks, complete release qualification, or harness-focused omp/codex",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=0,
        help="pooled/isolated unittest processes; 0 uses the platform default",
    )
    parser.add_argument(
        "--test-mode",
        choices=TEST_EXECUTION_MODES,
        default="auto",
        help="unittest process strategy passed to tools/run_tests.py (default: auto)",
    )
    parser.add_argument(
        "-v", "--verbose-tests",
        action="store_true",
        help="show every unittest and disposition; default release verification uses quiet suite summaries",
    )
    parser.add_argument("--timing-report", help="write the unittest timing report to this path")
    parser.add_argument("--no-timing-report", action="store_true", help="disable the default package-external unittest timing report")
    parser.add_argument("--require-node", action="store_true", help="fail if Node.js is unavailable for OMP syntax validation")
    parser.add_argument("--skip-package-manifest", action="store_true", help="source-build mode: skip pre/post immutable package checks")
    parser.add_argument("--list", action="store_true", help="list ordered checks without running them")
    parser.add_argument("--json", action="store_true", help="emit one JSON report containing captured human output")
    parser.add_argument(
        "--report-file",
        help="write the machine-readable report to this file while streaming normal human output",
    )
    args = parser.parse_args(argv)
    if args.jobs < 0:
        parser.error("--jobs must be zero or positive")
    if args.json and args.report_file:
        parser.error("--json and --report-file are mutually exclusive")
    if args.timing_report and args.no_timing_report:
        parser.error("--timing-report and --no-timing-report are mutually exclusive")
    if args.list:
        for index, spec in enumerate(
            verification_steps(
                profile=args.profile,
                require_node=args.require_node,
                skip_package_manifest=args.skip_package_manifest,
                jobs=args.jobs,
                test_mode=args.test_mode,
                verbose_tests=args.verbose_tests,
                timing_report=args.timing_report,
                no_timing_report=args.no_timing_report,
            ), start=1
        ):
            suffix = command_text(spec.command) if spec.command else f"SKIP — {spec.optional_reason}"
            print(f"{index}. {spec.name}: {suffix}")
        return 0
    if args.json:
        stream = io.StringIO()
        exit_code, results = run_all_report(
            profile=args.profile,
            failfast=args.failfast,
            require_node=args.require_node,
            skip_package_manifest=args.skip_package_manifest,
            jobs=args.jobs,
            test_mode=args.test_mode,
            verbose_tests=args.verbose_tests,
            timing_report=args.timing_report,
            no_timing_report=args.no_timing_report,
            stream=stream,
        )
        value = report_dict(
            results,
            expected=len(
                verification_steps(
                    profile=args.profile,
                    require_node=args.require_node,
                    skip_package_manifest=args.skip_package_manifest,
                    jobs=args.jobs,
                    test_mode=args.test_mode,
                    verbose_tests=args.verbose_tests,
                    timing_report=args.timing_report,
                    no_timing_report=args.no_timing_report,
                )
            ),
            exit_code=exit_code,
            profile=args.profile,
        )
        value["output"] = stream.getvalue()
        print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True))
        return exit_code
    exit_code, results = run_all_report(
        profile=args.profile,
        failfast=args.failfast,
        require_node=args.require_node,
        skip_package_manifest=args.skip_package_manifest,
        jobs=args.jobs,
        test_mode=args.test_mode,
        verbose_tests=args.verbose_tests,
        timing_report=args.timing_report,
        no_timing_report=args.no_timing_report,
    )
    if args.report_file:
        destination = Path(args.report_file).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        value = report_dict(
            results,
            expected=len(
                verification_steps(
                    profile=args.profile,
                    require_node=args.require_node,
                    skip_package_manifest=args.skip_package_manifest,
                    jobs=args.jobs,
                    test_mode=args.test_mode,
                    verbose_tests=args.verbose_tests,
                    timing_report=args.timing_report,
                    no_timing_report=args.no_timing_report,
                )
            ),
            exit_code=exit_code,
            profile=args.profile,
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
