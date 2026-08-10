# Changelog

## 0.1.0-alpha.17.0.2.1 — 2026-08-09

- Publish the Windows qualification hotfix as a clean source successor to Alpha.17.0.2.
- Fix the PowerShell clean-replacement path using native `GetConsoleMode` detection; redirected and `NUL` stdin now fail safe without entering `msvcrt`.
- Decompose the qualification suite into focused modules with structured ledgers and receipts.
- Record authoritative Windows calibration and pooled execution coverage across 61 modules and 756 outcomes.
- Remove the obsolete `HOTFIX-ALPHA17.0.2-WINDOWS.md` companion note from the package surface while retaining release history and external evidence.
- Align canonical version metadata, generated projections, templates, qualification-kit identity, and exact-version regression fixtures on `0.1.0-alpha.17.0.2.1`.

## 0.1.0-alpha.17.0.2

- Removed the retired internal `IMPLEMENTATION-MAPPING-CHECKLIST-COMPLETED.md` artifact and its stale evidence references from the public package.

- Corrected native Windows qualification isolation: runtime mise resolution is now explicit/PATH-only, batch-launcher assertions understand `cmd.exe /c`, byte-exact fixtures force LF, and real-mise qualification uses isolated Windows and mise state directories with network/auto-install/lockfile effects disabled.
- Corrected the PowerShell clean-replacement prompt: native input now requires a real `GetConsoleMode` console handle, redirected or `NUL` stdin never enters `msvcrt`, setup preserves genuine interactive stdin, and unreadable confirmation fails safe to reconciliation.
- Added native Windows module-duration weights, kept high-core hotspots separated across six pooled processes, bound retained timings to their operating system, and excluded failed or timed-out singleton runs from the cache.
 — 2026-08-07

- Set Python 3.11 as the package-wide minimum; enforce it at the setup, install, update, CLI, verification, test-runner, release, and package entry points, and declare it for the standalone JSONL analyzer.
- Add a single host-aware dependency contract for Git, mise, pinned `jj@0.43.0`, Beads `1.1.0`, runtime `jsonschema` and `referencing`, and Node.js only when OMP is selected.
- Add `tools/setup.py --check-dependencies` as an offline, non-installing preflight that disables mise network and automatic-install paths, checks exact managed versions through `mise which`, and blocks before tests or destination access.
- Add the explicit `tools/setup.py --install-dependencies` bootstrap. After user consent it can use supported Windows, macOS, and Linux package managers for Git and mise, install pinned managed tools through mise, and install compatible Python runtime packages through the active interpreter. Host apps and language-profile toolchains remain separate.
- Pin the OMP-managed Node runtime in non-default `tools/omp-runtime.mise.toml`, keep Node out of root mise tasks, accept a compatible direct Node.js 22+ runtime, and remove Node from every Codex-only install, update, dependency, and verification path.
- Add focused Codex and OMP setup profiles; standard and release remain cross-host profiles and declare their Node requirement. Guard host-specific tests so missing unrelated host tools cause a clear skip or preflight block instead of a raw process error.
- Make Windows batch verification execute only the modules selected for the active profile, avoiding unused host imports and broad-discovery startup cost.
- Prevent dependency probes from causing mise downloads or tool installs, reject unsupported Windows `PATHEXT` source-file matches, and correct aggregate doctor status for all blocked dependency states.
- Audit tool imports and copied OMP runtime modules so every third-party Python package and package-local import is declared and tested.
- Make native Windows CI provision and verify the same Git, mise, jj, Beads, Python-package, and OMP Node dependency contract used by setup rather than relying on runner-image tools.
- Align the README, installation, usage, development, upgrade, release, and qualification guidance with the Python floor, opt-in bootstrap, host-app boundary, and Codex/OMP dependency split.

## 0.1.0-alpha.17.0.1 — 2026-08-07

- Replace the former root README with the concise public BBK overview, consolidate its operating detail into `docs/USAGE.md`, and reorganize the documentation index around user, method, host, release-record, and maintainer paths.
- Reconcile current documentation with the package: five install targets, 19 roles, 43 prompt modules, 40 shared skills, projection manifest v10, 58 OMP model tools, 48 OMP UI commands, mixed profile versions, and current critical-path skill sizes.
- Keep volatile route tables, install detail, and verification commands in their canonical focused guides; update documentation tests to check those ownership boundaries.
- Preserve the exact promoted Alpha.17 runtime and add delivery-first continuation as a side-by-side successor rather than modifying the final bytes.
- Make `FAST_CONTINUATION`, `ADOPT_AND_GAP`, `ROADMAP_READY + FRONTIER_READY`, and `DEFERRED_UNTIL_FRONTIER` the canonical rolling-wave planning model.
- Add standing delivery authority, `MAJOR_BLOCKER` / `ARCHITECTURAL_BRANCH` user-attention boundaries, active-child effect ownership, worktree-local toolchain-state projection, contained authority-incident recovery, and bounded coordination-message budgets.
- Add a v2 host-neutral procedure registry with `bbk-wayfind -> bbk-plan` dependency closure and identity-aware `COMPILED_ONLY`, `COMPILER_SELECTABLE`, `EXTERNAL_OPTIONAL`, and `HOST_TOOL_ONLY` catalog classes.
- Compile controllers and all 19 roles for Codex, OMP, Claude, explicit Pi, and generic/Pi compatibility from one `CompilationResult` per target; preserve primary-last prompt tails, selected-ID suppression, source maps, prompt metrics, typed events, and exact follow-up invalidation.
- Add profile- and invocation-selected procedure support through `tools/prompt_compile.py`, plus generated plans, manifests, effective catalogs, source maps, logical-child state, and zero-source-read unchanged reuse.
- Generate controller projections and make the OMP runtime consume the generated controller/role prompt surfaces, place runtime data before the compiled tail, and emit typed events tied to the actual effective prompt digest.
- Add `tools/prompt_lint.py`, a 100-projection prompt compilation report, semantic contradiction checks, explicit Pi install/update support, and per-harness installed prompt metadata.
- Harden JSONL/manual qualification so free-form model prose cannot satisfy compilation, reuse, readiness, Worker-start, or completion gates.
- Retain Alpha.17 record compatibility and the exact predecessor provider-evidence boundary; changed Alpha.17.0.1 bytes require separate live-host qualification.
- Derive bundled language-profile inventory and test expectations from the archives and release manifest that are present; no test assumes a fixed profile count or requires an excluded optional profile.
- Replace POSIX-only fake command fixtures with Python-backed POSIX launchers and Windows `.cmd` launchers, stabilize governed-filesystem byte assertions against Git line-ending conversion, and make invalid-UTF-8 transport tests invoke the recorded Python interpreter directly.
- Compile only the harness projections selected by an install or update command, share validated prompt/compiler inputs across one render, cache immutable schema documents, and keep behavior-level CLI checks in-process while retaining real processes for launcher, Node, Git, and process-boundary coverage.
- Replace stale partial test weights with measured weights for all 49 modules and bind local timing caches to the exact packaged seed so an older install cannot override a corrected shard plan.
- Prevent Windows `PATHEXT` from exposing Python payload files as native substrate commands: fake launchers now use non-command payload names, and substrate discovery accepts only the declared extensionless, `.exe`, `.cmd`, and `.bat` spellings.

## 0.1.0-alpha.17 — 2026-08-06

- Promote the approved RC9 governed runtime to Alpha.17 final after the Windows/OMP 16.4.8 provider campaign passed all sixteen M17 invariants and the release operator approved the redacted evidence.
- Preserve token-addressed Worker dispatch, READY/LEASED/ACTIVATED/TERMINAL retry semantics, Windows-safe jj path identity, exact two-parent content-neutral integration, candidate admission, persistent BBK mode, and event-oriented completion.
- Preserve product-first execution, current-until-invalidated verification receipts, same-attempt mechanical repair, structured-return-first transport, scope-aware validators, grouped assurance, and planning-stop behavior.
- Preserve compiled-once child procedures, same-child external-catalog suppression, unchanged follow-up reuse, and ROADMAP_READY + FRONTIER_READY rolling-wave execution.
- Preserve pre-effect validation of every governed child `yield` and the `bbk_return_template` / `bbk_return_prepare` schema-correct construction path.
- Correct final evidence tooling so complete assistant-message arguments supersede filtered host projections, rejected-then-corrected return preparations count as same-attempt repair, Windows Python probes use temporary source files, and response-ID redaction does not corrupt ordinary code identifiers.
- Qualify Alpha.17 final for OMP 16.4.8. OMP 17.2.9 and credentialed Codex/Pi behavioral parity remain explicitly unclaimed.

