# Development and repository workflow

The extracted BBK package root is the canonical BBK source tree and is intended
to be committed directly to the BBK Git repository. No repository-extraction script
or generated `bbk/` staging directory is required.


## Canonical generation graph

Alpha.16.1 uses a one-way generation graph:

```text
spec/roles/catalog.json + spec/roles/bbk_*-role.json
  → tools/assemble_roles.py
  → spec/roles.json

canonical role return metadata
  → tools/return_contracts.py
  → role result/return schemas + role-return registry

spec/method-content.json + spec/prompt-modules/ + spec/model-routing.json + generated roles.json
  → tools/generate_agents.py
  → shared SKILL.md files + Codex/OMP/Claude/generic projections + projections/manifest.json

shared/skills/bbk-artifact/{agents,assets,references,scripts}
  → source-owned auxiliary skill package installed beside its generated SKILL.md
```

Provider-bound prompt integrity is qualified against the actual object returned by `before_provider_request`, not `ctx.getSystemPrompt()` or the earlier `before_agent_start` value. Tests must cover ordinary non-BBK pass-through, controller and child prompts, the IRC-wake contamination regression, every supported provider adapter, unsupported payload blocking, absent/failed host abort behavior, per-request receipts, session recovery, and the documented extension-order finality boundary. Raw prompt and provider payload content must not be persisted in receipts.

Artifact publication tests must prefer `artifact finalize` for the standard immutable path and verify that publication/current metadata remains outside the sealed tree, mutable coordination files are rejected by default, pre/post publication verification passes, and external metadata is rolled back after a failed publication transaction.

Structured CLI parse failures must be tested under `--json` for invalid choices and missing required arguments without relying on `SystemExit`.

Edit only canonical inputs for generated outputs. `spec/method-content.json#skills/bbk-artifact` is the canonical prompt body for `shared/skills/bbk-artifact/SKILL.md`; its host metadata, draft template, reference, and wrappers are source-owned auxiliary files and must be reviewed and tested directly. Every generator has a drift-check mode and the release gate runs all of them before packaging.

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

Alpha.16.1 exposes three explicit profiles. Use the smallest profile that matches the decision being made:

```bash
# Canonical contracts and deterministic transformations
python tools/setup.py --test-fast

# Routine product, integration, and platform verification
python tools/setup.py --test --require-node

# Exhaustive release qualification
python tools/setup.py --release-test --require-node
```

The lower-level ordered verifier accepts `fast`, `standard`, and `release` directly. Historical `quick` and `full` spellings remain aliases for `fast` and `release` where supported:

```bash
python tools/verify_all.py --profile fast
python tools/verify_all.py --profile standard --require-node
python tools/verify_all.py --profile release --require-node
```

The standard profile keeps every product, installer, Git, Node/OMP, Beads, routing, platform, and user-facing schema-command test. Release adds only test-runner self-tests and duplicate optional whole-package Draft 2020-12 cross-checks. Release publication and `tools/build_release.py` always select release explicitly.

The default `auto` strategy uses six workers on hosts with at least 12 logical CPUs, four on medium hosts, and a smaller bound on low-core hosts. Windows groups modules into bounded pooled Python processes; POSIX retains module-isolated parallelism. `--jobs` changes only the worker count. Retained per-module durations drive later shards; source size is used only when no duration exists. For example:

```bash
python tools/run_tests.py --profile standard -v
python tools/run_tests.py --profile release -v --mode pooled --jobs 6
python tools/run_tests.py --profile release -v --mode isolated --jobs 1 -p test_installation_portability.py --suite-timeout 300
```

Canonical BBK CLI assertions and package-local deterministic verifier commands execute in-process after the immutable package trust gate. The adapters restore current directory, `sys.argv`, `sys.path`, environment, and temporary module state. Real process boundaries remain for package trust, Node, Git, interpreter flags, stdin/encoding and process-tree tests, installed copies, and unittest shard isolation.

Timing reports and the rolling duration cache live outside the package tree so test execution cannot mutate a qualified release. Defaults are `%LOCALAPPDATA%\BBK\test-runs` on Windows and `~/.cache/bbk/test-runs` on POSIX. Set `BBK_TEST_CACHE_DIR` for an isolated benchmark or CI workspace.

The ordered profiles verify the applicable package trust gates, canonical method and role projections, model routing, generated agents, Python and JSON sanity, semantic/schema fixtures, selected unittests, OMP syntax, and post-test package integrity. OMP-only and Codex-only tested updates retain their corresponding targeted profiles.

Alpha.16.1 has eight release-specific regression boundaries:

- `tests/test_omp_runtime.py` mirrors the exact IRC-wake contamination path, verifies/reconstructs every supported provider payload adapter, blocks unsupported shapes without retaining user content, records one v2 receipt per request, and exposes the extension-order finality boundary.
- `tests/test_omp_runtime.py` also separates native-`ask` wait from elapsed time and carries the current `WAITING_ON_USER` state into `/bbk:agents` while preserving independent child visibility.
- `tests/test_omp_runtime.py` retains the observed post-completion wake and five-peer roster shapes. Successful `injected`, `woken`, and `revived` receipts or newer live rosters reactivate a completed peer without duplicate identities; later task/roster evidence and failed receipts remain authoritative.
- `tests/test_artifact_packages_v1.py` proves draft-mode finalization, default project-local sealed output, external publication/current metadata, mutable-coordination rejection, post-publication verification, and rollback after an injected publication failure.
- `tests/test_artifact_packages_v1.py` additionally proves one-shot Python/HTML software publication without package internals, deterministic exclusions and symlink rejection, ephemeral-draft removal, exact source binding, current-pointer resolution, and freshness rejection after source mutation.
- `tests/test_omp_runtime.py` proves that an explicit finalization requirement cannot be satisfied by a handoff, a fresh publication permits completion, a later source mutation blocks it, and a voluntarily observed finalization receives the same freshness check.
- `tests/test_installation_portability.py` reproduces the alpha.16 OMP-only clean-replacement failure, proves the canonical adjacent import closure is installed and manifest-owned, refreshes predecessor packaged-default routing metadata, executes installed `/bbk:models` status and schema surfaces, and repeats the checks through the dedicated updater.
- prompt-module/generated-projection and CLI tests prove the WORKSPACE_IMPLEMENTATION / EXTERNAL_EXECUTION / PRODUCE_ONLY split, exact independent completion vocabulary, and machine-readable `bbk.cli-error.v1` diagnostics without uncontrolled argparse output.

