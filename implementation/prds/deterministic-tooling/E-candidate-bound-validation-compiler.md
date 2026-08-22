# PRD E — Candidate-bound validation compiler

**Status:** Proposed

**Owner kind:** deterministic assurance-tooling maintainer; assertion meaning remains with the AssuranceContract owner
**Priority:** Required

## Problem and repository evidence

`tools/review_assurance.py` already validates `bbk.assurance-contract.v1`, compiles `bbk.review-manifest.v1`, compiles `bbk.review-context-manifest.v1`, and aggregates review runs. `tools/context_packages.py` already builds candidate-bound review packages for Validators. The missing boundary is deterministic admission of the exact frozen candidate and its prerequisite gate aggregate into one non-overlapping validation plan. Creating a new “validation manifest” would duplicate ReviewManifest and create a third assurance format alongside AssuranceContract and ReviewManifest.

This PRD evolves the existing review-plan compiler. It consumes [PRD C](C-gate-receipt-aggregation.md) and the exact [PRD D](D-canonical-candidate-freezer.md) CandidateRef, emits the existing ReviewManifest as the sole assignment plan, and feeds existing context compilation and Validator orchestration. Its result is consumed by [PRD F](F-completion-readiness-compiler.md) and qualified end to end by [PRD G](G-lifecycle-qualification-fixture.md).

## Goals

- Bind validation to one exact, current D CandidateRef and one current C aggregate.
- Compile accepted AssuranceContract assertions into the smallest non-overlapping existing ReviewManifest.
- Make profile, environment, method applicability, evidence, and actual independence requirements explicit and checkable.
- Feed the existing ReviewContextManifest/review-package/Validator flow without a parallel format.

## Non-goals

- Executing validation, interpreting evidence, producing findings, repairing the candidate, or accepting it.
- Inventing assertions, methods, profiles, environments, capabilities, or independence.
- Averaging assertion outcomes or turning infrastructure success into semantic pass.
- Replacing ReviewManifest, ReviewContextManifest, ReviewRun, or ReviewAggregate.

## Callers

- `bbk_validator_orchestrator` preparing one candidate-bound assurance program.
- `bbk_territory_orchestrator` requesting independent-validation admission.
- Qualification fixtures testing plan compilation and candidate binding.

## Command surface and exact examples

```powershell
python tools/bbk.py validation compile --candidate-ref .bbk/candidates/CAND-17-r1/candidate-freeze-receipt.json --gate-aggregate .bbk/gates/aggregate.json --assurance contracts/assurance.json --profile-lock .bbk/profiles/lock.json --environment .bbk/environment/qualified.json --methods .bbk/validation/method-applicability.json --independence .bbk/validation/independence.json --manifest-id RM-CAND-17 --purpose acceptance --output .bbk/validation/review-manifest.json
python tools/bbk.py review context compile --manifest .bbk/validation/review-manifest.json --candidate .bbk/candidates/CAND-17-r1 --output .bbk/validation/context
```

The second command represents the existing context path; implementation may retain its current spelling. The first command’s primary output is schema-valid `bbk.review-manifest.v1`, not `bbk.validation-manifest.*`.

## Inputs and schemas

- Verified D `CandidateRef` and detached freeze receipt; the sealed `bbk.candidate-package.v1` is the exact ReviewManifest subject.
- Verified `bbk.gate-aggregate.v1` from C with current passing prerequisites for that CandidateRef lineage.
- Accepted, non-superseded `bbk.assurance-contract.v1` whose subject, revision, and digest bind the exact candidate or an explicitly declared pre-freeze subject mapping.
- Current profile lock/effective profile receipt and qualified environment observations.
- Method-applicability inventory mapping each declared AssuranceContract method to `APPLICABLE`, `NOT_APPLICABLE_WITH_REASON`, or `UNAVAILABLE`; it includes tool/environment/capability prerequisites and evidence kind.
- Independence facts and requirements, including producer/reviewer/validator identity dimensions and overlap rationale where the accepted contract permits complementary overlap.

No ambient profile, environment, method, or independence fact may be inferred. Remote schema or method references are rejected offline.

## Outputs and finalization

- One atomically finalized `bbk.review-manifest.v1`, using its existing `subject`, `assuranceContract`, `requiredAssertionRefs`, `lensAssignments`, `independenceRequirements`, `contextPolicy`, `requiredDeterministicEvidence`, `aggregationPolicy`, `dependencyClosure`, `provenance`, and `authorityDisclaimer` fields.
- One detached compiler receipt containing manifest digest, exact CandidateRef, C aggregate digest, profile/environment/method/independence input digests, compiler identity, and claims-not-established.

The compiler may add backward-compatible fields only through a versioned ReviewManifest schema revision and readers-first migration. It must not emit a second assignment manifest. Finalization uses the shared atomic finalizer; context packaging remains owned by existing review/context tooling.

## Functional requirements

