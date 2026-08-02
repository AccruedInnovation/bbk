# Development and repository workflow

The extracted BBK package root is the canonical BBK source tree and is intended
to be committed directly to the BBK Git repository. No repository-extraction script
or generated `bbk/` staging directory is required.


## Canonical generation graph

Alpha.13 uses a one-way generation graph:

```text
spec/roles/catalog.json + spec/roles/bbk_*-role.json
  → tools/assemble_roles.py
  → spec/roles.json

canonical role return metadata
  → tools/return_contracts.py
  → role result/return schemas + role-return registry

spec/method-content.json + spec/prompt-modules/ + spec/model-routing.json + generated roles.json
  → tools/generate_agents.py
  → shared skills + Codex/OMP/Claude/generic projections + projections/manifest.json
```

Edit only canonical inputs. Every generator has a drift-check mode and the release gate runs all of them before packaging.

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

Run all consolidated unittest modules (independent modules run concurrently by default):

```bash
python tools/run_tests.py -v
```

Run the cross-cutting developer smoke profile when full release qualification is not required:

```bash
python tools/verify_all.py --profile quick --require-node
```

Use `python tools/run_tests.py -v --jobs 1` to reproduce ordering-sensitive failures serially. To isolate the Windows portability module, use `python tools/run_tests.py -v --jobs 1 -p test_installation_portability.py --suite-timeout 300`. Test children cannot read the developer console, and every module is bounded by the displayed hard timeout. OMP-only and Codex-only tested updates use their corresponding targeted verification profiles; the complete ordered sequence remains mandatory for release publication and CI qualification.

The ordered sequence verifies package integrity before execution, canonical
method and role projections, model routing, generated agents, Python and JSON
sanity, semantic/schema fixtures, typed profile fixtures, all tests, OMP syntax,
and package integrity after testing.

## Windows-native compatibility

Linux and macOS runs cannot faithfully reproduce Windows console code pages,
8.3 aliases, case-insensitive path identity, directory junctions, or Win32 file
sharing. Before publishing a release, run the native probe and the full suite
on Windows:

```powershell
python tools/windows_compat.py
python tools/run_tests.py --all --require-node

$env:PYTHONIOENCODING = "cp1252:strict"
python tools/run_tests.py -v --jobs 1
```

`tools/windows_compat.py` treats unavailable 8.3 generation or junction
creation as `NOT_APPLICABLE`, but fails any native behavior that is available
and produces inconsistent physical-path identity or leaves a capture file
behind after its exclusive Win32 handle is released.

The repository workflow `.github/workflows/windows-verification.yml` performs
these checks on `windows-latest` with Python 3.11 and 3.13. Keep that workflow
blocking for pull requests that change installation, update, subprocess,
console, temporary-file, path, or manifest code.

Cross-platform regressions still simulate a `TOMBST~1` to `Tombstone`
short-name expansion and use a directory alias to verify collision detection.
This keeps the algorithm covered even when a particular Windows CI volume has
8.3 name generation disabled.

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
