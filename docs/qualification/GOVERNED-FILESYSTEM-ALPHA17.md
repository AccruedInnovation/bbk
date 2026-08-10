# Alpha.17 governed filesystem qualification

Status: **automated PASS for WU-013**

Release candidate scope: `0.1.0-alpha.17+rc.2`  
Stable jj change identity: `loqtsroyovyqozprxrvsmwnurqnwnmqk`

## Qualified contract

The explicit `governed-software` OMP profile exposes four custom tools:

- `bbk_governed_read`
- `bbk_governed_write`
- `bbk_governed_edit`
- `bbk_governed_delete`

Each call is converted to `bbk.mutation-intent.v1`, correlated to the exact
active invocation binding, authorized before effect by the Gate Kernel, and
returned as `bbk.mutation-result.v1`. The adapter accepts no workspace or
absolute target authority from model-controlled content. The workspace, role,
capability, mutation classes, and path prefixes come from the immutable binding;
the requested path must remain relative to that workspace.

## Enforced properties

- Process CWD is never used as workspace authority.
- Absolute paths, drive-qualified paths, empty/dot/parent components, workspace
  escape, and symlink traversal fail closed before effect.
- The compiled role-capability manifest is digest-verified and bound to the
  invocation before the Gate Kernel evaluates the request.
- Mutations beneath `.bbk/artifacts/sealed` or beneath any package whose
  `bbk-package.json` declares lifecycle `SEALED` are invariant-blocked.
- Expected presence or SHA-256 preconditions are checked before effect.
- Writes and edits use a same-directory temporary file, `fsync`, and atomic
  replacement where the host permits it; deletes accept regular files only.
- Git-observed changed paths are reconciled against the bound path scope and the
  exact jj change identity after every mutation.
- Immutable Gate, VCS, filesystem, and host receipts identify the exact binding,
  session, invocation, candidate, path, and before/after digests without
  retaining raw credentials or provider payloads.
- Exact idempotent retries reuse the prior result only while the observed target
  state remains equivalent. Reused keys with changed intent or changed state
  fail closed.

## Acceptance assertions

- `VER-031`: **PASS** — authorization occurs before effect and all paths resolve
  from the bound workspace rather than CWD.
- `VER-032`: **PASS** — designated and declared sealed package paths are
  invariant-immutable through the governed mutation boundary.

## Automated evidence

```text
python -m unittest -v \
  tests.test_governed_filesystem \
  tests.test_gate_kernel \
  tests.test_omp_governed_profile \
  tests.test_installation_repository_sources.SharedPathAssertionSupportTests
```

The suite covers all four operations, real Git reconciliation, supplied jj
identity, role denial, path and symlink escape, sealed paths, preconditions,
idempotent retry and collision, session/invocation/payload/host binding,
out-of-scope pre-existing drift, installed runtime inventory, and schema-valid
results. The OMP integration test executes a governed write through the exact
binding and verifies the correlated pre-effect host receipt.

Canonical machine-readable status is in
`evidence/qualification/governed-filesystem-alpha17.json`.

## Honest limits

- No operating-system sandbox is claimed.
- Effects outside the OMP-mediated custom-tool and pre-tool boundaries remain
  `DETECT_ONLY` or `UNQUALIFIED`.
- Symlinks are conservatively denied rather than resolved as authority.
- OMP hosts other than qualified 16.4.8 identities remain `UNQUALIFIED`.
- This automated work unit does not replace the release-wide, user-run,
  API-key-enabled OMP qualification required before Alpha.17 finalization.
