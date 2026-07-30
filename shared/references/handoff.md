# Durable handoff reference

A BBK handoff is a compact coordination record whose authoritative large or exact outputs remain in workspace files.

Required transport invariant:

```text
path + byte count + SHA-256
```

Use `bbk handoff create` to build a record and `bbk handoff verify` before another role relies on it. A conversational message may summarize the handoff, but it must not be the sole carrier for exact schemas, hashes, paths, or evidence that can be truncated by the host.

For a work tracker such as Beads, append only a compact pointer containing the BBK work-unit ID, disposition, handoff path, handoff byte count, handoff SHA-256, and smallest next action. The durable BBK handoff remains authoritative.

Rediscover a carrier whose conversational locator was truncated with `bbk handoff list --root <project> --work-unit <id> --latest`. Generate a compact tracker update with `bbk beads handoff-plan`; use `--apply` only after the project mapping explicitly enables Beads writes.

Configured gate output follows the same principle: the receipt carries a compact preview, while complete stdout and stderr files remain authoritative and are bound by path, byte count, and SHA-256.
