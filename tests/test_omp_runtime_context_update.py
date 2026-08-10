"""Split OMP runtime regression tests: Alpha114OmpContextAndUpdateTests."""
from __future__ import annotations

from tests._omp_runtime_support import *
from tests._test_profiles import load_profiled_tests as load_tests

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
            installation = m1_write_minimal_routing_install(base=base, home=home, scope='user')
            binding = json.loads(installation['binding'].read_text(encoding='utf-8'))
            binding['path'] = str(m1_ROOT.resolve())
            binding['package_root'] = str(m1_ROOT.resolve())
            installation['binding'].write_text(json.dumps(binding, indent=2, sort_keys=True) + '\n', encoding='utf-8')
            extension = installation['extension'] / 'index.js'
            script = base / 'context-boundary.mjs'
            script.write_text(textwrap.dedent(f"\n                    const chain = () => ({{ optional() {{ return this; }} }});\n                    const z = {{ object: value => value, string: chain, boolean: chain,\n                      enum: values => chain(), array: value => chain(), any: chain }};\n                    const commands = new Map(), handlers = new Map();\n                    const messages = [], userMessages = [], notifications = [], entries = [], statuses = [];\n                    const branch = [];\n                    const pi = {{\n                      zod: {{ z }}, setLabel() {{}}, registerTool() {{}},\n                      on(name, value) {{ if (!handlers.has(name)) handlers.set(name, []); handlers.get(name).push(value); }},\n                      registerCommand(name, value) {{ commands.set(name, value); }},\n                      sendMessage(value, options) {{ messages.push({{value, options}}); }},\n                      async sendUserMessage(value, options) {{ userMessages.push({{value, options}}); }},\n                      appendEntry(customType, data) {{ entries.push({{customType, data}}); branch.push({{type:'custom', customType, data}}); }},\n                    }};\n                    const mod = await import({json.dumps(extension.as_uri())});\n                    mod.default(pi);\n                    const ctx = {{\n                      cwd: {json.dumps(str(base))}, hasUI: true,\n                      isIdle() {{ return true; }},\n                      sessionManager: {{ getBranch() {{ return branch; }} }},\n                      models: {{ list() {{ return []; }}, resolve() {{ return true; }} }},\n                      ui: {{\n                        notify(message, level) {{ notifications.push({{message, level}}); }},\n                        setStatus(key, value) {{ statuses.push({{key, value: value ?? null}}); }},\n                        async select() {{ throw new Error('unexpected interactive menu'); }},\n                      }},\n                    }};\n                    const results = [];\n                    const commandNames = [...commands.keys()].sort();\n                    for (const name of commandNames) {{\n                      if (name === 'bbk') {{\n                        results.push(await commands.get(name).handler('status', ctx));\n                      }} else if (name === 'bbk:models') {{\n                        results.push(await commands.get(name).handler('status', ctx));\n                      }} else {{\n                        results.push(await commands.get(name).handler('', ctx));\n                      }}\n                    }}\n                    const beforeMode = {{ messages: messages.length, userMessages: userMessages.length, entries: entries.length }};\n                    results.push(await commands.get('bbk').handler('', ctx));\n                    const afterEnter = {{ messages: messages.length, userMessages: userMessages.length, entries: entries.length }};\n                    const beforeAgent = handlers.get('before_agent_start')?.[0];\n                    if (!beforeAgent) throw new Error('missing before_agent_start');\n                    const activeOverlay = await beforeAgent({{systemPrompt:['<<OMP-INHERITED-CONTAMINATION>>']}}, ctx);\n                    results.push(await commands.get('bbk').handler('Plan the sample system', ctx));\n                    results.push(await commands.get('bbk:exit').handler('', ctx));\n                    const inactiveOverlay = await beforeAgent({{systemPrompt:['<<OMP-INHERITED-CONTAMINATION>>']}}, ctx);\n                    console.log(JSON.stringify({{\n                      allUndefined: results.every(value => value === undefined),\n                      commandNames,\n                      messages: messages.length,\n                      userMessages: userMessages.length,\n                      beforeMode,\n                      afterEnter,\n                      entries,\n                      statuses,\n                      notifications: notifications.length,\n                      prompt: userMessages[0]?.value || '',\n                      activeOverlay: activeOverlay?.systemPrompt?.join(String.fromCharCode(10)) || '',\n                      inactiveOverlay: inactiveOverlay ?? null,\n                    }}));\n                    "), encoding='utf-8')
            value = json.loads(m2_run([shutil.which('node') or 'node', script], env=env).stdout)
            self.assertTrue(value['allUndefined'])
            self.assertEqual(len(value['commandNames']), 48)
            self.assertIn('bbk:agents', value['commandNames'])
            self.assertIn('bbk:exit', value['commandNames'])
            for command in (
                'bbk:artifact:preflight', 'bbk:artifact:seal',
                'bbk:artifact:successor', 'bbk:preflight',
                'bbk:context:worker', 'bbk:context:review',
                'bbk:handoff:create', 'bbk:handoff:verify', 'bbk:handoff:list',
            ):
                self.assertIn(command, value['commandNames'])
            self.assertEqual(value['messages'], 0)
            self.assertEqual(value['beforeMode'], {'messages': 0, 'userMessages': 0, 'entries': 0})
            self.assertEqual(value['afterEnter'], {'messages': 0, 'userMessages': 0, 'entries': 1})
            self.assertEqual(value['userMessages'], 1)
            self.assertGreaterEqual(value['notifications'], 28)
            self.assertEqual(value['prompt'], 'Plan the sample system')
            self.assertNotIn('bbk_root_wayfinder', value['prompt'])
            self.assertIn('<bbk-controller-system', value['activeOverlay'])
            self.assertIn('BBK harness-root controller', value['activeOverlay'])
            self.assertIn('### Compiled primary procedure: `bbk`', value['activeOverlay'])
            self.assertIn('`hub`/IRC', value['activeOverlay'])
            self.assertIn('bbk_root_wayfinder', value['activeOverlay'])
            self.assertNotIn('OMP DEFAULT', value['activeOverlay'])
            self.assertNotIn('.codex/AGENTS.md', value['activeOverlay'])
            self.assertIsNone(value['inactiveOverlay'])
            self.assertEqual([entry['data']['enabled'] for entry in value['entries'] if entry['customType'] == 'bbk-mode-state'], [True, False])
            self.assertEqual(value['statuses'], [])

    def test_every_bundled_profile_extension_is_ui_only_but_tools_remain_model_facing(self):
        archives = sorted(m2_BUNDLED.glob('*.zip'))
        release = json.loads((m2_BUNDLED.parent / 'RELEASE-MANIFEST.json').read_text(encoding='utf-8'))
        declared = dict(sorted((release.get('profileVersions') or {}).items()))
        self.assertEqual(len(archives), len(declared))
        self.assertTrue(archives)
        found = {}
        for archive in archives:
            with self.subTest(archive=archive.name), ZipFile(archive) as zf:
                roots = {name.split('/', 1)[0] for name in zf.namelist() if '/' in name}
                self.assertEqual(len(roots), 1)
                package_root = next(iter(roots))
                profile = json.loads(zf.read(f'{package_root}/PROFILE.json'))
                found[profile['id']] = profile['version']
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
        self.assertEqual(dict(sorted(found.items())), declared)

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
            # Simulate an alpha.11.11 predecessor installation that did not yet
            # carry the shared path helper beside the routing command. The OMP-
            # only successor update must make its new import self-contained.
            helper = extension / 'path_compat.py'
            helper.unlink()
            manifest_path = Path(installed['manifest_path'])
            predecessor_manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            predecessor_manifest['files'] = [
                record for record in predecessor_manifest['files']
                if not paths_identify_same(record['path'], helper)
            ]
            manifest_path.write_text(
                json.dumps(predecessor_manifest, indent=2, ensure_ascii=False, sort_keys=True) + '\n',
                encoding='utf-8',
            )
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
            self.assertTrue(helper.is_file())
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

