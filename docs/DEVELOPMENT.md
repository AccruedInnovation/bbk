# Development and repository workflow

The extracted BBK package root is the canonical BBK source tree and is intended to be committed directly to the BBK Git repository. No repository-extraction script or generated `bbk/` staging directory is required.

## Development dependencies

Use Python 3.11 or newer. Check or install the dependency set before running generators or tests:

```bash
python tools/setup.py --check-dependencies
python tools/setup.py --install-dependencies --dry-run
python tools/setup.py --install-dependencies
```

No host flag selects the complete development surface, including OMP and Node. For Codex-only work without Node, add `--codex` to each command. The non-installing check disables mise downloads and automatic installation. The root `mise.toml` declares only pinned jj and Beads; the non-default `tools/omp-runtime.mise.toml` owns the OMP Node pin so ordinary root tasks do not load it. The opt-in installer handles Git, mise, those managed tools, compatible runtime schema packages, and the OMP Node runtime when selected; it does not install agent hosts or project language toolchains.

## Canonical generation graph

BBK uses a one-way generation graph:

```text
spec/roles/catalog.json + spec/roles/bbk_*-role.json
  → tools/assemble_roles.py
  → spec/roles.json

canonical role return metadata
  → tools/return_contracts.py
  → role result/return schemas + role-return registries

spec/prompt-modules/catalog.json + spec/prompt-modules/*.json
  → tools/prompt_modules.py
  → prompt-module compatibility package

spec/method-content.json
  → tools/create_method_content.py
  → generated shared SKILL.md files and method references

split roles + return contracts + prompt modules + method content + spec/model-routing.json
  → tools/generate_agents.py
  → Codex/OMP/Pi/Claude Code/generic projections + projections/manifest.json

shared/skills/bbk-artifact/{agents,assets,references,scripts}
  → source-owned auxiliary skill files installed beside the generated SKILL.md
```

Provider-bound prompt integrity is qualified against the actual object returned by `before_provider_request`, not `ctx.getSystemPrompt()` or the earlier `before_agent_start` value. Tests must cover ordinary non-BBK pass-through, controller and child prompts, the IRC-wake contamination regression, every supported provider adapter, unsupported payload blocking, absent/failed host abort behavior, per-request receipts, session recovery, and the documented extension-order finality boundary. Raw prompt and provider payload content must not be persisted in receipts.

Artifact publication tests must prefer `artifact finalize` for the standard immutable path and verify that publication/current metadata remains outside the sealed tree, mutable coordination files are rejected by default, pre/post publication verification passes, and external metadata is rolled back after a failed publication transaction.

Structured CLI parse failures must be tested under `--json` for invalid choices and missing required arguments without relying on `SystemExit`.

Edit only canonical inputs for generated outputs. `spec/method-content.json#skills/bbk-artifact` is the canonical prompt body for `shared/skills/bbk-artifact/SKILL.md`; its host metadata, draft template, reference, and wrappers are source-owned auxiliary files and must be reviewed and tested directly. Every generator has a drift-check mode and the release gate runs all of them before packaging.

## Normal update workflow

1. Extract the new BBK release into a clean directory.
2. Review the release notes and run the complete verification sequence.
3. Replace the repository worktree with the verified package tree while preserving `.git/` and only deliberate repository-local files that the package does not own. The root `README.md` is package-owned and must not be carried forward from an older release.
4. Review the Git diff, rerun drift checks and tests, then commit and tag or publish through the normal repository workflow.

The package tree already contains `.gitignore`, `.gitattributes`, `LICENSE`,
`CHANGELOG.md`, source, generated projections, tests, bundled profile archives,
and durable documentation. Candidate-specific qualification records that are needed to explain the shipped host boundary live under `docs/qualification/`. Large test transcripts, archive audits, and other release evidence remain outside the source tree and may be attached to the release.

The separate `bbk-language-profiles` repository is distributed as an expanded
repository tree with independently manifested profile packages beneath
`packages/`. For this release it publishes the same Go, Python, Rust, and
TypeScript/JavaScript profile set as the public BBK bundle. Update that
repository directly from the matching repository archive; BBK does not
need to extract it.

## Verification

Use the smallest setup profile that matches the surface under review. Setup runs the declared dependency preflight before any test process starts:

```bash
# Canonical contracts and deterministic transformations; no Node requirement
python tools/setup.py --test-fast

# Codex-only package and adapter checks; no Node requirement
python tools/setup.py --test --codex

# OMP-only package and runtime checks; Node.js 22+ required
python tools/setup.py --test --omp

# Routine cross-host product, integration, and platform verification
python tools/setup.py --test

# Exhaustive release qualification
python tools/setup.py --release-test
```

The ordered verifier also exposes focused OMP and Codex profiles. The low-level unittest runner exposes `fast`, `standard`, and `release` because host-focused selection belongs to the ordered verifier:

```bash
python tools/verify_all.py --profile codex
python tools/verify_all.py --profile omp --require-node
python tools/verify_all.py --profile fast
python tools/verify_all.py --profile standard --require-node
python tools/verify_all.py --profile release --require-node

python tools/run_tests.py --profile fast -v
python tools/run_tests.py --profile standard -v
python tools/run_tests.py --profile release --all --require-node -v
```

Historical `quick` and `full` spellings remain aliases for `fast` and `release` where supported.

