# Install and qualify BBK alpha.15

Alpha.15 is distributed as one archive containing the BBK core and five independently manifested language profiles: CODESYS `0.1.0-alpha.4`, plus Go, Python, Rust, and TypeScript/JavaScript `0.1.0-alpha.3`. It integrates the canonical split-role v4 package, exact role-return/execution contracts, 31 reusable prompt modules, compact infrastructure/schema/artifact tooling, projection manifest v8, and the reviewed per-role model-routing defaults. It preserves bounded verification, harness-scoped updates, the PowerShell-visible default-Yes prompt, OMP controller/activity/`ask` behavior, and installs all five profiles by default. Use a clean extraction for each release.

## Prerequisites

- Python 3.10 or newer for core BBK;
- Git for worktree operations;
- Node.js when OMP is selected or JavaScript syntax validation must be blocking;
- any compiler, linter, simulator, IDE, or runtime required by a selected language profile's live gates.

Package verification and profile-package verification do not imply that external language toolchains are installed.

## Preferred one-command path

From a clean extraction:

```bash
python tools/setup.py --test-and-install --scope user --omp --codex --claude
```

This command:

1. verifies the immutable core package before executing package code;
2. checks method, role, model-routing, and generated-agent projections;
3. compiles Python, parses JSON, validates semantic/schema fixtures, runs the standard product/integration/platform test profile, and validates OMP JavaScript;
4. verifies the package again after testing;
5. prepares and independently verifies all five bundled language-profile packages;
6. computes the complete core-plus-profile destination plan;
7. installs only if every blocking check and preflight passes.

With no profile-selection flag, these profiles are installed by default:

```text
codesys
go
python
rust
typescript-javascript
```


The shorter front door is equivalent:

```bash
python tools/bootstrap.py --test-and-install --scope user --omp --codex --claude
```

If no harness flag is supplied, Codex, OMP, Claude Code, and generic targets are all selected.

## Verification only

Routine verification uses the standard profile:

```bash
python tools/setup.py --test --require-node
python tools/bootstrap.py --test --require-node
python tools/install.py verify --verification-profile standard --require-node
```

Use the fast profile during active contract/prompt work:

```bash
python tools/setup.py --test-fast
python tools/verify_all.py --profile fast
```

Release authors must use the exhaustive profile:

```bash
python tools/setup.py --release-test --require-node
python tools/verify_all.py --profile release --require-node
```

The standard profile includes all product, integration, installer, Git, Node/OMP, Beads, routing, platform, and user-facing schema-command tests. Release adds test-runner self-tests and duplicate optional external Draft 2020-12 package cross-checks. `tools/build_release.py` selects release explicitly.

The ordered profile runs the applicable strict package-manifest trust gate, canonical projection and routing checks, source sanity, semantic/schema fixtures, selected unittests, OMP JavaScript syntax, and post-test package verification. Safe deterministic Python commands execute in-process after trust; package verification, Node, Git, interpreter/process-tree, stdin/encoding, installed-copy, and unittest-shard boundaries remain real processes.

`auto` uses up to six workers on high-core hosts and four on medium hosts; Windows groups modules into bounded pooled processes while POSIX retains module-isolated parallelism. Retained module timings are used for sharding. Test reports and the duration cache are external to the package (`%LOCALAPPDATA%\BBK\test-runs` on Windows, `~/.cache/bbk/test-runs` on POSIX); use `BBK_TEST_CACHE_DIR` to isolate a benchmark. Direct diagnostics include:

```bash
python tools/run_tests.py --profile standard -v
python tools/run_tests.py --profile release -v --mode pooled --jobs 6
python tools/run_tests.py --profile release -v --mode isolated --jobs 1
```

For ordinary selective successor updates, prefer `python tools/setup.py --test-and-update-omp --scope user` or `--test-and-update-codex`; those commands retain package trust and generated-source checks without unrelated harness suites.

## Inspect the full plan

A dry run plans the core and all five bundled profiles without creating any destination or install manifest:

```bash
python tools/install.py install --scope user --omp --codex --claude --dry-run
```

The reported manifest path is the path that a real installation would write; `--dry-run` intentionally does not create it.

JSON output is available with `--json`:

```bash
python tools/install.py --json install --scope user --omp --codex --dry-run
```