1. Verify the D receipt and artifact package, reproduce all CandidateRef fields, and reject invalidated or mutated candidates.
2. Verify the C aggregate and require the configured pass state for the exact execution/candidate lineage.
3. Validate the AssuranceContract, require `status: accepted`, and fail on subject mismatch or supersession.
4. Resolve applicable profiles from the supplied current profile lock only; unknown or ambiguous profile requirements block compilation.
5. Resolve each assertion’s declared methods against the explicit applicability inventory and qualified environment.
6. Never substitute an undeclared method. If no declared method is applicable and available, emit a typed blocker and no active manifest.
7. Assign every required assertion exactly once as a primary assertion; reject duplicate, omitted, or conflicting ownership.
8. Permit overlap only for distinct complementary methods when the AssuranceContract’s overlap policy allows it and rationale is explicit; overlapping assignments cannot mask one another.
9. Preserve blocking flags, protected floors, required deterministic evidence, consumer/fault obligations, prior-findings visibility, repair limits, and non-averaging central blocking.
10. Compile the smallest coherent lens assignment set. Lens hints constrain selection but do not authorize deleting an assertion.
11. Evaluate required independence dimensions against supplied facts before dispatch. Unsatisfied required independence blocks; it is not downgraded to advisory.
12. Bind context selectors to the sealed candidate root and required evidence only; any allowed exclusion is explicit and reflected in context completeness.
13. Produce stable ordering and digest for semantically identical normalized inputs.
14. Mark an earlier manifest stale when CandidateRef, C aggregate, AssuranceContract, profile lock, environment, method applicability, or independence facts change.
15. Provide the exact existing manifest to ReviewContext compilation and Validator orchestration without translation to another semantic structure.

## State and ordering

`REQUESTED -> CANDIDATE_VERIFIED -> GATES_VERIFIED -> CONTRACT_VERIFIED -> APPLICABILITY_RESOLVED -> PARTITIONED -> INDEPENDENCE_CHECKED -> FINALIZED -> CONTEXT_ELIGIBLE`.

Any changed dependency after finalization makes the manifest `STALE`; a successor manifest gets a new revision and preserves predecessor lineage. ReviewContext compilation occurs only after finalization. Validator dispatch occurs only after context completeness and candidate identity are independently verified by the existing assurance flow.

## Failure semantics

Wrong candidate, stale gate aggregate, draft/superseded contract, missing assertion, duplicate primary ownership, method unavailability, environment mismatch, profile ambiguity, independence failure, context escape, or finalization collision is a typed non-zero result. The compiler distinguishes candidate defect from infrastructure/environment inability and produces no `active` manifest on blockers. It never converts `INCONCLUSIVE`, `NOT_RUN`, or unavailable evidence into pass.

## Security and authority

Compilation is read-only except for its explicit output path. All paths resolve under admitted roots; candidate bytes remain read-only. Method inputs are data and are never executed during compilation. Network access is forbidden. Authority references and role capabilities are checked, but the compiler cannot grant effect authority, create reviewer independence, authorize Validator dispatch, or approve validation results.

## Compatibility and migration

Extend `compile_review_manifest` and its CLI adapter while preserving `bbk.review-manifest.v1` as the only validation plan. Readers-first schema evolution is allowed if exact CandidateRef provenance cannot fit current `subject`/`provenance`, but the package must continue accepting existing manifests. Existing manifests may be inspected, but consequential candidate validation requires recompilation with D/C bindings; no silent backfill from ambient files.

## Observability

Structured output reports CandidateRef, all input digests, assertions required/assigned, chosen methods, applicability dispositions, lens count, overlap decisions, independence checks, protected floors, manifest digest, and stable failure fingerprint. It records selection rationale references without copying private context or secrets.

## Test strategy

Unit tests cover deterministic partitioning, exact-once ownership, allowed complementary overlap, method resolution, and staleness keys. Integration tests compile a real ReviewManifest, then pass it through existing ReviewContext and review-package validation. Negative/fault controls include wrong CandidateRef, invalidated candidate, stale/non-pass C aggregate, draft contract, subject mismatch, missing assertion, duplicate assignment, undeclared method substitution, profile drift, environment mismatch, required independence overlap, missing context, remote reference with network disabled, output collision, and mutation after candidate admission. Metamorphic tests reorder equivalent inputs and require identical manifest bytes.

## Acceptance criteria

1. A valid exact D candidate and passing C aggregate compile to one schema-valid existing ReviewManifest.
2. Every required AssuranceContract assertion has exactly one primary assignment and no prohibited overlap.
3. The output passes existing ReviewContext compilation without a validation-manifest translation layer.
4. Wrong, stale, invalidated, mutated, or differently gated candidate input blocks compilation.
5. Missing method applicability, qualified environment, profile, or required independence blocks compilation explicitly.
6. Protected floors and non-averaging policy survive byte-for-byte semantic projection.
7. Equivalent normalized inputs produce identical manifest bytes and compiler identity.
8. No successful result claims that validation ran, passed, accepted the candidate, or authorized deployment/release.

## Dependencies and consumers

Dependencies: [PRD C](C-gate-receipt-aggregation.md), [PRD D](D-canonical-candidate-freezer.md), `tools/review_assurance.py`, `tools/context_packages.py`, `bbk.assurance-contract.v1`, `bbk.review-manifest.v1`, and profile/environment receipts.

Consumers: existing ReviewContextManifest/review-package compilers, `bbk_validator_orchestrator`, Validators, [PRD F](F-completion-readiness-compiler.md), and [PRD G](G-lifecycle-qualification-fixture.md).

## Rollout

First add strict binding validation and compiler receipt in shadow mode against current review fixtures. Then make exact CandidateRef and C aggregate mandatory for consequential candidate manifests. Finally route territory validation admission through the command and retire any ad hoc validation-plan JSON producers.

## Risks and open questions

- Current ReviewManifest `subject` may need a readers-first additive schema revision to carry the full CandidateRef without overloading `provenance`.
- Applicability inventories can become stale; their dependency keys and environment identity must be precise.
- Automated “smallest lens set” must remain a deterministic projection of accepted hints/rules, not a semantic judgment.
- Actual independence is partly a dispatch-time fact; compilation can establish requirements and known facts but Validator Orchestrator must recheck it at admission.

## Estimate

7–10 engineer-days: binding/schema work 2–3, compiler evolution 2–3, context integration 1–2, negative and determinism tests 2.
