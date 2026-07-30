#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

PROFILE_ID='alpha8-fixture'; PROFILE_VERSION='0.1.0-alpha.4'
REQUEST_ROOT=Path('.')
OPS={
 'state-effect':'state_decision_effect','state-effect-inventory':'state_decision_effect','state-effect-review':'state_decision_effect',
 'review-context':'review_assurance','review-lens':'review_assurance','evidence-adapter':'review_assurance'
}
def digest(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def load_input(req, kind):
 for item in req.get('inputs',[]):
  if item.get('kind')==kind: return json.loads((REQUEST_ROOT/item['path']).read_text(encoding="utf-8"))
 raise SystemExit(f'missing input {kind}')
def result(req, payload, status='PASS', warnings=None, errors=None, limitations=None):
 return {'schema':'bbk.profile-capability-result.v1','profileId':PROFILE_ID,'profileVersion':PROFILE_VERSION,'capability':OPS[req['operation']],'operation':req['operation'],'status':status,'requestDigest':req['requestDigest'],'payload':payload,'warnings':warnings or [],'errors':errors or [],'limitations':limitations or ['fixture-only projection']}
def context_payload(req):
 manifest=load_input(req,'review-manifest')
 binding=next(i for i in req['inputs'] if i['kind']=='review-manifest')
 rel='profile-input/review-manifest.json'; size=(REQUEST_ROOT/binding['path']).stat().st_size
 item={'itemId':'PROFILE-INPUT-001','kind':'review-manifest','path':rel,'bytes':size,'sha256':binding['sha256'],'sourceClass':'profile-bound-input','generated':False,'redaction':'none'}
 content=digest([{'path':item['path'],'sha256':item['sha256'],'bytes':item['bytes'],'sourceClass':item['sourceClass'],'redaction':item['redaction']}])
 return {'schema':'bbk.review-context-manifest.v1','contextManifestId':'RCM-'+req['requestDigest'][:16].upper(),'revision':'1','subject':manifest['subject'],'reviewManifest':{'ref':manifest['manifestId'],'digest':binding['canonicalSha256']},'root':req['source']['root'],'contentRoot':content,'requiredSemanticObjects':['subject','assurance-contract'],'includedItems':[item],'retrievalOnlyItems':[],'excludedItems':[],'omissions':[],'redactions':[],'compiler':{'id':'alpha8-fixture-profile','version':PROFILE_VERSION,'policyDigest':req['requestDigest']},'contextPacks':[{'packId':'PACK-SHARD-001','shardRef':'SHARD-001','contentRoot':content,'bytes':size}],'shards':[{'shardId':'SHARD-001','primaryGroup':'profile-bound-input','primaryItemRefs':['PROFILE-INPUT-001'],'sharedItemRefs':[],'bytes':size,'contentRoot':content}],'crossShardAssertions':list(manifest.get('shardPlan',{}).get('crossShardAssertionRefs') or []),'completeness':'COMPLETE','blockers':[],'dependencyClosure':[manifest['subject']['digest'],binding['canonicalSha256'],content],'authorityDisclaimer':'Profile context is a bounded read-only projection; generic BBK review authority remains controlling.'}

def main():
 global REQUEST_ROOT
 p=argparse.ArgumentParser(); p.add_argument('--json',action='store_true'); p.add_argument('command'); p.add_argument('--request'); args,unknown=p.parse_known_args()
 if args.command not in OPS:
  print(json.dumps({'schema':'fixture.profile-result.v1','profileId':PROFILE_ID,'command':args.command,'unknown':unknown,'selectedSkills':['alpha8-router'],'plannedGates':[],'structureProjection':{'schema':'fixture.alpha8-structure-projection.v1','kind':'fixture'}})); return
 request_path=Path(args.request).resolve(); REQUEST_ROOT=request_path.parent
 req=json.loads(request_path.read_text(encoding="utf-8"))
 op=req['operation']
 if op=='state-effect':
  design=load_input(req,'state-decision-effect'); payload={'schema':'fixture.alpha8-state-effect-projection.v1','designRef':design.get('designId'),'designDigest':next(i['canonicalSha256'] for i in req['inputs'] if i['kind']=='state-decision-effect'),'representations':['sum-type'],'decisionBoundaries':['fixture-decision'],'effectBoundaries':['fixture-effect']}
 elif op=='state-effect-inventory':
  design=load_input(req,'state-decision-effect'); payload={'schema':'fixture.alpha8-state-effect-inventory.v1','inventoryId':'SEI-'+req['requestDigest'][:16].upper(),'subject':req['subject'],'designRef':design.get('designId'),'stateOwners':['fixture-state-owner'],'decisionEntryPoints':['fixture-decision'],'effectExecutors':['fixture-effect'],'recoveryMechanisms':['fixture-recovery']}
 elif op=='state-effect-review':
  inventory=load_input(req,'state-effect-inventory'); payload={'schema':'fixture.alpha8-state-effect-review.v1','subject':req['subject'],'inventoryRef':inventory.get('inventoryId'),'disposition':'PASS_ADVISORY','findings':[]}
 elif op=='review-context': payload=context_payload(req)
 elif op=='review-lens':
  payload={'schema':'fixture.alpha8-review-lens-result.v1','subject':req['subject'],'lensIds':req['context'].get('lensIds',[]),'assignmentIds':req['context'].get('assignmentIds',[]),'assertionEvaluations':[],'findings':[],'disposition':'INCONCLUSIVE'}
 else:
  receipt=load_input(req,'evidence-input'); receipt=dict(receipt); receipt['subject']=dict(receipt.get('subject') or {}); receipt['subject']['digest']=req['subject']['digest']; payload={'receipt':receipt}
 print(json.dumps(result(req,payload),sort_keys=True))
if __name__=='__main__': main()
