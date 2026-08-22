# PRD G — Lifecycle qualification fixture

**Status:** Proposed

**Owner kind:** deterministic qualification maintainer; acceptance remains with the accountable controller/release process
**Priority:** Required

## Problem and repository evidence

PRDs [A](A-execution-admission-compiler.md) through [F](F-completion-readiness-compiler.md) form one ordered lifecycle, but isolated unit tests cannot prove cross-command candidate binding, staleness propagation, atomic finalization, offline behavior, or non-authoritative completion semantics. The repository already uses checked-in qualification fixtures and known-bad evidence controls, and `tools/verify_all.py` distinguishes STANDARD from RELEASE with explicit currentness requirements. A hermetic lifecycle fixture is needed before these deterministic commands can become admission gates.

This PRD creates a repository-owned positive scenario plus mandatory known-bad controls. It tests tools and schema wiring; it does not certify a product candidate or authorize a BBK release.

## Goals

- Exercise A–F in order from accepted fixture inputs to a non-authoritative completion-readiness report.
- Prove exact predecessor, CandidateRef, currentness, protected-byte, authority, and cleanup binding across every step.
- Run all material negative/fault controls hermetically, including STANDARD-to-RELEASE evidence-reuse safety.
- Produce a reproducible qualification report and retained per-case raw evidence.

## Non-goals

- Running deployment, publication, production services, live credentials, or remote dependencies.
- Treating fixture pass as semantic acceptance of arbitrary candidates or authorization to release BBK.
- Adding a new public test profile or replacing focused unit/integration suites.
- Making the fixture’s expected outputs semantic authority for future schema changes.

## Callers

- Repository maintainers during local/CI qualification.
- `tools/verify_all.py` as an internal named check once stable.
- Release evidence assembly as one candidate-bound toolchain qualification input, never as the release decision itself.

## Command surface and exact examples

```powershell
python tools/bbk.py qualification deterministic-lifecycle --fixture tests/fixtures/deterministic-lifecycle/positive --work-root .bbk/qualification/lifecycle --output .bbk/qualification/lifecycle/report.json
python tools/bbk.py qualification deterministic-lifecycle --fixture tests/fixtures/deterministic-lifecycle/controls --case wrong-candidate --work-root .bbk/qualification/wrong-candidate --output .bbk/qualification/wrong-candidate/report.json
python tools/bbk.py qualification deterministic-lifecycle --fixture tests/fixtures/deterministic-lifecycle/controls --all-negative --work-root .bbk/qualification/negative --output .bbk/qualification/negative/report.json
```

The harness invokes the public `python tools/bbk.py` surfaces for A–F in subprocesses, captures complete stdout/stderr/exit status, and validates every output with the checked-in schema registry offline.

## Inputs and schemas

- A checked-in positive fixture containing accepted graph/authority inputs, a bounded workspace, B worker-return inputs, deterministic gate definitions, accepted AssuranceContract, profile/environment/method/independence inputs, finding/disposition inputs, cleanup evidence, and protected-byte declaration.
- A control catalog whose entries specify base fixture, one mutation/fault, expected failing stage, allowed diagnostic code(s), prohibited claims, and expected preserved artifacts.
- Tool, Python, schema-registry, platform, and fixture-tree identities.
- Existing A–F schemas plus a new `bbk.deterministic-lifecycle-qualification.v1` report schema.

Fixture files use canonical UTF-8/LF and relative paths. Remote `$ref`, executable download, and ambient network dependency are forbidden. Timestamps/seeds are explicit inputs.

## Outputs and finalization

The report contains qualification ID, fixture/tool/schema/environment digests, ordered step attempts, each command and exit status, produced carrier identities, positive assertions, negative-control results, unexpected residuals, final disposition, and claims-not-established. Each control retains raw stdout/stderr and copied immutable inputs under its case directory.

Allowed overall dispositions are `PASS`, `FAIL`, `BLOCKED_ENVIRONMENT`, and `ERROR`. `PASS` requires the positive case and every mandatory negative control to produce its expected fail-closed result. The report is atomically finalized with a detached identity receipt; retained evidence may additionally use the existing generic artifact package.

## Functional requirements

