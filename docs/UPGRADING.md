# Upgrading BBK

Use a clean extraction for each BBK version. Do not overlay a new release onto an older extracted package.

## Upgrade to `0.1.0-alpha.15`

`0.1.0-alpha.15` is a product-first workflow and deterministic packaging release over alpha.14. Use a clean extraction and the managed installer or selective updater; do not copy generated roles, skills, extension files, schemas, or routing files into an older extraction.

For a complete managed upgrade:

```bash
python tools/setup.py --test-and-install --scope user --omp --codex --claude --generic
```

Reload OMP and start fresh Codex/Claude parent sessions after updating generated prompts. The exact 19 reviewed model routes, `testing-flash`, `deepseek-economy`, install scopes, and bundled language-profile versions are unchanged. Existing user/project routing states remain distinct.

No `.bbk/` project-record migration is required. Existing `bbk.handoff.v1`, `bbk.role-return.v1`, artifact manifests, review records, Beads mappings, and external routing policies remain consumable. New constructors prefer sealed handoff v2, role-return v2, and generated context packages. External routing policies must set `package_version` to `0.1.0-alpha.15` and be revalidated before installation.

Alpha.15 adds:

- product-first proportional workflow and INLINE/FOCUSED/FULL assurance;
- strict JSON and deterministic sealed artifact packages;
- project-local OMP routing creation, status, dry-run repair, and profile application;
- role-return v2 COMPACT/FULL contracts for all 19 roles;
- generated Worker and candidate-bound review contexts;
- requirement-scoped host preflight;
- compact/full prototype charter v2; and
- sealed handoff v2 with v1 compatibility.

Alpha.15 does **not** add a global deterministic lifecycle, acceptance, authorization, candidate, review-invalidation, release, ACL, or lease engine. Blueprint remains the intended owner of those system-wide responsibilities.

## Upgrade to `0.1.0-alpha.13.5`

`0.1.0-alpha.13.5` is a test-only portability corrective over alpha.13.4. It does not change BBK runtime behavior, project records, role prompts, model selections, or language-profile packages. It corrects a Windows verification assertion that treated long-name and 8.3 spellings of the same physical project path as different strings.

Use a clean extraction. For a complete managed upgrade:

```bash
python tools/setup.py --test-and-install --scope user --omp --codex --claude
```

Existing alpha.13.4 installations do not require replacement solely for runtime correctness. Alpha.13.5 is required when using the verification-first setup path on a Windows host affected by the alias spelling mismatch.

No `.bbk/` record migration is required.

## Upgrade to `0.1.0-alpha.13.4`

`0.1.0-alpha.13.4` is a test/verification and install-reconciliation corrective over alpha.13.3. It preserves the alpha.13.3 project/runtime behavior and reviewed model routes.

Use a clean extraction. Do not overlay release package directories. For a complete managed upgrade:

```bash
python tools/setup.py --test-and-install --scope user --omp --codex --claude
```

Routine `--test` and `--test-and-install` use the standard product/integration/platform profile. Release authors use:

```bash
python tools/setup.py --release-test --require-node
```

All selected bundled or external language-profile packages are still fully authenticated before mutation. When the installed profile identity, package-root digest, layout, harness selection, owned bytes, and modes already match, alpha.13.4 reuses those files in place rather than reinstalling them. Changed or locally divergent files retain the previous conservative refusal/backup/`--force` behavior.

No `.bbk/` record migration is required. Start a fresh Codex session after changing its generated agents and run `/reload-plugins` after changing OMP files.

## Upgrade to `0.1.0-alpha.13.3`

`0.1.0-alpha.13.3` is a bounded corrective over alpha.13.2. It preserves alpha.13.2's Beads defaults, project-scoped OMP routing, nested-agent view, canonical roles, return/execution contracts, prompt modules, language profiles, and reviewed model routes.

Use a clean alpha.13.3 extraction or the supported installer/update entrypoints. Do not copy selected extension, role, skill, routing, or generated-agent files into an older package.

### Managed update

For a full managed update, select the harnesses you use:

```bash
python tools/setup.py --test-and-install --scope user --omp --codex --claude --generic
```

