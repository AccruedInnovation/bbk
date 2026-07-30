---
name: bbk-wayfind
description: Navigate an uncertain outcome through posture, low-resolution mapping, recursive territory work, decision and investigation routing, invalidation, economic stopping, and synthesis. Use by BBK Wayfinders before or while compiling an operating baseline.
---

# BBK Wayfind

Wayfinding is a recursive navigation procedure, not a one-pass planning checklist.

## 1. Frame the destination and authority

1. State the operational outcome, success evidence, current/no-change baseline, actors and affected viewpoints, in-scope and out-of-scope boundaries, constraints, feared events, and accountable authority.
2. Calibrate interaction posture proportionately. Record which choices are `USER_DECIDES`, `WAYFINDER_RECOMMENDS`, `DELEGATED`, or `CONSTRAINT_DRIVEN`; what must interrupt the user; and what may be inferred responsibly.
3. Separate facts, assumptions, proposals, accepted decisions, delegated defaults, and unresolved uncertainty.

## 2. Maintain the active planning state

Keep four distinct sets current:

- **Map:** known territories, responsibilities, interfaces, accepted decisions, and dependencies.
- **Frontier:** precise questions, investigations, prototypes, reviews, or planning actions that are actionable now.
- **Blockers:** conditions preventing otherwise actionable work.
- **Fog:** relevant uncertainty that is not yet sharp enough to become a question or task.

Do not convert all fog into work merely to appear complete. Do not silently discard it.

## 3. Run the recursive loop

Repeat until synthesis is justified:

1. Load the current destination, posture, accepted decisions, territory scope, interfaces, frontier, blockers, and fog.
2. Map the territory at low resolution before deep decomposition.
3. Decide whether one Wayfinder can coherently own it. Subdivide only when responsibility, authority, expertise, containment, or safe parallelism materially improves.
4. When subdividing, define each child boundary and the integration obligations created by the split.
5. Sharpen the highest-value visible uncertainty into a decision, research, prototype, architecture, review, or planning action. Leave the rest as fog.
6. Dispatch bounded work with an exact context edge, authority, stopping condition, and return envelope.
7. Receive results and update decisions, dependencies, interfaces, impacts, frontier, blockers, and fog.
8. Invalidate or reopen downstream objects when an upstream decision, fact, interface, or subject changes. Do not preserve stale work because it was expensive.
9. Reassess whether the territory still needs subdivision and whether another action has positive information value.
10. Synthesize only when no blocking frontier item remains and residual uncertainty is explicit and proportionate.

## 4. Route work without ceremony

- Route discoverable facts to `bbk_researcher`.
- Route a bounded empirical discriminator to `bbk_prototyper`.
- Route a material human decision to `bbk_questioning_wayfinder`, which should first produce a decision-ready recommendation. Use `bbk_question_guide` only when the recommendation is rejected, contested, materially ambiguous, or the user requests deeper exploration.
- Route architecture synthesis to `bbk_architect` after the governing decisions are sufficiently resolved.
- Route capability/phase/work decomposition to `bbk_planning_wayfinder`; it may use `bbk_phase_wayfinder`.
- Route assurance composition to `bbk_verification_designer` and worker composition to `bbk_worker_designer`.
- Route independent challenge to `bbk_reviewer` only for a distinct assurance reason.

A planning role that discovers a missing outcome, interface, architecture, authority, risk-acceptance, or verification decision must return a structured decision request to the responsible Wayfinder. It must not manufacture the decision needed to finish its own plan.

## 5. Apply proportional pressure tests

Select only lenses that can change the decision or confidence: no-change/counterfactual, evidence quality, viewpoint conflict, interfaces, failure and recovery, authority, reversibility, temporal durability, adoption, observability, and unknown unknowns. These are pressure tests, not a mandatory questionnaire.

## 6. Stop economically

For each next action compare expected reduction in consequential uncertainty with compute, elapsed time, coordination, cleanup, and user-attention cost.

Continue when benefit clearly exceeds cost. For borderline cases, continue only when a consequential assurance gap remains and no cheaper sufficient action exists. Otherwise choose a defensible delegated default, accept explicitly bounded residual uncertainty, stop and synthesize, increase planning depth, or report a blocker.

## 7. Return a synthesis

Return the exact destination and posture used; accepted decisions and their authority; territory and interface map; active and completed frontier; blockers and fog; invalidated or reopened objects; capability/phase/work implications; assurance obligations; residual uncertainty; and the smallest valid next action. Distinguish `READY_TO_PLAN`, `READY_TO_EXECUTE`, `NEEDS_DECISION`, `NEEDS_INVESTIGATION`, and `BLOCKED`.

## Profile interaction

Use the installed profile registry when language-, runtime-, framework-, or toolchain-specific constraints can change the map, frontier, recommendation, decomposition, or evidence plan. Load the smallest applicable profile procedure and carry its identity, lock or digest, assumptions, required gates, and unavailable-capability disposition into delegated work.

## Durable question state

Persist a material multi-turn decision as `.bbk/questions/<question-id>.json` using `bbk.question-branch.v1`. Keep the root decision, recommendation, proposal response, root disposition, dependencies, invalidation, exposure history, unresolved point, stopping assessment, and next action current. Routine recommendations accepted immediately may proceed directly to the decision packet without creating a branch file.
