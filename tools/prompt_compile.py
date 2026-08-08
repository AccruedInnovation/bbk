#!/usr/bin/env python3
"""Compile or reuse an invocation-specific BBK controller/role prompt.

This is the host-neutral adapter surface for Codex, OMP, Claude, and Pi.
Requests are JSON objects supplied with ``--request FILE`` or ``--request -``.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
TOOLS=ROOT/'tools'
if str(TOOLS) not in sys.path: sys.path.insert(0,str(TOOLS))

from compiled_procedures import (  # noqa: E402
    CompiledProcedureError, compile_controller_prompt, compile_role_prompt,
    compiled_state, followup_result, catalog_projection, canonical_json_bytes,
    load_profile_procedure_selection,
)
from generate_agents import base_instruction_text, controller_base_prompt  # noqa: E402
from model_routing import load_model_routing, route_for_role  # noqa: E402


def load_request(path:str)->dict[str,Any]:
    raw=sys.stdin.read() if path=='-' else Path(path).read_text(encoding='utf-8')
    value=json.loads(raw)
    if not isinstance(value,dict): raise ValueError('request must be a JSON object')
    return value


def write_artifacts(out:Path,result, catalog:dict[str,Any])->dict[str,str]:
    out.mkdir(parents=True,exist_ok=True)
    values={
      'prompt.md':result.prompt.encode(),
      'compiled-procedure-manifest.json':canonical_json_bytes(result.manifest),
      'effective-procedure-catalog.json':canonical_json_bytes(catalog),
      'prompt-compilation-plan.json':canonical_json_bytes(result.plan),
      'prompt-source-map.json':canonical_json_bytes({'schema':'bbk.prompt-source-map.v1','sections':list(result.source_map)}),
      'prompt-compilation-event.json':canonical_json_bytes(result.event),
      'logical-child-compiled-state.json':canonical_json_bytes(compiled_state(result)),
    }
    import hashlib
    records={}
    for name,data in values.items():
        (out/name).write_bytes(data)
        records[name]=hashlib.sha256(data).hexdigest()
    return records


def compile_request(req:dict[str,Any]):
    harness=str(req.get('harness') or '').lower()
    if harness not in {'codex','omp','claude','pi','generic'}: raise ValueError('unsupported harness')
    identity_kind=str(req.get('identity_kind') or 'ROLE').upper()
    profile=[str(x) for x in req.get('profile_procedures') or []]
    invocation=[str(x) for x in req.get('invocation_procedures') or []]
    additional_procedures:dict[str,dict[str,Any]]={}
    additional_available:list[str]=[]
    profile_registry_revision=str(req.get('profile_registry_revision') or '')
    profile_registry=req.get('profile_registry')
    profile_ids=[str(x) for x in req.get('profile_ids') or []]
    if profile_registry:
        additional_procedures, required, optional, observed_revision = load_profile_procedure_selection(
            Path(str(profile_registry)).expanduser().resolve(),
            profile_ids=profile_ids,
        )
        profile=list(dict.fromkeys([*profile,*required]))
        additional_available=list(optional)
        if profile_registry_revision and profile_registry_revision != observed_revision:
            raise ValueError('profile registry revision does not match selected installed profiles')
        profile_registry_revision=observed_revision
    common=dict(
      harness=harness, logical_child_id=req.get('logical_child_id'), invocation_id=req.get('invocation_id'),
      profile_procedures=profile, invocation_procedures=invocation,
      tool_capabilities=req.get('tool_capabilities'), adapter_template=req.get('adapter_template'),
      profile_registry_revision=profile_registry_revision,
      invocation_policy=req.get('invocation_policy'), root=ROOT,
      additional_procedures=additional_procedures,
      additional_available_procedures=additional_available,
    )
    if identity_kind=='CONTROLLER':
        base=controller_base_prompt(json.loads((ROOT/'spec/roles.json').read_text(encoding='utf-8')),host=harness)
        result=compile_controller_prompt(base,**common)
        identity=json.loads((ROOT/'spec/procedures/catalog.json').read_text(encoding='utf-8'))['controller']
    else:
        role_name=str(req.get('role') or '')
        roles=json.loads((ROOT/'spec/roles.json').read_text(encoding='utf-8'))['roles']
        role=next((x for x in roles if x['name']==role_name),None)
        if role is None: raise ValueError(f'unknown role {role_name!r}')
        route=route_for_role(load_model_routing(ROOT/'spec/model-routing.json',root=ROOT,role_spec={'roles':roles}),role_name)
        base=base_instruction_text({'package_version':(ROOT/'VERSION').read_text(encoding='utf-8').strip(),**json.loads((ROOT/'spec/roles.json').read_text(encoding='utf-8'))},role,host=harness)
        result=compile_role_prompt(base,role,return_contract=role.get('return_contract'),model_route=route,**common)
        identity=role
    catalog=catalog_projection(
        identity,
        result.manifest,
        additional_procedures=additional_procedures,
        additional_available_procedures=additional_available,
        root=ROOT,
    )
    return result,catalog


def main()->int:
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    c=sub.add_parser('compile'); c.add_argument('--request',required=True); c.add_argument('--output-dir'); c.add_argument('--include-prompt',action='store_true')
    f=sub.add_parser('followup'); f.add_argument('--state',required=True); f.add_argument('--request'); f.add_argument('--output-dir'); f.add_argument('--include-prompt',action='store_true')
    args=parser.parse_args()
    try:
        if args.command=='compile':
            req=load_request(args.request); result,catalog=compile_request(req)
        else:
            state=json.loads(Path(args.state).read_text(encoding='utf-8'))
            req=load_request(args.request) if args.request else {}
            result=followup_result(state,requested_procedure_ids=req.get('requested_procedure_ids'),harness=req.get('harness'),registry_revision=req.get('registry_revision'),compiler_sha256=req.get('compiler_sha256'),current_invalidation_keys=req.get('current_invalidation_keys'),root=ROOT)
            identity={'name':result.manifest.get('role'),'available':state.get('external_catalog',[])}
            catalog={'schema':'bbk.effective-procedure-catalog.v2','identity_kind':result.manifest.get('identity_kind','ROLE'),'role':result.manifest.get('role'),'available_external_procedures':list(result.external_catalog),'compiler_selectable_procedures':[],'suppressed_compiled_procedures':[x['id'] for x in result.manifest.get('procedures',[])],'catalog_sha256':result.manifest.get('effective_external_catalog_sha256'),'status':'PASS'}
        files=write_artifacts(Path(args.output_dir),result,catalog) if args.output_dir else {}
        response={'schema':'bbk.prompt-compilation-response.v1','status':'PASS','reused':result.reused,'manifest':result.manifest,'catalog':catalog,'event':result.event,'files':files}
        if args.include_prompt: response['prompt']=result.prompt
        sys.stdout.write(json.dumps(response,indent=2,ensure_ascii=False,sort_keys=True)+'\n')
        return 0
    except (OSError,ValueError,json.JSONDecodeError,CompiledProcedureError) as exc:
        sys.stdout.write(json.dumps({'schema':'bbk.prompt-compilation-response.v1','status':'ERROR','error':str(exc)},indent=2,sort_keys=True)+'\n')
        return 2

if __name__=='__main__': raise SystemExit(main())
