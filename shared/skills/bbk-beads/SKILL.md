---
name: bbk-beads
description: Project every substantive BBK semantic object and governed invocation through mandatory Beads coordination while keeping BBK records, authority, evidence, decisions, and lifecycle semantics canonical.
requires_prompt_modules: []
standalone_prompt_modules: []
---

# BBK Beads

Beads is mandatory coordination state for every substantive BBK record and governed invocation. It is never BBK semantic authority: BBK records, decisions, assertions, findings, candidate identity, lifecycle, acceptance, and release state remain canonical in BBK.

## Ownership and triggers

Load this skill only for record kinds owned by the current role:

- Root and Territory Wayfinders: project, territory, and decision records.
- Planning and Phase Wayfinders: capability increments, phases, and WorkUnits.
- Root, Territory, and Worker Orchestrators: execution-state records and durable-handoff pointers.
- Questioning Wayfinder: question records.

Project only after the canonical BBK record is durable. Another role may inspect the projection, but must not mutate a record kind it does not own. Every substantive owned record and governed invocation has one typed, idempotent coordination projection; absence, drift, or failure is preserved as coordination evidence rather than converted into semantic state.

## Mandatory single-writer synchronization

1. Read .bbk/mappings/beads.json; mandatory mappings declare enabled=true, write_enabled=true, workspace=., and first-use initialization.
2. Run bbk beads plan --root <project> --kind <owned-kind> before mutation. Review the exact create, update, inspect, initialization, parent-binding, and stale-binding operations.
3. When the plan is valid and the role has authority for every selected record, run the same checked-in BBK CLI command with --apply. The adapter is the sole project-scoped Beads writer and serializes it with expected-revision and idempotency guards.
4. The adapter invokes only pinned github:gastownhall/beads@1.1.0 through the canonical mise route mise exec ... -- bd. Global PATH discovery, raw bd, direct backend writes, and unregistered wrappers are denied before effect. Receipts record the pinned tool specification, mise executable, and version binding.
5. If mise, pinned Beads, workspace initialization, or a binding is unavailable or fails, preserve the canonical BBK record and append an immutable typed failure receipt. Do not claim projection success or continue past the next safe coordination boundary until the exact deterministic correction is applied. A first eligible mechanical correction stays in the same semantic attempt; a second matching unresolved recurrence or immediate-stop failure routes through the parent diagnostic path.
6. Keep BBK IDs stable. Never search by title and silently adopt a Beads issue; create or repair the explicit foreign binding under accountable review.
7. Use the default mapping: project to root epic; territory to epic/sub-epic; decision to task; question to task; capability increment to epic; phase to epic; WorkUnit to task. Parent-child links are coordination structure only.
8. Keep BBK lifecycle meaning separate from Beads workflow status. A Beads claim, status, dependency, close, comment, or deletion never accepts a decision, proves an assertion, closes a finding, validates a candidate, establishes outcome completion, or authorizes release.
9. Project deterministically and idempotently. Unexpected direct edits, missing issues, parent changes, duplicate bindings, and incompatible issue types are drift to review; never apply last-write-wins reconciliation.
10. Permit Beads-to-BBK input only as a typed observation or proposed update that the responsible BBK role evaluates against current canonical state and authority.
11. Do not place secrets, credentials, protected evidence, large artifacts, or private reasoning in Beads. Project only the minimum coordination metadata authorized for the workspace.

## Execution-state and durable-handoff pointers

For an execution-state transition or Worker, Validator, Reviewer, or orchestrator handoff, keep the complete carrier in an authorized BBK file. Append only a verified compact pointer; never translate BBK semantic state into Beads workflow status.

- Worker Orchestrator normally targets the mapped WorkUnit with bbk beads handoff-plan --handoff <file>.
- Root or Territory Orchestrator passes --target-bbk-id <project-or-territory-id> to bind the pointer to the exact mapped record it owns. An explicit target must already have a unique mapping, and a simultaneously supplied --bead must match that binding.
- --bead <id> without --target-bbk-id is reserved for an explicitly reviewed foreign target when no WorkUnit binding exists. It does not create a BBK-to-Beads binding.

The compact comment contains the target BBK ID, subject kind and ID, producer role, WorkUnit ID, disposition, handoff path, byte count, SHA-256, and smallest next action. Add --apply only after the mandatory mapping and writer preflight pass. The adapter verifies the resulting Beads issue after mutation. The BBK file remains authoritative. The durable carrier remains the authoritative payload.

## Profile-bound work

When a projected WorkUnit depends on a language or domain profile, preserve only the profile identity, effective lock or digest, and required gate identifiers as coordination metadata. Beads does not discover, select, validate, or override profiles.
