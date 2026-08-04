from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from assemble_roles import (  # noqa: E402
    EXPECTED_CONTROLLER_ENTRYPOINTS,
    EXPECTED_HUMAN_REQUEST_ORIGINATORS,
    RolePackageError,
    assemble,
    canonical_bytes,
    projection_drift,
)


class SplitRolePackageV4Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.package = assemble(ROOT)
        self.catalog = self.package.catalog
        self.roles = list(self.package.roles)
        self.by_name = {role["name"]: role for role in self.roles}
        self.entries = {
            entry["name"]: entry for entry in self.catalog["role_entries"]
        }

    def _minimal_copy(self, target: Path) -> None:
        (target / "spec").mkdir(parents=True)
        shutil.copy2(ROOT / "spec" / "method-content.json", target / "spec" / "method-content.json")
        shutil.copytree(ROOT / "spec" / "roles", target / "spec" / "roles")
        shutil.copytree(ROOT / "spec" / "prompt-modules", target / "spec" / "prompt-modules")
        shutil.copytree(ROOT / "spec" / "schemas", target / "spec" / "schemas")
        shutil.copytree(ROOT / "spec" / "contracts", target / "spec" / "contracts")
        shutil.copy2(ROOT / "spec" / "roles.json", target / "spec" / "roles.json")

    def test_catalog_is_the_canonical_ordered_source(self) -> None:
        names = [entry["name"] for entry in self.catalog["role_entries"]]
        self.assertEqual(names, [role["name"] for role in self.roles])
        self.assertEqual(len(names), 19)
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(
            {entry["file"] for entry in self.catalog["role_entries"]},
            {
                path.relative_to(ROOT).as_posix()
                for path in (ROOT / "spec" / "roles").glob("bbk_*-role.json")
            },
        )

    def test_compatibility_projection_is_current_and_deterministic(self) -> None:
        self.assertEqual(projection_drift(self.package), [])
        first = canonical_bytes(assemble(ROOT).projection)
        second = canonical_bytes(assemble(ROOT).projection)
        self.assertEqual(first, second)
        self.assertEqual((ROOT / "spec" / "roles.json").read_bytes(), first)

    def test_projection_schema_is_declared_and_self_describing(self) -> None:
        expected = "spec/schemas/bbk-roles-v4.schema.json"
        self.assertEqual(self.catalog["projection_schema"], expected)
        self.assertEqual(self.package.projection["projection_schema"], expected)
        self.assertTrue((ROOT / expected).is_file())

    def test_published_draft_2020_12_schemas_validate_all_instances(self) -> None:
        try:
            import jsonschema
            from referencing import Registry, Resource
        except ImportError as exc:  # pragma: no cover - optional validator
            self.skipTest(f"optional Draft 2020-12 validator unavailable: {exc}")

        schema_paths = [
            ROOT / "spec" / "schemas" / "bbk-role-v4.schema.json",
            ROOT / "spec" / "schemas" / "bbk-role-catalog-v4.schema.json",
            ROOT / "spec" / "schemas" / "bbk-roles-v4.schema.json",
        ]
        schemas = [json.loads(path.read_text(encoding="utf-8")) for path in schema_paths]
        registry = Registry()
        for schema in schemas:
            jsonschema.Draft202012Validator.check_schema(schema)
            registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))

        role_schema, catalog_schema, projection_schema = schemas
        jsonschema.Draft202012Validator(catalog_schema, registry=registry).validate(self.catalog)
        role_validator = jsonschema.Draft202012Validator(role_schema, registry=registry)
        for role in self.roles:
            role_validator.validate(role)
        jsonschema.Draft202012Validator(
            projection_schema, registry=registry
        ).validate(self.package.projection)

    def test_method_content_is_the_single_canonical_skill_source(self) -> None:
        method = json.loads((ROOT / self.catalog["method_content_source"]).read_text(encoding="utf-8"))
        self.assertEqual(method["schema"], "bbk.method-content.v2")
        self.assertEqual(method["version"], self.catalog["package_version"])
        self.assertEqual(method["prompt_module_source"], self.catalog["prompt_module_package"])
        known = set(method["skills"])
        referenced = {skill for role in self.roles for skill in role["skills"]}
        self.assertTrue(referenced <= known)
        self.assertEqual(len(known), 40)

    def test_beads_on_demand_skill_is_owned_by_exact_record_authorities(self) -> None:
        expected = {
            "bbk_root_wayfinder",
            "bbk_territory_wayfinder",
            "bbk_planning_wayfinder",
            "bbk_phase_wayfinder",
            "bbk_root_orchestrator",
            "bbk_territory_orchestrator",
            "bbk_worker_orchestrator",
            "bbk_questioning_wayfinder",
        }
        actual = {
            role["name"] for role in self.roles
            if "bbk-beads" in role["skills"]
        }
        self.assertEqual(actual, expected)
        for role in self.roles:
            with self.subTest(role=role["name"]):
                self.assertNotIn("bbk-beads", role["mandatory_skills"])
                if role["name"] in expected:
                    self.assertTrue(
                        any("bbk-beads" in responsibility for responsibility in role["responsibilities"]),
                        f"{role['name']} has the skill but no explicit record-ownership responsibility",
                    )

    def test_primary_procedure_and_prompt_module_metadata_are_explicit(self) -> None:
        prompt_catalog = json.loads(
            (ROOT / self.catalog["prompt_module_package"]).read_text(encoding="utf-8")
        )
        order = [entry["id"] for entry in prompt_catalog["module_entries"]]
        policy = prompt_catalog["compilation_policy"]
        self.assertEqual(policy["mandatory_procedure_default"], 1)
        self.assertIsNone(policy["mandatory_procedure_maximum"])
        self.assertEqual(policy["additional_mandatory_procedure_exceptions"], {})
        for role in self.roles:
            with self.subTest(role=role["name"]):
                self.assertEqual(role["mandatory_skills"], [role["primary_skill"]])
                self.assertIn(role["primary_skill"], role["skills"])
                selected = set(role["prompt_modules"])
                self.assertEqual(role["prompt_modules"], [item for item in order if item in selected])

    def test_projection_binds_every_source_by_size_and_digest(self) -> None:
        manifest = self.package.projection["source_manifest"]
        self.assertEqual(manifest["catalog"]["path"], "spec/roles/catalog.json")
        self.assertEqual(len(manifest["roles"]), 19)
        prompt_catalog = json.loads(
            (ROOT / self.catalog["prompt_module_package"]).read_text(encoding="utf-8")
        )
        self.assertEqual(
            len(manifest["prompt_modules"]),
            1 + len(prompt_catalog["module_entries"]),
        )
        for record in [manifest["catalog"], *manifest["roles"], *manifest["prompt_modules"]]:
            path = ROOT / record["path"]
            payload = path.read_bytes()
            self.assertEqual(record["bytes"], len(payload))
            import hashlib

            self.assertEqual(record["sha256"], hashlib.sha256(payload).hexdigest())

    def test_controller_entrypoints_are_exact_and_roles_remain_non_user_facing(self) -> None:
        actual = tuple(
            (entry["route"], entry["role"], entry["invocation_mode"])
            for entry in self.catalog["controller_entrypoints"]
        )
        self.assertEqual(actual, EXPECTED_CONTROLLER_ENTRYPOINTS)
        topology = self.catalog["interaction_topology"]
        self.assertEqual(topology["user_facing_identity"], "harness_root_controller")
        self.assertFalse(topology["canonical_roles_user_facing"])

    def test_human_request_originators_match_trigger_owners(self) -> None:
        topology = self.catalog["interaction_topology"]
        self.assertEqual(
            tuple(topology["human_request_originators"]),
            EXPECTED_HUMAN_REQUEST_ORIGINATORS,
        )
        trigger_roles = {
            role["name"] for role in self.roles if role["human_decision_triggers"]
        }
        self.assertEqual(trigger_roles, set(EXPECTED_HUMAN_REQUEST_ORIGINATORS))

    def test_every_spawn_edge_has_exactly_one_child_parent_mode(self) -> None:
        declared: dict[tuple[str, str], str] = {}
        for child, entry in self.entries.items():
            for mode in entry["allowed_parent_modes"]:
                if mode["parent_kind"] != "canonical_role":
                    continue
                for parent in mode["parents"]:
                    edge = (parent, child)
                    self.assertNotIn(edge, declared)
                    declared[edge] = mode["mode"]
        spawned = {
            (parent, child)
            for parent, role in self.by_name.items()
            for child in role["spawns"]
        }
        self.assertEqual(set(declared), spawned)

    def test_all_roles_are_reachable_from_the_four_controller_entrypoints(self) -> None:
        roots = [entry["role"] for entry in self.catalog["controller_entrypoints"]]
        reached: set[str] = set()
        stack = list(roots)
        while stack:
            current = stack.pop()
            if current in reached:
                continue
            reached.add(current)
            stack.extend(self.by_name[current]["spawns"])
        self.assertEqual(reached, set(self.by_name))

    def test_context_sensitive_parent_modes_are_explicit(self) -> None:
        worker_modes = {
            mode["mode"]: set(mode["parents"])
            for mode in self.entries["bbk_worker"]["allowed_parent_modes"]
        }
        self.assertEqual(
            worker_modes,
            {
                "CANDIDATE_PRODUCTION": {"bbk_worker_orchestrator"},
                "PROTOTYPE_SUPPORT": {"bbk_prototyper"},
            },
        )
        self.assertEqual(
            set(self.by_name["bbk_worker"]["return_contract"]["allowed_invocation_modes"]),
            set(worker_modes),
        )
        validator_modes = {
            mode["mode"]: set(mode["parents"])
            for mode in self.entries["bbk_validator_orchestrator"]["allowed_parent_modes"]
        }
        self.assertEqual(
            validator_modes,
            {
                "TERRITORY_BOUND": {"bbk_territory_orchestrator"},
                "CONTROLLER_ROOT": {"harness_root_controller"},
            },
        )

    def test_reviewer_root_child_and_manifest_modes_are_distinct(self) -> None:
        pairs = {
            (mode["mode"], mode["parent_kind"], parent)
            for mode in self.entries["bbk_reviewer"]["allowed_parent_modes"]
            for parent in mode["parents"]
        }
        self.assertIn(
            ("DIRECT_BOUNDED_REVIEW", "controller", "harness_root_controller"),
            pairs,
        )
        self.assertIn(
            ("MANIFEST_ATTEMPT", "canonical_role", "bbk_validator_orchestrator"),
            pairs,
        )
        self.assertNotIn(
            ("DIRECT_BOUNDED_REVIEW", "canonical_role", "bbk_validator_orchestrator"),
            pairs,
        )

    def test_prototyper_topology_remains_bounded(self) -> None:
        self.assertEqual(
            set(self.by_name["bbk_prototyper"]["spawns"]),
            {"bbk_worker_designer", "bbk_worker"},
        )
        self.assertIn("coordination", self.by_name["bbk_prototyper"]["constitution"])

    def test_projection_drift_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._minimal_copy(root)
            package = assemble(root)
            projection = root / "spec" / "roles.json"
            projection.write_bytes(projection.read_bytes() + b"\n")
            self.assertTrue(projection_drift(package))

    def test_noncanonical_split_source_serialization_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._minimal_copy(root)
            role_path = root / "spec" / "roles" / "bbk_worker-role.json"
            role_path.write_bytes(role_path.read_bytes() + b"\n")
            with self.assertRaises(RolePackageError) as caught:
                assemble(root)
            self.assertIn("is not canonically serialized", "\n".join(caught.exception.errors))

    def test_uncatalogued_split_role_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._minimal_copy(root)
            shutil.copy2(
                root / "spec" / "roles" / "bbk_worker-role.json",
                root / "spec" / "roles" / "bbk_uncatalogued-role.json",
            )
            with self.assertRaises(RolePackageError) as caught:
                assemble(root)
            self.assertIn("uncatalogued split role files", "\n".join(caught.exception.errors))

    def test_role_schema_violation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._minimal_copy(root)
            role_path = root / "spec" / "roles" / "bbk_worker-role.json"
            role = json.loads(role_path.read_text(encoding="utf-8"))
            del role["purpose"]
            role_path.write_bytes(canonical_bytes(role))
            with self.assertRaises(RolePackageError) as caught:
                assemble(root)
            self.assertIn("missing fields ['purpose']", "\n".join(caught.exception.errors))

    def test_method_content_version_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._minimal_copy(root)
            path = root / "spec" / "method-content.json"
            method = json.loads(path.read_text(encoding="utf-8"))
            method["version"] = "0.1.0-alpha.12.4"
            path.write_bytes(canonical_bytes(method))
            with self.assertRaises(RolePackageError) as caught:
                assemble(root)
            self.assertIn("method-content version", "\n".join(caught.exception.errors))

    def test_controller_entrypoint_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._minimal_copy(root)
            path = root / "spec" / "roles" / "catalog.json"
            catalog = json.loads(path.read_text(encoding="utf-8"))
            catalog["controller_entrypoints"][0]["invocation_mode"] = "WRONG_ROOT_MODE"
            path.write_bytes(canonical_bytes(catalog))
            with self.assertRaises(RolePackageError) as caught:
                assemble(root)
            self.assertIn("controller entrypoints must be exactly", "\n".join(caught.exception.errors))

    def test_human_request_originator_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._minimal_copy(root)
            path = root / "spec" / "roles" / "catalog.json"
            catalog = json.loads(path.read_text(encoding="utf-8"))
            catalog["interaction_topology"]["human_request_originators"] = [
                "bbk_root_wayfinder",
                "bbk_question_guide",
                "bbk_researcher",
            ]
            path.write_bytes(canonical_bytes(catalog))
            with self.assertRaises(RolePackageError) as caught:
                assemble(root)
            self.assertIn("human request originators must be exactly", "\n".join(caught.exception.errors))

    def test_role_return_mode_drift_from_catalog_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._minimal_copy(root)
            path = root / "spec" / "roles" / "bbk_reviewer-role.json"
            role = json.loads(path.read_text(encoding="utf-8"))
            role["return_contract"]["allowed_invocation_modes"] = [
                "DIRECT_BOUNDED_REVIEW"
            ]
            path.write_bytes(canonical_bytes(role))
            with self.assertRaises(RolePackageError) as caught:
                assemble(root)
            self.assertIn(
                "allowed_invocation_modes must exactly match",
                "\n".join(caught.exception.errors),
            )

    def test_unintended_delegation_cycle_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._minimal_copy(root)

            worker_path = root / "spec" / "roles" / "bbk_worker-role.json"
            worker = json.loads(worker_path.read_text(encoding="utf-8"))
            worker["constitution"] = ["core", "coordination", "execution"]
            worker["spawns"] = ["bbk_worker_orchestrator"]
            worker["delegation"] = {
                "bbk_worker_orchestrator": "Synthetic cycle used only to test graph rejection."
            }
            worker_path.write_bytes(canonical_bytes(worker))

            catalog_path = root / "spec" / "roles" / "catalog.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            child = next(
                entry
                for entry in catalog["role_entries"]
                if entry["name"] == "bbk_worker_orchestrator"
            )
            child["allowed_parent_modes"].append(
                {
                    "mode": "SYNTHETIC_CYCLE",
                    "parent_kind": "canonical_role",
                    "parents": ["bbk_worker"],
                    "purpose": "Synthetic cycle used only to test graph rejection.",
                }
            )
            catalog_path.write_bytes(canonical_bytes(catalog))

            with self.assertRaises(RolePackageError) as caught:
                assemble(root)
            self.assertIn(
                "unintended canonical-role delegation cycle",
                "\n".join(caught.exception.errors),
            )

    def test_one_sided_spawn_edge_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._minimal_copy(root)
            catalog_path = root / "spec" / "roles" / "catalog.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            worker = next(
                entry for entry in catalog["role_entries"] if entry["name"] == "bbk_worker"
            )
            worker["allowed_parent_modes"] = [
                mode
                for mode in worker["allowed_parent_modes"]
                if mode["mode"] != "PROTOTYPE_SUPPORT"
            ]
            catalog_path.write_bytes(canonical_bytes(catalog))
            with self.assertRaises(RolePackageError) as caught:
                assemble(root)
            self.assertIn(
                "spawn edges missing from child allowed-parent contracts",
                "\n".join(caught.exception.errors),
            )

    def test_legacy_command_surface_invokes_v4_assembler(self) -> None:
        completed = subprocess.run(
            [sys.executable, ROOT / "tools" / "create_role_spec.py", "--check"],
            cwd=ROOT,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("canonical split roles validated", completed.stdout)


if __name__ == "__main__":
    unittest.main()

# Deterministic fast/standard/release selection used by tools/run_tests.py.
from tests._test_profiles import load_profiled_tests as load_tests
