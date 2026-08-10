"""Extracted installation regression tests."""
from __future__ import annotations

# Historical source: test_alpha11_7_git_repositories.py
# ---------------------------------------------------------------------------
import importlib.util
import importlib
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import types
import unittest
from pathlib import Path
from unittest import mock
m8_ROOT = Path(__file__).resolve().parents[1]
m8_TOOLS = m8_ROOT / 'tools'
if str(m8_TOOLS) not in sys.path:
    sys.path.insert(0, str(m8_TOOLS))

def m1_load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, m8_ROOT / relative_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'cannot load {relative_path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

import install
import path_compat
import profile_install
import run_tests
import windows_compat
import install as install_tool
import verify_all
from tests import _test_profiles as test_profiles
from tests._path_support import assert_different_path, assert_same_path, assert_same_path_sequence
m8_build_release = m1_load_module('bbk_build_release_alpha13', 'tools/build_release.py')
m8_BUNDLE = m8_ROOT / 'bundled-language-profiles'
m8_RELEASE = json.loads((m8_BUNDLE / 'RELEASE-MANIFEST.json').read_text(encoding='utf-8'))
m5_EXPECTED_PROFILES = sorted((m8_RELEASE.get('profileVersions') or {}).keys())

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
        self.assertEqual([item.profile_id for item in prepared], m5_EXPECTED_PROFILES)
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
        self.assertEqual(run_tests.automatic_parallel_jobs(4, platform_name='posix'), 3)
        self.assertEqual(run_tests.automatic_parallel_jobs(8, platform_name='posix'), 4)
        self.assertEqual(run_tests.automatic_parallel_jobs(12, platform_name='posix'), 6)
        self.assertEqual(run_tests.automatic_parallel_jobs(32, platform_name='posix'), 6)
        self.assertEqual(run_tests.automatic_parallel_jobs(4, platform_name='nt'), 3)
        self.assertEqual(run_tests.automatic_parallel_jobs(8, platform_name='nt'), 4)
        self.assertEqual(run_tests.automatic_parallel_jobs(32, platform_name='nt'), 6)
        self.assertEqual(run_tests.automatic_parallel_jobs(32, platform_name='posix'), 6)

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

    def test_duration_partition_keeps_a_dominant_module_in_its_own_pool(self):
        files = [Path('tests/test_short.py'), Path('tests/test_dominant.py'), Path('tests/test_other.py')]
        weights = {'test_dominant.py': 100.0, 'test_short.py': 1.0, 'test_other.py': 1.0}
        groups = run_tests.partition_test_files(
            files, 2, duration_weights=weights
        )
        self.assertEqual(groups, [[files[1]], [files[0], files[2]]])

    def test_duration_seed_merges_windows_modules_over_generic_seed(self):
        with tempfile.TemporaryDirectory() as raw:
            seed = Path(raw) / 'test-durations.json'
            seed.write_text(json.dumps({
                'schema': 'bbk.test-duration-seed.v1',
                'modules': {'generic.py': 1.0},
                'platforms': {'windows': {
                    'provenance': 'native probe',
                    'modules': {'generic.py': 3.0, 'windows.py': 4.0},
                }},
            }), encoding='utf-8')
            self.assertEqual(
                run_tests.load_duration_weights(seed, platform_name='nt'),
                {'generic.py': 3.0, 'windows.py': 4.0},
            )
            self.assertEqual(
                run_tests.load_duration_weights(seed, platform_name='posix'),
                {'generic.py': 1.0},
            )

    def test_duration_cache_updates_only_passing_single_module_groups(self):
        with tempfile.TemporaryDirectory() as raw:
            cache = Path(raw) / 'module-durations.json'
            seed = Path(raw) / 'test-durations.json'
            seed.write_text('{}', encoding='utf-8')
            report = {
                'groups': [
                    {'modules': ['pass.py'], 'duration_seconds': 2.0, 'status': 'PASS'},
                    {'modules': ['fail.py'], 'duration_seconds': 9.0, 'status': 'FAIL'},
                ]
            }
            with mock.patch.object(run_tests, 'duration_cache_path', return_value=cache):
                run_tests.update_duration_cache(report, seed_path=seed)
            value = json.loads(cache.read_text(encoding='utf-8'))
            self.assertEqual(value['modules'], {'pass.py': 2.0})
            self.assertNotIn('fail.py', value['modules'])

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

    def test_duration_cache_is_bound_to_the_exact_packaged_seed(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            seed = root / 'test-durations.json'
            cache = root / 'module-durations.json'
            seed.write_text(
                json.dumps({'schema': 'bbk.test-duration-seed.v1', 'modules': {'test_seed.py': 1.0}}),
                encoding='utf-8',
            )
            cache.write_text(
                json.dumps({
                    'schema': 'bbk.test-duration-cache.v1',
                    'seed_sha256': run_tests.duration_seed_sha256(seed),
                    'modules': {'test_cached.py': 9.0},
                }),
                encoding='utf-8',
            )
            with mock.patch.object(run_tests, 'duration_cache_path', return_value=cache):
                self.assertEqual(
                    run_tests.load_duration_weights(seed),
                    {'test_seed.py': 1.0, 'test_cached.py': 9.0},
                )
                seed.write_text(
                    json.dumps({'schema': 'bbk.test-duration-seed.v1', 'modules': {'test_seed.py': 2.0}}),
                    encoding='utf-8',
                )
                self.assertEqual(
                    run_tests.load_duration_weights(seed),
                    {'test_seed.py': 2.0},
                    'timings from an older package seed must not override new shard weights',
                )

    def test_duration_cache_rejects_a_different_recorded_platform(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            seed = root / 'test-durations.json'
            cache = root / 'module-durations.json'
            seed.write_text(
                json.dumps({'schema': 'bbk.test-duration-seed.v1', 'modules': {'test_seed.py': 1.0}}),
                encoding='utf-8',
            )
            cache.write_text(
                json.dumps({
                    'schema': 'bbk.test-duration-cache.v1',
                    'seed_sha256': run_tests.duration_seed_sha256(seed),
                    'platform': 'windows',
                    'modules': {'test_cached.py': 9.0},
                }),
                encoding='utf-8',
            )
            with mock.patch.object(run_tests, 'duration_cache_path', return_value=cache):
                self.assertEqual(
                    run_tests.load_duration_weights(seed, platform_name='posix'),
                    {'test_seed.py': 1.0},
                )
                self.assertEqual(
                    run_tests.load_duration_weights(seed, platform_name='nt'),
                    {'test_seed.py': 1.0, 'test_cached.py': 9.0},
                )

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
            'batch[test_a.py, test_b.py]',
            0,
            'Ran 2 tests in 0.001s\n\nOK (skipped=1)\n',
            2,
            (),
            1,
        )
        stream = io.StringIO()
        with mock.patch.object(run_tests, 'execute_modules', return_value=result) as execute:
            code = run_tests.run_test_batch(
                files,
                pattern='test*.py',
                quiet=True,
                stream=stream,
            )
        self.assertEqual(code, 0)
        execute.assert_called_once()
        called_files = execute.call_args.args[0]
        self.assertEqual(called_files, files)
        self.assertEqual(execute.call_args.kwargs['label'], 'batch[test_a.py, test_b.py]')
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
                    # Process startup can exceed five seconds on a saturated
                    # Windows or CI host even though the fixture itself sleeps
                    # for only 250 ms. Keep this runner self-test deterministic
                    # under release-suite contention without weakening the
                    # heartbeat assertion.
                    suite_timeout=15,
                    jobs=2,
                )
            output = stream.getvalue()
        self.assertEqual(code, 0, output)
        self.assertIn('test_visible_slow.py', output)
        self.assertIn('test_current_operation_is_visible', output)
        self.assertIn('hard timeout 15s', output)

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

    def test_structured_report_sidecar_is_cleaned_on_child_error(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            tests = root / "tests"
            tests.mkdir()
            test_file = tests / "test_broken_sidecar.py"
            test_file.write_text(
                "print('BBK_TEST_REPORT_JSON:{\"selected\":[\"nested.fake\"],\"executed\":[\"nested.fake\"],\"skipped\":[],\"not_run\":[]}', flush=True)\n"
                "raise RuntimeError('load failure')\n",
                encoding="utf-8",
            )
            removed: list[Path] = []
            original_remove = run_tests._remove_capture_file

            def record_remove(path, **kwargs):
                removed.append(Path(path))
                return original_remove(path, **kwargs)

            with mock.patch.object(run_tests, "ROOT", root), mock.patch.object(run_tests, "TESTS", tests), mock.patch.object(run_tests, "_remove_capture_file", side_effect=record_remove):
                result = run_tests.execute_discovered(test_file.name, stream=io.StringIO(), timeout=10)
            self.assertFalse(result.passed)
            self.assertNotIn("nested.fake", result.selected_ids)
            self.assertEqual({path.suffix for path in removed}, {".log", ".json"})
            self.assertTrue(all(not path.exists() for path in removed))

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
        # Dependency preflight may itself launch subprocesses.  Keep this
        # verifier-specific fake scoped to the actual gate child so the test
        # still exercises CP1252 mirroring without intercepting preflight.
        with mock.patch.object(
            install_tool.dependency_tool,
            'verification_environment',
            return_value=dict(os.environ, PYTHONIOENCODING='utf-8:backslashreplace'),
        ), mock.patch.object(install_tool.subprocess, 'Popen', side_effect=fake_popen), contextlib.redirect_stdout(stream):
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

