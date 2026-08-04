from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BBK = ROOT / "tools" / "bbk.py"


class StructuredCliErrorTests(unittest.TestCase):
    def run_cli(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(BBK), *args],
            cwd=cwd or ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def assert_cli_error(self, result: subprocess.CompletedProcess[str], *, code: str, field: str) -> dict[str, object]:
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stderr, "")
        value = json.loads(result.stdout)
        self.assertEqual(value["schema"], "bbk.cli-error.v1")
        self.assertEqual(value["status"], "INVALID_ARGUMENT")
        self.assertEqual(value["code"], code)
        self.assertEqual(value["field"], field)
        self.assertIsInstance(value["valid_values"], list)
        self.assertTrue(value["example_command"])
        self.assertTrue(value["documentation_command"])
        self.assertTrue(value["smallest_next_action"])
        return value

    def test_invalid_choice_reports_field_received_values_and_example(self):
        result = self.run_cli("--json", "schema", "template", "--kind", "not-a-template", "--output", "out.json")
        value = self.assert_cli_error(result, code="INVALID_CHOICE", field="kind")
        self.assertEqual(value["received"], "not-a-template")
        self.assertIn("artifact-manifest", value["valid_values"])
        self.assertEqual(value["documentation_command"], "bbk schema template --help")
        self.assertIn("--kind", value["example_command"])
        self.assertIn("--output", value["example_command"])

    def test_missing_required_argument_is_json_not_argparse_usage_wall(self):
        result = self.run_cli("--json", "schema", "template", "--kind", "artifact-manifest")
        value = self.assert_cli_error(result, code="MISSING_REQUIRED_ARGUMENT", field="output")
        self.assertIsNone(value["received"])
        self.assertNotIn("usage:", result.stdout.lower())

    def test_unknown_command_reports_all_valid_commands(self):
        result = self.run_cli("--json", "definitely-not-a-command")
        value = self.assert_cli_error(result, code="INVALID_CHOICE", field="command")
        self.assertEqual(value["received"], "definitely-not-a-command")
        self.assertIn("artifact", value["valid_values"])
        self.assertIn("status", value["valid_values"])

    def test_command_level_capability_zone_error_preserves_valid_values(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            project.mkdir()
            initialized = self.run_cli("--json", "init", "--root", str(project), "--title", "CLI errors", "--no-examples")
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            result = self.run_cli(
                "--json", "handoff", "create",
                "--root", str(project),
                "--work-unit", "WU-CLI-1",
                "--disposition", "COMPLETE",
                "--summary", "fixture",
                "--next-action", "none",
                "--capability-zone", "unknown-zone=work",
            )
            value = self.assert_cli_error(result, code="INVALID_ARGUMENT", field="capability_zone")
            self.assertEqual(value["received"], "unknown-zone")
            self.assertEqual(
                value["valid_values"],
                ["disposable-candidate-root", "protected-worktree", "sealed-evidence"],
            )
            self.assertIn("diagnostic", value)

    def test_human_error_is_concise_and_has_example_and_help(self):
        result = self.run_cli("schema", "template", "--kind", "not-a-template", "--output", "out.json")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("bbk: error:", result.stderr)
        self.assertIn("example:", result.stderr)
        self.assertIn("help:", result.stderr)
        self.assertNotIn("usage:", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
