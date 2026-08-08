#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

EXPECTED = {
    'WU-MANUAL-WORKER-A': ['src/worker-a/result.txt'],
    'WU-MANUAL-WORKER-B': ['src/worker-b/result.txt'],
}
EXPECTED_BYTES = {
    'src/worker-a/result.txt': b'alpha17-worker-a\n',
    'src/worker-b/result.txt': b'alpha17-worker-b\n',
}


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink() or path.is_symlink():
        raise RuntimeError(f'unsafe manual integration record path: {path}')
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    os.replace(tmp, path)


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise RuntimeError(f'{path} must contain one JSON object')
    return value


def package_root(project: Path) -> Path:
    current = read_object(project / '.bbk-kit' / 'current.json')
    root = Path(current['path']).resolve()
    if not root.is_dir() or root.is_symlink():
        raise RuntimeError(f'installed package root is unsafe: {root}')
    return root


def failure_code(exc: BaseException) -> str:
    code = str(getattr(exc, 'code', '') or '').strip()
    return code if code else 'MANUAL_INTEGRATION_FAILED'


def execute(args: argparse.Namespace) -> dict[str, Any]:
    project = Path(args.project_root).resolve()
    if not project.is_dir() or project.is_symlink():
        raise RuntimeError(f'unsafe project root: {project}')
    git_path = Path(args.git).resolve()
    mise_path = Path(args.mise).resolve()
    if not git_path.is_file() or not mise_path.is_file():
        raise RuntimeError('exact Git and mise launcher paths must resolve to files')
    os.environ['BBK_MISE'] = str(mise_path)
    package = package_root(project)
    sys.path.insert(0, str(package / 'tools'))
    sys.path.insert(0, str(package / 'tools' / 'substrate'))
    from gate_kernel import canonical_digest
    from governed_state import all_bindings, append_receipt
    from omp_binding_registry import resolve_binding_reference
    from substrate import git_adapter, jj_adapter

    bootstrap = read_object(project / '.bbk' / 'manual-qualification' / 'bootstrap.json')
    exact_actor = (
        args.session_id == bootstrap.get('root_session_id')
        and args.binding_ref == bootstrap.get('root_binding_ref')
        and args.invocation_id == bootstrap.get('root_invocation_id')
    )
    if not exact_actor:
        raise RuntimeError('manual integration actor does not match the exact create-once bootstrap root binding')
    if resolve_binding_reference(project, args.binding_ref) is None:
        raise RuntimeError('manual integration root binding is not active')

    out_path = project / '.bbk' / 'manual-qualification' / 'integration.json'
    if out_path.exists():
        prior = read_object(out_path)
        if prior.get('idempotency_key') != args.idempotency_key:
            raise RuntimeError('manual integration idempotency collision')
        return prior

    actual: list[dict[str, Any]] = []
    for work_unit, expected_paths in EXPECTED.items():
        matches = [
            binding for binding in all_bindings(project)
            if binding.get('request', {}).get('work_unit_id') == work_unit
            and binding.get('request', {}).get('role') == 'bbk_worker'
            and not str(binding.get('request', {}).get('session_id', '')).startswith('planned-session:')
        ]
        if len(matches) != 1:
            raise RuntimeError(f'{work_unit} requires exactly one activated worker binding; observed {len(matches)}')
        binding = matches[0]
        request = binding['request']
        workspace_ref = Path(request['workspace_ref']).resolve()
        workspace_parent = (project.parent / 'workspaces').resolve()
        if os.path.commonpath([str(workspace_parent), str(workspace_ref)]) != str(workspace_parent):
            raise RuntimeError(f'{work_unit} workspace escapes the qualification workspace parent')
        paths = jj_adapter.changed_paths(workspace_ref, revision=request['jj_change_id'])
        if paths != expected_paths:
            raise RuntimeError(f'{work_unit} changed paths {paths!r}; expected {expected_paths!r}')
        for relative in paths:
            observed = (workspace_ref / relative).read_bytes()
            if observed != EXPECTED_BYTES[relative]:
                raise RuntimeError(f'{work_unit} content mismatch for {relative}')
        identity = jj_adapter.identity(workspace_ref, revision=request['jj_change_id'])
        actual.append({
            'work_unit_id': work_unit,
            'binding_ref': binding['binding_id'],
            'session_id': request['session_id'],
            'attempt_id': request['attempt_id'],
            'workspace_ref': str(workspace_ref),
            'jj_change_id': request['jj_change_id'],
            'jj_commit_id': identity['jj_commit_id'],
            'changed_paths': paths,
        })

    expected_workspace_parent = (project.parent / 'workspaces').resolve()
    recorded_workspace_parent = Path(bootstrap['workspace_parent']).resolve()
    if recorded_workspace_parent != expected_workspace_parent:
        raise RuntimeError('bootstrap workspace parent does not match the exact qualification layout')
    destination = recorded_workspace_parent / 'alpha17-manual-integration'
    result = jj_adapter.merge_content_neutral(
        project,
        destination,
        work_unit_id='WU-MANUAL-INTEGRATION',
        attempt_id='integration-1',
        source_revisions=[item['jj_change_id'] for item in actual],
        parent_revision=bootstrap['parent_revision'],
        description='Alpha.17 manual content-neutral integration',
        workspace_name='alpha17-manual-integration',
    )
    workspace = Path(result['workspace_path']).resolve()
    if os.path.commonpath([str(recorded_workspace_parent), str(workspace)]) != str(recorded_workspace_parent):
        raise RuntimeError('integration workspace escapes the qualification workspace parent')

    expected_change_ids = [item['jj_change_id'] for item in actual]
    expected_commit_ids = [item['jj_commit_id'] for item in actual]
    expected_paths = sorted(EXPECTED_BYTES)
    if result.get('status') != 'INTEGRATED':
        raise RuntimeError(f"integration adapter returned {result.get('status')!r}, not INTEGRATED")
    if result.get('source_change_ids') != expected_change_ids:
        raise RuntimeError('integration source changes do not match the exact two worker changes')
    if result.get('source_commit_ids') != expected_commit_ids:
        raise RuntimeError('integration source commits do not match the exact two worker revisions')
    if sorted(result.get('parent_commit_ids', [])) != sorted(expected_commit_ids):
        raise RuntimeError('integration candidate parents do not match the exact two worker commits')
    if result.get('integrated_paths') != expected_paths:
        raise RuntimeError(f"integration paths {result.get('integrated_paths')!r}; expected {expected_paths!r}")
    if result.get('conflict_resolution_authority') != 'DENIED':
        raise RuntimeError('content-neutral adapter unexpectedly granted conflict-resolution authority')
    if result.get('integration_mode') != 'CONTENT_NEUTRAL_DISJOINT_PATHS':
        raise RuntimeError('integration adapter did not establish content-neutral disjoint paths')

    integrated_identity = jj_adapter.identity(workspace, revision=result['jj_change_id'])
    if sorted(integrated_identity.get('parent_commit_ids', [])) != sorted(expected_commit_ids):
        raise RuntimeError('post-integration jj identity does not retain the exact source parents')
    baseline_paths = jj_adapter.changed_paths_between(
        workspace,
        from_revision=bootstrap['parent_revision'],
        to_revision=result['jj_change_id'],
    )
    if baseline_paths != expected_paths:
        raise RuntimeError(
            f'post-integration baseline path closure {baseline_paths!r}; expected {expected_paths!r}'
        )

    git_repository_root = jj_adapter.git_repository_root(workspace)
    candidate = git_adapter.freeze_candidate(
        workspace,
        candidate_id='candidate:alpha17-manual:integrated',
        jj_change_id=result['jj_change_id'],
        workspace_path=workspace,
        git_path=git_path,
        git_repository_root=git_repository_root,
    )
    if Path(candidate['workspace_path']).resolve() != workspace:
        raise RuntimeError('frozen candidate workspace differs from integration workspace')

    files: dict[str, Any] = {}
    for relative, expected in EXPECTED_BYTES.items():
        data = (workspace / relative).read_bytes()
        if data != expected:
            raise RuntimeError(f'integrated candidate content mismatch for {relative}')
        files[relative] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    forbidden = [
        'src/root-orchestrator-forbidden.txt',
        'src/reviewer-forbidden.txt',
        'src/validator-forbidden.txt',
        'src/worker-b/cross-worker-forbidden.txt',
        'escape.txt',
    ]
    present_forbidden = [relative for relative in forbidden if (workspace / relative).exists()]
    if present_forbidden:
        raise RuntimeError(f'forbidden files present in integration candidate: {present_forbidden}')

    core = {
        'schema': 'bbk.alpha17-manual-content-neutral-integration.v1',
        'status': 'INTEGRATED',
        'idempotency_key': args.idempotency_key,
        'actor_binding_ref': args.binding_ref,
        'actor_invocation_id': args.invocation_id,
        'actor_session_id': args.session_id,
        'bootstrap_digest': bootstrap['bootstrap_digest'],
        'workers': actual,
        'adapter_result': result,
        'candidate': candidate,
        'files': files,
        'exact_source_parent_commit_ids': expected_commit_ids,
        'exact_integrated_paths': expected_paths,
        'baseline_revision': bootstrap['parent_revision'],
        'unresolved_conflicts': False,
        'forbidden_paths_present': present_forbidden,
        'conflict_resolution_authority': 'DENIED',
        'integration_mode': 'CONTENT_NEUTRAL_DISJOINT_PATHS',
        'jj_execution_mode': 'MISE_MANAGED',
        'jj_tool_spec': 'jj@0.43.0',
        'mise_path': str(mise_path),
    }
    core['integration_record_digest'] = f"sha256:{canonical_digest(core)}"
    integration_receipt, _ = append_receipt(project, 'MANUAL_CONTENT_NEUTRAL_INTEGRATION', core)

    admission_core = {
        'schema': 'bbk.candidate-integration-admission.v1',
        'status': 'PASS',
        'integration_receipt_ref': integration_receipt['receipt_id'],
        'integration_record_digest': core['integration_record_digest'],
        'candidate_id': candidate['candidate_id'],
        'candidate_digest': candidate['digest'],
        'workspace_ref': candidate['workspace_path'],
        'jj_change_id': candidate['jj_change_id'],
        'git_tree': candidate.get('git_tree'),
        'baseline_revision': bootstrap['parent_revision'],
        'source_change_ids': expected_change_ids,
        'source_commit_ids': expected_commit_ids,
        'parent_commit_ids': integrated_identity['parent_commit_ids'],
        'integrated_paths': expected_paths,
        'unresolved_conflicts': False,
        'conflict_resolution_authority': 'DENIED',
        'integration_mode': 'CONTENT_NEUTRAL_DISJOINT_PATHS',
    }
    admission_core['admission_digest'] = f"sha256:{canonical_digest(admission_core)}"
    candidate_admission, _ = append_receipt(project, 'CANDIDATE_INTEGRATION_ADMISSION', admission_core)
    output = {
        **core,
        'integration_receipt_ref': integration_receipt['receipt_id'],
        'candidate_admission_ref': candidate_admission['receipt_id'],
        'candidate_admission': admission_core,
    }
    atomic_json(out_path, output)
    failure_path = project / '.bbk' / 'manual-qualification' / 'integration-failure.json'
    failure_path.unlink(missing_ok=True)
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-root', required=True)
    parser.add_argument('--session-id', required=True)
    parser.add_argument('--binding-ref', required=True)
    parser.add_argument('--invocation-id', required=True)
    parser.add_argument('--idempotency-key', required=True)
    parser.add_argument('--git', required=True)
    parser.add_argument('--mise', required=True)
    args = parser.parse_args()
    project = Path(args.project_root).resolve()
    try:
        result = execute(args)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:  # noqa: BLE001 - preserve exact nonpass evidence
        failure: dict[str, Any] = {
            'schema': 'bbk.alpha17-manual-integration-failure.v1',
            'status': 'BLOCKED_TECHNICAL',
            'reason_code': failure_code(exc),
            'message': str(getattr(exc, 'message', exc)),
            'idempotency_key': args.idempotency_key,
            'actor_binding_ref': args.binding_ref,
            'actor_invocation_id': args.invocation_id,
            'actor_session_id': args.session_id,
            'candidate_bind_permitted': False,
            'smallest_next_action': 'Preserve this failure. Do not bind reviewer or validator to an integrated candidate until a current integration and candidate-admission receipt exists.',
        }
        try:
            package = package_root(project)
            sys.path.insert(0, str(package / 'tools'))
            from gate_kernel import canonical_digest
            from governed_state import append_receipt
            failure['failure_digest'] = f"sha256:{canonical_digest(failure)}"
            receipt, _ = append_receipt(project, 'MANUAL_CONTENT_NEUTRAL_INTEGRATION_FAILURE', failure)
            failure['failure_receipt_ref'] = receipt['receipt_id']
            atomic_json(project / '.bbk' / 'manual-qualification' / 'integration-failure.json', failure)
        except Exception as record_exc:  # noqa: BLE001
            failure['evidence_record_error'] = str(record_exc)
        print(json.dumps(failure, sort_keys=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
