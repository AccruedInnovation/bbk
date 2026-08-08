# Using BBK

This is the operating guide for BBK `0.1.0-alpha.17.0.2`. Installation and update details are in [`INSTALL.md`](INSTALL.md); role contracts are in [`AGENTS.md`](AGENTS.md); and qualification limits are in [`BOUNDARIES.md`](BOUNDARIES.md).

BBK uses the harness-root session as the sole user-facing controller and exposes four controller-selectable canonical roots. All 19 roles are non-user-facing children compiled from split v4 role sources, 43 prompt modules, exact role-specific procedures, and generated v2 return contracts. Codex, OMP, Pi, Claude Code, and generic projections are generated from the same host-neutral compilation plan; OMP additionally replaces Main and child system prompts so conflicting generic or client-specific instructions cannot govern BBK work.

## Quick start

Use Python 3.11 or newer. Check the Codex dependency set without changing the machine:

```bash
python tools/setup.py --check-dependencies --codex
```

Install any missing BBK dependencies after explicit consent, then test and install Codex:

```bash
python tools/setup.py --install-dependencies --codex
python tools/setup.py --test-and-install --scope user --codex
```

Codex-only installation and verification do not require Node. The root `mise.toml` declares only jj and Beads; the Node pin is isolated in the non-default `tools/omp-runtime.mise.toml`. For OMP, select OMP on both commands so the bootstrap also installs that pinned Node runtime through mise:

```bash
python tools/setup.py --install-dependencies --omp
python tools/setup.py --test-and-install --scope user --omp
```

Use `--pi`, `--claude`, or `--generic` instead of `--codex`, or combine host flags. With no host flag, the installer selects all five projection targets, including OMP and its Node dependency. All bundled language profiles install by default. The dependency script installs BBK's declared system, managed, and Python package dependencies; it does not install the selected agent host or a language-profile toolchain.

For OMP, reload the extension after an update and enter BBK mode:

```text
/reload-plugins
/bbk
```

## Current operating behavior

For continuation work with an accepted outcome and architecture, BBK defaults to `FAST_CONTINUATION` and `ADOPT_AND_GAP`. A coarse whole-project `ROADMAP_READY` state plus one exact `FRONTIER_READY` slice is enough to begin authorized execution. Later slices stay `DEFERRED_UNTIL_FRONTIER` with stable IDs and clear refinement triggers; BBK does not require the full future plan before the first safe slice starts.

Routine work is product-first. Worker dispatch begins as soon as exactly four blocking facts are current: exact work/scope/return route; authority/effect fence; workspace/mutation ownership; and required inputs/toolchain/output carrier/completion checks. Additional support-role work requires a named material risk, unresolved proposition, explanation of why current evidence or a standard template is insufficient, and the smallest bounded resolving action.

Successful deterministic receipts are current until a declared invalidation key changes. Consumers validate and reuse the receipt rather than rerunning the underlying operation across role, process, or session boundaries. Reversible pre-freeze mechanical defects are repaired in the same semantic run and physical attempt, with only the affected mechanical gate rerun. Structured role returns are preferred unless exact durable transport materially requires a sealed handoff package.

Assurance uses `INLINE` by default. Compatible assertions are grouped into one evidence-producing assignment; a broad product validator runs only when an inspected input changed and at most once against the frozen final candidate. `FOCUSED` is used for a named qualitative risk or finding-scoped recheck. Reviewer dispatch without such a risk returns `NO_MATERIAL_ASSURANCE_WORK`.

Authority remains effect-specific. `WORKSPACE_IMPLEMENTATION` covers requested artifact production and local verification inside the authorized workspace; `EXTERNAL_EXECUTION` covers real-host, remote-system, credential, deployment, network, publication, release, and migration effects. `PRODUCE_ONLY` grants workspace implementation while withholding external execution. Completion reports use only independently established claims.

An explicit delivery assignment supplies standing continuation authority for routine frontiers and physical attempts. User attention is reserved for a `MAJOR_BLOCKER` or `ARCHITECTURAL_BRANCH`. While a child owns an active WorkUnit, it alone runs effectful source, package, build, cache, test, simulator, daemon, process, or cleanup commands for that surface. Writable toolchain cache/temp/config/log roots are explicit and worktree-local by default.

Controllers and children receive required procedures from the compiled prompt tail rather than rereading matching `SKILL.md` files. Optional procedures remain model-discoverable only when classified `EXTERNAL_OPTIONAL`; compiler-selectable sources stay package-owned. `tools/prompt_compile.py` supplies additional qualified profile or invocation procedures and preserves unchanged logical-child state across follow-ups.

Git and mise are the global repository-substrate prerequisites. The package `mise.toml` declares `jj@0.43.0` and `github:gastownhall/beads@1.1.0`; normal BBK execution calls both through `mise exec` with automatic installation and network access disabled. A global `jj` or `bd` installation is neither required nor preferred.

Useful deterministic utilities include:

```text
bbk artifact preflight <draft>
bbk artifact finalize --root <project> --package-id <id> --revision <rev> [--source <path> ...]
bbk artifact finalize <draft> --root <project>
bbk artifact freshness <publication-or-current-pointer> --root <project>
bbk artifact seal <draft> --output <sealed>
bbk artifact verify <sealed>
bbk artifact successor <sealed> --output <draft> --revision <rev> --reason <reason>
bbk preflight run <request.json> --root <project> --output <result.json>
bbk context worker --root <project> --work-unit <wu.json> --profile-lock <lock.json> --host-preflight <result.json> --output <package>
bbk context review --root <project> --candidate <candidate-package> --request <request.json> --output <package>
python tools/verification_economy.py pre-check --request <request.json> --receipts <index-or-dir>
python tools/verification_economy.py dispatch --request <request.json>
```

