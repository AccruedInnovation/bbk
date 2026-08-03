#!/usr/bin/env python3
"""Deterministic BBK artifact package primitives.

This module is the canonical implementation for strict package preflight,
BBK-JSON-1 canonicalization, staged seal publication, read-only verification,
successor creation, and the shared byte/hash primitives used by legacy BBK
artifact and handoff commands.

A successful seal proves exact stored bytes and declared local reference
closure.  It does not assert semantic acceptance, authorization, independent
review, deployment readiness, or release authority.
"""
from __future__ import annotations

import argparse
import contextlib
import ctypes
import datetime as dt
import errno
import hashlib
import json
import os
import re
import shutil
import socket
import stat
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePath, PurePosixPath
from typing import Any, Iterable, Mapping, MutableMapping, Sequence

try:
    from strict_json import DEFAULT_MAX_DEPTH, StrictJsonError, load_path, loads_bytes
except ModuleNotFoundError:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from strict_json import DEFAULT_MAX_DEPTH, StrictJsonError, load_path, loads_bytes

BBK_JSON_1 = "BBK-JSON-1"
DRAFT_FILE = "bbk-package-draft.json"
PACKAGE_FILE = "bbk-package.json"
MANIFEST_FILE = "bbk-package-manifest.json"
RECEIPT_FILE = "bbk-seal-receipt.json"
PROFILE_REGISTRY = "spec/contracts/artifact-package-profile-registry.json"
GENERATED_FILES = frozenset({PACKAGE_FILE, MANIFEST_FILE, RECEIPT_FILE})
AUTHORITY_BOUNDARY = (
    "This receipt proves exact stored bytes and declared local reference closure only; "
    "it does not establish semantic acceptance, authorization, independent review, "
    "deployment readiness, or release authority."
)
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ROLE = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{0,127}$")


def _package_root() -> Path:
    script = Path(__file__).resolve()
    candidates: list[Path] = []
    if value := os.environ.get("BBK_PACKAGE_ROOT"):
        candidates.append(Path(value).expanduser())
    candidates.extend([script.parents[1], script.parent])
    for candidate in candidates:
        if (candidate / "VERSION").is_file() and (candidate / "spec").is_dir():
            return candidate.resolve()
    return script.parents[1]


PACKAGE_ROOT = _package_root()
SCHEMA_ROOT = PACKAGE_ROOT / "spec" / "schemas"


