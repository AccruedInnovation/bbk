# BBK 0.1.0-alpha.13.5 release notes

Alpha.13.5 is a narrowly bounded test-portability corrective over alpha.13.4.

## Corrected Windows routing test

The OMP project-routing isolation test still compared rendered paths by raw text in several places. On Windows, `tempfile` may expose a directory through an 8.3 spelling such as `TOMBST~1`, while BBK correctly reports the same physical path through its canonical long-name spelling. The runtime and routing state were correct, but the assertion failed before installation.

The correction now uses one shared `tests/_path_support.py` boundary for native filesystem paths. It:

- parses `Project`, `Binding`, and `State` fields from OMP notifications;
- compares existing objects with `os.path.samefile` and uses BBK's canonical physical-path key for missing or planned leaves;
- compares binding, routing-status, installer, profile, cache, and other native paths by physical identity;
- keeps exact spelling assertions explicit for portable relative paths and serialization contracts;
- deliberately exercises a POSIX symlink alias when available;
- emits raw, canonical, identity-key, and existence diagnostics on failure; and
- audits the test sources so direct `Path.resolve()` equality, direct `path_key`/`same_path` use, and interpolated native-path notification assertions cannot be reintroduced silently.

## Product behavior

No runtime, installer, role, prompt, execution-contract, Beads, OMP agent-tree, language-profile, or model-routing behavior changed. The exact reviewed 19-role default routing remains in force. Existing alpha.13.4 installations are operationally equivalent; alpha.13.5 removes the false Windows verification failure from `setup.py --test` and verification-first installation.

## Qualification

The release is qualified through the complete release profile, fresh archive extraction, strict package verification, deterministic rebuilding, routing verification, and installer smoke testing. The exact failing test is included in the qualification set.

## Repository and migration boundary

The extracted archive remains **Repository-native source**: canonical specifications, deterministic generators, tests, documentation, and package metadata are present without an external migration step.

The `docs/` directory contains **15 current** public-facing documents. Full qualification transcripts and **pre-public history** remain release-development records rather than public runtime dependencies.

**No `.bbk/` project-record migration** is required solely for alpha.13.5.
