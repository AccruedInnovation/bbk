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