## Select bundled profiles

Install only a subset by repeating `--profile-id`; no external bundle path is required:

```bash
python tools/setup.py --test-and-install --scope user --omp --codex \
  --profile-id rust \
  --profile-id python
```

Profile IDs must match the bundled package IDs exactly.

## Core-only installation

Opt out explicitly:

```bash
python tools/setup.py --test-and-install --scope user --omp --codex \
  --no-language-profiles
```

`--no-language-profiles` cannot be combined with `--profile-id` or `--language-profiles`.

A core-only installation still generates `bbk-installed-profiles/SKILL.md`; the registry explicitly says no language/domain profile is managed by that installation.

## Use an alternate profile source

Supplying `--language-profiles PATH` replaces the bundled source for that invocation:

```bash
python tools/setup.py --test-and-install --scope user --omp --codex --claude \
  --language-profiles /path/to/alternate-profile-bundle.zip
```

Accepted sources are:

- an individual profile ZIP;
- an extracted profile package;
- a flat directory whose immediate children are extracted profile packages;
- a directory whose `packages/` children are extracted profile packages;
- a manifested expanded profile repository containing `REPOSITORY-MANIFEST.json`;
- a verified multi-profile release-bundle ZIP;
- an extracted verified release-bundle directory.

Repeat `--language-profiles` to combine explicit sources. Repeat `--profile-id` to select an exact subset from those explicit sources.

For sibling BBK and `bbk-language-profiles` Git checkouts:

```powershell
python tools\setup.py --test-and-install `
  --scope user --omp --codex `
  --language-profiles ..\bbk-language-profiles
```

When `REPOSITORY-MANIFEST.json` is present, BBK verifies its exact profile IDs, versions, paths, and package-root digests before independently verifying each profile package. An unmanifested flat or `packages/` directory is still accepted, but each discovered package must pass its own manifest verification.

The profile-focused wrapper uses the bundled set when `--bundle` is omitted:

```bash
python tools/install_profiles.py --scope user --omp --codex --claude
```

A bundled subset:

```bash
python tools/install_profiles.py --scope user --omp --codex \
  --profile rust --profile python
```

An alternate source:

```bash
python tools/install_profiles.py --bundle /path/to/profiles.zip \
  --scope user --omp --codex --claude
```

## Install without rerunning verification

Use only after the exact extraction has already passed the ordered sequence:

```bash
python tools/setup.py --install --scope user --omp --codex --claude
```

Lower-level equivalent:

```bash
python tools/install.py install --scope user --omp --codex --claude
```

Profile package, compatibility, archive-safety, collision, and destination preflight checks are never skipped.

## Existing installation and clean replacement

Before an ordinary interactive install begins verification or profile preparation, BBK checks the selected scope for an existing `bbk.install-manifest.v1`. It reports the installed version, harnesses, file count, and manifest path.

The replacement question now follows the selected harness scope.

When every installed harness is selected—or the existing installation contains only the selected harness—the installer offers a full replacement:

```text
Uninstall the existing BBK installation first? [Y/n]
```

A full replacement preflights the successor before removal, removes every unchanged manifest-owned file from the previous install, then installs only the harnesses and profiles selected by the current command.

When an existing multi-harness installation contains OMP and/or Codex and the command selects exactly one already-installed `--omp` or `--codex` harness, the installer offers a harness-scoped replacement instead:

```text
Clean-replace the selected omp harness now? [Y/n]
```

or:

```text
Clean-replace the selected codex harness now? [Y/n]
```

That path refreshes only the selected harness and removes only stale manifest-owned files inside that harness's target roots. It preserves every unselected harness, its files, its per-harness version record, shared install ownership, and unowned/private files. In particular, `--omp --uninstall-existing` no longer uninstalls Codex, and `--codex --uninstall-existing` no longer removes OMP.

Harness-scoped clean replacement currently supports exactly one already-installed OMP or Codex harness. Unsupported partial combinations fail before any removal. Selecting all installed harnesses uses full replacement. Use the dedicated selective update commands for normal successor updates.

Press Enter to accept the displayed default **Yes**. Locally modified manifest-owned files stop either replacement before removal unless `--force` is explicit; forced replacement backs up modified regular files first. Non-regular objects at manifest-owned file paths fail closed. Unowned material is never removed merely because it lives under a BBK directory.

