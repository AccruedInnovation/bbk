# BBK — Blueprint Bootstrap Kit

### Structured planning, delegation, execution, and review for coding agents

> **Make your agents work as a team without losing the plan.**
>
> BBK gives coding agents a durable way to plan, delegate, execute, review, recover, and keep long-running work on track.

Coding agents can already inspect a repository, plan work, edit files, run tests, use tools, and spawn sub-agents. What they often lack is durable project state: what outcome matters, what is known, what was decided, who may change what, which implementation was reviewed, what evidence supports it, and where work should resume after a context or agent boundary.

**BBK adds that control layer to Codex, OMP, Pi, Claude Code, and generic agent hosts.** It combines structured roles, durable project records, model routing, language profiles, resumable handoffs, deterministic checks, and evidence-bound review.

BBK is not a bigger system prompt. It is a host-neutral harness for making multi-agent engineering work more structured, durable, and efficient.

## Try BBK with Codex

From the BBK repository, check the Codex dependency set:

```bash
python tools/setup.py --check-dependencies --codex
```

When the check reports missing BBK dependencies, install them through the explicit opt-in bootstrap, then install BBK:

```bash
python tools/setup.py --install-dependencies --codex
python tools/setup.py --install --scope user --codex
```

The dependency command asks for consent before it changes system or user tools. Then use Codex normally. BBK installs generated custom agents, skills, delegation rules, and model/reasoning routing for the Codex host.

