# Upgrading BBK

Use a clean extraction for each BBK version. Do not overlay a new release onto an
older extracted package.

## Full managed upgrade

From the previous extraction:

```bash
python tools/install.py uninstall --scope user
```

From the new extraction:

```bash
python tools/setup.py --test-and-install --scope user --omp --codex --claude
```

All bundled language profiles install by default. Add `--no-language-profiles`
for an intentional core-only installation or repeated `--profile-id` options for
a subset.

## Selective host updates

Update OMP without modifying the installed Codex agents:

```bash
python tools/setup.py --test-and-update-omp --scope user
```

Update Codex agents without modifying OMP:

```bash
python tools/setup.py --test-and-update-codex --scope user
```

Use the corresponding non-test form only after the exact extraction has already
passed verification. Start a fresh Codex session after a Codex-agent update; use
`/reload-plugins` in an existing OMP session after an OMP extension update.

## Project records

A release note will state explicitly when `.bbk/` project-record migration is
required. In the absence of such a statement, preserve the records and validate
them with the new CLI before continuing consequential work.

## External routing policies

External model-routing files are package-version-bound. Update their
`package_version` to the installed BBK version and validate them before use:

```bash
python tools/model_routing.py --path /path/to/model-routing.json --check
```
