# PRD J — Authority and decision recorder

**Status:** Proposed — later hardening

**Owner kind:** Controller-facing evidence recorder; semantic owner remains the accountable human/controller and the canonical BBK role named by the record
**Priority:** Later hardening; foundational for deterministic planning and execution admission

## Problem and evidence

BBK repeatedly depends on exact answers to two questions: what effects were explicitly authorized, and which proposed semantic choice was explicitly accepted? The repository is unequivocal that host access, silence, delivery receipts, tracker state, ordinary assistant prose, successful tooling, and inferred intent are not authority. In OMP, durable authority must be backed by the controller's native `ask` response and correlated `BBK_USER_RESPONSE`; canonical roles then create the applicable ADR-compatible record.

Today those records can be authored manually, which risks omitting the subject/revision, effect fence, exclusions, expiry, predecessor, response provenance, or successor triggers. A deterministic recorder should validate and persist an explicit disposition. It must never decide on the user's behalf, widen the response, or manufacture acceptance from context.

`tools/launch_recorder.py` supplies a useful implementation pattern: caller-owned evidence is supplied explicitly; the recorder validates exact context, persists append-only records atomically, and does not infer host state. Existing `bbk.plan-event.v1` values `DECISION_ACCEPTED`, `DECISION_SUPERSEDED`, and `AUTHORITY_UPDATED` provide the downstream transaction vocabulary.

## Goals

1. Record an explicit user/controller authority grant, denial, restriction, revocation, or expiry with exact scope and provenance.
2. Record an explicit acceptance/rejection/deferral/supersession of one proposed decision.
3. Preserve effects, exclusions, safeguards, expiry, invalidation, predecessor, and successor requirements in append-only durable records.
4. Produce finalized identities and plan-event/Beads projection plans for downstream mechanical consumers.
5. Fail closed whenever accountable disposition or subject binding is absent, ambiguous, stale, or contradictory.

## Non-goals

- Asking the user, choosing which question to ask, recommending an answer, interpreting silence, or resolving ambiguity.
- Accepting architecture, fit, risk, findings, completion, deployment, publication, or release unless the explicit disposition names that exact subject and effect.
- Granting permissions because the host can perform an operation.
- Writing Beads semantic status or treating a tracker update as a decision.
- Replacing ADRs, question branches, plan transactions, or role-return contracts; the recorder emits references/events they consume.

## Callers

- Harness-root controller after receiving an explicit user response.
- Canonical responsible roles: Root/Questioning/Planning/Territory Wayfinder for semantic decisions; Root/Territory Orchestrator for execution-authority receipts within their authority boundary.
- Read-only consumers: [PRD H](H-planning-bundle-compiler.md), [PRD I](I-territory-boundary-compiler.md), [PRD A](A-execution-admission-compiler.md), worker-contract generation, recovery, assurance, and audit tooling.

## Commands and exact examples

Record a bounded workspace implementation grant:

```powershell
bbk --json authority record --root . `
  --authority-id AUTH-001 --revision 1 `
  --subject .bbk/subjects/SUBJECT-001.json `
  --disposition GRANTED `
  --effect WORKSPACE_IMPLEMENTATION `
  --scope .bbk/requests/AUTH-SCOPE-001.json `
  --exclude EXTERNAL_EXECUTION --exclude PUBLICATION --exclude RELEASE `
  --safeguard WORKTREE_LOCAL_WRITES `
  --expires-at 2026-09-01T00:00:00Z `
  --response .bbk/controller-responses/RESP-001.json `
  --question .bbk/questions/QUESTION-001.json
```

Record the user's exact architecture disposition:

```powershell
bbk --json decision accept --root . `
  --decision-id ADR-014 --revision 1 `
  --proposal .bbk/decisions/proposals/ADR-014.json `
  --disposition ACCEPTED `
  --response .bbk/controller-responses/RESP-014.json `
  --effects .bbk/decisions/effects/ADR-014.json `
  --exclude DEPLOYMENT_APPROVAL --exclude RISK_ACCEPTANCE
```