`tests/test_artifact_skill.py` continues to verify the seven-file canonical skill package, all role/projection references, real Codex and Claude installation, install-manifest ownership, executable modes, wrapper binding without `bbk` on `PATH`, package preflight/finalize/verify, and uninstall. The Codex selective-update test separately proves that an older managed installation acquires the skill without rebinding the shared package or changing OMP agent/extension files.

### Native filesystem path assertions

Tests must distinguish physical filesystem identity from exact serialized spelling. Windows can expose the same object through long and 8.3 names, case variants, junctions, or other aliases; POSIX can do the same through symlinks. Raw `Path` or string equality is therefore incorrect for host paths.

Use `tests/_path_support.py`:

```python
from tests._path_support import (
    assert_exact_path_text,
    assert_labeled_path,
    assert_no_path_within,
    assert_same_path,
    assert_same_path_sequence,
    create_symlink_or_skip,
)

assert_same_path(self, status["project_root"], project)
assert_labeled_path(self, notifications, "Project", project)
```

`assert_same_path` prefers `os.path.samefile` when both objects exist and falls back to BBK's canonical physical-path key for planned or missing leaves. Use `assert_exact_path_text` only when slash, case, or relative spelling is itself the public serialization contract. A test-source audit rejects the recurring raw-equality and interpolated-notification patterns.

The presence of `os.symlink` does not prove that the current Windows process can create a link. Non-elevated sessions can receive WinError 1314 when Developer Mode or `SeCreateSymbolicLinkPrivilege` is unavailable. Security behavior that rejects symlinks must therefore have a deterministic privilege-independent unit test, with a separate real-filesystem integration probe using `create_symlink_or_skip`. A source audit rejects unguarded `os.symlink(...)` and `Path.symlink_to(...)` fixtures so this platform assumption cannot silently return.

## Windows-native compatibility

Linux and macOS runs cannot faithfully reproduce Windows console code pages,
8.3 aliases, case-insensitive path identity, directory junctions, or Win32 file
sharing. Before publishing a release, run the native probe and the full suite
on Windows:

```powershell
python tools/windows_compat.py
python tools/setup.py --release-test --require-node

chcp 1252
$env:PYTHONUTF8 = "0"
$env:PYTHONIOENCODING = "cp1252:strict"
python -m unittest -v `
  tests.test_core_contracts.Alpha6CongruenceTests.test_unicode_initialization_examples_and_uninitialized_status_are_truthful `
  tests.test_omp_runtime.Alpha113OmpModelMenuTests.test_installed_omp_tool_transport_round_trips_utf8_strictly
python tools/run_tests.py --profile release -v --mode isolated --jobs 1
```

`tools/windows_compat.py` treats unavailable 8.3 generation or junction
creation as `NOT_APPLICABLE`, but fails any native behavior that is available
and produces inconsistent physical-path identity or leaves a capture file
behind after its exclusive Win32 handle is released.

The repository workflow `.github/workflows/windows-verification.yml` performs
these checks on `windows-latest` with Python 3.11 and 3.13, including the
non-ASCII title `Baffle Connector — Δ測試 — café — 🚧` under code page 1252. Keep that workflow
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
python tools/assemble_roles.py
python tools/create_method_content.py
python tools/generate_agents.py
```

Then prove drift-free generation:

```bash
python tools/assemble_roles.py --check
python tools/create_method_content.py --check
python tools/generate_agents.py --check
```

`create_method_content.py` owns generated `SKILL.md` files and shared method references only. It deliberately does not delete or regenerate the auxiliary files under `shared/skills/bbk-artifact/`; those files are covered by the artifact-skill contract test and package manifest.

Then rerun the complete verification sequence. `projections/manifest.json` and
`PACKAGE-MANIFEST.json` are generated integrity records and should change only
with the source tree they describe.

## Release archive executable policy

BBK release ZIP entries remain mode-normalized to `0644`; host-facing scripts are interpreter-invoked rather than native executable entrypoints. In particular, invoke the POSIX artifact-skill wrapper as `sh scripts/bbk-artifact.sh ...`; its Python implementation is invoked by that wrapper. Tests must not depend on source-checkout executable bits because those bits are deliberately absent after clean extraction.

## Building a release

```bash
python tools/build_release.py --output-dir /path/to/output
```

The builder explicitly runs the exhaustive release profile unless `--skip-tests` is supplied after a separately recorded qualification. The builder writes a deterministic package ZIP, SHA-256 companion, package
manifest copy, and release-notes copy. Release-specific qualification evidence is
kept outside the repository tree and may be attached to the corresponding GitHub
release.

## Documentation policy

`docs/` contains only current, durable user and developer documentation. Historical
migration notes, implementation PRDs, decision notes, alignment audits, and
release-specific qualification reports are not part of the public source tree.
Their durable public history is `CHANGELOG.md`; complete pre-public records may be
kept in a separate archival artifact.
