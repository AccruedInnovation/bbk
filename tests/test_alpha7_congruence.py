from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BBK = ROOT / "tools" / "bbk.py"


class Alpha7CongruenceTests(unittest.TestCase):
    def test_release_is_additive_over_alpha6(self):
        self.assertEqual((ROOT / "VERSION").read_text(encoding="utf-8").strip(), "0.1.0-alpha.11.7")
        help_text = subprocess.run([sys.executable, BBK, "--help"], cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout
        for command in ("fit", "structure", "slice", "profile", "manifest", "candidate", "gate", "workspace", "worktree", "package"):
            self.assertIn(command, help_text)
        for command in ("assurance", "state-effect", "trace", "evidence", "review"):
            self.assertIn(command, help_text)

    def test_new_schemas_skills_and_references_exist(self):
        schemas = {path.name for path in (ROOT / "spec" / "schemas").glob("*.json")}
        for name in (
            "bbk-state-decision-effect-design-v1.schema.json",
            "bbk-state-transition-trace-v1.schema.json",
            "bbk-implementation-structure-contract-v2.schema.json",
            "bbk-assurance-contract-v1.schema.json",
            "bbk-review-manifest-v1.schema.json",
            "bbk-review-context-manifest-v1.schema.json",
            "bbk-review-run-v1.schema.json",
            "bbk-evidence-receipt-v2.schema.json",
            "bbk-review-finding-v1.schema.json",
            "bbk-finding-disposition-v1.schema.json",
            "bbk-learning-candidate-v1.schema.json",
        ):
            self.assertIn(name, schemas)
        skills = {path.parent.name for path in (ROOT / "shared" / "skills").glob("*/SKILL.md")}
        self.assertEqual(len(skills), 21)
        for name in ("bbk-state-decision-effect-design", "bbk-review-plan", "bbk-review-context", "bbk-review-run", "bbk-review-findings", "bbk-review-intent", "bbk-review-learn", "bbk-context-routing", "bbk-procedure-design"):
            self.assertIn(name, skills)
        self.assertEqual(len(list((ROOT / "shared" / "references").glob("*.md"))), 20)

    def test_role_catalogue_is_extended_not_replaced(self):
        roles = json.loads((ROOT / "spec" / "roles.json").read_text(encoding="utf-8"))
        self.assertEqual(len(roles["roles"]), 19)
        reviewer = next(role for role in roles["roles"] if role["id"] == "reviewer")
        validator = next(role for role in roles["roles"] if role["id"] == "validator")
        self.assertGreaterEqual(len(reviewer["responsibilities"]), 7)
        self.assertIn("bbk-review-run", reviewer["skills"])
        self.assertIn("bbk-review-findings", validator["skills"])
        self.assertIn("bbk-state-decision-effect-design", validator["skills"])

    def test_omp_surface_is_additive(self):
        source = (ROOT / "omp" / "extension" / "index.js").read_text(encoding="utf-8")
        tools = re.findall(r'name: "(bbk_[^"]+)"', source)
        commands = re.findall(r'registerCommand\(pi, "(bbk(?::[^"]*)?)"', source)
        commands += re.findall(r'pi\.registerCommand\("(bbk(?::[^"]*)?)"', source)
        self.assertEqual(len(tools), 26)
        self.assertEqual(len(commands), 27)
        for name in ("bbk_manifest", "bbk_candidate", "bbk_gate", "bbk_workspace", "bbk_review_plan", "bbk_review_run", "bbk_state_effect_validate"):
            self.assertIn(name, tools)

    def test_installer_copies_alpha7_cli_modules(self):
        source = (ROOT / "tools" / "install.py").read_text(encoding="utf-8")
        for name in ("bbk.py", "contracts.py", "state_effect.py", "review_assurance.py", "verify_package.py"):
            self.assertIn(name, source)

    def test_current_method_and_public_contributor_docs_are_present(self):
        for relative in (
            "docs/STATE-DECISION-EFFECT.md",
            "docs/REVIEW-ASSURANCE.md",
            "docs/DEVELOPMENT.md",
            "docs/UPGRADING.md",
            "CONTRIBUTING.md",
            "SECURITY.md",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)
        self.assertFalse((ROOT / "docs" / "source-prds").exists())
        self.assertFalse((ROOT / "docs" / "profile-update-prds").exists())


if __name__ == "__main__":
    unittest.main()
