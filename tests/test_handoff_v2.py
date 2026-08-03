from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "tools" / "bbk.py"
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from artifact_packages import validate_schema_instance
from strict_json import load_path


class HandoffV2Tests(unittest.TestCase):
    def run_cli(self, *args: str, check: bool = True) -> tuple[subprocess.CompletedProcess[str], dict]:
        completed = subprocess.run(
            [sys.executable, str(CLI), "--json", *args],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        payload = json.loads(completed.stdout) if completed.stdout.strip() else {}
        if check and completed.returncode != 0:
            self.fail(f"CLI failed ({completed.returncode}): {completed.stderr}\n{completed.stdout}")
        return completed, payload

    def init(self, root: Path) -> None:
        self.run_cli("init", "--root", str(root), "--title", "handoff-test", "--project-id", "handoff-test", "--no-examples")

    def create(self, root: Path, *extra: str, legacy: bool = False) -> dict:
        args = [
            "handoff", "create", "--root", str(root), "--work-unit", "WU-HANDOFF",
            "--attempt", "1", "--disposition", "COMPLETE",
            "--summary", "Implemented the exact bounded work.",
            "--work-performed", "changed the assigned fixture",
            "--check", "focused test passed",
            "--next-action", "Parent integrates the exact sealed package.",
            *extra,
        ]
        if legacy:
            args.append("--legacy-v1")
        return self.run_cli(*args)[1]

    def test_default_constructor_creates_sealed_v2_without_manual_digest_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.init(root)
            artifact = root / "result.txt"; artifact.write_text("exact result\n", encoding="utf-8")
            created = self.create(root, "--artifact", str(artifact))
            self.assertEqual(created["schema"], "bbk.handoff-verification.v2")
            self.assertTrue(created["valid"])
            package = root / created["handoff"]["path"]
            self.assertTrue(package.is_dir())
            semantic = load_path(package / "handoff.json")
            self.assertEqual(semantic["schema"], "bbk.handoff.v2")
            self.assertNotIn("sha256", semantic)
            self.assertNotIn("bytes", semantic)
            self.assertEqual(semantic["artifacts"][0]["artifactId"], "artifact-001")
            self.assertIn("release", semantic["prohibited_claims"])
            self.assertEqual(validate_schema_instance(semantic, "bbk.handoff.v2"), [])

    def test_package_tampering_is_detected_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.init(root)
            created = self.create(root)
            package = root / created["handoff"]["path"]
            before = (package / "bbk-package.json").read_bytes()
            (package / "handoff.json").write_text("tampered\n", encoding="utf-8")
            completed, verified = self.run_cli("handoff", "verify", str(package), "--root", str(root), check=False)
            self.assertNotEqual(completed.returncode, 0)
            self.assertFalse(verified["valid"])
            self.assertEqual((package / "bbk-package.json").read_bytes(), before)

    def test_sealed_handoff_never_overwrites_even_with_force(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.init(root)
            created = self.create(root)
            package = root / created["handoff"]["path"]
            completed, failure = self.run_cli(
                "handoff", "create", "--root", str(root), "--work-unit", "WU-HANDOFF",
                "--attempt", "1", "--disposition", "COMPLETE", "--summary", "again",
                "--next-action", "choose a successor", "--output", str(package), "--force",
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("immutable", failure["error"])
            self.assertTrue(package.is_dir())

    def test_legacy_v1_is_explicitly_constructible_and_both_versions_are_listed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.init(root)
            current = self.create(root, "--id", "HO-WU-HANDOFF-V2")
            legacy = self.create(root, "--id", "HO-WU-HANDOFF-V1", "--attempt", "2", legacy=True)
            self.assertEqual(current["schema"], "bbk.handoff-verification.v2")
            self.assertEqual(legacy["schema"], "bbk.handoff-verification.v1")
            listed = self.run_cli("handoff", "list", "--root", str(root), "--work-unit", "WU-HANDOFF")[1]
            self.assertEqual(listed["schema"], "bbk.handoff-list.v2")
            self.assertEqual(listed["count"], 2)
            self.assertEqual({item["format"] for item in listed["handoffs"]}, {"SEALED_V2", "LEGACY_V1"})
            self.assertEqual(listed["compatibility"], {"defaultProducer": "bbk.handoff.v2", "legacyV1Readable": True})

    def test_beads_projection_consumes_verified_v2_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.init(root)
            created = self.create(root)
            package = root / created["handoff"]["path"]
            plan = self.run_cli("beads", "handoff-plan", "--root", str(root), "--handoff", str(package), "--bead", "bd-123")[1]
            self.assertEqual(plan["status"], "PASS")
            self.assertIn(created["handoff"]["sha256"], plan["note"])
            self.assertIn("bd-123", json.dumps(plan))

    def test_default_schema_template_is_v2_and_v1_remains_named(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current = root / "current.json"; legacy = root / "legacy.json"
            self.run_cli("schema", "template", "--kind", "handoff", "--output", str(current))
            self.run_cli("schema", "template", "--kind", "handoff-v1", "--output", str(legacy))
            self.assertEqual(load_path(current)["schema"], "bbk.handoff.v2")
            self.assertEqual(load_path(legacy)["schema"], "bbk.handoff.v1")


if __name__ == "__main__":
    unittest.main()
