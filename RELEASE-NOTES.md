# BBK 0.1.0-alpha.15 release notes

Alpha.15 is a product-first workflow, deterministic packaging, project-routing, and generated-context release over alpha.14. It reduces routine coordination ceremony while preserving BBK's existing 19-role topology, exact reviewed model routes, install scopes, language-profile reuse, Windows path handling, Beads behavior, and Blueprint boundary.

## Product-first proportional assurance

Four canonical prompt modules now govern the routine workflow across the relevant planning, execution, and assurance roles:

- `bbk-prompt-product-first-proportionality`
- `bbk-prompt-mechanical-admission`
- `bbk-prompt-assurance-modes`
- `bbk-prompt-candidate-focused-review`

Work is organized around actor-visible capability increments with stable interfaces and independent mutation/evidence scopes. Mechanical defects are repaired or rejected at the smallest responsible scope; they do not automatically commission architecture, research, planning, independent review, or user authorization.

Assurance now uses three explicit modes:

- **INLINE** — the routine default for local, reversible, adequately evidenced work;
- **FOCUSED** — an exact material risk, candidate scope, or finding-scoped recheck; and
- **FULL** — consequential boundaries, material external effects, complex recovery, authority ambiguity, interrupted attempts, or an explicit parent request.

Independent review normally targets an integrated candidate or an exact material risk. A repair recheck is limited to the finding, successor candidate, affected scope, relevant evidence, and reopening triggers unless semantics changed materially.

## Deterministic artifact packages

Alpha.15 adds one canonical strict-JSON and artifact-package implementation under `tools/strict_json.py` and `tools/artifact_packages.py`. `tools/bbk_artifact.py` is a thin adapter to the same implementation.

The strict loader rejects duplicate keys, invalid UTF-8, forbidden BOMs, non-finite values, malformed JSON, trailing data, and configured excessive depth with structured diagnostics.

The package engine provides:

```text
bbk artifact preflight <draft-directory>
bbk artifact seal <draft-directory> --output <sealed-directory>
bbk artifact verify <sealed-directory>
bbk artifact successor <sealed-directory> --output <draft-directory> \
  --revision <revision> --reason <reason>
```

`BBK-JSON-1` defines exact stored JSON bytes. JSON artifacts are canonicalized before publication; non-JSON artifacts retain their exact bytes. Generated digests, byte lengths, canonicalization labels, package closure, and seal receipts are tool-owned rather than agent-authored.

Seal uses an exclusive lock, a staged package, complete verification, and atomic publication to a new target. It refuses overwrite. Verification is read-only. Successor creation preserves the immutable predecessor package and binds the new draft to its predecessor identity and digest.

The package profile registry separates generic, handoff, role-return, candidate, review, and worker-context semantics. It distinguishes valid recursive schema references from prohibited artifact-reference cycles and applies profile-specific checks before expensive review.

Legacy `bbk artifact manifest/verify` remains available. Existing v1 records remain consumable.

## Project-local OMP routing creation and repair

A user-scoped OMP installation can now create a project-scoped routing installation directly from `/bbk:models`, including in an existing empty non-Git directory:

```text
/bbk:models project create
/bbk:models project create D:\Projects\Machine-A
/bbk:models project status
/bbk:models project repair --dry-run
/bbk:models project repair
/bbk:models project profile testing-flash
```

Creation clones the exact effective user OMP routes into an authenticated temporary `bbk.model-routing.v2` policy and invokes the sibling BBK installer with project scope, OMP only, and no language-profile installation. All 19 project routes are verified. User routing files, agents, binding, and manifest remain byte-identical.

Partial, divergent, or mis-scoped project installations fail closed with an explicit repair path. Repair shows the dry-run plan first and backs up modified manifest-owned files when applied. Neither path initializes Git or `.bbk`, and neither silently falls back to user-global mutation. OMP must be reloaded or restarted in the project after creation or repair.

The packaged `default`, `testing-flash`, and `deepseek-economy` profiles and all 19 reviewed default model routes are unchanged.

## Role-return v2

`bbk.role-return.v2` is now the generated producer default for all 19 roles. It supports two detail modes:

- **COMPACT** uses a generated role-specific compact result schema and omits irrelevant empty sections while preserving core truth, evidence, effects/cleanup, blockers/residuals, prohibited claims, and exact next action.
- **FULL** uses the existing authoritative role-specific result schema for consequential or explicitly requested detail.

The v2 registry, common envelope, 19 compact schemas, and 19 role-return schemas are generated from canonical role sources. `bbk.role-return.v1` schemas, registry, validation, and consumption remain available during the compatibility transition.

## Generated Worker and review contexts

