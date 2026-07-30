#!/usr/bin/env python3
"""BBK alpha.7 State–Decision–Effect design validation and rendering.

This module is deliberately domain-neutral. It validates explicit state,
decision, transition, effect, invariant, formalization, trace, and planned-versus-
actual contracts. It does not prove project correctness or grant effect authority.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

try:
    from contracts import canonical_digest, validate_slice, validate_structure
except ModuleNotFoundError:  # installed adjacent to bbk.py
    from .contracts import canonical_digest, validate_slice, validate_structure  # type: ignore

APPLICABILITY = {"NONE", "INLINE", "CONTRACT"}
STATE_STRATEGIES = {"STATELESS", "SINGLE_SUM", "PRODUCT_OF_SUMS", "DECISION_TABLE", "EXTERNAL_CANONICAL_CONTRACT", "OTHER_WITH_RATIONALE"}
DETERMINISM = {"PURE_DETERMINISTIC", "DETERMINISTIC_WITH_EXPLICIT_CONTEXT", "LEGACY_EFFECTFUL_WITH_CONTAINMENT"}
DECISION_OUTPUTS = {"NEXT_STATE", "DOMAIN_FACTS", "EFFECT_INTENTS", "REJECTION", "NO_CHANGE"}
FORMALIZATION = {"NONE", "TRANSITION_TABLE", "STATE_MACHINE_PROPERTIES", "FORMAL_EXECUTABLE_MODEL"}
INVARIANT_CLASSES = {"representation", "transition", "authority", "effect", "recovery", "temporal-order", "safety-feared-event", "idempotency-duplicate", "lifecycle-closure"}
TRACE_CLASSES = {"legal-path", "illegal-transition", "retry", "duplicate-delivery", "cancellation", "timeout", "partial-completion", "ambiguous-acknowledgement", "crash-before-effect", "crash-after-effect-before-receipt", "crash-after-semantic-commit", "stale-result", "replacement-fence", "degraded-recovery"}


def _dict(value: Any, where: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{where} must be an object")
        return {}
    return value


def _list(value: Any, where: str, errors: list[str]) -> list[Any]:
    if not isinstance(value, list):
        errors.append(f"{where} must be an array")
        return []
    return value


def _text(value: Any, where: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{where} must be a non-empty string")
        return ""
    return value


def _required(obj: dict[str, Any], fields: Iterable[str], where: str, errors: list[str]) -> None:
    for field in fields:
        if field not in obj:
            errors.append(f"{where}.{field} is required")


def _unique(items: list[Any], field: str, where: str, errors: list[str]) -> set[str]:
    seen: set[str] = set()
    for index, value in enumerate(items):
        item = _dict(value, f"{where}[{index}]", errors)
        identifier = item.get(field)
        if not isinstance(identifier, str) or not identifier.strip():
            errors.append(f"{where}[{index}].{field} must be a non-empty string")
        elif identifier in seen:
            errors.append(f"duplicate {where}.{field}: {identifier}")
        else:
            seen.add(identifier)
    return seen


def _strings(value: Any, where: str, errors: list[str], *, nonempty: bool = False) -> list[str]:
    values = _list(value, where, errors)
    result: list[str] = []
    for index, item in enumerate(values):
        text = _text(item, f"{where}[{index}]", errors)
        if text:
            result.append(text)
    if nonempty and not result:
        errors.append(f"{where} must contain at least one value")
    return result


def validate_state_decision_effect(data: Any) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    obj = _dict(data, "design", errors)
    _required(obj, ["schema", "designId", "revision", "title", "status", "applicability", "rationale", "scopeRefs", "sourceRequirementRefs", "sourceInterfaceRefs", "sourceDecisionRefs", "fixedDecisionRefs", "delegatedFreedom", "canonicalState", "decisionBoundaries", "transitionRules", "effectContracts", "invariants", "formalization", "traceFixtureRefs", "reviewPolicy"], "design", errors)
    if obj.get("schema") != "bbk.state-decision-effect-design.v1":
        errors.append("design.schema must equal bbk.state-decision-effect-design.v1")
    for field in ("designId", "revision", "title", "rationale"):
        _text(obj.get(field), f"design.{field}", errors)
    if obj.get("status") not in {"draft", "in-review", "accepted", "superseded"}:
        errors.append("design.status is invalid")
    applicability = str(obj.get("applicability", ""))
    if applicability not in APPLICABILITY:
        errors.append("design.applicability must be NONE, INLINE, or CONTRACT")
    for field in ("scopeRefs", "sourceRequirementRefs", "sourceInterfaceRefs", "sourceDecisionRefs", "fixedDecisionRefs", "delegatedFreedom", "traceFixtureRefs"):
        _strings(obj.get(field), f"design.{field}", errors, nonempty=(field == "scopeRefs"))

    canonical = _dict(obj.get("canonicalState"), "design.canonicalState", errors)
    _required(canonical, ["strategy", "semanticOwner", "dimensions", "derivedFacts", "observations", "persistenceBoundary", "duplicateStateProhibitions", "versionFenceSemantics"], "design.canonicalState", errors)
    strategy = canonical.get("strategy")
    if strategy not in STATE_STRATEGIES:
        errors.append("design.canonicalState.strategy is invalid")
    owner = _text(canonical.get("semanticOwner"), "design.canonicalState.semanticOwner", errors)
    dimensions = _list(canonical.get("dimensions"), "design.canonicalState.dimensions", errors)
    dimension_ids = _unique(dimensions, "dimensionId", "design.canonicalState.dimensions", errors)
    value_ids: dict[str, set[str]] = {}
    authoritative_sources: set[str] = set()
    for index, raw in enumerate(dimensions):
        item = _dict(raw, f"design.canonicalState.dimensions[{index}]", errors)
        _required(item, ["dimensionId", "purpose", "mutuallyExclusive", "independentOf", "owner", "values", "initialization", "terminalOrReset", "persistence"], f"design.canonicalState.dimensions[{index}]", errors)
        dimension_id = _text(item.get("dimensionId"), f"design.canonicalState.dimensions[{index}].dimensionId", errors)
        _text(item.get("purpose"), f"design.canonicalState.dimensions[{index}].purpose", errors)
        if not isinstance(item.get("mutuallyExclusive"), bool):
            errors.append(f"design.canonicalState.dimensions[{index}].mutuallyExclusive must be boolean")
        independent = _strings(item.get("independentOf"), f"design.canonicalState.dimensions[{index}].independentOf", errors)
        _text(item.get("owner"), f"design.canonicalState.dimensions[{index}].owner", errors)
        values = _list(item.get("values"), f"design.canonicalState.dimensions[{index}].values", errors)
        ids = _unique(values, "id", f"design.canonicalState.dimensions[{index}].values", errors)
        value_ids[dimension_id] = ids
        for value_index, raw_value in enumerate(values):
            value = _dict(raw_value, f"design.canonicalState.dimensions[{index}].values[{value_index}]", errors)
            _required(value, ["id", "requiredData", "prohibitedData"], f"design.canonicalState.dimensions[{index}].values[{value_index}]", errors)
            _strings(value.get("requiredData"), f"design.canonicalState.dimensions[{index}].values[{value_index}].requiredData", errors)
            _strings(value.get("prohibitedData"), f"design.canonicalState.dimensions[{index}].values[{value_index}].prohibitedData", errors)
            overlap = set(value.get("requiredData") or []) & set(value.get("prohibitedData") or [])
            if overlap:
                errors.append(f"dimension {dimension_id} value {value.get('id')} requires and prohibits {sorted(overlap)}")
        _text(item.get("initialization"), f"design.canonicalState.dimensions[{index}].initialization", errors)
        _text(item.get("terminalOrReset"), f"design.canonicalState.dimensions[{index}].terminalOrReset", errors)
        if item.get("persistence") not in {"persisted", "reconstructed", "derived", "none"}:
            errors.append(f"design.canonicalState.dimensions[{index}].persistence is invalid")
        if item.get("persistence") != "derived":
            authoritative_sources.add(dimension_id)
        for other in independent:
            if other == dimension_id:
                errors.append(f"dimension {dimension_id} cannot be independent of itself")
    for index, raw in enumerate(dimensions):
        item = raw if isinstance(raw, dict) else {}
        for other in item.get("independentOf", []) or []:
            if other not in dimension_ids:
                errors.append(f"dimension {item.get('dimensionId')} references unknown independent dimension {other}")
    if strategy == "STATELESS" and dimensions:
        errors.append("STATELESS canonical state must not declare dimensions")
    if strategy == "SINGLE_SUM" and len(dimensions) != 1:
        errors.append("SINGLE_SUM canonical state requires exactly one dimension")
    if strategy == "PRODUCT_OF_SUMS" and len(dimensions) < 2:
        errors.append("PRODUCT_OF_SUMS requires at least two dimensions")

    derived = _list(canonical.get("derivedFacts"), "design.canonicalState.derivedFacts", errors)
    derived_ids = _unique(derived, "id", "design.canonicalState.derivedFacts", errors)
    for index, raw in enumerate(derived):
        item = _dict(raw, f"design.canonicalState.derivedFacts[{index}]", errors)
        _required(item, ["id", "statement", "sourceRefs"], f"design.canonicalState.derivedFacts[{index}]", errors)
        _text(item.get("statement"), f"design.canonicalState.derivedFacts[{index}].statement", errors)
        _strings(item.get("sourceRefs"), f"design.canonicalState.derivedFacts[{index}].sourceRefs", errors, nonempty=True)
        if item.get("id") in authoritative_sources:
            errors.append(f"fact {item.get('id')} is both authoritative state and derived")
    observations = _list(canonical.get("observations"), "design.canonicalState.observations", errors)
    observation_ids = _unique(observations, "id", "design.canonicalState.observations", errors)
    for index, raw in enumerate(observations):
        item = _dict(raw, f"design.canonicalState.observations[{index}]", errors)
        _required(item, ["id", "source", "freshnessPolicy", "authority"], f"design.canonicalState.observations[{index}]", errors)
        for field in ("source", "freshnessPolicy", "authority"):
            _text(item.get(field), f"design.canonicalState.observations[{index}].{field}", errors)
    _text(canonical.get("persistenceBoundary"), "design.canonicalState.persistenceBoundary", errors)
    _strings(canonical.get("duplicateStateProhibitions"), "design.canonicalState.duplicateStateProhibitions", errors)
    _text(canonical.get("versionFenceSemantics"), "design.canonicalState.versionFenceSemantics", errors)

    boundaries = _list(obj.get("decisionBoundaries"), "design.decisionBoundaries", errors)
    boundary_ids = _unique(boundaries, "boundaryId", "design.decisionBoundaries", errors)
    for index, raw in enumerate(boundaries):
        item = _dict(raw, f"design.decisionBoundaries[{index}]", errors)
        _required(item, ["boundaryId", "owner", "stateInputs", "inputTypes", "outputs", "determinism", "hiddenDependencyPolicy", "contextHandling", "expectedFailures", "authorityValidation", "freshnessValidation", "executionMode", "ioClaims"], f"design.decisionBoundaries[{index}]", errors)
        _text(item.get("owner"), f"design.decisionBoundaries[{index}].owner", errors)
        state_inputs = _strings(item.get("stateInputs"), f"design.decisionBoundaries[{index}].stateInputs", errors)
        for ref in state_inputs:
            if ref not in dimension_ids and ref not in derived_ids and ref not in observation_ids:
                errors.append(f"decision boundary {item.get('boundaryId')} references unknown state input {ref}")
        _strings(item.get("inputTypes"), f"design.decisionBoundaries[{index}].inputTypes", errors, nonempty=True)
        outputs = _strings(item.get("outputs"), f"design.decisionBoundaries[{index}].outputs", errors, nonempty=True)
        for output in outputs:
            if output not in DECISION_OUTPUTS:
                errors.append(f"decision boundary {item.get('boundaryId')} has invalid output {output}")
        determinism = item.get("determinism")
        if determinism not in DETERMINISM:
            errors.append(f"decision boundary {item.get('boundaryId')} determinism is invalid")
        _text(item.get("hiddenDependencyPolicy"), f"design.decisionBoundaries[{index}].hiddenDependencyPolicy", errors)
        context = _dict(item.get("contextHandling"), f"design.decisionBoundaries[{index}].contextHandling", errors)
        for field in ("clock", "randomness", "configuration", "environment", "externalData"):
            _text(context.get(field), f"design.decisionBoundaries[{index}].contextHandling.{field}", errors)
        _strings(item.get("expectedFailures"), f"design.decisionBoundaries[{index}].expectedFailures", errors)
        _text(item.get("authorityValidation"), f"design.decisionBoundaries[{index}].authorityValidation", errors)
        _text(item.get("freshnessValidation"), f"design.decisionBoundaries[{index}].freshnessValidation", errors)
        if item.get("executionMode") not in {"transactional", "staged", "compensated", "none"}:
            errors.append(f"decision boundary {item.get('boundaryId')} executionMode is invalid")
        io_claims = _strings(item.get("ioClaims"), f"design.decisionBoundaries[{index}].ioClaims", errors)
        if determinism == "PURE_DETERMINISTIC" and io_claims:
            errors.append(f"pure decision boundary {item.get('boundaryId')} may not claim I/O")
        if determinism == "LEGACY_EFFECTFUL_WITH_CONTAINMENT" and not io_claims:
            warnings.append(f"legacy effectful boundary {item.get('boundaryId')} declares no contained I/O")

    effects = _list(obj.get("effectContracts"), "design.effectContracts", errors)
    effect_ids = _unique(effects, "effectId", "design.effectContracts", errors)
    for index, raw in enumerate(effects):
        item = _dict(raw, f"design.effectContracts[{index}]", errors)
        _required(item, ["effectId", "intent", "executor", "requestAuthority", "executionAuthority", "target", "preconditions", "idempotency", "duplicateBehavior", "retryPolicy", "timeoutMeaning", "cancellationSemantics", "orderingRequirements", "partialCompletion", "irreversibleBoundary", "resultReceipt", "ambiguousAcknowledgement", "durableAfterInterruption", "recoveryOwner", "observability", "compensationPolicy", "externalRestrictions"], f"design.effectContracts[{index}]", errors)
        for field in ("intent", "executor", "target", "duplicateBehavior", "retryPolicy", "timeoutMeaning", "cancellationSemantics", "orderingRequirements", "partialCompletion", "irreversibleBoundary", "resultReceipt", "ambiguousAcknowledgement", "durableAfterInterruption", "recoveryOwner", "compensationPolicy"):
            _text(item.get(field), f"design.effectContracts[{index}].{field}", errors)
        for field in ("requestAuthority", "executionAuthority", "preconditions", "observability", "externalRestrictions"):
            _strings(item.get(field), f"design.effectContracts[{index}].{field}", errors, nonempty=field in {"requestAuthority", "executionAuthority"})
        idem = _dict(item.get("idempotency"), f"design.effectContracts[{index}].idempotency", errors)
        if idem.get("classification") not in {"idempotent", "deduplicated", "non-idempotent"}:
            errors.append(f"design.effectContracts[{index}].idempotency.classification is invalid")
        if idem.get("classification") in {"idempotent", "deduplicated"}:
            _text(idem.get("key"), f"design.effectContracts[{index}].idempotency.key", errors)
        if idem.get("classification") == "non-idempotent" and not str(item.get("compensationPolicy", "")).strip():
            errors.append(f"non-idempotent effect {item.get('effectId')} requires containment/compensation policy")

    invariants = _list(obj.get("invariants"), "design.invariants", errors)
    invariant_ids = _unique(invariants, "invariantId", "design.invariants", errors)
    for index, raw in enumerate(invariants):
        item = _dict(raw, f"design.invariants[{index}]", errors)
        _required(item, ["invariantId", "class", "statement", "verificationMethods", "assertionRefs"], f"design.invariants[{index}]", errors)
        if item.get("class") not in INVARIANT_CLASSES:
            errors.append(f"design.invariants[{index}].class is invalid")
        _text(item.get("statement"), f"design.invariants[{index}].statement", errors)
        methods = _strings(item.get("verificationMethods"), f"design.invariants[{index}].verificationMethods", errors, nonempty=True)
        _strings(item.get("assertionRefs"), f"design.invariants[{index}].assertionRefs", errors)
        if not methods:
            errors.append(f"invariant {item.get('invariantId')} has no verification method")

    transitions = _list(obj.get("transitionRules"), "design.transitionRules", errors)
    _unique(transitions, "ruleId", "design.transitionRules", errors)
    for index, raw in enumerate(transitions):
        item = _dict(raw, f"design.transitionRules[{index}]", errors)
        _required(item, ["ruleId", "dimensionRef", "fromPattern", "inputType", "guards", "authorityRequirements", "toPattern", "domainFacts", "effectIntentRefs", "rejection", "invariantRefs"], f"design.transitionRules[{index}]", errors)
        dimension_ref = _text(item.get("dimensionRef"), f"design.transitionRules[{index}].dimensionRef", errors)
        if dimension_ref and dimension_ref not in dimension_ids:
            errors.append(f"transition {item.get('ruleId')} references unknown dimension {dimension_ref}")
        for field in ("fromPattern", "inputType", "toPattern", "rejection"):
            _text(item.get(field), f"design.transitionRules[{index}].{field}", errors)
        for field in ("guards", "authorityRequirements", "domainFacts", "effectIntentRefs", "invariantRefs"):
            refs = _strings(item.get(field), f"design.transitionRules[{index}].{field}", errors)
            if field == "effectIntentRefs":
                for ref in refs:
                    if ref not in effect_ids:
                        errors.append(f"transition {item.get('ruleId')} references unknown effect {ref}")
            if field == "invariantRefs":
                for ref in refs:
                    if ref not in invariant_ids:
                        errors.append(f"transition {item.get('ruleId')} references unknown invariant {ref}")

    formal = _dict(obj.get("formalization"), "design.formalization", errors)
    _required(formal, ["level", "required", "rationale", "tool", "modelRef", "modelDigest", "assumptions", "properties", "exploredBounds", "mappingRefs", "limitations", "divergenceHandling"], "design.formalization", errors)
    level = formal.get("level")
    if level not in FORMALIZATION:
        errors.append("design.formalization.level is invalid")
    if not isinstance(formal.get("required"), bool):
        errors.append("design.formalization.required must be boolean")
    _text(formal.get("rationale"), "design.formalization.rationale", errors)
    for field in ("assumptions", "properties", "exploredBounds", "mappingRefs", "limitations"):
        _strings(formal.get(field), f"design.formalization.{field}", errors)
    _text(formal.get("divergenceHandling"), "design.formalization.divergenceHandling", errors)
    if level == "FORMAL_EXECUTABLE_MODEL":
        _text(formal.get("tool"), "design.formalization.tool", errors)
        _text(formal.get("modelRef"), "design.formalization.modelRef", errors)
        digest = formal.get("modelDigest")
        if not isinstance(digest, str) or not __import__("re").fullmatch(r"[0-9a-f]{64}", digest):
            errors.append("FORMAL_EXECUTABLE_MODEL requires a 64-character modelDigest")
    if formal.get("required") and level == "NONE":
        errors.append("required formalization may not use level NONE")

    review = _dict(obj.get("reviewPolicy"), "design.reviewPolicy", errors)
    _required(review, ["required", "assuranceTier", "reviewerLenses", "acceptanceCriteria"], "design.reviewPolicy", errors)
    if not isinstance(review.get("required"), bool):
        errors.append("design.reviewPolicy.required must be boolean")
    if review.get("assuranceTier") not in {"routine", "material", "consequential", "critical"}:
        errors.append("design.reviewPolicy.assuranceTier is invalid")
    _strings(review.get("reviewerLenses"), "design.reviewPolicy.reviewerLenses", errors)
    _strings(review.get("acceptanceCriteria"), "design.reviewPolicy.acceptanceCriteria", errors, nonempty=applicability == "CONTRACT")

    triggers = set(str(value).casefold() for value in (obj.get("triggerIndicators") or []))
    high_risk_tokens = {"retry", "replay", "recovery", "cancellation", "concurrency", "lease", "fence", "external-effect", "ambiguous-acknowledgement", "irreversible"}
    if applicability == "NONE" and triggers & high_risk_tokens:
        errors.append("State–Decision–Effect triggers are present but applicability is NONE")
    if applicability == "CONTRACT":
        if strategy == "STATELESS" and not effects:
            warnings.append("CONTRACT applicability with stateless/no-effect design may be disproportionate")
        if not boundaries:
            errors.append("CONTRACT applicability requires at least one decision boundary")
        if not invariants:
            errors.append("CONTRACT applicability requires at least one invariant")
    if effects and not boundaries:
        errors.append("effect contracts require at least one decision boundary")
    if owner and dimensions:
        divergent = {str(item.get("owner")) for item in dimensions if isinstance(item, dict) and item.get("owner") and item.get("owner") != owner}
        if divergent:
            warnings.append(f"state dimensions use owners different from canonical semantic owner: {sorted(divergent)}")

    return {
        "kind": "state-decision-effect-design",
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "digest": canonical_digest(obj) if isinstance(data, dict) else None,
        "summary": {"applicability": applicability or None, "strategy": strategy, "dimensions": len(dimensions), "decisionBoundaries": len(boundaries), "effects": len(effects), "transitions": len(transitions), "invariants": len(invariants), "formalization": level},
    }


def validate_transition_trace(data: Any) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    obj = _dict(data, "trace", errors)
    _required(obj, ["schema", "traceId", "traceClass", "subjectRef", "designRevision", "modelRef", "initialState", "steps", "permittedVariation", "faultPlan", "environmentIdentity", "evidenceRequirements"], "trace", errors)
    if obj.get("schema") != "bbk.state-transition-trace.v1":
        errors.append("trace.schema must equal bbk.state-transition-trace.v1")
    for field in ("traceId", "subjectRef", "designRevision", "environmentIdentity"):
        _text(obj.get(field), f"trace.{field}", errors)
    if obj.get("traceClass") not in TRACE_CLASSES:
        errors.append("trace.traceClass is invalid")
    _dict(obj.get("initialState"), "trace.initialState", errors)
    steps = _list(obj.get("steps"), "trace.steps", errors)
    if not steps:
        errors.append("trace.steps must not be empty")
    for index, raw in enumerate(steps):
        item = _dict(raw, f"trace.steps[{index}]", errors)
        _required(item, ["input", "expectedDecision", "expectedNextState", "expectedDomainFacts", "expectedEffectIntents", "expectedRejection", "expectedInvariantResults"], f"trace.steps[{index}]", errors)
        _dict(item.get("input"), f"trace.steps[{index}].input", errors)
        _text(item.get("expectedDecision"), f"trace.steps[{index}].expectedDecision", errors)
        _dict(item.get("expectedNextState"), f"trace.steps[{index}].expectedNextState", errors)
        for field in ("expectedDomainFacts", "expectedEffectIntents", "expectedInvariantResults"):
            _list(item.get(field), f"trace.steps[{index}].{field}", errors)
        if item.get("expectedRejection") is not None and not isinstance(item.get("expectedRejection"), str):
            errors.append(f"trace.steps[{index}].expectedRejection must be string or null")
    _list(obj.get("permittedVariation"), "trace.permittedVariation", errors)
    _list(obj.get("faultPlan"), "trace.faultPlan", errors)
    _list(obj.get("evidenceRequirements"), "trace.evidenceRequirements", errors)
    if obj.get("traceClass") in {"retry", "duplicate-delivery", "cancellation", "timeout", "partial-completion", "ambiguous-acknowledgement", "replacement-fence", "degraded-recovery"} and not obj.get("faultPlan"):
        warnings.append("fault-oriented trace has an empty faultPlan")
    return {"kind": "state-transition-trace", "valid": not errors, "errors": errors, "warnings": warnings, "digest": canonical_digest(obj) if isinstance(data, dict) else None, "traceClass": obj.get("traceClass")}


def validate_transition_trace_set(values: Any, design: dict[str, Any] | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    traces = _list(values, "traces", errors)
    results = [validate_transition_trace(value) for value in traces]
    for result in results:
        errors.extend(result["errors"])
        warnings.extend(result["warnings"])
    ids = [value.get("traceId") for value in traces if isinstance(value, dict)]
    if len(ids) != len(set(ids)):
        errors.append("trace IDs must be unique")
    if design is not None:
        dresult = validate_state_decision_effect(design)
        if not dresult["valid"]:
            errors.append("referenced State–Decision–Effect design is invalid")
        revision = design.get("revision")
        expected_refs = set(design.get("traceFixtureRefs") or [])
        observed = set(ids)
        for value in traces:
            if isinstance(value, dict) and value.get("designRevision") != revision:
                errors.append(f"trace {value.get('traceId')} designRevision does not match design revision {revision}")
        missing = expected_refs - observed
        if missing:
            errors.append(f"design references missing traces: {sorted(missing)}")
    classes = {value.get("traceClass") for value in traces if isinstance(value, dict)}
    return {"kind": "state-transition-trace-set", "valid": not errors, "errors": errors, "warnings": warnings, "traceCount": len(traces), "traceClasses": sorted(str(x) for x in classes if x), "digest": canonical_digest(traces)}


def _structure_v1_projection(obj: dict[str, Any]) -> dict[str, Any]:
    projected = json.loads(json.dumps(obj))
    projected["schema"] = "bbk.implementation-structure-contract.v1"
    projected.pop("stateDecisionEffectDesign", None)
    return projected


def validate_structure_v2(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"kind": "implementation-structure-contract", "valid": False, "errors": ["contract must be an object"], "warnings": [], "digest": None}
    if data.get("schema") == "bbk.implementation-structure-contract.v1":
        result = validate_structure(data)
        result["version"] = "v1"
        result["stateDecisionEffect"] = "not-present-legacy"
        return result
    if data.get("schema") != "bbk.implementation-structure-contract.v2":
        return {"kind": "implementation-structure-contract", "valid": False, "errors": ["contract.schema must be bbk.implementation-structure-contract.v1 or v2"], "warnings": [], "digest": canonical_digest(data)}
    base = validate_structure(_structure_v1_projection(data))
    sde = validate_state_decision_effect(data.get("stateDecisionEffectDesign"))
    errors = list(base["errors"]) + list(sde["errors"])
    warnings = list(base["warnings"]) + list(sde["warnings"])
    fixed_ids = {item.get("id") for item in (data.get("decisions") or {}).get("fixed", []) if isinstance(item, dict)}
    missing = [ref for ref in (data.get("stateDecisionEffectDesign") or {}).get("fixedDecisionRefs", []) if ref not in fixed_ids]
    if missing:
        errors.append(f"state/effect design references fixed decisions absent from parent contract: {missing}")
    subject_refs = set((data.get("subject") or {}).get("scopeRefs", []))
    design_scope = set((data.get("stateDecisionEffectDesign") or {}).get("scopeRefs", []))
    if design_scope and subject_refs and not design_scope.issubset(subject_refs):
        warnings.append("state/effect scope includes references outside parent structure subject scope")
    return {"kind": "implementation-structure-contract", "version": "v2", "valid": not errors, "errors": errors, "warnings": warnings, "digest": canonical_digest(data), "stateDecisionEffect": sde}


def _slice_v1_projection(obj: dict[str, Any]) -> dict[str, Any]:
    projected = json.loads(json.dumps(obj))
    projected["schema"] = "bbk.execution-slice.v1"
    for field in ("stateDecisionEffectRefs", "stateTransitionTouchpoints", "effectBoundaryTouchpoints", "traceFixtureRefs", "formalModelRefs"):
        projected.pop(field, None)
    return projected


def validate_slice_v2(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"kind": "execution-slice", "valid": False, "errors": ["slice must be an object"], "warnings": [], "digest": None}
    if data.get("schema") == "bbk.execution-slice.v1":
        result = validate_slice(data)
        result["version"] = "v1"
        return result
    if data.get("schema") != "bbk.execution-slice.v2":
        return {"kind": "execution-slice", "valid": False, "errors": ["slice.schema must be bbk.execution-slice.v1 or v2"], "warnings": [], "digest": canonical_digest(data)}
    base = validate_slice(_slice_v1_projection(data))
    errors = list(base["errors"])
    warnings = list(base["warnings"])
    for field in ("stateDecisionEffectRefs", "stateTransitionTouchpoints", "effectBoundaryTouchpoints", "traceFixtureRefs", "formalModelRefs"):
        values = data.get(field)
        if not isinstance(values, list):
            errors.append(f"slice.{field} must be an array")
        elif any(not isinstance(value, str) or not value.strip() for value in values):
            errors.append(f"slice.{field} entries must be non-empty strings")
    if data.get("stateDecisionEffectRefs") and not data.get("stateTransitionTouchpoints"):
        warnings.append("slice references state/effect design but declares no stateTransitionTouchpoints")
    if data.get("effectBoundaryTouchpoints") and not data.get("stateDecisionEffectRefs"):
        warnings.append("slice declares effect touchpoints without a state/effect design reference")
    return {"kind": "execution-slice", "version": "v2", "valid": not errors, "errors": errors, "warnings": warnings, "digest": canonical_digest(data)}


def validate_structure_review_v2(data: Any) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    obj = _dict(data, "review", errors)
    _required(obj, ["schema", "reviewId", "subjectRef", "subjectDigest", "reviewer", "coverage", "findings", "stateDecisionEffectFindings", "inventoryStatus", "disposition", "limitations"], "review", errors)
    if obj.get("schema") != "bbk.structure-review-result.v2":
        errors.append("review.schema must equal bbk.structure-review-result.v2")
    for field in ("reviewId", "subjectRef", "reviewer"):
        _text(obj.get(field), f"review.{field}", errors)
    digest = obj.get("subjectDigest")
    if not isinstance(digest, str) or not __import__("re").fullmatch(r"[0-9a-f]{64}", digest):
        errors.append("review.subjectDigest must be a lowercase SHA-256 digest")
    _strings(obj.get("coverage"), "review.coverage", errors, nonempty=True)
    for field in ("findings", "stateDecisionEffectFindings"):
        items = _list(obj.get(field), f"review.{field}", errors)
        _unique(items, "id", f"review.{field}", errors)
        for index, raw in enumerate(items):
            item = _dict(raw, f"review.{field}[{index}]", errors)
            _required(item, ["id", "class", "statement", "evidence", "route"], f"review.{field}[{index}]", errors)
            if item.get("class") not in {"blocker", "material", "advisory", "observation"}:
                errors.append(f"review.{field}[{index}].class is invalid")
            for name in ("statement", "evidence", "route"):
                _text(item.get(name), f"review.{field}[{index}].{name}", errors)
            if field == "stateDecisionEffectFindings" and item.get("divergenceClass") not in {"within-delegated-freedom", "advisory-drift", "material-divergence", "blocked-unknown"}:
                errors.append(f"review.{field}[{index}].divergenceClass is invalid")
    if obj.get("inventoryStatus") not in {"COMPLETE", "PARTIAL", "BLOCKED", "UNKNOWN"}:
        errors.append("review.inventoryStatus is invalid")
    if obj.get("disposition") not in {"accept", "accept-with-advisories", "revise", "blocked", "inconclusive"}:
        errors.append("review.disposition is invalid")
    _strings(obj.get("limitations"), "review.limitations", errors)
    if obj.get("inventoryStatus") in {"BLOCKED", "UNKNOWN"} and obj.get("disposition") not in {"blocked", "inconclusive"}:
        errors.append("blocked/unknown inventory cannot produce an accepting disposition")
    if any(item.get("class") == "blocker" for item in [*(obj.get("findings") or []), *(obj.get("stateDecisionEffectFindings") or [])] if isinstance(item, dict)) and obj.get("disposition") in {"accept", "accept-with-advisories"}:
        errors.append("open blocker finding cannot produce an accepting disposition")
    return {"kind": "structure-review-result", "version": "v2", "valid": not errors, "errors": errors, "warnings": warnings, "digest": canonical_digest(obj) if isinstance(data, dict) else None}


def compare_state_effect_inventory(design: dict[str, Any], inventory: dict[str, Any]) -> dict[str, Any]:
    """Produce deterministic planned-versus-actual findings from a bounded inventory.

    Inventory is intentionally simple and profile-produced. Unknown inventory blocks
    conformance rather than being treated as a pass.
    """
    validation = validate_state_decision_effect(design)
    findings: list[dict[str, Any]] = []
    status = inventory.get("status", "UNKNOWN") if isinstance(inventory, dict) else "UNKNOWN"
    if not validation["valid"]:
        return {"schema": "bbk.structure-review-result.v2", "reviewId": "generated-invalid-design", "subjectRef": design.get("designId", "unknown"), "subjectDigest": canonical_digest(design), "reviewer": "bbk-deterministic-inventory-review", "coverage": ["state-decision-effect"], "findings": [], "stateDecisionEffectFindings": [{"id": "SDE-DESIGN-INVALID", "class": "blocker", "divergenceClass": "blocked-unknown", "statement": "The planned State–Decision–Effect design is invalid.", "evidence": "; ".join(validation["errors"]), "route": "repair the design contract"}], "inventoryStatus": "BLOCKED", "disposition": "blocked", "limitations": []}
    if status not in {"COMPLETE", "PARTIAL"}:
        findings.append({"id": "SDE-INVENTORY-UNKNOWN", "class": "blocker", "divergenceClass": "blocked-unknown", "statement": "Actual state/effect inventory is unavailable.", "evidence": str(inventory.get("reason", "no complete inventory")) if isinstance(inventory, dict) else "inventory not an object", "route": "produce a qualified profile inventory"})
    planned_owner = (design.get("canonicalState") or {}).get("semanticOwner")
    actual_owners = set(inventory.get("canonicalStateOwners", []) if isinstance(inventory, dict) else [])
    if actual_owners and planned_owner not in actual_owners:
        findings.append({"id": "SDE-OWNER-MOVED", "class": "blocker", "divergenceClass": "material-divergence", "statement": "Canonical semantic state ownership moved or is absent.", "evidence": f"planned={planned_owner}; actual={sorted(actual_owners)}", "route": "architecture/change review"})
    if len(actual_owners) > 1:
        findings.append({"id": "SDE-SHADOW-STATE", "class": "blocker", "divergenceClass": "material-divergence", "statement": "Several independently mutable canonical state owners are reported.", "evidence": ", ".join(sorted(actual_owners)), "route": "restore one semantic owner or define an explicit shared-authority protocol"})
    planned_boundaries = {item.get("boundaryId") for item in design.get("decisionBoundaries", []) if isinstance(item, dict)}
    actual_boundaries = set(inventory.get("decisionBoundaryIds", []) if isinstance(inventory, dict) else [])
    for missing in sorted(planned_boundaries - actual_boundaries):
        findings.append({"id": f"SDE-MISSING-DECISION-{missing}", "class": "material", "divergenceClass": "material-divergence", "statement": f"Planned decision boundary {missing} is absent from the actual inventory.", "evidence": "profile inventory", "route": "implementation or design review"})
    planned_effects = {item.get("effectId") for item in design.get("effectContracts", []) if isinstance(item, dict)}
    actual_effects = set(inventory.get("effectExecutorIds", []) if isinstance(inventory, dict) else [])
    for extra in sorted(actual_effects - planned_effects):
        findings.append({"id": f"SDE-HIDDEN-EFFECT-{extra}", "class": "blocker", "divergenceClass": "material-divergence", "statement": f"Actual effect path {extra} is not declared by the design.", "evidence": "profile inventory", "route": "contain or formally add the effect through change control"})
    hidden = inventory.get("hiddenDependencies", []) if isinstance(inventory, dict) else []
    for index, dependency in enumerate(hidden):
        findings.append({"id": f"SDE-HIDDEN-DEPENDENCY-{index+1}", "class": "material", "divergenceClass": "material-divergence", "statement": "Decision boundary reads an undeclared dependency.", "evidence": str(dependency), "route": "pass it explicitly as context or revise the design"})
    advisory = inventory.get("advisoryDrift", []) if isinstance(inventory, dict) else []
    for index, value in enumerate(advisory):
        findings.append({"id": f"SDE-ADVISORY-{index+1}", "class": "advisory", "divergenceClass": "advisory-drift", "statement": str(value), "evidence": "profile inventory", "route": "record in a successor design when convenient"})
    blockers = any(item["class"] == "blocker" for item in findings)
    material = any(item["class"] == "material" for item in findings)
    disposition = "blocked" if status not in {"COMPLETE", "PARTIAL"} else "revise" if blockers or material else "accept-with-advisories" if findings else "accept"
    return {"schema": "bbk.structure-review-result.v2", "reviewId": f"SDE-REVIEW-{canonical_digest([design, inventory])[:16]}", "subjectRef": design.get("designId", "unknown"), "subjectDigest": canonical_digest(design), "reviewer": "bbk-deterministic-inventory-review", "coverage": ["canonical-state", "decision-boundaries", "effect-boundaries", "hidden-dependencies"], "findings": [], "stateDecisionEffectFindings": findings, "inventoryStatus": status if status in {"COMPLETE", "PARTIAL", "BLOCKED", "UNKNOWN"} else "UNKNOWN", "disposition": disposition, "limitations": list(inventory.get("limitations", []) if isinstance(inventory, dict) else [])}


def markdown_state_decision_effect(data: dict[str, Any]) -> str:
    canonical = data.get("canonicalState", {})
    formal = data.get("formalization", {})
    lines = [
        f"# {data.get('title', 'State–Decision–Effect Design')}", "",
        f"**Design:** `{data.get('designId')}` revision `{data.get('revision')}`  ",
        f"**Status:** `{data.get('status')}`  ",
        f"**Applicability:** `{data.get('applicability')}`  ",
        f"**Canonical state strategy:** `{canonical.get('strategy')}`  ",
        f"**Canonical semantic owner:** `{canonical.get('semanticOwner')}`  ",
        f"**Formalization:** `{formal.get('level')}`", "",
        "## Rationale", "", str(data.get("rationale", "")), "",
        "## State dimensions", "",
        "| ID | Owner | Mutually exclusive | Persistence | Purpose |", "|---|---|---:|---|---|",
    ]
    for item in canonical.get("dimensions", []):
        lines.append(f"| `{item.get('dimensionId')}` | {item.get('owner')} | {item.get('mutuallyExclusive')} | {item.get('persistence')} | {item.get('purpose')} |")
    if not canonical.get("dimensions"):
        lines.append("| — | — | — | — | Stateless or externally governed |")
    lines += ["", "## Decision boundaries", ""]
    for item in data.get("decisionBoundaries", []):
        lines += [f"### `{item.get('boundaryId')}`", "", f"Owner: **{item.get('owner')}**  ", f"Determinism: `{item.get('determinism')}`  ", f"Inputs: {', '.join(item.get('inputTypes', [])) or '—'}  ", f"Outputs: {', '.join(item.get('outputs', [])) or '—'}", ""]
    lines += ["## Effects", "", "| ID | Executor | Idempotency | Recovery owner | Intent |", "|---|---|---|---|---|"]
    for item in data.get("effectContracts", []):
        idem = item.get("idempotency", {})
        lines.append(f"| `{item.get('effectId')}` | {item.get('executor')} | {idem.get('classification')} | {item.get('recoveryOwner')} | {item.get('intent')} |")
    if not data.get("effectContracts"):
        lines.append("| — | — | — | — | No material effects |")
    lines += ["", "## Invariants", ""]
    for item in data.get("invariants", []):
        lines.append(f"- `{item.get('invariantId')}` **{item.get('class')}** — {item.get('statement')} ({', '.join(item.get('verificationMethods', []))})")
    lines += ["", "## Formalization", "", str(formal.get("rationale", "")), "", f"- Tool: `{formal.get('tool') or 'none'}`", f"- Model: `{formal.get('modelRef') or 'none'}`", f"- Divergence handling: {formal.get('divergenceHandling') or '—'}", ""]
    return "\n".join(lines).rstrip() + "\n"
