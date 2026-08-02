# Blueprint Bootstrap Kit

**Version:** `0.1.0-alpha.13.1`
**Status:** package-qualified temporary method harness; live host, model, profile-toolchain, and target-project behavior remain separately qualified

BBK is a lightweight, Blueprint-inspired planning, execution, evidence, and review kit for Codex, Oh My Pi (OMP), Claude Code, and generic agent harnesses. It is external to the real Blueprint product and carries no official Blueprint lifecycle, capability, authorization, readiness, execution, verification, completion, qualification, or release authority.

Alpha.13.1 preserves the alpha.13 role and contract architecture while correcting release verification and test performance. Alpha.13 makes the 19 individual role files the canonical role source, formalizes the four controller-selectable roots and parent-admission modes, publishes exact machine-valid role-return and execution contracts, and compiles shared behavior through 21 reusable prompt modules. It preserves complete OMP prompt replacement, `hub`/IRC communication, live worker/context display, `ask`-backed decisions, bounded verification, harness-scoped updates, and the five bundled language profiles. Its default per-role model routes are the reviewed selections in `spec/model-routing.json`, not broad judgment tiers.

## BBK entrypoint

Invoking BBK enters a governed role topology rather than exposing method text to an otherwise unbound parent agent.

The **harness-root controller** is the only user-facing BBK identity. It classifies the request, invokes one named canonical root, supervises the active workflow, relays material human requests, and presents results. It does not imitate a Wayfinder, Orchestrator, Worker, Reviewer, Validator, Architect, or Question Guide. Every named `bbk_*` role—including roles whose names contain `root` or `guide`—runs as a child and communicates through the host's parent/child transport.

Mandatory procedures are part of each generated role prompt. A role does not spend a skill-discovery or skill-read call to obtain them, and correct behavior does not depend on optional host autoload semantics. Optional procedures and language/domain profiles remain available on demand.

### Persistent OMP mode and complete prompt replacement

OMP provides a persistent BBK mode:

```text
/bbk                 enter BBK mode without starting an agent turn
/bbk <request>       enter BBK mode and submit the first directive
/bbk:exit            exit BBK mode and return Main to normal OMP prompting
/bbk exit            non-colon exit alias
/bbk status          deterministic BBK project status; does not enter the mode
/bbk:status          deterministic BBK project status; does not enter the mode
```

`/bbk` records a compact `bbk-mode-state` entry with `appendEntry`; that state is not sent to the model. The extension restores the latest state from the active session branch on session start, resume/switch, branch, and tree navigation.

While BBK mode is active, one compact widget appears directly above the editor. It shows `BBK · ready` while no canonical child is active. While children are running, the same line shows the latest active job name and public progress intent/tool/output, plus current context consumption when OMP publishes `contextTokens` and `contextWindow`; up to three other active workers appear as compact context gauges. The widget is rebuilt from the active session on navigation and clears only when BBK mode exits or the session shuts down. Non-BBK tasks are ignored.

The previous `setStatus`-based standalone `BBK` row has been replaced by this single ready/activity widget. Current OMP interactive extensions do not provide a working public footer-replacement surface, so BBK cannot replace the built-in `pi` brand without modifying OMP itself. Alpha.13 preserves the single BBK-owned line rather than adding both a permanent mode row and a separate activity row.

On each active Main turn, `before_agent_start` performs a **system-prompt replacement**, not an append or overlay. The replacement excludes OMP's generic planning/delegation workflow and compatibility-discovered `.codex`, `.claude`, `.gemini`, or other client-specific instructions. It provides a controller-only contract and injects the complete `bbk` and `bbk-context-routing` skills directly. Main then selects exactly one named root:

```text
planning, design, material uncertainty, or no accepted executable baseline
  → bbk_root_wayfinder

execution or recovery of an accepted, sufficiently specified baseline
  → bbk_root_orchestrator

bounded independent review
  → bbk_reviewer

assertion-scoped candidate acceptance
  → bbk_validator_orchestrator
```

