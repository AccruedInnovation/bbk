#!/usr/bin/env python3
"""Filesystem-identity helpers for cross-platform BBK ownership checks.

Windows can expose one file through long names, 8.3 short names, case variants,
and directory aliases.  ``Path`` equality and a plain ``abspath`` comparison do
not collapse every one of those spellings.  BBK uses these helpers anywhere a
path is a dictionary key or an ownership/collision boundary.
"""
from __future__ import annotations

import ntpath
import os
from pathlib import Path
from typing import Callable, TypeAlias

PathValue: TypeAlias = str | os.PathLike[str]


def _windows_long_name(value: str) -> str:
    """Expand an existing Windows path to its long-name spelling when possible."""
    if os.name != "nt":
        return value
    try:
        import ctypes
        from ctypes import wintypes

        get_long = ctypes.windll.kernel32.GetLongPathNameW
        get_long.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
        get_long.restype = wintypes.DWORD
        size = 32768
        buffer = ctypes.create_unicode_buffer(size)
        written = get_long(value, buffer, size)
        if 0 < written < size:
            return buffer.value
        if written >= size:
            buffer = ctypes.create_unicode_buffer(written + 1)
            written = get_long(value, buffer, len(buffer))
            if 0 < written < len(buffer):
                return buffer.value
    except (AttributeError, ImportError, OSError, ValueError):
        pass
    return value


def _expand_existing_windows_prefix(
    value: str,
    *,
    exists: Callable[[str], bool] | None = None,
    long_name: Callable[[str], str] | None = None,
) -> str:
    """Long-name the deepest existing prefix and retain any missing suffix.

    The injectable functions make the 8.3-to-long-name algorithm testable on
    non-Windows CI without pretending that POSIX path semantics are Windows
    semantics.  Production calls use the native filesystem and Win32 API.
    """
    if os.name != "nt" and exists is None and long_name is None:
        return value
    exists_fn = exists or os.path.exists
    long_name_fn = long_name or _windows_long_name
    current = value
    suffix: list[str] = []
    while not exists_fn(current):
        parent, name = ntpath.split(current)
        if not name or parent == current:
            return value
        suffix.append(name)
        current = parent
    expanded = long_name_fn(current)
    if suffix:
        expanded = ntpath.join(expanded, *reversed(suffix))
    return expanded


def canonical_path_text(path: PathValue) -> str:
    """Return a best-effort physical path spelling suitable for identity checks.

    ``realpath`` collapses symlinks and Windows directory junctions.  The
    Windows long-name pass additionally collapses 8.3 aliases for existing path
    components.  Missing leaf components are retained after the deepest
    existing canonical parent, which keeps install-plan preflight useful before
    files are created.
    """
    raw = os.path.expanduser(os.fspath(path))
    absolute = os.path.abspath(raw)
    try:
        resolved = os.path.realpath(absolute)
    except OSError:
        resolved = absolute
    resolved = _expand_existing_windows_prefix(resolved)
    return os.path.normpath(resolved)


def path_key(path: PathValue) -> str:
    """Return a native-host key for one physical filesystem destination.

    This follows the current host's case rules: case-insensitive on Windows and
    case-sensitive on POSIX. Use :func:`portable_path_key` for install-plan
    collision checks that must also reject destinations differing only by case
    or slash spelling before a package is moved between operating systems.
    """
    return os.path.normcase(canonical_path_text(path)).replace("\\", "/")


def portable_path_key(path: PathValue) -> str:
    """Return a cross-platform-safe destination ownership key.

    BBK packages and installation plans are portable even when generated or
    tested on a case-sensitive host.  Canonicalize physical aliases first, then
    normalize both slash spelling and case so ``C:/x`` and ``c:\\x`` cannot
    become two owners of the same destination when the plan reaches Windows.
    The deliberately conservative case fold also rejects case-only collisions
    on POSIX instead of producing a package that is unsafe to install elsewhere.
    """
    return canonical_path_text(path).replace("\\", "/").casefold()


def same_path(left: PathValue, right: PathValue) -> bool:
    """Return whether two spellings identify the same canonical destination."""
    return path_key(left) == path_key(right)
