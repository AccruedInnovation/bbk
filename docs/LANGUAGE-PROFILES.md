# Language and domain profiles

Profiles specialize BBK procedures for a language, framework, runtime, toolchain, or engineering domain. They are maintained in the companion `bbk-language-profiles` repository.

## Source repository layout

```text
workspace/
├── bbk/
└── bbk-language-profiles/
    ├── REPOSITORY-MANIFEST.json
    └── packages/
        ├── bbk-profile-codesys-.../
        ├── bbk-profile-go-.../
        ├── bbk-profile-python-.../
        ├── bbk-profile-rust-.../
        └── bbk-profile-typescript-javascript-.../
```

The BBK Git repository does not duplicate profile ZIPs. Published releases may bundle exact qualified snapshots for self-contained installation.

## Installation from source

```bash
python tools/repo_setup.py --test-and-install \
  --scope user --omp --codex
```

The wrapper auto-detects the sibling repository. An explicit source and profile subset are also supported:

```bash
python tools/repo_setup.py --test-and-install \
  --scope user --omp --codex \
  --language-profiles ../bbk-language-profiles \
  --profile-id rust --profile-id python
```

## Capability and authority

A profile may provide:

- specialist planning and implementation procedures;
- compiler, formatter, linter, test, mutation-test, static-analysis, or CI guidance;
- evidence adapters and profile-specific gates;
- host extensions or launchers;
- compatibility and capability metadata.

A profile may not:

- redefine the canonical BBK role topology;
- broaden effects or authority;
- waive assurance requirements;
- invent availability of an external toolchain;
- convert weak or missing evidence into a pass.

## Discovery, resolution, and locks

Profile resolution should select the smallest capability set that satisfies the task. A profile lock binds the selected identity and content so later work does not silently switch procedure or evidence semantics.

Legacy or partial profile capabilities remain explicit. They are not upgraded by implication.

## Installed registry

Installation generates a compact `bbk-installed-profiles` skill and a full machine-readable effective inventory. Agents consult the router first and load only the focused procedures needed for the exact role and assertion.

## Developing profiles

Profile changes belong in the companion repository. Rebuild and verify each profile independently, update its repository manifest, then test it against BBK through `--language-profiles PATH`.

## Inspecting the effective installed profile set

Installation writes the full machine-readable profile inventory to:

```text
effective-language-profiles.json
```

and generates the compact `bbk-installed-profiles` skill for agent context. Inspect the resolved profile packages and capability dispatch with:

```bash
bbk --json profile list
```

The compact skill names the selected routers and profile identities; focused specialist skills remain discoverable through the machine inventory rather than being embedded into every agent prompt.
