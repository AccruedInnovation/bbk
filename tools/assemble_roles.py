#!/usr/bin/env python3
"""Assemble and verify the canonical BBK split-role package.

``spec/roles/catalog.json`` and its ordered per-role files are canonical.
``spec/roles.json`` is a deterministic compatibility projection consumed by
existing role generators and host adapters. The assembler validates the v4
schemas, method references, delegation graph, controller entrypoints, allowed
parent modes, human-request routing, multi-root reachability, source identity,
and projection drift.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from prompt_modules import (
    PromptModuleError,
    load_prompt_modules,
    mandatory_procedure_exception_measurement,
    role_skill_module_requirements,
    source_manifest as prompt_module_source_manifest,
    validate_skill_templates,
)
from return_contracts import validate_metadata as validate_return_contract_metadata


DEFAULT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_CONTROLLER_ENTRYPOINTS = (
    ("PLANNING", "bbk_root_wayfinder", "CONTROLLER_ROOT"),
    ("EXECUTION", "bbk_root_orchestrator", "CONTROLLER_ROOT"),
    ("REVIEW", "bbk_reviewer", "DIRECT_BOUNDED_REVIEW"),
    ("ASSURANCE", "bbk_validator_orchestrator", "CONTROLLER_ROOT"),
)
EXPECTED_HUMAN_REQUEST_ORIGINATORS = (
    "bbk_root_wayfinder",
    "bbk_questioning_wayfinder",
    "bbk_question_guide",
)
EXPECTED_EXCLUSIVE_PROMPT_MODULE_ROLES = {
    "bbk-prompt-human-request": set(EXPECTED_HUMAN_REQUEST_ORIGINATORS),
    "bbk-prompt-handoff-protocol": {
        "bbk_architect",
        "bbk_phase_wayfinder",
        "bbk_planning_wayfinder",
        "bbk_prototyper",
        "bbk_reviewer",
        "bbk_root_orchestrator",
        "bbk_synthesizer",
        "bbk_territory_orchestrator",
        "bbk_validator",
        "bbk_validator_orchestrator",
        "bbk_verification_designer",
        "bbk_worker",
        "bbk_worker_designer",
        "bbk_worker_orchestrator",
    },
    "bbk-prompt-executable-baseline": {
        "bbk_architect",
        "bbk_phase_wayfinder",
        "bbk_planning_wayfinder",
        "bbk_prototyper",
        "bbk_reviewer",
        "bbk_root_orchestrator",
        "bbk_root_wayfinder",
        "bbk_territory_orchestrator",
        "bbk_territory_wayfinder",
        "bbk_verification_designer",
        "bbk_worker",
        "bbk_worker_designer",
        "bbk_worker_orchestrator",
    },
    "bbk-prompt-execution-slicing": {
        "bbk_planning_wayfinder",
        "bbk_phase_wayfinder",
    },
    "bbk-prompt-profile-dispatch": {"bbk_worker_designer"},
    "bbk-prompt-evidence-receipts": {
        "bbk_reviewer",
        "bbk_validator",
        "bbk_validator_orchestrator",
        "bbk_verification_designer",
    },
    "bbk-prompt-finding-lifecycle": {
        "bbk_reviewer",
        "bbk_validator",
        "bbk_validator_orchestrator",
        "bbk_verification_designer",
    },
}


class RolePackageError(RuntimeError):
    """Raised when one or more split-role package invariants fail."""

    def __init__(self, errors: Sequence[str]):
        self.errors = list(errors)
        super().__init__("\n".join(self.errors))


@dataclass(frozen=True)
class PackagePaths:
    root: Path
    catalog: Path
    role_dir: Path
    role_schema: Path
    catalog_schema: Path
    aggregate_schema: Path
    method_content: Path
    prompt_module_catalog: Path
    contract_catalog: Path
    projection: Path

    @classmethod
    def from_root(cls, root: Path) -> "PackagePaths":
        root = root.resolve()
        return cls(
            root=root,
            catalog=root / "spec" / "roles" / "catalog.json",
            role_dir=root / "spec" / "roles",
            role_schema=root / "spec" / "schemas" / "bbk-role-v4.schema.json",
            catalog_schema=root / "spec" / "schemas" / "bbk-role-catalog-v4.schema.json",
            aggregate_schema=root / "spec" / "schemas" / "bbk-roles-v4.schema.json",
            method_content=root / "spec" / "method-content.json",
            prompt_module_catalog=root / "spec" / "prompt-modules" / "catalog.json",
            contract_catalog=root / "spec" / "contracts" / "catalog.json",
            projection=root / "spec" / "roles.json",
        )


@dataclass(frozen=True)
class AssembledRolePackage:
    paths: PackagePaths
    catalog: dict[str, Any]
    roles: tuple[dict[str, Any], ...]
    projection: dict[str, Any]
    canonical_sources: tuple[Path, ...]


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def rel(paths: PackagePaths, path: Path) -> str:
    try:
        return path.resolve().relative_to(paths.root).as_posix()
    except ValueError:
        return str(path)


def load_json(paths: PackagePaths, path: Path, errors: list[str]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        errors.append(f"cannot read {rel(paths, path)}: {exc}")
    except json.JSONDecodeError as exc:
        errors.append(
            f"invalid JSON in {rel(paths, path)} at line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}"
        )
    return None


def pointer(parts: Iterable[Any]) -> str:
    encoded = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(encoded) if encoded else "/"


ROLE_REQUIRED_FIELDS = {
    "id", "name", "title", "family", "description", "purpose",
    "constitution", "scope", "responsibilities", "delegation",
    "escalations", "human_decision_triggers", "prohibitions", "skills",
    "primary_skill", "mandatory_skills", "prompt_modules",
    "mutates", "spawns", "web", "return_contract",
}
CATALOG_REQUIRED_FIELDS = {
    "schema_version", "package_version", "catalog_schema", "role_schema",
    "projection_schema", "method_content_source", "prompt_module_package",
    "contract_package", "compatibility_projection",
    "constitution_modules",
    "interaction_topology", "controller_entrypoints", "role_entries",
}
PROJECTION_REQUIRED_FIELDS = {
    "schema_version", "package_version", "projection_schema", "source_catalog",
    "prompt_module_package", "contract_package", "source_manifest",
    "constitution_modules", "interaction_topology", "controller_entrypoints",
    "role_entries", "roles",
}
ROLE_NAME_PATTERN = re.compile(r"^bbk_[a-z][a-z0-9_]*$")
ROLE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
MODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
SKILL_PATTERN = re.compile(r"^bbk(?:-[a-z0-9]+)+$")
PROMPT_MODULE_PATTERN = re.compile(r"^bbk-prompt-[a-z0-9]+(?:-[a-z0-9]+)*$")
VERSION_PATTERN = re.compile(
    r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
RETURN_SCHEMA_PATTERN = re.compile(r"^bbk\.[a-z0-9][a-z0-9.-]*\.v[0-9]+$")
LEGACY_ONLY_DISPOSITIONS = {"READY_FOR_VALIDATION", "BLOCKED", "PAUSED"}


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _check_fields(
    instance: Any,
    required: set[str],
    label: str,
    errors: list[str],
) -> bool:
    if not isinstance(instance, dict):
        errors.append(f"{label}: must be an object")
        return False
    missing = sorted(required - set(instance))
    extra = sorted(set(instance) - required)
    if missing:
        errors.append(f"{label}: missing fields {missing}")
    if extra:
        errors.append(f"{label}: unexpected fields {extra}")
    return not missing and not extra


def _check_string_list(
    value: Any,
    label: str,
    errors: list[str],
    *,
    non_empty: bool,
    pattern: re.Pattern[str] | None = None,
) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{label}: must be an array")
        return []
    if non_empty and not value:
        errors.append(f"{label}: must not be empty")
    result: list[str] = []
    for index, item in enumerate(value):
        if not _is_non_empty_string(item):
            errors.append(f"{label}/{index}: must be a non-empty string")
            continue
        if pattern is not None and not pattern.fullmatch(item):
            errors.append(f"{label}/{index}: invalid value {item!r}")
        result.append(item)
    if len(result) != len(set(result)):
        errors.append(f"{label}: values must be unique")
    return result


def _validate_return_contract(instance: Any, label: str, errors: list[str]) -> None:
    required = {
        "contract_id", "envelope_schema", "return_schema", "result_schema",
        "semantic_state_name", "allowed_invocation_modes", "allowed_return_kinds",
        "allowed_operational_dispositions", "allowed_semantic_states",
        "supplemental_enums", "result_fields", "requirements",
        "readiness_rule", "authority_boundary",
    }
    _check_fields(instance, required, label, errors)
    if not isinstance(instance, dict):
        return
    contract_id = instance.get("contract_id")
    if not _is_non_empty_string(contract_id) or not re.fullmatch(
        r"bbk\.[a-z0-9][a-z0-9.-]*-return\.v[0-9]+", contract_id
    ):
        errors.append(f"{label}/contract_id: invalid role-return contract ID")
    if instance.get("envelope_schema") != "spec/schemas/bbk-role-return-v1.schema.json":
        errors.append(f"{label}/envelope_schema: invalid common envelope path")
    for key, pattern in (
        ("return_schema", r"spec/schemas/role-returns/bbk-[a-z][a-z0-9-]*-return-v[0-9]+\.schema\.json"),
        ("result_schema", r"spec/schemas/role-results/bbk-[a-z][a-z0-9-]*-result-v[0-9]+\.schema\.json"),
    ):
        value = instance.get(key)
        if not _is_non_empty_string(value) or not re.fullmatch(pattern, value):
            errors.append(f"{label}/{key}: invalid generated schema path")
    semantic_name = instance.get("semantic_state_name")
    if not _is_non_empty_string(semantic_name) or not ROLE_ID_PATTERN.fullmatch(semantic_name):
        errors.append(f"{label}/semantic_state_name: must be lower_snake_case")
    for key in (
        "allowed_invocation_modes", "allowed_return_kinds",
        "allowed_operational_dispositions", "allowed_semantic_states",
    ):
        values = _check_string_list(instance.get(key), f"{label}/{key}", errors, non_empty=True)
        if key in {"allowed_invocation_modes", "allowed_return_kinds", "allowed_semantic_states"}:
            for index, value in enumerate(values):
                if not MODE_PATTERN.fullmatch(value):
                    errors.append(f"{label}/{key}/{index}: must be UPPER_SNAKE_CASE")
    dispositions = instance.get("allowed_operational_dispositions") or []
    legacy = sorted(set(dispositions) & LEGACY_ONLY_DISPOSITIONS)
    if legacy:
        errors.append(f"{label}: emits legacy-only operational dispositions {legacy}")
    enums = instance.get("supplemental_enums")
    if not isinstance(enums, dict):
        errors.append(f"{label}/supplemental_enums: must be an object")
    else:
        for enum_name, values in enums.items():
            if not isinstance(enum_name, str) or not ROLE_ID_PATTERN.fullmatch(enum_name):
                errors.append(f"{label}/supplemental_enums: invalid name {enum_name!r}")
            _check_string_list(values, f"{label}/supplemental_enums/{enum_name}", errors, non_empty=True)
    fields = instance.get("result_fields")
    field_kinds = {
        "STRING", "STRING_LIST", "BOOLEAN", "INTEGER", "NUMBER",
        "REFERENCE", "REFERENCE_LIST", "ARTIFACT_REFERENCE",
        "ARTIFACT_REFERENCE_LIST", "STRUCTURED", "STRUCTURED_LIST", "ENUM", "ENUM_LIST",
    }
    if not isinstance(fields, dict) or not fields:
        errors.append(f"{label}/result_fields: must be a non-empty object")
    else:
        for field_name, field in fields.items():
            field_label = f"{label}/result_fields/{field_name}"
            if not isinstance(field_name, str) or not ROLE_ID_PATTERN.fullmatch(field_name):
                errors.append(f"{field_label}: invalid field name")
            if not isinstance(field, dict):
                errors.append(f"{field_label}: must be an object")
                continue
            expected = {"kind", "nullable", "description"}
            if field.get("kind") in {"ENUM", "ENUM_LIST"}:
                expected.add("enum_values")
            _check_fields(field, expected, field_label, errors)
            if field.get("kind") not in field_kinds:
                errors.append(f"{field_label}/kind: invalid")
            if not isinstance(field.get("nullable"), bool):
                errors.append(f"{field_label}/nullable: must be boolean")
            if not _is_non_empty_string(field.get("description")):
                errors.append(f"{field_label}/description: must be non-empty text")
            if "enum_values" in expected:
                _check_string_list(field.get("enum_values"), f"{field_label}/enum_values", errors, non_empty=True)
    _check_string_list(instance.get("requirements"), f"{label}/requirements", errors, non_empty=True)
    for key in ("readiness_rule", "authority_boundary"):
        if not _is_non_empty_string(instance.get(key)):
            errors.append(f"{label}/{key}: must be non-empty text")


def _validate_role_shape(instance: Any, label: str, errors: list[str]) -> None:
    _check_fields(instance, ROLE_REQUIRED_FIELDS, label, errors)
    if not isinstance(instance, dict):
        return
    role_id = instance.get("id")
    role_name = instance.get("name")
    if not _is_non_empty_string(role_id) or not ROLE_ID_PATTERN.fullmatch(role_id):
        errors.append(f"{label}/id: must be lower_snake_case")
    if not _is_non_empty_string(role_name) or not ROLE_NAME_PATTERN.fullmatch(role_name):
        errors.append(f"{label}/name: must be a canonical bbk_* role name")
    for key in ("title", "description", "purpose"):
        if not _is_non_empty_string(instance.get(key)):
            errors.append(f"{label}/{key}: must be non-empty text")
    if instance.get("family") not in {"planning", "specialist", "execution", "review"}:
        errors.append(f"{label}/family: invalid family {instance.get('family')!r}")
    _check_string_list(
        instance.get("constitution"), f"{label}/constitution", errors,
        non_empty=True, pattern=ROLE_ID_PATTERN,
    )
    for key in ("scope", "responsibilities", "escalations", "prohibitions"):
        _check_string_list(instance.get(key), f"{label}/{key}", errors, non_empty=True)
    _check_string_list(
        instance.get("human_decision_triggers"),
        f"{label}/human_decision_triggers", errors, non_empty=False,
    )
    _check_string_list(
        instance.get("skills"), f"{label}/skills", errors,
        non_empty=True, pattern=SKILL_PATTERN,
    )
    primary_skill = instance.get("primary_skill")
    if not _is_non_empty_string(primary_skill) or not SKILL_PATTERN.fullmatch(primary_skill):
        errors.append(f"{label}/primary_skill: must be a canonical bbk-* skill name")
    _check_string_list(
        instance.get("mandatory_skills"), f"{label}/mandatory_skills", errors,
        non_empty=True, pattern=SKILL_PATTERN,
    )
    _check_string_list(
        instance.get("prompt_modules"), f"{label}/prompt_modules", errors,
        non_empty=True, pattern=PROMPT_MODULE_PATTERN,
    )
    _check_string_list(
        instance.get("spawns"), f"{label}/spawns", errors,
        non_empty=False, pattern=ROLE_NAME_PATTERN,
    )
    delegation = instance.get("delegation")
    if not isinstance(delegation, dict):
        errors.append(f"{label}/delegation: must be an object")
    else:
        for child, trigger in delegation.items():
            if not isinstance(child, str) or not ROLE_NAME_PATTERN.fullmatch(child):
                errors.append(f"{label}/delegation: invalid child name {child!r}")
            if not _is_non_empty_string(trigger):
                errors.append(f"{label}/delegation/{child}: must be non-empty text")
    for key in ("mutates", "web"):
        if not isinstance(instance.get(key), bool):
            errors.append(f"{label}/{key}: must be boolean")
    _validate_return_contract(instance.get("return_contract"), f"{label}/return_contract", errors)


def _validate_catalog_shape(instance: Any, label: str, errors: list[str]) -> None:
    _check_fields(instance, CATALOG_REQUIRED_FIELDS, label, errors)
    if not isinstance(instance, dict):
        return
    if instance.get("schema_version") != "bbk.roles.v4":
        errors.append(f"{label}/schema_version: must equal bbk.roles.v4")
    version = instance.get("package_version")
    if not _is_non_empty_string(version) or not VERSION_PATTERN.fullmatch(version):
        errors.append(f"{label}/package_version: invalid semantic version")
    expected_paths = {
        "catalog_schema": "spec/schemas/bbk-role-catalog-v4.schema.json",
        "role_schema": "spec/schemas/bbk-role-v4.schema.json",
        "projection_schema": "spec/schemas/bbk-roles-v4.schema.json",
        "method_content_source": "spec/method-content.json",
        "prompt_module_package": "spec/prompt-modules/catalog.json",
        "contract_package": "spec/contracts/catalog.json",
        "compatibility_projection": "spec/roles.json",
    }
    for key, expected in expected_paths.items():
        if instance.get(key) != expected:
            errors.append(f"{label}/{key}: must equal {expected!r}")
    modules = instance.get("constitution_modules")
    if not isinstance(modules, dict) or not modules or "core" not in modules:
        errors.append(f"{label}/constitution_modules: must be non-empty and define core")
    elif isinstance(modules, dict):
        for name, clauses in modules.items():
            if not isinstance(name, str) or not ROLE_ID_PATTERN.fullmatch(name):
                errors.append(f"{label}/constitution_modules: invalid module {name!r}")
            _check_string_list(
                clauses, f"{label}/constitution_modules/{name}", errors, non_empty=True
            )
    topology = instance.get("interaction_topology")
    topology_fields = {
        "user_facing_identity", "canonical_roles_user_facing", "human_request_route",
        "omp_transport", "fallback_transport", "human_request_originators",
    }
    _check_fields(topology, topology_fields, f"{label}/interaction_topology", errors)
    if isinstance(topology, dict):
        if topology.get("user_facing_identity") != "harness_root_controller":
            errors.append(f"{label}/interaction_topology/user_facing_identity: invalid")
        if topology.get("canonical_roles_user_facing") is not False:
            errors.append(f"{label}/interaction_topology/canonical_roles_user_facing: must be false")
        for key in ("human_request_route", "omp_transport", "fallback_transport"):
            if not _is_non_empty_string(topology.get(key)):
                errors.append(f"{label}/interaction_topology/{key}: must be non-empty text")
        _check_string_list(
            topology.get("human_request_originators"),
            f"{label}/interaction_topology/human_request_originators",
            errors, non_empty=True, pattern=ROLE_NAME_PATTERN,
        )
    entrypoints = instance.get("controller_entrypoints")
    if not isinstance(entrypoints, list) or len(entrypoints) != 4:
        errors.append(f"{label}/controller_entrypoints: must contain exactly four entries")
    else:
        entrypoint_fields = {
            "route", "role", "invocation_mode", "selected_by", "selection_when",
        }
        for index, entry in enumerate(entrypoints):
            item_label = f"{label}/controller_entrypoints/{index}"
            _check_fields(entry, entrypoint_fields, item_label, errors)
            if not isinstance(entry, dict):
                continue
            if entry.get("route") not in {"PLANNING", "EXECUTION", "REVIEW", "ASSURANCE"}:
                errors.append(f"{item_label}/route: invalid")
            if not _is_non_empty_string(entry.get("role")) or not ROLE_NAME_PATTERN.fullmatch(entry["role"]):
                errors.append(f"{item_label}/role: invalid")
            if not _is_non_empty_string(entry.get("invocation_mode")) or not MODE_PATTERN.fullmatch(entry["invocation_mode"]):
                errors.append(f"{item_label}/invocation_mode: invalid")
            if entry.get("selected_by") != "harness_root_controller":
                errors.append(f"{item_label}/selected_by: invalid")
            if not _is_non_empty_string(entry.get("selection_when")):
                errors.append(f"{item_label}/selection_when: must be non-empty text")
    entries = instance.get("role_entries")
    if not isinstance(entries, list) or len(entries) != 19:
        errors.append(f"{label}/role_entries: must contain exactly 19 entries")
    else:
        role_entry_fields = {"name", "file", "allowed_parent_modes"}
        mode_fields = {"mode", "parent_kind", "parents", "purpose"}
        for index, entry in enumerate(entries):
            item_label = f"{label}/role_entries/{index}"
            _check_fields(entry, role_entry_fields, item_label, errors)
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if not _is_non_empty_string(name) or not ROLE_NAME_PATTERN.fullmatch(name):
                errors.append(f"{item_label}/name: invalid")
            expected_file = f"spec/roles/{name}-role.json" if isinstance(name, str) else None
            if entry.get("file") != expected_file:
                errors.append(f"{item_label}/file: must equal {expected_file!r}")
            modes = entry.get("allowed_parent_modes")
            if not isinstance(modes, list) or not modes:
                errors.append(f"{item_label}/allowed_parent_modes: must be non-empty")
                continue
            for mode_index, mode in enumerate(modes):
                mode_label = f"{item_label}/allowed_parent_modes/{mode_index}"
                _check_fields(mode, mode_fields, mode_label, errors)
                if not isinstance(mode, dict):
                    continue
                if not _is_non_empty_string(mode.get("mode")) or not MODE_PATTERN.fullmatch(mode["mode"]):
                    errors.append(f"{mode_label}/mode: invalid")
                if mode.get("parent_kind") not in {"controller", "canonical_role"}:
                    errors.append(f"{mode_label}/parent_kind: invalid")
                parents = _check_string_list(
                    mode.get("parents"), f"{mode_label}/parents", errors, non_empty=True
                )
                if mode.get("parent_kind") == "controller" and any(
                    parent != "harness_root_controller" for parent in parents
                ):
                    errors.append(f"{mode_label}/parents: invalid controller parent")
                if mode.get("parent_kind") == "canonical_role" and any(
                    not ROLE_NAME_PATTERN.fullmatch(parent) for parent in parents
                ):
                    errors.append(f"{mode_label}/parents: invalid canonical parent")
                if not _is_non_empty_string(mode.get("purpose")):
                    errors.append(f"{mode_label}/purpose: must be non-empty text")


def _validate_projection_shape(instance: Any, label: str, errors: list[str]) -> None:
    _check_fields(instance, PROJECTION_REQUIRED_FIELDS, label, errors)
    if not isinstance(instance, dict):
        return
    if instance.get("schema_version") != "bbk.roles.v4":
        errors.append(f"{label}/schema_version: must equal bbk.roles.v4")
    if instance.get("projection_schema") != "spec/schemas/bbk-roles-v4.schema.json":
        errors.append(f"{label}/projection_schema: invalid")
    if instance.get("source_catalog") != "spec/roles/catalog.json":
        errors.append(f"{label}/source_catalog: invalid")
    if instance.get("prompt_module_package") != "spec/prompt-modules/catalog.json":
        errors.append(f"{label}/prompt_module_package: invalid")
    if instance.get("contract_package") != "spec/contracts/catalog.json":
        errors.append(f"{label}/contract_package: invalid")
    roles = instance.get("roles")
    if not isinstance(roles, list) or len(roles) != 19:
        errors.append(f"{label}/roles: must contain exactly 19 roles")
    else:
        for index, role in enumerate(roles):
            _validate_role_shape(role, f"{label}/roles/{index}", errors)
    manifest = instance.get("source_manifest")
    if not isinstance(manifest, dict) or set(manifest) != {"catalog", "roles", "prompt_modules"}:
        errors.append(f"{label}/source_manifest: invalid")
    else:
        records = [manifest.get("catalog")]
        role_records = manifest.get("roles")
        if not isinstance(role_records, list) or len(role_records) != 19:
            errors.append(f"{label}/source_manifest/roles: must contain 19 records")
            role_records = []
        prompt_module_records = manifest.get("prompt_modules")
        if not isinstance(prompt_module_records, list) or len(prompt_module_records) < 2:
            errors.append(f"{label}/source_manifest/prompt_modules: must contain a catalog and at least one module record")
            prompt_module_records = []
        records.extend(role_records)
        records.extend(prompt_module_records)
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                errors.append(f"{label}/source_manifest/{index}: must be an object")
                continue
            required = {"path", "bytes", "sha256"}
            allowed = required | {"name"}
            if not required.issubset(record) or not set(record).issubset(allowed):
                errors.append(f"{label}/source_manifest/{index}: invalid fields")
            if not _is_non_empty_string(record.get("path")):
                errors.append(f"{label}/source_manifest/{index}/path: invalid")
            if not isinstance(record.get("bytes"), int) or record["bytes"] < 1:
                errors.append(f"{label}/source_manifest/{index}/bytes: invalid")
            digest = record.get("sha256")
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                errors.append(f"{label}/source_manifest/{index}/sha256: invalid")


def validate_instance(
    instance: Any,
    schema: Mapping[str, Any],
    label: str,
    errors: list[str],
    *,
    registry: Any | None = None,
) -> None:
    """Apply the package's dependency-free structural schema checks.

    The published Draft 2020-12 schemas are the portable external contract.
    This standard-library implementation mirrors their blocking structure so
    role assembly and drift checks remain runnable before optional validator
    packages are installed. Gate tests cross-check the same instances with a
    conforming Draft 2020-12 implementation when one is available.
    """
    del registry
    schema_id = schema.get("$id") if isinstance(schema, dict) else None
    if not isinstance(schema, dict):
        errors.append(f"invalid JSON Schema for {label}: schema must be an object")
        return
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        errors.append(f"invalid JSON Schema for {label}: expected Draft 2020-12")
    if schema_id == "https://bbk.local/schemas/bbk-role-v4.schema.json":
        _validate_role_shape(instance, label, errors)
    elif schema_id == "https://bbk.local/schemas/bbk-role-catalog-v4.schema.json":
        _validate_catalog_shape(instance, label, errors)
    elif schema_id == "https://bbk.local/schemas/bbk-roles-v4.schema.json":
        _validate_projection_shape(instance, label, errors)
    else:
        errors.append(f"unsupported JSON Schema identity for {label}: {schema_id!r}")


def resolve_catalog_path(
    paths: PackagePaths,
    raw: Any,
    field: str,
    errors: list[str],
) -> Path | None:
    if not isinstance(raw, str) or not raw:
        errors.append(f"catalog {field} must be a non-empty root-relative path")
        return None
    candidate = (paths.root / raw).resolve()
    if not candidate.is_relative_to(paths.root):
        errors.append(f"catalog {field} escapes the package root: {raw!r}")
        return None
    return candidate


def source_record(paths: PackagePaths, path: Path, *, name: str | None = None) -> dict[str, Any]:
    payload = path.read_bytes()
    record: dict[str, Any] = {}
    if name is not None:
        record["name"] = name
    record.update({"path": rel(paths, path), "bytes": len(payload), "sha256": sha256(payload)})
    return record


def mode_pairs(entry: Mapping[str, Any]) -> list[tuple[str, str, str]]:
    result: list[tuple[str, str, str]] = []
    for mode in entry.get("allowed_parent_modes", []):
        if not isinstance(mode, dict):
            continue
        mode_name = mode.get("mode")
        parent_kind = mode.get("parent_kind")
        parents = mode.get("parents") or []
        if isinstance(mode_name, str) and isinstance(parent_kind, str):
            result.extend((mode_name, parent_kind, parent) for parent in parents if isinstance(parent, str))
    return result


def assemble(
    root: Path = DEFAULT_ROOT,
    *,
    require_canonical_sources: bool = True,
) -> AssembledRolePackage:
    paths = PackagePaths.from_root(root)
    errors: list[str] = []

    catalog_schema = load_json(paths, paths.catalog_schema, errors)
    role_schema = load_json(paths, paths.role_schema, errors)
    aggregate_schema = load_json(paths, paths.aggregate_schema, errors)
    catalog = load_json(paths, paths.catalog, errors)
    method_content = load_json(paths, paths.method_content, errors)
    contract_catalog = load_json(paths, paths.contract_catalog, errors)
    try:
        prompt_package = load_prompt_modules(paths.root)
    except PromptModuleError as exc:
        errors.extend(exc.errors)
        prompt_package = None
    if errors:
        raise RolePackageError(errors)
    assert isinstance(catalog_schema, dict)
    assert isinstance(role_schema, dict)
    assert isinstance(aggregate_schema, dict)
    assert isinstance(catalog, dict)
    assert isinstance(method_content, dict)
    assert isinstance(contract_catalog, dict)
    assert prompt_package is not None

    validate_instance(catalog, catalog_schema, rel(paths, paths.catalog), errors)

    expected_catalog_paths = {
        "catalog_schema": "spec/schemas/bbk-role-catalog-v4.schema.json",
        "role_schema": "spec/schemas/bbk-role-v4.schema.json",
        "projection_schema": "spec/schemas/bbk-roles-v4.schema.json",
        "method_content_source": "spec/method-content.json",
        "prompt_module_package": "spec/prompt-modules/catalog.json",
        "contract_package": "spec/contracts/catalog.json",
        "compatibility_projection": "spec/roles.json",
    }
    for field, expected in expected_catalog_paths.items():
        if catalog.get(field) != expected:
            errors.append(f"catalog {field} must equal {expected!r}")
    if prompt_package.catalog.get("package_version") != catalog.get("package_version"):
        errors.append("prompt-module package version must match the split-role catalog")
    if catalog.get("prompt_module_package") != rel(paths, prompt_package.catalog_path):
        errors.append("role catalog must reference the canonical prompt-module package")
    if contract_catalog.get("schema") != "bbk.contract-catalog.v1":
        errors.append("contract package schema must equal bbk.contract-catalog.v1")
    if contract_catalog.get("package_version") != catalog.get("package_version"):
        errors.append("contract package version must match the split-role catalog")
    if contract_catalog.get("source_role_catalog") != "spec/roles/catalog.json":
        errors.append("contract package must reference spec/roles/catalog.json")

    # The split-role catalog is the canonical owner of the role-package version.
    # The repository-wide VERSION file is reconciled during release integration.
    version = str(catalog.get("package_version") or "")

    if require_canonical_sources and paths.catalog.read_bytes() != canonical_bytes(catalog):
        errors.append(f"drift: {rel(paths, paths.catalog)} is not canonically serialized")

    entries = catalog.get("role_entries")
    if not isinstance(entries, list):
        entries = []

    entry_names: list[str] = []
    entry_files: list[str] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        file_name = entry.get("file")
        if isinstance(name, str):
            entry_names.append(name)
        if isinstance(file_name, str):
            entry_files.append(file_name)
        if isinstance(name, str) and isinstance(file_name, str):
            expected = f"spec/roles/{name}-role.json"
            if file_name != expected:
                errors.append(f"catalog role_entries[{index}].file must equal {expected!r}")
    if len(entry_names) != len(set(entry_names)):
        errors.append("catalog role entry names must be unique")
    if len(entry_files) != len(set(entry_files)):
        errors.append("catalog role entry files must be unique")

    discovered = {
        rel(paths, item)
        for item in paths.role_dir.glob("bbk_*-role.json")
        if item.is_file()
    }
    catalogued = set(entry_files)
    missing = sorted(catalogued - discovered)
    extra = sorted(discovered - catalogued)
    if missing:
        errors.append(f"catalogued role files are missing: {missing}")
    if extra:
        errors.append(f"uncatalogued split role files are present: {extra}")

    roles: list[dict[str, Any]] = []
    role_paths: list[Path] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        raw_path = entry.get("file")
        role_path = resolve_catalog_path(paths, raw_path, f"role_entries[{index}].file", errors)
        if role_path is None or not role_path.is_file():
            continue
        role = load_json(paths, role_path, errors)
        if not isinstance(role, dict):
            continue
        role_paths.append(role_path)
        validate_instance(role, role_schema, rel(paths, role_path), errors)
        if role.get("name") != entry.get("name"):
            errors.append(
                f"{rel(paths, role_path)} declares {role.get('name')!r}, "
                f"but catalog entry names {entry.get('name')!r}"
            )
        if require_canonical_sources and role_path.read_bytes() != canonical_bytes(role):
            errors.append(f"drift: {rel(paths, role_path)} is not canonically serialized")
        roles.append(role)

    names = [role.get("name") for role in roles]
    ids = [role.get("id") for role in roles]
    if names != entry_names:
        errors.append("assembled role order must exactly match catalog role_entries order")
    if len(names) != len(set(names)):
        errors.append("role names must be unique")
    if len(ids) != len(set(ids)):
        errors.append("role ids must be unique")

    by_name = {
        role["name"]: role
        for role in roles
        if isinstance(role.get("name"), str)
    }
    entry_by_name = {
        entry["name"]: entry
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("name"), str)
    }
    known_names = set(by_name)
    errors.extend(validate_return_contract_metadata(catalog, roles, entry_by_name))
    method_content_payload = paths.method_content.read_bytes()
    method_skills = method_content.get("skills")
    if method_content.get("schema") != "bbk.method-content.v2":
        errors.append("method-content schema must equal bbk.method-content.v2")
    if method_content.get("version") != version:
        errors.append(
            f"method-content version {method_content.get('version')!r} "
            f"does not match VERSION {version!r}"
        )
    if method_content.get("prompt_module_source") != catalog.get("prompt_module_package"):
        errors.append("method-content prompt_module_source must match the role catalog")
    errors.extend(validate_skill_templates(method_content, prompt_package))
    if not isinstance(method_skills, dict) or not method_skills:
        method_skills = {}
    known_skills = set(method_skills)
    constitution_modules = catalog.get("constitution_modules") or {}

    for role in roles:
        name = role.get("name")
        where = f"role {name!r}"
        role_id = role.get("id")
        if isinstance(role_id, str) and name != f"bbk_{role_id}":
            errors.append(f"{where}: name must equal bbk_<id>")

        modules = role.get("constitution") or []
        if modules and modules[0] != "core":
            errors.append(f"{where}: constitution must begin with core")
        unknown_modules = sorted(set(modules) - set(constitution_modules))
        if unknown_modules:
            errors.append(f"{where}: unknown constitution modules {unknown_modules}")
        if role.get("spawns") and "coordination" not in modules:
            errors.append(f"{where}: roles with direct children require coordination constitution")
        if role.get("mutates") and "execution" not in modules:
            errors.append(f"{where}: mutating roles require execution constitution")
        if role.get("family") == "planning" and "planning" not in modules:
            errors.append(f"{where}: planning roles require planning constitution")
        if role.get("family") == "review" and "assurance" not in modules:
            errors.append(f"{where}: review roles require assurance constitution")

        spawns = role.get("spawns") or []
        delegation = role.get("delegation") or {}
        if set(spawns) != set(delegation):
            errors.append(f"{where}: delegation keys must exactly match spawns")
        unknown_children = sorted(set(spawns) - known_names)
        if unknown_children:
            errors.append(f"{where}: unknown spawned roles {unknown_children}")

        skills = role.get("skills") or []
        primary_skill = role.get("primary_skill")
        mandatory = role.get("mandatory_skills") or []
        unknown_skills = sorted(set(skills) - known_skills)
        if unknown_skills:
            errors.append(f"{where}: unknown skills {unknown_skills}")
        missing_mandatory = sorted(set(mandatory) - set(skills))
        if missing_mandatory:
            errors.append(f"{where}: mandatory skills are not in skills {missing_mandatory}")
        if primary_skill not in skills:
            errors.append(f"{where}: primary_skill must be present in skills")
        if not mandatory or mandatory[0] != primary_skill:
            errors.append(f"{where}: mandatory_skills must begin with primary_skill")
        if "bbk" in skills or "bbk" in mandatory or primary_skill == "bbk":
            errors.append(f"{where}: canonical roles must not load the top-level bbk controller skill")

        role_prompt_modules = role.get("prompt_modules") or []
        known_prompt_modules = set(prompt_package.by_id)
        unknown_prompt_modules = sorted(set(role_prompt_modules) - known_prompt_modules)
        if unknown_prompt_modules:
            errors.append(f"{where}: unknown prompt modules {unknown_prompt_modules}")
        canonical_module_order = [
            module_id for module_id in prompt_package.ordered_ids
            if module_id in set(role_prompt_modules)
        ]
        if role_prompt_modules != canonical_module_order:
            errors.append(f"{where}: prompt_modules must follow catalog order")
        required_by_skills = set(role_skill_module_requirements(role, method_skills))
        missing_required_modules = sorted(required_by_skills - set(role_prompt_modules))
        if missing_required_modules:
            errors.append(
                f"{where}: mandatory procedures require unassigned prompt modules "
                f"{missing_required_modules}"
            )

        policy = prompt_package.catalog["compilation_policy"]
        default_count = policy["mandatory_procedure_default"]
        maximum_count = policy["mandatory_procedure_maximum"]
        exceptions = policy["additional_mandatory_procedure_exceptions"]
        exception = exceptions.get(name)
        if len(mandatory) != default_count:
            if not isinstance(exception, dict):
                errors.append(
                    f"{where}: {len(mandatory)} mandatory procedures require an explicit measured exception"
                )
            else:
                if mandatory != exception.get("mandatory_skills"):
                    errors.append(f"{where}: mandatory procedure list does not match its exception")
                try:
                    expected_measurement = mandatory_procedure_exception_measurement(
                        mandatory, method_skills, prompt_package, method_content_payload,
                    )
                except PromptModuleError as exc:
                    errors.extend(f"{where}: {item}" for item in exc.errors)
                else:
                    if exception.get("measurement") != expected_measurement:
                        errors.append(
                            f"{where}: mandatory-procedure exception measurement is stale or incorrect"
                        )
                distinct_behavior = exception.get("distinct_behavior")
                if not isinstance(distinct_behavior, dict) or set(distinct_behavior) != set(mandatory[1:]):
                    errors.append(
                        f"{where}: mandatory-procedure exception must describe each additional procedure"
                    )
        elif exception is not None:
            errors.append(f"{where}: unnecessary mandatory-procedure exception")
        if maximum_count is not None and len(mandatory) > maximum_count:
            errors.append(f"{where}: mandatory procedure count exceeds configured maximum")

        baseline_modules = {
            "bbk-prompt-role-boundary",
            "bbk-prompt-invocation-binding",
            "bbk-prompt-context-human-relay",
            "bbk-prompt-durable-handoff",
            "bbk-prompt-state-claim-truth",
            "bbk-prompt-proportional-stop",
        }
        missing_baseline = sorted(baseline_modules - set(role_prompt_modules))
        if missing_baseline:
            errors.append(f"{where}: missing baseline prompt modules {missing_baseline}")
        if spawns and "bbk-prompt-delegation-return" not in role_prompt_modules:
            errors.append(f"{where}: coordinating roles require bbk-prompt-delegation-return")
        if role.get("mutates"):
            for required_module in ("bbk-prompt-effects-cleanup", "bbk-prompt-host-capability-truth"):
                if required_module not in role_prompt_modules:
                    errors.append(f"{where}: mutating role requires {required_module}")
        if role.get("family") == "review":
            for required_module in (
                "bbk-prompt-assurance-integrity", "bbk-prompt-evidence-lineage",
                "bbk-prompt-liveness-recovery", "bbk-prompt-effects-cleanup",
            ):
                if required_module not in role_prompt_modules:
                    errors.append(f"{where}: review role requires {required_module}")

    unknown_exception_roles = sorted(
        set(prompt_package.catalog["compilation_policy"]["additional_mandatory_procedure_exceptions"])
        - known_names
    )
    if unknown_exception_roles:
        errors.append(
            f"mandatory-procedure exceptions name unknown roles {unknown_exception_roles}"
        )

    for module_id, expected_roles in EXPECTED_EXCLUSIVE_PROMPT_MODULE_ROLES.items():
        actual_roles = {
            role["name"]
            for role in roles
            if module_id in (role.get("prompt_modules") or [])
        }
        if actual_roles != expected_roles:
            errors.append(
                f"{module_id} role ownership must be exactly {sorted(expected_roles)}; "
                f"got {sorted(actual_roles)}"
            )

    # Parent-mode contracts and parent spawn declarations must agree in both directions.
    admitted_edges: dict[tuple[str, str], str] = {}
    controller_modes: set[tuple[str, str]] = set()
    for child, entry in entry_by_name.items():
        seen_parents: set[str] = set()
        seen_mode_kind: set[tuple[str, str]] = set()
        for mode, parent_kind, parent in mode_pairs(entry):
            mode_kind = (mode, parent_kind)
            if mode_kind in seen_mode_kind and parent in seen_parents:
                errors.append(f"{child}: duplicate parent-mode declaration {mode_kind} for {parent}")
            seen_mode_kind.add(mode_kind)
            if parent in seen_parents:
                errors.append(f"{child}: parent {parent} appears in more than one allowed parent mode")
            seen_parents.add(parent)
            if parent_kind == "controller":
                if parent != "harness_root_controller":
                    errors.append(f"{child}: controller parent mode may name only harness_root_controller")
                controller_modes.add((child, mode))
                continue
            if parent_kind != "canonical_role":
                errors.append(f"{child}: unknown parent_kind {parent_kind!r}")
                continue
            if parent not in known_names:
                errors.append(f"{child}: allowed parent mode names unknown canonical role {parent!r}")
                continue
            if parent == child and not (
                child == "bbk_territory_wayfinder" and mode == "TERRITORY_RECURSION"
            ):
                errors.append(f"{child}: same-role parent is allowed only for TERRITORY_RECURSION")
            edge = (parent, child)
            if edge in admitted_edges:
                errors.append(
                    f"canonical parent edge {parent} -> {child} is admitted more than once "
                    f"({admitted_edges[edge]} and {mode})"
                )
            admitted_edges[edge] = mode
            parent_role = by_name[parent]
            if child not in (parent_role.get("spawns") or []):
                errors.append(
                    f"child contract admits {parent} -> {child} via {mode}, "
                    "but the parent does not declare that direct child"
                )

    spawn_edges = {
        (parent, child)
        for parent, role in by_name.items()
        for child in role.get("spawns") or []
    }
    missing_child_contract = sorted(spawn_edges - set(admitted_edges))
    missing_parent_contract = sorted(set(admitted_edges) - spawn_edges)
    if missing_child_contract:
        errors.append(f"spawn edges missing from child allowed-parent contracts: {missing_child_contract}")
    if missing_parent_contract:
        errors.append(f"allowed-parent edges missing from parent spawns: {missing_parent_contract}")

    # A recursive Territory Wayfinder subdivision is the only intentional cycle.
    graph = {name: set(role.get("spawns") or []) for name, role in by_name.items()}
    graph.get("bbk_territory_wayfinder", set()).discard("bbk_territory_wayfinder")
    visiting: list[str] = []
    visiting_set: set[str] = set()
    visited: set[str] = set()
    reported_cycles: set[tuple[str, ...]] = set()

    def visit(node: str) -> None:
        if node in visited:
            return
        if node in visiting_set:
            start = visiting.index(node)
            cycle = tuple(visiting[start:] + [node])
            if cycle not in reported_cycles:
                reported_cycles.add(cycle)
                errors.append(
                    "unintended canonical-role delegation cycle: " + " -> ".join(cycle)
                )
            return
        visiting.append(node)
        visiting_set.add(node)
        for child in sorted(graph.get(node, set())):
            if child in graph:
                visit(child)
        visiting.pop()
        visiting_set.remove(node)
        visited.add(node)

    for role_name in sorted(graph):
        visit(role_name)

    # Where a role-level return contract names its invocation context or parent,
    # it must agree exactly with the catalog-owned topology.
    for role_name, entry in entry_by_name.items():
        role = by_name.get(role_name) or {}
        contract = role.get("return_contract") or {}
        mode_names = {
            mode.get("mode")
            for mode in entry.get("allowed_parent_modes", [])
            if isinstance(mode, dict) and isinstance(mode.get("mode"), str)
        }
        canonical_parents = {
            parent
            for mode in entry.get("allowed_parent_modes", [])
            if isinstance(mode, dict) and mode.get("parent_kind") == "canonical_role"
            for parent in mode.get("parents", [])
            if isinstance(parent, str)
        }
        if set(contract.get("allowed_invocation_modes") or []) != mode_names:
            errors.append(
                f"{role_name} allowed_invocation_modes must exactly match its catalog parent-mode names"
            )

    entrypoints = catalog.get("controller_entrypoints") or []
    actual_entrypoints = tuple(
        (item.get("route"), item.get("role"), item.get("invocation_mode"))
        for item in entrypoints
        if isinstance(item, dict)
    )
    if actual_entrypoints != EXPECTED_CONTROLLER_ENTRYPOINTS:
        errors.append(
            f"controller entrypoints must be exactly {EXPECTED_CONTROLLER_ENTRYPOINTS!r}; "
            f"got {actual_entrypoints!r}"
        )
    expected_controller_modes = {(role, mode) for _, role, mode in EXPECTED_CONTROLLER_ENTRYPOINTS}
    if controller_modes != expected_controller_modes:
        errors.append(
            "controller parent modes must exactly match controller entrypoints; "
            f"got {sorted(controller_modes)}"
        )

    topology = catalog.get("interaction_topology") or {}
    originators = tuple(topology.get("human_request_originators") or [])
    if originators != EXPECTED_HUMAN_REQUEST_ORIGINATORS:
        errors.append(
            f"human request originators must be exactly {EXPECTED_HUMAN_REQUEST_ORIGINATORS!r}"
        )
    trigger_roles = {
        name for name, role in by_name.items() if role.get("human_decision_triggers")
    }
    if trigger_roles != set(EXPECTED_HUMAN_REQUEST_ORIGINATORS):
        errors.append(
            "roles with human_decision_triggers must exactly match the catalog originators; "
            f"got {sorted(trigger_roles)}"
        )
    if topology.get("user_facing_identity") != "harness_root_controller":
        errors.append("the sole user-facing identity must remain harness_root_controller")
    if topology.get("canonical_roles_user_facing") is not False:
        errors.append("canonical roles must remain non-user-facing")

    # Mode-specific role contracts whose behavior changes by parent context.
    worker_modes = {
        mode: set(mode_entry.get("parents") or [])
        for mode_entry in entry_by_name.get("bbk_worker", {}).get("allowed_parent_modes", [])
        if isinstance(mode_entry, dict)
        for mode in [mode_entry.get("mode")]
        if isinstance(mode, str)
    }
    expected_worker_modes = {
        "CANDIDATE_PRODUCTION": {"bbk_worker_orchestrator"},
        "PROTOTYPE_SUPPORT": {"bbk_prototyper"},
    }
    if worker_modes != expected_worker_modes:
        errors.append(f"bbk_worker parent modes must equal {expected_worker_modes!r}")
    validator_orchestrator_modes = {
        mode_entry.get("mode"): set(mode_entry.get("parents") or [])
        for mode_entry in entry_by_name.get("bbk_validator_orchestrator", {}).get(
            "allowed_parent_modes", []
        )
        if isinstance(mode_entry, dict)
    }
    expected_validator_orchestrator_modes = {
        "TERRITORY_BOUND": {"bbk_territory_orchestrator"},
        "CONTROLLER_ROOT": {"harness_root_controller"},
    }
    if validator_orchestrator_modes != expected_validator_orchestrator_modes:
        errors.append(
            "bbk_validator_orchestrator must support exactly TERRITORY_BOUND and CONTROLLER_ROOT"
        )

    reviewer_pairs = set(mode_pairs(entry_by_name.get("bbk_reviewer", {})))
    expected_reviewer_pairs = {
        ("DIRECT_BOUNDED_REVIEW", "controller", "harness_root_controller"),
        ("DIRECT_BOUNDED_REVIEW", "canonical_role", "bbk_root_wayfinder"),
        ("DIRECT_BOUNDED_REVIEW", "canonical_role", "bbk_territory_wayfinder"),
        ("DIRECT_BOUNDED_REVIEW", "canonical_role", "bbk_planning_wayfinder"),
        ("DIRECT_BOUNDED_REVIEW", "canonical_role", "bbk_phase_wayfinder"),
        ("DIRECT_BOUNDED_REVIEW", "canonical_role", "bbk_root_orchestrator"),
        ("DIRECT_BOUNDED_REVIEW", "canonical_role", "bbk_territory_orchestrator"),
        ("MANIFEST_ATTEMPT", "canonical_role", "bbk_validator_orchestrator"),
    }
    if reviewer_pairs != expected_reviewer_pairs:
        errors.append("bbk_reviewer parent modes do not match direct-review and manifest-attempt ownership")

    # Preserve the corrected direct-child topology from Gate 1.
    prototyper = by_name.get("bbk_prototyper") or {}
    if set(prototyper.get("spawns") or []) != {"bbk_worker_designer", "bbk_worker"}:
        errors.append("bbk_prototyper must have exactly Worker Designer and Worker as direct child types")
    questioning = by_name.get("bbk_questioning_wayfinder") or {}
    if "bbk_question_guide" not in (questioning.get("spawns") or []):
        errors.append("bbk_questioning_wayfinder must spawn bbk_question_guide")
    for parent_name in ("bbk_root_wayfinder", "bbk_territory_wayfinder"):
        parent = by_name.get(parent_name) or {}
        if "bbk_questioning_wayfinder" not in (parent.get("spawns") or []):
            errors.append(f"{parent_name} must route material decisions through bbk_questioning_wayfinder")
        if "bbk_planning_wayfinder" not in (parent.get("spawns") or []):
            errors.append(f"{parent_name} must be able to invoke bbk_planning_wayfinder")
        if "bbk_question_guide" in (parent.get("spawns") or []):
            errors.append(f"{parent_name} must not bypass bbk_questioning_wayfinder")
    if "bbk_phase_wayfinder" not in ((by_name.get("bbk_planning_wayfinder") or {}).get("spawns") or []):
        errors.append("bbk_planning_wayfinder must spawn bbk_phase_wayfinder")

    required_primary_skills = {
        "bbk_root_wayfinder": "bbk-wayfind",
        "bbk_territory_wayfinder": "bbk-wayfind",
        "bbk_questioning_wayfinder": "bbk-question-branch",
        "bbk_question_guide": "bbk-grill",
        "bbk_planning_wayfinder": "bbk-work-graph",
        "bbk_phase_wayfinder": "bbk-phase-plan",
    }
    for role_name, skill in required_primary_skills.items():
        if (by_name.get(role_name) or {}).get("primary_skill") != skill:
            errors.append(f"{role_name} must declare {skill} as its primary procedure")

    roots = [role for _, role, _ in EXPECTED_CONTROLLER_ENTRYPOINTS]
    reachable: set[str] = set()
    stack = list(roots)
    while stack:
        current = stack.pop()
        if current in reachable or current not in by_name:
            continue
        reachable.add(current)
        stack.extend(by_name[current].get("spawns") or [])
    unreachable = sorted(known_names - reachable)
    if unreachable:
        errors.append(f"roles unreachable from the four controller entrypoints: {unreachable}")

    if errors:
        raise RolePackageError(errors)

    projection = {
        "schema_version": catalog["schema_version"],
        "package_version": catalog["package_version"],
        "projection_schema": catalog["projection_schema"],
        "source_catalog": "spec/roles/catalog.json",
        "prompt_module_package": catalog["prompt_module_package"],
        "contract_package": catalog["contract_package"],
        "source_manifest": {
            "catalog": source_record(paths, paths.catalog),
            "roles": [
                source_record(paths, role_path, name=entry["name"])
                for entry, role_path in zip(entries, role_paths, strict=True)
            ],
            "prompt_modules": prompt_module_source_manifest(prompt_package)["sources"],
        },
        "constitution_modules": catalog["constitution_modules"],
        "interaction_topology": catalog["interaction_topology"],
        "controller_entrypoints": catalog["controller_entrypoints"],
        "role_entries": catalog["role_entries"],
        "roles": roles,
    }

    validate_instance(
        projection,
        aggregate_schema,
        rel(paths, paths.projection),
        errors,
    )
    if errors:
        raise RolePackageError(errors)

    return AssembledRolePackage(
        paths=paths,
        catalog=catalog,
        roles=tuple(roles),
        projection=projection,
        canonical_sources=(
            paths.catalog,
            *role_paths,
            prompt_package.catalog_path,
            *[
                paths.root / entry["file"]
                for entry in prompt_package.catalog["module_entries"]
            ],
        ),
    )


def projection_drift(package: AssembledRolePackage) -> list[str]:
    path = package.paths.projection
    if not path.is_file():
        return [f"drift: missing compatibility projection {rel(package.paths, path)}"]
    if path.read_bytes() != canonical_bytes(package.projection):
        return [
            f"drift: {rel(package.paths, path)} does not match the canonical split-role sources"
        ]
    return []


def print_errors(errors: Sequence[str]) -> None:
    print("BBK split-role package errors:", file=sys.stderr)
    for error in errors:
        print(f"- {error}", file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail on source or projection drift")
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)

    try:
        package = assemble(args.root, require_canonical_sources=True)
    except RolePackageError as exc:
        print_errors(exc.errors)
        return 1

    if args.check:
        drift = projection_drift(package)
        if drift:
            print_errors(drift)
            return 1
        print(
            f"OK: {len(package.roles)} canonical split roles validated; "
            f"{rel(package.paths, package.paths.projection)} matches "
            f"{rel(package.paths, package.paths.catalog)}"
        )
        return 0

    package.paths.projection.write_bytes(canonical_bytes(package.projection))
    print(
        f"assembled {len(package.roles)} split roles into "
        f"{rel(package.paths, package.paths.projection)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
