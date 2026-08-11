---
name: bbk-implementation-structure
description: Create or review a proportional domain-neutral ImplementationStructureContract, including compact infrastructure, network, deployment, software, automation, hardware, data, procedure, and mixed-system structures.
requires_prompt_modules: ["bbk-prompt-evidence-subject-identity"]
standalone_prompt_modules: ["bbk-prompt-planning-source-integrity", "bbk-prompt-specialist-disposition"]
---

# BBK Implementation Structure

Use this between architecture and execution when realization shape is material. The generic contract is authoritative; language or toolchain profiles create only namespaced projections.

<!-- BBK prompt module bbk-prompt-planning-source-integrity: expanded from canonical source -->

### Planning-source integrity and partial invalidation

Preserve accepted decisions and exact source lineage while planning, decomposing, or proposing designs.

- `PLANNING.SOURCE_BINDING` — Bind every planning claim, decision, requirement, architecture element, interface, work item, assertion, authority source, and profile assumption to the exact accepted subject/revision.
- `PLANNING.NO_UPSTREAM_REPAIR` — Do not silently repair, reinterpret, approve, or overwrite a missing, conflicting, stale, wrong-subject, or insufficiently accepted upstream source in downstream planning/design.
- `PLANNING.SPECIALIST_AUTHORITY` — Commission exact specialist work through its owning role, validate/integrate the return, and keep semantic commissioning separate from specialist design ownership.
- `PLANNING.SUCCESSOR` — When a governing source changes, preserve the predecessor, derive the deterministic impact set, invalidate only affected graph/assertion/worker-contract/evidence/handoff dependencies, and request the smallest sufficient successor work.
- `PLANNING.NO_EXECUTION_AUTHORITY` — Planning may specify authority, effects, environments, checks, and recovery; it cannot authorize execution, accept risk, validate a candidate, or release a result.

<!-- End BBK prompt module bbk-prompt-planning-source-integrity -->

> Apply the already embedded `bbk-prompt-evidence-subject-identity` module here.

<!-- BBK prompt module bbk-prompt-specialist-disposition: expanded from canonical source -->

### Specialist-return disposition and conditional-currentness

Explicitly disposition specialist review requests, unresolved decisions, blockers, and successor requirements before treating integrated planning or execution state as current.

- `SPECIALIST.DISPOSITION` — Give every material specialist review request, blocker, open decision, conditional branch, successor need, or follow-up one explicit disposition: COMMISSIONED with ref, INTEGRATED, DEFERRED with owner/trigger, SUPERSEDED with successor, REJECTED with rationale, or REMAINS_OPEN with impact.
- `SPECIALIST.CONDITIONAL_CURRENTNESS` — Do not call an artifact/baseline current, complete, or decision-closed while its producing specialist makes it conditional on an unresolved material decision or successor work. Preserve the condition and affected scope.
- `SPECIALIST.RECONFIRM_BRANCH` — When a later material decision resolves an open specialist branch, obtain bounded confirmation, amendment, or successor from the owning specialist before treating it current, unless the original return explicitly delegated that exact integration choice.
- `SPECIALIST.REVIEW_NOT_SILENTLY_DROPPED` — A requested independent review may be accepted, proportionately deferred, or rejected with rationale, but not omitted. State review owner, exact focus, timing trigger, and residual risk.

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
