---
name: bbk-recover
description: Recover BBK work after interruption, stale candidates, orphaned worktrees, failed gates, ambiguous effects, or partial handoffs. Use when continuing blindly could duplicate work, lose evidence, or mutate the wrong subject.
requires_prompt_modules: []
standalone_prompt_modules: []
---

# BBK Recover

Recover from durable facts before relying on transcript memory.

0. Recover the accepted planning chain first: SolutionOutcomeFit, outcomes, structure contract, slices, work unit, resolved profiles, candidate and receipts. A current candidate against stale or blocked planning inputs is not safe to resume.

1. Identify the project root, active work unit, candidate, workspace, latest receipts, unresolved findings, and last known external effects.
2. Classify the condition: clean interruption, host execution-window expiry, stale candidate, dirty or orphaned workspace, failed gate, incomplete handoff, ambiguous external effect, or evidence corruption.
3. Stop new mutation when candidate identity, workspace ownership, or an irreversible external effect is ambiguous.
4. Reconstruct from `.bbk/` records, Git state, candidate manifests, receipts, durable handoff files, and direct artifact reads. Never infer success or failure from a missing process, quiet session, elapsed time, repeated wait timeouts, absent heartbeat, truncated tool output, or a parent summary.
5. Continue automatically only when the exact intended next state is uniquely derivable and no authority boundary changes. Prefer resuming or steering the existing worker thread; otherwise dispatch a successor from the verified checkpoint with no repeated discovery.
6. Reconcile ambiguous external effects before retrying. Do not blindly repeat non-idempotent operations.
7. Preserve failed candidates, logs, and findings. Mark supersession or staleness outside sealed candidate directories.
8. Clean only BBK-owned resources after checking worktree dirtiness, active references, and retention policy.
9. Verify handoff path, byte count, and SHA-256 before resuming exact work. If the carrier is missing or mismatched, return `RECOVERY_REQUIRED` rather than reconstructing it from memory.
10. Return a recovery disposition: `RESUME`, `RETRY_SAFE`, `REPAIR_REQUIRED`, `REPLAN_REQUIRED`, `AUTHORITY_REQUIRED`, or `ABANDON_AND_PRESERVE`. Preserve the precise operational class (`BLOCKED_TECHNICAL`, `BLOCKED_AUTHORITY`, `BLOCKED_DECISION`, `PAUSED_CAPACITY`, or `PAUSED_HOST_WINDOW`) rather than collapsing it into generic failure.

Review recovery also reconstructs manifest, context, run/attempt lineage, open findings, dispositions, evidence validity, and prior-findings visibility. Never retry a non-idempotent review effect or mark an interrupted attempt as a candidate failure.


## Interruption evidence

A prior interruption is valid only when its reason was `USER_CANCELLED`, `CHILD_REQUESTED_STOP`, `UNAUTHORIZED_EFFECT`, `OWNERSHIP_COLLISION`, `CONFIRMED_HANG`, or `OBSOLETE_WORK` and the record contains concrete evidence. `Timed out`, `silent`, `taking too long`, repeated wait timeout, and missing heartbeat are invalid reasons. Treat heartbeat/progress events as informational and resume from durable state when safe.


## Profile-aware recovery

Reconcile the work unit's profile lock with `bbk-installed-profiles` before resuming. A removed, upgraded, drifted, or newly unavailable profile/toolchain invalidates only the dependent context, gates, and receipts, but may block the candidate until a responsible planner dispositions the change.
