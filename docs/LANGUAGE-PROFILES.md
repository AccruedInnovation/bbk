# Language and domain profiles in BBK alpha.11.12

BBK installs five independently manifested profile packages by default: CODESYS `0.1.0-alpha.4`, and Go, Python, Rust, and TypeScript/JavaScript `0.1.0-alpha.3`. Strict manifests bind their metadata, compatibility, OMP launch behavior, structure-validator detection, and consolidated test surfaces. The typed capability protocol is `bbk.profile-capability.v1`.

## Bundled inventory

The verified inner archives live at `bundled-language-profiles/packages/`:

| ID | Package | Version | Router skill | CLI |
|---|---|---|---|---|
| `codesys` | `bbk-profile-codesys` | `0.1.0-alpha.4` | `bbk-codesys` | `bbk-codesys` |
| `go` | `bbk-profile-go` | `0.1.0-alpha.3` | `bbk-go` | `bbk-go` |
| `python` | `bbk-profile-python` | `0.1.0-alpha.3` | `bbk-python` | `bbk-python` |
| `rust` | `bbk-profile-rust` | `0.1.0-alpha.3` | `bbk-rust` | `bbk-rust` |
| `typescript-javascript` | `bbk-profile-typescript-javascript` | `0.1.0-alpha.3` | `bbk-tsjs` | `bbk-tsjs` |

`bundled-language-profiles/RELEASE-MANIFEST.json` binds the exact five archives and their SHA-256 companion files. Each inner archive retains its own `PACKAGE-MANIFEST.json`, root digest, profile contract, and version.

## Default installation

The ordinary setup command installs BBK and all five profiles in one manifest-managed operation:

```bash
python tools/setup.py --test-and-install --scope user --omp --codex --claude
```

No separate bundle path is needed. The installer reports:

```text
language_profile_source_mode: bundled-default
profile_count: 5
```

Select a subset from the bundled set:

```bash
python tools/setup.py --test-and-install --scope user --omp --codex \
  --profile-id rust \
  --profile-id python
```

Install only core BBK:

```bash
python tools/setup.py --test-and-install --scope user --omp --codex \
  --no-language-profiles
```

Use an external package, expanded repository, or release bundle instead of the bundled set:

```bash
python tools/setup.py --test-and-install --scope user --omp --codex \
  --language-profiles /path/to/alternate-profiles.zip
```

An expanded Git repository is accepted directly:

```powershell
python tools\setup.py --test-and-install `
  --scope user --omp --codex `
  --language-profiles ..\bbk-language-profiles
```

Supported extracted layouts include one profile root, immediate child profile roots, and profile roots beneath `packages/`. The published `bbk-language-profiles` repository includes `REPOSITORY-MANIFEST.json`, which binds the exact profile inventory and package-root digests. Every profile package is independently verified whether or not an outer repository manifest exists.

An explicit `--language-profiles` source replaces the built-in source for that invocation. It does not silently merge with the bundled set. Repeat the flag to combine multiple explicit sources.

The profile-focused wrapper defaults to the bundled set:

```bash
python tools/install_profiles.py --scope user --omp --codex --claude
```

## Effective composition

A material language/toolchain invocation combines:

```text
canonical BBK role and authority
+ model-routing profile
+ BBK method skill
+ installed-profile registry
+ selected profile router
+ focused profile procedures required by this role/assertion
+ exact project/profile lock and toolchain assumptions
= effective invocation
```

A profile adds procedures, review criteria, gates, evidence adapters, context selectors, and domain assumptions. It does not expand scope, grant filesystem/network effects, waive generic BBK invariants, prove external tool availability, approve a candidate, or authorize release.

OMP keeps direct-child topology in native `spawns` metadata. Non-OMP generated agents name their canonical direct children in prompt text. Profile-aware roles also explain when to consult the installed registry and how to propagate profile identity, lock/digest, assumptions, gates, and unavailable-capability dispositions to child agents.

## Installation-specific profile registry

The source tree contains a placeholder:

```text
shared/skills/bbk-installed-profiles/SKILL.md
```

