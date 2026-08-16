# BBK Execution Readiness M1–M6 Operating Plan

Plan ID: `BBK-EXECUTION-READINESS-001-PLAN-r1`  
Status: accepted operating direction, execution-admission package; execution process amended by `BBK-EXECUTION-READINESS-001-EXECUTION-AMENDMENT-001`  
Planning mode: `FAST_CONTINUATION`; architecture mode: `ADOPT_AND_GAP`  
Prepared: 2026-08-16  
Execution stop: after Milestone 6; Milestones 7 and 8 are excluded

## Objective and outcome

Make BBK execution mechanically trustworthy before any campaign cutover: adopt the exact closed artifact-hardening predecessor, make child-spawning Luna roles run on Terra, make Beads mandatory and single-writer, establish deterministic failure diagnosis, separate semantic product identity from every carrier or attempt identity, enforce receipt reuse and bounded recurrence, preserve inner stage results, then prove those rules by replaying the accepted closed campaign and a synthetic failure matrix.

Success is demonstrated only when every applicable blocking assertion in this plan is `PASS` for the exact frozen candidate, repository and user-scoped Codex projections agree, the accepted history is unchanged, Beads projection succeeds through the deterministic BBK CLI, and the M6 checkpoint says execution has stopped. A skipped, stale, wrong-subject, unavailable, or inconclusive assertion is not a pass.

## Exact predecessor baseline

The product predecessor is commit `88e9b028ee9c2191da105530f7cd682a05e8aa58`, version `0.1.0-alpha.17.0.2.1`, title `feat: finalize artifact hardening and qualification tooling`. Commit `c473f81d9778065edcb7a52251d02a68ba29ac8f` is a coordination-only Beads bootstrap overlay and is not a product invalidation key.

The accepted closed-campaign report is `.bbk/execution/ARTIFACT-HARDENING-001/POSTMORTEM.md`, 13,598 bytes, SHA-256 `e95a60f7b8d49bd32e01dd77d3fcf6980311778c052529587d8c081565f63f13`. The selected S24 package inputs are:

| Object | Exact identity |
|---|---|
| sealed package descriptor | `.../sealed/CAND-AH-R13-RELEASE-S24/bbk-package.json`; 123,891 bytes; `01ce80dc1c6400e19ce97d3d12a2b958f5c48b64f6e65a732dafed8a74e8e0c0` |
| candidate record | `.../sealed/CAND-AH-R13-RELEASE-S24/candidate.json`; 22,522 bytes; `18ee094b081f62b18a5700fa57ff1d13535bb4b02b3c38522e75e367bff58ab4` |
| package manifest | `.../sealed/CAND-AH-R13-RELEASE-S24/PACKAGE-MANIFEST.json`; 212,697 bytes; `e17181c6f298648844a33e3c7729ef53dbdbed03488814dcefd7bbd5a4886312` |
| publication receipt | `.bbk/artifacts/publications/bbk-artifact-hardening-candidate-24.json`; 1,346 bytes; `50fbd8210861f0d3669d2a543772cfe1071ea79cf3e0675e72a6453e439fff51` |
| publication subject | revision 24; content `25730ecc42b0e4a852f7d2495d5ae506069ac1a77ef3ae2b2e81b6e18a89f687`; manifest `82e817ac9ed892917ab1a584da4fefdfd134f9398f439d7165ea6390a8b8d588` |

The `.bbk/execution/ARTIFACT-HARDENING-001` tree is ignored and mutable ambient state. M1 must therefore freeze a selected, path-and-hash-bound replay corpus manifest before M6. The postmortem reports a final A3 handoff, but no exact final A3 carrier was found. Replay must preserve this as `SOURCE_REPORT_ONLY / EXACT_CARRIER_NOT_ESTABLISHED`; it must not invent or infer bytes.

## Authority, decision posture, and exclusions

The controlling user accepted this direction and authorized `WORKSPACE_IMPLEMENTATION` in this repository plus `EXTERNAL_EXECUTION` only for its user-scoped Codex BBK installation, routine reversible decisions, local packaging, and deterministic validation. No remote publication, deployment, service, account, credential, network, or release effect is authorized. Repository work, user installation, and canonical Beads mutation are serialized at their respective mutation boundaries.