New constructors use sealed packages. `artifact finalize` supports a one-shot software mode over ordinary project files and the existing profile-specific draft mode. It rejects symbolic links, applies deterministic exclusions and optional selectors, writes immutable package content under `.bbk/artifacts/sealed`, and binds the exact selected live source set in an external publication receipt. `artifact freshness` re-verifies the package and source binding. Tool-owned hashes, byte lengths, canonicalization labels, package closure, and receipts should not be reconstructed manually.

When the user explicitly requires `bbk artifact finalize`, a handoff, passing tests, raw implementation directory, or `artifact seal` is not a substitute. A post-finalization source mutation requires local re-verification and successor finalization. This checks local byte consistency only and does not infer semantic review, acceptance, deployment, or live validation.

## Enter BBK

### OMP persistent BBK mode

```text
/bbk                 enter persistent BBK mode without starting a turn
/bbk <request>       enter the mode and submit a first directive
/bbk:exit            exit the mode
/bbk exit            exit alias
/bbk status          deterministic project status; mode is unchanged
/bbk:status          deterministic project status; mode is unchanged
```

`/bbk` persists a session-local `bbk.omp-mode-state.v2` entry with `appendEntry` and does not inject a chat message. The state is restored from the active branch when a session is resumed, switched, branched, or navigated.

Ordinary messages in an active BBK session run under the replacement controller prompt. They may steer, correct, cancel, or grant operating authority, but Main must confirm a durable decision through OMP's native `ask` tool before a child records it as ADR-compatible authority. BBK mode does not change the parent model, thinking level, active tools, installed child routes, filesystem containment, or native host capabilities.

BBK renders one live line immediately above the editor for the full lifetime of active BBK mode. It reads `BBK · ready` when no canonical child is working. Otherwise the newest worker supplies its job name and latest public intent/tool/output; current context consumption is shown as `used/window` plus percentage when OMP publishes those fields, and up to three additional workers receive compact context gauges. The same widget returns to `BBK · ready` when work finishes and is cleared on mode exit. BBK no longer adds a second `setStatus` row. OMP's current public interactive extension API cannot replace the built-in `pi` footer brand, so that host-owned label remains unchanged.

While active, `before_agent_start` performs a complete **system-prompt replacement** for the peer whose `kind` is `main`, normally `Main`. The replacement excludes OMP's generic workflow prompt and compatibility-discovered `.codex`, `.claude`, `.gemini`, and other client-specific context. It injects the mandatory `bbk` and `bbk-context-routing` procedures and establishes Main as a controller/relay that invokes exactly one named root:

```text
no accepted executable baseline, planning, architecture, or material uncertainty
  → bbk_root_wayfinder
accepted sufficiently specified execution/recovery baseline
  → bbk_root_orchestrator
bounded independent review
  → bbk_reviewer
assertion-scoped candidate acceptance
  → bbk_validator_orchestrator
```

With OMP's advertised batch form, dispatch even one root as `{ context, tasks: [{ name, agent, task, ... }] }`. Set `agent` to the exact canonical `bbk_*` role, use `name` only as a stable IRC/job identifier, and put the complete self-contained assignment in `task`. When OMP advertises only the flat form, follow it exactly and put reusable shared background in a durable `local://` context file.

All named `bbk_*` agents are non-user-facing children. Their generated definitions carry a `<bbk-agent-system>` marker and complete inlined `mandatory_skills`. On child start, the same hook verifies the marker-bearing wrapper's role block against the installed canonical projection, replaces the complete incoming prompt, and preserves only explicit task-call context, approved plan/path, worktree, hub identity/roster, and caller yield schema. A child finishes through OMP's hidden `yield` tool with its governed result in `result.data`. In the current release the routine path is `bbk_return_template` → `bbk_return_prepare` → the returned immutable `yield_input`. The `yield` pre-effect hook validates the role-specific schema and active binding identity before the result is accepted; focused JSON-pointer diagnostics support same-attempt repair.

A second `before_provider_request` guard handles wake, resume, ask-return, and other continuation paths that can skip a fresh `before_agent_start`. It inspects and, where necessary, replaces the actual provider-specific payload. Each governed request becomes `VERIFIED`, `REPAIRED`, or `BLOCKED` in `bbk.effective-prompt-receipt.v2`. Unsupported or failed repair calls the host abort control and substitutes a payload containing no user request content. `/bbk:prompt-status [json]` reports counts and unresolved status. This guarantee ends at BBK's handler because later OMP extension handlers can still replace the payload.

Children coordinate through `hub`/IRC. A material human need is sent to Main as a stable `BBK_USER_REQUEST`. Main must use OMP's native `ask` tool for the user-facing question and relay its structured answer to the exact waiting peer as a matching `BBK_USER_RESPONSE` marked `source: omp.ask`, with `replyTo` when available. Anything phrased as a question only in ordinary assistant prose is informational text: it is not pending, cannot be treated as answered, and cannot become ADR authority. The responsible canonical role—not Main—creates the ADR from an ask-backed response. Delivery, timeout, silence, or missing heartbeat is not a response. Continue independent authorized work after sending and wait only when completely blocked.