It deliberately does not claim that any profile is installed. During installation BBK excludes that placeholder from ordinary skill copying and generates a compact registry from the exact verified profile set in the installation operation.

The generated skill records:

- profile ID, display name, and version;
- router skill;
- profile CLI;
- focused-skill count;
- declared typed-capability status.

The complete machine-readable inventory is written to:

```text
<BBK data root>/effective-language-profiles.json
```

The same identity, source, package digest, compatibility result, installed paths, and registry digest are bound into `install-manifest.json`.

Agents still confirm live discovery with:

```bash
bbk --json profile list
```

Project-local profile roots and `BBK_PROFILE_PATH` may change runtime precedence beyond the managed installation.

## Pre-public metadata corrections and CODESYS alpha.4 promotion

Go, Python, Rust, and TypeScript/JavaScript retain their independently versioned `0.1.0-alpha.3` packages. CODESYS is now `0.1.0-alpha.4`, an immutable successor to the reviewed alpha.3 CI-script and documentation correction. Current-facing metadata agrees across `VERSION`, `PROFILE.json`, README, installation guidance, OMP extension metadata, and each strict package manifest. Historical predecessor, migration, source-binding, and source-change records remain unchanged where they describe actual lineage.

The bundle therefore carries four distinct identities that must not be conflated:

```text
CODESYS profile package version:       0.1.0-alpha.4
other bundled profile versions:        0.1.0-alpha.3
minimum compatible BBK core:           0.1.0-alpha.8
structure/slice contract dialect:      introduced in 0.1.0-alpha.4
```

The four alpha.3 packages remain byte-identical to the corrected `verified-r3` set. The CODESYS package has a new semantic version, package root, archive digest, predecessor binding, and migration record while retaining the reviewed alpha.3 operational behavior and authority boundary.

## Fail-closed preparation

Before any install destination is written, BBK:

1. verifies the outer bundled release manifest or expanded repository manifest when present;
2. safely extracts ZIP sources or discovers only explicit supported extracted layouts;
3. independently verifies each package manifest and root digest;
4. validates `PROFILE.json`, `VERSION`, package name, profile ID, declared installation paths, minimum BBK version, and Python range;
5. rejects duplicate identity with divergent root content;
6. validates requested profile IDs and reports missing IDs;
7. incorporates all selected package, skill, extension, launcher, registry, and core destinations into one no-write plan;
8. rejects byte or executable-mode collisions before actual installation.

Archive validation rejects path traversal, absolute or drive-qualified entries, backslashes, alternate-data-stream syntax, reserved Windows device names, trailing dots/spaces, NUL/control characters, duplicate entries, portable case collisions, file/directory conflicts, symlinks, special files, encryption, excessive entry counts, and excessive expansion.

## Installed layout and ownership

Package copies are stored beneath the BBK data root:

```text
profiles/<profile-id>/<version>/
profiles/<profile-id>/current.json
```

Declared profile skills are copied to selected host skill roots. Declared OMP extensions are copied to the OMP extension root. User-scope installs create profile CLI launchers. Core and profile files are recorded in one manifest, so the normal commands cover the complete installation:

```bash
python tools/install.py status --scope user
python tools/install.py uninstall --scope user
```

Uninstall is conservative: content or executable-mode divergence is preserved and reported unless `--force` is explicit.

## Capability generations

- Earlier packages may be `legacy-unprojected`, `legacy-summary`, or `legacy-no-review-manifest`.
- Alpha.7 could declare capability names but had no central typed invocation protocol; those declarations remain `legacy-declared` and are not auto-dispatched.
- Alpha.8-aware profiles opt into `bbk.profile-capability.v1` and typed request/result handling.
- All bundled profiles declare minimum BBK alpha.8 and remain compatible with alpha.11.12 and compatible successors when their exact package and runtime checks pass.

No profile file, skill, compiler, linter, simulator, IDE, or native tool is invoked merely because the package is installed.

## Runtime commands

