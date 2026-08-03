#!/usr/bin/env python3
"""Validate the BBK alpha.13 role-return and execution-contract source package.

Gate 3 intentionally validates canonical sources, generated contract schemas,
and companion execution-object examples. It does not generate or verify the
complete release package, host installations, or release manifests.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from return_contracts import (
    ENVELOPE_PATH,
    REGISTRY_PATH,
    check_or_write as check_role_return_outputs,
    load_package as load_role_package,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_CATALOG = Path("spec/contracts/catalog.json")
CONTRACT_CATALOG_SCHEMA = Path("spec/schemas/bbk-contract-catalog-v1.schema.json")
CAPABILITY_INVENTORY = Path("spec/capability-status.json")
CAPABILITY_SCHEMA = Path("spec/schemas/bbk-capability-status-inventory-v1.schema.json")
ROLE_RETURN_REGISTRY_SCHEMA = Path("spec/schemas/bbk-role-return-registry-v1.schema.json")
POLICY = Path("spec/policies/local-discovery-v1.json")
POLICY_SCHEMA = Path("spec/schemas/bbk-local-discovery-policy-v1.schema.json")
BOUNDARY_TEMPLATE = Path("templates/contracts/territory-execution-boundary.json")
BOUNDARY_SCHEMA = Path("spec/schemas/bbk-territory-execution-boundary-v1.schema.json")
ENVELOPE_TEMPLATE = Path("templates/contracts/local-discovery-envelope.json")
ENVELOPE_SCHEMA = Path("spec/schemas/bbk-local-discovery-envelope-v1.schema.json")
PERMIT_TEMPLATE = Path("templates/contracts/local-discovery-permit.json")
PERMIT_SCHEMA = Path("spec/schemas/bbk-local-discovery-permit-v1.schema.json")

EXPECTED_DISPOSITIONS = [
    "COMPLETE", "PARTIAL", "BLOCKED_TECHNICAL", "BLOCKED_AUTHORITY",
    "BLOCKED_DECISION", "PAUSED_CAPACITY", "PAUSED_HOST_WINDOW",
    "CANCELLED", "INCONCLUSIVE",
]
EXPECTED_STATUS_VOCABULARY = [
    "IMPLEMENTED_DETERMINISTIC", "IMPLEMENTED_BOOTSTRAP",
    "SCHEMA_DEFINED_COMPANION", "HOST_PROVIDED_OPTIONAL", "TARGET_ONLY",
    "RETIRED_NOT_IMPLEMENTED",
]
EXPECTED_EXECUTION_CONTRACTS = {
    "bbk.territory-execution-boundary.v1": (
        "EXECUTION_BOUNDARY", "SCHEMA_DEFINED_COMPANION", "bbk_root_orchestrator"
    ),
    "bbk.local-discovery-policy.v1": (
        "POLICY", "ACTIVE_POLICY", "bbk_territory_orchestrator"
    ),
    "bbk.local-discovery-envelope.v1": (
        "AUTHORITY_ENVELOPE", "SCHEMA_DEFINED_COMPANION", "bbk_territory_orchestrator"
    ),
    "bbk.local-discovery-permit.v1": (
        "AUTHORITY_PERMIT", "SCHEMA_DEFINED_COMPANION", "bbk_territory_orchestrator"
    ),
}
EXPECTED_PROHIBITED_CHANGES = [
    "OUTCOME", "SCOPE", "REQUIREMENT", "ADR_OR_ARCHITECTURE",
    "CANONICAL_INTERFACE", "ASSERTION_MEANING_OR_OWNERSHIP",
    "PROTECTED_FLOOR", "AUTHORITY", "TERRITORY_BOUNDARY",
    "COHORT_MEANING", "TOOLCHAIN_POLICY", "VALIDATION_MEANING",
    "EXTERNAL_EFFECT_ENVELOPE",
]
EXPECTED_CAPABILITIES = {
    "RoleReturnEnvelope", "RoleSpecificReturnSchemas",
    "TerritoryExecutionBoundary", "LocalDiscoveryPolicy",
    "LocalDiscoveryEnvelope", "LocalDiscoveryPermit",
    "WorkerValidationBatch", "CandidateManifest", "GateReceipt",
    "WorkerQualityAttestation", "ExecutionAuthorization",
    "ExecutionScopeFence", "SemanticRun", "LeaseAndFencingToken",
    "RepairRecord", "ClosureTransition",
}
ACTIVE_SOURCE_SCAN = (
    Path("spec/method-content.json"),
    Path("spec/contracts/catalog.json"),
    Path("spec/policies/local-discovery-v1.json"),
    Path("templates/contracts/territory-execution-boundary.json"),
    Path("templates/contracts/local-discovery-envelope.json"),
    Path("templates/contracts/local-discovery-permit.json"),
)


class ContractPackageError(RuntimeError):
    def __init__(self, errors: Sequence[str] | str):
        self.errors = [errors] if isinstance(errors, str) else list(errors)
        super().__init__("\n".join(self.errors))


def load_json(root: Path, rel: Path) -> Any:
    return json.loads((root / rel).read_text(encoding="utf-8"))


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def add_error(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def schema_registry(root: Path, *, required: bool = True):
    """Return the optional Draft 2020-12 validator registry.

    Canonical contract generation and semantic package validation are standard-
    library operations. ``jsonschema`` is an explicitly optional BBK capability,
    so ordinary source checks must not fail merely because it is absent. Release
    qualification can still request strict schema conformance with ``required``.
    """
    try:
        import jsonschema
        from referencing import Registry, Resource
    except ImportError as exc:
        if required:
            raise ContractPackageError(f"jsonschema and referencing are required: {exc}")
        return None, None, []
    registry = Registry()
    schemas: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted((root / "spec/schemas").glob("*.schema.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        schemas.append((path, schema))
        schema_id = schema.get("$id")
        if isinstance(schema_id, str):
            registry = registry.with_resource(schema_id, Resource.from_contents(schema))
    for directory in (root / "spec/schemas/role-results", root / "spec/schemas/role-returns"):
        for path in sorted(directory.glob("*.schema.json")):
            schema = json.loads(path.read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator.check_schema(schema)
            schemas.append((path, schema))
            registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    return jsonschema, registry, schemas


def validate_instance(root: Path, instance_path: Path, schema_path: Path, registry: Any) -> None:
    import jsonschema

    schema = load_json(root, schema_path)
    instance = load_json(root, instance_path)
    jsonschema.Draft202012Validator(
        schema,
        registry=registry,
        format_checker=jsonschema.FormatChecker(),
    ).validate(instance)


def field_example(field: Mapping[str, Any]) -> Any:
    kind = field["kind"]
    if field.get("nullable"):
        # Exercise the non-null branch so every kind remains validated.
        pass
    if kind == "STRING":
        return "example"
    if kind == "STRING_LIST":
        return []
    if kind == "REFERENCE":
        return {"id": "REF-EXAMPLE"}
    if kind == "REFERENCE_LIST":
        return []
    if kind == "ARTIFACT_REFERENCE":
        return {
            "id": "ARTIFACT-EXAMPLE", "path": "artifacts/example.bin",
            "bytes": 0, "sha256": "0" * 64,
        }
    if kind == "ARTIFACT_REFERENCE_LIST":
        return []
    if kind == "STRUCTURED":
        return {"state": "EXAMPLE"}
    if kind == "STRUCTURED_LIST":
        return []
    if kind == "BOOLEAN":
        return False
    if kind == "INTEGER":
        return 0
    if kind == "NUMBER":
        return 0
    if kind == "ENUM":
        return field["enum_values"][0]
    if kind == "ENUM_LIST":
        return []
    raise ContractPackageError(f"unsupported result-field kind {kind!r}")


def representative_role_return(role: Mapping[str, Any], entry: Mapping[str, Any]) -> dict[str, Any]:
    contract = role["return_contract"]
    mode = entry["allowed_parent_modes"][0]
    parent = mode["parents"][0]
    parent_ref: dict[str, Any] = {
        "kind": mode["parent_kind"],
        "id": parent,
        "invocation_mode": mode["mode"],
    }
    parent_ref["role"] = parent if mode["parent_kind"] == "canonical_role" else None
    return {
        "schema": "bbk.role-return.v1",
        "contract": contract["contract_id"],
        "role": role["name"],
        "invocation_mode": mode["mode"],
        "return_kind": contract["allowed_return_kinds"][0],
        "subject_ref": {"id": "SUBJECT-EXAMPLE", "revision": "1"},
        "parent_ref": parent_ref,
        "attempt_ref": {
            "semantic_run_id": "RUN-EXAMPLE",
            "physical_attempt_id": "ATTEMPT-EXAMPLE",
            "host_session_id": None,
            "continuation_of": None,
            "replacement_of": None,
        },
        "operational_disposition": contract["allowed_operational_dispositions"][0],
        "semantic_state": {
            "name": contract["semantic_state_name"],
            "value": contract["allowed_semantic_states"][0],
        },
        "summary": "Representative schema-valid role return.",
        "authority_and_effects_used": {
            "authority_refs": [],
            "allowed_effect_classes": [],
            "effects_used": [],
            "denied_or_uncovered_effects": [],
            "violations_or_ambiguities": [],
        },
        "result": {
            name: field_example(field)
            for name, field in contract["result_fields"].items()
        },
        "durable_handoff_refs": [],
        "smallest_valid_next_action": {
            "action": "RETURN_TO_PARENT",
            "owner": parent,
            "reason": "Representative contract validation.",
            "affected_refs": [],
            "unaffected_work_may_continue": False,
        },
    }


def validate_role_returns(root: Path, registry: Any | None, errors: list[str]) -> None:
    try:
        drift = check_role_return_outputs(root, write=False)
    except Exception as exc:  # retain exact contract-tool diagnostics
        errors.append(f"role-return generation check failed: {exc}")
        return
    errors.extend(drift)
    catalog, roles, entries = load_role_package(root)
    registry_doc = load_json(root, REGISTRY_PATH)
    add_error(errors, registry_doc.get("role_count") == 19, "role-return registry must contain 19 roles")
    add_error(errors, len(registry_doc.get("entries", [])) == 19, "role-return registry entry count must be 19")
    add_error(errors, registry_doc.get("operational_dispositions") == EXPECTED_DISPOSITIONS,
              "role-return registry disposition vocabulary drifted")
    if registry is not None:
        try:
            import jsonschema
            for role in roles:
                document = representative_role_return(role, entries[role["name"]])
                schema = load_json(root, Path(role["return_contract"]["return_schema"]))
                jsonschema.Draft202012Validator(
                    schema, registry=registry, format_checker=jsonschema.FormatChecker()
                ).validate(document)
        except Exception as exc:
            errors.append(f"representative role-return validation failed: {exc}")
    add_error(errors, catalog.get("contract_package") == CONTRACT_CATALOG.as_posix(),
              "split-role catalog must link the contract package")


def validate_contract_catalog(root: Path, roles: set[str], errors: list[str]) -> dict[str, Any]:
    catalog = load_json(root, CONTRACT_CATALOG)
    add_error(errors, catalog.get("source_role_catalog") == "spec/roles/catalog.json",
              "contract catalog source_role_catalog is incorrect")
    package = catalog.get("role_return_package") or {}
    expected_paths = {
        "common_envelope": ENVELOPE_PATH.as_posix(),
        "generated_registry": REGISTRY_PATH.as_posix(),
        "registry_schema": ROLE_RETURN_REGISTRY_SCHEMA.as_posix(),
        "generator": "tools/return_contracts.py",
        "return_schema_directory": "spec/schemas/role-returns",
        "result_schema_directory": "spec/schemas/role-results",
    }
    for key, expected in expected_paths.items():
        add_error(errors, package.get(key) == expected,
                  f"contract catalog role_return_package.{key} must equal {expected}")
    for raw in [catalog.get("capability_status_inventory"), *expected_paths.values()]:
        if isinstance(raw, str):
            add_error(errors, (root / raw).exists(), f"contract package path does not exist: {raw}")
    entries = catalog.get("execution_contracts") or []
    by_id = {entry.get("contract_id"): entry for entry in entries if isinstance(entry, dict)}
    add_error(errors, set(by_id) == set(EXPECTED_EXECUTION_CONTRACTS),
              "execution-contract catalog membership drifted")
    for contract_id, (kind, status, owner) in EXPECTED_EXECUTION_CONTRACTS.items():
        entry = by_id.get(contract_id) or {}
        add_error(errors, entry.get("kind") == kind, f"{contract_id}: wrong kind")
        add_error(errors, entry.get("status") == status, f"{contract_id}: wrong status")
        add_error(errors, entry.get("lifecycle_owner") == owner, f"{contract_id}: wrong lifecycle owner")
        for field in ("schema", "source"):
            value = entry.get(field)
            add_error(errors, isinstance(value, str) and (root / value).is_file(),
                      f"{contract_id}: missing {field} path {value!r}")
        named_roles = set(entry.get("producer_roles") or []) | set(entry.get("consumer_roles") or []) | {owner}
        add_error(errors, named_roles <= roles, f"{contract_id}: unknown role in ownership contract")
    return catalog


def validate_capability_inventory(root: Path, roles: set[str], errors: list[str]) -> dict[str, Any]:
    inventory = load_json(root, CAPABILITY_INVENTORY)
    add_error(errors, inventory.get("status_vocabulary") == EXPECTED_STATUS_VOCABULARY,
              "capability status vocabulary/order drifted")
    entries = inventory.get("entries") or []
    ids = [entry.get("capability_id") for entry in entries if isinstance(entry, dict)]
    add_error(errors, len(ids) == len(set(ids)), "capability IDs must be unique")
    add_error(errors, set(ids) == EXPECTED_CAPABILITIES, "capability inventory membership drifted")
    by_id = {entry.get("capability_id"): entry for entry in entries if isinstance(entry, dict)}
    retired = by_id.get("WorkerValidationBatch") or {}
    add_error(errors, retired.get("status") == "RETIRED_NOT_IMPLEMENTED",
              "WorkerValidationBatch must remain RETIRED_NOT_IMPLEMENTED")
    add_error(errors, retired.get("replacement_refs") == [
        "candidate-producing Worker cohort", "immutable candidate identity", "candidate-assurance run"
    ], "WorkerValidationBatch replacement contract drifted")
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        status = entry.get("status")
        add_error(errors, status in EXPECTED_STATUS_VOCABULARY,
                  f"{entry.get('capability_id')}: unknown status {status!r}")
        named_roles = set(entry.get("owner_roles") or []) | set(entry.get("consumer_roles") or [])
        add_error(errors, named_roles <= roles,
                  f"{entry.get('capability_id')}: unknown role in capability ownership")
        for source in entry.get("source_refs") or []:
            add_error(errors, (root / source).exists(),
                      f"{entry.get('capability_id')}: missing source ref {source}")
    for required, expected in {
        "RoleReturnEnvelope": "IMPLEMENTED_DETERMINISTIC",
        "RoleSpecificReturnSchemas": "IMPLEMENTED_DETERMINISTIC",
        "TerritoryExecutionBoundary": "SCHEMA_DEFINED_COMPANION",
        "LocalDiscoveryPolicy": "SCHEMA_DEFINED_COMPANION",
        "LocalDiscoveryEnvelope": "SCHEMA_DEFINED_COMPANION",
        "LocalDiscoveryPermit": "SCHEMA_DEFINED_COMPANION",
        "CandidateManifest": "IMPLEMENTED_BOOTSTRAP",
        "GateReceipt": "IMPLEMENTED_BOOTSTRAP",
        "WorkerQualityAttestation": "IMPLEMENTED_BOOTSTRAP",
        "ExecutionAuthorization": "TARGET_ONLY",
        "ExecutionScopeFence": "TARGET_ONLY",
        "SemanticRun": "HOST_PROVIDED_OPTIONAL",
        "LeaseAndFencingToken": "HOST_PROVIDED_OPTIONAL",
        "RepairRecord": "TARGET_ONLY",
        "ClosureTransition": "TARGET_ONLY",
    }.items():
        add_error(errors, (by_id.get(required) or {}).get("status") == expected,
                  f"{required}: capability status must be {expected}")
    return inventory


def validate_boundary(boundary: Mapping[str, Any], errors: list[str]) -> None:
    add_error(errors, boundary.get("lifecycle_state") == "ADMITTED",
              "boundary template must demonstrate the ADMITTED state")
    admission = boundary.get("admission") or {}
    add_error(errors, admission.get("compiled_by_role") == "bbk_root_orchestrator",
              "Root Orchestrator must compile the boundary")
    add_error(errors, admission.get("admitted_by_role") == "bbk_root_orchestrator",
              "Root Orchestrator must admit the boundary")
    add_error(errors, (boundary.get("local_discovery") or {}).get("issuer_role") == "bbk_territory_orchestrator",
              "Territory Orchestrator must own local-discovery issuance")
    add_error(errors, (boundary.get("completion_contract") or {}).get("completion_owner_role") == "bbk_territory_orchestrator",
              "Territory Orchestrator must own boundary completion reporting")
    immutability = boundary.get("immutability") or {}
    add_error(errors, immutability.get("immutable_after") == "ADMITTED",
              "boundary immutability must begin at ADMITTED")
    add_error(errors, immutability.get("successor_required_for_change") is True,
              "immutable boundary changes must require a successor")
    expected_fields = {
        "subject_ref", "operating_baseline_ref", "execution_baseline_ref",
        "execution_authorization_ref", "root_campaign_ref", "membership", "ownership",
        "interfaces", "authority_and_effects", "resources_and_budgets", "assurance",
        "local_discovery.policy_ref", "recovery_and_invalidation", "completion_contract",
    }
    add_error(errors, set(immutability.get("immutable_fields") or []) == expected_fields,
              "boundary immutable-field set is incomplete or ambiguous")
    membership = boundary.get("membership") or {}
    add_error(errors, bool(membership.get("work_unit_refs")),
              "boundary template must bind at least one WorkUnit")


def validate_local_discovery(
    policy: Mapping[str, Any], envelope: Mapping[str, Any], permit: Mapping[str, Any],
    boundary: Mapping[str, Any], errors: list[str],
) -> None:
    budget_policy = policy.get("budget") or {}
    add_error(errors, policy.get("default_allowance") == "ZERO_WITHOUT_ACTIVE_ENVELOPE_AND_PERMIT",
              "local discovery must default to zero")
    add_error(errors, policy.get("issuer_role") == "bbk_territory_orchestrator",
              "Territory Orchestrator must be sole local-discovery issuer")
    add_error(errors, policy.get("proposer_roles") == ["bbk_worker_orchestrator", "bbk_worker"],
              "local-discovery proposer roles drifted")
    expected_budget = {
        "item_unit": "DISCOVERY_ITEM",
        "max_items_per_envelope": 2,
        "effort_unit": "PLANNED_EFFORT_UNIT",
        "effort_unit_semantics": "COHORT_CHARTER_RELATIVE_NONNEGATIVE_INTEGER",
        "denominator_source": "COMPILED_COHORT_CHARTER",
        "denominator_binding": "EXACT_COHORT_ID_REVISION_SHA256_AND_DECLARED_TOTAL",
        "max_effort_basis_points": 1000,
        "rounding": "FLOOR",
        "missing_denominator_allowance": 0,
        "cumulative_accounting": True,
    }
    add_error(errors, budget_policy == expected_budget, "local-discovery policy budget drifted")
    add_error(errors, (policy.get("scope") or {}).get("prohibited_changes") == EXPECTED_PROHIBITED_CHANGES,
              "local-discovery prohibited-governance set drifted")
    c_and_v = policy.get("candidate_and_validation") or {}
    add_error(errors, c_and_v.get("post_freeze_rule") == "SUCCESSOR_COHORT_OR_PARENT_RECHARTER_REQUIRED",
              "post-freeze local discovery must require successor cohort or recharter")
    add_error(errors, c_and_v.get("permit_refs_required_in_candidate_manifest") is True,
              "permit refs must be required in candidate manifests")
    add_error(errors, c_and_v.get("validation_scope_impact_must_be_declared") is True,
              "permit validation impact must be declared")
    add_error(errors, c_and_v.get("permit_cannot_establish_validation") is True,
              "a local-discovery permit must not establish validation")

    add_error(errors, envelope.get("lifecycle_state") == "ACTIVE",
              "example local-discovery envelope must be ACTIVE")
    add_error(errors, (envelope.get("issued_by") or {}).get("role") == "bbk_territory_orchestrator",
              "Territory Orchestrator must issue the envelope")
    add_error(errors, (envelope.get("policy_ref") or {}).get("id") == policy.get("policy_id"),
              "envelope policy reference mismatch")
    add_error(errors, (envelope.get("boundary_ref") or {}).get("id") == boundary.get("boundary_id"),
              "envelope boundary reference mismatch")
    add_error(errors, envelope.get("prohibited_changes") == EXPECTED_PROHIBITED_CHANGES,
              "envelope prohibited-change set must equal policy")
    add_error(errors, envelope.get("invalidation_triggers") == (policy.get("expiry_and_revocation") or {}).get("automatic_invalidation_triggers"),
              "envelope invalidation triggers must exactly match policy")
    cohort_ref = envelope.get("cohort_ref") or {}
    add_error(errors, bool(cohort_ref.get("id")) and cohort_ref.get("revision") is not None
              and isinstance(cohort_ref.get("digest"), str) and len(cohort_ref["digest"]) == 64,
              "envelope must bind exact cohort ID, revision, and SHA-256 digest")
    proposer_roles = {item.get("role") for item in envelope.get("proposed_by_refs") or [] if isinstance(item, dict)}
    add_error(errors, proposer_roles <= set(policy.get("proposer_roles") or []) and bool(proposer_roles),
              "envelope proposer identities are not policy-authorized")
    budget = envelope.get("budget") or {}
    add_error(errors, budget.get("item_unit") == "DISCOVERY_ITEM", "envelope item unit drifted")
    add_error(errors, isinstance(budget.get("item_limit"), int) and 0 <= budget["item_limit"] <= 2,
              "envelope item limit exceeds policy")
    add_error(errors, budget.get("items_used", 0) + budget.get("items_remaining", 0) == budget.get("item_limit"),
              "envelope item accounting does not balance")
    add_error(errors, budget.get("effort_unit") == "PLANNED_EFFORT_UNIT", "envelope effort unit drifted")
    add_error(errors, budget.get("denominator_source") == "COMPILED_COHORT_CHARTER",
              "envelope denominator source drifted")
    add_error(errors, budget.get("denominator_ref") == cohort_ref,
              "envelope denominator reference must exactly equal the bound cohort charter")
    planned = budget.get("planned_effort_units")
    basis_points = budget.get("effort_limit_basis_points")
    if isinstance(planned, int) and isinstance(basis_points, int):
        expected_limit = math.floor(planned * basis_points / 10000) if planned > 0 else 0
        add_error(errors, 0 <= basis_points <= 1000, "envelope effort basis points exceed policy")
        add_error(errors, budget.get("effort_limit_units") == expected_limit,
                  "envelope effort limit does not use FLOOR against compiled cohort budget")
    else:
        errors.append("envelope planned effort and basis points must be integers")
    add_error(errors, budget.get("effort_used_units", 0) + budget.get("effort_remaining_units", 0) == budget.get("effort_limit_units"),
              "envelope effort accounting does not balance")
    add_error(errors, budget.get("rounding") == "FLOOR", "envelope effort rounding must be FLOOR")
    try:
        add_error(errors, parse_time(envelope["issued_at"]) <= parse_time(envelope["activates_at"]) < parse_time(envelope["expires_at"]),
                  "envelope timestamps are not ordered")
    except Exception as exc:
        errors.append(f"envelope timestamps are invalid: {exc}")
    envelope_state = envelope.get("lifecycle_state")
    if envelope_state == "REVOKED":
        add_error(errors, isinstance(envelope.get("revoked_at"), str), "revoked envelope requires revoked_at")
    if envelope_state == "SUPERSEDED":
        add_error(errors, isinstance(envelope.get("superseded_by_ref"), Mapping), "superseded envelope requires successor reference")
    if envelope_state == "EXHAUSTED":
        add_error(errors, budget.get("items_remaining") == 0 or budget.get("effort_remaining_units") == 0,
                  "exhausted envelope must have no remaining item or effort allowance")

    add_error(errors, permit.get("lifecycle_state") in {"ISSUED", "ACTIVE"},
              "example permit must be ISSUED or ACTIVE")
    add_error(errors, (permit.get("issued_by") or {}).get("role") == "bbk_territory_orchestrator",
              "Territory Orchestrator must issue the permit")
    add_error(errors, (permit.get("proposed_by") or {}).get("role") in set(policy.get("proposer_roles") or []),
              "permit proposer is not policy-authorized")
    add_error(errors, (permit.get("policy_ref") or {}).get("id") == policy.get("policy_id"),
              "permit policy reference mismatch")
    add_error(errors, (permit.get("envelope_ref") or {}).get("id") == envelope.get("envelope_id"),
              "permit envelope reference mismatch")
    def bound_ref_identity(value: Any) -> tuple[Any, Any, Any]:
        value = value if isinstance(value, Mapping) else {}
        return value.get("id"), value.get("revision"), value.get("digest")

    add_error(errors, bound_ref_identity(permit.get("boundary_ref"))[:2] == bound_ref_identity(envelope.get("boundary_ref"))[:2],
              "permit boundary reference mismatch")
    add_error(errors, bound_ref_identity(permit.get("cohort_ref")) == bound_ref_identity(envelope.get("cohort_ref")),
              "permit cohort reference mismatch")
    eligible_work_units = {bound_ref_identity(item) for item in envelope.get("eligible_work_unit_refs") or [] if isinstance(item, dict)}
    add_error(errors, bound_ref_identity(permit.get("work_unit_ref")) in eligible_work_units,
              "permit WorkUnit is not eligible under the envelope")
    charge = permit.get("budget_charge") or {}
    add_error(errors, charge.get("item_unit") == "DISCOVERY_ITEM" and charge.get("item_units") == 1,
              "one permit must charge exactly one DISCOVERY_ITEM")
    add_error(errors, charge.get("effort_unit") == "PLANNED_EFFORT_UNIT",
              "permit effort unit drifted")
    add_error(errors, isinstance(charge.get("planned_effort_units"), int)
              and 0 <= charge["planned_effort_units"] <= budget.get("effort_remaining_units", -1),
              "permit effort charge exceeds envelope remainder")
    governance = permit.get("governance_impact") or {}
    add_error(errors, bool(governance) and all(value is False for value in governance.values()),
              "permit may not change a prohibited governance dimension")
    impact = permit.get("candidate_and_validation_impact") or {}
    if impact.get("candidate_state") == "FROZEN_CANDIDATE":
        add_error(errors, impact.get("requires_successor_candidate") is True,
                  "post-freeze permit must require successor candidate")
        add_error(errors, impact.get("requires_successor_cohort_or_parent_recharter") is True,
                  "post-freeze permit must require successor cohort or recharter")
    add_error(errors, isinstance(impact.get("validation_scope_impact"), str) and bool(impact["validation_scope_impact"].strip()),
              "permit must declare validation-scope impact")
    try:
        p_issued, p_active, p_expiry = map(parse_time, [permit["issued_at"], permit["activates_at"], permit["expires_at"]])
        add_error(errors, p_issued <= p_active < p_expiry, "permit timestamps are not ordered")
        add_error(errors, p_expiry <= parse_time(envelope["expires_at"]), "permit outlives its envelope")
    except Exception as exc:
        errors.append(f"permit timestamps are invalid: {exc}")
    permit_state = permit.get("lifecycle_state")
    if permit_state == "CONSUMED":
        add_error(errors, isinstance(permit.get("consumption"), Mapping), "consumed permit requires consumption record")
    if permit_state == "REVOKED":
        add_error(errors, isinstance(permit.get("revoked_at"), str), "revoked permit requires revoked_at")
    if permit_state == "SUPERSEDED":
        add_error(errors, isinstance(permit.get("superseded_by_ref"), Mapping), "superseded permit requires successor reference")


def validate_retired_object_absence(root: Path, errors: list[str]) -> None:
    token = "WorkerValidationBatch"
    for role_path in sorted((root / "spec/roles").glob("bbk_*-role.json")):
        if token in role_path.read_text(encoding="utf-8"):
            errors.append(f"retired object appears in active role source: {role_path.relative_to(root)}")
    for rel in ACTIVE_SOURCE_SCAN:
        if token in (root / rel).read_text(encoding="utf-8"):
            errors.append(f"retired object appears in active source: {rel}")
    inventory_text = (root / CAPABILITY_INVENTORY).read_text(encoding="utf-8")
    add_error(errors, inventory_text.count(token) == 1,
              "retired object must appear exactly once, in the capability inventory")


def validate_canonical_sources(root: Path, paths: Iterable[Path], errors: list[str]) -> None:
    for rel in paths:
        path = root / rel
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"cannot parse {rel}: {exc}")
            continue
        if path.read_bytes() != canonical_bytes(value):
            errors.append(f"drift: {rel} is not canonically serialized")


def validate_package(
    root: Path = ROOT,
    *,
    require_jsonschema: bool = False,
) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    try:
        _, registry, _ = schema_registry(root, required=require_jsonschema)
        schema_pairs = [
            (CONTRACT_CATALOG, CONTRACT_CATALOG_SCHEMA),
            (CAPABILITY_INVENTORY, CAPABILITY_SCHEMA),
            (REGISTRY_PATH, ROLE_RETURN_REGISTRY_SCHEMA),
            (POLICY, POLICY_SCHEMA),
            (BOUNDARY_TEMPLATE, BOUNDARY_SCHEMA),
            (ENVELOPE_TEMPLATE, ENVELOPE_SCHEMA),
            (PERMIT_TEMPLATE, PERMIT_SCHEMA),
        ]
        if registry is not None:
            for instance, schema in schema_pairs:
                validate_instance(root, instance, schema, registry)
        role_catalog, roles_list, _ = load_role_package(root)
        roles = {role["name"] for role in roles_list}
        package_version = role_catalog.get("package_version")
        contract_catalog = validate_contract_catalog(root, roles, errors)
        capability = validate_capability_inventory(root, roles, errors)
        add_error(errors, contract_catalog.get("package_version") == package_version,
                  "contract catalog version must match role package")
        add_error(errors, capability.get("package_version") == package_version,
                  "capability inventory version must match role package")
        validate_role_returns(root, registry, errors)
        boundary = load_json(root, BOUNDARY_TEMPLATE)
        policy = load_json(root, POLICY)
        envelope = load_json(root, ENVELOPE_TEMPLATE)
        permit = load_json(root, PERMIT_TEMPLATE)
        validate_boundary(boundary, errors)
        validate_local_discovery(policy, envelope, permit, boundary, errors)
        validate_retired_object_absence(root, errors)
        validate_canonical_sources(root, [
            CONTRACT_CATALOG, CAPABILITY_INVENTORY, POLICY,
            BOUNDARY_TEMPLATE, ENVELOPE_TEMPLATE, PERMIT_TEMPLATE,
            Path("spec/roles/catalog.json"), Path("spec/roles.json"),
        ], errors)
    except (OSError, json.JSONDecodeError, ContractPackageError) as exc:
        errors.append(str(exc))
    except Exception as exc:
        errors.append(f"contract package validation failed: {type(exc).__name__}: {exc}")
    return errors


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    parser.add_argument("--check", action="store_true", help="validate canonical Gate 3 contract sources")
    parser.add_argument(
        "--require-jsonschema",
        action="store_true",
        help="also require optional jsonschema/referencing Draft 2020-12 conformance checks",
    )
    args = parser.parse_args(argv)
    errors = validate_package(args.root, require_jsonschema=args.require_jsonschema)
    if errors:
        print("BBK contract package errors:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    _, registry, _ = schema_registry(args.root.resolve(), required=False)
    suffix = (
        "; Draft 2020-12 instance checks passed"
        if registry is not None
        else "; optional jsonschema unavailable, deterministic and semantic checks passed"
    )
    print("OK: 19 role-return contracts and 4 execution contracts validated" + suffix)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
