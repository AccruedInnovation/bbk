from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import model_routing  # noqa: E402

ROLES = ROOT / "spec" / "roles.json"
ROUTING = ROOT / "spec" / "model-routing.json"
INSTALL = ROOT / "tools" / "install.py"
GENERATOR = ROOT / "tools" / "generate_agents.py"


def run(command: list[str | Path], *, cwd: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(value) for value in command],
        cwd=cwd,
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frontmatter(path: Path) -> dict[str, object]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        raise AssertionError(f"missing YAML frontmatter: {path}")
    end = lines.index("---", 1)
    result: dict[str, object] = {}
    active_list: str | None = None
    for line in lines[1:end]:
        if line.startswith("  - "):
            if active_list is None:
                raise AssertionError(f"orphan YAML list item in {path}: {line}")
            raw = line[4:]
            try:
                value: object = json.loads(raw)
            except json.JSONDecodeError:
                value = raw
            cast = result.setdefault(active_list, [])
            if not isinstance(cast, list):
                raise AssertionError(f"mixed scalar/list key in {path}: {active_list}")
            cast.append(value)
            continue
        if not line.strip():
            continue
        key, raw = line.split(":", 1)
        key = key.strip()
        raw = raw.strip()
        active_list = key
        if not raw:
            result[key] = []
            continue
        try:
            result[key] = json.loads(raw)
        except json.JSONDecodeError:
            result[key] = raw
    return result



