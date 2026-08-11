---
name: bbk-review-plan
description: Compile the smallest sufficient ReviewManifest from an exact AssuranceContract, subject, risk, profiles, environment capabilities, and review purpose.
requires_prompt_modules: ["bbk-prompt-assurance-modes"]
standalone_prompt_modules: ["bbk-prompt-candidate-focused-review"]
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

> Apply the already embedded `bbk-prompt-assurance-modes` module here.

<!-- BBK prompt module bbk-prompt-candidate-focused-review: expanded from canonical source -->

### Candidate-focused qualitative review and scoped recheck

Review a named qualitative risk over an exact candidate without duplicating deterministic mechanics.

- `CANDIDATE_REVIEW.NAMED_RISK` — Dispatch Reviewer only for a named qualitative or cross-cutting product risk deterministic checks cannot establish; otherwise return `NO_MATERIAL_ASSURANCE_WORK`.
- `CANDIDATE_REVIEW.EXACT_SUBJECT` — Review the exact frozen integrated candidate or one exact material interface boundary; use current identity, package, environment, test, schema, and evidence receipts.
- `CANDIDATE_REVIEW.NO_DUPLICATE_MECHANICS` — Do not rerun tests, schema/package checks, hashing, profile discovery, or environment qualification merely to appear independent. Interpret current evidence independently; run another method only when the assurance contract names its controlled risk.
- `CANDIDATE_REVIEW.DELTA_OUTPUT` — Return findings, evidence gaps, concrete deltas, affected scope, reopening triggers, and the smallest valid next action rather than rewriting the plan or restating unaffected context.
- `CANDIDATE_REVIEW.SCOPED_RECHECK` — After repair, revalidate failed assertions, direct impact closure, and explicitly invalidated regression gates only. Broaden review only after changed semantics, interfaces, authority, protected floors, ownership, or evidence meaning.

<!-- End BBK prompt module bbk-prompt-candidate-focused-review -->