## 0.1.0-alpha.17+rc.9

- Validate every governed child `yield` against its exact role-return Draft 2020-12 schema before OMP acceptance.
- Bind schema-valid returns to the active work unit, revision, attempt, session, invocation, parent route, authority, and effect fence.
- Add `bbk_return_template` and `bbk_return_prepare` for deterministic role-return construction and complete immutable binding-scoped yield inputs.
- Record role-return validation and admission receipts and return focused JSON-pointer diagnostics for same-attempt repair.
- Extend manual evidence analysis across nested child sessions, structured returns, verification-economy duplication, all M17 invariants, and analyzer-populated result records.
- Add the live OMP 16.4.8 `VER-022` malformed-yield block and prepared-yield replacement contract.

## 0.1.0-alpha.17+rc.8 — 2026-08-06

- Preserve RC7's real-provider-proven READY/LEASED/ACTIVATED/TERMINAL native Worker dispatch lifecycle without reopening the accepted Alpha.17 architecture.
- Canonicalize `jj diff --name-only` results to validated repository-relative POSIX paths at the shared adapter boundary, including Windows backslash output, and apply the same contract to direct and baseline-relative path closure.
- Refresh only isolated source workspaces during content-neutral integration; do not snapshot the repository/root workspace carrying mutable `.bbk` coordination state.
- Derive integration-request Beads revisions internally and reuse the immutable idempotency-record revision for exact retries; retain `expected_revision` only as an optional compatibility field.
- Treat a named poll denied before effect as a recorded efficiency finding rather than an executed polling violation; unblocked or unobserved named polling still fails admission.
- Require a genuine token boundary for secret redaction so BBK receipt/schema identifiers containing `rk_` remain intact while standalone key-shaped values are removed.
- Add Windows-path, integration, polling/analyzer, redaction, revision-derivation, migration, rollback, deterministic packaging, and credentialed-harness regression coverage. Alpha.17 final remains provider-gated.

## 0.1.0-alpha.17+rc.7 — 2026-08-06

- Corrected the OMP 16.4.8 compact-dispatch digest boundary by excluding the host-discarded presentation-only `i` field while retaining exact marker, agent, task-name, and parent-session checks.
- Made `bbk_control_spawn` the atomic logical-attempt, jj-workspace, immutable-registration, Beads-assignment, and private-payload preparation surface; normal dispatch no longer requires model-authored `bbk_control_assign`.
- Added durable READY/LEASED/ACTIVATED/TERMINAL dispatch status, lease release/expiry, activation acknowledgement, same-token retry, and duplicate-attempt prevention independent of idempotency keys.
- Serialized full spawn preparation with bounded waiting while preserving parallel child execution after preparation.
- Added `bbk_control_dispatch_status` and blocked eval/shell/Python/JavaScript dispatch emulation before effect.
- Updated schemas, role capabilities, OMP/manual qualification fixtures, Windows scripts, tests, release packages, and migration/rollback material for RC7.

## 0.1.0-alpha.17+rc.6 — 2026-08-06

- Compile canonical required procedures exactly once into a closed final child-prompt tail, place the primary procedure last, and suppress the same IDs from each child's effective external skill catalog and indexed installation roots.
- Retain compiled manifest/prompt/catalog state across unchanged follow-ups with declared invalidation keys and zero procedure-source reads.
- Add `FAST_CONTINUATION`, `ADOPT_AND_GAP`, `ROADMAP_READY`, and `FRONTIER_READY`, permitting current Worker execution while future phases remain stable `DEFERRED_UNTIL_FRONTIER` records.
- Generate routine Worker and assertion contracts deterministically; require typed material triggers for Worker Designer and Verification Designer.
- Add transactional planning state, immutable semantic event transactions, atomic current-pointer publication, optimistic conflict detection, migration anchors, and rollback of failed publication.
- Add atomic `bbk result finalize` and `bbk manifest finalize` operations with canonical UTF-8/LF bytes and sidecar identity receipts.
- Add one bounded same-attempt evidence-capture replay for exact safe capture-only failures, plus expanded PowerShell wrapper preflight.
- Add late-bound effective profile receipts, reusable workspace admission receipts, typed child events, and candidate-versus-project coverage truth.
- Ship the standalone Alpha.17 JSONL analyzer configuration, hard-gate evaluator, synthetic acceptance fixture, deterministic Codex manual qualification kit, and corrected current-RC OMP redaction/rollback paths.
- Preserve RC5's token-addressed bound dispatch, create-once root identity, exact two-parent integration, candidate-admission closure, structured-return-first enforcement, event-oriented completion, and generic evaluator fallback prohibition.
- Keep `jj@0.43.0` and Beads `1.1.0` mise-managed, retain the supplied 19-role routing defaults, and keep routing `package_version` optional.
- Defer the canonical candidate-workspace/jj-overlay redesign to a successor release.

## 0.1.0-alpha.17+rc.5 — 2026-08-05

- Replace model-reproduced bound task payloads with immutable token-addressed dispatch reservations. `bbk_control_spawn` and `bbk_control_bind` return one compact OMP-native one-item batch; the qualified pre-effect OMP hook admits the reservation and rewrites it to the exact privately stored assignment before the built-in task tool executes.
- Add a keyless OMP 16.4.8 host-contract scenario proving that compact dispatch survives host schema validation, the pre-effect hook forwards the exact resolved payload, and the child never receives the compact marker as its assignment. Generic `eval`, shell, Python, or free-form task reconstruction remains forbidden.
- Make the manual root bootstrap create-once and parent-aware. Child sessions may observe but cannot replace the original root binding, and the qualification integration bridge authenticates the exact top-level root identity rather than the most recently started child.
- Repair content-neutral two-parent jj integration by verifying the integrated path closure against the exact baseline revision, source commit identities, disjoint worker paths, conflict state, and candidate workspace. The bridge now emits a current candidate-admission receipt or fails closed before reviewer/validator binding.
- Require that an integrated candidate have a successful current integration receipt, exact two-source closure, exact expected paths, no conflicts, and matching workspace, jj, Git-tree, and candidate digests. A failed integration cannot be relabelled or substituted with a single-worker workspace.
- Add a deterministic structured-return transport fence. `STRUCTURED_RETURN_ONLY` bindings block `bbk_handoff_create`; `STRUCTURED_RETURN_FIRST` requires a named material durable-transport reason before a sealed package may be created.
- Correct the Windows manual-kit installer with bounded mise discovery across current PATH, explicit parameters, environment hints, standard user-local locations, and WinGet package roots while preserving native-stderr-safe exit handling. Global `jj` and `bd` remain unnecessary; mise owns both pinned tools.
- Replace the unreliable OMP start runner with a pure command emitter. It validates the isolated install, writes and prints one exact copy-and-paste PowerShell launch block, and never starts, backgrounds, waits for, or exits an OMP process itself.
- Correct evidence analysis to deduplicate host and assistant projections by shared tool-call identity, avoiding doubled calls and false zero-second polling intervals. Preserve event-driven completion, the five-minute probe floor, and truthful nonpass evidence.
- Retain all RC4 persistent-mode, prompt-integrity, polling, collector, schema-registry, critical-path, routing, governed-filesystem, control-plane, jj/mise, and verification-economy corrections. The observed RC4 provider run is retained as nonpass evidence; `VER-037` requires a new archive-bound RC5 Windows/provider PASS before Alpha.17 final.

## 0.1.0-alpha.17+rc.4 — 2026-08-05

