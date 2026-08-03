#!/usr/bin/env python3
"""BBK alpha.7 review-assurance contracts and deterministic compilers.

The module plans and records reviews. It deliberately separates required proof,
review planning, context integrity, execution observations, assertion evaluation,
findings, and finding disposition. A BBK review never grants official Blueprint
readiness, execution, release, or organizational authority.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Iterable, Sequence

def _read_bbk_version() -> str:
    """Read the package version from both source-tree and installed layouts.

    In the source tree this module lives in ``tools/`` and ``VERSION`` is one
    directory above it.  The OMP installer copies the module beside ``bbk.py``
    and ``VERSION`` inside the extension directory, so the adjacent path must
    also be supported.  Failing closed on a missing file would make every
    installed CLI command unusable merely by importing this module; retain an
    explicit environment/fallback value for copied or embedded deployments.
    """

    module = Path(__file__).resolve()
    candidates = [module.with_name("VERSION"), module.parents[1] / "VERSION"]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8").strip()
    return os.environ.get("BBK_VERSION", "0.1.0-alpha.7")


BBK_VERSION = _read_bbk_version()

try:
    from contracts import canonical_digest
except ModuleNotFoundError:  # pragma: no cover - package-relative fallback
    from .contracts import canonical_digest  # type: ignore

try:
    from artifact_classification import is_non_operational_example
except ModuleNotFoundError:  # pragma: no cover - package-relative fallback
    from .artifact_classification import is_non_operational_example  # type: ignore

RISK_TIERS = {"routine", "material", "consequential", "critical"}
APPLICABILITY = {"none", "inline", "manifest"}
LENSES = {
    "intent-outcome",
    "specification-acceptance",
    "feasibility-dependency",
    "architecture-boundary",
    "interface-consumer-compatibility",
    "implementation-structure",
    "state-concurrency-effect-recovery",
    "security-privacy-supply-chain",
    "test-evidence",
    "operations-performance-resource",
    "package-install-migration-release",
    "cross-shard-integration",
}
ASSERTION_STATUS = {"PASS", "FAIL", "BLOCKED", "INCONCLUSIVE", "ERROR", "NOT_RUN", "NOT_APPLICABLE"}
AGGREGATES = {"PASS", "PASS_ADVISORY", "NEEDS_REVISION", "BLOCKED_INSUFFICIENT_CONTEXT", "BLOCKED_ENVIRONMENT", "INCONCLUSIVE", "ERROR", "ESCALATED", "CANCELLED", "STALE"}
TRUST_CLASSES = {"DETERMINISTIC_LOCAL", "QUALIFIED_TOOL", "QUALIFIED_EXTERNAL_CHECK", "SIMULATOR_OR_HARNESS", "AGENT_INSPECTION", "HUMAN_REVIEW", "OPERATIONAL_OBSERVATION", "UNSTRUCTURED_OBSERVATION", "LEGACY_IMPORTED"}
DISPOSITIONS = {"FIXED", "REBUTTED", "ACCEPTED_RISK", "FALSE_POSITIVE", "DUPLICATE_OF", "SUPERSEDED", "DEFERRED", "OUT_OF_SCOPE", "REMAINS_OPEN"}
COMPLETENESS = {"COMPLETE", "COMPLETE_WITH_DECLARED_EXCLUSIONS", "PARTIAL_NONBLOCKING", "BLOCKED_REQUIRED_CONTEXT_MISSING", "STALE", "INVALID"}
PRIOR_VISIBILITY = {"HIDDEN", "TARGETED", "FULL", "NOT_APPLICABLE"}


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


def _unique(items: list[Any], field: str, where: str, errors: list[str]) -> set[str]:
    seen: set[str] = set()
    for index, raw in enumerate(items):
        item = _dict(raw, f"{where}[{index}]", errors)
        value = item.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{where}[{index}].{field} must be a non-empty string")
        elif value in seen:
            errors.append(f"duplicate {where}.{field}: {value}")
        else:
            seen.add(value)
    return seen


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def validate_assurance_contract(data: Any) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    obj = _dict(data, "assurance", errors)
    _required(obj, ["schema", "assuranceContractId", "revision", "status", "subject", "riskTier", "changeClasses", "protectedFloors", "assertions", "deterministicGates", "consumerObligations", "faultObligations", "independencePolicy", "evidenceReusePolicy", "repairPolicy", "reviewApplicability", "environmentRefs"], "assurance", errors)
    if obj.get("schema") != "bbk.assurance-contract.v1":
        errors.append("assurance.schema must equal bbk.assurance-contract.v1")
    for field in ("assuranceContractId", "revision"):
        _text(obj.get(field), f"assurance.{field}", errors)
    if obj.get("status") not in {"draft", "accepted", "superseded"}:
        errors.append("assurance.status is invalid")
    subject = _dict(obj.get("subject"), "assurance.subject", errors)
    _required(subject, ["ref", "kind", "revision", "digest"], "assurance.subject", errors)
    for field in ("ref", "kind", "revision"):
        _text(subject.get(field), f"assurance.subject.{field}", errors)
    if not isinstance(subject.get("digest"), str) or not re.fullmatch(r"[0-9a-f]{64}", subject.get("digest", "")):
        errors.append("assurance.subject.digest must be a lowercase SHA-256 digest")
    if obj.get("riskTier") not in RISK_TIERS:
        errors.append("assurance.riskTier is invalid")
    _strings(obj.get("changeClasses"), "assurance.changeClasses", errors)
    _strings(obj.get("protectedFloors"), "assurance.protectedFloors", errors)
    assertions = _list(obj.get("assertions"), "assurance.assertions", errors)
    assertion_ids = _unique(assertions, "assertionId", "assurance.assertions", errors)
    if not assertions:
        errors.append("assurance.assertions must not be empty")
    owners: dict[str, str] = {}
    for index, raw in enumerate(assertions):
        item = _dict(raw, f"assurance.assertions[{index}]", errors)
        _required(item, ["assertionId", "statement", "owner", "methods", "requiredEvidence", "blocking", "lensHints", "independence"], f"assurance.assertions[{index}]", errors)
        assertion_id = _text(item.get("assertionId"), f"assurance.assertions[{index}].assertionId", errors)
        _text(item.get("statement"), f"assurance.assertions[{index}].statement", errors)
        owner = _text(item.get("owner"), f"assurance.assertions[{index}].owner", errors)
        if assertion_id:
            owners[assertion_id] = owner
        _strings(item.get("methods"), f"assurance.assertions[{index}].methods", errors, nonempty=True)
        _strings(item.get("requiredEvidence"), f"assurance.assertions[{index}].requiredEvidence", errors)
        if not isinstance(item.get("blocking"), bool):
            errors.append(f"assurance.assertions[{index}].blocking must be boolean")
        hints = _strings(item.get("lensHints"), f"assurance.assertions[{index}].lensHints", errors)
        for hint in hints:
            if hint not in LENSES:
                errors.append(f"assurance assertion {assertion_id} has unknown lens hint {hint}")
        independence = _dict(item.get("independence"), f"assurance.assertions[{index}].independence", errors)
        _required(independence, ["required", "reason", "dimensions"], f"assurance.assertions[{index}].independence", errors)
        if not isinstance(independence.get("required"), bool):
            errors.append(f"assurance.assertions[{index}].independence.required must be boolean")
        if independence.get("required"):
            _text(independence.get("reason"), f"assurance.assertions[{index}].independence.reason", errors)
            _strings(independence.get("dimensions"), f"assurance.assertions[{index}].independence.dimensions", errors, nonempty=True)
    gates = _list(obj.get("deterministicGates"), "assurance.deterministicGates", errors)
    _unique(gates, "gateId", "assurance.deterministicGates", errors)
    for index, raw in enumerate(gates):
        item = _dict(raw, f"assurance.deterministicGates[{index}]", errors)
        _required(item, ["gateId", "assertionRefs", "required", "method", "evidenceKind"], f"assurance.deterministicGates[{index}]", errors)
        refs = _strings(item.get("assertionRefs"), f"assurance.deterministicGates[{index}].assertionRefs", errors)
        for ref in refs:
            if ref not in assertion_ids:
                errors.append(f"gate {item.get('gateId')} references unknown assertion {ref}")
        if not isinstance(item.get("required"), bool):
            errors.append(f"assurance.deterministicGates[{index}].required must be boolean")
        _text(item.get("method"), f"assurance.deterministicGates[{index}].method", errors)
        _text(item.get("evidenceKind"), f"assurance.deterministicGates[{index}].evidenceKind", errors)
    for field in ("consumerObligations", "faultObligations", "environmentRefs"):
        _strings(obj.get(field), f"assurance.{field}", errors)
    independence = _dict(obj.get("independencePolicy"), "assurance.independencePolicy", errors)
    _required(independence, ["required", "reason", "dimensions", "overlapPolicy"], "assurance.independencePolicy", errors)
    if not isinstance(independence.get("required"), bool):
        errors.append("assurance.independencePolicy.required must be boolean")
    _strings(independence.get("dimensions"), "assurance.independencePolicy.dimensions", errors)
    if independence.get("overlapPolicy") not in {"reject", "allow-complementary-with-rationale"}:
        errors.append("assurance.independencePolicy.overlapPolicy is invalid")
    reuse = _dict(obj.get("evidenceReusePolicy"), "assurance.evidenceReusePolicy", errors)
    _required(reuse, ["allowed", "dependencyKeys", "validityWindow"], "assurance.evidenceReusePolicy", errors)
    if not isinstance(reuse.get("allowed"), bool):
        errors.append("assurance.evidenceReusePolicy.allowed must be boolean")
    _strings(reuse.get("dependencyKeys"), "assurance.evidenceReusePolicy.dependencyKeys", errors, nonempty=reuse.get("allowed") is True)
    _text(reuse.get("validityWindow"), "assurance.evidenceReusePolicy.validityWindow", errors)
    repair = _dict(obj.get("repairPolicy"), "assurance.repairPolicy", errors)
    _required(repair, ["ordinaryCycles", "hardCeiling", "earlyEscalationTriggers"], "assurance.repairPolicy", errors)
    if not isinstance(repair.get("ordinaryCycles"), int) or repair.get("ordinaryCycles", 0) < 0:
        errors.append("assurance.repairPolicy.ordinaryCycles must be a non-negative integer")
    if not isinstance(repair.get("hardCeiling"), int) or repair.get("hardCeiling", 0) < 1:
        errors.append("assurance.repairPolicy.hardCeiling must be a positive integer")
    if isinstance(repair.get("ordinaryCycles"), int) and isinstance(repair.get("hardCeiling"), int) and repair["hardCeiling"] < repair["ordinaryCycles"]:
        errors.append("assurance.repairPolicy.hardCeiling may not be lower than ordinaryCycles")
    _strings(repair.get("earlyEscalationTriggers"), "assurance.repairPolicy.earlyEscalationTriggers", errors)
    if obj.get("reviewApplicability") not in APPLICABILITY:
        errors.append("assurance.reviewApplicability is invalid")
    if obj.get("riskTier") in {"consequential", "critical"} and obj.get("reviewApplicability") == "none":
        warnings.append("consequential/critical assurance uses no persisted review; confirm a stronger deterministic method fully discharges every assertion")
    return {"kind": "assurance-contract", "valid": not errors, "errors": errors, "warnings": warnings, "digest": canonical_digest(obj) if isinstance(data, dict) else None, "assertionCount": len(assertions)}


def _lens_for_assertion(assertion: dict[str, Any], change_classes: Sequence[str]) -> str:
    hints = [value for value in assertion.get("lensHints", []) if value in LENSES]
    if hints:
        return hints[0]
    text = " ".join([str(assertion.get("statement", "")), *map(str, assertion.get("methods", [])), *map(str, change_classes)]).casefold()
    rules = [
        (("outcome", "intent", "fit", "scope"), "intent-outcome"),
        (("acceptance", "requirement", "specification"), "specification-acceptance"),
        (("dependency", "feasibility", "build"), "feasibility-dependency"),
        (("architecture", "boundary", "module"), "architecture-boundary"),
        (("interface", "consumer", "compatibility", "schema", "api"), "interface-consumer-compatibility"),
        (("structure", "artifact", "delegated freedom"), "implementation-structure"),
        (("state", "concurrency", "effect", "retry", "recovery", "cancellation"), "state-concurrency-effect-recovery"),
        (("security", "privacy", "credential", "dependency", "supply"), "security-privacy-supply-chain"),
        (("test", "evidence", "coverage", "verification"), "test-evidence"),
        (("operational", "performance", "resource", "observability"), "operations-performance-resource"),
        (("package", "install", "migration", "release", "rollback"), "package-install-migration-release"),
    ]
    for tokens, lens in rules:
        if any(token in text for token in tokens):
            return lens
    return "specification-acceptance"


def compile_review_manifest(assurance: dict[str, Any], *, purpose: str, manifest_id: str, subject_override: dict[str, Any] | None = None, environment_capabilities: Sequence[str] = ()) -> dict[str, Any]:
    validation = validate_assurance_contract(assurance)
    if not validation["valid"]:
        raise ValueError("invalid AssuranceContract: " + "; ".join(validation["errors"]))
    subject = dict(subject_override or assurance["subject"])
    applicability = assurance.get("reviewApplicability") or ("inline" if assurance["riskTier"] == "routine" else "manifest")
    assignments: list[dict[str, Any]] = []
    for assertion in assurance["assertions"]:
        lens = _lens_for_assertion(assertion, assurance.get("changeClasses", []))
        assignments.append({
            "assignmentId": f"LA-{assertion['assertionId']}",
            "lens": lens,
            "primaryAssertionRefs": [assertion["assertionId"]],
            "method": assertion["methods"][0],
            "evidenceRequirements": assertion.get("requiredEvidence", []),
            "reviewerCapabilityRequirements": [lens],
            "independence": assertion.get("independence", {}),
            "contextSelector": {"include": ["subject", "governing-contracts", "assertion-evidence"], "exclude": ["unrelated-history"]},
            "blocking": bool(assertion.get("blocking")),
        })
    required_evidence = [{"gateId": gate["gateId"], "assertionRefs": gate.get("assertionRefs", []), "evidenceKind": gate.get("evidenceKind"), "required": gate.get("required", False)} for gate in assurance.get("deterministicGates", [])]
    prior_policy = "HIDDEN" if assurance["riskTier"] in {"consequential", "critical"} else "NOT_APPLICABLE"
    return {
        "schema": "bbk.review-manifest.v1",
        "manifestId": manifest_id,
        "revision": "1",
        "status": "planned",
        "purpose": purpose,
        "gateKind": "acceptance" if assurance["riskTier"] in {"consequential", "critical"} else "focused",
        "applicability": applicability,
        "subject": subject,
        "assuranceContract": {"ref": assurance["assuranceContractId"], "digest": canonical_digest(assurance)},
        "requiredAssertionRefs": [item["assertionId"] for item in assurance["assertions"]],
        "lensAssignments": assignments,
        "independenceRequirements": assurance["independencePolicy"],
        "priorFindingsVisibility": prior_policy,
        "contextPolicy": {"requiredKinds": ["subject", "assurance-contract"], "requiredPaths": [], "includePatterns": ["**"], "excludePatterns": [".git/**", ".bbk/**"], "redactionClass": "project-local", "maxPackBytes": 4 * 1024 * 1024},
        "shardPlan": {"mode": "none", "grouping": "execution-slice-or-responsibility", "crossShardAssertionRefs": []},
        "requiredDeterministicEvidence": required_evidence,
        "aggregationPolicy": {"nonAveraging": True, "allowPassAdvisory": True, "centralBlocking": True, "protectedFloors": assurance.get("protectedFloors", [])},
        "repairPolicy": assurance["repairPolicy"],
        "dependencyClosure": ["subject.digest", "assuranceContract.digest", "context.contentRoot", "profile.digest", "environment.digest"],
        "provenance": {"compiler": "bbk-review-planner", "bbkVersion": BBK_VERSION, "environmentCapabilities": sorted(set(environment_capabilities))},
        "authorityDisclaimer": "This BBK review plan is non-authoritative relative to Blueprint and grants no mutation, waiver, execution, or release authority.",
    }


def validate_review_manifest(data: Any, assurance: dict[str, Any] | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    obj = _dict(data, "manifest", errors)
    _required(obj, ["schema", "manifestId", "revision", "status", "purpose", "gateKind", "applicability", "subject", "assuranceContract", "requiredAssertionRefs", "lensAssignments", "independenceRequirements", "priorFindingsVisibility", "contextPolicy", "shardPlan", "requiredDeterministicEvidence", "aggregationPolicy", "repairPolicy", "dependencyClosure", "provenance", "authorityDisclaimer"], "manifest", errors)
    if obj.get("schema") != "bbk.review-manifest.v1":
        errors.append("manifest.schema must equal bbk.review-manifest.v1")
    for field in ("manifestId", "revision", "purpose", "gateKind", "authorityDisclaimer"):
        _text(obj.get(field), f"manifest.{field}", errors)
    if obj.get("status") not in {"planned", "active", "completed", "stale", "superseded"}:
        errors.append("manifest.status is invalid")
    if obj.get("applicability") not in APPLICABILITY:
        errors.append("manifest.applicability is invalid")
    subject = _dict(obj.get("subject"), "manifest.subject", errors)
    _required(subject, ["ref", "kind", "revision", "digest"], "manifest.subject", errors)
    for field in ("ref", "kind", "revision"):
        _text(subject.get(field), f"manifest.subject.{field}", errors)
    if not isinstance(subject.get("digest"), str) or not re.fullmatch(r"[0-9a-f]{64}", subject.get("digest", "")):
        errors.append("manifest.subject.digest must be SHA-256")
    assurance_ref = _dict(obj.get("assuranceContract"), "manifest.assuranceContract", errors)
    _required(assurance_ref, ["ref", "digest"], "manifest.assuranceContract", errors)
    _text(assurance_ref.get("ref"), "manifest.assuranceContract.ref", errors)
    if not isinstance(assurance_ref.get("digest"), str) or not re.fullmatch(r"[0-9a-f]{64}", assurance_ref.get("digest", "")):
        errors.append("manifest.assuranceContract.digest must be SHA-256")
    required_assertions = _strings(obj.get("requiredAssertionRefs"), "manifest.requiredAssertionRefs", errors, nonempty=obj.get("applicability") != "none")
    assignments = _list(obj.get("lensAssignments"), "manifest.lensAssignments", errors)
    assignment_ids = _unique(assignments, "assignmentId", "manifest.lensAssignments", errors)
    primary_owners: dict[str, str] = {}
    overlap: list[str] = []
    for index, raw in enumerate(assignments):
        item = _dict(raw, f"manifest.lensAssignments[{index}]", errors)
        _required(item, ["assignmentId", "lens", "primaryAssertionRefs", "method", "evidenceRequirements", "reviewerCapabilityRequirements", "independence", "contextSelector", "blocking"], f"manifest.lensAssignments[{index}]", errors)
        if item.get("lens") not in LENSES:
            errors.append(f"manifest.lensAssignments[{index}].lens is invalid")
        refs = _strings(item.get("primaryAssertionRefs"), f"manifest.lensAssignments[{index}].primaryAssertionRefs", errors, nonempty=True)
        for ref in refs:
            if ref not in required_assertions:
                errors.append(f"lens assignment references assertion not required by manifest: {ref}")
            if ref in primary_owners:
                overlap.append(ref)
            else:
                primary_owners[ref] = str(item.get("assignmentId"))
        _text(item.get("method"), f"manifest.lensAssignments[{index}].method", errors)
        _strings(item.get("evidenceRequirements"), f"manifest.lensAssignments[{index}].evidenceRequirements", errors)
        _strings(item.get("reviewerCapabilityRequirements"), f"manifest.lensAssignments[{index}].reviewerCapabilityRequirements", errors)
        _dict(item.get("independence"), f"manifest.lensAssignments[{index}].independence", errors)
        _dict(item.get("contextSelector"), f"manifest.lensAssignments[{index}].contextSelector", errors)
        if not isinstance(item.get("blocking"), bool):
            errors.append(f"manifest.lensAssignments[{index}].blocking must be boolean")
    missing_owners = sorted(set(required_assertions) - set(primary_owners))
    if missing_owners and obj.get("applicability") != "none":
        errors.append(f"required assertions lack a primary evaluation owner: {missing_owners}")
    independence = _dict(obj.get("independenceRequirements"), "manifest.independenceRequirements", errors)
    overlap_policy = independence.get("overlapPolicy")
    if overlap and overlap_policy != "allow-complementary-with-rationale":
        errors.append(f"assertion ownership overlaps without complementary rationale policy: {sorted(set(overlap))}")
    elif overlap:
        for ref in sorted(set(overlap)):
            owners = [item for item in assignments if isinstance(item, dict) and ref in (item.get("primaryAssertionRefs") or [])]
            methods = {str(item.get("method", "")) for item in owners}
            lenses = {str(item.get("lens", "")) for item in owners}
            for item in owners[1:]:
                rationale = item.get("independence") if isinstance(item.get("independence"), dict) else {}
                if rationale.get("required") is not True or not str(rationale.get("reason", "")).strip():
                    errors.append(f"overlapping assertion {ref} requires an explicit complementary independence rationale on assignment {item.get('assignmentId')}")
            if len(methods) < 2 and len(lenses) < 2:
                errors.append(f"overlapping assertion {ref} repeats the same method and lens without a distinct assurance property")
    if obj.get("priorFindingsVisibility") not in PRIOR_VISIBILITY:
        errors.append("manifest.priorFindingsVisibility is invalid")
    context = _dict(obj.get("contextPolicy"), "manifest.contextPolicy", errors)
    _required(context, ["requiredKinds", "requiredPaths", "includePatterns", "excludePatterns", "redactionClass", "maxPackBytes"], "manifest.contextPolicy", errors)
    for field in ("requiredKinds", "requiredPaths", "includePatterns", "excludePatterns"):
        _strings(context.get(field), f"manifest.contextPolicy.{field}", errors)
    _text(context.get("redactionClass"), "manifest.contextPolicy.redactionClass", errors)
    if not isinstance(context.get("maxPackBytes"), int) or context.get("maxPackBytes", 0) < 1:
        errors.append("manifest.contextPolicy.maxPackBytes must be a positive integer")
    shard = _dict(obj.get("shardPlan"), "manifest.shardPlan", errors)
    if shard.get("mode") not in {"none", "semantic", "path-fallback"}:
        errors.append("manifest.shardPlan.mode is invalid")
    cross_shard_refs = _strings(shard.get("crossShardAssertionRefs"), "manifest.shardPlan.crossShardAssertionRefs", errors)
    for ref in cross_shard_refs:
        if ref not in required_assertions:
            errors.append(f"cross-shard assertion is not required by manifest: {ref}")
        owners = [item for item in assignments if isinstance(item, dict) and ref in (item.get("primaryAssertionRefs") or [])]
        if not any(item.get("lens") == "cross-shard-integration" for item in owners):
            errors.append(f"cross-shard assertion {ref} requires a cross-shard-integration lens assignment")
    if cross_shard_refs and shard.get("mode") == "none":
        errors.append("cross-shard assertions require semantic or path-fallback sharding")
    _list(obj.get("requiredDeterministicEvidence"), "manifest.requiredDeterministicEvidence", errors)
    aggregate = _dict(obj.get("aggregationPolicy"), "manifest.aggregationPolicy", errors)
    if aggregate.get("nonAveraging") is not True:
        errors.append("manifest.aggregationPolicy.nonAveraging must be true")
    _list(obj.get("dependencyClosure"), "manifest.dependencyClosure", errors)
    _dict(obj.get("provenance"), "manifest.provenance", errors)
    if assurance is not None:
        aresult = validate_assurance_contract(assurance)
        if not aresult["valid"]:
            errors.append("referenced AssuranceContract is invalid")
        if assurance_ref.get("digest") != canonical_digest(assurance):
            errors.append("manifest AssuranceContract digest does not match supplied contract")
        if subject.get("digest") != (assurance.get("subject") or {}).get("digest"):
            errors.append("manifest subject digest differs from AssuranceContract subject digest")
        contract_assertions = {item.get("assertionId") for item in assurance.get("assertions", [])}
        if not set(required_assertions).issuperset(contract_assertions):
            errors.append("ReviewManifest may not omit AssuranceContract assertions")
    return {"kind": "review-manifest", "valid": not errors, "errors": errors, "warnings": warnings, "digest": canonical_digest(obj) if isinstance(data, dict) else None, "assignmentCount": len(assignment_ids), "assertionCount": len(required_assertions)}


def _git_classification(root: Path) -> tuple[set[str], set[str], set[str]]:
    tracked: set[str] = set()
    untracked: set[str] = set()
    ignored: set[str] = set()
    try:
        result = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
        if result.returncode == 0:
            tracked = {value.decode("utf-8", errors="strict") for value in result.stdout.split(b"\0") if value}
        result = subprocess.run(["git", "-C", str(root), "ls-files", "--others", "--exclude-standard", "-z"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
        if result.returncode == 0:
            untracked = {value.decode("utf-8", errors="strict") for value in result.stdout.split(b"\0") if value}
        result = subprocess.run(["git", "-C", str(root), "ls-files", "--others", "--ignored", "--exclude-standard", "-z"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
        if result.returncode == 0:
            ignored = {value.decode("utf-8", errors="strict") for value in result.stdout.split(b"\0") if value}
    except OSError:
        pass
    return tracked, untracked, ignored


def _matches(path: str, patterns: Sequence[str]) -> bool:
    if not patterns:
        return True
    return any(fnmatch.fnmatch(path, pattern) or (pattern.endswith("/**") and (path == pattern[:-3] or path.startswith(pattern[:-3].rstrip("/") + "/"))) for pattern in patterns)


def compile_review_context(manifest: dict[str, Any], root: Path, *, include_patterns: Sequence[str] = (), exclude_patterns: Sequence[str] = (), context_id: str | None = None) -> dict[str, Any]:
    validation = validate_review_manifest(manifest)
    if not validation["valid"]:
        raise ValueError("invalid ReviewManifest: " + "; ".join(validation["errors"]))
    root = root.resolve()
    policy = manifest["contextPolicy"]
    includes = list(include_patterns or policy.get("includePatterns") or ["**"])
    excludes = list(policy.get("excludePatterns") or []) + list(exclude_patterns)
    tracked, untracked, ignored = _git_classification(root)
    included: list[dict[str, Any]] = []
    omitted: list[dict[str, Any]] = []
    required_paths = set(policy.get("requiredPaths") or [])
    found_paths: set[str] = set()
    for directory, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        base = Path(directory)
        kept: list[str] = []
        for name in sorted(dirnames):
            path = base / name
            rel = path.relative_to(root).as_posix()
            if path.is_symlink() or _matches(rel, excludes):
                omitted.append({"path": rel, "reason": "symlink" if path.is_symlink() else "excluded-pattern", "required": rel in required_paths})
                continue
            kept.append(name)
        dirnames[:] = kept
        for name in sorted(filenames):
            path = base / name
            rel = path.relative_to(root).as_posix()
            if is_non_operational_example(path):
                omitted.append({"path": rel, "reason": "non-operational-example", "required": False})
                continue
            if not _matches(rel, includes) or _matches(rel, excludes):
                omitted.append({"path": rel, "reason": "not-selected", "required": rel in required_paths})
                continue
            if path.is_symlink():
                omitted.append({"path": rel, "reason": "symlink", "required": rel in required_paths})
                continue
            try:
                size = path.stat().st_size
                digest = _sha_file(path)
            except OSError as exc:
                omitted.append({"path": rel, "reason": f"unavailable:{exc}", "required": rel in required_paths})
                continue
            found_paths.add(rel)
            source_class = "tracked" if rel in tracked else "untracked" if rel in untracked else "ignored" if rel in ignored else "external-or-non-git"
            generated = any(part in {"dist", "build", "target", "generated", "out"} for part in Path(rel).parts)
            included.append({"itemId": f"FILE-{len(included)+1:05d}", "kind": "file", "path": rel, "bytes": size, "sha256": digest, "sourceClass": source_class, "generated": generated, "redaction": "none"})
    for required in sorted(required_paths - found_paths):
        omitted.append({"path": required, "reason": "required-missing", "required": True})
    content_payload = [{"path": item["path"], "sha256": item["sha256"], "bytes": item["bytes"], "sourceClass": item["sourceClass"], "redaction": item["redaction"]} for item in included]
    content_root = canonical_digest(content_payload)
    total = sum(item["bytes"] for item in included)
    max_pack = int(policy.get("maxPackBytes", 4 * 1024 * 1024))
    shards: list[dict[str, Any]] = []
    if total > max_pack or manifest.get("shardPlan", {}).get("mode") in {"semantic", "path-fallback"}:
        groups: dict[str, list[dict[str, Any]]] = {}
        for item in included:
            parts = Path(item["path"]).parts
            key = parts[0] if len(parts) > 1 else "root"
            groups.setdefault(key, []).append(item)
        for index, key in enumerate(sorted(groups), 1):
            members = groups[key]
            shards.append({"shardId": f"SHARD-{index:03d}", "primaryGroup": key, "primaryItemRefs": [item["itemId"] for item in members], "sharedItemRefs": [], "bytes": sum(item["bytes"] for item in members), "contentRoot": canonical_digest([{"path": item["path"], "sha256": item["sha256"]} for item in members])})
    else:
        shards.append({"shardId": "SHARD-001", "primaryGroup": "complete", "primaryItemRefs": [item["itemId"] for item in included], "sharedItemRefs": [], "bytes": total, "contentRoot": content_root})
    blocking_omissions = [item for item in omitted if item.get("required")]
    if blocking_omissions:
        completeness = "BLOCKED_REQUIRED_CONTEXT_MISSING"
    elif omitted:
        completeness = "COMPLETE_WITH_DECLARED_EXCLUSIONS"
    else:
        completeness = "COMPLETE"
    return {
        "schema": "bbk.review-context-manifest.v1",
        "contextManifestId": context_id or f"RCM-{content_root[:16].upper()}",
        "revision": "1",
        "subject": manifest["subject"],
        "reviewManifest": {"ref": manifest["manifestId"], "digest": canonical_digest(manifest)},
        "root": str(root),
        "contentRoot": content_root,
        "requiredSemanticObjects": list(policy.get("requiredKinds") or []),
        "includedItems": included,
        "retrievalOnlyItems": [],
        "excludedItems": [item for item in omitted if not item.get("required")],
        "omissions": omitted,
        "redactions": [],
        "compiler": {"id": "bbk-review-context-compiler", "version": "1", "policyDigest": canonical_digest(policy)},
        "contextPacks": [{"packId": f"PACK-{item['shardId']}", "shardRef": item["shardId"], "contentRoot": item["contentRoot"], "bytes": item["bytes"]} for item in shards],
        "shards": shards,
        "crossShardAssertions": list(manifest.get("shardPlan", {}).get("crossShardAssertionRefs") or []),
        "completeness": completeness,
        "blockers": [f"required context missing: {item['path']}" for item in blocking_omissions],
        "dependencyClosure": [manifest["subject"]["digest"], canonical_digest(manifest), content_root],
        "authorityDisclaimer": "Context completeness proves what was assembled; it does not prove the subject is correct.",
    }


def validate_review_context(data: Any, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    obj = _dict(data, "context", errors)
    _required(obj, ["schema", "contextManifestId", "revision", "subject", "reviewManifest", "root", "contentRoot", "requiredSemanticObjects", "includedItems", "retrievalOnlyItems", "excludedItems", "omissions", "redactions", "compiler", "contextPacks", "shards", "crossShardAssertions", "completeness", "blockers", "dependencyClosure", "authorityDisclaimer"], "context", errors)
    if obj.get("schema") != "bbk.review-context-manifest.v1":
        errors.append("context.schema must equal bbk.review-context-manifest.v1")
    for field in ("contextManifestId", "revision", "root", "authorityDisclaimer"):
        _text(obj.get(field), f"context.{field}", errors)
    if not isinstance(obj.get("contentRoot"), str) or not re.fullmatch(r"[0-9a-f]{64}", obj.get("contentRoot", "")):
        errors.append("context.contentRoot must be SHA-256")
    included = _list(obj.get("includedItems"), "context.includedItems", errors)
    item_ids = _unique(included, "itemId", "context.includedItems", errors)
    paths: set[str] = set()
    canonical_items = []
    for index, raw in enumerate(included):
        item = _dict(raw, f"context.includedItems[{index}]", errors)
        _required(item, ["itemId", "kind", "path", "bytes", "sha256", "sourceClass", "generated", "redaction"], f"context.includedItems[{index}]", errors)
        path = _text(item.get("path"), f"context.includedItems[{index}].path", errors)
        if path in paths:
            errors.append(f"context includes duplicate path {path}")
        paths.add(path)
        if Path(path).is_absolute() or ".." in Path(path).parts:
            errors.append(f"context path is unsafe: {path}")
        if not isinstance(item.get("bytes"), int) or item.get("bytes", -1) < 0:
            errors.append(f"context.includedItems[{index}].bytes is invalid")
        if not isinstance(item.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", item.get("sha256", "")):
            errors.append(f"context.includedItems[{index}].sha256 is invalid")
        if not isinstance(item.get("generated"), bool):
            errors.append(f"context.includedItems[{index}].generated must be boolean")
        canonical_items.append({"path": item.get("path"), "sha256": item.get("sha256"), "bytes": item.get("bytes"), "sourceClass": item.get("sourceClass"), "redaction": item.get("redaction")})
    calculated = canonical_digest(canonical_items)
    if obj.get("contentRoot") != calculated:
        errors.append("context.contentRoot does not match included item content")
    for field in ("retrievalOnlyItems", "excludedItems", "omissions", "redactions", "contextPacks", "shards", "crossShardAssertions", "blockers", "dependencyClosure", "requiredSemanticObjects"):
        _list(obj.get(field), f"context.{field}", errors)
    primary_items: list[str] = []
    for index, raw in enumerate(obj.get("shards") or []):
        item = _dict(raw, f"context.shards[{index}]", errors)
        _required(item, ["shardId", "primaryGroup", "primaryItemRefs", "sharedItemRefs", "bytes", "contentRoot"], f"context.shards[{index}]", errors)
        refs = _strings(item.get("primaryItemRefs"), f"context.shards[{index}].primaryItemRefs", errors)
        primary_items.extend(refs)
        for ref in refs + list(item.get("sharedItemRefs") or []):
            if ref not in item_ids:
                errors.append(f"shard {item.get('shardId')} references unknown context item {ref}")
    duplicates = sorted({ref for ref in primary_items if primary_items.count(ref) > 1})
    if duplicates:
        errors.append(f"context items have more than one primary shard owner: {duplicates}")
    missing_primary = sorted(item_ids - set(primary_items))
    if missing_primary and included:
        errors.append(f"context items lack a primary shard: {missing_primary}")
    if obj.get("completeness") not in COMPLETENESS:
        errors.append("context.completeness is invalid")
    if obj.get("completeness") == "BLOCKED_REQUIRED_CONTEXT_MISSING" and not obj.get("blockers"):
        errors.append("blocked context requires blockers")
    if manifest is not None:
        if obj.get("reviewManifest", {}).get("digest") != canonical_digest(manifest):
            errors.append("context ReviewManifest digest does not match supplied manifest")
        if obj.get("subject", {}).get("digest") != manifest.get("subject", {}).get("digest"):
            errors.append("context subject digest does not match ReviewManifest")
        expected_cross = sorted(manifest.get("shardPlan", {}).get("crossShardAssertionRefs") or [])
        actual_cross = sorted(obj.get("crossShardAssertions") or [])
        if actual_cross != expected_cross:
            errors.append("context cross-shard assertions do not match ReviewManifest")
        if expected_cross and len(obj.get("shards") or []) < 2:
            errors.append("cross-shard assertions require at least two context shards")
    return {"kind": "review-context-manifest", "valid": not errors, "errors": errors, "warnings": warnings, "digest": canonical_digest(obj) if isinstance(data, dict) else None, "calculatedContentRoot": calculated, "completeness": obj.get("completeness")}


def validate_evidence_receipt(data: Any) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    obj = _dict(data, "receipt", errors)
    _required(obj, ["schema", "receiptId", "kind", "producer", "subject", "assertionRefs", "operation", "startedAt", "completedAt", "completionStatus", "outputs", "toolIdentity", "environmentIdentity", "dependencyFingerprint", "coverage", "trustClass", "redaction", "freshness", "rawEvidenceRef"], "receipt", errors)
    if obj.get("schema") != "bbk.evidence-receipt.v2":
        errors.append("receipt.schema must equal bbk.evidence-receipt.v2")
    for field in ("receiptId", "kind", "producer", "startedAt", "completedAt", "completionStatus"):
        _text(obj.get(field), f"receipt.{field}", errors)
    subject = _dict(obj.get("subject"), "receipt.subject", errors)
    _required(subject, ["ref", "digest"], "receipt.subject", errors)
    _text(subject.get("ref"), "receipt.subject.ref", errors)
    if not isinstance(subject.get("digest"), str) or not re.fullmatch(r"[0-9a-f]{64}", subject.get("digest", "")):
        errors.append("receipt.subject.digest must be SHA-256")
    _strings(obj.get("assertionRefs"), "receipt.assertionRefs", errors)
    operation = _dict(obj.get("operation"), "receipt.operation", errors)
    _required(operation, ["argv", "workingDirectory", "sanitized", "network", "externalEffects"], "receipt.operation", errors)
    argv = _strings(operation.get("argv"), "receipt.operation.argv", errors)
    _text(operation.get("workingDirectory"), "receipt.operation.workingDirectory", errors)
    if not isinstance(operation.get("sanitized"), bool):
        errors.append("receipt.operation.sanitized must be boolean")
    if not isinstance(operation.get("network"), bool) or not isinstance(operation.get("externalEffects"), bool):
        errors.append("receipt.operation network/externalEffects must be boolean")
    sensitive = re.compile(r"(?i)(token|secret|password|api[-_]?key|authorization)")
    if any(sensitive.search(arg) for arg in argv) and not operation.get("sanitized"):
        errors.append("receipt operation appears to contain sensitive material but is not marked sanitized")
    outputs = _dict(obj.get("outputs"), "receipt.outputs", errors)
    _required(outputs, ["exitCode", "stdoutDigest", "stderrDigest", "reportRefs", "artifactRefs", "traceRefs"], "receipt.outputs", errors)
    if outputs.get("exitCode") is not None and not isinstance(outputs.get("exitCode"), int):
        errors.append("receipt.outputs.exitCode must be integer or null")
    for field in ("stdoutDigest", "stderrDigest"):
        value = outputs.get(field)
        if value is not None and (not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)):
            errors.append(f"receipt.outputs.{field} must be SHA-256 or null")
    for field in ("reportRefs", "artifactRefs", "traceRefs"):
        _strings(outputs.get(field), f"receipt.outputs.{field}", errors)
    _dict(obj.get("toolIdentity"), "receipt.toolIdentity", errors)
    _dict(obj.get("environmentIdentity"), "receipt.environmentIdentity", errors)
    fingerprint = obj.get("dependencyFingerprint")
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint or ""):
        errors.append("receipt.dependencyFingerprint must be SHA-256")
    _dict(obj.get("coverage"), "receipt.coverage", errors)
    if obj.get("trustClass") not in TRUST_CLASSES:
        errors.append("receipt.trustClass is invalid")
    _dict(obj.get("redaction"), "receipt.redaction", errors)
    freshness = _dict(obj.get("freshness"), "receipt.freshness", errors)
    _required(freshness, ["dependencyKeys", "validUntil", "stale"], "receipt.freshness", errors)
    _strings(freshness.get("dependencyKeys"), "receipt.freshness.dependencyKeys", errors, nonempty=True)
    if not isinstance(freshness.get("stale"), bool):
        errors.append("receipt.freshness.stale must be boolean")
    if obj.get("trustClass") == "UNSTRUCTURED_OBSERVATION" and obj.get("assertionRefs"):
        warnings.append("unstructured observation names assertions but is not assertion-satisfying by default")
    return {"kind": "evidence-receipt", "valid": not errors, "errors": errors, "warnings": warnings, "digest": canonical_digest(obj) if isinstance(data, dict) else None, "trustClass": obj.get("trustClass")}


def validate_review_attempt(data: Any) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    obj = _dict(data, "attempt", errors)
    _required(obj, ["schema", "attemptId", "runId", "assignmentRef", "lens", "assertionRefs", "reviewer", "invocation", "contextPack", "priorFindingsVisibility", "independenceFacts", "startedAt", "completedAt", "completionState", "assertionEvaluations", "evidenceRefs", "findingRefs", "infrastructureErrors"], "attempt", errors)
    if obj.get("schema") != "bbk.review-attempt.v1":
        errors.append("attempt.schema must equal bbk.review-attempt.v1")
    for field in ("attemptId", "runId", "assignmentRef", "startedAt", "completionState"):
        _text(obj.get(field), f"attempt.{field}", errors)
    if obj.get("lens") not in LENSES and obj.get("lens") != "deterministic-gate":
        errors.append("attempt.lens is invalid")
    _strings(obj.get("assertionRefs"), "attempt.assertionRefs", errors, nonempty=True)
    reviewer = _dict(obj.get("reviewer"), "attempt.reviewer", errors)
    _required(reviewer, ["role", "effectiveDigest", "model", "provider"], "attempt.reviewer", errors)
    _text(reviewer.get("role"), "attempt.reviewer.role", errors)
    if not isinstance(reviewer.get("effectiveDigest"), str) or not re.fullmatch(r"[0-9a-f]{64}", reviewer.get("effectiveDigest", "")):
        errors.append("attempt.reviewer.effectiveDigest must be SHA-256")
    _dict(obj.get("invocation"), "attempt.invocation", errors)
    pack = _dict(obj.get("contextPack"), "attempt.contextPack", errors)
    _required(pack, ["ref", "digest"], "attempt.contextPack", errors)
    if not isinstance(pack.get("digest"), str) or not re.fullmatch(r"[0-9a-f]{64}", pack.get("digest", "")):
        errors.append("attempt.contextPack.digest must be SHA-256")
    if obj.get("priorFindingsVisibility") not in PRIOR_VISIBILITY:
        errors.append("attempt.priorFindingsVisibility is invalid")
    independence = _dict(obj.get("independenceFacts"), "attempt.independenceFacts", errors)
    for field in ("authorSeparation", "roleSeparation", "sessionSeparation", "independentContextAssembly", "modelDiversity", "providerDiversity", "deterministicEvidenceIndependence", "organizationalIndependence", "candidateMutationProhibited"):
        if field not in independence or not isinstance(independence.get(field), bool):
            errors.append(f"attempt.independenceFacts.{field} must be boolean")
    if obj.get("completionState") not in {"COMPLETED", "CANCELLED", "BLOCKED_ENVIRONMENT", "BLOCKED_CONTEXT", "ERROR", "STALE"}:
        errors.append("attempt.completionState is invalid")
    evaluations = _list(obj.get("assertionEvaluations"), "attempt.assertionEvaluations", errors)
    evaluated: set[str] = set()
    for index, raw in enumerate(evaluations):
        item = _dict(raw, f"attempt.assertionEvaluations[{index}]", errors)
        _required(item, ["assertionRef", "status", "rationale", "evidenceRefs"], f"attempt.assertionEvaluations[{index}]", errors)
        ref = _text(item.get("assertionRef"), f"attempt.assertionEvaluations[{index}].assertionRef", errors)
        if ref in evaluated:
            errors.append(f"attempt evaluates assertion more than once: {ref}")
        evaluated.add(ref)
        if item.get("status") not in ASSERTION_STATUS:
            errors.append(f"attempt.assertionEvaluations[{index}].status is invalid")
        _text(item.get("rationale"), f"attempt.assertionEvaluations[{index}].rationale", errors)
        _strings(item.get("evidenceRefs"), f"attempt.assertionEvaluations[{index}].evidenceRefs", errors)
    for field in ("evidenceRefs", "findingRefs", "infrastructureErrors"):
        _strings(obj.get(field), f"attempt.{field}", errors)
    if obj.get("completionState") != "COMPLETED" and any(item.get("status") in {"PASS", "FAIL"} for item in evaluations if isinstance(item, dict)):
        warnings.append("non-completed attempt contains substantive PASS/FAIL evaluations")
    return {"kind": "review-attempt", "valid": not errors, "errors": errors, "warnings": warnings, "digest": canonical_digest(obj) if isinstance(data, dict) else None}


def validate_review_finding(data: Any) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    obj = _dict(data, "finding", errors)
    _required(obj, ["schema", "findingId", "sourceRunRef", "sourceAttemptRef", "subject", "assertionRefs", "objectRefs", "classification", "severity", "blocking", "expectedCondition", "observedCondition", "reproduction", "evidenceRefs", "scope", "probableImpact", "recommendedRoute", "fingerprint", "createdAt", "lifecycle"], "finding", errors)
    if obj.get("schema") != "bbk.review-finding.v1":
        errors.append("finding.schema must equal bbk.review-finding.v1")
    for field in ("findingId", "sourceRunRef", "sourceAttemptRef", "classification", "severity", "expectedCondition", "observedCondition", "reproduction", "scope", "probableImpact", "recommendedRoute", "createdAt"):
        _text(obj.get(field), f"finding.{field}", errors)
    subject = _dict(obj.get("subject"), "finding.subject", errors)
    _required(subject, ["ref", "digest"], "finding.subject", errors)
    if not isinstance(subject.get("digest"), str) or not re.fullmatch(r"[0-9a-f]{64}", subject.get("digest", "")):
        errors.append("finding.subject.digest must be SHA-256")
    for field in ("assertionRefs", "objectRefs", "evidenceRefs"):
        _strings(obj.get(field), f"finding.{field}", errors, nonempty=field == "assertionRefs")
    if not isinstance(obj.get("blocking"), bool):
        errors.append("finding.blocking must be boolean")
    if not isinstance(obj.get("fingerprint"), str) or not re.fullmatch(r"[0-9a-f]{64}", obj.get("fingerprint", "")):
        errors.append("finding.fingerprint must be SHA-256")
    if obj.get("lifecycle") not in {"OPEN", "REPAIR_PROPOSED", "REVALIDATION_REQUIRED", "DISPOSITIONED", "SUPERSEDED"}:
        errors.append("finding.lifecycle is invalid")
    return {"kind": "review-finding", "valid": not errors, "errors": errors, "warnings": warnings, "digest": canonical_digest(obj) if isinstance(data, dict) else None}


def validate_finding_disposition(data: Any) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    obj = _dict(data, "disposition", errors)
    _required(obj, ["schema", "dispositionId", "findingRef", "disposition", "successorSubject", "closureEvidenceRefs", "reviewAttemptRef", "authorityRef", "residualImpact", "reopeningTriggers", "createdAt"], "disposition", errors)
    if obj.get("schema") != "bbk.finding-disposition.v1":
        errors.append("disposition.schema must equal bbk.finding-disposition.v1")
    for field in ("dispositionId", "findingRef", "residualImpact", "createdAt"):
        _text(obj.get(field), f"disposition.{field}", errors)
    if obj.get("disposition") not in DISPOSITIONS:
        errors.append("disposition.disposition is invalid")
    successor = _dict(obj.get("successorSubject"), "disposition.successorSubject", errors)
    _required(successor, ["ref", "digest"], "disposition.successorSubject", errors)
    if not isinstance(successor.get("digest"), str) or not re.fullmatch(r"[0-9a-f]{64}", successor.get("digest", "")):
        errors.append("disposition.successorSubject.digest must be SHA-256")
    evidence = _strings(obj.get("closureEvidenceRefs"), "disposition.closureEvidenceRefs", errors)
    if obj.get("disposition") in {"FIXED", "REBUTTED", "FALSE_POSITIVE", "DUPLICATE_OF", "SUPERSEDED"} and not evidence:
        errors.append("closing disposition requires closure evidence")
    if obj.get("disposition") == "ACCEPTED_RISK" and not obj.get("authorityRef"):
        errors.append("ACCEPTED_RISK requires authorityRef")
    if obj.get("disposition") != "ACCEPTED_RISK" and not obj.get("reviewAttemptRef") and not obj.get("authorityRef"):
        errors.append("disposition requires reviewing attempt or accountable authority")
    _strings(obj.get("reopeningTriggers"), "disposition.reopeningTriggers", errors)
    return {"kind": "finding-disposition", "valid": not errors, "errors": errors, "warnings": warnings, "digest": canonical_digest(obj) if isinstance(data, dict) else None, "closes": obj.get("disposition") not in {"REMAINS_OPEN", "DEFERRED"}}


def aggregate_review(manifest: dict[str, Any], context: dict[str, Any], attempts: Sequence[dict[str, Any]], findings: Sequence[dict[str, Any]], dispositions: Sequence[dict[str, Any]] = (), receipts: Sequence[dict[str, Any]] = ()) -> dict[str, Any]:
    mresult = validate_review_manifest(manifest)
    cresult = validate_review_context(context, manifest)
    errors: list[str] = []
    if not mresult["valid"]:
        errors.extend(mresult["errors"])
    if not cresult["valid"]:
        errors.extend(cresult["errors"])
    attempt_results = [validate_review_attempt(value) for value in attempts]
    receipt_results = [validate_evidence_receipt(value) for value in receipts]
    finding_results = [validate_review_finding(value) for value in findings]
    disposition_results = [validate_finding_disposition(value) for value in dispositions]
    for result in [*attempt_results, *receipt_results, *finding_results, *disposition_results]:
        errors.extend(result["errors"])

    # EvidenceReceipt states what was run or observed; it does not automatically
    # satisfy an assertion.  The aggregate enforces the exact-subject, freshness,
    # completion, and trust requirements for deterministic evidence named by the
    # ReviewManifest.  This keeps a prose "tests passed" observation, a stale
    # receipt, or a receipt from another candidate from creating a passing gate.
    receipt_by_id: dict[str, dict[str, Any]] = {
        str(value.get("receiptId")): value
        for value in receipts
        if isinstance(value, dict) and value.get("receiptId")
    }
    subject = manifest.get("subject") if isinstance(manifest.get("subject"), dict) else {}
    subject_ref = subject.get("ref")
    subject_digest = subject.get("digest")
    deterministic_trust = {
        "DETERMINISTIC_LOCAL",
        "QUALIFIED_TOOL",
        "QUALIFIED_EXTERNAL_CHECK",
        "SIMULATOR_OR_HARNESS",
    }
    evidence_blockers: list[str] = []
    evidence_stale: list[str] = []
    required_evidence_status: dict[str, str] = {}
    cross_shard_status: dict[str, str] = {}

    def receipt_eligible(receipt: dict[str, Any], assertion_ref: str, *, deterministic: bool) -> tuple[bool, str | None]:
        receipt_subject = receipt.get("subject") if isinstance(receipt.get("subject"), dict) else {}
        if receipt_subject.get("ref") != subject_ref or receipt_subject.get("digest") != subject_digest:
            return False, "wrong-subject"
        freshness = receipt.get("freshness") if isinstance(receipt.get("freshness"), dict) else {}
        if freshness.get("stale") is True:
            return False, "stale"
        if receipt.get("completionStatus") != "PASS":
            return False, "not-pass"
        if assertion_ref not in (receipt.get("assertionRefs") or []):
            return False, "assertion-not-covered"
        if deterministic and receipt.get("trustClass") not in deterministic_trust:
            return False, "insufficient-trust"
        return True, None

    for obligation in manifest.get("requiredDeterministicEvidence", []) or []:
        if not isinstance(obligation, dict) or not obligation.get("required", True):
            continue
        for assertion_ref in obligation.get("assertionRefs", []) or []:
            candidates = [value for value in receipts if isinstance(value, dict) and assertion_ref in (value.get("assertionRefs") or [])]
            reasons: list[str] = []
            eligible = False
            for receipt in candidates:
                ok, reason = receipt_eligible(receipt, assertion_ref, deterministic=True)
                if ok:
                    eligible = True
                    break
                if reason:
                    reasons.append(f"{receipt.get('receiptId')}: {reason}")
            if eligible:
                required_evidence_status[assertion_ref] = "PASS"
                continue
            if any(reason.endswith("wrong-subject") or reason.endswith("stale") for reason in reasons):
                required_evidence_status[assertion_ref] = "STALE"
                evidence_stale.append(f"required deterministic evidence for {assertion_ref} is stale or bound to another subject ({'; '.join(reasons)})")
            else:
                required_evidence_status[assertion_ref] = "INCONCLUSIVE"
                detail = "; ".join(reasons) if reasons else "no matching receipt"
                evidence_blockers.append(f"required deterministic evidence for {assertion_ref} is unavailable or insufficient ({detail})")

    for assertion_ref in manifest.get("shardPlan", {}).get("crossShardAssertionRefs", []) or []:
        matching = [
            attempt
            for attempt in attempts
            if isinstance(attempt, dict)
            and attempt.get("lens") == "cross-shard-integration"
            and assertion_ref in (attempt.get("assertionRefs") or [])
            and attempt.get("completionState") == "COMPLETED"
        ]
        if matching:
            cross_shard_status[assertion_ref] = "PASS"
        else:
            cross_shard_status[assertion_ref] = "INCONCLUSIVE"
            evidence_blockers.append(f"cross-shard assertion {assertion_ref} lacks a completed cross-shard-integration attempt")
    disposition_by_finding: dict[str, list[dict[str, Any]]] = {}
    for value in dispositions:
        if isinstance(value, dict):
            disposition_by_finding.setdefault(str(value.get("findingRef")), []).append(value)
    open_findings: list[dict[str, Any]] = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        history = disposition_by_finding.get(str(finding.get("findingId")), [])
        latest = history[-1] if history else None
        if latest is None or latest.get("disposition") in {"REMAINS_OPEN", "DEFERRED"}:
            open_findings.append(finding)
    required = set(manifest.get("requiredAssertionRefs") or [])
    evaluations: dict[str, list[dict[str, Any]]] = {ref: [] for ref in required}
    infrastructure_states: list[str] = []
    for attempt in attempts:
        if not isinstance(attempt, dict):
            continue
        state = attempt.get("completionState")
        if state != "COMPLETED":
            infrastructure_states.append(str(state))
        for evaluation in attempt.get("assertionEvaluations", []) or []:
            if isinstance(evaluation, dict) and evaluation.get("assertionRef") in evaluations:
                evaluations[evaluation["assertionRef"]].append(evaluation)
    assertion_results: list[dict[str, Any]] = []
    for ref in sorted(required):
        values = evaluations.get(ref, [])
        statuses = [value.get("status") for value in values]
        if "FAIL" in statuses:
            status = "FAIL"
        elif "BLOCKED" in statuses:
            status = "BLOCKED"
        elif "ERROR" in statuses:
            status = "ERROR"
        elif "INCONCLUSIVE" in statuses:
            status = "INCONCLUSIVE"
        elif "PASS" in statuses:
            status = "PASS"
        elif "NOT_APPLICABLE" in statuses and statuses:
            status = "NOT_APPLICABLE"
        else:
            status = "NOT_RUN"
        evidence_override = required_evidence_status.get(ref)
        if evidence_override in {"INCONCLUSIVE", "STALE"} and status == "PASS":
            status = evidence_override
        cross_override = cross_shard_status.get(ref)
        if cross_override == "INCONCLUSIVE" and status == "PASS":
            status = "INCONCLUSIVE"
        assertion_results.append({"assertionRef": ref, "status": status, "attemptRefs": [attempt.get("attemptId") for attempt in attempts if isinstance(attempt, dict) and any(isinstance(ev, dict) and ev.get("assertionRef") == ref for ev in attempt.get("assertionEvaluations", []) or [])]})
    if errors:
        result = "ERROR"
        blockers = errors
    elif context.get("completeness") == "BLOCKED_REQUIRED_CONTEXT_MISSING":
        result = "BLOCKED_INSUFFICIENT_CONTEXT"
        blockers = list(context.get("blockers") or [])
    elif evidence_stale:
        result = "STALE"
        blockers = evidence_stale
    elif any(state == "BLOCKED_ENVIRONMENT" for state in infrastructure_states):
        result = "BLOCKED_ENVIRONMENT"
        blockers = ["required review environment unavailable"]
    elif any(state in {"ERROR", "STALE"} for state in infrastructure_states):
        result = "ERROR" if "ERROR" in infrastructure_states else "STALE"
        blockers = [f"attempt infrastructure state: {state}" for state in infrastructure_states]
    elif any(item["status"] == "FAIL" for item in assertion_results) or any(item.get("blocking") for item in open_findings):
        result = "NEEDS_REVISION"
        blockers = [f"assertion {item['assertionRef']} failed" for item in assertion_results if item["status"] == "FAIL"] + [f"open blocking finding {item.get('findingId')}" for item in open_findings if item.get("blocking")]
    elif any(item["status"] in {"BLOCKED", "ERROR", "INCONCLUSIVE", "NOT_RUN", "STALE"} for item in assertion_results):
        result = "INCONCLUSIVE"
        blockers = evidence_blockers + [f"assertion {item['assertionRef']} is {item['status']}" for item in assertion_results if item["status"] in {"BLOCKED", "ERROR", "INCONCLUSIVE", "NOT_RUN", "STALE"}]
    elif open_findings:
        result = "PASS_ADVISORY" if manifest.get("aggregationPolicy", {}).get("allowPassAdvisory") else "NEEDS_REVISION"
        blockers = [] if result == "PASS_ADVISORY" else [f"open finding {item.get('findingId')}" for item in open_findings]
    else:
        result = "PASS"
        blockers = []
    return {
        "schema": "bbk.review-aggregate.v1",
        "aggregateId": f"RA-{canonical_digest([manifest, context, list(attempts), list(findings), list(dispositions), list(receipts)])[:16].upper()}",
        "reviewManifestRef": manifest.get("manifestId"),
        "subject": manifest.get("subject"),
        "result": result,
        "assertionResults": assertion_results,
        "openFindingRefs": [item.get("findingId") for item in open_findings],
        "contextCompleteness": context.get("completeness"),
        "infrastructureStates": infrastructure_states,
        "blockers": blockers,
        "advisories": [f"open advisory finding {item.get('findingId')}" for item in open_findings if not item.get("blocking")],
        "nonAveraging": True,
        "calculationDigest": canonical_digest({"manifest": canonical_digest(manifest), "context": canonical_digest(context), "attempts": [canonical_digest(x) for x in attempts], "findings": [canonical_digest(x) for x in findings], "dispositions": [canonical_digest(x) for x in dispositions], "receipts": [canonical_digest(x) for x in receipts]}),
        "authorityDisclaimer": "This aggregate is a BBK workflow result only; it grants no official Blueprint authority.",
    }


def validate_review_aggregate(data: Any) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    obj = _dict(data, "aggregate", errors)
    _required(obj, ["schema", "aggregateId", "reviewManifestRef", "subject", "result", "assertionResults", "openFindingRefs", "contextCompleteness", "infrastructureStates", "blockers", "advisories", "nonAveraging", "calculationDigest", "authorityDisclaimer"], "aggregate", errors)
    if obj.get("schema") != "bbk.review-aggregate.v1":
        errors.append("aggregate.schema must equal bbk.review-aggregate.v1")
    for field in ("aggregateId", "reviewManifestRef", "authorityDisclaimer"):
        _text(obj.get(field), f"aggregate.{field}", errors)
    if obj.get("result") not in AGGREGATES:
        errors.append("aggregate.result is invalid")
    _dict(obj.get("subject"), "aggregate.subject", errors)
    for field in ("assertionResults", "openFindingRefs", "infrastructureStates", "blockers", "advisories"):
        _list(obj.get(field), f"aggregate.{field}", errors)
    if obj.get("contextCompleteness") not in COMPLETENESS:
        errors.append("aggregate.contextCompleteness is invalid")
    if obj.get("nonAveraging") is not True:
        errors.append("aggregate.nonAveraging must be true")
    if not isinstance(obj.get("calculationDigest"), str) or not re.fullmatch(r"[0-9a-f]{64}", obj.get("calculationDigest", "")):
        errors.append("aggregate.calculationDigest must be SHA-256")
    return {"kind": "review-aggregate", "valid": not errors, "errors": errors, "warnings": warnings, "digest": canonical_digest(obj) if isinstance(data, dict) else None}


def build_review_run(manifest: dict[str, Any], context: dict[str, Any], *, run_id: str, attempts: Sequence[dict[str, Any]], receipts: Sequence[dict[str, Any]], findings: Sequence[dict[str, Any]], dispositions: Sequence[dict[str, Any]], predecessor_refs: Sequence[str] = ()) -> dict[str, Any]:
    aggregate = aggregate_review(manifest, context, attempts, findings, dispositions, receipts)
    run = {
        "schema": "bbk.review-run.v1",
        "runId": run_id,
        "reviewManifest": {"ref": manifest["manifestId"], "digest": canonical_digest(manifest)},
        "reviewContextManifest": {"ref": context["contextManifestId"], "digest": canonical_digest(context)},
        "subject": manifest["subject"],
        "assuranceContract": manifest["assuranceContract"],
        "predecessorRefs": list(predecessor_refs),
        "attempts": list(attempts),
        "evidenceReceipts": list(receipts),
        "findings": list(findings),
        "findingDispositions": list(dispositions),
        "aggregate": aggregate,
        "environment": {"host": os.uname().nodename if hasattr(os, "uname") else "unknown", "bbk": BBK_VERSION},
        "startedAt": min([str(item.get("startedAt")) for item in attempts if isinstance(item, dict) and item.get("startedAt")] or ["unknown"]),
        "completedAt": max([str(item.get("completedAt")) for item in attempts if isinstance(item, dict) and item.get("completedAt")] or ["unknown"]),
        "state": "completed" if aggregate["result"] not in {"STALE", "CANCELLED"} else aggregate["result"].casefold(),
    }
    run["contentDigest"] = canonical_digest(run)
    return run


def validate_review_run(data: Any, manifest: dict[str, Any] | None = None, context: dict[str, Any] | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    obj = _dict(data, "run", errors)
    _required(obj, ["schema", "runId", "reviewManifest", "reviewContextManifest", "subject", "assuranceContract", "predecessorRefs", "attempts", "evidenceReceipts", "findings", "findingDispositions", "aggregate", "environment", "startedAt", "completedAt", "state", "contentDigest"], "run", errors)
    if obj.get("schema") != "bbk.review-run.v1":
        errors.append("run.schema must equal bbk.review-run.v1")
    _text(obj.get("runId"), "run.runId", errors)
    for field in ("reviewManifest", "reviewContextManifest", "subject", "assuranceContract", "environment"):
        _dict(obj.get(field), f"run.{field}", errors)
    for field in ("predecessorRefs", "attempts", "evidenceReceipts", "findings", "findingDispositions"):
        _list(obj.get(field), f"run.{field}", errors)
    aggregate_result = validate_review_aggregate(obj.get("aggregate"))
    errors.extend(aggregate_result["errors"])
    for value in obj.get("attempts", []) or []:
        errors.extend(validate_review_attempt(value)["errors"])
    for value in obj.get("evidenceReceipts", []) or []:
        errors.extend(validate_evidence_receipt(value)["errors"])
    for value in obj.get("findings", []) or []:
        errors.extend(validate_review_finding(value)["errors"])
    for value in obj.get("findingDispositions", []) or []:
        errors.extend(validate_finding_disposition(value)["errors"])
    supplied = obj.get("contentDigest")
    without = dict(obj)
    without.pop("contentDigest", None)
    calculated = canonical_digest(without)
    if supplied != calculated:
        errors.append("run.contentDigest does not match run content")
    if manifest is not None and obj.get("reviewManifest", {}).get("digest") != canonical_digest(manifest):
        errors.append("run ReviewManifest digest mismatch")
    if context is not None and obj.get("reviewContextManifest", {}).get("digest") != canonical_digest(context):
        errors.append("run ReviewContextManifest digest mismatch")
    return {"kind": "review-run", "valid": not errors, "errors": errors, "warnings": warnings, "digest": canonical_digest(obj) if isinstance(data, dict) else None, "calculatedContentDigest": calculated, "result": (obj.get("aggregate") or {}).get("result")}


def reconcile_findings(findings: Sequence[dict[str, Any]]) -> dict[str, Any]:
    proposals: list[dict[str, Any]] = []
    for index, left in enumerate(findings):
        for right in findings[index + 1 :]:
            relation = "UNRELATED"
            confidence = "low"
            rationale = "no deterministic correlation"
            if left.get("findingId") == right.get("findingId"):
                relation, confidence, rationale = "SAME_DEFECT", "high", "identical finding identity"
            elif left.get("fingerprint") and left.get("fingerprint") == right.get("fingerprint"):
                relation, confidence, rationale = "PROBABLE_DUPLICATE", "medium", "matching correlation fingerprint; confirmation required"
            elif set(left.get("assertionRefs", [])) & set(right.get("assertionRefs", [])):
                relation, confidence, rationale = "OVERLAPPING_IMPACT", "medium", "findings affect a shared assertion"
                if left.get("observedCondition") == right.get("observedCondition"):
                    relation, confidence, rationale = "SHARED_ROOT_CAUSE", "medium", "shared assertion and observed condition"
                elif left.get("expectedCondition") == right.get("expectedCondition") and left.get("observedCondition") != right.get("observedCondition"):
                    relation, confidence, rationale = "CONTRADICTORY_ASSESSMENT", "medium", "same expected condition with different observations"
            proposals.append({"leftFindingRef": left.get("findingId"), "rightFindingRef": right.get("findingId"), "relationship": relation, "confidence": confidence, "rationale": rationale, "requiresConfirmation": relation != "UNRELATED"})
    return {"schema": "bbk.finding-reconciliation.v1", "proposalId": f"FR-{canonical_digest(list(findings))[:16].upper()}", "proposals": proposals, "authorityDisclaimer": "Relationships are proposals; original findings remain immutable."}


def create_finding_disposition(finding: dict[str, Any], *, disposition: str, successor_ref: str, successor_digest: str, evidence_refs: Sequence[str], review_attempt_ref: str | None, authority_ref: str | None, residual_impact: str, reopening_triggers: Sequence[str], disposition_id: str, created_at: str) -> dict[str, Any]:
    value = {"schema": "bbk.finding-disposition.v1", "dispositionId": disposition_id, "findingRef": finding.get("findingId"), "disposition": disposition, "successorSubject": {"ref": successor_ref, "digest": successor_digest}, "closureEvidenceRefs": list(evidence_refs), "reviewAttemptRef": review_attempt_ref, "authorityRef": authority_ref, "residualImpact": residual_impact, "reopeningTriggers": list(reopening_triggers), "createdAt": created_at}
    validation = validate_finding_disposition(value)
    if not validation["valid"]:
        raise ValueError("invalid finding disposition: " + "; ".join(validation["errors"]))
    return value


def validate_learning_candidate(data: Any) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    obj = _dict(data, "learning", errors)
    _required(obj, ["schema", "candidateId", "candidateType", "proposedLesson", "applicabilityScope", "supportingEvidenceRefs", "contraryEvidenceRefs", "sourceFindingRefs", "sourceRunRefs", "sourceDispositionRefs", "causalConfidence", "uncertainty", "proposedAction", "privacyClass", "exportClass", "status"], "learning", errors)
    if obj.get("schema") != "bbk.learning-candidate.v1":
        errors.append("learning.schema must equal bbk.learning-candidate.v1")
    for field in ("candidateId", "candidateType", "proposedLesson", "applicabilityScope", "causalConfidence", "uncertainty", "proposedAction", "privacyClass", "exportClass"):
        _text(obj.get(field), f"learning.{field}", errors)
    for field in ("supportingEvidenceRefs", "contraryEvidenceRefs", "sourceFindingRefs", "sourceRunRefs", "sourceDispositionRefs"):
        _strings(obj.get(field), f"learning.{field}", errors)
    if obj.get("status") != "PROPOSED":
        errors.append("learning.status must remain PROPOSED until a separate method-governance decision")
    return {"kind": "learning-candidate", "valid": not errors, "errors": errors, "warnings": warnings, "digest": canonical_digest(obj) if isinstance(data, dict) else None}


def create_learning_candidate(*, candidate_id: str, candidate_type: str, lesson: str, scope: str, supporting: Sequence[str], contrary: Sequence[str], findings: Sequence[str], runs: Sequence[str], dispositions: Sequence[str], confidence: str, uncertainty: str, action: str, privacy_class: str = "project-local", export_class: str = "restricted") -> dict[str, Any]:
    value = {"schema": "bbk.learning-candidate.v1", "candidateId": candidate_id, "candidateType": candidate_type, "proposedLesson": lesson, "applicabilityScope": scope, "supportingEvidenceRefs": list(supporting), "contraryEvidenceRefs": list(contrary), "sourceFindingRefs": list(findings), "sourceRunRefs": list(runs), "sourceDispositionRefs": list(dispositions), "causalConfidence": confidence, "uncertainty": uncertainty, "proposedAction": action, "privacyClass": privacy_class, "exportClass": export_class, "status": "PROPOSED"}
    result = validate_learning_candidate(value)
    if not result["valid"]:
        raise ValueError("invalid LearningCandidate: " + "; ".join(result["errors"]))
    return value


def markdown_review_manifest(data: dict[str, Any]) -> str:
    lines = [f"# Review Manifest {data.get('manifestId')}", "", f"**Purpose:** {data.get('purpose')}  ", f"**Applicability:** `{data.get('applicability')}`  ", f"**Subject:** `{data.get('subject', {}).get('ref')}` @ `{data.get('subject', {}).get('digest')}`  ", f"**Assurance:** `{data.get('assuranceContract', {}).get('ref')}`", "", "## Lens and assertion assignments", "", "| Assignment | Lens | Assertions | Method | Blocking |", "|---|---|---|---|---:|"]
    for item in data.get("lensAssignments", []):
        lines.append(f"| `{item.get('assignmentId')}` | {item.get('lens')} | {', '.join(f'`{x}`' for x in item.get('primaryAssertionRefs', []))} | {item.get('method')} | {item.get('blocking')} |")
    lines += ["", "## Context policy", "", f"- Required kinds: {', '.join(data.get('contextPolicy', {}).get('requiredKinds', [])) or '—'}", f"- Required paths: {', '.join(data.get('contextPolicy', {}).get('requiredPaths', [])) or '—'}", f"- Redaction class: `{data.get('contextPolicy', {}).get('redactionClass')}`", "", "## Independence", "", str(data.get("independenceRequirements", {}).get("reason", "")), "", "## Authority boundary", "", str(data.get("authorityDisclaimer", "")), ""]
    return "\n".join(lines)


def markdown_review_run(data: dict[str, Any]) -> str:
    aggregate = data.get("aggregate", {})
    lines = [f"# Review Run {data.get('runId')}", "", f"**Result:** `{aggregate.get('result')}`  ", f"**Subject:** `{data.get('subject', {}).get('ref')}` @ `{data.get('subject', {}).get('digest')}`  ", f"**Attempts:** {len(data.get('attempts', []))}  ", f"**Receipts:** {len(data.get('evidenceReceipts', []))}  ", f"**Findings:** {len(data.get('findings', []))}", "", "## Assertion results", "", "| Assertion | Status | Attempts |", "|---|---|---|"]
    for item in aggregate.get("assertionResults", []):
        lines.append(f"| `{item.get('assertionRef')}` | `{item.get('status')}` | {', '.join(item.get('attemptRefs', [])) or '—'} |")
    lines += ["", "## Blockers", ""] + ([f"- {value}" for value in aggregate.get("blockers", [])] or ["- None"])
    lines += ["", "## Open findings", ""] + ([f"- `{value}`" for value in aggregate.get("openFindingRefs", [])] or ["- None"])
    lines += ["", "## Authority boundary", "", str(aggregate.get("authorityDisclaimer", "")), ""]
    return "\n".join(lines)
