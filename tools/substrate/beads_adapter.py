#!/usr/bin/env python3
"""Single-writer typed projection adapter for Beads coordination state."""
from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from gate_kernel import canonical_digest, canonical_json_bytes
try:
    from .mise_adapter import MiseAdapterError, managed_tool_command, managed_tool_environment
except ImportError:  # pragma: no cover - direct script compatibility
    from mise_adapter import MiseAdapterError, managed_tool_command, managed_tool_environment
from governed_state import all_receipts, append_receipt, initialize


class BeadsAdapterError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


TRANSITIONS = {"CREATE", "START", "BLOCK", "UNBLOCK", "COMPLETE", "FAIL", "ANNOTATE"}
COORDINATION_OPERATIONS = {"ASSIGN", "UPDATE", "INTEGRATE_REQUEST"}

SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+\-]*$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
ORCHESTRATOR_ROLES = {
    "bbk_root_orchestrator",
    "bbk_territory_orchestrator",
    "bbk_worker_orchestrator",
    "bbk_validator_orchestrator",
}
SUMMARY_FORBIDDEN_FRAGMENTS = ("```", "diff --git", "@@ ", "*** Begin Patch", "*** End Patch")
COORDINATION_FIELDS = {
    "schema", "command_id", "operation", "actor", "work_unit", "attempt", "transition",
    "correlation_id", "payload_summary", "expected_revision", "idempotency_key",
    "evidence_refs", "finding_refs", "assignment", "integration",
}
ACTOR_FIELDS = {"role", "session_id", "invocation_id", "binding_ref", "authority_ref", "capability_ref"}
ASSIGNMENT_FIELDS = {
    "worker_binding_ref", "attempt_registration_ref", "assignee_role", "task_name",
    "candidate_ref", "workspace_ref", "jj_change_id", "assignment_digest", "packet_digest",
    "task_input_digest",
}
INTEGRATION_FIELDS = {
    "source_candidate_refs", "target_candidate_ref", "conflict_classification", "requested_route",
    "integration_worker_required", "orchestrator_conflict_resolution_authority", "effect_performed",
}
UPDATE_TRANSITIONS = {"START", "BLOCK", "UNBLOCK", "COMPLETE", "FAIL", "ANNOTATE"}
REQUEST_TRANSITIONS = {"CREATE", "ANNOTATE"}
CONFLICT_CLASSIFICATIONS = {"NONE", "CONTENT_NEUTRAL", "CONTENT_CHANGING", "UNKNOWN"}
INTEGRATION_ROUTES = {"CONTENT_NEUTRAL_INTEGRATION_ADAPTER", "BOUND_INTEGRATION_WORKER"}

STATE_AFTER = {
    "CREATE": "open",
    "START": "in_progress",
    "BLOCK": "blocked",
    "UNBLOCK": "open",
    "COMPLETE": "closed",
    "FAIL": "blocked",
}


def _bd_path(explicit: str | Path) -> Path:
    path = Path(str(explicit)).resolve()
    if not path.is_file() or path.is_symlink() or not os.access(path, os.X_OK):
        raise BeadsAdapterError("SUBSTRATE_BD_UNSAFE_PATH", f"bd executable is not a safe regular executable: {path}")
    return path


def _bd_command(
    workspace: str | Path,
    *,
    bd_path: str | Path | None = None,
) -> tuple[list[str], dict[str, str]]:
    if bd_path is not None:
        executable = _bd_path(bd_path)
        return [str(executable)], {"execution_mode": "EXPLICIT_EXECUTABLE", "bd_path": str(executable)}
    try:
        command, binding = managed_tool_command(
            workspace,
            "bd",
            mise_path_value=os.environ.get("BBK_MISE"),
            environment=os.environ,
        )
    except MiseAdapterError as exc:
        raise BeadsAdapterError(
            "SUBSTRATE_BD_MISE_UNAVAILABLE",
            f"bd must be resolved through mise and canonical [tools] configuration: {exc.code}: {exc.message}",
        ) from exc
    return command, binding


