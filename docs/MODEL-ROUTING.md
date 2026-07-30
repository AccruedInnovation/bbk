# Model routing

BBK separates stable role responsibility from replaceable model selection.

```text
spec/roles.json          role responsibilities and topology
spec/model-routing.json  cross-host model and effort defaults
```

The generator combines both inputs into host-native agent definitions.

## Default tiers

BBK uses reusable cost/capability tiers, typically:

- `judgment` for planning, architecture, synthesis, assurance, review, and root orchestration;
- `coordination` for bounded implementation and orchestration;
- `mechanical` for tightly bounded collection and exact assertion work.

The actual model identifiers and effort settings are versioned configuration, not semantic role definitions.

## Host fields

```text
OMP:         model, thinkingLevel
Codex:       model, model_reasoning_effort
Claude Code: model, effort
```

Host aliases and direct selectors remain subject to the live host's available model catalogue and policy.

## Validate or customize install-time routing

```bash
python tools/model_routing.py --check
python tools/model_routing.py --json
```

Copy the policy outside the repository before customization:

```bash
cp spec/model-routing.json ../my-model-routing.json
python tools/model_routing.py --path ../my-model-routing.json --check
```

Pass it to the installer with `--model-routing`.

## OMP runtime profiles

OMP can change future BBK task-agent routes without changing the parent session:

```text
/bbk:models
/bbk:models status
/bbk:models apply testing-flash
/bbk:models apply deepseek-balanced
/bbk:models set bbk_worker @tiny low
/bbk:models reset
```

Runtime routing changes the higher-precedence BBK task-agent definitions and records managed state. It does not grant authority, change already-running agents, or override a still-higher project/local OMP configuration.

## Sufficiency and escalation

A default route is not proof that the model is sufficient for every invocation. Escalate when consequence, uncertainty, context size, tool use, or architectural judgment exceeds the nominal role tier.

## Current packaged defaults

The current cross-host defaults are:

| Tier | OMP | Codex | Claude Code |
|---|---|---|---|
| `judgment` | `openai-codex/gpt-5.6-sol`, `thinkingLevel: high` | `gpt-5.6-sol`, `model_reasoning_effort: high` | `opus`, `effort: high` |
| `coordination` | `deepseek/deepseek-v4-pro`, `thinkingLevel: high` | `gpt-5.6-terra`, `model_reasoning_effort: medium` | `sonnet`, `effort: medium` |
| `mechanical` | `deepseek/deepseek-v4-flash`, `thinkingLevel: high` | `gpt-5.6-luna`, `model_reasoning_effort: low` | `haiku`, `effort: low` |

These values are execution defaults only. The canonical role catalogue and projection provenance remain in `projections/manifest.json`, outside model-facing prompt text.
