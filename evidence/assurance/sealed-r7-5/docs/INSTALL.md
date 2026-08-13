# Install and qualify BBK

This guide applies to BBK `0.1.0-alpha.17.0.2.1`. Use a clean extraction for each release; do not overlay one extracted package on another.

The release contains BBK core plus independently versioned Go, Python, Rust, and TypeScript/JavaScript profiles at `0.1.0-alpha.3`.

## Bootstrap and dependency policy

**Python 3.11 or newer is required.** Python is the bootstrap requirement for the Python setup and dependency scripts, so BBK does not try to install or replace Python itself.

BBK uses this dependency contract:

| Dependency | Required for | Setup behavior |
| --- | --- | --- |
| Python 3.11+ | all supported BBK use | checked before public setup, install, update, test, verification, and release entry points load BBK internals; installed separately by the user |
| Git | repository identity and worktree flows | installed by the opt-in dependency script through a supported system package manager |
| mise | pinned managed tools | installed by the opt-in dependency script through a supported package manager or the official user-local installer |
| `jj@0.43.0` | BBK repository substrate | installed explicitly through mise |
| Beads `1.1.0` (`bd`) | BBK work and handoff substrate | installed explicitly through mise |
| `jsonschema>=4.25.1,<5` | runtime schema checks | installed for the active Python interpreter through pip |
| `referencing>=0.36.2,<1` | runtime schema registry support | installed for the active Python interpreter through pip |
| Node.js 22+ | OMP only | uses a compatible direct runtime when present; otherwise the bootstrap installs `node@22.23.2` through mise |
| Codex, OMP, Pi, or Claude Code | use of that host | reported as a warning when absent; never installed or updated by BBK |

A language profile may need its own compiler, runtime, IDE, simulator, or test tool. BBK does not install those project-specific tools as part of core setup.

## Check dependencies without installing them

Run the preflight for the host or hosts you plan to install:

```bash
python tools/setup.py --check-dependencies --codex
python tools/setup.py --check-dependencies --omp
```

The preflight does not download or install tools and does not write BBK installation files. It disables mise network access and automatic installation, checks the exact managed versions with `mise which`, and prints one repair command when a required item is missing. A missing selected host app is a warning because BBK may prepare host files before that app is installed.

With no host flag, BBK selects all five hosts. That includes OMP and its Node requirement.

## Install missing dependencies after consent

Preview the exact plan:

```bash
python tools/setup.py --install-dependencies --codex --dry-run
```

Run it interactively:

```bash
python tools/setup.py --install-dependencies --codex
```

For automation, consent explicitly:

```bash
python tools/setup.py --install-dependencies --codex --yes
```

For OMP, select OMP so the plan also installs the pinned Node runtime:

```bash
python tools/setup.py --install-dependencies --omp
```

The script supports `winget`, Scoop, and Chocolatey on Windows; Homebrew and MacPorts on macOS; and `apt-get`, `dnf`, `yum`, `pacman`, `zypper`, and `apk` on Linux. Use `--package-manager NAME` to select one. On non-Windows systems where the selected package manager does not provide mise, the script can install mise under `~/.local/bin` through mise's official installer.

The script installs only missing BBK dependencies. It does not install or update agent host apps, language toolchains, drivers, IDEs, simulators, or target-project packages. Review the dry-run plan before using `--yes`.

## Canonical managed versions

The package-root [`mise.toml`](../mise.toml) declares only the core repository tools:

```toml
[tools]
"github:gastownhall/beads" = "1.1.0"
jj = "0.43.0"
```

The OMP-only [`tools/omp-runtime.mise.toml`](../tools/omp-runtime.mise.toml) declares:

```toml
[tools]
node = "22.23.2"
```

The OMP file has a non-default name, so root `mise run` tasks do not load it or acquire a Node dependency. BBK reads it only for an OMP dependency check or bootstrap. Codex-only verification does not require Node, and Codex-only installation has no Node dependency. A global `jj` or `bd` is neither required nor used as a substitute for the pinned mise-managed tools. Normal BBK execution resolves them through mise with automatic installation disabled.

