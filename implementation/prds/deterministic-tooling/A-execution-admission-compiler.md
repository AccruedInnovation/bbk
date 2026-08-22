# PRD A — Deterministic Execution Admission Compiler

| Field | Value |
|---|---|
| Status | Proposed; canonical implementation contract |
| Owner kind | Deterministic execution/evidence tooling maintainer |
| Priority | P0 / execution safety blocker |

## Problem and evidence

An accepted work graph is not itself a safe process-launch contract. Execution needs a mechanical boundary that proves the selected WorkUnit, governing objects, currentness observations, workspace ownership, dirty prestate, physical tools, environment, and return route are mutually consistent before any Worker is launched.

The checked-in `tools/execution_admission.py` already provides the semantic nucleus: strict offline schema closure, recursive governing-reference verification, independent selector/currentness checks, known-successor rejection, Git plus physical inventory, exact dirty-path reconciliation, closed environment construction, `bbk.worker-contract.v2` compilation, R0/R1 endpoint drift checks, detached atomic identity receipts, pre-launch R2 guards, complete stdout/stderr capture, effect reconciliation, failure fingerprints, and breaker projection. `spec/schemas/bbk-execution-admission-request-v1.schema.json`, `bbk-execution-admission-v1.schema.json`, `bbk-worker-contract-v2.schema.json`, and the regression tests in `tests/test_execution_admission.py` are current evidence. The module intentionally lacks a CLI; callers otherwise risk reimplementing selection, counters, and publication inconsistently.

## Goals

- Compile one exact Worker contract from one selected WorkUnit in an accepted, current work graph.
- Fail closed on stale predecessors, omitted known successors, incomplete reference closure, endpoint drift, undeclared dirt, ambiguous ownership, or tool drift.
- Emit an immutable admission document plus detached identity receipt that agents consume byte-for-byte without reinterpretation.
- Inventory dependencies and preserve raw command streams, stable failure fingerprints, and breaker counters for bounded retry decisions.
- Keep all schema resolution, temporary state, and caches local and network-inert.

## Non-goals

- Accepting a plan, work graph, risk, candidate, or release.
- Designing WorkUnits, choosing a Worker model, granting authority, or expanding effects.
- Providing an OS sandbox, proving network prevention, or proving descendant termination; the current compiler explicitly disclaims these.
- Running arbitrary shell text, resolving executables through ambient `PATH`, fetching schemas, installing dependencies, or repairing dirty state.
- Replacing [worker result assembly](B-worker-result-assembler.md) or [gate receipt aggregation](C-gate-receipt-aggregation.md).

## Users and callers

Primary callers are `bbk_worker_designer`, `bbk_worker_orchestrator`, `bbk_territory_orchestrator`, and harness adapters immediately before Worker dispatch. Workers and agents are downstream consumers only: they receive the finalized `worker_contract` and admission identity unchanged.

## Command surface

The thin CLI adapter SHALL expose these subcommands over the existing Python API aliases `compile`, `verify`, `run`, and `inspect`:

```text
python tools/execution_admission.py compile --root D:\repo --request D:\repo\.bbk\admission\WU-17.request.json --output D:\repo\.bbk\attempts\WU-17\admission.json --git C:\Program Files\Git\cmd\git.exe
python tools/execution_admission.py verify --root D:\repo --admission D:\repo\.bbk\attempts\WU-17\admission.json
python tools/execution_admission.py run --root D:\repo --admission D:\repo\.bbk\attempts\WU-17\admission.json --command-id test-unit --evidence-root D:\repo\.bbk\attempts\WU-17\evidence\test-unit-01 --breaker-events D:\repo\.bbk\attempts\WU-17\breaker-events.json
python tools/execution_admission.py inspect --admission D:\repo\.bbk\attempts\WU-17\admission.json --breaker-events D:\repo\.bbk\attempts\WU-17\breaker-events.json
```

Arguments are arrays passed directly to `subprocess` with `shell=False`; examples are illustrative physical paths, not permission to search or widen roots. JSON success goes to stdout, one JSON diagnostic goes to stderr, exit `0` means operation PASS, `2` means typed rejection, and `3` means internal/tooling failure. No subcommand prompts or retries.

## Required inputs and schemas