- Correct the Windows manual-qualification launcher so OMP remains foreground-attached for native executables and PowerShell/CMD wrappers; disable discovered skills as well as discovered extensions, load only the exact RC extension and helper, and remove the script-level `exit` path.
- Publish an exact version-bound `bbk.omp-runtime.v1` marker from the OMP extension. The manual helper now requires that marker, activates persistent BBK mode before the first user prompt, requires current controller/provider prompt-integrity receipts, and fails closed when a skill-only fallback or mismatched extension is observed.
- Make the canonical `bbk` skill an explicit compatibility discovery surface rather than a mode substitute. A `skill-prompt` without extension-owned `bbk_*` tools, `bbk-mode-state`, and `bbk-effective-prompt-receipt` evidence returns `BBK_OMP_EXTENSION_NOT_ACTIVE` instead of emulating BBK through generic tools.
- Replace high-frequency child polling with event-delivery semantics. OMP task results and IRC messages auto-deliver; a blocking empty `job`/IRC wait remains available, specific-job polling is denied, and successful nonblocking list/inbox/roster probes are limited to one per 300 seconds while children remain active.
- Correct `collect-evidence.ps1` to preserve native stderr warnings as evidence and determine success from the actual process exit code, matching the earlier installer correction. Add session-admission analysis that preserves a non-mode or skill-fallback run as `INCONCLUSIVE` rather than losing evidence or allowing a false manual PASS.
- Expand the Windows manual gate from 13 to 16 invariants to cover extension-owned mode/prompt admission, foreground/no-skill-fallback launch, and event-driven coordination. The observed RC3 user run is retained as nonpass evidence and does not satisfy `VER-037`.
- Preserve every RC3 substrate, critical-path, routing, schema-registry, governed-filesystem, control-plane, jj/mise, and verification-economy correction. Alpha.17 final remains blocked on a successful RC4 real-provider run.

## 0.1.0-alpha.17+rc.3 — 2026-08-05

- Make mise the canonical owner and launcher for `jj@0.43.0` and `github:gastownhall/beads@1.1.0`; normal BBK, substrate-doctor, Beads, jj, and release-qualification paths no longer require globally installed `jj` or `bd`. Git remains a global prerequisite.
- Adopt the supplied 19-role `bbk.model-routing.v2` policy as the packaged default. Treat `package_version` as optional provenance for imported v1/v2 routing policies; schema version, exact live-role coverage, and host route fields remain governing.
- Integrate the critical-path execution policy into canonical prompt modules, all 19 roles, high-frequency skills, schemas, deterministic runtime helpers, generators, documentation, and tests. Current PASS receipts are reused until invalidated, Worker dispatch uses exactly four blocking facts, and executable work stops further planning unless a named material blocker or risk is supplied.
- Permit reversible pre-freeze mechanical defects to be repaired in the same semantic run and physical attempt with only the affected mechanical gate rerun. Scope broad product validators to declared inspected-input changes and at most one final frozen-candidate pass. Default routine assurance to INLINE, group compatible assertions, and require a named qualitative risk for Reviewer dispatch.
- Compile shared prompt modules once per effective role/skill closure. Generated skills declare `requires_prompt_modules` and `standalone_prompt_modules`; the four hot-path skills now total 67,609 bytes while retaining lossless standalone handoff/recovery content where needed.
- Add verification-receipt, admission-certificate, verification-budget, verification-economy event-log, and metrics schemas; deterministic dispatch, pre-check/reuse, receipt persistence, repair-transition, validator-scope, assurance-grouping, and planning-stop code; and replay fixtures for the observed Alpha.16 verification-churn pattern.
- Preserve the Alpha.16.1 recursive declared-`$id` schema registry and structured managed-validator failure correction, the RC2 governed write/control-plane/session-oracle work, content-neutral jj integration, and candidate-safe mise task execution.
- Publish only as a successor release candidate. `VER-037` real-provider qualification remains mandatory before Alpha.17 final.

## 0.1.0-alpha.16.1 — 2026-08-04

- Repair harness-scoped OMP clean replacement and the dedicated OMP updater by sharing one canonical adjacent Python runtime inventory with the full installer, proving manifest ownership, smoke-running the installed import/routing/schema surfaces, and rolling back targeted files plus the prior manifest on post-install failure.
- Refresh packaged-default model-routing source/effective-copy metadata to the current release during selective OMP updates while preserving explicit custom policy ownership and active OMP routes.
- Add one-shot software `bbk artifact finalize` mode over ordinary project files and directories, with deterministic exclusions, include/exclude selectors, symlink rejection, ephemeral generic draft construction, immutable publication, and external source binding.
- Add `bbk artifact freshness`, the OMP `bbk_artifact_freshness` tool, and `/bbk:artifact:freshness` to verify the sealed package and detect added, removed, changed, or missing files in a source-bound implementation selection.
- Prevent OMP completion-bearing relays from substituting a handoff, passing tests, raw directory, or stale publication when the user explicitly required artifact finalization; also freshness-check voluntarily observed finalizations before completion claims.
- Preserve alpha.16 provider-prompt enforcement, authority/timing/CLI behavior, canonical roles, and exact reviewed per-role model routes.

## 0.1.0-alpha.16 — 2026-08-04

- Enforce the exact session-bound Main or child prompt at OMP's actual `before_provider_request` payload. Verify exact supported payloads, repair recognized generic/developer contamination, block unsupported or failed repairs through host abort plus a user-content-free sentinel, and retain ordinary non-BBK OMP pass-through.
- Add per-request digest-only `bbk.effective-prompt-receipt.v2`, persistent unresolved prompt-integrity status, adapter/provider/model and request-sequence evidence, exact IRC-wake contamination regression coverage, and `/bbk:prompt-status` verified/repaired/blocked counts. Disclose that later extension handlers can still rewrite because OMP exposes no post-chain finalizer.
- Add `bbk artifact finalize`, `bbk_artifact_finalize`, and `/bbk:artifact:finalize`: strict preflight, default rejection of mutable coordination records, project-local `.bbk/artifacts/sealed/<package-id>-<revision>` publication, external immutable publication receipts, mutable current pointers, post-publication drift verification, package-ID locking, and rollback of incomplete external metadata.
- Add the canonical WORKSPACE_IMPLEMENTATION / EXTERNAL_EXECUTION / PRODUCE_ONLY authority split and exact independent completion claims across all 19 roles and the OMP controller, preventing both unauthorized external effects and premature planning-only termination when local implementation artifacts are authorized.
- Add `/bbk:timing` and controller timing in `/bbk:agents`, separating explicit native-`ask` user wait from session elapsed while reporting provider, tool, sub-agent, overlap-aware wall, prompt-block, and unattributed intervals without labelling elapsed-minus-wait as model compute.
- Replace uncontrolled argparse failures with `bbk.cli-error.v1` diagnostics containing exact field, received value, permitted values, required fields, corrected example, help command, and smallest next action; retain concise human errors and exit status 2.
- Extend the managed Codex/Claude `bbk-artifact` skill with one-shot finalization and publication metadata guidance. Preserve alpha.15.1 revived-agent reconciliation, PATH-independent bindings, exact 19-role model routes, install scopes, language profiles, handoff/context/package compatibility, and the boundary that Blueprint owns global deterministic lifecycle and model-suitability governance.

## 0.1.0-alpha.15.1 — 2026-08-03

- Reconcile `/bbk:agents` against both OMP task lifecycle/progress and later live coordination evidence. Successful `injected`, `woken`, or `revived` hub/IRC receipts, authoritative peer rosters, and legacy running-agent reports can make a completed task session active again; newer lifecycle or roster evidence supersedes older observations.
- Preserve one deduplicated Main-to-descendant tree across task IDs and hub/IRC/job peer IDs, discover role-bearing live peers, expose task status, peer status, effective status source, and current wake outcome in JSON/details output, and keep failed send receipts non-activating.
- Add the canonical `bbk-artifact` skill to all 19 roles as an on-demand procedure and install it automatically for Codex and Claude Code. Its project/user-scope wrapper resolves the exact BBK install manifest and invokes the recorded Python plus `tools/bbk.py`, so the short `bbk` command is not required on `PATH`; the Codex-only successor updater also adds or refreshes the skill without rebinding the shared package.
- Qualify Codex and Claude skill installation, install-manifest ownership, archive-safe wrapper invocation, uninstall, PATH-independent binding, and real artifact preflight/seal/verify behavior. Preserve the boundary that package integrity does not establish semantic acceptance, authorization, validation, deployment readiness, or release authority.
- Retain the corrected alpha.15 Windows symlink-fixture portability behavior, exact 19-role model routes, all package/profile/context/handoff features, install scopes, language-profile reuse, Beads compatibility, and Blueprint lifecycle boundary.

## 0.1.0-alpha.15 — 2026-08-03

