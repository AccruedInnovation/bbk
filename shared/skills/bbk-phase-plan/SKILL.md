---
name: bbk-phase-plan
description: Decompose one accepted BBK phase into an exact, phase-local work-unit graph with owned mutation and integration boundaries, assertion coverage, worker contracts, continuation, and a durable return to the Planning Wayfinder. Use only after the phase charter and governing sources are sufficiently accepted.
requires_prompt_modules: ["bbk-prompt-invocation-binding", "bbk-prompt-delegation-return", "bbk-prompt-durable-handoff", "bbk-prompt-handoff-protocol", "bbk-prompt-state-claim-truth", "bbk-prompt-profile-qualification", "bbk-prompt-execution-slicing", "bbk-prompt-proportional-stop", "bbk-prompt-planning-source-integrity", "bbk-prompt-execution-autonomy", "bbk-prompt-product-first-proportionality", "bbk-prompt-mechanical-admission", "bbk-prompt-assurance-modes", "bbk-prompt-candidate-focused-review"]
standalone_prompt_modules: ["bbk-prompt-critical-path-execution"]
---

# BBK Phase Plan

## Rolling-wave phase readiness — controlling rule

Use `PHASE_SKELETON` for stable phase purpose, ownership, interfaces, dependencies, risks, and refinement trigger; `SLICE_READY` for the exact current execution slice; and `PHASE_FULL` only when explicitly required. For normal work, return as soon as the first safe slice is `SLICE_READY` and leave later slices `DEFERRED_UNTIL_FRONTIER`.

The detailed WorkUnit fields below apply to the active slice. Generate routine Worker and assertion contracts mechanically; call specialists only for named exceptional ambiguity. Refining the next slice must not mutate an admitted current-slice contract.

> Apply the already embedded `bbk-prompt-execution-autonomy` module here.

<!-- BBK prompt module bbk-prompt-critical-path-execution: expanded from canonical source -->

### Execution bias and critical-path economy

Dispatch executable work immediately, resolve scope-preserving blockers locally, and reuse current assurance while retaining authority, safety, candidate-integrity, and truthful-claim floors.

