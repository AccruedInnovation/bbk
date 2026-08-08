# BBK Alpha.17 @BBK_RC_LABEL@ Codex manual qualification

This kit proves the behavioral gates that require the operator's authenticated Codex environment. It does not place credentials on a command line or copy credential stores into evidence.

## Candidate

- Version: `@BBK_VERSION@`
- RC archive SHA-256: `@BBK_ARCHIVE_SHA256@`
- Package-root SHA-256: `@BBK_PACKAGE_ROOT_SHA256@`

## Sequence

1. Open Windows PowerShell in this directory.
2. Run `Set-ExecutionPolicy -Scope Process Bypass`.
3. Run `./prepare-codex-fixtures.ps1`.
4. Copy and execute the printed Codex command for `MH-CODEX-01`.
5. In that same Codex conversation, paste `prompts/MH-CODEX-02-FOLLOWUP.md` unchanged.
6. Start the separately printed `MH-CODEX-03` command in the rolling-wave fixture.
7. Export or locate each raw Codex JSONL log.
8. Run `./analyze-codex-run.ps1 -TestId MH-CODEX-01 -LogPath <PATH>` and repeat for the follow-up/rolling-wave log as directed.
9. Complete `RESULT-TEMPLATE.md` and `RESULT-RECORD-TEMPLATE.json`.
10. Run `./rollback-codex-fixtures.ps1` after evidence is copied.

The preparation script installs only into disposable project scope and prints commands; it does not start Codex.
