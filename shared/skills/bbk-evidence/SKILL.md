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

- `EVIDENCE.ASSERTION_FIRST` — State exact assertion and subject before collecting, reusing, or interpreting evidence.
- `EVIDENCE.FINGERPRINT` — Bind each receipt to candidate or planning subject, operation/method, command, inputs, config, environment, toolchain, profile, context/exposure policy, and produced artifacts.
- `EVIDENCE.REUSE` — Reuse PASS only when the full fingerprint and dependency closure are unchanged and no invalidation condition fired.
- `EVIDENCE.OBSERVATION_INFERENCE` — Separate direct observation, source report, inference, evaluation, recommendation, and authority-bearing decision.
- `EVIDENCE.APPEND_ONLY` — Preserve failed attempts, conflicts, exposure history, and superseded state. Link later annotations/dispositions to immutable records; do not rewrite them.
- `EVIDENCE.INVALIDATE` — A material subject, source, assertion, criterion, method, environment, context, independence, or exposure change invalidates only affected evidence/conclusions. Create a successor and retain unaffected valid reuse.

<!-- End BBK prompt module bbk-prompt-evidence-lineage -->

> Apply the already embedded `bbk-prompt-evidence-subject-identity` module here.

## EvidenceReceipt v2

<!-- BBK prompt module bbk-prompt-evidence-receipts: expanded from canonical source -->

### Evidence representation and receipt protocol

Represent byte, semantic, command, profile, and observation evidence with the exact identity, carrier, trust, completeness, and reuse information needed by assurance roles.

- `EVIDENCE.PLANNING_BINDING` — Bind evidence to the exact planning subject and candidate as applicable: fit revision, outcome refs, structure-contract digest, slice IDs, WorkUnit revision, profile digest, assertion, and dependency closure.
- `EVIDENCE.BYTE_IDENTITY` — Use exact SHA-256 bytes for immutable source, manifests, candidates, generated definitions, and artifacts whose byte identity is meaningful.
- `EVIDENCE.SEMANTIC_IDENTITY` — For semantic equivalence, use canonical structured comparison. Formatting-only JSON change is not semantic drift; classify added, removed, byte-changed, semantic-changed, semantic-equivalent, or unavailable—not just hash mismatch.
- `EVIDENCE.NONDETERMINISTIC` — Treat compiler output, timestamps, platform metadata, nondeterministic archives, and similar values as semantic or fresh-run receipts unless exact deterministic bytes are required.
- `EVIDENCE.RECEIPT` — An EvidenceReceipt records what actually ran or was observed; exact subject, candidate and assertion; operation or method; command; environment; toolchain and profile; inputs and configuration; outputs and raw carriers; coverage; trust and completeness class; redaction; freshness; exposure; and reuse dependencies. Freeform tests-passed prose or model confidence is not required-gate evidence.
- `EVIDENCE.SEAL` — Seal evidence only after collection. Put later annotations outside and link them; preserve failed attempts, conflicts, and superseded state.
- `EVIDENCE.NO_SELF_HASH` — Do not self-hash mutable indexes or copy one digest into many hand-kept authorities. Generate projections from one canonical mapping source.
- `EVIDENCE.PROFILE_BINDING` — For profile evidence, bind exact profile ID/version, source/effective digest, router/focused procedure, capability operation, adapter identity, toolchain context, request digest, and input/output subject. A skill name proves neither selection nor qualification.
- `EVIDENCE.COMMAND_STREAMS` — If a configured gate stores only bounded UTF-8 previews in its JSON receipt, keep authoritative stdout/stderr beside it and bind each by safe project-relative path, byte count, and SHA-256. Reusable PASS requires both streams unchanged.
- `EVIDENCE.CURRENT_UNTIL_INVALIDATED` — A passing deterministic receipt stays current while exact subject binding and declared invalidation-key values stay unchanged. Validate identity/binding, then reuse; crossing a role, process, session, host, or orchestration boundary does not invalidate it.
- `EVIDENCE.DUPLICATE_CHECK` — Before a deterministic operation, derive claim ID, subject identity, method identity, and invalidation-key values. Return matching current PASS as `REUSED_RECEIPT`; authorize the smallest check only without a current match or under an explicit independent-method requirement.
- `EVIDENCE.VERIFICATION_BUDGET` — Invocation contracts state required/reusable/independent checks, forbidden duplicates, invalidation triggers, max rechecks, and stop condition. Stop when each required claim has a current adequate receipt; independent judgment does not require duplicate execution.

<!-- End BBK prompt module bbk-prompt-evidence-receipts -->

## Durable handoff evidence

For an exact deliverable set, prefer `bbk artifact manifest --root <root> --path <path> --output <manifest>` and `bbk artifact verify <manifest> --root <root>` over ad hoc shell or PowerShell hashing. The manifest uses portable relative paths, byte counts, SHA-256, one content digest, deterministic ordering, and excludes BBK examples by default.

> Apply the already embedded `bbk-prompt-durable-handoff` module here.

## Profile-bound evidence

> Apply the already embedded `bbk-prompt-profile-qualification` module here.

## Lossless command evidence

> Apply the `EVIDENCE.COMMAND_STREAMS` clause above.
