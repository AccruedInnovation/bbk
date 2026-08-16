# Agents, roles, and delegation

BBK separates stable responsibility, reusable procedure, routed context, domain method, physical invocation, and host transport:

```text
canonical role contract
+ selected constitution modules and prompt modules
+ one or more role-specific mandatory procedures
+ task-kind and language/domain profiles
+ exact invocation context, authority, effects, capability zones, and stopping conditions
+ direct per-role host model/effort route
+ exact role-return schema
= effective agent invocation
```

## Canonical split-role package

The canonical source is `bbk.roles.v4`:

```text
spec/roles/catalog.json             package metadata, deterministic role order, topology, controller roots, schemas
spec/roles/bbk_*-role.json          19 independently maintained canonical role definitions
spec/roles.json                     generated compatibility projection; do not edit
```

`tools/assemble_roles.py` validates the split package and regenerates `spec/roles.json`. `tools/create_role_spec.py` is a compatibility wrapper around the same assembler. Generated Codex, OMP, Pi, Claude Code, and generic projections must not be edited directly.

The catalogue owns:

    - the six controller-selectable roots (`bbk_root_wayfinder`, `bbk_root_orchestrator`, `bbk_reviewer`, `bbk_validator_orchestrator`, `bbk_worker`, and `bbk_validator`);
- every allowed parent and invocation mode;
- all direct-child edges and expected child-return modes;
- the roles allowed to originate a structured human request;
- the five constitution modules;
- prompt-module and return-contract package bindings;
- deterministic source ordering and compatibility-projection paths.

The assembler rejects undeclared or one-sided edges, parent-mode drift, return-mode drift, unintended cycles, unreachable roles, controller-root drift, human-originator drift, noncanonical serialization, uncatalogued role files, and generated projection drift.


## Prompt composition and return contracts

A role prompt is compiled from four layers: canonical role contract, selected reusable prompt modules, role-specific mandatory procedures, and host projection instructions. Shared behavior is maintained once under `spec/prompt-modules/`; role-specific algorithms remain in `spec/method-content.json`, which currently indexes 40 shared skills. There is no fixed mandatory-procedure count. An additional mandatory procedure requires a measured catalogue exception proving distinct behavior and zero duplicated module bodies.

Every canonical role returns `bbk.role-return.v2` with an exact role-specific result schema; `bbk.role-return.v1` remains read-compatible during migration. Operational dispositions describe the physical attempt; semantic states describe readiness for the parent. Neither successful tool access nor operational `COMPLETE` grants acceptance, candidate freeze, validation admission, or release authority.

## Interaction topology

The **harness-root controller** is the sole user-facing BBK identity. It classifies the request and selects one canonical root:

| Route | Canonical root | Typical entry condition |
|---|---|---|
| Planning | `bbk_root_wayfinder` | planning, design, decisions, uncertainty reduction, or operating-baseline preparation |
| Execution | `bbk_root_orchestrator` | accepted baseline plus sufficient authority for execution, integration, or recovery |
| Review | `bbk_reviewer` | exact bounded independent review charter |
| Assurance | `bbk_validator_orchestrator` | exact candidate and assertion-scoped assurance campaign |
| Direct implementation | `bbk_worker` | one exact bounded implementation or repair WorkUnit |
| Direct assertion | `bbk_validator` | one grouped candidate-bound assertion evaluation |

This is a deliberate multi-root graph. The six accepted roots cover the routine direct Worker/Validator path as well as escalated planning, execution, review, and assurance; not every role descends from `bbk_root_wayfinder`.

Every canonical `bbk_*` role remains non-user-facing, including roles whose names contain `root`, `guide`, `orchestrator`, `reviewer`, or `validator`. A child never asks the user directly, calls a human-interaction surface, seizes terminal focus, or infers consent from silence or transport state.

Only the roles declared as human-request originators may construct a controller request. They send a stable request ID, exact subject and revision, request kind, smallest question, recommendation, credible alternatives, consequences, blocker state, independently continuable work, expiry or invalidation conditions, durable packet reference when needed, and exact reply target. The controller asks the user and relays the authority-bound answer to the exact waiting role.

