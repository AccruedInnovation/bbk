from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import generate_role_capabilities as compiler


class RoleCapabilityProjectionTests(unittest.TestCase):
    def test_projection_is_deterministic_complete_and_current(self) -> None:
        manifests, index = compiler.compile_manifests()
        catalog = json.loads((ROOT / "spec" / "roles" / "catalog.json").read_text(encoding="utf-8"))
        canonical = {item["name"] for item in catalog["role_entries"]}
        self.assertEqual(canonical, set(manifests))
        self.assertEqual(len(canonical), index["role_count"])
        self.assertEqual([], compiler.check_outputs())
        completed = subprocess.run(
            [sys.executable, "tools/generate_role_capabilities.py", "--check"],
            cwd=ROOT,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)

    def test_control_plane_roles_receive_no_product_mutation_surface(self) -> None:
        manifests, _ = compiler.compile_manifests()
        for role in (
            "bbk_root_orchestrator",
            "bbk_territory_orchestrator",
            "bbk_worker_orchestrator",
            "bbk_validator_orchestrator",
        ):
            with self.subTest(role=role):
                manifest = manifests[role]
                self.assertEqual(["COORDINATION_METADATA"], manifest["allowed_mutation_classes"])
                self.assertNotIn("bbk_governed_write", manifest["allowed_tools"])
                self.assertNotIn("bbk_governed_edit", manifest["allowed_tools"])
                self.assertNotIn("bbk_governed_delete", manifest["allowed_tools"])
                self.assertNotIn("bash", manifest["allowed_tools"])
                self.assertNotIn("bd", manifest["allowed_tools"])
                self.assertNotIn("bbk_control_beads_transition", manifest["allowed_tools"])
                self.assertNotIn("bbk_control_integration_request", manifest["allowed_tools"])
                self.assertTrue(
                    {
                        "bbk_control_assign",
                        "bbk_control_update",
                        "bbk_control_integrate_request",
                    }.issubset(set(manifest["allowed_tools"]))
                )
                self.assertIn("PRODUCT_CONTENT", manifest["forbidden_effects"])
                self.assertIn("DIRECT_BEADS_WRITE", manifest["forbidden_effects"])
                self.assertIn("UNQUALIFIED_SHELL", manifest["forbidden_effects"])

    def test_reviewer_and_validator_are_candidate_read_only(self) -> None:
        manifests, _ = compiler.compile_manifests()
        for role in ("bbk_reviewer", "bbk_validator"):
            with self.subTest(role=role):
                manifest = manifests[role]
                self.assertEqual([], manifest["allowed_mutation_classes"])
                self.assertEqual("READ_ONLY", manifest["scope_rules"]["path_scope"])
                self.assertIn("CANDIDATE_MUTATION", manifest["forbidden_effects"])
                self.assertEqual({"bbk_governance_status", "bbk_governed_read", "bbk_return_template", "bbk_return_prepare"}, set(manifest["allowed_tools"]))

    def test_writable_workers_require_exact_invocation_and_workspace_binding(self) -> None:
        manifests, _ = compiler.compile_manifests()
        required = {
            "SESSION", "INVOCATION", "WORK_UNIT", "ATTEMPT", "CANDIDATE",
            "WORKSPACE", "JJ_CHANGE", "AUTHORITY", "PATH_SCOPE",
            "MUTATION_CLASS", "RETURN_CONTRACT",
        }
        for role in ("bbk_worker", "bbk_prototyper"):
            with self.subTest(role=role):
                manifest = manifests[role]
                self.assertTrue(required.issubset(set(manifest["required_bindings"])))
                self.assertEqual("REGISTRY_BINDING", manifest["scope_rules"]["workspace_source"])
                self.assertEqual("BOUND_PREFIXES", manifest["scope_rules"]["path_scope"])
                self.assertIn("CROSS_WORKSPACE_WRITE", manifest["forbidden_effects"])

    def test_manifest_identity_binds_role_source_and_policy(self) -> None:
        manifests, index = compiler.compile_manifests()
        self.assertRegex(index["manifest_digest"], r"^sha256:[0-9a-f]{64}$")
        for role, manifest in manifests.items():
            with self.subTest(role=role):
                self.assertRegex(manifest["manifest_digest"], r"^sha256:[0-9a-f]{64}$")
                self.assertRegex(manifest["source_role_digest"], r"^sha256:[0-9a-f]{64}$")
                stored = json.loads((ROOT / "spec" / "role-capabilities" / f"{role}.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest, stored)


if __name__ == "__main__":
    unittest.main()