With OMP's advertised batch task schema, Main dispatches even one root as `{ context, tasks: [{ name, agent, task, ... }] }`: `agent` selects the exact canonical `bbk_*` role, `name` is a stable IRC/job identifier, and `task` is the complete self-contained assignment. When only a flat task form is advertised, Main follows that schema and references reusable shared background through a durable `local://` context file.

Each generated OMP BBK child carries a closed `<bbk-agent-system>` marker. The same hook locates only OMP's marker-bearing native child wrapper, authenticates every non-empty role-contract line against the installed canonical projection while tolerating only line-ending, blank-line, and trailing-horizontal-whitespace normalization, and replaces the child's complete incoming system prompt with that canonical contract, inlined mandatory skills, runtime facts, and explicit task-call data such as assigned context, approved plan, isolated worktree, hub peer identity/roster, and caller yield schema. Conflicting generic OMP workflow text and Codex/Claude/Gemini compatibility context are not retained. Any changed, missing, injected, or reordered non-empty instruction fails closed.

OMP's peer whose `kind` is `main`, normally `Main`, is the sole user-facing endpoint. Named BBK agents use `hub`/IRC to coordinate with parents and send a compact `BBK_USER_REQUEST` to Main when a material decision, authority grant, private context, protected-floor exception, hard-to-reverse commitment, or explicit acceptance is required. Main presents the smallest question through OMP's native `ask` tool and relays the structured answer to the exact waiting peer as a matching `BBK_USER_RESPONSE` with `source: omp.ask`, using `replyTo` where available. A question written only in ordinary assistant prose is informational text—not a pending BBK question—and cannot support an ADR. Main never authors the ADR; the responsible canonical role records an ask-backed accepted decision. A send receipt, timeout, silence, or missing heartbeat is never a user response.

Ordinary messages in an active BBK session are handled under the replacement controller prompt. They may steer, correct, cancel, or grant operational authority, but Main must confirm any durable decision through `ask` before a child records it as ADR-compatible authority. `/bbk <request>` forwards only the user's directive with `sendUserMessage`; prompt replacement supplies the controller contract. `/bbk` with no arguments and `/bbk:exit` are UI/state operations and do not trigger a model turn. BBK mode is session-local and does not change the parent model, thinking level, active tools, installed child routes, filesystem containment, or native host capabilities. `/bbk:exit` restores ordinary OMP prompting for subsequent Main turns; named BBK children still receive their role-specific replacement whenever they are invoked.

Codex, Claude Code, and generic hosts use the same topology: the visible parent/controller is the only human channel, canonical children return or message human requests through the invocation chain, and mandatory skills are already embedded in each generated role definition.

## Wayfinding, recommendations, and Grill

Ordinary material decisions do not automatically create a Question Guide:

```text
Root or Territory Wayfinder
  → Questioning Wayfinder
      → investigate discoverable facts
      → prepare a decision-ready recommendation
  → harness-root controller presents it
      ├─ accepted → record the decision; no Question Guide
      ├─ bounded correction → revise the recommendation
      └─ rejected, contested, materially ambiguous, or deeper exploration requested
           → one Question Guide conducts the deep Grill
```

`bbk-wayfind` restores the recursive map → frontier → dispatch → receive → invalidate → reassess → synthesize loop, including posture, blockers, fog, interface obligations, proportional pressure tests, and economic stopping. `bbk-grill` supplies the escalation-only probe → reflect → challenge → update → converge loop. Rejecting one recommendation keeps the root question active; it does not disposition the underlying decision. See `docs/WAYFINDING-AND-GRILL.md`.

The four controller-selectable roots jointly reach all 19 canonical roles. `bbk_root_wayfinder` owns planning and uncertainty reduction; it does not own execution, direct bounded review, or candidate assurance. Planning still includes:

```text
Root/Territory Wayfinder → Planning Wayfinder → Phase Wayfinder
```

Territory Wayfinders do not ask material user questions directly. Planning and Phase Wayfinders identify and commission specialist work, validate and integrate the returns, and decide readiness. Verification Designer owns exact assertion and evidence-method design; Worker Designer owns exact Worker invocation-contract design. A Wayfinder does not silently author, repair, or approve the specialist contract it commissioned.

## Durable material decisions

