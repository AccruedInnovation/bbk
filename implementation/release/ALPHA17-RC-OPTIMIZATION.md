# Alpha.17 RC9 Optimization, Dispatch, and Integration Reliability Implementation

**Version:** `0.1.0-alpha.17+rc.9`
**Scope:** bounded final-RC continuation of the accepted Alpha.17 architecture

## Implemented behavior

RC9 preserves the accepted RC6 critical-path behavior and the RC7 real-provider-proven native dispatch lifecycle into canonical generated policy and adds compiled procedures, rolling-wave planning, deterministic routine contracts, atomic finalization, bounded evidence replay, late-bound runtime identity, project-coverage truth, transactional planning state, and JSONL gate analysis.

### Compiled procedures

- Canonical procedure sources remain under `shared/skills/<procedure-id>/SKILL.md`.
- `spec/procedures/catalog.json` records stable IDs, versions, source digests, dependencies, eligible roles, and selection metadata.
- The prompt compiler emits the selected dependency closure once in a closed block at the end of each child prompt; the primary procedure is the final procedure body.
- The same compiled IDs are removed from that child’s effective external catalog and from automatically indexed installed skill roots.
- Unchanged follow-ups reuse the retained manifest, prompt, and catalog without reading procedure files. Recompilation occurs only after a declared invalidation key changes.

### Rolling-wave continuation

- Planning modes: `FAST_CONTINUATION`, `STANDARD`, `FULL_GOVERNED`.
- Architecture modes: `ADOPT_AND_GAP`, `DELTA`, `FULL`.
- Readiness states: `ROADMAP_READY`, `FRONTIER_READY`, `FULLY_COMPILED`.
- `ROADMAP_READY + FRONTIER_READY` admits the exact current slice while future phases remain `DEFERRED_UNTIL_FRONTIER` with refinement triggers.
- Routine Worker and assertion contracts are deterministic projections. Worker Designer and Verification Designer require typed material triggers.

### Transactional planning state

`bbk plan transact` stages an immutable semantic event transaction, regenerates owned projections, writes one transaction receipt, and swaps `current.json` last as the authoritative pointer. Lock conflict is retryable; a failed final pointer swap restores the prior projections/log/head. Legacy plans are preserved and receive an additive migration anchor rather than an in-place rewrite.

### Atomic results and manifests

`bbk result finalize` and `bbk manifest finalize` validate and canonicalize UTF-8/LF JSON, stage the output and identity receipt, and publish the pair atomically. A failed receipt publication restores the exact prior pair or leaves no new pair.

### Evidence-capture replay

A capture-only failure may receive exactly one replay when the semantic invocation is identical, the first physical attempt completed successfully, effects are proven `NONE`, cleanup is `COMPLETE`, the command is read-only or disposable-idempotent, and the candidate is not frozen. Mutating, unknown-effect, cleanup-uncertain, changed-invocation, frozen-candidate, and second-failure cases fail closed without successor planning.

### Runtime identity, workspace admission, and project coverage

Planning records semantic profile constraints; runtime admission emits the effective identity. An equivalent effective digest does not reopen planning. Workspace admission receipts permit delta checks while the bound baseline/protected tree/invalidation keys remain current. Candidate results and whole-project completion are separate machine-readable claims.

### Coordination and observability

Typed child events represent started, milestone, blocked, return-ready, failed, and cancelled states. Event delivery is preferred; hosts without a complete event API retain a long blocking wait and a 300-second minimum interval for nonblocking probes. The standalone JSONL analyzer recognizes the new transitions and evaluates the compiled-procedure, catalog-suppression, zero-read, follow-up-reuse, and rolling-frontier hard gates.


## RC8 bounded dispatch correction

RC8 canonicalizes compact native task integrity after OMP host normalization, makes the dispatch token authoritative, folds initial Beads assignment into `bbk_control_spawn`, enforces logical-attempt uniqueness independently of idempotency keys, serializes preparation while retaining parallel child execution, and records durable READY/LEASED/ACTIVATED/TERMINAL lifecycle state. Failed native launches release the same token for bounded retry; evaluator/shell/Python dispatch emulation is blocked before effect.

## Retained floors

RC8 does not weaken authority-bound effects, mutation ownership, external-effect controls, candidate immutability, product validation, evidence truth, or completion-claim separation. It retains the RC5 compact token dispatch, stable root binding, exact two-parent integration, integrated-candidate admission, structured-return-first enforcement, and evaluator-fallback prohibition.

## Deferred post-RC item

`WU-A17-OPT-017`, a canonical candidate workspace/jj overlay/copy-on-write redesign, remains a successor candidate. RC8 does not introduce a new workspace architecture.

## RC8 bounded integration correction

RC8 canonicalizes every jj changed path at the shared adapter boundary to a validated repository-relative POSIX path. Windows separators therefore cannot cause a false integration nonpass, while absolute, traversing, drive-qualified, control-bearing, or ambiguous paths still fail closed. Content-neutral integration refreshes isolated Worker workspaces only; the root workspace carrying `.bbk` coordination metadata is not an integration source.

`bbk_control_integrate_request` derives the current Beads revision internally. An exact retry uses the revision bound by the immutable idempotency record, removing model-authored revision guessing without weakening the single-writer or idempotency contract. The RC8 session analyzer records a named poll denied before effect as an efficiency finding rather than an executed polling violation, and redaction requires a genuine left token boundary so BBK receipt/schema identifiers remain intact.


## RC9 validated role-return correction

RC9 makes the role-return contract a pre-effect host boundary rather than a prompt-only convention. Every governed child `yield` is validated against the exact role-specific recursive Draft 2020-12 schema and the active immutable invocation identity before OMP accepts it. The active-binding comparison covers role and invocation mode, subject and revision, semantic run and physical attempt, actual child session, parent identity and route, authority reference, and allowed effect classes.

`bbk_return_template` returns the exact bound contract, allowed controlled values, compact/full result fields, and a minimal example. `bbk_return_prepare` accepts the role-specific facts as structured tool fields, constructs the common envelope, validates the result, stores one immutable prepared-return record, and returns the complete immutable `yield_input`. The OMP hook validates that exact full document against the binding-owned prepared record before acceptance; JSON-string fields remain compatibility-only. A malformed, misbound, or unprepared reconstructed return is blocked with focused JSON-pointer diagnostics and may be repaired in the same attempt; it is never accepted as a parent result.

The qualification analyzer now traverses nested child sessions, validates admitted Worker, Reviewer, and Validator returns, identifies redundant deterministic reads/hashes after current receipts, and generates the machine result record. Only the operator redaction attestation and narrative remain manual. RC9 leaves the proven RC7/RC8 dispatch, retry, jj path, integration, candidate-admission, polling, and redaction semantics unchanged.
