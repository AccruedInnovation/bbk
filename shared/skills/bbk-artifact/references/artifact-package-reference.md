# BBK 0.1.0-alpha.17 artifact-package reference

This reference describes the `bbk artifact` surface implemented by BBK 0.1.0-alpha.17. The skill wrapper invokes the installed CLI as:

```text
<exact-python> -X utf8 <installed-package>/tools/bbk.py --json artifact <arguments>
```

The wrapper-specific `binding` command reports which installation it resolved. All other arguments are passed to `bbk artifact`.

## Command synopsis

```text
inspect PATH [--exclude PATTERN] [--include-examples] [--verbose] [--output FILE]
manifest [--root ROOT] [--path PATH] [--source PATH] [--include PATTERN]
         [--exclude PATTERN] [--include-examples] [--subject TEXT]
         [--root-label TEXT] [--output FILE]
preflight DRAFT_ROOT [--registry FILE] [--max-depth N]
doctor --root PROJECT_ROOT [--publication-root DIR]
reconcile JOURNAL_OR_OPERATION [--root PROJECT_ROOT] [--resume]
finalize [DRAFT_ROOT] [--root PROJECT_ROOT] [--output SEALED_ROOT]
         [--publication-root DIR] [--registry FILE]
         [--package-id ID --revision REVISION] [--source PATH ...]
         [--include GLOB ...] [--exclude GLOB ...]
         [--subject-kind KIND] [--subject-id ID]
         [--subject-revision REVISION] [--purpose TEXT]
         [--allow-mutable-coordination] [--no-current-pointer]
         [--recover-stale-lock]
freshness PUBLICATION_OR_CURRENT_OR_SEALED [--root PROJECT_ROOT]
          [--registry FILE]
seal DRAFT_ROOT --output SEALED_ROOT [--registry FILE] [--recover-stale-lock]
verify SEALED_ROOT_OR_MANIFEST [--root ROOT] [--registry FILE]
successor SEALED_ROOT --output DRAFT_ROOT --revision REVISION --reason TEXT
          [--registry FILE] [--recover-stale-lock]
```

## Filesystem qualification and transaction ordering

Run `doctor` before materialization. `bbk artifact doctor --root ROOT` qualifies the
exact runtime and filesystem used by the operation: workspace and same-volume
identity, durable file writes, directory flush, atomic replace, file and directory
no-replace, OS locks, readback, and cleanup. A doctor `PASS` is a capability
receipt; it does not establish native Windows durability, semantic acceptance, or
release readiness.

`finalize` acquires the publication namespace lock before the package-ID lock.
Each OS-held lock and operation journal carries one durable operation token. Lock
age, PID, host, or a stale-looking timestamp never authorizes takeover; inspect the
owner and reconcile the exact journal first. The compatibility option
`--recover-stale-lock` is deliberately rejected with
`PACKAGE_LOCK_RECOVERY_REQUIRES_RECONCILE`; it is not a lock-deletion or takeover
mechanism.

For sharing violations, the portable Win32 policy has exactly six attempts with
delays `0/25/50/100/200/400 ms`. Only classified sharing errors (Win32 32 or 33)
enter this schedule; unrelated errors are raised immediately. Exhaustion records
`PUBLISH_BLOCKED` and preserves the token-bound operation evidence.

## Publication, receipts, and pointer authority

Sealed targets and immutable publication receipts use no-replace creation. An
existing target or receipt is preserved and reported as a conflict; neither is
overwritten. `finalize` verifies the target once before writing the publication
receipt, performs receipt readback and schema/hash verification, then performs a
decisive target verification. Only after that ordering may it write and read back
the optional current-pointer projection. The pointer selects a verified package
identity; it is nonauthoritative and cannot extend the package's authority.

`seal` is an explicit `NON_PUBLISHED` package operation. It creates and verifies an
immutable sealed tree without publication metadata. `finalize` is the operation
that publishes the immutable receipt (and, when requested, the nonauthoritative
current pointer). `freshness` is a separate read-only check: it verifies the
publication or sealed tree and, for a source-bound publication, compares the live
selected paths, byte counts, and SHA-256 values with the recorded source snapshot.

