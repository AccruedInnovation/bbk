---
name: bbk-work-graph
description: Compile an accepted planning basis into a capability-oriented, dependency-valid, assurance- and worker-complete execution work graph. Use by the BBK Planning Wayfinder after governing outcome, architecture, interface, authority, and assurance decisions are sufficiently accepted for decomposition.
requires_prompt_modules: ["bbk-prompt-invocation-binding", "bbk-prompt-delegation-return", "bbk-prompt-durable-handoff", "bbk-prompt-handoff-protocol", "bbk-prompt-state-claim-truth", "bbk-prompt-profile-qualification", "bbk-prompt-execution-slicing", "bbk-prompt-proportional-stop", "bbk-prompt-planning-source-integrity", "bbk-prompt-execution-autonomy", "bbk-prompt-product-first-proportionality", "bbk-prompt-mechanical-admission", "bbk-prompt-assurance-modes", "bbk-prompt-candidate-focused-review"]
standalone_prompt_modules: ["bbk-prompt-critical-path-execution"]
---

# BBK Work Graph

## Rolling-wave graph readiness — controlling rule

`ROADMAP_READY` requires coarse charters for the whole known project. `FRONTIER_READY` requires exact phase, WorkUnit, assertion, ownership, authority, toolchain, integration, cleanup, and return contracts only for the active execution frontier. Future phases and WorkUnits remain `DEFERRED_UNTIL_FRONTIER` until refinement is necessary.

Commission a Phase Wayfinder only for an active-frontier phase whose detailed decomposition is not already mechanically derivable. Generate routine Worker and assertion contracts from accepted records; invoke Worker Designer or Verification Designer only for a named material ambiguity. A graph is executable at `ROADMAP_READY + FRONTIER_READY`; do not wait for all future work to be fully compiled.

> Apply the already embedded `bbk-prompt-execution-autonomy` module here.

<!-- BBK prompt module bbk-prompt-critical-path-execution: expanded from canonical source -->

### Execution bias and critical-path economy

Dispatch executable work immediately, resolve scope-preserving blockers locally, and reuse current assurance while retaining authority, safety, candidate-integrity, and truthful-claim floors.

- `CRITICAL_PATH.EXECUTION_PRECEDENCE` — When a current executable WorkUnit has exact scope, applicable authority, mutation ownership, required inputs, selected toolchain, return route, and completion checks, dispatch it immediately by the shortest safe Worker path. No extra planning, design, context package, handoff, review, or verification design unless a named material risk remains unresolved.
- `CRITICAL_PATH.MINIMUM_CEREMONY` — For a clear, local, reversible Level 0 change, route directly to one Worker, freeze only a lightweight changed-file-set identity, and run exactly one grouped independent candidate-bound Validator. Do not require Root Wayfinder, Root Orchestrator, Reviewer, ReviewManifest, sealed package, or broad-suite validation unless a named escalation trigger applies.
- `CRITICAL_PATH.ESCALATION_TRIGGERS` — Escalate only for unclear outcome or acceptance meaning, shared/public interface change, multiple mutation owners, external/credential/network/deployment/migration/destructive/irreversible effects, a new recovery contract, a named qualitative risk, explicit acceptance/publication/release, or an inconclusive/materially unrepaired routine Validator. Inspectable, parameterizable, safely defaulted, or deferrable unknowns do not escalate by themselves.
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

This procedure compiles **accepted planning inputs** into an executable work graph. It does not establish the outcome, choose the architecture, accept shared interfaces, grant authority, approve the operating baseline, or authorize execution.

The semantic sequence is:

```text
accepted planning basis
  → actor-visible capability increments
  → coherent phases
  → phase-owned work units
  → assertions, evidence, workers, and handoffs
  → versioned work graph
  → semantic-parent integration
```

A graph can be complete as a planning artifact without being accepted or authorized for execution.

## 1. Bind the accepted planning basis

> Apply the already embedded `bbk-prompt-invocation-binding` module here.

> Apply the already embedded `bbk-prompt-planning-source-integrity` module here.

Bind the exact planning subject, semantic parent, requested outcome, accepted fit and architecture, source revisions, shared interfaces, requirements, feared events, authority sources, profile and environment constraints, exclusions, prior graph state, and return contract before compiling capability increments or phases.

## 2. Define actor-visible capability increments

> Apply the already embedded `bbk-prompt-execution-slicing` module here.

A capability increment states what an actor can meaningfully accomplish end to end after the increment exists. It is not a repository layer, component list, team tranche, or file grouping.

For each increment define:

- stable identity and actor;
- independently meaningful ability and operational outcome advanced;
- accepted source decisions, requirements, quality scenarios, and feared events;
- participating architecture elements and material interfaces;
- entry assumptions and observable exit behavior;
- risk, uncertainty, migration burden, or integration concern retired;
- predecessor and successor capability relations;
- assertions, fixtures, demonstrations, or operational observations needed to attribute success;
- residual uncertainty and reopening triggers.

