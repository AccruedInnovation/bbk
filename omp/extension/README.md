# BBK alpha.14 OMP extension

This adapter exposes BBK's deterministic project, fit, structure, State–Decision–Effect, slicing, assurance, candidate, gate, review, evidence, profile, workspace, model-routing, and orchestration-entrypoint surfaces.

## `/bbk` enters persistent BBK mode

```text
/bbk                 enter BBK mode without starting an agent turn
/bbk <request>       enter BBK mode and submit the first directive
/bbk:exit            exit BBK mode
/bbk exit            non-colon exit alias
/bbk status          deterministic project status without changing mode
/bbk:status          deterministic project status without changing mode
```

The mode is **session-local**. `/bbk` stores a compact `bbk-mode-state` v2 custom entry with `pi.appendEntry`; OMP does not send that entry to the model. The extension restores the latest branch state on `session_start`, `session_switch`, `session_branch`, and `session_tree`.

## Live child activity widget

The extension subscribes to OMP's shared `task:subagent:lifecycle` and `task:subagent:progress` events. While BBK mode is active it owns one line through `ctx.ui.setWidget(..., { placement: "aboveEditor" })`. The idle form is:

```text
BBK · ready
```

While canonical `bbk_*` jobs are pending or running, the same line becomes:

```text
BBK · 3 active · Root plan › Phase plan › Architecture [ctx 264k/1M 26%]: compiling interfaces | Verification 44.7k/1M 4.5%
```

The most recently active BBK job supplies its full Main-to-descendant path and latest public intent, tool/action, or recent public output. The extension recursively consumes OMP `inflightTaskDetails.progress`, finalized task results, lifecycle events, and direct progress events, so synchronous descendants remain visible even when a detached-only host list shows only Main's direct child. Direct and nested observations are deduplicated by stable agent, task, session, and tool-call identities. When OMP publishes `contextTokens` and `contextWindow`, BBK shows current context use and percentage; up to three other active jobs receive compact gauges. ANSI/control characters and embedded newlines are removed and non-BBK task events are ignored. Completion returns the line to `BBK · ready` while retaining bounded terminal history; session navigation rebuilds it from restored mode state; mode exit and shutdown clear it.

The complete hierarchy and per-agent metadata are available through:

```text
/bbk:agents
/bbk:agents active
/bbk:agents details <agent-id-or-name>
/bbk:agents json
```

The view includes parentage, depth, status, synchronous/detached mode, selected model, assignment, current activity/tool, context use, session identity, and task-call identity.

The old separate `setStatus`-based `BBK` row is no longer emitted. OMP's public `setFooter` extension method is currently not effective in interactive mode, so an extension cannot replace the built-in `pi` footer brand. BBK leaves that native footer intact and consolidates mode plus worker state into the single widget above it.

## Complete Main system-prompt replacement

For each ordinary Main turn in an active session, `before_agent_start` returns one `<bbk-controller-system>` block. This is a **system-prompt replacement**, not an append or overlay. It excludes OMP's generic planning/delegation workflow and compatibility-discovered `.codex`, `.claude`, `.gemini`, and other client-specific instructions. The replacement injects the complete `bbk` and `bbk-context-routing` mandatory skills directly.

The peer whose `kind` is `main`, normally `Main`, is the sole user-facing controller. It does not imitate canonical roles. It routes exactly one root through OMP `task`. With the advertised batch form, even one root uses `{ context, tasks: [{ name, agent, task, ... }] }`: `agent` is the exact canonical role, `name` is a stable IRC/job ID, and `task` is the complete assignment. A flat-form host uses its exact schema and a durable `local://` file for reusable shared context.

```text
planning, design, uncertainty, or no accepted executable baseline
  → bbk_root_wayfinder
accepted-baseline execution or recovery
  → bbk_root_orchestrator
bounded independent review
  → bbk_reviewer
assertion-scoped candidate acceptance
  → bbk_validator_orchestrator
```

Prefer background/non-blocking root jobs so Main remains available to relay user decisions and steering. `/bbk <request>` forwards only the raw directive through `sendUserMessage`; `/bbk` with no arguments and `/bbk:exit` perform only local state/UI work. `/bbk:exit` restores ordinary OMP prompting for later Main turns.

