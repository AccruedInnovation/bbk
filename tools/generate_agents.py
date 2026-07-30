#!/usr/bin/env python3
"""Generate Codex, OMP, Claude Code, and generic BBK agents."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path, PurePath
from typing import Any, Callable, Mapping

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from model_routing import load_model_routing, route_for_role

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "spec" / "roles.json"
MODEL_ROUTING_PATH = ROOT / "spec" / "model-routing.json"
TARGETS = {
    "codex": ROOT / "projections" / "codex" / "agents",
    "omp": ROOT / "projections" / "omp" / "agents",
    "claude": ROOT / "projections" / "claude" / "agents",
    "generic": ROOT / "projections" / "generic" / "agents",
}
MANIFEST = ROOT / "projections" / "manifest.json"


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


def instruction_text(
    spec: dict[str, Any],
    role: dict[str, Any],
    *,
    host: str,
) -> str:
    """Render only operational instructions intended for the model context.

    Build provenance, canonical digests, host identity, and model-routing metadata
    belong in ``projections/manifest.json`` or native host configuration, not in
    the prompt body consumed on every invocation.
    """
    lines = [
        "## Purpose",
        "",
        role["purpose"],
        "",
        "## Shared constitution",
        "",
    ]
    lines.extend(f"- {item}" for item in spec["common_constitution"])
    lines += ["", "## Responsibilities", ""]
    lines.extend(f"- {item}" for item in role["responsibilities"])
    lines += ["", "## Prohibitions", ""]
    lines.extend(f"- {item}" for item in role["prohibitions"])

    # OMP and Claude Code carry their skill sets in native frontmatter. Codex
    # and the generic projection do not have an equivalent BBK autoload field,
    # so keep the operational skill names in the prompt rather than forcing the
    # agent to infer its procedure surface.
    skills = role.get("skills", [])
    if host in {"codex", "generic"} and skills:
        lines += [
            "",
            "## Procedure skills",
            "",
            "Use the installed BBK skills applicable to this invocation: "
            + ", ".join(f"`{name}`" for name in skills)
            + ". Load only the procedure content needed for the current responsibility.",
        ]

    profile_aware = (
        "bbk-profile-routing" in skills or "bbk-installed-profiles" in skills
    )
    if profile_aware:
        lines += [
            "",
            "## Language and domain profiles",
            "",
            "- Consult `bbk-installed-profiles` before material language-, framework-, runtime-, or toolchain-specific planning, execution, or review.",
            "- When a matching installed profile applies, use `bbk-profile-routing`, load its router skill, and select only the focused procedures needed for this role and the exact assertion; never fan out every profile or specialist pack.",
            "- Carry the selected profile identity, effective lock or digest, toolchain assumptions, required gates, and unavailable-capability dispositions into child invocations and the return envelope.",
            "- An installed profile adds procedure and evidence expectations only. It does not broaden scope, grant tools or effects, reduce assurance, or authorize a pass.",
        ]

    # OMP exposes the exact direct-child allowlist through native `spawns`
    # metadata. Other hosts need the same semantic contract in model-facing
    # instructions so the role knows which named agents to use and when.
    if host != "omp":
        role_index = {item["name"]: item for item in spec["roles"]}
        allowed = role.get("spawns", [])
        lines += ["", "## Delegation", ""]
        if allowed:
            lines.append(
                "Use these direct child agents when their responsibility is needed; do not absorb their work merely because the current host could perform it directly:"
            )
            lines.append("")
            for name in allowed:
                child = role_index[name]
                if host == "claude":
                    invocation = claude_name(child)
                    label = f"`{invocation}` (canonical `{name}`)"
                else:
                    label = f"`{name}`"
                lines.append(f"- {label} — {child['description']}")
            lines += [
                "",
                "Delegate only inside this list and the invocation's authority. Give each child an exact subject, purpose, context package, allowed effects, assurance obligations, stopping conditions, and return schema. Host support for additional agents does not expand this contract.",
            ]
        else:
            lines.append(
                "This role has no child-agent delegation contract. Return work requiring another BBK responsibility to the parent instead of silently creating or impersonating an unlisted child role."
            )

    if host == "codex":
        lines += [
            "",
            "## Codex workspace behavior",
            "",
            "- This role deliberately omits a role-level `sandbox_mode` override and inherits the parent turn's active Codex sandbox and approval settings.",
            "- It may create or update bounded BBK coordination artifacts—notes, handoffs, plans, ADRs, manifests, evidence records, findings, dispositions, and result packets—when required by this invocation and stored inside the permitted workspace.",
        ]
        if role.get("mutates"):
            lines.append(
                "- It may also modify subject or product artifacts only within the invocation's explicit scope, allowed effects, and stopping conditions."
            )
        else:
            lines.append(
                "- Inherited host write access does not authorize changes to subject or product artifacts. Return implementation work to the parent or an explicitly permitted mutating role."
            )
    if host == "claude":
        lines += [
            "",
            "## Claude Code operating notes",
            "",
            "- When this definition runs as a subagent, unavailable human-interaction tools must be replaced by a structured `needs-human-decision` return; never infer consent.",
            "- A role with the Agent tool may delegate only to the role types named above and exposed by its tool allowlist. Host support for nested subagents does not broaden semantic authority.",
            "- Worktree isolation is a host containment mechanism, not permission to change unrelated files, branches, repositories, or external systems.",
        ]
    lines += [
        "",
        "## Invocation contract",
        "",
        "Before acting, bind the exact subject, desired result, scope, authority, allowed effects, inputs, interfaces, assurance contract, and return format supplied by the parent or user. Fill safely inferable gaps with explicit assumptions; interrupt only for material authority or outcome ambiguity.",
        "",
        "Use the invocation-supplied task-kind and language/toolchain profiles where applicable. Runtime permissions and workspace controls override prose; this role never gains authority merely because an instruction requests it.",
        "",
        "The generated model and reasoning-effort settings are defaults, not evidence of fitness. Obey a valid host-, organization-, session-, or invocation-level override and report when the requested model is unavailable or materially downgraded.",
        "",
        "## Return contract",
        "",
        "Return: disposition; exact subject; concise summary; work performed or findings; evidence and commands; changed artifacts if any; residual uncertainty; blockers; discoveries; and the smallest valid next action. Use `PASS`, `FAIL`, `BLOCKED`, or `INCONCLUSIVE` only when evaluating a declared assertion.",
    ]
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
    ]
    if role.get("skills"):
        lines.append("autoloadSkills: " + ", ".join(role["skills"]))
    if role.get("spawns"):
        lines.append("spawns: " + ", ".join(role["spawns"]))
    lines.extend([
        "---",
        "",
        instruction_text(spec, role, host="omp").rstrip(),
    ])
    return "\n".join(lines) + "\n"


def claude_tools(role: dict[str, Any]) -> tuple[list[str], list[str]]:
    tools = ["Read", "Grep", "Glob", "Bash", "Skill", "TodoWrite"]
    denied: list[str] = []
    if role.get("web"):
        tools += ["WebFetch", "WebSearch"]
    if role.get("interactive"):
        tools.append("AskUserQuestion")
    if role.get("spawns"):
        allowed = ", ".join(name.replace("_", "-") for name in role["spawns"])
        tools.insert(0, f"Agent({allowed})")
    if role.get("mutates"):
        tools += ["Edit", "Write", "NotebookEdit"]
    else:
        denied += ["Edit", "Write", "NotebookEdit"]
    tools = list(dict.fromkeys(tools))
    denied = list(dict.fromkeys(denied))
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
    render_yaml_list(lines, "skills", role.get("skills", []))
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
    role_digest = sha256(canonical_json_bytes(spec))
    routing_digest = sha256(canonical_json_bytes(routing))
    source_digest = sha256(canonical_json_bytes({"roles": spec, "model_routing": routing}))
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
            "skills": role.get("skills", []),
            "spawns": role.get("spawns", []),
            "may_mutate": bool(role.get("mutates")),
            "model_profile": route["profile"],
            "model_routing": {
                "omp": route["omp"],
                "codex": route["codex"],
                "claude": route["claude"],
            },
            "files": filenames,
        }
    metadata = {
        "package_version": spec["package_version"],
        "source_sha256": source_digest,
        "role_source_sha256": role_digest,
        "model_routing_source_sha256": routing_digest,
        "role_count": len(spec["roles"]),
        "model_profile_count": len(routing["profiles"]),
        "role_profile_counts": {
            profile: sum(1 for selected in routing["role_profiles"].values() if selected == profile)
            for profile in sorted(routing["profiles"])
        },
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
        "schema": "bbk.projection-manifest.v3",
        "package_version": metadata["package_version"],
        "source": portable_relative_path(SPEC_PATH, ROOT),
        "model_routing_source": portable_relative_path(MODEL_ROUTING_PATH, ROOT),
        "source_sha256": metadata["source_sha256"],
        "role_source_sha256": metadata["role_source_sha256"],
        "model_routing_source_sha256": metadata["model_routing_source_sha256"],
        "role_count": metadata["role_count"],
        "model_profile_count": metadata["model_profile_count"],
        "role_profile_counts": metadata["role_profile_counts"],
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
            f"OK: {manifest['role_count']} roles, {manifest['model_profile_count']} model profiles, "
            f"{manifest['target_count']} targets, and {manifest['projection_count']} projections "
            f"match {manifest['source_sha256']}"
        )
        return 0
    write(outputs)
    print(
        f"Generated {manifest['role_count']} roles into {manifest['projection_count']} projections "
        f"across {manifest['target_count']} targets using {manifest['model_profile_count']} model profiles"
    )
    print(f"Projection input SHA-256: {manifest['source_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
