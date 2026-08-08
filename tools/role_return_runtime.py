#!/usr/bin/env python3
"""Build, validate, and admit exact BBK structured role returns.

The runtime gives governed OMP children a schema-aware construction tool and
enforces the same role-specific Draft 2020-12 contract at the hidden ``yield``
boundary. A prepared return is immutable, content addressed, and bound to the
active invocation. The child submits the complete prepared yield input; the
qualified host hook independently revalidates it before acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from gate_kernel import canonical_digest, canonical_json_bytes
    from governed_state import GovernanceStateError, append_receipt, resolve_binding, utc_now
    from omp_binding_registry import OmpBindingError, binding_execution_policy, resolve_binding_reference
    from return_contracts import load_package, load_role
except ImportError:  # pragma: no cover - installed-package import fallback
    from .gate_kernel import canonical_digest, canonical_json_bytes
    from .governed_state import GovernanceStateError, append_receipt, resolve_binding, utc_now
    from .omp_binding_registry import OmpBindingError, binding_execution_policy, resolve_binding_reference
    from .return_contracts import load_package, load_role

ROOT = Path(__file__).resolve().parents[1]
RETURN_REF_RE = re.compile(r"^return:[0-9a-f]{64}$")
DIGEST_RE = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")
PREPARE_SCHEMA = "bbk.role-return-prepare.v1"
VALIDATE_SCHEMA = "bbk.role-return-validate.v1"
RESOLVE_SCHEMA = "bbk.role-return-resolve.v1"
TEMPLATE_SCHEMA = "bbk.role-return-template-query.v1"
TOKEN_SCHEMA = "bbk.prepared-role-return.v1"


def _validator_runtime_available() -> bool:
    try:
        import jsonschema  # noqa: F401
        import referencing  # noqa: F401
        return True
    except ImportError:
        return False


def _validator_python_candidates(project_root: str | Path) -> list[Path]:
    """Return bounded managed-validator interpreters in deterministic order."""
    roots: list[Path] = []
    explicit_python = os.environ.get("BBK_JSONSCHEMA_PYTHON")
    if explicit_python:
        roots.append(Path(explicit_python).expanduser())
    for name in ("BBK_JSONSCHEMA_TOOL_DIR", "BBK_SCHEMA_TOOL_DIR"):
        value = os.environ.get(name)
        if value:
            roots.append(Path(value).expanduser())
    if value := os.environ.get("BBK_TOOL_ROOT"):
        roots.append(Path(value).expanduser() / "jsonschema-4.25.1")
    project = Path(project_root).expanduser()
    roots.append(project / ".bbk" / "tooling" / "jsonschema-4.25.1")
    roots.append(Path.home() / ".cache" / "bbk" / "tooling" / "jsonschema-4.25.1")

    candidates: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        values = [root] if root.suffix.lower() in {".exe", ".bin"} or root.name.startswith("python") else [
            root / "Scripts" / "python.exe",
            root / "bin" / "python",
            root / "python.exe",
            root / "python",
        ]
        for candidate in values:
            key = os.path.normcase(os.path.abspath(str(candidate)))
            if key not in seen:
                candidates.append(candidate)
                seen.add(key)
    return candidates


def _maybe_reexec_managed_validator(project_root: str | Path) -> None:
    """Re-exec under BBK's managed jsonschema environment when needed.

    The hidden-yield hook must never silently skip Draft 2020-12 validation.
    Re-exec preserves the original argv and emits the same structured result to
    the JavaScript bridge.  A guard prevents recursive delegation.
    """
    if _validator_runtime_available() or os.environ.get("BBK_ROLE_RETURN_RUNTIME_REEXEC") == "1":
        return
    current = Path(sys.executable).resolve()
    for candidate in _validator_python_candidates(project_root):
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            continue
        if resolved == current or not resolved.is_file():
            continue
        environment = dict(os.environ)
        environment.update({
            "BBK_ROLE_RETURN_RUNTIME_REEXEC": "1",
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        })
        argv = [str(resolved), "-X", "utf8", str(Path(__file__).resolve()), *sys.argv[1:]]
        try:
            os.execve(str(resolved), argv, environment)
        except OSError:
            continue


class RoleReturnRuntimeError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        smallest_next_action: str = "Use bbk_return_template, repair only the reported fields, and retry in the same attempt.",
        diagnostics: Sequence[Mapping[str, Any]] | None = None,
    ) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.smallest_next_action = smallest_next_action
        self.diagnostics = [dict(item) for item in diagnostics or []]


def _text(value: Any, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise RoleReturnRuntimeError("ROLE_RETURN_REQUEST_INVALID", f"{field} must be a non-empty string")
    return value.strip() if not allow_empty else value


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise RoleReturnRuntimeError("ROLE_RETURN_REQUEST_INVALID", f"{field} must be a JSON object")
    return dict(value)


def _list(value: Any, field: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise RoleReturnRuntimeError("ROLE_RETURN_REQUEST_INVALID", f"{field} must be a JSON array")
    return list(value)


def _load_request(value: str) -> dict[str, Any]:
    try:
        if value == "-":
            result = json.load(sys.stdin)
        else:
            path = Path(value)
            result = json.loads(path.read_text(encoding="utf-8")) if path.exists() else json.loads(value)
    except (OSError, json.JSONDecodeError) as exc:
        raise RoleReturnRuntimeError("ROLE_RETURN_REQUEST_INVALID_JSON", str(exc)) from exc
    if not isinstance(result, dict):
        raise RoleReturnRuntimeError("ROLE_RETURN_REQUEST_INVALID", "request must be a JSON object")
    return result


def _package_root(root: str | Path | None) -> Path:
    candidate = Path(root or os.environ.get("BBK_PACKAGE_ROOT") or ROOT).resolve()
    if not (candidate / "spec" / "roles" / "catalog.json").is_file():
        raise RoleReturnRuntimeError(
            "ROLE_RETURN_PACKAGE_ROOT_INVALID",
            f"{candidate} does not contain the canonical BBK role package",
            smallest_next_action="Use the exact installed RC package root and retry.",
        )
    return candidate


def _project_root(root: str | Path) -> Path:
    raw = Path(root).expanduser()
    if raw.is_symlink():
        raise RoleReturnRuntimeError("ROLE_RETURN_PROJECT_ROOT_INVALID", f"project root must not be a symlink: {raw}")
    try:
        candidate = raw.resolve(strict=True)
    except OSError as exc:
        raise RoleReturnRuntimeError("ROLE_RETURN_PROJECT_ROOT_INVALID", f"cannot resolve project root {raw}: {exc}") from exc
    if not candidate.is_dir():
        raise RoleReturnRuntimeError("ROLE_RETURN_PROJECT_ROOT_INVALID", f"unsafe project root {candidate}")
    return candidate


def _role_entry(role_name: str, package_root: Path) -> dict[str, Any]:
    catalog, _, entries = load_package(package_root)
    del catalog
    entry = entries.get(role_name)
    if not isinstance(entry, dict):
        raise RoleReturnRuntimeError("ROLE_RETURN_ROLE_UNKNOWN", f"unknown role {role_name!r}")
    return entry


def _validation_registry(package_root: Path):
    try:
        import jsonschema
        from referencing import Registry, Resource
    except ImportError as exc:  # pragma: no cover - exercised in installed-host tests
        raise RoleReturnRuntimeError(
            "ROLE_RETURN_VALIDATOR_UNAVAILABLE",
            f"Draft 2020-12 validator is unavailable: {exc}",
            smallest_next_action="Use the BBK-managed jsonschema environment and retry; do not bypass yield validation.",
        ) from exc
    resources: dict[str, Any] = {}
    origins: dict[str, str] = {}
    for schema_path in sorted((package_root / "spec" / "schemas").rglob("*.json"), key=lambda p: p.as_posix()):
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RoleReturnRuntimeError("ROLE_RETURN_SCHEMA_REGISTRY_INVALID", f"cannot load {schema_path}: {exc}") from exc
        if not isinstance(schema, dict):
            continue
        schema_id = schema.get("$id")
        if not isinstance(schema_id, str) or not schema_id:
            continue
        relative = schema_path.relative_to(package_root).as_posix()
        if schema_id in resources:
            raise RoleReturnRuntimeError(
                "ROLE_RETURN_SCHEMA_REGISTRY_DUPLICATE_ID",
                f"schema $id {schema_id!r} is declared by both {origins[schema_id]} and {relative}",
            )
        resources[schema_id] = schema
        origins[schema_id] = relative
    registry = Registry()
    for schema_id in sorted(resources):
        registry = registry.with_resource(schema_id, Resource.from_contents(resources[schema_id]))
    return jsonschema, registry, resources, origins


def _pointer(parts: Iterable[Any]) -> str:
    encoded = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(encoded) if encoded else ""


def validate_surface(value: Any, schema_name: str, package_root: Path, *, code: str) -> dict[str, Any]:
    """Validate an internal/tool surface before it crosses its format boundary."""
    schema_path = package_root / "spec" / "schemas" / schema_name
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RoleReturnRuntimeError("ROLE_RETURN_SCHEMA_UNAVAILABLE", f"cannot load {schema_name}: {exc}") from exc
    jsonschema, registry, _resources, _origins = _validation_registry(package_root)
    validator = jsonschema.Draft202012Validator(schema, registry=registry)
    errors = sorted(validator.iter_errors(value), key=lambda item: (list(item.absolute_path), item.message))
    if errors:
        diagnostics = [
            {
                "instance_pointer": _pointer(error.absolute_path),
                "schema_pointer": _pointer(error.absolute_schema_path),
                "validator": str(error.validator),
                "message": error.message,
            }
            for error in errors[:40]
        ]
        raise RoleReturnRuntimeError(
            code,
            f"surface failed {len(errors)} schema assertion(s) against {schema_name}",
            diagnostics=diagnostics,
        )
    return {"schema_path": f"spec/schemas/{schema_name}", "value_digest": f"sha256:{canonical_digest(value)}"}


def validate_role_return(document: Any, role_name: str, package_root: Path) -> dict[str, Any]:
    role = load_role(role_name, package_root)
    contract = role["return_contract"]
    schema_name = contract["v2_return_schema"] if isinstance(document, dict) and document.get("schema") == "bbk.role-return.v2" else contract["return_schema"]
    schema_path = package_root / schema_name
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RoleReturnRuntimeError("ROLE_RETURN_SCHEMA_UNAVAILABLE", f"cannot load {schema_name}: {exc}") from exc
    jsonschema, registry, _resources, _origins = _validation_registry(package_root)
    validator = jsonschema.Draft202012Validator(schema, registry=registry)
    errors = sorted(validator.iter_errors(document), key=lambda item: (list(item.absolute_path), item.message))
    diagnostics = [
        {
            "instance_pointer": _pointer(error.absolute_path),
            "schema_pointer": _pointer(error.absolute_schema_path),
            "validator": str(error.validator),
            "message": error.message,
        }
        for error in errors[:40]
    ]
    if errors:
        raise RoleReturnRuntimeError(
            "BBK_ROLE_RETURN_SCHEMA_INVALID",
            f"{role_name} return failed {len(errors)} schema assertion(s) against {schema_name}",
            diagnostics=diagnostics,
        )
    return {
        "status": "PASS",
        "role": role_name,
        "contract": contract["v2_contract_id"] if document.get("schema") == "bbk.role-return.v2" else contract["contract_id"],
        "schema_path": schema_name,
        "schema_id": schema.get("$id"),
        "document_digest": f"sha256:{canonical_digest(document)}",
        "diagnostics": [],
    }


def _binding_context(project_root: Path, request: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    session_id = _text(request.get("session_id"), "session_id")
    binding_ref = _text(request.get("binding_ref"), "binding_ref")
    invocation_id = _text(request.get("invocation_id"), "invocation_id")
    policy = binding_execution_policy(project_root, session_id=session_id)
    if policy.get("binding_ref") != binding_ref:
        raise RoleReturnRuntimeError("ROLE_RETURN_BINDING_MISMATCH", "binding_ref is not the active binding for this session")
    if policy.get("invocation_id") != invocation_id:
        raise RoleReturnRuntimeError("ROLE_RETURN_INVOCATION_MISMATCH", "invocation_id differs from the active binding")
    binding = resolve_binding_reference(project_root, binding_ref)
    if not binding:
        raise RoleReturnRuntimeError("ROLE_RETURN_BINDING_NOT_FOUND", f"active binding {binding_ref} does not exist")
    parent = None
    parent_session = binding.get("request", {}).get("parent_session_id")
    if isinstance(parent_session, str) and parent_session:
        parent = resolve_binding(project_root, session_id=parent_session)
    return policy, binding, parent


def _select_parent(role_name: str, binding: Mapping[str, Any], parent: Mapping[str, Any] | None, package_root: Path, requested_mode: Any) -> tuple[str, dict[str, Any]]:
    entry = _role_entry(role_name, package_root)
    modes = entry.get("allowed_parent_modes", [])
    request = binding.get("request", {})
    if parent is None:
        parent_kind = "controller"
        parent_id = "harness_root_controller"
        parent_role = None
        parent_invocation = str(request.get("invocation_id") or "controller-root")
    else:
        parent_kind = "canonical_role"
        parent_request = parent.get("request", {})
        parent_id = str(parent_request.get("role") or "")
        parent_role = parent_id
        parent_invocation = str(parent_request.get("invocation_id") or "")
    matches = [
        item for item in modes
        if item.get("parent_kind") == parent_kind and parent_id in item.get("parents", [])
    ]
    if requested_mode:
        requested = _text(requested_mode, "invocation_mode")
        matches = [item for item in matches if item.get("mode") == requested]
    if len(matches) != 1:
        available = sorted({str(item.get("mode")) for item in modes})
        raise RoleReturnRuntimeError(
            "ROLE_RETURN_PARENT_NOT_ALLOWED",
            f"active parent {parent_kind}:{parent_id} does not select exactly one allowed mode for {role_name}; available modes: {available}",
            smallest_next_action="Use a role-parent route declared by the generated contract; do not fabricate parent identity.",
        )
    mode = str(matches[0]["mode"])
    parent_ref: dict[str, Any] = {
        "kind": parent_kind,
        "id": parent_id,
        "role": parent_role,
        "invocation_mode": mode,
        "invocation_id": parent_invocation,
        "return_route": "omp-task-result" if parent else "harness-controller",
    }
    return mode, parent_ref



def _binding_diagnostic(pointer: str, message: str) -> dict[str, str]:
    return {
        "instance_pointer": pointer,
        "schema_pointer": "",
        "validator": "bbk_active_binding",
        "message": message,
    }


def validate_document_binding(
    document: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    binding: Mapping[str, Any],
    parent: Mapping[str, Any] | None,
    package_root: Path,
) -> dict[str, Any]:
    """Bind a schema-valid return to the exact active invocation identity.

    JSON Schema proves shape and controlled vocabulary.  This check proves that
    the shaped document is about the child that is actually yielding, rather
    than another work unit, attempt, parent, session, or authority.
    """
    role_name = str(policy.get("role") or "")
    request = binding.get("request") if isinstance(binding.get("request"), Mapping) else {}
    expected_mode, expected_parent = _select_parent(
        role_name,
        binding,
        parent,
        package_root,
        document.get("invocation_mode"),
    )
    expected_subject_id = str(request.get("work_unit_id") or policy.get("work_unit_id") or "")
    expected_revision = str(request.get("baseline_ref") or "unversioned")
    expected_attempt = str(policy.get("attempt_id") or request.get("attempt_id") or "")
    expected_semantic_run = str(request.get("semantic_run_id") or f"{expected_subject_id}:{expected_attempt}")
    expected_authority = str(request.get("authority_ref") or "authority:unspecified")
    expected_effects = sorted(str(item) for item in (request.get("scope") or {}).get("mutation_classes", []) if str(item))

    diagnostics: list[dict[str, str]] = []

    def same(pointer: str, observed: Any, expected: Any) -> None:
        if observed != expected:
            diagnostics.append(_binding_diagnostic(pointer, f"must equal active binding value {expected!r}; observed {observed!r}"))

    same("/role", document.get("role"), role_name)
    same("/invocation_mode", document.get("invocation_mode"), expected_mode)
    executor = document.get("executor") if isinstance(document.get("executor"), Mapping) else {}
    same("/executor/role", executor.get("role"), role_name)
    same("/executor/invocation_id", executor.get("invocation_id"), policy.get("invocation_id"))
    same("/executor/host_session_id", executor.get("host_session_id"), policy.get("session_id"))
    subject = document.get("subject_ref") if isinstance(document.get("subject_ref"), Mapping) else {}
    same("/subject_ref/id", subject.get("id"), expected_subject_id)
    same("/subject_ref/revision", str(subject.get("revision")), expected_revision)
    attempt = document.get("attempt_ref") if isinstance(document.get("attempt_ref"), Mapping) else {}
    same("/attempt_ref/semantic_run_id", attempt.get("semantic_run_id"), expected_semantic_run)
    same("/attempt_ref/physical_attempt_id", attempt.get("physical_attempt_id"), expected_attempt)
    same("/attempt_ref/host_session_id", attempt.get("host_session_id"), policy.get("session_id"))
    parent_ref = document.get("parent_ref") if isinstance(document.get("parent_ref"), Mapping) else {}
    for field in ("kind", "id", "role", "invocation_mode", "invocation_id", "return_route"):
        same(f"/parent_ref/{field}", parent_ref.get(field), expected_parent.get(field))
    authority = document.get("authority_and_effects_used") if isinstance(document.get("authority_and_effects_used"), Mapping) else {}
    authority_refs = authority.get("authority_refs") if isinstance(authority.get("authority_refs"), list) else []
    observed_authorities = [str(item.get("id")) for item in authority_refs if isinstance(item, Mapping) and item.get("id") is not None]
    if expected_authority not in observed_authorities:
        diagnostics.append(_binding_diagnostic(
            "/authority_and_effects_used/authority_refs",
            f"must include active authority_ref {expected_authority!r}",
        ))
    observed_effects = sorted(str(item) for item in authority.get("allowed_effect_classes", []) if str(item))
    if observed_effects != expected_effects:
        diagnostics.append(_binding_diagnostic(
            "/authority_and_effects_used/allowed_effect_classes",
            f"must equal active mutation-class fence {expected_effects!r}; observed {observed_effects!r}",
        ))
    if diagnostics:
        raise RoleReturnRuntimeError(
            "BBK_ROLE_RETURN_BINDING_INVALID",
            f"{role_name} return differs from the active immutable invocation in {len(diagnostics)} field(s)",
            diagnostics=diagnostics,
        )
    return {
        "status": "PASS",
        "binding_ref": str(policy.get("binding_ref") or ""),
        "identity_digest": f"sha256:{canonical_digest({
            'role': role_name,
            'mode': expected_mode,
            'subject': expected_subject_id,
            'revision': expected_revision,
            'attempt': expected_attempt,
            'semantic_run': expected_semantic_run,
            'session': policy.get('session_id'),
            'invocation': policy.get('invocation_id'),
            'parent': expected_parent,
            'authority': expected_authority,
            'allowed_effect_classes': expected_effects,
        })}",
    }


def _sample_for_field(name: str, field: Mapping[str, Any]) -> Any:
    kind = field.get("kind")
    if kind == "REFERENCE":
        return {"id": f"replace:{name}"}
    if kind == "REFERENCE_LIST":
        return [{"id": f"replace:{name}"}]
    if kind == "ARTIFACT_REFERENCE":
        return {"id": f"replace:{name}", "path": "replace/path", "bytes": 0, "sha256": "0" * 64}
    if kind == "ARTIFACT_REFERENCE_LIST":
        return [{"id": f"replace:{name}", "path": "replace/path", "bytes": 0, "sha256": "0" * 64}]
    if kind == "STRUCTURED":
        return {"status": "REPLACE_WITH_EXACT_FACTS"}
    if kind == "STRUCTURED_LIST":
        return [{"status": "REPLACE_WITH_EXACT_FACTS"}]
    if kind == "STRING":
        return "REPLACE_WITH_EXACT_VALUE"
    if kind == "STRING_LIST":
        return ["REPLACE_WITH_EXACT_VALUE"]
    if kind == "BOOLEAN":
        return False
    if kind in {"INTEGER", "NUMBER"}:
        return 0
    if kind == "ENUM":
        values = field.get("enum_values", [])
        return values[0] if values else "REPLACE_WITH_ALLOWED_VALUE"
    if kind == "ENUM_LIST":
        values = field.get("enum_values", [])
        return [values[0]] if values else ["REPLACE_WITH_ALLOWED_VALUE"]
    return None


def template(project_root: Path, package_root: Path, request: Mapping[str, Any]) -> dict[str, Any]:
    validate_surface(dict(request), "bbk-role-return-template-query-v1.schema.json", package_root, code="ROLE_RETURN_REQUEST_SCHEMA_INVALID")
    policy, binding, parent = _binding_context(project_root, request)
    role_name = str(policy.get("role") or "")
    role = load_role(role_name, package_root)
    contract = role["return_contract"]
    mode, parent_ref = _select_parent(role_name, binding, parent, package_root, request.get("invocation_mode"))
    compact = {
        name: _sample_for_field(name, contract["result_fields"][name])
        for name in contract["compact_result_fields"]
    }
    value = {
        "schema": "bbk.role-return-template.v1",
        "status": "PASS",
        "binding_ref": policy["binding_ref"],
        "invocation_id": policy["invocation_id"],
        "role": role_name,
        "contract": contract["v2_contract_id"],
        "return_schema": contract["v2_return_schema"],
        "invocation_mode": mode,
        "allowed_return_kinds": contract["allowed_return_kinds"],
        "allowed_operational_dispositions": contract["allowed_operational_dispositions"],
        "semantic_state": {
            "name": contract["semantic_state_name"],
            "allowed_values": contract["allowed_semantic_states"],
        },
        "parent_ref": parent_ref,
        "compact_result_fields": [
            {
                "name": name,
                **contract["result_fields"][name],
                "example": compact[name],
            }
            for name in contract["compact_result_fields"]
        ],
        "result_json_example": json.dumps(compact, ensure_ascii=False, separators=(",", ":")),
        "instruction": "Pass the role-specific result and optional evidence/effect sections as structured tool fields to bbk_return_prepare. JSON-string fields are compatibility-only. Do not hand-author the common envelope.",
    }
    validate_surface(value, "bbk-role-return-template-v1.schema.json", package_root, code="ROLE_RETURN_OUTPUT_SCHEMA_INVALID")
    return value


def _prepared_root(project_root: Path) -> Path:
    try:
        root = project_root.resolve(strict=True)
    except OSError as exc:
        raise RoleReturnRuntimeError("ROLE_RETURN_PROJECT_ROOT_INVALID", f"cannot resolve project root {project_root}: {exc}") from exc
    current = root
    for component in (".bbk", "governance", "role-returns"):
        current = current / component
        if current.is_symlink():
            raise RoleReturnRuntimeError("ROLE_RETURN_STATE_PATH_UNSAFE", f"prepared-return path component is a symlink: {current}")
        if current.exists():
            if not current.is_dir():
                raise RoleReturnRuntimeError("ROLE_RETURN_STATE_PATH_UNSAFE", f"prepared-return path component is not a directory: {current}")
        else:
            current.mkdir(mode=0o700)
    resolved = current.resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise RoleReturnRuntimeError("ROLE_RETURN_STATE_PATH_UNSAFE", f"prepared-return directory escapes project root: {resolved}")
    return resolved


def _write_exclusive(path: Path, value: Mapping[str, Any]) -> bool:
    payload = canonical_json_bytes(value) + b"\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError:
        if path.is_symlink():
            raise RoleReturnRuntimeError("ROLE_RETURN_STATE_PATH_UNSAFE", f"prepared-return record is a symlink: {path}")
        existing = path.read_bytes()
        if existing == payload:
            return False
        raise RoleReturnRuntimeError("ROLE_RETURN_IDEMPOTENCY_COLLISION", f"{path.name} exists with different immutable content")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return True


def _load_prepared(project_root: Path, return_ref: str) -> dict[str, Any]:
    if not RETURN_REF_RE.fullmatch(return_ref):
        raise RoleReturnRuntimeError("ROLE_RETURN_REF_INVALID", "return_ref must be return:<64 lowercase hex>")
    path = _prepared_root(project_root) / f"{return_ref.removeprefix('return:')}.json"
    if path.is_symlink():
        raise RoleReturnRuntimeError("ROLE_RETURN_STATE_PATH_UNSAFE", f"prepared-return record is a symlink: {path}")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RoleReturnRuntimeError("ROLE_RETURN_REF_NOT_FOUND", f"cannot resolve {return_ref}: {exc}") from exc
    if not isinstance(record, dict) or record.get("return_ref") != return_ref:
        raise RoleReturnRuntimeError("ROLE_RETURN_RECORD_INVALID", f"prepared return {return_ref} has invalid identity")
    stable = {key: value for key, value in record.items() if key != "record_digest"}
    if record.get("record_digest") != f"sha256:{canonical_digest(stable)}":
        raise RoleReturnRuntimeError("ROLE_RETURN_RECORD_TAMPERED", f"prepared return {return_ref} failed integrity validation")
    return record


def _prepared_for_document(
    project_root: Path,
    *,
    policy: Mapping[str, Any],
    document: Mapping[str, Any],
    document_digest: str,
) -> dict[str, Any]:
    """Resolve exactly one immutable prepared record for a complete yield document."""
    matches: list[dict[str, Any]] = []
    for path in sorted(_prepared_root(project_root).glob("*.json"), key=lambda item: item.name):
        if path.is_symlink():
            raise RoleReturnRuntimeError("ROLE_RETURN_STATE_PATH_UNSAFE", f"prepared-return record is a symlink: {path}")
        try:
            candidate = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RoleReturnRuntimeError("ROLE_RETURN_RECORD_INVALID", f"cannot load prepared-return record {path.name}: {exc}") from exc
        if not isinstance(candidate, dict):
            raise RoleReturnRuntimeError("ROLE_RETURN_RECORD_INVALID", f"prepared-return record {path.name} is not an object")
        if candidate.get("binding_ref") != policy.get("binding_ref"):
            continue
        if candidate.get("session_id") != policy.get("session_id") or candidate.get("invocation_id") != policy.get("invocation_id"):
            continue
        if candidate.get("role") != policy.get("role") or candidate.get("document_digest") != document_digest:
            continue
        ref = candidate.get("return_ref")
        if not isinstance(ref, str):
            raise RoleReturnRuntimeError("ROLE_RETURN_RECORD_INVALID", f"prepared-return record {path.name} lacks return_ref")
        verified = _load_prepared(project_root, ref)
        if canonical_json_bytes(verified.get("document")) != canonical_json_bytes(document):
            raise RoleReturnRuntimeError(
                "ROLE_RETURN_RECORD_TAMPERED",
                f"prepared return {ref} has the expected digest but different canonical document bytes",
            )
        matches.append(verified)
    if not matches:
        raise RoleReturnRuntimeError(
            "ROLE_RETURN_PREPARATION_REQUIRED",
            "the complete schema-valid return was not created by bbk_return_prepare for this active binding",
            smallest_next_action="Call bbk_return_prepare with the same role-specific facts, then invoke hidden yield with its exact complete yield_input in this same attempt.",
        )
    refs = {str(item.get("return_ref")) for item in matches}
    if len(refs) != 1:
        raise RoleReturnRuntimeError(
            "ROLE_RETURN_PREPARED_AMBIGUOUS",
            f"{len(refs)} immutable prepared records match the same bound return document",
            smallest_next_action="Preserve the records and repair the idempotency collision before yielding.",
        )
    return matches[0]


def prepare(project_root: Path, package_root: Path, request: Mapping[str, Any]) -> dict[str, Any]:
    validate_surface(dict(request), "bbk-role-return-prepare-v1.schema.json", package_root, code="ROLE_RETURN_REQUEST_SCHEMA_INVALID")
    policy, binding, parent = _binding_context(project_root, request)
    role_name = str(policy.get("role") or "")
    role = load_role(role_name, package_root)
    contract = role["return_contract"]
    mode, parent_ref = _select_parent(role_name, binding, parent, package_root, request.get("invocation_mode"))
    binding_request = binding.get("request", {})
    detail_level = str(request.get("detail_level") or "COMPACT").strip().upper()
    if detail_level not in {"COMPACT", "FULL"}:
        raise RoleReturnRuntimeError("ROLE_RETURN_REQUEST_INVALID", "detail_level must be COMPACT or FULL")
    return_kind = _text(request.get("return_kind"), "return_kind")
    disposition = _text(request.get("operational_disposition"), "operational_disposition")
    semantic_value = _text(request.get("semantic_state_value"), "semantic_state_value")
    next_action = _object(request.get("smallest_valid_next_action"), "smallest_valid_next_action")
    # Keep the direct runtime API as simple as the OMP tool surface.  The
    # extension supplies this field explicitly, while compatibility callers
    # may omit it and receive the conservative default.
    next_action.setdefault("unaffected_work_may_continue", False)
    result_value = _object(request.get("result"), "result")
    authority_refs = _list(request.get("authority_refs"), "authority_refs") or [{"id": str(binding_request.get("authority_ref") or "authority:unspecified")}]
    allowed_effects = _list(request.get("allowed_effect_classes"), "allowed_effect_classes")
    if not allowed_effects:
        allowed_effects = [str(item) for item in binding_request.get("scope", {}).get("mutation_classes", []) if str(item)]
    document: dict[str, Any] = {
        "schema": "bbk.role-return.v2",
        "contract": contract["v2_contract_id"],
        "role": role_name,
        "executor": {
            "role": role_name,
            "invocation_id": policy["invocation_id"],
            "host_session_id": policy["session_id"],
        },
        "invocation_mode": mode,
        "return_kind": return_kind,
        "detail_level": detail_level,
        "subject_ref": {
            "id": str(binding_request.get("work_unit_id") or policy.get("work_unit_id")),
            "revision": str(binding_request.get("baseline_ref") or "unversioned"),
        },
        "parent_ref": parent_ref,
        "attempt_ref": {
            "semantic_run_id": str(binding_request.get("semantic_run_id") or f"{policy.get('work_unit_id')}:{policy.get('attempt_id')}"),
            "physical_attempt_id": str(policy.get("attempt_id")),
            "host_session_id": policy["session_id"],
        },
        "operational_disposition": disposition,
        "semantic_state": {"name": contract["semantic_state_name"], "value": semantic_value},
        "summary": _text(request.get("summary"), "summary", allow_empty=True),
        "authority_and_effects_used": {
            "authority_refs": authority_refs,
            "allowed_effect_classes": [str(item) for item in allowed_effects],
            "effects_used": _list(request.get("effects_used"), "effects_used"),
            "denied_or_uncovered_effects": _list(request.get("denied_or_uncovered_effects"), "denied_or_uncovered_effects"),
            "violations_or_ambiguities": _list(request.get("violations_or_ambiguities"), "violations_or_ambiguities"),
        },
        "result": result_value,
        "smallest_valid_next_action": next_action,
    }
    optional = {
        "outputs": request.get("outputs"),
        "checks_and_evidence": request.get("checks_and_evidence"),
        "effects_and_cleanup": request.get("effects_and_cleanup"),
        "blockers_and_residuals": request.get("blockers_and_residuals"),
        "prohibited_claims": request.get("prohibited_claims"),
        "durable_handoff_refs": request.get("durable_handoff_refs"),
    }
    for key, value in optional.items():
        if value not in (None, [], {}):
            document[key] = value
    validation = validate_role_return(document, role_name, package_root)
    binding_validation = validate_document_binding(
        document, policy=policy, binding=binding, parent=parent, package_root=package_root
    )
    idempotency_key = _text(request.get("idempotency_key"), "idempotency_key")
    identity = {
        "binding_ref": policy["binding_ref"],
        "invocation_id": policy["invocation_id"],
        "idempotency_key": idempotency_key,
    }
    return_ref = f"return:{canonical_digest(identity)}"
    stable = {
        "schema": "bbk.prepared-role-return-record.v1",
        "return_ref": return_ref,
        "binding_ref": policy["binding_ref"],
        "session_id": policy["session_id"],
        "invocation_id": policy["invocation_id"],
        "role": role_name,
        "return_contract": policy.get("return_contract"),
        "document_digest": validation["document_digest"],
        "binding_identity_digest": binding_validation["identity_digest"],
        "schema_path": validation["schema_path"],
        "idempotency_key": idempotency_key,
        "document": document,
    }
    record = {**stable, "record_digest": f"sha256:{canonical_digest(stable)}"}
    validate_surface(record, "bbk-prepared-role-return-record-v1.schema.json", package_root, code="ROLE_RETURN_RECORD_SCHEMA_INVALID")
    created = _write_exclusive(_prepared_root(project_root) / f"{return_ref.removeprefix('return:')}.json", record)
    receipt_content = {
        "schema": "bbk.role-return-validation-receipt.v1",
        "phase": "PREPARED",
        "return_ref": return_ref,
        "binding_ref": policy["binding_ref"],
        "session_id": policy["session_id"],
        "invocation_id": policy["invocation_id"],
        "role": role_name,
        "contract": validation["contract"],
        "schema_path": validation["schema_path"],
        "document_digest": validation["document_digest"],
        "binding_identity_digest": binding_validation["identity_digest"],
        "result": "PASS",
    }
    validate_surface(receipt_content, "bbk-role-return-validation-receipt-v1.schema.json", package_root, code="ROLE_RETURN_RECEIPT_SCHEMA_INVALID")
    receipt, _ = append_receipt(project_root, "ROLE_RETURN_VALIDATION", receipt_content)
    value = {
        "schema": "bbk.role-return-prepared.v1",
        "status": "PASS",
        "return_ref": return_ref,
        "created": created,
        "validation_receipt_ref": receipt["receipt_id"],
        "document_digest": validation["document_digest"],
        "binding_identity_digest": binding_validation["identity_digest"],
        "yield_input": {"result": {"data": document}},
        "instruction": "Invoke hidden yield once with the exact complete yield_input. The pre-effect hook revalidates it against this immutable prepared record; do not reconstruct, abbreviate, or edit it.",
    }
    validate_surface(value, "bbk-role-return-prepared-v1.schema.json", package_root, code="ROLE_RETURN_OUTPUT_SCHEMA_INVALID")
    return value


def validate_request(project_root: Path, package_root: Path, request: Mapping[str, Any]) -> dict[str, Any]:
    validate_surface(dict(request), "bbk-role-return-validate-v1.schema.json", package_root, code="ROLE_RETURN_REQUEST_SCHEMA_INVALID")
    policy, binding, parent = _binding_context(project_root, request)
    document = request.get("document")
    validation = validate_role_return(document, str(policy.get("role") or ""), package_root)
    expected_contract = policy.get("return_contract")
    if isinstance(document, dict) and expected_contract and document.get("contract") != expected_contract:
        raise RoleReturnRuntimeError(
            "ROLE_RETURN_CONTRACT_MISMATCH",
            f"document contract {document.get('contract')!r} differs from bound contract {expected_contract!r}",
        )
    binding_validation = validate_document_binding(
        document, policy=policy, binding=binding, parent=parent, package_root=package_root
    )
    tool_call_id = _text(request.get("tool_call_id"), "tool_call_id")
    prepared_record = _prepared_for_document(
        project_root,
        policy=policy,
        document=document,
        document_digest=validation["document_digest"],
    )
    return_ref = str(prepared_record["return_ref"])
    admission = {
        "schema": "bbk.role-return-admission.v1",
        "phase": "YIELD_PRE_EFFECT",
        "return_ref": return_ref,
        "binding_ref": policy["binding_ref"],
        "session_id": policy["session_id"],
        "invocation_id": policy["invocation_id"],
        "role": policy["role"],
        "contract": validation["contract"],
        "schema_path": validation["schema_path"],
        "document_digest": validation["document_digest"],
        "binding_identity_digest": binding_validation["identity_digest"],
        "prepared_return_verified": True,
        "tool_call_id": tool_call_id,
        "result": "PASS",
    }
    validate_surface(admission, "bbk-role-return-admission-v1.schema.json", package_root, code="ROLE_RETURN_RECEIPT_SCHEMA_INVALID")
    receipt, _ = append_receipt(project_root, "ROLE_RETURN_ADMISSION", admission)
    value = {
        "schema": "bbk.role-return-validation.v1",
        **validation,
        "binding_ref": policy["binding_ref"],
        "binding_identity_digest": binding_validation["identity_digest"],
        "session_id": policy["session_id"],
        "invocation_id": policy["invocation_id"],
        "tool_call_id": tool_call_id,
        "return_ref": return_ref,
        "admission_receipt_ref": receipt["receipt_id"],
        "prepared_return_verified": True,
    }
    validate_surface(value, "bbk-role-return-validation-v1.schema.json", package_root, code="ROLE_RETURN_OUTPUT_SCHEMA_INVALID")
    return value


def resolve_prepared(project_root: Path, package_root: Path, request: Mapping[str, Any]) -> dict[str, Any]:
    validate_surface(dict(request), "bbk-role-return-resolve-v1.schema.json", package_root, code="ROLE_RETURN_REQUEST_SCHEMA_INVALID")
    policy, _binding, _parent = _binding_context(project_root, request)
    return_ref = _text(request.get("return_ref"), "return_ref")
    record = _load_prepared(project_root, return_ref)
    for field in ("binding_ref", "session_id", "invocation_id", "role"):
        expected = policy.get(field)
        if record.get(field) != expected:
            raise RoleReturnRuntimeError("ROLE_RETURN_TOKEN_BINDING_MISMATCH", f"prepared return {field} differs from the active binding")
    validation = validate_role_return(record.get("document"), str(policy.get("role") or ""), package_root)
    binding_validation = validate_document_binding(
        record.get("document"), policy=policy, binding=_binding, parent=_parent, package_root=package_root
    )
    if validation["document_digest"] != record.get("document_digest"):
        raise RoleReturnRuntimeError("ROLE_RETURN_RECORD_TAMPERED", "prepared document digest changed")
    tool_call_id = _text(request.get("tool_call_id"), "tool_call_id")
    admission = {
        "schema": "bbk.role-return-admission.v1",
        "phase": "YIELD_PRE_EFFECT",
        "return_ref": return_ref,
        "binding_ref": policy["binding_ref"],
        "session_id": policy["session_id"],
        "invocation_id": policy["invocation_id"],
        "role": policy["role"],
        "contract": validation["contract"],
        "schema_path": validation["schema_path"],
        "document_digest": validation["document_digest"],
        "binding_identity_digest": binding_validation["identity_digest"],
        "prepared_return_verified": True,
        "tool_call_id": tool_call_id,
        "result": "PASS",
    }
    validate_surface(admission, "bbk-role-return-admission-v1.schema.json", package_root, code="ROLE_RETURN_RECEIPT_SCHEMA_INVALID")
    receipt, _ = append_receipt(project_root, "ROLE_RETURN_ADMISSION", admission)
    value = {
        "schema": "bbk.role-return-yield-admission.v1",
        "status": "ADMITTED",
        "return_ref": return_ref,
        "binding_ref": policy["binding_ref"],
        "role": policy["role"],
        "document_digest": validation["document_digest"],
        "binding_identity_digest": binding_validation["identity_digest"],
        "admission_receipt_ref": receipt["receipt_id"],
        "tool_call_id": tool_call_id,
        "prepared_return_verified": True,
        "yield_input": {"result": {"data": record["document"]}},
    }
    validate_surface(value, "bbk-role-return-yield-admission-v1.schema.json", package_root, code="ROLE_RETURN_OUTPUT_SCHEMA_INVALID")
    return value


def execute(project_root: Path, package_root: Path, command: str, request: Mapping[str, Any]) -> dict[str, Any]:
    if command == "template":
        return template(project_root, package_root, request)
    if command == "prepare":
        return prepare(project_root, package_root, request)
    if command == "validate":
        return validate_request(project_root, package_root, request)
    if command == "resolve":
        return resolve_prepared(project_root, package_root, request)
    raise RoleReturnRuntimeError("ROLE_RETURN_COMMAND_INVALID", f"unknown command {command!r}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="governed project root")
    parser.add_argument("--package-root", default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("template", "prepare", "validate", "resolve"):
        command = sub.add_parser(name)
        command.add_argument("--request", required=True, help="JSON object, path, or - for stdin")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    _maybe_reexec_managed_validator(args.root)
    try:
        result = execute(
            _project_root(args.root),
            _package_root(args.package_root),
            args.command,
            _load_request(args.request),
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (RoleReturnRuntimeError, OmpBindingError, GovernanceStateError) as exc:
        code = getattr(exc, "code", "ROLE_RETURN_RUNTIME_ERROR")
        message = getattr(exc, "message", str(exc))
        next_action = getattr(exc, "smallest_next_action", "Repair the typed request and retry.")
        diagnostics = getattr(exc, "diagnostics", [])
        print(json.dumps({
            "schema": "bbk.role-return-error.v1",
            "status": "BLOCK",
            "reason_code": code,
            "message": message,
            "diagnostics": diagnostics,
            "smallest_next_action": next_action,
        }, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