Ordinary recommendations do not require a Question Guide or a branch file. When a material decision spans turns, research, parking, or deeper Grill work, persist it explicitly:

```powershell
python tools\bbk.py question new --root D:\Project `
  --id Q-PROVIDER-CONTRACT `
  --root-decision "Which provider contract should the Stage 1 harness adopt?"

python tools\bbk.py question validate `
  D:\Project\.bbk\questions\Q-PROVIDER-CONTRACT.json
```

`REJECT` and `REVISE` keep the root question open. `RESOLVED` requires an approved decision. See `docs/WAYFINDING-AND-GRILL.md`.

## Resumable workers and lossless handoffs

BBK treats a host sub-agent turn as one segment of a logical worker lifecycle, not necessarily the entire work unit. New project configuration gives workers an extended logical window, bounded checkpoints, same-thread continuation after infrastructure interruption, and a durable handoff requirement. BBK does not emit an undocumented Codex timeout key.

Exact or large results use an authoritative UTF-8 handoff file with project-relative paths, byte counts, and SHA-256 digests:

```powershell
python tools\bbk.py handoff create --root D:\Project `
  --work-unit WU-EXAMPLE --disposition PARTIAL `
  --summary "Implementation complete; focused validation remains." `
  --artifact out\candidate.json --continuation-state READY `
  --checkpoint .bbk\runtime\checkpoint.json `
  --next-action "Resume the same worker thread and run focused validation."

python tools\bbk.py handoff verify `
  .bbk\handoffs\WU-EXAMPLE\HO-WU-EXAMPLE-1.json --root D:\Project

python tools\bbk.py handoff list --root D:\Project `
  --work-unit WU-EXAMPLE --latest
```

Beads can carry a compact append-only pointer rather than the full payload:

```powershell
python tools\bbk.py beads handoff-plan `
  --root D:\Project --handoff .bbk\handoffs\WU-EXAMPLE\HO-WU-EXAMPLE-1.json `
  --bead bd-123
```

Add `--apply` only after `.bbk/mappings/beads.json` explicitly enables projection and writes. BBK appends a compact pointer with `bd comments add`; it never treats the bead text as the authoritative payload.

The BBK file remains authoritative. Configured gate runs follow the same lossless boundary: JSON receipts expose bounded previews, while complete stdout and stderr are stored beside the receipt and bound by project-relative path, byte count, and SHA-256. A PASS receipt is not reusable if either bound stream is missing or changed. See `docs/DURABLE-HANDOFFS.md`.


## Execution authority and child lifecycle

Execution planning now carries standing user authority as a scoped grant rather than forcing each worker to ask again for effects that were already approved. The grant records its source, exact scope, approved effects, safeguards, exclusions, and expiry. Filesystem access is classified into disposable candidate roots, protected worktrees, and sealed evidence.

Worker and orchestrator returns distinguish technical, authority, and decision blockers from capacity and host-window pauses. A polling timeout, silence, elapsed time, or missing heartbeat is non-evidence. Running children may be interrupted only for an enumerated reason with concrete evidence; completed children are consumed or continued through the host follow-up mechanism rather than interrupted to reclaim capacity.

The existing `bbk manifest` and `bbk candidate` commands are the first-class exact-inventory and candidate-identity operations. See `docs/USAGE.md` for the tested Codex `multi_agent_v2` configuration and the complete interruption policy.


## Canonical role, contract, and prompt packages

Alpha.13 separates canonical sources from generated compatibility surfaces:

```text
spec/roles/catalog.json                 package metadata, roots, parent modes, ordering, topology
spec/roles/bbk_*-role.json              19 canonical role definitions
spec/roles.json                         deterministic generated compatibility projection
spec/contracts/catalog.json             role-return and execution-contract package
spec/contracts/role-return-registry.json generated digest-bound role-return registry
spec/prompt-modules/catalog.json         reusable prompt-module package and compilation policy
spec/prompt-modules/modules/*.json       21 canonical shared behavior modules
spec/method-content.json                 canonical procedure-skill and reference content
```