Record a successor restriction or superseding decision:

```powershell
bbk --json authority record --root . --authority-id AUTH-001 --revision 2 `
  --predecessor .bbk/authority/AUTH-001/r1/record.json `
  --disposition RESTRICTED --scope .bbk/requests/AUTH-SCOPE-002.json `
  --response .bbk/controller-responses/RESP-002.json --successor-reason SCOPE_REDUCED

bbk --json decision accept --root . --decision-id ADR-014 --revision 2 `
  --predecessor .bbk/decisions/ADR-014/r1/record.json `
  --proposal .bbk/decisions/proposals/ADR-014-r2.json `
  --disposition SUPERSEDED --response .bbk/controller-responses/RESP-015.json
```

The commands do not open a prompt. If the response artifact is not already present and attributable, they fail with `EXPLICIT_DISPOSITION_REQUIRED`.

## Inputs and schemas

Proposed schemas:

- `bbk.controller-disposition-evidence.v1`: immutable response evidence with request ID, question ID, controller/session identity, accountable actor kind, response source, answer payload/digest, received time, and correlation.
- `bbk.authority-record.v1`: authority disposition and exact effect envelope.
- `bbk.decision-record.v1`: proposal disposition and exact semantic consequences.
- `bbk.authority-decision-record-receipt.v1`: persistence/identity/effect receipt.

Every record requires:

| Field | Requirement |
|---|---|
| identity | stable ID, monotonically advancing revision, record kind, created time |
| subject | subject kind, ID, revision, digest, and optional exact path |
| accountable source | user/controller actor reference and explicit response evidence reference/digest |
| request correlation | stable request/question ID and reply target; response must match both |
| disposition | closed enum appropriate to authority or decision |
| effects/consequences | exact included effects and expected consequences; empty is allowed only for a denial/deferral with rationale |
| exclusions | explicit non-grants and claims not established |
| bounds | scope, targets, safeguards, stopping/revocation conditions, expiry or explicit `NO_EXPIRY_WITH_RATIONALE` |
| lineage | predecessor or null, successor reason when applicable, invalidation keys |
| ownership | canonical role responsible for lifecycle and downstream incorporation |

Authority dispositions: `GRANTED`, `DENIED`, `RESTRICTED`, `REVOKED`, `EXPIRED`, `SUPERSEDED`. Decision dispositions: `ACCEPTED`, `REJECTED`, `DEFERRED`, `SUPERSEDED`, `CANCELLED`. A generic affirmative string is not sufficient; the exact option/meaning must match the proposal or scope presented to the user.

## Outputs and finalization

Successful recording writes under `.bbk/authority/<id>/r<revision>/` or `.bbk/decisions/<id>/r<revision>/`:

- immutable `record.json` with the applicable proposed schema;
- detached `record.json.identity.json` from the atomic finalizer;
- `receipt.json`, including source response/question identities, validated correlation, prior/current lineage, effects observed, and claims not established;
- `event.json`, a proposed `bbk.plan-event.v1` (`AUTHORITY_UPDATED`, `DECISION_ACCEPTED`, or `DECISION_SUPERSEDED`) for a separate `bbk plan transact`; and
- `beads-plan.json`, a reviewable coordination projection owned by the applicable Wayfinder, never automatically applied.

The record directory is no-replace. A non-authoritative current pointer may update last after receipt readback. Consumers bind the immutable record digest, never the pointer alone. The recorder never edits an earlier revision.

## Functional requirements