BBK also supports OMP / Oh My Pi, Pi, Claude Code, and portable generic agent definitions. See [Installation](#installation) for other setups.

> [!IMPORTANT]
> BBK is pre-1.0 software. Its package checks verify BBK's own tested properties; they do not prove that a model is capable, a host is perfectly isolated, an outside toolchain works, a target project is correct, or an organization has granted authority to release or operate a system.

The current version is recorded in [`VERSION`](VERSION). See [`RELEASE-NOTES.md`](RELEASE-NOTES.md) for release details.

---

## Why BBK?

A normal agent workflow often looks like:

```text
request → plan → code → tests → done
```

That works well for small, clear jobs. It gets less reliable when work is long-running, uncertain, split across agents, hard to reverse, or too large for one context window.

BBK adds structure where it helps:

- **Keep the outcome in view.** Test whether the requested solution actually serves the result that matters.
- **Separate facts, assumptions, proposals, and decisions.** Do not let plausible model output silently become project truth.
- **Separate planning from execution.** Workers implement an accepted baseline instead of redesigning it as they go.
- **Make delegation explicit.** Give each agent a role, scope, authority, return contract, and escalation path.
- **Route work by cost and judgment.** Use stronger models where judgment matters and cheaper models for bounded or mechanical work.
- **Keep state outside the chat.** Persist decisions, work units, candidates, blockers, findings, handoffs, and evidence in the project.
- **Resume interrupted work.** Continue from durable state instead of reconstructing the project from a conversation summary.
- **Bind review to the exact implementation.** Know which candidate a test, benchmark, or review actually supports.
- **Use deterministic checks where exactness matters.** Models make judgments; code checks identities, schemas, state, gates, manifests, evidence, and invalidation.
- **Keep the process proportional.** Small changes stay light; risky or complex work gets more structure.

The core design rule is:

> **Models make judgments; deterministic code binds identity, state, and gates.**

---

## What BBK provides

BBK currently includes:

- a canonical **19-role agent system** for wayfinding, planning, architecture, orchestration, implementation, validation, synthesis, and independent review;
- generated host integrations for **Codex, OMP, Pi, Claude Code, and generic agents**;
- explicit delegation triggers, agent scope, authority limits, escalation paths, and return contracts;
- per-role **model routing** for Codex, OMP, and Claude Code, plus default, economy, and low-cost OMP runtime profiles;
- durable `.bbk` records for decisions, work, authority, gates, candidates, handoffs, findings, evidence, and status;
- resumable worker lifecycles with durable checkpoints and handoffs;
- deterministic validation, candidate binding, gate execution, evidence receipts, review contexts, and invalidation;
- typed language and domain profiles for **Go, Python, Rust, and TypeScript/JavaScript**;
- optional Beads handoff pointers;
- cautious install, update, backup, status, verification, and uninstall tooling;
- a persistent BBK mode for OMP with `/bbk`, `/bbk:models`, and `/bbk:exit`.

For the full method and internal contracts, see [`docs/README.md`](docs/README.md).

---

## Supported agent hosts

| Host               | BBK integration                                                                                                               |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------- |
| **Codex**          | Generated custom agents, model and reasoning-effort routing, skills, delegation triggers, and inherited host sandbox settings |
| **OMP / Oh My Pi** | Extension, persistent BBK mode, model-routing menu, commands, tools, skills, and native task-agent spawning metadata          |
| **Pi**             | Generated Markdown agents, shared skills, and an external agent manifest for Pi-compatible hosts                              |
| **Claude Code**    | Generated sub-agents, model and effort routing, skills, child-agent allowlists, and bounded coordination-file writes          |
| **Generic**        | Portable Markdown agent definitions and shared skills for other harnesses                                                     |

BBK sits above the host. It does not tie project meaning to one model provider, issue tracker, or hosted project service. Current repository and worktree flows require Git. BBK resolves its pinned jj and Beads tools through mise.

---

## Installation

### Requirements and dependency setup

BBK requires **Python 3.11 or newer**. Python is the one bootstrap requirement that BBK cannot install because it runs the setup command.

Check the exact dependencies for a Codex install without downloading or changing anything:

```bash
python tools/setup.py --check-dependencies --codex
```

Preview the dependency plan, then install the missing BBK dependencies after explicit consent:

```bash
python tools/setup.py --install-dependencies --codex --dry-run
python tools/setup.py --install-dependencies --codex
```

Use `--yes` only for reviewed, non-interactive automation.

The opt-in dependency installer can install Git, mise, the pinned `jj@0.43.0` and Beads `1.1.0` tools, and BBK's compatible Python runtime packages. The root `mise.toml` contains only those core tools. OMP also needs Node.js; select OMP to install the separate OMP-only `node@22.23.2` pin through mise:

```bash
python tools/setup.py --install-dependencies --omp
```

**Codex-only verification does not require Node.** Codex-only installation has no Node dependency either. The Node pin lives in `tools/omp-runtime.mise.toml`, whose non-default name keeps it out of ordinary root mise tasks. Node is required only when OMP is selected or when the standard or release profile checks all hosts. The dependency script does not install Codex, OMP, Pi, Claude Code, or other agent hosts. Install the host you plan to use separately.

Normal install, test, and update commands run the same dependency preflight before tests or file writes. The preflight does not download or install tools and does not write BBK installation files. It disables mise auto-install and network access, then exits with exact repair guidance when a required tool is missing. Language profiles may still require their own compilers, runtimes, IDEs, simulators, or test tools.

### Codex

```bash
python tools/setup.py --install --scope user --codex
```

### OMP / Oh My Pi

```bash
python tools/setup.py --install --scope user --omp
```

### Pi

```bash
python tools/setup.py --install --scope user --pi
```

### Claude Code

```bash
python tools/setup.py --install --scope user --claude
```

### Generic agents

```bash
python tools/setup.py --install --scope user --generic
```

### More than one host

Combine host flags as needed:

```bash
python tools/setup.py --install --scope user --omp --codex
```

When no host flag is supplied, the installer selects Codex, OMP, Pi, Claude Code, and generic agents. That full selection includes OMP and therefore requires Node. All bundled language profiles are installed by default.

Run a host-focused test without installing:

```bash
python tools/setup.py --test --codex
python tools/setup.py --test --omp
```

Test before installing:

```bash
python tools/setup.py --test-and-install --scope user --codex
```

To replace the bundled profile source with the expanded companion repository (currently Go, Python, Rust, and TypeScript/JavaScript):

```bash
python tools/setup.py --install --scope user --codex --language-profiles ../bbk-language-profiles
```

To install selected profiles only:

```bash
python tools/setup.py --install --scope user --codex --language-profiles ../bbk-language-profiles --profile-id rust --profile-id python
```

To install core BBK without profiles:

```bash
python tools/setup.py --install --scope user --codex --no-language-profiles
```

To preview an install without writing:

```bash
python tools/setup.py --install --scope user --codex --dry-run
```

See [`docs/INSTALL.md`](docs/INSTALL.md) for supported package managers, dependency boundaries, project and user scopes, selective host updates, external routing policies, profile sources, status, and uninstall behavior.

### OMP BBK mode

```text
/bbk          enter persistent BBK mode
/bbk:models   inspect or change sub-agent model routing
/bbk:exit     leave BBK mode
```

Inside BBK mode, the parent session stays user-facing and routes planning, execution, review, and acceptance work to the right BBK agents.

### Project records

```bash
bbk init --title "Project name"
bbk status
```

BBK scales from mostly inline use to explicit structured records as consequence, uncertainty, duration, and coordination needs increase.

---

## How BBK approaches agent work

### Outcome before intervention

“Build a dashboard” is an intervention. “Help an operator recognize and respond to a developing fault within two minutes” is an outcome. BBK asks agents to check whether the requested solution fits the result that matters.

### Recommendation before deep questioning

For material decisions, BBK first asks a Questioning Wayfinder to investigate what it can and prepare a recommendation. A deeper Question Guide / Grill is used only when the recommendation is rejected, contested, still materially unclear, or the user asks for deeper exploration.

See [`docs/WAYFINDING-AND-GRILL.md`](docs/WAYFINDING-AND-GRILL.md).

### Durable execution and handoffs

A host sub-agent turn can be one part of a longer logical worker lifecycle. Workers checkpoint before likely host boundaries and return continuation-ready handoffs when they cannot finish in one turn.

Authoritative handoffs bind referenced artifacts by:

```text
project-relative path + byte count + SHA-256
```

Large outputs and full gate logs stay in files; chat carries a compact locator and next action.

See [`docs/DURABLE-HANDOFFS.md`](docs/DURABLE-HANDOFFS.md) and [`docs/EXECUTION-DESIGN.md`](docs/EXECUTION-DESIGN.md).

### Evidence belongs to an exact candidate

A passing test, benchmark, inspection, or review only supports the exact subject it evaluated. If that subject changes in a material way, BBK can mark the affected evidence stale.

See [`docs/ASSURANCE.md`](docs/ASSURANCE.md).

---

## Language profiles

BBK profiles add language- and domain-specific procedures, checks, tool guidance, and evidence adapters. The current bundled set covers:

- Go
- Python
- Rust
- TypeScript/JavaScript

Release archives install the bundled profiles by default. The companion [`AccruedInnovation/bbk-language-profiles`](https://github.com/AccruedInnovation/bbk-language-profiles) repository contains expanded editable source for the same profile set.

Profiles specialize how a BBK role performs authorized work. They do not change the role system, broaden authority, waive assurance requirements, or make an unavailable toolchain available.

See [`docs/LANGUAGE-PROFILES.md`](docs/LANGUAGE-PROFILES.md).

---

## When BBK is worth using

BBK is most useful when some of these are true:

- the requested solution may not be the right intervention;
- work will span many agent turns or context windows;
- several agents need clear ownership and interfaces;
- work is uncertain, consequential, or hard to reverse;
- the implementation crosses several systems or domains;
- review must support specific claims rather than general confidence;
- safety, security, privacy, legal, reliability, or regulatory constraints matter;
- work may stop and later resume with another agent or person;
- a later change must invalidate an earlier conclusion correctly;
- completing the implementation does not by itself prove the real outcome improved.

For a small, local, reversible change with clear tests, a vanilla coding agent or a lighter method may be faster. BBK is designed to add only the structure the job needs.

---

## BBK and other agent workflows

BBK is a control layer, not a demand to replace every other useful method.

| Layer                                                  | Main job                                                                                                                       |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| **Codex, OMP, Pi, Claude Code, Cursor, and similar hosts** | Models, sessions, tools, editing, permissions, hooks, and sub-agent execution                                                  |
| **Skills-first methods**                               | Development procedures such as debugging, TDD, review, and verification                                                        |
| **Spec-first systems**                                 | Structured specification and intent-to-implementation workflows                                                                |
| **Language/domain profiles**                           | Specialist procedures, checks, tools, and evidence adapters                                                                    |
| **BBK / Blueprint**                                    | Outcomes, decisions, authority, interfaces, execution state, candidate identity, evidence, invalidation, recovery, and closure |

A skill, spec, or domain procedure can run inside a larger BBK-governed effort.

---

## BBK and Blueprint

**Blueprint** is the broader planned local-first planning and execution control system. Its goal is to represent important project concepts as durable, related objects rather than leaving them as loose prose across chats and documents.

**BBK** is the practical bootstrap harness available now. It brings much of that approach to current coding-agent hosts while Blueprint is still being built.

BBK remains separate from the eventual Blueprint product and does not claim Blueprint lifecycle, readiness, release, organizational, Tenex, or other institutional authority.

---

## Repository layout

```text
spec/                         canonical roles, method content, routing, and schemas
shared/skills/                host-neutral BBK skills
shared/references/            reusable method modules
projections/                  generated Codex, OMP, Pi, Claude Code, and generic agents
bundled-language-profiles/    qualified release snapshots
omp/extension/                OMP extension, commands, tools, mode, and model UI
templates/                    project and artifact templates
fixtures/                     positive, negative, and compatibility fixtures
examples/                     worked public examples
tools/                        CLI, validators, installers, generators, and release tooling
tests/                        contract, assurance, portability, OMP, and system tests
docs/                         usage, method, architecture, assurance, and maintenance docs
```

Generated projections should normally be changed through their canonical inputs rather than edited directly.

---

## Qualification boundaries

BBK uses deterministic checks for properties that software can check exactly.

BBK can verify things such as:

- schema conformance;
- recorded decision authority;
- candidate identity;
- gate dependency order;
- package and installation manifests;
- finding disposition state;
- evidence invalidation after material changes.

BBK cannot prove that an architecture is wise, a chosen model is capable enough, evidence is strong, reviewers are physically independent, outside tools behaved correctly, a target system is safe or compliant, or a human or organization truly granted recorded authority.

Read [`docs/BOUNDARIES.md`](docs/BOUNDARIES.md) before relying on BBK for consequential work.

---

## Documentation

Start with [`docs/README.md`](docs/README.md), or go directly to:

- [`docs/USAGE.md`](docs/USAGE.md) — operating guide, day-to-day workflows, host behavior, and tested Codex multi-agent use
- [`docs/INSTALL.md`](docs/INSTALL.md) — installation, updates, profiles, status, and removal
- [`docs/AGENTS.md`](docs/AGENTS.md) — roles, delegation, scope, escalation, and shared rules
- [`docs/WAYFINDING-AND-GRILL.md`](docs/WAYFINDING-AND-GRILL.md) — wayfinding and deep-question escalation
- [`docs/EXECUTION-DESIGN.md`](docs/EXECUTION-DESIGN.md) — work structure, authority, and execution slices
- [`docs/DURABLE-HANDOFFS.md`](docs/DURABLE-HANDOFFS.md) — resumable workers and exact handoffs
- [`docs/ASSURANCE.md`](docs/ASSURANCE.md) — review, evidence, findings, and intent checks
- [`docs/MODEL-ROUTING.md`](docs/MODEL-ROUTING.md) — model tiers and routing profiles
- [`docs/LANGUAGE-PROFILES.md`](docs/LANGUAGE-PROFILES.md) — language and domain profiles
- [`docs/SOLUTION-OUTCOME-FIT.md`](docs/SOLUTION-OUTCOME-FIT.md) — matching solutions to outcomes
- [`docs/BOUNDARIES.md`](docs/BOUNDARIES.md) — authority and qualification limits
- [`docs/UPGRADING.md`](docs/UPGRADING.md) — upgrade guidance
- [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) — maintenance, generation, testing, and releases

---

## Contributing

BBK is still evolving quickly. Issues and pull requests are especially useful when they include:

- the outcome or failure mode being addressed;
- current and expected behavior;
- the affected canonical source, not only a generated projection;
- compatibility or migration effects;
- evidence that the change works on the relevant hosts or platforms;
- whether the change belongs in BBK core, a host adapter, or a language/domain profile.

Changes to generated agents should normally begin in the canonical role, method, or routing specifications and include regenerated projections plus drift tests.

Removing needless process, duplicate context, brittle assumptions, or unprotected complexity is as useful as adding features.

See [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md).

---

## Influences and lineage

The Blueprint Method and BBK were developed independently as a broader planning, systems-engineering, execution, and assurance system. Several interaction ideas and names were materially inspired by Matt Pocock's open-source `grill-me`, `grilling`, and `wayfinder` skills, including one-question-at-a-time decision exploration, destination-defined scope, decision maps, actionable frontiers, and fog of war.

Blueprint extends those ideas into recursive responsibility territories, operational framing, interface architecture, implementation-structure contracts, execution slices, proportional assurance, isolated workers, candidate-bound validation, and lifecycle feedback.

Matt Pocock is not affiliated with and has not endorsed this project unless explicitly stated otherwise.

---

## License

BBK is released under the [MIT License](LICENSE).