The Codex profile contains no Node command and must pass even when Node is absent from `PATH`. The OMP profile owns OMP JavaScript and runtime checks. Standard and release cover all hosts, so they declare the OMP Node requirement instead of discovering it by accident. Git, mise, jj, Beads, `jsonschema`, and `referencing` are declared core dependencies. Test child processes set explicit fixture paths for substrate commands, so their results do not vary with unrelated global jj or Beads installs.

The native Windows workflow uses the official mise action to install the root `mise.toml` pins, then runs BBK's own opt-in dependency bootstrap and non-installing dependency check for Codex plus OMP. CI therefore exercises the same contract as a new user instead of relying on tools that happen to be preinstalled on the runner image.

The standard profile keeps every product, installer, Git, Node/OMP, Beads, routing, platform, and user-facing schema-command test. Release adds only test-runner self-tests and duplicate optional whole-package Draft 2020-12 cross-checks. Release publication and `tools/build_release.py` always select release explicitly.

The default `auto` strategy uses six workers on hosts with at least 12 logical CPUs, four on medium hosts, and a smaller bound on low-core hosts. Windows groups modules into bounded pooled Python processes; POSIX retains module-isolated parallelism. `--jobs` changes only the worker count. Retained per-module durations drive later shards; source size is used only when no duration exists. The packaged `tests/test-durations.json` keeps generic weights plus an optional `platforms.windows` map with provenance; missing native data falls back to the generic map. For example:

```bash
python tools/run_tests.py --profile standard -v
python tools/run_tests.py --profile release -v --mode pooled --jobs 6
python tools/run_tests.py --profile release -v --mode isolated --jobs 1 -p 'test_installation_*.py' --suite-timeout 420
```

Canonical BBK CLI assertions and package-local deterministic verifier commands execute in-process after the immutable package trust gate. The adapters restore current directory, `sys.argv`, `sys.path`, environment, and temporary module state. Real process boundaries remain for package trust, Node, Git, interpreter flags, stdin/encoding and process-tree tests, installed copies, and unittest shard isolation.

Timing reports and the rolling duration cache live outside the package tree so test execution cannot mutate a qualified release. Defaults are `%LOCALAPPDATA%\BBK\test-runs` on Windows and `~/.cache/bbk/test-runs` on POSIX. Set `BBK_TEST_CACHE_DIR` for an isolated benchmark or CI workspace.

Native Windows duration calibration is explicit and fail-closed. Use native Windows, the standard profile, isolated mode, one job, an explicit report path, and a fresh isolated `BBK_TEST_CACHE_DIR`:

```powershell
$env:BBK_TEST_CACHE_DIR = (Join-Path $PWD '.bbk-windows-calibration-cache')
python tools/run_tests.py --calibrate-windows-singleton --profile standard --mode isolated --jobs 1 --timing-report .\evidence\windows-standard-singleton-calibration.json
```

Reports record module inventory and runtime/tool/CPU provenance. Every module must be a passing singleton with a positive duration and matching Windows/standard/runtime/inventory identity; timeout, partial, duplicate, missing, stale, or wrong-subject evidence is rejected. Calibration never writes `tests/test-durations.json`, updates the rolling cache, or promotes weights.

The ordered profiles verify the applicable package trust gates, canonical method and role projections, model routing, generated agents, Python and JSON sanity, semantic/schema fixtures, selected unittests, OMP syntax, and post-test package integrity. OMP-only and Codex-only tested updates retain their corresponding targeted profiles.

Current regression coverage includes:

- the Python floor, dependency inventory, offline mise behavior, opt-in bootstrap plan, host-scoped Node rule, and preflight-before-write ordering;
- role, prompt-module, return-contract, routing, and projection drift;
- OMP Main/child prompt replacement, provider-payload verification, wake/resume handling, native `ask`, child visibility, routing state, and extension-order limits;
- candidate identity, artifact finalization, source freshness, publication rollback, and exact completion claims;
- installation, selective OMP/Codex updates, profile verification and reuse, manifest ownership, Windows paths, console behavior, and UTF-8 handling;
- governed filesystem effects, WorkUnit ownership, durable handoffs, Beads projection, assurance state, findings, and schema commands.

Add a focused regression whenever a defect exposes a new contract boundary. Keep release history in [`../CHANGELOG.md`](../CHANGELOG.md) and candidate-specific host evidence in `qualification/`.

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
  tests.test_omp_runtime_model_menu.Alpha113OmpModelMenuTests.test_installed_omp_tool_transport_round_trips_utf8_strictly
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
python tools/return_contracts.py --write
python tools/create_method_content.py
python tools/create_procedure_registry.py
python tools/prompt_modules.py --size-report
python tools/generate_role_capabilities.py
python tools/model_routing.py --check
python tools/generate_agents.py
python tools/prompt_lint.py
```

Then prove drift-free generation:

```bash
python tools/assemble_roles.py --check
python tools/return_contracts.py --check
python tools/create_method_content.py --check
python tools/create_procedure_registry.py --check
python tools/prompt_modules.py --check-size-report
python tools/generate_role_capabilities.py --check
python tools/model_routing.py --check
python tools/generate_agents.py --check
python tools/prompt_lint.py --check
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

The root `README.md` is the public overview. The 16 current top-level guides under `docs/`, plus `docs/README.md`, cover current operation, method, hosts, assurance, and maintenance. Release-specific files under `docs/qualification/` remain bound to the exact candidate and host combination they record; they are evidence, not general instructions.

Keep migration detail and implementation history in `CHANGELOG.md` or a separate archival artifact unless the current package still depends on it. Update links, counts, commands, versions, host lists, schemas, and generated-surface names whenever their canonical source changes. Run the documentation link and current-facing checks before release.
