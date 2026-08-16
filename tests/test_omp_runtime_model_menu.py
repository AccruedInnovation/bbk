"""Split OMP runtime regression tests: Alpha113OmpModelMenuTests."""
from __future__ import annotations

from tests._omp_runtime_support import *
from tests._test_profiles import load_profiled_tests as load_tests

class Alpha113OmpModelMenuTests(unittest.TestCase):

    def test_bundled_profiles_cover_every_role_and_include_requested_cost_modes(self):
        value = json.loads(m1_PROFILES.read_text(encoding='utf-8'))
        roles = {item['name'] for item in json.loads((m1_ROOT / 'spec' / 'roles.json').read_text(encoding='utf-8'))['roles']}
        self.assertEqual(value['schema_version'], 'bbk.omp-model-routing-profiles.v1')
        self.assertEqual(value['package_version'], m1_VERSION)
        self.assertEqual(set(value['profiles']), {'default', 'testing-flash', 'deepseek-economy'})
        for profile in value['profiles'].values():
            self.assertEqual(set(profile['roles']), roles)
        testing = value['profiles']['testing-flash']['roles']
        self.assertEqual({route['model'] for route in testing.values()}, {'deepseek/deepseek-v4-flash'})
        economy = value['profiles']['deepseek-economy']['roles']
        self.assertTrue(all((route['model'].startswith('deepseek/') for route in economy.values())))
        self.assertIn('deepseek/deepseek-v4-pro', {route['model'] for route in economy.values()})
        self.assertIn('deepseek/deepseek-v4-flash', {route['model'] for route in economy.values()})

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for OMP routing-scope behavior')
    def test_project_profiles_are_isolated_and_broken_project_installs_do_not_fall_back(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            home = base / 'home'
            project_a = base / 'project-a'
            project_b = base / 'project-b'
            broken = base / 'broken-project'
            broken_router = base / 'broken-router-project'
            for path in (home, project_a, project_b, broken / 'nested', broken_router):
                path.mkdir(parents=True)
            routing_cwd_a = project_a / 'src'
            project_a_input_spelling = project_a
            alias = base / 'project-a-alias'
            try:
                alias.symlink_to(project_a, target_is_directory=True)
                routing_cwd_a = alias / 'src'
                project_a_input_spelling = alias
            except OSError:
                pass
            env = os.environ.copy()
            env.update({
                'BBK_HOME': str(home),
                'HOME': str(home),
                'BBK_INSTALL_ROOT': str(base / 'data'),
                'BBK_BIN_DIR': str(base / 'bin'),
            })
            m1_write_minimal_routing_install(base=base, home=home, scope='user')
            m1_write_minimal_routing_install(base=base, home=home, scope='project', project=project_a)
            m1_write_minimal_routing_install(base=base, home=home, scope='project', project=project_b)
            m1_write_minimal_routing_install(base=base, home=home, scope='project', project=broken_router)

            user_extension = home / '.omp' / 'agent' / 'extensions' / 'bbk'
            script = base / 'project-routing.mjs'
            script.write_text(textwrap.dedent(f'''
                const chain = () => ({{ optional() {{ return this; }} }});
                const z = {{ object: value => value, string: chain, boolean: chain,
                  enum: values => chain(), array: value => chain(), any: chain }};
                const commands = new Map(), notifications = [], confirmations = [];
                const pi = {{ zod: {{ z }}, setLabel() {{}}, registerTool() {{}}, on() {{}},
                  events: {{ on() {{ return () => {{}}; }} }},
                  registerCommand(name, value) {{ commands.set(name, value); }} }};
                const {{ unlinkSync }} = await import('node:fs');
                const mod = await import({json.dumps((user_extension / 'index.js').as_uri())});
                mod.default(pi);
                const command = commands.get('bbk:models');
                function context(cwd) {{
                  return {{
                    cwd, hasUI: true,
                    models: {{ list() {{ return []; }}, resolve() {{ return true; }} }},
                    ui: {{
                      notify(message, level) {{ notifications.push({{cwd, message, level}}); }},
                      async confirm(title, body) {{ confirmations.push({{cwd, title, body}}); return false; }},
                    }},
                  }};
                }}
                const a = context({json.dumps(str(routing_cwd_a))});
                const b = context({json.dumps(str(project_b))});
                const u = context({json.dumps(str(base))});
                const broken = context({json.dumps(str(broken / 'nested'))});
                const brokenRouter = context({json.dumps(str(broken_router))});
                await command.handler('profile testing-flash', a);
                await command.handler('status', a);
                await command.handler('profile deepseek-economy', b);
                await command.handler('status', b);
                await command.handler('user profile testing-flash', u);
                await command.handler('status', broken);
                unlinkSync({json.dumps(str(broken_router / '.omp' / 'extensions' / 'bbk' / 'omp_model_routing.py'))});
                await command.handler('status', brokenRouter);
                console.log(JSON.stringify({{notifications, confirmations}}));
            '''), encoding='utf-8')
            (project_a / 'src').mkdir()
            broken_manifest = {
                'schema': 'bbk.install-manifest.v1',
                'version': 'broken-test',
                'scope': 'project',
                'omp': True,
                'files': [],
            }
            (broken / '.bbk-kit-install.json').write_text(json.dumps(broken_manifest, indent=2) + '\n', encoding='utf-8')
            ui = json.loads(m1_run(['node', script], env=env).stdout)

            state_a = json.loads((project_a / '.bbk-kit' / 'effective-omp-model-routing.json').read_text(encoding='utf-8'))
            state_b = json.loads((project_b / '.bbk-kit' / 'effective-omp-model-routing.json').read_text(encoding='utf-8'))
            state_user = json.loads((base / 'data' / 'effective-omp-model-routing.json').read_text(encoding='utf-8'))
            self.assertEqual(state_a['active_profile'], 'testing-flash')
            self.assertEqual(state_b['active_profile'], 'deepseek-economy')
            self.assertEqual(state_user['active_profile'], 'installation-default')
            self.assertEqual(len(ui['confirmations']), 1)
            self.assertIn('shared user-scoped BBK installation', ui['confirmations'][0]['body'])

            messages = [item['message'] for item in ui['notifications']]
            assert_labeled_path(self, messages, 'Project', project_a_input_spelling, required_text='Scope: project')
            assert_labeled_path(
                self,
                messages,
                'Binding',
                project_a_input_spelling / '.omp' / 'extensions' / 'bbk' / 'bbk-package-root.json',
            )
            assert_labeled_path(
                self,
                messages,
                'State',
                project_b / '.bbk-kit' / 'effective-omp-model-routing.json',
            )
            self.assertTrue(any('routing did not fall back to user scope' in message for message in messages))
            self.assertTrue(any('missing its bound router' in message and 'did not fall back' in message for message in messages))
            broken_router_state = json.loads((broken_router / '.bbk-kit' / 'effective-omp-model-routing.json').read_text(encoding='utf-8'))
            self.assertEqual(broken_router_state['active_profile'], 'installation-default')

            for project, expected_profile in ((project_a, 'testing-flash'), (project_b, 'deepseek-economy')):
                binding = json.loads((project / '.omp' / 'extensions' / 'bbk' / 'bbk-package-root.json').read_text(encoding='utf-8'))
                self.assertEqual(binding['schema'], 'bbk.omp-package-binding.v3')
                self.assertEqual(binding['scope'], 'project')
                assert_same_path(self, binding['project_root'], project)
                status, _ = m1_run_json([
                    sys.executable, project / '.omp' / 'extensions' / 'bbk' / 'omp_model_routing.py',
                    '--binding', project / '.omp' / 'extensions' / 'bbk' / 'bbk-package-root.json',
                    '--json', 'status',
                ], env=env)
                self.assertEqual(status['scope'], 'project')
                assert_same_path(self, status['project_root'], project)
                self.assertEqual(status['active_profile'], expected_profile)
                assert_same_path(self, status['omp_agents'], project / '.omp' / 'agents')
                self.assertFalse(status['global_effect'])

            user_binding = user_extension / 'bbk-package-root.json'
            user_status, _ = m1_run_json([
                sys.executable, user_extension / 'omp_model_routing.py',
                '--binding', user_binding, '--json', 'status',
            ], env=env)
            self.assertEqual(user_status['scope'], 'user')
            self.assertTrue(user_status['global_effect'])

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for OMP UTF-8 transport behavior')
    def test_installed_omp_tool_transport_round_trips_utf8_strictly(self):
        title = "Baffle Connector — Δ測試 — café — 🚧"
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project = base / 'project'
            project.mkdir()
            script = base / 'utf8-roundtrip.mjs'
            script.write_text(textwrap.dedent(f"""
                const chain = () => ({{ optional() {{ return this; }} }});
                const z = {{ object: value => value, string: chain, boolean: chain,
                  enum: values => chain(), array: value => chain(), any: chain }};
                const tools = new Map();
                const pi = {{ zod: {{ z }}, setLabel() {{}}, on() {{}},
                  events: {{ on() {{ return () => {{}}; }} }},
                  registerCommand() {{}}, registerTool(value) {{ tools.set(value.name, value); }} }};
                const mod = await import({json.dumps((m1_ROOT / 'omp' / 'extension' / 'index.js').as_uri())});
                mod.default(pi);
                const ctx = {{ cwd: {json.dumps(str(project))} }};
                const init = await tools.get('bbk_init').execute('init', {{
                  root: {json.dumps(str(project))}, title: {json.dumps(title)}, projectId: 'BBK-UTF8-OMP'
                }}, undefined, undefined, ctx);
                const status = await tools.get('bbk_status').execute('status', {{root: {json.dumps(str(project))}}}, undefined, undefined, ctx);
                console.log(JSON.stringify({{init, status}}));
            """), encoding='utf-8')
            env = {**os.environ, 'BBK_PYTHON': sys.executable, 'BBK_CLI': str(m1_ROOT / 'tools' / 'bbk.py')}
            value = json.loads(m1_run(['node', script], env=env).stdout)
            self.assertFalse(value['init']['isError'])
            self.assertFalse(value['status']['isError'])
            self.assertEqual(value['init']['details']['title'], title)
            self.assertEqual(value['status']['details']['project']['title'], title)
            self.assertNotIn('�', json.dumps(value, ensure_ascii=False))
            self.assertEqual(json.loads((project / '.bbk' / 'config.json').read_text(encoding='utf-8'))['title'], title)
            self.assertIn(title, (project / '.bbk' / 'project.md').read_text(encoding='utf-8'))

    @unittest.skipUnless(shutil.which('node'), 'node is required for invalid UTF-8 transport test')
    def test_omp_tool_transport_rejects_invalid_utf8_without_replacement(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            fake = base / 'invalid-utf8-cli.py'
            fake.write_text(
                "import sys\nsys.stdout.buffer.write(b'\\xff')\n",
                encoding='utf-8',
                newline='\n',
            )
            script = base / 'invalid-utf8.mjs'
            script.write_text(textwrap.dedent(f"""
                const chain = () => ({{ optional() {{ return this; }} }});
                const z = {{ object: value => value, string: chain, boolean: chain,
                  enum: values => chain(), array: value => chain(), any: chain }};
                const tools = new Map();
                const pi = {{ zod: {{ z }}, setLabel() {{}}, on() {{}},
                  events: {{ on() {{ return () => {{}}; }} }}, registerCommand() {{}},
                  registerTool(value) {{ tools.set(value.name, value); }} }};
                const mod = await import({json.dumps((m1_ROOT / 'omp' / 'extension' / 'index.js').as_uri())});
                mod.default(pi);
                const value = await tools.get('bbk_status').execute('status', {{}}, undefined, undefined, {{cwd: {json.dumps(str(base))}}});
                console.log(JSON.stringify(value));
            """), encoding='utf-8')
            value = json.loads(m1_run(['node', script], env={**os.environ, 'BBK_PYTHON': sys.executable, 'BBK_CLI': str(fake)}).stdout)
            self.assertTrue(value['isError'])
            self.assertEqual(value['details']['schema'], 'bbk.utf8-transport-error.v1')
            self.assertIn('not valid UTF-8', value['details']['error'])
            self.assertNotIn('�', json.dumps(value, ensure_ascii=False))

    def test_template_is_compact_and_valid_for_runtime_application(self):
        value = json.loads(m1_TEMPLATE.read_text(encoding='utf-8'))
        self.assertEqual(value['schema_version'], 'bbk.omp-model-routing-profile.v1')
        self.assertNotIn('package_version', value)
        self.assertEqual(set(value['default']), {'model', 'thinkingLevel'})
        canonical = {item['name'] for item in json.loads((m1_ROOT / 'spec' / 'roles.json').read_text(encoding='utf-8'))['roles']}
        self.assertLessEqual(set(value['roles']), canonical)

    def test_custom_profile_package_version_is_optional_provenance(self):
        roles = [item['name'] for item in json.loads((m1_ROOT / 'spec' / 'roles.json').read_text(encoding='utf-8'))['roles']]
        base = json.loads(m1_TEMPLATE.read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'profile.json'
            for label in (None, 'different-release-label'):
                value = dict(base)
                if label is not None:
                    value['package_version'] = label
                path.write_text(json.dumps(value), encoding='utf-8')
                profile_id, description, routes = __import__('omp_model_routing').load_custom_profile(
                    path, m1_VERSION, roles
                )
                self.assertEqual(profile_id, value['id'])
                self.assertEqual(description, value['description'])
                self.assertEqual(set(routes), set(roles))
            invalid = dict(base)
            invalid['package_version'] = ''
            path.write_text(json.dumps(invalid), encoding='utf-8')
            with self.assertRaisesRegex(__import__('omp_model_routing').RoutingError, 'non-empty string'):
                __import__('omp_model_routing').load_custom_profile(path, m1_VERSION, roles)

    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for OMP model-menu behavior')
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
            self.assertEqual(binding['schema'], 'bbk.omp-package-binding.v3')
            self.assertEqual(binding['scope'], 'user')
            self.assertIsNone(binding['project_root'])
            self.assertTrue((extension / 'omp_model_routing.py').is_file())
            self.assertTrue((extension / 'path_compat.py').is_file())
            self.assertTrue(Path(binding['state_path']).is_file())
            status, _ = m1_run_json([sys.executable, extension / 'omp_model_routing.py', '--json', 'status'], env=env)
            self.assertEqual(status['active_profile'], 'installation-default')
            self.assertEqual(len(status['roles']), 19)
            self.assertEqual(status['route_surface'], 'bbk-managed-agent-frontmatter')
            self.assertIn('task.agentModelOverrides', status['precedence_note'])
            script = base / 'model-menu.mjs'
            script.write_text(textwrap.dedent(f"\n                const chain = () => ({{ optional() {{ return this; }} }});\n                const z = {{ object: value => value, string: chain, boolean: chain,\n                  enum: values => chain(), array: value => chain(), any: chain }};\n                const commands = new Map(), messages = [], userMessages = [], notifications = [];\n                const pi = {{ zod: {{ z }}, setLabel() {{}}, registerTool() {{}}, on() {{}},\n                  registerCommand(name, value) {{ commands.set(name, value); }},\n                  sendMessage(value) {{ messages.push(value); }},\n                  sendUserMessage(value) {{ userMessages.push(value); }} }};\n                const mod = await import({json.dumps((extension / 'index.js').as_uri())});\n                mod.default(pi);\n                const command = commands.get('bbk:models');\n                if (!command) throw new Error('missing bbk:models');\n                const ui = {{\n                  async select(title, options) {{\n                    if (title.includes('sub-agent model routing')) return 'Apply a routing profile';\n                    if (title === 'Routing profile') return options.find(value => value.startsWith('testing-flash'));\n                    throw new Error(`unexpected select ${{title}}`);\n                  }},\n                  async confirm() {{ return true; }},\n                  notify(message, level) {{ notifications.push({{message, level}}); }},\n                }};\n                const result = await command.handler('', {{cwd: {json.dumps(str(base))}, hasUI: true, ui, models: {{list() {{ return []; }}}}}});\n                console.log(JSON.stringify({{\n                  resultIsUndefined: result === undefined,\n                  messages: messages.length,\n                  userMessages: userMessages.length,\n                  notifications: notifications.length,\n                }}));\n            "), encoding='utf-8')
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
            routing = m1_write_minimal_routing_install(base=base, home=home, scope='user')
            extension = routing['extension']
            agent = routing['agents'] / 'bbk_worker.md'
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
        self.assertEqual(version, m1_VERSION)
        self.assertEqual(json.loads((m1_ROOT / 'omp' / 'extension' / 'package.json').read_text(encoding='utf-8'))['version'], version)
        self.assertEqual(json.loads(m1_PROFILES.read_text(encoding='utf-8'))['package_version'], version)

