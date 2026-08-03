# Durable question branch

Use `.bbk/questions/<question-id>.json` only for a material decision that must survive multiple turns, research interruptions, branch parking, or Question Guide escalation. Classify the need first as `ENVIRONMENT_FACT`, `CONFIGURATION_PARAMETER`, `REVERSIBLE_IMPLEMENTATION_CHOICE`, `ARCHITECTURAL_DECISION`, `AUTHORITY_EXPANSION`, or `USER_RESERVED_PREFERENCE`. Facts, parameters, and ordinary reversible choices do not require user attention by default.

A branch keeps one root decision visible and records attention rationale, discoverability, safe default, unaffected work, the current recommendation, proposal response, root-question disposition, accepted decision, related and independent questions, dependencies, invalidation, evidence exposure, unresolved point, stopping assessment, and next action.

The normal path is recommendation-first:

```text
Questioning Wayfinder recommendation
  → APPROVE: RESOLVED without a Question Guide
  → bounded correction: REVISE recommendation
  → REJECT / material ambiguity / deeper request: open one Question Guide
```

`REJECT` and `REVISE` are responses to the current proposal. They do not dispose the root question. A branch closes only with an accepted decision or an explicit non-resolution disposition. Batch coherent independent requests and preserve every stable request ID and answer in one response packet.
