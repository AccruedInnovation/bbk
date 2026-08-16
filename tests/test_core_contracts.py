"""Consolidated BBK regression tests grouped by responsibility.

Historical release-specific modules were merged to keep the public repository
readable while retaining their behavioral coverage.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Historical source: test_alpha6_congruence.py
# ---------------------------------------------------------------------------
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from tests import _cli_support as cli_support
from tests._cli_support import run_cli as test_run_cli
from tests._path_support import assert_same_path

try:
    import jsonschema as m1_jsonschema
except ImportError:  # Optional independent Draft 2020-12 cross-check.
    m1_jsonschema = None
m1_ROOT = Path(__file__).resolve().parents[1]
m1_BBK = m1_ROOT / 'tools' / 'bbk.py'
m1_spec = importlib.util.spec_from_file_location('bbk_alpha6_cli', m1_BBK)
m1_bbk = importlib.util.module_from_spec(m1_spec)
assert m1_spec.loader is not None
m1_spec.loader.exec_module(m1_bbk)

class Alpha6CongruenceTests(unittest.TestCase):
    maxDiff = None

    def load(self, rel: str):
        return json.loads((m1_ROOT / rel).read_text(encoding='utf-8'))

    def cli(self, *args: str, check: bool=True):
        return test_run_cli([sys.executable, '-B', str(m1_BBK), *args], cwd=m1_ROOT, check=check, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})

    def test_alpha3_and_alpha5_command_surfaces_coexist(self):
        help_text = self.cli('--help').stdout
        for command in ('manifest', 'candidate', 'gate', 'workspace', 'profile', 'beads'):
            self.assertIn(command, help_text)
        for command in ('fit', 'structure', 'slice', 'work-unit', 'worktree', 'package', 'digest'):
            self.assertIn(command, help_text)

    def test_solution_outcome_fit_examples_and_nonaveraging_risk(self):
        expected = {'confirmed-fit.json': ('CONFIRMED_FIT', 'CLEAR'), 'reframed-dashboard.json': ('REFRAMED', 'CLEAR'), 'investigate-fit.json': ('INVESTIGATE', 'BLOCKED'), 'preference-driven.json': ('PREFERENCE_DRIVEN', 'CLEAR'), 'constraint-required.json': ('CONSTRAINT_REQUIRED', 'CLEAR'), 'no-change-preferred.json': ('NO_CHANGE_PREFERRED', 'CLEAR')}
        for name, (disposition, commitment) in expected.items():
            report = m1_bbk.validate_solution_outcome_fit(self.load(f'fixtures/fit/{name}'))
            self.assertTrue(report['valid'], report)
            self.assertEqual(report['planningDisposition']['fitDisposition'], disposition)
            self.assertEqual(report['planningDisposition']['solutionCommitment'], commitment)
        self.assertEqual(m1_bbk.derive_fit_risk_tier({'consequence': 4, 'irreversibility': 0, 'uncertainty': 0, 'interfaceExposure': 0}), 'critical')
        self.assertEqual(m1_bbk.derive_fit_risk_tier({'consequence': 2, 'irreversibility': 2, 'uncertainty': 0, 'interfaceExposure': 0}), 'consequential')

    def test_invalid_fit_and_blocked_chain(self):
        invalid = m1_bbk.validate_solution_outcome_fit(self.load('fixtures/fit/invalid-intervention-as-outcome.json'))
        self.assertFalse(invalid['valid'])
        result = self.cli('--json', 'fit', 'check-chain', '--fit', 'fixtures/fit/investigate-fit.json', '--structure', 'fixtures/structure/software-contract.json', check=False)
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertFalse(payload['valid'])
        self.assertTrue(any(('blocks material solution commitment' in value for value in payload['errors'])))

    def test_fit_structure_slice_work_unit_chain(self):
        result = self.cli('--json', 'fit', 'check-chain', '--fit', 'fixtures/fit/confirmed-fit.json', '--structure', 'fixtures/structure/software-contract.json', '--slice', 'fixtures/slices/software-slice-1.json', '--slice', 'fixtures/slices/software-slice-2.json', '--work-unit', 'fixtures/work-units/query-service.json')
        payload = json.loads(result.stdout)
        self.assertTrue(payload['valid'], payload)
        self.assertEqual(payload['fit']['identity'], 'SOF-DECISION-QUERY@r1')
        self.assertEqual(len(payload['chain']['slices']), 2)

    def test_structure_slice_and_stable_renderers(self):
        for name in ('software-contract.json', 'procedure-contract.json'):
            value = self.load(f'fixtures/structure/{name}')
            report = m1_bbk.validate_structure(value)
            self.assertTrue(report['valid'], report)
            self.assertEqual(m1_bbk.markdown_structure(value), m1_bbk.markdown_structure(value))
        self.assertFalse(m1_bbk.validate_structure(self.load('fixtures/structure/invalid-contract.json'))['valid'])
        slices = [self.load('fixtures/slices/software-slice-1.json'), self.load('fixtures/slices/software-slice-2.json')]
        self.assertTrue(m1_bbk.validate_slice_set(slices)['valid'])
        slices[1]['dependsOn'] = ['missing']
        self.assertFalse(m1_bbk.validate_slice_set(slices)['valid'])

    def test_legacy_and_current_work_units_validate(self):
        current = m1_bbk.validate_work_unit(self.load('fixtures/work-units/query-service.json'))
        self.assertTrue(current['valid'], current)
        legacy = {'schema': 'bbk.work-unit.v1', 'id': 'WU-LEGACY', 'purpose': 'Preserve alpha.3 syntax', 'task_profile': 'implementation', 'assurance_tier': 'routine', 'scope': ['src/**'], 'language_profiles': ['legacy-fixture'], 'profile_hints': [], 'change_classes': []}
        report = m1_bbk.validate_work_unit(legacy)
        self.assertTrue(report['valid'], report)
        self.assertEqual(report['normalized']['taskProfile'], 'implementation')
        self.assertEqual(report['normalized']['assuranceTier'], 'routine')
        self.assertTrue(report['warnings'])

    def test_legacy_and_current_profiles_resolve(self):
        legacy = m1_bbk.validate_profile(self.load('fixtures/profiles/legacy/PROFILE.json'))
        current = m1_bbk.validate_profile(self.load('fixtures/profiles/alpha4/PROFILE.json'))
        self.assertTrue(legacy['valid'], legacy)
        self.assertEqual(legacy['implementationStructureSupport'], 'legacy-unprojected')
        self.assertTrue(current['valid'], current)
        self.assertEqual(current['implementationStructureSupport'], 'supported')
        with tempfile.TemporaryDirectory() as tmp:
            wu = Path(tmp) / 'legacy.json'
            wu.write_text(json.dumps({'schema': 'bbk.work-unit.v1', 'id': 'WU-LEGACY', 'purpose': 'Compatibility', 'task_profile': 'implementation', 'assurance_tier': 'routine', 'scope': ['src/**']}), encoding='utf-8')
            value = json.loads(self.cli('--json', 'profile', 'resolve', '--profile-root', 'fixtures/profiles', '--id', 'legacy-fixture', '--work-unit', str(wu), '--allow-unverified').stdout)
            self.assertEqual(value['profile']['id'], 'legacy-fixture')
            self.assertEqual(value['implementation_structure']['support'], 'legacy-unprojected')
        value = json.loads(self.cli('--json', 'profile', 'resolve', '--profile-root', 'fixtures/profiles', '--id', 'alpha4-fixture', '--work-unit', 'fixtures/work-units/query-service.json', '--solution-outcome-fit', 'fixtures/fit/confirmed-fit.json', '--structure-contract', 'fixtures/structure/software-contract.json', '--execution-slice', 'fixtures/slices/software-slice-1.json', '--allow-unverified').stdout)
        self.assertEqual(value['profile']['id'], 'alpha4-fixture')
        self.assertEqual(value['inputs']['solutionOutcomeFits'][0]['solutionCommitment'], 'CLEAR')
        self.assertEqual(value['implementation_structure']['support'], 'supported')

    def test_blocked_fit_profile_policy(self):
        result = self.cli('--json', 'profile', 'resolve', '--profile-root', 'fixtures/profiles', '--id', 'alpha4-fixture', '--task-profile', 'implementation', '--assurance-tier', 'consequential', '--solution-outcome-fit', 'fixtures/fit/investigate-fit.json', '--allow-unverified', check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn('blocks task profile implementation', json.loads(result.stdout)['error'])
        allowed = self.cli('--json', 'profile', 'resolve', '--profile-root', 'fixtures/profiles', '--id', 'legacy-fixture', '--task-profile', 'investigation-prototype', '--assurance-tier', 'consequential', '--solution-outcome-fit', 'fixtures/fit/investigate-fit.json', '--allow-unverified')
        self.assertEqual(json.loads(allowed.stdout)['inputs']['taskProfile'], 'investigation-prototype')

    def test_roles_preserve_detail_and_add_feature_skills(self):
        roles = self.load('spec/roles.json')
        self.assertEqual(roles['package_version'], (m1_ROOT / 'VERSION').read_text(encoding='utf-8').strip())
        self.assertEqual(len(roles['roles']), 19)
        self.assertEqual(roles['schema_version'], 'bbk.roles.v4')
        self.assertEqual(set(roles['constitution_modules']), {'core', 'planning', 'coordination', 'execution', 'assurance'})
        self.assertTrue(all(role['constitution'][0] == 'core' for role in roles['roles']))
        self.assertTrue(all(len(role['scope']) >= 2 for role in roles['roles']))
        self.assertTrue(all(len(role['responsibilities']) >= 5 for role in roles['roles']))
        self.assertTrue(all(len(role['escalations']) >= 2 for role in roles['roles']))
        self.assertTrue(all(set(role['delegation']) == set(role['spawns']) for role in roles['roles']))
        self.assertTrue(all('bbk' not in role['skills'] and 'bbk' not in role['mandatory_skills'] for role in roles['roles']))
        self.assertTrue(all(set(role['mandatory_skills']) <= set(role['skills']) for role in roles['roles']))
        self.assertTrue(all(len(role['mandatory_skills']) >= 1 for role in roles['roles']))
        prompt_policy = json.loads((m1_ROOT / 'spec' / 'prompt-modules' / 'catalog.json').read_text(encoding='utf-8'))['compilation_policy']
        self.assertIsNone(prompt_policy['mandatory_procedure_maximum'])
        self.assertFalse(roles['interaction_topology']['canonical_roles_user_facing'])
        self.assertEqual(roles['interaction_topology']['omp_transport'], 'hub/IRC to the peer whose kind is main')
        self.assertGreaterEqual(sum(('bbk-solution-outcome-fit' in role['skills'] for role in roles['roles'])), 8)
        self.assertGreaterEqual(sum(('bbk-implementation-structure' in role['skills'] for role in roles['roles'])), 8)

    def test_alpha3_document_and_skill_baseline_is_retained(self):
        for rel in ('LICENSE', 'docs/README.md', 'docs/INSTALL.md', 'docs/USAGE.md', 'docs/DEVELOPMENT.md', 'shared/references/method.md', 'shared/references/assurance.md', 'shared/references/evidence.md', 'shared/references/recovery.md', 'shared/skills/bbk/SKILL.md', 'shared/skills/bbk-plan/SKILL.md', 'shared/skills/bbk-execute/SKILL.md', 'shared/skills/bbk-recover/SKILL.md'):
            self.assertTrue((m1_ROOT / rel).is_file(), rel)
        self.assertGreaterEqual(len(list((m1_ROOT / 'shared' / 'skills').glob('*/SKILL.md'))), 11)

    def test_init_is_additive_and_installs_current_templates(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = json.loads(self.cli('--json', 'init', '--root', tmp, '--project-id', 'TEST-A6').stdout)
            self.assertIn(first['status'], {'PASS', 'initialized'})
            root = Path(tmp) / '.bbk'
            self.assertTrue((root / 'examples' / 'fit' / 'EXAMPLE-solution-outcome-fit.json').is_file())
            self.assertTrue((root / 'examples' / 'structures' / 'EXAMPLE-implementation-structure-contract.json').is_file())
            self.assertTrue((root / 'examples' / 'slices' / 'EXAMPLE-execution-slice.json').is_file())
            marker = root / 'project.md'
            marker.write_text('preserve me\n', encoding='utf-8')
            second = json.loads(self.cli('--json', 'init', '--root', tmp).stdout)
            self.assertEqual(marker.read_text(encoding='utf-8'), 'preserve me\n')
            self.assertIn('.bbk/project.md', second.get('preserved', []))

    @unittest.skipUnless(m1_jsonschema is not None, "optional jsonschema capability is unavailable")
    def test_status_results_validate_against_published_schema(self):
        schema = self.load('spec/schemas/bbk-status-v1.schema.json')
        validator = m1_jsonschema.Draft202012Validator(schema)
        validator.check_schema(schema)
        no_project = json.loads(self.cli('--json', 'status').stdout)
        validator.validate(no_project)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            uninitialized = json.loads(self.cli('--json', 'status', '--root', str(root)).stdout)
            validator.validate(uninitialized)
            self.cli('--json', 'init', '--root', str(root), '--project-id', 'BBK-STATUS-SCHEMA')
            initialized = json.loads(self.cli('--json', 'status', '--root', str(root)).stdout)
            validator.validate(initialized)

    def test_unicode_initialization_examples_and_uninitialized_status_are_truthful(self):
        title = "Baffle Connector — Δ測試 — café — 🚧"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            empty = json.loads(self.cli('--json', 'status', '--root', str(root)).stdout)
            self.assertEqual(empty['status'], 'UNINITIALIZED')
            self.assertEqual(empty['command_status'], 'PASS')
            self.assertFalse(empty['project']['initialized'])
            self.assertEqual(empty['planning_artifacts'], {'fit': 0, 'structures': 0, 'slices': 0, 'work_units': 0})
            self.assertEqual(empty['next_action']['command'], 'bbk init')

            initialized = json.loads(self.cli('--json', 'init', '--root', str(root), '--project-id', 'BBK-UNICODE', '--title', title).stdout)
            self.assertEqual(initialized['title'], title)
            direct_root = root / 'direct-cli'
            direct = test_run_cli(
                [sys.executable, '-X', 'utf8', str(m1_BBK), '--json', 'init', '--root', str(direct_root), '--project-id', 'BBK-UNICODE-DIRECT', '--title', title],
                cwd=m1_ROOT,
                env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'},
                force_subprocess=True,
            )
            self.assertEqual(json.loads(direct.stdout)['title'], title)
            self.assertNotIn('�', direct.stdout)
            self.assertEqual(
                json.loads((direct_root / '.bbk' / 'config.json').read_text(encoding='utf-8'))['title'],
                title,
            )
            config = json.loads((root / '.bbk' / 'config.json').read_text(encoding='utf-8'))
            self.assertEqual(config['title'], title)
            project_bytes = (root / '.bbk' / 'project.md').read_bytes()
            self.assertEqual(project_bytes.decode('utf-8').splitlines()[0], f'# {title}')
            self.assertNotIn('�', project_bytes.decode('utf-8'))

            status = json.loads(self.cli('--json', 'status', '--root', str(root)).stdout)
            self.assertEqual(status['project']['title'], title)
            self.assertTrue(status['project']['initialized'])
            self.assertEqual(status['planning_artifacts'], {'fit': 0, 'structures': 0, 'slices': 0, 'work_units': 0})
            expected_examples = sum(
                1
                for path in (root / '.bbk').rglob('*')
                if path.is_file() and path.name.casefold().startswith('example-')
            )
            self.assertGreater(expected_examples, 0)
            self.assertEqual(status['examples_available']['total'], expected_examples)

            questions = json.loads(self.cli('--json', 'question', 'list', '--root', str(root)).stdout)
            handoffs = json.loads(self.cli('--json', 'handoff', 'list', '--root', str(root)).stdout)
            self.assertEqual(questions['count'], 0)
            self.assertEqual(handoffs['count'], 0)

            copies = {
                'fit/real-fit.json': m1_ROOT / 'fixtures' / 'fit' / 'confirmed-fit.json',
                'structures/real-structure.json': m1_ROOT / 'fixtures' / 'structure' / 'software-contract.json',
                'slices/real-slice.json': m1_ROOT / 'fixtures' / 'slices' / 'software-slice-1.json',
                'work-units/real-work-unit.json': m1_ROOT / 'fixtures' / 'work-units' / 'query-service.json',
            }
            for rel, source in copies.items():
                shutil.copy2(source, root / '.bbk' / rel)
            status = json.loads(self.cli('--json', 'status', '--root', str(root)).stdout)
            self.assertEqual(status['planning_artifacts'], {'fit': 1, 'structures': 1, 'slices': 1, 'work_units': 1})

            manifest = json.loads(self.cli('--json', 'manifest', 'create', '--root', str(root), '--source', str(root / '.bbk')).stdout)
            self.assertGreaterEqual(manifest['examples_excluded'], expected_examples)
            self.assertFalse(manifest['include_examples'])
            self.assertFalse(any(Path(item['path']).name.startswith('EXAMPLE-') for item in manifest['files']))

            explicit_examples = json.loads(self.cli(
                '--json', 'manifest', 'create', '--root', str(root),
                '--source', str(root / '.bbk'), '--include-examples',
            ).stdout)
            self.assertTrue(explicit_examples['include_examples'])
            self.assertEqual(explicit_examples['examples_excluded'], 0)
            self.assertTrue(any(Path(item['path']).name.startswith('EXAMPLE-') for item in explicit_examples['files']))

            standalone_source = root / 'standalone-candidate-source'
            standalone_source.mkdir()
            (standalone_source / 'EXAMPLE-template.json').write_text('{"template": true}\n', encoding='utf-8')
            (standalone_source / 'real.json').write_text('{"real": true}\n', encoding='utf-8')
            default_candidate = root / 'candidate-default.json'
            self.cli('--json', 'candidate', 'freeze', '--root', str(standalone_source),
                     '--source', str(standalone_source), '--output', str(default_candidate))
            default_value = json.loads(default_candidate.read_text(encoding='utf-8'))
            self.assertEqual({item['path'] for item in default_value['files']}, {'real.json'})
            explicit_candidate = root / 'candidate-with-examples.json'
            self.cli('--json', 'candidate', 'freeze', '--root', str(standalone_source),
                     '--source', str(standalone_source), '--output', str(explicit_candidate),
                     '--include-examples')
            explicit_value = json.loads(explicit_candidate.read_text(encoding='utf-8'))
            self.assertEqual({item['path'] for item in explicit_value['files']}, {'EXAMPLE-template.json', 'real.json'})

            direct = test_run_cli(
                [sys.executable, str(m1_BBK), '--json', 'status', '--root', str(root)],
                env={**os.environ, 'PYTHONIOENCODING': 'cp1252'},
                force_subprocess=True,
            )
            self.assertEqual(json.loads(direct.stdout)['project']['title'], title)
            self.assertNotIn('�', direct.stdout)

            malformed = root / 'malformed'
            (malformed / '.bbk').mkdir(parents=True)
            (malformed / '.bbk' / 'config.json').write_text('{bad json', encoding='utf-8')
            failed = self.cli('--json', 'status', '--root', str(malformed), check=False)
            self.assertEqual(failed.returncode, 2)
            self.assertEqual(json.loads(failed.stdout)['status'], 'ERROR')

            missing = root / 'does-not-exist'
            failed = self.cli('--json', 'status', '--root', str(missing), check=False)
            self.assertEqual(failed.returncode, 2)
            self.assertIn('does not exist', json.loads(failed.stdout)['error'])

    def test_cancelled_partial_attempt_remains_provisional_until_successor_return(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.cli('--json', 'init', '--root', str(root), '--project-id', 'BBK-ATTEMPT-LINEAGE')
            partial = root / 'partial-architecture.md'
            partial.write_text('# Provisional\n\nIncomplete attempt output.\n', encoding='utf-8')
            cancelled = json.loads(self.cli(
                '--json', 'handoff', 'create', '--root', str(root),
                '--id', 'HO-WU-ARCH-1', '--work-unit', 'WU-ARCH', '--attempt', '1',
                '--role', 'bbk_architect', '--disposition', 'CANCELLED',
                '--summary', 'Parent explicitly cancelled attempt 1; partial output is provisional.',
                '--interrupt-reason', 'USER_CANCELLED',
                '--interrupt-evidence', 'controller cancellation request CANCEL-1',
                '--partial-work-location', str(partial), '--artifact', str(partial),
                '--continuation-state', 'READY', '--checkpoint', str(partial),
                '--no-resume-same-thread',
                '--next-action', 'Commission a successor attempt that explicitly adopts, repairs, replaces, or discards the partial output.',
            ).stdout)
            self.assertTrue(cancelled['valid'])
            first_path = root / cancelled['handoff']['path']
            first = json.loads((first_path / 'handoff.json').read_text(encoding='utf-8'))
            self.assertEqual(first['attempt'], 1)
            self.assertEqual(first['disposition'], 'CANCELLED')
            self.assertEqual(first['interrupt']['partial_work_location'], 'partial-architecture.md')

            final = root / 'architecture.md'
            final.write_text('# Architecture\n\nValidated successor output.\n', encoding='utf-8')
            successor = json.loads(self.cli(
                '--json', 'handoff', 'create', '--root', str(root),
                '--id', 'HO-WU-ARCH-2', '--work-unit', 'WU-ARCH', '--attempt', '2',
                '--role', 'bbk_architect', '--disposition', 'COMPLETE',
                '--summary', 'Successor attempt 2 replaced cancelled attempt 1 after independently validating the usable content.',
                '--work-performed', 'Disposition for attempt 1 partial output: REPLACED',
                '--artifact', str(final), '--completed-step', 'Replaced and superseded attempt 1 partial output',
                '--next-action', 'Parent validates and integrates successful attempt 2 only.',
            ).stdout)
            self.assertTrue(successor['valid'])
            second_path = root / successor['handoff']['path']
            second = json.loads((second_path / 'handoff.json').read_text(encoding='utf-8'))
            self.assertEqual(second['attempt'], 2)
            self.assertEqual(second['disposition'], 'COMPLETE')
            self.assertIn('replaced cancelled attempt 1', second['summary'].lower())
            self.assertEqual(second['work_performed'], ['Disposition for attempt 1 partial output: REPLACED'])

            listed = json.loads(self.cli('--json', 'handoff', 'list', '--root', str(root), '--work-unit', 'WU-ARCH').stdout)
            self.assertEqual(listed['count'], 2)
            by_attempt = {item['attempt']: item for item in listed['handoffs']}
            self.assertEqual(by_attempt[1]['disposition'], 'CANCELLED')
            self.assertEqual(by_attempt[2]['disposition'], 'COMPLETE')

    def test_standalone_candidate_and_recorded_gate_receipt_remain_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'a.txt').write_text('one\n', encoding='utf-8')
            candidate = root / 'candidate.json'
            self.cli('candidate', 'freeze', '--root', str(root), '--output', str(candidate))
            verified = json.loads(self.cli('--json', 'candidate', 'verify', str(candidate)).stdout)
            self.assertTrue(verified['valid'], verified)
            receipt = root / 'receipt.json'
            self.cli('gate', 'record', '--candidate', str(candidate), '--gate-id', 'fixture', '--status', 'PASS', '--output', str(receipt))
            checked = json.loads(self.cli('--json', 'gate', 'check', str(receipt), '--candidate', str(candidate)).stdout)
            self.assertTrue(checked['valid'], checked)
            (root / 'a.txt').write_text('two\n', encoding='utf-8')
            stale = json.loads(self.cli('--json', 'candidate', 'verify', str(candidate), check=False).stdout)
            self.assertFalse(stale['valid'])

    def test_installer_refuses_divergence_and_backs_up_force_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            home = base / 'home'
            home.mkdir()
            env = {**os.environ, 'BBK_HOME': str(home), 'HOME': str(home), 'BBK_INSTALL_ROOT': str(base / 'data'), 'BBK_BIN_DIR': str(base / 'bin')}
            install = m1_ROOT / 'tools' / 'install.py'
            test_run_cli([sys.executable, str(install), 'install', '--scope', 'user', '--codex', '--no-language-profiles'], check=True, env=env)
            target = home / '.codex' / 'agents' / 'bbk_worker.toml'
            target.write_text(target.read_text(encoding='utf-8') + '\n# local divergence\n', encoding='utf-8')
            rejected = test_run_cli([sys.executable, str(install), '--json', 'install', '--scope', 'user', '--codex', '--no-language-profiles'], check=False, env=env)
            self.assertEqual(rejected.returncode, 2)
            self.assertIn('Destination differs', json.loads(rejected.stdout)['error'])
            replaced = test_run_cli([sys.executable, str(install), '--json', 'install', '--scope', 'user', '--codex', '--no-language-profiles', '--force'], check=True, env=env)
            records = [item for item in json.loads(replaced.stdout)['files'] if Path(item['path']).exists() and Path(item['path']).samefile(target)]
            self.assertEqual(len(records), 1, records)
            record = records[0]
            self.assertEqual(record['action'], 'replace')
            self.assertTrue(Path(record['backup']).is_file())
            test_run_cli([sys.executable, str(install), 'uninstall', '--scope', 'user'], check=True, env=env)
            self.assertTrue(home.exists())

    def test_schemas_parse_and_support_both_profile_lock_forms(self):
        for path in (m1_ROOT / 'spec' / 'schemas').glob('*.json'):
            json.loads(path.read_text(encoding='utf-8'))
        lock_schema = self.load('spec/schemas/bbk-profile-lock-v1.schema.json')
        self.assertIn('anyOf', lock_schema)
        profile_schema = self.load('spec/schemas/bbk-language-profile-v1.schema.json')
        self.assertIn('capabilities', profile_schema['properties'])

# ---------------------------------------------------------------------------
# Historical source: test_alpha7_congruence.py
# ---------------------------------------------------------------------------
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path
m2_ROOT = Path(__file__).resolve().parents[1]
m2_BBK = m2_ROOT / 'tools' / 'bbk.py'

class Alpha7CongruenceTests(unittest.TestCase):

    def test_release_is_additive_over_alpha6(self):
        self.assertEqual((m2_ROOT / 'VERSION').read_text(encoding='utf-8').strip(), '0.1.0-alpha.17.0.2.1')
        help_text = test_run_cli([sys.executable, m2_BBK, '--help'], cwd=m2_ROOT).stdout
        for command in ('fit', 'structure', 'slice', 'profile', 'manifest', 'candidate', 'gate', 'workspace', 'worktree', 'package'):
            self.assertIn(command, help_text)
        for command in ('assurance', 'state-effect', 'trace', 'evidence', 'review'):
            self.assertIn(command, help_text)

    def test_new_schemas_skills_and_references_exist(self):
        schemas = {path.name for path in (m2_ROOT / 'spec' / 'schemas').glob('*.json')}
        for name in ('bbk-state-decision-effect-design-v1.schema.json', 'bbk-state-transition-trace-v1.schema.json', 'bbk-implementation-structure-contract-v2.schema.json', 'bbk-assurance-contract-v1.schema.json', 'bbk-review-manifest-v1.schema.json', 'bbk-review-context-manifest-v1.schema.json', 'bbk-review-run-v1.schema.json', 'bbk-evidence-receipt-v2.schema.json', 'bbk-review-finding-v1.schema.json', 'bbk-finding-disposition-v1.schema.json', 'bbk-learning-candidate-v1.schema.json'):
            self.assertIn(name, schemas)
        method = json.loads((m2_ROOT / 'spec' / 'method-content.json').read_text(encoding='utf-8'))
        skills = {path.parent.name for path in (m2_ROOT / 'shared' / 'skills').glob('*/SKILL.md')}
        self.assertEqual(skills, set(method['skills']))
        self.assertEqual(len(skills), 40)
        for name in ('bbk-artifact', 'bbk-state-decision-effect-design', 'bbk-review-plan', 'bbk-review-context', 'bbk-review-run', 'bbk-review-findings', 'bbk-review-intent', 'bbk-review-learn', 'bbk-context-routing', 'bbk-procedure-design'):
            self.assertIn(name, skills)
        self.assertEqual(len(list((m2_ROOT / 'shared' / 'references').glob('*.md'))), 23)
        self.assertTrue((m2_ROOT / 'shared' / 'references' / 'omp.md').is_file())

    def test_role_catalogue_is_extended_not_replaced(self):
        roles = json.loads((m2_ROOT / 'spec' / 'roles.json').read_text(encoding='utf-8'))
        self.assertEqual(len(roles['roles']), 19)
        reviewer = next((role for role in roles['roles'] if role['id'] == 'reviewer'))
        validator = next((role for role in roles['roles'] if role['id'] == 'validator'))
        self.assertGreaterEqual(len(reviewer['responsibilities']), 7)
        self.assertEqual(reviewer['primary_skill'], 'bbk-review')
        self.assertEqual(reviewer['mandatory_skills'], ['bbk-review'])
        self.assertIn('bbk-review-context', reviewer['skills'])
        self.assertIn('bbk-review-findings', reviewer['skills'])
        self.assertIn('bbk-review-findings', validator['skills'])
        self.assertIn('bbk-state-decision-effect-design', validator['skills'])

    def test_alpha16_authority_completion_vocabulary_is_canonical_and_projected(self):
        module_id = 'bbk-prompt-authority-completion-vocabulary'
        module = json.loads(
            (m2_ROOT / 'spec' / 'prompt-modules' / f'{module_id}.json').read_text(encoding='utf-8')
        )
        self.assertEqual(module['id'], module_id)
        clauses = {item['id']: item['text'] for item in module['clauses']}
        self.assertEqual(
            set(clauses),
            {
                'AUTHORITY.WORKSPACE_IMPLEMENTATION',
                'AUTHORITY.EXTERNAL_EXECUTION',
                'AUTHORITY.PRODUCE_ONLY',
                'AUTHORITY.EXACT_NEXT_EFFECT',
                'COMPLETION.EXACT_CLAIMS',
                'COMPLETION.NO_COLLAPSE',
                'COMPLETION.EVIDENCE_DERIVED',
                'COMPLETION.BYTE_INTEGRITY_CURRENT',
            },
        )
        self.assertIn('grants WORKSPACE_IMPLEMENTATION', clauses['AUTHORITY.PRODUCE_ONLY'])
        self.assertIn('withholding EXTERNAL_EXECUTION', clauses['AUTHORITY.PRODUCE_ONLY'])
        self.assertIn('may not reinterpret a deterministic failure as a pass', clauses['COMPLETION.EVIDENCE_DERIVED'])
        self.assertIn('bbk artifact freshness', clauses['COMPLETION.BYTE_INTEGRITY_CURRENT'])
        for claim in (
            'PLANNING_COMPLETE', 'IMPLEMENTATION_ARTIFACTS_COMPLETE',
            'BYTE_INTEGRITY_VERIFIED', 'SEMANTIC_REVIEW_COMPLETE',
            'DEPLOYMENT_AUTHORIZED', 'DEPLOYMENT_PERFORMED',
            'LIVE_ACCEPTANCE_VERIFIED',
        ):
            self.assertIn(claim, clauses['COMPLETION.EXACT_CLAIMS'])

        catalog = json.loads(
            (m2_ROOT / 'spec' / 'prompt-modules' / 'catalog.json').read_text(encoding='utf-8')
        )
        self.assertIn(module_id, {item['id'] for item in catalog['module_entries']})
        roles = json.loads((m2_ROOT / 'spec' / 'roles.json').read_text(encoding='utf-8'))['roles']
        self.assertEqual(len(roles), 19)
        self.assertTrue(all(module_id in role['prompt_modules'] for role in roles))

        expected = (
            'WORKSPACE_IMPLEMENTATION', 'EXTERNAL_EXECUTION', 'PRODUCE_ONLY',
            'IMPLEMENTATION_ARTIFACTS_COMPLETE', 'LIVE_ACCEPTANCE_VERIFIED',
        )
        for role in roles:
            role_name = role['name']
            paths = (
                m2_ROOT / 'projections' / 'codex' / 'agents' / f'{role_name}.toml',
                m2_ROOT / 'projections' / 'omp' / 'agents' / f'{role_name}.md',
                m2_ROOT / 'projections' / 'generic' / 'agents' / f'{role_name}.md',
                m2_ROOT / 'projections' / 'claude' / 'agents' / f"{role_name.replace('_', '-')}.md",
            )
            for path in paths:
                text = path.read_text(encoding='utf-8')
                if path.suffix == '.toml':
                    self.assertIn(
                        f'### `{module_id}`',
                        text,
                        str(path),
                    )
                    self.assertNotIn('<bbk-prompt-module', text, str(path))
                else:
                    self.assertIn(f'<bbk-prompt-module id="{module_id}">', text, str(path))
                for token in expected:
                    self.assertIn(token, text, str(path))

        omp_controller = (m2_ROOT / 'projections' / 'omp' / 'controllers' / 'bbk_controller.md').read_text(encoding='utf-8')
        omp_worker = (m2_ROOT / 'projections' / 'omp' / 'agents' / 'bbk_worker.md').read_text(encoding='utf-8')
        for token in expected:
            self.assertIn(token, omp_controller + omp_worker)

    def test_omp_surface_is_additive(self):
        source = (m2_ROOT / 'omp' / 'extension' / 'index.js').read_text(encoding='utf-8')
        tools = re.findall('name: "(bbk_[^"]+)"', source)
        commands = re.findall('registerCommand\\(pi, "(bbk(?::[^"]*)?)"', source)
        commands += re.findall('pi\\.registerCommand\\("(bbk(?::[^"]*)?)"', source)
        self.assertEqual(len(tools), 58)
        self.assertEqual(len(commands), 48)
        for name in (
            'bbk_manifest', 'bbk_candidate', 'bbk_gate', 'bbk_workspace',
            'bbk_review_plan', 'bbk_review_run', 'bbk_state_effect_validate',
            'bbk_artifact_preflight', 'bbk_artifact_seal', 'bbk_artifact_finalize', 'bbk_artifact_successor',
            'bbk_host_preflight', 'bbk_context_worker', 'bbk_context_review',
            'bbk_handoff_create', 'bbk_handoff_verify', 'bbk_handoff_list',
            'bbk_control_spawn', 'bbk_control_assign', 'bbk_control_update',
            'bbk_control_integrate_request', 'bbk_control_bind', 'bbk_control_dispatch_status',
            'bbk_governance_status', 'bbk_task_run',
        ):
            self.assertIn(name, tools)
        self.assertIn('bbk:artifact:finalize', commands)
        self.assertIn('bbk:timing', commands)
        self.assertIn('bbk:prompt-status', commands)

    def test_installer_copies_alpha7_cli_modules(self):
        source = (m2_ROOT / 'tools' / 'install.py').read_text(encoding='utf-8')
        for name in ('bbk.py', 'contracts.py', 'state_effect.py', 'review_assurance.py', 'artifact_classification.py', 'verify_package.py'):
            self.assertIn(name, source)

    def test_public_documentation_is_current_facing_and_compact(self):
        expected = {
            'README.md', 'INSTALL.md', 'USAGE.md', 'UPGRADING.md', 'DEVELOPMENT.md',
            'AGENTS.md', 'WAYFINDING-AND-GRILL.md', 'SOLUTION-OUTCOME-FIT.md',
            'EXECUTION-DESIGN.md', 'DURABLE-HANDOFFS.md', 'ASSURANCE.md',
            'LANGUAGE-PROFILES.md', 'MODEL-ROUTING.md', 'BOUNDARIES.md',
            'OMP-CHILD-LIFETIME.md', 'CRITICAL-PATH-EXECUTION-ALPHA17.md',
            'PROMPT-COMPILATION-ALPHA17.0.1.md',
            'BBK-MINIMUM-CEREMONY-OPERATING-MODE.md',
        }
        actual = {path.name for path in (m2_ROOT / 'docs').iterdir() if path.is_file()}
        self.assertEqual(actual, expected)
        self.assertFalse((m2_ROOT / 'docs' / 'source-prds').exists())
        self.assertFalse(any((m2_ROOT / 'docs').glob('MIGRATION-*.md')))
        self.assertFalse(any((m2_ROOT / 'docs').glob('DECISION-NOTE-*.md')))

# ---------------------------------------------------------------------------
# Historical source: test_alpha8_profile_dispatch.py
# ---------------------------------------------------------------------------
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
m3_ROOT = Path(__file__).resolve().parents[1]
m3_BBK = m3_ROOT / 'tools' / 'bbk.py'
m3_A8 = m3_ROOT / 'fixtures' / 'profiles' / 'alpha8'
m3_A7 = m3_ROOT / 'fixtures' / 'profiles' / 'alpha7'
m3_SDE = m3_ROOT / 'fixtures' / 'state-effect' / 'contract-order.json'
m3_ASSURANCE = m3_ROOT / 'fixtures' / 'review' / 'assurance-consequential.json'
m3_MANIFEST = m3_ROOT / 'fixtures' / 'review' / 'manifest-consequential.json'
m3_RECEIPT = m3_ROOT / 'fixtures' / 'review' / 'evidence-receipt-v2.json'

def m3_run_json(args: list[str]) -> dict:
    env = os.environ.copy()
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    completed = test_run_cli(
        [sys.executable, str(m3_BBK), '--json', *[str(x) for x in args]],
        cwd=m3_ROOT,
        env=env,
        check=True,
    )
    return json.loads(completed.stdout)

class Alpha8ProfileDispatchTests(unittest.TestCase):

    def test_fixture_profile_python_entrypoints_reuse_the_test_interpreter(self):
        script = m3_A8 / 'tools' / 'profile.py'
        eligible = cli_support._eligible_nested_python_script(
            [sys.executable, str(script), '--json', 'resolve']
        )
        self.assertIsNotNone(eligible)
        assert eligible is not None
        assert_same_path(self, eligible[0], script)
        self.assertEqual(eligible[1], ['--json', 'resolve'])
        self.assertIsNone(
            cli_support._eligible_nested_python_script(
                [sys.executable, str(m3_ROOT / 'tools' / 'bbk.py'), '--help']
            )
        )
        result = cli_support._run_nested_python_script(
            [sys.executable, str(script), '--json', 'resolve'],
            m3_ROOT,
            timeout=30,
            env=os.environ.copy(),
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result['returncode'], 0, result['stderr'])
        self.assertEqual(json.loads(result['stdout'])['profileId'], 'alpha8-fixture')

    def test_trusted_installed_routing_copy_reuses_canonical_main_with_adjacent_binding(self):
        with tempfile.TemporaryDirectory() as temp:
            extension = Path(temp)
            source = m3_ROOT / 'tools' / 'omp_model_routing.py'
            copied = extension / source.name
            shutil.copy2(source, copied)
            binding = extension / 'bbk-package-root.json'
            binding.write_text('{}\n', encoding='utf-8')
            parsed = cli_support._python_script(
                [sys.executable, str(copied), '--json', 'status']
            )
            self.assertIsNotNone(parsed)
            assert parsed is not None
            assert_same_path(self, parsed[0], source)
            self.assertEqual(parsed[1][0], '--binding')
            assert_same_path(self, parsed[1][1], binding)
            self.assertEqual(parsed[1][2:], ['--json', 'status'])
            copied.write_text(copied.read_text(encoding='utf-8') + '\n# modified\n', encoding='utf-8')
            self.assertIsNone(
                cli_support._python_script(
                    [sys.executable, str(copied), '--json', 'status']
                )
            )

    def test_alpha7_declaration_remains_valid_but_is_not_auto_dispatched(self):
        inspected = m3_run_json(['profile', 'inspect', '--id', 'alpha7-fixture', '--profile-dir', str(m3_A7)])
        self.assertEqual(inspected['package_verification']['status'], 'PASS')
        self.assertEqual(inspected['validation']['stateDecisionEffectDispatch'], 'legacy-declared')
        self.assertEqual(inspected['validation']['reviewAssuranceDispatch'], 'legacy-declared')
        dispatched = m3_run_json(['profile', 'dispatch', '--operation', 'state-effect', '--id', 'alpha7-fixture', '--profile-dir', str(m3_A7), '--source', str(m3_ROOT), '--state-decision-effect', str(m3_SDE)])
        self.assertEqual(dispatched['status'], 'UNSUPPORTED')
        self.assertIn('legacy alpha.7 declaration', dispatched['reason'])

    def test_alpha8_profile_declares_typed_capabilities(self):
        inspected = m3_run_json(['profile', 'inspect', '--id', 'alpha8-fixture', '--profile-dir', str(m3_A8)])
        self.assertEqual(inspected['package_verification']['status'], 'PASS')
        self.assertEqual(inspected['compatibility']['status'], 'PASS')
        self.assertEqual(inspected['validation']['stateDecisionEffectDispatch'], 'typed-v1')
        self.assertEqual(inspected['validation']['reviewAssuranceDispatch'], 'typed-v1')

    def test_standalone_dispatch_covers_all_operations(self):
        state = m3_run_json(['profile', 'dispatch', '--operation', 'state-effect', '--id', 'alpha8-fixture', '--profile-dir', str(m3_A8), '--source', str(m3_ROOT), '--state-decision-effect', str(m3_SDE)])
        self.assertEqual(state['status'], 'PASS')
        inventory = m3_run_json(['profile', 'dispatch', '--operation', 'state-effect-inventory', '--id', 'alpha8-fixture', '--profile-dir', str(m3_A8), '--source', str(m3_ROOT), '--state-decision-effect', str(m3_SDE)])
        self.assertEqual(inventory['status'], 'PASS')
        with tempfile.TemporaryDirectory() as temp:
            inventory_path = Path(temp) / 'inventory.json'
            inventory_path.write_text(json.dumps(inventory['result']['payload']), encoding='utf-8')
            review = m3_run_json(['profile', 'dispatch', '--operation', 'state-effect-review', '--id', 'alpha8-fixture', '--profile-dir', str(m3_A8), '--source', str(m3_ROOT), '--state-decision-effect', str(m3_SDE), '--state-effect-inventory', str(inventory_path)])
            self.assertEqual(review['status'], 'PASS')
            context = m3_run_json(['profile', 'dispatch', '--operation', 'review-context', '--id', 'alpha8-fixture', '--profile-dir', str(m3_A8), '--source', str(m3_ROOT), '--assurance-contract', str(m3_ASSURANCE), '--review-manifest', str(m3_MANIFEST)])
            self.assertEqual(context['status'], 'PASS')
            context_path = Path(temp) / 'context.json'
            context_path.write_text(json.dumps(context['result']['payload']), encoding='utf-8')
            lens = m3_run_json(['profile', 'dispatch', '--operation', 'review-lens', '--id', 'alpha8-fixture', '--profile-dir', str(m3_A8), '--source', str(m3_ROOT), '--assurance-contract', str(m3_ASSURANCE), '--review-manifest', str(m3_MANIFEST), '--review-context', str(context_path), '--lens-id', 'state-concurrency-effect-recovery', '--assignment-id', 'LA-A-STATE-ONE'])
            self.assertEqual(lens['status'], 'PASS')
        evidence = m3_run_json(['profile', 'dispatch', '--operation', 'evidence-adapter', '--id', 'alpha8-fixture', '--profile-dir', str(m3_A8), '--source', str(m3_ROOT), '--evidence-input', str(m3_RECEIPT)])
        self.assertEqual(evidence['status'], 'PASS')
        self.assertTrue(evidence['adaptedEvidenceValidation']['valid'])

    def test_resolve_auto_dispatches_smallest_supported_set_and_is_stable(self):
        # Resolve against an isolated source tree. The package root is shared by
        # concurrently executing test modules and may legitimately acquire
        # transient files while release/package tests run, which would make the
        # source-manifest digest nondeterministic without testing BBK behavior.
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'source'
            (source / 'src').mkdir(parents=True)
            (source / 'src' / 'lib.rs').write_text('pub fn stable() {}\n', encoding='utf-8')
            argv = ['profile', 'resolve', '--id', 'alpha8-fixture', '--profile-dir', str(m3_A8), '--source', str(source), '--role', 'reviewer', '--task-profile', 'interface-schema-migration', '--assurance-tier', 'consequential', '--state-decision-effect', str(m3_SDE), '--assurance-contract', str(m3_ASSURANCE), '--review-manifest', str(m3_MANIFEST), '--evidence-input', str(m3_RECEIPT)]
            first = m3_run_json(argv)
            second = m3_run_json(argv)
        self.assertEqual(first['schema'], 'bbk.profile-resolution-wrapper.v3')
        self.assertEqual(first['effective_sha256'], second['effective_sha256'])
        self.assertEqual(len(first['profile_dispatch']['operations']), 7)
        self.assertEqual([item['status'] for item in first['profile_dispatch']['operations']], ['PASS'] * 7)
        self.assertEqual(first['profile_dispatch']['unhandledReviewAssignments'], [{'manifestId': 'RM-ORDER-001', 'assignmentId': 'LA-A-INTENT', 'lens': 'intent-outcome'}])
        for item in first['profile_dispatch']['operations']:
            if item.get('request'):
                for binding in item['request']['inputs']:
                    self.assertFalse(Path(binding['path']).is_absolute())

    def test_manifest_git_status_is_scoped_to_the_requested_source_tree(self):
        # Build the repository fixture explicitly instead of relying on the BBK
        # source tree itself being a Git checkout. Release archives intentionally
        # exclude ``.git`` and must be able to run the complete suite after
        # extraction.
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            subprocess.run(['git', 'init', '--quiet'], cwd=base, check=True)
            subprocess.run(['git', 'config', 'user.name', 'BBK Tests'], cwd=base, check=True)
            subprocess.run(['git', 'config', 'user.email', 'bbk-tests@example.invalid'], cwd=base, check=True)
            seed = base / 'seed.txt'
            seed.write_text('seed\n', encoding='utf-8')
            subprocess.run(['git', 'add', 'seed.txt'], cwd=base, check=True)
            subprocess.run(['git', 'commit', '--quiet', '-m', 'seed'], cwd=base, check=True)
            source = base / 'source'
            source.mkdir()
            (source / 'bounded.txt').write_text('bounded\n', encoding='utf-8')
            unrelated = base / 'unrelated.txt'
            unrelated.write_text('outside source\n', encoding='utf-8')

            manifest = m1_bbk.collect_manifest(source)

        self.assertTrue(manifest['git']['available'])
        self.assertEqual(manifest['git']['status_porcelain'], ['?? bounded.txt'])
        self.assertNotIn('unrelated.txt', '\n'.join(manifest['git']['status_porcelain']))

    def test_profile_lock_binds_stable_dispatch(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / 'project'
            project.mkdir()
            source = Path(temp) / 'source'
            (source / 'src').mkdir(parents=True)
            (source / 'src' / 'lib.rs').write_text('pub fn stable() {}\n', encoding='utf-8')
            m3_run_json(['init', '--root', str(project), '--project-id', 'A8-PROFILE-LOCK'])
            value = m3_run_json(['profile', 'resolve', '--root', str(project), '--source', str(source), '--id', 'alpha8-fixture', '--profile-dir', str(m3_A8), '--state-decision-effect', str(m3_SDE), '--write-lock'])
            lock = json.loads((project / '.bbk' / 'profile-lock.json').read_text(encoding='utf-8'))
            profile = lock['profiles'][0]
            self.assertIn('capability_dispatch', profile)
            self.assertRegex(profile['capability_dispatch_sha256'], '^[0-9a-f]{64}$')
            self.assertNotIn('executions', profile['capability_dispatch'])
            self.assertEqual(lock['effective_sha256'], value['effective_sha256'])

    def test_alpha8_package_surface_is_present(self):
        self.assertEqual((m3_ROOT / 'VERSION').read_text(encoding='utf-8').strip(), '0.1.0-alpha.17.0.2.1')
        for rel in ['docs/LANGUAGE-PROFILES.md', 'spec/schemas/bbk-profile-capability-request-v1.schema.json', 'spec/schemas/bbk-profile-capability-result-v1.schema.json', 'spec/schemas/bbk-profile-dispatch-v1.schema.json', 'templates/profile-capability-request.json']:
            self.assertTrue((m3_ROOT / rel).is_file(), rel)

    def test_omp_exposes_typed_profile_dispatch(self):
        source = (m3_ROOT / 'omp' / 'extension' / 'index.js').read_text(encoding='utf-8')
        self.assertIn('bbk_profile_dispatch', source)
        self.assertIn('bbk:profile:dispatch', source)
        self.assertIn('--evidence-input', source)

# ---------------------------------------------------------------------------
# Public repository and product-neutral contract boundaries
# ---------------------------------------------------------------------------
import json
import re
import unittest
from pathlib import Path
m4_ROOT = Path(__file__).resolve().parents[1]


def m4_load(rel: str):
    return json.loads((m4_ROOT / rel).read_text(encoding='utf-8'))


class PublicRepositoryBoundaryTests(unittest.TestCase):

    def test_public_tree_excludes_pre_public_alignment_and_history_material(self):
        for rel in (
            'spec/blueprint-alignment.json',
            'examples/blueprint-dogfood',
            'tools/audit_alpha9_1_windows_test_leak.py',
            'tools/extract_git_repositories.py',
            'docs/source-prds',
            'docs/GIT-REPOSITORIES.md',
        ):
            self.assertFalse((m4_ROOT / rel).exists(), rel)
        self.assertFalse(any((m4_ROOT / 'docs').glob('MIGRATION-*.md')))
        self.assertFalse(any((m4_ROOT / 'docs').glob('DECISION-NOTE-*.md')))

    def test_questioning_wayfinder_is_a_first_class_logical_boundary(self):
        roles = m4_load('spec/roles.json')['roles']
        self.assertEqual(len(roles), 19)
        by_id = {role['id']: role for role in roles}
        questioning = by_id['questioning_wayfinder']
        self.assertIn('bbk_question_guide', questioning['spawns'])
        self.assertIn('bbk_researcher', questioning['spawns'])
        self.assertIn('bbk-context-routing', questioning['skills'])
        self.assertEqual(questioning['primary_skill'], 'bbk-question-branch')
        self.assertEqual(questioning['mandatory_skills'], ['bbk-question-branch'])
        self.assertTrue(questioning['human_decision_triggers'])
        for parent in ('root_wayfinder', 'territory_wayfinder'):
            self.assertIn('bbk_questioning_wayfinder', by_id[parent]['spawns'])
            self.assertNotIn('bbk_question_guide', by_id[parent]['spawns'])

    def test_context_and_procedure_methods_are_canonical_and_projected(self):
        method = m4_load('spec/method-content.json')
        self.assertEqual(method['version'], '0.1.0-alpha.17.0.2.1')
        self.assertIn('bbk-context-routing', method['skills'])
        self.assertIn('bbk-procedure-design', method['skills'])
        self.assertIn('context-routing.md', method['references'])
        self.assertIn('procedure-design.md', method['references'])
        manifest = m4_load('projections/manifest.json')
        self.assertEqual(manifest['role_count'], 19)
        self.assertEqual(manifest['projection_count'], 100)
        for target in manifest['targets']:
            names = [path.name for path in (m4_ROOT / 'projections' / target / 'agents').glob('*')]
            self.assertTrue(any(('questioning' in name and 'wayfinder' in name for name in names)), target)

    def test_current_facing_docs_do_not_publish_internal_partition_status(self):
        docs = [m4_ROOT / 'README.md', m4_ROOT / 'RELEASE-NOTES.md', *sorted((m4_ROOT / 'docs').glob('*.md'))]
        joined = '\n'.join(path.read_text(encoding='utf-8') for path in docs)
        for pattern in (r'\bQ0\b', r'\bC0\b', r'\bC11\b', r'ADR-BP-\d+'):
            self.assertIsNone(re.search(pattern, joined), pattern)

    def test_current_role_constitution_is_not_bound_to_product_status(self):
        roles = m4_load('spec/roles.json')
        constitution = ' '.join(
            clause
            for module in roles['constitution_modules'].values()
            for clause in module
        )
        lowered = constitution.casefold()
        self.assertNotIn('q0/c1 state', lowered)
        self.assertNotIn('c0–c11', lowered)
        self.assertNotIn('blueprint', lowered)
        self.assertNotIn('tenex', lowered)
        self.assertIn('Separate logical role, reusable procedure', constitution)
        self.assertIn('Keep evidence exposure append-only', constitution)
        self.assertIn('define capability, not authority', constitution)

# ---------------------------------------------------------------------------
# Historical source: test_alpha10_model_routing.py
# ---------------------------------------------------------------------------
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
m5_ROOT = Path(__file__).resolve().parents[1]
m5_TOOLS = m5_ROOT / 'tools'
if str(m5_TOOLS) not in sys.path:
    sys.path.insert(0, str(m5_TOOLS))
import model_routing
m5_ROLES = m5_ROOT / 'spec' / 'roles.json'
m5_ROUTING = m5_ROOT / 'spec' / 'model-routing.json'
m5_INSTALL = m5_ROOT / 'tools' / 'install.py'
m5_GENERATOR = m5_ROOT / 'tools' / 'generate_agents.py'

def m5_run(command: list[str | Path], *, cwd: Path=m5_ROOT, check: bool=True) -> subprocess.CompletedProcess[str]:
    return test_run_cli(command, cwd=cwd, check=check)

def m5_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def m5_frontmatter(path: Path) -> dict[str, object]:
    lines = path.read_text(encoding='utf-8').splitlines()
    if not lines or lines[0] != '---':
        raise AssertionError(f'missing YAML frontmatter: {path}')
    end = lines.index('---', 1)
    result: dict[str, object] = {}
    active_list: str | None = None
    for line in lines[1:end]:
        if line.startswith('  - '):
            if active_list is None:
                raise AssertionError(f'orphan YAML list item in {path}: {line}')
            raw = line[4:]
            try:
                value: object = json.loads(raw)
            except json.JSONDecodeError:
                value = raw
            cast = result.setdefault(active_list, [])
            if not isinstance(cast, list):
                raise AssertionError(f'mixed scalar/list key in {path}: {active_list}')
            cast.append(value)
            continue
        if not line.strip():
            continue
        key, raw = line.split(':', 1)
        key = key.strip()
        raw = raw.strip()
        active_list = key
        if not raw:
            result[key] = []
            continue
        try:
            result[key] = json.loads(raw)
        except json.JSONDecodeError:
            result[key] = raw
    return result

class Alpha10ModelRoutingTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.roles = json.loads(m5_ROLES.read_text(encoding='utf-8'))
        cls.routing = json.loads(m5_ROUTING.read_text(encoding='utf-8'))
        cls.role_names = {role['name'] for role in cls.roles['roles']}

    def test_policy_covers_every_role_with_independent_v2_routes(self):
        version = (m5_ROOT / 'VERSION').read_text(encoding='utf-8').strip()
        errors = model_routing.validate_model_routing(
            self.routing, version=version, role_names=self.role_names
        )
        self.assertEqual(errors, [])
        self.assertEqual(self.routing['schema_version'], 'bbk.model-routing.v2')
        self.assertEqual(set(self.routing['roles']), self.role_names)
        stats = model_routing.routing_statistics(self.routing)
        self.assertEqual(stats['mode'], 'per-role')
        self.assertEqual(stats['route_count'], 19)
        self.assertEqual(stats['profile_count'], 0)
        self.assertEqual(stats['role_profile_counts'], {})

    def test_alpha17_defaults_match_the_user_supplied_per_role_routing_selection(self):
        reviewed = json.loads(
            (m5_ROOT / 'tests' / 'fixtures' / 'alpha17-default-model-routing.json').read_text(
                encoding='utf-8'
            )
        )
        self.assertNotIn('package_version', reviewed)
        self.assertEqual(reviewed['schema_version'], 'bbk.model-routing.v2')
        self.assertEqual(set(reviewed['roles']), self.role_names)
        self.assertEqual(self.routing, reviewed)

        profiles = json.loads(
            (m5_ROOT / 'spec' / 'omp-model-routing-profiles.json').read_text(encoding='utf-8')
        )
        self.assertEqual(
            profiles['profiles']['default']['roles'],
            {name: route['omp'] for name, route in reviewed['roles'].items()},
        )

        relative = 'docs/MODEL-ROUTING.md'
        text = (m5_ROOT / relative).read_text(encoding='utf-8')
        for expected_fragment in (
            '`openai-codex/gpt-5.6-sol`, `thinkingLevel: high`',
            '`deepseek/deepseek-v4-pro`, `thinkingLevel: high`',
            '`deepseek/deepseek-v4-flash`, `thinkingLevel: max`',
            '`gpt-5.6-luna`, `model_reasoning_effort: medium`',
            '`gpt-5.6-luna`, `model_reasoning_effort: high`',
            '`gpt-5.6-luna`, `model_reasoning_effort: xhigh`',
            '`gpt-5.6-sol`, `model_reasoning_effort: medium`',
            '`haiku`, `effort: high`',
            '`sonnet`, `effort: medium`',
            '`opus`, `effort: high`',
        ):
            self.assertIn(expected_fragment, text, relative)
        self.assertIn('`package_version` is optional provenance', text, relative)
        readme = (m5_ROOT / 'README.md').read_text(encoding='utf-8')
        self.assertIn('docs/MODEL-ROUTING.md', readme)


    def test_generated_host_fields_match_each_direct_role_route(self):
        manifest = json.loads((m5_ROOT / 'projections' / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['schema'], 'bbk.projection-manifest.v10')
        self.assertEqual(manifest['model_routing_schema'], 'bbk.model-routing.v2')
        self.assertEqual(manifest['model_routing_mode'], 'per-role')
        self.assertEqual(manifest['model_route_count'], 19)
        self.assertNotIn('model_profile_count', manifest)
        self.assertNotIn('role_profile_counts', manifest)
        self.assertEqual(manifest['model_routing_source'], 'spec/model-routing.json')
        for role_name in sorted(self.role_names):
            route = self.routing['roles'][role_name]
            codex = tomllib.loads((m5_ROOT / 'projections' / 'codex' / 'agents' / f'{role_name}.toml').read_text(encoding='utf-8'))
            self.assertEqual(codex['model'], route['codex']['model'])
            self.assertEqual(codex['model_reasoning_effort'], route['codex']['model_reasoning_effort'])
            omp = m5_frontmatter(m5_ROOT / 'projections' / 'omp' / 'agents' / f'{role_name}.md')
            self.assertEqual(omp['model'], route['omp']['model'])
            self.assertEqual(omp['thinkingLevel'], route['omp']['thinkingLevel'])
            claude_name = role_name.replace('_', '-')
            claude = m5_frontmatter(m5_ROOT / 'projections' / 'claude' / 'agents' / f'{claude_name}.md')
            self.assertEqual(claude['model'], route['claude']['model'])
            self.assertEqual(claude['effort'], route['claude']['effort'])
            agent_meta = manifest['agents'][role_name]
            self.assertEqual(agent_meta['model_route'], role_name)
            self.assertEqual(agent_meta['model_routing_mode'], 'per-role')
            self.assertEqual(
                agent_meta['model_routing'],
                {'omp': route['omp'], 'codex': route['codex'], 'claude': route['claude']},
            )
            generic_text = (m5_ROOT / 'projections' / 'generic' / 'agents' / f'{role_name}.md').read_text(encoding='utf-8')
            self.assertIn('## Role', generic_text)
            self.assertIn(f"You are the canonical `{role_name}` BBK child role.", generic_text)
            self.assertNotIn('```json', generic_text)

    def test_v2_policy_validator_rejects_missing_and_unknown_roles(self):
        invalid = copy.deepcopy(self.routing)
        invalid['roles'].pop('bbk_worker')
        invalid['roles']['bbk_unknown_role'] = copy.deepcopy(invalid['roles']['bbk_validator'])
        errors = model_routing.validate_model_routing(
            invalid,
            version=(m5_ROOT / 'VERSION').read_text(encoding='utf-8').strip(),
            role_names=self.role_names,
        )
        self.assertTrue(any('missing roles' in error and 'bbk_worker' in error for error in errors))
        self.assertTrue(any('unknown roles' in error and 'bbk_unknown_role' in error for error in errors))

    def test_legacy_v1_accepts_new_profile_names_and_resolves_them(self):
        version = (m5_ROOT / 'VERSION').read_text(encoding='utf-8').strip()
        route = copy.deepcopy(self.routing['roles']['bbk_worker'])
        legacy = {
            'schema_version': 'bbk.model-routing.v1',
            'package_version': version,
            'description': 'Legacy compatibility policy with a user-defined profile.',
            'profiles': {
                'my-custom-worker-route': {
                    'description': 'A caller-defined profile name, not one of the original three.',
                    **route,
                },
            },
            'role_profiles': {name: 'my-custom-worker-route' for name in self.role_names},
        }
        self.assertEqual(
            model_routing.validate_model_routing(legacy, version=version, role_names=self.role_names),
            [],
        )
        resolved = model_routing.route_for_role(legacy, 'bbk_architect')
        self.assertEqual(resolved['profile'], 'my-custom-worker-route')
        self.assertEqual(resolved['mode'], 'profiles')
        migrated = model_routing.as_v2(legacy)
        self.assertEqual(migrated['schema_version'], 'bbk.model-routing.v2')
        self.assertEqual(set(migrated['roles']), self.role_names)
        self.assertEqual(migrated['roles']['bbk_architect']['omp'], route['omp'])

    def test_runtime_prompt_surface_is_product_neutral(self):
        paths = [m5_ROLES, m5_ROOT / 'spec' / 'method-content.json']
        paths.extend((m5_ROOT / 'shared' / 'skills').glob('*/SKILL.md'))
        paths.extend((m5_ROOT / 'shared' / 'references').glob('*.md'))
        for target in ('codex', 'omp', 'claude', 'generic'):
            paths.extend((m5_ROOT / 'projections' / target / 'agents').glob('*'))
        forbidden = (
            'tenex', 'otobotto', 'autospec',
            'deterministic blueprint-core object',
            'universal bbk / blueprint integrity obligations',
        )
        partition_tokens = {'q0', *(f'c{number}' for number in range(12))}
        for path in paths:
            text = path.read_text(encoding='utf-8').lower()
            for token in forbidden:
                self.assertNotIn(token, text, str(path.relative_to(m5_ROOT)))
            words = {word.strip('`\'".,:;()[]{}<>—–-') for word in text.split()}
            self.assertTrue(words.isdisjoint(partition_tokens), str(path.relative_to(m5_ROOT)))

    def test_install_time_override_changes_harness_agents_without_mutating_package(self):
        canonical_worker = m5_ROOT / 'projections' / 'omp' / 'agents' / 'bbk_worker.md'
        before = m5_sha256(canonical_worker)
        custom = copy.deepcopy(self.routing)
        custom['roles']['bbk_worker']['omp'] = {'model': '@tiny', 'thinkingLevel': 'low'}
        custom['roles']['bbk_worker']['codex'] = {'model': 'gpt-5.4-mini', 'model_reasoning_effort': 'low'}
        custom['roles']['bbk_worker']['claude'] = {'model': 'sonnet', 'effort': 'low'}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / 'project'
            project.mkdir()
            policy = root / 'custom-model-routing.json'
            policy.write_text(json.dumps(custom, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
            installed = m5_run([sys.executable, m5_INSTALL, '--json', 'install', '--scope', 'project', '--root', project, '--codex', '--omp', '--claude', '--generic', '--model-routing', policy, '--no-language-profiles'])
            value = json.loads(installed.stdout)
            assert_same_path(self, value['model_routing']['source'], policy)
            effective = project / '.bbk-kit' / 'effective-model-routing.json'
            self.assertEqual(json.loads(effective.read_text(encoding='utf-8')), custom)
            omp = m5_frontmatter(project / '.omp' / 'agents' / 'bbk_worker.md')
            self.assertEqual(omp['model'], '@tiny')
            self.assertEqual(omp['thinkingLevel'], 'low')
            codex = tomllib.loads((project / '.codex' / 'agents' / 'bbk_worker.toml').read_text(encoding='utf-8'))
            self.assertEqual(codex['model'], 'gpt-5.4-mini')
            claude = m5_frontmatter(project / '.claude' / 'agents' / 'bbk-worker.md')
            self.assertEqual(claude['model'], 'sonnet')
            generic_text = (project / '.agents' / 'bbk' / 'agents' / 'bbk_worker.md').read_text(encoding='utf-8')
            self.assertIn('## Role', generic_text)
            self.assertIn("You are the canonical `bbk_worker` BBK child role.", generic_text)
            self.assertNotIn('<bbk-model-routing', generic_text)
            self.assertNotIn('```json', generic_text)
            generic_manifest = json.loads((project / '.agents' / 'bbk' / 'agent-manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(generic_manifest['schema'], 'bbk.installed-host-neutral-agent-manifest.v4')
            self.assertEqual(generic_manifest['agents']['bbk_worker']['model_routing']['omp']['model'], '@tiny')
            empty_registry = (project / '.agents' / 'skills' / 'bbk-installed-profiles' / 'SKILL.md').read_text(encoding='utf-8')
            self.assertIn('No language or domain profile is managed', empty_registry)
            self.assertNotIn('package-source placeholder', empty_registry)
            self.assertEqual(value['language_profile_registry']['profile_count'], 0)
            self.assertEqual(value['model_routing']['sha256'], hashlib.sha256(json.dumps(custom, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest())
            binding_path = project / '.omp' / 'extensions' / 'bbk' / 'bbk-package-root.json'
            binding = json.loads(binding_path.read_text(encoding='utf-8'))
            self.assertEqual(binding['schema'], 'bbk.omp-package-binding.v3')
            self.assertEqual(binding['scope'], 'project')
            assert_same_path(self, binding['project_root'], project)
            assert_same_path(self, binding['omp_agents'], project / '.omp' / 'agents')
            assert_same_path(self, binding['state_path'], project / '.bbk-kit' / 'effective-omp-model-routing.json')
            m5_run([sys.executable, m5_INSTALL, 'uninstall', '--scope', 'project', '--root', project])
        self.assertEqual(m5_sha256(canonical_worker), before)

    def test_invalid_external_policy_blocks_install_before_any_write(self):
        invalid = copy.deepcopy(self.routing)
        invalid['roles'].pop('bbk_worker')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / 'project'
            project.mkdir()
            policy = root / 'invalid-model-routing.json'
            policy.write_text(json.dumps(invalid, indent=2) + '\n', encoding='utf-8')
            result = m5_run([sys.executable, m5_INSTALL, '--json', 'install', '--scope', 'project', '--root', project, '--omp', '--model-routing', policy], check=False)
            self.assertEqual(result.returncode, 2)
            payload = json.loads(result.stdout)
            self.assertEqual(payload['status'], 'ERROR')
            self.assertIn('missing roles', payload['error'])
            self.assertFalse((project / '.bbk-kit').exists())
            self.assertFalse((project / '.omp').exists())

    def test_model_routing_cli_and_projection_check_succeed(self):
        checked = m5_run([sys.executable, m5_ROOT / 'tools' / 'model_routing.py', '--check'])
        self.assertIn('19 roles have individual model routes', checked.stdout)
        generated = m5_run([sys.executable, m5_GENERATOR, '--check'])
        self.assertIn('19 roles, 19 direct model routes, 5 targets, and 100 projections', generated.stdout)



class Alpha14BoundedPlanningAndToolingTests(unittest.TestCase):
    """Regression coverage for alpha.14 prompt/tooling improvements.

    These checks deliberately validate schemas, command behavior, and prompt
    compilation. They do not create Blueprint-style lifecycle transition gates.
    """

    def cli(self, *args: str, check: bool = True):
        return test_run_cli(
            [sys.executable, '-B', str(m1_BBK), *args],
            cwd=m1_ROOT,
            check=check,
            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
        )

    def test_structure_v3_supports_compact_infrastructure_without_fake_state_machine(self):
        compact = json.loads(
            (m1_ROOT / 'templates' / 'implementation-structure-contract-v3-infrastructure-compact.json')
            .read_text(encoding='utf-8')
        )
        report = m1_bbk.validate_structure_v2(compact)
        self.assertTrue(report['valid'], report)
        self.assertEqual(report['version'], 'v3')
        self.assertEqual(report['contractDepth'], 'compact')
        self.assertEqual(report['stateDecisionEffect'], 'not-applicable')
        self.assertNotIn('stateDecisionEffectDesign', compact)
        self.assertTrue(compact['preExecutionConfirmations'])

        invalid = json.loads(json.dumps(compact))
        invalid['sectionApplicability']['stateDecisionEffect']['status'] = 'REQUIRED'
        invalid_report = m1_bbk.validate_structure_v2(invalid)
        self.assertFalse(invalid_report['valid'])
        self.assertTrue(any('stateDecisionEffectDesign is required' in item for item in invalid_report['errors']))

        standard = json.loads(
            (m1_ROOT / 'templates' / 'implementation-structure-contract-v3.json')
            .read_text(encoding='utf-8')
        )
        self.assertTrue(m1_bbk.validate_structure_v2(standard)['valid'])
        self.assertIn('stateDecisionEffectDesign', standard)

    def test_schema_catalog_template_enum_and_explanation_are_actionable(self):
        catalog = json.loads(self.cli('--json', 'schema', 'list').stdout)
        self.assertEqual(catalog['status'], 'PASS')
        self.assertIn('implementation-structure', {item['kind'] for item in catalog['items']})
        self.assertEqual(catalog['implementation_structure']['versions'], ['v1', 'v2', 'v3'])

        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'infra.json'
            created = json.loads(self.cli(
                '--json', 'schema', 'template', '--kind', 'implementation-structure',
                '--subject-kind', 'infrastructure', '--depth', 'compact', '--output', str(output),
            ).stdout)
            self.assertEqual(created['template'], 'implementation-structure-contract-v3-infrastructure-compact.json')
            self.assertTrue(output.is_file())
            self.assertTrue(json.loads(self.cli('--json', 'structure', 'validate', str(output)).stdout)['valid'])

            enum = json.loads(self.cli(
                '--json', 'schema', 'enum', '--schema', 'implementation-structure',
                '--pointer', '/contractDepth',
            ).stdout)
            self.assertEqual(enum['enum'], ['compact', 'standard', 'full'])
            self.assertEqual(enum['smallest_valid_example'], 'compact')

            value = json.loads(output.read_text(encoding='utf-8'))
            value['contractDepth'] = 'gigantic'
            output.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
            explained = self.cli(
                '--json', 'schema', 'explain', '--schema', 'implementation-structure',
                '--instance', str(output), '--pointer', '/contractDepth', check=False,
            )
            self.assertEqual(explained.returncode, 1)
            payload = json.loads(explained.stdout)
            self.assertEqual(payload['focus']['supplied_value'], 'gigantic')
            self.assertEqual(payload['focus']['allowed_values'], ['compact', 'standard', 'full'])
            self.assertEqual(payload['focus']['smallest_valid_example'], 'compact')

            without_site_packages = test_run_cli(
                [
                    sys.executable, '-S', str(m1_BBK), '--json', 'schema', 'explain',
                    '--schema', 'implementation-structure', '--instance', str(output),
                    '--pointer', '/contractDepth',
                ],
                cwd=m1_ROOT,
                check=False,
                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                force_subprocess=True,
            )
            self.assertEqual(without_site_packages.returncode, 1)
            no_site_payload = json.loads(without_site_packages.stdout)
            self.assertTrue(no_site_payload['external_validator']['available'])
            self.assertEqual(no_site_payload['focus']['allowed_values'], ['compact', 'standard', 'full'])
            self.assertIn('contractDepth must be compact, standard, or full', no_site_payload['builtin_validator']['errors'][0])

    def test_artifact_manifest_is_deterministic_excludes_examples_and_detects_tamper(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'sub').mkdir()
            (root / '.bbk' / 'examples').mkdir(parents=True)
            (root / 'a.txt').write_text('alpha\n', encoding='utf-8')
            (root / 'sub' / 'b.txt').write_text('beta\n', encoding='utf-8')
            (root / '.bbk' / 'examples' / 'EXAMPLE-ignore.json').write_text('{}\n', encoding='utf-8')
            manifest_path = root / 'artifact-manifest.json'
            first = json.loads(self.cli(
                '--json', 'artifact', 'manifest', '--root', str(root), '--path', '.',
                '--output', str(manifest_path), '--subject', 'bounded-review-package',
            ).stdout)
            self.assertEqual(first['file_count'], 2)
            self.assertEqual([item['path'] for item in first['files']], ['a.txt', 'sub/b.txt'])
            digest = first['content_sha256']
            second = json.loads(self.cli(
                '--json', 'artifact', 'manifest', '--root', str(root), '--path', '.',
                '--output', str(manifest_path), '--subject', 'bounded-review-package',
            ).stdout)
            self.assertEqual(second['content_sha256'], digest)
            verified = json.loads(self.cli(
                '--json', 'artifact', 'verify', 'artifact-manifest.json', '--root', str(root),
            ).stdout)
            self.assertTrue(verified['valid'])
            assert_same_path(self, verified['manifest'], manifest_path)
            (root / 'sub' / 'b.txt').write_text('changed\n', encoding='utf-8')
            failed = self.cli(
                '--json', 'artifact', 'verify', str(manifest_path), '--root', str(root), check=False,
            )
            self.assertEqual(failed.returncode, 1)
            self.assertTrue(any('digest changed' in item for item in json.loads(failed.stdout)['errors']))

    def test_init_isolates_examples_and_can_omit_them(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project = base / 'with-examples'
            project.mkdir()
            initialized = json.loads(self.cli(
                '--json', 'init', '--root', str(project), '--title', 'Alpha 14', '--project-id', 'A14',
            ).stdout)
            self.assertGreaterEqual(initialized['examples']['materialized'], 20)
            self.assertTrue((project / '.bbk' / 'examples' / 'structures' / 'EXAMPLE-implementation-structure-contract-v3-infrastructure-compact.json').is_file())
            self.assertFalse(any((project / '.bbk' / 'structures').glob('EXAMPLE-*')))
            status = json.loads(self.cli('--json', 'status', '--root', str(project)).stdout)
            self.assertEqual(status['planning_artifacts'], {'fit': 0, 'slices': 0, 'structures': 0, 'work_units': 0})
            self.assertGreater(status['examples_available']['total'], 0)
            config = json.loads((project / '.bbk' / 'config.json').read_text(encoding='utf-8'))
            self.assertEqual(config['examples']['materialization'], 'isolated')
            self.assertFalse(config['examples']['operational'])

            no_examples = base / 'without-examples'
            no_examples.mkdir()
            self.cli(
                '--json', 'init', '--root', str(no_examples), '--title', 'No examples',
                '--project-id', 'A14-NO-EXAMPLES', '--no-examples',
            )
            self.assertEqual(list((no_examples / '.bbk' / 'examples').rglob('*')), [])
            no_config = json.loads((no_examples / '.bbk' / 'config.json').read_text(encoding='utf-8'))
            self.assertEqual(no_config['examples']['materialization'], 'disabled')

    def test_question_attention_and_environment_observation_are_machine_explicit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.cli('--json', 'init', '--root', str(root), '--project-id', 'A14-Q', '--no-examples')
            ordinary = self.cli(
                '--json', 'question', 'new', '--root', str(root), '--id', 'Q-FACT',
                '--root-decision', 'Determine the exact host name', '--need-class', 'ENVIRONMENT_FACT',
                '--discoverability', 'DISCOVERABLE_NOW', '--safe-default', 'leave parameterized',
            )
            ordinary_value = json.loads(ordinary.stdout)
            question = json.loads((root / ordinary_value['path']).read_text(encoding='utf-8'))
            self.assertEqual(question['need_class'], 'ENVIRONMENT_FACT')
            self.assertFalse(question['attention']['requires_user_attention'])

            blocking_fact = json.loads(self.cli(
                '--json', 'question', 'new', '--root', str(root), '--id', 'Q-BLOCKING-FACT',
                '--root-decision', 'Discover the one fact required by all remaining work',
                '--need-class', 'ENVIRONMENT_FACT', '--discoverability', 'DISCOVERABLE_NOW',
                '--blocks-unaffected-work',
            ).stdout)
            blocking_question = json.loads((root / blocking_fact['path']).read_text(encoding='utf-8'))
            self.assertFalse(blocking_question['attention']['requires_user_attention'])
            self.assertFalse(blocking_question['attention']['unaffected_work_may_continue'])

            unavailable = json.loads(self.cli(
                '--json', 'question', 'new', '--root', str(root), '--id', 'Q-UNAVAILABLE-FACT',
                '--root-decision', 'Obtain the exact externally owned account identifier',
                '--need-class', 'CONFIGURATION_PARAMETER',
                '--discoverability', 'NOT_DISCOVERABLE_BY_BBK',
            ).stdout)
            unavailable_question = json.loads((root / unavailable['path']).read_text(encoding='utf-8'))
            self.assertTrue(unavailable_question['attention']['requires_user_attention'])
            self.assertIn('no safe default', unavailable_question['attention']['rationale'])

            reversible = json.loads(self.cli(
                '--json', 'question', 'new', '--root', str(root), '--id', 'Q-REVERSIBLE',
                '--root-decision', 'Choose a conventional local filename',
                '--need-class', 'REVERSIBLE_IMPLEMENTATION_CHOICE',
                '--discoverability', 'NOT_APPLICABLE',
            ).stdout)
            reversible_question = json.loads((root / reversible['path']).read_text(encoding='utf-8'))
            self.assertFalse(reversible_question['attention']['requires_user_attention'])

            architectural = json.loads(self.cli(
                '--json', 'question', 'new', '--root', str(root), '--id', 'Q-ARCHITECTURE',
                '--root-decision', 'Choose between two materially different deployment boundaries',
                '--need-class', 'ARCHITECTURAL_DECISION',
                '--discoverability', 'NOT_APPLICABLE',
            ).stdout)
            architectural_question = json.loads((root / architectural['path']).read_text(encoding='utf-8'))
            self.assertTrue(architectural_question['attention']['requires_user_attention'])

            evidence_path = Path(temp) / 'environment.json'
            created = json.loads(self.cli(
                '--json', 'evidence', 'new', '--kind', 'environment-observation',
                '--output', str(evidence_path), '--force',
            ).stdout)
            self.assertEqual(created['status'], 'PASS')
            evidence = json.loads(evidence_path.read_text(encoding='utf-8'))
            subject = evidence['environmentIdentity']
            for field in ('node_id', 'hostname', 'location_scope', 'observed_at', 'observation_source', 'method', 'scope', 'confidence', 'transferability'):
                self.assertIn(field, subject)
            self.assertTrue(json.loads(self.cli('--json', 'evidence', 'validate', str(evidence_path)).stdout)['valid'])


# Deterministic fast/standard/release selection used by tools/run_tests.py.
from tests._test_profiles import load_profiled_tests as load_tests