1. Materialize every case into a fresh explicit work root and prove all writable paths stay beneath it.
2. Run A, B, C, D, E, and F through their public CLI in dependency order; no direct Python helper may bypass a public boundary being qualified.
3. Verify each intermediate schema, detached receipt, subject/digest binding, and expected state before launching its consumer.
4. Record the exact command, environment allowlist, cwd, start/end, exit status, stdout, stderr, and produced file identities.
5. Keep the positive candidate immutable after D freeze and require E/F to reproduce its CandidateRef exactly.
6. Assert that positive F output is only `READY_FOR_PARENT_DISPOSITION` and contains all mandatory claims-not-established.
7. For every negative control, prove the expected stage refuses admission/readiness and does not publish a later-stage success carrier.
8. Require the following named controls: `stale-predecessor`, `wrong-candidate`, `post-admission-mutation`, `missing-or-inconclusive-gate`, `self-cycle`, `outside-root`, `remote-ref-without-network`, `post-freeze-mutation`, `stale-standard-receipt-reused-by-release`, and `failed-validation-presented-as-completion`.
9. `stale-predecessor` changes an immutable predecessor after a successor request and expects currentness rejection.
10. `wrong-candidate` substitutes a valid receipt from another fixture and expects exact subject mismatch.
11. `post-admission-mutation` changes workspace bytes after A admission and before B/C/D consumption; all affected successors must fail closed.
12. `missing-or-inconclusive-gate` runs both absent required receipt and `INCONCLUSIVE` variants; neither may aggregate/freeze/complete as pass.
13. `self-cycle` introduces a package or evidence reference to itself and expects cycle rejection before finalization.
14. `outside-root` uses traversal, absolute path, and link/junction escape variants without touching the external sentinel.
15. `remote-ref-without-network` supplies an HTTPS schema/artifact reference, denies network, and expects deterministic offline rejection with zero connection attempt.
16. `post-freeze-mutation` alters source/protected bytes after D publication and expects candidate verification and F readiness to become stale/blocked.
17. `stale-standard-receipt-reused-by-release` supplies a previously passing STANDARD receipt whose required-equal identity differs from RELEASE; reuse must be rejected and the existing full-RELEASE fallback semantics preserved, never reported as RELEASE pass.
18. `failed-validation-presented-as-completion` supplies a schema-valid failing ReviewAggregate alongside otherwise passing inputs; F must refuse ready disposition.
19. Inject at least one crash/fault between staging and atomic publication for A–F writable commands and prove no partial final output is admitted.
20. Compare repeated positive runs after removing normalized volatile fields; canonical carriers and case outcomes must match.
21. Leave the source fixture unchanged and reconcile processes, locks, temporary directories, caches, and other effects for every case.
22. Fail qualification on missing control, unexpected pass, prohibited claim, unverified evidence, dirty source fixture, or unexplained residual.

## State and ordering

Harness state is `DISCOVERED -> PREFLIGHTED -> POSITIVE_RUNNING -> POSITIVE_VERIFIED -> CONTROLS_RUNNING -> CONTROLS_VERIFIED -> CLEANUP_VERIFIED -> FINALIZED`.

Each case follows `MATERIALIZED -> MUTATION_ARMED -> STEPS_RUN -> EXPECTATION_COMPARED -> RESIDUALS_RECONCILED -> RECORDED`. Cases may run in parallel only in distinct work roots after preflight; their reports are aggregated in stable catalog order. A missing positive prerequisite prevents dependent controls but is recorded as `BLOCKED_ENVIRONMENT` or `ERROR`, never pass.

## Failure semantics

An expected command rejection is a control pass only when the stage, diagnostic class, absence of prohibited output, preserved sentinels, and cleanup all match. Process timeout, silence, exception, schema error, or harness crash is not an expected rejection unless the control explicitly injects that exact fault. Unexpected partial outputs are quarantined and inventoried. The harness does not delete evidence needed for diagnosis and never labels an unrun control passed.

## Security and authority

Run with a minimal environment, fake credentials, network denied, no production endpoints, and all mutations inside per-case roots. Outside-root sentinels are read-only and verified unchanged. Subprocess argv is constructed without shell interpolation. Fixture authority grants only local disposable effects; neither harness nor report grants acceptance, deployment, publication, or release authority.

