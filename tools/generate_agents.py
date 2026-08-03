#!/usr/bin/env python3
"""Generate Codex, OMP, Claude Code, and generic BBK agents."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from functools import lru_cache
from pathlib import Path, PurePath
from typing import Any, Callable, Mapping

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from model_routing import load_model_routing, route_for_role, routing_statistics
from prompt_modules import (
    PromptModuleError,
    compact_skill_template,
    load_prompt_modules,
    module_directives,
    ordered_modules,
    source_manifest as prompt_module_source_manifest,
    strip_frontmatter,
    validate_skill_templates,
)
from return_contracts import render_return_contract_prompt

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "spec" / "roles.json"
MODEL_ROUTING_PATH = ROOT / "spec" / "model-routing.json"
METHOD_CONTENT_PATH = ROOT / "spec" / "method-content.json"
TARGETS = {
    "codex": ROOT / "projections" / "codex" / "agents",
    "omp": ROOT / "projections" / "omp" / "agents",
    "claude": ROOT / "projections" / "claude" / "agents",
    "generic": ROOT / "projections" / "generic" / "agents",
}
MANIFEST = ROOT / "projections" / "manifest.json"



@lru_cache(maxsize=1)
def prompt_module_package():
    try:
        return load_prompt_modules(ROOT)
    except PromptModuleError as exc:
        raise ValueError("invalid prompt-module package: " + "; ".join(exc.errors)) from exc


@lru_cache(maxsize=1)
def canonical_method_content() -> dict[str, Any]:
    try:
        value = json.loads(METHOD_CONTENT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load canonical method content: {exc}") from exc
    package = prompt_module_package()
    errors = validate_skill_templates(value, package)
    if value.get("version") != package.catalog.get("package_version"):
        errors.append("method-content and prompt-module package versions differ")
    if errors:
        raise ValueError("invalid canonical method content: " + "; ".join(errors))
    return value


def mandatory_skill_body(name: str) -> str:
    template = canonical_method_content().get("skills", {}).get(name)
    if not isinstance(template, str) or not template.strip():
        raise ValueError(f"mandatory skill {name!r} is absent from canonical method content")
    body = strip_frontmatter(compact_skill_template(template, prompt_module_package())).strip()
    if not body:
        raise ValueError(f"mandatory skill {name!r} has an empty compact body")
    return body


def mandatory_skill_sources(spec: dict[str, Any]) -> dict[str, str]:
    names = sorted({
        name
        for role in spec.get("roles", [])
        for name in role.get("mandatory_skills", [])
    })
    return {name: mandatory_skill_body(name) for name in names}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def portable_relative_path(path: PurePath, root: PurePath) -> str:
    """Serialize a package-relative path with stable POSIX separators on every host."""
    return path.relative_to(root).as_posix()


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def toml_multiline(value: str) -> str:
    return '"""' + value.replace("\\", "\\\\").replace('"""', '\\"\\"\\"') + '"""'