For OMP only:

```bash
python tools/setup.py --test-and-update-omp --scope user
```

For Codex only:

```bash
python tools/setup.py --test-and-update-codex --scope user
```

Reload OMP after updating:

```text
/reload-plugins
```

### Child-lifetime behavior

All alpha.13.3 OMP BBK agents explicitly declare `blocking: false`. On OMP 16.4.8, they use managed background jobs when `async.enabled=true` and an `AsyncJobManager` is available. If the host runs task children inline, BBK's shared callback-sequencing rules avoid combining an immediate human response with a cancellation-sensitive child wait.

BBK does not override a user's global OMP asynchronous-execution policy. See `OMP-CHILD-LIFETIME.md` for the exact native and fallback boundaries.

### Existing projects

No `.bbk/` project-record migration is required.

- `EXAMPLE-*` files remain in place but are excluded from live counts, automatic discovery, default project manifests, and candidate inputs.
- `bbk status --root <existing-empty-directory>` now returns a successful `UNINITIALIZED` result with an explicit `bbk init` next action.
- Existing Beads mappings are preserved.
- Existing project/user routing state is preserved and remains separately scoped.

### External model-routing policies

The 19 reviewed default routes are unchanged. An external routing policy remains release-bound: set its `package_version` to `0.1.0-alpha.13.3`, preserve exact role coverage, and validate it before installation:

```bash
python tools/model_routing.py validate --policy /path/to/model-routing.json
```

Do not carry an alpha.13.1 or alpha.13.2 generated agent file forward manually. Regenerate/install from alpha.13.3 so prompt-module assignments, OMP `blocking: false`, version bindings, and projection digests remain congruent.

### Unicode and Windows paths

The OMP adapter now forces strict UTF-8 Python transport. The installer and runtime routing resolver compare physical path identity, including long-name/8.3 aliases, rather than requiring identical textual spellings.

A genuine project mismatch still fails closed; these changes do not permit one project's command to mutate another project's routing state.

### Source patch use

The release may provide patches from alpha.13.1 and alpha.13.2 for source review and exact reconstruction. They are not a supported substitute for clean extraction or the managed installer on a live installation.

## Upgrade to `0.1.0-alpha.13.2`

`0.1.0-alpha.13.2` is a corrective OMP and coordination release over alpha.13.1. Use a clean alpha.13.2 extraction or the supported installer/update entrypoints; do not copy selected extension, role, skill, routing, or generated-agent files into an older package.

The release keeps the alpha.13 canonical role, return-contract, execution-contract, and prompt-module packages, and adds three operational changes:

- Beads is enabled as the normal writable coordination projection for newly initialized BBK projects. BBK files remain authoritative, the external `bd` executable is still required for applied projection, and foreign drift fails closed rather than being overwritten. Execution handoffs can target the exact mapped project, territory, or WorkUnit without translating BBK state into tracker status.
- OMP model-routing commands resolve the nearest valid project-scoped BBK installation by default. Explicit `project` and `user` targets are available; an invalid expected project binding does not silently fall back to user scope.
- `/bbk:agents` reconstructs and retains the complete nested BBK agent hierarchy from OMP progress and finalized task details, including synchronous descendants that do not appear in detached-only activity lists.

Existing projects are not silently rewritten. To adopt the normal Beads defaults, update `.bbk/config.json` and `.bbk/mappings/beads.json` deliberately or initialize a new project with alpha.13.2. A project may still set `enabled` or `write_enabled` to `false` when tracker projection is inappropriate.

### OMP-only update

A user-scoped OMP installation can be updated without modifying Codex:

```powershell
python tools\setup.py --test-and-update-omp --scope user
```

For project-isolated routing, install or update OMP in each project:

```powershell
python tools\install.py install --scope project --root D:\Projects\ProjectA --omp
python tools\install.py install --scope project --root D:\Projects\ProjectB --omp
```

After updating a running OMP session, run `/reload-plugins`. Model-profile changes affect future child spawns only; already-running agents retain the model with which they started.

### External model-routing policies

