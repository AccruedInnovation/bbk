---
name: bbk-review-plan
description: Compile the smallest sufficient ReviewManifest from an exact AssuranceContract, subject, risk, profiles, environment capabilities, and review purpose.
---

# BBK Review Plan

The `AssuranceContract` says what must be proven. The `ReviewManifest` says how this review will cover it.

1. Bind exact subject identity/digest and exact AssuranceContract identity/digest.
2. Choose `none`, `inline`, or `manifest` applicability proportionately.
3. Assign each required assertion one primary evaluation owner, method, evidence requirement, logical lens, context selector, and blocking consequence.
4. Reject overlapping lens assignments unless the second method adds a declared complementary assurance property.
5. Select deterministic evidence before agent or human interpretation where it can prove the same assertion.
6. Specify independence dimensions separately: author separation, role, invocation, context assembly, prior-finding visibility, model/provider diversity, deterministic evidence, organizational independence, and mutation prohibition.
7. Set prior-finding visibility to `HIDDEN`, `TARGETED`, `FULL`, or `NOT_APPLICABLE` according to blind reassessment, closure, synthesis, or deterministic purpose.
7a. Record outcome-bearing evidence exposure and classify each attempt as exploratory, alternative, replication, robustness, targeted closure, adjudication, or confirmatory. Criteria chosen after evidence exposure cannot be independent confirmation against that evidence.
8. Include context completeness, explicit context edges, logical-role-to-invocation mapping, sharding, cross-shard, evidence, repair, retry, escalation, staleness, and aggregation policy.
9. Use the smallest sufficient lens set. File count, model availability, or a broad survey request does not activate every specialist.
10. Never weaken the AssuranceContract or infer approval, acceptance, compliance, release, or product authority.

## Profile-aware review planning

Use `bbk-installed-profiles` to discover managed profile lenses, context selectors, and evidence adapters. Select them only for assertions they uniquely own, and record unavailable mandatory profile capability as a blocker rather than silently replacing it with a generic model review.

## Product-first proportional workflow

<!-- BBK prompt module bbk-prompt-assurance-modes: expanded from canonical source -->

### Proportional assurance modes

Select INLINE, FOCUSED, or FULL assurance from the exact subject and material risk without creating a global lifecycle gate.

- `ASSURANCE_MODE.INLINE` — Use INLINE by default for routine, reversible, profile-covered work. Worker self-checks and applicable deterministic gates are sufficient; do not commission an independent Reviewer or manually authored review manifest solely because work occurred.
- `ASSURANCE_MODE.FOCUSED` — Use FOCUSED for one exact material risk, interface, finding, or candidate claim. Record the exact subject and risk rationale, generate the bounded context, commission only the necessary independent focus, and recheck the affected scope after repair.
- `ASSURANCE_MODE.FULL` — Use FULL for safety or security exposure, irreversible migration, consequential shared interfaces, contractual or compliance obligations, novel high-risk mechanisms, or explicit user request. Broader assertion design and candidate-bound evidence are warranted only to the extent required by those risks.
- `ASSURANCE_MODE.RECORD` — Represent the selection with `bbk.assurance-mode.v1`: mode, exact subject reference, risk basis, rationale, review focus, recheck scope, and whether independent review is required. FOCUSED and FULL require an explicit material-risk rationale; INLINE must state its routine basis.
- `ASSURANCE_MODE.NO_LIFECYCLE_ENGINE` — The assurance-mode record guides proportional work and context generation. It does not itself accept a candidate, authorize effects, invalidate prior work automatically, or introduce a global deterministic lifecycle state machine.

<!-- End BBK prompt module bbk-prompt-assurance-modes -->

<!-- BBK prompt module bbk-prompt-candidate-focused-review: expanded from canonical source -->

### Candidate-focused review and delta recheck

Review the exact integrated candidate or material boundary and return bounded findings instead of rewriting the plan.

- `CANDIDATE_REVIEW.EXACT_SUBJECT` — Independent review normally targets an exact sealed integrated candidate or one exact material risk or interface boundary. Do not default to reviewing an abstract plan or every intermediate artifact when those are not the assurance subject.
- `CANDIDATE_REVIEW.DELTA_OUTPUT` — Return findings, evidence gaps, concrete deltas, affected scope, reopening triggers, and the smallest valid next action. Do not rewrite the implementation plan or restate unaffected context as the review product.
- `CANDIDATE_REVIEW.FINDING_SCOPED_RECHECK` — A focused repair recheck consumes the finding, successor candidate, affected scope, relevant evidence, and reopening triggers. Reopen broader review only when the repair materially changes semantics, interfaces, authority, protected floors, or evidence meaning.
- `CANDIDATE_REVIEW.STOP_RULE` — Stop when the exact review focus is resolved and its required evidence is adequate. Do not expand a bounded review into a general audit, duplicate prior assurance, or continue after the named risk has been retired.
- `CANDIDATE_REVIEW.INLINE_BOUNDARY` — INLINE work does not commission an independent Reviewer. Apply normal worker self-checks and deterministic gates unless a named material risk changes the assurance mode.

<!-- End BBK prompt module bbk-prompt-candidate-focused-review -->
