# Blueprint Bootstrap Kit

**Version:** `0.1.0-alpha.11.11`  
**Status:** package-qualified temporary method harness; live host, model, profile-toolchain, and target-project behavior remain separately qualified

BBK is a lightweight, Blueprint-inspired planning, execution, evidence, and review kit for Codex, Oh My Pi (OMP), Claude Code, and generic agent harnesses. It is external to the real Blueprint product and carries no official Blueprint lifecycle, capability, authorization, readiness, execution, verification, completion, qualification, or release authority.

Alpha.11.11 is the current canonical successor. It preserves the complete role, Wayfinding, execution, assurance, model-routing, and language-profile contracts while making the extracted package root the direct Git repository source. The public documentation set is consolidated and current-facing; historical PRDs, per-alpha migration notes, internal alignment audits, and release-specific qualification evidence are distributed separately instead of cluttering `docs/`.

## BBK entrypoint

Invoking BBK enters the role system rather than merely exposing method text to an otherwise unbound parent agent.

When the baseline `bbk` skill is loaded in a primary non-OMP session, the current agent acts as the **BBK entry controller** and routes planning, accepted execution, bounded review, or assertion-scoped acceptance to the corresponding named BBK role. Where named agents are supported, the entry controller invokes the selected agent instead of imitating it, so the configured model, effort, skills, tools, spawn policy, and return contract apply.

### Persistent OMP mode

OMP provides a persistent BBK mode:

```text
/bbk                 enter BBK mode without starting an agent turn
/bbk <request>       enter BBK mode and submit the first directive
/bbk:exit            exit BBK mode and return to normal OMP prompting
/bbk exit            non-colon exit alias
/bbk status          deterministic BBK project status; does not enter the mode
/bbk:status          deterministic BBK project status; does not enter the mode
```

`/bbk` records a small `bbk-mode-state` entry with `appendEntry`; that state is not sent to the model. The extension restores the latest state from the active session branch on session start, resume/switch, branch, and tree navigation. A `BBK` footer indicator is shown while the mode is active.

Before every ordinary agent turn in the active session, the extension's `before_agent_start` handler appends a concise `<bbk-session-mode>` system-prompt overlay. The overlay tells the parent to interpret the message as part of the ongoing BBK-governed workflow, preserve current project state, and route work through the appropriate named BBK role:

```text
planning, design, material uncertainty, or no accepted executable baseline
  → bbk_root_wayfinder

execution or recovery of an accepted, sufficiently specified baseline
  → bbk_root_orchestrator

bounded independent review
  → bbk_reviewer

assertion-scoped acceptance run
  → bbk_validator_orchestrator
```

The full baseline skill and routing JSON are not copied into the conversation transcript. `/bbk <request>` forwards only the user's request with `sendUserMessage`; the system-prompt overlay supplies the mode context for that and subsequent ordinary messages. `/bbk` with no arguments and `/bbk:exit` are UI/state operations and do not trigger a model turn.

BBK mode is session-local. It does not change the parent model, thinking level, active tools, or installed sub-agent routes, and it does not replace OMP's native plan or vibe modes. Exit a conflicting native mode separately when its tool or prompt restrictions are not appropriate for BBK work.

In Codex, Claude Code, and generic harnesses, invoke the installed baseline `bbk` skill. The non-OMP entry-controller contract remains turn-scoped unless the host provides its own persistent-mode mechanism.

## Wayfinding, recommendations, and Grill

Ordinary material decisions do not automatically create a Question Guide:

```text
Root or Territory Wayfinder
  → Questioning Wayfinder
      → investigate discoverable facts
      → prepare a decision-ready recommendation
  → user-facing parent presents it
      ├─ accepted → record the decision; no Question Guide
      ├─ bounded correction → revise the recommendation
      └─ rejected, contested, materially ambiguous, or deeper exploration requested
           → one Question Guide conducts the deep Grill
```

`bbk-wayfind` restores the recursive map → frontier → dispatch → receive → invalidate → reassess → synthesize loop, including posture, blockers, fog, interface obligations, proportional pressure tests, and economic stopping. `bbk-grill` supplies the escalation-only probe → reflect → challenge → update → converge loop. Rejecting one recommendation keeps the root question active; it does not disposition the underlying decision. See `docs/WAYFINDING-AND-GRILL.md`.

The canonical topology now reaches all 19 roles from `bbk_root_wayfinder`, including:

```text
Root/Territory Wayfinder → Planning Wayfinder → Phase Wayfinder
```

