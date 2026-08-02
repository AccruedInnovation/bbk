#!/usr/bin/env python3
"""Run BBK unittests with PowerShell-safe output and a final roll-up.

Python's standard ``unittest`` text runner writes progress to stderr, and
individual tests may invoke tools that also use stderr for routine notices.
Windows PowerShell 5.1 can present any native stderr line as
``NativeCommandError`` even when the process exits successfully.

By default this wrapper runs matching unittest modules in fresh Python
processes, merges each process tree's stderr into stdout, preserves aggregate
pass/fail semantics, and always prints a final summary. When tests fail, the
summary repeats every formal ``FAIL`` and ``ERROR`` heading with its terminal
cause so a failure does not disappear in earlier verbose output.

Use ``--all`` for BBK's complete ordered verification pipeline: immutable
package checks, generated-surface drift checks, source sanity, semantic
fixtures, all unittest modules, and OMP JavaScript syntax validation.
"""
from __future__ import annotations

import argparse
import codecs
import concurrent.futures
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from typing import NamedTuple, Sequence, TextIO

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
RUN_COUNT_RE = re.compile(r"^Ran (\d+) tests? in ", re.MULTILINE)
DEFAULT_SUITE_TIMEOUT = 300.0
DEFAULT_HEARTBEAT_SECONDS = 15.0
DEFAULT_PARALLEL_JOBS = 0
ISSUE_HEADING_RE = re.compile(r"^(ERROR|FAIL): (.+)$")
SUBPROCESS_OUTPUT_ENCODING = "utf-8"
SUBPROCESS_OUTPUT_ERRORS = "backslashreplace"


class TestIssue(NamedTuple):
    """One formal unittest failure/error or runner-level process problem."""

    kind: str
    label: str
    cause: str


class SuiteResult(NamedTuple):
    """Captured result for one independently executed test module."""

    name: str
    returncode: int
    output: str
    tests_run: int | None
    issues: tuple[TestIssue, ...]

    @property
    def passed(self) -> bool:
        return self.returncode == 0


class SuiteProgressStream:
    """Thread-safe sink exposing the latest visible child-test activity.

    Parallel execution buffers complete suite output until completion so
    tracebacks cannot interleave. This sink still lets heartbeat messages name
    the test or operation currently visible in each running suite.
    """

    encoding = SUBPROCESS_OUTPUT_ENCODING
    errors = SUBPROCESS_OUTPUT_ERRORS

    def __init__(self, *, limit: int = 320) -> None:
        self._lock = threading.Lock()
        self._pending = ""
        self._latest = ""
        self._limit = max(80, int(limit))

    def write(self, value: str) -> int:
        text = str(value)
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        with self._lock:
            combined = self._pending + normalized
            parts = combined.split("\n")
            self._pending = parts[-1]
            for line in parts[:-1]:
                if line.strip():
                    self._latest = line.strip()[-self._limit :]
            if self._pending.strip():
                self._latest = self._pending.strip()[-self._limit :]
        return len(text)

    def flush(self) -> None:
        return None

    def snapshot(self) -> str:
        with self._lock:
            return self._latest


def _stream_text(stream: TextIO, value: str) -> str:
    """Return *value* in a form the destination stream can always encode.

    PowerShell 5.1 and redirected Windows consoles commonly expose a strict
    CP1252 ``sys.stdout``.  Test output can contain Unicode that CP1252 cannot
    represent, including escaped undecodable bytes.  Preserve that information
    as explicit ``\\u``/``\\U``/``\\x`` sequences rather than allowing a
    ``UnicodeEncodeError`` to abort verification.
    """
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
    """Write without allowing console encoding limitations to abort a run."""
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
        # A host may provide a non-reconfigurable wrapper. _write_text remains
        # the final defensive layer for those streams.
        pass


def _subprocess_environment() -> dict[str, str]:
    """Return an environment that makes Python child output deterministic."""
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = (
        f"{SUBPROCESS_OUTPUT_ENCODING}:{SUBPROCESS_OUTPUT_ERRORS}"
    )
    return environment


def discover_suite(pattern: str = "test*.py") -> unittest.TestSuite:
    """Discover an in-process suite; primarily useful to callers and tests."""
    os.chdir(ROOT)
    return unittest.defaultTestLoader.discover(str(TESTS), pattern=pattern)


