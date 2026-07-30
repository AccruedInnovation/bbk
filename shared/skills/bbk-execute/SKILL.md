---
name: bbk-execute
description: Execute a BBK operating plan through bounded workers, isolated workspaces, deterministic gates, late candidate freeze, assertion-scoped validation, repair, and structured handoff. Use for multi-part implementation or other effectful work.
---

# BBK Execute

Execute the active work-unit contracts; do not silently redesign the outcome or boundary.

## Bound planning artifacts

Before implementation-oriented effects, verify that any required SolutionOutcomeFit permits solution commitment and that the work unit references the accepted fit/outcomes, ImplementationStructureContract, ExecutionSlice, and resolved profile. A causal, structural, or slice contradiction is a planning discovery, not an ordinary implementation patch.

## Before effects

1. Bind the exact work unit, inputs, dependencies, interfaces, writable scope, prohibited scope, tools, effects, assurance contract, and completion evidence.
2. Confirm each concurrent writer has a distinct physical workspace. A branch name alone is not isolation.
3. Resolve only routine implementation choices inside delegated authority. Escalate changes to outcome, scope, shared interfaces, requirements, protected floors, external effects, or hard-to-reverse commitments.
4. Run applicable cheap preflight checks before expensive work.

## During work

1. Keep the implementation mutable as a draft until the applicable pre-freeze gates pass.
2. Record discoveries as ordinary in-scope work only when they remain inside the same outcome, boundary, authority, interface, and assurance contract. Route everything else for impact review.
3. Run focused checks while iterating. Do not repeatedly run the full suite solely for reassurance.
4. Use actual consumers when the claim being made concerns downstream consumption. Do not require an actual-consumer test for unrelated changes.
5. Treat skipped or unavailable required checks as `BLOCKED`, not as success.

## Freeze and validate

1. Freeze one exact candidate only after ordinary edits and cheap applicable checks are complete.
2. Run the candidate-bound prevalidation gate once. Reuse a valid receipt only when its complete fingerprint is unchanged.
3. Launch validators only for exact named assertions and only after candidate eligibility is established.
4. Avoid overlapping validator charters. One assertion should not be independently re-proved several times without a distinct assurance reason.
5. Aggregate findings without voting or averaging. Preserve every finding and candidate identity.
6. Every repair creates a successor candidate and re-runs only invalidated evidence plus any required aggregate gate.
7. Use two ordinary local repair cycles as the default; by the third unresolved cycle, inspect whether the plan, interface, assertion, or test is wrong.

## Completion

Close the work unit only when the completion evidence required by its contract is current. Report changed artifacts, candidate identity, gate receipts, validation findings, residual risk, discoveries, and follow-up work separately.

## Alpha.7 execution bindings

- Keep workers bound to fixed State–Decision–Effect decisions and exact transition/effect obligations; material state or effect drift returns to structure review.
- Launch review attempts only from an exact ReviewManifest and complete ReviewContextManifest. Preserve reviewer/infrastructure failure separately from candidate failure.

## Language and domain profiles

Before effects, confirm the work unit's selected profile is installed, verified, compatible, and locked. Load its router skill and run only the applicable profile procedures and gates. A required unavailable profile capability is `BLOCKED`, not permission to improvise a generic substitute.

## Language-profile execution

Before dispatching a worker or validator, confirm that the applicable entry in `bbk-installed-profiles` and the effective profile lock agree with the work unit. Supply the profile router skill and only the focused procedure modules selected by `bbk-profile-routing`. A profile or toolchain mismatch is a planning or eligibility blocker, not permission to improvise.
