"""Checked-in, fail-closed deterministic operation registry for M3."""
from __future__ import annotations

import hashlib
import importlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

try:
    from diagnostics import typed_diagnostic
except ModuleNotFoundError:  # namespace-package import (``tools.deterministic_operations``)
    from .diagnostics import typed_diagnostic

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "spec" / "operations" / "deterministic-operation-registry.json"


class OperationAdmissionError(ValueError):
    """Raised before an operation's callable is entered."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_registry(path: Path | None = None) -> dict[str, Any]:
    source = path or REGISTRY_PATH
    value = json.loads(source.read_text(encoding="utf-8"))
    if value.get("schema") != "bbk.deterministic-operation-registry.v1":
        raise OperationAdmissionError("OPERATION_REGISTRY_SCHEMA", "unsupported operation registry schema")
    operations = value.get("operations")
    if not isinstance(operations, list) or not operations:
        raise OperationAdmissionError("OPERATION_REGISTRY_EMPTY", "operation registry has no operations")
    ids = [item.get("operation_id") for item in operations]
    if any(not isinstance(item, dict) for item in operations) or len(ids) != len(set(ids)):
        raise OperationAdmissionError("OPERATION_REGISTRY_DUPLICATE_ID", "operation IDs must be unique")
    return value


def _entrypoint(entry: Mapping[str, Any]) -> tuple[Callable[..., Any], Path]:
    module_name, function_name = str(entry["entrypoint"]).split(":", 1)
    module = importlib.import_module(module_name)
    function = getattr(module, function_name, None)
    module_path = Path(getattr(module, "__file__", "")).resolve()
    if not callable(function) or not module_path.is_file():
        raise OperationAdmissionError("OPERATION_ENTRYPOINT_UNAVAILABLE", str(entry["entrypoint"]))
    return function, module_path


def qualify_operation(
    operation_id: str,
    *,
    subject: str,
    argv: Sequence[str] = (),
    environment: Mapping[str, str] | None = None,
    requested_effects: Sequence[str] = ("READ_ONLY",),
    registry_path: Path | None = None,
) -> dict[str, Any]:
    """Qualify one registered operation; reject every ad-hoc variant."""
    registry = load_registry(registry_path)
    entry = next((item for item in registry["operations"] if item.get("operation_id") == operation_id), None)
    if entry is None:
        raise OperationAdmissionError("OPERATION_NOT_REGISTERED", f"unregistered operation: {operation_id}")
    if not subject:
        raise OperationAdmissionError("OPERATION_SUBJECT_REQUIRED", "operation subject is required")
    function, module_path = _entrypoint(entry)
    observed_hash = _sha256(module_path)
    if observed_hash != entry.get("implementation_sha256"):
        raise OperationAdmissionError("OPERATION_IMPLEMENTATION_DRIFT", operation_id)
    expected_argv = list(entry.get("argv", []))
    if list(argv) != expected_argv:
        raise OperationAdmissionError("OPERATION_ARGV_NOT_QUALIFIED", "argv must match the registered array exactly")
    requested = set(requested_effects)
    allowed = set(entry.get("allowed_effects", []))
    if not requested or not requested.issubset(allowed):
        raise OperationAdmissionError("OPERATION_EFFECT_NOT_ALLOWED", "requested effects exceed registered effects")
    policy = entry.get("environment_policy", {})
    env = dict(environment or {})
    if policy.get("mode") == "NONE" and env:
        raise OperationAdmissionError("OPERATION_ENVIRONMENT_NOT_ALLOWED", "operation forbids environment variables")
    if policy.get("mode") == "ALLOWLIST" and not set(env).issubset(set(policy.get("allowed_variables", []))):
        raise OperationAdmissionError("OPERATION_ENVIRONMENT_NOT_QUALIFIED", "environment contains unregistered variables")
    return {
        "schema": "bbk.operation-qualification.v1",
        "status": "QUALIFIED",
        "operation_id": operation_id,
        "version": entry["version"],
        "implementation_sha256": observed_hash,
        "subject": subject,
        "argv": expected_argv,
        "allowed_effects": list(entry["allowed_effects"]),
        "environment_policy": policy,
        "reason": "registered implementation, argv, environment, and effect fence matched",
    }


def run_registered_operation(
    operation_id: str,
    *,
    subject: str,
    argv: Sequence[str] = (),
    environment: Mapping[str, str] | None = None,
    registry_path: Path | None = None,
) -> dict[str, Any]:
    """Run a qualified operation and return its semantic result plus v2 receipt."""
    qualification = qualify_operation(
        operation_id,
        subject=subject,
        argv=argv,
        environment=environment,
        registry_path=registry_path,
    )
    registry = load_registry(registry_path)
    entry = next(item for item in registry["operations"] if item["operation_id"] == operation_id)
    function, _module_path = _entrypoint(entry)
    try:
        result = function(Path(subject))
        status = str(result.get("status", "PASS")) if isinstance(result, dict) else "PASS"
        semantic = {"status": "PASS" if status == "PASS" else "FAIL", "value": result, "code": None, "message": None}
        disposition = "PASS" if status == "PASS" else "FAIL"
        diagnostic = typed_diagnostic(
            code="OPERATION_COMPLETED" if status == "PASS" else "OPERATION_RESULT_FAILED",
            subject=subject,
            semantic_status=semantic["status"],
            semantic_value=result,
            mechanical_status="PASS",
            claims=("registered operation executed",),
            not_established=("independent validation",),
        )
    except Exception as exc:  # operation failure is represented, not promoted
        result = None
        disposition = "FAIL"
        semantic = {"status": "NOT_RUN", "value": None, "code": "OPERATION_EXCEPTION", "message": str(exc)}
        diagnostic = typed_diagnostic(
            code="OPERATION_EXCEPTION", subject=subject, semantic_status="NOT_RUN", mechanical_status="FAIL", message=str(exc), not_established=("operation result",)
        )
    receipt = {
        "schema": "bbk.command-attempt.v2",
        "semantic_command_id": operation_id,
        "execution_attempt_ref": f"{operation_id}:1",
        "physical_command_attempt": 1,
        "invocation_identity": {
            "executable": entry["entrypoint"],
            "arguments_sha256": hashlib.sha256(json.dumps(list(argv), separators=(",", ":")).encode()).hexdigest(),
            "inputs_sha256": hashlib.sha256(subject.encode()).hexdigest(),
            "environment_constraints_sha256": hashlib.sha256(json.dumps(qualification["environment_policy"], sort_keys=True).encode()).hexdigest(),
        },
        "effect_class": "READ_ONLY",
        "disposition": disposition,
        "effects_observed": {"product_mutation": "NONE", "external_effect": "NONE"},
        "cleanup": {"state": "COMPLETE", "remaining_processes_or_handles": False},
        "replay": {"eligible": True, "reason": "read-only registered operation", "maximum_replays": 1, "replay_of_physical_attempt": None},
        "operation_id": operation_id,
        "operation_version": qualification["version"],
        "operation_implementation_sha256": qualification["implementation_sha256"],
        "subject": subject,
        "argv": list(argv),
        "environment_policy": qualification["environment_policy"],
        "allowed_effects": qualification["allowed_effects"],
        "output_schema": entry["output_schema"],
        "invalidation_keys": list(entry["invalidation_keys"]),
        "qualification": "QUALIFIED",
        "semantic_result": semantic,
        "mechanical_envelope": diagnostic["mechanical_envelope"],
    }
    return {"status": disposition, "result": result, "diagnostic": diagnostic, "qualification": qualification, "receipt": receipt}


def run_source_sanity(subject: Path) -> dict[str, Any]:
    from source_sanity import validate
    # The source-sanity tool is canonical for repository scope; subject is
    # admission-bound here to prevent an operation from silently changing root.
    if subject.resolve() != ROOT.resolve():
        raise OperationAdmissionError("OPERATION_SUBJECT_MISMATCH", "source sanity is registered for this repository root")
    return validate()


def run_identity_graph(subject: Path) -> dict[str, Any]:
    """Validate one exact identity graph carrier without mutating it."""
    try:
        from identity_graph import validate_file
    except ModuleNotFoundError:  # namespace-package import
        from .identity_graph import validate_file
    return validate_file(subject)
