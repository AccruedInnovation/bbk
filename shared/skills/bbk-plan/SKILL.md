---
name: bbk-plan
description: Create or repair a proportional BBK operating plan from an ambiguous request or supplied plan. Use for operational outcomes, Wayfinding, interfaces, capability-oriented work, work units, assurance contracts, agent selection, and execution readiness.
---

# BBK Plan

Create the smallest plan that makes safe progress possible. Use `bbk-wayfind` for the recursive navigation loop; this skill defines the planning artifact chain and execution-readiness contract.

0. Treat the requested intervention as a candidate means unless it is an accepted preference, learning objective, or hard external constraint. Perform a proportionate SolutionOutcomeFit check before material solution commitment and carry exact fit/outcome references downstream.
1. State the operational result, success evidence, current/no-change baseline, actors and affected viewpoints, in-scope boundary, exclusions, constraints, feared events, and accountable decision authority. Record any standing user authority as an explicit grant with its source, already approved effect classes, exact scope, safeguards, exclusions, and revocation or expiry conditions.
2. Calibrate posture: distinguish `USER_DECIDES`, `WAYFINDER_RECOMMENDS`, `DELEGATED`, and `CONSTRAINT_DRIVEN` choices. Separate facts, assumptions, proposals, accepted choices, and unresolved uncertainty.
3. Maintain map, actionable frontier, blockers, and fog. Map only territories needed to reach the result; subdivide for coherent responsibility, authority, specialization, containment, or useful safe parallelism—not prompt length.
4. Route material human decisions through `bbk_questioning_wayfinder`. It should retire discoverable facts and produce a decision-ready recommendation first. Spawn `bbk_question_guide` only when the recommendation is rejected, contested, materially ambiguous, or deeper exploration is requested.
5. Record logical roles separately from physical invocations. Compile explicit context edges and result envelopes; ambient transcript history is not a context contract.
6. Define material interfaces once. Include provider, consumers, ownership, normal behavior, failure, retry, cancellation, compatibility, observability, transition, and recovery as applicable.
7. Compare credible alternatives for consequential, interface-heavy, uncertain, or hard-to-reverse choices. Prototype only when a bounded artifact resolves uncertainty more cheaply than analysis.
8. When realization shape is material, create one domain-neutral ImplementationStructureContract, then coherent ExecutionSlices with integrated touchpoints, integration owners, assertions, evidence, containment, and scaffolding disposition.
9. Organize delivery around actor-visible capability outcomes, then phases and single-concern work units. For every work unit define purpose, exact inputs, mutation scope, standing-authority grant, capability zones, dependencies, interfaces, expected behavior, exact tool environment, payload limits, operational dispositions, interruption policy, checks, runtime budget, checkpoint/handoff contract, rollback, and completion evidence.
10. Assign task-kind and language/toolchain profiles instead of inventing permanent specialist roles. Bind reusable procedures separately from performer identity and execution authorization.
11. Compile an AssuranceContract from consequence, uncertainty, change class, and protected floors. Prove each material assertion once by the cheapest sufficient method; add independence only for a distinct property.
12. Close deterministic entry checks before effects and plan late candidate freeze. Do not assign candidate identity while ordinary edits remain expected.
13. For stateful or effectful realization, disposition State–Decision–Effect applicability and bind fixed decisions, traces, and formalization proportionately.
14. Compile persisted review records only when separately inspectable assurance is required. Keep context compilation, execution, evidence, findings, and closure distinct.
15. Declare branch purpose, evidence exposure, variation allowed, synthesis/selection rule, disagreement handling, stopping, and later fresh-confirmation needs for exploratory, alternative, replication, robustness, or confirmatory work.
16. End with execution order, safe parallelism, blockers, explicit decision requests, invalidation/reopening triggers, residual fog, economic stopping assessment, and the minimum review needed before starting.

A Planning or Phase Wayfinder that discovers a missing outcome, interface, architecture, authority, risk-acceptance, or verification decision must return a structured decision request to the responsible Wayfinder. It must not silently choose what is needed to make its plan complete.

For a supplied plan, preserve useful structure and add only missing boundaries, interfaces, work-unit contracts, continuation/handoff state, candidate identity, or assurance needed for responsible execution.


## Execution-control compilation

For effectful or long-running work, make these fields explicit rather than leaving them in parent conversation history:

- **Standing authority:** source, approved writes/installations/effects, exact scope, safeguards, exclusions, and revocation or expiry. Children should not re-request routine permission already granted inside this boundary.
- **Capability zones:** a disposable candidate root permits create, expected-hash-guarded replace, rename, and delete inside the exact root; a protected worktree permits mutation only of explicitly owned paths; sealed or historical evidence is immutable.
- **Tool environment:** exact BBK launcher, runtime/compiler/inspection/profile executable paths, versions, activation steps, and deterministic fallbacks.
- **Payload contract:** declared inline/result limits, fail-before-mutation behavior, and file/byte-count/SHA-256 transport for exact or large content.
- **Operational states:** distinguish technical, authority, and decision blockers from capacity or host-window pauses.
- **Interruption policy:** silence, elapsed time, polling timeout, or missing heartbeat are non-evidence. Only an allowed reason with concrete evidence may stop a running child.
- **Return contract:** disposition, exact subject, authority/zone use, changed artifacts and hashes, commands, validation, discoveries, residual uncertainty, blocker/pause class, continuation state, and smallest next action.


## Language and domain profiles

Consult `bbk-installed-profiles` before fixing language-specific structure, work units, gates, or review obligations. Use the exact installed BBK launcher recorded by that registry when `bbk` is not on `PATH`. Bind the smallest compatible profile through `bbk-profile-routing`, load its router first, and record profile version/lock, toolchain assumptions, capability gaps, and profile-owned gates in the operating baseline.
