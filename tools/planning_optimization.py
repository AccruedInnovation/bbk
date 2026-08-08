#!/usr/bin/env python3
"""Rolling-wave planning, routine contracts, coverage, and plan transactions."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shutil
import stat
import tempfile
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence


class PlanningOptimizationError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(f"{code}: {message}")


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def utc(value: str | None = None) -> str:
    if value:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise PlanningOptimizationError("BBK-PLAN-006", "timestamp must include timezone")
        return parsed.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def reference(value: Mapping[str, Any] | str, *, default_id: str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        result = dict(value)
        if not all(key in result for key in ("id", "revision", "digest")):
            result.setdefault("id", default_id)
            result.setdefault("revision", 1)
            result.setdefault("digest", digest(value))
        return result
    path = Path(value)
    if path.is_file():
        data = path.read_bytes()
        return {"id": default_id, "revision": 1, "digest": hashlib.sha256(data).hexdigest(), "path": path.as_posix()}
    return {"id": str(value) or default_id, "revision": 1, "digest": hashlib.sha256(str(value).encode()).hexdigest(), "path": None}


def validate_planning_readiness(value: Mapping[str, Any]) -> None:
    readiness = set(value.get("readiness") or [])
    frontier = value.get("frontier_ref")
    if value.get("execution_admissible") is True:
        if "FRONTIER_READY" not in readiness:
            raise PlanningOptimizationError("BBK-PLAN-001", "execution admission requires FRONTIER_READY")
        if not isinstance(frontier, Mapping):
            raise PlanningOptimizationError("BBK-PLAN-002", "execution admission requires frontier_ref")
    if "FRONTIER_READY" in readiness:
        if "ROADMAP_READY" not in readiness:
            raise PlanningOptimizationError("BBK-PLAN-003", "FRONTIER_READY requires ROADMAP_READY")
        if not isinstance(frontier, Mapping):
            raise PlanningOptimizationError("BBK-PLAN-002", "FRONTIER_READY requires frontier_ref")
    if "FULLY_COMPILED" in readiness and not {"ROADMAP_READY", "FRONTIER_READY"}.issubset(readiness):
        raise PlanningOptimizationError("BBK-PLAN-004", "FULLY_COMPILED requires roadmap and frontier readiness")
    if value.get("planning_mode") == "FULL_GOVERNED" and not value.get("full_compilation_trigger"):
        raise PlanningOptimizationError("BBK-PLAN-005", "FULL_GOVERNED requires explicit full-compilation trigger")


def build_planning_readiness(
    *, roadmap: Mapping[str, Any] | str, frontier: Mapping[str, Any] | str | None,
    coverage: Mapping[str, Any] | str, planning_mode: str = "FAST_CONTINUATION",
    architecture_mode: str = "ADOPT_AND_GAP", deferred_refinements: Sequence[Mapping[str, Any]] = (),
    fully_compiled: bool = False, full_compilation_trigger: str | None = None,
) -> dict[str, Any]:
    readiness = ["ROADMAP_READY"]
    frontier_ref = reference(frontier, default_id="frontier") if frontier is not None else None
    if frontier_ref is not None:
        readiness.append("FRONTIER_READY")
    if fully_compiled:
        readiness.append("FULLY_COMPILED")
    result = {
        "schema": "bbk.planning-readiness.v1",
        "planning_mode": planning_mode,
        "architecture_mode": architecture_mode,
        "readiness": readiness,
        "roadmap_ref": reference(roadmap, default_id="roadmap"),
        "frontier_ref": frontier_ref,
        "coverage_ref": reference(coverage, default_id="coverage"),
        "deferred_refinements": [dict(item) for item in deferred_refinements],
        "execution_admissible": frontier_ref is not None,
        "full_compilation_trigger": full_compilation_trigger,
        "invalidation_keys": [
            f"roadmap:{reference(roadmap, default_id='roadmap')['digest']}",
            *( [f"frontier:{frontier_ref['digest']}"] if frontier_ref else []),
            f"coverage:{reference(coverage, default_id='coverage')['digest']}",
        ],
    }
    validate_planning_readiness(result)
    return result


def migrate_legacy_planning_readiness(
    legacy: Mapping[str, Any], *, roadmap: Mapping[str, Any] | str,
    frontier: Mapping[str, Any] | str, coverage: Mapping[str, Any] | str,
    authority_ref: str, generated_at: str | None = None,
) -> dict[str, Any]:
    """Project one immutable fully detailed legacy plan into Alpha.17 readiness.

    The legacy object is never modified.  The returned successor record binds
    its canonical digest and includes a BASELINE_ADVANCED migration anchor so a
    new event stream may begin without replaying historical micro-carriers.
    """
    source_digest = digest(legacy)
    authority_mode = str(legacy.get("planning_mode") or legacy.get("governance_mode") or legacy.get("authority_mode") or "").upper()
    full_governed = authority_mode in {"FULL_GOVERNED", "FULL", "GOVERNED_FULL"} or bool(legacy.get("full_governed"))
    planning_mode = "FULL_GOVERNED" if full_governed else "STANDARD"
    readiness = build_planning_readiness(
        roadmap=roadmap, frontier=frontier, coverage=coverage,
        planning_mode=planning_mode,
        architecture_mode=str(legacy.get("architecture_mode") or "ADOPT_AND_GAP"),
        deferred_refinements=(), fully_compiled=True,
        full_compilation_trigger=("legacy-authority-required-full-governance" if full_governed else None),
    )
    observed = utc(generated_at)
    readiness["migration"] = {
        "source_schema": str(legacy.get("schema") or "legacy-planning-artifact"),
        "source_id": str(legacy.get("id") or legacy.get("plan_id") or "legacy-plan"),
        "source_digest": source_digest,
        "source_preserved_immutable": True,
        "projection_kind": "SUCCESSOR_COMPATIBILITY_PROJECTION",
        "migrated_at": observed,
    }
    readiness["invalidation_keys"].append(f"legacy-source:{source_digest}")
    anchor = {
        "event_type": "BASELINE_ADVANCED",
        "subject_ref": readiness["roadmap_ref"]["id"],
        "authority_ref": authority_ref,
        "predecessor_refs": [],
        "payload": {
            "migration_anchor": True,
            "legacy_source_digest": source_digest,
            "readiness_digest": digest(readiness),
            "projection": "roadmap",
        },
        "created_at": observed,
    }
    return {
        "schema": "bbk.planning-readiness-migration.v1",
        "status": "PASS",
        "legacy_source_digest": source_digest,
        "legacy_source_modified": False,
        "readiness": readiness,
        "migration_anchor_event": anchor,
    }


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def worker_design_trigger(work_unit: Mapping[str, Any]) -> dict[str, Any] | None:
    explicit = work_unit.get("worker_design_trigger")
    if isinstance(explicit, Mapping):
        result = dict(explicit)
        result.setdefault("schema", "bbk.worker-design-trigger.v1")
        result.setdefault("work_unit_ref", str(work_unit.get("id") or work_unit.get("work_unit_id") or "unknown"))
        return result
    owners = work_unit.get("mutation_owners")
    if isinstance(owners, list) and len({str(item) for item in owners}) > 1:
        return {
            "schema": "bbk.worker-design-trigger.v1",
            "work_unit_ref": str(work_unit.get("id") or work_unit.get("work_unit_id") or "unknown"),
            "trigger": "CROSS_INTERFACE_MULTI_OWNER_MUTATION",
            "material_ambiguity": "The WorkUnit names more than one mutation owner and has no positive serialization contract.",
            "why_template_is_insufficient": "The routine generator requires one owner or a pre-existing exact serialization policy.",
            "required_designer_output": "One bounded ownership/serialization and recovery contract for the named surfaces.",
            "unaffected_work_may_continue": True,
        }
    effects = set(str(item) for item in (work_unit.get("effect_classes") or []))
    if effects & {"DESTRUCTIVE", "IRREVERSIBLE", "PRIVILEGED", "SECRET_BEARING"}:
        return {
            "schema": "bbk.worker-design-trigger.v1",
            "work_unit_ref": str(work_unit.get("id") or work_unit.get("work_unit_id") or "unknown"),
            "trigger": "UNUSUAL_EFFECTS_OR_RECOVERY",
            "material_ambiguity": "The WorkUnit includes unusual or consequential effect classes requiring an exact recovery contract.",
            "why_template_is_insufficient": "The routine workspace-only template cannot establish the additional effect and recovery controls.",
            "required_designer_output": "A bounded effect, safeguard, rollback, and evidence contract.",
            "unaffected_work_may_continue": True,
        }
    return None


def generate_worker_contract(
    work_unit: Mapping[str, Any], authority: Mapping[str, Any], workspace_receipt: Mapping[str, Any],
    profile_constraints: Mapping[str, Any], *, return_contract: str = "bbk.worker-return.v2",
) -> dict[str, Any]:
    trigger = worker_design_trigger(work_unit)
    if trigger:
        return {"schema": "bbk.routine-worker-contract-generation.v1", "status": "SPECIALIST_REQUIRED", "trigger": trigger}
    work_id = str(work_unit.get("id") or work_unit.get("work_unit_id") or "")
    if not work_id:
        raise PlanningOptimizationError("BBK-CONTRACT-001", "WorkUnit has no stable identity")
    scope = work_unit.get("scope") or work_unit.get("path_prefixes") or work_unit.get("owned_paths") or []
    if isinstance(scope, str):
        scope = [scope]
    checks = work_unit.get("completion_checks") or work_unit.get("checks") or []
    if isinstance(checks, str):
        checks = [checks]
    owned_roots = list(workspace_receipt.get("owned_roots") or scope)
    mutation_owner = str(workspace_receipt.get("mutation_owner") or work_unit.get("mutation_owner") or "")
    if not owned_roots or not mutation_owner:
        raise PlanningOptimizationError("BBK-CONTRACT-002", "workspace/mutation ownership is incomplete")
    contract = {
        "schema": "bbk.routine-worker-contract.v1",
        "contract_id": f"worker-contract:{work_id}:{digest({'w':work_unit,'a':authority,'r':workspace_receipt,'p':profile_constraints})[:16]}",
        "work_unit_ref": work_id,
        "subject_revision": work_unit.get("revision", 1),
        "scope": [str(item) for item in scope],
        "prohibited_scope": [str(item) for item in work_unit.get("prohibited_scope") or []],
        "authority_ref": str(authority.get("id") or authority.get("authority_ref") or digest(authority)),
        "allowed_effects": [str(item) for item in authority.get("allowed_effects") or work_unit.get("effect_classes") or ["WORKSPACE_IMPLEMENTATION"]],
        "denied_effects": [str(item) for item in authority.get("denied_effects") or ["EXTERNAL_EXECUTION"]],
        "workspace_receipt_ref": str(workspace_receipt.get("receipt_id") or digest(workspace_receipt)),
        "owned_roots": owned_roots,
        "mutation_owner": mutation_owner,
        "serialization_state": str(workspace_receipt.get("serialization_state") or "EXCLUSIVE"),
        "required_inputs": [str(item) for item in work_unit.get("required_inputs") or []],
        "stable_interfaces": [str(item) for item in work_unit.get("stable_interfaces") or []],
        "profile_constraints": dict(profile_constraints),
        "expected_outputs": [str(item) for item in work_unit.get("expected_outputs") or work_unit.get("outputs") or []],
        "focused_checks": [str(item) for item in work_unit.get("focused_checks") or []],
        "completion_checks": [str(item) for item in checks],
        "cleanup": dict(work_unit.get("cleanup") or {"state": "COMPLETE_REQUIRED"}),
        "checkpoint": dict(work_unit.get("checkpoint") or {"required": True}),
        "return_contract": return_contract,
        "return_route": str(work_unit.get("return_route") or "invoking-parent"),
        "reusable_receipts": [str(item) for item in work_unit.get("reusable_receipts") or []],
        "forbidden_duplicate_checks": [str(item) for item in work_unit.get("forbidden_duplicate_checks") or []],
        "invalidation_keys": [f"work-unit:{digest(work_unit)}", f"authority:{digest(authority)}", f"workspace:{digest(workspace_receipt)}", f"profile:{digest(profile_constraints)}"],
    }
    return {"schema": "bbk.routine-worker-contract-generation.v1", "status": "GENERATED", "contract": contract, "trigger": None}


def verification_design_trigger(criterion: Mapping[str, Any], profile_template: Mapping[str, Any]) -> dict[str, Any] | None:
    explicit = criterion.get("verification_design_trigger")
    if isinstance(explicit, Mapping):
        result = dict(explicit); result.setdefault("schema", "bbk.verification-design-trigger.v1")
        result.setdefault("subject_ref", str(criterion.get("id") or "unknown")); return result
    if criterion.get("method_ambiguity"):
        return {
            "schema": "bbk.verification-design-trigger.v1",
            "subject_ref": str(criterion.get("id") or "unknown"),
            "trigger": "METHOD_AMBIGUITY",
            "material_ambiguity": str(criterion["method_ambiguity"]),
            "why_template_is_insufficient": "The selected profile template does not deterministically select one sufficient method.",
            "required_designer_output": "Select the minimum sufficient method, environment, evidence, and independence contract.",
            "unaffected_work_may_continue": True,
        }
    if not profile_template.get("method") and not profile_template.get("methods"):
        return {
            "schema": "bbk.verification-design-trigger.v1",
            "subject_ref": str(criterion.get("id") or "unknown"),
            "trigger": "METHOD_AMBIGUITY",
            "material_ambiguity": "No profile-owned verification method is available for the criterion.",
            "why_template_is_insufficient": "The routine assertion generator has no selected evidence-producing method.",
            "required_designer_output": "Define one bounded method and its evidence and independence requirements.",
            "unaffected_work_may_continue": True,
        }
    return None


def generate_assertion_contract(criterion: Mapping[str, Any], profile_template: Mapping[str, Any], *, candidate_stage: str) -> dict[str, Any]:
    trigger = verification_design_trigger(criterion, profile_template)
    if trigger:
        return {"schema": "bbk.routine-assertion-contract-generation.v1", "status": "SPECIALIST_REQUIRED", "trigger": trigger}
    criterion_id = str(criterion.get("id") or "")
    if not criterion_id:
        raise PlanningOptimizationError("BBK-ASSERT-001", "acceptance criterion has no stable identity")
    method = profile_template.get("method") or (profile_template.get("methods") or [None])[0]
    contract = {
        "schema": "bbk.routine-assertion-contract.v1",
        "assertion_id": f"assertion:{criterion_id}:{digest({'c':criterion,'p':profile_template,'s':candidate_stage})[:16]}",
        "criterion_ref": criterion_id,
        "subject": criterion.get("subject") or criterion.get("statement") or criterion_id,
        "method": method,
        "candidate_stage": candidate_stage,
        "environment": profile_template.get("environment") or {},
        "evidence": profile_template.get("evidence") or [],
        "expected": criterion.get("expected") or criterion.get("acceptance") or True,
        "disposition": profile_template.get("disposition") or "REQUIRED",
        "independence": profile_template.get("independence") or "INLINE",
        "invalidation_keys": [f"criterion:{digest(criterion)}", f"profile-template:{digest(profile_template)}", f"stage:{candidate_stage}"],
    }
    return {"schema": "bbk.routine-assertion-contract-generation.v1", "status": "GENERATED", "contract": contract, "trigger": None}


def validate_project_coverage(value: Mapping[str, Any]) -> None:
    seen: set[str] = set()
    root_claims = {str(item) for item in value.get("claims_not_established") or []}
    for capability in value.get("capabilities") or []:
        cid = str(capability.get("id") or "")
        if cid in seen:
            raise PlanningOptimizationError("BBK-COVER-001", f"duplicate capability {cid}")
        seen.add(cid)
        if capability.get("status") == "COMPLETED":
            if capability.get("remaining_scope"):
                raise PlanningOptimizationError("BBK-COVER-002", f"completed capability {cid} has remaining scope")
            if capability.get("unmet_claims"):
                raise PlanningOptimizationError("BBK-COVER-003", f"completed capability {cid} has unmet claims")
        for claim in capability.get("unmet_claims") or []:
            if str(claim) not in root_claims:
                raise PlanningOptimizationError("BBK-COVER-004", f"unmet claim {claim} missing from root projection")


def coverage_return_projection(value: Mapping[str, Any]) -> dict[str, Any]:
    validate_project_coverage(value)
    by_status = {key: [] for key in ("COMPLETED", "PARTIAL", "NOT_STARTED", "BLOCKED", "OUT_OF_SCOPE")}
    for item in value.get("capabilities") or []:
        by_status[str(item.get("status"))].append(str(item.get("id")))
    return {
        "delivered_scope": list(value.get("delivered_scope") or []),
        "master_graph_coverage_ref": value.get("master_graph_ref"),
        "capabilities_completed": by_status["COMPLETED"],
        "capabilities_partial": by_status["PARTIAL"],
        "capabilities_not_started": by_status["NOT_STARTED"],
        "capabilities_blocked": by_status["BLOCKED"],
        "capabilities_out_of_scope": by_status["OUT_OF_SCOPE"],
        "claims_not_established": list(value.get("claims_not_established") or []),
        "next_executable_frontier": value.get("next_executable_frontier"),
        "project_complete": bool(value.get("capabilities")) and all(item.get("status") in {"COMPLETED", "OUT_OF_SCOPE"} for item in value.get("capabilities") or []),
    }


def issue_workspace_receipt(*, repository_ref: str, baseline_ref: str, protected_tree_state: str,
                            known_unrelated_dirt: Sequence[str], owned_roots: Sequence[str], mutation_owner: str,
                            serialization_state: str, issued_at: str | None = None) -> dict[str, Any]:
    if not owned_roots or not mutation_owner:
        raise PlanningOptimizationError("BBK-WORKSPACE-001", "owned roots and mutation owner are required")
    seed = {"repo":repository_ref,"base":baseline_ref,"roots":list(owned_roots),"owner":mutation_owner,"serial":serialization_state}
    return {
        "schema": "bbk.workspace-admission-receipt.v1",
        "receipt_id": f"workspace:{digest(seed)[:20]}",
        "repository_ref": repository_ref,
        "baseline_ref": baseline_ref,
        "protected_tree_state": protected_tree_state,
        "known_unrelated_dirt": list(known_unrelated_dirt),
        "owned_roots": list(owned_roots),
        "mutation_owner": mutation_owner,
        "serialization_state": serialization_state,
        "invalidation_keys": [f"repository:{repository_ref}",f"baseline:{baseline_ref}",f"roots:{digest(list(owned_roots))}",f"owner:{mutation_owner}"],
        "issued_at": utc(issued_at),
    }


def child_event(*, child_ref: str, state: str, detail: Mapping[str, Any] | None = None, observed_at: str | None = None) -> dict[str, Any]:
    allowed={"STARTED","PROGRESS_MILESTONE","BLOCKED","RETURN_READY","FAILED","CANCELLED"}
    if state not in allowed:
        raise PlanningOptimizationError("BBK-CHILD-EVENT-001", f"invalid child event state {state}")
    return {"schema":"bbk.child-event.v1","child_ref":child_ref,"state":state,"detail":dict(detail or {}),"observed_at":utc(observed_at),"poll_required":False}


def _stage_file(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        return temp
    except Exception:
        temp.unlink(missing_ok=True)
        raise


def _replace_file(source: Path, target: Path) -> None:
    """Replace indirection retained for deterministic fault-injection tests."""
    os.replace(source, target)


def _snapshot(path: Path) -> tuple[bool, bytes | None, int | None]:
    if not path.exists():
        return False, None, None
    if path.is_symlink() or not path.is_file():
        raise PlanningOptimizationError("BBK-PLAN-TX-UNSAFE", f"unsafe transaction target {path}")
    info = path.stat()
    return True, path.read_bytes(), stat.S_IMODE(info.st_mode)


def _restore(path: Path, prior: tuple[bool, bytes | None, int | None]) -> None:
    existed, data, mode = prior
    if not existed:
        path.unlink(missing_ok=True)
        return
    assert data is not None
    temp = _stage_file(path, data)
    try:
        os.replace(temp, path)
        if mode is not None:
            os.chmod(path, mode)
    finally:
        temp.unlink(missing_ok=True)


def _atomic_write(path: Path, data: bytes) -> None:
    temp = _stage_file(path, data)
    try:
        _replace_file(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _acquire_plan_lock(state_root: Path) -> Path:
    lock = state_root / ".plan-transaction.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise PlanningOptimizationError(
            "BBK-PLAN-TX-CONFLICT", f"another plan transaction owns {lock}", retryable=True
        ) from exc
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
        json.dump({"pid": os.getpid(), "created_at": utc()}, stream, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    return lock


def _read_current_state(state_root: Path) -> tuple[list[dict[str, Any]], str, dict[str, Any] | None]:
    pointer_path = state_root / "current.json"
    if pointer_path.is_file():
        try:
            pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
            tx_dir = state_root / str(pointer["transaction_path"])
            lines = (tx_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
            events = [json.loads(line) for line in lines if line.strip()]
            head = str(pointer["head"])
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise PlanningOptimizationError("BBK-PLAN-TX-STATE", f"invalid authoritative planning pointer: {exc}") from exc
        if digest(events) != head:
            raise PlanningOptimizationError("BBK-PLAN-TX-STATE", "authoritative planning head does not match events")
        return events, head, pointer
    # Backward-compatible read of the pre-pointer Alpha.17/legacy materialization.
    log_path = state_root / "events.jsonl"
    try:
        lines = log_path.read_text(encoding="utf-8").splitlines() if log_path.is_file() else []
        events = [json.loads(line) for line in lines if line.strip()]
    except (OSError, json.JSONDecodeError) as exc:
        raise PlanningOptimizationError("BBK-PLAN-TX-STATE", f"invalid legacy planning event stream: {exc}") from exc
    return events, digest(events), None


def _publish_targets(staged: list[tuple[Path, Path, tuple[bool, bytes | None, int | None]]]) -> None:
    published: list[tuple[Path, tuple[bool, bytes | None, int | None]]] = []
    try:
        for target, temp, prior in staged:
            _replace_file(temp, target)
            published.append((target, prior))
    except OSError as exc:
        restore_errors: list[str] = []
        for target, prior in reversed(published):
            try:
                _restore(target, prior)
            except OSError as restore_exc:
                restore_errors.append(f"{target}: {restore_exc}")
        message = f"planning projection publication failed: {exc}"
        if restore_errors:
            message += "; restore failures=" + "; ".join(restore_errors)
        raise PlanningOptimizationError("BBK-PLAN-TX-PUBLISH", message, retryable=True) from exc
    finally:
        for _, temp, _ in staged:
            temp.unlink(missing_ok=True)


def transact_plan(
    state_root: Path, events: Sequence[Mapping[str, Any]], *, authority_ref: str,
    projection_outputs: Mapping[str, Path] | None = None, expected_head: str | None = None,
    transaction_id: str | None = None, created_at: str | None = None,
) -> dict[str, Any]:
    """Commit a semantic event transaction through an authoritative pointer.

    The immutable transaction directory and all compatibility projections are
    fully staged first.  ``current.json`` is the final atomic commit point.
    A concurrent writer receives a retryable conflict; interruption before the
    pointer swap leaves the prior transaction authoritative.
    """
    state_root = state_root.resolve()
    state_root.mkdir(parents=True, exist_ok=True)
    lock = _acquire_plan_lock(state_root)
    transaction_dir: Path | None = None
    compatibility_published: list[tuple[Path, tuple[bool, bytes | None, int | None]]] = []
    try:
        prior, head, prior_pointer = _read_current_state(state_root)
        if expected_head is not None and expected_head != head:
            raise PlanningOptimizationError(
                "BBK-PLAN-TX-CONFLICT", f"expected head {expected_head} but current is {head}", retryable=True
            )
        tx = transaction_id or f"plan-tx:{uuid.uuid4()}"
        safe_tx = tx.replace(":", "-").replace("/", "-").replace("\\", "-")
        now = utc(created_at)
        appended: list[dict[str, Any]] = []
        sequence = len(prior) + 1
        allowed = {
            "DECISION_ACCEPTED", "DECISION_SUPERSEDED", "FINDING_DISPOSITION_CHANGED",
            "BASELINE_ADVANCED", "AUTHORITY_UPDATED", "ROADMAP_REVISED", "FRONTIER_REVISED",
            "FRONTIER_ADVANCED", "PROJECT_COVERAGE_UPDATED", "ARTIFACT_INVALIDATED",
            "BLOCKER_RECORDED", "BLOCKER_CLEARED",
        }
        previous_event_id = prior[-1]["event_id"] if prior else None
        for raw in events:
            event = dict(raw)
            event_type = str(event.get("event_type") or "")
            if event_type not in allowed:
                raise PlanningOptimizationError("BBK-PLAN-TX-001", f"invalid event type {event_type}")
            if not event.get("subject_ref"):
                raise PlanningOptimizationError("BBK-PLAN-TX-001", "event subject_ref is required")
            event.update({
                "schema": "bbk.plan-event.v1",
                "event_id": str(event.get("event_id") or f"{tx}:{sequence}"),
                "transaction_id": tx,
                "sequence": sequence,
                "authority_ref": str(event.get("authority_ref") or authority_ref),
                "predecessor_refs": list(event.get("predecessor_refs") or ([previous_event_id] if previous_event_id else [])),
                "payload": dict(event.get("payload") or {}),
                "created_at": str(event.get("created_at") or now),
            })
            previous_event_id = event["event_id"]
            appended.append(event)
            sequence += 1
        combined = [*prior, *appended]
        new_head = digest(combined)
        outputs = dict(projection_outputs or {})
        projections: dict[str, dict[str, Any]] = {}
        for name, path in sorted(outputs.items()):
            relevant = [
                item for item in combined
                if item["event_type"].startswith(name.replace("-", "_").upper())
                or str(item.get("payload", {}).get("projection")) == name
            ]
            projection = {
                "schema": f"bbk.plan-projection.{name}.v1",
                "transaction_id": tx,
                "head": new_head,
                "events": relevant,
                "generated_at": now,
            }
            data = canonical_bytes(projection)
            projections[name] = {
                "path": path.resolve().as_posix(),
                "sha256": hashlib.sha256(data).hexdigest(),
                "byte_count": len(data),
                "value": projection,
            }
        jsonl = b"".join(
            (json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
            for item in combined
        )
        head_value = {
            "schema": "bbk.plan-head.v1", "head": new_head,
            "event_count": len(combined), "last_transaction_id": tx,
        }
        durable_writes = [
            "SEMANTIC_EVENT_BATCH",
            *[f"PROJECTION:{name}" for name in sorted(projections)],
            "TRANSACTION_RECEIPT",
            "AUTHORITATIVE_CURRENT_POINTER",
        ]
        receipt = {
            "schema": "bbk.plan-transaction-receipt.v1", "status": "PASS", "transaction_id": tx,
            "prior_head": head, "head": new_head,
            "event_sequence_start": len(prior) + 1 if appended else None,
            "event_sequence_end": len(combined) if appended else None,
            "event_ids": [item["event_id"] for item in appended],
            "projection_identities": [{k: v for k, v in item.items() if k != "value"} for item in projections.values()],
            "authority_ref": authority_ref, "generated_at": now, "atomic": True,
            "commit_point": "current.json", "prior_transaction_ref": prior_pointer,
            "durable_planning_writes": durable_writes,
            "durable_planning_write_count": len(durable_writes),
            "write_accounting_basis": "LOGICAL_DURABLE_ARTIFACTS",
        }

        transactions_root = state_root / "transactions"
        transactions_root.mkdir(parents=True, exist_ok=True)
        final_tx_dir = transactions_root / safe_tx
        if final_tx_dir.exists():
            raise PlanningOptimizationError("BBK-PLAN-TX-CONFLICT", f"transaction already exists: {tx}", retryable=True)
        staging_dir = Path(tempfile.mkdtemp(prefix=f".{safe_tx}.", dir=transactions_root))
        try:
            (staging_dir / "projections").mkdir()
            (staging_dir / "events.jsonl").write_bytes(jsonl)
            (staging_dir / "head.json").write_bytes(canonical_bytes(head_value))
            for name, item in projections.items():
                (staging_dir / "projections" / f"{name}.json").write_bytes(canonical_bytes(item["value"]))
            (staging_dir / "receipt.json").write_bytes(canonical_bytes(receipt))
            os.replace(staging_dir, final_tx_dir)
            transaction_dir = final_tx_dir
        finally:
            if staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)

        # Publish compatibility projections first. They are restored if the
        # final current-pointer swap fails.
        targets: list[tuple[Path, bytes]] = [
            (state_root / "events.jsonl", jsonl),
            (state_root / "head.json", canonical_bytes(head_value)),
            (state_root / f"{safe_tx}.receipt.json", canonical_bytes(receipt)),
        ]
        targets.extend((Path(item["path"]), canonical_bytes(item["value"])) for item in projections.values())
        staged: list[tuple[Path, Path, tuple[bool, bytes | None, int | None]]] = []
        for target, data in targets:
            target = target.resolve()
            prior_target = _snapshot(target)
            staged.append((target, _stage_file(target, data), prior_target))
        # Publish manually so snapshots remain available for pointer rollback.
        try:
            for target, temp, prior_target in staged:
                _replace_file(temp, target)
                compatibility_published.append((target, prior_target))
        except OSError as exc:
            for target, prior_target in reversed(compatibility_published):
                _restore(target, prior_target)
            raise PlanningOptimizationError("BBK-PLAN-TX-PUBLISH", f"planning projection publication failed: {exc}", retryable=True) from exc
        finally:
            for _, temp, _ in staged:
                temp.unlink(missing_ok=True)

        pointer = {
            "schema": "bbk.plan-current.v1", "transaction_id": tx, "head": new_head,
            "transaction_path": final_tx_dir.relative_to(state_root).as_posix(),
            "receipt_path": (final_tx_dir / "receipt.json").relative_to(state_root).as_posix(),
            "committed_at": now,
        }
        pointer_path = state_root / "current.json"
        pointer_temp = _stage_file(pointer_path, canonical_bytes(pointer))
        try:
            _replace_file(pointer_temp, pointer_path)
        except OSError as exc:
            for target, prior_target in reversed(compatibility_published):
                _restore(target, prior_target)
            raise PlanningOptimizationError("BBK-PLAN-TX-PUBLISH", f"planning commit-point publication failed: {exc}", retryable=True) from exc
        finally:
            pointer_temp.unlink(missing_ok=True)
        receipt["current_pointer"] = pointer
        return receipt
    finally:
        try:
            lock.unlink(missing_ok=True)
        except OSError:
            pass

