# BBK 0.1.0-alpha.17.0.2.1

- Removed the retired internal `IMPLEMENTATION-MAPPING-CHECKLIST-COMPLETED.md` artifact and its stale evidence references from the public package.

- Corrected native Windows qualification isolation: runtime mise resolution is now explicit/PATH-only, batch-launcher assertions understand `cmd.exe /c`, byte-exact fixtures force LF, and real-mise qualification uses isolated Windows and mise state directories with network/auto-install/lockfile effects disabled.
- Corrected the PowerShell clean-replacement prompt: native Windows console input bypasses the stalled `sys.stdin.readline()` path, setup preserves stdin, and unreadable confirmation fails safe to reconciliation.
 release notes

## Release relationship

Alpha.17.0.2.1 is a source successor to `0.1.0-alpha.17.0.2`. It keeps the accepted Alpha.17 planning, execution, prompt-compilation, host-integration, record, and public-profile contracts while publishing the Windows qualification hotfix as ordinary release-source metadata. No `.bbk/` record migration is required. Install from a clean extraction rather than overlaying an older package tree. The predecessor `.2` qualification evidence remains immutable and is explicitly limited to predecessor-source evidence; it does not requalify current `.2.1` VER-035 or provider behavior.

## Source successor corrections

- Remove the obsolete `HOTFIX-ALPHA17.0.2-WINDOWS.md` package companion; historical release notes and external qualification evidence remain preserved outside the current package surface.
- Align canonical metadata, generated projections, templates, qualification-kit identity, and exact-version regression fixtures on `0.1.0-alpha.17.0.2.1`.

## Dependency setup

- Standardize BBK core on Python 3.11 or newer and enforce that floor before loading setup, install, update, verification, release, or package tooling.
- Add an offline, non-installing dependency preflight at `python tools/setup.py --check-dependencies`.
- Add an explicit opt-in installer at `python tools/setup.py --install-dependencies` with a dry-run plan, interactive consent, and `--yes` for automation.
- Install Git and mise through supported platform package managers or mise's official user-local installer where needed.
- Install the exact package pins `jj@0.43.0` and `github:gastownhall/beads@1.1.0` through mise.
- Declare and install the Python runtime requirements `jsonschema>=4.25.1,<5` and `referencing>=0.36.2,<1` for the active interpreter.
- Keep the root `mise.toml` limited to jj and Beads, and place `node@22.23.2` in the non-default `tools/omp-runtime.mise.toml` so ordinary root mise tasks cannot acquire a Node cross-dependency.
- Install that package-pinned Node runtime through mise only when OMP is selected. A compatible direct Node 22 or newer is also accepted for OMP.
- Report selected host applications as non-blocking warnings. BBK does not install or update Codex, OMP, Pi, Claude Code, generic host software, or language-profile toolchains.

## Safe dependency checks

- Run dependency preflight before tests, existing-install inspection, prompt rendering, or destination writes.
- Disable mise network use and automatic install paths during checks.
- Resolve pinned tools with `mise which`, then execute the resolved binary directly.
- Reject unsupported Windows `PATHEXT` source-file matches and run `.cmd` or `.bat` launchers through `COMSPEC`.
- Check exact jj, Beads, and managed Node versions rather than accepting substring matches.
- Enforce single-part bounds such as Node `22+` and Python package upper bounds such as `<5`.
- Keep dependency checks non-installing and offline, and return one host-scoped repair command when they block.

## Host-focused verification

- Add dedicated `codex` and `omp` verification profiles.
- Make Codex-only setup, update, and verification independent of Node.
- Keep OMP JavaScript syntax and runtime checks in the OMP, standard, and release profiles.
- Make Windows batch mode execute the profile-selected module list directly instead of importing every test module before case filtering.
- Select the smallest automatic profile for one-host installs: Codex, OMP, or the host-neutral fast profile. Multi-host installs use the standard profile.
- Move Alpha.17.0.2 dependency regression coverage into its own small test module rather than adding work to the large installation-portability module.
- Add a static import-closure check so new third-party Python dependencies cannot enter `tools/` without being declared.
- Add an OMP runtime-file closure check so copied Python modules cannot depend on omitted local modules.

## Installer and doctor corrections

- Make setup and selective update entry points use the same dependency contract.
- Preserve the canonical unified install manifest during harness-scoped replacement rather than overwriting it with a user-facing summary object.
- Treat `BLOCKED`, `ERROR`, and missing mise-managed tools as failing overall doctor states.
- Keep dependency and verification environments explicit so test fixtures do not inherit accidental tools from the qualification host.
- Align native Windows CI with the same declared contract by provisioning mise, running the opt-in dependency installer for Codex plus OMP, and then running the non-installing dependency check before compatibility probes.

## Documentation

- Update the root README, install guide, usage guide, upgrade guide, development guide, and analyzer metadata for Python 3.11+, the opt-in dependency installer, exact managed versions, host-app boundaries, and Node's OMP-only scope.
- State that omitting all host flags selects all five projection targets and therefore includes OMP and Node.
- Keep the public profile set dynamic and limited to Go, Python, Rust, and TypeScript/JavaScript in this release.

## Repository-native documentation boundary

Repository-native source remains the authority for current operating guidance. The `docs/` directory contains 16 current top-level guides plus its task-based index; pre-public history stays outside that current-facing surface. No `.bbk/` project-record migration is required for Alpha.17.0.2.

## Compatibility and claim limits

- Existing Alpha.17 and Alpha.17.0.1 role-return, handoff, receipt, dispatch, integration, candidate, planning, profile, prompt-compilation, and project records remain readable through their declared compatibility paths.
- The dependency bootstrap changes local developer tools only after explicit consent. It does not grant release, deployment, remote-system, credential, or host-application authority.
- Package verification proves the checked BBK bytes and deterministic contracts only. Qualify the selected host, model, credentials, language toolchain, and target project separately before consequential use.
