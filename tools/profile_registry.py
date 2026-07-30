#!/usr/bin/env python3
"""Build the installation-specific BBK language-profile registry and skill."""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Sequence

REGISTRY_SKILL_NAME = "bbk-installed-profiles"
REGISTRY_RELATIVE_PATH = PurePosixPath(REGISTRY_SKILL_NAME) / "SKILL.md"


def _frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return {}
    try:
        end = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration:
        return {}
    values: dict[str, str] = {}
    for raw in lines[1:end]:
        if not raw.strip() or raw.lstrip().startswith("#") or ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value[:1] == value[-1:] and value[:1] in {'"', "'"}:
            value = value[1:-1]
        if key and value:
            values[key] = value
    return values


def _skill_root(item: Any) -> Path | None:
    installation = item.profile.get("installation") or {}
    raw = installation.get("skill_root")
    if not isinstance(raw, str) or not raw:
        return None
    return item.root.joinpath(*PurePosixPath(raw).parts)


def profile_skills(item: Any) -> list[dict[str, str]]:
    """Return deterministic, declared skill metadata for one prepared profile."""
    root = _skill_root(item)
    declared = item.profile.get("skills") or []
    values: list[dict[str, str]] = []
    if not isinstance(declared, list):
        declared = []
    for raw in declared:
        if not isinstance(raw, dict):
            continue
        skill_id = raw.get("id")
        kind = raw.get("kind")
        raw_path = raw.get("path")
        if not all(isinstance(value, str) and value for value in (skill_id, kind, raw_path)):
            continue
        rel = PurePosixPath(raw_path)
        skill_file = item.root.joinpath(*rel.parts)
        description = ""
        directory = rel.parent.name
        if skill_file.is_file():
            meta = _frontmatter(skill_file.read_text(encoding="utf-8", errors="replace"))
            description = meta.get("description", "")
            directory = skill_file.parent.name
        elif root is not None:
            fallback = root / skill_id / "SKILL.md"
            if fallback.is_file():
                meta = _frontmatter(fallback.read_text(encoding="utf-8", errors="replace"))
                description = meta.get("description", "")
                directory = fallback.parent.name
        values.append(
            {
                "id": skill_id,
                "name": skill_id,
                "kind": kind,
                "path": rel.as_posix(),
                "directory": directory,
                "description": description,
            }
        )
    if not values and root is not None and root.is_dir():
        # Legacy/minimal profiles may predate the explicit PROFILE.json skill
        # inventory. Preserve installability while keeping the fallback visibly
        # undesignated in the machine-readable registry.
        for skill_file in sorted(root.glob("*/SKILL.md"), key=lambda path: path.parent.name.casefold()):
            meta = _frontmatter(skill_file.read_text(encoding="utf-8", errors="replace"))
            skill_id = meta.get("name") or skill_file.parent.name
            values.append(
                {
                    "id": skill_id,
                    "name": skill_id,
                    "kind": "undesignated",
                    "path": skill_file.relative_to(item.root).as_posix(),
                    "directory": skill_file.parent.name,
                    "description": meta.get("description", ""),
                }
            )
    return sorted(values, key=lambda value: (value["id"].casefold(), value["kind"].casefold()))


def profile_router_skill(item: Any, skills: Sequence[dict[str, str]] | None = None) -> str | None:
    """Return the profile-declared router skill, with conservative fallbacks."""
    values = list(skills if skills is not None else profile_skills(item))
    routers = sorted(entry["id"] for entry in values if entry.get("kind") == "router")
    if len(routers) == 1:
        return routers[0]
    if len(routers) > 1:
        return None
    names = [entry["id"] for entry in values]
    exact = f"bbk-{item.profile_id}"
    if exact in names:
        return exact
    bbk_names = sorted(name for name in names if name.startswith("bbk-"))
    if len(bbk_names) == 1:
        return bbk_names[0]
    if item.profile_id in names:
        return item.profile_id
    if len(names) == 1:
        return names[0]
    return None


def profile_cli_command(item: Any) -> str | None:
    installation = item.profile.get("installation") or {}
    raw = installation.get("cli")
    if not isinstance(raw, str) or not raw:
        return None
    return PurePosixPath(raw).stem.replace("_", "-")


def profile_capabilities(item: Any) -> list[dict[str, str]]:
    values: list[dict[str, str]] = []
    capabilities = item.profile.get("capabilities") or {}
    if not isinstance(capabilities, dict):
        return values
    for name, contract in sorted(capabilities.items()):
        if not isinstance(contract, dict):
            continue
        status = contract.get("status")
        if isinstance(status, str) and status:
            values.append({"name": name, "status": status})
    return values


