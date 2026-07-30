# Sub-agent model routing

BBK `0.1.0-alpha.11.11` separates a role's responsibility from the model used to perform it.

The canonical default policy is:

```text
spec/model-routing.json
```

It is intentionally separate from `spec/roles.json`:

- `roles.json` defines stable responsibilities, authority, skills, spawning, and return contracts;
- `model-routing.json` defines replaceable cost/capability profiles and maps each role to one profile;
- `tools/generate_agents.py` combines both inputs into host-native agent definitions;
- `projections/manifest.json` (`bbk.projection-manifest.v4`) binds the role catalogue, routing policy, all 76 generated files, per-role constitution modules, scope, direct-child topology and triggers, escalations, user-interaction boundaries, full and autoload skill sets, model profiles, host routes, and filenames by digest.

## Default profiles

| Profile | OMP | Codex | Claude Code | Default use |
|---|---|---|---|---|
| `judgment` | `openai-codex/gpt-5.6-sol`, `thinkingLevel: high` | `gpt-5.6-sol`, `model_reasoning_effort: high` | `opus`, `effort: high` | planning, architecture, synthesis, assurance, review, root-level orchestration |
| `coordination` | `deepseek/deepseek-v4-pro`, `thinkingLevel: high` | `gpt-5.6-terra`, `model_reasoning_effort: medium` | `sonnet`, `effort: medium` | research, prototyping, and bounded execution coordination |
| `mechanical` | `deepseek/deepseek-v4-flash`, `thinkingLevel: high` | `gpt-5.6-luna`, `model_reasoning_effort: low` | `haiku`, `effort: low` | tightly bounded leaf work and exact assertion evaluation |

The DeepSeek V4 OMP defaults use `high` in both bundled cost profiles. The economical distinction comes primarily from model choice. OMP remains authoritative for the thinking levels supported by the selected provider/model, and a user-supplied selector may use another supported level.

The default role allocation is:

```text
judgment
  bbk_root_wayfinder
  bbk_territory_wayfinder
  bbk_questioning_wayfinder
  bbk_planning_wayfinder
  bbk_phase_wayfinder
  bbk_question_guide
  bbk_synthesizer
  bbk_architect
  bbk_verification_designer
  bbk_worker_designer
  bbk_reviewer
  bbk_root_orchestrator

coordination
  bbk_researcher
  bbk_prototyper
  bbk_territory_orchestrator
  bbk_worker_orchestrator
  bbk_validator_orchestrator

mechanical
  bbk_worker
  bbk_validator
```

These are defaults, not claims that a model is sufficient for every invocation. Assignment complexity, consequence, uncertainty, context size, tool use, model availability, organizational policy, and live host behavior may justify an override or escalation. In particular, a worker or validator receiving judgment-heavy work should be promoted rather than forced through the economical tier.

## Prompt and metadata boundary

Model-facing instructions contain operational content only: purpose, constitution, responsibilities, prohibitions, applicable procedure/profile guidance, non-OMP delegation guidance, invocation contract, and return contract. BBK no longer spends context tokens on repeated title banners, canonical role labels, host-projection labels, model-profile labels, generated-file notices, or role/routing digests.

Those values remain auditable elsewhere:

- OMP, Codex, and Claude Code keep required name/model/effort/skills/tool fields in native configuration or frontmatter;
- `projections/manifest.json` keeps canonical provenance, file digests, role skills, `spawns`, model-profile allocation, and all host routes;
- generic installations keep the effective custom route and topology in `.agents/bbk/agent-manifest.json` beside prompt-only agent files;
- `effective-model-routing.json` and the install manifest bind any external install-time override.

Removing metadata from the prompt does not remove it from qualification or installation evidence.

## Host fields

BBK emits the host-native keys requested by each target:

```text
OMP:         model, thinkingLevel
Codex:       model, model_reasoning_effort
Claude Code: model, effort
```

OMP model values may be a direct selector such as `deepseek/deepseek-v4-flash` or one of the configured role aliases:

```text
@default  @smol  @slow  @vision  @plan
@designer @commit @tiny @task    @advisor
```

BBK deliberately validates host model and effort values as non-empty strings rather than freezing a host catalogue into the package. The target host remains authoritative for currently accepted identifiers, aliases, effort levels, model capability clamps, organizational allowlists, and runtime override precedence.

## Change OMP routes at runtime

