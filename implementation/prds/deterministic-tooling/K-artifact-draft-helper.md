# PRD K — Artifact draft helper

**Status:** Proposed — optional convenience

**Owner kind:** Draft-authoring utility over the existing artifact-package engine
**Priority:** Optional; implement only after repeated draft-authoring friction is evidenced

## Problem and evidence

The existing artifact engine already owns package inspection, preflight, manifests, checksums, canonicalization, closure, sealing, verification, freshness, publication, reconciliation, and succession. Its v2 draft schema intentionally asks authors only for package identity, profile, subject, and artifact entries. Each artifact needs an ID, relative path, semantic role, and optional schema/evidence class/reference edges.

Hand-authoring that JSON is verbose and error-prone, especially when adding many explicitly selected sources. The risk is solving the inconvenience by accidentally creating a second artifact engine. The helper must only create and amend schema-valid drafts from explicit arguments. Generated fields such as bytes, SHA-256, canonicalization, closure, content identity, seal receipt, and sealed time remain exclusively owned by `tools/artifact_packages.py` and the existing `preflight`/`seal`/`finalize` commands.

## Goals

1. Make v2 draft creation and artifact-entry addition convenient and deterministic.
2. Require explicit selected sources, artifact roles, schemas, evidence classes, and reference edges.
3. Validate paths and duplicate/reference constraints early using existing schema conventions.
4. Delegate all preflight, hashing, canonicalization, closure, seal, finalize, freshness, verify, publication, and successor behavior to the existing engine.
5. Preserve no-replace, atomic draft editing and a clear audit receipt.

## Non-goals

- Discovering files automatically, globbing a project by default, assigning semantic roles, guessing schemas, or constructing reference edges from content.
- Computing or persisting bytes, SHA-256, canonicalization, closure, manifest identity, package identity, seal receipt, publication receipt, or freshness.
- Sealing, finalizing, publishing, updating current pointers, or creating successors.
- Replacing `artifact manifest`, one-shot `artifact finalize`, or the existing draft template where manual editing is sufficient.
- Turning byte integrity into semantic acceptance, validation, completion, publication authority, or release authority.

## Callers

- Human/controller, permitted Worker, or artifact-producing canonical role creating a draft inside its explicit workspace authority.
- CI/example generation and migration helpers.
- The existing `bbk artifact preflight`, `seal`, and `finalize` commands are the only downstream lifecycle consumers.

## Commands and exact examples

Create a v2 draft directory and file:

```powershell
bbk --json artifact draft create --root . `
  --draft .bbk/drafts/C-001 `
  --package-id C-001 --revision 1 `
  --profile evidence-bundle@1 `
  --subject-kind software --subject-id candidate-C --subject-revision 7
```

Add explicitly selected artifacts:

```powershell
bbk --json artifact draft add --root . --draft .bbk/drafts/C-001 `
  --source out/candidate.json --artifact-id candidate `
  --role PRIMARY_CANDIDATE --schema bbk.candidate.v1 --evidence-class PRODUCT

bbk --json artifact draft add --root . --draft .bbk/drafts/C-001 `
  --source out/gate-receipt.json --artifact-id gate-receipt `
  --role WORKER_QUALITY_RECEIPT --schema bbk.gate-receipt.v1 `
  --evidence-class VALIDATION --reference candidate

