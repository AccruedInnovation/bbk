# State–Decision–Effect design

Stateful systems fail when authoritative state, derived state, observations, decisions, requested effects, executed effects, and receipts are blurred together.

## Core model

- **State**: retained information that changes what behavior is legal or what result follows.
- **Observation**: information obtained from outside the decision boundary.
- **Decision**: deterministic or governed selection of the next intended behavior.
- **Requested effect**: an authorized request to change the world.
- **Executed effect**: what the effect boundary actually attempted or completed.
- **Receipt**: evidence describing the effect result and correlation identity.
- **Derived state**: a projection that must not become an independent authority without an explicit reason.

## Design obligations

Where applicable, define:

- one canonical owner for each coherent state;
- legal states and transitions;
- sum/variant state versus independent product dimensions;
- observations and validation;
- decision rules and invariants;
- effect authorization and execution boundary;
- duplicate, ordering, timeout, cancellation, retry, acknowledgement, and replay semantics;
- partial completion and reconciliation;
- restart and recovery;
- trace and evidence strategy.

## Applicability

Use the lightest treatment:

- `NONE` for genuinely stateless or trivial work;
- `INLINE` for simple local state/effect behavior;
- `CONTRACT` for material workflows, ownership ambiguity, external effects, recovery, or consequential failure.

A passing trace suite supports specific assertions; it does not by itself prove the implementation or operational outcome.
