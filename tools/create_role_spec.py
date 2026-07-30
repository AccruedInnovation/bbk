#!/usr/bin/env python3
"""Normalize or verify the canonical BBK role catalogue.

``spec/roles.json`` is the canonical role source. This tool verifies its
version, structural invariants, method-skill references, spawn graph, and
stable serialization. It deliberately does not maintain a second Python copy
of the role catalogue that can drift from the generated harness projections.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ROLE_SPEC = ROOT / "spec" / "roles.json"
METHOD_SPEC = ROOT / "spec" / "method-content.json"
REQUIRED_ROLE_FIELDS = {
    "id", "name", "title", "family", "description", "purpose",
    "constitution", "scope", "responsibilities", "delegation",
    "escalations", "user_interaction", "prohibitions", "autoload_skills",
    "skills", "mutates", "spawns", "interactive", "web",
}


def load_and_validate() -> dict[str, Any]:
    errors: list[str] = []
    try:
        data = json.loads(ROLE_SPEC.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read canonical role catalogue: {exc}")

    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if data.get("schema_version") != "bbk.roles.v2":
        errors.append("schema_version must equal bbk.roles.v2")
    if data.get("package_version") != version:
        errors.append(f"package_version {data.get('package_version')!r} != {version!r}")
    constitution_modules = data.get("constitution_modules")
    if not isinstance(constitution_modules, dict) or not constitution_modules:
        errors.append("constitution_modules must be a non-empty object")
        constitution_modules = {}
    else:
        for module, clauses in constitution_modules.items():
            if not isinstance(module, str) or not module.strip():
                errors.append("constitution module names must be non-empty strings")
            if not isinstance(clauses, list) or not clauses or not all(
                isinstance(item, str) and item.strip() for item in clauses
            ):
                errors.append(f"constitution module {module!r} must be a non-empty string list")
        if "core" not in constitution_modules:
            errors.append("constitution_modules must define core")

    roles = data.get("roles")
    if not isinstance(roles, list) or not roles:
        errors.append("roles must be a non-empty array")
        roles = []

    method = json.loads(METHOD_SPEC.read_text(encoding="utf-8"))
    known_skills = set((method.get("skills") or {}).keys())
    ids: set[str] = set()
    names: set[str] = set()
    for index, raw in enumerate(roles):
        where = f"roles[{index}]"
        if not isinstance(raw, dict):
            errors.append(f"{where} must be an object")
            continue
        missing = sorted(REQUIRED_ROLE_FIELDS - set(raw))
        extra = sorted(set(raw) - REQUIRED_ROLE_FIELDS)
        if missing:
            errors.append(f"{where} missing fields: {missing}")
        if extra:
            errors.append(f"{where} unexpected fields: {extra}")
        role_id = raw.get("id")
        name = raw.get("name")
        if not isinstance(role_id, str) or not role_id:
            errors.append(f"{where}.id must be non-empty")
        elif role_id in ids:
            errors.append(f"duplicate role id: {role_id}")
        else:
            ids.add(role_id)
        if name != f"bbk_{role_id}":
            errors.append(f"{where}.name must equal bbk_<id>")
        if name in names:
            errors.append(f"duplicate role name: {name}")
        elif isinstance(name, str):
            names.add(name)
        for field in (
            "constitution", "scope", "responsibilities", "escalations",
            "user_interaction", "prohibitions", "autoload_skills", "skills", "spawns",
        ):
            values = raw.get(field)
            if not isinstance(values, list) or not all(
                isinstance(x, str) and x.strip() for x in values
            ):
                errors.append(f"{where}.{field} must be a string list")
        if not raw.get("scope"):
            errors.append(f"{where}.scope must not be empty")
        if not raw.get("escalations"):
            errors.append(f"{where}.escalations must not be empty")
        selected_modules = raw.get("constitution") or []
        if selected_modules and selected_modules[0] != "core":
            errors.append(f"{where}.constitution must begin with core")
        if len(selected_modules) != len(set(selected_modules)):
            errors.append(f"{where}.constitution contains duplicates")
        unknown_modules = sorted(set(selected_modules) - set(constitution_modules))
        if unknown_modules:
            errors.append(f"{where} references unknown constitution modules: {unknown_modules}")
        delegation = raw.get("delegation")
        if not isinstance(delegation, dict) or not all(
            isinstance(child, str) and child.strip() and isinstance(trigger, str) and trigger.strip()
            for child, trigger in (delegation or {}).items()
        ):
            errors.append(f"{where}.delegation must be an object of child-role to trigger text")
            delegation = {}
        spawns = raw.get("spawns") or []
        if set(delegation) != set(spawns):
            errors.append(f"{where}.delegation keys must exactly match spawns")
        for field in ("mutates", "interactive", "web"):
            if not isinstance(raw.get(field), bool):
                errors.append(f"{where}.{field} must be boolean")
        if raw.get("interactive") and not raw.get("user_interaction"):
            errors.append(f"{where} is interactive but has no user_interaction contract")
        if raw.get("interactive") is False and raw.get("user_interaction"):
            errors.append(f"{where} is non-interactive but declares user_interaction")
        if raw.get("spawns") and "coordination" not in selected_modules:
            errors.append(f"{where} has child agents but lacks the coordination constitution")
        if raw.get("mutates") and "execution" not in selected_modules:
            errors.append(f"{where} mutates but lacks the execution constitution")
        if raw.get("family") == "planning" and "planning" not in selected_modules:
            errors.append(f"{where} is a planning role but lacks the planning constitution")
        if raw.get("family") == "review" and "assurance" not in selected_modules:
            errors.append(f"{where} is a review role but lacks the assurance constitution")
        skills = raw.get("skills") or []
        autoload_skills = raw.get("autoload_skills") or []
        unknown_skills = sorted(set(skills) - known_skills)
        if unknown_skills:
            errors.append(f"{where} references unknown skills: {unknown_skills}")
        unknown_autoload = sorted(set(autoload_skills) - set(skills))
        if unknown_autoload:
            errors.append(f"{where}.autoload_skills must be a subset of skills: {unknown_autoload}")
        if len(autoload_skills) != len(set(autoload_skills)):
            errors.append(f"{where}.autoload_skills contains duplicates")
        if len(autoload_skills) > 3:
            errors.append(f"{where}.autoload_skills must remain focused at three or fewer procedures")
        if "bbk" in skills or "bbk" in autoload_skills:
            errors.append(f"{where} must not load the top-level bbk entry-controller skill")

    known_names = {f"bbk_{role_id}" for role_id in ids}
    for index, raw in enumerate(roles):
        if not isinstance(raw, dict):
            continue
        unknown = sorted(set(raw.get("spawns") or []) - known_names)
        if unknown:
            errors.append(f"roles[{index}] references unknown spawned roles: {unknown}")

    by_id = {raw.get("id"): raw for raw in roles if isinstance(raw, dict)}
    questioning = by_id.get("questioning_wayfinder")
    if questioning is None:
        errors.append("the canonical role topology requires questioning_wayfinder")
    else:
        if "bbk_question_guide" not in questioning.get("spawns", []):
            errors.append("questioning_wayfinder must spawn bbk_question_guide")
    for parent_id in ("root_wayfinder", "territory_wayfinder"):
        parent = by_id.get(parent_id)
        if parent is None or "bbk_questioning_wayfinder" not in parent.get("spawns", []):
            errors.append(f"{parent_id} must route decision branches through bbk_questioning_wayfinder")
        if parent is None or "bbk_planning_wayfinder" not in parent.get("spawns", []):
            errors.append(f"{parent_id} must be able to route accepted design through bbk_planning_wayfinder")
        if parent is not None and "bbk_question_guide" in parent.get("spawns", []):
            errors.append(f"{parent_id} must not bypass bbk_questioning_wayfinder for direct Question Guide spawning")
    territory = by_id.get("territory_wayfinder")
    if territory is not None and territory.get("interactive") is not False:
        errors.append("territory_wayfinder must route material human interaction through the Questioning Wayfinder and user-facing parent")
    planning = by_id.get("planning_wayfinder")
    if planning is None or "bbk_phase_wayfinder" not in planning.get("spawns", []):
        errors.append("planning_wayfinder must spawn bbk_phase_wayfinder")
    guide = by_id.get("question_guide")
    if guide is None or "bbk-grill" not in guide.get("skills", []):
        errors.append("question_guide must load the escalation-only bbk-grill procedure")
    for role_id in ("root_wayfinder", "territory_wayfinder", "questioning_wayfinder", "planning_wayfinder", "phase_wayfinder"):
        role = by_id.get(role_id)
        if role is None or "bbk-wayfind" not in role.get("skills", []):
            errors.append(f"{role_id} must load bbk-wayfind")

    # Every canonical role must be reachable from the root entrypoint through
    # the same direct-child topology projected into OMP and non-OMP hosts.
    by_name = {raw.get("name"): raw for raw in roles if isinstance(raw, dict)}
    reachable: set[str] = set()
    stack = ["bbk_root_wayfinder"]
    while stack:
        current = stack.pop()
        if current in reachable or current not in by_name:
            continue
        reachable.add(current)
        stack.extend(by_name[current].get("spawns", []))
    unreachable = sorted(known_names - reachable)
    if unreachable:
        errors.append(f"roles unreachable from bbk_root_wayfinder: {unreachable}")

    if errors:
        print("BBK role catalogue errors:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        raise SystemExit(1)
    return data


def rendered(data: dict[str, Any]) -> bytes:
    return (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = load_and_validate()
    expected = rendered(data)
    if args.check:
        if ROLE_SPEC.read_bytes() != expected:
            print(f"drift: {ROLE_SPEC.relative_to(ROOT)} is not canonically serialized", file=sys.stderr)
            return 1
        print(f"OK: {len(data['roles'])} canonical roles validated in {ROLE_SPEC.relative_to(ROOT)}")
        return 0
    ROLE_SPEC.write_bytes(expected)
    print(f"normalized {len(data['roles'])} roles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
