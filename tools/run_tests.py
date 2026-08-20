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
import platform
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from typing import Any, Mapping, NamedTuple, Sequence, TextIO

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from runtime_requirements import PythonLaunchInvariantError, enforce_supported_python, python_command, python_environment
import launch_recorder

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
    # ART-HARD-A13 is the bounded native artifact-control subject.  Keep its
    # applicability-aware skips in the fast inventory so the gate cannot omit
    # the subject merely because this host is not Windows.
    "test_artifact_windows_native.py",
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
STRUCTURED_REPORT_RE = re.compile(r"^BBK_TEST_REPORT_JSON:(\{.*\})$", re.MULTILINE)
STRUCTURED_REPORT_ENV = "BBK_TEST_REPORT_JSON"
STRUCTURED_REPORT_NONCE_ENV = "BBK_TEST_REPORT_NONCE"
SUBPROCESS_OUTPUT_ENCODING = "utf-8"
SUBPROCESS_OUTPUT_ERRORS = "backslashreplace"
STRUCTURED_REPORT_SCHEMA = "bbk.test-child-report.v2"
STRUCTURED_SUBJECT_SCHEMA = "bbk.test-child-actual-subject.v1"
STRUCTURED_REPORT_MAX_BYTES = 4 * 1024 * 1024


class TestIssue(NamedTuple):
    """One formal unittest failure/error or runner-level process problem."""

    kind: str
    label: str
    cause: str


