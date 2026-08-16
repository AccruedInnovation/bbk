"""Small, fault-injectable filesystem primitives used by artifact publication.

This module deliberately contains platform effects only.  It does not own
package state, transaction phases, retry scheduling, or recovery decisions.
"""
from __future__ import annotations

import ctypes
import errno
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, BinaryIO, Mapping


class Outcome(str, Enum):
    PASS = "PASS"
    CONFLICT = "CONFLICT"
    SHARING_RETRYABLE = "SHARING_RETRYABLE"
    UNSUPPORTED = "UNSUPPORTED"
    AMBIGUOUS = "AMBIGUOUS"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ErrorClassification:
    """A bounded classification; callers decide whether/how to retry."""

    outcome: Outcome
    code: str
    message: str
    errno_value: int | None = None
    win32_code: int | None = None

    @property
    def status(self) -> str:
        return self.outcome.value

    @property
    def classification(self) -> str:
        return self.outcome.value

    @property
    def retryable(self) -> bool:
        return self.outcome is Outcome.SHARING_RETRYABLE

    def __str__(self) -> str:
        return self.outcome.value


@dataclass
class FsResult:
    """Typed adapter result with a mapping-friendly inspection surface."""

    status: str
    value: Any = None
    error: ErrorClassification | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == Outcome.PASS.value

    @property
    def outcome(self) -> str:
        return self.status

    def __bool__(self) -> bool:
        return self.ok

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def to_dict(self) -> dict[str, Any]:
        result = {"status": self.status, "value": self.value, **self.details}
        if self.error is not None:
            result["error"] = self.error
            result["classification"] = self.error.classification
            result["code"] = self.error.code
        return result


def _pass(value: Any = None, **details: Any) -> FsResult:
    return FsResult(Outcome.PASS.value, value=value, details=details)


def _failure(exc: BaseException, *, operation: str = "filesystem operation") -> FsResult:
    error = classify_error(exc, operation=operation)
    return FsResult(error.status, error=error)


def _path(value: str | os.PathLike[str] | Path) -> Path:
    return Path(os.fspath(value))


def _winerror(exc: BaseException) -> int | None:
    value = getattr(exc, "winerror", None)
    if isinstance(value, int):
        return value
    if isinstance(exc, int):
        return exc
    return None


def classify_error(error: BaseException | int | Mapping[str, Any], *, operation: str = "filesystem operation") -> ErrorClassification:
    """Classify an OS failure without deciding policy or scheduling retries."""
    if isinstance(error, Mapping):
        win_code = error.get("win32_code", error.get("winerror"))
        errno_value = error.get("errno", error.get("errno_value"))
        message = str(error.get("message", operation))
        code = str(error.get("code", "OS_ERROR"))
    else:
        win_code = _winerror(error)
        errno_value = getattr(error, "errno", None)
        message = str(error)
        code = type(error).__name__.upper()
    if win_code in (32, 33):
        return ErrorClassification(Outcome.SHARING_RETRYABLE, f"WIN32_{win_code}", message, errno_value, win_code)
    if isinstance(error, FileExistsError) or errno_value in (errno.EEXIST, errno.ENOTEMPTY):
        return ErrorClassification(Outcome.CONFLICT, "ALREADY_EXISTS", message, errno_value, win_code)
    if isinstance(error, NotImplementedError) or errno_value in (errno.ENOSYS, errno.EOPNOTSUPP):
        return ErrorClassification(Outcome.UNSUPPORTED, "UNSUPPORTED", message, errno_value, win_code)
    if isinstance(error, (RuntimeError, ValueError, TypeError)):
        return ErrorClassification(Outcome.AMBIGUOUS, code, message, errno_value, win_code)
    return ErrorClassification(Outcome.FAILED, code, message, errno_value, win_code)


def same_volume(first: str | os.PathLike[str] | Path, second: str | os.PathLike[str] | Path) -> bool:
    """Return whether two paths resolve to the same local filesystem device."""
    try:
        a, b = _path(first), _path(second)
        if not a.exists() or not b.exists():
            return False
        return os.stat(a).st_dev == os.stat(b).st_dev
    except OSError:
        return False


def _flush_handle(handle: int) -> None:
    os.fsync(handle)