def run_suite(
    suite: unittest.TestSuite,
    *,
    stream: TextIO | None = None,
    verbosity: int = 1,
    failfast: bool = False,
    buffer: bool = False,
) -> unittest.result.TestResult:
    """Run *suite* and direct unittest's progress stream to stdout by default."""
    runner = unittest.TextTestRunner(
        stream=stream if stream is not None else sys.stdout,
        verbosity=verbosity,
        failfast=failfast,
        buffer=buffer,
    )
    return runner.run(suite)


def matching_test_files(pattern: str) -> list[Path]:
    """Return deterministic package-local test modules matching *pattern*."""
    return sorted(path for path in TESTS.glob(pattern) if path.is_file())


def unittest_command(
    pattern: str,
    *,
    quiet: bool = False,
    verbose: bool = False,
    failfast: bool = False,
    buffer: bool = False,
) -> list[str]:
    """Return the standard-library unittest discovery command."""
    command = [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-p",
        pattern,
    ]
    if verbose:
        command.append("-v")
    elif quiet:
        command.append("-q")
    if failfast:
        command.append("-f")
    if buffer:
        command.append("-b")
    return command


def _is_rule(line: str, character: str) -> bool:
    stripped = line.strip()
    return len(stripped) >= 20 and set(stripped) == {character}


def _terminal_cause(lines: Sequence[str]) -> str:
    """Return the final meaningful diagnostic line from a unittest issue."""
    for line in reversed(lines):
        value = line.strip()
        if value and not _is_rule(value, "-") and not _is_rule(value, "="):
            return value
    return "No terminal cause was emitted."


def parse_issues(output: str) -> tuple[TestIssue, ...]:
    """Extract formal ``unittest`` FAIL/ERROR blocks from captured output."""
    lines = output.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    issues: list[TestIssue] = []
    index = 0
    while index + 1 < len(lines):
        if not _is_rule(lines[index], "="):
            index += 1
            continue
        heading = ISSUE_HEADING_RE.match(lines[index + 1].strip())
        if heading is None:
            index += 1
            continue

        end = index + 2
        while end < len(lines):
            if (
                _is_rule(lines[end], "=")
                and end + 1 < len(lines)
                and ISSUE_HEADING_RE.match(lines[end + 1].strip())
            ):
                break
            if (
                _is_rule(lines[end], "-")
                and end + 1 < len(lines)
                and RUN_COUNT_RE.match(lines[end + 1])
            ):
                break
            end += 1

        body = lines[index + 2 : end]
        issues.append(
            TestIssue(
                kind=heading.group(1),
                label=heading.group(2),
                cause=_terminal_cause(body),
            )
        )
        index = end
    return tuple(issues)


def parse_test_count(output: str) -> int | None:
    """Return the last standard unittest ``Ran N tests`` count, if present."""
    matches = list(RUN_COUNT_RE.finditer(output.replace("\r\n", "\n").replace("\r", "\n")))
    return int(matches[-1].group(1)) if matches else None


def _terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    """Best-effort termination of a timed-out suite and its descendants."""
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            # A wedged taskkill must not wedge the verification runner too.
            try:
                process.kill()
            except OSError:
                pass
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=2)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except OSError:
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # Preserve the bounded failure contract even if the OS refuses to
            # reap a damaged process immediately.
            pass


def _remove_capture_file(path: Path, *, attempts: int = 20, delay: float = 0.05) -> None:
    """Best-effort removal resilient to delayed Windows handle release.

    Cleanup must never replace the real test-runner failure with ``WinError
    32``.  A terminated Windows process can retain its redirected file handle
    for a short interval, so retry before giving up silently on the temporary
    diagnostic file.
    """
    for attempt in range(max(attempts, 1)):
        try:
            path.unlink(missing_ok=True)
            return
        except PermissionError:
            if attempt + 1 >= max(attempts, 1):
                return
            time.sleep(max(delay, 0.0))
        except OSError:
            return


