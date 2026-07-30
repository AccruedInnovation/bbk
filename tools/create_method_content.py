#!/usr/bin/env python3
"""Render or verify BBK skills and method references from one canonical spec."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SPEC=ROOT/'spec'/'method-content.json'

def expected():
    data=json.loads(SPEC.read_text(encoding='utf-8'))
    if data.get('schema')!='bbk.method-content.v1': raise SystemExit('unsupported method-content schema')
    version=(ROOT/'VERSION').read_text(encoding='utf-8').strip()
    if data.get('version')!=version: raise SystemExit(f"method-content version {data.get('version')} != {version}")
    values={}
    for name,text in data.get('skills',{}).items(): values[ROOT/'shared'/'skills'/name/'SKILL.md']=text.encode('utf-8')
    for name,text in data.get('references',{}).items(): values[ROOT/'shared'/'references'/name]=text.encode('utf-8')
    return values

def main():
    p=argparse.ArgumentParser(); p.add_argument('--check',action='store_true'); args=p.parse_args(); values=expected()
    if args.check:
        errors=[]
        for path,content in values.items():
            if not path.is_file(): errors.append(f'missing: {path.relative_to(ROOT)}')
            elif path.read_bytes()!=content: errors.append(f'drift: {path.relative_to(ROOT)}')
        actual=set((ROOT/'shared/skills').glob('*/SKILL.md'))|set((ROOT/'shared/references').glob('*.md'))
        extra=actual-set(values)
        errors.extend(f'unexpected: {path.relative_to(ROOT)}' for path in sorted(extra))
        if errors:
            print('BBK method-content drift:',file=sys.stderr)
            for error in errors: print(f'- {error}',file=sys.stderr)
            return 1
        print(f'OK: {len(values)} method assets match {SPEC.relative_to(ROOT)}')
        return 0
    for path,content in values.items(): path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(content)
    print(f'wrote {len(values)} method assets')
    return 0
if __name__=='__main__': raise SystemExit(main())