```bash
bbk profile list
bbk profile inspect --id rust
bbk profile resolve --id rust --work-unit .bbk/work-units/WU-001.json --write-lock
bbk profile dispatch --operation state-effect --id rust --state-decision-effect design.json
```

The resolver selects only capabilities for which exact inputs and qualified profile support exist. It may receive applicable fit, structure, slice, state/effect, assurance, review, and evidence inputs more than once.

## Typed operation boundary

Capability fields name entrypoint keys, and `entrypoints` supplies argv arrays. Every operation receives a read-only, content-addressed request package. Input locators are request-relative. Profile outputs are schema-validated and remain non-authoritative projections until generic BBK assurance accepts them.

The profile lock binds the exact package, resolver result, capability dispatch, and input digests. Runtime diagnostics remain separate so effective identities are not accidentally made machine-path- or duration-dependent.

See `INSTALL.md`, `ASSURANCE.md`, and the schemas under `../spec/schemas/`.

## Current bundled-profile contract

The bundled package identities are CODESYS `0.1.0-alpha.4` plus Go, Python, Rust, and TypeScript/JavaScript `0.1.0-alpha.3`. All five share the following contract:

- current package metadata agrees across `VERSION`, `PROFILE.json`, README, installation guidance, OMP package metadata, and `PACKAGE-MANIFEST.json`;
- `PROFILE.json.requires.bbk_minimum` is `0.1.0-alpha.8`;
- legacy projection fields containing `"bbk_version": "0.1.0-alpha.4"` are explicitly the structure/slice **contract dialect**, not the installed core version or compatibility floor;
- Python tools and tests use explicit UTF-8 text I/O;
- release-numbered profile tests are consolidated into responsibility-oriented suites;
- OMP environment overrides ending in `.py` are run through the configured Python interpreter rather than spawned as native executables;
- every package is independently manifested, tested, strictly verified, and then bound into the outer release bundle.

The Python profile additionally uses capability-aware structure-validator detection and accepts alpha.4, alpha.8, alpha.11.x, stable, and compatible future cores while continuing to reject genuinely older cores. Its fallback minimum comes from `PROFILE.json.requires.bbk_minimum`; Rust quick-start guidance and common metadata regressions also enforce the alpha.8 compatibility floor.

## Typed capability dispatch

**Introduced:** `0.1.0-alpha.8`  
**Protocol:** `bbk.profile-capability.v1`

### Purpose

Alpha.7 let profiles declare State–Decision–Effect and Review Assurance capabilities but did not define one central execution protocol. Alpha.8 completes that boundary without turning profiles into semantic or effect authorities.

A profile capability is invoked through:

```text
core validates profile package and capability
  → core binds exact source, subject, and input digests
    → core writes one read-only request package
      → profile returns one typed projection/result
        → core validates the result
          → generic BBK retains assurance, evidence, finding, and authority decisions
```

### Capability declaration

Capability fields contain entrypoint **names**. `entrypoints` contains argv arrays.

```json
{
  "capabilities": {
    "state_decision_effect": {
      "status": "supported",
      "dispatch_protocol": "bbk.profile-capability.v1",
      "projection_entrypoint": "state_effect",
      "inventory_entrypoint": "state_effect_inventory",
      "review_entrypoint": "state_effect_review"
    },
    "review_assurance": {
      "status": "supported",
      "dispatch_protocol": "bbk.profile-capability.v1",
      "context_entrypoint": "review_context",
      "review_entrypoint": "review_lens",
      "evidence_entrypoint": "evidence_adapter",
      "lens_ids": ["state-concurrency-effect-recovery"]
    }
  },
  "entrypoints": {
    "state_effect": ["{python}", "tools/profile.py", "--json", "state-effect"],
    "state_effect_inventory": ["{python}", "tools/profile.py", "--json", "state-effect-inventory"],
    "state_effect_review": ["{python}", "tools/profile.py", "--json", "state-effect-review"],
    "review_context": ["{python}", "tools/profile.py", "--json", "review-context"],
    "review_lens": ["{python}", "tools/profile.py", "--json", "review-lens"],
    "evidence_adapter": ["{python}", "tools/profile.py", "--json", "evidence-adapter"]
  }
}
```