- `CRITICAL_PATH.EXECUTION_PRECEDENCE` — When a current executable WorkUnit has exact scope, applicable authority, mutation ownership, required inputs, selected toolchain, return route, and completion checks, dispatch it immediately by the shortest safe Worker path. No extra planning, design, context package, handoff, review, or verification design unless a named material risk remains unresolved.
- `CRITICAL_PATH.SUPPORT_WORK_TEST` — Before support work, state: (1) material product/authority/safety/interface/environment/completion risk; (2) unresolved proposition; (3) why current deterministic evidence or a standard template cannot resolve it; (4) smallest resolving action. Without all four, execute admitted work or return `NO_MATERIAL_SUPPORT_WORK`.
- `CRITICAL_PATH.FOUR_FACT_DISPATCH` — Worker dispatch has exactly four blocking facts: exact work/scope plus parent return route; current authority/effect fence; workspace/mutation ownership or positive serialization; required inputs, selected profile/toolchain, output carrier, and completion checks. When all four are current, dispatch at once; do not rebuild global admission.
- `CRITICAL_PATH.ATOMIC_BOUND_SPAWN` — For an authorized writable OMP child, call `bbk_control_spawn` once per logical `(parent binding, WorkUnit, attempt)`. It allocates/reuses jj workspace/change and binding, registers the immutable packet, and projects Beads through the single writer. Do not also call `bbk_control_assign` for a normal spawn or change the idempotency key to create a second binding.
- `CRITICAL_PATH.TOKEN_DISPATCH` — The returned `dispatch_ref` is authoritative. Invoke its compact native OMP `dispatch_input` once without rebuilding the private payload. If launch state is uncertain, call `bbk_control_dispatch_status`: READY may retry the same token; LEASED must wait; ACTIVATED must consume the existing child; TERMINAL requires the recorded outcome. Never respawn that logical attempt or emulate dispatch with eval, shell, Python, JavaScript, or another generic surface.
- `CRITICAL_PATH.CONTROL_SERIALIZATION` — Serialize canonical control-plane and Beads mutations; parallelize independently admitted child execution. A writer lease does not authorize another attempt: wait for the bounded serializer or return its typed blocker.
- `CRITICAL_PATH.ONE_CHECK` — A successful deterministic validation or review receipt is current while its exact subject binding and declared invalidation-key values are unchanged. Reuse is mandatory. Do not repeat the underlying validation or review unless a declared invalidation key changed, the receipt is missing, mismatched or corrupt, or the contract explicitly requires an independent method; otherwise record `REUSED_RECEIPT` rather than creating recovery work.
- `CRITICAL_PATH.MECHANICAL_REPAIR` — Before candidate freeze or irreversible/external effect, preserve and locally fix any reversible materialization, schema-shape, canonicalization, path, digest, byte-count, manifest, package, carrier, locator, ledger, profile-projection, or tool-projection defect in the same semantic run and physical attempt. Regenerate only affected material, rerun only its mechanical gate, and continue. Create no successor plan, WorkUnit, campaign, authority package, review cycle, or zero-credit lineage unless semantics, authority, protected floors, interfaces, ownership, or completion meaning changed.
- `CRITICAL_PATH.LOCAL_BLOCKER_REPAIR` — Treat missing inputs, wrong or stale paths, new runtime facts, environment mismatch, and other scope-preserving technical failures as local execution blockers. Fix them in the same physical attempt when authority/ownership allow; otherwise admit the smallest successor WorkUnit or physical attempt that supplies/corrects the fact/effect. Do not reopen planning unless evidence establishes a material change to intended outcome/semantics, architecture/shared interfaces, authority, protected floors, ownership boundaries, risk posture, or completion meaning. Report the exact blocked scope; continue all independent useful frontiers.
- `CRITICAL_PATH.STRUCTURED_RETURN` — Use the structured role result directly when it carries the result without loss/truncation. Seal a handoff package only for large/truncation-sensitive output, binary content, durable cross-session/process/host recovery, a schema-required package, or exact artifact/evidence closure unsafe inline.
- `CRITICAL_PATH.VALIDATOR_SCOPE` — Run targeted checks during implementation. Run each applicable broad product validator at most once against the final frozen candidate and only when a declared inspected input, implementation, configuration, tool identity, or environment invalidation key changes. Planning/evidence/coordination/log/handoff metadata alone does not trigger unrelated product validators.
- `CRITICAL_PATH.ASSURANCE_ECONOMY` — Default routine assurance to INLINE. Group compatible assertions sharing candidate, method/toolchain, environment, fixtures, exposure, and independence requirements into one evidence-producing assignment. Commission Reviewer only for a named qualitative or cross-cutting product risk deterministic checks cannot establish; independent judgment does not require duplicate mechanics.
- `CRITICAL_PATH.PLANNING_STOP` — Stop wayfinding, architecture, Worker design, and verification design when executable WorkUnits, authority, ownership, selected toolchain, return route, and completion checks exist. Fix local blockers without replanning. Only evidence of material change to intended outcome/semantics, architecture/shared interfaces, authority, protected floors, ownership boundaries, risk posture, or completion meaning reopens the right semantic owner.
- `CRITICAL_PATH.ROUTING_EFFORT` — An effort-only routing change within an already qualified model/provider family is runtime cost tuning, not semantic invalidation. Record runtime-policy provenance; do not regenerate planning or invalidate evidence whose declared method, subject, configuration, environment, and qualification keys remain current.
- `CRITICAL_PATH.GOVERNANCE_FLOORS` — Optimization never weakens exact WorkUnit identity/scope; write/effect authority; single mutation ownership or positive serialization; protected floors/fixed interfaces; external, destructive, or secret-bearing effect controls; post-freeze candidate immutability; applicable completion checks; preservation of failed evidence/findings; cleanup/residual reporting; or truthful claim limits. No child self-accepts, self-releases, or replaces user authority.
- `CRITICAL_PATH.CANONICAL_SOURCE` — This is core BBK execution policy. Harness projections, role prompts, and procedure bodies consume one canonical source; independently maintained copies are prohibited.

