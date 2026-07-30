# Review and assurance

BBK treats review as assertion-specific, context-bound, evidence-bearing work rather than a generic "looks good" judgment.

## Assurance contract

The `AssuranceContract` states what must be established:

- exact assertions;
- applicability;
- required methods and evidence;
- protected floors;
- independence expectations;
- blocking and advisory outcomes;
- authority for residual acceptance.

A review plan explains how one review will cover that contract. It does not replace the contract.

## Review context

A review result is meaningful only when its context is explicit. Record:

- exact subject and candidate identity;
- source inventory and content roots;
- omitted, stale, redacted, unavailable, or sharded context;
- instructions, profiles, tools, and environment;
- prior findings visible to the reviewer;
- independence dimensions.

Missing required context blocks the affected assertion rather than producing fabricated confidence.

## Evidence receipts

Evidence should record the actual operation, subject, environment, inputs, outputs, trust classification, completeness, and content identity. Freeform logs are not silently promoted to strong required-gate evidence.

Evidence reuse requires a complete matching fingerprint. Material subject, environment, method, dependency, or context change invalidates affected reuse.

## Findings and dispositions

Findings are durable records. A finding does not close because:

- a later reviewer failed to mention it;
- a majority disagreed;
- the original worker declared it fixed;
- another test passed without addressing the closure criteria.

Closure requires an explicit disposition and evidence against the finding's criteria. Preserve original finding history.

## Blind and targeted re-review

- **Targeted closure** includes the finding and exact closure criteria.
- **Blind reassessment** excludes prior finding text and worker self-assessment where independence from anchoring matters.

Do not label a review blind merely because it used another model or session.

## Independence

Record independence dimensions separately:

- author/worker separation;
- context separation;
- model/provider diversity;
- tool or method diversity;
- organizational separation;
- human authority.

No single dimension implies all others.

## Intent conformance

Review should trace from outcome and accepted decisions through architecture, structure, slices, work units, candidate, and evidence. A technically clean implementation can still fail if it implements the wrong intervention or violates an accepted interface or constraint.

## Aggregate result

Do not average protected failures away. Keep distinct states for:

- subject failure;
- reviewer/context/environment insufficiency;
- infrastructure failure;
- blocked authority;
- not applicable;
- advisory residuals.
