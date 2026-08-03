"""Consolidated BBK regression tests grouped by responsibility.

Historical release-specific modules were merged to keep the public repository
readable while retaining their behavioral coverage.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Historical source: test_alpha7_review_assurance.py
# ---------------------------------------------------------------------------
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
m1_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(m1_ROOT / 'tools'))
from contracts import canonical_digest
from review_assurance import aggregate_review, build_review_run, compile_review_context, compile_review_manifest, create_finding_disposition, reconcile_findings, validate_assurance_contract, validate_evidence_receipt, validate_review_attempt, validate_review_context, validate_review_manifest, validate_review_run

def m1_load(rel: str):
    return json.loads((m1_ROOT / rel).read_text(encoding='utf-8'))

class Alpha7ReviewAssuranceTests(unittest.TestCase):

    def setUp(self):
        self.assurance = m1_load('fixtures/review/assurance-consequential.json')
        self.manifest = m1_load('fixtures/review/manifest-consequential.json')
        self.context = m1_load('fixtures/review/context-complete.json')
        self.attempts = [m1_load('fixtures/review/attempt-blind.json'), m1_load('fixtures/review/attempt-intent.json')]
        self.receipts = [m1_load('fixtures/review/evidence-receipt-v2.json'), m1_load('fixtures/review/evidence-intent.json')]

    def test_assurance_contract_and_duplicate_assertions(self):
        self.assertTrue(validate_assurance_contract(self.assurance)['valid'])
        invalid = validate_assurance_contract(m1_load('fixtures/review/invalid-assurance-duplicate.json'))
        self.assertFalse(invalid['valid'])
        self.assertTrue(any(('duplicate' in message.lower() for message in invalid['errors'])))

    def test_manifest_compilation_is_deterministic_and_intent_aware(self):
        first = compile_review_manifest(self.assurance, manifest_id='RM-COMPILED', purpose='acceptance')
        second = compile_review_manifest(self.assurance, manifest_id='RM-COMPILED', purpose='acceptance')
        self.assertEqual(canonical_digest(first), canonical_digest(second))
        self.assertTrue(validate_review_manifest(first, self.assurance)['valid'])
        lenses = {item['lens'] for item in first['lensAssignments']}
        self.assertIn('intent-outcome', lenses)
        self.assertIn('state-concurrency-effect-recovery', lenses)
        self.assertEqual(len(first['lensAssignments']), 3)
        self.assertEqual(first['provenance']['bbkVersion'], '0.1.0-alpha.15')

    def test_manifest_rejects_unjustified_assertion_overlap(self):
        value = copy.deepcopy(self.manifest)
        duplicate = copy.deepcopy(value['lensAssignments'][0])
        duplicate['assignmentId'] = 'LA-DUPLICATE'
        duplicate['independence'] = {'required': False, 'dimensions': [], 'reason': ''}
        value['lensAssignments'].append(duplicate)
        result = validate_review_manifest(value, self.assurance)
        self.assertFalse(result['valid'])
        self.assertTrue(any(('overlap' in message.lower() for message in result['errors'])))

    def test_context_uses_full_content_and_blocks_missing_required_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'README.md').write_text('alpha\n', encoding='utf-8')
            manifest = copy.deepcopy(self.manifest)
            complete = compile_review_context(manifest, root, context_id='RCM-1')
            self.assertEqual(complete['completeness'], 'COMPLETE')
            self.assertTrue(validate_review_context(complete, manifest)['valid'])
            root_digest = complete['contentRoot']
            (root / 'README.md').write_text('beta\n', encoding='utf-8')
            changed = compile_review_context(manifest, root, context_id='RCM-1')
            self.assertNotEqual(root_digest, changed['contentRoot'])
            manifest['contextPolicy']['requiredPaths'] = ['README.md', 'required.md']
            blocked = compile_review_context(manifest, root, context_id='RCM-2')
            self.assertEqual(blocked['completeness'], 'BLOCKED_REQUIRED_CONTEXT_MISSING')
            self.assertTrue(blocked['blockers'])

    def test_review_context_excludes_examples_with_shared_non_operational_classification(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'EXAMPLE-template.json').write_text('{"example": true}\n', encoding='utf-8')
            (root / 'real.json').write_text('{"real": true}\n', encoding='utf-8')
            manifest = copy.deepcopy(self.manifest)
            manifest['contextPolicy']['requiredPaths'] = []
            context = compile_review_context(manifest, root, context_id='RCM-EXAMPLES')
            included = {item['path'] for item in context['includedItems']}
            omitted = {item['path']: item['reason'] for item in context['omissions']}
            self.assertEqual(included, {'real.json'})
            self.assertEqual(omitted.get('EXAMPLE-template.json'), 'non-operational-example')
            self.assertEqual(context['completeness'], 'COMPLETE_WITH_DECLARED_EXCLUSIONS')
            self.assertTrue(validate_review_context(context, manifest)['valid'])

    def test_cross_shard_assertion_requires_cross_shard_lens_and_attempt(self):
        manifest = copy.deepcopy(self.manifest)
        manifest['shardPlan'] = {'mode': 'semantic', 'grouping': 'execution-slice-or-responsibility', 'crossShardAssertionRefs': ['A-INTENT']}
        invalid = validate_review_manifest(manifest, self.assurance)
        self.assertFalse(invalid['valid'])
        intent_assignment = next((item for item in manifest['lensAssignments'] if 'A-INTENT' in item['primaryAssertionRefs']))
        intent_assignment['lens'] = 'cross-shard-integration'
        intent_assignment['reviewerCapabilityRequirements'] = ['cross-shard-integration']
        self.assertTrue(validate_review_manifest(manifest, self.assurance)['valid'])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'README.md').write_text('root\n', encoding='utf-8')
            (root / 'provider').mkdir()
            (root / 'provider' / 'a.txt').write_text('a\n', encoding='utf-8')
            (root / 'consumer').mkdir()
            (root / 'consumer' / 'b.txt').write_text('b\n', encoding='utf-8')
            context = compile_review_context(manifest, root, context_id='RCM-SHARDED')
            self.assertGreaterEqual(len(context['shards']), 2)
            self.assertTrue(validate_review_context(context, manifest)['valid'])
            missing = aggregate_review(manifest, context, self.attempts, [], receipts=self.receipts)
            self.assertEqual(missing['result'], 'INCONCLUSIVE')
            cross_attempt = copy.deepcopy(self.attempts[1])
            cross_attempt['lens'] = 'cross-shard-integration'
            complete = aggregate_review(manifest, context, [self.attempts[0], cross_attempt], [], receipts=self.receipts)
            self.assertEqual(complete['result'], 'PASS')

    def test_unstructured_evidence_is_not_silent_strong_evidence(self):
        receipt = copy.deepcopy(self.receipts[0])
        receipt['receiptId'] = 'ER-UNSTRUCTURED'
        receipt['trustClass'] = 'UNSTRUCTURED_OBSERVATION'
        receipt['assertionRefs'] = ['A-EFFECT-ONCE']
        result = validate_evidence_receipt(receipt)
        self.assertTrue(result['valid'], result)
        self.assertTrue(any(('not assertion-satisfying' in message for message in result['warnings'])))
        aggregate = aggregate_review(self.manifest, self.context, self.attempts, [], receipts=[receipt, self.receipts[1]])
        self.assertEqual(aggregate['result'], 'INCONCLUSIVE')
        effect = next((item for item in aggregate['assertionResults'] if item['assertionRef'] == 'A-EFFECT-ONCE'))
        self.assertEqual(effect['status'], 'INCONCLUSIVE')

    def test_wrong_subject_required_receipt_makes_review_stale(self):
        receipt = copy.deepcopy(self.receipts[0])
        receipt['subject']['digest'] = 'f' * 64
        aggregate = aggregate_review(self.manifest, self.context, self.attempts, [], receipts=[receipt, self.receipts[1]])
        self.assertEqual(aggregate['result'], 'STALE')
        self.assertTrue(any(('another subject' in blocker for blocker in aggregate['blockers'])))

    def test_complete_run_passes_and_is_content_bound(self):
        run = build_review_run(self.manifest, self.context, run_id='RR-ORDER-001', attempts=self.attempts, receipts=self.receipts, findings=[], dispositions=[])
        self.assertEqual(run['aggregate']['result'], 'PASS')
        self.assertTrue(validate_review_run(run, self.manifest, self.context)['valid'])
        changed = copy.deepcopy(run)
        changed['subject']['ref'] = 'OTHER'
        self.assertFalse(validate_review_run(changed, self.manifest, self.context)['valid'])

    def test_reviewer_infrastructure_failure_is_not_candidate_failure(self):
        broken = copy.deepcopy(self.attempts[0])
        broken['completionState'] = 'ERROR'
        broken['assertionEvaluations'] = []
        broken['infrastructureErrors'] = ['model provider unavailable']
        aggregate = aggregate_review(self.manifest, self.context, [broken, self.attempts[1]], [], receipts=self.receipts)
        self.assertEqual(aggregate['result'], 'ERROR')
        self.assertFalse(any(('failed' in item.lower() for item in aggregate['blockers'])))

    def test_nonrediscovery_does_not_close_finding(self):
        finding = m1_load('fixtures/review/finding-open.json')
        aggregate = aggregate_review(self.manifest, self.context, self.attempts, [finding], receipts=self.receipts)
        self.assertEqual(aggregate['result'], 'NEEDS_REVISION')
        self.assertIn(finding['findingId'], aggregate['openFindingRefs'])
        disposition = m1_load('fixtures/review/finding-disposition-fixed.json')
        closed = aggregate_review(self.manifest, self.context, self.attempts, [finding], [disposition], self.receipts)
        self.assertEqual(closed['result'], 'PASS')
        self.assertNotIn(finding['findingId'], closed['openFindingRefs'])

    def test_targeted_and_blind_attempt_visibility_remain_distinct(self):
        blind = self.attempts[0]
        self.assertEqual(blind['priorFindingsVisibility'], 'HIDDEN')
        targeted = copy.deepcopy(blind)
        targeted['attemptId'] = 'ATT-TARGETED'
        targeted['priorFindingsVisibility'] = 'TARGETED'
        targeted['assignmentRef'] = 'LA-A-EFFECT-ONCE'
        self.assertTrue(validate_review_attempt(targeted)['valid'])
        self.assertNotEqual(canonical_digest(blind), canonical_digest(targeted))

    def test_reconciliation_preserves_original_findings(self):
        left = m1_load('fixtures/review/finding-open.json')
        right = copy.deepcopy(left)
        right['findingId'] = 'F-ORDER-002'
        proposal = reconcile_findings([left, right])
        self.assertEqual(proposal['proposals'][0]['relationship'], 'PROBABLE_DUPLICATE')
        self.assertTrue(proposal['proposals'][0]['requiresConfirmation'])
        self.assertEqual(left['lifecycle'], 'OPEN')
        self.assertEqual(right['lifecycle'], 'OPEN')

    def test_explicit_disposition_requires_closure_evidence(self):
        finding = m1_load('fixtures/review/finding-open.json')
        with self.assertRaises(ValueError):
            create_finding_disposition(finding, disposition='FIXED', successor_ref='CANDIDATE-ORDER-002', successor_digest='a' * 64, evidence_refs=[], review_attempt_ref='ATT-CLOSURE', authority_ref=None, residual_impact='none', reopening_triggers=[], disposition_id='FDISP-BAD', created_at='2026-07-24T00:00:00Z')

# ---------------------------------------------------------------------------
# Historical source: test_alpha7_state_effect.py
# ---------------------------------------------------------------------------
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
m2_ROOT = Path(__file__).resolve().parents[1]
m2_BBK = m2_ROOT / 'tools' / 'bbk.py'
sys.path.insert(0, str(m2_ROOT / 'tools'))
from state_effect import compare_state_effect_inventory, validate_slice_v2, validate_state_decision_effect, validate_structure_v2, validate_transition_trace, validate_transition_trace_set
from contracts import validate_profile, validate_work_unit

def m2_load(rel: str):
    return json.loads((m2_ROOT / rel).read_text(encoding='utf-8'))

def m2_run_json(argv, *, cwd=m2_ROOT, env=None, check=True):
    completed = subprocess.run([str(x) for x in argv], cwd=str(cwd), env=env, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check)
    return (json.loads(completed.stdout), completed)

class Alpha7StateEffectTests(unittest.TestCase):

    def test_valid_and_invalid_state_effect_designs(self):
        valid = validate_state_decision_effect(m2_load('fixtures/state-effect/contract-order.json'))
        self.assertTrue(valid['valid'], valid)
        self.assertEqual(valid['summary']['applicability'], 'CONTRACT')
        invalid = validate_state_decision_effect(m2_load('fixtures/state-effect/invalid-authoritative-derived.json'))
        self.assertFalse(invalid['valid'])
        self.assertTrue(any(('authoritative state and derived' in message for message in invalid['errors'])))

    def test_transition_trace_set_and_stale_design_revision(self):
        design = m2_load('fixtures/state-effect/contract-order.json')
        traces = [m2_load(f'fixtures/state-effect/trace-{name}.json') for name in ('happy', 'duplicate', 'ack-lost')]
        report = validate_transition_trace_set(traces, design)
        self.assertTrue(report['valid'], report)
        self.assertEqual(report['traceCount'], 3)
        stale = json.loads(json.dumps(traces[0]))
        stale['designRevision'] = '0'
        result = validate_transition_trace_set([stale], design)
        self.assertFalse(result['valid'])
        self.assertTrue(any(('revision' in message.lower() for message in result['errors'])))

    def test_structure_and_slice_v2_preserve_v1_compatibility(self):
        structure = m2_load('fixtures/structure/software-contract-v2.json')
        slice_value = m2_load('fixtures/slices/software-slice-v2.json')
        structure_result = validate_structure_v2(structure)
        slice_result = validate_slice_v2(slice_value)
        self.assertTrue(structure_result['valid'], structure_result)
        self.assertTrue(slice_result['valid'], slice_result)
        self.assertEqual(structure_result['stateDecisionEffect']['summary']['applicability'], 'CONTRACT')
        self.assertTrue(slice_value['stateTransitionTouchpoints'])
        self.assertTrue(slice_value['effectBoundaryTouchpoints'])

    def test_planned_actual_review_classifies_material_divergence(self):
        contract = m2_load('fixtures/structure/software-contract-v2.json')
        design = contract['stateDecisionEffectDesign']
        conformant = compare_state_effect_inventory(design, m2_load('fixtures/state-effect/inventory-conformant.json'))
        divergent = compare_state_effect_inventory(design, m2_load('fixtures/state-effect/inventory-divergent.json'))
        self.assertEqual(conformant['disposition'], 'accept-with-advisories')
        self.assertTrue(any((item['divergenceClass'] == 'advisory-drift' for item in conformant['stateDecisionEffectFindings'])))
        self.assertEqual(divergent['disposition'], 'revise')
        self.assertTrue(any((item['divergenceClass'] == 'material-divergence' for item in divergent['stateDecisionEffectFindings'])))

    def test_work_unit_state_effect_and_review_bindings(self):
        work = m2_load('fixtures/work-units/query-service.json')
        work.update({'profileHints': ['stateful', 'recovery'], 'stateDecisionEffectRefs': ['SDE-ORDER-001@1'], 'stateTransitionTraceRefs': ['TRACE-ORDER-HAPPY'], 'assuranceContractRefs': ['AC-ORDER-001@1'], 'reviewManifestRefs': ['RM-ORDER-001@1']})
        result = validate_work_unit(work)
        self.assertTrue(result['valid'], result)
        broken = dict(work)
        broken['stateDecisionEffectRefs'] = []
        self.assertFalse(validate_work_unit(broken)['valid'])

    def test_profile_capability_states_are_explicit(self):
        legacy = validate_profile(m2_load('fixtures/profiles/legacy/PROFILE.json'))
        alpha7 = validate_profile(m2_load('fixtures/profiles/alpha7/PROFILE.json'))
        self.assertEqual(legacy['stateDecisionEffectSupport'], 'legacy-summary')
        self.assertEqual(legacy['reviewAssuranceSupport'], 'legacy-no-review-manifest')
        self.assertEqual(alpha7['stateDecisionEffectSupport'], 'supported')
        self.assertEqual(alpha7['reviewAssuranceSupport'], 'supported')
        self.assertTrue(alpha7['valid'], alpha7)
        inspected, _ = m2_run_json([sys.executable, m2_BBK, '--json', 'profile', 'inspect', '--profile-dir', m2_ROOT / 'fixtures' / 'profiles' / 'alpha7', '--id', 'alpha7-fixture'])
        self.assertEqual(inspected['package_verification']['status'], 'PASS')

    def test_candidate_bound_inventory_change_invalidates_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            project = base / 'project'
            project.mkdir()
            source = project
            subprocess.run(['git', 'init', '-q'], cwd=source, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(['git', 'config', 'user.email', 'bbk@example.invalid'], cwd=source, check=True)
            subprocess.run(['git', 'config', 'user.name', 'BBK Test'], cwd=source, check=True)
            (source / 'main.txt').write_text('v1\n', encoding='utf-8')
            subprocess.run(['git', 'add', 'main.txt'], cwd=source, check=True)
            subprocess.run(['git', 'commit', '-m', 'initial'], cwd=source, check=True, stdout=subprocess.PIPE)
            m2_run_json([sys.executable, m2_BBK, '--json', 'init', '--root', project, '--project-id', 'TEST-ALPHA7-CANDIDATE'])
            inventory = base / 'inventory.json'
            inventory.write_text(json.dumps(m2_load('fixtures/state-effect/inventory-conformant.json'), sort_keys=True), encoding='utf-8')
            frozen, _ = m2_run_json([sys.executable, m2_BBK, '--json', 'candidate', 'freeze', '--root', project, '--id', 'C-001', '--structure-inventory', inventory])
            self.assertEqual(frozen['status'], 'FROZEN')
            current, _ = m2_run_json([sys.executable, m2_BBK, '--json', 'candidate', 'check', '--root', project, '--id', 'C-001'])
            self.assertTrue(current['current'])
            inventory.write_text(inventory.read_text(encoding='utf-8') + '\n', encoding='utf-8')
            stale, _ = m2_run_json([sys.executable, m2_BBK, '--json', 'candidate', 'check', '--root', project, '--id', 'C-001'])
            self.assertFalse(stale['current'])
            self.assertEqual(stale['comparison']['summary']['bound_dependency_changed'], 1)

# Deterministic fast/standard/release selection used by tools/run_tests.py.
from tests._test_profiles import load_profiled_tests as load_tests
