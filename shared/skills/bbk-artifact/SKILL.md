---
name: bbk-artifact
description: Create, preflight, finalize, seal, verify, inspect, manifest, or revise BBK artifact packages with the installed BBK artifact-package engine. Use when exact artifact bytes, declared reference closure, immutable publication, tamper detection, or predecessor-bound successors matter. Do not treat a passing package check as semantic acceptance, authorization, validation, deployment readiness, or release authority.
requires_prompt_modules: []
standalone_prompt_modules: []
---

# BBK artifact packages

Use the deterministic BBK package engine for package identity, strict JSON handling, canonicalization, byte counts, hashes, manifests, receipts, closure checks, immutable publication, verification, and successors. Do not replace it with ad hoc hashing, copying, archive creation, or hand-authored generated fields.

## Preserve the authority boundary

A successful seal or verification proves exact stored bytes and declared local reference closure. It does not establish semantic correctness, acceptance, authorization, independent review, validation, deployment readiness, completion, or release authority. This skill does not expand the current role's scope, filesystem authority, network authority, or approval rights.

## Invoke BBK when `bbk` is not on `PATH`

Use the wrapper bundled with this skill instead of the short `bbk` command.

On Windows, resolve this skill's actual directory from the `SKILL.md` path shown by Codex, then run:

```powershell
& "<skill-directory>\scripts\bbk-artifact.cmd" binding
& "<skill-directory>\scripts\bbk-artifact.cmd" --help
```

Replace `<skill-directory>` with the real directory; never pass the placeholder literally. Normal user-scope locations are:

```powershell
# Codex
$BbkArtifact = "$HOME\.agents\skills\bbk-artifact\scripts\bbk-artifact.cmd"

# Claude Code (use this assignment instead in Claude)
# $BbkArtifact = "$HOME\.claude\skills\bbk-artifact\scripts\bbk-artifact.cmd"

& $BbkArtifact binding
& $BbkArtifact --help
```

For a project-scope BBK install, use the corresponding `<project>\.agents\skills\bbk-artifact` or `<project>\.claude\skills\bbk-artifact` directory. On Linux or macOS, invoke the wrapper through `sh`; release archives intentionally do not rely on executable permission bits:

```sh
BbkArtifact="$HOME/.agents/skills/bbk-artifact/scripts/bbk-artifact.sh"
# Claude Code instead:
# BbkArtifact="$HOME/.claude/skills/bbk-artifact/scripts/bbk-artifact.sh"

sh "$BbkArtifact" binding
sh "$BbkArtifact" --help
```

The wrapper discovers the exact project- or user-scope BBK installation manifest, validates the installed package root, and invokes its recorded Python executable and `tools/bbk.py`. It automatically inserts `--json artifact`. Do not classify BBK as unavailable merely because the short command is unresolved. If wrapper discovery fails, read `bbk-installed-profiles/SKILL.md` and use its exact CLI fallback before reporting a blocker.

## Select the correct BBK surface

Use a dedicated semantic constructor when one exists:

- Use `bbk handoff create` and `bbk handoff verify` for `bbk.handoff.v2`; do not hand-author generated handoff identity.
- Use `bbk context worker` or `bbk context review` for generated Worker and review context packages.
- Use `bbk candidate freeze`, `check`, `status`, or `verify` for the existing project-managed or legacy candidate lifecycle. Do not confuse `bbk.candidate.v1` with the sealed `candidate-package-v1` profile required by generated review context.
- Use one-shot `bbk artifact finalize --root <project> --package-id <id> --revision <rev>` for ordinary software implementations; the source set defaults to the project root, and repeat `--source <path>` only to narrow it. It constructs the generic package draft, publishes under `.bbk/artifacts/sealed/`, and binds the exact live source set without requiring hand-authored package internals.
- Use draft-mode `bbk artifact finalize <draft-root> --root <project>` when an exact profile-specific descriptor, semantic artifact roles, references, or predecessor structure is required. Use the remaining `bbk artifact` commands for explicit preflight/seal/verify/successor operations, exact inspection, and legacy manifest compatibility.

A legacy `artifact manifest` is a flat exact-file manifest. It is not a substitute for a sealed package when immutable publication, profile semantics, artifact-reference closure, or successor history is required.

## Run the standard package lifecycle

For an ordinary implementation already present in the project workspace:

1. Select the exact implementation source set. `--source .` is appropriate only when the default exclusions and any explicit `--include`/`--exclude` rules describe the intended candidate.
2. Run one-shot `finalize` with an explicit package ID and revision. BBK constructs a temporary generic draft, copies only the selected regular files, seals to a new absent directory under `.bbk/artifacts/sealed/<packageId>-<revision>`, verifies the exact tree, writes an immutable publication receipt under `.bbk/artifacts/publications`, and updates a mutable current pointer under `.bbk/artifacts/current`.
3. Run `freshness` against the returned publication receipt immediately before a completion relay. A later source mutation invalidates the bound completion evidence and requires a successor revision.
4. Return the tool-generated identity and the claims that remain unestablished.

For a profile-specific semantic package:

1. Write the semantic artifacts to a physical draft directory.
2. Create `bbk-package-draft.json` and declare every file, role, schema, and reference intended to appear in the sealed package.
3. Run preflight and repair only findings within current authority.
4. Run draft-mode `finalize`; publication metadata remains outside the sealed package.
5. Use explicit `seal` only when a caller deliberately owns a non-published intermediate or another exact output path. Never overwrite a prior package.
6. Verify the sealed output from disk before consuming it across a trust boundary, even though `finalize` already performs pre- and post-publication verification.

`finalize` rejects common live coordination files such as current status, readiness, and package-index records by default. Keep those mutable projections outside the draft. Use `--allow-mutable-coordination` only when the file is intentionally an immutable snapshot and the role owns that decision.

Windows one-shot software example (after assigning `$BbkArtifact` to the active Codex or Claude skill wrapper above):

```powershell
$Finalized = & $BbkArtifact finalize `
  --root (Get-Location) `
  --package-id "session-inspector" `
  --revision "1" `
  --source "."

$Finalized
& $BbkArtifact freshness $Finalized.publicationReceipt --root (Get-Location)
```

Profile-specific draft example:

```powershell
$Draft = ".bbk\artifacts\drafts\design-package-r1"
& $BbkArtifact preflight $Draft
$Finalized = & $BbkArtifact finalize $Draft --root (Get-Location)
& $BbkArtifact freshness $Finalized.publicationReceipt --root (Get-Location)
```

The default sealed directory is derived from the package ID and revision. Consume the exact `outputRoot` returned by `finalize` rather than predicting it. If the user explicitly requires `bbk artifact finalize`, a handoff, passing tests, a raw directory, or `artifact seal` is not a substitute; do not issue the completion relay until `finalize` passes and `freshness` confirms the current source set.

Use `assets/bbk-package-draft.generic.json` as a starting point for an arbitrary local package. Read `references/artifact-package-reference.md` before constructing a profile-specific package or diagnosing a rejected operation.

## Draft rules

- Use profile `generic` version `1` for arbitrary local artifacts unless an exact profile-specific producer contract applies.
- Use unique `packageId`, artifact IDs, and artifact paths. Keep the same `packageId` across successors and change `revision` for each new attempt or revision.
- Use relative paths with `/` separators. Do not use absolute paths, `..`, backslashes, symlink roots, symlink path components, or package control filenames as artifact paths.
- Declare every file that must be carried. Unlisted draft files are not part of the sealed package.
- Use `references` only for declared artifact IDs. Keep references unique and acyclic.
- For a schema-declared JSON artifact, the descriptor's `schema` must equal the artifact's top-level `schema`, and that schema must be permitted by the selected profile.
- Never place generated fields in a draft artifact descriptor: `bytes`, `sha256`, `canonicalization`, `contentSha256`, `closure`, `sealReceipt`, `sealedAtUtc`, or `toolVersion`.
- Do not manually create or edit `bbk-package.json`, `bbk-package-manifest.json`, or `bbk-seal-receipt.json`.

## Treat sealed packages as immutable

Never edit, add, remove, rename, canonicalize, or repair files inside a sealed package. Verification must remain read-only. To revise a package, create a predecessor-bound successor draft:

```powershell
& $BbkArtifact successor ".bbk\artifacts\sealed\design-package-r1" `
  --output ".bbk\artifacts\drafts\design-package-r2" `
  --revision "2" `
  --reason "Address reviewed design findings"

& $BbkArtifact preflight ".bbk\artifacts\drafts\design-package-r2"
& $BbkArtifact finalize ".bbk\artifacts\drafts\design-package-r2" --root (Get-Location)
```

Use the exact `outputRoot` from the finalize result for any later read-only verify. The external publication receipt and current pointer may be updated; files inside the sealed package may not.

Use `--recover-stale-lock` only after establishing that no live seal or successor operation owns the lock. A lock conflict is not permission to delete the lock reflexively.

## Handle structured findings

Read `status`, `code`, `classification`, `findings`, and `smallest_next_action` from JSON output.

- Repair a `MECHANICAL` finding only when the affected path and mutation are in scope.
- Stop and return `SEMANTIC_OWNER_REQUIRED` when profile choice, subject identity, artifact meaning, schema meaning, or another semantic decision is missing or inconsistent.
- Stop and return `AUTHORITY_REQUIRED` when the operation encounters unauthorized mutation, concurrency, ownership, or another authority boundary.
- Preserve rejected, partial, blocked, predecessor, and superseded state. Never rewrite history to make a package appear originally successful.

## Delegate package work explicitly

When delegating package work to a Codex child agent, name `$bbk-artifact` explicitly and provide the exact draft or sealed path, intended profile, authorized operations, and required return fields. Do not assume that ambient context grants the child mutation authority or that a package-verification pass grants acceptance authority.

## Report the result

For a completed operation, report:

- operation and `PASS` or `REJECTED` status;
- exact draft or sealed package path;
- publication receipt and current-pointer path when `finalize` produced them, plus the current `freshness` result for source-bound software packages;
- package ID, revision, profile, and `contentSha256` when produced;
- verification status and whether it remained read-only;
- material findings and the smallest next action;
- the explicit boundary that package integrity does not establish semantic acceptance, authorization, validation, or release.