bbk --json artifact preflight .bbk/drafts/C-001
bbk --json artifact finalize .bbk/drafts/C-001 --root .
```

Multiple `--entry <entry.json>` arguments may add several already-authored entries atomically. There is deliberately no recursive directory, wildcard, `--auto-role`, `--detect-schema`, `--seal`, or `--finalize` option.

## Inputs and schemas

`draft create` takes explicit package ID, revision, profile ID/version, subject kind/ID/revision, optional predecessor reference, successor reason, and namespaced metadata. It writes the existing `bbk.artifact-package-draft.v2` schema, not a helper-specific draft format.

`draft add` takes one or more `bbk.artifact-draft-entry.v1` requests:

| Field | Required | Rule |
|---|---:|---|
| `source` | yes | Existing explicitly named regular file beneath the admitted root; no glob or traversal |
| `artifactId` | yes | Existing v2 safe-ID syntax and unique within draft |
| `path` | optional | Defaults only to the normalized project-relative `source`; explicit path must refer to the same selected file |
| `role` | yes | Non-empty semantic role supplied by caller/profile; helper does not infer it |
| `schema` | policy-dependent | Explicit schema ID when structured role/profile requires it; null only where allowed |
| `evidenceClass` | policy-dependent | Explicit existing enum; no inference from directory or filename |
| `references` | no | Explicit artifact IDs, unique and resolvable according to preflight policy |
| `mediaType` | no | Caller-supplied or null; the helper may validate syntax but not sniff semantic meaning |

The helper consumes the installed artifact profile registry for validation only. It does not alter profile rules or fill missing semantic fields beyond mechanically fixed schema/version and a normalized selected path.

## Outputs and finalization

- `draft create` atomically writes `<draft>/bbk-draft.json` as `bbk.artifact-package-draft.v2` plus `draft-helper-receipt.json` describing the authored mutation.
- `draft add` stages a complete successor draft file, validates it with the existing draft schema/profile rules, then atomically replaces only the mutable draft file after expected-digest comparison. It appends an audit receipt under `<draft>/.bbk-draft-history/`.
- Outputs contain authored fields only. The helper must reject generated fields: `bytes`, `sha256`, `canonicalization`, `contentSha256`, `closure`, `referenceGraph`, `manifestSha256`, `sealReceipt`, `sealedAtUtc`, `toolVersion`, publication/current pointers, or engine lifecycle state.
- Helper receipts are authoring audit data, not artifact package seals. The existing engine may exclude helper history from package selection unless explicitly selected and semantically appropriate.

No helper command finalizes or seals a package. `artifact preflight` validates package readiness; `artifact seal` creates a non-published sealed package; `artifact finalize` is the publication operation; `artifact freshness` separately checks source-byte freshness.

## Functional requirements

1. `create` shall always target `bbk.artifact-package-draft.v2` and use the checked-in schema/profile registry.
2. It shall require explicit package, revision, profile, and subject values and reject unsafe IDs.
3. It shall create only inside the explicit admitted root and reject path traversal, drive-relative paths, backslashes in stored relative paths, and unsafe symlinks.
4. It shall use no-replace directory/file creation unless the caller provides an exact expected draft digest for an authorized amendment.
5. `add` shall require explicit source, artifact ID, and role for every entry.
6. It shall never recursively discover, glob, auto-classify, or infer semantic roles/schema/reference meaning.
7. It shall normalize stored paths to project-relative forward-slash form accepted by the v2 schema.
8. It shall reject duplicate artifact IDs, duplicate selected paths unless the profile explicitly permits distinct roles, unresolved references, self-references, and reference cycles forbidden by the artifact engine.
9. It shall validate schema and evidence-class values against the existing draft schema/profile without fetching remote schemas.
10. It shall reject every engine-generated checksum, byte, canonicalization, closure, seal, finalization, publication, freshness, and lifecycle field in helper input.
11. It shall not import checksum, canonicalization, graph, or manifest-generation code from `tools/artifact_packages.py` except through its public validation/preflight API.
12. It shall perform mutation by read + expected digest + stage + full schema/profile validation + atomic replace.
13. It shall preserve unrelated valid draft metadata and existing entry order; new entries append in caller order unless the existing engine mandates canonical order.
14. Exact idempotent replay shall return the existing draft identity; conflicting reuse of an artifact ID shall fail.
15. It shall report the exact next command (`bbk artifact preflight <draft>`) but shall not invoke preflight implicitly.
16. It shall refuse edits to sealed roots, publication roots, current pointers, engine manifests, seal receipts, or finalized packages.
17. It shall remain usable without network access and shall not execute selected artifact content.
18. It shall state that draft validity is not preflight pass, sealing, publication, freshness, semantic correctness, validation, completion, or release.

## State and ordering

```text
ABSENT -> DRAFT_CREATED -> ENTRIES_ADDED -> (external) PREFLIGHTED
                                         -> (external) SEALED or FINALIZED