Machine-readable and detached automation never answers a destructive prompt implicitly. JSON, dry-run, and other noninteractive installs retain/reconcile the existing installation unless an explicit policy is supplied:

```bash
# Clean-replace only OMP and preserve installed Codex.
python tools/setup.py --install --scope user --omp --uninstall-existing

# Clean-replace only Codex and preserve installed OMP.
python tools/setup.py --install --scope user --codex --uninstall-existing

# Reconcile without clean stale-file removal.
python tools/setup.py --install --scope user --omp --keep-existing
```

The same flags are available on `tools/install.py install`; `--uninstall-existing` and `--keep-existing` are mutually exclusive.

A harness-scoped replacement preserves the installed shared model-routing policy and language-profile set. Supplying `--model-routing`, `--language-profiles`, `--profile-id`, or `--no-language-profiles` with that path fails before removal; use a full replacement when changing shared installation state.

Selective `--test-and-update-omp` and `--test-and-update-codex` commands use the same manifest-aware host boundaries without the install prompt and remain the preferred way to apply a successor to only one harness.

## Fail-closed preparation and installation boundary

Before the first destination write, alpha.13:

1. validates raw ZIP paths before normalization;
2. rejects traversal, absolute/drive-qualified paths, backslashes, alternate-data-stream names, NUL/control characters, trailing dots/spaces, reserved Windows device names, duplicate entries, portable case collisions, file/directory conflicts, symlinks, special files, encrypted entries, and excessive expansion;
3. verifies the exact outer release-bundle inventory or expanded-repository profile inventory and root digests;
4. independently verifies every selected profile package manifest and root digest;
5. validates `PROFILE.json`, `VERSION`, package identity, install paths, profile IDs, BBK minimum, and Python compatibility;
6. renders core agents and dynamic registry material in memory;
7. builds one complete core/profile destination plan;
8. rejects divergent or executable-mode-conflicting co-ownership;
9. preflights existing-destination divergence and backup behavior over the complete plan.

Only after that no-write preflight passes does the actual installation begin. The durable manifest records the preflight receipt.

### Codex custom-agent sandbox behavior

Generated Codex agents omit `sandbox_mode` and inherit the parent turn's live sandbox and approval choices. This avoids forcing non-mutating roles into a host-level read-only state that also blocks notes, handoffs, evidence records, and other coordination artifacts. The omission does not grant subject-mutation authority: only the canonical mutating roles may change subject or product artifacts, and only inside their invocation grant. Set the parent Codex session to read-only whenever no child writes of any kind should be allowed.

## Visible progress during verification and installation

Human-readable setup and installation commands stream progress instead of buffering the complete verification run. The console shows:

- each ordered verification gate and elapsed time;
- each unittest suite as `[current/total]`;
- a `still running` heartbeat after 15 seconds without completion, including the latest visible test line and the module hard timeout;
- verified profile IDs before planning;
- no-write preflight file counts;
- actual file-write progress at bounded intervals;
- final manifest completion.

Machine-readable `--json` output suppresses these human messages so stdout remains valid JSON.

## Profile CLI fallback and schema validation

The generated `bbk-installed-profiles` skill records the preferred installed BBK launcher plus the exact Python interpreter and installed `tools/bbk.py` script. Agents should use that binding when `bbk` is not visible through the current shell, PATH, or mise environment. The ordinary discovery command remains:

```powershell
bbk --json profile list
```

Draft 2020-12 validation is exposed through the core CLI:

```powershell
python tools\bbk.py schema status
python tools\bbk.py schema validate --schema schema.json --instance candidate.json
```

`schema status` returns structured `BLOCKED` and process exit code 1 when neither the active interpreter nor the managed environment provides `jsonschema`; that is an expected optional-capability state, not malformed output. `--ensure` is explicit and creates an isolated `jsonschema==4.25.1` environment only when requested. Use `--wheelhouse PATH` for an offline source.

## Installed layout

User scope uses the platform data root. On Windows the default is:

```text
%LOCALAPPDATA%\BBK\
  current.json
  effective-model-routing.json
  effective-omp-model-routing.json    # when OMP is selected
  effective-language-profiles.json
  install-manifest.json
  bin\
  versions\0.1.0-alpha.15\
  profiles\<profile-id>\0.1.0-alpha.3\
  profiles\<profile-id>\current.json
```