Routine Worker invocation packages are now compiled mechanically from a complete WorkUnit, governing references, authority, profile lock, exact host-preflight result, and output contract:

```text
bbk context worker --root <project> \
  --work-unit <work-unit.json> \
  --profile-lock <profile-lock.json> \
  --host-preflight <preflight-result.json> \
  --output <worker-package-directory>
```

The compiler validates canonical inputs and seals the resulting `worker-context-v1` package. It does not invent missing semantics. A nonstandard or incomplete request returns `SPECIALIST_DESIGN_REQUIRED`, preserving Worker Designer as the semantic owner. Required host failures are reported as `BLOCKED_BY_HOST_PREFLIGHT`.

Review packages are generated from an exact verified candidate package and a review request:

```text
bbk context review --root <project> \
  --candidate <candidate-package-directory> \
  --request <review-request.json> \
  --output <review-package-directory>
```

The compiler supports ordinary review and focused recheck. Reviewers consume the generated mechanical context rather than authoring the manifest that admits their own subject.

## Requirement-scoped host preflight

Host preflight accepts a canonical request and inspects only plan-named capabilities:

```text
bbk preflight run <request.json> --root <project> --output <result.json>
```

Read-only probes cover command, path, environment, and explicitly declared live checks. Results use `AVAILABLE`, `UNAVAILABLE`, `VERSION_MISMATCH`, `PERMISSION_BLOCKED`, `UNKNOWN`, or `REQUIRES_LIVE_PROBE` and are bound to exact host identity, requirements digest, tool identity, and freshness horizon. Cached observations are evidence only; they do not grant execution authority.

## Compact and full prototype charters

`bbk.prototype-charter.v2` adds COMPACT and FULL prototype modes without adding a role. COMPACT requires one material uncertainty, one parent decision, a decision threshold, bounded time/effect budget, guaranteed fallback, evidence commitment, and cleanup/disposition. FULL retains the larger apparatus for consequential experiments. The Prototyper remains a bounded coordinator and may invoke only Worker Designer and Worker.

## Sealed handoff v2

New handoff creation defaults to a sealed `bbk.handoff.v2` package. Generated byte counts and digests are package-engine output rather than CLI input:

```text
bbk handoff create --root <project> --work-unit <id> \
  --disposition COMPLETE --summary "..." --next-action "..."
bbk handoff verify <sealed-handoff-directory> --root <project>
bbk handoff list --root <project>
```

Legacy `bbk.handoff.v1` files remain readable, verifiable, listable, and usable by Beads. Use `--legacy-v1` only when an explicit v1 producer is required. Beads emits the same compact verified pointer for either format.

## OMP surface

The OMP extension now exposes direct tools and slash commands for package preflight/seal/verify/successor, host preflight, Worker/review context generation, and handoff create/verify/list. The extension contains 42 tools and 45 commands after alpha.15 generation. Command payloads remain outside the model prompt boundary.

## Compatibility and migration

No `.bbk` project-record migration is required solely for alpha.15. Existing v1 handoffs, role returns, artifact manifests, model-routing policies, and review records remain consumable. New constructors prefer v2 sealed packages and v2 role returns.

Use a clean extraction and managed install/update paths. Do not overlay release source directories. Reload OMP plugins and start fresh Codex/Claude parent sessions after installing regenerated projections.

Alpha.15 deliberately does **not** add a global acceptance, authorization, candidate, review-invalidation, release, ACL, lease, or lifecycle state machine. It does not add a canonical role or change default routing. Those deterministic lifecycle responsibilities remain Blueprint concerns.

## Repository-native source

The extracted archive remains **Repository-native source**: canonical specifications, deterministic generators, tests, current documentation, and package metadata are present without an external migration step. The `docs/` directory contains **15 current** public-facing documents. Full qualification transcripts, archive audits, and **pre-public history** are separate release artifacts rather than runtime dependencies. **No `.bbk/` project-record migration** is required solely for alpha.15.

## Qualification boundary

The release is qualified from its source tree and a fresh archive extraction, with deterministic rebuild and exact alpha.14 patch reconstruction checks. Native Windows, live OMP 16.4.8 execution, and a production `bd` executable were not available in the Linux qualification environment; their behavior is covered by deterministic, JavaScript syntax, path-alias, installer, and Beads compatibility tests rather than direct live-host operation.

### Windows symlink-test portability correction

The reissued alpha.15 package no longer assumes that the presence of `os.symlink` means a non-elevated Windows process has permission to create symbolic links. Artifact-package rejection is now covered by a deterministic privilege-independent unit test on every host, plus a real-link integration test that skips only when the operating system or test process denies link creation. Shared test support and a source audit reject future unguarded symlink fixtures. Runtime artifact-package behavior is unchanged.
