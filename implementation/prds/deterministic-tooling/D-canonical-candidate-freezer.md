# PRD D — Canonical candidate freezer

**Status:** Proposed

**Owner kind:** deterministic tooling maintainer; semantic owner remains the invoking orchestrator
**Priority:** Required

## Problem and repository evidence

BBK already defines `bbk.candidate-package.v1`, registers the `candidate-package-v1` artifact profile, and provides canonical preflight, seal, verify, freshness, and successor primitives in `tools/artifact_packages.py` through `tools/bbk.py`. `tools/review_assurance.py` can identify a lightweight file set, but that is not a consequential candidate freeze. Today there is no single command that locks an admitted workspace before inventory, proves prerequisite gates, inventories every candidate-affecting class, seals exactly one canonical package, and returns one stable `CandidateRef`.

That gap allows inventory races, partial candidate descriptions, mismatched review subjects, and post-freeze mutations to be mistaken for the admitted candidate. This PRD upgrades candidate freeze without creating a second checksum or package engine. It depends on [PRD C](C-gate-receipt-aggregation.md) and supplies the exact candidate used by [PRD E](E-candidate-bound-validation-compiler.md), [PRD F](F-completion-readiness-compiler.md), and [PRD G](G-lifecycle-qualification-fixture.md).

## Goals

- Lock before reading the first inventory byte and hold the lock through post-seal recomputation.
- Admit exactly one current, passing [PRD C](C-gate-receipt-aggregation.md) aggregate for the same execution lineage.
- Inventory source, generated output, configuration, tools, dependencies, and relevant environment observations.
- Produce one sealed canonical `candidate-package-v1` artifact package and one detached freeze receipt containing the sole `CandidateRef`.
- Detect post-inventory or post-freeze mutation, and record explicit invalidation without rewriting history.

## Non-goals

- Judging semantic correctness, accepting findings, authorizing validation, deployment, publication, or release.
- Replacing `tools/artifact_packages.py`, changing BBK-JSON-1, or inventing a second package format.
- Freezing remote state that has not been materialized under admitted authority.
- Treating a source VCS revision alone as the identity of generated, configured, or environment-dependent bytes.

## Callers

- `bbk_worker_orchestrator` after candidate-producing integration and worker-quality gates.
- `bbk_territory_orchestrator` when admitting a candidate for independent validation.
- Deterministic qualification fixtures and recovery tooling checking currentness or invalidation.

## Command surface and exact examples

```powershell
python tools/bbk.py candidate freeze --workspace .bbk/workspaces/integrated-17 --inventory candidate-inventory.json --gate-aggregate .bbk/gates/aggregate.json --execution-admission .bbk/admission/receipt.json --package-id CAND-17 --revision r1 --output .bbk/candidates/CAND-17-r1
python tools/bbk.py candidate verify --candidate-ref .bbk/candidates/CAND-17-r1/candidate-freeze-receipt.json
python tools/bbk.py candidate invalidate --candidate-ref .bbk/candidates/CAND-17-r1/candidate-freeze-receipt.json --cause POST_FREEZE_MUTATION --evidence .bbk/evidence/mutation.json --output .bbk/candidates/CAND-17-r1/invalidation-001.json
```

`freeze` delegates package construction and sealing to the existing artifact implementation. `verify` is read-only. `invalidate` appends a detached record and never edits the sealed package or freeze receipt.

## Inputs and schemas

- Admitted workspace root and its current lock/admission identity from [PRD A](A-execution-admission-compiler.md).
- Current `bbk.gate-aggregate.v1` from [PRD C](C-gate-receipt-aggregation.md), with a passing disposition and matching execution/candidate-input identity.
- Operator-authored inventory declaration whose entries are normalized into six required classes: `source`, `generated`, `configuration`, `tools`, `dependencies`, and `environment`.
- Existing `bbk.candidate-package.v1` semantic descriptor and artifact draft/profile `candidate-package-v1`.
- Optional authority record references; references prove what grant was supplied, not that the tool grants authority.