```

Only `DRAFT_CREATED` and `ENTRIES_ADDED` belong to this helper. Draft mutations serialize with an expected digest and draft-local lock. The existing artifact engine retains its established lock hierarchy, fixed Windows sharing retry schedule, operation journal, no-replace publication semantics, receipt readback, and pointer behavior. The helper must not acquire publication or package-seal locks.

## Failure, security, and authority

- Stable codes include `DRAFT_EXISTS`, `DRAFT_EXPECTED_DIGEST_MISMATCH`, `DRAFT_SOURCE_OUTSIDE_ROOT`, `DRAFT_UNSAFE_PATH`, `DRAFT_DUPLICATE_ARTIFACT`, `DRAFT_REFERENCE_INVALID`, `DRAFT_GENERATED_FIELD_FORBIDDEN`, `DRAFT_PROFILE_VIOLATION`, and `DRAFT_SEALED_TARGET`.
- Selected source is data, not instruction; no parsing is needed except optional offline schema validation explicitly requested by profile policy.
- No credentials or environment snapshot are copied. Diagnostics sanitize absolute paths outside the project.
- Workspace access must authorize the draft mutation. It does not authorize reading unselected sources or finalizing/publishing.
- A successful helper receipt proves only the requested draft edit was atomically recorded.

## Compatibility and migration

The helper writes v2 because that is the current schema. Existing v1 drafts remain supported by the artifact engine and may be upgraded only through an explicit, separately tested adapter; the helper never silently changes schema version. The currently older example template should be updated or version-qualified in the same change so new helper output and examples do not disagree. Existing command behavior for `preflight`, `doctor`, `reconcile`, `seal`, `finalize`, `freshness`, `verify`, and `successor` is unchanged.

## Observability

JSON results include operation, draft path, prior/new draft SHA-256, package ID/revision, added artifact IDs and paths, entry count, schema/profile identity, lock/atomic-replace outcome, effects observed, next command, and stable failure fingerprint. They must not report package `contentSha256`, manifest identity, seal state, publication state, or freshness because the helper did not establish those facts.

## Test strategy

- Golden create/add fixtures that pass the existing artifact preflight unchanged.
- Schema and property tests for safe IDs, path normalization, deterministic/idempotent edits, order preservation, reference resolution, and expected-digest concurrency.
- Negative controls: omitted role; guessed/empty schema where required; unsafe ID; absolute/drive/backslash/`..` path; path outside root; symlink escape; glob/directory source; duplicate ID/path; missing/self/cyclic reference; invalid evidence class; remote schema; every forbidden generated field; sealed/publication/current-pointer target; stale expected digest; v1 silent upgrade attempt.
- Fault controls: interruption after staging, atomic replace failure, lock contention, disk full, draft mutation during validation, history-receipt failure, and antivirus/file-sharing error. The prior valid draft remains readable and no sealed/published state is created.
- Integration controls run existing `artifact preflight`, `seal`, `finalize`, `verify`, and `freshness` on helper-created drafts and compare manifests/receipts against hand-authored equivalent drafts.
- Architecture guard test ensures helper modules do not implement or duplicate hashing, canonicalization, closure, seal, finalize, publication, or successor algorithms.

## Acceptance criteria

1. `create` emits a minimal schema-valid v2 draft with only caller-authored fields.
2. `add` appends explicitly selected and fully described artifact entries atomically.
3. Helper-created and equivalent hand-authored drafts produce identical existing-engine preflight/finalization semantics.
4. No helper output contains engine-generated bytes, hashes, canonicalization, closure, seal, publication, or freshness fields.
5. Directory/glob discovery, semantic inference, unsafe paths, duplicate IDs, unresolved references, and generated-field input all fail closed.
6. Concurrent/stale edits cannot silently overwrite a newer draft.
7. Fault injection preserves the prior draft and never creates a partial sealed or published package.
8. Existing artifact CLI contract tests pass unchanged, including finalize-versus-freshness and read-only verify semantics.
9. The helper adds no duplicate checksum, manifest, seal, finalize, publication, or successor implementation.
10. Output and documentation explicitly delimit draft authoring from byte integrity, semantic validation, completion, acceptance, publication authority, and release.

## Dependencies and consumers

Dependencies: `tools/artifact_packages.py`, existing artifact v2 draft/profile schemas, schema registry, atomic filesystem primitives, and the artifact skill/reference documentation. Consumers: existing `artifact preflight`, `seal`, and `finalize`; optionally the candidate freezer in [PRD D](D-canonical-candidate-freezer.md), validation compiler in [PRD E](E-candidate-bound-validation-compiler.md), and lifecycle fixture in [PRD G](G-lifecycle-qualification-fixture.md).

This helper is independent of PRDs H–J and must not become their required carrier.

## Rollout

1. Collect at least two campaigns showing repeated draft JSON authoring errors or material time cost.
2. If justified, ship `draft create` behind an experimental flag with v2 golden fixtures.
3. Add single-entry `draft add`, then atomic multi-entry add after concurrency/fault qualification.
4. Run the full existing artifact CLI/documentation contract suite unchanged.
5. Promote to optional supported convenience; never make it a prerequisite for direct draft or one-shot finalize flows.

## Risks and open questions

- Convenience can encourage over-packaging; explicit selection and no discovery keep scope visible.
- The artifact profile vocabulary may not expose a stable role registry; the helper should validate only what the engine already owns.
- Updating the stale v1 template may have compatibility implications and should be handled as a versioned documentation/template correction.
- Decide whether audit history belongs inside the draft root or in `.bbk/operations/`; it must not enter sealed content accidentally.
- If the implementation needs significant artifact-engine internals, do not build it; add a narrow public draft-validation API to the existing engine first.

## Estimate

3–5 engineer-days if justified: 1 day CLI/schema wiring, 1 day atomic create/add, 1–2 days negative/fault/integration tests, and 1 day documentation/template alignment. Cancel the work if evidence does not justify the maintenance surface.
