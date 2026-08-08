#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

HOST = 'omp/16.4.8'
ROLE = 'bbk_root_orchestrator'


def run(command: list[str], cwd: Path) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8',
        errors='backslashreplace',
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"command failed ({completed.returncode}): {' '.join(command)}\n{completed.stderr[-2000:]}")
    return completed.stdout.strip()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise RuntimeError(f'{path} must contain one JSON object')
    return value


def write_once_json(path: Path, value: dict[str, Any]) -> bool:
    """Create immutable bootstrap state; byte-identical races are harmless."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink() or path.is_symlink():
        raise RuntimeError(f'unsafe bootstrap path: {path}')
    data = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode('utf-8')
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if path.read_bytes() == data:
            return False
        raise RuntimeError('manual bootstrap was concurrently created with different immutable bytes')
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return True


def package_root(project: Path) -> Path:
    current = read_object(project / '.bbk-kit' / 'current.json')
    root = Path(current['path']).resolve()
    if not root.is_dir() or root.is_symlink():
        raise RuntimeError(f'installed package root is unsafe: {root}')
    return root


def existing_result(
    existing: dict[str, Any],
    *,
    project: Path,
    package: Path,
    session_id: str,
    parent_session_id: str,
    host_version: str,
) -> dict[str, Any]:
    expected_version = (package / 'VERSION').read_text(encoding='utf-8').strip()
    existing_project = str(existing.get('project_root') or '').strip()
    existing_package = str(existing.get('package_root') or '').strip()
    identity_fields = (
        str(existing.get('root_session_id') or '').strip(),
        str(existing.get('root_binding_ref') or '').strip(),
        str(existing.get('root_invocation_id') or '').strip(),
    )
    integrity_core = {
        key: value
        for key, value in existing.items()
        if key not in {'bootstrap_digest', 'bootstrap_receipt_ref'}
    }
    checks = {
        'schema': existing.get('schema') == 'bbk.alpha17-manual-bootstrap.v1',
        'status': existing.get('status') == 'PASS',
        'project_root': bool(existing_project) and Path(existing_project).resolve() == project,
        'package_root': bool(existing_package) and Path(existing_package).resolve() == package,
        'package_version': existing.get('package_version') == expected_version,
        'host_version': existing.get('host_version') == host_version == HOST,
        'root_identity': all(identity_fields),
        'root_parent': existing.get('root_parent_session_id') is None,
        'bootstrap_receipt': bool(str(existing.get('bootstrap_receipt_ref') or '').strip()),
        'bootstrap_integrity': existing.get('bootstrap_digest') == f"sha256:{canonical_digest_compat(integrity_core)}",
    }
    failed = sorted(key for key, passed in checks.items() if not passed)
    if failed:
        raise RuntimeError(f'existing manual bootstrap is stale or inconsistent: {failed}')
    if existing['root_session_id'] == session_id:
        return {
            **existing,
            'bootstrap_reused': True,
            'is_root_session': True,
            'observed_session_id': session_id,
            'observed_parent_session_id': parent_session_id or None,
        }
    return {
        'schema': 'bbk.alpha17-manual-bootstrap-observation.v1',
        'status': 'ROOT_PRESERVED',
        'is_root_session': False,
        'observed_session_id': session_id,
        'observed_parent_session_id': parent_session_id or None,
        'root_session_id': existing['root_session_id'],
        'root_binding_ref': existing['root_binding_ref'],
        'root_invocation_id': existing['root_invocation_id'],
        'root_bootstrap_digest': existing['bootstrap_digest'],
        'root_bootstrap_receipt_ref': existing['bootstrap_receipt_ref'],
        'root_bootstrap': existing,
    }


def canonical_digest_compat(value: Any) -> str:
    """Match BBK's canonical JSON digest without importing the installed package.

    Existing bootstrap validation runs before adding the installed package to
    ``sys.path``. Keeping the tiny canonicalization primitive local lets child
    sessions verify create-once state without loading untrusted project code or
    mutating interpreter import state.
    """
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-root', required=True)
    parser.add_argument('--session-id', required=True)
    parser.add_argument('--parent-session-id', default='')
    parser.add_argument('--host-version', required=True)
    parser.add_argument('--git', required=True)
    parser.add_argument('--mise', required=True)
    args = parser.parse_args()
    project = Path(args.project_root).resolve()
    session_id = str(args.session_id).strip()
    parent_session_id = str(args.parent_session_id or '').strip()
    if not session_id:
        raise RuntimeError('manual session identity is required')
    if args.host_version != HOST:
        raise RuntimeError(f'unqualified host {args.host_version!r}; expected {HOST}')
    if not project.is_dir() or project.is_symlink():
        raise RuntimeError(f'unsafe project root: {project}')
    package = package_root(project)
    bootstrap_path = project / '.bbk' / 'manual-qualification' / 'bootstrap.json'
    if bootstrap_path.exists():
        print(json.dumps(existing_result(
            read_object(bootstrap_path),
            project=project,
            package=package,
            session_id=session_id,
            parent_session_id=parent_session_id,
            host_version=args.host_version,
        ), sort_keys=True))
        return 0
    if parent_session_id:
        raise RuntimeError(
            'manual child session cannot create the root bootstrap; the top-level session must initialize it first'
        )

    sys.path.insert(0, str(package / 'tools'))
    sys.path.insert(0, str(package / 'tools' / 'substrate'))
    from gate_kernel import canonical_digest
    from governed_state import append_receipt
    from omp_binding_registry import create_initial_binding
    from substrate import jj_adapter

    capability_path = package / 'spec' / 'role-capabilities' / f'{ROLE}.json'
    capability = read_object(capability_path)
    capability_ref = f"role:{ROLE}@{capability['policy_version']}#{capability['manifest_digest']}"
    git_path = Path(args.git).resolve()
    mise_path = Path(args.mise).resolve()
    if not git_path.is_file() or not mise_path.is_file():
        raise RuntimeError('exact Git and mise launcher paths must resolve to files')
    os.environ['BBK_MISE'] = str(mise_path)
    git_head = run([str(git_path), 'rev-parse', 'HEAD'], project)
    parent_identity = jj_adapter.identity(project, revision='@-')
    if parent_identity['jj_commit_id'] != git_head:
        raise RuntimeError('jj @- does not match the exact Git baseline commit')
    current_identity = jj_adapter.identity(project)
    invocation_id = f"manual-root:{hashlib.sha256(session_id.encode()).hexdigest()}"
    authority_ref = 'authority:operator-alpha17-manual-qualification'
    workspaces = (project.parent / 'workspaces').resolve()
    workspaces.mkdir(parents=True, exist_ok=True)
    request = {
        'schema': 'bbk.invocation-binding-create.v1',
        'session_id': session_id,
        'invocation_id': invocation_id,
        'role': ROLE,
        'work_unit_id': 'WU-MANUAL-ROOT',
        'attempt_id': 'manual-root-1',
        'baseline_ref': f'git:{git_head}',
        'candidate_ref': f'git:{git_head}',
        'workspace_ref': str(project),
        'authority_ref': authority_ref,
        'scope': {
            'path_prefixes': [str((project / '.bbk').resolve())],
            'mutation_classes': ['COORDINATION_METADATA'],
            'semantic_scope': ['manual:alpha17', 'gate:VER-037'],
        },
        'return_contract': 'bbk.root-orchestrator-return.v2',
        'jj_change_id': current_identity['jj_change_id'],
        'idempotency_key': f'manual-bootstrap:{session_id}',
    }
    binding, created = create_initial_binding(project, request, capability_ref=capability_ref)
    core = {
        'schema': 'bbk.alpha17-manual-bootstrap.v1',
        'status': 'PASS',
        'host_version': args.host_version,
        'project_root': str(project),
        'package_root': str(package),
        'package_version': (package / 'VERSION').read_text(encoding='utf-8').strip(),
        'root_binding_ref': binding['binding_id'],
        'root_invocation_id': invocation_id,
        'root_session_id': session_id,
        'root_parent_session_id': None,
        'root_capability_ref': capability_ref,
        'baseline_ref': f'git:{git_head}',
        'parent_revision': git_head,
        'root_jj_change_id': current_identity['jj_change_id'],
        'jj_execution_mode': 'MISE_MANAGED',
        'jj_tool_spec': 'jj@0.43.0',
        'mise_path': str(mise_path),
        'authority_ref': authority_ref,
        'workspace_parent': str(workspaces),
        'expected_worker_work_units': ['WU-MANUAL-WORKER-A', 'WU-MANUAL-WORKER-B'],
        'binding_created': created,
    }
    core['bootstrap_digest'] = f"sha256:{canonical_digest(core)}"
    receipt, _ = append_receipt(project, 'MANUAL_HARNESS_BOOTSTRAP', core)
    core['bootstrap_receipt_ref'] = receipt['receipt_id']
    write_once_json(bootstrap_path, core)
    print(json.dumps({**core, 'bootstrap_reused': False, 'is_root_session': True}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
