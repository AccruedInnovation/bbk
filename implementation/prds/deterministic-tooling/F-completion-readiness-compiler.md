# PRD F — Completion-readiness compiler

**Status:** Proposed

**Owner kind:** deterministic lifecycle-report tooling maintainer; accountable completion disposition remains external
**Priority:** Required

## Problem and repository evidence

BBK deliberately separates operational completion, semantic readiness, accountable acceptance, and release. Existing role-return contracts, review aggregates, artifact verification, finding disposition, cleanup states, authority references, and protected-floor policies carry the facts, but there is no one deterministic reconciliation step proving that the current lifecycle evidence closes over the same candidate. As a result, a controller must manually compare [PRD B](B-worker-result-assembler.md), [PRD C](C-gate-receipt-aggregation.md), [PRD D](D-canonical-candidate-freezer.md), and [PRD E](E-candidate-bound-validation-compiler.md) outputs plus findings and residual effects.

This PRD compiles those facts into a non-authoritative completion-readiness report. It does not declare project completion, deployability, release readiness, or authorization. [PRD G](G-lifecycle-qualification-fixture.md) qualifies both the positive reconciliation and required fail-closed cases.

## Goals

- Reconcile B/C/D/E identities, current validation outcomes, findings, cleanup/residuals, authority scope, and protected bytes.
- Produce one deterministic, candidate-bound readiness report with explicit blockers and claims not established.
- Fail closed on missing, inconclusive, stale, wrong-candidate, mutated, unauthorized, or unclean evidence.
- Give the accountable parent the smallest exact next action without taking that action.

## Non-goals

- Accepting the candidate, closing findings, granting authority, authorizing effects, deployment, publication, or release.
- Inferring whole-project completion from a candidate-level pass.
- Executing gates, validation, cleanup, repair, deployment, or release commands.
- Replacing role returns, gate aggregates, ReviewAggregate, finding records, or artifact receipts.

## Callers

- `bbk_territory_orchestrator` preparing a boundary report.
- `bbk_root_orchestrator` reconciling candidate evidence before controller disposition.
- Recovery and qualification tooling requiring an exact machine-readable blocker set.

## Command surface and exact examples

```powershell
python tools/bbk.py completion report --worker-results .bbk/results/index.json --gate-aggregate .bbk/gates/aggregate.json --candidate-ref .bbk/candidates/CAND-17-r1/candidate-freeze-receipt.json --review-manifest .bbk/validation/review-manifest.json --review-aggregate .bbk/validation/review-aggregate.json --findings .bbk/findings/index.json --cleanup .bbk/effects/cleanup.json --authority .bbk/authority/effective.json --protected-bytes .bbk/candidates/CAND-17-r1/protected-bytes.json --output .bbk/completion/CAND-17-r1-readiness.json
python tools/bbk.py completion verify --report .bbk/completion/CAND-17-r1-readiness.json
```

`report` reads and verifies existing carriers. It invokes no product check and mutates only its staging/output path. `verify` recomputes input identities and report currentness read-only.

## Inputs and schemas

- Complete current worker-result set/index from [PRD B](B-worker-result-assembler.md), including execution/admission bindings and actual effects.
- Current non-averaging `bbk.gate-aggregate.v1` from [PRD C](C-gate-receipt-aggregation.md).
- Verified, non-invalidated D CandidateRef, candidate package, and freeze receipt.
- E-produced existing ReviewManifest plus current ReviewContext/ReviewRun/`bbk.review-aggregate.v1` outputs.
- Immutable `bbk.review-finding.v1` records and current disposition records; prior findings remain visible according to the manifest policy.
- Cleanup/residual inventory using existing allowed role-return cleanup states and exact owners/evidence.
- Explicit effective authority references for actions already taken and for the parent’s next disposition.
- Protected-byte inventory derived from the frozen candidate and accepted protected floors, including path/role/bytes/SHA-256 and exclusions.

The new report schema, `bbk.completion-readiness-report.v1`, is a reconciliation result only. It references canonical inputs by digest and does not copy or supersede their semantics.

## Outputs and finalization