Task completion is not peer death. A completed child may remain parked in the OMP hub and later be reactivated for follow-up work. `/bbk:agents` reconciles ordered task-lifecycle and coordination evidence: successful `injected`, `woken`, or `revived` receipts, live `hub`/IRC rosters, and legacy `job` running-agent reports can make a completed peer active again. Later lifecycle or roster evidence supersedes older wake evidence; failed receipts do not activate. Role-bearing rosters can discover nested peers without duplicating identities.

Use:

```text
/bbk:agents          complete reconciled tree
/bbk:agents active   active peers plus their ancestors
/bbk:agents json     additive machine-readable status evidence
/bbk:agents details <id-or-name>
/bbk:timing          observational elapsed/user-wait/activity timing
/bbk:timing json     machine-readable timing
```

While OMP's native `ask` tool is open, the agent view reports `WAITING_ON_USER`, observed request IDs, wait start, and independently active work. `/bbk:timing` separates that explicit user-wait interval from session elapsed and reports provider, tool, and sub-agent timing with overlap-aware wall and summed durations. Unattributed elapsed is reported as unknown rather than mislabeled as model compute.

The JSON record distinguishes `task_status`, `peer_status`, `peer_status_current`, `status_source`, and `wake_outcome`. A split text status such as `running · task completed · peer running (woken)` is intentional. This is observability, not cancellation or execution authority, and it can report only wake/roster evidence observed by the current Main session.

`/bbk <request>` sends only the request text through `sendUserMessage`. `/bbk` with no arguments and `/bbk:exit` are local UI/state operations and do not start a model turn. BBK mode does not change the parent model, thinking level, toolset, child model routing, or containment. `/bbk:exit` restores ordinary prompting for subsequent Main turns; named BBK children still receive role-specific replacement whenever invoked.

In persistent BBK mode, task results and IRC messages are event-delivered. Main should continue independent work or use an empty `job`/`irc wait` when blocked. The extension denies specific-job polling and rate-limits successful nonblocking list/inbox/roster probes to one per 300 seconds while children remain active. This prevents short polling loops without treating silence as failure or removing explicit cancellation.

### Codex, Pi, Claude Code, and generic hosts

Invoke the installed baseline `bbk` controller procedure in the visible parent session. That session is the only user-facing endpoint. Invoke a named canonical role where the host supports children so its model, effort, inlined mandatory procedures, tools, spawn policy, and return contract apply. Children return human-decision packets through the parent channel; they never open a separate user interaction. Only when named-agent invocation is genuinely unavailable may the visible session adopt a logical role, and it must preserve the same authority and communication boundaries.

For Codex, choose the parent turn's sandbox and approval policy before delegation. BBK custom agents do not force `read-only`; they inherit that parent setting. Claude Code roles likewise receive Edit/Write so non-mutating roles can persist coordination artifacts. Inherited write access does not authorize subject or product changes: those remain limited to the canonical mutating roles and their exact grants.

### Codex `multi_agent_v2` configuration

For effective orchestration on the Codex build against which this BBK multi-agent path was tested, add the following to `config.toml`:

```toml
[features.multi_agent_v2]
enabled = true
max_concurrent_threads_per_session = 32
max_wait_timeout_ms = 3600000

multi_agent_mode_hint_text = """
Use subagents when explicitly requested or when active project instructions
call for delegation.

Here is the method for using custom sub-agents that we have tested and validated. This example shows how to use a configured custom agent named `test_agent`:

Call `spawn_agent` with:
- task_name: "<a unique underscore safe name>"
- agent_type: "test_agent"
- fork_turns: "none"
- message: "<the delegated task>"

Do not use a full-history fork. This works with both global and project-specific sub-agents so long as their names are underscore_safe. 

A wait_agent timeout is only a parent polling deadline. It has no semantic meaning about the child's health or progress and is never evidence that the child is stalled or eligible for interruption. Parent commentary or polling cadence does not impose a deadline on a child.

Never call interrupt_agent merely because of elapsed time, silence, repeated wait timeouts, lack of intermediate messages, apparent slow progress, or a desire to reclaim a concurrency slot. Do not impose an arbitrary wall-clock deadline on a child unless the user or governing project instructions require one.

A child reported as running must be presumed healthy. Continue waiting, perform non-overlapping work, inspect already-produced artifacts read-only, or send a non-interrupting status request. Silence alone remains non-evidence even after a status request.

Interrupt a running child only when:
1. the user explicitly cancels or supersedes its work;
2. the child explicitly requests termination;
3. concrete tool or process evidence proves an irrecoverable hang or deadlock; elapsed time, silence, and polling timeouts do not qualify as evidence; or
4. continuing would cause a specifically identified correctness, ownership, data-integrity, or safety problem.

A completed, failed, or already-interrupted child must not be interrupted. Consume its result, or use followup_task if additional work is needed.

Before interrupting, state in the parent transcript:
- the permitted interruption reason;
- the concrete evidence;
- why waiting or a non-interrupting message is insufficient; and
- the location and status of any known partial work.

Preserve partial work whenever doing so is safe.
"""
```

This table is version-sensitive and reflects the tested `multi_agent_v2` surface. If an installed Codex build rejects it, use that build's documented multi-agent namespace rather than guessing or silently translating unsupported keys. The BBK role contracts still require the same polling, continuation, and interruption semantics.