def execute_discovered(
    pattern: str = "test*.py",
    *,
    quiet: bool = False,
    verbose: bool = False,
    failfast: bool = False,
    buffer: bool = False,
    stream: TextIO | None = None,
    timeout: float = DEFAULT_SUITE_TIMEOUT,
    heartbeat_seconds: float = DEFAULT_HEARTBEAT_SECONDS,
) -> SuiteResult:
    """Execute one discovery pattern with merged, bounded process-tree output.

    Output is routed through a temporary file rather than a pipe.  A test's
    orphaned grandchild therefore cannot keep the runner blocked by retaining
    an inherited pipe handle after the suite process exits.  When *stream* is
    supplied, new bytes are decoded and mirrored while the suite is running.
    """
    command = unittest_command(
        pattern,
        quiet=quiet,
        verbose=verbose,
        failfast=failfast,
        buffer=buffer,
    )
    creation: dict[str, object] = {}
    if os.name == "nt":
        creation["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        creation["start_new_session"] = True

    capture_path: Path | None = None
    process: subprocess.Popen[bytes] | None = None
    try:
        fd, raw_capture = tempfile.mkstemp(prefix="bbk-test-suite-", suffix=".log")
        os.close(fd)
        capture_path = Path(raw_capture)
        with capture_path.open("wb") as writer:
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                stdout=writer,
                stderr=subprocess.STDOUT,
                env=_subprocess_environment(),
                **creation,
            )

        decoder = codecs.getincrementaldecoder(SUBPROCESS_OUTPUT_ENCODING)(
            errors=SUBPROCESS_OUTPUT_ERRORS
        )
        chunks: list[str] = []
        started = time.monotonic()
        last_visible_activity = started
        timed_out = False
        with capture_path.open("rb") as reader:
            while process.poll() is None:
                now = time.monotonic()
                if timeout > 0 and now - started > timeout:
                    timed_out = True
                    _terminate_process_tree(process)
                    break
                if stream is not None:
                    data = reader.read()
                    if data:
                        value = decoder.decode(data, final=False)
                        chunks.append(value)
                        _write_text(stream, value, flush=True)
                        last_visible_activity = now
                    elif heartbeat_seconds > 0 and now - last_visible_activity >= heartbeat_seconds:
                        elapsed = now - started
                        timeout_text = f" of {timeout:g}s timeout" if timeout > 0 else ""
                        _write_text(
                            stream,
                            f"    ... {pattern} is still running "
                            f"({elapsed:.0f}s elapsed{timeout_text})\n",
                            flush=True,
                        )
                        last_visible_activity = now
                time.sleep(0.05)

            if process.poll() is None:
                _terminate_process_tree(process)
            try:
                returncode = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                timed_out = True
                returncode = 2
            if stream is None:
                reader.seek(0)
                output = reader.read().decode(
                    SUBPROCESS_OUTPUT_ENCODING,
                    errors=SUBPROCESS_OUTPUT_ERRORS,
                )
            else:
                data = reader.read()
                tail = decoder.decode(data, final=True)
                if tail:
                    chunks.append(tail)
                    _write_text(stream, tail, flush=True)
                output = "".join(chunks)

        if timed_out:
            diagnostic = (
                f"\nBBK test runner: suite {pattern} exceeded "
                f"{timeout:g} seconds and its process tree was terminated.\n"
            )
            output += diagnostic
            if stream is not None:
                _write_text(stream, diagnostic, flush=True)
            issue = TestIssue("PROCESS ERROR", pattern, diagnostic.strip())
            return SuiteResult(pattern, 2, output, parse_test_count(output), (issue,))
    except OSError as exc:
        issue = TestIssue("PROCESS ERROR", pattern, f"{type(exc).__name__}: {exc}")
        return SuiteResult(pattern, 2, "", None, (issue,))
    finally:
        if process is not None and process.poll() is None:
            try:
                _terminate_process_tree(process)
            except OSError:
                # Do not mask the original output/process failure. The capture
                # deletion below is independently best-effort for the same
                # reason.
                pass
        if capture_path is not None:
            _remove_capture_file(capture_path)

    return SuiteResult(
        name=pattern,
        returncode=returncode,
        output=output,
        tests_run=parse_test_count(output),
        issues=parse_issues(output),
    )


def _write_output(output: str, stream: TextIO) -> None:
    if not output:
        return
    _write_text(stream, output)
    if not output.endswith("\n"):
        _write_text(stream, "\n")
    stream.flush()


def run_discovered(
    pattern: str = "test*.py",
    *,
    quiet: bool = False,
    verbose: bool = False,
    failfast: bool = False,
    buffer: bool = False,
) -> int:
    """Run one discovery pattern with the entire child stream on stdout."""
    result = execute_discovered(
        pattern,
        quiet=quiet,
        verbose=verbose,
        failfast=failfast,
        buffer=buffer,
    )
    _write_output(result.output, sys.stdout)
    return result.returncode


