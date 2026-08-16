#!/usr/bin/env python3
"""Validate BBK alpha.8 typed profile-dispatch fixtures and inherited alpha.7 corpus."""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path
from typing import Any, Sequence
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from contracts import validate_profile, validate_profile_capability_request, validate_profile_capability_result
from validate_alpha7_fixtures import validate as validate_alpha7
from runtime_requirements import python_command, python_environment

def run_json(args:list[str])->dict[str,Any]:
 p=subprocess.run(python_command(ROOT/'tools/bbk.py','--json',*args),cwd=ROOT,env=python_environment(),text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if p.returncode!=0: return {'status':'ERROR','stderr':p.stderr,'stdout':p.stdout,'argv':args}
 return json.loads(p.stdout)
def check(name,status,detail=None): return {'name':name,'status':status,'detail':detail}
def validate()->dict[str,Any]:
 checks=[]
 inherited=validate_alpha7(); checks.append(check('inherited-alpha7-corpus',inherited['status'],{'semantic':inherited['semanticCheckCount'],'schema':inherited['schemaCheckCount']}))
 a8=json.loads((ROOT/'fixtures/profiles/alpha8/PROFILE.json').read_text(encoding="utf-8")); report=validate_profile(a8)
 checks.append(check('alpha8-profile-contract','PASS' if report['valid'] else 'FAIL',report))
 a7=json.loads((ROOT/'fixtures/profiles/alpha7/PROFILE.json').read_text(encoding="utf-8")); legacy=validate_profile(a7)
 checks.append(check('alpha7-profile-remains-legacy-declared','PASS' if legacy['valid'] and legacy['stateDecisionEffectDispatch']=='legacy-declared' and legacy['reviewAssuranceDispatch']=='legacy-declared' else 'FAIL',legacy))
 dispatch=run_json(['profile','dispatch','--operation','state-effect','--id','alpha8-fixture','--profile-dir',str(ROOT/'fixtures/profiles/alpha8'),'--source',str(ROOT),'--state-decision-effect',str(ROOT/'fixtures/state-effect/contract-order.json')])
 req=validate_profile_capability_request(dispatch.get('request')) if dispatch.get('request') else {'valid':False,'errors':['missing request']}
 res=validate_profile_capability_result(dispatch.get('result'),expected_profile_id='alpha8-fixture',expected_profile_version='0.1.0-alpha.4',expected_operation='state-effect',expected_request_digest=(dispatch.get('request') or {}).get('requestDigest')) if dispatch.get('result') else {'valid':False,'errors':['missing result']}
 checks.append(check('typed-dispatch-request','PASS' if req.get('valid') else 'FAIL',req))
 checks.append(check('typed-dispatch-result','PASS' if res.get('valid') else 'FAIL',res))
 stable_args=['profile','resolve','--id','alpha8-fixture','--profile-dir',str(ROOT/'fixtures/profiles/alpha8'),'--source',str(ROOT),'--role','reviewer','--task-profile','interface-schema-migration','--assurance-tier','consequential','--state-decision-effect',str(ROOT/'fixtures/state-effect/contract-order.json'),'--assurance-contract',str(ROOT/'fixtures/review/assurance-consequential.json'),'--review-manifest',str(ROOT/'fixtures/review/manifest-consequential.json'),'--evidence-input',str(ROOT/'fixtures/review/evidence-receipt-v2.json')]
 one=run_json(stable_args); two=run_json(stable_args)
 checks.append(check('stable-effective-dispatch-digest','PASS' if one.get('effective_sha256') and one.get('effective_sha256')==two.get('effective_sha256') else 'FAIL',{'first':one.get('effective_sha256'),'second':two.get('effective_sha256')}))
 dispatch_summary = one.get('profile_dispatch') or {}
 operations = dispatch_summary.get('operations', [])
 unhandled = dispatch_summary.get('unhandledReviewAssignments', [])
 checks.append(check(
  'smallest-supported-dispatch-set',
  'PASS' if len(operations)==7 and len(unhandled)==1 else 'FAIL',
  {
   'operationCount': len(operations),
   'operations': [
    {
     'operation': item.get('operation'),
     'status': item.get('status'),
     'lensId': item.get('lensId'),
     'assignmentId': item.get('assignmentId'),
    }
    for item in operations
   ],
   'unhandledReviewAssignments': unhandled,
  },
 ))
 failures=[x for x in checks if x['status']=='FAIL']
 return {'schema':'bbk.alpha8-fixture-validation.v1','bbkVersion':(ROOT/'VERSION').read_text(encoding="utf-8").strip(),'status':'PASS' if not failures else 'FAIL','checkCount':len(checks),'failures':failures,'checks':checks}
def main(argv:Sequence[str]|None=None)->int:
 p=argparse.ArgumentParser();p.add_argument('--json',action='store_true');p.add_argument('--output');a=p.parse_args(argv);r=validate();text=json.dumps(r,indent=2,sort_keys=True)+'\n'
 if a.output: Path(a.output).write_text(text, encoding="utf-8")
 if a.json: print(text,end='')
 else: print(f"BBK alpha.8 fixture validation: {r['status']} ({r['checkCount']} checks)")
 return 0 if r['status']=='PASS' else 1
if __name__=='__main__': raise SystemExit(main())