Routine schema layout, helper boundaries, compatible naming, test fixture structure, sequencing within a milestone, and recovery within the accepted local effect envelope are delegated. Only a change to actor-visible outcome, protected floors, external effect class, or identity meaning requires a new architectural branch. Compatible interface refinement, local tooling repair, carrier repair, evidence completion, and deterministic recovery stay in the current semantic WorkUnit. Milestone order is fixed. Milestone notifications do not pause execution.

### Durable deviations and overrides

1. Beads is mandatory for every substantive semantic object and invocation, despite installed skill text that calls it optional. Beads stays non-authoritative; projection failure blocks at the next safe coordination boundary.
2. Direct Python initially failed `bbk doctor` because the qualified `PYTHONPATH` was absent. Preserve the failed bootstrap observation. The deterministic correction is the ordered path `D:\Projects\BBK\repos\bbk;D:\Projects\BBK\repos\bbk\tools;C:\Users\Tombstone\.cache\bbk\tooling\jsonschema-4.25.1\Lib\site-packages`, with `BBK_QUALIFIED_PYTHONPATH` and `PYTHONPATH` equal, `PYTHONNOUSERSITE=1`, `PYTHONDONTWRITEBYTECODE=1`, and `C:\Python313\python.exe -B -X utf8`. Do not improvise a wrapper.
3. The campaign implements through M6 only. Campaign-bound readiness cutover and CODESYS adaptation remain deferred even if technically reachable.
4. The architecture specialist requested a separate pre-acceptance Reviewer. That request is rejected for this already user-accepted direction. Amendment 001 also supersedes mandatory review of every recurrence: deterministic method, environment, carrier, path, schema, serialization, finalization, projection, or launch failure is recorded and recovered in the same semantic WorkUnit when effects are reconciled. Review is reserved for semantic product ambiguity, contradictory acceptance evidence, an unresolved external-effect ambiguity, or a genuine cross-boundary authority conflict.
5. The user-scoped Codex update formerly required by M2 is moved to M6. M2 establishes repository candidate correctness and installability; M6 performs the one final official updater after all M3-M5 product changes and final candidate assurance.
6. The campaign operates under one accepted M1-M6 local execution envelope. New Root Wayfinder baselines or Territory boundaries are not created for same-scope mechanical recovery, new physical attempts, carrier publication, or evidence completion. The controller records those as attempt-local incidents and continues under the current semantic WorkUnit.

## Stable interfaces and ownership

| Interface | Provider and consumers | Contract |
|---|---|---|
| `IF-ER-01 EffectiveRouteResolution` | routing policy/compiler → Codex projections and dispatch | derive the set from Luna route plus non-empty spawn authority; resolve `bbk_prototyper`, `bbk_territory_orchestrator`, and `bbk_worker_orchestrator` to `gpt-5.6-terra`; preserve reasoning and spawn edges; never silently fall back |
| `IF-ER-02 DeterministicControlCommand` | operation registry/CLI → controllers/orchestrators | version-bound typed operation, subject, authority, environment, outputs, diagnostics, and invalidation keys; reject unregistered/ad-hoc mechanisms before effect |
| `IF-ER-03 SerializedCoordinationMutation` | BBK CLI → `.bbk` and mise-managed Beads | one project-scoped writer, expected revision, idempotency, exact receipt; BBK semantic truth remains canonical |
| `IF-ER-04 TypedIdentityGraph` | identity kernel → artifact/evidence/handoff/runner consumers | typed nodes and dependency edges; no identity-kind substitution; dependent-only invalidation |
| `IF-ER-05 VerificationReceiptPrecheck` | evidence kernel → runners/validators | unchanged declared keys and current exact PASS require `REUSED_RECEIPT`, `execution_count=0` |
| `IF-ER-06 StageExecutionReceipt` | stage runner → aggregate/evidence consumers | immutable inner outcome plus independent runner/finalizer outcomes; outer failure cannot erase or promote inner PASS |
| `IF-ER-07 DiagnosticEscalationTrigger` | classifier/recurrence guard → diagnostic Reviewer route | normalized recurrence and immediate-stop classes fence broad work and emit one bounded read-only review request |

