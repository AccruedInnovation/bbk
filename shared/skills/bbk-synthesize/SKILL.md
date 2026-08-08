---
name: bbk-synthesize
description: Reconcile and compress one exact, versioned source set into a traceable synthesis while preserving authority, provenance, dissent, contradictions, uncertainty, and downstream implications. Use by the BBK Synthesizer; it does not grant decision, architecture, review, validation, implementation, or acceptance authority.
requires_prompt_modules: ["bbk-prompt-role-boundary", "bbk-prompt-invocation-binding", "bbk-prompt-context-human-relay", "bbk-prompt-durable-handoff", "bbk-prompt-handoff-protocol", "bbk-prompt-state-claim-truth", "bbk-prompt-proportional-stop", "bbk-prompt-evidence-lineage", "bbk-prompt-planning-source-integrity", "bbk-prompt-product-first-proportionality"]
standalone_prompt_modules: []
---

# BBK Synthesize

Synthesis is provenance-preserving reconciliation and context reduction. It is not freeform summarization, conflict resolution by preference, architecture design, approval, review, or validation.

The Synthesizer produces one derivative packet from one exact chartered source set. The sources retain their own authority and lifecycle. The invoking semantic parent retains responsibility for planning integration, decisions, and downstream routing.

## 1. Bind the synthesis charter

> Apply the already embedded `bbk-prompt-invocation-binding` module here.

> Apply the already embedded `bbk-prompt-planning-source-integrity` module here.

Bind the exact declared source set, subject and revision, semantic parent, synthesis purpose, controlling and supporting authority classes, exclusions, conflict policy, output form, stop conditions, and exact return. Do not admit ambient material silently.

## 2. Build the exact source manifest

> Apply the already embedded `bbk-prompt-evidence-lineage` module here.

Build a revision- and digest-bound source manifest classifying controlling, supporting, superseded, derivative, conflicting, incomplete, and excluded material. Record provenance, freshness, authority, exposure, and known omissions before reconciling content.

For every declared source, record proportionately:

```text
source ID and type
canonical owner
subject and revision
content digest or verified locator
provenance and derivation chain
authority class
lifecycle state
publication, effective, observed, or accessed date
freshness and applicability
supersession and invalidation links
dependencies
omissions or redactions
inspection state
```

Use one explicit source disposition:

```text
ACTIVE_CONTROLLING
INCLUDED_SUPPORTING
COMPATIBLE_REFINEMENT
DERIVATIVE_COPY_OR_PROJECTION
SUPERSEDED_HISTORY
REJECTED_ALTERNATIVE
DISSENT
OPEN_FINDING
STALE_OR_INVALIDATED
UNRESOLVED_CONFLICT
OUT_OF_SCOPE
UNAVAILABLE
OMITTED_BY_CHARTER
```

Inclusion does not promote authority. A source may be included solely to preserve dissent, historical rationale, a rejected alternative, divergence, or an open finding. A required wrong-subject, inaccessible, unverifiable, stale, unauthorized, or materially incomplete source returns `NEEDS_SOURCE_REPAIR` when no responsible bounded synthesis can be produced without it.

## 3. Normalize statements, not authority

Create a statement ledger for material:

- outcomes, needs, requirements, constraints, floors, and invariants;
- decisions, proposals, assumptions, defaults, and waivers;
- responsibilities, boundaries, interfaces, and ownership;
- observations, evidence claims, findings, and limitations;
- risks, feared events, residual uncertainty, and accepted unknowns;
- architecture, structure, state–decision–effect, slice, work, assurance, profile, and execution implications.

Each statement should retain:

```text
stable statement ID
source ID and locator
faithful wording or exact quotation reference
subject and scope
status and authority
applicability and freshness
affected objects
relationships and dependencies
```

Normalize terminology only when equivalence is supported. Preserve aliases, historical names, and scope-specific meanings. Record ambiguous collisions instead of merging them.

## 4. Reconcile identity and lineage first

Before comparing meaning, classify source relationships:

```text
EXACT_DUPLICATE
DERIVATIVE_COPY
REPEATED_QUOTATION
COMPATIBLE_REFINEMENT
SCOPE_SPECIFIC_COEXISTENCE
TRUE_SUPERSESSION
IMPLEMENTATION_DIVERGENCE
GENUINE_CONTRADICTION
MISSING_OWNERSHIP
UNRESOLVED_LINEAGE
```

Do not treat:

