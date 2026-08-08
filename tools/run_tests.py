#!/usr/bin/env python3
"""Run BBK unittests with PowerShell-safe output and a final roll-up.

Python's standard ``unittest`` text runner writes progress to stderr, and
individual tests may invoke tools that also use stderr for routine notices.
Windows PowerShell 5.1 can present any native stderr line as
``NativeCommandError`` even when the process exits successfully.

The default ``auto`` strategy uses a small pool of multi-module processes on
Windows. This retains parallelism without paying for one interpreter per test
module, while POSIX hosts retain parallel module isolation. ``--mode pooled``,
``--mode batch``, and ``--mode isolated`` make that choice explicit. Every
child process merges stderr into stdout, preserves aggregate pass/fail
semantics, and ends with a final summary. When tests fail, the summary repeats
every formal ``FAIL`` and ``ERROR`` heading with its terminal cause so a
failure does not disappear in earlier verbose output.

Use ``--all`` for BBK's complete ordered verification pipeline: immutable
package checks, generated-surface drift checks, source sanity, semantic
fixtures, all unittest modules, and OMP JavaScript syntax validation. The
ordered path uses quiet suite summaries by default; add ``--all -v`` only when
a complete per-test transcript is needed.
"""
from __future__ import annotations

import argparse
import codecs
import concurrent.futures
import contextlib
import datetime as dt
import hashlib
import json
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
from typing import Any, Mapping, NamedTuple, Sequence, TextIO

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from runtime_requirements import enforce_supported_python

enforce_supported_python(program='BBK test runner')

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
RUN_COUNT_RE = re.compile(r"^Ran (\d+) tests? in ", re.MULTILINE)
DEFAULT_SUITE_TIMEOUT = 420.0
DEFAULT_HEARTBEAT_SECONDS = 15.0
DEFAULT_PARALLEL_JOBS = 0
DEFAULT_EXECUTION_MODE = "auto"
EXECUTION_MODES = ("auto", "pooled", "batch", "isolated")
TEST_PROFILES = ("fast", "standard", "release")
DEFAULT_TEST_PROFILE = "standard"
DURATION_SEED_PATH = TESTS / "test-durations.json"
LAST_RUN_REPORT: dict[str, Any] | None = None
FAST_TEST_FILES = frozenset({
    "test_assurance_state.py",
    "test_dependencies.py",
    "test_contract_package_v1.py",
    "test_prompt_module_package_v1.py",
    "test_role_package_v4.py",
    "test_schema_registry.py",
    "test_role_capabilities.py",
    "test_substrate_beads.py",
    "test_governed_filesystem.py",
    "test_worker_spawn.py",
    "test_read_only_spawn.py",
    "test_qualified_task.py",
    "test_governance_status.py",
    "test_omp_governed_profile.py",
    "test_role_return_runtime.py",
    "test_control_plane.py",
    "test_release_qualification.py",
    "test_session_oracle.py",
    "test_model_routing_optional_package_version.py",
    "test_manual_qualification_kit.py",
    "test_verification_economy.py",
    "test_verification_metrics.py",
    "test_substrate_doctor.py",
    "test_substrate_jj.py",
})


@contextlib.contextmanager
def test_profile_environment(profile: str):
    """Temporarily expose profile selection to discovered child suites."""
    previous = {
        "BBK_TEST_PROFILE": os.environ.get("BBK_TEST_PROFILE"),
        "BBK_EXTERNAL_SCHEMA": os.environ.get("BBK_EXTERNAL_SCHEMA"),
        "BBK_TEST_ALLOW_MISSING_DEPENDENCIES": os.environ.get(
            "BBK_TEST_ALLOW_MISSING_DEPENDENCIES"
        ),
    }
    os.environ["BBK_TEST_PROFILE"] = profile
    os.environ["BBK_EXTERNAL_SCHEMA"] = "1" if profile == "release" else "0"
    os.environ["BBK_TEST_ALLOW_MISSING_DEPENDENCIES"] = "1"
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
ISSUE_HEADING_RE = re.compile(r"^(ERROR|FAIL): (.+)$")
SKIP_COUNT_RE = re.compile(r"(?:OK|FAILED) \([^\n]*?skipped=(\d+)")
SUBPROCESS_OUTPUT_ENCODING = "utf-8"
SUBPROCESS_OUTPUT_ERRORS = "backslashreplace"