The controller chooses one root according to consequence: `bbk_root_wayfinder` for planning and uncertainty, `bbk_root_orchestrator` for an accepted executable baseline, `bbk_reviewer` for bounded independent review, or `bbk_validator_orchestrator` for candidate-bound assurance. Parent modes, direct-child edges, expected return modes, and human-request originators are explicit in the role catalogue. Generated Codex, OMP, Claude, and generic agents are projections and must not be edited directly.

Every role return uses `bbk.role-return.v1`: operational attempt state is separate from role-specific semantic readiness. Current operational dispositions are `COMPLETE`, `PARTIAL`, `BLOCKED_TECHNICAL`, `BLOCKED_AUTHORITY`, `BLOCKED_DECISION`, `PAUSED_CAPACITY`, `PAUSED_HOST_WINDOW`, `CANCELLED`, and `INCONCLUSIVE`. `READY_FOR_VALIDATION`, `BLOCKED`, and `PAUSED` are consume-only legacy `bbk.handoff.v1` inputs, not values emitted by current role contracts.

Shared prompt behavior is compiled once from reusable modules, then combined with the exact role contract, one or more genuinely role-specific mandatory procedures, and host-specific transport instructions. Alpha.13 imposes no arbitrary mandatory-procedure maximum. Additional procedures require a source-bound measured exception proving distinct behavior and no duplicated prompt-module bodies.

## Discoverable schema validation and profile CLI

```powershell
python tools\bbk.py schema status
python tools\bbk.py schema validate --schema schema.json --instance candidate.json
```

When `python-jsonschema` is missing, the validator reports `BLOCKED` with process exit code 1 and an exact `--ensure` remediation; this is an expected optional-capability status, and it does not silently access the network. The installation-specific `bbk-installed-profiles` skill now records both the preferred launcher path and the exact Python/script fallback, so a missing `bbk` entry in `PATH` or a mise shell does not by itself make profile discovery unavailable. The familiar discovery form remains `bbk --json profile list`.

## Model routing

Model selection is separate from stable role responsibility:

```text
spec/roles/                         canonical responsibility, authority, topology, and return contracts
spec/model-routing.json             exact OMP, Codex, and Claude route for each canonical role
spec/omp-model-routing-profiles.json OMP runtime profiles generated from the canonical default
```

The canonical policy uses `bbk.model-routing.v2`. Every role has an independent host route. Alpha.13 defaults are the exact reviewed selections from the role-update package; they are not derived from three broad tiers. The repeated route shapes are:

| Reviewed route shape | OMP | Codex | Claude Code | Roles using it |
|---|---|---|---|---|
| High-judgment | `openai-codex/gpt-5.6-sol`, `thinkingLevel: high` | `gpt-5.6-sol`, `model_reasoning_effort: high` | `opus`, `effort: high` | Root Wayfinder, Question Guide, Planning Wayfinder, Phase Wayfinder, Architect, Verification Designer, Worker Designer, Root Orchestrator, Reviewer |
| Medium Wayfinding/synthesis | `openai-codex/gpt-5.6-sol`, `thinkingLevel: medium` | `gpt-5.6-sol`, `model_reasoning_effort: medium` | `opus`, `effort: high` | Territory Wayfinder, Questioning Wayfinder, Synthesizer |
| Empirical bounded work | `deepseek/deepseek-v4-flash`, `thinkingLevel: max` | `gpt-5.6-luna`, `model_reasoning_effort: xhigh` | `sonnet`, `effort: medium` | Researcher, Prototyper |
| Territory execution | `openai-codex/gpt-5.6-luna`, `thinkingLevel: xhigh` | `gpt-5.6-luna`, `model_reasoning_effort: xhigh` | `sonnet`, `effort: medium` | Territory Orchestrator |
| Mechanical coordination | `deepseek/deepseek-v4-flash`, `thinkingLevel: max` | `gpt-5.6-luna`, `model_reasoning_effort: xhigh` | `sonnet`, `effort: medium` | Worker Orchestrator |
| Validation coordination | `openai-codex/gpt-5.6-sol`, `thinkingLevel: medium` | `gpt-5.6-sol`, `model_reasoning_effort: medium` | `sonnet`, `effort: medium` | Validator Orchestrator |
| Mechanical leaf work | `deepseek/deepseek-v4-flash`, `thinkingLevel: max` | `gpt-5.6-luna`, `model_reasoning_effort: xhigh` | `haiku`, `effort: high` | Worker, Validator |