An external routing policy remains release-bound. Set its `package_version` to `0.1.0-alpha.13.2`, preserve exact coverage of all 19 roles, and validate it before installation:

```powershell
python tools\model_routing.py --path D:\Profiles\bbk-model-routing.json --check
```

Alpha.13.2 preserves the reviewed per-role model selections introduced in alpha.13; only release metadata changes.

### Verification

```powershell
python tools\verify_package.py --strict-mode
python tools\run_tests.py -q --jobs 0
```

The default test runner executes the eight consolidated suites in a bounded process pool while ordinary canonical BBK CLI calls run in-process inside each suite. Tests that require interpreter flags, process semantics, Node, Git, stdin, timeouts, or modified scripts retain real subprocess boundaries.

## Alpha.13 formalizes split roles, returns, execution contracts, and prompt modules

`0.1.0-alpha.13.1` is a role-package and generated-prompt migration. Use a clean alpha.13 extraction; do not copy selected role or skill files into an alpha.12.4 package.

The role source of truth changes from one editable `spec/roles.json` file to:

```text
spec/roles/catalog.json
spec/roles/bbk_*-role.json
```

`spec/roles.json` remains present only as a deterministic generated compatibility projection. External role consumers must support `bbk.roles.v4`, the four controller-selectable roots, allowed parent modes, expected child-return modes, prompt-module assignments, and exact role-return contracts. `projections/manifest.json` advances to `bbk.projection-manifest.v8`.

Alpha.13 also changes the generated prompt composition. Shared behavior is sourced from 21 prompt modules, while each current role has one primary mandatory procedure. Do not preserve an external rule that every role must have at most three mandatory procedures; alpha.13 permits additional procedures only through a measured, source-bound catalogue exception.

The alpha.13 default model routes are the reviewed per-role selections in `spec/model-routing.json`. Do not carry forward alpha.12.4 routes by changing only `package_version`. Copy the alpha.13 policy, reapply intentional role-level changes, compare every role, and validate the result. In particular, the qualified defaults include OMP Flash/max, OMP/Codex Luna/xhigh, Codex Sol/medium, Claude Sonnet/medium, Claude Haiku/high, and Claude Opus/high routes where assigned.

No `.bbk/` project-record migration is required solely for alpha.13. Existing project records remain subject to their own schema and freshness checks.

For a full managed upgrade:

```bash
python tools/setup.py --test-and-install --scope user --omp --codex --claude
```

Accept the managed clean-replacement prompt, or select `--uninstall-existing` explicitly in noninteractive automation. All five language profiles remain installed by default; use `--no-language-profiles` or repeated `--profile-id` options to change that set.

For a harness-scoped update after the alpha.13 extraction passes the matching verification profile:

```bash
python tools/setup.py --test-and-update-omp --scope user
python tools/setup.py --test-and-update-codex --scope user
```

Run `/reload-plugins` after updating OMP. Begin a fresh Codex turn or session if the host cached custom-agent definitions. Existing OMP runtime model-menu state is preserved by the selective OMP updater, while `installation-default` is rebound to the alpha.13 install-time routes.

Current role writers use typed operational dispositions and a separate role-specific semantic state. Existing legacy `bbk.handoff.v1` records containing `READY_FOR_VALIDATION`, `BLOCKED`, or `PAUSED` remain readable, but current handoff creation rejects those values. Role-result and complete role-return schemas live under `spec/schemas/role-results/` and `spec/schemas/role-returns/`.

`TerritoryExecutionBoundary` and the local-discovery policy/envelope/permit are schema-defined companion contracts; they do not create a lease-backed runtime mutation fence beyond implemented host capabilities. `WorkerValidationBatch` is retired. Use a candidate-producing cohort and a distinct candidate-bound assurance run linked by immutable candidate identity.

## Alpha.12.4 added per-role routing and harness-scoped clean replacement

`0.1.0-alpha.12.4` changes the canonical install-time model policy to `bbk.model-routing.v2`: every one of the 19 roles has independent OMP, Codex, and Claude Code routes. Legacy v1 policies remain accepted, including caller-defined profile names, but v2 is the preferred format. Copy the new `spec/model-routing.json`, adjust individual role entries, set its `package_version` to `0.1.0-alpha.12.4`, and validate it before installation.

