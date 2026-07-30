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
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
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
        return subprocess.run([sys.executable, '-B', str(m1_BBK), *args], cwd=m1_ROOT, check=check, capture_output=True, text=True, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})

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
        self.assertEqual(roles['schema_version'], 'bbk.roles.v2')
        self.assertEqual(set(roles['constitution_modules']), {'core', 'planning', 'coordination', 'execution', 'assurance'})
        self.assertTrue(all(role['constitution'][0] == 'core' for role in roles['roles']))
        self.assertTrue(all(len(role['scope']) >= 2 for role in roles['roles']))
        self.assertTrue(all(len(role['responsibilities']) >= 5 for role in roles['roles']))
        self.assertTrue(all(len(role['escalations']) >= 2 for role in roles['roles']))
        self.assertTrue(all(set(role['delegation']) == set(role['spawns']) for role in roles['roles']))
        self.assertTrue(all('bbk' not in role['skills'] and 'bbk' not in role['autoload_skills'] for role in roles['roles']))
        self.assertTrue(all(set(role['autoload_skills']) <= set(role['skills']) for role in roles['roles']))
        self.assertTrue(all(1 <= len(role['autoload_skills']) <= 3 for role in roles['roles']))
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
            self.assertTrue((root / 'fit' / 'EXAMPLE-solution-outcome-fit.json').is_file())
            self.assertTrue((root / 'structures' / 'EXAMPLE-implementation-structure-contract.json').is_file())
            self.assertTrue((root / 'slices' / 'EXAMPLE-execution-slice.json').is_file())
            marker = root / 'project.md'
            marker.write_text('preserve me\n', encoding='utf-8')
            second = json.loads(self.cli('--json', 'init', '--root', tmp).stdout)
            self.assertEqual(marker.read_text(encoding='utf-8'), 'preserve me\n')
            self.assertIn('.bbk/project.md', second.get('preserved', []))

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
            subprocess.run([sys.executable, str(install), 'install', '--scope', 'user', '--codex'], check=True, capture_output=True, text=True, env=env)
            target = home / '.codex' / 'agents' / 'bbk_worker.toml'
            target.write_text(target.read_text(encoding='utf-8') + '\n# local divergence\n', encoding='utf-8')
            rejected = subprocess.run([sys.executable, str(install), '--json', 'install', '--scope', 'user', '--codex'], capture_output=True, text=True, env=env)
            self.assertEqual(rejected.returncode, 2)
            self.assertIn('Destination differs', json.loads(rejected.stdout)['error'])
            replaced = subprocess.run([sys.executable, str(install), '--json', 'install', '--scope', 'user', '--codex', '--force'], check=True, capture_output=True, text=True, env=env)
            records = [item for item in json.loads(replaced.stdout)['files'] if Path(item['path']).exists() and Path(item['path']).samefile(target)]
            self.assertEqual(len(records), 1, records)
            record = records[0]
            self.assertEqual(record['action'], 'replace')
            self.assertTrue(Path(record['backup']).is_file())
            subprocess.run([sys.executable, str(install), 'uninstall', '--scope', 'user'], check=True, capture_output=True, text=True, env=env)
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
        self.assertEqual((m2_ROOT / 'VERSION').read_text(encoding='utf-8').strip(), '0.1.0-alpha.11.11')
        help_text = subprocess.run([sys.executable, m2_BBK, '--help'], cwd=m2_ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout
        for command in ('fit', 'structure', 'slice', 'profile', 'manifest', 'candidate', 'gate', 'workspace', 'worktree', 'package'):
            self.assertIn(command, help_text)
        for command in ('assurance', 'state-effect', 'trace', 'evidence', 'review'):
            self.assertIn(command, help_text)

    def test_new_schemas_skills_and_references_exist(self):
        schemas = {path.name for path in (m2_ROOT / 'spec' / 'schemas').glob('*.json')}
        for name in ('bbk-state-decision-effect-design-v1.schema.json', 'bbk-state-transition-trace-v1.schema.json', 'bbk-implementation-structure-contract-v2.schema.json', 'bbk-assurance-contract-v1.schema.json', 'bbk-review-manifest-v1.schema.json', 'bbk-review-context-manifest-v1.schema.json', 'bbk-review-run-v1.schema.json', 'bbk-evidence-receipt-v2.schema.json', 'bbk-review-finding-v1.schema.json', 'bbk-finding-disposition-v1.schema.json', 'bbk-learning-candidate-v1.schema.json'):
            self.assertIn(name, schemas)
        skills = {path.parent.name for path in (m2_ROOT / 'shared' / 'skills').glob('*/SKILL.md')}
        self.assertEqual(len(skills), 24)
        for name in ('bbk-state-decision-effect-design', 'bbk-review-plan', 'bbk-review-context', 'bbk-review-run', 'bbk-review-findings', 'bbk-review-intent', 'bbk-review-learn', 'bbk-context-routing', 'bbk-procedure-design'):
            self.assertIn(name, skills)
        self.assertEqual(len(list((m2_ROOT / 'shared' / 'references').glob('*.md'))), 22)

    def test_role_catalogue_is_extended_not_replaced(self):
        roles = json.loads((m2_ROOT / 'spec' / 'roles.json').read_text(encoding='utf-8'))
        self.assertEqual(len(roles['roles']), 19)
        reviewer = next((role for role in roles['roles'] if role['id'] == 'reviewer'))
        validator = next((role for role in roles['roles'] if role['id'] == 'validator'))
        self.assertGreaterEqual(len(reviewer['responsibilities']), 7)
        self.assertIn('bbk-review-run', reviewer['skills'])
        self.assertIn('bbk-review-findings', validator['skills'])
        self.assertIn('bbk-state-decision-effect-design', validator['skills'])

    def test_omp_surface_is_additive(self):
        source = (m2_ROOT / 'omp' / 'extension' / 'index.js').read_text(encoding='utf-8')
        tools = re.findall('name: "(bbk_[^"]+)"', source)
        commands = re.findall('registerCommand\\(pi, "(bbk(?::[^"]*)?)"', source)
        commands += re.findall('pi\\.registerCommand\\("(bbk(?::[^"]*)?)"', source)
        self.assertEqual(len(tools), 26)
        self.assertEqual(len(commands), 27)
        for name in ('bbk_manifest', 'bbk_candidate', 'bbk_gate', 'bbk_workspace', 'bbk_review_plan', 'bbk_review_run', 'bbk_state_effect_validate'):
            self.assertIn(name, tools)

    def test_installer_copies_alpha7_cli_modules(self):
        source = (m2_ROOT / 'tools' / 'install.py').read_text(encoding='utf-8')
        for name in ('bbk.py', 'contracts.py', 'state_effect.py', 'review_assurance.py', 'verify_package.py'):
            self.assertIn(name, source)

    def test_public_documentation_is_current_facing_and_compact(self):
        expected = {
            'README.md', 'INSTALL.md', 'USAGE.md', 'UPGRADING.md', 'DEVELOPMENT.md',
            'AGENTS.md', 'WAYFINDING-AND-GRILL.md', 'SOLUTION-OUTCOME-FIT.md',
            'EXECUTION-DESIGN.md', 'DURABLE-HANDOFFS.md', 'ASSURANCE.md',
            'LANGUAGE-PROFILES.md', 'MODEL-ROUTING.md', 'BOUNDARIES.md',
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
    completed = subprocess.run(
        [sys.executable, str(m3_BBK), '--json', *[str(x) for x in args]],
        cwd=m3_ROOT,
        env=env,
        check=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return json.loads(completed.stdout)

class Alpha8ProfileDispatchTests(unittest.TestCase):

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
        argv = ['profile', 'resolve', '--id', 'alpha8-fixture', '--profile-dir', str(m3_A8), '--source', str(m3_ROOT), '--role', 'reviewer', '--task-profile', 'interface-schema-migration', '--assurance-tier', 'consequential', '--state-decision-effect', str(m3_SDE), '--assurance-contract', str(m3_ASSURANCE), '--review-manifest', str(m3_MANIFEST), '--evidence-input', str(m3_RECEIPT)]
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

    def test_profile_lock_binds_stable_dispatch(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / 'project'
            project.mkdir()
            m3_run_json(['init', '--root', str(project), '--project-id', 'A8-PROFILE-LOCK'])
            value = m3_run_json(['profile', 'resolve', '--root', str(project), '--source', str(m3_ROOT), '--id', 'alpha8-fixture', '--profile-dir', str(m3_A8), '--state-decision-effect', str(m3_SDE), '--write-lock'])
            lock = json.loads((project / '.bbk' / 'profile-lock.json').read_text(encoding='utf-8'))
            profile = lock['profiles'][0]
            self.assertIn('capability_dispatch', profile)
            self.assertRegex(profile['capability_dispatch_sha256'], '^[0-9a-f]{64}$')
            self.assertNotIn('executions', profile['capability_dispatch'])
            self.assertEqual(lock['effective_sha256'], value['effective_sha256'])

    def test_alpha8_package_surface_is_present(self):
        self.assertEqual((m3_ROOT / 'VERSION').read_text(encoding='utf-8').strip(), '0.1.0-alpha.11.11')
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
        self.assertIn('bbk-context-routing', questioning['skills'])
        self.assertIn('bbk-procedure-design', questioning['skills'])
        for parent in ('root_wayfinder', 'territory_wayfinder'):
            self.assertIn('bbk_questioning_wayfinder', by_id[parent]['spawns'])
            self.assertNotIn('bbk_question_guide', by_id[parent]['spawns'])

    def test_context_and_procedure_methods_are_canonical_and_projected(self):
        method = m4_load('spec/method-content.json')
        self.assertEqual(method['version'], '0.1.0-alpha.11.11')
        self.assertIn('bbk-context-routing', method['skills'])
        self.assertIn('bbk-procedure-design', method['skills'])
        self.assertIn('context-routing.md', method['references'])
        self.assertIn('procedure-design.md', method['references'])
        manifest = m4_load('projections/manifest.json')
        self.assertEqual(manifest['role_count'], 19)
        self.assertEqual(manifest['projection_count'], 76)
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
        self.assertIn('logical responsibility', constitution)
        self.assertIn('append-only evidence exposure', constitution)
        self.assertIn('does not create authority', constitution)

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
    return subprocess.run([str(value) for value in command], cwd=cwd, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')

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

    def test_policy_covers_every_role_through_three_named_tiers(self):
        errors = model_routing.validate_model_routing(self.routing, version=(m5_ROOT / 'VERSION').read_text(encoding='utf-8').strip(), role_names=self.role_names)
        self.assertEqual(errors, [])
        self.assertEqual(set(self.routing['profiles']), {'judgment', 'coordination', 'mechanical'})
        self.assertEqual(set(self.routing['role_profiles']), self.role_names)
        counts = {name: sum((value == name for value in self.routing['role_profiles'].values())) for name in self.routing['profiles']}
        self.assertEqual(counts, {'judgment': 12, 'coordination': 5, 'mechanical': 2})

    def test_default_tiers_use_deliberate_cost_quality_routing(self):
        profiles = self.routing['profiles']
        self.assertEqual(profiles['judgment']['omp'], {'model': 'openai-codex/gpt-5.6-sol', 'thinkingLevel': 'high'})
        self.assertEqual(profiles['coordination']['omp'], {'model': 'deepseek/deepseek-v4-pro', 'thinkingLevel': 'high'})
        self.assertEqual(profiles['mechanical']['omp'], {'model': 'deepseek/deepseek-v4-flash', 'thinkingLevel': 'high'})
        self.assertEqual(profiles['judgment']['codex'], {'model': 'gpt-5.6-sol', 'model_reasoning_effort': 'high'})
        self.assertEqual(profiles['coordination']['codex'], {'model': 'gpt-5.6-terra', 'model_reasoning_effort': 'medium'})
        self.assertEqual(profiles['mechanical']['codex'], {'model': 'gpt-5.6-luna', 'model_reasoning_effort': 'low'})
        self.assertEqual(profiles['judgment']['claude'], {'model': 'opus', 'effort': 'high'})
        self.assertEqual(profiles['coordination']['claude'], {'model': 'sonnet', 'effort': 'medium'})
        self.assertEqual(profiles['mechanical']['claude'], {'model': 'haiku', 'effort': 'low'})
        self.assertEqual(self.routing['role_profiles']['bbk_worker_orchestrator'], 'coordination')
        self.assertEqual(self.routing['role_profiles']['bbk_validator_orchestrator'], 'coordination')
        self.assertEqual(self.routing['role_profiles']['bbk_worker'], 'mechanical')
        self.assertEqual(self.routing['role_profiles']['bbk_validator'], 'mechanical')
        self.assertEqual(self.routing['role_profiles']['bbk_synthesizer'], 'judgment')
        for relative in ('README.md', 'docs/MODEL-ROUTING.md'):
            text = (m5_ROOT / relative).read_text(encoding='utf-8')
            for expected in ('`gpt-5.6-sol`, `model_reasoning_effort: high`', '`gpt-5.6-terra`, `model_reasoning_effort: medium`', '`gpt-5.6-luna`, `model_reasoning_effort: low`', '`opus`, `effort: high`', '`sonnet`, `effort: medium`', '`haiku`, `effort: low`'):
                self.assertIn(expected, text, relative)

    def test_generated_host_fields_match_each_role_route(self):
        manifest = json.loads((m5_ROOT / 'projections' / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['schema'], 'bbk.projection-manifest.v4')
        self.assertEqual(manifest['model_profile_count'], 3)
        self.assertEqual(manifest['model_routing_source'], 'spec/model-routing.json')
        for role_name in sorted(self.role_names):
            profile_name = self.routing['role_profiles'][role_name]
            profile = self.routing['profiles'][profile_name]
            codex = tomllib.loads((m5_ROOT / 'projections' / 'codex' / 'agents' / f'{role_name}.toml').read_text(encoding='utf-8'))
            self.assertEqual(codex['model'], profile['codex']['model'])
            self.assertEqual(codex['model_reasoning_effort'], profile['codex']['model_reasoning_effort'])
            omp = m5_frontmatter(m5_ROOT / 'projections' / 'omp' / 'agents' / f'{role_name}.md')
            self.assertEqual(omp['model'], profile['omp']['model'])
            self.assertEqual(omp['thinkingLevel'], profile['omp']['thinkingLevel'])
            claude_name = role_name.replace('_', '-')
            claude = m5_frontmatter(m5_ROOT / 'projections' / 'claude' / 'agents' / f'{claude_name}.md')
            self.assertEqual(claude['model'], profile['claude']['model'])
            self.assertEqual(claude['effort'], profile['claude']['effort'])
            agent_meta = manifest['agents'][role_name]
            self.assertEqual(agent_meta['model_profile'], profile_name)
            self.assertEqual(agent_meta['model_routing'], {'omp': profile['omp'], 'codex': profile['codex'], 'claude': profile['claude']})
            generic_text = (m5_ROOT / 'projections' / 'generic' / 'agents' / f'{role_name}.md').read_text(encoding='utf-8')
            self.assertIn('## Purpose', generic_text)
            self.assertNotIn('```json', generic_text)

    def test_policy_validator_rejects_missing_roles_and_unknown_profiles(self):
        invalid = copy.deepcopy(self.routing)
        invalid['role_profiles'].pop('bbk_worker')
        invalid['role_profiles']['bbk_validator'] = 'not-a-profile'
        errors = model_routing.validate_model_routing(invalid, version=(m5_ROOT / 'VERSION').read_text(encoding='utf-8').strip(), role_names=self.role_names)
        self.assertTrue(any(('missing roles' in error and 'bbk_worker' in error for error in errors)))
        self.assertTrue(any(('unknown profile' in error and 'not-a-profile' in error for error in errors)))

    def test_runtime_prompt_surface_is_product_neutral(self):
        paths = [m5_ROLES, m5_ROOT / 'spec' / 'method-content.json']
        paths.extend((m5_ROOT / 'shared' / 'skills').glob('*/SKILL.md'))
        paths.extend((m5_ROOT / 'shared' / 'references').glob('*.md'))
        for target in ('codex', 'omp', 'claude', 'generic'):
            paths.extend((m5_ROOT / 'projections' / target / 'agents').glob('*'))
        forbidden = ('blueprint', 'tenex', 'otobotto', 'autospec')
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
        custom['profiles']['mechanical']['omp'] = {'model': '@tiny', 'thinkingLevel': 'low'}
        custom['profiles']['mechanical']['codex'] = {'model': 'gpt-5.4-mini', 'model_reasoning_effort': 'low'}
        custom['profiles']['mechanical']['claude'] = {'model': 'sonnet', 'effort': 'low'}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / 'project'
            project.mkdir()
            policy = root / 'custom-model-routing.json'
            policy.write_text(json.dumps(custom, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
            installed = m5_run([sys.executable, m5_INSTALL, '--json', 'install', '--scope', 'project', '--root', project, '--codex', '--omp', '--claude', '--generic', '--model-routing', policy, '--no-language-profiles'])
            value = json.loads(installed.stdout)
            self.assertEqual(value['model_routing']['source'], policy.resolve().as_posix())
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
            self.assertIn('## Purpose', generic_text)
            self.assertNotIn('model_profile', generic_text)
            generic_manifest = json.loads((project / '.agents' / 'bbk' / 'agent-manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(generic_manifest['schema'], 'bbk.installed-generic-agent-manifest.v1')
            self.assertEqual(generic_manifest['agents']['bbk_worker']['model_routing']['omp']['model'], '@tiny')
            empty_registry = (project / '.agents' / 'skills' / 'bbk-installed-profiles' / 'SKILL.md').read_text(encoding='utf-8')
            self.assertIn('No language or domain profile is managed', empty_registry)
            self.assertNotIn('package-source placeholder', empty_registry)
            self.assertEqual(value['language_profile_registry']['profile_count'], 0)
            self.assertEqual(value['model_routing']['sha256'], hashlib.sha256(json.dumps(custom, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest())
            m5_run([sys.executable, m5_INSTALL, 'uninstall', '--scope', 'project', '--root', project])
        self.assertEqual(m5_sha256(canonical_worker), before)

    def test_invalid_external_policy_blocks_install_before_any_write(self):
        invalid = copy.deepcopy(self.routing)
        invalid['role_profiles'].pop('bbk_worker')
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
        self.assertIn('19 roles resolve through 3 model profiles', checked.stdout)
        generated = m5_run([sys.executable, m5_GENERATOR, '--check'])
        self.assertIn('19 roles, 3 model profiles, 4 targets, and 76 projections', generated.stdout)
