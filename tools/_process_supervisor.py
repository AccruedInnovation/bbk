"""Private bounded process supervision for the test and verification runners.

The public runners only need one narrow effect boundary: a child receives a
file-backed merged output handle, its descendants stay in the same owned
containment scope, and timeout/normal completion return a bounded result.
Windows launches are suspended and assigned to a kill-on-close Job before the
first thread is resumed.  POSIX uses an owned process group/session.  Unknown
cleanup is deliberately represented as non-quiescent rather than guessed.
"""
from __future__ import annotations

import ctypes
import os
import signal
import subprocess
import tempfile
import time
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


DEFAULT_TIMEOUT = 420.0
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000
STILL_ACTIVE = 259


@dataclass(frozen=True)
class BoundedResult:
    """Lossless producer observation from one owned process tree."""

    returncode: int
    output: str
    timed_out: bool
    quiescent: bool
    cleanup: str
    pids: tuple[int, ...]
    elapsed_seconds: float
    capture_path: str


class SupervisionError(RuntimeError):
    """The process could not be safely admitted or its state is unknown."""


if os.name == "nt":
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class _StartupInfo(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("lpReserved", wintypes.LPWSTR),
            ("lpDesktop", wintypes.LPWSTR),
            ("lpTitle", wintypes.LPWSTR),
            ("dwX", wintypes.DWORD),
            ("dwY", wintypes.DWORD),
            ("dwXSize", wintypes.DWORD),
            ("dwYSize", wintypes.DWORD),
            ("dwXCountChars", wintypes.DWORD),
            ("dwYCountChars", wintypes.DWORD),
            ("dwFillAttribute", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("wShowWindow", wintypes.WORD),
            ("cbReserved2", wintypes.WORD),
            ("lpReserved2", ctypes.POINTER(ctypes.c_ubyte)),
            ("hStdInput", wintypes.HANDLE),
            ("hStdOutput", wintypes.HANDLE),
            ("hStdError", wintypes.HANDLE),
        ]

    class _ProcessInformation(ctypes.Structure):
        _fields_ = [
            ("hProcess", wintypes.HANDLE),
            ("hThread", wintypes.HANDLE),
            ("dwProcessId", wintypes.DWORD),
            ("dwThreadId", wintypes.DWORD),
        ]

    class _BasicLimit(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
        )]

    class _ExtendedLimit(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _BasicLimit),
            ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, wintypes.INT, wintypes.LPVOID, wintypes.DWORD]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.QueryInformationJobObject.argtypes = [wintypes.HANDLE, wintypes.INT, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    kernel32.QueryInformationJobObject.restype = wintypes.BOOL
    kernel32.CreateProcessW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.LPVOID, wintypes.LPVOID, wintypes.BOOL, wintypes.DWORD, wintypes.LPVOID, wintypes.LPCWSTR, ctypes.POINTER(_StartupInfo), ctypes.POINTER(_ProcessInformation)]
    kernel32.CreateProcessW.restype = wintypes.BOOL
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.ResumeThread.argtypes = [wintypes.HANDLE]
    kernel32.ResumeThread.restype = wintypes.DWORD
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateProcess.restype = wintypes.BOOL
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
    kernel32.IsProcessInJob.restype = wintypes.BOOL

    CREATE_SUSPENDED = 0x00000004
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    CREATE_BREAKAWAY_FROM_JOB = 0x01000000
    CREATE_UNICODE_ENVIRONMENT = 0x00000400
    STARTF_USESTDHANDLES = 0x00000100
    JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    JOB_OBJECT_BASIC_PROCESS_ID_LIST = 3
    WAIT_OBJECT_0 = 0
    WAIT_TIMEOUT = 258


def _read_capture(path: Path) -> str:
    return path.read_bytes().decode("utf-8", errors="backslashreplace")


def _environment_block(environment: Mapping[str, str] | None) -> ctypes.Array[ctypes.c_wchar] | None:
    if environment is None:
        return None
    values = [f"{key}={value}" for key, value in sorted(environment.items(), key=lambda item: item[0].upper())]
    return ctypes.create_unicode_buffer("\0".join(values) + "\0\0")


def _win_error(label: str) -> SupervisionError:
    return SupervisionError(f"{label}: WinError {ctypes.get_last_error()}")


def _windows_pids(job: int) -> tuple[int, ...]:
    size = 4096
    while size <= 1024 * 1024:
        buffer = ctypes.create_string_buffer(size)
        returned = wintypes.DWORD()
        if kernel32.QueryInformationJobObject(job, JOB_OBJECT_BASIC_PROCESS_ID_LIST, buffer, size, ctypes.byref(returned)):
            count = int.from_bytes(buffer.raw[4:8], "little")
            width = ctypes.sizeof(ctypes.c_size_t)
            return tuple(
                int.from_bytes(buffer.raw[8 + offset:8 + offset + width], "little")
                for offset in range(0, count * width, width)
            )
        if ctypes.get_last_error() != 122:
            return ()
        size *= 2
    return ()