## Compatibility and migration

Keep the fixture additive and versioned. Existing `verify_all` STANDARD/RELEASE profiles remain canonical; the stale-reuse control calls or fixtures their existing reuse decision rather than duplicating it. Schema evolution requires readers-first support or a new fixture version with explicit migration expectations. Historical reports stay immutable and are never used for a changed tool/schema/fixture identity.

## Observability

Emit concise live case/state events and a final structured report with durations, command identities, carrier digests, expected/actual diagnostics, network-attempt count, sentinel status, residual inventory, cleanup status, determinism comparison, and stable failure fingerprints. Raw logs are referenced rather than embedded; secret-like values are rejected/redacted.

## Test strategy and negative/fault controls

The qualification fixture is itself tested with unit tests for catalog completeness, mutation operators, expectation matching, claim prohibition, and report canonicalization. A smoke test runs the positive case plus one negative control on each supported platform. The full CI test runs all ten mandatory controls and atomic-publication faults. Meta-tests deliberately weaken each oracle and verify the harness detects the weakness. Windows coverage includes case-folding, junctions, and locked files; POSIX coverage includes symlinks and mode changes. Network denial is observed, not merely asserted.

Mandatory expected outcomes:

| Control | Expected rejection |
|---|---|
| stale predecessor | successor/currentness verification |
| wrong candidate | CandidateRef/subject binding |
| post-admission mutation | first consuming admission/currentness check |
| missing/inconclusive gate | C aggregation and all downstream admission |
| self cycle | reference-closure preflight |
| outside root | path-resolution preflight; sentinel unchanged |
| remote ref without network | offline reference resolution; zero connection attempts |
| post-freeze mutation | D verification and F protected-byte/currentness checks |
| stale STANDARD reused by RELEASE | reuse decision; full RELEASE fallback required |
| failed validation presented as completion | F validation reconciliation |

## Acceptance criteria

1. The positive fixture executes public A–F commands in order and produces a verifiable non-authoritative readiness report.
2. All intermediate consumers reproduce exact predecessor and CandidateRef identities.
3. All ten named negative controls run and fail closed at the expected boundary.
4. No negative case publishes a valid downstream success receipt or ready completion report.
5. The stale STANDARD/RELEASE control proves stale reuse rejection and does not weaken existing full-RELEASE fallback behavior.
6. The remote-reference control records zero network attempts, and outside-root controls leave sentinels unchanged.
7. Atomic fault controls leave no admitted partial output and report all residual staging state.
8. Repeated positive runs are canonically equivalent and source fixtures remain unchanged.
9. Qualification PASS includes no claim of semantic acceptance, deployment readiness, publication, or release authority.

## Dependencies and consumers

Dependencies: [PRD A](A-execution-admission-compiler.md), [PRD B](B-worker-result-assembler.md), [PRD C](C-gate-receipt-aggregation.md), [PRD D](D-canonical-candidate-freezer.md), [PRD E](E-candidate-bound-validation-compiler.md), [PRD F](F-completion-readiness-compiler.md), checked-in schema registry, atomic finalizer, artifact tooling, and existing STANDARD/RELEASE reuse logic in `tools/verify_all.py`.

Consumers: local/CI verification, release evidence assembly, and maintainers diagnosing lifecycle contract regressions. A passing report is evidence for these consumers, not authority.

## Rollout

Land fixture schema/catalog and positive case first, then mandatory identity/path/offline controls, then mutation and atomic-fault controls. Run initially as an informational CI job, stabilize platform variance, promote to a required internal check, and only then reference it from broader release qualification. Do not add a public test profile.

## Risks and open questions

- Public A–F command names must be frozen before golden report identities become stable.
- Filesystem race injection must be deterministic enough for CI without weakening the real lock/currentness assertions.
- Network-denial instrumentation differs by platform; the evidence method must prove no attempt rather than relying only on policy.
- Full end-to-end subprocess coverage can be expensive; maintain a small positive fixture and parallel isolated controls while preserving deterministic aggregation.

## Estimate

9–14 engineer-days: fixture/report harness 3–4, positive lifecycle 2–3, ten controls 3–5, cross-platform/fault stabilization 1–2.
