# BBK — Blueprint Bootstrap Kit

### A practical control layer for agentic engineering

> Most agentic-development systems improve **how the agent behaves**.
>
> BBK helps preserve **what the project means**.

Coding agents are already capable actors. They can inspect a repository, plan work, edit files, run tests, use tools, and delegate to sub-agents. What they do not automatically provide is durable project meaning: a persistent account of the outcome being pursued, what is known, what was decided, who had authority, which implementation was reviewed, what evidence supports acceptance, what later changed, and where work can safely resume.

**BBK—the Blueprint Bootstrap Kit—is an early, host-neutral harness for adding that control discipline to existing agent environments.** It projects planning, orchestration, implementation, validation, and review roles into OMP, Codex, Claude Code, and generic agent hosts; adds structured project records and language profiles; and supplies deterministic tooling for validation, installation, candidate binding, evidence, handoffs, review, and recovery.

BBK is not “a bigger prompt.” It is a working bridge between capable coding agents and the broader Blueprint method.

> [!IMPORTANT]
> BBK is pre-1.0 software. Package qualification establishes the integrity and tested behavior of the package itself. It does **not** prove that a selected model is competent, that a host provides perfect isolation, that two logical roles are physically independent, that an external language toolchain is available, that a target project is correct, or that organizational approval or release authority exists.

The current package version is recorded in [`VERSION`](VERSION), with current release details in [`RELEASE-NOTES.md`](RELEASE-NOTES.md).

---

## The problem BBK is trying to solve

A conventional agent workflow often looks like this:

```text
request → plan → code → tests → “done”
```

That is enough for a great deal of useful work. It becomes fragile when the work is long-running, consequential, uncertain, distributed across several agents, difficult to reverse, or expected to survive beyond the conversation that started it.

BBK applies more structure only where the work justifies it:

```text
requested intervention
  → desired operational outcome
    → facts, assumptions, and open questions
      → decisions, authority, architecture, and interfaces
        → accepted execution baseline
          → bounded work units
            → exact implementation candidate
              → assertion-specific validation and review
                → evidence-bound acceptance
                  → operational outcome check
```

The central idea is simple:

> Agentic engineering needs more than a capable actor and a good prompt. It needs a persistent model of outcomes, decisions, authority, interfaces, execution state, evidence, invalidation, and recovery.

A useful design shorthand is:

> **Models propose; deterministic code commits.**

Models remain responsible for judgment, investigation, design, implementation, and interpretation. Deterministic tooling is used where exactness matters: schema validation, authority and state checks, candidate identity, gate dependencies, manifest comparison, installation ownership, evidence binding, and invalidation.

---

## What changes when you use BBK

### Outcome before intervention

“Build a dashboard” is an intervention. “Help an operator recognize and respond to a developing fault within two minutes” is an outcome. BBK encourages agents to test whether the requested solution is actually fit for the result that matters.

### Facts, assumptions, proposals, and decisions stay distinct

A plausible statement from a model is not automatically a fact. A recommendation is not automatically a decision. A decision is not automatically authorized. BBK keeps those distinctions visible so downstream work does not inherit accidental certainty or authority.

### Planning and execution are separate responsibilities

Planning roles discover, frame, decide, and structure. Execution roles implement an accepted baseline. Material discoveries return to planning rather than being silently absorbed as implementation drift.

### Interfaces matter more than file lists

Parallel agents help only when ownership, contracts, failure behavior, compatibility, and integration obligations are explicit. BBK treats interfaces and responsibility boundaries as first-class architecture.

### Evidence belongs to an exact subject

A green test, review, benchmark, or inspection is meaningful only when it is bound to the exact candidate, environment, context, method, and claim it supports. Change the candidate materially and affected evidence becomes stale.

### Recovery is a state problem, not a memory problem

Interrupted work should resume from durable decisions, active branches, candidates, blockers, checkpoints, handoffs, findings, and evidence—not from whichever summary the last model happened to write.

### Process is proportional