def _windows_process_dead(pid: int) -> bool | None:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid)
    if not handle:
        error = ctypes.get_last_error()
        return True if error == 87 else None
    try:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return None
        return code.value != STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def _run_windows(
    command: Sequence[str], *, capture: Path, timeout: float, cwd: Path | None,
    environment: Mapping[str, str] | None,
) -> BoundedResult:
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise _win_error("CreateJobObjectW")
    process = thread = None
    output_fd = input_fd = None
    started = time.monotonic()
    timed_out = False
    resumed = False
    pids: tuple[int, ...] = ()
    try:
        info = _ExtendedLimit()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel32.SetInformationJobObject(job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, ctypes.byref(info), ctypes.sizeof(info)):
            raise _win_error("SetInformationJobObject")
        capture.parent.mkdir(parents=True, exist_ok=True)
        output_fd = os.open(str(capture), os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
        input_fd = os.open(os.devnull, os.O_RDONLY)
        os.set_handle_inheritable(msvcrt.get_osfhandle(output_fd), True)
        os.set_handle_inheritable(msvcrt.get_osfhandle(input_fd), True)
        startup = _StartupInfo()
        startup.cb = ctypes.sizeof(startup)
        startup.dwFlags = STARTF_USESTDHANDLES
        startup.hStdInput = msvcrt.get_osfhandle(input_fd)
        startup.hStdOutput = msvcrt.get_osfhandle(output_fd)
        startup.hStdError = msvcrt.get_osfhandle(output_fd)
        pi = _ProcessInformation()
        command_line = ctypes.create_unicode_buffer(subprocess.list2cmdline(list(command)))
        host_job = wintypes.BOOL()
        if not kernel32.IsProcessInJob(kernel32.GetCurrentProcess(), None, ctypes.byref(host_job)):
            raise _win_error("IsProcessInJob")
        flags = CREATE_SUSPENDED | CREATE_NEW_PROCESS_GROUP | CREATE_UNICODE_ENVIRONMENT
        if host_job.value:
            flags |= CREATE_BREAKAWAY_FROM_JOB
        env_block = _environment_block(environment)
        if not kernel32.CreateProcessW(None, command_line, None, None, True, flags, env_block, str(cwd) if cwd else None, ctypes.byref(startup), ctypes.byref(pi)):
            raise _win_error("CreateProcessW")
        process, thread = int(pi.hProcess), int(pi.hThread)
        os.close(output_fd); output_fd = None
        os.close(input_fd); input_fd = None
        before = wintypes.BOOL()
        if not kernel32.IsProcessInJob(process, None, ctypes.byref(before)):
            raise _win_error("IsProcessInJob(root)")
        if before.value:
            raise SupervisionError("root process remained in ambient Job before supervisor assignment")
        if not kernel32.AssignProcessToJobObject(job, process):
            raise _win_error("AssignProcessToJobObject")
        after = wintypes.BOOL()
        if not kernel32.IsProcessInJob(process, None, ctypes.byref(after)) or not after.value:
            raise SupervisionError("root process was not observed in supervisor Job")
        if kernel32.ResumeThread(thread) == 0xFFFFFFFF:
            raise _win_error("ResumeThread")
        resumed = True
        wait_ms = int(max(timeout, 0.0) * 1000) if timeout > 0 else 0xFFFFFFFF
        waited = kernel32.WaitForSingleObject(process, wait_ms)
        timed_out = waited == WAIT_TIMEOUT
        if waited not in (WAIT_OBJECT_0, WAIT_TIMEOUT):
            raise _win_error("WaitForSingleObject")
        pids = _windows_pids(job) or (int(pi.dwProcessId),)
    except BaseException:
        if process and not resumed:
            kernel32.TerminateProcess(process, 2)
        raise
    finally:
        if job:
            kernel32.CloseHandle(job)
            job = None
        if output_fd is not None:
            os.close(output_fd)
        if input_fd is not None:
            os.close(input_fd)
    # The Job close is the only tree-wide cleanup effect.  Wait on the known
    # root handle, then independently inspect every PID captured from the Job.
    quiescent = bool(process) and kernel32.WaitForSingleObject(process, 5000) == WAIT_OBJECT_0
    states = tuple(_windows_process_dead(pid) for pid in pids)
    quiescent = quiescent and all(value is True for value in states)
    code = wintypes.DWORD()
    returncode = int(code.value) if process and kernel32.GetExitCodeProcess(process, ctypes.byref(code)) else 2
    if timed_out:
        returncode = 2
    if process:
        kernel32.CloseHandle(process)
    if thread:
        kernel32.CloseHandle(thread)
    return BoundedResult(returncode, _read_capture(capture), timed_out, quiescent, "CLEAN" if quiescent else "CLEANUP_UNKNOWN", pids, time.monotonic() - started, str(capture))


def _run_posix(
    command: Sequence[str], *, capture: Path, timeout: float, cwd: Path | None,
    environment: Mapping[str, str] | None,
) -> BoundedResult:
    capture.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with capture.open("wb") as output:
        process = subprocess.Popen(list(command), cwd=cwd, env=environment, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            process.wait(timeout=timeout if timeout > 0 else None)
            timed_out = False
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
    return BoundedResult(process.returncode if not timed_out else 2, _read_capture(capture), timed_out, process.poll() is not None, "CLEAN" if process.poll() is not None else "CLEANUP_UNKNOWN", (process.pid,), time.monotonic() - started, str(capture))


def run_bounded(
    command: Sequence[str], *, capture_path: Path | None = None, timeout: float = DEFAULT_TIMEOUT,
    cwd: Path | None = None, environment: Mapping[str, str] | None = None,
) -> BoundedResult:
    """Run one owned command without a stdout pipe or unbound cleanup target."""
    temporary = capture_path is None
    capture = capture_path or Path(tempfile.mkstemp(prefix="bbk-supervisor-", suffix=".log")[1])
    try:
        if os.name == "nt":
            return _run_windows(command, capture=capture, timeout=timeout, cwd=cwd, environment=environment)
        return _run_posix(command, capture=capture, timeout=timeout, cwd=cwd, environment=environment)
    finally:
        if temporary:
            capture.unlink(missing_ok=True)


supervise = run_bounded
execute = run_bounded


if os.name == "nt":
    import msvcrt