An OMP installation exposes an interactive routing menu:

```text
/bbk:models
```

The menu can inspect the BBK-managed routes, apply a packaged profile, edit any one sub-agent, apply an external profile file, or export the current routing. OMP rediscovers task-agent definitions when a sub-agent is spawned, so future BBK spawns use the changed `model` and `thinkingLevel`; already-running sub-agents are unaffected. Do not apply a profile while a new BBK spawn is being launched.

The bundled runtime profiles are:

| Profile | Behavior |
|---|---|
| `installation-default` | Restore the exact OMP routes selected at installation, including an external install-time policy. |
| `default` | Restore BBK's packaged judgment/coordination/mechanical defaults. |
| `testing-flash` | Route all 19 BBK sub-agents through `deepseek/deepseek-v4-flash` with high thinking for low-cost functional testing. |
| `deepseek-economy` | Use DeepSeek V4 Pro for judgment and coordination roles and V4 Flash for mechanical roles. |

The same operations are scriptable from OMP:

```text
/bbk:models status
/bbk:models profile testing-flash
/bbk:models profile deepseek-economy
/bbk:models set bbk_worker @task medium
/bbk:models apply D:\Profiles\my-bbk-routing.json
/bbk:models export D:\Profiles\current-bbk-routing.json current-bbk
```

They are also available through the installed helper:

```powershell
python "$HOME/.omp/agent/extensions/bbk/omp_model_routing.py" status
python "$HOME/.omp/agent/extensions/bbk/omp_model_routing.py" apply-profile testing-flash
```

Project-scope paths live under `.omp/extensions/bbk/` instead. The extension discovers authenticated OMP models for its menu and also accepts direct selectors and the aliases `@default`, `@smol`, `@slow`, `@vision`, `@plan`, `@designer`, `@commit`, `@tiny`, `@task`, and `@advisor`. When OMP cannot currently resolve a selector, the interactive menu warns before saving it; this permits preparing a route before the provider or alias is configured without falsely reporting live availability.

Runtime changes are BBK-installation state, not edits to the sealed package. BBK rewrites only the `model` and `thinkingLevel` fields of affected installed BBK OMP agents, writes `effective-omp-model-routing.json`, and reconciles the corresponding digests and routing metadata into the BBK install manifest. It verifies every managed agent and state file against the manifest before changing anything and refuses a locally modified or unowned agent instead of overwriting it. Consequently, `tools/install.py status` remains current and conservative uninstall still recognizes the active routes. Uninstalling and reinstalling, or a reviewed forced replacement, restores the selected installation policy.

### OMP precedence boundary

The menu manages BBK-owned agent frontmatter. It does not mutate OMP's global or project settings. OMP resolves a spawned agent's model in this order:

1. `task.agentModelOverrides[agentName]`;
2. the selected agent definition's `model` frontmatter;
3. the parent-session model.

OMP also discovers project agent definitions before user agent definitions. Therefore an OMP task override, or a higher-precedence project `.omp/agents/<role>.md` definition with the same role name, can supersede the route displayed by `/bbk:models status`. BBK reports this boundary in status and apply results rather than claiming exclusive control over OMP routing. Use OMP's own agent/settings surfaces to remove an intentional higher-precedence override.

### Build reusable OMP profiles

Copy the compact template:

```text
templates/omp-model-routing-profile.json
```

Its `default` route applies to every canonical role, and `roles` contains only exceptions. Validate and apply it through the OMP menu or helper:

```powershell
python tools/omp_model_routing.py --binding C:\path\to\bbk-package-root.json apply-file D:\Profiles\my-bbk-routing.json
```

The schema is `spec/schemas/omp-model-routing-profile.schema.json`. A custom profile is bound to one BBK package version so additions or renames in the canonical role catalogue cannot silently inherit an unintended route.

## Validate the packaged default

```bash
python tools/model_routing.py --check
python tools/model_routing.py --json
python tools/generate_agents.py --check
```

`model_routing.py` verifies:

- the `bbk.model-routing.v1` structure;
- package-version binding;
- complete and exact coverage of all canonical roles;
- valid profile references;
- required host objects and fields;
- non-empty host values.

The JSON Schema is `spec/schemas/bbk-model-routing-v1.schema.json`. Cross-role coverage and package binding are enforced by `tools/model_routing.py`, because they depend on the live canonical role catalogue.

