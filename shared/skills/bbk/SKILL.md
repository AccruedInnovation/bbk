---
name: bbk
description: Use BBK as a lightweight, proportional planning and execution method for complex work. Route requests through planning, bounded execution, review, recovery, evidence, or optional Beads projection without claiming approval, acceptance, compliance, release, or product authority.
---

# BBK

Use BBK to improve coherence without turning ordinary work into a release program.

## Entrypoint responsibility

When this skill is invoked in a primary host session that is not already bound to a canonical BBK role, act as the BBK entry controller. Do not perform the complete task directly merely because the current agent has the necessary tools.

1. Preserve the user's requested terminal condition and inspect the available project records.
2. Route planning, design, materially uncertain, underspecified, architectural, or no-accepted-baseline work to the named `bbk_root_wayfinder` agent.
3. Route execution or recovery of an accepted, sufficiently specified operating baseline to the named `bbk_root_orchestrator` agent. If recovery shows that the baseline itself is invalid or materially incomplete, return to `bbk_root_wayfinder`.
4. Route a bounded independent review to `bbk_reviewer`, or an assertion-scoped acceptance run to `bbk_validator_orchestrator`.
5. Retain user-facing continuity: relay material questions, authority requests, blockers, and final structured results between the selected BBK role and the user.
6. When the host supports named BBK agents, invoke the selected agent rather than merely imitating it, so its configured model, reasoning effort, skills, tools, spawn policy, and return contract apply.
7. When the host cannot invoke named agents, adopt the selected logical role locally while preserving its authority, delegation, evidence, independence, and escalation boundaries.

If the current invocation is already explicitly bound to a canonical BBK role, do not perform entrypoint routing again. Continue under the assigned role and do not recursively launch a duplicate root agent.

## Route the request

1. Preserve the requested terminal condition: understand, plan, execute, review, recover, or close an outcome.
2. Treat an existing plan as a candidate operating baseline. Retain its intent and repair only material execution gaps.
3. Use `bbk-plan` when work needs an outcome, boundary, interfaces, work graph, or assurance contract.
3a. Use `bbk-procedure-design` when recurring or multi-step organizational behavior must be explicit.
3b. Use `bbk-context-routing` whenever a logical role or procedure delegates work across a context boundary.
4. Use `bbk-execute` when a bounded executable plan exists.
5. Use `bbk-review` for an independent assertion-scoped review.
6. Use `bbk-recover` for interrupted, stale, orphaned, or ambiguous work.
7. Use `bbk-evidence` for manifests, candidate identity, receipts, and evidence reuse.
8. Use `bbk-beads` only when the project elects to project BBK coordination records into Beads.

## Installed language and domain profiles

Before material language-, framework-, runtime-, or toolchain-specific work, consult `bbk-installed-profiles`. It is the installation-specific inventory generated from profile packages owned by the active BBK install manifest.

- Route through `bbk-profile-routing` and the matching profile's router skill.
- Load only the focused procedures needed for the current role and assertion; never preload every installed profile or every specialist pack.
- Pass the selected profile identity, effective lock or digest, toolchain assumptions, and required gates into each delegated child invocation.
- If a required profile or external capability is absent, return `BLOCKED` rather than substituting model memory.
- Profile installation adds procedure and evidence expectations only; it does not grant effects, broaden scope, reduce assurance, or authorize success.

## Planning artifact chain

For material solution work, use progressive disclosure rather than automatic ceremony:

1. `bbk-solution-outcome-fit` separates the requested intervention from the outcome, baseline, causal hypothesis, constraints, alternatives, counterfactual, success evidence, and fit disposition.
2. `bbk-implementation-structure` captures realization shape when module/object/contract/state/effect ownership is material.
3. `bbk-execution-slicing` creates the smallest integrated, inspectable, outcome-linked increments.
4. `bbk-profile-routing` consults `bbk-installed-profiles`, confirms live discovery with `bbk --json profile list`, and selects only the applicable language/domain router, procedure, lens, inventory, evidence adapter, and gate recipe.
5. `bbk-procedure-design` distinguishes reusable procedure from performer identity and the exact execution baseline.
6. `bbk-context-routing` binds the smallest authorized context edge and result envelope for each delegation.

Routine obvious work may keep fit implicit or inline. `INVESTIGATE` and `UNRESOLVED` fit dispositions block material implementation commitment while permitting bounded investigation.

## Operating rules

- Make routine, reversible, conventional, and responsibly inferable choices without asking.
- Ask only for authority, private context, protected-floor exceptions, hard-to-reverse commitments, or materially divergent outcomes.
- Define the operational outcome and boundaries before selecting a solution.
- Treat interfaces, ownership, failure, recovery, and transition as first-class concerns.
- Decompose only when the split improves coherence, containment, specialization, or safe parallelism.
- Give each concurrent writer a distinct physical workspace and mutation scope.
- Run deterministic checks before model review.
- Prove each material assertion once by the cheapest sufficient method. Add independence only for a distinct assurance property.
- Freeze candidates late and bind receipts to the exact candidate.
- Preserve failed attempts and findings. Repair through successors instead of rewriting history.
- Distinguish logical roles and reusable procedures from physical invocations; shared execution does not collapse authority or independence.
- Route exact context explicitly and default to no ambient transcript inheritance.
- Preserve evidence exposure. Post-hoc criteria against already-seen outcome evidence are not independent confirmation.
- For language- or domain-specific work, discover and bind one compatible installed profile, load its router skill, and avoid fanning out every profile or focused skill.

## Authority boundary

BBK files are practical project records. They are not authoritative product revisions, readiness attestations, execution authorizations, compliance records, acceptance records, or release packages. Never represent a BBK result as one of those things.

## Return

Lead with the achieved result. Name the active work unit or candidate, evidence actually run, residual findings, and any decision or authority still required. Do not infer approval or completion from prose.

## Design, context, and review routing

- Use `bbk-procedure-design` when organizational control flow, interaction, adaptive branching, or reusable execution semantics are material.
- Use `bbk-context-routing` for every material parent/child, worker/reviewer, question branch, or cross-territory context edge.
- Use `bbk-state-decision-effect-design` when canonical state, transition legality, external effects, ambiguity, retry, cancellation, or recovery is material.
- Use `bbk-review-plan`, `bbk-review-context`, `bbk-review-run`, `bbk-review-findings`, `bbk-review-intent`, and `bbk-review-learn` as separate stages. The AssuranceContract remains the proof obligation; a review run does not create approval, acceptance, compliance, release, or product authority.