- Add one strict-JSON and deterministic artifact-package engine with BBK-JSON-1 canonicalization, profile preflight, lock-protected staged publication, read-only verification, successor drafts, structured diagnostics, and a thin compatibility wrapper.
- Add project-local OMP routing creation, status, dry-run repair, profile application, byte-stable user-state isolation, and fail-closed divergent-install handling through `/bbk:models project ...`.
- Add product-first proportional workflow modules, INLINE/FOCUSED/FULL assurance modes, local mechanical-defect admission, candidate-focused review, finding-scoped rechecks, and stable-interface capability parallelism.
- Add `bbk.role-return.v2` with generated COMPACT schemas and existing FULL role-specific results for all 19 roles while preserving v1 consumption.
- Add sealed Worker and review context compilers, exact candidate/focused-recheck packages, requirement-scoped host preflight, and `SPECIALIST_DESIGN_REQUIRED` for incomplete nonstandard Worker semantics.
- Add COMPACT/FULL `bbk.prototype-charter.v2` and sealed `bbk.handoff.v2` as the default producer while retaining legacy v1 readers and explicit v1 production.
- Add OMP tools and commands for artifact lifecycle, host preflight, Worker/review context generation, and handoff creation/verification/listing.
- Preserve the exact reviewed 19-role default routes, `testing-flash`, `deepseek-economy`, all install scopes, language-profile reuse, Windows path handling, Beads compatibility, and the boundary that Blueprint owns global lifecycle enforcement.

## 0.1.0-alpha.14 — 2026-08-03

- Add one canonical execution-autonomy module across Main and relevant planning/execution roles: proceed through routine in-authority changes and single-path technical resolutions; interrupt the user only for genuine material branches, authority expansion, or reserved preference.
- Add user-attention classification and coherent request/response batching, prompt-level Root-Wayfinder ownership of baseline acceptance and authority integration, node-bound evidence, and explicit specialist-return disposition without adding Blueprint lifecycle gates.
- Add `bbk.implementation-structure-contract.v3` with compact infrastructure/network/deployment subjects, applicability-aware sections, pre-execution confirmations, and compatibility-preserving v1/v2 validation.
- Add `bbk schema list/template/enum/explain` and deterministic `bbk artifact manifest/verify` tooling.
- Initialize reference examples under non-operational `.bbk/examples/` by default; preserve legacy example recognition and `--no-examples` initialization.
- Add digest-only OMP effective/provider-prompt receipts and `/bbk:prompt-status` as observability-only evidence.
- Preserve the exact reviewed 19-role model routes, project/user routing isolation, Beads defaults, agent-tree visibility, installer/profile reuse, and alpha.13.5 Windows path handling.

## 0.1.0-alpha.13.5 — 2026-08-03

- Correct the OMP project-routing isolation regression test to compare canonical filesystem identity instead of requiring byte-identical path spellings in notifications and JSON results.
- Add shared test path assertions for physical identity, notification fields, ordered path collections, containment, and deliberate exact serialization, with alias-aware diagnostics.
- Add a source audit that rejects direct physical-path equality, direct identity-primitive use outside the helper, and interpolated native paths in notification assertions.
- Cover Windows long-name versus 8.3 temporary-directory aliases and POSIX symlink aliases through the same physical-path assertion path.
- Preserve alpha.13.4 runtime behavior, verification profiles, language-profile reuse, installer behavior, canonical roles, prompt contracts, and reviewed 19-role model routing unchanged.

## 0.1.0-alpha.13.4 — 2026-08-02

- Add explicit `fast`, `standard`, and `release` verification profiles; make routine setup/testing use standard while release building and publication use exhaustive release qualification.
- Retain all product/integration/platform tests in standard; move only test-runner self-tests and duplicate optional external-schema cross-checks to release.
- Remove the exact-eight-test-files organizational assertion and duplicate package-wide drift/sanity invocations from the unittest stage.
- Replace nested duplicate installation meta-tests with focused hermetic probes, reuse minimal OMP fixtures, use core-only installs where profiles are irrelevant, and reduce oversized output fixtures.
- Run safe deterministic verifier commands in-process after package trust, retain real processes where semantics require them, and restore all mutable process state after each call.
- Use measured-duration sharding, six pooled workers on high-core hosts, and package-external timing/cache records; `--jobs` now changes worker count without changing execution mode.
- Authenticate selected language-profile packages on every install while reusing already-current installed profile files and other byte/mode-identical successor files instead of rewriting them.
- Preserve normal divergence, backup, `--force`, manifest ownership, uninstall, and routing behavior; unchanged profile reuse is digest- and mode-based rather than version-label-based.
- Preserve the exact reviewed 19-role model-routing defaults and all alpha.13.3 operational corrections.

## 0.1.0-alpha.13.3 — 2026-08-02

- Make all 19 generated OMP BBK roles explicitly `blocking: false`, using OMP 16.4.8 managed background task jobs when `async.enabled` and the host job manager are available, while retaining callback-safe sequencing when task execution is inline.
- Add modular interrupt-safe delegation and partial-attempt truth: a user/IRC wake is not cancellation authority, decision-dependent specialists wait for durable response integration, cancelled files remain provisional, and successor attempts record resume/adopt/replace/discard disposition.
- Force strict UTF-8 across OMP Node-to-Python transport with `-X utf8`, `PYTHONUTF8`, `PYTHONIOENCODING`, fatal decoding, typed transport errors, explicit Python stream/file encoding, and non-ASCII round-trip regressions.
- Treat an existing empty project root as successful `UNINITIALIZED` status with an explicit next action; separate command health, project state, artifact integrity, semantic readiness, and execution authorization.
- Centralize `EXAMPLE-*` classification and exclude examples from live counts, automatic question/handoff discovery, default manifests, and candidate inputs while reporting them separately and retaining template access.
- Compare OMP project routing, bindings, installed paths, manifests, agent directories, and test expectations by physical identity, covering Windows long-name/8.3 aliases without weakening fail-closed cross-project routing.
- Add proportional research stopping, executable-command verification, a bounded pre-execution confirmation register, and concise transport-versus-integration claim truth through reusable prompt modules.
- Audit and preserve exact candidate/review binding, specialist ownership, Beads operation, project/user routing isolation, nested-agent visibility, test-runner acceleration, all bundled language profiles, and the reviewed 19-role default model routes.
- Explicitly defer deterministic claim-state transitions, automatic review invalidation, filesystem-enforced specialist ownership, and Blueprint lifecycle/release gates.

## 0.1.0-alpha.13.2 — 2026-08-02

- Make Beads the default enabled, write-enabled coordination projection for newly initialized projects, with first-use initialization, dry-run/apply synchronization, exact foreign bindings, idempotence, hierarchy preservation, and direct-drift refusal.
- Add `bbk-beads` as an on-demand skill to the eight canonical record-owning roles: Root/Territory/Planning/Phase Wayfinders, Questioning Wayfinder, and Root/Territory/Worker Orchestrators.
- Add model-facing and OMP slash-command Beads synchronization and compact durable-handoff pointer surfaces, including exact mapped project/territory/WorkUnit targets and fail-closed foreign-ID checks, while retaining BBK records as semantic authority.
- Add project-safe OMP routing target resolution with `auto`, `project`, and `user` scopes, nearest-project selection, exact binding/path reporting, user-global mutation confirmation, and fail-closed behavior when an expected project binding is invalid.
- Add a complete hierarchical `/bbk:agents` view that recursively consumes live and finalized nested OMP task details, deduplicates direct and nested events, preserves parentage, and retains bounded terminal history.
- Preserve the reviewed 19-role default model selections from `roles-update.zip`, alpha.13 role/return/execution/prompt contracts, alpha.13.1 standard-library validation, and accelerated test execution.
- Make full ordered release/CI verification use quiet suite summaries by default instead of forcing per-test verbose output; retain `python tools/run_tests.py --all -v --require-node` for explicit diagnostic detail.

## 0.1.0-alpha.13.1 — 2026-08-02

- Remove the undeclared hard import of `jsonschema` from `test_contract_package_v1.py`; deterministic and semantic contract validation remains mandatory on standard-library-only Python, while the seven tests that specifically exercise the optional external Draft 2020-12 engine report `skipped` when it is unavailable.
- Add `--require-jsonschema` to `tools/validate_contract_package.py` for maintainers who want absence of the optional validator to be blocking.
- Add `auto`, `batch`, and `isolated` unittest execution modes. Windows `auto` now runs all discovered modules in one bounded Python process; POSIX `auto` retains module-isolated parallelism.
- Reuse public `main(argv)` entry points for behavior-level install, routing, update, setup, role-assembly, contract, and fixture CLI tests; retain real subprocess coverage for copied launchers, Node integration, interpreter/environment isolation, and process-tree behavior.
- Preserve alpha.13's role contracts, prompt modules, execution contracts, generated agents, project schemas, install surfaces, bundled profiles, and reviewed default model routing unchanged.

