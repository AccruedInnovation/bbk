# Agents, roles, and delegation

BBK separates stable responsibility, reusable procedure, routed context, domain method, and one physical invocation:

```text
role constitution modules
+ role scope, responsibilities, direct-child triggers, and escalation contract
+ selected model-routing profile and host model/effort settings
+ task-kind and language/domain profiles
+ accepted BBK records and explicit context edge
+ exact authority, effects, tools, budget, stopping, and result envelope
= effective agent invocation
```

The canonical source is `spec/roles.json`. Generated Codex, OMP, Claude Code, and generic projections must not be edited directly.

## Modular constitution

Alpha.11.12 replaces one shared constitution copied into every role with five modules:

| Module | Loaded by | Purpose |
|---|---|---|
| `core` | all 19 roles | authority, exact-subject binding, epistemic labels, responsible inference, durable history, and bounded context |
| `planning` | Wayfinders and planning/design specialists | outcome-versus-means, proportionate planning formality, traceability, and non-self-approval |
| `coordination` | every role with canonical children | logical-versus-physical roles, exact child contracts, parent integration ownership, and user-interaction routing |
| `execution` | effectful and execution-contract roles | standing authority, capability zones, checkpoints, candidate identity, and durable handoffs |
| `assurance` | evidence, review, synthesis, and acceptance roles | proportional proof, exposure history, evidence-stage separation, and non-pass dispositions |

Only the six `core` rules are universal. A role receives no planning, coordination, execution, or assurance clause unless that responsibility is material to its work. `tools/create_role_spec.py --check` enforces module coverage and rejects invalid combinations.

The universal core is intentionally small. Removing another core rule would make at least one of authority, exact subject identity, epistemic status, responsible local inference, durable failed-history, or explicit context binding implicit again.

## Complete canonical role contract

Every role now declares these fields independently of host projection:

```text
purpose
constitution modules
scope
responsibilities
direct children
per-child delegation trigger
escalation routes
permitted direct user interaction
prohibitions
procedure skills
mutation authority
return contract
```

This makes four questions answerable from the role itself:

1. What exact responsibility does this role own, and what does it not own?
2. Which child may it invoke, and under what condition is that child actually needed?
3. Which issue is handled locally, returned to the parent, routed to a Wayfinder, or presented to the user?
4. What exact result must return before the parent may integrate, freeze, validate, or report completion?

A role with no children is explicitly prohibited from spawning, impersonating, or silently absorbing another role. It returns adjacent work to its parent.

## Entrypoint versus canonical sub-agents

The top-level `bbk` skill is an entry controller for the primary user-facing session. It selects the appropriate root role and relays decisions, authority requests, blockers, and final results.

Canonical BBK roles do **not** autoload that entry skill. Each generated sub-agent instead receives its own constitution modules, scope, delegation triggers, escalation boundary, focused procedures, and return contract. This avoids repeated entry routing, removes a large irrelevant prompt payload, and prevents a child from promoting itself into another root role.

## Direct-child delegation by host

`spec/roles.json` contains both the exact allowlist and a trigger for every child.

- **OMP:** native `spawns` remains the enforceable allowlist; the prompt also states when each allowed child should be used.
- **Claude Code:** `Agent(...)` restricts the callable child set and the prompt carries the same triggers using installed agent names.
- **Codex and generic:** the prompt carries the exact canonical child set and trigger for each child.
- **Leaf roles:** the prompt states that the role has no child-agent authority.

A child is not invoked merely because it is permitted. The parent delegates only when the child's distinct responsibility is needed and supplies:

```text
exact subject and revision
purpose and desired result
bounded context and declared omissions
authority source and allowed effects
capability zones and writable ownership
tools, profiles, budgets, and payload limits
assurance obligations and independence reason
stopping, continuation, and interruption conditions
structured return envelope
```

Host support for additional agents does not broaden the BBK topology or authority.

## Escalation and user interaction

Only two canonical roles may directly question the user, and only when they are the active user-facing invocation:

- `bbk_root_wayfinder` for initial outcome, posture, private context, authority, protected-floor exceptions, hard-to-reverse commitments, and baseline acceptance;
- `bbk_question_guide` for one material question at a time inside an escalated Grill branch.

Every other role is explicitly non-user-facing. It returns a structured decision, authority, private-context, blocker, or scope request to its invoking parent. If an interactive role is itself running as a child, it also returns the question to the parent rather than opening a second user conversation.

Routine, reversible, conventional, and responsibly inferable choices stay local inside scope. Material outcome, authority, protected-floor, shared-interface, ownership, or hard-to-reverse ambiguity follows the role's declared escalation route.

## Scope and mutation authority

Host write access and BBK authority remain separate:

- Codex roles inherit the parent sandbox, and Claude Code roles receive Edit/Write tools, so every role can persist bounded coordination artifacts when the workspace permits;
- only `bbk_worker` and `bbk_prototyper` have canonical subject-mutation authority;
- a worker may change only its exact work unit, assigned paths, and capability zones;
- planners, orchestrators, reviewers, validators, and designers may create coordination records but may not edit the governed subject to make their own work easier;
- sealed or historical evidence remains immutable.

The role catalogue's `mutates` field is semantic authority, not a sandbox selector.

## Focused procedure loading

Each role now separates its full allowed `skills` set from `autoload_skills`. OMP `autoloadSkills` and Claude Code `skills` contain only the two or three procedures that are routinely necessary for that role. The prompt names the remaining allowed procedures and directs the agent to load one only when its method is material.

Examples:

```text
Root Wayfinder        autoloads wayfinding + context routing
Question Guide        autoloads Grill + context routing
Worker                autoloads execution + durable handoff
Reviewer              autoloads review + review context + handoff
Worker Orchestrator   autoloads execution + context routing + handoff
```

Conditional fit, structure, slicing, state/effect, profile, recovery, evidence, and specialist review procedures remain available without being copied into every invocation. The validator caps native autoload at three skills per role, and regressions cap the resulting preload word budget.

## Language and domain profiles

Profile-aware roles load `bbk-installed-profiles` and `bbk-profile-routing`. They consult the installation-specific registry before material language-, framework-, runtime-, or toolchain-specific work, select the smallest applicable profile, and load only the focused procedures needed for their role and assertion.

Question-only roles remain lean and do not load the registry unless language-specific procedure is actually material. A profile adds method and evidence requirements; it never broadens scope, grants tools or effects, waives assurance, or creates a pass.

## Logical role is not physical invocation

A logical role does not require one dedicated model call:

- several compatible logical roles may share one physical invocation when no authority, return, exposure, or independence boundary is lost;
- one logical role may use several physical invocations for scale or specialization;
- physical separation remains mandatory for properties such as independent validation, non-self-approval, worker/integrator separation, or uncontaminated evidence.

Co-location never erases the logical role's scope, escalation, return contract, or child allowlist.

## Recommendation-first questioning

The ordinary material-decision path remains:

```text
Root or Territory Wayfinder
  → Questioning Wayfinder investigates facts and prepares a recommendation
  → user-facing parent presents it
      ├─ accepted or bounded correction: no Question Guide
      └─ rejected, contested, materially ambiguous, or deeper exploration requested
           → one Question Guide runs the focused Grill
```

The Questioning Wayfinder owns branch continuity and reconciliation. The Question Guide owns only the escalated root-decision conversation and does not absorb sibling decisions or implementation.

## Execution continuity and durable returns

Execution roles preserve standing authority, capability zones, candidate identity, checkpoints, and exact handoffs. Polling timeouts, silence, elapsed time, and absent heartbeats are not interruption evidence. Child continuation should reuse the same logical work and verified checkpoint where the host permits it.

Exact or large results remain in files and return through path, byte count, and SHA-256. A parent verifies the referenced handoff before candidate freeze, integration, validation, or completion reporting.

## Generated metadata and validation

`projections/manifest.json` uses `bbk.projection-manifest.v4`. For each role it records:

```text
constitution modules
scope
direct-child allowlist and trigger map
escalations
user-interaction boundary
skills and mutation authority
model-routing profile and host model/effort settings
generated filenames and source digests
```

The model-facing prompt omits build provenance, catalogue digests, and host projection labels. Those remain in metadata where they are auditable without consuming context.

Run:

```bash
python tools/create_role_spec.py --check
python tools/model_routing.py --check
python tools/generate_agents.py --check
```

The regression suite additionally verifies all 76 projections for required sections, exact delegation triggers, user-facing boundaries, focused constitution modules, valid skill frontmatter, and absence of the entry-controller skill from canonical sub-agents.

## Role-by-role disposition

