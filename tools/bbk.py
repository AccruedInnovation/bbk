#!/usr/bin/env python3
"""Deterministic utilities for the Blueprint Bootstrap Kit (BBK).

BBK provides practical project records and evidence mechanics. It never creates
an official Blueprint baseline, readiness attestation, execution authorization,
or release authority.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fnmatch
import hashlib
import json
import os
import platform
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
import traceback
import uuid
from importlib import metadata as importlib_metadata
from pathlib import Path, PurePath
from typing import Any, Iterable, Iterator, Mapping, NoReturn, Sequence

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from runtime_requirements import enforce_supported_python, normalize_python_command, python_command, python_environment

enforce_supported_python(program="BBK")

import dependencies as dependency_tool
from urllib.parse import urlparse

# When executed from the source package, ``tools`` is the script directory.
# The OMP installer also places ``bbk.py`` and ``contracts.py`` beside one
# another, so this import path works in both forms.  Importlib-based tests do
# not always add the script directory to sys.path, hence the explicit fallback.
try:
    from contracts import (
        canonical_digest as contract_digest,
        derive_fit_risk_tier,
        markdown_slice,
        markdown_solution_outcome_fit,
        markdown_structure,
        validate_profile,
        validate_profile_capability_request,
        validate_profile_capability_result,
        validate_slice,
        validate_slice_set,
        validate_solution_outcome_fit,
        validate_structure,
        validate_work_unit,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from contracts import (
        canonical_digest as contract_digest,
        derive_fit_risk_tier,
        markdown_slice,
        markdown_solution_outcome_fit,
        markdown_structure,
        validate_profile,
        validate_profile_capability_request,
        validate_profile_capability_result,
        validate_slice,
        validate_slice_set,
        validate_solution_outcome_fit,
        validate_structure,
        validate_work_unit,
    )

try:
    from state_effect import (
        compare_state_effect_inventory,
        markdown_state_decision_effect,
        validate_slice_v2,
        validate_state_decision_effect,
        validate_structure_review_v2,
        validate_structure_v2,
        validate_transition_trace,
        validate_transition_trace_set,
    )
    from review_assurance import (
        aggregate_review,
        build_review_run,
        compile_review_context,
        compile_review_manifest,
        create_finding_disposition,
        create_learning_candidate,
        markdown_review_manifest,
        markdown_review_run,
        reconcile_findings,
        validate_assurance_contract,
        validate_evidence_receipt,
        validate_finding_disposition,
        validate_learning_candidate,
        validate_review_attempt,
        validate_review_context,
        validate_review_finding,
        validate_review_manifest,
        validate_review_run,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from state_effect import (
        compare_state_effect_inventory,
        markdown_state_decision_effect,
        validate_slice_v2,
        validate_state_decision_effect,
        validate_structure_review_v2,
        validate_structure_v2,
        validate_transition_trace,
        validate_transition_trace_set,
    )
    from review_assurance import (
        aggregate_review,
        build_review_run,
        compile_review_context,
        compile_review_manifest,
        create_finding_disposition,
        create_learning_candidate,
        markdown_review_manifest,
        markdown_review_run,
        reconcile_findings,
        validate_assurance_contract,
        validate_evidence_receipt,
        validate_finding_disposition,
        validate_learning_candidate,
        validate_review_attempt,
        validate_review_context,
        validate_review_finding,
        validate_review_manifest,
        validate_review_run,
    )

try:
    from artifact_classification import is_non_operational_example
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from artifact_classification import is_non_operational_example

try:
    from substrate import mise_adapter as substrate_mise_adapter
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from substrate import mise_adapter as substrate_mise_adapter

try:
    from atomic_finalizer import FinalizationError, finalize_json as finalize_atomic_json
    from evidence_replay import ReplayError, evaluate_replay as evaluate_command_replay, powershell_capture_preflight, replay_attempt as build_replay_attempt
    from planning_optimization import (
        PlanningOptimizationError, build_planning_readiness, child_event as build_child_event,
        coverage_return_projection, generate_assertion_contract, generate_worker_contract,
        issue_workspace_receipt, migrate_legacy_planning_readiness, transact_plan, validate_project_coverage,
    )
    from runtime_identity import RuntimeIdentityError, resolve_effective_profile
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from atomic_finalizer import FinalizationError, finalize_json as finalize_atomic_json
    from evidence_replay import ReplayError, evaluate_replay as evaluate_command_replay, powershell_capture_preflight, replay_attempt as build_replay_attempt
    from planning_optimization import (
        PlanningOptimizationError, build_planning_readiness, child_event as build_child_event,
        coverage_return_projection, generate_assertion_contract, generate_worker_contract,
        issue_workspace_receipt, migrate_legacy_planning_readiness, transact_plan, validate_project_coverage,
    )
    from runtime_identity import RuntimeIdentityError, resolve_effective_profile

try:
    from strict_json import StrictJsonError, load_path as strict_load_path
    from artifact_packages import (
        ArtifactPackageError,
        build_legacy_manifest as artifact_build_legacy_manifest,
        create_successor as artifact_create_successor,
        doctor as artifact_doctor,
        file_reference as artifact_file_reference,
        finalize_draft as artifact_finalize_draft,
        finalize_source_set as artifact_finalize_source_set,
        preflight_draft as artifact_preflight_draft,
        reconcile_operation as artifact_reconcile_operation,
        verify_publication_freshness as artifact_verify_publication_freshness,
        seal_draft as artifact_seal_draft,
        verify_file_reference as artifact_verify_file_reference,
        verify_legacy_manifest as artifact_verify_legacy_manifest,
        verify_package as artifact_verify_package,
    )
    from handoff_packages import (
        AUTHORITY_BOUNDARY as HANDOFF_V2_AUTHORITY_BOUNDARY,
        handoff_value as load_handoff_v2_value,
        seal_handoff as seal_handoff_v2,
        verify_handoff_package as verify_handoff_v2_package,
    )
    from context_packages import ContextPackageError, compile_review_package, compile_worker_context
    from host_preflight import HostPreflightError, run_preflight
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from strict_json import StrictJsonError, load_path as strict_load_path
    from artifact_packages import (
        ArtifactPackageError,
        build_legacy_manifest as artifact_build_legacy_manifest,
        create_successor as artifact_create_successor,
        doctor as artifact_doctor,
        file_reference as artifact_file_reference,
        finalize_draft as artifact_finalize_draft,
        finalize_source_set as artifact_finalize_source_set,
        preflight_draft as artifact_preflight_draft,
        reconcile_operation as artifact_reconcile_operation,
        verify_publication_freshness as artifact_verify_publication_freshness,
        seal_draft as artifact_seal_draft,
        verify_file_reference as artifact_verify_file_reference,
        verify_legacy_manifest as artifact_verify_legacy_manifest,
        verify_package as artifact_verify_package,
    )
    from handoff_packages import (
        AUTHORITY_BOUNDARY as HANDOFF_V2_AUTHORITY_BOUNDARY,
        handoff_value as load_handoff_v2_value,
        seal_handoff as seal_handoff_v2,
        verify_handoff_package as verify_handoff_v2_package,
    )
    from context_packages import ContextPackageError, compile_review_package, compile_worker_context
    from host_preflight import HostPreflightError, run_preflight


def _read_package_version() -> str:
    script = Path(__file__).resolve()
    candidates = [script.parents[1] / "VERSION", script.parent / "VERSION"]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8").strip()
    raise RuntimeError(
        "BBK VERSION file is missing; expected it at "
        + " or ".join(str(candidate) for candidate in candidates)
    )


VERSION = _read_package_version()
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
DEFAULT_EXCLUDES = [
    ".git/**", ".jj/**", ".bbk/**", ".bbk-worktrees/**",
    "node_modules/**", "target/**", "dist/**", "build/**", "out/**", ".next/**",
    ".venv/**", "venv/**", "__pycache__/**", ".pytest_cache/**", ".mypy_cache/**",
    ".ruff_cache/**", ".cache/**", "*.pyc", "*.pyo", "*.swp", "*.tmp",
]
MAX_CAPTURE = 2 * 1024 * 1024


def package_root() -> Path:
    """Resolve the BBK package root for source, installed CLI, or OMP copy."""
    script = Path(__file__).resolve()
    candidates: list[Path] = []
    if value := os.environ.get("BBK_PACKAGE_ROOT"):
        candidates.append(Path(value).expanduser())
    # Normal source/install package: <root>/tools/bbk.py.
    candidates.append(script.parents[1])
    # Self-contained OMP copy: <extension>/bbk.py.
    candidates.append(script.parent)
    for candidate in candidates:
        if (candidate / "VERSION").is_file() and (candidate / "templates").is_dir():
            return candidate.resolve()
    return script.parents[1]


PACKAGE_ROOT = package_root()
TEMPLATE_DIR = PACKAGE_ROOT / "templates"
SCHEMA_DIR = PACKAGE_ROOT / "spec" / "schemas"

SCHEMA_TEMPLATE_REGISTRY: dict[str, dict[str, str]] = {
    "solution-outcome-fit": {
        "template": "solution-outcome-fit.json",
        "schema": "bbk-solution-outcome-fit-v1.schema.json",
    },
    "implementation-structure": {
        "template": "implementation-structure-contract-v3.json",
        "schema": "bbk-implementation-structure-contract-v3.schema.json",
    },
    "state-decision-effect": {
        "template": "state-decision-effect-design.json",
        "schema": "bbk-state-decision-effect-design-v1.schema.json",
    },
    "transition-trace": {
        "template": "state-transition-trace.json",
        "schema": "bbk-state-transition-trace-v1.schema.json",
    },
    "execution-slice": {
        "template": "execution-slice-v2.json",
        "schema": "bbk-execution-slice-v2.schema.json",
    },
    "work-unit": {
        "template": "work-unit.json",
        "schema": "work-unit.schema.json",
    },
    "assurance-contract": {
        "template": "assurance-contract.json",
        "schema": "bbk-assurance-contract-v1.schema.json",
    },
    "evidence-receipt": {
        "template": "evidence-receipt-v2.json",
        "schema": "bbk-evidence-receipt-v2.schema.json",
    },
    "environment-observation": {
        "template": "environment-observation-evidence-receipt-v2.json",
        "schema": "bbk-evidence-receipt-v2.schema.json",
    },
    "question-branch": {
        "template": "question-branch.json",
        "schema": "bbk-question-branch-v1.schema.json",
    },
    "handoff": {
        "template": "handoff-v2.json",
        "schema": "bbk-handoff-v2.schema.json",
    },
    "handoff-v2": {
        "template": "handoff-v2.json",
        "schema": "bbk-handoff-v2.schema.json",
    },
    "handoff-v1": {
        "template": "handoff.json",
        "schema": "bbk-handoff-v1.schema.json",
    },
    "host-preflight-request": {
        "template": "host-preflight-request.json",
        "schema": "bbk-host-preflight-request-v1.schema.json",
    },
    "review-package-request": {
        "template": "review-package-request.json",
        "schema": "bbk-review-package-request-v1.schema.json",
    },
    "prototype-charter": {
        "template": "prototype-charter-v2.json",
        "schema": "bbk-prototype-charter-v2.schema.json",
    },
    "review-manifest": {
        "template": "review-manifest.json",
        "schema": "bbk-review-manifest-v1.schema.json",
    },
    "review-context": {
        "template": "review-context-manifest.json",
        "schema": "bbk-review-context-manifest-v1.schema.json",
    },
    "review-attempt": {
        "template": "review-attempt.json",
        "schema": "bbk-review-attempt-v1.schema.json",
    },
    "review-finding": {
        "template": "review-finding.json",
        "schema": "bbk-review-finding-v1.schema.json",
    },
    "finding-disposition": {
        "template": "finding-disposition.json",
        "schema": "bbk-finding-disposition-v1.schema.json",
    },
    "learning-candidate": {
        "template": "learning-candidate.json",
        "schema": "bbk-learning-candidate-v1.schema.json",
    },
    "artifact-manifest": {
        "template": "",
        "schema": "bbk-artifact-manifest-v1.schema.json",
    },
}


class BbkError(RuntimeError):
    """BBK command error with an optional structured diagnostic payload."""

    def __init__(self, message: str, *, diagnostic: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.diagnostic = dict(diagnostic) if diagnostic is not None else None


def invalid_argument_error(
    message: str,
    *,
    field: str,
    received: Any,
    valid_values: Sequence[Any] = (),
    example_command: str = "bbk --help",
    documentation_command: str = "bbk --help",
    smallest_next_action: str | None = None,
) -> BbkError:
    """Create a command-level argument error with a stable diagnostic."""
    diagnostic = {
        "schema": "bbk.cli-error.v1",
        "status": "INVALID_ARGUMENT",
        "code": "INVALID_ARGUMENT",
        "error": message,
        "message": message,
        "field": field,
        "received": received,
        "valid_values": sorted(str(value) for value in valid_values),
        "required": [],
        "example_command": example_command,
        "documentation_command": documentation_command,
        "smallest_next_action": smallest_next_action or "Correct the named argument and rerun the command.",
    }
    return BbkError(message, diagnostic=diagnostic)


class BbkCliParseError(RuntimeError):
    """Argument-parser failure rendered as a stable machine-readable diagnostic."""

    def __init__(self, diagnostic: Mapping[str, Any]):
        self.diagnostic = dict(diagnostic)
        super().__init__(str(self.diagnostic.get("error") or self.diagnostic.get("message") or "invalid arguments"))


def _argument_example(parser: argparse.ArgumentParser) -> str:
    """Build one concise syntactically shaped example from parser metadata."""
    pieces = [parser.prog]
    for action in parser._actions:
        if isinstance(action, argparse._HelpAction):
            continue
        if isinstance(action, argparse._SubParsersAction):
            choices = [name for name in action.choices if name]
            if choices:
                pieces.append(sorted(choices)[0])
            continue
        if action.option_strings and not action.required:
            continue
        if not action.option_strings and not action.required and action.nargs in ("?", "*"):
            continue
        if action.option_strings:
            flag = next((value for value in action.option_strings if value.startswith("--")), action.option_strings[0])
            pieces.append(flag)
            if action.nargs != 0:
                value = sorted(str(item) for item in action.choices)[0] if action.choices else f"<{action.dest.replace('_', '-')}>"
                pieces.append(value)
            continue
        if action.dest in {"help", argparse.SUPPRESS}:
            continue
        value = sorted(str(item) for item in action.choices)[0] if action.choices else f"<{action.dest.replace('_', '-')}>"
        pieces.append(value)
    return " ".join(pieces)


def _argument_for_token(parser: argparse.ArgumentParser, token: str | None) -> argparse.Action | None:
    if not token:
        return None
    for action in parser._actions:
        if token == action.dest or token in action.option_strings:
            return action
    normalized = token.lstrip("-").replace("-", "_")
    return next((action for action in parser._actions if action.dest == normalized), None)


class BbkArgumentParser(argparse.ArgumentParser):
    """Argparse adapter that never emits an unstructured usage wall on errors."""

    def _raise_diagnostic(
        self,
        message: str,
        *,
        field: str | None = None,
        received: Any = None,
        valid_values: Sequence[Any] | None = None,
        required: Sequence[str] | None = None,
        code: str = "INVALID_ARGUMENT",
        smallest_next_action: str | None = None,
    ) -> NoReturn:
        diagnostic = {
            "schema": "bbk.cli-error.v1",
            "status": "INVALID_ARGUMENT",
            "code": code,
            "command": self.prog,
            "error": message,
            "message": message,
            "field": field,
            "received": received,
            "valid_values": sorted(str(value) for value in (valid_values or [])),
            "required": [str(value) for value in (required or [])],
            "example_command": _argument_example(self),
            "documentation_command": f"{self.prog} --help",
            "smallest_next_action": smallest_next_action
            or "Correct the named argument using the command help, then rerun the command.",
        }
        raise BbkCliParseError(diagnostic)

    def _check_value(self, action: argparse.Action, value: Any) -> None:
        if action.choices is not None and value not in action.choices:
            self._raise_diagnostic(
                f"Invalid value for {action.dest}: {value!r}.",
                field=action.dest,
                received=value,
                valid_values=list(action.choices),
                code="INVALID_CHOICE",
                smallest_next_action=f"Use one of the valid values for {action.dest}, then rerun the command.",
            )
        super()._check_value(action, value)

    def error(self, message: str) -> NoReturn:
        field: str | None = None
        received: Any = None
        valid_values: list[Any] = []
        required: list[str] = []
        code = "INVALID_ARGUMENT"
        smallest = "Correct the arguments shown by the command help, then rerun the command."

        missing_match = re.search(r"the following arguments are required: (.+)$", message)
        argument_match = re.search(r"argument ([^:]+): (.+)$", message)
        unrecognized_match = re.search(r"unrecognized arguments?: (.+)$", message)
        invalid_choice_match = re.search(r"argument ([^:]+): invalid choice: ['\"]?([^'\" ]+)", message)
        if missing_match:
            required = [item.strip() for item in missing_match.group(1).split(",") if item.strip()]
            token = required[0] if required else None
            action = _argument_for_token(self, token)
            field = action.dest if action is not None else (token or "required_arguments").lstrip("-").replace("-", "_")
            valid_values = list(action.choices) if action is not None and action.choices is not None else []
            code = "MISSING_REQUIRED_ARGUMENT"
            smallest = f"Provide {', '.join(required)} and rerun the command."
        elif invalid_choice_match:
            token = invalid_choice_match.group(1).strip()
            action = _argument_for_token(self, token)
            field = action.dest if action is not None else token.lstrip("-").replace("-", "_")
            received = invalid_choice_match.group(2)
            valid_values = list(action.choices) if action is not None and action.choices is not None else []
            code = "INVALID_CHOICE"
            smallest = f"Use one of the valid values for {field}, then rerun the command."
        elif argument_match:
            token = argument_match.group(1).strip()
            action = _argument_for_token(self, token)
            field = action.dest if action is not None else token.lstrip("-").replace("-", "_")
            valid_values = list(action.choices) if action is not None and action.choices is not None else []
            value_match = re.search(r"(?:value|choice):? ['\"]?([^'\" ]+)", argument_match.group(2))
            if value_match:
                received = value_match.group(1)
            code = "INVALID_ARGUMENT_VALUE"
        elif unrecognized_match:
            received = unrecognized_match.group(1).split()[0]
            field = "arguments"
            code = "UNRECOGNIZED_ARGUMENT"
            smallest = f"Remove or correct {received!r}; inspect {self.prog} --help for supported arguments."
        elif "invalid choice" in message:
            choice_match = re.search(r"invalid choice: ['\"]?([^'\" ]+)", message)
            received = choice_match.group(1) if choice_match else None
            field = "command"
            code = "INVALID_CHOICE"
            for action in self._actions:
                if isinstance(action, argparse._SubParsersAction):
                    valid_values = list(action.choices)
                    field = action.dest or "command"
                    break

        self._raise_diagnostic(
            message,
            field=field,
            received=received,
            valid_values=valid_values,
            required=required,
            code=code,
            smallest_next_action=smallest,
        )


def configure_utf8_standard_streams() -> None:
    """Make direct CLI JSON/text transport UTF-8 and fail on corruption.

    OMP launches the CLI in UTF-8 mode, but users and test runners can also
    invoke ``python tools/bbk.py`` directly from a legacy Windows code page.
    Governed text must be emitted as UTF-8 rather than being replaced or
    rejected by an inherited locale-dependent stream encoding.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(encoding="utf-8", errors="strict")
        except (AttributeError, OSError, TypeError, ValueError):
            pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def portable_relative_path(path: PurePath, root: PurePath) -> str:
    """Serialize a root-relative path with stable POSIX separators."""
    return path.relative_to(root).as_posix()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def pretty_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write(path: Path, data: bytes, mode: int | None = None) -> None:
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
    finally:
        with contextlib.suppress(FileNotFoundError):
            temp.unlink()


def write_json(path: Path, value: Any, mode: int | None = None) -> None:
    atomic_write(path, pretty_bytes(value), mode)


def read_json(path: Path) -> Any:
    """Read governed JSON through the shared strict-load boundary."""
    try:
        return strict_load_path(path)
    except StrictJsonError as exc:
        diagnostic = exc.as_dict()
        raise BbkError(
            f"Invalid governed JSON in {path}: {diagnostic.get('message')}",
            diagnostic=diagnostic,
        ) from exc


def validate_id(value: str, label: str = "id") -> str:
    if not SAFE_ID.fullmatch(value):
        raise BbkError(f"Invalid {label} {value!r}; use 1-128 letters, digits, '.', '_' or '-' and start with a letter or digit")
    return value


def run(argv: Sequence[str], cwd: Path, *, timeout: float | None = None, env: dict[str, str] | None = None) -> dict[str, Any]:
    command = [str(item) for item in argv]
    if not command:
        raise BbkError("Command argv must not be empty")
    started = time.monotonic()
    execution_environment = os.environ if env is None else env
    execution_command = normalize_python_command(command)
    child_environment = execution_environment
    if execution_command != command:
        child_environment = python_environment(execution_environment)
    executable = shutil.which(command[0], path=execution_environment.get("PATH"))
    execution_command = list(execution_command)
    if command[0].casefold() == "git":
        configured = execution_environment.get("BBK_GIT") or execution_environment.get("BBK_TEST_GIT")
        resolved = (
            Path(configured).expanduser().resolve()
            if configured
            else dependency_tool.discover_executable("git", environment=execution_environment)
        )
        if resolved is not None:
            executable = str(resolved)
            execution_command = dependency_tool.command_argv(
                resolved,
                command[1:],
                environment=execution_environment,
            )
    try:
        result = subprocess.run(
            execution_command, cwd=str(cwd), env=child_environment, timeout=timeout, check=False,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        try:
            stdout = result.stdout.decode("utf-8", "strict")
            stderr = result.stderr.decode("utf-8", "strict")
        except UnicodeDecodeError as exc:
            return {
                "argv": command, "cwd": str(cwd), "returncode": 126,
                "stdout": "",
                "stderr": f"BBK child-process output was not valid UTF-8: {exc}",
                "duration_seconds": round(time.monotonic() - started, 6),
                "timed_out": False, "executable": executable,
                "encoding_error": {
                    "schema": "bbk.utf8-transport-error.v1",
                    "status": "ERROR",
                    "stream": "stdout" if exc.object is result.stdout else "stderr",
                    "reason": str(exc),
                },
            }
        return {
            "argv": command, "cwd": str(cwd), "returncode": result.returncode,
            "stdout": stdout, "stderr": stderr,
            "duration_seconds": round(time.monotonic() - started, 6),
            "timed_out": False, "executable": executable,
        }
    except subprocess.TimeoutExpired as exc:
        try:
            stdout = exc.stdout.decode("utf-8", "strict") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = exc.stderr.decode("utf-8", "strict") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        except UnicodeDecodeError as decode_exc:
            return {
                "argv": command, "cwd": str(cwd), "returncode": 126,
                "stdout": "",
                "stderr": f"Timed-out BBK child-process output was not valid UTF-8: {decode_exc}",
                "duration_seconds": round(time.monotonic() - started, 6),
                "timed_out": True, "executable": executable,
                "encoding_error": {
                    "schema": "bbk.utf8-transport-error.v1",
                    "status": "ERROR",
                    "stream": "stdout" if decode_exc.object is exc.stdout else "stderr",
                    "reason": str(decode_exc),
                },
            }
        return {
            "argv": command, "cwd": str(cwd), "returncode": 124,
            "stdout": stdout, "stderr": stderr,
            "duration_seconds": round(time.monotonic() - started, 6),
            "timed_out": True, "executable": executable,
        }
    except FileNotFoundError as exc:
        return {
            "argv": command, "cwd": str(cwd), "returncode": 127,
            "stdout": "", "stderr": str(exc),
            "duration_seconds": round(time.monotonic() - started, 6),
            "timed_out": False, "executable": executable,
        }


def project_root(start: Path | None = None, *, required: bool = True) -> Path | None:
    current = (start or Path.cwd()).expanduser().resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".bbk" / "config.json").is_file():
            return candidate
    if required:
        raise BbkError(f"No BBK project found from {current}; run `bbk init` at the project root")
    return None


def resolve_root(value: str | None, *, required: bool = True) -> Path | None:
    if value:
        root = Path(value).expanduser().resolve()
        if required and not (root / ".bbk" / "config.json").is_file():
            raise BbkError(f"Not a BBK project: {root}")
        return root
    return project_root(required=required)


def load_config(root: Path) -> dict[str, Any]:
    value = read_json(root / ".bbk" / "config.json")
    if value.get("schema") != "bbk.config.v1":
        raise BbkError("Unsupported .bbk/config.json schema")
    return value


@contextlib.contextmanager
def lock_project(root: Path, operation: str, stale_seconds: int = 3600) -> Iterator[None]:
    path = root / ".bbk" / "runtime" / "project.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    while True:
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(pretty_bytes({"schema": "bbk.lock.v1", "operation": operation, "pid": os.getpid(), "host": socket.gethostname(), "created_at": utc_now()}))
            break
        except FileExistsError:
            age = time.time() - path.stat().st_mtime
            if age > stale_seconds:
                os.replace(path, path.with_name(f"project.lock.stale-{int(time.time())}"))
                continue
            raise BbkError(f"BBK project is locked: {path}")
    try:
        yield
    finally:
        with contextlib.suppress(FileNotFoundError):
            path.unlink()


def bbk_data_root() -> Path:
    """Return the user-level BBK data root without importing the installer."""
    if value := os.environ.get("BBK_INSTALL_ROOT"):
        return Path(value).expanduser().resolve()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "BBK"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "BBK"
    base = os.environ.get("XDG_DATA_HOME")
    return (Path(base).expanduser() if base else Path.home() / ".local" / "share") / "bbk"


def profile_search_paths(root: Path | None, extras: Sequence[str] | None = None) -> list[Path]:
    """Return deterministic profile search roots, highest precedence first."""
    raw: list[Path] = []
    for value in extras or []:
        raw.append(Path(value).expanduser())
    for value in os.environ.get("BBK_PROFILE_PATH", "").split(os.pathsep):
        if value.strip():
            raw.append(Path(value).expanduser())
    if root is not None:
        raw.extend([root / ".bbk" / "profiles", root / ".bbk-kit" / "profiles"])
    raw.append(bbk_data_root() / "profiles")
    raw.append(Path(__file__).resolve().parents[1] / "profiles")
    values: list[Path] = []
    seen: set[str] = set()
    for value in raw:
        path = value.resolve()
        key = os.path.normcase(str(path))
        if key not in seen:
            values.append(path)
            seen.add(key)
    return values



def version_key(value: str) -> tuple[tuple[int, ...], tuple[int, str, int]]:
    """Return a conservative key for BBK-style semantic prerelease versions."""
    main, _, prerelease = value.partition("-")
    numbers: list[int] = []
    for part in main.split("."):
        match = re.match(r"^(\d+)", part)
        numbers.append(int(match.group(1)) if match else 0)
    numbers += [0] * (3 - len(numbers))
    if not prerelease:
        pre = (1, "", 0)
    else:
        match = re.match(r"([A-Za-z]+)[.-]?(\d*)", prerelease)
        label = match.group(1).lower() if match else prerelease.lower()
        number = int(match.group(2)) if match and match.group(2) else 0
        rank = {"dev": 0, "alpha": 1, "beta": 2, "rc": 3}.get(label, 0)
        pre = (0, f"{rank:02d}:{label}", number)
    return tuple(numbers[:3]), pre


def profile_compatibility(value: dict[str, Any]) -> dict[str, Any]:
    requires = value.get("requires") if isinstance(value.get("requires"), dict) else {}
    minimum = requires.get("bbk_minimum") if isinstance(requires, dict) else None
    python_minimum = requires.get("python_minimum") if isinstance(requires, dict) else None
    bbk_ok = True if not minimum else version_key(VERSION) >= version_key(str(minimum))
    python_ok = True
    if python_minimum:
        pieces = [int(part) for part in re.findall(r"\d+", str(python_minimum))[:2]]
        pieces += [0] * (2 - len(pieces))
        python_ok = sys.version_info[:2] >= tuple(pieces[:2])
    return {
        "status": "PASS" if bbk_ok and python_ok else "FAIL",
        "bbk_version": VERSION, "bbk_minimum": minimum, "bbk_compatible": bbk_ok,
        "python_version": platform.python_version(), "python_minimum": python_minimum, "python_compatible": python_ok,
    }

def profile_manifest_digest(value: dict[str, Any]) -> str:
    return sha256_bytes(canonical_bytes(value))


def verify_profile_package(profile_root: Path) -> dict[str, Any]:
    """Verify an installed profile tree against its BBK package manifest."""
    manifest_path = profile_root / "PACKAGE-MANIFEST.json"
    if not manifest_path.is_file():
        return {"status": "UNMANIFESTED", "errors": ["PACKAGE-MANIFEST.json is absent"]}
    try:
        manifest = read_json(manifest_path)
    except BbkError as exc:
        return {"status": "FAIL", "errors": [str(exc)]}
    errors: list[str] = []
    files = manifest.get("files")
    if not isinstance(files, list):
        return {"status": "FAIL", "errors": ["package manifest files must be a list"]}
    expected: dict[str, dict[str, Any]] = {}
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            errors.append("invalid file record")
            continue
        rel = item["path"]
        candidate = Path(rel)
        if not rel or candidate.is_absolute() or ".." in candidate.parts or "\\" in rel:
            errors.append(f"unsafe manifest path: {rel}")
            continue
        if rel in expected:
            errors.append(f"duplicate manifest path: {rel}")
            continue
        expected[rel] = item
    excluded_parts = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
    actual: set[str] = set()
    for path in profile_root.rglob("*"):
        rel_path = path.relative_to(profile_root)
        if path.is_symlink():
            errors.append(f"symlink not allowed: {rel_path.as_posix()}")
            continue
        if not path.is_file():
            continue
        if any(part in excluded_parts for part in rel_path.parts) or path.suffix in {".pyc", ".pyo"}:
            continue
        rel = rel_path.as_posix()
        if rel == "PACKAGE-MANIFEST.json":
            continue
        actual.add(rel)
    for rel in sorted(set(expected) - actual):
        errors.append(f"missing: {rel}")
    for rel in sorted(actual - set(expected)):
        errors.append(f"unexpected: {rel}")
    for rel in sorted(actual & set(expected)):
        item = expected[rel]
        path = profile_root / rel
        if path.stat().st_size != item.get("bytes"):
            errors.append(f"size mismatch: {rel}")
        if sha256_file(path) != item.get("sha256"):
            errors.append(f"digest mismatch: {rel}")
        if os.name != "nt" and "executable" in item:
            executable = bool(path.stat().st_mode & stat.S_IXUSR)
            if executable != bool(item.get("executable")):
                errors.append(f"executable-bit mismatch: {rel}")
    payload = {
        "schema": manifest.get("root_schema", "bbk.profile-package-root.v1"),
        "name": manifest.get("name"),
        "version": manifest.get("version"),
        "files": files,
    }
    root_digest = sha256_bytes(canonical_bytes(payload))
    if manifest.get("root_sha256") != root_digest:
        errors.append("root digest mismatch")
    if manifest.get("file_count") != len(expected):
        errors.append("file_count mismatch")
    return {
        "status": "PASS" if not errors else "FAIL",
        "schema": manifest.get("schema"),
        "version": manifest.get("version"),
        "root_sha256": root_digest,
        "file_count": len(expected),
        "errors": errors,
    }


def discover_profiles(root: Path | None, extras: Sequence[str] | None = None) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    seen_manifests: set[str] = set()
    for precedence, search_root in enumerate(profile_search_paths(root, extras)):
        if not search_root.exists():
            continue
        manifests: list[Path] = []
        if (search_root / "PROFILE.json").is_file():
            manifests.append(search_root / "PROFILE.json")
        else:
            for candidate in search_root.glob("*/*/PROFILE.json"):
                if candidate.is_file():
                    manifests.append(candidate)
            for candidate in search_root.glob("*/PROFILE.json"):
                if candidate.is_file():
                    manifests.append(candidate)
        for path in sorted(set(manifests)):
            resolved = str(path.resolve())
            if resolved in seen_manifests:
                continue
            seen_manifests.add(resolved)
            try:
                value = read_json(path)
                if value.get("schema") != "bbk.language-profile.v1":
                    raise BbkError(f"unsupported profile schema {value.get('schema')!r}")
                validation = validate_profile(value)
                if not validation.get("valid"):
                    raise BbkError("invalid profile contract: " + "; ".join(validation.get("errors", [])))
                profile_id = validate_id(str(value.get("id", "")), "profile id")
                version = str(value.get("version", ""))
                if not version:
                    raise BbkError("profile version is required")
                package = verify_profile_package(path.parent)
                profiles.append({
                    "id": profile_id, "version": version, "name": value.get("name"),
                    "maturity": value.get("maturity"), "root": str(path.parent),
                    "manifest_path": str(path), "manifest_sha256": profile_manifest_digest(value),
                    "precedence": precedence, "package_verification": package,
                    "compatibility": profile_compatibility(value), "validation": validation,
                    "manifest": value,
                })
            except BbkError as exc:
                profiles.append({
                    "id": None, "version": None, "name": None, "maturity": None,
                    "root": str(path.parent), "manifest_path": str(path),
                    "precedence": precedence, "package_verification": {"status": "FAIL", "errors": [str(exc)]},
                    "compatibility": {"status": "FAIL", "errors": [str(exc)]}, "manifest": None,
                })
    return sorted(profiles, key=lambda item: (item["precedence"], item.get("id") or "", item.get("version") or ""))


def find_profile(root: Path | None, profile_id: str, version: str | None, extras: Sequence[str] | None) -> dict[str, Any]:
    profile_id = validate_id(profile_id, "profile id")
    matches = [item for item in discover_profiles(root, extras) if item.get("id") == profile_id and (version is None or item.get("version") == version)]
    if not matches:
        suffix = f" version {version}" if version else ""
        raise BbkError(f"Profile {profile_id}{suffix} was not found; set BBK_PROFILE_PATH or pass --profile-dir")
    best_precedence = min(item["precedence"] for item in matches)
    matches = [item for item in matches if item["precedence"] == best_precedence]
    return sorted(matches, key=lambda item: version_key(str(item["version"])), reverse=True)[0]


def cmd_profile_list(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).expanduser().resolve() if args.root else project_root(required=False)
    profiles = discover_profiles(root, args.profile_dir)
    return {
        "schema": "bbk.profile-list.v1", "bbk_version": VERSION,
        "project_root": str(root) if root else None,
        "search_paths": [str(path) for path in profile_search_paths(root, args.profile_dir)],
        "profiles": [{key: value for key, value in item.items() if key != "manifest"} for item in profiles],
    }


def cmd_profile_inspect(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).expanduser().resolve() if args.root else project_root(required=False)
    item = find_profile(root, args.id, args.version, args.profile_dir)
    return {"schema": "bbk.profile-inspection.v1", "bbk_version": VERSION, **item}


def resolve_profile_entrypoint(profile: dict[str, Any], key: str = "resolve") -> list[str]:
    manifest = profile.get("manifest") or {}
    entry = (manifest.get("entrypoints") or {}).get(key)
    if not isinstance(entry, list) or not entry or not all(isinstance(item, str) for item in entry):
        raise BbkError(f"Profile {profile.get('id')} has no valid {key} entrypoint")
    profile_root = Path(profile["root"])
    command: list[str] = []
    for index, raw in enumerate(entry):
        value = raw.replace("{python}", sys.executable).replace("{profile_root}", str(profile_root))
        if index > 0 and not value.startswith("-"):
            candidate = profile_root / value
            if candidate.exists():
                value = str(candidate)
        command.append(value)
    return command