<!-- End BBK prompt module bbk-prompt-critical-path-execution -->

This procedure compiles **one accepted phase charter** into a detailed, worker-ready phase plan. It does not define the global phase topology, change capability relations, accept shared interfaces, grant authority, authorize execution, validate a candidate, or approve completion.

The semantic sequence is:

```text
accepted phase charter and supplied slices, when any
  → coherent phase boundary check
  → phase-local slice refinement within delegated bounds
  → atomic work units
  → phase-local dependencies and mutation ownership
  → integration obligations and assertion coverage
  → exact worker-invocation contracts
  → versioned phase plan
  → Planning Wayfinder integration
```

A phase plan can be complete as a planning artifact without the phase having been executed, validated, accepted, or released.

## 1. Bind the exact phase charter

> Apply the already embedded `bbk-prompt-invocation-binding` module here.

> Apply the already embedded `bbk-prompt-planning-source-integrity` module here.

Bind the exact phase subject and revision, Planning Wayfinder parent, phase purpose and capability contribution, entry and exit conditions, accepted interfaces and decisions, cross-phase obligations, exclusions, local design freedom, source and profile bindings, assertion and Worker-contract commissioning duties, and exact return.

Classify every governing source as exactly one of:

```text
ACCEPTED
DELEGATED
CONSTRAINT_DRIVEN
PROPOSED
ASSUMED
STALE
CONTRADICTORY
MISSING
```

Only `ACCEPTED`, `DELEGATED`, or `CONSTRAINT_DRIVEN` sources may govern the phase plan. Keep every other class explicit and route the resulting repair, decision, or recharter need to its owner; do not reconstruct a missing or stale upstream decision from ambient conversation or implementation convenience.

## 2. Test the phase boundary before decomposing

A valid phase ends in one coherent, integrated, testable state. It may advance several capability increments, and one capability increment may span several phases, but the relationship must already be explicit in the parent graph.

Check whether the supplied phase:

- has one intelligible purpose and exit state;
- can be planned under one coherent authority and assurance regime;
- has stable-enough participating interfaces for independent work;
- has bounded internal dependencies and integration ownership;
- can be decomposed into work units that fit suitable worker contexts and reviewable handoffs;
- is not merely a repository, language, component, team, or technical-layer tranche;
- does not hide several independently coherent phases;
- does not require the Phase Wayfinder to alter cross-phase ordering, capability relations, shared interfaces, or governing decisions.

When the boundary fails, do not create nested phases. Return one of:

```text
NEEDS_PARENT_PHASE_RECHARTER
NEEDS_PARENT_RESYNTHESIS
NEEDS_PARENT_DECISION
BLOCKED
```

Include the exact defect, affected work, smallest parent action, and any reusable partial decomposition.

## 3. Operationalize entry and exit without redefining them

Translate the accepted phase charter into an executable planning boundary:

- exact predecessor state and entry evidence;
- entry gates that must be true before phase work begins;
- observable integrated exit behavior;
- requirements and capability contributions made testable by the phase;
- risk, uncertainty, migration burden, or integration concern retired;
- phase-local integration assembly and earliest useful touchpoints;
- deterministic, evidentiary, review, and parent-owned gates that consume the result;
- invalidation and reopening conditions;
- successor handoffs and assumptions.

If the accepted exit conditions are ambiguous, mutually inconsistent, unverifiable, or impossible under current interfaces and authority, return the defect to the Planning Wayfinder. Do not silently rewrite the phase.

## 4. Bind or refine phase-local slices, then define atomic work units

> Apply the already embedded `bbk-prompt-execution-slicing` module here.

Bind every `ExecutionSlice` supplied by the Planning Wayfinder. Where the phase charter explicitly delegates local slicing freedom, refine or define only the slices needed inside the accepted phase boundary. A slice change that alters capability-to-phase relations, cross-phase sequencing, phase topology, shared interfaces, or parent-level integration returns to the Planning Wayfinder. Each phase-local slice must preserve its parent-graph relationship, integrated touchpoint, owner, work-unit set, assertions, containment, scaffolding disposition, and invalidation conditions.

