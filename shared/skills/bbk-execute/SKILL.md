---
name: bbk-execute
description: Execute a BBK operating plan through bounded workers, isolated workspaces, deterministic gates, late candidate freeze, assertion-scoped validation, repair, and structured handoff. Use for multi-part implementation or other effectful work.
---

# BBK Execute

Execute the active work-unit contracts; do not silently redesign the outcome or boundary.

## Bound planning artifacts

Before implementation-oriented effects, verify that any required SolutionOutcomeFit permits solution commitment and that the work unit references the accepted fit/outcomes, ImplementationStructureContract, ExecutionSlice, and resolved profile. A causal, structural, or slice contradiction is a planning discovery, not an ordinary implementation patch.


## Authority and capability zones

The executable invocation must carry standing user authority explicitly. Record its source, already approved effects, exact scope, safeguards, exclusions, and revocation or expiry. A worker must not ask again for routine source writing, disposable-root cleanup, or temporary package installation already authorized inside that boundary; missing or ambiguous authority narrows the grant.

Classify every writable or inspectable location:

- **Disposable candidate root:** create, expected-hash-guarded replace, rename, and delete are allowed inside the exact root. Do not escape it or remove an artifact whose ownership or expected prior hash is unknown.
- **Protected worktree:** mutate only explicitly owned paths. Unrelated cleanup, broad formatting, and opportunistic repair remain out of scope.
- **Sealed or historical evidence:** immutable. Create a successor carrier or disposition outside the sealed zone.

Host sandbox access is capability, not authority. The invocation contract and zone assignment remain controlling.

## Tool and payload contract

Supply exact executable paths, versions, environment activation, and fallback commands for BBK, runtimes, compilers, source inspection, binary or IL inspection, and profile tools. A missing required tool is `BLOCKED_TECHNICAL`, not permission to improvise.

Declare payload limits before work begins. Preflight exact or large writes against those limits. If a payload will not fit, fail before mutation or use an approved durable file carrier. Never treat silent truncation as a successful write.

For exact replacement, prefer an exact-byte or atomic-write operation with an expected prior hash, final byte count, and final SHA-256. Where the host lacks such a tool, stage to a temporary file inside the same capability zone, verify it, atomically replace when supported, and verify the final bytes.


## Before effects

1. Bind the exact work unit, inputs, dependencies, interfaces, writable scope, prohibited scope, tools, effects, assurance contract, and completion evidence.
2. Confirm each concurrent writer has a distinct physical workspace. A branch name alone is not isolation.
3. Resolve only routine implementation choices inside delegated authority. Escalate changes to outcome, scope, shared interfaces, requirements, protected floors, external effects, or hard-to-reverse commitments.
4. Run applicable cheap preflight checks before expensive work. Keep preflight proportional so it does not consume the worker's useful execution window.
5. Assign an execution-window class and checkpoint policy. Workers default to an extended cohesive run intended to complete the work unit, not a short turn that stops after planning or preflight.

## During work

1. Keep the implementation mutable as a draft until the applicable pre-freeze gates pass.
2. Record discoveries as ordinary in-scope work only when they remain inside the same outcome, boundary, authority, interface, and assurance contract. Route everything else for impact review.
3. Run focused checks while iterating. Do not repeatedly run the full suite solely for reassurance.
4. Use actual consumers when the claim being made concerns downstream consumption. Do not require an actual-consumer test for unrelated changes.
5. Treat skipped or unavailable required checks as `BLOCKED`, not as success.
6. Persist progress through `bbk-handoff`: write exact paths, hashes, commands, evidence, and continuation state to disk; return only a concise path/byte-count/digest envelope through the agent bridge.
7. When the host interrupts or expires a worker without a technical blocker, classify it as an infrastructure interruption. Resume or steer the same worker thread when supported; otherwise launch a successor against the verified durable checkpoint rather than restarting discovery.


## Child lifecycle and operational state

Use these operational states for execution coordination:

```text
COMPLETE
PARTIAL
BLOCKED_TECHNICAL
BLOCKED_AUTHORITY
BLOCKED_DECISION
PAUSED_CAPACITY
PAUSED_HOST_WINDOW
CANCELLED
INCONCLUSIVE
```

Keep semantic readiness separate. `READY_FOR_PARENT_INTEGRATION` may describe a WorkUnit contribution in the role result, but it is not an operational disposition and does not freeze a candidate or authorize validation admission. Accept `READY_FOR_VALIDATION` only when consuming a legacy `bbk.handoff.v1` record.

Only the three `BLOCKED_*` states affect the development disposition. Capacity and host-window pauses are scheduling or infrastructure states and preserve the current candidate/work-unit disposition.

A wait timeout is a parent polling deadline only. Elapsed time, silence, repeated polling timeouts, apparent slow progress, or absence of a heartbeat are not evidence of failure or hang. Heartbeats and progress events are informational.

Interrupt a running child only for:

```text
USER_CANCELLED
CHILD_REQUESTED_STOP
UNAUTHORIZED_EFFECT
OWNERSHIP_COLLISION
CONFIRMED_HANG
OBSOLETE_WORK
```

Before interruption, record the reason, concrete evidence, why waiting or non-interrupting steering is insufficient, and the location/status of partial work. Never interrupt a completed, failed, or already-interrupted child. Consume its result; for related work, continue the same logical child thread through the host continuation/follow-up operation when possible.


## Freeze and validate

1. Freeze one exact candidate only after ordinary edits and cheap applicable checks are complete. Use `bbk manifest create`/`compare` for exact directory inventories and `bbk candidate freeze`/`check`/`verify` for candidate identity rather than inventing ad hoc hash listings.
2. Run the candidate-bound prevalidation gate once. Reuse a valid receipt only when its complete fingerprint is unchanged.
3. Launch validators only for exact named assertions and only after candidate eligibility is established.
4. Treat a configured gate receipt's `stdout` and `stderr` fields as bounded previews. The complete streams are receipt-bound files with project-relative path, byte count, and SHA-256; verify those files whenever a preview is truncated or the exact output is evidence-bearing.
5. Avoid overlapping validator charters. One assertion should not be independently re-proved several times without a distinct assurance reason.
6. Aggregate findings without voting or averaging. Preserve every finding and candidate identity.
7. Every repair creates a successor candidate and re-runs only invalidated evidence plus any required aggregate gate.
8. Use two ordinary local repair cycles as the default; by the third unresolved cycle, inspect whether the plan, interface, assertion, or test is wrong.

## Completion

Close the work unit only when the completion evidence required by its contract is current. Verify the durable handoff file and every material artifact/evidence byte count and SHA-256 before relying on it. Return the operational disposition, exact subject, authority and capability-zone use, changed artifacts and hashes, commands, validation, candidate identity, gate receipts, discoveries, residual uncertainty, blocker or pause classification, continuation state, and smallest next action.

## Alpha.7 execution bindings

- Keep workers bound to fixed State–Decision–Effect decisions and exact transition/effect obligations; material state or effect drift returns to structure review.
- Launch review attempts only from an exact ReviewManifest and complete ReviewContextManifest. Preserve reviewer/infrastructure failure separately from candidate failure.

## Language and domain profiles

Before effects or child dispatch, confirm that the work unit, `bbk-installed-profiles`, and the effective profile lock agree and that the selected package is verified and compatible. Supply the profile router skill, only the focused procedures selected by `bbk-profile-routing`, the exact toolchain assumptions, and required profile gates. A missing, mismatched, or unavailable required profile capability is a planning or eligibility blocker, not permission to improvise a generic substitute.