def _fallback_issue(result: SuiteResult) -> TestIssue:
    useful = [
        line.strip()
        for line in result.output.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if line.strip()
        and not _is_rule(line, "-")
        and not _is_rule(line, "=")
        and not line.strip().startswith("Ran ")
        and not line.strip().startswith("FAILED (")
    ]
    cause = useful[-1] if useful else "No structured unittest failure block was emitted."
    return TestIssue("PROCESS ERROR", result.name, f"exit code {result.returncode}: {cause}")


def summary_issues(results: Sequence[SuiteResult]) -> list[tuple[str, TestIssue]]:
    """Return every reportable issue, including fallbacks for opaque failures."""
    values: list[tuple[str, TestIssue]] = []
    for result in results:
        if result.passed:
            continue
        if result.issues:
            values.extend((result.name, issue) for issue in result.issues)
        else:
            values.append((result.name, _fallback_issue(result)))
    return values


def print_final_summary(
    results: Sequence[SuiteResult],
    *,
    expected_suites: int,
    exit_code: int,
    stream: TextIO | None = None,
) -> None:
    """Print an always-visible aggregate summary and all failure/error labels."""
    target = stream if stream is not None else sys.stdout
    passed = sum(result.passed for result in results)
    failed = len(results) - passed
    not_run = max(expected_suites - len(results), 0)
    known_test_count = sum(result.tests_run or 0 for result in results)
    unknown_count_suites = sum(result.tests_run is None for result in results)
    issues = summary_issues(results)

    _write_text(target, "\n" + "=" * 70 + "\n")
    _write_text(target, "BBK FINAL TEST SUMMARY\n")
    _write_text(target, "=" * 70 + "\n")
    _write_text(target, f"Result: {'PASS' if exit_code == 0 else 'FAILED'}\n")
    _write_text(
        target,
        f"Suites: {len(results)}/{expected_suites} run; "
        f"{passed} passed; {failed} failed; {not_run} not run\n"
    )
    test_suffix = f"; {unknown_count_suites} suite(s) did not report a count" if unknown_count_suites else ""
    _write_text(target, f"Tests reported: {known_test_count}{test_suffix}\n")
    failure_count = sum(issue.kind == "FAIL" for _, issue in issues)
    error_count = sum(issue.kind == "ERROR" for _, issue in issues)
    runner_error_count = len(issues) - failure_count - error_count
    _write_text(target, f"Failures: {failure_count}\n")
    _write_text(target, f"Errors: {error_count}\n")
    _write_text(target, f"Runner/configuration errors: {runner_error_count}\n")

    failed_results = [result for result in results if not result.passed]
    if failed_results:
        _write_text(target, "\nFailed suites:\n")
        for result in failed_results:
            _write_text(target, f"- {result.name}: exit code {result.returncode}\n")

    if issues:
        _write_text(target, "\nFailure/error list:\n")
        for number, (suite_name, issue) in enumerate(issues, start=1):
            _write_text(target, f"{number}. [{issue.kind}] {issue.label}\n")
            _write_text(target, f"   Suite: {suite_name}\n")
            _write_text(target, f"   Cause: {issue.cause}\n")

    else:
        _write_text(target, "No failures or errors.\n")

    _write_text(target, f"Exit code: {exit_code}\n")
    _write_text(target, "=" * 70 + "\n")
    target.flush()