def _version() -> str:
    for candidate in (PACKAGE_ROOT / "VERSION", Path(__file__).resolve().parent / "VERSION"):
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8").strip()
    return "unknown"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json_bytes(value: Any) -> bytes:
    """Return exact BBK-JSON-1 stored bytes."""
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def identity_json_bytes(value: Any) -> bytes:
    """Return deterministic compact bytes used for an internal identity digest."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def file_reference(path: Path, *, root: Path | None = None) -> dict[str, Any]:
    """Return one shared exact-byte reference used by legacy constructors."""
    physical = path.resolve(strict=True)
    if physical.is_symlink() or not physical.is_file():
        raise ValueError(f"not a regular physical file: {path}")
    rendered = physical.as_posix()
    if root is not None:
        rendered = physical.relative_to(root.resolve(strict=True)).as_posix()
    return {
        "path": rendered,
        "bytes": physical.stat().st_size,
        "sha256": sha256_file(physical),
    }


def verify_file_reference(reference: Mapping[str, Any], *, root: Path) -> list[str]:
    errors: list[str] = []
    raw = reference.get("path")
    if not isinstance(raw, str) or not raw:
        return ["reference.path must be a non-empty string"]
    try:
        path = resolve_local_path(root, raw, must_exist=True)
    except ValueError as exc:
        return [str(exc)]
    if not path.is_file():
        return [f"referenced path is not a regular file: {raw}"]
    actual_bytes = path.stat().st_size
    actual_sha = sha256_file(path)
    if reference.get("bytes") != actual_bytes:
        errors.append(f"byte length mismatch for {raw}: expected {reference.get('bytes')}, got {actual_bytes}")
    if reference.get("sha256") != actual_sha:
        errors.append(f"SHA-256 mismatch for {raw}: expected {reference.get('sha256')}, got {actual_sha}")
    return errors


def atomic_write(path: Path, data: bytes, *, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    temp = Path(raw)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(temp, mode)
        os.replace(temp, path)
        _fsync_dir(path.parent)
    finally:
        with contextlib.suppress(FileNotFoundError):
            temp.unlink()


def _fsync_dir(path: Path) -> None:
    if os.name != "posix":
        return
    flags = getattr(os, "O_DIRECTORY", 0) | os.O_RDONLY
    try:
        fd = os.open(path, flags)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _pointer(parts: Sequence[str | int]) -> str:
    if not parts:
        return ""
    return "/" + "/".join(str(p).replace("~", "~0").replace("/", "~1") for p in parts)


def finding(
    code: str,
    message: str,
    *,
    pointer: str = "",
    path: str | None = None,
    classification: str = "MECHANICAL",
    remediation: str = "Repair the exact affected package scope and rerun preflight.",
    severity: str = "ERROR",
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "code": code,
        "severity": severity,
        "classification": classification,
        "message": message,
        "pointer": pointer,
        "path": path,
        "remediation": remediation,
        "smallest_next_action": remediation,
    }
    if details:
        result["details"] = dict(details)
    return result


@dataclass
class ArtifactPackageError(RuntimeError):
    result: dict[str, Any]

    def __post_init__(self) -> None:
        RuntimeError.__init__(self, self.result.get("message") or self.result.get("status") or "artifact package error")

    def as_dict(self) -> dict[str, Any]:
        return self.result


def _operation_error(
    schema: str,
    code: str,
    message: str,
    *,
    path: str | None = None,
    classification: str = "MECHANICAL",
    remediation: str,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    item = finding(
        code,
        message,
        path=path,
        classification=classification,
        remediation=remediation,
        details=details,
    )
    return {
        "schema": schema,
        "status": "REJECTED",
        "code": code,
        "classification": classification,
        "message": message,
        "path": path,
        "finding": item,
        "smallest_next_action": remediation,
        "claims_not_established": [
            "semantic acceptance",
            "authorization",
            "independent review",
            "release readiness",
        ],
    }


def _is_windows_absolute_text(value: str) -> bool:
    return bool(re.match(r"^[A-Za-z]:[\\/]", value)) or value.startswith("\\\\")


def validate_relative_path_text(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise ValueError("artifact path must be a non-empty string")
    if "\\" in value:
        raise ValueError(f"artifact path must use portable '/' separators: {value!r}")
    if value.startswith("/") or _is_windows_absolute_text(value):
        raise ValueError(f"artifact path must be relative: {value!r}")
    pure = PurePosixPath(value)
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError(f"artifact path contains an empty, current, or parent segment: {value!r}")
    if pure.as_posix() in GENERATED_FILES or pure.as_posix() == DRAFT_FILE:
        raise ValueError(f"artifact path collides with a package control file: {value!r}")
    return pure


def _reject_symlink_components(root: Path, relative: PurePosixPath, *, include_leaf: bool = True) -> None:
    current = root
    parts = relative.parts if include_leaf else relative.parts[:-1]
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"package paths do not follow symbolic links: {current}")


def resolve_local_path(root: Path, raw: str, *, must_exist: bool) -> Path:
    pure = validate_relative_path_text(raw)
    physical_root = root.resolve(strict=True)
    _reject_symlink_components(physical_root, pure)
    candidate = physical_root.joinpath(*pure.parts)
    if must_exist:
        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError as exc:
            raise ValueError(f"package path does not exist: {raw}") from exc
    else:
        parent = candidate.parent
        parent.mkdir(parents=True, exist_ok=True)
        _reject_symlink_components(physical_root, pure, include_leaf=False)
        resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(physical_root)
    except ValueError as exc:
        raise ValueError(f"package path escapes the declared root: {raw}") from exc
    return resolved


def _schema_index(schema_root: Path = SCHEMA_ROOT) -> dict[str, Path]:
    result: dict[str, Path] = {}
    if not schema_root.is_dir():
        return result
    for path in sorted(schema_root.glob("*.json")):
        result[path.name] = path
        try:
            value = load_path(path)
        except StrictJsonError:
            continue
        if not isinstance(value, dict):
            continue
        schema_id = value.get("$id")
        if isinstance(schema_id, str):
            result[schema_id] = path
            result[schema_id.rsplit("/", 1)[-1]] = path
        props = value.get("properties")
        if isinstance(props, dict):
            schema_prop = props.get("schema")
            if isinstance(schema_prop, dict):
                const = schema_prop.get("const")
                if isinstance(const, str):
                    result[const] = path
    return result


def _json_type_matches(value: Any, expected: str) -> bool:
    return {
        "null": value is None,
        "boolean": isinstance(value, bool),
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "string": isinstance(value, str),
    }.get(expected, True)


class _SchemaValidator:
    """Small Draft 2020-12 subset sufficient for BBK's bundled contracts.

    It intentionally resolves schema references separately from artifact
    references.  Recursive schema references are valid; artifact cycles are
    evaluated later under the selected package profile.
    """

    def __init__(self, schema_root: Path = SCHEMA_ROOT) -> None:
        self.schema_root = schema_root
        self.index = _schema_index(schema_root)
        self.cache: dict[Path, Any] = {}

    def load_schema(self, declared: str) -> tuple[Path, Any] | None:
        path = self.index.get(declared)
        if path is None:
            basename = declared.rsplit("/", 1)[-1]
            path = self.index.get(basename)
        if path is None:
            return None
        if path not in self.cache:
            self.cache[path] = load_path(path)
        return path, self.cache[path]

    @staticmethod
    def _fragment(value: Any, fragment: str) -> Any:
        if not fragment or fragment == "#":
            return value
        if not fragment.startswith("#/"):
            raise ValueError(f"unsupported schema reference fragment: {fragment}")
        current = value
        for raw in fragment[2:].split("/"):
            token = raw.replace("~1", "/").replace("~0", "~")
            if not isinstance(current, dict) or token not in current:
                raise ValueError(f"unresolved schema reference fragment: {fragment}")
            current = current[token]
        return current

    def resolve_ref(self, ref: str, *, current_path: Path, current_schema: Any) -> tuple[Path, Any]:
        if ref.startswith("#"):
            return current_path, self._fragment(current_schema, ref)
        external, marker, fragment = ref.partition("#")
        path = self.index.get(external) or self.index.get(external.rsplit("/", 1)[-1])
        if path is None:
            candidate = (current_path.parent / external).resolve()
            if candidate.is_file() and candidate.parent == self.schema_root.resolve():
                path = candidate
        if path is None:
            raise ValueError(f"unresolved schema reference: {ref}")
        if path not in self.cache:
            self.cache[path] = load_path(path)
        value = self.cache[path]
        return path, self._fragment(value, f"#{fragment}" if marker else "")

    def validate(self, instance: Any, declared: str) -> list[dict[str, Any]]:
        loaded = self.load_schema(declared)
        if loaded is None:
            return [finding(
                "PACKAGE_SCHEMA_NOT_FOUND",
                f"No bundled schema resolves declared schema {declared!r}.",
                classification="SEMANTIC_OWNER_REQUIRED",
                remediation="Add or select the exact governed schema before package admission.",
            )]
        path, schema = loaded
        findings: list[dict[str, Any]] = []
        self._validate(instance, schema, path, schema, (), findings, set())
        return findings

    def _validate(
        self,
        instance: Any,
        schema: Any,
        schema_path: Path,
        schema_document: Any,
        path: Sequence[str | int],
        findings: list[dict[str, Any]],
        active: set[tuple[str, int, str]],
    ) -> None:
        if isinstance(schema, bool):
            if not schema:
                findings.append(finding("SCHEMA_FALSE", "Instance is rejected by a false schema.", pointer=_pointer(path)))
            return
        if not isinstance(schema, dict):
            return
        marker = (str(schema_path), id(instance), str(schema.get("$id") or schema.get("$ref") or id(schema)))
        if marker in active:
            # A recursive schema reached the same instance node.  The finite
            # instance has already been checked at this schema position.
            return
        next_active = set(active)
        next_active.add(marker)

        ref = schema.get("$ref")
        if isinstance(ref, str):
            try:
                ref_path, target = self.resolve_ref(ref, current_path=schema_path, current_schema=schema_document)
                target_document = self.cache.get(ref_path, schema_document if ref_path == schema_path else target)
                self._validate(instance, target, ref_path, target_document, path, findings, next_active)
            except (ValueError, StrictJsonError) as exc:
                findings.append(finding(
                    "SCHEMA_REFERENCE_UNRESOLVED",
                    str(exc),
                    pointer=_pointer(path),
                    classification="SEMANTIC_OWNER_REQUIRED",
                    remediation="Repair the schema reference or provide the exact referenced schema.",
                ))
            # Sibling keywords are permitted in modern JSON Schema and continue.

        expected = schema.get("type")
        if isinstance(expected, str):
            allowed = [expected]
        elif isinstance(expected, list):
            allowed = [item for item in expected if isinstance(item, str)]
        else:
            allowed = []
        if allowed and not any(_json_type_matches(instance, item) for item in allowed):
            findings.append(finding(
                "SCHEMA_TYPE_MISMATCH",
                f"Expected JSON type {allowed}, got {type(instance).__name__}.",
                pointer=_pointer(path),
            ))
            return
        if "const" in schema and instance != schema["const"]:
            findings.append(finding("SCHEMA_CONST_MISMATCH", f"Value must equal {schema['const']!r}.", pointer=_pointer(path)))
        enum = schema.get("enum")
        if isinstance(enum, list) and instance not in enum:
            findings.append(finding("SCHEMA_ENUM_MISMATCH", f"Value is not in the permitted vocabulary {enum!r}.", pointer=_pointer(path)))

        for keyword in ("allOf",):
            values = schema.get(keyword)
            if isinstance(values, list):
                for child in values:
                    self._validate(instance, child, schema_path, schema_document, path, findings, next_active)
        for keyword, exact in (("anyOf", False), ("oneOf", True)):
            values = schema.get(keyword)
            if isinstance(values, list):
                passes = 0
                for child in values:
                    local: list[dict[str, Any]] = []
                    self._validate(instance, child, schema_path, schema_document, path, local, next_active)
                    if not local:
                        passes += 1
                if passes == 0 or (exact and passes != 1):
                    findings.append(finding(
                        "SCHEMA_COMPOSITION_MISMATCH",
                        f"Value does not satisfy {keyword} (matching branches: {passes}).",
                        pointer=_pointer(path),
                    ))
        if_schema = schema.get("if")
        if isinstance(if_schema, (dict, bool)):
            probe: list[dict[str, Any]] = []
            self._validate(instance, if_schema, schema_path, schema_document, path, probe, next_active)
            branch = schema.get("then") if not probe else schema.get("else")
            if isinstance(branch, (dict, bool)):
                self._validate(instance, branch, schema_path, schema_document, path, findings, next_active)

        if isinstance(instance, dict):
            required = schema.get("required")
            if isinstance(required, list):
                for name in required:
                    if isinstance(name, str) and name not in instance:
                        findings.append(finding(
                            "SCHEMA_REQUIRED_PROPERTY_MISSING",
                            f"Required property {name!r} is missing.",
                            pointer=_pointer((*path, name)),
                        ))
            properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
            pattern_properties = schema.get("patternProperties") if isinstance(schema.get("patternProperties"), dict) else {}
            evaluated: set[str] = set()
            for name, value in instance.items():
                if name in properties:
                    evaluated.add(name)
                    self._validate(value, properties[name], schema_path, schema_document, (*path, name), findings, next_active)
                for pattern, child in pattern_properties.items():
                    try:
                        matched = re.search(pattern, name) is not None
                    except re.error:
                        matched = False
                    if matched:
                        evaluated.add(name)
                        self._validate(value, child, schema_path, schema_document, (*path, name), findings, next_active)
            additional = schema.get("additionalProperties", True)
            for name, value in instance.items():
                if name in evaluated or name in properties:
                    continue
                if additional is False:
                    findings.append(finding(
                        "SCHEMA_ADDITIONAL_PROPERTY",
                        f"Property {name!r} is not permitted.",
                        pointer=_pointer((*path, name)),
                    ))
                elif isinstance(additional, dict):
                    self._validate(value, additional, schema_path, schema_document, (*path, name), findings, next_active)
            min_props = schema.get("minProperties")
            max_props = schema.get("maxProperties")
            if isinstance(min_props, int) and len(instance) < min_props:
                findings.append(finding("SCHEMA_MIN_PROPERTIES", f"Object requires at least {min_props} properties.", pointer=_pointer(path)))
            if isinstance(max_props, int) and len(instance) > max_props:
                findings.append(finding("SCHEMA_MAX_PROPERTIES", f"Object permits at most {max_props} properties.", pointer=_pointer(path)))

        if isinstance(instance, list):
            min_items = schema.get("minItems")
            max_items = schema.get("maxItems")
            if isinstance(min_items, int) and len(instance) < min_items:
                findings.append(finding("SCHEMA_MIN_ITEMS", f"Array requires at least {min_items} items.", pointer=_pointer(path)))
            if isinstance(max_items, int) and len(instance) > max_items:
                findings.append(finding("SCHEMA_MAX_ITEMS", f"Array permits at most {max_items} items.", pointer=_pointer(path)))
            if schema.get("uniqueItems") is True:
                seen: set[bytes] = set()
                for index, item in enumerate(instance):
                    marker_bytes = identity_json_bytes(item)
                    if marker_bytes in seen:
                        findings.append(finding("SCHEMA_UNIQUE_ITEMS", "Array items must be unique.", pointer=_pointer((*path, index))))
                    seen.add(marker_bytes)
            prefix = schema.get("prefixItems")
            if isinstance(prefix, list):
                for index, child in enumerate(prefix[: len(instance)]):
                    self._validate(instance[index], child, schema_path, schema_document, (*path, index), findings, next_active)
            items = schema.get("items")
            if isinstance(items, (dict, bool)):
                start = len(prefix) if isinstance(prefix, list) else 0
                for index in range(start, len(instance)):
                    self._validate(instance[index], items, schema_path, schema_document, (*path, index), findings, next_active)

        if isinstance(instance, str):
            min_length = schema.get("minLength")
            max_length = schema.get("maxLength")
            if isinstance(min_length, int) and len(instance) < min_length:
                findings.append(finding("SCHEMA_MIN_LENGTH", f"String requires at least {min_length} characters.", pointer=_pointer(path)))
            if isinstance(max_length, int) and len(instance) > max_length:
                findings.append(finding("SCHEMA_MAX_LENGTH", f"String permits at most {max_length} characters.", pointer=_pointer(path)))
            pattern = schema.get("pattern")
            if isinstance(pattern, str):
                try:
                    matched = re.search(pattern, instance) is not None
                except re.error:
                    matched = True
                if not matched:
                    findings.append(finding("SCHEMA_PATTERN_MISMATCH", f"String does not match pattern {pattern!r}.", pointer=_pointer(path)))

        if isinstance(instance, (int, float)) and not isinstance(instance, bool):
            for key, comparison, symbol in (
                ("minimum", lambda a, b: a >= b, ">="),
                ("maximum", lambda a, b: a <= b, "<="),
                ("exclusiveMinimum", lambda a, b: a > b, ">"),
                ("exclusiveMaximum", lambda a, b: a < b, "<"),
            ):
                bound = schema.get(key)
                if isinstance(bound, (int, float)) and not comparison(instance, bound):
                    findings.append(finding("SCHEMA_NUMERIC_BOUND", f"Number must be {symbol} {bound}.", pointer=_pointer(path)))


def validate_schema_instance(
    instance: Any,
    declared_schema: str,
    *,
    schema_root: Path = SCHEMA_ROOT,
) -> list[dict[str, Any]]:
    """Validate one instance with BBK's dependency-free schema subset.

    Schema-reference traversal is deliberately independent of artifact graph
    traversal, so recursive schemas do not become package reference cycles.
    """
    return _SchemaValidator(schema_root).validate(instance, declared_schema)


def load_profile_registry(path: Path | None = None) -> dict[str, Any]:
    candidate = path or (PACKAGE_ROOT / PROFILE_REGISTRY)
    value = load_path(candidate)
    if not isinstance(value, dict) or value.get("schema") != "bbk.artifact-package-profile-registry.v1":
        raise ValueError(f"not a BBK artifact package profile registry: {candidate}")
    profiles = value.get("profiles")
    if not isinstance(profiles, list):
        raise ValueError("profile registry profiles must be an array")
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(profiles):
        if not isinstance(item, dict):
            raise ValueError(f"profile registry profiles[{index}] must be an object")
        key = (str(item.get("id")), str(item.get("version")))
        if key in seen:
            raise ValueError(f"duplicate artifact package profile: {key[0]} {key[1]}")
        seen.add(key)
    return value


def select_profile(registry: Mapping[str, Any], profile_ref: Any) -> dict[str, Any] | None:
    if not isinstance(profile_ref, dict):
        return None
    profile_id = profile_ref.get("id")
    version = str(profile_ref.get("version"))
    for item in registry.get("profiles", []):
        if isinstance(item, dict) and item.get("id") == profile_id and str(item.get("version")) == version:
            return item
    return None


def _load_artifact_json(path: Path, max_depth: int) -> Any:
    return loads_bytes(path.read_bytes(), source=str(path), max_depth=max_depth)


def _detect_cycle(graph: Mapping[str, Sequence[str]]) -> list[str] | None:
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        marker = state.get(node, 0)
        if marker == 1:
            try:
                start = stack.index(node)
            except ValueError:
                start = 0
            return [*stack[start:], node]
        if marker == 2:
            return None
        state[node] = 1
        stack.append(node)
        for target in graph.get(node, []):
            found = visit(target)
            if found:
                return found
        stack.pop()
        state[node] = 2
        return None

    for node in sorted(graph):
        found = visit(node)
        if found:
            return found
    return None


def _semantic_findings(
    profile: Mapping[str, Any],
    descriptor: Mapping[str, Any],
    artifacts: Mapping[str, tuple[Mapping[str, Any], Any | None]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    subject = descriptor.get("subject") if isinstance(descriptor.get("subject"), dict) else {}
    subject_id = subject.get("id")
    subject_kind = subject.get("kind")
    validators = profile.get("semanticValidators") if isinstance(profile.get("semanticValidators"), list) else []
    for validator in validators:
        if validator == "executor-identity":
            for artifact_id, (meta, value) in artifacts.items():
                if not isinstance(value, dict) or value.get("schema") != "bbk.role-return.v2":
                    continue
                role = value.get("role")
                executor = value.get("executor") if isinstance(value.get("executor"), dict) else {}
                executor_role = executor.get("role")
                if subject_kind in {"role", "canonical-role", "role-return"} and role != subject_id:
                    result.append(finding(
                        "PACKAGE_EXECUTOR_IDENTITY_MISMATCH",
                        f"Role return {artifact_id!r} role {role!r} does not match package subject {subject_id!r}.",
                        pointer="/role",
                        path=str(meta.get("path")),
                        classification="SEMANTIC_OWNER_REQUIRED",
                        remediation="Bind the return to the exact executor/subject identity or select the correct package subject.",
                    ))
                if executor_role is not None and role is not None and executor_role != role:
                    result.append(finding(
                        "PACKAGE_EXECUTOR_IDENTITY_MISMATCH",
                        f"Role return {artifact_id!r} executor.role {executor_role!r} differs from role {role!r}.",
                        pointer="/executor/role",
                        path=str(meta.get("path")),
                        classification="SEMANTIC_OWNER_REQUIRED",
                        remediation="Repair the exact executor identity binding.",
                    ))
        elif validator in {"handoff-subject-binding", "candidate-subject-binding"}:
            for artifact_id, (meta, value) in artifacts.items():
                if not isinstance(value, dict):
                    continue
                artifact_subject = value.get("subject")
                if isinstance(artifact_subject, dict) and artifact_subject.get("id") not in {None, subject_id}:
                    result.append(finding(
                        "PACKAGE_SUBJECT_IDENTITY_MISMATCH",
                        f"Artifact {artifact_id!r} subject does not match the package subject.",
                        pointer="/subject/id",
                        path=str(meta.get("path")),
                        classification="SEMANTIC_OWNER_REQUIRED",
                        remediation="Bind the artifact and package to the same exact subject identity.",
                    ))
        elif validator == "review-candidate-binding":
            for artifact_id, (meta, value) in artifacts.items():
                if not isinstance(value, dict) or value.get("schema") != "bbk.review-package.v2":
                    continue
                candidate = value.get("candidate")
                if not isinstance(candidate, dict) or not candidate.get("contentSha256"):
                    result.append(finding(
                        "PACKAGE_REVIEW_CANDIDATE_BINDING_MISSING",
                        f"Review artifact {artifact_id!r} lacks an exact sealed candidate content digest.",
                        pointer="/candidate/contentSha256",
                        path=str(meta.get("path")),
                        classification="SEMANTIC_OWNER_REQUIRED",
                        remediation="Generate the review package from an exact verified sealed candidate.",
                    ))
    return result


def preflight_draft(
    draft_root: Path | str,
    *,
    registry_path: Path | None = None,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> dict[str, Any]:
    """Run cheap deterministic package admission checks without mutation."""
    raw_root = Path(draft_root).expanduser()
    findings: list[dict[str, Any]] = []
    descriptor: dict[str, Any] | None = None
    profile: dict[str, Any] | None = None
    loaded_artifacts: dict[str, tuple[Mapping[str, Any], Any | None]] = {}
    artifact_count = 0
    reference_count = 0

    if raw_root.is_symlink():
        findings.append(finding(
            "PACKAGE_ROOT_SYMLINK_FORBIDDEN",
            "Package draft root must be a physical directory, not a symbolic link.",
            path=str(raw_root),
            remediation="Use the physical draft directory as the package root.",
        ))
        root = raw_root.absolute()
    else:
        try:
            root = raw_root.resolve(strict=True)
        except FileNotFoundError:
            root = raw_root.absolute()
            findings.append(finding(
                "PACKAGE_DRAFT_ROOT_NOT_FOUND",
                "Package draft root does not exist.",
                path=str(raw_root),
                remediation="Create the draft directory and its bbk-package-draft.json descriptor.",
            ))
        except OSError as exc:
            root = raw_root.absolute()
            findings.append(finding("PACKAGE_DRAFT_ROOT_UNREADABLE", str(exc), path=str(raw_root)))
    if root.exists() and not root.is_dir():
        findings.append(finding(
            "PACKAGE_DRAFT_ROOT_NOT_DIRECTORY",
            "Package draft root is not a directory.",
            path=str(root),
            remediation="Provide the directory containing bbk-package-draft.json.",
        ))

    descriptor_path = root / DRAFT_FILE
    if not findings or root.is_dir():
        try:
            raw_descriptor = load_path(descriptor_path, max_depth=max_depth)
            if not isinstance(raw_descriptor, dict):
                findings.append(finding("PACKAGE_DESCRIPTOR_NOT_OBJECT", "Package draft descriptor must be a JSON object.", path=str(descriptor_path)))
            else:
                descriptor = raw_descriptor
        except StrictJsonError as exc:
            diag = exc.as_dict()
            findings.append(finding(
                diag.get("code", "PACKAGE_DESCRIPTOR_JSON_INVALID"),
                diag.get("message", "Package descriptor is invalid JSON."),
                pointer=diag.get("pointer", ""),
                path=str(descriptor_path),
                remediation=diag.get("remediation", "Repair the exact JSON defect."),
                details={key: diag[key] for key in ("line", "column", "offset", "duplicate_key") if key in diag},
            ))

    registry: dict[str, Any] | None = None
    try:
        registry = load_profile_registry(registry_path)
    except (StrictJsonError, ValueError, OSError) as exc:
        findings.append(finding(
            "PACKAGE_PROFILE_REGISTRY_INVALID",
            f"Artifact package profile registry is unavailable or invalid: {exc}",
            classification="SEMANTIC_OWNER_REQUIRED",
            remediation="Repair the canonical artifact package profile registry before package admission.",
        ))

    validator = _SchemaValidator()
    if descriptor is not None:
        for item in validator.validate(descriptor, "bbk.artifact-package-draft.v1"):
            item["path"] = str(descriptor_path)
            findings.append(item)
        if descriptor.get("schema") != "bbk.artifact-package-draft.v1":
            findings.append(finding(
                "PACKAGE_DESCRIPTOR_SCHEMA_INVALID",
                "descriptor.schema must equal bbk.artifact-package-draft.v1.",
                pointer="/schema",
                path=str(descriptor_path),
            ))
        package_id = descriptor.get("packageId")
        revision = descriptor.get("revision")
        if not isinstance(package_id, str) or not _SAFE_ID.fullmatch(package_id):
            findings.append(finding("PACKAGE_ID_INVALID", "packageId is missing or outside the stable ID vocabulary.", pointer="/packageId", path=str(descriptor_path)))
        if not isinstance(revision, str) or not revision.strip():
            findings.append(finding("PACKAGE_REVISION_INVALID", "revision must be a non-empty semantic revision string.", pointer="/revision", path=str(descriptor_path)))
        if registry is not None:
            profile = select_profile(registry, descriptor.get("profile"))
            if profile is None:
                findings.append(finding(
                    "PACKAGE_PROFILE_UNKNOWN",
                    f"No profile matches {descriptor.get('profile')!r}.",
                    pointer="/profile",
                    path=str(descriptor_path),
                    classification="SEMANTIC_OWNER_REQUIRED",
                    remediation="Select one exact profile ID/version from the canonical registry.",
                ))

        raw_artifacts = descriptor.get("artifacts")
        if isinstance(raw_artifacts, list):
            artifact_count = len(raw_artifacts)
            ids: set[str] = set()
            paths: set[str] = set()
            graph: dict[str, list[str]] = {}
            schemas_seen: set[str] = set()
            generated_fields = set()
            if isinstance(registry, dict):
                ownership = registry.get("generatedFieldOwnership")
                if isinstance(ownership, dict) and isinstance(ownership.get("descriptorFields"), list):
                    generated_fields = {str(item) for item in ownership["descriptorFields"]}
            for index, raw in enumerate(raw_artifacts):
                pointer = f"/artifacts/{index}"
                if not isinstance(raw, dict):
                    findings.append(finding("PACKAGE_ARTIFACT_DESCRIPTOR_INVALID", "Artifact descriptor must be an object.", pointer=pointer, path=str(descriptor_path)))
                    continue
                forbidden = sorted(generated_fields.intersection(raw))
                for name in forbidden:
                    findings.append(finding(
                        "PACKAGE_GENERATED_FIELD_MANUALLY_OWNED",
                        f"Artifact descriptor field {name!r} is generated by the package engine and is forbidden in a draft.",
                        pointer=f"{pointer}/{name}",
                        path=str(descriptor_path),
                        remediation=f"Remove {name!r}; the seal engine will generate it from exact bytes.",
                    ))
                artifact_id = raw.get("artifactId")
                raw_path = raw.get("path")
                role = raw.get("role")
                declared_schema = raw.get("schema")
                refs = raw.get("references", [])
                if not isinstance(artifact_id, str) or not _SAFE_ID.fullmatch(artifact_id):
                    findings.append(finding("PACKAGE_ARTIFACT_ID_INVALID", "artifactId is missing or invalid.", pointer=f"{pointer}/artifactId", path=str(descriptor_path)))
                    continue
                if artifact_id in ids:
                    findings.append(finding("PACKAGE_ARTIFACT_ID_DUPLICATE", f"Duplicate artifactId {artifact_id!r}.", pointer=f"{pointer}/artifactId", path=str(descriptor_path)))
                ids.add(artifact_id)
                if not isinstance(raw_path, str):
                    findings.append(finding("PACKAGE_ARTIFACT_PATH_INVALID", "Artifact path must be a non-empty relative string.", pointer=f"{pointer}/path", path=str(descriptor_path)))
                    graph[artifact_id] = []
                    continue
                if raw_path in paths:
                    findings.append(finding("PACKAGE_ARTIFACT_PATH_DUPLICATE", f"Artifact path {raw_path!r} is owned by more than one artifact.", pointer=f"{pointer}/path", path=str(descriptor_path)))
                paths.add(raw_path)
                if profile is not None:
                    roles = profile.get("artifactRoles") if isinstance(profile.get("artifactRoles"), list) else []
                    if role not in roles:
                        findings.append(finding(
                            "PACKAGE_ARTIFACT_ROLE_NOT_PERMITTED",
                            f"Artifact role {role!r} is not permitted by profile {profile.get('id')} {profile.get('version')}.",
                            pointer=f"{pointer}/role",
                            path=str(descriptor_path),
                            classification="SEMANTIC_OWNER_REQUIRED",
                            remediation="Use an artifact role from the selected profile vocabulary or select the correct profile.",
                        ))
                    permitted = profile.get("permittedSchemas") if isinstance(profile.get("permittedSchemas"), list) else []
                    if isinstance(declared_schema, str) and "*" not in permitted and declared_schema not in permitted:
                        findings.append(finding(
                            "PACKAGE_ARTIFACT_SCHEMA_NOT_PERMITTED",
                            f"Schema {declared_schema!r} is not permitted by the selected profile.",
                            pointer=f"{pointer}/schema",
                            path=str(descriptor_path),
                            classification="SEMANTIC_OWNER_REQUIRED",
                            remediation="Use a schema permitted by the profile or select the correct profile.",
                        ))
                if isinstance(declared_schema, str):
                    schemas_seen.add(declared_schema)
                try:
                    artifact_path = resolve_local_path(root, raw_path, must_exist=True)
                    if artifact_path.is_symlink() or not artifact_path.is_file():
                        raise ValueError(f"artifact is not a regular physical file: {raw_path}")
                    value: Any | None = None
                    if artifact_path.suffix.lower() == ".json" or isinstance(declared_schema, str):
                        value = _load_artifact_json(artifact_path, max_depth)
                        if not isinstance(value, dict) and isinstance(declared_schema, str):
                            findings.append(finding(
                                "PACKAGE_SCHEMA_INSTANCE_NOT_OBJECT",
                                "A schema-declared artifact must be a JSON object.",
                                path=raw_path,
                            ))
                        if isinstance(value, dict) and isinstance(declared_schema, str):
                            actual_schema = value.get("schema")
                            if actual_schema != declared_schema:
                                findings.append(finding(
                                    "PACKAGE_DECLARED_SCHEMA_MISMATCH",
                                    f"Descriptor declares {declared_schema!r} but artifact reports {actual_schema!r}.",
                                    pointer="/schema",
                                    path=raw_path,
                                ))
                            for item in validator.validate(value, declared_schema):
                                item["path"] = raw_path
                                findings.append(item)
                    loaded_artifacts[artifact_id] = (raw, value)
                except StrictJsonError as exc:
                    diag = exc.as_dict()
                    findings.append(finding(
                        diag.get("code", "PACKAGE_ARTIFACT_JSON_INVALID"),
                        diag.get("message", "Artifact JSON is invalid."),
                        pointer=diag.get("pointer", ""),
                        path=raw_path,
                        remediation=diag.get("remediation", "Repair the exact JSON defect."),
                        details={key: diag[key] for key in ("line", "column", "offset", "duplicate_key") if key in diag},
                    ))
                    loaded_artifacts[artifact_id] = (raw, None)
                except (ValueError, OSError) as exc:
                    findings.append(finding(
                        "PACKAGE_ARTIFACT_PATH_INVALID",
                        str(exc),
                        pointer=f"{pointer}/path",
                        path=raw_path,
                        remediation="Repair the exact local artifact path; package paths may not escape or traverse symlinks.",
                    ))
                    loaded_artifacts[artifact_id] = (raw, None)

                if not isinstance(refs, list):
                    findings.append(finding("PACKAGE_REFERENCES_INVALID", "references must be an array of artifact IDs.", pointer=f"{pointer}/references", path=str(descriptor_path)))
                    graph[artifact_id] = []
                else:
                    normalized_refs = [item for item in refs if isinstance(item, str)]
                    reference_count += len(normalized_refs)
                    if len(normalized_refs) != len(refs) or len(set(normalized_refs)) != len(normalized_refs):
                        findings.append(finding("PACKAGE_REFERENCES_INVALID", "references must contain unique string artifact IDs.", pointer=f"{pointer}/references", path=str(descriptor_path)))
                    graph[artifact_id] = normalized_refs

            for source, targets in graph.items():
                for target in targets:
                    if target not in ids:
                        findings.append(finding(
                            "PACKAGE_REFERENCE_UNRESOLVED",
                            f"Artifact {source!r} references unknown artifact {target!r}.",
                            path=str(descriptor_path),
                            remediation="Declare the referenced local artifact or remove the invalid edge.",
                            details={"from": source, "to": target},
                        ))
            if profile is not None:
                required_schemas = profile.get("requiredSchemas") if isinstance(profile.get("requiredSchemas"), list) else []
                for required in required_schemas:
                    if required not in schemas_seen:
                        findings.append(finding(
                            "PACKAGE_REQUIRED_SCHEMA_MISSING",
                            f"Profile requires at least one artifact with schema {required!r}.",
                            pointer="/artifacts",
                            path=str(descriptor_path),
                            classification="SEMANTIC_OWNER_REQUIRED",
                            remediation=f"Add the required {required!r} artifact or select the correct profile.",
                        ))
                if profile.get("artifactReferenceCycles") == "FORBIDDEN":
                    cycle = _detect_cycle(graph)
                    if cycle:
                        findings.append(finding(
                            "PACKAGE_ARTIFACT_REFERENCE_CYCLE",
                            "Artifact reference cycles are forbidden by the selected profile.",
                            pointer="/artifacts",
                            path=str(descriptor_path),
                            remediation="Break the declared artifact-reference cycle; recursive JSON Schema references are evaluated separately and remain permitted.",
                            details={"cycle": cycle},
                        ))
                findings.extend(_semantic_findings(profile, descriptor, loaded_artifacts))
        else:
            findings.append(finding("PACKAGE_ARTIFACTS_INVALID", "descriptor.artifacts must be an array.", pointer="/artifacts", path=str(descriptor_path)))

    errors = sum(1 for item in findings if item.get("severity", "ERROR") == "ERROR")
    warnings = sum(1 for item in findings if item.get("severity") == "WARNING")
    status = "PASS" if errors == 0 else "REJECTED"
    package_summary = None
    if descriptor is not None:
        package_summary = {
            "packageId": descriptor.get("packageId"),
            "revision": descriptor.get("revision"),
            "subject": descriptor.get("subject"),
        }
    profile_summary = None
    if profile is not None:
        profile_summary = {"id": profile.get("id"), "version": profile.get("version")}
    return {
        "schema": "bbk.artifact-package-preflight.v1",
        "status": status,
        "draftRoot": str(root),
        "profile": profile_summary,
        "package": package_summary,
        "findings": findings,
        "summary": {
            "errors": errors,
            "warnings": warnings,
            "artifacts": artifact_count,
            "references": reference_count,
        },
        "claims_not_established": [
            "semantic acceptance",
            "authorization",
            "independent review",
            "release readiness",
        ],
        "smallest_next_action": (
            "Seal the admitted draft or submit it to the exact intended consumer."
            if status == "PASS"
            else (findings[0].get("remediation") if findings else "Repair the exact package defect and rerun preflight.")
        ),
    }


def _lock_metadata(operation: str, target: Path) -> dict[str, Any]:
    return {
        "schema": "bbk.artifact-package-lock.v1",
        "operation": operation,
        "target": str(target),
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "createdAtUtc": utc_now(),
        "toolVersion": _version(),
    }


@contextlib.contextmanager
def _exclusive_lock(lock_path: Path, *, operation: str, target: Path, recover_stale: bool = False):
    stale_seconds = 3600
    try:
        lock_path.mkdir(mode=0o700)
    except FileExistsError as exc:
        metadata: Any = None
        metadata_path = lock_path / "lock.json"
        with contextlib.suppress(Exception):
            metadata = load_path(metadata_path)
        age = None
        with contextlib.suppress(OSError):
            age = max(0.0, dt.datetime.now().timestamp() - lock_path.stat().st_mtime)
        stale = age is not None and age > stale_seconds
        if recover_stale and stale:
            shutil.rmtree(lock_path)
            lock_path.mkdir(mode=0o700)
        else:
            code = "PACKAGE_LOCK_STALE_OR_AMBIGUOUS" if stale else "PACKAGE_LOCK_HELD"
            raise ArtifactPackageError(_operation_error(
                "bbk.artifact-package-lock-result.v1",
                code,
                f"Exclusive package lock is already present: {lock_path}",
                path=str(lock_path),
                remediation=(
                    "Inspect the recorded owner and explicitly rerun with stale-lock recovery only after confirming no active owner."
                    if stale
                    else "Allow the current owner to finish, or inspect and resolve the exact lock owner before retrying."
                ),
                details={"metadata": metadata, "ageSeconds": age, "staleThresholdSeconds": stale_seconds},
            )) from exc
    atomic_write(lock_path / "lock.json", canonical_json_bytes(_lock_metadata(operation, target)))
    try:
        yield lock_path
    finally:
        with contextlib.suppress(FileNotFoundError):
            shutil.rmtree(lock_path)
        _fsync_dir(lock_path.parent)


def _atomic_publish_noreplace(stage: Path, target: Path) -> None:
    """Publish one directory atomically without replacing an existing target."""
    if target.exists() or target.is_symlink():
        raise FileExistsError(errno.EEXIST, "target already exists", str(target))
    if os.name == "posix":
        try:
            libc = ctypes.CDLL(None, use_errno=True)
            renameat2 = getattr(libc, "renameat2")
            renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
            renameat2.restype = ctypes.c_int
            result = renameat2(
                -100,
                os.fsencode(stage),
                -100,
                os.fsencode(target),
                1,  # RENAME_NOREPLACE
            )
            if result == 0:
                _fsync_dir(target.parent)
                return
            error = ctypes.get_errno()
            if error not in {errno.ENOSYS, errno.EINVAL, errno.ENOTSUP}:
                raise OSError(error, os.strerror(error), str(target))
        except AttributeError:
            pass
    # Windows os.rename refuses an existing target.  The POSIX fallback is
    # protected by the operation-specific lock and an immediate existence
    # check; platforms with renameat2 use the kernel no-replace primitive.
    if target.exists() or target.is_symlink():
        raise FileExistsError(errno.EEXIST, "target already exists", str(target))
    os.rename(stage, target)
    _fsync_dir(target.parent)


def _content_identity(
    descriptor: Mapping[str, Any],
    artifacts: Sequence[Mapping[str, Any]],
    reference_graph: Sequence[Mapping[str, str]],
) -> tuple[dict[str, Any], str]:
    value: dict[str, Any] = {
        "schema": "bbk.artifact-package-content.v1",
        "canonicalization": BBK_JSON_1,
        "packageId": descriptor.get("packageId"),
        "revision": descriptor.get("revision"),
        "profile": descriptor.get("profile"),
        "subject": descriptor.get("subject"),
        "predecessor": descriptor.get("predecessor"),
        "artifacts": list(artifacts),
        "referenceGraph": list(reference_graph),
    }
    return value, sha256_bytes(identity_json_bytes(value))


def _artifact_entries_from_draft(root: Path, descriptor: Mapping[str, Any], stage: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    raw_artifacts = descriptor.get("artifacts")
    assert isinstance(raw_artifacts, list)
    for raw in sorted(raw_artifacts, key=lambda item: str(item.get("artifactId"))):
        assert isinstance(raw, dict)
        source = resolve_local_path(root, str(raw["path"]), must_exist=True)
        destination = resolve_local_path(stage, str(raw["path"]), must_exist=False)
        destination.parent.mkdir(parents=True, exist_ok=True)
        source_bytes = source.read_bytes()
        if source.suffix.lower() == ".json" or isinstance(raw.get("schema"), str):
            value = loads_bytes(source_bytes, source=str(source))
            stored = canonical_json_bytes(value)
            canonicalization = BBK_JSON_1
        else:
            stored = source_bytes
            canonicalization = "UNCHANGED"
        atomic_write(destination, stored, mode=stat.S_IMODE(source.stat().st_mode))
        entry = {
            "artifactId": raw["artifactId"],
            "path": raw["path"],
            "schema": raw.get("schema"),
            "role": raw["role"],
            "references": sorted(raw.get("references") or []),
            "mediaType": raw.get("mediaType"),
            "bytes": len(stored),
            "sha256": sha256_bytes(stored),
            "canonicalization": canonicalization,
        }
        entries.append(entry)
    return entries


def _reference_graph(entries: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    return sorted(
        [
            {"from": str(entry["artifactId"]), "to": str(target)}
            for entry in entries
            for target in entry.get("references", [])
        ],
        key=lambda item: (item["from"], item["to"]),
    )


def seal_draft(
    draft_root: Path | str,
    output_root: Path | str,
    *,
    registry_path: Path | None = None,
    recover_stale_lock: bool = False,
    sealed_at_utc: str | None = None,
    _test_fail_phase: str | None = None,
) -> dict[str, Any]:
    """Preflight, stage, self-verify, and atomically publish a new package."""
    draft = Path(draft_root).expanduser().resolve(strict=True)
    output = Path(output_root).expanduser().absolute()
    output_parent = output.parent.resolve(strict=True)
    output = output_parent / output.name
    lock = output_parent / f".{output.name}.bbk-seal.lock"
    stage = output_parent / f".{output.name}.bbk-stage-{uuid.uuid4().hex}"
    schema = "bbk.artifact-package-seal-result.v1"
    if output.exists() or output.is_symlink():
        raise ArtifactPackageError(_operation_error(
            schema,
            "PACKAGE_TARGET_EXISTS",
            "Seal refuses to overwrite an existing output path.",
            path=str(output),
            remediation="Choose a new output directory or create a successor draft from the existing sealed package.",
        ))
    try:
        with _exclusive_lock(lock, operation="seal", target=output, recover_stale=recover_stale_lock):
            if output.exists() or output.is_symlink():
                raise ArtifactPackageError(_operation_error(
                    schema,
                    "PACKAGE_TARGET_EXISTS",
                    "Seal target appeared while acquiring the exclusive lock.",
                    path=str(output),
                    remediation="Do not overwrite the existing target; choose a new output or create a successor.",
                ))
            preflight = preflight_draft(draft, registry_path=registry_path)
            if preflight["status"] != "PASS":
                raise ArtifactPackageError({
                    "schema": schema,
                    "status": "REJECTED",
                    "code": "PACKAGE_PREFLIGHT_REJECTED",
                    "message": "Package seal stopped because deterministic preflight rejected the draft.",
                    "draftRoot": str(draft),
                    "outputRoot": str(output),
                    "preflight": preflight,
                    "smallest_next_action": preflight.get("smallest_next_action"),
                    "claims_not_established": preflight.get("claims_not_established", []),
                })
            descriptor = load_path(draft / DRAFT_FILE)
            assert isinstance(descriptor, dict)
            stage.mkdir(mode=0o700)
            entries = _artifact_entries_from_draft(draft, descriptor, stage)
            graph = _reference_graph(entries)
            identity_value, content_sha = _content_identity(descriptor, entries, graph)
            package = {
                "schema": "bbk.artifact-package.v1",
                "packageId": descriptor["packageId"],
                "revision": descriptor["revision"],
                "profile": descriptor["profile"],
                "subject": descriptor["subject"],
                "predecessor": descriptor.get("predecessor"),
                "artifacts": entries,
                "contentSha256": content_sha,
                "canonicalization": BBK_JSON_1,
                "lifecycle": "SEALED",
                "metadata": descriptor.get("metadata", {}),
            }
            manifest = {
                "schema": "bbk.artifact-package-manifest.v1",
                "packageId": descriptor["packageId"],
                "revision": descriptor["revision"],
                "profile": descriptor["profile"],
                "subject": descriptor["subject"],
                "predecessor": descriptor.get("predecessor"),
                "canonicalization": BBK_JSON_1,
                "artifacts": entries,
                "referenceGraph": graph,
                "closure": {
                    "artifactCount": len(entries),
                    "referenceCount": len(graph),
                    "unresolved": [],
                },
                "contentSha256": content_sha,
            }
            package_bytes = canonical_json_bytes(package)
            manifest_bytes = canonical_json_bytes(manifest)
            receipt = {
                "schema": "bbk.artifact-package-seal-receipt.v1",
                "packageId": descriptor["packageId"],
                "revision": descriptor["revision"],
                "contentSha256": content_sha,
                "manifestSha256": sha256_bytes(manifest_bytes),
                "sealedAtUtc": sealed_at_utc or utc_now(),
                "tool": {"name": "bbk", "version": _version()},
                "authorityBoundary": AUTHORITY_BOUNDARY,
            }
            atomic_write(stage / PACKAGE_FILE, package_bytes)
            atomic_write(stage / MANIFEST_FILE, manifest_bytes)
            atomic_write(stage / RECEIPT_FILE, canonical_json_bytes(receipt))
            _fsync_dir(stage)
            if _test_fail_phase == "after-stage":
                raise RuntimeError("injected failure after stage construction")
            staged_verification = verify_package(stage, registry_path=registry_path)
            if staged_verification["status"] != "PASS":
                raise ArtifactPackageError({
                    "schema": schema,
                    "status": "REJECTED",
                    "code": "PACKAGE_STAGED_VERIFY_FAILED",
                    "message": "Staged package failed read-only self-verification and was not published.",
                    "draftRoot": str(draft),
                    "outputRoot": str(output),
                    "verification": staged_verification,
                    "smallest_next_action": staged_verification.get("smallest_next_action"),
                    "claims_not_established": staged_verification.get("claims_not_established", []),
                })
            if _test_fail_phase == "before-publish":
                raise RuntimeError("injected failure before publish")
            _atomic_publish_noreplace(stage, output)
            stage = Path()  # mark moved
            final_verification = verify_package(output, registry_path=registry_path)
            if final_verification["status"] != "PASS":
                # This should be unreachable after same-volume rename.  Do not
                # repair or delete an externally visible package automatically;
                # return a precise bounded failure for operator disposition.
                raise ArtifactPackageError({
                    "schema": schema,
                    "status": "REJECTED",
                    "code": "PACKAGE_POST_PUBLISH_VERIFY_FAILED",
                    "message": "Published target failed verification; it is not authoritative.",
                    "outputRoot": str(output),
                    "verification": final_verification,
                    "smallest_next_action": "Quarantine the exact target and inspect the recorded verification findings.",
                    "claims_not_established": final_verification.get("claims_not_established", []),
                })
            return {
                "schema": schema,
                "status": "PASS",
                "draftRoot": str(draft),
                "outputRoot": str(output),
                "packageId": descriptor["packageId"],
                "revision": descriptor["revision"],
                "profile": descriptor["profile"],
                "contentSha256": content_sha,
                "manifestSha256": receipt["manifestSha256"],
                "artifactCount": len(entries),
                "verification": final_verification,
                "authorityBoundary": AUTHORITY_BOUNDARY,
                "smallest_next_action": "Provide the exact sealed package reference to its intended bounded consumer.",
                "claims_not_established": [
                    "semantic acceptance",
                    "authorization",
                    "independent review",
                    "release readiness",
                ],
            }
    except ArtifactPackageError:
        raise
    except FileExistsError as exc:
        raise ArtifactPackageError(_operation_error(
            schema,
            "PACKAGE_TARGET_EXISTS",
            "Atomic publication refused an existing target.",
            path=str(output),
            remediation="Preserve the existing target and choose a new output or create a successor.",
        )) from exc
    except Exception as exc:
        raise ArtifactPackageError(_operation_error(
            schema,
            "PACKAGE_SEAL_FAILED",
            f"Package seal failed before authoritative publication: {exc}",
            path=str(output),
            remediation="Inspect the exact draft/lock/staging finding, repair only the affected scope, and rerun seal to a new absent target.",
            details={"exceptionType": type(exc).__name__},
        )) from exc
    finally:
        if stage and str(stage) not in {".", ""} and stage.exists():
            shutil.rmtree(stage, ignore_errors=True)


def _load_control_file(root: Path, name: str, findings: list[dict[str, Any]]) -> Any | None:
    path = root / name
    if path.is_symlink():
        findings.append(finding("PACKAGE_CONTROL_SYMLINK_FORBIDDEN", f"Control file {name} may not be a symlink.", path=name))
        return None
    try:
        value = load_path(path)
    except StrictJsonError as exc:
        diag = exc.as_dict()
        findings.append(finding(
            diag.get("code", "PACKAGE_CONTROL_JSON_INVALID"),
            diag.get("message", f"Control file {name} is invalid."),
            pointer=diag.get("pointer", ""),
            path=name,
            remediation=diag.get("remediation", "Restore the exact canonical control file."),
        ))
        return None
    raw = path.read_bytes()
    if raw != canonical_json_bytes(value):
        findings.append(finding(
            "PACKAGE_CONTROL_NONCANONICAL",
            f"Control file {name} is not stored as exact BBK-JSON-1 bytes.",
            path=name,
            remediation="Restore the exact bytes from the authoritative sealed package; verify never normalizes or repairs.",
        ))
    return value


def verify_package(
    sealed_root: Path | str,
    *,
    registry_path: Path | None = None,
) -> dict[str, Any]:
    """Read-only recomputation of one sealed package."""
    raw_root = Path(sealed_root).expanduser()
    findings: list[dict[str, Any]] = []
    schema = "bbk.artifact-package-verification.v1"
    before: dict[str, tuple[int, int]] = {}
    if raw_root.is_symlink():
        findings.append(finding("PACKAGE_ROOT_SYMLINK_FORBIDDEN", "Sealed package root may not be a symbolic link.", path=str(raw_root)))
        root = raw_root.absolute()
    else:
        try:
            root = raw_root.resolve(strict=True)
        except FileNotFoundError:
            root = raw_root.absolute()
            findings.append(finding("PACKAGE_ROOT_NOT_FOUND", "Sealed package root does not exist.", path=str(raw_root), remediation="Provide the exact sealed package directory."))
        except OSError as exc:
            root = raw_root.absolute()
            findings.append(finding("PACKAGE_ROOT_UNREADABLE", str(exc), path=str(raw_root)))
    if root.exists() and root.is_dir():
        for path in root.rglob("*"):
            with contextlib.suppress(OSError):
                stat_result = path.lstat()
                before[path.relative_to(root).as_posix()] = (stat_result.st_mtime_ns, stat_result.st_size)
    elif root.exists():
        findings.append(finding("PACKAGE_ROOT_NOT_DIRECTORY", "Sealed package root is not a directory.", path=str(root)))

    package = _load_control_file(root, PACKAGE_FILE, findings) if root.is_dir() else None
    manifest = _load_control_file(root, MANIFEST_FILE, findings) if root.is_dir() else None
    receipt = _load_control_file(root, RECEIPT_FILE, findings) if root.is_dir() else None
    validator = _SchemaValidator()
    for value, declared, path in (
        (package, "bbk.artifact-package.v1", PACKAGE_FILE),
        (manifest, "bbk.artifact-package-manifest.v1", MANIFEST_FILE),
        (receipt, "bbk.artifact-package-seal-receipt.v1", RECEIPT_FILE),
    ):
        if isinstance(value, dict):
            for item in validator.validate(value, declared):
                item["path"] = path
                findings.append(item)

    entries: list[Mapping[str, Any]] = []
    if isinstance(manifest, dict) and isinstance(manifest.get("artifacts"), list):
        entries = [item for item in manifest["artifacts"] if isinstance(item, dict)]
    else:
        if manifest is not None:
            findings.append(finding("PACKAGE_MANIFEST_ARTIFACTS_INVALID", "Manifest artifacts must be an array.", path=MANIFEST_FILE, pointer="/artifacts"))

    expected_paths = set(GENERATED_FILES)
    ids: set[str] = set()
    graph: dict[str, list[str]] = {}
    for index, entry in enumerate(entries):
        artifact_id = entry.get("artifactId")
        raw_path = entry.get("path")
        if not isinstance(artifact_id, str) or artifact_id in ids:
            findings.append(finding("PACKAGE_MANIFEST_ARTIFACT_ID_INVALID", "Manifest artifact IDs must be unique strings.", path=MANIFEST_FILE, pointer=f"/artifacts/{index}/artifactId"))
            continue
        ids.add(artifact_id)
        refs = entry.get("references") if isinstance(entry.get("references"), list) else []
        graph[artifact_id] = [str(item) for item in refs]
        if not isinstance(raw_path, str):
            findings.append(finding("PACKAGE_MANIFEST_PATH_INVALID", "Manifest artifact path must be a string.", path=MANIFEST_FILE, pointer=f"/artifacts/{index}/path"))
            continue
        expected_paths.add(raw_path)
        try:
            path = resolve_local_path(root, raw_path, must_exist=True)
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"artifact is not a regular physical file: {raw_path}")
            raw = path.read_bytes()
            if entry.get("bytes") != len(raw):
                findings.append(finding("PACKAGE_ARTIFACT_BYTES_MISMATCH", f"Byte length mismatch for {raw_path}.", path=raw_path, details={"expected": entry.get("bytes"), "actual": len(raw)}))
            actual_sha = sha256_bytes(raw)
            if entry.get("sha256") != actual_sha:
                findings.append(finding("PACKAGE_ARTIFACT_DIGEST_MISMATCH", f"SHA-256 mismatch for {raw_path}.", path=raw_path, details={"expected": entry.get("sha256"), "actual": actual_sha}))
            canonicalization = entry.get("canonicalization")
            if canonicalization == BBK_JSON_1:
                value = loads_bytes(raw, source=str(path))
                expected = canonical_json_bytes(value)
                if raw != expected:
                    findings.append(finding(
                        "PACKAGE_ARTIFACT_NONCANONICAL",
                        f"JSON artifact {raw_path} is not stored as exact BBK-JSON-1 bytes.",
                        path=raw_path,
                        remediation="Restore the exact sealed bytes; verification is read-only and will not normalize the artifact.",
                    ))
                declared = entry.get("schema")
                if isinstance(value, dict) and isinstance(declared, str):
                    if value.get("schema") != declared:
                        findings.append(finding("PACKAGE_DECLARED_SCHEMA_MISMATCH", f"Artifact {raw_path} schema does not match its manifest declaration.", path=raw_path, pointer="/schema"))
                    for item in validator.validate(value, declared):
                        item["path"] = raw_path
                        findings.append(item)
            elif canonicalization != "UNCHANGED":
                findings.append(finding("PACKAGE_CANONICALIZATION_INVALID", f"Unknown canonicalization label {canonicalization!r}.", path=MANIFEST_FILE, pointer=f"/artifacts/{index}/canonicalization"))
        except StrictJsonError as exc:
            diag = exc.as_dict()
            findings.append(finding(diag.get("code", "PACKAGE_ARTIFACT_JSON_INVALID"), diag.get("message", "Artifact JSON is invalid."), path=raw_path, pointer=diag.get("pointer", ""), remediation="Restore the exact valid sealed artifact bytes."))
        except (ValueError, OSError) as exc:
            findings.append(finding("PACKAGE_ARTIFACT_PATH_INVALID", str(exc), path=raw_path, remediation="Restore the exact package artifact at the declared local path."))

    for source, targets in graph.items():
        for target in targets:
            if target not in ids:
                findings.append(finding("PACKAGE_REFERENCE_UNRESOLVED", f"Artifact {source!r} references unknown artifact {target!r}.", path=MANIFEST_FILE, details={"from": source, "to": target}))
    if isinstance(manifest, dict):
        recorded_graph = manifest.get("referenceGraph")
        recomputed_graph = _reference_graph(entries)
        if recorded_graph != recomputed_graph:
            findings.append(finding("PACKAGE_REFERENCE_GRAPH_MISMATCH", "Manifest referenceGraph does not equal the artifact declarations.", path=MANIFEST_FILE, pointer="/referenceGraph"))
        closure = manifest.get("closure") if isinstance(manifest.get("closure"), dict) else {}
        expected_closure = {"artifactCount": len(entries), "referenceCount": len(recomputed_graph), "unresolved": []}
        if closure != expected_closure:
            findings.append(finding("PACKAGE_CLOSURE_MISMATCH", "Manifest closure summary is not exact.", path=MANIFEST_FILE, pointer="/closure", details={"expected": expected_closure, "actual": closure}))

    if root.is_dir():
        actual_files: set[str] = set()
        for path in root.rglob("*"):
            if path.is_symlink():
                findings.append(finding("PACKAGE_SYMLINK_FORBIDDEN", "Sealed packages may not contain symbolic links.", path=path.relative_to(root).as_posix()))
            elif path.is_file():
                actual_files.add(path.relative_to(root).as_posix())
        extra = sorted(actual_files - expected_paths)
        missing = sorted(expected_paths - actual_files)
        for path in extra:
            findings.append(finding("PACKAGE_UNDECLARED_FILE", "Sealed package contains an undeclared file.", path=path, remediation="Use an exact package produced by seal; do not add files in place."))
        for path in missing:
            findings.append(finding("PACKAGE_DECLARED_FILE_MISSING", "Sealed package is missing a declared file.", path=path, remediation="Restore the exact complete package or create a successor; do not repair in place."))

    if isinstance(package, dict) and isinstance(manifest, dict):
        comparable_fields = ("packageId", "revision", "profile", "subject", "predecessor", "artifacts", "contentSha256", "canonicalization")
        for name in comparable_fields:
            if package.get(name) != manifest.get(name):
                findings.append(finding("PACKAGE_CONTROL_MISMATCH", f"Package descriptor and manifest differ at {name!r}.", path=PACKAGE_FILE, pointer=f"/{name}"))
        _, content_sha = _content_identity(manifest, entries, _reference_graph(entries))
        if manifest.get("contentSha256") != content_sha:
            findings.append(finding("PACKAGE_CONTENT_DIGEST_MISMATCH", "Manifest contentSha256 does not match recomputed package identity.", path=MANIFEST_FILE, pointer="/contentSha256", details={"expected": manifest.get("contentSha256"), "actual": content_sha}))
        if package.get("contentSha256") != content_sha:
            findings.append(finding("PACKAGE_CONTENT_DIGEST_MISMATCH", "Package descriptor contentSha256 does not match recomputed package identity.", path=PACKAGE_FILE, pointer="/contentSha256", details={"expected": package.get("contentSha256"), "actual": content_sha}))
    else:
        content_sha = None

    manifest_sha = None
    if isinstance(manifest, dict) and (root / MANIFEST_FILE).is_file():
        manifest_sha = sha256_file(root / MANIFEST_FILE)
    if isinstance(receipt, dict):
        if manifest_sha is not None and receipt.get("manifestSha256") != manifest_sha:
            findings.append(finding("PACKAGE_RECEIPT_MANIFEST_DIGEST_MISMATCH", "Seal receipt manifestSha256 does not match exact manifest bytes.", path=RECEIPT_FILE, pointer="/manifestSha256"))
        if isinstance(manifest, dict):
            for name in ("packageId", "revision", "contentSha256"):
                if receipt.get(name) != manifest.get(name):
                    findings.append(finding("PACKAGE_RECEIPT_IDENTITY_MISMATCH", f"Seal receipt differs from manifest at {name!r}.", path=RECEIPT_FILE, pointer=f"/{name}"))

    # Validate the selected profile and its artifact graph policy without
    # treating recursive schema refs as graph edges.
    if isinstance(manifest, dict):
        try:
            registry = load_profile_registry(registry_path)
            profile = select_profile(registry, manifest.get("profile"))
            if profile is None:
                findings.append(finding("PACKAGE_PROFILE_UNKNOWN", "Sealed package profile is not present in the registry.", path=MANIFEST_FILE, pointer="/profile", classification="SEMANTIC_OWNER_REQUIRED"))
            elif profile.get("artifactReferenceCycles") == "FORBIDDEN":
                cycle = _detect_cycle(graph)
                if cycle:
                    findings.append(finding("PACKAGE_ARTIFACT_REFERENCE_CYCLE", "Artifact reference cycle is forbidden by the selected profile.", path=MANIFEST_FILE, pointer="/referenceGraph", details={"cycle": cycle}))
        except (StrictJsonError, ValueError, OSError) as exc:
            findings.append(finding("PACKAGE_PROFILE_REGISTRY_INVALID", str(exc), classification="SEMANTIC_OWNER_REQUIRED", remediation="Restore the canonical profile registry before relying on package verification."))

    after: dict[str, tuple[int, int]] = {}
    if root.exists() and root.is_dir():
        for path in root.rglob("*"):
            with contextlib.suppress(OSError):
                stat_result = path.lstat()
                after[path.relative_to(root).as_posix()] = (stat_result.st_mtime_ns, stat_result.st_size)
    if before != after:
        findings.append(finding(
            "PACKAGE_VERIFY_MUTATED_SUBJECT",
            "Read-only verification observed a package metadata or file-set change during verification.",
            path=str(root),
            classification="AUTHORITY_REQUIRED",
            remediation="Stop concurrent mutation and verify an immutable exact package copy.",
        ))

    errors = sum(1 for item in findings if item.get("severity", "ERROR") == "ERROR")
    status = "PASS" if errors == 0 else "REJECTED"
    return {
        "schema": schema,
        "status": status,
        "sealedRoot": str(root),
        "packageId": manifest.get("packageId") if isinstance(manifest, dict) else None,
        "revision": manifest.get("revision") if isinstance(manifest, dict) else None,
        "profile": manifest.get("profile") if isinstance(manifest, dict) else None,
        "contentSha256": manifest.get("contentSha256") if isinstance(manifest, dict) else None,
        "manifestSha256": manifest_sha,
        "findings": findings,
        "summary": {"errors": errors, "artifacts": len(entries), "references": sum(len(v) for v in graph.values())},
        "readOnly": before == after,
        "authorityBoundary": AUTHORITY_BOUNDARY,
        "smallest_next_action": (
            "Use the verified exact package only within the authority of its intended consumer."
            if status == "PASS"
            else (findings[0].get("remediation") if findings else "Restore the exact sealed package and rerun verification.")
        ),
        "claims_not_established": [
            "semantic acceptance",
            "authorization",
            "independent review",
            "release readiness",
        ],
    }


def _remove_json_pointer(value: Any, pointer: str) -> None:
    if not pointer.startswith("/"):
        return
    tokens = [token.replace("~1", "/").replace("~0", "~") for token in pointer[1:].split("/")]
    current = value
    for token in tokens[:-1]:
        if isinstance(current, dict):
            current = current.get(token)
        elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
            current = current[int(token)]
        else:
            return
    if not tokens:
        return
    last = tokens[-1]
    if isinstance(current, dict):
        current.pop(last, None)
    elif isinstance(current, list) and last.isdigit() and int(last) < len(current):
        del current[int(last)]


def create_successor(
    sealed_root: Path | str,
    output_root: Path | str,
    *,
    revision: str,
    reason: str,
    registry_path: Path | None = None,
    recover_stale_lock: bool = False,
) -> dict[str, Any]:
    """Create a new mutable draft from an immutable verified predecessor."""
    source = Path(sealed_root).expanduser().resolve(strict=True)
    output = Path(output_root).expanduser().absolute()
    output_parent = output.parent.resolve(strict=True)
    output = output_parent / output.name
    schema = "bbk.artifact-package-successor-result.v1"
    if not isinstance(revision, str) or not revision.strip():
        raise ArtifactPackageError(_operation_error(schema, "PACKAGE_SUCCESSOR_REVISION_INVALID", "Successor revision must be a non-empty semantic revision string.", path=str(output), remediation="Provide the new semantic revision explicitly."))
    if not isinstance(reason, str) or not reason.strip():
        raise ArtifactPackageError(_operation_error(schema, "PACKAGE_SUCCESSOR_REASON_INVALID", "Successor reason must be non-empty.", path=str(output), remediation="Record the bounded reason for creating the successor."))
    verification = verify_package(source, registry_path=registry_path)
    if verification["status"] != "PASS":
        raise ArtifactPackageError({
            "schema": schema,
            "status": "REJECTED",
            "code": "PACKAGE_PREDECESSOR_VERIFY_FAILED",
            "message": "Successor creation requires an exact verified predecessor.",
            "predecessor": str(source),
            "verification": verification,
            "smallest_next_action": verification.get("smallest_next_action"),
            "claims_not_established": verification.get("claims_not_established", []),
        })
    package = load_path(source / PACKAGE_FILE)
    assert isinstance(package, dict)
    if revision == package.get("revision"):
        raise ArtifactPackageError(_operation_error(schema, "PACKAGE_SUCCESSOR_REVISION_UNCHANGED", "Successor revision must differ from the sealed predecessor revision.", path=str(output), remediation="Choose the next semantic revision while preserving packageId."))
    if output.exists() or output.is_symlink():
        raise ArtifactPackageError(_operation_error(schema, "PACKAGE_TARGET_EXISTS", "Successor creation refuses to overwrite an existing path.", path=str(output), remediation="Choose a new absent draft directory."))
    lock = output_parent / f".{output.name}.bbk-successor.lock"
    stage = output_parent / f".{output.name}.bbk-successor-stage-{uuid.uuid4().hex}"
    try:
        with _exclusive_lock(lock, operation="successor", target=output, recover_stale=recover_stale_lock):
            if output.exists() or output.is_symlink():
                raise ArtifactPackageError(_operation_error(schema, "PACKAGE_TARGET_EXISTS", "Successor target appeared while acquiring the lock.", path=str(output), remediation="Choose a new absent draft directory."))
            stage.mkdir(mode=0o700)
            registry = load_profile_registry(registry_path)
            profile = select_profile(registry, package.get("profile")) or {}
            clear_pointers = profile.get("successorClearPointers") if isinstance(profile.get("successorClearPointers"), list) else []
            draft_artifacts: list[dict[str, Any]] = []
            for entry in package.get("artifacts", []):
                if not isinstance(entry, dict):
                    continue
                raw_path = str(entry["path"])
                source_path = resolve_local_path(source, raw_path, must_exist=True)
                destination = resolve_local_path(stage, raw_path, must_exist=False)
                destination.parent.mkdir(parents=True, exist_ok=True)
                raw = source_path.read_bytes()
                if entry.get("canonicalization") == BBK_JSON_1:
                    value = loads_bytes(raw, source=str(source_path))
                    for pointer in clear_pointers:
                        if isinstance(pointer, str):
                            _remove_json_pointer(value, pointer)
                    raw = canonical_json_bytes(value)
                atomic_write(destination, raw, mode=stat.S_IMODE(source_path.stat().st_mode))
                draft_artifacts.append({
                    "artifactId": entry["artifactId"],
                    "path": raw_path,
                    "schema": entry.get("schema"),
                    "role": entry["role"],
                    "references": list(entry.get("references") or []),
                    **({"mediaType": entry.get("mediaType")} if entry.get("mediaType") is not None else {}),
                })
            descriptor = {
                "schema": "bbk.artifact-package-draft.v1",
                "packageId": package["packageId"],
                "revision": revision,
                "profile": package["profile"],
                "subject": package["subject"],
                "predecessor": {
                    "packageId": package["packageId"],
                    "revision": package["revision"],
                    "contentSha256": package["contentSha256"],
                    "source": str(source),
                },
                "successorReason": reason,
                "artifacts": draft_artifacts,
                "metadata": package.get("metadata", {}),
            }
            atomic_write(stage / DRAFT_FILE, canonical_json_bytes(descriptor))
            _fsync_dir(stage)
            _atomic_publish_noreplace(stage, output)
            stage = Path()
            return {
                "schema": schema,
                "status": "PASS",
                "predecessorRoot": str(source),
                "outputRoot": str(output),
                "packageId": package["packageId"],
                "revision": revision,
                "predecessor": descriptor["predecessor"],
                "clearedPointers": clear_pointers,
                "smallest_next_action": "Complete any successor attempt-owned fields, run preflight, and seal to a new absent output when ready.",
                "claims_not_established": [
                    "successor preflight pass",
                    "semantic acceptance",
                    "authorization",
                    "release readiness",
                ],
            }
    except ArtifactPackageError:
        raise
    except Exception as exc:
        raise ArtifactPackageError(_operation_error(
            schema,
            "PACKAGE_SUCCESSOR_FAILED",
            f"Successor creation failed before publication: {exc}",
            path=str(output),
            remediation="Repair the exact predecessor/output defect and rerun to a new absent draft directory.",
        )) from exc
    finally:
        if stage and str(stage) not in {".", ""} and stage.exists():
            shutil.rmtree(stage, ignore_errors=True)


# ---------------------------------------------------------------------------
# Legacy artifact-manifest compatibility primitives
# ---------------------------------------------------------------------------


def build_legacy_manifest(
    root: Path,
    paths: Sequence[Path],
    *,
    subject: str | None,
    root_label: str,
    bbk_version: str,
) -> dict[str, Any]:
    physical_root = root.resolve(strict=True)
    files = [file_reference(path, root=physical_root) for path in paths]
    files.sort(key=lambda item: item["path"])
    content = {
        "schema": "bbk.artifact-manifest-content.v1",
        "subject": subject,
        "root_label": root_label,
        "files": files,
    }
    return {
        "schema": "bbk.artifact-manifest.v1",
        "bbk_version": bbk_version,
        "subject": subject,
        "root_label": root_label,
        "content_sha256": sha256_bytes(identity_json_bytes(content)),
        "file_count": len(files),
        "total_bytes": sum(int(item["bytes"]) for item in files),
        "files": files,
    }


def verify_legacy_manifest(manifest: Mapping[str, Any], *, root: Path) -> dict[str, Any]:
    errors: list[str] = []
    if manifest.get("schema") != "bbk.artifact-manifest.v1":
        errors.append("not a bbk.artifact-manifest.v1 object")
    files = manifest.get("files")
    if not isinstance(files, list):
        files = []
        errors.append("manifest.files must be an array")
    rebuilt: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(files):
        if not isinstance(item, dict):
            errors.append(f"files[{index}] must be an object")
            continue
        raw = item.get("path")
        if not isinstance(raw, str) or not raw:
            errors.append(f"files[{index}].path must be a non-empty string")
            continue
        if raw in seen:
            errors.append(f"duplicate manifest path: {raw}")
            continue
        seen.add(raw)
        try:
            path = resolve_local_path(root, raw, must_exist=True)
            reference = file_reference(path, root=root)
            rebuilt.append(reference)
            for error in verify_file_reference(item, root=root):
                if error.startswith("SHA-256 mismatch for "):
                    errors.append(error.replace("SHA-256 mismatch for ", "artifact digest changed for ", 1))
                elif error.startswith("byte length mismatch for "):
                    errors.append(error.replace("byte length mismatch for ", "artifact byte count changed for ", 1))
                else:
                    errors.append(error)
        except (ValueError, OSError) as exc:
            errors.append(str(exc))
    rebuilt.sort(key=lambda item: item["path"])
    content = {
        "schema": "bbk.artifact-manifest-content.v1",
        "subject": manifest.get("subject"),
        "root_label": manifest.get("root_label"),
        "files": rebuilt,
    }
    digest = sha256_bytes(identity_json_bytes(content))
    if manifest.get("content_sha256") != digest:
        errors.append(f"content_sha256 mismatch: expected {manifest.get('content_sha256')}, got {digest}")
    if manifest.get("file_count") != len(rebuilt):
        errors.append(f"file_count mismatch: expected {manifest.get('file_count')}, got {len(rebuilt)}")
    total = sum(int(item["bytes"]) for item in rebuilt)
    if manifest.get("total_bytes") != total:
        errors.append(f"total_bytes mismatch: expected {manifest.get('total_bytes')}, got {total}")
    return {
        "schema": "bbk.artifact-manifest-verification.v1",
        "status": "PASS" if not errors else "FAIL",
        "valid": not errors,
        "errors": errors,
        "file_count": len(rebuilt),
        "total_bytes": total,
        "content_sha256": digest,
    }


def _human(value: Mapping[str, Any]) -> str:
    schema = value.get("schema")
    status = value.get("status")
    if schema == "bbk.artifact-package-preflight.v1":
        lines = [f"Artifact package preflight: {status}", f"Draft: {value.get('draftRoot')}"]
        lines.extend(f"[{item.get('classification')}] {item.get('code')}: {item.get('message')} ({item.get('path') or item.get('pointer')})" for item in value.get("findings", []))
        lines.append(f"Next: {value.get('smallest_next_action')}")
        return "\n".join(lines)
    if schema in {"bbk.artifact-package-verification.v1", "bbk.artifact-package-seal-result.v1", "bbk.artifact-package-successor-result.v1"}:
        lines = [f"{schema}: {status}"]
        for key in ("draftRoot", "sealedRoot", "predecessorRoot", "outputRoot", "packageId", "revision", "contentSha256"):
            if value.get(key) is not None:
                lines.append(f"{key}: {value.get(key)}")
        for item in value.get("findings", []):
            lines.append(f"[{item.get('classification')}] {item.get('code')}: {item.get('message')} ({item.get('path') or item.get('pointer')})")
        lines.append(f"Next: {value.get('smallest_next_action')}")
        return "\n".join(lines)
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="bbk-artifact", description=__doc__)
    p.add_argument("--json", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)
    x = sub.add_parser("preflight"); x.add_argument("draft_root"); x.add_argument("--registry"); x.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH)
    x = sub.add_parser("seal"); x.add_argument("draft_root"); x.add_argument("--output", required=True); x.add_argument("--registry"); x.add_argument("--recover-stale-lock", action="store_true")
    x = sub.add_parser("verify"); x.add_argument("sealed_root"); x.add_argument("--registry")
    x = sub.add_parser("successor"); x.add_argument("sealed_root"); x.add_argument("--output", required=True); x.add_argument("--revision", required=True); x.add_argument("--reason", required=True); x.add_argument("--registry"); x.add_argument("--recover-stale-lock", action="store_true")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    registry = Path(args.registry).expanduser().resolve() if getattr(args, "registry", None) else None
    try:
        if args.command == "preflight":
            value = preflight_draft(args.draft_root, registry_path=registry, max_depth=args.max_depth)
        elif args.command == "seal":
            value = seal_draft(args.draft_root, args.output, registry_path=registry, recover_stale_lock=args.recover_stale_lock)
        elif args.command == "verify":
            value = verify_package(args.sealed_root, registry_path=registry)
        else:
            value = create_successor(args.sealed_root, args.output, revision=args.revision, reason=args.reason, registry_path=registry, recover_stale_lock=args.recover_stale_lock)
    except ArtifactPackageError as exc:
        value = exc.as_dict()
    print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) if args.json else _human(value))
    return 0 if value.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