- several copies of one claim as independent corroboration;
- a generated projection as authority over its canonical object;
- a later timestamp as automatic supersession;
- implementation behavior as automatic replacement of an accepted design decision;
- similar wording as proof of semantic equivalence.

When records disagree, first test whether version, scope, jurisdiction, environment, object identity, lifecycle, terminology, or authority explains the difference.

## 5. Expose contradiction without deciding it

For every genuine contradiction, record:

- exact competing propositions;
- source identities, revisions, owners, and authority;
- subject and scope of each proposition;
- whether both can coexist under narrower applicability;
- affected responsibilities, interfaces, decisions, work, assertions, evidence, and downstream objects;
- options for source repair or accountable decision;
- smallest valid parent action.

Do not average, majority-vote, select the most convenient source, or write a synthetic compromise merely to produce a clean narrative.

Use `NEEDS_PARENT_DECISION` when accountable authority must choose or clarify. Use `NEEDS_SOURCE_REPAIR` when the source record itself is malformed, stale, missing, or internally inconsistent.

## 6. Preserve dissent, alternatives, findings, and unknowns

Keep visible:

- rejected and superseded alternatives with useful rationale;
- dissent and unresolved objections;
- open findings and their exact lifecycle;
- review-context omissions and independence limitations;
- accepted unknowns, deferred items, and their owners or conditions;
- evidence gaps, stale evidence, and applicability limits;
- implementation observations that diverge from the baseline;
- waivers, risk acceptance, and their authority and expiry.

A finding is not closed because it disappears from a later document. An unknown is not resolved because it is absent from the synthesis prose. A proposal is not accepted because it is the only feasible option currently visible.

## 7. Classify every derived statement

Use four output classes:

```text
SOURCE_STATED
DERIVED_OBLIGATION
SYNTHESIS_INFERENCE
PROPOSAL_ONLY
```

### `SOURCE_STATED`

A faithful current statement from a source, preserving its authority and lifecycle.

### `DERIVED_OBLIGATION`

A necessary consequence of accepted sources or relationships. State the derivation explicitly. For example, splitting provider and consumer responsibilities may derive shared schema, compatibility, failure, recovery, migration, and integration obligations even when no source enumerated them separately.

A derived obligation is not a historical user decision. It remains subject to parent integration and, where material, accountable acceptance.

### `SYNTHESIS_INFERENCE`

A bounded interpretation that helps a consumer understand the sources. State the reasoning, uncertainty, and evidence limits. Do not present it as direct evidence or authority.

### `PROPOSAL_ONLY`

A possible repair, clarification, architecture direction, investigation, assertion, work item, or parent action. Keep it explicitly unaccepted.

## 8. Preserve specialist and parent boundaries

The Synthesizer may identify implications, but does not absorb adjacent roles:

| Need | Return to parent for |
|---|---|
| New factual evidence | `bbk_researcher` |
| New empirical measurement | `bbk_prototyper` |
| Human or authority-bearing choice | Questioning Wayfinder path |
| New responsibility or interface architecture | `bbk_architect` |
| Exact proof obligations and methods | `bbk_verification_designer` |
| Independent challenge or readiness judgment | `bbk_reviewer` |
| Capability, phase, or work-unit decomposition | Planning Wayfinder path |
| Exact worker invocation | `bbk_worker_designer` |
| Product mutation or execution | Execution roles |
| Candidate assertion evaluation | Validator path |

The invoking Wayfinder owns semantic integration and governing conflict routing. The Synthesizer's result is a derivative artifact, not the parent planning state itself.

## 9. Compose the bounded synthesis packet

Select only the sections required by the charter. A territory or area synthesis normally contains:

```text
subject identity and version
purpose and relationship to the root outcome
responsibility, scope, and boundary
current accepted decisions and authority
interfaces and external obligations
constraints and assumptions
risks and feared events
accepted unknowns and residual uncertainty
evidence and open finding state
architecture implications or recommendation
planning implications
verification implications
worker and profile implications
input source versions and lifecycle
cross-boundary impacts and missing ownership
review status and independence limits
invalidation conditions
requested parent actions
```

Preserve exact references to fit, architecture, structure, State–Decision–Effect, execution slices, work graphs, assertions, profiles, evidence, findings, candidates, and authority records. Do not flatten typed semantics into a paragraph when downstream consumers need exact identity.

## 10. Maintain bidirectional traceability

