#!/usr/bin/env python3
"""Strict, dependency-free JSON loading for governed BBK artifacts.

The ordinary :mod:`json` loader is intentionally permissive in several places
that matter to identity-bearing records: it accepts duplicate object keys,
non-finite numbers, and (through some call patterns) byte-order marks.  This
module implements the BBK strict-load boundary once and returns stable,
structured diagnostics that callers can preserve through CLI and package
admission workflows.

This loader establishes only syntactic and encoding validity.  It does not
assert schema conformance, semantic acceptance, authorization, or release.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Sequence

DEFAULT_MAX_DEPTH: Final[int] = 128
_DIAGNOSTIC_SCHEMA: Final[str] = "bbk.strict-json-diagnostic.v1"
_BOMS: Final[tuple[tuple[bytes, str], ...]] = (
    (b"\xef\xbb\xbf", "UTF-8"),
    (b"\xff\xfe\x00\x00", "UTF-32-LE"),
    (b"\x00\x00\xfe\xff", "UTF-32-BE"),
    (b"\xff\xfe", "UTF-16-LE"),
    (b"\xfe\xff", "UTF-16-BE"),
)
_NUMBER_RE: Final[re.Pattern[str]] = re.compile(
    r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?"
)


def _pointer(parts: Sequence[str | int]) -> str:
    if not parts:
        return ""
    encoded: list[str] = []
    for part in parts:
        text = str(part).replace("~", "~0").replace("/", "~1")
        encoded.append(text)
    return "/" + "/".join(encoded)


def _line_column(text: str, offset: int) -> tuple[int, int]:
    bounded = max(0, min(offset, len(text)))
    line = text.count("\n", 0, bounded) + 1
    previous = text.rfind("\n", 0, bounded)
    column = bounded + 1 if previous < 0 else bounded - previous
    return line, column


@dataclass(frozen=True)
class StrictJsonDiagnostic:
    """Stable rejection information for one strict JSON load failure."""

    code: str
    message: str
    source: str
    pointer: str = ""
    offset: int | None = None
    line: int | None = None
    column: int | None = None
    duplicate_key: str | None = None
    classification: str = "MECHANICAL"
    remediation: str = "Repair the exact JSON defect and rerun the same operation."

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema": _DIAGNOSTIC_SCHEMA,
            "status": "REJECTED",
            "code": self.code,
            "classification": self.classification,
            "source": self.source,
            "pointer": self.pointer,
            "message": self.message,
            "remediation": self.remediation,
            "smallest_next_action": self.remediation,
            "claims_not_established": [
                "JSON schema conformance",
                "semantic acceptance",
                "authorization",
                "release readiness",
            ],
        }
        if self.offset is not None:
            result["offset"] = self.offset
        if self.line is not None:
            result["line"] = self.line
        if self.column is not None:
            result["column"] = self.column
        if self.duplicate_key is not None:
            result["duplicate_key"] = self.duplicate_key
        return result


class StrictJsonError(ValueError):
    """Raised when governed JSON fails the strict-load boundary."""

    def __init__(self, diagnostic: StrictJsonDiagnostic):
        self.diagnostic = diagnostic
        super().__init__(diagnostic.message)

    def as_dict(self) -> dict[str, Any]:
        return self.diagnostic.as_dict()


class _Parser:
    def __init__(self, text: str, *, source: str, max_depth: int) -> None:
        self.text = text
        self.source = source
        self.max_depth = max_depth
        self.length = len(text)
        self.index = 0

    def error(
        self,
        code: str,
        message: str,
        *,
        path: Sequence[str | int] = (),
        offset: int | None = None,
        duplicate_key: str | None = None,
        remediation: str | None = None,
    ) -> StrictJsonError:
        at = self.index if offset is None else offset
        line, column = _line_column(self.text, at)
        return StrictJsonError(
            StrictJsonDiagnostic(
                code=code,
                message=message,
                source=self.source,
                pointer=_pointer(path),
                offset=at,
                line=line,
                column=column,
                duplicate_key=duplicate_key,
                remediation=remediation
                or "Repair the exact JSON defect and rerun the same operation.",
            )
        )

    def skip_ws(self) -> None:
        while self.index < self.length and self.text[self.index] in " \t\r\n":
            self.index += 1

    def parse(self) -> Any:
        self.skip_ws()
        if self.index >= self.length:
            raise self.error(
                "JSON_EMPTY_INPUT",
                "JSON input is empty or contains only whitespace.",
                remediation="Provide one complete JSON value.",
            )
        value = self.parse_value(path=(), depth=0)
        self.skip_ws()
        if self.index != self.length:
            raise self.error(
                "JSON_TRAILING_DATA",
                "Trailing data follows the complete JSON value.",
                offset=self.index,
                remediation="Remove all bytes after the first complete JSON value.",
            )
        return value

    def parse_value(self, *, path: Sequence[str | int], depth: int) -> Any:
        self.skip_ws()
        if self.index >= self.length:
            raise self.error("JSON_UNEXPECTED_EOF", "Unexpected end of JSON input.", path=path)
        ch = self.text[self.index]
        if ch == "{":
            return self.parse_object(path=path, depth=depth + 1)
        if ch == "[":
            return self.parse_array(path=path, depth=depth + 1)
        if ch == '"':
            return self.parse_string(path=path)
        if self.text.startswith("true", self.index):
            self.index += 4
            return True
        if self.text.startswith("false", self.index):
            self.index += 5
            return False
        if self.text.startswith("null", self.index):
            self.index += 4
            return None
        for token in ("NaN", "Infinity", "-Infinity"):
            if self.text.startswith(token, self.index):
                raise self.error(
                    "JSON_NONFINITE_NUMBER",
                    f"Non-finite numeric token {token!r} is forbidden.",
                    path=path,
                    remediation="Replace the non-finite token with a finite JSON number or an explicit string/null representation.",
                )
        if ch == "-" or ch.isdigit():
            return self.parse_number(path=path)
        raise self.error(
            "JSON_SYNTAX_ERROR",
            f"Unexpected token {ch!r} while parsing JSON.",
            path=path,
        )

    def check_depth(self, depth: int, path: Sequence[str | int]) -> None:
        if depth > self.max_depth:
            raise self.error(
                "JSON_MAX_DEPTH_EXCEEDED",
                f"JSON nesting depth exceeds configured maximum {self.max_depth}.",
                path=path,
                remediation=f"Reduce nesting to at most {self.max_depth} containers or raise the explicitly governed depth policy.",
            )

    def parse_object(self, *, path: Sequence[str | int], depth: int) -> dict[str, Any]:
        self.check_depth(depth, path)
        self.index += 1
        result: dict[str, Any] = {}
        seen: set[str] = set()
        self.skip_ws()
        if self.index < self.length and self.text[self.index] == "}":
            self.index += 1
            return result
        while True:
            self.skip_ws()
            if self.index >= self.length:
                raise self.error("JSON_UNEXPECTED_EOF", "Unterminated JSON object.", path=path)
            if self.text[self.index] != '"':
                raise self.error(
                    "JSON_OBJECT_KEY_REQUIRED",
                    "JSON object members require quoted string keys.",
                    path=path,
                )
            key_offset = self.index
            key = self.parse_string(path=path)
            if key in seen:
                raise self.error(
                    "JSON_DUPLICATE_KEY",
                    f"Duplicate object key {key!r} is forbidden.",
                    path=path,
                    offset=key_offset,
                    duplicate_key=key,
                    remediation=f"Keep exactly one {key!r} member in the object at pointer {_pointer(path) or '/'}.",
                )
            seen.add(key)
            self.skip_ws()
            if self.index >= self.length or self.text[self.index] != ":":
                raise self.error(
                    "JSON_COLON_REQUIRED",
                    f"Object key {key!r} is not followed by ':'.",
                    path=(*path, key),
                )
            self.index += 1
            result[key] = self.parse_value(path=(*path, key), depth=depth)
            self.skip_ws()
            if self.index >= self.length:
                raise self.error("JSON_UNEXPECTED_EOF", "Unterminated JSON object.", path=path)
            delimiter = self.text[self.index]
            if delimiter == "}":
                self.index += 1
                return result
            if delimiter != ",":
                raise self.error(
                    "JSON_OBJECT_DELIMITER_REQUIRED",
                    "Expected ',' or '}' after object member.",
                    path=path,
                )
            self.index += 1

    def parse_array(self, *, path: Sequence[str | int], depth: int) -> list[Any]:
        self.check_depth(depth, path)
        self.index += 1
        result: list[Any] = []
        self.skip_ws()
        if self.index < self.length and self.text[self.index] == "]":
            self.index += 1
            return result
        while True:
            item_path = (*path, len(result))
            result.append(self.parse_value(path=item_path, depth=depth))
            self.skip_ws()
            if self.index >= self.length:
                raise self.error("JSON_UNEXPECTED_EOF", "Unterminated JSON array.", path=path)
            delimiter = self.text[self.index]
            if delimiter == "]":
                self.index += 1
                return result
            if delimiter != ",":
                raise self.error(
                    "JSON_ARRAY_DELIMITER_REQUIRED",
                    "Expected ',' or ']' after array item.",
                    path=path,
                )
            self.index += 1

    def parse_string(self, *, path: Sequence[str | int]) -> str:
        quote_offset = self.index
        try:
            value, end = json.decoder.scanstring(self.text, self.index + 1, True)
        except json.JSONDecodeError as exc:
            message = exc.msg
            lowered = message.lower()
            code = (
                "JSON_MALFORMED_ESCAPE"
                if "escape" in lowered or "unicode" in lowered
                else "JSON_UNTERMINATED_STRING"
                if "unterminated" in lowered
                else "JSON_SYNTAX_ERROR"
            )
            raise self.error(code, message, path=path, offset=exc.pos) from exc
        except (UnicodeDecodeError, ValueError) as exc:
            raise self.error(
                "JSON_MALFORMED_ESCAPE",
                f"Invalid JSON string escape: {exc}",
                path=path,
                offset=quote_offset,
            ) from exc
        self.index = end
        return value

    def parse_number(self, *, path: Sequence[str | int]) -> int | float:
        match = _NUMBER_RE.match(self.text, self.index)
        if match is None:
            raise self.error("JSON_INVALID_NUMBER", "Invalid JSON number.", path=path)
        token = match.group(0)
        end = match.end()
        # A JSON number cannot be immediately followed by an identifier or a
        # second decimal/exponent fragment.  Reporting it here is more useful
        # than reducing the defect to generic trailing data.
        if end < self.length and self.text[end] not in " \t\r\n,]}":
            raise self.error(
                "JSON_INVALID_NUMBER",
                f"Invalid JSON number token beginning {token!r}.",
                path=path,
                offset=end,
            )
        self.index = end
        try:
            return float(token) if any(marker in token for marker in ".eE") else int(token)
        except (OverflowError, ValueError) as exc:
            raise self.error(
                "JSON_INVALID_NUMBER",
                f"JSON number cannot be represented: {token!r}.",
                path=path,
            ) from exc


def loads_text(
    text: str,
    *,
    source: str = "<string>",
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> Any:
    """Load one strict JSON value from text.

    ``source`` is an identity label used only in diagnostics.  The caller is
    responsible for binding that label to any higher-level subject identity.
    """
    if not isinstance(text, str):
        raise TypeError("text must be str")
    if max_depth < 1:
        raise ValueError("max_depth must be at least 1")
    if text.startswith("\ufeff"):
        raise StrictJsonError(
            StrictJsonDiagnostic(
                code="JSON_FORBIDDEN_BOM",
                message="A Unicode byte-order mark is forbidden for governed JSON.",
                source=source,
                offset=0,
                line=1,
                column=1,
                remediation="Remove the byte-order mark and encode the document as UTF-8 without BOM.",
            )
        )
    return _Parser(text, source=source, max_depth=max_depth).parse()


def loads_bytes(
    data: bytes,
    *,
    source: str = "<bytes>",
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> Any:
    """Decode UTF-8-without-BOM bytes and load one strict JSON value."""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError("data must be bytes-like")
    raw = bytes(data)
    for marker, encoding in _BOMS:
        if raw.startswith(marker):
            raise StrictJsonError(
                StrictJsonDiagnostic(
                    code="JSON_FORBIDDEN_BOM",
                    message=f"A {encoding} byte-order mark is forbidden for governed JSON.",
                    source=source,
                    offset=0,
                    line=1,
                    column=1,
                    remediation="Encode the document as UTF-8 without BOM.",
                )
            )
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise StrictJsonError(
            StrictJsonDiagnostic(
                code="JSON_INVALID_UTF8",
                message=f"JSON bytes are not valid UTF-8: {exc.reason}.",
                source=source,
                offset=exc.start,
                remediation="Re-encode the exact document as valid UTF-8 without BOM.",
            )
        ) from exc
    return loads_text(text, source=source, max_depth=max_depth)


def load_path(path: Path | str, *, max_depth: int = DEFAULT_MAX_DEPTH) -> Any:
    """Read and strictly load one JSON file without following a file symlink."""
    candidate = Path(path)
    source = str(candidate)
    if candidate.is_symlink():
        raise StrictJsonError(
            StrictJsonDiagnostic(
                code="JSON_SYMLINK_FORBIDDEN",
                message="Governed JSON input must be a regular file, not a symbolic link.",
                source=source,
                remediation="Provide the physical regular file through an explicitly governed path.",
            )
        )
    try:
        data = candidate.read_bytes()
    except FileNotFoundError as exc:
        raise StrictJsonError(
            StrictJsonDiagnostic(
                code="JSON_FILE_NOT_FOUND",
                message=f"JSON file does not exist: {candidate}",
                source=source,
                remediation="Provide the exact existing JSON file and rerun the operation.",
            )
        ) from exc
    except OSError as exc:
        raise StrictJsonError(
            StrictJsonDiagnostic(
                code="JSON_FILE_READ_ERROR",
                message=f"Unable to read JSON file {candidate}: {exc}",
                source=source,
                remediation="Restore read access to the exact file and rerun the operation.",
            )
        ) from exc
    return loads_bytes(data, source=source, max_depth=max_depth)


def try_load_path(path: Path | str, *, max_depth: int = DEFAULT_MAX_DEPTH) -> dict[str, Any]:
    """Return a versioned result instead of raising for one path load."""
    try:
        value = load_path(path, max_depth=max_depth)
    except StrictJsonError as exc:
        return exc.as_dict()
    return {
        "schema": "bbk.strict-json-load-result.v1",
        "status": "PASS",
        "source": str(Path(path)),
        "value": value,
        "claims_not_established": [
            "JSON schema conformance",
            "semantic acceptance",
            "authorization",
            "release readiness",
        ],
    }


__all__ = [
    "DEFAULT_MAX_DEPTH",
    "StrictJsonDiagnostic",
    "StrictJsonError",
    "load_path",
    "loads_bytes",
    "loads_text",
    "try_load_path",
]