The table groups identical values for readability only. It does not create categories or shared policy objects; each of the 19 role entries remains independently editable. Legacy `bbk.model-routing.v1` policies remain accepted when valid, including caller-defined profile names.

Validate the packaged policy and every generated host projection:

```bash
python tools/model_routing.py --check
python tools/generate_agents.py --check
```

To customize without modifying the qualified package, copy `spec/model-routing.json` outside the extraction, edit exact role entries, retain `package_version: 0.1.0-alpha.13.1`, validate it, and pass it during installation:

```powershell
Copy-Item .\spec\model-routing.json D:\Projects\BBK\my-model-routing.json
python tools/model_routing.py --path D:\Projects\BBK\my-model-routing.json --check
python tools/install.py install --scope user --omp --codex --claude `
  --model-routing D:\Projects\BBK\my-model-routing.json --dry-run
python tools/install.py install --scope user --omp --codex --claude `
  --model-routing D:\Projects\BBK\my-model-routing.json
```

The installer validates exact role coverage before writing, renders selected projections in memory, copies the effective policy to `effective-model-routing.json`, and binds its digest into the install manifest. See `docs/MODEL-ROUTING.md`.

### OMP runtime routing menu

After installing the OMP target, run:

```text
/bbk:models
```

Use `testing-flash` to send all 19 BBK sub-agents through DeepSeek V4 Flash for inexpensive functional testing, `deepseek-economy` for a DeepSeek-only cost-conscious route, `default` for the reviewed packaged per-role route, or `installation-default` to restore the exact install-time policy. The menu can also edit any one sub-agent's `model` and `thinkingLevel`, apply a reusable profile file based on `templates/omp-model-routing-profile.json`, and export the BBK-managed route. Changes affect future OMP sub-agent spawns and remain manifest-aware for status and uninstall.

```text
/bbk:models status
/bbk:models profile testing-flash
/bbk:models profile deepseek-economy
/bbk:models set bbk_worker @task medium
/bbk:models apply D:\Profiles\bbk-routing.json
/bbk:models export D:\Profiles\bbk-current.json current-bbk
```

OMP rediscovers agent definitions when it spawns a task agent, so already-running sub-agents are not changed. BBK writes its managed route into the installed BBK agent frontmatter and updates the BBK install manifest. An OMP `task.agentModelOverrides` entry or a higher-precedence project agent definition with the same role name can still supersede that frontmatter; `/bbk:models status` reports this precedence boundary.


### OMP command/context boundary

OMP slash commands such as `/bbk:models`, `/bbk:status`, `/bbk:doctor`, `/bbk:exit`, and every bundled language-profile command are **UI-only**. They show concise results through `ctx.ui.notify`, return no structured command payload, and do not call `sendMessage` or `sendUserMessage`; deterministic JSON therefore does not enter model context. Explicit LLM-callable tools still return structured results because the model deliberately invoked them.

Mode state is persisted with `appendEntry`, which OMP does not send to the LLM. While BBK mode is active, `before_agent_start` replaces Main's complete system prompt for each ordinary turn and injects the mandatory controller procedures. For named BBK children, the hook replaces OMP's subagent wrapper while preserving only sanitized invocation data required to do and return the assigned work. `/bbk <request>` is the sole slash-command path that deliberately calls `sendUserMessage`, and it forwards only the user's directive. `/bbk` with no arguments, `/bbk:exit`, `/bbk status`, and all other deterministic commands remain non-agent-facing.

### Update only OMP

A running Codex session does not need to be stopped to update BBK's OMP surface:

```powershell
python tools/setup.py --test-and-update-omp --scope user
```

For a faster update after independently verifying the package:

```powershell
python tools/setup.py --update-omp --scope user
```

The updater preserves the active `/bbk:models` route, updates future OMP agents and bundled profile extensions, reconciles the unified install manifest, and does not modify `.codex` agent files. Afterward, run `/reload-plugins` in OMP.

