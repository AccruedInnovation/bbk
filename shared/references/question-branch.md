# Durable question branch

Use `.bbk/questions/<question-id>.json` for a material decision that must survive multiple turns, research interruptions, branch parking, or Question Guide escalation.

A branch keeps one root decision visible and records the current recommendation, proposal response, root-question disposition, accepted decision, related and independent questions, dependencies, invalidation, evidence exposure, unresolved point, stopping assessment, and next action.

The normal path is recommendation-first:

```text
Questioning Wayfinder recommendation
  → APPROVE: RESOLVED without a Question Guide
  → bounded correction: REVISE recommendation
  → REJECT / material ambiguity / deeper request: open one Question Guide
```

`REJECT` and `REVISE` are responses to the current proposal. They do not dispose the root question. A branch closes only with an accepted decision or an explicit non-resolution disposition.

Persist only material branches. Routine recommendations that are accepted immediately may be recorded directly as the resulting decision packet.