def flush_file(file_or_path: int | BinaryIO | str | os.PathLike[str] | Path) -> FsResult:
    """Flush file contents and metadata visible through the supplied handle."""
    close = False
    try:
        if isinstance(file_or_path, int):
            fd = file_or_path
        elif hasattr(file_or_path, "fileno"):
            fd = file_or_path.fileno()
        else:
            fd = os.open(_path(file_or_path), os.O_RDONLY)
            close = True
        _flush_handle(fd)
        return _pass()
    except (OSError, ValueError) as exc:
        return _failure(exc, operation="flush file")
    finally:
        if close:
            try:
                os.close(fd)
            except OSError:
                pass


def _flush_windows_directory(directory: Path) -> None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel32.CreateFileW
    create.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    create.restype = ctypes.c_void_p
    handle = create(str(directory), 0xC0000000, 0x00000007, None, 3, 0x02000000, None)
    invalid = ctypes.c_void_p(-1).value
    if handle in (None, invalid):
        code = ctypes.get_last_error()
        raise OSError(code, f"CreateFileW directory failed ({code})")
    try:
        if not kernel32.FlushFileBuffers(handle):
            code = ctypes.get_last_error()
            raise OSError(code, f"FlushFileBuffers failed ({code})")
    finally:
        kernel32.CloseHandle(handle)


def flush_directory(directory: str | os.PathLike[str] | Path) -> FsResult:
    """Flush a directory entry after a rename or durable file creation."""
    target = _path(directory)
    try:
        if os.name == "nt":
            _flush_windows_directory(target)
        else:
            fd = os.open(target, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        return _pass()
    except (OSError, NotImplementedError) as exc:
        return _failure(exc, operation="flush directory")


def durable_write_temp(
    destination: str | os.PathLike[str] | Path,
    data: bytes | bytearray | memoryview,
    *,
    suffix: str = ".tmp",
) -> FsResult:
    """Write and flush a temporary file beside ``destination``."""
    target = _path(destination)
    parent = target.parent
    temporary: Path | None = None
    try:
        if not parent.is_dir():
            raise FileNotFoundError(errno.ENOENT, "temporary parent does not exist", str(parent))
        fd, name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=suffix, dir=parent)
        temporary = Path(name)
        with os.fdopen(fd, "wb") as stream:
            stream.write(bytes(data))
            stream.flush()
            _flush_handle(stream.fileno())
        directory_result = flush_directory(parent)
        if not directory_result.ok:
            raise OSError(errno.EIO, "temporary directory flush failed")
        return _pass(temporary, path=str(temporary), bytes=temporary.stat().st_size)
    except (OSError, TypeError, ValueError) as exc:
        if temporary is not None:
            try:
                temporary.unlink()
            except OSError:
                pass
        return _failure(exc, operation="durable temporary write")


def atomic_replace(source: str | os.PathLike[str] | Path, destination: str | os.PathLike[str] | Path) -> FsResult:
    """Replace a mutable projection atomically, then flush its parent."""
    src, dst = _path(source), _path(destination)
    try:
        if src.parent != dst.parent and not same_volume(src, dst.parent):
            raise OSError(errno.EXDEV, "source and destination are on different volumes")
        os.replace(src, dst)
        result = flush_directory(dst.parent)
        if not result.ok:
            return result
        return _pass(dst, path=str(dst))
    except (OSError, ValueError) as exc:
        return _failure(exc, operation="atomic replace")


def create_file_noreplace(path: str | os.PathLike[str] | Path, data: bytes | bytearray | memoryview = b"") -> FsResult:
    """Create one file without replacing an existing path."""
    target = _path(path)
    try:
        with target.open("xb") as stream:
            stream.write(bytes(data))
            stream.flush()
            _flush_handle(stream.fileno())
        result = flush_directory(target.parent)
        if not result.ok:
            return result
        return _pass(target, path=str(target), bytes=target.stat().st_size)
    except (OSError, TypeError, ValueError) as exc:
        return _failure(exc, operation="no-replace file create")


def publish_dir_noreplace(source: str | os.PathLike[str] | Path, destination: str | os.PathLike[str] | Path) -> FsResult:
    """Move a same-volume directory into place without replacing it."""
    src, dst = _path(source), _path(destination)
    try:
        if not src.is_dir():
            raise NotADirectoryError(errno.ENOTDIR, "publication source is not a directory", str(src))
        if not same_volume(src, dst.parent):
            raise OSError(errno.EXDEV, "source and destination are on different volumes")
        if dst.exists() or dst.is_symlink():
            return FsResult(Outcome.CONFLICT.value, error=ErrorClassification(Outcome.CONFLICT, "ALREADY_EXISTS", str(dst), errno.EEXIST))
        os.rename(src, dst)
        result = flush_directory(dst.parent)
        if not result.ok:
            return result
        return _pass(dst, path=str(dst))
    except (OSError, ValueError) as exc:
        return _failure(exc, operation="no-replace directory publish")


