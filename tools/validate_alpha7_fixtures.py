#!/usr/bin/env python3
"""Validate BBK alpha.7 State–Decision–Effect and Review Assurance fixtures.

The semantic checks are standard-library only. When the optional ``jsonschema``
package is installed, the script also validates the positive fixture corpus
against the bundled Draft 2020-12 schemas using a local reference registry.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import sys
from pathlib import Path
from typing import Any, Callable, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from review_assurance import (  # noqa: E402
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
from session_oracle import verify_oracle  # noqa: E402
from state_effect import (  # noqa: E402
    compare_state_effect_inventory,
    validate_slice_v2,
    validate_state_decision_effect,
    validate_structure_review_v2,
    validate_structure_v2,
    validate_transition_trace,
    validate_transition_trace_set,
)


def load(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def result(name: str, status: str, detail: Any = None) -> dict[str, Any]:
    return {"name": name, "status": status, "detail": detail}


def semantic_checks() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    positive: list[tuple[str, Callable[[Any], dict[str, Any]], str]] = [
        ("sde-contract", validate_state_decision_effect, "fixtures/state-effect/contract-order.json"),
        ("sde-none", validate_state_decision_effect, "fixtures/state-effect/stateless-none.json"),
        ("trace-happy", validate_transition_trace, "fixtures/state-effect/trace-happy.json"),
        ("trace-duplicate", validate_transition_trace, "fixtures/state-effect/trace-duplicate.json"),
        ("trace-ack-lost", validate_transition_trace, "fixtures/state-effect/trace-ack-lost.json"),
        ("structure-v2", validate_structure_v2, "fixtures/structure/software-contract-v2.json"),
        ("slice-v2", validate_slice_v2, "fixtures/slices/software-slice-v2.json"),
        ("assurance", validate_assurance_contract, "fixtures/review/assurance-consequential.json"),
        ("review-manifest", validate_review_manifest, "fixtures/review/manifest-consequential.json"),
        ("review-context-complete", validate_review_context, "fixtures/review/context-complete.json"),
        ("review-context-blocked-record", validate_review_context, "fixtures/review/context-blocked.json"),
        ("review-attempt-blind", validate_review_attempt, "fixtures/review/attempt-blind.json"),
        ("review-attempt-intent", validate_review_attempt, "fixtures/review/attempt-intent.json"),
        ("evidence-trace", validate_evidence_receipt, "fixtures/review/evidence-receipt-v2.json"),
        ("evidence-intent", validate_evidence_receipt, "fixtures/review/evidence-intent.json"),
        ("evidence-unstructured", validate_evidence_receipt, "fixtures/review/evidence-unstructured.json"),
        ("evidence-wrong-subject-record", validate_evidence_receipt, "fixtures/review/evidence-wrong-subject.json"),
        ("review-finding", validate_review_finding, "fixtures/review/finding-open.json"),
        ("finding-disposition", validate_finding_disposition, "fixtures/review/finding-disposition-fixed.json"),
        ("learning-candidate", validate_learning_candidate, "fixtures/review/learning-candidate.json"),
        ("review-run", validate_review_run, "fixtures/review/run-pass.json"),
    ]
    for name, validator, rel in positive:
        report = validator(load(rel))
        checks.append(result(name, "PASS" if report.get("valid") else "FAIL", report))

    invalid_sde = validate_state_decision_effect(load("fixtures/state-effect/invalid-authoritative-derived.json"))
    checks.append(result("invalid-authoritative-derived-rejected", "PASS" if not invalid_sde.get("valid") else "FAIL", invalid_sde))

    invalid_assurance = validate_assurance_contract(load("fixtures/review/invalid-assurance-duplicate.json"))
    checks.append(result("duplicate-assurance-assertion-rejected", "PASS" if not invalid_assurance.get("valid") else "FAIL", invalid_assurance))

    design = load("fixtures/state-effect/contract-order.json")
    traces = [
        load("fixtures/state-effect/trace-happy.json"),
        load("fixtures/state-effect/trace-duplicate.json"),
        load("fixtures/state-effect/trace-ack-lost.json"),
    ]
    trace_set = validate_transition_trace_set(traces, design=design)
    checks.append(result("trace-set", "PASS" if trace_set.get("valid") else "FAIL", trace_set))

    planned = design
    conformant = load("fixtures/state-effect/inventory-conformant.json")
    divergent = load("fixtures/state-effect/inventory-divergent.json")
    conformant_report = compare_state_effect_inventory(planned, conformant)
    divergent_report = compare_state_effect_inventory(planned, divergent)
    checks.append(result(
        "planned-actual-conformance",
        "PASS" if conformant_report.get("disposition") in {"accept", "accept-with-advisories"} else "FAIL",
        conformant_report,
    ))
    checks.append(result(
        "planned-actual-material-divergence",
        "PASS" if divergent_report.get("disposition") == "revise" else "FAIL",
        divergent_report,
    ))

    review_report = validate_structure_review_v2(conformant_report)
    checks.append(result("structure-review-v2", "PASS" if review_report.get("valid") else "FAIL", review_report))

    from review_assurance import aggregate_review
    manifest = load("fixtures/review/manifest-consequential.json")
    context = load("fixtures/review/context-complete.json")
    attempts = [load("fixtures/review/attempt-blind.json"), load("fixtures/review/attempt-intent.json")]
    intent_receipt = load("fixtures/review/evidence-intent.json")
    weak_aggregate = aggregate_review(
        manifest,
        context,
        attempts,
        [],
        receipts=[load("fixtures/review/evidence-unstructured.json"), intent_receipt],
    )
    checks.append(result("unstructured-required-evidence-blocked", "PASS" if weak_aggregate.get("result") == "INCONCLUSIVE" else "FAIL", weak_aggregate))
    stale_aggregate = aggregate_review(
        manifest,
        context,
        attempts,
        [],
        receipts=[load("fixtures/review/evidence-wrong-subject.json"), intent_receipt],
    )
    checks.append(result("wrong-subject-required-evidence-stale", "PASS" if stale_aggregate.get("result") == "STALE" else "FAIL", stale_aggregate))

    session_oracle_report = verify_oracle(
        load("fixtures/session-inspector-alpha16/source-session-oracle.json"),
        load("fixtures/session-inspector-alpha16/derived-analysis-contradictions.json"),
    )
    checks.append(result(
        "session-inspector-alpha16-oracle",
        "PASS" if session_oracle_report.get("status") == "PASS" else "FAIL",
        session_oracle_report,
    ))

    return checks


def schema_checks() -> tuple[list[dict[str, Any]], str | None]:
    try:
        from jsonschema import Draft202012Validator
        from referencing import Registry, Resource
    except ImportError:
        return [result("json-schema-validation", "SKIPPED_OPTIONAL", "jsonschema/referencing not installed")], None

    version = importlib.metadata.version("jsonschema")
    schema_dir = ROOT / "spec" / "schemas"
    schemas: dict[str, Any] = {}
    resources: list[tuple[str, Resource[Any]]] = []
    checks: list[dict[str, Any]] = []
    for path in sorted(schema_dir.glob("*.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as exc:  # pragma: no cover - qualification failure path
            checks.append(result(f"schema:{path.name}", "FAIL", str(exc)))
            continue
        schemas[path.name] = schema
        resource = Resource.from_contents(schema)
        resources.append((schema.get("$id", path.name), resource))
        resources.append((path.name, resource))
        checks.append(result(f"schema:{path.name}", "PASS", "Draft 2020-12 schema valid"))
    registry = Registry().with_resources(resources)

    pairs = [
        ("fixtures/state-effect/contract-order.json", "bbk-state-decision-effect-design-v1.schema.json"),
        ("fixtures/state-effect/stateless-none.json", "bbk-state-decision-effect-design-v1.schema.json"),
        ("fixtures/state-effect/trace-happy.json", "bbk-state-transition-trace-v1.schema.json"),
        ("fixtures/state-effect/trace-duplicate.json", "bbk-state-transition-trace-v1.schema.json"),
        ("fixtures/state-effect/trace-ack-lost.json", "bbk-state-transition-trace-v1.schema.json"),
        ("fixtures/structure/software-contract-v2.json", "bbk-implementation-structure-contract-v2.schema.json"),
        ("fixtures/slices/software-slice-v2.json", "bbk-execution-slice-v2.schema.json"),
        ("fixtures/state-effect/inventory-conformant.json", "bbk-actual-state-effect-inventory-v1.schema.json"),
        ("fixtures/review/assurance-consequential.json", "bbk-assurance-contract-v1.schema.json"),
        ("fixtures/review/manifest-consequential.json", "bbk-review-manifest-v1.schema.json"),
        ("fixtures/review/context-complete.json", "bbk-review-context-manifest-v1.schema.json"),
        ("fixtures/review/attempt-blind.json", "bbk-review-attempt-v1.schema.json"),
        ("fixtures/review/evidence-receipt-v2.json", "bbk-evidence-receipt-v2.schema.json"),
        ("fixtures/review/evidence-unstructured.json", "bbk-evidence-receipt-v2.schema.json"),
        ("fixtures/review/evidence-wrong-subject.json", "bbk-evidence-receipt-v2.schema.json"),
        ("fixtures/review/finding-open.json", "bbk-review-finding-v1.schema.json"),
        ("fixtures/review/finding-disposition-fixed.json", "bbk-finding-disposition-v1.schema.json"),
        ("fixtures/review/learning-candidate.json", "bbk-learning-candidate-v1.schema.json"),
        ("fixtures/review/run-pass.json", "bbk-review-run-v1.schema.json"),
        (
            "fixtures/session-inspector-alpha16/source-session-oracle.json",
            "bbk-session-inspector-oracle-manifest-v1.schema.json",
        ),
        (
            "fixtures/session-inspector-alpha16/derived-analysis-contradictions.json",
            "bbk-session-inspector-contradictions-v1.schema.json",
        ),
    ]
    for data_rel, schema_name in pairs:
        data = load(data_rel)
        validator = Draft202012Validator(schemas[schema_name], registry=registry)
        errors = sorted(validator.iter_errors(data), key=lambda item: list(item.absolute_path))
        if errors:
            detail = [
                {"path": list(error.absolute_path), "message": error.message}
                for error in errors
            ]
            checks.append(result(f"fixture-schema:{data_rel}", "FAIL", detail))
        else:
            checks.append(result(f"fixture-schema:{data_rel}", "PASS", schema_name))
    return checks, version


def validate() -> dict[str, Any]:
    semantic = semantic_checks()
    schemas, schema_version = schema_checks()
    checks = semantic + schemas
    failures = [item for item in checks if item["status"] == "FAIL"]
    return {
        "schema": "bbk.alpha7-fixture-validation.v1",
        "bbkVersion": (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
        "status": "PASS" if not failures else "FAIL",
        "semanticCheckCount": len(semantic),
        "schemaCheckCount": len(schemas),
        "jsonschemaVersion": schema_version,
        "failures": failures,
        "checks": checks,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    report = validate()
    rendered = json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    if args.json:
        print(rendered, end="")
    else:
        print(f"BBK alpha.7 fixture validation: {report['status']}")
        print(f"Semantic checks: {report['semanticCheckCount']}")
        print(f"Schema checks: {report['schemaCheckCount']}")
        if report.get("jsonschemaVersion"):
            print(f"jsonschema: {report['jsonschemaVersion']}")
        for failure in report["failures"]:
            print(f"- {failure['name']}: {failure['detail']}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
