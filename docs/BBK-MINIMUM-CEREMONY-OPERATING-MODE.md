# BBK Minimum-Ceremony Operating Mode

## Controlling direction

This document is an operating-policy change for BBK. The default is to reach a working result with the smallest sufficient planning, implementation, and verification path.

Do not treat every change as a full governed campaign. Start at the lowest appropriate level and escalate only when a concrete trigger requires more planning, authority handling, independence, evidence, or packaging.

This policy applies both to all future BBK requests unless the controlling user explicitly requests a stronger assurance or governance mode.

## Non-negotiable assurance floor

Every implementation change receives one candidate-bound Validator evaluation, even routine changes. The Validator is the minimum independent check that can catch Worker mistakes.

The routine Validator should be compact:

- one exact candidate identity, normally the changed-file set plus source revision/hash;
- one grouped assertion set covering the requested behavior and directly affected compatibility;
- one qualified deterministic method or focused test command;
- one independent logical Validator invocation, separate from the Worker;
- one concise result with PASS, FAIL, or INCONCLUSIVE and the relevant evidence.

The Validator does not imply a Reviewer, ReviewManifest, full AssuranceContract, sealed artifact package, broad test suite, or release assessment. Those are escalation tools.

Reuse a current Validator receipt whenever its declared subject and invalidation keys are unchanged. Do not rerun it merely because another role produced coordination metadata.

## Graduated execution levels

### Level 0 — Routine change (default)

Use this level when the outcome and implementation direction are already clear and the change is local, reversible, and free of consequential external effects.

Required path:

1. Classify the request as routine.
2. Create the smallest compact WorkUnit, or generate one mechanically from the user request.
3. Dispatch one Worker through the normal Worker path; the controller must not implement the change itself.
4. Run focused checks while the Worker edits.
5. Freeze only a lightweight candidate identity sufficient for the Validator; do not create a sealed package by default.
6. Run exactly one grouped candidate-bound Validator.
7. Return changed files, focused checks, Validator result, residuals, and the smallest next action.

Do not invoke Root Wayfinder, Architecture, Verification Designer, Reviewer, ReviewManifest compilation, full candidate packaging, artifact finalization, or broad-suite validation unless a named escalation trigger applies.

### Level 1 — Bounded consequential change

Escalate only when the change affects a shared/public interface, multiple mutation owners, a migration, external or credential-bearing effects, a material toolchain/environment boundary, or a meaningful recovery/rollback contract.

Use the smallest additional structure needed: a Root/Territory Orchestrator or Wayfinder, a focused assurance contract or manifest when necessary, and one grouped Validator. Do not automatically add a Reviewer or sealed package.

### Level 2 — Full governed campaign

Use full planning, independent review, expanded evidence, immutable candidate packaging, and release-oriented gates only for safety/security exposure, irreversible or destructive work, publication/release, consequential deployment, explicit user request, unresolved architectural alternatives, or a material authority/protected-floor decision. The amount of structure applied should still be limited to the minimum required to get an effective result - do not re-plan an entire project if a single narrow vertical slice will do.

## Escalation triggers

Escalation must name the exact trigger and affected scope. Valid triggers are:

- outcome, requirement, or acceptance meaning is unclear;
- a canonical public/shared interface or data contract changes;
- more than one mutation or integration owner is required;
- external, credential, network, deployment, migration, destructive, or irreversible effects are involved;
- a new recovery, retry, lifecycle, or state-ownership decision is required;
- independent qualitative judgment is needed because deterministic checks cannot establish a material risk;
- candidate acceptance, publication, release, or live acceptance is explicitly requested;
- the routine Validator is inconclusive or finds a material defect that cannot be repaired locally.

Unknowns that can be inspected, parameterized, safely defaulted, or deferred are not escalation triggers by themselves.

## Artifact and evidence economy

The artifact tool remains authoritative for exact immutable packages, binary or large outputs, durable cross-session handoffs, candidate/release boundaries, and explicit packaging requests. It is not a default completion gate for ordinary source changes.

For Level 0 work:

- do not run `artifact finalize`, `freshness`, `candidate freeze`, or successor packaging unless the WorkUnit explicitly needs that boundary;
- do not create a ReviewContext package or durable handoff when the structured role return carries the result without loss;
- record concise command results instead of producing a separate evidence package;
- preserve failed Validator output, but do not manufacture hashes, manifests, or findings unrelated to the requested behavior.

The artifact tool proves byte identity and declared closure only. It does not replace the routine Validator, and a package pass does not establish semantic correctness.

## Planning stop rule

Planning stops as soon as the minimum WorkUnit, authority, mutation owner, inputs/toolchain, return route, focused checks, and Validator contract are executable. Do not produce a roadmap, architecture record, assurance design, or distant phase plan merely because the repository is large or BBK records are absent.

When a local mechanical defect occurs before candidate freeze, repair it in the same Worker attempt and rerun only the affected focused check. Do not create a successor plan or new campaign for a reversible local repair.