A work unit is **atomic** when it is independently assignable and verifiable, normally fits one suitable worker context, and produces one reviewable handoff. Atomic does not mean one file, one commit, one tool call, one model turn, or a universal duration.

For every WorkUnit in the **active slice**, define at least:

- stable ID and concise purpose;
- phase, capability, outcome, requirement, structure, slice, interface, decision, and assurance traceability;
- exact in-scope and out-of-scope surfaces;
- preconditions and exact inputs;
- expected outputs and behavior;
- dependencies and consumers;
- likely affected paths, objects, resources, configurations, or external targets;
- one production owner and the logical worker class;
- mutation scope, prohibited scope, readable scope, and external-effect requirements;
- task-kind, language, domain, runtime, framework, and toolchain profile needs;
- required and optional procedures or skills;
- assertions completed and checks that expose the result;
- rollback, cleanup, compensation, or safe-disposition requirements;
- discovery policy for already-implied repair versus genuinely new work;
- runtime, cost, checkpoint, continuation, and payload requirements;
- exact result and handoff schema.

A work unit is too large when it contains several independently assignable responsibilities, incompatible authority or environments, unrelated mutation regions, several unrelated handoffs, or a context footprint that prevents coherent execution and evidence. It is too small when the split adds coordination without improving ownership, containment, integration, verification, or specialization.

One work unit may contribute to several execution slices. One execution slice may require several work units. Preserve both relations explicitly.

## 5. Compile the phase-local dependency graph

Record every phase-local ordering relationship and the reason for it:

- data or artifact dependency;
- accepted interface dependency;
- state or migration dependency;
- authority or environment prerequisite;
- integration ordering;
- evidence or gate prerequisite;
- shared-resource serialization;
- explicit repair, retry, or recovery loop.

A normal dependency graph should be acyclic. An iteration or recovery cycle is permitted only when it is explicit, bounded, has an owner and stopping condition, and does not conceal an unresolved design or authority loop.

Safe parallelism requires more than the absence of a declared dependency. Before marking work parallel, verify that the units do not have:

- overlapping mutation or external-effect targets;
- incompatible interface assumptions;
- conflicting generated artifacts or candidate inventory;
- shared credentials, devices, services, environments, ports, databases, controllers, or rate limits without serialization;
- evidence contamination or independence conflicts;
- incompatible branch, workspace, or migration ownership.

## 6. Assign mutation and workspace ownership

Every mutable path, object, resource, configuration surface, schema, migration target, remote system, or external-effect target has exactly one current production owner for the relevant execution window.

Distinguish:

```text
DISPOSABLE CANDIDATE ROOT
PROTECTED WORKTREE
SEALED OR HISTORICAL EVIDENCE
SHARED READ-ONLY RESOURCE
SERIALIZED SHARED MUTATION
EXTERNAL EFFECT TARGET
```

For each zone record allowed operations, guards, workspace or branch, expected prior-state checks, cleanup or successor behavior, and authority source.

Writable scope is not authority. Tool availability is not authority. Physical access is not authority. The Worker Designer must bind the accepted grant into the exact invocation contract.

If ownership overlaps cannot be removed without changing the phase topology or shared interface, return the conflict to the Planning Wayfinder.

## 7. Create integration obligations for every work-unit split

Every decomposition creates boundary work.

For each internal or phase-exit integration obligation record:

- stable identity;
- pieces and owners being integrated;
- one accountable integration owner;
- canonical interface or exchange boundary;
- assembly point and earliest coherent exercise point;
- sequencing, compatibility, migration, and rollback expectations;
- normal, degraded, failure, timeout, duplicate, partial-completion, cancellation, and recovery behavior where material;
- observability and diagnostic needs;
- linked assertion, evidence method, and completing work unit;
- affected successor work;
- invalidation and reopening trigger.