An atomically finalized report contains report ID, exact CandidateRef, B/C/D/E input identities, validation aggregate, assertion closure, finding closure, cleanup/residual state, authority coverage, protected-byte verification, staleness/invalidation keys, blocker/advisory lists, readiness disposition, smallest valid next action, and a mandatory authority disclaimer.

Allowed disposition values are `READY_FOR_PARENT_DISPOSITION`, `BLOCKED_EVIDENCE`, `BLOCKED_FINDINGS`, `BLOCKED_CLEANUP`, `BLOCKED_AUTHORITY`, `BLOCKED_CANDIDATE_INTEGRITY`, `INCONCLUSIVE`, `STALE`, and `ERROR`. “Ready” means only that this evidence bundle is internally current and closed enough for its named parent disposition.

A detached atomic-finalization receipt binds the report bytes. The report does not inventory its own digest.

## Functional requirements

1. Verify every input schema, detached identity, provenance chain, and currentness before reconciliation.
2. Require every B worker result expected by the admitted work graph and reject duplicates, missing terminal results, wrong execution identities, or unaccounted effects.
3. Require C’s configured passing non-averaging result and exact binding to the execution lineage used by D.
4. Verify D’s CandidateRef, package, freeze receipt, invalidation state, and current protected bytes.
5. Require E’s ReviewManifest subject to equal D’s CandidateRef and require current context/run/aggregate lineage for that exact manifest.
6. Treat validation `FAIL`, `NEEDS_REVISION`, blocked, error, cancelled, stale, inconclusive, required-not-run, or missing evidence as non-ready; advisory pass remains visible and follows the accepted aggregation policy.
7. Reconcile every open finding with its immutable lineage and current allowed disposition. A blocker cannot be erased by omission, narrative rebuttal, or a disposition from another candidate.
8. Require cleanup evidence for all B and validation effects. `CLEAN`, `ROLLED_BACK`, and `NOT_APPLICABLE` are ready only when supported by evidence; quarantined, residual, blocked, unknown, or missing cleanup is non-ready unless the accepted contract explicitly assigns a later parent action, which still cannot yield clean completion.
9. Compare actual effects to supplied authority scope. Filesystem access, role identity, or successful execution is not authority evidence.
10. Recompute every protected-byte digest and detect added, removed, renamed, or changed entries. No finding disposition may waive a protected-byte mismatch.
11. Derive disposition by fixed precedence: integrity/identity, staleness, authority, evidence/validation, findings, cleanup, then ready/advisory. Passing lower-priority areas never averages away a blocker.
12. Preserve distinct candidate defects, infrastructure/environment blockers, authority gaps, cleanup residuals, and report errors.
13. Emit exact blockers, implicated input refs, invalidation keys, and smallest valid next action without automatically performing repair, revalidation, cleanup, or escalation.
14. Re-running unchanged inputs must be byte-stable apart from explicitly excluded detached generation metadata; changed input must make the prior report stale.
15. Include `claims_not_established` naming at least semantic acceptance, whole-project completion, deployment readiness, publication authorization, and release authority.

## State and ordering

`REQUESTED -> INPUTS_VERIFIED -> LINEAGE_RECONCILED -> PROTECTED_BYTES_VERIFIED -> FINDINGS_RECONCILED -> EFFECTS_AND_AUTHORITY_RECONCILED -> DISPOSITION_DERIVED -> FINALIZED`.

Verification order is fail-closed but diagnostics should collect independent safe failures where possible. A finalized report becomes `STALE` on any input, candidate, finding disposition, cleanup, authority, protected-byte, profile/environment, or validation change. Successor reports preserve predecessor identity.

## Failure semantics

Malformed or tampered carriers, missing predecessors, cycles, digest mismatch, post-freeze mutation, wrong candidate, incomplete validation, unresolved blocking finding, cleanup ambiguity, authority gap, protected-byte mismatch, or finalization collision yields a typed blocker/non-zero command result according to CLI convention. A report may still be finalized for diagnostic blocked dispositions if all referenced evidence identities are trustworthy; corrupt or ambiguous identity prevents authoritative reconciliation and must not produce `READY_FOR_PARENT_DISPOSITION`.

