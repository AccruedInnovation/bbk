---
name: bbk-review-intent
description: Check intent and outcome conformance across requested intervention, SolutionOutcomeFit, plans, structure, slices, work, candidate, evidence, and promised capability.
---

# BBK Intent Conformance

Review the chain rather than only the leaf artifact:

```text
requested intervention ↔ SolutionOutcomeFit ↔ operational outcome
parent plan ↔ child plan
architecture/interface ↔ ImplementationStructureContract
ExecutionSlice ↔ WorkUnits
AssuranceContract ↔ candidate/evidence
package/release subject ↔ promised capability
```

Detect dropped obligations, unauthorized scope change, child work that no longer contributes to the parent outcome, weakened quality/failure/recovery/security/compatibility behavior, boundary drift, evidence of activity without outcome proof, and repairs that make a local test pass by changing the contract. Route intent drift to the responsible planning or authority boundary; never silently rewrite the parent artifact.

## Profile conformance

When a profile applies, include its locked assumptions, required gates, unsupported capabilities, and toolchain constraints in the intent chain. An installed profile is implementation evidence or procedure, not permission to change the requested outcome or architecture.
