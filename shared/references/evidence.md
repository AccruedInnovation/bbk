# Evidence and Candidate Identity

Exact-byte identity is appropriate for source inputs, manifests, generated definitions, candidate trees, and artifacts whose byte form is part of the claim. Canonical semantic comparison is appropriate for structured JSON where formatting is irrelevant. Nondeterministic outputs require fresh-run semantic receipts rather than impossible byte equality. Freeze candidates after ordinary edits and cheap checks. Any later mutation makes the candidate or its receipt stale.
