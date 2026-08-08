# Alpha.17 bound worker-spawn qualification

Status: **automated PASS for WU-014**

Release target: `0.1.0-alpha.17`

## Qualified contract

`bbk_control_spawn` compiles a writable OMP child only after every identity
required by `REQ-029` is explicit and current. It validates the parent
orchestrator binding and its current digest-bound capability, validates the
child role capability, allocates exactly one jj workspace/change for the
work-unit attempt, creates an immutable planned binding, compiles a worker
packet, records the attempt, and reserves the exact OMP `task` input digest.
Unknown request fields, noncanonical roles, stale capability manifests, stale
parent capability references, unqualified hosts, altered task payloads, and
relative or escaping workspace/scope paths fail closed before writable child
execution.

OMP does not expose the eventual child session ID at the parent pre-effect
boundary. The packet therefore carries a deterministic `planned-session:*`
identity. The qualified `before_agent_start` hook reads the packet marker only
from the authenticated host-supplied CONTEXT suffix of an installed canonical
BBK role wrapper. It supersedes that planned binding with OMP's actual child
session before the first provider turn. The planned binding reference remains a
safe alias to the one activated successor, so wake/inject/resume retain the
same work-unit authority without rebinding from CWD or task prose.

## Enforced properties

- Work-unit, attempt, candidate, jj change, workspace, authority, path scope,
  mutation classes, return contract, parent session, and invocation are all
  bound before `task` admission.
- Parent session/invocation correlation comes from an active parent binding;
  CWD is never accepted as authority.
- Parent and worker role capabilities are current and digest-bound. Requested
  mutation classes must be a subset of the worker capability.
- Workspace and jj change allocation is exact and idempotent for a work-unit
  attempt; identity or idempotency collisions fail closed.
- Raw assignment text is delivered in the transient OMP task input but durable
  governance records contain only its SHA-256 digest.
- The built-in OMP `task` call must match the reserved complete input digest.
- Child activation requires exactly one admitted task call and one matching
  immutable attempt registration.
- A planned spawn cannot activate to two child sessions, and an actual child
  identity cannot use the `planned-session:` namespace.
- Wake, inject, and resume retain the activated binding. Retry requires an
  explicit superseding attempt and invocation.
- Ordinary and deliberately malformed legacy child-prompt fixtures remain on
  the established prompt-replacement path; strict spawn activation begins only
  when a bound-worker marker is actually present.

## Automated evidence

Focused contract run:

```text
python -m unittest -v \
  tests.test_worker_spawn \
  tests.test_omp_binding_registry \
  tests.test_omp_governed_profile \
  tests.test_governed_filesystem
```

Complete source-build standard profile:

```text
python tools/run_tests.py --all --profile standard \
  --skip-package-manifest --require-node --mode pooled --jobs 6
```

Observed result on 2026-08-04:

```text
Verification checks: 8/8 PASS
Unittest modules:    30
Tests reported:      505
Skipped:             5
Failures/errors:     0/0
Python files:        88 compiled
JSON files:          361 parsed
Implicit encodings:  0
OMP syntax:          PASS (Node.js 22.16.0)
```

The tests use the supplied local jj binary and a keyless OMP extension harness.
They cover exact compilation and reuse, incomplete binding denial, unknown-field
and role denial, scope escape, stale child and parent capability denial, exact
task admission, authenticated actual-child activation, activation without
admission, packet mismatch, continuity through the planned-reference alias,
ambient task denial, governed filesystem correlation, legacy prompt-boundary
compatibility, and Windows path-identity portability.

Machine-readable status is in
`evidence/qualification/bound-worker-spawn-alpha17.json`.

## Honest limits

- This is WU-014 automated qualification, not Alpha.17 release qualification.
- The release-wide real OMP/provider campaign required by WU-018 remains a
  manual user-run gate and is not claimed here.
- No operating-system sandbox is claimed.
- OMP versions other than qualified 16.4.8 remain `UNQUALIFIED`.
