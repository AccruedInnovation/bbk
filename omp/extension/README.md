# BBK alpha.11.11 OMP extension

This thin adapter exposes the BBK project, fit, structure, State–Decision–Effect, slicing, assurance, candidate, gate, review, finding, evidence, package, profile, leased-workspace, and orchestration-entrypoint surfaces.

## `/bbk` enters persistent BBK mode

```text
/bbk                 enter BBK mode without starting an agent turn
/bbk <request>       enter BBK mode and submit the first directive
/bbk:exit            exit BBK mode
/bbk exit            exit alias
/bbk status          run deterministic BBK status without changing the mode
/bbk:status          run deterministic BBK status without changing the mode
```

The mode is session-local. `/bbk` stores a compact `bbk-mode-state` custom entry with `pi.appendEntry`; OMP does not send that entry to the LLM. The extension restores the latest state from `ctx.sessionManager.getBranch()` on `session_start`, `session_switch`, `session_branch`, and `session_tree`, and shows a `BBK` footer/status indicator while active.

For each ordinary user turn in an active session, `before_agent_start` appends a concise `<bbk-session-mode>` system-prompt overlay. The overlay tells the parent to preserve the current BBK workflow and route the request through the named task-agent system:

```text
planning/uncertainty/no executable baseline → bbk_root_wayfinder
accepted execution or recovery baseline     → bbk_root_orchestrator
bounded independent review                  → bbk_reviewer
assertion-scoped acceptance                 → bbk_validator_orchestrator
```

`/bbk <request>` forwards only the raw directive through `sendUserMessage`; it no longer copies the full baseline skill or a large entry-controller prompt into the transcript. `/bbk` with no arguments and `/bbk:exit` perform only local state/UI work and do not trigger a model turn.

The named invocation remains important: it is where the selected OMP agent's `model`, `thinkingLevel`, autoloaded skills, tool policy, native `spawns` restrictions, and return contract take effect. The parent remains user-facing and relays material questions, authority requests, blockers, and final results.

BBK mode does not change the parent model, thinking level, active tools, or sub-agent routes. It also does not replace OMP's native plan or vibe modes; exit a conflicting native mode separately when its restrictions are inappropriate.

## Installed projection surface

- 19 agents, including `bbk_questioning_wayfinder`;
- 21 skills, including `bbk-context-routing`, `bbk-procedure-design`, and the install-bound `bbk-installed-profiles` registry;
- product-neutral reusable role instructions;
- native `spawns` allowlists on every role that may delegate, without duplicating the list in the model-facing prompt;
- profile-aware roles that autoload `bbk-installed-profiles` and `bbk-profile-routing`;
- explicit `model` and `thinkingLevel` on every generated OMP agent;
- 26 tools and 27 commands, including the active `/bbk`, deterministic `/bbk:status`, and interactive `/bbk:models`;
- common constraints for logical-versus-physical topology, explicit context edges, proportional assurance, and append-only evidence exposure.

The packaged model-routing defaults are:

- `judgment`: `openai-codex/gpt-5.6-sol`, high thinking;
- `coordination`: `deepseek/deepseek-v4-pro`, high thinking;
- `mechanical`: `deepseek/deepseek-v4-flash`, high thinking.

A validated external policy can be supplied at install time with `--model-routing PATH`. Model selection is an execution preference. It does not broaden role authority, weaken assurance, prove model availability, or establish that a lower-cost route is adequate for a concrete invocation.

## Interactive sub-agent model menu

```text
/bbk:models
```

The menu lets you view current routes, apply `installation-default`, `default`, `testing-flash`, or `deepseek-economy`, set the model and thinking level for one sub-agent, apply an `omp-model-routing-profile.json` file, or export the effective routing. Only future sub-agent spawns use a changed route; already-running sub-agents continue unchanged.

Headless equivalents are available:

```text
/bbk:models status
/bbk:models profile testing-flash
/bbk:models profile deepseek-economy
/bbk:models set bbk_worker deepseek/deepseek-v4-flash high
/bbk:models apply /path/to/profile.json
/bbk:models export /path/to/profile.json profile-id
```

The installer owns a mutable `effective-omp-model-routing.json` beside the immutable package copy. Applying a route updates only the `model` and `thinkingLevel` frontmatter of installed BBK OMP agents, reconciles their digests and routing metadata into the BBK install manifest, and refuses any locally divergent or unowned agent. Uninstalling and reinstalling restores the installation-time route.

The menu manages BBK-owned frontmatter. OMP `task.agentModelOverrides` has higher model precedence, and a project agent definition has discovery precedence over the same user agent name. Either can supersede the BBK-managed route. `/bbk:models status` reports this boundary. See `docs/MODEL-ROUTING.md` and `templates/omp-model-routing-profile.json`.

## Profile surface

The typed profile-capability surface remains:

```text
bbk_profile_dispatch
/bbk:profile:dispatch
```

Language-profile bundles can now be installed with the core in one verified operation:

```bash
python tools/bootstrap.py --test-and-install --scope user --omp \
  --language-profiles /path/to/bbk-language-profiles.zip
```

The core and declared profile OMP extensions are preflighted together and recorded in one installation manifest. The installer also generates a compact `bbk-installed-profiles` skill from the exact selected packages and writes the complete machine inventory to `effective-language-profiles.json`. OMP agents use that registry to select a profile router before loading focused profile procedures.

## Qualification boundary

Package qualification validates 26 tool registrations and 27 command registrations, including `/bbk:exit`; JavaScript syntax; persistent session-state restoration; footer state; per-turn `before_agent_start` system-prompt overlays; verbatim first-directive forwarding; UI-only deterministic commands; installed-adjacent-CLI behavior; deterministic agent projection; and model-routing bindings. It does not establish live provider/model availability, native OMP mode interoperability, task-agent competence, physical review independence, profile toolchains, or target-project correctness.

## Slash-command and model-context boundary

The extension treats deterministic slash commands as **UI-only** operations. `/bbk:models`, `/bbk:status`, `/bbk:doctor`, `/bbk:exit`, and the other deterministic `/bbk:*` commands show concise notifications and return no structured payload. They do not call `sendMessage` or `sendUserMessage`, so command-result JSON does not enter model context.

Mode state is persisted by `appendEntry`, which is explicitly not model-facing. When the mode is active, `before_agent_start` adds a concise system-prompt overlay for that agent turn; it does not add a transcript message. `/bbk <request>` is the only slash-command path that calls `sendUserMessage`, and it forwards only the request text. Registered BBK tools continue to return structured content because those calls are explicitly initiated by the model.

Update only this OMP surface from a successor package with:

```powershell
python tools/setup.py --test-and-update-omp --scope user
```

The updater preserves the current BBK OMP route and does not modify `.codex` agent files. Run `/reload-plugins` after it completes.
