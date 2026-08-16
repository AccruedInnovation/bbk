"""Extracted installation regression tests."""
from __future__ import annotations

# Historical source: test_alpha10_1_entry_setup.py
# ---------------------------------------------------------------------------
import hashlib
import ast
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
    source_profile.update({'id': profile_id, 'name': f'Sample {profile_id} profile', 'package': package_name, 'version': version, 'maturity': 'qualified-fixture', 'requires': {'bbk_minimum': '0.1.0-alpha.8', 'python_minimum': '3.11'}, 'installation': {'cli': 'tools/profile.py', 'skill_root': 'skills', 'omp_extension': 'omp/extension'}, 'skills': [{'id': profile_id, 'kind': 'router', 'path': f'skills/{profile_id}/SKILL.md'}]})
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
        self.assertEqual(version, '0.1.0-alpha.17.0.2.1')
        self.assertEqual(json.loads((m4_ROOT / 'spec' / 'roles.json').read_text(encoding='utf-8'))['package_version'], version)
        self.assertNotIn('package_version', json.loads((m4_ROOT / 'spec' / 'model-routing.json').read_text(encoding='utf-8')))
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
                  enum: values => chain(), array: value => chain(), any: chain }};
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
                if (commands.size !== 48) throw new Error(`commands=${{commands.size}}`);
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
                  'bbk_reviewer', 'bbk_validator_orchestrator', '/bbk:exit', '### Compiled primary procedure: `bbk`',
                  '### Compiled procedure: `bbk-context-routing`', '`task`', '`hub`/IRC', 'Main']) {{
                  if (!joined.includes(expected)) throw new Error(`missing ${{expected}}`);
                }}
                for (const excluded of ['OMP DEFAULT', '.codex/AGENTS.md', 'one-liner solutions']) {{
                  if (joined.includes(excluded)) throw new Error(`retained ${{excluded}}`);
                }}
                if (entries.length !== 3 || entries[1][0] !== 'bbk-effective-prompt-receipt' || entries[1][1].status !== 'REPLACED') throw new Error('effective prompt receipt missing');
                if (entries[2][0] !== 'bbk-prompt-compilation-event' || entries[2][1].schema !== 'bbk.prompt-compilation-event.v1' || entries[2][1].event !== 'PROMPT_COMPILED') throw new Error('typed prompt compilation event missing');
                await commands.get('bbk').handler('Implement the accepted baseline', ctx);
                if (messages.length !== 1 || messages[0][0] !== 'Implement the accepted baseline') throw new Error('request was not forwarded verbatim');
                if (messages[0][0].includes('bbk_root_wayfinder')) throw new Error('mode prompt leaked into user message');
                console.log(JSON.stringify({{commands: commands.size, messages: messages.length, entries: entries.length, replacementLength: joined.length}}));
            '''), encoding='utf-8')
            result = subprocess.run([shutil.which('node') or 'node', script], cwd=m4_ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', check=False, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            value = json.loads(result.stdout)
            self.assertEqual(value['commands'], 48)
            self.assertEqual(value['messages'], 1)
            self.assertEqual(value['entries'], 3)

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
            attempt = root.parent / f'{root.name}-attempt'
            for name in ('evidence', 'temp', 'cache', 'pycache'):
                (attempt / name).mkdir(parents=True)
            qualified = os.pathsep.join((str(m4_ROOT), str(m4_ROOT / 'tools'), r'C:\Users\Tombstone\.cache\bbk\tooling\jsonschema-4.25.1\Lib\site-packages'))
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
                        'BBK_LAUNCH_RECORD_ROOT': str(attempt / 'evidence'),
                        'BBK_NATIVE_EVIDENCE_ROOT': str(attempt / 'evidence'),
                        'BBK_TEST_CACHE_DIR': str(attempt / 'cache'),
                        'TEMP': str(attempt / 'temp'),
                        'TMP': str(attempt / 'temp'),
                        'TMPDIR': str(attempt / 'temp'),
                        'PYTHONPYCACHEPREFIX': str(attempt / 'pycache'),
                        'PYTHONPATH': qualified,
                        'BBK_QUALIFIED_PYTHONPATH': qualified,
                        'PYTHONDONTWRITEBYTECODE': '1',
                        'PYTHONNOUSERSITE': '1',
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
        self.assertEqual(values[values.index('--verification-profile') + 1], 'omp')
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

    def test_windows_console_confirmation_uses_native_key_reader(self):
        output = io.StringIO()
        keys = iter(["n", "\r"])
        with mock.patch.object(install_tool.sys, "stdout", output):
            self.assertEqual(
                install_tool._read_windows_console_line(read_key=lambda: next(keys)),
                "n",
            )
        self.assertEqual(output.getvalue(), "n\n")

        existing = {
            "version": "0.1.0-alpha.17.0.2.1",
            "harnesses": ["omp", "codex"],
            "file_count": 123,
            "manifest_path": Path("C:/Temp/install-manifest.json"),
        }
        args = install_tool.build_parser().parse_args(
            ["install", "--scope", "user", "--omp", "--no-language-profiles"]
        )
        interactive = io.StringIO()
        interactive.isatty = lambda: True
        with (
            mock.patch.object(install_tool.sys, "stdin", interactive),
            mock.patch.object(install_tool.sys, "stdout", io.StringIO()),
            mock.patch.object(install_tool, "_native_windows_console_input", return_value=True),
            mock.patch.object(install_tool, "_read_windows_console_line", return_value="n") as reader,
            mock.patch("builtins.input", side_effect=AssertionError("text input path must not run")),
        ):
            self.assertEqual(install_tool.choose_existing_install_action(args, existing), "keep")
        reader.assert_called_once_with()

        fallback_output = io.StringIO()
        with (
            mock.patch.object(install_tool.sys, "stdin", interactive),
            mock.patch.object(install_tool.sys, "stdout", fallback_output),
            mock.patch.object(install_tool, "_native_windows_console_input", return_value=True),
            mock.patch.object(install_tool, "_read_windows_console_line", return_value=None),
            mock.patch("builtins.input", side_effect=AssertionError("text input path must not run")),
        ):
            self.assertEqual(install_tool.choose_existing_install_action(args, existing), "keep")
        self.assertIn("could not be read", fallback_output.getvalue())
        self.assertIn("--uninstall-existing", fallback_output.getvalue())

    def test_windows_console_detector_uses_kernel32_console_mode(self):
        stream = io.StringIO()

        class Kernel32:
            def __init__(self, mode_result=1):
                self.mode_result = mode_result
                self.handle_args = []

            def GetStdHandle(self, value):
                self.handle_args.append(value)
                return 123

            def GetConsoleMode(self, handle, mode):
                self.console_handle = handle
                return self.mode_result

        kernel = Kernel32()
        with (
            mock.patch.object(install_tool.os, "name", "nt"),
            mock.patch.object(install_tool.sys, "stdin", stream),
            mock.patch.object(install_tool.sys, "__stdin__", stream),
            mock.patch.object(install_tool.ctypes, "WinDLL", return_value=kernel, create=True),
        ):
            self.assertTrue(install_tool._native_windows_console_input())
        self.assertEqual(kernel.handle_args, [-10])
        self.assertEqual(kernel.console_handle, 123)

        with (
            mock.patch.object(install_tool.os, "name", "nt"),
            mock.patch.object(install_tool.sys, "stdin", stream),
            mock.patch.object(install_tool.sys, "__stdin__", stream),
            mock.patch.object(install_tool.ctypes, "WinDLL", side_effect=OSError("kernel32 unavailable"), create=True),
        ):
            self.assertFalse(install_tool._native_windows_console_input())

    def test_failed_native_console_probe_does_not_fall_back_to_blocking_prompt(self):
        class ConsoleStream(io.StringIO):
            def isatty(self) -> bool:
                return True

        stream = ConsoleStream()
        existing = {
            "version": "0.1.0-alpha.17.0.2.1",
            "harnesses": ["omp"],
            "file_count": 1,
            "manifest_path": Path("C:/Temp/install-manifest.json"),
        }
        args = install_tool.build_parser().parse_args(
            ["install", "--scope", "user", "--omp", "--no-language-profiles"]
        )
        output = io.StringIO()
        kernel = mock.Mock()
        kernel.GetStdHandle.return_value = 0  # detached/redirected stdin
        with (
            mock.patch.object(install_tool.os, "name", "nt"),
            mock.patch.object(install_tool.sys, "stdin", stream),
            mock.patch.object(install_tool.sys, "__stdin__", stream),
            mock.patch.object(install_tool.sys, "stdout", output),
            mock.patch.object(install_tool.ctypes, "WinDLL", return_value=kernel, create=True),
            mock.patch("builtins.input", side_effect=AssertionError("native probe must not use text input")),
        ):
            self.assertEqual(install_tool.choose_existing_install_action(args, existing), "keep")
        self.assertNotIn("[Y/n]", output.getvalue())

    def test_setup_install_preserves_interactive_stdin_for_confirmation(self):
        class InteractiveInput(io.StringIO):
            def isatty(self) -> bool:
                return True

        input_stream = InteractiveInput("n\n")
        output_stream = io.StringIO()
        observed = {}

        def fake_install_main(values):
            observed["values"] = list(values)
            observed["stdin"] = install_tool.sys.stdin
            observed["stdout"] = install_tool.sys.stdout
            return 0

        with (
            mock.patch.object(setup_tool.install_tool, "main", side_effect=fake_install_main),
            mock.patch.object(setup_tool.sys, "stdin", input_stream),
            mock.patch.object(setup_tool.sys, "stdout", output_stream),
        ):
            self.assertEqual(
                setup_tool.main(
                    ["--install", "--scope", "user", "--omp", "--no-language-profiles"]
                ),
                0,
            )
        self.assertIs(observed["stdin"], input_stream)
        self.assertIs(observed["stdout"], output_stream)
        self.assertIn("--omp", observed["values"])

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
            self.assertIn('Required router procedure: `sample`', registry_text)
            self.assertNotIn('package-source placeholder', registry_text)
            effective_registry = json.loads((base / 'data' / 'effective-language-profiles.json').read_text(encoding='utf-8'))
            self.assertEqual([item['id'] for item in effective_registry['profiles']], ['sample'])
            self.assertTrue((base / 'home' / '.omp' / 'agent' / 'extensions' / 'bbk-profile-sample' / 'index.js').is_file())
            self.assertTrue((base / 'bin' / ('profile.cmd' if os.name == 'nt' else 'profile')).is_file())
            registry_skill = base / 'home' / '.agents' / 'skills' / 'bbk-installed-profiles' / 'SKILL.md'
            self.assertTrue(registry_skill.is_file())
            registry_text = registry_skill.read_text(encoding='utf-8')
            self.assertIn('`sample@0.1.0-alpha.3`', registry_text)
            self.assertIn('Required router procedure: `sample`', registry_text)
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

