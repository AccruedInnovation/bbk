# PRD H — Planning bundle compiler

**Status:** Proposed — later hardening

**Owner kind:** Planning compiler owned by the Planning Wayfinder; transactional persistence owned by the existing planning engine
**Priority:** Later hardening; prerequisite for routine Territory-boundary compilation

## Problem and evidence

BBK already defines accepted outcome fit, architecture, decisions, execution authority, WorkUnits, assertions, rolling-wave readiness, project coverage, and atomic plan events. The missing operation is a deterministic closure step that turns those independently accepted objects into one inspectable operating baseline and executable work graph. Today a Planning Wayfinder must mechanically copy identifiers, dependencies, digests, coverage edges, dispatch facts, and Beads projection intent into several records. That creates avoidable omission and stale-reference risk at the exact planning-to-execution boundary.

The repository already establishes the constraints this compiler must preserve:

- `docs/WAYFINDING-AND-GRILL.md` forbids Planning and Phase Wayfinders from inventing missing outcome, interface, architecture, authority, risk-acceptance, or verification decisions.
- `tools/planning_optimization.py` and `bbk plan transact` already own append-only plan events, projection regeneration, atomic receipts, and the final `current.json` pointer swap.
- `bbk.planning-readiness.v1`, `bbk.project-coverage.v1`, and `bbk.plan-event.v1` already distinguish roadmap, current frontier, coverage, and durable semantic events.
- `docs/USAGE.md` makes Beads a coordination projection, not semantic authority, and assigns capability, phase, and WorkUnit projections to Planning and Phase Wayfinders.

The compiler therefore closes explicit references and reports gaps. It does not complete a plan by guessing.

## Goals

1. Compile accepted semantic inputs into a canonical operating-baseline draft, work graph, coverage projection, readiness projection, dispatch plan, and Beads projection plan.
2. Verify exact subject, revision, digest, dependency, authority, ownership, interface, assertion, and acceptance closure before any durable planning mutation.
3. Make every semantic judgment an explicit, attributable input.
4. Hand a complete event set to the existing `bbk plan transact` implementation for one atomic commit.
5. Produce stable, machine-readable gap and invalidation reports.

## Non-goals

- Choosing an intervention, architecture, decomposition, owner, dependency, acceptance criterion, risk disposition, authority grant, assurance method, or Beads semantic status.
- Accepting a decision or authority statement; use [PRD J](J-authority-decision-recorder.md).
- Admitting a Territory for execution; use [PRD I](I-territory-boundary-compiler.md) and then [PRD A](A-execution-admission-compiler.md).
- Replacing `bbk plan transact`, the atomic finalizer, the schema validator, or the Beads adapter.
- Requiring full-project detail when a valid rolling-wave frontier is explicitly selected.

## Callers

- Primary: `bbk_planning_wayfinder` and `bbk_phase_wayfinder`.
- Review-only: `bbk_root_wayfinder`, `bbk_root_orchestrator`, and CI/qualification fixtures.
- Consumers: Territory-boundary compilation, execution-admission compilation, worker-contract generation, assurance planning, completion reporting, and Beads projection.

## Commands and exact examples

Compile without durable mutation:

```powershell
bbk --json plan compile --root . `
  --fit .bbk/decisions/FIT-001.json `
  --architecture .bbk/architecture/ARCH-001.json `
  --decision .bbk/decisions/ADR-001.json `
  --authority .bbk/authority/AUTH-001.json `
  --work-units .bbk/plans/WUS-001.json `
  --assertions .bbk/assurance/ASSERTIONS-001.json `
  --planning-mode FAST_CONTINUATION `
  --architecture-mode ADOPT_AND_GAP `
  --output .bbk/staging/PLAN-COMPILE-001
