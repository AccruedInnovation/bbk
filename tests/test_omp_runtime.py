"""Consolidated BBK regression tests grouped by responsibility.

Historical release-specific modules were merged to keep the public repository
readable while retaining their behavioral coverage.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Historical source: test_alpha11_3_omp_model_menu.py
# ---------------------------------------------------------------------------
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
m1_ROOT = Path(__file__).resolve().parents[1]
m1_INSTALL = m1_ROOT / 'tools' / 'install.py'
m1_ROUTING = m1_ROOT / 'tools' / 'omp_model_routing.py'
m1_PROFILES = m1_ROOT / 'spec' / 'omp-model-routing-profiles.json'
m1_TEMPLATE = m1_ROOT / 'templates' / 'omp-model-routing-profile.json'

def m1_run(command, *, env=None, cwd=m1_ROOT, check=True):
    return subprocess.run([str(value) for value in command], cwd=str(cwd), env=env, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')

def m1_run_json(command, *, env=None, cwd=m1_ROOT, check=True):
    result = m1_run(command, env=env, cwd=cwd, check=check)
    return (json.loads(result.stdout), result)

def m1_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding='utf-8')
    raw = text.split('---\n', 2)[1]
    result = {}
    for line in raw.splitlines():
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        try:
            parsed = json.loads(value.strip())
        except json.JSONDecodeError:
            parsed = value.strip()
        result[key] = parsed
    return result

class Alpha113OmpModelMenuTests(unittest.TestCase):

    def test_bundled_profiles_cover_every_role_and_include_requested_cost_modes(self):
        value = json.loads(m1_PROFILES.read_text(encoding='utf-8'))
        roles = {item['name'] for item in json.loads((m1_ROOT / 'spec' / 'roles.json').read_text(encoding='utf-8'))['roles']}
        self.assertEqual(value['schema_version'], 'bbk.omp-model-routing-profiles.v1')
        self.assertEqual(value['package_version'], '0.1.0-alpha.11.11')
        self.assertEqual(set(value['profiles']), {'default', 'testing-flash', 'deepseek-economy'})
        for profile in value['profiles'].values():
            self.assertEqual(set(profile['roles']), roles)
        testing = value['profiles']['testing-flash']['roles']
        self.assertEqual({route['model'] for route in testing.values()}, {'deepseek/deepseek-v4-flash'})
        economy = value['profiles']['deepseek-economy']['roles']
        self.assertTrue(all((route['model'].startswith('deepseek/') for route in economy.values())))
        self.assertIn('deepseek/deepseek-v4-pro', {route['model'] for route in economy.values()})
        self.assertIn('deepseek/deepseek-v4-flash', {route['model'] for route in economy.values()})

    def test_template_is_compact_and_valid_for_runtime_application(self):
        value = json.loads(m1_TEMPLATE.read_text(encoding='utf-8'))
        self.assertEqual(value['schema_version'], 'bbk.omp-model-routing-profile.v1')
        self.assertEqual(value['package_version'], '0.1.0-alpha.11.11')
        self.assertEqual(set(value['default']), {'model', 'thinkingLevel'})
        canonical = {item['name'] for item in json.loads((m1_ROOT / 'spec' / 'roles.json').read_text(encoding='utf-8'))['roles']}
        self.assertLessEqual(set(value['roles']), canonical)

    def test_install_apply_menu_profiles_manifest_status_and_uninstall_round_trip(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            home = base / 'home'
            home.mkdir()
            env = os.environ.copy()
            env.update({'BBK_HOME': str(home), 'HOME': str(home), 'BBK_INSTALL_ROOT': str(base / 'data'), 'BBK_BIN_DIR': str(base / 'bin')})
            installed, _ = m1_run_json([sys.executable, m1_INSTALL, '--json', 'install', '--scope', 'user', '--omp', '--no-language-profiles'], env=env)
            extension = home / '.omp' / 'agent' / 'extensions' / 'bbk'
            binding = json.loads((extension / 'bbk-package-root.json').read_text(encoding='utf-8'))
            self.assertEqual(binding['schema'], 'bbk.omp-package-binding.v2')
            self.assertTrue((extension / 'omp_model_routing.py').is_file())
            self.assertTrue(Path(binding['state_path']).is_file())
            status, _ = m1_run_json([sys.executable, extension / 'omp_model_routing.py', '--json', 'status'], env=env)
            self.assertEqual(status['active_profile'], 'installation-default')
            self.assertEqual(len(status['roles']), 19)
            self.assertEqual(status['route_surface'], 'bbk-managed-agent-frontmatter')
            self.assertIn('task.agentModelOverrides', status['precedence_note'])
            script = base / 'model-menu.mjs'
            script.write_text(textwrap.dedent(f"\n                const chain = () => ({{ optional() {{ return this; }} }});\n                const z = {{ object: value => value, string: chain, boolean: chain,\n                  enum: values => chain(), array: value => chain() }};\n                const commands = new Map(), messages = [], userMessages = [], notifications = [];\n                const pi = {{ zod: {{ z }}, setLabel() {{}}, registerTool() {{}}, on() {{}},\n                  registerCommand(name, value) {{ commands.set(name, value); }},\n                  sendMessage(value) {{ messages.push(value); }},\n                  sendUserMessage(value) {{ userMessages.push(value); }} }};\n                const mod = await import({json.dumps((extension / 'index.js').as_uri())});\n                mod.default(pi);\n                const command = commands.get('bbk:models');\n                if (!command) throw new Error('missing bbk:models');\n                const ui = {{\n                  async select(title, options) {{\n                    if (title.includes('sub-agent model routing')) return 'Apply a routing profile';\n                    if (title === 'Routing profile') return options.find(value => value.startsWith('testing-flash'));\n                    throw new Error(`unexpected select ${{title}}`);\n                  }},\n                  async confirm() {{ return true; }},\n                  notify(message, level) {{ notifications.push({{message, level}}); }},\n                }};\n                const result = await command.handler('', {{cwd: {json.dumps(str(base))}, hasUI: true, ui, models: {{list() {{ return []; }}}}}});\n                console.log(JSON.stringify({{\n                  resultIsUndefined: result === undefined,\n                  messages: messages.length,\n                  userMessages: userMessages.length,\n                  notifications: notifications.length,\n                }}));\n            "), encoding='utf-8')
            menu = json.loads(m1_run(['node', script], env=env).stdout)
            self.assertTrue(menu['resultIsUndefined'])
            self.assertEqual(menu['messages'], 0)
            self.assertEqual(menu['userMessages'], 0)
            self.assertGreaterEqual(menu['notifications'], 1)
            routed, _ = m1_run_json([sys.executable, extension / 'omp_model_routing.py', '--json', 'status'], env=env)
            self.assertEqual(routed['active_profile'], 'testing-flash')
            self.assertEqual({route['model'] for route in routed['roles'].values()}, {'deepseek/deepseek-v4-flash'})
            agents = home / '.omp' / 'agent' / 'agents'
            for role in status['roles']:
                meta = m1_frontmatter(agents / f'{role}.md')
                self.assertEqual(meta['model'], 'deepseek/deepseek-v4-flash')
                self.assertEqual(meta['thinkingLevel'], 'high')
            install_status, _ = m1_run_json([sys.executable, m1_INSTALL, '--json', 'status', '--scope', 'user'], env=env)
            self.assertEqual(install_status['summary'], {'current': len(install_status['files'])})
            self.assertEqual(install_status['omp_runtime_routing']['active_profile'], 'testing-flash')
            custom, _ = m1_run_json([sys.executable, extension / 'omp_model_routing.py', '--json', 'set-role', 'bbk_worker', '--model', '@task', '--thinking-level', 'medium'], env=env)
            self.assertEqual(custom['active_profile'], 'custom')
            self.assertEqual(m1_frontmatter(agents / 'bbk_worker.md')['model'], '@task')
            exported = base / 'exported-routing.json'
            export_result, _ = m1_run_json([sys.executable, extension / 'omp_model_routing.py', '--json', 'export', exported, '--id', 'round-trip'], env=env)
            self.assertEqual(export_result['status'], 'EXPORTED')
            exported_value = json.loads(exported.read_text(encoding='utf-8'))
            self.assertEqual(exported_value['id'], 'round-trip')
            exported_value['id'] = 'file-profile'
            exported_value['description'] = 'Applied from a compact external profile file.'
            exported.write_text(json.dumps(exported_value, indent=2) + '\n', encoding='utf-8')
            from_file, _ = m1_run_json([sys.executable, extension / 'omp_model_routing.py', '--json', 'apply-file', exported], env=env)
            self.assertEqual(from_file['active_profile'], 'file-profile')
            self.assertEqual(from_file['routes']['bbk_worker']['model'], '@task')
            economy, _ = m1_run_json([sys.executable, extension / 'omp_model_routing.py', '--json', 'apply-profile', 'deepseek-economy'], env=env)
            self.assertEqual(economy['active_profile'], 'deepseek-economy')
            self.assertTrue(all((route['model'].startswith('deepseek/') for route in economy['routes'].values())))
            removed, _ = m1_run_json([sys.executable, m1_INSTALL, '--json', 'uninstall', '--scope', 'user'], env=env)
            self.assertFalse(removed['preserved'])
            self.assertFalse(Path(installed['manifest_path']).exists())

    def test_runtime_router_refuses_locally_modified_agent(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            home = base / 'home'
            home.mkdir()
            env = os.environ.copy()
            env.update({'BBK_HOME': str(home), 'HOME': str(home), 'BBK_INSTALL_ROOT': str(base / 'data'), 'BBK_BIN_DIR': str(base / 'bin')})
            m1_run([sys.executable, m1_INSTALL, 'install', '--scope', 'user', '--omp', '--no-language-profiles'], env=env)
            extension = home / '.omp' / 'agent' / 'extensions' / 'bbk'
            agent = home / '.omp' / 'agent' / 'agents' / 'bbk_worker.md'
            agent.write_text(agent.read_text(encoding='utf-8') + '\nlocal change\n', encoding='utf-8')
            value, result = m1_run_json([sys.executable, extension / 'omp_model_routing.py', '--json', 'apply-profile', 'testing-flash'], env=env, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(value['status'], 'ERROR')
            self.assertIn('differs from the BBK install manifest', value['error'])

    def test_current_docs_describe_menu_profiles_and_headless_commands(self):
        text = '\n'.join(((m1_ROOT / name).read_text(encoding='utf-8') for name in ['README.md', 'docs/MODEL-ROUTING.md', 'docs/USAGE.md', 'omp/extension/README.md']))
        for required in ['/bbk:models', 'testing-flash', 'deepseek-economy', 'installation-default', 'omp-model-routing-profile.json', 'future', 'sub-agent', 'task.agentModelOverrides']:
            self.assertIn(required, text)

    def test_version_and_extension_metadata_agree(self):
        version = (m1_ROOT / 'VERSION').read_text(encoding='utf-8').strip()
        self.assertEqual(version, '0.1.0-alpha.11.11')
        self.assertEqual(json.loads((m1_ROOT / 'omp' / 'extension' / 'package.json').read_text(encoding='utf-8'))['version'], version)
        self.assertEqual(json.loads(m1_PROFILES.read_text(encoding='utf-8'))['package_version'], version)

# ---------------------------------------------------------------------------
# Historical source: test_alpha11_4_omp_context_update.py
# ---------------------------------------------------------------------------
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from zipfile import ZipFile
m2_ROOT = Path(__file__).resolve().parents[1]
m2_INSTALL = m2_ROOT / 'tools' / 'install.py'
m2_SETUP = m2_ROOT / 'tools' / 'setup.py'
m2_UPDATE_OMP = m2_ROOT / 'tools' / 'update_omp.py'
m2_EXTENSION = m2_ROOT / 'omp' / 'extension' / 'index.js'
m2_BUNDLED = m2_ROOT / 'bundled-language-profiles' / 'packages'
m2_VERSION = (m2_ROOT / 'VERSION').read_text(encoding='utf-8').strip()

def m2_run(command, *, env=None, cwd=m2_ROOT, check=True):
    return subprocess.run([str(value) for value in command], cwd=str(cwd), env=env, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', timeout=180)

def m2_run_json(command, *, env=None, cwd=m2_ROOT, check=True):
    result = m2_run(command, env=env, cwd=cwd, check=check)
    return (json.loads(result.stdout), result)

def m2_file_snapshot(root: Path) -> dict[str, tuple[str, int]]:
    return {path.relative_to(root).as_posix(): (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns) for path in sorted(root.rglob('*')) if path.is_file()}

class Alpha114OmpContextAndUpdateTests(unittest.TestCase):

    def test_core_extension_has_one_deliberate_prompt_path_and_no_command_payloads(self):
        text = m2_EXTENSION.read_text(encoding='utf-8')
        self.assertNotIn('.sendMessage(', text)
        self.assertEqual(text.count('.sendUserMessage('), 1)
        self.assertNotIn('return value.details', text)
        self.assertIn('ctx?.ui?.notify', text)
        self.assertIn('content: [{ type: "text", text: JSON.stringify(value.details, null, 2) }]', text)
        self.assertIn('registerTool', text)
        self.assertIn('registerCommand', text)
        self.assertIn('appendEntry', text)
        self.assertIn('"before_agent_start"', text)
        self.assertIn('"bbk:exit"', text)

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for OMP extension behavior')
    def test_deterministic_commands_are_ui_only_and_only_bbk_directive_enters_prompt_flow(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            home = base / 'home'
            home.mkdir()
            env = os.environ.copy()
            env.update({'BBK_HOME': str(home), 'HOME': str(home), 'BBK_INSTALL_ROOT': str(base / 'data'), 'BBK_BIN_DIR': str(base / 'bin')})
            m2_run([sys.executable, m2_INSTALL, 'install', '--scope', 'user', '--omp', '--no-language-profiles'], env=env)
            extension = home / '.omp' / 'agent' / 'extensions' / 'bbk' / 'index.js'
            script = base / 'context-boundary.mjs'
            script.write_text(textwrap.dedent(f"\n                    const chain = () => ({{ optional() {{ return this; }} }});\n                    const z = {{ object: value => value, string: chain, boolean: chain,\n                      enum: values => chain(), array: value => chain() }};\n                    const commands = new Map(), handlers = new Map();\n                    const messages = [], userMessages = [], notifications = [], entries = [], statuses = [];\n                    const branch = [];\n                    const pi = {{\n                      zod: {{ z }}, setLabel() {{}}, registerTool() {{}},\n                      on(name, value) {{ if (!handlers.has(name)) handlers.set(name, []); handlers.get(name).push(value); }},\n                      registerCommand(name, value) {{ commands.set(name, value); }},\n                      sendMessage(value, options) {{ messages.push({{value, options}}); }},\n                      async sendUserMessage(value, options) {{ userMessages.push({{value, options}}); }},\n                      appendEntry(customType, data) {{ entries.push({{customType, data}}); branch.push({{type:'custom', customType, data}}); }},\n                    }};\n                    const mod = await import({json.dumps(extension.as_uri())});\n                    mod.default(pi);\n                    const ctx = {{\n                      cwd: {json.dumps(str(base))}, hasUI: true,\n                      isIdle() {{ return true; }},\n                      sessionManager: {{ getBranch() {{ return branch; }} }},\n                      models: {{ list() {{ return []; }}, resolve() {{ return true; }} }},\n                      ui: {{\n                        notify(message, level) {{ notifications.push({{message, level}}); }},\n                        setStatus(key, value) {{ statuses.push({{key, value: value ?? null}}); }},\n                        async select() {{ throw new Error('unexpected interactive menu'); }},\n                      }},\n                    }};\n                    const results = [];\n                    const commandNames = [...commands.keys()].sort();\n                    for (const name of commandNames) {{\n                      if (name === 'bbk') {{\n                        results.push(await commands.get(name).handler('status', ctx));\n                      }} else if (name === 'bbk:models') {{\n                        results.push(await commands.get(name).handler('status', ctx));\n                      }} else {{\n                        results.push(await commands.get(name).handler('', ctx));\n                      }}\n                    }}\n                    const beforeMode = {{ messages: messages.length, userMessages: userMessages.length, entries: entries.length }};\n                    results.push(await commands.get('bbk').handler('', ctx));\n                    const afterEnter = {{ messages: messages.length, userMessages: userMessages.length, entries: entries.length }};\n                    const beforeAgent = handlers.get('before_agent_start')?.[0];\n                    if (!beforeAgent) throw new Error('missing before_agent_start');\n                    const activeOverlay = await beforeAgent({{systemPrompt:['base']}}, ctx);\n                    results.push(await commands.get('bbk').handler('Plan the sample system', ctx));\n                    results.push(await commands.get('bbk:exit').handler('', ctx));\n                    const inactiveOverlay = await beforeAgent({{systemPrompt:['base']}}, ctx);\n                    console.log(JSON.stringify({{\n                      allUndefined: results.every(value => value === undefined),\n                      commandNames,\n                      messages: messages.length,\n                      userMessages: userMessages.length,\n                      beforeMode,\n                      afterEnter,\n                      entries,\n                      statuses,\n                      notifications: notifications.length,\n                      prompt: userMessages[0]?.value || '',\n                      activeOverlay: activeOverlay?.systemPrompt?.join(String.fromCharCode(10)) || '',\n                      inactiveOverlay: inactiveOverlay ?? null,\n                    }}));\n                    "), encoding='utf-8')
            value = json.loads(m2_run([shutil.which('node') or 'node', script], env=env).stdout)
            self.assertTrue(value['allUndefined'])
            self.assertEqual(len(value['commandNames']), 27)
            self.assertIn('bbk:exit', value['commandNames'])
            self.assertEqual(value['messages'], 0)
            self.assertEqual(value['beforeMode'], {'messages': 0, 'userMessages': 0, 'entries': 0})
            self.assertEqual(value['afterEnter'], {'messages': 0, 'userMessages': 0, 'entries': 1})
            self.assertEqual(value['userMessages'], 1)
            self.assertGreaterEqual(value['notifications'], 27)
            self.assertEqual(value['prompt'], 'Plan the sample system')
            self.assertNotIn('bbk_root_wayfinder', value['prompt'])
            self.assertIn('<bbk-session-mode>', value['activeOverlay'])
            self.assertIn('bbk_root_wayfinder', value['activeOverlay'])
            self.assertIsNone(value['inactiveOverlay'])
            self.assertEqual([entry['data']['enabled'] for entry in value['entries']], [True, False])
            self.assertEqual(value['statuses'][-1], {'key': 'bbk-mode', 'value': None})

    def test_every_bundled_profile_extension_is_ui_only_but_tools_remain_model_facing(self):
        archives = sorted(m2_BUNDLED.glob('*.zip'))
        self.assertEqual(len(archives), 5)
        for archive in archives:
            with self.subTest(archive=archive.name), ZipFile(archive) as zf:
                roots = {name.split('/', 1)[0] for name in zf.namelist() if '/' in name}
                self.assertEqual(len(roots), 1)
                package_root = next(iter(roots))
                extension_name = f'{package_root}/omp/extension/index.js'
                text = zf.read(extension_name).decode('utf-8')
                self.assertNotIn('sendMessage(', text)
                self.assertNotIn('sendUserMessage(', text)
                self.assertNotIn('return value.details', text)
                self.assertIn('ctx.ui.notify', text)
                self.assertIn('registerTool', text)
                self.assertIn('content:', text)
                self.assertIn('details:', text)
                manifest = json.loads(zf.read(f'{package_root}/PACKAGE-MANIFEST.json'))
                record = next((item for item in manifest['files'] if item['path'] == 'omp/extension/index.js'))
                data = zf.read(extension_name)
                self.assertEqual(record['bytes'], len(data))
                self.assertEqual(record['sha256'], hashlib.sha256(data).hexdigest())
                self.assertIn(f'{package_root}/tests/test_dispatch_runtime.py', zf.namelist())

    def test_setup_exposes_omp_only_update_and_rejects_harness_selection(self):
        help_text = m2_run([sys.executable, m2_SETUP, '--help']).stdout
        self.assertIn('--update-omp', help_text)
        self.assertIn('--test-and-update-omp', help_text)
        self.assertIn('preserve Codex', help_text)
        invalid = m2_run([sys.executable, m2_SETUP, '--update-omp', '--scope', 'user', '--codex'], check=False)
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn('do not apply to an OMP-only update', invalid.stdout + invalid.stderr)

    def test_omp_only_update_preserves_active_route_and_does_not_touch_codex_files(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            home = base / 'home'
            home.mkdir()
            env = os.environ.copy()
            env.update({'BBK_HOME': str(home), 'HOME': str(home), 'BBK_INSTALL_ROOT': str(base / 'data'), 'BBK_BIN_DIR': str(base / 'bin')})
            installed, _ = m2_run_json([sys.executable, m2_INSTALL, '--json', 'install', '--scope', 'user', '--omp', '--codex', '--no-language-profiles'], env=env)
            extension = home / '.omp' / 'agent' / 'extensions' / 'bbk'
            m2_run_json([sys.executable, extension / 'omp_model_routing.py', '--json', 'apply-profile', 'testing-flash'], env=env)
            codex_root = home / '.codex' / 'agents'
            before = m2_file_snapshot(codex_root)
            updated, _ = m2_run_json([sys.executable, m2_UPDATE_OMP, '--json', '--scope', 'user'], env=env)
            self.assertEqual(updated['status'], 'PASS')
            self.assertEqual(updated['to_version'], m2_VERSION)
            self.assertEqual(updated['preserved_profile'], 'testing-flash')
            self.assertEqual(updated['codex_files_touched'], 0)
            self.assertIn('codex', updated['untouched_harnesses'])
            self.assertEqual(updated['reload_command'], '/reload-plugins')
            self.assertEqual(before, m2_file_snapshot(codex_root))
            routed, _ = m2_run_json([sys.executable, extension / 'omp_model_routing.py', '--json', 'status'], env=env)
            self.assertEqual(routed['active_profile'], 'testing-flash')
            self.assertEqual({route['model'] for route in routed['roles'].values()}, {'deepseek/deepseek-v4-flash'})
            status, _ = m2_run_json([sys.executable, m2_INSTALL, '--json', 'status', '--scope', 'user'], env=env)
            self.assertEqual(status['summary'], {'current': len(status['files'])})
            manifest = json.loads(Path(installed['manifest_path']).read_text(encoding='utf-8'))
            self.assertEqual(manifest['harness_versions']['omp'], m2_VERSION)
            self.assertEqual(manifest['last_omp_update']['kind'], 'omp-only')
            removed, _ = m2_run_json([sys.executable, m2_INSTALL, '--json', 'uninstall', '--scope', 'user'], env=env)
            self.assertFalse(removed['preserved'])

    def test_current_documentation_states_the_context_and_update_boundaries(self):
        text = '\n'.join(((m2_ROOT / name).read_text(encoding='utf-8') for name in ('README.md', 'docs/INSTALL.md', 'docs/USAGE.md', 'docs/MODEL-ROUTING.md', 'omp/extension/README.md')))
        for expected in ('UI-only', 'sendUserMessage', 'model context', '--update-omp', '--test-and-update-omp', '/reload-plugins', 'does not modify `.codex`', 'testing-flash', 'before_agent_start', 'appendEntry', '/bbk:exit'):
            self.assertIn(expected, text)

# ---------------------------------------------------------------------------
# Historical source: test_alpha11_5_omp_mode.py
# ---------------------------------------------------------------------------
import json
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path
m3_ROOT = Path(__file__).resolve().parents[1]
m3_EXTENSION = m3_ROOT / 'omp' / 'extension' / 'index.js'
m3_VERSION = (m3_ROOT / 'VERSION').read_text(encoding='utf-8').strip()

def m3_run_node(source: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as temp:
        script = Path(temp) / 'test.mjs'
        script.write_text(source, encoding='utf-8')
        result = subprocess.run([shutil.which('node') or 'node', script], cwd=m3_ROOT, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', timeout=90)
        if result.returncode != 0:
            raise AssertionError(result.stderr or result.stdout)
        return json.loads(result.stdout)
m3_MOCK_PREFIX = '\nconst chain = () => ({ optional() { return this; } });\nconst z = { object: value => value, string: chain, boolean: chain,\n  enum: values => chain(), array: value => chain() };\nconst commands = new Map(), handlers = new Map();\nconst userMessages = [], customMessages = [], entries = [], notifications = [], statuses = [];\nlet branch = [];\nconst pi = {\n  zod: { z }, setLabel() {}, registerTool() {},\n  registerCommand(name, value) { commands.set(name, value); },\n  on(name, value) { if (!handlers.has(name)) handlers.set(name, []); handlers.get(name).push(value); },\n  appendEntry(customType, data) {\n    entries.push({customType, data});\n    branch.push({type: "custom", customType, data});\n  },\n  sendMessage(value, options) { customMessages.push({value, options}); },\n  async sendUserMessage(value, options) { userMessages.push({value, options: options || null}); },\n};\nconst notificationsFor = () => notifications.map(item => item.message);\nconst ctx = {\n  cwd: process.cwd(), hasUI: true,\n  isIdle() { return true; },\n  sessionManager: { getBranch() { return branch; } },\n  ui: {\n    notify(message, level) { notifications.push({message, level}); },\n    setStatus(key, value) { statuses.push({key, value: value ?? null}); },\n  },\n};\n'

@unittest.skipUnless(shutil.which('node'), 'Node.js is required for OMP extension behavior')
class Alpha115OmpModeTests(unittest.TestCase):

    def test_mode_source_uses_session_state_and_system_prompt_not_transcript_payloads(self):
        source = m3_EXTENSION.read_text(encoding='utf-8')
        self.assertIn('const BBK_MODE_ENTRY_TYPE = "bbk-mode-state"', source)
        self.assertIn('const BBK_MODE_SCHEMA = "bbk.omp-mode-state.v1"', source)
        self.assertIn('"before_agent_start"', source)
        self.assertIn('appendEntry', source)
        self.assertIn('getBranch', source)
        self.assertIn('"session_switch"', source)
        self.assertIn('"session_branch"', source)
        self.assertIn('"session_tree"', source)
        self.assertIn('"bbk:exit"', source)
        self.assertEqual(source.count('.sendUserMessage('), 1)
        self.assertNotIn('.sendMessage(', source)
        self.assertNotIn('bbkEntrypointPrompt', source)
        self.assertNotIn('Installed baseline BBK skill', source)
        self.assertNotIn('readPackageText("shared", "skills", "bbk"', source)

    def test_enter_every_turn_overlay_verbatim_first_directive_and_exit(self):
        value = m3_run_node(textwrap.dedent(f'\n                {m3_MOCK_PREFIX}\n                const mod = await import({json.dumps(m3_EXTENSION.as_uri())});\n                mod.default(pi);\n                const before = handlers.get("before_agent_start")?.[0];\n                if (!before) throw new Error("before_agent_start missing");\n\n                const inactive = await before({{systemPrompt:["base"]}}, ctx);\n                const enterResult = await commands.get("bbk").handler("", ctx);\n                const afterEnterMessages = userMessages.length;\n                const active = await before({{systemPrompt:["base"]}}, ctx);\n                const repeated = await before({{systemPrompt:active.systemPrompt}}, ctx);\n                const directive = "Implement the accepted baseline without restarting planning";\n                await commands.get("bbk").handler(directive, ctx);\n                const exitResult = await commands.get("bbk:exit").handler("", ctx);\n                const afterExit = await before({{systemPrompt:["base"]}}, ctx);\n\n                const activeText = active.systemPrompt.join("\\n");\n                const repeatedText = repeated.systemPrompt.join("\\n");\n                console.log(JSON.stringify({{\n                  version: {json.dumps(m3_VERSION)},\n                  commands: commands.size,\n                  inactive: inactive ?? null,\n                  enterUndefined: enterResult === undefined,\n                  exitUndefined: exitResult === undefined,\n                  afterEnterMessages,\n                  userMessages,\n                  customMessages,\n                  entries,\n                  activeText,\n                  markerCount: (repeatedText.match(/<bbk-session-mode>/g) || []).length,\n                  afterExit: afterExit ?? null,\n                  statuses,\n                  notifications: notificationsFor(),\n                }}));\n                '))
        self.assertEqual(value['commands'], 27)
        self.assertIsNone(value['inactive'])
        self.assertTrue(value['enterUndefined'])
        self.assertTrue(value['exitUndefined'])
        self.assertEqual(value['afterEnterMessages'], 0)
        self.assertEqual(value['customMessages'], [])
        self.assertEqual(len(value['userMessages']), 1)
        self.assertEqual(value['userMessages'][0]['value'], 'Implement the accepted baseline without restarting planning')
        self.assertNotIn('bbk_root_wayfinder', value['userMessages'][0]['value'])
        self.assertEqual([entry['data']['enabled'] for entry in value['entries']], [True, False])
        self.assertEqual(value['entries'][0]['data']['schema'], 'bbk.omp-mode-state.v1')
        self.assertEqual(value['entries'][0]['data']['package_version'], m3_VERSION)
        for expected in ('<bbk-session-mode>', 'BBK mode is active', 'bbk_root_wayfinder', 'bbk_root_orchestrator', 'bbk_reviewer', 'bbk_validator_orchestrator', '/bbk:exit'):
            self.assertIn(expected, value['activeText'])
        self.assertEqual(value['markerCount'], 1)
        self.assertIsNone(value['afterExit'])
        self.assertIn({'key': 'bbk-mode', 'value': 'BBK'}, value['statuses'])
        self.assertEqual(value['statuses'][-1], {'key': 'bbk-mode', 'value': None})

    def test_mode_restores_per_branch_and_session_navigation(self):
        value = m3_run_node(textwrap.dedent(f'\n                {m3_MOCK_PREFIX}\n                const mod = await import({json.dumps(m3_EXTENSION.as_uri())});\n                mod.default(pi);\n                const before = handlers.get("before_agent_start")?.[0];\n                const sessionStart = handlers.get("session_start")?.[0];\n                const sessionSwitch = handlers.get("session_switch")?.[0];\n                const sessionBranch = handlers.get("session_branch")?.[0];\n                const sessionTree = handlers.get("session_tree")?.[0];\n                if (![before, sessionStart, sessionSwitch, sessionBranch, sessionTree].every(Boolean)) throw new Error("lifecycle handler missing");\n\n                branch = [{{type:"custom", customType:"bbk-mode-state", data:{{enabled:true}}}}];\n                await sessionStart({{type:"session_start"}}, ctx);\n                const startActive = await before({{systemPrompt:["base"]}}, ctx);\n\n                branch = [];\n                await sessionSwitch({{type:"session_switch"}}, ctx);\n                const switchedOff = await before({{systemPrompt:["base"]}}, ctx);\n\n                branch = [\n                  {{type:"custom", customType:"bbk-mode-state", data:{{enabled:true}}}},\n                  {{type:"custom", customType:"bbk-mode-state", data:{{enabled:false}}}},\n                ];\n                await sessionBranch({{type:"session_branch"}}, ctx);\n                const branchOff = await before({{systemPrompt:["base"]}}, ctx);\n\n                branch.push({{type:"custom", customType:"bbk-mode-state", data:{{enabled:true}}}});\n                await sessionTree({{type:"session_tree"}}, ctx);\n                const treeActive = await before({{systemPrompt:["base"]}}, ctx);\n                console.log(JSON.stringify({{\n                  startActive: Boolean(startActive), switchedOff: switchedOff ?? null,\n                  branchOff: branchOff ?? null, treeActive: Boolean(treeActive),\n                  statuses, notifications: notificationsFor(),\n                }}));\n                '))
        self.assertTrue(value['startActive'])
        self.assertIsNone(value['switchedOff'])
        self.assertIsNone(value['branchOff'])
        self.assertTrue(value['treeActive'])
        self.assertIn('BBK mode restored', '\n'.join(value['notifications']))

    def test_no_argument_entry_is_idempotent_and_exit_has_non_colon_alias(self):
        value = m3_run_node(textwrap.dedent(f'\n                {m3_MOCK_PREFIX}\n                const mod = await import({json.dumps(m3_EXTENSION.as_uri())});\n                mod.default(pi);\n                await commands.get("bbk").handler("", ctx);\n                await commands.get("bbk").handler("", ctx);\n                await commands.get("bbk").handler("exit", ctx);\n                await commands.get("bbk").handler("off", ctx);\n                console.log(JSON.stringify({{entries, userMessages, customMessages, notifications:notificationsFor()}}));\n                '))
        self.assertEqual([entry['data']['enabled'] for entry in value['entries']], [True, False])
        self.assertEqual(value['userMessages'], [])
        self.assertEqual(value['customMessages'], [])
        self.assertIn('BBK mode is already active', value['notifications'])
        self.assertIn('BBK mode is not active', value['notifications'])

    def test_current_docs_describe_persistent_mode_without_claiming_native_tool_restriction(self):
        text = '\n'.join(((m3_ROOT / name).read_text(encoding='utf-8') for name in ('README.md', 'docs/USAGE.md', 'docs/INSTALL.md', 'omp/extension/README.md', 'RELEASE-NOTES.md')))
        for expected in ('/bbk:exit', 'persistent BBK mode', 'before_agent_start', 'appendEntry', 'system-prompt overlay', 'session-local', 'footer', 'ordinary messages', 'does not change the parent model', '--update-omp'):
            self.assertIn(expected, text)
        self.assertIn("does not replace OMP's native plan or vibe modes", text)
