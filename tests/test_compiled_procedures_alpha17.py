from __future__ import annotations

import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import compiled_procedures as cp  # noqa: E402
import generate_agents as ga  # noqa: E402
import install as install_tool  # noqa: E402


class CompiledProcedureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roles = json.loads((ROOT / "spec" / "roles.json").read_text(encoding="utf-8"))["roles"]
        cls.manifest = json.loads((ROOT / "projections" / "manifest.json").read_text(encoding="utf-8"))

    def test_registry_is_reproducible_and_complete(self):
        self.assertEqual(cp.build_registry(ROOT), cp.load_registry(ROOT))
        registry = cp.load_registry(ROOT)
        self.assertEqual(40, len(registry["procedures"]))
        self.assertEqual(19, len(registry["roles"]))
        self.assertTrue(registry["global_non_indexed_compiled_set"])

    def test_every_generated_role_has_one_closed_compiled_tail_and_primary_last(self):
        for role in self.roles:
            name = role["name"]
            entry = self.manifest["agents"][name]
            for target, metadata in entry["compiled_procedures"].items():
                path = ROOT / "projections" / target / "agents" / entry["files"][target]
                text = path.read_text(encoding="utf-8")
                primary = role["primary_skill"]
                self.assertEqual(1, text.count("## Compiled procedures manifest"), (name, target))
                self.assertEqual(1, text.count("## Compiled procedures\n"), (name, target))
                self.assertEqual(1, text.count("## End compiled procedures"), (name, target))
                self.assertEqual(1, text.count(f"### Compiled primary procedure: `{primary}`"), (name, target))
                semantic = text.split("## End compiled procedures", 1)[1].strip()
                expected_suffix = {"omp": "</bbk-agent-system>", "codex": '"""'}.get(target, "")
                self.assertEqual(expected_suffix, semantic, (name, target))
                procedures = metadata["procedures"]
                self.assertEqual(primary, procedures[-1]["id"])
                self.assertTrue(all(item["state"] == "COMPILED_COMPLETE" for item in procedures))
                self.assertTrue(all(item["catalog_visibility"] == "SUPPRESSED" for item in procedures))
                self.assertNotIn("<bbk-inlined-skill", text)

    def test_effective_external_catalog_is_disjoint_and_optional_skills_remain(self):
        for role in self.roles:
            entry = self.manifest["agents"][role["name"]]
            for target, catalog in entry["effective_external_catalogs"].items():
                available = set(catalog["available_external_procedures"])
                suppressed = set(catalog["suppressed_compiled_procedures"])
                self.assertFalse(available & suppressed, (role["name"], target))
                self.assertEqual("PASS", catalog["status"])
                registry = cp.load_registry(ROOT)
                classes = {
                    item["id"]: item["catalog_classification"]
                    for item in registry["procedures"]
                }
                for optional in set(role["skills"]) - set(role["mandatory_skills"]):
                    if classes.get(optional) == "EXTERNAL_OPTIONAL":
                        self.assertIn(optional, available, (role["name"], target, optional))
                    else:
                        self.assertNotIn(optional, available, (role["name"], target, optional))
                        self.assertIn(optional, catalog["compiler_selectable_procedures"])

    def test_unchanged_followup_reuses_without_source_read(self):
        role = next(item for item in self.roles if item["name"] == "bbk_worker")
        result = cp.compile_role_prompt("base", role, harness="codex", logical_child_id="child:1")
        reused = cp.followup_result(
            cp.compiled_state(result),
            requested_procedure_ids=[item["id"] for item in result.manifest["procedures"]],
            harness="codex",
            registry_revision=result.manifest["registry_revision"],
            compiler_sha256=result.manifest["compiler"]["sha256"],
        )
        self.assertTrue(reused.reused)
        self.assertEqual(0, reused.source_read_count)
        self.assertEqual(result.prompt, reused.prompt)
        with self.assertRaises(cp.CompiledProcedureError) as cm:
            cp.followup_result(cp.compiled_state(result), requested_procedure_ids=["bbk-worker-design"])
        self.assertEqual("BBK-CP-007", cm.exception.code)

    def test_installer_keeps_canonical_sources_but_excludes_compiled_catalog_files(self):
        excluded = install_tool.compiled_skill_catalog_exclusions(ROOT)
        for procedure in cp.globally_suppressed_procedures(ROOT):
            self.assertIn(f"{procedure}/SKILL.md", excluded)
            self.assertTrue((ROOT / "shared" / "skills" / procedure / "SKILL.md").is_file())
        self.assertNotIn("bbk-artifact/SKILL.md", excluded)

    def test_controller_projections_embed_every_prompt_module_once(self):
        spec = json.loads((ROOT / "spec" / "roles.json").read_text(encoding="utf-8"))
        for host in ("codex", "claude", "pi", "generic"):
            result = ga.compiled_controller(spec, host=host)
            dependencies = {
                dependency
                for procedure in result.manifest["procedures"]
                for dependency in procedure["dependencies"]
                if dependency.startswith("bbk-prompt-")
            }
            self.assertNotIn("Apply the already embedded", result.prompt, host)
            for module_id in dependencies:
                self.assertEqual(
                    1,
                    result.prompt.count(f"<!-- BBK compiled prompt module {module_id} -->"),
                    (host, module_id),
                )

    def test_host_facing_controller_skill_has_valid_frontmatter_and_activation(self):
        spec = json.loads((ROOT / "spec" / "roles.json").read_text(encoding="utf-8"))
        expected = {
            "codex": "`$bbk`",
            "claude": "`/bbk`",
            "pi": "asks Pi",
            "generic": "asks the host",
        }
        for host, activation in expected.items():
            result = ga.compiled_controller(spec, host=host)
            skill = ga.rendered_controller_skill(spec, host=host, compiled=result)
            frontmatter, body = skill.removeprefix("---\n").split("\n---\n", 1)
            fields = dict(line.split(": ", 1) for line in frontmatter.splitlines())
            self.assertEqual("bbk", fields["name"])
            self.assertIsInstance(json.loads(fields["description"]), str)
            self.assertIn(activation, fields["description"])
            self.assertIn("# BBK harness-root controller", body)
            self.assertNotIn("Apply the already embedded", skill)

        invalid = replace(result, prompt=result.prompt + "Apply the already embedded `missing` module here.\n")
        with self.assertRaisesRegex(ValueError, "unresolved prompt-module placeholders"):
            ga.rendered_controller_skill(spec, host="generic", compiled=invalid)


if __name__ == "__main__":
    unittest.main()