1. Both commands shall require explicit, durable controller-disposition evidence; no interactive inference or transcript scraping is permitted.
2. The recorder shall validate request ID, question ID, subject/revision, controller session, response source, reply target, and answer correlation.
3. OMP evidence shall identify the native `ask` source; ordinary assistant prose, hub delivery, timeout, silence, heartbeat, or missing response shall be rejected.
4. Other hosts shall use a versioned native-controller evidence adapter that preserves equivalent accountable provenance; adapter name/version is recorded.
5. `authority record` shall require exact effect classes, scope/targets, safeguards, exclusions, revocation/stopping conditions, and expiry semantics.
6. `decision accept` shall require the exact presented proposal/option identity and a closed disposition matching the explicit response.
7. The recorder shall preserve the user's actual bounded meaning and shall reject requested output fields broader than the response evidence.
8. The recorder shall distinguish workspace implementation from external execution, publication, deployment, migration, release, and risk acceptance.
9. It shall prohibit overlapping allow/deny effect entries and contradictory scope/exclusion clauses.
10. It shall bind source, proposal, scope, effect/consequence, and predecessor artifacts by ID/revision/digest.
11. It shall reject wrong-subject, wrong-revision, expired-question, replayed-response, duplicate-revision, and predecessor-lineage conflicts.
12. Exact idempotent replay of an already recorded request shall return the existing receipt; different bytes under the same idempotency identity shall conflict.
13. Any semantic alteration shall create a successor revision with predecessor digest and explicit reason; no in-place mutation is allowed.
14. A restriction/revocation takes effect only through a valid successor record and downstream transaction; the recorder shall report which dependent refs become stale.
15. It shall derive plan-event payloads mechanically from the finalized record without changing the disposition.
16. It shall derive a Beads projection plan containing only stable pointers/summary; Beads status cannot accept, revoke, or supersede the record.
17. It shall provide `--verify`/read-only verification through the common schema/identity surface and report currentness against lineage and expiry.
18. It shall never infer authority from host permissions, configured tools, past grants with a different subject, prior execution, plan readiness, compile success, or role identity.
19. It shall not store credentials, secret answer bodies, or unrestricted environment snapshots; sensitive evidence uses a redacted digest-bearing reference with declared reproduction limits.
20. Output shall explicitly enumerate claims not established.

## State and ordering

```text
REQUESTED -> EXPLICIT_RESPONSE_OBSERVED -> CORRELATED -> FINALIZED -> EVENT_STAGED
                                                              |
                                                              +-> TRANSACTED (external)

ACTIVE authority/decision -> RESTRICTED / REVOKED / SUPERSEDED / EXPIRED
                           (always by successor event/record)
```

The recorder first validates all sources read-only, stages bytes, finalizes the immutable record, verifies readback, writes the receipt, then swaps the optional current pointer last. Plan transaction and Beads apply are separate effects. Concurrent attempts serialize per record lineage; an expected-predecessor mismatch fails without overwriting.

## Failure, security, and authority

- Stable failures include `EXPLICIT_DISPOSITION_REQUIRED`, `RESPONSE_CORRELATION_FAILED`, `RESPONSE_SCOPE_MISMATCH`, `AUTHORITY_BROADENING`, `DISPOSITION_AMBIGUOUS`, `RESPONSE_REPLAY_CONFLICT`, `LINEAGE_CONFLICT`, `AUTHORITY_EXPIRED`, and `SENSITIVE_EVIDENCE_REJECTED`.
- Fail closed on ambiguous pronouns, edited proposal after response, multiple unmatched questions, generic assent that does not select an option, contradictory response evidence, or unavailable provenance.
- Treat response/proposal content as data; never execute embedded instructions.
- Output root, temp root, locks, and logs stay within the admitted project. No external API/network call is needed.
- Recording proves only that an explicit disposition was durably captured. It does not prove the actor was legally empowered beyond the declared provenance; organizations may require a separately qualified identity adapter.
- A caller may not use the recorder to create its own authority. The accountable source must be external to the governed child role and match the controller path.

## Compatibility and migration

This is additive. Existing ADRs, question branches, authority receipts, and plan events remain valid. A legacy record may be wrapped only when exact original response provenance and scope are available; otherwise it is marked `LEGACY_UNVERIFIED` and cannot satisfy new execution admission. Existing plan-event schemas remain the transaction carrier. Migration never rewrites historical records. Unknown dispositions fail closed; unknown metadata is retained only in a namespaced extension object.