Canonical policy and schemas live under `spec/`; generators and checked-in CLI operations under `tools/`; projections under their existing generated roots; tests own only `tests/`; documentation owns `docs/`, root guidance, and shared skill text. `.bbk` holds canonical campaign coordination and evidence; `.beads` is a non-authoritative projection mutated only by `python tools\bbk.py --json beads ...`, whose adapter invokes the pinned Beads executable through mise. User installation is mutated only by `python tools\update_codex.py --scope user --verify --json` after an exact candidate passes its milestone gate.

No Worker may write another WorkUnit's owned paths. Generated projections are never hand-edited. Historical `.bbk/execution/ARTIFACT-HARDENING-001/**`, sealed S24 bytes, publications, and current pointers are read-only. A sealed candidate is immutable; product-byte repair creates a successor, while a carrier-only repair creates only a carrier successor.

## Deterministic tool registry policy

Controllers and orchestrators may use only (a) version-bound qualified checked-in operations registered by stable operation ID or (b) qualified host-native primitives explicitly listed for read-only inspection and process control. They may not create or run hand-written shell, Python, PowerShell, JavaScript, `eval`, wrapper, or ledger mechanisms. Each registered operation declares implementation revision, subjects, effects, authority class, arguments, output/receipt schema, diagnostics, environment, idempotency, invalidation keys, and recovery. A missing operation becomes one bounded tooling Worker WorkUnit. Operation qualification is evidence, not authority.

The execution baseline uses `C:\Python313\python.exe -B -X utf8`, the released repository `tools\bbk.py`, the qualified Python path above, and mise-managed Beads. Runtime admission must record actual versions and paths. Python 3.11 evidence is required only where available; its absence is a typed environment limitation, never a fabricated pass.

## Identity and retry state machine

The typed identity graph has nine non-substitutable kinds: `PRODUCT_PAYLOAD`, `COMPLETE_PACKAGE`, `CARRIER`, `METHOD`, `ENVIRONMENT_OR_MIRROR`, `ASSURANCE_ATTEMPT`, `EVIDENCE_BUNDLE`, `PUBLICATION`, and `HANDOFF`. Product payload is derived only from selected outcome-bearing bytes and selection policy. Existing `contentSha256` retains its existing complete-package meaning and is not reinterpreted. Every relation records source kind, target kind, relation, exact digest/revision, and invalidation behavior.

The stage lifecycle is `PLANNED → RUNNING → INNER_RECORDED → FINALIZING → COMPLETE`. Failure substates are `LOCAL_MECHANICAL_FAILED`, `OUTER_FAILED_WITH_INNER`, `REPAIR_ADMITTED`, `DIAGNOSTIC_REVIEW_REQUIRED`, and `BLOCKED`. `INNER_RECORDED` is immutable. Overall PASS requires inner PASS and every required outer stage PASS. A physical-attempt or carrier failure does not create a new planning baseline or semantic WorkUnit.

Every evidenced non-success is durably recorded. Clear local reversible failures are repaired within the same semantic WorkUnit, with a new physical ordinal only when the method actually executes again. If the receipt key is unchanged, the inner result is reused. The normalized recurrence fingerprint includes logical subject scope, assertion/operation, deterministic failure class and stable code, method revision, and material environment class; it excludes timestamps, absolute/temp paths, free-form formatting, physical attempt IDs, and carrier IDs. A deterministic classifier may disposition method, environment, carrier, path, schema, serialization, finalization, projection, and launch failures without a Reviewer after effect reconciliation. Broad work stops immediately only for wrong subject with possible effect, contradictory acceptance evidence, integrity or unowned write, ambiguous irreversible effect, or cross-boundary authority impact. Recurrence alone does not force replanning or review.

## Receipt reuse and handoff semantics

A deterministic validation/review receipt remains current while its exact subject and declared invalidation keys are unchanged. Matching current PASS means return `REUSED_RECEIPT` and do not execute the underlying method. A changed key reruns only the directly dependent stage. Missing, corrupt, ambiguous, stale, wrong-subject, or incomplete receipts are not reusable. Planning, coordination, Beads, carrier, locator, publication, or handoff-only changes do not invalidate unrelated product checks.