Operation journals preserve typed dispositions: `ACTIVE`, `COMPLETED`,
`NON_PUBLISHED`, `REJECTED`, `RECOVERY_REQUIRED`, `CONFLICT_REJECTED`,
`CANCELLED_PRESERVED`, and `PUBLISH_BLOCKED`. Quarantine is limited to an exact
operation-owned output whose recorded verification or publication failure makes it
unsafe to consume. A pre-existing target, receipt, pointer, or unrelated user
path must remain in place; preserve it and choose a new successor or reconcile the
bound operation.

## Crash recovery and reconciliation

After a crash or uncertain effect, reconcile the existing journal and observed
target/receipt bytes. Recovery does not reread a mutable draft, regenerate package
bytes, overwrite an existing target or receipt, or rewrite terminal history. A
terminal journal (`COMPLETED`, `NON_PUBLISHED`, `REJECTED`, or
`CONFLICT_REJECTED`) is read-only. A `--resume` request without exact evidence of
one missing effect is converted to `PUBLISH_BLOCKED` and requires a bound recovery
observation; `RECOVERY_REQUIRED` and `CANCELLED_PRESERVED` remain preserved for
disposition rather than being rewritten as success.

## Compatibility and identity boundaries

Readers retain v1 read compatibility for the draft, package, manifest, seal
receipt, publication receipt, and current-pointer schema families. The current
writer remains v1 where the profile registry requires it; accepting a v1 input
does not silently upgrade or change its stored bytes.

Governed JSON uses strict UTF-8 and `BBK-JSON-1` canonicalization during sealing.
Non-JSON artifacts retain their exact input bytes (`UNCHANGED`); do not normalize
line endings or predict generated byte fields. A v2 content identity is
path-independent: it contains semantic package/profile/subject metadata,
predecessor identity, artifacts, and reference graph, but no physical lineage
locator. The engine, not a draft author, creates bytes, hashes, canonicalization,
content identity, manifests, receipts, and closure fields.

The handoff and context constructors call the internal seal constructor and require
the resulting package disposition to be `NON_PUBLISHED`; they do not create signed
attestations or any signed-attestation semantics. Use those constructors for their
dedicated package types and keep publication as a separate explicitly selected
`finalize` operation.

`verify` accepts either a sealed package directory or its `bbk-package-manifest.json`. It also retains compatibility with legacy `bbk.artifact-manifest.v1` files.

## Generic draft descriptor

The draft root must contain `bbk-package-draft.json` and every declared artifact. A minimal generic descriptor is:

```json
{
  "schema": "bbk.artifact-package-draft.v1",
  "packageId": "pkg-design-001",
  "revision": "1",
  "profile": {
    "id": "generic",
    "version": "1"
  },
  "subject": {
    "kind": "design-package",
    "id": "design-001",
    "revision": "1"
  },
  "predecessor": null,
  "artifacts": [
    {
      "artifactId": "design",
      "path": "design.md",
      "role": "semantic",
      "references": [
        "evidence"
      ]
    },
    {
      "artifactId": "evidence",
      "path": "evidence.txt",
      "role": "evidence",
      "references": []
    }
  ],
  "metadata": {
    "purpose": "Exact design and supporting evidence"
  }
}
```

`predecessor`, `successorReason`, `metadata`, artifact `schema`, artifact `mediaType`, and artifact `references` are optional in the schema, though generated successors populate predecessor data and references should be explicit when closure matters.

## Canonical profiles

