# PRD C — Gate Receipt Normalization, Recording, and Aggregation

| Field | Value |
|---|---|
| Status | Proposed |
| Owner kind | Assurance/evidence tooling maintainer |
| Priority | P0 / completion-truth blocker |

## Problem and evidence

BBK currently has two distinct gate families. Policy gates are deterministic authority/effect decisions: `tools/gate_kernel.py` evaluates `bbk.gate-evaluation-request.v1` against governed policy and returns `bbk.gate-decision.v1` (`ALLOW`, `BLOCK`, or `REQUIRE_OVERRIDE`), while `bbk.gate-receipt.v1` records that decision. Operational/assurance gates report execution or assertion status such as `PASS`, `FAIL`, `BLOCKED`, `INCONCLUSIVE`, `ERROR`, `NOT_RUN`, or `NOT_APPLICABLE`; `bbk.review-attempt.v1` and `bbk.review-aggregate.v1` already encode non-averaging assurance semantics. Treating these shapes as interchangeable can turn `ALLOW` into evidence of correctness or average an unrun required gate into PASS.

The needed tool is an authority-neutral normalizer and recorder. It binds receipts to exact candidate, method, environment, tool, config, and source identities; verifies them; and calculates a deterministic non-averaging aggregate. It does not evaluate policy predicates or operational assertions itself.

## Goals

- Preserve the semantic distinction between policy decisions and operational/assertion results while exposing one typed receipt envelope.
- Record create-once receipts with exact candidate/method/environment/tool/config bindings and detached identity.
- Verify receipt bodies, referenced evidence, lineage, and currentness without executing gates.
- Aggregate required gates non-averaging: any required `INCONCLUSIVE` or `NOT_RUN` is nonpass.

## Non-goals

- Running commands, evaluating assertions, interpreting test output, choosing required gates, granting overrides, accepting risk, accepting candidates, or releasing.
- Translating `ALLOW` to `PASS`, `BLOCK` to `FAIL`, or infrastructure failure to product failure.
- Majority voting, scores, weighted averages, retry policy, finding disposition, or evidence repair.
- Replacing [execution admission](A-execution-admission-compiler.md) or [Worker result assembly](B-worker-result-assembler.md).

## Users and callers

Policy adapters call `record` after `gate_kernel.evaluate`. Operational gate runners and validator/reviewer orchestration call `record` after producing their own typed evaluation. Worker orchestrators, validator orchestrators, candidate gates, recovery, release tooling, and Worker result assembly call `verify`/`aggregate`.

## Command surface

```text
python tools/gate_receipts.py record --root D:\repo --request D:\repo\.bbk\gates\unit.record-request.json --output D:\repo\.bbk\gates\unit.receipt.json
python tools/gate_receipts.py verify --root D:\repo --receipt D:\repo\.bbk\gates\unit.receipt.json
python tools/gate_receipts.py aggregate --root D:\repo --manifest D:\repo\.bbk\gates\candidate-17.manifest.json --receipt D:\repo\.bbk\gates\policy.receipt.json --receipt D:\repo\.bbk\gates\unit.receipt.json --output D:\repo\.bbk\gates\candidate-17.aggregate.json
```

All commands emit one JSON result, are non-interactive and offline, and use exit `0` for valid record/verification or aggregate PASS, `1` for valid nonpass aggregate, `2` for malformed/stale/mismatched input, and `3` for internal/finalization failure. `verify` is read-only. `record` and `aggregate` are create-once; no force overwrite.

## Required inputs and schemas

Add closed schemas for:

1. `bbk.gate-record-request.v1`: `gate_kind` (`POLICY` or `OPERATIONAL`), producer/evaluation reference, subject binding, dependency bindings, evidence refs, predecessor receipt ref if any, and `recorded_at`.
2. `bbk.operational-gate-evaluation.v1`: `gate_id`, assertion/check reference, status (`PASS`, `FAIL`, `BLOCKED`, `INCONCLUSIVE`, `ERROR`, `NOT_RUN`, `NOT_APPLICABLE`), rationale, evidence refs, execution/cleanup state, and claims not established.
3. `bbk.normalized-gate-receipt.v1`: common envelope plus a discriminated policy or operational payload.
4. `bbk.gate-aggregate-manifest.v1`: aggregate/candidate identity, ordered gate requirements, `required` boolean, applicable condition already resolved by an authority-bearing manifest producer, expected kind/method/environment/tool/config bindings, and permitted receipt IDs.
5. `bbk.gate-aggregate.v1`: per-gate normalized results, missing/stale/duplicate lists, overall result, non-averaging marker, calculation digest, authority disclaimer, and identity receipt reference.