Stage receipts contain the immutable inner assertion result and separate launch, runner, serialization, finalization, and aggregate states. Inner PASS survives an outer failure as evidence, while the aggregate remains non-PASS. Handoff embeds only evidence whose cutoff precedes sealing. Handoff verification and freshness receipts are always external to the sealed handoff and cannot be self-included.

## Work graph

Routine Worker contracts are generated mechanically from the exact WorkUnit, authority, owned paths, qualified Python profile, output carrier, checks, checkpoint, cleanup, and `bbk.worker-return.v2`. One Worker may own the complete coherent milestone slice when its mutation surface is serialized. Independent candidate-bound validation is required for the integrated M5 candidate and final M6 candidate; M3 and M4 close on deterministic focused gates and are revalidated together at M5. All Beads mutations and artifact/handoff writers are serialized.

### M1 — adopt predecessor and freeze replay inputs

Definition of done: product and coordination baselines are separately bound; S24/postmortem identities pass; selected replay files are in a tracked, hash-bound manifest; missing A3 carrier is recorded as unknown; no historical byte changes.

| WorkUnit | Purpose and owned mutation | Depends on | Completion evidence |
|---|---|---|---|
| `WU-ER-01-01-BASELINE-BIND` | create baseline/adoption records under `.bbk/planning/...` only | none | exact commit/S24/postmortem comparison and lineage receipt |
| `WU-ER-01-02-CORPUS-FREEZE` | add tracked `tests/fixtures/execution-readiness/history-corpus.json`; references, does not copy, selected history | 01-01 | manifest schema/hash check, pre/post history inventory |
| `WU-ER-01-03-M1-VALIDATE` | grouped check-only Validator and checkpoint | 01-02 | `ER-M1-001`, `ER-M1-002` PASS; Beads bindings current |

### M2 — Terra routing, mandatory Beads, repo and installed projections

Definition of done: exactly the three currently Luna-routed Codex roles with spawn authority route to Terra, reasoning and spawn graph are unchanged, all mandatory-Beads source text and projections agree, single-writer/mise behavior is proven, repo projections pass, and the M2 repository candidate passes grouped assurance. User-scoped installation is deferred to the single final M6 updater.

| WorkUnit | Purpose and canonical ownership | Depends on | Completion evidence |
|---|---|---|---|
| `WU-ER-02-01-ROUTING-POLICY` | routing policy and role-source semantics; derive applicable roles, no duplicate allowlist | M1 | exact route diff and unchanged-edge comparison |
| `WU-ER-02-02-BEADS-POLICY` | canonical mandatory-Beads/single-writer directives, method content, checked-in adapter policy | M1 | direct-write negative tests; mise path/version receipt; failure containment |
| `WU-ER-02-03-PROJECTIONS-TESTS` | regenerate repo/Codex projections and focused routing/Beads/bootstrap tests | 02-01, 02-02 | projection congruence, direct-Python fail/correct/pass lineage |
| `WU-ER-02-04-M2-VALIDATE` | freeze M2 candidate; grouped independent Validator | 02-03 | `ER-M2-001..003` PASS; exact candidate identity |
| `WU-ER-02-05-USER-INSTALL` | superseded by Amendment 001; retain all attempts as diagnostic evidence and defer the official updater to M6 | 02-04 | `DEFERRED_TO_M6`; no M2 installation effect required |

### M3 — canonical diagnostics and deterministic operations

Definition of done: one canonical source projects failure-diagnostic and deterministic-tool rules without drift; typed diagnostics distinguish semantic result from mechanical envelope; all immediate-stop classes and static-versus-dynamic limits behave as specified; unregistered mechanisms fail before effects.

| WorkUnit | Purpose and owned mutation | Depends on | Completion evidence |
|---|---|---|---|
| `WU-ER-03-01-CONTRACTS` | schemas for diagnostic, operation registry, and command-attempt receipts; schema registry | M2 | schema positive/negative corpus |
| `WU-ER-03-02-TOOLS-DIRECTIVES` | canonical prompt directives, registry, qualified CLI operations, generated consumers | 03-01 | consumer coverage/digest report; unregistered-operation rejection |
| `WU-ER-03-03-M3-VALIDATE` | focused behavior tests, grouped Validator, checkpoint | 03-02 | `ER-M3-001..003` PASS; zero unowned effects |

