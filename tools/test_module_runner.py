#!/usr/bin/env python3
"""Structured unittest child runner used by ``tools.run_tests``."""
from __future__ import annotations

import json
import os
import types
from pathlib import Path
import sys
import unittest

REPORT_ENV = "BBK_TEST_REPORT_JSON"
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


def main(argv: list[str]) -> int:
    # Capture the parent-owned sidecar before loading tests.  A test may alter
    # its process environment, but that must never redirect the final report.
    report_path = os.environ.get(REPORT_ENV)
    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite()
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
    skipped = list(dict.fromkeys(result.skipped_ids))
    skipped_set = set(skipped)
    executed = list(dict.fromkeys(test_id for test_id in result.executed if test_id not in skipped_set))
    executed_set = set(executed)
    payload = {
        "selected": selected,
        "executed": executed,
        "skipped": skipped,
        "not_run": [test_id for test_id in selected if test_id not in executed_set and test_id not in skipped_set],
    }
    encoded = json.dumps(payload, sort_keys=True)
    if report_path:
        try:
            destination = Path(report_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
            temporary.write_text(encoded + "\n", encoding="utf-8")
            os.replace(temporary, destination)
        except OSError as exc:
            try:
                temporary.unlink(missing_ok=True)
            except (NameError, OSError):
                pass
            print(f"BBK test report sidecar write failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2
    else:
        # Preserve direct/standalone runner usability when no parent has
        # supplied a private report carrier.
        print("BBK_TEST_REPORT_JSON:" + encoded)
    return 0 if result.wasSuccessful() else 1


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
        if not raw[index].startswith("-"):
            names.append(raw[index])
        index += 1
    raise SystemExit(main(names))
