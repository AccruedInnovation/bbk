# Prefilled credentialed/full-harness tests

The exact RC archive and gate inputs are packaged beside this document. Run `prepare-codex-fixtures.ps1`; it writes and prints complete commands containing the resolved Codex executable and disposable fixture paths.

- `MH-CODEX-01`: `fixtures/worker`, prompt `prompts/MH-CODEX-01-PRIMARY.md`.
- `MH-CODEX-02`: paste `prompts/MH-CODEX-02-FOLLOWUP.md` into the same MH-CODEX-01 conversation.
- `MH-CODEX-03`: `fixtures/rolling-wave`, prompt `prompts/MH-CODEX-03-ROLLING-WAVE.md`.
- `MH-CODEX-04` through `MH-CODEX-06`: use the named prefilled prompts after the principal gates or in separate disposable conversations.

Analyze an exported log with:

```powershell
.\analyze-codex-run.ps1 -TestId MH-CODEX-01 -LogPath "C:\exact\path\to\rollout.jsonl"
```

The script supplies the Alpha.17 analyzer configuration, exact compiled manifest, effective catalog, readiness fixture, projected Worker prompt, and output paths. No API key belongs on the command line.

OMP 16.4.8 qualification is established by the approved RC9 provider campaign. The separately packaged Alpha.17 final OMP kit is retained for post-release regression. Pi/generic static projection parity is automated; a credentialed Pi provider run remains `USER_ACTION_REQUIRED` because no Pi harness binary or authenticated runtime was supplied to the implementation environment.
