# Changelog

## 0.1.0-alpha.13.1 — 2026-08-02

- Remove the accidental hard test dependency on `jsonschema`; add a standard-library role-return validator and run the complete contract suite successfully under `python -S`.
- Retain optional Draft 2020-12 validation through `jsonschema`/`referencing` when installed, while making the standalone full validator report a precise dependency blocker when absent.
- Restore cached in-process execution for canonical BBK CLI behavior tests and trusted package-local profile fixtures, retaining real subprocesses for operating-system, isolation, timeout, and tamper boundaries.
- Reduce the default eight-suite wall time from 42.48 seconds to 25.21 seconds on the qualification host while increasing contract coverage.
- Preserve alpha.13 role, contract, prompt, installer, language-profile, and reviewed per-role model-routing behavior unchanged apart from the package-version binding.


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
- Preserve the 19-role method, project-record formats, installer destinations, model-routing defaults, and all five bundled language-profile archives; beyond the Windows portability corrections, changes are limited to release identity, generated integrity metadata, documentation, and version-bound fixtures.

## 0.1.0-alpha.11.11 — 2026-07-30

- Make the extracted BBK package root the canonical Git repository source; remove the repository-extractor and generated staging-tree workflow.
- Reduce `docs/` to 14 indexed, current-facing documents and consolidate agent, execution-design, assurance, profile, upgrade, and repository guidance.
- Move historical PRDs, per-alpha migration notes, decision notes, internal alignment material, old qualification reports, and release transcripts outside the public source tree while preserving them in a separate pre-public history artifact.
- Remove pre-public-only Blueprint alignment/dogfood material and the one-off alpha.9.1 Windows leak-recovery utility from the current package.
- Replace history-presence regressions with direct public-repository-shape, documentation-inventory, and product-neutrality checks while retaining the five consolidated test modules.
- Update the deterministic release builder and current documentation for direct repository maintenance without changing role, runtime, installer, project-record, model-routing, or bundled-profile operational behavior.
- Promote the bundled CODESYS profile to its independently versioned `0.1.0-alpha.4` successor after CI-script/documentation review; preserve the Go, Python, Rust, and TypeScript/JavaScript `0.1.0-alpha.3` packages byte-for-byte.

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

- Rebuilt all five bundled language profiles at their existing independently versioned `0.1.0-alpha.3` identities before the first public tag.
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
