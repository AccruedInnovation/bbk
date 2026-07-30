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
