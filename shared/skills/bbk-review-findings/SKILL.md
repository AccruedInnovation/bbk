    ---
    name: bbk-review-findings
    description: Preserve, correlate, disposition, and close immutable BBK review findings using exact successor evidence rather than rediscovery or voting.
    ---

    # BBK Review Findings

1. Create an immutable finding bound to one run, attempt, subject/candidate digest, assertion, observation, expected condition, evidence, scope, impact, and route.
2. Use fingerprints only for correlation. A collision cannot merge records, and absence from a later run cannot close a finding.
3. Reconciliation may propose `SAME_DEFECT`, `PROBABLE_DUPLICATE`, `SHARED_ROOT_CAUSE`, `OVERLAPPING_IMPACT`, `CONTRADICTORY_ASSESSMENT`, or `UNRELATED`; preserve every original.
4. Close only through a successor `FindingDisposition`: `FIXED`, `REBUTTED`, `ACCEPTED_RISK`, `FALSE_POSITIVE`, `DUPLICATE_OF`, `SUPERSEDED`, `DEFERRED`, `OUT_OF_SCOPE`, or `REMAINS_OPEN`.
5. Every closing disposition names the exact finding, successor subject or changed context, closure evidence, reviewing attempt or accountable authority, residual impact, and reopening trigger.
6. Workers do not close their own material findings. Reviewers do not waive their own failures.
7. A contradicted or protected-floor finding escalates; it is not hidden by a lower aggregate count.
8. Preserve immutable history and derive current projection state from finding plus dispositions.

## Profile binding

Preserve the selected profile identity, profile/toolchain version, applicable rule or gate, and evidence adapter in any profile-derived finding or disposition. Do not generalize a profile-specific defect into a language-independent BBK defect without separate evidence.
