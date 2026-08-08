# Canonical BBK role package

The files in this directory are the canonical BBK role source.

- `catalog.json` owns the role-package version, constitution modules, interaction topology, four controller entrypoints, deterministic role order, role file paths, and allowed parent modes. The repository-wide release `VERSION` is reconciled separately during release integration.
- Each `bbk_*-role.json` file owns one role's semantic contract, including purpose, scope, responsibilities, authority, topology, primary procedure, prompt-module selection, and normalized role-return metadata.
- `../method-content.json` is the sole canonical procedure source. Generated `shared/skills/*/SKILL.md` files are projections and must not be edited independently.
- `../prompt-modules/catalog.json` and its module files own reusable cross-role behavior. A role's ordered `prompt_modules` list selects only the modules applicable to that responsibility.
- `../roles.json` is a deterministic compatibility projection. Do not edit it directly.
- `../contracts/catalog.json` owns the related contract-package catalogue. Role-specific result and return schemas are generated from each role's `return_contract`; see [`../contracts/README.md`](../contracts/README.md).

## Prompt and procedure composition

Each role declares one `primary_skill`. Its `mandatory_skills` list begins with that procedure. The current package needs only that primary procedure for every role because shared authority, routing, evidence, liveness, handoff, profile, and assurance behavior is compiled from small canonical prompt modules.

One procedure is a default, not a maximum. The module catalog deliberately sets no mandatory-procedure ceiling. Additional procedures are valid when they add distinct behavior not already supplied by the primary procedure or selected modules and carry a source-bound measurement record that the assembler recomputes. This replaces the former arbitrary three-procedure limit with a correctness criterion.

The assembler also verifies exact ownership for behavior-specific modules, including controller-mediated human requests, the full durable-handoff protocol, execution slicing, profile capability dispatch, EvidenceReceipt construction, and finding lifecycle management.

## Validation

Validate the canonical role package and its generated contract surfaces without writing changes:

```console
python tools/assemble_roles.py --check
python tools/return_contracts.py --check
python tools/validate_contract_package.py --check
```

Regenerate the role compatibility projection after an intentional canonical-source change:

```console
python tools/assemble_roles.py
```

The legacy command remains an exact compatibility wrapper:

```console
python tools/create_role_spec.py --check
```

`BBK_ALLOW_STAGED_ROLE_PACKAGE=1` is reserved for deliberate development states in which canonical package versions have not yet been reconciled. It is not part of normal validation or release qualification.

Assembly fails for schema violations, noncanonical JSON serialization, catalog/file drift, unknown skills or modules, stale mandatory-procedure measurements, inappropriate module ownership, one-sided delegation edges, invalid parent modes, controller-root drift, human-request-routing drift, or roles unreachable from the declared controller roots.

After canonical changes, regenerate and verify shared skills, host projections, documentation, package manifests, and release archives through the workflow in [`docs/DEVELOPMENT.md`](../../docs/DEVELOPMENT.md).