The common `subject` binds candidate kind/ID/revision/SHA-256, WorkUnit/boundary, invocation/attempt where applicable, and governing baseline/manifest digests. `method` binds method ID/version/content digest and assertion/check ref. `environment` binds profile/environment receipt and digest. `tool` binds physical executable/package identity and version/digest. `config` binds all behavior-affecting configuration/corpus/seed/flags by canonical digest. Evidence refs bind path/URI, byte count, SHA-256, schema, producer attempt, and capture completeness.

Policy input must be an exact `bbk.gate-evaluation-request.v1` plus `bbk.gate-decision.v1` pair consistent with `gate_kernel`'s request digest and receipt ref. The existing `bbk.gate-receipt.v1` remains a supported policy source format. Operational input must not contain policy outcomes.

## Outputs, schemas, identity, and finalization

`record` produces `bbk.normalized-gate-receipt.v1`:

- Common envelope: schema/version, immutable receipt ID, kind, recorded time, subject and dependency bindings, producer/evaluation identity, evidence refs, predecessor, invalidation keys, and authority disclaimer.
- `POLICY` payload: original request and decision, preserving `ALLOW|BLOCK|REQUIRE_OVERRIDE`, reason codes, observations, override eligibility/evidence, policy and implementation versions, request digest, and original receipt ref.
- `OPERATIONAL` payload: original evaluation status and rationale, execution/cleanup facts, evidence completeness, and bounded claims.

The receipt ID is `sha256:` plus the canonical digest of the content-defined envelope excluding `recorded_at`, storage path, and receipt ID itself; timestamps therefore do not create a different semantic receipt. Storage bytes and detached identity still include `recorded_at`. `atomic_finalizer` validates and atomically publishes body plus `.identity.json` with all source/evidence references.

`aggregate` emits finalized `bbk.gate-aggregate.v1`. `calculation_digest` covers the manifest identity, ordered normalized receipt semantic IDs, per-gate classifications, missing/stale/duplicate facts, and algorithm version. It does not imply acceptance authority.

## Functional requirements

1. Validate all inputs with the local Draft 2020-12 schema registry and reject remote/unknown schema references.
2. Discriminate gate kinds structurally; reject payloads mixing policy decisions and operational statuses.
3. For policy receipts, recompute canonical request digest and `gate_kernel` receipt reference; verify policy ID/version, implementation version, actor/authority/candidate/work-unit/invocation subject, predecessor chain, and exact decision bytes.
4. Preserve `ALLOW`, `BLOCK`, and `REQUIRE_OVERRIDE` without mapping them to operational correctness. A policy gate satisfies a manifest requirement only according to the manifest's explicit required policy outcome, normally `ALLOW`.
5. For operational receipts, require one allowed status, rationale, method binding, complete subject/dependency binding, and evidence/claims appropriate to that status.
6. Bind every receipt to exact candidate SHA-256/revision, method digest, environment/profile digest, tool digest, and configuration digest. Missing required binding is `INCONCLUSIVE`/invalid, never reusable PASS.
7. Verify referenced evidence existence, byte count, SHA-256, schema, capture completeness, producer attempt, and candidate binding. Transport integrity alone does not establish gate correctness.
8. Reject duplicate receipt IDs with conflicting bytes, multiple current receipts for one required gate unless the manifest names a deterministic successor, broken predecessor chains, cycles, and stale candidate/dependency bindings.
9. Normalize infrastructure states separately from assertion result; tool crash/missing environment is `ERROR`, `BLOCKED`, `INCONCLUSIVE`, or `NOT_RUN`, not `FAIL` unless the gate's own qualified method establishes product failure.
10. Treat `NOT_APPLICABLE` as satisfying only when the manifest marks the gate optional or carries an exact authority-bearing applicability disposition; the aggregator cannot invent non-applicability.
11. Aggregate required policy gates as pass only when their exact required policy outcome is present/current; `BLOCK` and `REQUIRE_OVERRIDE` are nonpass.
12. Aggregate required operational gates as pass only on current `PASS`; required `FAIL`, `BLOCKED`, `INCONCLUSIVE`, `ERROR`, and `NOT_RUN` are all nonpass.
13. Use non-averaging precedence for the overall result: malformed/conflicting input `ERROR`; stale required input `STALE`; required operational `FAIL` or policy `BLOCK` `FAIL`; required policy `REQUIRE_OVERRIDE` or operational `BLOCKED` `BLOCKED`; required `ERROR` `ERROR`; required `INCONCLUSIVE`/`NOT_RUN`/unjustified `NOT_APPLICABLE`/missing receipt `INCONCLUSIVE`; otherwise `PASS` (with optional advisories represented separately).
14. Preserve every per-gate outcome and blocker; never allow optional PASS receipts or receipt count to offset one required nonpass.
15. Make verification deterministic and read-only. Re-recording semantically identical content yields the same semantic receipt ID; different candidate/method/environment/tool/config produces a different ID.
16. Publish receipts and aggregates create-once via `atomic_finalizer`; corrections create successors with predecessor refs and preserve old bytes.
17. Emit explicit authority disclaimers: aggregation establishes configured receipt-set calculation only, not assertion quality, candidate acceptance, risk acceptance, outcome achievement, or release.

