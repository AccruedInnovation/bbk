from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PublicSourceRepositoryTests(unittest.TestCase):
    def test_release_only_payloads_are_absent(self):
        self.assertFalse((ROOT / "bundled-language-profiles").exists())
        self.assertFalse((ROOT / "PACKAGE-MANIFEST.json").exists())
        self.assertFalse((ROOT / "RELEASE-NOTES.md").exists())
        self.assertFalse(list(ROOT.glob("*.sha256")))
        self.assertFalse((ROOT / "SHA256SUMS.txt").exists())

    def test_public_documentation_tree_is_exact(self):
        expected = {
            "INSTALL.md",
            "USAGE.md",
            "AGENT-COMPOSITION.md",
            "MODEL-ROUTING.md",
            "LANGUAGE-PROFILES.md",
            "BOUNDARIES.md",
            "QUALIFICATION.md",
            "SOLUTION-OUTCOME-FIT.md",
            "IMPLEMENTATION-STRUCTURE.md",
            "STATE-DECISION-EFFECT.md",
            "REVIEW-ASSURANCE.md",
            "DEVELOPMENT.md",
            "UPGRADING.md",
        }
        actual = {path.name for path in (ROOT / "docs").iterdir() if path.is_file()}
        self.assertEqual(actual, expected)
        self.assertFalse((ROOT / "docs" / "source-prds").exists())
        self.assertFalse((ROOT / "docs" / "profile-update-prds").exists())

    def test_repository_entry_files_exist(self):
        for relative in (
            "README.md",
            "LICENSE",
            "VERSION",
            "CHANGELOG.md",
            "CONTRIBUTING.md",
            "SECURITY.md",
            ".github/workflows/verify.yml",
            "tools/verify_source_repository.py",
            "tools/repo_setup.py",
            "tools/build_public_release.py",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_readme_links_resolve(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)
        local = [link.split("#", 1)[0] for link in links if "://" not in link and not link.startswith("mailto:")]
        missing = [link for link in local if link and not (ROOT / link).exists()]
        self.assertEqual(missing, [])

    def test_internal_blueprint_dogfood_is_absent(self):
        self.assertFalse((ROOT / "examples" / "blueprint-dogfood").exists())


if __name__ == "__main__":
    unittest.main()