The inventory schema must require normalized relative paths or explicit non-file observations, role/class, byte inclusion policy, source of truth, and invalidation key. File entries carry byte count and SHA-256. Dependency and tool entries carry the resolved executable/package identity and lockfile or equivalent evidence. Environment entries are an allowlisted, redacted observation set; secrets and ambient environment dumps are forbidden.

`CandidateRef` is a value object, not another manifest: `{candidate_id, revision, package_root, content_sha256, manifest_sha256, freeze_receipt_sha256}`. Every downstream record must reproduce all six values exactly.

## Outputs and finalization

- A sealed artifact package using profile `candidate-package-v1`, containing `bbk.candidate-package.v1`, normalized inventory, admitted prerequisite receipts, and selected candidate bytes.
- A detached, atomically finalized `bbk.candidate-freeze-receipt.v1` containing the sole `CandidateRef`, lock identity, pre/post inventory roots, C aggregate identity, execution-admission identity, tool identity, inventory-class coverage, timestamps, and claims-not-established.
- Optional immutable `bbk.candidate-invalidation.v1` successor records.

The freeze receipt must remain outside the package so content never inventories its own digest. Publication of the output directory occurs only after artifact seal verification and a second inventory recomputation match. Partial staging is not a candidate.

## Functional requirements

1. Resolve the workspace and every selected path beneath the admitted root before mutation or hashing.
2. Acquire the existing workspace/substrate lock before inventory traversal; refusal or contention fails before reading candidate content.
3. Verify [PRD A](A-execution-admission-compiler.md) identity and [PRD C](C-gate-receipt-aggregation.md) signature/digest/currentness; accept only the configured pass state, never missing, inconclusive, required-not-run, or advisory-as-pass evidence.
4. Require all six inventory classes. A legitimately empty class must have an explicit `NOT_APPLICABLE` reason and governing source, not silent omission.
5. Normalize paths, reject links or traversal escaping the root, sort entries deterministically, and reject duplicates or class ambiguity.
6. Copy selected bytes into an isolated staging root while locked, then recompute and compare every source identity before sealing.
7. Build the semantic `bbk.candidate-package.v1` descriptor and use the registered artifact profile and existing preflight/seal/verify functions.
8. Emit exactly one CandidateRef derived only from verified package outputs; aliases or mutable `current` pointers are not CandidateRefs.
9. Recompute the source inventory and sealed package identities after seal verification and before releasing the lock.
10. Publish package and receipt atomically; on any failure, leave only diagnosed staging state outside the canonical output.
11. `candidate verify` must verify the freeze receipt, artifact package, manifest closure, referenced prerequisites, and absence of a current invalidation record.
12. `candidate invalidate` must require an existing CandidateRef, typed cause, evidence reference, caller authority reference, and monotonic record identity; it must not delete bytes or imply a successor is valid.
13. Repeated freeze with identical normalized inputs must either return the byte-identical existing CandidateRef or fail on conflicting output; it must not silently mint competing identities.

## State and ordering

`REQUESTED -> LOCKED -> PREREQUISITES_VERIFIED -> INVENTORIED -> STAGED -> SEALED -> RECOMPUTED -> PUBLISHED -> UNLOCKED`.

Any mutation or identity mismatch before publication transitions to `ABORTED` and then `UNLOCKED`. A published candidate may transition only by detached record to `INVALIDATED`; it is never rewritten back to current. A replacement is a new candidate revision with explicit predecessor lineage.

## Failure semantics

Malformed input, wrong subject, stale aggregate, lock loss, missing class, path escape, unreadable file, mutation during copy, package preflight/seal/verify failure, post-seal mismatch, or publication collision is a typed non-zero failure. The tool must release a lock it owns after recording the failure, preserve immutable prerequisite evidence, and report whether staging cleanup is clean, residual, or blocked. It must never return CandidateRef on a partial run.

