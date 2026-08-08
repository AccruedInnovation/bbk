# Alpha.17.0.1 delivery-first execution and prompt compilation

BBK `0.1.0-alpha.17.0.1` is a side-by-side successor to the immutable Alpha.17 final package. It integrates the delivery-first and rolling-wave behavior proven after Alpha.17 promotion and makes prompt/procedure composition a host-neutral, generated surface rather than a Codex-only overlay.

## Delivery-first core semantics

The default operating posture is:

```yaml
planning_mode: FAST_CONTINUATION
architecture_mode: ADOPT_AND_GAP
readiness_target:
  - ROADMAP_READY
  - FRONTIER_READY
future_work_state: DEFERRED_UNTIL_FRONTIER
evidence_policy: CURRENT_UNTIL_INVALIDATED
mechanical_repair: SAME_ATTEMPT
assurance_default: INLINE
specialist_delegation: EXCEPTION_ONLY
validation_policy: SCOPED_AND_CANDIDATE_BOUND
```

A Worker becomes executable when exactly four blocking facts are current:

1. exact WorkUnit, subject, scope, and parent return;
2. applicable authority and effect fence;
3. workspace and mutation ownership or positive serialization;
4. required inputs, toolchain, output carrier, and completion checks.

Planning beyond the first executable frontier is intentionally coarse. A later frontier is refined when it approaches execution; it is not fully compiled merely to make the overall roadmap appear complete.

Routine deterministic Worker and assertion contracts are generated from current semantic records. Worker Designer, Verification Designer, Reviewer, and additional Validators require a named material ambiguity or risk that cannot be resolved by the standard contract, current evidence, or an existing deterministic method.

## Standing delivery authority and user attention

An explicit controlling assignment that adopts an exact baseline and authorizes delivery is the accountable acceptance record for unchanged semantics. BBK does not manufacture another proposal/acceptance loop merely to repeat that decision.

The controller and execution roots continue routine work without requesting another authorization for each frontier, repair, check, candidate freeze, or contained local incident. User interruption is reserved for:

- `MAJOR_BLOCKER` — no safe useful frontier remains and bounded recovery is exhausted, or an unavailable external action is the sole remaining path;
- `ARCHITECTURAL_BRANCH` — multiple materially different viable choices would alter outcomes, capability boundaries, canonical interfaces, protected floors, deployment topology, irreversible migration, or material external commitment.

A blocked individual WorkUnit is not a major blocker while another safe useful frontier remains.

## Active-child command ownership and toolchain state

While a child owns an active WorkUnit, that child is the sole executor of commands capable of affecting that WorkUnit's source, build outputs, dependency state, caches, temporary state, tests, simulators, daemons, or owned processes. Parent orchestrators consume receipts and perform bounded read-only inspection; they route effectful diagnostics to the current owner.

Workspace authority does not implicitly authorize user- or machine-global toolchain state. Package managers, compilers, installers, and commands named `verify`, `doctor`, `audit`, `repair`, `clean`, `prune`, `purge`, `gc`, `sync`, or `update` are treated as potentially effectful until their write roots and process effects are established. Writable cache, temporary, configuration, and log roots default to explicit worktree-local projections. Global caches and configuration are read-only unless a separate authority grant names the exact root and operation.

A contained, fully bounded local-host authority incident may be fenced, recorded, and resumed through a successor physical authority receipt without reopening architecture or semantic planning. Unknown, expanding, external, protected, secret-bearing, physical, or safety-relevant effects remain terminal blockers.

## Host-neutral procedure compiler

Canonical procedure sources remain under `shared/skills/` and are indexed by `spec/procedures/catalog.json`. The compiler resolves one `bbk.prompt-compilation-plan.v1` from:

```text
controller or role required procedures
+ qualified profile required procedures
+ invocation required procedures
+ transitive procedure dependencies
= selected procedure closure
```

The compiler:

1. rejects unknown IDs, duplicate effective bodies, missing sources, and dependency cycles;
2. orders dependencies before their owners;
3. places the primary procedure last;
4. reads each selected canonical source once;
5. compiles one final prompt and one closed procedure tail;
6. removes selected IDs from the effective external catalog;
7. emits one manifest, source map, catalog, plan, and typed event from the same `CompilationResult`;
8. preserves that state for an unchanged logical-child follow-up.

