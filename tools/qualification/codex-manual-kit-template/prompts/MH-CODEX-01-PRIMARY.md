Run the BBK Alpha.17 compiled-procedure acceptance fixture in this disposable repository.

Use the installed canonical BBK orchestration path and launch exactly one `bbk_worker` child for `WU-MH-CODEX-01`. The WorkUnit is already executable and its four blocking facts are current:

- exact scope: edit only `input.txt` and return to Main;
- authority/effect fence: workspace-local text edit and local Python check only;
- mutation ownership: this one Worker owns `input.txt` for the attempt;
- required inputs/toolchain/return route: existing `input.txt`, `python check.py`, structured return to Main.

The Worker must replace the file content with exactly `alpha17-compiled-procedure-pass` plus one LF, run `python check.py`, and return structured completion. It must not read `shared/skills/bbk-work-unit-execution/SKILL.md`, search for that procedure source, invoke a discovered copy of that procedure as an external skill, create a sealed handoff, commission planning/design/review/verification-design work, or use network/external effects.

Capture the child identity and compiled-procedure manifest/catalog evidence supported by the installed Codex agent projection. Preserve the raw Codex JSONL log. Report only the WorkUnit outcome and exact evidence locations; do not claim Alpha.17 final authorization.
