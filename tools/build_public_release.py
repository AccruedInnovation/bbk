#!/usr/bin/env python3
"""Stage a self-contained immutable BBK release from two public source repos."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_source(destination: Path) -> None:
    excluded = {
        ".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
        "build", "dist", "out", "release", "bundled-language-profiles",
    }

    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored = {name for name in names if name in excluded}
        for name in names:
            if name == "PACKAGE-MANIFEST.json" or name.endswith((".pyc", ".pyo", ".zip", ".sha256")):
                ignored.add(name)
            if name in {"SHA256SUMS.txt", "RELEASE-NOTES.md"}:
                ignored.add(name)
        return ignored

    shutil.copytree(ROOT, destination, ignore=ignore)


def profile_roots(repository: Path) -> list[Path]:
    packages = repository / "packages" if (repository / "packages").is_dir() else repository
    roots = sorted(
        [path for path in packages.iterdir() if path.is_dir() and (path / "PROFILE.json").is_file()],
        key=lambda value: value.name,
    )
    if not roots:
        raise RuntimeError(f"no extracted profile packages found beneath {packages}")
    return roots


def build_profile(profile: Path, output: Path) -> Path:
    builder = profile / "tools" / "build_release.py"
    if not builder.is_file():
        raise RuntimeError(f"profile has no release builder: {profile}")
    command = [sys.executable, str(builder), "--skip-tests", "--output-dir", str(output)]
    print(f"==> Building profile package: {profile.name}", flush=True)
    completed = subprocess.run(command, cwd=profile, check=False)
    if completed.returncode:
        raise RuntimeError(f"profile build failed ({completed.returncode}): {profile.name}")
    candidates = sorted(output.glob(f"{profile.name}.zip"))
    if not candidates:
        version = (profile / "VERSION").read_text(encoding="utf-8").strip()
        candidates = sorted(output.glob(f"*{version}*.zip"))
    if len(candidates) != 1:
        raise RuntimeError(f"could not identify one release ZIP for {profile.name}: {candidates}")
    return candidates[0]


def write_bundle(bundle: Path, archives: list[Path], bbk_version: str) -> None:
    package_dir = bundle / "packages"
    package_dir.mkdir(parents=True, exist_ok=True)
    for archive in archives:
        shutil.copy2(archive, package_dir / archive.name)
        digest = sha256(archive)
        (package_dir / f"{archive.name}.sha256").write_text(
            f"{digest}  {archive.name}\n", encoding="utf-8"
        )

    (bundle / "README.md").write_text(
        "# Bundled BBK language profiles\n\n"
        "This directory is generated while staging an immutable BBK release. "
        "The editable profile sources live in the separate `bbk-language-profiles` repository.\n",
        encoding="utf-8",
    )
    checksum_lines = [
        f"{sha256(path)}  {path.relative_to(bundle).as_posix()}"
        for path in sorted(package_dir.glob("*.zip"), key=lambda value: value.name)
    ]
    (bundle / "SHA256SUMS.txt").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    files: list[dict[str, Any]] = []
    for path in sorted(bundle.rglob("*"), key=lambda value: value.relative_to(bundle).as_posix()):
        if not path.is_file() or path.name == "RELEASE-MANIFEST.json":
            continue
        files.append({
            "path": path.relative_to(bundle).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        })
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH", "0"))
    generated = dt.datetime.fromtimestamp(epoch, tz=dt.timezone.utc).isoformat().replace("+00:00", "Z")
    manifest = {
        "schema": "bbk.language-profiles-release-bundle-manifest.v1",
        "status": "PASS",
        "release": "source-staged",
        "variant": f"bundled-with-bbk-{bbk_version}",
        "generatedAt": generated,
        "timezone": "UTC",
        "fileCount": len(files),
        "files": files,
    }
    (bundle / "RELEASE-MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language-profiles", required=True, help="expanded bbk-language-profiles repository")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--require-node", action="store_true")
    args = parser.parse_args(argv)

    profiles_repo = Path(args.language_profiles).expanduser().resolve()
    output = Path(args.output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    if not args.skip_tests:
        command = [sys.executable, "tools/verify_source_repository.py"]
        if args.require_node:
            command.append("--require-node")
        if subprocess.run(command, cwd=ROOT, check=False).returncode:
            return 1

    with tempfile.TemporaryDirectory(prefix="bbk-release-stage-") as raw:
        temp = Path(raw)
        stage = temp / ROOT.name
        copy_source(stage)
        built_profiles = temp / "profile-builds"
        built_profiles.mkdir()
        archives = [build_profile(profile, built_profiles) for profile in profile_roots(profiles_repo)]
        version = (stage / "VERSION").read_text(encoding="utf-8").strip()
        write_bundle(stage / "bundled-language-profiles", archives, version)

        builder = stage / "tools" / "build_release.py"
        if not builder.is_file():
            raise RuntimeError("staged BBK tree has no tools/build_release.py")
        command = [sys.executable, str(builder), "--skip-tests", "--output-dir", str(output)]
        print("==> Building immutable BBK release from staged source and profiles", flush=True)
        completed = subprocess.run(command, cwd=stage, check=False)
        if completed.returncode:
            return completed.returncode
    print(f"Release artifacts written to {output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
