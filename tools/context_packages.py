#!/usr/bin/env python3
"""Compile standard BBK Worker and review contexts into sealed packages.

The compiler is mechanical. It refuses incomplete semantic inputs with
SPECIALIST_DESIGN_REQUIRED rather than inventing authority, acceptance
criteria, review scope, or parent decisions.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from strict_json import load_path
    from contracts import validate_work_unit
    from artifact_packages import (
        ArtifactPackageError, canonical_json_bytes, seal_draft, verify_package,
        validate_schema_instance,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from strict_json import load_path
    from contracts import validate_work_unit
    from artifact_packages import (
        ArtifactPackageError, canonical_json_bytes, seal_draft, verify_package,
        validate_schema_instance,
    )

AUTHORITY_BOUNDARY = (
    "This generated context preserves supplied semantics and exact sealed inputs. "
    "It does not create authority, acceptance criteria, independent review, finding closure, or release authority."
)
SAFE_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
GOVERNING_REF_FIELDS = (
    "supportedOutcomeRefs", "solutionOutcomeFitRefs",
    "implementationStructureContractRefs", "keyContractRefs",
    "executionSliceIds", "stateDecisionEffectRefs", "stateTransitionTraceRefs",
    "assuranceContractRefs", "reviewManifestRefs",
)
STANDARD_WORK_UNIT_FIELDS = (
    "id", "purpose", "scope", "taskProfile", "assuranceTier", "role",
    "expectedBehavior", "verificationPlan", "authorityGrant", "capabilityZones",
    "toolEnvironment", "returnContract", "payloadLimits", "interruptPolicy",
    "executionBudget",
)


class ContextPackageError(RuntimeError):
    pass


def _safe_id(value: str, label: str) -> str:
    if not value or len(value) > 128 or value[0] not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" or any(ch not in SAFE_CHARS for ch in value):
        raise ContextPackageError(f"{label} must be a safe BBK identifier")
    return value


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))


def _specialist(kind: str, missing: Sequence[str], findings: Sequence[str] = ()) -> dict[str, Any]:
    exact = sorted(dict.fromkeys([*missing, *findings]))
    return {
        "schema": "bbk.context-package-compilation.v1",
        "status": "SPECIALIST_DESIGN_REQUIRED",
        "packageKind": kind,
        "missingOrAmbiguousSemantics": exact,
        "outputRoot": None,
        "smallestNextAction": "Route the exact missing semantic fields to bbk_worker_designer or the owning planning role; do not infer them in the compiler.",
        "claimsNotEstablished": ["complete invocation semantics", "execution authorization", "review readiness"],
    }


def _validate_profile_lock(value: Any) -> list[str]:
    if not isinstance(value, dict) or value.get("schema") != "bbk.profile-lock.v1":
        return ["profile_lock.schema must equal bbk.profile-lock.v1"]
    modern = all(value.get(name) not in (None, "") for name in ("bbkVersion", "profileId", "profileVersion", "profileRootDigest", "effectiveDigest", "inputs"))
    legacy = all(name in value for name in ("generated_at", "profiles", "effective_sha256"))
    errors = [] if modern or legacy else ["profile_lock is missing its complete modern or legacy identity fields"]
    if not errors:
        errors.extend(_schema_messages(value, "bbk.profile-lock.v1", "profile_lock"))
    return errors


def _validate_host_preflight(value: Any) -> list[str]:
    if not isinstance(value, dict) or value.get("schema") != "bbk.host-preflight-result.v1":
        return ["host_preflight.schema must equal bbk.host-preflight-result.v1"]
    required = ("host", "requirementsDigest", "observations", "cache", "authorityBoundary")
    errors = [f"host_preflight.{name} is missing" for name in required if name not in value]
    if not errors:
        errors.extend(_schema_messages(value, "bbk.host-preflight-result.v1", "host_preflight"))
    host = value.get("host") if isinstance(value.get("host"), dict) else None
    if host:
        observed = {key: item for key, item in host.items() if key != "digest"}
        if host.get("digest") != _digest(observed):
            errors.append("host_preflight.host.digest does not match the exact host identity fields")
    return errors


def _schema_messages(value: Any, schema: str, label: str) -> list[str]:
    return [
        f"{label}{item.get('pointer') or ''}: {item.get('message', item.get('code', 'schema validation failed'))}"
        for item in validate_schema_instance(value, schema)
    ]


def _prototype_required(work_unit: Mapping[str, Any]) -> bool:
    text = " ".join(str(work_unit.get(name, "")) for name in ("taskProfile", "role", "purpose")).lower()
    return "prototype" in text or work_unit.get("role") == "prototyper"


def compile_worker_context(
    work_unit: Mapping[str, Any], profile_lock: Mapping[str, Any], host_preflight: Mapping[str, Any],
    *, output_root: Path, package_id: str | None = None, revision: str = "1",
    prototype_charter: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    validation = validate_work_unit(work_unit)
    normalized = validation.get("normalized") if isinstance(validation.get("normalized"), dict) else {}
    missing: list[str] = [f"work_unit validation: {item}" for item in validation.get("errors", [])]
    for field in STANDARD_WORK_UNIT_FIELDS:
        value = normalized.get(field)
        if value is None or value == "" or value == []:
            missing.append(f"work_unit.{field}")
    governing = {field: normalized.get(field) for field in GOVERNING_REF_FIELDS if normalized.get(field)}
    if not governing:
        missing.append("work_unit governing references")
    missing.extend(_validate_profile_lock(profile_lock))
    missing.extend(_validate_host_preflight(host_preflight))
    if _prototype_required(normalized):
        if not isinstance(prototype_charter, dict) or prototype_charter.get("schema") != "bbk.prototype-charter.v2":
            missing.append("prototype_charter.v2 for prototype work")
        else:
            missing.extend(_schema_messages(prototype_charter, "bbk.prototype-charter.v2", "prototype_charter"))
    if missing:
        return _specialist("WORKER_CONTEXT", missing)

    work_unit_id = _safe_id(str(normalized["id"]), "work unit id")
    package_id = _safe_id(package_id or f"WC-{work_unit_id}", "package id")
    output_root = output_root.expanduser().absolute()
    output_root.parent.mkdir(parents=True, exist_ok=True)
    blockers = [
        {"capabilityId": item.get("id"), "status": item.get("status"), "kind": item.get("kind")}
        for item in host_preflight.get("observations", [])
        if isinstance(item, dict) and item.get("required", True) and item.get("status") != "AVAILABLE"
    ]
    subject = {"kind": "work-unit", "id": work_unit_id, "revision": normalized.get("revision")}
    context = {
        "schema": "bbk.worker-context-package.v1",
        "id": package_id,
        "subject": subject,
        "compiledFrom": {"workUnitId": work_unit_id, "workUnitDigest": validation.get("digest") or _digest(work_unit)},
        "workUnit": work_unit,
        "governingReferences": governing,
        "authority": normalized["authorityGrant"],
        "capabilityZones": normalized["capabilityZones"],
        "profileLock": profile_lock,
        "hostPreflight": host_preflight,
        "admission": {
            "status": "ELIGIBLE" if not blockers else "BLOCKED_BY_HOST_PREFLIGHT",
            "blockers": blockers,
            "liveConfirmationItems": [item.get("id") for item in host_preflight.get("observations", []) if isinstance(item, dict) and item.get("status") == "REQUIRES_LIVE_PROBE"],
        },
        "tools": normalized["toolEnvironment"],
        "outputs": {"plannedArtifactRefs": normalized.get("plannedArtifactRefs", []), "returnContract": normalized["returnContract"]},
        "checks": normalized["verificationPlan"],
        "cleanup": {"temporaryScaffolding": normalized.get("temporaryScaffolding", []), "disposition": normalized.get("scaffoldingDisposition")},
        "payloadLimits": normalized["payloadLimits"],
        "interruptPolicy": normalized["interruptPolicy"],
        "executionBudget": normalized["executionBudget"],
        "prototypeCharter": prototype_charter,
        "authorityBoundary": AUTHORITY_BOUNDARY,
        "smallestValidNextAction": "Resolve required host blockers before mutation." if blockers else "Admit the exact Worker attempt under the supplied authority and package identity.",
    }
    with tempfile.TemporaryDirectory(prefix="bbk-worker-context-", dir=str(output_root.parent)) as raw:
        draft = Path(raw)
        _write_json(draft / "worker-context.json", context)
        _write_json(draft / "sources" / "work-unit.json", work_unit)
        _write_json(draft / "sources" / "profile-lock.json", profile_lock)
        _write_json(draft / "sources" / "host-preflight.json", host_preflight)
        artifacts = [
            {"artifactId": "worker-context", "path": "worker-context.json", "schema": "bbk.worker-context-package.v1", "role": "context", "references": ["work-unit", "profile-lock", "host-preflight"]},
            {"artifactId": "work-unit", "path": "sources/work-unit.json", "role": "source", "references": []},
            {"artifactId": "profile-lock", "path": "sources/profile-lock.json", "role": "source", "references": []},
            {"artifactId": "host-preflight", "path": "sources/host-preflight.json", "role": "evidence", "references": []},
        ]
        if prototype_charter is not None:
            _write_json(draft / "sources" / "prototype-charter.json", prototype_charter)
            artifacts.append({"artifactId": "prototype-charter", "path": "sources/prototype-charter.json", "schema": "bbk.prototype-charter.v2", "role": "context", "references": []})
            artifacts[0]["references"].append("prototype-charter")
        _write_json(draft / "bbk-package-draft.json", {
            "schema": "bbk.artifact-package-draft.v1", "packageId": package_id, "revision": revision,
            "profile": {"id": "worker-context-v1", "version": "1"}, "subject": subject,
            "predecessor": None, "artifacts": artifacts,
            "metadata": {"compiler": "tools/context_packages.py", "authorityBoundary": AUTHORITY_BOUNDARY},
        })
        sealed = seal_draft(draft, output_root)
    return {
        "schema": "bbk.context-package-compilation.v1", "status": "COMPILED",
        "packageKind": "WORKER_CONTEXT", "admissionStatus": context["admission"]["status"],
        "outputRoot": str(output_root), "packageId": package_id, "contentSha256": sealed["contentSha256"],
        "verification": sealed["verification"], "smallestNextAction": context["smallestValidNextAction"],
        "claimsNotEstablished": sealed["claims_not_established"],
    }


def _verified_candidate(candidate_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    verification = verify_package(candidate_root)
    if verification.get("status") != "PASS":
        raise ContextPackageError("candidate package verification failed")
    package = load_path(candidate_root / "bbk-package.json")
    if not isinstance(package, dict):
        raise ContextPackageError("candidate package control record is invalid")
    profile = package.get("profile") if isinstance(package.get("profile"), dict) else {}
    if profile.get("id") != "candidate-package-v1":
        raise ContextPackageError("review compilation requires a sealed candidate-package-v1 package")
    return package, verification


def compile_review_package(
    candidate_root: Path, request: Mapping[str, Any], *, output_root: Path,
    package_id: str | None = None, revision: str = "1",
) -> dict[str, Any]:
    candidate_root = candidate_root.expanduser().resolve(strict=True)
    candidate, candidate_verification = _verified_candidate(candidate_root)
    mode = request.get("mode", "REVIEW") if isinstance(request, dict) else None
    missing: list[str] = []
    if not isinstance(request, dict) or request.get("schema") != "bbk.review-package-request.v1":
        missing.append("request.schema bbk.review-package-request.v1")
    else:
        missing.extend(_schema_messages(request, "bbk.review-package-request.v1", "request"))
    if mode not in {"REVIEW", "FOCUSED_RECHECK"}:
        missing.append("request.mode REVIEW or FOCUSED_RECHECK")
    assurance = request.get("assuranceMode") if isinstance(request, dict) else None
    if not isinstance(assurance, dict) or assurance.get("schema") != "bbk.assurance-mode.v1":
        missing.append("request.assuranceMode bbk.assurance-mode.v1")
    if mode == "REVIEW":
        if not request.get("exactFocus"):
            missing.append("request.exactFocus")
        if not isinstance(request.get("applicableFloors"), list):
            missing.append("request.applicableFloors")
        if not isinstance(request.get("priorFindings", []), list):
            missing.append("request.priorFindings")
    if mode == "FOCUSED_RECHECK":
        for field in ("finding", "affectedScope", "relevantEvidence", "reopeningTriggers"):
            value = request.get(field)
            if value is None or value == "" or value == []:
                missing.append(f"request.{field}")
        if not isinstance(request.get("semanticChange", False), bool):
            missing.append("request.semanticChange boolean")
        if request.get("semanticChange") is False and request.get("broaderReviewContext"):
            missing.append("request.broaderReviewContext is forbidden without semanticChange")
    if missing:
        return _specialist("REVIEW_CONTEXT", missing)

    candidate_binding = {
        "packageId": candidate["packageId"], "revision": candidate["revision"],
        "contentSha256": candidate["contentSha256"], "subject": candidate["subject"],
    }
    package_id = _safe_id(package_id or f"RP-{candidate['packageId']}-{mode.lower()}", "package id")
    semantic: dict[str, Any] = {
        "schema": "bbk.review-package.v2", "id": package_id, "mode": mode,
        "candidate": candidate_binding, "assuranceMode": assurance,
        "exactFocus": request.get("exactFocus") or {"findingId": (request.get("finding") or {}).get("id")},
        "applicableFloors": request.get("applicableFloors", []),
        "priorFindings": request.get("priorFindings", []),
        "relevantEvidence": request.get("relevantEvidence", []),
        "reviewerOutputContract": {
            "produce": ["findings", "finding deltas", "evidence limitations", "recommended dispositions"],
            "prohibited": ["rewritten plan", "candidate mutation", "finding closure", "release authorization"],
        },
        "authorityBoundary": AUTHORITY_BOUNDARY,
    }
    if mode == "FOCUSED_RECHECK":
        semantic["recheck"] = {
            "finding": request["finding"], "successorCandidate": candidate_binding,
            "affectedScope": request["affectedScope"], "relevantEvidence": request["relevantEvidence"],
            "reopeningTriggers": request["reopeningTriggers"], "semanticChange": request.get("semanticChange", False),
            **({"broaderReviewContext": request["broaderReviewContext"]} if request.get("semanticChange") and request.get("broaderReviewContext") else {}),
        }
    output_root = output_root.expanduser().absolute()
    output_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="bbk-review-context-", dir=str(output_root.parent)) as raw:
        draft = Path(raw)
        _write_json(draft / "review-package.json", semantic)
        (draft / "candidate").mkdir(parents=True, exist_ok=True)
        for name in ("bbk-package.json", "bbk-package-manifest.json", "bbk-seal-receipt.json"):
            shutil.copy2(candidate_root / name, draft / "candidate" / name)
        _write_json(draft / "sources" / "review-request.json", request)
        artifacts = [
            {"artifactId": "review-package", "path": "review-package.json", "schema": "bbk.review-package.v2", "role": "context", "references": ["candidate-package", "candidate-manifest", "candidate-receipt", "review-request"]},
            {"artifactId": "candidate-package", "path": "candidate/bbk-package.json", "schema": "bbk.artifact-package.v1", "role": "candidate", "references": []},
            {"artifactId": "candidate-manifest", "path": "candidate/bbk-package-manifest.json", "schema": "bbk.artifact-package-manifest.v1", "role": "candidate", "references": []},
            {"artifactId": "candidate-receipt", "path": "candidate/bbk-seal-receipt.json", "schema": "bbk.artifact-package-seal-receipt.v1", "role": "evidence", "references": []},
            {"artifactId": "review-request", "path": "sources/review-request.json", "role": "context", "references": []},
        ]
        _write_json(draft / "bbk-package-draft.json", {
            "schema": "bbk.artifact-package-draft.v1", "packageId": package_id, "revision": revision,
            "profile": {"id": "review-package-v2", "version": "1"}, "subject": candidate["subject"],
            "predecessor": None, "artifacts": artifacts,
            "metadata": {"compiler": "tools/context_packages.py", "candidateContentSha256": candidate["contentSha256"], "authorityBoundary": AUTHORITY_BOUNDARY},
        })
        sealed = seal_draft(draft, output_root)
    return {
        "schema": "bbk.context-package-compilation.v1", "status": "COMPILED",
        "packageKind": mode, "outputRoot": str(output_root), "packageId": package_id,
        "candidateContentSha256": candidate["contentSha256"], "contentSha256": sealed["contentSha256"],
        "verification": sealed["verification"], "candidateVerification": candidate_verification,
        "smallestNextAction": "Provide the exact sealed review package to the assigned Reviewer.",
        "claimsNotEstablished": sealed["claims_not_established"],
    }


def _load(path: str | None) -> Any:
    return load_path(Path(path).expanduser()) if path else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    worker = sub.add_parser("worker")
    worker.add_argument("--work-unit", required=True); worker.add_argument("--profile-lock", required=True)
    worker.add_argument("--host-preflight", required=True); worker.add_argument("--prototype-charter")
    worker.add_argument("--output", required=True); worker.add_argument("--id"); worker.add_argument("--revision", default="1")
    review = sub.add_parser("review")
    review.add_argument("--candidate", required=True); review.add_argument("--request", required=True)
    review.add_argument("--output", required=True); review.add_argument("--id"); review.add_argument("--revision", default="1")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "worker":
            result = compile_worker_context(_load(args.work_unit), _load(args.profile_lock), _load(args.host_preflight),
                output_root=Path(args.output), package_id=args.id, revision=args.revision,
                prototype_charter=_load(args.prototype_charter))
        else:
            result = compile_review_package(Path(args.candidate), _load(args.request), output_root=Path(args.output), package_id=args.id, revision=args.revision)
    except (ContextPackageError, ArtifactPackageError, OSError, ValueError) as exc:
        diagnostic = exc.result if isinstance(exc, ArtifactPackageError) else None
        result = {"schema": "bbk.context-package-compilation.v1", "status": "REJECTED", "message": str(exc), "diagnostic": diagnostic}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    return 0 if result.get("status") == "COMPILED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
