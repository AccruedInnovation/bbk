# BBK alpha.11.11 usage

Alpha.11.11 is the current canonical successor. It adds complete per-role scope, delegation-trigger, escalation, and user-interaction contracts; modular role constitutions; and lean canonical sub-agents that no longer autoload the top-level entry controller. It retains persistent session-local BBK mode, bundled profiles, ordered verification, installation safeguards, model routing, selective host updates, recommendation-first Wayfinding, escalation-only Grill, durable handoffs, resumable workers, and explicit execution control.

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

`/bbk` persists a session-local state entry with `appendEntry`, shows `BBK` in the footer, and does not inject a chat message. While active, `before_agent_start` adds a concise system-prompt overlay to every ordinary agent turn. The overlay makes each new message a continuation or directive within the BBK-governed workflow and routes work to the appropriate named agent:

```text
no accepted executable baseline, planning, architecture, or material uncertainty
  → bbk_root_wayfinder

accepted sufficiently specified execution/recovery baseline
  → bbk_root_orchestrator

bounded independent review
  → bbk_reviewer

assertion-scoped acceptance run
  → bbk_validator_orchestrator
```

`/bbk <request>` sends only the request text through `sendUserMessage`; it does not copy the full `bbk` skill into the transcript. `/bbk` with no arguments and `/bbk:exit` are local UI/state operations and do not start an agent turn. The mode is restored from the active branch when a session is resumed, switched, branched, or navigated.

BBK mode is session-local. It does not change the parent model, thinking level, toolset, or sub-agent model routing, and it does not replace OMP's native plan or vibe modes. Use `/bbk:exit` before returning to an unrelated main-session workflow.

### Codex, Claude Code, and generic hosts

Invoke the installed baseline `bbk` skill. It carries the entry-controller responsibility for the current request. Use a named generated BBK agent where the host supports one so its model, effort, skills, tool policy, spawn policy, and return contract apply. Adopt the selected logical role in the current session only where named-agent invocation is unavailable.

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

Use `bbk manifest create` and `bbk manifest compare` for exact directory inventories. Use `bbk candidate freeze`, `check`, and `verify` for candidate identity. Use `bbk handoff create`/`verify` for structured, digest-bound returns and `bbk handoff list --latest` for deterministic rediscovery.


## Test and install

Complete ordered verification:

```bash
python tools/run_tests.py --all --require-node
python tools/bootstrap.py --test --require-node
```

Verify and install only on PASS. All five bundled profiles are installed by default:

```bash
python tools/bootstrap.py --test-and-install --scope user --omp --codex --claude
```

Install a bundled subset:

```bash
python tools/bootstrap.py --test-and-install --scope user --omp --codex \
  --profile-id rust --profile-id python
```

Install core BBK only:

```bash
python tools/bootstrap.py --test-and-install --scope user --omp --codex \
  --no-language-profiles
```

Use the profile-focused wrapper with the bundled default:

```bash
python tools/install_profiles.py --scope user --omp --codex --claude
```

Supplying `--language-profiles /path/to/bundle.zip` or `install_profiles.py --bundle ...` replaces the bundled source for that invocation. The path may also be an expanded profile package tree or the directly published `bbk-language-profiles` repository.

See `INSTALL.md` and `LANGUAGE-PROFILES.md` for dry runs, source-mode semantics, direct installer equivalents, and the complete preflight boundary.

## Select sub-agent models

The packaged default is `spec/model-routing.json`. It maps all 19 roles through `judgment`, `coordination`, and `mechanical` profiles and emits native model/effort fields for OMP, Codex, and Claude Code.

Validate it with:

```bash
python tools/model_routing.py --check
python tools/generate_agents.py --check
```

For a customized installation, copy the policy outside the verified package, edit profile settings or role assignments, validate the copy, and pass it to the installer:

```bash
python tools/model_routing.py --path /path/to/model-routing.json --check
python tools/install.py install --scope project --root /path/to/repo \
  --omp --codex --claude --model-routing /path/to/model-routing.json
```