All generated alpha.14 OMP BBK agents declare `blocking: false`. With OMP 16.4.8 and `async.enabled=true`, eligible task spawns use managed background jobs whose lifetime is independent of the parent tool call. When the host uses inline task execution, BBK prompt modules sequence human callbacks ahead of decision-dependent specialist dispatch so an immediate response cannot cascade-cancel useful work. See `docs/OMP-CHILD-LIFETIME.md`.

Prompt replacement does not change the parent model, thinking level, active tools, child model routes, filesystem containment, or native host capabilities. It also does not itself exit another OMP mode; leave a conflicting native mode separately when its tool restrictions are inappropriate.

## Closed role-specific child replacement

All 19 generated OMP roles carry a deterministic `<bbk-agent-system role="...">` marker. Every named `bbk_*` role is a non-user-facing child, including Root Wayfinder, Root Orchestrator, Question Guide, Reviewer, and Validator Orchestrator.

When a marked role starts, `before_agent_start` replaces the complete incoming subagent system prompt with one `<bbk-agent-replacement>` block containing:

- the canonical role contract;
- complete inlined bodies and digests for the role's declared `mandatory_skills`;
- compact BBK runtime facts;
- explicit task-call context parsed only from OMP's marker-bearing native child wrapper;
- an approved `<plan>` and its path when present;
- isolated worktree information;
- hub peer identity and initial roster;
- the caller's yield schema when present; and
- the BBK completion, blocker, evidence, and durable-handoff rules.

The replacement discards conflicting generic OMP workflow rules and Codex/Claude/Gemini compatibility context. It authenticates every non-empty line of the embedded role contract against the installed projection while allowing only host presentation normalization: line-ending conversion, blank-line insertion/removal, and trailing spaces or tabs. A changed, missing, injected, or reordered non-empty instruction still fails closed. A caller schema may refine result-field shape but cannot broaden authority, erase findings, or convert missing evidence into success. Children finish through OMP's hidden `yield` tool with the BBK result in `result.data`; genuine terminal failures use `result.error`. Prompt assembly fails closed when the marker, role catalogue, installed projection, or mandatory procedure set is invalid.

OMP frontmatter intentionally has no `autoloadSkills`. Mandatory procedures are already in the system prompt, so the model does not waste a skill-read call and correctness does not depend on host autoload behavior. Optional procedures and language/domain profiles remain available on demand.

## Effective prompt receipts

OMP 16.4.8 records a child session's assembled pre-hook prompt before `before_agent_start` replacement. Alpha.14 appends digest-only `bbk.effective-prompt-receipt.v1` entries after replacement and at `before_provider_request` when the host exposes `getSystemPrompt()`.

```text
/bbk:prompt-status
/bbk:prompt-status json
```

The receipt records source/effective lengths and SHA-256 digests, role/package identity, replacement-marker count, generic OMP contamination detection/removal, and provider-bound `VERIFIED`, `MISMATCH`, `UNAVAILABLE`, or `ERROR`. It never duplicates the raw prompt. The surface is observability only and does not abort or create Blueprint-style lifecycle authority.

## Main-mediated `hub`/IRC communication

Named BBK agents use OMP `hub`/IRC for live communication. They discover exact peer IDs with the roster, send ordinary coordination to their invoking parent, and send a compact `BBK_USER_REQUEST` to Main when they need a material decision, authority grant, private context, protected-floor exception, hard-to-reverse commitment, or explicit acceptance. The request carries a stable ID, the smallest material question, recommendation, alternatives, consequences, residual uncertainty, blocking state, and any durable packet reference.

Main presents the question only through OMP's native `ask` tool and relays the structured result to the exact waiting peer as a matching `BBK_USER_RESPONSE` marked `source: omp.ask`, preserving `replyTo` where available and notifying the semantic parent when needed. A question written only in assistant prose is informational; it is not pending and cannot be treated as answered. Only an ask-backed response is eligible for ADR-compatible accepted-decision recording, and the responsible canonical role—not Main—authors the ADR. A send receipt, timeout, silence, or missing heartbeat is not a user answer or proof of failure. Large or authority-bearing material remains in durable files; IRC carries path, bytes, SHA-256, disposition, and smallest next action.

## Installed projection and model-routing surface

The OMP target installs:

- 19 role agents with native direct-child `spawns` allowlists;
- 39 generated BBK skills, including one installation-bound profile registry;
- complete mandatory-skill injection for every role;
- explicit `model` and `thinkingLevel` fields;
- 33 model-facing tools and 36 UI commands; and
- the persistent `/bbk`, deterministic `/bbk:status`, scoped `/bbk:models`, hierarchical `/bbk:agents`, normal `/bbk:beads`, schema/artifact utilities, and `/bbk:prompt-status` surfaces.

