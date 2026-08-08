# Alpha.17 orchestrator control-plane qualification

Status: **automated PASS for WU-015**

Release target: `0.1.0-alpha.17`

## Qualified contract

The four BBK orchestrator roles receive three typed coordination tools:

- `bbk_control_assign`
- `bbk_control_update`
- `bbk_control_integrate_request`

Each tool is admitted only from a qualified OMP 16.4.8 session with an active,
digest-current orchestrator invocation binding and `COORDINATION_METADATA`
authority. The host supplies the project/session identity and records the
pre-effect host event; model-controlled content cannot substitute CWD, role,
capability, or authority. The Python control plane converts accepted requests
to `bbk.coordination-command.v1` and invokes only the single BBK Beads writer.
Raw `bd`, unrestricted shell, and generic product-content mutation remain
forbidden to orchestrators.

Assignments resolve an immutable WU-014 attempt registration and require the
current worker binding, worker capability, work-unit, attempt, baseline,
candidate, workspace, jj change, authority, scope, return contract, parent
binding/session/invocation, packet digest, assignment digest, and task-input
digest to agree. A stale or altered identity fails before Beads mutation.

Integration calls record requests only. `CONTENT_CHANGING` and `UNKNOWN`
conflicts route to a future bound Integration Worker. An orchestrator cannot
submit conflict-resolution prose or claim that a candidate effect occurred.
`NONE` and `CONTENT_NEUTRAL` requests may route to a separately qualified
content-neutral adapter, but this work unit performs no candidate integration.

## Enforced properties

- Only `tools/substrate/beads_adapter.py` invokes the qualified `bd` binary.
- Every effect carries exact work-unit, attempt, transition, correlation,
  expected-revision, and idempotency identities.
- The semantic coordination record, backend Beads command receipt, and Beads
  projection receipt are immutable and separately addressable.
- Exact retries reuse prior semantic and backend effects; changed content under
  an existing idempotency key fails closed.
- The Beads writer independently revalidates the closed command shape, actor
  role, operation/transition pairing, assignment and integration subcontracts,
  and product-payload exclusions. Calling the adapter directly cannot bypass
  the agent-facing validator.
- Unknown fields, multiline summaries, patch fragments, raw prompt fields,
  false content-effect claims, and inconsistent integration routes are denied
  before effect.
- Orchestrator capability projections exclude generic write/edit/delete,
  direct Beads write, raw `bd`, and unqualified shell authority.

## Acceptance assertions

- `VER-020`: **PASS** — governed Beads effects use one locked adapter and no
  orchestrator receives a raw Beads mutation path.
- `VER-021`: **PASS** — assign, update, and integration requests are typed and
  carry exact work-unit, attempt, transition, correlation, revision, and
  idempotency identities.
- `VER-026`: **PASS** — Root, Territory, Worker, and Validator Orchestrators
  have coordination metadata authority only, with negative product-write tests.
- `VER-034`: **PASS** — content-changing or unknown integration conflicts are
  request-only and route to a bound Integration Worker.

## Automated evidence

Fast source-build profile:

```text
python tools/run_tests.py --all --profile fast \
  --skip-package-manifest --require-node --mode pooled --jobs 6
```

Complete standard module set, executed in bounded alphabetic shards because the
qualification container limits one command invocation to approximately thirty
seconds:

```text
for prefix in a c g h i o p r s w; do
  python tools/run_tests.py -q --profile standard \
    --mode isolated --jobs 6 -p "test_${prefix}*.py"
done
```

Every standard-profile module was selected exactly once. Observed result on
2026-08-04:

```text
Source-build checks:  8/8 PASS
Standard modules:     31
Tests reported:       518
Skipped:              1 optional live host-contract probe
Failures/errors:      0/0
Fast tests:           153, 0 skipped, 0 failures/errors
Python files:         90 compiled
JSON files:           368 parsed
Implicit encodings:   0
Role projections:     19 current
OMP syntax:           PASS (Node.js 22.16.0)
Real local Beads:     PASS
Network/API keys:     not used
```

The suite covers current actor and worker capabilities, exact assignment
registration, stale and mismatched identity denial, typed state updates,
content-neutral and content-changing integration routing, strict direct-adapter
revalidation, semantic/backend/projection receipt separation, real local Beads
create/update/comment behavior, exact idempotent retry, OMP host projection,
role-capability negatives, installer/runtime inventory, Windows portability,
and all prior WU-014 continuity regressions.

Machine-readable status is in
`evidence/qualification/orchestrator-control-plane-alpha17.json`.

## Honest limits

- This qualifies WU-015 automation, not the Alpha.17 release as a whole.
- No integration candidate effect is implemented or claimed in this work unit.
- The content-neutral integration adapter and bound Integration Worker campaign
  are later work; this tool only records and routes the request.
- No operating-system sandbox is claimed.
- OMP versions other than 16.4.8 remain `UNQUALIFIED`.
- The release-wide, API-key-enabled OMP qualification remains the manual WU-018
  gate before Alpha.17 finalization.