def _run(
    workspace: str | Path,
    arguments: Sequence[str],
    *,
    bd_path: str | Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    command_prefix, _binding = _bd_command(workspace, bd_path=bd_path)
    completed = subprocess.run(
        [*command_prefix, "--sandbox", "--json", "-C", str(Path(workspace).resolve()), *arguments],
        cwd=Path(workspace).resolve(),
        env={
            **managed_tool_environment(os.environ),
            "BD_NON_INTERACTIVE": "1",
            "BEADS_DISABLE_METRICS": "1",
        },
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="backslashreplace",
        timeout=300,
    )
    if check and completed.returncode != 0:
        raise BeadsAdapterError(
            "BEADS_COMMAND_FAILED",
            f"bd {' '.join(arguments)}: {(completed.stderr or completed.stdout).strip() or completed.returncode}",
        )
    return completed


def ensure_backend_initialized(
    workspace: str | Path,
    *,
    bd_path: str | Path | None = None,
) -> dict[str, Any]:
    """Idempotently initialize the project-local Beads substrate.

    BBK configuration already declares Beads auto-initialization.  Spawn-time
    assignment therefore establishes the local coordination database when it
    is absent instead of returning a model-recoverable "no beads project"
    error after the immutable attempt has been registered.
    """
    root = Path(workspace).resolve()
    beads_dir = root / ".beads"
    if beads_dir.is_dir():
        return {"status": "REUSED", "beads_root": str(beads_dir)}
    command_prefix, _binding = _bd_command(root, bd_path=bd_path)
    # Beads 1.1.0 otherwise creates and commits coordination metadata during
    # ``bd init``.  That advances Git HEAD after a jj attempt workspace has
    # already been allocated, making the worker appear to contain unrelated
    # deletions.  ``--setup-exclude`` keeps the Beads database local.  Beads
    # may also materialize a repository-root .gitignore; preserve the exact
    # pre-init bytes and mode so BBK coordination cannot change product state.
    gitignore = root / ".gitignore"
    if gitignore.is_symlink() or (gitignore.exists() and not gitignore.is_file()):
        raise BeadsAdapterError(
            "BEADS_GITIGNORE_UNSAFE",
            f"cannot preserve unsafe repository .gitignore during Beads initialization: {gitignore}",
        )
    gitignore_existed = gitignore.is_file()
    gitignore_bytes = gitignore.read_bytes() if gitignore_existed else b""
    gitignore_mode = gitignore.stat().st_mode if gitignore_existed else None
    try:
        completed = subprocess.run(
            [
                *command_prefix, "--sandbox", "--json", "init", "--init-if-missing",
                "--non-interactive", "--skip-agents", "--skip-hooks", "--setup-exclude",
                "--prefix", "BBK",
            ],
            cwd=root,
            env={
                **managed_tool_environment(os.environ),
                "BD_NON_INTERACTIVE": "1",
                "BEADS_DISABLE_METRICS": "1",
            },
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="backslashreplace",
            timeout=300,
        )
    finally:
        if gitignore_existed:
            gitignore.write_bytes(gitignore_bytes)
            if gitignore_mode is not None:
                os.chmod(gitignore, gitignore_mode)
        else:
            try:
                gitignore.unlink()
            except FileNotFoundError:
                pass
    if completed.returncode != 0:
        raise BeadsAdapterError(
            "BEADS_INITIALIZATION_FAILED",
            (completed.stderr or completed.stdout).strip() or str(completed.returncode),
        )
    if not beads_dir.is_dir():
        raise BeadsAdapterError("BEADS_INITIALIZATION_FAILED", "bd init exited successfully without creating .beads")
    return {
        "status": "CREATED",
        "beads_root": str(beads_dir),
        "exit_code": completed.returncode,
    }


def _validate(command: Mapping[str, Any]) -> None:
    if command.get("schema") != "bbk.beads-command.v1":
        raise BeadsAdapterError("BEADS_COMMAND_SCHEMA_INVALID", "expected bbk.beads-command.v1")
    for field in ("command_id", "work_unit_id", "attempt_id", "transition", "correlation_id", "idempotency_key"):
        if not isinstance(command.get(field), str) or not command[field]:
            raise BeadsAdapterError("BEADS_COMMAND_INVALID", f"{field} is required")
    if command["transition"] not in TRANSITIONS:
        raise BeadsAdapterError("BEADS_TRANSITION_INVALID", f"unsupported transition {command['transition']}")
    revision = command.get("expected_revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        raise BeadsAdapterError("BEADS_EXPECTED_REVISION_INVALID", "expected_revision must be a non-negative integer")
    for field in ("evidence_refs", "finding_refs"):
        value = command.get(field, [])
        if not isinstance(value, list) or len(value) != len(set(value)) or any(not isinstance(item, str) for item in value):
            raise BeadsAdapterError("BEADS_COMMAND_INVALID", f"{field} must be a unique string list")
    projection_payload = command.get("projection_payload", {})
    if not isinstance(projection_payload, Mapping):
        raise BeadsAdapterError("BEADS_COMMAND_INVALID", "projection_payload must be an object")


def _validate_coordination(command: Mapping[str, Any]) -> None:
    if command.get("schema") != "bbk.coordination-command.v1":
        raise BeadsAdapterError("COORDINATION_COMMAND_SCHEMA_INVALID", "expected bbk.coordination-command.v1")
    unknown = sorted(set(command) - COORDINATION_FIELDS)
    if unknown:
        raise BeadsAdapterError(
            "COORDINATION_COMMAND_INVALID",
            f"unsupported coordination fields: {', '.join(unknown)}",
        )
    required = (
        "command_id", "operation", "work_unit", "attempt", "transition", "correlation_id",
        "payload_summary", "expected_revision", "idempotency_key", "actor",
        "evidence_refs", "finding_refs",
    )
    for field in required:
        if field not in command:
            raise BeadsAdapterError("COORDINATION_COMMAND_INVALID", f"{field} is required")
    for field in ("command_id", "work_unit", "attempt", "transition", "correlation_id", "idempotency_key"):
        value = command.get(field)
        if not isinstance(value, str) or not value.strip() or not SAFE_ID_RE.fullmatch(value.strip()):
            raise BeadsAdapterError("COORDINATION_COMMAND_INVALID", f"{field} must be a safe non-empty identifier")
    operation = command.get("operation")
    transition = command.get("transition")
    if operation not in COORDINATION_OPERATIONS:
        raise BeadsAdapterError("COORDINATION_OPERATION_INVALID", f"unsupported operation {operation}")
    if transition not in TRANSITIONS:
        raise BeadsAdapterError("BEADS_TRANSITION_INVALID", f"unsupported transition {transition}")
    if operation == "UPDATE" and transition not in UPDATE_TRANSITIONS:
        raise BeadsAdapterError("COORDINATION_TRANSITION_INVALID", "UPDATE cannot use CREATE")
    if operation in {"ASSIGN", "INTEGRATE_REQUEST"} and transition not in REQUEST_TRANSITIONS:
        raise BeadsAdapterError(
            "COORDINATION_TRANSITION_INVALID",
            f"{operation} must use CREATE for revision zero or ANNOTATE for an existing work unit",
        )
    revision = command.get("expected_revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        raise BeadsAdapterError("BEADS_EXPECTED_REVISION_INVALID", "expected_revision must be a non-negative integer")

    actor = command.get("actor")
    if not isinstance(actor, Mapping):
        raise BeadsAdapterError("COORDINATION_COMMAND_INVALID", "actor must be an object")
    actor_unknown = sorted(set(actor) - ACTOR_FIELDS)
    if actor_unknown:
        raise BeadsAdapterError("COORDINATION_COMMAND_INVALID", f"unsupported actor fields: {', '.join(actor_unknown)}")
    for field in ACTOR_FIELDS:
        if not isinstance(actor.get(field), str) or not str(actor[field]).strip():
            raise BeadsAdapterError("COORDINATION_COMMAND_INVALID", f"actor.{field} is required")
    if actor.get("role") not in ORCHESTRATOR_ROLES:
        raise BeadsAdapterError("COORDINATION_ACTOR_DENIED", f"{actor.get('role')} is not an orchestrator role")

    summary = command.get("payload_summary")
    if not isinstance(summary, str) or not summary.strip() or len(summary.encode("utf-8")) > 512:
        raise BeadsAdapterError(
            "COORDINATION_COMMAND_INVALID",
            "payload_summary must be a non-empty UTF-8 string no larger than 512 bytes",
        )
    if any(character in summary for character in ("\x00", "\r", "\n")) or any(
        fragment in summary for fragment in SUMMARY_FORBIDDEN_FRAGMENTS
    ):
        raise BeadsAdapterError(
            "COORDINATION_PRODUCT_PAYLOAD_FORBIDDEN",
            "payload_summary must contain coordination metadata rather than product content or a patch",
        )
    for field in ("evidence_refs", "finding_refs"):
        value = command.get(field)
        if not isinstance(value, list) or len(value) != len(set(value)) or any(
            not isinstance(item, str) or not item.strip() or len(item.encode("utf-8")) > 512
            for item in value
        ):
            raise BeadsAdapterError("COORDINATION_COMMAND_INVALID", f"{field} must be a unique non-empty string list")

    assignment = command.get("assignment")
    integration = command.get("integration")
    if operation == "ASSIGN":
        if not isinstance(assignment, Mapping) or integration is not None:
            raise BeadsAdapterError("COORDINATION_COMMAND_INVALID", "ASSIGN requires assignment and forbids integration")
        unknown_assignment = sorted(set(assignment) - ASSIGNMENT_FIELDS)
        missing_assignment = sorted(ASSIGNMENT_FIELDS - set(assignment))
        if unknown_assignment or missing_assignment:
            raise BeadsAdapterError(
                "COORDINATION_COMMAND_INVALID",
                f"assignment shape mismatch; missing={missing_assignment}, unsupported={unknown_assignment}",
            )
        for field in ASSIGNMENT_FIELDS:
            value = assignment.get(field)
            if not isinstance(value, str) or not value.strip():
                raise BeadsAdapterError("COORDINATION_COMMAND_INVALID", f"assignment.{field} is required")
        for field in ("attempt_registration_ref", "assignment_digest", "packet_digest", "task_input_digest"):
            if not DIGEST_RE.fullmatch(str(assignment[field])):
                raise BeadsAdapterError("COORDINATION_COMMAND_INVALID", f"assignment.{field} must be sha256:<64 hex>")
    elif operation == "INTEGRATE_REQUEST":
        if not isinstance(integration, Mapping) or assignment is not None:
            raise BeadsAdapterError(
                "COORDINATION_COMMAND_INVALID",
                "INTEGRATE_REQUEST requires integration and forbids assignment",
            )
        unknown_integration = sorted(set(integration) - INTEGRATION_FIELDS)
        missing_integration = sorted(INTEGRATION_FIELDS - set(integration))
        if unknown_integration or missing_integration:
            raise BeadsAdapterError(
                "COORDINATION_COMMAND_INVALID",
                f"integration shape mismatch; missing={missing_integration}, unsupported={unknown_integration}",
            )
        sources = integration.get("source_candidate_refs")
        if not isinstance(sources, list) or not sources or len(sources) != len(set(sources)) or any(
            not isinstance(item, str) or not item.strip() for item in sources
        ):
            raise BeadsAdapterError("COORDINATION_COMMAND_INVALID", "integration.source_candidate_refs is invalid")
        if not isinstance(integration.get("target_candidate_ref"), str) or not integration["target_candidate_ref"].strip():
            raise BeadsAdapterError("COORDINATION_COMMAND_INVALID", "integration.target_candidate_ref is required")
        if integration["target_candidate_ref"] in sources:
            raise BeadsAdapterError("COORDINATION_COMMAND_INVALID", "integration target cannot also be a source")
        if integration.get("conflict_classification") not in CONFLICT_CLASSIFICATIONS:
            raise BeadsAdapterError("COORDINATION_COMMAND_INVALID", "integration conflict classification is invalid")
        if integration.get("requested_route") not in INTEGRATION_ROUTES:
            raise BeadsAdapterError("COORDINATION_COMMAND_INVALID", "integration requested route is invalid")
        worker_required = integration.get("conflict_classification") in {"CONTENT_CHANGING", "UNKNOWN"}
        expected_route = "BOUND_INTEGRATION_WORKER" if worker_required else "CONTENT_NEUTRAL_INTEGRATION_ADAPTER"
        if integration.get("integration_worker_required") is not worker_required or integration.get("requested_route") != expected_route:
            raise BeadsAdapterError("COORDINATION_COMMAND_INVALID", "integration route does not match conflict classification")
        if integration.get("orchestrator_conflict_resolution_authority") != "DENIED":
            raise BeadsAdapterError("COORDINATION_COMMAND_INVALID", "orchestrator conflict resolution authority must be DENIED")
        if integration.get("effect_performed") != "REQUEST_RECORDED_ONLY":
            raise BeadsAdapterError("COORDINATION_COMMAND_INVALID", "integration requests cannot claim a candidate effect")
    elif assignment is not None or integration is not None:
        raise BeadsAdapterError("COORDINATION_COMMAND_INVALID", "UPDATE forbids assignment and integration payloads")


def _command_receipts(project_root: str | Path) -> list[dict[str, Any]]:
    return [item for item in all_receipts(project_root) if item.get("receipt_kind") == "BEADS_COMMAND"]


def _coordination_receipts(project_root: str | Path) -> list[dict[str, Any]]:
    return [item for item in all_receipts(project_root) if item.get("receipt_kind") == "COORDINATION_COMMAND"]


def _failure_receipts(project_root: str | Path, receipt_kind: str) -> list[dict[str, Any]]:
    return [item for item in all_receipts(project_root) if item.get("receipt_kind") == receipt_kind]


def _find_failed(
    project_root: str | Path,
    receipt_kind: str,
    idempotency_key: str,
) -> dict[str, Any] | None:
    matches = [
        item for item in _failure_receipts(project_root, receipt_kind)
        if item.get("content", {}).get("command", {}).get("idempotency_key") == idempotency_key
    ]
    if len(matches) > 1:
        raise BeadsAdapterError(
            "BEADS_FAILURE_STATE_CORRUPT",
            f"duplicate failed Beads command idempotency key {idempotency_key}",
        )
    return matches[0] if matches else None


def _append_failure(
    project_root: str | Path,
    receipt_kind: str,
    command: Mapping[str, Any],
    error: BeadsAdapterError,
) -> dict[str, Any]:
    stable = _stable_command(command)
    content = {
        "schema": "bbk.beads-failure.v1",
        "command": stable,
        "error": {"code": error.code, "message": error.message},
        "effect_state": "UNKNOWN_OR_NOT_APPLIED",
        "correction": "Reconcile backend state, then retry only with a corrected idempotency key.",
    }
    receipt_id = f"sha256:{canonical_digest({'receipt_kind': receipt_kind, 'content': content})}"
    receipt, _ = append_receipt(project_root, receipt_kind, content, receipt_id=receipt_id)
    return receipt


def _stable_command(command: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(canonical_json_bytes(dict(command)).decode("utf-8"))


def current_revision(project_root: str | Path, work_unit_id: str) -> int:
    return sum(
        1
        for receipt in _command_receipts(project_root)
        if receipt.get("content", {}).get("command", {}).get("work_unit_id") == work_unit_id
    )


def find_idempotent(project_root: str | Path, idempotency_key: str) -> dict[str, Any] | None:
    matches = [
        item
        for item in _command_receipts(project_root)
        if item.get("content", {}).get("command", {}).get("idempotency_key") == idempotency_key
    ]
    if len(matches) > 1:
        raise BeadsAdapterError("BEADS_IDEMPOTENCY_STATE_CORRUPT", f"duplicate canonical idempotency key {idempotency_key}")
    return matches[0] if matches else None


def find_coordination_idempotent(project_root: str | Path, idempotency_key: str) -> dict[str, Any] | None:
    matches = [
        item
        for item in _coordination_receipts(project_root)
        if item.get("content", {}).get("command", {}).get("idempotency_key") == idempotency_key
    ]
    if len(matches) > 1:
        raise BeadsAdapterError(
            "COORDINATION_IDEMPOTENCY_STATE_CORRUPT",
            f"duplicate canonical coordination idempotency key {idempotency_key}",
        )
    return matches[0] if matches else None


@contextlib.contextmanager
def single_writer(project_root: str | Path) -> Iterator[None]:
    """Acquire the canonical Beads writer with bounded serialization.

    Concurrent orchestrator preparation is expected; it must serialize the
    coordination journal rather than fail immediately and tempt a model to
    regenerate an attempt.  A bounded timeout remains fail-closed for a truly
    stuck owner.
    """
    root = initialize(project_root)
    lock = root / "locks" / "beads-single-writer.lock"
    try:
        wait_seconds = float(os.environ.get("BBK_BEADS_WRITER_WAIT_SECONDS", "30"))
        poll_seconds = float(os.environ.get("BBK_BEADS_WRITER_POLL_SECONDS", "0.05"))
    except ValueError as exc:
        raise BeadsAdapterError("BEADS_SINGLE_WRITER_CONFIG_INVALID", "writer wait/poll values must be numeric") from exc
    if wait_seconds < 0 or poll_seconds <= 0:
        raise BeadsAdapterError("BEADS_SINGLE_WRITER_CONFIG_INVALID", "writer wait must be non-negative and poll positive")
    deadline = time.monotonic() + wait_seconds
    fd = None
    while fd is None:
        try:
            fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            if time.monotonic() >= deadline:
                raise BeadsAdapterError(
                    "BEADS_SINGLE_WRITER_TIMEOUT",
                    f"timed out after {wait_seconds:g}s waiting for BBK Beads writer {lock}",
                ) from exc
            time.sleep(min(poll_seconds, max(0.0, deadline - time.monotonic())))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(json.dumps({"pid": os.getpid(), "acquired_monotonic": time.monotonic()}, sort_keys=True))
            stream.flush()
            os.fsync(stream.fileno())
        yield
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def _summary_payload(command: Mapping[str, Any]) -> str:
    payload = {
        "bbk_projection": True,
        "command_id": command["command_id"],
        "attempt_id": command["attempt_id"],
        "correlation_id": command["correlation_id"],
        "evidence_refs": command.get("evidence_refs", []),
        "finding_refs": command.get("finding_refs", []),
        "projection_payload": command.get("projection_payload", {}),
        "summary": command.get("summary", ""),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _apply_backend(
    workspace: str | Path,
    command: Mapping[str, Any],
    *,
    bd_path: str | Path | None = None,
) -> dict[str, Any]:
    transition = command["transition"]
    issue_id = command["work_unit_id"]
    summary = str(command.get("summary") or f"BBK work unit {issue_id}")
    note = _summary_payload(command)
    if transition == "CREATE":
        arguments: tuple[str, ...] = (
            "create", "--id", issue_id, "--force", "--title", summary,
            "--description", "BBK coordination projection; canonical execution semantics remain in BBK receipts.",
            "--type", "task", "--append-notes", note,
        )
        assignment = command.get("projection_payload", {}).get("assignment", {})
        assignee = assignment.get("assignee_role") if isinstance(assignment, Mapping) else None
        if isinstance(assignee, str) and assignee:
            arguments = (*arguments, "--assignee", assignee)
    elif transition == "START":
        arguments = ("update", issue_id, "--status", "in_progress", "--append-notes", note)
    elif transition == "BLOCK":
        arguments = ("update", issue_id, "--status", "blocked", "--append-notes", note)
    elif transition == "UNBLOCK":
        arguments = ("update", issue_id, "--status", "open", "--append-notes", note)
    elif transition == "COMPLETE":
        arguments = ("close", issue_id, "--reason", summary)
    elif transition == "FAIL":
        arguments = ("update", issue_id, "--status", "blocked", "--append-notes", f"FAIL {note}")
    elif transition == "ANNOTATE" and command.get("projection_payload", {}).get("operation") == "ASSIGN":
        assignment = command.get("projection_payload", {}).get("assignment", {})
        assignee = assignment.get("assignee_role") if isinstance(assignment, Mapping) else None
        arguments = (
            "update", issue_id,
            *(('--assignee', str(assignee)) if isinstance(assignee, str) and assignee else ()),
            "--append-notes", note,
        )
    else:
        arguments = ("comment", issue_id, note)
    completed = _run(workspace, arguments, bd_path=bd_path)
    try:
        output = json.loads(completed.stdout) if completed.stdout.strip() else None
    except json.JSONDecodeError as exc:
        raise BeadsAdapterError("BEADS_OUTPUT_INVALID", f"bd returned invalid JSON: {exc}") from exc
    return {
        "exit_code": completed.returncode,
        "issue_id": issue_id,
        "transition": transition,
        "projected_status": STATE_AFTER.get(transition),
        "bd_result": output,
    }


def execute(
    project_root: str | Path,
    beads_workspace: str | Path,
    command: Mapping[str, Any],
    *,
    bd_path: str | Path | None = None,
) -> dict[str, Any]:
    """Validate, serialize, execute, and receipt one typed projection command."""
    _validate(command)
    stable = _stable_command(command)
    failed = _find_failed(project_root, "BEADS_COMMAND_FAILURE", command["idempotency_key"])
    if failed:
        prior_command = failed.get("content", {}).get("command")
        if prior_command != stable:
            raise BeadsAdapterError(
                "BEADS_IDEMPOTENCY_COLLISION",
                f"idempotency key {command['idempotency_key']} was used for different failed command content",
            )
        raise BeadsAdapterError(
            "BEADS_FAILED_ATTEMPT_REQUIRES_CORRECTION",
            f"failed Beads command {command['idempotency_key']} requires backend reconciliation before retry",
        )
    prior = find_idempotent(project_root, command["idempotency_key"])
    if prior:
        prior_command = prior.get("content", {}).get("command")
        if prior_command != stable:
            raise BeadsAdapterError(
                "BEADS_IDEMPOTENCY_COLLISION",
                f"idempotency key {command['idempotency_key']} was used for different command content",
            )
        return {**prior["content"]["result"], "idempotent_reuse": True, "receipt_id": prior["receipt_id"]}

    revision = current_revision(project_root, command["work_unit_id"])
    if command["expected_revision"] != revision:
        raise BeadsAdapterError(
            "BEADS_EXPECTED_REVISION_MISMATCH",
            f"work unit {command['work_unit_id']} is revision {revision}, not {command['expected_revision']}",
        )
    if revision == 0 and command["transition"] != "CREATE":
        raise BeadsAdapterError("BEADS_CREATE_REQUIRED", "the first transition for a work unit must be CREATE")
    if revision > 0 and command["transition"] == "CREATE":
        raise BeadsAdapterError("BEADS_ALREADY_CREATED", f"work unit {command['work_unit_id']} already has canonical projection history")

    with single_writer(project_root):
        # Recheck after acquiring the lock to close the race window.
        if current_revision(project_root, command["work_unit_id"]) != revision:
            raise BeadsAdapterError("BEADS_EXPECTED_REVISION_MISMATCH", "revision changed while waiting for writer lock")
        try:
            ensure_backend_initialized(beads_workspace, bd_path=bd_path)
            result = _apply_backend(beads_workspace, stable, bd_path=bd_path)
        except BeadsAdapterError as exc:
            _append_failure(project_root, "BEADS_COMMAND_FAILURE", stable, exc)
            raise
        result.update({
            "schema": "bbk.beads-command-result.v1",
            "status": "PASS",
            "revision_before": revision,
            "revision_after": revision + 1,
            "idempotent_reuse": False,
        })
        receipt_id = f"sha256:{canonical_digest({'command': stable, 'result': result})}"
        receipt, _ = append_receipt(
            project_root,
            "BEADS_COMMAND",
            {"command": stable, "result": result},
            receipt_id=receipt_id,
        )
    rebuild_projection(project_root)
    return {**result, "receipt_id": receipt["receipt_id"]}


def execute_coordination(
    project_root: str | Path,
    beads_workspace: str | Path,
    command: Mapping[str, Any],
    *,
    bd_path: str | Path | None = None,
) -> dict[str, Any]:
    """Project one IF-007 coordination command through the single Beads writer.

    The semantic request and the Beads effect are recorded separately.  A
    failed backend projection may therefore leave a truthful immutable request
    record, but it can never leave a success receipt without the corresponding
    adapter receipt.  Exact retries reuse both records and do not repeat the
    backend effect.
    """
    _validate_coordination(command)
    stable = _stable_command(command)
    failed = _find_failed(project_root, "COORDINATION_COMMAND_FAILURE", stable["idempotency_key"])
    if failed:
        prior_command = failed.get("content", {}).get("command")
        if prior_command != stable:
            raise BeadsAdapterError(
                "COORDINATION_IDEMPOTENCY_COLLISION",
                f"idempotency key {stable['idempotency_key']} was used for different failed coordination content",
            )
        raise BeadsAdapterError(
            "COORDINATION_FAILED_ATTEMPT_REQUIRES_CORRECTION",
            f"failed coordination command {stable['idempotency_key']} requires backend reconciliation before retry",
        )
    prior = find_coordination_idempotent(project_root, stable["idempotency_key"])
    if prior:
        prior_command = prior.get("content", {}).get("command")
        if prior_command != stable:
            raise BeadsAdapterError(
                "COORDINATION_IDEMPOTENCY_COLLISION",
                f"idempotency key {stable['idempotency_key']} was used for different coordination content",
            )
        semantic_record = prior
    else:
        semantic_record_id = f"sha256:{canonical_digest({'schema': 'bbk.coordination-command-record.v1', 'command': stable})}"
        semantic_record, _ = append_receipt(
            project_root,
            "COORDINATION_COMMAND",
            {"schema": "bbk.coordination-command-record.v1", "command": stable},
            receipt_id=semantic_record_id,
        )

    backend_command = {
        "schema": "bbk.beads-command.v1",
        "command_id": stable["command_id"],
        "work_unit_id": stable["work_unit"],
        "attempt_id": stable["attempt"],
        "transition": stable["transition"],
        "correlation_id": stable["correlation_id"],
        "expected_revision": stable["expected_revision"],
        "idempotency_key": stable["idempotency_key"],
        "summary": stable["payload_summary"],
        "evidence_refs": stable.get("evidence_refs", []),
        "finding_refs": stable.get("finding_refs", []),
        "projection_payload": {
            "operation": stable["operation"],
            "actor": stable["actor"],
            **({"assignment": stable["assignment"]} if "assignment" in stable else {}),
            **({"integration": stable["integration"]} if "integration" in stable else {}),
        },
    }
    try:
        backend_result = execute(project_root, beads_workspace, backend_command, bd_path=bd_path)
    except BeadsAdapterError as exc:
        _append_failure(project_root, "COORDINATION_COMMAND_FAILURE", stable, exc)
        raise
    result_core = {
        "schema": "bbk.beads-projection-receipt.v1",
        "status": "PASS",
        "operation": stable["operation"],
        "subject": {"work_unit": stable["work_unit"], "attempt": stable["attempt"]},
        "previous_revision": backend_result["revision_before"],
        "new_revision": backend_result["revision_after"],
        "bd_receipt": backend_result["receipt_id"],
        "semantic_record_ref": semantic_record["receipt_id"],
        "backend": {
            "issue_id": backend_result["issue_id"],
            "transition": backend_result["transition"],
            "projected_status": backend_result.get("projected_status"),
            "exit_code": backend_result["exit_code"],
        },
    }
    projection_id = f"sha256:{canonical_digest(result_core)}"
    result_value = {
        **result_core,
        "projection_id": projection_id,
        "idempotent_reuse": bool(prior) or bool(backend_result.get("idempotent_reuse")),
    }
    projection_record, _ = append_receipt(
        project_root,
        "BEADS_PROJECTION",
        {
            "schema": "bbk.beads-projection-record.v1",
            "command_ref": semantic_record["receipt_id"],
            "backend_receipt_ref": backend_result["receipt_id"],
            "result": {**result_value, "idempotent_reuse": False},
        },
        receipt_id=projection_id,
    )
    return {**result_value, "projection_id": projection_record["receipt_id"]}


def rebuild_projection(project_root: str | Path) -> dict[str, Any]:
    """Regenerate BBK's Beads status projection from canonical command receipts."""
    state: dict[str, dict[str, Any]] = {}
    receipts = sorted(_command_receipts(project_root), key=lambda item: item.get("recorded_at", ""))
    for receipt in receipts:
        content = receipt.get("content", {})
        command = content.get("command", {})
        result = content.get("result", {})
        work_unit = command.get("work_unit_id")
        if not work_unit:
            continue
        previous = state.get(work_unit, {"revision": 0, "status": None, "commands": []})
        status = result.get("projected_status") or previous["status"]
        state[work_unit] = {
            "revision": result.get("revision_after", previous["revision"] + 1),
            "status": status,
            "attempt_id": command.get("attempt_id"),
            "last_transition": command.get("transition"),
            "commands": [*previous["commands"], receipt.get("receipt_id")],
        }
    projection = {
        "schema": "bbk.beads-projection.v1",
        "authority": "NON_AUTHORITATIVE_PROJECTION",
        "work_units": dict(sorted(state.items())),
    }
    root = initialize(project_root) / "projections"
    path = root / "beads.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(canonical_json_bytes(projection) + b"\n")
    os.replace(temporary, path)
    return projection


def read_backend_issue(
    beads_workspace: str | Path,
    work_unit_id: str,
    *,
    bd_path: str | Path | None = None,
) -> Any:
    completed = _run(beads_workspace, ("show", work_unit_id), bd_path=bd_path)
    return json.loads(completed.stdout)


__all__ = [
    "BeadsAdapterError", "current_revision", "execute", "execute_coordination",
    "find_coordination_idempotent", "find_idempotent", "read_backend_issue", "rebuild_projection",
    "single_writer",
]