## Execution authority, capability zones, and worker returns

Planning records standing user authority once and propagates it through the Root, Territory, and Worker Orchestrators. A child should not ask again for routine temporary package installation, source writing, or disposable-root cleanup already approved inside the exact grant. The grant must still identify its source, scope, safeguards, exclusions, and expiry; host write access alone is not authority.

Effectful work should classify paths as:

- `disposable-candidate-root` — create, expected-hash-guarded replace, rename, and delete inside the exact root;
- `protected-worktree` — mutate only explicitly owned paths;
- `sealed-evidence` — read-only historical or candidate evidence; create successors elsewhere.

Operational returns distinguish `BLOCKED_TECHNICAL`, `BLOCKED_AUTHORITY`, and `BLOCKED_DECISION` from `PAUSED_CAPACITY` and `PAUSED_HOST_WINDOW`. A capacity or host-window pause does not fail the candidate.

Use `bbk manifest create` and `bbk manifest compare` for exact directory inventories. Shipped `EXAMPLE-*` templates are excluded by default; `--include-examples` is the explicit opt-in for a template-oriented manifest or candidate. Use `bbk candidate freeze`, `check`, and `verify` for candidate identity. Use `bbk handoff create`/`verify` for structured, digest-bound returns and `bbk handoff list --latest` for deterministic rediscovery.

## Test and install

Setup-driven verification performs the dependency preflight before tests. Use the profile that matches the host surface:

```bash
# Codex-only; does not require Node
python tools/setup.py --test --codex

# OMP-only; requires Node 22+
python tools/setup.py --test --omp

# Standard cross-host profile; includes OMP and requires Node
python tools/setup.py --test
```

Use the compact contract profile during active development and the exhaustive profile for release qualification:

```bash
python tools/setup.py --test-fast
python tools/setup.py --release-test
```

The direct test-runner forms are intended for diagnosis after the dependency check:

```bash
python tools/run_tests.py --profile fast -v
python tools/run_tests.py --profile standard -v
python tools/run_tests.py --profile release --all --require-node -v
```

`auto` uses a bounded worker pool on Windows and isolated modules on POSIX. Timing reports are stored outside the package. Use `--mode isolated --jobs 1` only for fresh-process diagnosis. `tools/verify_all.py` remains the ordered verification wrapper used by `tools/setup.py`.

For a selective OMP or Codex update, the `--test-and-update-*` commands run the matching trust-gated profile. Direct equivalents remain:

```bash
python tools/verify_all.py --profile omp --require-node
python tools/verify_all.py --profile codex
```

Verify and install only on PASS. With no host flags, all five host projections and all bundled language profiles are selected:

```bash
python tools/setup.py --test-and-install --scope user
```

Select hosts, a language-profile subset, or core only as needed:

```bash
python tools/setup.py --test-and-install --scope user --omp --codex --pi
python tools/setup.py --test-and-install --scope user --codex \
  --profile-id rust --profile-id python
python tools/setup.py --test-and-install --scope user --codex \
  --no-language-profiles
```

`python tools/bootstrap.py --test-and-install ...` remains a compatibility entry point and delegates to the same setup path.

Every selected profile package is authenticated. If a pre-existing profile's exact package digest, layout, harness set, installed bytes, and modes already match, the installer reuses those files instead of rewriting them. Local divergence still follows the normal refusal and `--force` rules.

Use `python tools/install_profiles.py --scope user --omp --codex --claude` for the profile-focused wrapper. Supplying `--language-profiles /path/to/source` replaces the bundled source for that invocation.

See [`INSTALL.md`](INSTALL.md) and [`LANGUAGE-PROFILES.md`](LANGUAGE-PROFILES.md) for the complete boundary.

## Select sub-agent models

The canonical install-time policy is `spec/model-routing.json` with:

```json
{
  "schema_version": "bbk.model-routing.v2"
}
```

It contains one independent OMP, Codex, and Claude Code route for each of the 19 canonical roles. There are no governing `judgment`, `coordination`, or `mechanical` buckets in v2; identical packaged values are duplicated deliberately so one role can be changed without affecting any other role.

Validate it with:

```bash
python tools/model_routing.py --check
python tools/generate_agents.py --check
```

For a customized installation, copy the policy outside the verified package, edit the exact role entries, validate the copy, and pass it to the installer:

```bash
python tools/model_routing.py --path /path/to/model-routing.json --check
python tools/install.py install --scope project --root /path/to/repo \
  --omp --codex --claude --model-routing /path/to/model-routing.json
```

Legacy `bbk.model-routing.v1` policies remain accepted. Their profile names were never limited to the original three: any valid profile name may be defined and referenced by the complete role map. V2 is preferred because direct role entries avoid category coupling.

OMP routes may use configured aliases such as `@default`, `@smol`, `@slow`, `@vision`, `@plan`, `@designer`, `@commit`, `@tiny`, `@task`, and `@advisor`, or direct selectors such as `deepseek/deepseek-v4-flash`. Routing is an execution default, not an authority grant or proof that the selected model is sufficient for every invocation. See `MODEL-ROUTING.md`.

## OMP sub-agent model menu

```text
/bbk:models
```

