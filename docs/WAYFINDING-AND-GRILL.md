# Wayfinding and Grill

BBK separates ordinary decision preparation from deep interactive exploration.


## Root and specialist ownership

Planning starts at `bbk_root_wayfinder`; execution, direct bounded review, and candidate assurance start at separate controller-selected roots. Planning Wayfinder owns work-graph topology, cross-phase dependencies, global coverage, and readiness. Phase Wayfinder owns phase-local decomposition, sequencing, mutation ownership, specialist commissioning, and integration. Verification Designer owns exact assertion and evidence-method design; Worker Designer owns exact executable Worker invocation-contract design. A Wayfinder commissions, validates, and integrates those specialist returns but does not silently author or approve the specialist contract it requested.

## Recommendation-first path

```text
Root or Territory Wayfinder
  → Questioning Wayfinder
      → investigate discoverable facts
      → prepare one decision-ready recommendation
      → state alternatives, consequences, affected scope, and uncertainty
  → harness-root controller presents the recommendation
      ├─ accepted
      │    → record and return the ADR-compatible decision packet
      │    → no Question Guide
      ├─ bounded correction or clarification
      │    → revise the recommendation
      │    → no Question Guide unless a material unresolved issue appears
      └─ rejected, contested, materially ambiguous, or deeper exploration requested
           → one focused Question Guide
           → deep Grill
           → return to the Questioning Wayfinder for validation and reconciliation
```

The Questioning Wayfinder is a logical responsibility. It may share a physical invocation with another role where no authority, context, or independence boundary is lost. It must not create a Question Guide merely because a decision exists.

## Recursive Wayfinding

`bbk-wayfind` governs Root, Territory, Questioning, Planning, and Phase Wayfinders. They continuously maintain four distinct sets:

- **Map:** the current destination, accepted decisions, territories, interfaces, dependencies, and evidence posture.
- **Frontier:** sufficiently sharp questions or bounded investigations that can be acted on now.
- **Blockers:** conditions preventing otherwise actionable frontier work.
- **Fog:** relevant uncertainty that is not yet sharp enough to become a decision or task.

Wayfinding is iterative:

1. Bind destination, scope, posture, accepted decisions, interfaces, frontier, blockers, and fog.
2. Map at the lowest resolution sufficient to expose consequential uncertainty.
3. Subdivide only at a real responsibility, containment, specialization, interface, or safe-parallelism boundary.
4. Sharpen uncertainty into decisions, research, prototypes, reviews, or planning work.
5. Dispatch bounded work with exact context and return contracts.
6. Receive results and update decisions, dependencies, interfaces, impacts, invalidation, frontier, blockers, and fog.
7. Reassess subdivision, pressure-test lenses, and stopping economics.
8. Synthesize only when no material blocking work remains and the source state is current.

Stopping compares expected reduction in consequential uncertainty with compute, time, delay, coordination, cleanup, and user-attention cost. It does not mean “stop when the prompt is long.”

## Deep Grill

`bbk-grill` is loaded by the Question Guide only. It is the exception path for a recommendation that was rejected or contested, contains conflicting assumptions, remains materially ambiguous, or was explicitly opened for deeper exploration.

The Guide keeps one root decision visible and repeats:

```text
frame
  → investigate facts
  → recommend and ask one material question
  → reflect the answer
  → challenge assumptions, contradictions, interfaces, evidence, and consequences
  → update the decision frame
  → converge or record an explicit non-resolution disposition
```

A response to the current proposal is not the same as disposition of the root question:

```text
APPROVE  → may resolve the root question
REJECT   → keeps the root question active
REVISE   → keeps the root question active
```

The root question ends only with an explicitly accepted decision or an explicit disposition such as deferred, parked, blocked, insufficient evidence, out of scope, cancelled, or superseded. Silence, session closure, transport success, and host-window exhaustion are never consent.

## Route-back rule

Planning and Phase Wayfinders may elaborate accepted decisions. They must return missing outcome, interface, architecture, authority, risk-acceptance, or verification decisions to the responsible Territory or Root Wayfinder rather than inventing those decisions to make a plan complete.

## Durable branch state

Persist only material decisions that span turns, research, parking, or Grill escalation:

```bash
bbk question new --root . --id Q-ARCH --root-decision "Choose the architecture"
bbk question validate .bbk/questions/Q-ARCH.json
bbk question list --root .
```

The `bbk.question-branch.v1` record separates proposal response from root-question disposition and preserves authority, recommendation, dependencies, invalidation, exposure history, unresolved point, stopping assessment, and next action.
