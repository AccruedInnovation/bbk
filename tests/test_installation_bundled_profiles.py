"""Bundled profile installer regressions."""
from __future__ import annotations
import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
import source_sanity
from tests._path_support import assert_no_path_within
m6_ROOT = ROOT

class Alpha112WindowsUtf8Tests(unittest.TestCase):

    def test_current_version_and_utf8_canonical_input_are_read_explicitly(self):
        version = (m6_ROOT / 'VERSION').read_text(encoding='utf-8').strip()
        self.assertEqual(version, '0.1.0-alpha.17.0.2.1')
        method_content = json.loads((m6_ROOT / 'spec' / 'method-content.json').read_text(encoding='utf-8'))
        self.assertEqual(method_content['version'], version)


    def test_source_sanity_detects_implicit_path_text_calls(self):
        with tempfile.TemporaryDirectory() as temp:
            sample = Path(temp) / 'implicit.py'
            sample.write_text("from pathlib import Path\nvalue = Path('input.txt').read_text()\nPath('output.txt').write_text(value)\n", encoding='utf-8')
            violations = source_sanity.text_encoding_violations(sample)
        self.assertEqual(len(violations), 2)
        self.assertTrue(any(('read_text() omits encoding' in item for item in violations)))
        self.assertTrue(any(('write_text() omits encoding' in item for item in violations)))

    def test_installer_regressions_override_ambient_bbk_home(self):
        # Prove the environment-isolation invariant directly. The old form
        # reran three broad integration tests that this same full suite already
        # executes, multiplying install and Node work.
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            ambient = base / 'ambient-home'
            explicit = base / 'explicit-home'
            explicit.mkdir()
            env = os.environ.copy()
            env.update({
                'BBK_HOME': str(explicit),
                'HOME': str(explicit),
                'BBK_INSTALL_ROOT': str(base / 'data'),
                'BBK_BIN_DIR': str(base / 'bin'),
                'PYTHONDONTWRITEBYTECODE': '1',
            })
            # Keep an unrelated ambient marker and verify the operation stays
            # within the explicit isolated root.
            ambient.mkdir()
            marker = ambient / 'do-not-touch.txt'
            marker.write_text('preserve', encoding='utf-8')
            result = subprocess.run([
                sys.executable, str(m6_ROOT / 'tools' / 'install.py'), '--json',
                'install', '--scope', 'user', '--codex',
                '--no-language-profiles', '--dry-run',
            ], cwd=m6_ROOT, env=env, stdin=subprocess.DEVNULL,
               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
               encoding='utf-8', errors='replace', timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout)
            payload = json.loads(result.stdout)
            self.assertTrue(marker.is_file())
            self.assertTrue(payload['files'])
            assert_no_path_within(self, [item['path'] for item in payload['files']], ambient)