To apply a BBK Codex-agent successor without modifying an existing OMP installation:

```powershell
python tools/setup.py --test-and-update-codex --scope user
```

Or, after independently verifying the extracted release:

```powershell
python tools/setup.py --update-codex --scope user
```

The selective updater preserves the installed package copy, current pointer, launcher, effective model-routing file, OMP runtime state, and other harnesses. It replaces only BBK's 19 Codex custom-agent definitions and reconciles their ownership records in the unified manifest. Start a fresh Codex turn or session if the running host has cached custom-agent definitions.

## Product-neutral roles, modular prompts, and explicit delegation

Reusable role instructions do not inject Blueprint product status, target-project names, routing digests, or build provenance into unrelated work.

The canonical `bbk.roles.v4` package is split across `spec/roles/catalog.json` and 19 `spec/roles/bbk_*-role.json` files. `spec/roles.json` is a deterministic generated compatibility projection. Every role declares its scope, focused constitution modules, exact direct-child triggers, escalation routes, human-decision triggers, procedures, prohibitions, mutation authority, allowed parent modes, prompt modules, and exact return contract.

Prompt compilation has four layers: canonical role contract, reusable prompt modules, role-specific mandatory procedures, and host projection instructions. The package currently contains 21 prompt modules and 39 skills. Every current role has one primary mandatory procedure because common behavior is modularized, not because BBK imposes an arbitrary maximum. Additional mandatory procedures require a measured, source-bound catalogue exception proving distinct behavior and no duplicated module body.

The top-level `bbk` skill belongs to the harness-root controller and is not a child skill. Mandatory procedure bodies are embedded in generated roles, so baseline behavior does not depend on OMP `autoloadSkills`, Claude Code skill autoload, or a separate discovery call. Optional focused procedures and language/domain profiles remain available on demand.

OMP keeps native `spawns` as the exact direct-child allowlist and tells each role when each child is appropriate. Codex, Claude Code, and generic projections carry the same trigger map; Claude's `Agent(...)` allowlist matches it. Leaf roles return adjacent work to their parent. `bbk_prototyper` is intentionally a bounded coordinator rather than a leaf: it may invoke only `bbk_worker_designer` and `bbk_worker` under a fixed experiment charter.

All 19 canonical roles are non-user-facing. Material decision and authority needs travel through the invoking chain to the harness-root controller. In OMP the live transport is `hub`/IRC to the peer whose `kind` is `main`; in Codex and Claude Code the child returns the same structured human-request packet through the parent channel. See `docs/AGENTS.md`.

Every role returns a machine-valid `bbk.role-return.v1` envelope with a closed role-specific result schema. Operational attempt disposition is distinct from semantic readiness. Current operational values are `COMPLETE`, `PARTIAL`, `BLOCKED_TECHNICAL`, `BLOCKED_AUTHORITY`, `BLOCKED_DECISION`, `PAUSED_CAPACITY`, `PAUSED_HOST_WINDOW`, `CANCELLED`, and `INCONCLUSIVE`; legacy `READY_FOR_VALIDATION`, `BLOCKED`, and `PAUSED` are consume-only `bbk.handoff.v1` inputs.

Generated prompt bodies begin with operational content while provenance stays outside the model-facing body. Codex `developer_instructions` contain no BBK XML-like build/provenance tags. OMP retains authenticated markers because its extension verifies canonical child definitions before complete prompt replacement. Role identity, filenames, exact routes, constitution and prompt-module selections, topology, primary/mandatory procedures, return contracts, mutability, and source digests are externalized in `projections/manifest.json` (`bbk.projection-manifest.v8`). Generic installations also write `.agents/bbk/agent-manifest.json`.

### Host workspace permissions versus BBK authority

Codex projections deliberately omit a role-level `sandbox_mode`, and Claude Code projections no longer deny Edit/Write to non-mutating roles. Every role can therefore persist bounded coordination artifacts such as notes, handoffs, plans, ADRs, manifests, evidence records, findings, dispositions, and result packets when the host workspace permits it.

