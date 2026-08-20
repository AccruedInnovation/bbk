#!/usr/bin/env python3
"""Structured unittest child runner used by ``tools.run_tests``."""
from __future__ import annotations

import json
import hashlib
import os
import platform
import types
from pathlib import Path
import sys
import unittest

REPORT_ENV = "BBK_TEST_REPORT_JSON"
REPORT_NONCE_ENV = "BBK_TEST_REPORT_NONCE"
PROFILE_ENV = "BBK_TEST_PROFILE"
REPORT_SCHEMA = "bbk.test-child-report.v2"
SUBJECT_SCHEMA = "bbk.test-child-actual-subject.v1"
# Resolve the execution root from the child working directory when it exposes
# a tests package.  The structured runner is launched against temporary roots
# by pooled/isolated harnesses; anchoring discovery to this script's checkout
# silently yielded zero tests there.  Fall back to the repository containing
# this script for normal invocations.
_SCRIPT_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path.cwd() if (Path.cwd() / "tests").is_dir() else _SCRIPT_ROOT
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if "tests" not in sys.modules:
    package = types.ModuleType("tests")
    package.__path__ = [str(ROOT / "tests")]
    sys.modules["tests"] = package


class StructuredResult(unittest.TextTestResult):
    def __init__(self, *args, selected: list[str], **kwargs):
        super().__init__(*args, **kwargs)
        self.selected = selected
        self.executed: list[str] = []
        self.skipped_ids: list[str] = []

    def startTest(self, test):
        self.executed.append(test.id())
        super().startTest(test)

    def addSkip(self, test, reason):
        self.skipped_ids.append(test.id())
        super().addSkip(test, reason)


class StructuredRunner(unittest.TextTestRunner):
    resultclass = StructuredResult

    def __init__(self, *args, selected: list[str], **kwargs):
        self._selected = selected
        super().__init__(*args, **kwargs)

    def _makeResult(self):
        result = self.resultclass(self.stream, self.descriptions, self.verbosity,
                                  selected=self._selected)
        result.failfast = self.failfast
        result.buffer = self.buffer
        return result


def _flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _flatten(item)
        else:
            yield item


def _physical_identity(path: Path) -> dict[str, int]:
    stat = path.stat()
    return {"st_dev": int(stat.st_dev), "st_ino": int(stat.st_ino)}


def _raw_identity(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {
        "byte_count": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _under_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _actual_subject(names: list[str], *, profile_arg: str | None) -> dict[str, object]:
    cwd = Path.cwd().resolve()
    root = cwd if (cwd / "tests").is_dir() else _SCRIPT_ROOT
    root = root.resolve()
    runner = Path(__file__).resolve()
    environment_profile = os.environ.get(PROFILE_ENV)
    if profile_arg and environment_profile and profile_arg != environment_profile:
        raise ValueError("PROFILE_ENV_ARG_MISMATCH")
    profile = profile_arg or environment_profile
    if profile is None and os.environ.get(REPORT_NONCE_ENV):
        raise ValueError("MISSING_EXPLICIT_PROFILE")

    module_paths: list[Path] = []
    if "--discover" in names:
        index = names.index("--discover")
        pattern = names[index + 1] if index + 1 < len(names) else "test*.py"
        module_paths = sorted(path.resolve() for path in (root / "tests").glob(pattern) if path.is_file())
    else:
        for name in names:
            path = Path(name)
            if path.suffix == ".py" and path.is_file():
                module_paths.append(path.resolve())

    if any(not _under_root(path, root) for path in module_paths):
        raise ValueError("ENVIRONMENT_ESCAPE")
    assigned = []
    for path in module_paths:
        relative = path.relative_to(root).as_posix()
        identity = _raw_identity(path)
        assigned.append({
            "relative_path": relative,
            "path": str(path),
            "physical": _physical_identity(path),
            **identity,
        })
    subject: dict[str, object] = {
        "schema": SUBJECT_SCHEMA,
        "cwd": {"path": str(cwd), "physical": _physical_identity(cwd)},
        "root": {"path": str(root), "physical": _physical_identity(root)},
        "child_runner": {
            "path": str(runner),
            "physical": _physical_identity(runner),
            **_raw_identity(runner),
        },
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


def _subject_digest(subject: dict[str, object]) -> str:
    encoded = json.dumps(subject, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_report(path: Path, payload: dict[str, object]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(encoded, encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv: list[str]) -> int:
    # Capture the parent-owned sidecar before loading tests.  A test may alter
    # its process environment, but that must never redirect the final report.
    report_path = os.environ.get(REPORT_ENV)
    profile_arg: str | None = None
    filtered: list[str] = []
    index = 0
    while index < len(argv):
        value = argv[index]
        if value in {"--bbk-profile", "--profile"}:
            profile_arg = argv[index + 1] if index + 1 < len(argv) else None
            index += 2
            continue
        filtered.append(value)
        index += 1
    argv = filtered
    nonce = os.environ.get(REPORT_NONCE_ENV)
    subject: dict[str, object] | None = None
    subject_error: str | None = None
    try:
        subject = _actual_subject(argv, profile_arg=profile_arg)
    except (OSError, ValueError) as exc:
        subject_error = str(exc) or type(exc).__name__
    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite()
    if subject_error is None:
        if "--discover" in argv:
            index = argv.index("--discover")
            pattern = argv[index + 1] if index + 1 < len(argv) else "test*.py"
            suite.addTests(loader.discover(str(ROOT / "tests"), pattern=pattern))
            argv = argv[:index] + argv[index + 2:]
        for name in argv:
            if name.endswith(".py") and Path(name).is_file():
                suite.addTests(loader.discover(str(Path(name).parent), pattern=Path(name).name))
            else:
                suite.addTests(loader.loadTestsFromName(name))
    selected = [test.id() for test in _flatten(suite)]
    runner = StructuredRunner(verbosity=2 if "-v" in sys.argv else 1,
                              failfast="-f" in sys.argv,
                              buffer="-b" in sys.argv,
                              selected=selected)
    result = runner.run(suite)
    skipped = list(result.skipped_ids)
    skipped_set = set(skipped)
    executed = [test_id for test_id in result.executed if test_id not in skipped_set]
    executed_set = set(executed)
    payload = {
        "schema": REPORT_SCHEMA,
        "nonce": nonce,
        "actual_subject": subject,
        "actual_subject_sha256": _subject_digest(subject) if subject is not None else None,
        "subject_error": subject_error,
        "selected": selected,
        "executed": executed,
        "skipped": skipped,
        "not_run": [test_id for test_id in selected if test_id not in executed_set and test_id not in skipped_set],
        "tests_run": len(executed) + len(skipped),
        "state": "completed" if subject_error is None else "subject-invalid",
    }
    if report_path:
        try:
            destination = Path(report_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            _write_report(destination, payload)
        except OSError as exc:
            print(f"BBK test report sidecar write failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2
    else:
        # Preserve direct/standalone runner usability when no parent has
        # supplied a private report carrier.
        print("BBK_TEST_REPORT_JSON:" + json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result.wasSuccessful() and subject_error is None else 1


if __name__ == "__main__":
    # unittest options are consumed by this runner; module names are positional.
    raw = sys.argv[1:]
    names = []
    index = 0
    while index < len(raw):
        if raw[index] == "--discover":
            names.extend(raw[index:index + 2])
            index += 2
            continue
        if raw[index] in {"--bbk-profile", "--profile"}:
            names.extend(raw[index:index + 2])
            index += 2
            continue
        if not raw[index].startswith("-"):
            names.append(raw[index])
        index += 1
    raise SystemExit(main(names))
