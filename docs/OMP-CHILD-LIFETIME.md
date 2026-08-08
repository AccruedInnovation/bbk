# OMP child lifetime, callbacks, and revived-agent visibility

## Current behavior

BBK `0.1.0-alpha.17.0.2` treats **task execution state** and **live peer state** as separate observations and adds typed prompt-compilation/reuse state for the same logical child.

A child can finish one OMP task attempt, remain parked in the hub, and later be woken for follow-up work. The earlier task lifecycle may still say `completed`; that does not prove that the peer session is dead or inactive. `/bbk:agents` therefore reconciles two ordered evidence sources:

1. OMP task progress and lifecycle events; and
2. later coordination results from `hub`, legacy `irc`, or `job`.

The coordination source may reactivate a completed peer when Main observes:

- a successful `injected`, `woken`, or `revived` receipt;
- an authoritative peer roster reporting `running`, `active`, `working`, `busy`, or `waking`; or
- a legacy `job` running-agent report for a known peer.

A later lifecycle event or authoritative roster supersedes older wake evidence. A failed receipt never activates a peer. Role-bearing rosters may discover nested peers that were not present in the local task history, and stable IDs/aliases are reconciled so the same peer is not shown twice.

`/bbk:agents json` retains the additive `bbk.omp-agent-tree.v1` schema and exposes:

```text
status                 effective current status
task_status            newest task progress/lifecycle status
peer_status            newest coordination status, when observed
peer_status_current    whether peer evidence is at least as new as task evidence
status_source          evidence source controlling the effective status
wake_outcome           current successful wake outcome, only while it remains controlling
```

The text tree makes split state explicit, for example:

```text
BaffleRelayWayfinder [bbk_root_wayfinder] · running · task completed · peer running (woken)
```

This is an observability correction. It does not create cancellation authority, guarantee that a peer will make forward progress, or replace OMP's own task/session lifecycle. `/bbk:agents` reports the newest evidence visible to the current Main session; a wake or roster result not observed by that session cannot be invented.

The current extension includes the `controller_timing` attachment on `/bbk:agents json`. While native `ask` is open, human output prefixes `WAITING_ON_USER`, request IDs, wait start, and the count of independently active BBK peers. `/bbk:timing` reports the same wait separately from provider, tool, and sub-agent observations; it does not infer compute from unattributed time.

## Exact OMP 16.4.8 child-lifetime cause

BBK `0.1.0-alpha.17.0.2` retains the child-lifetime contract qualified against OMP `16.4.8`. Changed package or host bytes require separate live qualification. That OMP release has two task-execution paths.

### Native background path

When all of the following are true:

- `async.enabled=true`;
- the session exposes an `AsyncJobManager`; and
- the selected agent does not declare `blocking: true`;

OMP registers each task spawn as a managed background job and returns control to the parent. The lifecycle event marks the spawn `detached`, a job handle is available for inspect/wait/cancel, and the result is delivered when the child yields.

All generated OMP BBK agents explicitly declare:

```yaml
blocking: false
```

This is the native non-cascading child-lifetime path. BBK does not invent a task argument or private OMP API; it declares its agents eligible for the public behavior selected by OMP's setting and job manager.

### Inline path and the observed cancellation

When asynchronous task execution is disabled or unavailable, or when an agent declares `blocking: true`, OMP runs the child inline. The synchronous executor receives the parent tool-call `AbortSignal`, and a parallel inline cohort combines that parent signal with its cohort controller.

An IRC message, user response, or steering wake can interrupt the parent's current task wait. In the inline path, aborting that parent task call can therefore abort still-running children. The extension's Python subprocess abort handler is unrelated; it controls BBK-owned CLI processes, not native OMP task children.

The ordinary model-facing `task` schema does not expose a per-call `detached`, `preserveOnInterrupt`, or non-cascading wait field. Execution mode is derived from OMP's host setting and agent frontmatter.

## Current scheduling contract

BBK uses the native OMP path where it is available and a scheduling fallback everywhere else.

1. All 19 generated OMP roles declare `blocking: false`.
2. A role that sends a `BBK_USER_REQUEST` or equivalent controller callback does not enter a cancellation-sensitive blocking child wait while an immediate response may arrive.
3. Request transport and such a task wait are not placed in the same callback window or tool batch.
4. Decision-dependent specialists are dispatched only after the bound response is durably integrated.
5. Local analysis may continue while waiting. Independent child work may run concurrently only through a host-proven detached or non-cascading lifetime; otherwise BBK sequences safely.
6. A parent wake is not cancellation authority. Explicit cancellation, declared cascading abort policy, process/session termination, and unrecoverable runtime failure remain valid cancellation paths.

This avoids the observed cancellation whether OMP background execution is enabled or not. BBK does not force the user's OMP `async.enabled` setting and does not add a second scheduler.

The current extension bounds observation overhead deterministically. OMP background task results and IRC steering deliver themselves. Continue independent work, or when completely blocked use one empty `job` wait or `irc wait`; both wake on completion, messages, steering, or the host wait window. Persistent BBK mode denies specific-job polling and successful nonblocking `job list` / IRC inbox, list, or roster probes before 300 seconds have elapsed since dispatch or the prior probe while children remain active. Five minutes of silence permits one observation but is not child-health evidence, cancellation authority, or a reason to restart. Coordination calls and assurance calls remain separate verification-economy metrics.

## Why sequencing matters

The unsafe sequence sends a user decision request, immediately enters an inline specialist batch, and then lets the response interrupt that task call and cancel the specialists. The current sequence avoids that pattern:

- on the native background path, the request can wake the parent while eligible specialist jobs continue independently and later deliver exactly one result each;
- on the inline path, BBK does not dispatch decision-dependent specialists until the response is integrated, and it does not combine the callback with the cancellation-sensitive wait.

Explicit `job` or host cancellation still cancels the intended background child or cohort.

## Cancelled and partial attempts

Every physical child attempt retains a stable attempt identity. A cancelled, interrupted, failed, or incomplete attempt is provisional even when it wrote a plausible file. **File existence is not a complete specialist return.**

A successor records whether it:

```text
RESUMED
ADOPTED_AND_REPAIRED
REPLACED
DISCARDED
```

The parent may claim specialist completion only from the successful validated return and its attempt identity. Partial predecessor artifacts remain available for evidence and recovery but do not silently acquire canonical status.

## Upstream boundary

A per-call lifetime override would require OMP to expose model-facing lifetime selection separate from agent frontmatter and host settings. BBK does not assume such an option.

The available managed-job path already provides inspect, wait, result delivery, and explicit cancel operations. When that path is disabled or absent, BBK relies on safe sequencing rather than pretending the inline `AbortSignal` is non-cascading.
