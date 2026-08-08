# Alpha.17 OMP governed binding boundary

Status: **automated PASS for WU-012**

The `governed-software` profile is explicit. Baseline/default OMP behavior is
unchanged unless `BBK_GOVERNED_PROFILE=governed-software` is selected.

## Enforced on the qualified host

For the supplied OMP 16.4.8 binary, the existing keyless host-contract evidence
establishes that `tool_call` runs before built-in effects and can block them. The
Alpha.17 extension therefore blocks built-in `write`, `edit`, and `bash` at that
pre-effect boundary. A `task` call is admitted only after the adapter consumes a
single-use immutable spawn reservation matching the exact input digest, parent
session, task name, role, active binding, and host version.

A complete writable-worker binding includes work unit, attempt, baseline,
candidate, workspace, jj change, authority, path and mutation scope, invocation,
session, and return contract. CWD is never accepted as candidate, workspace, or
session authority.

## Governed filesystem effects

The active binding also supplies the only workspace, role capability, mutation
class, and path-scope authority for `bbk_governed_read`,
`bbk_governed_write`, `bbk_governed_edit`, and `bbk_governed_delete`. Paths are
workspace-relative, symlink traversal is denied, sealed packages are invariant,
and successful effects are reconciled against Git and the exact jj change before
a mutation receipt can report success. See
`docs/qualification/GOVERNED-FILESYSTEM-ALPHA17.md`.

## Continuity

`WAKE`, `INJECT`, and `RESUME` retain the exact active session/invocation
binding. `RETRY` requires a complete successor binding with a new attempt and
invocation that explicitly supersedes the predecessor without changing stable
role, work-unit, baseline, authority, return-contract, or parent-session fields.

## Honest limits

- OMP lifecycle and post-effect events are `DETECT_ONLY` evidence, not prevention.
- Any host other than the qualified 16.4.8 identity is `UNQUALIFIED` until it is
  re-qualified.
- No operating-system sandbox is claimed.
- Effects outside OMP-mediated hooks remain `DETECT_ONLY` or `UNQUALIFIED`.
- Raw prompts, provider payloads, API keys, tokens, and credentials are excluded
  from durable host records.

Canonical machine-readable status is in
`evidence/qualification/omp-governed-boundary-alpha17.json`.