## Preferred install path

Test and install Codex at user scope:

```bash
python tools/setup.py --test-and-install --scope user --codex
```

Then start a fresh Codex session and invoke `$bbk` when BBK control is wanted. The user-scoped install makes the skill and named agents available; it does not add a global instruction that activates BBK in every project.

Select another host or combine host flags:

```bash
python tools/setup.py --test-and-install --scope user --omp
python tools/setup.py --test-and-install --scope user --pi
python tools/setup.py --test-and-install --scope user --claude
python tools/setup.py --test-and-install --scope user --generic
python tools/setup.py --test-and-install --scope user --omp --codex --pi
```

Each install and update command runs the matching dependency preflight before tests or destination writes. Codex-only setup uses the Codex verification profile and does not invoke Node. OMP-only setup uses the OMP profile. A multi-host install uses the standard profile.

When no host flag is supplied, BBK selects all five targets: Codex, OMP, Pi, Claude Code, and generic agents.

All bundled language profiles are installed by default:

```text
go
python
rust
typescript-javascript
```

The compatibility front door delegates to the same setup path:

```bash
python tools/bootstrap.py --test-and-install --scope user --codex
```

## User and project scope

Use user scope for host definitions shared by the current operating-system account:

```bash
python tools/setup.py --install --scope user --codex
```

Use project scope for definitions owned by one repository:

```bash
python tools/setup.py --install --scope project --root /path/to/repository --codex
```

Project scope requires an explicit project root. A Codex project install also creates or updates a delimited, installer-managed BBK activation block in `<project>/AGENTS.md`. Existing user content outside that block is preserved; BBK does not replace the file wholesale. OMP project installations allow each repository to keep its own runtime routing state. Generic project agents are written under `<project>/.agents/bbk/agents`; Pi agents under `<project>/.pi/agents`; Codex agents under `<project>/.codex/agents`; OMP agents and extensions under `<project>/.omp`; and Claude Code agents and skills under `<project>/.claude`.

### DeepSeek Codex project actors (keyless)

For an isolated project actor lifecycle, set `CODEX_HOME` (or pass
`--codex-home`) and always select both a BBK role and a DeepSeek target. The
only supported targets are `deepseek-v4-pro` and `deepseek-v4-flash`; missing or
unknown role/target values fail closed. The lifecycle stores an environment
credential reference, never an API-key value:

```bash
python tools/codex_ds_lifecycle.py install --role bbk_worker --target deepseek-v4-flash --project /path/to/repository
python tools/codex_ds_lifecycle.py update --role bbk_worker --target deepseek-v4-pro --codex-home /path/to/project/.codex
python tools/codex_ds_lifecycle.py status --codex-home /path/to/project/.codex
python tools/codex_ds_lifecycle.py rollback --codex-home /path/to/project/.codex
python tools/codex_ds_lifecycle.py uninstall --codex-home /path/to/project/.codex
```

`reinstall` is an explicit replacement operation equivalent to `install` with
the predecessor recorded for rollback. The manifest and actor file are scoped
to that `CODEX_HOME`; no user Codex installation or global configuration is
modified.

For one explicit bulk mirror of the packaged OMP defaults, add
`--codex-use-packaged-omp-default-routing` to a Codex install. It stages and
commits all 19 role files as one local transaction, records
`MIRROR_CANONICAL_OMP`, and fails before mutation on a conflicting routing
source or per-agent lifecycle owner. The operation is keyless and does not
touch runtime OMP state, network endpoints, or credentials.

## Verify without installing

Use a host-focused profile when testing one integration:

```bash
# Codex contracts and installation; no Node dependency
python tools/setup.py --test --codex

# OMP contracts and JavaScript/runtime checks; Node required
python tools/setup.py --test --omp
```

Use the compact host-neutral profile while changing contracts or generated prompts:

```bash
python tools/setup.py --test-fast
```

Use the standard profile to check all supported hosts, or the exhaustive profile before a release:

```bash
python tools/setup.py --test
python tools/setup.py --release-test
```

The standard and release profiles include OMP, so their dependency preflight requires Node. `--require-node` remains accepted for compatibility but is redundant for those profiles.

The direct test runner is useful for diagnosis after dependency preflight has passed:

```bash
python tools/run_tests.py --profile fast -v
python tools/run_tests.py --profile standard -v
python tools/run_tests.py --profile release --all --require-node -v
```

`tools/verify_all.py` is the ordered verification wrapper used by `tools/setup.py`:

```bash
python tools/verify_all.py --profile codex
python tools/verify_all.py --profile omp --require-node
python tools/verify_all.py --profile standard --require-node
python tools/verify_all.py --profile release --require-node
```

The test runner emits bounded progress. After a quiet interval it prints a `still running` heartbeat with the current module or test line. Timing reports and duration caches stay outside the package by default.

## Preview before writing

Use `--dry-run` with either setup or the lower-level installer:

```bash
python tools/setup.py --install --scope user --codex --dry-run
python tools/install.py install --scope user --codex --dry-run
python tools/install.py --json install --scope user --codex --dry-run
```

A dry run prepares and verifies selected profile packages, renders generated material in memory, checks the complete destination plan, and reports the manifest path without creating it.

## Select language profiles

Install only named bundled profiles:

```bash
python tools/setup.py --test-and-install --scope user --codex \
  --profile-id rust \
  --profile-id python
```

Install BBK core without language profiles:

```bash
python tools/setup.py --test-and-install --scope user --codex \
  --no-language-profiles
```

`--no-language-profiles` cannot be combined with `--profile-id` or `--language-profiles`. A core-only install still writes the `bbk-installed-profiles` registry; it states that no language or domain profile is managed.

## Use another profile source

`--language-profiles PATH` replaces the bundled source for that invocation. Accepted sources include:

- one profile ZIP;
- one extracted profile package;
- a directory of extracted profile packages;
- a directory whose `packages/` children are extracted packages;
- an expanded profile repository with `REPOSITORY-MANIFEST.json`;
- a verified multi-profile release-bundle ZIP;
- an extracted verified release bundle.

For sibling BBK and `bbk-language-profiles` checkouts:

```bash
python tools/setup.py --test-and-install --scope user --codex \
  --language-profiles ../bbk-language-profiles
```

BBK verifies `REPOSITORY-MANIFEST.json` when present, then independently verifies each selected package. No repository-extraction script is needed; the installer consumes the expanded repository directly. The companion repository published with this release contains the same Go, Python, Rust, and TypeScript/JavaScript profile set as the public bundle. Because an explicit source replaces the bundled source, repeat `--language-profiles` only when combining two or more explicit sources.

The profile-focused wrapper uses bundled profiles when `--bundle` is absent:

```bash
python tools/install_profiles.py --scope user --codex
python tools/install_profiles.py --scope user --codex \
  --profile rust --profile python
python tools/install_profiles.py --bundle /path/to/profiles.zip \
  --scope user --codex
```

Repeat `--language-profiles` to combine explicit sources and repeat `--profile-id` to choose an exact subset.

## External model-routing policy

The packaged policy is [`../spec/model-routing.json`](../spec/model-routing.json). To use another valid v2 policy, keep it outside the verified extraction:

```bash
python tools/model_routing.py --path /path/to/model-routing.json --check
python tools/setup.py --install --scope user --omp --codex --claude \
  --model-routing /path/to/model-routing.json --dry-run
python tools/setup.py --install --scope user --omp --codex --claude \
  --model-routing /path/to/model-routing.json
```

`package_version` is optional provenance. The governing checks are `schema_version`, exact coverage of all 19 roles, and the required host route fields. See [`MODEL-ROUTING.md`](MODEL-ROUTING.md).

## Installed skills and agent definitions