Choose `testing-flash` for fast low-cost BBK functional tests, `deepseek-economy` for DeepSeek-only routing, `default` for the packaged per-role route, or `installation-default` to return to the exact install-time routes. The menu can set `model` and `thinkingLevel` for any BBK sub-agent, apply an external `omp-model-routing-profile.json`, and export the current BBK-managed routes. Changes apply to future spawns; already-running sub-agents are unaffected.

The menu populates model choices from authenticated OMP models, the packaged profiles, the current route, and OMP's built-in aliases. It warns when OMP cannot currently resolve a selected model but permits saving it for later provider configuration. OMP `task.agentModelOverrides` and higher-precedence project agent definitions can supersede BBK-managed frontmatter; use `/bbk:models status` and inspect OMP configuration when a spawned model differs from the displayed BBK route.

Scriptable forms:

```text
/bbk:models status
/bbk:models project status
/bbk:models user status
/bbk:models project profile testing-flash
/bbk:models user profile default
/bbk:models set bbk_validator @task medium
/bbk:models apply D:\Profiles\bbk-cheap.json
/bbk:models export D:\Profiles\bbk-current.json current-bbk
/bbk:models project create
/bbk:models project status
/bbk:models project repair --dry-run
/bbk:models project repair
```

In a user-scoped session, the menu recommends project-local creation instead of only warning about global effect. Creation clones all 19 current effective user OMP routes and calls the exact bound package installer for an OMP-only project install with language profiles disabled. It does not require Git or `.bbk`, and it verifies that the user routing surface remained byte-identical. Divergent project footprints return `REPAIR_REQUIRED`; repair is dry-run first, backup-aware, explicit, and never falls through to user scope. Reload or restart OMP after creation or repair.

The default `auto` target selects the nearest valid project-scoped OMP installation and otherwise the user-scoped installation. Explicit `project` and `user` prefixes remove ambiguity. An expected but invalid project binding fails closed; it does not fall through to the shared user route. User-scope changes require interactive confirmation and affect future spawns in all projects using that user installation. Project-scope installations retain independent profiles.

Use `/bbk:agents`, `/bbk:agents active`, `/bbk:agents details <id-or-name>`, or `/bbk:agents json` to inspect the complete nested BBK hierarchy. The tree includes synchronous descendants carried in parent task progress, not only directly listed detached agents, and retains bounded terminal history for post-run inspection.

See [`MODEL-ROUTING.md`](MODEL-ROUTING.md) and [`../templates/omp-model-routing-profile.json`](../templates/omp-model-routing-profile.json).

## Start a project

```bash
bbk init --title "Project name"
bbk status
```

`bbk status --root <existing-empty-directory>` is a successful `UNINITIALIZED` result with zero live planning counts and an explicit `bbk init` next action. Initialized-project counts exclude `EXAMPLE-*` templates and report them separately under `examples_available`. The successful result shapes are defined by `spec/schemas/bbk-status-v1.schema.json`.

## Method flow

```text
operational outcome and boundary
  → SolutionOutcomeFit when material
  → implementation structure
      → StateDecisionEffectDesign when applicable
        → execution slices and work units
          → AssuranceContract and profile resolution
            → isolated execution and focused checks
              → exact candidate and deterministic gates
                → ReviewManifest and exact context
                  → profile-specific read-only projections/evidence
                    → attempts, receipts, findings, dispositions
                      → completion or successor repair
```

## User attention, execution autonomy, and example state

Classify unresolved items before asking the user: environment fact, configuration parameter, reversible implementation choice, architectural decision, authority expansion, or user-reserved preference. Inspect, parameterize, safely default, or defer the first three whenever that remains responsible. Batch coherent material requests and return one correlated response packet.

After an accepted baseline and current authority are bound, proceed through routine plan-detail corrections, local sequencing changes, reversible implementation choices, ordinary repairs, compatible substitutions, and a technical blocker with one safe realistic in-authority resolution. Ask only for a genuine consequential branch or authority expansion; do not re-request an existing grant.

New projects store shipped reference artifacts under `.bbk/examples/`, outside operational directories. They do not count as live project state or default manifest/candidate inputs. Omit them entirely when desired:

```bash
bbk init --root . --project-id PROJECT-1 --title "Project 1" --no-examples
```

Existing legacy `EXAMPLE-*` files remain recognized as non-operational.

## Durable question and handoff records

```bash
bbk question new --root . --id Q-001 --root-decision "Choose the provider contract"
bbk question validate .bbk/questions/Q-001.json
bbk question list --root .

bbk handoff create --root . --work-unit WU-001 --attempt 1 \
  --disposition PARTIAL --summary "Checkpoint" \
  --artifact out/result.json --continuation-state READY \
  --next-action "Resume and validate"
bbk handoff verify .bbk/handoffs/WU-001/HO-WU-001-1 --root .
bbk handoff list --root . --work-unit WU-001 --latest
```

Use `bbk beads handoff-plan` for a compact append-only Beads pointer. New projects enable writes by default, while existing projects retain their recorded mapping. Worker Orchestrator normally targets the mapped WorkUnit; Root or Territory Orchestrator passes `--target-bbk-id <project-or-territory-id>` for the exact mapped owner record. `--bead` without `--target-bbk-id` is an explicitly reviewed foreign target and does not create a mapping. Never project BBK semantic state into Beads workflow status.

## Decision branches and context

For a material decision, use the recommendation-first path:

```text
Root or Territory Wayfinder
  → Questioning Wayfinder
      → investigate discoverable facts
      → prepare a decision-ready recommendation
  → harness-root controller presents it
      ├─ accepted → ADR-compatible decision packet; no Question Guide
      ├─ bounded correction → revise the recommendation
      └─ rejected, contested, materially ambiguous, or deeper exploration requested
           → one focused Question Guide conducts the deep Grill
           → validated result returns through the Questioning Wayfinder
  → controller-mediated parent synthesis
```

The Questioning Wayfinder may share a physical model invocation with another logical role when policy permits. Record the mapping and preserve any required approval, validation, integration, or evidence-independence separation. Do not spawn a Question Guide merely because a decision exists.

Use `bbk-wayfind` to maintain destination, posture, map, frontier, blockers, fog, dependencies, invalidation, and economic stopping across the recursive planning loop. Use `bbk-grill` only for the deeper escalation path. Rejecting one recommendation keeps the root question open; it does not disposition the question itself. Territory Wayfinders route material human decisions through this path rather than asking directly. Planning and Phase Wayfinders return missing decisions upward instead of silently filling them.

See [`WAYFINDING-AND-GRILL.md`](WAYFINDING-AND-GRILL.md).

Before delegation, use `bbk-context-routing` to bind the exact subject and revision, included structured objects or summaries, omissions, redactions, retrieval rights, effective instructions, tools, authority, allowed effects, freshness, and required result envelope. Do not rely on ambient transcript history as an undeclared input.

Use `bbk-procedure-design` when work is recurring, multi-step, interactive, adaptive, recovery-sensitive, or assurance-sensitive. Keep the procedure separate from performer identity and the exact execution baseline that grants authority.

Evidence exposure is append-only. Exploratory criteria or selections made after seeing outcome-bearing evidence cannot later be represented as independent confirmation against that same evidence.

## Role scope, delegation, escalation, and installed profiles

Each canonical role carries explicit `## Runtime identity and interaction topology`, `## Scope`, `## Delegation`, `## Escalation and human relay`, invocation, and return contracts. OMP's native `spawns` field remains the enforceable direct-child allowlist, while every projection states the exact trigger for each child. Do not delegate merely because a child is available, delegate to an unlisted role, or absorb a listed child's responsibility because the parent model could perform it.

All 19 canonical roles are non-user-facing. `human_decision_triggers` identify when a role must send a structured decision, authority, private-context, protected-floor, hard-to-reverse, acceptance, blocker, or scope request to the harness-root controller. In OMP, use `hub`/IRC to the peer whose `kind` is `main`; in Codex and Claude Code, return the same packet through the native parent channel. No child infers consent from silence or transport state.

Canonical projections embed each role's assigned prompt modules and exact role-specific mandatory procedures. Every current role uses one primary procedure, but one is not a fixed maximum: additional procedures require a source-bound measured exception proving distinct behavior and zero duplicated module bodies. OMP has no `autoloadSkills` requirement and Claude Code has no mandatory `skills` frontmatter. Optional procedures and language/domain profiles remain visible and load only when material. See [`AGENTS.md`](AGENTS.md).

Before material language-, framework-, runtime-, or toolchain-specific work, consult the installed `bbk-installed-profiles` skill and confirm discovery:

```bash
bbk --json profile list
```

The installed registry records the preferred launcher and an exact Python/script fallback. If a shell or mise environment cannot resolve `bbk`, invoke that bound path before classifying profile discovery as unavailable. Load the selected router and only the focused procedures required for the current assertion. Carry the profile identity, lock/digest, toolchain assumptions, gates, and unavailable-capability disposition into child context and returns.

## Typed language/domain profile resolution

Profiles that implement the original preflight, structure, slice, and gate operations remain usable for those operations. Profiles using `bbk.profile-capability.v1` can also participate in State–Decision–Effect and Review Assurance.

```bash
bbk profile resolve \
  --id rust \
  --role reviewer \
  --work-unit .bbk/work-units/WU-001.json \
  --solution-outcome-fit .bbk/fit/SOF-001.json \
  --structure-contract .bbk/structures/ISC-001.json \
  --execution-slice .bbk/slices/ES-001.json \
  --state-decision-effect .bbk/state-effects/SDE-001.json \
  --assurance-contract .bbk/assurance/AC-001.json \
  --review-manifest .bbk/reviews/manifests/RM-001.json \
  --evidence-input .bbk/receipts/NATIVE-001.json \
  --write-lock
```

The resolver runs only operations declared through the typed protocol and supported by exact inputs. It records unsupported review assignments rather than silently dropping or improvising them.

For one operation:

```bash
bbk profile dispatch \
  --operation state-effect \
  --id rust \
  --state-decision-effect .bbk/state-effects/SDE-001.json
```

Available operations:

```text
state-effect
state-effect-inventory
state-effect-review
review-context
review-lens
evidence-adapter
```

Profiles receive a read-only, content-addressed request package. `runTools` permits only profile-qualified read-only inspection/evidence actions; it never grants mutation, dependency installation, network access, publication, deployment, or external effects.

## Solution–outcome fit

```bash
bbk fit new --output .bbk/fit/SOF-001.json
bbk fit validate .bbk/fit/SOF-001.json
bbk fit render .bbk/fit/SOF-001.json --output .bbk/reviews/SOF-001.md
```

`INVESTIGATE` and `UNRESOLVED` block implementation commitment but permit bounded investigation.

## Structure, schema discovery, state/effect design, and slices

