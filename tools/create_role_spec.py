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
    "responsibilities", "prohibitions", "skills", "mutates", "spawns",
    "interactive", "web",
}


def load_and_validate() -> dict[str, Any]:
    errors: list[str] = []
    try:
        data = json.loads(ROLE_SPEC.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read canonical role catalogue: {exc}")

    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if data.get("schema_version") != "bbk.roles.v1":
        errors.append("schema_version must equal bbk.roles.v1")
    if data.get("package_version") != version:
        errors.append(f"package_version {data.get('package_version')!r} != {version!r}")
    constitution = data.get("common_constitution")
    if not isinstance(constitution, list) or not constitution or not all(isinstance(x, str) and x.strip() for x in constitution):
        errors.append("common_constitution must be a non-empty string list")

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
        for field in ("responsibilities", "prohibitions", "skills", "spawns"):
            values = raw.get(field)
            if not isinstance(values, list) or not all(isinstance(x, str) and x for x in values):
                errors.append(f"{where}.{field} must be a string list")
        for field in ("mutates", "interactive", "web"):
            if not isinstance(raw.get(field), bool):
                errors.append(f"{where}.{field} must be boolean")
        unknown_skills = sorted(set(raw.get("skills") or []) - known_skills)
        if unknown_skills:
            errors.append(f"{where} references unknown skills: {unknown_skills}")

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
        if parent is not None and "bbk_question_guide" in parent.get("spawns", []):
            errors.append(f"{parent_id} must not bypass bbk_questioning_wayfinder for direct Question Guide spawning")

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
