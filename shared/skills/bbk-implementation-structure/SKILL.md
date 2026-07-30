---
name: bbk-implementation-structure
description: Create or review a domain-neutral ImplementationStructureContract.
---

Use this between architecture and execution when realization shape is material.

1. Bind the exact baseline, accepted SolutionOutcomeFit where applicable, selected direction, scope, architecture, interfaces and outcomes.
2. Describe artifact/object topology in domain vocabulary, not software-only vocabulary.
3. Name key contracts, signatures, schemas, forms or ports.
4. Trace important behavior, control and handoff paths including failure and recovery.
5. Assign state, information and effect ownership.
6. Identify test seams, observability and migration touchpoints.
7. Separate fixed decisions, delegated freedom and prohibited shortcuts.
8. Record uncertainty and review policy.
9. Avoid pseudocode and private-detail freezing unless consequence justifies it.
10. Produce profile-specific projections only as namespaced views over the generic contract.

11. When state/effect triggers are material, nest one `stateDecisionEffectDesign` concern using `NONE`, `INLINE`, or `CONTRACT`; do not create a parallel top-level design authority.
12. Preserve canonical state ownership, deterministic decision boundaries, controlled effects, ambiguity/recovery semantics, formalization, and trace references.

13. Before producing a profile-specific projection, consult `bbk-installed-profiles`, select and lock one compatible profile through `bbk-profile-routing`, and load its router skill. The namespaced projection never replaces the generic contract.

## Language-profile projection

When an installed profile applies, use its router from `bbk-installed-profiles` to project language-specific artifact, contract, ownership, and touchpoint concepts onto the generic structure contract. Keep the generic object authoritative and record the exact profile/digest used for the projection.
