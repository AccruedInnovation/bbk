# Execution design

BBK separates outcome fit, implementation structure, state/effect semantics, execution slicing, and work-unit execution so consequential design choices are visible before effects occur. Routine work may keep these distinctions inline; material, stateful, effectful, interface-heavy, or hard-to-reverse work records them explicitly.

## Implementation structure and execution slicing

### 1. Purpose

A reviewed `SolutionOutcomeFit` establishes which intervention direction is being pursued and which outcomes it must change. Architecture answers which responsibilities, boundaries and interfaces should exist. An `ImplementationStructureContract` answers what shape the realization should take sufficiently to coordinate bounded work. It is not source code, a substitute for architecture, or a demand to freeze every helper.

The contract should make the consequential implementation decisions visible before candidate freeze:

- artifact or object topology;
- key types, schemas, signatures or structured forms;
- important behavior, call, control or handoff paths;
- state, information and effect ownership;
- failure, cancellation, recovery and degraded behavior;
- test seams, observability points and migration touchpoints;
- fixed decisions, delegated freedom and prohibited shortcuts.

### 2. Applicability

Use the least ceremony sufficient for the decision.

| Level | Use |
|---|---|
| `none` | Routine local change whose realization shape is already constrained and low risk |
| `inline` | A compact structure note embedded in the work unit |
| `contract` | A separate accepted contract for material cross-boundary, stateful, irreversible or multi-artifact work |

Common triggers include public interface changes, ownership changes, stateful orchestration, concurrency, recovery, migration, multi-module or multi-repository work, hard-to-reverse topology and consequential uncertainty about where behavior belongs.

### 3. Fixed decisions and delegated freedom

A useful contract distinguishes:

**Fixed decisions** — a worker may not change them without the applicable impact/change process.

Examples: state ownership, public signature, durability boundary, idempotency rule, source-of-truth location, safety interlock, migration sequence.

**Delegated freedom** — the worker may choose inside stated bounds.

Examples: private helper names, local iteration style, small refactors that preserve ownership and behavior, exact placement of a private test utility.

The contract should not contain pseudocode merely to simulate certainty.

### 4. Type-driven development

A profile should define its meaningful “type” vocabulary. The generic discipline is:

1. Name important identities, states and outcomes explicitly.
2. Represent permitted transitions and ownership.
3. Define boundary shapes before independent work begins.
4. Prefer representations that prevent invalid composition where practical.
5. Validate at runtime where static notation cannot establish facts.
6. Keep types deep: they should hide or constrain meaningful complexity, not add ceremonial wrappers.

### 5. Execution slices

An `ExecutionSlice` is the smallest coherent step that:

- advances an integrated behavior rather than only one technical layer;
- creates an inspectable touchpoint;
- has one accountable integration owner;
- can be reviewed and verified against explicit assertions;
- has containment or rollback behavior;
- identifies temporary scaffolding and its disposition.

A touchpoint may be a CLI operation, API exchange, rendered view, procedure walkthrough, protocol trace, simulation observation, physical measurement, generated package, document review or another domain-appropriate observation.

Do not use a universal line-count ceiling. Slice by change surface, coupling, risk and reviewer cognitive load.

### 6. Relationship among objects

```text
Accepted outcomes and SolutionOutcomeFit when applicable
  -> Capability Increment
      -> ImplementationStructureContract when applicable
          -> Execution Slices
          -> Work Units
                  -> Exact Candidate / Validation Cohort
```

A material structure contract must serve accepted outcomes and the selected fit direction. A passing structure review cannot clear an `INVESTIGATE` or `UNRESOLVED` fit disposition.

One slice may require several work units. A work unit may contribute to several slices. The slice owns integrated feedback; the work unit owns bounded execution responsibility.

### 7. Review checks

A structure review should ask:

- Is every consequential behavior located under one clear owner?
- Do key contracts make illegal or ambiguous interactions harder?
- Does the artifact topology reduce or merely relocate complexity?
- Are state lifetime, mutation authority and recovery explicit?
- Are failure and cancellation paths designed, not inferred?
- Do slices expose useful feedback early?
- Is temporary scaffolding named and dispositioned?
- Are fixed decisions no broader than needed?
- Is delegated freedom sufficient for competent implementation?
- Can the actual implementation be compared to the plan without treating harmless private differences as violations?

### 8. State–Decision–Effect concern

When implementation structure is stateful or effectful, use the nested `stateDecisionEffectDesign` concern described in `STATE-DECISION-EFFECT.md`. It identifies canonical state, independent dimensions, decision boundaries, effect contracts, invariants, trace fixtures, and the proportional formalization level.

The nested concern is part of the structure contract's fixed/delegated decision model. Workers may change private representation inside delegated freedom, but may not silently move state authority, perform undeclared effects, weaken retry/recovery semantics, or invalidate trace/model mappings.

### 9. Assurance integration

A structure review may become one logical lens in an alpha.7 `ReviewRun`. The original structure-review object remains valid; the review-assurance wrapper preserves its digest and does not reinterpret it as stronger evidence. See `REVIEW-ASSURANCE.md` and `FINDING-LIFECYCLE.md`.

## State, decision, effect, recovery, and rollback

BBK alpha.7 adds an applicability-aware `StateDecisionEffectDesign` concern beneath `ImplementationStructureContract`. It makes state ownership, legal transitions, deterministic decisions, external effects, receipts, ambiguity, and recovery explicit before workers improvise them independently.

