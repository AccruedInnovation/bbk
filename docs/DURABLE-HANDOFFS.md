# Durable handoffs and resumable work

Agent messages are coordination channels, not guaranteed lossless artifact transports. Exact paths, hashes, schemas, evidence carriers, and large outputs must survive host truncation and execution-window interruption.

## Authoritative carrier

BBK uses a UTF-8 JSON handoff whose referenced files are bound by:

```text
project-relative path + byte count + SHA-256
```

Create a handoff:

```powershell
python tools\bbk.py handoff create `
  --root D:\Project `
  --work-unit WU-STAGE1-HARNESS `
  --attempt 2 `
  --role bbk_worker `
  --disposition PARTIAL `
  --summary "Implementation complete; focused validation remains." `
  --artifact src\provider.cs `
  --evidence evidence\source-review.json `
  --continuation-state READY `
  --checkpoint .bbk\runtime\stage1-checkpoint.json `
  --completed-step implementation `
  --next-step "run focused build and schema checks" `
  --next-action "Resume the same worker thread and run focused validation."
```

Verify before relying on it:

```powershell
python tools\bbk.py handoff verify `
  .bbk\handoffs\WU-STAGE1-HARNESS\HO-WU-STAGE1-HARNESS-2.json `
  --root D:\Project
```

The conversational return should remain compact: disposition, handoff path, handoff bytes, handoff SHA-256, blocker if any, and smallest next action. Another role reads and verifies the file directly. If the locator itself was truncated, rediscover it deterministically:

```powershell
python tools\bbk.py handoff list --root D:\Project `
  --work-unit WU-STAGE1-HARNESS --latest
```

## Logical execution windows

BBK cannot manufacture a host timeout setting that the host does not expose. Instead, long-running workers receive an **extended logical execution window**:

- continue beyond preflight into implementation and focused checks;
- checkpoint at bounded intervals and before the host boundary is likely to end;
- resume the same logical thread from verified state when possible;
- classify host-window expiry as an infrastructure interruption, not a candidate defect;
- reassign only when the original thread is unavailable, unsuitable, or repeatedly makes no progress;
- preserve attempt lineage and completed work.

New projects record this policy in `.bbk/config.json` under `execution`.

## Beads projection

Beads is useful as a searchable work graph and coordination index. Keep the full handoff in BBK and append a compact pointer to the corresponding bead:

```powershell
python tools\bbk.py beads handoff-plan `
  --root D:\Project `
  --handoff .bbk\handoffs\WU-STAGE1-HARNESS\HO-WU-STAGE1-HARNESS-2.json `
  --bead bd-123
```

The dry-run plan uses `bd comments add <id> <pointer>`. The comment contains only the work-unit ID, attempt, disposition, handoff path, byte count, SHA-256, and next action. It does not paste large artifacts into the bead, and closing the bead does not prove BBK validation or outcome completion.

To apply the pointer directly, first set both `enabled` and `write_enabled` to `true` in `.bbk/mappings/beads.json`, bind the exact workspace, and add `--apply`. The command remains fail-closed when `bd` is unavailable or the mapping is not explicitly write-enabled.

## Lossless configured-gate output

The gate runner writes complete stdout and stderr streams beside each gate receipt. The receipt contains bounded previews plus `stdout_file` and `stderr_file` records with project-relative path, byte count, and SHA-256. When a preview is truncated, read and verify the bound file; do not reconstruct the missing tail from prose. A prior PASS receipt is reused only while both stream files remain byte-identical to their bindings.

## Draft 2020-12 schema validation

BBK now exposes one discoverable adapter:

```powershell
python tools\bbk.py schema status
python tools\bbk.py schema validate --schema schema.json --instance candidate.json
```

When `python-jsonschema` is absent, the command returns `BLOCKED` with an exact remediation. An explicit `--ensure` creates an isolated environment and installs pinned `jsonschema==4.25.1`; `--wheelhouse PATH` supports an offline package source. BBK does not silently create environments or access the network.
