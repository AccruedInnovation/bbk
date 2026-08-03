---
name: bbk-implementation-structure
description: Create or review a proportional domain-neutral ImplementationStructureContract, including compact infrastructure, network, deployment, software, automation, hardware, data, procedure, and mixed-system structures.
---

# BBK Implementation Structure

Use this between architecture and execution when realization shape is material. The generic contract is authoritative; language or toolchain profiles create only namespaced projections.

<!-- BBK prompt module bbk-prompt-planning-source-integrity: expanded from canonical source -->

### Planning-source integrity and partial invalidation

Preserve accepted decisions and exact source lineage while planning, decomposing, or proposing designs.

- `PLANNING.SOURCE_BINDING` — Bind each planning claim, decision, requirement, architecture element, interface, work item, assertion, authority source, and profile assumption to the exact accepted subject and revision.
- `PLANNING.NO_UPSTREAM_REPAIR` — Do not silently repair, reinterpret, approve, or overwrite a missing, contradictory, stale, wrong-subject, or insufficiently accepted upstream source inside a downstream plan or design.
- `PLANNING.SPECIALIST_AUTHORITY` — Commission exact specialist work through its owning role, validate and integrate the return, and preserve the distinction between semantic commissioning and specialist design ownership.
- `PLANNING.SUCCESSOR` — When a governing source changes, preserve the predecessor, identify the deterministic impact set, invalidate only affected graph, assertion, worker-contract, evidence, and handoff dependencies, and request the smallest sufficient successor work.
- `PLANNING.NO_EXECUTION_AUTHORITY` — Planning may describe required authority, effects, environments, checks, and recovery, but it does not authorize execution, accept risk, validate a candidate, or release a result.

<!-- End BBK prompt module bbk-prompt-planning-source-integrity -->

<!-- BBK prompt module bbk-prompt-evidence-subject-identity: expanded from canonical source -->

### Evidence subject and environment identity

Bind observations and quantitative claims to the exact node, environment, source, time, and method so evidence is not transferred between superficially similar systems.

- `EVIDENCE.NODE_BINDING` — Every material environment observation must identify the exact node or subject, node_id when available, hostname or stable system identity, environment and location, observation source, observation time or as-of boundary, method and command or API, scope, authority, and confidence or limitation.
- `EVIDENCE.NO_TRANSFERENCE` — Do not transfer an observation from one machine, account, network, repository, version, jurisdiction, or environment to another merely because they share an operating system or role. Unknown target-node state remains unknown until established or explicitly assumed.
- `EVIDENCE.ESTIMATE_TRUTH` — Bind every quantitative estimate to its source, assumptions, units, environment, uncertainty, and intended use. Label an estimate as measured, documented, calculated, inferred, or illustrative; do not present an unmeasured planning estimate as observed performance.

<!-- End BBK prompt module bbk-prompt-evidence-subject-identity -->

<!-- BBK prompt module bbk-prompt-specialist-disposition: expanded from canonical source -->

### Specialist-return disposition and conditional-currentness

Explicitly disposition specialist review requests, unresolved decisions, blockers, and successor requirements before treating integrated planning or execution state as current.

- `SPECIALIST.DISPOSITION` — For every material specialist-requested review, unresolved blocker, open decision, conditional branch, successor requirement, or recommended follow-up, record one explicit disposition: COMMISSIONED with reference, INTEGRATED, DEFERRED with owner and trigger, SUPERSEDED with successor, REJECTED with rationale, or REMAINS_OPEN with impact.
- `SPECIALIST.CONDITIONAL_CURRENTNESS` — Do not describe an artifact or baseline as current, complete, or decision-closed while its producing specialist says it is conditional on an unresolved material decision or successor work. Preserve the conditional state and affected scope.
- `SPECIALIST.RECONFIRM_BRANCH` — When a material decision resolves a branch that was open during specialist work, obtain a bounded confirmation, amendment, or successor from the owning specialist before treating the selected branch as current, unless the original return explicitly delegated that exact integration choice to the parent.
- `SPECIALIST.REVIEW_NOT_SILENTLY_DROPPED` — A specialist request for independent review may be accepted, proportionately deferred, or rejected with rationale, but it must not disappear from the parent result. State the review owner, exact focus, timing trigger, and residual risk.

<!-- End BBK prompt module bbk-prompt-specialist-disposition -->

## Choose the smallest applicable contract

Use `bbk.implementation-structure-contract.v3` for new work. Select:

```text
subject.kind:
  software | automation | hardware | procedure | data | document |
  infrastructure | network_configuration | deployment_configuration |
  mixed | other

contractDepth:
  compact | standard | full
```

Prefer `compact` for bounded infrastructure, network, deployment, configuration, and similarly narrow work when topology, interfaces, effects, recovery, security, and pre-execution confirmations can be represented without software-oriented internal machinery. Use `standard` for ordinary multi-artifact realization and `full` only when consequence, interface exposure, migration, recovery, or state complexity warrants it.

Create a starting point with:

```text
bbk schema list
bbk schema template --kind implementation-structure --subject-kind infrastructure --depth compact --output <path>
bbk schema enum --schema implementation-structure --pointer /contractDepth
bbk schema explain --schema implementation-structure --instance <path>
```

Do not discover required fields and enums by repeatedly rewriting an unrelated example.

## Describe realization proportionately

1. Bind the exact baseline, accepted SolutionOutcomeFit where applicable, selected direction, scope, architecture, interfaces, outcomes, and subject identity.
2. Describe artifact, object, node, service, configuration, or procedure topology in domain vocabulary rather than forcing every system into software classes.
3. Name key contracts, signatures, schemas, forms, protocols, ports, routes, files, services, or operational boundaries.
4. Trace important behavior, control, data, handoff, failure, degraded, recovery, rollback, and migration paths.
5. Assign state, information, decision, effect, credential, configuration, and mutable-resource ownership.
6. Identify test seams, observability, deployment order, migration touchpoints, and rollback anchors.
7. Separate fixed decisions, delegated freedom, prohibited shortcuts, unresolved uncertainty, and review obligations.
8. Record pre-execution confirmations for exact host, edition, version, network-policy, credential, licence, storage, runtime, command, API, and authorization facts that must be established before effects.
9. Explicitly disposition specialist-requested review, open decisions, conditional branches, blockers, and successor requirements.
10. Avoid pseudocode and private-detail freezing unless consequence or a public contract justifies it.

## Apply sections rather than padding them

For each material section record `REQUIRED`, `APPLICABLE`, `NOT_APPLICABLE`, or `DEFERRED` with rationale and an exact trigger where relevant. In particular, do not require State–Decision–Effect machinery merely because the schema can represent it. Use `NONE`, `INLINE`, or `CONTRACT` only when independently evolving semantic state, ambiguous acknowledgement, retries, concurrent mutation, controlled effects, or recovery semantics are material.

A section marked `NOT_APPLICABLE` is an explicit design conclusion, not an omission. A section marked `DEFERRED` requires an owner and trigger before execution reaches the affected scope.

## Language-profile projection

Before producing a profile-specific projection, consult `bbk-installed-profiles`, select and lock one compatible profile through `bbk-profile-routing`, and load its router skill. The namespaced projection never replaces the generic contract or grants authority.

## Return truth

A schema-valid structure is a producer artifact, not architecture acceptance, execution authorization, assurance success, or proof that referenced commands and platform behavior are correct. Preserve exact validation evidence, unresolved confirmations, review disposition, and the parent-owned next action.