```

Review the generated Beads intent against the existing adapter's independently compiled plan, apply it only through the existing explicit effect path, then atomically commit the exact compiled event set:

```powershell
bbk --json beads plan --root . --output .bbk/staging/PLAN-COMPILE-001/beads-adapter-plan.json
bbk --json beads plan --root . --apply
bbk --json plan transact --state-root .bbk/planning `
  --event .bbk/staging/PLAN-COMPILE-001/events/0001.json `
  --event .bbk/staging/PLAN-COMPILE-001/events/0002.json `
  --roadmap-out .bbk/planning/roadmap.json `
  --frontier-out .bbk/planning/frontier.json `
  --coverage-out .bbk/planning/coverage.json `
  --authority AUTH-001 --expected-head PLAN-HEAD-0007
```

`plan compile` never implicitly runs `plan transact` or `beads plan --apply`. A caller may provide `--emit-transaction-request` to obtain the exact argv/input manifest for the separately authorized transaction.

## Inputs and schemas

All file inputs are explicit, project-relative where persisted, schema-valid, and content-bound by SHA-256. Proposed compiler request schema: `bbk.plan-compile-request.v1`.

| Input | Cardinality | Required semantics |
|---|---:|---|
| `fit_ref` | 1 | Accepted `SolutionOutcomeFit`; subject and selected direction are explicit |
| `architecture_refs` | 1..n | Accepted architecture/structure and canonical interface decisions |
| `decision_refs` | 0..n | Accepted records from `bbk decision accept`; no merely proposed decision may govern |
| `authority_ref` | 1 | Current, unexpired record from `bbk authority record`, including effects and exclusions |
| `work_unit_set_ref` | 1 | Explicit capability/phase/WorkUnit membership, owners, dependencies, mutation surfaces, and integration obligations |
| `assertion_set_ref` | 1 | Acceptance criteria mapped to assertion IDs, owners, methods, stages, and protected floors |
| `planning_policy` | 1 | `planning_mode`, `architecture_mode`, frontier selection, allowed deferrals, and compilation trigger |
| `prior_head_ref` | 0..1 | Required when updating existing planning state; exact expected head and digest |
| `beads_mapping_ref` | 0..1 | Current `.bbk/mappings/beads.json` identity and projection policy |

The compiler rejects ambient transcript text, directory-wide implicit selection, missing digests, unresolved relative references, remote schema retrieval, duplicate semantic IDs, and conflicting revisions. Input adapters may support legacy accepted artifacts, but must normalize them into a versioned source manifest without changing their meaning.

## Outputs and finalization

A successful compile writes a staging directory containing:

- `compile-result.json` (`bbk.plan-compile-result.v1`) with status, complete input manifest, compiler/tool/schema identity, invalidation keys, and file identities;
- `operating-baseline.json`, with accepted outcome, fit, architecture, decision, authority, assurance, and exclusion references;
- `work-graph.json`, containing capability increments, phases, WorkUnits, dependency edges, integration obligations, interface edges, and execution ordering constraints;
- `roadmap.json`, `frontier.json`, `coverage.json`, and `readiness.json` compatible with existing planning schemas;
- `dispatch-plan.json`, listing executable WorkUnits and exact prerequisites without launching them;
- `beads-plan.json`, containing only the planned project/capability/phase/WorkUnit/decision projection operations;
- `events/*.json`, schema-valid `bbk.plan-event.v1` records for a subsequent transaction; and
- `transaction-request.json`, including expected head, authority reference, ordered event identities, projection outputs, and the exact `bbk plan transact` command.

Each standalone JSON file is finalized through `tools/atomic_finalizer.py`; detached identity sidecars carry raw file identity so content is acyclic. Compile output is staging state, not the authoritative planning head. Only a passing `bbk.plan-transaction-receipt.v1` from `plan transact` makes the successor baseline current.

## Functional requirements

1. The command shall validate every input against a checked-in Draft 2020-12 schema with offline reference resolution.
2. It shall bind every input by schema, ID, revision, path, byte length, and SHA-256.
3. It shall require explicit acceptance/authority records for every governing semantic choice and reject proposal-only or inferred states.
4. It shall produce a stable node ID for each capability, phase, WorkUnit, interface, integration obligation, assertion, and decision.
5. It shall reject duplicate IDs, missing dependency targets, cycles where the declared edge type is acyclic, and dependency edges that cross an undeclared interface.
6. It shall ensure every WorkUnit belongs to an accepted capability/phase and has one accountable owner, one mutation ownership statement, a return route, completion checks, and an authority/effect fence.
7. It shall ensure overlapping writable surfaces have an explicit serialization or integration decision; it shall not choose one.
8. It shall ensure each acceptance criterion maps to at least one assertion and each required assertion maps to a WorkUnit, integration obligation, or boundary-level assurance owner.
9. It shall calculate non-averaging coverage: one uncovered required criterion, protected floor, or blocking dependency makes the relevant readiness state false.
10. It shall derive roadmap/frontier/readiness only from the explicit planning policy and closed graph.
11. In rolling-wave mode it shall require stable interfaces, owners, dependencies, risk class, and refinement triggers for every deferred item.
12. It shall compile dispatch eligibility as facts (`READY`, `BLOCKED`, `DEFERRED`) with reason codes; it shall not dispatch a role or reserve a workspace.
13. It shall compile Beads intent according to the existing ownership split and current mapping, without applying it or reading tracker state as semantic truth.
14. It shall emit ordered plan events accepted by the existing `plan transact` contract and an expected-head precondition.
15. It shall be deterministic: identical canonical inputs and explicit timestamp/transaction ID produce byte-identical semantic outputs.
16. It shall never overwrite a prior compile directory unless an explicit replace option is authorized; authoritative history is never rewritten.
17. It shall expose a verification mode that recomputes input/output identities and closure without writes.
18. It shall keep claims bounded: successful compilation means mechanical planning closure only, not correctness, execution admission, outcome acceptance, or release readiness.

## State and ordering

```text
INPUTS_SELECTED
  -> VALIDATED
  -> REFERENCES_CLOSED
  -> GRAPH_COMPILED
  -> COVERAGE_COMPILED
  -> STAGED
  -> TRANSACTION_REQUESTED
  -> TRANSACTED (only from external plan-transaction receipt)
```

Validation and graph compilation are read-only. Staging uses temp files followed by atomic rename. Beads apply, planning transaction, Territory admission, and worker dispatch are separate serialized effects. A stale expected head rejects the transaction; callers recompile or explicitly prove the staged bundle is unchanged and retry against a successor request.

## Failure, security, and authority

- Fail before writes on malformed schemas, remote references, path escape, symlinks where selection policy forbids them, ambiguous IDs, stale digests, missing acceptance, expired authority, or contradictory effects.
- Emit stable codes such as `PLAN_INPUT_STALE`, `PLAN_SEMANTIC_GAP`, `PLAN_GRAPH_CYCLE`, `PLAN_COVERAGE_GAP`, `PLAN_AUTHORITY_MISSING`, and `PLAN_HEAD_CONFLICT`.
- Treat source contents as data, never executable instructions. Do not execute commands embedded in planning artifacts.
- Redact secrets from diagnostics; authority records may reference secret-bearing systems but must not contain credentials.
- The command has workspace-write authority only for the explicit staging output. It has no authority to accept, transact, apply Beads, dispatch, install, publish, deploy, or release.
- Silence, prior behavior, host permissions, Beads status, or a successful compile never imply consent.

## Compatibility and migration

This is additive. Existing `plan readiness`, `plan migrate-readiness`, and `plan transact` commands remain valid. The compiler emits their current schemas and treats the transaction engine as authoritative. Legacy planning artifacts may be supplied only through an adapter that emits additive migration/anchor events; it must not rewrite them in place. Unknown future fields are preserved only when their owning schema permits them; unknown semantic enums fail closed.

## Observability

JSON output includes compile ID, phase, duration, input/output identities, node/edge counts, uncovered-item counts, readiness classes, event IDs, expected head, Beads operation counts, warnings, and stable failure fingerprint. Logs must distinguish `effects_observed: NONE`, staging writes, and separately observed transaction/apply receipts. No metric may translate compile success into implementation or validation success.

## Test strategy

- Golden fixtures for full-governed and rolling-wave bundles, including byte-identical repeat compilation.
- Schema and property tests for reference closure, topological ordering, coverage monotonicity, and deterministic canonicalization.
- Negative controls: unaccepted fit, proposed decision, expired/wrong-subject authority, duplicate WorkUnit ID, missing dependency, undeclared cross-boundary interface, overlapping mutation ownership, uncovered criterion, protected-floor omission, illegal deferral, stale digest, path escape, remote `$ref`, and Beads mapping drift.
- Fault controls: interruption before staging rename, partial temp directory, disk-full write, finalizer failure, expected-head race, failed projection regeneration, failed current-pointer swap, and Beads unavailable. Each preserves the prior authoritative head and reports exact effects.
- Metamorphic controls: input ordering does not alter output; one semantic input change alters its reference/invalidation closure; narrative-only metadata changes do not invent graph edges.
- Integration test proving emitted events pass existing `plan transact`, and that transaction rollback preserves prior log/projections/head on injected pointer-swap failure.

## Acceptance criteria

1. A complete accepted fixture compiles into all declared outputs and passes every published schema.
2. The same canonical inputs, explicit compile ID, and timestamp produce byte-identical semantic outputs on Windows and Linux.
3. Every governing output field traces to an exact accepted input pointer; the trace report contains no `INFERRED_SEMANTIC_VALUE` entries.
4. Every required acceptance criterion and protected floor has non-averaging assertion coverage, or compilation fails.
5. Every executable WorkUnit has exact authority, ownership, prerequisites, interface obligations, completion checks, and return route.
6. The generated event set commits through unmodified `bbk plan transact` and yields a valid transaction receipt.
7. A stale expected head or injected pointer-swap failure leaves the previous authoritative planning state intact.
8. Beads output is a reviewable plan only and cannot mutate the tracker without the existing explicit `--apply` path.
9. All listed negative and fault controls pass in the standard qualification profile.
10. Documentation states that compile success does not establish semantic correctness, execution admission, validation, acceptance, deployment, or release.

## Dependencies and consumers

Dependencies: [PRD J](J-authority-decision-recorder.md), existing planning schemas/transaction engine, atomic finalizer, schema registry, and Beads adapter. Consumers: [PRD I](I-territory-boundary-compiler.md), [PRD A](A-execution-admission-compiler.md), worker-contract generation, validation compilation, and [PRD F](F-completion-readiness-compiler.md).

## Rollout

1. Ship schemas and verify-only compiler behind `BBK_PLAN_COMPILE=preview`.
2. Add golden/negative fixtures and compare generated projections with manually accepted planning bundles.
3. Enable staging output and transaction-request generation; retain explicit separate `plan transact`.
4. Make compiled bundle identity an optional Territory-boundary input.
5. After two successful real campaigns and no unexplained semantic diffs, recommend it as the default mechanical closure path.

## Risks and open questions

- Existing planning artifacts may not expose uniform architecture or assertion references; adapters must remain mechanical and gap-reporting.
- The canonical work-graph schema and whether roadmap/frontier remain separate projections need a versioned schema decision.
- A large graph may require streaming or bounded-memory closure while preserving deterministic order.
- Decide whether decision projection belongs in the compiler output or is accepted exclusively from the recorder's Beads plan; duplicate projection ownership is prohibited.
- `--emit-transaction-request` is recommended over an all-in-one `--commit` option to keep effect authority visible.

## Estimate

8–12 engineer-days: 2 days schemas/fixtures, 3–4 days graph and coverage compiler, 2 days finalization/transaction integration, 2–3 days negative/fault qualification, and 1 day documentation/migration. Add 3–5 days if heterogeneous legacy planning adapters are required.
