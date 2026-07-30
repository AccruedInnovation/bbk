# BBK 0.1.0-alpha.11.11 release notes

Alpha.11.11 is a repository-shape and documentation-maintenance successor to
alpha.11.10. It does not change the 19-role method, generated agent behavior,
model-routing policy, language-profile packages, installer destination
contracts, or `.bbk/` project-record formats.

## Repository-native source

The extracted BBK package root is now the canonical Git source tree. A separate
repository extractor, generated staging tree, or post-release projection step is
no longer required.

A normal repository update is:

1. extract and verify the new release;
2. replace the tracked repository contents while preserving `.git/` and any
   intentionally repository-only root README;
3. review the diff;
4. commit and tag through the normal Git workflow.

The source tree retains everything required to verify, develop, install, and
build BBK, including generated host projections and the five small bundled
language-profile archives. Keeping the bundled archives makes a standalone BBK
clone self-contained and preserves default profile installation.

## Documentation boundary

`docs/` is reduced from the accumulated pre-public history to 14 current,
durable documents:

```text
README.md
INSTALL.md
USAGE.md
UPGRADING.md
DEVELOPMENT.md
AGENTS.md
WAYFINDING-AND-GRILL.md
SOLUTION-OUTCOME-FIT.md
EXECUTION-DESIGN.md
DURABLE-HANDOFFS.md
ASSURANCE.md
LANGUAGE-PROFILES.md
MODEL-ROUTING.md
BOUNDARIES.md
```

Related material was consolidated rather than discarded:

- role composition and role-contract guidance are combined in `AGENTS.md`;
- state/effect and implementation-structure guidance are combined in
  `EXECUTION-DESIGN.md`;
- review context, evidence, findings, independence, and intent conformance are
  combined in `ASSURANCE.md`;
- profile dispatch is part of `LANGUAGE-PROFILES.md`;
- one durable `UPGRADING.md` replaces a chain of per-alpha migration files;
- `docs/README.md` is the documentation index.

Historical PRDs, decision notes, migration notes, internal alignment material,
old qualification reports, and release-specific test/audit transcripts are not
part of the public source tree. The human-readable public history remains in
`CHANGELOG.md`; the complete pre-public material is preserved in a separate
archive artifact.

## Removed pre-public utilities and fixtures

The public tree no longer carries:

- the repository-extraction utility and its documentation;
- the alpha.9.1 one-off Windows test-leak recovery utility;
- the internal Blueprint alignment data and dogfood fixture;
- historical source-PRD and decision-note directories.

None is required to build, verify, install, update, or use current BBK. They are
retained in the separate pre-public history archive for provenance.

## Test and build alignment

The five consolidated responsibility-oriented test modules now verify the
repository boundary directly:

- the public documentation inventory is exact and current-facing;
- historical directories and one-off utilities remain absent;
- the package root remains self-contained;
- expanded language-profile repositories remain directly installable;
- release building copies the root release notes without relying on a deleted
  documentation path.

`tools/build_release.py` continues to produce a deterministic release ZIP,
SHA-256 companion, package-manifest copy, and release-notes copy.

## Compatibility

No `.bbk/` project-record migration is required. Existing alpha.11.10 model
routing overrides need only update their package-version binding when used with
alpha.11.11. The independently versioned CODESYS, Go, Python, Rust, and
TypeScript/JavaScript `0.1.0-alpha.3` packages are byte-identical to the set in
alpha.11.10 and continue to install by default.

See `docs/DEVELOPMENT.md` for the direct Git workflow, `docs/README.md` for the
current documentation map, and `docs/UPGRADING.md` for managed-install updates.
