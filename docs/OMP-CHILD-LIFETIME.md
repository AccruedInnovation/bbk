# OMP child lifetime and BBK callback sequencing

## Exact OMP 16.4.8 cause

BBK alpha.13.4 retains the child-lifetime contract introduced in alpha.13.3 and targets OMP `16.4.8`. That release has two task-execution paths.

### Native background path

When all of the following are true:

- `async.enabled=true`;
- the session exposes an `AsyncJobManager`; and
- the selected agent does not declare `blocking: true`;

OMP registers each task spawn as a managed background job and returns control to the parent. The lifecycle event marks the spawn `detached`, a job handle is available for inspect/wait/cancel, and the result is delivered when the child yields.

All generated alpha.13.4 OMP BBK agents explicitly declare:

```yaml
blocking: false
```

This is the native non-cascading child-lifetime path. BBK does not invent a task argument or private OMP API; it declares its agents eligible for the public behavior selected by OMP's setting and job manager.

### Inline path and the observed cancellation

When asynchronous task execution is disabled or unavailable, or when an agent declares `blocking: true`, OMP runs the child inline. The synchronous executor receives the parent tool-call `AbortSignal`, and a parallel inline cohort combines that parent signal with its cohort controller.

An IRC message, user response, or steering wake can interrupt the parent's current task wait. In the inline path, aborting that parent task call can therefore abort still-running children. The extension's Python subprocess abort handler is unrelated; it controls BBK-owned CLI processes, not native OMP task children.

The ordinary model-facing `task` schema does not expose a per-call `detached`, `preserveOnInterrupt`, or non-cascading wait field. Execution mode is derived from OMP's host setting and agent frontmatter.

## Alpha.13.3 implementation path

Alpha.13.3 uses the native OMP path where it is available and a BBK scheduling fallback everywhere else.

1. All 19 generated OMP roles declare `blocking: false`.
2. A role that sends a `BBK_USER_REQUEST` or equivalent controller callback does not enter a cancellation-sensitive blocking child wait while an immediate response may arrive.
3. Request transport and such a task wait are not placed in the same callback window or tool batch.
4. Decision-dependent specialists are dispatched only after the bound response is durably integrated.
5. Local analysis may continue while waiting. Independent child work may run concurrently only through a host-proven detached or non-cascading lifetime; otherwise BBK sequences safely.
6. A parent wake is not cancellation authority. Explicit cancellation, declared cascading abort policy, process/session termination, and unrecoverable runtime failure remain valid cancellation paths.

This avoids the observed failure whether OMP background execution is enabled or not. BBK does not force the user's OMP `async.enabled` setting and does not add a second scheduler.

## Before and after

Before alpha.13.3, a parent could send a user decision request, immediately enter an inline specialist batch, then have the user response interrupt that task call and cancel the specialists.

After alpha.13.3:

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

A per-call override would require OMP to expose model-facing lifetime selection separate from agent frontmatter and host settings. Alpha.13.3 does not assume such an option.

The available managed-job path already provides inspect, wait, result delivery, and explicit cancel operations. When that path is disabled or absent, BBK relies on safe sequencing rather than pretending the inline `AbortSignal` is non-cascading.