`bbk-wayfind` declares `bbk-plan` as a procedure dependency. Root and Territory Wayfinder projections therefore receive both procedures in every harness without a second model-side skill read.

The generated targets are:

```text
codex
omp
claude
pi
generic   # retained compatibility projection; compiled harness identity is PI
```

Each target receives 19 role projections and one generated controller projection. Harness adapters add only host syntax, tools, runtime facts, and containment; canonical BBK workflow semantics come from the shared compiler.

## Static and invocation-specific compilation

Static role/controller projections contain the required closure known at package generation time. `tools/prompt_compile.py` is the host-neutral invocation adapter for additional qualified profile and invocation procedures:

```bash
python tools/prompt_compile.py compile \
  --request request.json \
  --output-dir compiled-child
```

A request binds the harness, identity, logical child, physical attempt, selected procedures, profile registry revision, tool capabilities, adapter template, and invocation policy. The output directory contains:

```text
prompt.md
compiled-procedure-manifest.json
effective-procedure-catalog.json
prompt-compilation-plan.json
prompt-source-map.json
prompt-compilation-event.json
logical-child-compiled-state.json
```

An unchanged follow-up uses:

```bash
python tools/prompt_compile.py followup \
  --state compiled-child/logical-child-compiled-state.json \
  --request followup.json \
  --output-dir reused-child
```

Reuse fails closed when procedure selection, harness, registry, compiler, base prompt, return contract, model route, tool projection, adapter template, profile registry, effective catalog, or invocation policy changed.

Static projections and the host-neutral compilation API are package-qualified. A host can claim live invocation-selected compilation or follow-up reuse only when its actual child-construction path consumes these artifacts and emits the corresponding runtime event.

## Identity-aware catalogs

Procedure catalog classes are:

- `COMPILED_ONLY` — supplied only through compilation;
- `COMPILER_SELECTABLE` — package-owned sources available to the compiler but not model-discoverable by default;
- `EXTERNAL_OPTIONAL` — physically indexed for model selection when not compiled;
- `HOST_TOOL_ONLY` — host-native procedure/tool surfaces, when defined.

Every controller and role receives its own effective catalog. A compiled procedure and the same external procedure cannot appear in one effective child context.

## Effective prompt order

The semantic order is:

1. harness identity and physical constraints;
2. canonical controller or role contract;
3. shared policy modules;
4. runtime and invocation data;
5. exact return contract;
6. compiled procedure closure;
7. primary procedure last.

No semantic host prose may follow the primary procedure. Structural closing markers are permitted. OMP inserts runtime facts and invocation data before the generated compiled tail and binds a typed event to the actual effective prompt digest.

## Typed observability and qualification

Compilation produces `bbk.prompt-compilation-event.v1` with `PROMPT_COMPILED` or `PROMPT_REUSED`, logical-child and physical-attempt identity, role/controller identity, harness, effective prompt digest, selected procedure IDs, effective catalog digest, compiler source-read count, and model procedure-read count.

The JSONL analyzer and Alpha.17 gate evaluator accept only schema-bound runtime objects and actual collaboration/tool calls. Keywords copied into user, developer, or assistant prose cannot satisfy compilation, reuse, frontier, Worker-start, or completion gates.

`tools/prompt_lint.py` checks all effective controller and role projections for:

- one closed compiled tail;
- primary-last ordering;
- complete and acyclic dependency closure;
- selection/catalog disjointness;
- valid source-map ranges and digests;
- cross-target procedure parity;
- required delivery-first policy;
- absence of known legacy contradictory instructions.

## Assurance and claim limits

The core anti-churn rules apply at every future assurance depth. Stronger assurance adds relevant methods, environments, independence, traceability, and fault coverage; it does not restore repeated handoff verification, complete distant planning, broad metadata-triggered product tests, or automatic successor cycles for mechanical defects.

Alpha.17.0.1 automated package qualification does not transfer Alpha.17's credentialed provider evidence to changed bytes. Live Codex, OMP, Claude Code, and Pi behavior remains separately qualified. In particular, static projection generation and the host-neutral invocation compiler do not by themselves prove that every external host invokes dynamic compilation on every child launch or follow-up.