## State and ordering model

Receipt recording: `OBSERVED -> SOURCE_VERIFIED -> NORMALIZED -> FINALIZED`; failures end `REJECTED` with no new pair. Receipt lineage is append-only: `CURRENT -> SUPERSEDED` is represented by a new receipt/selector record, never mutation.

Aggregation: `MANIFEST_VERIFIED -> RECEIPTS_VERIFIED -> BINDINGS_MATCHED -> PER_GATE_CLASSIFIED -> NON_AVERAGING_CALCULATED -> FINALIZED`. Any input change invalidates the calculation digest. Aggregate finalization occurs only after all per-gate states, including missing and not-run entries, are explicit.

## Failure semantics and circuit-breaker behavior

Malformed or mismatched receipts are invalid inputs, not gate FAIL. Required missing/stale/inconclusive/not-run receipts yield a valid nonpass aggregate and a smallest next action. Publication failure leaves either the prior complete pair or no new pair. No evaluator or command is automatically rerun.

The tool does not own execution breakers. It records breaker state/fingerprint/counters from operational evidence and classifies a breaker-prevented required gate as `NOT_RUN` or `BLOCKED` according to the producer's typed evaluation; both are nonpass. It must never reset counters or bypass an open breaker to seek a PASS.

## Security, authority, path, and network rules

- Operate only on explicit regular-file inputs beneath the governed root; reject traversal, symlink/reparse escape, case aliases, and output outside a declared evidence root.
- No shell/process execution, remote fetch, package install, environment discovery, credentials, network, publication, deployment, or mutation beyond local receipt/aggregate finalization.
- Never infer authority from actor kind, successful execution, policy `ALLOW`, or a receipt producer. Override applicability remains governed by the original policy decision and exact-scope authority evidence.
- Evidence previews must be bounded and classified; digests and references are preferred. Do not copy secrets or raw untrusted streams into normalized receipts.

## Compatibility and migration

Support existing `bbk.gate-receipt.v1` as a policy-source adapter without changing its meaning or bytes. Support `bbk.review-attempt.v1` assertion evaluations as operational sources when all new binding requirements can be proven; otherwise normalize as `INCONCLUSIVE` with missing bindings, never retrofit PASS. Keep `bbk.review-aggregate.v1` as a consumer-facing assurance aggregate; this gate aggregate may be referenced by it but does not replace reviewer/validator authority. Dual-read legacy and normalized receipts during migration, write only the normalized format, and compare decisions in shadow mode.

## Observability and evidence

