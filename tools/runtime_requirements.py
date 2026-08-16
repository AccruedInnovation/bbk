#!/usr/bin/env python3
"""Shared Python runtime floor for BBK command entry points.

Keep this module free of third-party and Python 3.11-only imports so older
interpreters can report the supported floor before importing the rest of BBK.
"""
import os
import platform
import sys
from pathlib import Path

MINIMUM_PYTHON = (3, 11)
MINIMUM_PYTHON_TEXT = "3.11"
DIRECT_PYTHON_WINDOWS = r"C:\Python313\python.exe"


class PythonLaunchInvariantError(RuntimeError):
    """Raised when a managed Python child cannot retain the qualified runtime."""


def direct_python_executable() -> str:
    """Return the one qualified child interpreter, failing closed on Windows."""
    if os.name != "nt":
        return str(Path(sys.executable).resolve())
    configured = os.environ.get("BBK_DIRECT_PYTHON_EXECUTABLE", DIRECT_PYTHON_WINDOWS)
    if Path(configured).resolve().as_posix().casefold() != Path(DIRECT_PYTHON_WINDOWS).resolve().as_posix().casefold():
        raise PythonLaunchInvariantError(
            f"direct Python invariant requires {DIRECT_PYTHON_WINDOWS}; got {configured}"
        )
    return DIRECT_PYTHON_WINDOWS


def qualified_pythonpath(environment=None) -> str:
    """Require the caller's explicit, ordered managed import closure."""
    source = os.environ if environment is None else environment
    value = str(source.get("BBK_QUALIFIED_PYTHONPATH") or source.get("PYTHONPATH") or "")
    if not value.strip():
        raise PythonLaunchInvariantError("direct Python invariant requires an explicit qualified PYTHONPATH")
    roots = [Path(item.strip()).expanduser() for item in value.split(os.pathsep) if item.strip()]
    if len(roots) != 3 or any(not root.is_dir() for root in roots):
        raise PythonLaunchInvariantError("direct Python invariant requires exactly three existing qualified import roots")
    if roots[1].name.casefold() != "tools" or roots[1].parent != roots[0]:
        raise PythonLaunchInvariantError("direct Python invariant requires ordered project and tools roots")
    managed = roots[-1]
    if managed.name.casefold() != "site-packages" or not all((managed / package).is_dir() for package in ("jsonschema", "referencing")):
        raise PythonLaunchInvariantError("direct Python invariant requires the managed jsonschema and referencing site-packages root")
    normalized = [str(root.resolve()) for root in roots]
    if len({root.casefold() for root in normalized}) != len(normalized):
        raise PythonLaunchInvariantError("direct Python invariant rejects duplicate qualified import roots")
    return os.pathsep.join(normalized)


def python_environment(environment=None, *, extra=None) -> dict[str, str]:
    """Preserve caller roots while forcing the managed Python policy."""
    result = dict(os.environ if environment is None else environment)
    qualified = qualified_pythonpath(result)
    result.update({str(key): str(value) for key, value in (extra or {}).items()})
    result["PYTHONDONTWRITEBYTECODE"] = "1"
    result["PYTHONNOUSERSITE"] = "1"
    result["PYTHONPATH"] = qualified
    result["BBK_QUALIFIED_PYTHONPATH"] = qualified
    return result


def python_command(script=None, *arguments, module=None, isolated=False) -> list[str]:
    """Build a direct Python argv with ``-B`` before script/module arguments."""
    if (script is None) == (module is None):
        raise ValueError("provide exactly one of script or module")
    command = [direct_python_executable(), "-B"]
    if isolated:
        command.append("-S")
    command.extend(("-X", "utf8"))
    command.extend(("-m", str(module)) if module is not None else (str(script),))
    command.extend(str(value) for value in arguments)
    return command


def normalize_python_command(command) -> list[str]:
    """Normalize a Python command constructor while preserving its arguments."""
    values = [str(value) for value in command]
    if not values:
        raise PythonLaunchInvariantError("managed Python command must not be empty")
    name = Path(values[0]).name.casefold()
    if name not in {"python", "python.exe", "python3", "python3.exe", "py", "py.exe"} and values[0] != sys.executable:
        return values
    arguments = [value for value in values[1:] if value not in {"-B", "-3"}]
    return [direct_python_executable(), "-B", *arguments]


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
    "DIRECT_PYTHON_WINDOWS",
    "MINIMUM_PYTHON",
    "MINIMUM_PYTHON_TEXT",
    "PythonLaunchInvariantError",
    "direct_python_executable",
    "enforce_supported_python",
    "normalize_python_command",
    "python_command",
    "python_environment",
    "qualified_pythonpath",
    "require_supported_python",
    "supported",
    "unsupported_message",
]
