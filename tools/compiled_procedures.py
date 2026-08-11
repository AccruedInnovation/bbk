#!/usr/bin/env python3
"""Host-neutral BBK prompt/procedure compiler and logical-child reuse state.

Canonical procedure sources live under ``shared/skills`` and are backed by
``spec/method-content.json``.  Required role, controller, profile, invocation,
and transitive dependency procedures are selected once, compiled once, removed
from the effective external catalog, and preserved for unchanged follow-ups.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from prompt_modules import clauses_for_harness, compact_skill_template, load_prompt_modules, ordered_modules, strip_frontmatter, validate_skill_templates
except ModuleNotFoundError:  # pragma: no cover
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from prompt_modules import clauses_for_harness, compact_skill_template, load_prompt_modules, ordered_modules, strip_frontmatter, validate_skill_templates

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "spec" / "procedures" / "catalog.json"
DEPENDENCY_PATH = ROOT / "spec" / "procedures" / "dependencies.json"
CONTROLLER_PATH = ROOT / "spec" / "controllers" / "bbk_controller.json"
COMPILER_ID = "bbk.compiled-procedure-compiler"
COMPILER_VERSION = "2"
FOLLOWUP_TRIGGERS = [
    "SOURCE_DIGEST_CHANGED", "DEPENDENCY_DIGEST_CHANGED", "COMPILER_CHANGED",
    "SELECTION_CHANGED", "PROFILE_SELECTION_CHANGED", "INVOCATION_SELECTION_CHANGED",
    "HARNESS_PROJECTION_CHANGED", "BASE_PROMPT_CHANGED", "RETURN_CONTRACT_CHANGED",
    "MODEL_ROUTE_CHANGED", "TOOL_CAPABILITY_CHANGED", "ADAPTER_TEMPLATE_CHANGED",
    "EXTERNAL_CATALOG_CHANGED", "INVOCATION_POLICY_CHANGED", "PROCEDURE_REMOVED",
]
HARNESS_IDS = {"codex": "CODEX", "omp": "OMP", "claude": "CLAUDE", "pi": "PI", "generic": "PI"}


class CompiledProcedureError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def compact_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompiledProcedureError("BBK-CP-008", f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CompiledProcedureError("BBK-CP-008", f"{path} must contain a JSON object")
    return value


def _package_version(root: Path) -> str:
    return (root / "VERSION").read_text(encoding="utf-8").strip()


def _method_content(root: Path, prompt_package: Any | None = None) -> dict[str, Any]:
    value = _load_json(root / "spec" / "method-content.json")
    package = prompt_package if prompt_package is not None else load_prompt_modules(root)
    errors = validate_skill_templates(value, package)
    if errors:
        raise CompiledProcedureError("BBK-CP-008", "; ".join(errors))
    return value


def _dependency_map(root: Path, known: set[str]) -> dict[str, list[str]]:
    payload = _load_json(root / "spec" / "procedures" / "dependencies.json")
    raw = payload.get("dependencies")
    if not isinstance(raw, dict):
        raise CompiledProcedureError("BBK-CP-008", "procedure dependency map is missing")
    result: dict[str, list[str]] = {item: [] for item in known}
    for procedure, values in raw.items():
        if procedure not in known:
            raise CompiledProcedureError("BBK-CP-008", f"dependency owner is unknown: {procedure}")
        if not isinstance(values, list) or len(values) != len(set(values)) or not all(isinstance(x, str) for x in values):
            raise CompiledProcedureError("BBK-CP-008", f"invalid dependencies for {procedure}")
        missing = sorted(set(values) - known)
        if missing:
            raise CompiledProcedureError("BBK-CP-008", f"unresolved dependencies for {procedure}: {missing}")
        result[procedure] = list(values)
    # Validate the complete graph now so every later selection is safe.
    visiting: list[str] = []
    visited: set[str] = set()
    def visit(item: str) -> None:
        if item in visiting:
            start = visiting.index(item)
            raise CompiledProcedureError("BBK-CP-003", "procedure dependency cycle: " + " -> ".join(visiting[start:] + [item]))
        if item in visited:
            return
        visiting.append(item)
        for dep in result[item]:
            visit(dep)
        visiting.pop(); visited.add(item)
    for item in sorted(known):
        visit(item)
    return result


def _identity_spec(name: str, primary: str, required: Sequence[str], available: Sequence[str]) -> dict[str, Any]:
    required_unique = list(dict.fromkeys(str(x) for x in required))
    if primary not in required_unique:
        required_unique.insert(0, primary)
    return {
        "name": name,
        "primary": primary,
        "required": required_unique,
        "optional": [str(x) for x in available if str(x) not in set(required_unique)],
        "available": list(dict.fromkeys(str(x) for x in available)),
    }


def build_registry(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    method_path = root / "spec" / "method-content.json"
    role_catalog_path = root / "spec" / "roles" / "catalog.json"
    method = _method_content(root)
    role_catalog = _load_json(role_catalog_path)
    skills = method.get("skills")
    if not isinstance(skills, dict):
        raise CompiledProcedureError("BBK-CP-008", "method-content skills are missing")
    known = set(str(x) for x in skills)
    dependencies = _dependency_map(root, known)

    role_entries = role_catalog.get("role_entries")
    if not isinstance(role_entries, list):
        raise CompiledProcedureError("BBK-CP-008", "role catalog entries are missing")
    roles: dict[str, dict[str, Any]] = {}
    statically_required: set[str] = set()
    for entry in role_entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("file"), str):
            raise CompiledProcedureError("BBK-CP-008", "invalid role catalog entry")
        role = _load_json(root / entry["file"])
        name = str(role.get("name") or "")
        primary = str(role.get("primary_skill") or "")
        required = [str(x) for x in role.get("mandatory_skills") or []]
        available = [str(x) for x in role.get("skills") or []]
        if not name or not primary or not required or required[0] != primary:
            raise CompiledProcedureError("BBK-CP-008", f"role {name or entry['file']} has invalid procedure declaration")
        missing = sorted((set(required) | set(available)) - known)
        if missing:
            raise CompiledProcedureError("BBK-CP-008", f"role {name} references unknown procedures {missing}")
        roles[name] = _identity_spec(name, primary, required, available)
        statically_required.update(required)

    controller_source = _load_json(root / "spec" / "controllers" / "bbk_controller.json")
    controller = _identity_spec(
        str(controller_source.get("name") or "bbk_controller"),
        str(controller_source.get("primary_procedure") or "bbk"),
        [str(x) for x in controller_source.get("required_procedures") or []],
        [str(x) for x in controller_source.get("available_procedures") or sorted(known)],
    )
    statically_required.update(controller["required"])

    def closure(items: Sequence[str]) -> set[str]:
        result: set[str] = set()
        def visit(item: str) -> None:
            for dep in dependencies[item]: visit(dep)
            result.add(item)
        for item in items: visit(item)
        return result
    statically_required = closure(sorted(statically_required))

    module_dependencies = method.get("skill_module_dependencies") or {}
    entries: list[dict[str, Any]] = []
    for skill_id in sorted(known):
        source_path = root / "shared" / "skills" / skill_id / "SKILL.md"
        if not source_path.is_file():
            raise CompiledProcedureError("BBK-CP-008", f"canonical source is missing for {skill_id}")
        policy = module_dependencies.get(skill_id) if isinstance(module_dependencies, dict) else None
        prompt_dependencies: list[str] = []
        if isinstance(policy, dict):
            prompt_dependencies = [
                *[str(x) for x in policy.get("requires_prompt_modules") or []],
                *[str(x) for x in policy.get("standalone_prompt_modules") or []],
            ]
        if skill_id == controller["primary"] and skill_id not in any_role_available(roles):
            classification = "COMPILED_ONLY"
        elif skill_id in statically_required:
            classification = "COMPILER_SELECTABLE"
        else:
            classification = "EXTERNAL_OPTIONAL"
        entries.append({
            "id": skill_id,
            "version": _package_version(root),
            "source": source_path.relative_to(root).as_posix(),
            "source_sha256": sha256_bytes(source_path.read_bytes()),
            "procedure_dependencies": dependencies[skill_id],
            "prompt_module_dependencies": prompt_dependencies,
            "catalog_classification": classification,
            # Retained compatibility field.
            "external_selection": "COMPILED_OR_OPTIONAL" if classification != "EXTERNAL_OPTIONAL" else "OPTIONAL_ONLY",
        })

    payload: dict[str, Any] = {
        "schema": "bbk.procedure-registry.v2",
        "package_version": _package_version(root),
        "source": "spec/method-content.json",
        "source_sha256": sha256_bytes(method_path.read_bytes()),
        "role_source_sha256": sha256_bytes(role_catalog_path.read_bytes()),
        "dependency_source": "spec/procedures/dependencies.json",
        "dependency_source_sha256": sha256_bytes((root / "spec/procedures/dependencies.json").read_bytes()),
        "controller_source": "spec/controllers/bbk_controller.json",
        "controller_source_sha256": sha256_bytes((root / "spec/controllers/bbk_controller.json").read_bytes()),
        "procedures": entries,
        "roles": {name: roles[name] for name in sorted(roles)},
        "controller": controller,
        "physical_catalog_classes": {
            "COMPILED_ONLY": sorted(x["id"] for x in entries if x["catalog_classification"] == "COMPILED_ONLY"),
            "COMPILER_SELECTABLE": sorted(x["id"] for x in entries if x["catalog_classification"] == "COMPILER_SELECTABLE"),
            "EXTERNAL_OPTIONAL": sorted(x["id"] for x in entries if x["catalog_classification"] == "EXTERNAL_OPTIONAL"),
            "HOST_TOOL_ONLY": [],
        },
    }
    # Compatibility projection: every non-indexed package-owned source.
    payload["global_non_indexed_compiled_set"] = sorted(
        payload["physical_catalog_classes"]["COMPILED_ONLY"] + payload["physical_catalog_classes"]["COMPILER_SELECTABLE"]
    )
    payload["registry_revision"] = sha256_bytes(compact_json_bytes(payload))
    return payload


def any_role_available(roles: Mapping[str, Mapping[str, Any]]) -> set[str]:
    result: set[str] = set()
    for role in roles.values():
        result.update(str(x) for x in role.get("available") or [])
    return result


def write_registry(root: Path = ROOT, path: Path | None = None) -> Path:
    path = path or (root / "spec" / "procedures" / "catalog.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(build_registry(root)))
    return path


def load_registry(root: Path = ROOT) -> dict[str, Any]:
    path = root / "spec" / "procedures" / "catalog.json"
    current = _load_json(path)
    expected = build_registry(root)
    if current != expected:
        raise CompiledProcedureError("BBK-CP-008", f"procedure registry drift: {path}")
    return current


def compiler_identity(root: Path = ROOT) -> dict[str, str]:
    source = Path(__file__).resolve()
    try: source = root / source.relative_to(ROOT)
    except ValueError: pass
    payload = source.read_bytes() if source.is_file() else COMPILER_ID.encode()
    return {"id": COMPILER_ID, "version": COMPILER_VERSION, "sha256": sha256_bytes(payload)}


def _harness_id(harness: str) -> str:
    return HARNESS_IDS.get(harness.lower(), "OTHER")


def _normalize_additional_procedures(
    values: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for procedure_id, raw in sorted((values or {}).items()):
        if not isinstance(procedure_id, str) or not procedure_id:
            raise CompiledProcedureError("BBK-CP-008", "additional procedure ID is invalid")
        if not isinstance(raw, Mapping):
            raise CompiledProcedureError("BBK-CP-008", f"additional procedure {procedure_id} is invalid")
        source_path = raw.get("source_path")
        source_sha256 = raw.get("source_sha256")
        source_bytes = raw.get("source_bytes")
        version = raw.get("version")
        dependencies = raw.get("procedure_dependencies") or []
        classification = raw.get("catalog_classification") or "COMPILER_SELECTABLE"
        if not isinstance(source_path, str) or not source_path:
            raise CompiledProcedureError("BBK-CP-008", f"additional procedure {procedure_id} has no source path")
        if not isinstance(source_sha256, str) or len(source_sha256) != 64:
            raise CompiledProcedureError("BBK-CP-008", f"additional procedure {procedure_id} has no source digest")
        if not isinstance(source_bytes, int) or source_bytes < 0:
            raise CompiledProcedureError("BBK-CP-008", f"additional procedure {procedure_id} has invalid source bytes")
        if not isinstance(version, str) or not version:
            raise CompiledProcedureError("BBK-CP-008", f"additional procedure {procedure_id} has no version")
        if (
            not isinstance(dependencies, list)
            or len(dependencies) != len(set(dependencies))
            or not all(isinstance(item, str) and item for item in dependencies)
        ):
            raise CompiledProcedureError("BBK-CP-008", f"additional procedure {procedure_id} has invalid dependencies")
        if classification not in {"COMPILER_SELECTABLE", "EXTERNAL_OPTIONAL"}:
            raise CompiledProcedureError("BBK-CP-008", f"additional procedure {procedure_id} has invalid classification")
        result[procedure_id] = {
            "id": procedure_id,
            "version": version,
            "source_path": source_path,
            "source_ref": str(raw.get("source_ref") or source_path),
            "source_sha256": source_sha256,
            "source_bytes": source_bytes,
            "procedure_dependencies": list(dependencies),
            "prompt_module_dependencies": [str(item) for item in raw.get("prompt_module_dependencies") or []],
            "catalog_classification": classification,
            "profile_id": raw.get("profile_id"),
            "profile_version": raw.get("profile_version"),
        }
    return result


def load_profile_procedure_selection(
    registry_path: Path,
    *,
    profile_ids: Sequence[str],
) -> tuple[dict[str, dict[str, Any]], tuple[str, ...], tuple[str, ...], str]:
    """Load exact installed profile procedure sources for one invocation.

    The installed profile registry is produced only after package verification
    and binds each procedure to the persistent installed package path, source
    byte count, and SHA-256.  Required routers become profile-selected
    procedures; optional procedures become invocation-selectable catalog
    candidates.
    """
    value = _load_json(registry_path)
    if value.get("schema") != "bbk.installed-profile-registry.v1":
        raise CompiledProcedureError("BBK-CP-008", "installed profile registry schema is unsupported")
    selected = list(dict.fromkeys(str(item) for item in profile_ids))
    if not selected:
        raise CompiledProcedureError("BBK-CP-008", "profile_ids are required with an installed profile registry")
    profiles = value.get("profiles")
    if not isinstance(profiles, list):
        raise CompiledProcedureError("BBK-CP-008", "installed profile registry has no profiles")
    by_id = {str(item.get("id")): item for item in profiles if isinstance(item, Mapping)}
    missing = sorted(set(selected) - set(by_id))
    if missing:
        raise CompiledProcedureError("BBK-CP-008", f"installed profile IDs are missing: {missing}")
    additional: dict[str, dict[str, Any]] = {}
    required: list[str] = []
    optional: list[str] = []
    revisions: list[str] = []
    for profile_id in selected:
        profile = by_id[profile_id]
        version = str(profile.get("version") or "")
        binding = profile.get("procedure_binding")
        if not isinstance(binding, Mapping):
            raise CompiledProcedureError("BBK-CP-008", f"profile {profile_id} has no procedure binding")
        revision = profile.get("procedure_registry_revision") or binding.get("registry_revision")
        if not isinstance(revision, str) or len(revision) != 64:
            raise CompiledProcedureError("BBK-CP-008", f"profile {profile_id} has no registry revision")
        revisions.append(f"{profile_id}@{version}:{revision}")
        required_ids = [str(item) for item in binding.get("required_procedures") or []]
        optional_ids = [str(item) for item in binding.get("optional_procedures") or []]
        sources = binding.get("procedure_sources")
        if not isinstance(sources, list):
            raise CompiledProcedureError("BBK-CP-008", f"profile {profile_id} has no procedure sources")
        for source in sources:
            if not isinstance(source, Mapping):
                raise CompiledProcedureError("BBK-CP-008", f"profile {profile_id} has an invalid procedure source")
            procedure_id = str(source.get("id") or "")
            installed_path = source.get("installed_path")
            digest = source.get("sha256")
            source_bytes = source.get("bytes")
            if procedure_id in additional:
                raise CompiledProcedureError("BBK-CP-008", f"profile procedure ID collision: {procedure_id}")
            if not isinstance(installed_path, str) or not installed_path:
                raise CompiledProcedureError("BBK-CP-008", f"profile procedure {procedure_id} has no installed path")
            path = Path(installed_path)
            if not path.is_file():
                raise CompiledProcedureError("BBK-CP-008", f"profile procedure source is missing: {path}")
            payload = path.read_bytes()
            observed = sha256_bytes(payload)
            if observed != digest or len(payload) != source_bytes:
                raise CompiledProcedureError("BBK-CP-008", f"profile procedure source identity mismatch: {procedure_id}")
            additional[procedure_id] = {
                "version": version,
                "source_path": str(path),
                "source_ref": f"profile:{profile_id}@{version}:{source.get('path')}",
                "source_sha256": observed,
                "source_bytes": len(payload),
                "procedure_dependencies": [str(item) for item in source.get("procedure_dependencies") or []],
                "prompt_module_dependencies": [],
                "catalog_classification": "COMPILER_SELECTABLE" if procedure_id in required_ids else "EXTERNAL_OPTIONAL",
                "profile_id": profile_id,
                "profile_version": version,
            }
        required.extend(required_ids)
        optional.extend(optional_ids)
    missing_sources = sorted((set(required) | set(optional)) - set(additional))
    if missing_sources:
        raise CompiledProcedureError("BBK-CP-008", f"profile procedure sources are missing: {missing_sources}")
    combined_revision = sha256_bytes(compact_json_bytes(sorted(revisions)))
    return (
        _normalize_additional_procedures(additional),
        tuple(dict.fromkeys(required)),
        tuple(dict.fromkeys(optional)),
        combined_revision,
    )


def _closure(selected: Sequence[str], registry: Mapping[str, Any], reasons: Mapping[str, str], primary: str) -> tuple[list[str], dict[str, str]]:
    known = {str(x["id"]): x for x in registry.get("procedures") or [] if isinstance(x, Mapping)}
    missing = sorted(set(selected) - set(known))
    if missing: raise CompiledProcedureError("BBK-CP-008", f"unresolved procedure IDs: {missing}")
    result: list[str] = []
    reason = dict(reasons)
    visiting: list[str] = []
    def visit(item: str, parent: str | None = None) -> None:
        if item in visiting:
            start=visiting.index(item)
            raise CompiledProcedureError("BBK-CP-003", "procedure dependency cycle: " + " -> ".join(visiting[start:]+[item]))
        if item in result: return
        visiting.append(item)
        for dep in known[item].get("procedure_dependencies") or []:
            dep=str(dep)
            reason.setdefault(dep, f"DEPENDENCY_OF:{item}")
            visit(dep,item)
        visiting.pop()
        if item not in result: result.append(item)
    for item in selected: visit(item)
    # Primary is always the final semantic procedure. Its dependencies remain before it.
    result=[x for x in result if x != primary]+[primary]
    return result, reason


@dataclass(frozen=True)
class PromptCompilationPlan:
    schema: str
    identity_kind: str
    identity_name: str
    harness: str
    logical_child_id: str
    invocation_id: str | None
    primary_procedure: str
    role_required_procedures: tuple[str, ...]
    profile_required_procedures: tuple[str, ...] = ()
    invocation_required_procedures: tuple[str, ...] = ()
    selected_procedure_closure: tuple[str, ...] = ()
    selection_reasons: Mapping[str, str] = field(default_factory=dict)
    available_procedures: tuple[str, ...] = ()
    base_prompt_sha256: str = ""
    return_contract_sha256: str = ""
    model_route_sha256: str = ""
    tool_capability_sha256: str = ""
    adapter_template_sha256: str = ""
    profile_registry_revision: str = ""
    invocation_policy_sha256: str = ""
    additional_procedures: tuple[dict[str, Any], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema, "identity_kind": self.identity_kind,
            "identity_name": self.identity_name, "harness": self.harness,
            "logical_child_id": self.logical_child_id, "invocation_id": self.invocation_id,
            "primary_procedure": self.primary_procedure,
            "role_required_procedures": list(self.role_required_procedures),
            "profile_required_procedures": list(self.profile_required_procedures),
            "invocation_required_procedures": list(self.invocation_required_procedures),
            "selected_procedure_closure": list(self.selected_procedure_closure),
            "selection_reasons": dict(self.selection_reasons),
            "available_procedures": list(self.available_procedures),
            "base_prompt_sha256": self.base_prompt_sha256,
            "return_contract_sha256": self.return_contract_sha256,
            "model_route_sha256": self.model_route_sha256,
            "tool_capability_sha256": self.tool_capability_sha256,
            "adapter_template_sha256": self.adapter_template_sha256,
            "profile_registry_revision": self.profile_registry_revision,
            "invocation_policy_sha256": self.invocation_policy_sha256,
            "additional_procedures": [dict(item) for item in self.additional_procedures],
        }


@dataclass(frozen=True)
class CompilationResult:
    prompt: str
    prompt_tail: str
    manifest: dict[str, Any]
    external_catalog: tuple[str, ...]
    source_read_count: int
    reused: bool
    plan: dict[str, Any] = field(default_factory=dict)
    source_map: tuple[dict[str, Any], ...] = ()
    event: dict[str, Any] = field(default_factory=dict)


def build_plan(
    identity: Mapping[str, Any], *, identity_kind: str, harness: str,
    base_prompt: str, logical_child_id: str | None = None, invocation_id: str | None = None,
    profile_procedures: Sequence[str] = (), invocation_procedures: Sequence[str] = (),
    return_contract: Any = None, model_route: Any = None, tool_capabilities: Any = None,
    adapter_template: Any = None, profile_registry_revision: str = "", invocation_policy: Any = None,
    additional_procedures: Mapping[str, Mapping[str, Any]] | None = None,
    additional_available_procedures: Sequence[str] = (),
    root: Path = ROOT,
    procedure_registry: Mapping[str, Any] | None = None,
) -> PromptCompilationPlan:
    registry = procedure_registry if procedure_registry is not None else load_registry(root.resolve())
    additional = _normalize_additional_procedures(additional_procedures)
    core_ids = {str(item["id"]) for item in registry.get("procedures") or []}
    collisions = sorted(core_ids & set(additional))
    if collisions:
        raise CompiledProcedureError("BBK-CP-008", f"additional procedure IDs collide with core procedures: {collisions}")
    combined_registry = {
        **registry,
        "procedures": [
            *registry.get("procedures", []),
            *[
                {
                    "id": procedure_id,
                    "version": item["version"],
                    "source": item["source_ref"],
                    "source_sha256": item["source_sha256"],
                    "procedure_dependencies": item["procedure_dependencies"],
                    "prompt_module_dependencies": item["prompt_module_dependencies"],
                    "catalog_classification": item["catalog_classification"],
                }
                for procedure_id, item in additional.items()
            ],
        ],
    }
    primary = str(identity.get("primary_skill") or identity.get("primary") or identity.get("primary_procedure") or "")
    required = [str(x) for x in (identity.get("mandatory_skills") or identity.get("required") or identity.get("required_procedures") or [])]
    available = list(dict.fromkeys([
        *[str(x) for x in (identity.get("skills") or identity.get("available") or identity.get("available_procedures") or [])],
        *[str(x) for x in additional_available_procedures],
    ]))
    name = str(identity.get("name") or "unknown")
    if not primary:
        raise CompiledProcedureError("BBK-CP-001", f"{name} has no primary procedure")
    if primary not in required: required.insert(0,primary)
    reasons: dict[str,str] = {}
    selected: list[str] = []
    for item in required:
        if item not in selected: selected.append(item)
        reasons[item] = "PRIMARY" if item == primary else "ROLE_REQUIRED"
    for item in profile_procedures:
        item=str(item)
        if item not in selected: selected.append(item)
        reasons[item] = "PROFILE"
    for item in invocation_procedures:
        item=str(item)
        if item not in selected: selected.append(item)
        reasons[item] = "INVOCATION"
    closure,reasons = _closure(selected, combined_registry, reasons, primary)
    digest=lambda x: sha256_bytes(compact_json_bytes(x)) if x not in (None,"",[],{}) else ""
    return PromptCompilationPlan(
        schema="bbk.prompt-compilation-plan.v1", identity_kind=identity_kind,
        identity_name=name, harness=harness.lower(),
        logical_child_id=logical_child_id or f"projection:{harness.lower()}:{name}", invocation_id=invocation_id,
        primary_procedure=primary, role_required_procedures=tuple(required),
        profile_required_procedures=tuple(str(x) for x in profile_procedures),
        invocation_required_procedures=tuple(str(x) for x in invocation_procedures),
        selected_procedure_closure=tuple(closure), selection_reasons=reasons,
        available_procedures=tuple(available), base_prompt_sha256=sha256_bytes(base_prompt.encode("utf-8")),
        return_contract_sha256=digest(return_contract), model_route_sha256=digest(model_route),
        tool_capability_sha256=digest(tool_capabilities), adapter_template_sha256=digest(adapter_template),
        profile_registry_revision=profile_registry_revision, invocation_policy_sha256=digest(invocation_policy),
        additional_procedures=tuple(dict(additional[key]) for key in sorted(additional)),
    )


def _project_body(
    root: Path,
    skill_id: str,
    method: Mapping[str, Any],
    additional: Mapping[str, Mapping[str, Any]],
    prompt_package: Any | None = None,
    embedded_prompt_modules: Sequence[str] = (),
) -> tuple[str,str,str,list[str]]:
    if skill_id in additional:
        item = additional[skill_id]
        source = Path(str(item["source_path"]))
        if not source.is_file():
            raise CompiledProcedureError("BBK-CP-008", f"additional procedure source missing for {skill_id}")
        payload = source.read_bytes()
        observed = sha256_bytes(payload)
        if observed != item["source_sha256"] or len(payload) != item["source_bytes"]:
            raise CompiledProcedureError("BBK-CP-008", f"additional procedure source identity changed for {skill_id}")
        body = strip_frontmatter(payload.decode("utf-8")).strip()
        if not body:
            raise CompiledProcedureError("BBK-CP-008", f"additional procedure body is empty for {skill_id}")
        return (
            _resolve_embedded_module_references(body, embedded_prompt_modules),
            str(item["source_ref"]),
            observed,
            [str(value) for value in item.get("prompt_module_dependencies") or []],
        )
    template=(method.get("skills") or {}).get(skill_id)
    if not isinstance(template,str): raise CompiledProcedureError("BBK-CP-008",f"unknown procedure {skill_id}")
    package = prompt_package if prompt_package is not None else load_prompt_modules(root)
    body=strip_frontmatter(compact_skill_template(template,package)).strip()
    source=root/"shared"/"skills"/skill_id/"SKILL.md"
    if not source.is_file(): raise CompiledProcedureError("BBK-CP-008",f"canonical source missing for {skill_id}")
    policy=(method.get("skill_module_dependencies") or {}).get(skill_id) or {}
    prompt_deps=[*[str(x) for x in policy.get("requires_prompt_modules") or []],*[str(x) for x in policy.get("standalone_prompt_modules") or []]]
    return _resolve_embedded_module_references(body, embedded_prompt_modules),source.relative_to(root).as_posix(),sha256_bytes(source.read_bytes()),prompt_deps


def _resolve_embedded_module_references(body: str, module_ids: Sequence[str]) -> str:
    """Keep each embedded-module dependency visible at its procedure position."""
    for module_id in module_ids:
        escaped = re.escape(module_id)
        body = re.sub(
            rf"(?m)^[ \t]*> (?:Apply the already embedded|The compiled|Apply embedded|Apply|Apply module) `"
            rf"{escaped}` (?:module here\.|module above applies at this point\.|here\.|\.)[ \t]*$",
            f"> Apply `{module_id}`.",
            body,
        )
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def _controller_module_ids(
    plan: PromptCompilationPlan,
    registry: Mapping[str, Any],
    package: Any,
) -> tuple[str, ...]:
    procedures = {str(item["id"]): item for item in registry["procedures"]}
    procedures.update({str(item["id"]): item for item in plan.additional_procedures})
    selected = {
        str(module_id)
        for procedure_id in plan.selected_procedure_closure
        for module_id in procedures[procedure_id].get("prompt_module_dependencies") or []
    }
    return tuple(module["id"] for module in ordered_modules(package, selected))


def _embed_role_modules(
    base_prompt: str,
    module_ids: Sequence[str],
    package: Any,
    harness: str,
) -> str:
    lines = [base_prompt.rstrip(), "", "## Compiled prompt modules"]
    tagged = harness.lower() != "codex"
    for module in ordered_modules(package, module_ids):
        module_id = str(module["id"])
        clauses = clauses_for_harness(module, harness)
        lines.extend([""])
        if tagged:
            lines.extend([
                f'<bbk-prompt-module id="{module_id}">',
                *[f"- {clause['text']}" for clause in clauses],
                "</bbk-prompt-module>",
            ])
        else:
            lines.extend([
                f"### `{module_id}`",
                "",
                *[f"- {clause['text']}" for clause in clauses],
            ])
    return "\n".join(lines).rstrip() + "\n"


def _embed_controller_modules(
    base_prompt: str,
    module_ids: Sequence[str],
    package: Any,
    harness: str,
) -> str:
    lines = [base_prompt.rstrip(), "", "## Compiled prompt modules"]
    for module in ordered_modules(package, module_ids):
        module_id = str(module["id"])
        lines.extend([
            "",
            f"<!-- BBK compiled prompt module {module_id} -->",
            "",
            f"### `{module_id}`",
            "",
            *[f"- `{clause['id']}` — {clause['text']}" for clause in clauses_for_harness(module, harness)],
            "",
            f"<!-- End BBK compiled prompt module {module_id} -->",
        ])
    return "\n".join(lines).rstrip() + "\n"


def render_compiled_tail(records: Sequence[Mapping[str,Any]], bodies: Mapping[str,str], primary: str) -> str:
    lines = [
        "## Compiled procedures manifest",
        "",
        "Procedure state and digest details remain in the machine manifest.",
        "",
    ]
    for rec in records:
        lines += [
            f"- id: {rec['id']}",
            "  state: COMPILED_COMPLETE",
            "  catalog_visibility: SUPPRESSED",
        ]
    lines += [
        "",
        "## Compiled procedures",
        "",
        "Complete developer instructions in execution order; primary last. All are `COMPILED_COMPLETE`, catalog `SUPPRESSED`; no external selection or model filesystem read.",
        "",
    ]
    for rec in records:
        label = "Compiled primary procedure" if rec["id"] == primary else "Compiled procedure"
        lines += [f"### {label}: `{rec['id']}`", "", bodies[str(rec["id"])], ""]
    lines.append("## End compiled procedures")
    return "\n".join(lines).rstrip() + "\n"


def compile_plan(
    base_prompt: str,
    plan: PromptCompilationPlan,
    *,
    root: Path = ROOT,
    procedure_registry: Mapping[str, Any] | None = None,
    method_content: Mapping[str, Any] | None = None,
    prompt_package: Any | None = None,
    embedded_prompt_modules: Sequence[str] = (),
) -> CompilationResult:
    root = root.resolve()
    registry = procedure_registry if procedure_registry is not None else load_registry(root)
    package = prompt_package if prompt_package is not None else load_prompt_modules(root)
    method = method_content if method_content is not None else _method_content(root, package)
    additional = _normalize_additional_procedures(
        {str(item["id"]): item for item in plan.additional_procedures}
    )
    known={str(x["id"]):x for x in registry["procedures"]}
    known.update(
        {
            procedure_id: {
                "id": procedure_id,
                "version": item["version"],
                "source": item["source_ref"],
                "source_sha256": item["source_sha256"],
                "procedure_dependencies": item["procedure_dependencies"],
                "prompt_module_dependencies": item["prompt_module_dependencies"],
                "catalog_classification": item["catalog_classification"],
            }
            for procedure_id, item in additional.items()
        }
    )
    bodies:dict[str,str]={}; records=[]; seen={}; source_map=[]
    for order,skill_id in enumerate(plan.selected_procedure_closure):
        body,source_ref,source_digest,prompt_deps=_project_body(
            root, skill_id, method, additional, package, embedded_prompt_modules
        )
        missing_modules = set(prompt_deps) - set(embedded_prompt_modules) if embedded_prompt_modules else set()
        if missing_modules:
            raise CompiledProcedureError("BBK-CP-009", f"{skill_id} has unembedded prompt modules {sorted(missing_modules)}")
        effective=sha256_bytes((body.rstrip()+"\n").encode())
        if effective in seen and seen[effective]!=skill_id:
            raise CompiledProcedureError("BBK-CP-002",f"{skill_id} duplicates effective body of {seen[effective]}")
        seen[effective]=skill_id; bodies[skill_id]=body
        records.append({"id":skill_id,"version":str(known[skill_id]["version"]),"source_ref":source_ref,"source_sha256":source_digest,"effective_sha256":effective,"selection_reason":plan.selection_reasons.get(skill_id,"DEPENDENCY"),"ordering":order,"catalog_visibility":"SUPPRESSED","state":"COMPILED_COMPLETE","dependencies":[*[str(x) for x in known[skill_id].get("procedure_dependencies") or []],*prompt_deps]})
    tail=render_compiled_tail(records,bodies,plan.primary_procedure)
    prompt=(base_prompt.rstrip()+"\n\n"+tail).rstrip()+"\n"
    if embedded_prompt_modules:
        if "Apply the already embedded" in prompt:
            raise CompiledProcedureError("BBK-CP-009", "compiled prompt contains unresolved embedded-module placeholders")
        for module_id in embedded_prompt_modules:
            controller_marker = f"<!-- BBK compiled prompt module {module_id} -->"
            role_marker = f'<bbk-prompt-module id="{module_id}">'
            codex_marker = f"### `{module_id}`"
            if controller_marker in prompt:
                count = prompt.count(controller_marker)
            elif role_marker in prompt:
                count = prompt.count(role_marker)
            else:
                count = prompt.count(codex_marker)
            if count != 1:
                raise CompiledProcedureError("BBK-CP-009", f"compiled prompt must embed {module_id} exactly once")
    suppression=[str(x["id"]) for x in records]
    classifications={str(x["id"]):str(x.get("catalog_classification")) for x in registry["procedures"]}
    external=tuple(x for x in plan.available_procedures if x not in set(suppression) and classifications.get(x)=="EXTERNAL_OPTIONAL")
    plan_dict=plan.as_dict(); plan_digest=sha256_bytes(compact_json_bytes(plan_dict))
    ci=compiler_identity(root)
    invalidation=[f"registry:{registry['registry_revision']}",f"compiler:{ci['sha256']}",f"harness:{plan.harness}",f"plan:{plan_digest}",f"base:{plan.base_prompt_sha256}"]
    for key,value in [("return",plan.return_contract_sha256),("model",plan.model_route_sha256),("tools",plan.tool_capability_sha256),("adapter",plan.adapter_template_sha256),("profile",plan.profile_registry_revision),("policy",plan.invocation_policy_sha256)]:
        if value: invalidation.append(f"{key}:{value}")
    manifest={
        "schema":"bbk.compiled-procedure-manifest.v1","role":plan.identity_name,
        "identity_kind":plan.identity_kind,"logical_child_id":plan.logical_child_id,
        "invocation_id":plan.invocation_id,"harness":_harness_id(plan.harness),"compiler":ci,
        "registry_revision":registry["registry_revision"],"plan_sha256":plan_digest,
        "procedures":records,"catalog_suppression_set":suppression,
        "effective_external_catalog_sha256":sha256_bytes(compact_json_bytes(external)),
        "compiled_prompt_sha256":sha256_bytes(prompt.encode()),"compiled_tail_sha256":sha256_bytes(tail.encode()),
        "prompt_metrics":{"characters":len(prompt),"utf8_bytes":len(prompt.encode()),"estimated_tokens":(len(prompt)+3)//4},
        "invalidation_keys":invalidation,
        "followup_policy":{"preserve_by_default":True,"recompile_triggers":FOLLOWUP_TRIGGERS},
    }
    # Source map is generated from exact final prompt offsets.
    cursor=0
    base_end=len(base_prompt.rstrip())
    source_map.append({"id":"base-prompt","source":"canonical-role-or-controller","start":0,"end":base_end,"sha256":plan.base_prompt_sha256})
    for rec in records:
        marker=f"### {'Compiled primary procedure' if rec['id']==plan.primary_procedure else 'Compiled procedure'}: `{rec['id']}`\n\n"
        start=prompt.index(marker)+len(marker); end=start+len(bodies[rec['id']])
        source_map.append({"id":f"procedure:{rec['id']}","source":rec["source_ref"],"start":start,"end":end,"sha256":rec["effective_sha256"]})
    event={"schema":"bbk.prompt-compilation-event.v1","event":"PROMPT_COMPILED","logical_child_id":plan.logical_child_id,"physical_attempt_id":plan.invocation_id,"identity_kind":plan.identity_kind,"role":plan.identity_name,"harness":_harness_id(plan.harness),"effective_prompt_sha256":manifest["compiled_prompt_sha256"],"procedure_ids":suppression,"external_catalog_sha256":manifest["effective_external_catalog_sha256"],"source_reads_by_compiler":len(records),"procedure_reads_by_model":0,"reused":False}
    return CompilationResult(prompt,tail,manifest,external,len(records),False,plan_dict,tuple(source_map),event)


def compile_role_prompt(
    base_prompt: str,
    role: Mapping[str, Any],
    *,
    harness: str,
    logical_child_id: str | None = None,
    invocation_id: str | None = None,
    profile_procedures: Sequence[str] = (),
    invocation_procedures: Sequence[str] = (),
    root: Path = ROOT,
    procedure_registry: Mapping[str, Any] | None = None,
    method_content: Mapping[str, Any] | None = None,
    prompt_package: Any | None = None,
    **context: Any,
) -> CompilationResult:
    root = root.resolve()
    registry = procedure_registry if procedure_registry is not None else load_registry(root)
    package = prompt_package if prompt_package is not None else load_prompt_modules(root)
    method = method_content if method_content is not None else _method_content(root, package)
    plan = build_plan(
        role,
        identity_kind="ROLE",
        harness=harness,
        base_prompt=base_prompt,
        logical_child_id=logical_child_id,
        invocation_id=invocation_id,
        profile_procedures=profile_procedures,
        invocation_procedures=invocation_procedures,
        root=root,
        procedure_registry=registry,
        **context,
    )
    selected_module_ids = _controller_module_ids(plan, registry, package)
    module_ids = tuple(
        module["id"]
        for module in ordered_modules(
            package,
            {
                *[str(value) for value in role.get("prompt_modules") or ()],
                *selected_module_ids,
            },
        )
    )
    base_prompt = _embed_role_modules(base_prompt, module_ids, package, harness)
    plan = build_plan(
        role,
        identity_kind="ROLE",
        harness=harness,
        base_prompt=base_prompt,
        logical_child_id=logical_child_id,
        invocation_id=invocation_id,
        profile_procedures=profile_procedures,
        invocation_procedures=invocation_procedures,
        root=root,
        procedure_registry=registry,
        **context,
    )
    return compile_plan(
        base_prompt,
        plan,
        root=root,
        procedure_registry=registry,
        method_content=method,
        prompt_package=package,
        embedded_prompt_modules=module_ids,
    )


def compile_controller_prompt(
    base_prompt: str,
    *,
    harness: str,
    logical_child_id: str | None = None,
    invocation_id: str | None = None,
    profile_procedures: Sequence[str] = (),
    invocation_procedures: Sequence[str] = (),
    root: Path = ROOT,
    procedure_registry: Mapping[str, Any] | None = None,
    method_content: Mapping[str, Any] | None = None,
    prompt_package: Any | None = None,
    **context: Any,
) -> CompilationResult:
    root = root.resolve()
    registry = procedure_registry if procedure_registry is not None else load_registry(root)
    package = prompt_package if prompt_package is not None else load_prompt_modules(root)
    method = method_content if method_content is not None else _method_content(root, package)
    source = _load_json(root / "spec" / "controllers" / "bbk_controller.json")
    identity = {
        "name": source["name"],
        "primary_procedure": source["primary_procedure"],
        "required_procedures": source["required_procedures"],
        "available_procedures": source["available_procedures"],
    }
    plan = build_plan(
        identity,
        identity_kind="CONTROLLER",
        harness=harness,
        base_prompt=base_prompt,
        logical_child_id=logical_child_id,
        invocation_id=invocation_id,
        profile_procedures=profile_procedures,
        invocation_procedures=invocation_procedures,
        root=root,
        procedure_registry=registry,
        **context,
    )
    module_ids = _controller_module_ids(plan, registry, package)
    base_prompt = _embed_controller_modules(base_prompt, module_ids, package, harness)
    plan = build_plan(
        identity,
        identity_kind="CONTROLLER",
        harness=harness,
        base_prompt=base_prompt,
        logical_child_id=logical_child_id,
        invocation_id=invocation_id,
        profile_procedures=profile_procedures,
        invocation_procedures=invocation_procedures,
        root=root,
        procedure_registry=registry,
        **context,
    )
    return compile_plan(
        base_prompt,
        plan,
        root=root,
        procedure_registry=registry,
        method_content=method,
        prompt_package=package,
        embedded_prompt_modules=module_ids,
    )


def compiled_state(result: CompilationResult) -> dict[str,Any]:
    return {"schema":"bbk.logical-child-compiled-procedure-state.v2","manifest":result.manifest,"prompt":result.prompt,"prompt_tail":result.prompt_tail,"external_catalog":list(result.external_catalog),"plan":result.plan,"source_map":list(result.source_map)}


def followup_result(
    previous_state: Mapping[str,Any], *,
    requested_procedure_ids: Sequence[str]|None=None,
    harness: str|None=None,
    registry_revision: str|None=None,
    compiler_sha256: str|None=None,
    current_invalidation_keys: Sequence[str]|None=None,
    root: Path=ROOT,
) -> CompilationResult:
    manifest=previous_state.get("manifest")
    if not isinstance(manifest,Mapping): raise CompiledProcedureError("BBK-CP-007","previous state has no manifest")
    current_registry = load_registry(root.resolve())
    current_compiler = compiler_identity(root.resolve())
    if manifest.get("registry_revision") != current_registry.get("registry_revision"):
        raise CompiledProcedureError("BBK-CP-007", "procedure registry changed")
    compiler = manifest.get("compiler")
    if not isinstance(compiler, Mapping) or compiler.get("sha256") != current_compiler.get("sha256"):
        raise CompiledProcedureError("BBK-CP-007", "compiler identity changed")
    previous_ids=[str(x.get("id")) for x in manifest.get("procedures") or [] if isinstance(x,Mapping)]
    if requested_procedure_ids is not None and list(requested_procedure_ids)!=previous_ids: raise CompiledProcedureError("BBK-CP-007","procedure selection changed")
    if harness and manifest.get("harness")!=_harness_id(harness): raise CompiledProcedureError("BBK-CP-007","harness projection changed")
    if registry_revision and manifest.get("registry_revision")!=registry_revision: raise CompiledProcedureError("BBK-CP-007","registry revision changed")
    if compiler_sha256 and (not isinstance(compiler,Mapping) or compiler.get("sha256")!=compiler_sha256): raise CompiledProcedureError("BBK-CP-007","compiler identity changed")
    if current_invalidation_keys is not None and list(current_invalidation_keys)!=list(manifest.get("invalidation_keys") or []): raise CompiledProcedureError("BBK-CP-007","compilation invalidation keys changed")
    prompt=previous_state.get("prompt"); tail=previous_state.get("prompt_tail"); catalog=previous_state.get("external_catalog")
    if not isinstance(prompt,str) or not isinstance(tail,str) or not isinstance(catalog,list): raise CompiledProcedureError("BBK-CP-007","previous state is incomplete")
    if sha256_bytes(prompt.encode())!=manifest.get("compiled_prompt_sha256"): raise CompiledProcedureError("BBK-CP-006","preserved prompt digest mismatch")
    core = {str(item["id"]): item for item in current_registry.get("procedures") or []}
    plan = previous_state.get("plan") if isinstance(previous_state.get("plan"), Mapping) else {}
    additional = _normalize_additional_procedures(
        {
            str(item["id"]): item
            for item in plan.get("additional_procedures") or []
            if isinstance(item, Mapping) and isinstance(item.get("id"), str)
        }
    )
    for record in manifest.get("procedures") or []:
        if not isinstance(record, Mapping):
            raise CompiledProcedureError("BBK-CP-007", "preserved manifest has an invalid procedure record")
        procedure_id = str(record.get("id") or "")
        if procedure_id in core:
            current = core[procedure_id]
            if (
                record.get("source_sha256") != current.get("source_sha256")
                or list(current.get("procedure_dependencies") or [])
                != [value for value in record.get("dependencies") or [] if not str(value).startswith("bbk-prompt-")]
            ):
                raise CompiledProcedureError("BBK-CP-007", f"procedure source or dependency changed: {procedure_id}")
        elif procedure_id in additional:
            item = additional[procedure_id]
            source = Path(str(item["source_path"]))
            if not source.is_file():
                raise CompiledProcedureError("BBK-CP-007", f"profile procedure source removed: {procedure_id}")
            payload = source.read_bytes()
            if sha256_bytes(payload) != item["source_sha256"] or len(payload) != item["source_bytes"]:
                raise CompiledProcedureError("BBK-CP-007", f"profile procedure source changed: {procedure_id}")
        else:
            raise CompiledProcedureError("BBK-CP-007", f"procedure removed: {procedure_id}")
    event={"schema":"bbk.prompt-compilation-event.v1","event":"PROMPT_REUSED","logical_child_id":manifest.get("logical_child_id"),"physical_attempt_id":manifest.get("invocation_id"),"identity_kind":manifest.get("identity_kind","ROLE"),"role":manifest.get("role"),"harness":manifest.get("harness"),"effective_prompt_sha256":manifest.get("compiled_prompt_sha256"),"procedure_ids":previous_ids,"external_catalog_sha256":manifest.get("effective_external_catalog_sha256",sha256_bytes(compact_json_bytes(catalog))),"source_reads_by_compiler":0,"procedure_reads_by_model":0,"reused":True}
    return CompilationResult(prompt,tail,dict(manifest),tuple(str(x) for x in catalog),0,True,dict(previous_state.get("plan") or {}),tuple(previous_state.get("source_map") or []),event)


def globally_suppressed_procedures(root: Path=ROOT) -> tuple[str,...]:
    registry=load_registry(root.resolve())
    classes=registry.get("physical_catalog_classes") or {}
    return tuple(sorted([*[str(x) for x in classes.get("COMPILED_ONLY") or []],*[str(x) for x in classes.get("COMPILER_SELECTABLE") or []]]))


def physically_indexed_procedures(root: Path=ROOT) -> tuple[str,...]:
    registry=load_registry(root.resolve())
    return tuple(str(x) for x in (registry.get("physical_catalog_classes") or {}).get("EXTERNAL_OPTIONAL") or [])


def catalog_projection(
    identity: Mapping[str,Any], manifest: Mapping[str,Any], *,
    additional_procedures: Mapping[str, Mapping[str, Any]] | None = None,
    additional_available_procedures: Sequence[str] = (),
    root: Path=ROOT,
    procedure_registry: Mapping[str, Any] | None = None,
) -> dict[str,Any]:
    registry = procedure_registry if procedure_registry is not None else load_registry(root.resolve())
    classifications={str(x["id"]):str(x.get("catalog_classification")) for x in registry["procedures"]}
    classifications.update(
        {
            procedure_id: str(item["catalog_classification"])
            for procedure_id, item in _normalize_additional_procedures(additional_procedures).items()
        }
    )
    suppression=[str(x) for x in manifest.get("catalog_suppression_set") or []]
    available_source=list(dict.fromkeys([
        *[str(x) for x in (identity.get("skills") or identity.get("available") or identity.get("available_procedures") or [])],
        *[str(x) for x in additional_available_procedures],
    ]))
    available=[x for x in available_source if x not in set(suppression) and classifications.get(x)=="EXTERNAL_OPTIONAL"]
    return {"schema":"bbk.effective-procedure-catalog.v2","identity_kind":manifest.get("identity_kind","ROLE"),"role":identity.get("name"),"available_external_procedures":available,"compiler_selectable_procedures":[x for x in available_source if classifications.get(x)=="COMPILER_SELECTABLE"],"suppressed_compiled_procedures":suppression,"catalog_sha256":sha256_bytes(compact_json_bytes(available)),"status":"PASS"}