Emit counts by kind/status, missing/stale/duplicate/conflict counts, candidate/method/environment/tool/config digest match flags, evidence completeness, lineage depth, algorithm version, calculation digest, finalization identity, duration, and authority disclaimer. Metrics must preserve policy and operational namespaces and must not collapse them into a single generic success counter.

## Test strategy

- **Positive:** policy ALLOW/BLOCK/REQUIRE_OVERRIDE normalization; operational PASS/FAIL/BLOCKED/INCONCLUSIVE/ERROR/NOT_RUN/NOT_APPLICABLE; mixed manifest; deterministic receipt IDs; predecessor successor; legacy policy/review adapters; atomic finalize/verify round trips.
- **Negative:** candidate/method/env/tool/config mismatch; altered evidence; incomplete streams; mixed namespaces; forged request digest/receipt ref; duplicate conflicting ID; stale predecessor; cycle; missing required receipt; unjustified NOT_APPLICABLE; optional receipt attempting to offset required failure.
- **Fault injection:** source changes during verification, schema registry unavailable, identity-sidecar mismatch, output/sidecar replace failures, interrupted aggregate publication, truncated evidence, timestamp variation.
- **Known-bad controls:** `ALLOW` presented as test PASS, required `INCONCLUSIVE` plus many optional PASS receipts, required `NOT_RUN` omitted from output, and tool/environment drift under a reused PASS receipt must all remain nonpass or invalid. The suite must prove these controls fail before crediting aggregate tests.

## Acceptance criteria

1. All exact example argv operate offline and emit schema-valid JSON with documented exit behavior.
2. Policy and operational payloads remain distinguishable end to end; no code path maps `ALLOW` to operational `PASS`.
3. Every reusable receipt binds exact candidate, method, environment, tool, config, evidence, and producer identities and invalidates on any bound digest change.
4. Required `INCONCLUSIVE`, `NOT_RUN`, missing, stale, unjustified `NOT_APPLICABLE`, `REQUIRE_OVERRIDE`, or `BLOCKED` always produces a nonpass aggregate regardless of other PASS receipts.
5. One required FAIL/BLOCK cannot be averaged away; per-gate facts and precedence are visible in the aggregate.
6. Legacy `bbk.gate-receipt.v1` decisions verify against recomputed `gate_kernel` digests and normalize without semantic change.
7. Atomic fault tests never expose a new receipt/aggregate without its matching identity sidecar and never overwrite prior immutable records.
8. Known-bad namespace, averaging, omission, and drift controls are rejected/nonpass with stable diagnostics and explicit smallest next actions.
9. Aggregate output states that it does not establish assertion quality, acceptance, risk disposition, outcome achievement, or release.

## Dependencies and consumers

Dependencies: `tools/gate_kernel.py`, `tools/atomic_finalizer.py`, strict JSON/local schema registry, existing gate/review schemas, command evidence from [PRD A](A-execution-admission-compiler.md), and optionally assembled Worker evidence from [PRD B](B-worker-result-assembler.md).

Consumers: Worker and validator orchestrators, `bbk.review-aggregate.v1` compilation, candidate/worker-quality gates, release qualification, recovery, evidence replay, and completion-truth reporting.

## Rollout

1. Add closed schemas and read-only normalization/verification for existing policy and review fixtures.
2. Shadow-record normalized receipts alongside legacy receipts and compare semantic decisions/digests.
3. Enable create-once aggregate generation for one candidate gate manifest; retain existing aggregation as the release authority.
4. After parity and known-bad controls pass, make normalized receipts required for new gate runs; retain legacy readers for the declared compatibility window.

## Risks and open questions

- The exact aggregate result vocabulary (`FAIL` versus `NEEDS_REVISION`, `BLOCKED` variants) must align with the consuming schema; precedence semantics are fixed even if labels are mapped.
- Applicability authority must live in the gate manifest or AssuranceContract, not this tool; name the exact schema/ref before implementation.
- Semantic receipt ID excludes timestamp but storage identity includes it; document collision handling for identical semantic receipts recorded at different times.
- Operational producers vary in evidence richness. Missing bindings must remain visible nonpass during migration, which may expose previously hidden coverage gaps.

## Effort estimate

Medium-large: 8–11 engineering days plus 3–5 days for legacy adapters, non-averaging controls, and atomic/fault-injection qualification.