## 0.1.0-alpha.13 — 2026-08-01

- Make the 19 split role files canonical under `spec/roles/`, with a v4 catalogue, explicit controller roots and parent modes, deterministic assembly, and generated `spec/roles.json` compatibility projection.
- Resolve Prototyper delegation, Planning/Phase specialist ownership, and operational-versus-semantic readiness contradictions.
- Add exact normalized role-return/result schemas, registry generation, formal TerritoryExecutionBoundary and local-discovery contracts, capability-status inventory, and retire the ambiguous WorkerValidationBatch object.
- Compile shared role behavior through 21 reusable prompt modules, remove the arbitrary three-mandatory-procedure ceiling, and preserve role-specific protocol behavior through source-bound regression tests.
- Advance generated projection metadata to `bbk.projection-manifest.v8` and integrate exact return contracts into Codex, OMP, Claude, and generic projections.
- Set alpha.13 default model routing to the exact reviewed `roles-update.zip` per-role selections and bind them through a complete fixture and generated-host regression.
- Regenerate skills, schemas, projections, manifests, templates, documentation, installers, and release metadata; retain alpha.12.4 project-record and installer compatibility boundaries.
- Make source-archive executable modes an explicit empty allowlist so Python, Windows, and POSIX extractors produce the same strictly verifiable alpha.13 package tree.


## 0.1.0-alpha.12.4 — 2026-08-01

- Replace canonical install-time profile buckets with `bbk.model-routing.v2`, giving all 19 roles independent OMP, Codex, and Claude Code routes while retaining validated v1 compatibility and arbitrary valid v1 profile names.
- Advance generated routing metadata to `bbk.projection-manifest.v6` and add the v2 JSON Schema, direct-route qualification, install-time override, and migration regressions.
- Make `--uninstall-existing` harness-scoped when exactly one already-installed OMP or Codex harness is selected, preserving unselected harness files and ownership records instead of uninstalling the entire managed installation.
- Add manifest-aware stale-file removal, backup/force handling, rollback, interactive scope-specific prompts, and OMP/Codex preservation regressions for selective clean replacement.
- Remove `<bbk-role-contract>` and `<bbk-inlined-skill>` metadata envelopes from Codex `developer_instructions`; retain mandatory procedure bodies as plain Markdown and keep provenance in native metadata and manifests.
- Preserve OMP's authenticated child markers, alpha.12.3.1's PowerShell-visible prompt, alpha.12.3's bounded test runner, alpha.12.2's activity/`ask` behavior, and all existing project-record schemas.

## 0.1.0-alpha.12.3.1 — 2026-08-01

- Make the interactive existing-install question line-terminated before reading stdin so Windows PowerShell and other line-oriented native-command hosts display the `[Y/n]` prompt instead of buffering it invisibly.
- Add a regression that simulates a line-mediated host and proves the prompt is visible before the installer reads the user's response.
- Preserve alpha.12.3 test-runner bounds, diagnostics, OMP behavior, installer replacement semantics, and all package/project schemas unchanged.

## 0.1.0-alpha.12.3 — 2026-08-01

- Close stdin for unittest-module processes and real behavior-test subprocesses so an unexpected prompt cannot consume the developer console or block verification indefinitely.
- Reduce the default per-module hard timeout from 900 to 300 seconds while preserving the `--suite-timeout` override.
- Add explicit 30/120/180-second bounds to Node, installer, nested unittest, and Codex-update subprocesses used by portability tests.
- Bound Windows `taskkill` to ten seconds and retain bounded direct-kill/reap fallbacks so cleanup cannot become the new hang.
- Show each running suite's latest visible unittest line in parallel heartbeats, including the current test and the hard timeout.
- Add regressions for console-input isolation and current-test heartbeat visibility; retain all alpha.12.2 product behavior unchanged.

## 0.1.0-alpha.12.2 — 2026-08-01

- Add a single above-editor OMP BBK line, showing `BBK · ready` while idle and live canonical-child activity while work is running.
- Show the latest named worker's public intent/tool/output and current context-window use, with compact context gauges for up to three additional workers.
- Remove the old `setStatus` row; document that OMP's current interactive extension API cannot replace the built-in `pi` footer brand, and consolidate mode/activity state into the one widget.
- Accept harmless OMP child-wrapper presentation normalization (line endings, blank lines, trailing horizontal whitespace) while continuing to fail closed on any changed, missing, injected, or reordered non-empty role instruction.
- Require Main to use OMP `ask` for every BBK user-facing question or decision request; ordinary prose questions are informational and cannot be treated as answered.
- Bind ADR-compatible accepted decisions to matching `BBK_USER_RESPONSE` packets marked `source: omp.ask`; keep ADR authorship in the responsible canonical role rather than Main.
- Detect a pre-existing managed BBK installation before an ordinary install and offer a default-Yes clean replacement.
- Add `--uninstall-existing` and `--keep-existing` for explicit automation policy; preflight before removal, preserve unowned files, back up forced modified regular files, and reject non-regular manifest-path conflicts.
- Add regressions for live worker/context rendering, lifecycle clearing, ask provenance, interactive replacement defaults, and preservation of a user-owned OMP extension file.
- Retain all alpha.12.1 verification-profile, hermetic-test, and performance improvements.

## 0.1.0-alpha.12.1 — 2026-07-31

- Make the profile-discovery regression hermetic instead of assuming an explicit `--profile-dir` suppresses the intentionally additive installed-profile search path.
- Verify explicit profile precedence against a deliberate isolated ambient profile and retain unexpected-file package-drift coverage.
- Add `full`, `quick`, `omp`, and `codex` ordered-verification profiles while preserving the complete release/CI path.
- Use OMP-focused qualification for `--test-and-update-omp` and Codex-focused qualification for `--test-and-update-codex`; keep full qualification for `--test`, test-and-install, and release builds.
- Run independent unittest modules concurrently by default, with `--jobs 1` available for serial diagnosis.
- Replace repeated Python interpreter startup in behavior-level CLI tests with calls to the same public `main(argv)` entry points, while retaining real subprocess coverage for operating-system and isolation boundaries.
- Keep the standalone Alpha.8 typed-profile validator for profile maintainers but stop running its external-process matrix immediately before the equivalent Alpha8ProfileDispatchTests release coverage.
- Preserve alpha.12's prompt replacement, mandatory-skill injection, controller topology, role/project schemas, model routing, and bundled profile packages.

## 0.1.0-alpha.12 — 2026-07-31

- Made the harness-root session the sole user-facing BBK controller; every canonical `bbk_*` role is now a non-user-facing child.
- Added explicit controller-mediated human-decision triggers and OMP `hub`/IRC request/reply routing.
- Replaced OMP's Main and canonical-child system prompts through `before_agent_start`, excluding conflicting generic and client-specific compatibility instructions.
- Preserved only explicit task-call data from OMP's marker-bearing child wrapper, verified the embedded role against the installed canonical projection, and discarded all other host workflow or compatibility policy.
- Made the OMP batch task contract explicit: `agent` selects the canonical role, `name` is a stable IRC/job identity, and even one child uses the `tasks` array.
- Inlined mandatory procedure bodies into all generated role prompts and removed reliance on OMP/Claude autoload metadata.
- Advanced the role catalogue to `bbk.roles.v3`, projection metadata to `bbk.projection-manifest.v5`, and OMP mode state to `bbk.omp-mode-state.v2`.
- Preserved all alpha.11.12 Windows verification and portability corrections.

## 0.1.0-alpha.11.12 — 2026-07-30