def yaml_scalar(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def claude_name(role: dict[str, Any]) -> str:
    value = role["name"].replace("_", "-").lower()
    if not re.fullmatch(r"[a-z][a-z0-9-]*", value):
        raise ValueError(f"Claude agent name is invalid: {value}")
    return value


@lru_cache(maxsize=None)
def load_skill(name: str) -> dict[str, Any]:
    template = canonical_method_content().get("skills", {}).get(name)
    if not isinstance(template, str) or not template.strip():
        raise ValueError(f"unknown canonical skill {name!r}")
    body = mandatory_skill_body(name)
    encoded = body.encode("utf-8")
    template_encoded = template.encode("utf-8")
    return {
        "name": name,
        "path": f"shared/skills/{name}/SKILL.md",
        "source": f"spec/method-content.json#skills/{name}",
        "bytes": len(encoded),
        "sha256": sha256(encoded),
        "template_bytes": len(template_encoded),
        "template_sha256": sha256(template_encoded),
        "prompt_modules": list(module_directives(template)),
    }


def mandatory_skill_metadata(role: dict[str, Any]) -> list[dict[str, Any]]:
    return [load_skill(name) for name in role.get("mandatory_skills", [])]

def render_role_prompt_module(module: Mapping[str, Any], *, tagged: bool) -> str:
    """Render one behavior-bearing module exactly once.

    OMP retains authenticated markers. Codex keeps the model-facing body free of
    BBK XML-like metadata while preserving the module identity in Markdown.
    """
    heading = f'### Shared module: `{module["id"]}` — {module["title"]}'
    body = "\n".join([heading, "", *[f'- {clause["text"]}' for clause in module["clauses"]]])
    if not tagged:
        return body
    return (
        f'<bbk-prompt-module id="{module["id"]}">\n'
        f'{body}\n'
        '</bbk-prompt-module>'
    )

def instruction_text(
    spec: dict[str, Any],
    role: dict[str, Any],
    *,
    host: str,
) -> str:
    """Render one self-contained role prompt from canonical contracts.

    Role-specific purpose, scope, responsibility, topology, and return contracts
    remain explicit. Shared cross-role behavior is embedded once per assigned
    prompt module. Mandatory procedure templates retain only compact references
    to those already embedded modules.
    """
    constitution = spec["constitution_modules"]
    constitution_clauses: list[str] = []
    for module_name in role["constitution"]:
        constitution_clauses.extend(constitution[module_name])

    package = prompt_module_package()
    mandatory_skills = role.get("mandatory_skills", [])
    skills = role.get("skills", [])
    on_demand = [name for name in skills if name not in mandatory_skills]
    assigned_modules = ordered_modules(package, role.get("prompt_modules", []))
    human_request_originators = set(spec["interaction_topology"]["human_request_originators"])
    may_originate_human_request = role["name"] in human_request_originators

    lines: list[str] = []
    tagged_contract = host != "codex"
    if tagged_contract:
        lines += [
            f'<bbk-role-contract role="{role["name"]}" package-version="{spec["package_version"]}">',
            "",
        ]

    lines += [
        "## Runtime identity and interaction topology",
        "",
        f"You are the canonical `{role['name']}` BBK child role.",
        "",
        "Apply the role contract, embedded modules, and mandatory procedures as one instruction set.",
        "",
        "## Purpose",
        "",
        role["purpose"],
        "",
        "## Constitution",
        "",
    ]
    lines.extend(f"- {item}" for item in constitution_clauses)

    lines += ["", "## Scope", ""]
    lines.extend(f"- {item}" for item in role["scope"])

    lines += ["", "## Responsibilities", ""]
    lines.extend(f"- {item}" for item in role["responsibilities"])

    lines += [
        "",
        "## Shared behavior modules — embedded once",
        "",
        "Each module is active once for the whole invocation.",
    ]
    for module in assigned_modules:
        lines += ["", render_role_prompt_module(module, tagged=host != "codex")]

    lines += ["", "## Delegation", ""]
    delegation = role.get("delegation", {})
    if delegation:
        if host == "omp":
            lines.append("The native `spawns` allowlist constrains direct children. Use a child only for its declared trigger:")
        else:
            lines.append("Use only these direct child agents, and only for their declared trigger:")
        lines.append("")
        role_index = {item["name"]: item for item in spec["roles"]}
        for child_name in role.get("spawns", []):
            trigger = delegation[child_name]
            child = role_index[child_name]
            if host == "claude":
                label = f"`{claude_name(child)}` (canonical `{child_name}`)"
            else:
                label = f"`{child_name}`"
            lines.append(f"- {label} — when {trigger}.")
        if host == "omp":
            lines += [
                "",
                "For the OMP batch `task` form, set each task's `agent` to the exact permitted canonical `bbk_*` role, use a stable logical `name`, and provide a complete self-contained `task`. For the flat form, follow the advertised schema and use a durable `local://` context file for reusable shared background.",
            ]
    else:
        lines.append(
            "This role has no child-agent authority. Return work requiring another responsibility to the invoking parent rather than spawning, impersonating, or silently absorbing an unlisted role."
        )

    lines += ["", "## Escalation and human relay", ""]
    lines.extend(f"- {item}" for item in role["escalations"])
    human_triggers = role.get("human_decision_triggers", [])
    if human_triggers:
        lines += [
            "",
            "These conditions trigger a controller-mediated human request, never direct user interaction:",
            "",
        ]
        lines.extend(f"- {item}" for item in human_triggers)
    else:
        lines += [
            "",
            "This role has no ordinary user-gateway branch. Report typed blockers or findings through its parent/controller route.",
        ]

    lines += ["", "## Prohibitions", ""]
    lines.extend(f"- {item}" for item in role["prohibitions"])

    lines += ["", "## Procedure skills", ""]
    lines.append(f"Primary procedure: `{role['primary_skill']}`.")
    if mandatory_skills:
        lines.append(
            "Mandatory procedures embedded below: "
            + ", ".join(f"`{name}`" for name in mandatory_skills)
            + "."
        )
    if on_demand:
        lines.append(
            "Additional procedures available on demand: "
            + ", ".join(f"`{name}`" for name in on_demand)
            + ". Load one only when its method is material to the assigned responsibility."
        )

    profile_aware = "bbk-profile-routing" in skills or "bbk-installed-profiles" in skills
    lines += ["", "## Language, domain, toolchain, and model qualification", ""]
    if profile_aware:
        lines.append(
            "Use the embedded `bbk-prompt-profile-qualification` module and the current installed-profile registry to select only the applicable focused procedures and gates."
        )
    else:
        lines.append(
            "Use only a profile or focused procedure supplied by the invocation. Return a profile-resolution blocker when a material specialized method is required but absent."
        )

    if host == "omp":
        lines += [
            "",
            "## OMP hub/IRC communication contract",
            "",
            "- Run as an OMP task subagent. Use `hub`/IRC for live inter-agent communication and the task/yield channel for the final governed result.",
            "- Resolve the harness-root controller with `hub` `op: \"list\"` and the peer whose `kind` is `main`; never infer or invent a peer ID.",
        ]
        if may_originate_human_request:
            lines.append("- This role is a declared human-request originator. Send only its exact controller-mediated request packet to the `main` peer and bind the reply to the stable request; send ordinary coordination to the invoking parent.")
        else:
            lines.append("- This role is not a human-request originator. Send decision, authority, private-context, or acceptance needs as typed blockers to the invoking parent; do not send a direct user request to `main`.")
        lines += [
            "- Wait only when no other authorized work remains, and resume the same logical role after a valid bound response or parent continuation.",
            "- When spawning, carry the main peer, invoking-parent peer, logical parent, branch identity, and exact reply target in the child context edge.",
            "- This replacement prompt excludes OMP generic workflow policy and compatibility-discovered cross-harness instructions unless supplied as governed project data.",
        ]

    if host == "codex":
        lines += [
            "",
            "## Codex workspace and parent-channel behavior",
            "",
            ("- This Codex child cannot converse with the user. Use the declared controller route for exact human requests." if may_originate_human_request else "- This Codex child cannot converse with the user and is not a human-request originator. Return material human needs to the invoking parent through the inter-agent channel or typed terminal result."),
            "- Inherit the parent turn's active sandbox and approval settings. Persist bounded BBK coordination artifacts inside the permitted workspace.",
        ]
        if role.get("mutates"):
            lines.append("- Modify subject or product artifacts only within the exact invocation scope, effects, safeguards, and stopping conditions.")
        else:
            lines.append("- Writable host tools do not authorize subject or product mutation for this non-mutating role.")
        if role.get("spawns"):
            lines += [
                "- Use host continuation/follow-up for the same logical child when possible. The embedded liveness module controls polling, interruption, replacement, and preservation of partial work.",
            ]

    if host == "claude":
        lines += [
            "",
            "## Claude Code operating notes",
            "",
            ("- This Claude Code child has no `AskUserQuestion` authority. Use the declared controller route for exact human requests." if may_originate_human_request else "- This Claude Code child has no `AskUserQuestion` authority and is not a human-request originator. Return material human needs through the parent channel or typed result."),
            "- Agent, Edit, Write, and worktree affordances do not broaden the role's declared delegation or mutation authority.",
        ]

    lines += [
        "",
        "## Invocation contract",
        "",
        "Apply the embedded `bbk-prompt-invocation-binding` module before substantive work. Invocation-, organization-, session-, sandbox-, and runtime-level controls take precedence over a generated default; unavailable or materially downgraded capabilities must be reported truthfully.",
    ]

    if host == "omp":
        lines += [
            "",
            "## Return contract",
            "",
            "The BBK OMP adapter injects the exact role-specific return contract from the installed v4 role catalogue. Treat it as controlling and fail closed if it is absent or inconsistent.",
        ]
    else:
        lines += ["", render_return_contract_prompt(role)]

    if mandatory_skills:
        lines += [
            "",
            "## Mandatory procedures — injected",
            "",
            "Apply these compact canonical procedure templates directly. Their shared module references point to the single embedded copies above.",
        ]
        for name in mandatory_skills:
            body = mandatory_skill_body(name)
            lines.append("")
            if host == "codex":
                lines += [f"### Mandatory procedure: `{name}`", "", body]
            else:
                lines += [
                    f'<bbk-inlined-skill name="{name}" source="spec/method-content.json#skills/{name}">',
                    body,
                    "</bbk-inlined-skill>",
                ]

    if tagged_contract:
        lines += ["", "</bbk-role-contract>"]
    return "\n".join(lines).strip() + "\n"


def render_codex(
    spec: dict[str, Any], role: dict[str, Any], route: dict[str, Any],
    role_digest: str, routing_digest: str, source_digest: str,
) -> str:
    body = instruction_text(spec, role, host="codex")
    codex = route["codex"]
    lines = [
        f"name = {toml_string(role['name'])}",
        f"description = {toml_string(role['description'])}",
        f"model = {toml_string(codex['model'])}",
        f"model_reasoning_effort = {toml_string(codex['model_reasoning_effort'])}",
    ]
    # Semantic mutability is not a Codex sandbox policy. Omitting
    # ``sandbox_mode`` lets every custom agent inherit the parent turn's live
    # sandbox and approval settings, while the role instructions continue to
    # constrain which artifacts the role is authorized to change.
    lines.append(f"developer_instructions = {toml_multiline(body)}")
    return "\n".join(lines) + "\n"


def render_omp(
    spec: dict[str, Any], role: dict[str, Any], route: dict[str, Any],
    role_digest: str, routing_digest: str, source_digest: str,
) -> str:
    omp = route["omp"]
    lines = [
        "---",
        f"name: {role['name']}",
        f"description: {yaml_scalar(role['description'])}",
        f"model: {yaml_scalar(omp['model'])}",
        f"thinkingLevel: {yaml_scalar(omp['thinkingLevel'])}",
        "blocking: false",
    ]
    if role.get("spawns"):
        lines.append("spawns: " + ", ".join(role["spawns"]))
    lines.extend([
        "---",
        "",
        f'<bbk-agent-system role="{role["name"]}" package-version="{spec["package_version"]}">',
        "",
        instruction_text(spec, role, host="omp").rstrip(),
        "",
        "</bbk-agent-system>",
    ])
    return "\n".join(lines) + "\n"


def claude_tools(role: dict[str, Any]) -> tuple[list[str], list[str]]:
    # Host write capability must not be used as a proxy for semantic mutation
    # authority. Every role may need to persist bounded coordination artifacts
    # such as plans, ADRs, handoffs, findings, manifests, or evidence records.
    # Only Worker and Prototyper may alter the governed subject, as constrained
    # by the role prompt and invocation authority.
    tools = ["Read", "Grep", "Glob", "Bash", "Skill", "TodoWrite", "Edit", "Write", "NotebookEdit"]
    denied: list[str] = []
    if role.get("web"):
        tools += ["WebFetch", "WebSearch"]
    if role.get("spawns"):
        allowed = ", ".join(name.replace("_", "-") for name in role["spawns"])
        tools.insert(0, f"Agent({allowed})")
    tools = list(dict.fromkeys(tools))
    return tools, denied


def render_yaml_list(lines: list[str], key: str, values: list[str]) -> None:
    if not values:
        return
    lines.append(f"{key}:")
    lines.extend(f"  - {yaml_scalar(value)}" for value in values)


def render_claude(
    spec: dict[str, Any], role: dict[str, Any], route: dict[str, Any],
    role_digest: str, routing_digest: str, source_digest: str,
) -> str:
    name = claude_name(role)
    tools, denied = claude_tools(role)
    colors = {"planning": "blue", "specialist": "purple", "review": "yellow", "execution": "green"}
    claude = route["claude"]
    lines = [
        "---",
        f"name: {name}",
        f"description: {yaml_scalar(role['description'])}",
        f"model: {yaml_scalar(claude['model'])}",
        f"effort: {yaml_scalar(claude['effort'])}",
        "permissionMode: default",
        f"color: {colors.get(role['family'], 'cyan')}",
    ]
    render_yaml_list(lines, "tools", tools)
    render_yaml_list(lines, "disallowedTools", denied)
    if role.get("mutates"):
        lines.append("isolation: worktree")
    lines.extend([
        "---",
        "",
        instruction_text(spec, role, host="claude").rstrip(),
    ])
    return "\n".join(lines) + "\n"


def render_generic(
    spec: dict[str, Any], role: dict[str, Any], route: dict[str, Any],
    role_digest: str, routing_digest: str, source_digest: str,
) -> str:
    # Generic projections contain only model-facing operational instructions.
    # Machine-readable role, spawn, skill, routing, and provenance metadata lives
    # in projections/manifest.json.
    return instruction_text(spec, role, host="generic")


def rendered_projections(
    model_routing_path: Path = MODEL_ROUTING_PATH,
) -> tuple[dict[str, dict[str, bytes]], dict[str, Any]]:
    """Render every host projection from canonical roles and one routing policy.

    The returned paths are filenames relative to each host's agent directory,
    which lets the installer apply an external routing policy without mutating
    or re-sealing the qualified package tree.
    """
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    routing = load_model_routing(model_routing_path, root=ROOT, role_spec=spec)
    method_content = canonical_method_content()
    module_package = prompt_module_package()
    module_manifest = prompt_module_source_manifest(module_package)
    skill_sources = mandatory_skill_sources(spec)
    role_digest = sha256(canonical_json_bytes(spec))
    routing_digest = sha256(canonical_json_bytes(routing))
    method_content_digest = sha256(METHOD_CONTENT_PATH.read_bytes())
    prompt_module_digest = sha256(canonical_json_bytes(module_manifest))
    mandatory_skill_digest = sha256(canonical_json_bytes(skill_sources))
    source_digest = sha256(canonical_json_bytes({
        "roles": spec,
        "model_routing": routing,
        "method_content": method_content,
        "prompt_module_sources": module_manifest,
        "mandatory_skill_sources": skill_sources,
    }))
    outputs: dict[str, dict[str, bytes]] = {target: {} for target in TARGETS}
    renderers: dict[
        str,
        Callable[[dict[str, Any], dict[str, Any], dict[str, Any], str, str, str], str],
    ] = {
        "codex": render_codex,
        "omp": render_omp,
        "claude": render_claude,
        "generic": render_generic,
    }
    extensions = {"codex": ".toml", "omp": ".md", "claude": ".md", "generic": ".md"}
    agents: dict[str, Any] = {}
    for role in sorted(spec["roles"], key=lambda item: item["name"]):
        route = route_for_role(routing, role["name"])
        filenames: dict[str, str] = {}
        for target, renderer in renderers.items():
            stem = claude_name(role) if target == "claude" else role["name"]
            filename = f"{stem}{extensions[target]}"
            filenames[target] = filename
            outputs[target][filename] = renderer(
                spec, role, route, role_digest, routing_digest, source_digest
            ).encode("utf-8")
        agents[role["name"]] = {
            "family": role["family"],
            "description": role["description"],
            "constitution_modules": role.get("constitution", []),
            "scope": role.get("scope", []),
            "skills": role.get("skills", []),
            "primary_skill": role.get("primary_skill"),
            "mandatory_skills": role.get("mandatory_skills", []),
            "prompt_modules": role.get("prompt_modules", []),
            "inlined_skills": mandatory_skill_metadata(role),
            "spawns": role.get("spawns", []),
            "delegation": role.get("delegation", {}),
            "return_contract": role.get("return_contract", {}),
            "escalations": role.get("escalations", []),
            "human_decision_triggers": role.get("human_decision_triggers", []),
            "user_facing": False,
            "may_mutate": bool(role.get("mutates")),
            "model_route": route["route_id"],
            "model_routing_mode": route["mode"],
            "model_routing": {
                "omp": route["omp"],
                "codex": route["codex"],
                "claude": route["claude"],
            },
            "files": filenames,
        }
    routing_stats = routing_statistics(routing)
    metadata = {
        "package_version": spec["package_version"],
        "contract_package": spec.get("contract_package"),
        "role_return_registry": "spec/contracts/role-return-registry.json",
        "role_return_registry_v2": "spec/contracts/role-return-registry-v2.json",
        "default_role_return_version": "v2",
        "method_content_source": portable_relative_path(METHOD_CONTENT_PATH, ROOT),
        "prompt_module_package": spec.get("prompt_module_package"),
        "source_sha256": source_digest,
        "role_source_sha256": role_digest,
        "model_routing_source_sha256": routing_digest,
        "method_content_source_sha256": method_content_digest,
        "prompt_module_source_sha256": prompt_module_digest,
        "prompt_module_sources": module_manifest["sources"],
        "mandatory_skill_source_sha256": mandatory_skill_digest,
        "mandatory_skill_sources": sorted(skill_sources),
        "role_count": len(spec["roles"]),
        "model_routing_schema": routing["schema_version"],
        "model_routing_mode": routing_stats["mode"],
        "model_route_count": routing_stats["route_count"],
        # Retained internally so install-time v1 compatibility can report legacy
        # profile statistics without exposing profile tiers in the v2 projection manifest.
        "legacy_model_profile_count": routing_stats["profile_count"],
        "legacy_role_profile_counts": routing_stats["role_profile_counts"],
        "target_count": len(TARGETS),
        "projection_count": sum(len(files) for files in outputs.values()),
        "targets": sorted(TARGETS),
        "model_routing_path": model_routing_path.resolve().as_posix(),
        "agents": agents,
    }
    return outputs, metadata


def expected_files() -> tuple[dict[Path, bytes], dict[str, Any]]:
    projections, metadata = rendered_projections(MODEL_ROUTING_PATH)
    outputs: dict[Path, bytes] = {}
    for target, files in projections.items():
        for filename, content in files.items():
            outputs[TARGETS[target] / filename] = content
    manifest_files = {
        portable_relative_path(path, ROOT): sha256(content)
        for path, content in sorted(outputs.items(), key=lambda item: str(item[0]))
    }
    manifest = {
        "schema": "bbk.projection-manifest.v8",
        "package_version": metadata["package_version"],
        "contract_package": metadata["contract_package"],
        "role_return_registry": metadata["role_return_registry"],
        "role_return_registry_v2": metadata["role_return_registry_v2"],
        "default_role_return_version": metadata["default_role_return_version"],
        "source": portable_relative_path(SPEC_PATH, ROOT),
        "model_routing_source": portable_relative_path(MODEL_ROUTING_PATH, ROOT),
        "method_content_source": metadata["method_content_source"],
        "prompt_module_package": metadata["prompt_module_package"],
        "source_sha256": metadata["source_sha256"],
        "role_source_sha256": metadata["role_source_sha256"],
        "model_routing_source_sha256": metadata["model_routing_source_sha256"],
        "method_content_source_sha256": metadata["method_content_source_sha256"],
        "prompt_module_source_sha256": metadata["prompt_module_source_sha256"],
        "prompt_module_sources": metadata["prompt_module_sources"],
        "model_routing_schema": metadata["model_routing_schema"],
        "model_routing_mode": metadata["model_routing_mode"],
        "model_route_count": metadata["model_route_count"],
        "mandatory_skill_source_sha256": metadata["mandatory_skill_source_sha256"],
        "mandatory_skill_sources": metadata["mandatory_skill_sources"],
        "role_count": metadata["role_count"],
        "target_count": metadata["target_count"],
        "projection_count": metadata["projection_count"],
        "targets": metadata["targets"],
        "agents": metadata["agents"],
        "files": manifest_files,
    }
    outputs[MANIFEST] = (
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    ).encode("utf-8")
    return outputs, manifest


def check(outputs: dict[Path, bytes]) -> list[str]:
    errors: list[str] = []
    expected_paths = set(outputs)
    for path, expected in outputs.items():
        if not path.exists():
            errors.append(f"missing: {portable_relative_path(path, ROOT)}")
        elif path.read_bytes() != expected:
            errors.append(f"drift: {portable_relative_path(path, ROOT)}")
    for directory in TARGETS.values():
        if not directory.exists():
            continue
        for path in directory.iterdir():
            if path.is_file() and path not in expected_paths:
                errors.append(f"unexpected generated file: {portable_relative_path(path, ROOT)}")
    return errors


def write(outputs: dict[Path, bytes]) -> None:
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail when generated files are missing or drifted")
    args = parser.parse_args()
    try:
        outputs, manifest = expected_files()
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"BBK agent projection input error: {exc}", file=sys.stderr)
        return 1
    if args.check:
        errors = check(outputs)
        if errors:
            print("BBK agent projection drift detected:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            return 1
        print(
            f"OK: {manifest['role_count']} roles, {manifest['model_route_count']} direct model routes, "
            f"{manifest['target_count']} targets, and {manifest['projection_count']} projections "
            f"match {manifest['source_sha256']}"
        )
        return 0
    write(outputs)
    print(
        f"Generated {manifest['role_count']} roles into {manifest['projection_count']} projections "
        f"across {manifest['target_count']} targets using {manifest['model_route_count']} direct model routes"
    )
    print(f"Projection input SHA-256: {manifest['source_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
