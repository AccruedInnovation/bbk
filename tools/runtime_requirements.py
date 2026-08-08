#!/usr/bin/env python3
"""Shared Python runtime floor for BBK command entry points.

Keep this module free of third-party and Python 3.11-only imports so older
interpreters can report the supported floor before importing the rest of BBK.
"""
import platform
import sys

MINIMUM_PYTHON = (3, 11)
MINIMUM_PYTHON_TEXT = "3.11"


def supported(version_info=None):
    """Return whether *version_info* meets BBK's public Python floor."""
    value = sys.version_info if version_info is None else version_info
    return tuple(value[:2]) >= MINIMUM_PYTHON


def unsupported_message(program="BBK"):
    return (
        f"{program} requires Python {MINIMUM_PYTHON_TEXT} or newer; "
        f"this interpreter is Python {platform.python_version()}."
    )


def require_supported_python(*, program="BBK", stream=None):
    """Print one clear error and return ``False`` on an old interpreter."""
    if supported():
        return True
    target = sys.stderr if stream is None else stream
    print(unsupported_message(program), file=target)
    print("No BBK files were changed.", file=target)
    return False


def enforce_supported_python(*, program="BBK", exit_code=2):
    """Exit before loading BBK internals when Python is too old."""
    if not require_supported_python(program=program):
        raise SystemExit(exit_code)


__all__ = [
    "MINIMUM_PYTHON",
    "MINIMUM_PYTHON_TEXT",
    "enforce_supported_python",
    "require_supported_python",
    "supported",
    "unsupported_message",
]