Prefer increments that cross the risky or uncertain causal and interface boundaries early. Technical foundation work may appear beneath an increment when it is genuinely enabling, but it does not become the primary increment merely because it is convenient to schedule.

Do not force one increment to equal one phase. An increment may span phases; one phase may advance several increments. Preserve the relationship explicitly.

## 3. Define the phase topology

A phase ends in a coherent, testable state. It is a planning boundary around integrated behavior and risk retirement, not a bucket of related tasks.

For each phase define:

- stable identity, purpose, and capability relations;
- entry conditions and exact predecessor state;
- actor-visible or integration-visible exit behavior;
- participating territories, architecture elements, and interfaces;
- dependencies, ordering, and safe parallelism;
- risks or uncertainty retired;
- integration obligations created by the phase boundary;
- assertions, evidence, review, and acceptance gates;
- operational prerequisites, environments, credentials, tools, and recovery assumptions;
- invalidation and reopening conditions.

The Planning Wayfinder owns the phase topology and cross-phase coherence. A **Phase Wayfinder** owns the detailed decomposition of one phase into work units, mutation ownership, phase-local sequencing, integration, checks, execution windows, and handoffs.

Every **active-frontier** executable phase has a Phase Wayfinder contract when detailed decomposition is not mechanically derivable. A genuinely atomic phase may be handled in the same physical invocation only when the Phase Wayfinder remains an explicit logical responsibility with its own charter, result, ownership, and return boundary. Do not silently create a phase-local work unit under Planning Wayfinder authority merely to avoid a child invocation.

## 4. Create integration obligations for every split

Every decomposition creates work at the boundary.

For each capability, phase, territory, or work-unit split, record:

- the pieces being integrated;
- one integration owner;
- the canonical interface or exchange boundary;
- the integration point and earliest coherent phase;
- sequencing, compatibility, migration, and rollback expectations;
- failure, timeout, duplicate, partial-completion, cancellation, and recovery implications where material;
- observability and diagnostic needs;
- the assertion and evidence method that establish the integration;
- what upstream change invalidates the obligation or its evidence.

Do not permit independent production planning on both sides of a material interface until its contract is stable enough for that independence. An accepted exception must keep the work inside one bounded co-evolving unit or disposable prototype and state the resulting authority, containment, integration, and assurance consequences.

## 5. Delegate and integrate phase plans

> Apply the already embedded `bbk-prompt-delegation-return` module here.

Commission one exact Phase Wayfinder charter for each non-atomic **active-frontier** phase that still requires detailed decomposition. Preserve phase purpose, accepted decisions, shared contracts, cross-phase obligations, delegated freedom, exclusions, assertion and Worker-contract commissioning duties, and exact return. Validate and integrate each phase result without absorbing phase-local ownership.

## 6. Commission and integrate verification design before sealing the graph

Planning and verification are one design activity with separate owners.

The Planning Wayfinder identifies graph-level claim obligations, including:

- capability outcomes;
- cross-phase behavior;
- shared-interface obligations;
- quality scenarios and feared-event mitigations;
- migration and compatibility;
- operational readiness and recovery;
- intent conformance and outcome evidence.

Invoke the **Verification Designer** directly when one coherent cross-graph assertion and evidence design is needed. Route phase-local claims through the owning Phase Wayfinder, which identifies and charters the need, supplies phase semantics, validates and integrates the return, and owns phase-plan readiness.

The Verification Designer owns exact assertion definitions, evidence methods, environments, stages, independence rationale, coverage, revalidation, and unavailable-capability disposition. The Planning Wayfinder owns integration of graph-level objects into the work graph; the Phase Wayfinder owns integration of phase-local objects into the phase plan. Neither Wayfinder silently takes over the specialist design.

Before readiness, require:

- every active assertion has exactly one completing leaf work unit;
- every assertion names the cheapest sufficient method and expected evidence;
- every assertion belongs to the applicable phase or cross-graph gate;
- deterministic evidence is preferred when it proves the same claim;
- independence is added only for a distinct assurance property;
- no critical or protected-floor failure is averaged away by unrelated positive results;
- evidence reuse has explicit subject, input, environment, and invalidation boundaries.

A broad suite or reviewer cannot substitute for an undefined assertion.

## 7. Commission and integrate Worker invocation design before sealing the graph

A work unit is not execution-ready merely because its task text exists.

The graph must identify, directly or through child-owned references:

- logical worker role or class;
- required and optional skills or procedures;
- applicable language, domain, runtime, framework, and toolchain profiles;
- model capability and escalation conditions;
- exact tools, executable or fallback paths, versions, and activation steps;
- mutation scope, isolation, workspace, and capability zones;
- standing-authority source, limits, safeguards, exclusions, and expiry;
- runtime and cost budget, concurrency, recursion, and retry policy;
- payload limits and fail-before-mutation behavior;
- discovery policy for newly found work;
- operational disposition vocabulary;
- checkpoint cadence, continuation identity, interruption policy, and durable handoff;
- exact result schema and required evidence.

Invoke the **Worker Designer** directly for a reusable worker class, shared skill or procedure capsule, cross-phase execution-control contract, or common least-privilege invocation pattern. For concrete phase-local WorkUnits, the Phase Wayfinder supplies the semantic contract, commissions the design, validates and integrates the return, and owns phase-plan readiness; the Worker Designer owns the exact invocation-contract design.

Do not use model strength or Wayfinder authority as a substitute for an exact Worker Designer contract.

## 8. Validate graph invariants

Before declaring the graph ready for parent integration, verify at least:

- every work unit traces to a phase, capability increment, and accepted planning source;
- every capability relation and cross-cutting phase relation is represented explicitly;
- the dependency graph is valid, with no unexplained cycle or hidden ordering edge;
- safe parallelism has no overlapping mutation or incompatible interface assumptions;
- every decomposition has one owned integration obligation;
- every active assertion has one completing leaf work unit and sufficient evidence method;
- every work unit has one production owner and an adequate worker-invocation contract;
- validator, review, and acceptance responsibilities remain separate from production ownership;
- all required tools, environments, credentials, isolation, recovery, and checkpoints are known or blocked explicitly;
- handoffs are exact enough to survive context and host-window boundaries;
- no unresolved finding, authority gap, protected-floor failure, or stale source is hidden by aggregate completeness;
- residual uncertainty is explicit, bounded, owned, and economically justified.

Readiness is calculated from these invariants. It is not a narrative claim.

## 9. Compile graph-level execution controls

Verify that phase and worker contracts carry the controls needed for execution without relying on ambient conversation:

- standing authority and per-work-unit grants;
- capability zones and mutation fences;
- exact tool environments and version probes;
- payload and result-transport limits;
- technical, authority, decision, capacity, and host-window dispositions;
- heartbeat, timeout, interruption, retry, pause, resume, and cancellation semantics;
- runtime, cost, concurrency, and recursion budgets;
- durable checkpoints, continuation identity, and same-thread or replacement policy;
- candidate inventory and late-freeze obligations;
- finding, repair, revalidation, and closure paths.

Silence, elapsed time, delivery receipt, missing heartbeat, or physical task termination is not semantic completion, approval, cancellation, or failure evidence by itself.

## 10. Freeze candidates late

Plan the exact candidate inventory and freeze operation only after ordinary graph-shaping edits are expected to stop.

The plan should state:

- inventory roots and exclusions;
- generated, vendored, environment, and external-state treatment;
- dependency and configuration bindings;
- candidate digest or identity method;
- which gates run before and after freeze;
- what changes invalidate the candidate and prior evidence;
- how a successor candidate is created and related to the prior one.

Candidate identity does not grant acceptance or release authority.

## 11. Preserve invalidation and partial reuse

> Apply the already embedded `bbk-prompt-planning-source-integrity` module here.

When a source changes, preserve the predecessor graph, calculate the deterministic affected subgraph and evidence closure, invalidate only impacted capability, phase, WorkUnit, assertion, Worker-contract, integration, and handoff records, and request the smallest sufficient successor work.

## 12. Use review proportionately

> Apply the already embedded `bbk-prompt-proportional-stop` module here.

Use Reviewer only for a distinct bounded judgment—such as intent conformance, proportionality, cross-phase coherence, or readiness—that deterministic graph checks and specialist contracts do not already establish.

## 13. Return to the semantic parent

> Apply the already embedded `bbk-prompt-durable-handoff` module here.

> Apply the already embedded `bbk-prompt-handoff-protocol` module here.

> Apply the already embedded `bbk-prompt-state-claim-truth` module here.

Return the exact `bbk.planning-wayfinder-return.v1` envelope and versioned work graph. Include capability and phase topology, dependency and integration closure, WorkUnit index, assertion and Worker-contract coverage, execution-control requirements, blockers, invalidation, review dispositions, and smallest parent-owned next action. Work-graph readiness is not baseline acceptance or execution authorization.

## Profile interaction

> Apply the already embedded `bbk-prompt-profile-qualification` module here.

## Product-first proportional workflow

> Apply the already embedded `bbk-prompt-product-first-proportionality` module here.

> Apply the already embedded `bbk-prompt-mechanical-admission` module here.

> Apply the already embedded `bbk-prompt-assurance-modes` module here.

> Apply the already embedded `bbk-prompt-candidate-focused-review` module here.