class Alpha10ModelRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.roles = json.loads(ROLES.read_text(encoding="utf-8"))
        cls.routing = json.loads(ROUTING.read_text(encoding="utf-8"))
        cls.role_names = {role["name"] for role in cls.roles["roles"]}

    def test_policy_covers_every_role_through_three_named_tiers(self):
        errors = model_routing.validate_model_routing(
            self.routing,
            version=(ROOT / "VERSION").read_text(encoding="utf-8").strip(),
            role_names=self.role_names,
        )
        self.assertEqual(errors, [])
        self.assertEqual(set(self.routing["profiles"]), {"judgment", "coordination", "mechanical"})
        self.assertEqual(set(self.routing["role_profiles"]), self.role_names)
        counts = {
            name: sum(value == name for value in self.routing["role_profiles"].values())
            for name in self.routing["profiles"]
        }
        self.assertEqual(counts, {"judgment": 12, "coordination": 5, "mechanical": 2})

    def test_default_tiers_use_deliberate_cost_quality_routing(self):
        profiles = self.routing["profiles"]
        self.assertEqual(
            profiles["judgment"]["omp"],
            {"model": "openai-codex/gpt-5.6-sol", "thinkingLevel": "high"},
        )
        self.assertEqual(
            profiles["coordination"]["omp"],
            {"model": "deepseek/deepseek-v4-pro", "thinkingLevel": "high"},
        )
        self.assertEqual(
            profiles["mechanical"]["omp"],
            {"model": "deepseek/deepseek-v4-flash", "thinkingLevel": "high"},
        )
        self.assertEqual(
            profiles["judgment"]["codex"],
            {"model": "gpt-5.6-sol", "model_reasoning_effort": "high"},
        )
        self.assertEqual(
            profiles["coordination"]["codex"],
            {"model": "gpt-5.6-terra", "model_reasoning_effort": "medium"},
        )
        self.assertEqual(
            profiles["mechanical"]["codex"],
            {"model": "gpt-5.6-luna", "model_reasoning_effort": "low"},
        )
        self.assertEqual(profiles["judgment"]["claude"], {"model": "opus", "effort": "high"})
        self.assertEqual(profiles["coordination"]["claude"], {"model": "sonnet", "effort": "medium"})
        self.assertEqual(profiles["mechanical"]["claude"], {"model": "haiku", "effort": "low"})
        self.assertEqual(self.routing["role_profiles"]["bbk_worker_orchestrator"], "coordination")
        self.assertEqual(self.routing["role_profiles"]["bbk_validator_orchestrator"], "coordination")
        self.assertEqual(self.routing["role_profiles"]["bbk_worker"], "mechanical")
        self.assertEqual(self.routing["role_profiles"]["bbk_validator"], "mechanical")
        self.assertEqual(self.routing["role_profiles"]["bbk_synthesizer"], "judgment")

        # Current-facing routing tables must not drift from the canonical policy.
        for relative in ("docs/MODEL-ROUTING.md",):
            text = (ROOT / relative).read_text(encoding="utf-8")
            for expected in (
                "`gpt-5.6-sol`, `model_reasoning_effort: high`",
                "`gpt-5.6-terra`, `model_reasoning_effort: medium`",
                "`gpt-5.6-luna`, `model_reasoning_effort: low`",
                "`opus`, `effort: high`",
                "`sonnet`, `effort: medium`",
                "`haiku`, `effort: low`",
            ):
                self.assertIn(expected, text, relative)

    def test_generated_host_fields_match_each_role_route(self):
        manifest = json.loads((ROOT / "projections" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema"], "bbk.projection-manifest.v3")
        self.assertEqual(manifest["model_profile_count"], 3)
        self.assertEqual(manifest["model_routing_source"], "spec/model-routing.json")
        for role_name in sorted(self.role_names):
            profile_name = self.routing["role_profiles"][role_name]
            profile = self.routing["profiles"][profile_name]

            codex = tomllib.loads(
                (ROOT / "projections" / "codex" / "agents" / f"{role_name}.toml").read_text(encoding="utf-8")
            )
            self.assertEqual(codex["model"], profile["codex"]["model"])
            self.assertEqual(codex["model_reasoning_effort"], profile["codex"]["model_reasoning_effort"])

            omp = frontmatter(ROOT / "projections" / "omp" / "agents" / f"{role_name}.md")
            self.assertEqual(omp["model"], profile["omp"]["model"])
            self.assertEqual(omp["thinkingLevel"], profile["omp"]["thinkingLevel"])

            claude_name = role_name.replace("_", "-")
            claude = frontmatter(ROOT / "projections" / "claude" / "agents" / f"{claude_name}.md")
            self.assertEqual(claude["model"], profile["claude"]["model"])
            self.assertEqual(claude["effort"], profile["claude"]["effort"])

            agent_meta = manifest["agents"][role_name]
            self.assertEqual(agent_meta["model_profile"], profile_name)
            self.assertEqual(agent_meta["model_routing"], {
                "omp": profile["omp"], "codex": profile["codex"], "claude": profile["claude"]
            })
            generic_text = (ROOT / "projections" / "generic" / "agents" / f"{role_name}.md").read_text(encoding="utf-8")
            self.assertIn("## Purpose", generic_text)
            self.assertNotIn("```json", generic_text)

    def test_policy_validator_rejects_missing_roles_and_unknown_profiles(self):
        invalid = copy.deepcopy(self.routing)
        invalid["role_profiles"].pop("bbk_worker")
        invalid["role_profiles"]["bbk_validator"] = "not-a-profile"
        errors = model_routing.validate_model_routing(
            invalid,
            version=(ROOT / "VERSION").read_text(encoding="utf-8").strip(),
            role_names=self.role_names,
        )
        self.assertTrue(any("missing roles" in error and "bbk_worker" in error for error in errors))
        self.assertTrue(any("unknown profile" in error and "not-a-profile" in error for error in errors))

    def test_runtime_prompt_surface_is_product_neutral(self):
        paths = [ROLES, ROOT / "spec" / "method-content.json"]
        paths.extend((ROOT / "shared" / "skills").glob("*/SKILL.md"))
        paths.extend((ROOT / "shared" / "references").glob("*.md"))
        for target in ("codex", "omp", "claude", "generic"):
            paths.extend((ROOT / "projections" / target / "agents").glob("*"))
        forbidden = ("blueprint", "tenex", "otobotto", "autospec")
        partition_tokens = {"q0", *(f"c{number}" for number in range(12))}
        for path in paths:
            text = path.read_text(encoding="utf-8").lower()
            for token in forbidden:
                self.assertNotIn(token, text, str(path.relative_to(ROOT)))
            words = {word.strip("`'\".,:;()[]{}<>—–-") for word in text.split()}
            self.assertTrue(words.isdisjoint(partition_tokens), str(path.relative_to(ROOT)))

    def test_install_time_override_changes_harness_agents_without_mutating_package(self):
        canonical_worker = ROOT / "projections" / "omp" / "agents" / "bbk_worker.md"
        before = sha256(canonical_worker)
        custom = copy.deepcopy(self.routing)
        custom["profiles"]["mechanical"]["omp"] = {"model": "@tiny", "thinkingLevel": "low"}
        custom["profiles"]["mechanical"]["codex"] = {
            "model": "gpt-5.4-mini", "model_reasoning_effort": "low"
        }
        custom["profiles"]["mechanical"]["claude"] = {"model": "sonnet", "effort": "low"}

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "project"
            project.mkdir()
            policy = root / "custom-model-routing.json"
            policy.write_text(json.dumps(custom, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            installed = run([
                sys.executable, INSTALL, "--json", "install", "--scope", "project", "--root", project,
                "--codex", "--omp", "--claude", "--generic", "--model-routing", policy,
                "--no-language-profiles",
            ])
            value = json.loads(installed.stdout)
            self.assertEqual(value["model_routing"]["source"], policy.resolve().as_posix())
            effective = project / ".bbk-kit" / "effective-model-routing.json"
            self.assertEqual(json.loads(effective.read_text(encoding="utf-8")), custom)

            omp = frontmatter(project / ".omp" / "agents" / "bbk_worker.md")
            self.assertEqual(omp["model"], "@tiny")
            self.assertEqual(omp["thinkingLevel"], "low")
            codex = tomllib.loads((project / ".codex" / "agents" / "bbk_worker.toml").read_text(encoding="utf-8"))
            self.assertEqual(codex["model"], "gpt-5.4-mini")
            claude = frontmatter(project / ".claude" / "agents" / "bbk-worker.md")
            self.assertEqual(claude["model"], "sonnet")
            generic_text = (project / ".agents" / "bbk" / "agents" / "bbk_worker.md").read_text(encoding="utf-8")
            self.assertIn("## Purpose", generic_text)
            self.assertNotIn("model_profile", generic_text)
            generic_manifest = json.loads(
                (project / ".agents" / "bbk" / "agent-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(generic_manifest["schema"], "bbk.installed-generic-agent-manifest.v1")
            self.assertEqual(
                generic_manifest["agents"]["bbk_worker"]["model_routing"]["omp"]["model"],
                "@tiny",
            )
            empty_registry = (project / ".agents" / "skills" / "bbk-installed-profiles" / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("No language or domain profile is managed", empty_registry)
            self.assertNotIn("package-source placeholder", empty_registry)
            self.assertEqual(value["language_profile_registry"]["profile_count"], 0)
            self.assertEqual(
                value["model_routing"]["sha256"],
                hashlib.sha256(json.dumps(custom, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
            )

            run([sys.executable, INSTALL, "uninstall", "--scope", "project", "--root", project])
        self.assertEqual(sha256(canonical_worker), before)


    def test_invalid_external_policy_blocks_install_before_any_write(self):
        invalid = copy.deepcopy(self.routing)
        invalid["role_profiles"].pop("bbk_worker")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "project"
            project.mkdir()
            policy = root / "invalid-model-routing.json"
            policy.write_text(json.dumps(invalid, indent=2) + "\n", encoding="utf-8")
            result = run([
                sys.executable, INSTALL, "--json", "install", "--scope", "project",
                "--root", project, "--omp", "--model-routing", policy, "--no-language-profiles",
            ], check=False)
            self.assertEqual(result.returncode, 2)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "ERROR")
            self.assertIn("missing roles", payload["error"])
            self.assertFalse((project / ".bbk-kit").exists())
            self.assertFalse((project / ".omp").exists())

    def test_model_routing_cli_and_projection_check_succeed(self):
        checked = run([sys.executable, ROOT / "tools" / "model_routing.py", "--check"])
        self.assertIn("19 roles resolve through 3 model profiles", checked.stdout)
        generated = run([sys.executable, GENERATOR, "--check"])
        self.assertIn("19 roles, 3 model profiles, 4 targets, and 76 projections", generated.stdout)


if __name__ == "__main__":
    unittest.main()
