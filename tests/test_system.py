"""Consolidated BBK regression tests grouped by responsibility.

Historical release-specific modules were merged to keep the public repository
readable while retaining their behavioral coverage.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Historical source: test_bbk.py
# ---------------------------------------------------------------------------
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import tomllib
import unittest
from pathlib import Path
m1_ROOT = Path(__file__).resolve().parents[1]
m1_BBK = m1_ROOT / 'tools' / 'bbk.py'
m1_INSTALL = m1_ROOT / 'tools' / 'install.py'
m1_GENERATOR = m1_ROOT / 'tools' / 'generate_agents.py'
m1_ROUTING = m1_ROOT / 'spec' / 'model-routing.json'

def m1_run(command, *, cwd=None, env=None, check=True):
    return subprocess.run([str(x) for x in command], cwd=str(cwd or m1_ROOT), env=env, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')

def m1_run_json(command, *, cwd=None, env=None, check=True):
    result = m1_run(command, cwd=cwd, env=env, check=check)
    return (json.loads(result.stdout), result)

def m1_parse_simple_yaml_frontmatter(path: Path):
    lines = path.read_text(encoding='utf-8').splitlines()
    assert lines[0] == '---'
    end = lines.index('---', 1)
    data = {}
    key = None
    for line in lines[1:end]:
        if line.startswith('  - '):
            if key is None:
                raise AssertionError(f'orphan list item in {path}: {line}')
            raw = line[4:]
            try:
                value = json.loads(raw)
            except json.JSONDecodeError:
                value = raw
            data.setdefault(key, []).append(value)
            continue
        if not line.strip():
            continue
        if ':' not in line:
            raise AssertionError(f'invalid frontmatter line in {path}: {line}')
        key, raw = line.split(':', 1)
        key = key.strip()
        raw = raw.strip()
        if raw == '':
            data[key] = []
        else:
            try:
                data[key] = json.loads(raw)
            except json.JSONDecodeError:
                if raw == 'true':
                    data[key] = True
                elif raw == 'false':
                    data[key] = False
                else:
                    data[key] = raw
    return data

def m1_make_test_profile(base: Path) -> Path:
    profile_root = base / 'rust' / '0.0.0-test'
    (profile_root / 'tools').mkdir(parents=True)
    resolver = profile_root / 'tools' / 'resolve.py'
    resolver.write_text(textwrap.dedent("\n        import argparse, hashlib, json\n        p = argparse.ArgumentParser(); p.add_argument('--json', action='store_true')\n        sub = p.add_subparsers(dest='command', required=True); r = sub.add_parser('resolve')\n        r.add_argument('--root'); r.add_argument('--work-unit'); r.add_argument('--task-profile')\n        r.add_argument('--assurance-tier'); r.add_argument('--role'); r.add_argument('--change-class', action='append')\n        r.add_argument('--hint', action='append'); r.add_argument('--path', action='append'); r.add_argument('--run-tools', action='store_true')\n        args = p.parse_args()\n        payload = {'id':'rust','version':'0.0.0-test','root':args.root,'task':args.task_profile,'tier':args.assurance_tier,'role':args.role,'hints':args.hint or [],'paths':args.path or []}\n        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()\n        lock = {'schema':'bbk.profile-lock.v1','generated_at':'2026-07-23T00:00:00Z','profiles':[payload],'effective_sha256':digest}\n        print(json.dumps({'schema':'bbk.test-profile-resolution.v1','selected_components':[{'id':'test-rust'}],'effective_sha256':digest,'lock':lock}))\n    "), encoding='utf-8')
    resolver.chmod(493)
    profile = {'schema': 'bbk.language-profile.v1', 'id': 'rust', 'name': 'Test Rust', 'package': 'bbk-profile-rust-test', 'version': '0.0.0-test', 'maturity': 'review-only', 'authority': {'may_grant_tools_or_effects': False, 'may_expand_work_scope': False, 'may_reduce_assurance': False, 'may_declare_pass': False}, 'entrypoints': {'resolve': ['{python}', 'tools/resolve.py', '--json', 'resolve']}, 'skills': []}
    (profile_root / 'PROFILE.json').write_text(json.dumps(profile, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    records = []
    for path in sorted([profile_root / 'PROFILE.json', resolver]):
        data = path.read_bytes()
        rel = path.relative_to(profile_root).as_posix()
        records.append({'path': rel, 'bytes': len(data), 'sha256': __import__('hashlib').sha256(data).hexdigest(), 'executable': bool(path.stat().st_mode & 73)})
    payload = {'schema': 'bbk.profile-package-root.v1', 'name': 'Test Rust', 'version': '0.0.0-test', 'files': records}
    root_digest = __import__('hashlib').sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    manifest = {'schema': 'bbk.profile-package-manifest.v1', 'root_schema': 'bbk.profile-package-root.v1', 'name': 'Test Rust', 'profile_id': 'rust', 'version': '0.0.0-test', 'file_count': len(records), 'files': records, 'root_sha256': root_digest}
    (profile_root / 'PACKAGE-MANIFEST.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return profile_root

class BbkTests(unittest.TestCase):

    def test_agent_generation_and_counts(self):
        m1_run([sys.executable, m1_GENERATOR, '--check'])
        manifest = json.loads((m1_ROOT / 'projections' / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['role_count'], 19)
        self.assertEqual(manifest['target_count'], 4)
        self.assertEqual(manifest['projection_count'], 76)
        self.assertEqual(manifest['model_profile_count'], 3)
        self.assertEqual(manifest['role_profile_counts'], {'coordination': 5, 'judgment': 12, 'mechanical': 2})
        self.assertEqual(manifest['targets'], ['claude', 'codex', 'generic', 'omp'])
        for target in manifest['targets']:
            self.assertEqual(len(list((m1_ROOT / 'projections' / target / 'agents').glob('*'))), 19)

    def test_codex_toml_parses(self):
        routing = json.loads(m1_ROUTING.read_text(encoding='utf-8'))
        for path in (m1_ROOT / 'projections' / 'codex' / 'agents').glob('*.toml'):
            value = tomllib.loads(path.read_text(encoding='utf-8'))
            self.assertTrue(value['name'].startswith('bbk_'))
            self.assertTrue(value['model'])
            self.assertIn(value['model_reasoning_effort'], {'minimal', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra'})
            self.assertIn('developer_instructions', value)
            profile = routing['role_profiles'][value['name']]
            expected = routing['profiles'][profile]['codex']
            self.assertEqual(value['model'], expected['model'])
            self.assertEqual(value['model_reasoning_effort'], expected['model_reasoning_effort'])

    def test_claude_frontmatter_and_containment(self):
        paths = list((m1_ROOT / 'projections' / 'claude' / 'agents').glob('*.md'))
        self.assertEqual(len(paths), 19)
        names = set()
        routing = json.loads(m1_ROUTING.read_text(encoding='utf-8'))
        for path in paths:
            value = m1_parse_simple_yaml_frontmatter(path)
            name = value['name']
            self.assertRegex(name, '^[a-z][a-z0-9-]*$')
            self.assertNotIn(name, names)
            names.add(name)
            canonical_name = name.replace('-', '_')
            profile = routing['role_profiles'][canonical_name]
            expected = routing['profiles'][profile]['claude']
            self.assertEqual(value['model'], expected['model'])
            self.assertEqual(value['effort'], expected['effort'])
            self.assertEqual(value['permissionMode'], 'default')
            self.assertTrue(value['description'])
            self.assertIn('Read', value['tools'])
            self.assertIn('Skill', value['tools'])
            self.assertTrue(value['skills'])
            self.assertIn('Edit', value['tools'])
            self.assertIn('Write', value['tools'])
            self.assertIn('NotebookEdit', value['tools'])
            self.assertNotIn('disallowedTools', value)
            if name in {'bbk-worker', 'bbk-prototyper'}:
                self.assertEqual(value['isolation'], 'worktree')
            else:
                self.assertNotIn('isolation', value)
        root = m1_parse_simple_yaml_frontmatter(m1_ROOT / 'projections' / 'claude' / 'agents' / 'bbk-root-wayfinder.md')
        self.assertTrue(any((tool.startswith('Agent(') for tool in root['tools'])))
        self.assertIn('AskUserQuestion', root['tools'])

    def test_omp_extension_parses_and_registers(self):
        m1_run(['node', '--check', m1_ROOT / 'omp' / 'extension' / 'index.js'])
        script = m1_ROOT / 'tests' / '.omp-mock.mjs'
        script.write_text(textwrap.dedent(f"\n            const chain = () => ({{ optional() {{ return this; }} }});\n            const z = {{\n              object: value => value,\n              string: chain,\n              boolean: chain,\n              enum: values => chain(),\n              array: value => chain(),\n            }};\n            const tools = [], commands = [], handlers = [];\n            const pi = {{\n              zod: {{ z }}, setLabel() {{}},\n              registerTool(value) {{ tools.push(value); }},\n              registerCommand(name, value) {{ commands.push([name, value]); }},\n              on(name, value) {{ handlers.push([name, value]); }},\n              sendMessage() {{}},\n            }};\n            const mod = await import({json.dumps((m1_ROOT / 'omp' / 'extension' / 'index.js').as_uri())});\n            mod.default(pi);\n            if (tools.length !== 26) throw new Error(`tools=${{tools.length}}`);\n            if (commands.length !== 27) throw new Error(`commands=${{commands.length}}`);\n            if (!handlers.some(([n]) => n === 'tool_call')) throw new Error('missing tool_call');\n            if (!handlers.some(([n]) => n === 'session_start')) throw new Error('missing session_start');\n            if (!handlers.some(([n]) => n === 'before_agent_start')) throw new Error('missing before_agent_start');\n            console.log(JSON.stringify({{tools: tools.map(x=>x.name), commands: commands.map(x=>x[0])}}));\n        "), encoding='utf-8')
        try:
            result = m1_run(['node', script])
            value = json.loads(result.stdout)
            self.assertIn('bbk_status', value['tools'])
            self.assertIn('bbk:gate', value['commands'])
            self.assertIn('bbk:models', value['commands'])
            self.assertIn('bbk:exit', value['commands'])
        finally:
            script.unlink(missing_ok=True)

    def test_installed_omp_extension_executes_copied_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            home = base / 'home'
            home.mkdir()
            project = base / 'project'
            project.mkdir()
            env = os.environ.copy()
            env.update({'BBK_HOME': str(home), 'HOME': str(home), 'BBK_INSTALL_ROOT': str(base / 'data'), 'BBK_BIN_DIR': str(base / 'bin')})
            m1_run([sys.executable, m1_BBK, 'init', '--root', project, '--project-id', 'TEST-INSTALLED-OMP'])
            installed, _ = m1_run_json([sys.executable, m1_INSTALL, '--json', 'install', '--scope', 'user', '--omp'], env=env)
            self.assertTrue(installed['omp'])
            extension = home / '.omp' / 'agent' / 'extensions' / 'bbk' / 'index.js'
            self.assertTrue((extension.parent / 'VERSION').is_file())
            installed_package = Path(installed['package_root'])
            script = base / 'installed-omp-mock.mjs'
            script.write_text(textwrap.dedent(f"\n                const chain = () => ({{ optional() {{ return this; }} }});\n                const z = {{ object: value => value, string: chain, boolean: chain,\n                  enum: values => chain(), array: value => chain() }};\n                const tools = [], commands = [], handlers = [];\n                const pi = {{ zod: {{ z }}, setLabel() {{}},\n                  registerTool(value) {{ tools.push(value); }},\n                  registerCommand(name, value) {{ commands.push([name, value]); }},\n                  on(name, value) {{ handlers.push([name, value]); }}, sendMessage() {{}} }};\n                const mod = await import({json.dumps(extension.as_uri())});\n                mod.default(pi);\n                const tool = tools.find(value => value.name === 'bbk_status');\n                if (!tool) throw new Error('missing bbk_status');\n                const result = await tool.execute('call-1', {{root: {json.dumps(str(project))}}}, undefined, undefined, {{cwd: {json.dumps(str(project))}}});\n                if (result.isError || result.details?.schema !== 'bbk.status.v1')\n                  throw new Error(JSON.stringify(result.details));\n                const stateEffect = tools.find(value => value.name === 'bbk_state_effect_validate');\n                const sde = await stateEffect.execute('call-2', {{path: {json.dumps(str(installed_package / 'fixtures' / 'state-effect' / 'contract-order.json'))}}}, undefined, undefined, {{cwd: {json.dumps(str(project))}}});\n                if (sde.isError || sde.details?.kind !== 'state-decision-effect-design' || !sde.details?.valid)\n                  throw new Error(JSON.stringify(sde.details));\n                const review = tools.find(value => value.name === 'bbk_review_status');\n                const rr = await review.execute('call-3', {{path: {json.dumps(str(installed_package / 'fixtures' / 'review' / 'run-pass.json'))}}}, undefined, undefined, {{cwd: {json.dumps(str(project))}}});\n                if (rr.isError || rr.details?.kind !== 'review-run' || !rr.details?.valid)\n                  throw new Error(JSON.stringify(rr.details));\n                console.log(JSON.stringify({{schema: result.details.schema, tools: tools.length, sde: sde.details.kind, review: rr.details.kind}}));\n            "), encoding='utf-8')
            value = json.loads(m1_run(['node', script], env=env).stdout)
            self.assertEqual(value['schema'], 'bbk.status.v1')
            self.assertEqual(value['sde'], 'state-decision-effect-design')
            self.assertEqual(value['review'], 'review-run')
            m1_run([sys.executable, m1_INSTALL, 'uninstall', '--scope', 'user'], env=env)
            self.assertTrue(home.exists())

    def test_manifest_distinguishes_semantic_and_byte_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'source'
            source.mkdir()
            (source / 'data.json').write_text('{"a":1,"b":2}\n', encoding='utf-8')
            left, _ = m1_run_json([sys.executable, m1_BBK, '--json', 'manifest', 'create', '--source', source])
            (source / 'data.json').write_text('{\n  "b": 2,\n  "a": 1\n}\n', encoding='utf-8')
            right, _ = m1_run_json([sys.executable, m1_BBK, '--json', 'manifest', 'create', '--source', source])
            left_path = Path(temp) / 'left.json'
            right_path = Path(temp) / 'right.json'
            left_path.write_text(json.dumps(left), encoding='utf-8')
            right_path.write_text(json.dumps(right), encoding='utf-8')
            comparison, _ = m1_run_json([sys.executable, m1_BBK, '--json', 'manifest', 'compare', '--left', left_path, '--right', right_path])
            self.assertFalse(comparison['equal'])
            self.assertEqual(comparison['summary'], {'semantic_equivalent_byte_change': 1})
            (source / 'data.json').write_text('{"a":1,"b":3}\n', encoding='utf-8')
            changed, _ = m1_run_json([sys.executable, m1_BBK, '--json', 'manifest', 'create', '--source', source])
            changed_path = Path(temp) / 'changed.json'
            changed_path.write_text(json.dumps(changed), encoding='utf-8')
            comparison, _ = m1_run_json([sys.executable, m1_BBK, '--json', 'manifest', 'compare', '--left', left_path, '--right', changed_path])
            self.assertEqual(comparison['summary'], {'semantic_changed': 1})

    def test_candidate_staleness_and_gate_reuse(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'project'
            root.mkdir()
            m1_run([sys.executable, m1_BBK, 'init', '--root', root, '--project-id', 'TEST-CANDIDATE'])
            (root / 'subject.txt').write_text('one\n', encoding='utf-8')
            gates = {'schema': 'bbk.gates.v1', 'prevalidation': {'allow_empty': False}, 'gates': [{'id': 'focused', 'enabled': True, 'phases': ['prevalidate'], 'description': 'focused pass', 'command': [sys.executable, '-c', "print('ok')"], 'cwd': '.', 'blocking': True, 'requires': [Path(sys.executable).name], 'assertions': ['focused-pass']}]}
            (root / '.bbk' / 'gates.json').write_text(json.dumps(gates), encoding='utf-8')
            m1_run([sys.executable, m1_BBK, 'candidate', 'freeze', '--root', root, '--id', 'C-001'])
            first, _ = m1_run_json([sys.executable, m1_BBK, '--json', 'gate', 'run', '--root', root, '--phase', 'prevalidate', '--candidate', 'C-001'])
            self.assertEqual(first['status'], 'PASS')
            self.assertFalse(first['results'][0]['reused'])
            second, _ = m1_run_json([sys.executable, m1_BBK, '--json', 'gate', 'run', '--root', root, '--phase', 'prevalidate', '--candidate', 'C-001'])
            self.assertEqual(second['status'], 'PASS')
            self.assertTrue(second['results'][0]['reused'])
            status, _ = m1_run_json([sys.executable, m1_BBK, '--json', 'candidate', 'status', '--root', root, '--id', 'C-001'])
            self.assertTrue(status['state']['validator_ready'])
            (root / 'subject.txt').write_text('two\n', encoding='utf-8')
            checked, _ = m1_run_json([sys.executable, m1_BBK, '--json', 'candidate', 'check', '--root', root, '--id', 'C-001'])
            self.assertFalse(checked['current'])
            self.assertFalse(checked['state']['validator_ready'])

    def test_git_worktree_lifecycle(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'repo'
            root.mkdir()
            m1_run(['git', 'init', '-q'], cwd=root)
            m1_run(['git', 'config', 'user.email', 'bbk@example.invalid'], cwd=root)
            m1_run(['git', 'config', 'user.name', 'BBK Test'], cwd=root)
            (root / 'README.md').write_text('test\n', encoding='utf-8')
            m1_run(['git', 'add', 'README.md'], cwd=root)
            m1_run(['git', 'commit', '-qm', 'initial'], cwd=root)
            m1_run([sys.executable, m1_BBK, 'init', '--root', root, '--project-id', 'TEST-WORKSPACE'])
            created, _ = m1_run_json([sys.executable, m1_BBK, '--json', 'workspace', 'create', '--root', root, '--id', 'worker-1'])
            worktree = Path(created['workspace']['path'])
            self.assertTrue(worktree.is_dir())
            inspected, _ = m1_run_json([sys.executable, m1_BBK, '--json', 'workspace', 'inspect', '--root', root, '--id', 'worker-1'])
            self.assertTrue(inspected['inspection']['exists'])
            removed, _ = m1_run_json([sys.executable, m1_BBK, '--json', 'workspace', 'cleanup', '--root', root, '--id', 'worker-1', '--delete-branch'])
            self.assertEqual(removed['status'], 'REMOVED')
            self.assertFalse(worktree.exists())

    def test_beads_projection_is_dry_run(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'project'
            root.mkdir()
            m1_run([sys.executable, m1_BBK, 'init', '--root', root, '--project-id', 'TEST-BEADS'])
            project_map = json.loads((root / '.bbk' / 'map.json').read_text(encoding='utf-8'))
            project_map['territories'] = [{'id': 'T-1', 'name': 'Core'}]
            project_map['questions'] = [{'id': 'Q-1', 'title': 'Choose storage', 'territory_id': 'T-1'}]
            (root / '.bbk' / 'map.json').write_text(json.dumps(project_map), encoding='utf-8')
            value, _ = m1_run_json([sys.executable, m1_BBK, '--json', 'beads', 'plan', '--root', root])
            self.assertTrue(value['dry_run'])
            self.assertFalse(value['write_enabled'])
            self.assertEqual(len(value['operations']), 3)

    def test_user_install_all_targets_and_uninstall(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / 'home'
            home.mkdir()
            env = os.environ.copy()
            env.update({'BBK_HOME': str(home), 'HOME': str(home), 'BBK_INSTALL_ROOT': str(home / 'data'), 'BBK_BIN_DIR': str(home / 'bin')})
            installed, _ = m1_run_json([sys.executable, m1_INSTALL, '--json', 'install', '--scope', 'user'], env=env)
            self.assertTrue(installed['codex'] and installed['omp'] and installed['claude'] and installed['generic'])
            self.assertEqual(len(list((home / '.claude' / 'agents').glob('*.md'))), 19)
            self.assertGreater(len(list((home / '.claude' / 'skills').glob('*/SKILL.md'))), 21)
            self.assertEqual(len(list((home / '.codex' / 'agents').glob('*.toml'))), 19)
            registry = (home / '.agents' / 'skills' / 'bbk-installed-profiles' / 'SKILL.md').read_text(encoding='utf-8')
            expected_profiles = ['codesys', 'go', 'python', 'rust', 'typescript-javascript']
            self.assertEqual([item['id'] for item in installed['language_profiles']], expected_profiles)
            self.assertEqual(installed['language_profile_source_mode'], 'bundled-default')
            self.assertEqual(installed['language_profile_registry']['profile_count'], 5)
            for router in ('bbk-codesys', 'bbk-go', 'bbk-python', 'bbk-rust', 'bbk-tsjs'):
                self.assertIn(f'Router skill: `{router}`', registry)
            self.assertNotIn('package-source placeholder', registry)
            self.assertEqual(len(list((home / '.agents' / 'bbk' / 'agents').glob('*.md'))), 19)
            status, _ = m1_run_json([sys.executable, m1_INSTALL, '--json', 'status', '--scope', 'user'], env=env)
            self.assertTrue(status['installed'])
            self.assertEqual(status['summary'].get('current'), len(status['files']))
            m1_run([sys.executable, m1_INSTALL, 'uninstall', '--scope', 'user'], env=env)
            self.assertTrue(home.exists())
            self.assertFalse((home / 'data' / 'install-manifest.json').exists())

    def test_project_all_targets_dry_run_does_not_require_staged_copy(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / 'project'
            project.mkdir()
            value, _ = m1_run_json([sys.executable, m1_INSTALL, '--json', 'install', '--scope', 'project', '--root', project, '--dry-run'])
            self.assertTrue(value['codex'] and value['omp'] and value['claude'] and value['generic'])
            self.assertTrue(any((item['path'].endswith('.omp/extensions/bbk/bbk.py') for item in value['files'])))
            self.assertFalse((project / '.bbk-kit').exists())

    def test_project_claude_only_install_preserves_root(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / 'project'
            project.mkdir()
            installed, _ = m1_run_json([sys.executable, m1_INSTALL, '--json', 'install', '--scope', 'project', '--root', project, '--claude'])
            self.assertFalse(installed['codex'])
            self.assertFalse(installed['omp'])
            self.assertTrue(installed['claude'])
            self.assertEqual(len(list((project / '.claude' / 'agents').glob('*.md'))), 19)
            self.assertFalse((project / '.codex' / 'agents').exists())
            m1_run([sys.executable, m1_INSTALL, 'uninstall', '--scope', 'project', '--root', project])
            self.assertTrue(project.exists())
            self.assertFalse((project / '.bbk-kit-install.json').exists())

    def test_profile_discovery_resolution_lock_and_extra_file_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            project = temp_root / 'project'
            project.mkdir()
            m1_run([sys.executable, m1_BBK, 'init', '--root', project, '--project-id', 'TEST-PROFILE'])
            profile_base = temp_root / 'profiles'
            profile_root = m1_make_test_profile(profile_base)
            listed, _ = m1_run_json([sys.executable, m1_BBK, '--json', 'profile', 'list', '--root', project, '--profile-dir', profile_base])
            self.assertEqual(len(listed['profiles']), 1)
            self.assertEqual(listed['profiles'][0]['package_verification']['status'], 'PASS')
            inspected, _ = m1_run_json([sys.executable, m1_BBK, '--json', 'profile', 'inspect', '--root', project, '--profile-dir', profile_base, '--id', 'rust'])
            self.assertEqual(inspected['version'], '0.0.0-test')
            resolved, _ = m1_run_json([sys.executable, m1_BBK, '--json', 'profile', 'resolve', '--root', project, '--source', project, '--profile-dir', profile_base, '--id', 'rust', '--role', 'worker', '--task-profile', 'implementation', '--assurance-tier', 'routine', '--hint', 'public-api', '--path', 'src/lib.rs', '--write-lock'])
            self.assertEqual(resolved['resolution']['selected_components'][0]['id'], 'test-rust')
            lock = json.loads((project / '.bbk' / 'profile-lock.json').read_text(encoding='utf-8'))
            self.assertRegex(lock['effective_sha256'], '^[0-9a-f]{64}$')
            (profile_root / 'unexpected.txt').write_text('drift\n', encoding='utf-8')
            drifted, _ = m1_run_json([sys.executable, m1_BBK, '--json', 'profile', 'inspect', '--root', project, '--profile-dir', profile_base, '--id', 'rust'])
            self.assertEqual(drifted['package_verification']['status'], 'FAIL')
            self.assertTrue(any(('unexpected' in error for error in drifted['package_verification']['errors'])))

    def test_init_creates_empty_profile_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'project'
            root.mkdir()
            m1_run([sys.executable, m1_BBK, 'init', '--root', root, '--project-id', 'TEST-LOCK'])
            value = json.loads((root / '.bbk' / 'profile-lock.json').read_text(encoding='utf-8'))
            self.assertEqual(value['schema'], 'bbk.profile-lock.v1')
            self.assertIsNone(value['generated_at'])
            self.assertEqual(value['profiles'], [])
            self.assertIsNone(value['effective_sha256'])

# ---------------------------------------------------------------------------
# Historical source: test_alpha10_2_delegation_profiles.py
# ---------------------------------------------------------------------------
import json
import re
import tempfile
import tomllib
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any
m2_ROOT = Path(__file__).resolve().parents[1]
m2_TOOLS = m2_ROOT / 'tools'
import sys
if str(m2_TOOLS) not in sys.path:
    sys.path.insert(0, str(m2_TOOLS))
import profile_registry
m2_FORBIDDEN_PROMPT_PROVENANCE = ('Canonical role:', 'Host projection:', 'Model-routing profile:', 'Canonical role catalogue digest:', 'Canonical model-routing digest:', 'projection_source_sha256')
m2_PROFILE_AWARE_ROLES = {'bbk_root_wayfinder', 'bbk_territory_wayfinder', 'bbk_planning_wayfinder', 'bbk_phase_wayfinder', 'bbk_prototyper', 'bbk_synthesizer', 'bbk_architect', 'bbk_verification_designer', 'bbk_worker_designer', 'bbk_reviewer', 'bbk_root_orchestrator', 'bbk_territory_orchestrator', 'bbk_worker_orchestrator', 'bbk_validator_orchestrator', 'bbk_worker', 'bbk_validator'}

def m2__frontmatter_and_body(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding='utf-8')
    lines = text.splitlines()
    if not lines or lines[0] != '---':
        raise AssertionError(f'missing frontmatter: {path}')
    end = lines.index('---', 1)
    data: dict[str, Any] = {}
    active: str | None = None
    for line in lines[1:end]:
        if line.startswith('  - '):
            if active is None:
                raise AssertionError(f'orphan list item in {path}: {line}')
            value = line[4:]
            try:
                parsed: Any = json.loads(value)
            except json.JSONDecodeError:
                parsed = value
            current = data.setdefault(active, [])
            if not isinstance(current, list):
                raise AssertionError(f'mixed scalar/list field in {path}: {active}')
            current.append(parsed)
            continue
        if not line.strip():
            continue
        key, raw = line.split(':', 1)
        key, raw = (key.strip(), raw.strip())
        active = key
        if not raw:
            data[key] = []
            continue
        try:
            data[key] = json.loads(raw)
        except json.JSONDecodeError:
            data[key] = [value.strip() for value in raw.split(',')] if ',' in raw else raw
    body = '\n'.join(lines[end + 1:]).lstrip('\n') + ('\n' if text.endswith('\n') else '')
    return (data, body)

def m2__codex(path: Path) -> tuple[dict[str, Any], str]:
    data = tomllib.loads(path.read_text(encoding='utf-8'))
    return (data, str(data['developer_instructions']))

def m2__delegated_names(body: str, *, host: str) -> list[str]:
    if '## Delegation' not in body:
        return []
    section = body.split('## Delegation', 1)[1]
    if '\n## ' in section:
        section = section.split('\n## ', 1)[0]
    if host == 'claude':
        return re.findall('^-[^\\n]*\\(canonical `([^`]+)`\\) — ', section, flags=re.MULTILINE)
    return re.findall('^- `([^`]+)` — ', section, flags=re.MULTILINE)

@dataclass
class _DummyProfile:
    root: Path
    profile: dict[str, Any]

    @property
    def profile_id(self) -> str:
        return str(self.profile['id'])

    @property
    def version(self) -> str:
        return str(self.profile['version'])

    @property
    def package_name(self) -> str:
        return str(self.profile['package'])

class Alpha102DelegationProfileTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.spec = json.loads((m2_ROOT / 'spec' / 'roles.json').read_text(encoding='utf-8'))
        cls.roles = {role['name']: role for role in cls.spec['roles']}
        cls.manifest = json.loads((m2_ROOT / 'projections' / 'manifest.json').read_text(encoding='utf-8'))

    def test_non_omp_projections_name_only_the_canonical_allowed_children(self):
        for role_name, role in self.roles.items():
            expected = role.get('spawns', [])
            paths_and_bodies = []
            _, codex_body = m2__codex(m2_ROOT / 'projections' / 'codex' / 'agents' / f'{role_name}.toml')
            paths_and_bodies.append(('codex', codex_body))
            _, claude_body = m2__frontmatter_and_body(m2_ROOT / 'projections' / 'claude' / 'agents' / f"{role_name.replace('_', '-')}.md")
            paths_and_bodies.append(('claude', claude_body))
            generic_body = (m2_ROOT / 'projections' / 'generic' / 'agents' / f'{role_name}.md').read_text(encoding='utf-8')
            paths_and_bodies.append(('generic', generic_body))
            for host, body in paths_and_bodies:
                self.assertIn('## Delegation', body, f'{host}:{role_name}')
                self.assertEqual(m2__delegated_names(body, host=host), expected, f'{host}:{role_name}')
                if expected:
                    for child_name in expected:
                        trigger = role['delegation'][child_name]
                        if host == 'claude':
                            invocation = child_name.replace('_', '-')
                            expected_line = f"- `{invocation}` (canonical `{child_name}`) — when {trigger}."
                        else:
                            expected_line = f"- `{child_name}` — when {trigger}."
                        self.assertIn(expected_line, body, f'{host}:{role_name}')
                    self.assertIn('Delegate only inside this list', body, f'{host}:{role_name}')
                else:
                    self.assertIn('has no child-agent authority', body, f'{host}:{role_name}')

    def test_omp_spawns_and_prompt_triggers_match_the_canonical_contract(self):
        for role_name, role in self.roles.items():
            meta, body = m2__frontmatter_and_body(m2_ROOT / 'projections' / 'omp' / 'agents' / f'{role_name}.md')
            expected = role.get('spawns', [])
            actual = meta.get('spawns', [])
            if isinstance(actual, str):
                actual = [value.strip() for value in actual.split(',') if value.strip()]
            self.assertEqual(actual, expected, role_name)
            self.assertIn('## Delegation', body, role_name)
            self.assertEqual(m2__delegated_names(body, host='omp'), expected, role_name)
            for child_name, trigger in role['delegation'].items():
                self.assertIn(f"- `{child_name}` — when {trigger}.", body, role_name)

    def test_claude_agent_tool_allowlist_matches_canonical_children(self):
        for role_name, role in self.roles.items():
            meta, _ = m2__frontmatter_and_body(m2_ROOT / 'projections' / 'claude' / 'agents' / f"{role_name.replace('_', '-')}.md")
            tools = meta.get('tools', [])
            agent_tools = [value for value in tools if isinstance(value, str) and value.startswith('Agent(')]
            expected = role.get('spawns', [])
            if not expected:
                self.assertEqual(agent_tools, [], role_name)
                continue
            allowed = ', '.join((value.replace('_', '-') for value in expected))
            self.assertEqual(agent_tools, [f'Agent({allowed})'], role_name)

    def test_prompt_bodies_exclude_build_provenance_and_begin_with_operational_content(self):
        for role_name in self.roles:
            bodies = []
            codex_data, codex_body = m2__codex(m2_ROOT / 'projections' / 'codex' / 'agents' / f'{role_name}.toml')
            self.assertFalse((m2_ROOT / 'projections' / 'codex' / 'agents' / f'{role_name}.toml').read_text(encoding='utf-8').startswith('#'))
            self.assertEqual(codex_data['name'], role_name)
            bodies.append(('codex', codex_body))
            for host, filename in (('omp', f'{role_name}.md'), ('claude', f"{role_name.replace('_', '-')}.md")):
                _, body = m2__frontmatter_and_body(m2_ROOT / 'projections' / host / 'agents' / filename)
                bodies.append((host, body))
            bodies.append(('generic', (m2_ROOT / 'projections' / 'generic' / 'agents' / f'{role_name}.md').read_text(encoding='utf-8')))
            for host, body in bodies:
                self.assertTrue(body.startswith('## Purpose\n'), f'{host}:{role_name}')
                for forbidden in m2_FORBIDDEN_PROMPT_PROVENANCE:
                    self.assertNotIn(forbidden, body, f'{host}:{role_name}')
                self.assertNotIn('```json', body, f'{host}:{role_name}')

    def test_projection_manifest_v4_carries_role_contract_metadata(self):
        self.assertEqual(self.manifest['schema'], 'bbk.projection-manifest.v4')
        self.assertEqual(set(self.manifest['agents']), set(self.roles))
        self.assertRegex(self.manifest['role_source_sha256'], '^[0-9a-f]{64}$')
        self.assertRegex(self.manifest['model_routing_source_sha256'], '^[0-9a-f]{64}$')
        for role_name, role in self.roles.items():
            value = self.manifest['agents'][role_name]
            self.assertEqual(value['description'], role['description'])
            self.assertEqual(value['constitution_modules'], role['constitution'])
            self.assertEqual(value['scope'], role['scope'])
            self.assertEqual(value['skills'], role.get('skills', []))
            self.assertEqual(value['autoload_skills'], role.get('autoload_skills', []))
            self.assertEqual(value['spawns'], role.get('spawns', []))
            self.assertEqual(value['delegation'], role['delegation'])
            self.assertEqual(value['escalations'], role['escalations'])
            self.assertEqual(value['user_interaction'], role['user_interaction'])
            self.assertIn(value['model_profile'], {'judgment', 'coordination', 'mechanical'})
            self.assertEqual(set(value['files']), {'codex', 'omp', 'claude', 'generic'})

    def test_profile_procedures_remain_available_while_native_autoload_stays_focused(self):
        for role_name, role in self.roles.items():
            skills = role.get('skills', [])
            autoload_expected = role.get('autoload_skills', [])
            self.assertTrue(set(autoload_expected) <= set(skills), role_name)
            self.assertLessEqual(len(autoload_expected), 3, role_name)
            if role_name in m2_PROFILE_AWARE_ROLES:
                self.assertIn('bbk-installed-profiles', skills, role_name)
                self.assertIn('bbk-profile-routing', skills, role_name)
            else:
                self.assertNotIn('bbk-installed-profiles', skills, role_name)
            omp, _ = m2__frontmatter_and_body(m2_ROOT / 'projections' / 'omp' / 'agents' / f'{role_name}.md')
            autoload = omp.get('autoloadSkills', [])
            if isinstance(autoload, str):
                autoload = [value.strip() for value in autoload.split(',') if value.strip()]
            self.assertEqual(autoload, autoload_expected, role_name)
            claude, _ = m2__frontmatter_and_body(m2_ROOT / 'projections' / 'claude' / 'agents' / f"{role_name.replace('_', '-')}.md")
            claude_skills = claude.get('skills', [])
            if isinstance(claude_skills, str):
                claude_skills = [value.strip() for value in claude_skills.split(',') if value.strip()]
            self.assertEqual(claude_skills, autoload_expected, role_name)

    def test_every_generated_role_prompt_explains_profile_selection_and_propagation(self):
        for role_name in self.roles:
            bodies = []
            _, codex_body = m2__codex(m2_ROOT / 'projections' / 'codex' / 'agents' / f'{role_name}.toml')
            bodies.append(codex_body)
            for host, filename in (('omp', f'{role_name}.md'), ('claude', f"{role_name.replace('_', '-')}.md")):
                _, body = m2__frontmatter_and_body(m2_ROOT / 'projections' / host / 'agents' / filename)
                bodies.append(body)
            bodies.append((m2_ROOT / 'projections' / 'generic' / 'agents' / f'{role_name}.md').read_text(encoding='utf-8'))
            for body in bodies:
                if role_name in m2_PROFILE_AWARE_ROLES:
                    self.assertIn('## Language and domain profiles', body, role_name)
                    self.assertIn('`bbk-installed-profiles`', body, role_name)
                    self.assertIn('`bbk-profile-routing`', body, role_name)
                    self.assertIn('Carry the selected profile identity', body, role_name)
                else:
                    self.assertIn('## Language and domain profile boundary', body, role_name)
                    self.assertIn('return a profile-resolution request to the parent', body, role_name)
                    self.assertNotIn('Consult `bbk-installed-profiles`', body, role_name)

    def test_every_projection_contains_scope_delegation_escalation_and_correct_user_boundary(self):
        for role_name, role in self.roles.items():
            bodies = []
            _, codex_body = m2__codex(m2_ROOT / 'projections' / 'codex' / 'agents' / f'{role_name}.toml')
            bodies.append(('codex', codex_body))
            for host, filename in (('omp', f'{role_name}.md'), ('claude', f"{role_name.replace('_', '-')}.md")):
                _, body = m2__frontmatter_and_body(m2_ROOT / 'projections' / host / 'agents' / filename)
                bodies.append((host, body))
            bodies.append(('generic', (m2_ROOT / 'projections' / 'generic' / 'agents' / f'{role_name}.md').read_text(encoding='utf-8')))
            for host, body in bodies:
                for heading in ('## Constitution', '## Scope', '## Responsibilities', '## Delegation', '## Escalation and user interaction', '## Prohibitions', '## Invocation contract', '## Return contract'):
                    self.assertIn(heading, body, f'{host}:{role_name}')
                for item in role['scope'] + role['escalations']:
                    self.assertIn(item, body, f'{host}:{role_name}')
                if role['interactive']:
                    self.assertIn('direct user questions are limited to', body, f'{host}:{role_name}')
                    for item in role['user_interaction']:
                        self.assertIn(item, body, f'{host}:{role_name}')
                else:
                    self.assertIn('This role is not user-facing', body, f'{host}:{role_name}')

    def test_constitution_is_modular_and_top_level_entry_skill_is_not_autoloaded(self):
        self.assertEqual(self.spec['schema_version'], 'bbk.roles.v2')
        modules = self.spec['constitution_modules']
        self.assertEqual(set(modules), {'core', 'planning', 'coordination', 'execution', 'assurance'})
        entry = (m2_ROOT / 'shared' / 'skills' / 'bbk' / 'SKILL.md').read_text(encoding='utf-8')
        self.assertIn('This skill is for the primary user-facing session', entry)
        self.assertLess(len(entry.split()), 750)
        for role_name, role in self.roles.items():
            self.assertEqual(role['constitution'][0], 'core', role_name)
            self.assertNotIn('bbk', role['skills'], role_name)
            self.assertNotIn('bbk', role['autoload_skills'], role_name)
            self.assertTrue(set(role['autoload_skills']) <= set(role['skills']), role_name)
            self.assertLessEqual(len(role['autoload_skills']), 3, role_name)
            if role['spawns']:
                self.assertIn('coordination', role['constitution'], role_name)
            if role['mutates']:
                self.assertIn('execution', role['constitution'], role_name)
            if role['family'] == 'planning':
                self.assertIn('planning', role['constitution'], role_name)
            if role['family'] == 'review':
                self.assertIn('assurance', role['constitution'], role_name)

    def test_native_skill_preload_budget_is_bounded_and_role_specific(self):
        word_counts = {
            path.parent.name: len(path.read_text(encoding='utf-8').split())
            for path in (m2_ROOT / 'shared' / 'skills').glob('*/SKILL.md')
        }
        for role_name, role in self.roles.items():
            autoload = role['autoload_skills']
            self.assertGreaterEqual(len(autoload), 1, role_name)
            self.assertLessEqual(len(autoload), 3, role_name)
            self.assertLessEqual(sum(word_counts[name] for name in autoload), 2300, role_name)
            if role['spawns']:
                self.assertIn('bbk-context-routing', autoload, role_name)
        self.assertIn('bbk-wayfind', self.roles['bbk_root_wayfinder']['autoload_skills'])
        self.assertIn('bbk-grill', self.roles['bbk_question_guide']['autoload_skills'])
        self.assertIn('bbk-execute', self.roles['bbk_worker']['autoload_skills'])
        self.assertIn('bbk-review', self.roles['bbk_validator']['autoload_skills'])

    def test_every_shared_skill_has_valid_unindented_frontmatter(self):
        for path in sorted((m2_ROOT / 'shared' / 'skills').glob('*/SKILL.md')):
            text = path.read_text(encoding='utf-8')
            self.assertTrue(text.startswith('---\n'), str(path.relative_to(m2_ROOT)))
            self.assertGreaterEqual(text.count('---'), 2, str(path.relative_to(m2_ROOT)))
            self.assertIn(f"name: {path.parent.name}", text.split('---', 2)[1], str(path.relative_to(m2_ROOT)))

    def test_all_shared_skills_define_profile_interaction_without_embedding_inventory(self):
        paths = sorted((m2_ROOT / 'shared' / 'skills').glob('*/SKILL.md'))
        self.assertEqual(len(paths), 24)
        for path in paths:
            text = path.read_text(encoding='utf-8')
            self.assertRegex(text.lower(), '\\bprofiles?\\b', str(path.relative_to(m2_ROOT)))
        placeholder = (m2_ROOT / 'shared' / 'skills' / 'bbk-installed-profiles' / 'SKILL.md').read_text(encoding='utf-8')
        self.assertIn('package-source placeholder', placeholder)
        self.assertIn('No language or domain profile is managed', placeholder)
        self.assertNotIn('### `rust@', placeholder)

    def test_current_docs_explain_delegation_registry_and_prompt_metadata_boundary(self):
        combined = '\n'.join(((m2_ROOT / relative).read_text(encoding='utf-8') for relative in ('README.md', 'docs/AGENTS.md', 'docs/INSTALL.md', 'docs/LANGUAGE-PROFILES.md', 'docs/MODEL-ROUTING.md', 'docs/USAGE.md')))
        for expected in ('bbk-installed-profiles', 'effective-language-profiles.json', 'bbk --json profile list', 'spawns', 'Delegation', 'projections/manifest.json'):
            self.assertIn(expected, combined)
        self.assertIn('prompt', combined.lower())
        self.assertIn('provenance', combined.lower())

    def test_install_specific_registry_selects_compact_router_and_records_capabilities(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'profile'
            (root / 'skills' / 'bbk-rust').mkdir(parents=True)
            (root / 'skills' / 'rust-review').mkdir(parents=True)
            (root / 'skills' / 'bbk-rust' / 'SKILL.md').write_text('---\nname: bbk-rust\ndescription: Rust profile router.\n---\n\n# Router\n', encoding='utf-8')
            (root / 'skills' / 'rust-review' / 'SKILL.md').write_text('---\nname: rust-review\ndescription: Focused Rust review.\n---\n\n# Review\n', encoding='utf-8')
            item = _DummyProfile(root=root, profile={'id': 'rust', 'version': '0.1.0-alpha.3', 'name': 'Rust', 'description': 'Qualified Rust procedures.', 'package': 'bbk-profile-rust', 'installation': {'skill_root': 'skills', 'cli': 'tools/rust_profile.py'}, 'capabilities': {'test': {'status': 'supported'}, 'mutation': {'status': 'conditional'}}})
            data = profile_registry.registry_data([item], bbk_version='0.1.0-alpha.11.11')
            profile = data['profiles'][0]
            self.assertEqual(profile['router_skill'], 'bbk-rust')
            self.assertEqual(profile['cli_command'], 'rust-profile')
            self.assertEqual(profile['skill_count'], 2)
            text = profile_registry.registry_skill_text([item], bbk_version='0.1.0-alpha.11.11')
            self.assertIn('### `rust@0.1.0-alpha.3` — Rust', text)
            self.assertIn('Router skill: `bbk-rust`', text)
            self.assertIn('test=supported', text)
            self.assertIn('mutation=conditional', text)
            self.assertNotIn('rust-review', text, 'focused skill inventories should not bloat every autoloaded registry')

# ---------------------------------------------------------------------------
# Alpha.11.8 Wayfinding, durable-handoff, and execution-continuity corrections
# ---------------------------------------------------------------------------
import hashlib as a118_hashlib
import json as a118_json
import os as a118_os
import subprocess as a118_subprocess
import sys as a118_sys
import tempfile as a118_tempfile
import unittest as a118_unittest
from pathlib import Path as A118Path

A118_ROOT = A118Path(__file__).resolve().parents[1]
A118_BBK = A118_ROOT / "tools" / "bbk.py"


class Alpha118WayfindingExecutionTests(a118_unittest.TestCase):
    def run_cli(self, *args: str, cwd: A118Path | None = None, check: bool = True, env: dict[str, str] | None = None) -> dict:
        child_env = a118_os.environ.copy()
        child_env["PYTHONDONTWRITEBYTECODE"] = "1"
        if env:
            child_env.update(env)
        result = a118_subprocess.run(
            [a118_sys.executable, str(A118_BBK), "--json", *args],
            cwd=str(cwd or A118_ROOT),
            env=child_env,
            stdout=a118_subprocess.PIPE,
            stderr=a118_subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if check and result.returncode != 0:
            self.fail(f"CLI failed ({result.returncode}): {result.stderr}\n{result.stdout}")
        return a118_json.loads(result.stdout)

    def test_wayfinding_topology_is_complete_and_question_guide_is_escalation_only(self) -> None:
        catalogue = a118_json.loads((A118_ROOT / "spec" / "roles.json").read_text(encoding="utf-8"))
        by_id = {role["id"]: role for role in catalogue["roles"]}
        by_name = {role["name"]: role for role in catalogue["roles"]}
        for role_id in (
            "root_wayfinder", "territory_wayfinder", "questioning_wayfinder",
            "planning_wayfinder", "phase_wayfinder",
        ):
            self.assertIn("bbk-wayfind", by_id[role_id]["skills"])
        self.assertIn("bbk-grill", by_id["question_guide"]["skills"])
        self.assertFalse(by_id["territory_wayfinder"]["interactive"])
        for parent in ("root_wayfinder", "territory_wayfinder"):
            self.assertIn("bbk_questioning_wayfinder", by_id[parent]["spawns"])
            self.assertIn("bbk_planning_wayfinder", by_id[parent]["spawns"])
            self.assertNotIn("bbk_question_guide", by_id[parent]["spawns"])
        questioning = "\n".join(by_id["questioning_wayfinder"]["responsibilities"] + by_id["questioning_wayfinder"]["prohibitions"])
        self.assertIn("accepted recommendation becomes the decision packet without spawning a Question Guide", questioning)
        self.assertIn("Do not create a Question Guide for every", questioning)
        guide = "\n".join(by_id["question_guide"]["responsibilities"] + by_id["question_guide"]["prohibitions"])
        self.assertIn("rejection keeps the question active", guide)
        reachable: set[str] = set()
        stack = ["bbk_root_wayfinder"]
        while stack:
            current = stack.pop()
            if current in reachable:
                continue
            reachable.add(current)
            stack.extend(by_name[current]["spawns"])
        self.assertEqual(reachable, set(by_name))

    def test_wayfinding_and_grill_procedures_preserve_dynamic_method(self) -> None:
        wayfind = (A118_ROOT / "shared" / "skills" / "bbk-wayfind" / "SKILL.md").read_text(encoding="utf-8")
        grill = (A118_ROOT / "shared" / "skills" / "bbk-grill" / "SKILL.md").read_text(encoding="utf-8")
        for phrase in ("frontier", "blocker", "fog", "information value", "invalidation", "synthesize"):
            self.assertIn(phrase, wayfind.lower())
        for phrase in ("one material question at a time", "reflect", "challenge", "reject", "root question"):
            self.assertIn(phrase, grill.lower())
        self.assertIn("escalation path, not ceremony for every decision", grill.lower())

    def test_durable_question_branch_preserves_rejection_and_resolution_semantics(self) -> None:
        with a118_tempfile.TemporaryDirectory() as raw:
            root = A118Path(raw)
            self.run_cli("init", "--root", str(root), "--title", "Questions", "--project-id", "BBK-QUESTIONS")
            created = self.run_cli(
                "question", "new", "--root", str(root), "--id", "Q-ARCH",
                "--root-decision", "Which provider contract should the harness adopt?",
            )
            path = root / created["path"]
            branch = a118_json.loads(path.read_text(encoding="utf-8"))
            branch["current_recommendation"] = "Adopt provider contract A."
            branch["proposal_response"] = "REJECT"
            branch["unresolved_point"] = "The third-provider adapter may require a different lifecycle boundary."
            branch["next_action"] = "Open one Question Guide for the contested lifecycle trade-off."
            branch["updated_at"] = "2026-07-29T00:00:00Z"
            path.write_text(a118_json.dumps(branch, indent=2) + "\n", encoding="utf-8")
            open_result = self.run_cli("question", "validate", str(path))
            self.assertTrue(open_result["valid"])
            branch["root_disposition"] = "RESOLVED"
            branch["status"] = "RESOLVED"
            branch["accepted_decision"] = "Adopt provider contract B."
            path.write_text(a118_json.dumps(branch, indent=2) + "\n", encoding="utf-8")
            invalid = self.run_cli("question", "validate", str(path), check=False)
            self.assertFalse(invalid["valid"])
            self.assertTrue(any("keeps the root question open" in item or "requires proposal_response APPROVE" in item for item in invalid["errors"]))
            branch["proposal_response"] = "APPROVE"
            path.write_text(a118_json.dumps(branch, indent=2) + "\n", encoding="utf-8")
            resolved = self.run_cli("question", "validate", str(path))
            self.assertTrue(resolved["valid"])
            listed = self.run_cli("question", "list", "--root", str(root), "--status", "RESOLVED")
            self.assertEqual(listed["count"], 1)
            self.assertEqual(listed["questions"][0]["id"], "Q-ARCH")

    def test_durable_handoff_is_lossless_and_beads_projection_is_compact(self) -> None:
        with a118_tempfile.TemporaryDirectory() as raw:
            root = A118Path(raw)
            self.run_cli("init", "--root", str(root), "--title", "Handoff", "--project-id", "BBK-HANDOFF")
            payload = root / "out" / "large.json"
            payload.parent.mkdir(parents=True)
            payload.write_text('{"payload":"' + ("x" * 70000) + '"}\n', encoding="utf-8")
            created = self.run_cli(
                "handoff", "create", "--root", str(root),
                "--work-unit", "WU-HANDOFF", "--attempt", "2",
                "--disposition", "PARTIAL", "--summary", "Host window ended after implementation.",
                "--artifact", "out/large.json", "--continuation-state", "READY",
                "--checkpoint", "out/large.json", "--completed-step", "implementation",
                "--next-step", "focused validation", "--next-action", "Resume the same worker thread and run focused validation.",
            )
            self.assertTrue(created["valid"])
            handoff = root / created["handoff"]["path"]
            self.assertEqual(created["references"][0]["bytes"], payload.stat().st_size)
            self.assertEqual(created["references"][0]["sha256"], a118_hashlib.sha256(payload.read_bytes()).hexdigest())
            plan = self.run_cli(
                "beads", "handoff-plan", "--root", str(root),
                "--handoff", str(handoff), "--bead", "bd-123",
            )
            self.assertTrue(plan["dry_run"])
            self.assertLess(len(plan["note"].encode("utf-8")), 2048)
            self.assertIn(created["handoff"]["sha256"], plan["note"])
            self.assertEqual(plan["argv"][:4], ["bd", "comments", "add", "bd-123"])
            listed = self.run_cli("handoff", "list", "--root", str(root), "--work-unit", "WU-HANDOFF", "--latest")
            self.assertEqual(listed["count"], 1)
            self.assertEqual(listed["latest"]["sha256"], created["handoff"]["sha256"])
            self.assertEqual(listed["latest"]["path"], created["handoff"]["path"])
            payload.write_text("tampered\n", encoding="utf-8")
            failed = self.run_cli("handoff", "verify", str(handoff), "--root", str(root), check=False)
            self.assertFalse(failed["valid"])
            self.assertTrue(any("mismatch" in error for error in failed["errors"]))

    @a118_unittest.skipIf(a118_os.name == "nt", "mock POSIX bd executable is covered by Windows-safe dry-run tests")
    def test_beads_handoff_apply_is_explicit_compact_and_write_gated(self) -> None:
        with a118_tempfile.TemporaryDirectory() as raw:
            root = A118Path(raw) / "project"
            self.run_cli("init", "--root", str(root), "--title", "Beads", "--project-id", "BBK-BEADS")
            artifact = root / "result.txt"
            artifact.write_text("result\n", encoding="utf-8")
            created = self.run_cli(
                "handoff", "create", "--root", str(root), "--work-unit", "WU-BEADS",
                "--attempt", "1", "--disposition", "COMPLETE", "--summary", "Done.",
                "--artifact", "result.txt", "--continuation-state", "NOT_REQUIRED",
                "--next-action", "Validate the exact result.",
            )
            handoff = root / created["handoff"]["path"]
            blocked = self.run_cli(
                "beads", "handoff-plan", "--root", str(root), "--handoff", str(handoff),
                "--bead", "bd-apply", "--apply", check=False,
            )
            self.assertEqual(blocked["status"], "ERROR")
            mapping_path = root / ".bbk" / "mappings" / "beads.json"
            mapping = a118_json.loads(mapping_path.read_text(encoding="utf-8"))
            mapping.update({"enabled": True, "write_enabled": True, "workspace": str(root)})
            mapping_path.write_text(a118_json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
            bindir = A118Path(raw) / "bin"
            bindir.mkdir()
            log = A118Path(raw) / "bd.log"
            executable = bindir / "bd"
            executable.write_text(
                "#!/usr/bin/env python3\n"
                "import os, pathlib, sys\n"
                "pathlib.Path(os.environ['BBK_TEST_BD_LOG']).write_text('\\n'.join(sys.argv[1:]), encoding='utf-8')\n",
                encoding="utf-8",
            )
            executable.chmod(0o755)
            applied = self.run_cli(
                "beads", "handoff-plan", "--root", str(root), "--handoff", str(handoff),
                "--bead", "bd-apply", "--apply",
                env={"PATH": str(bindir) + a118_os.pathsep + a118_os.environ.get("PATH", ""), "BBK_TEST_BD_LOG": str(log)},
            )
            self.assertTrue(applied["applied"])
            self.assertFalse(applied["dry_run"])
            recorded = log.read_text(encoding="utf-8")
            self.assertIn("comments\nadd\nbd-apply", recorded)
            self.assertIn(created["handoff"]["sha256"], recorded)
            self.assertLess(len(applied["note"].encode("utf-8")), 4096)

    def test_gate_output_is_spooled_losslessly_and_reuse_is_content_bound(self) -> None:
        with a118_tempfile.TemporaryDirectory() as raw:
            root = A118Path(raw)
            self.run_cli("init", "--root", str(root), "--title", "Gate output", "--project-id", "BBK-GATE-OUTPUT")
            payload_bytes = (2 * 1024 * 1024) + 257
            command = (
                "import sys; "
                f"sys.stdout.buffer.write(b'A'*{payload_bytes} + b'BBK-TAIL'); "
                "sys.stderr.buffer.write(b'ERR-TAIL')"
            )
            gates = {
                "schema": "bbk.gates.v1",
                "prevalidation": {"allow_empty": True},
                "gates": [{
                    "id": "large-output",
                    "description": "produce output beyond the preview ceiling",
                    "enabled": True,
                    "phases": ["prefreeze"],
                    "command": [a118_sys.executable, "-c", command],
                    "cwd": ".",
                    "blocking": True,
                    "requires": [A118Path(a118_sys.executable).name],
                    "assertions": ["lossless-output"],
                }],
            }
            (root / ".bbk" / "gates.json").write_text(a118_json.dumps(gates), encoding="utf-8")
            first = self.run_cli("gate", "run", "--root", str(root), "--phase", "prefreeze")
            result = first["results"][0]
            self.assertEqual(result["status"], "PASS")
            self.assertTrue(result["stdout_truncated"])
            self.assertEqual(result["output_transport"], "file-bytes-sha256")
            stdout_path = root / result["stdout_file"]["path"]
            stderr_path = root / result["stderr_file"]["path"]
            stdout_raw = stdout_path.read_bytes()
            stderr_raw = stderr_path.read_bytes()
            self.assertTrue(stdout_raw.endswith(b"BBK-TAIL"))
            self.assertEqual(stderr_raw, b"ERR-TAIL")
            self.assertEqual(result["stdout_file"]["bytes"], len(stdout_raw))
            self.assertEqual(result["stdout_file"]["sha256"], a118_hashlib.sha256(stdout_raw).hexdigest())
            self.assertEqual(result["stderr_file"]["sha256"], a118_hashlib.sha256(stderr_raw).hexdigest())
            second = self.run_cli("gate", "run", "--root", str(root), "--phase", "prefreeze")
            self.assertTrue(second["results"][0]["reused"])
            stdout_path.write_bytes(b"tampered")
            third = self.run_cli("gate", "run", "--root", str(root), "--phase", "prefreeze")
            self.assertFalse(third["results"][0]["reused"])
            restored = stdout_path.read_bytes()
            self.assertTrue(restored.endswith(b"BBK-TAIL"))
            self.assertEqual(third["results"][0]["stdout_file"]["sha256"], a118_hashlib.sha256(restored).hexdigest())

    def test_schema_validator_is_discoverable_and_uses_draft_2020_12(self) -> None:
        status = self.run_cli("schema", "status")
        self.assertEqual(status["draft"], "2020-12")
        self.assertIn("ensure_command", status)
        schema = A118_ROOT / "spec" / "schemas" / "bbk-handoff-v1.schema.json"
        instance = A118_ROOT / "templates" / "handoff.json"
        result = self.run_cli("schema", "validate", "--schema", str(schema), "--instance", str(instance), check=False)
        if result["status"] == "BLOCKED":
            self.assertIn("--ensure", result["remediation"])
        else:
            self.assertTrue(result["valid"], result)
            self.assertEqual(result["draft"], "2020-12")

    def test_worker_execution_window_is_logical_resumable_and_not_fake_host_metadata(self) -> None:
        with a118_tempfile.TemporaryDirectory() as raw:
            root = A118Path(raw)
            self.run_cli("init", "--root", str(root), "--title", "Runtime", "--project-id", "BBK-RUNTIME")
            config = a118_json.loads((root / ".bbk" / "config.json").read_text(encoding="utf-8"))
            execution = config["execution"]
            self.assertEqual(execution["worker_window"], "extended")
            self.assertTrue(execution["resume_same_thread"])
            self.assertTrue(execution["durable_handoffs"])
            self.assertEqual(execution["large_result_transport"], "file-bytes-sha256")
            self.assertEqual(execution["infrastructure_continuations"], 6)
            work_template = a118_json.loads((A118_ROOT / "templates" / "work-unit.json").read_text(encoding="utf-8"))
            self.assertEqual(work_template["executionBudget"]["mode"], "extended-resumable")
            self.assertEqual(work_template["executionBudget"]["infrastructureContinuations"], 6)
            mapping = a118_json.loads((root / ".bbk" / "map.json").read_text(encoding="utf-8"))
            for field in ("posture", "frontier", "blockers", "fog", "stopping_assessment"):
                self.assertIn(field, mapping)
        roles = a118_json.loads((A118_ROOT / "spec" / "roles.json").read_text(encoding="utf-8"))["roles"]
        by_id = {role["id"]: role for role in roles}
        worker_text = "\n".join(by_id["worker"]["responsibilities"])
        orchestrator_text = "\n".join(by_id["worker_orchestrator"]["responsibilities"])
        self.assertIn("continue beyond preflight", worker_text)
        self.assertIn("same-thread", orchestrator_text)
        for path in (A118_ROOT / "projections" / "codex" / "agents").glob("*.toml"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("timeout =", text)
            self.assertNotIn("max_turns =", text)

    def test_profile_registry_records_exact_cli_fallback(self) -> None:
        source = (A118_ROOT / "shared" / "skills" / "bbk-installed-profiles" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("python tools/bbk.py", source)
        self.assertIn("Do not classify profile discovery as unavailable", source)
        registry_source = (A118_ROOT / "tools" / "profile_registry.py").read_text(encoding="utf-8")
        self.assertIn('"bbk_cli"', registry_source)
        self.assertIn("Exact fallback when `bbk` is not on `PATH`", registry_source)

    def test_public_test_suite_is_consolidated(self) -> None:
        paths = sorted((A118_ROOT / "tests").glob("test*.py"))
        self.assertEqual([path.name for path in paths], [
            "test_assurance_state.py",
            "test_core_contracts.py",
            "test_installation_portability.py",
            "test_omp_runtime.py",
            "test_system.py",
        ])
        self.assertFalse(any("alpha" in path.name for path in paths))

    def test_method_and_schema_surfaces_include_new_contracts(self) -> None:
        methods = a118_json.loads((A118_ROOT / "spec" / "method-content.json").read_text(encoding="utf-8"))
        self.assertEqual(len(methods["skills"]), 24)
        self.assertEqual(len(methods["references"]), 22)
        for name in ("bbk-wayfind", "bbk-grill", "bbk-handoff"):
            self.assertIn(name, methods["skills"])
        self.assertIn("handoff.md", methods["references"])
        self.assertIn("question-branch.md", methods["references"])
        self.assertTrue((A118_ROOT / "spec" / "schemas" / "bbk-handoff-v1.schema.json").is_file())
        self.assertTrue((A118_ROOT / "spec" / "schemas" / "bbk-question-branch-v1.schema.json").is_file())
        self.assertTrue((A118_ROOT / "templates" / "handoff.json").is_file())
        self.assertTrue((A118_ROOT / "templates" / "question-branch.json").is_file())

    def test_standing_authority_capability_zones_and_worker_contract_are_projected(self) -> None:
        catalogue = a118_json.loads((A118_ROOT / "spec" / "roles.json").read_text(encoding="utf-8"))
        by_id = {role["id"]: role for role in catalogue["roles"]}
        for role_id in (
            "root_wayfinder", "planning_wayfinder", "phase_wayfinder",
            "worker_designer", "root_orchestrator", "territory_orchestrator",
            "worker_orchestrator", "worker",
        ):
            text = "\n".join(by_id[role_id]["responsibilities"] + by_id[role_id]["prohibitions"]).lower()
            self.assertIn("standing", text, role_id)
            self.assertIn("authority", text, role_id)
        worker = "\n".join(by_id["worker"]["responsibilities"] + by_id["worker"]["prohibitions"])
        self.assertIn("When writing code, follow YAGNI principles, and one-liner solutions.", worker)
        for phrase in (
            "disposable candidate root", "protected worktree", "sealed or historical evidence",
            "BLOCKED_TECHNICAL", "PAUSED_CAPACITY", "PAUSED_HOST_WINDOW",
            "silent truncation", "structured result",
        ):
            self.assertIn(phrase.lower(), worker.lower())
        orchestration = "\n".join(
            item
            for role_id in ("root_orchestrator", "territory_orchestrator", "worker_orchestrator", "validator_orchestrator")
            for item in by_id[role_id]["responsibilities"] + by_id[role_id]["prohibitions"]
        )
        for phrase in (
            "USER_CANCELLED", "CONFIRMED_HANG", "OBSOLETE_WORK",
            "polling", "heartbeat", "completed", "active-slot accounting",
            "host-level physical thread reclamation",
        ):
            self.assertIn(phrase, orchestration)
        self.assertNotIn("Use heartbeat/deadline checks", orchestration)
        codex_worker = (A118_ROOT / "projections" / "codex" / "agents" / "bbk_worker.toml").read_text(encoding="utf-8")
        omp_worker = (A118_ROOT / "projections" / "omp" / "agents" / "bbk_worker.md").read_text(encoding="utf-8")
        generic_worker = (A118_ROOT / "projections" / "generic" / "agents" / "bbk_worker.md").read_text(encoding="utf-8")
        claude_worker = (A118_ROOT / "projections" / "claude" / "agents" / "bbk-worker.md").read_text(encoding="utf-8")
        for projection in (codex_worker, omp_worker, generic_worker, claude_worker):
            self.assertIn("When writing code, follow YAGNI principles, and one-liner solutions.", projection)
            self.assertIn("BLOCKED_AUTHORITY", projection)
            self.assertIn("capability zone", projection.lower())

    def test_work_unit_execution_control_contract_is_schema_valid(self) -> None:
        work = a118_json.loads((A118_ROOT / "templates" / "work-unit.json").read_text(encoding="utf-8"))
        self.assertTrue(work["authorityGrant"]["standing"])
        self.assertEqual(
            [zone["kind"] for zone in work["capabilityZones"]],
            ["disposable-candidate-root", "protected-worktree", "sealed-evidence"],
        )
        self.assertFalse(work["payloadLimits"]["silentTruncationAllowed"])
        self.assertEqual(work["interruptPolicy"]["heartbeatSemantics"], "informational")
        self.assertEqual(work["interruptPolicy"]["waitTimeoutSemantics"], "polling-only")
        self.assertIn("BLOCKED_DECISION", work["returnContract"]["operationalDispositions"])
        result = self.run_cli(
            "schema", "validate",
            "--schema", str(A118_ROOT / "spec" / "schemas" / "work-unit.schema.json"),
            "--instance", str(A118_ROOT / "templates" / "work-unit.json"),
            check=False,
        )
        if result["status"] == "BLOCKED":
            self.assertIn("--ensure", result["remediation"])
        else:
            self.assertTrue(result["valid"], result)

    def test_handoff_supports_precise_pause_block_and_interrupt_records(self) -> None:
        with a118_tempfile.TemporaryDirectory() as raw:
            project = A118Path(raw)
            self.run_cli("init", "--root", str(project), "--title", "Control", "--project-id", "BBK-CONTROL")
            artifact = project / "result.bin"
            artifact.write_bytes(b"exact-result")
            paused = self.run_cli(
                "handoff", "create", "--root", str(project),
                "--work-unit", "WU-CONTROL", "--attempt", "1",
                "--disposition", "PAUSED_HOST_WINDOW",
                "--summary", "Host window ended at a verified checkpoint.",
                "--authority-source", "standing user authorization",
                "--authority-scope", "result.bin",
                "--capability-zone", "protected-worktree=.",
                "--artifact", "result.bin",
                "--continuation-state", "READY",
                "--checkpoint", "result.bin",
                "--next-action", "Continue the same worker thread.",
            )
            handoff_path = project / paused["handoff"]["path"]
            value = a118_json.loads(handoff_path.read_text(encoding="utf-8"))
            self.assertEqual(value["disposition"], "PAUSED_HOST_WINDOW")
            self.assertTrue(value["authority"]["standing"])
            self.assertEqual(value["capability_zones_used"][0]["kind"], "protected-worktree")
            self.assertIsNone(value["interrupt"])
            self.assertTrue(self.run_cli("handoff", "verify", str(handoff_path), "--root", str(project))["valid"])
            missing_evidence = self.run_cli(
                "handoff", "create", "--root", str(project),
                "--work-unit", "WU-CONTROL", "--attempt", "2",
                "--disposition", "CANCELLED", "--summary", "Cancelled.",
                "--interrupt-reason", "USER_CANCELLED",
                "--next-action", "Preserve partial work.",
                check=False,
            )
            self.assertEqual(missing_evidence["status"], "ERROR")
            self.assertIn("interrupt-evidence", missing_evidence["error"])

    def test_release_notes_describe_repository_native_documentation_boundary(self) -> None:
        top = (A118_ROOT / "RELEASE-NOTES.md").read_text(encoding="utf-8")
        index = (A118_ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        self.assertFalse((A118_ROOT / "docs" / "RELEASE-NOTES.md").exists())
        for expected in ("Repository-native source", "14 current", "pre-public history", "No `.bbk/` project-record migration"):
            self.assertIn(expected, top)
        self.assertIn("[`RELEASE-NOTES.md`](../RELEASE-NOTES.md)", index)

    def test_usage_documents_tested_codex_multi_agent_contract(self) -> None:
        usage = (A118_ROOT / "docs" / "USAGE.md").read_text(encoding="utf-8")
        for expected in (
            "[features.multi_agent_v2]",
            "max_concurrent_threads_per_session = 32",
            "max_wait_timeout_ms = 3600000",
            'fork_turns: "none"',
            "A wait_agent timeout is only a parent polling deadline.",
            "Never call interrupt_agent merely because of elapsed time",
            "use followup_task if additional work is needed",
            "Preserve partial work whenever doing so is safe.",
        ):
            self.assertIn(expected, usage)
        self.assertIn("version-sensitive", usage.lower())

    def test_execution_procedure_rejects_silence_as_interrupt_evidence(self) -> None:
        execute = (A118_ROOT / "shared" / "skills" / "bbk-execute" / "SKILL.md").read_text(encoding="utf-8")
        handoff = (A118_ROOT / "shared" / "skills" / "bbk-handoff" / "SKILL.md").read_text(encoding="utf-8")
        for expected in (
            "A wait timeout is a parent polling deadline only",
            "absence of a heartbeat",
            "USER_CANCELLED",
            "CONFIRMED_HANG",
            "completed, failed, or already-interrupted",
            "bbk manifest create",
            "bbk candidate freeze",
        ):
            self.assertIn(expected, execute)
        for expected in (
            "BLOCKED_TECHNICAL", "BLOCKED_AUTHORITY", "BLOCKED_DECISION",
            "PAUSED_CAPACITY", "PAUSED_HOST_WINDOW", "timed out", "slot needed",
        ):
            self.assertIn(expected, handoff)

