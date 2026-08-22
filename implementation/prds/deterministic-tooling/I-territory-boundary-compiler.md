# PRD I — Territory-boundary compiler

**Status:** Proposed — later hardening

**Owner kind:** Root Orchestrator lifecycle tool; Territory Orchestrator is an admitted-boundary consumer, never its compiler
**Priority:** Later hardening; required before deterministic multi-territory execution admission

## Problem and evidence

`spec/schemas/bbk-territory-execution-boundary-v1.schema.json` is a deliberate 613-line contract. It binds subject and baseline identity, exact graph membership, mutation ownership, interfaces, effects, budgets, assurance, local discovery, recovery, invalidation, completion, and successor behavior. `docs/EXECUTION-DESIGN.md` and canonical role contracts make Root Orchestrator the compiler/admitter and forbid Territory Orchestrator from rewriting an admitted boundary.

Hand-authoring this instance requires copying a large accepted graph subtree into a structurally strict record. Mechanical omissions, inconsistent references, and accidental in-place changes are likely, while the tool must not decide what a territory contains or what authority it receives. A compiler can safely derive the schema instance only from an explicitly selected accepted subtree and explicit governing records.

## Goals

1. Deterministically compile a complete `bbk.territory-execution-boundary.v1` draft from accepted graph, authority, ownership, interface, assertion, invalidation, recovery, and completion inputs.
2. Separate compilation, admission, verification, and succession into explicit lifecycle operations.
3. Bind admitted boundaries immutably and issue exact finalized/admitted receipts.
4. Detect overlap, gaps, stale dependencies, and forbidden authority broadening before execution admission.
5. Produce a boundary directly consumable by [PRD A](A-execution-admission-compiler.md).

## Non-goals

- Selecting territory membership, assigning ownership, defining interfaces, granting effects, setting assurance floors, or declaring completion.
- Creating or accepting authority/decisions; use [PRD J](J-authority-decision-recorder.md).
- Compiling the root plan; use [PRD H](H-planning-bundle-compiler.md).
- Dispatching a Territory Orchestrator, issuing local-discovery permits, freezing candidates, validating work, or accepting completion.
- Compressing, weakening, or replacing the existing 613-line schema.

## Callers

- `bbk_root_orchestrator` is the only role authorized to compile, admit, or issue a successor boundary.
- `bbk_territory_orchestrator`, Worker Orchestrator, Validator Orchestrator, recovery tooling, and completion reporting call `verify` read-only.
- CI and qualification fixtures exercise every lifecycle and negative control.

## Commands and exact examples

```powershell
bbk --json boundary compile --root . `
  --boundary-id TEB-API-001 --revision 1 `
  --graph .bbk/planning/work-graph.json --subtree TERRITORY-API `
  --authority .bbk/authority/AUTH-API-001.json `
  --ownership .bbk/planning/ownership-API.json `
  --interfaces .bbk/architecture/interfaces-API.json `
  --assertions .bbk/assurance/ASSERTIONS-API.json `
  --invalidation .bbk/planning/invalidation-API.json `
  --completion .bbk/planning/completion-API.json `
  --output .bbk/boundaries/drafts/TEB-API-001.json

bbk --json boundary admit --root . `
  --draft .bbk/boundaries/drafts/TEB-API-001.json `
  --root-campaign .bbk/execution/CAMPAIGN-001.json `
  --root-orchestrator .bbk/invocations/ROOT-001.json `
  --territory-orchestrator .bbk/invocations/TERRITORY-API-001.json `
  --authority .bbk/authority/AUTH-ROOT-001.json

bbk --json boundary verify --root . `
  --boundary .bbk/boundaries/admitted/TEB-API-001/r1/boundary.json `
  --against-current

bbk --json boundary successor --root . `
  --predecessor .bbk/boundaries/admitted/TEB-API-001/r1/boundary.json `
  --revision 2 --reason MEMBERSHIP_CHANGED `
  --graph .bbk/planning/work-graph-r2.json --subtree TERRITORY-API `
  --authority .bbk/authority/AUTH-API-002.json `
  --output .bbk/boundaries/drafts/TEB-API-002.json