In OMP, live child communication uses `hub`/IRC to the peer whose `kind` is `main`, normally `Main`. Use exact peer IDs from the roster and `replyTo` where available. A send receipt, timeout, silence, or missing heartbeat is non-evidence. Large or authority-bearing material remains in a durable handoff with path, bytes, and SHA-256.

Codex, Pi, Claude Code, and other capable hosts use their native parent/child channels for the same logical packet. When live relay is unavailable, a child returns the typed request through the invocation chain as `BLOCKED_DECISION`, `BLOCKED_AUTHORITY`, or the applicable private-context state.

## Role contract

Every canonical role independently declares:

```text
purpose and family
constitution modules
scope and responsibilities
direct children and per-child delegation trigger
escalations and human-decision triggers
prohibitions
full skills, primary skill, mandatory procedures, and prompt modules
mutation authority
allowed parent modes and expected child returns
exact machine-valid return contract
```

A role with no children is explicitly prohibited from spawning, impersonating, or silently absorbing another responsibility. It returns adjacent work to its parent.

`bbk_prototyper` is intentionally not a leaf. It is a bounded experimental coordinator that may invoke only `bbk_worker_designer` and `bbk_worker` under a fixed experiment charter. It retains hypothesis, evaluation, apparatus integration, run-validity, interpretation, cleanup, and parent-return ownership. Workers invoked by a Prototyper cannot delegate.

## Direct-child delegation

The canonical role files contain each role's `spawns` list and per-child trigger; the catalogue carries the matching parent-mode and expected-return edge. An allowlist is not an instruction to invoke every permitted role.

- **OMP:** native `spawns` is the enforceable direct-child allowlist. For batch `task`, each task's `agent` is the exact permitted `bbk_*` role, `name` is a stable logical job identity, and `task` is the complete self-contained assignment.
- **Codex:** generated child names and delegation instructions mirror the same canonical edge set.
- **Pi:** generated agent definitions carry the same canonical delegation triggers and return contract; the host controls the physical child surface.
- **Claude Code:** native `Agent(...)` permissions match the exact direct-child allowlist.
- **Generic:** the prompt carries the same triggers but the host must enforce its own physical child capability.

Every physical child invocation binds the sole user-facing controller, invoking parent peer, logical parent role, exact reply target, branch or decision identity, subject/revision, authority, effects, capability zones, assurance, stopping conditions, and return schema. Parent ownership of child validation and integration remains explicit.

## Constitution and reusable prompt modules

The five constitution modules remain:

| Module | Loaded by | Purpose |
|---|---|---|
| `core` | all roles | authority, exact-subject binding, epistemic labels, responsible inference, durable history, bounded context |
| `planning` | Wayfinders and design/planning specialists | outcome-versus-means, proportionate planning, traceability, non-self-approval |
| `coordination` | roles with canonical children | logical/physical separation, exact child contracts, parent integration, controller relay |
| `execution` | effectful and execution-contract roles | standing authority, capability zones, checkpoints, candidate identity, durable handoffs |
| `assurance` | evidence, review, synthesis, and acceptance roles | proportional proof, exposure history, stage separation, non-pass dispositions |

The current package has 43 reusable `bbk.prompt-module.v1` modules under `spec/prompt-modules/`. They carry materially identical behavior—role boundary, invocation binding, human relay, delegation/return, durable handoffs, state-claim truth, workspace/external authority and exact completion vocabulary, profile qualification, liveness/recovery, effects/cleanup, evidence lineage and receipts, finding lifecycle, candidate integrity, execution autonomy, user-attention threshold, planning-to-execution ownership, node-bound evidence, specialist-return disposition, and related concerns—without duplicating the body in every procedure.

Prompt modules carry guidance and protocol contracts. Deterministic code, not prompt text alone, checks schema, binding, candidate, receipt, finding, and gate state where BBK exposes an exact checker.

Each selected module is embedded once in a compiled role prompt. A primary procedure references the already embedded module instead of restating it.

## Mandatory procedure injection

Every current role has one primary mandatory procedure because shared behavior has been factored into prompt modules. One is not a fixed maximum.

