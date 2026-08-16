from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from replay_oracle import run_replay_oracle  # noqa: E402


def _protected_history_available() -> bool:
    corpus = json.loads(
        (ROOT / "tests" / "fixtures" / "execution-readiness" / "history-corpus.json").read_text(
            encoding="utf-8"
        )
    )
    return all((ROOT / str(entry["path"])).is_file() for entry in corpus.get("entries", []))


class ReplayOracleTests(unittest.TestCase):
    def test_every_predeclared_case_passes_and_history_is_read_only(self):
        subject = ROOT / "tests" / "fixtures" / "execution-readiness" / "replay-oracle.json"
        if _protected_history_available():
            result = run_replay_oracle(subject)
            self.assertEqual("PASS", result["status"])
            self.assertEqual(9, len(result["history_cases"]))
            self.assertEqual(11, len(result["synthetic_cases"]))
            self.assertTrue(result["protected_history"]["byte_identical"])
            self.assertEqual(0, sum(result["write_inventory"].values()))
            self.assertEqual(0, result["reuse_ledger"][0]["execution_count"])
            return

        before = sorted(path.relative_to(ROOT).as_posix() for path in ROOT.rglob("*") if path.is_file())
        with self.assertRaisesRegex(ValueError, r"^protected history reference is unavailable: .+$"):
            run_replay_oracle(subject)
        after = sorted(path.relative_to(ROOT).as_posix() for path in ROOT.rglob("*") if path.is_file())
        self.assertEqual(before, after)

    def test_tampered_expected_row_fails_closed(self):
        path = ROOT / "tests" / "fixtures" / "execution-readiness" / "replay-oracle.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["history_cases"][0]["expected"] = "PASS"
        with tempfile.TemporaryDirectory() as temporary_root:
            temporary = Path(temporary_root) / "oracle-tampered-test.json"
            temporary.write_text(json.dumps(value), encoding="utf-8")
            if _protected_history_available():
                self.assertEqual("FAIL", run_replay_oracle(temporary)["status"])
            else:
                with self.assertRaisesRegex(ValueError, r"^protected history reference is unavailable: .+$"):
                    run_replay_oracle(temporary)


if __name__ == "__main__":
    unittest.main()