A `supported` typed SDE capability requires all three SDE entrypoints. A `supported` typed review capability requires context, review, evidence entrypoints, and at least one logical lens. A `partial` capability must name its limitations and at least one implemented entrypoint.

### Operations

| Operation | Required exact inputs | Intended result |
|---|---|---|
| `state-effect` | StateDecisionEffectDesign | language/domain projection and applicable procedure |
| `state-effect-inventory` | StateDecisionEffectDesign | actual-structure inventory procedure or inventory |
| `state-effect-review` | design plus exact inventory | planned-versus-actual profile review projection |
| `review-context` | AssuranceContract plus ReviewManifest | valid ReviewContextManifest or bounded blocked result |
| `review-lens` | assurance, manifest, and valid context | one logical-lens procedure/result bound to assignment IDs |
| `evidence-adapter` | one exact source evidence record | valid EvidenceReceipt v2 or explicit unsupported/blocked result |

### Request contract

The profile receives `--request <path>`. The file uses `bbk.profile-capability-request.v1` and contains:

- exact profile package and manifest digests;
- source content root and stable Git facts;
- exact subject identity and digest;
- content-addressed input bindings;
- role, task, assurance, hints, affected paths, lens, and assignment context;
- a read-only authority envelope;
- a self-validating request digest.

Input `path` values are relative to the request file's directory. Profiles must resolve them against `Path(request_path).parent`, not the process working directory. The actual source tree is separately exposed as `BBK_PROFILE_SOURCE_ROOT`; it is not part of the stable request identity.

`runTools=true` permits only profile-qualified read-only inspection or evidence commands. It never grants subject mutation, package installation, network use, publication, deployment, or external effects.

### Result contract

Profiles return `bbk.profile-capability-result.v1`:

```json
{
  "schema": "bbk.profile-capability-result.v1",
  "profileId": "rust",
  "profileVersion": "0.1.0-alpha.3",
  "capability": "state_decision_effect",
  "operation": "state-effect",
  "status": "PASS",
  "requestDigest": "<exact request digest>",
  "payload": {},
  "warnings": [],
  "errors": [],
  "limitations": []
}
```

Allowed status values are `PASS`, `PASS_ADVISORY`, `PARTIAL`, `BLOCKED`, `UNSUPPORTED`, and `ERROR`. They describe completion of the profile procedure—not generic assertion success or official Blueprint authority.

An `evidence-adapter` success must contain a valid `bbk.evidence-receipt.v2` either directly as the payload or at `payload.receipt`. Its subject digest must match the dispatch subject.

### Central resolution

`bbk profile resolve` automatically dispatches only when exact corresponding inputs are supplied and the profile has the typed protocol. It executes the SDE chain in projection → inventory → review order. It executes review context before only those lens assignments listed in the profile's `lens_ids`. Unhandled assignments are retained explicitly.

```bash
bbk profile resolve \
  --id rust \
  --state-decision-effect design.json \
  --assurance-contract assurance.json \
  --review-manifest review-manifest.json \
  --evidence-input legacy-or-native-receipt.json \
  --write-lock
```

The profile lock stores the stable capability-dispatch projection and its digest. Runtime argv, temporary paths, durations, and stdout/stderr digests remain execution diagnostics and are excluded from the effective semantic digest.

For one operation:

```bash
bbk profile dispatch \
  --operation state-effect \
  --id rust \
  --state-decision-effect design.json
```

### Compatibility

- Alpha.2 profiles remain valid under their original capability declarations.
- Alpha.7 profiles that name SDE/review entrypoints but omit the typed protocol are `legacy-declared` and are not automatically invoked.
- No skill name, file presence, or maturity label silently grants capability.
- Old locks and evidence remain bound to their original package digest.

### Authority boundary

Profiles remain projections and procedural adapters. Core BBK owns package verification, request identity, generic schemas, candidate identity, assurance obligations, evidence eligibility, aggregation, finding lifecycle, and locks. BBK itself remains non-authoritative relative to Blueprint.
