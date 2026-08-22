# Deterministic BBK Tooling PRDs

**Status:** Proposed implementation blueprint

**Scope:** deterministic tooling that removes mechanical JSON assembly and lifecycle-admission churn without transferring semantic authority to tools

## Outcome

This package defines the smallest reusable toolchain needed to turn explicit, accepted BBK semantics into mechanically closed execution and assurance records. Tools may compile structure, reference closure, identities, receipts, currentness, and non-averaging dispositions. They must not invent requirements, architecture, authority, findings, acceptance, deployment, or release decisions.

The execution-admission compiler is assumed to be implemented by an existing parallel effort. The remaining required PRDs make its immutable receipt usable through result assembly, gate aggregation, candidate freeze, validation, and completion reporting. Later hardening PRDs cover planning, Territory boundaries, explicit authority recording, and an optional artifact-draft convenience layer.

## PRD index

| ID | PRD | Commands | Priority | Direct dependencies |
|---|---|---|---|---|
| A | [Execution admission compiler](A-execution-admission-compiler.md) | `bbk admission compile`, `bbk admission verify` | External/in progress | Accepted graph, authority, atomic finalizer |
| B | [Worker-result assembler](B-worker-result-assembler.md) | `bbk result assemble worker` | Required | A |
| C | [Gate receipt normalization and aggregation](C-gate-receipt-aggregation.md) | `bbk gate record`, `aggregate`, `verify` | Required | CandidateRef contract; A for execution identity |
| D | [Canonical candidate freezer](D-canonical-candidate-freezer.md) | `bbk candidate freeze`, `verify`, `invalidate` | Required | C; artifact tooling |
| E | [Candidate-bound validation compiler](E-candidate-bound-validation-compiler.md) | `bbk validation compile` | Required | C, D; AssuranceContract |
| F | [Completion-readiness compiler](F-completion-readiness-compiler.md) | `bbk completion report` | Required | B, C, D, E |
| G | [Lifecycle qualification fixture](G-lifecycle-qualification-fixture.md) | qualification fixture and negative controls | Required | A–F |
| H | [Planning bundle compiler](H-planning-bundle-compiler.md) | `bbk plan compile` | Later hardening | J; planning transaction and Beads tooling |
| I | [Territory-boundary compiler](I-territory-boundary-compiler.md) | `bbk boundary compile`, `admit`, `verify`, `successor` | Later hardening | H or accepted graph; J |
| J | [Authority and decision recorder](J-authority-decision-recorder.md) | `bbk authority record`, `bbk decision accept` | Later hardening | Explicit accountable disposition |
| K | [Artifact draft helper](K-artifact-draft-helper.md) | `bbk artifact draft create`, `add` | Optional | Existing artifact-package engine |

## Dependency graph

```text
J ────┐
     ├─→ H ─→ I
     └─→ A ─→ B ──────────┐
          └─→ C ─→ D ─→ E ──├─→ F ─→ G
               └────────────┘

K is independent convenience tooling over the existing artifact engine.
```

## Parallel implementation waves

| Wave | Parallel tracks | Exit condition |
|---|---|---|
| 1 | A; B scaffolding; C schema normalization; D design; J | Stable admission, result, gate, CandidateRef, and authority interfaces |
| 2 | B completion; C aggregation; D implementation; E and F design | Candidate can be frozen from complete current receipts |
| 3 | E and F implementation; H and I implementation if funded | Candidate-bound validation and completion records compile deterministically |
| 4 | G end-to-end qualification | Positive lifecycle and all material negative controls pass |
| 5 | K only if repeated draft-authoring evidence justifies it | No duplicate manifest, checksum, seal, or finalization implementation |

## Shared requirements

Every command in this package must:

1. Use checked-in deterministic operations and schemas.
2. Resolve all owned paths beneath an explicitly admitted workspace root.
3. Keep temporary directories, caches, schema stores, and command streams inside that root unless an explicit authority record permits otherwise.
4. Perform schema resolution offline; a remote reference fails before network access.
5. Preserve complete stdout, stderr, exit status, command identity, tool identity, environment identity, and invalidation keys where execution occurs.
6. Use canonical UTF-8/LF serialization and the existing atomic finalizer for standalone JSON identities.
7. Keep finalized content acyclic: the content never inventories its own bytes or digest; a detached sidecar carries its raw identity.
8. Treat stale, missing, duplicated, malformed, tampered, wrong-subject, wrong-context, inconclusive, or required-not-run evidence as non-pass.
9. Preserve semantic authority: tools validate and compile explicit inputs but never invent authority, findings, acceptance, deployment, publication, or release decisions.
10. Produce stable failure fingerprints keyed by exact gate and subject identity so circuit breakers operate on normalized failures rather than narrative similarity.
11. Provide focused known-bad controls for every material fail-closed claim.
12. Remain compatible with mandatory Beads coordination through checked-in `tools/bbk.py` and mise-managed Beads; raw `bd` and `jj` are outside these PRDs.

## Existing components to reuse

- `tools/bbk.py` for the public command surface.
- `tools/atomic_finalizer.py` for standalone JSON finalization and detached identity receipts.
- `tools/role_return_runtime.py` and `tools/return_contracts.py` for bound role-return envelopes.
- `tools/artifact_packages.py` for package manifests, checksums, sealing, freshness, verification, and succession.
- `tools/handoff_packages.py` for sealed handoff construction and verification.
- `tools/planning_optimization.py` for transactional planning state.
- `tools/review_assurance.py` and `tools/context_packages.py` for assurance and candidate-bound context compilation.
- `tools/substrate/beads_adapter.py` for mandatory coordination effects routed by `tools/bbk.py`.

## Explicit exclusions

- No new public test profile.
- No per-test desiderata database.
- No replacement artifact checksum or sealing engine.
- No automation that invents qualitative findings or accountable decisions.
- No conversion of Beads into semantic authority.
- No broad rewrite of existing historical `.bbk` evidence solely to adopt these tools.
