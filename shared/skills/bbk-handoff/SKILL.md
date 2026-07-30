---
name: bbk-handoff
description: Create and verify durable, lossless BBK handoffs for worker, validator, review, planning, and recovery boundaries. Use when exact paths, hashes, evidence, large output, or continuation across agent turns is material.
---

# BBK Handoff

A chat response is a notification channel, not a reliable evidence carrier. Use a durable handoff file whenever exact paths, hashes, commands, evidence, or more than a small summary must cross an agent boundary.

## Carrier

Write one UTF-8 JSON handoff under `.bbk/handoffs/` or another invocation-authorized project path. Bind:

- schema and handoff ID;
- exact subject, work unit, candidate/revision, attempt, producer role, and physical invocation when known;
- operational disposition and concise summary;
- work performed, changed paths, commands, checks, findings, discoveries, residuals, blockers, and smallest next action;
- every material artifact/evidence reference as a project-relative path plus byte count and SHA-256;
- profile identity/lock, context package, standing-authority source and scope, capability-zone use, and exposure history where applicable;
- continuation state sufficient for a fresh agent to resume without transcript memory;
- blocker or pause classification and, when interrupted, the permitted interrupt reason and concrete evidence.

Use one record per attempt. Do not overwrite an earlier handoff to make a later attempt look successful.


## Operational disposition vocabulary

Use precise execution state:

- `BLOCKED_TECHNICAL` — required tool, environment, implementation, or infrastructure capability cannot proceed.
- `BLOCKED_AUTHORITY` — the needed effect is outside, absent from, expired under, or ambiguous in the authority grant.
- `BLOCKED_DECISION` — a governing choice must be made before work can continue.
- `PAUSED_CAPACITY` — work is ready but no execution capacity is available.
- `PAUSED_HOST_WINDOW` — the host turn ended with a valid continuation checkpoint.

Capacity and host-window pauses are not candidate failures. Retain legacy `BLOCKED` or `PAUSED` only when consuming an older handoff whose more precise class is unavailable.

Allowed interrupt reasons are `USER_CANCELLED`, `CHILD_REQUESTED_STOP`, `UNAUTHORIZED_EFFECT`, `OWNERSHIP_COLLISION`, `CONFIRMED_HANG`, and `OBSOLETE_WORK`. Reject `timed out`, `silent`, `taking too long`, or `slot needed` as reasons.


## Lossless transport rule

For large, single-line, binary, generated, or evidence-heavy content:

1. write the content directly to an authorized file;
2. compute byte count and SHA-256 from disk;
3. include only a concise summary and the file reference in the agent return;
4. have the receiver verify the file, byte count, and digest before relying on it.

Never copy a large evidence carrier through a patch/result bridge merely because it can display text. If the receiver shares the filesystem, it should read the file directly.

## Response envelope

The model-facing return should normally contain only:

```text
disposition
exact_subject
summary
blocker_or_pause_class
continuation_state
handoff_path
handoff_bytes
handoff_sha256
smallest_next_action
```

The parent then verifies and reads the durable record. A truncated response is recoverable because the authoritative carrier remains on disk.

## Beads projection

When Beads projection is enabled, append a compact comment or note to the mapped bead containing BBK work-unit ID, disposition, handoff path, byte count, SHA-256, and next action. Do not put the full handoff or large evidence into a bead text field. Beads is a coordination index; the BBK handoff file and referenced artifacts remain the exact carriers.

Use append/comment semantics rather than replacing existing notes. Verify the resulting bead state when concurrent writers or sync modes are in use.

## Recovery and authority

An absent, mismatched, stale, or unreadable handoff is `BLOCKED` or `RECOVERY_REQUIRED`, not permission to reconstruct exact evidence from memory. A handoff communicates state; it does not accept a decision, close a finding, authorize effects, prove validation, or grant release authority.

## Discovery

When a compact agent return loses or truncates the exact locator, rediscover the authoritative carrier with `bbk handoff list --root <project> --work-unit <id> --latest`, then verify it before reading. Do not guess a path or hash from conversational memory.