class StructuredReportError(ValueError):
    """Typed rejection for a managed child report that cannot establish PASS."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        message = code if not detail else f"{code}: {detail}"
        super().__init__(message)


class SuiteResult(NamedTuple):
    """Captured result for one test module or one batched discovery process."""

    name: str
    returncode: int
    output: str
    tests_run: int | None
    issues: tuple[TestIssue, ...]
    skipped: int = 0
    selected_ids: tuple[str, ...] = ()
    executed_ids: tuple[str, ...] = ()
    skipped_ids: tuple[str, ...] = ()
    not_run_ids: tuple[str, ...] = ()

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


def _subprocess_environment(
    *, report_path: Path | None = None, report_nonce: str | None = None
) -> dict[str, str]:
    """Return an environment that makes Python child output deterministic."""
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = (
        f"{SUBPROCESS_OUTPUT_ENCODING}:{SUBPROCESS_OUTPUT_ERRORS}"
    )
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONNOUSERSITE"] = "1"
    if raw_cache := environment.get("BBK_TEST_CACHE_DIR"):
        runtime = Path(raw_cache).expanduser() / "runtime"
        runtime.mkdir(parents=True, exist_ok=True)
        # Preserve caller-owned external roots when supplied.  Only construct
        # attempt-local fallbacks for callers that omitted them.
        if not environment.get("TEMP"):
            environment["TEMP"] = str(runtime / "temp")
        if not environment.get("TMP"):
            environment["TMP"] = str(runtime / "temp")
        if not environment.get("TMPDIR"):
            environment["TMPDIR"] = str(runtime / "temp")
        if not environment.get("PYTHONPYCACHEPREFIX"):
            environment["PYTHONPYCACHEPREFIX"] = str(runtime / "cache")
        Path(environment["TEMP"]).mkdir(parents=True, exist_ok=True)
        Path(environment["PYTHONPYCACHEPREFIX"]).mkdir(parents=True, exist_ok=True)
    environment = python_environment(environment, extra={"BBK_TEST_ALLOW_MISSING_DEPENDENCIES": "1"})
    if report_path is not None:
        # Every child receives a fresh parent-owned carrier.  Overriding an
        # inherited value prevents nested BBK runners from writing into an
        # outer pool/batch/isolated ledger.
        environment[STRUCTURED_REPORT_ENV] = str(report_path)
        if report_nonce is not None:
            environment[STRUCTURED_REPORT_NONCE_ENV] = report_nonce
        else:
            environment.pop(STRUCTURED_REPORT_NONCE_ENV, None)
    else:
        environment.pop(STRUCTURED_REPORT_ENV, None)
        environment.pop(STRUCTURED_REPORT_NONCE_ENV, None)
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
    command = python_command(TOOLS_DIR / "test_module_runner.py", "--discover", pattern)
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
    command = python_command(TOOLS_DIR / "test_module_runner.py")
    if verbose:
        command.append("-v")
    elif quiet:
        command.append("-q")
    if failfast:
        command.append("-f")
    if buffer:
        command.append("-b")
    for path in files:
        command.append(str(path.resolve()))
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


def parse_structured_test_report(output: str) -> dict[str, tuple[str, ...]]:
    """Read callback-derived test identities emitted by the child runner."""
    matches = list(STRUCTURED_REPORT_RE.finditer(output.replace("\r\n", "\n")))
    if not matches:
        return {key: () for key in ("selected", "executed", "skipped", "not_run")}
    try:
        value = json.loads(matches[-1].group(1))
    except json.JSONDecodeError:
        return {key: () for key in ("selected", "executed", "skipped", "not_run")}
    return {
        key: tuple(item for item in value.get(key, []) if isinstance(item, str))
        for key in ("selected", "executed", "skipped", "not_run")
    }


def _empty_structured_test_report() -> dict[str, tuple[str, ...]]:
    return {key: () for key in ("selected", "executed", "skipped", "not_run")}


def _physical_identity(path: Path) -> dict[str, int]:
    stat = path.stat()
    return {"st_dev": int(stat.st_dev), "st_ino": int(stat.st_ino)}


def _raw_identity(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {"byte_count": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _expected_child_subject(
    command: Sequence[str],
    environment: Mapping[str, str],
) -> dict[str, object] | None:
    """Derive the parent view without consuming any child report values."""
    profile = environment.get("BBK_TEST_PROFILE")
    if not profile:
        return None
    root = ROOT.resolve()
    cwd = root
    try:
        runner_index = next(index for index, value in enumerate(command) if Path(value).name == "test_module_runner.py")
        runner = Path(command[runner_index]).resolve()
    except (StopIteration, OSError):
        return None
    args = list(command[runner_index + 1:])
    profile_arg: str | None = None
    filtered: list[str] = []
    index = 0
    while index < len(args):
        value = args[index]
        if value in {"--bbk-profile", "--profile"}:
            profile_arg = args[index + 1] if index + 1 < len(args) else None
            index += 2
            continue
        filtered.append(value)
        index += 1
    if profile_arg and profile_arg != profile:
        return None
    args = filtered
    modules: list[Path] = []
    if "--discover" in args:
        discover_index = args.index("--discover")
        pattern = args[discover_index + 1] if discover_index + 1 < len(args) else "test*.py"
        modules = sorted(path.resolve() for path in (root / "tests").glob(pattern) if path.is_file())
    else:
        modules = [Path(value).resolve() for value in args if value.endswith(".py") and Path(value).is_file()]
    assigned: list[dict[str, object]] = []
    for path in modules:
        try:
            relative = path.relative_to(root).as_posix()
            physical = _physical_identity(path)
            identity = _raw_identity(path)
        except (OSError, ValueError):
            return None
        assigned.append({"relative_path": relative, "path": str(path), "physical": physical, **identity})
    subject: dict[str, object] = {
        "schema": STRUCTURED_SUBJECT_SCHEMA,
        "cwd": {"path": str(cwd), "physical": _physical_identity(cwd)},
        "root": {"path": str(root), "physical": _physical_identity(root)},
        "child_runner": {"path": str(runner), "physical": _physical_identity(runner), **_raw_identity(runner)},
        "assigned_modules": assigned,
        "interpreter": {
            "path": str(Path(sys.executable).resolve()),
            "implementation": sys.implementation.name,
            "version": platform.python_version(),
            "cache_tag": sys.implementation.cache_tag,
        },
        "profile": profile,
    }
    return subject


def _subject_digest(subject: Mapping[str, object]) -> str:
    encoded = json.dumps(subject, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _invalid_report(code: str, detail: str = "") -> None:
    raise StructuredReportError(code, detail)


def _validate_structured_report(
    value: object,
    *,
    expected_subject: Mapping[str, object] | None = None,
    expected_nonce: str | None = None,
    expected_profile: str | None = None,
    expected_modules: Sequence[Mapping[str, object]] | None = None,
    raw_count: int | None = None,
) -> dict[str, object]:
    if not isinstance(value, dict):
        _invalid_report("MALFORMED_REPORT", "root must be an object")
    if value.get("schema") != STRUCTURED_REPORT_SCHEMA:
        _invalid_report("SCHEMA_MISMATCH", "expected bbk.test-child-report.v2")
    required = ("nonce", "actual_subject", "actual_subject_sha256", "selected", "executed", "skipped", "not_run", "tests_run", "state")
    if any(key not in value for key in required):
        _invalid_report("MALFORMED_REPORT", "required field missing")
    if not isinstance(value.get("nonce"), (str, type(None))):
        _invalid_report("MALFORMED_REPORT", "nonce must be a string or null")
    if value.get("state") not in {"completed", "subject-invalid"}:
        _invalid_report("MALFORMED_REPORT", "unknown state")
    if expected_nonce is not None and value.get("nonce") != expected_nonce:
        _invalid_report("NONCE_MISMATCH")
    if value.get("subject_error"):
        _invalid_report("SUBJECT_INVALID", str(value["subject_error"]))
    subject = value.get("actual_subject")
    digest = value.get("actual_subject_sha256")
    if not isinstance(subject, dict) or subject.get("schema") != STRUCTURED_SUBJECT_SCHEMA:
        _invalid_report("SUBJECT_MISSING")
    if not isinstance(digest, str) or digest != _subject_digest(subject):
        _invalid_report("SUBJECT_DIGEST_MISMATCH")
    if expected_subject is not None:
        if subject != dict(expected_subject):
            _invalid_report("SUBJECT_MISMATCH")
        if digest != _subject_digest(expected_subject):
            _invalid_report("SUBJECT_DIGEST_MISMATCH")
    if expected_profile is not None and subject.get("profile") != expected_profile:
        _invalid_report("PROFILE_MISMATCH")
    if expected_modules is not None and subject.get("assigned_modules") != list(expected_modules):
        _invalid_report("MODULE_ASSIGNMENT_MISMATCH")
    result: dict[str, object] = {"schema": value["schema"], "nonce": value["nonce"], "actual_subject": subject, "actual_subject_sha256": digest}
    for key in ("selected", "executed", "skipped", "not_run"):
        raw = value.get(key)
        if not isinstance(raw, list) or not all(isinstance(item, str) and item for item in raw):
            _invalid_report("MALFORMED_REPORT", f"{key} must be a string list")
        if len(raw) != len(set(raw)):
            _invalid_report("DUPLICATE_IDENTITY", key)
        result[key] = tuple(raw)
    selected = set(result["selected"])
    executed = set(result["executed"])
    skipped = set(result["skipped"])
    not_run = set(result["not_run"])
    if (executed & skipped) or (executed & not_run) or (skipped & not_run):
        _invalid_report("IDENTITY_OVERLAP")
    if (executed | skipped | not_run) != selected:
        _invalid_report("IDENTITY_CLOSURE")
    tests_run = value.get("tests_run")
    if not isinstance(tests_run, int) or isinstance(tests_run, bool):
        _invalid_report("MALFORMED_REPORT", "tests_run must be an integer")
    expected_count = len(result["executed"]) + len(result["skipped"])
    if tests_run != expected_count or (raw_count is not None and raw_count != tests_run):
        _invalid_report("COUNT_MISMATCH", f"tests_run={tests_run}, raw={raw_count}")
    if value.get("state") == "completed" and not selected:
        _invalid_report("ZERO_SELECTED")
    if value.get("state") == "completed" and not_run:
        _invalid_report("NOT_RUN_ON_SUCCESS")
    result["tests_run"] = tests_run
    result["state"] = value["state"]
    return result


def read_structured_test_report(
    path: Path,
    *,
    strict: bool = False,
    expected_subject: Mapping[str, object] | None = None,
    expected_nonce: str | None = None,
    expected_profile: str | None = None,
    expected_modules: Sequence[Mapping[str, object]] | None = None,
    raw_count: int | None = None,
) -> dict[str, object]:
    """Read a child sidecar; strict mode is the managed PASS boundary."""
    try:
        if not path.is_file():
            _invalid_report("MISSING_REPORT")
        size = path.stat().st_size
        if size == 0:
            _invalid_report("MISSING_REPORT")
        if size > STRUCTURED_REPORT_MAX_BYTES:
            _invalid_report("REPORT_TOO_LARGE")
        value = json.loads(path.read_text(encoding="utf-8"))
        return _validate_structured_report(
            value,
            expected_subject=expected_subject,
            expected_nonce=expected_nonce,
            expected_profile=expected_profile,
            expected_modules=expected_modules,
            raw_count=raw_count,
        )
    except StructuredReportError:
        if strict:
            raise
        return _empty_structured_test_report()
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        if strict:
            raise StructuredReportError("MALFORMED_REPORT", f"{type(exc).__name__}: {exc}") from exc
        return _empty_structured_test_report()



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


def _duration_platform_key(platform_name: str | None = None) -> str:
    platform = (platform_name or os.name).lower()
    if platform in {"nt", "windows"}:
        return "windows"
    if platform in {"posix", "linux", "darwin"}:
        return "posix"
    return platform


def _duration_modules(value: Any, *, platform_name: str | None = None) -> dict[str, float]:
    modules = value.get("modules") if isinstance(value, dict) else None
    result: dict[str, float] = {}
    if isinstance(modules, dict):
        for name, raw in modules.items():
            if isinstance(name, str) and isinstance(raw, (int, float)) and raw > 0:
                result[name] = float(raw)
    if isinstance(value, dict) and platform_name:
        key = _duration_platform_key(platform_name)
        platform_values = value.get("platforms")
        platform_value = platform_values.get(key) if isinstance(platform_values, dict) else None
        if platform_value is None and isinstance(platform_values, dict):
            aliases = {"windows": ("nt",), "posix": ("linux", "darwin")}
            platform_value = next(
                (platform_values[name] for name in aliases.get(key, ()) if name in platform_values),
                None,
            )
        platform_modules = platform_value.get("modules") if isinstance(platform_value, dict) else platform_value
        if isinstance(platform_modules, dict):
            for name, raw in platform_modules.items():
                if isinstance(name, str) and isinstance(raw, (int, float)) and raw > 0:
                    result[name] = float(raw)
    return result


def _read_duration_value(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_duration_file(path: Path, *, platform_name: str | None = None) -> dict[str, float]:
    return _duration_modules(_read_duration_value(path), platform_name=platform_name)


def duration_seed_sha256(path: Path | None = None) -> str:
    candidate = path if path is not None else DURATION_SEED_PATH
    try:
        data = candidate.read_bytes()
    except OSError:
        data = b""
    return hashlib.sha256(data).hexdigest()


def _read_duration_cache(
    path: Path,
    *,
    seed_path: Path | None = None,
    platform_name: str | None = None,
) -> dict[str, float]:
    value = _read_duration_value(path)
    if not isinstance(value, dict):
        return {}
    if value.get("seed_sha256") != duration_seed_sha256(seed_path):
        return {}
    recorded_platform = value.get("platform")
    if recorded_platform is not None and recorded_platform != _duration_platform_key(platform_name):
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


def _attach_launch_ledger(report: dict[str, Any], *, child_scope: bool = False) -> bool:
    """Finalize the explicit launch ledger and fail closed on its integrity."""
    try:
        ledger = launch_recorder.finalize(exclude_enclosing_ancestor=child_scope)
    except launch_recorder.LaunchRecordError as exc:
        launch_recorder.persist_error_diagnostic(exc, report=report)
        return False
    if ledger is not None:
        report["launch_ledger"] = ledger
    return True


def update_duration_cache(
    report: Mapping[str, Any],
    *,
    seed_path: Path | None = None,
    platform_name: str | None = None,
) -> None:
    """Update retained module weights only from one-module process timings."""
    # Authoritative calibration is observational.  Its report may be handed
    # to this helper by generic callers, but it must never promote weights.
    if isinstance(report, Mapping) and (
        report.get("schema") == WINDOWS_CALIBRATION_SCHEMA
        or (isinstance(report.get("calibration"), Mapping) and report["calibration"].get("authoritative"))
    ):
        return
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
            and group.get("status") == "PASS"
            and isinstance(duration, (int, float))
            and duration > 0
        ):
            observed[modules[0]] = float(duration)
    if not observed:
        return
    path = duration_cache_path()
    selected_seed = seed_path if seed_path is not None else DURATION_SEED_PATH
    selected_platform = platform_name or os.name
    current = _read_duration_cache(
        path,
        seed_path=selected_seed,
        platform_name=selected_platform,
    )
    for name, duration in observed.items():
        previous = current.get(name)
        current[name] = duration if previous is None else round((previous * 0.6) + (duration * 0.4), 6)
    value = {
        "schema": "bbk.test-duration-cache.v1",
        "package_version": (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
        "seed_sha256": duration_seed_sha256(selected_seed),
        "platform": _duration_platform_key(selected_platform),
        "updated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "modules": dict(sorted(current.items())),
    }
    try:
        write_json_atomic(path, value)
    except OSError:
        pass


WINDOWS_CALIBRATION_SCHEMA = "bbk.windows-singleton-calibration.v1"


def calibration_rejection_reason(
    report: Mapping[str, Any],
    *,
    expected_modules: Sequence[str] | None = None,
    expected_subject: str = "BBK",
    expected_runtime: str | None = None,
    expected_seed_sha256: str | None = None,
) -> str | None:
    """Return a fail-closed reason for authoritative Windows calibration.

    This validator deliberately accepts only an explicitly isolated, standard
    profile run.  It is also used by tests and by callers consuming a report;
    no cache or packaged seed is modified here.
    """
    if not isinstance(report, Mapping):
        return "invalid-report"
    if report.get("schema") not in {"bbk.test-run.v1", WINDOWS_CALIBRATION_SCHEMA}:
        return "wrong-schema"
    if report.get("status") != "PASS" or report.get("exit_code", 0) != 0:
        return "non-pass"
    if report.get("platform", report.get("platform_name")) not in {"windows", "nt"}:
        return "wrong-platform"
    if report.get("profile") != "standard":
        return "wrong-profile"
    if report.get("mode") != "isolated" or report.get("requested_jobs") != 1:
        return "non-singleton"
    if report.get("subject", expected_subject) != expected_subject:
        return "wrong-subject"
    groups = report.get("groups")
    if not isinstance(groups, list) or not groups:
        return "missing-coverage"
    expected = list(expected_modules) if expected_modules is not None else None
    seen: list[str] = []
    for group in groups:
        if not isinstance(group, Mapping) or group.get("status") != "PASS":
            return "non-pass"
        modules = group.get("modules")
        duration = group.get("duration_seconds")
        if not isinstance(modules, list) or len(modules) != 1 or not isinstance(modules[0], str):
            return "non-singleton"
        if modules[0] in seen:
            return "duplicate-coverage"
        seen.append(modules[0])
        if not isinstance(duration, (int, float)) or duration <= 0:
            return "non-positive-duration"
        if group.get("timed_out") or group.get("partial") or group.get("not_run"):
            return "partial-coverage"
    if expected is not None and sorted(seen) != sorted(expected):
        return "missing-coverage" if len(seen) < len(expected) else "wrong-inventory"
    provenance = report.get("provenance")
    if not isinstance(provenance, Mapping):
        return "missing-provenance"
    for key in ("candidate", "runtime", "tool", "cpu", "inventory", "test"):
        if not provenance.get(key):
            return f"missing-{key}-provenance"
    if expected_runtime is not None:
        runtime = provenance.get("runtime", report.get("runtime"))
        runtime_value = runtime.get("python") if isinstance(runtime, Mapping) else runtime
        if runtime_value != expected_runtime:
            return "wrong-runtime"
    if expected_seed_sha256 is not None and report.get("seed_sha256") != expected_seed_sha256:
        return "stale-evidence"
    return None


def calibration_eligible(report: Mapping[str, Any], **kwargs: Any) -> bool:
    """Boolean convenience wrapper around :func:`calibration_rejection_reason`."""
    return calibration_rejection_reason(report, **kwargs) is None


# Descriptive aliases retained for callers that treat the report validator as
# a public runner interface.
validate_windows_singleton_calibration = calibration_rejection_reason
is_windows_singleton_calibration_eligible = calibration_eligible


def _calibration_provenance(files: Sequence[Path]) -> dict[str, Any]:
    """Capture non-authoritative runtime provenance for a calibration report."""
    inventory = [path.name for path in files]
    candidate = hashlib.sha256(
        json.dumps({"version": (ROOT / "VERSION").read_text(encoding="utf-8").strip(), "modules": inventory}, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {
        "candidate": {"sha256": candidate},
        "runtime": {"python": sys.version.split()[0], "executable": sys.executable},
        "tool": {"runner": str(Path(__file__).name), "version": (ROOT / "VERSION").read_text(encoding="utf-8").strip()},
        "cpu": {"count": os.cpu_count() or 1},
        "inventory": {"modules": inventory, "count": len(files)},
        "test": {"profile": "standard", "module_count": len(files)},
    }


def automatic_parallel_jobs(
    cpu_count: int | None = None,
    *,
    platform_name: str | None = None,
) -> int:
    """Return a conservative worker count for this process/I/O-heavy suite."""
    count = max(1, int(cpu_count if cpu_count is not None else (os.cpu_count() or 1)))
    # Windows process startup and handle sharing are materially more expensive,
    # but native duration weights keep its six high-core pools from combining
    # the slowest modules. Medium hosts remain bounded at four workers.
    if (platform_name or os.name).lower() == "nt":
        if count >= 12:
            return 6
        if count >= 6:
            return 4
        return min(3, count)
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


def load_duration_weights(
    path: Path | None = None,
    *,
    platform_name: str | None = None,
) -> dict[str, float]:
    """Load packaged weights plus a cache bound to the exact packaged seed."""
    selected_platform = platform_name or os.name
    seed_path = path if path is not None else DURATION_SEED_PATH
    result = _read_duration_file(seed_path, platform_name=selected_platform)
    result.update(
        _read_duration_cache(
            duration_cache_path(),
            seed_path=seed_path,
            platform_name=selected_platform,
        )
    )
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
    report_path: Path | None = None
    structured = _empty_structured_test_report()
    process: subprocess.Popen[bytes] | None = None
    launch: launch_recorder.LaunchHandle | None = None
    launch_completed = False
    launch_failure: launch_recorder.LaunchRecordError | None = None
    timed_out = False
    returncode = 2
    expected_subject: dict[str, object] | None = None
    report_nonce: str | None = None
    launch_command = list(command)
    try:
        capture_dir = None
        if raw_cache := os.environ.get("BBK_TEST_CACHE_DIR"):
            capture_dir = Path(raw_cache).expanduser() / "runtime" / "captures"
            capture_dir.mkdir(parents=True, exist_ok=True)
        mkstemp_kwargs = {"prefix": "bbk-test-suite-", "suffix": ".log"}
        if capture_dir is not None:
            mkstemp_kwargs["dir"] = str(capture_dir)
        fd, raw_capture = tempfile.mkstemp(**mkstemp_kwargs)
        os.close(fd)
        capture_path = Path(raw_capture)
        # Derive a sibling carrier from the already private capture name so
        # test doubles (and restricted hosts) need only one temp-file create.
        # ``x`` keeps an accidental pre-existing path from being overwritten.
        report_path = capture_path.with_suffix(".json")
        report_fd = os.open(
            str(report_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
        )
        os.close(report_fd)
        with capture_path.open("wb") as writer:
            managed_profile = os.environ.get("BBK_TEST_PROFILE")
            if managed_profile and "--bbk-profile" not in launch_command and "--profile" not in launch_command:
                try:
                    runner_index = next(index for index, value in enumerate(launch_command) if Path(value).name == "test_module_runner.py")
                except StopIteration:
                    runner_index = -1
                if runner_index >= 0:
                    launch_command[runner_index + 1:runner_index + 1] = ["--bbk-profile", managed_profile]
            report_nonce = uuid.uuid4().hex if managed_profile else None
            child_environment = _subprocess_environment(report_path=report_path, report_nonce=report_nonce)
            expected_subject = _expected_child_subject(launch_command, child_environment)
            launch = launch_recorder.prepare(
                launch_command,
                cwd=ROOT,
                environment=child_environment,
                kind="unittest-suite",
                require_evidence_root=True,
            )
            process = subprocess.Popen(
                launch_command,
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                stdout=writer,
                stderr=subprocess.STDOUT,
                env=child_environment,
                **creation,
            )
            launch.started(process.pid)

        decoder = codecs.getincrementaldecoder(SUBPROCESS_OUTPUT_ENCODING)(
            errors=SUBPROCESS_OUTPUT_ERRORS
        )
        chunks: list[str] = []
        started = time.monotonic()
        last_visible_activity = started
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
            if launch is not None:
                launch.completed(returncode=returncode, state="timed-out" if timed_out else "completed")
                launch_completed = True
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

        # A supplied sidecar is authoritative.  Do not fall back to stdout
        # when it is missing or malformed: nested child markers are precisely
        # the contamination boundary this carrier prevents.
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
        try:
            structured = read_structured_test_report(
                report_path,
                strict=True,
                expected_subject=expected_subject,
                expected_nonce=report_nonce,
                expected_profile=os.environ.get("BBK_TEST_PROFILE") or None,
                expected_modules=(expected_subject or {}).get("assigned_modules") if expected_subject else None,
                raw_count=parse_test_count(output),
            )
        except StructuredReportError as exc:
            issue = TestIssue("REPORT REJECTED", label, str(exc))
            return SuiteResult(label, 2, output, parse_test_count(output), (issue,), parse_skip_count(output))
    except (launch_recorder.LaunchRecordError, PythonLaunchInvariantError) as exc:
        if isinstance(exc, launch_recorder.LaunchRecordError):
            launch_failure = exc
        issue = TestIssue("PROCESS ERROR", label, f"{type(exc).__name__}: {exc}")
        return SuiteResult(label, 2, "", None, (issue,), 0)
    except OSError as exc:
        if launch is not None:
            launch.spawn_failed(exc)
        issue = TestIssue("PROCESS ERROR", label, f"{type(exc).__name__}: {exc}")
        return SuiteResult(label, 2, "", None, (issue,), 0)
    finally:
        if process is not None and process.poll() is None:
            try:
                _terminate_process_tree(process)
            except OSError:
                pass
        if process is not None:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                timed_out = True
        if launch is not None and process is not None and not launch_completed:
            observed = process.poll()
            if observed is None:
                observed = 2
            try:
                launch.completed(
                    returncode=observed,
                    state="timed-out" if timed_out else "completed",
                    error=(
                        f"{type(launch_failure).__name__}: {launch_failure}"
                        if launch_failure is not None
                        else ("suite process cleanup completed before launch finalization" if timed_out else None)
                    ),
                )
                launch_completed = True
            except launch_recorder.LaunchRecordError as exc:
                # Keep the underlying process/test result, while the later
                # aggregate receives the exact record identity and ownership
                # details from this durable integrity failure.
                launch_failure = exc
        if capture_path is not None:
            _remove_capture_file(capture_path)
        if report_path is not None:
            _remove_capture_file(report_path)

    # The private sidecar is authoritative for every managed child.  Stdout
    # marker parsing remains a standalone compatibility helper only.
    return SuiteResult(
        name=label,
        returncode=returncode,
        output=output,
        tests_run=parse_test_count(output),
        issues=parse_issues(output),
        skipped=parse_skip_count(output),
        selected_ids=structured["selected"],
        executed_ids=structured["executed"],
        skipped_ids=structured["skipped"],
        not_run_ids=structured["not_run"],
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


def _identity_report(results: Sequence[SuiteResult]) -> dict[str, Any]:
    selected = tuple(item for result in results for item in result.selected_ids)
    skipped = tuple(item for result in results for item in result.skipped_ids)
    skipped_set = set(skipped)
    executed = tuple(item for result in results for item in result.executed_ids if item not in skipped_set)
    not_run = tuple(item for result in results for item in result.not_run_ids)
    return {
        "selected": list(dict.fromkeys(selected)),
        "executed": list(dict.fromkeys(executed)),
        "skipped_ids": list(dict.fromkeys(skipped)),
        "not_run": list(dict.fromkeys(not_run)),
        "test_ids": {
            "selected": list(dict.fromkeys(selected)),
            "executed": list(dict.fromkeys(executed)),
            "skipped": list(dict.fromkeys(skipped)),
            "not_run": list(dict.fromkeys(not_run)),
        },
        "selected_count": len(selected),
        "executed_count": len(executed),
        "skipped_count": len(skipped),
        "not_run_count": len(not_run),
    }


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
    platform_name: str | None = None,
) -> list[list[Path]]:
    """Partition modules by retained measured duration, then source size."""
    count = min(len(files), max(1, int(processes)))
    if count == 0:
        return []
    original_order = {path.resolve(): index for index, path in enumerate(files)}
    measured = (
        duration_weights
        if duration_weights is not None
        else load_duration_weights(platform_name=platform_name)
    )

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
    groups = partition_test_files(files, process_count, platform_name=os.name)
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
        **_identity_report(results),
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
    if not _attach_launch_ledger(LAST_RUN_REPORT, child_scope=True):
        exit_code = 1
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
        **_identity_report([result]),
        "groups": [{
            "label": result.name,
            "modules": [path.name for path in files],
            "duration_seconds": round(elapsed, 6),
            "tests_reported": result.tests_run,
            "status": "PASS" if result.passed else "FAIL",
        }],
    }
    if not _attach_launch_ledger(LAST_RUN_REPORT, child_scope=True):
        exit_code = 1
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
        **_identity_report(results),
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
    if not _attach_launch_ledger(LAST_RUN_REPORT, child_scope=True):
        exit_code = 1
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
        **_identity_report(results),
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
    if not _attach_launch_ledger(LAST_RUN_REPORT, child_scope=True):
        exit_code = 1
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
    parser.add_argument(
        "--calibrate-windows-singleton", "--windows-singleton-calibration",
        action="store_true",
        help="run an explicit native-Windows standard isolated jobs=1 calibration (never promotes weights)",
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
    if args.calibrate_windows_singleton:
        if os.name != "nt":
            parser.error("Windows singleton calibration requires native Windows")
        if args.profile != "standard" or args.mode != "isolated" or args.jobs != 1:
            parser.error("Windows singleton calibration requires --profile standard --mode isolated --jobs 1")
        if not args.timing_report or args.no_timing_report:
            parser.error("Windows singleton calibration requires an explicit --timing-report path")
        if not os.environ.get("BBK_TEST_CACHE_DIR"):
            parser.error("Windows singleton calibration requires an isolated BBK_TEST_CACHE_DIR")
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
        if args.calibrate_windows_singleton:
            report["schema"] = WINDOWS_CALIBRATION_SCHEMA
            report["subject"] = "BBK"
            report["platform"] = "windows"
            report["seed_sha256"] = duration_seed_sha256(DURATION_SEED_PATH)
            report["provenance"] = _calibration_provenance(files)
            report["calibration"] = {
                "authoritative": True,
                "cache_mutated": False,
                "seed_promoted": False,
                "eligibility": calibration_rejection_reason(report, expected_modules=[path.name for path in files]),
            }
        report_path = None if args.no_timing_report else Path(args.timing_report).expanduser() if args.timing_report else default_timing_report_path()
        _store_run_report(report, report_path)
        if not args.calibrate_windows_singleton:
            update_duration_cache(report, platform_name=os.name)
        if report_path is not None:
            _write_text(sys.stdout, f"Timing report: {report_path}\n", flush=True)
        return exit_code



if __name__ == "__main__":
    raise SystemExit(main())
