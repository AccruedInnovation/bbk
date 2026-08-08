# Alpha.17 final provider gate and authorization

## Decision

The RC9 Windows/provider campaign is accepted for `VER-037`, and the release operator explicitly approved the reviewed evidence and authorized Alpha.17 final on 2026-08-06 after the corrected analyzer report and operator attestation were reviewed.

## Established results

- OMP host: `16.4.8`.
- M17 invariants: `16/16 PASS`.
- Structured role returns: `PASS`; four prepared returns admitted and no unvalidated successful yield accepted.
- Same-attempt role-return repairs: `5`.
- Duplicate deterministic checks: `0`.
- Integration candidate: `sha256:d38b3c438a2c35f4c6a62a005cf6ce4f4d6b685e1d7b44f81df86c34b0cdbe09` with exactly two parents and the two expected paths.
- Redaction scanner: `PASS`; manual inspection completed; credential values returned: `false`.
- Evidence ZIP SHA-256: `f4fc0939735865d8ef929505f0e21b3f844bc90952e94d890c0b7e5b46213cbf`.
- Corrected machine result: `evidence/qualification/alpha17-rc9-result-record-approved.json`.
- Corrected session analysis: `evidence/qualification/alpha17-rc9-session-admission-corrected.json`.

## Final-package corrections

The final source includes the approved evidence-tooling fixes: complete assistant-message tool arguments take precedence over filtered host projections, same-attempt prepare repairs are counted, response-ID redaction requires ID-like entropy, and Windows Python probes use temporary source files rather than multiline `python -c`.

## Claim limits

Alpha.17 final is qualified for the packaged implementation and OMP 16.4.8 provider path established above. It does not claim OMP 17.2.9 qualification or credentialed Codex/Pi behavioral parity.