Territory Wayfinders do not ask material user questions directly. Planning and Phase Wayfinders return missing outcome, interface, architecture, authority, risk-acceptance, or verification decisions to the responsible Wayfinder instead of inventing them.

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


## Discoverable schema validation and profile CLI

```powershell
python tools\bbk.py schema status
python tools\bbk.py schema validate --schema schema.json --instance candidate.json
```

When `python-jsonschema` is missing, the validator reports `BLOCKED` with an exact `--ensure` remediation; it does not silently access the network. The installation-specific `bbk-installed-profiles` skill now records both the preferred launcher path and the exact Python/script fallback, so a missing `bbk` entry in `PATH` or a mise shell does not by itself make profile discovery unavailable. The familiar discovery form remains `bbk --json profile list`.

## Model routing

Model selection is separate from stable role responsibility:

```text
spec/roles.json            role responsibility, authority, skills, and direct children
spec/model-routing.json    model/effort profiles and role-to-profile allocation
```

The packaged defaults are:

| Profile | OMP | Codex | Claude Code |
|---|---|---|---|
| `judgment` | `openai-codex/gpt-5.6-sol`, `thinkingLevel: high` | `gpt-5.6-sol`, `model_reasoning_effort: high` | `opus`, `effort: high` |
| `coordination` | `deepseek/deepseek-v4-pro`, `thinkingLevel: high` | `gpt-5.6-terra`, `model_reasoning_effort: medium` | `sonnet`, `effort: medium` |
| `mechanical` | `deepseek/deepseek-v4-flash`, `thinkingLevel: high` | `gpt-5.6-luna`, `model_reasoning_effort: low` | `haiku`, `effort: low` |

High-judgment planning, architecture, synthesis, assurance, review, and root orchestration use `judgment`; research, prototyping, and bounded execution coordination use `coordination`; tightly bounded leaf workers and exact validators use `mechanical`. A parent or user should override or escalate an assignment whose uncertainty, consequence, or breadth exceeds its default tier.

Validate the packaged policy and projections:

```bash
python tools/model_routing.py --check
python tools/generate_agents.py --check
```

To customize without modifying the qualified package, copy `spec/model-routing.json` outside the extracted release and pass it at installation:

```powershell
Copy-Item .\spec\model-routing.json D:\Projects\BBK\my-model-routing.json
python tools/model_routing.py --path D:\Projects\BBK\my-model-routing.json --check
python tools/install.py install --scope user --omp --codex --claude `
  --model-routing D:\Projects\BBK\my-model-routing.json --dry-run
python tools/install.py install --scope user --omp --codex --claude `
  --model-routing D:\Projects\BBK\my-model-routing.json
```

The installer validates the complete policy before writing, renders selected projections in memory, copies the active policy to `effective-model-routing.json`, and binds its digest into the installation manifest. See `docs/MODEL-ROUTING.md`.

### OMP runtime routing menu

After installing the OMP target, run:

```text
/bbk:models
```

Use `testing-flash` to send all 19 BBK sub-agents through DeepSeek V4 Flash for inexpensive functional testing, `deepseek-economy` for a DeepSeek-only cost-conscious route, `default` for the packaged tiered route, or `installation-default` to restore the exact install-time policy. The menu can also edit any one sub-agent's `model` and `thinkingLevel`, apply a reusable profile file based on `templates/omp-model-routing-profile.json`, and export the BBK-managed route. Changes affect future OMP sub-agent spawns and remain manifest-aware for status and uninstall.

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

The mode state is persisted with `appendEntry`, which OMP does not send to the LLM. When BBK mode is active, `before_agent_start` adds only the concise system-prompt overlay for the current turn. `/bbk <request>` is the sole slash-command path that deliberately calls `sendUserMessage`, and it forwards only the user's directive. `/bbk` with no arguments, `/bbk:exit`, `/bbk status`, and all other deterministic commands remain non-agent-facing.

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

## Product-neutral roles, modular constitutions, and explicit delegation

Reusable role instructions do not inject Blueprint, Tenex, Otobotto, Autospec, capability-partition, host-projection, routing-digest, or build-provenance text into unrelated project work.

Every canonical role now declares its own scope, focused constitution modules, exact direct-child triggers, escalation routes, user-interaction boundary, procedures, prohibitions, and return contract. Only six universal `core` rules are repeated. Planning, coordination, execution, and assurance clauses are included only where that responsibility applies.

The top-level `bbk` skill is an entry controller for the primary user-facing session and is no longer autoloaded by canonical sub-agents. Children receive their own complete role contract instead of entry-routing text. Each role also separates its full allowed procedures from a two- or three-skill always-loaded core; conditional procedures remain available on demand.

