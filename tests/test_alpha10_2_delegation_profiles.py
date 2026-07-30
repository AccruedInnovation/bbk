from __future__ import annotations

import json
import re
import tempfile
import tomllib
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
import sys
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import profile_registry  # noqa: E402


FORBIDDEN_PROMPT_PROVENANCE = (
    "Canonical role:",
    "Host projection:",
    "Model-routing profile:",
    "Canonical role catalogue digest:",
    "Canonical model-routing digest:",
    "projection_source_sha256",
)

PROFILE_AWARE_ROLES = {
    "bbk_root_wayfinder",
    "bbk_territory_wayfinder",
    "bbk_planning_wayfinder",
    "bbk_phase_wayfinder",
    "bbk_prototyper",
    "bbk_synthesizer",
    "bbk_architect",
    "bbk_verification_designer",
    "bbk_worker_designer",
    "bbk_reviewer",
    "bbk_root_orchestrator",
    "bbk_territory_orchestrator",
    "bbk_worker_orchestrator",
    "bbk_validator_orchestrator",
    "bbk_worker",
    "bbk_validator",
}


def _frontmatter_and_body(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise AssertionError(f"missing frontmatter: {path}")
    end = lines.index("---", 1)
    data: dict[str, Any] = {}
    active: str | None = None
    for line in lines[1:end]:
        if line.startswith("  - "):
            if active is None:
                raise AssertionError(f"orphan list item in {path}: {line}")
            value = line[4:]
            try:
                parsed: Any = json.loads(value)
            except json.JSONDecodeError:
                parsed = value
            current = data.setdefault(active, [])
            if not isinstance(current, list):
                raise AssertionError(f"mixed scalar/list field in {path}: {active}")
            current.append(parsed)
            continue
        if not line.strip():
            continue
        key, raw = line.split(":", 1)
        key, raw = key.strip(), raw.strip()
        active = key
        if not raw:
            data[key] = []
            continue
        try:
            data[key] = json.loads(raw)
        except json.JSONDecodeError:
            data[key] = [value.strip() for value in raw.split(",")] if "," in raw else raw
    body = "\n".join(lines[end + 1 :]).lstrip("\n") + ("\n" if text.endswith("\n") else "")
    return data, body


def _codex(path: Path) -> tuple[dict[str, Any], str]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return data, str(data["developer_instructions"])


def _delegated_names(body: str, *, host: str) -> list[str]:
    if "## Delegation" not in body:
        return []
    section = body.split("## Delegation", 1)[1]
    if "\n## " in section:
        section = section.split("\n## ", 1)[0]
    if host == "claude":
        return re.findall(r"^-[^\n]*\(canonical `([^`]+)`\) — ", section, flags=re.MULTILINE)
    return re.findall(r"^- `([^`]+)` — ", section, flags=re.MULTILINE)


@dataclass
class _DummyProfile:
    root: Path
    profile: dict[str, Any]

    @property
    def profile_id(self) -> str:
        return str(self.profile["id"])

    @property
    def version(self) -> str:
        return str(self.profile["version"])

    @property
    def package_name(self) -> str:
        return str(self.profile["package"])


class Alpha102DelegationProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.spec = json.loads((ROOT / "spec" / "roles.json").read_text(encoding="utf-8"))
        cls.roles = {role["name"]: role for role in cls.spec["roles"]}
        cls.manifest = json.loads((ROOT / "projections" / "manifest.json").read_text(encoding="utf-8"))

    def test_non_omp_projections_name_only_the_canonical_allowed_children(self):
        for role_name, role in self.roles.items():
            expected = role.get("spawns", [])
            paths_and_bodies = []
            _, codex_body = _codex(ROOT / "projections" / "codex" / "agents" / f"{role_name}.toml")
            paths_and_bodies.append(("codex", codex_body))
            _, claude_body = _frontmatter_and_body(
                ROOT / "projections" / "claude" / "agents" / f"{role_name.replace('_', '-')}.md"
            )
            paths_and_bodies.append(("claude", claude_body))
            generic_body = (ROOT / "projections" / "generic" / "agents" / f"{role_name}.md").read_text(encoding="utf-8")
            paths_and_bodies.append(("generic", generic_body))

            for host, body in paths_and_bodies:
                self.assertIn("## Delegation", body, f"{host}:{role_name}")
                self.assertEqual(_delegated_names(body, host=host), expected, f"{host}:{role_name}")
                if expected:
                    for child_name in expected:
                        child = self.roles[child_name]
                        if host == "claude":
                            invocation = child_name.replace("_", "-")
                            expected_line = f"- `{invocation}` (canonical `{child_name}`) — {child['description']}"
                        else:
                            expected_line = f"- `{child_name}` — {child['description']}"
                        self.assertIn(expected_line, body, f"{host}:{role_name}")
                    self.assertIn("Delegate only inside this list", body, f"{host}:{role_name}")
                else:
                    self.assertIn("has no child-agent delegation contract", body, f"{host}:{role_name}")

    def test_omp_spawns_remain_machine_metadata_without_prompt_duplication(self):
        for role_name, role in self.roles.items():
            meta, body = _frontmatter_and_body(ROOT / "projections" / "omp" / "agents" / f"{role_name}.md")
            expected = role.get("spawns", [])
            actual = meta.get("spawns", [])
            if isinstance(actual, str):
                actual = [value.strip() for value in actual.split(",") if value.strip()]
            self.assertEqual(actual, expected, role_name)
            self.assertNotIn("## Delegation", body, role_name)

    def test_claude_agent_tool_allowlist_matches_canonical_children(self):
        for role_name, role in self.roles.items():
            meta, _ = _frontmatter_and_body(
                ROOT / "projections" / "claude" / "agents" / f"{role_name.replace('_', '-')}.md"
            )
            tools = meta.get("tools", [])
            agent_tools = [value for value in tools if isinstance(value, str) and value.startswith("Agent(")]
            expected = role.get("spawns", [])
            if not expected:
                self.assertEqual(agent_tools, [], role_name)
                continue
            allowed = ", ".join(value.replace("_", "-") for value in expected)
            self.assertEqual(agent_tools, [f"Agent({allowed})"], role_name)

    def test_prompt_bodies_exclude_build_provenance_and_begin_with_operational_content(self):
        for role_name in self.roles:
            bodies = []
            codex_data, codex_body = _codex(ROOT / "projections" / "codex" / "agents" / f"{role_name}.toml")
            self.assertFalse((ROOT / "projections" / "codex" / "agents" / f"{role_name}.toml").read_text(encoding="utf-8").startswith("#"))
            self.assertEqual(codex_data["name"], role_name)
            bodies.append(("codex", codex_body))
            for host, filename in (
                ("omp", f"{role_name}.md"),
                ("claude", f"{role_name.replace('_', '-')}.md"),
            ):
                _, body = _frontmatter_and_body(ROOT / "projections" / host / "agents" / filename)
                bodies.append((host, body))
            bodies.append(("generic", (ROOT / "projections" / "generic" / "agents" / f"{role_name}.md").read_text(encoding="utf-8")))
            for host, body in bodies:
                self.assertTrue(body.startswith("## Purpose\n"), f"{host}:{role_name}")
                for forbidden in FORBIDDEN_PROMPT_PROVENANCE:
                    self.assertNotIn(forbidden, body, f"{host}:{role_name}")
                self.assertNotIn("```json", body, f"{host}:{role_name}")

    def test_projection_manifest_v3_carries_removed_metadata(self):
        self.assertEqual(self.manifest["schema"], "bbk.projection-manifest.v3")
        self.assertEqual(set(self.manifest["agents"]), set(self.roles))
        self.assertRegex(self.manifest["role_source_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(self.manifest["model_routing_source_sha256"], r"^[0-9a-f]{64}$")
        for role_name, role in self.roles.items():
            value = self.manifest["agents"][role_name]
            self.assertEqual(value["description"], role["description"])
            self.assertEqual(value["skills"], role.get("skills", []))
            self.assertEqual(value["spawns"], role.get("spawns", []))
            self.assertIn(value["model_profile"], {"judgment", "coordination", "mechanical"})
            self.assertEqual(set(value["files"]), {"codex", "omp", "claude", "generic"})

    def test_profile_aware_roles_autoload_registry_and_router_while_question_roles_remain_lean(self):
        for role_name, role in self.roles.items():
            skills = role.get("skills", [])
            if role_name in PROFILE_AWARE_ROLES:
                self.assertIn("bbk-installed-profiles", skills, role_name)
                self.assertIn("bbk-profile-routing", skills, role_name)
            else:
                self.assertNotIn("bbk-installed-profiles", skills, role_name)

            omp, _ = _frontmatter_and_body(ROOT / "projections" / "omp" / "agents" / f"{role_name}.md")
            autoload = omp.get("autoloadSkills", [])
            if isinstance(autoload, str):
                autoload = [value.strip() for value in autoload.split(",") if value.strip()]
            self.assertEqual(autoload, skills, role_name)

    def test_every_generated_role_prompt_explains_profile_selection_and_propagation(self):
        for role_name in self.roles:
            bodies = []
            _, codex_body = _codex(ROOT / "projections" / "codex" / "agents" / f"{role_name}.toml")
            bodies.append(codex_body)
            for host, filename in (
                ("omp", f"{role_name}.md"),
                ("claude", f"{role_name.replace('_', '-')}.md"),
            ):
                _, body = _frontmatter_and_body(ROOT / "projections" / host / "agents" / filename)
                bodies.append(body)
            bodies.append((ROOT / "projections" / "generic" / "agents" / f"{role_name}.md").read_text(encoding="utf-8"))
            for body in bodies:
                self.assertIn("`bbk-installed-profiles`", body, role_name)
                self.assertIn("language/toolchain profiles", body, role_name)
                if role_name in PROFILE_AWARE_ROLES:
                    self.assertIn("## Language and domain profiles", body, role_name)
                    self.assertIn("`bbk-profile-routing`", body, role_name)
                    self.assertIn("Carry the selected profile identity", body, role_name)
                else:
                    self.assertNotIn("## Language and domain profiles", body, role_name)

    def test_all_shared_skills_define_profile_interaction_without_embedding_inventory(self):
        paths = sorted((ROOT / "shared" / "skills").glob("*/SKILL.md"))
        self.assertEqual(len(paths), 21)
        for path in paths:
            text = path.read_text(encoding="utf-8")
            self.assertRegex(text.lower(), r"\bprofiles?\b", str(path.relative_to(ROOT)))
        placeholder = (ROOT / "shared" / "skills" / "bbk-installed-profiles" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("package-source placeholder", placeholder)
        self.assertIn("No language or domain profile is managed", placeholder)
        self.assertNotIn("### `rust@", placeholder)

    def test_current_docs_explain_delegation_registry_and_prompt_metadata_boundary(self):
        combined = "\n".join(
            (ROOT / relative).read_text(encoding="utf-8")
            for relative in (
                "README.md",
                "docs/AGENT-COMPOSITION.md",
                "docs/INSTALL.md",
                "docs/LANGUAGE-PROFILES.md",
                "docs/MODEL-ROUTING.md",
                "docs/USAGE.md",
            )
        )
        for expected in (
            "bbk-installed-profiles",
            "effective-language-profiles.json",
            "bbk --json profile list",
            "spawns",
            "Delegation",
            "projections/manifest.json",
        ):
            self.assertIn(expected, combined)
        self.assertIn("prompt", combined.lower())
        self.assertIn("provenance", combined.lower())

    def test_install_specific_registry_selects_compact_router_and_records_capabilities(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "profile"
            (root / "skills" / "bbk-rust").mkdir(parents=True)
            (root / "skills" / "rust-review").mkdir(parents=True)
            (root / "skills" / "bbk-rust" / "SKILL.md").write_text(
                "---\nname: bbk-rust\ndescription: Rust profile router.\n---\n\n# Router\n",
                encoding="utf-8",
            )
            (root / "skills" / "rust-review" / "SKILL.md").write_text(
                "---\nname: rust-review\ndescription: Focused Rust review.\n---\n\n# Review\n",
                encoding="utf-8",
            )
            item = _DummyProfile(
                root=root,
                profile={
                    "id": "rust",
                    "version": "0.1.0-alpha.3",
                    "name": "Rust",
                    "description": "Qualified Rust procedures.",
                    "package": "bbk-profile-rust",
                    "installation": {"skill_root": "skills", "cli": "tools/rust_profile.py"},
                    "capabilities": {
                        "test": {"status": "supported"},
                        "mutation": {"status": "conditional"},
                    },
                },
            )
            data = profile_registry.registry_data([item], bbk_version="0.1.0-alpha.11.7")
            profile = data["profiles"][0]
            self.assertEqual(profile["router_skill"], "bbk-rust")
            self.assertEqual(profile["cli_command"], "rust-profile")
            self.assertEqual(profile["skill_count"], 2)
            text = profile_registry.registry_skill_text([item], bbk_version="0.1.0-alpha.11.7")
            self.assertIn("### `rust@0.1.0-alpha.3` — Rust", text)
            self.assertIn("Router skill: `bbk-rust`", text)
            self.assertIn("test=supported", text)
            self.assertIn("mutation=conditional", text)
            self.assertNotIn("rust-review", text, "focused skill inventories should not bloat every autoloaded registry")


if __name__ == "__main__":
    unittest.main()