### M4 — typed identity enforcement

Definition of done: all nine identities are typed and separately validated; compatibility preserves existing package identity meaning; carrier/method/attempt changes do not create product successors; product changes do; ambiguous substitution and zero-payload successors fail closed; handoff cutoff/external verification are enforced.

| WorkUnit | Purpose and owned mutation | Depends on | Completion evidence |
|---|---|---|---|
| `WU-ER-04-01-IDENTITY-SCHEMA` | additive `bbk.identity-graph.v1` schema, relations, compatibility contract | M3 | schema and legacy fixture validation |
| `WU-ER-04-02-IDENTITY-ENFORCEMENT` | artifact/evidence/handoff identity derivation and dependency-local invalidation | 04-01 | metamorphic transition matrix and negative substitution fixtures |
| `WU-ER-04-03-M4-VALIDATE` | grouped independent Validator and checkpoint | 04-02 | `ER-M4-001..004` PASS; no historical mutation |

### M5 — receipt economy, recurrence guard, and layered stage receipts

Definition of done: unchanged exact PASS receipts are mechanically reused with zero invocation; changed keys rerun only dependents; recurrence normalization is stable across volatile fields; second recurrence and immediate-stop classes fence execution; stage receipts preserve inner results across outer failure.

| WorkUnit | Purpose and owned mutation | Depends on | Completion evidence |
|---|---|---|---|
| `WU-ER-05-01-RECEIPT-PRECHECK` | verification key, currentness, reuse and targeted invalidation kernel | M4 | invocation-count and invalidation matrix |
| `WU-ER-05-02-RECURRENCE-GUARD` | normalized fingerprint, two-occurrence guard, diagnostic route | 05-01 | property tests, two receipts, stop receipt, zero third invocation |
| `WU-ER-05-03-STAGE-RECEIPTS` | stage/aggregate/command-attempt schemas and runner integrations | 05-01 | inner/outer truth table, fault/interruption fixtures |
| `WU-ER-05-04-M5-VALIDATE` | integrate 05-02/03, grouped Validator, checkpoint | 05-02, 05-03 | `ER-M5-001..004` PASS; exact integrated identity |

### M6 — history replay, synthetic matrix, final local qualification

Definition of done: the frozen closed-history oracle and every synthetic case produce the expected typed result; history and S24 remain byte-identical; all M1–M6 assertions pass non-averaging; final package/handoff verify locally; repo and user installation projections agree after a final official updater refresh; M6 checkpoint stops execution.

| WorkUnit | Purpose and owned mutation | Depends on | Completion evidence |
|---|---|---|---|
| `WU-ER-06-01-REPLAY-ORACLE` | tracked replay oracle and synthetic matrix fixtures only | M5 | exact input hash admission and complete expected-result table |
| `WU-ER-06-02-STAGE-REPLAY` | read-only replay through repository runner; attempt evidence only | 06-01 | per-case/stage receipts, no-write inventory, reuse ledger |
| `WU-ER-06-03-INTEGRATED-VALIDATE` | freeze candidate; final grouped independent Validator; standard/release gates once | 06-02 | all blocking assertions PASS, no unexplained skip, current freshness |
| `WU-ER-06-04-FINALIZE-STOP` | local package/handoff, final official user updater refresh/verify, final checkpoint and milestone notice | 06-03 | sealed/verified local evidence, installed parity, cleanup/resume=`STOP_M6_COMPLETE` |

Safe parallelism is limited to non-overlapping owned paths after stable interfaces: M2 routing and Beads policy may run in parallel; M5 recurrence and runner work may run in parallel after the receipt precheck interface freezes. Every integration, Beads mutation, installation, candidate freeze, package publication, and milestone checkpoint is serialized. M1→M2→M3→M4→M5→M6 is mandatory.

## Schema, tool, projection, and test changes