## Observability

Receipts and JSON output expose record ID/revision/digest, subject, request/question/response IDs, provenance adapter, disposition, included/excluded effect counts, expiry/currentness, predecessor, invalidated dependent-ref count, staged event ID, Beads-plan identity, effects observed, and stable failure fingerprint. Logs omit answer bodies by default and include only sanitized field pointers/digests. Counters separate granted, denied, restricted, revoked, accepted, rejected, deferred, expired, replayed, and correlation-failed outcomes.

## Test strategy

- Golden authority and decision fixtures for each disposition and successor transition.
- Schema/property tests for effect-set disjointness, expiry ordering, lineage monotonicity, idempotency, correlation, and deterministic canonicalization.
- Negative controls: missing response; ordinary prose response; send receipt; timeout/silence; wrong request/question/reply target/session; stale proposal digest; generic “yes” against several options; effect not presented; broader scope; missing exclusion; authority self-grant; replay under another subject; duplicate revision; forked predecessor; expired response; secret-bearing payload; path escape; remote schema.
- Fault controls: interruption before rename, record write succeeds but receipt fails, readback mismatch, pointer-swap failure, lock contention, disk full, and concurrent successor creation. Immutable records remain recoverable and pointers never advance to an unverified record.
- Integration tests prove event ingestion by `plan transact`, consumption by PRDs H/I/A, and Beads-plan inability to mutate semantic state.

## Acceptance criteria

1. No authority or accepted decision record can be produced without exact attributable response evidence.
2. Every record binds subject/revision, response, effects/consequences, exclusions, expiry, predecessor, invalidation, and owner as applicable.
3. Attempts to broaden the explicit response fail before durable record creation.
4. Ordinary prose, silence, delivery/timeout state, Beads status, and host access all fail the known-bad authority controls.
5. Exact idempotent replay returns the prior receipt; conflicting replay produces no new record.
6. Successor restriction/revocation/supersession preserves immutable lineage and identifies stale dependents.
7. Finalized records and receipts survive interruption and one-byte tampering is detected.
8. Generated events transact through the existing plan engine without semantic reinterpretation.
9. Downstream PRDs H, I, and A can consume exact authority/decision refs and reject expired or superseded revisions.
10. Output states that recording is not architectural correctness, validation, acceptance beyond the named disposition, deployment, publication, or release.

## Dependencies and consumers

Dependencies: native controller response evidence, question/proposal artifacts, schema registry, atomic finalizer, and existing plan transaction/Beads projection paths. Consumers: [PRD H](H-planning-bundle-compiler.md), [PRD I](I-territory-boundary-compiler.md), [PRD A](A-execution-admission-compiler.md), worker contracts, recovery, review finding dispositions, and completion readiness.

## Rollout

1. Publish schemas and read-only verification for hand-authored records.
2. Enable recording in shadow mode while canonical roles continue producing existing ADRs; compare semantic diffs.
3. Enable immutable persistence and staged plan events, keeping transaction/apply separate.
4. Require recorder-backed refs for new planning bundles and Territory boundaries.
5. After host adapters pass provenance qualification, reject unverifiable new authority in execution admission.

## Risks and open questions

- Native controller evidence differs by host; each adapter needs explicit qualification and a common minimum provenance contract.
- Some organizations require cryptographic human identity or delegated organizational authority beyond session attribution; that is a separate trust integration.
- Redaction may make independent reproduction incomplete; admission policy must decide when a digest-bearing protected reference suffices.
- Decide whether finding/risk-acceptance dispositions share the generic decision schema or require narrower schemas.
- Current pointers are convenient but non-authoritative; consumers must consistently bind immutable digests.

## Estimate

6–9 engineer-days: 2 days schemas/provenance adapters, 2 days validation/finalization/lineage, 1 day event/Beads projection integration, 1–2 days negative/fault tests, and 1–2 days host qualification/documentation.