def profile_runtime_summary(item: Any) -> dict[str, Any]:
    skills = profile_skills(item)
    return {
        "id": item.profile_id,
        "version": item.version,
        "name": item.profile.get("name"),
        "description": item.profile.get("description"),
        "package": item.package_name,
        "router_skill": profile_router_skill(item, skills),
        "skill_count": len(skills),
        "skills": skills,
        "cli_command": profile_cli_command(item),
        "capabilities": profile_capabilities(item),
    }


def registry_data(items: Iterable[Any], *, bbk_version: str) -> dict[str, Any]:
    profiles = sorted(
        (profile_runtime_summary(item) for item in items),
        key=lambda value: (str(value["id"]), str(value["version"])),
    )
    return {
        "schema": "bbk.installed-profile-registry.v1",
        "bbk_version": bbk_version,
        "profiles": profiles,
    }


def registry_json_bytes(items: Iterable[Any], *, bbk_version: str) -> bytes:
    return (
        json.dumps(registry_data(items, bbk_version=bbk_version), indent=2, ensure_ascii=False, sort_keys=True)
        + "\n"
    ).encode("utf-8")


def _capability_text(profile: dict[str, Any]) -> str:
    values = profile.get("capabilities") or []
    if not values:
        return "not declared"
    return ", ".join(f"{item['name']}={item['status']}" for item in values)


def registry_skill_text(items: Iterable[Any], *, bbk_version: str) -> str:
    registry = registry_data(items, bbk_version=bbk_version)
    lines = [
        "---",
        f"name: {REGISTRY_SKILL_NAME}",
        "description: Installation-specific registry of language and domain profiles managed by the active BBK install manifest. Consult before material language-, framework-, runtime-, or toolchain-specific work.",
        "---",
        "",
        "# Installed BBK language and domain profiles",
        "",
        "This skill is generated by the BBK installer from independently verified profile packages. It identifies what this installation actually provides; it does not prove that a profile applies to the current subject or that its external toolchain is available.",
        "",
        "## Use",
        "",
        "1. Match the exact repository language, framework, runtime, and toolchain surface to the smallest applicable installed profile. Confirm the live discovery set with `bbk --json profile list`; project-local paths and `BBK_PROFILE_PATH` can change precedence.",
        "2. Load the profile's router skill first. Let that router and `bbk-profile-routing` select only the focused worker, reviewer, gate, and evidence modules needed for the current role and assertion.",
        "3. Run the profile's preflight or resolution command when material assumptions, environment identity, gate selection, or a profile lock are required.",
        "4. Pass the selected profile identity, router skill, effective digest or lock, and required gates into delegated work. Do not assume a child agent inherits them from ambient context.",
        "5. Treat missing required profile capability or external tooling as `BLOCKED`; do not substitute model memory for an unavailable qualified procedure.",
        "",
        "## Installed profiles",
        "",
    ]
    profiles = registry["profiles"]
    if not profiles:
        lines += [
            "No language or domain profile is managed by this BBK installation.",
            "",
            "Use generic BBK procedure only, or reinstall with `--language-profiles`. Do not infer that a profile is installed merely because a similarly named skill, command, or model capability exists elsewhere on the host.",
            "",
        ]
    else:
        for profile in profiles:
            identity = f"{profile['id']}@{profile['version']}"
            lines += [f"### `{identity}` — {profile.get('name') or profile['id']}", ""]
            # Keep the autoloaded registry compact. Full descriptions and the
            # complete focused-skill inventory remain in
            # effective-language-profiles.json and the install manifest.
            router = profile.get("router_skill")
            lines.append(f"- Router skill: `{router}`" if router else "- Router skill: not declared; select a named profile skill explicitly.")
            cli = profile.get("cli_command")
            lines.append(f"- CLI: `{cli}`" if cli else "- CLI: not installed")
            lines.append(f"- Focused skills available: {profile.get('skill_count', 0)}")
            lines.append(f"- Declared capability status: {_capability_text(profile)}")
            lines.append("")
    lines += [
        "## Authority boundary",
        "",
        "An installed profile may add procedures, review criteria, gate recipes, context selectors, or evidence adapters. It does not expand work scope, grant filesystem/network/tool effects, waive generic BBK invariants, reduce assurance, declare success, or authorize release.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def registry_skill_bytes(items: Iterable[Any], *, bbk_version: str) -> bytes:
    return registry_skill_text(items, bbk_version=bbk_version).encode("utf-8")


def source_placeholder_skill(*, bbk_version: str) -> str:
    """Canonical source-tree form used before an installation is bound."""
    text = registry_skill_text([], bbk_version=bbk_version)
    marker = (
        "This package-source placeholder is not an installation inventory. "
        "The installer replaces it at the managed skill destination with an exact registry for the selected profile packages.\n\n"
    )
    needle = "# Installed BBK language and domain profiles\n\n"
    return text.replace(needle, needle + marker, 1)
