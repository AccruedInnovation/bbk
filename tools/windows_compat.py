#!/usr/bin/env python3
"""Run native Windows probes for BBK path, console, and file-handle behavior.

The cross-platform unittest suite simulates Windows edge cases.  This probe adds
native coverage for the host behaviours that cannot be reproduced faithfully
on Linux: case-insensitive aliases, 8.3 names when enabled, directory junctions,
and deletion after a Win32 sharing violation.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable, Sequence

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from runtime_requirements import enforce_supported_python

enforce_supported_python(program="BBK Windows compatibility probe")

from path_compat import path_key
import run_tests


def _check(name: str, operation: Callable[[], dict[str, Any] | None]) -> dict[str, Any]:
    try:
        detail = operation() or {}
        return {"name": name, "status": "PASS", **detail}
    except Exception as exc:  # a probe should report every native failure together
        return {"name": name, "status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}


def _get_short_path(value: Path) -> str | None:
    import ctypes
    from ctypes import wintypes

    get_short = ctypes.windll.kernel32.GetShortPathNameW
    get_short.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    get_short.restype = wintypes.DWORD
    size = 32768
    buffer = ctypes.create_unicode_buffer(size)
    written = get_short(str(value), buffer, size)
    if not (0 < written < size):
        return None
    return buffer.value


def _case_alias_probe(target: Path) -> dict[str, Any]:
    alias = Path(str(target).swapcase())
    if not alias.exists():
        raise RuntimeError(f"case-variant path did not resolve: {alias}")
    if path_key(alias) != path_key(target):
        raise RuntimeError("case-variant path keys differ")
    return {"canonical_key": path_key(target), "alias": str(alias)}


def _short_alias_probe(target: Path) -> dict[str, Any]:
    short = _get_short_path(target)
    if not short or os.path.normcase(short) == os.path.normcase(str(target)):
        return {
            "status": "NOT_APPLICABLE",
            "reason": "8.3 short-name generation is disabled or produced no alternate spelling",
        }
    if path_key(short) != path_key(target):
        raise RuntimeError(f"8.3 and long-name keys differ: {short} != {target}")
    return {"short_path": short, "long_path": str(target), "canonical_key": path_key(target)}


def _junction_probe(root: Path, target: Path) -> dict[str, Any]:
    alias = root / "junction-alias"
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(alias), str(target)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    output = result.stdout.decode("mbcs", errors="backslashreplace").strip()
    if result.returncode != 0:
        return {"status": "NOT_APPLICABLE", "reason": output or f"mklink exited {result.returncode}"}
    try:
        alias_file = alias / "identity.txt"
        target_file = target / "identity.txt"
        if not alias_file.is_file():
            raise RuntimeError("junction did not expose the target file")
        if path_key(alias_file) != path_key(target_file):
            raise RuntimeError("junction and target path keys differ")
        return {"alias": str(alias), "target": str(target), "canonical_key": path_key(target_file)}
    finally:
        try:
            alias.rmdir()
        except OSError:
            subprocess.run(
                ["cmd.exe", "/d", "/c", "rmdir", str(alias)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )


def _locked_cleanup_probe(root: Path) -> dict[str, Any]:
    import ctypes
    from ctypes import wintypes

    capture = root / "locked-capture.log"
    capture.write_bytes(b"locked")
    create_file = ctypes.windll.kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    close_handle = ctypes.windll.kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    generic_read = 0x80000000
    open_existing = 3
    file_attribute_normal = 0x80
    invalid_handle = wintypes.HANDLE(-1).value
    handle = create_file(
        str(capture), generic_read, 0, None, open_existing, file_attribute_normal, None
    )
    if handle == invalid_handle:
        raise OSError(ctypes.get_last_error(), "CreateFileW could not acquire an exclusive handle")

    release_requested = threading.Event()
    released = threading.Event()

    def release() -> None:
        if not release_requested.wait(timeout=2):
            return
        close_handle(handle)
        released.set()

    thread = threading.Thread(target=release, daemon=True)
    thread.start()
    started = time.monotonic()
    # Coordinate the first retry explicitly instead of relying on a wall-clock
    # sleep.  The cleanup helper still owns retry semantics; this probe merely
    # releases the native handle at its first retry boundary.
    original_sleep = run_tests.time.sleep

    def request_release(_delay: float) -> None:
        release_requested.set()
        if not released.wait(timeout=2):
            raise RuntimeError("exclusive handle release did not complete")

    run_tests.time.sleep = request_release
    try:
        run_tests._remove_capture_file(capture, attempts=40, delay=0.025)
    finally:
        run_tests.time.sleep = original_sleep
    thread.join(timeout=2)
    elapsed = time.monotonic() - started
    if capture.exists():
        raise RuntimeError("capture file remained after the exclusive handle was released")
    return {"elapsed_seconds": round(elapsed, 3), "retries_exercised": released.is_set()}


def probe() -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema": "bbk.windows-compatibility.v1",
        "platform": sys.platform,
        "python": sys.executable,
        "filesystem_encoding": sys.getfilesystemencoding(),
        "stdout_encoding": getattr(sys.stdout, "encoding", None),
        "temp": tempfile.gettempdir(),
    }
    if os.name != "nt":
        report.update({"status": "NOT_APPLICABLE", "checks": []})
        return report

    with tempfile.TemporaryDirectory(prefix="BBK-Windows-Compatibility-") as raw:
        root = Path(raw)
        target = root / "Long Mixed Case Directory"
        target.mkdir()
        (target / "identity.txt").write_bytes(b"identity")
        checks = [
            _check("case-insensitive path identity", lambda: _case_alias_probe(target)),
            _check("8.3 short-name path identity", lambda: _short_alias_probe(target)),
            _check("directory-junction path identity", lambda: _junction_probe(root, target)),
            _check("WinError 32 capture cleanup retry", lambda: _locked_cleanup_probe(root)),
        ]
    report["checks"] = checks
    report["status"] = "FAIL" if any(item["status"] == "FAIL" for item in checks) else "PASS"
    return report


def human(report: dict[str, Any]) -> str:
    lines = [f"BBK native Windows compatibility: {report['status']}"]
    lines.append(f"Platform: {report['platform']}")
    lines.append(f"Python: {report['python']}")
    lines.append(f"Temporary directory: {report['temp']}")
    for item in report.get("checks", []):
        lines.append(f"- {item['name']}: {item['status']}")
        if item.get("reason"):
            lines.append(f"  {item['reason']}")
        if item.get("error"):
            lines.append(f"  {item['error']}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = probe()
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) if args.json else human(report))
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
