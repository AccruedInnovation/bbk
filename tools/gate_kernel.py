#!/usr/bin/env python3
"""Deterministic, host-neutral policy evaluation for BBK governed execution.

The Gate Kernel has no provider, OMP, VCS, filesystem-effect, Beads, or mise
side effects.  Adapters supply typed facts and persist the returned receipt.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePath
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
VERSION_PATH = ROOT / "VERSION"
try:
    IMPLEMENTATION_VERSION = VERSION_PATH.read_text(encoding="utf-8").strip()
except OSError:
    IMPLEMENTATION_VERSION = "unknown"

DECISIONS = frozenset({"ALLOW", "BLOCK", "REQUIRE_OVERRIDE"})
LEVELS = frozenset({"OBSERVE", "ENFORCE", "INVARIANT"})
OPERATORS = frozenset({"eq", "ne", "in", "not_in", "exists", "truthy", "contains", "prefix", "path_within"})


class GateKernelError(ValueError):
    """Typed input or policy is invalid and cannot be evaluated safely."""


def canonical_json_bytes(value: Any) -> bytes:
    """Return Blueprint-portable canonical JSON bytes."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def canonical_digest(value: Any, *, prefixed: bool = False) -> str:
    digest = hashlib.sha256(canonical_json_bytes(value)).hexdigest()
    return f"sha256:{digest}" if prefixed else digest


