from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BBK = ROOT / "tools" / "bbk.py"
spec = importlib.util.spec_from_file_location("bbk_alpha6_cli", BBK)
bbk = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(bbk)


class Alpha6CongruenceTests(unittest.TestCase):
    maxDiff = None

    def load(self, rel: str):
        return json.loads((ROOT / rel).read_text(encoding="utf-8"))

    def cli(self, *args: str, check: bool = True):
        return subprocess.run(
            [sys.executable, "-B", str(BBK), *args], cwd=ROOT, check=check,
            capture_output=True, text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )

    def test_alpha3_and_alpha5_command_surfaces_coexist(self):
        help_text = self.cli("--help").stdout
        for command in ("manifest", "candidate", "gate", "workspace", "profile", "beads"):
            self.assertIn(command, help_text)
        for command in ("fit", "structure", "slice", "work-unit", "worktree", "package", "digest"):
            self.assertIn(command, help_text)

    def test_solution_outcome_fit_examples_and_nonaveraging_risk(self):
        expected = {
            "confirmed-fit.json": ("CONFIRMED_FIT", "CLEAR"),
            "reframed-dashboard.json": ("REFRAMED", "CLEAR"),
            "investigate-fit.json": ("INVESTIGATE", "BLOCKED"),
            "preference-driven.json": ("PREFERENCE_DRIVEN", "CLEAR"),
            "constraint-required.json": ("CONSTRAINT_REQUIRED", "CLEAR"),
            "no-change-preferred.json": ("NO_CHANGE_PREFERRED", "CLEAR"),
        }
        for name, (disposition, commitment) in expected.items():
            report = bbk.validate_solution_outcome_fit(self.load(f"fixtures/fit/{name}"))
            self.assertTrue(report["valid"], report)
            self.assertEqual(report["planningDisposition"]["fitDisposition"], disposition)
            self.assertEqual(report["planningDisposition"]["solutionCommitment"], commitment)
        self.assertEqual(bbk.derive_fit_risk_tier({"consequence":4,"irreversibility":0,"uncertainty":0,"interfaceExposure":0}), "critical")
        self.assertEqual(bbk.derive_fit_risk_tier({"consequence":2,"irreversibility":2,"uncertainty":0,"interfaceExposure":0}), "consequential")

    def test_invalid_fit_and_blocked_chain(self):
        invalid = bbk.validate_solution_outcome_fit(self.load("fixtures/fit/invalid-intervention-as-outcome.json"))
        self.assertFalse(invalid["valid"])
        result = self.cli("--json", "fit", "check-chain", "--fit", "fixtures/fit/investigate-fit.json", "--structure", "fixtures/structure/software-contract.json", check=False)
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["valid"])
        self.assertTrue(any("blocks material solution commitment" in value for value in payload["errors"]))

    def test_fit_structure_slice_work_unit_chain(self):
        result = self.cli(
            "--json", "fit", "check-chain", "--fit", "fixtures/fit/confirmed-fit.json",
            "--structure", "fixtures/structure/software-contract.json",
            "--slice", "fixtures/slices/software-slice-1.json",
            "--slice", "fixtures/slices/software-slice-2.json",
            "--work-unit", "fixtures/work-units/query-service.json",
        )
        payload = json.loads(result.stdout)
        self.assertTrue(payload["valid"], payload)
        self.assertEqual(payload["fit"]["identity"], "SOF-DECISION-QUERY@r1")
        self.assertEqual(len(payload["chain"]["slices"]), 2)

    def test_structure_slice_and_stable_renderers(self):
        for name in ("software-contract.json", "procedure-contract.json"):
            value = self.load(f"fixtures/structure/{name}")
            report = bbk.validate_structure(value)
            self.assertTrue(report["valid"], report)
            self.assertEqual(bbk.markdown_structure(value), bbk.markdown_structure(value))
        self.assertFalse(bbk.validate_structure(self.load("fixtures/structure/invalid-contract.json"))["valid"])
        slices = [self.load("fixtures/slices/software-slice-1.json"), self.load("fixtures/slices/software-slice-2.json")]
        self.assertTrue(bbk.validate_slice_set(slices)["valid"])
        slices[1]["dependsOn"] = ["missing"]
        self.assertFalse(bbk.validate_slice_set(slices)["valid"])

    def test_legacy_and_current_work_units_validate(self):
        current = bbk.validate_work_unit(self.load("fixtures/work-units/query-service.json"))
        self.assertTrue(current["valid"], current)
        legacy = {
            "schema":"bbk.work-unit.v1", "id":"WU-LEGACY", "purpose":"Preserve alpha.3 syntax",
            "task_profile":"implementation", "assurance_tier":"routine", "scope":["src/**"],
            "language_profiles":["legacy-fixture"], "profile_hints":[], "change_classes":[],
        }
        report = bbk.validate_work_unit(legacy)
        self.assertTrue(report["valid"], report)
        self.assertEqual(report["normalized"]["taskProfile"], "implementation")
        self.assertEqual(report["normalized"]["assuranceTier"], "routine")
        self.assertTrue(report["warnings"])

    def test_legacy_and_current_profiles_resolve(self):
        legacy = bbk.validate_profile(self.load("fixtures/profiles/legacy/PROFILE.json"))
        current = bbk.validate_profile(self.load("fixtures/profiles/alpha4/PROFILE.json"))
        self.assertTrue(legacy["valid"], legacy)
        self.assertEqual(legacy["implementationStructureSupport"], "legacy-unprojected")
        self.assertTrue(current["valid"], current)
        self.assertEqual(current["implementationStructureSupport"], "supported")
        with tempfile.TemporaryDirectory() as tmp:
            wu = Path(tmp) / "legacy.json"
            wu.write_text(json.dumps({
                "schema":"bbk.work-unit.v1", "id":"WU-LEGACY", "purpose":"Compatibility",
                "task_profile":"implementation", "assurance_tier":"routine", "scope":["src/**"]
            }), encoding="utf-8")
            value = json.loads(self.cli(
                "--json", "profile", "resolve", "--profile-root", "fixtures/profiles",
                "--id", "legacy-fixture", "--work-unit", str(wu), "--allow-unverified"
            ).stdout)
            self.assertEqual(value["profile"]["id"], "legacy-fixture")
            self.assertEqual(value["implementation_structure"]["support"], "legacy-unprojected")
        value = json.loads(self.cli(
            "--json", "profile", "resolve", "--profile-root", "fixtures/profiles",
            "--id", "alpha4-fixture", "--work-unit", "fixtures/work-units/query-service.json",
            "--solution-outcome-fit", "fixtures/fit/confirmed-fit.json",
            "--structure-contract", "fixtures/structure/software-contract.json",
            "--execution-slice", "fixtures/slices/software-slice-1.json", "--allow-unverified"
        ).stdout)
        self.assertEqual(value["profile"]["id"], "alpha4-fixture")
        self.assertEqual(value["inputs"]["solutionOutcomeFits"][0]["solutionCommitment"], "CLEAR")
        self.assertEqual(value["implementation_structure"]["support"], "supported")

    def test_blocked_fit_profile_policy(self):
        result = self.cli(
            "--json", "profile", "resolve", "--profile-root", "fixtures/profiles",
            "--id", "alpha4-fixture", "--task-profile", "implementation", "--assurance-tier", "consequential",
            "--solution-outcome-fit", "fixtures/fit/investigate-fit.json", "--allow-unverified", check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("blocks task profile implementation", json.loads(result.stdout)["error"])
        allowed = self.cli(
            "--json", "profile", "resolve", "--profile-root", "fixtures/profiles",
            "--id", "legacy-fixture", "--task-profile", "investigation-prototype", "--assurance-tier", "consequential",
            "--solution-outcome-fit", "fixtures/fit/investigate-fit.json", "--allow-unverified",
        )
        self.assertEqual(json.loads(allowed.stdout)["inputs"]["taskProfile"], "investigation-prototype")

    def test_roles_preserve_detail_and_add_feature_skills(self):
        roles = self.load("spec/roles.json")
        self.assertEqual(roles["package_version"], (ROOT / "VERSION").read_text(encoding="utf-8").strip())
        self.assertEqual(len(roles["roles"]), 19)
        self.assertGreaterEqual(len(roles["common_constitution"]), 9)
        self.assertTrue(all(len(role["responsibilities"]) >= 5 for role in roles["roles"]))
        self.assertGreaterEqual(sum("bbk-solution-outcome-fit" in role["skills"] for role in roles["roles"]), 8)
        self.assertGreaterEqual(sum("bbk-implementation-structure" in role["skills"] for role in roles["roles"]), 8)

    def test_alpha3_document_and_skill_baseline_is_retained(self):
        for rel in (
            "LICENSE", "docs/INSTALL.md", "docs/USAGE.md", "docs/DEVELOPMENT.md", "docs/QUALIFICATION.md",
            "shared/references/method.md", "shared/references/assurance.md", "shared/references/evidence.md",
            "shared/references/recovery.md", "shared/skills/bbk/SKILL.md", "shared/skills/bbk-plan/SKILL.md",
            "shared/skills/bbk-execute/SKILL.md", "shared/skills/bbk-recover/SKILL.md",
        ):
            self.assertTrue((ROOT / rel).is_file(), rel)
        self.assertGreaterEqual(len(list((ROOT / "shared" / "skills").glob("*/SKILL.md"))), 11)

    def test_init_is_additive_and_installs_current_templates(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = json.loads(self.cli("--json", "init", "--root", tmp, "--project-id", "TEST-A6").stdout)
            self.assertIn(first["status"], {"PASS", "initialized"})
            root = Path(tmp) / ".bbk"
            self.assertTrue((root / "fit" / "EXAMPLE-solution-outcome-fit.json").is_file())
            self.assertTrue((root / "structures" / "EXAMPLE-implementation-structure-contract.json").is_file())
            self.assertTrue((root / "slices" / "EXAMPLE-execution-slice.json").is_file())
            marker = root / "project.md"
            marker.write_text("preserve me\n", encoding="utf-8")
            second = json.loads(self.cli("--json", "init", "--root", tmp).stdout)
            self.assertEqual(marker.read_text(encoding="utf-8"), "preserve me\n")
            self.assertIn(".bbk/project.md", second.get("preserved", []))

    def test_standalone_candidate_and_recorded_gate_receipt_remain_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "a.txt").write_text("one\n", encoding="utf-8")
            candidate = root / "candidate.json"
            self.cli("candidate", "freeze", "--root", str(root), "--output", str(candidate))
            verified = json.loads(self.cli("--json", "candidate", "verify", str(candidate)).stdout)
            self.assertTrue(verified["valid"], verified)
            receipt = root / "receipt.json"
            self.cli("gate", "record", "--candidate", str(candidate), "--gate-id", "fixture", "--status", "PASS", "--output", str(receipt))
            checked = json.loads(self.cli("--json", "gate", "check", str(receipt), "--candidate", str(candidate)).stdout)
            self.assertTrue(checked["valid"], checked)
            (root / "a.txt").write_text("two\n", encoding="utf-8")
            stale = json.loads(self.cli("--json", "candidate", "verify", str(candidate), check=False).stdout)
            self.assertFalse(stale["valid"])

    def test_installer_refuses_divergence_and_backs_up_force_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); home = base / "home"; home.mkdir()
            env = {**os.environ, "BBK_HOME":str(home), "HOME":str(home), "BBK_INSTALL_ROOT":str(base/"data"), "BBK_BIN_DIR":str(base/"bin")}
            install = ROOT / "tools" / "install.py"
            subprocess.run([sys.executable, str(install), "install", "--scope", "user", "--codex", "--no-language-profiles"], check=True, capture_output=True, text=True, env=env)
            target = home / ".codex" / "agents" / "bbk_worker.toml"
            target.write_text(target.read_text(encoding="utf-8") + "\n# local divergence\n", encoding="utf-8")
            rejected = subprocess.run([sys.executable, str(install), "--json", "install", "--scope", "user", "--codex", "--no-language-profiles"], capture_output=True, text=True, env=env)
            self.assertEqual(rejected.returncode, 2)
            self.assertIn("Destination differs", json.loads(rejected.stdout)["error"])
            replaced = subprocess.run([sys.executable, str(install), "--json", "install", "--scope", "user", "--codex", "--no-language-profiles", "--force"], check=True, capture_output=True, text=True, env=env)
            records = [
                item
                for item in json.loads(replaced.stdout)["files"]
                if Path(item["path"]).exists() and Path(item["path"]).samefile(target)
            ]
            self.assertEqual(len(records), 1, records)
            record = records[0]
            self.assertEqual(record["action"], "replace")
            self.assertTrue(Path(record["backup"]).is_file())
            subprocess.run([sys.executable, str(install), "uninstall", "--scope", "user"], check=True, capture_output=True, text=True, env=env)
            self.assertTrue(home.exists())

    def test_schemas_parse_and_support_both_profile_lock_forms(self):
        for path in (ROOT / "spec" / "schemas").glob("*.json"):
            json.loads(path.read_text(encoding="utf-8"))
        lock_schema = self.load("spec/schemas/bbk-profile-lock-v1.schema.json")
        self.assertIn("anyOf", lock_schema)
        profile_schema = self.load("spec/schemas/bbk-language-profile-v1.schema.json")
        self.assertIn("capabilities", profile_schema["properties"])


if __name__ == "__main__":
    unittest.main()
