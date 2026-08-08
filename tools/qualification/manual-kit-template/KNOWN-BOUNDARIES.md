# Known boundaries

This campaign establishes only the real Windows OMP/provider behavior for
BBK Alpha.17 @BBK_RC_LABEL@. It does not establish an operating-system sandbox,
deployment, publication, live product acceptance, or official Blueprint
authority.

## Toolchain boundary

- Python, Git, mise, and OMP are operator prerequisites.
- The project `mise.toml` owns `jj@0.43.0` and
  `github:gastownhall/beads@1.1.0`.
- The installer uses isolated `MISE_DATA_DIR`, `MISE_CACHE_DIR`, and
  `MISE_CONFIG_DIR` paths under the qualification root and runs `mise install`.
  Network access may occur only during that operator bootstrap when tools are
  not cached.
- Normal BBK, harness, and evidence commands invoke jj and Beads through
  `mise exec`. No global `jj` or `bd` executable is required or authoritative.
- `mise` is a qualified task/tool vocabulary, not an authorization system.

## Enforcement boundary

- OMP 16.4.8 is the qualified pre-effect host. Other OMP versions are
  `UNQUALIFIED` until separately tested.
- Built-in OMP `write`, `edit`, and `bash` are expected to be blocked before
  effect in `governed-software` mode. Effects outside OMP-mediated hooks remain
  `DETECT_ONLY` or `UNQUALIFIED`.
- Workers receive exact work-unit, attempt, session, workspace, jj change,
  authority, path, mutation-class, toolchain, and return-contract bindings.
- Every governed child return is intercepted at the OMP `yield` pre-effect
  boundary. BBK validates the declared role-specific Draft 2020-12 schema and
  the active work-unit, attempt, session, parent, authority, and effect-fence
  identity before OMP can accept it. Malformed returns are blocked with focused
  JSON-pointer diagnostics and may be repaired in the same attempt.
- `bbk_return_template` and `bbk_return_prepare` are the routine construction
  path. The latter persists an immutable validated return and supplies a small
  binding-scoped token; the model does not hand-author the common envelope.
- Reviewers and validators are candidate-read-only. Their deliberate writes
  must block.
- Beads state may be changed only through the BBK control-plane adapter during
  the campaign. The operator's one-time mise-mediated `bd init` is setup, not
  an agent effect.
- Critical-path optimization does not weaken authority, safety, security,
  protected-floor, candidate-freeze, or truthful-claim requirements.

## Qualification-only bootstrap and integration bridge

Alpha.17's product surface requires an active parent binding, but OMP does not
supply the eventual session ID before session start. OMP 16.4.8 incorrectly
suppresses explicit extension paths when `--no-extensions` is present. The kit
therefore applies `omp-qualification-overlay.yml`, whose empty `extensions`
array replaces configured extension discovery, disables skill and rule
discovery through CLI flags, and explicitly loads
`manual-bootstrap-extension.mjs` after the exact package extension. The helper
requires the extension-owned runtime marker, activates persistent BBK mode, and
fails closed when mode or prompt-integrity receipts are absent. It then creates one
root-orchestrator binding from the host-supplied session ID, exact project root,
Git baseline, current capability digest, qualified host version, and
mise-managed jj identity. It writes a typed bootstrap receipt and exposes no
generic mutation tool.

The helper also exposes `bbk_manual_qualification_integrate`, a narrow bridge to
the package's content-neutral jj adapter. The root bootstrap is create-once and
parent-aware: child session starts observe but cannot replace the top-level root
identity. The bridge accepts only that stable root plus the predefined Worker A
and Worker B attempts, verifies exact disjoint paths and exact source parents,
denies conflict resolution, creates a sibling integration workspace, freezes
it, and issues a candidate-admission receipt. Any integration nonpass records a
failure receipt and forbids downstream candidate binding. Reviewer and Validator
bindings for an integrated candidate require the exact current admission
receipt. The ordinary `bbk_control_integrate_request` remains request-only and derives its current Beads revision internally; the model-facing tool does not expose `expectedRevision`.
Evidence must distinguish the product request from this qualification bridge.

These bridge operations are part of the manual harness, not ordinary Alpha.17
user-facing tools. Their source and digests are included in returned evidence.
The start script is also deliberately not a process runner: it validates the
install and emits the exact PowerShell environment/invocation block for the
operator to execute manually.

## Claim limits

A passing result supports that the exact package ran under the user's real
provider path, all sixteen manual invariants were observed, mise owned jj/Beads,
and the returned evidence passed redaction. Release labeling remains a separate
operator decision. For Alpha.17 final, this kit supplies post-release regression
evidence and cannot broaden the final release's documented host/provider claims.


## Coordination boundary

OMP task results and IRC messages are event-delivered. The RC blocks specific-job polling and rate-limits successful nonblocking list/inbox/roster probes to one per 300 seconds while BBK children remain active. A pre-effect denied specific-poll attempt is retained as an efficiency finding but is not a status observation or session-admission failure. A blocking empty job wait or IRC wait is allowed. Five minutes of silence permits one observation but is not evidence of failure, cancellation, or restart.
