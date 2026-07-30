from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import source_sanity  # noqa: E402


class Alpha112WindowsUtf8Tests(unittest.TestCase):
    def test_current_version_and_utf8_canonical_input_are_read_explicitly(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(version, "0.1.0-alpha.11.7")
        method_content = json.loads(
            (ROOT / "spec" / "method-content.json").read_text(encoding="utf-8")
        )
        self.assertEqual(method_content["version"], version)

    def test_package_python_has_no_implicit_path_text_encoding(self):
        report = source_sanity.validate()
        self.assertEqual(report["implicit_text_encoding_calls"], 0, report["errors"])

    def test_source_sanity_detects_implicit_path_text_calls(self):
        with tempfile.TemporaryDirectory() as temp:
            sample = Path(temp) / "implicit.py"
            sample.write_text(
                "from pathlib import Path\n"
                "value = Path('input.txt').read_text()\n"
                "Path('output.txt').write_text(value)\n",
                encoding="utf-8",
            )
            violations = source_sanity.text_encoding_violations(sample)
        self.assertEqual(len(violations), 2)
        self.assertTrue(any("read_text() omits encoding" in item for item in violations))
        self.assertTrue(any("write_text() omits encoding" in item for item in violations))

    def test_installer_regressions_override_ambient_bbk_home(self):
        with tempfile.TemporaryDirectory() as temp:
            decoy = Path(temp) / "ambient-bbk-home"
            env = os.environ.copy()
            env.update({
                "BBK_HOME": str(decoy),
                "PYTHONDONTWRITEBYTECODE": "1",
            })
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "unittest",
                    "-v",
                    "test_alpha6_congruence.Alpha6CongruenceTests.test_installer_refuses_divergence_and_backs_up_force_replacement",
                    "test_bbk.BbkTests.test_installed_omp_extension_executes_copied_cli",
                    "test_bbk.BbkTests.test_user_install_all_targets_and_uninstall",
                ],
                cwd=ROOT / "tests",
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertFalse(decoy.exists(), result.stdout)


if __name__ == "__main__":
    unittest.main()
