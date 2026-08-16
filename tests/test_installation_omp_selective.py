"""Selective OMP installer regressions."""
from __future__ import annotations
import ast
import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
import install as install_tool
import update_omp
from tests._cli_support import run_cli as test_run_cli
from tests._path_support import assert_same_path
from tests._path_support import source_ast
m4_ROOT = ROOT

class Alpha161SelectiveOmpInstallerTests(unittest.TestCase):
    """Regression coverage for the alpha.16 selective OMP replacement defect."""

    def test_empty_installed_profiles_skip_bundle_preparation_without_changing_selection(self):
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.object(
                update_omp,
                "prepare_profile_sources",
                side_effect=AssertionError("bundled profiles must not be prepared when none are installed"),
            ):
                empty_selection = update_omp.prepared_bundled_profiles([], Path(temp))
                self.assertEqual(empty_selection, ([], []))

            prepared = [SimpleNamespace(profile_id="python"), SimpleNamespace(profile_id="rust")]
            with mock.patch.object(update_omp, "prepare_profile_sources", return_value=prepared) as prepare:
                selected, skipped = update_omp.prepared_bundled_profiles(["rust", "missing"], Path(temp))
            prepare.assert_called_once_with(
                [str(install_tool.BUNDLED_PROFILES_PATH)], temp_root=Path(temp), selected_ids=None
            )
            self.assertEqual([item.profile_id for item in selected], ["rust"])
            self.assertEqual(skipped, ["missing"])

    def test_canonical_omp_runtime_inventory_covers_local_python_import_closure(self):
        tools = {
            path.stem: path
            for path in (m4_ROOT / 'tools').glob('*.py')
            if path.is_file()
        }
        pending = ['bbk', 'omp_model_routing']
        visited: set[str] = set()
        while pending:
            name = pending.pop()
            if name in visited:
                continue
            visited.add(name)
            tree = source_ast(tools[name])
            imported: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split('.', 1)[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    imported.add(node.module.split('.', 1)[0])
            pending.extend(sorted(imported & tools.keys() - visited))

        required = {f'{name}.py' for name in visited}
        installed = set(install_tool.OMP_EXTENSION_RUNTIME_FILES)
        self.assertTrue(
            required <= installed,
            f'OMP runtime inventory is missing local import dependencies: {sorted(required - installed)}',
        )

    def test_harness_scoped_replacement_and_update_keep_complete_runtime_and_refresh_routing_metadata(self):
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
            install_base = [
                sys.executable,
                str(m4_ROOT / 'tools' / 'install.py'),
                '--json',
                'install',
                '--scope', 'user',
            ]
            first = test_run_cli(
                [*install_base, '--omp', '--codex', '--no-language-profiles'],
                cwd=m4_ROOT,
                env=env,
                check=False,
                timeout=240,
            )
            self.assertEqual(first.returncode, 0, first.stderr or first.stdout)
            installed = json.loads(first.stdout)
            manifest_path = Path(installed['manifest_path'])
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            manifest['model_routing'].update({
                'custom': False,
                'source': 'D:/Projects/BBK/bbk-0.1.0-alpha.15/spec/model-routing.json',
                'package_version': '0.1.0-alpha.15',
            })
            manifest_path.write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + '\n',
                encoding='utf-8',
            )

            # Exact user regression shape: an installation owns Codex and OMP,
            # then only OMP is selected for a clean harness-scoped replacement.
            replaced = test_run_cli(
                [
                    sys.executable,
                    str(m4_ROOT / 'tools' / 'setup.py'),
                    '--install',
                    '--scope', 'user',
                    '--omp',
                    '--uninstall-existing',
                    '--json',
                ],
                cwd=m4_ROOT,
                env=env,
                check=False,
                timeout=240,
            )
            self.assertEqual(replaced.returncode, 0, replaced.stderr or replaced.stdout)
            replacement = json.loads(replaced.stdout)
            self.assertEqual(replacement['preexisting_install']['decision'], 'replace-selected')
            self.assertEqual(replacement['preexisting_install']['selected_harnesses'], ['omp'])
            self.assertEqual(replacement['preexisting_install']['preserved_harnesses'], ['codex'])

            extension = home / '.omp' / 'agent' / 'extensions' / 'bbk'

            def assert_runtime_and_router_pass() -> None:
                current_manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
                owned = {
                    install_tool.portable_path_key(item['path'])
                    for item in current_manifest['files']
                }
                for name in install_tool.OMP_EXTENSION_RUNTIME_FILES:
                    path = extension / name
                    self.assertTrue(path.is_file(), f'missing installed OMP runtime module: {name}')
                    self.assertIn(install_tool.portable_path_key(path), owned, f'unowned OMP runtime module: {name}')
                router = test_run_cli(
                    [
                        sys.executable,
                        str(extension / 'omp_model_routing.py'),
                        '--binding', str(extension / 'bbk-package-root.json'),
                        '--json', 'status',
                    ],
                    cwd=base,
                    env=env,
                    check=False,
                    timeout=120,
                )
                self.assertEqual(router.returncode, 0, router.stderr or router.stdout)
                self.assertEqual(json.loads(router.stdout)['status'], 'PASS')
                routing = current_manifest['model_routing']
                self.assertFalse(routing['custom'])
                self.assertNotIn('0.1.0-alpha.15', str(routing))
                assert_same_path(self, routing['source'], m4_ROOT / 'spec' / 'model-routing.json')

            assert_runtime_and_router_pass()

            # The dedicated selective updater must use the same canonical
            # runtime inventory and refresh the same packaged-default metadata.
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            manifest['model_routing'].update({
                'custom': False,
                'source': 'D:/Projects/BBK/bbk-0.1.0-alpha.15/spec/model-routing.json',
                'package_version': '0.1.0-alpha.15',
            })
            manifest_path.write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + '\n',
                encoding='utf-8',
            )
            updated = test_run_cli(
                [
                    sys.executable,
                    str(m4_ROOT / 'tools' / 'update_omp.py'),
                    '--scope', 'user',
                    '--clean',
                    '--json',
                ],
                cwd=m4_ROOT,
                env=env,
                check=False,
                timeout=240,
            )
            self.assertEqual(updated.returncode, 0, updated.stderr or updated.stdout)
            update_result = json.loads(updated.stdout)
            self.assertEqual(update_result['status'], 'PASS')
            self.assertEqual(update_result['runtime_inventory']['status'], 'PASS')
            self.assertEqual(update_result['runtime_inventory']['file_count'], len(install_tool.OMP_EXTENSION_RUNTIME_FILES))
            self.assertEqual(update_result['runtime_smoke']['status'], 'PASS')
            self.assertEqual(update_result['runtime_smoke']['import_closure'], 'PASS')
            self.assertEqual(update_result['runtime_smoke']['routing_status'], 'PASS')
            self.assertGreater(update_result['runtime_smoke']['schema_catalogue_count'], 0)
            assert_runtime_and_router_pass()