def run_test_files(
    files: Sequence[Path],
    *,
    quiet: bool = False,
    verbose: bool = False,
    failfast: bool = False,
    buffer: bool = False,
    stream: TextIO | None = None,
    suite_timeout: float = DEFAULT_SUITE_TIMEOUT,
    heartbeat_seconds: float = DEFAULT_HEARTBEAT_SECONDS,
    jobs: int = 1,
) -> int:
    """Run each test module independently and aggregate exact pass/fail state."""
    target = stream if stream is not None else sys.stdout
    resolved_jobs = min(
        len(files),
        max(1, (min(4, os.cpu_count() or 1) if jobs == 0 else jobs)),
    )
    # Fail-fast is only meaningful when suites are launched serially. Avoid
    # starting work that the caller explicitly asked us not to run after the
    # first failure.
    if failfast:
        resolved_jobs = 1

    if resolved_jobs > 1:
        return _run_test_files_parallel(
            files,
            quiet=quiet,
            verbose=verbose,
            buffer=buffer,
            stream=target,
            suite_timeout=suite_timeout,
            heartbeat_seconds=heartbeat_seconds,
            jobs=resolved_jobs,
        )

    results: list[SuiteResult] = []
    total_started = time.monotonic()
    for index, path in enumerate(files, start=1):
        suite_started = time.monotonic()
        _write_text(target, f"==> [{index}/{len(files)}] {path.name}\n", flush=True)
        result = execute_discovered(
            path.name,
            quiet=quiet,
            verbose=verbose,
            failfast=failfast,
            buffer=buffer,
            stream=target,
            timeout=suite_timeout,
            heartbeat_seconds=heartbeat_seconds,
        )
        results.append(result)
        elapsed = time.monotonic() - suite_started
        count_text = f", {result.tests_run} tests" if result.tests_run is not None else ""
        _write_text(
            target,
            f"<== [{index}/{len(files)}] {path.name}: "
            f"{'PASS' if result.passed else 'FAIL'} ({elapsed:.1f}s{count_text})\n",
            flush=True,
        )
        if not result.passed and failfast:
            break

    total_elapsed = time.monotonic() - total_started
    _write_text(
        target,
        f"Completed {len(results)}/{len(files)} unittest suites in {total_elapsed:.1f}s.\n",
        flush=True,
    )
    exit_code = 1 if any(not result.passed for result in results) else 0
    print_final_summary(
        results,
        expected_suites=len(files),
        exit_code=exit_code,
        stream=target,
    )
    return exit_code


def _run_test_files_parallel(
    files: Sequence[Path],
    *,
    quiet: bool,
    verbose: bool,
    buffer: bool,
    stream: TextIO,
    suite_timeout: float,
    heartbeat_seconds: float,
    jobs: int,
) -> int:
    """Run independent unittest modules concurrently with deterministic roll-up.

    Each module still executes in its own bounded process tree and capture file.
    Only module-level scheduling is parallelized; individual test ordering and
    isolation inside a module remain unchanged. Captured output is emitted as a
    complete block when that module finishes, preventing interleaved tracebacks.
    """
    results_by_index: dict[int, SuiteResult] = {}
    started_by_index: dict[int, float] = {}
    progress_by_index: dict[int, SuiteProgressStream] = {}
    total_started = time.monotonic()
    _write_text(
        stream,
        f"Running {len(files)} unittest suites with {jobs} parallel workers.\n",
        flush=True,
    )
    for index, path in enumerate(files, start=1):
        _write_text(stream, f"==> [{index}/{len(files)}] {path.name} (queued)\n", flush=True)

    def execute(index: int, path: Path) -> tuple[int, SuiteResult, float]:
        started = time.monotonic()
        result = execute_discovered(
            path.name,
            quiet=quiet,
            verbose=verbose,
            failfast=False,
            buffer=buffer,
            stream=progress_by_index[index],
            timeout=suite_timeout,
            heartbeat_seconds=0,
        )
        return index, result, time.monotonic() - started

    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs, thread_name_prefix="bbk-tests") as pool:
        pending: dict[concurrent.futures.Future[tuple[int, SuiteResult, float]], tuple[int, Path]] = {}
        for index, path in enumerate(files, start=1):
            started_by_index[index] = time.monotonic()
            progress_by_index[index] = SuiteProgressStream()
            pending[pool.submit(execute, index, path)] = (index, path)

        while pending:
            timeout = heartbeat_seconds if heartbeat_seconds > 0 else None
            done, _ = concurrent.futures.wait(
                pending,
                timeout=timeout,
                return_when=concurrent.futures.FIRST_COMPLETED,
            )
            if not done:
                elapsed = time.monotonic() - total_started
                running = sorted(pending.values())
                noun = "suite" if len(running) == 1 else "suites"
                _write_text(
                    stream,
                    f"    ... {len(running)} {noun} still running after {elapsed:.0f}s",
                )
                if suite_timeout > 0:
                    _write_text(stream, f" (hard timeout {suite_timeout:g}s)")
                _write_text(stream, ":\n")
                for index, path in running[:4]:
                    current = progress_by_index[index].snapshot()
                    detail = f" — {current}" if current else ""
                    _write_text(stream, f"        {path.name}{detail}\n")
                if len(running) > 4:
                    _write_text(stream, f"        … and {len(running) - 4} more\n")
                stream.flush()
                continue

            for future in sorted(done, key=lambda item: pending[item][0]):
                index, path = pending.pop(future)
                try:
                    _, result, elapsed = future.result()
                except BaseException as exc:  # pragma: no cover - defensive scheduler path
                    issue = TestIssue("PROCESS ERROR", path.name, f"{type(exc).__name__}: {exc}")
                    result = SuiteResult(path.name, 2, "", None, (issue,))
                    elapsed = time.monotonic() - started_by_index[index]
                results_by_index[index] = result
                _write_text(stream, f"\n==> [{index}/{len(files)}] {path.name} output\n", flush=True)
                _write_output(result.output, stream)
                count_text = f", {result.tests_run} tests" if result.tests_run is not None else ""
                _write_text(
                    stream,
                    f"<== [{index}/{len(files)}] {path.name}: "
                    f"{'PASS' if result.passed else 'FAIL'} ({elapsed:.1f}s{count_text})\n",
                    flush=True,
                )

    results = [results_by_index[index] for index in range(1, len(files) + 1)]
    total_elapsed = time.monotonic() - total_started
    _write_text(
        stream,
        f"Completed {len(results)}/{len(files)} unittest suites in {total_elapsed:.1f}s.\n",
        flush=True,
    )
    exit_code = 1 if any(not result.passed for result in results) else 0
    print_final_summary(
        results,
        expected_suites=len(files),
        exit_code=exit_code,
        stream=stream,
    )
    return exit_code


