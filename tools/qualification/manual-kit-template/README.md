# BBK Alpha.17 @BBK_RC_LABEL@ provider qualification kit

This kit reproduces the user-run `VER-037` and `VER-038` campaign for the exact
package below. For a release candidate it supplies evidence to the separate
`VER-039` release decision. For Alpha.17 final it is a post-release regression
kit and does not change or broaden the release authorization.

- Package: `@BBK_VERSION@`
- Package archive SHA-256: `@BBK_ARCHIVE_SHA256@`
- Package-root SHA-256: `@BBK_PACKAGE_ROOT_SHA256@`
- Qualified OMP host: `omp/16.4.8`
- mise-managed tools: `jj@0.43.0` and `github:gastownhall/beads@1.1.0`

## Prerequisites

The operator must have these commands available:

- Python 3.11 or newer;
- Git;
- mise;
- OMP 16.4.8 with the intended provider authentication already configured.

A global `jj` or `bd` installation is neither required nor used. For ordinary BBK setup, `tools/setup.py --install-dependencies --omp` can install the declared dependencies. This qualification kit keeps its own tool state isolated: its installer copies the kit's `mise.toml` into the isolated project, sets isolated
`MISE_DATA_DIR`, `MISE_CACHE_DIR`, and `MISE_CONFIG_DIR` paths, runs
`mise install`, and invokes the pinned tools only through `mise exec`.

`mise install` may contact the tool registries when the pinned versions are not
already cached. This is an operator bootstrap effect performed before the OMP
session; agents remain prohibited from network retrieval and dependency
installation.

## Safety boundary

The scripts install BBK only into a new, dedicated project directory. They do
not replace, update, or uninstall the active user-scope BBK installation. The
isolated mise state is also placed under the qualification root. The start
script uses the operator's existing OMP provider configuration without copying
credentials into the evidence directory.

## Procedure

1. Extract this complete kit into a normal local directory outside an existing
   project.
2. Open Windows PowerShell 5.1 or PowerShell 7 in that directory.
3. Run:

   ```powershell
   Set-ExecutionPolicy -Scope Process Bypass
   .\install-isolated-rc.ps1
   ```

   Supply explicit `-Python`, `-Git`, `-Mise`, or `-Omp` paths only when those
   commands are not already on `PATH`. There are intentionally no `-Jj` or
   `-Bd` parameters. The script records direct operator-tool identities and the
   mise-managed tool specs, versions, managed paths, and digests; it never
   records credential values.
4. Generate the exact launch command. The start script validates the isolated
   install and writes one copy-and-pasteable PowerShell command to
   `evidence/launch-alpha17-qualification-command.ps1`. It deliberately does
   **not** start OMP:

   ```powershell
   .\start-alpha17-qualification.ps1
   ```

   Optional examples:

   ```powershell
   .\start-alpha17-qualification.ps1 -Model "provider/model"
   .\start-alpha17-qualification.ps1 -OmpProfile "existing-profile-name"
   ```

   Copy the emitted command block into a PowerShell terminal and execute it
   manually. The command applies the empty configured-extension overlay,
   disables skill and rule discovery, and explicitly loads the exact package
   extension followed by the qualification helper. OMP 16.4.8 must not be
   launched with `--no-extensions`, because that host version incorrectly
   suppresses explicit extension paths as well.

   Wait for the notification **BBK extension verified and persistent mode activated**.
   If OMP exits immediately or that notification does not appear, preserve the
   emitted command and failure. Do not invoke `/bbk`, do not load the skill as a
   substitute, and do not modify the emitted command except by regenerating it
   with the documented `-Model` or `-OmpProfile` parameters.

   Do not pass an API key on the command line. Use the provider authentication
   already configured for OMP or its normal environment-variable mechanism.
5. In the fresh OMP session, paste the complete contents of
   `EXACT-OMP-PROMPT.md`. When asked to accept the exact two-work-unit baseline,
   choose **Accept and proceed**. Do not intervene when deliberate negative
   tests return structured blocks. Any other material question is a gate
   blocker; record it rather than improvising authority.
6. Export the completed OMP session to HTML using OMP's normal export command.
7. Collect evidence. Native warnings on stderr are captured as evidence and do not terminate the collector when the process exit code is zero. The collector also writes `session/session-admission.json`; a missing mode/prompt receipt or a skill fallback is preserved as a truthful nonpass rather than discarded:


   ```powershell
   .\collect-evidence.ps1 -SessionHtml "C:\path\to\omp-session-export.html"
   ```
8. Redact and package it:

   ```powershell
   .\redact-and-package.ps1
   ```

   The collector has already generated `RESULT-RECORD.json` from the full
   analyzer, populated all machine-observable invariants, validated every child
   return, and evaluated duplicate deterministic checks. Manually inspect the
   generated redacted directory and checksummed ZIP, then complete only the
   human `redaction_attestation` fields in `RESULT-RECORD.json`. Complete
   `RESULT-TEMPLATE.md` only for concise operator context. Do not edit
   `RESULT-RECORD-TEMPLATE.json`, and do not modify the ZIP after its checksum
   is made.
9. Restore the isolated scope:

   ```powershell
   .\rollback-isolated-rc.ps1
   ```

   Rollback removes only manifest-owned project-scope BBK files. The isolated
   mise tools remain under the qualification root until
   `-RemoveQualificationDirectory` is used after evidence preservation.

## Return to the release agent

Return all four items:

- completed `RESULT-TEMPLATE.md`;
- analyzer-populated `RESULT-RECORD.json` with the manual redaction attestation completed;
- redacted evidence ZIP and its `.sha256` file;
- the redacted OMP HTML export contained in that ZIP.

Do not return API keys, provider tokens, credential files, cookies, raw
environment listings, or an uninspected evidence bundle.
