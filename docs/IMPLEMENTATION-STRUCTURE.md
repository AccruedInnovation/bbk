# Implementation structure

An `ImplementationStructureContract` records the planned realization shape for a bounded subject. It protects important responsibility, interface, ownership, and integration decisions without freezing harmless private detail.

## The missing middle

A feature list is too abstract for parallel implementation. A file list is too incidental. The structure contract captures the stable middle:

- responsibility and outcome;
- owned state, rules, schemas, and behavior;
- components or artifacts and allowed dependencies;
- public and cross-component contracts;
- control, data, signal, and handoff paths;
- effect boundaries;
- failure, retry, cancellation, partial-completion, migration, and recovery behavior;
- test seams and observability;
- fixed decisions, delegated freedom, and prohibited shortcuts;
- review and acceptance policy.

## Execution slices

An execution slice is a coherent integrated step that creates an inspectable touchpoint. Prefer vertical capability evidence over large horizontal foundations with no actor-visible or integration proof.

A slice binds:

- work units;
- dependencies;
- assertions and evidence;
- integration obligations;
- containment and rollback;
- temporary scaffolding and its disposition.

## Work units

A work unit assigns one bounded responsibility under exact scope, tools, effects, dependencies, expected behavior, and handoff. It is not simply a file assignment.

## Planned-versus-actual review

Review compares the accepted structure with the implementation. Material divergence includes changed ownership, public contracts, control/effect boundaries, failure semantics, compatibility, or integration obligations. Private helper names or harmless internal refactoring are not automatically material.