`compile` requires a strict `bbk.execution-admission-request.v1` document. Its required fields remain canonical: `admission_id`, positive `attempt`, `subject`, `work_unit_id`, `accepted_baseline_ref`, `accepted_work_graph_ref`, nonempty `authority_refs`, `source_guard_refs`, `lineage_only_refs`, exact repository path, workspace attempt root/mutation owner/owned roots/dirty entries, physical command argv/cwd/gate/time/effect/output/completion fields, tool requirements, return contract, and `generated_at`. `schema_refs` and `profile_dependency_refs` participate when present.

The accepted work-graph reference is the authority-bearing source for WorkUnit selection. The compiler SHALL locate exactly one node matching `work_unit_id`, verify that the request's command, ownership, dependency, and return projections are a lossless deterministic projection of that node and its referenced accepted artifacts, and reject zero, duplicate, or contradictory matches. It SHALL NOT fill semantic omissions from conventions.

Every `bbk.governing-reference.v1` supplies object path and SHA-256, schema ID, subject identity/revision, expected-current identity, reference kind, selector anchor and owner, selector operation identity, and independent selector evidence. References discovered through governed objects' `governing_refs` are part of the bounded recursive closure. Maximum depth is 64 and maximum verified objects is 1,024.

Dependency inventory has two typed streams: `declared` (graph/profile/tool requirements and exact identities) and `observed` (physical executable/script path, SHA-256, byte count, and any admitted dependency-inspection command evidence). Absence or disagreement is data, never silently repaired. Breaker input is an immutable ordered array of prior breaker events bound to candidate identity, semantic gate ID, boundary anchor, fingerprint, and process-invocation count.

## Outputs, schemas, identity, and finalization

`compile` emits `bbk.execution-admission-compilation.v1` referencing a finalized `bbk.execution-admission.v1`. The admission contains the verified governing and lineage-only references, selector evidence, `bbk.repository-inventory.v1`, repository guard, `bbk.worker-contract.v2`, tool/dependency inventory, sorted invalidation keys, timestamp, and explicit claims not established.

Canonical JSON is UTF-8/LF with sorted keys. `atomic_finalizer.finalize_json` validates against the checked-in schema closure and publishes `<output>` with `<output>.identity.json` as a recoverable pair. The receipt binds byte count, SHA-256, subject kind `EXECUTION_ADMISSION`, references, finalizer version, and canonicalization profile. Default behavior is create-once; replacement requires an explicit successor operation, never `--force` on this surface.

`run` creates a unique evidence root containing raw `stdout.bin`, raw `stderr.bin`, finalized `command-evidence.json`, and its identity sidecar. Evidence binds admission identity, exact argv/cwd, closed-environment name/value digests, timestamps, exit/timeout/cleanup, complete stream digests, normalized digests, reconciliation, creditability, fingerprint, and breaker projection. Raw streams are never merged or truncated.

## Functional requirements

1. Validate every input and recursive schema reference from the checked-in `spec/schemas` closure; reject remote or unknown `$ref` values without network access.
2. Verify every object byte hash, declared schema, subject identity/revision, expected-current identity, selector anchor hash/owner, selector operation identity, and independent PASS evidence.
3. Reject self-anchored selectors, cycles, conflicting current candidates, stale identities, and any known successor omitted from the submitted closure.
4. Project exactly one selected accepted WorkUnit into `bbk.worker-contract.v2`; do not create authority, commands, scopes, completion checks, or return semantics absent from accepted inputs.
5. Inventory Git HEAD/tree/index/status/untracked/ignored/preimages/submodules/control inputs and the physical tree using configuration-independent Git invocation.
6. Require the requested root to equal Git top level; reject submodules, special files, escaping symlinks/reparse points, case collisions, overlapping/broad owned roots, and command cwd outside the repository.
7. Require exact equality between observed dirty paths and declared dirty entries; verify optional preimage hashes/Git states and exactly one owner for write-capable dirt.
8. Route `TEMP`, `TMP`, `TMPDIR`, Python cache, and synthetic home beneath the attempt root; construct a closed allowlisted environment and reject ambient secrets, proxies, loader injection, Python overrides, cloud/CI tokens, and command-declared secrets without a separate authority contract.
9. Require each executable to be an exact physical regular file and bind its SHA-256/size; inventory an absolute script operand when present.
10. Compare R0 and R1 whole-repository inventories before publication and R2 against the admitted scope guard immediately before launch.
11. Preserve declared and observed dependency inventories as separate ordered streams and report missing, extra, or drifted dependencies with stable codes.
12. Execute only an admitted command ID, once, with `shell=False`, no stdin, no detached descendants by contract, bounded timeout, separate concurrent stream drains, and no automatic replay.
13. Reconcile R2/R3/R4 effects against owned roots and allowed effect class; evidence-control self-publication is excluded from product-effect credit.
14. Compute a fingerprint from normalizer version, admission invalidation digest, gate/command IDs, tool digest, termination class, and normalized stdout/stderr digests.
15. Record both physical invocation count and consecutive identical-fingerprint count; a changed candidate, gate, boundary, admission invalidation digest, tool, or normalized failure resets the latter rather than erasing history.
16. Refuse process creation when the existing `verification_economy.classify_composite_breaker` projection says execution is unauthorized or its state begins `TRIPPED`, `TERMINAL`, or `DIAGNOSIS`.
17. Return stable diagnostics with `claims_not_established`; never translate mechanical PASS into semantic admission, gate PASS, acceptance, or release.
18. Provide `verify` and `inspect` as read-only operations; verification SHALL recheck identity, repository root, guard/currentness, tools, and invalidation keys by default.