Host projections and skills are installed into the selected user or project harness paths. The exact generated `bbk-installed-profiles` registry is installed into each selected host skill root.

All core files, profile package copies, profile skills, OMP extensions, launchers, generated registries, and generic metadata are owned by one install manifest.

## Model routing

Use the packaged defaults or pass an external `bbk.model-routing.v2` policy (legacy v1 remains accepted):

```bash
python tools/model_routing.py --path /path/to/model-routing.json --check
python tools/install.py install --scope user --omp --codex --claude \
  --model-routing /path/to/model-routing.json --dry-run
```

The external file's `package_version` must be `0.1.0-alpha.15`. The installer validates exact coverage of all 19 roles before writing and records the effective policy and digest.

An OMP installation also writes `effective-omp-model-routing.json` and exposes an interactive runtime menu:

```text
/bbk:models
/bbk:models status
/bbk:models project profile testing-flash
/bbk:models user profile default
/bbk:models project status
/bbk:models user status
```

The default `auto` target resolves the nearest valid project installation and otherwise the loaded user installation. Use a project-scoped OMP install in each repository that needs an independent runtime profile:

```powershell
python tools\install.py install --scope project --root D:\Projects\ProjectA --omp
python tools\install.py install --scope project --root D:\Projects\ProjectB --omp
```

The menu changes the selected installation's BBK OMP agent frontmatter for future spawns and reconciles changed digests into that installation's `install-manifest.json`. An expected but invalid project binding fails closed instead of falling back to the user installation. User-scope mutations require interactive confirmation because they are shared across projects. The menu refuses locally divergent or unowned agent files. The compact reusable template is `templates/omp-model-routing-profile.json`. OMP `task.agentModelOverrides` and higher-precedence project agent definitions remain authoritative over agent frontmatter. See `MODEL-ROUTING.md`.

Newly initialized BBK projects enable writable Beads coordination by default. The external `bd` executable is not bundled; run `bbk beads plan` before `bbk beads plan --apply`. Existing projects retain their current mapping until deliberately migrated.

## Status and uninstall

```bash
python tools/install.py status --scope user
python tools/install.py uninstall --scope user
```

Status compares content digests and, on POSIX, expected executable modes. Uninstall removes only manifest-owned files that remain unchanged. Locally modified bytes or executable modes are preserved and reported unless `--force` is explicit.

## Reusing unchanged installed profile files

Every selected bundled or external profile package is prepared and authenticated before the installer mutates a destination. Alpha.13.4 then compares the verified successor package with the existing unified manifest. A profile is reused only when its ID, independently versioned package version, package-root SHA-256, layout version, selected harness set, every owned file digest, and applicable executable mode are exact.

In reconciliation mode, a fully current profile bypasses the profile-copy operation and is adopted into the new manifest. During explicit clean replacement, any byte/mode-identical successor-owned file is retained in place rather than deleted and recopied. Install results report `language_profile_reuse`, per-profile `install_action`, and reused file counts.

This is not a version-label shortcut. Missing, changed, mode-divergent, or locally modified files follow the ordinary refusal, backup, repair, and `--force` rules. Profile packages are never trusted solely because the profile version string has not changed.

## Upgrade to alpha.15

Do not overlay one extracted release package directory onto another. Extract alpha.15 into a new directory and choose the narrowest appropriate update. See `UPGRADING.md` for the standard/release verification split, duration-aware pooled testing, and authenticated reuse of unchanged installed profile files.

Alpha.15 adds product-first proportional assurance, strict JSON and sealed artifact packages, project-local OMP routing creation/repair, role-return v2, generated Worker/review contexts, requirement-scoped host preflight, prototype charter v2, and sealed handoff v2. It does not add Blueprint lifecycle gates or automatically rewrite accepted-baseline, authority, Markdown, or Beads records. Existing projects and installed language profiles do not require content migration; unchanged authenticated profile packages remain eligible for in-place reuse.

To refresh only OMP while preserving Codex:

```bash
python tools/setup.py --test-and-update-omp --scope user
```

To refresh only Codex while preserving OMP:

```bash
python tools/setup.py --test-and-update-codex --scope user
```