A one-line bug does not need a miniature safety case. BBK’s rule is to use the lightest structure that protects the important claims and boundaries. Routine work can remain mostly inline; consequential or uncertain work earns more explicit artifacts and assurance.

---

## What BBK provides today

BBK currently provides:

- a canonical 19-role system covering recursive Wayfinding, recommendation preparation, focused Grill escalation, planning, architecture, orchestration, bounded implementation, validation, synthesis, and independent review;
- generated host projections for **OMP, Codex, Claude Code, and generic agent environments**;
- explicit role scope, user-interaction boundaries, direct-child delegation triggers, escalation routes, mutation authority, and structured return contracts;
- a modular shared constitution so each role receives the universal rules plus only the planning, coordination, execution, or assurance rules relevant to its work;
- focused procedure autoloading rather than injecting every available skill into every sub-agent;
- durable `.bbk` project records for decisions, question branches, structures, work, authority, assurance, gates, candidates, handoffs, findings, profile locks, status, and related state;
- recommendation-first questioning, with a Question Guide and deep Grill only when a recommendation is rejected, contested, materially ambiguous, or deliberately opened for deeper exploration;
- `SolutionOutcomeFit` for detecting when the requested intervention is not well matched to the desired outcome;
- implementation-structure, execution-slice, work-unit, capability-zone, and State–Decision–Effect methods;
- standing-authority propagation so workers do not repeatedly ask for already-approved effects while remaining unable to broaden their own authority;
- resumable logical worker lifecycles, explicit interruption reasons, durable checkpoints, and lossless handoffs bound by path, byte count, and SHA-256;
- exact candidates, deterministic gate execution, complete file-backed gate streams, evidence receipts, review contexts, findings, and dispositions;
- optional Beads handoff pointers that preserve the verified BBK handoff as the authoritative carrier;
- install-time and OMP runtime model-routing profiles, including balanced defaults, an all-DeepSeek economy route, and an inexpensive all-Flash testing route;
- a persistent OMP BBK mode with `/bbk`, `/bbk:exit`, and `/bbk:models`;
- typed, independently verified language and domain profiles;
- cautious installation, selective OMP or Codex updates, ownership manifests, backups, status, and conservative uninstall;
- ordered verification with visible progress, consolidated test suites, final failure summaries, deterministic release building, and a direct Git-ready source tree.

---

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

Wayfinding maintains the destination, map, actionable frontier, blockers, fog, interfaces, dependencies, invalidation, and stopping economics. Grill is the escalation path: one material question at a time, with factual investigation, a recommendation, reflection, challenge, revision, and explicit convergence or non-resolution.

See [`docs/WAYFINDING-AND-GRILL.md`](docs/WAYFINDING-AND-GRILL.md).

---

## Durable execution and handoffs

BBK treats a host sub-agent turn as one segment of a logical worker lifecycle, not necessarily the entire work unit. Workers continue beyond preflight where possible, checkpoint before likely host boundaries, and return a durable continuation-ready handoff when work cannot finish in one turn.

Authoritative handoffs bind referenced artifacts by:

```text
project-relative path + byte count + SHA-256
```

Large outputs and exact evidence remain in files; chat carries only a compact locator and next action. Configured gate output follows the same rule: complete stdout and stderr are retained as bound files while only bounded previews remain inline.

See [`docs/DURABLE-HANDOFFS.md`](docs/DURABLE-HANDOFFS.md) and [`docs/EXECUTION-DESIGN.md`](docs/EXECUTION-DESIGN.md).

---

## Language profiles

BBK uses profiles for language- and domain-specific procedures, checks, tool guidance, and evidence adapters. The current set covers:

- CODESYS;
- Go;
- Python;
- Rust;
- TypeScript/JavaScript.

