# PRD B — Typed Worker Result Assembler

| Field | Value |
|---|---|
| Status | Proposed |
| Owner kind | Role-return/runtime tooling maintainer |
| Priority | P0 / return-integrity blocker |

## Problem and evidence

Workers produce several independently useful facts—an [execution admission](A-execution-admission-compiler.md), command receipts, changed-path/diff evidence, cleanup state, and a durable handoff—but manually composing them into `bbk.role-return.v2` permits omissions, mismatched identity, invented executor facts, and non-atomic publication. The checked-in `tools/role_return_runtime.py` already owns bound template/prepare/validate/resolve behavior and durable admission receipts. `tools/atomic_finalizer.py` owns canonical validation and pair publication. Worker result schemas already distinguish the full `bbk-worker-result-v1` payload from compact `bbk-worker-compact-result-v2`. The assembler must compose these sources; it must not become a new authority or fabricate its own identity.

## Goals

- Deterministically assemble a typed Worker return from verified admission and evidence inputs.
- Bind all result facts to the active invocation, subject, attempt, authority/effect fence, candidate, and return contract.
- Use `role_return_runtime` for bound return preparation/admission and `atomic_finalizer` for durable JSON identity/finalization.
- Make omissions, contradictions, residual effects, and claims not established explicit.

## Non-goals

- Executing Worker commands, interpreting whether code is correct, evaluating independent assertions, accepting a candidate, closing findings, or releasing.
- Generating executor/session/invocation/candidate identity from output paths, host state, timestamps, or assembler identity.
- Creating a handoff when none was produced, repairing cleanup, rewriting diffs, or summarizing away raw receipts.
- Replacing gate normalization/aggregation in [PRD C](C-gate-receipt-aggregation.md).

## Users and callers

Primary caller: `bbk_worker` at return time. Mechanical callers may include Worker harness adapters and `bbk_worker_orchestrator`. Consumers are `role_return_runtime`, the semantic parent, Worker orchestrator, recovery tooling, candidate assembly, and assurance planners.

## Command surface

```text
python tools/worker_result_assembler.py assemble --root D:\repo --request D:\repo\.bbk\attempts\WU-17\worker-result-assembly.request.json --output D:\repo\.bbk\attempts\WU-17\worker-result.json
python tools/worker_result_assembler.py verify --root D:\repo --result D:\repo\.bbk\attempts\WU-17\worker-result.json --admission D:\repo\.bbk\attempts\WU-17\admission.json
```

`assemble` emits canonical JSON to stdout, writes only the requested result/identity pair and the records explicitly created by `role_return_runtime`, and exits `0` on PASS, `2` on typed input/binding rejection, `3` on internal/finalization failure. `verify` is read-only. No `--force`, identity overrides, free-form executor flags, or network flags are permitted.

## Required inputs and schemas

Introduce a closed `bbk.worker-result-assembly-request.v1` with:

- `schema`, `generated_at`, `detail_level` (`COMPACT` or `FULL`), and `summary`.
- `admission`: path, byte count, SHA-256, identity-receipt path, and admission ID; the body must be finalized `bbk.execution-admission.v1`.
- `binding`: exact `session_id`, `binding_ref`, `invocation_id`, and prepared return-contract reference accepted by `role_return_runtime`; values are references to existing binding facts, never authored by the assembler.
- `command_evidence_refs`: ordered path/bytes/SHA-256 references to finalized `bbk.command-evidence.v1` records; admitted completion-check coverage is explicit.
- `diff_inventory_ref`: finalized typed changed-artifact inventory binding before/after identities, path operations, byte counts/SHA-256, and owning WorkUnit.
- `cleanup_ref`: finalized typed cleanup/effect inventory with processes, temp/cache, credentials/services/ports/network/remote effects, residuals, and owner.
- optional `handoff_ref`: finalized `bbk.handoff.v2` identity, subject, producer attempt, and verification state.
- explicit `discoveries`, `blockers`, `continuation`, `claims_established`, `claims_not_established`, and `smallest_valid_next_action`; each claim cites evidence refs.

All referenced files are strict JSON regular files below admitted read/evidence roots and have verified detached identities where their schema requires one. Raw diff/stream files may be non-JSON but must be referenced by byte count and SHA-256. The return contract is taken from `admission.worker_contract.return_contract` and active binding; disagreement is fatal.

## Outputs, schemas, identity, and finalization

The durable output is a complete `bbk.role-return.v2` with `contract: bbk.worker-return.v2`, `role: bbk_worker`, bound executor/subject/parent/attempt, operational disposition, semantic state, authority/effects used, role-specific result, smallest next action, and optional outputs/evidence/cleanup/blockers/prohibited claims.