For a full managed upgrade, select every installed harness and accept the full clean-replacement prompt, or pass `--uninstall-existing` explicitly in automation. A command selecting only `--omp` or only `--codex` now performs a harness-scoped clean replacement and preserves the other installed harness rather than removing it.

Alpha.15 retains the canonical split role package to split `bbk.roles.v4`, the generated projection manifest to v8, and the default `bbk.model-routing.v2` policy to the exact reviewed per-role selections. It adds generated role-return/result schemas and contract registries while preserving the existing install destinations. Start a fresh Codex session after updating its agents. Reload OMP plugins with `/reload-plugins` after an OMP update.

No `.bbk` project-record migration is required solely for alpha.15. New initializations place reference templates under `.bbk/examples/`; existing legacy examples remain supported and non-operational.

## Live qualification

Package qualification does not establish that a particular host version accepts every model identifier, reasoning-effort value, extension hook, task-agent field, external compiler, simulator, IDE, or gate. Inspect the dry run and qualify the installed host/toolchain combination before relying on it for consequential work.

## OMP persistent mode after installation

After installing or selectively updating OMP, reload extensions if the process was already running:

```text
/reload-plugins
```

Then enter persistent BBK mode:

```text
/bbk                 enter mode without starting an agent turn
/bbk <request>       enter mode and submit the first directive
/bbk:exit            exit mode
```

Mode state is session-local and persisted with `appendEntry`; it is not sent to the model. While active, `before_agent_start` performs a complete Main **system-prompt replacement** that excludes OMP's generic workflow and compatibility-discovered `.codex`, `.claude`, `.gemini`, or other client-specific instructions. The replacement injects the mandatory `bbk` and `bbk-context-routing` procedures and makes Main the sole user-facing controller.

Every generated named BBK role is a non-user-facing child with mandatory procedures already inlined. The hook also replaces each marked child's generic OMP subagent prompt while preserving sanitized assignment context, approved plan/path, worktree, hub identity/roster, and caller yield schema. Children coordinate through `hub`/IRC and send material human requests to Main; they do not focus the terminal or question the user directly.

Prompt replacement does not change the parent model, thinking level, toolset, child routing, or filesystem containment. `/bbk:exit` restores normal OMP prompting for later Main turns. Named BBK children continue to receive their role-specific replacement when invoked.

## Codex-only update without modifying OMP

From a clean extraction of the successor BBK release, update only the Codex-owned custom-agent surface of an existing installation:

```powershell
python tools/setup.py --test-and-update-codex --scope user
```

Or, when the release has already been verified:

```powershell
python tools/setup.py --update-codex --scope user
```

Inspect the plan without writing:

```powershell
python tools/setup.py --update-codex --scope user --dry-run
```

The operation replaces only the 19 installed BBK Codex agent definitions and reconciles their ownership records plus per-harness version metadata in the unified manifest. It deliberately preserves the installed BBK package copy, current pointer, launcher, effective install-time model-routing file, OMP agents and extensions, OMP runtime model routing, Claude Code agents, generic agents, and installed language-profile packages. It renders the new Codex files from a temporary version-rebound copy of the installed model policy, and refuses locally divergent targeted Codex files unless `--force` is explicit.

Because host caching behavior may vary, start a fresh Codex turn or session after the update before relying on newly generated custom-agent definitions.

## OMP-only update without stopping Codex

From a clean extraction of the successor BBK release, update only the OMP-owned surface of an existing installation:

```powershell
python tools/setup.py --test-and-update-omp --scope user
```

Or, when the release has already been verified:

```powershell
python tools/setup.py --update-omp --scope user
```

The operation updates the installed BBK package copy and launcher, OMP agents, the core OMP extension, installed bundled-profile OMP extensions, the mutable OMP routing state, and installation metadata. It preserves the active `/bbk:models` profile and per-role routes. It does not modify `.codex` agent files, Claude agent files, or generic agent files, so a running Codex process need not be shut down. The compact shared installed-profile registry may be refreshed only when every installed profile is present in the bundled release; already-loaded Codex context is not changed.

Use `--dry-run` to inspect the exact plan and `--force` only after reviewing a locally divergent targeted OMP file. After a successful update, run `/reload-plugins` in OMP so the process reloads the changed extensions and agent definitions.
