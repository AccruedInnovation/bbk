from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests._cli_support import run_cli


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "tools" / "bbk.py"


def _draft(project: Path, package_id: str) -> Path:
    draft = project / f"{package_id}-draft"
    draft.mkdir(parents=True)
    (draft / "payload.txt").write_text("artifact cli fixture\n", encoding="utf-8")
    (draft / "bbk-package-draft.json").write_text(
        json.dumps(
            {
                "schema": "bbk.artifact-package-draft.v1",
                "packageId": package_id,
                "revision": "1",
                "profile": {"id": "generic", "version": "1"},
                "subject": {"kind": "test", "id": package_id, "revision": "1"},
                "predecessor": None,
                "artifacts": [{"artifactId": "payload", "path": "payload.txt", "role": "semantic", "references": []}],
                "metadata": {"purpose": "CLI producer check"},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return draft


def _json(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    if result.returncode not in (0, 1):
        raise AssertionError(result.stderr or result.stdout)
    return json.loads(result.stdout)


class ArtifactCliV2Tests(unittest.TestCase):
    def run_cli(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return run_cli([sys.executable, str(CLI), "--json", *args], cwd=cwd or ROOT, check=False, timeout=180)

    def test_doctor_help_and_json_surface(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            help_result = self.run_cli("artifact", "doctor", "--help")
            self.assertEqual(help_result.returncode, 0, help_result.stderr)
            self.assertIn("--publication-root", help_result.stdout)
            doctor = _json(self.run_cli("artifact", "doctor", "--root", str(root)))
            self.assertEqual(doctor["schema"], "bbk.artifact-doctor-result.v1")
            self.assertEqual(doctor["status"], "PASS")

    def test_seal_finalize_freshness_and_reconcile_delegate_to_core(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            sealed_draft = _draft(project, "seal-cli")
            sealed = self.run_cli("artifact", "seal", str(sealed_draft), "--output", str(project / "sealed"))
            seal = _json(sealed)
            self.assertEqual(seal["status"], "PASS")
            self.assertEqual(seal["publicationState"], "NON_PUBLISHED")
            self.assertTrue(seal["operationId"])
            self.assertTrue(seal["journalPath"])

            by_path = _json(self.run_cli("artifact", "reconcile", str(seal["journalPath"]), "--root", str(project)))
            self.assertEqual(by_path["status"], "PASS")
            self.assertTrue(by_path["readOnly"])
            by_id = _json(self.run_cli("artifact", "reconcile", str(seal["operationId"]), "--root", str(project)))
            self.assertEqual(by_id["operationId"], seal["operationId"])
            self.assertEqual(by_id["disposition"], "NON_PUBLISHED")

            final_draft = _draft(project, "finalize-cli")
            finalized = _json(self.run_cli("artifact", "finalize", str(final_draft), "--root", str(project)))
            self.assertEqual(finalized["status"], "PASS")
            self.assertEqual(finalized["publicationState"], "PUBLISHED")
            self.assertTrue(finalized["journalPath"])
            freshness = _json(self.run_cli("artifact", "freshness", str(finalized["publicationReceipt"]), "--root", str(project)))
            self.assertEqual(freshness["status"], "PASS")

    def test_stale_lock_takeover_compatibility_flag_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            draft = _draft(project, "stale-flag")
            result = self.run_cli(
                "artifact", "seal", str(draft), "--output", str(project / "sealed"), "--recover-stale-lock"
            )
            self.assertEqual(result.returncode, 1)
            value = _json(result)
            self.assertEqual(value["status"], "REJECTED")
            self.assertEqual(value["code"], "PACKAGE_LOCK_RECOVERY_REQUIRES_RECONCILE")

    def test_callable_delegation_and_behavior_free_wrapper(self):
        surface = (ROOT / "tools" / "bbk.py").read_text(encoding="utf-8")
        wrapper = (ROOT / "tools" / "bbk_artifact.py").read_text(encoding="utf-8")
        self.assertIn("doctor as artifact_doctor", surface)
        self.assertIn("reconcile_operation as artifact_reconcile_operation", surface)
        self.assertNotIn("_journal_transition", surface)
        self.assertNotIn("def seal", wrapper)
        self.assertNotIn("def finalize", wrapper)
        subprocess.run([sys.executable, str(ROOT / "tools" / "bbk_artifact.py"), "--help"], cwd=ROOT, check=True)


if __name__ == "__main__":
    unittest.main()