Additional mandatory procedures are allowed when `spec/roles/catalog.json` contains a source-bound exception that identifies the exact ordered procedures, proves the distinct behavior supplied by each, binds current method-content digests and measured compact-body sizes, and contains no duplicated prompt-module body. Unmeasured, stale, incomplete, or duplicative exceptions fail validation.

Optional focused procedures and language/domain profiles remain available on demand. Correct baseline behavior does not depend on host skill-discovery or autoload behavior.

## Return contracts

Every role returns `bbk.role-return.v2` with a closed role-specific result schema. The OMP `yield` boundary validates the full document before parent acceptance; `bbk_return_template` and `bbk_return_prepare` are the routine construction path, while existing v1/v2 documents remain consume-compatible outside the OMP producer boundary; governed OMP production requires an immutable prepared record. The common envelope separates physical-attempt disposition from semantic readiness and requires:

- exact subject, parent, attempt, role, and invocation mode;
- return kind and current operational disposition;
- role-specific semantic-state name and value;
- summary and exact result payload;
- authority and effects actually used;
- durable handoff references;
- smallest valid next action.

Current operational dispositions are:

```text
COMPLETE
PARTIAL
BLOCKED_TECHNICAL
BLOCKED_AUTHORITY
BLOCKED_DECISION
PAUSED_CAPACITY
PAUSED_HOST_WINDOW
CANCELLED
INCONCLUSIVE
```

`READY_FOR_VALIDATION`, `BLOCKED`, and `PAUSED` are consume-only legacy `bbk.handoff.v1` values. Candidate admission, parent integration, orchestrator integration, planning readiness, and similar meanings live in the role-specific semantic state rather than masquerading as operational completion.

`tools/return_contracts.py` generates 19 full result schemas, 19 compact result schemas, 19 v1 and 19 v2 complete return schemas, and digest-bound return registries. `tools/role_return_runtime.py` validates tool requests, generated templates, prepared records, validation/admission receipts, and yielded role returns against the recursive schema registry and the active invocation binding.

## Planning and specialist ownership

Planning Wayfinder owns graph-level identification, semantic commissioning, integration, coverage, and readiness. Phase Wayfinder owns the equivalent phase-local responsibilities plus detailed phase decomposition and mutation/integration obligations.

Verification Designer owns exact assertion and evidence-method design. Worker Designer owns exact executable Worker invocation-contract design. Wayfinders may identify the need, commission the specialist, validate the returned contract, integrate it, and decide readiness; they may not silently author, modify, repair, or approve the specialist contract they commissioned.

Reviewer owns bounded qualitative or interpretive judgment under an exact charter. Validator owns exact candidate/assertion/method evaluation. Missing assertions, criteria, methods, evidence requirements, or revalidation design return to Verification Designer.

## OMP prompt boundary

Main receives a complete controller system-prompt replacement while persistent BBK mode is active. A marked BBK child receives a complete role-specific replacement after the extension authenticates the installed canonical projection. Compatibility-discovered `.codex`, `.claude`, `.gemini`, and other unrelated workflow instructions are excluded unless explicitly supplied as governed project data.

OMP may resume or wake a session without invoking another ordinary `before_agent_start` replacement. BBK therefore also guards the actual outgoing provider payload in `before_provider_request`. It verifies exactly one session-bound canonical BBK system surface, repairs recognized OpenAI/DeepSeek, OpenAI Responses, Anthropic, Google, direct-message-array, `systemPrompt`, and one-level nested payload shapes, or blocks an unsupported/unrepairable BBK request. Blocking calls the host abort control and substitutes a payload containing no user request content. Ordinary non-BBK OMP requests pass through unchanged.

Digest-only `bbk.effective-prompt-receipt.v2` entries record every `VERIFIED`, `REPAIRED`, and `BLOCKED` provider request; raw prompt and provider payload content are not persisted. `/bbk:prompt-status` reports counts, current guarantee, unresolved failures, and the exact extension-order boundary. OMP has no post-chain finalizer, so a later extension handler can still rewrite the payload after BBK's hook; BBK reports but cannot eliminate that host-owned boundary.

OMP markers remain model-visible because the runtime uses them for prompt authentication. Codex does not need this mechanism, so its `developer_instructions` use ordinary Markdown and contain no BBK XML-like build/provenance envelopes.

