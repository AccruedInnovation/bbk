# Alpha.17 RC9 credentialed Codex qualification

This is the exact operator procedure for the real Codex gates that cannot be established in the implementation sandbox. Use the deterministic `bbk-0.1.0-alpha.17+rc.9-codex-manual-qualification-kit.zip`; it contains the exact RC archive, package manifest, fixed fixtures, prefilled prompts, Worker compiled manifest, effective catalog, readiness record, projected Worker TOML, JSONL analyzer, and hard-gate evaluator.

## Preparation

Extract the Codex kit into a new directory and open Windows PowerShell there:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\prepare-codex-fixtures.ps1
```

The script verifies the embedded RC archive, creates two disposable Git repositories, installs RC9 into project scope with `--codex --no-language-profiles`, records status, and prints the exact authenticated Codex commands. It does not start Codex and does not place a provider credential on the command line.

## Principal release gates

### MH-CODEX-01 — compiled Worker procedure

Copy the printed MH-CODEX-01 command. It runs the prefilled `prompts/MH-CODEX-01-PRIMARY.md` against the disposable `fixture-worker` repository.

Required outcome:

- exactly one `bbk_worker` child;
- one compiled procedure block at the final prompt tail;
- primary procedure absent from the effective external catalog;
- zero filesystem reads/searches of `shared/skills/bbk-work-unit-execution/SKILL.md`;
- unrelated optional skills remain available;
- `input.txt` and `python check.py` pass;
- no sealed handoff, planning/design/review/verification-design fan-out, or external effect.

### MH-CODEX-02 — unchanged follow-up reuse

In the same Codex conversation, paste `prompts/MH-CODEX-02-FOLLOWUP.md` unchanged. It must use `followup_task` on the same logical Worker, reuse the compiled set, perform zero source reads, append the exact follow-up line, and avoid reinitializing planning or assurance.

### MH-CODEX-03 — rolling-wave continuation

Copy the separately printed MH-CODEX-03 command. It runs `prompts/MH-CODEX-03-ROLLING-WAVE.md` against `fixture-rolling-wave`.

Required outcome:

- `FAST_CONTINUATION` and `ADOPT_AND_GAP`;
- `ROADMAP_READY + FRONTIER_READY` without `FULLY_COMPILED` as a prerequisite;
- phase 1 exact and executing;
- later phases `DEFERRED_UNTIL_FRONTIER` with refinement triggers;
- no routine Worker Designer, Verification Designer, Reviewer, Researcher, Architect, or new planning cycle;
- project coverage marks only the frontier scope complete.

## Supplemental tests

The kit includes prefilled prompts for:

- `MH-CODEX-04`: Worker/Verification Designer exception triggers;
- `MH-CODEX-05`: safe evidence-capture replay and negative controls;
- `MH-CODEX-06`: metadata-only validator suppression, one relevant final validation, and project coverage.

## Analyze the raw logs

For each exported/raw JSONL path:

```powershell
.\analyze-codex-run.ps1 -TestId MH-CODEX-01 -LogPath "C:\exact\path\to\rollout.jsonl"
.\analyze-codex-run.ps1 -TestId MH-CODEX-02 -LogPath "C:\exact\path\to\rollout.jsonl"
.\analyze-codex-run.ps1 -TestId MH-CODEX-03 -LogPath "C:\exact\path\to\rollout.jsonl"
```

The wrapper supplies every analyzer and gate input. Preserve `summary.md`, `summary.json`, `skill_reads.csv`, `commands.csv`, `warnings.csv`, `structured_event_summary.csv`, and `alpha17-gate-report.json`.

## Result and rollback

Complete `RESULT-TEMPLATE.md` and `RESULT-RECORD-TEMPLATE.json`, changing `template` to `false`. Then remove only the managed BBK project installations:

```powershell
.\rollback-codex-fixtures.ps1
```

The disposable project files and evidence are preserved.

The operator result must bind the exact RC9 archive SHA-256 in the kit. Any changed candidate requires a new run. These tests produce evidence for Alpha.17 release authorization; they do not authorize final release by themselves.
