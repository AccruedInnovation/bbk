# BBK contract package

This directory records the canonical alpha.13 source contract for role returns and the catalogue of formal execution companion objects. It is a source package, not a completed release projection.

## Source direction

Each `spec/roles/bbk_*-role.json` file owns its normalized `return_contract`. The deterministic generator then produces:

```text
canonical split role return_contract
        │
        ├── tools/return_contracts.py
        │       ├── spec/schemas/role-results/*-result-v1.schema.json
        │       ├── spec/schemas/role-returns/*-return-v1.schema.json
        │       └── spec/contracts/role-return-registry.json
        │
        └── spec/schemas/bbk-role-return-v1.schema.json
                common envelope
```

Generated return and result schemas and the registry must not be edited independently. Check them with:

```console
python -S tools/return_contracts.py --check
```

Regenerate them after an intentional split-role contract change with:

```console
python -S tools/return_contracts.py --write
```

## Return semantics

Every canonical return separates:

- operational disposition of the physical attempt;
- role-specific semantic state of the subject contribution;
- role-specific result data;
- authority and effects actually used;
- durable handoff references;
- the smallest valid next action.

A schema-valid return does not establish parent acceptance, outcome satisfaction, risk acceptance, candidate validity, campaign completion, release, or authority not otherwise granted.

`READY_FOR_VALIDATION`, `BLOCKED`, and `PAUSED` are consume-only legacy `bbk.handoff.v1` operational values. Current role-return contracts do not emit them.

## Execution companion objects

`catalog.json` declares four active execution contracts:

- `bbk.territory-execution-boundary.v1` — compiled and admitted by Root Orchestrator; operated within and completion-reported by Territory Orchestrator; immutable after admission except through a successor boundary.
- `bbk.local-discovery-policy.v1` — zero-default policy and budget ceiling owned by Territory Orchestrator.
- `bbk.local-discovery-envelope.v1` — boundary-, exact cohort-charter identity/digest-, authority-, candidate-, validation-, expiry-, and budget-bound allowance issued by Territory Orchestrator. Its `PLANNED_EFFORT_UNIT` denominator is the nonnegative integer relative planning total declared by that exact compiled cohort charter; it is not elapsed time, cost, token count, model confidence, or completion percentage.
- `bbk.local-discovery-permit.v1` — one exact discovery item under one active envelope, with one-to-one prohibited-governance declarations and explicit candidate/validation impact.

`WorkerValidationBatch` is retired and was never implemented. Candidate production remains a Worker-cohort lifecycle. Assurance remains a separate candidate-bound assurance-run lifecycle linked by immutable candidate identity.

`spec/capability-status.json` distinguishes deterministic implementation, bootstrap implementation, schema-defined companion contracts, optional host capabilities, target-only capabilities, and retired concepts. Prose or model confidence is not an equivalent implementation state.

## Contract-package validation

Run the source-level contract checks with:

```console
python tools/validate_contract_package.py --check
python -m unittest discover -s tests -p 'test_contract_package_v1.py' -v
```

Contract-package validation checks canonical contract sources and examples. Complete release qualification additionally regenerates host projections, verifies installers and manifests, and tests clean extracted archives.
