    ---
    name: bbk-state-decision-effect-design
    description: Design or review canonical state, deterministic decisions, controlled effects, recovery semantics, and proportionate transition evidence inside an ImplementationStructureContract.
    ---

    # BBK State–Decision–Effect Design

Use this concern only where state or effects are material. Keep it nested under the governing `ImplementationStructureContract`.

1. Select `NONE`, `INLINE`, or `CONTRACT` from explicit triggers. Do not create state-machine ceremony for a stateless or purely mechanical change.
2. Name one canonical semantic owner for each coherent workflow. Distinguish authoritative state, derived facts, observations, projections, caches, and receipts.
3. Use one sum for mutually exclusive lifecycle alternatives and a product of smaller sums for genuinely independent dimensions. Avoid both contradictory flags and one combinatorial mega-enum.
4. Define each decision boundary from explicit state and explicit command/event/observation inputs to next state, domain facts, effect intents, rejection, or no change.
5. Pass time, randomness, configuration, identity generation, environment data, and external facts as explicit context when deterministic reasoning depends on them.
6. Separate effect intent, executor acceptance, execution, acknowledgement, and semantic consequence. Tool availability never grants effect authority.
7. State idempotency, duplicate, retry, timeout, cancellation, ordering, partial completion, irreversible point, ambiguous acknowledgement, durable interruption fact, recovery owner, and compensation/successor policy where applicable.
8. Link representation, transition, authority, effect, recovery, temporal, safety, and lifecycle invariants to exact assertions or evidence methods.
9. Select the lowest sufficient formalization rung: `NONE`, `TRANSITION_TABLE`, `STATE_MACHINE_PROPERTIES`, or `FORMAL_EXECUTABLE_MODEL`. A model remains a design/evidence artifact, not runtime authority.
10. Create transition traces for the material legal, illegal, retry, duplicate, cancellation, timeout, partial, ambiguous, crash, stale, replacement, degraded, and recovery paths required by the assurance contract.
11. Preserve fixed state/effect decisions and delegated private implementation freedom. Route material divergence through structure review rather than letting a worker improvise it.
12. Return applicability, canonical owner, state algebra, decisions, effects, invariants, formalization, traces, uncertainties, and review obligations.


When a compatible language/domain profile is selected, use `bbk-profile-routing` to invoke only its typed State–Decision–Effect projection, inventory, or review capability. Keep the generic design authoritative and treat a missing required capability as `BLOCKED`.

## Language-profile projection

When a managed profile applies, use `bbk-installed-profiles` and `bbk-profile-routing` to select its state/effect representation, inventory, review, and evidence procedures. Bind the projection to the generic design and exact profile digest; unsupported or unavailable mandatory capability is `BLOCKED`.