Planned additive schemas include `bbk.diagnostic.v1`, `bbk.deterministic-operation-registry.v1`, `bbk.coordination-transaction.v1`, `bbk.identity-graph.v1`, `bbk.stage-receipt.v1`, `bbk.run-aggregate.v2`, and `bbk.command-attempt.v2`. Register them in the canonical schema registry and preserve v1 compatibility where existing consumers require it. Checked-in tools add only the smallest qualified operations needed for admission, identity derivation, receipt precheck, recurrence classification, and layered stage finalization; no new service or daemon is introduced.

Regenerate all declared projections from canonical source. Focused tests cover schemas, role routing/spawn edges, user installed-consumer behavior, mise Beads single writer/idempotency/failure, bootstrap diagnosis, operation allow/deny, identity metamorphics, receipt counters, recurrence properties, runner fault injection, replay oracle, and no-write checks. Run broad standard/release qualification once against the final frozen candidate unless a declared implementation/tool/environment invalidation key changes.

## Beads mapping and projection

Project `BBK-EXECUTION-READINESS-001` is bound to Bead `bbk-y3e`. Create one current Beads binding for each capability, phase, and WorkUnit in this graph; attempts reuse the WorkUnit's semantic Bead. Level 0 remains only the minimal project/change binding. Apply through one deterministic command: `python tools\bbk.py --json beads plan --root . --apply` under the qualified environment. Never invoke raw `bd` or `jj`. Persist the preview, apply receipt, and `.bbk/mappings/beads.json`; tracker drift never changes BBK semantic state. An adapter failure is an evidenced non-success and blocks at the next safe coordination boundary after all positively isolated work is checkpointed.

## Replay corpus oracle

| Case | Expected classification and guard |
|---|---|
| `HIST-INCOMPLETE-MIRROR` | `ENVIRONMENT_ADMISSION_FAILURE`; product `NOT_RUN`; does not consume a product attempt or create successor |
| `HIST-STATIC-OVERCLAIM` | `STATIC_INVENTORY_PASS` plus `DYNAMIC_EXECUTION_NOT_ESTABLISHED` |
| `HIST-INNER-PASS-OUTER-FAIL` | inner PASS retained; outer FAIL; aggregate `BLOCKED_TECHNICAL`; no product successor |
| `HIST-S21-ZERO-DELTA` | semantic successor denied as `ZERO_PAYLOAD_SUCCESSOR` |
| `HIST-S22-S24-CANDIDATE-JSON-ONLY` | administrative/carrier delta; product identity unchanged |
| `HIST-HANDOFF-ROOT-FAILURE` | carrier transport failure; preserve prior product/qualification; targeted repair only |
| `HIST-A3-CUTOFF` | accepted report only unless exact carrier appears; valid handoff requires truthful pre-seal cutoff plus external verification/freshness |
| `HIST-UNCHANGED-GATE` | `REUSED_RECEIPT`; `execution_count=0` |
| `HIST-RECURRENT-INFRASTRUCTURE` | second normalized occurrence stops broad work; no product candidate |

Synthetic cases are `WRONG_SUBJECT`, `CONTRADICTORY_EVIDENCE`, `INTEGRITY_FAILURE`, `UNOWNED_WRITE`, `AMBIGUOUS_IRREVERSIBLE_EFFECT`, `CROSS_BOUNDARY_EFFECT`, `ZERO_PAYLOAD_SUCCESSOR`, `INNER_PASS_OUTER_FAIL`, `STATIC_DYNAMIC`, `RECURRENCE_2`, and `PRESEAL_CUTOFF`. Each has one predeclared typed result; any different outcome fails the matrix.

## Assertion and evidence matrix