OMP accepts its configured role aliases such as `@default`, `@smol`, `@slow`, `@vision`, `@plan`, `@designer`, `@commit`, `@tiny`, `@task`, and `@advisor`, or a direct selector such as `deepseek/deepseek-v4-flash`. Model routing is an execution default, not an authority grant or proof that the selected model is sufficient for every invocation. See `MODEL-ROUTING.md`.

## OMP sub-agent model menu

```text
/bbk:models
```

Choose `testing-flash` for fast low-cost BBK functional tests, `deepseek-economy` for DeepSeek-only routing, `default` for the packaged tiered route, or `installation-default` to return to the exact install-time routes. The menu can set `model` and `thinkingLevel` for any BBK sub-agent, apply an external `omp-model-routing-profile.json`, and export the current BBK-managed routes. Changes apply to future spawns; already-running sub-agents are unaffected.

The menu populates model choices from authenticated OMP models, the packaged profiles, the current route, and OMP's built-in aliases. It warns when OMP cannot currently resolve a selected model but permits saving it for later provider configuration. OMP `task.agentModelOverrides` and higher-precedence project agent definitions can supersede BBK-managed frontmatter; use `/bbk:models status` and inspect OMP configuration when a spawned model differs from the displayed BBK route.

Scriptable forms:

```text
/bbk:models status
/bbk:models profile testing-flash
/bbk:models set bbk_validator @task medium
/bbk:models apply D:\Profiles\bbk-cheap.json
/bbk:models export D:\Profiles\bbk-current.json current-bbk
```

See `MODEL-ROUTING.md` and `../templates/omp-model-routing-profile.json`.

## Start a project

```bash
bbk init --title "Project name"
bbk status
```

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

## Durable question and handoff records

```bash
bbk question new --root . --id Q-001 --root-decision "Choose the provider contract"
bbk question validate .bbk/questions/Q-001.json
bbk question list --root .

bbk handoff create --root . --work-unit WU-001 --attempt 1 \
  --disposition PARTIAL --summary "Checkpoint" \
  --artifact out/result.json --continuation-state READY \
  --next-action "Resume and validate"
bbk handoff verify .bbk/handoffs/WU-001/HO-WU-001-1.json --root .
bbk handoff list --root . --work-unit WU-001 --latest
```

Use `bbk beads handoff-plan` for a compact append-only Beads pointer. `--apply` is allowed only after the project mapping explicitly enables writes.

## Decision branches and context

For a material decision, use the recommendation-first path:

```text
Root or Territory Wayfinder
  → Questioning Wayfinder
      → investigate discoverable facts
      → prepare a decision-ready recommendation
  → user-facing parent presents it
      ├─ accepted → ADR-compatible decision packet; no Question Guide
      ├─ bounded correction → revise the recommendation
      └─ rejected, contested, materially ambiguous, or deeper exploration requested
           → one focused Question Guide conducts the deep Grill
           → validated result returns through the Questioning Wayfinder
  → parent synthesis
```

The Questioning Wayfinder may share a physical model invocation with another logical role when policy permits. Record the mapping and preserve any required approval, validation, integration, or evidence-independence separation. Do not spawn a Question Guide merely because a decision exists.

Use `bbk-wayfind` to maintain destination, posture, map, frontier, blockers, fog, dependencies, invalidation, and economic stopping across the recursive planning loop. Use `bbk-grill` only for the deeper escalation path. Rejecting one recommendation keeps the root question open; it does not disposition the question itself. Territory Wayfinders route material human decisions through this path rather than asking directly. Planning and Phase Wayfinders return missing decisions upward instead of silently filling them.

See `WAYFINDING-AND-GRILL.md`.

Before delegation, use `bbk-context-routing` to bind the exact subject and revision, included structured objects or summaries, omissions, redactions, retrieval rights, effective instructions, tools, authority, allowed effects, freshness, and required result envelope. Do not rely on ambient transcript history as an undeclared input.

Use `bbk-procedure-design` when work is recurring, multi-step, interactive, adaptive, recovery-sensitive, or assurance-sensitive. Keep the procedure separate from performer identity and the exact execution baseline that grants authority.

Evidence exposure is append-only. Exploratory criteria or selections made after seeing outcome-bearing evidence cannot later be represented as independent confirmation against that same evidence.

## Role scope, delegation, escalation, and installed profiles