Inherited workspace write access is not subject-mutation authority. Only `bbk_worker` and `bbk_prototyper` may change subject or product artifacts, and only inside their explicit invocation scope and allowed effects. Other roles may write coordination artifacts but must return implementation work to the parent or an explicitly permitted mutating role. A user- or organization-selected read-only parent session still remains read-only.

## Bundled language profiles

BBK includes independently manifested language profiles: CODESYS `0.1.0-alpha.4`, plus Go, Python, Rust, and TypeScript/JavaScript `0.1.0-alpha.3`. All five install by default; use `--no-language-profiles` for core-only installation or repeated `--profile-id` options for a subset.

An explicit `--language-profiles PATH` replaces the bundled source for that invocation. It may identify a profile ZIP, an extracted profile package, a flat set of extracted profiles, a `packages/` repository tree, or a verified aggregate bundle. The separate `bbk-language-profiles` repository is already expanded and can be passed directly:

```powershell
python tools\setup.py --test-and-install `
  --scope user --omp --codex `
  --language-profiles ..\bbk-language-profiles
```

During installation BBK replaces the package placeholder `bbk-installed-profiles` skill with a compact registry generated from the exact verified profile set. The complete machine-readable inventory is written to `effective-language-profiles.json` and bound into `install-manifest.json`.

See `docs/LANGUAGE-PROFILES.md`.

## Repository-native source

The extracted package root is the BBK Git repository tree. No Git-repository extractor or staging script is required. Preserve `.git/` and any intentionally maintained repository-only README, replace the repository contents with the verified package tree, review the diff, and commit.

Release qualification reports, archive audits, test transcripts, and pre-public history are separate release artifacts rather than source-tree documentation. The BBK repository intentionally retains the small bundled profile archives so a clone remains self-contained and the default installer continues to install all profiles.

See `docs/DEVELOPMENT.md` and `docs/UPGRADING.md`.

## Lineage and scope

BBK is Blueprint-inspired but product-neutral. It carries forward explicit authority, bounded context, recommendation-first Wayfinding, escalation-only Grill, durable evidence, non-averaging assurance, and logical-role boundaries without claiming official Blueprint, Tenex, target-project, qualification, or release authority.

Pre-public Blueprint alignment reviews, roadmap mappings, source PRDs, and dogfood fixtures are preserved outside the public source tree. The executable source of truth for current BBK behavior is the canonical specification under `spec/`, generated projections, schemas, tests, and the durable documentation indexed by `docs/README.md`.

## Core method chain

```text
requested intervention
  → desired operational outcome and baseline
  → SolutionOutcomeFit when applicable
  → architecture and ImplementationStructureContract
    → reusable procedure and explicit context edges when applicable
      → StateDecisionEffectDesign when applicable
        → ExecutionSlices and WorkUnits
          → AssuranceContract
            → deterministic gates and exact candidate
              → ReviewManifest and ReviewContextManifest
                → typed profile projections and evidence adapters
                  → ReviewRun, receipts, findings, and dispositions
                    → outcome evidence and learning candidates
```

Routine work may keep most of this inline. Material, consequential, uncertain, stateful, effectful, interface-heavy, recurrent, delegated, or hard-to-reverse work records only the applicable objects and boundaries.

## Language/domain profile protocol

`bbk.profile-capability.v1` remains the core-owned, typed, content-addressed boundary for read-only language/domain procedures:

```text
verified profile package
  → exact content-bound request package
    → read-only profile operation
      → typed result bound to the request digest
        → generic BBK validation, assurance, evidence, and locking
```

Supported operations remain `state-effect`, `state-effect-inventory`, `state-effect-review`, `review-context`, `review-lens`, and `evidence-adapter`. Alpha.7 declarations without the typed protocol remain `legacy-declared` and are not invoked automatically. Alpha.8-aware independently versioned profiles remain compatible when their exact package and runtime compatibility checks pass.

## Package layout

