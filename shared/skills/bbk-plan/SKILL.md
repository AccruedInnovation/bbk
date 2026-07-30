---
name: bbk-plan
description: Create or repair a proportional BBK operating plan from an ambiguous request or supplied plan. Use for operational outcomes, boundaries, interfaces, capability-oriented work, work units, assurance contracts, agent selection, and execution readiness.
---

# BBK Plan

Create the smallest plan that makes safe progress possible.

0. Treat the requested intervention as a candidate means unless it is itself an accepted preference, learning objective, or hard external constraint. Perform a proportionate SolutionOutcomeFit check before material solution commitment. Carry its exact fit and outcome references downstream.

1. State the desired operational result, success evidence, in-scope boundary, exclusions, constraints, and accountable decision authority.
2. Separate observed facts, assumptions, proposals, accepted choices, and unresolved uncertainty.
3. Map only the territories needed to reach the result. Subdivide for coherent responsibility, distinct expertise or authority, failure containment, or useful safe parallelism—not to reduce prompt length.
3a. Route clustered human decisions through a logical Questioning Wayfinder boundary that prepares exact Question Guide context and returns ADR-compatible decision packets.
3b. Record logical roles separately from physical invocations; do not assume one role equals one model call.
4. Define material interfaces once. Include provider, consumers, ownership, normal behavior, failure, retry, cancellation, compatibility, observability, transition, and recovery as applicable.
5. Compare credible alternatives for consequential, interface-heavy, uncertain, or hard-to-reverse choices. Prototype only when a bounded artifact resolves uncertainty more cheaply than more analysis.
6. Organize delivery around integrated capability outcomes, then phases and single-concern work units.
7. For every work unit define purpose, inputs, mutation scope, dependencies, interfaces, expected behavior, checks, handoff, rollback, and completion evidence.
8. Assign a task-kind profile and language/toolchain profile instead of inventing a permanent specialist role for every combination.
8b. Where organizational control flow is material, bind a reusable procedure record or explicit inline procedure separately from the performer definition and execution authorization.
8c. Compile explicit context edges and result envelopes for delegated work; ambient conversation history is not a valid context contract.
8a. When realization shape is material, create one domain-neutral ImplementationStructureContract before final work decomposition. Then define coherent ExecutionSlices with an integrated touchpoint, explicit integration owner, assertions, evidence, failure containment, and scaffolding disposition. Resolve task/language profiles from those artifacts rather than from language alone.

9. Compile an `AssuranceContract` from risk and change class. Do not inherit maximum rigor by default.
10. Close deterministic entry checks before effects. Identify the cheapest sufficient proof for every material assertion and the exact reason any independent review is required.
11. Plan late candidate freeze. Do not assign a candidate identity while ordinary implementation edits remain expected.
12. End with execution order, safe parallelism, blockers, decision points, and the minimum review needed before starting.

For a supplied plan, preserve useful structure and add only missing boundaries, interfaces, work-unit contracts, candidate identity, or assurance needed for responsible execution.

13. For stateful or effectful realization, disposition State–Decision–Effect applicability inside the ImplementationStructureContract and bind fixed decisions, traces, and formalization proportionately.
14. Compile a review manifest only when the AssuranceContract needs a separately persisted review. Keep context compilation, execution, evidence, findings, and closure distinct.

15. For exploratory, alternative, replication, robustness, or confirmatory work, declare the branch purpose, exposure history, variation allowed, synthesis/selection rule, disagreement handling, stopping, and any later fresh-confirmation requirement.

## Language and domain profiles

Before fixing language-specific structure, work units, gates, or review obligations, consult `bbk-installed-profiles`, confirm live discovery with `bbk --json profile list`, and bind the smallest compatible profile through `bbk-profile-routing`. Use its router skill rather than loading every focused skill.

## Language-profile planning

Consult `bbk-installed-profiles` while mapping implementation surfaces. Record the selected profile router, exact version or lock, toolchain assumptions, capability gaps, and profile-owned gates in the operating baseline. Delegate profile selection through `bbk_worker_designer` or `bbk_verification_designer` when it materially affects worker composition or assurance.
