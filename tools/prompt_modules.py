#!/usr/bin/env python3
"""Load, validate, and compile BBK prompt modules and skill templates.

Prompt modules are small canonical behavior capsules shared by role prompts and
standalone generated skills.  Canonical skill templates may reference a module
with ``{{bbk-module:<module-id>}}``.  Standalone ``SKILL.md`` projections expand
those directives, while role prompts embed each assigned module once and retain
only compact references inside inlined primary procedures.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
MODULE_ID_RE = re.compile(r"^bbk-prompt-[a-z0-9]+(?:-[a-z0-9]+)*$")
CLAUSE_ID_RE = re.compile(r"^[A-Z][A-Z0-9_]*(?:\.[A-Z][A-Z0-9_]*)+$")
DIRECTIVE_RE = re.compile(r"\{\{bbk-module:(bbk-prompt-[a-z0-9]+(?:-[a-z0-9]+)*)\}\}")
SKILL_NAME_RE = re.compile(r"^bbk(?:-[a-z0-9]+)+$")


class PromptModuleError(RuntimeError):
    """Raised when prompt-module or skill-template sources are invalid."""

    def __init__(self, errors: Sequence[str]):
        self.errors = list(errors)
        super().__init__("\n".join(self.errors))


@dataclass(frozen=True)
class PromptModulePackage:
    root: Path
    catalog_path: Path
    catalog: dict[str, Any]
    modules: tuple[dict[str, Any], ...]
    by_id: Mapping[str, dict[str, Any]]

    @property
    def ordered_ids(self) -> tuple[str, ...]:
        return tuple(module["id"] for module in self.modules)


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def strip_frontmatter(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if normalized.startswith("---\n"):
        end = normalized.find("\n---\n", 4)
        if end < 0:
            raise PromptModuleError(["skill template contains unterminated YAML frontmatter"])
        normalized = normalized[end + 5 :]
    return normalized.strip()


def _load_json(path: Path, errors: list[str]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        errors.append(f"cannot read {path}: {exc}")
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON in {path} at {exc.lineno}:{exc.colno}: {exc.msg}")
    return None


def load_prompt_modules(root: Path = DEFAULT_ROOT) -> PromptModulePackage:
    root = root.resolve()
    catalog_path = root / "spec" / "prompt-modules" / "catalog.json"
    errors: list[str] = []
    catalog = _load_json(catalog_path, errors)
    if not isinstance(catalog, dict):
        raise PromptModuleError(errors or ["prompt-module catalog must be an object"])

    expected_catalog_keys = {
        "schema_version", "package_version", "module_schema", "catalog_schema",
        "module_entries", "compilation_policy",
    }
    missing = sorted(expected_catalog_keys - set(catalog))
    extra = sorted(set(catalog) - expected_catalog_keys)
    if missing:
        errors.append(f"prompt-module catalog missing fields {missing}")
    if extra:
        errors.append(f"prompt-module catalog has unexpected fields {extra}")
    if catalog.get("schema_version") != "bbk.prompt-modules.v1":
        errors.append("prompt-module catalog schema_version must be bbk.prompt-modules.v1")
    if catalog.get("module_schema") != "spec/schemas/bbk-prompt-module-v1.schema.json":
        errors.append("prompt-module catalog module_schema is not canonical")
    if catalog.get("catalog_schema") != "spec/schemas/bbk-prompt-module-catalog-v1.schema.json":
        errors.append("prompt-module catalog catalog_schema is not canonical")

    policy = catalog.get("compilation_policy")
    if not isinstance(policy, dict):
        errors.append("prompt-module compilation_policy must be an object")
        policy = {}
    expected_policy = {
        "role_field", "skill_directive_syntax", "embed_each_module_once",
        "standalone_skill_expands_modules", "role_prompt_uses_compact_skill_references",
        "mandatory_procedure_default", "mandatory_procedure_maximum",
        "additional_mandatory_procedure_rule", "additional_mandatory_procedure_exceptions",
    }
    if set(policy) != expected_policy:
        errors.append("prompt-module compilation_policy fields are malformed")
    if policy.get("role_field") != "prompt_modules":
        errors.append("prompt-module role_field must be prompt_modules")
    if policy.get("skill_directive_syntax") != "{{bbk-module:<module-id>}}":
        errors.append("prompt-module directive syntax is not canonical")
    for key in (
        "embed_each_module_once", "standalone_skill_expands_modules",
        "role_prompt_uses_compact_skill_references",
    ):
        if policy.get(key) is not True:
            errors.append(f"prompt-module policy {key} must be true")
    default_count = policy.get("mandatory_procedure_default")
    if not isinstance(default_count, int) or isinstance(default_count, bool) or default_count < 1:
        errors.append("mandatory_procedure_default must be a positive integer")
    max_count = policy.get("mandatory_procedure_maximum")
    if max_count is not None and (
        not isinstance(max_count, int) or isinstance(max_count, bool) or max_count < 1
    ):
        errors.append("mandatory_procedure_maximum must be null or a positive integer")
    if not isinstance(policy.get("additional_mandatory_procedure_rule"), str) or not policy.get("additional_mandatory_procedure_rule", "").strip():
        errors.append("additional_mandatory_procedure_rule must be non-empty")
    exceptions = policy.get("additional_mandatory_procedure_exceptions")
    if not isinstance(exceptions, dict):
        errors.append("additional_mandatory_procedure_exceptions must be an object")
        exceptions = {}

    entries = catalog.get("module_entries")
    if not isinstance(entries, list) or not entries:
        errors.append("prompt-module catalog module_entries must be a non-empty array")
        entries = []

    modules: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_files: set[str] = set()
    seen_clause_ids: set[str] = set()
    for index, entry in enumerate(entries):
        label = f"module_entries[{index}]"
        if not isinstance(entry, dict) or set(entry) != {"id", "file"}:
            errors.append(f"{label} must contain exactly id and file")
            continue
        module_id = entry.get("id")
        file_name = entry.get("file")
        if not isinstance(module_id, str) or not MODULE_ID_RE.fullmatch(module_id):
            errors.append(f"{label}.id is invalid")
            continue
        expected_file = f"spec/prompt-modules/{module_id}.json"
        if file_name != expected_file:
            errors.append(f"{label}.file must equal {expected_file}")
            continue
        if module_id in seen_ids:
            errors.append(f"duplicate prompt-module id {module_id}")
        if file_name in seen_files:
            errors.append(f"duplicate prompt-module file {file_name}")
        seen_ids.add(module_id)
        seen_files.add(file_name)
        path = root / file_name
        module = _load_json(path, errors)
        if not isinstance(module, dict):
            continue
        expected_module_keys = {"schema_version", "id", "title", "description", "clauses"}
        if set(module) != expected_module_keys:
            errors.append(f"{file_name}: module fields are malformed")
        if module.get("schema_version") != "bbk.prompt-module.v1":
            errors.append(f"{file_name}: schema_version must be bbk.prompt-module.v1")
        if module.get("id") != module_id:
            errors.append(f"{file_name}: module id does not match catalog entry")
        for key in ("title", "description"):
            if not isinstance(module.get(key), str) or not module.get(key, "").strip():
                errors.append(f"{file_name}: {key} must be non-empty")
        clauses = module.get("clauses")
        if not isinstance(clauses, list) or not clauses:
            errors.append(f"{file_name}: clauses must be a non-empty array")
            clauses = []
        local_clause_ids: set[str] = set()
        for clause_index, clause in enumerate(clauses):
            where = f"{file_name}/clauses/{clause_index}"
            if not isinstance(clause, dict) or set(clause) != {"id", "text"}:
                errors.append(f"{where}: clause must contain exactly id and text")
                continue
            clause_id = clause.get("id")
            if not isinstance(clause_id, str) or not CLAUSE_ID_RE.fullmatch(clause_id):
                errors.append(f"{where}: invalid clause id")
            elif clause_id in local_clause_ids or clause_id in seen_clause_ids:
                errors.append(f"{where}: duplicate clause id {clause_id}")
            else:
                local_clause_ids.add(clause_id)
                seen_clause_ids.add(clause_id)
            if not isinstance(clause.get("text"), str) or not clause.get("text", "").strip():
                errors.append(f"{where}: clause text must be non-empty")
        raw = path.read_bytes() if path.is_file() else b""
        if raw and raw != canonical_bytes(module):
            errors.append(f"{file_name}: prompt-module source is not canonically serialized")
        modules.append(module)

    expected_paths = {root / value for value in seen_files}
    actual_paths = set((root / "spec" / "prompt-modules").glob("bbk-prompt-*.json"))
    unexpected = sorted(path.relative_to(root).as_posix() for path in actual_paths - expected_paths)
    missing_paths = sorted(path.relative_to(root).as_posix() for path in expected_paths - actual_paths)
    if unexpected:
        errors.append(f"uncatalogued prompt-module files {unexpected}")
    if missing_paths:
        errors.append(f"missing prompt-module files {missing_paths}")

    measurement_basis = "UTF8_BYTES_OF_FRONTMATTER_STRIPPED_COMPACT_PROCEDURE_BODIES_JOINED_BY_TWO_LF"
    for role_name, exception in exceptions.items():
        if not isinstance(role_name, str) or not role_name.startswith("bbk_"):
            errors.append(f"invalid mandatory-procedure exception role {role_name!r}")
            continue
        expected_exception_keys = {
            "mandatory_skills", "distinct_behavior", "measurement", "rationale",
        }
        if not isinstance(exception, dict) or set(exception) != expected_exception_keys:
            errors.append(f"mandatory-procedure exception {role_name} is malformed")
            continue
        skills = exception.get("mandatory_skills")
        if not isinstance(skills, list) or len(skills) < 2 or len(skills) != len(set(skills)) or not all(isinstance(name, str) and SKILL_NAME_RE.fullmatch(name) for name in skills):
            errors.append(f"mandatory-procedure exception {role_name} has invalid mandatory_skills")
            skills = []
        distinct_behavior = exception.get("distinct_behavior")
        expected_distinct = set(skills[1:]) if skills else set()
        if not isinstance(distinct_behavior, dict) or set(distinct_behavior) != expected_distinct:
            errors.append(
                f"mandatory-procedure exception {role_name} distinct_behavior must name "
                "every additional procedure exactly once"
            )
        elif any(not isinstance(value, str) or not value.strip() for value in distinct_behavior.values()):
            errors.append(f"mandatory-procedure exception {role_name} has empty distinct behavior")
        measurement = exception.get("measurement")
        expected_measurement_keys = {
            "basis", "method_content_sha256", "primary_body_bytes",
            "all_mandatory_body_bytes", "incremental_body_bytes",
            "duplicated_prompt_module_bodies",
        }
        if not isinstance(measurement, dict) or set(measurement) != expected_measurement_keys:
            errors.append(f"mandatory-procedure exception {role_name} measurement is malformed")
        else:
            if measurement.get("basis") != measurement_basis:
                errors.append(f"mandatory-procedure exception {role_name} measurement basis is invalid")
            digest = measurement.get("method_content_sha256")
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                errors.append(f"mandatory-procedure exception {role_name} method-content digest is invalid")
            primary_bytes = measurement.get("primary_body_bytes")
            all_bytes = measurement.get("all_mandatory_body_bytes")
            incremental_bytes = measurement.get("incremental_body_bytes")
            if any(not isinstance(value, int) or isinstance(value, bool) or value < 1 for value in (primary_bytes, all_bytes, incremental_bytes)):
                errors.append(f"mandatory-procedure exception {role_name} byte measurements must be positive integers")
            elif all_bytes - primary_bytes != incremental_bytes:
                errors.append(f"mandatory-procedure exception {role_name} byte measurements are inconsistent")
            if measurement.get("duplicated_prompt_module_bodies") != 0:
                errors.append(f"mandatory-procedure exception {role_name} duplicates prompt-module bodies")
        if not isinstance(exception.get("rationale"), str) or not exception.get("rationale", "").strip():
            errors.append(f"mandatory-procedure exception {role_name} has no rationale")

    if catalog_path.is_file() and catalog_path.read_bytes() != canonical_bytes(catalog):
        errors.append("spec/prompt-modules/catalog.json is not canonically serialized")
    if errors:
        raise PromptModuleError(errors)
    by_id = {module["id"]: module for module in modules}
    return PromptModulePackage(
        root=root,
        catalog_path=catalog_path,
        catalog=catalog,
        modules=tuple(modules),
        by_id=by_id,
    )


def module_directives(text: str) -> tuple[str, ...]:
    """Return module IDs in first-occurrence order."""
    found: list[str] = []
    for match in DIRECTIVE_RE.finditer(text):
        module_id = match.group(1)
        if module_id not in found:
            found.append(module_id)
    return tuple(found)


def validate_skill_templates(
    method_content: Mapping[str, Any],
    package: PromptModulePackage,
) -> list[str]:
    errors: list[str] = []
    if method_content.get("schema") != "bbk.method-content.v2":
        errors.append("method-content schema must be bbk.method-content.v2")
    if method_content.get("prompt_module_source") != "spec/prompt-modules/catalog.json":
        errors.append("method-content prompt_module_source is not canonical")
    skills = method_content.get("skills")
    if not isinstance(skills, dict) or not skills:
        errors.append("method-content skills must be a non-empty object")
        return errors
    known = set(package.by_id)
    for name, template in skills.items():
        if name != "bbk" and (not isinstance(name, str) or not SKILL_NAME_RE.fullmatch(name)):
            errors.append(f"method-content contains invalid skill name {name!r}")
        if not isinstance(template, str) or not template.strip():
            errors.append(f"method-content skill {name!r} must have a non-empty string template")
            continue
        directives = module_directives(template)
        unknown = sorted(set(directives) - known)
        if unknown:
            errors.append(f"method-content skill {name!r} references unknown prompt modules {unknown}")
        residue = DIRECTIVE_RE.sub("", template)
        if "{{bbk-module:" in residue:
            errors.append(f"method-content skill {name!r} contains a malformed prompt-module directive")
    return errors


def render_module(module: Mapping[str, Any], *, tagged: bool = False) -> str:
    lines = [f"### {module['title']}", "", module["description"], ""]
    lines.extend(f"- `{clause['id']}` — {clause['text']}" for clause in module["clauses"])
    body = "\n".join(lines).strip()
    if tagged:
        return (
            f'<bbk-prompt-module id="{module["id"]}">\n'
            f"{body}\n"
            "</bbk-prompt-module>"
        )
    return body


def expand_skill_template(template: str, package: PromptModulePackage) -> str:
    """Expand each referenced module once for a standalone generated SKILL.md."""
    emitted: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        module_id = match.group(1)
        module = package.by_id.get(module_id)
        if module is None:
            raise PromptModuleError([f"unknown prompt module {module_id}"])
        if module_id in emitted:
            return f"> Continue to apply the `{module_id}` module expanded above."
        emitted.add(module_id)
        return (
            f"<!-- BBK prompt module {module_id}: expanded from canonical source -->\n\n"
            f"{render_module(module)}\n\n"
            f"<!-- End BBK prompt module {module_id} -->"
        )

    expanded = DIRECTIVE_RE.sub(replace, template)
    if "{{bbk-module:" in expanded:
        raise PromptModuleError(["expanded skill contains unresolved prompt-module directive"])
    return expanded


def compact_skill_template(template: str, package: PromptModulePackage) -> str:
    """Replace module directives with compact references for a role prompt."""
    def replace(match: re.Match[str]) -> str:
        module_id = match.group(1)
        module = package.by_id.get(module_id)
        if module is None:
            raise PromptModuleError([f"unknown prompt module {module_id}"])
        return f"> Apply the already embedded `{module_id}` module here."

    compact = DIRECTIVE_RE.sub(replace, template)
    if "{{bbk-module:" in compact:
        raise PromptModuleError(["compact skill contains unresolved prompt-module directive"])
    return compact


def ordered_modules(
    package: PromptModulePackage,
    module_ids: Iterable[str],
) -> tuple[dict[str, Any], ...]:
    requested = list(module_ids)
    if len(requested) != len(set(requested)):
        raise PromptModuleError(["role prompt_modules contains duplicate IDs"])
    unknown = sorted(set(requested) - set(package.by_id))
    if unknown:
        raise PromptModuleError([f"unknown role prompt modules {unknown}"])
    requested_set = set(requested)
    return tuple(module for module in package.modules if module["id"] in requested_set)


def role_skill_module_requirements(
    role: Mapping[str, Any],
    skill_templates: Mapping[str, str],
) -> tuple[str, ...]:
    found: list[str] = []
    for skill_name in role.get("mandatory_skills", []):
        template = skill_templates.get(skill_name)
        if not isinstance(template, str):
            continue
        for module_id in module_directives(template):
            if module_id not in found:
                found.append(module_id)
    return tuple(found)


MANDATORY_PROCEDURE_MEASUREMENT_BASIS = (
    "UTF8_BYTES_OF_FRONTMATTER_STRIPPED_COMPACT_PROCEDURE_BODIES_JOINED_BY_TWO_LF"
)


def compact_procedure_body_bytes(
    skill_names: Sequence[str],
    skill_templates: Mapping[str, str],
    package: PromptModulePackage,
) -> int:
    """Measure the exact compact procedure bodies used by exception policy.

    This excludes host-specific wrappers.  Each canonical body is stripped of
    YAML frontmatter, module directives are replaced by compact references, and
    bodies are joined by exactly two LF characters before UTF-8 measurement.
    """
    bodies: list[str] = []
    for skill_name in skill_names:
        template = skill_templates.get(skill_name)
        if not isinstance(template, str):
            raise PromptModuleError([f"unknown mandatory procedure {skill_name}"])
        bodies.append(strip_frontmatter(compact_skill_template(template, package)))
    return len("\n\n".join(bodies).encode("utf-8"))


def mandatory_procedure_exception_measurement(
    mandatory_skills: Sequence[str],
    skill_templates: Mapping[str, str],
    package: PromptModulePackage,
    method_content_payload: bytes,
) -> dict[str, Any]:
    """Return the deterministic measurement record for a procedure exception."""
    if len(mandatory_skills) < 2:
        raise PromptModuleError(["a measured exception requires at least two procedures"])
    primary_bytes = compact_procedure_body_bytes(
        mandatory_skills[:1], skill_templates, package,
    )
    all_bytes = compact_procedure_body_bytes(
        mandatory_skills, skill_templates, package,
    )
    return {
        "basis": MANDATORY_PROCEDURE_MEASUREMENT_BASIS,
        "method_content_sha256": sha256_bytes(method_content_payload),
        "primary_body_bytes": primary_bytes,
        "all_mandatory_body_bytes": all_bytes,
        "incremental_body_bytes": all_bytes - primary_bytes,
        "duplicated_prompt_module_bodies": 0,
    }


def source_manifest(package: PromptModulePackage) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for path in [package.catalog_path, *[package.root / entry["file"] for entry in package.catalog["module_entries"]]]:
        payload = path.read_bytes()
        records.append({
            "path": path.relative_to(package.root).as_posix(),
            "bytes": len(payload),
            "sha256": sha256_bytes(payload),
        })
    return {
        "schema_version": package.catalog["schema_version"],
        "package_version": package.catalog["package_version"],
        "sources": records,
    }
