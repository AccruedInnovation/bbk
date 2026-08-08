#!/usr/bin/env python3
"""Deterministic Alpha.17 execution-admission and verification-economy rules.

This module is intentionally independent of model judgment.  It produces and
reuses exact receipts, issues four-fact admission certificates, scopes broad
validators, classifies bounded repair transitions, and groups assurance work.
Alpha.17 callers may use the Python API or the JSON CLI; Alpha.17.1 can attach
stricter host pre-effect enforcement without changing these record shapes.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from gate_kernel import canonical_digest, canonical_json_bytes
except ImportError:  # pragma: no cover
    from .gate_kernel import canonical_digest, canonical_json_bytes

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
PASS_STATUSES = {"PASS"}
MECHANICAL_CLASSES = {
    "ENCODING", "BOM", "LINE_ENDING", "TERMINAL_NEWLINE", "CANONICALIZATION",
    "SERIALIZATION", "SCHEMA_SHAPE", "CONTROLLED_VOCABULARY", "GENERATED_METADATA",
    "PATH_NORMALIZATION", "DIGEST", "BYTE_COUNT", "MANIFEST", "PACKAGE", "CARRIER",
    "LOCATOR", "LEDGER_FORMAT", "CHECKPOINT_FORMAT", "PROFILE_PROJECTION",
    "TOOL_PROJECTION", "DETERMINISTIC_ADMISSION",
}
SEMANTIC_CHANGE_KEYS = {
    "semantic_meaning", "scope", "interface", "authority", "protected_floor",
    "mutation_ownership", "external_effect", "completion_meaning", "safety", "security",
}
METADATA_PREFIXES = (
    ".bbk/", "docs/planning/", "evidence/", "handoffs/", "logs/", "coordination/",
)


class VerificationEconomyError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise VerificationEconomyError("VERIFICATION_REQUEST_INVALID", f"{field} must be an object")
    return dict(value)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise VerificationEconomyError("VERIFICATION_REQUEST_INVALID", f"{field} must be a non-empty string")
    return value.strip()


def _string_list(value: Any, field: str, *, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise VerificationEconomyError("VERIFICATION_REQUEST_INVALID", f"{field} must be a {'non-empty ' if not allow_empty else ''}list")
    result = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise VerificationEconomyError("VERIFICATION_REQUEST_INVALID", f"{field} entries must be non-empty strings")
        result.append(item.strip())
    if len(result) != len(set(result)):
        raise VerificationEconomyError("VERIFICATION_REQUEST_INVALID", f"{field} contains duplicates")
    return result


def _digest(value: Any) -> str:
    return f"sha256:{canonical_digest(value)}"


def _integrity(value: Mapping[str, Any], *, field: str) -> dict[str, Any]:
    core = {key: item for key, item in value.items() if key != field}
    return {**core, field: _digest(core)}


def verification_identity(request: Mapping[str, Any]) -> dict[str, Any]:
    claim_id = _text(request.get("claim_id"), "claim_id")
    subject = _object(request.get("subject"), "subject")
    method = _object(request.get("method"), "method")
    invalidation = request.get("invalidation_keys")
    if not isinstance(invalidation, list) or not invalidation:
        raise VerificationEconomyError("VERIFICATION_REQUEST_INVALID", "invalidation_keys must be a non-empty list")
    normalized_keys: list[dict[str, str]] = []
    seen: set[str] = set()
    for entry in invalidation:
        item = _object(entry, "invalidation_keys[]")
        key = _text(item.get("key"), "invalidation key")
        value = _text(item.get("value"), f"invalidation_keys.{key}.value")
        if key in seen:
            raise VerificationEconomyError("VERIFICATION_REQUEST_INVALID", f"duplicate invalidation key {key}")
        seen.add(key)
        normalized_keys.append({"key": key, "value": value})
    normalized_keys.sort(key=lambda item: item["key"])
    core = {
        "claim_id": claim_id,
        "subject": subject,
        "method": method,
        "invalidation_keys": normalized_keys,
    }
    return {**core, "verification_key": _digest(core)}


def current_receipt(request: Mapping[str, Any], receipts: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    identity = verification_identity(request)
    matches = [
        dict(receipt) for receipt in receipts
        if receipt.get("schema") == "bbk.verification-receipt.v1"
        and receipt.get("verification_key") == identity["verification_key"]
        and receipt.get("result", {}).get("status") in PASS_STATUSES
    ]
    if len(matches) > 1:
        digests = {item.get("integrity", {}).get("receipt_digest") for item in matches}
        if len(digests) > 1:
            raise VerificationEconomyError(
                "VERIFICATION_RECEIPT_INDEX_CONFLICT",
                f"multiple different PASS receipts exist for {identity['verification_key']}",
            )
    return matches[-1] if matches else None


def pre_check(request: Mapping[str, Any], receipts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if request.get("schema") != "bbk.verification-precheck.v1":
        raise VerificationEconomyError("VERIFICATION_PRECHECK_SCHEMA_INVALID", "expected bbk.verification-precheck.v1")
    identity = verification_identity(request)
    independent = bool(request.get("independent_method_required", False))
    existing = current_receipt(request, receipts)
    if existing is not None and not independent:
        return {
            "schema": "bbk.verification-precheck-result.v1",
            "status": "REUSED_RECEIPT",
            "execution_authorized": False,
            "verification_key": identity["verification_key"],
            "receipt_id": existing["receipt_id"],
            "reason_code": "CURRENT_PASS_RECEIPT",
            "smallest_next_action": "Consume the current receipt; do not rerun the unchanged check.",
        }
    return {
        "schema": "bbk.verification-precheck-result.v1",
        "status": "AUTHORIZED_CHECK",
        "execution_authorized": True,
        "verification_key": identity["verification_key"],
        "receipt_id": None,
        "reason_code": "INDEPENDENT_METHOD_REQUIRED" if independent and existing else "NO_CURRENT_PASS_RECEIPT",
        "smallest_next_action": "Execute the smallest declared method once and register its result.",
    }


def create_receipt(request: Mapping[str, Any], result: Mapping[str, Any], *, observed_at: str | None = None) -> dict[str, Any]:
    identity = verification_identity(request)
    result_value = _object(result, "result")
    status = result_value.get("status")
    if status not in {"PASS", "FAIL", "INCONCLUSIVE", "BLOCKED"}:
        raise VerificationEconomyError("VERIFICATION_RESULT_INVALID", "result.status is invalid")
    producer = _object(request.get("producer"), "producer")
    context = _object(request.get("context", {}), "context")
    evidence_refs = _string_list(result_value.get("evidence_refs", []), "result.evidence_refs")
    receipt_core = {
        "schema": "bbk.verification-receipt.v1",
        "receipt_id": "",
        "verification_key": identity["verification_key"],
        "claim_id": identity["claim_id"],
        "subject": identity["subject"],
        "method": identity["method"],
        "context": context,
        "result": {
            "status": status,
            "observed_at": observed_at or utc_now(),
            "evidence_refs": evidence_refs,
            **({"reason_code": result_value["reason_code"]} if isinstance(result_value.get("reason_code"), str) else {}),
        },
        "invalidation_keys": identity["invalidation_keys"],
        "producer": producer,
    }
    receipt_id = _digest({key: value for key, value in receipt_core.items() if key != "receipt_id"})
    receipt_core["receipt_id"] = receipt_id
    digest = _digest(receipt_core)
    return {**receipt_core, "integrity": {"receipt_digest": digest}}


def _fact_present(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return bool(value) and all(_fact_present(item) for item in value.values())
    if isinstance(value, list):
        return bool(value) and all(_fact_present(item) for item in value)
    return value is not None


def dispatch_admission(request: Mapping[str, Any], *, issued_at: str | None = None) -> dict[str, Any]:
    if request.get("schema") != "bbk.dispatch-admission-request.v1":
        raise VerificationEconomyError("DISPATCH_ADMISSION_SCHEMA_INVALID", "expected bbk.dispatch-admission-request.v1")
    subject = _object(request.get("subject"), "subject")
    facts = _object(request.get("facts"), "facts")
    required = {
        "work_scope_return": "exact WorkUnit/subject, bounded scope, and parent return route",
        "authority_effect_fence": "current authority and effect fence",
        "workspace_mutation_ownership": "workspace and mutation ownership or positive serialization",
        "inputs_toolchain_carrier_checks": "required inputs, selected profile/toolchain, output carrier, and completion checks",
    }
    blockers = [
        {"fact": name, "reason_code": f"DISPATCH_{name.upper()}_MISSING", "message": description}
        for name, description in required.items()
        if not _fact_present(facts.get(name))
    ]
    status = "ADMITTED" if not blockers else "BLOCKED"
    core = {
        "schema": "bbk.admission-certificate.v1",
        "certificate_id": "",
        "kind": "BOUNDARY",
        "subject": subject,
        "status": status,
        "facts": {name: facts.get(name) for name in required},
        "blockers": blockers,
        "invalidation_keys": request.get("invalidation_keys", []),
        "issued_at": issued_at or utc_now(),
        "smallest_next_action": (
            "Dispatch the Worker immediately; no additional support cycle is authorized."
            if status == "ADMITTED"
            else f"Supply only the missing fact: {blockers[0]['message']}."
        ),
    }
    core["certificate_id"] = _digest({key: value for key, value in core.items() if key != "certificate_id"})
    return {**core, "integrity": {"certificate_digest": _digest(core)}}


def mechanical_transition(request: Mapping[str, Any]) -> dict[str, Any]:
    if request.get("schema") != "bbk.mechanical-transition-request.v1":
        raise VerificationEconomyError("MECHANICAL_TRANSITION_SCHEMA_INVALID", "expected bbk.mechanical-transition-request.v1")
    defect_class = _text(request.get("defect_class"), "defect_class").upper()
    frozen = bool(request.get("candidate_frozen", False))
    irreversible = bool(request.get("irreversible_or_external_effect_occurred", False))
    changed = set(_string_list(request.get("changed_governing_keys", []), "changed_governing_keys"))
    semantic = bool(changed & SEMANTIC_CHANGE_KEYS)
    if defect_class in MECHANICAL_CLASSES and not semantic and not frozen and not irreversible:
        transition = "SAME_ATTEMPT_REPAIR"
        successor_plan = False
        recheck = "AFFECTED_MECHANICAL_GATE_ONLY"
    elif defect_class in MECHANICAL_CLASSES and not semantic and frozen:
        transition = "SUCCESSOR_CANDIDATE"
        successor_plan = False
        recheck = "AFFECTED_ASSERTIONS_AND_EXPLICIT_INVALIDATIONS"
    else:
        transition = "SEMANTIC_OWNER_ESCALATION"
        successor_plan = semantic
        recheck = "SEMANTIC_IMPACT_CLOSURE"
    return {
        "schema": "bbk.mechanical-transition-result.v1",
        "status": "PASS",
        "classification": "MECHANICAL" if defect_class in MECHANICAL_CLASSES and not semantic else "SEMANTIC_OR_UNKNOWN",
        "transition": transition,
        "same_semantic_run": transition == "SAME_ATTEMPT_REPAIR",
        "same_physical_attempt": transition == "SAME_ATTEMPT_REPAIR",
        "successor_plan_required": successor_plan,
        "recheck_scope": recheck,
        "preserve_failed_materialization": True,
    }


def _normalize_relative_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _path_matches(path: str, selectors: Sequence[str]) -> bool:
    normalized = _normalize_relative_path(path)
    for selector in selectors:
        value = _normalize_relative_path(selector)
        if value.endswith("/**") and normalized.startswith(value[:-3].rstrip("/") + "/"):
            return True
        if value.endswith("/") and normalized.startswith(value):
            return True
        if normalized == value:
            return True
    return False


def validator_scope(request: Mapping[str, Any]) -> dict[str, Any]:
    if request.get("schema") != "bbk.validator-scope-request.v1":
        raise VerificationEconomyError("VALIDATOR_SCOPE_SCHEMA_INVALID", "expected bbk.validator-scope-request.v1")
    changed = _string_list(request.get("changed_paths", []), "changed_paths")
    selectors = _string_list(request.get("inspected_inputs", []), "inspected_inputs")
    implementation_changed = bool(request.get("validator_implementation_changed", False))
    configuration_changed = bool(request.get("validator_configuration_changed", False))
    invalidation_changed = bool(request.get("invalidation_key_changed", False))
    relevant = sorted(path for path in changed if _path_matches(path, selectors))
    metadata_only = bool(changed) and all(_normalize_relative_path(path).startswith(METADATA_PREFIXES) for path in changed)
    permit = bool(relevant or implementation_changed or configuration_changed or invalidation_changed)
    final_already = bool(request.get("final_pass_already_recorded", False))
    frozen = bool(request.get("candidate_frozen", False))
    broad = permit and frozen and not final_already
    reason = (
        "METADATA_ONLY_NO_INSPECTED_INPUT_CHANGE" if metadata_only and not permit else
        "NO_INSPECTED_INPUT_CHANGE" if not permit else
        "FINAL_PASS_ALREADY_CURRENT" if final_already else
        "CANDIDATE_NOT_FROZEN_TARGETED_ONLY" if not frozen else
        "RELEVANT_INPUT_CHANGED"
    )
    return {
        "schema": "bbk.validator-scope-result.v1",
        "status": "PASS",
        "relevant_changed_paths": relevant,
        "targeted_checks_authorized": permit,
        "broad_final_pass_authorized": broad,
        "maximum_broad_final_passes": 1,
        "reason_code": reason,
    }


def assurance_dispatch(request: Mapping[str, Any]) -> dict[str, Any]:
    if request.get("schema") != "bbk.assurance-dispatch-request.v1":
        raise VerificationEconomyError("ASSURANCE_DISPATCH_SCHEMA_INVALID", "expected bbk.assurance-dispatch-request.v1")
    assertions = request.get("assertions", [])
    if not isinstance(assertions, list):
        raise VerificationEconomyError("ASSURANCE_DISPATCH_INVALID", "assertions must be a list")
    groups: dict[tuple[str, ...], list[str]] = {}
    reviewer: list[str] = []
    for raw in assertions:
        item = _object(raw, "assertions[]")
        assertion_id = _text(item.get("assertion_id"), "assertion_id")
        qualitative = bool(item.get("qualitative_risk"))
        deterministic = bool(item.get("deterministic_evidence_sufficient", False))
        if qualitative and not deterministic:
            reviewer.append(assertion_id)
            continue
        key = tuple(str(item.get(field, "")) for field in (
            "candidate_ref", "method_id", "toolchain_ref", "environment_ref",
            "fixture_ref", "exposure_class", "independence_requirement",
        ))
        groups.setdefault(key, []).append(assertion_id)
    validator_assignments = [
        {"assignment_id": _digest({"group": list(key), "assertions": sorted(ids)}), "assertion_ids": sorted(ids)}
        for key, ids in sorted(groups.items())
    ]
    return {
        "schema": "bbk.assurance-dispatch-result.v1",
        "status": "NO_MATERIAL_ASSURANCE_WORK" if not assertions else "PASS",
        "mode": "INLINE" if not assertions else ("FOCUSED" if reviewer else "INLINE_OR_BOUNDED_FINAL"),
        "validator_assignments": validator_assignments,
        "reviewer_assignments": [
            {"assignment_id": _digest({"qualitative_risk": item}), "assertion_id": item}
            for item in sorted(reviewer)
        ],
        "reviewer_invocation_count": len(reviewer),
        "evidence_operation_count": len(validator_assignments),
    }


def planning_stop(request: Mapping[str, Any]) -> dict[str, Any]:
    if request.get("schema") != "bbk.planning-stop-request.v1":
        raise VerificationEconomyError("PLANNING_STOP_SCHEMA_INVALID", "expected bbk.planning-stop-request.v1")
    unresolved = request.get("unresolved_support_work")
    executable = bool(request.get("executable_work_exists", False))
    if executable and not unresolved:
        return {
            "schema": "bbk.planning-stop-result.v1", "status": "STOP_PLANNING",
            "support_work_authorized": False, "disposition": "PROCEED_TO_EXECUTION",
        }
    if unresolved:
        required = ("material_risk", "unresolved_proposition", "current_evidence_insufficient_because", "smallest_bounded_action")
        missing = [field for field in required if not _fact_present(unresolved.get(field))]
        if missing:
            return {
                "schema": "bbk.planning-stop-result.v1", "status": "NO_MATERIAL_SUPPORT_WORK",
                "support_work_authorized": False, "missing_justification_fields": missing,
                "disposition": "PROCEED_TO_EXECUTION" if executable else "RETURN_TYPED_BLOCKER",
            }
        return {
            "schema": "bbk.planning-stop-result.v1", "status": "BOUNDED_SUPPORT_WORK_AUTHORIZED",
            "support_work_authorized": True, "disposition": unresolved["smallest_bounded_action"],
        }
    return {
        "schema": "bbk.planning-stop-result.v1", "status": "NOT_EXECUTABLE",
        "support_work_authorized": False, "disposition": "ESTABLISH_ONLY_THE_MISSING_DISPATCH_FACT",
    }


def load_receipts(path: str | Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    p = Path(path)
    if not p.exists():
        return []
    if p.is_dir():
        values=[]
        for child in sorted(p.glob("*.json")):
            value=json.loads(child.read_text(encoding="utf-8"))
            if isinstance(value,dict): values.append(value)
        return values
    value=json.loads(p.read_text(encoding="utf-8"))
    if isinstance(value,list): return [dict(item) for item in value if isinstance(item,Mapping)]
    if isinstance(value,dict): return [value]
    raise VerificationEconomyError("VERIFICATION_RECEIPT_INDEX_INVALID", f"{p} must contain an object or list")


def persist_receipt(directory: str | Path, receipt: Mapping[str, Any]) -> Path:
    root=Path(directory).resolve(); root.mkdir(parents=True,exist_ok=True)
    receipt_id=_text(receipt.get("receipt_id"),"receipt_id")
    if not DIGEST_RE.fullmatch(receipt_id):
        raise VerificationEconomyError("VERIFICATION_RECEIPT_ID_INVALID","receipt_id must be sha256:<64 hex>")
    path=root/(receipt_id.removeprefix("sha256:")+".json")
    payload=canonical_json_bytes(dict(receipt))+b"\n"
    if path.exists():
        if path.read_bytes()!=payload:
            raise VerificationEconomyError("VERIFICATION_RECEIPT_COLLISION",f"immutable receipt differs: {path}")
        return path
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"wb") as stream:
        stream.write(payload); stream.flush(); os.fsync(stream.fileno())
    return path


def _load_request(path: str | None) -> dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8") if path else __import__("sys").stdin.read()
    value=json.loads(text)
    if not isinstance(value,dict):
        raise VerificationEconomyError("VERIFICATION_REQUEST_INVALID","request must be a JSON object")
    return value


def main(argv: Iterable[str] | None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("dispatch","pre-check","post-check","mechanical","validator-scope","assurance","planning-stop"))
    parser.add_argument("--request")
    parser.add_argument("--receipts")
    parser.add_argument("--receipt-dir")
    args=parser.parse_args(list(argv) if argv is not None else None)
    try:
        request=_load_request(args.request)
        if args.action=="dispatch": result=dispatch_admission(request)
        elif args.action=="pre-check": result=pre_check(request,load_receipts(args.receipts))
        elif args.action=="post-check":
            result=create_receipt(request,_object(request.get("result"),"result"))
            if args.receipt_dir: result={**result,"receipt_path":str(persist_receipt(args.receipt_dir,result))}
        elif args.action=="mechanical": result=mechanical_transition(request)
        elif args.action=="validator-scope": result=validator_scope(request)
        elif args.action=="assurance": result=assurance_dispatch(request)
        else: result=planning_stop(request)
        print(json.dumps(result,indent=2,sort_keys=True))
        return 0
    except (VerificationEconomyError, OSError, json.JSONDecodeError) as exc:
        code=getattr(exc,"code","VERIFICATION_ECONOMY_ERROR")
        message=getattr(exc,"message",str(exc))
        print(json.dumps({"status":"BLOCK","reason_code":code,"message":message},sort_keys=True))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
