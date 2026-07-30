# BBK — Blueprint Bootstrap Kit

### A practical control layer for agentic engineering

> Most agentic-development systems improve **how the agent behaves**.
>
> BBK helps preserve **what the project means**.

Coding agents are already capable actors. They can inspect a repository, plan work, edit files, run tests, use tools, and delegate to sub-agents. What they do not automatically provide is durable project meaning: a persistent account of the outcome being pursued, what is known, what was decided, who had authority, which implementation was reviewed, what evidence supports acceptance, what later changed, and where work can safely resume.

**BBK—the Blueprint Bootstrap Kit—is an early, host-neutral harness for adding that control discipline to existing agent environments.** It projects planning, orchestration, implementation, validation, and review roles into OMP, Codex, Claude Code, and generic agent hosts; adds structured project records and language profiles; and supplies deterministic tooling for validation, packaging, installation, candidate binding, evidence, review, and recovery.

BBK is not “a bigger prompt.” It is a working bridge between capable coding agents and the broader Blueprint method.

> [!IMPORTANT]
> BBK is pre-1.0 software. Package qualification establishes the integrity and tested behavior of the package itself. It does **not** prove that a selected model is competent, that a host provides perfect isolation, that two logical roles are physically independent, that an external language toolchain is available, that a target project is correct, or that organizational approval or release authority exists.

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

### Review is claim-specific

“Looks good” is not an assurance strategy. Important assertions receive explicit methods, evidence requirements, applicability rules, and independence expectations. Protected floors such as safety, security, privacy, or reliability cannot be averaged away by strong performance elsewhere.

### Recovery is a state problem, not a memory problem

Interrupted work should resume from durable decisions, active branches, candidates, blockers, deviations, findings, and evidence—not from whichever summary the last model happened to write.

### Process is proportional

A one-line bug does not need a miniature safety case. BBK’s rule is to use the lightest structure that protects the important claims and boundaries. Routine work can remain mostly inline; consequential or uncertain work earns more explicit artifacts and assurance.

---

## What BBK provides today

BBK currently provides:

- a canonical role system covering recursive planning, focused investigation, architecture, orchestration, bounded implementation, validation, synthesis, and independent review;
- generated host projections for **OMP, Codex, Claude Code, and generic agent environments**;
- explicit direct-child delegation contracts and structured return expectations;
- durable `.bbk` project records for decisions, structures, work, assurance, gates, reviews, profile locks, status, and related state;
- `SolutionOutcomeFit` for detecting when the requested intervention is not well matched to the desired outcome;
- implementation-structure, execution-slice, work-unit, and State–Decision–Effect methods;
- exact candidates, deterministic gate execution, evidence receipts, review contexts, findings, and dispositions;
- install-time and OMP runtime model-routing profiles, including economical test and all-DeepSeek routes;
- a persistent OMP BBK mode with `/bbk`, `/bbk:exit`, and `/bbk:models`;
- independently verified language and domain profiles;
- cautious installation, selective host updates, ownership manifests, backups, status, and conservative uninstall;
- deterministic package verification, ordered test execution, reproducible release building, and Git-repository extraction.

The companion **`bbk-language-profiles`** repository contains the editable source form of the current specialist profiles:

- CODESYS;
- Go;
- Python;
- Rust;
- TypeScript/JavaScript.

Profiles add language- or domain-specific procedures, checks, tool guidance, and evidence adapters. They do not redefine the canonical BBK role topology or grant additional authority.

---

## Supported agent hosts

| Host | BBK integration |
|---|---|
| **OMP / Oh My Pi** | Extension, persistent BBK mode, model-routing menu, commands, tools, skills, and native task-agent `spawns` metadata |
| **Codex** | Generated custom agents, model and reasoning-effort routing, skills, and explicit delegation contracts |
| **Claude Code** | Generated sub-agents, model and effort routing, skills, and child-agent allowlists |
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

### Verify the source checkout

```bash
python tools/verify_source_repository.py --require-node
```

A source checkout intentionally has no release `PACKAGE-MANIFEST.json`. This command verifies canonical/generated drift, model routing, Python and JSON sanity, semantic fixtures, the ordered unittest corpus, and OMP JavaScript syntax without pretending the mutable Git working tree is an immutable release archive.

### Install from sibling source repositories

The normal source layout is:

```text
workspace/
├── bbk/
└── bbk-language-profiles/
```

Verify BBK and install it for OMP and Codex with all profiles from the sibling repository:

```bash
python tools/repo_setup.py --test-and-install \
  --scope user \
  --omp --codex
```

`repo_setup.py` auto-detects `../bbk-language-profiles`. An explicit profile source is also supported:

```bash
python tools/repo_setup.py --test-and-install \
  --scope user \
  --omp --codex \
  --language-profiles /path/to/bbk-language-profiles
```

Install only selected profiles:

```bash
python tools/repo_setup.py --test-and-install \
  --scope user \
  --omp --codex \
  --profile-id rust \
  --profile-id python
```

Install core BBK without language profiles:

```bash
python tools/repo_setup.py --test-and-install \
  --scope user \
  --omp --codex \
  --no-language-profiles
```

Preview installation without writing:

```bash
python tools/repo_setup.py --test-and-install \
  --scope user \
  --omp --codex \
  --dry-run
```

Published release archives may bundle exact qualified profile snapshots for self-contained installation. The Git `main` branch does not duplicate those ZIP payloads. See [`docs/INSTALL.md`](docs/INSTALL.md) for release installation, user/project scopes, selective host updates, external model-routing policies, status, and uninstall behavior.

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

The method is designed to scale from mostly inline use to explicit structured records as the consequence, uncertainty, duration, and coordination burden increase.

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
|---|---|
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

```text
spec/                 canonical roles, method content, routing, and schemas
shared/skills/        host-neutral BBK skills
shared/references/    reusable method modules
projections/          generated Codex, OMP, Claude, and generic agents
omp/extension/        OMP extension, mode, commands, tools, and model UI
templates/            project and artifact templates
fixtures/             positive, negative, and compatibility fixtures
examples/             curated public examples
tools/                CLI, validators, installers, generators, and release tools
tests/                behavioral, semantic, portability, and integration tests
docs/                 current usage, method, contributor, and boundary documentation
```

The source repository deliberately excludes bundled language-profile ZIPs, release manifests, checksums, archive audits, full test logs, and version-specific qualification reports. Those are staged for GitHub Releases. The editable profiles live in the companion `bbk-language-profiles` repository.

Generated files should normally be changed through their canonical inputs rather than edited directly:

```text
spec/roles.json
spec/method-content.json
spec/model-routing.json
```

Run the relevant generator and drift checks after canonical changes.

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

See [`docs/QUALIFICATION.md`](docs/QUALIFICATION.md) and [`docs/BOUNDARIES.md`](docs/BOUNDARIES.md) before relying on BBK for consequential work.

---

## Documentation

Start with:

- [`docs/USAGE.md`](docs/USAGE.md) — day-to-day BBK workflows;
- [`docs/INSTALL.md`](docs/INSTALL.md) — source and release installation, updates, profiles, and removal;
- [`docs/AGENT-COMPOSITION.md`](docs/AGENT-COMPOSITION.md) — role, delegation, and host-projection architecture;
- [`docs/MODEL-ROUTING.md`](docs/MODEL-ROUTING.md) — install-time tiers and OMP runtime profiles;
- [`docs/LANGUAGE-PROFILES.md`](docs/LANGUAGE-PROFILES.md) — profile discovery, locking, routing, and repository use;
- [`docs/SOLUTION-OUTCOME-FIT.md`](docs/SOLUTION-OUTCOME-FIT.md) — outcome and intervention fitness;
- [`docs/IMPLEMENTATION-STRUCTURE.md`](docs/IMPLEMENTATION-STRUCTURE.md) — responsibilities, interfaces, slices, and work units;
- [`docs/STATE-DECISION-EFFECT.md`](docs/STATE-DECISION-EFFECT.md) — stateful and effectful system design;
- [`docs/REVIEW-ASSURANCE.md`](docs/REVIEW-ASSURANCE.md) — assurance contracts, context, evidence, findings, independence, and intent;
- [`docs/BOUNDARIES.md`](docs/BOUNDARIES.md) — authority and non-claims;
- [`docs/QUALIFICATION.md`](docs/QUALIFICATION.md) — evergreen source/release verification model;
- [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) — canonical files, generation, tests, and release staging;
- [`docs/UPGRADING.md`](docs/UPGRADING.md) — supported upgrade patterns.

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

---

## Influences and lineage

The Blueprint Method and BBK were developed independently as a broader planning, systems-engineering, execution, and assurance system. Several foundational interaction concepts and names were materially inspired by Matt Pocock’s open-source `grill-me`, `grilling`, and `wayfinder` skills, particularly one-question-at-a-time decision exploration, destination-defined scope, decision maps, actionable frontiers, and fog of war.

Blueprint extends those ideas into recursive responsibility territories, operational framing, interface architecture, implementation-structure contracts, execution slices, proportional assurance, isolated workers, candidate-bound validation, and lifecycle feedback.

Matt Pocock is not affiliated with and has not endorsed this project unless explicitly stated otherwise.

---

## License

BBK is released under the [MIT License](LICENSE).