Alpha.12.4 also corrects `--uninstall-existing` scope. Against a multi-harness install, selecting exactly one already-installed `--omp` or `--codex` harness now clean-replaces only that harness and preserves all other harness files and ownership records:

```bash
python tools/setup.py --install --scope user --omp --uninstall-existing
python tools/setup.py --install --scope user --codex --uninstall-existing
```

Selecting every installed harness still performs a full clean replacement. Unsupported partial combinations fail before removal. Shared routing or language-profile changes require a full replacement; harness-scoped replacement preserves them.

Codex projections no longer place BBK XML-like role or inlined-skill metadata tags in `developer_instructions`. Mandatory procedure bodies remain present under plain Markdown headings, while provenance stays in native TOML fields and `bbk.projection-manifest.v6`. Start a fresh Codex session after updating its agent definitions.

Preferred selective successor commands remain:

```bash
python tools/setup.py --test-and-update-omp --scope user
python tools/setup.py --test-and-update-codex --scope user
```

Reload OMP with `/reload-plugins` after an OMP update. No `.bbk/` project-record migration is required solely for alpha.12.4.

## Alpha.12.3.1 makes the existing-install question visible in PowerShell

`0.1.0-alpha.12.3.1` preserves alpha.12.3's verification bounds and diagnostics and alpha.12.2's OMP activity widget, ask-backed decision channel, canonical prompts, and managed-install behavior. It terminates the interactive default-Yes replacement question with a newline so line-oriented PowerShell/native-command output cannot buffer the prompt invisibly while Python waits for input.

Use a clean alpha.12.3.1 extraction. For an OMP-only successor update:

```bash
python tools/setup.py --test-and-update-omp --scope user
```

The OMP-focused profile intentionally skips the complete portability suite. To validate the fixed test harness, run:

```bash
python tools/run_tests.py -v
```

Each unittest module now has a 300-second default hard limit, suite and real behavior-test children cannot read the developer console, nested subprocesses have local limits, and a still-running heartbeat names the latest visible test. For a serial diagnostic transcript:

```bash
python tools/run_tests.py -v --mode isolated --jobs 1 -p test_installation_portability.py --suite-timeout 300
```

No `.bbk/` project-record migration is required solely for alpha.12.3.1.

## Alpha.12.2 adds OMP activity, ask-backed decisions, and managed replacement

`0.1.0-alpha.12.2` does not change alpha.12's role catalogue, authority topology, mandatory-skill injection, or `hub`/IRC parent channel. It adds one persistent OMP `BBK · ready`/worker activity-context widget, requires the Main controller to use OMP `ask` for ADR-bearing user decisions, tolerates only harmless host presentation whitespace when authenticating canonical child prompts, and detects an existing managed install before an ordinary full installation. It also retains alpha.12.1's profile-test isolation and separation of ordinary harness updates from release-author qualification.

For a normal interactive full install from a clean alpha.12.2 extraction, the installer reports the existing installation and asks whether to uninstall it first. The default is Yes. The successor is preflighted before removal, unowned files are preserved, and locally modified manifest-owned files require `--force` so they can be backed up before removal.

For automation, select the policy explicitly:

```bash
python tools/setup.py --test-and-install --scope user --omp --codex --uninstall-existing
python tools/setup.py --test-and-install --scope user --omp --codex --keep-existing
```

JSON, dry-run, and noninteractive installs default to `--keep-existing` semantics rather than inferring approval. In alpha.12.2 through alpha.12.3.1, a full clean replacement installed only the selected harness set; alpha.12.4 supersedes that behavior for single-harness OMP/Codex selections with a harness-scoped replacement that preserves unselected harnesses.

The full verification path remains available and remains the required release/CI path:

```bash
python tools/setup.py --test --require-node
```

Selective tested updates now run package trust/drift checks plus only the relevant harness regression surface:

```bash
python tools/setup.py --test-and-update-omp --scope user
python tools/setup.py --test-and-update-codex --scope user
```