```

## Inputs and schemas

Proposed request schemas are `bbk.boundary-compile-request.v1`, `bbk.boundary-admission-request.v1`, and `bbk.boundary-successor-request.v1`. The compiled subject remains the existing `bbk.territory-execution-boundary.v1` without a parallel representation.

Required input groups:

| Group | Explicit content |
|---|---|
| Identity | boundary ID/revision, exact subject, operating/execution baseline, root campaign, predecessor/parent boundary |
| Membership | selected accepted graph subtree and exact capability, phase, WorkUnit, dependency, integration-obligation refs |
| Ownership | integration owner, mutation surface owner, workspace, serialization policy, shared resources |
| Interfaces | direction, owner, consumers, required state, and accepted interface ref |
| Authority/effects | authority holder, allowed/prohibited effect classes, safeguards, revocation and expiry |
| Resources | planned effort units, concurrency limit, allocations, stopping conditions |
| Assurance | contracts, protected floors, completion assertions, worker gates, independent evaluations, candidate lineage policy |
| Recovery/invalidation | checkpoint requirements, invalidation triggers, successor triggers, recovery owner |
| Completion | required WorkUnit states, integration/assurance obligations, cleanup, and claims not established |

Each semantic value must already exist in an accepted source. CLI convenience flags select those values; they never synthesize them. `compile` rejects a subtree name that is not declared in the graph or a field supplied only by narrative prose.

## Outputs and finalization

- `boundary compile` writes a finalized `DRAFT` boundary and `bbk.boundary-compile-receipt.v1`, binding all source manifests, mappings, gaps, schema identity, and detached boundary identity.
- `boundary admit` writes an immutable `ADMITTED` boundary under `.bbk/boundaries/admitted/<boundary-id>/r<revision>/`, an admission receipt (`bbk.boundary-admission-receipt.v1`), and an atomic current pointer. It never mutates the draft in place.
- `boundary verify` returns `bbk.boundary-verification.v1` with byte/schema/reference/currentness/immutability results and no writes by default.
- `boundary successor` creates a new `DRAFT` with predecessor identity, explicit reason, changed-field manifest, and retained immutable lineage. Admission remains a separate command.

Standalone JSON uses the atomic finalizer and detached identities. Admission uses lock, stage, verify, durable rename, receipt, and current-pointer-last ordering. A receipt proves mechanical compilation/admission only.

## Functional requirements

1. `compile` shall validate the complete 613-line v1 schema, not a permissive subset.
2. It shall select membership only from the exact accepted graph subtree named by the caller.
3. It shall bind each reference by ID/revision/digest and reject stale, missing, duplicated, or wrong-subject references.
4. It shall require at least one WorkUnit and exactly one integration owner.
5. It shall verify that each member WorkUnit is reachable from the selected subtree and no excluded WorkUnit is imported through an untyped edge.
6. It shall reject writable surface overlap without an explicit accepted serialization policy and owner.
7. It shall verify every cross-territory dependency has a declared interface, direction, owner, consumer, and required state.
8. It shall intersect—not union—the selected territory effects with current authority; any requested broadening fails with an authority gap.
9. It shall require explicit prohibited effects, safeguards, revocation conditions, expiry, budgets, and stopping conditions.
10. It shall carry all applicable assurance contracts, protected floors, completion assertions, worker gates, independent evaluation refs, and lineage rules.
11. It shall enforce zero local discovery without the fixed policy and Territory-Orchestrator-issued active envelope/permit lifecycle.
12. It shall include explicit invalidation and successor triggers covering baseline, membership, ownership, interface, authority/effect, assurance, recovery, and completion changes.
13. `admit` shall require caller role `bbk_root_orchestrator`, a current authority record, root campaign identity, and exact Territory Orchestrator invocation identity.
14. `admit` shall reject `ADMITTED` ID/revision reuse, predecessor forks without explicit branch disposition, and any existing different bytes at the destination.
15. After admission, all schema-declared immutable fields shall be byte/content immutable; lifecycle observations live in receipts/events, not rewritten semantic fields.
16. `verify --against-current` shall re-resolve declared invalidation keys and report `CURRENT`, `STALE`, `INVALIDATED`, or `UNKNOWN`; unknown is non-admissible.
17. `successor` shall verify the predecessor first, increment revision, bind the exact predecessor digest, preserve unchanged fields, and require explicit accepted sources for changed fields.
18. It shall prevent an active predecessor and successor from both being represented as current; pointer swap occurs only on successor admission.
19. It shall emit a handoff reference suitable for execution-admission compilation but shall not dispatch or admit execution itself.
20. It shall never claim Territory completion, validation pass, outcome acceptance, risk acceptance, deployment, or release.

## State and ordering

```text
DRAFT -> PROPOSED -> ADMITTED -> ACTIVE -> SUSPENDED
                                  |          |
                                  v          v
                       COMPLETION_REPORTED -> COMPLETED
                                  |
                                  +-> CANCELLED / INVALIDATED / SUPERSEDED