- Reissue the corrected alpha.11.11 line as an immutable alpha.11.12 successor instead of continuing to replace archives under the same version identity.
- Make unittest, ordered-verification, and install-gate streaming safe on legacy Windows console code pages by forcing Python child stdio to UTF-8, preserving undecodable bytes as escapes, and escaping unsupported console characters.
- Terminate an unfinished suite before capture cleanup and make locked temporary-log removal bounded and best-effort, preventing a secondary `WinError 32` from masking the original result.
- Add strict-CP1252, mixed-byte, Unicode, and locked-capture regressions for the native Windows verification path.
- Correct the Codex-only update regression to compare manifest ownership through physical path identity rather than raw `WindowsPath` spelling, covering long-name/8.3 aliases.
- Correct schema-validator coverage to treat optional-dependency `BLOCKED` plus exit code 1 as the documented machine-readable status contract.
- Centralize install/update path identity across core installation, Codex-only update, OMP-only update, and installed OMP routing; use native physical identity for live files and a stricter case/slash-normalized portable key for cross-platform install-plan collision checks.
- Add a native Windows compatibility probe and GitHub Actions matrix for Python 3.11/3.13, full verification, strict CP1252 output, path aliases, and Win32 sharing violations.
- Preserve the 19-role method, project-record formats, installer destinations, model-routing defaults, and all bundled language-profile archives; beyond the Windows portability corrections, changes are limited to release identity, generated integrity metadata, documentation, and version-bound fixtures.

## 0.1.0-alpha.11.11 — 2026-07-30

- Make the extracted BBK package root the canonical Git repository source; remove the repository-extractor and generated staging-tree workflow.
- Reduce `docs/` to 14 indexed, current-facing documents and consolidate agent, execution-design, assurance, profile, upgrade, and repository guidance.
- Move historical PRDs, per-alpha migration notes, decision notes, internal alignment material, old qualification reports, and release transcripts outside the public source tree while preserving them in a separate pre-public history artifact.
- Remove pre-public-only Blueprint alignment/dogfood material and the one-off alpha.9.1 Windows leak-recovery utility from the current package.
- Replace history-presence regressions with direct public-repository-shape, documentation-inventory, and product-neutrality checks while retaining the five consolidated test modules.
- Update the deterministic release builder and current documentation for direct repository maintenance without changing role, runtime, installer, project-record, model-routing, or bundled-profile operational behavior.
- Refresh bundled language-profile release metadata after CI-script and documentation review; preserve the published Go, Python, Rust, and TypeScript/JavaScript `0.1.0-alpha.3` packages byte-for-byte.

## 0.1.0-alpha.11.10 — 2026-07-30

- Replace the single cross-role constitution with selectively loaded `core`, `planning`, `coordination`, `execution`, and `assurance` modules.
- Upgrade the canonical role catalogue to `bbk.roles.v2` with explicit scope, per-child delegation triggers, escalation routes, and user-interaction boundaries for all 19 roles.
- Add model-facing child-selection triggers to OMP while retaining native `spawns` as the enforceable allowlist; align Codex, Claude Code, and generic projections to the same contract.
- Restrict direct user questioning to an active Root Wayfinder or active Question Guide; require all other roles to return structured requests to their parent.
- Stop canonical sub-agents from autoloading the top-level `bbk` entry-controller skill and reduce that skill to user-facing entry and relay responsibilities.
- Upgrade the projection manifest to `bbk.projection-manifest.v4` and bind constitution modules, scope, delegation triggers, escalations, and user boundaries.
- Normalize shared-skill frontmatter, merge duplicate profile sections, regenerate all 76 projections, and extend the five consolidated regression modules.
- Preserve alpha.11.9's corrected independently versioned alpha.3 language profiles and all existing `.bbk` project-record formats.

## 0.1.0-alpha.11.9 — 2026-07-29

- Rebuilt all bundled language profiles at their existing independently versioned `0.1.0-alpha.3` identities before the first public tag.
- Normalized current profile metadata to require BBK `0.1.0-alpha.8` or a compatible successor while preserving predecessor provenance and the structure/slice contract dialect introduced in alpha.4.
- Corrected Python structure-contract validator compatibility so alpha.8, alpha.11.x, stable, and compatible future cores are accepted while genuinely older cores remain unavailable.
- Consolidated profile tests into responsibility-oriented suites, enforced explicit UTF-8 text I/O, and made OMP `.py` command overrides interpreter-safe across Windows and POSIX.
- Rebound the default bundled profile set, release manifest, install tests, Git-ready profile repository, and qualification evidence to the corrected packages.

## 0.1.0-alpha.11.8 — 2026-07-29

- Restore recursive Wayfinding through dedicated `bbk-wayfind` procedure, active map/frontier/blocker/fog maintenance, dependency invalidation, proportionate pressure tests, and information-value stopping.
- Make the Questioning Wayfinder recommendation-first and reserve the Question Guide/`bbk-grill` path for rejected, contested, materially ambiguous, or explicitly deeper decisions.
- Complete Root/Territory → Planning → Phase reachability, prohibit Territory Wayfinders from directly asking material user questions, and add Planning/Phase route-back for missing decisions.
- Add durable `bbk.question-branch.v1` records plus `bbk question new|validate|list`.
- Add extended logical worker execution, same-thread continuation, bounded checkpoints, and six infrastructure continuations without inventing unsupported Codex timeout metadata.
- Add `bbk.handoff.v1`, `bbk handoff create|verify|list`, exact file byte/hash binding, and large-result direct-file transport.
- Add compact Beads handoff pointers with explicit `enabled`/`write_enabled` gating for `--apply`.
- Add discoverable Draft 2020-12 schema validation and optional isolated `jsonschema==4.25.1` bootstrap.
- Add exact installed-profile CLI fallback for shells that cannot resolve `bbk`.
- Consolidate 20 release-numbered test modules into five thematic modules while retaining behavioral coverage and detailed final summaries.
- Keep all bundled alpha.3 language-profile packages unchanged pending the separate profile-focused follow-up.
- Propagate standing user authority through Wayfinder, Planning, and Orchestrator contracts with exact scope, safeguards, exclusions, expiry, and no redundant re-approval inside the grant.
- Add disposable-candidate-root, protected-worktree, and sealed-evidence capability zones to work-unit, worker, and execution contracts.
- Add precise technical/authority/decision blocker and capacity/host-window pause states plus strict interruption reasons; make heartbeat absence, silence, elapsed time, and polling timeout non-evidence.
- Add exact tool-environment, payload-limit, fail-before-mutation, structured-return, same-thread continuation, and completed-child slot-hygiene duties.
- Direct workers to use built-in manifest/candidate operations for exact inventories and add the requested YAGNI/one-liner implementation instruction.
- Document the tested Codex `[features.multi_agent_v2]` configuration and custom-agent lifecycle contract in `docs/USAGE.md`.

## 0.1.0-alpha.11.7 — 2026-07-29

- Accept expanded language-profile package trees, conventional `packages/` layouts, and manifested Git repositories through `--language-profiles`.
- Add `bbk.language-profiles-repository-manifest.v1` validation that binds exact profile identity, version, path, package name, and package-root digest before independent package verification.
- Add `tools/extract_git_repositories.py` to produce an exact verified BBK repository and a separate expanded, editable `bbk-language-profiles` repository.
- Stream verification output during `--test-and-install` while writing the structured verification report separately for manifest binding.
- Add unittest suite position, elapsed-time completion records, quiet-period heartbeats, and total duration reporting.
- Add low-noise language-profile preparation, no-write preflight, file-write, and final-manifest installation progress while preserving clean `--json` output.
- Add alpha.11.7 repository-layout, tamper-rejection, extractor, progress, and documentation regressions.

## 0.1.0-alpha.11.6 — 2026-07-28

- Remove the generated Codex `sandbox_mode = "read-only"` override from all non-mutating BBK roles; all 19 Codex agents now inherit the parent turn's active sandbox and approval settings.
- Separate host write capability from BBK subject-mutation authority: every role may write bounded coordination artifacts, while only `bbk_worker` and `bbk_prototyper` may modify subject or product artifacts inside an explicit grant.
- Add concise Codex workspace-behavior instructions to every generated Codex role without changing OMP, Claude Code, or generic permission projections.
- Add `tools/update_codex.py`, `setup.py --update-codex`, and `setup.py --test-and-update-codex` for manifest-safe Codex-only upgrades that replace only the 19 Codex agent definitions and their manifest records while preserving the shared package, launcher, effective model policy, OMP state, language profiles, and other harness files.
- Preserve custom install-time model routing during selective Codex updates, reject divergent targeted files by default, and record mixed per-harness versions.
- Add seven alpha.11.6 permission, generation, documentation, setup-surface, and end-to-end selective-update regressions.

## 0.1.0-alpha.11.5 — 2026-07-28

