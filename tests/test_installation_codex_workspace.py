"""Codex workspace installer regressions."""
from __future__ import annotations
import hashlib
import json
import os
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
import install as install_tool
from tests._cli_support import run_cli as test_run_cli
from tests._path_support import assert_same_path, path_identity_key
m7_ROOT = ROOT
m7_CODEX_AGENTS = ROOT / "projections" / "codex" / "agents"
m7_INSTALL = ROOT / "tools" / "install.py"
m7_SETUP = ROOT / "tools" / "setup.py"
m7_UPDATE_CODEX = ROOT / "tools" / "update_codex.py"
m7_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()

def m7_run(command, *, env=None, check=True):
    return test_run_cli([str(value) for value in command], cwd=ROOT, env=env, check=check, timeout=180)

def m7_run_json(command, *, env=None, check=True):
    result = m7_run(command, env=env, check=check)
    return json.loads(result.stdout), result

def m7_snapshot(root: Path) -> dict[str, tuple[str, int]]:
    return {
        path.relative_to(root).as_posix(): (
            hashlib.sha256(path.read_bytes()).hexdigest(),
            path.stat().st_mtime_ns,
        )
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }

class Alpha116CodexWorkspaceTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.roles = json.loads((m7_ROOT / 'spec' / 'roles.json').read_text(encoding='utf-8'))['roles']
        cls.by_name = {item['name']: item for item in cls.roles}

    def test_current_version_matches_release(self) -> None:
        self.assertEqual(m7_VERSION, '0.1.0-alpha.17.0.2.1')

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
                self.assertIn('## Compiled procedures manifest', instructions)
                for skill in self.by_name[path.stem].get('mandatory_skills', []):
                    self.assertIn((f'### Compiled primary procedure: `{skill}`' if skill == self.by_name[path.stem]['primary_skill'] else f'### Compiled procedure: `{skill}`'), instructions)

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
            artifact_skill_root = home / '.agents' / 'skills' / 'bbk-artifact'
            controller_skill = home / '.agents' / 'skills' / 'bbk' / 'SKILL.md'
            artifact_skill_files = sorted(path for path in artifact_skill_root.rglob('*') if path.is_file())
            self.assertEqual(len(artifact_skill_files), 7)
            # Simulate an alpha.15 installation: the shared artifact skill did
            # not exist yet, while Codex and OMP were already installed.
            artifact_skill_keys = {path_identity_key(path) for path in artifact_skill_files}
            for path in artifact_skill_files:
                path.unlink()
            for directory in sorted(artifact_skill_root.rglob('*'), reverse=True):
                if directory.is_dir():
                    directory.rmdir()
            artifact_skill_root.rmdir()
            controller_skill_key = path_identity_key(controller_skill)
            controller_skill.unlink()
            controller_skill.parent.rmdir()
            manifest['files'] = [
                item for item in manifest['files']
                if path_identity_key(item['path']) not in artifact_skill_keys | {controller_skill_key}
            ]
            records = {path_identity_key(item['path']): item for item in manifest['files']}
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
            self.assertEqual(updated['codex_skill_file_count'], 7)
            self.assertEqual(updated['codex_controller_skill_count'], 1)
            self.assertEqual(updated['actions'], {'create': 8, 'replace': 19, 'unchanged': 17})
            self.assertFalse(updated['shared_package_updated'])
            self.assertFalse(updated['effective_model_routing_updated'])
            self.assertEqual(updated['omp_files_touched'], 0)
            self.assertIn('omp', updated['untouched_harnesses'])
            updated_paths = [item['path'].replace('\\', '/') for item in updated['files']]
            self.assertEqual(sum('/.codex/agents/bbk_' in item for item in updated_paths), 19)
            self.assertEqual(sum('/.agents/skills/bbk-artifact/' in item for item in updated_paths), 7)
            self.assertEqual(sum(item.endswith('/.agents/skills/bbk/SKILL.md') for item in updated_paths), 1)
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
            restored_skill_files = sorted(path for path in artifact_skill_root.rglob('*') if path.is_file())
            self.assertEqual(len(restored_skill_files), 7)
            controller_text = controller_skill.read_text(encoding='utf-8')
            self.assertIn('name: bbk', controller_text)
            self.assertIn('harness: codex', controller_text)
            self.assertEqual(
                {path.relative_to(artifact_skill_root).as_posix() for path in restored_skill_files},
                {
                    'SKILL.md',
                    'agents/openai.yaml',
                    'assets/bbk-package-draft.generic.json',
                    'references/artifact-package-reference.md',
                    'scripts/bbk-artifact.cmd',
                    'scripts/bbk-artifact.sh',
                    'scripts/bbk_artifact.py',
                },
            )
            current = json.loads(manifest_path.read_text(encoding='utf-8'))
            self.assertEqual(current['version'], initial_version)
            assert_same_path(self, current['package_root'], manifest['package_root'])
            self.assertEqual(current['harness_versions']['codex'], m7_VERSION)
            self.assertEqual(current['harness_versions']['omp'], initial_version)
            self.assertEqual(current['last_codex_update']['kind'], 'codex-only')
            self.assertFalse(current['last_codex_update']['shared_package_updated'])
            current_records = {path_identity_key(item['path']): item for item in current['files']}
            self.assertTrue(all(path_identity_key(path) in current_records for path in restored_skill_files))
            self.assertIn(controller_skill_key, current_records)
            status, _ = m7_run_json([sys.executable, m7_INSTALL, '--json', 'status', '--scope', 'user'], env=env)
            self.assertEqual(status['summary'], {'current': len(status['files'])})

    def test_controller_skill_delivery_respects_harness_discovery_roots(self) -> None:
        selections = {
            'codex': ('.agents/skills/bbk/SKILL.md', 'harness: codex'),
            'pi': ('.agents/skills/bbk/SKILL.md', 'harness: pi'),
            'generic': ('.agents/skills/bbk/SKILL.md', 'harness: generic'),
            'claude': ('.claude/skills/bbk/SKILL.md', 'harness: claude'),
        }
        for harness, (relative, host_marker) in selections.items():
            with self.subTest(harness=harness), tempfile.TemporaryDirectory() as temp:
                base = Path(temp)
                home = base / 'home'
                home.mkdir()
                env = os.environ.copy()
                env.update({'BBK_HOME': str(home), 'HOME': str(home), 'BBK_INSTALL_ROOT': str(base / 'data'), 'BBK_BIN_DIR': str(base / 'bin')})
                m7_run_json([sys.executable, m7_INSTALL, '--json', 'install', '--scope', 'user', f'--{harness}', '--no-language-profiles'], env=env)
                skill = home / relative
                text = skill.read_text(encoding='utf-8')
                self.assertIn('name: bbk', text)
                self.assertIn(host_marker, text)
                self.assertIn('Compiled primary procedure', text)
                self.assertNotIn('{{bbk-module:', text)
                self.assertFalse((home / 'AGENTS.md').exists())
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            home = base / 'home'
            home.mkdir()
            env = os.environ.copy()
            env.update({'BBK_HOME': str(home), 'HOME': str(home), 'BBK_INSTALL_ROOT': str(base / 'data'), 'BBK_BIN_DIR': str(base / 'bin')})
            m7_run_json([sys.executable, m7_INSTALL, '--json', 'install', '--scope', 'user', '--omp', '--no-language-profiles'], env=env)
            self.assertFalse((home / '.agents' / 'skills' / 'bbk' / 'SKILL.md').exists())

    def test_project_codex_created_agents_file_is_removed_on_uninstall(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            env = os.environ.copy()
            env['BBK_TEST_ALLOW_MISSING_DEPENDENCIES'] = '1'
            installed, _ = m7_run_json([
                sys.executable, m7_INSTALL, '--json', 'install', '--scope', 'project',
                '--root', project, '--codex', '--no-language-profiles',
            ], env=env)
            agents = project / 'AGENTS.md'
            self.assertTrue(agents.is_file())
            activation = installed['codex_project_activation']
            self.assertTrue(activation['created_file'])
            self.assertNotIn(path_identity_key(agents), {path_identity_key(item['path']) for item in installed['files']})
            removed, _ = m7_run_json([sys.executable, m7_INSTALL, '--json', 'uninstall', '--scope', 'project', '--root', project], env=env)
            self.assertEqual(removed['codex_project_activation']['action'], 'remove-file')
            self.assertFalse(agents.exists())

    def test_project_codex_clean_replacement_accepts_its_owned_activation_block(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            env = os.environ.copy()
            env['BBK_TEST_ALLOW_MISSING_DEPENDENCIES'] = '1'
            command = [
                sys.executable, m7_INSTALL, '--json', 'install', '--scope', 'project',
                '--root', project, '--codex', '--no-language-profiles',
            ]
            m7_run_json(command, env=env)
            replaced, _ = m7_run_json([*command, '--uninstall-existing'], env=env)
            activation = replaced['codex_project_activation']
            self.assertTrue((project / 'AGENTS.md').is_file())
            self.assertEqual(activation['block_sha256'], hashlib.sha256(
                install_tool.codex_activation_block()
            ).hexdigest())

    def test_project_codex_activation_preserves_user_agents_text_through_update_and_uninstall(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            agents = project / 'AGENTS.md'
            agents.write_text('Existing project guidance.\n', encoding='utf-8')
            env = os.environ.copy()
            env['BBK_TEST_ALLOW_MISSING_DEPENDENCIES'] = '1'
            installed, _ = m7_run_json([
                sys.executable, m7_INSTALL, '--json', 'install', '--scope', 'project',
                '--root', project, '--codex', '--no-language-profiles',
            ], env=env)
            manifest_path = Path(installed['manifest_path'])
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            activation = manifest['codex_project_activation']
            self.assertNotIn(path_identity_key(agents), {path_identity_key(item['path']) for item in manifest['files']})
            self.assertEqual(activation['schema'], 'bbk.codex-project-activation.v1')
            self.assertFalse(activation['created_file'])
            original_backup = Path(activation['original_backup'])
            self.assertEqual(original_backup.read_text(encoding='utf-8'), 'Existing project guidance.\n')
            old_block = (
                '<!-- BEGIN BBK CODEX ACTIVATION -->\n'
                'For old substantive work, invoke `$bbk`.\n'
                '<!-- END BBK CODEX ACTIVATION -->\n'
            )
            current = agents.read_text(encoding='utf-8')
            begin = current.index('<!-- BEGIN BBK CODEX ACTIVATION -->')
            agents.write_bytes((current[:begin] + old_block + 'Later user guidance.\n').encode('utf-8'))
            activation['block_sha256'] = hashlib.sha256(old_block.encode()).hexdigest()
            activation['installed_file_sha256'] = hashlib.sha256((current[:begin] + old_block).encode()).hexdigest()
            manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
            update_result = m7_run([sys.executable, m7_UPDATE_CODEX, '--json', '--scope', 'project', '--root', project], env=env, check=False)
            self.assertEqual(update_result.returncode, 0, update_result.stdout + update_result.stderr)
            updated = json.loads(update_result.stdout)
            self.assertEqual(updated['status'], 'PASS')
            updated_text = agents.read_text(encoding='utf-8')
            self.assertIn('Existing project guidance.', updated_text)
            self.assertIn('Later user guidance.', updated_text)
            self.assertIn('For substantive work in this project, invoke `$bbk`', updated_text)
            removed, _ = m7_run_json([sys.executable, m7_INSTALL, '--json', 'uninstall', '--scope', 'project', '--root', project], env=env)
            self.assertEqual(removed['codex_project_activation']['action'], 'remove-block')
            final_text = agents.read_text(encoding='utf-8')
            self.assertIn('Existing project guidance.', final_text)
            self.assertIn('Later user guidance.', final_text)
            self.assertNotIn('BBK CODEX ACTIVATION', final_text)

    def test_current_docs_explain_permission_and_authority_separation(self) -> None:
        corpus = '\n'.join(((m7_ROOT / rel).read_text(encoding='utf-8') for rel in ('README.md', 'docs/AGENTS.md', 'docs/USAGE.md', 'docs/INSTALL.md')))
        for expected in ('inherit the parent', 'sandbox', 'coordination artifacts', 'does not authorize', 'subject or product artifacts', '--update-codex'):
            self.assertIn(expected, corpus)
