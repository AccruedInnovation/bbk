---
name: bbk-grill
description: Conduct a deep, collaborative, one-root-decision exploration after an ordinary Questioning Wayfinder recommendation is rejected, contested, materially ambiguous, or explicitly opened for deeper examination.
---

# BBK Grill

Grill is the escalation path, not ceremony for every decision. Begin only when a recommendation-first pass did not produce a decision-ready acceptance.

## Entry

Bind one root decision, the current recommendation, credible alternatives, governing facts and assumptions, accepted related decisions, authority, affected interfaces, branch history, user-attention state, and the exact return schema. Keep the root decision visible throughout.

Do not open a nested foreground Grill. Park independent questions for the Questioning Wayfinder; explore only related sub-decisions needed to resolve the root.

## Collaborative loop

Repeat:

1. **Frame:** restate the current decision frame and the highest-value unresolved point.
2. **Investigate:** retire discoverable factual uncertainty through bounded research rather than asking the user.
3. **Recommend and ask:** ask one material question at a time, accompanied by the current recommendation, credible alternatives, consequences, and residual uncertainty.
4. **Reflect:** interpret the answer and reflect the updated understanding before moving on.
5. **Challenge:** test the answer against evidence, constraints, prior decisions, interfaces, affected viewpoints, counterfactual/no-change, failure and recovery, reversibility, adoption, observability, and hidden assumptions—but only where the lens can change the decision.
6. **Update:** revise the decision frame and recommendation explicitly. Preserve contradictions instead of smoothing them away.
7. **Converge:** continue until shared understanding and decision readiness are sufficient, or until a valid non-resolution disposition is explicit.

Be persistent without being adversarial. Respect the user's authority without treating every first answer as fully informed. Avoid repetitive or low-value questions.

## Proposal response is not question disposition

A response to the current proposal is one of:

- `APPROVE`
- `REJECT`
- `REVISE`

`REJECT` and `REVISE` keep the root question active. They require interpretation, reframing, or an alternative recommendation.

The root question closes only as:

- `RESOLVED` with one explicitly accepted decision; or
- an explicit non-resolution disposition such as `DEFERRED`, `PARKED`, `BLOCKED`, `INSUFFICIENT_EVIDENCE`, `OUT_OF_SCOPE`, `CANCELLED`, or `SUPERSEDED`.

Silence, session closure, transport success, branch navigation, or exhaustion is not acceptance.

## Attention and continuation

When fatigue, time, or context pressure is material, offer a concise checkpoint: root decision, current recommendation, accepted related decisions, rejected proposals, unresolved point, evidence still needed, and the exact resumption handle. Pause or switch branches without pretending resolution.

## Return

Return an ADR-compatible packet containing the root decision; disposition; accepted decision if any; rationale; alternatives and consequences; facts, assumptions, and evidence; related accepted decisions; independent questions returned to the frontier; affected scope and interfaces; exposure history; residual uncertainty; invalidation/reopening triggers; and the smallest valid next action. Never execute the production consequence of the decision.

## Profile interaction

When the root decision is language-, runtime-, framework-, or toolchain-specific, consult the installed profile registry and load only the focused profile procedure needed to test the material claim. A profile adds procedure and evidence obligations; it does not replace user authority or make the proposal accepted.

## Durable branch

For a Grill that spans turns, research, parking, or host interruption, update the bound `bbk.question-branch.v1` record after each material response. Preserve rejected proposals and exposure history; do not rewrite the branch as though the accepted result had been obvious from the start.
