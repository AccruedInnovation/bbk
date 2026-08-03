#!/usr/bin/env python3
"""Generate, inspect, render, and validate canonical BBK role-return contracts.

The canonical contract metadata lives in each split role file. This tool emits
one closed result schema and one full envelope schema per role plus a generated
registry. It uses only the standard library for generation and drift checks;
JSON document validation uses jsonschema when requested.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
ROLE_CATALOG = Path("spec/roles/catalog.json")
ENVELOPE_PATH = Path("spec/schemas/bbk-role-return-v1.schema.json")
ENVELOPE_ID = "bbk.role-return.v1"
ENVELOPE_URI = "https://bbk.local/schemas/bbk-role-return-v1.schema.json"
V2_ENVELOPE_PATH = Path("spec/schemas/bbk-role-return-v2.schema.json")
V2_ENVELOPE_ID = "bbk.role-return.v2"
V2_ENVELOPE_URI = "https://bbk.local/schemas/bbk-role-return-v2.schema.json"
REGISTRY_PATH = Path("spec/contracts/role-return-registry.json")
REGISTRY_SCHEMA_PATH = Path("spec/schemas/bbk-role-return-registry-v1.schema.json")
REGISTRY_SCHEMA_ID = "bbk.role-return-registry.v1"
V2_REGISTRY_PATH = Path("spec/contracts/role-return-registry-v2.json")
V2_REGISTRY_SCHEMA_PATH = Path("spec/schemas/bbk-role-return-registry-v2.schema.json")
V2_REGISTRY_SCHEMA_ID = "bbk.role-return-registry.v2"
DETAIL_LEVELS = ["COMPACT", "FULL"]
OPERATIONAL_DISPOSITIONS = [
    "COMPLETE", "PARTIAL", "BLOCKED_TECHNICAL", "BLOCKED_AUTHORITY",
    "BLOCKED_DECISION", "PAUSED_CAPACITY", "PAUSED_HOST_WINDOW",
    "CANCELLED", "INCONCLUSIVE",
]
LEGACY_ONLY = {"READY_FOR_VALIDATION", "BLOCKED", "PAUSED"}
FIELD_KINDS = {
    "REFERENCE", "REFERENCE_LIST", "ARTIFACT_REFERENCE",
    "ARTIFACT_REFERENCE_LIST", "STRUCTURED", "STRUCTURED_LIST", "STRING",
    "STRING_LIST", "BOOLEAN", "INTEGER", "NUMBER", "ENUM", "ENUM_LIST",
}
COMMON_FIELDS = {
    "schema", "contract", "role", "invocation_mode", "return_kind",
    "subject_ref", "parent_ref", "attempt_ref", "operational_disposition",
    "semantic_state", "summary", "authority_and_effects_used", "result",
    "durable_handoff_refs", "smallest_valid_next_action",
}
V2_COMMON_FIELDS = COMMON_FIELDS | {
    "executor", "detail_level", "outputs", "checks_and_evidence",
    "effects_and_cleanup", "blockers_and_residuals", "prohibited_claims",
}

ROLE_RE = re.compile(r"^bbk_[a-z][a-z0-9_]*$")
MODE_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
FIELD_RE = re.compile(r"^[a-z][a-z0-9_]*$")
CONTRACT_RE = re.compile(r"^bbk\.[a-z0-9][a-z0-9.-]*\.v[0-9]+$")


class ReturnContractError(RuntimeError):
    def __init__(self, errors: Sequence[str] | str):
        self.errors = [errors] if isinstance(errors, str) else list(errors)
        super().__init__("\n".join(self.errors))


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def unique_strings(value: Any) -> bool:
    return (
        isinstance(value, list) and bool(value)
        and all(isinstance(item, str) and bool(item.strip()) for item in value)
        and len(value) == len(set(value))
    )


def role_schema_path(role_name: str) -> str:
    return f"spec/schemas/role-returns/{role_name.replace('_', '-')}-return-v1.schema.json"


def result_schema_path(role_name: str) -> str:
    return f"spec/schemas/role-results/{role_name.replace('_', '-')}-result-v1.schema.json"


def v2_role_schema_path(role_name: str) -> str:
    return f"spec/schemas/role-returns/{role_name.replace('_', '-')}-return-v2.schema.json"


def compact_result_schema_path(role_name: str) -> str:
    return f"spec/schemas/role-results/{role_name.replace('_', '-')}-compact-result-v2.schema.json"


def schema_uri(path: str) -> str:
    return "https://bbk.local/schemas/" + Path(path).name


def load_package(root: Path = ROOT) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    catalog = load_json(root / ROLE_CATALOG)
    roles = [load_json(root / entry["file"]) for entry in catalog["role_entries"]]
    entries = {entry["name"]: entry for entry in catalog["role_entries"]}
    return catalog, roles, entries


def modes_for(entry: Mapping[str, Any]) -> list[str]:
    result: list[str] = []
    for item in entry.get("allowed_parent_modes", []):
        mode = item.get("mode")
        if isinstance(mode, str) and mode not in result:
            result.append(mode)
    return result


def validate_metadata(catalog: Mapping[str, Any], roles: Iterable[Mapping[str, Any]], entries: Mapping[str, Mapping[str, Any]]) -> list[str]:
    errors: list[str] = []
    seen_contracts: set[str] = set()
    seen_paths: set[str] = set()
    required = {
        "contract_id", "envelope_schema", "return_schema", "result_schema",
        "v2_contract_id", "v2_envelope_schema", "v2_return_schema",
        "compact_result_schema", "compact_result_fields", "full_detail_triggers",
        "semantic_state_name", "allowed_invocation_modes",
        "allowed_return_kinds", "allowed_operational_dispositions",
        "allowed_semantic_states", "supplemental_enums", "result_fields",
        "requirements", "readiness_rule", "authority_boundary",
    }
    for role in roles:
        name = role.get("name")
        label = f"{name or '<unknown>'}/return_contract"
        c = role.get("return_contract")
        if not isinstance(name, str) or not ROLE_RE.fullmatch(name):
            errors.append(f"{label}: invalid role name")
            continue
        if not isinstance(c, dict):
            errors.append(f"{label}: must be an object")
            continue
        missing = sorted(required - set(c))
        extra = sorted(set(c) - required)
        if missing: errors.append(f"{label}: missing fields {missing}")
        if extra: errors.append(f"{label}: unexpected fields {extra}")
        contract_id = c.get("contract_id")
        if not isinstance(contract_id, str) or not CONTRACT_RE.fullmatch(contract_id):
            errors.append(f"{label}/contract_id: invalid")
        elif contract_id in seen_contracts:
            errors.append(f"{label}/contract_id: duplicate {contract_id}")
        else:
            seen_contracts.add(contract_id)
        expected_return = role_schema_path(name)
        expected_result = result_schema_path(name)
        expected_v2_return = v2_role_schema_path(name)
        expected_compact = compact_result_schema_path(name)
        if c.get("envelope_schema") != ENVELOPE_PATH.as_posix():
            errors.append(f"{label}/envelope_schema: must equal {ENVELOPE_PATH.as_posix()}")
        if c.get("return_schema") != expected_return:
            errors.append(f"{label}/return_schema: must equal {expected_return}")
        if c.get("result_schema") != expected_result:
            errors.append(f"{label}/result_schema: must equal {expected_result}")
        expected_v2_contract = c.get("contract_id", "").removesuffix(".v1") + ".v2"
        if c.get("v2_contract_id") != expected_v2_contract:
            errors.append(f"{label}/v2_contract_id: must equal {expected_v2_contract!r}")
        if c.get("v2_envelope_schema") != V2_ENVELOPE_PATH.as_posix():
            errors.append(f"{label}/v2_envelope_schema: must equal {V2_ENVELOPE_PATH.as_posix()}")
        if c.get("v2_return_schema") != expected_v2_return:
            errors.append(f"{label}/v2_return_schema: must equal {expected_v2_return}")
        if c.get("compact_result_schema") != expected_compact:
            errors.append(f"{label}/compact_result_schema: must equal {expected_compact}")
        for path_key in ("return_schema", "result_schema", "v2_return_schema", "compact_result_schema"):
            value = c.get(path_key)
            if isinstance(value, str):
                if value in seen_paths: errors.append(f"{label}/{path_key}: duplicate {value}")
                seen_paths.add(value)
        semantic_name = c.get("semantic_state_name")
        if not isinstance(semantic_name, str) or not FIELD_RE.fullmatch(semantic_name):
            errors.append(f"{label}/semantic_state_name: invalid")
        modes = c.get("allowed_invocation_modes")
        expected_modes = modes_for(entries.get(name, {}))
        if not unique_strings(modes) or any(not MODE_RE.fullmatch(x) for x in modes or []):
            errors.append(f"{label}/allowed_invocation_modes: invalid")
        elif modes != expected_modes:
            errors.append(f"{label}/allowed_invocation_modes: must exactly match catalog order {expected_modes!r}")
        for key in ("allowed_return_kinds", "allowed_semantic_states"):
            values = c.get(key)
            if not unique_strings(values) or any(not MODE_RE.fullmatch(x) for x in values or []):
                errors.append(f"{label}/{key}: invalid")
        dispositions = c.get("allowed_operational_dispositions")
        if dispositions != OPERATIONAL_DISPOSITIONS:
            errors.append(f"{label}/allowed_operational_dispositions: must equal canonical vocabulary")
        if set(dispositions or []) & LEGACY_ONLY:
            errors.append(f"{label}: legacy-only disposition appears in current contract")
        enums = c.get("supplemental_enums")
        if not isinstance(enums, dict):
            errors.append(f"{label}/supplemental_enums: must be an object")
        else:
            for enum_name, values in enums.items():
                if not FIELD_RE.fullmatch(str(enum_name)) or not unique_strings(values):
                    errors.append(f"{label}/supplemental_enums/{enum_name}: invalid")
        fields = c.get("result_fields")
        if not isinstance(fields, dict) or not fields:
            errors.append(f"{label}/result_fields: must be a non-empty object")
        else:
            overlap = sorted(set(fields) & COMMON_FIELDS)
            if overlap: errors.append(f"{label}/result_fields: duplicates envelope fields {overlap}")
            for field_name, field in fields.items():
                flabel = f"{label}/result_fields/{field_name}"
                if not FIELD_RE.fullmatch(str(field_name)):
                    errors.append(f"{flabel}: invalid field name")
                if not isinstance(field, dict):
                    errors.append(f"{flabel}: must be an object")
                    continue
                expected_keys = {"kind", "nullable", "description"}
                if field.get("kind") in {"ENUM", "ENUM_LIST"}: expected_keys.add("enum_values")
                if set(field) != expected_keys:
                    errors.append(f"{flabel}: fields must be exactly {sorted(expected_keys)}")
                if field.get("kind") not in FIELD_KINDS:
                    errors.append(f"{flabel}/kind: invalid {field.get('kind')!r}")
                if not isinstance(field.get("nullable"), bool):
                    errors.append(f"{flabel}/nullable: must be boolean")
                description = field.get("description")
                if not isinstance(description, str) or not description.strip():
                    errors.append(f"{flabel}/description: must be non-empty")
                elif re.search(r"\bnull\b", description, re.IGNORECASE) and field.get("nullable") is not True:
                    errors.append(f"{flabel}/nullable: description permits null but nullable is false")
                if field.get("kind") in {"ENUM", "ENUM_LIST"} and not unique_strings(field.get("enum_values")):
                    errors.append(f"{flabel}/enum_values: invalid")
        compact_fields = c.get("compact_result_fields")
        if not unique_strings(compact_fields):
            errors.append(f"{label}/compact_result_fields: must be a non-empty unique string list")
        elif isinstance(fields, dict):
            unknown = [field for field in compact_fields if field not in fields]
            if unknown:
                errors.append(f"{label}/compact_result_fields: unknown result fields {unknown}")
            if len(compact_fields) > 8:
                errors.append(f"{label}/compact_result_fields: compact payload may contain at most 8 fields")
        for key in ("requirements", "full_detail_triggers"):
            if not unique_strings(c.get(key)):
                errors.append(f"{label}/{key}: must be a non-empty unique string list")
        for key in ("readiness_rule", "authority_boundary"):
            if not isinstance(c.get(key), str) or not c.get(key, "").strip():
                errors.append(f"{label}/{key}: must be non-empty")
    if len(seen_contracts) != len(catalog.get("role_entries", [])):
        errors.append("role-return contract IDs are not one-to-one with catalog roles")
    return errors


def field_schema(field: Mapping[str, Any], *, envelope_uri: str = ENVELOPE_URI) -> dict[str, Any]:
    kind = field["kind"]
    refs = {
        "REFERENCE": {"$ref": f"{envelope_uri}#/$defs/reference"},
        "REFERENCE_LIST": {"$ref": f"{envelope_uri}#/$defs/referenceList"},
        "ARTIFACT_REFERENCE": {"$ref": f"{envelope_uri}#/$defs/artifactReference"},
        "ARTIFACT_REFERENCE_LIST": {"$ref": f"{envelope_uri}#/$defs/artifactReferenceList"},
        "STRUCTURED": {"$ref": f"{envelope_uri}#/$defs/structured"},
        "STRUCTURED_LIST": {"$ref": f"{envelope_uri}#/$defs/structuredList"},
        "STRING": {"$ref": f"{envelope_uri}#/$defs/nonEmptyString"},
        "STRING_LIST": {"$ref": f"{envelope_uri}#/$defs/stringList"},
        "BOOLEAN": {"type": "boolean"},
        "INTEGER": {"type": "integer"},
        "NUMBER": {"type": "number"},
        "ENUM": {"type": "string", "enum": field.get("enum_values", [])},
        "ENUM_LIST": {"type": "array", "items": {"type": "string", "enum": field.get("enum_values", [])}, "uniqueItems": True},
    }
    base = dict(refs[kind])
    base["description"] = field["description"]
    if field["nullable"]:
        return {"anyOf": [base, {"type": "null"}], "description": field["description"]}
    return base


def build_result_schema(role: Mapping[str, Any]) -> dict[str, Any]:
    c = role["return_contract"]
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_uri(c["result_schema"]),
        "title": f"BBK {role['title']} result payload v1",
        "description": f"Closed role-specific `result` payload for `{role['name']}` returns.",
        "type": "object",
        "additionalProperties": False,
        "required": list(c["result_fields"]),
        "properties": {name: field_schema(field) for name, field in c["result_fields"].items()},
        "x-bbk-role": role["name"],
        "x-bbk-contract": c["contract_id"],
        "x-bbk-supplemental-enums": c["supplemental_enums"],
    }


def build_v2_envelope(root: Path = ROOT) -> dict[str, Any]:
    """Project the additive v2 envelope from the stable v1 definitions."""
    envelope = copy.deepcopy(load_json(root / ENVELOPE_PATH))
    envelope["$id"] = V2_ENVELOPE_URI
    envelope["title"] = "BBK canonical role-return envelope v2"
    envelope["description"] = (
        "Common machine-valid envelope for COMPACT or FULL canonical BBK role returns. "
        "V1 remains consume-compatible; v2 adds exact executor identity, proportional detail, "
        "and concise evidence/effect/next-action truth without creating acceptance authority."
    )
    defs = envelope["$defs"]
    defs["executorReference"] = {
        "type": "object",
        "additionalProperties": True,
        "required": ["role", "invocation_id"],
        "properties": {
            "role": {"type": "string", "pattern": "^bbk_[a-z][a-z0-9_]*$"},
            "invocation_id": {"$ref": "#/$defs/nonEmptyString"},
            "host_session_id": {"type": ["string", "null"], "minLength": 1},
            "provider": {"type": ["string", "null"], "minLength": 1},
            "model": {"type": ["string", "null"], "minLength": 1},
        },
    }
    defs["nonEmptyStructuredList"] = {
        "type": "array", "minItems": 1, "items": {"$ref": "#/$defs/structured"}
    }
    defs["nonEmptyStringList"] = {
        "type": "array", "minItems": 1,
        "items": {"$ref": "#/$defs/nonEmptyString"}, "uniqueItems": True,
    }
    envelope["required"] = [
        "schema", "contract", "role", "executor", "invocation_mode", "return_kind",
        "detail_level", "subject_ref", "parent_ref", "attempt_ref",
        "operational_disposition", "semantic_state", "summary",
        "authority_and_effects_used", "result", "smallest_valid_next_action",
    ]
    properties = envelope["properties"]
    properties["schema"] = {"const": V2_ENVELOPE_ID}
    properties["executor"] = {"$ref": "#/$defs/executorReference"}
    properties["detail_level"] = {"enum": DETAIL_LEVELS}
    properties["outputs"] = {
        "type": "array", "minItems": 1,
        "items": {"$ref": "#/$defs/reference"},
        "description": "Material output or sealed-package references; omit when none exist.",
    }
    properties["checks_and_evidence"] = {
        "$ref": "#/$defs/nonEmptyStructuredList",
        "description": "Material checks and evidence with claim limits; omit when none exist.",
    }
    properties["effects_and_cleanup"] = {
        "$ref": "#/$defs/structured",
        "description": "Material effects, cleanup, quarantine, or disposition facts; omit when irrelevant.",
    }
    properties["blockers_and_residuals"] = {
        "$ref": "#/$defs/nonEmptyStringList",
        "description": "Material blockers and residual uncertainty; omit only when none remain.",
    }
    properties["prohibited_claims"] = {
        "$ref": "#/$defs/nonEmptyStringList",
        "description": "Material claims this return does not establish; omit only when none are material.",
    }
    properties["durable_handoff_refs"] = {
        "type": "array", "minItems": 1,
        "items": {"$ref": "#/$defs/handoffReference"},
        "description": "Verified durable handoff references; omit when no separate handoff exists.",
    }
    return envelope


def build_compact_result_schema(role: Mapping[str, Any]) -> dict[str, Any]:
    c = role["return_contract"]
    selected = c["compact_result_fields"]
    fields = c["result_fields"]
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_uri(c["compact_result_schema"]),
        "title": f"BBK {role['title']} compact result payload v2",
        "description": (
            f"Closed compact role-specific result payload for `{role['name']}`. "
            "Use FULL when material truth cannot fit these fields."
        ),
        "type": "object",
        "additionalProperties": False,
        "required": list(selected),
        "properties": {
            name: field_schema(fields[name], envelope_uri=V2_ENVELOPE_URI)
            for name in selected
        },
        "x-bbk-role": role["name"],
        "x-bbk-contract": c["v2_contract_id"],
        "x-bbk-detail-level": "COMPACT",
        "x-bbk-full-detail-triggers": c["full_detail_triggers"],
    }


def build_v2_return_schema(role: Mapping[str, Any], entry: Mapping[str, Any]) -> dict[str, Any]:
    c = role["return_contract"]
    narrowing = {
        "type": "object",
        "properties": {
            "contract": {"const": c["v2_contract_id"]},
            "role": {"const": role["name"]},
            "executor": {
                "type": "object",
                "properties": {"role": {"const": role["name"]}},
                "required": ["role"],
            },
            "invocation_mode": {"enum": c["allowed_invocation_modes"]},
            "return_kind": {"enum": c["allowed_return_kinds"]},
            "operational_disposition": {"enum": c["allowed_operational_dispositions"]},
            "semantic_state": {
                "type": "object", "additionalProperties": False,
                "required": ["name", "value"],
                "properties": {
                    "name": {"const": c["semantic_state_name"]},
                    "value": {"enum": c["allowed_semantic_states"]},
                },
            },
        },
        "allOf": [
            *parent_constraints(entry),
            {
                "if": {"properties": {"detail_level": {"const": "COMPACT"}}, "required": ["detail_level"]},
                "then": {"properties": {"result": {"$ref": schema_uri(c["compact_result_schema"])}}},
            },
            {
                "if": {"properties": {"detail_level": {"const": "FULL"}}, "required": ["detail_level"]},
                "then": {"properties": {"result": {"$ref": schema_uri(c["result_schema"])}}},
            },
        ],
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_uri(c["v2_return_schema"]),
        "title": f"BBK {role['title']} return v2",
        "description": f"Role-specific `{V2_ENVELOPE_ID}` COMPACT/FULL contract for `{role['name']}`.",
        "allOf": [{"$ref": V2_ENVELOPE_URI}, narrowing],
        "x-bbk-role": role["name"],
        "x-bbk-contract": c["v2_contract_id"],
        "x-bbk-envelope": V2_ENVELOPE_ID,
        "x-bbk-v1-consume-compatible": True,
        "x-bbk-full-result-schema": c["result_schema"],
        "x-bbk-compact-result-schema": c["compact_result_schema"],
        "x-bbk-full-detail-triggers": c["full_detail_triggers"],
        "x-bbk-semantic-state-name": c["semantic_state_name"],
        "x-bbk-requirements": c["requirements"],
        "x-bbk-readiness-rule": c["readiness_rule"],
        "x-bbk-authority-boundary": c["authority_boundary"],
    }


def parent_constraints(entry: Mapping[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for item in entry.get("allowed_parent_modes", []):
        grouped.setdefault(item["mode"], []).append(item)
    constraints: list[dict[str, Any]] = []
    for mode, items in grouped.items():
        alternatives: list[dict[str, Any]] = []
        for item in items:
            properties: dict[str, Any] = {
                "kind": {"const": item["parent_kind"]},
                "id": {"enum": item["parents"]},
                "invocation_mode": {"const": mode},
            }
            required = ["kind", "id", "invocation_mode"]
            if item["parent_kind"] == "canonical_role":
                properties["role"] = {"enum": item["parents"]}
                required.append("role")
            else:
                properties["role"] = {"type": "null"}
            alternatives.append({"type": "object", "properties": properties, "required": required})
        constraints.append({
            "if": {"properties": {"invocation_mode": {"const": mode}}, "required": ["invocation_mode"]},
            "then": {"properties": {"parent_ref": {"oneOf": alternatives}}},
        })
    return constraints


def build_return_schema(role: Mapping[str, Any], entry: Mapping[str, Any]) -> dict[str, Any]:
    c = role["return_contract"]
    narrowing = {
        "type": "object",
        "properties": {
            "contract": {"const": c["contract_id"]},
            "role": {"const": role["name"]},
            "invocation_mode": {"enum": c["allowed_invocation_modes"]},
            "return_kind": {"enum": c["allowed_return_kinds"]},
            "operational_disposition": {"enum": c["allowed_operational_dispositions"]},
            "semantic_state": {
                "type": "object", "additionalProperties": False,
                "required": ["name", "value"],
                "properties": {
                    "name": {"const": c["semantic_state_name"]},
                    "value": {"enum": c["allowed_semantic_states"]},
                },
            },
            "result": {"$ref": schema_uri(c["result_schema"])},
        },
        "allOf": parent_constraints(entry),
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_uri(c["return_schema"]),
        "title": f"BBK {role['title']} return v1",
        "description": f"Role-specific `{ENVELOPE_ID}` contract for `{role['name']}`.",
        "allOf": [{"$ref": ENVELOPE_URI}, narrowing],
        "x-bbk-role": role["name"],
        "x-bbk-contract": c["contract_id"],
        "x-bbk-envelope": ENVELOPE_ID,
        "x-bbk-semantic-state-name": c["semantic_state_name"],
        "x-bbk-requirements": c["requirements"],
        "x-bbk-readiness-rule": c["readiness_rule"],
        "x-bbk-authority-boundary": c["authority_boundary"],
    }


def expected_outputs(root: Path = ROOT) -> tuple[dict[str, Any], list[dict[str, Any]], dict[Path, bytes]]:
    catalog, roles, entries = load_package(root)
    errors = validate_metadata(catalog, roles, entries)
    if errors:
        raise ReturnContractError(errors)
    outputs: dict[Path, bytes] = {}
    v1_registry_entries: list[dict[str, Any]] = []
    v2_registry_entries: list[dict[str, Any]] = []
    outputs[root / V2_ENVELOPE_PATH] = canonical_bytes(build_v2_envelope(root))
    for role in roles:
        c = role["return_contract"]
        result_payload = canonical_bytes(build_result_schema(role))
        return_payload = canonical_bytes(build_return_schema(role, entries[role["name"]]))
        compact_payload = canonical_bytes(build_compact_result_schema(role))
        v2_return_payload = canonical_bytes(build_v2_return_schema(role, entries[role["name"]]))
        result_path = root / c["result_schema"]
        return_path = root / c["return_schema"]
        compact_path = root / c["compact_result_schema"]
        v2_return_path = root / c["v2_return_schema"]
        outputs[result_path] = result_payload
        outputs[return_path] = return_payload
        outputs[compact_path] = compact_payload
        outputs[v2_return_path] = v2_return_payload
        source_path = root / entries[role["name"]]["file"]
        source_record = {
            "path": entries[role["name"]]["file"],
            "bytes": source_path.stat().st_size,
            "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        }
        v1_registry_entries.append({
            "role": role["name"], "contract_id": c["contract_id"],
            "semantic_state_name": c["semantic_state_name"],
            "return_schema": {"path": c["return_schema"], "bytes": len(return_payload), "sha256": sha256(return_payload)},
            "result_schema": {"path": c["result_schema"], "bytes": len(result_payload), "sha256": sha256(result_payload)},
            "source": source_record,
        })
        v2_registry_entries.append({
            "role": role["name"],
            "contract_id": c["v2_contract_id"],
            "default_detail_level": "COMPACT",
            "allowed_detail_levels": DETAIL_LEVELS,
            "semantic_state_name": c["semantic_state_name"],
            "return_schema": {"path": c["v2_return_schema"], "bytes": len(v2_return_payload), "sha256": sha256(v2_return_payload)},
            "compact_result_schema": {"path": c["compact_result_schema"], "bytes": len(compact_payload), "sha256": sha256(compact_payload)},
            "full_result_schema": {"path": c["result_schema"], "bytes": len(result_payload), "sha256": sha256(result_payload)},
            "v1_compatibility": {"contract_id": c["contract_id"], "return_schema": c["return_schema"]},
            "compact_result_fields": c["compact_result_fields"],
            "full_detail_triggers": c["full_detail_triggers"],
            "source": source_record,
        })
    registry = {
        "schema": REGISTRY_SCHEMA_ID,
        "package_version": catalog["package_version"],
        "source_role_catalog": ROLE_CATALOG.as_posix(),
        "envelope_schema": ENVELOPE_PATH.as_posix(),
        "generator": "tools/return_contracts.py",
        "role_count": len(v1_registry_entries),
        "operational_dispositions": OPERATIONAL_DISPOSITIONS,
        "entries": v1_registry_entries,
    }
    v2_registry = {
        "schema": V2_REGISTRY_SCHEMA_ID,
        "package_version": catalog["package_version"],
        "source_role_catalog": ROLE_CATALOG.as_posix(),
        "envelope_schema": V2_ENVELOPE_PATH.as_posix(),
        "v1_registry": REGISTRY_PATH.as_posix(),
        "generator": "tools/return_contracts.py",
        "role_count": len(v2_registry_entries),
        "default_detail_level": "COMPACT",
        "allowed_detail_levels": DETAIL_LEVELS,
        "operational_dispositions": OPERATIONAL_DISPOSITIONS,
        "entries": v2_registry_entries,
    }
    outputs[root / REGISTRY_PATH] = canonical_bytes(registry)
    outputs[root / V2_REGISTRY_PATH] = canonical_bytes(v2_registry)
    return catalog, roles, outputs


def check_or_write(root: Path, write: bool) -> list[str]:
    _, _, outputs = expected_outputs(root)
    errors: list[str] = []
    expected = set(outputs)
    for path, payload in outputs.items():
        if write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        elif not path.is_file():
            errors.append(f"missing: {path.relative_to(root).as_posix()}")
        elif path.read_bytes() != payload:
            errors.append(f"drift: {path.relative_to(root).as_posix()}")
    for directory in (root / "spec/schemas/role-returns", root / "spec/schemas/role-results"):
        if directory.exists():
            for path in directory.glob("*.schema.json"):
                if path not in expected: errors.append(f"unexpected generated schema: {path.relative_to(root).as_posix()}")
    return errors


def render_return_contract_prompt(role: Mapping[str, Any]) -> str:
    c = role["return_contract"]
    lines = [
        "## Exact role-return contract", "",
        f"Return one JSON object governed by `{c['v2_return_schema']}`. New returns use `{c['v2_envelope_schema']}`; v1 remains consume-compatible through `{c['return_schema']}`.", "",
        "Use these exact v2 discriminators:", "",
        f"- `schema`: `{V2_ENVELOPE_ID}`",
        f"- `contract`: `{c['v2_contract_id']}`",
        f"- `role` and `executor.role`: `{role['name']}`",
        "- `detail_level`: `COMPACT` by default; use `FULL` only when a trigger below applies",
        "- `invocation_mode`: " + ", ".join(f"`{x}`" for x in c["allowed_invocation_modes"]),
        "- `return_kind`: " + ", ".join(f"`{x}`" for x in c["allowed_return_kinds"]),
        "- `operational_disposition`: " + ", ".join(f"`{x}`" for x in c["allowed_operational_dispositions"]),
        f"- `semantic_state.name`: `{c['semantic_state_name']}`",
        "- `semantic_state.value`: " + ", ".join(f"`{x}`" for x in c["allowed_semantic_states"]), "",
        "The v2 envelope requires exact subject, parent, attempt, executor, disposition, semantic state, summary, authority/effect truth, result, and smallest valid next action. Include material outputs, checks/evidence, effects/cleanup, blockers/residuals, prohibited claims, and durable handoff references; omit only irrelevant empty sections.", "",
        f"COMPACT uses `{c['compact_result_schema']}` and requires:", "",
    ]
    for name in c["compact_result_fields"]:
        field = c["result_fields"][name]
        details = field["kind"] + ("; nullable" if field["nullable"] else "")
        if field["kind"] in {"ENUM", "ENUM_LIST"}:
            details += "; " + ", ".join(field["enum_values"])
        lines.append(f"- `{name}` ({details}) — {field['description']}")
    lines += ["", f"FULL uses the existing complete payload `{c['result_schema']}`. Use FULL when:", ""]
    lines.extend(f"- {item}" for item in c["full_detail_triggers"])
    lines += ["", "Readiness rule:", "", c["readiness_rule"], "", "Authority boundary:", "", c["authority_boundary"], "", "Operational completion, role semantic readiness, accountable acceptance, and release remain separate. Do not emit `READY_FOR_VALIDATION`, `BLOCKED`, or `PAUSED` as current operational dispositions."]
    return "\n".join(lines)


def load_role(role_name: str, root: Path = ROOT) -> dict[str, Any]:
    _, roles, _ = load_package(root)
    for role in roles:
        if role["name"] == role_name: return role
    raise ReturnContractError(f"unknown role: {role_name}")


def validate_document(document: Any, role_name: str, root: Path = ROOT) -> None:
    try:
        import jsonschema
        from referencing import Registry, Resource
    except ImportError as exc:
        raise ReturnContractError(f"jsonschema is required for document validation: {exc}")
    role = load_role(role_name, root)
    c = role["return_contract"]
    schema_id = document.get("schema") if isinstance(document, dict) else None
    if schema_id == ENVELOPE_ID:
        paths = [ENVELOPE_PATH, Path(c["result_schema"]), Path(c["return_schema"])]
    elif schema_id == V2_ENVELOPE_ID:
        paths = [ENVELOPE_PATH, V2_ENVELOPE_PATH, Path(c["compact_result_schema"]), Path(c["result_schema"]), Path(c["v2_return_schema"])]
    else:
        raise ReturnContractError(f"unsupported role-return schema: {schema_id!r}")
    schemas = [load_json(root / path) for path in paths]
    registry = Registry()
    for schema in schemas:
        registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    jsonschema.Draft202012Validator(schemas[-1], registry=registry).validate(document)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    group.add_argument("--validate", type=Path)
    parser.add_argument("--role")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.validate:
            if not args.role: raise ReturnContractError("--validate requires --role")
            validate_document(load_json(args.validate), args.role, root)
            print(f"OK: {args.validate} validates as {args.role}")
            return 0
        errors = check_or_write(root, write=args.write)
        if errors: raise ReturnContractError(errors)
        _, roles, _ = load_package(root)
        action = "generated" if args.write else "verified"
        print(f"OK: {action} {len(roles)} v1 + {len(roles)} v2 role return schemas, {len(roles)} full + {len(roles)} compact result schemas, and two registries")
        return 0
    except (OSError, json.JSONDecodeError, ReturnContractError) as exc:
        print(f"BBK role-return contract error:\n{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