| Profile | Version | Intended use | Permitted artifact roles |
|---|---:|---|---|
| `generic` | `1` | Arbitrary local artifact packages | `semantic`, `context`, `result`, `evidence`, `candidate`, `source`, `documentation`, `fixture`, `other` |
| `handoff-v2` | `1` | Sealed `bbk.handoff.v2` packages | `result`, `evidence`, `context`, `other` |
| `role-return-v2` | `1` | `bbk.role-return.v2` packages | `result`, `evidence`, `context`, `other` |
| `worker-context-v1` | `1` | Generated Worker context packages | `context`, `source`, `evidence`, `other` |
| `review-package-v2` | `1` | Generated review and focused-recheck packages | `context`, `candidate`, `evidence`, `result`, `other` |
| `candidate-package-v1` | `1` | Integrated candidate packages | `candidate`, `evidence`, `context`, `documentation`, `other` |

Prefer the dedicated BBK constructors for handoff and generated Worker/review context packages. The older `bbk candidate` commands manage `bbk.candidate.v1`; they do not construct the sealed `candidate-package-v1` package consumed by `bbk context review`. Construct a profile-specific sealed package directly only when the semantic artifact already exists, matches the required schema and subject binding, and the current role owns that construction decision.

## Descriptor constraints

- `packageId` and `artifactId` use stable IDs: one leading alphanumeric character followed by at most 127 alphanumeric, `.`, `_`, or `-` characters.
- `revision` is a non-empty string.
- `subject` requires `kind` and `id`; `revision` may be a string, integer, or null.
- Artifact paths must be portable, relative, physical file paths. They cannot use `\`, absolute prefixes, parent segments, symlinks, or package control filenames.
- Each artifact path and ID must be unique.
- `references` must contain unique declared artifact IDs. Artifact-reference cycles are forbidden for all alpha.16.1 profiles. Recursive JSON Schema references are evaluated separately and remain allowed.
- JSON is decoded as strict UTF-8. Duplicate keys, byte-order marks, non-finite numbers, malformed escapes, trailing data, and excessive nesting are rejected.
- JSON with a declared schema is canonicalized to BBK-JSON-1 during sealing. Do not predict or author canonicalized bytes manually.

## Generated ownership

The package engine exclusively owns these descriptor-derived fields:

```text
bytes
sha256
canonicalization
contentSha256
closure
sealReceipt
sealedAtUtc
toolVersion
```

It also exclusively generates:

```text
bbk-package.json
bbk-package-manifest.json
bbk-seal-receipt.json
```

A sealed package contains the declared artifacts plus those three generated control files. The mutable `bbk-package-draft.json` is not published into the sealed package.

## Operation behavior

### `preflight`

Runs cheap deterministic admission checks without mutating the draft. It validates the descriptor, profile, physical paths, artifact roles, declared schemas, strict JSON, schema instances, reference closure, reference cycles, required schemas, and profile-specific semantic bindings.

A preflight `PASS` is necessary for seal but does not reserve the output path or establish semantic acceptance.

### `seal`

Preflights, stages artifacts, computes generated identity, self-verifies the staged package, and atomically publishes to a new absent output directory. It refuses to overwrite an existing path. A failed operation must not be reported as a partial seal.

### `finalize`

`finalize` supports two modes.

**One-shot software mode** requires `--root`, `--package-id`, and `--revision`. When `--source` is omitted, BBK selects the project root; repeat `--source` only to narrow the candidate. BBK selects regular files inside the project, applies built-in exclusions for `.bbk`, VCS state, caches, virtual environments, `node_modules`, build output, and bytecode, then applies any explicit include/exclude globs. It constructs a temporary generic draft, classifies source/documentation/fixture roles mechanically, seals the selected bytes, removes the temporary draft, and binds the exact source selection and snapshot into the external publication receipt. This mode is intended for ordinary Python, HTML, JavaScript, Rust, Go, documentation, test, and similar implementation trees that do not require a profile-specific semantic descriptor.

Example:

```text
bbk artifact finalize --root . --package-id omp-session-inspector \
  --revision 1
