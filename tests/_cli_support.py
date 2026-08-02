"""Fast, subprocess-faithful helpers for BBK behavior-level tests.

The public Python command entry points are ordinary ``main`` functions. Most
regression tests need their argument, environment, output, and exit semantics;
they do not need to pay for a fresh Python interpreter on every assertion.
Canonical BBK scripts therefore execute in-process by default. Content-identical
installed copies of selected BBK scripts are also loaded once per path and
reused, preserving their path-relative behavior without repeated interpreter
startup.

Real subprocesses remain available and are still used for interpreter-isolation,
``-S``/``-I`` behavior, installed-launcher, Node, Git, process-tree, raw-byte,
and deliberately tampered-script tests.
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import inspect
import io
import os
import runpy
import subprocess
import sys
import time
import traceback
from pathlib import Path
from types import ModuleType
from typing import Callable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
DEFAULT_REAL_SUBPROCESS_TIMEOUT = 120.0
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

# Scripts whose public main entry point is safe and useful to exercise in the
# current test interpreter. Loading is lazy so a small test does not import the
# entire BBK tool surface. The two high-frequency CLIs are preloaded below to
# preserve their established shared-module behavior.
_CANONICAL_SCRIPT_NAMES = {
    "assemble_roles.py",
    "bbk.py",
    "create_method_content.py",
    "create_role_spec.py",
    "generate_agents.py",
    "install.py",
    "install_profiles.py",
    "model_routing.py",
    "omp_model_routing.py",
    "prompt_modules.py",
    "return_contracts.py",
    "setup.py",
    "source_sanity.py",
    "update_codex.py",
    "update_omp.py",
    "validate_alpha7_fixtures.py",
    "validate_alpha8_fixtures.py",
    "validate_contract_package.py",
    "verify_package.py",
    "windows_compat.py",
}

# Installed copies are eligible only for scripts whose behavior intentionally
# derives from their own location. Byte equality with the canonical source is
# mandatory; a modified copy is always executed as a real child so the helper
# cannot conceal installation or tampering defects.
_CONTENT_IDENTICAL_COPY_NAMES = {
    "bbk.py",
    "omp_model_routing.py",
    "update_codex.py",
    "update_omp.py",
}

_MODULE_CACHE: dict[Path, ModuleType] = {}
_MAIN_CACHE: dict[Path, Callable[..., object]] = {}
_DIGEST_CACHE: dict[Path, tuple[int, int, str]] = {}

# Preserve the established shared-module behavior for the two highest-frequency
# CLIs. Other tools remain lazy.
import bbk as _bbk_tool
import install as _install_tool
_MAIN_CACHE[(TOOLS / "bbk.py").resolve()] = _bbk_tool.main
_MAIN_CACHE[(TOOLS / "install.py").resolve()] = _install_tool.main

_ORIGINAL_BBK_RUN = _bbk_tool.run
_FIXTURE_PROFILE_ROOT = (ROOT / "fixtures" / "profiles").resolve()


def _fixture_python_script(command: Sequence[str]) -> tuple[Path, list[str]] | None:
    """Recognize trusted package-local profile fixtures invoked by BBK."""
    if not command:
        return None
    try:
        if Path(command[0]).resolve() != Path(sys.executable).resolve():
            return None
    except OSError:
        return None
    index = 1
    while index < len(command) and command[index] in {"-B", "-u"}:
        index += 1
    if index >= len(command) or command[index].startswith("-"):
        return None
    try:
        script = Path(command[index]).resolve(strict=True)
        script.relative_to(_FIXTURE_PROFILE_ROOT)
    except (OSError, ValueError):
        return None
    if script.name != "profile.py" or script.parent.name != "tools":
        return None
    return script, list(command[index + 1 :])


def _bbk_run_with_fast_fixtures(
    argv: Sequence[str],
    cwd: Path,
    *,
    timeout: float | None = None,
    env: dict[str, str] | None = None,
):
    """Execute trusted profile fixtures in-process for behavior tests only."""
    command = [str(item) for item in argv]
    parsed = _fixture_python_script(command)
    if parsed is None:
        return _ORIGINAL_BBK_RUN(argv, cwd, timeout=timeout, env=env)
    script, script_argv = parsed
    started = time.monotonic()
    stdout = io.StringIO()
    stderr = io.StringIO()
    returncode = 0
    with process_context(cwd=cwd, env=env), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        sys.argv[:] = [str(script), *script_argv]
        try:
            runpy.run_path(str(script), run_name="__main__")
        except SystemExit as exc:
            code = exc.code
            if code is None:
                returncode = 0
            elif isinstance(code, int):
                returncode = code
            else:
                print(code, file=sys.stderr)
                returncode = 1
        except BaseException:
            traceback.print_exc()
            returncode = 1
    return {
        "argv": command,
        "cwd": str(cwd),
        "returncode": returncode,
        "stdout": stdout.getvalue(),
        "stderr": stderr.getvalue(),
        "duration_seconds": round(time.monotonic() - started, 6),
        "timed_out": False,
        "executable": str(Path(sys.executable).resolve()),
    }


_bbk_tool.run = _bbk_run_with_fast_fixtures


@contextlib.contextmanager
def process_context(*, cwd: str | os.PathLike[str] | None, env: Mapping[str, str] | None):
    """Temporarily apply subprocess-equivalent cwd and environment state."""
    previous_cwd = Path.cwd()
    previous_env = os.environ.copy()
    previous_argv = sys.argv[:]
    try:
        if cwd is not None:
            os.chdir(cwd)
        if env is not None:
            os.environ.clear()
            os.environ.update({str(key): str(value) for key, value in env.items()})
        yield
    finally:
        os.chdir(previous_cwd)
        sys.argv[:] = previous_argv
        # A real child cannot mutate its parent's environment. Restore it even
        # when the caller inherited the current environment implicitly.
        os.environ.clear()
        os.environ.update(previous_env)


def _sha256(path: Path) -> str:
    stat = path.stat()
    cached = _DIGEST_CACHE.get(path)
    marker = (stat.st_size, stat.st_mtime_ns)
    if cached is not None and cached[:2] == marker:
        return cached[2]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    _DIGEST_CACHE[path] = (marker[0], marker[1], digest)
    return digest


def _eligible_script(path: Path) -> bool:
    """Return whether *path* may execute through a cached ``main`` function."""
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        return False
    canonical = (TOOLS / resolved.name).resolve()
    if resolved == canonical:
        return resolved.name in _CANONICAL_SCRIPT_NAMES
    if resolved.name not in _CONTENT_IDENTICAL_COPY_NAMES or not canonical.is_file():
        return False
    try:
        return _sha256(resolved) == _sha256(canonical)
    except OSError:
        return False


def _load_main(script: Path) -> Callable[..., object]:
    resolved = script.resolve()
    cached = _MAIN_CACHE.get(resolved)
    if cached is not None:
        return cached

    # Use a path-derived private name. Loading the actual script path preserves
    # __file__, SCRIPT_DIR, and package-root behavior for installed copies.
    module_name = f"_bbk_test_cli_{resolved.stem}_{hashlib.sha256(str(resolved).encode()).hexdigest()[:16]}"
    spec = importlib.util.spec_from_file_location(module_name, resolved)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load BBK CLI script: {resolved}")
    module = importlib.util.module_from_spec(spec)
    previous_path = sys.path[:]
    try:
        if str(resolved.parent) not in sys.path:
            sys.path.insert(0, str(resolved.parent))
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    finally:
        sys.path[:] = previous_path
    main = getattr(module, "main", None)
    if not callable(main):
        raise ImportError(f"BBK CLI script has no callable main(): {resolved}")
    _MODULE_CACHE[resolved] = module
    _MAIN_CACHE[resolved] = main
    return main


def _python_script(args: Sequence[str]) -> tuple[Path, list[str]] | None:
    """Return a supported script and its argv, or ``None`` for a real process."""
    if not args:
        return None
    try:
        if Path(args[0]).resolve() != Path(sys.executable).resolve():
            return None
    except OSError:
        return None
    index = 1
    while index < len(args) and args[index] in {"-B", "-E", "-I", "-s", "-S", "-u"}:
        # -I/-E/-s/-S affect import/environment semantics and therefore must
        # retain a real interpreter. -B and -u are safe for captured tests.
        if args[index] in {"-E", "-I", "-s", "-S"}:
            return None
        index += 1
    if index >= len(args) or args[index].startswith("-"):
        return None
    try:
        script = Path(args[index]).resolve()
    except OSError:
        return None
    if not _eligible_script(script):
        return None
    return script, list(args[index + 1 :])


def _invoke_main(main: Callable[..., object], script: Path, argv: list[str]) -> int:
    """Invoke either ``main(argv)`` or legacy ``main()`` faithfully."""
    sys.argv[:] = [str(script), *argv]
    try:
        parameters = inspect.signature(main).parameters
    except (TypeError, ValueError):
        parameters = {"argv": object()}
    value = main() if len(parameters) == 0 else main(argv)
    return int(value or 0)


def run_cli(
    command: Sequence[str | os.PathLike[str]],
    *,
    cwd: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
    check: bool = True,
    force_subprocess: bool = False,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command with ``subprocess.run``-compatible captured semantics.

    Supported BBK Python scripts execute through cached public ``main`` entry
    points unless ``force_subprocess`` is requested. Every other command is
    delegated to a real child process.
    """
    args = [str(value) for value in command]
    parsed = None if force_subprocess else _python_script(args)
    if parsed is None:
        return subprocess.run(
            args,
            cwd=str(cwd or ROOT),
            env=dict(env) if env is not None else None,
            check=check,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=DEFAULT_REAL_SUBPROCESS_TIMEOUT if timeout is None else timeout,
        )

    script, argv = parsed
    stdout = io.StringIO()
    stderr = io.StringIO()
    with process_context(cwd=cwd or ROOT, env=env), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            returncode = _invoke_main(_load_main(script), script, argv)
        except SystemExit as exc:
            returncode = int(exc.code or 0)
    result = subprocess.CompletedProcess(args, returncode, stdout.getvalue(), stderr.getvalue())
    if check and returncode != 0:
        raise subprocess.CalledProcessError(
            returncode,
            args,
            output=result.stdout,
            stderr=result.stderr,
        )
    return result


def run_json(
    command: Sequence[str | os.PathLike[str]],
    *,
    cwd: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
    check: bool = True,
    force_subprocess: bool = False,
    timeout: float | None = None,
):
    """Return decoded JSON and the completed process-style result."""
    import json

    result = run_cli(
        command,
        cwd=cwd,
        env=env,
        check=check,
        force_subprocess=force_subprocess,
        timeout=timeout,
    )
    return json.loads(result.stdout), result