## State and ordering model

`REQUESTED -> VALIDATING -> INVENTORIED_R0 -> REFERENCES_VERIFIED -> CONTRACT_COMPILED -> INVENTORIED_R1 -> FINALIZED` is the only successful compile order. Any error transitions to `REJECTED` and publishes no new pair. A finalized admission is immutable; changed invalidation input requires a new `admission_id`/attempt and successor lineage.

Command order is `VERIFY_FINALIZED -> BREAKER_CHECK -> R2_GUARD -> TOOL_RECHECK -> PROCESS_CREATED_ONCE -> STREAMS_CLOSED -> R3_RECONCILED -> R4_CAPTURED -> EVIDENCE_FINALIZED`. Process creation is forbidden before all preceding checks pass. Evidence finalization failure does not justify replay because the process may already have effected state.

## Failure semantics and circuit breaker

All expected failures use stable `ADMISSION_*` codes and fail closed. Pre-process failures have `process_invocations: 0`; post-process failures preserve the attempt directory, streams, observed effects, cleanup state, and `process_invocations: 1`. Capture uncertainty is non-creditable and never treated as no effect. Timeouts attempt bounded group/session termination, report `cleanup: UNKNOWN` if not proven, and block reuse.

Breaker counters are derived from immutable events, not mutable hidden state. Identical normalized failure fingerprints increment a consecutive counter. Different non-creditable failures increment total failure count but do not masquerade as progress. The classifier remains the sole checked-in breaker decision implementation; this compiler only enforces its `execution_authorized` result and preserves the projection.

## Security, authority, path, and network rules

- The tool proves contract consistency, not authority legitimacy; authority comes only from the verified accepted references.
- Repository-relative paths use canonical POSIX form with no absolute path, drive prefix, `.` or `..`; explicit operation roots/executables may be absolute and are resolved physically.
- Output/evidence must be beneath one declared `EXPECTED_OUTPUT` or `EVIDENCE_CONTROL` owned root; product mutation is limited to the corresponding owned root/effect class.
- Schemas and references must be regular files beneath the repository/package root and must not traverse symlinks.
- The compiler and verifier perform no remote fetch. Admitted commands default to no network authority; because the current runtime is not an OS network sandbox, any network-capable command requires an explicit separately enforced capability or is rejected.
- Diagnostics must not echo environment values or raw streams; persisted command evidence stores value digests and classifies raw streams `UNCLASSIFIED` until a later authorized classifier acts.

## Compatibility and migration

The first CLI wraps existing functions and v1/v2 schemas without changing their meaning. Existing finalized admissions remain verify/inspect compatible. New graph-projection and dependency/counter fields require additive schema revisions if they cannot fit existing open object fields; do not silently add properties to schemas with `additionalProperties: false`. Migrate by dual-reading old/new admissions, writing only the newest schema, and retaining old identity sidecars. Agents that previously consumed hand-built Worker contracts switch to the embedded contract bytes from the admission; no automatic content rewrite is allowed.

