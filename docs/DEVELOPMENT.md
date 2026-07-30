# Development guide

## Canonical and generated files

Edit canonical sources:

```text
spec/roles.json
spec/method-content.json
spec/model-routing.json
shared/skills/
shared/references/
```

Generated host projections live under `projections/` and are committed for review and direct installation. Do not hand-edit them unless repairing the generator itself.

Regenerate and check:

```bash
python tools/create_method_content.py
python tools/create_role_spec.py
python tools/generate_agents.py

python tools/create_method_content.py --check
python tools/create_role_spec.py --check
python tools/model_routing.py --check
python tools/generate_agents.py --check
```

## Verify the source repository

```bash
python tools/verify_source_repository.py --require-node
```

This source-mode verification intentionally skips immutable package-manifest gates.

Run one test module during development:

```bash
python tools/run_tests.py -v -p test_name.py
```

## Repository responsibilities

Core BBK owns host-neutral roles, methods, records, model routing, installers, host adapters, and qualification machinery.

The companion profile repository owns language/domain-specific procedures, tool adapters, profile metadata, and profile package manifests.

A profile must not fork core semantic objects or broaden role authority.

## Building a release

The Git `main` branch does not contain bundled profile ZIPs or release-only evidence. Stage a self-contained release with:

```bash
python tools/build_public_release.py \
  --language-profiles ../bbk-language-profiles \
  --output-dir dist
```

The wrapper:

1. verifies the source checkout;
2. independently builds/validates selected profile packages;
3. stages `bundled-language-profiles/` in a temporary release tree;
4. invokes the existing immutable release builder;
5. leaves the source checkout unmodified.

Release notes, package manifests, checksums, qualification reports, archive audits, and full logs belong in GitHub Release assets, not on `main`.

## Documentation policy

Keep `/docs` evergreen and user/contributor focused. Historical PRDs, alpha decision notes, migration chains, lineage audits, fixture matrices, and release-specific qualification evidence belong in tags, releases, private project storage, or an optional history branch.

## Generated-source drift

CI should fail when canonical sources and committed projections differ. Every change to roles, methods, or routing should include the regenerated output and tests for the intended behavioral change.

## Low-level verification commands

The repository-level verifier is the preferred entrypoint. For diagnosis or CI composition, the underlying ordered pipeline can also be run directly in source mode:

```bash
python tools/run_tests.py --all --skip-package-manifest --require-node
```

Run only the unittest modules, with per-suite progress and the final consolidated error summary:

```bash
python tools/run_tests.py -v
```

Historical `tools/bootstrap.py` and release-package `tools/setup.py --test` entrypoints remain for compatibility and immutable releases. Public source workflows should use `verify_source_repository.py` and `repo_setup.py`.