def run_profile_json(
    profile: dict[str, Any], key: str, extra: Sequence[str], source: Path, timeout: float,
    *, extra_env: dict[str, str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    command = [*resolve_profile_entrypoint(profile, key), *[str(value) for value in extra]]
    env = os.environ.copy()
    env.update({"BBK_PROFILE_ROOT": profile["root"], "BBK_CORE_VERSION": VERSION})
    if extra_env:
        env.update(extra_env)
    executed = run(command, source, timeout=timeout, env=env)
    if executed["returncode"] != 0:
        raise BbkError(f"Profile {key} entrypoint failed ({executed['returncode']}): {(executed['stderr'] or executed['stdout']).strip()}")
    try:
        return json.loads(executed["stdout"]), executed
    except json.JSONDecodeError as exc:
        raise BbkError(f"Profile {key} entrypoint returned invalid JSON: {exc}") from exc

PROFILE_CAPABILITY_OPERATION_SPEC: dict[str, dict[str, str]] = {
    "state-effect": {
        "capability": "state_decision_effect",
        "entrypoint_field": "projection_entrypoint",
    },
    "state-effect-inventory": {
        "capability": "state_decision_effect",
        "entrypoint_field": "inventory_entrypoint",
    },
    "state-effect-review": {
        "capability": "state_decision_effect",
        "entrypoint_field": "review_entrypoint",
    },
    "review-context": {
        "capability": "review_assurance",
        "entrypoint_field": "context_entrypoint",
    },
    "review-lens": {
        "capability": "review_assurance",
        "entrypoint_field": "review_entrypoint",
    },
    "evidence-adapter": {
        "capability": "review_assurance",
        "entrypoint_field": "evidence_entrypoint",
    },
}


def _require_profile_execution(profile: dict[str, Any], *, allow_unverified: bool) -> None:
    verification = profile.get("package_verification", {})
    if verification.get("status") != "PASS" and not allow_unverified:
        raise BbkError(
            f"Profile package verification is {verification.get('status')}; "
            "pass --allow-unverified only for deliberate local development"
        )
    compatibility = profile.get("compatibility", {})
    if compatibility.get("status") != "PASS":
        raise BbkError(f"Profile is incompatible with this BBK/Python environment: {compatibility}")


def _profile_identity(profile: dict[str, Any]) -> dict[str, Any]:
    verification = profile.get("package_verification") if isinstance(profile.get("package_verification"), dict) else {}
    return {
        "id": str(profile.get("id")),
        "version": str(profile.get("version")),
        "rootSha256": str(verification.get("root_sha256") or profile.get("manifest_sha256")),
        "manifestSha256": str(profile.get("manifest_sha256")),
    }


def _profile_operation_binding(profile: dict[str, Any], operation: str) -> dict[str, Any]:
    spec = PROFILE_CAPABILITY_OPERATION_SPEC.get(operation)
    if spec is None:
        raise BbkError(f"Unsupported profile capability operation: {operation}")
    manifest = profile.get("manifest") or {}
    capabilities = manifest.get("capabilities") if isinstance(manifest.get("capabilities"), dict) else {}
    capability = capabilities.get(spec["capability"])
    if not isinstance(capability, dict):
        legacy = (
            profile.get("validation", {}).get("stateDecisionEffectSupport", "legacy-summary")
            if spec["capability"] == "state_decision_effect"
            else profile.get("validation", {}).get("reviewAssuranceSupport", "legacy-no-review-manifest")
        )
        return {
            "status": "UNSUPPORTED", "capability": spec["capability"], "support": legacy,
            "entrypoint": None, "reason": f"profile does not declare {spec['capability']} capability",
        }
    support = str(capability.get("status", "unsupported")).lower().replace("_", "-")
    if support in {"unsupported", "legacy-summary", "legacy-no-review-manifest"}:
        return {
            "status": "UNSUPPORTED", "capability": spec["capability"], "support": support,
            "entrypoint": None, "reason": f"profile capability state is {support}",
        }
    if capability.get("dispatch_protocol") != "bbk.profile-capability.v1":
        return {
            "status": "UNSUPPORTED", "capability": spec["capability"], "support": support,
            "entrypoint": None,
            "reason": (
                "profile capability is a legacy alpha.7 declaration without the "
                "bbk.profile-capability.v1 dispatch protocol"
            ),
        }
    entrypoint = capability.get(spec["entrypoint_field"])
    entrypoints = manifest.get("entrypoints") if isinstance(manifest.get("entrypoints"), dict) else {}
    if not isinstance(entrypoint, str) or not isinstance(entrypoints.get(entrypoint), list):
        return {
            "status": "BLOCKED", "capability": spec["capability"], "support": support,
            "entrypoint": entrypoint,
            "reason": f"profile has no valid {spec['entrypoint_field']} binding",
        }
    return {
        "status": "READY", "capability": spec["capability"], "support": support,
        "entrypoint": entrypoint, "reason": None,
    }


def _artifact_ref(data: dict[str, Any], path: Path) -> str:
    for field in (
        "designId", "inventoryId", "contractId", "manifestId", "contextId", "runId",
        "attemptId", "receiptId", "findingId", "dispositionId", "fitId", "sliceId", "id",
    ):
        if data.get(field):
            identity = str(data[field])
            revision = data.get("revision")
            return f"{identity}@{revision}" if revision not in (None, "") else identity
    return path.name


def _bind_profile_input(
    kind: str,
    raw: str | None,
    *,
    validator: Any | None = None,
    validator_args: Sequence[Any] = (),
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not raw:
        return None, None
    path = Path(raw).expanduser().resolve()
    if not path.is_file():
        raise BbkError(f"Profile dispatch input is not a file: {path}")
    data = read_json(path)
    if validator is not None:
        report = validator(data, *validator_args)
        if not report.get("valid"):
            raise BbkError(f"Invalid {kind} input {path}: {report.get('errors')}")
    return {
        "kind": kind,
        "path": str(path),
        "sha256": sha256_file(path),
        "canonicalSha256": contract_digest(data),
        "schema": data.get("schema"),
        "ref": _artifact_ref(data, path),
    }, data


def _profile_dispatch_inputs(
    operation: str,
    *,
    state_effect: str | None = None,
    inventory: str | None = None,
    assurance: str | None = None,
    review_manifest: str | None = None,
    review_context: str | None = None,
    evidence_input: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    bound: list[dict[str, Any]] = []
    values: dict[str, dict[str, Any]] = {}

    assurance_binding, assurance_data = _bind_profile_input(
        "assurance-contract", assurance, validator=validate_assurance_contract
    )
    if assurance_binding:
        bound.append(assurance_binding); values["assurance-contract"] = assurance_data or {}

    design_binding, design_data = _bind_profile_input(
        "state-decision-effect", state_effect, validator=validate_state_decision_effect
    )
    if design_binding:
        bound.append(design_binding); values["state-decision-effect"] = design_data or {}

    inventory_binding, inventory_data = _bind_profile_input("state-effect-inventory", inventory)
    if inventory_binding:
        bound.append(inventory_binding); values["state-effect-inventory"] = inventory_data or {}

    manifest_data: dict[str, Any] | None = None
    if review_manifest:
        path = Path(review_manifest).expanduser().resolve()
        manifest_data = read_json(path)
        report = validate_review_manifest(manifest_data, assurance_data)
        if not report.get("valid"):
            raise BbkError(f"Invalid review-manifest input {path}: {report.get('errors')}")
        bound.append({
            "kind": "review-manifest", "path": str(path), "sha256": sha256_file(path),
            "canonicalSha256": contract_digest(manifest_data), "schema": manifest_data.get("schema"),
            "ref": _artifact_ref(manifest_data, path),
        })
        values["review-manifest"] = manifest_data

    context_binding, context_data = _bind_profile_input(
        "review-context", review_context,
        validator=validate_review_context,
        validator_args=(manifest_data,) if manifest_data is not None else (),
    )
    if context_binding:
        bound.append(context_binding); values["review-context"] = context_data or {}

    evidence_binding, evidence_data = _bind_profile_input("evidence-input", evidence_input)
    if evidence_binding:
        bound.append(evidence_binding); values["evidence-input"] = evidence_data or {}

    required: dict[str, tuple[str, ...]] = {
        "state-effect": ("state-decision-effect",),
        "state-effect-inventory": ("state-decision-effect",),
        "state-effect-review": ("state-decision-effect", "state-effect-inventory"),
        "review-context": ("assurance-contract", "review-manifest"),
        "review-lens": ("assurance-contract", "review-manifest", "review-context"),
        "evidence-adapter": ("evidence-input",),
    }
    missing = [kind for kind in required[operation] if kind not in values]
    if missing:
        raise BbkError(f"Profile dispatch operation {operation} requires: {', '.join(missing)}")
    return bound, values


def _profile_dispatch_subject(
    operation: str,
    values: dict[str, dict[str, Any]],
    source_manifest: dict[str, Any],
) -> dict[str, Any]:
    if operation in {"review-context", "review-lens"}:
        subject = values["review-manifest"].get("subject") or {}
        digest = subject.get("digest")
        if isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest):
            return {
                "ref": str(subject.get("ref") or values["review-manifest"].get("manifestId")),
                "kind": str(subject.get("kind") or "review-subject"),
                "revision": str(subject.get("revision") or "unknown"),
                "digest": digest,
            }
    if operation == "evidence-adapter":
        source = values["evidence-input"]
        subject = source.get("subject") if isinstance(source.get("subject"), dict) else {}
        digest = subject.get("digest") or source.get("subjectDigest")
        if isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest):
            return {
                "ref": str(subject.get("ref") or source.get("subjectRef") or "evidence-subject"),
                "kind": str(subject.get("kind") or "evidence-subject"),
                "revision": str(subject.get("revision") or "unknown"),
                "digest": digest,
            }
    if operation in {"state-effect", "state-effect-inventory", "state-effect-review"}:
        design = values["state-decision-effect"]
        return {
            "ref": _artifact_ref(design, Path("state-effect.json")),
            "kind": "state-decision-effect-design",
            "revision": str(design.get("revision") or "unknown"),
            "digest": contract_digest(design),
        }
    return {
        "ref": "source-tree",
        "kind": "source-tree",
        "revision": str((source_manifest.get("git") or {}).get("head") or "working-tree"),
        "digest": str(source_manifest["content_sha256"]),
    }


def _profile_execution_receipt(executed: dict[str, Any]) -> dict[str, Any]:
    return {
        "argv": executed.get("argv"), "cwd": executed.get("cwd"),
        "returncode": executed.get("returncode"), "durationSeconds": executed.get("duration_seconds"),
        "timedOut": executed.get("timed_out"), "executable": executed.get("executable"),
        "stdoutSha256": sha256_bytes(str(executed.get("stdout") or "").encode("utf-8")),
        "stderrSha256": sha256_bytes(str(executed.get("stderr") or "").encode("utf-8")),
    }


def dispatch_profile_capability(
    profile: dict[str, Any],
    operation: str,
    *,
    source: Path,
    role: str,
    task_profile: str,
    assurance_tier: str,
    change_classes: Sequence[str] = (),
    hints: Sequence[str] = (),
    paths: Sequence[str] = (),
    lens_ids: Sequence[str] = (),
    assignment_ids: Sequence[str] = (),
    run_tools: bool = False,
    state_effect: str | None = None,
    inventory: str | None = None,
    assurance: str | None = None,
    review_manifest: str | None = None,
    review_context: str | None = None,
    evidence_input: str | None = None,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Dispatch one profile capability through a core-owned typed request.

    Dispatch is read-only toward the subject. ``run_tools`` permits only profile-qualified
    read-only inspection or evidence tooling; it never grants mutation or external effects.
    """
    binding = _profile_operation_binding(profile, operation)
    if binding["status"] != "READY":
        return {
            "schema": "bbk.profile-capability-dispatch.v1",
            "status": binding["status"], "bbkVersion": VERSION,
            "operation": operation, "capability": binding["capability"],
            "profile": {"id": profile.get("id"), "version": profile.get("version")},
            "support": binding["support"], "entrypoint": binding.get("entrypoint"),
            "reason": binding["reason"], "request": None, "result": None,
        }
    inputs, values = _profile_dispatch_inputs(
        operation, state_effect=state_effect, inventory=inventory, assurance=assurance,
        review_manifest=review_manifest, review_context=review_context, evidence_input=evidence_input,
    )
    source_manifest = collect_manifest(source)
    request_inputs: list[dict[str, Any]] = []
    runtime_inputs: list[tuple[Path, str]] = []
    for index, item in enumerate(inputs):
        runtime_path = Path(str(item["path"])).resolve()
        logical_path = f"inputs/{index:02d}-{re.sub(r'[^A-Za-z0-9._-]+', '-', str(item['kind']))}.json"
        request_inputs.append({**item, "path": logical_path})
        runtime_inputs.append((runtime_path, logical_path))
    git_info = source_manifest.get("git") if isinstance(source_manifest.get("git"), dict) else {}
    stable_git = {
        key: git_info.get(key)
        for key in ("available", "head", "branch", "dirty", "status_porcelain")
        if key in git_info
    }
    request_seed = {
        "schema": "bbk.profile-capability-request.v1",
        "operation": operation,
        "profile": _profile_identity(profile),
        "source": {
            "root": ".", "contentSha256": source_manifest["content_sha256"],
            "fileCount": source_manifest["file_count"], "git": stable_git,
        },
        "subject": _profile_dispatch_subject(operation, values, source_manifest),
        "inputs": request_inputs,
        "context": {
            "role": role, "taskProfile": task_profile, "assuranceTier": assurance_tier,
            "changeClasses": sorted(set(change_classes)), "hints": sorted(set(hints)),
            "paths": sorted(set(paths)), "lensIds": sorted(set(lens_ids)),
            "assignmentIds": sorted(set(assignment_ids)), "runTools": bool(run_tools),
        },
        "authority": {
            "readOnly": True, "mayMutateSubject": False, "mayGrantEffects": False,
            "runQualifiedReadOnlyTools": bool(run_tools),
        },
    }
    seed_digest = contract_digest(request_seed)
    request = {**request_seed, "requestId": f"PDR-{seed_digest[:20].upper()}"}
    request["requestDigest"] = contract_digest(request)
    request_validation = validate_profile_capability_request(request)
    if not request_validation.get("valid"):
        raise BbkError(f"Internal profile dispatch request is invalid: {request_validation.get('errors')}")
    with tempfile.TemporaryDirectory(prefix="bbk-profile-dispatch-") as temp:
        request_root = Path(temp)
        request_path = request_root / "request.json"
        for runtime_path, logical_path in runtime_inputs:
            destination = request_root / logical_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(runtime_path, destination)
        write_json(request_path, request)
        result, executed = run_profile_json(
            profile, str(binding["entrypoint"]), ["--request", str(request_path)], source, timeout,
            extra_env={"BBK_PROFILE_SOURCE_ROOT": str(source), "BBK_PROFILE_REQUEST_ROOT": str(request_root)},
        )
    result_validation = validate_profile_capability_result(
        result,
        expected_profile_id=str(profile["id"]),
        expected_profile_version=str(profile["version"]),
        expected_operation=operation,
        expected_request_digest=str(request["requestDigest"]),
    )
    if not result_validation.get("valid"):
        raise BbkError(
            f"Profile {profile.get('id')} returned an invalid {operation} result: "
            + "; ".join(result_validation.get("errors", []))
        )
    adapted_receipt_validation = None
    if operation == "evidence-adapter" and result.get("status") in {"PASS", "PASS_ADVISORY", "PARTIAL"}:
        payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}
        receipt = payload.get("receipt") if isinstance(payload.get("receipt"), dict) else payload
        adapted_receipt_validation = validate_evidence_receipt(receipt)
        if not adapted_receipt_validation.get("valid"):
            raise BbkError(
                "Profile evidence adapter did not return a valid EvidenceReceipt v2: "
                + "; ".join(adapted_receipt_validation.get("errors", []))
            )
        request_subject = request.get("subject") or {}
        receipt_subject = receipt.get("subject") or {}
        if (
            isinstance(request_subject.get("digest"), str)
            and request_subject.get("kind") != "source-tree"
            and receipt_subject.get("digest") != request_subject.get("digest")
        ):
            raise BbkError("Adapted EvidenceReceipt subject digest does not match the dispatch subject")
    return {
        "schema": "bbk.profile-capability-dispatch.v1",
        "status": str(result.get("status")), "bbkVersion": VERSION,
        "operation": operation, "capability": binding["capability"],
        "profile": _profile_identity(profile), "support": binding["support"],
        "entrypoint": binding["entrypoint"], "request": request,
        "requestValidation": request_validation,
        "execution": _profile_execution_receipt(executed),
        "result": result, "resultValidation": result_validation,
        "resultDigest": result_validation.get("digest"),
        "adaptedEvidenceValidation": adapted_receipt_validation,
    }


def _stable_profile_dispatch(result: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if key not in {"execution", "executions"}}


def compile_profile_capability_dispatch(
    profile: dict[str, Any],
    *,
    source: Path,
    role: str,
    task_profile: str,
    assurance_tier: str,
    run_tools: bool,
    timeout: float,
    change_classes: Sequence[str],
    hints: Sequence[str],
    paths: Sequence[str],
    state_effect_inputs: Sequence[dict[str, Any]],
    assurance_inputs: Sequence[dict[str, Any]],
    review_inputs: Sequence[dict[str, Any]],
    evidence_inputs: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Automatically dispatch typed profile capabilities for exact supplied inputs."""
    operations: list[dict[str, Any]] = []
    executions: list[dict[str, Any]] = []
    warnings: list[str] = []
    unhandled: list[dict[str, Any]] = []
    manifest = profile.get("manifest") if isinstance(profile.get("manifest"), dict) else {}
    capabilities = manifest.get("capabilities") if isinstance(manifest.get("capabilities"), dict) else {}

    def record(value: dict[str, Any]) -> dict[str, Any]:
        if value.get("execution"):
            executions.append({
                "operation": value.get("operation"),
                "requestId": (value.get("request") or {}).get("requestId"),
                **value["execution"],
            })
        operations.append(_stable_profile_dispatch(value))
        return value

    assurance_by_id = {str(item.get("id")): item for item in assurance_inputs if item.get("id")}
    assurance_by_digest = {str(item.get("digest")): item for item in assurance_inputs if item.get("digest")}

    with tempfile.TemporaryDirectory(prefix="bbk-profile-auto-dispatch-") as temp_raw:
        temp = Path(temp_raw)
        for index, item in enumerate(state_effect_inputs):
            design_path = str(item["path"])
            projection = record(dispatch_profile_capability(
                profile, "state-effect", source=source, role=role, task_profile=task_profile,
                assurance_tier=assurance_tier, change_classes=change_classes, hints=hints,
                paths=paths, run_tools=run_tools, state_effect=design_path, timeout=timeout,
            ))
            inventory = record(dispatch_profile_capability(
                profile, "state-effect-inventory", source=source, role=role, task_profile=task_profile,
                assurance_tier=assurance_tier, change_classes=change_classes, hints=hints,
                paths=paths, run_tools=run_tools, state_effect=design_path, timeout=timeout,
            ))
            payload = (inventory.get("result") or {}).get("payload") if isinstance(inventory.get("result"), dict) else None
            if isinstance(payload, dict) and inventory.get("status") not in {"UNSUPPORTED", "BLOCKED", "ERROR"}:
                inventory_path = temp / f"state-effect-inventory-{index}.json"
                write_json(inventory_path, payload)
                record(dispatch_profile_capability(
                    profile, "state-effect-review", source=source, role=role, task_profile=task_profile,
                    assurance_tier=assurance_tier, change_classes=change_classes, hints=hints,
                    paths=paths, run_tools=run_tools, state_effect=design_path,
                    inventory=str(inventory_path), timeout=timeout,
                ))
            else:
                warnings.append(f"state-effect review skipped for {item.get('id')}: no usable profile inventory payload")

        review_cap = capabilities.get("review_assurance") if isinstance(capabilities.get("review_assurance"), dict) else {}
        supported_lenses = set(review_cap.get("lens_ids") or [])
        for index, item in enumerate(review_inputs):
            manifest_path = str(item["path"])
            review = read_json(Path(manifest_path))
            ref = review.get("assuranceContract") or review.get("assuranceContractRef") or {}
            assurance_item = assurance_by_digest.get(str(ref.get("digest"))) or assurance_by_id.get(str(ref.get("ref") or ref.get("id")))
            if not assurance_item:
                warnings.append(f"review profile dispatch skipped for {item.get('id')}: exact AssuranceContract input not supplied")
                continue
            assurance_path = str(assurance_item["path"])
            context = record(dispatch_profile_capability(
                profile, "review-context", source=source, role=role, task_profile=task_profile,
                assurance_tier=assurance_tier, change_classes=change_classes, hints=hints,
                paths=paths, run_tools=run_tools, assurance=assurance_path,
                review_manifest=manifest_path, timeout=timeout,
            ))
            context_payload = (context.get("result") or {}).get("payload") if isinstance(context.get("result"), dict) else None
            if not isinstance(context_payload, dict) or context.get("status") in {"UNSUPPORTED", "BLOCKED", "ERROR"}:
                warnings.append(f"review lens dispatch skipped for {item.get('id')}: no usable profile context payload")
                continue
            context_path = temp / f"review-context-{index}.json"
            write_json(context_path, context_payload)
            for assignment in review.get("lensAssignments") or []:
                if not isinstance(assignment, dict):
                    continue
                lens = str(assignment.get("lens") or "")
                assignment_id = str(assignment.get("assignmentId") or "")
                if lens not in supported_lenses:
                    unhandled.append({"manifestId": item.get("id"), "assignmentId": assignment_id, "lens": lens})
                    continue
                record(dispatch_profile_capability(
                    profile, "review-lens", source=source, role=role, task_profile=task_profile,
                    assurance_tier=assurance_tier, change_classes=change_classes, hints=hints,
                    paths=paths, lens_ids=[lens], assignment_ids=[assignment_id], run_tools=run_tools,
                    assurance=assurance_path, review_manifest=manifest_path,
                    review_context=str(context_path), timeout=timeout,
                ))

        for item in evidence_inputs:
            record(dispatch_profile_capability(
                profile, "evidence-adapter", source=source, role=role, task_profile=task_profile,
                assurance_tier=assurance_tier, change_classes=change_classes, hints=hints,
                paths=paths, run_tools=run_tools, evidence_input=str(item["path"]), timeout=timeout,
            ))

    return {
        "schema": "bbk.profile-dispatch.v1", "bbkVersion": VERSION,
        "profile": _profile_identity(profile), "runTools": bool(run_tools),
        "operations": operations, "executions": executions,
        "unhandledReviewAssignments": unhandled, "warnings": warnings,
        "authorityDisclaimer": (
            "Profile dispatch is a read-only procedural projection. Generic BBK validation, "
            "assurance, evidence sufficiency, finding closure, and authority remain controlling."
        ),
    }


def cmd_profile_dispatch(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).expanduser().resolve() if args.root else (project_root(required=False) or Path.cwd().resolve())
    source = Path(args.source).expanduser().resolve() if args.source else root
    profile = find_profile(root, args.id, args.version, args.profile_dir)
    _require_profile_execution(profile, allow_unverified=args.allow_unverified)
    result = dispatch_profile_capability(
        profile, args.operation, source=source,
        role=args.role or "reviewer", task_profile=args.task_profile or "review",
        assurance_tier=args.assurance_tier or "material",
        change_classes=args.change_class or [], hints=args.hint or [], paths=args.path or [],
        lens_ids=args.lens_id or [], assignment_ids=args.assignment_id or [],
        run_tools=args.run_tools, state_effect=args.state_decision_effect,
        inventory=args.state_effect_inventory, assurance=args.assurance_contract,
        review_manifest=args.review_manifest, review_context=args.review_context,
        evidence_input=args.evidence_input, timeout=args.timeout,
    )
    if args.output:
        output = Path(args.output).expanduser().resolve()
        write_json(output, result); result["output"] = str(output)
    return result


def cmd_profile_resolve(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).expanduser().resolve() if args.root else (project_root(required=False) or Path.cwd().resolve())
    source = Path(args.source).expanduser().resolve() if args.source else root
    profile = find_profile(root, args.id, args.version, args.profile_dir)
    verification = profile.get("package_verification", {})
    if verification.get("status") != "PASS" and not args.allow_unverified:
        raise BbkError(f"Profile package verification is {verification.get('status')}; pass --allow-unverified only for deliberate local development")
    compatibility = profile.get("compatibility", {})
    if compatibility.get("status") != "PASS":
        raise BbkError(f"Profile is incompatible with this BBK/Python environment: {compatibility}")

    work_unit_report = None
    work_unit_data: dict[str, Any] | None = None
    if args.work_unit:
        work_unit_path = Path(args.work_unit).expanduser().resolve()
        work_unit_data = read_json(work_unit_path)
        work_unit_report = validate_work_unit(work_unit_data)
        if not work_unit_report.get("valid"):
            raise BbkError(f"Invalid work unit {work_unit_path}: {work_unit_report.get('errors')}")
        normalized = work_unit_report.get("normalized") or work_unit_data
        args.task_profile = args.task_profile or normalized.get("taskProfile")
        args.assurance_tier = args.assurance_tier or normalized.get("assuranceTier")
        args.role = args.role or normalized.get("role")

    task_profile = args.task_profile or "implementation"
    assurance_tier = args.assurance_tier or "routine"
    role = args.role or "worker"

    fit_reports: list[dict[str, Any]] = []
    fit_inputs: list[dict[str, Any]] = []
    for raw in args.solution_outcome_fit or []:
        path = Path(raw).expanduser().resolve(); data = read_json(path); report = validate_solution_outcome_fit(data)
        if not report.get("valid"):
            raise BbkError(f"Invalid SolutionOutcomeFit {path}: {report.get('errors')}")
        fit_reports.append(report)
        fit_inputs.append({
            "path": str(path), "digest": report.get("digest"), "id": data.get("fitId"),
            "revision": data.get("revision"), "disposition": (data.get("disposition") or {}).get("status"),
            "solutionCommitment": report.get("planningDisposition", {}).get("solutionCommitment"),
        })

    structure_reports: list[dict[str, Any]] = []
    structure_inputs: list[dict[str, Any]] = []
    for raw in args.structure_contract or []:
        path = Path(raw).expanduser().resolve(); data = read_json(path); report = validate_structure_v2(data)
        if not report.get("valid"):
            raise BbkError(f"Invalid ImplementationStructureContract {path}: {report.get('errors')}")
        structure_reports.append(report)
        structure_inputs.append({"path": str(path), "digest": report.get("digest"), "id": data.get("contractId"), "revision": data.get("revision")})

    slice_reports: list[dict[str, Any]] = []
    slice_inputs: list[dict[str, Any]] = []
    for raw in args.execution_slice or []:
        path = Path(raw).expanduser().resolve(); data = read_json(path); report = validate_slice_v2(data)
        if not report.get("valid"):
            raise BbkError(f"Invalid Execution Slice {path}: {report.get('errors')}")
        slice_reports.append(report)
        slice_inputs.append({"path": str(path), "digest": report.get("digest"), "id": data.get("sliceId"), "status": data.get("status")})

    state_effect_reports: list[dict[str, Any]] = []
    state_effect_inputs: list[dict[str, Any]] = []
    for raw in args.state_decision_effect or []:
        path = Path(raw).expanduser().resolve(); data = read_json(path); report = validate_state_decision_effect(data)
        if not report.get("valid"):
            raise BbkError(f"Invalid StateDecisionEffectDesign {path}: {report.get('errors')}")
        state_effect_reports.append(report)
        state_effect_inputs.append({"path": str(path), "digest": report.get("digest"), "id": data.get("designId"), "revision": data.get("revision"), "applicability": data.get("applicability")})

    assurance_reports: list[dict[str, Any]] = []
    assurance_inputs: list[dict[str, Any]] = []
    for raw in args.assurance_contract or []:
        path = Path(raw).expanduser().resolve(); data = read_json(path); report = validate_assurance_contract(data)
        if not report.get("valid"):
            raise BbkError(f"Invalid AssuranceContract {path}: {report.get('errors')}")
        assurance_reports.append(report)
        assurance_inputs.append({"path": str(path), "digest": report.get("digest"), "id": data.get("contractId"), "revision": data.get("revision"), "riskTier": data.get("riskTier")})

    review_reports: list[dict[str, Any]] = []
    review_inputs: list[dict[str, Any]] = []
    for raw in args.review_manifest or []:
        path = Path(raw).expanduser().resolve(); data = read_json(path)
        assurance = None
        assurance_ref = data.get("assuranceContract") or data.get("assuranceContractRef") or {}
        for candidate_path, candidate_report in zip(args.assurance_contract or [], assurance_reports):
            candidate = read_json(Path(candidate_path).expanduser().resolve())
            candidate_id = candidate.get("contractId") or candidate.get("assuranceContractId")
            candidate_digest = candidate_report.get("digest")
            if (
                (assurance_ref.get("ref") or assurance_ref.get("id")) == candidate_id
                or (assurance_ref.get("digest") and assurance_ref.get("digest") == candidate_digest)
            ):
                assurance = candidate; break
        report = validate_review_manifest(data, assurance)
        if not report.get("valid"):
            raise BbkError(f"Invalid ReviewManifest {path}: {report.get('errors')}")
        review_reports.append(report)
        review_inputs.append({"path": str(path), "digest": report.get("digest"), "id": data.get("manifestId"), "purpose": data.get("purpose"), "applicability": data.get("applicability")})

    evidence_inputs: list[dict[str, Any]] = []
    for raw in args.evidence_input or []:
        path = Path(raw).expanduser().resolve(); data = read_json(path)
        evidence_inputs.append({
            "path": str(path),
            "sha256": sha256_file(path),
            "digest": contract_digest(data),
            "id": data.get("receiptId") or data.get("id"),
            "schema": data.get("schema"),
        })

    committing_profiles = {"implementation", "interface-schema-migration", "integration", "integration-consumer-path", "packaging-release", "implementation-structure", "execution-slicing"}
    blocked_fits = [item for item in fit_inputs if item.get("solutionCommitment") == "BLOCKED"]
    if blocked_fits and task_profile in committing_profiles:
        identities = ", ".join(f"{item.get('id')}@{item.get('revision')}" for item in blocked_fits)
        raise BbkError(f"SolutionOutcomeFit blocks task profile {task_profile}: {identities}; use investigation/review work or resolve the fit")

    extra = ["--root", str(source)]
    if args.work_unit: extra += ["--work-unit", str(Path(args.work_unit).expanduser().resolve())]
    extra += ["--task-profile", task_profile, "--assurance-tier", assurance_tier, "--role", role]
    for value in args.change_class or []: extra += ["--change-class", value]
    for value in args.hint or []: extra += ["--hint", value]
    for value in args.path or []: extra += ["--path", value]
    if args.run_tools: extra.append("--run-tools")
    resolved, executed = run_profile_json(profile, "resolve", extra, source, args.timeout)

    manifest = profile.get("manifest") or {}
    support = ((manifest.get("capabilities") or {}).get("implementation_structure") if isinstance(manifest.get("capabilities"), dict) else None)
    support_status = profile.get("validation", {}).get("implementationStructureSupport", "legacy-unprojected")
    structure_projections: list[dict[str, Any]] = []
    slice_projections: list[dict[str, Any]] = []
    if structure_inputs and isinstance(support, dict) and support.get("status") in {"supported", "partial"} and isinstance((manifest.get("entrypoints") or {}).get("structure"), list):
        for item in structure_inputs:
            projection, _ = run_profile_json(profile, "structure", ["--contract", item["path"], "--role", role, "--task-profile", task_profile, "--assurance-tier", assurance_tier, "--root", str(source)], source, args.timeout)
            structure_projections.append(projection)
    if slice_inputs and isinstance(support, dict) and support.get("status") == "supported" and isinstance((manifest.get("entrypoints") or {}).get("slice"), list):
        for item in slice_inputs:
            projection, _ = run_profile_json(profile, "slice", ["--slice", item["path"], "--role", role, "--task-profile", task_profile, "--assurance-tier", assurance_tier, "--root", str(source)], source, args.timeout)
            slice_projections.append(projection)

    profile_dispatch = compile_profile_capability_dispatch(
        profile,
        source=source,
        role=role,
        task_profile=task_profile,
        assurance_tier=assurance_tier,
        run_tools=bool(args.run_tools),
        timeout=args.timeout,
        change_classes=args.change_class or [],
        hints=args.hint or [],
        paths=args.path or [],
        state_effect_inputs=state_effect_inputs,
        assurance_inputs=assurance_inputs,
        review_inputs=review_inputs,
        evidence_inputs=evidence_inputs,
    )

    inputs = {
        "role": role, "taskProfile": task_profile, "assuranceTier": assurance_tier,
        "changeClasses": args.change_class or [], "hints": args.hint or [], "paths": args.path or [],
        "workUnit": str(Path(args.work_unit).expanduser().resolve()) if args.work_unit else None,
        "solutionOutcomeFits": fit_inputs, "structureContracts": structure_inputs, "executionSlices": slice_inputs,
        "stateDecisionEffectDesigns": state_effect_inputs, "assuranceContracts": assurance_inputs, "reviewManifests": review_inputs,
        "evidenceInputs": evidence_inputs,
    }
    result = {
        "schema": "bbk.profile-resolution-wrapper.v3", "bbk_version": VERSION,
        "profile": {key: value for key, value in profile.items() if key != "manifest"},
        "source_root": str(source), "inputs": inputs, "resolver": executed, "resolution": resolved,
        "solution_outcome_fit": {"reports": fit_reports},
        "implementation_structure": {
            "support": support_status, "contract_reports": structure_reports, "slice_reports": slice_reports,
            "profile_projections": structure_projections, "profile_slice_projections": slice_projections,
        },
        "state_decision_effect": {
            "support": profile.get("validation", {}).get("stateDecisionEffectSupport", "legacy-summary"),
            "reports": state_effect_reports,
        },
        "review_assurance": {
            "support": profile.get("validation", {}).get("reviewAssuranceSupport", "legacy-no-review-manifest"),
            "assurance_reports": assurance_reports, "manifest_reports": review_reports,
            "evidence_inputs": evidence_inputs,
        },
        "profile_dispatch": profile_dispatch,
        "work_unit_report": work_unit_report,
    }
    stable_result = {key: value for key, value in result.items() if key not in {"resolver", "effective_sha256"}}
    stable_result["profile_dispatch"] = _stable_profile_dispatch(profile_dispatch)
    result["effective_sha256"] = sha256_bytes(canonical_bytes(stable_result))
    # Alpha.4/5 spelling retained for compatibility.
    result["effectiveDigest"] = result["effective_sha256"]

    if args.write_lock:
        if not (root / ".bbk" / "config.json").is_file():
            raise BbkError("--write-lock requires an initialized BBK project root")
        lock_path = Path(args.lock_path).expanduser().resolve() if args.lock_path else root / ".bbk" / "profile-lock.json"
        profile_root_digest = verification.get("root_sha256") or profile.get("manifest_sha256")
        profile_record = {
            "id": profile.get("id"), "version": profile.get("version"), "root": profile.get("root"),
            "profile_root_sha256": profile_root_digest, "manifest_sha256": profile.get("manifest_sha256"),
            "inputs": inputs, "resolution": resolved,
            "capability_dispatch": _stable_profile_dispatch(profile_dispatch),
            "capability_dispatch_sha256": sha256_bytes(canonical_bytes(_stable_profile_dispatch(profile_dispatch))),
        }
        lock = {
            "schema": "bbk.profile-lock.v1", "generated_at": utc_now(), "profiles": [profile_record],
            "effective_sha256": result["effective_sha256"],
            "bbkVersion": VERSION, "profileId": profile.get("id"), "profileVersion": profile.get("version"),
            "profileRootDigest": profile_root_digest, "effectiveDigest": result["effective_sha256"],
            "inputs": inputs, "resolution": result,
        }
        write_json(lock_path, lock)
        result["lock_path"] = str(lock_path)
    return result



def _report_status(report: dict[str, Any]) -> dict[str, Any]:
    value = dict(report)
    if "status" not in value:
        value["status"] = "PASS" if value.get("valid", True) else "FAIL"
    return value


def _template_path(name: str) -> Path:
    path = TEMPLATE_DIR / name
    if not path.is_file():
        raise BbkError(f"BBK template is unavailable: {path}")
    return path


def _write_new_from_template(template: str, output: str, *, force: bool = False) -> dict[str, Any]:
    source = _template_path(template)
    destination = Path(output).expanduser().resolve()
    if destination.exists() and not force:
        raise BbkError(f"Refusing to overwrite {destination}; pass --force to replace it")
    atomic_write(destination, source.read_bytes())
    return {
        "schema": "bbk.template-created.v1", "status": "PASS", "template": template,
        "output": str(destination), "sha256": sha256_file(destination),
    }


def _render_result(kind: str, source: Path, report: dict[str, Any], content: str, fmt: str, output: str | None) -> dict[str, Any]:
    if not report.get("valid"):
        return _report_status(report)
    written = None
    if output:
        destination = Path(output).expanduser().resolve()
        atomic_write(destination, content.encode("utf-8"))
        written = str(destination)
    return {
        "schema": "bbk.render-result.v1", "status": "PASS", "kind": kind,
        "source": str(source), "format": fmt, "content": content, "output": written,
        "source_digest": report.get("digest"),
    }


def cmd_digest(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.path).expanduser().resolve()
    if not path.is_file():
        raise BbkError(f"Not a regular file: {path}")
    return {"schema": "bbk.digest.v1", "status": "PASS", "path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def _artifact_manifest_candidates(
    root: Path,
    raw_paths: Sequence[str],
    *,
    includes: Sequence[str],
    excludes: Sequence[str],
    include_examples: bool,
    output: Path | None,
) -> list[Path]:
    root = root.resolve()
    selected: dict[str, Path] = {}
    output_resolved = output.resolve() if output is not None else None

    def add_file(candidate: Path) -> None:
        if candidate.is_symlink():
            raise BbkError(f"Artifact manifests do not follow symlinks: {candidate}")
        resolved = candidate.resolve(strict=True)
        try:
            relative = resolved.relative_to(root).as_posix()
        except ValueError as exc:
            raise BbkError(f"Artifact path escapes the declared project root: {candidate}") from exc
        if output_resolved is not None and resolved == output_resolved:
            return
        if not include_examples and is_non_operational_example(resolved):
            return
        if includes and not any(fnmatch.fnmatch(relative, pattern) for pattern in includes):
            return
        if any(fnmatch.fnmatch(relative, pattern) for pattern in excludes):
            return
        selected[relative] = resolved

    for raw in raw_paths:
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
        if candidate.is_symlink():
            raise BbkError(f"Artifact manifests do not follow symlinks: {candidate}")
        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError as exc:
            raise BbkError(f"Artifact path does not exist: {candidate}") from exc
        except OSError as exc:
            raise BbkError(f"Unable to resolve artifact path {candidate}: {exc}") from exc
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise BbkError(f"Artifact path escapes the declared project root: {candidate}") from exc
        if resolved.is_file():
            add_file(resolved)
            continue
        if not resolved.is_dir():
            raise BbkError(f"Artifact path is not a regular file or directory: {resolved}")
        for child in sorted(resolved.rglob("*")):
            if child.is_symlink():
                raise BbkError(f"Artifact manifests do not follow symlinks: {child}")
            if child.is_file():
                add_file(child)
    return [selected[key] for key in sorted(selected)]


def _artifact_manifest_content(
    root: Path,
    paths: Sequence[Path],
    *,
    subject: str | None,
    root_label: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = artifact_build_legacy_manifest(
        root,
        paths,
        subject=subject,
        root_label=root_label,
        bbk_version=VERSION,
    )
    content = {
        "schema": "bbk.artifact-manifest-content.v1",
        "subject": subject,
        "root_label": root_label,
        "files": manifest["files"],
    }
    return content, manifest


def cmd_artifact_manifest(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_root(args.root, required=False) or Path.cwd().resolve()
    if not root.is_dir():
        raise BbkError(f"Artifact manifest root is not a directory: {root}")
    raw_paths = list(args.path or []) + list(args.source or [])
    if not raw_paths:
        raw_paths = ["."]
    output: Path | None = None
    if args.output:
        output = Path(args.output).expanduser()
        if not output.is_absolute():
            output = root / output
        output = output.resolve()
    paths = _artifact_manifest_candidates(
        root,
        raw_paths,
        includes=list(args.include or []),
        excludes=list(args.exclude or []),
        include_examples=bool(args.include_examples),
        output=output,
    )
    _, manifest = _artifact_manifest_content(
        root,
        paths,
        subject=args.subject,
        root_label=args.root_label or "project",
    )
    if output is not None:
        write_json(output, manifest)
        manifest["written_to"] = str(output)
    manifest["status"] = "PASS"
    return manifest


def cmd_artifact_preflight(args: argparse.Namespace) -> dict[str, Any]:
    registry = Path(args.registry).expanduser().resolve() if args.registry else None
    return artifact_preflight_draft(
        Path(args.draft_root).expanduser(),
        registry_path=registry,
        max_depth=int(args.max_depth),
    )


def _artifact_reject_stale_lock_takeover(args: argparse.Namespace) -> dict[str, Any] | None:
    if not bool(getattr(args, "recover_stale_lock", False)):
        return None
    return {
        "schema": "bbk.artifact-package-cli-result.v1",
        "status": "REJECTED",
        "code": "PACKAGE_LOCK_RECOVERY_REQUIRES_RECONCILE",
        "message": "Stale-lock age never authorizes takeover; reconcile the exact operation journal.",
        "smallest_next_action": "Run bbk artifact reconcile with the exact journal path or operation ID.",
        "claims_not_established": ["transaction completion", "publication", "semantic acceptance"],
    }


def cmd_artifact_doctor(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        raise invalid_argument_error(
            "Artifact doctor root is not an existing directory.",
            field="root",
            received=args.root,
            example_command="bbk artifact doctor --root .",
            documentation_command="bbk artifact doctor --help",
            smallest_next_action="Provide an existing local project or transaction root.",
        )
    target_parent = None
    if args.publication_root:
        target_parent = Path(args.publication_root).expanduser()
        if not target_parent.is_absolute():
            target_parent = root / target_parent
    return artifact_doctor(root, target_parent)


def cmd_artifact_reconcile(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_root(args.root, required=False) or Path.cwd().resolve()
    raw = Path(args.journal_or_operation).expanduser()
    journal = raw if raw.is_absolute() else root / raw
    if not journal.is_file() and SAFE_ID.fullmatch(args.journal_or_operation):
        journal = root / ".bbk" / "artifacts" / "operations" / f"{args.journal_or_operation}.json"
    if not journal.is_file():
        raise invalid_argument_error(
            "The exact operation journal or operation ID does not resolve to a file.",
            field="journal_or_operation",
            received=args.journal_or_operation,
            example_command="bbk artifact reconcile <journal-or-operation-id> --root .",
            documentation_command="bbk artifact reconcile --help",
            smallest_next_action="Provide the exact existing journal path or operation ID under .bbk/artifacts/operations.",
        )
    return artifact_reconcile_operation(journal, resume=bool(args.resume))


def cmd_artifact_seal(args: argparse.Namespace) -> dict[str, Any]:
    rejected = _artifact_reject_stale_lock_takeover(args)
    if rejected is not None:
        return rejected
    registry = Path(args.registry).expanduser().resolve() if args.registry else None
    try:
        return artifact_seal_draft(
            Path(args.draft_root).expanduser(),
            Path(args.output).expanduser(),
            registry_path=registry,
            recover_stale_lock=bool(args.recover_stale_lock),
        )
    except ArtifactPackageError as exc:
        return exc.as_dict()


def cmd_artifact_finalize(args: argparse.Namespace) -> dict[str, Any]:
    rejected = _artifact_reject_stale_lock_takeover(args)
    if rejected is not None:
        return rejected
    registry = Path(args.registry).expanduser().resolve() if args.registry else None
    root = resolve_root(args.root, required=False) or Path.cwd().resolve()
    try:
        if args.draft_root:
            return artifact_finalize_draft(
                Path(args.draft_root).expanduser(),
                Path(args.output).expanduser() if args.output else None,
                project_root=root,
                publication_root=Path(args.publication_root).expanduser() if args.publication_root else None,
                registry_path=registry,
                allow_mutable_coordination=bool(args.allow_mutable_coordination),
                write_current_pointer=not bool(args.no_current_pointer),
                recover_stale_lock=bool(args.recover_stale_lock),
            )
        if not args.package_id or not args.revision:
            raise invalid_argument_error(
                "Provide a draft root, or use one-shot software mode with --package-id and --revision. The source set defaults to the project root when --source is omitted.",
                field="finalization_mode",
                received={
                    "draft_root": args.draft_root,
                    "package_id": args.package_id,
                    "revision": args.revision,
                    "source_count": len(args.source or []),
                },
                valid_values=[
                    "<draft-root>",
                    "--package-id <id> --revision <revision> [--source <path> ...]",
                ],
                example_command="bbk artifact finalize --root . --package-id my-tool --revision r1",
                documentation_command="bbk artifact finalize --help",
                smallest_next_action="Choose one complete finalization mode and rerun the command.",
            )
        return artifact_finalize_source_set(
            project_root=root,
            package_id=args.package_id,
            revision=args.revision,
            sources=args.source or ["."],
            includes=args.include or [],
            excludes=args.exclude or [],
            subject_kind=args.subject_kind or "software-implementation",
            subject_id=args.subject_id,
            subject_revision=args.subject_revision,
            purpose=args.purpose,
            output_root=Path(args.output).expanduser() if args.output else None,
            publication_root=Path(args.publication_root).expanduser() if args.publication_root else None,
            registry_path=registry,
            write_current_pointer=not bool(args.no_current_pointer),
            recover_stale_lock=bool(args.recover_stale_lock),
        )
    except ArtifactPackageError as exc:
        return exc.as_dict()


def cmd_artifact_freshness(args: argparse.Namespace) -> dict[str, Any]:
    registry = Path(args.registry).expanduser().resolve() if args.registry else None
    root = resolve_root(args.root, required=False) or Path.cwd().resolve()
    return artifact_verify_publication_freshness(
        Path(args.subject).expanduser(),
        project_root=root,
        registry_path=registry,
    )


def cmd_artifact_successor(args: argparse.Namespace) -> dict[str, Any]:
    rejected = _artifact_reject_stale_lock_takeover(args)
    if rejected is not None:
        return rejected
    registry = Path(args.registry).expanduser().resolve() if args.registry else None
    try:
        return artifact_create_successor(
            Path(args.sealed_root).expanduser(),
            Path(args.output).expanduser(),
            revision=args.revision,
            reason=args.reason,
            registry_path=registry,
            recover_stale_lock=bool(args.recover_stale_lock),
        )
    except ArtifactPackageError as exc:
        return exc.as_dict()


def cmd_artifact_verify(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_root(args.root, required=False) or Path.cwd().resolve()
    subject = Path(args.manifest).expanduser()
    if not subject.is_absolute():
        subject = root / subject
    subject = subject.resolve()
    registry = Path(args.registry).expanduser().resolve() if getattr(args, "registry", None) else None
    if subject.is_dir():
        return artifact_verify_package(subject, registry_path=registry)
    manifest = read_json(subject)
    if isinstance(manifest, dict) and manifest.get("schema") == "bbk.artifact-package-manifest.v1":
        return artifact_verify_package(subject.parent, registry_path=registry)
    if not isinstance(manifest, dict) or manifest.get("schema") != "bbk.artifact-manifest.v1":
        raise BbkError(f"Not a BBK legacy artifact manifest or sealed package: {subject}")
    result = artifact_verify_legacy_manifest(manifest, root=root)
    result.update({"manifest": str(subject), "root": str(root)})
    return result



def _resolve_input_path(root: Path, raw: str, *, label: str) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = root / path
    try:
        return path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise BbkError(f"{label} does not exist: {path}") from exc


def cmd_preflight_run(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_root(args.root, required=False) or Path.cwd().resolve()
    request_path = _resolve_input_path(root, args.request, label="host preflight request")
    try:
        request = strict_load_path(request_path)
        cache_dir = Path(args.cache_dir).expanduser() if args.cache_dir else root / ".bbk" / "cache" / "host-preflight"
        if not cache_dir.is_absolute():
            cache_dir = root / cache_dir
        result = run_preflight(request, cache_dir=cache_dir, use_cache=not args.no_cache, timeout=args.timeout)
    except (HostPreflightError, StrictJsonError, OSError, ValueError) as exc:
        raise BbkError(str(exc)) from exc
    if args.output:
        output = Path(args.output).expanduser()
        if not output.is_absolute():
            output = root / output
        write_json(output, result)
        result["writtenTo"] = str(output.resolve())
    return result


def cmd_context_worker(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_root(args.root, required=False) or Path.cwd().resolve()
    try:
        work_unit = strict_load_path(_resolve_input_path(root, args.work_unit, label="WorkUnit"))
        profile_lock = strict_load_path(_resolve_input_path(root, args.profile_lock, label="profile lock"))
        host_preflight = strict_load_path(_resolve_input_path(root, args.host_preflight, label="host preflight"))
        prototype = strict_load_path(_resolve_input_path(root, args.prototype_charter, label="prototype charter")) if args.prototype_charter else None
    except (StrictJsonError, OSError, ValueError) as exc:
        raise BbkError(str(exc)) from exc
    work_id = work_unit.get("id", "unknown") if isinstance(work_unit, dict) else "unknown"
    output = Path(args.output).expanduser() if args.output else root / ".bbk" / "contexts" / "workers" / f"WC-{work_id}"
    if not output.is_absolute():
        output = root / output
    try:
        return compile_worker_context(work_unit, profile_lock, host_preflight, output_root=output, package_id=args.id, revision=args.revision, prototype_charter=prototype)
    except (ContextPackageError, ArtifactPackageError, OSError, ValueError) as exc:
        diagnostic = exc.result if isinstance(exc, ArtifactPackageError) else None
        raise BbkError(str(exc), diagnostic=diagnostic) from exc


def cmd_context_review(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_root(args.root, required=False) or Path.cwd().resolve()
    candidate = _resolve_input_path(root, args.candidate, label="sealed candidate")
    try:
        request = strict_load_path(_resolve_input_path(root, args.request, label="review package request"))
    except (StrictJsonError, OSError, ValueError) as exc:
        raise BbkError(str(exc)) from exc
    output = Path(args.output).expanduser() if args.output else root / ".bbk" / "reviews" / "packages" / (args.id or f"RP-{candidate.name}")
    if not output.is_absolute():
        output = root / output
    try:
        return compile_review_package(candidate, request, output_root=output, package_id=args.id, revision=args.revision)
    except (ContextPackageError, ArtifactPackageError, OSError, ValueError) as exc:
        diagnostic = exc.result if isinstance(exc, ArtifactPackageError) else None
        raise BbkError(str(exc), diagnostic=diagnostic) from exc



def _artifact_identity(value: Mapping[str, Any]) -> dict[str, Any]:
    fields = (
        "schema", "id", "contractId", "fitId", "designId", "sliceId", "manifestId",
        "contextId", "runId", "attemptId", "receiptId", "findingId", "dispositionId",
        "work_unit_id", "candidate_id", "revision", "status",
    )
    return {field: value.get(field) for field in fields if value.get(field) is not None}


def cmd_artifact_inspect(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.path).expanduser().resolve()
    if not path.exists() and not path.is_symlink():
        raise BbkError(f"Artifact does not exist: {path}")
    if path.is_dir():
        manifest = collect_manifest(path, args.exclude, include_examples=bool(args.include_examples))
        result: dict[str, Any] = {
            "schema": "bbk.artifact-inspection.v1",
            "status": "PASS",
            "kind": "directory",
            "path": str(path),
            "content_sha256": manifest.get("content_sha256"),
            "file_count": len(manifest.get("files", [])),
            "examples_excluded": manifest.get("examples_excluded", 0),
            "manifest": manifest if args.verbose else None,
        }
    elif path.is_symlink():
        target = os.readlink(path)
        result = {
            "schema": "bbk.artifact-inspection.v1", "status": "PASS", "kind": "symlink",
            "path": str(path), "target": target, "sha256": sha256_bytes(target.encode("utf-8")),
        }
    elif path.is_file():
        data = path.read_bytes()
        result = {
            "schema": "bbk.artifact-inspection.v1", "status": "PASS", "kind": "file",
            "path": str(path), "bytes": len(data), "sha256": sha256_bytes(data),
            "executable": bool(path.stat().st_mode & stat.S_IXUSR),
            "example": is_non_operational_example(path),
        }
        try:
            value = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            value = None
        if isinstance(value, Mapping):
            result["json"] = {
                "canonical_sha256": sha256_bytes(canonical_bytes(value)),
                "identity": _artifact_identity(value),
            }
    else:
        raise BbkError(f"Unsupported artifact type: {path}")
    if args.output:
        output = Path(args.output).expanduser().resolve()
        write_json(output, result)
        result["output"] = str(output)
    return result


def cmd_fit_validate(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.path).expanduser().resolve()
    return _report_status(validate_solution_outcome_fit(read_json(path)))


def cmd_fit_render(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.path).expanduser().resolve()
    data = read_json(path)
    report = validate_solution_outcome_fit(data)
    content = markdown_solution_outcome_fit(data) if args.format == "markdown" else json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    return _render_result("solution-outcome-fit", path, report, content, args.format, args.output)


def cmd_fit_new(args: argparse.Namespace) -> dict[str, Any]:
    return _write_new_from_template("solution-outcome-fit.json", args.output, force=args.force)


def _fit_ref_matches(refs: list[Any], fit_id: str, revision: str) -> bool:
    identity = f"{fit_id}@{revision}"
    return identity in refs or fit_id in refs


def cmd_fit_check_chain(args: argparse.Namespace) -> dict[str, Any]:
    fit_path = Path(args.fit).expanduser().resolve()
    fit = read_json(fit_path)
    fit_report = validate_solution_outcome_fit(fit)
    errors = [f"fit: {value}" for value in fit_report["errors"]]
    warnings = [f"fit: {value}" for value in fit_report["warnings"]]
    fit_id = str(fit.get("fitId") or "")
    revision = str(fit.get("revision") or "")
    identity = f"{fit_id}@{revision}"
    outcome_ids = {str(value.get("id")) for value in fit.get("desiredOutcomes", []) if isinstance(value, dict)}
    chain: dict[str, list[dict[str, Any]]] = {"structures": [], "slices": [], "workUnits": []}

    for raw in args.structure or []:
        path = Path(raw).expanduser().resolve(); data = read_json(path); report = validate_structure_v2(data)
        errors.extend([f"structure {path.name}: {message}" for message in report["errors"]])
        warnings.extend([f"structure {path.name}: {message}" for message in report["warnings"]])
        subject = data.get("subject") if isinstance(data.get("subject"), dict) else {}
        refs = list(subject.get("solutionOutcomeFitRefs") or [])
        outcomes = {str(item) for item in subject.get("outcomeRefs") or []}
        if not _fit_ref_matches(refs, fit_id, revision): errors.append(f"structure {path.name} does not reference SolutionOutcomeFit {identity}")
        unknown = sorted(outcomes - outcome_ids)
        if unknown: errors.append(f"structure {path.name} references outcomes not present in fit: {unknown}")
        if not outcomes: errors.append(f"structure {path.name} names no outcomeRefs")
        chain["structures"].append({"path": str(path), "id": data.get("contractId"), "revision": data.get("revision"), "digest": report.get("digest"), "outcomeRefs": sorted(outcomes)})

    for raw in args.slice or []:
        path = Path(raw).expanduser().resolve(); data = read_json(path); report = validate_slice(data)
        errors.extend([f"slice {path.name}: {message}" for message in report["errors"]])
        warnings.extend([f"slice {path.name}: {message}" for message in report["warnings"]])
        refs = list(data.get("solutionOutcomeFitRefs") or [])
        outcomes = {str(item) for item in data.get("outcomeRefs") or []}
        if not _fit_ref_matches(refs, fit_id, revision): errors.append(f"slice {path.name} does not reference SolutionOutcomeFit {identity}")
        unknown = sorted(outcomes - outcome_ids)
        if unknown: errors.append(f"slice {path.name} references outcomes not present in fit: {unknown}")
        if not outcomes: errors.append(f"slice {path.name} names no outcomeRefs")
        chain["slices"].append({"path": str(path), "id": data.get("sliceId"), "digest": report.get("digest"), "outcomeRefs": sorted(outcomes)})

    for raw in args.work_unit or []:
        path = Path(raw).expanduser().resolve(); data = read_json(path); report = validate_work_unit(data)
        errors.extend([f"work unit {path.name}: {message}" for message in report["errors"]])
        warnings.extend([f"work unit {path.name}: {message}" for message in report["warnings"]])
        normalized = report.get("normalized") or data
        refs = list(normalized.get("solutionOutcomeFitRefs") or [])
        outcomes = {str(item) for item in normalized.get("supportedOutcomeRefs") or []}
        if not _fit_ref_matches(refs, fit_id, revision): errors.append(f"work unit {path.name} does not reference SolutionOutcomeFit {identity}")
        unknown = sorted(outcomes - outcome_ids)
        if unknown: errors.append(f"work unit {path.name} references outcomes not present in fit: {unknown}")
        if not outcomes: errors.append(f"work unit {path.name} names no supportedOutcomeRefs")
        chain["workUnits"].append({"path": str(path), "id": normalized.get("id"), "digest": report.get("digest"), "outcomeRefs": sorted(outcomes)})

    downstream_count = sum(len(values) for values in chain.values())
    commitment = fit_report.get("planningDisposition", {}).get("solutionCommitment")
    if downstream_count and commitment == "BLOCKED": errors.append("SolutionOutcomeFit blocks material solution commitment but downstream planning artifacts were supplied")
    declared_work = {str(value) for value in (fit.get("traceability") or {}).get("workUnitRefs", [])}
    supplied_work = {str(value.get("id")) for value in chain["workUnits"] if value.get("id")}
    if declared_work and supplied_work and not supplied_work.issubset(declared_work): warnings.append(f"supplied work units are not all declared in fit traceability: {sorted(supplied_work - declared_work)}")
    result = {
        "schema": "bbk.solution-outcome-fit-chain-check.v1",
        "fit": {"path": str(fit_path), "identity": identity, "digest": fit_report.get("digest"), "planningDisposition": fit_report.get("planningDisposition")},
        "chain": chain, "chainDigest": contract_digest({"fit": fit_report.get("digest"), **chain}),
        "valid": not errors, "errors": errors, "warnings": warnings,
    }
    return _report_status(result)


def cmd_assurance_validate(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.path).expanduser().resolve()
    return _report_status(validate_assurance_contract(read_json(path)))


def cmd_assurance_new(args: argparse.Namespace) -> dict[str, Any]:
    return _write_new_from_template("assurance-contract.json", args.output, force=args.force)


def cmd_sde_validate(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.path).expanduser().resolve()
    return _report_status(validate_state_decision_effect(read_json(path)))


def cmd_sde_render(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.path).expanduser().resolve(); data = read_json(path); report = validate_state_decision_effect(data)
    content = markdown_state_decision_effect(data) if args.format == "markdown" else json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    return _render_result("state-decision-effect-design", path, report, content, args.format, args.output)


def cmd_sde_new(args: argparse.Namespace) -> dict[str, Any]:
    return _write_new_from_template("state-decision-effect-design.json", args.output, force=args.force)


def cmd_trace_validate(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.path).expanduser().resolve()
    return _report_status(validate_transition_trace(read_json(path)))


def cmd_trace_new(args: argparse.Namespace) -> dict[str, Any]:
    return _write_new_from_template("state-transition-trace.json", args.output, force=args.force)


def cmd_trace_check_set(args: argparse.Namespace) -> dict[str, Any]:
    design = read_json(Path(args.design).expanduser().resolve()) if args.design else None
    values = [read_json(Path(raw).expanduser().resolve()) for raw in args.trace]
    result = validate_transition_trace_set(values, design)
    result["schema"] = "bbk.state-transition-trace-set-result.v1"
    return _report_status(result)


def cmd_structure_validate(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.path).expanduser().resolve()
    return _report_status(validate_structure_v2(read_json(path)))


def cmd_structure_render(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.path).expanduser().resolve(); data = read_json(path); report = validate_structure_v2(data)
    if args.format == "markdown":
        content = markdown_structure(data)
        if data.get("schema") in {"bbk.implementation-structure-contract.v2", "bbk.implementation-structure-contract.v3"} and data.get("stateDecisionEffectDesign") is not None:
            content += "\n" + markdown_state_decision_effect(data.get("stateDecisionEffectDesign") or {})
    else:
        content = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    return _render_result("implementation-structure-contract", path, report, content, args.format, args.output)


def cmd_structure_new(args: argparse.Namespace) -> dict[str, Any]:
    if args.version == "v1":
        template = "implementation-structure-contract.json"
    elif args.version == "v2":
        template = "implementation-structure-contract-v2.json"
    elif args.depth == "compact" and args.kind in {"infrastructure", "network_configuration", "deployment_configuration"}:
        template = "implementation-structure-contract-v3-infrastructure-compact.json"
    else:
        template = "implementation-structure-contract-v3.json"
    result = _write_new_from_template(template, args.output, force=args.force)
    path = Path(args.output).expanduser().resolve()
    data = read_json(path)
    data.setdefault("subject", {})["kind"] = args.kind
    if args.version == "v3":
        data["contractDepth"] = args.depth
        if args.kind in {"infrastructure", "network_configuration", "deployment_configuration"} and args.depth == "compact":
            data.setdefault("metadata", {})["template"] = "compact-infrastructure"
    write_json(path, data)
    result["sha256"] = sha256_file(path)
    result["version"] = args.version
    result["subject_kind"] = args.kind
    result["contract_depth"] = args.depth if args.version == "v3" else "legacy"
    return result


def cmd_structure_review(args: argparse.Namespace) -> dict[str, Any]:
    contract_path = Path(args.contract).expanduser().resolve(); contract = read_json(contract_path)
    if contract.get("schema") not in {"bbk.implementation-structure-contract.v2", "bbk.implementation-structure-contract.v3"} or contract.get("stateDecisionEffectDesign") is None:
        raise BbkError("State–Decision–Effect inventory review requires an ImplementationStructureContract v2 or v3 with stateDecisionEffectDesign")
    inventory_path = Path(args.inventory).expanduser().resolve(); inventory = read_json(inventory_path)
    result = compare_state_effect_inventory(contract.get("stateDecisionEffectDesign") or {}, inventory)
    validation = validate_structure_review_v2(result)
    if not validation["valid"]:
        result["validationErrors"] = validation["errors"]
        result["disposition"] = "blocked"
    if args.output:
        write_json(Path(args.output).expanduser().resolve(), result)
        result["output"] = str(Path(args.output).expanduser().resolve())
    return _report_status({**result, "valid": validation["valid"], "errors": validation["errors"], "warnings": validation["warnings"]})


def cmd_slice_validate(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.path).expanduser().resolve()
    return _report_status(validate_slice_v2(read_json(path)))


def cmd_slice_render(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.path).expanduser().resolve(); data = read_json(path); report = validate_slice_v2(data)
    content = markdown_slice(data) if args.format == "markdown" else json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    return _render_result("execution-slice", path, report, content, args.format, args.output)


def cmd_slice_new(args: argparse.Namespace) -> dict[str, Any]:
    template = "execution-slice-v2.json" if args.version == "v2" else "execution-slice.json"
    return _write_new_from_template(template, args.output, force=args.force)


def cmd_slice_check_set(args: argparse.Namespace) -> dict[str, Any]:
    contract_path = Path(args.contract).expanduser().resolve(); contract = read_json(contract_path)
    values = [read_json(Path(raw).expanduser().resolve()) for raw in args.slice]
    if contract.get("schema") in {"bbk.implementation-structure-contract.v2", "bbk.implementation-structure-contract.v3"} or any(value.get("schema") == "bbk.execution-slice.v2" for value in values):
        errors: list[str] = []
        warnings: list[str] = []
        contract_report = validate_structure_v2(contract)
        errors.extend(contract_report["errors"]); warnings.extend(contract_report["warnings"])
        for value in values:
            item = validate_slice_v2(value); errors.extend(item["errors"]); warnings.extend(item["warnings"])
        expected = set(contract.get("executionSliceRefs") or [])
        observed = {str(value.get("sliceId")) for value in values}
        missing = sorted(expected - observed)
        if missing: errors.append(f"contract references missing execution slices: {missing}")
        report = _report_status({"kind": "execution-slice-set", "valid": not errors, "errors": errors, "warnings": warnings, "digest": contract_digest(values)})
    else:
        report = _report_status(validate_slice_set(values, contract))
    report["schema"] = "bbk.slice-set-assessment.v1"
    report["contract"] = {"path": str(contract_path), "id": f"{contract.get('contractId')}@{contract.get('revision')}", "digest": validate_structure_v2(contract).get("digest")}
    report["slices"] = [{"path": str(Path(raw).expanduser().resolve()), "id": value.get("sliceId"), "digest": validate_slice_v2(value).get("digest"), "status": value.get("status")} for raw, value in zip(args.slice, values)]
    return report


def cmd_work_unit_validate(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.path).expanduser().resolve()
    return _report_status(validate_work_unit(read_json(path)))


def cmd_work_unit_new(args: argparse.Namespace) -> dict[str, Any]:
    return _write_new_from_template("work-unit.json", args.output, force=args.force)


def cmd_evidence_validate(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.path).expanduser().resolve()
    return _report_status(validate_evidence_receipt(read_json(path)))


def cmd_evidence_new(args: argparse.Namespace) -> dict[str, Any]:
    template = "environment-observation-evidence-receipt-v2.json" if args.kind == "environment-observation" else "evidence-receipt-v2.json"
    result = _write_new_from_template(template, args.output, force=args.force)
    result["evidence_kind"] = args.kind
    return result


def cmd_review_plan(args: argparse.Namespace) -> dict[str, Any]:
    assurance_path = Path(args.assurance).expanduser().resolve(); assurance = read_json(assurance_path)
    subject_override = None
    if args.subject:
        subject_path = Path(args.subject).expanduser().resolve()
        if not subject_path.is_file():
            raise BbkError(f"Review subject is not a file: {subject_path}")
        subject_override = {
            "ref": args.subject_ref or str(subject_path),
            "kind": args.subject_kind or "artifact",
            "revision": args.subject_revision or "file",
            "digest": sha256_file(subject_path),
        }
    try:
        manifest = compile_review_manifest(
            assurance,
            purpose=args.purpose,
            manifest_id=validate_id(args.id, "review manifest id"),
            subject_override=subject_override,
            environment_capabilities=args.capability or [],
        )
    except ValueError as exc:
        raise BbkError(str(exc)) from exc
    manifest.setdefault("provenance", {})["bbkVersion"] = VERSION
    validation = validate_review_manifest(manifest, assurance)
    if args.output:
        write_json(Path(args.output).expanduser().resolve(), manifest)
    return _report_status({"schema": "bbk.review-plan-result.v1", "valid": validation["valid"], "errors": validation["errors"], "warnings": validation["warnings"], "manifest": manifest, "output": str(Path(args.output).expanduser().resolve()) if args.output else None, "digest": validation.get("digest")})


def cmd_review_context(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path = Path(args.manifest).expanduser().resolve(); manifest = read_json(manifest_path)
    root = Path(args.source or args.root or Path.cwd()).expanduser().resolve()
    try:
        context = compile_review_context(
            manifest,
            root,
            include_patterns=args.include or [],
            exclude_patterns=args.exclude or [],
            context_id=args.id,
        )
    except ValueError as exc:
        raise BbkError(str(exc)) from exc
    validation = validate_review_context(context, manifest)
    if args.output:
        write_json(Path(args.output).expanduser().resolve(), context)
    return _report_status({"schema": "bbk.review-context-result.v1", "valid": validation["valid"], "errors": validation["errors"], "warnings": validation["warnings"], "context": context, "output": str(Path(args.output).expanduser().resolve()) if args.output else None, "digest": validation.get("digest")})


def _load_many(paths: Sequence[str] | None) -> list[dict[str, Any]]:
    return [read_json(Path(raw).expanduser().resolve()) for raw in (paths or [])]


def cmd_review_run(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path = Path(args.manifest).expanduser().resolve(); manifest = read_json(manifest_path)
    context_path = Path(args.context).expanduser().resolve(); context = read_json(context_path)
    attempts = _load_many(args.attempt)
    receipts = _load_many(args.receipt)
    findings = _load_many(args.finding)
    dispositions = _load_many(args.disposition)
    run_id = validate_id(args.id, "review run id")
    run_record = build_review_run(
        manifest,
        context,
        run_id=run_id,
        attempts=attempts,
        receipts=receipts,
        findings=findings,
        dispositions=dispositions,
        predecessor_refs=args.predecessor or [],
    )
    validation = validate_review_run(run_record, manifest, context)
    output: Path | None = None
    if args.output:
        output = Path(args.output).expanduser().resolve()
    elif args.root:
        root = resolve_root(args.root); assert root
        output = root / ".bbk" / "reviews" / "runs" / f"{run_id}.json"
    if output:
        write_json(output, run_record)
    return _report_status({"schema": "bbk.review-run-result.v1", "valid": validation["valid"], "errors": validation["errors"], "warnings": validation["warnings"], "run": run_record, "output": str(output) if output else None, "result": run_record["aggregate"]["result"]})


def cmd_review_inspect(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.path).expanduser().resolve(); value = read_json(path); schema = value.get("schema")
    validators = {
        "bbk.assurance-contract.v1": validate_assurance_contract,
        "bbk.review-manifest.v1": validate_review_manifest,
        "bbk.review-context-manifest.v1": validate_review_context,
        "bbk.review-run.v1": validate_review_run,
        "bbk.review-attempt.v1": validate_review_attempt,
        "bbk.evidence-receipt.v2": validate_evidence_receipt,
        "bbk.review-finding.v1": validate_review_finding,
        "bbk.finding-disposition.v1": validate_finding_disposition,
        "bbk.learning-candidate.v1": validate_learning_candidate,
    }
    validator = validators.get(schema)
    if validator is None:
        raise BbkError(f"Unsupported review artifact schema: {schema}")
    report = validator(value)
    content = None
    if schema == "bbk.review-manifest.v1": content = markdown_review_manifest(value)
    elif schema == "bbk.review-run.v1": content = markdown_review_run(value)
    return _report_status({**report, "schema": "bbk.review-inspection.v1", "path": str(path), "artifactSchema": schema, "rendered": content})


def cmd_review_reconcile(args: argparse.Namespace) -> dict[str, Any]:
    findings = _load_many(args.finding)
    for index, finding in enumerate(findings):
        result = validate_review_finding(finding)
        if not result["valid"]:
            raise BbkError(f"Finding {index + 1} is invalid: {'; '.join(result['errors'])}")
    result = reconcile_findings(findings)
    if args.output:
        write_json(Path(args.output).expanduser().resolve(), result)
        result["output"] = str(Path(args.output).expanduser().resolve())
    return {"status": "PASS", **result}


def cmd_review_close(args: argparse.Namespace) -> dict[str, Any]:
    finding = read_json(Path(args.finding).expanduser().resolve())
    fvalidation = validate_review_finding(finding)
    if not fvalidation["valid"]:
        raise BbkError("Invalid finding: " + "; ".join(fvalidation["errors"]))
    successor_digest = args.successor_digest
    if args.successor_file:
        successor_path = Path(args.successor_file).expanduser().resolve()
        successor_digest = sha256_file(successor_path)
    if not successor_digest:
        raise BbkError("Finding disposition requires --successor-digest or --successor-file")
    try:
        disposition = create_finding_disposition(
            finding,
            disposition=args.disposition,
            successor_ref=args.successor_ref,
            successor_digest=successor_digest,
            evidence_refs=args.evidence or [],
            review_attempt_ref=args.review_attempt,
            authority_ref=args.authority,
            residual_impact=args.residual_impact,
            reopening_triggers=args.reopen_trigger or [],
            disposition_id=validate_id(args.id, "finding disposition id"),
            created_at=utc_now(),
        )
    except ValueError as exc:
        raise BbkError(str(exc)) from exc
    output = Path(args.output).expanduser().resolve()
    write_json(output, disposition)
    return {"schema": "bbk.finding-disposition-result.v1", "status": "PASS", "disposition": disposition, "output": str(output), "digest": contract_digest(disposition)}


def cmd_review_learn(args: argparse.Namespace) -> dict[str, Any]:
    try:
        candidate = create_learning_candidate(
            candidate_id=validate_id(args.id, "learning candidate id"),
            candidate_type=args.type,
            lesson=args.lesson,
            scope=args.scope,
            supporting=args.supporting or [],
            contrary=args.contrary or [],
            findings=args.finding or [],
            runs=args.run or [],
            dispositions=args.disposition or [],
            confidence=args.confidence,
            uncertainty=args.uncertainty,
            action=args.action,
            privacy_class=args.privacy_class,
            export_class=args.export_class,
        )
    except ValueError as exc:
        raise BbkError(str(exc)) from exc
    output = Path(args.output).expanduser().resolve()
    write_json(output, candidate)
    return {"schema": "bbk.learning-candidate-result.v1", "status": "PASS", "candidate": candidate, "output": str(output), "digest": contract_digest(candidate)}


def cmd_package_verify(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.package_root or PACKAGE_ROOT).expanduser().resolve()
    candidates = [PACKAGE_ROOT / "tools" / "verify_package.py", PACKAGE_ROOT / "verify_package.py"]
    verifier = next((path for path in candidates if path.is_file()), None)
    if verifier is None: raise BbkError("Package verifier is not installed beside this BBK CLI")
    outcome = run([sys.executable, str(verifier), "--root", str(root), "--json", "--strict-mode"], root, timeout=120)
    if outcome["returncode"] not in {0, 1}: raise BbkError(f"Package verifier failed: {outcome['stderr'] or outcome['stdout']}")
    try: return json.loads(outcome["stdout"])
    except json.JSONDecodeError as exc: raise BbkError(f"Package verifier returned invalid JSON: {exc}") from exc


def cmd_gate_record(args: argparse.Namespace) -> dict[str, Any]:
    candidate_path = Path(args.candidate).expanduser().resolve(); candidate = read_json(candidate_path)
    digest = candidate.get("candidateDigest") or candidate.get("manifest_content_sha256") or candidate.get("content_sha256")
    if not digest: raise BbkError("Candidate record has no recognized digest")
    evidence = []
    for raw in args.evidence or []:
        path = Path(raw).expanduser().resolve(); evidence.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    receipt = {"schema": "bbk.compat-gate-receipt.v1", "bbk_version": VERSION, "gate_id": validate_id(args.gate_id, "gate id"), "candidate_path": str(candidate_path), "candidate_digest": digest, "status": args.status, "evidence": evidence, "recorded_at": utc_now()}
    receipt["receipt_digest"] = sha256_bytes(canonical_bytes(receipt))
    output = Path(args.output).expanduser().resolve(); write_json(output, receipt)
    return {"status": "PASS", "receipt": receipt, "output": str(output)}


def cmd_gate_check(args: argparse.Namespace) -> dict[str, Any]:
    receipt = read_json(Path(args.receipt).expanduser().resolve()); candidate = read_json(Path(args.candidate).expanduser().resolve())
    digest = candidate.get("candidateDigest") or candidate.get("manifest_content_sha256") or candidate.get("content_sha256")
    errors = []
    if receipt.get("candidate_digest") != digest: errors.append("receipt candidate digest does not match candidate")
    if receipt.get("status") != "PASS": errors.append(f"receipt status is {receipt.get('status')}, not PASS")
    return {"schema": "bbk.compat-gate-check.v1", "status": "PASS" if not errors else "FAIL", "valid": not errors, "errors": errors, "candidate_digest": digest, "gate_id": receipt.get("gate_id")}


def cmd_candidate_verify_file(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.manifest).expanduser().resolve(); manifest = read_json(path)
    root = Path(manifest.get("root") or manifest.get("source_root") or ".").expanduser().resolve()
    if manifest.get("schema") == "bbk.manifest.v1":
        current = collect_manifest(root, excludes=manifest.get("excludes") or [])
        comparison = compare_manifests(manifest, current)
        return {"schema": "bbk.candidate-file-verification.v1", "status": "PASS" if comparison["equal"] else "FAIL", "valid": comparison["equal"], "comparison": comparison}
    expected = {item.get("path"): item for item in manifest.get("files", []) if isinstance(item, dict) and item.get("path")}
    current = {item.get("path"): item for item in collect_manifest(root, manifest.get("excludes") or []).get("files", [])}
    errors = []
    for rel in sorted(set(expected) | set(current)):
        before, after = expected.get(rel), current.get(rel)
        if before is None: errors.append(f"added: {rel}")
        elif after is None: errors.append(f"removed: {rel}")
        elif before.get("sha256") != after.get("sha256"): errors.append(f"changed: {rel}")
    return {"schema": "bbk.candidate-file-verification.v1", "status": "PASS" if not errors else "FAIL", "valid": not errors, "root": str(root), "errors": errors}


def cmd_worktree_plan(args: argparse.Namespace) -> dict[str, Any]:
    repo = Path(args.repo).expanduser().resolve(); path = Path(args.path).expanduser().resolve(); ref = args.ref or "HEAD"
    resolved = git(repo, "rev-parse", ref)
    if resolved["returncode"] != 0: raise BbkError(f"Invalid Git ref {ref!r}: {resolved['stderr']}")
    return {"schema": "bbk.worktree-plan.v1", "status": "PASS", "repo": str(repo), "path": str(path), "ref": ref, "commit": resolved["stdout"].strip(), "command": ["git", "-C", str(repo), "worktree", "add", "--detach", str(path), resolved["stdout"].strip()], "recommendation": "Use `bbk workspace create` when lease, ownership and candidate-reference tracking are required."}


def cmd_worktree_create(args: argparse.Namespace) -> dict[str, Any]:
    plan = cmd_worktree_plan(args); path = Path(plan["path"])
    if path.exists(): raise BbkError(f"Worktree path already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True); outcome = run(plan["command"], Path(plan["repo"]))
    if outcome["returncode"] != 0: raise BbkError(f"git worktree add failed: {outcome['stderr']}")
    return {**plan, "status": "ACTIVE", "result": outcome}


def cmd_worktree_cleanup(args: argparse.Namespace) -> dict[str, Any]:
    repo = Path(args.repo).expanduser().resolve(); path = Path(args.path).expanduser().resolve()
    if path.exists():
        state = git_metadata(path)
        if state.get("dirty") and not args.force: raise BbkError("Worktree is dirty; preserve changes or pass --force")
    command = ["git", "-C", str(repo), "worktree", "remove"] + (["--force"] if args.force else []) + [str(path)]
    outcome = run(command, repo)
    if outcome["returncode"] != 0: raise BbkError(f"git worktree remove failed: {outcome['stderr']}")
    git(repo, "worktree", "prune")
    return {"schema": "bbk.worktree-cleanup.v1", "status": "REMOVED", "repo": str(repo), "path": str(path), "force": bool(args.force)}

def git(root: Path, *args: str) -> dict[str, Any]:
    return run(["git", *args], root)


def git_metadata(root: Path) -> dict[str, Any]:
    inside = git(root, "rev-parse", "--is-inside-work-tree")
    if inside["returncode"] != 0:
        return {"available": False}
    head = git(root, "rev-parse", "HEAD")
    branch = git(root, "branch", "--show-current")
    # Bind working-tree observations to the requested source root. Git walks
    # upward from ``root`` to discover a repository; an unscoped status would
    # therefore include unrelated parent-repository changes (and can vary while
    # another test or worker writes elsewhere in that repository). ``-- .``
    # keeps the metadata useful for repository subtrees while ensuring the
    # manifest depends only on the bounded source tree.
    status = git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--", ".")
    prefix_result = git(root, "rev-parse", "--show-prefix")
    prefix = prefix_result["stdout"].strip() if prefix_result["returncode"] == 0 else ""

    def source_relative(path: str) -> str:
        if prefix and path.startswith(prefix):
            return path[len(prefix):]
        return path

    status_porcelain: list[str] = []
    fields = status["stdout"].split("\0")
    index = 0
    while index < len(fields):
        field = fields[index]
        index += 1
        if not field:
            continue
        if len(field) < 3 or field[2] != " ":
            status_porcelain.append(field)
            continue
        code = field[:2]
        path = source_relative(field[3:])
        if "R" in code or "C" in code:
            if index >= len(fields) or not fields[index]:
                status_porcelain.append(f"{code} {path}")
                continue
            original = source_relative(fields[index])
            index += 1
            status_porcelain.append(f"{code} {original} -> {path}")
        else:
            status_porcelain.append(f"{code} {path}")
    return {
        "available": head["returncode"] == 0,
        "head": head["stdout"].strip() or None,
        "branch": branch["stdout"].strip() or None,
        "dirty": bool(status_porcelain),
        "status_porcelain": status_porcelain,
    }



def operational_json_paths(base: Path, *, recursive: bool = False) -> list[Path]:
    iterator = base.rglob("*.json") if recursive else base.glob("*.json")
    return [path for path in sorted(iterator) if not is_non_operational_example(path)]


def example_paths(base: Path, *, recursive: bool = False) -> list[Path]:
    iterator = base.rglob("*") if recursive else base.glob("*")
    return [path for path in sorted(iterator) if path.is_file() and is_non_operational_example(path)]


def is_excluded(rel: str, patterns: Sequence[str]) -> bool:
    rel = rel.lstrip("./")
    for pattern in patterns:
        pattern = pattern.lstrip("./")
        if fnmatch.fnmatch(rel, pattern):
            return True
        if pattern.endswith("/**"):
            base = pattern[:-3].rstrip("/")
            if rel == base or rel.startswith(base + "/"):
                return True
    return False


def semantic_json(path: Path) -> tuple[str | None, str | None]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return sha256_bytes(canonical_bytes(value)), None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, str(exc)


def collect_manifest(
    source: Path,
    excludes: Sequence[str] | None = None,
    *,
    include_examples: bool = False,
) -> dict[str, Any]:
    source = source.resolve()
    patterns = list(dict.fromkeys([*DEFAULT_EXCLUDES, *(excludes or [])]))
    files: list[dict[str, Any]] = []
    warnings: list[str] = []
    excluded_examples: list[str] = []
    for dirpath, dirnames, filenames in os.walk(source, topdown=True, followlinks=False):
        directory = Path(dirpath)
        kept: list[str] = []
        for name in sorted(dirnames):
            path = directory / name
            rel = path.relative_to(source).as_posix()
            if is_excluded(rel, patterns):
                continue
            if not include_examples and path.name.casefold().startswith("example-"):
                excluded_examples.append(rel)
                continue
            if path.is_symlink():
                target = os.readlink(path)
                files.append({"path": rel, "type": "symlink", "target": target, "sha256": sha256_bytes(target.encode())})
            else:
                kept.append(name)
        dirnames[:] = kept
        for name in sorted(filenames):
            path = directory / name
            rel = path.relative_to(source).as_posix()
            if is_excluded(rel, patterns):
                continue
            if not include_examples and is_non_operational_example(path):
                excluded_examples.append(rel)
                continue
            try:
                info = path.lstat()
                if stat.S_ISLNK(info.st_mode):
                    target = os.readlink(path)
                    files.append({"path": rel, "type": "symlink", "target": target, "sha256": sha256_bytes(target.encode())})
                    continue
                if not stat.S_ISREG(info.st_mode):
                    warnings.append(f"Skipped non-regular path: {rel}")
                    continue
                record: dict[str, Any] = {
                    "path": rel, "type": "file", "size": info.st_size,
                    "executable": bool(info.st_mode & stat.S_IXUSR), "sha256": sha256_file(path),
                }
                if path.suffix.lower() == ".json":
                    digest, error = semantic_json(path)
                    record["semantic_kind"] = "canonical-json"
                    record["semantic_sha256"] = digest
                    if error:
                        record["semantic_error"] = error
                files.append(record)
            except OSError as exc:
                warnings.append(f"Unable to read {rel}: {exc}")
    content = {"schema": "bbk.manifest-content.v1", "root_label": source.name, "files": files}
    excluded_examples.sort()
    return {
        "schema": "bbk.manifest.v1", "bbk_version": VERSION, "created_at": utc_now(),
        "root": str(source), "excludes": patterns, "content_sha256": sha256_bytes(canonical_bytes(content)),
        "file_count": len(files), "files": files, "git": git_metadata(source), "warnings": warnings,
        "include_examples": include_examples,
        "examples_excluded": len(excluded_examples), "excluded_example_paths": excluded_examples,
    }


def compare_manifests(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    lidx = {item["path"]: item for item in left.get("files", [])}
    ridx = {item["path"]: item for item in right.get("files", [])}
    changes: list[dict[str, Any]] = []
    for path in sorted(set(lidx) | set(ridx)):
        before, after = lidx.get(path), ridx.get(path)
        if before is None:
            changes.append({"path": path, "kind": "added", "after": after})
        elif after is None:
            changes.append({"path": path, "kind": "removed", "before": before})
        elif before.get("type") != after.get("type"):
            changes.append({"path": path, "kind": "type_changed", "before": before, "after": after})
        elif before.get("sha256") != after.get("sha256") or before.get("executable") != after.get("executable"):
            if before.get("semantic_kind") == after.get("semantic_kind") == "canonical-json" and before.get("semantic_sha256") == after.get("semantic_sha256") and before.get("semantic_sha256"):
                kind = "semantic_equivalent_byte_change"
            elif before.get("semantic_kind") == after.get("semantic_kind") == "canonical-json":
                kind = "semantic_changed"
            else:
                kind = "byte_changed"
            changes.append({"path": path, "kind": kind, "before": before, "after": after})
    lg, rg = left.get("git", {}), right.get("git", {})
    git_changed = lg.get("head") != rg.get("head") or lg.get("branch") != rg.get("branch")
    summary: dict[str, int] = {}
    for item in changes:
        summary[item["kind"]] = summary.get(item["kind"], 0) + 1
    return {
        "schema": "bbk.manifest-comparison.v1",
        "left_content_sha256": left.get("content_sha256"),
        "right_content_sha256": right.get("content_sha256"),
        "equal": not changes and not git_changed,
        "git_identity_changed": git_changed,
        "summary": summary,
        "changes": changes,
    }


def initial_files(title: str, project_id: str, *, examples_enabled: bool = True) -> dict[str, bytes]:
    created = utc_now()
    config = {
        "schema": "bbk.config.v1", "bbk_version": VERSION, "project_id": project_id,
        "title": title, "created_at": created,
        "method": {"default_depth": "standard", "default_assurance_tier": "material", "ordinary_repair_cycles": 2, "hard_repair_review_cycle": 3},
        "execution": {
            "worker_window": "extended",
            "checkpoint_interval_seconds": 600,
            "checkpoint_before_host_boundary": True,
            "resume_same_thread": True,
            "infrastructure_continuations": 6,
            "durable_handoffs": True,
            "large_result_transport": "file-bytes-sha256"
        },
        "manifest": {"excludes": DEFAULT_EXCLUDES},
        "workspaces": {"root": "../.bbk-worktrees", "default_lease_hours": 24},
        "prevalidation": {"allow_empty": False},
        "beads": {"enabled": True, "write_enabled": True, "workspace": ".", "auto_initialize": True},
        "profiles": {"enabled": True, "lock_file": "profile-lock.json"},
        "examples": {
            "enabled": examples_enabled,
            "root": "examples",
            "operational": False,
            "materialization": "isolated" if examples_enabled else "disabled",
        },
        "planning_artifacts": {
            "solution_outcome_fit": True,
            "implementation_structure": True,
            "execution_slices": True,
            "state_decision_effect": True,
            "review_assurance": True,
        },
    }
    values: dict[str, Any] = {
        "config.json": config,
        "map.json": {
            "schema": "bbk.map.v1",
            "project_id": project_id,
            "destination": {"outcome": "", "success_evidence": [], "in_scope": [], "out_of_scope": [], "constraints": []},
            "posture": {"user_decides": [], "wayfinder_recommends": [], "delegated": [], "constraint_driven": [], "interrupt_for": []},
            "territories": [],
            "decisions": [],
            "questions": [],
            "frontier": [],
            "blockers": [],
            "capability_increments": [],
            "phases": [],
            "fog": [],
            "stopping_assessment": {"last_assessed_at": None, "remaining_positive_information_value": None, "residual_uncertainty": []}
        },
        "interfaces.json": {"schema": "bbk.interfaces.v1", "project_id": project_id, "interfaces": []},
        "work.json": {"schema": "bbk.work.v1", "project_id": project_id, "work_units": [], "integration_obligations": []},
        "assurance.json": {"schema": "bbk.assurance.v1", "project_id": project_id, "default_tier": "material", "contracts": [], "policy": {"one_assertion_one_sufficient_proof": True, "deterministic_before_model_review": True, "independence_requires_distinct_property": True, "ordinary_repair_cycles": 2, "review_by_cycle": 3}},
        "gates.json": {"schema": "bbk.gates.v1", "prevalidation": {"allow_empty": False}, "gates": [{"id": "example-focused-check", "description": "Replace this disabled example with a project-specific deterministic check.", "enabled": False, "phases": ["prefreeze", "prevalidate"], "command": ["python3", "-m", "unittest"], "cwd": ".", "blocking": True, "timeout_seconds": 300, "requires": ["python3"], "assertions": ["project-specific-focused-checks-pass"]}]},
        "profile-lock.json": {"schema": "bbk.profile-lock.v1", "project_id": project_id, "generated_at": None, "profiles": [], "effective_sha256": None},
        "review-index.json": {"schema": "bbk.review-index.v1", "project_id": project_id, "manifests": [], "contexts": [], "runs": [], "findings": [], "dispositions": [], "learning_candidates": []},
        "mappings/beads.json": {"schema": "bbk.beads-mapping.v1", "enabled": True, "write_enabled": True, "workspace": ".", "auto_initialize": True, "objects": [], "policy": {"source_identity": "bbk", "last_write_wins": False, "close_implies_completion": False}},
    }
    files = {name: pretty_bytes(value) for name, value in values.items()}
    files["project.md"] = f"# {title}\n\n**BBK project:** `{project_id}`  \n**Initialized:** {created}\n\n## Operational outcome\n\nDescribe what must be observably true when this effort succeeds.\n\n## Boundary\n\n- In scope:\n- Out of scope:\n- Constraints:\n- Accountable authority:\n\n> `.bbk/` is a practical bootstrap record, not an official Blueprint baseline.\n".encode("utf-8")
    files["decisions.md"] = b"# Decisions\n\n| ID | Status | Decision | Authority | Affected scope |\n|---|---|---|---|---|\n"
    files["status.md"] = b"# BBK status\n\n- State: initialized\n- Active work: none\n- Current candidate: none\n- Blockers: none recorded\n"
    files[".gitignore"] = b"runtime/\nlogs/\nworkspaces/\n*.tmp\n"
    return files


def cmd_init(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root or Path.cwd()).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    target = root / ".bbk"
    existing_config = read_json(target / "config.json") if (target / "config.json").is_file() else None
    title = args.title or (existing_config or {}).get("title") or root.name
    project_id = validate_id(args.project_id or (existing_config or {}).get("project_id") or f"BBK-{uuid.uuid4().hex[:12].upper()}", "project id")
    created, preserved = [], []
    for rel, data in initial_files(title, project_id, examples_enabled=not args.no_examples).items():
        path = target / rel
        if path.exists():
            preserved.append(portable_relative_path(path, root))
            continue
        atomic_write(path, data)
        created.append(portable_relative_path(path, root))
    for name in [
        "candidates", "attestations", "receipts/gates", "questions", "handoffs", "runtime/candidate-state",
        "runtime", "workspaces", "logs", "fit", "structures", "state-effects", "traces", "slices", "reviews", "reviews/manifests", "reviews/contexts", "reviews/runs", "reviews/findings", "reviews/dispositions", "reviews/learning", "work-units", "profiles", "examples",
    ]:
        (target / name).mkdir(parents=True, exist_ok=True)
    examples = {
        "fit/EXAMPLE-solution-outcome-fit.json": "solution-outcome-fit.json",
        "structures/EXAMPLE-implementation-structure-contract.json": "implementation-structure-contract.json",
        "structures/EXAMPLE-implementation-structure-contract-v2.json": "implementation-structure-contract-v2.json",
        "structures/EXAMPLE-implementation-structure-contract-v3.json": "implementation-structure-contract-v3.json",
        "structures/EXAMPLE-implementation-structure-contract-v3-infrastructure-compact.json": "implementation-structure-contract-v3-infrastructure-compact.json",
        "state-effects/EXAMPLE-state-decision-effect-design.json": "state-decision-effect-design.json",
        "traces/EXAMPLE-state-transition-trace.json": "state-transition-trace.json",
        "slices/EXAMPLE-execution-slice.json": "execution-slice.json",
        "slices/EXAMPLE-execution-slice-v2.json": "execution-slice-v2.json",
        "reviews/EXAMPLE-assurance-contract.json": "assurance-contract.json",
        "reviews/EXAMPLE-review-manifest.json": "review-manifest.json",
        "reviews/EXAMPLE-review-context-manifest.json": "review-context-manifest.json",
        "reviews/EXAMPLE-review-attempt.json": "review-attempt.json",
        "reviews/EXAMPLE-evidence-receipt-v2.json": "evidence-receipt-v2.json",
        "reviews/EXAMPLE-environment-observation-evidence-receipt-v2.json": "environment-observation-evidence-receipt-v2.json",
        "reviews/EXAMPLE-review-finding.json": "review-finding.json",
        "reviews/EXAMPLE-finding-disposition.json": "finding-disposition.json",
        "reviews/EXAMPLE-learning-candidate.json": "learning-candidate.json",
        "work-units/EXAMPLE-work-unit.json": "work-unit.json",
        "questions/EXAMPLE-question-branch.json": "question-branch.json",
        "handoffs/EXAMPLE-handoff.json": "handoff.json",
    }
    examples_materialized = 0
    legacy_examples_preserved = 0
    if not args.no_examples:
        for legacy_rel, template in examples.items():
            legacy_destination = target / legacy_rel
            destination = target / "examples" / legacy_rel
            # Existing alpha.13.x projects keep their legacy examples in place.
            # Do not duplicate them into the new isolated template tree.
            if legacy_destination.exists():
                preserved.append(portable_relative_path(legacy_destination, root))
                legacy_examples_preserved += 1
                continue
            if destination.exists():
                preserved.append(portable_relative_path(destination, root))
                continue
            source = _template_path(template)
            atomic_write(destination, source.read_bytes())
            created.append(portable_relative_path(destination, root))
            examples_materialized += 1
    return {
        "status": "initialized" if existing_config is None else "updated",
        "root": str(root), "project_id": project_id, "title": title,
        "created": created, "preserved": preserved,
        "examples": {
            "enabled": not args.no_examples,
            "materialized": examples_materialized,
            "legacy_preserved": legacy_examples_preserved,
            "root": portable_relative_path(target / "examples", root),
        },
    }


def cmd_manifest_create(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_root(args.root, required=False) or Path.cwd().resolve()
    source = Path(args.source).expanduser().resolve() if args.source else root
    excludes: list[str] = []
    if (root / ".bbk" / "config.json").is_file():
        excludes = load_config(root).get("manifest", {}).get("excludes", [])
    manifest = collect_manifest(
        source,
        [*excludes, *(args.exclude or [])],
        include_examples=bool(getattr(args, "include_examples", False)),
    )
    if args.output:
        output = Path(args.output).expanduser()
        if not output.is_absolute():
            output = root / output
        write_json(output, manifest)
        manifest["written_to"] = str(output.resolve())
    return manifest


def cmd_manifest_compare(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_root(args.root, required=False) or Path.cwd().resolve()
    left_path = Path(args.left).expanduser()
    if not left_path.is_absolute():
        left_path = root / left_path
    left = read_json(left_path)
    if args.right:
        path = Path(args.right).expanduser()
        if not path.is_absolute():
            path = root / path
        right = read_json(path)
    else:
        source = Path(args.source).expanduser().resolve() if args.source else root
        excludes = load_config(root).get("manifest", {}).get("excludes", []) if (root / ".bbk" / "config.json").is_file() else []
        right = collect_manifest(
            source, excludes, include_examples=bool(getattr(args, "include_examples", False))
        )
    return compare_manifests(left, right)


def candidate_paths(root: Path, candidate_id: str) -> tuple[Path, Path, Path]:
    validate_id(candidate_id, "candidate id")
    return (
        root / ".bbk" / "candidates" / candidate_id,
        root / ".bbk" / "runtime" / "candidate-state" / f"{candidate_id}.json",
        root / ".bbk" / "attestations" / candidate_id / "worker-quality.json",
    )


def candidate_meta(root: Path, candidate_id: str) -> dict[str, Any]:
    return read_json(candidate_paths(root, candidate_id)[0] / "candidate.json")


def candidate_manifest(root: Path, candidate_id: str) -> dict[str, Any]:
    return read_json(candidate_paths(root, candidate_id)[0] / "manifest.json")


def write_candidate_state(root: Path, candidate_id: str, state: str, stale: bool, reasons: list[Any], comparison: dict[str, Any] | None = None) -> dict[str, Any]:
    _, path, attestation = candidate_paths(root, candidate_id)
    value = {"schema": "bbk.candidate-state.v1", "candidate_id": candidate_id, "state": state, "stale": stale, "reasons": reasons, "updated_at": utc_now()}
    if comparison is not None:
        value["comparison"] = comparison
    value["attestation_present"] = attestation.exists()
    if attestation.exists():
        record = read_json(attestation)
        value["validator_ready"] = record.get("status") == "PASS" and not stale
        value["attestation_sha256"] = sha256_file(attestation)
    else:
        value["validator_ready"] = False
    write_json(path, value)
    return value


def candidate_state(root: Path, candidate_id: str) -> dict[str, Any]:
    _, path, attestation = candidate_paths(root, candidate_id)
    if path.exists():
        value = read_json(path)
    else:
        value = {"schema": "bbk.candidate-state.v1", "candidate_id": candidate_id, "state": "FROZEN", "stale": False, "reasons": []}
    value["attestation_present"] = attestation.exists()
    value["validator_ready"] = False
    if attestation.exists():
        record = read_json(attestation)
        value["validator_ready"] = record.get("status") == "PASS" and not value.get("stale")
        value["attestation_sha256"] = sha256_file(attestation)
    return value


def cmd_candidate_freeze(args: argparse.Namespace) -> dict[str, Any]:
    # Alpha.4/5 supported an independent file-manifest candidate without an
    # initialized BBK project. Preserve that surface when --output is supplied;
    # initialized projects additionally receive alpha.3's immutable candidate,
    # state and later executable-gate workflow.
    explicit_root = Path(args.root).expanduser().resolve() if args.root else None
    initialized = bool(explicit_root and (explicit_root / ".bbk" / "config.json").is_file())
    if not explicit_root:
        discovered = project_root(required=False)
        explicit_root = discovered or Path.cwd().resolve()
        initialized = bool(discovered)
    if not initialized and not getattr(args, "output", None):
        raise BbkError(f"Not a BBK project: {explicit_root}; initialize it or supply --output for a standalone candidate manifest")

    root = explicit_root
    candidate_id = validate_id(args.id or f"C-{uuid.uuid4().hex[:12].upper()}", "candidate id")
    source = Path(args.source).expanduser().resolve() if args.source else root
    if source != root and not args.allow_external_source:
        raise BbkError("External candidate source requires --allow-external-source")
    excludes = list(load_config(root).get("manifest", {}).get("excludes", []) if initialized else [])
    standalone_path = Path(args.output).expanduser().resolve() if getattr(args, "output", None) else None
    if standalone_path:
        try:
            excludes.append(standalone_path.relative_to(source).as_posix())
        except ValueError:
            pass
    manifest = collect_manifest(
        source, excludes, include_examples=bool(getattr(args, "include_examples", False))
    )
    if manifest["warnings"] and not args.allow_warnings:
        raise BbkError("Manifest warnings block freeze:\n- " + "\n- ".join(manifest["warnings"]))
    file_records = [
        {"path": item.get("path"), "bytes": item.get("size", 0), "sha256": item.get("sha256"), "executable": item.get("executable", False)}
        for item in manifest.get("files", []) if item.get("type") == "file"
    ]
    structure_inventory = []
    for raw in getattr(args, "structure_inventory", None) or []:
        path = Path(raw).expanduser().resolve()
        if not path.is_file():
            raise BbkError(f"Candidate structure inventory is missing: {path}")
        value = read_json(path)
        structure_inventory.append({"path": str(path), "sha256": sha256_file(path), "schema": value.get("schema"), "subjectRef": value.get("subjectRef")})
    trace_inventory = []
    for raw in getattr(args, "trace", None) or []:
        path = Path(raw).expanduser().resolve()
        result = validate_transition_trace(read_json(path))
        if not result["valid"]:
            raise BbkError(f"Candidate trace is invalid ({path}): {'; '.join(result['errors'])}")
        trace_inventory.append({"path": str(path), "sha256": sha256_file(path), "traceId": read_json(path).get("traceId")})
    model_inventory = []
    for raw in getattr(args, "formal_model", None) or []:
        path = Path(raw).expanduser().resolve()
        if not path.is_file():
            raise BbkError(f"Candidate formal model is missing: {path}")
        model_inventory.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    standalone = {
        "schema": "bbk.candidate.v1", "bbkVersion": VERSION, "candidateId": candidate_id,
        "root": str(source), "files": file_records, "candidateDigest": contract_digest(file_records),
        "projectId": load_config(root).get("project_id") if initialized else None, "createdAt": utc_now(),
        "excludes": excludes, "stateEffectInventories": structure_inventory,
        "stateTransitionTraces": trace_inventory, "formalModels": model_inventory,
    }

    candidate = None
    if initialized:
        directory, _, _ = candidate_paths(root, candidate_id)
        if directory.exists():
            raise BbkError(f"Candidate already exists: {candidate_id}; use a successor ID")
        with lock_project(root, f"candidate-freeze:{candidate_id}"):
            directory.mkdir(parents=True)
            candidate = {
                "schema": "bbk.candidate.v1", "bbk_version": VERSION, "candidate_id": candidate_id,
                "project_id": load_config(root)["project_id"], "source_root": str(source), "created_at": standalone["createdAt"],
                "manifest_content_sha256": manifest["content_sha256"], "manifest_sha256": sha256_bytes(canonical_bytes(manifest)),
                "git": manifest.get("git"), "note": args.note or "",
                "state_effect_inventories": structure_inventory,
                "state_transition_traces": trace_inventory,
                "formal_models": model_inventory,
                "authority_disclaimer": "BBK candidate identity is not an official Blueprint baseline or execution authorization.",
            }
            write_json(directory / "manifest.json", manifest, 0o444)
            write_json(directory / "candidate.json", candidate, 0o444)
            write_candidate_state(root, candidate_id, "FROZEN", False, [])
    if standalone_path:
        write_json(standalone_path, standalone)
    return {
        "schema": "bbk.candidate-freeze-result.v1", "status": "FROZEN", "candidate_id": candidate_id,
        "candidate": candidate, "standalone": standalone if standalone_path else None,
        "standalone_manifest": str(standalone_path) if standalone_path else None,
        "project_managed": initialized,
    }


def cmd_candidate_check(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_root(args.root); assert root
    original = candidate_manifest(root, args.id)
    meta = candidate_meta(root, args.id)
    source = Path(meta["source_root"])
    if not source.exists():
        comparison = {"schema": "bbk.manifest-comparison.v1", "equal": False, "git_identity_changed": True, "summary": {"source_missing": 1}, "changes": []}
    else:
        current = collect_manifest(source, load_config(root).get("manifest", {}).get("excludes", []))
        comparison = compare_manifests(original, current)
    dependency_changes: list[dict[str, Any]] = []
    for field in ("state_effect_inventories", "state_transition_traces", "formal_models"):
        for item in meta.get(field, []) or []:
            path = Path(str(item.get("path", "")))
            expected = item.get("sha256")
            if not path.is_file():
                dependency_changes.append({"kind": "missing", "field": field, "path": str(path), "expected": expected})
            else:
                current_digest = sha256_file(path)
                if current_digest != expected:
                    dependency_changes.append({"kind": "digest_changed", "field": field, "path": str(path), "expected": expected, "actual": current_digest})
    if dependency_changes:
        comparison = dict(comparison)
        comparison["equal"] = False
        comparison.setdefault("summary", {})["bound_dependency_changed"] = len(dependency_changes)
        comparison["boundDependencyChanges"] = dependency_changes
    stale = not comparison["equal"]
    reasons = [] if not stale else [comparison["summary"]]
    state = write_candidate_state(root, args.id, "STALE" if stale else "FROZEN", stale, reasons, comparison)
    return {"candidate_id": args.id, "current": not stale, "state": state, "comparison": comparison}


def cmd_candidate_status(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_root(args.root); assert root
    if args.check:
        return cmd_candidate_check(args)
    return {"candidate": candidate_meta(root, args.id), "state": candidate_state(root, args.id)}


def cmd_candidate_invalidate(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_root(args.root); assert root
    candidate_meta(root, args.id)
    return {"candidate_id": args.id, "state": write_candidate_state(root, args.id, "INVALIDATED", True, [args.reason])}


def load_gates(root: Path) -> dict[str, Any]:
    value = read_json(root / ".bbk" / "gates.json")
    if value.get("schema") != "bbk.gates.v1" or not isinstance(value.get("gates"), list):
        raise BbkError(".bbk/gates.json must use schema bbk.gates.v1")
    ids = [gate.get("id") for gate in value["gates"]]
    if len(ids) != len(set(ids)) or any(not isinstance(item, str) or not SAFE_ID.fullmatch(item) for item in ids):
        raise BbkError("Gate IDs must be unique safe identifiers")
    return value


def gate_applicability(root: Path, gate: dict[str, Any], phase: str) -> tuple[str, str | None]:
    if not gate.get("enabled", True):
        return "SKIPPED", "gate disabled"
    phases = gate.get("phases", [])
    if phases and phase not in phases:
        return "NOT_APPLICABLE", f"phase {phase!r} not in {phases}"
    for executable in gate.get("requires", []):
        if shutil.which(str(executable)) is None:
            return "BLOCKED", f"required executable not found: {executable}"
    return "APPLICABLE", None


def capture_preview(path: Path) -> tuple[str, int, bool]:
    """Return a bounded UTF-8 preview while preserving the authoritative file."""
    size = path.stat().st_size
    with path.open("rb") as handle:
        raw = handle.read(MAX_CAPTURE)
    truncated = size > len(raw)
    try:
        preview = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        preview = (
            "[BBK preview unavailable: captured output is not valid UTF-8; "
            f"verify the bound output file for authoritative bytes ({exc})]\n"
        )
    if truncated:
        preview += "\n[BBK preview truncated; verify the bound output file for complete bytes]\n"
    return preview, size, truncated


def gate_stream_record(root: Path, path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def gate_streams_current(root: Path, receipt: dict[str, Any]) -> bool:
    """A reusable gate receipt must still bind both complete output streams."""
    for field in ("stdout_file", "stderr_file"):
        record = receipt.get(field)
        if not isinstance(record, dict):
            return False
        rel = record.get("path")
        expected_bytes = record.get("bytes")
        expected_sha = record.get("sha256")
        if not isinstance(rel, str) or not isinstance(expected_bytes, int) or not isinstance(expected_sha, str):
            return False
        candidate = Path(rel)
        if candidate.is_absolute() or "\\" in rel:
            return False
        path = (root / candidate).resolve()
        try:
            path.relative_to(root.resolve())
        except ValueError:
            return False
        if not path.is_file() or path.stat().st_size != expected_bytes or sha256_file(path) != expected_sha:
            return False
    return True


def run_to_bound_files(
    argv: Sequence[str],
    cwd: Path,
    stdout_path: Path,
    stderr_path: Path,
    *,
    timeout: float | None,
    env: dict[str, str] | None,
) -> dict[str, Any]:
    """Run without an in-memory output ceiling and atomically bind both streams."""
    command = normalize_python_command(argv)
    if not command:
        raise BbkError("Command argv must not be empty")
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    stdout_temp = stdout_path.with_name(f".{stdout_path.name}.{token}.tmp")
    stderr_temp = stderr_path.with_name(f".{stderr_path.name}.{token}.tmp")
    started = time.monotonic()
    child_environment = env or os.environ
    if command != [str(item) for item in argv]:
        child_environment = python_environment(child_environment)
    executable = shutil.which(command[0], path=child_environment.get("PATH"))
    returncode = 127
    timed_out = False
    try:
        with stdout_temp.open("wb") as stdout_handle, stderr_temp.open("wb") as stderr_handle:
            try:
                result = subprocess.run(
                    command,
                    cwd=str(cwd),
                    env=child_environment,
                    timeout=timeout,
                    check=False,
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                )
                returncode = result.returncode
            except subprocess.TimeoutExpired:
                returncode = 124
                timed_out = True
            except FileNotFoundError as exc:
                stderr_handle.write(str(exc).encode("utf-8", "replace"))
                returncode = 127
            stdout_handle.flush()
            stderr_handle.flush()
            os.fsync(stdout_handle.fileno())
            os.fsync(stderr_handle.fileno())
        os.replace(stdout_temp, stdout_path)
        os.replace(stderr_temp, stderr_path)
    finally:
        stdout_temp.unlink(missing_ok=True)
        stderr_temp.unlink(missing_ok=True)
    return {
        "argv": command,
        "cwd": str(cwd),
        "returncode": returncode,
        "duration_seconds": round(time.monotonic() - started, 6),
        "timed_out": timed_out,
        "executable": executable,
    }


def run_gate(root: Path, gate: dict[str, Any], phase: str, candidate_id: str | None, no_reuse: bool) -> dict[str, Any]:
    applicability, reason = gate_applicability(root, gate, phase)
    if applicability != "APPLICABLE":
        return {"schema": "bbk.gate-result.v1", "gate_id": gate["id"], "phase": phase, "candidate_id": candidate_id, "status": applicability, "reason": reason, "blocking": bool(gate.get("blocking", True)), "assertions": gate.get("assertions", []), "reused": False}
    command = gate.get("command")
    if not isinstance(command, list) or not command:
        raise BbkError(f"Gate {gate['id']} command must be a non-empty argv array")
    cwd = (root / gate.get("cwd", ".")).resolve()
    try:
        cwd.relative_to(root.resolve())
    except ValueError as exc:
        raise BbkError(f"Gate {gate['id']} cwd escapes project root") from exc
    candidate_digest = candidate_meta(root, candidate_id)["manifest_content_sha256"] if candidate_id else None
    resolved = {
        "schema": "bbk.resolved-gate.v1", "gate": gate, "phase": phase,
        "candidate_id": candidate_id, "candidate_digest": candidate_digest,
        "cwd": str(cwd.relative_to(root)), "command": [str(x) for x in command],
        "environment": {key: os.environ.get(key) for key in sorted(gate.get("bind_environment", []))},
        "platform": {"system": platform.system(), "release": platform.release(), "machine": platform.machine(), "python": platform.python_version()},
        "executable": shutil.which(str(command[0])),
    }
    fingerprint = sha256_bytes(canonical_bytes(resolved))
    receipt_path = root / ".bbk" / "receipts" / "gates" / gate["id"] / f"{fingerprint}.json"
    stdout_path = receipt_path.with_suffix(".stdout.bin")
    stderr_path = receipt_path.with_suffix(".stderr.bin")
    if receipt_path.exists() and not no_reuse:
        existing = read_json(receipt_path)
        if (
            existing.get("status") == "PASS"
            and existing.get("fingerprint") == fingerprint
            and gate_streams_current(root, existing)
        ):
            existing["reused"] = True
            existing["receipt_path"] = str(receipt_path)
            return existing
    env = os.environ.copy()
    env.update({str(k): str(v) for k, v in gate.get("env", {}).items()})
    outcome = run_to_bound_files(
        resolved["command"],
        cwd,
        stdout_path,
        stderr_path,
        timeout=float(gate.get("timeout_seconds", 600)),
        env=env,
    )
    stdout, stdout_bytes, stdout_truncated = capture_preview(stdout_path)
    stderr, stderr_bytes, stderr_truncated = capture_preview(stderr_path)
    stdout_file = gate_stream_record(root, stdout_path)
    stderr_file = gate_stream_record(root, stderr_path)
    status = "PASS" if outcome["returncode"] == 0 else ("BLOCKED" if outcome["returncode"] == 127 else ("ERROR" if outcome["timed_out"] else "FAIL"))
    receipt = {
        "schema": "bbk.gate-receipt.v1", "bbk_version": VERSION, "gate_id": gate["id"],
        "description": gate.get("description", ""), "phase": phase, "candidate_id": candidate_id,
        "candidate_digest": candidate_digest, "fingerprint": fingerprint, "resolved_gate": resolved,
        "blocking": bool(gate.get("blocking", True)), "assertions": gate.get("assertions", []),
        "status": status, "returncode": outcome["returncode"], "timed_out": outcome["timed_out"],
        "duration_seconds": outcome["duration_seconds"], "stdout": stdout, "stderr": stderr,
        "stdout_bytes": stdout_bytes, "stderr_bytes": stderr_bytes,
        "stdout_truncated": stdout_truncated, "stderr_truncated": stderr_truncated,
        "stdout_file": stdout_file, "stderr_file": stderr_file,
        "output_transport": "file-bytes-sha256",
        "completed_at": utc_now(), "reused": False,
    }
    write_json(receipt_path, receipt)
    receipt["receipt_path"] = str(receipt_path)
    return receipt


def prevalidation_attestation(root: Path, candidate_id: str, results: list[dict[str, Any]], gates_doc: dict[str, Any]) -> dict[str, Any]:
    state = candidate_state(root, candidate_id)
    if state.get("stale"):
        raise BbkError(f"Candidate {candidate_id} is stale")
    blocking = [r for r in results if r.get("blocking") and r.get("status") not in {"SKIPPED", "NOT_APPLICABLE"}]
    allow_empty = bool(gates_doc.get("prevalidation", {}).get("allow_empty", False))
    if not blocking and not allow_empty:
        status, gap = "BLOCKED", "No applicable blocking prevalidation gate"
    elif any(r["status"] != "PASS" for r in blocking):
        status, gap = "FAIL", "One or more applicable blocking gates did not pass"
    else:
        status, gap = "PASS", None
    candidate = candidate_meta(root, candidate_id)
    value = {
        "schema": "bbk.worker-quality-attestation.v1", "bbk_version": VERSION,
        "candidate_id": candidate_id, "candidate_digest": candidate["manifest_content_sha256"],
        "phase": "prevalidate", "gate_manifest_sha256": sha256_bytes(canonical_bytes(gates_doc)),
        "status": status, "coverage_gap": gap,
        "gate_results": [{"gate_id": r["gate_id"], "status": r["status"], "fingerprint": r.get("fingerprint"), "receipt_path": r.get("receipt_path"), "reused": r.get("reused", False)} for r in results],
        "created_at": utc_now(),
        "authority_disclaimer": "This BBK attestation establishes only configured bootstrap gate eligibility.",
    }
    path = candidate_paths(root, candidate_id)[2]
    write_json(path, value)
    return value


def cmd_gate_run(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_root(args.root); assert root
    phase = validate_id(args.phase, "phase")
    gates_doc = load_gates(root)
    if args.candidate:
        checked = cmd_candidate_check(argparse.Namespace(root=str(root), id=args.candidate))
        if not checked["current"]:
            raise BbkError(f"Candidate {args.candidate} is stale")
    selected = [gate for gate in gates_doc["gates"] if not args.gate or gate["id"] in set(args.gate)]
    missing = sorted(set(args.gate or []) - {gate["id"] for gate in selected})
    if missing:
        raise BbkError(f"Unknown gate IDs: {', '.join(missing)}")
    if not selected:
        raise BbkError("No gates selected")
    with lock_project(root, f"gate:{phase}"):
        results = [run_gate(root, gate, phase, args.candidate, args.no_reuse) for gate in selected]
        attestation = None
        if phase == "prevalidate":
            if not args.candidate:
                raise BbkError("prevalidate requires --candidate")
            attestation = prevalidation_attestation(root, args.candidate, results, gates_doc)
    failures = [r for r in results if r.get("blocking") and r.get("status") in {"FAIL", "BLOCKED", "ERROR"}]
    status = "PASS" if not failures else "FAIL"
    if attestation and attestation["status"] != "PASS":
        status = attestation["status"]
    return {"schema": "bbk.gate-run.v1", "phase": phase, "candidate_id": args.candidate, "status": status, "results": results, "attestation": attestation}


def cmd_gate_list(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_root(args.root); assert root
    return load_gates(root)


def workspace_registry(root: Path) -> tuple[Path, dict[str, Any]]:
    path = root / ".bbk" / "workspaces" / "registry.json"
    if path.exists():
        value = read_json(path)
    else:
        value = {"schema": "bbk.workspace-registry.v1", "project_id": load_config(root)["project_id"], "workspaces": []}
    return path, value


def workspace_item(registry: dict[str, Any], workspace_id: str) -> dict[str, Any]:
    for item in registry.get("workspaces", []):
        if item.get("id") == workspace_id:
            return item
    raise BbkError(f"Unknown workspace id: {workspace_id}")


def workspace_inspection(item: dict[str, Any]) -> dict[str, Any]:
    path = Path(item["path"])
    value = {"exists": path.exists(), "path": str(path)}
    if path.exists():
        value["git"] = git_metadata(path)
        value["dirty"] = value["git"].get("dirty")
    return value


def candidate_workspace_refs(root: Path, path: Path) -> list[str]:
    refs = []
    for meta_path in (root / ".bbk" / "candidates").glob("*/candidate.json"):
        with contextlib.suppress(Exception):
            meta = read_json(meta_path)
            if Path(meta.get("source_root", "")).resolve() == path.resolve():
                refs.append(meta["candidate_id"])
    return refs


def cmd_workspace_create(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_root(args.root); assert root
    workspace_id = validate_id(args.id, "workspace id")
    registry_path, registry = workspace_registry(root)
    if any(i.get("id") == workspace_id and i.get("state") != "REMOVED" for i in registry.get("workspaces", [])):
        raise BbkError(f"Workspace id already active: {workspace_id}")
    meta = git_metadata(root)
    if not meta.get("available"):
        raise BbkError("Git worktree creation requires a Git repository with at least one commit")
    base_result = git(root, "rev-parse", args.base or "HEAD")
    if base_result["returncode"] != 0:
        raise BbkError(f"Invalid base: {base_result['stderr'].strip()}")
    base_commit = base_result["stdout"].strip()
    config = load_config(root)
    if args.path:
        path = Path(args.path).expanduser().resolve()
    else:
        configured = Path(config.get("workspaces", {}).get("root", "../.bbk-worktrees"))
        parent = configured if configured.is_absolute() else (root / configured).resolve()
        path = parent / root.name / workspace_id
    if path.exists():
        raise BbkError(f"Workspace path exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    branch = None if args.detach else (args.branch or f"bbk/{workspace_id}")
    with lock_project(root, f"workspace-create:{workspace_id}"):
        git_args = ["worktree", "add"]
        if args.detach:
            git_args += ["--detach", str(path), base_commit]
        else:
            git_args += ["-b", branch, str(path), base_commit]
        outcome = git(root, *git_args)
        if outcome["returncode"] != 0:
            raise BbkError(f"git worktree add failed:\n{outcome['stdout']}\n{outcome['stderr']}")
        hours = float(args.lease_hours or config.get("workspaces", {}).get("default_lease_hours", 24))
        expiry = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=hours)
        item = {
            "schema": "bbk.workspace.v1", "id": workspace_id, "path": str(path), "branch": branch,
            "base_commit": base_commit, "state": "ACTIVE", "lease_id": uuid.uuid4().hex, "lease_epoch": 1,
            "created_at": utc_now(), "expires_at": expiry.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "owner": {"pid": os.getpid(), "host": socket.gethostname(), "user": os.environ.get("USER") or os.environ.get("USERNAME")},
            "purpose": args.purpose or "",
        }
        registry.setdefault("workspaces", []).append(item)
        write_json(registry_path, registry)
    return {"status": "ACTIVE", "workspace": item, "inspection": workspace_inspection(item)}


def cmd_workspace_list(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_root(args.root); assert root
    _, registry = workspace_registry(root)
    items = [{**item, "inspection": workspace_inspection(item)} for item in registry.get("workspaces", []) if args.all or item.get("state") != "REMOVED"]
    return {"schema": "bbk.workspace-list.v1", "workspaces": items}


def cmd_workspace_inspect(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_root(args.root); assert root
    _, registry = workspace_registry(root)
    item = workspace_item(registry, validate_id(args.id, "workspace id"))
    path = Path(item["path"])
    return {"workspace": item, "inspection": workspace_inspection(item), "candidate_references": candidate_workspace_refs(root, path)}


def cmd_workspace_renew(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_root(args.root); assert root
    path, registry = workspace_registry(root)
    item = workspace_item(registry, validate_id(args.id, "workspace id"))
    if item.get("state") != "ACTIVE":
        raise BbkError(f"Cannot renew workspace in state {item.get('state')}")
    hours = float(args.hours or load_config(root).get("workspaces", {}).get("default_lease_hours", 24))
    expiry = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=hours)
    item.update({"expires_at": expiry.replace(microsecond=0).isoformat().replace("+00:00", "Z"), "lease_epoch": int(item.get("lease_epoch", 0)) + 1, "lease_id": uuid.uuid4().hex, "renewed_at": utc_now()})
    write_json(path, registry)
    return {"status": "ACTIVE", "workspace": item}


def cmd_workspace_cleanup(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_root(args.root); assert root
    path_registry, registry = workspace_registry(root)
    item = workspace_item(registry, validate_id(args.id, "workspace id"))
    path = Path(item["path"])
    inspection = workspace_inspection(item)
    refs = candidate_workspace_refs(root, path)
    if inspection.get("dirty") and not args.force:
        raise BbkError("Workspace is dirty; preserve changes or use --force")
    if refs and not args.force:
        raise BbkError(f"Workspace is referenced by candidates: {refs}")
    with lock_project(root, f"workspace-cleanup:{args.id}"):
        if path.exists():
            command = ["worktree", "remove"] + (["--force"] if args.force else []) + [str(path)]
            outcome = git(root, *command)
            if outcome["returncode"] != 0:
                raise BbkError(f"git worktree remove failed: {outcome['stderr']}")
        if args.delete_branch and item.get("branch"):
            outcome = git(root, "branch", "-D" if args.force else "-d", item["branch"])
            if outcome["returncode"] != 0:
                raise BbkError(f"Branch deletion failed: {outcome['stderr']}")
        item.update({"state": "REMOVED", "removed_at": utc_now(), "removed_forcefully": bool(args.force)})
        write_json(path_registry, registry)
        git(root, "worktree", "prune")
    return {"status": "REMOVED", "workspace": item, "prior_inspection": inspection, "candidate_references": refs}



def _relative_file_reference(root: Path, raw: str, *, kind: str) -> dict[str, Any]:
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        reference = artifact_file_reference(candidate, root=root)
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise BbkError(f"Invalid {kind} file reference {candidate}: {exc}") from exc
    return {**reference, "kind": kind}


def _normalize_project_relative(root: Path, raw: str, *, label: str, require_exists: bool = False) -> str:
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve(strict=require_exists)
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise BbkError(f"{label} must remain inside the BBK project root: {candidate}") from exc


def _question_branch_errors(value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["question branch must be a JSON object"]
    required = {
        "schema", "bbk_version", "id", "root_decision", "status", "owner_role",
        "authority", "current_recommendation", "proposal_response", "root_disposition",
        "dependencies", "accepted_related_decisions", "independent_questions",
        "exposure_history", "unresolved_point", "stopping_assessment", "next_action",
        "updated_at", "need_class", "attention",
    }
    missing = sorted(required - set(value))
    if missing:
        errors.append(f"missing required fields: {missing}")
    if value.get("schema") != "bbk.question-branch.v1":
        errors.append("schema must equal bbk.question-branch.v1")
    if not isinstance(value.get("id"), str) or not SAFE_ID.fullmatch(value.get("id", "")):
        errors.append("id must be a safe BBK identifier")
    for field in ("root_decision", "owner_role", "next_action", "updated_at"):
        if not isinstance(value.get(field), str) or not value.get(field):
            errors.append(f"{field} must be non-empty")
    statuses = {
        "ACTIVE", "WAITING_FOR_USER", "RESEARCH_BLOCKED", "PARKED", "INVALIDATED",
        "ORPHANED", "RESOLVED", "DEFERRED", "BLOCKED", "CANCELLED", "SUPERSEDED",
    }
    if value.get("status") not in statuses:
        errors.append("status is not recognized")
    responses = {None, "APPROVE", "REJECT", "REVISE"}
    if value.get("proposal_response") not in responses:
        errors.append("proposal_response is not recognized")
    dispositions = {
        None, "RESOLVED", "DEFERRED", "PARKED", "BLOCKED", "INSUFFICIENT_EVIDENCE",
        "OUT_OF_SCOPE", "CANCELLED", "SUPERSEDED",
    }
    if value.get("root_disposition") not in dispositions:
        errors.append("root_disposition is not recognized")
    authority = value.get("authority")
    if not isinstance(authority, dict) or authority.get("mode") not in {
        "USER_DECIDES", "WAYFINDER_RECOMMENDS", "DELEGATED", "CONSTRAINT_DRIVEN",
    } or not isinstance(authority.get("holder"), str) or not authority.get("holder"):
        errors.append("authority requires a recognized mode and non-empty holder")
    need_classes = {
        "ENVIRONMENT_FACT", "CONFIGURATION_PARAMETER", "REVERSIBLE_IMPLEMENTATION_CHOICE",
        "ARCHITECTURAL_DECISION", "AUTHORITY_EXPANSION", "USER_RESERVED_PREFERENCE",
    }
    need_class = value.get("need_class")
    if need_class not in need_classes:
        errors.append("need_class is not recognized")
    attention = value.get("attention")
    if not isinstance(attention, dict):
        errors.append("attention must be an object")
    else:
        if not isinstance(attention.get("requires_user_attention"), bool):
            errors.append("attention.requires_user_attention must be boolean")
        if not isinstance(attention.get("rationale"), str) or not attention.get("rationale", "").strip():
            errors.append("attention.rationale must be non-empty")
        if attention.get("discoverability") not in {"DISCOVERABLE_NOW", "DISCOVERABLE_LATER", "NOT_DISCOVERABLE_BY_BBK", "NOT_APPLICABLE"}:
            errors.append("attention.discoverability is not recognized")
        if attention.get("safe_default") is not None and not isinstance(attention.get("safe_default"), str):
            errors.append("attention.safe_default must be a string or null")
        if not isinstance(attention.get("unaffected_work_may_continue"), bool):
            errors.append("attention.unaffected_work_may_continue must be boolean")
        if need_class == "REVERSIBLE_IMPLEMENTATION_CHOICE" and attention.get("requires_user_attention") is True:
            errors.append("REVERSIBLE_IMPLEMENTATION_CHOICE must not require user attention; resolve it inside delegated freedom or reclassify a genuinely consequential branch")
        if need_class in {"ENVIRONMENT_FACT", "CONFIGURATION_PARAMETER"} and attention.get("requires_user_attention") is True:
            if attention.get("discoverability") != "NOT_DISCOVERABLE_BY_BBK" or attention.get("safe_default") is not None:
                errors.append(f"{need_class} may require user attention only when BBK cannot discover it and no safe default exists")
    for field in ("dependencies", "accepted_related_decisions", "independent_questions", "exposure_history"):
        if not isinstance(value.get(field), list) or not all(isinstance(item, str) for item in value.get(field, [])):
            errors.append(f"{field} must be an array of strings")
    stopping = value.get("stopping_assessment")
    if not isinstance(stopping, dict) or not isinstance(stopping.get("decision_ready"), bool) or not isinstance(stopping.get("reason"), str):
        errors.append("stopping_assessment requires decision_ready and reason")
    if value.get("root_disposition") == "RESOLVED":
        if value.get("status") != "RESOLVED":
            errors.append("a RESOLVED root disposition requires status RESOLVED")
        if value.get("proposal_response") != "APPROVE":
            errors.append("a RESOLVED root disposition requires proposal_response APPROVE")
        if not isinstance(value.get("accepted_decision"), str) or not value.get("accepted_decision"):
            errors.append("a RESOLVED root disposition requires accepted_decision")
    if value.get("proposal_response") in {"REJECT", "REVISE"} and value.get("root_disposition") == "RESOLVED":
        errors.append("REJECT or REVISE keeps the root question open")
    return errors


def cmd_question_validate(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.path).expanduser().resolve()
    value = read_json(path)
    errors = _question_branch_errors(value)
    return {
        "schema": "bbk.question-branch-validation.v1",
        "status": "PASS" if not errors else "FAIL",
        "valid": not errors,
        "path": str(path),
        "id": value.get("id") if isinstance(value, dict) else None,
        "root_disposition": value.get("root_disposition") if isinstance(value, dict) else None,
        "errors": errors,
    }


def cmd_question_new(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_root(args.root, required=True)
    assert root is not None
    question_id = validate_id(args.id, "question id")
    output = Path(args.output).expanduser() if args.output else root / ".bbk" / "questions" / f"{question_id}.json"
    if not output.is_absolute():
        output = root / output
    output = output.resolve()
    _normalize_project_relative(root, str(output), label="question output")
    if output.exists() and not args.force:
        raise BbkError(f"Refusing to overwrite existing question branch without --force: {output}")
    value = read_json(TEMPLATE_DIR / "question-branch.json")
    user_attention_classes = {"ARCHITECTURAL_DECISION", "AUTHORITY_EXPANSION", "USER_RESERVED_PREFERENCE"}
    unavailable_fact_requires_attention = (
        args.need_class in {"ENVIRONMENT_FACT", "CONFIGURATION_PARAMETER"}
        and args.discoverability == "NOT_DISCOVERABLE_BY_BBK"
        and args.safe_default is None
    )
    requires_user_attention = args.need_class in user_attention_classes or unavailable_fact_requires_attention
    value.update({
        "bbk_version": VERSION,
        "id": question_id,
        "root_decision": args.root_decision,
        "owner_role": args.owner_role,
        "parent_scope": args.parent_scope,
        "authority": {"mode": args.authority_mode, "holder": args.authority_holder},
        "need_class": args.need_class,
        "attention": {
            "requires_user_attention": requires_user_attention,
            "rationale": args.attention_rationale or (
                "Several materially different consequential paths require accountable user disposition."
                if args.need_class == "ARCHITECTURAL_DECISION"
                else "The exact fact is unavailable to BBK and no safe default exists."
                if unavailable_fact_requires_attention
                else "The unresolved item is classified for bounded handling without manufacturing a user decision."
            ),
            "discoverability": args.discoverability,
            "safe_default": args.safe_default,
            "unaffected_work_may_continue": not args.blocks_unaffected_work,
        },
        "next_action": args.next_action,
        "updated_at": utc_now(),
    })
    errors = _question_branch_errors(value)
    if errors:
        raise BbkError("Invalid generated question branch: " + "; ".join(errors))
    write_json(output, value)
    return {
        "schema": "bbk.question-branch-created.v1",
        "status": "PASS",
        "created": True,
        "path": _normalize_project_relative(root, str(output), label="question", require_exists=True),
        "bytes": output.stat().st_size,
        "sha256": sha256_file(output),
        "question": value,
    }


def cmd_question_list(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_root(args.root, required=True)
    assert root is not None
    base = root / ".bbk" / "questions"
    items: list[dict[str, Any]] = []
    if base.is_dir():
        for path in operational_json_paths(base):
            value = read_json(path)
            errors = _question_branch_errors(value)
            if args.status and value.get("status") != args.status:
                continue
            items.append({
                "id": value.get("id"),
                "root_decision": value.get("root_decision"),
                "status": value.get("status"),
                "proposal_response": value.get("proposal_response"),
                "root_disposition": value.get("root_disposition"),
                "need_class": value.get("need_class"),
                "requires_user_attention": (value.get("attention") or {}).get("requires_user_attention"),
                "next_action": value.get("next_action"),
                "updated_at": value.get("updated_at"),
                "path": _normalize_project_relative(root, str(path), label="question", require_exists=True),
                "valid": not errors,
                "errors": errors,
            })
    items.sort(key=lambda item: (str(item.get("updated_at") or ""), str(item.get("id") or "")), reverse=True)
    return {"schema": "bbk.question-branch-list.v1", "status": "PASS", "count": len(items), "questions": items}


def _handoff_shape_errors(value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["handoff must be a JSON object"]
    required = {
        "schema", "bbk_version", "id", "work_unit_id", "attempt", "producer",
        "subject", "disposition", "summary", "artifacts", "evidence",
        "smallest_next_action", "created_at",
    }
    missing = sorted(required - set(value))
    if missing:
        errors.append(f"missing required fields: {missing}")
    if value.get("schema") != "bbk.handoff.v1":
        errors.append("schema must equal bbk.handoff.v1")
    for field in ("id", "work_unit_id"):
        raw = value.get(field)
        if not isinstance(raw, str) or not SAFE_ID.fullmatch(raw):
            errors.append(f"{field} must be a safe BBK identifier")
    if not isinstance(value.get("attempt"), int) or isinstance(value.get("attempt"), bool) or value.get("attempt", 0) < 1:
        errors.append("attempt must be an integer >= 1")
    # Consume-only compatibility: READY_FOR_VALIDATION, BLOCKED, and PAUSED
    # remain accepted when reading or verifying legacy bbk.handoff.v1 records.
    if value.get("disposition") not in {
        "COMPLETE", "READY_FOR_VALIDATION", "PARTIAL", "BLOCKED",
        "PAUSED", "BLOCKED_TECHNICAL", "BLOCKED_AUTHORITY",
        "BLOCKED_DECISION", "PAUSED_CAPACITY", "PAUSED_HOST_WINDOW",
        "CANCELLED", "INCONCLUSIVE",
    }:
        errors.append("disposition is not recognized")
    producer = value.get("producer")
    if not isinstance(producer, dict) or not isinstance(producer.get("role"), str) or not producer.get("role"):
        errors.append("producer.role must be non-empty")
    subject = value.get("subject")
    if not isinstance(subject, dict) or not all(isinstance(subject.get(name), str) and subject.get(name) for name in ("kind", "id")):
        errors.append("subject.kind and subject.id must be non-empty strings")
    authority = value.get("authority")
    if authority is not None:
        if not isinstance(authority, dict):
            errors.append("authority must be an object or null")
        else:
            if authority.get("source") is not None and not isinstance(authority.get("source"), str):
                errors.append("authority.source must be a string or null")
            if not isinstance(authority.get("scope", []), list) or not all(isinstance(item, str) and item for item in authority.get("scope", [])):
                errors.append("authority.scope must be a string array")
    zones = value.get("capability_zones_used", [])
    if not isinstance(zones, list):
        errors.append("capability_zones_used must be an array")
    else:
        for index, zone in enumerate(zones):
            if not isinstance(zone, dict):
                errors.append(f"capability_zones_used[{index}] must be an object")
                continue
            if zone.get("kind") not in {"disposable-candidate-root", "protected-worktree", "sealed-evidence"}:
                errors.append(f"capability_zones_used[{index}].kind is not recognized")
            if not isinstance(zone.get("path"), str) or not zone.get("path"):
                errors.append(f"capability_zones_used[{index}].path must be non-empty")
    interrupt = value.get("interrupt")
    if interrupt is not None:
        allowed_interrupts = {
            "USER_CANCELLED", "CHILD_REQUESTED_STOP", "UNAUTHORIZED_EFFECT",
            "OWNERSHIP_COLLISION", "CONFIRMED_HANG", "OBSOLETE_WORK",
        }
        if not isinstance(interrupt, dict):
            errors.append("interrupt must be an object or null")
        else:
            if interrupt.get("reason") not in allowed_interrupts:
                errors.append("interrupt.reason is not recognized")
            evidence_items = interrupt.get("evidence")
            if not isinstance(evidence_items, list) or not evidence_items or not all(isinstance(item, str) and item for item in evidence_items):
                errors.append("interrupt.evidence must be a non-empty string array")
    for field in ("summary", "smallest_next_action", "created_at"):
        if not isinstance(value.get(field), str) or not value.get(field):
            errors.append(f"{field} must be non-empty")
    for field in ("artifacts", "evidence"):
        refs = value.get(field)
        if not isinstance(refs, list):
            errors.append(f"{field} must be an array")
            continue
        for index, ref in enumerate(refs):
            where = f"{field}[{index}]"
            if not isinstance(ref, dict):
                errors.append(f"{where} must be an object")
                continue
            if not isinstance(ref.get("path"), str) or not ref.get("path"):
                errors.append(f"{where}.path must be non-empty")
            if not isinstance(ref.get("bytes"), int) or isinstance(ref.get("bytes"), bool) or ref.get("bytes", -1) < 0:
                errors.append(f"{where}.bytes must be an integer >= 0")
            if not isinstance(ref.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", ref.get("sha256", "")):
                errors.append(f"{where}.sha256 must be a lowercase SHA-256 digest")
    return errors


def verify_handoff_v1(path: Path, *, root: Path) -> dict[str, Any]:
    value = read_json(path)
    errors = _handoff_shape_errors(value)
    observations: list[dict[str, Any]] = []
    for field in ("artifacts", "evidence"):
        refs = value.get(field) if isinstance(value, dict) else []
        if not isinstance(refs, list):
            continue
        for index, ref in enumerate(refs):
            if not isinstance(ref, dict) or not isinstance(ref.get("path"), str):
                continue
            raw = ref["path"]
            observed: dict[str, Any] = {"field": field, "index": index, "path": raw}
            reference_errors = artifact_verify_file_reference(ref, root=root)
            errors.extend(f"{field}[{index}] {item}" for item in reference_errors)
            try:
                actual = artifact_file_reference(root / raw, root=root)
                observed.update({"status": "PASS" if not reference_errors else "FAIL", **actual})
            except (FileNotFoundError, OSError, ValueError):
                observed["status"] = "MISSING"
            observations.append(observed)
    return {
        "schema": "bbk.handoff-verification.v1",
        "status": "PASS" if not errors else "FAIL",
        "valid": not errors,
        "handoff": {
            "path": _normalize_project_relative(root, str(path), label="handoff", require_exists=True),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "id": value.get("id") if isinstance(value, dict) else None,
            "work_unit_id": value.get("work_unit_id") if isinstance(value, dict) else None,
            "disposition": value.get("disposition") if isinstance(value, dict) else None,
            "smallest_next_action": value.get("smallest_next_action") if isinstance(value, dict) else None,
        },
        "references": observations,
        "errors": errors,
    }


def _cmd_handoff_create_v1(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_root(args.root, required=True)
    assert root is not None
    if args.disposition in {"READY_FOR_VALIDATION", "BLOCKED", "PAUSED"}:
        raise BbkError(
            f"{args.disposition} is consume-only legacy bbk.handoff.v1 vocabulary; "
            "create a handoff with a current operational disposition and carry readiness separately"
        )
    config = load_config(root)
    work_unit = validate_id(args.work_unit, "work-unit id")
    attempt = int(args.attempt)
    handoff_id = validate_id(args.id or f"HO-{work_unit}-{attempt}", "handoff id")
    output = Path(args.output).expanduser() if args.output else root / ".bbk" / "handoffs" / work_unit / f"{handoff_id}.json"
    if not output.is_absolute():
        output = root / output
    output = output.resolve()
    _normalize_project_relative(root, str(output), label="handoff output")
    if output.exists() and not args.force:
        raise BbkError(f"Refusing to overwrite existing handoff without --force: {output}")
    artifacts = [_relative_file_reference(root, raw, kind="artifact") for raw in (args.artifact or [])]
    evidence = [_relative_file_reference(root, raw, kind="evidence") for raw in (args.evidence or [])]
    changed = [_normalize_project_relative(root, raw, label="changed path") for raw in (args.changed_path or [])]
    checkpoint = None
    if args.checkpoint:
        checkpoint = _normalize_project_relative(root, args.checkpoint, label="checkpoint", require_exists=True)
    zones: list[dict[str, Any]] = []
    for raw in args.capability_zone or []:
        if "=" not in raw:
            raise invalid_argument_error(
                "--capability-zone must use KIND=PATH",
                field="capability_zone",
                received=raw,
                valid_values=["disposable-candidate-root", "protected-worktree", "sealed-evidence"],
                example_command="bbk handoff create --root . --work-unit WU-1 --disposition COMPLETE --summary done --next-action none --capability-zone protected-worktree=work",
                documentation_command="bbk handoff create --help",
                smallest_next_action="Rewrite the capability-zone value as one supported KIND=PATH pair.",
            )
        kind, raw_path = raw.split("=", 1)
        if kind not in {"disposable-candidate-root", "protected-worktree", "sealed-evidence"}:
            raise invalid_argument_error(
                f"unrecognized capability-zone kind: {kind}",
                field="capability_zone",
                received=kind,
                valid_values=["disposable-candidate-root", "protected-worktree", "sealed-evidence"],
                example_command="bbk handoff create --root . --work-unit WU-1 --disposition COMPLETE --summary done --next-action none --capability-zone protected-worktree=work",
                documentation_command="bbk handoff create --help",
                smallest_next_action="Choose one supported capability-zone kind and preserve the intended project-relative path.",
            )
        zone_path = _normalize_project_relative(root, raw_path, label="capability zone")
        zones.append({"kind": kind, "path": zone_path, "operations": []})
    if args.interrupt_reason and not args.interrupt_evidence:
        raise BbkError("--interrupt-reason requires at least one --interrupt-evidence")
    if args.interrupt_evidence and not args.interrupt_reason:
        raise BbkError("--interrupt-evidence requires --interrupt-reason")
    partial_work_location = None
    if args.partial_work_location:
        partial_work_location = _normalize_project_relative(
            root, args.partial_work_location, label="partial work location"
        )
    authority = None
    if args.authority_source or args.authority_scope:
        authority = {
            "source": args.authority_source,
            "scope": list(args.authority_scope or []),
            "standing": not args.authority_not_standing,
        }
    interrupt = None
    if args.interrupt_reason:
        interrupt = {
            "reason": args.interrupt_reason,
            "evidence": list(args.interrupt_evidence or []),
            "partial_work_location": partial_work_location,
        }
    value = {
        "schema": "bbk.handoff.v1",
        "bbk_version": VERSION,
        "id": handoff_id,
        "project_id": config.get("project_id"),
        "work_unit_id": work_unit,
        "attempt": attempt,
        "producer": {
            "role": args.role,
            "invocation_id": args.invocation_id,
            "thread_id": args.thread_id,
        },
        "subject": {
            "kind": args.subject_kind,
            "id": args.subject_id or work_unit,
            "revision": args.subject_revision,
        },
        "authority": authority,
        "capability_zones_used": zones,
        "interrupt": interrupt,
        "disposition": args.disposition,
        "summary": args.summary,
        "work_performed": list(args.work_performed or []),
        "changed_paths": changed,
        "commands": list(args.command_run or []),
        "checks": list(args.check or []),
        "findings": list(args.finding or []),
        "discoveries": list(args.discovery or []),
        "residual_uncertainty": list(args.residual or []),
        "blockers": list(args.blocker or []),
        "artifacts": artifacts,
        "evidence": evidence,
        "continuation": {
            "state": args.continuation_state,
            "checkpoint_path": checkpoint,
            "resume_same_thread": not args.no_resume_same_thread,
            "completed_step": args.completed_step,
            "next_step": args.next_step,
        },
        "smallest_next_action": args.next_action,
        "created_at": utc_now(),
    }
    errors = _handoff_shape_errors(value)
    if errors:
        raise BbkError("Invalid handoff: " + "; ".join(errors))
    write_json(output, value)
    result = verify_handoff_v1(output, root=root)
    result["created"] = True
    return result


def verify_handoff(path: Path, *, root: Path) -> dict[str, Any]:
    """Verify sealed v2 handoffs while retaining read compatibility for v1 files."""
    if path.is_dir():
        try:
            result = verify_handoff_v2_package(path)
        except (OSError, ValueError, ArtifactPackageError) as exc:
            diagnostic = exc.result if isinstance(exc, ArtifactPackageError) else None
            return {
                "schema": "bbk.handoff-verification.v2", "status": "FAIL", "valid": False,
                "handoff": {"path": str(path), "id": None, "work_unit_id": None, "disposition": None},
                "references": [], "errors": [str(exc)], "diagnostic": diagnostic,
            }
        try:
            result["handoff"]["path"] = _normalize_project_relative(root, str(path), label="handoff", require_exists=True)
        except BbkError:
            result["handoff"]["path"] = str(path)
        return result
    return verify_handoff_v1(path, root=root)


def _handoff_v2_source_items(root: Path, values: Sequence[str], *, field: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sources: list[dict[str, Any]] = []
    semantic_refs: list[dict[str, Any]] = []
    folder = "artifacts" if field == "artifact" else "evidence"
    role = "result" if field == "artifact" else "evidence"
    for index, raw in enumerate(values, 1):
        relative = _normalize_project_relative(root, raw, label=field, require_exists=True)
        source = (root / relative).resolve(strict=True)
        if not source.is_file():
            raise BbkError(f"{field} must be a regular file: {relative}")
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", source.name).strip(".-") or "file"
        artifact_id = f"{field}-{index:03d}"
        package_path = f"{folder}/{index:03d}-{safe_name}"
        sources.append({
            "artifactId": artifact_id, "sourcePath": str(source), "packagePath": package_path,
            "role": role, "mediaType": "application/json" if source.suffix.lower() == ".json" else None,
        })
        semantic_refs.append({"artifactId": artifact_id, "path": package_path, "kind": field})
    return sources, semantic_refs


def cmd_handoff_create(args: argparse.Namespace) -> dict[str, Any]:
    if getattr(args, "legacy_v1", False):
        return _cmd_handoff_create_v1(args)
    if args.force:
        raise BbkError("sealed bbk.handoff.v2 packages are immutable and never overwritten; omit --force and choose a new ID or output")
    root = resolve_root(args.root, required=True)
    assert root is not None
    config = load_config(root)
    work_unit = validate_id(args.work_unit, "work-unit id")
    attempt = int(args.attempt)
    handoff_id = validate_id(args.id or f"HO-{work_unit}-{attempt}", "handoff id")
    output = Path(args.output).expanduser() if args.output else root / ".bbk" / "handoffs" / work_unit / handoff_id
    if not output.is_absolute():
        output = root / output
    output = output.absolute()
    _normalize_project_relative(root, str(output), label="handoff output")

    artifact_sources, artifact_refs = _handoff_v2_source_items(root, args.artifact or [], field="artifact")
    evidence_sources, evidence_refs = _handoff_v2_source_items(root, args.evidence or [], field="evidence")
    changed = [_normalize_project_relative(root, raw, label="changed path") for raw in (args.changed_path or [])]
    checkpoint = _normalize_project_relative(root, args.checkpoint, label="checkpoint", require_exists=True) if args.checkpoint else None
    zones: list[dict[str, Any]] = []
    for raw in args.capability_zone or []:
        if "=" not in raw:
            raise invalid_argument_error(
                "--capability-zone must use KIND=PATH",
                field="capability_zone",
                received=raw,
                valid_values=["disposable-candidate-root", "protected-worktree", "sealed-evidence"],
                example_command="bbk handoff create --root . --work-unit WU-1 --disposition COMPLETE --summary done --next-action none --capability-zone protected-worktree=work",
                documentation_command="bbk handoff create --help",
                smallest_next_action="Rewrite the capability-zone value as one supported KIND=PATH pair.",
            )
        kind, raw_path = raw.split("=", 1)
        if kind not in {"disposable-candidate-root", "protected-worktree", "sealed-evidence"}:
            raise invalid_argument_error(
                f"unrecognized capability-zone kind: {kind}",
                field="capability_zone",
                received=kind,
                valid_values=["disposable-candidate-root", "protected-worktree", "sealed-evidence"],
                example_command="bbk handoff create --root . --work-unit WU-1 --disposition COMPLETE --summary done --next-action none --capability-zone protected-worktree=work",
                documentation_command="bbk handoff create --help",
                smallest_next_action="Choose one supported capability-zone kind and preserve the intended project-relative path.",
            )
        zones.append({"kind": kind, "path": _normalize_project_relative(root, raw_path, label="capability zone"), "operations": []})
    if args.interrupt_reason and not args.interrupt_evidence:
        raise BbkError("--interrupt-reason requires at least one --interrupt-evidence")
    if args.interrupt_evidence and not args.interrupt_reason:
        raise BbkError("--interrupt-evidence requires --interrupt-reason")
    partial_work_location = _normalize_project_relative(root, args.partial_work_location, label="partial work location") if args.partial_work_location else None
    authority = None
    if args.authority_source or args.authority_scope:
        authority = {"source": args.authority_source, "scope": list(args.authority_scope or []), "standing": not args.authority_not_standing}
    interrupt = None
    if args.interrupt_reason:
        interrupt = {"reason": args.interrupt_reason, "evidence": list(args.interrupt_evidence or []), "partial_work_location": partial_work_location}
    prohibited = list(dict.fromkeys([
        *(args.prohibited_claim or []),
        "independent validation", "parent integration", "finding closure", "acceptance", "deployment authorization", "release",
    ]))
    semantic = {
        "schema": "bbk.handoff.v2", "bbk_version": VERSION, "id": handoff_id,
        "project_id": config.get("project_id"), "work_unit_id": work_unit, "attempt": attempt,
        "producer": {"role": args.role, "invocation_id": args.invocation_id, "thread_id": args.thread_id},
        "subject": {"kind": args.subject_kind, "id": args.subject_id or work_unit, "revision": args.subject_revision},
        "authority": authority, "capability_zones_used": zones, "interrupt": interrupt,
        "disposition": args.disposition, "summary": args.summary,
        "work_performed": list(args.work_performed or []), "changed_paths": changed,
        "commands": list(args.command_run or []), "checks": list(args.check or []),
        "findings": list(args.finding or []), "discoveries": list(args.discovery or []),
        "residual_uncertainty": list(args.residual or []), "blockers": list(args.blocker or []),
        "artifacts": artifact_refs, "evidence": evidence_refs,
        "effects_and_cleanup": {
            "state": args.cleanup_state, "actions": list(args.cleanup_action or []),
            "residuals": list(args.residual or []),
        },
        "continuation": {
            "state": args.continuation_state, "checkpoint": checkpoint,
            "resume_same_thread": not args.no_resume_same_thread,
            "completed_step": args.completed_step, "next_step": args.next_step,
        },
        "prohibited_claims": prohibited, "smallest_next_action": args.next_action,
        "created_at": utc_now(), "authority_boundary": HANDOFF_V2_AUTHORITY_BOUNDARY,
    }
    try:
        sealed = seal_handoff_v2(semantic, [*artifact_sources, *evidence_sources], output_root=output, revision=str(attempt))
    except ArtifactPackageError as exc:
        raise BbkError(str(exc), diagnostic=exc.result) from exc
    result = verify_handoff(output, root=root)
    result["created"] = True
    result["seal"] = {key: sealed.get(key) for key in ("packageId", "revision", "contentSha256", "manifestSha256", "authorityBoundary")}
    return result


def cmd_handoff_verify(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.path).expanduser().resolve()
    root = resolve_root(args.root, required=False)
    if root is None:
        root = project_root(path.parent, required=True)
    assert root is not None
    return verify_handoff(path, root=root)


def cmd_handoff_list(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_root(args.root, required=True)
    assert root is not None
    base = root / ".bbk" / "handoffs"
    items: list[dict[str, Any]] = []
    if base.is_dir():
        package_roots = sorted({path.parent for path in base.rglob("bbk-package.json")})
        for package_path in package_roots:
            try:
                value = load_handoff_v2_value(package_path)
                if args.work_unit and value.get("work_unit_id") != args.work_unit:
                    continue
                verification = verify_handoff(package_path, root=root)
                items.append({**verification["handoff"], "valid": verification["valid"], "errors": verification["errors"]})
            except (BbkError, OSError, ValueError, StrictJsonError, ArtifactPackageError) as exc:
                items.append({
                    "path": _normalize_project_relative(root, str(package_path), label="handoff", require_exists=True),
                    "format": "SEALED_V2", "valid": False, "errors": [str(exc)],
                    "created_at": None, "attempt": None,
                })
        package_roots_resolved = [path.resolve() for path in package_roots]
        for path in operational_json_paths(base, recursive=True):
            resolved = path.resolve()
            if any(package_root == resolved or package_root in resolved.parents for package_root in package_roots_resolved):
                continue
            try:
                value = read_json(path)
                if value.get("schema") != "bbk.handoff.v1":
                    continue
                if args.work_unit and value.get("work_unit_id") != args.work_unit:
                    continue
                verification = verify_handoff_v1(path, root=root)
                items.append({
                    **verification["handoff"], "attempt": value.get("attempt"),
                    "created_at": value.get("created_at"), "producer_role": (value.get("producer") or {}).get("role"),
                    "continuation": value.get("continuation"), "format": "LEGACY_V1",
                    "valid": verification["valid"], "errors": verification["errors"],
                })
            except (BbkError, OSError, json.JSONDecodeError, StrictJsonError) as exc:
                items.append({
                    "path": _normalize_project_relative(root, str(path), label="handoff", require_exists=True),
                    "format": "LEGACY_V1", "valid": False, "errors": [str(exc)],
                    "created_at": None, "attempt": None,
                })
    items.sort(key=lambda item: (str(item.get("created_at") or ""), int(item.get("attempt") or 0), str(item.get("path") or "")), reverse=True)
    latest = items[0] if items else None
    if args.latest and latest is not None:
        items = [latest]
    return {
        "schema": "bbk.handoff-list.v2", "status": "PASS", "root": str(root),
        "work_unit_id": args.work_unit, "count": len(items), "latest": latest, "handoffs": items,
        "compatibility": {"defaultProducer": "bbk.handoff.v2", "legacyV1Readable": True},
    }


def _schema_tool_root(root: Path | None, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    if value := os.environ.get("BBK_TOOL_ROOT"):
        return Path(value).expanduser().resolve() / "jsonschema-4.25.1"
    if root is not None:
        return root / ".bbk" / "tooling" / "jsonschema-4.25.1"
    return Path.home() / ".cache" / "bbk" / "tooling" / "jsonschema-4.25.1"


def _venv_python(root: Path) -> Path:
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _jsonschema_runtime(tool_root: Path | None = None) -> tuple[Any | None, str | None]:
    if tool_root is not None:
        candidates = [
            tool_root / "Lib" / "site-packages",
            tool_root / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages",
        ]
        for site_packages in candidates:
            if site_packages.is_dir() and str(site_packages) not in sys.path:
                sys.path.insert(0, str(site_packages))
    try:
        import importlib
        import jsonschema  # type: ignore
        importlib.invalidate_caches()
        try:
            version = importlib_metadata.version("jsonschema")
        except importlib_metadata.PackageNotFoundError:
            version = None
        return jsonschema, version
    except ModuleNotFoundError:
        return None, None



def _schema_error_detail(error: Any) -> dict[str, Any]:
    pointer = "/" + "/".join(str(part).replace("~", "~0").replace("/", "~1") for part in error.absolute_path) if error.absolute_path else ""
    schema_pointer = "/" + "/".join(str(part).replace("~", "~0").replace("/", "~1") for part in error.absolute_schema_path) if error.absolute_schema_path else ""
    detail: dict[str, Any] = {
        "pointer": pointer,
        "schema_pointer": schema_pointer,
        "message": error.message,
        "validator": error.validator,
        "supplied_value": error.instance,
    }
    if error.validator == "enum":
        detail["allowed_values"] = error.validator_value
    elif error.validator == "const":
        detail["allowed_values"] = [error.validator_value]
    elif error.validator == "type":
        detail["expected_type"] = error.validator_value
    elif error.validator == "required":
        detail["required_fields"] = error.validator_value
    if isinstance(error.schema, Mapping):
        detail["smallest_valid_example"] = _smallest_schema_example(error.schema)
        if error.schema.get("description"):
            detail["description"] = error.schema.get("description")
    return detail



def cmd_schema_status(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_root(args.root, required=False)
    package, version = _jsonschema_runtime()
    tool_root = _schema_tool_root(root, args.tool_dir)
    tool_python = _venv_python(tool_root)
    return {
        "schema": "bbk.schema-validator-status.v1",
        "status": "PASS" if package is not None or tool_python.is_file() else "BLOCKED",
        "draft": "2020-12",
        "current_interpreter": {
            "python": sys.executable,
            "jsonschema_available": package is not None,
            "jsonschema_version": version,
        },
        "managed_environment": {
            "root": str(tool_root),
            "python": str(tool_python),
            "available": tool_python.is_file(),
        },
        "ensure_command": f'bbk schema validate --ensure --schema <schema.json> --instance <instance.json>',
    }


def _resolve_schema_path(raw: str) -> Path:
    entry = SCHEMA_TEMPLATE_REGISTRY.get(raw)
    path = SCHEMA_DIR / entry["schema"] if entry else Path(raw).expanduser()
    path = path.resolve()
    if not path.is_file():
        raise BbkError(f"Schema is unavailable: {path}")
    return path


def _decode_json_pointer(pointer: str) -> list[str]:
    if pointer in {"", "/"}:
        return []
    if not pointer.startswith("/"):
        raise BbkError(f"JSON pointer must be empty or start with '/': {pointer}")
    return [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]


def _pointer_value(value: Any, pointer: str) -> Any:
    current = value
    for part in _decode_json_pointer(pointer):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            raise BbkError(f"JSON pointer does not exist in instance: {pointer}")
    return current


def _resolve_schema_ref(document: dict[str, Any], document_path: Path, ref: str) -> tuple[dict[str, Any], Path, Any]:
    file_part, _, fragment = ref.partition("#")
    if file_part:
        candidate = (document_path.parent / file_part).resolve()
        if not candidate.is_file():
            candidate = (SCHEMA_DIR / file_part).resolve()
        target_document = read_json(candidate)
        target_path = candidate
    else:
        target_document = document
        target_path = document_path
    node: Any = target_document
    if fragment:
        node = _pointer_value(target_document, fragment if fragment.startswith("/") else "/" + fragment)
    return target_document, target_path, node


def _schema_node_for_instance_pointer(schema_path: Path, pointer: str) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    document = read_json(schema_path)
    if not isinstance(document, dict):
        raise BbkError(f"Schema root must be an object: {schema_path}")
    current_document = document
    current_path = schema_path
    node: Any = document
    for segment in _decode_json_pointer(pointer):
        while isinstance(node, dict) and isinstance(node.get("$ref"), str):
            current_document, current_path, node = _resolve_schema_ref(current_document, current_path, node["$ref"])
        if not isinstance(node, dict):
            raise BbkError(f"Schema has no object node for instance pointer {pointer}")
        properties = node.get("properties")
        if isinstance(properties, dict) and segment in properties:
            node = properties[segment]
            continue
        if node.get("type") == "array" or "items" in node:
            node = node.get("items", {})
            continue
        additional = node.get("additionalProperties")
        if isinstance(additional, dict):
            node = additional
            continue
        raise BbkError(f"Schema does not describe instance pointer {pointer} at segment {segment!r}")
    while isinstance(node, dict) and isinstance(node.get("$ref"), str):
        current_document, current_path, node = _resolve_schema_ref(current_document, current_path, node["$ref"])
    if not isinstance(node, dict):
        raise BbkError(f"Schema node for {pointer} is not an object")
    return current_document, current_path, node


def _smallest_schema_example(node: Any) -> Any:
    if not isinstance(node, dict):
        return None
    if "const" in node:
        return node["const"]
    if isinstance(node.get("examples"), list) and node["examples"]:
        return node["examples"][0]
    if "default" in node:
        return node["default"]
    if isinstance(node.get("enum"), list) and node["enum"]:
        return node["enum"][0]
    if isinstance(node.get("oneOf"), list) and node["oneOf"]:
        return _smallest_schema_example(node["oneOf"][0])
    if isinstance(node.get("anyOf"), list) and node["anyOf"]:
        return _smallest_schema_example(node["anyOf"][0])
    kind = node.get("type")
    if isinstance(kind, list):
        if "null" in kind:
            return None
        kind = kind[0] if kind else None
    if kind == "object" or isinstance(node.get("properties"), dict):
        properties = node.get("properties") or {}
        return {name: _smallest_schema_example(properties.get(name, {})) for name in node.get("required", [])}
    if kind == "array":
        count = int(node.get("minItems", 0) or 0)
        return [_smallest_schema_example(node.get("items", {})) for _ in range(count)]
    if kind == "string":
        return "value"
    if kind == "integer":
        return int(node.get("minimum", 0) or 0)
    if kind == "number":
        return float(node.get("minimum", 0) or 0)
    if kind == "boolean":
        return False
    return None


def _operation_environment(values: Sequence[str] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values or ():
        if "=" not in value:
            raise BbkError(f"operation environment must be KEY=VALUE: {value}")
        key, raw = value.split("=", 1)
        result[key] = raw
    return result


def cmd_operation_list(args: argparse.Namespace) -> dict[str, Any]:
    from deterministic_operations import load_registry
    registry = load_registry(Path(args.registry) if args.registry else None)
    return {
        "schema": "bbk.deterministic-operation-registry.v1",
        "registry_id": registry["registry_id"],
        "revision": registry["revision"],
        "operations": registry["operations"],
    }


def cmd_operation_qualify(args: argparse.Namespace) -> dict[str, Any]:
    from deterministic_operations import OperationAdmissionError, qualify_operation
    try:
        return qualify_operation(
            args.operation_id,
            subject=args.subject,
            argv=args.argv or (),
            environment=_operation_environment(args.environment),
            registry_path=Path(args.registry) if args.registry else None,
        )
    except OperationAdmissionError as exc:
        raise BbkError(str(exc), diagnostic={"schema": "bbk.operation-qualification.v1", "status": "REJECTED", "code": exc.code, "message": str(exc)}) from exc


def cmd_operation_run(args: argparse.Namespace) -> dict[str, Any]:
    from deterministic_operations import OperationAdmissionError, run_registered_operation
    try:
        return run_registered_operation(
            args.operation_id,
            subject=args.subject,
            argv=args.argv or (),
            environment=_operation_environment(args.environment),
            registry_path=Path(args.registry) if args.registry else None,
        )
    except OperationAdmissionError as exc:
        # Qualification happens before the callable is entered.  Preserve that
        # boundary in the CLI error instead of executing an ad-hoc fallback.
        raise BbkError(str(exc), diagnostic={"schema": "bbk.operation-qualification.v1", "status": "REJECTED", "code": exc.code, "message": str(exc), "effects_observed": "NONE"}) from exc


def cmd_identity_validate(args: argparse.Namespace) -> dict[str, Any]:
    from identity_graph import IdentityGraphError, validate_file
    try:
        return validate_file(Path(args.path).expanduser().resolve())
    except IdentityGraphError as exc:
        raise BbkError(str(exc), diagnostic={"schema": "bbk.identity-graph-validation.v1", "status": "REJECTED", "code": exc.code, "message": str(exc)}) from exc


def cmd_identity_derive(args: argparse.Namespace) -> dict[str, Any]:
    from identity_graph import IdentityGraphError, derive_identity
    try:
        payload = json.loads(Path(args.payload).read_text(encoding="utf-8")) if args.payload else None
        node = derive_identity(
            args.kind,
            subject={"kind": args.subject_kind, "id": args.subject_id, "revision": args.subject_revision, "digest": args.subject_digest},
            revision=args.revision,
            payload=payload,
            node_id=args.node_id,
        )
        if args.output:
            output = Path(args.output).expanduser().resolve()
            if output.exists() and not args.force:
                raise BbkError(f"output already exists: {output}")
            write_json(output, node)
        return {"schema": "bbk.identity-node.v1", "status": "PASS", "node": node, "output": args.output}
    except IdentityGraphError as exc:
        raise BbkError(str(exc), diagnostic={"schema": "bbk.identity-node.v1", "status": "REJECTED", "code": exc.code, "message": str(exc)}) from exc


def _schema_registry_paths(schema_root: Path, extra_paths: Sequence[Path] = ()) -> list[Path]:
    """Return every schema resource path in stable physical-path order.

    Role return/result schemas intentionally live below nested directories.  A
    top-level-only glob leaves their declared ``$id`` values unavailable to the
    Draft 2020-12 resolver even though the package contains the files.
    """
    root = schema_root.resolve()
    candidates = {path.resolve() for path in root.rglob("*.json") if path.is_file()}
    candidates.update(path.resolve() for path in extra_paths if path.is_file())
    return sorted(candidates, key=lambda path: path.as_posix())


def _build_schema_registry(
    schema_root: Path,
    *,
    extra_paths: Sequence[Path] = (),
) -> tuple[Any, dict[str, Any]]:
    """Build one deterministic local-only registry and reject URI ambiguity."""
    from referencing import Registry, Resource  # type: ignore

    root = schema_root.resolve()
    paths = _schema_registry_paths(root, extra_paths)
    registry = Registry()
    uri_owners: dict[str, Path] = {}
    declared_ids: list[str] = []
    records: list[dict[str, Any]] = []

    for candidate in paths:
        value = read_json(candidate)
        if not isinstance(value, dict):
            continue
        resource = Resource.from_contents(value)
        declared = value.get("$id")
        uris: list[str] = []
        if isinstance(declared, str) and declared.strip():
            uris.append(declared.strip())
        uris.append(candidate.as_uri())
        for uri in uris:
            prior = uri_owners.get(uri)
            if prior is not None and prior != candidate:
                message = f"Schema registry URI {uri!r} is declared by both {prior} and {candidate}"
                raise BbkError(
                    message,
                    diagnostic={
                        "schema": "bbk.schema-registry-error.v1",
                        "status": "ERROR",
                        "code": "SCHEMA_REGISTRY_DUPLICATE_ID",
                        "message": message,
                        "duplicate_uri": uri,
                        "first_path": str(prior),
                        "duplicate_path": str(candidate),
                        "registry_roots": [str(root)],
                        "smallest_next_action": "Give every packaged schema one unique declared $id and rerun validation.",
                    },
                )
            if prior is None:
                uri_owners[uri] = candidate
                registry = registry.with_resource(uri, resource)
        if isinstance(declared, str) and declared.strip():
            declared_ids.append(declared.strip())
        records.append({
            "path": str(candidate),
            "file_uri": candidate.as_uri(),
            "declared_id": declared.strip() if isinstance(declared, str) and declared.strip() else None,
        })

    metadata = {
        "registry_roots": [str(root)],
        "registered_schema_ids": sorted(declared_ids),
        "registered_schema_files": records,
        "registered_resource_count": len(uri_owners),
    }
    return registry, metadata


def _reference_error_uri(exc: BaseException) -> str | None:
    for candidate in (exc, exc.__cause__, exc.__context__, getattr(exc, "_wrapped", None)):
        ref = getattr(candidate, "ref", None)
        if isinstance(ref, str) and ref:
            return ref
    return None


def _schema_reference_failure(
    exc: BaseException,
    *,
    schema_path: Path,
    schema_value: Any,
    registry_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    unresolved_uri = _reference_error_uri(exc)
    filename = Path(urlparse(unresolved_uri).path).name if unresolved_uri else ""
    registered_files = registry_metadata.get("registered_schema_files", [])
    matching = [
        record["path"]
        for record in registered_files
        if isinstance(record, Mapping) and filename and Path(str(record.get("path", ""))).name == filename
    ]
    return {
        "schema": "bbk.schema-validation.v1",
        "status": "BLOCKED",
        "valid": False,
        "code": "SCHEMA_REFERENCE_UNRESOLVED",
        "draft": "2020-12",
        "schema_path": str(schema_path),
        "schema_sha256": sha256_file(schema_path),
        "referencing_schema": {
            "path": str(schema_path),
            "declared_id": schema_value.get("$id") if isinstance(schema_value, Mapping) else None,
        },
        "unresolved_uri": unresolved_uri,
        "registry_roots": list(registry_metadata.get("registry_roots", [])),
        "registered_schema_ids": list(registry_metadata.get("registered_schema_ids", [])),
        "candidate_physical_files": matching,
        "error": str(exc),
        "exception_type": f"{type(exc).__module__}.{type(exc).__name__}",
        "exception_traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        "instances": [],
        "smallest_next_action": "Restore or register the schema resource identified by unresolved_uri, then rerun the same validation.",
    }


def _jsonschema_validator(schema_path: Path) -> tuple[Any | None, str | None, str | None]:
    package, version = _jsonschema_runtime()
    if package is None:
        return None, None, "The Python jsonschema package is not available."
    schema_value = read_json(schema_path)
    try:
        registry, _ = _build_schema_registry(SCHEMA_DIR, extra_paths=(schema_path,))
        validator = package.Draft202012Validator(schema_value, registry=registry)
    except Exception as exc:
        return None, version, f"Could not initialize Draft 2020-12 registry: {exc}"
    return validator, version, None


def _builtin_schema_report(instance: Any) -> dict[str, Any] | None:
    if not isinstance(instance, dict):
        return None
    schema_name = instance.get("schema")
    validators: dict[str, Any] = {
        "bbk.solution-outcome-fit.v1": validate_solution_outcome_fit,
        "bbk.implementation-structure-contract.v1": validate_structure_v2,
        "bbk.implementation-structure-contract.v2": validate_structure_v2,
        "bbk.implementation-structure-contract.v3": validate_structure_v2,
        "bbk.execution-slice.v1": validate_slice_v2,
        "bbk.execution-slice.v2": validate_slice_v2,
        "bbk.state-decision-effect-design.v1": validate_state_decision_effect,
        "bbk.state-transition-trace.v1": validate_transition_trace,
        "bbk.assurance-contract.v1": validate_assurance_contract,
        "bbk.evidence-receipt.v2": validate_evidence_receipt,
    }
    if schema_name == "bbk.question-branch.v1":
        errors = _question_branch_errors(instance)
        return {"valid": not errors, "errors": errors, "warnings": []}
    if schema_name == "bbk.artifact-manifest.v1":
        errors: list[str] = []
        for field in ("bbk_version", "root_label", "content_sha256", "files"):
            if field not in instance:
                errors.append(f"missing required field: {field}")
        return {"valid": not errors, "errors": errors, "warnings": []}
    validator = validators.get(str(schema_name))
    if validator is None and {"id", "taskKind", "instructionPackage"}.issubset(instance):
        validator = validate_work_unit
    return validator(instance) if validator else None


def cmd_schema_list(args: argparse.Namespace) -> dict[str, Any]:
    items = []
    for kind, entry in sorted(SCHEMA_TEMPLATE_REGISTRY.items()):
        items.append({
            "kind": kind,
            "schema": str((SCHEMA_DIR / entry["schema"]).resolve()),
            "template": str((TEMPLATE_DIR / entry["template"]).resolve()) if entry.get("template") else None,
        })
    return {
        "schema": "bbk.schema-catalog.v1",
        "status": "PASS",
        "count": len(items),
        "items": items,
        "implementation_structure": {
            "versions": ["v1", "v2", "v3"],
            "depths": ["compact", "standard", "full"],
            "subject_kinds": ["software", "automation", "hardware", "procedure", "data", "document", "infrastructure", "network_configuration", "deployment_configuration", "mixed", "other"],
        },
    }


def cmd_schema_template(args: argparse.Namespace) -> dict[str, Any]:
    if args.kind not in SCHEMA_TEMPLATE_REGISTRY:
        raise BbkError(f"Unknown template kind {args.kind!r}; use `bbk schema list`")
    output = Path(args.output).expanduser().resolve()
    if output.exists() and not args.force:
        raise BbkError(f"Refusing to overwrite {output}; pass --force to replace it")
    if args.kind == "artifact-manifest":
        value = {
            "schema": "bbk.artifact-manifest.v1", "bbk_version": VERSION,
            "subject": None, "root_label": "project", "content_sha256": sha256_bytes(canonical_bytes({"schema": "bbk.artifact-manifest-content.v1", "subject": None, "root_label": "project", "files": []})),
            "file_count": 0, "total_bytes": 0, "files": [],
        }
        write_json(output, value)
        template_name = "generated-empty-artifact-manifest"
    else:
        entry = SCHEMA_TEMPLATE_REGISTRY[args.kind]
        template_name = entry["template"]
        if args.kind == "implementation-structure":
            subject_kind = args.subject_kind or "software"
            depth = args.depth or "standard"
            if depth == "compact" and subject_kind in {"infrastructure", "network_configuration", "deployment_configuration"}:
                template_name = "implementation-structure-contract-v3-infrastructure-compact.json"
        source = _template_path(template_name)
        atomic_write(output, source.read_bytes())
        value = read_json(output)
        if args.kind == "implementation-structure":
            value.setdefault("subject", {})["kind"] = args.subject_kind or "software"
            value["contractDepth"] = args.depth or "standard"
            write_json(output, value)
    return {
        "schema": "bbk.schema-template-created.v1",
        "status": "PASS",
        "kind": args.kind,
        "template": template_name,
        "output": str(output),
        "bytes": output.stat().st_size,
        "sha256": sha256_file(output),
    }


def cmd_schema_enum(args: argparse.Namespace) -> dict[str, Any]:
    schema_path = _resolve_schema_path(args.schema)
    _, _, node = _schema_node_for_instance_pointer(schema_path, args.pointer)
    return {
        "schema": "bbk.schema-node.v1",
        "status": "PASS",
        "schema_path": str(schema_path),
        "pointer": args.pointer,
        "type": node.get("type"),
        "enum": node.get("enum"),
        "const": node.get("const"),
        "description": node.get("description"),
        "smallest_valid_example": _smallest_schema_example(node),
        "node": node,
    }


def cmd_schema_explain(args: argparse.Namespace) -> dict[str, Any]:
    schema_path = _resolve_schema_path(args.schema)
    instance_path = Path(args.instance).expanduser().resolve()
    instance = read_json(instance_path)
    external_errors: list[dict[str, Any]] = []
    validator, version, external_blocker = _jsonschema_validator(schema_path)
    if validator is not None:
        for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.absolute_path)):
            pointer = "/" + "/".join(str(part).replace("~", "~0").replace("/", "~1") for part in error.absolute_path) if error.absolute_path else ""
            external_errors.append({"pointer": pointer, "message": error.message, "validator": error.validator})
    builtin = _builtin_schema_report(instance)
    target_pointer = args.pointer
    if target_pointer is None and external_errors:
        target_pointer = external_errors[0]["pointer"]
    supplied = None
    node: dict[str, Any] | None = None
    node_error = None
    if target_pointer is not None:
        try:
            supplied = _pointer_value(instance, target_pointer)
        except BbkError:
            supplied = None
        try:
            _, _, node = _schema_node_for_instance_pointer(schema_path, target_pointer)
        except BbkError as exc:
            node_error = str(exc)
    valid = not external_errors if validator is not None else bool(builtin and builtin.get("valid"))
    return {
        "schema": "bbk.schema-explanation.v1",
        "status": "PASS" if valid else ("BLOCKED" if validator is None and builtin is None else "FAIL"),
        "valid": valid,
        "schema_path": str(schema_path),
        "instance_path": str(instance_path),
        "draft": "2020-12",
        "external_validator": {
            "available": validator is not None,
            "version": version,
            "blocker": external_blocker,
            "errors": external_errors,
        },
        "builtin_validator": builtin,
        "focus": {
            "pointer": target_pointer,
            "supplied_value": supplied,
            "schema_node": node,
            "node_error": node_error,
            "allowed_values": (node or {}).get("enum"),
            "smallest_valid_example": _smallest_schema_example(node or {}),
            "applicability": (node or {}).get("description"),
        },
    }


def _ensure_jsonschema_environment(tool_root: Path, wheelhouse: str | None) -> dict[str, Any]:
    site_packages = tool_root / (Path("Lib") / "site-packages" if os.name == "nt" else Path(f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages"))
    site_packages.mkdir(parents=True, exist_ok=True)
    operations: list[dict[str, Any]] = []
    argv = python_command(
        None,
        "install",
        "--target",
        str(site_packages),
        "--disable-pip-version-check",
        "jsonschema==4.25.1",
        module="pip",
    )
    if wheelhouse:
        argv.extend(["--no-index", "--find-links", str(Path(wheelhouse).expanduser().resolve())])
    result = run(argv, Path.cwd(), timeout=600)
    operations.append({"operation": "install-jsonschema", **result})
    if result["returncode"] != 0:
        raise BbkError(f"Could not install jsonschema 4.25.1: {result['stderr'] or result['stdout']}")
    return {"python": str(direct_python_executable()), "site_packages": str(site_packages), "operations": operations}


def cmd_schema_validate(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_root(args.root, required=False)
    tool_root = _schema_tool_root(root, args.tool_dir)
    package, version = _jsonschema_runtime(tool_root)
    if package is None:
        tool_python = _venv_python(tool_root)
        if not tool_python.is_file() and args.ensure:
            ensured = _ensure_jsonschema_environment(tool_root, args.wheelhouse)
            package, version = _jsonschema_runtime(tool_root)
        return {
            "schema": "bbk.schema-validation.v1",
            "status": "BLOCKED",
            "valid": False,
            "draft": "2020-12",
            "error": "The Python jsonschema package is not available.",
            "remediation": "Re-run with --ensure to create an isolated jsonschema 4.25.1 environment, or provide that package in the active interpreter.",
            "managed_environment": str(tool_root),
        }
    schema_path = _resolve_schema_path(args.schema)
    schema_value = read_json(schema_path)
    try:
        package.Draft202012Validator.check_schema(schema_value)
    except Exception as exc:  # jsonschema exposes several validation exception types
        return {
            "schema": "bbk.schema-validation.v1",
            "status": "FAIL",
            "valid": False,
            "draft": "2020-12",
            "validator_version": version,
            "schema_path": str(schema_path),
            "schema_errors": [str(exc)],
            "instances": [],
        }
    try:
        registry, registry_metadata = _build_schema_registry(SCHEMA_DIR, extra_paths=(schema_path,))
        validator = package.Draft202012Validator(schema_value, registry=registry)
    except ImportError:
        registry_metadata = {
            "registry_roots": [str(SCHEMA_DIR.resolve())],
            "registered_schema_ids": [],
            "registered_schema_files": [],
            "registered_resource_count": 0,
        }
        validator = package.Draft202012Validator(schema_value)
    instances: list[dict[str, Any]] = []
    valid = True
    for raw in args.instance:
        path = Path(raw).expanduser().resolve()
        instance = read_json(path)
        try:
            errors = sorted(validator.iter_errors(instance), key=lambda item: list(item.absolute_path))
        except Exception as exc:
            if _reference_error_uri(exc) is not None:
                failure = _schema_reference_failure(
                    exc,
                    schema_path=schema_path,
                    schema_value=schema_value,
                    registry_metadata=registry_metadata,
                )
                failure["instances"] = [{
                    "path": str(path),
                    "sha256": sha256_file(path),
                    "valid": False,
                    "code": "SCHEMA_REFERENCE_UNRESOLVED",
                    "errors": [],
                }]
                return failure
            raise
        rendered = [_schema_error_detail(error) for error in errors]
        if rendered:
            valid = False
        instances.append({
            "path": str(path),
            "sha256": sha256_file(path),
            "valid": not rendered,
            "code": None if not rendered else "SCHEMA_VALIDATION_FAILED",
            "errors": rendered,
        })
    return {
        "schema": "bbk.schema-validation.v1",
        "status": "PASS" if valid else "FAIL",
        "valid": valid,
        "code": None if valid else "SCHEMA_VALIDATION_FAILED",
        "draft": "2020-12",
        "validator": "python-jsonschema",
        "validator_version": version,
        "schema_path": str(schema_path),
        "schema_sha256": sha256_file(schema_path),
        "registry": {
            "roots": registry_metadata.get("registry_roots", []),
            "registered_schema_count": len(registry_metadata.get("registered_schema_ids", [])),
            "registered_resource_count": registry_metadata.get("registered_resource_count", 0),
        },
        "instances": instances,
    }


BEADS_OBJECT_KINDS = {
    "project", "territory", "decision", "question", "capability_increment", "phase", "work_unit"
}
BEADS_KIND_TYPES = {
    "project": "epic",
    "territory": "epic",
    "decision": "task",
    "question": "task",
    "capability_increment": "epic",
    "phase": "epic",
    "work_unit": "task",
}


def _beads_mapping(root: Path) -> tuple[Path, dict[str, Any]]:
    path = root / ".bbk" / "mappings" / "beads.json"
    value = read_json(path)
    if value.get("schema") != "bbk.beads-mapping.v1":
        raise BbkError(f"Unsupported Beads mapping schema in {path}: {value.get('schema')!r}")
    objects = value.get("objects")
    if not isinstance(objects, list):
        raise BbkError(f"Beads mapping objects must be an array: {path}")
    return path, value


def _beads_bound_id(mapping: Mapping[str, Any], bbk_id: str) -> str | None:
    """Return the exact foreign Beads identifier bound to one canonical BBK id."""
    found: str | None = None
    for raw in mapping.get("objects", []):
        if not isinstance(raw, Mapping) or raw.get("bbk_id") != bbk_id:
            continue
        bead_id = raw.get("bead_id")
        if not isinstance(bead_id, str) or not bead_id.strip():
            raise BbkError(f"Beads binding for {bbk_id} does not contain a valid bead_id")
        if found is not None and found != bead_id:
            raise BbkError(f"Duplicate Beads bindings exist for {bbk_id}; reconcile them before projection")
        found = bead_id
    return found


def _beads_workspace(root: Path, mapping: Mapping[str, Any]) -> Path:
    workspace_raw = mapping.get("workspace")
    workspace = root
    if isinstance(workspace_raw, str) and workspace_raw.strip():
        candidate = Path(workspace_raw).expanduser()
        workspace = (root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    if not workspace.is_dir():
        raise BbkError(f"Configured Beads workspace is not a directory: {workspace}")
    return workspace


def _beads_parse_json_output(raw: str) -> Any:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Some bd versions write a short informational line before JSON. Search
        # line boundaries from the end without accepting an arbitrary substring.
        lines = text.splitlines()
        for index in range(len(lines) - 1, -1, -1):
            candidate = "\n".join(lines[index:]).strip()
            if not candidate or candidate[0] not in "[{":
                continue
            with contextlib.suppress(json.JSONDecodeError):
                return json.loads(candidate)
    return None


def _beads_issue_record(value: Any) -> dict[str, Any] | None:
    if isinstance(value, list):
        for item in value:
            found = _beads_issue_record(item)
            if found is not None:
                return found
        return None
    if not isinstance(value, Mapping):
        return None
    if isinstance(value.get("id"), str) and value.get("id"):
        return dict(value)
    for key in ("issue", "data", "result", "created", "updated"):
        found = _beads_issue_record(value.get(key))
        if found is not None:
            return found
    return None


def _beads_command(workspace: Path) -> tuple[list[str] | None, dict[str, Any]]:
    try:
        command, binding = substrate_mise_adapter.managed_tool_command(
            workspace,
            "bd",
            mise_path_value=os.environ.get("BBK_MISE"),
            environment=os.environ,
        )
    except substrate_mise_adapter.MiseAdapterError as exc:
        return None, {
            "status": "BLOCKED",
            "code": exc.code,
            "message": exc.message,
            "execution_mode": "MISE_MANAGED",
        }
    return command, {"status": "CONFIGURED", **binding}


def _require_beads_command(workspace: Path) -> tuple[list[str], dict[str, Any]]:
    command, binding = _beads_command(workspace)
    if command is None:
        raise BbkError(
            "Cannot execute Beads operation through mise: "
            f"{binding.get('code')}: {binding.get('message')}"
        )
    return command, binding


def _beads_environment() -> dict[str, str]:
    return {
        **substrate_mise_adapter.managed_tool_environment(os.environ),
        "BD_NON_INTERACTIVE": "1",
        "BEADS_DISABLE_METRICS": "1",
    }


def _beads_run_json(command_prefix: Sequence[str], argv: Sequence[str], workspace: Path, timeout: float) -> tuple[dict[str, Any], dict[str, Any] | None]:
    executed = run([*command_prefix, *argv], workspace, timeout=timeout, env=_beads_environment())
    parsed = _beads_parse_json_output(str(executed.get("stdout") or ""))
    issue = _beads_issue_record(parsed)
    return executed, issue


def _beads_object_description(item: Mapping[str, Any]) -> str:
    parent = item.get("parent_bbk_id") or "none"
    lines = [
        "BBK coordination projection; canonical state remains under .bbk/.",
        f"bbk_id={item['bbk_id']}",
        f"bbk_kind={item['kind']}",
        f"parent_bbk_id={parent}",
    ]
    profile = item.get("profile")
    if isinstance(profile, str) and profile:
        lines.append(f"profile={profile}")
    return "\n".join(lines)


def _beads_source_digest(item: Mapping[str, Any]) -> str:
    material = {
        "bbk_id": item.get("bbk_id"),
        "kind": item.get("kind"),
        "title": item.get("title"),
        "parent_bbk_id": item.get("parent_bbk_id"),
        "beads_type": item.get("beads_type"),
        "profile": item.get("profile"),
    }
    return sha256_bytes(canonical_bytes(material))


def _beads_parent_from_issue(issue: Mapping[str, Any]) -> str | None:
    for key in ("parent_id", "parentId", "parent", "parent_issue_id", "parentIssueId"):
        value = issue.get(key)
        if isinstance(value, Mapping):
            value = value.get("id")
        if isinstance(value, str) and value.strip():
            return value.strip()
    issue_id = issue.get("id")
    if isinstance(issue_id, str) and "." in issue_id:
        return issue_id.rsplit(".", 1)[0]
    return None


def _beads_issue_projection(issue: Mapping[str, Any]) -> dict[str, Any]:
    issue_type = issue.get("issue_type") or issue.get("issueType") or issue.get("type")
    description = issue.get("description")
    return {
        "id": str(issue.get("id") or "").strip(),
        "title": str(issue.get("title") or "").strip(),
        "description": str(description or "").replace("\r\n", "\n").strip(),
        "beads_type": str(issue_type or "").strip(),
        "parent_bead_id": _beads_parent_from_issue(issue),
    }


def _beads_expected_projection(
    item: Mapping[str, Any],
    *,
    bead_id: str,
    parent_bead_id: str | None,
) -> dict[str, Any]:
    return {
        "id": bead_id,
        "title": str(item.get("title") or "").strip(),
        "description": _beads_object_description(item).replace("\r\n", "\n").strip(),
        "beads_type": str(item.get("beads_type") or "").strip(),
        "parent_bead_id": parent_bead_id,
    }


def _beads_projection_digest(value: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_bytes({
        "id": value.get("id"),
        "title": value.get("title"),
        "description": value.get("description"),
        "beads_type": value.get("beads_type"),
        "parent_bead_id": value.get("parent_bead_id"),
    }))


def _beads_projection_differences(
    expected: Mapping[str, Any],
    observed: Mapping[str, Any],
) -> list[dict[str, Any]]:
    differences: list[dict[str, Any]] = []
    for field in ("id", "title", "description", "beads_type", "parent_bead_id"):
        expected_value = expected.get(field)
        observed_value = observed.get(field)
        if expected_value != observed_value:
            differences.append({"field": field, "expected": expected_value, "observed": observed_value})
    return differences


def _beads_binding_projection(binding: Mapping[str, Any]) -> dict[str, Any] | None:
    bead_id = binding.get("bead_id")
    if not isinstance(bead_id, str) or not bead_id.strip():
        return None
    stored = binding.get("projected_issue")
    if isinstance(stored, Mapping):
        value = dict(stored)
        value["id"] = bead_id
        return value
    required = ("bbk_id", "kind", "title", "beads_type")
    if not all(binding.get(key) is not None for key in required):
        return None
    return _beads_expected_projection(
        binding,
        bead_id=bead_id,
        parent_bead_id=(str(binding.get("parent_bead_id")) if binding.get("parent_bead_id") else None),
    )


def _beads_collect_objects(root: Path, *, work_unit_path: Path | None = None) -> list[dict[str, Any]]:
    if work_unit_path is not None:
        data = read_json(work_unit_path)
        report = validate_work_unit(data)
        if not report.get("valid"):
            raise BbkError(f"Invalid work unit {work_unit_path}: {report.get('errors')}")
        item = report.get("normalized") or data
        profile = None
        binding = item.get("profile_binding")
        if isinstance(binding, Mapping):
            profile = binding.get("profile_id") or binding.get("id")
        return [{
            "bbk_id": item.get("id"),
            "kind": "work_unit",
            "title": item.get("purpose") or item.get("title") or item.get("id"),
            "parent_bbk_id": item.get("phase_id"),
            "beads_type": "task",
            "profile": profile,
        }]

    mapping = read_json(root / ".bbk" / "map.json")
    work = read_json(root / ".bbk" / "work.json")
    config = load_config(root)
    project_id = config["project_id"]
    objects: list[dict[str, Any]] = [{
        "bbk_id": project_id,
        "kind": "project",
        "title": config["title"],
        "parent_bbk_id": None,
        "beads_type": "epic",
    }]
    definitions = [
        ("territories", "territory", "epic"),
        ("decisions", "decision", "task"),
        ("questions", "question", "task"),
        ("capability_increments", "capability_increment", "epic"),
        ("phases", "phase", "epic"),
    ]
    for key, kind, beads_type in definitions:
        for item in mapping.get(key, []):
            if not isinstance(item, Mapping):
                continue
            title = (
                item.get("name") or item.get("title") or item.get("decision")
                or item.get("accepted_decision") or item.get("root_decision") or item.get("id")
            )
            parent = item.get("parent_id") or item.get("territory_id") or item.get("capability_increment_id")
            objects.append({
                "bbk_id": item.get("id"),
                "kind": kind,
                "title": title,
                "parent_bbk_id": parent or project_id,
                "beads_type": beads_type,
            })
    for item in work.get("work_units", []):
        if not isinstance(item, Mapping):
            continue
        profile = None
        binding = item.get("profile_binding")
        if isinstance(binding, Mapping):
            profile = binding.get("profile_id") or binding.get("id")
        objects.append({
            "bbk_id": item.get("id"),
            "kind": "work_unit",
            "title": item.get("purpose") or item.get("title") or item.get("id"),
            "parent_bbk_id": item.get("phase_id") or project_id,
            "beads_type": "task",
            "profile": profile,
        })
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in objects:
        raw_id = item.get("bbk_id")
        if not isinstance(raw_id, str) or not raw_id:
            continue
        bbk_id = validate_id(raw_id, "Beads-projected BBK id")
        if bbk_id in seen:
            raise BbkError(f"Duplicate BBK id in Beads projection source: {bbk_id}")
        seen.add(bbk_id)
        clean = dict(item)
        clean["bbk_id"] = bbk_id
        clean["title"] = str(clean.get("title") or bbk_id).strip()
        if not clean["title"]:
            clean["title"] = bbk_id
        clean["source_sha256"] = _beads_source_digest(clean)
        result.append(clean)
    return result


def _beads_operation_plan(
    objects: Sequence[Mapping[str, Any]],
    mapping: Mapping[str, Any],
    *,
    canonical_ids: set[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    bindings: dict[str, dict[str, Any]] = {}
    duplicates: set[str] = set()
    for raw in mapping.get("objects", []):
        if not isinstance(raw, Mapping) or not isinstance(raw.get("bbk_id"), str):
            continue
        bbk_id = str(raw["bbk_id"])
        if bbk_id in bindings:
            duplicates.add(bbk_id)
        bindings[bbk_id] = dict(raw)
    if duplicates:
        raise BbkError(f"Duplicate Beads foreign bindings require reconciliation: {sorted(duplicates)}")

    source_ids = canonical_ids if canonical_ids is not None else {str(item["bbk_id"]) for item in objects}
    stale = [dict(item) for bbk_id, item in sorted(bindings.items()) if bbk_id not in source_ids]
    operations: list[dict[str, Any]] = []
    for item_raw in objects:
        item = dict(item_raw)
        binding = bindings.get(item["bbk_id"])
        if binding is None:
            operation = "create"
        else:
            bead_id = binding.get("bead_id")
            if not isinstance(bead_id, str) or not bead_id.strip():
                operation = "binding_invalid"
            elif binding.get("kind") != item.get("kind") or binding.get("beads_type") != item.get("beads_type"):
                operation = "type_change_required"
            elif binding.get("parent_bbk_id") != item.get("parent_bbk_id"):
                operation = "reparent_required"
            elif binding.get("source_sha256") == item.get("source_sha256"):
                operation = "inspect"
            else:
                operation = "update"
        operations.append({
            "operation": operation,
            "object": item,
            **({"binding": binding} if binding is not None else {}),
        })
    return operations, stale, bindings


def _beads_execution_record(executed: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "argv": list(executed.get("argv") or []),
        "cwd": str(executed.get("cwd") or ""),
        "returncode": int(executed.get("returncode") or 0),
        "duration_seconds": executed.get("duration_seconds"),
        "timed_out": bool(executed.get("timed_out")),
        "stdout_sha256": sha256_bytes(str(executed.get("stdout") or "").encode("utf-8")),
        "stderr_sha256": sha256_bytes(str(executed.get("stderr") or "").encode("utf-8")),
    }


def _beads_verify_issue(command_prefix: Sequence[str], bead_id: str, workspace: Path, timeout: float) -> dict[str, Any]:
    executed, issue = _beads_run_json(command_prefix, ["show", bead_id, "--json"], workspace, timeout)
    if executed["returncode"] != 0:
        raise BbkError((executed.get("stderr") or executed.get("stdout") or f"bd show {bead_id} failed").strip())
    if issue is None:
        raise BbkError(f"bd show {bead_id} did not return a machine-readable issue record")
    if str(issue.get("id")) != bead_id:
        raise BbkError(f"bd show returned issue {issue.get('id')!r} while verifying {bead_id!r}")
    projection = _beads_issue_projection(issue)
    return {
        "issue": issue,
        "projection": projection,
        "projection_sha256": _beads_projection_digest(projection),
        "execution": _beads_execution_record(executed),
    }


def cmd_beads_handoff_plan(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.handoff).expanduser().resolve()
    root = resolve_root(args.root, required=False)
    if root is None:
        root = project_root(path.parent, required=True)
    assert root is not None
    verification = verify_handoff(path, root=root)
    if not verification["valid"]:
        raise BbkError("Cannot project an invalid handoff into Beads: " + "; ".join(verification["errors"]))
    item = load_handoff_v2_value(path) if path.is_dir() else read_json(path)
    handoff = verification["handoff"]
    mapping_path, mapping = _beads_mapping(root)
    explicit_target = getattr(args, "target_bbk_id", None)
    target_bbk_id = validate_id(explicit_target, "Beads handoff target BBK id") if explicit_target else str(item["work_unit_id"])
    bound_bead_id = _beads_bound_id(mapping, target_bbk_id)
    if explicit_target and not bound_bead_id:
        raise BbkError(
            f"No Beads binding exists for explicit target {target_bbk_id}; project that canonical record before appending execution-state or handoff pointers"
        )
    if args.bead and bound_bead_id and args.bead != bound_bead_id:
        raise BbkError(
            f"Explicit Beads issue {args.bead!r} does not match the binding {bound_bead_id!r} for {target_bbk_id}"
        )
    bead_id = args.bead or bound_bead_id
    if not bead_id:
        raise BbkError(
            f"No Beads binding exists for WorkUnit {item['work_unit_id']}; project the WorkUnit first or pass --bead"
        )
    target_resolution = "MAPPED" if bound_bead_id else "EXPLICIT_FOREIGN"
    subject = item.get("subject") if isinstance(item.get("subject"), Mapping) else {}
    producer = item.get("producer") if isinstance(item.get("producer"), Mapping) else {}
    note = "\n".join([
        f"BBK handoff {item['work_unit_id']} attempt {item['attempt']}: {item['disposition']}",
        f"target={target_bbk_id}",
        f"subject={subject.get('kind')}:{subject.get('id')}",
        f"producer={producer.get('role')}",
        f"handoff={handoff['path']}",
        f"bytes={handoff['bytes']}",
        f"sha256={handoff['sha256']}",
        f"next={item['smallest_next_action']}",
    ])
    if len(note.encode("utf-8")) > 4096:
        raise BbkError("Compact Beads handoff pointer exceeds 4096 UTF-8 bytes")
    workspace = _beads_workspace(root, mapping)
    command_prefix, declared_tool_binding = substrate_mise_adapter.managed_tool_plan_command(
        workspace, "bd", launcher=os.environ.get("BBK_MISE", "mise"),
    )
    argv = [*command_prefix, "comments", "add", bead_id, note]
    value: dict[str, Any] = {
        "schema": "bbk.beads-handoff-plan.v1",
        "status": "PASS",
        "dry_run": not bool(args.apply),
        "bead_id": bead_id,
        "target": {
            "bbk_id": target_bbk_id,
            "bead_id": bead_id,
            "resolution": target_resolution,
            "subject_kind": subject.get("kind"),
            "subject_id": subject.get("id"),
            "producer_role": producer.get("role"),
        },
        "handoff": handoff,
        "note": note,
        "argv": argv,
        "capability": declared_tool_binding,
        "warnings": [
            "The Beads comment is an append-only coordination pointer; the verified BBK handoff file remains authoritative.",
            "Do not paste large artifacts, protected evidence, credentials, or secrets into the Beads comment.",
            "A Beads update does not prove validation, acceptance, completion, or release.",
        ],
    }
    if args.apply:
        if not mapping.get("enabled") or not mapping.get("write_enabled"):
            raise BbkError(
                "Beads handoff writes require .bbk/mappings/beads.json with enabled=true and write_enabled=true"
            )
        command_prefix, tool_binding = _require_beads_command(workspace)
        value["capability"] = tool_binding
        executed = run(
            [*command_prefix, "comments", "add", bead_id, note],
            workspace,
            timeout=args.timeout,
            env=_beads_environment(),
        )
        value["execution"] = _beads_execution_record(executed)
        if executed["returncode"] != 0:
            value["status"] = "ERROR"
            value["error"] = (executed.get("stderr") or executed.get("stdout") or "bd comments add failed").strip()
        else:
            value["verification"] = _beads_verify_issue(command_prefix, bead_id, workspace, args.timeout)
            value["applied"] = True
            value["dry_run"] = False
    if args.output:
        output = Path(args.output).expanduser().resolve()
        write_json(output, value)
        value["output"] = str(output)
    return value


def cmd_beads_plan(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_root(args.root, required=False)
    work_unit_path = Path(args.work_unit).expanduser().resolve() if args.work_unit else None
    if root is None and work_unit_path is not None:
        root = project_root(work_unit_path.parent, required=False)
    if root is None and work_unit_path is None:
        raise BbkError("Project-level Beads planning requires an initialized BBK project or --work-unit")

    if root is None:
        mapping = {
            "schema": "bbk.beads-mapping.v1", "enabled": False, "write_enabled": False,
            "workspace": None, "auto_initialize": False, "objects": [],
        }
        mapping_path = None
        workspace = work_unit_path.parent if work_unit_path else Path.cwd()
    else:
        mapping_path, mapping = _beads_mapping(root)
        workspace = _beads_workspace(root, mapping)

    canonical_objects = _beads_collect_objects(root, work_unit_path=work_unit_path) if root is not None else _beads_collect_objects(workspace, work_unit_path=work_unit_path)
    objects = list(canonical_objects)
    selected_kinds = set(args.kind or [])
    selected_ids = set(args.id or [])
    unknown_kinds = sorted(selected_kinds - BEADS_OBJECT_KINDS)
    if unknown_kinds:
        raise BbkError(f"Unknown Beads projection kinds: {unknown_kinds}")
    if selected_kinds:
        objects = [item for item in objects if item["kind"] in selected_kinds]
    if selected_ids:
        objects = [item for item in objects if item["bbk_id"] in selected_ids]
        found = {item["bbk_id"] for item in objects}
        missing = sorted(selected_ids - found)
        if missing:
            raise BbkError(f"Requested Beads projection IDs were not found in canonical BBK state: {missing}")
    operations, stale, bindings = _beads_operation_plan(
        objects,
        mapping,
        canonical_ids={str(item["bbk_id"]) for item in canonical_objects},
    )
    command_prefix, tool_binding = _beads_command(workspace)
    initialized = (workspace / ".beads").exists()
    result: dict[str, Any] = {
        "schema": "bbk.beads-plan.v2",
        "status": "PASS",
        "dry_run": not bool(args.apply),
        "enabled": bool(mapping.get("enabled", False)),
        "write_enabled": bool(mapping.get("write_enabled", False)),
        "auto_initialize": bool(mapping.get("auto_initialize", False)),
        "workspace": str(workspace),
        "mapping_path": str(mapping_path) if mapping_path is not None else None,
        "capability": {
            "bd": tool_binding.get("tool_spec"),
            "status": "READY" if command_prefix and initialized else ("NOT_INITIALIZED" if command_prefix else "MISE_TOOL_UNAVAILABLE"),
            "initialized": initialized,
            "tool_binding": tool_binding,
        },
        "selected_kinds": sorted(selected_kinds) if selected_kinds else sorted({item["kind"] for item in objects}),
        "selected_ids": sorted(selected_ids),
        "operations": operations,
        "stale_bindings": stale,
        "warnings": [
            "BBK IDs and canonical .bbk records remain authoritative.",
            "Closing, claiming, or changing a Beads issue does not prove a BBK decision, validation, finding disposition, outcome, or release.",
            "Stale or directly edited bindings require review; BBK never uses last-write-wins reconciliation.",
        ],
    }
    if command_prefix is None:
        result["warnings"].append(
            "Beads coordination is enabled but the mise-managed bd tool is unavailable; canonical BBK work may continue."
        )
    elif not initialized:
        result["warnings"].append("The configured Beads workspace is not initialized; apply will initialize it only when auto_initialize=true or --initialize is supplied.")

    if args.apply:
        if root is None or mapping_path is None:
            raise BbkError("Applying Beads projection requires an initialized BBK project")
        if not mapping.get("enabled") or not mapping.get("write_enabled"):
            raise BbkError("Beads writes require enabled=true and write_enabled=true in .bbk/mappings/beads.json")
        if command_prefix is None:
            command_prefix, tool_binding = _require_beads_command(workspace)
            result["capability"].update({
                "bd": tool_binding.get("tool_spec"),
                "status": "NOT_INITIALIZED" if not initialized else "READY",
                "tool_binding": tool_binding,
            })
        invalid_actions = sorted(
            (item["operation"], item["object"]["bbk_id"])
            for item in operations
            if item["operation"] in {"binding_invalid", "type_change_required", "reparent_required"}
        )
        if invalid_actions:
            raise BbkError(
                "Beads bindings require explicit reconciliation before apply: "
                + ", ".join(f"{bbk_id} ({action})" for action, bbk_id in invalid_actions)
            )

        executions: list[dict[str, Any]] = []
        if not initialized:
            if bindings:
                raise BbkError("Beads bindings exist but the configured workspace is not initialized; reconcile the workspace before apply")
            if not (args.initialize or mapping.get("auto_initialize")):
                raise BbkError("Beads workspace is not initialized; rerun with --initialize or enable auto_initialize")
            assert command_prefix is not None
            init_exec = run(
                [*command_prefix, "init", "--quiet", "--skip-agents"],
                workspace,
                timeout=args.timeout,
                env=_beads_environment(),
            )
            executions.append({"operation": "initialize", "execution": _beads_execution_record(init_exec)})
            result["initialization"] = executions[-1]
            if init_exec["returncode"] != 0:
                raise BbkError((init_exec.get("stderr") or init_exec.get("stdout") or "bd init failed").strip())
            initialized = True
            result["capability"]["initialized"] = True
            result["capability"]["status"] = "READY"

        current_bindings = {key: dict(value) for key, value in bindings.items()}
        preflight: dict[str, dict[str, Any]] = {}
        drift: list[dict[str, Any]] = []
        for operation in operations:
            if operation["operation"] == "create":
                continue
            item = operation["object"]
            binding = current_bindings[item["bbk_id"]]
            bead_id = str(binding["bead_id"])
            verification = _beads_verify_issue(command_prefix, bead_id, workspace, args.timeout)
            preflight[item["bbk_id"]] = verification
            expected_previous = _beads_binding_projection(binding)
            if expected_previous is None:
                drift.append({
                    "bbk_id": item["bbk_id"],
                    "bead_id": bead_id,
                    "reason": "binding_missing_projected_issue",
                    "observed": verification["projection"],
                    "verification": verification,
                })
                continue
            differences = _beads_projection_differences(expected_previous, verification["projection"])
            expected_digest = binding.get("projected_issue_sha256") or _beads_projection_digest(expected_previous)
            if differences or verification["projection_sha256"] != expected_digest:
                drift.append({
                    "bbk_id": item["bbk_id"],
                    "bead_id": bead_id,
                    "reason": "foreign_issue_drift",
                    "expected": expected_previous,
                    "expected_sha256": expected_digest,
                    "observed": verification["projection"],
                    "observed_sha256": verification["projection_sha256"],
                    "differences": differences,
                    "verification": verification,
                })
        if drift:
            result.update({
                "status": "DRIFT",
                "dry_run": False,
                "applied": False,
                "drift": drift,
                "message": "Direct or unbound Beads changes were observed. BBK did not overwrite them; reconcile the foreign issues or bindings explicitly.",
            })
        else:
            applied: list[dict[str, Any]] = []
            for operation in operations:
                action = operation["operation"]
                item = operation["object"]
                parent_bead = None
                parent_bbk = item.get("parent_bbk_id")
                if parent_bbk:
                    parent_binding = current_bindings.get(str(parent_bbk))
                    if parent_binding is None or not isinstance(parent_binding.get("bead_id"), str):
                        raise BbkError(
                            f"Cannot project {item['bbk_id']}: parent BBK id {parent_bbk} has no verified Beads binding. "
                            "Include the parent kind in the plan or reconcile its binding first."
                        )
                    parent_bead = str(parent_binding["bead_id"])
                description = _beads_object_description(item)
                if action == "create":
                    argv = ["create", item["title"], "-t", item["beads_type"], "--description", description]
                    if parent_bead:
                        argv.extend(["--parent", parent_bead])
                    argv.append("--json")
                    executed, issue = _beads_run_json(command_prefix, argv, workspace, args.timeout)
                    if executed["returncode"] != 0 or issue is None or not isinstance(issue.get("id"), str):
                        raise BbkError((executed.get("stderr") or executed.get("stdout") or f"bd create failed for {item['bbk_id']}").strip())
                    bead_id = str(issue["id"])
                    execution_record = _beads_execution_record(executed)
                    verification = _beads_verify_issue(command_prefix, bead_id, workspace, args.timeout)
                else:
                    binding = current_bindings[item["bbk_id"]]
                    bead_id = str(binding["bead_id"])
                    if action == "update":
                        argv = ["update", bead_id, "--title", item["title"], "--description", description, "--json"]
                        executed, _issue = _beads_run_json(command_prefix, argv, workspace, args.timeout)
                        if executed["returncode"] != 0:
                            raise BbkError((executed.get("stderr") or executed.get("stdout") or f"bd update failed for {bead_id}").strip())
                        execution_record = _beads_execution_record(executed)
                        verification = _beads_verify_issue(command_prefix, bead_id, workspace, args.timeout)
                    else:
                        verification = preflight[item["bbk_id"]]
                        execution_record = verification["execution"]
                expected_projection = _beads_expected_projection(
                    item,
                    bead_id=bead_id,
                    parent_bead_id=parent_bead,
                )
                differences = _beads_projection_differences(expected_projection, verification["projection"])
                if differences:
                    raise BbkError(
                        f"Beads verification mismatch after {action} for {item['bbk_id']}: "
                        + json.dumps(differences, ensure_ascii=False, sort_keys=True)
                    )
                projected_at = utc_now()
                record = {
                    "bbk_id": item["bbk_id"],
                    "kind": item["kind"],
                    "bead_id": bead_id,
                    "beads_type": item["beads_type"],
                    "title": item["title"],
                    "profile": item.get("profile"),
                    "parent_bbk_id": parent_bbk,
                    "parent_bead_id": parent_bead,
                    "source_sha256": item["source_sha256"],
                    "projected_issue": expected_projection,
                    "projected_issue_sha256": _beads_projection_digest(expected_projection),
                    "projected_at": projected_at,
                    "verified_at": projected_at,
                }
                current_bindings[item["bbk_id"]] = record
                mapping["objects"] = [current_bindings[key] for key in sorted(current_bindings)]
                mapping["last_projected_at"] = projected_at
                write_json(mapping_path, mapping)
                applied.append({
                    "operation": action,
                    "bbk_id": item["bbk_id"],
                    "bead_id": bead_id,
                    "execution": execution_record,
                    "verification": verification,
                })
            result["applied"] = True
            result["dry_run"] = False
            result["applied_operations"] = applied
            result["mapping_sha256"] = sha256_file(mapping_path)

    if args.output:
        output = Path(args.output).expanduser().resolve()
        write_json(output, result)
        result["output"] = str(output)
    return result

def cmd_status(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_root(args.root, required=False)
    projection_manifest = PACKAGE_ROOT / "projections" / "manifest.json"
    projection = read_json(projection_manifest) if projection_manifest.is_file() else {}
    package_view = {
        "version": VERSION,
        "package_root": str(PACKAGE_ROOT),
        "roles": projection.get("role_count") or projection.get("roleCount"),
        "targets": projection.get("targets", []),
        "projections": projection.get("projection_count") or projection.get("projectionCount"),
        "schemas": len(list(SCHEMA_DIR.glob("*.json"))) if SCHEMA_DIR.is_dir() else 0,
        "features": {
            "solution_outcome_fit": True,
            "implementation_structure": True,
            "execution_slices": True,
            "manifest_comparison": True,
            "candidate_staleness": True,
            "executable_gates": True,
            "workspace_leases": True,
            "language_profiles": True,
            "recursive_wayfinding": True,
            "durable_question_branches": True,
            "durable_handoffs": True,
            "beads_coordination_projection": True,
            "draft_2020_12_schema_adapter": True,
        },
    }
    disclaimer = "BBK status is not official Blueprint lifecycle or readiness state."
    if root is None:
        return {
            "schema": "bbk.status.v1", "status": "PASS", "command_status": "PASS",
            "project_state": "NO_PROJECT_SELECTED", "artifact_integrity": "NOT_ASSESSED",
            "semantic_readiness": "NOT_ASSESSED", "execution_authorization": "NOT_ESTABLISHED",
            "bbk_version": VERSION, "package": package_view, "project": None,
            "disclaimer": disclaimer,
        }
    if not root.exists() or not root.is_dir():
        raise BbkError(f"Project root does not exist or is not a directory: {root}")
    config_path = root / ".bbk" / "config.json"
    zero_counts = {"fit": 0, "structures": 0, "slices": 0, "work_units": 0}
    if not config_path.is_file():
        return {
            "schema": "bbk.status.v1", "status": "UNINITIALIZED", "command_status": "PASS",
            "project_state": "UNINITIALIZED", "artifact_integrity": "NOT_APPLICABLE",
            "semantic_readiness": "NOT_ASSESSED", "execution_authorization": "NOT_AUTHORIZED",
            "bbk_version": VERSION, "package": package_view,
            "project": {"root": str(root), "initialized": False},
            "planning_artifacts": zero_counts,
            "examples_available": {**zero_counts, "questions": 0, "handoffs": 0, "reviews": 0, "total": 0},
            "next_action": {"command": "bbk init", "reason": "No .bbk/config.json exists at the requested root"},
            "disclaimer": disclaimer,
        }
    config = load_config(root)
    _, registry = workspace_registry(root)
    candidates = []
    for path in sorted((root / ".bbk" / "candidates").glob("*/candidate.json")):
        with contextlib.suppress(BbkError):
            meta = read_json(path)
            candidates.append({"candidate_id": meta["candidate_id"], "digest": meta["manifest_content_sha256"], "state": candidate_state(root, meta["candidate_id"])})
    receipts = sorted((root / ".bbk" / "receipts" / "gates").glob("*/*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    recent = []
    for path in receipts[:10]:
        with contextlib.suppress(BbkError):
            item = read_json(path)
            recent.append({"gate_id": item.get("gate_id"), "status": item.get("status"), "candidate_id": item.get("candidate_id"), "completed_at": item.get("completed_at"), "path": str(path)})
    artifact_dirs = {
        "fit": root / ".bbk" / "fit",
        "structures": root / ".bbk" / "structures",
        "slices": root / ".bbk" / "slices",
        "work_units": root / ".bbk" / "work-units",
    }
    artifact_counts = {name: len(operational_json_paths(directory)) for name, directory in artifact_dirs.items()}
    example_counts = {name: len(example_paths(directory)) for name, directory in artifact_dirs.items()}
    example_counts.update({
        "state_effects": len(example_paths(root / ".bbk" / "state-effects")),
        "traces": len(example_paths(root / ".bbk" / "traces")),
        "questions": len(example_paths(root / ".bbk" / "questions")),
        "handoffs": len(example_paths(root / ".bbk" / "handoffs", recursive=True)),
        "reviews": len(example_paths(root / ".bbk" / "reviews", recursive=True)),
    })
    isolated_examples = example_paths(root / ".bbk" / "examples", recursive=True)
    isolated_category_map = {
        "fit": "fit", "structures": "structures", "slices": "slices", "work-units": "work_units",
        "state-effects": "state_effects", "traces": "traces", "questions": "questions",
        "handoffs": "handoffs", "reviews": "reviews",
    }
    for path in isolated_examples:
        with contextlib.suppress(ValueError, IndexError):
            category = path.relative_to(root / ".bbk" / "examples").parts[0]
            key = isolated_category_map.get(category)
            if key:
                example_counts[key] = example_counts.get(key, 0) + 1
    example_counts["total"] = sum(example_counts.values())
    beads_path, beads_mapping = _beads_mapping(root)
    beads_workspace = _beads_workspace(root, beads_mapping)
    beads_command, beads_tool_binding = _beads_command(beads_workspace)
    beads_view = {
        "enabled": bool(beads_mapping.get("enabled")),
        "write_enabled": bool(beads_mapping.get("write_enabled")),
        "auto_initialize": bool(beads_mapping.get("auto_initialize")),
        "mapping_path": str(beads_path),
        "workspace": str(beads_workspace),
        "binding_count": len(beads_mapping.get("objects", [])),
        "bd": beads_tool_binding.get("tool_spec"),
        "tool_binding": beads_tool_binding,
        "initialized": (beads_workspace / ".beads").exists(),
    }
    return {
        "schema": "bbk.status.v1", "status": "PASS", "command_status": "PASS",
        "project_state": "INITIALIZED", "artifact_integrity": "OBSERVED",
        "semantic_readiness": "NOT_ASSESSED", "execution_authorization": "NOT_ESTABLISHED",
        "bbk_version": VERSION,
        "package": package_view,
        "project": {"id": config["project_id"], "title": config["title"], "root": str(root), "initialized": True},
        "git": git_metadata(root),
        "active_workspaces": [{**item, "inspection": workspace_inspection(item)} for item in registry.get("workspaces", []) if item.get("state") == "ACTIVE"],
        "candidates": candidates,
        "planning_artifacts": artifact_counts,
        "examples_available": example_counts,
        "beads": beads_view,
        "recent_gate_receipts": recent,
        "disclaimer": disclaimer,
    }


def cmd_doctor(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_root(args.root, required=False)
    package_path = PACKAGE_ROOT
    checks: list[dict[str, Any]] = []
    def add(name: str, status: str, detail: Any) -> None:
        checks.append({"name": name, "status": status, "detail": detail})
    add("python", "PASS" if sys.version_info >= (3, 11) else "FAIL", sys.version.split()[0])
    jsonschema_package, jsonschema_version = _jsonschema_runtime()
    managed_schema_python = _venv_python(_schema_tool_root(root, None))
    schema_available = jsonschema_package is not None or managed_schema_python.is_file()
    add(
        "draft-2020-12-schema-validator",
        "PASS" if schema_available else "BLOCKED",
        {
            "current_interpreter": jsonschema_version,
            "managed_python": str(managed_schema_python) if managed_schema_python.is_file() else None,
            "remediation": None if schema_available else "run bbk schema validate --ensure --schema <schema> --instance <instance>",
        },
    )
    for command, label in [("git", "git"), ("codex", "codex-runtime"), ("omp", "omp-runtime"), ("claude", "claude-code-runtime")]:
        found = shutil.which(command)
        add(label, "PASS" if found else ("BLOCKED" if command == "git" else "NOT_INSTALLED"), found or "not found")
    generator = package_path / "tools" / "generate_agents.py"
    if generator.exists():
        result = run([sys.executable, str(generator), "--check"], package_path, timeout=60)
        add("agent-projections", "PASS" if result["returncode"] == 0 else "FAIL", (result["stdout"] + result["stderr"]).strip())
    for name, validator, relative in [
        ("solution-outcome-fit", validate_solution_outcome_fit, "fixtures/fit/confirmed-fit.json"),
        ("implementation-structure", validate_structure, "fixtures/structure/software-contract.json"),
        ("execution-slice", validate_slice, "fixtures/slices/software-slice-1.json"),
    ]:
        fixture = package_path / relative
        if fixture.is_file():
            report = validator(read_json(fixture))
            add(f"contract:{name}", "PASS" if report.get("valid") else "FAIL", report.get("errors") or "fixture valid")
    if root:
        try:
            config = load_config(root)
            add("project-config", "PASS", {"root": str(root), "project_id": config["project_id"]})
            for name in ["map.json", "interfaces.json", "work.json", "assurance.json", "gates.json", "profile-lock.json", "mappings/beads.json"]:
                read_json(root / ".bbk" / name)
                add(f"project-file:{name}", "PASS", "valid JSON")
            _beads_path, beads_mapping = _beads_mapping(root)
            beads_workspace = _beads_workspace(root, beads_mapping)
            beads_command, beads_tool_binding = _beads_command(beads_workspace)
            if not beads_mapping.get("enabled"):
                beads_status = "DISABLED"
            elif beads_command is None:
                beads_status = "MISE_TOOL_UNAVAILABLE"
            elif not (beads_workspace / ".beads").exists():
                beads_status = "NOT_INITIALIZED"
            else:
                beads_status = "PASS"
            add("beads-coordination", beads_status, {
                "enabled": bool(beads_mapping.get("enabled")),
                "write_enabled": bool(beads_mapping.get("write_enabled")),
                "auto_initialize": bool(beads_mapping.get("auto_initialize")),
                "workspace": str(beads_workspace),
                "bd": beads_tool_binding.get("tool_spec"),
                "tool_binding": beads_tool_binding,
                "binding_count": len(beads_mapping.get("objects", [])),
            })
        except BbkError as exc:
            add("project-config", "FAIL", str(exc))
    else:
        add("project-config", "NOT_FOUND", "run from a BBK project or pass --root")
    blocking_statuses = {"FAIL", "BLOCKED", "ERROR", "MISE_TOOL_UNAVAILABLE"}
    return {
        "schema": "bbk.doctor.v1",
        "bbk_version": VERSION,
        "status": "FAIL" if any(item["status"] in blocking_statuses for item in checks) else "PASS",
        "checks": checks,
    }


def human(value: Any) -> str:
    if not isinstance(value, dict):
        return json.dumps(value, indent=2, ensure_ascii=False)
    if value.get("schema") == "bbk.render-result.v1":
        return str(value.get("content", ""))
    if value.get("schema") == "bbk.status.v1" and value.get("project") is None:
        package = value.get("package", {})
        return (
            f"BBK {value.get('bbk_version')}\n"
            f"Package: {package.get('package_root')}\n"
            f"Roles: {package.get('roles')}\n"
            f"Projections: {package.get('projections')}\n"
            f"Features: {', '.join(key for key, enabled in package.get('features', {}).items() if enabled)}"
        )
    if value.get("schema") == "bbk.gate-run.v1":
        lines = [f"Gate phase {value['phase']}: {value['status']}"]
        lines += [f"[{item['status']}] {item['gate_id']} ({'reused' if item.get('reused') else 'ran'})" for item in value["results"]]
        if value.get("attestation"):
            lines.append(f"Attestation: {value['attestation']['status']}")
        return "\n".join(lines)
    if value.get("schema") == "bbk.manifest-comparison.v1":
        lines = [f"Manifest equal: {value['equal']}", f"Summary: {value['summary']}", f"Git identity changed: {value['git_identity_changed']}"]
        lines += [f"- {item['kind']}: {item['path']}" for item in value["changes"][:100]]
        return "\n".join(lines)
    if value.get("schema") == "bbk.profile-list.v1":
        lines = [f"Profiles: {len(value['profiles'])}"]
        lines += [f"- {item.get('id') or '<invalid>'} {item.get('version') or ''} [{item.get('package_verification', {}).get('status')}/{item.get('compatibility', {}).get('status')}] {item.get('root')}" for item in value["profiles"]]
        return "\n".join(lines)
    if value.get("schema") == "bbk.profile-inspection.v1":
        return f"Profile {value.get('id')} {value.get('version')}\nMaturity: {value.get('maturity')}\nVerification: {value.get('package_verification', {}).get('status')}\nRoot: {value.get('root')}"
    if value.get("schema") in {"bbk.profile-resolution-wrapper.v1", "bbk.profile-resolution-wrapper.v2", "bbk.profile-resolution-wrapper.v3"}:
        resolution = value.get("resolution", {})
        selected = resolution.get("selected_components", []) if isinstance(resolution, dict) else []
        dispatch = value.get("profile_dispatch", {})
        return f"Profile resolution: {value.get('profile', {}).get('id')}\nSelected components: {len(selected)}\nCapability operations: {len(dispatch.get('operations', []))}\nEffective digest: {value.get('effective_sha256') or resolution.get('effective_sha256')}\nLock: {value.get('lock_path', 'not written')}"
    if value.get("schema") == "bbk.profile-dispatch-result.v1":
        return f"Profile dispatch: {value.get('operation')}\nStatus: {value.get('status')}\nRequest digest: {value.get('requestDigest')}"
    if value.get("schema") == "bbk.question-branch-list.v1":
        lines = [f"Question branches: {value.get('count', 0)}"]
        lines += [
            f"- {item.get('id')}: {item.get('status')} / {item.get('root_disposition')} — {item.get('root_decision')}"
            for item in value.get("questions", [])
        ]
        return "\n".join(lines)
    if value.get("schema") in {"bbk.handoff-list.v1", "bbk.handoff-list.v2"}:
        lines = [f"Handoffs: {value.get('count', 0)}"]
        lines += [
            f"- {item.get('work_unit_id')} attempt {item.get('attempt')}: {item.get('disposition')} "
            f"[{('valid' if item.get('valid') else 'invalid')}] {item.get('path')} sha256={item.get('sha256')}"
            for item in value.get("handoffs", [])
        ]
        return "\n".join(lines)
    if value.get("schema") == "bbk.doctor.v1":
        return "\n".join([f"BBK doctor: {value['status']}", *[f"[{item['status']}] {item['name']}: {item['detail']}" for item in value["checks"]]])
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)



def _read_object_argument(path: str, label: str) -> dict[str, Any]:
    value = read_json(Path(path).expanduser().resolve())
    if not isinstance(value, dict):
        raise BbkError(f"{label} must contain a JSON object")
    return value


def _write_optional_output(value: dict[str, Any], output: str | None, force: bool = False) -> dict[str, Any]:
    if output:
        path = Path(output).expanduser().resolve()
        if path.exists() and not force:
            raise BbkError(f"Output already exists: {path}; use --force to replace it")
        write_json(path, value)
        value = dict(value)
        value["output"] = path.as_posix()
    return value


def cmd_result_finalize(args: argparse.Namespace) -> dict[str, Any]:
    try:
        return finalize_atomic_json(
            Path(args.input).expanduser(), Path(args.output).expanduser(),
            subject_kind="ROLE_RETURN", schema=args.schema,
            references=[Path(item).expanduser() for item in (args.reference or [])],
            generated_at=args.generated_at, replace=args.force, root=PACKAGE_ROOT,
        )
    except FinalizationError as exc:
        raise BbkError(str(exc), diagnostic={"code": exc.code, "message": exc.message, "command": "result finalize"}) from exc


def cmd_manifest_finalize_opt(args: argparse.Namespace) -> dict[str, Any]:
    try:
        return finalize_atomic_json(
            Path(args.input).expanduser(), Path(args.output).expanduser(),
            subject_kind="MANIFEST", schema=args.schema,
            references=[Path(item).expanduser() for item in (args.reference or [])],
            generated_at=args.generated_at, replace=args.force, root=PACKAGE_ROOT,
        )
    except FinalizationError as exc:
        raise BbkError(str(exc), diagnostic={"code": exc.code, "message": exc.message, "command": "manifest finalize"}) from exc


def cmd_planning_readiness(args: argparse.Namespace) -> dict[str, Any]:
    roadmap = _read_object_argument(args.roadmap, "roadmap")
    coverage = _read_object_argument(args.coverage, "coverage")
    frontier = _read_object_argument(args.frontier, "frontier") if args.frontier else None
    deferred = []
    for path in args.deferred or []:
        value = read_json(Path(path).expanduser().resolve())
        if isinstance(value, list): deferred.extend(item for item in value if isinstance(item, dict))
        elif isinstance(value, dict): deferred.append(value)
        else: raise BbkError("--deferred must contain an object or object array")
    try:
        value = build_planning_readiness(
            roadmap=roadmap, frontier=frontier, coverage=coverage,
            planning_mode=args.planning_mode, architecture_mode=args.architecture_mode,
            deferred_refinements=deferred, fully_compiled=args.fully_compiled,
            full_compilation_trigger=args.full_compilation_trigger,
        )
    except PlanningOptimizationError as exc:
        raise BbkError(str(exc), diagnostic={"code":exc.code,"message":exc.message,"command":"plan readiness"}) from exc
    return _write_optional_output(value, args.output, args.force)


def cmd_plan_migrate_readiness(args: argparse.Namespace) -> dict[str, Any]:
    legacy = _read_object_argument(args.legacy, "legacy planning artifact")
    roadmap = _read_object_argument(args.roadmap, "roadmap")
    frontier = _read_object_argument(args.frontier, "frontier")
    coverage = _read_object_argument(args.coverage, "coverage")
    try:
        value = migrate_legacy_planning_readiness(
            legacy, roadmap=roadmap, frontier=frontier, coverage=coverage,
            authority_ref=args.authority, generated_at=args.generated_at,
        )
    except PlanningOptimizationError as exc:
        raise BbkError(str(exc), diagnostic={"code": exc.code, "message": exc.message, "command": "plan migrate-readiness"}) from exc
    return _write_optional_output(value, args.output, args.force)


def cmd_plan_transact_opt(args: argparse.Namespace) -> dict[str, Any]:
    events=[_read_object_argument(path,"event") for path in args.event]
    outputs={}
    for name in ("roadmap","frontier","coverage","role_return"):
        raw=getattr(args,f"{name}_out",None)
        if raw: outputs[name.replace('_','-')]=Path(raw).expanduser().resolve()
    try:
        return transact_plan(Path(args.state_root).expanduser(), events, authority_ref=args.authority,
                             projection_outputs=outputs, expected_head=args.expected_head,
                             transaction_id=args.transaction_id, created_at=args.generated_at)
    except PlanningOptimizationError as exc:
        raise BbkError(str(exc), diagnostic={"code":exc.code,"message":exc.message,"command":"plan transact","retryable":exc.retryable}) from exc


def cmd_worker_contract_generate(args: argparse.Namespace) -> dict[str, Any]:
    try:
        value=generate_worker_contract(
            _read_object_argument(args.work_unit,"work unit"),
            _read_object_argument(args.authority,"authority"),
            _read_object_argument(args.workspace_receipt,"workspace receipt"),
            _read_object_argument(args.profile_constraints,"profile constraints"),
            return_contract=args.return_contract,
        )
    except PlanningOptimizationError as exc:
        raise BbkError(str(exc), diagnostic={"code":exc.code,"message":exc.message,"command":"worker-contract generate"}) from exc
    return _write_optional_output(value,args.output,args.force)


def cmd_assertion_contract_generate(args: argparse.Namespace) -> dict[str, Any]:
    try:
        value=generate_assertion_contract(
            _read_object_argument(args.acceptance_criterion,"acceptance criterion"),
            _read_object_argument(args.profile_template,"profile template"),
            candidate_stage=args.candidate_stage,
        )
    except PlanningOptimizationError as exc:
        raise BbkError(str(exc), diagnostic={"code":exc.code,"message":exc.message,"command":"assertion-contract generate"}) from exc
    return _write_optional_output(value,args.output,args.force)


def cmd_command_replay_evaluate(args: argparse.Namespace) -> dict[str, Any]:
    value=_read_object_argument(args.attempt,"command attempt")
    try:
        result=evaluate_command_replay(value,candidate_frozen=args.candidate_frozen)
        if args.emit_replay and result.get("eligible"):
            result["replay_attempt"]=build_replay_attempt(value,candidate_frozen=args.candidate_frozen)
    except ReplayError as exc:
        raise BbkError(str(exc), diagnostic={"code":exc.code,"message":exc.message,"command":"command replay-evaluate"}) from exc
    return _write_optional_output(result,args.output,args.force)


def cmd_command_capture_preflight(args: argparse.Namespace) -> dict[str, Any]:
    try:
        text=Path(args.script).expanduser().read_text(encoding='utf-8-sig')
        result=powershell_capture_preflight(text,Path(args.receipt_dir).expanduser().resolve())
    except (OSError,UnicodeError) as exc:
        raise BbkError(f"Cannot inspect capture wrapper: {exc}") from exc
    return _write_optional_output(result,args.output,args.force)


def cmd_profile_admit(args: argparse.Namespace) -> dict[str, Any]:
    try:
        value=resolve_effective_profile(
            _read_object_argument(args.constraints,"profile constraints"),
            _read_object_argument(args.effective_profile,"effective profile"),
            _read_object_argument(args.environment,"environment identity"),
            registry_revision=args.registry_revision, selector=args.selector,
            exact_digest_required=args.exact_digest_required,
            exact_digest_reason=args.exact_digest_reason, observed_at=args.observed_at,
        )
    except RuntimeIdentityError as exc:
        raise BbkError(str(exc), diagnostic={"code":exc.code,"message":exc.message,"command":"profile admit"}) from exc
    return _write_optional_output(value,args.output,args.force)


def cmd_project_coverage_project(args: argparse.Namespace) -> dict[str, Any]:
    value=_read_object_argument(args.coverage,"project coverage")
    try:
        validate_project_coverage(value); result=coverage_return_projection(value)
    except PlanningOptimizationError as exc:
        raise BbkError(str(exc), diagnostic={"code":exc.code,"message":exc.message,"command":"coverage project"}) from exc
    return _write_optional_output(result,args.output,args.force)


def cmd_workspace_admit(args: argparse.Namespace) -> dict[str, Any]:
    try:
        value=issue_workspace_receipt(
            repository_ref=args.repository_ref, baseline_ref=args.baseline_ref,
            protected_tree_state=args.protected_tree_state,
            known_unrelated_dirt=args.known_unrelated_dirt or [], owned_roots=args.owned_root,
            mutation_owner=args.mutation_owner, serialization_state=args.serialization_state,
            issued_at=args.issued_at,
        )
    except PlanningOptimizationError as exc:
        raise BbkError(str(exc), diagnostic={"code":exc.code,"message":exc.message,"command":"workspace admit"}) from exc
    return _write_optional_output(value,args.output,args.force)


def cmd_child_event_emit(args: argparse.Namespace) -> dict[str, Any]:
    detail=_read_object_argument(args.detail,"event detail") if args.detail else {}
    try: value=build_child_event(child_ref=args.child_ref,state=args.state,detail=detail,observed_at=args.observed_at)
    except PlanningOptimizationError as exc: raise BbkError(str(exc),diagnostic={"code":exc.code,"message":exc.message,"command":"child-event emit"}) from exc
    return _write_optional_output(value,args.output,args.force)


def parser() -> argparse.ArgumentParser:
    p = BbkArgumentParser(prog="bbk", description=__doc__)
    p.add_argument("--version", action="version", version=f"bbk {VERSION}")
    p.add_argument("--json", action="store_true")
    sub = p.add_subparsers(parser_class=BbkArgumentParser, dest="command", required=True)
    from identity_graph import IDENTITY_KINDS

    result = sub.add_parser(
        "result", help="atomically finalize durable role results and emit identity receipts",
        description="Workspace implementation effect. Canonicalizes and validates JSON, atomically publishes the result and sidecar identity receipt, invalidates on subject/finalizer/reference digest changes, and is not replay-legal. Legacy return readers remain supported.",
    ).add_subparsers(parser_class=BbkArgumentParser, dest="result_command", required=True)
    x = result.add_parser(
        "finalize", help="canonicalize, validate, and atomically publish one JSON role result",
        description="Effect: WORKSPACE_IMPLEMENTATION. Atomic: yes, with prior-pair rollback. Validates optional Draft 2020-12 schema and safe references. Emits <output>.identity.json. Replay legal: no. Compatibility: reads UTF-8/BOM and writes canonical UTF-8 LF.",
    )
    x.add_argument("--input", required=True); x.add_argument("--output", required=True); x.add_argument("--schema"); x.add_argument("--reference", action="append"); x.add_argument("--generated-at"); x.add_argument("--force", action="store_true"); x.set_defaults(func=cmd_result_finalize)

    plan = sub.add_parser(
        "plan", help="rolling-wave readiness, migration, and transactional planning state",
        description="Planning-state effect only. Readiness and migration are deterministic projections; transact commits immutable events through an atomic current-pointer and emits a transaction receipt. Conflicts are retryable; semantic invalidations are explicit.",
    ).add_subparsers(parser_class=BbkArgumentParser, dest="plan_command", required=True)
    x = plan.add_parser(
        "readiness", help="project ROADMAP_READY/FRONTIER_READY execution admission",
        description="Effect: optional workspace projection. Atomic only when written by the caller's finalizer. Validates roadmap/frontier readiness and separates FULLY_COMPILED from execution admission. Emits no receipt by itself; invalidates on roadmap/frontier/coverage digests. Replay legal: yes for unchanged inputs.",
    )
    x.add_argument("--roadmap", required=True); x.add_argument("--frontier"); x.add_argument("--coverage", required=True); x.add_argument("--deferred", action="append"); x.add_argument("--planning-mode", choices=["FAST_CONTINUATION","STANDARD","FULL_GOVERNED"], default="FAST_CONTINUATION"); x.add_argument("--architecture-mode", choices=["ADOPT_AND_GAP","DELTA","FULL"], default="ADOPT_AND_GAP"); x.add_argument("--fully-compiled", action="store_true"); x.add_argument("--full-compilation-trigger"); x.add_argument("--output"); x.add_argument("--force", action="store_true"); x.set_defaults(func=cmd_planning_readiness)
    x = plan.add_parser(
        "migrate-readiness", help="project an immutable legacy fully detailed plan into Alpha.17 readiness",
        description="Effect: WORKSPACE_IMPLEMENTATION only when --output is used. Leaves the legacy artifact unchanged, emits a successor compatibility projection plus BASELINE_ADVANCED migration anchor, and binds the source digest. Replay legal for unchanged inputs.",
    )
    x.add_argument("--legacy", required=True); x.add_argument("--roadmap", required=True); x.add_argument("--frontier", required=True); x.add_argument("--coverage", required=True); x.add_argument("--authority", required=True); x.add_argument("--generated-at"); x.add_argument("--output"); x.add_argument("--force", action="store_true"); x.set_defaults(func=cmd_plan_migrate_readiness)
    x = plan.add_parser(
        "transact", help="atomically append plan events and regenerate requested projections",
        description="Effect: PLANNING_STATE_MUTATION. Atomic commit point: state-root/current.json. Validates event types, predecessor/head expectations, and authority; emits bbk.plan-transaction-receipt.v1. A changed current head invalidates and returns retryable BBK-PLAN-TX-CONFLICT. Replay legal only after confirming no commit occurred.",
    )
    x.add_argument("--state-root", required=True); x.add_argument("--authority", required=True); x.add_argument("--event", action="append", required=True); x.add_argument("--roadmap-out"); x.add_argument("--frontier-out"); x.add_argument("--coverage-out"); x.add_argument("--role-return-out"); x.add_argument("--expected-head"); x.add_argument("--transaction-id"); x.add_argument("--generated-at"); x.set_defaults(func=cmd_plan_transact_opt)

    wc = sub.add_parser("worker-contract", help="deterministic routine Worker contracts").add_subparsers(parser_class=BbkArgumentParser, dest="worker_contract_command", required=True)
    x=wc.add_parser("generate"); x.add_argument("--work-unit",required=True); x.add_argument("--authority",required=True); x.add_argument("--workspace-receipt",required=True); x.add_argument("--profile-constraints",required=True); x.add_argument("--return-contract",default="bbk.worker-return.v2"); x.add_argument("--output"); x.add_argument("--force",action="store_true"); x.set_defaults(func=cmd_worker_contract_generate)
    ac = sub.add_parser("assertion-contract", help="deterministic routine verification assertions").add_subparsers(parser_class=BbkArgumentParser, dest="assertion_contract_command", required=True)
    x=ac.add_parser("generate"); x.add_argument("--acceptance-criterion",required=True); x.add_argument("--profile-template",required=True); x.add_argument("--candidate-stage",required=True); x.add_argument("--output"); x.add_argument("--force",action="store_true"); x.set_defaults(func=cmd_assertion_contract_generate)

    command = sub.add_parser("command", help="semantic command attempt and evidence replay operations").add_subparsers(parser_class=BbkArgumentParser, dest="command_command", required=True)
    x=command.add_parser("replay-evaluate", description="Read-only evaluation. Validates command-attempt lineage and permits at most one same-semantic-attempt replay only when effects are proven NONE, cleanup COMPLETE, candidate unfrozen, and failure is capture-only. Emits no effect receipt unless --output is used."); x.add_argument("--attempt",required=True); x.add_argument("--candidate-frozen",action="store_true"); x.add_argument("--emit-replay",action="store_true"); x.add_argument("--output"); x.add_argument("--force",action="store_true"); x.set_defaults(func=cmd_command_replay_evaluate)
    x=command.add_parser("capture-preflight", description="Read-only wrapper inspection. Validates PowerShell reserved-variable safety, native stderr/exit capture, output bounds, timeout/cleanup declarations, canonical encoding, and atomic receipt-path support. Replay legal: yes."); x.add_argument("--script",required=True); x.add_argument("--receipt-dir",required=True); x.add_argument("--output"); x.add_argument("--force",action="store_true"); x.set_defaults(func=cmd_command_capture_preflight)

    coverage = sub.add_parser("coverage", help="project coverage and completion-truth projections").add_subparsers(parser_class=BbkArgumentParser, dest="coverage_command", required=True)
    x=coverage.add_parser("project", description="Read-only deterministic completion-truth projection unless --output is used. Validates capability/claim closure and never infers whole-project completion from candidate PASS. Invalidates on coverage input digest; replay legal."); x.add_argument("--coverage",required=True); x.add_argument("--output"); x.add_argument("--force",action="store_true"); x.set_defaults(func=cmd_project_coverage_project)

    child_event_parser = sub.add_parser("child-event", help="emit typed child lifecycle events").add_subparsers(parser_class=BbkArgumentParser, dest="child_event_command", required=True)
    x=child_event_parser.add_parser("emit"); x.add_argument("--child-ref",required=True); x.add_argument("--state",required=True,choices=["STARTED","PROGRESS_MILESTONE","BLOCKED","RETURN_READY","FAILED","CANCELLED"]); x.add_argument("--detail"); x.add_argument("--observed-at"); x.add_argument("--output"); x.add_argument("--force",action="store_true"); x.set_defaults(func=cmd_child_event_emit)

    sub.add_parser("version", help="print the BBK package version")
    x = sub.add_parser("init"); x.add_argument("--root"); x.add_argument("--title"); x.add_argument("--project-id"); x.add_argument("--force", action="store_true"); x.add_argument("--no-examples", action="store_true", help="initialize operational BBK state without materializing reference templates"); x.set_defaults(func=cmd_init)
    x = sub.add_parser("status"); x.add_argument("--root"); x.set_defaults(func=cmd_status)
    x = sub.add_parser("doctor"); x.add_argument("--root"); x.set_defaults(func=cmd_doctor)
    x = sub.add_parser("digest"); x.add_argument("path"); x.set_defaults(func=cmd_digest)

    artifact = sub.add_parser("artifact").add_subparsers(parser_class=BbkArgumentParser, dest="artifact_command", required=True)
    x = artifact.add_parser("inspect"); x.add_argument("path"); x.add_argument("--exclude", action="append"); x.add_argument("--include-examples", action="store_true"); x.add_argument("--verbose", action="store_true"); x.add_argument("--output"); x.set_defaults(func=cmd_artifact_inspect)
    x = artifact.add_parser("manifest"); x.add_argument("--root"); x.add_argument("--path", action="append"); x.add_argument("--source", action="append"); x.add_argument("--include", action="append"); x.add_argument("--exclude", action="append"); x.add_argument("--include-examples", action="store_true"); x.add_argument("--subject"); x.add_argument("--root-label"); x.add_argument("--output"); x.set_defaults(func=cmd_artifact_manifest)
    x = artifact.add_parser("doctor"); x.add_argument("--root", required=True); x.add_argument("--publication-root"); x.set_defaults(func=cmd_artifact_doctor)
    x = artifact.add_parser("reconcile"); x.add_argument("journal_or_operation"); x.add_argument("--root"); x.add_argument("--resume", action="store_true"); x.set_defaults(func=cmd_artifact_reconcile)
    x = artifact.add_parser("preflight"); x.add_argument("draft_root"); x.add_argument("--registry"); x.add_argument("--max-depth", type=int, default=128); x.set_defaults(func=cmd_artifact_preflight)
    x = artifact.add_parser("seal"); x.add_argument("draft_root"); x.add_argument("--output", required=True); x.add_argument("--registry"); x.add_argument("--recover-stale-lock", action="store_true"); x.set_defaults(func=cmd_artifact_seal)
    x = artifact.add_parser("finalize"); x.add_argument("draft_root", nargs="?"); x.add_argument("--root"); x.add_argument("--output"); x.add_argument("--publication-root"); x.add_argument("--registry"); x.add_argument("--package-id"); x.add_argument("--revision"); x.add_argument("--source", action="append"); x.add_argument("--include", action="append"); x.add_argument("--exclude", action="append"); x.add_argument("--subject-kind"); x.add_argument("--subject-id"); x.add_argument("--subject-revision"); x.add_argument("--purpose"); x.add_argument("--allow-mutable-coordination", action="store_true"); x.add_argument("--no-current-pointer", action="store_true"); x.add_argument("--recover-stale-lock", action="store_true"); x.set_defaults(func=cmd_artifact_finalize)
    x = artifact.add_parser("freshness"); x.add_argument("subject"); x.add_argument("--root"); x.add_argument("--registry"); x.set_defaults(func=cmd_artifact_freshness)
    x = artifact.add_parser("verify"); x.add_argument("manifest"); x.add_argument("--root"); x.add_argument("--registry"); x.set_defaults(func=cmd_artifact_verify)
    x = artifact.add_parser("successor"); x.add_argument("sealed_root"); x.add_argument("--output", required=True); x.add_argument("--revision", required=True); x.add_argument("--reason", required=True); x.add_argument("--registry"); x.add_argument("--recover-stale-lock", action="store_true"); x.set_defaults(func=cmd_artifact_successor)

    preflight = sub.add_parser("preflight").add_subparsers(parser_class=BbkArgumentParser, dest="preflight_command", required=True)
    x = preflight.add_parser("run"); x.add_argument("request"); x.add_argument("--root"); x.add_argument("--output"); x.add_argument("--cache-dir"); x.add_argument("--no-cache", action="store_true"); x.add_argument("--timeout", type=float, default=5.0); x.set_defaults(func=cmd_preflight_run)

    context = sub.add_parser("context").add_subparsers(parser_class=BbkArgumentParser, dest="context_command", required=True)
    x = context.add_parser("worker"); x.add_argument("--root"); x.add_argument("--work-unit", required=True); x.add_argument("--profile-lock", required=True); x.add_argument("--host-preflight", required=True); x.add_argument("--prototype-charter"); x.add_argument("--output"); x.add_argument("--id"); x.add_argument("--revision", default="1"); x.set_defaults(func=cmd_context_worker)
    x = context.add_parser("review"); x.add_argument("--root"); x.add_argument("--candidate", required=True); x.add_argument("--request", required=True); x.add_argument("--output"); x.add_argument("--id"); x.add_argument("--revision", default="1"); x.set_defaults(func=cmd_context_review)

    fit = sub.add_parser("fit").add_subparsers(parser_class=BbkArgumentParser, dest="fit_command", required=True)
    x = fit.add_parser("validate"); x.add_argument("path"); x.set_defaults(func=cmd_fit_validate)
    x = fit.add_parser("render"); x.add_argument("path"); x.add_argument("--format", choices=["markdown", "json"], default="markdown"); x.add_argument("--output"); x.set_defaults(func=cmd_fit_render)
    x = fit.add_parser("new"); x.add_argument("--output", required=True); x.add_argument("--force", action="store_true"); x.set_defaults(func=cmd_fit_new)
    x = fit.add_parser("check-chain"); x.add_argument("--fit", required=True); x.add_argument("--structure", action="append", default=[]); x.add_argument("--slice", action="append", default=[]); x.add_argument("--work-unit", action="append", default=[]); x.set_defaults(func=cmd_fit_check_chain)

    assurance = sub.add_parser("assurance").add_subparsers(parser_class=BbkArgumentParser, dest="assurance_command", required=True)
    x = assurance.add_parser("validate"); x.add_argument("path"); x.set_defaults(func=cmd_assurance_validate)
    x = assurance.add_parser("new"); x.add_argument("--output", required=True); x.add_argument("--force", action="store_true"); x.set_defaults(func=cmd_assurance_new)

    sde = sub.add_parser("state-effect").add_subparsers(parser_class=BbkArgumentParser, dest="state_effect_command", required=True)
    x = sde.add_parser("validate"); x.add_argument("path"); x.set_defaults(func=cmd_sde_validate)
    x = sde.add_parser("render"); x.add_argument("path"); x.add_argument("--format", choices=["markdown", "json"], default="markdown"); x.add_argument("--output"); x.set_defaults(func=cmd_sde_render)
    x = sde.add_parser("new"); x.add_argument("--output", required=True); x.add_argument("--force", action="store_true"); x.set_defaults(func=cmd_sde_new)

    trace = sub.add_parser("trace").add_subparsers(parser_class=BbkArgumentParser, dest="trace_command", required=True)
    x = trace.add_parser("validate"); x.add_argument("path"); x.set_defaults(func=cmd_trace_validate)
    x = trace.add_parser("new"); x.add_argument("--output", required=True); x.add_argument("--force", action="store_true"); x.set_defaults(func=cmd_trace_new)
    x = trace.add_parser("check-set"); x.add_argument("--design"); x.add_argument("--trace", action="append", required=True); x.set_defaults(func=cmd_trace_check_set)

    structure = sub.add_parser("structure").add_subparsers(parser_class=BbkArgumentParser, dest="structure_command", required=True)
    x = structure.add_parser("validate"); x.add_argument("path"); x.set_defaults(func=cmd_structure_validate)
    x = structure.add_parser("render"); x.add_argument("path"); x.add_argument("--format", choices=["markdown", "json"], default="markdown"); x.add_argument("--output"); x.set_defaults(func=cmd_structure_render)
    x = structure.add_parser("new"); x.add_argument("--output", required=True); x.add_argument("--version", choices=["v1", "v2", "v3"], default="v3"); x.add_argument("--kind", choices=["software", "automation", "hardware", "procedure", "data", "document", "infrastructure", "network_configuration", "deployment_configuration", "mixed", "other"], default="software"); x.add_argument("--depth", choices=["compact", "standard", "full"], default="standard"); x.add_argument("--force", action="store_true"); x.set_defaults(func=cmd_structure_new)
    x = structure.add_parser("review"); x.add_argument("--contract", required=True); x.add_argument("--inventory", required=True); x.add_argument("--output"); x.set_defaults(func=cmd_structure_review)

    slices = sub.add_parser("slice").add_subparsers(parser_class=BbkArgumentParser, dest="slice_command", required=True)
    x = slices.add_parser("validate"); x.add_argument("path"); x.set_defaults(func=cmd_slice_validate)
    x = slices.add_parser("render"); x.add_argument("path"); x.add_argument("--format", choices=["markdown", "json"], default="markdown"); x.add_argument("--output"); x.set_defaults(func=cmd_slice_render)
    x = slices.add_parser("new"); x.add_argument("--output", required=True); x.add_argument("--version", choices=["v1", "v2"], default="v2"); x.add_argument("--force", action="store_true"); x.set_defaults(func=cmd_slice_new)
    x = slices.add_parser("check-set"); x.add_argument("--contract", required=True); x.add_argument("--slice", action="append", required=True); x.set_defaults(func=cmd_slice_check_set)

    work_unit = sub.add_parser("work-unit").add_subparsers(parser_class=BbkArgumentParser, dest="work_unit_command", required=True)
    x = work_unit.add_parser("validate"); x.add_argument("path"); x.set_defaults(func=cmd_work_unit_validate)
    x = work_unit.add_parser("new"); x.add_argument("--output", required=True); x.add_argument("--force", action="store_true"); x.set_defaults(func=cmd_work_unit_new)

    evidence = sub.add_parser("evidence").add_subparsers(parser_class=BbkArgumentParser, dest="evidence_command", required=True)
    x = evidence.add_parser("validate"); x.add_argument("path"); x.set_defaults(func=cmd_evidence_validate)
    x = evidence.add_parser("new"); x.add_argument("--output", required=True); x.add_argument("--kind", choices=["generic", "environment-observation"], default="generic"); x.add_argument("--force", action="store_true"); x.set_defaults(func=cmd_evidence_new)

    review = sub.add_parser("review").add_subparsers(parser_class=BbkArgumentParser, dest="review_command", required=True)
    x = review.add_parser("plan"); x.add_argument("--assurance", required=True); x.add_argument("--id", required=True); x.add_argument("--purpose", required=True); x.add_argument("--subject"); x.add_argument("--subject-ref"); x.add_argument("--subject-kind"); x.add_argument("--subject-revision"); x.add_argument("--capability", action="append"); x.add_argument("--output"); x.set_defaults(func=cmd_review_plan)
    x = review.add_parser("context"); x.add_argument("--manifest", required=True); x.add_argument("--root"); x.add_argument("--source"); x.add_argument("--id"); x.add_argument("--include", action="append"); x.add_argument("--exclude", action="append"); x.add_argument("--output"); x.set_defaults(func=cmd_review_context)
    x = review.add_parser("run"); x.add_argument("--manifest", required=True); x.add_argument("--context", required=True); x.add_argument("--id", required=True); x.add_argument("--root"); x.add_argument("--attempt", action="append"); x.add_argument("--receipt", action="append"); x.add_argument("--finding", action="append"); x.add_argument("--disposition", action="append"); x.add_argument("--predecessor", action="append"); x.add_argument("--output"); x.set_defaults(func=cmd_review_run)
    x = review.add_parser("inspect"); x.add_argument("path"); x.set_defaults(func=cmd_review_inspect)
    x = review.add_parser("reconcile"); x.add_argument("--finding", action="append", required=True); x.add_argument("--output"); x.set_defaults(func=cmd_review_reconcile)
    x = review.add_parser("close"); x.add_argument("--finding", required=True); x.add_argument("--id", required=True); x.add_argument("--disposition", required=True, choices=["FIXED", "REBUTTED", "ACCEPTED_RISK", "FALSE_POSITIVE", "DUPLICATE_OF", "SUPERSEDED", "DEFERRED", "OUT_OF_SCOPE", "REMAINS_OPEN"]); x.add_argument("--successor-ref", required=True); x.add_argument("--successor-digest"); x.add_argument("--successor-file"); x.add_argument("--evidence", action="append"); x.add_argument("--review-attempt"); x.add_argument("--authority"); x.add_argument("--residual-impact", required=True); x.add_argument("--reopen-trigger", action="append"); x.add_argument("--output", required=True); x.set_defaults(func=cmd_review_close)
    x = review.add_parser("learn"); x.add_argument("--id", required=True); x.add_argument("--type", required=True); x.add_argument("--lesson", required=True); x.add_argument("--scope", required=True); x.add_argument("--supporting", action="append"); x.add_argument("--contrary", action="append"); x.add_argument("--finding", action="append"); x.add_argument("--run", action="append"); x.add_argument("--disposition", action="append"); x.add_argument("--confidence", required=True); x.add_argument("--uncertainty", required=True); x.add_argument("--action", required=True); x.add_argument("--privacy-class", default="project-local"); x.add_argument("--export-class", default="restricted"); x.add_argument("--output", required=True); x.set_defaults(func=cmd_review_learn)

    m = sub.add_parser("manifest").add_subparsers(parser_class=BbkArgumentParser, dest="manifest_command", required=True)
    x = m.add_parser("finalize", help="canonicalize, validate, and atomically publish one JSON manifest")
    x.add_argument("--input", required=True); x.add_argument("--output", required=True); x.add_argument("--schema"); x.add_argument("--reference", action="append"); x.add_argument("--generated-at"); x.add_argument("--force", action="store_true"); x.set_defaults(func=cmd_manifest_finalize_opt)
    x = m.add_parser("create"); x.add_argument("--root"); x.add_argument("--source"); x.add_argument("--output"); x.add_argument("--exclude", action="append"); x.add_argument("--include-examples", action="store_true", help="explicitly include shipped EXAMPLE-* templates"); x.set_defaults(func=cmd_manifest_create)
    x = m.add_parser("compare"); x.add_argument("--root"); x.add_argument("--left", required=True); g = x.add_mutually_exclusive_group(); g.add_argument("--right"); g.add_argument("--source"); x.add_argument("--include-examples", action="store_true", help="include EXAMPLE-* templates when compiling --source"); x.set_defaults(func=cmd_manifest_compare)

    c = sub.add_parser("candidate").add_subparsers(parser_class=BbkArgumentParser, dest="candidate_command", required=True)
    x = c.add_parser("freeze"); x.add_argument("--root"); x.add_argument("--id"); x.add_argument("--source"); x.add_argument("--note"); x.add_argument("--output"); x.add_argument("--structure-inventory", action="append"); x.add_argument("--trace", action="append"); x.add_argument("--formal-model", action="append"); x.add_argument("--allow-warnings", action="store_true"); x.add_argument("--allow-external-source", action="store_true"); x.add_argument("--include-examples", action="store_true", help="explicitly include shipped EXAMPLE-* templates in candidate content"); x.set_defaults(func=cmd_candidate_freeze)
    x = c.add_parser("check"); x.add_argument("--root"); x.add_argument("--id", required=True); x.set_defaults(func=cmd_candidate_check)
    x = c.add_parser("status"); x.add_argument("--root"); x.add_argument("--id", required=True); x.add_argument("--check", action="store_true"); x.set_defaults(func=cmd_candidate_status)
    x = c.add_parser("invalidate"); x.add_argument("--root"); x.add_argument("--id", required=True); x.add_argument("--reason", required=True); x.set_defaults(func=cmd_candidate_invalidate)
    x = c.add_parser("verify"); x.add_argument("manifest"); x.set_defaults(func=cmd_candidate_verify_file)

    gates = sub.add_parser("gate").add_subparsers(parser_class=BbkArgumentParser, dest="gate_command", required=True)
    x = gates.add_parser("list"); x.add_argument("--root"); x.set_defaults(func=cmd_gate_list)
    x = gates.add_parser("run"); x.add_argument("--root"); x.add_argument("--phase", required=True); x.add_argument("--candidate"); x.add_argument("--gate", action="append"); x.add_argument("--no-reuse", action="store_true"); x.set_defaults(func=cmd_gate_run)
    x = gates.add_parser("record"); x.add_argument("--candidate", required=True); x.add_argument("--gate-id", required=True); x.add_argument("--status", required=True, choices=["PASS", "FAIL", "BLOCKED", "ERROR", "INCONCLUSIVE", "NOT_RUN"]); x.add_argument("--evidence", action="append", default=[]); x.add_argument("--output", required=True); x.set_defaults(func=cmd_gate_record)
    x = gates.add_parser("check"); x.add_argument("receipt"); x.add_argument("--candidate", required=True); x.set_defaults(func=cmd_gate_check)

    w = sub.add_parser("workspace").add_subparsers(parser_class=BbkArgumentParser, dest="workspace_command", required=True)
    x=w.add_parser("admit", help="issue a reusable workspace admission receipt", description="Read-only observation projection unless --output is used. Binds baseline, protected-tree state, known dirt, owned roots, mutation owner, and serialization. Emits bbk.workspace-admission-receipt.v1; invalidates on repository/baseline/ownership changes.")
    x.add_argument("--repository-ref",required=True); x.add_argument("--baseline-ref",required=True); x.add_argument("--protected-tree-state",choices=["CLEAN","KNOWN_ACCEPTED_STATE","BLOCKED"],required=True); x.add_argument("--known-unrelated-dirt",action="append"); x.add_argument("--owned-root",action="append",required=True); x.add_argument("--mutation-owner",required=True); x.add_argument("--serialization-state",choices=["EXCLUSIVE","POSITIVELY_SERIALIZED","READ_ONLY"],required=True); x.add_argument("--issued-at"); x.add_argument("--output"); x.add_argument("--force",action="store_true"); x.set_defaults(func=cmd_workspace_admit)
    x = w.add_parser("create"); x.add_argument("--root"); x.add_argument("--id", required=True); x.add_argument("--base", default="HEAD"); x.add_argument("--branch"); x.add_argument("--path"); x.add_argument("--purpose"); x.add_argument("--lease-hours", type=float); x.add_argument("--detach", action="store_true"); x.set_defaults(func=cmd_workspace_create)
    x = w.add_parser("list"); x.add_argument("--root"); x.add_argument("--all", action="store_true"); x.set_defaults(func=cmd_workspace_list)
    x = w.add_parser("inspect"); x.add_argument("--root"); x.add_argument("--id", required=True); x.set_defaults(func=cmd_workspace_inspect)
    x = w.add_parser("renew"); x.add_argument("--root"); x.add_argument("--id", required=True); x.add_argument("--hours", type=float); x.set_defaults(func=cmd_workspace_renew)
    x = w.add_parser("cleanup"); x.add_argument("--root"); x.add_argument("--id", required=True); x.add_argument("--force", action="store_true"); x.add_argument("--delete-branch", action="store_true"); x.set_defaults(func=cmd_workspace_cleanup)

    # Alpha.4/5 command spelling retained as a compatibility surface.  The
    # workspace command above is preferred because it records ownership and leases.
    wt = sub.add_parser("worktree").add_subparsers(parser_class=BbkArgumentParser, dest="worktree_command", required=True)
    for name, func in [("plan", cmd_worktree_plan), ("create", cmd_worktree_create), ("cleanup", cmd_worktree_cleanup)]:
        x = wt.add_parser(name); x.add_argument("--repo", default="."); x.add_argument("--path", required=True); x.add_argument("--ref", default="HEAD")
        if name == "cleanup": x.add_argument("--force", action="store_true")
        x.set_defaults(func=func)

    pr = sub.add_parser("profile").add_subparsers(parser_class=BbkArgumentParser, dest="profile_command", required=True)
    x=pr.add_parser("admit", help="late-bind an effective profile/environment identity against semantic constraints", description="Read-only runtime admission unless --output is used. Validates capabilities, gates, family, environment, and optional exact digest. Emits bbk.effective-profile-receipt.v1; semantic equivalence avoids replanning while changed constraints/profile/environment invalidate the receipt.")
    x.add_argument("--constraints",required=True); x.add_argument("--effective-profile",required=True); x.add_argument("--environment",required=True); x.add_argument("--registry-revision",required=True); x.add_argument("--selector"); x.add_argument("--exact-digest-required",action="store_true"); x.add_argument("--exact-digest-reason"); x.add_argument("--observed-at"); x.add_argument("--output"); x.add_argument("--force",action="store_true"); x.set_defaults(func=cmd_profile_admit)
    x = pr.add_parser("list"); x.add_argument("--root"); x.add_argument("--profile-dir", "--profile-root", dest="profile_dir", action="append"); x.set_defaults(func=cmd_profile_list)
    x = pr.add_parser("inspect"); x.add_argument("--root"); x.add_argument("--id", required=True); x.add_argument("--version"); x.add_argument("--profile-dir", "--profile-root", dest="profile_dir", action="append"); x.set_defaults(func=cmd_profile_inspect)
    x = pr.add_parser("resolve"); x.add_argument("--root"); x.add_argument("--source"); x.add_argument("--id", required=True); x.add_argument("--version"); x.add_argument("--profile-dir", "--profile-root", dest="profile_dir", action="append"); x.add_argument("--work-unit"); x.add_argument("--task-profile"); x.add_argument("--assurance-tier", choices=["routine", "material", "consequential", "critical"]); x.add_argument("--role"); x.add_argument("--change-class", action="append"); x.add_argument("--hint", action="append"); x.add_argument("--path", action="append"); x.add_argument("--solution-outcome-fit", action="append"); x.add_argument("--structure-contract", action="append"); x.add_argument("--execution-slice", action="append"); x.add_argument("--state-decision-effect", action="append"); x.add_argument("--assurance-contract", action="append"); x.add_argument("--review-manifest", action="append"); x.add_argument("--evidence-input", action="append"); x.add_argument("--run-tools", action="store_true"); x.add_argument("--write-lock", action="store_true"); x.add_argument("--lock-path"); x.add_argument("--allow-unverified", action="store_true"); x.add_argument("--timeout", type=float, default=120.0); x.set_defaults(func=cmd_profile_resolve)
    x = pr.add_parser("dispatch"); x.add_argument("--operation", required=True, choices=sorted(PROFILE_CAPABILITY_OPERATION_SPEC)); x.add_argument("--root"); x.add_argument("--source"); x.add_argument("--id", required=True); x.add_argument("--version"); x.add_argument("--profile-dir", "--profile-root", dest="profile_dir", action="append"); x.add_argument("--role"); x.add_argument("--task-profile"); x.add_argument("--assurance-tier", choices=["routine", "material", "consequential", "critical"]); x.add_argument("--change-class", action="append"); x.add_argument("--hint", action="append"); x.add_argument("--path", action="append"); x.add_argument("--lens-id", action="append"); x.add_argument("--assignment-id", action="append"); x.add_argument("--state-decision-effect"); x.add_argument("--state-effect-inventory"); x.add_argument("--assurance-contract"); x.add_argument("--review-manifest"); x.add_argument("--review-context"); x.add_argument("--evidence-input"); x.add_argument("--run-tools", action="store_true"); x.add_argument("--allow-unverified", action="store_true"); x.add_argument("--timeout", type=float, default=120.0); x.add_argument("--output"); x.set_defaults(func=cmd_profile_dispatch)

    question = sub.add_parser("question").add_subparsers(parser_class=BbkArgumentParser, dest="question_command", required=True)
    x = question.add_parser("validate"); x.add_argument("path"); x.set_defaults(func=cmd_question_validate)
    x = question.add_parser("new"); x.add_argument("--root"); x.add_argument("--id", required=True); x.add_argument("--root-decision", required=True); x.add_argument("--owner-role", default="bbk_questioning_wayfinder"); x.add_argument("--parent-scope"); x.add_argument("--authority-mode", choices=["USER_DECIDES", "WAYFINDER_RECOMMENDS", "DELEGATED", "CONSTRAINT_DRIVEN"], default="WAYFINDER_RECOMMENDS"); x.add_argument("--authority-holder", default="user"); x.add_argument("--need-class", choices=["ENVIRONMENT_FACT", "CONFIGURATION_PARAMETER", "REVERSIBLE_IMPLEMENTATION_CHOICE", "ARCHITECTURAL_DECISION", "AUTHORITY_EXPANSION", "USER_RESERVED_PREFERENCE"], default="ARCHITECTURAL_DECISION"); x.add_argument("--attention-rationale"); x.add_argument("--discoverability", choices=["DISCOVERABLE_NOW", "DISCOVERABLE_LATER", "NOT_DISCOVERABLE_BY_BBK", "NOT_APPLICABLE"], default="NOT_DISCOVERABLE_BY_BBK"); x.add_argument("--safe-default"); x.add_argument("--blocks-unaffected-work", action="store_true"); x.add_argument("--next-action", default="Prepare and present a decision-ready recommendation."); x.add_argument("--output"); x.add_argument("--force", action="store_true"); x.set_defaults(func=cmd_question_new)
    x = question.add_parser("list"); x.add_argument("--root"); x.add_argument("--status"); x.set_defaults(func=cmd_question_list)

    handoff = sub.add_parser("handoff").add_subparsers(parser_class=BbkArgumentParser, dest="handoff_command", required=True)
    x = handoff.add_parser("create")
    x.add_argument("--root")
    x.add_argument("--id")
    x.add_argument("--work-unit", required=True)
    x.add_argument("--attempt", type=int, default=1)
    x.add_argument("--role", default="bbk_worker")
    x.add_argument("--invocation-id")
    x.add_argument("--thread-id")
    x.add_argument("--subject-kind", default="work-unit")
    x.add_argument("--subject-id")
    x.add_argument("--subject-revision")
    x.add_argument("--authority-source")
    x.add_argument("--authority-scope", action="append")
    x.add_argument("--authority-not-standing", action="store_true")
    x.add_argument("--capability-zone", action="append", metavar="KIND=PATH")
    x.add_argument("--interrupt-reason", choices=[
        "USER_CANCELLED", "CHILD_REQUESTED_STOP", "UNAUTHORIZED_EFFECT",
        "OWNERSHIP_COLLISION", "CONFIRMED_HANG", "OBSOLETE_WORK",
    ])
    x.add_argument("--interrupt-evidence", action="append")
    x.add_argument("--partial-work-location")
    x.add_argument("--disposition", choices=[
        "COMPLETE", "PARTIAL",
        "BLOCKED_TECHNICAL", "BLOCKED_AUTHORITY", "BLOCKED_DECISION",
        "PAUSED_CAPACITY", "PAUSED_HOST_WINDOW", "CANCELLED", "INCONCLUSIVE",
    ], required=True)
    x.add_argument("--summary", required=True)
    x.add_argument("--work-performed", action="append")
    x.add_argument("--changed-path", action="append")
    x.add_argument("--command-run", action="append")
    x.add_argument("--check", action="append")
    x.add_argument("--finding", action="append")
    x.add_argument("--discovery", action="append")
    x.add_argument("--residual", action="append")
    x.add_argument("--blocker", action="append")
    x.add_argument("--artifact", action="append")
    x.add_argument("--evidence", action="append")
    x.add_argument("--continuation-state", choices=["NOT_REQUIRED", "READY", "WAITING", "BLOCKED"], default="NOT_REQUIRED")
    x.add_argument("--checkpoint")
    x.add_argument("--no-resume-same-thread", action="store_true")
    x.add_argument("--completed-step")
    x.add_argument("--next-step")
    x.add_argument("--next-action", required=True)
    x.add_argument("--cleanup-state", choices=["NOT_REQUIRED", "COMPLETE", "PARTIAL", "BLOCKED", "QUARANTINED"], default="NOT_REQUIRED")
    x.add_argument("--cleanup-action", action="append")
    x.add_argument("--prohibited-claim", action="append")
    x.add_argument("--legacy-v1", action="store_true", help="explicitly create the legacy standalone bbk.handoff.v1 JSON record")
    x.add_argument("--output")
    x.add_argument("--force", action="store_true")
    x.set_defaults(func=cmd_handoff_create)
    x = handoff.add_parser("verify"); x.add_argument("path"); x.add_argument("--root"); x.set_defaults(func=cmd_handoff_verify)
    x = handoff.add_parser("list"); x.add_argument("--root"); x.add_argument("--work-unit"); x.add_argument("--latest", action="store_true"); x.set_defaults(func=cmd_handoff_list)

    schema = sub.add_parser("schema").add_subparsers(parser_class=BbkArgumentParser, dest="schema_command", required=True)
    x = schema.add_parser("list"); x.set_defaults(func=cmd_schema_list)
    x = schema.add_parser("template"); x.add_argument("--kind", required=True, choices=sorted(SCHEMA_TEMPLATE_REGISTRY)); x.add_argument("--output", required=True); x.add_argument("--subject-kind", choices=["software", "automation", "hardware", "procedure", "data", "document", "infrastructure", "network_configuration", "deployment_configuration", "mixed", "other"]); x.add_argument("--depth", choices=["compact", "standard", "full"]); x.add_argument("--force", action="store_true"); x.set_defaults(func=cmd_schema_template)
    x = schema.add_parser("enum"); x.add_argument("--schema", required=True); x.add_argument("--pointer", required=True); x.set_defaults(func=cmd_schema_enum)
    x = schema.add_parser("explain"); x.add_argument("--schema", required=True); x.add_argument("--instance", required=True); x.add_argument("--pointer"); x.set_defaults(func=cmd_schema_explain)
    x = schema.add_parser("validate"); x.add_argument("--schema", required=True); x.add_argument("--instance", action="append", required=True); x.add_argument("--root"); x.add_argument("--tool-dir"); x.add_argument("--ensure", action="store_true"); x.add_argument("--wheelhouse"); x.add_argument("--timeout", type=float, default=120.0); x.set_defaults(func=cmd_schema_validate)
    x = schema.add_parser("status"); x.add_argument("--root"); x.add_argument("--tool-dir"); x.set_defaults(func=cmd_schema_status)

    operation = sub.add_parser("operation", help="run only a qualified checked-in deterministic operation").add_subparsers(parser_class=BbkArgumentParser, dest="operation_command", required=True)
    x = operation.add_parser("list"); x.add_argument("--registry"); x.set_defaults(func=cmd_operation_list)
    for name, handler in (("qualify", cmd_operation_qualify), ("run", cmd_operation_run)):
        x = operation.add_parser(name)
        x.add_argument("--id", dest="operation_id", required=True)
        x.add_argument("--subject", required=True)
        x.add_argument("--arg", dest="argv", action="append", default=[])
        x.add_argument("--environment", action="append", default=[])
        x.add_argument("--registry")
        x.set_defaults(func=handler)

    identity = sub.add_parser("identity", help="validate or derive typed identity graph nodes").add_subparsers(parser_class=BbkArgumentParser, dest="identity_command", required=True)
    x = identity.add_parser("validate")
    x.add_argument("path")
    x.set_defaults(func=cmd_identity_validate)
    x = identity.add_parser("derive")
    x.add_argument("--kind", required=True, choices=sorted(IDENTITY_KINDS))
    x.add_argument("--subject-kind", required=True)
    x.add_argument("--subject-id", required=True)
    x.add_argument("--subject-revision", required=True)
    x.add_argument("--subject-digest", required=True)
    x.add_argument("--revision", required=True)
    x.add_argument("--payload")
    x.add_argument("--node-id")
    x.add_argument("--output")
    x.add_argument("--force", action="store_true")
    x.set_defaults(func=cmd_identity_derive)

    b = sub.add_parser("beads").add_subparsers(parser_class=BbkArgumentParser, dest="beads_command", required=True)
    x = b.add_parser("plan"); x.add_argument("--root"); x.add_argument("--work-unit"); x.add_argument("--kind", action="append", choices=sorted(BEADS_OBJECT_KINDS)); x.add_argument("--id", action="append"); x.add_argument("--output"); x.add_argument("--apply", action="store_true"); x.add_argument("--initialize", action="store_true"); x.add_argument("--timeout", type=float, default=60.0); x.set_defaults(func=cmd_beads_plan)
    x = b.add_parser("handoff-plan"); x.add_argument("--root"); x.add_argument("--handoff", required=True); x.add_argument("--target-bbk-id"); x.add_argument("--bead"); x.add_argument("--output"); x.add_argument("--apply", action="store_true"); x.add_argument("--timeout", type=float, default=60.0); x.set_defaults(func=cmd_beads_handoff_plan)

    package = sub.add_parser("package").add_subparsers(parser_class=BbkArgumentParser, dest="package_command", required=True)
    x = package.add_parser("verify"); x.add_argument("package_root", nargs="?", default=str(PACKAGE_ROOT)); x.set_defaults(func=cmd_package_verify)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    configure_utf8_standard_streams()
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    wants_json = "--json" in raw_argv
    try:
        args = parser().parse_args(raw_argv)
    except BbkCliParseError as exc:
        payload = exc.diagnostic
        if wants_json:
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        else:
            print(f"bbk: error: {payload.get('error') or payload.get('message')}", file=sys.stderr)
            print(f"example: {payload.get('example_command')}", file=sys.stderr)
            print(f"help: {payload.get('documentation_command')}", file=sys.stderr)
        return 2
    if args.command == "version":
        print(VERSION)
        return 0
    try:
        value = args.func(args)
    except BbkError as exc:
        if args.json:
            diagnostic = exc.diagnostic or {
                "schema": "bbk.cli-error.v1",
                "status": "ERROR",
                "code": "BBK_COMMAND_ERROR",
                "error": str(exc),
                "message": str(exc),
                "field": None,
                "received": None,
                "valid_values": [],
                "required": [],
                "example_command": f"bbk {getattr(args, 'command', '')} --help".strip(),
                "documentation_command": f"bbk {getattr(args, 'command', '')} --help".strip(),
                "smallest_next_action": "Inspect the error, correct the exact command input or project state, and rerun the command.",
            }
            diagnostic_status = str(diagnostic.get("status", "ERROR"))
            payload: dict[str, Any] = {
                "schema": "bbk.cli-error.v1",
                "status": "INVALID_ARGUMENT" if diagnostic_status == "INVALID_ARGUMENT" else "ERROR",
                "code": diagnostic.get("code", "BBK_COMMAND_ERROR"),
                "command": diagnostic.get("command", getattr(args, "command", None)),
                "field": diagnostic.get("field"),
                "received": diagnostic.get("received"),
                "valid_values": diagnostic.get("valid_values", []),
                "required": diagnostic.get("required", []),
                "message": diagnostic.get("message", str(exc)),
                "error": str(exc),
                "example_command": diagnostic.get("example_command", "bbk --help"),
                "documentation_command": diagnostic.get("documentation_command", "bbk --help"),
                "smallest_next_action": diagnostic.get("smallest_next_action"),
                "diagnostic": diagnostic,
            }
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        else:
            print(f"bbk: error: {exc}", file=sys.stderr)
            if exc.diagnostic:
                example = exc.diagnostic.get("example_command")
                documentation = exc.diagnostic.get("documentation_command")
                if example:
                    print(f"example: {example}", file=sys.stderr)
                if documentation:
                    print(f"help: {documentation}", file=sys.stderr)
        return 2
    print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) if args.json else human(value))
    if isinstance(value, dict) and (value.get("status") in {"FAIL", "BLOCKED", "ERROR", "DRIFT", "REJECTED"} or value.get("valid") is False):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