```text
bundled-language-profiles/             verified five-profile release bundle
spec/roles/catalog.json                canonical role-package catalogue
spec/roles/bbk_*-role.json             19 canonical role source files
spec/roles.json                        generated v4 compatibility projection
spec/contracts/                        return/execution contract catalogue and registry
spec/prompt-modules/                   21 reusable prompt modules and compilation policy
spec/model-routing.json                reviewed per-role OMP/Codex/Claude routing policy
spec/method-content.json               canonical skills and references
spec/schemas/                          BBK and role-specific JSON Schemas
shared/skills/                         generated harness-neutral skills
shared/references/                     method modules
projections/*/agents/                  generated Codex, OMP, Claude, and generic agents
projections/manifest.json              v8 role/module/routing/projection metadata
omp/extension/                         OMP tools, commands, and /bbk entrypoint
tools/assemble_roles.py                validates split role package and generates roles.json
tools/return_contracts.py              generates role result/return schemas and registry
tools/generate_agents.py               compiles role, module, procedure, and route projections
tools/bootstrap.py                     preferred test/install front door
tools/setup.py                         bootstrap modes and aliases
tools/update_omp.py                    selective OMP-only updater
tools/update_codex.py                  selective Codex-agent-only updater
tools/verify_all.py                    full, quick, OMP, and Codex verification profiles
tools/run_tests.py                     PowerShell-safe bounded test runner
tools/install.py                       unified preflight/install/status/uninstall
tools/bbk.py                           deterministic BBK CLI
fixtures/                              semantic, schema, profile, and compatibility fixtures
templates/                             BBK artifact templates
tests/                                 consolidated responsibility-oriented suites
```

## Verify and install

Run every package check in canonical order:

```bash
python tools/run_tests.py --all --require-node
```

Run all unittest modules. Independent modules run concurrently by default (up to four workers), while each module retains its own process boundary, capture, timeout, and exact failure report:

```bash
python tools/run_tests.py -v
```

Suite children run with closed stdin, each consolidated module has a 300-second hard timeout by default, and parallel heartbeats name the latest visible test. For a serial Windows portability diagnostic, run `python tools/run_tests.py -v --jobs 1 -p test_installation_portability.py --suite-timeout 300`.

For a cross-cutting developer smoke check rather than release qualification:

```bash
python tools/verify_all.py --profile quick --require-node
```

Ordinary OMP-only and Codex-only successor updates should use the targeted `--test-and-update-omp` or `--test-and-update-codex` commands; they retain package trust and drift checks without rerunning unrelated harness and historical portability suites. Use `--jobs 1` only when serial diagnosis is needed.

Preferred test-then-install command; all five bundled profiles are included automatically:

```bash
python tools/bootstrap.py --test-and-install --scope user --omp --codex --claude
```

Equivalent explicit setup spelling:

```bash
python tools/setup.py --test-and-install --scope user --omp --codex --claude
```

Inspect the complete core-plus-profile plan without creating the installation root or manifest:

```bash
python tools/install.py install --scope user --omp --codex --claude --dry-run
```

The installer verifies every selected profile package, validates a bundled release or expanded repository manifest when present, checks compatibility, generates one complete destination plan, rejects unsafe archives and cross-package collisions, and preflights divergence and backup behavior before the first write. Human-mode runs stream verification as it happens and report profile preparation, preflight file counts, write progress, and manifest completion. Core and profile files share one install manifest, status surface, and conservative uninstall path.

Against an existing multi-harness install, `--omp --uninstall-existing` now clean-replaces only OMP and preserves Codex; `--codex --uninstall-existing` does the inverse. Selecting every installed harness still requests a full clean replacement. Unowned files are preserved, modified owned files require `--force`, and unsupported partial combinations fail before removal. See `docs/INSTALL.md` for the exact scope rules.


See `docs/README.md`, `docs/INSTALL.md`, `docs/USAGE.md`, `docs/LANGUAGE-PROFILES.md`, and `docs/DEVELOPMENT.md`.

## Boundaries

BBK package qualification proves deterministic package content and the tested method and installer mechanics. It does not prove live model availability or competence, acceptance of a model/effort value by a particular host release, physical role separation, context isolation, external profile toolchains, target-project correctness, or official Blueprint/Tenex authority. Model routing and installed profiles add procedures and execution defaults; they do not grant effects, approval, evidence sufficiency, or release authority.

See `docs/BOUNDARIES.md` and `docs/MODEL-ROUTING.md`.
