# BBK delta

This pinned source is provenance and review material only. BBK does not run
the upstream installer or activate its hooks, skills, prompts, agents,
provider, credentials, or routes from this directory.

BBK-owned behavior is additive and activation-neutral:

- `spec/codex-external-targets.json` records explicit DeepSeek V4 Pro and V4
  Flash targets and provider capabilities as `CONFIGURED_UNQUALIFIED`.
- `spec/schemas/bbk-codex-external-target-registry-v1.schema.json` validates
  the registry without changing the existing model-routing policy.
- `tests/test_codex_external_targets.py` validates schema, target identity,
  provenance closure, and protected-routing invariants.
- `docs/MODEL-ROUTING.md` documents selection as explicit-only; no default or
  active role route is changed.

The upstream 33 tracked files are pinned to commit
`c949e8d9b8922a48990b1e08259ad4baefc75f55`. One file is an explicit,
reproducible BBK transformation: `tests/test_plaintext_handoff.py` changes
exactly 14 `.read_text()` calls to
`.read_text(encoding="utf-8")` under transformation
`codex-ds-plaintext-handoff-explicit-utf8-v1`. Its immutable upstream SHA-256
is `3f5c47b78b6038b964e06e30fc18490ba52b591fb207dc458ff233f231047cd8` and
its transformed local SHA-256 is
`77ec4c343866918f91815ef7ca031901601d041a1cb44bdb1e4c9418c239da85`.
`UPSTREAM-FILE-MAP.csv` and `UPSTREAM.json` are the canonical identity and
operation records. Any future adaptation must create a new revision and
preserve this predecessor's file map and license evidence.
