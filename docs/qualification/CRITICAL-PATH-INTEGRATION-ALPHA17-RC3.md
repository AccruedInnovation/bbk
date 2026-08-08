# Alpha.17 RC3 critical-path integration report

**Package:** `0.1.0-alpha.17+rc.3`  
**Status:** `PASS`  
**Manual provider gate:** `PENDING_USER_RUN`

## Integrated deltas

- `mise.toml` is the canonical owner of `jj@0.43.0` and `github:gastownhall/beads@1.1.0`; normal BBK execution uses `mise exec`, so global `jj` and `bd` installations are not required.
- The supplied 19-role `bbk.model-routing.v2` policy is the exact canonical default. `package_version` is optional provenance on imported routing files; `schema_version` governs compatibility.
- The critical-path execution rules are canonical prompt/runtime/test contracts, including four-fact Worker admission, current-until-invalidated receipt reuse, same-attempt pre-freeze mechanical repair, structured-return-first transport, validator scoping, grouped INLINE assurance, and planning stop.
- Shared prompt modules are compiler-deduplicated. The four hot-path skills total **67,609 bytes**, within the supplied **67,878-byte** hotfix budget.

## Qualification

| Profile | Result | Tests | Skips |
|---|---:|---:|---:|
| Fast | PASS | 227 | 1 |
| Standard | PASS | 576 | 2 |
| Release | PASS | 598 | 2 |

- Recursive schema inventory: **195 schemas / 195 unique `$id` values**.
- `VER-036`: **PASS**.
- `GATE-017-AUTOMATED`: **RC_ELIGIBLE**.
- Verification-economy replay: Alpha.16 baseline reproduces **6** expected budget violations; the Alpha.17-compliant pattern has **0**.

## Remaining gate

`VER-037` remains a user-operated Windows OMP/provider test. Alpha.17 final remains unauthorized until that evidence is returned and admitted.
