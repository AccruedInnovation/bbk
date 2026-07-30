# Changelog

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
- Update and remanifest the bundled CODESYS, Go, Python, Rust, and TypeScript/JavaScript alpha.3 profile archives with the same OMP command/context boundary.
- Add cross-command, cross-profile, routing-preservation, Codex-nonmutation, setup-surface, documentation, and installed-manifest regressions.
- Preserve alpha.11.3 routing profiles, alpha.11.2 Windows portability, alpha.11.1 bundled default profiles, role composition, and project-record compatibility.

## 0.1.0-alpha.11.3 — 2026-07-27

- Add interactive OMP `/bbk:models` routing for all 19 BBK sub-agents, including per-role `model` and `thinkingLevel` selection, grouped status, reusable profile import/export, and headless equivalents.
- Add bundled `default`, all-Flash `testing-flash`, and DeepSeek-only `deepseek-economy` runtime profiles plus a per-installation `installation-default` restore point.
- Persist BBK-managed routes in `effective-omp-model-routing.json`, patch only installed OMP routing frontmatter, and reconcile changed digests into the existing install manifest so status and conservative uninstall remain correct.
- Refuse missing, divergent, or unowned agents rather than overwriting local changes; attempt rollback if a routing-state write fails.
- Document OMP precedence: `task.agentModelOverrides` and project-scope agents can supersede BBK-managed user-agent frontmatter.
- Add a compact `bbk.omp-model-routing-profile.v1` template/schema, installed routing helper, six alpha.11.3 regressions, and update the OMP surface to 26 tools and 26 commands.
- Preserve alpha.11.2 Windows UTF-8/isolation corrections, the single bundled archive, five default-installed language profiles, corrected TypeScript/JavaScript alpha.3 metadata, role composition, install-time model routing, and project-record compatibility.

## 0.1.0-alpha.11.2 — 2026-07-27

- Correct the final native-Windows verification failure by declaring UTF-8 explicitly for every `Path.read_text()` and `Path.write_text()` call in BBK tests, tools, and executable fixtures.
- Extend source sanity so implicit `Path` text encoding is a blocking pre-unittest verification error rather than a locale-dependent runtime surprise.
- Add alpha.11.2 regressions for current UTF-8 canonical-input loading, package-wide explicit-encoding compliance, and detector behavior.
- Isolate installer regressions from an ambient `BBK_HOME` by binding both `BBK_HOME` and `HOME` to each temporary test profile.
- Preserve alpha.11.1's single bundled archive, five default-installed language profiles, corrected TypeScript/JavaScript alpha.3 metadata, installer transaction model, role composition, model routing, and project-record compatibility.

## 0.1.0-alpha.11.1 — 2026-07-27

- Reconcile the parallel alpha.11 and alpha.10.2 successors into one canonical release that supersedes both branches.
- Bundle the verified CODESYS, Go, Python, Rust, and TypeScript/JavaScript `0.1.0-alpha.3` profile archives inside the BBK distributable.
- Install all five bundled profiles by default; add `--no-language-profiles` for core-only installs and allow repeated `--profile-id` selection without an external bundle path.
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