class LockHandle:
    """An OS-held local lock; release is explicit and context-manager safe."""

    def __init__(self, stream: BinaryIO, path: Path):
        self.stream = stream
        self.path = path
        self._released = False

    def release(self) -> None:
        if self._released:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self.stream.seek(0)
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
        finally:
            self.stream.close()
            self._released = True

    def __enter__(self) -> "LockHandle":
        return self

    def __exit__(self, *_: Any) -> None:
        self.release()


def acquire(lock_key: str | os.PathLike[str] | Path, token: str | None = None) -> FsResult:
    """Acquire an OS-held lock for this process; no age/PID takeover occurs."""
    path = _path(lock_key)
    if path.exists() and path.is_dir():
        path = path / ".artifact.lock"
    try:
        if not path.parent.is_dir():
            raise FileNotFoundError(errno.ENOENT, "lock parent does not exist", str(path.parent))
        stream = path.open("a+b")
        if os.name == "nt":
            import msvcrt

            stream.seek(0)
            if stream.tell() == 0 and path.stat().st_size == 0:
                stream.write(b"\0")
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _pass(LockHandle(stream, path), path=str(path), token_bound=token is not None)
    except (OSError, ValueError) as exc:
        try:
            stream.close()  # type: ignore[has-type]
        except (NameError, UnboundLocalError, OSError):
            pass
        if os.name == "nt" and isinstance(exc, PermissionError) and path.exists():
            error = ErrorClassification(Outcome.SHARING_RETRYABLE, "WIN32_33", str(exc), getattr(exc, "errno", None), 33)
            return FsResult(error.status, error=error)
        return _failure(exc, operation="OS lock acquisition")


def readback(path: str | os.PathLike[str] | Path) -> FsResult:
    """Read exact bytes for coordinator-owned verification."""
    target = _path(path)
    try:
        data = target.read_bytes()
        return _pass(data, path=str(target), bytes=len(data))
    except (OSError, ValueError) as exc:
        return _failure(exc, operation="readback")


def cleanup_owned_path(path: str | os.PathLike[str] | Path) -> FsResult:
    """Remove exactly one operation-owned temporary path; never follows links."""
    target = _path(path)
    try:
        if target.is_symlink() or target.is_file():
            target.unlink()
        elif target.is_dir():
            shutil.rmtree(target)
        else:
            return _pass(None, path=str(target), absent=True)
        return _pass(None, path=str(target), removed=True)
    except (OSError, ValueError) as exc:
        return _failure(exc, operation="owned-path cleanup")


def doctor(root: str | os.PathLike[str] | Path, target_parent: str | os.PathLike[str] | Path) -> FsResult:
    """Check the local filesystem capabilities needed by the adapter."""
    base, parent = _path(root), _path(target_parent)
    try:
        if not base.is_dir() or not parent.is_dir():
            raise FileNotFoundError(errno.ENOENT, "doctor roots must be existing directories")
        for value in (base, parent):
            if value.is_symlink():
                raise OSError(errno.ELOOP, "symlink/reparse root is not permitted")
        if not same_volume(base, parent):
            raise OSError(errno.EXDEV, "roots are on different volumes")
        flush = flush_directory(parent)
        if not flush.ok:
            return flush
        return _pass({"platform": os.name, "same_volume": True, "directory_flush": True}, root=str(base), target_parent=str(parent))
    except (OSError, ValueError) as exc:
        return _failure(exc, operation="filesystem doctor")


# Explicit aliases make the I-FS vocabulary discoverable to callers.
durable_write = durable_write_temp
no_replace_file = create_file_noreplace
no_replace_directory = publish_dir_noreplace
read_back = readback
cleanup = cleanup_owned_path


__all__ = [
    "Outcome",
    "ErrorClassification",
    "FsResult",
    "LockHandle",
    "doctor",
    "acquire",
    "durable_write_temp",
    "atomic_replace",
    "create_file_noreplace",
    "publish_dir_noreplace",
    "flush_file",
    "flush_directory",
    "same_volume",
    "readback",
    "classify_error",
    "cleanup_owned_path",
]


