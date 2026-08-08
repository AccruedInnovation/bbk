Run the BBK Alpha.17 rolling-wave continuation acceptance fixture in this disposable repository.

Use Root Wayfinder continuation mode with the accepted outcome, architecture, roadmap, and current state in `accepted/`. Default to `FAST_CONTINUATION` and `ADOPT_AND_GAP`; do not request full future planning. Produce a planning-readiness record that is `ROADMAP_READY` and `FRONTIER_READY`, with phase 1 slice `WU-RW-001` exact and executable. Keep phases 2 and 3 coarse and `DEFERRED_UNTIL_FRONTIER` with stable IDs, owners, dependencies, interfaces, risks, and refinement triggers.

Begin execution of `WU-RW-001` while future work remains deliberately uncompiled. The Worker must create `delivered/frontier.txt` with exactly `frontier-executed` plus one LF and run `python check.py`. Routine contract and assertion generation must be deterministic: do not spawn Worker Designer, Verification Designer, Reviewer, Researcher, Architect, or another planning cycle unless a typed material trigger is produced. Return project coverage that marks only the frontier slice complete and leaves later phases partial/not started.

Preserve the raw Codex JSONL log and report readiness, first Worker start, deferred future work, specialist invocations, and project coverage. Do not claim whole-project completion or Alpha.17 final authorization.
