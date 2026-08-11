from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import compiled_procedures as cp  # noqa: E402
import generate_agents as ga  # noqa: E402
import prompt_lint  # noqa: E402
from model_routing import load_model_routing, route_for_role  # noqa: E402


class PromptCompilationV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.spec = json.loads((ROOT / "spec" / "roles.json").read_text(encoding="utf-8"))
        cls.roles = {item["name"]: item for item in cls.spec["roles"]}
        cls.routing = load_model_routing(
            ROOT / "spec" / "model-routing.json", root=ROOT, role_spec=cls.spec
        )
        cls.registry = cp.load_registry(ROOT)
        cls.projections = json.loads(
            (ROOT / "projections" / "manifest.json").read_text(encoding="utf-8")
        )

    def test_registry_dependency_closure_places_bbk_plan_before_wayfind(self) -> None:
        procedure = next(
            item for item in self.registry["procedures"] if item["id"] == "bbk-wayfind"
        )
        self.assertEqual(["bbk-plan"], procedure["procedure_dependencies"])
        role = self.roles["bbk_root_wayfinder"]
        route = route_for_role(self.routing, role["name"])
        result = ga.compiled_instruction(self.spec, role, host="codex", route=route)
        ids = [item["id"] for item in result.manifest["procedures"]]
        self.assertEqual(["bbk-plan", "bbk-wayfind"], ids)
        self.assertEqual("DEPENDENCY_OF:bbk-wayfind", result.manifest["procedures"][0]["selection_reason"])
        self.assertEqual("PRIMARY", result.manifest["procedures"][-1]["selection_reason"])

    def test_dependency_cycle_is_rejected(self) -> None:
        registry = {
            "procedures": [
                {"id": "one", "procedure_dependencies": ["two"]},
                {"id": "two", "procedure_dependencies": ["one"]},
            ]
        }
        with self.assertRaises(cp.CompiledProcedureError) as caught:
            cp._closure(["one"], registry, {"one": "PRIMARY"}, "one")
        self.assertEqual("BBK-CP-003", caught.exception.code)

    def test_all_role_and_controller_targets_share_procedure_semantics(self) -> None:
        targets = list(ga.TARGETS)
        self.assertEqual({"claude", "codex", "generic", "omp", "pi"}, set(targets))
        self.assertEqual(["claude", "codex", "generic", "omp", "pi"], self.projections["targets"])
        self.assertEqual("bbk.projection-manifest.v10", self.projections["schema"])
        self.assertEqual(100, self.projections["projection_count"])
        self.assertEqual(set(targets), set(self.projections["controllers"]))
        for role in self.spec["roles"]:
            entry = self.projections["agents"][role["name"]]["compiled_procedures"]
            procedure_sets = {
                target: tuple(item["id"] for item in entry[target]["procedures"])
                for target in targets
            }
            self.assertEqual(1, len(set(procedure_sets.values())), (role["name"], procedure_sets))
        controller_sets = {
            target: tuple(
                item["id"]
                for item in self.projections["controllers"][target]["compiled_procedures"]["procedures"]
            )
            for target in targets
        }
        self.assertEqual(1, len(set(controller_sets.values())), controller_sets)
        self.assertEqual(("bbk-context-routing", "bbk"), controller_sets["codex"])

    def test_profile_and_invocation_selection_compile_once_and_suppress_catalog(self) -> None:
        role = self.roles["bbk_worker"]
        result = cp.compile_role_prompt(
            "base",
            role,
            harness="codex",
            logical_child_id="child:dynamic",
            invocation_id="attempt:1",
            profile_procedures=["bbk-profile-routing"],
            invocation_procedures=["bbk-artifact"],
            profile_registry_revision="profiles:test",
            tool_capabilities={"filesystem": "workspace"},
            adapter_template={"id": "codex-agent-v1"},
            root=ROOT,
        )
        ids = [item["id"] for item in result.manifest["procedures"]]
        self.assertEqual(
            ["bbk-profile-routing", "bbk-artifact", "bbk-work-unit-execution"],
            ids,
        )
        self.assertEqual("PROFILE", result.manifest["procedures"][0]["selection_reason"])
        self.assertEqual("INVOCATION", result.manifest["procedures"][1]["selection_reason"])
        self.assertEqual("PRIMARY", result.manifest["procedures"][2]["selection_reason"])
        self.assertFalse(set(ids) & set(result.external_catalog))
        self.assertEqual(3, result.source_read_count)
        self.assertEqual("PROMPT_COMPILED", result.event["event"])
        self.assertEqual(0, result.event["procedure_reads_by_model"])
        self.assertTrue(any(key.startswith("profile:") for key in result.manifest["invalidation_keys"]))
        self.assertTrue(any(key.startswith("tools:") for key in result.manifest["invalidation_keys"]))
        self.assertTrue(any(key.startswith("adapter:") for key in result.manifest["invalidation_keys"]))

    def test_dynamic_role_module_closure_is_host_scoped_without_changing_procedures(self) -> None:
        role = dict(self.roles["bbk_worker"])
        package = cp.load_prompt_modules(ROOT)
        selected = set(role["prompt_modules"]) | {
            "bbk-prompt-context-human-relay",
            "bbk-prompt-human-request",
        }
        role["prompt_modules"] = [
            module_id for module_id in package.ordered_ids if module_id in selected
        ]
        results = {
            harness: cp.compile_role_prompt(
                "base",
                role,
                harness=harness,
                profile_procedures=["bbk-profile-routing"],
                root=ROOT,
            )
            for harness in ("omp", "codex", "claude", "pi", "generic")
        }
        procedure_sets = {
            tuple(item["id"] for item in result.manifest["procedures"])
            for result in results.values()
        }
        self.assertEqual(1, len(procedure_sets))
        self.assertIn("bbk-prompt-profile-dispatch", results["codex"].prompt)
        omp_only = [
            clause["text"]
            for module in package.modules
            for clause in module["clauses"]
            if clause.get("hosts") == ["omp"]
        ]
        self.assertEqual(5, len(omp_only))
        for clause_text in omp_only:
            self.assertIn(clause_text, results["omp"].prompt)
            for harness in ("codex", "claude", "pi", "generic"):
                self.assertNotIn(clause_text, results[harness].prompt)

    def test_controller_module_closure_is_host_scoped_without_changing_procedures(self) -> None:
        results = {
            harness: cp.compile_controller_prompt("base", harness=harness, root=ROOT)
            for harness in ("omp", "codex", "claude", "pi", "generic")
        }
        procedure_sets = {
            tuple(item["id"] for item in result.manifest["procedures"])
            for result in results.values()
        }
        self.assertEqual(1, len(procedure_sets))
        package = cp.load_prompt_modules(ROOT)
        scoped_texts = [
            clause["text"]
            for module in package.modules
            if f"<!-- BBK compiled prompt module {module['id']} -->" in results["omp"].prompt
            for clause in module["clauses"]
            if clause.get("hosts") == ["omp"]
        ]
        self.assertEqual(4, len(scoped_texts))
        for clause_text in scoped_texts:
            self.assertIn(clause_text, results["omp"].prompt)
            for harness in ("codex", "claude", "pi", "generic"):
                self.assertNotIn(clause_text, results[harness].prompt)

    def test_followup_reuse_requires_exact_invalidation_vector(self) -> None:
        role = self.roles["bbk_worker"]
        result = cp.compile_role_prompt(
            "base", role, harness="pi", logical_child_id="child:pi", root=ROOT
        )
        state = cp.compiled_state(result)
        reused = cp.followup_result(
            state,
            requested_procedure_ids=[item["id"] for item in result.manifest["procedures"]],
            harness="pi",
            registry_revision=result.manifest["registry_revision"],
            compiler_sha256=result.manifest["compiler"]["sha256"],
            current_invalidation_keys=result.manifest["invalidation_keys"],
        )
        self.assertTrue(reused.reused)
        self.assertEqual(0, reused.source_read_count)
        self.assertEqual("PROMPT_REUSED", reused.event["event"])
        changed = [*result.manifest["invalidation_keys"], "policy:changed"]
        with self.assertRaises(cp.CompiledProcedureError) as caught:
            cp.followup_result(state, harness="pi", current_invalidation_keys=changed)
        self.assertEqual("BBK-CP-007", caught.exception.code)

    def test_prompt_compile_cli_emits_bound_artifact_set(self) -> None:
        request = {
            "identity_kind": "ROLE",
            "role": "bbk_worker",
            "harness": "claude",
            "logical_child_id": "child:cli",
            "invocation_id": "attempt:cli",
            "invocation_procedures": ["bbk-artifact"],
        }
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            request_path = temp_path / "request.json"
            output_path = temp_path / "compiled"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(TOOLS / "prompt_compile.py"),
                    "compile",
                    "--request",
                    str(request_path),
                    "--output-dir",
                    str(output_path),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
            response = json.loads(completed.stdout)
            self.assertEqual("PASS", response["status"])
            expected = {
                "prompt.md",
                "compiled-procedure-manifest.json",
                "effective-procedure-catalog.json",
                "prompt-compilation-plan.json",
                "prompt-source-map.json",
                "prompt-compilation-event.json",
                "logical-child-compiled-state.json",
            }
            self.assertEqual(expected, {path.name for path in output_path.iterdir()})
            manifest = json.loads(
                (output_path / "compiled-procedure-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual("CLAUDE", manifest["harness"])
            self.assertEqual(
                ["bbk-artifact", "bbk-work-unit-execution"],
                [item["id"] for item in manifest["procedures"]],
            )

    def test_installed_profile_router_is_compiled_from_bound_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            router = temp_path / "profile" / "skills" / "bbk-sample" / "SKILL.md"
            router.parent.mkdir(parents=True)
            router.write_text(
                "---\nname: bbk-sample\ndescription: Sample profile router.\n---\n\n# Sample router\n\nUse the sample profile.\n",
                encoding="utf-8",
            )
            payload = router.read_bytes()
            binding = {
                "profile_id": "sample",
                "profile_version": "1.0.0",
                "profile_root_sha256": "0" * 64,
                "installed_package_root": str(temp_path / "profile"),
                "required_procedures": ["bbk-sample"],
                "optional_procedures": [],
                "procedure_sources": [
                    {
                        "id": "bbk-sample",
                        "path": "skills/bbk-sample/SKILL.md",
                        "installed_path": str(router),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "bytes": len(payload),
                        "selection": "PROFILE_REQUIRED",
                    }
                ],
            }
            binding["registry_revision"] = hashlib.sha256(
                json.dumps(binding, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            registry = {
                "schema": "bbk.installed-profile-registry.v1",
                "bbk_version": "0.1.0-alpha.17.0.2.1",
                "bbk_cli": {},
                "profiles": [
                    {
                        "id": "sample",
                        "version": "1.0.0",
                        "procedure_registry_revision": binding["registry_revision"],
                        "procedure_binding": binding,
                    }
                ],
            }
            registry_path = temp_path / "effective-language-profiles.json"
            registry_path.write_text(json.dumps(registry), encoding="utf-8")
            additional, required, optional, revision = cp.load_profile_procedure_selection(
                registry_path, profile_ids=["sample"]
            )
            self.assertEqual(("bbk-sample",), required)
            self.assertEqual((), optional)
            self.assertEqual(64, len(revision))
            role = self.roles["bbk_worker"]
            result = cp.compile_role_prompt(
                "base",
                role,
                harness="codex",
                profile_procedures=required,
                profile_registry_revision=revision,
                additional_procedures=additional,
                root=ROOT,
            )
            self.assertEqual(
                ["bbk-sample", "bbk-work-unit-execution"],
                [item["id"] for item in result.manifest["procedures"]],
            )
            self.assertIn("Use the sample profile.", result.prompt)
            state = cp.compiled_state(result)
            reused = cp.followup_result(state, harness="codex", root=ROOT)
            self.assertTrue(reused.reused)
            router.write_text(router.read_text(encoding="utf-8") + "changed\n", encoding="utf-8")
            with self.assertRaises(cp.CompiledProcedureError) as caught:
                cp.followup_result(state, harness="codex", root=ROOT)
            self.assertEqual("BBK-CP-007", caught.exception.code)

    def test_prompt_lint_report_covers_all_effective_projections(self) -> None:
        report = prompt_lint.build_report(ROOT)
        self.assertEqual("PASS", report["status"])
        self.assertEqual(20, report["identity_count"])
        self.assertEqual(100, report["projection_count"])
        self.assertEqual([], report["errors"])


if __name__ == "__main__":
    unittest.main()