class TestIssue(NamedTuple):
    """One formal unittest failure/error or runner-level process problem."""

    kind: str
    label: str
    cause: str


class SuiteResult(NamedTuple):
    """Captured result for one test module or one batched discovery process."""

    name: str
    returncode: int
    output: str
    tests_run: int | None
    issues: tuple[TestIssue, ...]
    skipped: int = 0

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
    environment["BBK_TEST_ALLOW_MISSING_DEPENDENCIES"] = "1"
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


def unittest_modules_command(
    files: Sequence[Path],
    *,
    quiet: bool = False,
    verbose: bool = False,
    failfast: bool = False,
    buffer: bool = False,
) -> list[str]:
    """Return one unittest command for an exact set of package test modules."""
    command = [sys.executable, "-m", "unittest"]
    if verbose:
        command.append("-v")
    elif quiet:
        command.append("-q")
    if failfast:
        command.append("-f")
    if buffer:
        command.append("-b")
    root = ROOT.resolve()
    for path in files:
        relative = path.resolve().relative_to(root)
        command.append(".".join(relative.with_suffix("").parts))
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


def parse_skip_count(output: str) -> int:
    """Return the final unittest skipped count, defaulting to zero."""
    matches = list(SKIP_COUNT_RE.finditer(output.replace("\r\n", "\n").replace("\r", "\n")))
    return int(matches[-1].group(1)) if matches else 0



def test_cache_root() -> Path:
    """Return a package-external cache root suitable for immutable releases."""
    if raw := os.environ.get("BBK_TEST_CACHE_DIR"):
        return Path(raw).expanduser()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "BBK" / "test-runs"
    base = os.environ.get("XDG_CACHE_HOME")
    return (Path(base).expanduser() if base else Path.home() / ".cache") / "bbk" / "test-runs"


def default_timing_report_path() -> Path:
    return test_cache_root() / "latest.json"


def duration_cache_path() -> Path:
    return test_cache_root() / "module-durations.json"


def _duration_modules(value: Any) -> dict[str, float]:
    modules = value.get("modules") if isinstance(value, dict) else None
    if not isinstance(modules, dict):
        return {}
    result: dict[str, float] = {}
    for name, raw in modules.items():
        if isinstance(name, str) and isinstance(raw, (int, float)) and raw > 0:
            result[name] = float(raw)
    return result