- Change OMP `/bbk` into a persistent, session-local BBK mode and add `/bbk:exit` plus `/bbk exit`/`off` aliases.
- Persist mode state through non-LLM `appendEntry` records and restore it on session start, switch, branch, and tree navigation.
- Add a `BBK` footer/status indicator while the mode is active.
- Apply a concise, deduplicated `before_agent_start` system-prompt overlay to each ordinary turn instead of copying the full baseline skill or a large entry-controller prompt into the transcript.
- Make `/bbk` with no arguments a non-agent-facing state transition; make `/bbk <request>` forward only the user's directive through the sole intentional `sendUserMessage` path.
- Preserve UI-only deterministic core/profile commands, manifest-aware OMP model routing, OMP-only updates, Codex non-mutation, default bundled profiles, and all existing project-record semantics.
- Add five persistent-mode lifecycle, branch restoration, context-boundary, idempotence, and documentation regressions.

## 0.1.0-alpha.11.4 — 2026-07-27

- Make `/bbk:models`, deterministic core `/bbk:*` commands, and every bundled language-profile slash command UI-only so CLI result JSON is not stored or injected into model context.
- Remove structured slash-command return payloads; retain structured JSON only for explicitly LLM-callable tools.
- Keep `/bbk <request>` as the sole deliberate extension prompt path through `sendUserMessage`, while `/bbk status` remains deterministic and UI-only.
- Add `tools/update_omp.py`, `setup.py --update-omp`, and `setup.py --test-and-update-omp` for manifest-safe OMP-only upgrades that preserve active routing and do not modify `.codex`, Claude, or generic agent files.
- Update and remanifest the bundled Go, Python, Rust, and TypeScript/JavaScript alpha.3 profile archives with the same OMP command/context boundary.
- Add cross-command, cross-profile, routing-preservation, Codex-nonmutation, setup-surface, documentation, and installed-manifest regressions.
- Preserve alpha.11.3 routing profiles, alpha.11.2 Windows portability, alpha.11.1 bundled default profiles, role composition, and project-record compatibility.

## 0.1.0-alpha.11.3 — 2026-07-27

- Add interactive OMP `/bbk:models` routing for all 19 BBK sub-agents, including per-role `model` and `thinkingLevel` selection, grouped status, reusable profile import/export, and headless equivalents.
- Add bundled `default`, all-Flash `testing-flash`, and DeepSeek-only `deepseek-economy` runtime profiles plus a per-installation `installation-default` restore point.
- Persist BBK-managed routes in `effective-omp-model-routing.json`, patch only installed OMP routing frontmatter, and reconcile changed digests into the existing install manifest so status and conservative uninstall remain correct.
- Refuse missing, divergent, or unowned agents rather than overwriting local changes; attempt rollback if a routing-state write fails.
- Document OMP precedence: `task.agentModelOverrides` and project-scope agents can supersede BBK-managed user-agent frontmatter.
- Add a compact `bbk.omp-model-routing-profile.v1` template/schema, installed routing helper, six alpha.11.3 regressions, and update the OMP surface to 26 tools and 26 commands.
- Preserve alpha.11.2 Windows UTF-8/isolation corrections, the single bundled archive, the default-installed bundled language profiles, corrected TypeScript/JavaScript alpha.3 metadata, role composition, install-time model routing, and project-record compatibility.

## 0.1.0-alpha.11.2 — 2026-07-27

- Correct the final native-Windows verification failure by declaring UTF-8 explicitly for every `Path.read_text()` and `Path.write_text()` call in BBK tests, tools, and executable fixtures.
- Extend source sanity so implicit `Path` text encoding is a blocking pre-unittest verification error rather than a locale-dependent runtime surprise.
- Add alpha.11.2 regressions for current UTF-8 canonical-input loading, package-wide explicit-encoding compliance, and detector behavior.
- Isolate installer regressions from an ambient `BBK_HOME` by binding both `BBK_HOME` and `HOME` to each temporary test profile.
- Preserve alpha.11.1's single bundled archive, the default-installed bundled language profiles, corrected TypeScript/JavaScript alpha.3 metadata, installer transaction model, role composition, model routing, and project-record compatibility.

## 0.1.0-alpha.11.1 — 2026-07-27

- Reconcile the parallel alpha.11 and alpha.10.2 successors into one canonical release that supersedes both branches.
- Bundle the verified Go, Python, Rust, and TypeScript/JavaScript `0.1.0-alpha.3` profile archives inside the BBK distributable.
- Install all bundled profiles by default; add `--no-language-profiles` for core-only installs and allow repeated `--profile-id` selection without an external bundle path.
- Treat an explicit `--language-profiles` source as a deliberate replacement for the bundled profile source for that invocation.
- Correct stale current-release metadata in the TypeScript/JavaScript alpha.3 package, rebuild its manifest/root digest, and retain legitimate alpha.2 lineage references without a version bump.
- Merge alpha.11 complete-plan preflight, destination collision checks, executable-mode preservation/repair, mode-aware status/uninstall, setup aliases, and archive safety with alpha.10.2 delegation/profile-registry/prompt-efficiency changes.
- Preserve the baseline BBK entry-controller contract, model routing, product-neutral generated agents, projection-manifest v3 metadata, C0–C11 Blueprint alignment, typed profile dispatch, Windows portability, and aggregate test reporting.
- Add alpha.11.1 regressions for branch supersession, bundled inventory, default/subset/disabled/explicit profile selection, corrected TypeScript/JavaScript metadata, wrapper behavior, plan collisions, mode divergence, and current documentation.

## 0.1.0-alpha.10.2 — 2026-07-27

- Project each canonical role's exact direct-child topology into Codex, Claude Code, and generic prompt contracts while retaining OMP's native `spawns` metadata without prompt duplication.
- Match Claude Code `Agent(...)` tool allowlists to the canonical child set and make leaf-role non-delegation explicit.
- Add profile selection, router use, gate propagation, and unavailable-capability handling to profile-aware generated roles and all relevant shared skills.
- Generate an installation-specific `bbk-installed-profiles` registry plus `effective-language-profiles.json` from the exact verified profiles selected for the unified install transaction.
- Remove repeated role, host, routing-profile, and digest provenance from model-facing prompts; retain it in native host metadata, `bbk.projection-manifest.v3`, and the generic installed agent manifest.
- Add alpha.10.2 regressions for exact delegation congruence, OMP/Claude enforcement surfaces, prompt-token cleanup, profile-aware role composition, shared-skill profile guidance, and compact registry generation.
- Preserve alpha.10.1 entrypoint and setup behavior, alpha.10 model routing, alpha.9.3 Windows portability/reporting, alpha.9 alignment, alpha.8 typed profile dispatch, and all existing project-record semantics.

## 0.1.0-alpha.10.1 — 2026-07-27

- Make the baseline `bbk` skill an explicit host-level entry controller that routes planning to `bbk_root_wayfinder`, accepted execution/recovery to `bbk_root_orchestrator`, bounded review to `bbk_reviewer`, and assertion-scoped acceptance to `bbk_validator_orchestrator` without recursive rerouting.
- Change OMP `/bbk <request>` into the active orchestration entrypoint while retaining deterministic status through `/bbk status` and `/bbk:status`.
- Add `tools/verify_all.py`, `python tools/run_tests.py --all`, and `python tools/bootstrap.py --test` for one canonical, trust-gated verification sequence with a final failed-check summary.
- Add `python tools/bootstrap.py --test-and-install` and lower-level `install --verify`, which begin installation only after all blocking verification checks pass.
- Add safe, fail-closed preparation and unified installation of verified language-profile bundles or individual packages through repeatable `--language-profiles` and `--profile-id` options.
- Record core and profile package copies, skills, OMP extensions, and launchers in one installation manifest so status and conservative uninstall cover the complete installation.
- Add `tools/install_profiles.py` as a profile-bundle convenience wrapper and update all relevant README, usage, install, OMP, profile, qualification, status, release, and migration documents.
- Preserve alpha.10 model routing and product-neutral roles, alpha.9.3 Windows portability/reporting corrections, alpha.9 Blueprint alignment, alpha.8 typed profile dispatch, and existing project-record semantics.

## 0.1.0-alpha.9.3 — 2026-07-26

- Fix the native-Windows force-replacement regression by matching the installed target through filesystem identity rather than exact path spelling, covering 8.3 and long-name aliases of the same file.
- Extend `tools/run_tests.py` with a suite-wide final PASS/FAIL summary, aggregate counts, failed-suite list, a repeated failure/error list with terminal causes, process-error reporting, and an explicit exit code.
- Add five alpha.9.3 verification-reporting and path-identity regressions.
- Preserve alpha.9.2 installer isolation, host-neutral JSON paths, backup containment, recovery tooling, BBK semantics, Blueprint alignment, and profile/project compatibility.

