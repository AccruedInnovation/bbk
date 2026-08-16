# Deterministic Operations and Diagnostics

Prefer a qualified checked-in operation from `spec/operations/deterministic-operation-registry.json` and invoke it with its registered argv array, subject, environment policy, allowed effects, output schema, and invalidation keys. Do not hand-roll shell, Python, PowerShell, JavaScript, `eval`, wrapper, or ledger mechanisms. An unregistered or ad-hoc operation fails closed before effects.

A missing required operation is implemented and qualified as one reusable helper in the current WorkUnit. Method, path, schema, serialization, projection, launch, carrier, and other deterministic mechanical failures are recorded in the WorkUnit incident ledger and repaired in the same semantic attempt when effects reconcile; they do not trigger replanning or Reviewer work. Use Reviewer only for unresolved semantic qualitative ambiguity, contradictory acceptance evidence, integrity/ownership ambiguity, or cross-boundary effects under `DEC-ER-017`.

Typed diagnostics keep the semantic inner result separate from the mechanical envelope. Static inventory may establish only static claims; it never establishes dynamic execution. Immediate-stop classes (`WRONG_SUBJECT`, `CONTRADICTORY_EVIDENCE`, `INTEGRITY_FAILURE`, `UNOWNED_WRITE`, `AMBIGUOUS_IRREVERSIBLE_EFFECT`, and `CROSS_BOUNDARY_EFFECT`) fence broad work before the next effect.
