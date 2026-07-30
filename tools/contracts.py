#!/usr/bin/env python3
"""Domain-neutral BBK artifact validation and rendering.

Derived from the alpha.5 contract work and kept separate from the durable
project/candidate/gate/workspace mechanics so later method artifacts can evolve
without replacing those controls.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable

RISK_ORDER = {"routine": 0, "material": 1, "consequential": 2, "critical": 3}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()

def require_dict(value: Any, where: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{where} must be an object")
        return {}
    return value

def require_list(value: Any, where: str, errors: list[str]) -> list[Any]:
    if not isinstance(value, list):
        errors.append(f"{where} must be an array")
        return []
    return value

def require_text(value: Any, where: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{where} must be a non-empty string")
        return ""
    return value

def check_required(obj: dict[str, Any], keys: Iterable[str], where: str, errors: list[str]) -> None:
    for key in keys:
        if key not in obj:
            errors.append(f"{where}.{key} is required")

def check_unique(items: list[Any], field: str, where: str, errors: list[str]) -> None:
    seen: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        value = item.get(field)
        if not isinstance(value, str) or not value:
            errors.append(f"{where}[{index}].{field} must be a non-empty string")
        elif value in seen:
            errors.append(f"duplicate {where} {field}: {value}")
        else:
            seen.add(value)

def derive_fit_risk_tier(risk: dict[str, Any]) -> str:
    values = [int(risk.get(field, 0)) for field in ("consequence", "irreversibility", "uncertainty", "interfaceExposure")]
    consequence, irreversibility, _uncertainty, interface_exposure = values
    if any(value >= 4 for value in values) or (consequence >= 3 and (irreversibility >= 3 or interface_exposure >= 3)):
        return "critical"
    if any(value >= 3 for value in values) or sum(value >= 2 for value in values) >= 2:
        return "consequential"
    if sum(value == 2 for value in values) == 1 and all(value <= 2 for value in values):
        return "material"
    return "routine"

def validate_solution_outcome_fit(data: Any) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    obj = require_dict(data, "fit", errors)
    required = [
        "schema", "fitId", "revision", "title", "status", "applicability", "requestedIntervention",
        "desiredOutcomes", "currentBaseline", "causalHypothesis", "constraints", "alternatives",
        "counterfactual", "successEvidence", "risk", "disposition", "traceability", "review",
    ]
    check_required(obj, required, "fit", errors)
    if obj.get("schema") != "bbk.solution-outcome-fit.v1":
        errors.append("fit.schema must equal bbk.solution-outcome-fit.v1")
    for field in ("fitId", "revision", "title"):
        require_text(obj.get(field), f"fit.{field}", errors)
    if obj.get("status") not in {"draft", "in-review", "reviewed", "superseded"}:
        errors.append("fit.status is invalid")

    applicability = require_dict(obj.get("applicability"), "fit.applicability", errors)
    check_required(applicability, ["level", "triggers", "rationale"], "fit.applicability", errors)
    if applicability.get("level") not in {"implicit", "inline", "record"}:
        errors.append("fit.applicability.level is invalid")
    require_list(applicability.get("triggers"), "fit.applicability.triggers", errors)
    require_text(applicability.get("rationale"), "fit.applicability.rationale", errors)

    intervention = require_dict(obj.get("requestedIntervention"), "fit.requestedIntervention", errors)
    check_required(intervention, ["statement", "source", "role", "mandatory", "rationale", "evidenceRefs"], "fit.requestedIntervention", errors)
    intervention_statement = require_text(intervention.get("statement"), "fit.requestedIntervention.statement", errors)
    if intervention.get("source") not in {"user-request", "existing-plan", "external-authority", "inferred", "other"}:
        errors.append("fit.requestedIntervention.source is invalid")
    if intervention.get("role") not in {"candidate", "preference", "learning-objective", "mandated", "unknown"}:
        errors.append("fit.requestedIntervention.role is invalid")
    if not isinstance(intervention.get("mandatory"), bool):
        errors.append("fit.requestedIntervention.mandatory must be boolean")
    require_text(intervention.get("rationale"), "fit.requestedIntervention.rationale", errors)
    require_list(intervention.get("evidenceRefs"), "fit.requestedIntervention.evidenceRefs", errors)
    if intervention.get("mandatory") and intervention.get("role") not in {"mandated"}:
        warnings.append("requested intervention is mandatory but its role is not 'mandated'")

    outcomes = require_list(obj.get("desiredOutcomes"), "fit.desiredOutcomes", errors)
    if not outcomes:
        errors.append("fit.desiredOutcomes must contain at least one outcome")
    check_unique(outcomes, "id", "fit.desiredOutcomes", errors)
    outcome_ids: set[str] = set()
    outcome_phrases: list[str] = []
    for index, outcome in enumerate(outcomes):
        item = require_dict(outcome, f"fit.desiredOutcomes[{index}]", errors)
        check_required(item, ["id", "statement", "actorRefs", "successMeasures", "evidenceRefs"], f"fit.desiredOutcomes[{index}]", errors)
        outcome_id = require_text(item.get("id"), f"fit.desiredOutcomes[{index}].id", errors)
        if outcome_id:
            outcome_ids.add(outcome_id)
        statement = require_text(item.get("statement"), f"fit.desiredOutcomes[{index}].statement", errors)
        outcome_phrases.append(statement)
        require_list(item.get("actorRefs"), f"fit.desiredOutcomes[{index}].actorRefs", errors)
        measures = require_list(item.get("successMeasures"), f"fit.desiredOutcomes[{index}].successMeasures", errors)
        if not measures:
            errors.append(f"fit.desiredOutcomes[{index}].successMeasures must not be empty")
        outcome_phrases.extend(str(value) for value in measures)
        require_list(item.get("evidenceRefs"), f"fit.desiredOutcomes[{index}].evidenceRefs", errors)
        if intervention_statement and statement.strip().casefold() == intervention_statement.strip().casefold():
            errors.append(f"desired outcome {outcome_id or index} repeats the requested intervention rather than an operational result")

    baseline = require_dict(obj.get("currentBaseline"), "fit.currentBaseline", errors)
    check_required(baseline, ["description", "currentApproach", "strengths", "costsAndPain", "noChangeConsequences", "evidenceRefs"], "fit.currentBaseline", errors)
    require_text(baseline.get("description"), "fit.currentBaseline.description", errors)
    for field in ("currentApproach", "strengths", "costsAndPain", "noChangeConsequences", "evidenceRefs"):
        require_list(baseline.get(field), f"fit.currentBaseline.{field}", errors)

    hypothesis = require_dict(obj.get("causalHypothesis"), "fit.causalHypothesis", errors)
    check_required(hypothesis, ["statement", "mechanism", "assumptions", "confidence", "evidenceRefs", "falsifiers"], "fit.causalHypothesis", errors)
    hypothesis_statement = require_text(hypothesis.get("statement"), "fit.causalHypothesis.statement", errors)
    mechanism = require_text(hypothesis.get("mechanism"), "fit.causalHypothesis.mechanism", errors)
    if hypothesis.get("confidence") not in {"high", "medium", "low", "unknown"}:
        errors.append("fit.causalHypothesis.confidence is invalid")
    for field in ("assumptions", "evidenceRefs", "falsifiers"):
        require_list(hypothesis.get(field), f"fit.causalHypothesis.{field}", errors)
    if intervention_statement and hypothesis_statement.strip().casefold() == intervention_statement.strip().casefold():
        warnings.append("causal hypothesis merely repeats the requested intervention")
    if intervention_statement and mechanism.strip().casefold() == intervention_statement.strip().casefold():
        warnings.append("causal mechanism merely repeats the requested intervention")

    constraints = require_list(obj.get("constraints"), "fit.constraints", errors)
    check_unique(constraints, "id", "fit.constraints", errors)
    for index, value in enumerate(constraints):
        item = require_dict(value, f"fit.constraints[{index}]", errors)
        check_required(item, ["id", "statement", "kind", "source", "evidenceRefs"], f"fit.constraints[{index}]", errors)
        require_text(item.get("id"), f"fit.constraints[{index}].id", errors)
        statement = require_text(item.get("statement"), f"fit.constraints[{index}].statement", errors)
        if item.get("kind") not in {"hard", "preference", "assumption", "unknown"}:
            errors.append(f"fit.constraints[{index}].kind is invalid")
        require_text(item.get("source"), f"fit.constraints[{index}].source", errors)
        require_list(item.get("evidenceRefs"), f"fit.constraints[{index}].evidenceRefs", errors)
        if item.get("kind") == "hard" and any(token in statement.lower() for token in ("prefer", "would like", "ideally")):
            warnings.append(f"hard constraint may actually be a preference: {statement}")

    alternatives = require_list(obj.get("alternatives"), "fit.alternatives", errors)
    check_unique(alternatives, "id", "fit.alternatives", errors)
    has_no_change = False
    for index, value in enumerate(alternatives):
        item = require_dict(value, f"fit.alternatives[{index}]", errors)
        check_required(item, ["id", "intervention", "kind", "fit", "benefits", "costs", "risks", "disposition", "evidenceRefs"], f"fit.alternatives[{index}]", errors)
        require_text(item.get("id"), f"fit.alternatives[{index}].id", errors)
        require_text(item.get("intervention"), f"fit.alternatives[{index}].intervention", errors)
        if item.get("kind") not in {"requested", "alternative", "no-change", "procedural", "operational", "technical", "other"}:
            errors.append(f"fit.alternatives[{index}].kind is invalid")
        if item.get("kind") == "no-change":
            has_no_change = True
        if item.get("fit") not in {"high", "medium", "low", "unknown"}:
            errors.append(f"fit.alternatives[{index}].fit is invalid")
        if item.get("disposition") not in {"selected", "rejected", "retained", "investigate", "not-applicable"}:
            errors.append(f"fit.alternatives[{index}].disposition is invalid")
        for field in ("benefits", "costs", "risks", "evidenceRefs"):
            require_list(item.get(field), f"fit.alternatives[{index}].{field}", errors)

    counterfactual = require_dict(obj.get("counterfactual"), "fit.counterfactual", errors)
    check_required(counterfactual, ["question", "failureConditions", "residualRisks", "conclusion"], "fit.counterfactual", errors)
    require_text(counterfactual.get("question"), "fit.counterfactual.question", errors)
    failure_conditions = require_list(counterfactual.get("failureConditions"), "fit.counterfactual.failureConditions", errors)
    require_list(counterfactual.get("residualRisks"), "fit.counterfactual.residualRisks", errors)
    require_text(counterfactual.get("conclusion"), "fit.counterfactual.conclusion", errors)

    evidence = require_list(obj.get("successEvidence"), "fit.successEvidence", errors)
    check_unique(evidence, "id", "fit.successEvidence", errors)
    operational_methods = 0
    for index, value in enumerate(evidence):
        item = require_dict(value, f"fit.successEvidence[{index}]", errors)
        check_required(item, ["id", "outcomeRef", "measure", "method", "thresholdOrSignal", "observationWindow", "evidenceRefs"], f"fit.successEvidence[{index}]", errors)
        for field in ("id", "outcomeRef", "measure", "thresholdOrSignal", "observationWindow"):
            require_text(item.get(field), f"fit.successEvidence[{index}].{field}", errors)
        if item.get("outcomeRef") not in outcome_ids:
            errors.append(f"fit.successEvidence[{index}].outcomeRef does not name a desired outcome: {item.get('outcomeRef')}")
        if item.get("method") not in {"analysis", "inspection", "demonstration", "test", "operational-observation", "review", "survey", "measurement", "other"}:
            errors.append(f"fit.successEvidence[{index}].method is invalid")
        if item.get("method") in {"demonstration", "operational-observation", "survey", "measurement"}:
            operational_methods += 1
        require_list(item.get("evidenceRefs"), f"fit.successEvidence[{index}].evidenceRefs", errors)

    risk = require_dict(obj.get("risk"), "fit.risk", errors)
    check_required(risk, ["consequence", "irreversibility", "uncertainty", "interfaceExposure", "derivedTier", "rationale", "confidence"], "fit.risk", errors)
    for field in ("consequence", "irreversibility", "uncertainty", "interfaceExposure"):
        value = risk.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > 4:
            errors.append(f"fit.risk.{field} must be an integer from 0 to 4")
    if risk.get("derivedTier") not in RISK_ORDER:
        errors.append("fit.risk.derivedTier is invalid")
    require_text(risk.get("rationale"), "fit.risk.rationale", errors)
    if risk.get("confidence") not in {"high", "medium", "low"}:
        errors.append("fit.risk.confidence is invalid")
    if all(isinstance(risk.get(field), int) and not isinstance(risk.get(field), bool) for field in ("consequence", "irreversibility", "uncertainty", "interfaceExposure")):
        derived = derive_fit_risk_tier(risk)
        if risk.get("derivedTier") != derived:
            errors.append(f"fit.risk.derivedTier must be {derived} for the supplied non-averaging axis values")
    else:
        derived = str(risk.get("derivedTier") or "routine")

    disposition = require_dict(obj.get("disposition"), "fit.disposition", errors)
    check_required(disposition, ["status", "selectedDirection", "authorityMode", "rationale", "approvalRefs", "investigationPlan", "blockers"], "fit.disposition", errors)
    status = disposition.get("status")
    if status not in {"CONFIRMED_FIT", "REFRAMED", "INVESTIGATE", "PREFERENCE_DRIVEN", "CONSTRAINT_REQUIRED", "NO_CHANGE_PREFERRED", "UNRESOLVED"}:
        errors.append("fit.disposition.status is invalid")
    if not isinstance(disposition.get("selectedDirection"), str):
        errors.append("fit.disposition.selectedDirection must be a string")
    if disposition.get("authorityMode") not in {"user", "delegated", "constraint-driven", "external-authority", "unresolved"}:
        errors.append("fit.disposition.authorityMode is invalid")
    require_text(disposition.get("rationale"), "fit.disposition.rationale", errors)
    approval_refs = require_list(disposition.get("approvalRefs"), "fit.disposition.approvalRefs", errors)
    investigation_plan = require_list(disposition.get("investigationPlan"), "fit.disposition.investigationPlan", errors)
    disposition_blockers = require_list(disposition.get("blockers"), "fit.disposition.blockers", errors)

    traceability = require_dict(obj.get("traceability"), "fit.traceability", errors)
    trace_fields = ["outcomeRefs", "needRefs", "requirementRefs", "decisionRefs", "architectureRefs", "capabilityRefs", "workUnitRefs"]
    check_required(traceability, trace_fields, "fit.traceability", errors)
    for field in trace_fields:
        require_list(traceability.get(field), f"fit.traceability.{field}", errors)
    if set(traceability.get("outcomeRefs") or []) != outcome_ids:
        errors.append("fit.traceability.outcomeRefs must exactly name the desired outcome IDs")

    review = require_dict(obj.get("review"), "fit.review", errors)
    check_required(review, ["required", "reviewerKind", "criteria", "acceptedReviewRefs", "blockers"], "fit.review", errors)
    if not isinstance(review.get("required"), bool):
        errors.append("fit.review.required must be boolean")
    if review.get("reviewerKind") not in {"same-wayfinder", "fresh-reviewer", "human", "not-required"}:
        errors.append("fit.review.reviewerKind is invalid")
    require_list(review.get("criteria"), "fit.review.criteria", errors)
    accepted_review_refs = require_list(review.get("acceptedReviewRefs"), "fit.review.acceptedReviewRefs", errors)
    review_blockers = require_list(review.get("blockers"), "fit.review.blockers", errors)
    if review.get("required") and review.get("reviewerKind") == "not-required":
        errors.append("fit.review.required=true is incompatible with reviewerKind=not-required")
    if not review.get("required") and review.get("reviewerKind") != "not-required":
        warnings.append("fit.review.required=false but reviewerKind names a reviewer")

    if RISK_ORDER.get(derived, 0) >= RISK_ORDER["material"] and len(alternatives) < 2 and status not in {"PREFERENCE_DRIVEN", "CONSTRAINT_REQUIRED"}:
        warnings.append("material-or-higher fit has fewer than two credible alternatives")
    if RISK_ORDER.get(derived, 0) >= RISK_ORDER["material"] and not has_no_change and status not in {"PREFERENCE_DRIVEN", "CONSTRAINT_REQUIRED"}:
        warnings.append("material-or-higher fit does not include a no-change alternative")
    if RISK_ORDER.get(derived, 0) >= RISK_ORDER["material"] and not failure_conditions:
        errors.append("material-or-higher fit requires a delivered-but-outcome-remains counterfactual failure condition")
    if RISK_ORDER.get(derived, 0) >= RISK_ORDER["material"] and not evidence:
        errors.append("material-or-higher fit requires outcome-level success evidence")

    artifact_tokens = (" exists", " is built", " built", " implemented", " delivered", " file is present", " created")
    artifact_only = bool(outcome_phrases) and all(any(token in f" {phrase.lower()}" for token in artifact_tokens) for phrase in outcome_phrases if phrase.strip())
    if artifact_only and operational_methods == 0:
        errors.append("desired outcome and success evidence are defined only as artifact completion")
    elif RISK_ORDER.get(derived, 0) >= RISK_ORDER["material"] and operational_methods == 0:
        warnings.append("material-or-higher fit has no demonstration, observation, survey or measurement evidence")

    if status in {"CONFIRMED_FIT", "REFRAMED", "PREFERENCE_DRIVEN", "CONSTRAINT_REQUIRED", "NO_CHANGE_PREFERRED"} and not str(disposition.get("selectedDirection", "")).strip():
        errors.append("resolved fit disposition requires selectedDirection")
    if status == "REFRAMED" and str(disposition.get("selectedDirection", "")).strip().casefold() == intervention_statement.strip().casefold():
        errors.append("REFRAMED selectedDirection must differ materially from the requested intervention")
    if status == "INVESTIGATE" and not investigation_plan:
        errors.append("INVESTIGATE requires a bounded investigationPlan")
    if status == "UNRESOLVED" and not disposition_blockers:
        errors.append("UNRESOLVED requires explicit blockers")
    if status == "PREFERENCE_DRIVEN" and intervention.get("role") not in {"preference", "learning-objective"}:
        warnings.append("PREFERENCE_DRIVEN normally requires requestedIntervention.role preference or learning-objective")
    if status == "CONSTRAINT_REQUIRED" and (not intervention.get("mandatory") or intervention.get("role") != "mandated"):
        errors.append("CONSTRAINT_REQUIRED requires a mandatory mandated intervention")
    if status == "CONFIRMED_FIT" and hypothesis.get("confidence") in {"low", "unknown"}:
        warnings.append("CONFIRMED_FIT has low or unknown causal confidence")

    resolved_commitment = status in {"CONFIRMED_FIT", "REFRAMED", "PREFERENCE_DRIVEN", "CONSTRAINT_REQUIRED", "NO_CHANGE_PREFERRED"}
    if resolved_commitment and RISK_ORDER.get(derived, 0) >= RISK_ORDER["consequential"] and disposition.get("authorityMode") == "delegated":
        errors.append("consequential-or-critical solution commitment may not use delegated authority")
    if resolved_commitment and disposition.get("authorityMode") in {"user", "external-authority"} and not approval_refs:
        errors.append("user or external-authority solution commitment requires approvalRefs")
    if RISK_ORDER.get(derived, 0) >= RISK_ORDER["consequential"] and not review.get("required"):
        errors.append("consequential-or-critical fit requires review")

    requires_human = resolved_commitment and disposition.get("authorityMode") in {"user", "external-authority"} and not approval_refs
    if errors or status in {"INVESTIGATE", "UNRESOLVED"} or disposition_blockers or review_blockers or requires_human:
        commitment = "BLOCKED"
    elif review.get("required") and not accepted_review_refs:
        commitment = "CONDITIONAL"
        warnings.append("required fit review has no acceptedReviewRefs")
    elif obj.get("status") == "reviewed":
        commitment = "CLEAR"
    else:
        commitment = "CONDITIONAL"
    reason = (
        "validation errors" if errors else
        "additional investigation is required" if status == "INVESTIGATE" else
        "fit remains unresolved" if status == "UNRESOLVED" else
        "explicit blockers remain" if disposition_blockers or review_blockers else
        "required review or acceptance is pending" if commitment == "CONDITIONAL" else
        "solution–outcome fit is reviewed and clear"
    )
    return {
        "kind": "solution-outcome-fit",
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "planningDisposition": {
            "fitDisposition": status,
            "riskTier": derived,
            "solutionCommitment": commitment,
            "requiresHumanDecision": requires_human,
            "reason": reason,
        },
        "digest": canonical_digest(obj) if isinstance(data, dict) else None,
    }

def validate_structure(data: Any) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    obj = require_dict(data, "contract", errors)
    check_required(obj, ["schema", "contractId", "revision", "title", "status", "subject", "applicability", "structure", "decisions", "review"], "contract", errors)
    if obj.get("schema") != "bbk.implementation-structure-contract.v1":
        errors.append("contract.schema must equal bbk.implementation-structure-contract.v1")
    for field in ("contractId", "revision", "title"):
        require_text(obj.get(field), f"contract.{field}", errors)
    if obj.get("status") not in {"draft", "in-review", "accepted", "superseded"}:
        errors.append("contract.status is invalid")

    subject = require_dict(obj.get("subject"), "contract.subject", errors)
    check_required(subject, ["purpose", "kind", "baselineRefs", "scopeRefs"], "contract.subject", errors)
    require_text(subject.get("purpose"), "contract.subject.purpose", errors)
    if subject.get("kind") not in {"software", "automation", "hardware", "procedure", "data", "document", "mixed", "other"}:
        errors.append("contract.subject.kind is invalid")
    for field in ("baselineRefs", "scopeRefs"):
        values = require_list(subject.get(field), f"contract.subject.{field}", errors)
        if not values:
            errors.append(f"contract.subject.{field} must contain at least one reference")
        for index, value in enumerate(values):
            require_text(value, f"contract.subject.{field}[{index}]", errors)
    for field in ("solutionOutcomeFitRefs", "outcomeRefs"):
        if field in subject:
            require_list(subject.get(field), f"contract.subject.{field}", errors)
    if subject.get("solutionOutcomeFitRefs") and not subject.get("outcomeRefs"):
        warnings.append("structure contract references SolutionOutcomeFit but names no outcomeRefs")

    applicability = require_dict(obj.get("applicability"), "contract.applicability", errors)
    check_required(applicability, ["level", "triggers", "rationale"], "contract.applicability", errors)
    level = applicability.get("level")
    if level not in {"none", "inline", "contract"}:
        errors.append("contract.applicability.level is invalid")
    require_list(applicability.get("triggers"), "contract.applicability.triggers", errors)
    require_text(applicability.get("rationale"), "contract.applicability.rationale", errors)

    structure = require_dict(obj.get("structure"), "contract.structure", errors)
    structural_fields = ["artifactTopology", "keyContracts", "behaviorPaths", "stateOwnership", "effectBoundaries", "testSeams", "observabilityPoints", "migrationTouchpoints"]
    check_required(structure, structural_fields, "contract.structure", errors)
    arrays: dict[str, list[Any]] = {}
    for field in structural_fields:
        arrays[field] = require_list(structure.get(field), f"contract.structure.{field}", errors)
    check_unique(arrays["artifactTopology"], "id", "artifactTopology", errors)
    check_unique(arrays["keyContracts"], "id", "keyContracts", errors)
    check_unique(arrays["behaviorPaths"], "id", "behaviorPaths", errors)
    for field in ("testSeams", "observabilityPoints", "migrationTouchpoints"):
        check_unique(arrays[field], "id", field, errors)
    for index, artifact in enumerate(arrays["artifactTopology"]):
        item = require_dict(artifact, f"artifactTopology[{index}]", errors)
        check_required(item, ["id", "action", "kind", "logicalPath", "responsibility", "owner"], f"artifactTopology[{index}]", errors)
        for field in ("id", "kind", "logicalPath", "responsibility", "owner"):
            require_text(item.get(field), f"artifactTopology[{index}].{field}", errors)
        if item.get("action") not in {"create", "modify", "move", "remove", "retain", "inspect"}:
            errors.append(f"artifactTopology[{index}].action is invalid")
    contract_ids: set[str] = set()
    for index, contract in enumerate(arrays["keyContracts"]):
        item = require_dict(contract, f"keyContracts[{index}]", errors)
        check_required(item, ["id", "kind", "name", "shape", "responsibility", "visibility", "invariants"], f"keyContracts[{index}]", errors)
        for field in ("id", "kind", "name", "shape", "responsibility"):
            require_text(item.get(field), f"keyContracts[{index}].{field}", errors)
        if isinstance(item.get("id"), str):
            contract_ids.add(item["id"])
        if item.get("visibility") not in {"private", "internal", "shared", "public", "external"}:
            errors.append(f"keyContracts[{index}].visibility is invalid")
        require_list(item.get("invariants"), f"keyContracts[{index}].invariants", errors)
    for index, path in enumerate(arrays["behaviorPaths"]):
        item = require_dict(path, f"behaviorPaths[{index}]", errors)
        check_required(item, ["id", "name", "trigger", "steps", "success", "failureAndRecovery"], f"behaviorPaths[{index}]", errors)
        for field in ("id", "name", "trigger", "success"):
            require_text(item.get(field), f"behaviorPaths[{index}].{field}", errors)
        steps = require_list(item.get("steps"), f"behaviorPaths[{index}].steps", errors)
        if not steps:
            errors.append(f"behaviorPaths[{index}].steps must not be empty")
        for step_index, step in enumerate(steps):
            step_obj = require_dict(step, f"behaviorPaths[{index}].steps[{step_index}]", errors)
            for field in ("from", "to", "interaction"):
                require_text(step_obj.get(field), f"behaviorPaths[{index}].steps[{step_index}].{field}", errors)
            ref = step_obj.get("contractRef")
            if isinstance(ref, str) and ref.startswith("KC-") and ref not in contract_ids:
                warnings.append(f"behavior path references key contract not declared in this contract: {ref}")
        failures = require_list(item.get("failureAndRecovery"), f"behaviorPaths[{index}].failureAndRecovery", errors)
        if not failures:
            warnings.append(f"behavior path {item.get('id', index)} has no explicit failure/recovery case")
    for index, state in enumerate(arrays["stateOwnership"]):
        item = require_dict(state, f"stateOwnership[{index}]", errors)
        for field in ("state", "owner", "lifetime", "mutationAuthority", "consistency", "recovery"):
            require_text(item.get(field), f"stateOwnership[{index}].{field}", errors)
    for index, effect in enumerate(arrays["effectBoundaries"]):
        item = require_dict(effect, f"effectBoundaries[{index}]", errors)
        for field in ("effect", "owner", "authorization", "idempotency", "failure", "recovery"):
            require_text(item.get(field), f"effectBoundaries[{index}].{field}", errors)

    decisions = require_dict(obj.get("decisions"), "contract.decisions", errors)
    check_required(decisions, ["fixed", "delegated", "prohibited"], "contract.decisions", errors)
    fixed = require_list(decisions.get("fixed"), "contract.decisions.fixed", errors)
    delegated = require_list(decisions.get("delegated"), "contract.decisions.delegated", errors)
    require_list(decisions.get("prohibited"), "contract.decisions.prohibited", errors)
    check_unique(fixed, "id", "fixed decisions", errors)
    for index, decision in enumerate(fixed):
        item = require_dict(decision, f"fixed[{index}]", errors)
        for field in ("id", "statement", "rationale", "changeRoute"):
            require_text(item.get(field), f"fixed[{index}].{field}", errors)
    for index, decision in enumerate(delegated):
        item = require_dict(decision, f"delegated[{index}]", errors)
        for field in ("area", "bounds"):
            require_text(item.get(field), f"delegated[{index}].{field}", errors)

    review = require_dict(obj.get("review"), "contract.review", errors)
    check_required(review, ["assuranceTier", "requiredReviewers", "acceptanceCriteria"], "contract.review", errors)
    if review.get("assuranceTier") not in {"routine", "material", "consequential", "critical"}:
        errors.append("contract.review.assuranceTier is invalid")
    require_list(review.get("requiredReviewers"), "contract.review.requiredReviewers", errors)
    criteria = require_list(review.get("acceptanceCriteria"), "contract.review.acceptanceCriteria", errors)
    if not criteria:
        errors.append("contract.review.acceptanceCriteria must not be empty")

    substantial = bool(arrays["artifactTopology"] or arrays["keyContracts"] or arrays["behaviorPaths"] or arrays["stateOwnership"])
    if level == "contract" and not substantial:
        errors.append("a contract-level ImplementationStructureContract must describe at least one consequential structure element")
    if level == "contract" and not (fixed or delegated):
        errors.append("a contract-level ImplementationStructureContract must distinguish at least one fixed decision or delegated area")
    if obj.get("status") == "accepted" and not fixed:
        warnings.append("accepted contract has no fixed decisions; confirm that a separate contract is warranted")
    if not delegated:
        warnings.append("no delegated implementation freedom is recorded; review for over-specification")
    if subject.get("kind") != "software" and any("file" in str(a.get("kind", "")).lower() for a in arrays["artifactTopology"] if isinstance(a, dict)):
        warnings.append("non-software contract uses file-oriented artifact kinds; confirm this is domain-appropriate")

    return {"kind": "implementation-structure-contract", "valid": not errors, "errors": errors, "warnings": warnings, "digest": canonical_digest(obj) if isinstance(data, dict) else None}

def validate_slice(data: Any) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    obj = require_dict(data, "slice", errors)
    required = ["schema", "sliceId", "title", "status", "parentCapabilityRefs", "structureContractRefs", "objective", "touchpoint", "flow", "workUnitRefs", "integrationOwner", "assertions", "entryConditions", "exitConditions", "atomicity", "scaffolding"]
    check_required(obj, required, "slice", errors)
    if obj.get("schema") != "bbk.execution-slice.v1":
        errors.append("slice.schema must equal bbk.execution-slice.v1")
    for field in ("sliceId", "title", "objective", "integrationOwner"):
        require_text(obj.get(field), f"slice.{field}", errors)
    if obj.get("status") not in {"draft", "ready", "running", "validating", "complete", "blocked", "superseded"}:
        errors.append("slice.status is invalid")
    for field in ("parentCapabilityRefs", "structureContractRefs", "workUnitRefs"):
        values = require_list(obj.get(field), f"slice.{field}", errors)
        if not values:
            errors.append(f"slice.{field} must not be empty")
    for field in ("solutionOutcomeFitRefs", "outcomeRefs"):
        if field in obj:
            require_list(obj.get(field), f"slice.{field}", errors)
    if obj.get("solutionOutcomeFitRefs") and not obj.get("outcomeRefs"):
        warnings.append("execution slice references SolutionOutcomeFit but names no outcomeRefs")
    touchpoint = require_dict(obj.get("touchpoint"), "slice.touchpoint", errors)
    for field in ("kind", "actor", "interaction", "expectedObservation", "environment"):
        require_text(touchpoint.get(field), f"slice.touchpoint.{field}", errors)
    if touchpoint.get("kind") not in {"cli", "api", "ui", "report", "procedure", "simulation", "physical-observation", "document", "package", "protocol-trace", "other"}:
        errors.append("slice.touchpoint.kind is invalid")
    flow = require_dict(obj.get("flow"), "slice.flow", errors)
    participants = require_list(flow.get("participants"), "slice.flow.participants", errors)
    steps = require_list(flow.get("steps"), "slice.flow.steps", errors)
    if not participants:
        errors.append("slice.flow.participants must not be empty")
    if not steps:
        errors.append("slice.flow.steps must not be empty")
    assertions = require_list(obj.get("assertions"), "slice.assertions", errors)
    if not assertions:
        errors.append("slice.assertions must not be empty")
    check_unique(assertions, "id", "assertions", errors)
    for index, assertion in enumerate(assertions):
        item = require_dict(assertion, f"slice.assertions[{index}]", errors)
        for field in ("id", "statement", "method", "evidence"):
            require_text(item.get(field), f"slice.assertions[{index}].{field}", errors)
    exit_conditions = require_list(obj.get("exitConditions"), "slice.exitConditions", errors)
    if not exit_conditions:
        errors.append("slice.exitConditions must not be empty")
    require_list(obj.get("entryConditions"), "slice.entryConditions", errors)
    atomicity = require_dict(obj.get("atomicity"), "slice.atomicity", errors)
    for field in ("coherent", "reviewable", "independentlyVerifiable", "containedOrReversible"):
        if not isinstance(atomicity.get(field), bool):
            errors.append(f"slice.atomicity.{field} must be boolean")
        elif obj.get("status") in {"ready", "running", "validating", "complete"} and atomicity.get(field) is not True:
            errors.append(f"slice status {obj.get('status')} requires atomicity.{field}=true")
    require_text(atomicity.get("rationale"), "slice.atomicity.rationale", errors)
    scaffolding = require_list(obj.get("scaffolding"), "slice.scaffolding", errors)
    check_unique(scaffolding, "id", "scaffolding", errors)
    for index, scaffold in enumerate(scaffolding):
        item = require_dict(scaffold, f"slice.scaffolding[{index}]", errors)
        for field in ("id", "purpose", "disposition", "owner"):
            require_text(item.get(field), f"slice.scaffolding[{index}].{field}", errors)
        if item.get("disposition") == "remove-by-slice" and not item.get("removeBySliceRef"):
            errors.append(f"slice.scaffolding[{index}] remove-by-slice requires removeBySliceRef")
    if len(obj.get("workUnitRefs") or []) > 7:
        warnings.append("slice has more than seven work units; review cognitive and validation coherence")
    if len(steps) == 1 and len(participants) == 1:
        warnings.append("slice may be a local task rather than an integrated execution slice")
    return {"kind": "execution-slice", "valid": not errors, "errors": errors, "warnings": warnings, "digest": canonical_digest(obj) if isinstance(data, dict) else None}

def validate_slice_set(values: Any, contract: dict[str, Any] | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    slices = require_list(values, "slices", errors)
    by_id: dict[str, dict[str, Any]] = {}
    reports: list[dict[str, Any]] = []
    for index, data in enumerate(slices):
        report = validate_slice(data)
        reports.append(report)
        errors.extend([f"slices[{index}]: {message}" for message in report["errors"]])
        warnings.extend([f"slices[{index}]: {message}" for message in report["warnings"]])
        if isinstance(data, dict):
            slice_id = data.get("sliceId")
            if isinstance(slice_id, str):
                if slice_id in by_id:
                    errors.append(f"duplicate slice ID: {slice_id}")
                else:
                    by_id[slice_id] = data
    for slice_id, data in by_id.items():
        for dependency in data.get("dependsOn") or []:
            if dependency not in by_id:
                errors.append(f"slice {slice_id} depends on missing slice {dependency}")
    # Detect cycles without requiring a particular ordering.
    visiting: set[str] = set()
    visited: set[str] = set()
    def visit(slice_id: str, path: list[str]) -> None:
        if slice_id in visited:
            return
        if slice_id in visiting:
            errors.append("slice dependency cycle: " + " -> ".join(path + [slice_id]))
            return
        visiting.add(slice_id)
        for dependency in by_id[slice_id].get("dependsOn") or []:
            if dependency in by_id:
                visit(dependency, path + [slice_id])
        visiting.remove(slice_id)
        visited.add(slice_id)
    for slice_id in sorted(by_id):
        visit(slice_id, [])
    if isinstance(contract, dict):
        contract_report = validate_structure(contract)
        errors.extend([f"contract: {message}" for message in contract_report["errors"]])
        warnings.extend([f"contract: {message}" for message in contract_report["warnings"]])
        identity = f"{contract.get('contractId')}@{contract.get('revision')}"
        for slice_id, data in by_id.items():
            refs = data.get("structureContractRefs") or []
            if identity not in refs and contract.get("contractId") not in refs:
                errors.append(f"slice {slice_id} does not reference {identity}")
        declared = set(contract.get("executionSliceRefs") or [])
        supplied = set(by_id)
        if declared - supplied:
            errors.append(f"contract-declared slices not supplied: {sorted(declared - supplied)}")
        if supplied - declared:
            warnings.append(f"supplied slices not declared by contract: {sorted(supplied - declared)}")
    payload = {"slices": [{"id": item.get("sliceId"), "digest": report.get("digest")} for item, report in zip(slices, reports) if isinstance(item, dict)]}
    return {"kind": "execution-slice-set", "valid": not errors, "errors": errors, "warnings": warnings, "digest": canonical_digest(payload)}

def validate_work_unit(data: Any) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    original = require_dict(data, "workUnit", errors)
    # Alpha.3 used snake_case field names.  Alpha.4 introduced richer
    # camelCase bindings.  Normalize both into one validation view while
    # preserving the original object and digest.
    aliases = {
        "task_profile": "taskProfile",
        "assurance_tier": "assuranceTier",
        "language_profiles": "languageProfiles",
        "profile_hints": "profileHints",
        "change_classes": "changeClasses",
        "paths": "affectedPaths",
        "expected_behavior": "expectedBehavior",
        "verification_plan": "verificationPlan",
        "required_skills": "requiredSkills",
        "solution_outcome_fit_refs": "solutionOutcomeFitRefs",
        "supported_outcome_refs": "supportedOutcomeRefs",
        "implementation_structure_contract_refs": "implementationStructureContractRefs",
        "execution_slice_ids": "executionSliceIds",
        "planned_artifact_refs": "plannedArtifactRefs",
        "key_contract_refs": "keyContractRefs",
        "temporary_scaffolding": "temporaryScaffolding",
        "scaffolding_disposition": "scaffoldingDisposition",
        "state_decision_effect_refs": "stateDecisionEffectRefs",
        "state_transition_trace_refs": "stateTransitionTraceRefs",
        "assurance_contract_refs": "assuranceContractRefs",
        "review_manifest_refs": "reviewManifestRefs",
    }
    obj = dict(original)
    for legacy, current in aliases.items():
        if current not in obj and legacy in obj:
            obj[current] = obj[legacy]
    if "expectedBehavior" not in obj:
        # Alpha.3 work units did not require a separate behavior list.  Scope
        # and purpose still provide a useful, honest legacy validation basis.
        obj["expectedBehavior"] = [str(obj.get("purpose", ""))] if obj.get("purpose") else []
        warnings.append("legacy work unit has no expectedBehavior; purpose was used as a compatibility projection")
    if "verificationPlan" not in obj:
        required_gates = obj.get("required_gates") or []
        assertions = obj.get("assertions") or []
        obj["verificationPlan"] = [str(x) for x in [*required_gates, *assertions] if str(x).strip()]
        if not obj["verificationPlan"]:
            obj["verificationPlan"] = ["define the assertion-specific verification method before execution"]
        warnings.append("legacy work unit has no verificationPlan; legacy gates/assertions were projected")
    if "role" not in obj:
        obj["role"] = "worker"
        warnings.append("legacy work unit has no role; defaulted to worker for compatibility")
    required = ["id", "purpose", "scope", "taskProfile", "assuranceTier", "role", "expectedBehavior", "verificationPlan"]
    check_required(obj, required, "workUnit", errors)
    for field in ("id", "purpose", "taskProfile"):
        require_text(obj.get(field), f"workUnit.{field}", errors)
    for field in ("scope", "expectedBehavior", "verificationPlan"):
        values = require_list(obj.get(field), f"workUnit.{field}", errors)
        if not values:
            errors.append(f"workUnit.{field} must not be empty")
    if obj.get("assuranceTier") not in {"routine", "material", "consequential", "critical"}:
        errors.append("workUnit.assuranceTier is invalid")
    if obj.get("role") not in {"worker", "validator", "reviewer", "prototyper", "architect", "wayfinder"}:
        errors.append("workUnit.role is invalid")
    structure_refs = obj.get("implementationStructureContractRefs") or []
    slice_refs = obj.get("executionSliceIds") or []
    fit_refs = obj.get("solutionOutcomeFitRefs") or []
    outcome_refs = obj.get("supportedOutcomeRefs") or []
    state_effect_refs = obj.get("stateDecisionEffectRefs") or []
    trace_refs = obj.get("stateTransitionTraceRefs") or []
    assurance_refs = obj.get("assuranceContractRefs") or []
    review_refs = obj.get("reviewManifestRefs") or []
    reference_fields = {
        "implementationStructureContractRefs": structure_refs,
        "executionSliceIds": slice_refs,
        "solutionOutcomeFitRefs": fit_refs,
        "supportedOutcomeRefs": outcome_refs,
        "stateDecisionEffectRefs": state_effect_refs,
        "stateTransitionTraceRefs": trace_refs,
        "assuranceContractRefs": assurance_refs,
        "reviewManifestRefs": review_refs,
    }
    for field, values in reference_fields.items():
        if values and not isinstance(values, list):
            errors.append(f"workUnit.{field} must be an array")
        elif isinstance(values, list):
            for index, value in enumerate(values):
                require_text(value, f"workUnit.{field}[{index}]", errors)
    if fit_refs and not outcome_refs:
        warnings.append("work unit references SolutionOutcomeFit but names no supportedOutcomeRefs")
    if outcome_refs and not fit_refs:
        warnings.append("work unit names supported outcomes but no SolutionOutcomeFit reference")
    if obj.get("temporaryScaffolding") and not obj.get("scaffoldingDisposition"):
        errors.append("temporaryScaffolding requires scaffoldingDisposition")
    if obj.get("assuranceTier") in {"consequential", "critical"} and not structure_refs:
        warnings.append("high-assurance work unit has no ImplementationStructureContract reference; confirm non-applicability")
    if obj.get("assuranceTier") in {"material", "consequential", "critical"} and not fit_refs:
        warnings.append("material-or-higher work unit has no SolutionOutcomeFit reference; confirm outcome traceability is established elsewhere")
    stateful_effectful = any(str(value).lower() in {"state", "stateful", "effect", "effects", "recovery", "retry", "concurrency", "cancellation"} for value in (obj.get("profileHints") or []))
    if stateful_effectful and not state_effect_refs:
        warnings.append("state/effect profile hints are present but no stateDecisionEffectRefs are bound")
    if trace_refs and not state_effect_refs:
        errors.append("stateTransitionTraceRefs require at least one stateDecisionEffectRefs entry")
    if obj.get("assuranceTier") in {"material", "consequential", "critical"} and not assurance_refs:
        warnings.append("material-or-higher work unit has no AssuranceContract reference")
    if review_refs and not assurance_refs:
        errors.append("reviewManifestRefs require at least one AssuranceContract reference")
    return {
        "kind": "work-unit", "valid": not errors, "errors": errors, "warnings": warnings,
        "digest": canonical_digest(original) if isinstance(data, dict) else None,
        "normalized": obj,
    }


PROFILE_CAPABILITY_OPERATIONS = {
    "state-effect",
    "state-effect-inventory",
    "state-effect-review",
    "review-context",
    "review-lens",
    "evidence-adapter",
}


def validate_profile_capability_request(data: Any) -> dict[str, Any]:
    """Validate the core-owned request passed to an alpha.8 profile adapter."""
    errors: list[str] = []
    warnings: list[str] = []
    obj = require_dict(data, "profile capability request", errors)
    required = [
        "schema", "requestId", "operation", "profile", "source", "subject",
        "inputs", "context", "authority", "requestDigest",
    ]
    check_required(obj, required, "profile capability request", errors)
    if obj.get("schema") != "bbk.profile-capability-request.v1":
        errors.append("request.schema must equal bbk.profile-capability-request.v1")
    request_id = obj.get("requestId")
    if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", request_id):
        errors.append("request.requestId must be a safe BBK identifier")
    if obj.get("operation") not in PROFILE_CAPABILITY_OPERATIONS:
        errors.append("request.operation is invalid")
    profile = require_dict(obj.get("profile"), "request.profile", errors)
    for field in ("id", "version", "rootSha256", "manifestSha256"):
        require_text(profile.get(field), f"request.profile.{field}", errors)
    for field in ("rootSha256", "manifestSha256"):
        value = profile.get(field)
        if isinstance(value, str) and not re.fullmatch(r"[0-9a-f]{64}", value):
            errors.append(f"request.profile.{field} must be a lowercase SHA-256 digest")
    source = require_dict(obj.get("source"), "request.source", errors)
    require_text(source.get("root"), "request.source.root", errors)
    require_text(source.get("contentSha256"), "request.source.contentSha256", errors)
    if isinstance(source.get("contentSha256"), str) and not re.fullmatch(r"[0-9a-f]{64}", source["contentSha256"]):
        errors.append("request.source.contentSha256 must be a lowercase SHA-256 digest")
    subject = require_dict(obj.get("subject"), "request.subject", errors)
    for field in ("ref", "kind", "revision", "digest"):
        require_text(subject.get(field), f"request.subject.{field}", errors)
    if isinstance(subject.get("digest"), str) and not re.fullmatch(r"[0-9a-f]{64}", subject["digest"]):
        errors.append("request.subject.digest must be a lowercase SHA-256 digest")
    inputs = require_list(obj.get("inputs"), "request.inputs", errors)
    if not inputs:
        errors.append("request.inputs must not be empty")
    seen: set[tuple[str, str]] = set()
    for index, raw in enumerate(inputs):
        item = require_dict(raw, f"request.inputs[{index}]", errors)
        for field in ("kind", "path", "sha256"):
            require_text(item.get(field), f"request.inputs[{index}].{field}", errors)
        digest = item.get("sha256")
        if isinstance(digest, str) and not re.fullmatch(r"[0-9a-f]{64}", digest):
            errors.append(f"request.inputs[{index}].sha256 must be a lowercase SHA-256 digest")
        canonical = item.get("canonicalSha256")
        if canonical is not None and (not isinstance(canonical, str) or not re.fullmatch(r"[0-9a-f]{64}", canonical)):
            errors.append(f"request.inputs[{index}].canonicalSha256 must be null or a lowercase SHA-256 digest")
        key = (str(item.get("kind")), str(item.get("path")))
        if key in seen:
            errors.append(f"duplicate request input binding: {key[0]} {key[1]}")
        seen.add(key)
    context = require_dict(obj.get("context"), "request.context", errors)
    for field in ("role", "taskProfile", "assuranceTier"):
        require_text(context.get(field), f"request.context.{field}", errors)
    if context.get("assuranceTier") not in {"routine", "material", "consequential", "critical"}:
        errors.append("request.context.assuranceTier is invalid")
    for field in ("changeClasses", "hints", "paths", "lensIds", "assignmentIds"):
        if field in context and not isinstance(context.get(field), list):
            errors.append(f"request.context.{field} must be an array")
    if "runTools" in context and not isinstance(context.get("runTools"), bool):
        errors.append("request.context.runTools must be boolean")
    authority = require_dict(obj.get("authority"), "request.authority", errors)
    if authority.get("readOnly") is not True:
        errors.append("request.authority.readOnly must be true")
    if authority.get("mayMutateSubject") is not False:
        errors.append("request.authority.mayMutateSubject must be false")
    if authority.get("mayGrantEffects") is not False:
        errors.append("request.authority.mayGrantEffects must be false")
    supplied = obj.get("requestDigest")
    if not isinstance(supplied, str) or not re.fullmatch(r"[0-9a-f]{64}", supplied):
        errors.append("request.requestDigest must be a lowercase SHA-256 digest")
    elif isinstance(data, dict):
        payload = {key: value for key, value in obj.items() if key != "requestDigest"}
        calculated = canonical_digest(payload)
        if supplied != calculated:
            errors.append(f"request.requestDigest mismatch: expected {calculated}")
    return {
        "kind": "profile-capability-request", "valid": not errors,
        "errors": errors, "warnings": warnings,
        "digest": canonical_digest(obj) if isinstance(data, dict) else None,
    }


def validate_profile_capability_result(
    data: Any,
    *,
    expected_profile_id: str | None = None,
    expected_profile_version: str | None = None,
    expected_operation: str | None = None,
    expected_request_digest: str | None = None,
) -> dict[str, Any]:
    """Validate one typed, non-authority-bearing profile capability result."""
    errors: list[str] = []
    warnings: list[str] = []
    obj = require_dict(data, "profile capability result", errors)
    required = [
        "schema", "profileId", "profileVersion", "capability", "operation",
        "status", "requestDigest", "payload", "warnings", "errors", "limitations",
    ]
    check_required(obj, required, "profile capability result", errors)
    if obj.get("schema") != "bbk.profile-capability-result.v1":
        errors.append("result.schema must equal bbk.profile-capability-result.v1")
    for field in ("profileId", "profileVersion", "capability", "operation", "status", "requestDigest"):
        require_text(obj.get(field), f"result.{field}", errors)
    if obj.get("capability") not in {"state_decision_effect", "review_assurance"}:
        errors.append("result.capability is invalid")
    if obj.get("operation") not in PROFILE_CAPABILITY_OPERATIONS:
        errors.append("result.operation is invalid")
    if obj.get("status") not in {"PASS", "PASS_ADVISORY", "PARTIAL", "BLOCKED", "UNSUPPORTED", "ERROR"}:
        errors.append("result.status is invalid")
    if not isinstance(obj.get("payload"), (dict, type(None))):
        errors.append("result.payload must be an object or null")
    for field in ("warnings", "errors", "limitations"):
        values = obj.get(field)
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            errors.append(f"result.{field} must be an array of strings")
    digest = obj.get("requestDigest")
    if isinstance(digest, str) and not re.fullmatch(r"[0-9a-f]{64}", digest):
        errors.append("result.requestDigest must be a lowercase SHA-256 digest")
    expectations = {
        "profileId": expected_profile_id,
        "profileVersion": expected_profile_version,
        "operation": expected_operation,
        "requestDigest": expected_request_digest,
    }
    for field, expected in expectations.items():
        if expected is not None and obj.get(field) != expected:
            errors.append(f"result.{field} does not match the dispatch request")
    if obj.get("status") in {"BLOCKED", "ERROR"} and not obj.get("errors"):
        warnings.append("blocked/error profile result has no explanatory errors")
    return {
        "kind": "profile-capability-result", "valid": not errors,
        "errors": errors, "warnings": warnings,
        "digest": canonical_digest(obj) if isinstance(data, dict) else None,
    }

def validate_profile(data: Any) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    obj = require_dict(data, "profile", errors)
    for field in ("schema", "id", "name", "version", "maturity", "authority", "entrypoints"):
        if field not in obj:
            errors.append(f"profile.{field} is required")
    if obj.get("schema") != "bbk.language-profile.v1":
        errors.append("profile.schema must equal bbk.language-profile.v1")
    profile_id = obj.get("id")
    if not isinstance(profile_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", profile_id):
        errors.append("profile.id must be a safe BBK identifier")
    requires_value = obj.get("requires")
    if requires_value is None:
        requires = {}
        warnings.append("legacy profile has no requires.bbk_minimum declaration")
    else:
        requires = require_dict(requires_value, "profile.requires", errors)
        if "bbk_minimum" in requires:
            require_text(requires.get("bbk_minimum"), "profile.requires.bbk_minimum", errors)
        else:
            warnings.append("profile has no requires.bbk_minimum declaration")
    if not obj.get("package"):
        warnings.append("legacy profile has no package identifier")
    authority = require_dict(obj.get("authority"), "profile.authority", errors)
    allowed_true = {"may_add_gate_recipes", "may_add_procedure", "may_add_review_criteria"}
    prohibited = {"may_declare_pass", "may_expand_work_scope", "may_grant_tools_or_effects", "may_reduce_assurance"}
    for field in sorted(prohibited):
        if not isinstance(authority.get(field), bool):
            errors.append(f"profile.authority.{field} must be boolean")
    for field in sorted(allowed_true):
        if field in authority and not isinstance(authority.get(field), bool):
            errors.append(f"profile.authority.{field} must be boolean when present")
        elif field not in authority:
            warnings.append(f"legacy profile omits authority.{field}; procedure/review/gate additions remain advisory")
    for field in prohibited:
        if authority.get(field) is True:
            errors.append(f"profile may not set authority.{field}=true")
    entrypoints = require_dict(obj.get("entrypoints"), "profile.entrypoints", errors)
    if not isinstance(entrypoints.get("resolve"), list) or not entrypoints.get("resolve"):
        errors.append("profile.entrypoints.resolve must be a non-empty argv array")
    for key, value in sorted(entrypoints.items()):
        if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
            errors.append(f"profile.entrypoints.{key} must be a non-empty argv array of strings")
    capabilities = obj.get("capabilities") if isinstance(obj.get("capabilities"), dict) else {}
    support = capabilities.get("implementation_structure")
    support_status = "legacy-unprojected"
    if support is not None:
        support_obj = require_dict(support, "profile.capabilities.implementation_structure", errors)
        support_status = str(support_obj.get("status", "invalid")).lower()
        if support_status not in {"supported", "partial", "unsupported"}:
            errors.append("implementation_structure.status is invalid")
        for field in ("artifact_kinds", "contract_kinds", "type_concepts", "touchpoint_kinds", "trigger_hints"):
            if not isinstance(support_obj.get(field), list):
                errors.append(f"implementation_structure.{field} must be an array")
        if support_status in {"supported", "partial"} and not isinstance(entrypoints.get("structure"), list):
            errors.append("supported/partial implementation structure requires entrypoints.structure")
        if support_status == "supported" and not isinstance(entrypoints.get("slice"), list):
            warnings.append("supported implementation structure has no slice entrypoint; generic slicing will be used")
    else:
        warnings.append("legacy profile: generic contracts are valid but no profile-specific structure projection is declared")

    state_effect = capabilities.get("state_decision_effect")
    state_effect_status = "legacy-summary"
    if state_effect is not None:
        state_effect_obj = require_dict(state_effect, "profile.capabilities.state_decision_effect", errors)
        state_effect_status = str(state_effect_obj.get("status", "invalid")).lower().replace("_", "-")
        if state_effect_status not in {"supported", "partial", "legacy-summary", "unsupported"}:
            errors.append("state_decision_effect.status is invalid")
        for field in ("representations", "boundary_concepts", "formal_model_tools", "limitations"):
            if field in state_effect_obj and not isinstance(state_effect_obj.get(field), list):
                errors.append(f"state_decision_effect.{field} must be an array")
        for field in ("projection_entrypoint", "inventory_entrypoint", "review_entrypoint"):
            value = state_effect_obj.get(field)
            if value is not None and not isinstance(value, str):
                errors.append(f"state_decision_effect.{field} must be an entrypoint name string")
            if isinstance(value, str) and not isinstance(entrypoints.get(value), list):
                errors.append(f"state_decision_effect.{field} references missing entrypoint {value}")
        dispatch_protocol = state_effect_obj.get("dispatch_protocol")
        if dispatch_protocol is not None and dispatch_protocol != "bbk.profile-capability.v1":
            errors.append("state_decision_effect.dispatch_protocol must equal bbk.profile-capability.v1 when present")
        state_fields = ("projection_entrypoint", "inventory_entrypoint", "review_entrypoint")
        if dispatch_protocol == "bbk.profile-capability.v1":
            if state_effect_status == "supported":
                for field in state_fields:
                    if not isinstance(state_effect_obj.get(field), str):
                        errors.append(f"typed supported state_decision_effect requires {field}")
            elif state_effect_status == "partial":
                if not any(isinstance(state_effect_obj.get(field), str) for field in state_fields):
                    errors.append("typed partial state_decision_effect requires at least one specialized entrypoint reference")
                if not isinstance(state_effect_obj.get("limitations"), list) or not state_effect_obj.get("limitations"):
                    errors.append("typed partial state_decision_effect requires non-empty limitations")
        elif state_effect_status in {"supported", "partial"}:
            warnings.append("state_decision_effect is declared without dispatch_protocol; automatic alpha.8 dispatch is disabled")
    else:
        warnings.append("profile has no state_decision_effect capability; classified as legacy-summary")

    review_assurance = capabilities.get("review_assurance")
    review_status = "legacy-no-review-manifest"
    if review_assurance is not None:
        review_obj = require_dict(review_assurance, "profile.capabilities.review_assurance", errors)
        review_status = str(review_obj.get("status", "invalid")).lower().replace("_", "-")
        if review_status not in {"supported", "partial", "legacy-no-review-manifest", "unsupported"}:
            errors.append("review_assurance.status is invalid")
        for field in ("lens_ids", "context_selectors", "evidence_adapters", "limitations"):
            if field in review_obj and not isinstance(review_obj.get(field), list):
                errors.append(f"review_assurance.{field} must be an array")
        for field in ("context_entrypoint", "review_entrypoint", "evidence_entrypoint"):
            value = review_obj.get(field)
            if value is not None and not isinstance(value, str):
                errors.append(f"review_assurance.{field} must be an entrypoint name string")
            if isinstance(value, str) and not isinstance(entrypoints.get(value), list):
                errors.append(f"review_assurance.{field} references missing entrypoint {value}")
        dispatch_protocol = review_obj.get("dispatch_protocol")
        if dispatch_protocol is not None and dispatch_protocol != "bbk.profile-capability.v1":
            errors.append("review_assurance.dispatch_protocol must equal bbk.profile-capability.v1 when present")
        review_fields = ("context_entrypoint", "review_entrypoint", "evidence_entrypoint")
        if dispatch_protocol == "bbk.profile-capability.v1":
            if review_status == "supported":
                for field in review_fields:
                    if not isinstance(review_obj.get(field), str):
                        errors.append(f"typed supported review_assurance requires {field}")
                if not isinstance(review_obj.get("lens_ids"), list) or not review_obj.get("lens_ids"):
                    errors.append("typed supported review_assurance requires non-empty lens_ids")
            elif review_status == "partial":
                if not any(isinstance(review_obj.get(field), str) for field in review_fields):
                    errors.append("typed partial review_assurance requires at least one specialized entrypoint reference")
                if not isinstance(review_obj.get("limitations"), list) or not review_obj.get("limitations"):
                    errors.append("typed partial review_assurance requires non-empty limitations")
        elif review_status in {"supported", "partial"}:
            warnings.append("review_assurance is declared without dispatch_protocol; automatic alpha.8 dispatch is disabled")
    else:
        warnings.append("profile has no review_assurance capability; classified as legacy-no-review-manifest")

    return {
        "kind": "language-profile", "valid": not errors, "errors": errors, "warnings": warnings,
        "implementationStructureSupport": support_status,
        "stateDecisionEffectSupport": state_effect_status,
        "stateDecisionEffectDispatch": (
            "typed-v1" if isinstance(state_effect, dict) and state_effect.get("dispatch_protocol") == "bbk.profile-capability.v1"
            else "legacy-declared" if state_effect_status in {"supported", "partial"}
            else "none"
        ),
        "reviewAssuranceSupport": review_status,
        "reviewAssuranceDispatch": (
            "typed-v1" if isinstance(review_assurance, dict) and review_assurance.get("dispatch_protocol") == "bbk.profile-capability.v1"
            else "legacy-declared" if review_status in {"supported", "partial"}
            else "none"
        ),
        "digest": canonical_digest(obj) if isinstance(data, dict) else None,
    }

def markdown_solution_outcome_fit(data: dict[str, Any]) -> str:
    applicability = data.get("applicability", {})
    intervention = data.get("requestedIntervention", {})
    baseline = data.get("currentBaseline", {})
    hypothesis = data.get("causalHypothesis", {})
    risk = data.get("risk", {})
    disposition = data.get("disposition", {})
    counterfactual = data.get("counterfactual", {})
    traceability = data.get("traceability", {})
    lines = [
        f"# {data.get('title', 'Solution–Outcome Fit')}", "",
        f"**Fit:** `{data.get('fitId')}` revision `{data.get('revision')}`  ",
        f"**Status:** `{data.get('status')}`  ",
        f"**Applicability:** `{applicability.get('level')}`  ",
        f"**Risk:** `{risk.get('derivedTier')}` (`C{risk.get('consequence')}` / `I{risk.get('irreversibility')}` / `U{risk.get('uncertainty')}` / `X{risk.get('interfaceExposure')}`)  ",
        f"**Disposition:** `{disposition.get('status')}`", "",
        "## Requested intervention", "",
        str(intervention.get("statement", "")), "",
        f"- Source: `{intervention.get('source')}`",
        f"- Role: `{intervention.get('role')}`",
        f"- Mandatory: `{intervention.get('mandatory')}`",
        f"- Rationale: {intervention.get('rationale') or '—'}", "",
        "## Desired outcomes", "",
    ]
    for outcome in data.get("desiredOutcomes", []):
        lines += [f"### `{outcome.get('id')}`", "", str(outcome.get("statement", "")), "", "Success measures:"]
        lines += [f"- {value}" for value in outcome.get("successMeasures", [])] or ["- —"]
        lines.append("")
    lines += [
        "## Current or no-intervention baseline", "", str(baseline.get("description", "")), "",
        "Current approach:", *([f"- {value}" for value in baseline.get("currentApproach", [])] or ["- —"]), "",
        "Strengths worth preserving:", *([f"- {value}" for value in baseline.get("strengths", [])] or ["- —"]), "",
        "Costs and pain:", *([f"- {value}" for value in baseline.get("costsAndPain", [])] or ["- —"]), "",
        "No-change consequences:", *([f"- {value}" for value in baseline.get("noChangeConsequences", [])] or ["- —"]), "",
        "## Causal hypothesis", "", str(hypothesis.get("statement", "")), "",
        f"**Mechanism:** {hypothesis.get('mechanism') or '—'}  ",
        f"**Confidence:** `{hypothesis.get('confidence')}`", "",
        "Assumptions:", *([f"- {value}" for value in hypothesis.get("assumptions", [])] or ["- —"]), "",
        "Falsifiers:", *([f"- {value}" for value in hypothesis.get("falsifiers", [])] or ["- —"]), "",
        "## Constraints, preferences and assumptions", "",
        "| ID | Kind | Statement | Source |", "|---|---|---|---|",
    ]
    for item in data.get("constraints", []):
        lines.append(f"| `{item.get('id')}` | {item.get('kind')} | {item.get('statement')} | {item.get('source')} |")
    if not data.get("constraints"):
        lines.append("| — | — | — | — |")
    lines += ["", "## Alternatives", "", "| ID | Kind | Fit | Disposition | Intervention |", "|---|---|---|---|---|"]
    for item in data.get("alternatives", []):
        lines.append(f"| `{item.get('id')}` | {item.get('kind')} | {item.get('fit')} | {item.get('disposition')} | {item.get('intervention')} |")
    if not data.get("alternatives"):
        lines.append("| — | — | — | — | — |")
    lines += [
        "", "## Counterfactual", "", str(counterfactual.get("question", "")), "",
        "The requested intervention may be delivered while the outcome remains unmet when:",
        *([f"- {value}" for value in counterfactual.get("failureConditions", [])] or ["- —"]), "",
        f"**Conclusion:** {counterfactual.get('conclusion') or '—'}", "",
        "## Outcome evidence", "",
        "| ID | Outcome | Method | Measure | Threshold or signal | Observation window |",
        "|---|---|---|---|---|---|",
    ]
    for item in data.get("successEvidence", []):
        lines.append(f"| `{item.get('id')}` | `{item.get('outcomeRef')}` | {item.get('method')} | {item.get('measure')} | {item.get('thresholdOrSignal')} | {item.get('observationWindow')} |")
    if not data.get("successEvidence"):
        lines.append("| — | — | — | — | — | — |")
    lines += [
        "", "## Disposition", "", f"**Selected direction:** {disposition.get('selectedDirection') or '—'}", "",
        str(disposition.get("rationale", "")), "",
        f"- Authority: `{disposition.get('authorityMode')}`",
        f"- Approval references: {', '.join(f'`{value}`' for value in disposition.get('approvalRefs', [])) or '—'}", "",
        "Investigation plan:", *([f"- {value}" for value in disposition.get("investigationPlan", [])] or ["- —"]), "",
        "Blockers:", *([f"- {value}" for value in disposition.get("blockers", [])] or ["- —"]), "",
        "## Traceability", "",
        f"- Outcomes: {', '.join(f'`{value}`' for value in traceability.get('outcomeRefs', [])) or '—'}",
        f"- Needs: {', '.join(f'`{value}`' for value in traceability.get('needRefs', [])) or '—'}",
        f"- Requirements: {', '.join(f'`{value}`' for value in traceability.get('requirementRefs', [])) or '—'}",
        f"- Decisions: {', '.join(f'`{value}`' for value in traceability.get('decisionRefs', [])) or '—'}",
        f"- Architecture: {', '.join(f'`{value}`' for value in traceability.get('architectureRefs', [])) or '—'}",
        f"- Capabilities: {', '.join(f'`{value}`' for value in traceability.get('capabilityRefs', [])) or '—'}",
        f"- Work units: {', '.join(f'`{value}`' for value in traceability.get('workUnitRefs', [])) or '—'}", "",
    ]
    return "\n".join(lines)

def markdown_structure(data: dict[str, Any]) -> str:
    subject = data.get("subject", {})
    applicability = data.get("applicability", {})
    structure = data.get("structure", {})
    decisions = data.get("decisions", {})
    review = data.get("review", {})
    lines = [
        f"# {data.get('title', 'Implementation Structure')}", "",
        f"**Contract:** `{data.get('contractId')}` revision `{data.get('revision')}`  ",
        f"**Status:** `{data.get('status')}`  ",
        f"**Subject kind:** `{subject.get('kind')}`  ",
        f"**Applicability:** `{applicability.get('level')}`", "",
        "## Purpose", "", str(subject.get("purpose", "")), "",
        "## Scope and basis", "",
        f"- Baselines: {', '.join(f'`{x}`' for x in subject.get('baselineRefs', [])) or '—'}",
        f"- Scope: {', '.join(f'`{x}`' for x in subject.get('scopeRefs', [])) or '—'}",
        f"- Solution–outcome fit: {', '.join(f'`{x}`' for x in subject.get('solutionOutcomeFitRefs', [])) or '—'}",
        f"- Outcomes: {', '.join(f'`{x}`' for x in subject.get('outcomeRefs', [])) or '—'}",
        f"- Capabilities: {', '.join(f'`{x}`' for x in subject.get('capabilityRefs', [])) or '—'}",
        f"- Interfaces: {', '.join(f'`{x}`' for x in subject.get('interfaceRefs', [])) or '—'}", "",
        "## Applicability rationale", "", str(applicability.get("rationale", "")), "",
        "## Artifact or object topology", "",
    ]
    artifacts = structure.get("artifactTopology", [])
    if artifacts:
        lines += ["| ID | Action | Kind | Logical path | Responsibility | Owner |", "|---|---|---|---|---|---|"]
        for item in artifacts:
            lines.append(f"| `{item.get('id')}` | {item.get('action')} | {item.get('kind')} | `{item.get('logicalPath')}` | {item.get('responsibility')} | {item.get('owner')} |")
    else:
        lines.append("—")
    lines += ["", "## Key contracts", ""]
    for item in structure.get("keyContracts", []):
        lines += [f"### `{item.get('id')}` — {item.get('name')}", "", f"**Shape:** `{item.get('shape')}`", "", item.get("responsibility", ""), "", "Invariants:"]
        lines += [f"- {x}" for x in item.get("invariants", [])] or ["- —"]
        if item.get("failureSemantics"):
            lines += ["", "Failure semantics:"] + [f"- {x}" for x in item.get("failureSemantics", [])]
        lines.append("")
    lines += ["## Behavior and control paths", ""]
    for item in structure.get("behaviorPaths", []):
        lines += [f"### `{item.get('id')}` — {item.get('name')}", "", f"Trigger: {item.get('trigger')}", ""]
        for index, step in enumerate(item.get("steps", []), 1):
            lines.append(f"{index}. **{step.get('from')} → {step.get('to')}** — {step.get('interaction')}")
        lines += ["", f"Success: {item.get('success')}", "", "Failure and recovery:"]
        lines += [f"- {x}" for x in item.get("failureAndRecovery", [])] or ["- —"]
        lines.append("")
    lines += ["## State and information ownership", ""]
    for item in structure.get("stateOwnership", []):
        lines.append(f"- **{item.get('state')}** — owner: {item.get('owner')}; lifetime: {item.get('lifetime')}; mutation: {item.get('mutationAuthority')}; recovery: {item.get('recovery')}")
    if not structure.get("stateOwnership"):
        lines.append("—")
    lines += ["", "## Effect boundaries", ""]
    for item in structure.get("effectBoundaries", []):
        lines.append(f"- **{item.get('effect')}** — owner: {item.get('owner')}; authorization: {item.get('authorization')}; failure: {item.get('failure')}; recovery: {item.get('recovery')}")
    if not structure.get("effectBoundaries"):
        lines.append("—")
    lines += ["", "## Fixed decisions", ""]
    for item in decisions.get("fixed", []):
        lines.append(f"- `{item.get('id')}` **{item.get('statement')}** — {item.get('rationale')} Change route: {item.get('changeRoute')}")
    if not decisions.get("fixed"):
        lines.append("—")
    lines += ["", "## Delegated freedom", ""]
    for item in decisions.get("delegated", []):
        lines.append(f"- **{item.get('area')}** — {item.get('bounds')}")
    if not decisions.get("delegated"):
        lines.append("—")
    lines += ["", "## Prohibited shortcuts", ""] + ([f"- {x}" for x in decisions.get("prohibited", [])] or ["—"])
    lines += ["", "## Review", "", f"Assurance: `{review.get('assuranceTier')}`", "", "Acceptance criteria:"] + ([f"- {x}" for x in review.get("acceptanceCriteria", [])] or ["- —"])
    return "\n".join(lines).rstrip() + "\n"

def markdown_slice(data: dict[str, Any]) -> str:
    touch = data.get("touchpoint", {})
    flow = data.get("flow", {})
    atom = data.get("atomicity", {})
    lines = [
        f"# {data.get('title', 'Execution Slice')}", "",
        f"**Slice:** `{data.get('sliceId')}`  ", f"**Status:** `{data.get('status')}`  ",
        f"**Integration owner:** {data.get('integrationOwner')}", "",
        f"**Solution–outcome fit:** {', '.join(f'`{x}`' for x in data.get('solutionOutcomeFitRefs', [])) or '—'}  ",
        f"**Outcomes:** {', '.join(f'`{x}`' for x in data.get('outcomeRefs', [])) or '—'}", "",
        "## Objective", "", str(data.get("objective", "")), "",
        "## Inspectable touchpoint", "",
        f"- Kind: `{touch.get('kind')}`", f"- Actor: {touch.get('actor')}", f"- Interaction: {touch.get('interaction')}", f"- Expected observation: {touch.get('expectedObservation')}", f"- Environment: {touch.get('environment')}", "",
        "## Flow", "",
    ]
    lines += [f"{index}. {step}" for index, step in enumerate(flow.get("steps", []), 1)] or ["—"]
    lines += ["", "## Work units", ""] + ([f"- `{x}`" for x in data.get("workUnitRefs", [])] or ["—"])
    lines += ["", "## Assertions", ""]
    for item in data.get("assertions", []):
        lines.append(f"- `{item.get('id')}` {item.get('statement')} — {item.get('method')}; evidence: {item.get('evidence')}")
    lines += ["", "## Exit conditions", ""] + ([f"- {x}" for x in data.get("exitConditions", [])] or ["—"])
    lines += ["", "## Atomicity", "", f"- coherent: `{atom.get('coherent')}`", f"- reviewable: `{atom.get('reviewable')}`", f"- independently verifiable: `{atom.get('independentlyVerifiable')}`", f"- contained or reversible: `{atom.get('containedOrReversible')}`", f"- rationale: {atom.get('rationale')}", "", "## Temporary scaffolding", ""]
    for item in data.get("scaffolding", []):
        lines.append(f"- `{item.get('id')}` {item.get('purpose')} — disposition: `{item.get('disposition')}`; owner: {item.get('owner')}")
    if not data.get("scaffolding"):
        lines.append("—")
    return "\n".join(lines).rstrip() + "\n"
