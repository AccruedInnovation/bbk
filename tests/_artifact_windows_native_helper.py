"""Small real-Windows process fixtures for the artifact transaction tests.

The helper deliberately owns no package semantics.  It only holds a native
handle/production OS lock or invokes the production finalize callable in a
separate process.  Control records are ordinary attempt-local JSON files so
the parent can synchronize on observed state rather than elapsed sleep.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import artifact_packages
import artifact_platform


def _canonical(value: object) -> bytes:
    return artifact_packages.canonical_json_bytes(value)


def _write(path: Path | None, value: object) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical(value))


def _record(command: str, *, token: str | None = None, **extra: object) -> dict[str, object]:
    result: dict[str, object] = {
        "command": command,
        "pid": os.getpid(),
        "timestamp": artifact_packages.utc_now(),
    }
    if token is not None:
        result["token"] = token
    result.update(extra)
    return result


def _wait_for_release(path: Path | None, token: str | None) -> dict[str, object] | None:
    if path is None:
        return None
    while not path.exists():
        time.sleep(0.01)
    value = json.loads(path.read_text(encoding="utf-8"))
    if token is not None and value.get("token") != token:
        raise RuntimeError("release control token mismatch")
    return value


def _native_handle(path: Path, share_mode: int) -> tuple[int, int]:
    if os.name != "nt":
        raise RuntimeError("native Windows helper requires Windows")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel32.CreateFileW
    create.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    create.restype = ctypes.c_void_p
    close = kernel32.CloseHandle
    close.argtypes = [ctypes.c_void_p]
    close.restype = ctypes.c_int
    access = 0x80000000 | 0x40000000
    handle = create(str(path), access, share_mode, None, 3, 0x02000000, None)
    invalid = ctypes.c_void_p(-1).value
    if handle in (None, invalid):
        code = ctypes.get_last_error()
        raise OSError(code, f"CreateFileW failed ({code})")
    return int(handle), int(ctypes.cast(close, ctypes.c_void_p).value or 0)


def hold_handle(args: argparse.Namespace) -> int:
    target = Path(args.target).resolve(strict=True)
    handle, _ = _native_handle(target, int(args.share_mode))
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    close = kernel32.CloseHandle
    close.argtypes = [ctypes.c_void_p]
    close.restype = ctypes.c_int
    ready = _record(
        "hold-handle",
        token=args.token,
        handle_target=str(target),
        share_mode=int(args.share_mode),
        creation="OPEN_EXISTING",
        flags="FILE_FLAG_BACKUP_SEMANTICS",
    )
    _write(Path(args.ready) if args.ready else None, ready)
    release = _wait_for_release(Path(args.release) if args.release else None, args.token)
    if not close(ctypes.c_void_p(handle)):
        code = ctypes.get_last_error()
        raise OSError(code, f"CloseHandle failed ({code})")
    done = _record("hold-handle", token=args.token, exit=0, released=True, release=release, handle_target=str(target), share_mode=int(args.share_mode))
    _write(Path(args.done) if args.done else None, done)
    return 0


def hold_os_lock(args: argparse.Namespace) -> int:
    if os.name != "nt":
        raise RuntimeError("native Windows helper requires Windows")
    result = artifact_platform.acquire(Path(args.lock), token=args.token)
    if not result.ok:
        error = result.error
        details = {
            "code": error.code if error else None,
            "win32_code": error.win32_code if error else None,
            "errno": error.errno_value if error else None,
            "message": error.message if error else None,
        }
        _write(Path(args.result) if args.result else None, _record("hold-os-lock", token=args.token, status=result.status, details=details))
        return 1
    ready = _record(
        "hold-os-lock",
        token=args.token,
        status="PASS",
        lock=str(Path(args.lock).resolve()),
        details={"path": result.get("path"), "token_bound": result.get("token_bound")},
    )
    _write(Path(args.ready) if args.ready else None, ready)
    release = _wait_for_release(Path(args.release) if args.release else None, args.token)
    result.value.release()
    _write(Path(args.done) if args.done else None, _record("hold-os-lock", token=args.token, status="PASS", released=True, release=release, lock=str(Path(args.lock).resolve())))
    return 0


def _finalize(args: argparse.Namespace, *, crash_phase: str | None = None) -> int:
    draft = Path(args.draft).resolve(strict=True)
    project = Path(args.project_root).resolve(strict=True)
    if crash_phase:
        original = artifact_packages._journal_transition

        def transition(journal: object, journal_path: Path, to_phase: str, effect: str, observation: str) -> None:
            original(journal, journal_path, to_phase, effect, observation)
            if to_phase != crash_phase or not isinstance(journal, dict) or journal.get("mode") != "FINALIZE":
                return
            _write(Path(args.phase_record) if args.phase_record else None, _record("crash-at-phase", token=getattr(journal, "operationToken", None) if not isinstance(journal, dict) else str(journal.get("operationToken")), phase=to_phase, journal=str(journal_path), durable=True))
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            kernel32.TerminateProcess.restype = ctypes.c_int
            kernel32.TerminateProcess(kernel32.GetCurrentProcess(), 197)

        artifact_packages._journal_transition = transition
    result = artifact_packages.finalize_draft(
        draft,
        Path(args.output).resolve() if args.output else None,
        project_root=project,
        write_current_pointer=not args.no_current_pointer,
    )
    _write(Path(args.result) if args.result else None, result)
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="subcommand", required=True)
    hold = sub.add_parser("hold-handle")
    hold.add_argument("target")
    hold.add_argument("--ready")
    hold.add_argument("--release")
    hold.add_argument("--done")
    hold.add_argument("--token")
    hold.add_argument("--share-mode", type=int, default=0)
    lock = sub.add_parser("hold-os-lock")
    lock.add_argument("lock")
    lock.add_argument("--token", required=True)
    lock.add_argument("--ready")
    lock.add_argument("--release")
    lock.add_argument("--done")
    lock.add_argument("--result")
    final = sub.add_parser("finalize")
    final.add_argument("draft")
    final.add_argument("--project-root", required=True)
    final.add_argument("--output")
    final.add_argument("--result")
    final.add_argument("--no-current-pointer", action="store_true")
    crash = sub.add_parser("crash-at-phase")
    crash.add_argument("draft")
    crash.add_argument("--project-root", required=True)
    crash.add_argument("--output")
    crash.add_argument("--phase", required=True)
    crash.add_argument("--phase-record")
    crash.add_argument("--no-current-pointer", action="store_true")
    args = parser.parse_args()
    try:
        if args.subcommand == "hold-handle":
            return hold_handle(args)
        if args.subcommand == "hold-os-lock":
            return hold_os_lock(args)
        if args.subcommand == "finalize":
            return _finalize(args)
        return _finalize(args, crash_phase=args.phase)
    except BaseException as exc:
        if isinstance(exc, artifact_packages.ArtifactPackageError):
            result = dict(exc.result)
            result.setdefault("command", args.subcommand)
            result.setdefault("pid", os.getpid())
            result.setdefault("timestamp", artifact_packages.utc_now())
        else:
            result = _record(args.subcommand, exit=1, error=type(exc).__name__, message=str(exc))
        if getattr(args, "result", None):
            _write(Path(args.result), result)
        print(json.dumps(result, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


