# BBK 0.1.0-alpha.16.1 release notes

Alpha.16.1 is a bounded corrective release over alpha.16. It repairs the selective OMP installation path that could remove required adjacent Python modules and retain stale predecessor routing metadata, makes ordinary software publication usable through one-shot `bbk artifact finalize`, binds those publications to the exact live source selection, and prevents an OMP completion relay from substituting a handoff or stale package for explicitly required artifact finalization.

The release preserves alpha.16's provider-bound prompt guard, authority vocabulary, timing surface, 19-role topology, and reviewed per-role model selections. It does not add Blueprint's global lifecycle, model-suitability, semantic-reference, acceptance, review-invalidation, or release-authority systems.

## Selective OMP installation correction

Alpha.16's full installation path contained the complete OMP runtime, but an OMP-only clean replacement or dedicated OMP update used a shorter file inventory. On an installation that already owned Codex and OMP, this could remove modules such as `strict_json.py` while preserving Codex and shared state. `/bbk:models` would then fail during import. The same path could retain an alpha.15 packaged-default routing source in install-manifest metadata.

Alpha.16.1 introduces one canonical `OMP_EXTENSION_RUNTIME_FILES` inventory consumed by both the full installer and the selective updater. The updater now:

1. plans every required adjacent Python runtime module from that inventory;
2. proves each module is present in the desired plan and owned by the merged install manifest;
3. refreshes packaged-default model-routing source and effective-copy metadata to the current package while preserving explicit custom policy ownership;
4. writes the merged manifest before post-install qualification;
5. executes the installed import closure, installed `/bbk:models` router status, and installed BBK schema catalogue; and
6. restores the previous manifest and targeted files if post-install smoke qualification fails.

The regression reproduces the reported sequence: install Codex and OMP, perform `--install --scope user --omp --uninstall-existing`, preserve Codex, and execute the installed model-routing status surface successfully.

## One-shot software artifact finalization

Ordinary implementations no longer require an agent to reverse-engineer or hand-author `bbk-package-draft.json`. The following is now a complete software-publication operation:

```text
bbk artifact finalize --root . \
  --package-id omp-session-inspector \
  --revision 1
```

The same mode is exposed through the OMP `bbk_artifact_finalize` tool and the managed Codex/Claude `bbk-artifact` skill. Draft mode remains available for profile-specific semantic packages:

```text
bbk artifact finalize <draft-root> --root <project>
```

One-shot software mode:

- defaults to the project root when `--source` is omitted, or accepts one or more explicit files/directories to narrow the source set;
- rejects symbolic-link roots and symbolic links inside selected directories;
- applies deterministic built-in exclusions for BBK/VCS state, caches, virtual environments, `node_modules`, build output, and bytecode;
- applies optional project-relative `--include` and `--exclude` globs;
- copies only selected regular files into an ephemeral generic draft;
- mechanically classifies source, documentation, and fixture roles;
- seals to `.bbk/artifacts/sealed/<package-id>-<revision>/` by default;
- writes the immutable publication receipt outside the package under `.bbk/artifacts/publications/`;
- updates the mutable selector under `.bbk/artifacts/current/`; and
- removes the synthesized draft before returning.

The operation returns the exact selected-source snapshot and reports `BYTE_INTEGRITY_VERIFIED` only. It does not establish semantic correctness, review closure, acceptance, authorization, deployment readiness, deployment, live acceptance, compliance, or release authority.

## Source-bound freshness

A one-shot software publication records its project root, source selectors, exact file paths, byte lengths, and SHA-256 values in the external publication receipt. The new command:

```text
bbk artifact freshness <publication-or-current-pointer> --root <project>
```

re-verifies the immutable package and reconstructs the current selected source set. Added, removed, changed, missing, or newly selected files make the result `REJECTED` with `PACKAGE_FINALIZATION_SOURCE_STALE`. A sealed directory without a source binding remains byte-verifiable but reports `sourceStatus: NOT_BOUND`.

Freshness is a local byte-evidence check. It does not rerun tests, semantic review, validation, or live acceptance.

## OMP finalization and completion guard

When BBK mode observes that the user explicitly required `bbk artifact finalize`, the OMP extension records a durable finalization obligation. A passing handoff, tests, raw implementation directory, or explicit `artifact seal` does not satisfy it.

A successful `bbk_artifact_finalize` result binds its publication receipt to the session. Before a terminal assistant message claims implementation completion, byte integrity, semantic completion, delivered-and-verified status, or live acceptance, BBK runs `artifact freshness` against that receipt. The relay proceeds only while the current selected source set still matches the publication. A later source mutation blocks the completion claim and requires local re-verification plus a successor finalization.

The same freshness check applies when finalization was voluntarily performed even if the initial user request did not make it mandatory. Ordinary sessions that neither require nor perform finalization are unaffected.

This is a local OMP consistency guard, not a global Blueprint lifecycle. It does not infer whether implementation, review, or acceptance is semantically complete; it only prevents a completion-bearing relay from contradicting an explicit finalization requirement or a known source-bound publication.

## Managed host surfaces

The managed Codex and Claude `bbk-artifact` skill now documents both finalization modes and requires a source-bound `freshness` check before reporting completion. It remains PATH-independent and resolves the active installed BBK package through the installation manifest.

The OMP extension now exposes:

- 44 model-facing tools; and
- 48 UI commands.

The added surface is `bbk_artifact_freshness` and `/bbk:artifact:freshness`.

## Upgrade

Use a clean alpha.16.1 extraction. Do not overlay selected files onto an alpha.16 package directory.

For the reported user-scope installation that owns OMP and Codex:

```powershell
python tools\setup.py --test-and-install `
  --scope user `
  --omp `
  --codex `
  --uninstall-existing
```

For a dedicated OMP-only update that preserves the installed Codex surface:

```powershell
python tools\setup.py --test-and-update-omp --scope user
```

After either path, run `/reload-plugins` or restart OMP. A successful selective update reports passing `runtime_inventory` and `runtime_smoke` records.

External model-routing policies remain release-bound: set `package_version` to `0.1.0-alpha.16.1`, preserve exact coverage of all 19 roles, and revalidate before installation. The reviewed role routes themselves are unchanged from alpha.16.

## Repository-native source

The extracted archive remains **Repository-native source**: canonical specifications, deterministic generators, tests, current documentation, and package metadata are present without an external migration step. The `docs/` directory contains **15 current** public-facing documents. Full qualification transcripts, archive audits, and **pre-public history** are separate release artifacts rather than runtime dependencies. **No `.bbk/` project-record migration** is required solely for alpha.16.1.