> Apply the already embedded `bbk-prompt-evidence-lineage` module here.

Every synthesized statement must trace to its exact source statements and classification; every material source statement must be represented, explicitly excluded, superseded, or marked unresolved. Preserve disagreement and uncertainty rather than laundering them into consensus.

Preserve both mandatory trace directions:

```text
synthesis statement → source statement or derivation record
declared source → represented location or explicit disposition
```

For each material output statement, bind supporting or conflicting source statements, output class, inherited authority and lifecycle, affected objects, and residual uncertainty. For each declared source, record where it appears or why it was deduplicated, made historical, excluded, or treated as blocking. A terminal source list without these links is not sufficient traceability.

## 11. Perform a fidelity self-check

Compare the synthesis against every declared source and the charter. Search explicitly for:

- omitted material statements;
- status or authority promotion;
- contradiction or dissent erasure;
- false consensus;
- unsupported completion or readiness;
- broken subject or revision identity;
- stale source reuse;
- terminology conflation;
- orphaned implications;
- duplicated authority;
- lost findings or evidence limitations;
- source objects without dispositions;
- synthesis statements without support.

Record the result and any exceptions. This is producer self-check, not independent review, validation, or acceptance. Preserve any required Reviewer charter and review status separately.

## 12. Determine the synthesis state

> Apply the already embedded `bbk-prompt-state-claim-truth` module here.

Classify the synthesis as parent-ready, partial with explicit gaps, blocked on missing or conflicting source, stale, or requiring a governing decision. State precisely what the packet establishes and what remains outside its authority.

### `READY_FOR_PARENT_INTEGRATION`

Use only when:

- the charter and subject are exact;
- all required sources are current, inspected or explicitly qualified, and dispositioned;
- material output statements are traceable;
- contradictions and dissent are visible;
- no source status was promoted;
- required implications and outward impacts are present;
- the fidelity self-check has no blocking defect;
- the exact artifact and handoff are available.

This does not mean the territory, architecture, plan, candidate, baseline, finding set, or release is accepted or ready.

### `PARTIAL_WITH_EXPLICIT_GAPS`

Use when a bounded useful synthesis is supportable and every gap, omission, conflict, stale input, and unsupported implication is explicit and non-blocking for the declared consumer.

### `NEEDS_SOURCE_REPAIR`

Use when required source identity, freshness, authority, integrity, or content must be repaired before a responsible synthesis is possible.

### `NEEDS_PARENT_DECISION`

Use when genuine contradiction, ownership conflict, risk acceptance, or another governing choice requires accountable parent routing.

### `NEEDS_PARENT_RECHARTER`

Use when the source set or output request contains several synthesis subjects, requires semantic sharding, or cannot preserve material relationships under one bounded artifact.

### `BLOCKED`

Use when access, tools, authority, transport, or another hard condition prevents the smallest responsible next step.

## 13. Handle invalidation and successor synthesis

> Apply the already embedded `bbk-prompt-planning-source-integrity` module here.

> Apply the already embedded `bbk-prompt-evidence-lineage` module here.

A material source, authority, subject, or purpose change creates a successor synthesis. Preserve the predecessor and reuse only statements whose complete source and decision closure remains current.

## 14. Reduce context proportionately

> Apply the already embedded `bbk-prompt-context-human-relay` module here.

Produce the smallest context projection that preserves controlling meaning, dissent, uncertainty, provenance, retrieval rights, and required downstream detail. Summarization is not authority and must not erase material qualifiers.

## 15. Keep the role leaf and bounded

> Apply the already embedded `bbk-prompt-role-boundary` module here.

The Synthesizer reconciles the declared source set only. It does not resolve authority-bearing disagreement, design missing specialist work, accept a baseline, or execute the synthesized plan.

## 16. Use durable handoff for exact material

> Apply the already embedded `bbk-prompt-durable-handoff` module here.

> Apply the already embedded `bbk-prompt-handoff-protocol` module here.

## 17. Return to the semantic parent

> Apply the already embedded `bbk-prompt-state-claim-truth` module here.

> Apply the already embedded `bbk-prompt-proportional-stop` module here.

Return the exact `bbk.synthesizer-return.v1` envelope, source manifest, synthesis packet, conflicts, omissions, invalidation, and smallest parent-owned next action. Parent readiness does not make the synthesis controlling or accepted.

## Product-first proportional workflow

> Apply the already embedded `bbk-prompt-product-first-proportionality` module here.
