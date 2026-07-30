# Contributing to BBK

BBK is pre-1.0 and still evolving quickly. Contributions are welcome when they improve the method, correctness, portability, usability, or evidence without silently broadening authority.

## Before opening a change

Describe:

- the operational problem or failure mode;
- current and expected behavior;
- the affected canonical source;
- compatibility and migration consequences;
- relevant host, platform, or profile boundaries;
- evidence that the change works.

## Canonical versus generated files

Most role, method, and model-routing changes begin in:

```text
spec/roles.json
spec/method-content.json
spec/model-routing.json
shared/skills/
shared/references/
```

Regenerate committed projections rather than editing generated agents directly:

```bash
python tools/create_method_content.py
python tools/create_role_spec.py
python tools/generate_agents.py
```

Then verify:

```bash
python tools/verify_source_repository.py --require-node
```

## Core versus profiles

Put host-neutral semantics, roles, records, installers, and host adapters in BBK core.

Put language-, framework-, runtime-, toolchain-, or domain-specific procedures and evidence adapters in the `bbk-language-profiles` repository.

Profiles may specialize procedure; they may not redefine core semantic objects or broaden authority.

## Pull requests

A useful pull request should include:

- a focused explanation;
- tests for behavior and failure cases;
- regenerated projections where applicable;
- documentation updates;
- a clear compatibility statement;
- truthful qualification limits.

Removing unnecessary ceremony, duplicated context, brittle assumptions, or token waste is as valuable as adding capability.

## Release evidence

Do not commit release ZIPs, package manifests, checksums, archive audits, full test logs, or version-specific qualification reports to `main`. Attach them to the corresponding GitHub Release.
