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

The upstream 33 tracked files are copied byte-for-byte at commit
`c949e8d9b8922a48990b1e08259ad4baefc75f55`. Any future adaptation must create
a new revision and preserve this predecessor's file map and license evidence.
