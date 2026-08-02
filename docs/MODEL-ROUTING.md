# Sub-agent model routing

BBK `0.1.0-alpha.13.1` separates each role's stable responsibility from the model used to perform it.

The canonical install-time policy is `spec/model-routing.json`. It uses `"schema_version": "bbk.model-routing.v2"` and contains one complete OMP, Codex, and Claude Code route for every canonical role. Exact coverage is required: a missing role and an unknown role both fail validation.

The alpha.13 defaults are the reviewed selections supplied with the split-role update. They are copied into the canonical policy, generated projections, packaged OMP `default` runtime profile, and a regression fixture. The only change from that reviewed source is advancing `package_version` to `0.1.0-alpha.13.1`.

## Default per-role routes

Identical values are grouped here only for readability. These groups are not schema objects or semantic categories; every role remains independently editable.

| Roles | OMP | Codex | Claude Code |
|---|---|---|---|
| Root Wayfinder, Question Guide, Planning Wayfinder, Phase Wayfinder, Architect, Verification Designer, Worker Designer, Root Orchestrator, Reviewer | `openai-codex/gpt-5.6-sol`, `thinkingLevel: high` | `gpt-5.6-sol`, `model_reasoning_effort: high` | `opus`, `effort: high` |
| Territory Wayfinder, Questioning Wayfinder, Synthesizer | `openai-codex/gpt-5.6-sol`, `thinkingLevel: medium` | `gpt-5.6-sol`, `model_reasoning_effort: medium` | `opus`, `effort: high` |
| Researcher, Prototyper, Worker Orchestrator | `deepseek/deepseek-v4-flash`, `thinkingLevel: max` | `gpt-5.6-luna`, `model_reasoning_effort: xhigh` | `sonnet`, `effort: medium` |
| Territory Orchestrator | `openai-codex/gpt-5.6-luna`, `thinkingLevel: xhigh` | `gpt-5.6-luna`, `model_reasoning_effort: xhigh` | `sonnet`, `effort: medium` |
| Validator Orchestrator | `openai-codex/gpt-5.6-sol`, `thinkingLevel: medium` | `gpt-5.6-sol`, `model_reasoning_effort: medium` | `sonnet`, `effort: medium` |
| Worker, Validator | `deepseek/deepseek-v4-flash`, `thinkingLevel: max` | `gpt-5.6-luna`, `model_reasoning_effort: xhigh` | `haiku`, `effort: high` |

These are starting points, not claims that a model is sufficient for every invocation. Consequence, uncertainty, context size, tool use, model availability, organizational policy, and live host behavior may require an invocation-level override or escalation.

## Canonical source and generated projections

The role and routing sources have distinct ownership:

```text
spec/roles/catalog.json             role-package metadata, ordering, topology, roots, and parent modes
spec/roles/bbk_*-role.json          19 canonical role definitions
spec/roles.json                     generated compatibility projection; do not edit
spec/model-routing.json             exact route for each role and host
spec/omp-model-routing-profiles.json packaged OMP runtime profiles
```

`tools/assemble_roles.py` validates and assembles the split role package. `tools/generate_agents.py` combines the generated role projection, method content, prompt modules, exact return contracts, and model-routing policy to create host-native definitions.

`projections/manifest.json` uses `bbk.projection-manifest.v8`. It binds the split role sources, prompt-module assignments, primary procedures, exact role-return schemas, routing policy, generated files, and source digests.

## Host fields

BBK emits the host-native keys requested by each target:

```text
OMP:         model, thinkingLevel
Codex:       model, model_reasoning_effort
Claude Code: model, effort
```

BBK validates these as non-empty strings rather than freezing a host model catalogue into the package. The target host remains authoritative for accepted identifiers, aliases, effort levels, capability clamps, organization allowlists, and runtime precedence.

OMP model values may be direct selectors such as `deepseek/deepseek-v4-flash` or configured aliases such as:

```text
@default  @smol  @slow  @vision  @plan
@designer @commit @tiny @task    @advisor
```

## Validate a policy

```bash
python tools/model_routing.py --check
python tools/model_routing.py --json
python tools/create_role_spec.py --check
python tools/generate_agents.py --check
```

The validator checks:

