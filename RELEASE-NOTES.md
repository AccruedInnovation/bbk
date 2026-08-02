# BBK 0.1.0-alpha.13.1 release notes

**Release date:** 2026-08-02
**Change class:** test-reliability and verification-performance correction

Alpha.13.1 is an immutable corrective successor to alpha.13. It preserves alpha.13's canonical split-role package, role and execution contracts, prompt modules, generated role behavior, and reviewed default model routing. It fixes one release-test dependency defect and restores the behavior-test process reuse that had regressed during the Gate 1–5 integration.

No `.bbk/` project-record migration is required. A clean alpha.13.1 extraction should be used instead of modifying or overlaying the published alpha.13 archive.

## Contract tests no longer require `jsonschema`

Alpha.13 imported `jsonschema` at test-module collection time in `test_contract_package_v1.py`. On a valid minimal Python installation without that optional package, the entire 27-test module became one loader error:

```text
ModuleNotFoundError: No module named 'jsonschema'
```

Alpha.13.1 corrects the dependency boundary:

- role-return generation and deterministic contract validation use only the Python standard library;
- the contract suite imports and runs under `python -S` without site packages;
- all common-envelope fields, catalogue parent admissions, exact discriminators, result-field kinds, nullability, supplemental enums, references, artifacts, handoffs, effects, and next-action records are covered by a contract-specific deterministic validator;
- Draft 2020-12 meta-schema and instance validation still runs as an additional cross-check when `jsonschema` and `referencing` are installed; and
- the standalone full JSON Schema validator continues to report an explicit dependency blocker when those optional packages are absent rather than silently claiming schema-engine validation occurred.

This keeps `jsonschema` optional for ordinary BBK verification while preserving the stronger external-engine qualification path when available.

## Faster behavior-level tests

The test runner still gives each consolidated unittest module an isolated Python process and still runs up to four independent modules concurrently by default. Inside those module processes, alpha.13.1 avoids repeatedly starting another Python interpreter for ordinary BBK CLI assertions.

The shared test adapter now reuses cached public `main(argv)` entry points for canonical BBK tools, including installation, routing, role assembly, projection, source-sanity, update, and contract commands. Trusted package-local language-profile fixtures used by `bbk profile` tests also execute in-process. Real subprocesses remain mandatory where the process boundary is the behavior under test, including:

- `python -S`, `-I`, `-E`, and `-s` import-isolation checks;
- Node.js and Git integration;
- process-tree timeout and stdin-isolation behavior;
- installed or deliberately modified scripts that do not exactly match an eligible source;
- raw stream, filesystem, and platform boundary tests; and
- explicit `force_subprocess` calls.

On the release qualification host, the same default eight-suite command changed from **42.48 seconds** for published alpha.13 to **25.21 seconds** for alpha.13.1, a **40.7% wall-clock reduction**. Windows results depend on storage and security-scanner behavior, but the eliminated interpreter launches are expected to have a larger effect on Windows than on the Linux qualification host.

## Alpha.13 behavior retained

Alpha.13.1 does not change:

- the 19 canonical split roles or four controller-selectable roots;
- Prototyper, Planning/Phase, review, validation, or orchestration responsibilities;
- `bbk.role-return.v1`, role-specific return/result contracts, or execution-contract semantics;
- the 21 prompt modules or role/module assignments;
- current operational dispositions or legacy handoff-read compatibility;
- OMP prompt replacement, persistent `/bbk` mode, activity display, or ask-backed decision routing;
- installation targets, selective OMP/Codex updates, or bundled language-profile versions; or
- the reviewed 19-role default model routes introduced in alpha.13.

`spec/model-routing.json`, the OMP `default` profile, all generated OMP/Codex/Claude projections, and the routing regression fixture remain bound to the exact reviewed per-role selections from `roles-update.zip`; only their package-version binding advances to `0.1.0-alpha.13.1`.

## Verify and install

Run complete qualification from the clean extraction:

```bash
python tools/run_tests.py --all --require-node
```

For a concise unittest-only run:

```bash
python tools/run_tests.py -q
```

For serial diagnosis:

```bash
python tools/run_tests.py -v --jobs 1
```

Then install:

```bash
python tools/bootstrap.py --test-and-install --scope user --omp --codex --claude
```

A previously qualified installation can still use the selective host update commands documented in `docs/UPGRADING.md`.

## Repository-native source and documentation boundary

The extracted archive remains **Repository-native source**: canonical specifications, deterministic generators, tests, documentation, and package metadata are all present in the repository tree rather than requiring an external migration step.

The `docs/` directory contains **14 current** public-consumer documents. Full qualification transcripts and **pre-public history** remain release-development records rather than public runtime dependencies.

No `.bbk/` project-record migration is required solely for alpha.13.1. Existing project records remain governed by their own schema and version rules.

## Qualification boundary

Package qualification proves deterministic source and generated artifacts, package integrity, the tested installer/runtime contracts, dependency-free core contract validation, and the optional external JSON Schema path when its dependencies are present. It does not prove live model availability or competence, target-project correctness, external toolchain behavior, physical reviewer independence, or official Blueprint authority.
