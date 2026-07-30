# Qualification model

This document describes the evergreen verification model. Exact test counts, environment versions, hashes, and pass reports belong to the relevant GitHub Release.

## Source repository verification

A mutable source checkout has no immutable package manifest. Run:

```bash
python tools/verify_source_repository.py --require-node
```

The source verification sequence checks:

1. method-content projection drift;
2. canonical role-specification drift;
3. install-time model-routing validity;
4. generated-agent projection drift;
5. Python compilation, JSON parsing, and text-encoding rules;
6. semantic and schema fixtures;
7. typed profile-dispatch fixtures;
8. the ordered behavioral unittest corpus;
9. OMP extension syntax when Node.js is available or required.

## Release qualification

A staged immutable release additionally checks:

- strict package-manifest integrity before package code runs;
- exact bundled-profile package identities and manifests;
- archive inventory, paths, modes, timestamps, CRCs, and digests;
- reproducible source and clean-extraction builds;
- clean-extraction replay;
- installation/status/uninstall ownership behavior;
- release checksums and external manifests.

Use `tools/build_public_release.py` to stage a release from the BBK and profile source repositories.

## Qualification does not prove

Package or source verification does not prove:

- live model/provider availability or competence;
- perfect host isolation or task-agent lifecycle behavior;
- actual physical review independence;
- external compiler, IDE, simulator, license, or toolchain behavior;
- target-project correctness, safety, security, compliance, or operational success;
- human or organizational approval.

Those are separate declared qualification subjects.

## Evidence discipline

Qualification evidence should identify:

- exact subject and version;
- environment and relevant dependencies;
- commands and methods used;
- pass, fail, blocked, unavailable, and not-applicable states;
- residual limitations;
- content identities and hashes where exact reuse matters.

For unittest-only diagnosis, use the PowerShell-safe runner directly:

```bash
python tools/run_tests.py -v
```

It executes each module independently, streams progress, preserves the real exit code, and repeats every failure or error in the final summary.
