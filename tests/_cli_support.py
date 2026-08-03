"""Fast, subprocess-faithful helpers for BBK behavior-level tests.

The public command entry points are ordinary ``main(argv)`` functions. Most
regression tests need their argument, environment, output, and exit semantics;
they do not need to pay for a fresh Python interpreter on every assertion.
Real subprocesses remain available and are still used for interpreter-isolation,
installed-launcher, Node, Git, and process-tree behavior.
"""
from __future__ import annotations

import contextlib
import io
import os
import runpy
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
DEFAULT_REAL_SUBPROCESS_TIMEOUT = 120.0
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import assemble_roles as assemble_roles_tool
import bbk as bbk_tool
import install as install_tool
import model_routing as model_routing_tool
import omp_model_routing as omp_model_routing_tool
import return_contracts as return_contracts_tool
import setup as setup_tool
import source_sanity as source_sanity_tool
import update_codex as update_codex_tool
import update_omp as update_omp_tool
import validate_alpha7_fixtures as validate_alpha7_tool
import validate_alpha8_fixtures as validate_alpha8_tool
import validate_contract_package as validate_contract_package_tool
import verify_package as verify_package_tool

_IN_PROCESS_CLIS = {
    (TOOLS / "assemble_roles.py").resolve(): assemble_roles_tool.main,
    (TOOLS / "create_role_spec.py").resolve(): assemble_roles_tool.main,
    (TOOLS / "bbk.py").resolve(): bbk_tool.main,
    (TOOLS / "install.py").resolve(): install_tool.main,
    (TOOLS / "model_routing.py").resolve(): model_routing_tool.main,
    (TOOLS / "omp_model_routing.py").resolve(): omp_model_routing_tool.main,
    (TOOLS / "return_contracts.py").resolve(): return_contracts_tool.main,
    (TOOLS / "setup.py").resolve(): setup_tool.main,
    (TOOLS / "source_sanity.py").resolve(): source_sanity_tool.main,
    (TOOLS / "update_codex.py").resolve(): update_codex_tool.main,
    (TOOLS / "update_omp.py").resolve(): update_omp_tool.main,
    (TOOLS / "validate_alpha7_fixtures.py").resolve(): validate_alpha7_tool.main,
    (TOOLS / "validate_alpha8_fixtures.py").resolve(): validate_alpha8_tool.main,
    (TOOLS / "validate_contract_package.py").resolve(): validate_contract_package_tool.main,
    (TOOLS / "verify_package.py").resolve(): verify_package_tool.main,
}

_COPIED_CLI_SOURCES = {
    "omp_model_routing.py": (TOOLS / "omp_model_routing.py").resolve(),
}


@contextlib.contextmanager
def process_context(*, cwd: str | os.PathLike[str] | None, env: Mapping[str, str] | None):
    """Temporarily apply subprocess-equivalent cwd and environment state."""
    previous_cwd = Path.cwd()
    previous_env = os.environ.copy()
    try:
        if cwd is not None:
            os.chdir(cwd)
        if env is not None:
            os.environ.clear()
            os.environ.update({str(key): str(value) for key, value in env.items()})
        yield
    finally:
        os.chdir(previous_cwd)
        # A real child cannot mutate its parent's environment. Restore it even
        # when the caller inherited the current environment implicitly.
        os.environ.clear()
        os.environ.update(previous_env)


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
    while index < len(args) and args[index] in {"-B", "-E", "-I", "-s", "-u"}:
        # -I/-E/-s affect import/environment semantics and therefore must retain
        # a real interpreter. -B and -u are safe for captured behavior tests.
        if args[index] in {"-E", "-I", "-s"}:
            return None
        index += 1
    if index >= len(args) or args[index].startswith("-"):
        return None
    try:
        script_spelling = Path(os.path.abspath(os.fspath(args[index])))
        script = script_spelling.resolve()
    except OSError:
        return None
    argv = list(args[index + 1 :])
    if script in _IN_PROCESS_CLIS:
        return script, argv

    # Installed OMP routing commands are byte-identical copies of the packaged
    # source tool. Most routing tests need the copied tool's argument and state
    # semantics, not another interpreter startup. Bind the canonical main()
    # function to the copied script's adjacent installation binding. A separate
    # system test still executes the installed CLI through a real child process.
    source = _COPIED_CLI_SOURCES.get(script.name)
    binding = script_spelling.parent / "bbk-package-root.json"
    try:
        is_trusted_copy = (
            source is not None
            and script.is_file()
            and binding.is_file()
            and script.read_bytes() == source.read_bytes()
        )
    except OSError:
        is_trusted_copy = False
    if not is_trusted_copy:
        return None
    if "--binding" not in argv:
        argv = ["--binding", str(binding), *argv]
    return source, argv