| Assertion | Blocking claim | Method and evidence | Completing WorkUnit |
|---|---|---|---|
| `ER-M1-001` | exact product/coordination baseline and S24 identity | commit/tree/hash comparison, publication/freshness refs | 01-01 |
| `ER-M1-002` | selected history and criteria frozen without mutation | corpus manifest and pre/post inventory | 01-02 |
| `ER-M2-001` | exact applicable roles route Terra; reasoning/spawns unchanged | policy/projection set comparison and allow/deny fixtures | 02-03 |
| `ER-M2-002` | mandatory Beads uses mise and sole writer, repo/install parity | adapter receipts, direct-write denial, updater verification | 02-05 |
| `ER-M2-003` | bootstrap failure/correction and Beads failures retain truth | failed and successor receipts, effect audit | 02-04 |
| `ER-M3-001` | typed deterministic diagnostic classifier | schema/behavior fixtures | 03-03 |
| `ER-M3-002` | six immediate stops plus contradictory evidence fire before effect | synthetic matrix, zero-effect counters | 03-03 |
| `ER-M3-003` | static inventory never claims dynamic execution | static/dynamic paired fixtures | 03-03 |
| `ER-M4-001` | nine identity kinds and dependency closure remain separate | schema and relation matrix | 04-03 |
| `ER-M4-002` | product successor and zero-payload rules | metamorphic transitions | 04-03 |
| `ER-M4-003` | wrong-subject/integrity/evidence externality fail closed | negative fixtures | 04-03 |
| `ER-M4-004` | pre-seal cutoff and external verification/freshness | handoff fixtures | 04-03 |
| `ER-M5-001` | exact unchanged PASS is reused without invocation | receipt key/counter matrix | 05-04 |
| `ER-M5-002` | invalidation is targeted | changed-key dependency matrix | 05-04 |
| `ER-M5-003` | inner result survives runner/finalizer failure truthfully | layered receipts and truth table | 05-04 |
| `ER-M5-004` | normalized second recurrence stops before third | property/state-machine trace | 05-04 |
| `ER-M6-001` | closed history replay is exact and read-only | hash admission and no-write inventory | 06-02 |
| `ER-M6-002` | every history oracle row matches expected classification | structured comparison | 06-02 |
| `ER-M6-003` | synthetic matrix and integrated candidate pass | one final grouped independent Validator and broad gates | 06-03 |

Independent validation is proportional and non-duplicative. M2's current grouped candidate assurance is reused. M3 and M4 use deterministic focused gates; one grouped independent Validator evaluates their integrated result with M5. M6 receives the final grouped independent candidate validation and broad gates. Reviewer work is not a standing gate and is not required for deterministic mechanical failures with reconciled effects. No Validator or Reviewer accepts or releases the candidate.

## Failure, rollback, recovery, and checkpoint protocol

Before freeze, mechanical schema/canonicalization/path/digest/projection defects are repaired in the same semantic WorkUnit and rerun only their gate. After freeze, product bytes require a product successor; carrier-only bytes require only a carrier successor and never a new planning baseline. Preserve compact failed receipts and findings; do not snapshot the whole repository when an exact path manifest or selected package already proves the subject. User installation changes require an updater-produced rollback reference to the previous verified installation. Delete only attempt-owned disposable temp/cache after evidence capture; never delete historical or sealed records.

Checkpoint at coherent WorkUnit completion, before or after a real external effect, and at milestone completion—not after every mechanical attempt. The deterministic checkpoint records exact completed/current/pending IDs, immutable refs and reusable receipts, owned workspaces/processes, effects, unresolved findings, Beads pointers, cleanup status, and one exact resume command. It is small and directly readable; no synthesis agent is required. Attempt-local incidents append to one ledger instead of creating a new baseline, handoff, or root report. A milestone checkpoint emits a concise controller notification and immediately continues. M6 uses resume command `STOP_M6_COMPLETE` and admits no M7/M8 work.

## Deferred work and final claim limits

`M7-CAMPAIGN-BOUND-READINESS-CUTOVER` is `DEFERRED_UNTIL_FRONTIER`; refine only after M6 is complete and the controller expressly starts cutover. `M8-CODESYS-ADAPTER` is `DEFERRED_UNTIL_FRONTIER`; refine only after M7 acceptance and a separately authorized CODESYS campaign. No live opt-in rollout is part of this plan.

This plan establishes an execution-ready M1–M6 operating baseline after its durable references and Beads projections validate. It does not establish implementation completion, assertion PASS, S24 revalidation, candidate acceptance, publication, deployment, release, or outcome achievement. Exact A3 handoff bytes remain unestablished. Future runtime versions and Python 3.11 availability remain admission facts. The Root Orchestrator is the recommended next root and must consume the accepted baseline, exact authority, graph, and checkpoint without changing their meaning.
