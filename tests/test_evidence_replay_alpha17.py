from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import evidence_replay as er  # noqa: E402


class EvidenceReplayTests(unittest.TestCase):
    def attempt(self):
        return {
            "schema": "bbk.command-attempt.v1",
            "semantic_command_id": "cmd:1",
            "execution_attempt_ref": "exec:1",
            "physical_command_attempt": 1,
            "effect_class": "READ_ONLY",
            "disposition": "EVIDENCE_CAPTURE_FAILED",
            "effects_observed": {"product_mutation": "NONE", "external_effect": "NONE"},
            "cleanup": {"state": "COMPLETE", "remaining_processes_or_handles": False},
            "invocation_identity": er.invocation_identity("python", ["-V"], {}, {"cwd": "fixture"}),
            "replay": {"eligible": True, "reason": "capture-only failure", "maximum_replays": 1, "replay_of_physical_attempt": None},
        }

    def test_capture_only_failure_allows_exactly_one_same_attempt_replay(self):
        decision = er.evaluate_replay(self.attempt())
        self.assertTrue(decision["eligible"])
        replay = er.replay_attempt(self.attempt())
        self.assertEqual(2, replay["physical_command_attempt"])
        self.assertEqual("exec:1", replay["execution_attempt_ref"])
        self.assertEqual("PLANNED", replay["disposition"])
        replay["disposition"] = "EVIDENCE_CAPTURE_FAILED"
        self.assertFalse(er.evaluate_replay(replay)["eligible"])

    def test_mutation_unknown_cleanup_and_frozen_candidate_block(self):
        cases = []
        a = self.attempt(); a["effects_observed"]["product_mutation"] = "UNKNOWN"; cases.append((a, False))
        a = self.attempt(); a["cleanup"]["state"] = "UNKNOWN"; cases.append((a, False))
        a = self.attempt(); a["effect_class"] = "MUTATING"; cases.append((a, False))
        cases.append((self.attempt(), True))
        for attempt, frozen in cases:
            self.assertFalse(er.evaluate_replay(attempt, candidate_frozen=frozen)["eligible"])

    def test_powershell_capture_preflight_rejects_reserved_output_and_accepts_safe_wrapper(self):
        bad = '$output = & $File @Arguments 2>&1 | Out-String\n'
        result = er.powershell_capture_preflight(bad, Path.cwd())
        self.assertEqual("FAIL", result["status"])
        good = """$nativeText = & $File @Arguments 2>&1 | Out-String
$nativeExit = $LASTEXITCODE
$TimeoutSeconds = 60
if ($nativeText.Length -gt $MaxCapture) { $nativeText = $nativeText.Substring(0, $MaxCapture) }
$process.WaitForExit($TimeoutSeconds * 1000)
if (-not $process.HasExited) { $process.Kill(); $process.Dispose() }
$utf8 = [Text.UTF8Encoding]::new($false)
$canonical = $nativeText.TrimEnd() + "`n"
[IO.File]::WriteAllText($tmp, $canonical, $utf8)
Move-Item $tmp $receipt -Force
"""
        result = er.powershell_capture_preflight(good, Path.cwd())
        self.assertEqual("PASS", result["status"])

    def test_missing_invocation_identity_blocks_replay(self):
        attempt = self.attempt()
        attempt.pop("invocation_identity")
        decision = er.evaluate_replay(attempt)
        self.assertFalse(decision["eligible"])
        self.assertEqual("BBK-REPLAY-008", decision["code"])


if __name__ == "__main__":
    unittest.main()
