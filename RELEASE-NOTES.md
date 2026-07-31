# BBK 0.1.0-alpha.11.12 release notes

Alpha.11.12 is the immutable Windows-portability and qualification successor to
alpha.11.11. It carries forward alpha.11.11's repository-native source tree,
consolidated documentation, 19-role method, model-routing policy, installer
contracts, `.bbk/` record formats, and mixed-version bundled profile set. The
revision changes the BBK package identity so the corrected archive is no longer
published by replacing an earlier artifact under the same version.

## Repository-native source and documentation boundary

The alpha.11.11 **Repository-native source** contract is unchanged: the
extracted BBK package root remains the canonical Git source tree and contains
everything required to develop, verify, install, and rebuild the release.

The public documentation inventory remains **14 current** durable documents.
Historical PRDs, per-alpha migration notes, internal alignment material, and
release-specific qualification transcripts remain outside the source tree in
the separate **pre-public history** artifact. No repository extractor or
post-release staging-tree workflow is reintroduced.

## Windows verification-console correction

The unittest runner, ordered verifier, and installation verification gate now
transport child output safely on native Windows consoles:

- Python verification children use deterministic UTF-8 standard streams;
- undecodable child bytes remain visible as ASCII escape sequences rather than
  becoming an unprintable replacement character;
- characters unsupported by the active console code page are escaped without
  forcing a global console-encoding change;
- a still-running suite is terminated before capture-file cleanup; and
- transiently locked capture logs are removed with bounded retries, while
  exhausted cleanup remains best-effort and cannot mask the actual test result.

Regression coverage includes strict CP1252 output, valid Unicode, invalid UTF-8
bytes, a running child, and both transient and persistent simulated Windows
sharing violations.

## Windows filesystem identity and optional tooling

BBK now centralizes two deliberate path identities in `tools/path_compat.py`:

- **native physical identity** follows host filesystem semantics and collapses
  long/8.3 Windows aliases, case aliases, junctions, and symlinks for live
  installation and selective-update ownership checks;
- **portable install-plan identity** additionally normalizes slash spelling and
  case on every host, preventing a plan created on Linux or macOS from carrying
  destinations that would collide when installed on Windows.

The Codex-only and OMP-only update paths, installed OMP model routing, and core
installer use the appropriate shared identity. Tests cover not-yet-created
leaves beneath an existing short-name parent and case-only portable collisions.

Schema-validator tests now recognize both supported states: `PASS` when the
optional `jsonschema` runtime is available, and structured `BLOCKED` with exit
code 1 when it is absent. An isolated `python -S` regression verifies that the
blocked-state contract does not depend on user-site packages or `PYTHONPATH`.

## Native Windows release gate

The source tree includes `tools/windows_compat.py` and
`.github/workflows/windows-verification.yml`. The native probe exercises:

- case-insensitive aliases;
- 8.3 aliases when enabled on the volume;
- directory-junction identity; and
- real Win32 sharing-violation cleanup after an exclusive handle is released.

The Windows CI matrix runs Python 3.11 and 3.13, the native probe, all ordered
verification stages, the complete unittest suite, and a second unittest pass
under strict CP1252 output. Unsupported 8.3 generation or junction creation is
reported as `NOT_APPLICABLE`; available behavior must pass.

## Bundled profiles and compatibility

The bundled profile inventory is unchanged:

- CODESYS `0.1.0-alpha.4`;
- Go `0.1.0-alpha.3`;
- Python `0.1.0-alpha.3`;
- Rust `0.1.0-alpha.3`; and
- TypeScript/JavaScript `0.1.0-alpha.3`.

All five inner archives remain independently manifested and byte-identical to
the alpha.11.11 bundle. No `.bbk/` project-record migration is required.
External model-routing overrides must bind `package_version` to
`0.1.0-alpha.11.12` when used with this release.

Use a new empty extraction directory. For a normal verified user installation:

```powershell
python tools\windows_compat.py
python tools\bootstrap.py --test-and-install --scope user --omp --codex --claude
```

See `docs/INSTALL.md`, `docs/UPGRADING.md`, and `docs/DEVELOPMENT.md` for the
managed-install, selective-update, and repository workflows.
