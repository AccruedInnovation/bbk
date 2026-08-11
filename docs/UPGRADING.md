# Upgrading BBK

## Upgrade to `0.1.0-alpha.17.0.2.1`

`0.1.0-alpha.17.0.2.1` supersedes `0.1.0-alpha.17.0.2` as the public Alpha.17 source successor. It keeps the accepted dependency, host-integration, and qualification contracts while removing the obsolete hotfix companion note and aligning source metadata. It does not alter the immutable Alpha.17 or Alpha.17.0.2 archives or rewrite existing `.bbk` project records.

Use Python 3.11 or newer. Check the dependencies for the host you plan to install:

```powershell
python tools/setup.py --check-dependencies --codex
python tools/setup.py --check-dependencies --omp
```

The check is offline, disables mise automatic installation, and changes no BBK installation files. To install missing core dependencies after reviewing the plan:

```powershell
python tools/setup.py --install-dependencies --codex --dry-run
python tools/setup.py --install-dependencies --codex
python tools/setup.py --install-dependencies --omp
```

Python itself and the selected host app remain separate prerequisites. The opt-in bootstrap can install Git, mise, the exact jj and Beads versions, BBK's Python schema packages, and the pinned Node runtime when OMP is selected. Codex-only setup and verification do not require Node.

Verify the extracted package before replacing an installation:

```powershell
python tools/verify_package.py --strict-mode
python tools/setup.py --test --codex
```

Use `python tools/setup.py --test --omp` for OMP, `python tools/setup.py --test` for the routine cross-host profile, or `python tools/setup.py --release-test` for release qualification. Standard and release verification include OMP and therefore require Node.

Install one or more selected hosts from the same package identity:

```powershell
python tools/setup.py --install --scope user --codex --uninstall-existing
python tools/setup.py --install --scope user --omp --codex --pi --claude --generic --uninstall-existing
```

After the replacement, start a fresh session in every updated host. Codex enters BBK through `$bbk`; Claude Code uses its installed `/bbk` skill. OMP's identically spelled `/bbk` command activates extension-owned persistent mode instead. A user-scoped Codex upgrade makes `$bbk` available without globally activating BBK.

For project scope:

```powershell
python tools/setup.py --install --scope project --root D:\Project --codex --uninstall-existing
```

For project-scoped Codex, the installer reconciles a delimited BBK activation block in `AGENTS.md` and preserves all user-authored content outside that block. Start a fresh Codex session in the project after the upgrade.

With no host flag, the installer selects all five targets, which includes OMP and its Node requirement. Missing selected host commands are reported as warnings because BBK may prepare projections before those hosts are installed. Missing core dependencies block before tests, destination reads, or writes and produce the exact bootstrap command.

Status records include the dependency preflight plus per-harness prompt compiler, controller/role projection, catalog, routing, and adapter metadata. Controller projections are not additional child agents: OMP consumes the compiled controller through its extension, while Codex and Claude Code receive it through their installed `$bbk` and `/bbk` skill surfaces respectively. Treat mixed package/projection identities as an explicit drift condition rather than assuming semantic parity.

Package-owned canonical sources classified `COMPILED_ONLY` or `COMPILER_SELECTABLE` normally remain outside model-discoverable skill directories. The controller's `$bbk` skill is the deliberate Codex/Claude delivery surface, not permission to copy the package's complete `shared/skills/` tree into `.agents/skills` or another host autoload root. Other installed procedures remain limited to the catalogued external skill surface.

Rollback is a clean replacement with a preserved predecessor package. Qualification evidence applies only to the exact package bytes it records; changed Alpha.17.0.2.1 bytes need their own live-provider evidence when that claim is required.

## Upgrade to `0.1.0-alpha.17`

`0.1.0-alpha.17` is the Alpha.17 final release and supersedes all Alpha.17 release candidates. Use a clean extraction. Preserve any active user- or project-scope installation until the new package passes strict verification and the requested harness projections install successfully.

Alpha.17 final retains the native token-addressed dispatch lifecycle, same-token retry, Windows path normalization, two-parent content-neutral integration, candidate admission, persistent mode, event-oriented child completion, compiled-once procedures, current-until-invalidated receipts, same-attempt mechanical repair, and pre-effect role-return schema/identity validation established across RC7 through RC9.

The final delta from RC9 is evidence-tooling-only:

- the Windows installer probes Python/jsonschema through a temporary source and result file rather than multiline `python -c`;
- the collector uses the same Windows-safe temporary-source strategy for the jsonschema version record;
- the session analyzer prefers complete assistant-message arguments over filtered host projections and counts rejected-then-corrected return preparations as same-attempt repairs;
- response-ID redaction requires ID-like entropy and no longer corrupts ordinary identifiers such as `call_succeeded` or `call_reason_code`.

No existing `.bbk` record is rewritten. Existing role-return, handoff, receipt, dispatch, integration, candidate, planning, and procedure records remain readable through the documented additive compatibility paths. The package version changes from `0.1.0-alpha.17+rc.9` to `0.1.0-alpha.17`; routing import compatibility continues to be governed by `schema_version`, with `package_version` optional provenance.

Install from the extracted final package:

```powershell
python tools/setup.py --install --scope user --omp --codex --claude --uninstall-existing
```

For a project-scoped replacement:

```powershell
python tools/setup.py --install --scope project --root D:\Project --omp --codex --claude --uninstall-existing
```

Verify before and after installation:

```powershell
python tools/verify_package.py --strict-mode
python tools/setup.py --test --require-node
python tools/install.py --json status --scope user
```

Rollback uses the ordinary uninstall path followed by reinstalling the preserved predecessor archive. Keep any release-specific restoration evidence with the archived predecessor and release records; it is not part of this source package.

The final release is qualified for OMP 16.4.8 by the approved Windows/provider campaign. It does not claim OMP 17.2.9 qualification or credentialed Codex/Pi behavioral parity.