def _eligible_nested_python_script(argv: Sequence[str]) -> tuple[Path, list[str]] | None:
    """Return a package-local Python script eligible for test-only in-process execution.

    BBK profile-dispatch fixtures intentionally use ordinary Python entrypoints.
    Starting a new interpreter for every fixture capability dominates Windows
    regression time and adds no isolation value: each script is pure, package-
    local, and receives all state through argv/files/environment.  Real package
    commands, installed launchers, and process-behavior tests remain subprocesses.
    """
    if len(argv) < 2:
        return None
    try:
        if Path(argv[0]).resolve() != Path(sys.executable).resolve():
            return None
        script = Path(argv[1]).resolve()
        fixture_root = (ROOT / "fixtures" / "profiles").resolve()
        script.relative_to(fixture_root)
    except (OSError, ValueError):
        return None
    if script.suffix.lower() != ".py" or not script.is_file():
        return None
    return script, list(argv[2:])


def _run_nested_python_script(
    argv: Sequence[str],
    cwd: Path,
    *,
    timeout: float | None,
    env: Mapping[str, str] | None,
) -> dict[str, Any] | None:
    """Execute an eligible fixture script without another interpreter startup."""
    parsed = _eligible_nested_python_script(argv)
    if parsed is None:
        return None
    script, script_argv = parsed
    stdout = io.StringIO()
    stderr = io.StringIO()
    started = time.monotonic()
    previous_argv = sys.argv[:]
    returncode = 0
    try:
        with process_context(cwd=cwd, env=env), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            sys.argv = [str(script), *script_argv]
            try:
                runpy.run_path(str(script), run_name="__main__")
            except SystemExit as exc:
                code = exc.code
                if code is None:
                    returncode = 0
                elif isinstance(code, int):
                    returncode = code
                else:
                    print(str(code), file=sys.stderr)
                    returncode = 1
            except BaseException:
                traceback.print_exc()
                returncode = 1
    finally:
        sys.argv = previous_argv
    return {
        "argv": [str(value) for value in argv],
        "cwd": str(cwd),
        "returncode": returncode,
        "stdout": stdout.getvalue(),
        "stderr": stderr.getvalue(),
        "duration_seconds": round(time.monotonic() - started, 6),
        "timed_out": False,
        "executable": shutil.which(str(argv[0]), path=(env or os.environ).get("PATH")),
    }


@contextlib.contextmanager
def accelerate_nested_profile_python() -> Iterable[None]:
    """Patch BBK's child runner only for deterministic fixture Python scripts."""
    original = bbk_tool.run

    def accelerated(
        argv: Sequence[str],
        cwd: Path,
        *,
        timeout: float | None = None,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        result = _run_nested_python_script(argv, cwd, timeout=timeout, env=env)
        return result if result is not None else original(argv, cwd, timeout=timeout, env=env)

    bbk_tool.run = accelerated
    try:
        yield
    finally:
        bbk_tool.run = original

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

    Supported BBK Python scripts execute through their public ``main(argv)``
    entry points unless ``force_subprocess`` is requested. Every other command
    is delegated to a real child process.
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
    with (
        process_context(cwd=cwd or ROOT, env=env),
        accelerate_nested_profile_python(),
        contextlib.redirect_stdout(stdout),
        contextlib.redirect_stderr(stderr),
    ):
        try:
            returncode = int(_IN_PROCESS_CLIS[script](argv) or 0)
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