Release archives include qualified profile snapshots and install all five by default. The companion [`AccruedInnovation/bbk-language-profiles`](https://github.com/AccruedInnovation/bbk-language-profiles) repository contains their expanded, editable source form.

Profiles specialize how an authorized BBK role performs work. They do not redefine the canonical role topology, broaden authority, waive assurance requirements, or make an unavailable external toolchain available.

See [`docs/LANGUAGE-PROFILES.md`](docs/LANGUAGE-PROFILES.md).

---

## BBK and Blueprint

**Blueprint** is the broader planned local-first semantic planning and execution control plane. Its goal is to represent important project concepts as identity-bearing, related objects rather than leaving them as loose prose across chats and documents.

**BBK** is the practical bootstrap harness available now. It applies much of that philosophy through current agent hosts while the full Blueprint product is still being developed.

```text
Vanilla coding agent
  A powerful actor that can reason and act.

Skills-first methodology
  Instructions and procedures that improve how that actor works.

Spec-first methodology
  Structured documents that make intent drive implementation.

Blueprint
  A project-local semantic and authority system that governs what the work
  means, what is known, who may decide, what may change, what counts as
  evidence, when execution is authorized, and how reality changes the plan.

BBK
  A practical bootstrap harness for applying much of that control discipline
  before the full Blueprint product exists.
```

BBK is deliberately external to the eventual Blueprint product. It does not claim official Blueprint lifecycle, capability, readiness, release, organizational, Tenex, or other institutional authority.

---

## Supported agent hosts

| Host | BBK integration |
| --- | --- |
| **OMP / Oh My Pi** | Extension, persistent BBK mode, model-routing menu, commands, tools, skills, and native task-agent `spawns` metadata |
| **Codex** | Generated custom agents, model and reasoning-effort routing, skills, explicit delegation triggers, and inherited host sandbox settings |
| **Claude Code** | Generated sub-agents, model and effort routing, skills, child-agent allowlists, and bounded coordination-file writes |
| **Generic** | Portable Markdown agent definitions and shared skills for other harnesses |

Host support is an adapter layer. BBK does not require one particular model provider, version-control system, issue tracker, or hosted project service to be the semantic authority.

---

## Quick start

### Requirements

At minimum:

- Python 3.10 or newer for BBK core;
- Git for worktree and repository workflows;
- Node.js when installing or qualifying the OMP extension;
- the selected agent host for live use.

Individual language profiles may require newer Python versions and their own compilers, runtimes, IDEs, simulators, or test tools.

### Verify the repository

```bash
python tools/setup.py --verify
```

This runs package checks, generated-surface drift checks, model-routing validation, Python and JSON sanity checks, semantic fixtures, the consolidated unittest corpus, OMP JavaScript validation when available, and a final mutation check.

### Install BBK

Install for OMP and Codex:

```bash
python tools/setup.py --test-and-install --scope user --omp --codex
```

All bundled language profiles install by default.

Use the expanded sibling profile repository instead of the bundled snapshots:

```bash
python tools/setup.py --test-and-install --scope user --omp --codex --language-profiles ../bbk-language-profiles
```

Install only selected profiles:

```bash
python tools/setup.py --test-and-install --scope user --omp --codex --language-profiles ../bbk-language-profiles --profile-id rust --profile-id python
```

Install core BBK without profiles:

```bash
python tools/setup.py --test-and-install --scope user --omp --codex --no-language-profiles
```

Preview installation without writing:

```bash
python tools/setup.py --test-and-install --scope user --omp --codex --dry-run
```

See [`docs/INSTALL.md`](docs/INSTALL.md) for user/project scopes, selective OMP or Codex updates, external model-routing policies, profile sources, status, and uninstall behavior.

### Begin using BBK in OMP

```text
/bbk          enter persistent BBK mode
/bbk:models   inspect or change sub-agent model routing
/bbk:exit     leave BBK mode
```

Inside BBK mode, ordinary messages are interpreted as part of the continuing governed workflow. The parent session remains user-facing and routes planning, execution, review, and acceptance work to the appropriate named BBK agents.

### Initialize project records

```bash
bbk init --title "Project name"
bbk status
```

The method is designed to scale from mostly inline use to explicit structured records as consequence, uncertainty, duration, and coordination burden increase.

---

## When BBK is worth using

BBK becomes compelling when several of these are true:

- the requested solution may be the wrong intervention;
- the work is long-running, consequential, uncertain, or difficult to reverse;
- implementation crosses software, equipment, operations, data, people, or policy;
- several agents, teams, or authorities must share decisions and interfaces;
- interface behavior and failure modes matter more than individual files;
- review must establish specific claims rather than produce general confidence;
- safety, security, privacy, legal, reliability, or regulatory floors matter;
- later changes must invalidate earlier conclusions correctly;
- execution may be interrupted and resumed by a different agent or person;
- implementation can be complete while the real operational outcome still fails.

A good first BBK pilot is consequential enough to expose real decisions, interfaces, evidence, and resumption—but bounded enough that the team can compare it honestly with its normal workflow.

## When a lighter approach is better

BBK is not automatically the right choice for every task.

A vanilla coding agent, Superpowers, Spec Kit, Compound Engineering, or a focused language skill may be faster when:

- the cause of a small defect is already known;
- the change is local, reversible, and well covered by existing tests;
- the feature is well specified and has few material interfaces;
- the work is a disposable prototype;
- durable authority, evidence, recovery, and operational closure do not justify additional structure.

That is not a failure of BBK. **Proportionality is part of the method.**

---

## Relationship to other agentic-development systems

BBK is best understood as a composable layer, not a demand to replace every useful workflow.

| Layer | Primary responsibility |
| --- | --- |
| **Claude Code, OMP, Codex, Cursor, and similar hosts** | Models, sessions, tools, editing, permissions, hooks, and sub-agent execution |
| **Superpowers and other skills-first methods** | Strong development procedures such as brainstorming, TDD, debugging, worktrees, review, and verification |
| **Spec Kit and other spec-first systems** | Structured specification and intent-to-implementation workflows |
| **Compound Engineering** | Pragmatic plan-build-review-learn loops and repository-local knowledge compounding |
| **Language/domain profiles** | Specialist procedures, checks, tools, and evidence adapters |
| **BBK / Blueprint** | Outcome, meaning, authority, interfaces, execution baseline, candidate identity, evidence, invalidation, recovery, and operational closure |

A mature workflow may use all of these. A Superpowers procedure, Spec Kit artifact, Compound Engineering practice, or language-profile operation can act as a capability provider inside a larger BBK-governed effort.

The distinction is not “more features.” It is center of gravity:

```text
What outcome are we pursuing?
What is known versus assumed?
What was proposed versus actually decided?
Who had authority to decide or authorize it?
What exact baseline was accepted for execution?
What exact candidate was tested or reviewed?
What evidence supports each acceptance claim?
What changed afterward?
Which conclusions are now stale?
Where can execution safely resume?
Did the delivered capability improve the real-world outcome?
```

---

## Repository layout

The extracted package root is the Git source tree. There is no repository-extraction or generated staging step.

```text
spec/                         canonical roles, method content, routing, and schemas
shared/skills/                host-neutral BBK skills
shared/references/            reusable method modules
projections/                  generated Codex, OMP, Claude Code, and generic agents
bundled-language-profiles/    qualified release snapshots of the current profile set
omp/extension/                OMP extension, persistent mode, commands, tools, and model UI
templates/                    project and artifact templates
fixtures/                     positive, negative, and compatibility fixtures
examples/                     worked public examples
tools/                        CLI, validators, installers, generators, and release tooling
tests/                        consolidated contract, assurance, portability, OMP, and system tests
docs/                         current usage, method, architecture, assurance, and maintenance docs
```

Generated files should normally be changed through their canonical inputs rather than edited directly:

```text
spec/roles.json
spec/method-content.json
spec/model-routing.json
```

The relevant generators and drift checks identify projection divergence.

---

## Project state and qualification boundaries

BBK uses deterministic checks to protect exact properties, but determinism does not remove engineering judgment.

BBK can verify that:

- an artifact conforms to a schema;
- a decision records an authority;
- a candidate digest matches the reviewed subject;
- required gates ran in the correct dependency order;
- a package or installation matches its manifest;
- a finding remains open until explicitly dispositioned;
- evidence is stale after a material subject change.

BBK cannot prove that:

- the architecture is wise;
- the selected model is capable enough for the assignment;
- weak evidence is strong;
- a claimed independent review was physically independent;
- an external compiler, simulator, provider, or service behaved correctly;
- a target system is safe, secure, compliant, or fit for operation;
- a human or organization actually granted the authority recorded in an artifact.

Read [`docs/BOUNDARIES.md`](docs/BOUNDARIES.md) before relying on BBK for consequential work. Package-specific qualification and known limits are recorded in [`RELEASE-NOTES.md`](RELEASE-NOTES.md).

---

## Documentation

Start with [`docs/README.md`](docs/README.md), or go directly to:

- [`docs/USAGE.md`](docs/USAGE.md) — day-to-day workflows and the tested Codex multi-agent configuration;
- [`docs/INSTALL.md`](docs/INSTALL.md) — installation, selective updates, profiles, status, and removal;
- [`docs/AGENTS.md`](docs/AGENTS.md) — role contracts, delegation, scope, escalation, and constitution modules;
- [`docs/WAYFINDING-AND-GRILL.md`](docs/WAYFINDING-AND-GRILL.md) — recursive Wayfinding and escalation-only Grill;
- [`docs/EXECUTION-DESIGN.md`](docs/EXECUTION-DESIGN.md) — structure, execution slices, authority, capability zones, and State–Decision–Effect;
- [`docs/DURABLE-HANDOFFS.md`](docs/DURABLE-HANDOFFS.md) — resumable workers, exact carriers, gate streams, and Beads pointers;
- [`docs/ASSURANCE.md`](docs/ASSURANCE.md) — claim-specific review, evidence, findings, independence, and intent conformance;
- [`docs/MODEL-ROUTING.md`](docs/MODEL-ROUTING.md) — model tiers and OMP runtime profiles;
- [`docs/LANGUAGE-PROFILES.md`](docs/LANGUAGE-PROFILES.md) — profile discovery, typed routing, and installation;
- [`docs/SOLUTION-OUTCOME-FIT.md`](docs/SOLUTION-OUTCOME-FIT.md) — outcome and intervention fitness;
- [`docs/BOUNDARIES.md`](docs/BOUNDARIES.md) — authority and qualification limits;
- [`docs/UPGRADING.md`](docs/UPGRADING.md) — durable upgrade guidance;
- [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) — repository maintenance, generation, testing, and release workflow.

---

## Contributing

BBK is still evolving quickly. Issues and pull requests are most useful when they identify:

- the operational outcome or failure mode being addressed;
- the current and expected behavior;
- the affected canonical source rather than only a generated projection;
- compatibility and migration consequences;
- evidence that the change works across the relevant hosts or platforms;
- whether the change belongs in core BBK, a host adapter, or a language/domain profile.

Changes to generated agents should normally begin in the canonical role, method, or routing specifications and include regenerated projections plus drift tests.

A useful contribution does not need to make BBK larger. Removing unnecessary ceremony, duplicated context, brittle assumptions, or unprotected complexity is equally aligned with the project.

See [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md).

---

## Influences and lineage

The Blueprint Method and BBK were developed independently as a broader planning, systems-engineering, execution, and assurance system. Several foundational interaction concepts and names were materially inspired by Matt Pocock’s open-source `grill-me`, `grilling`, and `wayfinder` skills, particularly one-question-at-a-time decision exploration, destination-defined scope, decision maps, actionable frontiers, and fog of war.

Blueprint extends those ideas into recursive responsibility territories, operational framing, interface architecture, implementation-structure contracts, execution slices, proportional assurance, isolated workers, candidate-bound validation, and lifecycle feedback.

Matt Pocock is not affiliated with and has not endorsed this project unless explicitly stated otherwise. I’ll update this if he notices it and lets me say he likes it. :)

---

## License

BBK is released under the [MIT License](LICENSE).