```

**Draft mode** accepts `DRAFT_ROOT` and retains the profile-specific descriptor workflow introduced in alpha.16.

Both modes run deterministic preflight, seal to an immutable project-local output, verify the exact stored tree, then publish external metadata without modifying the sealed package. With no explicit output, the target is:

```text
<project>/.bbk/artifacts/sealed/<packageId>-<revision>/
```

The immutable publication receipt is written to `.bbk/artifacts/publications/<packageId>-<revision>.json`. Unless `--no-current-pointer` is supplied, the mutable selector is written to `.bbk/artifacts/current/<packageId>.json`. Neither metadata path may be inside the sealed package.

Finalization rejects common live coordination/status artifacts by default, including status, current, readiness, and package-index records recognized by exact path or schema vocabulary. Move mutable projections outside the draft. `--allow-mutable-coordination` is an explicit override for an intentionally immutable snapshot; it is not a repair shortcut.

Finalization serializes revisions that share one package ID, refuses to overwrite an existing publication receipt, verifies before and after external metadata publication, and restores the prior current pointer plus removes the new publication receipt if publication fails. A successfully sealed directory can remain as an unadvertised immutable output after metadata failure; inspect or quarantine it before retrying with a successor revision.

A finalize `PASS` establishes `BYTE_INTEGRITY_VERIFIED` only. It does not establish semantic acceptance, authorization, independent review, deployment readiness, live acceptance, or release authority.

When a user explicitly requires `bbk artifact finalize`, a sealed handoff, passing tests, a raw implementation directory, or `artifact seal` does not satisfy that requirement. A successful final relay must bind the actual finalization publication receipt.

### `freshness`

Verifies the immutable package named by a publication receipt, current pointer, or sealed directory. When the publication was created in one-shot software mode, it also reconstructs the bound source selection from the live project and compares exact paths, byte lengths, and SHA-256 values with the publication snapshot. Any added, removed, or changed selected source makes the result `REJECTED` with `PACKAGE_FINALIZATION_SOURCE_STALE`.

Run freshness immediately before reporting completion:

```text
bbk artifact freshness .bbk/artifacts/publications/omp-session-inspector-1.json --root .
```

Freshness is a local byte-evidence check. It does not rerun tests, review, or semantic validation.

### `verify`

Recomputes exact file identity, manifest identity, content identity, strict JSON and schema validity, profile semantics, file closure, and artifact-reference closure. It records the file set before and after verification and rejects observed concurrent mutation. A pass should report `readOnly: true`.

### `successor`

Requires a verified predecessor, preserves `packageId`, requires a different revision and non-empty reason, copies declared artifacts into a new absent mutable draft, writes exact predecessor identity, and clears profile-defined attempt-owned pointers. It does not preflight or seal the successor automatically.

Profile-specific successor clearing includes:

- `handoff-v2`: `/attempt`, `/continuation/checkpoint`
- `role-return-v2`: `/attempt`, `/generated_at`, `/effects/attempt_owned`
- `worker-context-v1`: `/admission`, `/hostPreflight/cache`
- `review-package-v2`: `/attempt`, `/findings`
- `generic` and `candidate-package-v1`: no automatic semantic pointer clearing

Inspect and complete the successor draft, then preflight and seal it to another absent path.

### `inspect`

Reports exact identity for one physical file, symlink, or directory. Directory inspection excludes shipped examples unless `--include-examples` is explicit. Inspection does not create a sealed package.

### `manifest`

Builds the legacy `bbk.artifact-manifest.v1` compatibility format over selected files. Use it only when the caller explicitly needs the legacy flat manifest. It does not provide the sealed package lifecycle or predecessor binding.

## Failure classifications

- `MECHANICAL`: exact syntactic, path, hash, schema, or package-shape defect. Repair only within current mutation authority.
- `SEMANTIC_OWNER_REQUIRED`: profile, subject, schema meaning, identity binding, or other semantic ownership must be resolved by the responsible role or user.
- `AUTHORITY_REQUIRED`: concurrent mutation, unsafe recovery, ownership, permission, or scope requires an authority decision.

Use the first material finding's `remediation` or `smallest_next_action`; do not hide remaining findings or reinterpret a rejected operation as success.
