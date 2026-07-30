# Upgrading BBK

This page describes supported upgrade patterns. Exact release-specific corrections remain attached to the relevant GitHub Release.

## General rule

Do not overlay one immutable release extraction onto another. Extract the new release into a new directory.

## Full user installation upgrade

From the currently installed release, uninstall through its manifest-aware tool:

```bash
python /path/to/old/tools/install.py uninstall --scope user
```

Then install the new release or source checkout:

```bash
python tools/setup.py --test-and-install --scope user --omp --codex
```

For sibling source repositories:

```bash
python tools/repo_setup.py --test-and-install --scope user --omp --codex
```

## Selective host update

When supported by both versions:

```bash
python tools/setup.py --update-omp --scope user --dry-run
python tools/setup.py --update-omp --scope user
```

or:

```bash
python tools/setup.py --update-codex --scope user --dry-run
python tools/setup.py --update-codex --scope user
```

Selective updates preserve the other host definitions and record mixed harness versions in the unified install manifest.

## Project records

Do not rewrite `.bbk` records merely because the package version changed. Apply a migration only when a release explicitly changes an artifact schema or semantic contract.

Never silently upgrade a legacy record to a stronger evidence, authority, independence, closure, or readiness state.

## Model-routing files

External install-time routing policies are version-bound. Update their declared package version and revalidate them before use.

OMP runtime routing profiles may also be version-bound; validate or export them again after an upgrade.

## Historical upgrade instructions

Older alpha-to-alpha migration documents are retained in release archives and tags rather than the current source documentation tree.
