from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "codex_ds_lifecycle.py"


class CodexDeepSeekLifecycleTests(unittest.TestCase):
    def run_cli(self, home: Path, *args: str, check: bool = True) -> tuple[dict, subprocess.CompletedProcess[str]]:
        result = subprocess.run(
            [sys.executable, str(TOOL), *args, "--codex-home", str(home), "--json"],
            cwd=ROOT, text=True, capture_output=True,
        )
        if check:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout), result

    def test_keyless_explicit_role_target_lifecycle(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw) / "project-codex"
            installed, _ = self.run_cli(home, "install", "--role", "bbk_worker", "--target", "deepseek-v4-pro")
            self.assertEqual(installed["status"], "PASS")
            self.assertEqual(installed["credential_ref"], {"kind": "environment", "env_key": "DEEPSEEK_API_KEY", "value_persisted": False})
            self.assertTrue((home / "agents" / "bbk_worker.toml").is_file())
            updated, _ = self.run_cli(home, "update", "--role", "bbk_worker", "--target", "deepseek-v4-flash")
            self.assertEqual(updated["target"], "deepseek-v4-flash")
            current, _ = self.run_cli(home, "status")
            self.assertEqual(current["status"], "CURRENT")
            rolled, _ = self.run_cli(home, "rollback")
            self.assertEqual(rolled["target"], "deepseek-v4-pro")
            removed, _ = self.run_cli(home, "uninstall")
            self.assertEqual(removed["status"], "PASS")
            absent, _ = self.run_cli(home, "status")
            self.assertEqual(absent["status"], "ABSENT")

    def test_role_and_target_are_fail_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            for args, message in [
                (("install", "--target", "deepseek-v4-pro"), "explicit --role"),
                (("install", "--role", "bbk_worker", "--target", "other"), "unknown target"),
                (("install", "--role", "not_a_role", "--target", "deepseek-v4-pro"), "unknown role"),
            ]:
                result, proc = self.run_cli(home, *args, check=False)
                self.assertEqual(proc.returncode, 2)
                self.assertIn(message, result["error"])

    def test_absent_credential_and_provider_error_are_visible_without_fallback(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            previous = os.environ.pop("DEEPSEEK_API_KEY", None)
            try:
                installed, _ = self.run_cli(home, "install", "--role", "bbk_worker", "--target", "deepseek-v4-pro")
                self.assertEqual(installed["target"], "deepseek-v4-pro")
                absent, _ = self.run_cli(home, "status")
                self.assertEqual(absent["credential_state"], "ABSENT")
                self.assertEqual(absent["provider_state"], "CREDENTIAL_ABSENT")
                errored, _ = self.run_cli(home, "status", "--provider-error", "loopback unavailable")
                self.assertEqual(errored["provider_state"], "ERROR")
                self.assertEqual(errored["provider_error"], "loopback unavailable")
                self.assertEqual(errored["target"], "deepseek-v4-pro")
            finally:
                if previous is not None:
                    os.environ["DEEPSEEK_API_KEY"] = previous

    def test_direct_pro_and_flash_loopback_projections_are_distinct(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            for target, marker in (("deepseek-v4-pro", "deepseek-v4-pro"), ("deepseek-v4-flash", "deepseek-v4-flash")):
                home = base / target
                installed, _ = self.run_cli(home, "install", "--role", "bbk_worker", "--target", target)
                self.assertEqual(installed["target"], target)
                text = (home / "agents" / "bbk_worker.toml").read_text(encoding="utf-8")
                self.assertIn(marker, text)
                self.assertNotIn("DEEPSEEK_API_KEY=", text)


if __name__ == "__main__":
    unittest.main()