## Observability and evidence

Emit one canonical JSON result/diagnostic per operation with operation ID, admission/work-unit/attempt identity, phase, duration, R0/R1/R2/R3/R4 digests as applicable, reference and dependency counts, dirty counts by classification, tool digests, process-invocation count, fingerprint/counters, breaker state, effect reconciliation, and explicit claims not established. Do not persist raw prompts, credentials, ambient environment values, or combined stream previews.

## Test strategy

- **Positive:** canonical accepted graph to Worker contract; recursive references; clean and declared-dirty repositories; deterministic repeated compile in frozen fixtures; Windows/POSIX paths; complete binary stdout/stderr; verify/inspect round trip.
- **Negative:** stale predecessor, omitted successor, bad hash/schema/subject, self-anchor/cycle, ambiguous currentness, dirty mismatch/owner overlap, escaping path/symlink, submodule/special file/case collision, relative executable, forbidden environment, tool or endpoint drift, output outside ownership, unknown command.
- **Fault injection:** repository changes between R0/R1 or before R2, stream-drain error, timeout/failed termination, output or identity-sidecar replace failure, schema validator unavailable, process creation failure, evidence finalization failure.
- **Known-bad controls:** a fixture whose selector falsely names its own object, a fixture with an undeclared ignored file in an owned root, a command emitting identical failures until the breaker opens, and a command that mutates outside its owned root must all be rejected/non-creditable. Tests must demonstrate controls actually fail before trusting positive results.

## Acceptance criteria

1. All four exact CLI examples parse and return schema-valid JSON with documented exit codes.
2. Given frozen accepted inputs, two independent compiles produce byte-identical admission content when `generated_at` is fixed and valid detached identities.
3. Any recursive hash/currentness/successor defect, repository endpoint drift, or dirty ownership mismatch prevents publication and process creation.
4. The emitted Worker contract is demonstrably a lossless projection of exactly one accepted WorkUnit and is consumed unchanged by a dispatch fixture.
5. Temp/cache/home paths are workspace-local and schema validation succeeds with networking disabled and no remote resolution hook.
6. Raw stdout and stderr remain complete separate byte streams; one execution yields exactly one invocation count even when capture/finalization fails.
7. Fingerprints and consecutive counters are stable, and the known-bad repeated-failure control opens the existing breaker before another process is created.
8. Atomic publication fault tests expose either the prior complete pair or the new complete pair, never a mixed/unpaired admission.
9. Output claims expressly exclude semantic acceptance, OS containment, network prevention, gate PASS, and release readiness.

## Dependencies and consumers

Dependencies: `tools/execution_admission.py`, `tools/atomic_finalizer.py`, `tools/artifact_packages.py`, `tools/strict_json.py`, `tools/verification_economy.py`, checked-in schemas, exact Git, and an offline `jsonschema`/`referencing` runtime. Inputs may be generated by `tools/bbk.py worker-contract generate`, but the admission compiler, not that generator, owns final mechanical admission.

Consumers: Worker dispatch adapters, [worker result assembly](B-worker-result-assembler.md), command-evidence replay, worker-quality gate tooling, recovery, and orchestrator evidence reports.

## Rollout

1. Add CLI/parser and golden diagnostics without changing Python APIs.
2. Add accepted-graph projection and typed dependency/counter schema revisions behind an explicit format version.
3. Run dual verification against current admission fixtures; publish new format only after parity.
4. Switch one Worker cohort to receipt-only dispatch, then all cohorts; retain read-only verification for legacy admissions through the compatibility window.

## Risks and open questions

- OS-level network/process containment remains outside this Python tool; determine the qualified host adapter required for commands needing those guarantees.
- Work-graph schemas may vary; the exact accepted node/edge projection schema must be named before implementation rather than inferred heuristically.
- Decide the versioned schema homes for dependency streams and breaker counters; both require closed schemas and immutable event lineage.
- Whole physical-tree inventories can be expensive; any optimization must preserve equivalent dirty/escape detection and be proven by differential tests.

## Effort estimate

Large: 8–12 engineering days plus 3–5 days for cross-platform/fault-injection qualification; lower (3–5 days) if limited to the thin CLI over current schemas and deferred graph/dependency schema revisions.
