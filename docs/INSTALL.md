# Installing BBK

BBK is distributed in two forms:

- a mutable Git source checkout intended for development and contribution;
- an immutable release archive intended for self-contained installation and strict package verification.

The commands differ because a Git working tree is not an immutable package.

## Source checkout

The recommended source layout is:

```text
workspace/
├── bbk/
└── bbk-language-profiles/
```

Verify the source checkout:

```bash
python tools/verify_source_repository.py --require-node
```

Verify and install BBK with all profiles from the sibling repository:

```bash
python tools/repo_setup.py --test-and-install \
  --scope user \
  --omp --codex
```

`repo_setup.py` auto-detects `../bbk-language-profiles`. Override it explicitly when necessary:

```bash
python tools/repo_setup.py --test-and-install \
  --scope user \
  --omp --codex \
  --language-profiles /path/to/bbk-language-profiles
```

Select a subset:

```bash
python tools/repo_setup.py --test-and-install \
  --scope user \
  --omp --codex \
  --profile-id rust \
  --profile-id python
```

Install core only:

```bash
python tools/repo_setup.py --test-and-install \
  --scope user \
  --omp --codex \
  --no-language-profiles
```

Preview without writing:

```bash
python tools/repo_setup.py --test-and-install \
  --scope user \
  --omp --codex \
  --dry-run
```

## Release archive

A published release may bundle exact qualified profile snapshots. From an extracted release:

```bash
python tools/setup.py --verify
python tools/setup.py --test-and-install --scope user --omp --codex
```

Strict package verification applies only to the release form:

```bash
python tools/verify_package.py --strict-mode
```

## Harness selection

Select only the hosts in use:

```text
--omp
--codex
--claude
--generic
```

Omitting every harness selector may select all supported hosts, depending on the release. Prefer explicit selectors in automation.

## User and project scopes

User scope installs into the selected host's user directories and BBK's user data root:

```bash
python tools/repo_setup.py --test-and-install --scope user --omp --codex
```

Project scope installs into one repository:

```bash
python tools/repo_setup.py --test-and-install \
  --scope project \
  --root /path/to/project \
  --omp --codex
```

## Model routing

The packaged default policy is `spec/model-routing.json`. To customize it without editing generated agents:

```bash
cp spec/model-routing.json ../my-model-routing.json
python tools/model_routing.py --path ../my-model-routing.json --check
python tools/repo_setup.py --test-and-install \
  --scope user --omp --codex \
  --model-routing ../my-model-routing.json
```

OMP runtime routing can later be changed with `/bbk:models` without modifying Codex or Claude definitions.

## Selective host updates

Use the release or source tooling appropriate to the installed version:

```bash
python tools/setup.py --update-omp --scope user
python tools/setup.py --update-codex --scope user
```

The selective updater reconciles the unified installation manifest while leaving other host definitions untouched. Review a dry run first.

## Status and uninstall

```bash
python tools/install.py status --scope user
python tools/install.py uninstall --scope user --dry-run
python tools/install.py uninstall --scope user
```

BBK removes only unchanged manifest-owned files unless force behavior is explicitly requested. Modified files are preserved and reported.

## Source/release boundary

The Git source repository intentionally excludes:

- bundled profile ZIPs;
- `PACKAGE-MANIFEST.json`;
- release checksums;
- archive audits;
- full qualification logs;
- version-specific release notes.

`tools/build_public_release.py` stages the source checkout together with exact profile packages from the sibling profile repository and invokes the existing immutable release builder.