| Role | Constitution | Scope and delegation result | Escalation result |
|---|---|---|---|
| Root Wayfinder | core, planning, coordination | Owns the complete planning state. Its 11 children now have distinct triggers for territory mapping, decisions, research, prototypes, synthesis, architecture, verification design, worker design, review, executable planning, and execution. | Routes ordinary material decisions through the Questioning Wayfinder; asks the user only within its explicit user-facing boundary; reopens Wayfinding when execution exposes a baseline defect. |
| Territory Wayfinder | core, planning, coordination | Owns one territory and may recursively divide only at real responsibility/containment boundaries. It no longer directly conducts material user questioning. | Sends outcome, shared-interface, cross-territory ownership, or standing-authority conflicts to the Root Wayfinder. |
| Questioning Wayfinder | core, planning, coordination | Owns one decision cluster and the recommendation-first path. It uses Researcher for facts and Question Guide only after rejection, contest, material ambiguity, assumption conflict, or explicit deeper exploration. | Returns recommendations and decisions through the user-facing parent; keeps branch ownership while a Question Guide is active. |
| Planning Wayfinder | core, planning, coordination | Owns the executable work graph from accepted decisions. Uses Phase Wayfinder for coherent increments, Verification Designer for claims, Worker Designer for invocations, and Reviewer for independent plan review. | Returns missing governing decisions rather than inventing them; cannot authorize execution. |
| Phase Wayfinder | core, planning, coordination | Owns one accepted phase's decomposition, ownership, integration, checks, and handoffs. | Returns newly exposed governing decisions, cross-phase conflicts, missing authority, or infeasible evidence to the planning parent. |
| Question Guide | core, planning | Owns one escalated root-decision conversation and no sibling work. It has no children. | May ask one user question at a time only when active user-facing Grill; returns factual gaps and sibling decisions to the Questioning Wayfinder. |
| Researcher | core, assurance | Owns one bounded factual question and source/evidence return. It has no children. | Returns inability to reach decision-sufficient evidence, inaccessible required sources, and newly discovered decisions to the parent; never substitutes opinion for missing evidence. |
| Prototyper | core, execution, assurance | Owns one bounded, disposable experiment with a discrimination/falsification criterion and cleanup boundary. It has no children. | Returns architecture/scope/authority changes and prototype limitations to the parent; never promotes a prototype into production. |
| Synthesizer | core, planning, assurance | Owns reconciliation of named source objects, dissent, provenance, and uncertainty. It has no children. | Returns stale, contradictory, missing, or non-comparable inputs as `cannot synthesize yet` instead of manufacturing consensus. |
| Architect | core, planning | Owns a versioned architecture proposal against accepted decisions and interfaces. It has no children. | Returns missing governing choices or stale source decisions to the responsible Wayfinder; proposal does not approve itself. |
| Verification Designer | core, planning, assurance | Owns assertions, evidence methods, stages, independence, and revalidation design. It has no children. | Returns unprovable claims, missing tools, and unresolved acceptance policy to the planning parent; does not waive an assertion. |
| Worker Designer | core, planning, execution | Owns compilation of a least-privilege worker invocation with profiles, tools, authority, capability zones, payload limits, continuation, and handoff. It has no children. | Returns missing work-unit inputs or requests for broader authority/new permanent roles to the responsible planning parent. |
| Reviewer | core, assurance | Owns one exact charter, subject, context, assertion set, and independence reason. It has no children. | Returns findings and coverage gaps to the parent and requests a new charter rather than silently broadening scope. |
| Root Orchestrator | core, coordination, execution, assurance | Owns global execution coordination, dependencies, integration, evidence readiness, and completion reporting. Uses Territory Orchestrator for admitted territory execution and Reviewer for global/cross-territory review. | Stops affected work for material baseline changes and routes them back to Wayfinding; final status goes to the user-facing parent. |
| Territory Orchestrator | core, coordination, execution, assurance | Owns execution and recovery for one territory. Uses Worker Orchestrator for candidate-producing cohorts, Validator Orchestrator for frozen-candidate assurance, and Reviewer for independent cross-cutting questions. | Returns cross-territory, interface, authority, or repeated-repair problems to the Root Orchestrator. |
| Worker Orchestrator | core, coordination, execution, assurance | Owns one worker cohort, isolated workspaces, candidate lifecycle, retries, pre-freeze checks, and exact handoffs. It invokes a Worker only when subject, workspace, ownership, profiles, tools, authority, checks, continuation, and return contract are complete. | Stops on baseline/interface/scope/authority/ownership changes and returns exact blocker state to the Territory Orchestrator. |
| Validator Orchestrator | core, coordination, assurance | Owns one candidate-bound assurance run. Uses Validator for non-overlapping exact assertions and Reviewer for qualitative/cross-cutting independent charters. | Sends repairs to the worker path and governing assertion/waiver decisions upward; never repairs the candidate. |
| Worker | core, execution | Owns one exact work unit and its declared mutation scope. It has no child-agent authority. | Stops and returns outcome, scope, interface, authority, effect, ownership, or recovery-semantic changes to the Worker Orchestrator; records adjacent work instead of doing it. |
| Validator | core, assurance | Owns named assertions against one exact candidate and context. It has no child-agent authority. | Returns identity mismatches, charter ambiguity, tool/authority blockers, findings, and out-of-scope concerns to the Validator Orchestrator; never repairs or waives. |

## Machine checks

`tools/create_role_spec.py --check` rejects:

- missing or unknown constitution modules;
- incomplete scope, delegation, escalation, or user-interaction fields;
- a delegation map that differs from the canonical child list;
- user-interaction permissions on a non-interactive role;
- missing coordination constitution on a parent role;
- missing planning, execution, or assurance modules where required;
- autoloading the top-level entry-controller skill from a canonical role;
- unknown children, unreachable roles, or invalid topology.

The regression suite verifies the corresponding content in all 76 generated projections.