def load_policy(path: str | Path | None = None) -> dict[str, Any]:
    selected = Path(path) if path else ROOT / "spec" / "policies" / "governed-software-v1.json"
    try:
        value = json.loads(selected.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateKernelError(f"Cannot load governed policy {selected}: {exc}") from exc
    validate_policy(value)
    return value


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise GateKernelError(f"{label} must be an object")
    return value


def _require_text(mapping: Mapping[str, Any], field: str, label: str) -> str:
    value = mapping.get(field)
    if not isinstance(value, str) or not value.strip():
        raise GateKernelError(f"{label}.{field} must be a non-empty string")
    return value


def _require_unique_texts(value: Any, label: str, *, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise GateKernelError(f"{label} must be a{' non-empty' if not allow_empty else ''} list")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise GateKernelError(f"{label} entries must be non-empty strings")
        if item in result:
            raise GateKernelError(f"{label} contains duplicate {item!r}")
        result.append(item)
    return result


def validate_policy(policy: Mapping[str, Any]) -> None:
    _require_mapping(policy, "policy")
    if policy.get("schema") != "bbk.governed-policy.v1":
        raise GateKernelError("policy.schema must be bbk.governed-policy.v1")
    _require_text(policy, "policy_id", "policy")
    _require_text(policy, "policy_version", "policy")
    rules = policy.get("rules")
    if not isinstance(rules, list) or not rules:
        raise GateKernelError("policy.rules must be a non-empty list")
    seen: set[str] = set()
    for index, raw in enumerate(rules):
        rule = _require_mapping(raw, f"policy.rules[{index}]")
        rule_id = _require_text(rule, "rule_id", f"policy.rules[{index}]")
        if rule_id in seen:
            raise GateKernelError(f"duplicate policy rule_id {rule_id!r}")
        seen.add(rule_id)
        if rule.get("level") not in LEVELS:
            raise GateKernelError(f"policy rule {rule_id} has invalid level")
        _validate_predicate(rule.get("when"), f"policy rule {rule_id}.when")
        _require_text(rule, "reason_code", f"policy rule {rule_id}")
        _require_text(rule, "message", f"policy rule {rule_id}")
        _require_text(rule, "smallest_next_action", f"policy rule {rule_id}")
        override = _require_mapping(rule.get("override_eligibility"), f"policy rule {rule_id}.override_eligibility")
        if not isinstance(override.get("eligible"), bool):
            raise GateKernelError(f"policy rule {rule_id} override eligibility must be boolean")
        authorities = _require_unique_texts(override.get("authorities", []), f"policy rule {rule_id} authorities")
        if rule["level"] == "INVARIANT" and (override["eligible"] or authorities):
            raise GateKernelError(f"invariant policy rule {rule_id} cannot be override eligible")
        if override["eligible"] and not authorities:
            raise GateKernelError(f"override-eligible policy rule {rule_id} must name authorities")


def _validate_predicate(predicate: Any, label: str) -> None:
    value = _require_mapping(predicate, label)
    branches = [name for name in ("all", "any", "not", "field") if name in value]
    if len(branches) != 1:
        raise GateKernelError(f"{label} must contain exactly one of all, any, not, or field")
    branch = branches[0]
    if branch in {"all", "any"}:
        items = value.get(branch)
        if not isinstance(items, list) or not items:
            raise GateKernelError(f"{label}.{branch} must be a non-empty list")
        for index, item in enumerate(items):
            _validate_predicate(item, f"{label}.{branch}[{index}]")
        return
    if branch == "not":
        _validate_predicate(value["not"], f"{label}.not")
        return
    _require_text(value, "field", label)
    operator = value.get("operator")
    if operator not in OPERATORS:
        raise GateKernelError(f"{label}.operator must be one of {sorted(OPERATORS)}")
    if operator not in {"exists", "truthy"} and "value" not in value and "value_from" not in value:
        raise GateKernelError(f"{label} requires value or value_from for operator {operator}")
    if "value_from" in value and (not isinstance(value["value_from"], str) or not value["value_from"].strip()):
        raise GateKernelError(f"{label}.value_from must be a non-empty field path")


def validate_request(request: Mapping[str, Any]) -> None:
    _require_mapping(request, "request")
    if request.get("schema") != "bbk.gate-evaluation-request.v1":
        raise GateKernelError("request.schema must be bbk.gate-evaluation-request.v1")
    for field in ("policy_ref", "candidate_ref", "work_unit_id", "idempotency_key"):
        _require_text(request, field, "request")
    actor = _require_mapping(request.get("actor"), "request.actor")
    for field in ("role", "actor_id", "actor_kind"):
        _require_text(actor, field, "request.actor")
    if actor.get("actor_kind") not in {"MODEL", "HUMAN", "SYSTEM", "ADAPTER"}:
        raise GateKernelError("request.actor.actor_kind is invalid")
    authority = _require_mapping(request.get("authority"), "request.authority")
    for field in ("authority_ref", "holder_kind"):
        _require_text(authority, field, "request.authority")
    _require_unique_texts(authority.get("scopes", []), "request.authority.scopes")
    intent = _require_mapping(request.get("intent"), "request.intent")
    for field in ("operation", "mutation_class"):
        _require_text(intent, field, "request.intent")
    snapshot = _require_mapping(request.get("state_snapshot"), "request.state_snapshot")
    _require_text(snapshot, "snapshot_ref", "request.state_snapshot")
    override = request.get("override")
    if override is not None:
        override = _require_mapping(override, "request.override")
        if not isinstance(override.get("present"), bool):
            raise GateKernelError("request.override.present must be boolean")
        if override.get("present"):
            _require_text(override, "requested_by_kind", "request.override")
            _require_text(override, "authority_ref", "request.override")
            _require_unique_texts(override.get("scopes", []), "request.override.scopes", allow_empty=False)


def _field(value: Mapping[str, Any], dotted: str) -> tuple[bool, Any]:
    current: Any = value
    for component in dotted.split("."):
        if not isinstance(current, Mapping) or component not in current:
            return False, None
        current = current[component]
    return True, current


def _path_within(candidate: Any, root: Any) -> bool:
    if not isinstance(candidate, str) or not isinstance(root, str):
        return False
    try:
        c = PurePath(candidate)
        r = PurePath(root)
        return c == r or r in c.parents
    except (TypeError, ValueError):
        return False


def predicate_matches(predicate: Mapping[str, Any], facts: Mapping[str, Any]) -> bool:
    """Evaluate one validated predicate without side effects."""
    if "all" in predicate:
        return all(predicate_matches(item, facts) for item in predicate["all"])
    if "any" in predicate:
        return any(predicate_matches(item, facts) for item in predicate["any"])
    if "not" in predicate:
        return not predicate_matches(predicate["not"], facts)
    exists, actual = _field(facts, str(predicate["field"]))
    operator = predicate["operator"]
    if operator == "exists":
        expected = predicate.get("value", True)
        return exists is bool(expected)
    if operator == "truthy":
        return exists and bool(actual)
    expected = predicate.get("value")
    if "value_from" in predicate:
        expected_exists, expected = _field(facts, str(predicate["value_from"]))
        if not expected_exists:
            return False
    if operator == "eq":
        return exists and actual == expected
    if operator == "ne":
        return (not exists) or actual != expected
    if operator == "in":
        return exists and isinstance(expected, Sequence) and not isinstance(expected, (str, bytes)) and actual in expected
    if operator == "not_in":
        return (not exists) or not isinstance(expected, Sequence) or isinstance(expected, (str, bytes)) or actual not in expected
    if operator == "contains":
        if not exists:
            return False
        try:
            return expected in actual
        except TypeError:
            return False
    if operator == "prefix":
        return exists and isinstance(actual, str) and isinstance(expected, str) and actual.startswith(expected)
    if operator == "path_within":
        return exists and _path_within(actual, expected)
    raise GateKernelError(f"unsupported predicate operator {operator}")


def _override_applies(rule: Mapping[str, Any], request: Mapping[str, Any]) -> bool:
    eligibility = rule["override_eligibility"]
    override = request.get("override")
    authority = request["authority"]
    if not eligibility.get("eligible") or not isinstance(override, Mapping) or not override.get("present"):
        return False
    if override.get("requested_by_kind") == "MODEL":
        return False
    if override.get("authority_ref") != authority.get("authority_ref"):
        return False
    holder = authority.get("holder_kind")
    if holder not in eligibility.get("authorities", []):
        return False
    if eligibility.get("requires_exact_scope", True):
        scopes = set(override.get("scopes", []))
        required = {
            f"rule:{rule['rule_id']}",
            f"candidate:{request['candidate_ref']}",
            f"work-unit:{request['work_unit_id']}",
        }
        if not required.issubset(scopes):
            return False
    return True


def evaluate(policy: Mapping[str, Any], request: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate typed facts and return a stable ALLOW/BLOCK/REQUIRE_OVERRIDE decision."""
    validate_policy(policy)
    validate_request(request)
    expected_ref = f"{policy['policy_id']}@{policy['policy_version']}"
    if request["policy_ref"] != expected_ref:
        raise GateKernelError(f"request.policy_ref must be {expected_ref}")

    request_for_digest = dict(request)
    request_for_digest.pop("request_digest", None)
    request_digest = canonical_digest(request_for_digest)
    matched: list[Mapping[str, Any]] = [rule for rule in policy["rules"] if predicate_matches(rule["when"], request)]
    invariant = [rule for rule in matched if rule["level"] == "INVARIANT"]
    enforce_unoverridden: list[Mapping[str, Any]] = []
    overridden: list[Mapping[str, Any]] = []
    observed = [rule for rule in matched if rule["level"] == "OBSERVE"]
    for rule in (item for item in matched if item["level"] == "ENFORCE"):
        (overridden if _override_applies(rule, request) else enforce_unoverridden).append(rule)

    if invariant:
        outcome = "BLOCK"
        decisive = invariant
    elif enforce_unoverridden:
        if any(rule["override_eligibility"].get("eligible") for rule in enforce_unoverridden):
            outcome = "REQUIRE_OVERRIDE"
        else:
            outcome = "BLOCK"
        decisive = enforce_unoverridden
    else:
        outcome = "ALLOW"
        decisive = []

    reason_codes: list[str] = []
    for rule in (*invariant, *enforce_unoverridden):
        if rule["reason_code"] not in reason_codes:
            reason_codes.append(rule["reason_code"])
    observations: list[str] = []
    for rule in (*observed, *overridden):
        code = ("OVERRIDE_APPLIED:" if rule in overridden else "OBSERVED:") + str(rule["reason_code"])
        if code not in observations:
            observations.append(code)

    authorities: list[str] = []
    for rule in enforce_unoverridden:
        for authority in rule["override_eligibility"].get("authorities", []):
            if authority not in authorities:
                authorities.append(authority)
    required_evidence = []
    if outcome == "REQUIRE_OVERRIDE":
        required_evidence = [
            f"exact-scope override for rule:{rule['rule_id']} candidate:{request['candidate_ref']} work-unit:{request['work_unit_id']}"
            for rule in enforce_unoverridden if rule["override_eligibility"].get("eligible")
        ]

    if decisive:
        next_action = decisive[0]["smallest_next_action"]
    elif observed:
        next_action = observed[0]["smallest_next_action"]
    else:
        next_action = "Proceed through the authorized adapter and reconcile the observed effect."

    decision_core: dict[str, Any] = {
        "schema": "bbk.gate-decision.v1",
        "decision": outcome,
        "reason_codes": reason_codes,
        "observations": observations,
        "required_evidence": required_evidence,
        "override_eligibility": {
            "eligible": outcome == "REQUIRE_OVERRIDE" and bool(authorities),
            "authorities": authorities,
            "requires_exact_scope": bool(authorities),
        },
        "smallest_next_action": next_action,
        "policy_id": policy["policy_id"],
        "policy_version": policy["policy_version"],
        "request_digest": request_digest,
        "matched_rules": [str(rule["rule_id"]) for rule in matched],
        "implementation_version": IMPLEMENTATION_VERSION,
    }
    receipt_ref = canonical_digest(
        {
            "schema": "bbk.gate-receipt-content.v1",
            "request": request_for_digest,
            "decision": decision_core,
        },
        prefixed=True,
    )
    return {**decision_core, "receipt_ref": receipt_ref}


def evaluate_default(request: Mapping[str, Any], policy_path: str | Path | None = None) -> dict[str, Any]:
    return evaluate(load_policy(policy_path), request)


__all__ = [
    "DECISIONS",
    "GateKernelError",
    "canonical_digest",
    "canonical_json_bytes",
    "evaluate",
    "evaluate_default",
    "load_policy",
    "predicate_matches",
    "validate_policy",
    "validate_request",
]
