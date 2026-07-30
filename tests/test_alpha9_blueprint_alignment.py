from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from state_effect import (  # noqa: E402
    validate_state_decision_effect,
    validate_transition_trace,
    validate_transition_trace_set,
)


def load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


class Alpha9BlueprintAlignmentTests(unittest.TestCase):
    def test_alignment_keeps_effort_owner_and_normative_namespaces_explicit(self):
        value = load("spec/blueprint-alignment.json")
        self.assertEqual(value["bbkVersion"], "0.1.0-alpha.11.7")
        namespaces = value["identifierNamespaces"]
        self.assertEqual(
            namespaces["effortOwnerDevelopmentPartitions"]["sequence"],
            ["C0", "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10", "C11"],
        )
        self.assertEqual(
            namespaces["suppliedNormativeRoadmap"]["sequence"],
            ["Q0", "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10", "C11"],
        )
        status = namespaces["effortOwnerDevelopmentPartitions"]["statusAtReview"]
        self.assertEqual(status["C0"], "COMPLETE")
        self.assertEqual(status["C1"], "ACTIVE_NEARLY_COMPLETE")
        self.assertEqual(status["nextIntegrationReview"], "BEFORE_C2")
        rules = " ".join(namespaces["interpretationRules"])
        self.assertIn("must not silently assert", rules)
        self.assertIn("C0 through C11", rules)

    def test_successor_capability_partition_and_compatibility_map_are_complete(self):
        value = load("spec/blueprint-alignment.json")
        self.assertEqual([item["id"] for item in value["successorCapabilities"]], [f"C{i}" for i in range(1, 12)])
        self.assertEqual(value["releaseMarkers"]["firstCompleteLiteReleaseCandidate"], "C8")
        self.assertEqual(value["releaseMarkers"]["integratedBlueprintV1Gate"], "C11")
        self.assertEqual(value["parentCompatibilityMap"]["C3"], ["C3", "C4"])
        self.assertEqual(value["parentCompatibilityMap"]["C4"], ["C5", "C6"])
        self.assertEqual(value["parentCompatibilityMap"]["C5"], ["C7", "C8"])
        self.assertEqual(value["parentCompatibilityMap"]["C8"], ["C11"])

    def test_questioning_wayfinder_is_a_first_class_logical_boundary(self):
        roles = load("spec/roles.json")["roles"]
        self.assertEqual(len(roles), 19)
        by_id = {role["id"]: role for role in roles}
        questioning = by_id["questioning_wayfinder"]
        self.assertIn("bbk_question_guide", questioning["spawns"])
        self.assertIn("bbk-context-routing", questioning["skills"])
        self.assertIn("bbk-procedure-design", questioning["skills"])
        for parent in ("root_wayfinder", "territory_wayfinder"):
            self.assertIn("bbk_questioning_wayfinder", by_id[parent]["spawns"])
            self.assertNotIn("bbk_question_guide", by_id[parent]["spawns"])

    def test_context_and_procedure_methods_are_canonical_and_projected(self):
        method = load("spec/method-content.json")
        self.assertEqual(method["version"], "0.1.0-alpha.11.7")
        self.assertIn("bbk-context-routing", method["skills"])
        self.assertIn("bbk-procedure-design", method["skills"])
        self.assertIn("context-routing.md", method["references"])
        self.assertIn("procedure-design.md", method["references"])
        manifest = load("projections/manifest.json")
        self.assertEqual(manifest["role_count"], 19)
        self.assertEqual(manifest["projection_count"], 76)
        for target in manifest["targets"]:
            names = [path.name for path in (ROOT / "projections" / target / "agents").glob("*")]
            self.assertTrue(any("questioning" in name and "wayfinder" in name for name in names), target)

    def test_current_facing_docs_do_not_publish_the_obsolete_partition_as_current(self):
        current_docs = [
            "README.md",
            "docs/AGENT-COMPOSITION.md",
            "docs/BOUNDARIES.md",
            "docs/QUALIFICATION.md",
            "docs/INSTALL.md",
            "docs/USAGE.md",
            "docs/DEVELOPMENT.md",
            "docs/UPGRADING.md",
        ]
        joined = "\n".join((ROOT / rel).read_text(encoding="utf-8") for rel in current_docs)
        self.assertIsNone(re.search(r"C0\s*(?:–|-|\.\.)\s*C8", joined))
        self.assertIn("Blueprint", joined)
        self.assertIn("histor", joined.casefold())
        # Capability-partition namespaces remain in the canonical alignment
        # specification and release history, not the consumer documentation.
        alignment = load("spec/blueprint-alignment.json")
        rendered = json.dumps(alignment, ensure_ascii=False)
        for marker in ("C0", "C11", "Q0"):
            self.assertIn(marker, rendered)

    def test_current_role_constitution_is_not_bound_to_product_status(self):
        constitution = " ".join(load("spec/roles.json")["common_constitution"])
        lowered = constitution.casefold()
        self.assertNotIn("q0/c1 state", lowered)
        self.assertNotIn("c0–c11", lowered)
        self.assertNotIn("blueprint", lowered)
        self.assertNotIn("tenex", lowered)
        self.assertIn("logical responsibility", constitution)
        self.assertIn("append-only evidence exposure", constitution)
        self.assertIn("does not create authority", constitution)


if __name__ == "__main__":
    unittest.main()
