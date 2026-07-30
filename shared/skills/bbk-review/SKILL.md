---
name: bbk-review
description: Independently review a BBK plan, work unit, exact candidate, evidence package, recovery state, or outcome claim. Use for assertion-scoped readiness or acceptance review without mutating the subject or repeating deterministic checks unnecessarily.
---

# BBK Review

Review the named subject and assertions; do not mutate the subject.

0. When the charter concerns a solution or execution plan, check that the requested intervention, desired outcome, causal hypothesis, fit disposition, implementation structure, slices, work units, profiles, and success evidence form one traceable chain. Review only the portions named by the charter.

1. Bind the exact subject, candidate or revision identity, review charter, assertions, criteria, environment, evidence, and independence reason.
2. Confirm deterministic prerequisite receipts apply to the same subject. If the prerequisite is absent or stale, return `BLOCKED` rather than manually re-performing a whole mechanical gate.
3. Inspect only the scope needed for the assigned assertions plus any direct impact closure required to evaluate them.
4. Check that outcome, boundary, ownership, interfaces, failure/recovery semantics, work-unit contracts, and verification methods are mutually coherent where relevant.
5. Verify that decomposition reduced visible complexity and gave every mutation one owner.
6. Recompute or inspect candidate identity when possible. Distinguish exact immutable inputs from nondeterministic outputs that need semantic receipts.
7. Require actual-consumer evidence only for claims about that consumer or boundary.
8. Classify each finding as candidate defect, process defect, contract/design defect, evidence defect, or authority/scope question.
9. State the smallest valid disposition and owner. Do not turn a newly discovered normative requirement into a routine patch without impact review.
10. Preserve disagreement and earlier findings. Never waive a required assertion or silently review a different candidate.

Return findings ordered by consequence, then one of `PASS`, `FAIL`, `BLOCKED`, or `INCONCLUSIVE`. Include coverage gaps, residual uncertainty, evidence reused, evidence rerun, and whether the named next action may proceed.

## Review-assurance records

For a separately persisted review, require an AssuranceContract, ReviewManifest, ReviewContextManifest, ReviewRun, attempts, evidence receipts, immutable findings, and explicit dispositions. Use targeted closure and blind reassessment according to the manifest. Non-rediscovery never closes a prior finding.

## Language and domain profiles

When the review charter includes language- or toolchain-specific assertions, confirm the exact locked profile, load its router skill, and use only the applicable profile review lenses, context selectors, and evidence adapters. Profile output informs the declared assertion; it does not create approval or a pass by itself.

## Language-profile review

Use `bbk-installed-profiles` and the effective profile lock to select only profile-owned lenses, context selectors, gates, or evidence adapters that prove named assertions. Do not treat profile installation as proof of applicability, tool availability, independent execution, or candidate acceptance.
