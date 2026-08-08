#!/usr/bin/env python3
"""Extract Alpha.17 verification-economy metrics and enforce routine budgets.

The input is a compact, deterministic event log. Events may carry ``count`` so
large session replays can be represented without copying provider prompts or
shell output into the permanent fixture. Budgets intentionally measure process
redundancy alongside product correctness signals; they never convert missing or
failed product evidence into a PASS.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from gate_kernel import canonical_digest
except ImportError:  # pragma: no cover
    from .gate_kernel import canonical_digest


class VerificationMetricsError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def _text(value: Any, field: str, *, required: bool = True) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip():
        raise VerificationMetricsError("VERIFICATION_METRICS_INPUT_INVALID", f"{field} must be a non-empty string")
    return value.strip()


def _timestamp(value: Any, field: str, *, required: bool = False) -> dt.datetime | None:
    text = _text(value, field, required=required)
    if text is None:
        return None
    try:
        return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise VerificationMetricsError("VERIFICATION_METRICS_INPUT_INVALID", f"{field} must be an ISO-8601 timestamp") from exc


def _count(event: Mapping[str, Any]) -> int:
    value = event.get("count", 1)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise VerificationMetricsError("VERIFICATION_METRICS_INPUT_INVALID", "event.count must be an integer >= 1")
    return value


def _bool(event: Mapping[str, Any], field: str, default: bool = False) -> bool:
    value = event.get(field, default)
    if not isinstance(value, bool):
        raise VerificationMetricsError("VERIFICATION_METRICS_INPUT_INVALID", f"event.{field} must be boolean")
    return value


def _group_max(events: Sequence[Mapping[str, Any]], event_type: str, key_field: str) -> tuple[int, dict[str, int]]:
    grouped: dict[str, int] = defaultdict(int)
    for event in events:
        if event.get("type") != event_type:
            continue
        key = str(event.get(key_field) or "<unbound>")
        grouped[key] += _count(event)
    return (max(grouped.values(), default=0), dict(sorted(grouped.items())))


def extract_metrics(value: Mapping[str, Any]) -> dict[str, Any]:
    if value.get("schema") != "bbk.verification-economy-event-log.v1":
        raise VerificationMetricsError("VERIFICATION_METRICS_SCHEMA_INVALID", "expected bbk.verification-economy-event-log.v1")
    run_id = _text(value.get("run_id"), "run_id")
    started_at = _timestamp(value.get("started_at"), "started_at", required=True)
    executable_at = _timestamp(value.get("executable_work_at"), "executable_work_at")
    raw_events = value.get("events")
    if not isinstance(raw_events, list):
        raise VerificationMetricsError("VERIFICATION_METRICS_INPUT_INVALID", "events must be an array")
    events: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_events):
        if not isinstance(raw, Mapping):
            raise VerificationMetricsError("VERIFICATION_METRICS_INPUT_INVALID", f"events[{index}] must be an object")
        event = dict(raw)
        _text(event.get("type"), f"events[{index}].type")
        _count(event)
        events.append(event)

    totals: Counter[str] = Counter()
    role_sessions: Counter[str] = Counter()
    attempt_churn: Counter[str] = Counter()
    prompt = Counter()
    first_worker: dt.datetime | None = None
    deterministic_duplicate_count = 0
    metadata_validator_count = 0
    reviewer_without_risk = 0
    mechanical_successor_plans = 0
    support_after_executable = 0
    broad_validator_by_candidate: Counter[str] = Counter()
    independent_validator_by_candidate: Counter[str] = Counter()
    campaign_admission_by_attempt: Counter[str] = Counter()
    boundary_admission_by_subject: Counter[str] = Counter()

    for event in events:
        event_type = str(event["type"])
        count = _count(event)
        totals[event_type] += count
        if event_type == "session_started":
            role_sessions[str(event.get("role_class") or "other")] += count
        if event_type == "worker_action":
            observed = _timestamp(event.get("observed_at"), "event.observed_at")
            if observed is not None and (first_worker is None or observed < first_worker):
                first_worker = observed
        if event_type == "shell_call" and _bool(event, "exact_within_session_duplicate"):
            deterministic_duplicate_count += count
        if event_type == "deterministic_check" and _bool(event, "current_pass_receipt") and not _bool(event, "invalidation_changed"):
            deterministic_duplicate_count += count
        if event_type == "repository_validator" and not _bool(event, "changed_relevant_inputs", True):
            metadata_validator_count += count
        if event_type == "reviewer_invocation" and not _bool(event, "named_qualitative_risk"):
            reviewer_without_risk += count
        if event_type == "attempt_transition":
            attempt_churn[str(event.get("cause_class") or "UNKNOWN")] += count
            if _bool(event, "mechanical") and _bool(event, "successor_plan"):
                mechanical_successor_plans += count
        if event_type == "support_role_commissioned":
            observed = _timestamp(event.get("observed_at"), "event.observed_at")
            explicitly_after = _bool(event, "after_executable_work", False)
            if explicitly_after or (executable_at is not None and observed is not None and observed >= executable_at):
                if not _bool(event, "named_material_blocker_or_risk"):
                    support_after_executable += count
        if event_type == "repository_validator" and _bool(event, "broad_final"):
            broad_validator_by_candidate[str(event.get("subject_key") or "<unbound>")] += count
        if event_type == "validator_assignment" and _bool(event, "independent"):
            independent_validator_by_candidate[str(event.get("subject_key") or "<unbound>")] += count
        if event_type == "campaign_admission":
            campaign_admission_by_attempt[str(event.get("attempt_key") or "<unbound>")] += count
        if event_type == "boundary_admission":
            boundary_admission_by_subject[str(event.get("subject_key") or "<unbound>")] += count
        for field in ("prompt_bytes", "prompt_tokens", "compactions"):
            raw_number = event.get(field, 0)
            if isinstance(raw_number, bool) or not isinstance(raw_number, int) or raw_number < 0:
                raise VerificationMetricsError("VERIFICATION_METRICS_INPUT_INVALID", f"event.{field} must be an integer >= 0")
            prompt[field] += raw_number * count

    max_handoff, handoff_by_subject = _group_max(events, "handoff_verification", "subject_key")
    handoff_underlying = totals["handoff_verification"]
    handoff_subjects = len(handoff_by_subject)
    handoff_duplicates = max(0, handoff_underlying - handoff_subjects)

    violations: list[dict[str, Any]] = []

    def budget(metric: str, observed: int, maximum: int, detail: Mapping[str, Any] | None = None) -> None:
        if observed > maximum:
            violations.append({
                "metric": metric,
                "observed": observed,
                "maximum": maximum,
                **({"detail": dict(detail)} if detail else {}),
            })

    budget("underlying_handoff_verification_per_unchanged_subject", max_handoff, 1, handoff_by_subject)
    budget("campaign_admission_per_root_physical_attempt", max(campaign_admission_by_attempt.values(), default=0), 1, campaign_admission_by_attempt)
    budget("boundary_admission_per_unchanged_boundary", max(boundary_admission_by_subject.values(), default=0), 1, boundary_admission_by_subject)
    budget("product_validator_for_metadata_only_changes", metadata_validator_count, 0)
    budget("broad_product_validator_per_frozen_candidate", max(broad_validator_by_candidate.values(), default=0), 1, broad_validator_by_candidate)
    budget("reviewer_without_named_qualitative_risk", reviewer_without_risk, 0)
    budget("routine_independent_validator_attempts_per_candidate", max(independent_validator_by_candidate.values(), default=0), 1, independent_validator_by_candidate)
    budget("mechanical_defect_successor_plan_count", mechanical_successor_plans, 0)
    budget("preemptive_help_probes_for_known_commands", totals["preemptive_help_probe"], 0)
    budget("rechecks_without_changed_invalidation_key", deterministic_duplicate_count, 0)
    budget("support_roles_after_executable_work", support_after_executable, 0)

    elapsed = None
    if first_worker is not None and started_at is not None:
        elapsed = max(0.0, (first_worker - started_at).total_seconds())

    core = {
        "schema": "bbk.verification-economy-metrics.v1",
        "run_id": run_id,
        "source_digest": f"sha256:{canonical_digest(value)}",
        "status": "PASS" if not violations else "FAIL",
        "totals": dict(sorted(totals.items())),
        "sessions": {
            "total": sum(role_sessions.values()),
            "worker": role_sessions.get("worker", 0),
            "planning_coordination_assurance": sum(role_sessions.get(name, 0) for name in ("planning", "coordination", "assurance")),
            "by_class": dict(sorted(role_sessions.items())),
        },
        "latency": {"seconds_to_first_outcome_bearing_worker_action": elapsed},
        "verification": {
            "underlying_handoff_verifications": handoff_underlying,
            "handoff_subjects": handoff_subjects,
            "duplicate_handoff_verifications": handoff_duplicates,
            "receipt_reuse_count": totals["receipt_reused"],
            "avoided_check_count": totals["check_avoided"],
            "rechecks_without_changed_invalidation_key": deterministic_duplicate_count,
            "repository_validator_invocations": totals["repository_validator"],
            "metadata_only_repository_validator_invocations": metadata_validator_count,
            "reviewer_invocations": totals["reviewer_invocation"],
            "reviewer_without_named_qualitative_risk": reviewer_without_risk,
        },
        "coordination": {
            "poll_or_list_calls": totals["child_poll"] + totals["child_list"],
            "support_roles_after_executable_work": support_after_executable,
        },
        "attempts": {
            "churn_by_cause": dict(sorted(attempt_churn.items())),
            "mechanical_repairs_completed_in_place": totals["mechanical_repair_in_place"],
            "mechanical_defect_successor_plans": mechanical_successor_plans,
        },
        "product_quality": {
            "defects_found": totals["product_defect_found"],
            "escaped_defects": totals["escaped_defect"],
            "failed_assertions_preserved": totals["failed_assertion_preserved"],
        },
        "prompt": dict(prompt),
        "budgets": {
            "status": "PASS" if not violations else "FAIL",
            "violation_count": len(violations),
            "violations": violations,
        },
    }
    return {**core, "metrics_digest": f"sha256:{canonical_digest(core)}"}


def _load(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationMetricsError("VERIFICATION_METRICS_INPUT_INVALID", f"cannot read event log: {exc}") from exc
    if not isinstance(value, dict):
        raise VerificationMetricsError("VERIFICATION_METRICS_INPUT_INVALID", "event log must contain an object")
    return value


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("event_log")
    parser.add_argument("--output")
    parser.add_argument("--fail-on-budget", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        result = extract_metrics(_load(args.event_log))
    except VerificationMetricsError as exc:
        print(json.dumps({"schema": "bbk.verification-economy-metrics-error.v1", "status": "ERROR", "code": exc.code, "message": exc.message}, sort_keys=True))
        return 2
    text = json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 1 if args.fail_on_budget and result["status"] != "PASS" else 0


if __name__ == "__main__":
    raise SystemExit(main())
