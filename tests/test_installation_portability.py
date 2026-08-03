"""Consolidated BBK regression tests grouped by responsibility.

Historical release-specific modules were merged to keep the public repository
readable while retaining their behavioral coverage.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Historical source: test_alpha9_1_portability.py
# ---------------------------------------------------------------------------
import importlib.util
import io
import json
import unittest
from pathlib import Path, PureWindowsPath
m1_ROOT = Path(__file__).resolve().parents[1]

def m1_load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, m1_ROOT / relative_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'cannot load {relative_path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
m1_generate_agents = m1_load_module('bbk_generate_agents', 'tools/generate_agents.py')
m1_run_tests = m1_load_module('bbk_run_tests', 'tools/run_tests.py')

class Alpha91PortabilityTests(unittest.TestCase):

    def test_projection_manifest_path_serialization_is_host_independent(self):
        root = PureWindowsPath('D:\\Projects\\BBK\\bbk-0.1.0-alpha.9.1')
        path = root / 'projections' / 'codex' / 'agents' / 'bbk_architect.toml'
        source = root / 'spec' / 'roles.json'
        self.assertEqual(m1_generate_agents.portable_relative_path(path, root), 'projections/codex/agents/bbk_architect.toml')
        self.assertEqual(m1_generate_agents.portable_relative_path(source, root), 'spec/roles.json')

    def test_packaged_projection_manifest_contains_only_portable_paths(self):
        manifest = json.loads((m1_ROOT / 'projections' / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['source'], 'spec/roles.json')
        self.assertTrue(manifest['files'])
        self.assertTrue(all(('\\' not in path for path in manifest['files'])))

    def test_stdout_test_runner_preserves_success_exit_contract(self):

        class PassingTest(unittest.TestCase):

            def runTest(self):
                self.assertTrue(True)
        stream = io.StringIO()
        result = m1_run_tests.run_suite(unittest.TestSuite([PassingTest()]), stream=stream, verbosity=2)
        self.assertTrue(result.wasSuccessful())
        self.assertIn('runTest', stream.getvalue())
        self.assertIn('OK', stream.getvalue())

    def test_current_verification_docs_use_the_stdout_runner(self):
        for relative_path in ('README.md', 'docs/INSTALL.md', 'docs/DEVELOPMENT.md'):
            text = (m1_ROOT / relative_path).read_text(encoding='utf-8')
            self.assertIn('python tools/run_tests.py --profile', text, relative_path)
            self.assertIn('-v', text, relative_path)

# ---------------------------------------------------------------------------
# Historical source: test_alpha9_2_windows_installer.py
# ---------------------------------------------------------------------------
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path, PureWindowsPath
from unittest import mock
m2_ROOT = Path(__file__).resolve().parents[1]

def m2_load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, m2_ROOT / relative_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'cannot load {relative_path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
m2_install = m2_load_module('bbk_install_alpha92', 'tools/install.py')
m2_bbk = m2_load_module('bbk_cli_alpha92', 'tools/bbk.py')

class Alpha92WindowsInstallerTests(unittest.TestCase):

    def test_home_override_prevents_windows_verification_from_using_real_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            isolated = Path(temp) / 'isolated-home'
            actual = Path(temp) / 'actual-home'
            with mock.patch.dict(os.environ, {'HOME': str(isolated)}, clear=False):
                os.environ.pop('BBK_HOME', None)
                with mock.patch.object(m2_install.Path, 'home', return_value=actual):
                    assert_same_path(self, m2_install.user_home(), isolated)

    def test_bbk_home_has_explicit_precedence_over_home(self):
        with tempfile.TemporaryDirectory() as temp:
            explicit = Path(temp) / 'bbk-home'
            conventional = Path(temp) / 'home'
            with mock.patch.dict(os.environ, {'BBK_HOME': str(explicit), 'HOME': str(conventional)}, clear=False):
                assert_same_path(self, m2_install.user_home(), explicit)

    def test_windows_backup_layout_cannot_escape_backup_root(self):
        destination = PureWindowsPath('C:\\Users\\operator\\.codex\\agents\\bbk_worker.toml')
        namespace, parts = m2_install.backup_layout(destination)
        self.assertEqual(namespace, 'C')
        self.assertEqual(parts, ('Users', 'operator', '.codex', 'agents', 'bbk_worker.toml'))
        self.assertNotIn(destination.anchor, parts)
        unc = PureWindowsPath('\\\\server\\share\\operator\\.omp\\agent\\extensions\\bbk\\index.js')
        unc_namespace, unc_parts = m2_install.backup_layout(unc)
        self.assertEqual(unc_namespace, 'server_share')
        self.assertEqual(unc_parts[:2], ('operator', '.omp'))

    def test_json_path_fields_are_host_neutral(self):
        path = PureWindowsPath('D:\\Projects\\BBK\\.omp\\extensions\\bbk\\bbk.py')
        self.assertEqual(m2_install.json_path(path), 'D:/Projects/BBK/.omp/extensions/bbk/bbk.py')
        root = PureWindowsPath('D:\\Projects\\BBK')
        relative = root / '.bbk' / 'project.md'
        self.assertEqual(m2_bbk.portable_relative_path(relative, root), '.bbk/project.md')

    def test_current_installer_uses_override_aware_home_for_all_user_targets(self):
        source = (m2_ROOT / 'tools' / 'install.py').read_text(encoding='utf-8')
        self.assertEqual(source.count('Path.home()'), 2)
        self.assertIn('home = user_home()', source)
        for fragment in ('home / ".codex"', 'home / ".omp"', 'home / ".claude"', 'home / ".agents"'):
            self.assertIn(fragment, source)

# ---------------------------------------------------------------------------
# Historical source: test_alpha9_3_verification_reporting.py
# ---------------------------------------------------------------------------
import importlib.util
import io
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock
m3_ROOT = Path(__file__).resolve().parents[1]

def m3_load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, m3_ROOT / relative_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'cannot load {relative_path}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
m3_run_tests = m3_load_module('bbk_alpha93_run_tests', 'tools/run_tests.py')

class Alpha93VerificationReportingTests(unittest.TestCase):

    def test_problem_parser_captures_failure_and_error_causes(self):
        output = textwrap.dedent('            test_bad (sample.Case.test_bad) ... FAIL\n            test_boom (sample.Case.test_boom) ... ERROR\n\n            ======================================================================\n            ERROR: test_boom (sample.Case.test_boom)\n            ----------------------------------------------------------------------\n            Traceback (most recent call last):\n              File "sample.py", line 8, in test_boom\n                raise RuntimeError("boom")\n            RuntimeError: boom\n\n            ======================================================================\n            FAIL: test_bad (sample.Case.test_bad)\n            ----------------------------------------------------------------------\n            Traceback (most recent call last):\n              File "sample.py", line 5, in test_bad\n                self.assertEqual(1, 2)\n            AssertionError: 1 != 2\n\n            ----------------------------------------------------------------------\n            Ran 2 tests in 0.001s\n\n            FAILED (failures=1, errors=1)\n            ')
        issues = m3_run_tests.parse_issues(output)
        self.assertEqual(m3_run_tests.parse_test_count(output), 2)
        self.assertEqual([issue.kind for issue in issues], ['ERROR', 'FAIL'])
        self.assertEqual(issues[0].cause, 'RuntimeError: boom')
        self.assertEqual(issues[1].cause, 'AssertionError: 1 != 2')

    def test_final_summary_lists_every_problem_and_exit_code(self):
        result = m3_run_tests.SuiteResult(name='test_sample.py', returncode=1, output='', tests_run=2, issues=(m3_run_tests.TestIssue('ERROR', 'test_boom (sample.Case.test_boom)', 'RuntimeError: boom'), m3_run_tests.TestIssue('FAIL', 'test_bad (sample.Case.test_bad)', 'AssertionError: 1 != 2')))
        stream = io.StringIO()
        m3_run_tests.print_final_summary([result], expected_suites=1, exit_code=1, stream=stream)
        summary = stream.getvalue()
        self.assertIn('BBK FINAL TEST SUMMARY', summary)
        self.assertIn('Result: FAILED', summary)
        self.assertIn('Errors: 1', summary)
        self.assertIn('Failed suites:', summary)
        self.assertIn('- test_sample.py: exit code 1', summary)
        self.assertIn('Failures: 1', summary)
        self.assertIn('[ERROR] test_boom', summary)
        self.assertIn('Cause: RuntimeError: boom', summary)
        self.assertIn('[FAIL] test_bad', summary)
        self.assertIn('Cause: AssertionError: 1 != 2', summary)
        self.assertIn('Exit code: 1', summary)

    def test_runner_end_to_end_repeats_failure_and_error_at_the_end(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tests = root / 'tests'
            tests.mkdir()
            test_file = tests / 'test_deliberate.py'
            test_file.write_text(textwrap.dedent('                    import unittest\n\n                    class DeliberateTests(unittest.TestCase):\n                        def test_a_failure(self):\n                            self.assertEqual(1, 2)\n\n                        def test_b_error(self):\n                            raise RuntimeError("deliberate boom")\n                    '), encoding='utf-8')
            stream = io.StringIO()
            with mock.patch.object(m3_run_tests, 'ROOT', root), mock.patch.object(m3_run_tests, 'TESTS', tests):
                code = m3_run_tests.run_test_files([test_file], verbose=True, stream=stream)
            output = stream.getvalue()
            summary_position = output.rfind('BBK FINAL TEST SUMMARY')
            self.assertEqual(code, 1)
            self.assertGreater(summary_position, 0)
            final_summary = output[summary_position:]
            self.assertIn('Result: FAILED', final_summary)
            self.assertIn('- test_deliberate.py: exit code 1', final_summary)
            self.assertIn('test_a_failure', final_summary)
            self.assertIn('Cause: AssertionError: 1 != 2', final_summary)
            self.assertIn('test_b_error', final_summary)
            self.assertIn('Cause: RuntimeError: deliberate boom', final_summary)
            self.assertIn('Exit code: 1', final_summary)

    def test_runner_end_to_end_prints_clean_final_summary(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tests = root / 'tests'
            tests.mkdir()
            test_file = tests / 'test_passing.py'
            test_file.write_text(textwrap.dedent('                    import unittest\n\n                    class PassingTests(unittest.TestCase):\n                        def test_passes(self):\n                            self.assertTrue(True)\n                    '), encoding='utf-8')
            stream = io.StringIO()
            with mock.patch.object(m3_run_tests, 'ROOT', root), mock.patch.object(m3_run_tests, 'TESTS', tests):
                code = m3_run_tests.run_test_files([test_file], verbose=True, stream=stream)
            output = stream.getvalue()
            final_summary = output[output.rfind('BBK FINAL TEST SUMMARY'):]
            self.assertEqual(code, 0)
            self.assertIn('Result: PASS', final_summary)
            self.assertIn('No failures or errors.', final_summary)
            self.assertIn('Exit code: 0', final_summary)

    def test_installer_replacement_regression_uses_filesystem_identity(self):
        source = (m3_ROOT / 'tests' / 'test_core_contracts.py').read_text(encoding='utf-8')
        self.assertIn('.samefile(target)', source)
        self.assertNotIn('item["path"] == target.as_posix()', source)

# ---------------------------------------------------------------------------
# Historical source: test_alpha10_1_entry_setup.py
# ---------------------------------------------------------------------------
import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import types
import unittest
import zipfile
from pathlib import Path
from unittest import mock
m4_ROOT = Path(__file__).resolve().parents[1]
m4_TOOLS = m4_ROOT / 'tools'
if str(m4_TOOLS) not in sys.path:
    sys.path.insert(0, str(m4_TOOLS))
import create_method_content
import install as install_tool
import install_profiles
import profile_install
import profile_registry
import run_tests
import setup as setup_tool
import verify_all
from tests._cli_support import run_cli as test_run_cli
from tests._path_support import (
    assert_different_path,
    assert_labeled_path,
    assert_no_path_within,
    assert_same_path,
    assert_same_path_sequence,
    create_symlink_or_skip,
    find_unguarded_symlink_creations,
    find_unsafe_path_assertions,
    path_identity_key,
)
from tests import _test_profiles as test_profiles

def m4__canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')

def m4__write_profile_package(base: Path, *, profile_id: str='sample') -> Path:
    """Create one small, fully manifested installable profile package."""
    version = '0.1.0-alpha.3'
    package_name = f'bbk-profile-{profile_id}'
    root = base / f'{package_name}-{version}'
    (root / 'tools').mkdir(parents=True)
    (root / 'skills' / profile_id).mkdir(parents=True)
    (root / 'omp' / 'extension').mkdir(parents=True)
    source_profile = json.loads((m4_ROOT / 'fixtures' / 'profiles' / 'alpha8' / 'PROFILE.json').read_text(encoding='utf-8'))
    source_profile.update({'id': profile_id, 'name': f'Sample {profile_id} profile', 'package': package_name, 'version': version, 'maturity': 'qualified-fixture', 'requires': {'bbk_minimum': '0.1.0-alpha.8', 'python_minimum': '3.10'}, 'installation': {'cli': 'tools/profile.py', 'skill_root': 'skills', 'omp_extension': 'omp/extension'}, 'skills': [{'id': profile_id, 'kind': 'router', 'path': f'skills/{profile_id}/SKILL.md'}]})
    (root / 'PROFILE.json').write_text(json.dumps(source_profile, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    (root / 'VERSION').write_text(version + '\n', encoding='utf-8')
    cli = root / 'tools' / 'profile.py'
    cli.write_text("#!/usr/bin/env python3\nimport json\nprint(json.dumps({'status':'PASS'}))\n", encoding='utf-8')
    cli.chmod(493)
    (root / 'skills' / profile_id / 'SKILL.md').write_text(f'---\nname: {profile_id}\ndescription: Sample profile skill.\n---\n\n# Sample profile\n', encoding='utf-8')
    (root / 'omp' / 'extension' / 'index.js').write_text("export default function sampleProfile(pi) { pi.setLabel?.('sample-profile'); }\n", encoding='utf-8')
    (root / 'omp' / 'extension' / 'package.json').write_text(json.dumps({'name': package_name, 'version': version, 'type': 'module'}, indent=2) + '\n', encoding='utf-8')
    (root / 'omp' / 'extension' / 'README.md').write_text('# Sample profile extension\n', encoding='utf-8')
    records = []
    for path in sorted((candidate for candidate in root.rglob('*') if candidate.is_file()), key=lambda value: value.relative_to(root).as_posix()):
        data = path.read_bytes()
        records.append({'path': path.relative_to(root).as_posix(), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'executable': bool(path.stat().st_mode & 73)})
    payload = {'schema': 'bbk.profile-package-root.v1', 'name': package_name, 'version': version, 'files': records}
    manifest = {'schema': 'bbk.profile-package-manifest.v1', 'root_schema': 'bbk.profile-package-root.v1', 'name': package_name, 'profile_id': profile_id, 'version': version, 'file_count': len(records), 'files': records, 'root_sha256': hashlib.sha256(m4__canonical(payload)).hexdigest()}
    (root / 'PACKAGE-MANIFEST.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return root

def m4__write_profile_bundle(base: Path, *, profile_id: str='sample') -> Path:
    package_root = m4__write_profile_package(base / 'source', profile_id=profile_id)
    bundle_root = base / 'bundle-root'
    packages = bundle_root / 'packages'
    packages.mkdir(parents=True)
    package_zip = packages / f'{package_root.name}.zip'
    with zipfile.ZipFile(package_zip, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((candidate for candidate in package_root.rglob('*') if candidate.is_file()), key=lambda value: value.relative_to(package_root.parent).as_posix()):
            archive.write(path, path.relative_to(package_root.parent).as_posix())
    record = {'path': package_zip.relative_to(bundle_root).as_posix(), 'bytes': package_zip.stat().st_size, 'sha256': hashlib.sha256(package_zip.read_bytes()).hexdigest()}
    release = {'schema': 'bbk.language-profiles-release-bundle-manifest.v1', 'status': 'PASS', 'fileCount': 1, 'files': [record]}
    (bundle_root / 'RELEASE-MANIFEST.json').write_text(json.dumps(release, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    bundle_zip = base / 'profiles.zip'
    with zipfile.ZipFile(bundle_zip, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((candidate for candidate in bundle_root.rglob('*') if candidate.is_file()), key=lambda value: value.relative_to(bundle_root.parent).as_posix()):
            archive.write(path, path.relative_to(bundle_root.parent).as_posix())
    return bundle_zip

class Alpha101EntrySetupTests(unittest.TestCase):

    def test_version_and_canonical_inputs_agree(self):
        version = (m4_ROOT / 'VERSION').read_text(encoding='utf-8').strip()
        self.assertEqual(version, '0.1.0-alpha.15')
        self.assertEqual(json.loads((m4_ROOT / 'spec' / 'roles.json').read_text(encoding='utf-8'))['package_version'], version)
        self.assertEqual(json.loads((m4_ROOT / 'spec' / 'model-routing.json').read_text(encoding='utf-8'))['package_version'], version)
        self.assertEqual(json.loads((m4_ROOT / 'spec' / 'method-content.json').read_text(encoding='utf-8'))['version'], version)
        self.assertEqual(json.loads((m4_ROOT / 'omp' / 'extension' / 'package.json').read_text(encoding='utf-8'))['version'], version)

    def test_installed_profile_source_skill_is_a_generated_placeholder(self):
        version = (m4_ROOT / 'VERSION').read_text(encoding='utf-8').strip()
        rendered = (m4_ROOT / 'shared' / 'skills' / 'bbk-installed-profiles' / 'SKILL.md').read_text(encoding='utf-8')
        self.assertEqual(rendered, profile_registry.source_placeholder_skill(bbk_version=version))
        self.assertIn('package-source placeholder', rendered)
        self.assertIn('No language or domain profile is managed', rendered)

    def test_baseline_skill_is_the_harness_root_controller_without_recursive_rerouting(self):
        method = json.loads((m4_ROOT / 'spec' / 'method-content.json').read_text(encoding='utf-8'))
        rendered = (m4_ROOT / 'shared' / 'skills' / 'bbk' / 'SKILL.md').read_text(encoding='utf-8')
        expected = create_method_content.expected(allow_staged=True)[
            m4_ROOT / 'shared' / 'skills' / 'bbk' / 'SKILL.md'
        ].decode('utf-8')
        self.assertEqual(expected, rendered)
        self.assertNotIn('{{bbk-module:', rendered)
        self.assertEqual(rendered.count('# BBK harness-root controller'), 1)
        self.assertEqual(rendered.count('## Select one canonical root'), 1)
        for value in ('visible top-level harness session', 'bbk_root_wayfinder', 'bbk_root_orchestrator', 'bbk_reviewer', 'bbk_validator_orchestrator', 'Invoke the named canonical agent', 'must not perform, abbreviate, or imitate'):
            self.assertIn(value, rendered)
        self.assertIn('material baseline defect', rendered)
        roles = json.loads((m4_ROOT / 'spec' / 'roles.json').read_text(encoding='utf-8'))
        self.assertTrue(all('bbk' not in role['mandatory_skills'] for role in roles['roles']))
        self.assertFalse(roles['interaction_topology']['canonical_roles_user_facing'])

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for OMP extension behavior')
    def test_omp_bbk_command_enters_persistent_mode_and_keeps_status_command(self):
        with tempfile.TemporaryDirectory() as temp:
            script = Path(temp) / 'omp-entrypoint.mjs'
            script.write_text(textwrap.dedent(f'''\
                const chain = () => ({{ optional() {{ return this; }} }});
                const z = {{ object: value => value, string: chain, boolean: chain,
                  enum: values => chain(), array: value => chain() }};
                const tools = [], commands = new Map(), messages = [], handlers = new Map(), entries = [], statuses = [];
                const branch = [];
                const pi = {{ zod: {{ z }}, setLabel() {{}},
                  registerTool(value) {{ tools.push(value); }},
                  registerCommand(name, value) {{ commands.set(name, value); }},
                  on(name, value) {{ if (!handlers.has(name)) handlers.set(name, []); handlers.get(name).push(value); }},
                  appendEntry(customType, data) {{ entries.push([customType, data]); branch.push({{type:'custom', customType, data}}); }},
                  async sendUserMessage(value, options) {{ messages.push([value, options || null]); }}
                }};
                const ctx = {{
                  cwd: {json.dumps(str(m4_ROOT))}, isIdle() {{ return true; }},
                  sessionManager: {{ getBranch() {{ return branch; }} }},
                  ui: {{ notify() {{}}, setStatus(key, value) {{ statuses.push([key, value ?? null]); }} }}
                }};
                const mod = await import({json.dumps((m4_ROOT / 'omp' / 'extension' / 'index.js').as_uri())});
                mod.default(pi);
                if (commands.size !== 45) throw new Error(`commands=${{commands.size}}`);
                if (!commands.has('bbk') || !commands.has('bbk:status') || !commands.has('bbk:exit')) throw new Error('missing BBK commands');
                const entered = await commands.get('bbk').handler('', ctx);
                if (entered !== undefined) throw new Error(`unexpected command payload: ${{JSON.stringify(entered)}}`);
                if (messages.length !== 0) throw new Error(`no-argument /bbk started a model turn`);
                if (entries.length !== 1 || entries[0][1].enabled !== true) throw new Error('mode was not persisted');
                const before = handlers.get('before_agent_start')?.[0];
                if (!before) throw new Error('missing before_agent_start');
                const replacement = await before({{systemPrompt:[
                  'OMP DEFAULT NEVER outsource the top-level plan',
                  'C:/Users/Tombstone/.codex/AGENTS.md spawn_agent one-liner solutions'
                ]}}, ctx);
                const joined = replacement.systemPrompt.join(String.fromCharCode(10));
                for (const expected of ['<bbk-controller-system ', 'bbk_root_wayfinder', 'bbk_root_orchestrator',
                  'bbk_reviewer', 'bbk_validator_orchestrator', '/bbk:exit', '<bbk-inlined-skill name="bbk"',
                  '<bbk-inlined-skill name="bbk-context-routing"', '`task`', '`hub`/IRC', 'Main']) {{
                  if (!joined.includes(expected)) throw new Error(`missing ${{expected}}`);
                }}
                for (const excluded of ['OMP DEFAULT', '.codex/AGENTS.md', 'one-liner solutions']) {{
                  if (joined.includes(excluded)) throw new Error(`retained ${{excluded}}`);
                }}
                if (entries.length !== 2 || entries[1][0] !== 'bbk-effective-prompt-receipt' || entries[1][1].status !== 'REPLACED') throw new Error('effective prompt receipt missing');
                await commands.get('bbk').handler('Implement the accepted baseline', ctx);
                if (messages.length !== 1 || messages[0][0] !== 'Implement the accepted baseline') throw new Error('request was not forwarded verbatim');
                if (messages[0][0].includes('bbk_root_wayfinder')) throw new Error('mode prompt leaked into user message');
                console.log(JSON.stringify({{commands: commands.size, messages: messages.length, entries: entries.length, replacementLength: joined.length}}));
            '''), encoding='utf-8')
            result = subprocess.run([shutil.which('node') or 'node', script], cwd=m4_ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', check=False, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            value = json.loads(result.stdout)
            self.assertEqual(value['commands'], 45)
            self.assertEqual(value['messages'], 1)
            self.assertEqual(value['entries'], 2)

    def test_run_tests_all_delegates_to_the_ordered_verification_pipeline(self):
        calls: list[dict[str, object]] = []
        fake = types.ModuleType('verify_all')

        def fake_run_all(**kwargs: object) -> int:
            calls.append(kwargs)
            return 7
        fake.run_all = fake_run_all
        with mock.patch.dict(sys.modules, {'verify_all': fake}):
            result = run_tests.main(['--all', '--failfast', '--require-node'])
        self.assertEqual(result, 7)
        self.assertEqual(calls, [{
            'failfast': True,
            'require_node': True,
            'skip_package_manifest': False,
            'jobs': 0,
            'test_mode': 'auto',
            'verbose_tests': False,
            'profile': 'standard',
            'timing_report': None,
            'no_timing_report': False,
        }])
        files = run_tests.matching_test_files('test*.py')
        self.assertEqual(files, sorted(files))

    def test_verification_pipeline_has_trust_gate_generators_tests_and_post_check(self):
        with mock.patch.object(verify_all.shutil, 'which', return_value='node'):
            steps = verify_all.verification_steps(require_node=True)
        names = [step.name for step in steps]
        self.assertEqual(names[0], 'Package manifest integrity (pre-execution trust gate)')
        self.assertTrue(steps[0].trust_gate)
        self.assertIn('Method-content projection drift', names)
        self.assertIn('Agent projection drift', names)
        self.assertIn('Python compilation and JSON parsing', names)
        # The Alpha.8 validator remains a supported standalone maintainer tool,
        # but its complete typed-dispatch corpus is already exercised by
        # Alpha8ProfileDispatchTests. Do not execute the same expensive profile
        # subprocess matrix twice during full qualification.
        self.assertNotIn('Alpha.8 typed-profile fixtures', names)
        self.assertIn('Standard unittest suite', names)
        self.assertIn('OMP extension JavaScript syntax', names)
        self.assertEqual(names[-1], 'Package manifest integrity (post-test mutation check)')
        unittest_step = next(step for step in steps if step.name == 'Standard unittest suite')
        self.assertIn('-q', unittest_step.command)
        self.assertNotIn('-v', unittest_step.command)
        verbose_steps = verify_all.verification_steps(require_node=True, verbose_tests=True)
        verbose_unittest_step = next(step for step in verbose_steps if step.name == 'Standard unittest suite')
        self.assertIn('-v', verbose_unittest_step.command)
        self.assertNotIn('-q', verbose_unittest_step.command)
        self.assertIn('--jobs', unittest_step.command)
        self.assertIn('--mode', unittest_step.command)
        self.assertIn('auto', unittest_step.command)
        self.assertEqual(
            unittest_step.command[unittest_step.command.index('--profile') + 1],
            'standard',
        )
        release_steps = verify_all.verification_steps(profile='release', require_node=True)
        release_unittest = next(
            step for step in release_steps if step.name == 'Complete release unittest suite'
        )
        self.assertEqual(
            release_unittest.command[release_unittest.command.index('--profile') + 1],
            'release',
        )
        fast_steps = verify_all.verification_steps(profile='fast', require_node=True)
        fast_names = [step.name for step in fast_steps]
        self.assertIn('Fast contract unittest suite', fast_names)
        self.assertNotIn('Alpha.7 semantic fixtures', fast_names)
        pooled_step = next(
            step for step in verify_all.verification_steps(require_node=True, test_mode='pooled')
            if step.name == 'Standard unittest suite'
        )
        self.assertEqual(
            pooled_step.command[pooled_step.command.index('--mode') + 1],
            'pooled',
        )

    def test_safe_verifier_checks_run_in_process_and_restore_process_state(self):
        steps = verify_all.verification_steps(
            profile='standard', require_node=True, skip_package_manifest=False,
        )
        in_process_names = {step.name for step in steps if step.in_process}
        self.assertEqual(
            in_process_names,
            {
                'Method-content projection drift',
                'Role-specification projection drift',
                'Model-routing policy',
                'Agent projection drift',
                'Python compilation and JSON parsing',
                'Alpha.7 semantic fixtures',
            },
        )
        self.assertFalse(steps[0].in_process)
        self.assertTrue(steps[0].trust_gate)
        self.assertFalse(steps[-1].in_process)
        self.assertFalse(
            next(step for step in steps if step.name == 'Standard unittest suite').in_process
        )

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            tools = root / 'tools'
            tools.mkdir()
            (root / 'nested').mkdir()
            script = tools / 'probe.py'
            script.write_text(
                textwrap.dedent(
                    """
                    import os
                    import sys
                    from pathlib import Path

                    def main(argv):
                        print('in-process probe')
                        os.environ['BBK_VERIFY_PROBE'] = 'mutated'
                        sys.argv.append('mutated')
                        sys.path.insert(0, 'mutated')
                        os.chdir(Path(__file__).resolve().parents[1] / 'nested')
                        return 0 if argv == ['--check'] else 3
                    """
                ),
                encoding='utf-8',
            )
            before_cwd = Path.cwd()
            before_argv = list(sys.argv)
            before_path = list(sys.path)
            before_environment = os.environ.copy()
            before_modules = set(sys.modules)
            output = io.StringIO()
            spec = verify_all.CheckSpec(
                'Probe',
                (sys.executable, 'tools/probe.py', '--check'),
                cwd=root,
                in_process=True,
            )
            with mock.patch.object(verify_all, 'ROOT', root):
                result = verify_all.execute_step(spec, stream=output)
            self.assertTrue(result.passed, result.output)
            self.assertEqual(result.execution, 'in-process')
            self.assertIn('in-process probe', output.getvalue())
            assert_same_path(self, Path.cwd(), before_cwd)
            self.assertEqual(sys.argv, before_argv)
            self.assertEqual(sys.path, before_path)
            self.assertEqual(os.environ, before_environment)
            self.assertFalse(
                any(
                    name.startswith('_bbk_verify_probe_')
                    for name in set(sys.modules) - before_modules
                )
            )

    def test_profile_selection_is_total_and_standard_keeps_product_tests(self):
        with mock.patch.dict(
            os.environ,
            {'BBK_TEST_PROFILE': 'release', 'BBK_EXTERNAL_SCHEMA': '1'},
            clear=False,
        ):
            # Use a fresh loader: the process-wide default loader may retain
            # outer-discovery state while this release-only inventory test runs.
            suite = unittest.TestLoader().discover(
                str(m4_ROOT / 'tests'),
                pattern='test*.py',
            )
        ids = {
            test_profiles.normalize_test_id(test.id())
            for test in test_profiles.iter_tests(suite)
        }
        self.assertTrue(test_profiles.RELEASE_ONLY <= ids)
        self.assertGreater(len(ids), len(test_profiles.RELEASE_ONLY))
        standard = {
            test_id for test_id in ids
            if test_profiles.selected(test_id, 'standard')
        }
        release = {
            test_id for test_id in ids
            if test_profiles.selected(test_id, 'release')
        }
        fast = {
            test_id for test_id in ids
            if test_profiles.selected(test_id, 'fast')
        }
        self.assertEqual(release, ids)
        self.assertEqual(ids - standard, set(test_profiles.RELEASE_ONLY))
        self.assertTrue(fast < standard)
        self.assertEqual(
            {test_id.split('.', 1)[0] for test_id in fast},
            set(test_profiles.FAST_MODULES),
        )
        # Product-facing schema command behavior remains standard; only the
        # optional whole-package external-engine repetitions are release-only.
        self.assertIn(
            'test_system.Alpha118WayfindingExecutionTests.'
            'test_schema_validator_is_discoverable_and_uses_draft_2020_12',
            standard,
        )

    def test_runner_writes_package_external_timing_report_and_restores_profile_environment(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            tests = root / 'tests'
            tests.mkdir()
            (root / 'VERSION').write_text('0.1.0-test\n', encoding='utf-8')
            (tests / 'test_smoke.py').write_text(
                textwrap.dedent(
                    """
                    import unittest

                    class SmokeTests(unittest.TestCase):
                        def test_passes(self):
                            self.assertTrue(True)
                    """
                ),
                encoding='utf-8',
            )
            report_path = root.parent / f'{root.name}-timing.json'
            cache_path = root.parent / f'{root.name}-durations.json'
            try:
                with mock.patch.object(run_tests, 'ROOT', root), mock.patch.object(
                    run_tests, 'TESTS', tests
                ), mock.patch.object(
                    run_tests, 'DURATION_SEED_PATH', tests / 'missing-durations.json'
                ), mock.patch.object(
                    run_tests, 'duration_cache_path', return_value=cache_path
                ), mock.patch.dict(
                    os.environ,
                    {
                        'BBK_TEST_PROFILE': 'prior-profile',
                        'BBK_EXTERNAL_SCHEMA': 'prior-schema',
                    },
                    clear=False,
                ):
                    code = run_tests.main([
                        '-q',
                        '--profile', 'standard',
                        '--mode', 'batch',
                        '--timing-report', str(report_path),
                        '--heartbeat-seconds', '0',
                    ])
                    self.assertEqual(os.environ['BBK_TEST_PROFILE'], 'prior-profile')
                    self.assertEqual(os.environ['BBK_EXTERNAL_SCHEMA'], 'prior-schema')
                self.assertEqual(code, 0)
                report = json.loads(report_path.read_text(encoding='utf-8'))
                self.assertEqual(report['schema'], 'bbk.test-run.v1')
                self.assertEqual(report['profile'], 'standard')
                self.assertEqual(report['status'], 'PASS')
                self.assertEqual(report['tests_reported'], 1)
                self.assertEqual(report['module_count'], 1)
                self.assertEqual(report['execution_processes'], 1)
                self.assertEqual(report['groups'][0]['modules'], ['test_smoke.py'])
                retained = json.loads(cache_path.read_text(encoding='utf-8'))
                self.assertEqual(retained['schema'], 'bbk.test-duration-cache.v1')
                self.assertIn('test_smoke.py', retained['modules'])
                assert_no_path_within(self, [report_path, cache_path], root)
            finally:
                report_path.unlink(missing_ok=True)
                cache_path.unlink(missing_ok=True)

    def test_selective_update_profiles_keep_trust_checks_but_skip_unrelated_suites(self):
        with mock.patch.object(verify_all.shutil, 'which', return_value='node'):
            omp_steps = verify_all.verification_steps(profile='omp', require_node=True)
            codex_steps = verify_all.verification_steps(profile='codex')

        omp_names = [step.name for step in omp_steps]
        codex_names = [step.name for step in codex_steps]
        for names in (omp_names, codex_names):
            self.assertEqual(names[0], 'Package manifest integrity (pre-execution trust gate)')
            self.assertIn('Method-content projection drift', names)
            self.assertIn('Role-specification projection drift', names)
            self.assertIn('Model-routing policy', names)
            self.assertIn('Agent projection drift', names)
            self.assertIn('Python compilation and JSON parsing', names)
            self.assertEqual(names[-1], 'Package manifest integrity (post-test mutation check)')
            self.assertNotIn('Alpha.7 semantic fixtures', names)
            self.assertNotIn('Alpha.8 typed-profile fixtures', names)
            self.assertNotIn('Standard unittest suite', names)

        self.assertIn('OMP-focused unittest suite', omp_names)
        self.assertIn('OMP extension JavaScript syntax', omp_names)
        self.assertNotIn('Codex-focused unittest selection', omp_names)
        self.assertIn('Codex-focused unittest selection', codex_names)
        self.assertNotIn('OMP extension JavaScript syntax', codex_names)
        self.assertNotIn('OMP-focused unittest suite', codex_names)

    def test_setup_exposes_requested_test_and_install_flags(self):
        parser = setup_tool.build_parser()
        test = parser.parse_args(['--test'])
        self.assertTrue(test.test)
        self.assertTrue(parser.parse_args(['--test-fast']).test_fast)
        self.assertTrue(parser.parse_args(['--release-test']).release_test)
        combined = parser.parse_args(['--test-and-install', '--scope', 'project', '--root', '/tmp/project', '--omp', '--language-profiles', 'profiles.zip', '--profile-id', 'rust', '--uninstall-existing', '--test-mode', 'pooled', '--test-jobs', '6'])
        self.assertTrue(combined.test_and_install)
        values = setup_tool.install_arguments(combined)
        self.assertIn('--verify', values)
        self.assertIn('--language-profiles', values)
        self.assertIn('profiles.zip', values)
        self.assertIn('--profile-id', values)
        self.assertIn('rust', values)
        self.assertIn('--uninstall-existing', values)
        self.assertEqual(values[values.index('--verification-profile') + 1], 'standard')
        self.assertEqual(values[values.index('--test-mode') + 1], 'pooled')
        self.assertEqual(values[values.index('--test-jobs') + 1], '6')
        release_combined = parser.parse_args(['--release-test-and-install', '--omp'])
        release_values = setup_tool.install_arguments(release_combined)
        self.assertEqual(
            release_values[release_values.index('--verification-profile') + 1],
            'release',
        )
        ordinary = parser.parse_args(['--install', '--omp'])
        ordinary_values = setup_tool.install_arguments(ordinary)
        self.assertNotIn('--keep-existing', ordinary_values)
        reconciled = parser.parse_args(['--install', '--omp', '--keep-existing'])
        reconciled_values = setup_tool.install_arguments(reconciled)
        self.assertIn('--keep-existing', reconciled_values)
        destructive = parser.parse_args(['--install', '--omp', '--uninstall-existing'])
        destructive_values = setup_tool.install_arguments(destructive)
        self.assertIn('--uninstall-existing', destructive_values)
        self.assertNotIn('--keep-existing', destructive_values)

    def test_profile_zip_extraction_rejects_traversal_and_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            traversal = base / 'traversal.zip'
            with zipfile.ZipFile(traversal, 'w') as archive:
                archive.writestr('../escape.txt', 'bad')
            with self.assertRaises(profile_install.ProfileInstallError):
                profile_install.safe_extract_zip(traversal, base / 'out-traversal')
            symlink = base / 'symlink.zip'
            info = zipfile.ZipInfo('profile/link')
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 511) << 16
            with zipfile.ZipFile(symlink, 'w') as archive:
                archive.writestr(info, 'target')
            with self.assertRaises(profile_install.ProfileInstallError):
                profile_install.safe_extract_zip(symlink, base / 'out-symlink')

    def test_profile_zip_rejects_portable_collisions_and_windows_unsafe_names(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            collision = base / 'collision.zip'
            with zipfile.ZipFile(collision, 'w') as archive:
                archive.writestr('profile/Skill.md', 'one')
                archive.writestr('profile/skill.md', 'two')
            with self.assertRaises(profile_install.ProfileInstallError):
                profile_install.safe_extract_zip(collision, base / 'out-collision')
            for number, name in enumerate(('profile/data.txt:stream', 'profile/CON.txt', 'profile/trailing. ')):
                unsafe = base / f'unsafe-{number}.zip'
                with zipfile.ZipFile(unsafe, 'w') as archive:
                    archive.writestr(name, 'bad')
                with self.assertRaises(profile_install.ProfileInstallError):
                    profile_install.safe_extract_zip(unsafe, base / f'out-{number}')

    def test_release_bundle_manifest_requires_qualified_schema_and_exact_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'packages').mkdir()
            payload = root / 'packages' / 'profile.zip'
            payload.write_bytes(b'profile')
            import hashlib
            manifest = {'schema': 'bbk.language-profiles-release-bundle-manifest.v1', 'status': 'PASS', 'fileCount': 1, 'files': [{'path': 'packages/profile.zip', 'bytes': payload.stat().st_size, 'sha256': hashlib.sha256(payload.read_bytes()).hexdigest()}]}
            (root / 'RELEASE-MANIFEST.json').write_text(json.dumps(manifest), encoding='utf-8')
            self.assertEqual(profile_install.verify_bundle_manifest(root)['status'], 'PASS')
            manifest['status'] = 'FAIL'
            (root / 'RELEASE-MANIFEST.json').write_text(json.dumps(manifest), encoding='utf-8')
            with self.assertRaises(profile_install.ProfileInstallError):
                profile_install.verify_bundle_manifest(root)

    def test_install_preflight_rejects_duplicate_destination_ownership(self):
        with self.assertRaises(install_tool.InstallError):
            install_tool.validate_install_plan({'files': [{'path': 'C:/tmp/shared.md', 'sha256': 'a', 'source': 'one'}, {'path': 'c:\\tmp\\shared.md', 'sha256': 'b', 'source': 'two'}]})

    def test_install_parser_accepts_verification_and_profile_bundle_flags(self):
        args = install_tool.build_parser().parse_args(['install', '--scope', 'user', '--omp', '--verify', '--language-profiles', 'profiles.zip', '--profile-id', 'python'])
        self.assertTrue(args.verify)
        self.assertTrue(args.omp)
        self.assertEqual(args.language_profiles, ['profiles.zip'])
        self.assertEqual(args.profile_id, ['python'])

    def test_existing_install_prompt_defaults_to_clean_replacement_but_automation_is_explicit(self):
        class InteractiveInput(io.StringIO):
            def isatty(self) -> bool:
                return True

        existing = {
            'version': '0.1.0-alpha.12.1',
            'harnesses': ['omp', 'codex'],
            'file_count': 123,
            'manifest_path': Path('/tmp/install-manifest.json'),
        }
        parser = install_tool.build_parser()

        interactive = parser.parse_args(['install', '--scope', 'user', '--omp', '--no-language-profiles'])

        class LineMediatedOutput:
            """Expose only newline-terminated writes, like Windows PowerShell may."""

            encoding = 'utf-8'

            def __init__(self) -> None:
                self.pending = ''
                self.visible = ''

            def write(self, value: str) -> int:
                self.pending += value
                while '\n' in self.pending:
                    line, self.pending = self.pending.split('\n', 1)
                    self.visible += line + '\n'
                return len(value)

            def flush(self) -> None:
                return None

        line_output = LineMediatedOutput()

        class PromptCheckingInput(InteractiveInput):
            def readline(self, *args, **kwargs):
                self_test.assertIn(
                    'Clean-replace the selected omp harness now? [Y/n]\n',
                    line_output.visible,
                    'interactive prompt must be visible through a line-oriented host before input is read',
                )
                return super().readline(*args, **kwargs)

        self_test = self
        with mock.patch.object(install_tool.sys, 'stdin', PromptCheckingInput('\n')), mock.patch.object(install_tool.sys, 'stdout', line_output):
            self.assertEqual(install_tool.choose_existing_install_action(interactive, existing), 'replace')
        self.assertEqual(line_output.pending, '')

        decline_output = io.StringIO()
        with mock.patch.object(install_tool.sys, 'stdin', InteractiveInput('n\n')), mock.patch.object(install_tool.sys, 'stdout', decline_output):
            self.assertEqual(install_tool.choose_existing_install_action(interactive, existing), 'keep')
        self.assertTrue(decline_output.getvalue().endswith('[Y/n]\n'))

        full_existing = dict(existing, harnesses=['omp'])
        full_output = io.StringIO()
        with mock.patch.object(install_tool.sys, 'stdin', InteractiveInput('\n')), mock.patch.object(install_tool.sys, 'stdout', full_output):
            self.assertEqual(install_tool.choose_existing_install_action(interactive, full_existing), 'replace')
        self.assertIn('reuses byte-identical successor files in place', full_output.getvalue())
        self.assertTrue(full_output.getvalue().endswith('Uninstall the existing BBK installation first? [Y/n]\n'))

        unsupported = parser.parse_args(['install', '--scope', 'user', '--claude', '--no-language-profiles'])
        with mock.patch.object(install_tool.sys, 'stdin', InteractiveInput('\n')), mock.patch.object(install_tool.sys, 'stdout', io.StringIO()):
            with self.assertRaises(install_tool.InstallError):
                install_tool.choose_existing_install_action(unsupported, existing)

        json_args = parser.parse_args(['--json', 'install', '--scope', 'user', '--omp', '--no-language-profiles'])
        self.assertEqual(install_tool.choose_existing_install_action(json_args, existing), 'keep')
        dry_args = parser.parse_args(['install', '--scope', 'user', '--omp', '--no-language-profiles', '--dry-run'])
        self.assertEqual(install_tool.choose_existing_install_action(dry_args, existing), 'keep')
        replace_args = parser.parse_args(['install', '--scope', 'user', '--omp', '--no-language-profiles', '--uninstall-existing'])
        self.assertEqual(install_tool.choose_existing_install_action(replace_args, existing), 'replace')
        keep_args = parser.parse_args(['install', '--scope', 'user', '--omp', '--no-language-profiles', '--keep-existing'])
        self.assertEqual(install_tool.choose_existing_install_action(keep_args, existing), 'keep')

    def test_clean_replacement_preserves_unowned_omp_extension_files(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            home = base / 'home'
            home.mkdir()
            env = os.environ.copy()
            env.update({
                'BBK_HOME': str(home),
                'HOME': str(home),
                'BBK_INSTALL_ROOT': str(base / 'data'),
                'BBK_BIN_DIR': str(base / 'bin'),
            })
            base_command = [
                sys.executable,
                str(m4_ROOT / 'tools' / 'install.py'),
                '--json',
                'install',
                '--scope', 'user',
                '--omp',
                '--no-language-profiles',
            ]
            first = test_run_cli(base_command, cwd=m4_ROOT, env=env, check=False, timeout=120)
            self.assertEqual(first.returncode, 0, first.stderr or first.stdout)
            first_value = json.loads(first.stdout)
            self.assertFalse(first_value['preexisting_install']['detected'])

            custom = home / '.omp' / 'agent' / 'extensions' / 'bbk' / 'custom-model-profile.json'
            custom.write_text('{"ownedBy":"user"}\n', encoding='utf-8')

            second = test_run_cli([*base_command, '--uninstall-existing'], cwd=m4_ROOT, env=env, check=False, timeout=120)
            self.assertEqual(second.returncode, 0, second.stderr or second.stdout)
            value = json.loads(second.stdout)
            replacement = value['preexisting_install']
            self.assertTrue(replacement['detected'])
            self.assertEqual(replacement['decision'], 'replace')
            self.assertTrue(replacement['uninstalled'])
            self.assertEqual(replacement['previous_version'], (m4_ROOT / 'VERSION').read_text(encoding='utf-8').strip())
            self.assertGreater(
                replacement['removed_count'] + replacement.get('reused_identical_count', 0),
                0,
            )
            self.assertTrue(custom.is_file())
            self.assertEqual(custom.read_text(encoding='utf-8'), '{"ownedBy":"user"}\n')

            removed = test_run_cli(
                [sys.executable, str(m4_ROOT / 'tools' / 'install.py'), '--json', 'uninstall', '--scope', 'user'],
                cwd=m4_ROOT, env=env, check=False, timeout=120,
            )
            self.assertEqual(removed.returncode, 0, removed.stderr or removed.stdout)
            self.assertTrue(custom.is_file())

    def test_clean_replacement_reuses_unchanged_language_profile_files(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            home = base / 'home'
            home.mkdir()
            profile_root = m4__write_profile_package(base / 'profile-source', profile_id='reuse-sample')
            env = os.environ.copy()
            env.update({
                'BBK_HOME': str(home),
                'HOME': str(home),
                'BBK_INSTALL_ROOT': str(base / 'data'),
                'BBK_BIN_DIR': str(base / 'bin'),
            })
            command = [
                sys.executable, str(m4_ROOT / 'tools' / 'install.py'), '--json', 'install',
                '--scope', 'user', '--omp', '--language-profiles', str(profile_root),
                '--profile-id', 'reuse-sample',
            ]
            first_process = test_run_cli(
                command, cwd=m4_ROOT, env=env, check=False, timeout=120,
            )
            self.assertEqual(first_process.returncode, 0, first_process.stderr or first_process.stdout)
            first = json.loads(first_process.stdout)
            profile_records = [
                item for item in first['files']
                if install_tool._is_language_profile_source(item.get('source'))
            ]
            self.assertGreater(len(profile_records), 0)
            before = {
                item['path']: (Path(item['path']).stat().st_ino, Path(item['path']).stat().st_mtime_ns)
                for item in profile_records
            }

            second_process = test_run_cli(
                [*command, '--uninstall-existing'],
                cwd=m4_ROOT, env=env, check=False, timeout=120,
            )
            self.assertEqual(second_process.returncode, 0, second_process.stderr or second_process.stdout)
            second = json.loads(second_process.stdout)
            replacement = second['preexisting_install']
            self.assertGreater(replacement['reused_identical_count'], 0)
            self.assertEqual(
                replacement['reused_language_profile_file_count'],
                len(profile_records),
            )
            self.assertEqual(replacement['modified_backup_count'], 0)
            for path_text, identity in before.items():
                path = Path(path_text)
                self.assertTrue(path.is_file())
                self.assertEqual((path.stat().st_ino, path.stat().st_mtime_ns), identity)
            final_profile_records = [
                item for item in second['files']
                if install_tool._is_language_profile_source(item.get('source'))
            ]
            self.assertEqual(len(final_profile_records), len(profile_records))
            self.assertTrue(all(item['action'] == 'unchanged' for item in final_profile_records))

    def test_omp_scoped_clean_replacement_preserves_codex_and_unowned_files(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            home = base / 'home'
            home.mkdir()
            env = os.environ.copy()
            env.update({
                'BBK_HOME': str(home),
                'HOME': str(home),
                'BBK_INSTALL_ROOT': str(base / 'data'),
                'BBK_BIN_DIR': str(base / 'bin'),
            })
            install_cmd = [
                sys.executable, str(m4_ROOT / 'tools' / 'install.py'), '--json', 'install',
                '--scope', 'user', '--omp', '--codex', '--no-language-profiles',
            ]
            first = test_run_cli(
                install_cmd, cwd=m4_ROOT, env=env, check=False, timeout=180,
            )
            self.assertEqual(first.returncode, 0, first.stderr or first.stdout)
            installed = json.loads(first.stdout)
            manifest_path = Path(installed['manifest_path'])
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))

            codex_root = home / '.codex' / 'agents'
            codex_before = {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(codex_root.glob('bbk_*.toml'))
            }
            stale = home / '.omp' / 'agent' / 'agents' / 'bbk_obsolete.md'
            stale.write_text('obsolete managed OMP agent\n', encoding='utf-8')
            manifest['files'].append({
                'path': install_tool.json_path(stale),
                'sha256': hashlib.sha256(stale.read_bytes()).hexdigest(),
                'action': 'create',
                'source': 'test:stale-omp-agent',
                'backup': None,
                'executable': False,
            })
            manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
            custom = home / '.omp' / 'agent' / 'extensions' / 'bbk' / 'custom-model-profile.json'
            custom.write_text('{"ownedBy":"user"}\n', encoding='utf-8')

            second = test_run_cli(
                [sys.executable, str(m4_ROOT / 'tools' / 'install.py'), '--json', 'install',
                 '--scope', 'user', '--omp', '--uninstall-existing'],
                cwd=m4_ROOT, env=env, check=False, timeout=180,
            )
            self.assertEqual(second.returncode, 0, second.stderr or second.stdout)
            value = json.loads(second.stdout)
            self.assertEqual(value['preexisting_install']['decision'], 'replace-selected')
            self.assertEqual(value['preexisting_install']['selected_harnesses'], ['omp'])
            self.assertEqual(value['preexisting_install']['preserved_harnesses'], ['codex'])
            self.assertFalse(value['preexisting_install']['full_install_uninstalled'])
            self.assertGreaterEqual(value['preexisting_install']['removed_stale_count'], 1)
            self.assertTrue(value['omp'])
            self.assertTrue(value['codex'])
            self.assertFalse(stale.exists())
            self.assertTrue(custom.is_file())
            codex_after = {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(codex_root.glob('bbk_*.toml'))
            }
            self.assertEqual(codex_before, codex_after)
            final_manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            final_paths = {install_tool.portable_path_key(item['path']) for item in final_manifest['files']}
            self.assertNotIn(install_tool.portable_path_key(stale), final_paths)

    def test_codex_scoped_clean_replacement_preserves_omp_and_unowned_files(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            home = base / 'home'
            home.mkdir()
            env = os.environ.copy()
            env.update({
                'BBK_HOME': str(home),
                'HOME': str(home),
                'BBK_INSTALL_ROOT': str(base / 'data'),
                'BBK_BIN_DIR': str(base / 'bin'),
            })
            install_cmd = [
                sys.executable, str(m4_ROOT / 'tools' / 'install.py'), '--json', 'install',
                '--scope', 'user', '--omp', '--codex', '--no-language-profiles',
            ]
            first = test_run_cli(
                install_cmd, cwd=m4_ROOT, env=env, check=False, timeout=180,
            )
            self.assertEqual(first.returncode, 0, first.stderr or first.stdout)
            installed = json.loads(first.stdout)
            manifest_path = Path(installed['manifest_path'])
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))

            omp_root = home / '.omp'
            omp_before = {
                path.relative_to(omp_root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(omp_root.rglob('*')) if path.is_file()
            }
            stale = home / '.codex' / 'agents' / 'bbk_obsolete.toml'
            stale.write_text('name = "bbk_obsolete"\n', encoding='utf-8')
            manifest['files'].append({
                'path': install_tool.json_path(stale),
                'sha256': hashlib.sha256(stale.read_bytes()).hexdigest(),
                'action': 'create',
                'source': 'test:stale-codex-agent',
                'backup': None,
                'executable': False,
            })
            manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
            custom = home / '.codex' / 'agents' / 'custom-user-agent.toml'
            custom.write_text('name = "custom_user_agent"\n', encoding='utf-8')

            second = test_run_cli(
                [sys.executable, str(m4_ROOT / 'tools' / 'install.py'), '--json', 'install',
                 '--scope', 'user', '--codex', '--uninstall-existing'],
                cwd=m4_ROOT, env=env, check=False, timeout=180,
            )
            self.assertEqual(second.returncode, 0, second.stderr or second.stdout)
            value = json.loads(second.stdout)
            self.assertEqual(value['preexisting_install']['decision'], 'replace-selected')
            self.assertEqual(value['preexisting_install']['selected_harnesses'], ['codex'])
            self.assertEqual(value['preexisting_install']['preserved_harnesses'], ['omp'])
            self.assertFalse(value['preexisting_install']['full_install_uninstalled'])
            self.assertGreaterEqual(value['preexisting_install']['removed_stale_count'], 1)
            self.assertTrue(value['omp'])
            self.assertTrue(value['codex'])
            self.assertFalse(stale.exists())
            self.assertTrue(custom.is_file())
            omp_after = {
                path.relative_to(omp_root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(omp_root.rglob('*')) if path.is_file()
            }
            self.assertEqual(omp_before, omp_after)
            final_manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            final_paths = {install_tool.portable_path_key(item['path']) for item in final_manifest['files']}
            self.assertNotIn(install_tool.portable_path_key(stale), final_paths)

    def test_profile_bundle_installs_with_core_in_one_manifest_and_uninstalls(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            bundle = m4__write_profile_bundle(base)
            env = os.environ.copy()
            env.update({'BBK_HOME': str(base / 'home'), 'BBK_INSTALL_ROOT': str(base / 'data'), 'BBK_BIN_DIR': str(base / 'bin')})
            command = [sys.executable, str(m4_ROOT / 'tools' / 'install.py'), '--json', 'install', '--scope', 'user', '--codex', '--omp', '--language-profiles', str(bundle)]
            dry = test_run_cli([*command, '--dry-run'], cwd=m4_ROOT, env=env, check=False, timeout=120)
            self.assertEqual(dry.returncode, 0, dry.stderr or dry.stdout)
            dry_value = json.loads(dry.stdout)
            self.assertEqual([item['id'] for item in dry_value['language_profiles']], ['sample'])
            self.assertEqual(dry_value['language_profiles'][0]['router_skill'], 'sample')
            self.assertEqual(dry_value['language_profile_registry']['profile_count'], 1)
            self.assertFalse((base / 'data').exists())
            self.assertFalse(Path(dry_value['manifest_path']).exists())
            self.assertTrue(any((str(item.get('source', '')).startswith('profile:sample@') for item in dry_value['files'])))
            self.assertTrue(any((item.get('source') == 'generated:installed-profile-registry-skill' for item in dry_value['files'])))
            installed = test_run_cli(command, cwd=m4_ROOT, env=env, check=False, timeout=120)
            self.assertEqual(installed.returncode, 0, installed.stderr or installed.stdout)
            value = json.loads(installed.stdout)
            self.assertEqual(value['schema'], 'bbk.install-manifest.v1')
            self.assertEqual(len(value['language_profiles']), 1)
            self.assertTrue(Path(value['manifest_path']).is_file())
            self.assertTrue((base / 'data' / 'profiles' / 'sample' / 'current.json').is_file())
            self.assertTrue((base / 'home' / '.agents' / 'skills' / 'sample' / 'SKILL.md').is_file())
            registry_path = base / 'home' / '.agents' / 'skills' / 'bbk-installed-profiles' / 'SKILL.md'
            self.assertTrue(registry_path.is_file())
            registry_text = registry_path.read_text(encoding='utf-8')
            self.assertIn('### `sample@0.1.0-alpha.3`', registry_text)
            self.assertIn('Router skill: `sample`', registry_text)
            self.assertNotIn('package-source placeholder', registry_text)
            effective_registry = json.loads((base / 'data' / 'effective-language-profiles.json').read_text(encoding='utf-8'))
            self.assertEqual([item['id'] for item in effective_registry['profiles']], ['sample'])
            self.assertTrue((base / 'home' / '.omp' / 'agent' / 'extensions' / 'bbk-profile-sample' / 'index.js').is_file())
            self.assertTrue((base / 'bin' / ('profile.cmd' if os.name == 'nt' else 'profile')).is_file())
            registry_skill = base / 'home' / '.agents' / 'skills' / 'bbk-installed-profiles' / 'SKILL.md'
            self.assertTrue(registry_skill.is_file())
            registry_text = registry_skill.read_text(encoding='utf-8')
            self.assertIn('`sample@0.1.0-alpha.3`', registry_text)
            self.assertIn('Router skill: `sample`', registry_text)
            self.assertIn('--json profile list', registry_text)
            self.assertIn('BBK CLI discovery', registry_text)
            self.assertIn('Exact fallback when `bbk` is not on `PATH`', registry_text)
            self.assertNotIn('package-source placeholder', registry_text)
            effective_profiles = json.loads((base / 'data' / 'effective-language-profiles.json').read_text(encoding='utf-8'))
            self.assertEqual(effective_profiles['schema'], 'bbk.installed-profile-registry.v1')
            self.assertEqual(effective_profiles['profiles'][0]['router_skill'], 'sample')
            self.assertEqual(effective_profiles['profiles'][0]['skills'][0]['kind'], 'router')
            self.assertEqual(value['language_profile_registry']['profile_count'], 1)
            self.assertEqual(value['language_profile_registry']['skill'], 'bbk-installed-profiles')
            status = test_run_cli([sys.executable, str(m4_ROOT / 'tools' / 'install.py'), '--json', 'status', '--scope', 'user'], cwd=m4_ROOT, env=env, check=False, timeout=120)
            self.assertEqual(status.returncode, 0, status.stderr or status.stdout)
            status_value = json.loads(status.stdout)
            self.assertEqual(status_value['summary'].get('current'), len(status_value['files']))
            self.assertEqual([item['id'] for item in status_value['language_profiles']], ['sample'])
            self.assertEqual(status_value['language_profile_registry']['profile_count'], 1)
            removed = test_run_cli([sys.executable, str(m4_ROOT / 'tools' / 'install.py'), '--json', 'uninstall', '--scope', 'user'], cwd=m4_ROOT, env=env, check=False, timeout=120)
            self.assertEqual(removed.returncode, 0, removed.stderr or removed.stdout)
            self.assertFalse((base / 'data' / 'install-manifest.json').exists())
            self.assertFalse((base / 'home' / '.agents' / 'skills' / 'sample' / 'SKILL.md').exists())
            self.assertFalse((base / 'home' / '.agents' / 'skills' / 'bbk-installed-profiles' / 'SKILL.md').exists())
            self.assertFalse((base / 'home' / '.agents' / 'skills' / 'bbk-installed-profiles' / 'SKILL.md').exists())

    def test_unchanged_language_profile_install_is_reused_and_local_divergence_is_repaired_only_with_force(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            bundle = m4__write_profile_bundle(base)
            home = base / 'home'
            home.mkdir()
            env = os.environ.copy()
            env.update({
                'BBK_HOME': str(home),
                'HOME': str(home),
                'BBK_INSTALL_ROOT': str(base / 'data'),
                'BBK_BIN_DIR': str(base / 'bin'),
            })
            command = [
                sys.executable, str(m4_ROOT / 'tools' / 'install.py'), '--json',
                'install', '--scope', 'user', '--codex', '--omp',
                '--language-profiles', str(bundle), '--keep-existing',
            ]
            first = test_run_cli(command, cwd=m4_ROOT, env=env, check=False, timeout=120)
            self.assertEqual(first.returncode, 0, first.stderr or first.stdout)
            first_value = json.loads(first.stdout)
            self.assertEqual(first_value['language_profiles'][0]['install_action'], 'installed')

            args = install_tool.build_parser().parse_args([
                '--json', 'install', '--scope', 'user', '--codex', '--omp',
                '--language-profiles', str(bundle), '--keep-existing',
            ])
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
                install_tool, 'install_language_profile',
                side_effect=AssertionError('unchanged profile should not be reinstalled'),
            ):
                reused = install_tool.install(args)
            self.assertEqual(reused['language_profile_reuse']['reused_profile_count'], 1)
            self.assertGreater(reused['language_profile_reuse']['reused_file_count'], 0)
            self.assertEqual(reused['language_profiles'][0]['install_action'], 'reused')
            self.assertGreater(reused['language_profiles'][0]['reused_file_count'], 0)
            self.assertIn('reused', reused['preflight']['actions'])

            skill = home / '.agents' / 'skills' / 'sample' / 'SKILL.md'
            original = skill.read_text(encoding='utf-8')
            skill.write_text(original + '\nlocal divergence\n', encoding='utf-8')
            rejected = test_run_cli(command, cwd=m4_ROOT, env=env, check=False, timeout=120)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn('Destination differs', rejected.stderr + rejected.stdout)

            repaired = test_run_cli([*command, '--force'], cwd=m4_ROOT, env=env, check=False, timeout=120)
            self.assertEqual(repaired.returncode, 0, repaired.stderr or repaired.stdout)
            repaired_value = json.loads(repaired.stdout)
            self.assertEqual(repaired_value['language_profile_reuse']['reused_profile_count'], 0)
            self.assertEqual(repaired_value['language_profiles'][0]['install_action'], 'installed')
            self.assertEqual(skill.read_text(encoding='utf-8'), original)

            removed = test_run_cli(
                [sys.executable, str(m4_ROOT / 'tools' / 'install.py'), '--json',
                 'uninstall', '--scope', 'user'],
                cwd=m4_ROOT, env=env, check=False, timeout=120,
            )
            self.assertEqual(removed.returncode, 0, removed.stderr or removed.stdout)
            self.assertFalse(skill.exists())

    def test_bundle_outer_pass_does_not_hide_tampered_inner_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            bundle = m4__write_profile_bundle(base)
            extracted = base / 'extracted'
            profile_install.safe_extract_zip(bundle, extracted)
            bundle_root = next((path.parent for path in extracted.rglob('RELEASE-MANIFEST.json')))
            package_zip = next((bundle_root / 'packages').glob('*.zip'))
            with zipfile.ZipFile(package_zip, 'a') as archive:
                archive.writestr('bbk-profile-sample-0.1.0-alpha.3/unexpected.txt', 'tampered')
            release = json.loads((bundle_root / 'RELEASE-MANIFEST.json').read_text(encoding='utf-8'))
            release['files'][0]['bytes'] = package_zip.stat().st_size
            release['files'][0]['sha256'] = hashlib.sha256(package_zip.read_bytes()).hexdigest()
            (bundle_root / 'RELEASE-MANIFEST.json').write_text(json.dumps(release, indent=2, sort_keys=True) + '\n', encoding='utf-8')
            with tempfile.TemporaryDirectory() as prepared:
                with self.assertRaises(profile_install.ProfileInstallError):
                    profile_install.prepare_profile_sources([bundle_root], temp_root=Path(prepared))

    def test_test_and_install_stops_before_install_plan_on_failed_verification(self):
        args = install_tool.build_parser().parse_args(['install', '--scope', 'user', '--codex', '--verify'])
        with mock.patch.object(install_tool, 'run_verification_gate', side_effect=install_tool.InstallError('verification failed')), mock.patch.object(install_tool, '_perform_install') as perform:
            with self.assertRaises(install_tool.InstallError):
                install_tool.install(args)
        perform.assert_not_called()

    def test_profile_wrapper_defaults_to_test_and_install(self):
        with mock.patch.object(install_profiles.setup_tool, 'main', return_value=0) as entry:
            result = install_profiles.main(['--bundle', 'profiles.zip', '--omp', '--profile', 'rust'])
        self.assertEqual(result, 0)
        values = entry.call_args.args[0]
        self.assertIn('--test-and-install', values)
        self.assertIn('--language-profiles', values)
        self.assertIn('profiles.zip', values)
        self.assertIn('--profile-id', values)
        self.assertIn('rust', values)

    def test_current_docs_show_one_command_paths(self):
        combined = '\n'.join(((m4_ROOT / relative).read_text(encoding='utf-8') for relative in ('README.md', 'docs/INSTALL.md', 'docs/LANGUAGE-PROFILES.md', 'docs/USAGE.md')))
        for command in ('python tools/setup.py --test', 'python tools/setup.py --release-test', 'python tools/bootstrap.py --test', 'python tools/bootstrap.py --test-and-install', '--language-profiles', 'tools/install_profiles.py'):
            self.assertIn(command, combined)

# ---------------------------------------------------------------------------
# Historical source: test_alpha11_1_bundled_release.py
# ---------------------------------------------------------------------------
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock
m5_ROOT = Path(__file__).resolve().parents[1]
m5_TOOLS = m5_ROOT / 'tools'
import sys
if str(m5_TOOLS) not in sys.path:
    sys.path.insert(0, str(m5_TOOLS))
import install
import install_profiles
import profile_install
import setup as setup_tool
m5_BUNDLE = m5_ROOT / 'bundled-language-profiles'
m5_EXPECTED_PROFILES = ['codesys', 'go', 'python', 'rust', 'typescript-javascript']
m5_EXPECTED_PROFILE_VERSIONS = {
    'codesys': '0.1.0-alpha.4',
    'go': '0.1.0-alpha.3',
    'python': '0.1.0-alpha.3',
    'rust': '0.1.0-alpha.3',
    'typescript-javascript': '0.1.0-alpha.3',
}

class Alpha111BundledReleaseTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls._prepared_temp = tempfile.TemporaryDirectory(prefix='bbk-alpha111-profiles-')
        cls.prepared = profile_install.prepare_profile_sources([m5_BUNDLE], temp_root=Path(cls._prepared_temp.name))
        cls.by_id = {item.profile_id: item for item in cls.prepared}

    @classmethod
    def tearDownClass(cls) -> None:
        cls._prepared_temp.cleanup()

    def test_current_successor_is_repository_native_and_self_contained(self):
        self.assertEqual((m5_ROOT / 'VERSION').read_text(encoding='utf-8').strip(), '0.1.0-alpha.15')
        self.assertTrue((m5_ROOT / 'docs' / 'README.md').is_file())
        self.assertTrue((m5_ROOT / 'docs' / 'DEVELOPMENT.md').is_file())
        self.assertTrue((m5_ROOT / 'bundled-language-profiles' / 'packages').is_dir())
        self.assertFalse((m5_ROOT / 'tools' / 'extract_git_repositories.py').exists())
        self.assertFalse((m5_ROOT / 'docs' / 'GIT-REPOSITORIES.md').exists())


    def test_bundled_release_manifest_verifies_and_contains_exactly_five_profiles(self):
        report = profile_install.verify_bundle_manifest(m5_BUNDLE)
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual([item.profile_id for item in self.prepared], m5_EXPECTED_PROFILES)
        self.assertEqual({item.profile_id: item.version for item in self.prepared}, m5_EXPECTED_PROFILE_VERSIONS)
        release = json.loads((m5_BUNDLE / 'RELEASE-MANIFEST.json').read_text(encoding='utf-8'))
        self.assertEqual(release.get('profileVersions'), m5_EXPECTED_PROFILE_VERSIONS)
        self.assertTrue(all((item.package_verification.get('status') == 'PASS' for item in self.prepared)))
        self.assertTrue(all((item.compatibility.get('status') == 'PASS' for item in self.prepared)))

    def test_all_bundled_current_metadata_is_consistent(self):
        for profile_id, item in sorted(self.by_id.items()):
            with self.subTest(profile=profile_id):
                expected_version = m5_EXPECTED_PROFILE_VERSIONS[profile_id]
                self.assertEqual(item.profile['version'], expected_version)
                self.assertEqual(item.profile['requires']['bbk_minimum'], '0.1.0-alpha.8')
                self.assertEqual((item.root / 'VERSION').read_text(encoding='utf-8').strip(), expected_version)
                dialects = item.profile.get('contract_dialects', {})
                self.assertEqual(dialects['implementation_structure']['legacy_output_value'], '0.1.0-alpha.4')
                self.assertEqual(dialects['execution_slice']['legacy_output_value'], '0.1.0-alpha.4')
                self.assertEqual(dialects['typed_profile_dispatch']['id'], 'bbk.profile-capability.v1')
                readme = (item.root / 'README.md').read_text(encoding='utf-8')
                install_doc = (item.root / 'docs' / 'INSTALL.md').read_text(encoding='utf-8')
                metadata_doc = (item.root / 'docs' / 'METADATA-CONTRACT.md').read_text(encoding='utf-8')
                omp_package = json.loads((item.root / 'omp' / 'extension' / 'package.json').read_text(encoding='utf-8'))
                self.assertIn(expected_version, readme)
                self.assertIn('0.1.0-alpha.8', readme)
                self.assertIn('0.1.0-alpha.8', install_doc)
                self.assertIn('contract dialect', metadata_doc.lower())
                self.assertEqual(omp_package['version'], expected_version)
                expected_predecessor = '0.1.0-alpha.3' if profile_id == 'codesys' else '0.1.0-alpha.2'
                self.assertEqual(item.profile.get('predecessor', {}).get('version'), expected_predecessor)

    def test_current_docs_describe_the_mixed_profile_versions(self):
        combined = "\n".join(
            (m5_ROOT / relative).read_text(encoding="utf-8")
            for relative in (
                "README.md",
                "RELEASE-NOTES.md",
                "docs/INSTALL.md",
                "docs/LANGUAGE-PROFILES.md",
                "bundled-language-profiles/README.md",
            )
        )
        self.assertIn("CODESYS `0.1.0-alpha.4`", combined)
        self.assertIn("Go, Python, Rust, and TypeScript/JavaScript", combined)
        self.assertIn("`0.1.0-alpha.3`", combined)
        for stale_claim in (
            "All five packages remain `0.1.0-alpha.3`",
            "five independently manifested alpha.3 language profiles",
            "five bundled alpha.3 profiles",
            "The five package identities remain `0.1.0-alpha.3`",
        ):
            self.assertNotIn(stale_claim, combined)

    def test_profile_omp_python_overrides_are_interpreter_safe(self):
        for profile_id, item in sorted(self.by_id.items()):
            with self.subTest(profile=profile_id):
                extension = (item.root / 'omp' / 'extension' / 'index.js').read_text(encoding='utf-8')
                self.assertIn('function explicitCommand(value)', extension)
                self.assertIn('.endsWith(".py")', extension)
                self.assertIn('return pythonCommand(path.resolve(value))', extension)

    def test_python_profile_accepts_compatible_successor_core(self):
        item = self.by_id['python']
        module_path = item.root / 'tools' / 'bbk_python.py'
        spec = importlib.util.spec_from_file_location('bbk_profile_python_runtime', module_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertFalse(module.version_supports_structure_contract('0.1.0-alpha.3'))
        for version in ('0.1.0-alpha.4', '0.1.0-alpha.8', '0.1.0-alpha.11.11', '0.1.0-alpha.11.12', '0.1.0-alpha.12', '0.1.0-alpha.12.2', '0.1.0-alpha.12.4', '0.1.0-alpha.13.1', '0.1.0-alpha.13.2', '0.1.0-alpha.13.3', '0.1.0-alpha.13.4', '0.1.0-alpha.13.5', '0.1.0-alpha.14', '0.1.0-alpha.15', '0.1.0', '0.2.0-alpha.1'):
            with self.subTest(version=version):
                self.assertTrue(module.version_supports_structure_contract(version))
        gates = json.loads((item.root / 'gates' / 'python-gates.json').read_text(encoding='utf-8'))
        requirements = {value for recipe in gates['recipes'] for value in recipe.get('requires', [])}
        self.assertIn('bbk-structure-contract-validator', requirements)
        self.assertNotIn('bbk-alpha4-structure-validator', requirements)

    def test_default_install_source_is_the_bundled_set(self):
        args = install.build_parser().parse_args(['install', '--dry-run', '--codex'])
        result = {'schema': 'bbk.install-manifest.v1', 'files': [], 'language_profiles': []}
        with mock.patch.object(install, 'prepare_profile_sources', return_value=[]) as prepare, mock.patch.object(install, '_perform_install', return_value=result):
            value = install.install(args)
        prepare.assert_called_once()
        sources = prepare.call_args.args[0]
        assert_same_path_sequence(self, [Path(value) for value in sources], [m5_BUNDLE])
        self.assertIsNone(prepare.call_args.kwargs['selected_ids'])
        self.assertEqual(args.language_profile_source_mode, 'bundled-default')
        self.assertIs(value, result)

    def test_bundled_subset_and_core_only_are_explicit(self):
        subset_args = install.build_parser().parse_args(['install', '--dry-run', '--profile-id', 'rust', '--profile-id', 'python'])
        result = {'schema': 'bbk.install-manifest.v1', 'files': [], 'language_profiles': []}
        with mock.patch.object(install, 'prepare_profile_sources', return_value=[]) as prepare, mock.patch.object(install, '_perform_install', return_value=result):
            install.install(subset_args)
        self.assertEqual(prepare.call_args.kwargs['selected_ids'], ['rust', 'python'])
        self.assertEqual(subset_args.language_profile_source_mode, 'bundled-default')
        core_args = install.build_parser().parse_args(['install', '--dry-run', '--no-language-profiles'])
        with mock.patch.object(install, 'prepare_profile_sources') as prepare, mock.patch.object(install, '_perform_install', return_value=result):
            install.install(core_args)
        prepare.assert_not_called()
        self.assertEqual(core_args.language_profile_source_mode, 'disabled')

    def test_explicit_profile_source_replaces_bundled_source(self):
        args = install.build_parser().parse_args(['install', '--dry-run', '--language-profiles', 'replacement.zip'])
        result = {'schema': 'bbk.install-manifest.v1', 'files': [], 'language_profiles': []}
        with mock.patch.object(install, 'prepare_profile_sources', return_value=[]) as prepare, mock.patch.object(install, '_perform_install', return_value=result):
            install.install(args)
        self.assertEqual(prepare.call_args.args[0], ['replacement.zip'])
        self.assertEqual(args.language_profile_source_mode, 'explicit')

    def test_profile_wrapper_uses_bundled_profiles_when_bundle_is_omitted(self):
        with mock.patch.object(install_profiles.setup_tool, 'main', return_value=0) as entry:
            code = install_profiles.main(['--omp', '--profile', 'rust', '--dry-run'])
        self.assertEqual(code, 0)
        values = entry.call_args.args[0]
        self.assertIn('--test-and-install', values)
        self.assertIn('--profile-id', values)
        self.assertIn('rust', values)
        self.assertNotIn('--language-profiles', values)

    def test_setup_forwards_default_opt_out_and_rejects_conflicting_selection(self):
        with mock.patch.object(setup_tool.install_tool, 'main', return_value=0) as entry:
            code = setup_tool.main(['--install', '--no-language-profiles', '--codex', '--dry-run'])
        self.assertEqual(code, 0)
        self.assertIn('--no-language-profiles', entry.call_args.args[0])
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            setup_tool.main(['--install', '--no-language-profiles', '--profile-id', 'rust', '--dry-run'])

    def test_install_plan_collision_is_rejected_before_any_write(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / 'same.txt'
            records: list[dict[str, object]] = []
            planned: dict[str, int] = {}
            common = {'force': False, 'dry_run': True, 'backup_root': Path(temp) / 'backups', 'records': records, 'planned': planned}
            install.install_bytes(b'one', destination, source='first', **common)
            with self.assertRaisesRegex(install.InstallError, 'Install-plan collision'):
                install.install_bytes(b'two', destination, source='second', **common)
            self.assertFalse(destination.exists())
            self.assertEqual(len(records), 1)

    @unittest.skipIf(os.name == 'nt', 'POSIX executable modes are not meaningful on Windows')
    def test_status_and_uninstall_preserve_mode_divergence(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / 'project'
            project.mkdir()
            target = project / '.bbk-kit' / 'versions' / 'demo' / 'tool.py'
            target.parent.mkdir(parents=True)
            target.write_text("print('demo')\n", encoding='utf-8')
            target.chmod(420)
            manifest = {'schema': 'bbk.install-manifest.v1', 'version': 'demo', 'scope': 'project', 'files': [{'path': target.as_posix(), 'sha256': install.sha256_file(target), 'executable': True}]}
            (project / '.bbk-kit-install.json').write_text(json.dumps(manifest), encoding='utf-8')
            status_args = install.build_parser().parse_args(['status', '--scope', 'project', '--root', str(project)])
            state = install.status(status_args)
            self.assertEqual(state['summary'], {'mode-mismatch': 1})
            uninstall_args = install.build_parser().parse_args(['uninstall', '--scope', 'project', '--root', str(project)])
            removed = install.uninstall(uninstall_args)
            self.assertEqual(removed['removed'], [])
            self.assertEqual(len(removed['preserved']), 1)
            self.assertTrue(target.exists())

    def test_current_documentation_states_the_default_and_single_archive_contract(self):
        combined = '\n'.join(((m5_ROOT / relative).read_text(encoding='utf-8') for relative in ('README.md', 'docs/INSTALL.md', 'docs/LANGUAGE-PROFILES.md', 'RELEASE-NOTES.md')))
        for expected in ('0.1.0-alpha.15', 'installed by default', '--no-language-profiles', '--profile-id', 'bundled-language-profiles', 'TypeScript/JavaScript'):
            self.assertIn(expected, combined)

# ---------------------------------------------------------------------------
# Historical source: test_alpha11_2_windows_utf8.py
# ---------------------------------------------------------------------------
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
m6_ROOT = Path(__file__).resolve().parents[1]
m6_TOOLS = m6_ROOT / 'tools'
if str(m6_TOOLS) not in sys.path:
    sys.path.insert(0, str(m6_TOOLS))
import source_sanity

class Alpha112WindowsUtf8Tests(unittest.TestCase):

    def test_current_version_and_utf8_canonical_input_are_read_explicitly(self):
        version = (m6_ROOT / 'VERSION').read_text(encoding='utf-8').strip()
        self.assertEqual(version, '0.1.0-alpha.15')
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

# ---------------------------------------------------------------------------
# Historical source: test_alpha11_6_codex_workspace.py
# ---------------------------------------------------------------------------
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
m7_ROOT = Path(__file__).resolve().parents[1]
m7_TOOLS = m7_ROOT / 'tools'
if str(m7_TOOLS) not in sys.path:
    sys.path.insert(0, str(m7_TOOLS))
m7_CODEX_AGENTS = m7_ROOT / 'projections' / 'codex' / 'agents'
m7_INSTALL = m7_ROOT / 'tools' / 'install.py'
m7_SETUP = m7_ROOT / 'tools' / 'setup.py'
m7_UPDATE_CODEX = m7_ROOT / 'tools' / 'update_codex.py'
m7_VERSION = (m7_ROOT / 'VERSION').read_text(encoding='utf-8').strip()

def m7_run(command, *, env=None, check=True):
    return test_run_cli([str(value) for value in command], cwd=m7_ROOT, env=env, check=check, timeout=180)

def m7_run_json(command, *, env=None, check=True):
    result = m7_run(command, env=env, check=check)
    return (json.loads(result.stdout), result)

def m7_snapshot(root: Path) -> dict[str, tuple[str, int]]:
    return {path.relative_to(root).as_posix(): (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns) for path in sorted(root.rglob('*')) if path.is_file()}

class Alpha116CodexWorkspaceTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.roles = json.loads((m7_ROOT / 'spec' / 'roles.json').read_text(encoding='utf-8'))['roles']
        cls.by_name = {item['name']: item for item in cls.roles}

    def test_current_version_matches_release(self) -> None:
        self.assertEqual(m7_VERSION, '0.1.0-alpha.15')

    def test_all_codex_agents_inherit_parent_sandbox(self) -> None:
        files = sorted(m7_CODEX_AGENTS.glob('*.toml'))
        self.assertEqual(len(files), len(self.roles))
        self.assertEqual({path.stem for path in files}, set(self.by_name))
        for path in files:
            with self.subTest(agent=path.stem):
                value = tomllib.loads(path.read_text(encoding='utf-8'))
                self.assertNotIn('sandbox_mode', value)
                instructions = value['developer_instructions']
                self.assertIn("Inherit the parent turn's active sandbox and approval settings", instructions)
                self.assertIn('Persist bounded BBK coordination artifacts inside the permitted workspace', instructions)
                self.assertIn('Host capability does not create authority', instructions)
                for item in self.by_name[path.stem]['scope']:
                    self.assertIn(item, instructions)
                # Codex already carries identity, model, and effort in native TOML
                # fields. Do not duplicate BBK build/provenance metadata as XML-like
                # tags inside the model-facing developer instructions.
                self.assertNotIn('<bbk-', instructions)
                self.assertNotIn('</bbk-', instructions)
                self.assertNotIn('package-version=', instructions)
                self.assertNotIn('source="shared/skills/', instructions)
                self.assertIn('## Exact role-return contract', instructions)
                self.assertIn('## Mandatory procedures — injected', instructions)
                for skill in self.by_name[path.stem].get('mandatory_skills', []):
                    self.assertIn(f'### Mandatory procedure: `{skill}`', instructions)

    def test_semantic_mutation_boundary_remains_role_specific(self) -> None:
        for role in self.roles:
            path = m7_CODEX_AGENTS / f"{role['name']}.toml"
            instructions = tomllib.loads(path.read_text(encoding='utf-8'))['developer_instructions']
            with self.subTest(agent=role['name'], mutates=role.get('mutates')):
                if role.get('mutates'):
                    self.assertIn('Modify subject or product artifacts only within the exact invocation scope', instructions)
                    self.assertNotIn('Writable host tools do not authorize subject or product mutation for this non-mutating role', instructions)
                else:
                    self.assertIn('Writable host tools do not authorize subject or product mutation for this non-mutating role', instructions)
                    self.assertNotIn('Modify subject or product artifacts only within the exact invocation scope', instructions)

    def test_generator_no_longer_projects_read_only_codex_overrides(self) -> None:
        source = (m7_ROOT / 'tools' / 'generate_agents.py').read_text(encoding='utf-8')
        self.assertNotIn('lines.append(\'sandbox_mode = "read-only"\')', source)
        completed = m7_run([sys.executable, m7_ROOT / 'tools' / 'generate_agents.py', '--check'])
        self.assertEqual(completed.returncode, 0, completed.stdout)

    def test_setup_exposes_codex_only_update_and_rejects_harness_selection(self) -> None:
        help_text = m7_run([sys.executable, m7_SETUP, '--help']).stdout
        self.assertIn('--update-codex', help_text)
        self.assertIn('--test-and-update-codex', help_text)
        self.assertIn('preserve OMP', help_text)
        invalid = m7_run([sys.executable, m7_SETUP, '--update-codex', '--scope', 'user', '--omp'], check=False)
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn('do not apply to a Codex-only update', invalid.stdout + invalid.stderr)

    def test_codex_only_update_removes_legacy_overrides_without_touching_shared_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            home = base / 'home'
            home.mkdir()
            env = os.environ.copy()
            env.update({'BBK_HOME': str(home), 'HOME': str(home), 'BBK_INSTALL_ROOT': str(base / 'data'), 'BBK_BIN_DIR': str(base / 'bin')})
            installed, _ = m7_run_json([sys.executable, m7_INSTALL, '--json', 'install', '--scope', 'user', '--codex', '--omp', '--no-language-profiles'], env=env)
            manifest_path = Path(installed['manifest_path'])
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            initial_version = manifest['version']
            records = {path_identity_key(item['path']): item for item in manifest['files']}
            codex_root = home / '.codex' / 'agents'
            for path in sorted(codex_root.glob('bbk_*.toml')):
                text = path.read_text(encoding='utf-8')
                self.assertNotIn('\nsandbox_mode = "read-only"\n', text)
                text = text.replace('\ndeveloper_instructions = ', '\nsandbox_mode = "read-only"\ndeveloper_instructions = ', 1)
                path.write_text(text, encoding='utf-8')
                records[path_identity_key(path)]['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest.setdefault('harness_versions', {})['codex'] = '0.1.0-alpha.11.5'
            manifest['harness_versions']['omp'] = initial_version
            manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
            omp_root = home / '.omp'
            shared_root = base / 'data'
            current_file = shared_root / 'current.json'
            effective_file = Path(manifest['model_routing']['effective_copy'])
            launcher_root = base / 'bin'
            package_root = Path(manifest['package_root'])
            omp_before = m7_snapshot(omp_root)
            package_before = m7_snapshot(package_root)
            launcher_before = m7_snapshot(launcher_root)
            current_before = current_file.read_bytes()
            effective_before = effective_file.read_bytes()
            updated, _ = m7_run_json([sys.executable, m7_UPDATE_CODEX, '--json', '--scope', 'user'], env=env)
            self.assertEqual(updated['status'], 'PASS')
            self.assertEqual(updated['from_version'], '0.1.0-alpha.11.5')
            self.assertEqual(updated['to_version'], m7_VERSION)
            self.assertEqual(updated['codex_agent_count'], 19)
            self.assertEqual(updated['actions'], {'replace': 19})
            self.assertFalse(updated['shared_package_updated'])
            self.assertFalse(updated['effective_model_routing_updated'])
            self.assertEqual(updated['omp_files_touched'], 0)
            self.assertIn('omp', updated['untouched_harnesses'])
            self.assertTrue(all(('/.codex/agents/bbk_' in item['path'].replace('\\', '/') for item in updated['files'])))
            self.assertEqual(omp_before, m7_snapshot(omp_root))
            self.assertEqual(package_before, m7_snapshot(package_root))
            self.assertEqual(launcher_before, m7_snapshot(launcher_root))
            self.assertEqual(current_before, current_file.read_bytes())
            self.assertEqual(effective_before, effective_file.read_bytes())
            binding = omp_root / 'agent' / 'extensions' / 'bbk' / 'bbk-package-root.json'
            routing, _ = m7_run_json([sys.executable, m7_ROOT / 'tools' / 'omp_model_routing.py', '--binding', binding, '--json', 'status'], env=env)
            self.assertEqual(routing['status'], 'PASS')
            for path in sorted(codex_root.glob('bbk_*.toml')):
                value = tomllib.loads(path.read_text(encoding='utf-8'))
                self.assertNotIn('sandbox_mode', value)
            current = json.loads(manifest_path.read_text(encoding='utf-8'))
            self.assertEqual(current['version'], initial_version)
            assert_same_path(self, current['package_root'], manifest['package_root'])
            self.assertEqual(current['harness_versions']['codex'], m7_VERSION)
            self.assertEqual(current['harness_versions']['omp'], initial_version)
            self.assertEqual(current['last_codex_update']['kind'], 'codex-only')
            self.assertFalse(current['last_codex_update']['shared_package_updated'])
            status, _ = m7_run_json([sys.executable, m7_INSTALL, '--json', 'status', '--scope', 'user'], env=env)
            self.assertEqual(status['summary'], {'current': len(status['files'])})

    def test_current_docs_explain_permission_and_authority_separation(self) -> None:
        corpus = '\n'.join(((m7_ROOT / rel).read_text(encoding='utf-8') for rel in ('README.md', 'docs/AGENTS.md', 'docs/USAGE.md', 'docs/INSTALL.md')))
        for expected in ('inherit the parent', 'sandbox', 'coordination artifacts', 'does not authorize', 'subject or product artifacts', '--update-codex'):
            self.assertIn(expected, corpus)

# ---------------------------------------------------------------------------
# Historical source: test_alpha11_7_git_repositories.py
# ---------------------------------------------------------------------------
import contextlib
import io
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock
m8_ROOT = Path(__file__).resolve().parents[1]
m8_TOOLS = m8_ROOT / 'tools'
if str(m8_TOOLS) not in sys.path:
    sys.path.insert(0, str(m8_TOOLS))
import install
import path_compat
import profile_install
import run_tests
import windows_compat
m8_build_release = m1_load_module('bbk_build_release_alpha13', 'tools/build_release.py')

class Alpha117GitRepositoryTests(unittest.TestCase):

    def test_release_package_uses_an_explicit_cross_extractor_mode_policy(self):
        self.assertEqual(m8_build_release.PACKAGE_EXECUTABLES, frozenset())
        self.assertTrue(all((not m8_build_release.is_executable(path) for path in m8_build_release.package_files())))

    def test_release_builder_uses_the_exhaustive_test_profile(self):
        with mock.patch.object(m8_build_release, "run") as runner:
            m8_build_release.qualification_checks()
        runner.assert_called_once_with([
            sys.executable,
            "tools/run_tests.py",
            "--all",
            "--profile",
            "release",
            "--require-node",
            "--mode",
            "pooled",
            "--jobs",
            "0",
        ])

    def _expanded_profiles(self, destination: Path, *, count: int | None=None) -> list[Path]:
        packages = destination / 'packages'
        packages.mkdir(parents=True)
        archives = sorted((m8_ROOT / 'bundled-language-profiles' / 'packages').glob('*.zip'))
        if count is not None:
            archives = archives[:count]
        for archive in archives:
            profile_install.safe_extract_zip(archive, packages)
        return sorted((path for path in packages.iterdir() if path.is_dir()))

    def test_unzipped_packages_directory_is_a_supported_profile_source(self):
        with tempfile.TemporaryDirectory() as raw_repo, tempfile.TemporaryDirectory() as raw_work:
            repo = Path(raw_repo)
            self._expanded_profiles(repo)
            prepared = profile_install.prepare_profile_sources([repo], temp_root=Path(raw_work))
        self.assertEqual([item.profile_id for item in prepared], ['codesys', 'go', 'python', 'rust', 'typescript-javascript'])
        self.assertTrue(all((item.package_verification['status'] == 'PASS' for item in prepared)))

    def test_manifested_profile_repository_rejects_package_tampering(self):
        with tempfile.TemporaryDirectory() as raw_repo, tempfile.TemporaryDirectory() as raw_work:
            repo = Path(raw_repo)
            roots = self._expanded_profiles(repo, count=1)
            prepared = profile_install.prepare_profile_root(roots[0], source=str(roots[0]), source_sha256=None)
            manifest = {'schema': 'bbk.language-profiles-repository-manifest.v1', 'status': 'PASS', 'profile_count': 1, 'profiles': [{'id': prepared.profile_id, 'version': prepared.version, 'package': prepared.package_name, 'path': f'packages/{roots[0].name}', 'root_sha256': prepared.root_sha256}]}
            (repo / 'REPOSITORY-MANIFEST.json').write_text(json.dumps(manifest), encoding='utf-8')
            (roots[0] / 'README.md').write_text('tampered\n', encoding='utf-8')
            with self.assertRaises(profile_install.ProfileInstallError):
                profile_install.prepare_profile_sources([repo], temp_root=Path(raw_work))

    def test_manifested_profile_repository_rejects_untracked_package_entries(self):
        with tempfile.TemporaryDirectory() as raw_repo, tempfile.TemporaryDirectory() as raw_work:
            repo = Path(raw_repo)
            roots = self._expanded_profiles(repo, count=1)
            prepared = profile_install.prepare_profile_root(roots[0], source=str(roots[0]), source_sha256=None)
            manifest = {'schema': 'bbk.language-profiles-repository-manifest.v1', 'status': 'PASS', 'profile_count': 1, 'profiles': [{'id': prepared.profile_id, 'version': prepared.version, 'package': prepared.package_name, 'path': f'packages/{roots[0].name}', 'root_sha256': prepared.root_sha256}]}
            (repo / 'REPOSITORY-MANIFEST.json').write_text(json.dumps(manifest), encoding='utf-8')
            (repo / 'packages' / 'forgotten-profile').mkdir()
            with self.assertRaisesRegex(profile_install.ProfileInstallError, 'untracked'):
                profile_install.prepare_profile_sources([repo], temp_root=Path(raw_work))


    def test_windows_short_name_expansion_is_deterministic_for_missing_leaf_paths(self):
        short_parent = r'C:\Users\TOMBST~1\AppData\Local\Temp'
        long_parent = r'C:\Users\Tombstone\AppData\Local\Temp'
        pending = short_parent + r'\bbk-pending\agent.toml'
        expanded = path_compat._expand_existing_windows_prefix(
            pending,
            exists=lambda value: value == short_parent,
            long_name=lambda value: long_parent if value == short_parent else value,
        )
        self.assertEqual(expanded, long_parent + r'\bbk-pending\agent.toml')

    def test_portable_path_keys_reject_windows_case_and_separator_aliases_on_every_host(self):
        forward = 'C:/tmp/shared.md'
        backward = r'c:\tmp\shared.md'
        self.assertEqual(
            path_compat.portable_path_key(forward),
            path_compat.portable_path_key(backward),
        )
        with self.assertRaises(install.InstallError):
            install.validate_install_plan({
                'files': [
                    {'path': forward, 'sha256': 'a', 'source': 'one'},
                    {'path': backward, 'sha256': 'b', 'source': 'two'},
                ]
            })

    def test_physical_path_keys_collapse_directory_aliases_before_install_preflight(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            target = root / 'physical-target'
            target.mkdir()
            alias = root / 'alias-target'
            try:
                alias.symlink_to(target, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f'directory symlinks unavailable on this host: {exc}')
            target_file = target / 'same-file.txt'
            alias_file = alias / 'same-file.txt'
            assert_same_path(self, target_file, alias_file)
            records = []
            planned = {}
            backups = root / 'backups'
            install.install_bytes(
                b'first', target_file, source='first', force=False, dry_run=True,
                backup_root=backups, records=records, planned=planned,
            )
            with self.assertRaisesRegex(install.InstallError, 'collision'):
                install.install_bytes(
                    b'second', alias_file, source='second', force=False, dry_run=True,
                    backup_root=backups, records=records, planned=planned,
                )

    def test_test_runner_auto_mode_pools_on_windows_and_preserves_explicit_parallel_requests(self):
        self.assertEqual(
            run_tests.resolve_execution_mode('auto', jobs=0, platform_name='nt'),
            'pooled',
        )
        self.assertEqual(
            run_tests.resolve_execution_mode('auto', jobs=0, platform_name='posix'),
            'isolated',
        )
        self.assertEqual(
            run_tests.resolve_execution_mode('auto', jobs=4, platform_name='nt'),
            'pooled',
        )
        self.assertEqual(
            run_tests.resolve_execution_mode('batch', jobs=4, platform_name='nt'),
            'batch',
        )
        self.assertEqual(run_tests.automatic_parallel_jobs(4), 3)
        self.assertEqual(run_tests.automatic_parallel_jobs(8), 4)
        self.assertEqual(run_tests.automatic_parallel_jobs(12), 6)
        self.assertEqual(run_tests.automatic_parallel_jobs(32), 6)

    def test_duration_aware_sharding_prefers_measured_cost_over_source_size(self):
        files = [Path('tests/test_a.py'), Path('tests/test_b.py'), Path('tests/test_c.py')]
        groups = run_tests.partition_test_files(
            files,
            2,
            duration_weights={
                'test_a.py': 10.0,
                'test_b.py': 6.0,
                'test_c.py': 4.0,
            },
        )
        self.assertEqual(groups, [[files[0]], [files[1], files[2]]])

    def test_test_profiles_keep_release_coverage_and_exclude_only_declared_standard_cases(self):
        ordinary = 'test_core_contracts.SomeTests.test_behavior'
        release_only = next(iter(sorted(test_profiles.RELEASE_ONLY)))
        self.assertTrue(test_profiles.selected(ordinary, 'fast') is False)
        self.assertTrue(test_profiles.selected(ordinary, 'standard'))
        self.assertTrue(test_profiles.selected(ordinary, 'release'))
        self.assertFalse(test_profiles.selected(release_only, 'standard'))
        self.assertTrue(test_profiles.selected(release_only, 'release'))
        fast_contract = 'test_contract_package_v1.ContractPackageV1Tests.test_all_nineteen_roles_have_one_normalized_contract'
        self.assertTrue(test_profiles.selected(fast_contract, 'fast'))

    def test_timing_report_and_duration_cache_are_package_external_and_machine_readable(self):
        with tempfile.TemporaryDirectory() as raw:
            cache = Path(raw) / 'cache'
            with mock.patch.dict(os.environ, {'BBK_TEST_CACHE_DIR': str(cache)}):
                report_path = run_tests.default_timing_report_path()
                assert_same_path(self, report_path, cache / 'latest.json')
                report = {
                    'schema': 'bbk.test-run.v1',
                    'groups': [{
                        'modules': ['test_example.py'],
                        'duration_seconds': 2.5,
                        'status': 'PASS',
                    }],
                }
                run_tests._store_run_report(report, report_path)
                run_tests.update_duration_cache(report)
                self.assertEqual(json.loads(report_path.read_text(encoding='utf-8'))['schema'], 'bbk.test-run.v1')
                cache_value = json.loads(run_tests.duration_cache_path().read_text(encoding='utf-8'))
                self.assertEqual(cache_value['modules']['test_example.py'], 2.5)
                assert_different_path(self, report_path.parent, m8_ROOT)

    def test_pooled_runner_uses_bounded_multi_module_processes(self):
        with tempfile.TemporaryDirectory(dir=m8_ROOT) as raw_root:
            root = Path(raw_root)
            files = []
            for index, size in enumerate((900, 800, 700, 600, 500), start=1):
                path = root / f'test_{index}.py'
                path.write_text('#' * size, encoding='utf-8')
                files.append(path)

            calls = []

            def fake_execute(group, *, label, **kwargs):
                calls.append((tuple(group), label, kwargs))
                count = len(group)
                return run_tests.SuiteResult(
                    label,
                    0,
                    f'Ran {count} tests in 0.001s\n\nOK\n',
                    count,
                    (),
                )

            stream = io.StringIO()
            with mock.patch.object(run_tests, 'execute_modules', side_effect=fake_execute):
                code = run_tests.run_test_pool(
                    files,
                    quiet=True,
                    jobs=2,
                    stream=stream,
                    heartbeat_seconds=0,
                )

        self.assertEqual(code, 0)
        self.assertEqual(len(calls), 2)
        assigned = [path for group, _, _ in calls for path in group]
        self.assertEqual(sorted(assigned), sorted(files))
        self.assertTrue(any(len(group) > 1 for group, _, _ in calls))
        self.assertTrue(all(kwargs['quiet'] for _, _, kwargs in calls))
        output = stream.getvalue()
        self.assertIn('5 unittest modules in 2 multi-module Python processes', output)
        self.assertIn('Test modules discovered: 5; Python test processes: 2', output)
        self.assertIn('Tests reported: 5', output)

    def test_batch_runner_uses_one_python_process_for_all_discovered_modules(self):
        files = [Path('tests/test_a.py'), Path('tests/test_b.py')]
        result = run_tests.SuiteResult(
            'test*.py',
            0,
            'Ran 2 tests in 0.001s\n\nOK (skipped=1)\n',
            2,
            (),
            1,
        )
        stream = io.StringIO()
        with mock.patch.object(run_tests, 'execute_discovered', return_value=result) as execute:
            code = run_tests.run_test_batch(
                files,
                pattern='test*.py',
                quiet=True,
                stream=stream,
            )
        self.assertEqual(code, 0)
        execute.assert_called_once()
        output = stream.getvalue()
        self.assertIn('Running 2 unittest modules in one Python process', output)
        self.assertIn('Test modules discovered: 2; Python test processes: 1', output)
        self.assertIn('Skipped: 1', output)

    def test_native_windows_probe_and_ci_workflow_are_release_surfaces(self):
        workflow = m8_ROOT / '.github' / 'workflows' / 'windows-verification.yml'
        probe = m8_ROOT / 'tools' / 'windows_compat.py'
        helper = m8_ROOT / 'tools' / 'path_compat.py'
        self.assertTrue(workflow.is_file())
        self.assertTrue(probe.is_file())
        self.assertTrue(helper.is_file())
        workflow_text = workflow.read_text(encoding='utf-8')
        for expected in ('windows-latest', '3.11', '3.13', 'cp1252:strict', 'PYTHONUTF8', 'test_unicode_initialization_examples_and_uninitialized_status_are_truthful', 'windows_compat.py', '--all --profile release --require-node'):
            self.assertIn(expected, workflow_text)
        development = (m8_ROOT / 'docs' / 'DEVELOPMENT.md').read_text(encoding='utf-8')
        for expected in ('Windows-native compatibility', 'TOMBST~1', 'NOT_APPLICABLE', 'windows-verification.yml'):
            self.assertIn(expected, development)
        report = windows_compat.probe()
        expected = 'PASS' if os.name == 'nt' else 'NOT_APPLICABLE'
        self.assertEqual(report['status'], expected, report)

    def test_test_runner_emits_suite_progress_and_quiet_heartbeat(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            tests = root / 'tests'
            tests.mkdir()
            test_file = tests / 'test_slow.py'
            test_file.write_text(textwrap.dedent('                    import time\n                    import unittest\n\n                    class SlowTests(unittest.TestCase):\n                        def test_waits(self):\n                            time.sleep(0.20)\n                            self.assertTrue(True)\n                    '), encoding='utf-8')
            stream = io.StringIO()
            with mock.patch.object(run_tests, 'ROOT', root), mock.patch.object(run_tests, 'TESTS', tests):
                code = run_tests.run_test_files([test_file], verbose=True, stream=stream, heartbeat_seconds=0.05)
            output = stream.getvalue()
        self.assertEqual(code, 0)
        self.assertIn('==> [1/1] test_slow.py', output)
        self.assertIn('test_slow.py is still running', output)
        self.assertIn('<== [1/1] test_slow.py: PASS', output)
        self.assertIn('Completed 1/1 unittest suites', output)

    def test_parallel_runner_heartbeat_names_the_current_test(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            tests = root / 'tests'
            tests.mkdir()
            slow = tests / 'test_visible_slow.py'
            slow.write_text(textwrap.dedent('''
                    import time
                    import unittest

                    class VisibleSlowTests(unittest.TestCase):
                        def test_current_operation_is_visible(self):
                            time.sleep(0.25)
                    '''), encoding='utf-8')
            fast = tests / 'test_visible_fast.py'
            fast.write_text(textwrap.dedent('''
                    import unittest

                    class VisibleFastTests(unittest.TestCase):
                        def test_finishes(self):
                            self.assertTrue(True)
                    '''), encoding='utf-8')
            stream = io.StringIO()
            with mock.patch.object(run_tests, 'ROOT', root), mock.patch.object(run_tests, 'TESTS', tests):
                code = run_tests.run_test_files(
                    [fast, slow],
                    verbose=True,
                    stream=stream,
                    heartbeat_seconds=0.05,
                    suite_timeout=5,
                    jobs=2,
                )
            output = stream.getvalue()
        self.assertEqual(code, 0, output)
        self.assertIn('test_visible_slow.py', output)
        self.assertIn('test_current_operation_is_visible', output)
        self.assertIn('hard timeout 5s', output)

    def test_suite_children_cannot_read_the_developer_console(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            tests = root / 'tests'
            tests.mkdir()
            test_file = tests / 'test_stdin.py'
            test_file.write_text(textwrap.dedent('''
                    import unittest

                    class StdinIsolationTests(unittest.TestCase):
                        def test_stdin_is_closed(self):
                            with self.assertRaises(EOFError):
                                input('this prompt must never reach the developer console: ')
                    '''), encoding='utf-8')
            with mock.patch.object(run_tests, 'ROOT', root), mock.patch.object(run_tests, 'TESTS', tests):
                result = run_tests.execute_discovered(
                    test_file.name,
                    verbose=True,
                    timeout=5,
                    heartbeat_seconds=0,
                )
        self.assertTrue(result.passed, result.output)
        self.assertIn('test_stdin_is_closed', result.output)

    def test_test_runner_survives_cp1252_console_and_non_utf8_child_bytes(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            tests = root / 'tests'
            tests.mkdir()
            test_file = tests / 'test_unicode_output.py'
            test_file.write_text(textwrap.dedent('''
                    import sys
                    import unittest

                    class UnicodeOutputTests(unittest.TestCase):
                        def test_output(self):
                            print("Résumé → 🚀", flush=True)
                            sys.stdout.buffer.write(b"raw-invalid:\\x81\\n")
                            sys.stdout.buffer.flush()
                            self.assertTrue(True)
                    '''), encoding='utf-8')
            raw_output = io.BytesIO()
            stream = io.TextIOWrapper(
                raw_output,
                encoding='cp1252',
                errors='strict',
                write_through=True,
            )
            with mock.patch.object(run_tests, 'ROOT', root), mock.patch.object(run_tests, 'TESTS', tests):
                code = run_tests.run_test_files([test_file], verbose=True, stream=stream)
            stream.flush()
            output = raw_output.getvalue().decode('cp1252')
            stream.detach()
        self.assertEqual(code, 0)
        self.assertIn('Résumé', output)
        self.assertIn('\\u2192', output)
        self.assertIn('\\U0001f680', output)
        self.assertIn('raw-invalid:\\x81', output)
        self.assertNotIn('\ufffd', output)

    def test_output_stream_failure_terminates_child_before_capture_cleanup(self):

        class BrokenStream(io.StringIO):

            def write(self, value):
                if value:
                    raise RuntimeError('deliberate output-stream failure')
                return 0

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            tests = root / 'tests'
            tests.mkdir()
            test_file = tests / 'test_blocking.py'
            test_file.write_text(textwrap.dedent('''
                    import time
                    import unittest

                    class BlockingTests(unittest.TestCase):
                        def test_waits(self):
                            print("child ready", flush=True)
                            time.sleep(30)
                    '''), encoding='utf-8')
            capture = root / 'known-capture.log'

            def fixed_mkstemp(*args, **kwargs):
                fd = os.open(capture, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
                return fd, str(capture)

            with mock.patch.object(run_tests, 'ROOT', root), mock.patch.object(run_tests, 'TESTS', tests), mock.patch.object(run_tests.tempfile, 'mkstemp', side_effect=fixed_mkstemp):
                with self.assertRaisesRegex(RuntimeError, 'deliberate output-stream failure'):
                    run_tests.execute_discovered(
                        test_file.name,
                        verbose=True,
                        stream=BrokenStream(),
                        timeout=10,
                        heartbeat_seconds=0,
                    )
            self.assertFalse(capture.exists())

    def test_windows_process_tree_cleanup_bounds_taskkill(self):
        class FakeProcess:
            pid = 4242

            def __init__(self):
                self.killed = False

            def poll(self):
                return None

            def kill(self):
                self.killed = True

            def wait(self, timeout=None):
                if self.killed:
                    return -9
                raise subprocess.TimeoutExpired('fake-suite', timeout)

        process = FakeProcess()
        with mock.patch.object(run_tests.os, 'name', 'nt'), mock.patch.object(
            run_tests.subprocess,
            'run',
            side_effect=subprocess.TimeoutExpired('taskkill', 10),
        ) as taskkill:
            run_tests._terminate_process_tree(process)
        self.assertTrue(process.killed)
        self.assertEqual(taskkill.call_args.kwargs['timeout'], 10)
        self.assertIs(taskkill.call_args.kwargs['stdin'], subprocess.DEVNULL)

    def test_capture_cleanup_retries_and_suppresses_windows_sharing_violation(self):
        capture = Path('bbk-test-suite-locked.log')
        locked = PermissionError(32, 'file is being used by another process')
        with mock.patch.object(
            Path,
            'unlink',
            side_effect=[locked, locked, None],
        ) as unlink, mock.patch.object(run_tests.time, 'sleep') as sleep:
            run_tests._remove_capture_file(capture, attempts=3, delay=0.01)
        self.assertEqual(unlink.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

        with mock.patch.object(
            Path,
            'unlink',
            side_effect=locked,
        ) as unlink, mock.patch.object(run_tests.time, 'sleep') as sleep:
            run_tests._remove_capture_file(capture, attempts=2, delay=0.01)
        self.assertEqual(unlink.call_count, 2)
        self.assertEqual(sleep.call_count, 1)

    def test_ordered_verifier_survives_cp1252_console_with_unicode_child_output(self):
        raw_output = io.BytesIO()
        stream = io.TextIOWrapper(
            raw_output,
            encoding='cp1252',
            errors='strict',
            write_through=True,
        )
        spec = verify_all.CheckSpec(
            'Unicode output probe',
            (sys.executable, '-c', 'print("Résumé → 🚀")'),
        )
        result = verify_all.execute_step(spec, stream=stream)
        stream.flush()
        output = raw_output.getvalue().decode('cp1252')
        stream.detach()
        self.assertTrue(result.passed)
        self.assertIn('Résumé → 🚀', result.output)
        self.assertIn('Résumé', output)
        self.assertIn('\\u2192', output)
        self.assertIn('\\U0001f680', output)

    def test_install_verification_gate_survives_cp1252_console_mirroring(self):
        observed = {}

        def fake_popen(command, **kwargs):
            observed['command'] = list(command)
            observed.update(kwargs)
            report_path = Path(command[command.index('--report-file') + 1])
            report_path.write_text(json.dumps({
                'schema': 'bbk.verification-report.v1',
                'status': 'PASS',
                'checks': [],
                'checks_run': 0,
                'checks_expected': 0,
                'exit_code': 0,
            }), encoding='utf-8')
            return types.SimpleNamespace(
                stdout=io.StringIO('Résumé → 🚀\n'),
                wait=lambda: 0,
            )

        raw_output = io.BytesIO()
        stream = io.TextIOWrapper(
            raw_output,
            encoding='cp1252',
            errors='strict',
            write_through=True,
        )
        with mock.patch.object(install_tool.subprocess, 'Popen', side_effect=fake_popen), contextlib.redirect_stdout(stream):
            report = install_tool.run_verification_gate(
                failfast=False,
                require_node=False,
                echo=True,
                profile='omp',
                jobs=1,
            )
        stream.flush()
        output = raw_output.getvalue().decode('cp1252')
        stream.detach()
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(observed['encoding'], 'utf-8')
        self.assertEqual(observed['errors'], 'backslashreplace')
        self.assertEqual(observed['env']['PYTHONIOENCODING'], 'utf-8:backslashreplace')
        self.assertEqual(observed['command'][observed['command'].index('--profile') + 1], 'omp')
        self.assertEqual(observed['command'][observed['command'].index('--jobs') + 1], '1')
        self.assertIn('Résumé', output)
        self.assertIn('\\u2192', output)
        self.assertIn('\\U0001f680', output)

    def test_install_progress_reports_phase_file_counts_and_completion(self):
        stream = io.StringIO()
        progress = install.InstallProgress(enabled=True, interval_files=2, heartbeat_seconds=0)
        with contextlib.redirect_stdout(stream):
            progress.start('Installing', total=2)
            progress.advance(Path('one.txt'), 'create')
            progress.advance(Path('two.txt'), 'unchanged')
            progress.finish()
        output = stream.getvalue()
        self.assertIn('==> Installing (2 files)', output)
        self.assertIn('1/2 files processed', output)
        self.assertIn('2/2 files processed', output)
        self.assertIn('<== Installing: PASS', output)

    def test_current_docs_cover_unzipped_sources_progress_and_repository_native_workflow(self):
        paths = ['README.md', 'docs/INSTALL.md', 'docs/LANGUAGE-PROFILES.md', 'docs/DEVELOPMENT.md']
        combined = '\n'.join((m8_ROOT / path).read_text(encoding='utf-8') for path in paths)
        for phrase in ['REPOSITORY-MANIFEST.json', 'bbk-language-profiles', 'still running', '--language-profiles', 'No repository-extraction script']:
            self.assertIn(phrase, combined)
        self.assertNotIn('tools/extract_git_repositories.py', combined)
        self.assertFalse((m8_ROOT / 'tools' / 'extract_git_repositories.py').exists())

# Deterministic fast/standard/release selection used by tools/run_tests.py.
from tests._test_profiles import load_profiled_tests as load_tests


class SharedPathAssertionSupportTests(unittest.TestCase):
    """Keep filesystem-identity assertions centralized and alias-safe."""

    def test_shared_helpers_collapse_aliases_in_direct_and_notification_paths(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            target = root / 'physical-project'
            target.mkdir()
            alias = root / 'project-alias'
            try:
                alias.symlink_to(target, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f'directory aliases unavailable on this host: {exc}')

            assert_same_path(self, alias, target)
            assert_labeled_path(
                self,
                [f'Scope: project\nProject: {target.resolve()}'],
                'Project',
                alias,
                required_text='Scope: project',
            )

    def test_shared_helper_failure_identifies_raw_and_canonical_spellings(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            left = root / 'left'
            right = root / 'right'
            left.mkdir()
            right.mkdir()
            with self.assertRaisesRegex(AssertionError, r'raw=.*canonical=.*exists='):
                assert_same_path(self, left, right)

    def test_identity_sensitive_assertions_use_shared_helpers(self):
        """Prevent regressions to raw path-spelling comparisons in test code."""
        tests_root = Path(__file__).resolve().parent
        violations = [
            finding
            for path in sorted(tests_root.glob('test_*.py'))
            for finding in find_unsafe_path_assertions(path)
        ]
        self.assertEqual(violations, [], '\n'.join(violations))

    def test_symlink_fixtures_are_capability_guarded(self):
        """Prevent API-presence checks from standing in for host capability."""
        tests_root = Path(__file__).resolve().parent
        violations = [
            finding
            for path in sorted(tests_root.glob('test_*.py'))
            for finding in find_unguarded_symlink_creations(path)
        ]
        self.assertEqual(violations, [], '\n'.join(violations))

    def test_symlink_helper_converts_permission_denial_to_skip(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            with mock.patch.object(Path, 'symlink_to', side_effect=PermissionError('privilege unavailable')):
                with self.assertRaises(unittest.SkipTest):
                    create_symlink_or_skip(self, root / 'link', root / 'target')
