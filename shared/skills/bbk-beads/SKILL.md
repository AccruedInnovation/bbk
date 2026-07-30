---
name: bbk-beads
description: Map optional BBK project, territory, question, capability, phase, and work-unit records into Beads for coordination while keeping BBK vocabulary and records authoritative for the bootstrap method. Use only when a project has elected Beads projection.
---

# BBK Beads

Beads is an optional coordination projection, not BBK semantic authority.

1. Confirm `.bbk/mappings/beads.json` enables projection and names the exact Beads workspace.
2. Run a dry-run plan before any Beads mutation.
3. Keep BBK IDs stable and store Beads IDs only as foreign bindings.
4. Use the default mapping: project → root epic; territory → epic/sub-epic; question → task; capability increment → milestone/epic; phase → milestone/epic; work unit → task.
5. Keep BBK lifecycle meaning separate from Beads workflow status. A Beads close never accepts a decision, proves validation, or establishes outcome completion.
6. Project deterministically and idempotently. Unexpected direct edits become drift to review; never apply last-write-wins reconciliation.
7. Permit Beads-to-BBK input only as a typed observation or proposed update that a responsible agent reviews.
8. For worker or validator handoff, keep the complete carrier in an authorized BBK file. Project only a compact append-only bead comment containing the BBK work-unit ID, disposition, handoff path, byte count, SHA-256, and next action. Do not store large evidence in the bead or use a mutable field as the authoritative carrier.
9. Verify a Beads write after it is applied, especially with concurrent writers or sync/server modes. Treat a missing projected comment as coordination drift, not loss of the authoritative BBK handoff.
10. Do not build direct Dolt semantics into BBK. Use a replaceable adapter or CLI boundary.

## Profile-bound work

When a projected work item depends on a language or domain profile, preserve the profile identity, effective lock or digest, and required gates as coordination metadata. Beads does not discover, select, validate, or override profiles.

## Handoff command boundary

Use `bbk beads handoff-plan --handoff <file> --bead <id>` to generate the compact append-only update. Add `--apply` only when `.bbk/mappings/beads.json` explicitly has both `enabled=true` and `write_enabled=true`; BBK then calls `bd comments add <id> <pointer>`. Verify the resulting bead when concurrency or synchronization is material. The BBK file remains authoritative.