## 0.1.0-alpha.9.2 — 2026-07-26

- Make user-scope installation honor `BBK_HOME` and `HOME` before native `Path.home()`, preventing Windows verification from writing into the operator's real Codex, OMP, Claude, or generic harness profile.
- Normalize installer JSON and project-init relative path fields to forward slashes across hosts.
- Fix forced-install backup construction for Windows drive-letter and UNC paths so an anchored destination cannot discard the backup root or alias itself.
- Add an exact-digest audit/removal tool and source-bound manifest for files alpha.9.1 Windows verification may have left in the real user profile.
- Add six alpha.9.2 Windows installer, path, backup, and recovery tests while retaining the four alpha.9.1 portability tests and all earlier suites.
- Preserve alpha.9 Blueprint alignment, 19-role topology, 20 skills/references, 26 schemas, 76 projections, 26 OMP tools, 25 commands, typed profile protocol, and project-record compatibility.

## 0.1.0-alpha.9.1 — 2026-07-26

- Fix cross-platform agent-projection verification by serializing generated manifest paths with POSIX separators on every host.
- Add `tools/run_tests.py`, which preserves unittest exit codes while writing normal progress to stdout so Windows PowerShell 5.1 does not mislabel passing tests as `NativeCommandError`.
- Silence the Git default-branch advisory emitted by one fixture test.
- Add four cross-platform verification regression tests and LF-oriented `.gitattributes` rules.
- Preserve all alpha.9 roles, methods, schemas, fixtures, commands, profile protocol, Blueprint alignment, and project-record compatibility without semantic migration.

## 0.1.0-alpha.9 — 2026-07-26

- Align current-facing BBK material with the Effort Owner development partition range C0–C11 and the supplied normative Blueprint sequence Q0→C1–C11 without silently aliasing C0 and Q0.
- Add a content-bound Blueprint alignment reference, ADR-BP-131 compatibility map, C8 Lite-RC marker, C11 integrated-v1 marker, review audit, migration guide, and decision note.
- Add the logical Questioning Wayfinder as the nineteenth canonical role and route Root/Territory decision branches through it before Question Guides.
- Add `bbk-context-routing` and `bbk-procedure-design`, explicit logical-role-to-physical-invocation mapping, and append-only evidence-exposure constraints.
- Regenerate 19 roles into 76 projections and expand canonical method content to 20 skills and 20 references.
- Replace the mislabeled order/payment Blueprint C2 dogfood fixture with a validated question-branch, explicit-disposition, exactly-once-parent-return design and crash-after-semantic-commit trace.
- Preserve the alpha.8 typed profile-capability protocol, 26 OMP tools, 25 commands, existing project records, and historical C1–C8 provenance.
- Add seven alpha.9 alignment regression tests and retain all inherited qualification suites.

## 0.1.0-alpha.8 — 2026-07-24

- Correct the alpha.7 profile-capability documentation to use entrypoint key names rather than executable paths and to match the implemented `review_entrypoint` / `lens_ids` schema.
- Add core-owned `bbk.profile-capability.v1` dispatch for State–Decision–Effect projection, actual inventory, planned-versus-actual review, review-context assembly, logical review lenses, and EvidenceReceipt v2 adaptation.
- Add content-addressed `bbk.profile-capability-request.v1`, `bbk.profile-capability-result.v1`, and dispatch records with exact profile, subject, source, input, role, assurance, and assignment binding.
- Add standalone `bbk profile dispatch` and automatic smallest-supported-set execution inside `bbk profile resolve`.
- Bind stable capability-dispatch results into effective profile digests and project locks while keeping runtime paths, duration, and process diagnostics outside semantic identity.
- Preserve alpha.2 profiles and alpha.7 declarations as explicit legacy compatibility states; no capability is inferred from skill presence or entrypoint names alone.
- Add OMP `bbk_profile_dispatch` and `/bbk:profile:dispatch`, plus evidence-input forwarding through profile resolution.
- Extend canonical roles and method modules without adding roles or broadening authority.
- Add a typed alpha.8 fixture profile, request/result/dispatch schemas, migration guidance, seven alpha.8 regression tests, and dedicated fixture validation.

## 0.1.0-alpha.7 — 2026-07-24

- Add an applicability-aware `StateDecisionEffectDesign` concern nested in `ImplementationStructureContract` with `NONE`, `INLINE`, and `CONTRACT` dispositions.
- Add canonical state, sum/product dimensions, deterministic decision boundaries, effect contracts, invariants, formalization levels, and `StateTransitionTrace` fixtures.
- Add structure/slice v2, actual state/effect inventory, planned-versus-actual review, and candidate dependency binding for inventories, traces, and formal models.
- Add explicit `AssuranceContract`, `ReviewManifest`, `ReviewContextManifest`, `ReviewRun`, `ReviewAttempt`, `EvidenceReceipt v2`, immutable finding/disposition, aggregate, and learning-candidate objects.
- Add proportional lens compilation, exact context roots, omission/shard accounting, assertion ownership, complementary-overlap checks, blind and targeted re-review, intent conformance, and non-rediscovery-safe finding closure.
- Extend profiles with explicit state/effect and review-assurance capability states without granting authority by implication.
- Extend the existing 18 roles and canonical method source; generate 18 skills, 18 references, and 72 harness projections without adding a permanent role.
- Extend the OMP adapter additively to 25 tools and 24 commands.
- Preserve alpha.6 candidate, gate, workspace, installer, profile, fit, structure, slice, work-unit, and compatibility behavior.
- Add source PRD provenance, migration guidance, dogfood examples, schema/fixture validation, inherited regression tests, and alpha.7 congruence tests.

## 0.1.0-alpha.6 — 2026-07-24

- Reconcile the alpha.3 operational lineage with alpha.4/alpha.5 planning additions.
- Restore alpha.3 method references, core skills, detailed role constitutions, manifest semantics, candidate lifecycle, executable gates, leased worktrees, installer safeguards, OMP package metadata, and user documentation.
- Retain alpha.4 implementation-structure, execution-slice, and structure-aware profile behavior.
- Retain alpha.5 `SolutionOutcomeFit`, fit-aware traceability, and commitment blocking.
- Accept and normalize legacy and current work-unit/profile forms.
- Add standalone candidate/gate compatibility alongside project-managed mechanics.
- Add canonical method and role drift checks and a dedicated lineage-congruence regression suite.
- Make installed OMP extensions self-contained for the complete alpha.6 CLI surface.
- Fix absolute-path backup handling during forced installation.

## 0.1.0-alpha.5 — 2026-07-24

- Add first-class `SolutionOutcomeFit` records, non-averaging fit risk, renderers, fixtures, and chain checking.
- Bind fit and outcome references through implementation structure, execution slices, work units, profiles, and evidence.
- Block implementation commitment for `INVESTIGATE` and `UNRESOLVED` dispositions.

## 0.1.0-alpha.4 — 2026-07-24

- Add domain-neutral `ImplementationStructureContract` and `ExecutionSlice` artifacts.
- Add structure-aware language/domain profile capabilities and entrypoints.
- Add profile routing, structure/slice templates, fixtures, and schemas.
- This release was reconstructed independently and did not preserve the complete alpha.3 operational implementation; alpha.6 repairs that lineage break.

## 0.1.0-alpha.3 — 2026-07-23

- Add independently versioned language-profile discovery, verification, resolution, and project locking.
- Add `bbk profile list`, `inspect`, and `resolve` commands.
- Add strict profile package integrity checks, including unexpected-file and symlink rejection.
- Add language-profile, profile-lock, and profile-aware work-unit schemas.
- Add the integration surface required by separate profile packages.
- Fix installed OMP extension CLI self-containment and add an execution-level regression fixture.

## 0.1.0-alpha.2 — 2026-07-23

- Add Claude Code as a first-class generated agent and skill target.
- Generate 18 Claude Code subagents with native YAML frontmatter, least-privilege tools, preloaded BBK skills, and worktree isolation for mutating roles.
- Extend installation, generation, verification, tests, and documentation for Claude Code.

## 0.1.0-alpha.1 — 2026-07-23

- Initial qualified BBK alpha for Codex, OMP, and generic harnesses.
