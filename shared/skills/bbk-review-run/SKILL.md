---
name: bbk-review-run
description: Execute or record revision-bound review attempts, evidence, findings, and non-averaging aggregation without conflating infrastructure failure with candidate failure.
requires_prompt_modules: []
standalone_prompt_modules: []
---

# BBK Review Run

1. Verify exact manifest, context, subject, AssuranceContract, candidate, and prerequisite evidence digests before any attempt.
2. Launch only the attempts named by the manifest and grant only their exact read scope, tools, effects, assertions, and result schema.
3. Keep deterministic evidence production, assertion evaluation, and aggregate disposition distinct.
4. Record logical role/spec, physical invocation/session, model/provider/tool, exact context pack, prior-findings visibility, outcome-evidence exposure, attempt purpose, independence facts, environment, timestamps, and completion state per attempt.
5. Reviewer crash, malformed output, missing environment, stale context, and unavailable tooling are reviewer/context/environment/infrastructure states—not candidate findings.
6. Candidate reviewers remain read-only toward the subject.
7. Preserve every finding, evidence receipt, and append-only exposure event. Do not majority-vote, average severity, infer a pass from reviewer tone, or silently relabel exploratory/post-hoc work as confirmatory.
8. Every repair creates a successor candidate. Use targeted closure for exact prior findings and blind reassessment when the assurance contract requires new-defect discovery or anti-anchoring.
9. Derive the aggregate centrally from required attempts, assertion evaluations, open findings, context completeness, protected floors, and manifest policy.
10. Return exact blockers, advisories, stale dependencies, repair count, escalation reason, and residual uncertainty.

## Profile-aware execution

Confirm the ReviewManifest selection against `bbk-installed-profiles` and the effective lock. Invoke profile review lenses and evidence adapters only through the exact profile router and request package recorded by the manifest. Preserve the profile/toolchain identity and distinguish profile infrastructure failure from candidate failure.
