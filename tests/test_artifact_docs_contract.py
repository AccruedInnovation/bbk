"""Focused contract checks for the public artifact-package reference."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "shared" / "skills" / "bbk-artifact" / "references" / "artifact-package-reference.md"


class ArtifactDocsContractTests(unittest.TestCase):
    def test_reference_covers_transaction_publication_and_recovery_contract(self) -> None:
        text = REFERENCE.read_text(encoding="utf-8")
        normalized = " ".join(text.split())
        required = (
            "Run `doctor` before materialization",
            "publication namespace lock before the package-ID lock",
            "Each OS-held lock",
            "durable operation token",
            "Lock age, PID, host",
            "0/25/50/100/200/400 ms",
            "Win32 32 or 33",
            "no-replace creation",
            "receipt readback and schema/hash verification",
            "decisive target verification",
            "`seal` is an explicit `NON_PUBLISHED`",
            "`finalize` is the operation",
            "`freshness` is a separate read-only check",
            "`RECOVERY_REQUIRED`",
            "`CONFLICT_REJECTED`",
            "`CANCELLED_PRESERVED`",
            "`PUBLISH_BLOCKED`",
            "Quarantine is limited to an exact",
            "does not reread a mutable draft, regenerate package",
            "v1 read compatibility",
            "`BBK-JSON-1`",
            "exact input bytes (`UNCHANGED`)",
            "v2 content identity is",
            "internal seal constructor",
            "signed-attestation semantics",
            "`--recover-stale-lock` is deliberately rejected",
        )
        for statement in required:
            self.assertIn(statement, normalized)

    def test_command_synopsis_exposes_qualified_operations(self) -> None:
        text = REFERENCE.read_text(encoding="utf-8")
        self.assertIn("doctor --root PROJECT_ROOT", text)
        self.assertIn("reconcile JOURNAL_OR_OPERATION", text)
        self.assertIn("freshness PUBLICATION_OR_CURRENT_OR_SEALED", text)


if __name__ == "__main__":
    unittest.main()


