# BBK documentation

The root [`README.md`](../README.md) is the public overview. This directory holds the operating, method, assurance, host, and maintainer guides for the current package. Release changes are recorded in [`RELEASE-NOTES.md`](../RELEASE-NOTES.md) and [`CHANGELOG.md`](../CHANGELOG.md).

## Start here

- [`INSTALL.md`](INSTALL.md) — prerequisites, install scopes, host selection, updates, status, and removal.
- [`USAGE.md`](USAGE.md) — day-to-day operation, BBK mode, project records, execution, assurance, artifacts, and recovery.
- [`UPGRADING.md`](UPGRADING.md) — safe upgrade and rollback procedure.
- [`BOUNDARIES.md`](BOUNDARIES.md) — what BBK verifies, what it cannot prove, and where host or human authority remains decisive.

## Roles and method

- [`AGENTS.md`](AGENTS.md) — the 19 canonical roles, four controller roots, delegation, scope, return contracts, and generated projections.
- [`WAYFINDING-AND-GRILL.md`](WAYFINDING-AND-GRILL.md) — recommendation-first wayfinding and focused deep-question escalation.
- [`SOLUTION-OUTCOME-FIT.md`](SOLUTION-OUTCOME-FIT.md) — checking whether a proposed intervention fits the required outcome.
- [`EXECUTION-DESIGN.md`](EXECUTION-DESIGN.md) — implementation structure, state and effects, slices, WorkUnits, authority, and ownership.
- [`DURABLE-HANDOFFS.md`](DURABLE-HANDOFFS.md) — resumable workers and exact, digest-bound handoffs.
- [`ASSURANCE.md`](ASSURANCE.md) — candidate identity, review context, evidence, findings, invalidation, and intent checks.

## Hosts, routing, and profiles

- [`MODEL-ROUTING.md`](MODEL-ROUTING.md) — install-time routes, OMP runtime profiles, precedence, validation, and overrides.
- [`LANGUAGE-PROFILES.md`](LANGUAGE-PROFILES.md) — bundled profiles, typed capability dispatch, installation, and ownership.
- [`OMP-CHILD-LIFETIME.md`](OMP-CHILD-LIFETIME.md) — qualified OMP child scheduling, waiting, cancellation, and continuation behavior.
- [`../omp/extension/README.md`](../omp/extension/README.md) — OMP extension commands and runtime boundary.

## Release implementation records

These documents describe current implementation constraints that remain part of the package contract:

- [`CRITICAL-PATH-EXECUTION-ALPHA17.md`](CRITICAL-PATH-EXECUTION-ALPHA17.md)
- [`PROMPT-COMPILATION-ALPHA17.0.1.md`](PROMPT-COMPILATION-ALPHA17.0.1.md)

The `qualification/` directory retains release-specific test and host qualification records. Those records document the exact candidate and host boundary they tested; they are not general operating instructions and do not become current merely because they remain in the package.

## Maintainers

- [`DEVELOPMENT.md`](DEVELOPMENT.md) — canonical sources, generation, testing, documentation checks, and release builds.
- [`../spec/roles/README.md`](../spec/roles/README.md) — split role-source workflow.
- [`../spec/contracts/README.md`](../spec/contracts/README.md) — return and execution companion contracts.
- [`../spec/prompt-modules/README.md`](../spec/prompt-modules/README.md) — reusable prompt-module workflow.

Generated projections and reports should be changed through their canonical sources. See [`DEVELOPMENT.md`](DEVELOPMENT.md) before editing files under `projections/` or generated compatibility files under `spec/`.