An external policy is intentionally bound to one BBK release through `package_version`. When upgrading BBK, start from the successor package's policy (or update and revalidate the external copy) so changed role catalogues cannot be accepted silently.

## Customize without modifying the qualified package

Do not edit the extracted package merely to change model selection if package verification matters. Any package edit correctly causes `tools/verify_package.py --strict-mode` to report drift.

Instead, copy the default policy outside the package:

```powershell
Copy-Item .\spec\model-routing.json D:\Projects\BBK\my-model-routing.json
```

Edit the copy, then validate it:

```powershell
python tools/model_routing.py --path D:\Projects\BBK\my-model-routing.json --check
```

Preview installation with the external policy:

```powershell
python tools/install.py install `
  --scope user `
  --omp --codex --claude `
  --model-routing D:\Projects\BBK\my-model-routing.json `
  --dry-run
```

Install it:

```powershell
python tools/install.py install `
  --scope user `
  --omp --codex --claude `
  --model-routing D:\Projects\BBK\my-model-routing.json
```

The installer:

1. validates the complete policy before creating an installation directory or writing any host file;
2. renders all selected host projections in memory from canonical roles and the selected policy;
3. leaves the verified package tree unchanged;
4. writes an auditable copy to the installation root as `effective-model-routing.json`;
5. records the source, effective copy, canonical policy digest, combined projection-input digest, profile count, and role allocation in the install manifest;
6. records exact digests for every installed agent.

A project-local installation uses the same option:

```bash
python tools/install.py install \
  --scope project \
  --root /path/to/repository \
  --omp --codex --claude \
  --model-routing /path/to/model-routing.json
```

If different BBK agents or an earlier routing policy are already installed, the cautious installer refuses divergent destinations. Uninstall the previous BBK installation first, or use `--force` after reviewing the dry run; forced replacement creates digest-bound backups.

## Make a one-role exception

Profiles are reusable by design. To change one role without changing every role assigned to a profile:

1. copy the nearest profile under a new name;
2. change that profile's host settings;
3. map only the selected role to the new profile.

For example, a locally configured mechanical profile may route OMP through `@tiny` at low effort while leaving every other role unchanged:

```json
{
  "profiles": {
    "mechanical-local": {
      "description": "Local economical profile.",
      "omp": {
        "model": "@tiny",
        "thinkingLevel": "low"
      },
      "codex": {
        "model": "gpt-5.6-luna",
        "model_reasoning_effort": "low"
      },
      "claude": {
        "model": "haiku",
        "effort": "low"
      }
    }
  },
  "role_profiles": {
    "bbk_worker": "mechanical-local"
  }
}
```

The real file must retain every other profile and all 19 role mappings; the excerpt shows only the relevant addition and reassignment.

## Authority and runtime behavior

Model routing changes expected execution capability, latency, and cost. It does not grant authority, mutate role boundaries, waive review independence, alter allowed effects, or prove model fitness.

Generated prompts state that host-, organization-, session-, or invocation-level policy may override the packaged defaults. Claude Code, Codex, and OMP can each apply runtime precedence, availability rules, capability clamps, or version-specific behavior beyond BBK's static files. Inspect the host's actual session metadata when exact model use matters, and report an unavailable, rejected, silently inherited, or materially downgraded route rather than representing it as the requested configuration.

An unknown role, missing role, unknown profile, missing host object, missing field, empty value, malformed JSON, or package-version mismatch blocks generation and installation before host files are changed.

## Menu output and model-context isolation

`/bbk:models` is an interactive UI command. Applying, editing, viewing, importing, or exporting a route shows a concise `ctx.ui.notify` summary and returns no slash-command payload. The extension does not use `sendMessage` or `sendUserMessage` for model-routing operations, so the route JSON, agent inventory, and CLI details are not added to model context. Use the installed `omp_model_routing.py --json ...` helper when machine-readable output is actually required.

This boundary also applies to deterministic core and bundled language-profile slash commands. LLM-callable tools are intentionally different: their structured result is model-facing because the model invoked the tool.

An OMP-only successor update can preserve the active routing state:

```powershell
python tools/setup.py --test-and-update-omp --scope user
```

It rewrites future OMP agent definitions with the preserved `model` and `thinkingLevel`, updates the OMP extension and bundled profile extensions, and does not modify `.codex` agent files. Run `/reload-plugins` after the update.

