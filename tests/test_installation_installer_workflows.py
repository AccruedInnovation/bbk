"""Extracted installation regression tests."""
from __future__ import annotations

# Historical source: test_alpha11_1_bundled_release.py
# ---------------------------------------------------------------------------


import io
import importlib
import json
import os
import subprocess
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
from tests._path_support import assert_same_path_sequence
m5_BUNDLE = m5_ROOT / 'bundled-language-profiles'
m5_RELEASE = json.loads((m5_BUNDLE / 'RELEASE-MANIFEST.json').read_text(encoding='utf-8'))
m5_EXPECTED_PROFILE_VERSIONS = dict(sorted((m5_RELEASE.get('profileVersions') or {}).items()))
m5_EXPECTED_PROFILES = sorted(m5_EXPECTED_PROFILE_VERSIONS)

class Alpha111BundledReleaseTests(unittest.TestCase):

    @staticmethod
    def _predecessor_is_valid(profile, expected_package, expected_version):
        predecessor = profile.get('predecessor')
        if not isinstance(predecessor, dict):
            return False
        if predecessor.get('package') != expected_package:
            return False
        version = predecessor.get('version')
        if not isinstance(version, str) or not version:
            return False
        if version != expected_version:
            return True
        candidate = predecessor.get('candidate')
        if not isinstance(candidate, str) or candidate.count('@') != 1:
            return False
        candidate_id, revision = candidate.split('@')
        if not candidate_id or not revision or not revision.startswith('r') or not revision[1:].isdigit():
            return False
        successor_candidate = profile.get('successor_candidate')
        successor_revision = profile.get('successor_revision')
        if not isinstance(successor_candidate, str) or not isinstance(successor_revision, str):
            return False
        if candidate in {successor_candidate, f'{successor_candidate}@{successor_revision}'}:
            return False
        source_package = predecessor.get('source_package')
        source_prefix = f'packages/{expected_package}-{expected_version}-r'
        if not isinstance(source_package, str) or not source_package.startswith(source_prefix):
            return False
        if source_package[len(source_prefix):] != revision[1:]:
            return False
        for field in ('package_root_sha256', 'package_manifest_sha256'):
            value = predecessor.get(field)
            if not isinstance(value, str) or len(value) != 64 or any(char not in '0123456789abcdefABCDEF' for char in value):
                return False
        return True

    @classmethod
    def setUpClass(cls) -> None:
        cls._prepared_temp = tempfile.TemporaryDirectory(prefix='bbk-alpha111-profiles-')
        cls.prepared = profile_install.prepare_profile_sources([m5_BUNDLE], temp_root=Path(cls._prepared_temp.name))
        cls.by_id = {item.profile_id: item for item in cls.prepared}

    @classmethod
    def tearDownClass(cls) -> None:
        cls._prepared_temp.cleanup()

    def test_current_successor_is_repository_native_and_self_contained(self):
        self.assertEqual((m5_ROOT / 'VERSION').read_text(encoding='utf-8').strip(), '0.1.0-alpha.17.0.2.1')
        self.assertTrue((m5_ROOT / 'docs' / 'README.md').is_file())
        self.assertTrue((m5_ROOT / 'docs' / 'DEVELOPMENT.md').is_file())
        self.assertTrue((m5_ROOT / 'bundled-language-profiles' / 'packages').is_dir())
        self.assertFalse((m5_ROOT / 'tools' / 'extract_git_repositories.py').exists())
        self.assertFalse((m5_ROOT / 'docs' / 'GIT-REPOSITORIES.md').exists())


    def test_bundled_release_manifest_verifies_and_contains_declared_profiles(self):
        report = profile_install.verify_bundle_manifest(m5_BUNDLE)
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual([item.profile_id for item in self.prepared], m5_EXPECTED_PROFILES)
        self.assertEqual({item.profile_id: item.version for item in self.prepared}, m5_EXPECTED_PROFILE_VERSIONS)
        release = json.loads((m5_BUNDLE / 'RELEASE-MANIFEST.json').read_text(encoding='utf-8'))
        self.assertEqual(release.get('profileVersions'), m5_EXPECTED_PROFILE_VERSIONS)
        archives = sorted((m5_BUNDLE / 'packages').glob('*.zip'))
        self.assertEqual(len(archives), len(self.prepared))
        self.assertTrue(self.prepared, 'the public bundle must contain at least one language profile')
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
                self.assertTrue(self._predecessor_is_valid(item.profile, item.package_name, expected_version))

    def test_same_version_predecessor_lineage_fails_closed(self):
        item = self.by_id['codesys']
        profile = item.profile
        predecessor = profile['predecessor']
        self.assertEqual(predecessor['version'], profile['version'])
        self.assertTrue(self._predecessor_is_valid(profile, item.package_name, item.version))
        missing = dict(profile)
        missing.pop('predecessor')
        self.assertFalse(self._predecessor_is_valid(missing, item.package_name, item.version))
        for field in ('package', 'version', 'candidate', 'source_package', 'package_root_sha256', 'package_manifest_sha256'):
            malformed = dict(profile)
            malformed_predecessor = dict(predecessor)
            malformed_predecessor[field] = None
            malformed['predecessor'] = malformed_predecessor
            self.assertFalse(self._predecessor_is_valid(malformed, item.package_name, item.version), field)
        self_reference = dict(profile)
        self_reference_predecessor = dict(predecessor)
        self_reference_predecessor['candidate'] = f"{profile['successor_candidate']}@{profile['successor_revision']}"
        self_reference['predecessor'] = self_reference_predecessor
        self.assertFalse(self._predecessor_is_valid(self_reference, item.package_name, item.version))

    def test_current_docs_describe_the_declared_profile_set(self):
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
        for item in self.prepared:
            with self.subTest(profile=item.profile_id):
                display_name = str(item.profile.get('name') or item.profile_id)
                display_name = display_name.removeprefix('BBK ').removesuffix(' Profile')
                self.assertIn(display_name, combined)
                self.assertIn(f"`{item.version}`", combined)

    def test_profile_omp_python_overrides_are_interpreter_safe(self):
        for profile_id, item in sorted(self.by_id.items()):
            with self.subTest(profile=profile_id):
                extension = (item.root / 'omp' / 'extension' / 'index.js').read_text(encoding='utf-8')
                self.assertIn('function explicitCommand(value)', extension)
                self.assertIn('.endsWith(".py")', extension)
                self.assertIn('return pythonCommand(path.resolve(value))', extension)

    def test_all_omp_python_children_share_the_direct_runtime_contract(self):
        extension = (m5_ROOT / 'omp' / 'extension' / 'index.js').read_text(encoding='utf-8')
        self.assertIn('C:\\\\Python313\\\\python.exe', extension)
        self.assertIn('normalizedFsPath(selected) !== normalizedFsPath("C:\\\\Python313\\\\python.exe")', extension)
        self.assertIn('BBK direct Python invariant requires C:\\\\Python313\\\\python.exe; got ${selected}', extension)
        self.assertIn('function qualifiedPythonPath()', extension)
        self.assertIn('requires an explicit qualified PYTHONPATH', extension)
        self.assertIn('return ["-B", "-X", "utf8", script]', extension)
        self.assertIn('PYTHONDONTWRITEBYTECODE: "1"', extension)
        self.assertIn('PYTHONNOUSERSITE: "1"', extension)
        self.assertIn('PYTHONPATH: qualifiedPath', extension)
        self.assertEqual(3, extension.count('spawn(pythonCommand(),'))
        self.assertIn('...scriptPrefix(targetRoutingCliPath)', extension)
        self.assertIn('...scriptPrefix(script)', extension)
        self.assertIn('...commandPrefix()', extension)
        self.assertIn('function runQualifiedTask(request, projectRoot, signal)', extension)
        self.assertIn('qualifiedTaskPath,', extension)
        self.assertNotIn('["-3", "-X", "utf8"', extension)

    def test_global_python_launch_inventory_has_no_unclassified_release_constructor(self):
        governed = {
            'tools/install.py': ('sys.executable,', 'py -3 -X utf8', '"${BBK_PYTHON:-python3}" -X utf8'),
            'tools/omp_model_routing.py': ('sys.executable,', '"-S",\n            "-X"'),
            'tools/update_omp.py': ('sys.executable, "-X", "utf8"',),
            'tools/run_tests.py': ('sys.executable, "-B"',),
            'tools/verify_all.py': ('sys.executable, "tools/run_tests.py"',),
            'tools/validate_alpha8_fixtures.py': ('[sys.executable,',),
            'tools/build_release.py': ('sys.executable, "tools/run_tests.py"',),
            'tools/install_dependencies.py': ('[sys.executable, "-m"',),
            'tools/bbk.py': ('[str(tool_python), str(Path(__file__).resolve())',),
            'tests/_fake_executable.py': ('"{sys.executable}" -S -X utf8',),
        }
        for relative, forbidden in governed.items():
            source = (m5_ROOT / relative).read_text(encoding='utf-8')
            for fragment in forbidden:
                self.assertNotIn(fragment, source, f'unclassified launch producer: {relative}: {fragment}')
        helper = (m5_ROOT / 'tools' / 'runtime_requirements.py').read_text(encoding='utf-8')
        for fragment in ('DIRECT_PYTHON_WINDOWS', 'python_command', 'python_environment', 'normalize_python_command'):
            self.assertIn(fragment, helper)

    def test_generated_and_fake_launchers_are_fail_closed(self):
        name, content = install.launcher(m5_ROOT)
        self.assertEqual(name, 'bbk.cmd' if os.name == 'nt' else 'bbk')
        text = content.decode('utf-8')
        self.assertIn('-B -X utf8', text)
        self.assertIn('PYTHONDONTWRITEBYTECODE', text)
        self.assertIn('PYTHONNOUSERSITE', text)
        self.assertIn('BBK_QUALIFIED_PYTHONPATH', text)
        self.assertNotIn('py -3 -X utf8', text)
        fake = (m5_ROOT / 'tests' / '_fake_executable.py').read_text(encoding='utf-8')
        self.assertIn('direct_python_executable()', fake)
        self.assertIn('-B -S -X utf8', fake)


    def test_python_profile_accepts_compatible_successor_core(self):
        item = self.by_id['python']
        module_path = item.root / 'tools' / 'bbk_python.py'
        spec = importlib.util.spec_from_file_location('bbk_profile_python_runtime', module_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertFalse(module.version_supports_structure_contract('0.1.0-alpha.3'))
        for version in ('0.1.0-alpha.4', '0.1.0-alpha.8', '0.1.0-alpha.11.11', '0.1.0-alpha.11.12', '0.1.0-alpha.12', '0.1.0-alpha.12.2', '0.1.0-alpha.12.4', '0.1.0-alpha.13.1', '0.1.0-alpha.13.2', '0.1.0-alpha.13.3', '0.1.0-alpha.13.4', '0.1.0-alpha.13.5', '0.1.0-alpha.14', '0.1.0-alpha.16', '0.1.0-alpha.16.1', '0.1.0-alpha.17+rc.5', '0.1.0-alpha.17+rc.6', '0.1.0-alpha.17+rc.7', '0.1.0-alpha.17+rc.8', '0.1.0-alpha.17', '0.1.0', '0.2.0-alpha.1'):
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
        for expected in ('0.1.0-alpha.17', 'installed by default', '--no-language-profiles', '--profile-id', 'bundled-language-profiles', 'TypeScript/JavaScript'):
            self.assertIn(expected, combined)

# ---------------------------------------------------------------------------


class GlobalPythonLaunchInvariantTests(unittest.TestCase):

    def test_canonical_constructor_preserves_argv_and_external_roots(self):
        from runtime_requirements import python_command, python_environment

        qualified = os.pathsep.join((str(m5_ROOT), str(m5_TOOLS), r'C:\Users\Tombstone\.cache\bbk\tooling\jsonschema-4.25.1\Lib\site-packages'))
        source_env = {
            'PYTHONPATH': qualified,
            'TEMP': r'D:\AHR13\WU-S8-01\temp',
            'TMP': r'D:\AHR13\WU-S8-01\tmp',
            'TMPDIR': r'D:\AHR13\WU-S8-01\tmp',
            'BBK_TEST_CACHE_DIR': r'D:\AHR13\WU-S8-01\cache',
            'BBK_NATIVE_EVIDENCE_ROOT': r'D:\AHR13\WU-S8-01\evidence',
        }
        command = python_command(m5_ROOT / 'tools' / 'install.py', '--json')
        self.assertEqual(command[0].casefold(), r'C:\Python313\python.exe'.casefold())
        self.assertEqual(command[1:4], ['-B', '-X', 'utf8'])
        self.assertEqual(command[4], str(m5_ROOT / 'tools' / 'install.py'))
        environment = python_environment(source_env)
        self.assertEqual(environment['PYTHONDONTWRITEBYTECODE'], '1')
        self.assertEqual(environment['PYTHONNOUSERSITE'], '1')
        self.assertEqual(environment['PYTHONPATH'], qualified)
        for key in ('TEMP', 'TMP', 'TMPDIR', 'BBK_TEST_CACHE_DIR', 'BBK_NATIVE_EVIDENCE_ROOT'):
            self.assertEqual(environment[key], source_env[key])

    def test_canonical_constructor_fails_closed_without_runtime_inputs(self):
        from runtime_requirements import PythonLaunchInvariantError, direct_python_executable, python_environment

        with self.assertRaises(PythonLaunchInvariantError):
            python_environment({'TEMP': r'D:\AHR13\WU-S8-01\temp'})
        with mock.patch.dict(os.environ, {'BBK_DIRECT_PYTHON_EXECUTABLE': r'C:\Wrong\python.exe'}, clear=False):
            with self.assertRaises(PythonLaunchInvariantError):
                direct_python_executable()

    def test_qualified_closure_fails_closed_on_missing_or_misprojected_roots(self):
        from runtime_requirements import PythonLaunchInvariantError, python_environment

        managed = r'C:\Users\Tombstone\.cache\bbk\tooling\jsonschema-4.25.1\Lib\site-packages'
        with self.assertRaises(PythonLaunchInvariantError):
            python_environment({'PYTHONPATH': os.pathsep.join((str(m5_ROOT), str(m5_TOOLS), r'D:\missing\site-packages'))})
        with self.assertRaises(PythonLaunchInvariantError):
            python_environment({'PYTHONPATH': os.pathsep.join((str(m5_TOOLS), str(m5_ROOT), managed))})
        with self.assertRaises(PythonLaunchInvariantError):
            python_environment({'PYTHONPATH': os.pathsep.join((str(m5_ROOT), str(m5_TOOLS), str(m5_ROOT), managed))})

    def test_fast_standard_release_descendants_retain_real_import_closure(self):
        import run_tests
        import verify_all

        managed = Path(r'C:\Users\Tombstone\.cache\bbk\tooling\jsonschema-4.25.1\Lib\site-packages')
        qualified = os.pathsep.join((str(m5_ROOT), str(m5_TOOLS), str(managed)))
        source_env = {
            'PYTHONPATH': qualified,
            'BBK_QUALIFIED_PYTHONPATH': qualified,
            'TEMP': r'D:\AHR13\WU-S9-01\temp',
            'TMP': r'D:\AHR13\WU-S9-01\tmp',
            'TMPDIR': r'D:\AHR13\WU-S9-01\tmp',
            'PYTHONPYCACHEPREFIX': r'D:\AHR13\WU-S9-01\pycache',
            'BBK_TEST_CACHE_DIR': r'D:\AHR13\WU-S9-01\cache',
            'BBK_NATIVE_EVIDENCE_ROOT': r'D:\AHR13\WU-S9-01\evidence',
            'BBK_DIRECT_PYTHON_EXECUTABLE': r'C:\Python313\python.exe',
            'USERPROFILE': str(Path.home()),
            'PATH': os.environ.get('PATH', ''),
        }
        probe = (
            'import importlib.metadata, json, os, sys, jsonschema, referencing; '
            'print(json.dumps({"exe":sys.executable,"argv":sys.argv[1:],'
            '"pythonpath":os.environ["PYTHONPATH"],"dontwrite":os.environ["PYTHONDONTWRITEBYTECODE"],'
            '"nousersite":os.environ["PYTHONNOUSERSITE"],"jsonschema":jsonschema.__version__,'
            '"referencing":importlib.metadata.version("referencing"),"temp":os.environ["TEMP"],'
            '"tmp":os.environ["TMP"],"tmpdir":os.environ["TMPDIR"]}))'
        )
        with mock.patch.dict(os.environ, source_env, clear=True):
            for profile in ('fast', 'standard', 'release'):
                for constructor in (run_tests._subprocess_environment, verify_all._subprocess_environment):
                    environment = constructor()
                    command = [r'C:\Python313\python.exe', '-B', '-X', 'utf8', '-c', probe]
                    self.assertEqual(command[0].casefold(), r'c:\python313\python.exe')
                    self.assertEqual(command[1], '-B')
                    completed = subprocess.run(command, cwd=Path(r'D:\AHR13\WU-S9-01\cwd'), env=environment, capture_output=True, text=True, check=True)
                    observed = json.loads(completed.stdout)
                    self.assertEqual(observed['exe'].casefold(), r'c:\python313\python.exe')
                    self.assertEqual(observed['jsonschema'], '4.25.1')
                    self.assertTrue(observed['referencing'])
                    self.assertEqual(observed['dontwrite'], '1')
                    self.assertEqual(observed['nousersite'], '1')
                    self.assertEqual(observed['pythonpath'].split(os.pathsep), [str(m5_ROOT), str(m5_TOOLS), str(managed)])
                    self.assertEqual(observed['temp'], source_env['TEMP'])
                    self.assertEqual(observed['tmp'], source_env['TMP'])
                    self.assertEqual(observed['tmpdir'], source_env['TMPDIR'])