Each canonical role carries an explicit `## Scope`, `## Delegation`, and `## Escalation and user interaction` contract. OMP's native `spawns` field remains the enforceable direct-child allowlist, while the OMP prompt now states the exact condition under which each child should be used. Codex, Claude Code, and generic projections carry the same trigger map. Do not delegate merely because a child is available, delegate to an unlisted role, or absorb a listed child's distinct responsibility merely because the parent model could perform it.

Only the active Root Wayfinder and an active Question Guide may ask the user directly, within their declared limits. Every other role returns a structured decision, authority, private-context, blocker, or scope request to its parent. Canonical sub-agents do not autoload the top-level `bbk` entry-controller skill. OMP and Claude preload only each role's two- or three-skill procedure core; the full allowed procedure list remains visible and is loaded on demand. See `AGENTS.md`.

Before material language-, framework-, runtime-, or toolchain-specific work, consult the installed `bbk-installed-profiles` skill and confirm discovery:

```bash
bbk --json profile list
```

The installed registry records the preferred launcher and an exact Python/script fallback. If a shell or mise environment cannot resolve `bbk`, invoke that bound path before classifying profile discovery as unavailable.

Load the selected profile router, then only the focused procedures needed for the current role and assertion. Carry the profile lock/digest, toolchain assumptions, required gates, and unavailable-capability disposition into child context and returns.

## Typed language/domain profile resolution

Existing alpha.2 profiles remain usable for their original preflight, structure, slice, and gate behavior. A successor using `bbk.profile-capability.v1` can additionally participate in State–Decision–Effect and Review Assurance.

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

## Structure, state/effect design, and slices

```bash
bbk structure new --output .bbk/structures/ISC-001.json
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

Use `CONTRACT` for material history, concurrency, external effects, ambiguity, recovery, or authority. Use the least sufficient formalization level.

## Work units

```bash
bbk work-unit new --output .bbk/work-units/WU-001.json
bbk work-unit validate .bbk/work-units/WU-001.json
```

## Assurance and review

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

## Manifests, candidates, and gates

```bash
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
bbk schema status
```

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

Project-relative path, byte count, and SHA-256 are authoritative. Keep the conversational envelope compact. Use `bbk beads handoff-plan` to append only a verified pointer to a bead; do not paste the large artifact into the issue. Beads coordination cannot accept a BBK decision or finding, and closing a bead does not prove validation or outcome completion.

For Draft 2020-12 validation:

```powershell
python tools\bbk.py schema validate --schema schema.json --instance candidate.json
```

If the adapter reports `BLOCKED`, rerun explicitly with `--ensure` or provide the dependency through an offline wheelhouse. See `DURABLE-HANDOFFS.md`.

Use the `bbk-recover` skill when ownership, candidate identity, effects, evidence, or handoff state is ambiguous.

## OMP slash-command context boundary

Deterministic BBK slash commands are UI operations, not prompts. `/bbk:models`, `/bbk:status`, `/bbk:doctor`, `/bbk:exit`, the other deterministic `/bbk:*` commands, and every bundled language-profile slash command report concise UI summaries and do not inject CLI JSON into model context.

Persistent mode state is written with `appendEntry`, which is not sent to the LLM. While the mode is active, `before_agent_start` adds the small BBK system-prompt overlay for each ordinary turn. The only slash-command path that invokes `sendUserMessage` is `/bbk <request>`, and it forwards only the user's directive. `/bbk` with no arguments does not trigger a model turn.

To update only BBK's Codex custom-agent definitions while preserving OMP and its active model-routing state:

```powershell
python tools/setup.py --test-and-update-codex --scope user
```

Use `--update-codex` instead when the release has already been verified. The updater changes only BBK's 19 Codex custom-agent files and unified-manifest ownership metadata; it preserves the installed package, launcher, effective model-routing file, OMP state, Claude Code, generic agents, and language profiles. Start a fresh Codex turn or session if the host has cached agent definitions.

To update only OMP while Codex remains running:

```powershell
python tools/setup.py --test-and-update-omp --scope user
```

After it succeeds, run `/reload-plugins` in OMP. The updater preserves the current model-routing profile and does not modify `.codex` agent files.
