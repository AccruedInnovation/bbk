# State–Decision–Effect Design

Use an applicability-aware concern nested in `ImplementationStructureContract`. `NONE` is for materially stateless or externally governed work; `INLINE` is for one small local workflow; `CONTRACT` is for material lifecycle, ordering, concurrency, retry, duplicate, cancellation, timeout, partial-completion, acknowledgement, recovery, irreversible effect, or recurring-defect concerns.

Model mutually exclusive alternatives as sums and independent dimensions as products. Name one canonical semantic owner. Keep observations, derived facts, projections, and receipts distinct from canonical state. Decisions consume explicit state and explicit inputs and produce next state, facts, effect intents, rejection, or no change. Effects are performed only by controlled executors under explicit authority.

The formalization ladder is `NONE`, `TRANSITION_TABLE`, `STATE_MACHINE_PROPERTIES`, `FORMAL_EXECUTABLE_MODEL`. Choose the lowest adequate rung. Traces and models are evidence artifacts, not runtime authority.
