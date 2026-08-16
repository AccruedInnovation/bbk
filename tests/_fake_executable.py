from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

TOOLS_ROOT = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))
from runtime_requirements import direct_python_executable


def _windows_launcher(path: Path) -> Path:
    return path if path.suffix.lower() == ".cmd" else path.with_name(path.name + ".cmd")


def _windows_payload(launcher: Path) -> Path:
    # Do not name the Python payload ``<command>.py``. On Windows, users may
    # include .PY in PATHEXT; after a test removes the .cmd launcher, command
    # discovery could then mistake the payload for the executable itself.
    return launcher.with_name(f".{launcher.name}.py")


def write_python_executable(
    path: Path,
    source: str,
    *,
    platform_name: str | None = None,
) -> Path:
    """Write a small Python-backed command that runs on POSIX and Windows."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    source = source.rstrip() + "\n"

    if (platform_name or os.name) == "nt":
        launcher = _windows_launcher(path)
        script = _windows_payload(launcher)
        legacy_payload = launcher.with_suffix(".py")
        if legacy_payload != script and legacy_payload.is_file():
            legacy_payload.unlink()
        script.write_text(source, encoding="utf-8", newline="\n")
        launcher.write_text(
            "@echo off\r\n"
            f'if defined BBK_PYTHON if /I not "%BBK_PYTHON%"=="{direct_python_executable()}" exit /b 2\r\n'
            'if not defined BBK_QUALIFIED_PYTHONPATH if not defined PYTHONPATH exit /b 2\r\n'
            'set "PYTHONDONTWRITEBYTECODE=1"\r\n'
            'set "PYTHONNOUSERSITE=1"\r\n'
            f'"{direct_python_executable()}" -B -S -X utf8 "%~dp0{script.name}" %*\r\n'
            "exit /b %ERRORLEVEL%\r\n",
            encoding="utf-8",
            newline="",
        )
        return launcher.resolve()

    path.write_text(
        f"#!{sys.executable} -B -S -X utf8\n" + source,
        encoding="utf-8",
        newline="\n",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path.resolve()