For Codex, OMP, Pi, and generic targets, installable skills are written under the selected `.agents/skills` root. Claude Code receives them under `.claude/skills`. Codex receives the `$bbk` controller skill and Claude Code receives `/bbk`; invoke the appropriate skill in a fresh host session. OMP's identically spelled `/bbk` command activates extension-owned persistent mode rather than a discovered skill.

Controller compilation does not create a twentieth child agent. OMP consumes its compiled controller projection through extension-owned prompt replacement. Codex and Claude Code receive the controller through their installed `$bbk` and `/bbk` skill surfaces respectively, while their 19 generated `bbk_*` definitions remain non-user-facing child roles.

The `bbk-artifact` skill includes the semantic procedure, host metadata, a generic draft template, a reference, and Windows/POSIX wrappers. The wrapper resolves the nearest valid project install first and then the user install, and calls the exact recorded Python interpreter and installed `tools/bbk.py`.

User-scope Windows examples:

```powershell
# Codex, OMP, Pi, or generic skill root
$BbkArtifact = "$HOME\.agents\skills\bbk-artifact\scripts\bbk-artifact.cmd"

# Claude Code uses this root instead
# $BbkArtifact = "$HOME\.claude\skills\bbk-artifact\scripts\bbk-artifact.cmd"

& $BbkArtifact binding
& $BbkArtifact --help
```

A passing artifact operation establishes the recorded package bytes and declared closure only. It does not establish acceptance, authorization, validation, deployment readiness, or release authority.

## Existing installs

### PowerShell clean-replacement confirmation

Interactive Windows installs read the clean-replacement answer through the
native console input buffer rather than `sys.stdin.readline()`. This avoids a
PowerShell/Windows Terminal state where the prompt is visible but keyboard input
cannot reach Python's text stream. Press Enter for the default clean replacement,
or enter `n` and press Enter to preserve and reconcile the existing installation.

Automation should remain explicit: use `--uninstall-existing` to clean-replace or
`--keep-existing` to reconcile without a prompt. If native console input cannot
be opened, BBK fails safe by preserving the existing installation and prints the
explicit clean-replacement command-line option.

When BBK finds an existing managed install, interactive setup asks whether to clean-replace the selected surface or keep and reconcile it. For automation, choose explicitly:

```bash
python tools/setup.py --install --scope user --codex --uninstall-existing
python tools/setup.py --install --scope user --codex --keep-existing
```

`--uninstall-existing` and `--keep-existing` are mutually exclusive.

A partial clean replacement supports one already-installed OMP or Codex harness at a time and preserves peer harnesses. To change shared routing or language-profile state, perform a full replacement or an in-place reconciliation rather than a harness-only replacement.

The installer refuses locally changed managed files unless `--force` is explicit. It creates backups before replacing changed owned files. It does not delete unrelated files.

## Selective successor updates

Update only Codex after the package has passed the matching checks:

```bash
python tools/setup.py --test-and-update-codex --scope user
# Verified release only:
python tools/setup.py --update-codex --scope user
```

This updates Codex agent definitions and the installed `$bbk` and external optional skill surface. At project scope it also reconciles the managed BBK activation block in `AGENTS.md` without changing content outside that block. It preserves OMP, Pi, Claude Code, generic agents, installed profile packages, and the shared installed package state except for manifest records needed by the Codex update. Start a fresh Codex session after the update.

Update only OMP while Codex remains available:

```bash
python tools/setup.py --test-and-update-omp --scope user
# Verified release only:
python tools/setup.py --update-omp --scope user
```

The OMP-only updater preserves the active OMP runtime-routing profile and does not modify `.codex`, Pi, Claude Code, or generic agent files. After it succeeds, run:

```text
/reload-plugins
```

See [`UPGRADING.md`](UPGRADING.md) for full upgrade and rollback steps.

## Preparation and write boundary

Before the first destination write, BBK:

1. rejects unsafe or ambiguous archive paths, links, special files, collisions, and excessive expansion;
2. verifies the outer bundle or repository inventory when present;
3. independently verifies each selected profile package;
4. validates profile identity, compatibility, and install paths;
5. validates and renders role, prompt, return-contract, and routing projections;
6. constructs one complete core-and-profile destination plan;
7. rejects conflicting file ownership or executable-mode requirements;
8. checks destination drift, backup behavior, and the exact selected harness scope.