The Phase Wayfinder owns phase-internal and phase-exit integration planning. Cross-phase integration ownership, shared-interface changes, and changes to sibling work remain Planning Wayfinder concerns.

Do not permit independent production on both sides of a materially unstable interface unless a current accepted source defines one of these bounded exceptions:

- both sides intentionally co-evolve inside one work unit;
- the work is a disposable prototype;
- the interface is experimental with explicit containment, authority, evidence, rollback, and revalidation.

## 8. Commission and integrate phase-local verification design

The Phase Wayfinder owns phase-local claim identification, commissioning, return validation, work-graph integration, and readiness. The Verification Designer owns exact assertion wording, methods, environments, thresholds, evidence, applicability, independence, revalidation, and unavailable-capability disposition. The Phase Wayfinder does not silently author or repair that specialist design.

Identify claims for:

- phase entry and exit;
- work-unit integration and phase assembly;
- requirements and quality scenarios;
- interface behavior and compatibility;
- state invariants, transitions, decisions, effects, and recovery;
- feared-event prevention or containment;
- migration, rollback, cancellation, retry, timeout, duplicate, partial-completion, and ambiguous-result behavior;
- operational validation and outcome contribution where the phase can establish them.

Invoke `bbk_verification_designer` when assertion or evidence design is missing, ambiguous, duplicated, method-sensitive, environment-sensitive, or independence-sensitive.

Before phase-plan readiness require:

- every active assertion has exactly one completing leaf work unit;
- one work unit may complete several related assertions;
- a foundational work unit may complete none only with an explicit rationale;
- every assertion is placed at the earliest sufficient phase gate;
- every method names the exact subject, environment, expected evidence, and acceptance threshold;
- integration checking, requirement verification, operational validation, outcome evidence, and independent review remain distinct;
- deterministic evidence is preferred when it proves the same claim;
- no critical or protected-floor failure can be averaged away by unrelated positive evidence.

A broad suite or Reviewer cannot substitute for undefined assertions.

## 9. Commission and integrate exact Worker invocation contracts

Once a work-unit charter is stable, compile the exact input needed by `bbk_worker_designer`:

- work-unit identity, purpose, scope, inputs, outputs, dependencies, interfaces, and expected behavior;
- mutation and prohibited scope, external effects, isolation, and capability zones;
- standing-authority source, safeguards, exclusions, and expiry;
- task and profile requirements;
- procedures and skills;
- exact tool, runtime, compiler, inspection, and environment requirements known at phase level;
- assurance, checks, expected evidence, and assertions;
- runtime, cost, concurrency, recursion, checkpoint, continuation, and retry constraints;
- payload limits and fail-before-mutation behavior;
- discovery policy;
- operational dispositions, interruption reasons, result schema, and durable handoff requirements.

The Worker Designer produces the exact least-privilege invocation contract. The Phase Wayfinder owns the semantic commission, coverage, return validation, reference, and integration of that result; it does not design or modify the contract, fill missing executable paths, broaden tools or effects, or substitute model capability for an invocation contract.

A bounded set of homogeneous units may be sent in one Worker Designer call only when every unit retains a separate complete contract and shared profile or tool derivation does not blur mutation, authority, continuation, evidence, or result boundaries.

## 10. Map structure, slices, and State–Decision–Effect obligations

Carry current accepted realization contracts into the phase plan rather than rediscovering them during implementation.

For applicable `ImplementationStructureContract` objects, preserve:

- fixed decisions and delegated freedom;
- artifact and responsibility topology;
- key contracts and private-versus-shared boundaries;
- canonical state, rule, schema, and effect ownership;
- failure, compatibility, migration, recovery, and observability obligations;
- prohibited shortcuts and planned-versus-actual review points.

For every applicable `ExecutionSlice`, preserve:

- outcome and fit references;
- real integrated touchpoint;
- one integration owner;
- contributing work units;
- interfaces and dependency closure;
- assertions and evidence;
- containment, rollback, cleanup, and scaffolding disposition;
- earliest useful feedback and enabled successor slice.