## Security and authority

Workspace admission and lock ownership bound read/write scope. Symlinks, junctions, case-fold collisions, alternate data streams where applicable, and resolved paths are checked before inclusion. Environment capture is allowlist-only and secret names/values are redacted or rejected. The freezer executes no discovered candidate tool and performs no network access. Supplied authority records are validated for identity and scope; the command cannot widen them or infer approval from filesystem access.

## Compatibility and migration

Keep `bbk.candidate-package.v1` and artifact profile `candidate-package-v1` as the package contract. The new freeze receipt is additive and detached. Existing sealed candidate packages remain readable but are not automatically promoted to canonical CandidateRefs; migration requires an explicit re-freeze or a provenance-preserving import that proves the same six inventory classes and prerequisite aggregate. Historical artifacts are never rewritten.

## Observability

Structured output records state, duration, lock identity, counts/bytes by inventory class, package and receipt digests, prerequisite refs, recomputation result, invalidation state, cleanup state, and a stable failure fingerprint. Logs must not include candidate file contents or secret environment values.

## Test strategy

Unit tests cover normalization, ordering, CandidateRef derivation, empty-class declarations, and state transitions. Integration tests use the real artifact package engine and atomic finalizer on Windows and POSIX path behavior. Concurrency tests mutate a file after lock admission and during staging. Negative/fault controls cover stale C aggregate, wrong execution identity, lock theft/loss, duplicate/case-colliding paths, symlink/junction escape, missing generated/config/tool/dependency/environment classes, seal failure, output collision, post-seal source mutation, receipt tamper, and invalidation replay. A fault injected between seal and publication must yield no discoverable canonical CandidateRef.

## Acceptance criteria

1. A valid fixture produces one verifiable CandidateRef and a sealed `candidate-package-v1` package with all six inventory classes.
2. The first candidate byte is not inventoried before a workspace lock is acquired.
3. Missing, stale, wrong-subject, inconclusive, or non-pass C aggregate blocks freeze.
4. Mutation at any point through final recomputation blocks publication.
5. Package verification uses existing artifact tooling and produces no alternative hash/manifest implementation.
6. The detached receipt can be verified without creating a self-reference cycle.
7. Invalidation preserves the original package and causes subsequent `candidate verify` currentness checks to fail closed.
8. No successful result claims semantic acceptance, validation success, deployment readiness, or release authority.

## Dependencies and consumers

Dependencies: [PRD A](A-execution-admission-compiler.md), [PRD C](C-gate-receipt-aggregation.md), `tools/atomic_finalizer.py`, `tools/artifact_packages.py`, `spec/contracts/artifact-package-profile-registry.json`, and `spec/schemas/bbk-candidate-package-v1.schema.json`.

Consumers: [PRD E](E-candidate-bound-validation-compiler.md), [PRD F](F-completion-readiness-compiler.md), [PRD G](G-lifecycle-qualification-fixture.md), existing review-context compilation, Validators, and recovery tooling.

## Rollout

Add schemas and read-only verification first, then freeze behind an opt-in CLI flag. Run dual fixtures against current artifact packages, enable canonical CandidateRef for consequential validation, and finally require it at completion reconciliation. Retain legacy read compatibility during the transition.

## Risks and open questions

- Platform-specific link and file-change detection may require native identity metadata in addition to content hashes.
- Environment inventory must stay narrow enough to avoid secrets while capturing actual invalidation dependencies.
- Decide whether invalidation indexing belongs beside the candidate or in existing governed coordination storage; either choice must remain append-only and deterministic.
- Lock integration must use the repository’s existing substrate/workspace semantics rather than a second lock authority.

## Estimate

8–12 engineer-days: schemas and CLI 3–4, artifact/lock integration 3–4, cross-platform and fault tests 2–4.
