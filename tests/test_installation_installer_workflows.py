"""Extracted installation regression tests."""
from __future__ import annotations

# Historical source: test_alpha11_1_bundled_release.py
# ---------------------------------------------------------------------------
import io
import importlib
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
from tests._path_support import assert_same_path_sequence
m5_BUNDLE = m5_ROOT / 'bundled-language-profiles'
m5_RELEASE = json.loads((m5_BUNDLE / 'RELEASE-MANIFEST.json').read_text(encoding='utf-8'))
m5_EXPECTED_PROFILE_VERSIONS = dict(sorted((m5_RELEASE.get('profileVersions') or {}).items()))
m5_EXPECTED_PROFILES = sorted(m5_EXPECTED_PROFILE_VERSIONS)

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
                predecessor = item.profile.get('predecessor', {})
                self.assertEqual(predecessor.get('package'), item.package_name)
                self.assertIsInstance(predecessor.get('version'), str)
                self.assertNotEqual(predecessor.get('version'), expected_version)

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
