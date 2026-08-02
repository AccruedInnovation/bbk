---
name: bbk-review-findings
description: Preserve, correlate, disposition, and close immutable BBK review findings using exact successor evidence rather than rediscovery or voting.
---


# BBK Review Findings

<!-- BBK prompt module bbk-prompt-finding-lifecycle: expanded from canonical source -->

### Immutable finding correlation and disposition lifecycle

Preserve exact findings, correlate without merging, and close only through authority-bearing successor dispositions with current evidence.

- `FINDING.CREATE` — Create an immutable finding bound to one run and attempt, exact subject or candidate digest, assertion, observation, expected condition, evidence, scope, impact, blocking state, and route.
- `FINDING.CORRELATE` — Use fingerprints only for correlation. A collision cannot merge records, and absence or non-rediscovery in a later run cannot close a finding.
- `FINDING.RELATION` — A reconciliation may propose SAME_DEFECT, PROBABLE_DUPLICATE, SHARED_ROOT_CAUSE, OVERLAPPING_IMPACT, CONTRADICTORY_ASSESSMENT, or UNRELATED; preserve every original finding and its evidence.
- `FINDING.DISPOSITION` — Close or otherwise change current projection only through a successor FindingDisposition: FIXED, REBUTTED, ACCEPTED_RISK, FALSE_POSITIVE, DUPLICATE_OF, SUPERSEDED, DEFERRED, OUT_OF_SCOPE, or REMAINS_OPEN.
- `FINDING.CLOSURE_EVIDENCE` — Every disposition names the exact finding, successor subject or changed context, closure evidence, reviewing attempt or accountable authority, residual impact, and reopening trigger.
- `FINDING.SEPARATION` — Workers do not close their own material findings, evaluators do not waive their own failures, and recommendations do not become authority-bearing dispositions.
- `FINDING.PROTECTED_FLOOR` — A contradictory, minority, or protected-floor finding remains visible and escalates according to policy; it is never hidden by a lower count, friendlier aggregate, or unrelated pass.
- `FINDING.HISTORY` — Preserve immutable finding and disposition history and derive current projection state from that lineage rather than rewriting or deleting predecessor records.
- `FINDING.PROFILE` — For profile-derived findings or dispositions, bind the exact profile identity and version, toolchain, applicable rule or gate, and evidence adapter. Do not generalize a profile-specific defect without separate evidence.

<!-- End BBK prompt module bbk-prompt-finding-lifecycle -->

## Profile binding

<!-- BBK prompt module bbk-prompt-profile-qualification: expanded from canonical source -->

### Language, domain, toolchain, and model qualification

Select only applicable installed profiles and focused procedures without allowing them to broaden authority.

- `PROFILE.EXPLICIT` — Use only a profile explicitly supplied or selected from the current installed-profile registry for the exact language, domain, framework, runtime, or toolchain responsibility.
- `PROFILE.FOCUSED` — Load the router and only the focused procedures and gates material to this role and assertion; do not fan out every profile or specialist pack.
- `PROFILE.BIND` — Carry profile identity, version or digest, toolchain assumptions, required gates, qualified operations, unavailable-capability policy, and evidence bindings into child and return contracts.
- `PROFILE.NO_AUTHORITY` — A profile, skill, tool, model route, or host capability adds method and evidence requirements only. It cannot broaden scope, effects, authority, or acceptance.
- `PROFILE.UNAVAILABLE` — When a required profile, toolchain, model, environment, or qualified operation is unavailable, return the exact technical or eligibility blocker instead of improvising qualification.

<!-- End BBK prompt module bbk-prompt-profile-qualification -->

<!-- BBK prompt module bbk-prompt-evidence-lineage: expanded from canonical source -->

### Evidence identity, reuse, and invalidation

Bind every observation and receipt to the exact assertion, subject, environment, method, and dependency closure it can establish.

- `EVIDENCE.ASSERTION_FIRST` — State the exact assertion and subject before collecting, reusing, or interpreting evidence.
- `EVIDENCE.FINGERPRINT` — Bind each receipt to candidate or planning subject, operation or method, command, inputs, configuration, environment, toolchain, profile, context and exposure policy, and produced artifacts.
- `EVIDENCE.REUSE` — Reuse a prior PASS only when the complete fingerprint and dependency closure remain unchanged and no invalidation condition has fired.
- `EVIDENCE.OBSERVATION_INFERENCE` — Separate direct observation, source report, inference, evaluation, recommendation, and authority-bearing decision.
- `EVIDENCE.APPEND_ONLY` — Preserve failed attempts, conflicting evidence, exposure history, and superseded state. Later annotations and dispositions link to immutable records rather than rewriting them.
- `EVIDENCE.INVALIDATE` — A material subject, source, assertion, criterion, method, environment, context, independence, or exposure change invalidates only the affected evidence and conclusions; create a successor and preserve unaffected valid reuse.

<!-- End BBK prompt module bbk-prompt-evidence-lineage -->

<!-- BBK prompt module bbk-prompt-assurance-integrity: expanded from canonical source -->

### Assurance independence, evaluation, findings, and disposition

Preserve fixed proof obligations and non-averaging assurance authority.

- `ASSURANCE.FREEZE` — Freeze assertion meaning, applicability, criteria, acceptable method, evidence obligation, protected floors, and exposure policy before outcome-bearing evidence is used for confirmation.
- `ASSURANCE.INDEPENDENCE_FACT` — Record independence as concrete facts about evaluator, context, prior findings, criteria authorship, evidence exposure, tools, environment, and organizational relationship; do not infer independence from a role label.
- `ASSURANCE.CHEAPEST_SUFFICIENT` — Use deterministic checks first and the cheapest sufficient qualified method for each material assertion. Add independent review only for a distinct assurance property.
- `ASSURANCE.ONE_EVALUATION` — Assign one primary evaluator per required assertion and derive one central non-averaging aggregate. A majority, average, or qualitative impression cannot override a required protected-floor failure.
- `ASSURANCE.FINDING` — Create immutable evidence-linked findings only after classifying implementation, assertion, context, method, infrastructure, environment, stale-subject, or other failure.
- `ASSURANCE.DISPOSITION` — Finding remediation, repair, disposition, waiver, risk acceptance, candidate acceptance, completion, and release remain external to the evaluator unless the exact role contract assigns them.

<!-- End BBK prompt module bbk-prompt-assurance-integrity -->