New structure contracts default to v3. Use the compact infrastructure form when software-class structure is not material:

```bash
bbk structure new --version v3 --kind infrastructure --depth compact \
  --output .bbk/structures/ISC-001.json
bbk structure validate .bbk/structures/ISC-001.json

bbk schema list
bbk schema template --kind implementation-structure \
  --subject-kind network_configuration --depth compact \
  --output .bbk/structures/NETWORK-001.json
bbk schema enum --schema implementation-structure \
  --pointer /contractDepth
bbk schema explain --schema implementation-structure \
  --instance .bbk/structures/NETWORK-001.json

bbk state-effect new --output .bbk/state-effects/SDE-001.json
bbk state-effect validate .bbk/state-effects/SDE-001.json
bbk trace new --output .bbk/traces/TRACE-001.json
bbk trace validate .bbk/traces/TRACE-001.json
bbk trace check-set --design .bbk/state-effects/SDE-001.json \
  --trace .bbk/traces/TRACE-001.json
bbk structure validate .bbk/structures/ISC-001.json

bbk slice new --output .bbk/slices/ES-001.json
bbk slice validate .bbk/slices/ES-001.json
bbk slice check-set .bbk/slices/*.json
```

Use `compact` for a bounded infrastructure, network, deployment, procedure, or document topology when full software-state detail would be artificial. Use `standard` or `full` when material history, concurrency, state/effect transitions, external effects, ambiguity, recovery, migration, or authority demand it. v1/v2 remain valid compatibility inputs.

## Work units

```bash
bbk work-unit new --output .bbk/work-units/WU-001.json
bbk work-unit validate .bbk/work-units/WU-001.json
```

## Assurance and review

Choose the smallest justified mode: `INLINE`, `FOCUSED`, or `FULL`. For generated candidate-bound review context, prefer:

```bash
bbk context review --root . \
  --candidate .bbk/packages/C-001 \
  --request .bbk/reviews/requests/RQ-001.json \
  --output .bbk/reviews/contexts/C-001
```

Legacy assurance/review records remain supported:

```bash
bbk assurance new --output .bbk/assurance/AC-001.json
bbk assurance validate .bbk/assurance/AC-001.json

bbk review plan \
  --assurance .bbk/assurance/AC-001.json \
  --id RM-001 \
  --purpose acceptance \
  --output .bbk/reviews/manifests/RM-001.json

bbk review context \
  --manifest .bbk/reviews/manifests/RM-001.json \
  --id RCM-001 \
  --source . \
  --output .bbk/reviews/contexts/RCM-001.json
```

Compose a durable run from exact attempts, receipts, findings, and dispositions:

```bash
bbk review run \
  --id RR-001 \
  --manifest .bbk/reviews/manifests/RM-001.json \
  --context .bbk/reviews/contexts/RCM-001.json \
  --attempt .bbk/reviews/attempts/RA-001.json \
  --receipt .bbk/receipts/ER-001.json \
  --finding .bbk/reviews/findings/RF-001.json \
  --output .bbk/reviews/runs/RR-001.json
```

A later review's silence never closes a finding.

## Artifact packages, manifests, candidates, and gates

For immutable package publication, use the common transaction:

```bash
bbk artifact preflight .bbk/drafts/C-001
bbk artifact seal .bbk/drafts/C-001 --output .bbk/packages/C-001
bbk artifact verify .bbk/packages/C-001
bbk artifact successor .bbk/packages/C-001 --output .bbk/drafts/C-002 \
  --revision r2 --reason "Focused repair"
```

Codex, OMP, Pi, and generic hosts receive shared skills under `.agents/skills`; Claude Code receives the same canonical skills under `.claude/skills`. The `bbk-artifact` procedure is available on demand. When the short `bbk` launcher is not on `PATH`, call the skill wrapper; it resolves the nearest valid project install manifest and then the user install manifest, and invokes the exact recorded Python executable and installed `tools/bbk.py`.

User-scope Windows examples:

```powershell
# Codex
$BbkArtifact = "$HOME\.agents\skills\bbk-artifact\scripts\bbk-artifact.cmd"

# Claude Code uses this location instead:
# $BbkArtifact = "$HOME\.claude\skills\bbk-artifact\scripts\bbk-artifact.cmd"

& $BbkArtifact binding
& $BbkArtifact preflight ".bbk\drafts\C-001"
& $BbkArtifact seal ".bbk\drafts\C-001" --output ".bbk\packages\C-001"
& $BbkArtifact verify ".bbk\packages\C-001"
```

Project-scope roots are `<project>/.agents/skills/bbk-artifact` for Codex, OMP, Pi, and generic hosts, and `<project>/.claude/skills/bbk-artifact` for Claude Code. On Linux and macOS, invoke the wrapper as `sh <skill-root>/scripts/bbk-artifact.sh ...`; release archives intentionally do not rely on executable permission bits. A passing package operation proves stored bytes and declared closure only; it does not establish semantic correctness, acceptance, authorization, validation, deployment readiness, or release authority.

For a bounded legacy handoff or review set, the exact artifact-manifest surface remains available:

```bash
bbk artifact manifest --root . \
  --path deploy --path .bbk/structures/ISC-001.json \
  --subject REVIEW-001 --output .bbk/manifests/REVIEW-001.json
bbk artifact verify .bbk/manifests/REVIEW-001.json --root .

bbk manifest create --output .bbk/baseline-manifest.json
bbk manifest compare --left .bbk/baseline-manifest.json

bbk candidate freeze --id C-001 \
  --structure-inventory .bbk/inventories/ACTUAL-001.json \
  --trace .bbk/traces/TRACE-001.json \
  --formal-model .bbk/models/MODEL-001.json
bbk candidate check --id C-001
bbk gate run --phase prevalidate --candidate C-001
bbk candidate status --id C-001
```

## Workspaces

```bash
bbk workspace create --id WU-001 --base HEAD --purpose "Implement WU-001"
bbk workspace inspect --id WU-001
bbk workspace renew --id WU-001 --hours 24
bbk workspace cleanup --id WU-001 --delete-branch
```

Each concurrent writer needs a distinct physical worktree. Cleanup refuses dirty or candidate-referenced workspaces unless deliberately forced.

## Recovery, resumable workers, durable handoffs, and Beads

```bash
bbk status
bbk doctor
bbk workspace list --all
bbk beads plan
bbk beads plan --apply
bbk schema status
```

New projects record Beads settings and foreign bindings in `.bbk/mappings/beads.json`. They enable the Beads projection, writes, and first-use `bd init --quiet --skip-agents` by default. The external `bd` command is not bundled. `bbk beads plan` is the non-mutating review surface; `--apply` creates, inspects, or updates exact role-owned projections and records foreign IDs and verified projection digests. Repeating an unchanged apply is idempotent. Direct tracker edits, duplicate bindings, hierarchy changes, type changes, or mismatched foreign identity produce explicit drift/reconciliation results rather than last-write-wins mutation. Set `enabled` or `write_enabled` to `false` deliberately when a project must not project into Beads.

The ownership split is: Root/Territory Wayfinders for project, territory, and decision records; Planning/Phase Wayfinders for capability increments, phases, and WorkUnits; Root/Territory/Worker Orchestrators for execution-state and compact handoff pointers; Questioning Wayfinder for question records. BBK IDs, accepted decisions, execution authority, candidate identity, findings, evidence, validation, completion, and release state remain canonical under `.bbk/`.

Long-running workers use an extended logical execution window, checkpoint before host interruption, and resume the same logical thread when possible. Host-window expiry is infrastructure interruption unless evidence establishes a candidate defect.

Create and verify a lossless handoff for exact or large outputs:

```powershell
python tools\bbk.py handoff create --root D:\Project `
  --work-unit WU-001 --disposition PARTIAL `
  --summary "Implementation complete; validation remains." `
  --artifact out\candidate.json --continuation-state READY `
  --checkpoint .bbk\runtime\WU-001.json `
  --next-action "Resume the same worker thread and run focused validation."

python tools\bbk.py handoff verify `
  .bbk\handoffs\WU-001\HO-WU-001-1.json --root D:\Project
```

Project-relative path, byte count, and SHA-256 are authoritative. Keep the conversational envelope compact. Use `bbk beads handoff-plan` to append only a verified pointer; do not paste the large artifact into the issue. Worker Orchestrator normally targets the mapped WorkUnit. Root or Territory Orchestrator passes `--target-bbk-id` for the exact mapped project or territory record it owns. An explicit target must already have one unique mapping, and a simultaneously supplied `--bead` must match it. Beads coordination cannot accept a BBK decision or finding, and closing a bead does not prove validation or outcome completion.

For Draft 2020-12 validation:

```powershell
python tools\bbk.py schema validate --schema schema.json --instance candidate.json
```

If the adapter reports `BLOCKED`, rerun explicitly with `--ensure` or provide the dependency through an offline wheelhouse. See [`DURABLE-HANDOFFS.md`](DURABLE-HANDOFFS.md).

Use the `bbk-recover` skill when ownership, candidate identity, effects, evidence, or handoff state is ambiguous.

## OMP slash-command context boundary

Deterministic BBK slash commands are UI operations, not prompts. `/bbk:models`, `/bbk:agents`, `/bbk:beads`, `/bbk:status`, `/bbk:doctor`, `/bbk:exit`, the other deterministic `/bbk:*` commands, and every bundled language-profile slash command report concise UI summaries and do not inject CLI JSON into model context.

Persistent mode state is written with `appendEntry`, which is not sent to the LLM. While active, `before_agent_start` replaces Main's complete system prompt and injects the mandatory controller procedures. For named BBK children it replaces OMP's subagent workflow prompt while preserving only sanitized invocation data. `/bbk <request>` is the sole slash-command path that invokes `sendUserMessage`, and it forwards only the user's directive. `/bbk` with no arguments does not trigger a model turn.

To update only BBK's Codex custom-agent definitions while preserving OMP and its active model-routing state:

```powershell
python tools/setup.py --test-and-update-codex --scope user
```

Use `--update-codex` instead when the release has already been verified. The updater changes BBK's 19 Codex custom-agent files, installs or refreshes the seven-file canonical `bbk-artifact` skill under `.agents/skills`, and reconciles unified-manifest ownership. It preserves the installed package, launcher, effective model-routing file, OMP agent/extension state, Pi agents, Claude Code, generic agents, and language profiles. Start a fresh Codex turn or session if the host has cached agent definitions or skills.

To update only OMP while Codex remains running:

```powershell
python tools/setup.py --test-and-update-omp --scope user
```

After it succeeds, run `/reload-plugins` in OMP. The updater preserves the current OMP runtime-routing state and does not modify `.codex` agent files.
