# Development and repository workflow

The extracted BBK package root is the canonical BBK source tree and is intended
to be committed directly to the BBK Git repository. No repository-extraction script
or generated `bbk/` staging directory is required.

## Normal update workflow

1. Extract the new BBK release into a clean directory.
2. Review the release notes and run the complete verification sequence.
3. Replace the contents of the local BBK repository with the verified package
   tree, preserving `.git/` and any intentionally maintained repository-only
   files such as the public-facing root README.
4. Review the Git diff, commit, and tag or publish through the normal repository
   workflow.

The package tree already contains `.gitignore`, `.gitattributes`, `LICENSE`,
`CHANGELOG.md`, source, generated projections, tests, bundled profile archives,
and durable documentation. Release qualification reports, archive audits, test
transcripts, and pre-public history are distributed as separate release
artifacts rather than mixed into `docs/`.

The separate `bbk-language-profiles` repository is distributed as an expanded
repository tree with independently manifested profile packages beneath
`packages/`. Update that repository directly from the matching repository
archive; BBK does not need to extract it.

## Verification

Run the complete ordered trust-gated sequence:

```bash
python tools/run_tests.py --all --require-node
```

Run only the consolidated unittest modules:

```bash
python tools/run_tests.py -v
```

The ordered sequence verifies package integrity before execution, canonical
method and role projections, model routing, generated agents, Python and JSON
sanity, semantic/schema fixtures, typed profile fixtures, all tests, OMP syntax,
and package integrity after testing.

## Generated files

Do not edit generated agent projections directly. Update the canonical sources
and regenerate:

```bash
python tools/create_method_content.py
python tools/create_role_spec.py
python tools/generate_agents.py
```

Then rerun the complete verification sequence. `projections/manifest.json` and
`PACKAGE-MANIFEST.json` are generated integrity records and should change only
with the source tree they describe.

## Building a release

```bash
python tools/build_release.py --output-dir /path/to/output
```

The builder writes a deterministic package ZIP, SHA-256 companion, package
manifest copy, and release-notes copy. Release-specific qualification evidence is
kept outside the repository tree and may be attached to the corresponding GitHub
release.

## Documentation policy

`docs/` contains only current, durable user and developer documentation. Historical
migration notes, implementation PRDs, decision notes, alignment audits, and
release-specific qualification reports are not part of the public source tree.
Their durable public history is `CHANGELOG.md`; complete pre-public records may be
kept in a separate archival artifact.