For `COMPACT`, `result` validates against `spec/schemas/role-results/bbk-worker-compact-result-v2.schema.json`. For `FULL`, it uses the current full Worker result contract selected by the role-return registry; until a v2 full payload exists, the tool SHALL use the registry's declared compatible full schema and must not label a v1 payload as v2 without that registry mapping.

Assembly order is: verify sources; derive content; call `role_return_runtime prepare`; resolve/admit the exact prepared record; write a draft containing that exact accepted role return; call `atomic_finalizer.finalize_json` with all source identities as references. Output and `<output>.identity.json` are a recoverable pair. The assembler's process, hostname, user, model, or timestamp never becomes executor identity.

## Functional requirements

1. Verify admission body/sidecar, `state: FINALIZED`, currentness/guard, selected WorkUnit, subject, and embedded return contract before assembly.
2. Verify every receipt/diff/cleanup/handoff byte count, SHA-256, schema, subject/candidate, work-unit, attempt, producer, and currentness required by its contract.
3. Require every command-evidence item to name an admitted command ID with exact argv/cwd/admission digest; reject duplicates and foreign or missing required completion checks.
4. Preserve command chronology, return code, timeout, cleanup, stream references, tool/environment digests, fingerprint, creditability, reconciliation, and claim limits without recalculation that changes meaning.
5. Derive `changed_artifacts` solely from the typed diff inventory and reconcile all changed paths with admission-owned roots; undeclared or outside-scope changes force a blocked/inconclusive disposition.
6. Derive `authority_and_effects_used` from verified admission authority/effect fence plus observed receipts; never infer authority from observed success.
7. Require cleanup state for every admitted temporary/cache root and every observed external effect. Unknown or incomplete cleanup remains a blocker/residual and cannot yield `COMPLETE`.
8. Preserve a verified handoff reference exactly when supplied; absence is valid only when no separate durable handoff is required by the return contract.
9. Map source facts into every required compact/full field; empty required sections use typed empty values plus rationale, not omission or prose placeholders.
10. Require each positive claim to cite current evidence. Automatically include the Worker prohibitions: no independent validation, candidate acceptance, finding closure, outcome achievement, or release.
11. Derive operational disposition and semantic state by deterministic rules: any authority/scope violation blocks; unknown residual effects are inconclusive/blocked; incomplete required checks are partial/inconclusive; only complete covered work with complete cleanup may be `COMPLETE`.
12. Take executor, invocation, subject, parent, attempt, authority, and effect identities only from the immutable active binding and admission; the request may reference but not override them.
13. Use `role_return_runtime` to prepare and resolve the exact full document so the yielded value matches the binding-owned immutable prepared record.
14. Use `atomic_finalizer` for schema validation, canonical UTF-8/LF bytes, atomic result/identity publication, and reference identity capture.
15. Reject existing output rather than replace it; corrected assembly creates a successor result and preserves the failed/prior attempt.
16. Emit stable JSON-pointer diagnostics and the smallest safe repair action; publish no partial result on pre-finalization failure.

## State and ordering model

`REQUESTED -> SOURCES_VERIFIED -> COVERAGE_RECONCILED -> RESULT_DERIVED -> RETURN_PREPARED -> RETURN_ADMITTED -> FINALIZED`. A failure before finalization produces no result pair. A prepared/admitted role-return record is immutable and may be finalized exactly once. A changed source digest, binding, candidate, or admission creates a new assembly attempt rather than editing history.

The assembled return is subordinate to its sources: evidence records remain canonical; the result is an indexed projection. Later invalidation marks the result stale and points to a successor but does not mutate old bytes.

## Failure semantics and circuit breaker behavior

Typed failures use `WORKER_RESULT_*` codes and separate invalid input, binding mismatch, missing evidence, contradiction, incomplete cleanup, and publication failure. No source mutation or command replay occurs. A failure before any publication is safely retryable after source repair; uncertainty after role-return admission or pair-publication failure requires inspection of runtime receipts and atomic-finalizer recovery state before retry.

The assembler does not own a retry breaker. It SHALL propagate admission command fingerprints/counters and any open breaker as blockers, and SHALL refuse `COMPLETE` when a required gate is breaker-blocked, `INCONCLUSIVE`, or not run.

## Security, authority, path, and network rules