The canonical install-time v2 policy gives every role its own OMP route. Alpha.14 preserves the exact reviewed per-role selections from the split-role update: judgment-heavy roles primarily use `openai-codex/gpt-5.6-sol`, Territory Orchestrator uses `openai-codex/gpt-5.6-luna`, and bounded empirical/mechanical roles use `deepseek/deepseek-v4-flash`, with the reviewed role-specific thinking levels. These are duplicated per-role values rather than shared categories. Model choice is an execution preference, not authority or assurance.

```text
/bbk:models
/bbk:models status
/bbk:models project status
/bbk:models project create
/bbk:models project repair --dry-run
/bbk:models project repair
/bbk:models user status
/bbk:models project profile testing-flash
/bbk:models user profile default
/bbk:models set bbk_worker deepseek/deepseek-v4-flash high
/bbk:models apply /path/to/profile.json
/bbk:models export /path/to/profile.json profile-id
```

From user scope, `project create` clones the exact effective user OMP routes into an authenticated OMP-only project installation with no language profiles and no Git or `.bbk` initialization. A partial or divergent project fails closed. `project repair` is dry-run first, backup-aware, and requires explicit confirmation. Reload OMP after creation or repair.

The default `auto` target resolves the nearest valid project-scoped BBK OMP installation and otherwise the user installation. An expected but invalid project binding fails closed rather than falling through to user-global state. Explicit `project` and `user` targets are available; user-scope mutations require interactive confirmation. Changes apply to future child spawns. `task.agentModelOverrides` and higher-precedence project agent definitions may supersede BBK-managed frontmatter; status reports scope, binding paths, global effect, and that precedence boundary.
The selected binding is executed with the routing program installed beside that binding. A missing target-bound router fails closed; BBK does not use a router from another scope or package version.

## Normal Beads projection

New BBK projects enable Beads projection, writes, and first-use initialization by default. The external `bd` executable remains a separately installed host capability. BBK records remain semantically authoritative.

```text
/bbk:beads plan
/bbk:beads apply
/bbk:beads handoff --handoff .bbk/handoffs/WU-1/HO-WU-1-1.json
/bbk:beads handoff-apply --handoff .bbk/handoffs/WU-1/HO-WU-1-1.json
/bbk:beads handoff-apply --handoff .bbk/handoffs/WU-1/HO-WU-1-1.json --target-bbk-id T-1
```

The model-facing `bbk_beads_sync` and `bbk_beads_handoff` tools expose the same bounded operations. Worker Orchestrator normally targets the mapped WorkUnit; Root and Territory Orchestrators use `targetBbkId` for the exact mapped project or territory record they own. Explicit targets fail closed when unmapped or when a supplied foreign Beads ID disagrees with the binding. Synchronization is dry-run first, deterministic, idempotent, hierarchy-aware, and foreign-drift safe. It records exact BBK-to-Beads identities and refuses last-write-wins adoption of direct tracker edits. Tracker status, closure, comments, and hierarchy do not accept decisions, prove findings closed, establish validation, or define completion.

## Slash-command and model-context boundary

Deterministic slash commands are **UI-only**. They notify through `ctx.ui.notify`, return no structured command payload, and do not call `sendMessage` or `sendUserMessage`, so their JSON does not enter model context. `/bbk <request>` is the only slash-command path that calls `sendUserMessage`, and it forwards only the user's text. Registered model-facing tools still return structured content because the model explicitly invoked them.

## OMP-only update

```powershell
python tools/setup.py --test-and-update-omp --scope user
```

The updater preserves the active BBK OMP model route, updates future role definitions and the extension, reconciles the install manifest, and **does not modify `.codex`** agent files. Run `/reload-plugins` in an existing OMP session afterward.

## Qualification boundary

Package qualification checks JavaScript syntax, exact registration counts, persistent state restoration, live activity/context rendering, lifecycle clearing, full Main and child system-prompt replacement, exclusion of compatibility context, mandatory skill injection, ask-backed ADR provenance, preservation of sanitized invocation data, hub/Main communication contracts, fail-closed behavior, UI-only commands, deterministic projections, installation ownership, and model-routing bindings. It does not prove live provider/model availability, model competence, physical review independence, target-project correctness, external profile toolchains, exact optional progress fields in every OMP build, interactive footer replacement, or compliance with an institution's network policy.