def _read_duration_value(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_duration_file(path: Path) -> dict[str, float]:
    return _duration_modules(_read_duration_value(path))


def duration_seed_sha256(path: Path | None = None) -> str:
    candidate = path if path is not None else DURATION_SEED_PATH
    try:
        data = candidate.read_bytes()
    except OSError:
        data = b""
    return hashlib.sha256(data).hexdigest()


def _read_duration_cache(path: Path, *, seed_path: Path | None = None) -> dict[str, float]:
    value = _read_duration_value(path)
    if not isinstance(value, dict):
        return {}
    if value.get("seed_sha256") != duration_seed_sha256(seed_path):
        return {}
    return _duration_modules(value)


def write_json_atomic(path: Path, value: Mapping[str, Any] | dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + ".", delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _store_run_report(report: dict[str, Any], path: Path | None) -> None:
    global LAST_RUN_REPORT
    LAST_RUN_REPORT = report
    if path is None:
        return
    try:
        write_json_atomic(path, report)
    except OSError as exc:
        report["report_write_error"] = f"{type(exc).__name__}: {exc}"


def update_duration_cache(report: Mapping[str, Any]) -> None:
    """Update retained module weights only from one-module process timings."""
    observed: dict[str, float] = {}
    for group in report.get("groups", []) if isinstance(report, Mapping) else []:
        if not isinstance(group, Mapping):
            continue
        modules = group.get("modules")
        duration = group.get("duration_seconds")
        if (
            isinstance(modules, list)
            and len(modules) == 1
            and isinstance(modules[0], str)
            and isinstance(duration, (int, float))
            and duration > 0
        ):
            observed[modules[0]] = float(duration)
    if not observed:
        return
    path = duration_cache_path()
    current = _read_duration_cache(path)
    for name, duration in observed.items():
        previous = current.get(name)
        current[name] = duration if previous is None else round((previous * 0.6) + (duration * 0.4), 6)
    value = {
        "schema": "bbk.test-duration-cache.v1",
        "package_version": (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
        "seed_sha256": duration_seed_sha256(),
        "updated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "modules": dict(sorted(current.items())),
    }
    try:
        write_json_atomic(path, value)
    except OSError:
        pass


def automatic_parallel_jobs(cpu_count: int | None = None) -> int:
    """Return a conservative worker count for this process/I/O-heavy suite."""
    count = max(1, int(cpu_count if cpu_count is not None else (os.cpu_count() or 1)))
    if count >= 12:
        return 6
    if count >= 6:
        return 4
    return min(3, count)


def resolve_execution_mode(
    mode: str,
    *,
    jobs: int,
    platform_name: str | None = None,
) -> str:
    """Resolve the process strategy independently of the worker count.

    ``--jobs`` always means concurrency. It no longer changes ``auto`` from a
    pooled Windows run into one interpreter per module.
    """
    del jobs
    if mode not in EXECUTION_MODES:
        raise ValueError(f"unknown execution mode: {mode}")
    if mode != "auto":
        return mode
    return "pooled" if (platform_name or os.name) == "nt" else "isolated"


def load_duration_weights(path: Path | None = None) -> dict[str, float]:
    """Load packaged weights plus a cache bound to the exact packaged seed."""
    seed_path = path if path is not None else DURATION_SEED_PATH
    result = _read_duration_file(seed_path)
    result.update(_read_duration_cache(duration_cache_path(), seed_path=seed_path))
    return result


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


def _execute_unittest_command(
    command: Sequence[str],
    *,
    label: str,
    stream: TextIO | None = None,
    timeout: float = DEFAULT_SUITE_TIMEOUT,
    heartbeat_seconds: float = DEFAULT_HEARTBEAT_SECONDS,
) -> SuiteResult:
    """Execute one unittest command with merged, bounded process-tree output.

    Output is routed through a temporary file rather than a pipe. A test's
    orphaned grandchild therefore cannot keep the runner blocked by retaining
    an inherited pipe handle after the suite process exits. When *stream* is
    supplied, new bytes are decoded and mirrored while the suite is running.
    """
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
                list(command),
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
                            f"    ... {label} is still running "
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
                f"\nBBK test runner: suite {label} exceeded "
                f"{timeout:g} seconds and its process tree was terminated.\n"
            )
            output += diagnostic
            if stream is not None:
                _write_text(stream, diagnostic, flush=True)
            issue = TestIssue("PROCESS ERROR", label, diagnostic.strip())
            return SuiteResult(
                label, 2, output, parse_test_count(output), (issue,), parse_skip_count(output)
            )
    except OSError as exc:
        issue = TestIssue("PROCESS ERROR", label, f"{type(exc).__name__}: {exc}")
        return SuiteResult(label, 2, "", None, (issue,), 0)
    finally:
        if process is not None and process.poll() is None:
            try:
                _terminate_process_tree(process)
            except OSError:
                pass
        if capture_path is not None:
            _remove_capture_file(capture_path)

    return SuiteResult(
        name=label,
        returncode=returncode,
        output=output,
        tests_run=parse_test_count(output),
        issues=parse_issues(output),
        skipped=parse_skip_count(output),
    )


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
    """Execute one discovery pattern in a bounded child process."""
    return _execute_unittest_command(
        unittest_command(
            pattern,
            quiet=quiet,
            verbose=verbose,
            failfast=failfast,
            buffer=buffer,
        ),
        label=pattern,
        stream=stream,
        timeout=timeout,
        heartbeat_seconds=heartbeat_seconds,
    )


def execute_modules(
    files: Sequence[Path],
    *,
    label: str,
    quiet: bool = False,
    verbose: bool = False,
    failfast: bool = False,
    buffer: bool = False,
    stream: TextIO | None = None,
    timeout: float = DEFAULT_SUITE_TIMEOUT,
    heartbeat_seconds: float = DEFAULT_HEARTBEAT_SECONDS,
) -> SuiteResult:
    """Execute an exact set of test modules in one bounded child process."""
    return _execute_unittest_command(
        unittest_modules_command(
            files,
            quiet=quiet,
            verbose=verbose,
            failfast=failfast,
            buffer=buffer,
        ),
        label=label,
        stream=stream,
        timeout=timeout,
        heartbeat_seconds=heartbeat_seconds,
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
    module_count: int | None = None,
    execution_processes: int | None = None,
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
    if module_count is not None:
        processes = execution_processes if execution_processes is not None else len(results)
        _write_text(target, f"Test modules discovered: {module_count}; Python test processes: {processes}\n")
    test_suffix = f"; {unknown_count_suites} suite(s) did not report a count" if unknown_count_suites else ""
    _write_text(target, f"Tests reported: {known_test_count}{test_suffix}\n")
    _write_text(target, f"Skipped: {sum(result.skipped for result in results)}\n")
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


def partition_test_files(
    files: Sequence[Path],
    processes: int,
    *,
    duration_weights: dict[str, float] | None = None,
) -> list[list[Path]]:
    """Partition modules by retained measured duration, then source size."""
    count = min(len(files), max(1, int(processes)))
    if count == 0:
        return []
    original_order = {path.resolve(): index for index, path in enumerate(files)}
    measured = duration_weights if duration_weights is not None else load_duration_weights()

    def weight(path: Path) -> float:
        if path.name in measured:
            return max(0.001, float(measured[path.name]))
        try:
            return max(0.001, path.stat().st_size / 100_000.0)
        except OSError:
            return 0.001

    groups: list[list[Path]] = [[] for _ in range(count)]
    loads = [0.0 for _ in range(count)]
    for path in sorted(files, key=lambda value: (-weight(value), value.name)):
        index = min(range(count), key=lambda value: (loads[value], value))
        groups[index].append(path)
        loads[index] += weight(path)
    for group in groups:
        group.sort(key=lambda value: original_order[value.resolve()])
    return groups


def _shard_label(index: int, files: Sequence[Path]) -> str:
    return f"pool-{index}[{', '.join(path.name for path in files)}]"


def run_test_pool(
    files: Sequence[Path],
    *,
    quiet: bool = False,
    verbose: bool = False,
    failfast: bool = False,
    buffer: bool = False,
    stream: TextIO | None = None,
    suite_timeout: float = DEFAULT_SUITE_TIMEOUT,
    heartbeat_seconds: float = DEFAULT_HEARTBEAT_SECONDS,
    jobs: int = DEFAULT_PARALLEL_JOBS,
) -> int:
    """Run modules in a small parallel pool of multi-module processes."""
    target = stream if stream is not None else sys.stdout
    process_count = min(
        len(files),
        max(1, (automatic_parallel_jobs() if jobs == 0 else jobs)),
    )
    if failfast:
        process_count = 1
    groups = partition_test_files(files, process_count)
    results_by_index: dict[int, SuiteResult] = {}
    elapsed_by_index: dict[int, float] = {}
    progress_by_index: dict[int, SuiteProgressStream] = {}
    started_by_index: dict[int, float] = {}
    total_started = time.monotonic()
    _write_text(
        target,
        f"Running {len(files)} unittest modules in {len(groups)} multi-module "
        f"Python processes.\n",
        flush=True,
    )
    for index, group in enumerate(groups, start=1):
        _write_text(
            target,
            f"==> [{index}/{len(groups)}] {', '.join(path.name for path in group)} (queued)\n",
            flush=True,
        )

    def execute(index: int, group: Sequence[Path]) -> tuple[int, SuiteResult, float]:
        started = time.monotonic()
        result = execute_modules(
            group,
            label=_shard_label(index, group),
            quiet=quiet,
            verbose=verbose,
            failfast=failfast and len(groups) == 1,
            buffer=buffer,
            stream=progress_by_index[index],
            timeout=suite_timeout,
            heartbeat_seconds=0,
        )
        return index, result, time.monotonic() - started

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=len(groups),
        thread_name_prefix="bbk-test-pool",
    ) as pool:
        pending: dict[
            concurrent.futures.Future[tuple[int, SuiteResult, float]],
            tuple[int, Sequence[Path]],
        ] = {}
        for index, group in enumerate(groups, start=1):
            started_by_index[index] = time.monotonic()
            progress_by_index[index] = SuiteProgressStream()
            pending[pool.submit(execute, index, group)] = (index, group)

        while pending:
            wait_timeout = heartbeat_seconds if heartbeat_seconds > 0 else None
            done, _ = concurrent.futures.wait(
                pending,
                timeout=wait_timeout,
                return_when=concurrent.futures.FIRST_COMPLETED,
            )
            if not done:
                elapsed = time.monotonic() - total_started
                running = sorted(pending.values(), key=lambda value: value[0])
                noun = "process" if len(running) == 1 else "processes"
                _write_text(
                    target,
                    f"    ... {len(running)} pooled test {noun} still running "
                    f"after {elapsed:.0f}s",
                )
                if suite_timeout > 0:
                    _write_text(target, f" (hard timeout {suite_timeout:g}s per process)")
                _write_text(target, ":\n")
                for index, group in running:
                    current = progress_by_index[index].snapshot()
                    detail = f" — {current}" if current else ""
                    names = ", ".join(path.name for path in group)
                    _write_text(target, f"        pool-{index}: {names}{detail}\n")
                target.flush()
                continue

            for future in sorted(done, key=lambda item: pending[item][0]):
                index, group = pending.pop(future)
                label = _shard_label(index, group)
                try:
                    _, result, elapsed = future.result()
                except BaseException as exc:  # pragma: no cover
                    issue = TestIssue("PROCESS ERROR", label, f"{type(exc).__name__}: {exc}")
                    result = SuiteResult(label, 2, "", None, (issue,))
                    elapsed = time.monotonic() - started_by_index[index]
                results_by_index[index] = result
                elapsed_by_index[index] = elapsed
                _write_text(target, f"\n==> [{index}/{len(groups)}] {label} output\n", flush=True)
                _write_output(result.output, target)
                count_text = f", {result.tests_run} tests" if result.tests_run is not None else ""
                _write_text(
                    target,
                    f"<== [{index}/{len(groups)}] {label}: "
                    f"{'PASS' if result.passed else 'FAIL'} ({elapsed:.1f}s{count_text})\n",
                    flush=True,
                )

    results = [results_by_index[index] for index in range(1, len(groups) + 1)]
    total_elapsed = time.monotonic() - total_started
    _write_text(
        target,
        f"Completed {len(files)} modules in {len(groups)} pooled processes "
        f"in {total_elapsed:.1f}s.\n",
        flush=True,
    )
    exit_code = 1 if any(not result.passed for result in results) else 0
    print_final_summary(
        results,
        expected_suites=len(groups),
        exit_code=exit_code,
        stream=target,
        module_count=len(files),
        execution_processes=len(groups),
    )
    global LAST_RUN_REPORT
    LAST_RUN_REPORT = {
        "execution_processes": len(groups),
        "tests_reported": sum(result.tests_run or 0 for result in results),
        "skipped": sum(result.skipped for result in results),
        "groups": [
            {
                "label": _shard_label(index, groups[index - 1]),
                "modules": [path.name for path in groups[index - 1]],
                "duration_seconds": round(elapsed_by_index.get(index, 0.0), 6),
                "tests_reported": results_by_index[index].tests_run,
                "status": "PASS" if results_by_index[index].passed else "FAIL",
            }
            for index in range(1, len(groups) + 1)
        ],
    }
    return exit_code


def run_test_batch(
    files: Sequence[Path],
    *,
    pattern: str,
    quiet: bool = False,
    verbose: bool = False,
    failfast: bool = False,
    buffer: bool = False,
    stream: TextIO | None = None,
    suite_timeout: float = DEFAULT_SUITE_TIMEOUT,
    heartbeat_seconds: float = DEFAULT_HEARTBEAT_SECONDS,
) -> int:
    """Run all discovered modules in one bounded Python process.

    This is the Windows fast path. It preserves child-process containment and
    merged PowerShell-safe output while paying interpreter/import cost once.
    """
    target = stream if stream is not None else sys.stdout
    total_started = time.monotonic()
    _write_text(
        target,
        f"Running {len(files)} unittest modules in one Python process.\n",
        flush=True,
    )
    # ``files`` already reflects profile selection. Import only those exact
    # modules; discovery by the broad pattern would import every test module
    # before its load hook could filter cases, reintroducing host-only imports
    # and startup cost into focused profiles such as Codex.
    label = f"batch[{', '.join(path.name for path in files)}]"
    result = execute_modules(
        files,
        label=label,
        quiet=quiet,
        verbose=verbose,
        failfast=failfast,
        buffer=buffer,
        stream=target,
        timeout=suite_timeout,
        heartbeat_seconds=heartbeat_seconds,
    )
    elapsed = time.monotonic() - total_started
    count_text = f", {result.tests_run} tests" if result.tests_run is not None else ""
    _write_text(
        target,
        f"Completed batched unittest discovery: "
        f"{'PASS' if result.passed else 'FAIL'} ({elapsed:.1f}s{count_text}).\n",
        flush=True,
    )
    exit_code = 0 if result.passed else 1
    print_final_summary(
        [result],
        expected_suites=1,
        exit_code=exit_code,
        stream=target,
        module_count=len(files),
        execution_processes=1,
    )
    global LAST_RUN_REPORT
    LAST_RUN_REPORT = {
        "execution_processes": 1,
        "tests_reported": result.tests_run or 0,
        "skipped": result.skipped,
        "groups": [{
            "label": result.name,
            "modules": [path.name for path in files],
            "duration_seconds": round(elapsed, 6),
            "tests_reported": result.tests_run,
            "status": "PASS" if result.passed else "FAIL",
        }],
    }
    return exit_code


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
        max(1, (automatic_parallel_jobs() if jobs == 0 else jobs)),
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
    elapsed_by_index: dict[int, float] = {}
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
        elapsed_by_index[index] = elapsed
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
    global LAST_RUN_REPORT
    LAST_RUN_REPORT = {
        "execution_processes": 1,
        "tests_reported": sum(result.tests_run or 0 for result in results),
        "skipped": sum(result.skipped for result in results),
        "groups": [
            {
                "label": path.name,
                "modules": [path.name],
                "duration_seconds": round(elapsed_by_index.get(index, 0.0), 6),
                "tests_reported": results[index - 1].tests_run,
                "status": "PASS" if results[index - 1].passed else "FAIL",
            }
            for index, path in enumerate(files, start=1)
        ],
    }
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
    elapsed_by_index: dict[int, float] = {}
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
                elapsed_by_index[index] = elapsed
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
    global LAST_RUN_REPORT
    LAST_RUN_REPORT = {
        "execution_processes": len(files),
        "tests_reported": sum(result.tests_run or 0 for result in results),
        "skipped": sum(result.skipped for result in results),
        "groups": [
            {
                "label": files[index - 1].name,
                "modules": [files[index - 1].name],
                "duration_seconds": round(elapsed_by_index.get(index, 0.0), 6),
                "tests_reported": results_by_index[index].tests_run,
                "status": "PASS" if results_by_index[index].passed else "FAIL",
            }
            for index in range(1, len(files) + 1)
        ],
    }
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
        help="maximum seconds for one pooled shard, batch, or isolated unittest module (0 disables; default: 420)",
    )
    parser.add_argument(
        "--heartbeat-seconds",
        type=float,
        default=DEFAULT_HEARTBEAT_SECONDS,
        help="emit a still-running notice after this many quiet seconds (0 disables; default: 15)",
    )
    parser.add_argument(
        "--mode",
        choices=EXECUTION_MODES,
        default=DEFAULT_EXECUTION_MODE,
        help=(
            "test-process strategy: auto uses a small multi-module pool on Windows "
            "and parallel isolated modules elsewhere; pooled uses a bounded set of "
            "multi-module processes; batch uses one process; isolated uses one "
            "process per module (default: auto)"
        ),
    )
    parser.add_argument(
        "--profile",
        choices=TEST_PROFILES,
        default=DEFAULT_TEST_PROFILE,
        help="test selection: fast contracts, standard behavior/platform, or complete release qualification",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=DEFAULT_PARALLEL_JOBS,
        help="pooled/isolated unittest processes; 0 selects a conservative 3/4/6 workers from CPU count (default: 0)",
    )
    parser.add_argument(
        "--timing-report",
        metavar="PATH",
        help="write the machine-readable run/timing report here (default: package-external BBK test cache)",
    )
    parser.add_argument(
        "--no-timing-report",
        action="store_true",
        help="do not write the default package-external timing report",
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
    if args.timing_report and args.no_timing_report:
        parser.error("--timing-report and --no-timing-report are mutually exclusive")
    with test_profile_environment(args.profile):
        if args.all:
            if args.quiet or args.buffer or args.pattern != "test*.py" or args.heartbeat_seconds != DEFAULT_HEARTBEAT_SECONDS:
                parser.error("--all cannot be combined with --quiet, --buffer, --pattern, or --heartbeat-seconds")
            from verify_all import run_all

            return run_all(
                profile=args.profile,
                failfast=args.failfast,
                require_node=args.require_node,
                skip_package_manifest=args.skip_package_manifest,
                jobs=args.jobs,
                test_mode=args.mode,
                verbose_tests=args.verbose,
                timing_report=args.timing_report,
                no_timing_report=args.no_timing_report,
            )
        if args.require_node or args.skip_package_manifest:
            parser.error("--require-node and --skip-package-manifest require --all")
        files = matching_test_files(args.pattern)
        if args.profile == "fast" and args.pattern == "test*.py":
            files = [path for path in files if path.name in FAST_TEST_FILES]
        if not files:
            issue = TestIssue(
                "CONFIGURATION ERROR",
                args.pattern,
                f"No tests matched under {TESTS}",
            )
            result = SuiteResult(args.pattern, 2, "", 0, (issue,))
            print_final_summary([result], expected_suites=1, exit_code=2)
            return 2
        execution_mode = resolve_execution_mode(args.mode, jobs=args.jobs)
        started = time.monotonic()
        if execution_mode == "pooled":
            exit_code = run_test_pool(
                files,
                quiet=args.quiet,
                verbose=args.verbose,
                failfast=args.failfast,
                buffer=args.buffer,
                suite_timeout=args.suite_timeout,
                heartbeat_seconds=args.heartbeat_seconds,
                jobs=args.jobs,
            )
        elif execution_mode == "batch":
            exit_code = run_test_batch(
                files,
                pattern=args.pattern,
                quiet=args.quiet,
                verbose=args.verbose,
                failfast=args.failfast,
                buffer=args.buffer,
                suite_timeout=args.suite_timeout,
                heartbeat_seconds=args.heartbeat_seconds,
            )
        else:
            exit_code = run_test_files(
                files,
                quiet=args.quiet,
                verbose=args.verbose,
                failfast=args.failfast,
                buffer=args.buffer,
                suite_timeout=args.suite_timeout,
                heartbeat_seconds=args.heartbeat_seconds,
                jobs=args.jobs,
            )
        report = dict(LAST_RUN_REPORT or {})
        report.update({
            "schema": "bbk.test-run.v1",
            "package_version": (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
            "profile": args.profile,
            "mode": execution_mode,
            "requested_jobs": args.jobs,
            "module_count": len(files),
            "exit_code": exit_code,
            "status": "PASS" if exit_code == 0 else "FAIL",
            "wall_seconds": round(time.monotonic() - started, 6),
            "completed_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        })
        report_path = None if args.no_timing_report else Path(args.timing_report).expanduser() if args.timing_report else default_timing_report_path()
        _store_run_report(report, report_path)
        update_duration_cache(report)
        if report_path is not None:
            _write_text(sys.stdout, f"Timing report: {report_path}\n", flush=True)
        return exit_code



if __name__ == "__main__":
    raise SystemExit(main())