The concern is domain-neutral. It applies to software, automation, data publication, procedures, hardware commissioning, and mixed human/system workflows. It does not mandate functional programming, one mega-enum, or a formal model.

### Placement

```text
SolutionOutcomeFit, when applicable
  → architecture and interfaces
    → ImplementationStructureContract
        → StateDecisionEffectDesign, when applicable
          → ExecutionSlice
            → WorkUnit
              → candidate, evidence, and review
```

It is nested because it describes the realization of an accepted intervention and architecture. It does not create a new top-level lifecycle, role, or authority surface.

### Applicability

| Level | Use |
|---|---|
| `NONE` | Stateless or mechanically constrained work, or a subject fully governed by an exact external canonical contract |
| `INLINE` | One small local workflow with one owner and compact transition/effect semantics |
| `CONTRACT` | Cross-boundary, concurrent, persistent, externally effectful, recovery-sensitive, authority-bearing, or repeatedly defect-prone work |

Triggers include retries, duplicate delivery, cancellation, timeouts, interruption, partial completion, ambiguous acknowledgement, leases/fences, several actors, irreversible effects, shared state, and recurring repair loops. A trigger may still resolve to `NONE` only with a rationale and exact governing contract.

### State algebra and ownership

The design distinguishes:

- canonical semantic state;
- derived facts;
- observations supplied from outside the decision boundary;
- independently mutable state dimensions;
- storage, UI, cache, log, and host projections.

Supported strategies are:

```text
STATELESS
SINGLE_SUM
PRODUCT_OF_SUMS
DECISION_TABLE
EXTERNAL_CANONICAL_CONTRACT
OTHER_WITH_RATIONALE
```

A sum represents exactly one alternative in a coherent lifecycle. A product combines genuinely independent dimensions. BBK rejects unexplained multiple canonical owners, authoritative facts also marked derived, unknown transition variants, and shadow state without a reconciliation contract.

### Decision boundary

```text
explicit state + explicit input + explicit observations
  → decision boundary
      → next state + domain facts + effect intents + rejection/no-change
```

A decision boundary declares its state and input types, owner, outputs, authority/freshness checks, expected failures, hidden-dependency policy, and handling of clock, randomness, configuration, environment, and external data.

Classifications:

- `PURE_DETERMINISTIC` — no I/O claims;
- `DETERMINISTIC_WITH_EXPLICIT_CONTEXT` — nondeterministic observations arrive as explicit values;
- `LEGACY_EFFECTFUL_WITH_CONTAINMENT` — effectful behavior is acknowledged, bounded, and dispositioned.

### Effect boundary

BBK preserves this distinction:

```text
effect intent created
  ≠ accepted by executor
  ≠ performed
  ≠ acknowledged
  ≠ semantic consequence committed
```

Material effects declare request and execution authority, target, preconditions, idempotency or explicit non-idempotence, duplicate behavior, retry, timeout, cancellation, ordering, partial completion, irreversible point, receipt, ambiguous acknowledgement, durable post-interruption fact, recovery owner, observability, compensation, and external-effect restrictions.

### Formalization ladder

```text
NONE
TRANSITION_TABLE
STATE_MACHINE_PROPERTIES
FORMAL_EXECUTABLE_MODEL
```

Formalization escalates when order, concurrency, replacement, lease/fence, duplicate delivery, ambiguous acknowledgement, persistent recovery, safety, or repeated defects make ordinary scenarios inadequate. The selected tool may be Quint, TLA+, Alloy, statecharts, a property-test engine, a PLC model, or another qualified mechanism. BBK records identity, assumptions, bounds, properties, traces, implementation mapping, and limitations; the model never becomes runtime authority by implication.

### Trace fixtures

`StateTransitionTrace` records initial state, inputs, expected decisions, states, facts, effect intents, rejections, invariants, permitted variation, fault plan, environment, and evidence. Useful trace classes include legal and illegal transitions, retries, duplicates, cancellation, timeout, partial completion, acknowledgement loss, crash-before-effect, crash-after-effect, stale results, replacement/fence, and recovery.

Commands:

```bash
bbk state-effect new --output .bbk/state-effects/SDE-001.json
bbk state-effect validate .bbk/state-effects/SDE-001.json
bbk state-effect render .bbk/state-effects/SDE-001.json --output .bbk/reviews/SDE-001.md

bbk trace new --output .bbk/traces/TRACE-001.json
bbk trace validate .bbk/traces/TRACE-001.json
bbk trace check-set --design .bbk/state-effects/SDE-001.json \
  --trace .bbk/traces/TRACE-001.json \
  --trace .bbk/traces/TRACE-002.json
```

### Planned-versus-actual review

The structure review distinguishes:

- **within delegated freedom** — private names, helper decomposition, equivalent private data structures, tests and instrumentation;
- **advisory drift** — a harmless cache or private variant that should be reflected later;
- **material divergence** — ownership moved, lifecycle became contradictory flags, shadow state became authoritative, a decision-only boundary performs I/O, an adapter gains domain authority, recovery semantics changed, an effect became non-idempotent, or required traces/models no longer map to the candidate;
- **blocked/unknown** — actual inventory cannot be established.

Use `bbk structure review` with an actual state/effect inventory. Candidate freeze can bind structure inventories, traces, and formal-model files so later changes invalidate dependent evidence.

### Authority boundary

A valid design, trace, or structure review is a BBK planning/evidence artifact. It does not grant effect permission, approve architecture, pass a project assertion, establish formal-tool soundness, or create official Blueprint authority.