Only after that no-write preflight passes does installation begin. The install manifest records the resulting ownership and verification state.

## Host permission is not BBK authority

Generated Codex custom agents omit a fixed `sandbox_mode` and inherit the parent turn's sandbox and approval choices. This lets non-mutating roles write notes, evidence, handoffs, and other coordination artifacts when the parent permits it.

Host write access does not authorize subject or product artifacts. BBK role scope and the exact invocation grant still control those changes. Set the parent host to read-only when no child should write even coordination artifacts.

## Progress and machine-readable output

Human-readable setup streams ordered gate, test, profile, preflight, and write progress. `--json` suppresses those progress messages so stdout remains valid JSON. Errors include the failed boundary and the smallest safe next step when one is known.

## Installed layout

The user data root is:

```text
Windows: %LOCALAPPDATA%\BBK
macOS:   ~/Library/Application Support/BBK
Linux:   ${XDG_DATA_HOME:-~/.local/share}/bbk
```

It contains the versioned package copy, `install-manifest.json`, effective routing and profile registries, backups, and any user-scope launcher. Host files are installed in their native user or project paths:

```text
Codex agents:       ~/.codex/agents                or <project>/.codex/agents
OMP agents:         ~/.omp/agent/agents            or <project>/.omp/agents
OMP extension:      ~/.omp/agent/extensions/bbk    or <project>/.omp/extensions/bbk
Pi agents:          ~/.pi/agent/agents             or <project>/.pi/agents
Claude Code agents: ~/.claude/agents               or <project>/.claude/agents
Generic agents:     ~/.agents/bbk/agents           or <project>/.agents/bbk/agents
Shared skills:      ~/.agents/skills               or <project>/.agents/skills
Claude skills:      ~/.claude/skills               or <project>/.claude/skills
Codex activation:   (none at user scope)            or <project>/AGENTS.md managed block
```

After any install or update, start a fresh session in the affected host so it reloads skills and agent definitions. For OMP, reload the extension before starting that fresh session.

The exact `bbk-installed-profiles` registry is written to each selected skill root. `effective-language-profiles.json` provides the machine-readable installation record. Use `bbk --json profile list` to inspect the active profile registry.

## Status and removal

```bash
python tools/install.py status --scope user
python tools/install.py uninstall --scope user
```

Status compares managed file digests and, on POSIX, expected executable modes. Uninstall removes only unchanged manifest-owned files. It reports locally changed files and preserves them unless `--force` is explicit.

## Reuse of unchanged profile files

Every selected profile source is authenticated before BBK compares it with an existing install. Reuse requires the same profile ID, package version, package-root SHA-256, layout version, selected host set, every owned file digest, and each applicable executable mode.

A matching profile may be adopted without copying its files again. Any missing, changed, mode-divergent, or locally modified file follows the normal repair, refusal, backup, and `--force` rules. A matching version label alone never grants reuse.

## OMP after installation

Reload OMP plugins after installing or updating its extension, then enter persistent BBK mode:

```text
/reload-plugins
/bbk
```

Mode state is session-local and recorded with `appendEntry`. While active, `before_agent_start` performs Main and child system-prompt replacement, and named BBK children remain non-user-facing. This does not change the parent model, host tool access, or filesystem containment. See [`USAGE.md`](USAGE.md), [`OMP-CHILD-LIFETIME.md`](OMP-CHILD-LIFETIME.md), and [`../omp/extension/README.md`](../omp/extension/README.md).

## Qualification boundary

Package verification checks BBK's own files, contracts, projections, fixtures, and tests. It does not prove that a selected model is capable, a host accepts every model identifier or hook, an outside toolchain works, the target project is correct, or a person or organization granted real authority. Qualify the exact host, model, and toolchain combination before consequential use. See [`BOUNDARIES.md`](BOUNDARIES.md).