```

This tool authoritatively performs only draft creation, admission, verification observations, and successor creation/admission. Operational lifecycle transitions require separately authorized event/receipt inputs. Semantic changes after `ADMITTED` always create a successor. Compile may be parallel across non-overlapping territory IDs; admission/current-pointer updates serialize per boundary lineage and root campaign.

## Failure, security, and authority

- Reject path traversal, output escape, unsafe symlinks, remote schemas, schema ambiguity, source mutation during compile, and destination collisions before admission effects.
- Stable failures include `BOUNDARY_MEMBERSHIP_GAP`, `BOUNDARY_OWNERSHIP_CONFLICT`, `BOUNDARY_INTERFACE_GAP`, `BOUNDARY_AUTHORITY_BROADENING`, `BOUNDARY_ASSERTION_GAP`, `BOUNDARY_STALE_SOURCE`, `BOUNDARY_IMMUTABLE_CHANGE`, and `BOUNDARY_LINEAGE_CONFLICT`.
- Source data is untrusted data. No embedded command is executed and no credential is persisted.
- Root Orchestrator identity is necessary but not sufficient: the exact authority record must authorize the admission write. Host filesystem access is not authority.
- A valid boundary confines later work but grants no new authority beyond the referenced record.
- Unknown currentness, ambiguous external effect, or contradictory authority fails closed and leaves the prior current pointer unchanged.

## Compatibility and migration

The compiler targets the existing v1 schema and template. Existing manually authored valid boundaries remain readable/verifiable. They may be imported with a source-manifest receipt; they are never rewritten merely to adopt this tool. Schema evolution uses explicit readers and successor boundaries. Unknown lifecycle enums or immutable fields block admission rather than being dropped. Existing role-return contracts continue to reference `bbk.territory-execution-boundary.v1` unchanged.

## Observability

Receipts report boundary ID/revision/digest, predecessor/parent, source identities, member/edge/interface/owner/assertion counts, authority/effect counts, gap counts, lifecycle operation, lock/pointer outcome, effects observed, duration, tool/schema identity, and stable failure fingerprint. Audit output must show field-level provenance for every compiled semantic field and changed-field provenance for successors.

## Test strategy

- Golden compile/admit/verify/successor fixtures against the checked-in template and schema.
- Property tests for subtree closure, reference stability, authority subset behavior, ownership non-overlap, and deterministic ordering.
- Negative controls: empty membership; outside-subtree WorkUnit; duplicate ID; missing owner; two integration owners; writable overlap; undeclared cross-territory interface; direction mismatch; authority broadening; omitted prohibited effects; expired authority; assertion/protected-floor omission; invalid local-discovery allowance; missing successor trigger; wrong campaign; non-Root admitter; revision reuse; stale predecessor; in-place immutable edit; path escape; remote schema.
- Fault controls: interruption after stage, receipt-write failure, durable rename failure, lock contention, stale-lock recovery, disk full, pointer-swap failure, source mutation during hashing, and successor admission race. The prior admitted boundary/current pointer must remain intact.
- Cross-PRD integration: consume [PRD H](H-planning-bundle-compiler.md) output, [PRD J](J-authority-decision-recorder.md) authority, and prove [PRD A](A-execution-admission-compiler.md) accepts the admitted receipt.

## Acceptance criteria

1. A complete accepted subtree compiles into a schema-valid boundary with field-level source provenance.
2. The compiler reproduces all required fields in the existing 613-line schema without manual JSON completion.
3. No semantic field is populated without an exact accepted source pointer.
4. Overlapping ownership, undeclared interfaces, authority broadening, and assertion gaps fail before admission writes.
5. Admission produces immutable boundary bytes, detached identity, receipt, and current pointer using pointer-last atomic ordering.
6. Verification detects one-byte tampering, stale sources, wrong subject/campaign, and superseded currentness.
7. Every semantic change after admission requires a successor with exact predecessor lineage and changed-field manifest.
8. Injected admission failures preserve the last admitted boundary and current pointer.
9. The admitted receipt is consumable by PRD A without reinterpretation.
10. Documentation and output disclaim completion, validation, acceptance, deployment, and release authority.

## Dependencies and consumers

Dependencies: [PRD H](H-planning-bundle-compiler.md) or an equivalent accepted graph, [PRD J](J-authority-decision-recorder.md), existing boundary schema/template, atomic finalizer, and planning/currentness identities. Consumers: [PRD A](A-execution-admission-compiler.md), Root/Territory/Worker/Validator Orchestrators, recovery, candidate validation, and [PRD F](F-completion-readiness-compiler.md).

## Rollout

1. Ship verify-only support for existing boundaries.
2. Add compile preview and provenance diff against manually authored fixtures.
3. Enable draft finalization, then admission behind `BBK_BOUNDARY_ADMIT=preview`.
4. Integrate admitted receipts with execution admission and run the lifecycle qualification fixture.
5. Make the compiler the default for new multi-territory campaigns; preserve manual v1 read compatibility.

## Risks and open questions

- The schema permits some extensible records; provenance must still prevent semantic smuggling through `additionalProperties` subobjects.
- Decide whether operational lifecycle events need a separate boundary-event schema rather than reusing plan events.
- Cross-boundary overlap detection requires all sibling boundary manifests or an authoritative root ownership index.
- Successor branching policy needs an explicit controller decision when two legitimate alternatives share one predecessor.
- Large graph subtree resolution must remain bounded and deterministic.

## Estimate

7–10 engineer-days: 2 days request/receipt schemas and provenance model, 2–3 days compile/verify, 2 days atomic admission/successor lifecycle, 1–2 days fault/negative qualification, and 1 day integration/documentation.
