---
name: bbk-evidence
description: Create, compare, interpret, and reuse BBK manifests, candidate identities, gate receipts, validation evidence, and handoffs. Use when exact file identity, semantic JSON equivalence, stale evidence, or repeated validation is material.
---

# BBK Evidence

Use evidence to establish a specific assertion, not to accumulate ceremony.

0. Bind evidence to the exact planning subject as well as the candidate: fit revision, outcome references, structure-contract digest, slice IDs, work-unit revision, profile digest, and assertion where applicable.

1. State the assertion and subject before collecting evidence.
2. Use exact SHA-256 bytes for immutable source, manifests, candidates, generated definitions, and artifacts whose byte identity is meaningful.
3. Use canonical JSON comparison when structured semantic equivalence is the claim. Do not treat formatting-only JSON changes as semantic drift.
4. Treat compiler output, timestamps, platform metadata, nondeterministic archives, and similar outputs as semantic or fresh-run receipts unless deterministic bytes are explicitly required.
5. Bind every receipt to the full fingerprint needed for reuse: subject, candidate, gate definition, command, environment, toolchain, inputs, and configuration.
6. Reuse a prior `PASS` only when the entire fingerprint is unchanged and the receipt has not been invalidated.
7. Explain drift as added, removed, byte-changed, semantic-changed, semantic-equivalent, or unavailable—not merely “hash mismatch.”
8. Seal evidence only after collection is complete. Later annotations go outside the sealed object and link to it.
9. Preserve failed attempts and conflicting evidence.
10. Do not hash mutable indexes into themselves or copy one current digest into many hand-maintained authorities. Generate projections from one canonical mapping source.

## EvidenceReceipt v2

Record what actually ran or was observed, its exact subject, operation, environment, inputs, outputs, trust class, completeness, redaction, and reuse dependencies. Keep EvidenceReceipt, assertion evaluation, and review aggregate separate. Freeform “tests passed” prose is an unstructured observation, not required-gate evidence.

## Profile-bound evidence

When a language or domain profile contributes evidence, bind the profile identity, package/effective digest, capability operation, adapter, toolchain, and exact input/output subject. An installed skill name alone is not evidence that the profile or adapter was selected or qualified.

## Profile-bound evidence

Bind profile-derived evidence to the exact profile id, version, package/root digest, selected router and focused procedure, effective toolchain context, request digest, and adapter identity. `bbk-installed-profiles` establishes managed availability only; it does not make a stale, incomplete, or externally unqualified receipt reusable.
