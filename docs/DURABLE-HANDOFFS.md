# Durable handoffs and large outputs

BBK treats a host turn as one segment of a logical worker lifecycle. Exact or large results are carried by durable project-local artifacts rather than by a truncated parent message.

## Current operational disposition vocabulary

Current producers use `COMPLETE`, `PARTIAL`, `BLOCKED_TECHNICAL`, `BLOCKED_AUTHORITY`, `BLOCKED_DECISION`, `PAUSED_CAPACITY`, `PAUSED_HOST_WINDOW`, `CANCELLED`, or `INCONCLUSIVE`. Legacy `READY_FOR_VALIDATION`, `BLOCKED`, and `PAUSED` remain consume-only `bbk.handoff.v1` values.

## Sealed v2 carrier

New handoff construction defaults to a sealed `bbk.handoff.v2` package:

```bash
bbk handoff create --root . --work-unit WU-001 --attempt 1 \
  --disposition PARTIAL --summary "Implementation complete; validation remains" \
  --artifact out/result.json --continuation-state READY \
  --checkpoint .bbk/runtime/checkpoint.json \
  --next-action "Resume the same logical worker and validate"

bbk handoff verify .bbk/handoffs/WU-001/HO-WU-001-1 --root .
bbk handoff list --root . --work-unit WU-001 --latest
```

The semantic `handoff.json` is canonicalized and sealed by the common artifact-package engine. Package bytes, byte counts, SHA-256 digests, closure, canonicalization labels, manifest, and seal receipt are tool-owned. Verification is read-only and detects any change to the sealed copy.

Use `--legacy-v1` only when an explicit standalone `bbk.handoff.v1` producer is required. V1 files remain readable, verifiable, listable, and eligible for Beads pointer projection.

A complete handoff identifies the logical role and attempt, exact subject and authority, capability zones, disposition, work performed, changed paths, commands/checks, findings/discoveries/residuals/blockers, artifact/evidence references, continuation state, cleanup, prohibited claims, and exact next action. Irrelevant optional sections may be omitted.

## Logical execution windows

A polling timeout, elapsed time, silence, or missing heartbeat is non-evidence. Workers checkpoint before a host-window interruption and resume the same logical thread when possible. A successor attempt records whether prior partial work is resumed, adopted, replaced, or discarded. Host capability does not create authority.

## Beads projection

Beads may carry only a compact verified pointer:

```bash
bbk beads handoff-plan --root . \
  --handoff .bbk/handoffs/WU-001/HO-WU-001-1 \
  --target-bbk-id WU-001 --apply
```

The v1 file and v2 package paths produce the same pointer semantics. BBK files remain authoritative. Tracker state, comments, hierarchy, or closure do not become execution, acceptance, completion, or release authority.

## Lossless configured-gate output

Configured-gate receipts may contain bounded previews, but complete stdout and stderr are stored as separate project-relative artifacts with exact byte counts and SHA-256 digests. A PASS receipt is not reusable when either bound stream is absent or changed.

## Validation

Core v1/v2 handoff and package validation is standard-library capable. Optional external Draft 2020-12 validation remains an independent cross-check and is not required for test collection.