For applicable State–Decision–Effect work, place implementation and evidence for state transitions, decision boundaries, typed effects, authority, receipts, idempotency, duplicates, ordering, retries, cancellation, timeout, partial completion, ambiguous acknowledgement, fencing, compensation, and recovery at the earliest coherent boundary.

A missing governing structure or state/effect decision returns upward. It is not a Phase Wayfinder implementation detail.

## 11. Plan execution continuity without authorizing execution

Allocate phase-level constraints to work units:

- logical execution window;
- runtime and cost envelope;
- concurrency and shared-resource limits;
- checkpoint cadence;
- durable continuation identity and state path;
- same-thread continuation preference and justified replacement conditions;
- payload and result-channel limits;
- interruption, pause, retry, cancellation, and recovery semantics;
- environment, toolchain, device, credential-availability, and fallback constraints.

The Phase Wayfinder owns WorkUnit semantic completeness, commissioning, return validation, phase-plan integration, and readiness. The Worker Designer owns the exact invocation contract, including host-specific values and executable paths. The execution orchestrator later owns scheduling and lifecycle within the accepted baseline.

Silence, elapsed time, polling timeout, delivery receipt, missing heartbeat, host-window exhaustion, context pressure, or physical child termination is not semantic completion, approval, cancellation, or failure evidence by itself.

## 12. Define the phase exit and later candidate contribution

The phase plan should state:

- expected produced and modified inventory;
- phase-local integration assembly;
- deterministic checks before the phase result is handed upward;
- phase-exit evidence and unresolved evidence gaps;
- temporary scaffolding and its removal, retention, or successor disposition;
- handoffs to successor phases and parent integration;
- which outputs may contribute to the later global candidate;
- which changes invalidate the phase plan, result, or evidence.

Do not freeze or accept the global candidate. Do not schedule validators. Do not describe a ready phase plan as an executed or accepted phase.

## 13. Validate child returns

> Apply the already embedded `bbk-prompt-delegation-return` module here.

Validate every Verification Designer, Worker Designer, and Reviewer return against its exact phase-local charter, subject, revision, authority, provenance, schema, evidence exposure, blockers, and integration obligations. Return nonconforming work to its owner rather than repairing the specialist contract inside the phase plan.

## 14. Handle discovered work and invalidation

> Apply the already embedded `bbk-prompt-planning-source-integrity` module here.

Record newly discovered work as a proposed phase delta with exact cause, affected outcome or obligation, dependency and integration impact, assertion and Worker-contract impact, and parent disposition required. Preserve the predecessor plan and invalidate only the affected phase-local closure.

## 15. Use review and decomposition proportionately

> Apply the already embedded `bbk-prompt-proportional-stop` module here.

Avoid tracking-only WorkUnits, duplicate checks, speculative abstraction, and independent review without a distinct property. Continue decomposition only until every leaf is coherent, independently assignable, integration-bound, assertion-covered, Worker-ready, and proportionate to consequence.

## 16. Return to the Planning Wayfinder

> Apply the already embedded `bbk-prompt-durable-handoff` module here.

> Apply the already embedded `bbk-prompt-handoff-protocol` module here.

> Apply the already embedded `bbk-prompt-state-claim-truth` module here.

Return the exact `bbk.phase-wayfinder-return.v1` envelope and versioned phase plan. Include leaf WorkUnits, local dependency order, mutation and workspace ownership, integration obligations, specialist contracts and coverage, checks, continuation, blockers, invalidation, outward impacts, and smallest Planning Wayfinder action. Phase readiness is not global graph acceptance or execution authority.

## Profile interaction

> Apply the already embedded `bbk-prompt-profile-qualification` module here.

## Product-first proportional workflow

> Apply the already embedded `bbk-prompt-product-first-proportionality` module here.

> Apply the already embedded `bbk-prompt-mechanical-admission` module here.

> Apply the already embedded `bbk-prompt-assurance-modes` module here.

> Apply the already embedded `bbk-prompt-candidate-focused-review` module here.