- direct-role `bbk.model-routing.v2` structure, or legacy v1 compatibility structure;
- exact package-version binding;
- complete and exact coverage of the live 19-role catalogue;
- required host objects and fields;
- non-empty model and effort/thinking values; and
- v1 profile-reference integrity when a legacy policy is supplied.

Schemas:

```text
spec/schemas/bbk-model-routing-v2.schema.json
spec/schemas/bbk-model-routing-v1.schema.json    # compatibility only
```

Cross-role coverage and package binding are enforced by `tools/model_routing.py`, because they depend on the live role catalogue and release version.

## Customize without modifying the qualified package

Copy the canonical v2 file outside the extraction and edit only the desired role entries:

```powershell
Copy-Item .\spec\model-routing.json D:\Profiles\bbk-model-routing.json
python tools\model_routing.py --path D:\Profiles\bbk-model-routing.json --check
python tools\install.py install --scope user --omp --codex --claude `
  --model-routing D:\Profiles\bbk-model-routing.json --dry-run
python tools\install.py install --scope user --omp --codex --claude `
  --model-routing D:\Profiles\bbk-model-routing.json
```

The external file's `package_version` must be `0.1.0-alpha.13.1`. The installer validates it before writing, renders the selected projections from that policy, copies it to `effective-model-routing.json`, and binds its digest into `install-manifest.json`.

Do not edit generated files under `projections/` directly. Drift checks reject manual changes.

## Legacy v1 compatibility

`bbk.model-routing.v1` did not reserve the names `judgment`, `coordination`, and `mechanical`; any profile key matching `^[a-z][a-z0-9_-]*$` was valid if every role referenced a defined profile and the rest of the policy validated. Alpha.13 retains read and install-time validation compatibility with v1 policies.

V2 remains preferred because it removes profile indirection. A role route can be tuned without inventing a category or moving other roles assigned to it.

## Prompt and metadata boundary

Model-facing instructions contain operational content: role identity, authority, interaction topology, scope, prompt modules, role-specific procedure, invocation contract, and exact return contract. Build and routing provenance remains in native host fields and `projections/manifest.json`.

Codex `developer_instructions` deliberately contain no BBK XML-like metadata envelopes. Prompt modules and the primary procedure use plain Markdown headings. OMP retains authenticated marker blocks because its extension uses them to distinguish canonical BBK child definitions from untrusted prompt text before replacing the native child system prompt.

## OMP runtime profiles are separate

The install-time v2 policy defines all host projections. OMP also supports reusable runtime profiles for changing only installed OMP `model` and `thinkingLevel` values after installation:

```text
/bbk:models
```

Packaged runtime profiles are:

| Profile | Behavior |
|---|---|
| `installation-default` | Restore the exact OMP routes selected at installation, including an external v2 or legacy v1 policy. |
| `default` | Restore alpha.13's reviewed packaged per-role OMP routes. |
| `testing-flash` | Route all 19 BBK OMP children through `deepseek/deepseek-v4-flash` for inexpensive functional testing. |
| `deepseek-economy` | Use DeepSeek routes for a cost-conscious OMP configuration. |

Commands:

```text
/bbk:models status
/bbk:models profile testing-flash
/bbk:models profile deepseek-economy
/bbk:models set bbk_worker @task medium
/bbk:models apply D:\Profiles\my-omp-routing.json
/bbk:models export D:\Profiles\current-omp-routing.json current-bbk
```

Runtime changes affect future OMP child spawns only. BBK rewrites managed OMP agent frontmatter, writes `effective-omp-model-routing.json`, and reconciles ownership digests into the install manifest. Already-running children are unaffected.

### OMP precedence boundary

The menu manages BBK-owned agent frontmatter. It does not mutate OMP global or project settings. OMP resolves a spawned agent's model in this order:

1. `task.agentModelOverrides[agentName]`;
2. the selected agent definition's `model` frontmatter;
3. the parent-session model.

Project agent definitions also precede user definitions. A task override or higher-precedence project definition can therefore supersede the route shown by BBK. `/bbk:models status` reports this boundary rather than claiming exclusive control.

## Upgrade an external policy

An external policy is bound to one BBK release. Update `package_version` to `0.1.0-alpha.13.1`, compare its role keys and host fields with the new canonical policy, and validate it before installation. Alpha.13 retains the same 19 role names but materially changes the role package, return contracts, prompt composition, and generated projection digests, so installed agents must be regenerated rather than copied from alpha.12.4.
