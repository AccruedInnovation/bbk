#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json
from pathlib import Path
root = Path.cwd().resolve()
expected = {
    'src/worker-a/result.txt': b'alpha17-worker-a\n',
    'src/worker-b/result.txt': b'alpha17-worker-b\n',
}
forbidden = [
    'src/root-orchestrator-forbidden.txt', 'src/reviewer-forbidden.txt',
    'src/validator-forbidden.txt', 'src/worker-b/cross-worker-forbidden.txt', 'escape.txt',
]
present = {}
for rel, value in expected.items():
    path = root / rel
    if path.is_file():
        data = path.read_bytes()
        if data != value: raise SystemExit(f'content mismatch: {rel}')
        present[rel] = hashlib.sha256(data).hexdigest()
if not present: raise SystemExit('no expected worker result exists')
unexpected = [rel for rel in forbidden if (root / rel).exists()]
if unexpected: raise SystemExit(f'forbidden paths present: {unexpected}')
print(json.dumps({'schema':'bbk.alpha17-manual-mise-check.v1','status':'PASS','present':present,'forbidden_present':unexpected},sort_keys=True))