Use `python tools/run_tests.py -v --mode isolated --jobs 1` to force serial module-isolated execution during diagnosis. No `.bbk/` project-record migration is required from alpha.12, alpha.12.1, or alpha.12.2 solely because of this update.

## Alpha.12 is a prompt-authority migration

`0.1.0-alpha.12` is intentionally a major alpha revision rather than an alpha.11 patch. It changes how BBK is projected and executed across supported harnesses:

- the visible harness root is the sole user-facing controller;
- all 19 canonical BBK roles, including the four named roots, execute as non-user-facing children;
- mandatory procedure bodies are injected directly into generated role prompts;
- OMP replaces the assembled system prompt for both the persistent `/bbk` controller and marked BBK child agents;
- OMP child-to-controller communication uses `hub`/IRC, while Codex and Claude Code use their available parent/inter-agent return channel;
- role metadata and projection-manifest schemas advance to their alpha.12 forms.

These changes apply to **new turns and newly spawned agents after the host reloads the updated installation**. A child already running under an alpha.11 prompt does not acquire the alpha.12 authority or communication contract retroactively. Finish or cancel old work deliberately, reload the host integration, and start a fresh governed root invocation before relying on alpha.12 behavior.

No `.bbk/` project-record migration is required solely because of this release. Preserve existing records, validate them with the alpha.12 CLI, and let the new root role determine whether any active baseline or evidence became stale for substantive reasons.

## Full managed upgrade

From the new extraction:

```bash
python tools/setup.py --test-and-install --scope user --omp --codex --claude
```

Accept the default clean-replacement prompt. In noninteractive automation, append `--uninstall-existing`. Manual uninstall from the previous extraction remains available but is no longer required for an ordinary managed upgrade.

All bundled language profiles install by default. Add `--no-language-profiles` for an intentional core-only installation or repeated `--profile-id` options for a subset.

After installation:

- reload OMP plugins with `/reload-plugins`, then leave and re-enter `/bbk` if the current session had BBK mode active;
- start a fresh Codex session so projected agent definitions and parent-channel rules are reloaded;
- start a fresh Claude Code main session so generated agent frontmatter and prompt bodies are reloaded.

## Selective host updates

Update OMP without modifying the installed Codex or Claude Code agents:

```bash
python tools/setup.py --test-and-update-omp --scope user
```

Update Codex agents without modifying OMP or Claude Code:

```bash
python tools/setup.py --test-and-update-codex --scope user
```

Use the corresponding non-test form only after the exact extraction has already passed verification. Alpha.12's OMP extension and generated OMP agents form one prompt contract, so an OMP-only update must install both; do not copy only `index.js` or only the agent files.

## Project records

A release note will state explicitly when `.bbk/` project-record migration is required. In the absence of such a statement, preserve the records and validate them with the new CLI before continuing consequential work.

Prompt replacement does not erase project authority. The alpha.12 controller and child prompts consume the current project state, accepted baselines, plans, assignment context, and exact caller result schema; they do not silently upgrade or authorize those records.

## External routing policies

External model-routing files are package-version-bound. Update their `package_version` to the installed BBK version and validate them before use:

```bash
python tools/model_routing.py --path /path/to/model-routing.json --check
```

Do not assume an older policy is safe merely because all role names still exist. For v2, compare every direct role entry with the new canonical policy; for legacy v1, revalidate every role-to-profile mapping. Regenerate installed projections so prompt digests, mandatory-skill digests, and model routes are bound together.

## External policies and generated projections

Any external organizational policy that validates BBK's role catalogue, projection manifest, user-interaction flags, or skill-autoload metadata must be updated for:

- `bbk.roles.v4`, including split source files, controller roots, parent modes, and exact return contracts;
- `bbk.projection-manifest.v8`, including prompt-module assignments and role-return metadata;
- `mandatory_skills`, reusable prompt modules, and inlined-procedure digests;
- `human_decision_triggers`;
- the non-user-facing canonical-role topology.

Fail closed rather than translating old `interactive`, `user_interaction`, or `autoload_skills` fields heuristically.
