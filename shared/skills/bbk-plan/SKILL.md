---
name: bbk-plan
description: Create or repair a proportional BBK operating plan from an ambiguous request or supplied plan. Use for operational outcomes, Wayfinding, interfaces, capability-oriented work, work units, assurance contracts, agent selection, and execution readiness.
requires_prompt_modules: []
standalone_prompt_modules: ["bbk-prompt-critical-path-execution"]
---

# BBK Plan

## Delivery-first rolling-wave planning — controlling rule

Use `FAST_CONTINUATION` and `ADOPT_AND_GAP` whenever an accepted outcome and architecture already exist. Establish the whole-project roadmap coarsely as `ROADMAP_READY`, compile only the next one or two executable slices as `FRONTIER_READY`, mark future exact detail `DEFERRED_UNTIL_FRONTIER`, and begin execution immediately when those two states exist. `FULLY_COMPILED` is optional and requires an explicit regulated, contractual, fixed-program, or user requirement.

The exact field list below applies to active-frontier WorkUnits. Future WorkUnits need only stable identity, purpose, owner, dependencies, interface obligations, risk class, and refinement trigger. Generate routine Worker and assertion contracts mechanically. Commission Worker Designer or Verification Designer only for a named material ambiguity. An explicit controlling-user adoption of an exact architecture or baseline is acceptance for unchanged semantics; do not create another proposal/acceptance round trip.

Create the smallest plan that makes safe progress possible. Use `bbk-wayfind` for frontier-first navigation and recurse only when a material contradiction blocks readiness; this skill defines the planning artifact chain and execution-readiness contract.

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

0. Treat the requested intervention as a candidate means unless it is an accepted preference, learning objective, or hard external constraint. Perform a proportionate SolutionOutcomeFit check before material solution commitment and carry exact fit/outcome references downstream.
1. State the operational result, success evidence, current/no-change baseline, actors and affected viewpoints, in-scope boundary, exclusions, constraints, feared events, and accountable decision authority. Record any standing user authority as an explicit grant with its source, already approved effect classes, exact scope, safeguards, exclusions, and revocation or expiry conditions.
2. Calibrate posture: distinguish `USER_DECIDES`, `WAYFINDER_RECOMMENDS`, `DELEGATED`, and `CONSTRAINT_DRIVEN` choices. Separate facts, assumptions, proposals, accepted choices, and unresolved uncertainty.
3. Maintain map, actionable frontier, blockers, and fog. Map only territories needed to reach the result; subdivide for coherent responsibility, authority, specialization, containment, or useful safe parallelism—not prompt length.
4. Route material human decisions through `bbk_questioning_wayfinder`. It should retire discoverable facts and produce a decision-ready recommendation first. Spawn `bbk_question_guide` only when the recommendation is rejected, contested, materially ambiguous, or deeper exploration is requested.
5. Record logical roles separately from physical invocations. Compile explicit context edges and result envelopes; ambient transcript history is not a context contract.
6. Define material interfaces once. Include provider, consumers, ownership, normal behavior, failure, retry, cancellation, compatibility, observability, transition, and recovery as applicable.
7. Compare credible alternatives for consequential, interface-heavy, uncertain, or hard-to-reverse choices. Prototype only when a bounded artifact resolves uncertainty more cheaply than analysis.
8. When realization shape is material, create one domain-neutral ImplementationStructureContract, then coherent ExecutionSlices with integrated touchpoints, integration owners, assertions, evidence, containment, and scaffolding disposition.
9. Organize delivery around actor-visible capability outcomes, then phases and single-concern work units. For every **active-frontier** WorkUnit define purpose, exact inputs, mutation scope, standing-authority grant, capability zones, dependencies, interfaces, expected behavior, exact tool environment, payload limits, operational dispositions, interruption policy, checks, runtime budget, checkpoint/handoff contract, rollback, and completion evidence. For future WorkUnits preserve only stable coarse identity and refinement triggers.
10. Assign task-kind and language/toolchain profiles instead of inventing permanent specialist roles. Bind reusable procedures separately from performer identity and execution authorization.
11. Compile an AssuranceContract from consequence, uncertainty, change class, and protected floors. Prove each material assertion once by the cheapest sufficient method; add independence only for a distinct property.
12. Close deterministic entry checks before effects and plan late candidate freeze. Do not assign candidate identity while ordinary edits remain expected.
13. For stateful or effectful realization, disposition State–Decision–Effect applicability and bind fixed decisions, traces, and formalization proportionately.
14. Compile persisted review records only when separately inspectable assurance is required. Keep context compilation, execution, evidence, findings, and closure distinct.
15. Declare branch purpose, evidence exposure, variation allowed, synthesis/selection rule, disagreement handling, stopping, and later fresh-confirmation needs for exploratory, alternative, replication, robustness, or confirmatory work.
16. End with execution order, safe parallelism, blockers, explicit decision requests, invalidation/reopening triggers, residual fog, economic stopping assessment, and the minimum review needed before starting.

A Planning or Phase Wayfinder that discovers a missing outcome, interface, architecture, authority, risk-acceptance, or verification decision must return a structured decision request to the responsible Wayfinder. It must not silently choose what is needed to make its plan complete.

For a supplied plan, preserve useful structure and add only missing boundaries, interfaces, work-unit contracts, continuation/handoff state, candidate identity, or assurance needed for responsible execution.


## Execution-control compilation

For effectful or long-running work, make these fields explicit rather than leaving them in parent conversation history:

- **Standing authority:** source, approved writes/installations/effects, exact scope, safeguards, exclusions, and revocation or expiry. Children should not re-request routine permission already granted inside this boundary.
- **Capability zones:** a disposable candidate root permits create, expected-hash-guarded replace, rename, and delete inside the exact root; a protected worktree permits mutation only of explicitly owned paths; sealed or historical evidence is immutable.
- **Tool environment:** exact BBK launcher, runtime/compiler/inspection/profile executable paths, versions, activation steps, and deterministic fallbacks.
- **Payload contract:** declared inline/result limits, fail-before-mutation behavior, and file/byte-count/SHA-256 transport for exact or large content.
- **Operational states:** distinguish technical, authority, and decision blockers from capacity or host-window pauses.
- **Interruption policy:** silence, elapsed time, polling timeout, or missing heartbeat are non-evidence. Only an allowed reason with concrete evidence may stop a running child.
- **Return contract:** disposition, exact subject, authority/zone use, changed artifacts and hashes, commands, validation, discoveries, residual uncertainty, blocker/pause class, continuation state, and smallest next action.


## Language and domain profiles

Consult `bbk-installed-profiles` before fixing language-specific structure, work units, gates, or review obligations. Use the exact installed BBK launcher recorded by that registry when `bbk` is not on `PATH`. Bind the smallest compatible profile through `bbk-profile-routing`, load its router first, and record profile version/lock, toolchain assumptions, capability gaps, and profile-owned gates in the operating baseline.