def main(argv: Sequence[str] | None = None) -> int:
    _configure_standard_stream(sys.stdout)
    _configure_standard_stream(sys.stderr)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all",
        action="store_true",
        help="run the complete ordered BBK verification pipeline, not only unittests",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="show each unittest and disposition")
    parser.add_argument("-q", "--quiet", action="store_true", help="show only each unittest suite's final result")
    parser.add_argument("-f", "--failfast", action="store_true", help="stop after the first failing suite or check")
    parser.add_argument("-b", "--buffer", action="store_true", help="buffer unittest stdout and stderr")
    parser.add_argument("-p", "--pattern", default="test*.py", help="unittest-module filename pattern")
    parser.add_argument(
        "--require-node",
        action="store_true",
        help="with --all, fail if Node.js is unavailable for OMP syntax validation",
    )
    parser.add_argument(
        "--skip-package-manifest",
        action="store_true",
        help="with --all, source-build mode: omit pre/post immutable package checks",
    )
    parser.add_argument(
        "--suite-timeout",
        type=float,
        default=DEFAULT_SUITE_TIMEOUT,
        help="maximum seconds for any one unittest module (0 disables; default: 300)",
    )
    parser.add_argument(
        "--heartbeat-seconds",
        type=float,
        default=DEFAULT_HEARTBEAT_SECONDS,
        help="emit a still-running notice after this many quiet seconds (0 disables; default: 15)",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=DEFAULT_PARALLEL_JOBS,
        help="unittest modules to run concurrently; 0 selects up to four automatically (default: 0)",
    )
    args = parser.parse_args(argv)
    if args.verbose and args.quiet:
        parser.error("--verbose and --quiet are mutually exclusive")
    if args.suite_timeout < 0:
        parser.error("--suite-timeout must be zero or positive")
    if args.heartbeat_seconds < 0:
        parser.error("--heartbeat-seconds must be zero or positive")
    if args.jobs < 0:
        parser.error("--jobs must be zero or positive")
    if args.all:
        if args.quiet or args.buffer or args.pattern != "test*.py" or args.heartbeat_seconds != DEFAULT_HEARTBEAT_SECONDS:
            parser.error("--all cannot be combined with --quiet, --buffer, --pattern, or --heartbeat-seconds")
        from verify_all import run_all

        return run_all(
            failfast=args.failfast,
            require_node=args.require_node,
            skip_package_manifest=args.skip_package_manifest,
            jobs=args.jobs,
        )
    if args.require_node or args.skip_package_manifest:
        parser.error("--require-node and --skip-package-manifest require --all")
    files = matching_test_files(args.pattern)
    if not files:
        issue = TestIssue(
            "CONFIGURATION ERROR",
            args.pattern,
            f"No tests matched under {TESTS}",
        )
        result = SuiteResult(args.pattern, 2, "", 0, (issue,))
        print_final_summary([result], expected_suites=1, exit_code=2)
        return 2
    return run_test_files(
        files,
        quiet=args.quiet,
        verbose=args.verbose,
        failfast=args.failfast,
        buffer=args.buffer,
        suite_timeout=args.suite_timeout,
        heartbeat_seconds=args.heartbeat_seconds,
        jobs=args.jobs,
    )


if __name__ == "__main__":
    raise SystemExit(main())