- Read only admitted regular files; reject symlinks/reparse escapes, `..`, alternate-drive escape, case aliases, and output outside an admitted `EXPECTED_OUTPUT`/`EVIDENCE_CONTROL` root.
- Perform no subprocess, package, VCS, credential, service, network, publication, deployment, or remote-system effect other than local governed record publication.
- Never read ambient identity or credentials. Redact neither by silently dropping data nor by copying secrets; reject source fields that violate the destination classification contract.
- Authority is copied as verified reference identity and observed use. The assembler cannot grant, waive, extend, or interpret authority.

## Compatibility and migration

Use `spec/contracts/role-return-registry-v2.json` as the contract/schema selector and `role_return_runtime` as the compatibility boundary. Existing valid `bbk.role-return.v2` documents remain consumable. Initial rollout may compare assembler output with current hand-authored fixtures without requiring replacement. Closed new request/diff/cleanup schemas must be versioned. If FULL v2 lacks a dedicated payload schema, either add one through the registry or explicitly retain the registry's current mapping; do not fork undocumented shapes.

## Observability and evidence

Emit source count/digests, admitted/covered/missing command IDs, changed-path counts, cleanup status, handoff presence, detail level, derived disposition/state, binding/admission/result identities, finalizer receipt, diagnostics, and explicit claims not established. Metrics must not include raw streams, diff content, secrets, model prompts, or fabricated executor labels.

## Test strategy

- **Positive:** compact and full assembly; zero-change Worker; multiple command receipts in declared order; complete cleanup; verified handoff; direct-root and canonical-role parent bindings; validate/resolve round trip.
- **Negative:** wrong subject/session/invocation/attempt/candidate; admission or sidecar drift; foreign/duplicate/missing command; argv/cwd mismatch; diff outside ownership; effect without cleanup; handoff producer mismatch; unsupported detail/schema mapping; positive claim without evidence; attempted identity override.
- **Fault injection:** failure between prepare and resolve, stale active binding, role-return receipt append failure, result replace failure, sidecar replace failure, source file changes between verification and finalization.
- **Known-bad controls:** a schema-valid return for the wrong bound subject, a clean-looking summary backed by a failing receipt, an undeclared changed path, and a self-supplied executor identity must all be rejected. Controls must be asserted to fail before positive fixture conclusions are credited.

## Acceptance criteria

1. Exact example argv works offline and outputs a schema-valid, finalized Worker return plus valid detached identity.
2. Every identity field equals the active binding/admission source and cannot be overridden by request content or assembler runtime identity.
3. Compact and full outputs validate through `role_return_runtime` and the registry-selected role-specific schema.
4. Missing required receipts, non-creditable evidence, outside-scope diffs, or incomplete cleanup cannot produce `COMPLETE`.
5. All source digests and material claim/effect/cleanup limits are traceable from result fields to immutable input records.
6. Prepare/resolve/admission uses the exact document later finalized; mutation between stages is detected.
7. Atomic fault tests never leave a new result without its matching identity receipt and never destroy a prior pair.
8. Known-bad identity, failing-receipt, scope, and self-identity controls are rejected with stable codes and no source mutation.

## Dependencies and consumers

Dependencies: [PRD A](A-execution-admission-compiler.md), `tools/role_return_runtime.py`, `tools/atomic_finalizer.py`, invocation binding/governed-state storage, role-return registries and schemas, `bbk.command-evidence.v1`, diff/cleanup schemas, and optional `bbk.handoff.v2` verification.

Consumers: semantic parent, `bbk_worker_orchestrator`, candidate/recovery tooling, [gate aggregation](C-gate-receipt-aggregation.md), durable handoff tooling, and audit/evidence reports.

## Rollout

1. Add request/diff/cleanup schemas and read-only `verify` against existing Worker fixtures.
2. Add compact assembly and differential comparison with current manual `role_return_runtime prepare` flows.
3. Add FULL registry mapping and fault-injection qualification.
4. Require assembler output for routine Workers, then all governed Workers; retain legacy return consumption during a declared migration window.

## Risks and open questions

- The repository currently has a v2 compact Worker payload and a v1 full payload; the registry owner must settle the full-v2 mapping before implementation.
- A typed changed-artifact and cleanup inventory may already be planned elsewhere; reuse its authority-neutral schema rather than duplicate it.
- Source verification and role-return preparation must share a stable snapshot/lock boundary to avoid time-of-check/time-of-use drift.
- Very large diff/stream artifacts should remain referenced, not embedded; define bounded preview policy without weakening traceability.

## Effort estimate

Medium-large: 7–10 engineering days plus 3–4 days for binding, atomicity, and cross-platform fault-injection tests.
