---
name: bbk-evidence
description: Create, compare, interpret, and reuse BBK manifests, candidate identities, gate receipts, validation evidence, and handoffs. Use when exact file identity, semantic JSON equivalence, stale evidence, or repeated validation is material.
requires_prompt_modules: ["bbk-prompt-durable-handoff", "bbk-prompt-profile-qualification", "bbk-prompt-evidence-subject-identity"]
standalone_prompt_modules: ["bbk-prompt-evidence-lineage", "bbk-prompt-evidence-receipts"]
---


# BBK Evidence

<!-- BBK prompt module bbk-prompt-evidence-lineage: expanded from canonical source -->

### Evidence identity, reuse, and invalidation

Bind every observation and receipt to the exact assertion, subject, environment, method, and dependency closure it can establish.

- `EVIDENCE.ASSERTION_FIRST` — State the exact assertion and subject before collecting, reusing, or interpreting evidence.
- `EVIDENCE.FINGERPRINT` — Bind each receipt to candidate or planning subject, operation or method, command, inputs, configuration, environment, toolchain, profile, context and exposure policy, and produced artifacts.
- `EVIDENCE.REUSE` — Reuse a prior PASS only when the complete fingerprint and dependency closure remain unchanged and no invalidation condition has fired.
- `EVIDENCE.OBSERVATION_INFERENCE` — Separate direct observation, source report, inference, evaluation, recommendation, and authority-bearing decision.
- `EVIDENCE.APPEND_ONLY` — Preserve failed attempts, conflicting evidence, exposure history, and superseded state. Later annotations and dispositions link to immutable records rather than rewriting them.
- `EVIDENCE.INVALIDATE` — A material subject, source, assertion, criterion, method, environment, context, independence, or exposure change invalidates only the affected evidence and conclusions; create a successor and preserve unaffected valid reuse.

<!-- End BBK prompt module bbk-prompt-evidence-lineage -->

> Apply the already embedded `bbk-prompt-evidence-subject-identity` module here.

## EvidenceReceipt v2

<!-- BBK prompt module bbk-prompt-evidence-receipts: expanded from canonical source -->

### Evidence representation and receipt protocol

Represent byte, semantic, command, profile, and observation evidence with the exact identity, carrier, trust, completeness, and reuse information needed by assurance roles.

- `EVIDENCE.PLANNING_BINDING` — Bind evidence to the exact planning subject as well as the candidate where applicable: fit revision, outcome references, structure-contract digest, slice IDs, WorkUnit revision, profile digest, assertion, and dependency closure.
- `EVIDENCE.BYTE_IDENTITY` — Use exact SHA-256 bytes for immutable source, manifests, candidates, generated definitions, and artifacts whose byte identity is meaningful.
- `EVIDENCE.SEMANTIC_IDENTITY` — Use canonical structured comparison when semantic equivalence is the claim. Do not treat formatting-only JSON changes as semantic drift, and classify drift as added, removed, byte-changed, semantic-changed, semantic-equivalent, or unavailable rather than merely hash mismatch.
- `EVIDENCE.NONDETERMINISTIC` — Treat compiler output, timestamps, platform metadata, nondeterministic archives, and similar values as semantic or fresh-run receipts unless deterministic byte identity is explicitly required.
- `EVIDENCE.RECEIPT` — An EvidenceReceipt records what actually ran or was observed; exact subject, candidate and assertion; operation or method; command; environment; toolchain and profile; inputs and configuration; outputs and raw carriers; coverage; trust and completeness class; redaction; freshness; exposure; and reuse dependencies. Freeform tests-passed prose or model confidence is not required-gate evidence.
- `EVIDENCE.SEAL` — Seal an evidence object only after collection is complete. Put later annotations outside the sealed object and link them; preserve failed attempts, conflicting evidence, and superseded state.
- `EVIDENCE.NO_SELF_HASH` — Do not hash mutable indexes into themselves or copy one current digest into many hand-maintained authorities. Generate projections from one canonical mapping source.
- `EVIDENCE.PROFILE_BINDING` — For profile-derived evidence, bind exact profile ID and version, source or effective digest, router and focused procedure, capability operation, adapter identity, toolchain context, request digest, and input/output subject. An installed skill name alone establishes neither selection nor qualification.
- `EVIDENCE.COMMAND_STREAMS` — When a configured gate stores only bounded UTF-8 previews in its JSON receipt, preserve authoritative stdout and stderr beside the receipt and bind each by safe project-relative path, byte count, and SHA-256. A reusable PASS remains eligible only while both raw streams match.
- `EVIDENCE.CURRENT_UNTIL_INVALIDATED` — A successful deterministic receipt remains current while its exact subject binding and declared invalidation-key values are unchanged. Consumers validate identity and binding, then reuse it; a role, process, session, host, or orchestration boundary alone is not an invalidation.
- `EVIDENCE.DUPLICATE_CHECK` — Before a deterministic operation, derive claim ID, subject identity, method identity, and invalidation-key values. Return a matching current PASS as `REUSED_RECEIPT`; authorize the smallest check only when no current match exists or an explicit independent-method requirement applies.
- `EVIDENCE.VERIFICATION_BUDGET` — Invocation contracts declare required checks, reusable receipts, independent checks, forbidden duplicates, invalidation triggers, maximum rechecks, and a stop condition. Stop when every required claim has a current adequate receipt; independent judgment does not imply duplicate execution.

<!-- End BBK prompt module bbk-prompt-evidence-receipts -->

## Durable handoff evidence

For an exact deliverable set, prefer `bbk artifact manifest --root <root> --path <path> --output <manifest>` and `bbk artifact verify <manifest> --root <root>` over ad hoc shell or PowerShell hashing. The manifest uses portable relative paths, byte counts, SHA-256, one content digest, deterministic ordering, and excludes BBK examples by default.

> Apply the already embedded `bbk-prompt-durable-handoff` module here.

## Profile-bound evidence

> Apply the already embedded `bbk-prompt-profile-qualification` module here.

## Lossless command evidence

> Apply the `EVIDENCE.COMMAND_STREAMS` clause above.