## Scope, sandbox, and mutation authority

Host workspace capability and BBK authority are separate.

`WORKSPACE_IMPLEMENTATION` permits requested source, scripts, configuration, tests, documentation, and packages to be produced and locally checked inside the exact authorized workspace. `EXTERNAL_EXECUTION` separately covers real-host or remote-system installation, connection, credentials, provisioning, deployment, service/firewall/network mutation, publication, release, and migration. `PRODUCE_ONLY` grants the first and withholds the second; it is not a stop-before-writing mode.

Use only independently established completion claims: `PLANNING_COMPLETE`, `IMPLEMENTATION_ARTIFACTS_COMPLETE`, `BYTE_INTEGRITY_VERIFIED`, `SEMANTIC_REVIEW_COMPLETE`, `DEPLOYMENT_AUTHORIZED`, `DEPLOYMENT_PERFORMED`, and `LIVE_ACCEPTANCE_VERIFIED`.

Codex custom agents inherit the parent session's sandbox and approval policy; role projections do not silently broaden or narrow it. Claude Code projections similarly permit bounded coordination artifacts when the host workspace allows them. A read-only parent remains read-only.

Workspace access permits coordination artifacts such as plans, ADRs, handoffs, manifests, evidence records, findings, dispositions, and result packets. It does not authorize mutation of subject or product artifacts.

Only `bbk_worker` and `bbk_prototyper` may modify subject or product artifacts, and only inside the exact grant, ownership boundary, allowed effects, capability zones, and cleanup obligations of their invocation. Prototyper may also integrate bounded experimental apparatus produced by its permitted Workers. Every other role returns implementation needs to a permitted mutating role through its parent.

## Execution contracts

`TerritoryExecutionBoundary` binds exact territory and WorkUnit membership, mutation ownership, interfaces and shared state, allowed effects, resource budgets, assurance, local discovery, recovery, invalidation, completion, and successor behavior. Root Orchestrator compiles and admits it; Territory Orchestrator operates within it. Semantic changes require a successor boundary.

Local discovery is deny-by-default. Territory Orchestrator is the sole issuer and owner of a discovery envelope and permit. A valid permit is bound to an exact cohort charter/revision/digest and cannot alter outcomes, scope, requirements, architecture, canonical interfaces, assertion meaning, authority, territory boundaries, toolchain policy, or validation meaning.

Candidate production and candidate assurance are separate lifecycles linked by immutable candidate identity. `WorkerValidationBatch` is retired and has no active runtime meaning.

## Language and domain profiles

The placeholder `bbk-installed-profiles` skill is package-source text. During installation it is replaced with a compact registry generated from the exact verified profile set. The full inventory is written to `effective-language-profiles.json` and bound into the install manifest.

Preferred discovery is:

```bash
bbk --json profile list
```

The generated registry also records the exact `python tools/bbk.py` fallback, so a missing launcher in `PATH` does not by itself make profile discovery unavailable.

## Logical role is not physical invocation

A logical role boundary preserves ownership, authority, context, return semantics, and assurance even if a host co-locates work in one process or model. Conversely, a physical child call does not create a new logical role unless the canonical parent/child contract establishes it.

Model selection affects execution defaults, not role authority. The exact per-role routes live in `spec/model-routing.json` and generated host fields; responsibility remains in the role package.

## Generated metadata and checks

`projections/manifest.json` uses `bbk.projection-manifest.v10`. It externalizes role identity, host filenames, exact model routes, constitution and prompt-module selections, primary and mandatory procedures, mutability, topology, exact return contracts, source paths, and digests without requiring that provenance text to be repeated in every model-facing prompt.

Run:

```bash
python tools/assemble_roles.py --check
python tools/return_contracts.py --check
python tools/create_method_content.py --check
python tools/create_procedure_registry.py --check
python tools/prompt_modules.py --check-size-report
python tools/generate_role_capabilities.py --check
python tools/model_routing.py --check
python tools/generate_agents.py --check
python tools/prompt_lint.py --check
```

Any drift is a source or generation failure, not permission to edit a projection manually.
