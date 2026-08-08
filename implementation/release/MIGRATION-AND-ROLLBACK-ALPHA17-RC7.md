# Alpha.17 RC7 Migration and Rollback

**Target:** `0.1.0-alpha.17+rc.7`

## Compatibility model

RC7 is additive over the Alpha.17 RC5 architecture and preserves existing read compatibility promised by Alpha.17. Legacy planning and return artifacts are not rewritten in place.

- Existing detailed planning baselines receive a compatibility readiness projection and `BASELINE_ADVANCED` migration anchor.
- Existing role returns remain readable; new writes may use atomic finalization and sidecar identity receipts.
- Existing project evidence and campaign artifacts remain in place during install, update, uninstall, and rollback.
- Routing compatibility is controlled by `schema_version`; `package_version` remains optional provenance.

## Clean project install

From an extracted RC7 archive:

```powershell
python .\tools\install.py install --scope project --root <PROJECT> --codex --omp --generic --no-language-profiles --keep-existing
python .\tools\install.py status --scope project --root <PROJECT>
```

Select only the harnesses required by the project. The installer validates package ownership and never deletes unrelated skills or unselected harness files.

## In-place upgrade

```powershell
python .\tools\install.py install --scope project --root <PROJECT> --codex --omp --generic --no-language-profiles --keep-existing
python .\tools\install.py status --scope project --root <PROJECT>
```

The transaction installs the RC7 canonical procedure source tree, schemas, CLI, role projections, effective catalogs, and install manifest. Compiled procedures are not installed in automatically indexed skill roots. The previous version remains independently recoverable from its package or installer backup.

## Toolchain

The project `mise.toml` owns `jj@0.43.0` and `github:gastownhall/beads@1.1.0`. Global `jj` or `bd` is not required. Git, Python, mise, and the selected harness remain host prerequisites.

## Rollback

For an isolated or project-scope RC7 installation:

```powershell
python .\tools\install.py uninstall --scope project --root <PROJECT>
```

Then reinstall the preserved predecessor archive with the same selected harnesses. A manual qualification kit also contains `rollback-isolated-rc.ps1`, which uses the current RC7 path token and preserves unowned project files and evidence.

Rollback restores the prior managed projections, indexed skill catalog, procedure-source version, schemas/CLI, and install manifest. It does not delete campaign artifacts created under RC7; older writers may treat additive RC7 records as unsupported but must preserve them.

## Failure semantics

- Before install-manifest publication, the prior installation remains authoritative.
- A post-publication validation failure triggers bounded rollback and reports both outcomes.
- Prompt/catalog suppression mismatch is blocking; the installer must not launch a child with duplicate compiled and external visibility.
- Planning migration failure leaves immutable predecessor artifacts and the prior current pointer intact.
- Atomic result/manifest or plan-transaction failure restores the exact prior authoritative pair/projections.

## Verification required at release freeze

The release record binds clean install, RC5 upgrade, Alpha.16.1 upgrade compatibility, status, uninstall, rollback, unrelated-file preservation, extracted-archive verification, and deterministic duplicate builds.
