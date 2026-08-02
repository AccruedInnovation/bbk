#!/usr/bin/env python3
"""Generate, inspect, render, and validate canonical BBK role-return contracts.

The canonical contract metadata lives in each split role file. This tool emits
one closed result schema and one full envelope schema per role plus a generated
registry. It uses only the standard library for generation and drift checks;
JSON document validation uses jsonschema when requested.
"""
from __future__ import annotations

import argparse
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
REGISTRY_PATH = Path("spec/contracts/role-return-registry.json")
REGISTRY_SCHEMA_PATH = Path("spec/schemas/bbk-role-return-registry-v1.schema.json")
REGISTRY_SCHEMA_ID = "bbk.role-return-registry.v1"
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
ROLE_RE = re.compile(r"^bbk_[a-z][a-z0-9_]*$")
MODE_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
FIELD_RE = re.compile(r"^[a-z][a-z0-9_]*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
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
        if c.get("envelope_schema") != ENVELOPE_PATH.as_posix():
            errors.append(f"{label}/envelope_schema: must equal {ENVELOPE_PATH.as_posix()}")
        if c.get("return_schema") != expected_return:
            errors.append(f"{label}/return_schema: must equal {expected_return}")
        if c.get("result_schema") != expected_result:
            errors.append(f"{label}/result_schema: must equal {expected_result}")
        for path_key in ("return_schema", "result_schema"):
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
        for key in ("requirements",):
            if not unique_strings(c.get(key)):
                errors.append(f"{label}/{key}: must be a non-empty unique string list")
        for key in ("readiness_rule", "authority_boundary"):
            if not isinstance(c.get(key), str) or not c.get(key, "").strip():
                errors.append(f"{label}/{key}: must be non-empty")
    if len(seen_contracts) != len(catalog.get("role_entries", [])):
        errors.append("role-return contract IDs are not one-to-one with catalog roles")
    return errors


def field_schema(field: Mapping[str, Any]) -> dict[str, Any]:
    kind = field["kind"]
    refs = {
        "REFERENCE": {"$ref": f"{ENVELOPE_URI}#/$defs/reference"},
        "REFERENCE_LIST": {"$ref": f"{ENVELOPE_URI}#/$defs/referenceList"},
        "ARTIFACT_REFERENCE": {"$ref": f"{ENVELOPE_URI}#/$defs/artifactReference"},
        "ARTIFACT_REFERENCE_LIST": {"$ref": f"{ENVELOPE_URI}#/$defs/artifactReferenceList"},
        "STRUCTURED": {"$ref": f"{ENVELOPE_URI}#/$defs/structured"},
        "STRUCTURED_LIST": {"$ref": f"{ENVELOPE_URI}#/$defs/structuredList"},
        "STRING": {"$ref": f"{ENVELOPE_URI}#/$defs/nonEmptyString"},
        "STRING_LIST": {"$ref": f"{ENVELOPE_URI}#/$defs/stringList"},
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
    if errors: raise ReturnContractError(errors)
    outputs: dict[Path, bytes] = {}
    registry_entries: list[dict[str, Any]] = []
    for role in roles:
        c = role["return_contract"]
        result_payload = canonical_bytes(build_result_schema(role))
        return_payload = canonical_bytes(build_return_schema(role, entries[role["name"]]))
        result_path = root / c["result_schema"]
        return_path = root / c["return_schema"]
        outputs[result_path] = result_payload
        outputs[return_path] = return_payload
        source_path = root / entries[role["name"]]["file"]
        registry_entries.append({
            "role": role["name"], "contract_id": c["contract_id"],
            "semantic_state_name": c["semantic_state_name"],
            "return_schema": {"path": c["return_schema"], "bytes": len(return_payload), "sha256": sha256(return_payload)},
            "result_schema": {"path": c["result_schema"], "bytes": len(result_payload), "sha256": sha256(result_payload)},
            "source": {"path": entries[role["name"]]["file"], "bytes": source_path.stat().st_size, "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest()},
        })
    registry = {
        "schema": REGISTRY_SCHEMA_ID,
        "package_version": catalog["package_version"],
        "source_role_catalog": ROLE_CATALOG.as_posix(),
        "envelope_schema": ENVELOPE_PATH.as_posix(),
        "generator": "tools/return_contracts.py",
        "role_count": len(registry_entries),
        "operational_dispositions": OPERATIONAL_DISPOSITIONS,
        "entries": registry_entries,
    }
    outputs[root / REGISTRY_PATH] = canonical_bytes(registry)
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
        f"Return one JSON object governed by `{c['return_schema']}`. Its common envelope is `{c['envelope_schema']}` and its closed role payload is `{c['result_schema']}`.", "",
        "Use these exact discriminators:", "",
        f"- `schema`: `{ENVELOPE_ID}`",
        f"- `contract`: `{c['contract_id']}`",
        f"- `role`: `{role['name']}`",
        "- `invocation_mode`: " + ", ".join(f"`{x}`" for x in c["allowed_invocation_modes"]),
        "- `return_kind`: " + ", ".join(f"`{x}`" for x in c["allowed_return_kinds"]),
        "- `operational_disposition`: " + ", ".join(f"`{x}`" for x in c["allowed_operational_dispositions"]),
        f"- `semantic_state.name`: `{c['semantic_state_name']}`",
        "- `semantic_state.value`: " + ", ".join(f"`{x}`" for x in c["allowed_semantic_states"]), "",
        "The envelope also requires `subject_ref`, `parent_ref`, `attempt_ref`, `summary`, `authority_and_effects_used`, `result`, `durable_handoff_refs`, and `smallest_valid_next_action`.", "",
        "The closed `result` payload requires every field below:", "",
    ]
    for name, field in c["result_fields"].items():
        details = field["kind"] + ("; nullable" if field["nullable"] else "")
        if field["kind"] in {"ENUM", "ENUM_LIST"}:
            details += "; " + ", ".join(field["enum_values"])
        lines.append(f"- `{name}` ({details}) — {field['description']}")
    lines += ["", "Readiness rule:", "", c["readiness_rule"], "", "Authority boundary:", "", c["authority_boundary"], "", "Do not emit `READY_FOR_VALIDATION`, `BLOCKED`, or `PAUSED` as current operational dispositions; those values are consume-only legacy `bbk.handoff.v1` inputs."]
    return "\n".join(lines)


def load_role(role_name: str, root: Path = ROOT) -> dict[str, Any]:
    _, roles, _ = load_package(root)
    for role in roles:
        if role["name"] == role_name: return role
    raise ReturnContractError(f"unknown role: {role_name}")



def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_non_empty_string(value: Any, path: str, errors: list[str]) -> None:
    if not _is_non_empty_string(value):
        errors.append(f"{path}: must be a non-empty string")


def _validate_string_list(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append(f"{path}: must be an array")
        return
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not _is_non_empty_string(item):
            errors.append(f"{path}[{index}]: must be a non-empty string")
        elif item in seen:
            errors.append(f"{path}[{index}]: duplicate value {item!r}")
        else:
            seen.add(item)


def _validate_reference(
    value: Any,
    path: str,
    errors: list[str],
    *,
    require_id: bool = False,
) -> None:
    if not isinstance(value, dict) or not value:
        errors.append(f"{path}: must be a non-empty object")
        return
    if require_id and "id" not in value:
        errors.append(f"{path}: missing required field 'id'")
    if not any(key in value for key in ("id", "path", "uri")):
        errors.append(f"{path}: requires at least one of 'id', 'path', or 'uri'")
    for key in ("id", "schema", "path", "uri", "lifecycle_state"):
        if key in value:
            _validate_non_empty_string(value[key], f"{path}.{key}", errors)
    if "revision" in value:
        revision = value["revision"]
        if not ((_is_integer(revision) and revision >= 0) or _is_non_empty_string(revision)):
            errors.append(f"{path}.revision: must be a non-negative integer or non-empty string")
    if "digest" in value and (
        not isinstance(value["digest"], str) or not SHA256_RE.fullmatch(value["digest"])
    ):
        errors.append(f"{path}.digest: must be a lowercase SHA-256 digest")


def _validate_artifact_reference(value: Any, path: str, errors: list[str]) -> None:
    _validate_reference(value, path, errors)
    if not isinstance(value, dict):
        return
    for key in ("path", "bytes", "sha256"):
        if key not in value:
            errors.append(f"{path}: missing required field {key!r}")
    if "path" in value:
        _validate_non_empty_string(value["path"], f"{path}.path", errors)
    if "bytes" in value and (not _is_integer(value["bytes"]) or value["bytes"] < 0):
        errors.append(f"{path}.bytes: must be a non-negative integer")
    if "sha256" in value and (
        not isinstance(value["sha256"], str) or not SHA256_RE.fullmatch(value["sha256"])
    ):
        errors.append(f"{path}.sha256: must be a lowercase SHA-256 digest")


def _validate_attempt_reference(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{path}: must be an object")
        return
    for key in ("semantic_run_id", "physical_attempt_id"):
        if key not in value:
            errors.append(f"{path}: missing required field {key!r}")
        else:
            _validate_non_empty_string(value[key], f"{path}.{key}", errors)
    for key in ("host_session_id", "continuation_of", "replacement_of"):
        if key in value and value[key] is not None:
            _validate_non_empty_string(value[key], f"{path}.{key}", errors)


def _validate_authority_and_effects(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{path}: must be an object")
        return
    required = (
        "authority_refs", "allowed_effect_classes", "effects_used",
        "denied_or_uncovered_effects", "violations_or_ambiguities",
    )
    for key in required:
        if key not in value:
            errors.append(f"{path}: missing required field {key!r}")
    refs = value.get("authority_refs")
    if isinstance(refs, list):
        for index, item in enumerate(refs):
            _validate_reference(item, f"{path}.authority_refs[{index}]", errors)
    elif "authority_refs" in value:
        errors.append(f"{path}.authority_refs: must be an array")
    if "allowed_effect_classes" in value:
        _validate_string_list(value["allowed_effect_classes"], f"{path}.allowed_effect_classes", errors)
    for key in ("effects_used", "denied_or_uncovered_effects", "violations_or_ambiguities"):
        if key not in value:
            continue
        items = value[key]
        if not isinstance(items, list):
            errors.append(f"{path}.{key}: must be an array")
            continue
        for index, item in enumerate(items):
            if not isinstance(item, dict) or not item:
                errors.append(f"{path}.{key}[{index}]: must be a non-empty object")


def _validate_handoff_reference(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{path}: must be an object")
        return
    for key in ("id", "path", "bytes", "sha256"):
        if key not in value:
            errors.append(f"{path}: missing required field {key!r}")
    for key in ("id", "path", "schema"):
        if key in value:
            _validate_non_empty_string(value[key], f"{path}.{key}", errors)
    if "bytes" in value and (not _is_integer(value["bytes"]) or value["bytes"] < 0):
        errors.append(f"{path}.bytes: must be a non-negative integer")
    if "sha256" in value and (
        not isinstance(value["sha256"], str) or not SHA256_RE.fullmatch(value["sha256"])
    ):
        errors.append(f"{path}.sha256: must be a lowercase SHA-256 digest")
    if "subject_ref" in value:
        _validate_reference(value["subject_ref"], f"{path}.subject_ref", errors)
    if "producer_attempt_ref" in value:
        _validate_attempt_reference(value["producer_attempt_ref"], f"{path}.producer_attempt_ref", errors)


def _validate_next_action(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{path}: must be an object")
        return
    for key in ("action", "owner", "reason"):
        if key not in value:
            errors.append(f"{path}: missing required field {key!r}")
        else:
            _validate_non_empty_string(value[key], f"{path}.{key}", errors)
    refs = value.get("affected_refs")
    if refs is not None:
        if not isinstance(refs, list):
            errors.append(f"{path}.affected_refs: must be an array")
        else:
            for index, item in enumerate(refs):
                _validate_reference(item, f"{path}.affected_refs[{index}]", errors)
    if "unaffected_work_may_continue" in value and not isinstance(
        value["unaffected_work_may_continue"], bool
    ):
        errors.append(f"{path}.unaffected_work_may_continue: must be boolean")


def _validate_result_field(value: Any, field: Mapping[str, Any], path: str, errors: list[str]) -> None:
    if value is None:
        if not field.get("nullable"):
            errors.append(f"{path}: null is not permitted")
        return
    kind = field["kind"]
    if kind == "STRING":
        _validate_non_empty_string(value, path, errors)
    elif kind == "STRING_LIST":
        _validate_string_list(value, path, errors)
    elif kind == "BOOLEAN":
        if not isinstance(value, bool):
            errors.append(f"{path}: must be boolean")
    elif kind == "INTEGER":
        if not _is_integer(value):
            errors.append(f"{path}: must be an integer")
    elif kind == "NUMBER":
        if not _is_number(value):
            errors.append(f"{path}: must be a number")
    elif kind == "REFERENCE":
        _validate_reference(value, path, errors)
    elif kind == "REFERENCE_LIST":
        if not isinstance(value, list):
            errors.append(f"{path}: must be an array")
        else:
            for index, item in enumerate(value):
                _validate_reference(item, f"{path}[{index}]", errors)
    elif kind == "ARTIFACT_REFERENCE":
        _validate_artifact_reference(value, path, errors)
    elif kind == "ARTIFACT_REFERENCE_LIST":
        if not isinstance(value, list):
            errors.append(f"{path}: must be an array")
        else:
            for index, item in enumerate(value):
                _validate_artifact_reference(item, f"{path}[{index}]", errors)
    elif kind == "STRUCTURED":
        if not isinstance(value, dict) or not value:
            errors.append(f"{path}: must be a non-empty object")
    elif kind == "STRUCTURED_LIST":
        if not isinstance(value, list):
            errors.append(f"{path}: must be an array")
        else:
            for index, item in enumerate(value):
                if not isinstance(item, dict) or not item:
                    errors.append(f"{path}[{index}]: must be a non-empty object")
    elif kind == "ENUM":
        if value not in field.get("enum_values", []):
            errors.append(f"{path}: must be one of {field.get('enum_values', [])!r}")
    elif kind == "ENUM_LIST":
        if not isinstance(value, list):
            errors.append(f"{path}: must be an array")
        else:
            seen: list[Any] = []
            allowed = field.get("enum_values", [])
            for index, item in enumerate(value):
                if item not in allowed:
                    errors.append(f"{path}[{index}]: must be one of {allowed!r}")
                if item in seen:
                    errors.append(f"{path}[{index}]: duplicate value {item!r}")
                seen.append(item)
    else:  # protected by canonical metadata validation
        errors.append(f"{path}: unsupported field kind {kind!r}")


def validate_result_field_value(value: Any, field: Mapping[str, Any]) -> list[str]:
    """Validate one canonical role-result field value without JSON Schema."""
    errors: list[str] = []
    _validate_result_field(value, field, "$", errors)
    return errors


def validate_document_contract(
    document: Any,
    role_name: str,
    root: Path = ROOT,
) -> list[str]:
    """Validate one role return without optional third-party packages.

    This is a contract-specific deterministic validator, not a general JSON
    Schema implementation. It enforces the canonical envelope, catalogue
    parent admissions, and every role-specific result field. The optional
    ``jsonschema`` path remains available for Draft 2020-12 conformance checks.
    """
    errors: list[str] = []
    try:
        _, roles, entries = load_package(root)
    except (OSError, json.JSONDecodeError, ReturnContractError) as exc:
        return [f"cannot load role-return package: {exc}"]
    role = next((item for item in roles if item.get("name") == role_name), None)
    if role is None:
        return [f"unknown role: {role_name}"]
    if not isinstance(document, dict):
        return ["$: must be an object"]
    missing = sorted(COMMON_FIELDS - set(document))
    extra = sorted(set(document) - COMMON_FIELDS)
    if missing:
        errors.append(f"$: missing fields {missing}")
    if extra:
        errors.append(f"$: unexpected fields {extra}")
    contract = role["return_contract"]
    exact_values = {
        "schema": ENVELOPE_ID,
        "contract": contract["contract_id"],
        "role": role_name,
    }
    for key, expected in exact_values.items():
        if document.get(key) != expected:
            errors.append(f"$.{key}: must equal {expected!r}")
    mode = document.get("invocation_mode")
    if mode not in contract["allowed_invocation_modes"]:
        errors.append(
            f"$.invocation_mode: must be one of {contract['allowed_invocation_modes']!r}"
        )
    if document.get("return_kind") not in contract["allowed_return_kinds"]:
        errors.append(
            f"$.return_kind: must be one of {contract['allowed_return_kinds']!r}"
        )
    if document.get("operational_disposition") not in contract["allowed_operational_dispositions"]:
        errors.append(
            "$.operational_disposition: must be one of "
            f"{contract['allowed_operational_dispositions']!r}"
        )
    if "subject_ref" in document:
        _validate_reference(document["subject_ref"], "$.subject_ref", errors, require_id=True)
    parent = document.get("parent_ref")
    if not isinstance(parent, dict):
        errors.append("$.parent_ref: must be an object")
    else:
        for key in ("kind", "id", "invocation_mode"):
            if key not in parent:
                errors.append(f"$.parent_ref: missing required field {key!r}")
        candidates = [
            item for item in entries[role_name].get("allowed_parent_modes", [])
            if item.get("mode") == mode
        ]
        admitted = False
        for item in candidates:
            if parent.get("kind") != item.get("parent_kind"):
                continue
            if parent.get("id") not in item.get("parents", []):
                continue
            if parent.get("invocation_mode") != item.get("mode"):
                continue
            if item.get("parent_kind") == "canonical_role":
                if parent.get("role") not in item.get("parents", []):
                    continue
            elif "role" in parent and parent.get("role") is not None:
                continue
            admitted = True
            break
        if not admitted:
            errors.append("$.parent_ref: is not admitted for this role and invocation mode")
        for key in ("invocation_id", "return_route"):
            if key in parent:
                _validate_non_empty_string(parent[key], f"$.parent_ref.{key}", errors)
    if "attempt_ref" in document:
        _validate_attempt_reference(document["attempt_ref"], "$.attempt_ref", errors)
    semantic = document.get("semantic_state")
    if not isinstance(semantic, dict):
        errors.append("$.semantic_state: must be an object")
    else:
        if set(semantic) != {"name", "value"}:
            errors.append("$.semantic_state: fields must be exactly ['name', 'value']")
        if semantic.get("name") != contract["semantic_state_name"]:
            errors.append(
                f"$.semantic_state.name: must equal {contract['semantic_state_name']!r}"
            )
        if semantic.get("value") not in contract["allowed_semantic_states"]:
            errors.append(
                "$.semantic_state.value: must be one of "
                f"{contract['allowed_semantic_states']!r}"
            )
    if "summary" in document:
        _validate_non_empty_string(document["summary"], "$.summary", errors)
    if "authority_and_effects_used" in document:
        _validate_authority_and_effects(
            document["authority_and_effects_used"], "$.authority_and_effects_used", errors
        )
    result = document.get("result")
    fields = contract["result_fields"]
    if not isinstance(result, dict):
        errors.append("$.result: must be an object")
    else:
        missing_result = sorted(set(fields) - set(result))
        extra_result = sorted(set(result) - set(fields))
        if missing_result:
            errors.append(f"$.result: missing fields {missing_result}")
        if extra_result:
            errors.append(f"$.result: unexpected fields {extra_result}")
        for field_name, field in fields.items():
            if field_name in result:
                _validate_result_field(
                    result[field_name], field, f"$.result.{field_name}", errors
                )
    handoffs = document.get("durable_handoff_refs")
    if handoffs is not None:
        if not isinstance(handoffs, list):
            errors.append("$.durable_handoff_refs: must be an array")
        else:
            for index, item in enumerate(handoffs):
                _validate_handoff_reference(item, f"$.durable_handoff_refs[{index}]", errors)
    if "smallest_valid_next_action" in document:
        _validate_next_action(
            document["smallest_valid_next_action"], "$.smallest_valid_next_action", errors
        )
    return errors

def validate_document(document: Any, role_name: str, root: Path = ROOT) -> None:
    try:
        import jsonschema
        from referencing import Registry, Resource
    except ImportError as exc:
        raise ReturnContractError(f"jsonschema is required for document validation: {exc}")
    role = load_role(role_name, root)
    schemas = [load_json(root / ENVELOPE_PATH), load_json(root / role["return_contract"]["result_schema"]), load_json(root / role["return_contract"]["return_schema"])]
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
        print(f"OK: {action} {len(roles)} role return schemas, {len(roles)} result schemas, and registry")
        return 0
    except (OSError, json.JSONDecodeError, ReturnContractError) as exc:
        print(f"BBK role-return contract error:\n{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
