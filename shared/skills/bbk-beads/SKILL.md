---
name: bbk-beads
description: Project the BBK records owned by the invoking role into the project Beads workspace as normal coordination state while keeping BBK records, authority, evidence, decisions, and lifecycle semantics canonical. Load on demand when an owning role creates or changes a project, territory, decision, question, capability increment, phase, WorkUnit, execution-state record, or durable handoff pointer.
requires_prompt_modules: []
standalone_prompt_modules: []
---

# BBK Beads

Beads is BBK's default coordination projection for newly initialized projects. It is not BBK semantic authority.

## Ownership and triggers

Load this skill only for record kinds owned by the current role:

- Root and Territory Wayfinders: project, territory, and decision records.
- Planning and Phase Wayfinders: capability increments, phases, and WorkUnits.
- Root, Territory, and Worker Orchestrators: execution-state records and durable-handoff pointers.
- Questioning Wayfinder: question records.

Project only after the canonical BBK record is durable. Another role may inspect the projection, but must not mutate a record kind it does not own.

## Normal synchronization

1. Read `.bbk/mappings/beads.json`; new projects default to `enabled=true`, `write_enabled=true`, `workspace="."`, and first-use initialization enabled.
2. Run `bbk beads plan --root <project> --kind <owned-kind>` before mutation. Review the exact create, update, inspect, initialization, parent-binding, and stale-binding operations.
3. When the plan is valid and the role has authority for every selected record, run the same command with `--apply`. The BBK adapter initializes Beads on first use when configured, invokes `bd` through a replaceable CLI boundary, verifies each returned issue, and records the Beads ID only as a foreign binding.
4. If `bd` is unavailable, the workspace cannot be initialized, or a binding is ambiguous or drifted, preserve the canonical BBK change and report a typed coordination warning. Do not block otherwise-valid planning or execution solely because the optional tracker capability is unavailable.
5. Keep BBK IDs stable. Never search by title and silently adopt a Beads issue; create or repair the explicit foreign binding under accountable review.
6. Use the default mapping: project → root epic; territory → epic/sub-epic; decision → task; question → task; capability increment → epic; phase → epic; WorkUnit → task. Parent-child links are coordination structure only.
7. Keep BBK lifecycle meaning separate from Beads workflow status. A Beads claim, status, dependency, close, comment, or deletion never accepts a decision, proves an assertion, closes a finding, validates a candidate, establishes outcome completion, or authorizes release.
8. Project deterministically and idempotently. Unexpected direct edits, missing issues, parent changes, duplicate bindings, and incompatible issue types are drift to review; never apply last-write-wins reconciliation.
9. Permit Beads-to-BBK input only as a typed observation or proposed update that the responsible BBK role evaluates against current canonical state and authority.
10. Do not place secrets, credentials, protected evidence, large artifacts, or private reasoning in Beads. Project only the minimum coordination metadata authorized for the workspace.

## Execution-state and durable-handoff pointers

For an execution-state transition or Worker, Validator, Reviewer, or orchestrator handoff, keep the complete carrier in an authorized BBK file. Append only a verified compact pointer; never translate BBK semantic state into Beads workflow status.

- Worker Orchestrator normally targets the mapped WorkUnit with `bbk beads handoff-plan --handoff <file>`.
- Root or Territory Orchestrator passes `--target-bbk-id <project-or-territory-id>` to bind the pointer to the exact mapped record it owns. An explicit target must already have a unique mapping, and a simultaneously supplied `--bead` must match that binding.
- `--bead <id>` without `--target-bbk-id` is reserved for an explicitly reviewed foreign target when no WorkUnit binding exists. It does not create a BBK-to-Beads binding.

The compact comment contains the target BBK ID, subject kind and ID, producer role, WorkUnit ID, disposition, handoff path, byte count, SHA-256, and smallest next action. Add `--apply` only when the mapping is enabled and write-enabled. The adapter verifies the resulting Beads issue after mutation. The BBK file remains authoritative. The durable carrier remains the authoritative payload.

## Profile-bound work

When a projected WorkUnit depends on a language or domain profile, preserve only the profile identity, effective lock or digest, and required gate identifiers as coordination metadata. Beads does not discover, select, validate, or override profiles.