OMP keeps native `spawns` as the exact child allowlist **and** now tells the model when each allowed child is appropriate. Codex, Claude Code, and generic projections carry the same trigger map; Claude's `Agent(...)` allowlist matches it. Leaf roles explicitly return adjacent work to their parent rather than spawning, impersonating, or silently absorbing another responsibility.

Only `bbk_root_wayfinder` and an active `bbk_question_guide` may question the user directly. All other roles return structured decision, authority, private-context, blocker, or scope requests to the invoking parent. See `docs/AGENTS.md`.

Generated prompt bodies begin with operational content. Role identity, host filenames, model profile, host routes, constitution selection, scope, delegation topology and triggers, escalations, user boundary, skills, mutability, and source digests remain available in native host metadata and `projections/manifest.json` (`bbk.projection-manifest.v4`) instead of consuming build-provenance tokens. Generic installations also write `.agents/bbk/agent-manifest.json`.

### Host workspace permissions versus BBK authority

Codex projections deliberately omit a role-level `sandbox_mode`, and Claude Code projections no longer deny Edit/Write to non-mutating roles. Every role can therefore persist bounded coordination artifacts such as notes, handoffs, plans, ADRs, manifests, evidence records, findings, dispositions, and result packets when the host workspace permits it.

Inherited workspace write access is not subject-mutation authority. Only `bbk_worker` and `bbk_prototyper` may change subject or product artifacts, and only inside their explicit invocation scope and allowed effects. Other roles may write coordination artifacts but must return implementation work to the parent or an explicitly permitted mutating role. A user- or organization-selected read-only parent session still remains read-only.

## Bundled language profiles

BBK includes the independently manifested `0.1.0-alpha.3` CODESYS, Go, Python, Rust, and TypeScript/JavaScript profile packages. All five install by default; use `--no-language-profiles` for core-only installation or repeated `--profile-id` options for a subset.

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

Supported operations remain `state-effect`, `state-effect-inventory`, `state-effect-review`, `review-context`, `review-lens`, and `evidence-adapter`. Alpha.7 declarations without the typed protocol remain `legacy-declared` and are not invoked automatically. Alpha.8-aware alpha.3 profiles remain compatible when their exact package and runtime compatibility checks pass.

## Package layout

```text
bundled-language-profiles/          verified five-profile release bundle
spec/roles.json                     canonical role catalogue and direct-child topology
spec/model-routing.json             default model/effort policy
spec/method-content.json            canonical skills and references
spec/schemas/                       30 BBK schemas
shared/skills/                      harness-neutral skills
shared/references/                  method modules
projections/*/agents/               generated Codex, OMP, Claude, and generic agents
projections/manifest.json           externalized role/routing/projection metadata
omp/extension/                      OMP tools, commands, and /bbk entrypoint
tools/bootstrap.py                  preferred test/install front door
tools/setup.py                      bootstrap modes and aliases
tools/update_omp.py                 selective OMP-only updater
tools/update_codex.py               selective Codex-agent-only updater
tools/verify_all.py                 ordered full verification pipeline
tools/run_tests.py                  PowerShell-safe tests and final summaries
tools/profile_install.py            ZIP and expanded-repository profile validation
tools/profile_registry.py           install-bound compact profile registry
tools/install_profiles.py           bundled/alternate profile convenience wrapper
tools/install.py                    unified preflight/install/status/uninstall
tools/bbk.py                        deterministic BBK CLI
fixtures/                           semantic, schema, profile, and compatibility fixtures
templates/                          BBK artifact templates
tests/                              consolidated responsibility-oriented suites
```

## Verify and install

Run every package check in canonical order:

```bash
python tools/run_tests.py --all --require-node
```

Run only unittest modules, with `[current/total]` suite status, completion timing, a `still running` heartbeat after 15 quiet seconds, and the final aggregate failure/error summary:

```bash
python tools/run_tests.py -v
```

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


See `docs/README.md`, `docs/INSTALL.md`, `docs/USAGE.md`, `docs/LANGUAGE-PROFILES.md`, and `docs/DEVELOPMENT.md`.

## Boundaries

BBK package qualification proves deterministic package content and the tested method and installer mechanics. It does not prove live model availability or competence, acceptance of a model/effort value by a particular host release, physical role separation, context isolation, external profile toolchains, target-project correctness, or official Blueprint/Tenex authority. Model routing and installed profiles add procedures and execution defaults; they do not grant effects, approval, evidence sufficiency, or release authority.

See `docs/BOUNDARIES.md` and `docs/MODEL-ROUTING.md`.