## Security and authority

The compiler is read-only outside its output. It resolves paths beneath admitted roots, rejects link/path escapes, performs no network access, executes no candidate content, and redacts secrets from evidence excerpts. Authority inputs are treated as scoped claims to validate against recorded effects, never as power granted by the command. The report cannot direct or execute deployment/release and must reject wording that implies it.

## Compatibility and migration

The report is additive. Existing B–E, review, artifact, finding, and cleanup schemas remain canonical. Historical evidence can produce a blocked/legacy report only when its identities are verifiable; it cannot be silently upgraded to ready. Readers must ignore unknown future advisory fields but fail on unknown disposition, identity, or blocker semantics. No historical carrier is rewritten.

## Observability

Structured output includes counts and digests for every input family, lineage edges, assertion status counts, open/dispositioned findings, effects and cleanup states, authority gaps, protected-byte count/bytes, disposition, blockers, advisories, invalidation keys, compiler/tool identity, duration, and stable failure fingerprints. Evidence content and secrets stay in referenced carriers.

## Test strategy

Unit tests cover precedence, non-averaging behavior, finding lineage, cleanup classification, authority containment, protected-byte comparison, and staleness. Integration tests assemble real B/C/D/E fixture outputs and validate the final schema/receipt. Negative/fault controls cover missing worker result, stale C aggregate, wrong D CandidateRef, post-freeze mutation, missing/inconclusive/failed validation, finding omitted or dispositioned for another candidate, cleanup residual, unauthorized effect, protected-byte change/removal/addition, self/cross-reference cycle, outside-root path, remote reference with no network, report tamper, and fault between staging and atomic publication. A specific regression test presents failed validation as completion and must receive a non-ready disposition.

## Acceptance criteria

1. A fully current A–E fixture with closed findings, reconciled cleanup, covered authority, and unchanged protected bytes yields `READY_FOR_PARENT_DISPOSITION`.
2. Every report binds one and only one exact D CandidateRef across all inputs.
3. Any missing, stale, wrong-candidate, inconclusive, failed, or required-not-run gate/validation input prevents ready disposition.
4. Open blocking findings, unclean residuals, authority gaps, or protected-byte mismatch prevent ready disposition independently.
5. Fixed precedence preserves distinct blocker classes and never averages them into pass.
6. `completion verify` detects any changed input or report byte and returns stale/invalid.
7. The report’s next action is non-effecting and does not grant authority to perform it.
8. No output claims whole-project completion, deployment readiness, publication, acceptance, or release authority.

## Dependencies and consumers

Dependencies: [PRD B](B-worker-result-assembler.md), [PRD C](C-gate-receipt-aggregation.md), [PRD D](D-canonical-candidate-freezer.md), [PRD E](E-candidate-bound-validation-compiler.md), existing artifact/review/finding/role-return schemas, and `tools/atomic_finalizer.py`.

Consumers: territory/root orchestrators, controller-facing status, recovery/successor planning, and [PRD G](G-lifecycle-qualification-fixture.md). Deployment and release systems are explicitly not direct authority consumers.

## Rollout

Add schema/validator and blocked-report generation first. Run shadow reconciliation on current qualification fixtures and compare human/manual dispositions. Make CandidateRef/protected-byte/current-validation requirements mandatory next, then use the report as the sole deterministic evidence summary for parent disposition while retaining the original carriers.

## Risks and open questions

- “Expected worker result set” must come from an immutable admitted graph/boundary, not directory discovery.
- Authority schemas may differ across execution modes; reconciliation needs a narrow common scope view without weakening mode-specific rules.
- Protected-byte selection must be fixed before validation and must include generated/config/tool dependencies where a byte change alters behavior.
- `READY_FOR_PARENT_DISPOSITION` naming must remain clearly non-authoritative in UIs and logs.

## Estimate

8–12 engineer-days: schema/reconciler 3–4, identity/currentness integration 2–3, findings/effects/authority logic 1–2, fault and end-to-end tests 2–3.
